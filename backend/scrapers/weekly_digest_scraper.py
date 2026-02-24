"""
每周遊戲行銷摘要模組
- 目標遊戲：Android 營收 Top 10 + 巴哈熱門版 Top 10（合併去重）
- 資料來源：4Gamers tag 搜尋 + YouTube Data API + 巴哈遊戲板公告
- 分類：📢 廣告/行銷 │ 🎉 活動 │ 🤝 聯名合作
- 時間範圍：過去 14 天（涵蓋進行中活動）
- 排程：每周一執行一次
"""
import httpx
from bs4 import BeautifulSoup
import json
import os
import sys
import time
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

TW_TZ = timezone(timedelta(hours=8))


def _log(msg: str):
    """Safe print for Windows cp950 terminal"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"))


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "weekly_digest.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}

# ── 分類關鍵字 ──
EVENT_KEYWORDS = [
    "活動", "限定", "開跑", "登場", "開放", "更新", "改版", "版本", "賽季",
    "節慶", "周年", "春節", "過年", "新年", "維護", "公告", "獎勵", "儲值",
    "轉蛋", "抽獎", "免費", "贈送",
]
COLLAB_KEYWORDS = ["合作", "聯名", "聯動", "跨界", "x ", "×", "攜手", "授權"]
AD_KEYWORDS = [
    "廣告", "代言", "大使", "宣傳", "PV", "CM", "預告", "trailer",
    "MV", "形象", "品牌", "官方", "主題曲",
]

# ── 4Gamers tag 名稱對照表 ──
TAG_ALIASES = {
    "勝利女神：妮姬": ["NIKKE", "勝利女神"],
    "崩壞：星穹鐵道": ["星穹鐵道", "崩壞星穹鐵道"],
    "蔚藍檔案 Blue Archive": ["蔚藍檔案", "Blue Archive"],
    "Fate/Grand Order": ["FGO", "Fate"],
    "哈利波特：魔法覺醒": ["哈利波特"],
    "明日方舟：終末地": ["明日方舟", "Arknights"],
    "傳說對決": ["AOV", "Arena of Valor"],
    "天堂W": ["天堂", "Lineage"],
    "原神": ["Genshin", "Genshin Impact"],
}


def _classify_item(title: str, summary: str = "") -> list[str]:
    """根據標題和摘要分類消息類型"""
    text = f"{title} {summary}".lower()
    tags = []
    if any(kw in text for kw in AD_KEYWORDS):
        tags.append("ad")
    if any(kw in text for kw in COLLAB_KEYWORDS):
        tags.append("collab")
    if any(kw in text for kw in EVENT_KEYWORDS):
        tags.append("event")
    if not tags:
        tags.append("news")
    return tags


def _get_search_range():
    """取得搜尋時間範圍：過去 14 天（涵蓋進行中的活動）"""
    now = datetime.now(TW_TZ)
    start = now - timedelta(days=14)
    return start, now


async def _get_target_games() -> list[dict]:
    """
    從現有快取取得目標遊戲清單：
    - Android 營收 Top 10
    - 巴哈姆特熱門版 Top 10（含 bsn）
    合併去重後回傳
    """
    games = []
    seen_names = set()

    # 1. Android 營收 Top 10
    mobile_cache = os.path.join(CACHE_DIR, "mobile_data.json")
    try:
        with open(mobile_cache, "r", encoding="utf-8") as f:
            mobile_data = json.load(f)
        android_grossing = mobile_data.get("android", {}).get("grossing", [])
        for item in android_grossing[:10]:
            name = item.get("name", "").strip()
            if name and name not in seen_names:
                seen_names.add(name)
                games.append({
                    "name": name,
                    "source": "android_grossing",
                    "rank": item.get("rank", 0),
                    "bsn": None,
                })
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        _log("[WeeklyDigest] Mobile cache not found, skipping Android")

    # 2. 巴哈姆特熱門版 Top 10（含 bsn）
    discussion_cache = os.path.join(CACHE_DIR, "discussion_data.json")
    try:
        with open(discussion_cache, "r", encoding="utf-8") as f:
            disc_data = json.load(f)
        bahamut_boards = disc_data.get("bahamut_boards", [])

        # 建立 bsn 對照表，也嘗試幫 Android 遊戲補上 bsn
        bsn_map = {b.get("name", ""): b.get("bsn", "") for b in bahamut_boards}

        for item in bahamut_boards[:10]:
            name = item.get("name", "").strip()
            if name and name not in seen_names:
                seen_names.add(name)
                games.append({
                    "name": name,
                    "source": "bahamut_hot",
                    "rank": item.get("rank", 0),
                    "bsn": item.get("bsn"),
                })

        # 幫已有的 Android 遊戲補 bsn（名稱模糊匹配）
        for game in games:
            if game["bsn"] is None:
                for board_name, bsn in bsn_map.items():
                    if game["name"] in board_name or board_name in game["name"]:
                        game["bsn"] = bsn
                        break
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        _log("[WeeklyDigest] Discussion cache not found, skipping Bahamut")

    _log(f"[WeeklyDigest] Target games: {len(games)} "
         f"({len([g for g in games if g['source'] == 'android_grossing'])} Android + "
         f"{len([g for g in games if g['source'] == 'bahamut_hot'])} Bahamut)")
    return games


def _get_tag_variants(game_name: str) -> list[str]:
    """取得遊戲名稱的所有可能 tag 變體"""
    variants = [game_name]
    for canonical, aliases in TAG_ALIASES.items():
        if game_name == canonical or game_name in aliases:
            variants = [canonical] + aliases
            break
    return list(set(variants))


# ============================================================
# 來源 1: 4Gamers tag 搜尋
# ============================================================
async def _search_4gamers(client: httpx.AsyncClient, game_name: str, since: datetime) -> list[dict]:
    """搜尋 4Gamers 特定遊戲的近期新聞"""
    items = []
    variants = _get_tag_variants(game_name)

    for tag in variants:
        encoded = urllib.parse.quote(tag)
        url = f"https://www.4gamers.com.tw/site/api/news/by-tag?tag={encoded}&pageSize=20"
        try:
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code != 200 or "json" not in resp.headers.get("content-type", ""):
                continue
            data = resp.json()
            items = data.get("data", {}).get("results", [])
            if items:
                break
        except Exception:
            continue
    else:
        return []

    since_ts = int(since.timestamp() * 1000)
    results = []
    for item in items:
        ts = item.get("createPublishedAt", 0)
        if ts < since_ts:
            continue
        title = item.get("title", "")
        intro = item.get("intro", "") or ""
        results.append({
            "title": title,
            "url": item.get("canonicalUrl", ""),
            "summary": intro[:120],
            "source": "4Gamers",
            "published_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts / 1000)),
            "tags": _classify_item(title, intro),
        })

    return results


# ============================================================
# 來源 2: YouTube Data API — 官方影音/廣告/PV
# ============================================================
async def _search_youtube(client: httpx.AsyncClient, game_name: str, since: datetime) -> list[dict]:
    """搜尋 YouTube 上的遊戲官方影音/廣告"""
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        return []

    results = []
    queries = [
        f"{game_name} 官方",
        f"{game_name} 廣告 PV trailer",
    ]
    published_after = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    for q in queries:
        try:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": q,
                    "type": "video",
                    "publishedAfter": published_after,
                    "regionCode": "TW",
                    "relevanceLanguage": "zh-Hant",
                    "maxResults": 5,
                    "order": "date",
                    "key": api_key,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                _log(f"[WeeklyDigest] YouTube API error {resp.status_code} for '{q}'")
                continue
            data = resp.json()

            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                title = snippet.get("title", "")
                channel = snippet.get("channelTitle", "")
                video_id = item.get("id", {}).get("videoId", "")
                published = snippet.get("publishedAt", "")

                # 排除純實況/攻略
                skip_words = ["實況", "直播", "攻略", "教學", "開箱", "gameplay", "walkthrough", "let's play"]
                if any(sw in title.lower() for sw in skip_words):
                    continue

                results.append({
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "summary": f"頻道：{channel}",
                    "source": "YouTube",
                    "published_at": published[:19] if published else "",
                    "tags": _classify_item(title),
                    "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                })
        except Exception as e:
            _log(f"[WeeklyDigest] YouTube search error: {e}")

    # 去重
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return unique


# ============================================================
# 來源 3: 巴哈姆特遊戲板 — 活動/公告/官方貼文
# ============================================================
async def _search_bahamut_board(client: httpx.AsyncClient, bsn: str, game_name: str) -> list[dict]:
    """搜尋巴哈姆特遊戲板上的活動/公告/官方相關貼文"""
    if not bsn:
        return []

    url = f"https://forum.gamer.com.tw/B.php?bsn={bsn}"
    try:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        seen_titles = set()

        # 活動/公告相關關鍵字
        board_event_kws = [
            "活動", "公告", "官方", "更新", "維護", "聯名", "合作", "限定",
            "開跑", "獎勵", "免費", "贈送", "預告", "新版", "改版", "賽事",
        ]

        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "C.php?bsn=" not in href:
                continue

            title = a.get_text(strip=True)
            if not title or len(title) < 5 or title in seen_titles:
                continue

            # 篩選活動/公告相關
            if not any(kw in title for kw in board_event_kws):
                continue

            seen_titles.add(title)
            if not href.startswith("http"):
                href = f"https://forum.gamer.com.tw/{href}"

            results.append({
                "title": title,
                "url": href,
                "summary": f"巴哈 {game_name} 板",
                "source": "巴哈討論板",
                "published_at": "",  # 巴哈板文時間較難取得
                "tags": _classify_item(title),
            })

            if len(results) >= 10:
                break

        return results
    except Exception as e:
        _log(f"[WeeklyDigest] Bahamut board error for bsn={bsn}: {e}")
        return []


# ============================================================
# 主函式
# ============================================================
async def fetch_weekly_digest() -> dict:
    """主函式：產生每周遊戲行銷摘要"""
    start_time, now = _get_search_range()
    games = await _get_target_games()

    if not games:
        _log("[WeeklyDigest] No target games found, returning cache")
        return _load_cache()

    digest = []

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for game in games:
            name = game["name"]
            bsn = game.get("bsn")
            _log(f"[WeeklyDigest] Searching: {name} (bsn={bsn})")

            # 來源 1: 4Gamers tag 搜尋
            fgamers_items = await _search_4gamers(client, name, start_time)

            # 來源 2: YouTube 官方影音
            yt_items = await _search_youtube(client, name, start_time)

            # 來源 3: 巴哈遊戲板活動公告
            baha_items = await _search_bahamut_board(client, bsn, name)

            all_items = fgamers_items + yt_items + baha_items

            if not all_items:
                continue

            # 跨來源去重（用標題相似度）
            all_items = _dedup_items(all_items)

            # 按發佈時間排序（無時間的排最後）
            all_items.sort(key=lambda x: x.get("published_at") or "0000", reverse=True)

            # 分類統計
            tag_counts = {"ad": 0, "collab": 0, "event": 0, "news": 0}
            for item in all_items:
                for t in item.get("tags", []):
                    tag_counts[t] = tag_counts.get(t, 0) + 1

            digest.append({
                "game": name,
                "source": game["source"],
                "rank": game["rank"],
                "items": all_items,
                "item_count": len(all_items),
                "tag_counts": tag_counts,
                "sources_used": {
                    "4gamers": len(fgamers_items),
                    "youtube": len(yt_items),
                    "bahamut": len(baha_items),
                },
            })

    # 按消息數量排序（行銷活躍度高的排前面）
    digest.sort(key=lambda x: x["item_count"], reverse=True)

    result = {
        "digest": digest,
        "game_count": len(digest),
        "total_items": sum(g["item_count"] for g in digest),
        "period": {
            "start": start_time.strftime("%Y-%m-%d"),
            "end": now.strftime("%Y-%m-%d"),
        },
        "updated_at": int(time.time()),
    }

    _save_cache(result)
    _log(f"[WeeklyDigest] Done — {len(digest)} games, {result['total_items']} total items")
    return result


def _dedup_items(items: list[dict]) -> list[dict]:
    """跨來源去重：相同標題（前 20 字）視為重複"""
    seen = set()
    unique = []
    for item in items:
        key = item.get("title", "")[:20]
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _save_cache(data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"digest": [], "game_count": 0, "total_items": 0}
