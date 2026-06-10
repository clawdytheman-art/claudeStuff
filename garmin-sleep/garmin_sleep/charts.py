"""Chart generation (optional — requires matplotlib)."""

from __future__ import annotations

import sys

from .metrics import Analysis, clock_offset_hours, offset_to_clock


def save_charts(a: Analysis, path: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError:
        print(
            "matplotlib is required for charts:  pip install matplotlib",
            file=sys.stderr,
        )
        raise SystemExit(1)

    nights = a.nights
    dates = [n.date for n in nights]

    fig, axes = plt.subplots(4, 1, figsize=(11, 13), sharex=True)
    fig.suptitle("Garmin Sleep Analysis", fontsize=14, fontweight="bold")

    # 1. Stacked sleep stages per night
    ax = axes[0]
    deep = [n.deep_s / 3600 for n in nights]
    light = [n.light_s / 3600 for n in nights]
    rem = [n.rem_s / 3600 for n in nights]
    awake = [n.awake_s / 3600 for n in nights]
    bottom = [0.0] * len(nights)
    for vals, label, color in (
        (deep, "Deep", "#1f4e79"),
        (light, "Light", "#5b9bd5"),
        (rem, "REM", "#9b59b6"),
        (awake, "Awake", "#e8a87c"),
    ):
        ax.bar(dates, vals, bottom=bottom, label=label, color=color, width=0.8)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.axhline(a.goal_s / 3600, ls="--", c="green", lw=1, label="Goal")
    ax.set_ylabel("Hours")
    ax.set_title("Sleep stages")
    ax.legend(loc="upper left", ncols=5, fontsize=8)

    # 2. Sleep score with 7-night rolling average
    ax = axes[1]
    sdates = [n.date for n in nights if n.score is not None]
    scores = [n.score for n in nights if n.score is not None]
    ax.plot(sdates, scores, "o-", ms=4, lw=1, c="#5b9bd5", label="Score")
    if len(scores) >= 7:
        roll = [
            sum(scores[max(0, i - 6) : i + 1]) / len(scores[max(0, i - 6) : i + 1])
            for i in range(len(scores))
        ]
        ax.plot(sdates, roll, lw=2, c="#1f4e79", label="7-night avg")
    ax.set_ylabel("Score")
    ax.set_ylim(0, 100)
    ax.set_title("Garmin sleep score")
    ax.legend(loc="lower left", fontsize=8)

    # 3. Bed / wake times (hours after noon so midnight doesn't wrap)
    ax = axes[2]
    bd = [(n.date, clock_offset_hours(n.bedtime)) for n in nights if n.bedtime]
    wk = [(n.date, clock_offset_hours(n.wake)) for n in nights if n.wake]
    if bd:
        ax.plot(*zip(*bd), "v-", ms=4, lw=1, c="#9b59b6", label="Bedtime")
    if wk:
        ax.plot(*zip(*wk), "^-", ms=4, lw=1, c="#e8a87c", label="Wake")
    ticks = range(8, 25, 2)
    ax.set_yticks(list(ticks), [offset_to_clock(t) for t in ticks])
    ax.invert_yaxis()
    ax.set_ylabel("Clock time")
    ax.set_title("Schedule consistency")
    ax.legend(loc="upper left", fontsize=8)

    # 4. Overnight HRV and resting HR
    ax = axes[3]
    hd = [(n.date, n.hrv) for n in nights if n.hrv is not None]
    rd = [(n.date, n.resting_hr) for n in nights if n.resting_hr is not None]
    if hd:
        ax.plot(*zip(*hd), "o-", ms=4, lw=1, c="#2e8b57", label="HRV (ms)")
    if rd:
        ax2 = ax.twinx()
        ax2.plot(*zip(*rd), "s-", ms=4, lw=1, c="#c0504d", label="Resting HR")
        ax2.set_ylabel("Resting HR (bpm)", color="#c0504d")
        ax2.legend(loc="upper right", fontsize=8)
    ax.set_ylabel("HRV (ms)", color="#2e8b57")
    ax.set_title("Recovery signals")
    if hd:
        ax.legend(loc="upper left", fontsize=8)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=140)
    print(f"Charts saved to {path}")
