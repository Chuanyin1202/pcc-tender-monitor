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
import argparse
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

# 搜尋關鍵字（使用 listbydate API,本地端過濾）
SEARCH_KEYWORDS = ["軟體", "APP", "網站", "應用程式", "系統", "資訊", "開發", "建置"]

# 執行模式配置
QUICK_MODE_DAYS = 2    # 快速模式：查詢最近 2 天
DEEP_MODE_DAYS = 14    # 深度模式：查詢最近 14 天

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
                    status TEXT,
                    publish_date TEXT,
                    last_checked TEXT,
                    last_status_change TEXT,
                    PRIMARY KEY (unit_id, job_number)
                )
            """)

            # 建立歷史歸檔表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenders_archive (
                    unit_id TEXT,
                    job_number TEXT,
                    brief TEXT,
                    unit_name TEXT,
                    budget INTEGER,
                    pk_pms_main TEXT,
                    deadline TEXT,
                    date_added TEXT,
                    notified INTEGER DEFAULT 0,
                    status TEXT,
                    publish_date TEXT,
                    last_checked TEXT,
                    last_status_change TEXT,
                    archived_at TEXT,
                    archive_reason TEXT,
                    PRIMARY KEY (unit_id, job_number)
                )
            """)

            # 升級現有資料庫：增加新欄位
            try:
                cursor.execute("ALTER TABLE tenders ADD COLUMN status TEXT")
                logger.info("資料庫升級：新增 status 欄位")
            except sqlite3.OperationalError:
                pass  # 欄位已存在

            try:
                cursor.execute("ALTER TABLE tenders ADD COLUMN publish_date TEXT")
                logger.info("資料庫升級：新增 publish_date 欄位")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE tenders ADD COLUMN last_checked TEXT")
                logger.info("資料庫升級：新增 last_checked 欄位")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE tenders ADD COLUMN last_status_change TEXT")
                logger.info("資料庫升級：新增 last_status_change 欄位")
            except sqlite3.OperationalError:
                pass

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

def format_line_notification(mode, new_tenders, status_changes=None, report_url=None):
    """
    格式化 LINE 通知訊息（優化版：摘要式、分級）

    Args:
        mode: 'quick' 或 'deep'
        new_tenders: 新標案列表
        status_changes: 狀態變更列表 (深度模式)
        report_url: 完整報告連結 (深度模式)

    Returns:
        str: 格式化的 LINE 訊息
    """
    # 按預算分級
    high_priority = [t for t in new_tenders if t['budget'] > 800000]  # > 80萬
    medium_priority = [t for t in new_tenders if 500000 <= t['budget'] <= 800000]  # 50-80萬
    low_priority = [t for t in new_tenders if t['budget'] < 500000]  # < 50萬

    # 組合訊息
    message = f"📊 標案監控報告 ({'快速' if mode == 'quick' else '深度'})\n"
    message += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

    # 統計摘要
    message += f"✨ 新標案：{len(new_tenders)} 筆\n"
    if status_changes:
        message += f"🔄 狀態變更：{len(status_changes)} 筆\n"

    # 重點標案 (預算 > 80萬)
    if high_priority:
        message += "\n━━━━━━━━━━━━━━━\n"
        message += "🔥 重點標案 (預算 > 80萬)\n\n"

        for i, case in enumerate(high_priority[:3], 1):  # 最多顯示 3 筆
            detail_url = f"https://web.pcc.gov.tw/tps/pss/tender.do?searchMode=common&searchType=advance&pkPmsMain={case['pk_pms_main']}"

            # 截取標題（最多 40 字）
            title = case['brief'][:40] + '...' if len(case['brief']) > 40 else case['brief']
            budget_m = case['budget'] / 10000  # 轉換成萬

            # 解析截止日期
            try:
                deadline_dt = datetime.strptime(case['deadline'], "%Y-%m-%d %H:%M:%S")
                deadline_str = deadline_dt.strftime('%m/%d')
            except:
                deadline_str = 'N/A'

            message += f"{i}️⃣ {title}\n"
            message += f"   💰 {budget_m:.0f} 萬 | ⏰ {deadline_str}\n"
            message += f"   🔗 {detail_url}\n\n"

        if len(high_priority) > 3:
            message += f"... 及其他 {len(high_priority) - 3} 筆重點標案\n"

    # 一般標案摘要
    if medium_priority or low_priority:
        message += "\n━━━━━━━━━━━━━━━\n"
        message += "📋 一般標案\n"
        if medium_priority:
            message += f"  • 50-80萬：{len(medium_priority)} 筆\n"
        if low_priority:
            message += f"  • <50萬：{len(low_priority)} 筆\n"

    # 狀態變更摘要 (深度模式)
    if status_changes and len(status_changes) > 0:
        message += "\n━━━━━━━━━━━━━━━\n"
        message += "🔄 狀態變更\n\n"

        for i, change in enumerate(status_changes[:3], 1):  # 最多顯示 3 筆
            title = change['brief'][:40] + '...' if len(change['brief']) > 40 else change['brief']
            message += f"{i}. {title}\n"
            message += f"   {change['old_status']} → {change['new_status']}\n\n"

        if len(status_changes) > 3:
            message += f"... 及其他 {len(status_changes) - 3} 筆狀態變更\n"

    # 完整報告連結 (深度模式)
    if report_url:
        message += "\n━━━━━━━━━━━━━━━\n"
        message += f"📋 完整報告：\n{report_url}"

    return message


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
            records = data['records']

            # 優先選擇「公開招標公告」類型（包含 pkPmsMain），如果有多筆取日期最新的
            tender_records = [r for r in records if r.get('detail', {}).get('type') == '公開招標公告']

            if tender_records:
                # 如果有多筆招標公告，取日期最新的
                selected_record = max(tender_records, key=lambda r: r.get('date', 0))
            else:
                # 如果沒有「公開招標公告」，取所有 records 中日期最新的
                selected_record = max(records, key=lambda r: r.get('date', 0))

            detail = selected_record.get('detail', {})
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



def fetch_tenders_by_date_range(days_to_search):
    """
    查詢指定日期範圍的標案並過濾

    Args:
        days_to_search: 從今天往前推幾天

    Returns:
        list: 符合條件的候選標案
    """
    today = datetime.now()
    all_candidates = []

    logger.info(f"查詢最近 {days_to_search} 天的標案")

    for days_ago in range(days_to_search):
        target_date = today - timedelta(days=days_ago)
        date_str = target_date.strftime("%Y%m%d")

        logger.info(f"\n查詢日期: {target_date.strftime('%Y-%m-%d')}")

        url = f"{API_BASE_URL}/listbydate"
        params = {'date': date_str}

        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=API_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            records = data.get('records', [])

            logger.info(f"  取得 {len(records):,} 筆")

            # 本地關鍵字過濾
            matched = 0
            for record in records:
                brief_data = record.get('brief', {})
                title = brief_data.get('title', '')
                tender_type = brief_data.get('type', '')

                # 檢查包含關鍵字
                if any(kw in title for kw in SEARCH_KEYWORDS):
                    # 檢查排除關鍵字
                    if not any(ex_kw in title for ex_kw in KEYWORDS_EXCLUDE):
                        # 標準化資料結構：brief 改為字串
                        record['brief'] = title
                        record['publish_date'] = target_date.strftime('%Y-%m-%d')
                        record['status'] = tender_type
                        all_candidates.append(record)
                        matched += 1

            if matched > 0:
                logger.info(f"  符合關鍵字: {matched} 筆")

            time.sleep(API_DELAY)

        except Exception as e:
            logger.error(f"  查詢失敗: {e}")
            continue

    logger.info(f"\n總計候選標案: {len(all_candidates)} 筆")
    return all_candidates


def fetch_tenders(mode='quick'):
    """抓取並過濾政府採購標案"""
    logger.info("="*60)
    logger.info(f"開始抓取資料... (模式: {mode})")
    logger.info("="*60)

    try:
        # 初始化資料庫
        init_db()

        # 清理 3 個月前的舊資料
        cleanup_old_tenders()

        # 根據模式決定查詢天數
        if mode == 'quick':
            days_to_search = QUICK_MODE_DAYS
        elif mode == 'deep':
            days_to_search = DEEP_MODE_DAYS
        else:
            days_to_search = QUICK_MODE_DAYS

        # 查詢日期範圍內的標案
        candidates = fetch_tenders_by_date_range(days_to_search)

        logger.info("\n開始查詢詳細資料...")
        new_cases = []

        for record in candidates:
            brief_data = record.get('brief', {})
            title = brief_data.get('title', '')
            unit_id = record.get('unit_id', '')
            job_number = record.get('job_number', '')
            unit_name = record.get('unit_name', 'N/A')

            # 檢查是否為新案
            if not is_new_tender(unit_id, job_number):
                logger.debug(f"  跳過已存在標案: {title[:40]}...")
                continue

            logger.info(f"  ✓ 發現候選標案: {title[:60]}...")

            # 查詢詳細資料取得預算和截止日期
            result = get_tender_detail(unit_id, job_number)

            if result is None:
                logger.warning(f"    無法取得完整資訊,跳過")
                continue

            budget, pk_pms_main, deadline = result

            # 預算過濾
            if not (MIN_BUDGET <= budget <= MAX_BUDGET):
                logger.debug(f"    預算不符 (${budget:,})")
                continue

            # 截止日期檢查
            try:
                deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
                if deadline_dt < datetime.now():
                    logger.debug(f"    已截止")
                    continue
            except:
                logger.debug(f"    截止日期格式錯誤")
                continue

            logger.info(f"    ✓ 符合條件! 預算: ${budget:,}, 截止: {deadline}")

            # 儲存到資料庫
            case_info = {
                'brief': title,
                'unit': unit_name,
                'budget': budget,
                'deadline': deadline,
                'pk_pms_main': pk_pms_main,
                'unit_id': unit_id,
                'job_number': job_number,
                'publish_date': record.get('publish_date', ''),
                'status': record.get('status', '')
            }

            if save_tender(unit_id, job_number, title, unit_name, budget, pk_pms_main, deadline):
                new_cases.append(case_info)

        # 深度模式：檢查狀態變更 + 生成日報
        status_changes = []
        if mode == 'deep':
            logger.info("\n" + "="*60)
            logger.info("深度模式：檢查活躍標案狀態變更")
            logger.info("="*60)

            status_changes = check_status_changes(API_BASE_URL, HEADERS, API_DELAY)

            if status_changes:
                logger.info(f"\n發現 {len(status_changes)} 筆狀態變更")
                for change in status_changes[:5]:
                    logger.info(f"  {change['brief'][:40]}...")
                    logger.info(f"    {change['old_status']} → {change['new_status']}")
            else:
                logger.info("\n無狀態變更")

            # 生成日報
            logger.info("\n" + "="*60)
            logger.info("生成 Markdown 日報")
            logger.info("="*60)

            report_content = generate_daily_report(
                new_cases,
                status_changes,
                datetime.now().strftime('%Y-%m-%d')
            )

            # 儲存日報
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)

            report_file = reports_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)

            logger.info(f"已生成日報: {report_file}")

            # Git 自動提交（可選）
            if os.getenv("GIT_AUTO_COMMIT", "false").lower() == "true":
                logger.info("\n執行 Git 自動提交...")
                try:
                    import subprocess
                    subprocess.run(["git", "add", "reports/"], check=True)
                    subprocess.run([
                        "git", "commit", "-m",
                        f"新增日報 {datetime.now().strftime('%Y-%m-%d')}"
                    ], check=True)
                    subprocess.run(["git", "push"], check=True)
                    logger.info("Git 提交成功")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Git 提交失敗: {e}")

        # 發送通知
        if new_cases or (mode == 'deep' and status_changes):
            logger.info(f"\n發現 {len(new_cases)} 筆符合條件的新標案")

            # 生成報告 URL (深度模式)
            report_url = None
            if mode == 'deep':
                # 假設報告會推送到 GitHub
                # 格式: https://github.com/用戶名/倉庫名/blob/main/reports/YYYY-MM-DD.md
                # 這裡需要根據實際 GitHub 倉庫設定
                report_date = datetime.now().strftime('%Y-%m-%d')
                # report_url = f"https://github.com/YOUR_USERNAME/pcc-tender-monitor/blob/main/reports/{report_date}.md"

            # 使用優化的格式化函數
            line_message = format_line_notification(
                mode=mode,
                new_tenders=new_cases,
                status_changes=status_changes if mode == 'deep' else None,
                report_url=report_url
            )

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


# ============================================================
# 新架構：歸檔與統計相關函數
# ============================================================

def count_active_tenders():
    """統計資料庫中活躍標案數量"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tenders")
            result = cursor.fetchone()
            return result[0] if result else 0
    except Exception as e:
        logger.error(f"統計活躍標案失敗: {e}")
        return 0


def archive_ended_tenders():
    """
    將已結束的標案移至歸檔表

    結束條件：
    - 狀態包含：決標、廢標、無法決標、取消
    - 或截止日期已過

    Returns:
        list: 已歸檔的標案列表（用於日報）
    """
    archived_tenders = []

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # 查詢需要歸檔的標案
            cursor.execute("""
                SELECT unit_id, job_number, brief, budget, deadline, status
                FROM tenders
                WHERE (
                    status LIKE '%決標%' OR
                    status LIKE '%廢標%' OR
                    status LIKE '%無法決標%' OR
                    status LIKE '%取消%' OR
                    deadline < datetime('now')
                )
            """)

            to_archive = cursor.fetchall()

            if not to_archive:
                logger.info("無需歸檔的標案")
                return []

            logger.info(f"找到 {len(to_archive)} 筆需要歸檔的標案")

            # 移動到歸檔表
            for tender in to_archive:
                unit_id, job_number, brief, budget, deadline, status = tender

                # 判斷歸檔原因
                if status and '決標' in status:
                    reason = '決標'
                elif status and '廢標' in status:
                    reason = '廢標'
                elif status and '無法決標' in status:
                    reason = '無法決標'
                elif status and '取消' in status:
                    reason = '取消'
                else:
                    reason = '過期'

                # 複製到歸檔表
                cursor.execute("""
                    INSERT OR REPLACE INTO tenders_archive
                    SELECT *, datetime('now'), ?
                    FROM tenders
                    WHERE unit_id = ? AND job_number = ?
                """, (reason, unit_id, job_number))

                # 從主表刪除
                cursor.execute("""
                    DELETE FROM tenders
                    WHERE unit_id = ? AND job_number = ?
                """, (unit_id, job_number))

                archived_tenders.append({
                    'brief': brief,
                    'budget': budget,
                    'deadline': deadline,
                    'reason': reason
                })

                logger.info(f"  歸檔: {brief[:40]}... ({reason})")

            conn.commit()
            logger.info(f"成功歸檔 {len(archived_tenders)} 筆標案")

    except Exception as e:
        logger.error(f"歸檔標案失敗: {e}")

    return archived_tenders


# ============================================================
# 新架構：三種執行模式
# ============================================================

def init_mode():
    """
    初始化模式（增量補充）

    - 檢查資料庫現狀
    - 掃描 14 天資料
    - 只新增資料庫中不存在的標案
    - 發送完成通知
    """
    logger.info("="*60)
    logger.info("執行模式：初始化（增量補充）")
    logger.info("="*60)

    # 檢查資料庫現狀
    existing_count = count_active_tenders()
    if existing_count > 0:
        logger.info(f"資料庫已有 {existing_count} 筆活躍標案")
        logger.info("執行增量補充模式...")
    else:
        logger.info("資料庫為空，執行完整初始化...")

    # 呼叫現有函數掃描 14 天資料
    logger.info("\n開始掃描最近 14 天標案...")
    all_tenders = fetch_tenders_by_date_range(days_to_search=14)

    if not all_tenders:
        logger.info("未找到符合條件的標案")
        return

    logger.info(f"掃描完成，找到 {len(all_tenders)} 筆符合條件的標案")

    # 過濾出資料庫中不存在的標案
    new_tenders = []
    for tender in all_tenders:
        if is_new_tender(tender['unit_id'], tender['job_number']):
            new_tenders.append(tender)

    if not new_tenders:
        logger.info("所有標案皆已存在資料庫，無需新增")
    else:
        logger.info(f"\n發現 {len(new_tenders)} 筆新標案，開始查詢詳細資料...")

        # 查詢詳細資料並儲存
        saved_count = 0
        for idx, tender in enumerate(new_tenders, 1):
            logger.info(f"  [{idx}/{len(new_tenders)}] 查詢: {tender['brief'][:50]}...")

            # 查詢詳細資料取得預算和截止日期
            result = get_tender_detail(tender['unit_id'], tender['job_number'])

            if result is None:
                logger.warning(f"    無法取得完整資訊，跳過")
                continue

            budget, pk_pms_main, deadline = result

            # 預算過濾
            if not (MIN_BUDGET <= budget <= MAX_BUDGET):
                logger.debug(f"    預算不符 (${budget:,})")
                continue

            # 截止日期檢查
            try:
                deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
                if deadline_dt < datetime.now():
                    logger.debug(f"    已截止")
                    continue
            except:
                logger.debug(f"    截止日期格式錯誤")
                continue

            logger.info(f"    ✓ 符合條件! 預算: ${budget:,}, 截止: {deadline}")

            if save_tender(
                unit_id=tender['unit_id'],
                job_number=tender['job_number'],
                brief=tender['brief'],
                unit_name=tender.get('unit_name', ''),
                budget=budget,
                pk_pms_main=pk_pms_main,
                deadline=deadline
            ):
                saved_count += 1

        logger.info(f"\n成功儲存 {saved_count} 筆新標案")

    # 統計最終結果
    final_count = count_active_tenders()

    logger.info("\n" + "="*60)
    logger.info("初始化完成")
    logger.info(f"資料庫目前有 {final_count} 筆活躍標案")
    logger.info(f"本次新增：{len(new_tenders)} 筆")
    logger.info("="*60)

    # 發送 LINE 通知
    if LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID and new_tenders:
        message = f"""📊 標案監控系統初始化完成

✨ 新增標案：{len(new_tenders)} 筆
📌 目前追蹤：{final_count} 筆活躍標案

系統已就緒，開始監控！
"""
        send_line_message(message)


def monitor_mode():
    """
    日常監控模式（每 2 小時執行）

    - 查詢最近 1 天新標案
    - 檢查所有活躍標案狀態
    - 歸檔已結束標案
    - 發送 LINE 通知（僅新案）
    """
    logger.info("="*60)
    logger.info("執行模式：日常監控")
    logger.info("="*60)

    # 1. 歸檔已結束的標案
    logger.info("\n檢查需要歸檔的標案...")
    archived = archive_ended_tenders()

    # 2. 查詢最近 1 天新標案
    logger.info("\n查詢最近 1 天新標案...")
    all_candidates = fetch_tenders_by_date_range(days_to_search=1)

    if not all_candidates:
        logger.info("未找到符合條件的標案")
        new_tenders = []
    else:
        # 過濾出真正的新標案
        candidates = []
        for tender in all_candidates:
            if is_new_tender(tender['unit_id'], tender['job_number']):
                candidates.append(tender)

        if not candidates:
            logger.info("無新標案")
            new_tenders = []
        else:
            logger.info(f"發現 {len(candidates)} 筆候選新標案，開始查詢詳細資料...")

            # 查詢詳細資料並儲存
            new_tenders = []
            for idx, tender in enumerate(candidates, 1):
                logger.info(f"  [{idx}/{len(candidates)}] 查詢: {tender['brief'][:50]}...")

                # 查詢詳細資料取得預算和截止日期
                result = get_tender_detail(tender['unit_id'], tender['job_number'])

                if result is None:
                    logger.warning(f"    無法取得完整資訊，跳過")
                    continue

                budget, pk_pms_main, deadline = result

                # 預算過濾
                if not (MIN_BUDGET <= budget <= MAX_BUDGET):
                    logger.debug(f"    預算不符 (${budget:,})")
                    continue

                # 截止日期檢查
                try:
                    deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
                    if deadline_dt < datetime.now():
                        logger.debug(f"    已截止")
                        continue
                except:
                    logger.debug(f"    截止日期格式錯誤")
                    continue

                logger.info(f"    ✓ 符合條件! 預算: ${budget:,}, 截止: {deadline}")

                # 儲存新標案
                if save_tender(
                    unit_id=tender['unit_id'],
                    job_number=tender['job_number'],
                    brief=tender['brief'],
                    unit_name=tender.get('unit_name', ''),
                    budget=budget,
                    pk_pms_main=pk_pms_main,
                    deadline=deadline
                ):
                    new_tenders.append({
                        'brief': tender['brief'],
                        'unit': tender.get('unit_name', ''),
                        'budget': budget,
                        'deadline': deadline,
                        'pk_pms_main': pk_pms_main
                    })

            logger.info(f"成功儲存 {len(new_tenders)} 筆新標案")

    # 3. 統計結果
    active_count = count_active_tenders()

    logger.info("\n" + "="*60)
    logger.info("監控完成")
    logger.info(f"新增標案：{len(new_tenders)} 筆")
    logger.info(f"歸檔標案：{len(archived)} 筆")
    logger.info(f"目前追蹤：{active_count} 筆活躍標案")
    logger.info("="*60)

    # 4. 發送 LINE 通知（僅新標案）
    if LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID and new_tenders:
        # 使用現有的格式化函數
        message = format_line_notification(
            mode='monitor',
            new_tenders=new_tenders
        )
        send_line_message(message)
    elif new_tenders:
        logger.info("💡 提示：設定 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_USER_ID 環境變數即可啟用推播通知")


def report_mode():
    """
    日報生成模式（每天 20:00 執行）

    - 從資料庫讀取當天新增/歸檔標案
    - 生成 Markdown 日報
    - Git 提交到 reports/
    """
    logger.info("="*60)
    logger.info("執行模式：日報生成")
    logger.info("="*60)

    from datetime import datetime
    from pathlib import Path

    today = datetime.now().strftime('%Y-%m-%d')

    # 1. 查詢當天新增的標案（date_added = today）
    logger.info("\n查詢今日新增標案...")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT brief, budget, deadline, unit_name
                FROM tenders
                WHERE date(date_added) = date('now')
                ORDER BY budget DESC
            """)
            new_today = [
                {'brief': row[0], 'budget': row[1], 'deadline': row[2], 'unit': row[3]}
                for row in cursor.fetchall()
            ]
    except Exception as e:
        logger.error(f"查詢今日新增標案失敗: {e}")
        new_today = []

    # 2. 查詢當天歸檔的標案（archived_at = today）
    logger.info("查詢今日歸檔標案...")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT brief, budget, archive_reason
                FROM tenders_archive
                WHERE date(archived_at) = date('now')
                ORDER BY budget DESC
            """)
            archived_today = [
                {'brief': row[0], 'budget': row[1], 'reason': row[2]}
                for row in cursor.fetchall()
            ]
    except Exception as e:
        logger.error(f"查詢今日歸檔標案失敗: {e}")
        archived_today = []

    # 3. 統計目前活躍標案
    active_count = count_active_tenders()

    # 4. 生成 Markdown 日報
    logger.info("\n生成日報...")
    report = f"""# 政府標案監控日報

**日期**: {today}
**生成時間**: {datetime.now().strftime('%H:%M:%S')}

---

## 📊 統計摘要

- ✨ 今日新增：**{len(new_today)}** 筆
- 🔄 今日移除：**{len(archived_today)}** 筆
- 📌 目前追蹤：**{active_count}** 筆活躍標案

---

"""

    # 新增標案
    if new_today:
        report += "## ✨ 今日新增標案\n\n"
        report += "| 標案名稱 | 預算 | 截止日期 | 機關 |\n"
        report += "|---------|------|----------|------|\n"

        for tender in new_today:
            brief = tender['brief'][:50] + '...' if len(tender['brief']) > 50 else tender['brief']
            budget = f"${tender['budget']:,}"
            deadline = tender['deadline'][:10] if tender.get('deadline') else 'N/A'
            unit = tender['unit'][:20] if tender.get('unit') else 'N/A'
            report += f"| {brief} | {budget} | {deadline} | {unit} |\n"

        report += "\n"
    else:
        report += "## ✨ 今日新增標案\n\n無新增標案。\n\n"

    # 移除標案
    if archived_today:
        report += "## 🔄 今日移除標案\n\n"
        report += "| 標案名稱 | 預算 | 移除原因 |\n"
        report += "|---------|------|----------|\n"

        for tender in archived_today:
            brief = tender['brief'][:50] + '...' if len(tender['brief']) > 50 else tender['brief']
            budget = f"${tender['budget']:,}"
            reason = tender['reason']
            report += f"| {brief} | {budget} | {reason} |\n"

        report += "\n"
    else:
        report += "## 🔄 今日移除標案\n\n無移除標案。\n\n"

    report += "---\n\n"
    report += "*此報告由政府標案監控系統自動生成*\n"

    # 5. 儲存日報
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    report_file = reports_dir / f"{today}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info(f"日報已儲存: {report_file}")

    # 6. Git 自動提交（可選）
    if os.getenv("GIT_AUTO_COMMIT", "false").lower() == "true":
        logger.info("\n執行 Git 自動提交...")
        try:
            import subprocess
            subprocess.run(["git", "add", "reports/"], check=True)
            subprocess.run([
                "git", "commit", "-m",
                f"更新日報 {today}\n\n新增 {len(new_today)} 筆，移除 {len(archived_today)} 筆"
            ], check=True)
            logger.info("Git 提交成功")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Git 提交失敗: {e}")

    logger.info("\n" + "="*60)
    logger.info("日報生成完成")
    logger.info("="*60)


def main():
    """主程式入口"""
    parser = argparse.ArgumentParser(description='政府採購網軟體標案監控')
    parser.add_argument(
        '--mode',
        choices=['init', 'monitor', 'report'],
        default='monitor',
        help='執行模式: init(初始化), monitor(日常監控), report(日報生成)'
    )

    args = parser.parse_args()

    # 初始化資料庫
    init_db()

    # 根據模式執行對應功能
    if args.mode == 'init':
        init_mode()
    elif args.mode == 'monitor':
        monitor_mode()
    elif args.mode == 'report':
        report_mode()
    else:
        logger.error(f"未知模式: {args.mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
