"""
Google Trends 台灣遊戲/二次元熱搜模組
- Primary: Daily Trending Searches API (geo=TW)
- Supplementary: Realtime Trending Searches API (cat=e Entertainment)
- Fallback: Google Trends RSS feed
- 關鍵字分類：遊戲 (Gaming) / 二次元 (Anime)
"""
import httpx
import json
import os
import time
import re
import random
import feedparser

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "gtrends_data.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "application/json, text/plain, */*",
}

# --- 關鍵字分類 ---

GAMING_KEYWORDS = {
    # English
    "steam", "ps5", "ps4", "playstation", "xbox", "nintendo", "switch",
    "game", "gamer", "gaming", "esport", "esports",
    "valorant", "lol", "league of legends", "fortnite", "minecraft",
    "genshin", "zelda", "mario", "pokemon", "palworld", "elden ring",
    "apex", "overwatch", "diablo", "final fantasy", "monster hunter",
    "pubg", "cod", "call of duty", "gta", "cyberpunk", "baldur",
    "roblox", "among us", "dota",
    # Chinese
    "遊戲", "電玩", "手遊", "實況", "電競", "抽卡", "課金", "開服",
    "原神", "崩壞", "星穹鐵道", "絕區零", "鳴潮", "寶可夢",
    "薩爾達", "瑪利歐", "魔物獵人", "艾爾登法環", "暗黑破壞神",
    "英雄聯盟", "特戰英豪", "要塞英雄", "當個創世神",
    "太空戰士", "勇者鬥惡龍", "世紀帝國",
    "傳說對決", "荒野亂鬥", "部落衝突",
}

ANIME_KEYWORDS = {
    # English
    "anime", "manga", "vtuber", "hololive", "cosplay", "isekai",
    "naruto", "one piece", "dragon ball", "attack on titan",
    "jujutsu", "demon slayer", "spy x family", "chainsaw man",
    "my hero academia", "hunter x hunter", "bleach",
    "frieren", "oshi no ko", "solo leveling",
    # Chinese
    "動漫", "動畫", "漫畫", "二次元", "聲優", "新番", "番劇", "輕小說",
    "鬼滅", "鬼滅之刃", "進擊的巨人", "咒術迴戰", "海賊王", "航海王",
    "我推的孩子", "葬送的芙莉蓮", "排球少年", "間諜家家酒",
    "刀劍神域", "輝夜姬", "鏈鋸人", "七龍珠", "火影忍者",
    "吉卜力", "新海誠", "柯南", "名偵探柯南",
    "v圈", "虛擬偶像", "coser", "同人",
    "我獨自升級", "藍色監獄", "異世界",
}


def _classify(title: str, related: list[str] | None = None) -> dict:
    """根據關鍵字判斷趨勢屬於 gaming / anime / both / neither"""
    text = title.lower()
    if related:
        text += " " + " ".join(r.lower() for r in related)

    is_gaming = any(kw in text for kw in GAMING_KEYWORDS)
    is_anime = any(kw in text for kw in ANIME_KEYWORDS)
    return {"gaming": is_gaming, "anime": is_anime}


def _strip_xssi(text: str) -> str:
    """移除 Google API response 的 XSSI prefix"""
    if text.startswith(")]}'"):
        text = text[text.index("\n") + 1:]
    return text


def _save_cache(data: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_cache() -> dict:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


async def _fetch_daily_trends() -> list[dict]:
    """抓取 Google Trends Daily Trending Searches (TW)"""
    url = "https://trends.google.com/trends/api/dailytrends"
    params = {"hl": "zh-TW", "tz": "-480", "geo": "TW", "ns": "15"}

    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()

    raw = _strip_xssi(resp.text)
    data = json.loads(raw)

    results = []
    for day in data.get("default", {}).get("trendingSearchesDays", []):
        for item in day.get("trendingSearches", []):
            title_obj = item.get("title", {})
            query = title_obj.get("query", "")
            if not query:
                continue

            traffic = item.get("formattedTraffic", "")
            image_url = item.get("image", {}).get("imageUrl", "")
            related = [q.get("query", "") for q in item.get("relatedQueries", []) if q.get("query")]

            articles = []
            for art in item.get("articles", [])[:2]:
                articles.append({
                    "title": art.get("title", ""),
                    "url": art.get("url", ""),
                    "source": art.get("source", ""),
                })

            cats = _classify(query, related)
            results.append({
                "title": query,
                "traffic": traffic,
                "image_url": image_url,
                "related": related[:3],
                "articles": articles,
                "source": "daily",
                "categories": cats,
            })

    print(f"[GTrends] Daily: {len(results)} trends fetched")
    return results


async def _fetch_realtime_trends() -> list[dict]:
    """抓取 Google Trends Realtime Trending Searches (TW, Entertainment)"""
    url = "https://trends.google.com/trends/api/realtimetrends"
    params = {
        "hl": "zh-TW", "tz": "-480", "geo": "TW",
        "cat": "e",  # Entertainment
        "fi": "0", "fs": "0", "ri": "300", "rs": "20", "sort": "0",
    }

    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()

    raw = _strip_xssi(resp.text)
    data = json.loads(raw)

    results = []
    for story in data.get("storySummaries", {}).get("trendingStories", []):
        title = story.get("title", "")
        if not title:
            # 嘗試從 entityNames 取
            entities = story.get("entityNames", [])
            title = entities[0] if entities else ""
        if not title:
            continue

        image_url = story.get("image", {}).get("imageUrl", "")
        related = story.get("entityNames", [])[:3]

        articles = []
        for art in story.get("articles", [])[:2]:
            articles.append({
                "title": art.get("articleTitle", ""),
                "url": art.get("url", ""),
                "source": art.get("source", ""),
            })

        cats = _classify(title, related)
        results.append({
            "title": title,
            "traffic": "",
            "image_url": image_url,
            "related": related,
            "articles": articles,
            "source": "realtime",
            "categories": cats,
        })

    print(f"[GTrends] Realtime: {len(results)} trends fetched")
    return results


async def _fetch_rss_fallback() -> list[dict]:
    """RSS fallback — 當 API 端點不可用時使用"""
    url = "https://trends.google.com/trending/rss?geo=TW"

    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    results = []
    for entry in feed.entries[:30]:
        title = entry.get("title", "")
        if not title:
            continue
        traffic = entry.get("ht_approx_traffic", "")
        cats = _classify(title)
        results.append({
            "title": title,
            "traffic": traffic,
            "image_url": "",
            "related": [],
            "articles": [],
            "source": "rss",
            "categories": cats,
        })

    print(f"[GTrends] RSS fallback: {len(results)} trends fetched")
    return results


async def fetch_google_trends() -> dict:
    """
    主函式：抓取並分類 Google Trends 台灣熱搜
    回傳 {"gaming": [...], "anime": [...], "updated_at": ...}
    """
    all_items = []

    # 1) Primary: Daily Trends
    try:
        daily = await _fetch_daily_trends()
        all_items.extend(daily)
    except Exception as e:
        print(f"[GTrends] Daily trends error: {e}")

    # 小延遲避免觸發 rate limit
    await _async_sleep(random.uniform(1, 3))

    # 2) Supplementary: Realtime Trends
    try:
        realtime = await _fetch_realtime_trends()
        all_items.extend(realtime)
    except Exception as e:
        print(f"[GTrends] Realtime trends error: {e}")

    # 3) 如果都失敗，用 RSS fallback
    if not all_items:
        try:
            rss = await _fetch_rss_fallback()
            all_items.extend(rss)
        except Exception as e:
            print(f"[GTrends] RSS fallback error: {e}")

    # 4) 全部失敗 → 回傳 cache
    if not all_items:
        print("[GTrends] All sources failed, returning cache")
        return _load_cache()

    # 去重（以 title 為 key）
    seen = set()
    unique = []
    for item in all_items:
        key = item["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # 分類
    gaming = [item for item in unique if item["categories"]["gaming"]]
    anime = [item for item in unique if item["categories"]["anime"]]

    result = {
        "gaming": gaming,
        "anime": anime,
        "total_count": len(unique),
        "updated_at": int(time.time()),
    }

    _save_cache(result)
    print(f"[GTrends] Done — gaming: {len(gaming)}, anime: {len(anime)}, total: {len(unique)}")
    return result


async def _async_sleep(seconds: float):
    """非阻塞 sleep"""
    import asyncio
    await asyncio.sleep(seconds)
