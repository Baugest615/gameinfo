"""
Twitch 即時串流數據模組
- 中文語言 (language=zh) 熱門遊戲排行（涵蓋台灣/香港直播主）
"""
import asyncio
import httpx
import json
import os
import time

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "twitch_data.json")


def _get_client_id():
    return os.getenv("TWITCH_CLIENT_ID", "")

def _get_client_secret():
    return os.getenv("TWITCH_CLIENT_SECRET", "")

_token_cache = {"access_token": None, "expires_at": 0}
_token_lock = asyncio.Lock()


async def _get_access_token():
    """使用 Client Credentials Flow 取得 Twitch OAuth Token（async lock 防止並發重複刷新）"""
    global _token_cache

    async with _token_lock:
        if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
            return _token_cache["access_token"]

        if not _get_client_id() or not _get_client_secret():
            print("[Twitch] Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET")
            return None

        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": _get_client_id(),
            "client_secret": _get_client_secret(),
            "grant_type": "client_credentials"
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                _token_cache["access_token"] = data["access_token"]
                _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600) - 60
                return data["access_token"]
        except Exception as e:
            print(f"[Twitch] Error getting access token: {e}")
            return None


async def fetch_top_games(limit=20):
    """取得中文直播最熱門遊戲 Top N（language=zh，含台灣/香港直播主）"""
    token = await _get_access_token()

    if not token:
        print("[Twitch] No token available, returning cached data")
        return _load_cache().get("games", _get_demo_data())

    try:
        # 1. 抓取中文語言串流（language=zh 涵蓋繁體中文台灣/香港）
        streams = await _fetch_zh_streams(token, count=100)
        if not streams:
            return _load_cache().get("games", _get_demo_data())

        # 2. 依遊戲聚合觀看人數
        game_viewers = {}
        for s in streams:
            gid = s.get("game_id")
            if not gid:
                continue
            game_viewers[gid] = game_viewers.get(gid, 0) + s.get("viewer_count", 0)

        # 3. 取 Top limit 遊戲
        top_game_ids = sorted(game_viewers, key=lambda x: game_viewers[x], reverse=True)[:limit]

        # 4. 批次取得遊戲名稱與封面（單次請求）
        game_info = await _fetch_game_info(top_game_ids, token)

        games = []
        for i, gid in enumerate(top_game_ids, 1):
            info = game_info.get(gid, {})
            games.append({
                "rank": i,
                "id": gid,
                "name": info.get("name", f"Game {gid}"),
                "box_art_url": info.get("box_art_url", "").replace("{width}", "144").replace("{height}", "192"),
                "viewer_count": game_viewers[gid],
            })

        _save_cache({"games": games, "updated_at": int(time.time())})
        return games

    except Exception as e:
        print(f"[Twitch] Error fetching top games: {e}")
        return _load_cache().get("games", _get_demo_data())


async def _fetch_zh_streams(token, count=100):
    """抓取中文語言串流（最多 100 筆，依觀看人數降序）"""
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": _get_client_id(),
    }
    params = {"language": "zh", "first": min(count, 100)}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception as e:
        print(f"[Twitch] Error fetching zh streams: {e}")
        return []


async def _fetch_game_info(game_ids, token):
    """批次取得遊戲名稱與封面（單次請求，最多 100 個）"""
    if not game_ids:
        return {}
    url = "https://api.twitch.tv/helix/games"
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": _get_client_id(),
    }
    result = {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            params = [("id", gid) for gid in game_ids[:100]]
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            for item in resp.json().get("data", []):
                result[item["id"]] = {
                    "name": item["name"],
                    "box_art_url": item.get("box_art_url", ""),
                }
    except Exception as e:
        print(f"[Twitch] Error fetching game info: {e}")
    return result


def _get_demo_data():
    """無 API Key 時的示範數據"""
    return [
        {"rank": 1, "id": "0", "name": "League of Legends", "box_art_url": "", "viewer_count": 0},
        {"rank": 2, "id": "0", "name": "Valorant", "box_art_url": "", "viewer_count": 0},
        {"rank": 3, "id": "0", "name": "GTA V", "box_art_url": "", "viewer_count": 0},
    ]


def _save_cache(data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
