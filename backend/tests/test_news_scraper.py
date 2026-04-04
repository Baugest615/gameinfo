"""
news_scraper.py 測試 — RSS 解析、JSON API 解析、去重、容錯
使用 unittest.mock 模擬 httpx 回應
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers import news_scraper


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
    monkeypatch.setattr(news_scraper, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(news_scraper, "CACHE_FILE", str(tmp_path / "cache" / "news_data.json"))


# ── _news_hash ───────────────────────────────────────

def test_news_hash_deterministic():
    """同樣的 title+source 應產生相同 hash"""
    h1 = news_scraper._news_hash("遊戲新聞標題", "GNN")
    h2 = news_scraper._news_hash("遊戲新聞標題", "GNN")
    assert h1 == h2


def test_news_hash_different_sources():
    """不同 source 應產生不同 hash"""
    h1 = news_scraper._news_hash("相同標題", "GNN")
    h2 = news_scraper._news_hash("相同標題", "4Gamers TW")
    assert h1 != h2


# ── fetch_gnn_rss ────────────────────────────────────

GNN_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>GNN 新聞</title>
  <item>
    <title>《原神》5.0 更新預告</title>
    <link>https://gnn.gamer.com.tw/detail.php?sn=001</link>
    <description>原神新版本即將推出</description>
    <pubDate>Fri, 04 Apr 2026 08:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Steam 夏季特賣開跑</title>
    <link>https://gnn.gamer.com.tw/detail.php?sn=002</link>
    <description>年度最大特賣活動</description>
    <pubDate>Fri, 04 Apr 2026 06:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


async def test_fetch_gnn_rss_parses_feed():
    """正確解析 GNN RSS 並轉換日期為 ISO 格式"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(text=GNN_RSS))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.news_scraper.httpx.AsyncClient", return_value=mock_client):
        news = await news_scraper.fetch_gnn_rss()

    assert len(news) == 2
    assert news[0]["title"] == "《原神》5.0 更新預告"
    assert news[0]["source"] == "巴哈姆特 GNN"
    assert "2026-04-04" in news[0]["published_at"]
    assert news[0]["id"]  # 應有 hash ID


async def test_fetch_gnn_rss_error_returns_empty():
    """RSS 錯誤時回傳空列表"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("DNS resolution failed"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.news_scraper.httpx.AsyncClient", return_value=mock_client):
        news = await news_scraper.fetch_gnn_rss()

    assert news == []


# ── fetch_4gamers_tw ─────────────────────────────────

async def test_fetch_4gamers_tw_parses_json():
    """正確解析 4Gamers JSON API"""
    ts_ms = int(time.time() * 1000)
    api_data = {
        "data": {
            "results": [
                {
                    "title": "Switch 2 發售日確認",
                    "canonicalUrl": "https://www.4gamers.com.tw/news/001",
                    "intro": "任天堂正式公佈",
                    "createPublishedAt": ts_ms,
                },
                {
                    "title": "短",
                    "canonicalUrl": "https://www.4gamers.com.tw/news/002",
                    "intro": "",
                    "createPublishedAt": ts_ms,
                },
            ]
        }
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(json_data=api_data))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.news_scraper.httpx.AsyncClient", return_value=mock_client):
        news = await news_scraper.fetch_4gamers_tw()

    # "短" 應被過濾（len < 5）
    assert len(news) == 1
    assert news[0]["title"] == "Switch 2 發售日確認"
    assert news[0]["source"] == "4Gamers TW"


# ── aggregate_news ───────────────────────────────────

async def test_aggregate_news_deduplicates():
    """aggregate_news 應根據 id 去重"""
    duplicate_news = [
        {"id": "abc", "title": "新聞A", "source": "GNN", "published_at": "2026-04-04T08:00:00Z"},
        {"id": "abc", "title": "新聞A", "source": "GNN", "published_at": "2026-04-04T08:00:00Z"},
        {"id": "def", "title": "新聞B", "source": "4G", "published_at": "2026-04-04T07:00:00Z"},
    ]

    with patch("scrapers.news_scraper.fetch_gnn_rss", AsyncMock(return_value=duplicate_news[:2])), \
         patch("scrapers.news_scraper.fetch_4gamers_tw", AsyncMock(return_value=[duplicate_news[2]])), \
         patch("scrapers.news_scraper.fetch_udn_game", AsyncMock(return_value=[])):
        result = await news_scraper.aggregate_news()

    assert result["total_count"] == 2  # abc 去重後只剩 1 + def = 2


async def test_aggregate_news_partial_failure():
    """部分來源失敗時仍回傳其他來源的結果"""
    good_news = [
        {"id": "x1", "title": "好新聞", "source": "GNN", "published_at": "2026-04-04T08:00:00Z"},
    ]

    with patch("scrapers.news_scraper.fetch_gnn_rss", AsyncMock(return_value=good_news)), \
         patch("scrapers.news_scraper.fetch_4gamers_tw", AsyncMock(side_effect=Exception("boom"))), \
         patch("scrapers.news_scraper.fetch_udn_game", AsyncMock(return_value=[])):
        result = await news_scraper.aggregate_news()

    assert result["total_count"] == 1
    assert result["news"][0]["title"] == "好新聞"
