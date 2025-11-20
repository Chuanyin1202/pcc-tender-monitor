# PCC 政府採購標案監控系統 🔍

自動監控台灣政府採購網的軟體標案，提供智能分析與通知功能。

## ✨ 功能特色

### 核心功能
- ✅ **資料庫中心架構**：以 SQLite 為單一資料來源，追蹤活躍標案狀態
- ✅ **智能狀態管理**：自動歸檔已結束標案（決標/廢標/過期）
- ✅ **三模式運作**：初始化、日常監控、日報生成
- ✅ **自動抓取**：使用 g0v PCC API 取得政府採購網資料
- ✅ **智慧過濾**：預算範圍 10 萬 ~ 500 萬的軟體案
- ✅ **專業日誌**：完整的分級日誌系統（DEBUG/INFO/WARNING/ERROR）

### 自動化功能
- ✅ **GitHub Actions 整合**：完全自動化運行，無需本機執行
- ✅ **資料庫持久化**：使用 GitHub Artifacts 保存狀態（90天）
- ✅ **日報自動生成**：每天 20:00 自動生成 Markdown 日報並提交
- ✅ **LINE 即時通知**：發現新標案立即推播
- ✅ **日誌輪轉**：自動管理日誌檔案（10MB，保留 5 份）

## 系統架構

### 三種執行模式

#### 1. 初始化模式 (`--mode init`)
- **用途**：首次執行或重建資料庫
- **掃描範圍**：最近 14 天
- **執行時間**：約 15-20 分鐘
- **觸發方式**：手動觸發

#### 2. 日常監控模式 (`--mode monitor`)
- **用途**：監控新標案與狀態變更
- **掃描範圍**：最近 1 天
- **執行時間**：< 2 分鐘
- **排程**：每 2 小時（台北時間 8:00-18:00）
- **功能**：
  - 查詢新標案並儲存
  - 歸檔已結束標案
  - 發送 LINE 通知

#### 3. 日報生成模式 (`--mode report`)
- **用途**：生成每日統計報告
- **執行時間**：< 5 秒
- **排程**：每天 20:00（台北時間）
- **功能**：
  - 統計當日新增/移除標案
  - 生成 Markdown 報告
  - 自動 Git 提交到 reports/

### 資料庫管理策略

**活躍標案追蹤**：
- 只儲存符合條件且未結束的標案
- 每筆包含完整資訊（預算、截止日期、狀態）

**自動歸檔機制**：
- 狀態變更（決標、廢標、無法決標、取消）
- 截止日期已過
- 移至 `tenders_archive` 表保存歷史

**優勢**：
- 資料庫永遠保持精簡
- 快速查詢活躍標案
- 完整保留歷史記錄

## 快速開始

### GitHub Actions 自動化（推薦）

完全自動化執行，無需本機安裝。

#### 設置步驟

1. **Fork 本專案到你的 GitHub**

2. **設定 GitHub Secrets**（必要）
   - 前往 `Settings → Secrets and variables → Actions`
   - 新增兩個 secrets：
     - `LINE_CHANNEL_ACCESS_TOKEN`: 你的 LINE Channel Access Token
     - `LINE_USER_ID`: 你的 LINE User ID

3. **啟用 Workflows 權限**
   - 前往 `Settings → Actions → General → Workflow permissions`
   - 選擇 "Read and write permissions"

4. **手動執行初始化**
   - 前往 `Actions` 頁籤
   - 選擇 `政府標案監控` workflow
   - 點擊 `Run workflow`
   - Mode 選擇 `init`
   - 點擊 `Run workflow`

#### 執行排程

- **日常監控**：每 2 小時（台北時間 8:00, 10:00, 12:00, 14:00, 16:00, 18:00）
- **日報生成**：每天 20:00（台北時間）
- **自動通知**：發現新標案立即發送 LINE 通知

#### 狀態檢查

- 查看執行歷史：`Actions` 頁籤
- 下載資料庫：從 Artifacts 下載 `tender-database`
- 查看日報：`reports/` 目錄

### 本機執行（開發用）

#### 1. Clone 專案

```bash
git clone https://github.com/Chuanyin1202/pcc-tender-monitor.git
cd pcc-tender-monitor
```

#### 2. 安裝依賴

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. 設定 LINE 通知（選用）

```bash
# 方法 A：使用環境變數
export LINE_CHANNEL_ACCESS_TOKEN='你的_Token'
export LINE_USER_ID='你的_User_ID'

# 方法 B：使用 .env 檔案
cp .env.example .env
# 編輯 .env 填入資訊
```

**如何取得 LINE 資訊？**

1. **申請 LINE Messaging API**
   - 前往 [LINE Developers Console](https://developers.line.biz/console/)
   - 建立 Provider 和 Messaging API Channel
   - 從 Messaging API 頁籤取得 **Channel Access Token**

2. **取得 User ID**
   - 從 [LINE Official Account Manager](https://manager.line.biz/) 後台查看
   - 或設定 webhook 接收訊息事件取得

**注意**：LINE Notify 服務已於 2025/3/31 停止，本專案使用 LINE Messaging API。

#### 4. 執行監控

```bash
# 初始化（首次執行）
python monitor.py --mode init

# 日常監控
python monitor.py --mode monitor

# 生成日報
python monitor.py --mode report
```

## 自訂配置

編輯 `monitor.py` 調整參數：

```python
# 預算範圍
MIN_BUDGET = 100000      # 10 萬
MAX_BUDGET = 5000000     # 500 萬

# 關鍵字過濾
SEARCH_KEYWORDS = [
    "軟體", "系統", "APP", "網站", "維護",
    "資訊", "開發", "建置", "平台", "應用程式"
]

KEYWORDS_EXCLUDE = [
    "硬體", "監控", "機房", "消防", "電力",
    "機械", "儀器", "土木", "網路設備"
]

# 掃描天數
QUICK_MODE_DAYS = 1      # monitor 模式
DEEP_MODE_DAYS = 14      # init 模式
```

## 專案結構

```
pcc-tender-monitor/
├── monitor.py                  # 主程式
├── requirements.txt            # Python 依賴
├── .env.example               # 環境變數範例
├── .gitignore                 # Git 忽略清單
├── README.md                  # 本文件
├── .github/
│   └── workflows/
│       └── monitor.yml        # GitHub Actions 配置
├── docs/
│   ├── IMPLEMENTATION_PLAN.md # 實作計劃
│   └── API_PERFORMANCE_ANALYSIS.md # API 效能分析
├── reports/                   # 日報目錄（自動生成）
│   └── YYYY-MM-DD.md         # 每日報告
├── tenders.db                 # SQLite 資料庫（不進版控）
├── logs/                      # 日誌目錄（不進版控）
│   └── monitor.log           # 執行日誌
└── venv/                      # 虛擬環境（不進版控）
```

## 資料來源

本專案使用 [g0v 台灣政府採購公告 API](https://pcc-api.openfun.app/)

- **資料來源**：中華民國政府電子採購網
- **更新頻率**：每日更新
- **授權**：遵循[政府採購網著作權聲明](https://web.pcc.gov.tw/pis/main/pis/client/pssa/right.do)

## 注意事項

1. **API 使用**：程式已內建請求延遲（0.5秒）保護
2. **資料準確性**：請以政府採購網官方資料為準
3. **資料保留**：
   - 活躍標案：儲存在 `tenders` 表
   - 歷史標案：歸檔到 `tenders_archive` 表
   - Artifacts：GitHub 保存 90 天
4. **商業使用**：如需商業使用，請參考政府採購網的開放資料政策

## 常見問題

### Q: 如何查看執行狀態？
A: 前往 GitHub Actions 頁籤查看執行歷史和日誌。

### Q: 如何查看日報？
A: 日報自動儲存在 `reports/` 目錄，格式為 `YYYY-MM-DD.md`。

### Q: 資料庫在哪裡？
A:
- GitHub Actions：儲存在 Artifacts（tender-database）
- 本機執行：`tenders.db` 檔案

### Q: 如何修改監控頻率？
A: 編輯 `.github/workflows/monitor.yml` 中的 cron 排程。

### Q: 可以修改預算範圍嗎？
A: 編輯 `monitor.py` 中的 `MIN_BUDGET` 和 `MAX_BUDGET` 參數。

### Q: 為什麼有些標案沒有通知？
A: 可能原因：
- 預算不在 10萬~500萬 範圍
- 標題不包含關鍵字或包含排除關鍵字
- 截止日期已過
- 無法取得完整資訊（預算或截止日期）

## 技術文檔

- [實作計劃](docs/IMPLEMENTATION_PLAN.md) - 系統架構與實作細節
- [API 效能分析](docs/API_PERFORMANCE_ANALYSIS.md) - API 選擇與優化

## 授權

MIT License

## 貢獻

歡迎提交 Issue 或 Pull Request！

---

Made with ❤️ using Claude Code
