# get_results.py

from datetime import datetime, timedelta
import pytz

from get_fixtures import get_fixtures
from storage import get_tracked_matches, remove_match_from_db
from telegram_bot import send_results

UTC = pytz.utc

def post_results():
    """Fetch and post any matches that have just finished (or clean up postponed)."""
    now_utc = datetime.now(UTC)
    finished = []

    for stored in get_tracked_matches():
        start_iso = stored.get("utc_datetime")
        league = stored.get("league_code")
        match_id = stored.get("match_id")

        # must have start time, league_code, match_id
        if not start_iso or not league or not match_id:
            print(f"⚠️ Skipping entry with missing data: {stored}")
            continue

        # parse stored start time (ISO with offset)
        try:
            start_dt = datetime.fromisoformat(start_iso)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=UTC)
            else:
                start_dt = start_dt.astimezone(UTC)
        except Exception as e:
            print(f"⚠️ Could not parse start time `{start_iso}`: {e}")
            continue

        # 1) Too early—match hasn’t started yet
        if now_utc < start_dt:
            continue

        # 2) Check for postponed: >15 min past start but still scheduled
        if now_utc >= start_dt + timedelta(minutes=15) and now_utc < start_dt + timedelta(minutes=110):
            espn_date = start_dt.strftime("%Y%m%d")
            events = get_fixtures(league=league, filter_by_window=False, espn_date=espn_date)
            ev = next((e for e in events if e["match_id"] == match_id), None)
            status = ev.get("status", "") if ev else ""
            if not ev or status.upper() in ("STATUS_SCHEDULED", "SCHEDULED"):
                print(f"ℹ️ Match {match_id} appears postponed—removing from tracking.")
                remove_match_from_db(stored)
            continue

        # 3) Ongoing window: from 15 min after start up to 110 min after start
        if start_dt + timedelta(minutes=15) <= now_utc < start_dt + timedelta(minutes=110):
            # still in play—wait until after 110 min
            continue

        # 4) Now >= start + 110 min: fetch final result
        espn_date = start_dt.strftime("%Y%m%d")
        events = get_fixtures(league=league, filter_by_window=False, espn_date=espn_date)
        updated = next(
            (e for e in events
             if e["match_id"] == match_id
             and (e["status"] in ("STATUS_FINAL", "FINAL")
                  or e.get("status_type", {}).get("completed"))),
            None
        )

        if updated:
            finished.append(updated)
            remove_match_from_db(stored)

    if finished:
        send_results(finished)
    else:
        print("ℹ️ No results to post right now.")
