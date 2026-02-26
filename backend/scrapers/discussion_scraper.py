"""
遊戲討論聲量爬蟲模組 v3
Tab 1: 巴哈姆特 Top 20 熱門討論版
Tab 2: PTT 全站即時人氣熱門版 (hotboards)
Tab 3: 巴哈姆特每版當天最熱文章 (含來源版名)
Tab 4: PTT 遊戲版推文數最多文章
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
import json
import os
import time
import re
from scrapers.sentiment import analyze_title, analyze_ptt_article, aggregate_sentiment

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "discussion_data.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


# ============================================================
# Tab 1: 巴哈姆特 Top 20 熱門討論版
# ============================================================
async def fetch_bahamut_top_boards():
    """從巴哈姆特哈啦區首頁抓取熱門討論版"""
    url = "https://forum.gamer.com.tw/"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        boards = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "B.php?bsn=" not in href:
                continue

            name = a.get_text(strip=True)
            if not name or name in seen or len(name) < 2:
                continue

            bsn_match = re.search(r'bsn=(\d+)', href)
            if not bsn_match:
                continue

            bsn = bsn_match.group(1)
            seen.add(name)

            if not href.startswith("http"):
                href = f"https://forum.gamer.com.tw/{href}"

            boards.append({
                "name": name,
                "bsn": bsn,
                "url": href,
                "rank": len(boards) + 1,
            })

            if len(boards) >= 20:
                break

        return boards

    except Exception as e:
        print(f"[Discussion] Bahamut boards error: {e}")
        return []


# ============================================================
# Tab 2: PTT 全站即時人氣熱門版
# ============================================================
async def fetch_ptt_hot_boards():
    """PTT hotboards 全站即時人氣排行"""
    url = "https://www.ptt.cc/bbs/hotboards.html"
    cookies = {"over18": "1"}
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS, cookies=cookies)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        boards = []

        for item in soup.select("a.board"):
            board_name_el = item.select_one("div.board-name")
            board_class_el = item.select_one("div.board-class")
            board_title_el = item.select_one("div.board-title")

            if not board_name_el:
                continue

            name = board_name_el.get_text(strip=True)
            category = board_class_el.get_text(strip=True) if board_class_el else ""
            title = board_title_el.get_text(strip=True) if board_title_el else ""

            # 嘗試多種方式取得人氣數字
            pop_value = 0
            # 方法 1: div.board-nrec > span
            nrec_el = item.select_one("div.board-nrec span")
            if nrec_el:
                try:
                    pop_value = int(nrec_el.get_text(strip=True))
                except ValueError:
                    pass
            # 方法 2: div.board-nrec 直接文字
            if pop_value == 0:
                nrec_div = item.select_one("div.board-nrec")
                if nrec_div:
                    try:
                        pop_value = int(nrec_div.get_text(strip=True))
                    except ValueError:
                        pass
            # 方法 3: 從整個元素文字中用 regex 提取數字
            if pop_value == 0:
                full_text = item.get_text()
                # 找 board name 後面跟著的數字
                nums = re.findall(r'\b(\d{2,5})\b', full_text)
                if nums:
                    pop_value = int(nums[0])

            href = item.get("href", "")
            if href:
                href = f"https://www.ptt.cc{href}"

            boards.append({
                "name": name,
                "url": href,
                "popularity": pop_value,
                "category": category,
                "title": title,
                "rank": len(boards) + 1,
            })

            if len(boards) >= 20:
                break

        return boards

    except Exception as e:
        print(f"[Discussion] PTT hot boards error: {e}")

        return []


# ============================================================
# Tab 3: 巴哈姆特每版最熱文章 (含來源版名)
# ============================================================
async def fetch_bahamut_hot_articles():
    """從巴哈首頁取得每個熱門版的最熱文章，含來源版名"""
    url = "https://forum.gamer.com.tw/"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # 先建立 bsn -> 版面名稱 的映射
        bsn_to_board = {}
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "B.php?bsn=" in href:
                name = a.get_text(strip=True)
                bsn_match = re.search(r'bsn=(\d+)', href)
                if bsn_match and name and len(name) >= 2:
                    bsn_to_board[bsn_match.group(1)] = name

        # 再抓文章
        articles = []
        seen_titles = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "C.php?bsn=" not in href:
                continue

            title = a.get_text(strip=True)
            if not title or title in seen_titles or len(title) < 5:
                continue

            if not (title.startswith("\u3010") or title.startswith("[")):
                continue

            seen_titles.add(title)

            bsn_match = re.search(r'bsn=(\d+)', href)
            bsn = bsn_match.group(1) if bsn_match else ""
            board_name = bsn_to_board.get(bsn, "")

            if not href.startswith("http"):
                href = f"https://forum.gamer.com.tw/{href}"

            articles.append({
                "title": title,
                "url": href,
                "bsn": bsn,
                "source": board_name if board_name else "Bahamut",
            })

            if len(articles) >= 20:
                break

        return articles

    except Exception as e:
        print(f"[Discussion] Bahamut articles error: {e}")
        return []


# ============================================================
# Tab 4: PTT 推文數最多文章
# ============================================================
async def fetch_ptt_hot_articles():
    """PTT 遊戲版中推文數最多的文章（5 版面並行爬取）"""
    boards = ["C_Chat", "Steam", "PlayStation", "NSwitch", "LoL"]

    async def _fetch_one_board(client, board):
        url = f"https://www.ptt.cc/bbs/{board}/index.html"
        cookies = {"over18": "1"}
        articles = []
        try:
            resp = await client.get(url, headers=HEADERS, cookies=cookies)
            if resp.status_code != 200:
                return articles

            soup = BeautifulSoup(resp.text, "html.parser")

            for item in soup.select("div.r-ent"):
                title_el = item.select_one("div.title a")
                nrec_el = item.select_one("div.nrec span")

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)

                skip_prefixes = ["[公告]", "Fw: [公告]", "[版規]", "[置底]", "[活動]"]
                if any(title.startswith(p) for p in skip_prefixes):
                    continue
                if "(本文已被刪除)" in title:
                    continue

                href = title_el.get("href", "")
                pop_text = nrec_el.get_text(strip=True) if nrec_el else "0"

                if pop_text == "\u7206":
                    pop_value = 100
                elif pop_text.startswith("X"):
                    pop_value = -1
                elif pop_text.isdigit():
                    pop_value = int(pop_text)
                else:
                    pop_value = 0

                if href:
                    href = f"https://www.ptt.cc{href}"

                articles.append({
                    "title": title,
                    "url": href,
                    "source": f"PTT {board}",
                    "popularity": pop_text,
                    "popularity_value": pop_value,
                })
        except Exception:
            pass
        return articles

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        results = await asyncio.gather(
            *[_fetch_one_board(client, board) for board in boards],
            return_exceptions=True,
        )

    all_articles = []
    for r in results:
        if isinstance(r, list):
            all_articles.extend(r)

    all_articles.sort(key=lambda x: x["popularity_value"], reverse=True)
    return all_articles[:20]


# ============================================================
# 聚合所有數據
# ============================================================
async def fetch_all_discussions():
    """聚合四個分頁的討論數據（兩批並行：boards → articles）"""
    try:
        # 第一批：巴哈 boards + PTT boards（不同主機，可並行）
        bahamut_boards, ptt_boards = await asyncio.gather(
            fetch_bahamut_top_boards(),
            fetch_ptt_hot_boards(),
            return_exceptions=True,
        )
        if isinstance(bahamut_boards, Exception):
            print(f"[Discussion] Bahamut boards error: {bahamut_boards}")
            bahamut_boards = []
        if isinstance(ptt_boards, Exception):
            print(f"[Discussion] PTT boards error: {ptt_boards}")
            ptt_boards = []

        # 第二批：巴哈 articles + PTT articles（不同主機，可並行）
        bahamut_articles, ptt_articles = await asyncio.gather(
            fetch_bahamut_hot_articles(),
            fetch_ptt_hot_articles(),
            return_exceptions=True,
        )
        if isinstance(bahamut_articles, Exception):
            print(f"[Discussion] Bahamut articles error: {bahamut_articles}")
            bahamut_articles = []
        if isinstance(ptt_articles, Exception):
            print(f"[Discussion] PTT articles error: {ptt_articles}")
            ptt_articles = []

        # 情緒分析：巴哈用關鍵字，PTT 用推噓比 + 關鍵字
        for item in bahamut_articles:
            item["sentiment"] = analyze_title(item.get("title", ""))
        for item in ptt_articles:
            item["sentiment"] = analyze_ptt_article(
                item.get("title", ""), item.get("popularity_value", 0)
            )

        all_articles = bahamut_articles + ptt_articles

        all_discussions = {
            "bahamut_boards": bahamut_boards[:20],
            "ptt_boards": ptt_boards[:20],
            "bahamut_articles": bahamut_articles[:20],
            "ptt_articles": ptt_articles[:20],
            "total_count": (
                len(bahamut_boards) + len(ptt_boards)
                + len(bahamut_articles) + len(ptt_articles)
            ),
            "sentiment_summary": aggregate_sentiment(all_articles),
            "updated_at": int(time.time()),
        }

        _save_cache(all_discussions)
        return all_discussions

    except Exception as e:
        print(f"[Discussion] Aggregate error: {e}")
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
        return {
            "bahamut_boards": [], "ptt_boards": [],
            "bahamut_articles": [], "ptt_articles": [],
            "total_count": 0,
        }
