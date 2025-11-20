# 整合 Cloudflare Workers Proxy 到專案

## 📋 完整流程

### Step 1: 部署 Cloudflare Worker（你需要做這步）

請參考 [README.md](./README.md) 完成部署。

**最簡單的方式**：
1. 前往 https://dash.cloudflare.com/
2. Workers & Pages → Create Application → Create Worker
3. Deploy（先用預設程式碼）
4. Edit Code → 刪除全部 → 貼上 `worker.js` 內容 → Save and Deploy
5. **記下你的 Worker URL**，例如：`https://pcc-api-proxy.abc123.workers.dev`

---

### Step 2: 修改 monitor.py（我會幫你做）

部署完成後，告訴我你的 Worker URL，我會幫你修改 `monitor.py`。

**需要修改的地方**（僅 1 處）：

```python
# 原本
PCC_API_BASE = "https://pcc-api.openfun.app"

# 改為
PCC_API_BASE = "https://your-worker.workers.dev"  # 替換為你的 Worker URL
```

---

### Step 3: 本地測試（我會幫你做）

修改完成後，我會執行本地測試：

```bash
venv/bin/python3 monitor.py
```

確認能正常抓取標案資料。

---

### Step 4: 推送到 GitHub（我會幫你做）

確認本地測試通過後，我會：

1. Git commit
2. Git push
3. 檢查 GitHub Actions 是否成功執行

---

## 🎯 預期結果

完成後：
- ✅ GitHub Actions 不再出現 403 錯誤
- ✅ 每小時自動執行標案監控
- ✅ 完全免費（Cloudflare Workers 免費額度充足）
- ✅ 程式碼改動僅 1 行

---

## 🔍 測試 Worker

部署完成後，你可以先測試 Worker 是否正常：

```bash
# 測試取得今天的標案
curl "https://your-worker.workers.dev/api/listbydate?date=20251120"
```

應該會回傳 JSON 格式的標案資料。

---

## ❓ 常見問題

### Q: Worker URL 在哪裡找？
A: 部署完成後，Cloudflare Dashboard 會顯示，格式為 `https://<worker-name>.<your-subdomain>.workers.dev`

### Q: 需要付費嗎？
A: 不需要！Cloudflare Workers 免費版每天 10 萬次請求，你的用量遠低於此。

### Q: 會影響本地開發嗎？
A: 不會。本地和 GitHub Actions 都會使用同一個 Worker URL。

---

## 📞 下一步

請先完成 **Step 1**（部署 Worker），然後告訴我你的 Worker URL，我會繼續完成剩下的步驟。
