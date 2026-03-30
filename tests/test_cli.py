import json
from pathlib import Path
import sqlite3

from codex_cmonitor.monitor import build_snapshot
from codex_cmonitor.render import render_snapshot


def test_build_snapshot_returns_no_session_for_missing_codex_home(tmp_path: Path) -> None:
    snapshot = build_snapshot(tmp_path / "missing-codex-home")
    assert snapshot.status == "no_session"


def test_build_snapshot_reads_sqlite_and_rollout_jsonl(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    rollout_path = codex_home / "sessions" / "2026" / "03" / "30" / "rollout-example.jsonl"
    rollout_path.parent.mkdir(parents=True)
    rollout_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-30T08:00:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {"total_tokens": 1234},
                                "last_token_usage": {
                                    "input_tokens": 100,
                                    "output_tokens": 20,
                                    "reasoning_output_tokens": 5,
                                },
                            },
                            "rate_limits": {
                                "primary": {
                                    "used_percent": 4.0,
                                    "window_minutes": 300,
                                    "resets_at": 1774863600,
                                },
                                "secondary": {
                                    "used_percent": 3.0,
                                    "window_minutes": 10080,
                                    "resets_at": 1775229821,
                                },
                                "plan_type": "plus",
                            },
                        },
                    }
                )
            ]
        ),
        encoding="utf-8",
    )

    db_path = codex_home / "state_5.sqlite"
    _create_threads_table(db_path)
    _insert_thread_row(db_path, rollout_path)

    snapshot = build_snapshot(codex_home)

    assert snapshot.status == "ok"
    assert snapshot.session_id == "session-1"
    assert snapshot.model == "gpt-5.4"
    assert snapshot.cwd == "/tmp/project"
    assert snapshot.git_branch == "feat/test"
    assert snapshot.thread_tokens_used == 4321
    assert snapshot.last_total_tokens == 1234
    assert snapshot.last_input_tokens == 100
    assert snapshot.last_output_tokens == 20
    assert snapshot.last_reasoning_tokens == 5
    assert snapshot.primary_used_percent == 4.0
    assert snapshot.secondary_used_percent == 3.0
    assert snapshot.plan_type == "plus"


def test_render_snapshot_text_contains_live_fields(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    rollout_path = codex_home / "sessions" / "2026" / "03" / "30" / "rollout-render.jsonl"
    rollout_path.parent.mkdir(parents=True)
    rollout_path.write_text("", encoding="utf-8")

    db_path = codex_home / "state_5.sqlite"
    _create_threads_table(db_path)
    _insert_thread_row(db_path, rollout_path, title="Render Test")

    snapshot = build_snapshot(codex_home)
    output = render_snapshot(snapshot)

    assert "codex-cmonitor" in output
    assert "Render Test" in output
    assert "thread tokens: 4,321" in output


def _create_threads_table(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                rollout_path TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                source TEXT NOT NULL,
                model_provider TEXT NOT NULL,
                cwd TEXT NOT NULL,
                title TEXT NOT NULL,
                sandbox_policy TEXT NOT NULL,
                approval_mode TEXT NOT NULL,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                has_user_event INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                archived_at INTEGER,
                git_sha TEXT,
                git_branch TEXT,
                git_origin_url TEXT,
                cli_version TEXT NOT NULL DEFAULT '',
                first_user_message TEXT NOT NULL DEFAULT '',
                agent_nickname TEXT,
                agent_role TEXT,
                memory_mode TEXT NOT NULL DEFAULT 'enabled',
                model TEXT,
                reasoning_effort TEXT,
                agent_path TEXT
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _insert_thread_row(db_path: Path, rollout_path: Path, *, title: str = "Test Session") -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            INSERT INTO threads (
                id,
                rollout_path,
                created_at,
                updated_at,
                source,
                model_provider,
                cwd,
                title,
                sandbox_policy,
                approval_mode,
                tokens_used,
                has_user_event,
                archived,
                git_branch,
                cli_version,
                first_user_message,
                memory_mode,
                model,
                reasoning_effort
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "session-1",
                str(rollout_path),
                1774857171,
                1774860137,
                "cli",
                "openai",
                "/tmp/project",
                title,
                '{"type":"workspace-write"}',
                "on-request",
                4321,
                1,
                0,
                "feat/test",
                "0.117.0",
                "hello",
                "enabled",
                "gpt-5.4",
                "medium",
            ),
        )
        connection.commit()
    finally:
        connection.close()
