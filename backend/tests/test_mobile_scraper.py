"""
mobile_scraper.py 測試 — iOS RSS 解析、Android gplay-scraper mock、cache fallback、聚合容錯
使用 unittest.mock 模擬 httpx + gplay-scraper，不打外部 API
"""
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers import mobile_scraper


# ── helpers ──────────────────────────────────────────

def _mock_response(status_code=200, json_data=None):
    """建立模擬的 httpx.Response"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


SAMPLE_IOS_RSS = {
    "feed": {
        "entry": [
            {
                "im:name": {"label": "原神"},
                "id": {
                    "label": "https://apps.apple.com/tw/app/id1517783697",
                    "attributes": {"im:id": "1517783697"},
                },
                "im:image": [
                    {"label": "https://example.com/small.png"},
                    {"label": "https://example.com/large.png"},
                ],
                "category": {
                    "attributes": {"label": "遊戲"},
                },
            },
            {
                "im:name": {"label": "崩壞：星穹鐵道"},
                "id": {
                    "label": "https://apps.apple.com/tw/app/id123456",
                    "attributes": {"im:id": "123456"},
                },
                "im:image": [{"label": "https://example.com/icon2.png"}],
                "category": {"attributes": {"label": "遊戲"}},
            },
        ]
    }
}

SAMPLE_GP_RAW = [
    {
        "title": "原神",
        "appId": "com.miHoYo.GenshinImpact",
        "url": "https://play.google.com/store/apps/details?id=com.miHoYo.GenshinImpact",
        "icon": "https://example.com/genshin.png",
        "genre": "角色扮演",
        "score": 4.5,
        "installs": "50,000,000+",
        "developer": "miHoYo",
    },
    {
        "title": "傳說對決",
        "appId": "com.garena.game.kgtw",
        "url": "https://play.google.com/store/apps/details?id=com.garena.game.kgtw",
        "icon": "https://example.com/aov.png",
        "genre": "動作",
        "score": 3.8,
        "installs": "10,000,000+",
        "developer": "Garena",
    },
]


# ── fixtures ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    """隔離快取目錄，避免測試互相干擾"""
    cache_dir = str(tmp_path / "cache")
    monkeypatch.setattr(mobile_scraper, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(mobile_scraper, "CACHE_FILE", str(tmp_path / "cache" / "mobile_data.json"))


# ── fetch_ios_top_free ───────────────────────────────

async def test_fetch_ios_top_free_parses_rss():
    """正常 iTunes RSS 回應：解析遊戲名稱、app_id、icon、genre"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(json_data=SAMPLE_IOS_RSS))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.mobile_scraper.httpx.AsyncClient", return_value=mock_client):
        result = await mobile_scraper.fetch_ios_top_free()

    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["name"] == "原神"
    assert result[0]["id"] == "1517783697"
    assert result[0]["icon"] == "https://example.com/large.png"
    assert result[0]["genres"] == "遊戲"
    assert result[0]["chart"] == "iOS Free"
    assert result[1]["name"] == "崩壞：星穹鐵道"
    assert result[1]["rank"] == 2


async def test_fetch_ios_top_free_empty_feed():
    """RSS 回傳空 feed 時回傳空列表"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(json_data={"feed": {}}))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.mobile_scraper.httpx.AsyncClient", return_value=mock_client):
        result = await mobile_scraper.fetch_ios_top_free()

    assert result == []


async def test_fetch_ios_top_free_error_returns_empty():
    """HTTP 錯誤時回傳空列表"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.mobile_scraper.httpx.AsyncClient", return_value=mock_client):
        result = await mobile_scraper.fetch_ios_top_free()

    assert result == []


# ── fetch_ios_top_grossing ───────────────────────────

async def test_fetch_ios_top_grossing_returns_empty():
    """台灣區暢銷排行不可用，應回傳空列表"""
    result = await mobile_scraper.fetch_ios_top_grossing()
    assert result == []


# ── _format_gp_results ───────────────────────────────

def test_format_gp_results_structures_data():
    """格式化 gplay-scraper 回傳資料"""
    formatted = mobile_scraper._format_gp_results(SAMPLE_GP_RAW, "Android Free", count=30)

    assert len(formatted) == 2
    assert formatted[0]["rank"] == 1
    assert formatted[0]["name"] == "原神"
    assert formatted[0]["id"] == "com.miHoYo.GenshinImpact"
    assert formatted[0]["score"] == 4.5
    assert formatted[0]["chart"] == "Android Free"
    assert formatted[1]["developer"] == "Garena"


def test_format_gp_results_respects_count():
    """count 限制回傳筆數"""
    formatted = mobile_scraper._format_gp_results(SAMPLE_GP_RAW, "Android Free", count=1)
    assert len(formatted) == 1
    assert formatted[0]["name"] == "原神"


def test_format_gp_results_handles_missing_score():
    """score 為 None 時應回傳 0"""
    raw = [{"title": "TestApp", "appId": "com.test", "score": None}]
    formatted = mobile_scraper._format_gp_results(raw, "Android Free")
    assert formatted[0]["score"] == 0


# ── fetch_android_top_games ──────────────────────────

async def test_fetch_android_top_games_success():
    """正常取得 Android 排行榜"""
    with patch("scrapers.mobile_scraper._fetch_gp_chart") as mock_chart:
        mock_chart.return_value = SAMPLE_GP_RAW

        result = await mobile_scraper.fetch_android_top_games(count=30)

    assert "free" in result
    assert "grossing" in result
    assert len(result["free"]) == 2
    assert result["free"][0]["name"] == "原神"


async def test_fetch_android_top_games_error_fallback_cache(tmp_path):
    """Android 錯誤時 fallback 到 cache"""
    # 先寫入假快取
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = str(tmp_path / "cache" / "mobile_data.json")
    cached = {
        "android": {
            "free": [{"rank": 1, "name": "CachedGame"}],
            "grossing": [],
        }
    }
    with open(cache_file, "w") as f:
        json.dump(cached, f)

    with patch("scrapers.mobile_scraper._fetch_gp_chart", side_effect=Exception("timeout")):
        result = await mobile_scraper.fetch_android_top_games()

    assert result["free"][0]["name"] == "CachedGame"


# ── fetch_all_mobile ─────────────────────────────────

async def test_fetch_all_mobile_success():
    """聚合 iOS + Android 資料"""
    ios_data = [{"rank": 1, "name": "iOSGame", "chart": "iOS Free"}]
    android_data = {
        "free": [{"rank": 1, "name": "AndroidGame"}],
        "grossing": [{"rank": 1, "name": "TopGrossing"}],
    }

    with patch("scrapers.mobile_scraper.fetch_ios_top_free", AsyncMock(return_value=ios_data)), \
         patch("scrapers.mobile_scraper.fetch_android_top_games", AsyncMock(return_value=android_data)), \
         patch("scrapers.mobile_scraper.fetch_ios_top_grossing", AsyncMock(return_value=[])):
        result = await mobile_scraper.fetch_all_mobile()

    assert result["ios"]["free"] == ios_data
    assert result["ios"]["grossing"] == []
    assert result["android"]["free"] == android_data["free"]
    assert result["android"]["grossing"] == android_data["grossing"]
    assert "updated_at" in result


async def test_fetch_all_mobile_ios_exception_returns_empty():
    """iOS 拋出異常時，iOS 部分回傳空列表，Android 正常"""
    android_data = {"free": [{"rank": 1, "name": "OK"}], "grossing": []}

    with patch("scrapers.mobile_scraper.fetch_ios_top_free", AsyncMock(side_effect=Exception("iOS down"))), \
         patch("scrapers.mobile_scraper.fetch_android_top_games", AsyncMock(return_value=android_data)), \
         patch("scrapers.mobile_scraper.fetch_ios_top_grossing", AsyncMock(return_value=[])):
        result = await mobile_scraper.fetch_all_mobile()

    assert result["ios"]["free"] == []
    assert result["android"]["free"][0]["name"] == "OK"


async def test_fetch_all_mobile_total_failure_returns_cache(tmp_path):
    """全部失敗時 fallback 到 cache"""
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = str(tmp_path / "cache" / "mobile_data.json")
    cached = {
        "ios": {"free": [{"rank": 1, "name": "CachedIOS"}], "grossing": []},
        "android": {"free": [], "grossing": []},
    }
    with open(cache_file, "w") as f:
        json.dump(cached, f)

    # gather 裡兩個都拋例外，外層 catch 走 _load_cache
    with patch("scrapers.mobile_scraper.fetch_ios_top_free", AsyncMock(side_effect=Exception("fail"))), \
         patch("scrapers.mobile_scraper.fetch_android_top_games", AsyncMock(side_effect=Exception("fail"))), \
         patch("scrapers.mobile_scraper.asyncio") as mock_asyncio:
        # 讓 asyncio.gather 本身拋例外（模擬外層 except）
        mock_asyncio.gather = AsyncMock(side_effect=Exception("total failure"))
        mock_asyncio.wait_for = AsyncMock()
        mock_asyncio.to_thread = AsyncMock()

        result = await mobile_scraper.fetch_all_mobile()

    assert result["ios"]["free"][0]["name"] == "CachedIOS"


# ── cache functions ──────────────────────────────────

def test_save_and_load_cache(tmp_path):
    """cache 寫入後可正確讀回"""
    data = {"ios": {"free": [{"rank": 1}]}, "android": {"free": []}}
    mobile_scraper._save_cache(data)
    loaded = mobile_scraper._load_cache()
    assert loaded["ios"]["free"][0]["rank"] == 1


def test_load_cache_missing_file():
    """cache 檔案不存在時回傳預設結構"""
    result = mobile_scraper._load_cache()
    assert result == {"ios": {"free": [], "grossing": []}, "android": {"free": [], "grossing": []}}
