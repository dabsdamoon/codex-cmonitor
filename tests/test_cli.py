from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

from codex_cmonitor.cli import build_parser
from codex_cmonitor.monitor import build_snapshot
from codex_cmonitor.render import _bar, _distribution_widths, render_snapshot, render_snapshot_live
from rich.console import Group


def test_build_snapshot_returns_no_session_for_missing_codex_home(tmp_path: Path) -> None:
    snapshot = build_snapshot(tmp_path / "missing-codex-home")
    assert snapshot.status == "no_session"
    assert snapshot.captured_at is not None
    assert snapshot.active_session_count == 0


def test_build_snapshot_reads_sqlite_and_rollout_jsonl(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    now = datetime.now(tz=timezone.utc)
    earlier = (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    later = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")

    rollout_path = codex_home / "sessions" / "2026" / "03" / "30" / "rollout-example.jsonl"
    rollout_path.parent.mkdir(parents=True)
    rollout_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": earlier,
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {"total_tokens": 1000},
                                "last_token_usage": {
                                    "input_tokens": 10,
                                    "output_tokens": 2,
                                    "reasoning_output_tokens": 1,
                                },
                            },
                            "rate_limits": {
                                "primary": {
                                    "used_percent": 3.0,
                                    "window_minutes": 300,
                                    "resets_at": 1774863600,
                                },
                                "secondary": {
                                    "used_percent": 2.0,
                                    "window_minutes": 10080,
                                    "resets_at": 1775229821,
                                },
                                "plan_type": "plus",
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": later,
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

    snapshot = build_snapshot(codex_home, trend_minutes=15)

    assert snapshot.status == "ok"
    assert snapshot.active_session_count == 1
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
    assert snapshot.trend_points == [1000, 1234]
    assert snapshot.trend_delta_tokens == 234


def test_build_snapshot_aggregates_multiple_sessions(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    now = datetime.now(tz=timezone.utc)
    t1 = (now - timedelta(minutes=12)).isoformat().replace("+00:00", "Z")
    t2 = (now - timedelta(minutes=8)).isoformat().replace("+00:00", "Z")
    t3 = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    t4 = (now - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")

    rollout_path_1 = codex_home / "sessions" / "2026" / "03" / "30" / "rollout-1.jsonl"
    rollout_path_1.parent.mkdir(parents=True)
    rollout_path_1.write_text(
        "\n".join(
            [
                _token_event(t1, total_tokens=1000, input_tokens=10, output_tokens=2, reasoning_tokens=1, primary_used_percent=2.0, secondary_used_percent=1.0),
                _token_event(t3, total_tokens=1400, input_tokens=30, output_tokens=4, reasoning_tokens=2, primary_used_percent=3.0, secondary_used_percent=2.0),
            ]
        ),
        encoding="utf-8",
    )

    rollout_path_2 = codex_home / "sessions" / "2026" / "03" / "30" / "rollout-2.jsonl"
    rollout_path_2.write_text(
        "\n".join(
            [
                _token_event(t2, total_tokens=2000, input_tokens=20, output_tokens=3, reasoning_tokens=1, primary_used_percent=4.0, secondary_used_percent=3.0),
                _token_event(t4, total_tokens=2600, input_tokens=40, output_tokens=5, reasoning_tokens=3, primary_used_percent=5.0, secondary_used_percent=4.0),
            ]
        ),
        encoding="utf-8",
    )

    db_path = codex_home / "state_5.sqlite"
    _create_threads_table(db_path)
    _insert_thread_row(
        db_path,
        rollout_path_2,
        session_id="session-2",
        title="Latest Session",
        tokens_used=2600,
        updated_at=int((now - timedelta(minutes=1)).timestamp()),
    )
    _insert_thread_row(
        db_path,
        rollout_path_1,
        session_id="session-1",
        title="Earlier Session",
        tokens_used=1400,
        updated_at=int((now - timedelta(minutes=4)).timestamp()),
    )

    snapshot = build_snapshot(codex_home, trend_minutes=15)

    assert snapshot.status == "ok"
    assert snapshot.active_session_count == 2
    assert snapshot.session_id == "session-2"
    assert snapshot.thread_tokens_used == 4000
    assert snapshot.last_total_tokens == 4000
    assert snapshot.primary_used_percent == 5.0
    assert snapshot.secondary_used_percent == 4.0
    assert snapshot.last_input_tokens == 40
    assert snapshot.last_output_tokens == 5
    assert snapshot.last_reasoning_tokens == 3
    assert snapshot.trend_points == [1000, 3000, 3400, 4000]
    assert snapshot.trend_delta_tokens == 3000


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
    assert "Account total" in output
    assert "Active sessions" in output
    assert "4,321" in output


def test_build_parser_accepts_watch_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(["--watch", "--interval", "1.5", "--no-color", "--trend-minutes", "20"])
    assert args.watch is True
    assert args.interval == 1.5
    assert args.no_color is True
    assert args.trend_minutes == 20


def test_build_parser_defaults_include_trend_minutes() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert args.trend_minutes == 15


def test_render_snapshot_live_supports_compact_width(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    rollout_path = codex_home / "sessions" / "2026" / "03" / "30" / "rollout-live.jsonl"
    rollout_path.parent.mkdir(parents=True)
    rollout_path.write_text("", encoding="utf-8")

    db_path = codex_home / "state_5.sqlite"
    _create_threads_table(db_path)
    _insert_thread_row(db_path, rollout_path, title="Narrow Pane Test")

    snapshot = build_snapshot(codex_home)
    renderable = render_snapshot_live(snapshot, width=80)

    assert isinstance(renderable, Group)


def test_render_snapshot_live_supports_ultra_compact_width(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    rollout_path = codex_home / "sessions" / "2026" / "03" / "30" / "rollout-ultra-live.jsonl"
    rollout_path.parent.mkdir(parents=True)
    rollout_path.write_text("", encoding="utf-8")

    db_path = codex_home / "state_5.sqlite"
    _create_threads_table(db_path)
    _insert_thread_row(db_path, rollout_path, title="Ultra Narrow Pane Test")

    snapshot = build_snapshot(codex_home)
    renderable = render_snapshot_live(snapshot, width=60)

    assert isinstance(renderable, Group)


def test_bar_renders_expected_width() -> None:
    bar = _bar(50.0, width=10)
    assert len(bar) == 10
    assert bar.count("█") == 5


def test_distribution_widths_fill_available_width() -> None:
    widths = _distribution_widths([7, 2, 1], width=10)
    assert sum(widths) == 10
    assert widths[0] >= widths[1] >= widths[2]


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


def _insert_thread_row(
    db_path: Path,
    rollout_path: Path,
    *,
    session_id: str = "session-1",
    title: str = "Test Session",
    tokens_used: int = 4321,
    updated_at: int = 1774860137,
) -> None:
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
                session_id,
                str(rollout_path),
                1774857171,
                updated_at,
                "cli",
                "openai",
                "/tmp/project",
                title,
                '{"type":"workspace-write"}',
                "on-request",
                tokens_used,
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


def _token_event(
    timestamp: str,
    *,
    total_tokens: int,
    input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    primary_used_percent: float,
    secondary_used_percent: float,
) -> str:
    return json.dumps(
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"total_tokens": total_tokens},
                    "last_token_usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "reasoning_output_tokens": reasoning_tokens,
                    },
                },
                "rate_limits": {
                    "primary": {
                        "used_percent": primary_used_percent,
                        "window_minutes": 300,
                        "resets_at": 1774863600,
                    },
                    "secondary": {
                        "used_percent": secondary_used_percent,
                        "window_minutes": 10080,
                        "resets_at": 1775229821,
                    },
                    "plan_type": "plus",
                },
            },
        }
    )
