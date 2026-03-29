"""
GameInfo System — FastAPI 主入口
遊戲市場即時輿情追蹤系統 API Server
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 載入環境變數
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import Query
from scrapers import steam_scraper, twitch_scraper, discussion_scraper, news_scraper, mobile_scraper, weekly_digest_scraper
from scheduler import start_scheduler, stop_scheduler
import database
import predictor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動/關閉排程器"""
    await database.init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="🎮 GameInfo System API",
    description="遊戲市場即時輿情追蹤系統 — 即時新聞、Steam 數據、討論聲量、Twitch 直播、手遊排行",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 設定
_frontend_url = os.getenv("FRONTEND_URL", "")
_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://gameinfo-drab.vercel.app",
    "https://gameinfo-backend-production.up.railway.app",
]
if _frontend_url and _frontend_url not in _origins:
    _origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ============================================================
# Phase 1 端點：Steam / Twitch / 討論聲量
# ============================================================

@app.get("/api/steam/top-games", tags=["Steam"])
async def get_steam_top_games():
    """Steam 最熱門遊戲排行 + 同時在線人數"""
    games = await steam_scraper.fetch_top_games()
    return {"data": games, "source": "Steam Web API"}


@app.get("/api/steam/player-count/{appid}", tags=["Steam"])
async def get_steam_player_count(appid: int):
    """取得特定 Steam 遊戲的即時在線人數"""
    count = await steam_scraper.fetch_player_count(appid)
    return {"appid": appid, "player_count": count}


@app.get("/api/twitch/top-games", tags=["Twitch"])
async def get_twitch_top_games():
    """Twitch 最熱門遊戲直播排行"""
    games = await twitch_scraper.fetch_top_games()
    return {"data": games, "source": "Twitch Helix API"}


@app.get("/api/discussions", tags=["討論聲量"])
async def get_discussions():
    """巴哈姆特 + PTT + 遊戲大亂鬥 熱門話題聚合"""
    data = await discussion_scraper.fetch_all_discussions()
    return {"data": data, "source": "巴哈姆特/PTT/遊戲大亂鬥"}


# ============================================================
# Phase 2 端點：即時新聞 / 手遊排行
# ============================================================

@app.get("/api/news", tags=["即時新聞"])
async def get_news():
    """聚合遊戲新聞（巴哈GNN + 4Gamers + UDN 遊戲角落），上限 100 條"""
    data = await news_scraper.aggregate_news()
    return {"data": data, "source": "GNN/4Gamer/UDN"}


@app.get("/api/mobile/ios", tags=["手遊排行"])
async def get_mobile_ios():
    """App Store (iOS) 遊戲排行 — 免費 + 暢銷"""
    free = await mobile_scraper.fetch_ios_top_free()
    grossing = await mobile_scraper.fetch_ios_top_grossing()
    return {"data": {"free": free, "grossing": grossing}, "source": "Apple Marketing Tools"}


@app.get("/api/mobile/android", tags=["手遊排行"])
async def get_mobile_android():
    """Google Play 遊戲排行 — 直接爬取網頁解析"""
    data = await mobile_scraper.fetch_android_top_games()
    return {"data": data, "source": "Google Play"}


@app.get("/api/mobile/all", tags=["手遊排行"])
async def get_mobile_all():
    """iOS + Android 全部手遊排行"""
    data = await mobile_scraper.fetch_all_mobile()
    return {"data": data, "source": "App Store + Google Play"}


# ============================================================
# Phase 3 端點：歷史趨勢
# ============================================================

@app.get("/api/history/{source}/{game_id}", tags=["歷史趨勢"])
async def get_history(
    source: str,
    game_id: str,
    days: int = Query(default=7, ge=1, le=30),
    forecast: bool = Query(default=False),
):
    """取得遊戲歷史數據（source: steam | twitch，days: 1-30，forecast: 是否包含預測）"""
    if source not in ("steam", "twitch"):
        return {"data": [], "forecast": [], "game_id": game_id, "source": source}
    data = await database.get_history(source, game_id, days)
    forecast_data = []
    if forecast and len(data) >= 6:
        forecast_data = predictor.predict(data)
    return {"data": data, "forecast": forecast_data, "game_id": game_id, "source": source}



# ============================================================
# Phase 6 端點：每周遊戲行銷摘要
# ============================================================

@app.get("/api/weekly-digest", tags=["每周摘要"])
async def get_weekly_digest():
    """每周遊戲行銷摘要（廣告/活動/聯名），只讀快取（由排程更新）"""
    data = weekly_digest_scraper._load_cache()
    return {"data": data, "source": "Google News/4Gamers/YouTube/巴哈板"}


@app.post("/api/weekly-digest/refresh", tags=["每周摘要"])
async def refresh_weekly_digest():
    """手動觸發重新生成每周行銷摘要"""
    data = await weekly_digest_scraper.fetch_weekly_digest()
    return {"data": data, "source": "Google News/4Gamers/YouTube/巴哈板"}


# ============================================================
# 系統端點
# ============================================================

@app.get("/", tags=["系統"])
async def root():
    return {
        "name": "🎮 GameInfo System",
        "version": "1.0.0",
        "description": "遊戲市場即時輿情追蹤系統",
        "docs": "/docs",
        "endpoints": {
            "steam": "/api/steam/top-games",
            "twitch": "/api/twitch/top-games",
            "discussions": "/api/discussions",
            "news": "/api/news",
            "mobile_ios": "/api/mobile/ios",
            "mobile_android": "/api/mobile/android",
            "weekly_digest": "/api/weekly-digest",
        }
    }


@app.get("/api/health", tags=["系統"])
async def health_check():
    return {"status": "ok", "message": "GameInfo System is running"}
