"""
database.py 測試 — DB snapshot 完整性
覆蓋：init_db / save_snapshot / get_history / cleanup_old_data / 邊界條件
"""
import time
from unittest.mock import patch

import aiosqlite
import pytest

import database


# ── init_db ──────────────────────────────────────────


async def test_init_db_creates_table():
    """init_db 應建立 history table 及索引"""
    await database.init_db()
    async with aiosqlite.connect(database.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
        )
        row = await cursor.fetchone()
    assert row is not None, "history table should exist"


async def test_init_db_idempotent():
    """重複呼叫 init_db 不應報錯（CREATE TABLE IF NOT EXISTS）"""
    await database.init_db()
    await database.init_db()  # 第二次不應拋異常


async def test_init_db_creates_indexes():
    """init_db 應建立 idx_source_game 和 idx_recorded_at 索引"""
    await database.init_db()
    async with aiosqlite.connect(database.DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
    assert "idx_source_game" in indexes
    assert "idx_recorded_at" in indexes


# ── save_snapshot ────────────────────────────────────


async def test_save_snapshot_inserts_record():
    """save_snapshot 應正確寫入一筆資料"""
    await database.init_db()
    await database.save_snapshot("steam", "730", "Counter-Strike 2", 1200000)

    async with aiosqlite.connect(database.DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM history")
        rows = await cursor.fetchall()
    assert len(rows) == 1
    # columns: id, source, game_id, game_name, value, recorded_at
    assert rows[0][1] == "steam"
    assert rows[0][2] == "730"
    assert rows[0][3] == "Counter-Strike 2"
    assert rows[0][4] == 1200000


async def test_save_snapshot_records_current_time():
    """save_snapshot 的 recorded_at 應接近當前時間"""
    await database.init_db()
    before = int(time.time())
    await database.save_snapshot("twitch", "123", "Game", 5000)
    after = int(time.time())

    async with aiosqlite.connect(database.DB_PATH) as db:
        cursor = await db.execute("SELECT recorded_at FROM history")
        row = await cursor.fetchone()
    assert before <= row[0] <= after


async def test_save_snapshot_multiple_sources():
    """不同 source 的 snapshot 應獨立儲存"""
    await database.init_db()
    await database.save_snapshot("steam", "730", "CS2", 100)
    await database.save_snapshot("twitch", "730", "CS2", 200)

    async with aiosqlite.connect(database.DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM history")
        count = (await cursor.fetchone())[0]
    assert count == 2


# ── get_history ──────────────────────────────────────


async def test_get_history_returns_matching_records():
    """get_history 應回傳指定 source + game_id 的資料"""
    await database.init_db()
    await database.save_snapshot("steam", "730", "CS2", 100)
    await database.save_snapshot("steam", "570", "Dota 2", 200)
    await database.save_snapshot("twitch", "730", "CS2", 300)

    result = await database.get_history("steam", "730")
    assert len(result) == 1
    assert result[0]["game_name"] == "CS2"
    assert result[0]["value"] == 100


async def test_get_history_respects_days_filter():
    """get_history 只回傳 days 天內的資料"""
    await database.init_db()
    now = int(time.time())

    async with aiosqlite.connect(database.DB_PATH) as db:
        # 3 天前的資料
        await db.execute(
            "INSERT INTO history (source, game_id, game_name, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("steam", "730", "CS2", 100, now - 3 * 86400),
        )
        # 10 天前的資料
        await db.execute(
            "INSERT INTO history (source, game_id, game_name, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("steam", "730", "CS2", 50, now - 10 * 86400),
        )
        await db.commit()

    result = await database.get_history("steam", "730", days=7)
    assert len(result) == 1
    assert result[0]["value"] == 100


async def test_get_history_caps_days_at_30():
    """get_history 的 days 參數上限 30 天"""
    await database.init_db()
    now = int(time.time())

    async with aiosqlite.connect(database.DB_PATH) as db:
        # 25 天前 — 在 30 天內
        await db.execute(
            "INSERT INTO history (source, game_id, game_name, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("steam", "730", "CS2", 100, now - 25 * 86400),
        )
        # 35 天前 — 超出 30 天上限
        await db.execute(
            "INSERT INTO history (source, game_id, game_name, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("steam", "730", "CS2", 50, now - 35 * 86400),
        )
        await db.commit()

    # 即使 days=60，也只查 30 天
    result = await database.get_history("steam", "730", days=60)
    assert len(result) == 1
    assert result[0]["value"] == 100


async def test_get_history_empty_result():
    """查無資料時應回傳空列表"""
    await database.init_db()
    result = await database.get_history("steam", "nonexistent")
    assert result == []


async def test_get_history_ordered_by_time():
    """get_history 應按 recorded_at 升序排列"""
    await database.init_db()
    now = int(time.time())

    async with aiosqlite.connect(database.DB_PATH) as db:
        for i in range(3):
            await db.execute(
                "INSERT INTO history (source, game_id, game_name, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
                ("steam", "730", "CS2", (i + 1) * 100, now - (2 - i) * 3600),
            )
        await db.commit()

    result = await database.get_history("steam", "730")
    values = [r["value"] for r in result]
    assert values == [100, 200, 300], "should be ordered oldest to newest"


# ── cleanup_old_data ─────────────────────────────────


async def test_cleanup_removes_old_data():
    """cleanup_old_data 應刪除超過 90 天的資料"""
    await database.init_db()
    now = int(time.time())

    async with aiosqlite.connect(database.DB_PATH) as db:
        # 91 天前 — 應被清除
        await db.execute(
            "INSERT INTO history (source, game_id, game_name, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("steam", "730", "CS2", 50, now - 91 * 86400),
        )
        # 89 天前 — 應保留
        await db.execute(
            "INSERT INTO history (source, game_id, game_name, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("steam", "730", "CS2", 100, now - 89 * 86400),
        )
        # 今天 — 應保留
        await db.execute(
            "INSERT INTO history (source, game_id, game_name, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("steam", "730", "CS2", 200, now),
        )
        await db.commit()

    await database.cleanup_old_data()

    async with aiosqlite.connect(database.DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM history ORDER BY recorded_at")
        rows = await cursor.fetchall()
    values = [r[0] for r in rows]
    assert values == [100, 200], "91-day-old record should be deleted"


async def test_cleanup_on_empty_db():
    """空 DB 執行 cleanup 不應報錯"""
    await database.init_db()
    await database.cleanup_old_data()  # 不應拋異常
