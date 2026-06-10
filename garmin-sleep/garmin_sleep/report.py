"""Terminal report rendering."""

from __future__ import annotations

from .metrics import (
    Analysis,
    Night,
    fmt_duration,
    offset_to_clock,
    recommendations,
)

BAR_WIDTH = 24
FULL, PART = "█", "▏▎▍▌▋▊▉█"


def bar(value: float, max_value: float, width: int = BAR_WIDTH) -> str:
    if max_value <= 0:
        return ""
    frac = min(value / max_value, 1.0) * width
    full = int(frac)
    rem = frac - full
    partial = PART[int(rem * 8)] if rem > 1 / 16 else ""
    return FULL * full + partial


def night_row(n: Night, goal_s: int, scale_s: float) -> str:
    day = n.date.strftime("%a %m-%d")
    dur = fmt_duration(n.sleep_s)
    score = f"{n.score:>3}" if n.score is not None else "  –"
    bed = n.bedtime.strftime("%H:%M") if n.bedtime else "  –  "
    wake = n.wake.strftime("%H:%M") if n.wake else "  –  "
    marker = " " if n.sleep_s >= goal_s else "▼"
    return (
        f"  {day}  {bed}–{wake}  {dur:>7} {marker} "
        f"score {score}  {bar(n.sleep_s, scale_s, 20)}"
    )


def render(a: Analysis, days: int) -> str:
    lines = []
    add = lines.append
    n = len(a.nights)

    add(f"SLEEP REPORT — last {days} days ({n} nights recorded)")
    add("=" * 64)
    add("")

    add("Nightly log")
    add("-" * 64)
    scale_s = max([a.goal_s] + [x.sleep_s for x in a.nights]) * 1.05
    for night in a.nights:
        add(night_row(night, a.goal_s, scale_s))
    add(f"  (▼ = under your {fmt_duration(a.goal_s)} goal)")
    add("")

    add("Averages")
    add("-" * 64)
    add(f"  Sleep duration     {fmt_duration(a.avg_sleep_s):>8}   (goal {fmt_duration(a.goal_s)})")
    if a.avg_score is not None:
        add(f"  Garmin sleep score {a.avg_score:>8.0f}")
    if a.avg_bedtime_offset is not None:
        add(f"  Bedtime            {offset_to_clock(a.avg_bedtime_offset):>8}"
            + (f"   (± {a.bedtime_stdev_min:.0f} min)" if a.bedtime_stdev_min is not None else ""))
    if a.avg_wake_offset is not None:
        add(f"  Wake time          {offset_to_clock(a.avg_wake_offset):>8}"
            + (f"   (± {a.wake_stdev_min:.0f} min)" if a.wake_stdev_min is not None else ""))
    add(f"  Deep sleep         {a.avg_deep_pct:>7.0f}%   (typical 13–23%)")
    add(f"  REM sleep          {a.avg_rem_pct:>7.0f}%   (typical 20–25%)")
    if a.avg_efficiency is not None:
        add(f"  Efficiency         {a.avg_efficiency:>7.0f}%   (asleep vs in bed)")
    if a.avg_hrv is not None:
        add(f"  Overnight HRV      {a.avg_hrv:>7.0f}ms")
    if a.avg_resting_hr is not None:
        add(f"  Resting HR         {a.avg_resting_hr:>6.0f}bpm")
    add("")

    add("Sleep debt & consistency")
    add("-" * 64)
    add(f"  Nights under goal  {a.nights_under_goal}/{n}")
    add(f"  Accumulated debt   {fmt_duration(a.total_debt_s)} (shortfalls only)")
    add(f"  Net debt           {fmt_duration(a.net_debt_s)} (after surplus nights)")
    if a.consistency_grade:
        add(f"  Schedule regularity: {a.consistency_grade}")
    if a.social_jetlag_min is not None:
        direction = "later" if a.social_jetlag_min > 0 else "earlier"
        add(f"  Social jetlag      {abs(a.social_jetlag_min):.0f} min {direction} on weekends")
    add("")

    if a.late_night_score_corr is not None or a.duration_score_corr is not None:
        add("Patterns in your data")
        add("-" * 64)
        if a.duration_score_corr is not None:
            add(f"  Duration vs score correlation   r = {a.duration_score_corr:+.2f}")
        if a.late_night_score_corr is not None:
            add(f"  Late bedtime vs score           r = {a.late_night_score_corr:+.2f}")
        add("")

    add("Recommendations")
    add("-" * 64)
    for rec in recommendations(a):
        add(f"  • {rec}")
    add("")

    best = [x for x in a.nights if x.score is not None]
    if len(best) >= 3:
        top = max(best, key=lambda x: x.score)
        worst = min(best, key=lambda x: x.score)
        add("Best / worst nights")
        add("-" * 64)
        for label, nt in (("Best ", top), ("Worst", worst)):
            bed = nt.bedtime.strftime("%H:%M") if nt.bedtime else "–"
            add(
                f"  {label}: {nt.date} — score {nt.score}, "
                f"{fmt_duration(nt.sleep_s)}, bed {bed}, "
                f"deep {nt.deep_pct:.0f}%, REM {nt.rem_pct:.0f}%"
            )
    return "\n".join(lines)
