# 🎮 GameInfo System — 遊戲市場即時輿情追蹤系統

即時追蹤遊戲市場動態的 Bloomberg Terminal 風格儀表板。聚合 Steam、Twitch、台灣遊戲新聞、論壇討論聲量及手遊排行榜數據。

---

## 系統架構

```
gameinfo-system/
├── backend/                    # Python FastAPI 後端
│   ├── main.py                 # FastAPI 主程式 + API 路由
│   ├── scheduler.py            # APScheduler 定時排程 (10-30 min)
│   ├── requirements.txt        # Python 依賴
│   ├── .env                    # 環境變數 (API Keys)
│   ├── cache/                  # JSON 快取檔案
│   └── scrapers/               # 資料爬蟲模組
│       ├── steam_scraper.py    # Steam Web API 即時玩家數據
│       ├── twitch_scraper.py   # Twitch API 直播觀看數據
│       ├── news_scraper.py     # GNN/4Gamer/UDN RSS 新聞聚合
│       ├── discussion_scraper.py # 巴哈姆特/PTT/遊戲大亂鬥 聲量
│       └── mobile_scraper.py   # iOS/Android 手遊排行榜
├── frontend/                   # Vite + React 前端
│   ├── src/
│   │   ├── App.jsx             # 主面板 (3x2 Grid)
│   │   ├── index.css           # Bloomberg Dark 主題
│   │   └── components/
│   │       ├── Header.jsx      # Ticker + 時鐘
│   │       ├── SteamPanel.jsx  # Steam 熱門遊戲
│   │       ├── TwitchPanel.jsx # Twitch 直播熱度
│   │       ├── NewsPanel.jsx   # 即時新聞
│   │       ├── DiscussionPanel.jsx # 討論聲量
│   │       └── MobilePanel.jsx # 手遊排行榜
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── README.md
```

---

## 資料來源與更新頻率

| 模組 | 來源 | API/方式 | 更新間隔 | 狀態 |
|:---|:---|:---|:---:|:---:|
| **Steam 熱門** | Steam Web API | 免費 API ✅ | 10 分鐘 | ✅ 運作中 |
| **Twitch 直播** | Twitch Helix API | 免費 API（需 Key）| 10 分鐘 | ⚙️ 需設定 |
| **即時新聞** | 巴哈 GNN RSS / 4Gamer RSS / UDN | RSS + 爬蟲 | 10 分鐘 | ✅ 運作中 |
| **討論聲量** | 巴哈哈啦區 / PTT / 遊戲板 | HTML 爬蟲 | 10 分鐘 | ✅ 運作中 |
| **iOS 排行** | Apple Marketing Tools | JSON API ✅ | 30 分鐘 | ✅ 運作中 |
| **Android 排行** | Google Play Scraper | 套件 | 30 分鐘 | ⚙️ 需安裝 |

---

## 快速開始

### 1. 環境準備

- **Python** 3.10+
- **Node.js** 18+
- **npm** 9+

### 2. 後端設定

```bash
cd backend

# 安裝依賴
pip install -r requirements.txt

# 設定環境變數（複製範本後編輯）
cp .env.example .env
# 編輯 .env 填入:
#   TWITCH_CLIENT_ID=你的ID
#   TWITCH_CLIENT_SECRET=你的SECRET

# 啟動後端
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 前端設定

```bash
cd frontend

# 安裝依賴
npm install

# 啟動開發伺服器
npm run dev
# 前端預設在 http://localhost:5173
```

### 4. 開啟瀏覽器

前往 **http://localhost:5173** 即可看到儀表板。

---

## API 端點

| 端點 | 說明 | 回應格式 |
|:---|:---|:---|
| `GET /api/health` | 健康檢查 | `{"status": "ok"}` |
| `GET /api/steam/top-games` | Steam 前 20 熱門遊戲（即時在線人數）| `{data: [{name, appid, current_players}]}` |
| `GET /api/twitch/top-games` | Twitch 前 20 熱門遊戲（觀看人數）| `{data: [{name, viewer_count, box_art_url}]}` |
| `GET /api/news` | 遊戲即時新聞（GNN + 4Gamer + UDN）上限 50 則 | `{data: {news: [{title, url, source}], total_count}}` |
| `GET /api/discussions` | 論壇討論聲量（巴哈 + PTT + 遊戲板）| `{data: {bahamut, ptt, gameflier, total_count}}` |
| `GET /api/mobile/ios` | iOS App Store 排行 | `{data: {free: [...], grossing: [...]}}` |
| `GET /api/mobile/android` | Google Play 排行 | `{data: {free: [...], grossing: [...]}}` |

---

## 即時新聞管理策略

| 設定 | 值 | 說明 |
|:---|:---:|:---|
| 最大保留量 | **50 則** | 超過後自動移除最舊的 |
| 更新頻率 | 10 分鐘 | 每次抓取最新 → 去重 → 排序 → 裁切 |
| 來源分配建議 | GNN 20 + 4Gamer 20 + UDN 10 | 確保多元來源平衡 |

> **為何 50 則？** 在 Bloomberg 風格的面板中，50 則新聞約可呈現 48 小時內的重要新聞量，
> 既不會過多導致載入緩慢，也足以讓使用者瞭解近期動態。

---

## 環境變數

建立 `backend/.env` 檔案：

```env
# ── Twitch API（必填才能使用 Twitch 直播數據）──
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret

# ── 可選 ──
NEWS_MAX_COUNT=50
NEWS_UPDATE_INTERVAL=10
```

**Twitch 申請流程：**
1. 前往 https://dev.twitch.tv/console
2. 登入後建立新 Application
3. 取得 Client ID 和 Client Secret

---

## 開發路線圖

### ✅ Phase 1：核心功能（已完成）
- Steam 即時在線人數排行
- 遊戲即時新聞聚合（GNN + 4Gamer）
- PTT 討論聲量追蹤
- Bloomberg 風格前端儀表板

### ✅ Phase 2：擴展數據（已完成）
- 巴哈姆特哈啦區聲量
- iOS App Store 手遊排行
- Twitch 直播熱度整合
- 手遊排行面板（iOS/Android + 免費/暢銷）

### 🔜 Phase 3：進階功能（規劃中）
- [ ] Google Trends 搜尋趨勢整合
- [ ] NLP 情緒分析（正負面輿情）
- [ ] 歷史數據趨勢圖
- [ ] 自訂遊戲追蹤清單
- [ ] AI 預測遊戲熱度走勢
- [ ] 部署至 Vercel + Railway

---

## 技術堆疊

| 層級 | 技術 |
|:---|:---|
| 前端 | Vite 7 + React 19 |
| 後端 | Python FastAPI 0.115 |
| 爬蟲 | httpx + BeautifulSoup4 + feedparser |
| 排程 | APScheduler 3.10 |
| 快取 | JSON 檔案快取 |
| 字體 | Inter + JetBrains Mono |
| 主題 | Bloomberg Terminal Dark |

---

## License

MIT
