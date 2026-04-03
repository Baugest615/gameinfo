"""
scheduler.py 測試 — Scheduler resilience
覆蓋：_run_with_timeout 正常/超時/例外 + update_* cascade failure 防護
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import scheduler


# ── _run_with_timeout ────────────────────────────────


async def test_run_with_timeout_normal():
    """正常完成的 coroutine 應回傳結果"""
    async def quick_task():
        return "done"

    result = await scheduler._run_with_timeout(quick_task(), timeout=5, label="Test")
    assert result == "done"


async def test_run_with_timeout_returns_none_on_timeout():
    """超時的 coroutine 應回傳 None 而非拋異常"""
    async def slow_task():
        await asyncio.sleep(10)
        return "should not reach"

    result = await scheduler._run_with_timeout(slow_task(), timeout=0.1, label="SlowTest")
    assert result is None


async def test_run_with_timeout_returns_none_on_exception():
    """拋異常的 coroutine 應回傳 None（不讓錯誤冒泡）"""
    async def broken_task():
        raise ValueError("something broke")

    result = await scheduler._run_with_timeout(broken_task(), timeout=5, label="BrokenTest")
    assert result is None


async def test_run_with_timeout_zero_timeout():
    """timeout=0 應立刻超時（邊界條件）"""
    async def any_task():
        return "hi"

    result = await scheduler._run_with_timeout(any_task(), timeout=0, label="ZeroTimeout")
    # timeout=0 在 asyncio 中行為是「如果沒有立即完成就超時」
    # 結果可能是 None 或 "hi"，但不應拋異常
    assert result is None or result == "hi"


# ── update_steam cascade failure 防護 ────────────────


async def test_update_steam_saves_snapshots():
    """update_steam 正常流程：fetch 成功 → 存 snapshot"""
    mock_games = [
        {"appid": 730, "name": "CS2", "current_players": 1000000},
        {"appid": 570, "name": "Dota 2", "current_players": 500000},
    ]

    # 先 init DB（conftest 已設定 tmp DB path）
    import database
    await database.init_db()

    with patch("scheduler.steam_scraper.fetch_top_games", new_callable=AsyncMock, return_value=mock_games):
        await scheduler.update_steam()

    result = await database.get_history("steam", "730")
    assert len(result) == 1
    assert result[0]["value"] == 1000000


async def test_update_steam_handles_fetch_failure():
    """fetch 失敗（回傳 None）時 update_steam 不應崩潰"""
    import database
    await database.init_db()

    with patch("scheduler.steam_scraper.fetch_top_games", new_callable=AsyncMock, return_value=None):
        # 不應拋異常
        await scheduler.update_steam()

    # DB 應該是空的
    result = await database.get_history("steam", "730")
    assert result == []


async def test_update_steam_handles_timeout():
    """steam_scraper timeout 時 update_steam 不應崩潰，也不應存資料"""
    import database
    await database.init_db()

    async def slow_fetch():
        await asyncio.sleep(10)

    with patch("scheduler.steam_scraper.fetch_top_games", side_effect=slow_fetch):
        with patch.object(scheduler, "_run_with_timeout", new_callable=AsyncMock, return_value=None):
            await scheduler.update_steam()

    result = await database.get_history("steam", "730")
    assert result == []


# ── update_twitch cascade failure 防護 ───────────────


async def test_update_twitch_filters_zero_viewers():
    """update_twitch 應跳過 viewer_count=0 的遊戲"""
    mock_games = [
        {"id": "1", "name": "Game A", "viewer_count": 5000},
        {"id": "2", "name": "Game B", "viewer_count": 0},
    ]

    import database
    await database.init_db()

    with patch("scheduler.twitch_scraper.fetch_top_games", new_callable=AsyncMock, return_value=mock_games):
        await scheduler.update_twitch()

    result_a = await database.get_history("twitch", "1")
    result_b = await database.get_history("twitch", "2")
    assert len(result_a) == 1
    assert len(result_b) == 0, "zero-viewer game should not be saved"


async def test_update_twitch_handles_fetch_failure():
    """Twitch fetch 失敗時不應崩潰"""
    import database
    await database.init_db()

    with patch("scheduler.twitch_scraper.fetch_top_games", new_callable=AsyncMock, return_value=None):
        await scheduler.update_twitch()

    result = await database.get_history("twitch", "1")
    assert result == []


# ── cascade failure 防護（整合） ──────────────────────


async def test_multiple_jobs_independent():
    """一個 job 失敗不應影響其他 job 的執行"""
    import database
    await database.init_db()

    # Steam 失敗
    with patch("scheduler.steam_scraper.fetch_top_games", new_callable=AsyncMock, side_effect=RuntimeError("Steam down")):
        result = await scheduler._run_with_timeout(
            scheduler.steam_scraper.fetch_top_games(), timeout=5, label="Steam"
        )
    assert result is None  # 錯誤被吞掉

    # Twitch 正常 — 不受 Steam 失敗影響
    mock_twitch = [{"id": "1", "name": "Game", "viewer_count": 1000}]
    with patch("scheduler.twitch_scraper.fetch_top_games", new_callable=AsyncMock, return_value=mock_twitch):
        await scheduler.update_twitch()

    result = await database.get_history("twitch", "1")
    assert len(result) == 1, "Twitch should work even if Steam failed"
