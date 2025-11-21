# GitHub Actions 自動化設置指南

## 📋 概述

本專案已配置 GitHub Actions 自動執行標案監控，採用三模式運作：
- **初始化模式**：手動觸發，掃描最近 14 天標案（約 15-20 分鐘）
- **日常監控模式**：每 2 小時自動執行，掃描最近 1 天（< 2 分鐘）
- **日報生成模式**：每天 20:00 自動執行，生成當日統計報告（< 5 秒）

## ⚙️ 設置步驟

### 1. 設定 GitHub Secrets

前往 GitHub Repository 設定頁面:
```
Settings → Secrets and variables → Actions → New repository secret
```

需要新增以下兩個 Secrets:

#### Secret 1: `LINE_CHANNEL_ACCESS_TOKEN`
- **Name**: `LINE_CHANNEL_ACCESS_TOKEN`
- **Value**: 你的 LINE Channel Access Token
- **範例**: `hYxnseJDq93zdapjs6B+...`

#### Secret 2: `LINE_USER_ID`
- **Name**: `LINE_USER_ID`
- **Value**: 你的 LINE User ID
- **範例**: `U911096a75c1cb1d00e11c8a5a1dd9cd2`

### 2. 啟用 Workflows 權限

確保 GitHub Actions 有寫入權限來提交資料庫更新:

```
Settings → Actions → General → Workflow permissions
→ 選擇 "Read and write permissions"
→ 勾選 "Allow GitHub Actions to create and approve pull requests"
→ Save
```

### 3. 驗證設置

#### 方法 A: 手動觸發測試
1. 前往 `Actions` 頁籤
2. 選擇 `PCC 標案監控` workflow
3. 點擊 `Run workflow` → `Run workflow`
4. 等待執行完成,檢查是否收到 LINE 通知

#### 方法 B: 檢查 Secrets
前往 `Settings → Secrets and variables → Actions`,確認看到:
- ✅ `LINE_CHANNEL_ACCESS_TOKEN`
- ✅ `LINE_USER_ID`

## 📅 執行排程

### 日常監控模式
- **頻率**: 每 2 小時（台北時間 08:00-18:00）
- **Cron 表達式**: `0 0,2,4,6,8,10 * * *` (UTC)
- **執行時間**:
  - 00:00 UTC = 08:00 台北時間
  - 02:00 UTC = 10:00 台北時間
  - 04:00 UTC = 12:00 台北時間
  - 06:00 UTC = 14:00 台北時間
  - 08:00 UTC = 16:00 台北時間
  - 10:00 UTC = 18:00 台北時間

### 日報生成模式
- **頻率**: 每天一次
- **Cron 表達式**: `0 12 * * *` (UTC)
- **執行時間**: 12:00 UTC = 20:00 台北時間

### 初始化模式
- **觸發方式**: 僅手動觸發
- **用途**: 首次執行或重建資料庫

## 🔍 監控執行狀態

### 查看執行歷史
1. 前往 `Actions` 頁籤
2. 查看最近的 workflow runs
3. 點擊特定 run 查看詳細日誌

### 執行結果
- ✅ **成功**: 綠色勾勾,表示正常執行
- ❌ **失敗**: 紅色 X,點擊查看錯誤日誌
- 🟡 **執行中**: 黃色圓圈,正在執行

### 日誌保留
- 失敗時會自動上傳 `logs/` 目錄作為 artifact
- 保留天數: 7 天

## 📊 資料庫與日報管理

### 資料庫持久化
- 使用 GitHub Artifacts 保存資料庫狀態
- 每次執行後自動上傳 `tenders.db`
- 保留天數：90 天
- 下次執行時自動下載最新資料庫

### 日報自動生成
- 每天 20:00（台北時間）自動執行
- 生成 Markdown 格式日報至 `reports/` 目錄
- 自動 Git commit 並推送到 GitHub
- Commit message 包含 `[skip ci]` 避免循環執行

## 🚨 常見問題

### Q1: 沒有收到 LINE 通知
**檢查清單**:
- [ ] GitHub Secrets 是否設置正確？
- [ ] Secret 名稱是否完全正確（區分大小寫）？
- [ ] LINE Channel Access Token 是否過期？
- [ ] User ID 是否正確？

**除錯方式**:
1. 前往 Actions 頁籤查看執行日誌
2. 搜尋 "LINE" 關鍵字查看通知發送狀態
3. 查看是否有錯誤訊息

### Q2: Workflow 沒有自動執行
**可能原因**:
- Repository 超過 60 天無活動,GitHub 會停用 scheduled workflows
- 需要手動觸發一次或推送 commit 重新啟動

**解決方式**:
- 手動觸發一次 workflow
- 或推送任何 commit 到 repository

### Q3: 資料庫推送失敗
**錯誤訊息**: `refusing to allow a GitHub App to create or update workflow`

**解決方式**:
1. 前往 `Settings → Actions → General → Workflow permissions`
2. 選擇 "Read and write permissions"
3. 勾選 "Allow GitHub Actions to create and approve pull requests"

### Q4: 執行時間不符預期
**說明**: GitHub Actions 使用 UTC 時區

**轉換公式**:
```
台灣時間 = UTC 時間 + 8 小時
```

**範例**:
- 想在台灣時間 09:00 執行
- Cron 應設為: `0 1 * * *`（01:00 UTC）

## 🔧 進階設定

### 修改執行頻率
編輯 `.github/workflows/monitor.yml`:

```yaml
on:
  schedule:
    # 每小時執行
    - cron: '0 * * * *'

    # 每 2 小時執行
    # - cron: '0 */2 * * *'

    # 每天 09:00, 17:00 台北時間執行
    # - cron: '0 1,9 * * *'  # UTC 時間
```

### 停用自動執行
1. 註解或刪除 `schedule` 區塊
2. 保留 `workflow_dispatch` 允許手動觸發

### 測試模式
在 `monitor.py` 執行前加入測試參數:
```yaml
- name: 執行標案監控
  env:
    LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
    LINE_USER_ID: ${{ secrets.LINE_USER_ID }}
  run: |
    python monitor.py --dry-run  # 加入 dry-run 參數
```

## 📝 相關連結

- [GitHub Actions 文檔](https://docs.github.com/en/actions)
- [Cron 表達式生成器](https://crontab.guru/)
- [LINE Messaging API 文檔](https://developers.line.biz/en/docs/messaging-api/)
- [專案開發日報](/docs/daily/)

## ✅ 檢查清單

設置完成後,確認以下項目:

- [ ] LINE_CHANNEL_ACCESS_TOKEN Secret 已設置
- [ ] LINE_USER_ID Secret 已設置
- [ ] Workflow permissions 設為 "Read and write permissions"
- [ ] 手動觸發測試成功
- [ ] 收到測試 LINE 通知
- [ ] 資料庫自動 commit 成功

---

最後更新: 2025-11-21
