"""
APScheduler 定時排程
- Steam / 新聞：每 30 分鐘
- Twitch：每 15 分鐘
- 巴哈/PTT 討論：每 60 分鐘
- 手遊排行：每 180 分鐘
"""
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from scrapers import steam_scraper, twitch_scraper, discussion_scraper, news_scraper, mobile_scraper

scheduler = BackgroundScheduler()


def _run_async(coro):
    """在背景執行緒中執行 async 函式"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)
        loop.close()
    except Exception as e:
        print(f"[Scheduler] Error: {e}")


def update_steam():
    print("[Scheduler] Updating Steam data...")
    _run_async(steam_scraper.fetch_top_games())


def update_twitch():
    print("[Scheduler] Updating Twitch data...")
    _run_async(twitch_scraper.fetch_top_games())


def update_discussions():
    print("[Scheduler] Updating discussions...")
    _run_async(discussion_scraper.fetch_all_discussions())


def update_news():
    print("[Scheduler] Updating news...")
    _run_async(news_scraper.aggregate_news())


def update_mobile():
    print("[Scheduler] Updating mobile rankings...")
    _run_async(mobile_scraper.fetch_all_mobile())


def start_scheduler():
    """啟動定時排程"""
    scheduler.add_job(update_steam, "interval", minutes=30, id="steam", replace_existing=True)
    scheduler.add_job(update_twitch, "interval", minutes=15, id="twitch", replace_existing=True)
    scheduler.add_job(update_discussions, "interval", minutes=60, id="discussions", replace_existing=True)
    scheduler.add_job(update_news, "interval", minutes=30, id="news", replace_existing=True)
    scheduler.add_job(update_mobile, "interval", minutes=180, id="mobile", replace_existing=True)

    scheduler.start()
    print("[Scheduler] Started - Steam/News: 30min, Twitch: 15min, Discussions: 60min, Mobile: 180min")


def stop_scheduler():
    """停止排程"""
    scheduler.shutdown(wait=False)
    print("[Scheduler] Stopped")
