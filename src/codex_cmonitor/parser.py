from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any


@dataclass
class ThreadRecord:
    session_id: str
    rollout_path: Path
    created_at: int
    updated_at: int
    cwd: str
    title: str
    model_provider: str
    model: str
    reasoning_effort: str
    approval_mode: str
    sandbox_policy: str
    git_branch: str
    tokens_used: int


@dataclass
class TokenCountRecord:
    timestamp: str
    timestamp_unix: int | None
    total_tokens: int | None
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    primary_used_percent: float | None
    primary_window_minutes: int | None
    primary_resets_at: int | None
    secondary_used_percent: float | None
    secondary_window_minutes: int | None
    secondary_resets_at: int | None
    plan_type: str | None


def resolve_codex_home(codex_home: str | Path | None = None) -> Path:
    if codex_home is None:
        env_value = os.environ.get("CODEX_HOME")
        if env_value:
            return Path(env_value).expanduser()
        return Path.home() / ".codex"
    return Path(codex_home).expanduser()


def get_state_db_path(codex_home: str | Path | None = None) -> Path:
    return resolve_codex_home(codex_home) / "state_5.sqlite"


def fetch_latest_thread(codex_home: str | Path | None = None) -> ThreadRecord | None:
    db_path = get_state_db_path(codex_home)
    if not db_path.exists():
        return None

    query = """
        SELECT
            id,
            rollout_path,
            created_at,
            updated_at,
            cwd,
            title,
            model_provider,
            COALESCE(model, '') AS model,
            COALESCE(reasoning_effort, '') AS reasoning_effort,
            approval_mode,
            sandbox_policy,
            COALESCE(git_branch, '') AS git_branch,
            tokens_used
        FROM threads
        WHERE archived = 0
          AND rollout_path != ''
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
    """

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(query).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return ThreadRecord(
        session_id=row["id"],
        rollout_path=Path(row["rollout_path"]).expanduser(),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
        cwd=row["cwd"],
        title=row["title"],
        model_provider=row["model_provider"],
        model=row["model"],
        reasoning_effort=row["reasoning_effort"],
        approval_mode=row["approval_mode"],
        sandbox_policy=row["sandbox_policy"],
        git_branch=row["git_branch"],
        tokens_used=int(row["tokens_used"]),
    )


def fetch_latest_token_count(rollout_path: str | Path) -> TokenCountRecord | None:
    path = Path(rollout_path).expanduser()
    if not path.exists():
        return None

    latest: TokenCountRecord | None = None
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            record = _parse_token_count_event(event)
            if record is not None:
                latest = record
    return latest


def fetch_recent_token_counts(
    rollout_path: str | Path,
    *,
    minutes: int,
    now_ts: int | None = None,
) -> list[TokenCountRecord]:
    path = Path(rollout_path).expanduser()
    if not path.exists():
        return []

    if now_ts is None:
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    cutoff_ts = now_ts - max(0, minutes * 60)

    records: list[TokenCountRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            record = _parse_token_count_event(event)
            if record is None or record.timestamp_unix is None:
                continue
            if record.timestamp_unix >= cutoff_ts:
                records.append(record)
    return records


def _parse_token_count_event(event: dict[str, Any]) -> TokenCountRecord | None:
    if event.get("type") != "event_msg":
        return None

    payload = event.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None

    info = payload.get("info")
    total_usage = info.get("total_token_usage") if isinstance(info, dict) else None
    last_usage = info.get("last_token_usage") if isinstance(info, dict) else None

    rate_limits = payload.get("rate_limits")
    primary = rate_limits.get("primary") if isinstance(rate_limits, dict) else None
    secondary = rate_limits.get("secondary") if isinstance(rate_limits, dict) else None

    return TokenCountRecord(
        timestamp=str(event.get("timestamp", "")),
        timestamp_unix=_parse_timestamp_to_unix(event.get("timestamp")),
        total_tokens=_get_int(total_usage, "total_tokens"),
        input_tokens=_get_int(last_usage, "input_tokens"),
        output_tokens=_get_int(last_usage, "output_tokens"),
        reasoning_tokens=_get_int(last_usage, "reasoning_output_tokens"),
        primary_used_percent=_get_float(primary, "used_percent"),
        primary_window_minutes=_get_int(primary, "window_minutes"),
        primary_resets_at=_get_int(primary, "resets_at"),
        secondary_used_percent=_get_float(secondary, "used_percent"),
        secondary_window_minutes=_get_int(secondary, "window_minutes"),
        secondary_resets_at=_get_int(secondary, "resets_at"),
        plan_type=rate_limits.get("plan_type") if isinstance(rate_limits, dict) else None,
    )


def _parse_timestamp_to_unix(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _get_int(data: Any, key: str) -> int | None:
    if not isinstance(data, dict):
        return None
    value = data.get(key)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_float(data: Any, key: str) -> float | None:
    if not isinstance(data, dict):
        return None
    value = data.get(key)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
