"""
Steam 即時數據爬取模組
- 熱門遊戲排行 (免 API Key)
- 同時在線人數
"""
import asyncio
import httpx
import json
import os
import time

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "steam_data.json")


async def fetch_top_games():
    """取得 Steam 最多人同時在線的遊戲 Top 20"""
    url = "https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        ranks = data.get("response", {}).get("ranks", [])
        games = []
        # 取得遊戲名稱（需查 Steam store API）
        app_ids = [r["appid"] for r in ranks[:20]]
        names = await _batch_get_app_names(app_ids)

        for r in ranks[:20]:
            appid = r["appid"]
            games.append({
                "rank": r.get("rank", 0),
                "appid": appid,
                "name": names.get(appid, f"App {appid}"),
                "current_players": r.get("peak_in_game", 0),
                "peak_today": r.get("peak_in_game", 0),
            })

        # 寫入快取
        _save_cache({"games": games, "updated_at": int(time.time())})
        return games

    except Exception as e:
        print(f"[Steam] Error fetching top games: {e}")
        return _load_cache().get("games", [])


async def fetch_player_count(appid: int):
    """取得特定遊戲的目前在線人數"""
    url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", {}).get("player_count", 0)
    except Exception as e:
        print(f"[Steam] Error fetching player count for {appid}: {e}")
        return 0


async def _batch_get_app_names(app_ids: list):
    """批次取得遊戲名稱（並行查詢 + semaphore 限流）"""
    names = {}
    try:
        cached = _load_name_cache()
        to_fetch = [aid for aid in app_ids if aid not in cached]

        if to_fetch:
            sem = asyncio.Semaphore(5)

            async def _fetch_one(client, aid):
                async with sem:
                    try:
                        url = f"https://store.steampowered.com/api/appdetails?appids={aid}&l=tchinese"
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            d = resp.json()
                            app_data = d.get(str(aid), {})
                            if app_data.get("success"):
                                return (aid, app_data["data"]["name"])
                    except Exception:
                        pass
                    return (aid, None)

            async with httpx.AsyncClient(timeout=10) as client:
                results = await asyncio.gather(
                    *[_fetch_one(client, aid) for aid in to_fetch],
                    return_exceptions=True,
                )

            for r in results:
                if isinstance(r, tuple) and r[1] is not None:
                    cached[r[0]] = r[1]

            _save_name_cache(cached)

        names = {aid: cached.get(aid, f"App {aid}") for aid in app_ids}

    except Exception as e:
        print(f"[Steam] Error batch fetching names: {e}")

    return names


NAME_CACHE_FILE = os.path.join(CACHE_DIR, "steam_names.json")


def _load_name_cache():
    try:
        with open(NAME_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_name_cache(data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(NAME_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in data.items()}, f, ensure_ascii=False, indent=2)


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
