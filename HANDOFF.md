# 專案交接文檔

**交接時間**: 2025-11-19
**專案名稱**: PCC 政府採購標案監控系統
**GitHub Repo**: https://github.com/Chuanyin1202/pcc-tender-monitor
**專案路徑**: `/Volumes/MAC-SSD/Development/crawler-tools/pcc-tender-monitor`

---

## 📊 當前進度

### ✅ 已完成 - Phase 1

1. **核心功能優化**
   - ✅ 專業日誌系統（RotatingFileHandler，10MB，保留5份）
   - ✅ 資料庫事務安全（Context Manager）
   - ✅ 增量查詢邏輯（記錄最後檢查時間）
   - ✅ 強化日期解析（支援多種格式：民國年、西元年、ISO）
   - ✅ 強化預算解析（支援多種格式）
   - ✅ 優化 API timeout（30s → 15s）

2. **專案遷移**
   - ✅ 從 `/Users/alexhuang/Development/crawler-tools /gov-tender-monitor`
   - ✅ 到 `/Volumes/MAC-SSD/Development/crawler-tools/pcc-tender-monitor`
   - ✅ 重新命名為 `pcc-tender-monitor`

3. **版控設定**
   - ✅ 建立完整 `.gitignore`（排除 venv/, logs/, *.db, *.backup）
   - ✅ 更新 README.md（標註 Phase 1 完成、Phase 2 規劃）
   - ✅ 推送到 GitHub（使用 SSH，個人帳號 Chuanyin1202）
   - ✅ 移除資料庫檔案從版控

### 🔄 進行中 - 測試階段

**目前狀態**: 環境檢查已完成，準備執行功能測試

**環境檢查結果**:
- ✅ 虛擬環境存在（Python 3.14）
- ✅ requests 套件已安裝
- ✅ logs/ 目錄存在
- ✅ logs/monitor.log 存在
- ✅ tenders.db 存在（115 筆歷史標案）

### 📋 待辦事項

1. **測試 monitor.py 執行** (in_progress)
   - 驗證增量查詢功能
   - 檢查日誌輸出
   - 確認資料庫更新

2. **測試 query_tenders.py 功能** (pending)
   - 基本查詢
   - 篩選條件
   - CSV 匯出

3. **驗證檔案結構與日誌** (pending)
   - 日誌輪轉功能
   - 相對路徑正確性

4. **Phase 2 實作** (pending)
   - LINE Notify 整合
   - GitHub Actions 自動化
   - GitHub Pages 儀表板
   - Notion Database 整合（選用）

---

## 🧪 測試步驟

### 1. 測試 monitor.py

```bash
cd /Volumes/MAC-SSD/Development/crawler-tools/pcc-tender-monitor

# 執行監控腳本
./venv/bin/python monitor.py
```

**預期結果**:
- 使用增量查詢（從上次檢查時間開始，應該是 2025-11-19 左右）
- 顯示查詢日期範圍
- 輸出找到的標案數量
- 自動更新 logs/monitor.log
- 更新 tenders.db

**驗證重點**:
- [ ] 日誌檔案有新內容
- [ ] 增量查詢邏輯正確（不重複抓取舊資料）
- [ ] 沒有路徑錯誤
- [ ] 資料庫正常寫入

### 2. 測試 query_tenders.py

```bash
# 基本查詢（最近 30 天）
./venv/bin/python query_tenders.py

# 查詢最近 7 天
./venv/bin/python query_tenders.py --days 7

# 關鍵字搜尋
./venv/bin/python query_tenders.py --keyword "系統"

# 預算範圍查詢
./venv/bin/python query_tenders.py --min-budget 300000 --max-budget 1000000

# 匯出 CSV
./venv/bin/python query_tenders.py --export test_output.csv
```

**驗證重點**:
- [ ] 查詢結果正確
- [ ] 篩選條件生效
- [ ] CSV 匯出成功
- [ ] 統計資訊正確

### 3. 檢查日誌系統

```bash
# 查看日誌內容
tail -50 logs/monitor.log

# 檢查日誌輪轉（如果檔案大小接近 10MB）
ls -lh logs/
```

**驗證重點**:
- [ ] 日誌格式正確（時間戳、級別、訊息）
- [ ] DEBUG/INFO/WARNING 級別都有記錄
- [ ] 日誌輪轉功能正常（如有必要）

---

## 📁 專案結構

```
pcc-tender-monitor/
├── monitor.py              # 主程式（監控 & 資料收集）
├── query_tenders.py        # 查詢與匯出工具
├── requirements.txt        # Python 依賴（requests>=2.31.0）
├── .gitignore             # Git 忽略清單
├── README.md              # 專案說明
├── HANDOFF.md            # 本交接文檔
├── tenders.db             # SQLite 資料庫（115 筆標案）
├── logs/                   # 日誌目錄
│   └── monitor.log        # 執行日誌
├── venv/                   # 虛擬環境（Python 3.14）
├── test_budget.py         # 測試腳本
├── test_quick.py          # 測試腳本
├── monitor.py.backup      # Phase 1 前的備份
└── query_tenders.py.backup # Phase 1 前的備份
```

---

## ⚙️ 重要配置

### Git 設定
- **Git 帳號**: 已使用路徑區分
  - 全域預設: Chuanyin1202 / alexabc@gmail.com
  - Workspace: Alex / alex@medier.io
- **Remote URL**: git@github.com:Chuanyin1202/pcc-tender-monitor.git (SSH)

### Python 環境
- **Python 版本**: 3.14
- **依賴**: requests>=2.31.0
- **虛擬環境**: venv/

### 資料庫
- **格式**: SQLite
- **檔案**: tenders.db
- **當前資料**: 115 筆標案
- **Schema**: unit_id, job_number, brief, unit_name, budget, pk_pms_main, deadline, date_added, notified

---

## 🚨 注意事項

### 路徑相關
1. **所有腳本使用相對路徑** - 不需要修改程式碼
2. **必須在專案根目錄執行** - 否則會找不到檔案
3. **使用虛擬環境的 Python** - `./venv/bin/python`

### Bash 工具問題
- **目前狀態**: Bash 工具無法執行指令（所有指令返回 exit code 1）
- **解決方案**: 請在系統終端機手動執行測試指令
- **影響範圍**: 只影響 Claude Code 的 Bash 工具，不影響專案本身

### 資料庫管理
- **不進版控**: tenders.db 已在 .gitignore 中
- **已從 GitHub 移除**: 使用 `git rm --cached` 移除
- **本地保留**: 包含 115 筆歷史標案資料

---

## 🎯 下一步計畫

### 測試完成後
1. 確認所有功能正常運作
2. 記錄測試結果
3. 開始 Phase 2 實作

### Phase 2 優先順序
1. **Phase 2-1**: LINE Notify 整合（30-40 分鐘）
2. **Phase 2-2**: GitHub Actions 自動化（40-50 分鐘）
3. **Phase 2-3**: GitHub Pages 儀表板（1-1.5 小時）
4. **Phase 2-4**: Notion 整合 - 選用（1-1.5 小時）

---

## 📞 聯絡資訊

- **GitHub Repo**: https://github.com/Chuanyin1202/pcc-tender-monitor
- **API 來源**: https://pcc-api.openfun.app/api
- **政府採購網**: https://web.pcc.gov.tw

---

## ✅ 測試檢查清單

### monitor.py 測試
- [ ] 執行成功無錯誤
- [ ] 增量查詢邏輯正確
- [ ] 日誌正常輸出
- [ ] 資料庫正常更新
- [ ] 相對路徑正確

### query_tenders.py 測試
- [ ] 基本查詢成功
- [ ] 日期篩選正確
- [ ] 關鍵字搜尋正確
- [ ] 預算範圍篩選正確
- [ ] CSV 匯出成功
- [ ] 統計資訊正確

### 系統驗證
- [ ] logs/ 目錄自動建立
- [ ] 日誌輪轉功能正常
- [ ] 無路徑硬編碼問題
- [ ] Git 版控正確（無敏感檔案）

---

**交接完成。祝順利！** 🚀
