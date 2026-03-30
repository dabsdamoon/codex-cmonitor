from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codex_cmonitor.parser import (
    TokenCountRecord,
    ThreadRecord,
    fetch_latest_thread,
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


def get_active_session(
    codex_home: str | Path | None = None,
    *,
    trend_minutes: int = 15,
    now_ts: int | None = None,
) -> SessionSummary | None:
    thread = fetch_latest_thread(codex_home)
    if thread is None:
        return None

    token_count = fetch_latest_token_count(thread.rollout_path)
    recent_token_counts = fetch_recent_token_counts(
        thread.rollout_path,
        minutes=trend_minutes,
        now_ts=now_ts,
    )
    return _to_session_summary(thread, token_count, recent_token_counts)


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
