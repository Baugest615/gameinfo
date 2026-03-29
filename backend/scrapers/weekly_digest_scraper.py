"""
每周遊戲行銷摘要模組
- 目標遊戲：Android 營收 Top 10 + 巴哈熱門版 Top 10（合併去重）
- 資料來源：Google News RSS + 4Gamers tag + YouTube Data API + 巴哈遊戲板公告
- 分類：📢 廣告/行銷 │ 🎉 活動 │ 🤝 聯名合作
- 時間範圍：過去 14 天（涵蓋進行中活動）
- 排程：每周一執行一次
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from collections import Counter
import feedparser
import json
import os
import sys
import time
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

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

# ── 行銷分類關鍵字（僅行銷/推廣活動，排除營運公告/版更等）──
EVENT_KEYWORDS = [
    "活動", "限定", "開跑", "登場", "開放", "賽季",
    "節慶", "周年", "週年", "春節", "過年", "新年", "獎勵", "儲值",
    "轉蛋", "抽獎", "免費", "贈送", "造型", "禮包",
]
COLLAB_KEYWORDS = ["合作", "聯名", "聯動", "連動", "跨界", "x ", "×", "攜手", "授權"]
AD_KEYWORDS = [
    "廣告", "代言", "大使", "宣傳", "PV", "CM", "預告", "trailer",
    "MV", "形象", "品牌", "主題曲", "贊助", "推廣", "KOL",
]

# ── 非遊戲黑名單（巴哈姆特熱門版中的非遊戲板）──
BOARD_BLACKLIST = [
    "電腦應用綜合討論", "場外休憩區", "哈啦板務", "動漫戲劇綜合",
    "智慧型手機", "電腦硬體", "模型公仔", "生活娛樂",
]

# ── 博弈/非遊戲 App 關鍵字過濾 ──
GAME_NAME_BLACKLIST_KW = ["娛樂城", "麻將", "老虎機", "刮刮樂", "博弈", "棋牌"]

# ── 遊戲名稱清理：去前綴/副標題，取核心名稱 ──
NAME_PREFIXES = ["Garena ", "SEGA ", "miHoYo ", "Netmarble "]

def _clean_game_name(raw_name: str) -> str:
    """清理遊戲名稱：去掉發行商前綴和副標題"""
    name = raw_name.strip()
    # 去掉發行商前綴
    for prefix in NAME_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    # 去掉副標題（：或 - 後的描述性文字）
    for sep in ["：", " - ", "—"]:
        if sep in name:
            base = name.split(sep)[0].strip()
            # 保留有意義的短名（至少 2 字）
            if len(base) >= 2:
                name = base
                break
    return name

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
    "神魔之塔": ["Tower of Saviors"],
    "天堂M": ["Lineage M", "天堂 Mobile"],
    "RO仙境傳説": ["仙境傳說", "RO"],
    "貓咪大戰爭": ["Battle Cats"],
    "星城Online": ["星城"],
}

# ── 常見手遊 BSN 對照（補巴哈熱門版未涵蓋的遊戲）──
KNOWN_BSN = {
    "傳說對決": "30518",
    "天堂M": "25908",
    "寒霜啟示錄": "76999",
    "Kingshot": "82382",
    "RO仙境傳説": "28924",
    "最後的戰爭": "79869",
    "貓咪大戰爭": "23772",
    "神魔之塔": "23805",
    "原神": "36730",
    "崩壞：星穹鐵道": "75165",
    "勝利女神：妮姬": "74498",
    "明日方舟：終末地": "74604",
    "蔚藍檔案 Blue Archive": "73498",
}


async def _search_bsn(client: httpx.AsyncClient, game_name: str) -> str | None:
    """自動搜尋巴哈姆特遊戲板 BSN：ACG 搜尋 + 板頁標題驗證"""
    encoded = urllib.parse.quote(game_name)
    try:
        resp = await client.get(
            f"https://acg.gamer.com.tw/search.php?s=3&kw={encoded}",
            timeout=15,
        )
        if resp.status_code != 200:
            return None
    except Exception:
        return None

    bsn_list = re.findall(r'(?:G2|C|B)\.php\?bsn=0*(\d+)', resp.text)
    counter = Counter(bsn_list)
    candidates = [bsn for bsn, _ in counter.most_common(5)]
    if not candidates:
        return None

    # 產生所有可能的匹配名稱（含 TAG_ALIASES 變體 + CJK base）
    match_names = {game_name.lower()}
    for canonical, aliases in TAG_ALIASES.items():
        all_names = [canonical] + aliases
        if any(n in game_name or game_name in n for n in all_names):
            for n in all_names:
                match_names.add(n.lower())
            break
    cjk_base = re.sub(r'[^\u4e00-\u9fff]', '', game_name)
    if len(cjk_base) >= 2:
        match_names.add(cjk_base)

    # 逐一驗證候選 BSN：板頁標題/描述必須包含遊戲名稱
    for bsn in candidates:
        try:
            resp2 = await client.get(
                f"https://forum.gamer.com.tw/B.php?bsn={bsn}",
                timeout=10,
            )
            if resp2.status_code != 200:
                continue
            soup = BeautifulSoup(resp2.text, "html.parser")
            title_el = soup.select_one("title")
            page_title = (title_el.get_text() if title_el else "").lower()
            meta = soup.select_one('meta[name="description"]')
            desc = (meta.get("content", "") if meta else "").lower()
            full = page_title + " " + desc

            if any(name in full for name in match_names):
                _log(f"[WeeklyDigest] Auto-BSN: {game_name} -> bsn={bsn}")
                return bsn
        except Exception:
            continue
    return None


def _title_contains_game(title: str, game_name: str) -> bool:
    """檢查標題是否包含遊戲名稱（含別名 + CJK 核心字）"""
    t = title.lower()
    # 主名稱
    if game_name.lower() in t:
        return True
    # TAG_ALIASES 別名
    for canonical, aliases in TAG_ALIASES.items():
        all_names = [canonical] + aliases
        if any(n.lower() in game_name.lower() or game_name.lower() in n.lower() for n in all_names):
            if any(alias.lower() in t for alias in all_names):
                return True
            break
    # CJK 核心字（至少 2 字的中文部分）
    cjk = re.sub(r'[^\u4e00-\u9fff]', '', game_name)
    if len(cjk) >= 2 and cjk in title:
        return True
    return False


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
            raw_name = item.get("name", "").strip()
            if not raw_name:
                continue
            # 過濾博弈類
            if any(kw in raw_name for kw in GAME_NAME_BLACKLIST_KW):
                continue
            name = _clean_game_name(raw_name)
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
            if not name:
                continue
            # 過濾非遊戲板
            if name in BOARD_BLACKLIST:
                continue
            if name not in seen_names:
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

    # 3. 自動搜尋巴哈 BSN（ACG 搜尋 + 板頁驗證）
    missing_bsn = [g for g in games if g["bsn"] is None]
    if missing_bsn:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=HEADERS) as client:
            for game in missing_bsn:
                found = await _search_bsn(client, game["name"])
                if found:
                    game["bsn"] = found

    # 4. 用 KNOWN_BSN 硬編碼補上仍缺 bsn 的遊戲（最終兜底）
    for game in games:
        if game["bsn"] is None:
            for known_name, known_bsn in KNOWN_BSN.items():
                if game["name"] in known_name or known_name in game["name"]:
                    game["bsn"] = known_bsn
                    break

    with_bsn = len([g for g in games if g["bsn"]])
    _log(f"[WeeklyDigest] Target games: {len(games)} "
         f"({len([g for g in games if g['source'] == 'android_grossing'])} Android + "
         f"{len([g for g in games if g['source'] == 'bahamut_hot'])} Bahamut), "
         f"{with_bsn} with BSN")
    return games


def _get_tag_variants(game_name: str) -> list[str]:
    """取得遊戲名稱的所有可能 tag 變體（支援子字串匹配）"""
    variants = [game_name]
    for canonical, aliases in TAG_ALIASES.items():
        all_names = [canonical] + aliases
        # 子字串匹配：遊戲名稱包含 canonical/alias，或反過來
        if any(n in game_name or game_name in n for n in all_names):
            variants = [canonical] + aliases + [game_name]
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

    # 排除非行銷內容
    noise_keywords = [
        "性侵", "詐騙", "犯罪", "逮捕", "判刑", "起訴",
        "買賣", "代儲", "代打", "徵人", "收購",
    ]
    skip_words = [
        "評測", "review", "心得", "開箱", "攻略", "教學",
        "tier list", "比較", "推薦", "懶人包",
    ]
    marketing_kws = EVENT_KEYWORDS + COLLAB_KEYWORDS + AD_KEYWORDS

    results = []
    for item in items:
        ts = item.get("createPublishedAt", 0)
        if ts < since_ts:
            continue
        title = item.get("title", "")
        intro = item.get("intro", "") or ""
        combined = f"{title} {intro}".lower()

        # 標題必須包含遊戲名稱
        if not _title_contains_game(title, game_name):
            continue

        # 排除噪音
        if any(kw in combined for kw in noise_keywords):
            continue

        # 排除非行銷內容（評測/攻略等）
        if any(kw in combined for kw in skip_words):
            continue

        # 必須包含行銷相關關鍵字
        if not any(kw.lower() in combined for kw in marketing_kws):
            continue

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
    # 聚焦行銷相關搜尋（活動/聯名/廣告），不搜「官方」避免拉到一般影片
    queries = [
        f"{game_name} 活動 聯名",
        f"{game_name} 廣告 PV CM",
    ]
    published_after = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 排除非行銷內容
    yt_skip_words = [
        "實況", "直播", "攻略", "教學", "開箱", "心得", "評測", "review",
        "gameplay", "walkthrough", "let's play", "分享", "試玩", "體驗",
        "比較", "推薦", "tier list", "通關", "挑戰", "抽卡", "課金",
        "pvp", "pve", "組隊", "配裝", "懶人包",
    ]

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
                    "order": "relevance",
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

                # 標題必須包含遊戲名稱（防止 YT 推薦無關影片）
                if not _title_contains_game(title, game_name):
                    continue

                title_lower = title.lower()
                # 排除攻略/實況類
                if any(sw in title_lower for sw in yt_skip_words):
                    continue

                # 必須包含至少一個行銷相關關鍵字
                marketing_kws = EVENT_KEYWORDS + COLLAB_KEYWORDS + AD_KEYWORDS
                if not any(kw.lower() in title_lower for kw in marketing_kws):
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

        # 只保留情報類貼文前綴
        allow_prefixes = ["【情報】", "【官方】", "【活動】"]
        # 排除非行銷類貼文
        deny_prefixes = [
            "【心得】", "【攻略】", "【閒聊】", "【問題】",
            "【密技】", "【討論】", "【公告】", "【其他】",
            "【造型】", "【分享】", "【集中】", "【數據】",
        ]

        # 板務/行政類關鍵字（直接排除）
        admin_skip_kws = [
            "板主", "板規", "哈啦區", "發文規則", "申請人", "看板規範",
            "站規", "版規", "徵板主", "子板", "輕鬆不放縱",
            "集中串規則", "發文注意", "板務",
        ]

        # 行銷相關關鍵字（title 必須包含至少一個）
        marketing_kws = [
            "活動", "聯名", "合作", "限定", "聯動", "連動", "跨界",
            "開跑", "獎勵", "贈送", "免費", "預告", "賽事", "代言",
            "廣告", "PV", "主題曲", "贊助", "周年", "週年", "節慶",
            "春節", "新年", "造型", "儲值", "抽獎", "禮包",
        ]

        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "C.php?bsn=" not in href:
                continue

            title = a.get_text(strip=True)
            if not title or len(title) < 5 or title in seen_titles:
                continue

            # 排除板務/行政貼文
            if any(kw in title for kw in admin_skip_kws):
                continue

            # 處理「精華」前綴：去掉後判斷真實分類
            # 巴哈的精華標記前有 icon font (\ue838 等 PUA 字元)，需一併清除
            core_title = re.sub(r'[\ue000-\uf8ff]', '', title).strip()
            if core_title.startswith("精華"):
                core_title = core_title[2:].strip()

            # 排除非行銷類前綴
            if any(core_title.startswith(p) for p in deny_prefixes):
                continue

            # 排除玩家社群類內容（非官方行銷）
            player_skip_kws = [
                "集中串", "互助區", "交換", "徵人", "徵友", "找人",
                "贈送串", "分享串", "集中討論", "捏臉", "捏角",
                "序號分享", "人品爆炸",
            ]
            if any(kw in title for kw in player_skip_kws):
                continue

            # 必須是情報類，或包含行銷關鍵字
            is_info_post = any(core_title.startswith(p) for p in allow_prefixes)
            has_marketing_kw = any(kw in title for kw in marketing_kws)
            if not is_info_post and not has_marketing_kw:
                continue

            # 即使是情報貼，也要有行銷內容（排除純數據/排行情報）
            if is_info_post and not has_marketing_kw:
                continue

            seen_titles.add(title)
            if not href.startswith("http"):
                href = f"https://forum.gamer.com.tw/{href}"

            results.append({
                "title": title,
                "url": href,
                "summary": f"巴哈 {game_name} 板",
                "source": "巴哈討論板",
                "published_at": "",
                "tags": _classify_item(title),
            })

            if len(results) >= 8:
                break

        return results
    except Exception as e:
        _log(f"[WeeklyDigest] Bahamut board error for bsn={bsn}: {e}")
        return []


# ============================================================
# 來源 4: Google News RSS — 跨媒體新聞聚合（最廣覆蓋）
# ============================================================
async def _search_google_news(client: httpx.AsyncClient, game_name: str, since: datetime) -> list[dict]:
    """透過 Google News RSS 搜尋遊戲相關行銷新聞（不需 API key）"""
    # 用純遊戲名稱搜尋（不加關鍵字限制），讓 post-filter 處理相關性
    encoded = urllib.parse.quote(f'"{game_name}"')
    url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

    try:
        resp = await client.get(url, timeout=15)
        if resp.status_code != 200:
            return []
    except Exception:
        return []

    feed = feedparser.parse(resp.text)
    results = []

    # 非行銷噪音關鍵字（排除犯罪新聞、股市、純電競賽事等無關報導）
    noise_keywords = [
        "性侵", "詐騙", "犯罪", "逮捕", "判刑", "起訴", "酒駕",
        "股價", "財報", "營收報告", "法說會",
    ]

    for entry in feed.entries:
        title = entry.get("title", "")
        link = entry.get("link", "")
        source_name = ""
        if hasattr(entry, "source"):
            source_name = entry.source.get("title", "") if isinstance(entry.source, dict) else str(entry.source)
        pub_str = entry.get("published", "")

        # 標題必須包含遊戲名稱（防止混入其他遊戲的新聞）
        if not _title_contains_game(title, game_name):
            continue

        # 解析日期，過濾超出範圍的
        pub_dt = None
        try:
            pub_dt = parsedate_to_datetime(pub_str)
            if pub_dt < since:
                continue
        except Exception:
            pass  # 無法解析日期的仍保留

        # 排除噪音
        if any(kw in title for kw in noise_keywords):
            continue

        # 必須包含行銷相關關鍵字
        marketing_kws = EVENT_KEYWORDS + COLLAB_KEYWORDS + AD_KEYWORDS
        if not any(kw in title for kw in marketing_kws):
            continue

        tags = _classify_item(title)

        # 清理標題（Google News 會在末尾加 " - 來源名"）
        clean_title = title.rsplit(" - ", 1)[0].strip() if " - " in title else title

        results.append({
            "title": clean_title,
            "url": link,
            "summary": f"來源：{source_name}" if source_name else "",
            "source": "Google News",
            "published_at": pub_dt.strftime("%Y-%m-%dT%H:%M:%S") if pub_dt else "",
            "tags": tags,
        })

        if len(results) >= 15:
            break

    return results


# ============================================================
# 來源 5: Google Custom Search — Facebook/IG 官方社群貼文
# ============================================================
async def _search_social_posts(client: httpx.AsyncClient, game_name: str, since: datetime) -> list[dict]:
    """透過 Google Custom Search API 搜尋 Facebook/IG 公開貼文（免 FB API 審核）"""
    api_key = os.getenv("GOOGLE_CSE_KEY", "")
    cx = os.getenv("GOOGLE_CSE_CX", "")
    if not api_key or not cx:
        return []

    results = []
    days_back = (datetime.now(TW_TZ) - since).days

    try:
        resp = await client.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": api_key,
                "cx": cx,
                "q": f'"{game_name}" 活動 OR 聯名 OR 合作 OR 更新',
                "dateRestrict": f"d{days_back}",
                "lr": "lang_zh-TW",
                "num": 10,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            _log(f"[WeeklyDigest] Google CSE error {resp.status_code}")
            return []

        data = resp.json()
    except Exception as e:
        _log(f"[WeeklyDigest] Google CSE request failed: {e}")
        return []

    # 非行銷噪音
    noise_keywords = [
        "性侵", "詐騙", "犯罪", "逮捕", "判刑", "起訴",
        "買賣", "代儲", "代打", "徵人", "收購",
    ]

    for item in data.get("items", []):
        title = item.get("title", "")
        link = item.get("link", "")
        snippet = item.get("snippet", "")

        # 標題或摘要必須包含遊戲名稱
        if not _title_contains_game(f"{title} {snippet}", game_name):
            continue

        combined = f"{title} {snippet}"

        # 排除噪音
        if any(kw in combined for kw in noise_keywords):
            continue

        # 必須包含行銷關鍵字
        marketing_kws = EVENT_KEYWORDS + COLLAB_KEYWORDS + AD_KEYWORDS
        if not any(kw in combined for kw in marketing_kws):
            continue

        tags = _classify_item(title, snippet)

        # 標記來源
        if "instagram.com" in link:
            source_label = "Instagram"
        elif "facebook.com" in link:
            source_label = "Facebook"
        else:
            source_label = "社群搜尋"

        results.append({
            "title": title,
            "url": link,
            "summary": snippet[:120] if snippet else "",
            "source": source_label,
            "published_at": "",
            "tags": tags,
        })

    return results


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

            # 5 個來源並行查詢
            results = await asyncio.gather(
                _search_google_news(client, name, start_time),
                _search_social_posts(client, name, start_time),
                _search_4gamers(client, name, start_time),
                _search_youtube(client, name, start_time),
                _search_bahamut_board(client, bsn, name),
                return_exceptions=True,
            )
            gnews_items, fb_items, fgamers_items, yt_items, baha_items = [
                r if isinstance(r, list) else [] for r in results
            ]

            all_items = gnews_items + fb_items + fgamers_items + yt_items + baha_items

            if not all_items:
                continue

            # 跨來源去重（用標題相似度）
            all_items = _dedup_items(all_items)

            # 只保留有行銷標籤的項目（移除純 "news" 分類）
            all_items = [item for item in all_items
                         if item.get("tags") != ["news"]]

            if not all_items:
                continue

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
                    "google_news": len(gnews_items),
                    "facebook": len(fb_items),
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
