"""
steam_scraper.py 測試 — API 回應解析、容錯、cache fallback
使用 unittest.mock 模擬 httpx 回應，不打外部 API
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers import steam_scraper


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


# ── fetch_top_games ──────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    """隔離快取目錄，避免測試互相干擾"""
    cache_dir = str(tmp_path / "cache")
    monkeypatch.setattr(steam_scraper, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(steam_scraper, "CACHE_FILE", str(tmp_path / "cache" / "steam_data.json"))
    monkeypatch.setattr(steam_scraper, "NAME_CACHE_FILE", str(tmp_path / "cache" / "steam_names.json"))


async def test_fetch_top_games_success():
    """正常回應：解析 ranks 並回傳遊戲列表"""
    api_response = {
        "response": {
            "ranks": [
                {"rank": 1, "appid": 730, "peak_in_game": 1500000},
                {"rank": 2, "appid": 570, "peak_in_game": 800000},
            ]
        }
    }
    name_response_730 = {"730": {"success": True, "data": {"name": "Counter-Strike 2"}}}
    name_response_570 = {"570": {"success": True, "data": {"name": "Dota 2"}}}

    async def mock_get(url, **kwargs):
        if "GetMostPlayedGames" in url:
            return _mock_response(json_data=api_response)
        if "appids=730" in url:
            return _mock_response(json_data=name_response_730)
        if "appids=570" in url:
            return _mock_response(json_data=name_response_570)
        return _mock_response(json_data={})

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.steam_scraper.httpx.AsyncClient", return_value=mock_client):
        games = await steam_scraper.fetch_top_games()

    assert len(games) == 2
    assert games[0]["appid"] == 730
    assert games[0]["name"] == "Counter-Strike 2"
    assert games[0]["current_players"] == 1500000
    assert games[1]["appid"] == 570


async def test_fetch_top_games_api_error_falls_back_to_cache(tmp_path):
    """API 錯誤時應回傳快取資料"""
    # 先寫入假快取
    import os
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = str(tmp_path / "cache" / "steam_data.json")
    cached = {"games": [{"rank": 1, "appid": 999, "name": "Cached Game", "current_players": 100}]}
    with open(cache_file, "w") as f:
        json.dump(cached, f)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Connection timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.steam_scraper.httpx.AsyncClient", return_value=mock_client):
        games = await steam_scraper.fetch_top_games()

    assert len(games) == 1
    assert games[0]["name"] == "Cached Game"


async def test_fetch_top_games_empty_ranks():
    """API 回傳空 ranks 時應回傳空列表"""
    api_response = {"response": {"ranks": []}}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(json_data=api_response))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.steam_scraper.httpx.AsyncClient", return_value=mock_client):
        games = await steam_scraper.fetch_top_games()

    assert games == []


# ── fetch_player_count ───────────────────────────────

async def test_fetch_player_count_success():
    """正常回應：回傳玩家人數"""
    api_response = {"response": {"player_count": 42000}}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(json_data=api_response))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.steam_scraper.httpx.AsyncClient", return_value=mock_client):
        count = await steam_scraper.fetch_player_count(730)

    assert count == 42000


async def test_fetch_player_count_error_returns_zero():
    """API 錯誤時回傳 0"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("scrapers.steam_scraper.httpx.AsyncClient", return_value=mock_client):
        count = await steam_scraper.fetch_player_count(730)

    assert count == 0
