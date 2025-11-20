# 政府標案監控系統 - 深度模式實作計劃

## 📋 當前進度（2025-11-20 19:50）

### ✅ 已完成

1. **資料庫升級** (`monitor.py:110-164`)
   - 新增欄位：`status`, `publish_date`, `last_checked`, `last_status_change`
   - 支援自動升級（不影響現有資料）
   - 測試通過 ✓

2. **API 策略變更** (`monitor.py:412-556`)
   - 從 `searchbytitle` 改為 `listbydate` + 本地過濾
   - 原因：解決只能取前100筆的限制
   - 效能：查詢2天取得396個候選，執行時間3分鐘 ✓

3. **雙模式支援** (`monitor.py:598-617`)
   ```bash
   python monitor.py --mode quick   # 快速模式：查最近 2 天
   python monitor.py --mode deep    # 深度模式：查最近 14 天
   ```
   - 參數解析：使用 argparse ✓
   - 快速模式：測試通過，找到20筆符合標案 ✓

4. **深度模式輔助函數** (`deep_mode_functions.py`)
   - `get_active_tenders()`: 取得75個活躍標案 ✓
   - `update_tender_status()`: 更新標案狀態 ✓
   - `check_status_changes()`: 檢查狀態變更 ✓
   - `generate_daily_report()`: 生成Markdown日報 ✓

5. **深度模式整合** (`monitor.py:564-615`)
   - 狀態追蹤邏輯 ✓
   - 日報生成與儲存 ✓
   - Git 自動提交（可選）✓
   - 測試中...

6. **LINE 通知優化** (`monitor.py:245-325`)
   - 新增 `format_line_notification()` 函數 ✓
   - 按預算分級（> 80萬為重點）✓
   - 摘要式通知格式 ✓
   - 狀態變更整合（深度模式）✓

7. **GitHub Actions 雙排程** (`.github/workflows/monitor.yml`)
   - 快速模式：每小時 (`0 * * * *`) ✓
   - 深度模式：每天 00:00 UTC (`0 0 * * *`) ✓
   - 手動觸發支援兩種模式 ✓
   - Git 自動提交配置 ✓

---

## 🚧 待完成功能

### 1. 驗證深度模式執行

**位置**：`monitor.py` 的 `fetch_tenders()` 函數

**需要修改**：
```python
def fetch_tenders(mode='quick'):
    # ... 現有邏輯 ...

    # 新增：深度模式專屬邏輯
    if mode == 'deep':
        # 1. 檢查狀態變更
        from deep_mode_functions import check_status_changes
        status_changes = check_status_changes(API_BASE_URL, HEADERS, API_DELAY)

        # 2. 生成日報
        from deep_mode_functions import generate_daily_report
        from datetime import datetime

        report_content = generate_daily_report(
            new_cases,
            status_changes,
            datetime.now().strftime('%Y-%m-%d')
        )

        # 3. 儲存日報
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)

        report_file = reports_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        logger.info(f"已生成日報: {report_file}")

        # 4. Git 提交（可選）
        if os.getenv("GIT_AUTO_COMMIT", "false") == "true":
            import subprocess
            subprocess.run(["git", "add", "reports/"])
            subprocess.run([
                "git", "commit", "-m",
                f"新增日報 {datetime.now().strftime('%Y-%m-%d')}"
            ])
            subprocess.run(["git", "push"])
```

**實作步驟**：
1. 在 `monitor.py` 頂部 import deep_mode_functions
2. 修改 `fetch_tenders()` 函數，在 `if mode == 'deep':` 區塊加入上述邏輯
3. 測試深度模式執行

**預估時間**：30 分鐘

---

### 2. 優化 LINE 通知格式

**目標**：摘要式通知，避免洗版

**現有格式**（monitor.py:560-578）：
```
📊 政府標案監控報告
模式: 快速掃描
時間: 2025-11-20 19:33

✨ 發現 20 筆新標案:
━━━━━━━━━━━━━━━

1. 標案名稱...
   💰 $1,323,228
   🏢 機關名稱
   🔗 連結

... (列出前5筆)
```

**優化後格式**：
```
📊 標案監控報告 (快速)
🕐 2025-11-20 19:33

✨ 新標案：5 筆
🔄 狀態變更：3 筆 (僅深度模式)
⏰ 即將截止：2 筆 (僅深度模式)

━━━━━━━━━━━━━━━
🔥 重點標案 (預算 > 80萬)

1️⃣ 智慧支付整合平台
   💰 120 萬 | ⏰ 12/15
   🔗 https://...

2️⃣ Adobe軟體授權
   💰 95 萬 | ⏰ 12/20
   🔗 https://...

━━━━━━━━━━━━━━━
📋 完整報告：
https://github.com/.../reports/2025-11-20.md
```

**需要修改的函數**：
```python
def format_line_notification(mode, new_tenders, status_changes=None):
    """
    格式化 LINE 通知訊息

    Args:
        mode: 'quick' 或 'deep'
        new_tenders: 新標案列表
        status_changes: 狀態變更列表 (深度模式)

    Returns:
        str: 格式化的 LINE 訊息
    """
    # 分級處理
    high_priority = [t for t in new_tenders if t['budget'] > 800000]
    medium_priority = [t for t in new_tenders if 500000 <= t['budget'] <= 800000]

    # ... 實作
```

**預估時間**：20 分鐘

---

### 3. GitHub Actions 雙排程配置

**檔案**：`.github/workflows/monitor.yml`

**需要修改**：
```yaml
name: Government Tender Monitor

on:
  schedule:
    # 每小時執行（快速模式）
    - cron: '0 * * * *'
    # 每天 08:00 執行（深度模式）
    - cron: '0 0 * * *'
  workflow_dispatch:
    inputs:
      mode:
        description: '執行模式'
        required: true
        default: 'quick'
        type: choice
        options:
          - quick
          - deep

jobs:
  quick-scan:
    if: github.event.schedule == '0 * * * *' || (github.event_name == 'workflow_dispatch' && github.event.inputs.mode == 'quick')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests
      - name: Run quick scan
        env:
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_USER_ID: ${{ secrets.LINE_USER_ID }}
        run: python monitor.py --mode quick

  deep-scan:
    if: github.event.schedule == '0 0 * * *' || (github.event_name == 'workflow_dispatch' && github.event.inputs.mode == 'deep')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # 需要完整 git 歷史
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests
      - name: Run deep scan
        env:
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_USER_ID: ${{ secrets.LINE_USER_ID }}
          GIT_AUTO_COMMIT: "true"
        run: |
          git config user.name "GitHub Actions Bot"
          git config user.email "actions@github.com"
          python monitor.py --mode deep
      - name: Push reports
        run: |
          git push
```

**預估時間**：15 分鐘

---

## 🔍 測試計劃

### 本地測試

1. **深度模式完整測試**
   ```bash
   python monitor.py --mode deep
   ```
   驗證：
   - ✓ 查詢14天資料
   - ✓ 檢查狀態變更
   - ✓ 生成日報到 reports/
   - ✓ LINE 通知（如果設定）

2. **日報內容驗證**
   - 檢查 `reports/YYYY-MM-DD.md` 是否正確生成
   - 驗證 Markdown 格式
   - 確認統計數字正確

3. **Git 自動提交測試**
   ```bash
   GIT_AUTO_COMMIT=true python monitor.py --mode deep
   git log -1
   ```

### GitHub Actions 測試

1. 手動觸發測試
   - 在 GitHub → Actions → Run workflow
   - 選擇 quick 模式測試
   - 選擇 deep 模式測試

2. 排程測試
   - 等待下一個整點（快速模式）
   - 等待明天 08:00（深度模式）

---

## 📝 待解決問題

1. **關鍵字「系統」太廣**
   - 問題：匹配到「消防系統」「電力系統」等無關案件
   - 解決方案：已加入更多排除關鍵字（消防、電力、機械、儀器）
   - 狀態：✅ 已解決

2. **分頁限制**
   - searchbytitle API 最多只能取 10,000 筆
   - 解決方案：改用 listbydate + 本地過濾
   - 狀態：✅ 已解決

3. **Git commit message 格式**
   - 需求：統一格式、避免簡體字、去AI化
   - 狀態：⏳ 待建立規範（下階段處理）

---

## 🎯 下一步行動

1. **立即執行**（約1小時）：
   - 整合深度模式到 monitor.py
   - 測試深度模式執行
   - 優化 LINE 通知格式

2. **後續優化**（約30分鐘）：
   - 修改 GitHub Actions 配置
   - 本地 + CI/CD 測試
   - 監控實際運行狀況

3. **長期維護**：
   - 定期檢查日報品質
   - 調整關鍵字和排除規則
   - 根據實際使用優化通知頻率

---

## 📚 相關檔案

- `monitor.py`: 主程式（已支援快速模式）
- `deep_mode_functions.py`: 深度模式輔助函數
- `docs/API_PERFORMANCE_ANALYSIS.md`: API 效能分析
- `compare_methods.py`: 兩種API方法比較
- `monitor.py.backup`: 備份（searchbytitle版本）
- `monitor.py.backup2`: 備份（修改前版本）

---

**最後更新**: 2025-11-20 19:35
**進度**: 60% 完成
**預估完成時間**: 再1.5小時
