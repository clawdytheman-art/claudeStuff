"""Sleep analytics computed from cached nightly records.

Everything here is pure functions over the record dicts produced by
client.normalize_night(), so it's easy to test and works offline.
"""

from __future__ import annotations

import datetime as dt
import math
import statistics
from dataclasses import dataclass, field


def parse_local(ts: str | None) -> dt.datetime | None:
    if not ts:
        return None
    return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M")


def clock_offset_hours(t: dt.datetime) -> float:
    """Hours since the previous noon, so times around midnight stay contiguous
    (23:30 -> 11.5, 00:30 -> 12.5) and averages/stdevs behave sensibly."""
    return ((t.hour + t.minute / 60) - 12) % 24


def offset_to_clock(offset: float) -> str:
    hours = (offset + 12) % 24
    h = int(hours)
    m = int(round((hours - h) * 60))
    if m == 60:
        h, m = (h + 1) % 24, 0
    return f"{h:02d}:{m:02d}"


def fmt_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    return f"{sign}{seconds // 3600}h {seconds % 3600 // 60:02d}m"


@dataclass
class Night:
    date: dt.date
    sleep_s: int
    deep_s: int
    light_s: int
    rem_s: int
    awake_s: int
    bedtime: dt.datetime | None
    wake: dt.datetime | None
    score: int | None
    hrv: float | None
    resting_hr: int | None
    body_battery: int | None
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def efficiency(self) -> float | None:
        in_bed = self.sleep_s + self.awake_s
        return self.sleep_s / in_bed * 100 if in_bed else None

    @property
    def deep_pct(self) -> float:
        return self.deep_s / self.sleep_s * 100 if self.sleep_s else 0.0

    @property
    def rem_pct(self) -> float:
        return self.rem_s / self.sleep_s * 100 if self.sleep_s else 0.0


def to_nights(records: dict[str, dict], days: int) -> list[Night]:
    """Most recent `days` nights, oldest first."""
    cutoff = dt.date.today() - dt.timedelta(days=days)
    nights = []
    for date_str in sorted(records):
        date = dt.date.fromisoformat(date_str)
        if date < cutoff:
            continue
        r = records[date_str]
        nights.append(
            Night(
                date=date,
                sleep_s=r["sleep_seconds"],
                deep_s=r.get("deep_seconds", 0),
                light_s=r.get("light_seconds", 0),
                rem_s=r.get("rem_seconds", 0),
                awake_s=r.get("awake_seconds", 0),
                bedtime=parse_local(r.get("bedtime_local")),
                wake=parse_local(r.get("wake_local")),
                score=r.get("score"),
                hrv=r.get("avg_overnight_hrv"),
                resting_hr=r.get("resting_hr"),
                body_battery=r.get("body_battery_change"),
                raw=r,
            )
        )
    return nights


@dataclass
class Analysis:
    nights: list[Night]
    goal_s: int
    avg_sleep_s: float
    avg_score: float | None
    total_debt_s: float          # sum of nightly shortfalls (surplus ignored)
    net_debt_s: float            # goal minus actual, surpluses offset debt
    nights_under_goal: int
    avg_bedtime_offset: float | None
    avg_wake_offset: float | None
    bedtime_stdev_min: float | None
    wake_stdev_min: float | None
    consistency_grade: str | None
    social_jetlag_min: float | None   # weekend vs weekday sleep-midpoint shift
    avg_deep_pct: float
    avg_rem_pct: float
    avg_efficiency: float | None
    avg_hrv: float | None
    avg_resting_hr: float | None
    late_night_score_corr: float | None  # bedtime lateness vs sleep score
    duration_score_corr: float | None


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 5 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (sx * sy) if sx and sy else None


def grade_consistency(stdev_min: float) -> str:
    if stdev_min <= 30:
        return "excellent"
    if stdev_min <= 45:
        return "good"
    if stdev_min <= 75:
        return "fair"
    return "poor"


def analyze(nights: list[Night], goal_hours: float = 8.0) -> Analysis:
    goal_s = int(goal_hours * 3600)
    sleeps = [n.sleep_s for n in nights]
    scores = [n.score for n in nights if n.score is not None]
    hrvs = [n.hrv for n in nights if n.hrv is not None]
    rhrs = [n.resting_hr for n in nights if n.resting_hr is not None]
    effs = [n.efficiency for n in nights if n.efficiency is not None]

    bed_offsets = [clock_offset_hours(n.bedtime) for n in nights if n.bedtime]
    wake_offsets = [clock_offset_hours(n.wake) for n in nights if n.wake]

    bed_stdev = (
        statistics.stdev(bed_offsets) * 60 if len(bed_offsets) >= 3 else None
    )
    wake_stdev = (
        statistics.stdev(wake_offsets) * 60 if len(wake_offsets) >= 3 else None
    )

    # Social jetlag: shift of the sleep midpoint on weekend nights
    # (Fri/Sat night = Sat/Sun calendar date) vs weekday nights.
    midpoints_wd, midpoints_we = [], []
    for n in nights:
        if not (n.bedtime and n.wake):
            continue
        mid = clock_offset_hours(n.bedtime) + (n.wake - n.bedtime).total_seconds() / 7200
        (midpoints_we if n.date.weekday() in (5, 6) else midpoints_wd).append(mid)
    social_jetlag = (
        (statistics.fmean(midpoints_we) - statistics.fmean(midpoints_wd)) * 60
        if len(midpoints_wd) >= 3 and len(midpoints_we) >= 2
        else None
    )

    score_nights = [n for n in nights if n.score is not None and n.bedtime]
    late_corr = pearson(
        [clock_offset_hours(n.bedtime) for n in score_nights],
        [float(n.score) for n in score_nights],
    )
    dur_nights = [n for n in nights if n.score is not None]
    dur_corr = pearson(
        [n.sleep_s / 3600 for n in dur_nights],
        [float(n.score) for n in dur_nights],
    )

    return Analysis(
        nights=nights,
        goal_s=goal_s,
        avg_sleep_s=statistics.fmean(sleeps) if sleeps else 0.0,
        avg_score=statistics.fmean(scores) if scores else None,
        total_debt_s=sum(max(0, goal_s - s) for s in sleeps),
        net_debt_s=sum(goal_s - s for s in sleeps),
        nights_under_goal=sum(1 for s in sleeps if s < goal_s),
        avg_bedtime_offset=statistics.fmean(bed_offsets) if bed_offsets else None,
        avg_wake_offset=statistics.fmean(wake_offsets) if wake_offsets else None,
        bedtime_stdev_min=bed_stdev,
        wake_stdev_min=wake_stdev,
        consistency_grade=grade_consistency(bed_stdev) if bed_stdev is not None else None,
        social_jetlag_min=social_jetlag,
        avg_deep_pct=statistics.fmean([n.deep_pct for n in nights]) if nights else 0.0,
        avg_rem_pct=statistics.fmean([n.rem_pct for n in nights]) if nights else 0.0,
        avg_efficiency=statistics.fmean(effs) if effs else None,
        avg_hrv=statistics.fmean(hrvs) if hrvs else None,
        avg_resting_hr=statistics.fmean(rhrs) if rhrs else None,
        late_night_score_corr=late_corr,
        duration_score_corr=dur_corr,
    )


def recommendations(a: Analysis) -> list[str]:
    """Rule-based, plain-language takeaways from the numbers."""
    recs = []
    n = len(a.nights)
    if n < 7:
        recs.append(
            f"Only {n} nights of data so far — sync more history before "
            "reading too much into the trends."
        )

    avg_short = a.goal_s - a.avg_sleep_s
    if avg_short > 1800:
        recs.append(
            f"You average {fmt_duration(a.avg_sleep_s)} vs a "
            f"{fmt_duration(a.goal_s)} goal — about "
            f"{fmt_duration(avg_short)} short per night. Shifting bedtime "
            f"earlier by that amount is the single highest-impact change."
        )
    elif a.net_debt_s <= 0 and n >= 7:
        recs.append("You're meeting your sleep duration goal on average. Keep it up.")

    if a.bedtime_stdev_min is not None and a.bedtime_stdev_min > 45:
        recs.append(
            f"Bedtime varies a lot (±{a.bedtime_stdev_min:.0f} min). Irregular "
            "schedules hurt sleep quality even when total duration is fine — "
            "aim for a consistent window within ~30 minutes."
        )

    if a.social_jetlag_min is not None and abs(a.social_jetlag_min) > 60:
        direction = "later" if a.social_jetlag_min > 0 else "earlier"
        recs.append(
            f"Your weekend sleep midpoint is ~{abs(a.social_jetlag_min):.0f} min "
            f"{direction} than weekdays (social jetlag). Keeping weekends within "
            "an hour of your weekday schedule makes Monday mornings easier."
        )

    if a.avg_deep_pct and a.avg_deep_pct < 13:
        recs.append(
            f"Deep sleep averages {a.avg_deep_pct:.0f}% (typical is 13–23%). "
            "Alcohol, late meals, late workouts, and a warm bedroom all "
            "suppress deep sleep — worth experimenting."
        )
    if a.avg_rem_pct and a.avg_rem_pct < 18:
        recs.append(
            f"REM averages {a.avg_rem_pct:.0f}% (typical is 20–25%). REM is "
            "concentrated late in the night, so cutting sleep short or an "
            "erratic wake time costs REM first."
        )

    if a.avg_efficiency is not None and a.avg_efficiency < 88:
        recs.append(
            f"Sleep efficiency averages {a.avg_efficiency:.0f}% — you spend a "
            "fair amount of the night awake. If you're in bed long but awake "
            "often, a slightly later bedtime can consolidate sleep."
        )

    if a.late_night_score_corr is not None and a.late_night_score_corr < -0.35:
        recs.append(
            "Your data shows later bedtimes correlating with worse sleep "
            f"scores (r={a.late_night_score_corr:.2f}) — your own nights "
            "confirm earlier is better for you."
        )

    if not recs:
        recs.append("No red flags in this window — sleep looks solid.")
    return recs
