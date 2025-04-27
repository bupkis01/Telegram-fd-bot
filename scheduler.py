from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import json

from telegram_bot import send_fixtures, send_results, send_keepalive, send_message
from get_fixtures import get_fixtures
from storage import save_match_to_db, get_tracked_matches, remove_match_from_db
from config import PERSONAL_CHAT_ID

IST = pytz.timezone("Asia/Kolkata")

def load_leagues():
    try:
        with open("league_ids.json") as f:
            return json.load(f)["leagues"]
    except Exception as e:
        print(f"[{datetime.now(IST)}] ❌ Failed to load league IDs: {e}")
        return []

def post_daily_fixtures():
    fixtures = []
    for league in load_leagues():
        fixtures.extend(get_fixtures(league=league, filter_by_window=True))

    if not fixtures:
        print(f"[{datetime.now(IST)}] ℹ️ No fixtures to post today.")
        return

    send_fixtures(fixtures)
    for m in fixtures:
        save_match_to_db(m)
        send_message(
            text=f"🔖 Tracking match: {m['home']} vs {m['away']} at {m['local_time']}",
            chat_id=PERSONAL_CHAT_ID
        )

def post_results():
    finished = []
    for stored in get_tracked_matches():
        # skip if we never saved a valid datetime
        if not stored.get("utc_datetime"):
            continue

        # derive ESPN’s YYYYMMDD from the saved ISO timestamp
        dt = datetime.fromisoformat(stored["utc_datetime"])
        espn_date = dt.strftime("%Y%m%d")

        # fetch that exact day’s scoreboard
        all_events = get_fixtures(
            league=stored["league"],
            filter_by_window=False,
            espn_date=espn_date,
        )

        # see if this match just turned FINAL
        updated = next(
            (e for e in all_events if e["match_id"] == stored["match_id"]),
            None
        )
        if updated and updated["status"] == "STATUS_FINAL":
            finished.append(updated)
            remove_match_from_db(stored)

    if finished:
        send_results(finished)
    else:
        print(f"[{datetime.now(IST)}] ℹ️ No results to post right now.")

def start():
    try:
        scheduler = BackgroundScheduler(timezone=IST)
        scheduler.add_job(post_daily_fixtures, "cron", hour=22, minute=0)
        scheduler.add_job(post_results, "interval", minutes=15)
        scheduler.add_job(send_keepalive, "interval", minutes=4)
        scheduler.start()
        print(f"[{datetime.now(IST)}] ⏱️ Scheduler started...")
    except Exception as e:
        print(f"[{datetime.now(IST)}] ❌ Scheduler failed to start: {e}")

if __name__ == "__main__":
    start()
