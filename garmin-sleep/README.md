# garmin-sleep

Better sleep tracking analytics for Garmin watches (built for a Venu 3, works
with any Garmin device that records sleep to Garmin Connect).

Your watch already collects great sleep data — the Garmin app just doesn't do
much with it. This tool pulls your nightly data from Garmin Connect and gives
you the analysis the app doesn't:

- **Sleep debt** — accumulated and net shortfall against your goal
- **Schedule consistency** — bedtime/wake variability and a regularity grade
- **Social jetlag** — how far your weekend schedule drifts from weekdays
- **Stage analysis** — deep/REM percentages vs typical healthy ranges
- **Recovery overlay** — overnight HRV and resting HR alongside sleep
- **Patterns in *your* data** — e.g. whether late bedtimes actually correlate
  with worse sleep scores for you
- **Plain-language recommendations** derived from all of the above

## Setup

```bash
cd garmin-sleep
pip install .            # core
pip install '.[charts]'  # optional: PNG charts (matplotlib)
```

## Usage

```bash
garmin-sleep login              # one-time: log in to Garmin Connect
garmin-sleep sync --days 60     # pull your sleep history into a local cache
garmin-sleep report --days 30   # analysis report in the terminal
garmin-sleep chart --days 30 -o sleep.png   # 4-panel chart image
```

Set your personal sleep goal with `--goal 7.5` (hours, default 8).

Don't want to log in yet? Preview everything with synthetic data:

```bash
garmin-sleep report --demo
garmin-sleep chart --demo -o demo.png
```

## How it works

- Uses the community [`garminconnect`](https://github.com/cyberjunky/python-garminconnect)
  library, which authenticates the same way the Garmin mobile app does
  (OAuth via garth). MFA is supported.
- Your credentials are never stored — only OAuth tokens, cached in
  `~/.garmin-sleep/tokens` so you log in once.
- Sleep data is cached in `~/.garmin-sleep/data.json`, so reports work offline
  and you own a local copy of your history.

## Notes

- The Venu 3's on-wrist sleep *detection* is Garmin's closed algorithm and
  can't be modified; this tool improves everything downstream of it.
- Wear the watch snugly, a finger-width above the wrist bone, and enable
  Pulse Ox during sleep only if you want SpO2 (it costs battery) — those are
  the main levers for better raw data quality.
