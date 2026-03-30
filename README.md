# codex-cmonitor

`codex-cmonitor` is a terminal monitor for local OpenAI Codex usage.

The goal is to provide a terminal-friendly monitor for Codex similar in spirit to [`cmonitor`](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor), which is the main reference point for this project. Like `cmonitor`, this project is intended to read local session artifacts, surface useful live session status, and eventually grow into a standalone developer tool with stronger analytics.

The current implementation reads local Codex state from `~/.codex`, including:

- all non-archived threads in `state_5.sqlite`
- the session rollout JSONL pointed to by each thread's `rollout_path`
- the latest available `token_count` events across active sessions

It currently shows:

- active session count
- latest-session metadata
- model and working directory
- branch, timestamps, and approval mode
- aggregate account token totals across active sessions
- aggregate recent trend across active sessions
- aggregate input, output, and reasoning token usage across the selected recent window
- latest rate-limit signals when available

## Install

Current install is launcher-based for local development.

From this repository:

```bash
chmod +x bin/codex-cmonitor
ln -sf "$PWD/bin/codex-cmonitor" ~/.local/bin/codex-cmonitor
```

Make sure `~/.local/bin` is on your `PATH`.

Then run:

```bash
codex-cmonitor
codex-cmonitor --json
codex-cmonitor --watch
codex-cmonitor --watch --interval 1 --no-color
codex-cmonitor --trend-minutes 30
```

In watch mode, the live renderer automatically switches across responsive layouts for wide, compact, and very narrow terminal widths. This is intended for tmux side panes and quarter-width views. The narrow layouts prioritize trend, limit meters, and turn-mix visuals over low-value metadata.

Recent token trend is configurable with `--trend-minutes`. The default window is `15` minutes.

By default, `codex-cmonitor` aggregates usage across all active Codex sessions. This is deliberate: Codex limits are account-wide, so a single-session view can under-report the real risk of hitting a limit when multiple sessions are running at once.

The recent-window token rows are also aggregate values. For example, `Input (15m)` and `Output (15m)` are summed across all active sessions within the current trend window, rather than taken from only the latest session event.

## Development

Run directly from the source tree:

```bash
PYTHONPATH=src python3 -m codex_cmonitor
PYTHONPATH=src python3 -m codex_cmonitor --json
PYTHONPATH=src python3 -m codex_cmonitor --watch --interval 1 --no-color
PYTHONPATH=src python3 -m codex_cmonitor --trend-minutes 30
python3 -m pytest -q
```

## Status

This is an early standalone implementation. It currently uses:

- aggregate totals and recent trend across all active sessions
- aggregate bounded-window input/output/reasoning usage across all active sessions
- the latest available `token_count` event as the source of displayed limit percentages
- the most recently updated session as the metadata anchor for title, cwd, and related context
