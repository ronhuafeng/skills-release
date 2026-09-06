# rehome

## Goal

Move one idle local rollout to a valid CWD on a registered remote Codex host.
Preserve the thread id, bind and prove the destination, then archive the source
through the Codex App that owns it.

Rehome moves session state only. It does not move Git state or create a Codex
worktree. Use native handoff when Git or worktree ownership must move too.

## Input

Use one source `thread_id`, one registered destination `host`, and one absolute
destination `cwd`. The CWD may be any existing directory on that host.

## Preconditions

1. Use the available Codex App `list_projects` operation to require at least one
   remote project whose `hostDisplayName` equals `host`.
2. Use the Codex App `read_thread` operation on the local source. Require the
   exact id and status `idle` or `notLoaded`.
3. The destination CWD and destination `~/.codex` must already exist.
4. The destination must not already contain the thread id in active or archived
   rollouts.

## Execution

Perform these boundaries in order. Never repeat either mutation.

1. Establish the destination exactly once:

   ```text
   printf '%s\n' '{"thread_id":"<id>","host":"<host>","cwd":"<cwd>"}' |
     session-management rehome establish
   ```

   The executable hashes the active source, minimally rebinds Default Resume
   CWD and Indexed Thread CWD, performs a no-clobber same-id install, resumes the
   destination through its app-server, and rechecks the active source snapshot.

2. Use the Codex App `read_thread` operation with the destination `hostId`.
   Require the exact id, requested CWD, and persisted task history. This is the
   app integration readback.

3. Call the Codex App `set_thread_archived` operation once with the local source
   `hostId`, exact `threadId`, and `archived: true`. The running Codex App is the
   source archive authority. Do not start another local app-server.

4. Prove the archive with the source path and digest returned by step 1:

   ```text
   printf '%s\n' '{"thread_id":"<id>","source_rollout_path":"<path>","source_sha256":"<sha256>"}' |
     session-management rehome verify-archive
   ```

   Success requires the active source path to be absent and the exact archived
   identity and SHA-256 to match. This step is read only and may be repeated
   after correcting an input or transient read failure. It never repeats the
   archive mutation.

SQLite and indexes are never copied or written directly. Historical turn CWD,
workspace roots, world state, and Git metadata are not rewritten.

## Stop rules

- If destination establishment issued an install, do not establish the same id
  again. Read the returned partial evidence.
- If destination App readback fails, stop before source archive.
- If the source archive call returns an error or uncertain result, do not call
  it again. Read source state.
- If archive proof reports a digest mismatch, stop. The archived source is the
  retained authority; do not delete the destination or mutate SQLite.
- Do not automatically unarchive the source, substitute a model, delete the
  destination, or fall back to native handoff.

## Output

```markdown
Rehome completed

| Result | Value |
| --- | --- |
| Task | `<thread-id>` |
| Host | `<destination-host>` |
| Workspace | `<destination-cwd>` |
| Rollout | `<destination-rollout-path>` |
| Source SHA-256 | `<source-sha256>` |
| Destination SHA-256 | `<destination-sha256>` |
| Destination provider | `<destination-effective-provider>` |
| Final model | `<preserved-current-model>` |
| Source archive | `<verified-archived-path>` |
```
