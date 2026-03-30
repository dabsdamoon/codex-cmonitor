from __future__ import annotations

from datetime import datetime, timezone
import json

from codex_cmonitor.monitor import MonitorSnapshot


def render_snapshot(snapshot: MonitorSnapshot, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(snapshot.to_dict(), indent=2, sort_keys=True)

    lines = [
        "codex-cmonitor",
        f"status: {snapshot.status}",
        f"session: {snapshot.session_id or '-'}",
        f"title: {snapshot.title or '-'}",
        f"provider: {snapshot.model_provider or '-'}",
        f"model: {snapshot.model or '-'}",
        f"reasoning: {snapshot.reasoning_effort or '-'}",
        f"cwd: {snapshot.cwd or '-'}",
        f"branch: {snapshot.git_branch or '-'}",
        f"approval: {snapshot.approval_mode or '-'}",
        f"created: {_format_unix(snapshot.created_at)}",
        f"updated: {_format_unix(snapshot.updated_at)}",
        f"thread tokens: {_format_number(snapshot.thread_tokens_used)}",
        f"latest total tokens: {_format_number(snapshot.last_total_tokens)}",
        f"last turn input tokens: {_format_number(snapshot.last_input_tokens)}",
        f"last turn output tokens: {_format_number(snapshot.last_output_tokens)}",
        f"last turn reasoning tokens: {_format_number(snapshot.last_reasoning_tokens)}",
        f"last token event: {snapshot.last_event_timestamp or '-'}",
        f"primary limit: {_format_limit(snapshot.primary_used_percent, snapshot.primary_window_minutes, snapshot.primary_resets_at)}",
        f"secondary limit: {_format_limit(snapshot.secondary_used_percent, snapshot.secondary_window_minutes, snapshot.secondary_resets_at)}",
        f"plan: {snapshot.plan_type or '-'}",
    ]
    return "\n".join(lines)


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
