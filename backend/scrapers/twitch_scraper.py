"""
Twitch 即時串流數據模組
- 熱門遊戲觀看排行
"""
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


async def _get_access_token():
    """使用 Client Credentials Flow 取得 Twitch OAuth Token"""
    global _token_cache

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
    """取得 Twitch 最熱門遊戲 Top N（依觀看人數）"""
    token = await _get_access_token()

    if not token:
        print("[Twitch] No token available, returning cached data")
        return _load_cache().get("games", _get_demo_data())

    url = "https://api.twitch.tv/helix/games/top"
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": _get_client_id(),
    }
    params = {"first": min(limit, 100)}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        games = []
        for i, item in enumerate(data.get("data", []), 1):
            games.append({
                "rank": i,
                "id": item["id"],
                "name": item["name"],
                "box_art_url": item.get("box_art_url", "").replace("{width}", "144").replace("{height}", "192"),
            })

        # 取得各遊戲的串流數據（觀看人數）
        games = await _enrich_with_viewer_counts(games, token)

        _save_cache({"games": games, "updated_at": int(time.time())})
        return games

    except Exception as e:
        print(f"[Twitch] Error fetching top games: {e}")
        return _load_cache().get("games", _get_demo_data())


async def _enrich_with_viewer_counts(games, token):
    """為每個遊戲加上觀看人數"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for game in games:
                url = "https://api.twitch.tv/helix/streams"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Client-Id": _get_client_id(),
                }
                params = {"game_id": game["id"], "first": 1}
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    streams = resp.json().get("data", [])
                    # 用 Twitch 的排行順序作為人氣指標
                    game["viewer_count"] = sum(s.get("viewer_count", 0) for s in streams)
    except Exception:
        pass
    return games


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
