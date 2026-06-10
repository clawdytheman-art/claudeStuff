"""Garmin Connect access.

Uses the community `garminconnect` library (which authenticates the same way
the official mobile app does, via garth/OAuth). Tokens are cached locally so
you only enter your password once; subsequent syncs reuse the token.
"""

from __future__ import annotations

import datetime as dt
import getpass
import sys

from . import store

try:
    from garminconnect import (
        Garmin,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
except ImportError:  # pragma: no cover
    print(
        "The 'garminconnect' package is required for syncing.\n"
        "Install it with:  pip install garminconnect",
        file=sys.stderr,
    )
    raise


def login_interactive() -> "Garmin":
    """Prompt for credentials, log in, and cache tokens for future use."""
    email = input("Garmin Connect email: ").strip()
    password = getpass.getpass("Garmin Connect password: ")
    client = Garmin(email=email, password=password, prompt_mfa=_prompt_mfa)
    client.login()
    store.TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    client.garth.dump(str(store.TOKEN_DIR))
    print(f"Logged in. Tokens cached in {store.TOKEN_DIR}")
    return client


def get_client() -> "Garmin":
    """Return a logged-in client, resuming from cached tokens if possible."""
    if store.TOKEN_DIR.exists():
        try:
            client = Garmin()
            client.login(str(store.TOKEN_DIR))
            return client
        except (GarminConnectAuthenticationError, FileNotFoundError, Exception):
            print("Cached login expired; please log in again.", file=sys.stderr)
    return login_interactive()


def _prompt_mfa() -> str:
    return input("MFA code: ").strip()


def fetch_sleep(client: "Garmin", days: int) -> list[dict]:
    """Fetch the last `days` nights and normalize them into flat records.

    Nights with no sleep data (watch not worn, etc.) are skipped.
    """
    records = []
    today = dt.date.today()
    for offset in range(days):
        date = today - dt.timedelta(days=offset)
        date_str = date.isoformat()
        try:
            raw = client.get_sleep_data(date_str)
        except (GarminConnectConnectionError, GarminConnectTooManyRequestsError) as e:
            print(f"  {date_str}: fetch failed ({e}); stopping.", file=sys.stderr)
            break
        rec = normalize_night(raw)
        if rec:
            records.append(rec)
    return records


def normalize_night(raw: dict) -> dict | None:
    """Flatten Garmin's nested sleep payload into the record shape we store."""
    dto = (raw or {}).get("dailySleepDTO") or {}
    sleep_seconds = dto.get("sleepTimeSeconds")
    if not sleep_seconds:
        return None

    scores = dto.get("sleepScores") or {}
    overall = (scores.get("overall") or {}).get("value")

    def local_ts(key: str) -> str | None:
        # Garmin reports "local" timestamps as epoch millis pre-shifted into
        # local time, so reading them as UTC yields the local clock time.
        ms = dto.get(key)
        if ms is None:
            return None
        return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M"
        )

    return {
        "date": dto.get("calendarDate"),
        "sleep_seconds": sleep_seconds,
        "deep_seconds": dto.get("deepSleepSeconds") or 0,
        "light_seconds": dto.get("lightSleepSeconds") or 0,
        "rem_seconds": dto.get("remSleepSeconds") or 0,
        "awake_seconds": dto.get("awakeSleepSeconds") or 0,
        "nap_seconds": dto.get("napTimeSeconds") or 0,
        "bedtime_local": local_ts("sleepStartTimestampLocal"),
        "wake_local": local_ts("sleepEndTimestampLocal"),
        "score": overall,
        "avg_overnight_hrv": raw.get("avgOvernightHrv"),
        "resting_hr": raw.get("restingHeartRate"),
        "body_battery_change": raw.get("bodyBatteryChange"),
        "restless_moments": raw.get("restlessMomentsCount"),
        "avg_spo2": dto.get("averageSpO2Value"),
        "avg_respiration": dto.get("averageRespirationValue"),
        "avg_sleep_stress": dto.get("avgSleepStress"),
    }
