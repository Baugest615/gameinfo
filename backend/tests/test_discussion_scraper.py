"""
discussion_scraper.py 測試 — HTML 解析、PTT 推文數轉換、容錯
使用 unittest.mock 模擬 httpx 回應，不打外部網站
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers import discussion_scraper


# ── helpers ──────────────────────────────────────────

def _mock_response(status_code=200, text="", json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    cache_dir = str(tmp_path / "cache")
    monkeypatch.setattr(discussion_scraper, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(discussion_scraper, "CACHE_FILE", str(tmp_path / "cache" / "discussion_data.json"))


# ── PTT hot boards HTML 解析 ─────────────────────────

PTT_HOTBOARDS_HTML = """
<html><body>
<a class="board" href="/bbs/C_Chat/index.html">
  <div class="board-name">C_Chat</div>
  <div class="board-class">閒談</div>
  <div class="board-title">希洽</div>
  <div class="board-nrec"><span>9999</span></div>
</a>
<a class="board" href="/bbs/Gossiping/index.html">
  <div class="board-name">Gossiping</div>
  <div class="board-class">綜合</div>
  <div class="board-title">八卦</div>
  <div class="board-nrec"><span>5000</span></div>
</a>
</body></html>
"""


async def test_fetch_ptt_hot_boards_parses_html():
    """正確解析 PTT hotboards HTML 結構"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(text=PTT_HOTBOARDS_HTML))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.discussion_scraper.httpx.AsyncClient", return_value=mock_client):
        boards = await discussion_scraper.fetch_ptt_hot_boards()

    assert len(boards) == 2
    assert boards[0]["name"] == "C_Chat"
    assert boards[0]["popularity"] == 9999
    assert boards[0]["url"] == "https://www.ptt.cc/bbs/C_Chat/index.html"
    assert boards[1]["name"] == "Gossiping"


async def test_fetch_ptt_hot_boards_error_returns_empty():
    """網路錯誤時回傳空列表"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.discussion_scraper.httpx.AsyncClient", return_value=mock_client):
        boards = await discussion_scraper.fetch_ptt_hot_boards()

    assert boards == []


# ── PTT 文章推文數轉換邏輯 ───────────────────────────

PTT_ARTICLES_HTML = """
<html><body>
<div class="r-ent">
  <div class="nrec"><span class="hl f3">爆</span></div>
  <div class="title"><a href="/bbs/C_Chat/M.001.html">[閒聊] 超熱門文章</a></div>
</div>
<div class="r-ent">
  <div class="nrec"><span class="hl f3">X5</span></div>
  <div class="title"><a href="/bbs/C_Chat/M.002.html">[問題] 被噓爆的文</a></div>
</div>
<div class="r-ent">
  <div class="nrec"><span class="hl f3">30</span></div>
  <div class="title"><a href="/bbs/C_Chat/M.003.html">[心得] 普通文章</a></div>
</div>
<div class="r-ent">
  <div class="nrec"></div>
  <div class="title"><a href="/bbs/C_Chat/M.004.html">[討論] 零推文</a></div>
</div>
<div class="r-ent">
  <div class="nrec"><span>5</span></div>
  <div class="title"><a href="/bbs/C_Chat/M.005.html">[公告] 版規更新</a></div>
</div>
</body></html>
"""


async def test_fetch_ptt_hot_articles_popularity_conversion():
    """推文數轉換：爆→100, X開頭→-1, 數字→int, 無→0，公告跳過"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(text=PTT_ARTICLES_HTML))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.discussion_scraper.httpx.AsyncClient", return_value=mock_client):
        articles = await discussion_scraper.fetch_ptt_hot_articles()

    # [公告] 應被過濾
    titles = [a["title"] for a in articles]
    assert not any("[公告]" in t for t in titles)

    # 按 popularity_value 降序排列
    values = [a["popularity_value"] for a in articles]
    assert values == sorted(values, reverse=True)

    # 驗證轉換邏輯
    by_title = {a["title"]: a for a in articles}
    assert by_title["[閒聊] 超熱門文章"]["popularity_value"] == 100  # 爆
    assert by_title["[問題] 被噓爆的文"]["popularity_value"] == -1   # X5
    assert by_title["[心得] 普通文章"]["popularity_value"] == 30      # 數字
    assert by_title["[討論] 零推文"]["popularity_value"] == 0         # 無推文


# ── 巴哈姆特 boards 解析 ─────────────────────────────

BAHAMUT_HTML = """
<html><body>
<a href="B.php?bsn=60076">原神</a>
<a href="B.php?bsn=36730">英雄聯盟</a>
<a href="B.php?bsn=99999">A</a>
<a href="C.php?bsn=60076&snA=12345">【心得】好玩推薦</a>
<a href="other.php">不相關</a>
</body></html>
"""


async def test_fetch_bahamut_top_boards_parses_links():
    """正確解析巴哈 B.php?bsn= 格式的版面連結"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(text=BAHAMUT_HTML))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.discussion_scraper.httpx.AsyncClient", return_value=mock_client):
        boards = await discussion_scraper.fetch_bahamut_top_boards()

    # "A" 應被過濾（len < 2）
    names = [b["name"] for b in boards]
    assert "原神" in names
    assert "英雄聯盟" in names
    assert "A" not in names
    assert boards[0]["bsn"] == "60076"
    assert "B.php?bsn=60076" in boards[0]["url"]


async def test_fetch_bahamut_hot_articles_with_source():
    """巴哈文章應包含來源版名"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(text=BAHAMUT_HTML))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.discussion_scraper.httpx.AsyncClient", return_value=mock_client):
        articles = await discussion_scraper.fetch_bahamut_hot_articles()

    # HTML 中有一個 C.php 文章連結，標題以【開頭
    assert len(articles) >= 1
    assert articles[0]["source"] == "原神"  # bsn=60076 對應的版名
    assert articles[0]["bsn"] == "60076"
