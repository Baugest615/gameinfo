"""
即時新聞爬取模組
- 巴哈姆特 GNN RSS
- 4Gamers TW 網頁爬蟲
- UDN 遊戲角落 網頁爬蟲
"""
import asyncio
import feedparser
import httpx
import json
import os
import time
import hashlib
from email.utils import parsedate_to_datetime

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "news_data.json")
MAX_NEWS = 100
PER_SOURCE = 35  # 每來源最多抓取數量，3 來源 × 35 = 105，去重後可達 100

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
            # 將 RSS 日期格式轉為 ISO 8601
            pub_raw = entry.get("published", "")
            pub_iso = ""
            if pub_raw:
                try:
                    pub_iso = parsedate_to_datetime(pub_raw).strftime("%Y-%m-%dT%H:%M:%S")
                except Exception:
                    pub_iso = pub_raw
            news.append({
                "id": _news_hash(entry.get("title", ""), "GNN"),
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "summary": entry.get("summary", "")[:100],
                "source": "巴哈姆特 GNN",
                "source_icon": "🎮",
                "published_at": pub_iso,
                "fetched_at": int(time.time()),
            })
        return news
    except Exception as e:
        print(f"[News] GNN RSS error: {e}")
        return []


async def fetch_4gamers_tw():
    """4Gamers TW 台灣遊戲新聞（JSON API）"""
    url = f"https://www.4gamers.com.tw/site/api/news/latest?pageSize={PER_SOURCE}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
        data = resp.json()
        results = data.get("data", {}).get("results", [])
        news = []
        for item in results:
            title = item.get("title", "")
            if not title or len(title) < 5:
                continue
            published_at = ""
            ts = item.get("createPublishedAt")
            if ts:
                published_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts / 1000))
            news.append({
                "id": _news_hash(title, "4Gamers TW"),
                "title": title,
                "url": item.get("canonicalUrl", ""),
                "summary": (item.get("intro") or "")[:100],
                "source": "4Gamers TW",
                "source_icon": "🕹️",
                "published_at": published_at,
                "fetched_at": int(time.time()),
            })
        return news
    except Exception as e:
        print(f"[News] 4Gamers TW error: {e}")
        return []


async def fetch_udn_game():
    """UDN 遊戲角落 RSS"""
    url = "https://game.udn.com/game/rssfeed"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        news = []
        for entry in feed.entries[:PER_SOURCE]:
            title = entry.get("title", "")
            if not title or len(title) < 5:
                continue
            pub_raw = entry.get("published", "")
            pub_iso = ""
            if pub_raw:
                try:
                    pub_iso = parsedate_to_datetime(pub_raw).strftime("%Y-%m-%dT%H:%M:%S")
                except Exception:
                    pub_iso = pub_raw
            news.append({
                "id": _news_hash(title, "UDN"),
                "title": title,
                "url": entry.get("link", ""),
                "summary": (entry.get("summary", "") or "")[:100],
                "source": "UDN 遊戲角落",
                "source_icon": "📰",
                "published_at": pub_iso,
                "fetched_at": int(time.time()),
            })
        return news
    except Exception as e:
        print(f"[News] UDN error: {e}")
        return []


async def aggregate_news():
    """聚合所有新聞來源（三來源並行）"""
    results = await asyncio.gather(
        fetch_gnn_rss(),
        fetch_4gamers_tw(),
        fetch_udn_game(),
        return_exceptions=True,
    )

    all_news = []
    source_names = ["GNN", "4Gamers", "UDN"]
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"[News] {source_names[i]} gather error: {r}")
        elif isinstance(r, list):
            all_news.extend(r)

    seen_ids = set()
    unique_news = []
    for item in all_news:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique_news.append(item)

    unique_news.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    unique_news = unique_news[:MAX_NEWS]

    source_counts = {}
    for item in unique_news:
        src = item.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    result = {
        "news": unique_news,
        "total_count": len(unique_news),
        "max_count": MAX_NEWS,
        "source_counts": source_counts,
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
