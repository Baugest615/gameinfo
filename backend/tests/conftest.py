"""
測試共用 fixtures — 使用 in-memory SQLite 隔離，不碰實際 DB
"""
import pytest
import database


@pytest.fixture(autouse=True)
def use_in_memory_db(tmp_path, monkeypatch):
    """每個測試使用獨立的臨時 DB 檔案（aiosqlite 不支援 :memory: 跨連線共享）"""
    db_path = str(tmp_path / "test_history.db")
    monkeypatch.setattr(database, "DB_PATH", db_path)
    return db_path
