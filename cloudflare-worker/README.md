# PCC API Cloudflare Workers 反向代理

此 Cloudflare Worker 作為反向代理，將請求轉發到政府採購網 API，解決 GitHub Actions IP 被封鎖的問題。

## 🎯 功能

- 接收來自 GitHub Actions 的請求
- 轉發到 `https://pcc-api.openfun.app`
- 返回 API 回應
- 自動處理 CORS

## 📦 部署步驟

### 方法 A：使用 Cloudflare Dashboard（推薦，最簡單）

1. **登入 Cloudflare**
   - 前往 [Cloudflare Dashboard](https://dash.cloudflare.com/)
   - 如果沒有帳號，免費註冊一個

2. **建立 Worker**
   - 左側選單選擇 "Workers & Pages"
   - 點擊 "Create Application"
   - 選擇 "Create Worker"
   - 點擊 "Deploy"（先用預設程式碼部署）

3. **編輯 Worker 程式碼**
   - 部署完成後，點擊 "Edit Code"
   - 刪除所有預設程式碼
   - 複製 `worker.js` 的完整內容貼上
   - 點擊右上角 "Save and Deploy"

4. **取得 Worker URL**
   - 部署完成後會顯示 Worker URL
   - 格式：`https://pcc-api-proxy.<your-subdomain>.workers.dev`
   - **記下這個 URL**，等等會用到

### 方法 B：使用 Wrangler CLI（進階）

1. **安裝 Wrangler**
   ```bash
   npm install -g wrangler
   ```

2. **登入 Cloudflare**
   ```bash
   wrangler login
   ```

3. **部署 Worker**
   ```bash
   cd cloudflare-worker
   wrangler deploy
   ```

4. **查看 Worker URL**
   ```bash
   wrangler deployments list
   ```

## 🔗 取得 Worker URL

部署完成後，你會得到一個 URL，例如：
```
https://pcc-api-proxy.your-name.workers.dev
```

## ✅ 測試 Proxy

使用 curl 測試 Worker 是否正常運作：

```bash
# 測試取得標案列表
curl "https://your-worker.workers.dev/api/listbydate?date=20251120"
```

如果回應包含標案資料（JSON 格式），表示 Worker 正常運作！

## 📝 下一步

部署完成後，請執行以下步驟：

1. 記下你的 Worker URL
2. 回到主專案，修改 `monitor.py` 使用新的 URL
3. 本地測試
4. 推送到 GitHub 並測試 Actions

## 🔒 安全性

- Worker 只轉發請求，不儲存任何資料
- 支援 CORS，允許來自 GitHub 的請求
- 完全無狀態，不會洩漏敏感資訊

## 💰 成本

- Cloudflare Workers 免費版：**每天 10 萬次請求**
- 你的預估用量：每天約 240 次
- **完全免費！**

## 🐛 故障排除

### Worker 部署失敗
- 確認 JavaScript 語法正確
- 檢查 Cloudflare 帳號是否已驗證 email

### 測試時收到 404 錯誤
- 確認 Worker URL 正確
- 確認路徑包含 `/api/...`

### 測試時收到 500 錯誤
- 檢查 Worker logs（Dashboard → Workers → 你的 Worker → Logs）
- 確認目標 API 可以訪問

## 📚 更多資訊

- [Cloudflare Workers 文檔](https://developers.cloudflare.com/workers/)
- [Wrangler CLI 文檔](https://developers.cloudflare.com/workers/wrangler/)
