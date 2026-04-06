"""
weekly_digest_scraper.py 測試 — 分類邏輯、名稱匹配、去重、YouTube API 解析
聚焦可單元測試的純函式 + YouTube 搜尋的 mock 測試
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers import weekly_digest_scraper


# ── fixtures ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    """隔離快取目錄"""
    cache_dir = str(tmp_path / "cache")
    monkeypatch.setattr(weekly_digest_scraper, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(weekly_digest_scraper, "CACHE_FILE", str(tmp_path / "cache" / "weekly_digest.json"))


# ── helpers ──────────────────────────────────────────

def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


# ── _classify_item ───────────────────────────────────

def test_classify_item_ad():
    """含廣告關鍵字應分類為 ad"""
    tags = weekly_digest_scraper._classify_item("原神 全新廣告 CM 上線")
    assert "ad" in tags


def test_classify_item_event():
    """含活動關鍵字應分類為 event"""
    tags = weekly_digest_scraper._classify_item("崩壞：星穹鐵道 周年慶活動登場")
    assert "event" in tags


def test_classify_item_collab():
    """含聯名關鍵字應分類為 collab"""
    tags = weekly_digest_scraper._classify_item("傳說對決 x 鬼滅之刃 聯名合作")
    assert "collab" in tags


def test_classify_item_multiple_tags():
    """同時含多種關鍵字應回傳多個 tag"""
    tags = weekly_digest_scraper._classify_item("原神 周年慶活動 聯名 廣告大使")
    assert "event" in tags
    assert "collab" in tags
    assert "ad" in tags


def test_classify_item_no_match_returns_news():
    """無匹配關鍵字時預設為 news"""
    tags = weekly_digest_scraper._classify_item("一般遊戲討論文章")
    assert tags == ["news"]


def test_classify_item_uses_summary():
    """也會檢查 summary 參數"""
    tags = weekly_digest_scraper._classify_item("原神新消息", "限定活動即將開跑")
    assert "event" in tags


# ── _title_contains_game ─────────────────────────────

def test_title_contains_game_exact_match():
    """標題包含完整遊戲名稱"""
    assert weekly_digest_scraper._title_contains_game("原神 2.0 版本更新", "原神") is True


def test_title_contains_game_case_insensitive():
    """英文名稱不分大小寫"""
    assert weekly_digest_scraper._title_contains_game("New Genshin Impact Event", "Genshin Impact") is True


def test_title_contains_game_alias_match():
    """透過 TAG_ALIASES 別名匹配"""
    assert weekly_digest_scraper._title_contains_game("FGO 新活動公告", "Fate/Grand Order") is True


def test_title_contains_game_cjk_match():
    """CJK 核心字匹配（至少 2 字中文）"""
    assert weekly_digest_scraper._title_contains_game("星穹鐵道全新版本", "崩壞：星穹鐵道") is True


def test_title_contains_game_no_match():
    """完全無關的標題"""
    assert weekly_digest_scraper._title_contains_game("天氣預報今日晴", "原神") is False


def test_title_contains_game_substring_match():
    """game_name 是標題子字串時，第一層直接匹配即通過"""
    # "神" 在 "神奇寶貝最新消息" 中 → 第一層 `game_name.lower() in t` 就匹配
    assert weekly_digest_scraper._title_contains_game("神奇寶貝最新消息", "神") is True


def test_title_contains_game_no_cjk_fallback():
    """CJK 核心字不足 2 字且無直接匹配時回傳 False"""
    # "X" 不在標題中，CJK 提取為空，無別名 → False
    assert weekly_digest_scraper._title_contains_game("完全無關的內容", "X") is False


# ── _clean_game_name ─────────────────────────────────

def test_clean_game_name_removes_prefix():
    """去掉發行商前綴"""
    assert weekly_digest_scraper._clean_game_name("Garena 傳說對決") == "傳說對決"


def test_clean_game_name_removes_subtitle():
    """去掉副標題（：分隔）"""
    assert weekly_digest_scraper._clean_game_name("崩壞：星穹鐵道") == "崩壞"


def test_clean_game_name_preserves_short_names():
    """短名稱（< 2 字）不截斷"""
    # "A - Something" 中 "A" 只有 1 字，不足 2 字門檻，不截斷
    assert weekly_digest_scraper._clean_game_name("A - Something Else") == "A - Something Else"


def test_clean_game_name_strips_whitespace():
    """去除前後空白"""
    assert weekly_digest_scraper._clean_game_name("  原神  ") == "原神"


# ── _dedup_items ─────────────────────────────────────

def test_dedup_items_removes_duplicates():
    """相同標題前 20 字視為重複"""
    # 前 20 字完全相同，第 21 字後才不同
    base = "原神二點零版本更新活動即將登場正式上線中"  # 正好 20 字
    items = [
        {"title": base + "搶先看影片完整版", "source": "YouTube"},
        {"title": base + "全攻略整理", "source": "Google News"},
        {"title": "傳說對決新賽季開始", "source": "4Gamers"},
    ]
    result = weekly_digest_scraper._dedup_items(items)
    assert len(result) == 2
    assert result[0]["source"] == "YouTube"  # 保留第一個
    assert result[1]["title"] == "傳說對決新賽季開始"


def test_dedup_items_empty_list():
    """空列表回傳空列表"""
    assert weekly_digest_scraper._dedup_items([]) == []


def test_dedup_items_short_titles():
    """短標題（< 20 字）也能正確去重"""
    items = [
        {"title": "原神活動", "source": "A"},
        {"title": "原神活動", "source": "B"},
    ]
    result = weekly_digest_scraper._dedup_items(items)
    assert len(result) == 1


# ── _search_youtube ──────────────────────────────────

async def test_search_youtube_no_api_key(monkeypatch):
    """沒有 YOUTUBE_API_KEY 時回傳空列表"""
    monkeypatch.setenv("YOUTUBE_API_KEY", "")

    mock_client = AsyncMock()
    since = datetime.now(timezone.utc) - timedelta(days=14)
    result = await weekly_digest_scraper._search_youtube(mock_client, "原神", since)

    assert result == []
    mock_client.get.assert_not_called()


async def test_search_youtube_parses_results(monkeypatch):
    """正確解析 YouTube API 回應並過濾"""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test_key_123")

    yt_response = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "原神 周年慶活動 官方PV",
                    "channelTitle": "原神官方頻道",
                    "publishedAt": "2026-03-28T10:00:00Z",
                    "thumbnails": {
                        "medium": {"url": "https://i.ytimg.com/vi/abc123/mqdefault.jpg"},
                    },
                },
            },
            {
                "id": {"videoId": "def456"},
                "snippet": {
                    "title": "原神 實況直播 攻略",  # 應被排除（實況/攻略）
                    "channelTitle": "遊戲實況主",
                    "publishedAt": "2026-03-27T08:00:00Z",
                    "thumbnails": {},
                },
            },
            {
                "id": {"videoId": "ghi789"},
                "snippet": {
                    "title": "完全無關的影片",  # 應被排除（不含遊戲名稱）
                    "channelTitle": "其他頻道",
                    "publishedAt": "2026-03-26T06:00:00Z",
                    "thumbnails": {},
                },
            },
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(json_data=yt_response))

    since = datetime(2026, 3, 20, tzinfo=timezone.utc)
    result = await weekly_digest_scraper._search_youtube(mock_client, "原神", since)

    # 只有第一個符合（含行銷關鍵字 + 遊戲名稱，不含排除詞）
    assert len(result) == 1
    assert result[0]["url"] == "https://www.youtube.com/watch?v=abc123"
    assert result[0]["source"] == "YouTube"
    assert result[0]["thumbnail"] == "https://i.ytimg.com/vi/abc123/mqdefault.jpg"
    assert "event" in result[0]["tags"]  # 周年慶活動 → event


async def test_search_youtube_deduplicates(monkeypatch):
    """相同 videoId 出現在不同查詢中應去重"""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test_key")

    yt_response = {
        "items": [
            {
                "id": {"videoId": "same_video"},
                "snippet": {
                    "title": "原神 限定活動 廣告PV",
                    "channelTitle": "原神",
                    "publishedAt": "2026-03-28T10:00:00Z",
                    "thumbnails": {"medium": {"url": "https://example.com/thumb.jpg"}},
                },
            },
        ]
    }

    mock_client = AsyncMock()
    # 兩次查詢都回傳相同影片
    mock_client.get = AsyncMock(return_value=_mock_response(json_data=yt_response))

    since = datetime(2026, 3, 20, tzinfo=timezone.utc)
    result = await weekly_digest_scraper._search_youtube(mock_client, "原神", since)

    # 應該去重為 1 個
    assert len(result) == 1


async def test_search_youtube_api_error_returns_partial(monkeypatch):
    """API 錯誤時不崩潰，回傳已取得的結果"""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test_key")

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_response(json_data={
                "items": [{
                    "id": {"videoId": "v1"},
                    "snippet": {
                        "title": "原神 活動限定 廣告CM",
                        "channelTitle": "原神",
                        "publishedAt": "2026-03-28T10:00:00Z",
                        "thumbnails": {"medium": {"url": ""}},
                    },
                }]
            })
        raise Exception("API quota exceeded")

    mock_client = AsyncMock()
    mock_client.get = mock_get

    since = datetime(2026, 3, 20, tzinfo=timezone.utc)
    result = await weekly_digest_scraper._search_youtube(mock_client, "原神", since)

    # 第一次查詢成功，第二次失敗，應回傳第一次的結果
    assert len(result) >= 1


async def test_search_youtube_non_200_skips(monkeypatch):
    """非 200 回應碼應跳過該查詢"""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test_key")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(status_code=403))

    since = datetime(2026, 3, 20, tzinfo=timezone.utc)
    result = await weekly_digest_scraper._search_youtube(mock_client, "原神", since)

    assert result == []


# ── _get_search_range ────────────────────────────────

def test_get_search_range_returns_14_days():
    """搜尋範圍應為 14 天"""
    start, end = weekly_digest_scraper._get_search_range()
    diff = end - start
    assert diff.days == 14


# ── cache functions ──────────────────────────────────

def test_load_cache_missing_file():
    """cache 不存在時回傳預設結構"""
    result = weekly_digest_scraper._load_cache()
    assert result == {"digest": [], "game_count": 0, "total_items": 0}
