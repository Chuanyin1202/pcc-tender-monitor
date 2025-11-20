#!/usr/bin/env python3
"""
標案查詢工具
- 查詢資料庫內的標案
- 支援多種篩選條件
- 可匯出 CSV
- 智能推薦分析
"""

import sqlite3
import argparse
import csv
import requests
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ===== 日誌系統設定 =====

# 建立 logs 目錄
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 設定 logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 控制台處理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 格式化
formatter = logging.Formatter(
    '%(levelname)s - %(message)s'
)
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

# ===== 配置 =====

DB_PATH = "tenders.db"
API_BASE_URL = "https://pcc-api.openfun.app/api"
API_TIMEOUT = 15


def get_tender_full_detail(unit_id, job_number):
    """取得標案完整詳細資訊"""
    try:
        time.sleep(0.3)  # 避免 rate limiting

        url = f"{API_BASE_URL}/tender"
        params = {'unit_id': unit_id, 'job_number': job_number}

        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        if 'records' in data and len(data['records']) > 0:
            return data['records'][0].get('detail', {})

        return None
    except requests.exceptions.Timeout:
        logger.warning(f"查詢標案詳細資料超時: {unit_id}/{job_number}")
        return None
    except Exception as e:
        logger.warning(f"查詢標案詳細資料失敗: {e}")
        return None


def analyze_tender(brief, budget, unit_name, detail=None):
    """
    分析標案並評分
    回傳：{
        'difficulty': int (1-10),
        'competition': int (1-10),
        'beginner_friendly': str ('🟢', '🟡', '🔴'),
        'win_chance': str,
        'recommendation': str,
        'reasons': list,
        'warnings': list,
        'score': float
    }
    """
    analysis = {
        'difficulty': 5,
        'competition': 5,
        'beginner_friendly': '🟡',
        'win_chance': '中等',
        'recommendation': '可考慮',
        'reasons': [],
        'warnings': [],
        'score': 5.0
    }

    # 預算分析
    if budget < 300000:
        analysis['difficulty'] = 3
        analysis['reasons'].append('預算小，風險低')
    elif budget < 600000:
        analysis['difficulty'] = 5
        analysis['reasons'].append('預算適中')
    elif budget < 1000000:
        analysis['difficulty'] = 7
        analysis['warnings'].append('預算較高，需謹慎評估')
    else:
        analysis['difficulty'] = 9
        analysis['warnings'].append('大型專案，建議有經驗再接')

    # 標案類型分析
    if '維護' in brief or '維運' in brief:
        analysis['difficulty'] -= 1
        analysis['reasons'].append('維護類案件，需求明確')
    elif '建置' in brief or '開發' in brief:
        analysis['difficulty'] += 1
        analysis['warnings'].append('建置類案件，需求可能複雜')

    if 'APP' in brief or '網站' in brief:
        analysis['reasons'].append('常見軟體類型')

    # 機關分析
    if unit_name and ('學校' in unit_name or '大學' in unit_name):
        analysis['competition'] -= 1
        analysis['reasons'].append('學校單位，通常較容易溝通')
    elif unit_name and ('警察' in unit_name or '軍' in unit_name or '國防' in unit_name):
        analysis['difficulty'] += 1
        analysis['warnings'].append('安全要求較高')

    # 詳細資訊分析（如果有）
    if detail:
        # 決標方式
        decision_method = detail.get('招標資料:決標方式', '')
        if '最有利標' in decision_method:
            analysis['competition'] -= 2
            analysis['reasons'].append('最有利標，重品質不只看價格')
        elif '最低標' in decision_method:
            analysis['competition'] += 2
            analysis['warnings'].append('最低標，價格競爭激烈')

        # 招標方式
        tender_method = detail.get('招標資料:招標方式', '')
        if '報價單' in tender_method or '企劃書' in tender_method:
            analysis['difficulty'] -= 1
            analysis['reasons'].append('簡化招標，文件較簡單')

        # 特殊要求
        if detail.get('採購資料:本採購是否屬「涉及國家安全」採購', '') == '是':
            analysis['difficulty'] += 2
            analysis['warnings'].append('涉及國安，不允許陸資')

    # 計算總分
    analysis['difficulty'] = max(1, min(10, analysis['difficulty']))
    analysis['competition'] = max(1, min(10, analysis['competition']))

    # 新手友好度
    if analysis['difficulty'] <= 4 and analysis['competition'] <= 5:
        analysis['beginner_friendly'] = '🟢'
        analysis['recommendation'] = '強烈推薦'
    elif analysis['difficulty'] <= 6 and analysis['competition'] <= 7:
        analysis['beginner_friendly'] = '🟡'
        analysis['recommendation'] = '可以嘗試'
    else:
        analysis['beginner_friendly'] = '🔴'
        analysis['recommendation'] = '建議累積經驗後再接'

    # 得標機會
    win_score = 10 - analysis['competition']
    if win_score >= 7:
        analysis['win_chance'] = '高'
    elif win_score >= 4:
        analysis['win_chance'] = '中等'
    else:
        analysis['win_chance'] = '低'

    # 綜合評分 (1-10)
    analysis['score'] = round((11 - analysis['difficulty']) * 0.4 + win_score * 0.6, 1)

    return analysis


def query_tenders(days=30, keyword=None, unit=None, min_budget=None, max_budget=None, include_expired=False):
    """查詢標案"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # 基本 SQL 查詢
            sql = "SELECT unit_id, job_number, brief, unit_name, budget, pk_pms_main, deadline, date_added FROM tenders WHERE 1=1"
            params = []

            # 日期篩選
            if days:
                date_limit = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                sql += " AND date_added >= ?"
                params.append(date_limit)

            # 關鍵字篩選
            if keyword:
                sql += " AND brief LIKE ?"
                params.append(f"%{keyword}%")

            # 機關篩選
            if unit:
                sql += " AND unit_name LIKE ?"
                params.append(f"%{unit}%")

            # 預算範圍篩選
            if min_budget:
                sql += " AND budget >= ?"
                params.append(min_budget)

            if max_budget:
                sql += " AND budget <= ?"
                params.append(max_budget)

            # 截止日期篩選（預設只顯示未截止的）
            if not include_expired:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sql += " AND deadline > ?"
                params.append(now)

            # 排序：最新的在前
            sql += " ORDER BY date_added DESC"

            cursor.execute(sql, params)
            results = cursor.fetchall()

            return results
    except sqlite3.Error as e:
        logger.error(f"資料庫查詢錯誤: {e}")
        return []


def print_results(results):
    """輸出查詢結果"""
    if not results:
        logger.info("\n❌ 沒有找到符合條件的標案")
        return

    logger.info(f"\n✅ 找到 {len(results)} 筆標案")
    logger.info("=" * 80)

    total_budget = 0
    now = datetime.now()

    for i, (unit_id, job_number, brief, unit_name, budget, pk_pms_main, deadline, date_added) in enumerate(results, 1):
        total_budget += budget

        # 格式化日期
        date_str = date_added.split()[0] if ' ' in date_added else date_added

        # 計算距離截止日期的天數
        deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
        days_left = (deadline_dt - now).days
        if days_left < 0:
            deadline_status = f"⚠️ 已截止 {abs(days_left)} 天"
        elif days_left == 0:
            deadline_status = "🔥 今天截止！"
        elif days_left <= 3:
            deadline_status = f"🔥 剩 {days_left} 天！"
        elif days_left <= 7:
            deadline_status = f"⏰ 剩 {days_left} 天"
        else:
            deadline_status = f"✅ 剩 {days_left} 天"

        logger.info(f"\n【第 {i} 筆】")
        logger.info(f"標案名稱：{brief}")
        logger.info(f"招標機關：{unit_name}")
        logger.info(f"預算金額：${budget:,} 元")
        logger.info(f"截止時間：{deadline} ({deadline_status})")
        logger.info(f"發現日期：{date_str}")
        logger.info(f"詳細連結：https://web.pcc.gov.tw/tps/QueryTender/query/searchTenderDetail?pkPmsMain={pk_pms_main}")
        logger.info(f"標案代碼：{unit_id}/{job_number}")

    # 統計資訊
    logger.info("\n" + "=" * 80)
    logger.info(f"📊 統計資訊")
    logger.info(f"   總筆數：{len(results)} 筆")
    logger.info(f"   預算總額：${total_budget:,} 元")
    logger.info(f"   平均預算：${total_budget // len(results):,} 元")
    logger.info("=" * 80)


def export_csv(results, filename):
    """匯出 CSV"""
    if not results:
        logger.warning("❌ 沒有資料可匯出")
        return

    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)

            # 寫入標題列
            writer.writerow(['標案名稱', '招標機關', '預算金額', '截止時間', '發現日期', '標案代碼', '詳細連結'])

            # 寫入資料
            for unit_id, job_number, brief, unit_name, budget, pk_pms_main, deadline, date_added in results:
                date_str = date_added.split()[0] if ' ' in date_added else date_added
                detail_url = f"https://web.pcc.gov.tw/tps/QueryTender/query/searchTenderDetail?pkPmsMain={pk_pms_main}"

                writer.writerow([
                    brief,
                    unit_name,
                    budget,
                    deadline,
                    date_str,
                    f"{unit_id}/{job_number}",
                    detail_url
                ])

        logger.info(f"✅ 已匯出至 {filename}")
    except IOError as e:
        logger.error(f"匯出 CSV 失敗: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='查詢標案資料庫',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例：
  python query_tenders.py                           # 列出最近 30 天的標案
  python query_tenders.py --days 7                  # 列出最近 7 天
  python query_tenders.py --keyword "系統"          # 搜尋標題含"系統"
  python query_tenders.py --unit "臺北市"           # 搜尋臺北市的標案
  python query_tenders.py --min-budget 500000       # 預算 >= 50 萬
  python query_tenders.py --max-budget 1000000      # 預算 <= 100 萬
  python query_tenders.py --export result.csv       # 匯出 CSV
  python query_tenders.py --days 14 --keyword "APP" --export app_tenders.csv
        """
    )

    parser.add_argument('--days', type=int, default=30,
                        help='查詢最近幾天的標案（預設 30 天）')
    parser.add_argument('--keyword', type=str,
                        help='標案標題關鍵字')
    parser.add_argument('--unit', type=str,
                        help='招標機關關鍵字')
    parser.add_argument('--min-budget', type=int,
                        help='最低預算（元）')
    parser.add_argument('--max-budget', type=int,
                        help='最高預算（元）')
    parser.add_argument('--export', type=str,
                        help='匯出 CSV 檔案名稱')
    parser.add_argument('--include-expired', action='store_true',
                        help='包含已截止的標案（預設只顯示未截止的）')

    args = parser.parse_args()

    # 執行查詢
    results = query_tenders(
        days=args.days,
        keyword=args.keyword,
        unit=args.unit,
        min_budget=args.min_budget,
        max_budget=args.max_budget,
        include_expired=args.include_expired
    )

    # 輸出結果
    print_results(results)

    # 匯出 CSV
    if args.export and results:
        export_csv(results, args.export)


if __name__ == "__main__":
    main()
