# PCC 政府採購標案監控系統 🔍

自動監控台灣政府採購網的軟體標案，提供智能分析與通知功能。

## ✨ 功能特色

### 核心功能
- ✅ **增量查詢**：智能記錄上次檢查時間，只抓取新增標案
- ✅ **自動抓取**：使用 g0v PCC API 取得政府採購網資料
- ✅ **智慧過濾**：預算範圍 15 萬 ~ 150 萬的軟體案
- ✅ **SQLite 去重**：避免重複通知
- ✅ **專業日誌**：完整的分級日誌系統（DEBUG/INFO/WARNING/ERROR）

### 已完成功能（Phase 1）
- ✅ **日誌輪轉**：自動管理日誌檔案（10MB，保留 5 份）
- ✅ **資料庫事務**：使用 context manager 確保資料安全
- ✅ **強化解析**：支援多種日期與預算格式
- ✅ **優化 API**：降低 timeout 時間提升效率
- ✅ **LINE 推播**：LINE Messaging API 即時通知

### 已完成功能（Phase 2）
- ✅ **GitHub Actions 自動執行**：每小時自動監控，GitHub Secrets 管理敏感資訊

### 規劃中功能（Phase 3）
- 🚧 GitHub Pages 儀表板
- 🚧 Notion 整合管理（選用）

## 快速開始

### 1. Clone 專案

```bash
git clone https://github.com/Chuanyin1202/pcc-tender-monitor.git
cd pcc-tender-monitor
```

### 2. 安裝依賴

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 設定 LINE 通知（選用）

如需接收 LINE 即時通知，需設定環境變數：

```bash
# 複製範例設定檔
cp .env.example .env

# 編輯 .env 填入你的 LINE 資訊
# LINE_CHANNEL_ACCESS_TOKEN=你的_Channel_Access_Token
# LINE_USER_ID=你的_User_ID
```

**如何取得 LINE 資訊？**

1. **申請 LINE Messaging API**
   - 前往 [LINE Developers Console](https://developers.line.biz/console/)
   - 建立 Provider 和 Messaging API Channel
   - 從 Messaging API 頁籤取得 **Channel Access Token**

2. **取得 User ID**
   - 方法 A：從 [LINE Official Account Manager](https://manager.line.biz/) 後台查看
   - 方法 B：設定 webhook 接收訊息事件取得（詳見開發日報）

**注意**：LINE Notify 服務已於 2025/3/31 停止，本專案使用 LINE Messaging API。

### 4. 執行監控

```bash
# 激活虛擬環境
source venv/bin/activate  # Windows: venv\Scripts\activate

# 不使用 LINE 通知
python monitor.py

# 使用 LINE 通知（設定環境變數）
LINE_CHANNEL_ACCESS_TOKEN='...' LINE_USER_ID='...' python monitor.py

# 或使用 .env 檔案（需安裝 python-dotenv）
python monitor.py
```

第一次執行會回溯 30 天的標案資料，之後會使用增量查詢只抓取新標案。

## GitHub Actions 自動化執行

本專案已配置 GitHub Actions,可在 GitHub 上自動執行監控,無需本機運行。

### 設置步驟

1. **Fork 本專案到你的 GitHub**
2. **設定 GitHub Secrets**（必要）
   - 前往 `Settings → Secrets and variables → Actions`
   - 新增兩個 secrets:
     - `LINE_CHANNEL_ACCESS_TOKEN`: 你的 LINE Channel Access Token
     - `LINE_USER_ID`: 你的 LINE User ID
3. **啟用 Workflows 權限**
   - 前往 `Settings → Actions → General → Workflow permissions`
   - 選擇 "Read and write permissions"
4. **手動觸發測試**
   - 前往 `Actions` 頁籤
   - 選擇 `PCC 標案監控` workflow
   - 點擊 `Run workflow` 測試

### 執行排程
- **頻率**: 每小時執行一次（整點）
- **自動通知**: 發現新標案會自動發送 LINE 通知
- **資料同步**: 自動 commit 更新資料庫到 GitHub

**詳細設置說明**: 請參考 [GitHub Actions 設置指南](docs/github-actions-setup.md)

## 自訂配置

編輯 `monitor.py` 調整參數：

```python
# 預算範圍
MIN_BUDGET = 150000
MAX_BUDGET = 1500000

# 關鍵字過濾
KEYWORDS_INCLUDE = ["軟體", "系統", "APP", "網站", "維護", "資訊", "開發", "建置"]
KEYWORDS_EXCLUDE = ["硬體", "電腦", "監控", "機房", "土木", "網路設備"]

# 搜尋天數
SEARCH_DAYS = 3
```

## 查詢標案

使用 `query_tenders.py` 查詢資料庫內的標案：

### 基本使用

```bash
# 列出最近 30 天的標案（預設）
python query_tenders.py

# 列出最近 7 天的標案
python query_tenders.py --days 7

# 列出最近 90 天的標案
python query_tenders.py --days 90
```

### 進階篩選

```bash
# 搜尋標題含"系統"的標案
python query_tenders.py --keyword "系統"

# 搜尋臺北市政府的標案
python query_tenders.py --unit "臺北市"

# 預算範圍篩選（50 萬 ~ 100 萬）
python query_tenders.py --min-budget 500000 --max-budget 1000000

# 組合條件查詢
python query_tenders.py --days 14 --keyword "APP" --min-budget 300000
```

### 匯出 CSV

```bash
# 匯出最近 30 天的標案
python query_tenders.py --export result.csv

# 匯出特定條件的標案
python query_tenders.py --days 60 --keyword "網站" --export website_tenders.csv
```

### 查詢結果說明

- **標案名稱**：採購案件標題
- **招標機關**：發布標案的政府單位
- **預算金額**：採購預算
- **發現日期**：本系統發現該標案的日期
- **詳細連結**：政府採購網的標案詳細頁面
- **統計資訊**：總筆數、預算總額、平均預算

## 專案結構

```
pcc-tender-monitor/
├── monitor.py              # 主程式（監控 & 資料收集）
├── query_tenders.py        # 查詢與匯出工具
├── requirements.txt        # Python 依賴
├── .env.example           # 環境變數範例
├── .gitignore             # Git 忽略清單
├── README.md              # 本文件
├── HANDOFF.md             # 專案交接文檔（快照）
├── tenders.db             # SQLite 資料庫（自動生成，不進版控）
├── docs/                   # 文檔目錄
│   └── daily/             # 開發日報（按日期）
│       └── YYYY-MM-DD.md  # 每日開發記錄
├── logs/                   # 日誌目錄（自動生成，不進版控）
│   └── monitor.log        # 執行日誌
└── venv/                   # 虛擬環境（不進版控）
```

## 文檔說明

- **HANDOFF.md**：專案初始交接文檔（快照，不再更新）
- **docs/daily/YYYY-MM-DD.md**：每日開發日報
  - 記錄每日完成項目、技術決策、問題與解決方案
  - 按日期歸檔，避免單一文件過大
  - 查看最新進度請看最近日期的日報

## 資料來源

本專案使用 [g0v 台灣政府採購公告 API](https://pcc-api.openfun.app/)

- **資料來源**：中華民國政府電子採購網
- **更新頻率**：每日更新
- **授權**：遵循[政府採購網著作權聲明](https://web.pcc.gov.tw/pis/main/pis/client/pssa/right.do)

## 注意事項

1. **Rate Limiting**：程式已內建請求延遲保護
2. **資料準確性**：請以政府採購網官方資料為準
3. **資料保留期限**：資料庫自動保留最近 3 個月的標案，超過 90 天的舊資料會自動清理
4. **商業使用**：如需商業使用，請參考政府採購網的開放資料政策

## 授權

MIT License

## 貢獻

歡迎提交 Issue 或 Pull Request！

## 常見問題

### Q: 日誌檔案在哪裡？
A: 執行日誌儲存在 `logs/monitor.log`，支援自動輪轉（最大 10MB，保留 5 份備份）。

### Q: 如何查看歷史標案？
A: 使用 `python query_tenders.py` 指令查詢資料庫，支援多種篩選條件。

### Q: 資料庫會不會越來越大？
A: SQLite 資料庫只儲存基本資訊，每筆約 200 bytes，一年約 5MB。建議定期使用 `query_tenders.py --days 90` 檢視舊資料。

### Q: 可以修改預算範圍嗎？
A: 編輯 `monitor.py` 中的 `MIN_BUDGET` 和 `MAX_BUDGET` 參數即可。

---

Made with ❤️ using Claude Code
