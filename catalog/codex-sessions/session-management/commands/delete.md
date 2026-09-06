# delete

## Goal

Permanently delete one host-bound Codex root task and its native spawned
subagent subtree through the app-server that owns the task.

## Target and scope

Require one complete task UUID stated by the user. Resolve it to exactly one
`(hostId, threadId)` in Codex App state. The host must be registered, and the
task CWD must belong to a matching saved project. If the same id exists on more
than one host, ask the user to select the host.

Native `thread/delete` removes the root and its native spawned subagent subtree.
Ordinary forks and rehomed copies are outside that subtree. Root-only deletion
is unsupported. Before mutation, require explicit authorization for the subtree
scope unless the user already authorized it.

Do not accept a title, path, prefix, inferred current task, filesystem rollout,
or SQLite row as the target authority.

## Execution

1. Use Codex App discovery and its `read_thread` operation with the exact
   `hostId` and `threadId`. Require the same id, a matching saved project, and
   status `idle` or `notLoaded`.
2. Connect directly to `codex app-server` on that host. Use SSH only as the
   transport for a registered remote host. Initialize with
   `experimentalApi: true` and send `initialized`.
3. Call `thread/read` with the exact id. Require the same id, CWD, and non-running
   state observed by Codex App.
4. Call `thread/delete` exactly once with `{ "threadId": "<thread-id>" }`.
   A successful response is the mutation authority. Record any immediate
   `thread/deleted` notifications as supplemental evidence only.
5. Close the app-server connection. Use the host-bound Codex App `read_thread`
   operation to require that the root is absent. This readback is read only and
   may repeat within one short bound while App discovery converges.

Never call `thread/delete` again after its request was issued. A timeout,
missing notification, failed readback, or still-visible cached row does not
authorize another mutation.

Do not inspect or remove rollout files, query SQLite, edit spawn relationships,
or add an executable fallback. Those are lower-level
projections of state owned by `thread/delete`.

## Results

Report completion only when `thread/delete` returned success and the host-bound
App readback no longer finds the root:

```markdown
Delete completed

| Result | Value |
| --- | --- |
| Deleted task | `<thread-id>` |
| Host | `<host>` |
| Saved project | `<project>` |
| Scope | `Root and native spawned subagent subtree` |
| Previous title | `<title or untitled>` |
```

If mutation returned success but App readback did not converge, report
`Delete accepted; App readback incomplete`. If the mutation response was
uncertain, report `Delete outcome uncertain`. In both cases, include the exact
boundary and do not retry or print the completion form.
