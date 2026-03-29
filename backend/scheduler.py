"""
APScheduler 定時排程（AsyncIOScheduler）
共用 FastAPI 的事件循環，避免多執行緒 + asyncio.run() 的問題
- Steam / 新聞：每 30 分鐘
- Twitch：每 15 分鐘
- 巴哈/PTT 討論：每 60 分鐘
- 手遊排行：每 180 分鐘
- 每周行銷摘要：每周一 06:00
- DB 清理：每日 03:00
"""
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scrapers import steam_scraper, twitch_scraper, discussion_scraper, news_scraper, mobile_scraper, weekly_digest_scraper
import database

scheduler = AsyncIOScheduler()


async def _run_with_timeout(coro, timeout, label):
    """執行 async 任務，加 timeout 保護"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        print(f"[Scheduler] {label} timeout after {timeout}s")
        return None
    except Exception as e:
        print(f"[Scheduler] {label} error: {e}")
        return None


async def update_steam():
    print("[Scheduler] Updating Steam data...")
    games = await _run_with_timeout(
        steam_scraper.fetch_top_games(), timeout=60, label="Steam"
    )
    if games:
        for game in games[:10]:
            await database.save_snapshot(
                "steam", str(game["appid"]), game["name"], game["current_players"]
            )


async def update_twitch():
    print("[Scheduler] Updating Twitch data...")
    games = await _run_with_timeout(
        twitch_scraper.fetch_top_games(), timeout=45, label="Twitch"
    )
    if games:
        for game in games[:10]:
            if game.get("viewer_count", 0) > 0:
                await database.save_snapshot(
                    "twitch", str(game["id"]), game["name"], game["viewer_count"]
                )


async def update_discussions():
    print("[Scheduler] Updating discussions...")
    await _run_with_timeout(
        discussion_scraper.fetch_all_discussions(), timeout=90, label="Discussions"
    )


async def update_news():
    print("[Scheduler] Updating news...")
    await _run_with_timeout(
        news_scraper.aggregate_news(), timeout=60, label="News"
    )


async def update_mobile():
    print("[Scheduler] Updating mobile rankings...")
    await _run_with_timeout(
        mobile_scraper.fetch_all_mobile(), timeout=120, label="Mobile"
    )


async def update_weekly_digest():
    print("[Scheduler] Updating weekly digest...")
    await _run_with_timeout(
        weekly_digest_scraper.fetch_weekly_digest(), timeout=300, label="WeeklyDigest"
    )


async def cleanup_db():
    print("[Scheduler] Cleaning up old DB snapshots...")
    await _run_with_timeout(
        database.cleanup_old_data(), timeout=60, label="DB Cleanup"
    )


async def _init_weekly_digest():
    """啟動時先確保依賴快取存在，再跑 weekly digest"""
    import os
    cache_dir = os.path.join(os.path.dirname(__file__), "cache")
    mobile_cache = os.path.join(cache_dir, "mobile_data.json")
    disc_cache = os.path.join(cache_dir, "discussion_data.json")

    if not os.path.exists(mobile_cache):
        print("[Scheduler] Init: fetching mobile data first...")
        await update_mobile()
    if not os.path.exists(disc_cache):
        print("[Scheduler] Init: fetching discussion data first...")
        await update_discussions()

    print("[Scheduler] Init: now fetching weekly digest...")
    await update_weekly_digest()


def start_scheduler():
    """啟動定時排程（錯開首次執行，避免同時搶資源）"""
    now = datetime.now()

    # 錯開啟動：輕量 job 先跑，重量 job 延後
    scheduler.add_job(update_steam, "interval", minutes=30, id="steam",
                      next_run_time=now + timedelta(seconds=10), replace_existing=True)
    scheduler.add_job(update_twitch, "interval", minutes=15, id="twitch",
                      next_run_time=now + timedelta(minutes=2), replace_existing=True)
    scheduler.add_job(update_news, "interval", minutes=30, id="news",
                      next_run_time=now + timedelta(minutes=4), replace_existing=True)
    scheduler.add_job(update_discussions, "interval", minutes=60, id="discussions",
                      next_run_time=now + timedelta(minutes=6), replace_existing=True)
    scheduler.add_job(update_mobile, "interval", minutes=180, id="mobile",
                      next_run_time=now + timedelta(minutes=10), replace_existing=True)
    scheduler.add_job(update_weekly_digest, "cron", day_of_week="mon", hour=6, minute=0,
                      id="weekly_digest", replace_existing=True)
    scheduler.add_job(cleanup_db, "cron", hour=3, minute=0,
                      id="db_cleanup", replace_existing=True)

    scheduler.start()

    # 首次啟動：若 weekly digest 快取不存在或為空，排程初始化
    import os, json
    cache_file = os.path.join(os.path.dirname(__file__), "cache", "weekly_digest.json")
    need_init = not os.path.exists(cache_file)
    if not need_init:
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("total_items", 0) == 0:
                need_init = True
        except Exception:
            need_init = True
    if need_init:
        scheduler.add_job(_init_weekly_digest, id="weekly_digest_init",
                          next_run_time=now + timedelta(minutes=15), replace_existing=True)
        print("[Scheduler] Weekly digest init queued (will run after 15min)")

    print("[Scheduler] Started (AsyncIO) - Steam:10s, Twitch:2min, News:4min, Discussions:6min, Mobile:10min")


def stop_scheduler():
    """停止排程"""
    scheduler.shutdown(wait=False)
    print("[Scheduler] Stopped")
