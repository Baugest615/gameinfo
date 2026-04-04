"""
twitch_scraper.py 測試 — Token refresh、串流聚合、容錯
使用 unittest.mock 模擬 httpx 回應與環境變數
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers import twitch_scraper


# ── helpers ──────────────────────────────────────────

def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


@pytest.fixture(autouse=True)
def isolate_twitch(tmp_path, monkeypatch):
    """隔離快取 + 重置 token cache"""
    cache_dir = str(tmp_path / "cache")
    monkeypatch.setattr(twitch_scraper, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(twitch_scraper, "CACHE_FILE", str(tmp_path / "cache" / "twitch_data.json"))
    # 每次測試重置 token cache 和 lock
    twitch_scraper._token_cache["access_token"] = None
    twitch_scraper._token_cache["expires_at"] = 0
    twitch_scraper._token_lock = None


# ── _get_access_token ────────────────────────────────

async def test_get_access_token_success(monkeypatch):
    """有憑證時應成功取得 token"""
    monkeypatch.setenv("TWITCH_CLIENT_ID", "test_id")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "test_secret")

    token_response = {"access_token": "abc123", "expires_in": 3600}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(json_data=token_response))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.twitch_scraper.httpx.AsyncClient", return_value=mock_client):
        token = await twitch_scraper._get_access_token()

    assert token == "abc123"
    assert twitch_scraper._token_cache["access_token"] == "abc123"


async def test_get_access_token_missing_credentials(monkeypatch):
    """缺少 client_id/secret 時應回傳 None"""
    monkeypatch.setenv("TWITCH_CLIENT_ID", "")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "")

    token = await twitch_scraper._get_access_token()
    assert token is None


async def test_get_access_token_uses_cache(monkeypatch):
    """token 未過期時應使用快取，不再呼叫 API"""
    monkeypatch.setenv("TWITCH_CLIENT_ID", "test_id")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "test_secret")

    twitch_scraper._token_cache["access_token"] = "cached_token"
    twitch_scraper._token_cache["expires_at"] = time.time() + 3600

    # 不 patch httpx — 如果它真的去呼叫 API 會因為沒有 mock 而失敗
    token = await twitch_scraper._get_access_token()
    assert token == "cached_token"


# ── fetch_top_games ──────────────────────────────────

async def test_fetch_top_games_no_token_returns_demo(monkeypatch):
    """沒有 token 時回傳 demo 資料"""
    monkeypatch.setenv("TWITCH_CLIENT_ID", "")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "")

    games = await twitch_scraper.fetch_top_games()

    # 應回傳 demo 或快取（此測試無快取，所以是 demo）
    assert isinstance(games, list)
    assert len(games) >= 1
    assert games[0]["name"] == "League of Legends"


async def test_fetch_zh_streams_success(monkeypatch):
    """成功取得中文串流並正確解析"""
    monkeypatch.setenv("TWITCH_CLIENT_ID", "test_id")

    streams_data = {
        "data": [
            {"game_id": "21779", "viewer_count": 5000},
            {"game_id": "21779", "viewer_count": 3000},
            {"game_id": "33214", "viewer_count": 2000},
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(json_data=streams_data))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.twitch_scraper.httpx.AsyncClient", return_value=mock_client):
        streams = await twitch_scraper._fetch_zh_streams("fake_token", count=100)

    assert len(streams) == 3
    assert streams[0]["game_id"] == "21779"


async def test_fetch_zh_streams_error_returns_empty(monkeypatch):
    """串流 API 錯誤時回傳空列表"""
    monkeypatch.setenv("TWITCH_CLIENT_ID", "test_id")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Network error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.twitch_scraper.httpx.AsyncClient", return_value=mock_client):
        streams = await twitch_scraper._fetch_zh_streams("fake_token")

    assert streams == []
