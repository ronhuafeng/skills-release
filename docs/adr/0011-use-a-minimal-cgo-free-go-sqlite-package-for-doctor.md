---
status: superseded
superseded_by: 0026
---

# Use a minimal CGo-free Go SQLite package for doctor

Only `doctor` will access Codex SQLite state. A new API-only
`harnesses/codex/sqlite-go` package uses `database/sql` with
`modernc.org/sqlite`, opens the database read-only, and exposes the upstream
thread-audit fields `id`, `rollout_path`, `archived`, `source`, and
`model_provider`. It has no mutation, generic query API, ORM, repository layer,
or CLI. This keeps the runtime Go-only and cross-platform without depending on
a separately installed `sqlite3` executable.
