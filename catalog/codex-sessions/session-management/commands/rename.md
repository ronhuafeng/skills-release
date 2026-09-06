# rename

## Goal

Rename one or more host-bound Codex tasks through the app-server that owns each
task, then verify the visible title through Codex App.

Only process tasks on registered hosts whose CWD belongs to a matching saved
project. The target identity is `(hostId, threadId)`, not a title, path, list
position, or cross-host thread id.

## Title sources

Use one mutation workflow regardless of how the title was chosen:

- For an ordinary task, read its Codex App history and choose a concise,
  one-line title grounded in its material objective.
- For a split manifest part, use the exact title already fixed by the manifest.
  Obtain the immutable mappings with strict JSON input:

  ```text
  printf '%s\n' '{"split_manifest_path":"<absolute-path>"}' |
    session-management rename manifest-targets
  ```

  The read-only command validates the published split manifest and returns only
  ordered `thread_id → title` targets. Exit `0` returns the targets, exit `2`
  means malformed input, and exit `3` means manifest validation failed.

Do not regenerate or reinterpret a manifest title. Ordinary semantic judgment
does not require rollout collection or a manifest.

## Execution

Process targets sequentially. Stop at the first failure.

1. Resolve the target through Codex App discovery. Require exactly one
   registered `hostId`, exact `threadId`, matching saved project, and supported
   Codex task.
2. Call the Codex App `read_thread` operation with that host and id. For an
   ordinary title, follow read cursors only as far as needed to understand the
   material objective. For a manifest title, use the read only as identity and
   CWD preflight.
3. Connect directly to `codex app-server` on the target host. Use SSH only as
   transport for a registered remote host. Initialize with
   `experimentalApi: true` and send `initialized`.
4. Call `thread/read` with the exact id. Require the same id and CWD observed by
   Codex App.
5. Call `thread/name/set` exactly once with the selected title, then close the
   connection. Do not use a mutation interface that cannot bind the target
   host.
6. Use the host-bound Codex App `read_thread` operation to require the exact id
   and title. The read may repeat within one short bound while App state
   converges; the mutation must never repeat.
7. Record the verified target before continuing to the next one.

Do not read or write SQLite, rename rollout files, project app rows through a
local schema, or fall back between semantic and manifest title sources.

## Stop rules

- A deterministic discovery or manifest-input error may be corrected before
  any mutation is issued.
- After `thread/name/set` is issued, never call it again for that target,
  including after timeout or error.
- A successful mutation with incomplete App readback is `Rename accepted; App
  readback incomplete`, not permission to retry.
- Earlier verified targets remain completed when a later target stops.

## Output

```markdown
Rename completed

| Host | Task | Previous title | New title |
| --- | --- | --- | --- |
| `<host>` | `<thread-id>` | `<previous-title or untitled>` | `<verified-title>` |
```

On failure, report the completed rows, the exact target and boundary that
stopped, and whether its mutation was issued. Do not print completion for an
unverified target.
