#!/usr/bin/env python3
"""測試找出預算在 15-150 萬的軟體標案"""

import requests
import time
from datetime import datetime, timedelta

API_BASE_URL = "https://pcc-api.openfun.app/api"
MIN_BUDGET = 150000
MAX_BUDGET = 1500000
KEYWORDS_INCLUDE = ["軟體", "系統", "APP", "網站", "維護", "資訊", "開發", "建置"]
KEYWORDS_EXCLUDE = ["硬體", "電腦", "監控", "機房", "土木", "網路設備", "交換器"]

def parse_budget(budget_str):
    if not budget_str:
        return None
    budget_str = budget_str.replace(',', '').replace('元', '').strip()
    try:
        return int(budget_str)
    except ValueError:
        return None

def get_tender_detail(unit_id, job_number):
    time.sleep(0.3)
    try:
        url = f"{API_BASE_URL}/tender"
        response = requests.get(url, params={'unit_id': unit_id, 'job_number': job_number}, timeout=15)
        response.raise_for_status()
        data = response.json()
        if 'records' in data and len(data['records']) > 0:
            detail = data['records'][0].get('detail', {})
            return parse_budget(detail.get('採購資料:預算金額', ''))
        return None
    except:
        return None

# 查詢昨天
search_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
print(f"🔍 查詢 {search_date} 的標案，找出預算 15-150 萬的案例...\n")

url = f"{API_BASE_URL}/listbydate"
response = requests.get(url, params={'date': search_date}, timeout=30)
records = response.json().get('records', [])

found_count = 0
for record in records:
    if found_count >= 3:  # 只找 3 個案例
        break

    title = record.get('brief', {}).get('title', '')

    if any(kw in title for kw in KEYWORDS_EXCLUDE):
        continue
    if not any(kw in title for kw in KEYWORDS_INCLUDE):
        continue

    unit_id = record.get('unit_id', '')
    job_number = record.get('job_number', '')
    unit_name = record.get('unit_name', '')

    print(f"檢查: {title[:50]}...")
    budget = get_tender_detail(unit_id, job_number)

    if budget and MIN_BUDGET <= budget <= MAX_BUDGET:
        found_count += 1
        print(f"  ✅ 符合！")
        print(f"  機關：{unit_name}")
        print(f"  預算：${budget:,} 元")
        print(f"  ID: {unit_id}/{job_number}\n")
    elif budget:
        print(f"  ✗ 預算不符：${budget:,} 元\n")
    else:
        print(f"  ✗ 無預算資訊\n")

print(f"\n總共找到 {found_count} 筆符合條件的標案")
