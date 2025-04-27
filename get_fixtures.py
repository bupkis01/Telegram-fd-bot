import requests
from datetime import datetime, timedelta
import pytz
from typing import Optional
from dateutil import parser as _p2

ESPN_FIXTURES_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{}/scoreboard"
IST = pytz.timezone("Asia/Kolkata")

def is_within_custom_window(match_time_utc):
    now_ist = datetime.now(IST)
    start_window = now_ist.replace(hour=22, minute=0, second=0, microsecond=0)
    if now_ist.hour < 22:
        start_window -= timedelta(days=1)
    end_window = start_window + timedelta(days=1) - timedelta(minutes=1)
    match_time_ist = match_time_utc.astimezone(IST)
    return start_window <= match_time_ist <= end_window

def convert_match_time(iso_time):
    try:
        # first try strict ISO
        utc_time = datetime.fromisoformat(iso_time[:-1]).replace(tzinfo=pytz.utc)
    except Exception:
        # fallback to dateutil’s more permissive parser
        try:
            utc_time = _p2.parse(iso_time)
        except Exception as e:
            print(f"⚠️ Time conversion error: {e}")
            return "Unknown", None

    local_time = utc_time.astimezone(IST)
    return local_time.strftime("%H:%M"), utc_time

def get_fixtures(
    league: str = "eng.1",
    filter_by_window: bool = False,
    espn_date: Optional[str] = None,  # new: YYYYMMDD
) -> list:
    """
    If espn_date is given, pass it as the 'dates' param to ESPN,
    otherwise fetch the default (today).
    """
    try:
        print(f"📡 Fetching fixtures for {league} (date={espn_date})…")
        params = {}
        if espn_date:
            params["dates"] = espn_date

        response = requests.get(
            ESPN_FIXTURES_URL.format(league),
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        events = data.get("events", [])

        fixtures = []
        for event in events:
            try:
                comp = event["competitions"][0]
                match_time = comp["date"]
                local_time, match_time_utc = convert_match_time(match_time)

                if filter_by_window and (not match_time_utc or not is_within_custom_window(match_time_utc)):
                    continue

                home = next(t for t in comp["competitors"] if t["homeAway"] == "home")
                away = next(t for t in comp["competitors"] if t["homeAway"] == "away")

                fixtures.append({
                    "match_id":      event["id"],
                    "home":          home["team"]["displayName"],
                    "away":          away["team"]["displayName"],
                    "local_time":    local_time,
                    "utc_time":      match_time_utc.strftime("%H:%M") if match_time_utc else "Unknown",
                    "status":        event["status"]["type"]["name"].upper(),
                    "league":        data.get("leagues", [{}])[0].get("name", "Unknown League"),
                    "home_score":    int(home.get("score", 0)),
                    "away_score":    int(away.get("score", 0)),
                    "utc_datetime":  match_time_utc.isoformat() if match_time_utc else ""
                })
            except KeyError as e:
                print(f"⚠️ Missing data in API response: {e}")
                continue

        # dedupe
        unique = {m["match_id"]: m for m in fixtures}
        final = list(unique.values())
        print(f"✅ {len(final)} fixtures fetched.")
        return final

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching fixtures: {e}")
        return []
