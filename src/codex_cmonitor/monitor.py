from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import time

from codex_cmonitor.session_store import get_active_session


@dataclass
class MonitorSnapshot:
    status: str
    captured_at: int
    trend_minutes: int
    session_id: str | None
    rollout_path: str | None
    title: str | None
    model_provider: str | None
    model: str | None
    reasoning_effort: str | None
    cwd: str | None
    git_branch: str | None
    approval_mode: str | None
    created_at: int | None
    updated_at: int | None
    thread_tokens_used: int | None
    last_event_timestamp: str | None
    last_total_tokens: int | None
    last_input_tokens: int | None
    last_output_tokens: int | None
    last_reasoning_tokens: int | None
    primary_used_percent: float | None
    primary_window_minutes: int | None
    primary_resets_at: int | None
    secondary_used_percent: float | None
    secondary_window_minutes: int | None
    secondary_resets_at: int | None
    plan_type: str | None
    trend_points: list[int]
    trend_delta_tokens: int | None
    trend_start_timestamp: int | None
    trend_end_timestamp: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_snapshot(
    codex_home: str | Path | None = None,
    *,
    trend_minutes: int = 15,
) -> MonitorSnapshot:
    captured_at = int(time.time())
    session = get_active_session(
        codex_home,
        trend_minutes=trend_minutes,
        now_ts=captured_at,
    )
    if session is None:
        return MonitorSnapshot(
            status="no_session",
            captured_at=captured_at,
            trend_minutes=trend_minutes,
            session_id=None,
            rollout_path=None,
            title=None,
            model_provider=None,
            model=None,
            reasoning_effort=None,
            cwd=None,
            git_branch=None,
            approval_mode=None,
            created_at=None,
            updated_at=None,
            thread_tokens_used=None,
            last_event_timestamp=None,
            last_total_tokens=None,
            last_input_tokens=None,
            last_output_tokens=None,
            last_reasoning_tokens=None,
            primary_used_percent=None,
            primary_window_minutes=None,
            primary_resets_at=None,
            secondary_used_percent=None,
            secondary_window_minutes=None,
            secondary_resets_at=None,
            plan_type=None,
            trend_points=[],
            trend_delta_tokens=None,
            trend_start_timestamp=None,
            trend_end_timestamp=None,
        )

    token_count = session.token_count
    trend_points = [
        record.total_tokens
        for record in session.recent_token_counts
        if record.total_tokens is not None
    ]
    trend_start = session.recent_token_counts[0].timestamp_unix if session.recent_token_counts else None
    trend_end = session.recent_token_counts[-1].timestamp_unix if session.recent_token_counts else None
    trend_delta = None
    if len(trend_points) >= 2:
        trend_delta = trend_points[-1] - trend_points[0]
    return MonitorSnapshot(
        status="ok",
        captured_at=captured_at,
        trend_minutes=trend_minutes,
        session_id=session.session_id,
        rollout_path=str(session.rollout_path),
        title=session.title,
        model_provider=session.model_provider,
        model=session.model,
        reasoning_effort=session.reasoning_effort,
        cwd=session.cwd,
        git_branch=session.git_branch,
        approval_mode=session.approval_mode,
        created_at=session.created_at,
        updated_at=session.updated_at,
        thread_tokens_used=session.thread_tokens_used,
        last_event_timestamp=token_count.timestamp if token_count else None,
        last_total_tokens=token_count.total_tokens if token_count else None,
        last_input_tokens=token_count.input_tokens if token_count else None,
        last_output_tokens=token_count.output_tokens if token_count else None,
        last_reasoning_tokens=token_count.reasoning_tokens if token_count else None,
        primary_used_percent=token_count.primary_used_percent if token_count else None,
        primary_window_minutes=token_count.primary_window_minutes if token_count else None,
        primary_resets_at=token_count.primary_resets_at if token_count else None,
        secondary_used_percent=token_count.secondary_used_percent if token_count else None,
        secondary_window_minutes=token_count.secondary_window_minutes if token_count else None,
        secondary_resets_at=token_count.secondary_resets_at if token_count else None,
        plan_type=token_count.plan_type if token_count else None,
        trend_points=trend_points,
        trend_delta_tokens=trend_delta,
        trend_start_timestamp=trend_start,
        trend_end_timestamp=trend_end,
    )
