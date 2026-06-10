"""Command-line interface for garmin-sleep."""

from __future__ import annotations

import argparse
import sys

from . import metrics, report, store


def cmd_login(args: argparse.Namespace) -> None:
    from . import client

    client.login_interactive()


def cmd_sync(args: argparse.Namespace) -> None:
    from . import client

    c = client.get_client()
    print(f"Fetching last {args.days} nights from Garmin Connect...")
    records = client.fetch_sleep(c, args.days)
    changed = store.upsert(records)
    total = len(store.load())
    print(f"Synced {len(records)} nights ({changed} new/updated). "
          f"{total} nights cached locally.")


def _load_records(args: argparse.Namespace) -> dict[str, dict]:
    if getattr(args, "demo", False):
        from . import demo

        return demo.generate(args.days)
    records = store.load()
    if not records:
        print(
            "No cached data. Run `garmin-sleep sync` first "
            "(or use --demo to preview with synthetic data).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return records


def cmd_report(args: argparse.Namespace) -> None:
    records = _load_records(args)
    nights = metrics.to_nights(records, args.days)
    if not nights:
        print(f"No nights recorded in the last {args.days} days.", file=sys.stderr)
        raise SystemExit(1)
    analysis = metrics.analyze(nights, goal_hours=args.goal)
    print(report.render(analysis, args.days))


def cmd_chart(args: argparse.Namespace) -> None:
    from . import charts

    records = _load_records(args)
    nights = metrics.to_nights(records, args.days)
    if not nights:
        print(f"No nights recorded in the last {args.days} days.", file=sys.stderr)
        raise SystemExit(1)
    analysis = metrics.analyze(nights, goal_hours=args.goal)
    charts.save_charts(analysis, args.output)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="garmin-sleep",
        description="Better sleep analytics for your Garmin watch.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Log in to Garmin Connect and cache tokens").set_defaults(
        func=cmd_login
    )

    p_sync = sub.add_parser("sync", help="Fetch sleep data into the local cache")
    p_sync.add_argument("--days", type=int, default=30, help="nights to fetch (default 30)")
    p_sync.set_defaults(func=cmd_sync)

    def analysis_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--days", type=int, default=30, help="window size (default 30)")
        p.add_argument("--goal", type=float, default=8.0, help="sleep goal in hours (default 8)")
        p.add_argument("--demo", action="store_true", help="use synthetic demo data")

    p_report = sub.add_parser("report", help="Print a sleep analysis report")
    analysis_args(p_report)
    p_report.set_defaults(func=cmd_report)

    p_chart = sub.add_parser("chart", help="Save analysis charts as a PNG")
    analysis_args(p_chart)
    p_chart.add_argument("-o", "--output", default="sleep.png", help="output file")
    p_chart.set_defaults(func=cmd_chart)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
