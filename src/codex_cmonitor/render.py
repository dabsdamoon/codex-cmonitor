from __future__ import annotations

from datetime import datetime, timezone
import json
import os

from codex_cmonitor.monitor import MonitorSnapshot
from rich.console import Group
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class Palette:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"


def render_snapshot(
    snapshot: MonitorSnapshot,
    *,
    as_json: bool = False,
    color: bool | None = None,
) -> str:
    if as_json:
        return json.dumps(snapshot.to_dict(), indent=2, sort_keys=True)

    palette = Palette(_should_use_color(color))
    lines = [_header(snapshot, palette), ""]

    if snapshot.status != "ok":
        lines.extend(
            [
                palette.yellow("No active Codex session found."),
                palette.dim("Checked ~/.codex or the provided --codex-home path."),
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            _section(
                "Session",
                [
                    ("Active sessions", str(snapshot.active_session_count)),
                    ("Title", snapshot.title),
                    ("Latest session", snapshot.session_id),
                    ("Model", _join_nonempty(snapshot.model_provider, snapshot.model)),
                    ("Reasoning", snapshot.reasoning_effort or "-"),
                    ("Approval", snapshot.approval_mode or "-"),
                ],
                palette,
            ),
            _section(
                "Workspace",
                [
                    ("Cwd", snapshot.cwd),
                    ("Branch", snapshot.git_branch or "-"),
                    ("Created", _format_unix(snapshot.created_at)),
                    ("Updated", _format_unix(snapshot.updated_at)),
                    ("Age", _format_age(snapshot.captured_at, snapshot.updated_at)),
                ],
                palette,
            ),
            _section(
                "Usage",
                [
                    ("Account total", _format_number(snapshot.thread_tokens_used)),
                    ("Latest aggregate", _format_number(snapshot.last_total_tokens)),
                    ("Burn rate", _format_trend_summary(snapshot)),
                    (f"Input ({snapshot.trend_minutes}m)", _format_number(snapshot.recent_input_tokens)),
                    (f"Output ({snapshot.trend_minutes}m)", _format_number(snapshot.recent_output_tokens)),
                    (f"Reasoning ({snapshot.trend_minutes}m)", _format_number(snapshot.recent_reasoning_tokens)),
                    ("Last event", snapshot.last_event_timestamp or "-"),
                ],
                palette,
            ),
            _section(
                "Limits",
                [
                    ("Primary", _format_limit(snapshot.primary_used_percent, snapshot.primary_window_minutes, snapshot.primary_resets_at)),
                    ("Secondary", _format_limit(snapshot.secondary_used_percent, snapshot.secondary_window_minutes, snapshot.secondary_resets_at)),
                    ("Plan", snapshot.plan_type or "-"),
                ],
                palette,
            ),
        ]
    )
    return "\n".join(lines)


def render_snapshot_live(snapshot: MonitorSnapshot, *, width: int | None = None) -> Group:
    header = _live_header(snapshot)
    if snapshot.status != "ok":
        body = Panel(
            Text("No active Codex session found.\nChecked ~/.codex or the provided --codex-home path."),
            title="codex-cmonitor",
            border_style="yellow",
        )
        return Group(header, body)

    if width is not None and width < 72:
        return Group(header, _ultra_compact_live_panel(snapshot, width=width))

    if width is not None and width < 110:
        return Group(header, _compact_live_panel(snapshot, width=width))

    session_table = _build_live_table(
        [
            ("Active sessions", str(snapshot.active_session_count)),
            ("Title", snapshot.title),
            ("Latest session", snapshot.session_id),
            ("Model", _join_nonempty(snapshot.model_provider, snapshot.model)),
            ("Reasoning", snapshot.reasoning_effort or "-"),
            ("Approval", snapshot.approval_mode or "-"),
        ]
    )
    workspace_table = _build_live_table(
        [
            ("Cwd", snapshot.cwd),
            ("Branch", snapshot.git_branch or "-"),
            ("Created", _format_unix(snapshot.created_at)),
            ("Updated", _format_unix(snapshot.updated_at)),
            ("Age", _format_age(snapshot.captured_at, snapshot.updated_at)),
        ]
    )
    usage_table = _build_live_table(
        [
            ("Account total", _format_number(snapshot.thread_tokens_used)),
            ("Latest aggregate", _format_number(snapshot.last_total_tokens)),
            ("Trend", _format_trend_summary(snapshot)),
            (f"Input ({snapshot.trend_minutes}m)", _format_number(snapshot.recent_input_tokens)),
            (f"Output ({snapshot.trend_minutes}m)", _format_number(snapshot.recent_output_tokens)),
            (f"Reasoning ({snapshot.trend_minutes}m)", _format_number(snapshot.recent_reasoning_tokens)),
            ("Last event", snapshot.last_event_timestamp or "-"),
        ]
    )
    limits_table = _build_live_table(
        [
            ("Primary", _format_limit(snapshot.primary_used_percent, snapshot.primary_window_minutes, snapshot.primary_resets_at)),
            ("Secondary", _format_limit(snapshot.secondary_used_percent, snapshot.secondary_window_minutes, snapshot.secondary_resets_at)),
            ("Plan", snapshot.plan_type or "-"),
        ]
    )

    return Group(
        header,
        Panel(session_table, title="Session", border_style="cyan"),
        Panel(workspace_table, title="Workspace", border_style="blue"),
        Panel(usage_table, title="Usage", border_style="green"),
        Panel(limits_table, title="Limits", border_style="magenta"),
    )


def _header(snapshot: MonitorSnapshot, palette: Palette) -> str:
    title = palette.bold(palette.cyan("codex-cmonitor"))
    status = snapshot.status.upper()
    if snapshot.status == "ok":
        status = palette.green(status)
    elif snapshot.status == "no_session":
        status = palette.yellow(status)
    else:
        status = palette.red(status)
    captured = palette.dim(f"captured { _format_unix(snapshot.captured_at) }")
    return f"{title}  {status}  {captured}"


def _section(title: str, rows: list[tuple[str, str | None]], palette: Palette) -> str:
    label_width = max(len(label) for label, _ in rows)
    lines = [palette.bold(title)]
    for label, value in rows:
        lines.append(f"  {palette.dim(label.ljust(label_width))}  {value or '-'}")
    return "\n".join(lines)


def _should_use_color(color: bool | None) -> bool:
    if color is not None:
        return color
    return os.getenv("NO_COLOR") is None


def _format_number(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}"


def _format_unix(timestamp: int | None) -> str:
    if timestamp is None:
        return "-"
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.isoformat()


def _format_limit(
    used_percent: float | None,
    window_minutes: int | None,
    resets_at: int | None,
) -> str:
    if used_percent is None and window_minutes is None and resets_at is None:
        return "-"

    pieces = []
    if used_percent is not None:
        pieces.append(f"{used_percent:.1f}%")
    if window_minutes is not None:
        pieces.append(f"{window_minutes}m")
    if resets_at is not None:
        pieces.append(f"reset={_format_unix(resets_at)}")
    return ", ".join(pieces)


def _format_age(now_ts: int, then_ts: int | None) -> str:
    if then_ts is None:
        return "-"
    delta = max(0, now_ts - then_ts)
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        hours = delta // 3600
        minutes = (delta % 3600) // 60
        return f"{hours}h {minutes}m ago"
    days = delta // 86400
    hours = (delta % 86400) // 3600
    return f"{days}d {hours}h ago"


def _join_nonempty(*parts: str | None) -> str:
    values = [part for part in parts if part]
    return " / ".join(values) if values else "-"


def _live_header(snapshot: MonitorSnapshot) -> Panel:
    title = Text()
    title.append("codex-cmonitor", style="bold cyan")
    title.append("  ")
    title.append_text(_live_status(snapshot.status))
    title.append("  ")
    title.append(f"captured {_format_unix(snapshot.captured_at)}", style="dim")
    return Panel(title, border_style="white")


def _live_status(status: str) -> Text:
    if status == "ok":
        return Text(status.upper(), style="bold green")
    if status == "no_session":
        return Text(status.upper(), style="bold yellow")
    return Text(status.upper(), style="bold red")


def _build_live_table(rows: list[tuple[str, str | None]]) -> Table:
    table = Table.grid(expand=True)
    table.add_column(style="dim", ratio=1, no_wrap=True)
    table.add_column(ratio=4, overflow="fold")
    for label, value in rows:
        table.add_row(label, value or "-")
    return table


def _compact_live_panel(snapshot: MonitorSnapshot, *, width: int | None = None) -> Panel:
    content_width = max(40, (width or 80) - 4)
    left_width = max(18, min(24, content_width // 3))
    graph_width = max(12, min(28, content_width - left_width - 10))

    title = Text(_truncate(snapshot.title or "-", 64), style="bold")
    meta_table = Table.grid(expand=True)
    meta_table.add_column(style="dim", width=6, no_wrap=True)
    meta_table.add_column(overflow="ellipsis")
    meta_table.add_row("model", _truncate(_join_nonempty(snapshot.model_provider, snapshot.model), left_width + 6))
    meta_table.add_row("cwd", _truncate(snapshot.cwd or "-", left_width + 6))
    meta_table.add_row("sessions", str(snapshot.active_session_count))
    meta_table.add_row("age", _format_age(snapshot.captured_at, snapshot.updated_at))
    meta_table.add_row("plan", snapshot.plan_type or "-")
    if snapshot.git_branch:
        meta_table.add_row("branch", _truncate(snapshot.git_branch, left_width + 6))

    usage_table = Table.grid(expand=True)
    usage_table.add_column(style="dim", width=6, no_wrap=True)
    usage_table.add_column(overflow="ellipsis")
    usage_table.add_row("acct", _format_compact_number(snapshot.thread_tokens_used))
    usage_table.add_row("agg", _format_compact_number(snapshot.last_total_tokens))
    usage_table.add_row("burn", _format_trend_summary(snapshot))
    usage_table.add_row("turn", _truncate(_format_turn_tokens(snapshot), left_width + 6))

    left = Group(meta_table, Text(""), usage_table)

    right = Group(
        Text(f"Burn Rate ({snapshot.trend_minutes}m)", style="bold"),
        _trend_line(snapshot, graph_width=graph_width),
        Text(""),
        Text("Limits", style="bold"),
        _meter_line(
            "Primary",
            snapshot.primary_used_percent,
            style="green",
            suffix=_compact_limit(snapshot.primary_used_percent, snapshot.primary_window_minutes),
            width=graph_width,
        ),
        _meter_line(
            "Secondary",
            snapshot.secondary_used_percent,
            style="cyan",
            suffix=_compact_limit(snapshot.secondary_used_percent, snapshot.secondary_window_minutes),
            width=graph_width,
        ),
        Text(f"Turn Mix ({snapshot.trend_minutes}m)", style="bold"),
        _turn_mix_line(snapshot, width=graph_width),
    )

    body = Columns([left, right], expand=True, equal=False, padding=(0, 2))
    return Panel(body, title=title, border_style="cyan")


def _ultra_compact_live_panel(snapshot: MonitorSnapshot, *, width: int | None = None) -> Panel:
    content_width = max(28, (width or 64) - 4)
    graph_width = max(10, content_width - 12)

    title = Text(_truncate(snapshot.title or "-", min(content_width + 6, 44)), style="bold")
    rows = Table.grid(expand=True)
    rows.add_column(style="dim", width=7, no_wrap=True)
    rows.add_column(overflow="ellipsis")
    rows.add_row("model", _truncate(_join_nonempty(snapshot.model_provider, snapshot.model), content_width))
    rows.add_row("cwd", _truncate(snapshot.cwd or "-", content_width))
    rows.add_row("sessions", str(snapshot.active_session_count))
    rows.add_row("burn", _format_trend_summary(snapshot))
    rows.add_row("turn", _truncate(_format_turn_tokens(snapshot), content_width))

    visuals = Group(
        _trend_line(snapshot, graph_width=graph_width, label="b"),
        _meter_line(
            "p",
            snapshot.primary_used_percent,
            style="green",
            suffix=_compact_limit(snapshot.primary_used_percent, snapshot.primary_window_minutes),
            width=graph_width,
            label_width=2,
        ),
        _meter_line(
            "s",
            snapshot.secondary_used_percent,
            style="cyan",
            suffix=_compact_limit(snapshot.secondary_used_percent, snapshot.secondary_window_minutes),
            width=graph_width,
            label_width=2,
        ),
        _turn_mix_line(snapshot, width=graph_width, label="m", label_width=2),
    )

    body = Group(
        rows,
        Text(""),
        visuals,
        Text(""),
        Text(f"updated {_format_age(snapshot.captured_at, snapshot.updated_at)}", style="dim"),
    )
    return Panel(body, title=title, border_style="cyan")


def _compact_limit(used_percent: float | None, window_minutes: int | None) -> str:
    pieces = []
    if used_percent is not None:
        pieces.append(f"{used_percent:.1f}%")
    if window_minutes is not None:
        pieces.append(f"/ {window_minutes}m")
    return " ".join(pieces) if pieces else "-"


def _format_turn_tokens(snapshot: MonitorSnapshot) -> str:
    parts = [
        f"in {_format_compact_number(snapshot.recent_input_tokens)}",
        f"out {_format_compact_number(snapshot.recent_output_tokens)}",
    ]
    if snapshot.recent_reasoning_tokens:
        parts.append(f"r {_format_compact_number(snapshot.recent_reasoning_tokens)}")
    return ", ".join(parts)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3] + "..."


def _format_trend_summary(snapshot: MonitorSnapshot) -> str:
    if not snapshot.trend_points:
        return f"{snapshot.trend_minutes}m: -"
    delta = snapshot.trend_delta_tokens
    delta_str = _format_signed_compact_number(delta)
    peak = max(snapshot.trend_points)
    avg = sum(snapshot.trend_points) // len(snapshot.trend_points)
    return (
        f"{snapshot.trend_minutes}m {delta_str}"
        f" | peak {_format_compact_number(peak)}"
        f" avg {_format_compact_number(avg)}"
    )


def _format_compact_number(value: int | None) -> str:
    if value is None:
        return "-"
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def _meter_line(
    label: str,
    percent: float | None,
    *,
    style: str,
    suffix: str,
    width: int,
    label_width: int = 9,
) -> Text:
    text = Text()
    text.append(f"{label:<{label_width}}", style="dim")
    text.append(_bar(percent, width=width), style=style)
    text.append("  ")
    text.append(suffix)
    return text


def _trend_line(snapshot: MonitorSnapshot, *, graph_width: int, label: str = "burn") -> Text:
    text = Text()
    label_width = max(2, len(label) + 2)
    text.append(f"{label:<{label_width}}", style="dim")
    sparkline = _sparkline(snapshot.trend_points, width=graph_width)
    if sparkline:
        text.append(sparkline, style="yellow")
    else:
        text.append("·" * graph_width, style="dim")
    text.append("  ")
    text.append(_format_trend_summary(snapshot))
    return text


def _bar(percent: float | None, *, width: int) -> str:
    if percent is None:
        return "░" * width
    clamped = max(0.0, min(percent, 100.0))
    filled = int(round((clamped / 100.0) * width))
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


def _turn_mix_line(
    snapshot: MonitorSnapshot,
    *,
    width: int,
    label: str = "mix",
    label_width: int = 9,
) -> Text:
    input_tokens = snapshot.recent_input_tokens or 0
    output_tokens = snapshot.recent_output_tokens or 0
    reasoning_tokens = snapshot.recent_reasoning_tokens or 0
    total = input_tokens + output_tokens + reasoning_tokens

    text = Text()
    text.append(f"{label:<{label_width}}", style="dim")
    if total <= 0:
        text.append("░" * width, style="white")
        text.append("  -")
        return text

    input_width, output_width, reasoning_width = _distribution_widths(
        [input_tokens, output_tokens, reasoning_tokens],
        width=width,
    )
    if input_width:
        text.append("█" * input_width, style="green")
    if output_width:
        text.append("█" * output_width, style="cyan")
    if reasoning_width:
        text.append("█" * reasoning_width, style="magenta")
    text.append("  ")
    text.append(_format_turn_tokens(snapshot))
    return text


def _distribution_widths(values: list[int], *, width: int) -> tuple[int, ...]:
    total = sum(values)
    if total <= 0:
        return tuple(0 for _ in values)

    raw = [(value / total) * width for value in values]
    base = [int(part) for part in raw]
    remainder = width - sum(base)
    order = sorted(
        range(len(values)),
        key=lambda idx: raw[idx] - base[idx],
        reverse=True,
    )
    for idx in order[:remainder]:
        base[idx] += 1
    return tuple(base)


def _sparkline(values: list[int], *, width: int) -> str:
    if not values:
        return ""
    if len(values) > width:
        values = _downsample(values, width)
    levels = "▁▂▃▄▅▆▇█"
    maximum = max(values)
    if maximum == 0:
        return levels[0] * len(values)
    chars = []
    for value in values:
        ratio = value / maximum
        idx = int(round(ratio * (len(levels) - 1)))
        idx = max(0, min(idx, len(levels) - 1))
        chars.append(levels[idx])
    return "".join(chars)


def _downsample(values: list[int], width: int) -> list[int]:
    if width <= 0:
        return []
    if len(values) <= width:
        return values
    result = []
    for index in range(width):
        start = int(index * len(values) / width)
        end = int((index + 1) * len(values) / width)
        bucket = values[start:max(start + 1, end)]
        result.append(bucket[-1])
    return result


def _format_signed_compact_number(value: int | None) -> str:
    if value is None:
        return "-"
    if value == 0:
        return "0"
    prefix = "+" if value > 0 else "-"
    return prefix + _format_compact_number(abs(value))
