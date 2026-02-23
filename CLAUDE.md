# GameInfo System — Claude 開發上下文

## 專案概述
遊戲市場即時輿情追蹤系統。追蹤 Steam 熱門遊戲、Twitch 中文直播熱度、台灣遊戲新聞、討論聲量、手遊排行、Google Trends 遊戲/二次元熱搜，並提供歷史趨勢圖。

## 架構

```
gameinfo-system/
├── backend/          # FastAPI + APScheduler（部署於 Zeabur）
│   ├── main.py       # 主入口、API 端點
│   ├── scheduler.py  # 背景排程（各來源更新頻率）
│   ├── database.py   # SQLite 歷史數據（aiosqlite）
│   ├── predictor.py  # AI 熱度預測（加權線性回歸 + 日週期調整）
│   ├── scrapers/
│   │   ├── steam_scraper.py      # Steam Web API（全球排行）
│   │   ├── twitch_scraper.py     # Twitch Helix API（language=zh 中文直播）
│   │   ├── news_scraper.py       # 台灣遊戲新聞（GNN RSS / 4Gamers TW / UDN）
│   │   ├── discussion_scraper.py # 巴哈姆特 / PTT / 遊戲大亂鬥
│   │   ├── mobile_scraper.py     # App Store / Google Play 手遊排行
│   │   └── gtrends_scraper.py    # Google Trends 台灣遊戲/二次元熱搜
│   ├── cache/        # JSON 快取（+ history.db SQLite）
│   ├── requirements.txt
│   └── .env          # 本地環境變數（不進 git）
└── frontend/         # React + Vite（部署於 Vercel）
    └── src/
        ├── App.jsx
        ├── components/
        │   ├── Header.jsx          # 頂部 ticker 跑馬燈
        │   ├── SteamPanel.jsx      # Steam 熱門遊戲
        │   ├── TwitchPanel.jsx     # Twitch 中文直播熱度
        │   ├── DiscussionPanel.jsx # 討論聲量
        │   ├── NewsPanel.jsx       # 即時新聞
        │   ├── MobilePanel.jsx        # 手遊排行
        │   ├── GoogleTrendsPanel.jsx # Google Trends 熱搜（Phase 4）
        │   └── TrendModal.jsx        # 歷史趨勢圖 Modal（Phase 3）
```

## 部署

| 服務 | 平台 | 說明 |
|------|------|------|
| Backend | Zeabur（亞洲節點）| 亞洲節點重要，Zeabur 才能存取巴哈姆特 |
| Frontend | Vercel | 自動 CI/CD |

## 環境變數

**Backend（Zeabur 設定 / backend/.env 本地）**
```
TWITCH_CLIENT_ID=       # Twitch API 憑證
TWITCH_CLIENT_SECRET=
FRONTEND_URL=           # Vercel 前端網址（CORS 白名單）
```

**Frontend（Vercel 環境變數 / frontend/.env.local 本地）**
```
VITE_API_BASE=          # Zeabur backend 完整網址（如 https://xxx.zeabur.app）
```

## API 端點

```
GET /api/steam/top-games          # Steam 全球熱門排行
GET /api/steam/player-count/{id}  # 特定遊戲即時人數
GET /api/twitch/top-games         # Twitch 中文直播排行
GET /api/discussions              # 巴哈/PTT/遊戲大亂鬥討論聲量
GET /api/news                     # 台灣遊戲新聞（最多 50 條）
GET /api/mobile/ios               # App Store 遊戲排行
GET /api/mobile/android           # Google Play 遊戲排行
GET /api/mobile/all               # iOS + Android 合併
GET /api/history/{source}/{id}?days=&forecast=  # 歷史趨勢 + AI 預測（source: steam|twitch，days: 1-30，forecast: true|false）
GET /api/google-trends               # Google Trends 台灣遊戲/二次元熱搜
GET /api/health                      # 健康檢查
```

## 排程頻率

```
Steam / 新聞：30 分鐘
Twitch：15 分鐘
巴哈/PTT 討論 / Google Trends：60 分鐘
手遊排行：180 分鐘
```

## Phase 功能狀態

- **Phase 1** ✅ Steam 熱門遊戲 / Twitch 直播 / 討論聲量
- **Phase 2** ✅ 台灣即時新聞 / 手遊排行（iOS + Android）
- **Phase 3** ✅ 歷史趨勢圖（Recharts LineChart）
- **Phase 4** ✅ Google Trends 台灣遊戲/二次元熱搜（取代追蹤清單）
- **Phase 5** ✅ AI 熱度預測（加權線性回歸 + 日週期調整）

## 已知限制

- Zeabur 重啟後 `history.db` 資料遺失（ephemeral filesystem），資料需重新累積
- Twitch `language=zh` 涵蓋台灣/香港中文直播主，並非純台灣
- Steam 無台灣地區 API，顯示全球排行
- PTT 爬蟲可能因網路限制不穩定（Zeabur 亞洲節點較佳）
- Google Trends 使用非官方 API，可能因 Google 反爬機制暫時失效（有 RSS fallback + 快取兜底）

## 開發慣例

- **push 前務必先詢問使用者確認**
- 本地開發：`cd backend && uvicorn main:app --reload` + `cd frontend && npm run dev`
- 前端 build：`cd frontend && npm run build`（使用 JSX 非 TSX，不需 tsc check）
- 快取檔案在 `backend/cache/`，不進 git（已在 .gitignore）

## 技術棧

- Backend: Python 3.13, FastAPI, APScheduler, httpx, BeautifulSoup4, feedparser, aiosqlite
- Frontend: React 18, Vite, Recharts
- 儲存：JSON 快取（即時資料）+ SQLite `history.db`（歷史趨勢）
