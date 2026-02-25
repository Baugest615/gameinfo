# GameInfo System — Claude 開發上下文

## 專案概述
遊戲市場即時輿情追蹤系統。追蹤 Steam 熱門遊戲、Twitch 中文直播熱度、台灣遊戲新聞、討論聲量、手遊排行、每周行銷摘要，並提供歷史趨勢圖。

## 架構

- `backend/` — FastAPI + APScheduler，爬蟲邏輯在 `scrapers/`，API 端點在 `main.py`
- `frontend/` — React 19 + Vite，各面板元件在 `src/components/`
- 儲存：JSON 快取（即時資料）+ SQLite `history.db`（歷史趨勢）

## 部署

| 服務 | 平台 | 說明 |
|------|------|------|
| Backend | Fly.io（nrt 東京節點）| 亞洲節點重要，才能存取巴哈姆特。Volume mount `/app/cache` 持久化快取與 history.db |
| Frontend | Vercel | 自動 CI/CD |

部署指令：`cd backend && fly deploy`

## 環境變數

**Backend（Fly.io secrets / `backend/.env` 本地）**
```
TWITCH_CLIENT_ID=       # Twitch API 憑證
TWITCH_CLIENT_SECRET=
YOUTUBE_API_KEY=        # YouTube Data API v3（每周摘要用）
FRONTEND_URL=           # Vercel 前端網址（CORS 白名單）
```

**Frontend（Vercel / `frontend/.env.local` 本地）**
```
VITE_API_BASE=          # Fly.io backend 完整網址
```

## 已知限制

- Twitch `language=zh` 涵蓋台灣/香港中文直播主，並非純台灣
- Steam 無台灣地區 API，顯示全球排行
- PTT 爬蟲可能因網路限制不穩定（亞洲節點較佳）
- YouTube Data API 每日 10,000 單位配額（search.list = 100 單位/次），每周摘要約消耗 4,000 單位

## 開發慣例

- 本地開發：`cd backend && uvicorn main:app --reload` + `cd frontend && npm run dev`
- 前端 build：`cd frontend && npm run build`（JSX，不需 tsc check）
- `backend/cache/` 不進 git（已在 .gitignore）

## 技術棧

- Backend: Python 3.13, FastAPI, APScheduler, httpx, BeautifulSoup4, feedparser, aiosqlite
- Frontend: React 19, Vite, Recharts
