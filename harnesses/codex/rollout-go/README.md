# codex/rollout-go

The sole Go package that owns Codex rollout semantics.

## Ordered scan

`Scan` visits each non-empty Raw Rollout Line in source order. `ScanRange`
resumes at an exact byte and physical-line cursor through a fixed byte boundary
and exposes the current record cursor for bounded deferral. The package owns
file open, decode, source location, and close. It never retains the complete
rollout.

Each `Record` keeps the original JSON bytes, source line, optional common
`Envelope`, and line-local structural error. Unknown fields and variants remain
available in the raw record.

## Projections

Path-level functions scan incrementally and retain only their result or current
validation state:

- `SessionMeta` decodes the initial upstream `session_meta` payload;
- `ExecutionSettings` projects the latest model and provider authorities;
- `VisibleMessages` and `GoalUpdates` select persisted facts;
- `InspectCoverage` counts variants and field shapes;
- `ThreadID` and `ValidateThreadIdentity` verify persisted identity;
- `RebindResumeAndIndexedCWD` reads one file snapshot and produces the complete
  transport body required by rehome;
- `RebindResumeAndIndexedCWDBytes` applies the same projection to caller-bound
  bytes when a manifest or another authority must prove the exact input.

`Record.Content`, `Record.TurnRecord`, and `Record.ToolRecord` provide narrow
incremental facts. `TurnRecord` preserves the upstream optional Turn id on
`turn_aborted`. Command-owned state decides projected lifecycle completion,
unresolved call boundaries, and legal cuts. `Record.ProjectGeneratedSession`
projects one source record into a standalone generated split rollout.

`Record.Content` is the model-facing semantic projection. It excludes reasoning
records and every tool payload. `Record.ToolRecord` exposes only call type and
identity for private lifecycle validation; it does not expose arguments,
outputs, or reasoning content.

`ResolveSessionFile` accepts native
`rollout-<timestamp>-<uuid>.jsonl` filenames, searches active sessions first,
and optionally searches archived sessions second.

## Selection

`Select` streams matching raw records to its caller. With no filters it passes
through every non-empty line, including malformed evidence. With filters it
first validates the complete source and emits nothing on structural failure;
its second scan applies recursive partial-object matching.

The package performs no file mutation, semantic aliases, command-specific
rendering, fallback, or persistent scan state.

## Validation

```bash
GOWORK=off go test ./... -count=1
```
