#!/usr/bin/env python3
"""
回填腳本：為現有標案補充詳細資訊
- url
- unit_name（機關名稱）
- award_type（決標方式）
- is_electronic（電子投標）
- requires_deposit（押標金）
- contract_duration（履約期限）
- qualification_summary（資格要求）
"""

import sqlite3
import time
from pathlib import Path
import logging
from monitor import get_tender_detail, DB_PATH

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_tender_details(limit=None):
    """回填所有缺少詳細資訊的標案

    Args:
        limit: 限制處理的數量，用於測試（None 表示處理全部）
    """

    logger.info("開始回填標案詳細資訊...")

    # 1. 查詢需要回填的標案
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        query = """
            SELECT unit_id, job_number, brief, pk_pms_main
            FROM tenders
            WHERE (url IS NULL OR url = '')
               OR (unit_name IS NULL OR unit_name = '')
               OR (award_type IS NULL OR award_type = '')
            ORDER BY budget DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        tenders_to_update = cursor.fetchall()

    total = len(tenders_to_update)
    logger.info(f"找到 {total} 筆需要回填的標案")

    if total == 0:
        logger.info("沒有需要回填的標案")
        return

    # 2. 逐一回填
    success_count = 0
    failed_count = 0

    for idx, (unit_id, job_number, brief, pk_pms_main) in enumerate(tenders_to_update, 1):
        logger.info(f"[{idx}/{total}] 處理: {brief[:50]}...")

        try:
            # 呼叫 get_tender_detail 取得完整資訊
            result = get_tender_detail(unit_id, job_number)

            if result:
                budget, pk_pms_main_new, deadline, url, award_type, is_electronic, requires_deposit, contract_duration, qualification_summary, unit_name = result

                # 更新資料庫
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE tenders
                        SET url = ?,
                            unit_name = ?,
                            award_type = ?,
                            is_electronic = ?,
                            requires_deposit = ?,
                            contract_duration = ?,
                            qualification_summary = ?
                        WHERE unit_id = ? AND job_number = ?
                    """, (url, unit_name, award_type, is_electronic, requires_deposit,
                          contract_duration, qualification_summary, unit_id, job_number))
                    conn.commit()

                success_count += 1
                logger.info(f"  ✓ 更新成功 - 機關: {unit_name[:20] if unit_name else 'N/A'}..., 決標方式: {award_type or 'N/A'}")
            else:
                failed_count += 1
                logger.warning(f"  ✗ 無法取得詳細資訊")

            # 避免請求過快
            time.sleep(0.5)

        except Exception as e:
            failed_count += 1
            logger.error(f"  ✗ 處理失敗: {e}")
            continue

    # 3. 輸出統計
    logger.info("\n" + "="*60)
    logger.info(f"回填完成！")
    logger.info(f"成功: {success_count} 筆")
    logger.info(f"失敗: {failed_count} 筆")
    logger.info(f"總計: {total} 筆")
    logger.info("="*60)


if __name__ == "__main__":
    import sys

    # 支援命令列參數指定 limit
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            logger.info(f"測試模式：僅處理前 {limit} 筆")
        except ValueError:
            logger.error("參數必須是數字")
            sys.exit(1)

    backfill_tender_details(limit=limit)
