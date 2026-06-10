"""Synthetic data so the report/charts can be previewed without a Garmin login."""

from __future__ import annotations

import datetime as dt
import random


def generate(days: int = 30, seed: int = 7) -> dict[str, dict]:
    rng = random.Random(seed)
    records: dict[str, dict] = {}
    today = dt.date.today()
    for offset in range(days):
        date = today - dt.timedelta(days=offset)
        weekend = date.weekday() in (5, 6)
        bed_hour = 23.4 + (1.1 if weekend else 0) + rng.gauss(0, 0.7)
        sleep_h = max(4.5, rng.gauss(7.0 if not weekend else 7.8, 0.8))
        sleep_s = int(sleep_h * 3600)
        deep = int(sleep_s * max(0.05, rng.gauss(0.14, 0.04)))
        rem = int(sleep_s * max(0.08, rng.gauss(0.21, 0.05)))
        awake = int(rng.gauss(1500, 600))
        light = sleep_s - deep - rem

        bed_dt = dt.datetime.combine(
            date - dt.timedelta(days=1), dt.time(0)
        ) + dt.timedelta(hours=bed_hour)
        wake_dt = bed_dt + dt.timedelta(seconds=sleep_s + max(0, awake))
        score = int(
            max(30, min(95, 50 + (sleep_h - 6.5) * 14 - (bed_hour - 23) * 4 + rng.gauss(0, 6)))
        )
        records[date.isoformat()] = {
            "date": date.isoformat(),
            "sleep_seconds": sleep_s,
            "deep_seconds": deep,
            "light_seconds": light,
            "rem_seconds": rem,
            "awake_seconds": max(0, awake),
            "nap_seconds": 0,
            "bedtime_local": bed_dt.strftime("%Y-%m-%dT%H:%M"),
            "wake_local": wake_dt.strftime("%Y-%m-%dT%H:%M"),
            "score": score,
            "avg_overnight_hrv": round(max(20, rng.gauss(48, 7)), 1),
            "resting_hr": int(rng.gauss(55, 3)),
            "body_battery_change": int(rng.gauss(45, 12)),
            "restless_moments": int(abs(rng.gauss(25, 10))),
            "avg_spo2": round(rng.gauss(95.5, 1.0), 1),
            "avg_respiration": round(rng.gauss(14.5, 1.0), 1),
            "avg_sleep_stress": round(abs(rng.gauss(18, 6)), 1),
        }
    return records
