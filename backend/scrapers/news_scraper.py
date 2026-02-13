"""
即時新聞爬取模組
- 巴哈姆特 GNN RSS
- 4Gamers TW 網頁爬蟲
- UDN 遊戲角落 網頁爬蟲
"""
import feedparser
import httpx
from bs4 import BeautifulSoup
import json
import os
import time
import hashlib

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "news_data.json")
MAX_NEWS = 50
PER_SOURCE = 25  # 每來源最多抓取數量，3 來源 × 25 = 75，去重後可達 50

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}


def _news_hash(title, source):
    return hashlib.md5(f"{title}:{source}".encode()).hexdigest()


async def fetch_gnn_rss():
    """巴哈姆特 GNN 遊戲新聞 RSS"""
    url = "https://gnn.gamer.com.tw/rss.xml"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        news = []
        for entry in feed.entries[:PER_SOURCE]:
            news.append({
                "id": _news_hash(entry.get("title", ""), "GNN"),
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "summary": entry.get("summary", "")[:100],
                "source": "巴哈姆特 GNN",
                "source_icon": "🎮",
                "published_at": entry.get("published", ""),
                "fetched_at": int(time.time()),
            })
        return news
    except Exception as e:
        print(f"[News] GNN RSS error: {e}")
        return []


async def fetch_4gamers_tw():
    """4Gamers TW 台灣遊戲新聞"""
    url = "https://www.4gamers.com.tw/site/column/latest-news"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        news = []
        seen = set()

        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "/site/column/" not in href and "/site/news/" not in href:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5 or title in seen:
                continue
            seen.add(title)
            if not href.startswith("http"):
                href = f"https://www.4gamers.com.tw{href}"
            news.append({
                "id": _news_hash(title, "4Gamers TW"),
                "title": title,
                "url": href,
                "summary": "",
                "source": "4Gamers TW",
                "source_icon": "🕹️",
                "published_at": "",
                "fetched_at": int(time.time()),
            })
            if len(news) >= PER_SOURCE:
                break
        return news
    except Exception as e:
        print(f"[News] 4Gamers TW error: {e}")
        return []


async def fetch_udn_game():
    """UDN 遊戲角落"""
    url = "https://game.udn.com/game/index"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        news = []
        seen = set()

        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "game.udn.com/game/story" not in href:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5 or title in seen:
                continue
            seen.add(title)
            news.append({
                "id": _news_hash(title, "UDN"),
                "title": title,
                "url": href,
                "summary": "",
                "source": "UDN 遊戲角落",
                "source_icon": "📰",
                "published_at": "",
                "fetched_at": int(time.time()),
            })
            if len(news) >= PER_SOURCE:
                break
        return news
    except Exception as e:
        print(f"[News] UDN error: {e}")
        return []


async def aggregate_news():
    """聚合所有新聞來源"""
    gnn = await fetch_gnn_rss()
    four_gamers = await fetch_4gamers_tw()
    udn = await fetch_udn_game()

    all_news = gnn + four_gamers + udn

    seen_ids = set()
    unique_news = []
    for item in all_news:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique_news.append(item)

    unique_news.sort(key=lambda x: x.get("fetched_at", 0), reverse=True)
    unique_news = unique_news[:MAX_NEWS]

    result = {
        "news": unique_news,
        "total_count": len(unique_news),
        "max_count": MAX_NEWS,
        "updated_at": int(time.time()),
    }

    _save_cache(result)
    return result


def _save_cache(data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"news": [], "total_count": 0}
