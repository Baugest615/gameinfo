# GameInfo System 開發進度

## 2026-02-26

### 爬蟲優化：排程錯開 + 並行化 + Timeout 保護

**問題**：Fly.io 256MB shared-cpu backend 頻繁卡死，所有面板顯示 loading。

**根因**：
- 排程 job 接近同時執行，瞬間吃滿資源
- 各爬蟲內部序列執行，單次佔用時間長
- 無整體 timeout 保護，卡住的請求拖垮 process

**修改內容**：

| 檔案 | 優化項目 |
|------|----------|
| `scheduler.py` | 排程錯開首次執行（10s~10min）+ 各 job 獨立 timeout |
| `news_scraper.py` | GNN/4Gamers/UDN 三來源 `asyncio.gather` 並行 |
| `discussion_scraper.py` | 兩批並行（boards → articles）+ PTT 5 版面並行 |
| `steam_scraper.py` | 遊戲名稱查詢 `Semaphore(5)` + gather 並行 |
| `mobile_scraper.py` | GP timeout 60→30s + iOS/Android 並行 |

**效果**：
- 啟動資源峰值大幅降低（job 分散 0~10 分鐘）
- Discussion 執行時間 ~10-15s → ~4-6s
- News 執行時間 ~3-5s → ~1-2s
- 單一 job 最長佔用 120s（之前無上限）

### 其他修正

- 修正 `.env.production` API URL（Koyeb → Fly.io）
- 新增 `fly.toml` health check 自動重啟機制
