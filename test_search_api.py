#!/usr/bin/env python3
"""測試 searchbytitle API"""

import requests
import json

# 測試搜尋 API
url = "https://morning-pine-2053.alexabc.workers.dev/api/searchbytitle"
params = {"query": "軟體", "page": 1}

print("測試 API:", url)
print("參數:", params)
print("-" * 60)

try:
    response = requests.get(url, params=params, timeout=15)
    print(f"狀態碼: {response.status_code}")
    print(f"回應長度: {len(response.text)} bytes")
    print("-" * 60)

    if response.status_code == 200:
        data = response.json()

        # 分析回應結構
        print("回應結構:")
        print(f"  - 總鍵數: {len(data.keys())}")
        print(f"  - 鍵名稱: {list(data.keys())}")

        if 'records' in data:
            records = data['records']
            print(f"\n找到 {len(records)} 筆記錄")

            if len(records) > 0:
                print("\n第一筆資料範例:")
                print(json.dumps(records[0], indent=2, ensure_ascii=False))

                # 分析資料結構
                print("\n資料欄位:")
                for key in records[0].keys():
                    print(f"  - {key}")

        # 檢查是否有分頁資訊
        if 'total' in data:
            print(f"\n分頁資訊:")
            print(f"  - 總筆數: {data.get('total', 'N/A')}")
            print(f"  - 當前頁: {data.get('page', 'N/A')}")
            print(f"  - 每頁筆數: {data.get('per_page', 'N/A')}")
    else:
        print(f"錯誤: HTTP {response.status_code}")
        print(response.text[:500])

except Exception as e:
    print(f"錯誤: {e}")
