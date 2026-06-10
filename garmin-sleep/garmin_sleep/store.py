"""Local cache of nightly sleep records.

Records are stored as a JSON object keyed by calendar date (YYYY-MM-DD) in
~/.garmin-sleep/data.json so reports work offline and re-syncs are cheap.
"""

from __future__ import annotations

import json
from pathlib import Path

APP_DIR = Path.home() / ".garmin-sleep"
DATA_FILE = APP_DIR / "data.json"
TOKEN_DIR = APP_DIR / "tokens"


def load() -> dict[str, dict]:
    if not DATA_FILE.exists():
        return {}
    with DATA_FILE.open() as f:
        return json.load(f)


def save(records: dict[str, dict]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(records, f, indent=1, sort_keys=True)
    tmp.replace(DATA_FILE)


def upsert(new_records: list[dict]) -> int:
    """Merge new nightly records into the cache. Returns count of new/updated."""
    records = load()
    changed = 0
    for rec in new_records:
        date = rec["date"]
        if records.get(date) != rec:
            records[date] = rec
            changed += 1
    if changed:
        save(records)
    return changed
