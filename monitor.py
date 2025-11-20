#!/usr/bin/env python3
"""
政府採購網軟體標案監控
- 使用 g0v pcc-api.openfun.app API
- 自動抓取招標中的軟體案件
- SQLite 去重避免重複通知
- 支援 LINE Messaging API 推播
"""

import requests
import sqlite3
import sys
import os
import re
import time
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path

# ===== 日誌系統設定 =====

# 建立 logs 目錄
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 設定 logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 檔案處理器（帶時間輪轉）
file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "monitor.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)

# 控制台處理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 格式化
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ===== 配置區 =====

# 使用 Cloudflare Workers 反向代理（解決 GitHub Actions IP 封鎖問題）
API_BASE_URL = "https://morning-pine-2053.alexabc.workers.dev/api"

# API 請求 Headers（使用完整瀏覽器 headers 避免被阻擋）
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://pcc-api.openfun.app/',
    'Origin': 'https://pcc-api.openfun.app',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin'
}

# 預算範圍
MIN_BUDGET = 150000
MAX_BUDGET = 1500000

# 搜尋關鍵字（使用 searchbytitle API,伺服器端過濾）
SEARCH_KEYWORDS = ["軟體", "APP", "網站", "應用程式"]

# 排除關鍵字（本地端二次過濾）
KEYWORDS_EXCLUDE = [
    "硬體", "電腦", "監控", "機房", "土木", "網路設備", "交換器",
    "設備維護", "設備保養", "機電", "空調", "電梯", "消防系統",
    "清潔維護", "環境維護", "景觀維護", "綠美化", "水電",
    "高低壓", "變壓器", "發電機", "冷氣", "冰水主機", "污水",
    "抽水", "給水", "排水", "管線維護", "道路維護", "設施維護",
    "道路", "路面", "交通設施", "花木", "綠地", "垃圾", "清運",
    "手術", "顯微鏡", "醫療設備", "保全", "廣播系統", "景觀設施",
    "石綿", "回饋金", "灌溉", "熱泵", "噴水", "附加儲存", "NAS",
    "消防", "電力", "機械", "儀器", "儀控"
]

# LINE Messaging API 配置（從環境變數讀取）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.getenv("LINE_USER_ID", "")

# 資料庫路徑
DB_PATH = "tenders.db"

# API 請求間隔（秒）
API_DELAY = 0.5

# API 超時設定（秒）
API_TIMEOUT = 15  # 從 30 秒改為 15 秒


# ===== 資料庫初始化 =====

def init_db():
    """初始化 SQLite 資料庫"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenders (
                    unit_id TEXT,
                    job_number TEXT,
                    brief TEXT,
                    unit_name TEXT,
                    budget INTEGER,
                    pk_pms_main TEXT,
                    deadline TEXT,
                    date_added TEXT,
                    notified INTEGER DEFAULT 0,
                    PRIMARY KEY (unit_id, job_number)
                )
            """)

            conn.commit()
            logger.debug("資料庫初始化成功")
    except sqlite3.Error as e:
        logger.error(f"資料庫初始化失敗: {e}")
        raise


def is_new_tender(unit_id, job_number):
    """檢查標案是否為新案"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM tenders WHERE unit_id = ? AND job_number = ? LIMIT 1",
                (unit_id, job_number)
            )
            result = cursor.fetchone()
            return result is None
    except sqlite3.Error as e:
        logger.error(f"資料庫查詢錯誤: {e}")
        # 發生錯誤時，假設是新案（寧可重複通知也不要漏掉）
        return True


def save_tender(unit_id, job_number, brief, unit_name, budget, pk_pms_main, deadline):
    """儲存標案到資料庫，返回是否成功"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO tenders (unit_id, job_number, brief, unit_name, budget, pk_pms_main, deadline, date_added)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (unit_id, job_number, brief, unit_name, budget, pk_pms_main, deadline, now))

            conn.commit()
            logger.debug(f"標案已儲存: {brief[:40]}...")
            return True
    except sqlite3.IntegrityError:
        # 已存在（PRIMARY KEY 衝突），不是新標案
        logger.debug(f"標案已存在: {unit_id}/{job_number}")
        return False
    except sqlite3.Error as e:
        logger.error(f"儲存標案失敗: {e}")
        return False


def cleanup_old_tenders():
    """清理 3 個月前的舊標案資料"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # 計算 90 天前的日期
            three_months_ago = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

            # 刪除舊資料
            cursor.execute("DELETE FROM tenders WHERE date_added < ?", (three_months_ago,))
            deleted_count = cursor.rowcount

            conn.commit()

            if deleted_count > 0:
                logger.info(f"清理了 {deleted_count} 筆超過 3 個月的舊標案")

            return deleted_count
    except sqlite3.Error as e:
        logger.error(f"清理舊資料失敗: {e}")
        return 0


# ===== LINE Messaging API 通知 =====

def send_line_message(message):
    """發送 LINE Messaging API 推送訊息"""
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        logger.warning("LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID 未設定，跳過通知")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("LINE 通知發送成功")
            return True
        else:
            logger.warning(f"LINE 通知發送失敗: HTTP {response.status_code}")
            logger.debug(f"回應內容: {response.text}")
            return False
    except requests.exceptions.Timeout:
        logger.error("LINE 通知超時")
        return False
    except Exception as e:
        logger.error(f"LINE 通知失敗: {e}")
        return False


# ===== 核心爬蟲邏輯 =====

def parse_budget(budget_str):
    """
    解析預算字串，回傳數字
    支援格式：
    - "562,937元"
    - "約 562,937 元"
    - "562937"
    - "$562,937"
    """
    if not budget_str:
        return None

    try:
        # 移除常見前綴和單位
        budget_str = re.sub(r'[約^~\s]', '', budget_str)
        budget_str = re.sub(r'[元$€¥]', '', budget_str)

        # 提取所有數字和逗號
        budget_str = re.sub(r'[^\d,]', '', budget_str)

        # 移除逗號
        budget_str = budget_str.replace(',', '')

        if not budget_str:
            return None

        return int(budget_str)
    except (ValueError, AttributeError) as e:
        logger.warning(f"預算解析失敗: {budget_str} - {e}")
        return None


def parse_roc_date(roc_date_str):
    """
    解析民國或西元日期，回傳 ISO 格式字串

    支援格式：
    - 114/10/27 17:00 (民國年)
    - 2025/10/27 17:00 (西元年)
    - 114-10-27 (民國年，ISO 格式)
    - 10/27 (僅日期，年份使用當年)
    """
    if not roc_date_str:
        return None

    roc_date_str = roc_date_str.strip()

    try:
        # 嘗試多種格式
        formats = [
            "%Y/%m/%d %H:%M",    # 西元: 2025/10/27 17:00
            "%Y/%m/%d",          # 西元: 2025/10/27
            "%Y-%m-%d %H:%M",    # 西元: 2025-10-27 17:00
            "%Y-%m-%d",          # 西元: 2025-10-27
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(roc_date_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

        # 民國年格式: 114/10/27 17:00 或 114/10/27
        match = re.match(
            r"^(\d{3})/(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$",
            roc_date_str
        )

        if match:
            year_roc, month, day, hour, minute = match.groups()
            year_ad = int(year_roc) + 1911
            hour = int(hour) if hour else 0
            minute = int(minute) if minute else 0

            # 驗證日期有效性
            try:
                dt = datetime(int(year_ad), int(month), int(day), hour, minute)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError as e:
                logger.warning(f"無效的日期值: {roc_date_str} - {e}")
                return None

        logger.warning(f"無法解析日期格式: {roc_date_str}")
        return None

    except Exception as e:
        logger.error(f"日期解析異常: {roc_date_str} - {e}")
        return None


def get_tender_detail(unit_id, job_number):
    """查詢單一標案的詳細資料，回傳 (budget, pk_pms_main, deadline)"""
    try:
        # 加入延遲避免 rate limiting
        time.sleep(API_DELAY)

        url = f"{API_BASE_URL}/tender"
        params = {'unit_id': unit_id, 'job_number': job_number}

        response = requests.get(url, params=params, headers=HEADERS, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        if 'records' in data and len(data['records']) > 0:
            detail = data['records'][0].get('detail', {})
            budget_str = detail.get('採購資料:預算金額', '')
            pk_pms_main = detail.get('pkPmsMain', '')
            deadline_str = detail.get('領投開標:截止投標', '')

            budget = parse_budget(budget_str)
            deadline = parse_roc_date(deadline_str)

            if budget and deadline:
                return (budget, pk_pms_main, deadline)

        return None

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning(f"API 請求過於頻繁，等待後重試...")
            time.sleep(3)  # 等待 3 秒後重試
            return get_tender_detail(unit_id, job_number)  # 遞迴重試一次
        logger.error(f"查詢標案詳細資料失敗 ({unit_id}/{job_number}): HTTP {e.response.status_code}")
        return None
    except requests.exceptions.Timeout:
        logger.error(f"查詢標案超時 ({unit_id}/{job_number})")
        return None
    except Exception as e:
        logger.error(f"查詢標案詳細資料失敗 ({unit_id}/{job_number}): {e}")
        return None


def fetch_tenders():
    """抓取並過濾政府採購標案（使用 searchbytitle API）"""
    logger.info("="*60)
    logger.info("開始抓取資料...")
    logger.info("="*60)

    try:
        # 初始化資料庫
        init_db()

        # 清理 3 個月前的舊資料
        cleanup_old_tenders()

        today = datetime.now()
        new_cases = []
        processed_tenders = set()  # 去重：同一標案可能出現在多個關鍵字結果中

        # 使用 searchbytitle API 搜尋關鍵字
        logger.info(f"搜尋關鍵字: {', '.join(SEARCH_KEYWORDS)}")

        for keyword in SEARCH_KEYWORDS:
            logger.info(f"\n搜尋關鍵字: 「{keyword}」")

            url = f"{API_BASE_URL}/searchbytitle"
            params = {'query': keyword, 'page': 1}

            try:
                response = requests.get(url, params=params, headers=HEADERS, timeout=API_TIMEOUT)
                response.raise_for_status()

                data = response.json()
                records = data.get('records', [])
                total_records = data.get('total_records', 0)

                logger.info(f"  找到 {total_records} 筆，處理第 1 頁 ({len(records)} 筆)")

                # 處理搜尋結果
                for record in records:
                    brief_data = record.get('brief', {})
                    title = brief_data.get('title', '')
                    unit_id = record.get('unit_id', '')
                    job_number = record.get('job_number', '')
                    unit_name = record.get('unit_name', 'N/A')

                    # 去重檢查
                    tender_key = f"{unit_id}/{job_number}"
                    if tender_key in processed_tenders:
                        logger.debug(f"    跳過重複標案: {title[:40]}...")
                        continue

                    processed_tenders.add(tender_key)

                    # 排除關鍵字檢查
                    if any(exclude_kw in title for exclude_kw in KEYWORDS_EXCLUDE):
                        logger.debug(f"    排除: {title[:40]}... (包含排除關鍵字)")
                        continue

                    # 檢查是否為新案
                    if not is_new_tender(unit_id, job_number):
                        logger.debug(f"    跳過已存在標案: {title[:40]}...")
                        continue

                    logger.info(f"  ✓ 發現候選標案: {title[:60]}...")

                    # 查詢詳細資料取得預算和 pkPmsMain
                    result = get_tender_detail(unit_id, job_number)

                    if result is None:
                        logger.warning(f"    無法取得完整資訊（預算或截止日期），跳過")
                        continue

                    budget, pk_pms_main, deadline = result

                    # 預算過濾
                    if not (MIN_BUDGET <= budget <= MAX_BUDGET):
                        logger.debug(f"    預算不符 (${budget:,})")
                        continue

                    # 截止日期檢查
                    deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
                    if deadline_dt <= today:
                        logger.debug(f"    已截止 ({deadline})")
                        continue

                    logger.info(f"    ✓ 預算符合 (${budget:,})，截止日期：{deadline}")

                    # 儲存並加入新案清單
                    if save_tender(unit_id, job_number, title, unit_name, budget, pk_pms_main, deadline):
                        new_cases.append({
                            'unit_id': unit_id,
                            'job_number': job_number,
                            'brief': title,
                            'unit': unit_name,
                            'budget': budget,
                            'pk_pms_main': pk_pms_main,
                            'deadline': deadline
                        })

            except requests.exceptions.Timeout:
                logger.error(f"搜尋「{keyword}」超時，跳過")
                continue
            except requests.exceptions.RequestException as e:
                logger.error(f"搜尋「{keyword}」失敗: {e}")
                continue

        # 輸出結果
        logger.info("="*60)
        logger.info(f"本次發現 {len(new_cases)} 筆新標案（已處理 {len(processed_tenders)} 筆候選標案）")
        logger.info("="*60)

        if new_cases:
            # 準備 LINE 通知訊息
            line_message = f"\n🔔 發現 {len(new_cases)} 筆新軟體標案！\n\n"

            for i, case in enumerate(new_cases, 1):
                detail_url = f"https://web.pcc.gov.tw/tps/QueryTender/query/searchTenderDetail?pkPmsMain={case['pk_pms_main']}"

                # 終端輸出
                logger.info(f"\n【第 {i} 筆】")
                logger.info(f"標案名稱：{case['brief']}")
                logger.info(f"招標機關：{case['unit']}")
                logger.info(f"預算金額：${case['budget']:,}")
                logger.info(f"詳細連結：{detail_url}")

                # LINE 訊息內容
                line_message += f"{i}. {case['brief'][:40]}...\n"
                line_message += f"   💰 ${case['budget']:,}\n"
                unit_name = case['unit'][:30] if case['unit'] else "N/A"
                line_message += f"   🏢 {unit_name}\n"
                line_message += f"   🔗 {detail_url}\n\n"

            # 發送 LINE 通知
            if LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID:
                send_line_message(line_message)
            else:
                logger.info("💡 提示：設定 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_USER_ID 環境變數即可啟用推播通知")
        else:
            logger.info("目前沒有符合條件的新標案")

        logger.info("="*60)
        logger.info("執行完成")
        logger.info("="*60)

    except requests.exceptions.RequestException as e:
        logger.error(f"網路錯誤: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"發生錯誤: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    fetch_tenders()
