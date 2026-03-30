from __future__ import annotations

import argparse
from pathlib import Path
import time

from codex_cmonitor.monitor import build_snapshot
from codex_cmonitor.render import render_snapshot, render_snapshot_live
from rich.console import Console
from rich.live import Live


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-cmonitor",
        description="Display a lightweight local status view for Codex sessions.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Render raw monitor data as JSON.",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        help="Override the Codex home directory. Defaults to ~/.codex or $CODEX_HOME.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Refresh continuously for terminal or tmux-pane usage.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Refresh interval in seconds when --watch is enabled.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output.",
    )
    parser.add_argument(
        "--trend-minutes",
        type=int,
        default=15,
        help="Trend window in minutes for recent usage history.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be greater than 0")
    if args.trend_minutes <= 0:
        parser.error("--trend-minutes must be greater than 0")

    if args.watch and args.json:
        parser.error("--watch and --json cannot be used together")

    if args.watch:
        _watch(
            args.codex_home,
            args.interval,
            color=not args.no_color,
            trend_minutes=args.trend_minutes,
        )
        return 0

    snapshot = build_snapshot(args.codex_home, trend_minutes=args.trend_minutes)
    print(render_snapshot(snapshot, as_json=args.json, color=not args.no_color))
    return 0


def _watch(
    codex_home: Path | None,
    interval: float,
    *,
    color: bool,
    trend_minutes: int,
) -> None:
    console = Console(color_system=None if not color else "auto")
    try:
        snapshot = build_snapshot(codex_home, trend_minutes=trend_minutes)
        with Live(
            render_snapshot_live(snapshot, width=console.size.width),
            console=console,
            screen=True,
            auto_refresh=False,
            transient=False,
        ) as live:
            while True:
                snapshot = build_snapshot(codex_home, trend_minutes=trend_minutes)
                live.update(
                    render_snapshot_live(snapshot, width=console.size.width),
                    refresh=True,
                )
                time.sleep(interval)
    except KeyboardInterrupt:
        return
