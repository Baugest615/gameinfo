"""
手遊排行榜模組 v5
- App Store (iOS) — iTunes RSS genre=6014 (Games)
- Google Play (Android) — gplay-scraper 套件 (台灣區遊戲類排行)
"""
import httpx
import json
import os
import time
import asyncio
from gplay_scraper import GPlayScraper

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "mobile_data.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

# 建立 GPlayScraper 單例
_gp = GPlayScraper()


async def fetch_ios_top_free(country="tw", limit=30):
    """App Store 免費遊戲排行 — 使用 iTunes RSS 的 Games genre (6014)"""
    # genre=6014 為 Games，直接只回傳遊戲
    url = f"https://itunes.apple.com/{country}/rss/topfreeapplications/limit={limit}/genre=6014/json"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()

        entries = data.get("feed", {}).get("entry", [])
        result = []

        for i, entry in enumerate(entries, 1):
            name = entry.get("im:name", {}).get("label", "")
            app_id_info = entry.get("id", {})
            app_id = ""
            app_url = ""

            # id 可能是 dict 或 string
            if isinstance(app_id_info, dict):
                app_url = app_id_info.get("label", "")
                attrs = app_id_info.get("attributes", {})
                app_id = attrs.get("im:id", "")
            else:
                app_url = str(app_id_info)

            # icon (取最大的)
            images = entry.get("im:image", [])
            icon = ""
            if images and isinstance(images, list):
                icon = images[-1].get("label", "") if isinstance(images[-1], dict) else str(images[-1])

            # genre
            genre_info = entry.get("category", {})
            genre = ""
            if isinstance(genre_info, dict):
                attrs = genre_info.get("attributes", {})
                genre = attrs.get("label", "")

            result.append({
                "rank": i,
                "name": name,
                "id": app_id,
                "url": app_url,
                "icon": icon,
                "genres": genre,
                "chart": "iOS Free",
            })

        return result

    except Exception as e:
        print(f"[Mobile] iOS top free error: {e}")
        return []


async def fetch_ios_top_grossing(country="tw", limit=30):
    """App Store 暢銷排行 — 台灣區不可用，回傳提示"""
    # Apple top-grossing API 對台灣區回傳 404
    return []


def _fetch_gp_chart(collection_name, count=30):
    """同步呼叫 gplay-scraper 取得指定排行榜（台灣區遊戲類）"""
    return _gp.list_analyze(
        collection=collection_name,
        category="GAME",
        count=count,
        lang="zh_TW",
        country="tw",
    )


def _format_gp_results(raw_results, chart_label, count=30):
    """將 gplay-scraper 回傳資料格式化為前端相容結構"""
    formatted = []
    for i, app in enumerate(raw_results[:count], 1):
        formatted.append({
            "rank": i,
            "name": app.get("title", ""),
            "id": app.get("appId", ""),
            "url": app.get("url", f"https://play.google.com/store/apps/details?id={app.get('appId', '')}"),
            "icon": app.get("icon", ""),
            "genres": app.get("genre", ""),
            "score": round(app.get("score", 0) or 0, 1),
            "installs": app.get("installs", ""),
            "developer": app.get("developer", ""),
            "chart": chart_label,
        })
    return formatted


async def fetch_android_top_games(count=30):
    """Google Play 台灣區遊戲排行 — 使用 gplay-scraper 套件"""
    try:
        # gplay-scraper 是同步套件，用 asyncio.to_thread 避免阻塞，加逾時防止掛起
        free_raw = await asyncio.wait_for(
            asyncio.to_thread(_fetch_gp_chart, "TOP_FREE", count), timeout=60
        )
        grossing_raw = await asyncio.wait_for(
            asyncio.to_thread(_fetch_gp_chart, "TOP_GROSSING", count), timeout=60
        )

        results = {
            "free": _format_gp_results(free_raw, "Android Free", count),
            "grossing": _format_gp_results(grossing_raw, "Android Grossing", count),
        }

        print(f"[Mobile] Android: {len(results['free'])} free, {len(results['grossing'])} grossing")
        return results

    except Exception as e:
        print(f"[Mobile] Android top games error: {e}")
        # 嘗試從快取讀取 Android 部分
        cached = _load_cache()
        return cached.get("android", {"free": [], "grossing": []})


async def fetch_all_mobile():
    """取得所有手遊排行數據"""
    try:
        ios_free = await fetch_ios_top_free()
        ios_grossing = await fetch_ios_top_grossing()
        android_data = await fetch_android_top_games()

        result = {
            "ios": {
                "free": ios_free,
                "grossing": ios_grossing,
            },
            "android": {
                "free": android_data.get("free", []),
                "grossing": android_data.get("grossing", []),
            },
            "updated_at": int(time.time()),
        }

        _save_cache(result)
        return result

    except Exception as e:
        print(f"[Mobile] Aggregate error: {e}")
        return _load_cache()


def _save_cache(data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"ios": {"free": [], "grossing": []}, "android": {"free": [], "grossing": []}}
