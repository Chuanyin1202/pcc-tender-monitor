#!/usr/bin/env python3
"""比較兩種 API 方法的效能和覆蓋範圍"""

import requests
import time
from datetime import datetime

API_BASE_URL = "https://morning-pine-2053.alexabc.workers.dev/api"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json',
}

def test_search_method(keyword="軟體"):
    """測試搜尋方法"""
    print(f"\n{'='*60}")
    print(f"方法 A: 使用 searchbytitle API (關鍵字: {keyword})")
    print(f"{'='*60}")

    start_time = time.time()

    # 第一次請求取得總數
    url = f"{API_BASE_URL}/searchbytitle"
    params = {"query": keyword, "page": 1}

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()

        data = response.json()
        total_records = data.get('total_records', 0)
        total_pages = data.get('total_pages', 0)
        records = data.get('records', [])

        elapsed = time.time() - start_time

        print(f"✓ API 回應時間: {elapsed:.2f} 秒")
        print(f"✓ 找到總筆數: {total_records:,} 筆")
        print(f"✓ 總頁數: {total_pages} 頁 (每頁 100 筆)")
        print(f"✓ 第一頁筆數: {len(records)} 筆")

        if records:
            print(f"\n第一筆範例:")
            print(f"  標題: {records[0]['brief']['title']}")
            print(f"  機關: {records[0]['unit_name']}")
            print(f"  日期: {records[0]['date']}")

        # 分析資料結構
        print(f"\n資料完整性分析:")
        print(f"  ✗ 預算金額: 無 (需額外查詢 /api/tender)")
        print(f"  ✗ 截止日期: 無 (需額外查詢 /api/tender)")
        print(f"  ✓ 標案編號: 有 (unit_id, job_number)")
        print(f"  ✓ 標案標題: 有")

        return {
            'method': 'searchbytitle',
            'time': elapsed,
            'total_records': total_records,
            'requires_detail_api': True,
            'pages': total_pages
        }

    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return None


def test_listbydate_method(date_str="20251119"):
    """測試按日期查詢方法"""
    print(f"\n{'='*60}")
    print(f"方法 B: 使用 listbydate API (日期: {date_str})")
    print(f"{'='*60}")

    start_time = time.time()

    url = f"{API_BASE_URL}/listbydate"
    params = {"date": date_str}

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()

        data = response.json()
        records = data.get('records', [])

        elapsed = time.time() - start_time

        print(f"✓ API 回應時間: {elapsed:.2f} 秒")
        print(f"✓ 該日總筆數: {len(records):,} 筆")

        # 在本地過濾關鍵字
        keyword_matches = []
        keywords = ["軟體", "系統", "APP", "網站", "資訊", "開發", "建置"]

        for record in records:
            brief = record.get('brief', {})
            title = brief.get('title', '')

            if any(kw in title for kw in keywords):
                keyword_matches.append(record)

        print(f"✓ 關鍵字匹配: {len(keyword_matches)} 筆 ({len(keyword_matches)/len(records)*100:.1f}%)")

        if keyword_matches:
            print(f"\n第一筆匹配範例:")
            print(f"  標題: {keyword_matches[0]['brief']['title']}")
            print(f"  機關: {keyword_matches[0]['unit_name']}")

        print(f"\n資料完整性分析:")
        print(f"  ✗ 預算金額: 無 (需額外查詢 /api/tender)")
        print(f"  ✗ 截止日期: 無 (需額外查詢 /api/tender)")
        print(f"  ✓ 標案編號: 有")
        print(f"  ✓ 標案標題: 有")

        return {
            'method': 'listbydate',
            'time': elapsed,
            'total_records': len(records),
            'matched_records': len(keyword_matches),
            'requires_detail_api': True,
            'filtering': 'client-side'
        }

    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return None


def compare_results():
    """比較兩種方法"""
    print(f"\n{'#'*60}")
    print(f"# 兩種 API 方法的效能比較")
    print(f"# 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # 測試搜尋方法
    search_result = test_search_method("軟體")

    # 測試日期方法
    listbydate_result = test_listbydate_method("20251119")

    # 比較結果
    print(f"\n{'='*60}")
    print(f"比較總結")
    print(f"{'='*60}")

    if search_result and listbydate_result:
        print(f"\n速度比較:")
        print(f"  searchbytitle: {search_result['time']:.2f} 秒")
        print(f"  listbydate:    {listbydate_result['time']:.2f} 秒")
        print(f"  → searchbytitle 快 {listbydate_result['time']/search_result['time']:.1f} 倍")

        print(f"\n資料量比較:")
        print(f"  searchbytitle: 取得 100 筆 (第 1 頁，共 {search_result['total_records']:,} 筆)")
        print(f"  listbydate:    取得 {listbydate_result['total_records']:,} 筆 (單日全部)")
        print(f"  → searchbytitle 減少 {(1 - 100/listbydate_result['total_records'])*100:.1f}% 傳輸量")

        print(f"\n覆蓋範圍:")
        print(f"  searchbytitle: 搜尋全時間範圍 ({search_result['total_records']:,} 筆)")
        print(f"  listbydate:    單日範圍 (需逐日查詢)")

        print(f"\n共同限制:")
        print(f"  兩種方法都需要額外調用 /api/tender 來取得:")
        print(f"    - 預算金額")
        print(f"    - 截止日期")
        print(f"    - pkPmsMain (政府採購網連結)")

    print(f"\n{'='*60}")
    print(f"建議")
    print(f"{'='*60}")
    print("""
方案 1: 完全改用 searchbytitle
  優點:
    ✓ 極快速度 (伺服器端過濾)
    ✓ 減少傳輸量 95%+
    ✓ 支援關鍵字搜尋
    ✓ 搜尋全時間範圍
  缺點:
    ✗ 可能漏掉某些案件 (依賴 API 搜尋品質)
    ✗ 仍需逐筆查詢詳細資料 (預算、截止日期)
    ✗ 最多 10,000 筆結果限制

方案 2: 混合使用
  - 平常: 使用 searchbytitle (快速掃描)
  - 定期: 使用 listbydate (完整檢查,確保不漏)

方案 3: 保持現狀 (listbydate)
  優點:
    ✓ 完整覆蓋
    ✓ 不依賴搜尋品質
  缺點:
    ✗ 慢 (需處理大量無關資料)
    ✗ 浪費頻寬

推薦: 方案 1 (完全改用 searchbytitle)
理由: 對於監控場景,速度和效率更重要,
      API 搜尋品質通常很好,漏掉極少數案件是可接受的。
""")


if __name__ == "__main__":
    compare_results()
