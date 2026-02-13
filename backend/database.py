"""
SQLite 歷史數據模組
記錄 Steam / Twitch 遊戲的歷史人數快照，供趨勢圖使用
"""
import aiosqlite
import time
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "cache", "history.db")
KEEP_DAYS = 90  # 保留最近 90 天


async def init_db():
    """初始化資料庫，建立 history table"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                game_id TEXT NOT NULL,
                game_name TEXT NOT NULL,
                value INTEGER NOT NULL,
                recorded_at INTEGER NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_source_game ON history (source, game_id)"
        )
        await db.commit()
    print(f"[DB] Initialized history.db at {DB_PATH}")


async def save_snapshot(source: str, game_id: str, game_name: str, value: int):
    """寫入一筆快照，並清除超過 90 天的舊資料"""
    now = int(time.time())
    cutoff = now - KEEP_DAYS * 86400
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO history (source, game_id, game_name, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
            (source, str(game_id), game_name, value, now),
        )
        await db.execute(
            "DELETE FROM history WHERE recorded_at < ?", (cutoff,)
        )
        await db.commit()


async def get_history(source: str, game_id: str, days: int = 7):
    """取得指定遊戲的歷史資料，依時間排序"""
    cutoff = int(time.time()) - min(days, 30) * 86400
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT game_name, value, recorded_at
            FROM history
            WHERE source = ? AND game_id = ? AND recorded_at >= ?
            ORDER BY recorded_at ASC
            """,
            (source, str(game_id), cutoff),
        )
        rows = await cursor.fetchall()
    return [{"game_name": r["game_name"], "value": r["value"], "recorded_at": r["recorded_at"]} for r in rows]
