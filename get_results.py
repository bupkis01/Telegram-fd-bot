from datetime import datetime
from get_fixtures import get_fixtures
from storage import get_tracked_matches, remove_match_from_db
from telegram_bot import send_results

def post_results():
    """Fetch and post any matches that have just finished."""
    finished = []
    for stored in get_tracked_matches():
        # skip if we never saved a valid datetime
        if not stored.get("utc_datetime"):
            continue

        # derive ESPN’s YYYYMMDD from the saved ISO timestamp
        dt = datetime.fromisoformat(stored["utc_datetime"])
        espn_date = dt.strftime("%Y%m%d")

        # fetch that exact day’s scoreboard using the stored league_code
        all_events = get_fixtures(
            league=stored["league_code"],
            filter_by_window=False,
            espn_date=espn_date,
        )

        # see if this match just turned FINAL
        updated = next(
            (e for e in all_events 
             if e["match_id"] == stored["match_id"] 
             and e["status"] == "STATUS_FINAL"),
            None
        )
        if updated:
            finished.append(updated)
            remove_match_from_db(stored)

    if finished:
        send_results(finished)
    else:
        print("ℹ️ No results to post right now.")
