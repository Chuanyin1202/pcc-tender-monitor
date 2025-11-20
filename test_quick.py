#!/usr/bin/env python3
"""快速測試版本 - 只檢查前 5 筆匹配的標案"""

import requests
from datetime import datetime, timedelta

API_BASE_URL = "https://pcc-api.openfun.app/api"
KEYWORDS_INCLUDE = ["軟體", "系統", "APP", "網站", "維護", "資訊", "開發", "建置"]
KEYWORDS_EXCLUDE = ["硬體", "電腦", "監控", "機房", "土木", "網路設備", "交換器"]

search_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
print(f"🔍 查詢 {search_date} 的標案...")

url = f"{API_BASE_URL}/listbydate"
response = requests.get(url, params={'date': search_date}, timeout=30)
records = response.json().get('records', [])

print(f"✅ 找到 {len(records)} 筆原始資料\n")

matches = []
for record in records:
    title = record.get('brief', {}).get('title', '')

    # 排除關鍵字
    if any(kw in title for kw in KEYWORDS_EXCLUDE):
        continue

    # 包含關鍵字
    if any(kw in title for kw in KEYWORDS_INCLUDE):
        matches.append({
            'title': title,
            'unit': record.get('unit_name', ''),
            'unit_id': record.get('unit_id', ''),
            'job_number': record.get('job_number', '')
        })

        if len(matches) >= 5:  # 只取前 5 筆
            break

print(f"📊 前 5 筆關鍵字匹配的標案：\n")
for i, match in enumerate(matches, 1):
    print(f"{i}. {match['title'][:60]}...")
    print(f"   機關：{match['unit']}")
    print(f"   ID: {match['unit_id']}/{match['job_number']}")
    print()
