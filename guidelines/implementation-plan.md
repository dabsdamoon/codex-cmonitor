# codex-cmonitor Plan

## Goal

Build a standalone monitoring tool for OpenAI Codex sessions that is inspired by `cmonitor`, but adapted to Codex's local data model and workflow.

## Reference

The main reference is [`cmonitor`](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor).

Important distinction:

- `cmonitor` reads Claude local usage artifacts and performs analytics on structured session data.
- `codex-cmonitor` should follow the same general philosophy where possible, but use Codex local state under `~/.codex` instead of Claude's file layout.

## Confirmed Local Codex Data Sources

Current observed local artifacts include:

- `~/.codex/sessions/YYYY/MM/DD/*.jsonl`
- `~/.codex/history.jsonl`
- `~/.codex/state_5.sqlite`

Currently useful signals observed:

- session metadata
- cwd
- model and provider
- sandbox and approval mode
- session timestamps
- `tokens_used` in the `threads` table
- `token_count` events in session JSONL
- rate-limit percentages and reset times in session JSONL
- git branch in SQLite thread metadata

## Phase 1

Build a minimal local monitor that is useful in a tmux pane and also viable as the basis of a standalone CLI.

Deliverables:

- a small CLI entrypoint
- active-session detection
- session summary rendering
- refresh loop
- plain terminal output

Initial displayed fields:

- session id
- title
- cwd
- model
- git branch
- created time
- updated time
- total tokens used
- last token usage
- primary and secondary rate-limit percentages
- reset timestamps when available

## Phase 2

Stabilize session selection and data parsing.

Work items:

- map "active session" reliably when multiple Codex sessions exist
- reconcile SQLite thread data with session JSONL events
- handle missing, partial, or stale session artifacts
- isolate parsing logic from rendering logic
- add schema-tolerant parsing with graceful fallback

## Phase 3

Promote from personal script to standalone tool.

Work items:

- package as installable CLI
- define repository structure and module boundaries
- add configuration file support
- document install and usage flows
- support basic testing against recorded fixtures
- define compatibility expectations across Codex versions

## Phase 4

Add richer analytics only after raw data stability is proven.

Potential features:

- burn-rate calculations
- session trend summaries
- threshold warnings
- inferred cost estimates
- multiple active session views
- historical reporting

These should be treated as secondary because Codex local token and limit signals appear usable now, but cost signals have not yet been verified as stable local fields.

## Architecture Direction

Recommended early structure:

- `parser`: reads Codex SQLite and JSONL artifacts
- `session_store`: resolves latest and active sessions
- `monitor`: polling loop and state assembly
- `render`: terminal output formatting
- `cli`: command-line entrypoint and flags

This keeps the first version small while making later extraction and packaging straightforward.

## Risks

- Codex local artifact formats may change across CLI versions.
- The definition of "active session" may be ambiguous.
- Rate-limit and token fields may not be present in every session event stream.
- Cost estimation may be misleading if based on inference rather than native Codex fields.

## Non-Goals For First Version

- billing-grade accuracy
- cloud synchronization
- dashboard UI
- deep historical analytics
- hard dependency on tmux

## Success Criteria

The first version is successful if it can:

- identify a likely active Codex session
- display useful live session status from local artifacts
- degrade safely when fields are missing
- serve as the foundation for a future standalone public tool
