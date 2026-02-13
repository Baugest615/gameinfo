"""
APScheduler 定時排程
每 10 分鐘更新所有資料來源
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
    """啟動定時排程（每 10 分鐘更新）"""
    # Phase 1: 核心數據
    scheduler.add_job(update_steam, "interval", minutes=10, id="steam", replace_existing=True)
    scheduler.add_job(update_twitch, "interval", minutes=10, id="twitch", replace_existing=True)
    scheduler.add_job(update_discussions, "interval", minutes=10, id="discussions", replace_existing=True)

    # Phase 2: 新聞 + 手遊
    scheduler.add_job(update_news, "interval", minutes=10, id="news", replace_existing=True)
    scheduler.add_job(update_mobile, "interval", minutes=30, id="mobile", replace_existing=True)  # 手遊排行更新慢，30分鐘

    scheduler.start()
    print("[Scheduler] Started - updating every 10 minutes")


def stop_scheduler():
    """停止排程"""
    scheduler.shutdown(wait=False)
    print("[Scheduler] Stopped")
