# GameInfo System 開發進度

## 2026-04-04

### 測試基礎建設 — DB snapshot + Scheduler resilience 測試套件（完成，待 review）

**動機**：專案零測試覆蓋。`database.py` 的 `save_snapshot` + `cleanup_old_data` 是歷史趨勢資料的命脈，`scheduler.py` 的 timeout 機制未經驗證。Railway 部署後如果 DB 或排程壞了完全無預警。

**改動檔案**：
- `backend/pytest.ini` — pytest 設定（asyncio_mode=auto）
- `backend/tests/conftest.py` — 共用 fixture，tmp_path + monkeypatch 隔離 DB
- `backend/tests/test_database.py` — 13 個測試覆蓋 init_db / save_snapshot / get_history / cleanup_old_data
- `backend/tests/test_scheduler.py` — 10 個測試覆蓋 _run_with_timeout / update_steam / update_twitch / cascade failure

**驗證結果**：23 tests passed（0.76s），使用 Python 3.12 + pytest-asyncio

**新增依賴**（僅開發用）：pytest, pytest-asyncio（未加入 requirements.txt，建議另建 requirements-dev.txt）

**Branch**: `night-shift/2026-04-03/測試基礎建設-DB-snapshot-Scheduler-resilience-測試套件`

**建議 review 方式**：
1. `cd backend && source .venv/bin/activate && python -m pytest -v` 確認全過
2. 看 `tests/test_database.py` 的邊界條件是否符合預期（90天清理、30天上限）
3. 看 `tests/test_scheduler.py` 的 mock 策略是否合理

---

## 2026-04-03

### source 參數 enum 驗證 + 手動刷新端點認證（完成）

**動機**：夜班自主掃描發現兩個安全/健壯性問題：
1. `/api/history/{source}/{game_id}` 的 `source` 是 `str`，無效值不回 422 而是靜默回空資料，前端無法區分「無資料」和「打錯參數」
2. `/api/weekly-digest/refresh` 是 POST 但無任何認證，任何人可觸發昂貴的外部 API 呼叫（Google News/YouTube/4Gamers/巴哈）

**方案**：
1. 定義 `SourceEnum(str, Enum)` 用於 path parameter，FastAPI 自動回 422 + 錯誤訊息
2. refresh 端點加 header-based auth（`X-Refresh-Token` 比對環境變數 `REFRESH_SECRET`）

**改動檔案**：
- `backend/main.py` — SourceEnum 定義 + history 端點型別改 + refresh 端點 auth
- `backend/.env.example` — 新增 REFRESH_SECRET 欄位

**部署注意**：需在 Railway 設定 `REFRESH_SECRET` 環境變數，否則 refresh 端點會拒絕所有請求

---

## 2026-03-30

### 三家 AI 審查 + 全面修復 + 遷移至 Railway

**起因**：用三個 AI 審查員（Backend / Frontend / Infra）平行檢視整個 codebase，共發現 25 個獨立問題。

**Backend 修復（7 項）**：
- Scheduler 從 `BackgroundScheduler` 改為 `AsyncIOScheduler`，共用 FastAPI 事件循環（解決記憶體壓力 + event loop 衝突）
- Twitch `_token_lock` 延遲初始化，避免跨 event loop 失效
- DB `save_snapshot` 與 `cleanup_old_data` 分離，清理改為每日凌晨 3 點排程
- 新增 `recorded_at` 索引，加速清理查詢
- Discussion 快取 fallback 補齊 `sentiment_summary` / `updated_at`
- Weekly digest 5 來源改為 `asyncio.gather` 並行（避免 timeout）
- 新聞時區統一為 UTC ISO 8601

**Frontend 修復（9 項）**：
- 所有面板 stale closure 修復（改用 functional state update）
- 所有 fetch 加 `resp.ok` 檢查
- SteamPanel 改用 App 傳入的共享資料，消除重複 API 請求
- Ticker 移除硬編碼上漲箭頭 + 加空資料提示
- TrendModal tooltip null guard
- MobilePanel rank nullish guard
- CSS `--border-subtle` → `--border-color`
- 移除重複 CSS import
- TrendModal onClose 用 `useCallback`

**Infra 修復 + 遷移（4 項）**：
- 根 Dockerfile Python 3.11 → 3.13
- `.env.example` 補上 `YOUTUBE_API_KEY`
- CORS `allow_headers` 改為 `["*"]`
- **遷移至 Railway Singapore**（asia-southeast1），前端 API_BASE 已更新

**部署狀態**：
- Backend: Railway Singapore `gameinfo-backend-production.up.railway.app`
- Frontend: Vercel `gameinfo-drab.vercel.app`（需手動 `vercel deploy --prod` 或 Dashboard 觸發，Vercel 環境變數 `VITE_API_BASE` 已更新指向 Railway）
- Volume: `/app/cache`（Railway persistent volume，SQLite + JSON 快取持久化）
- 環境變數: `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` / `YOUTUBE_API_KEY` / `FRONTEND_URL` 已設定
- 已驗證：Steam / Twitch / 巴哈 / PTT 文章 / 新聞 / 手遊排行 / 每周摘要 全部正常

**部署注意事項**：
- Vercel 的 `VITE_API_BASE` 環境變數會覆蓋 `.env.production`，修改 API URL 需同步更新 Vercel Dashboard
- Weekly digest init 排程 12 分鐘後執行，若短時間內多次部署可能需手動 `POST /api/weekly-digest/refresh`

**已知限制**：
- PTT hotboards 從 Singapore 偶爾被擋（個別版面文章正常）
- iOS Grossing = 0（Apple 不開放台灣區暢銷榜 RSS）

### 待辦
- 觀察 Railway 穩定性與費用
- 考慮是否關閉 Fly.io 舊部署

---

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
