from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codex_cmonitor.parser import (
    TokenCountRecord,
    ThreadRecord,
    fetch_threads,
    fetch_latest_token_count,
    fetch_recent_token_counts,
)


@dataclass
class SessionSummary:
    session_id: str
    rollout_path: Path
    title: str
    model_provider: str
    model: str
    reasoning_effort: str
    cwd: str
    git_branch: str
    approval_mode: str
    sandbox_policy: str
    created_at: int
    updated_at: int
    thread_tokens_used: int
    token_count: TokenCountRecord | None
    recent_token_counts: list[TokenCountRecord]


@dataclass
class AggregateSessionSummary:
    active_session_count: int
    latest_session: SessionSummary
    total_thread_tokens_used: int
    latest_total_tokens: int | None
    token_count: TokenCountRecord | None
    recent_token_counts: list[TokenCountRecord]


def get_session_summary(
    codex_home: str | Path | None = None,
    *,
    trend_minutes: int = 15,
    now_ts: int | None = None,
) -> SessionSummary | None:
    threads = fetch_threads(codex_home)
    thread = threads[0] if threads else None
    if thread is None:
        return None

    token_count = fetch_latest_token_count(thread.rollout_path)
    recent_token_counts = fetch_recent_token_counts(
        thread.rollout_path,
        minutes=trend_minutes,
        now_ts=now_ts,
    )
    return _to_session_summary(thread, token_count, recent_token_counts)


def get_aggregate_session(
    codex_home: str | Path | None = None,
    *,
    trend_minutes: int = 15,
    now_ts: int | None = None,
) -> AggregateSessionSummary | None:
    threads = fetch_threads(codex_home)
    if not threads:
        return None

    session_summaries: list[SessionSummary] = []
    for thread in threads:
        token_count = fetch_latest_token_count(thread.rollout_path)
        recent_token_counts = fetch_recent_token_counts(
            thread.rollout_path,
            minutes=trend_minutes,
            now_ts=now_ts,
        )
        session_summaries.append(
            _to_session_summary(thread, token_count, recent_token_counts)
        )

    latest_session = session_summaries[0]
    total_thread_tokens_used = sum(session.thread_tokens_used for session in session_summaries)
    latest_total_tokens = sum(
        session.token_count.total_tokens or 0
        for session in session_summaries
        if session.token_count is not None
    )
    latest_global_token_count = _pick_latest_token_count(session_summaries)
    recent_token_counts = _aggregate_recent_token_counts(session_summaries)

    return AggregateSessionSummary(
        active_session_count=len(session_summaries),
        latest_session=latest_session,
        total_thread_tokens_used=total_thread_tokens_used,
        latest_total_tokens=latest_total_tokens,
        token_count=latest_global_token_count,
        recent_token_counts=recent_token_counts,
    )


def _to_session_summary(
    thread: ThreadRecord,
    token_count: TokenCountRecord | None,
    recent_token_counts: list[TokenCountRecord],
) -> SessionSummary:
    return SessionSummary(
        session_id=thread.session_id,
        rollout_path=thread.rollout_path,
        title=thread.title,
        model_provider=thread.model_provider,
        model=thread.model,
        reasoning_effort=thread.reasoning_effort,
        cwd=thread.cwd,
        git_branch=thread.git_branch,
        approval_mode=thread.approval_mode,
        sandbox_policy=thread.sandbox_policy,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        thread_tokens_used=thread.tokens_used,
        token_count=token_count,
        recent_token_counts=recent_token_counts,
    )


def _pick_latest_token_count(sessions: list[SessionSummary]) -> TokenCountRecord | None:
    latest: TokenCountRecord | None = None
    latest_ts = -1
    for session in sessions:
        token_count = session.token_count
        if token_count is None or token_count.timestamp_unix is None:
            continue
        if token_count.timestamp_unix > latest_ts:
            latest_ts = token_count.timestamp_unix
            latest = token_count
    return latest


def _aggregate_recent_token_counts(
    sessions: list[SessionSummary],
) -> list[TokenCountRecord]:
    events: list[tuple[int, int, TokenCountRecord]] = []
    for session_index, session in enumerate(sessions):
        for record in session.recent_token_counts:
            if record.timestamp_unix is None or record.total_tokens is None:
                continue
            events.append((record.timestamp_unix, session_index, record))

    events.sort(key=lambda item: (item[0], item[1]))
    if not events:
        return []

    latest_totals = [0 for _ in sessions]
    aggregated: list[TokenCountRecord] = []
    for timestamp_unix, session_index, record in events:
        latest_totals[session_index] = record.total_tokens or 0
        aggregated.append(
            TokenCountRecord(
                timestamp=record.timestamp,
                timestamp_unix=timestamp_unix,
                total_tokens=sum(latest_totals),
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                reasoning_tokens=record.reasoning_tokens,
                primary_used_percent=record.primary_used_percent,
                primary_window_minutes=record.primary_window_minutes,
                primary_resets_at=record.primary_resets_at,
                secondary_used_percent=record.secondary_used_percent,
                secondary_window_minutes=record.secondary_window_minutes,
                secondary_resets_at=record.secondary_resets_at,
                plan_type=record.plan_type,
            )
        )
    return aggregated
