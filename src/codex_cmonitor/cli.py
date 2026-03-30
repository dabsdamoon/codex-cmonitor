from __future__ import annotations

import argparse
from pathlib import Path

from codex_cmonitor.monitor import build_snapshot
from codex_cmonitor.render import render_snapshot


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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    snapshot = build_snapshot(args.codex_home)
    print(render_snapshot(snapshot, as_json=args.json))
    return 0
