# split

## Goal

Split one explicitly selected rollout into one or more chronologically
contiguous, rollout-valid sessions inside a new staging Codex home. Optionally
install those sessions into one registered Codex App project.

## Contract

- Read [partition.md](partition.md) and obtain one validated `PartitionPlan`
  before execute.
- Split requires `receipt.tail_open: false`.
- Split accepts a self-contained root rollout. It stops on fork, subagent, or
  external history lineage because the manifest binds only one physical source.
- Every raw body record belongs to exactly one generated rollout. Generated
  metadata and Goal identities must agree with each generated session id.
- A paginated source must have complete dense ordinals. Each generated rollout
  starts again at ordinal `0` and has a fresh context-window identity. Legacy
  sources remain ordinal-free.
- The source rollout, live Codex home, SQLite, indexes, and visible task state
  remain unchanged.
- Materialization occurs only on an explicit split request and publishes only
  after complete validation.

## Execute

Pass the exact returned plan on stdin:

```text
session-management split execute \
  --output-codex-home <absolute-nonexistent-path>
```

The output path must be under an existing non-symlink parent and outside the
source Codex home. The caller owns this isolated staging location.

Execute rederives the plan and proves that the source is a self-contained root
before creating output identities. It scans the frozen prefix in order, writes
one current part at a time, updates range and output proofs incrementally,
validates the manifest and every generated line through a second streaming
scan, independently verifies standalone metadata and ordinal continuity,
revalidates the prefix, and performs one no-replace atomic rename. It rejects
`tail_open: true` before creating output identities.

Failure before rename publishes nothing. If publication succeeds but the
response is lost or invalid, treat the result as unknown and inspect the exact
target. Never retry an uncertain publication.

## Install

Install only from a successfully published split manifest. The validated
manifest and its staging rollouts are the source authority. The original source
task does not need to be visible in the current Codex App.

Before install, use Codex App project discovery to resolve:

- `local`, or one registered SSH host;
- one App project ID and its destination CWD on that host.

Keep the App project ID for final readback. Do not pass it to the executable.

Do not pass the Codex App project ID to the executable. App project IDs and
native app-server project IDs are different identities. The executable lists
the target app-server projects and requires exactly one project root equal to
the destination CWD.

The destination app-server must expose project list and task project
assignment. Missing or ambiguous project discovery stops before a file effect.
Missing project assignment leaves the installed part in the reported partial
state and stops.

Pass that destination on stdin:

```text
printf '%s\n' \
  '{"split_manifest_path":"<absolute-manifest-path>","host":"<local-or-ssh-host>","cwd":"<absolute-project-root>"}' |
  session-management split install
```

The executable validates the manifest and project before any destination file
effect. It processes manifest parts in order. For each part, it rebinds only
the generated session's resume and indexed CWD, performs a no-clobber rollout
install, activates the session through the destination app-server, assigns the
selected project, and reads back the exact task.

Stop at the first part that cannot be proved complete. Keep earlier completed
parts, the staging bundle, and any uncertain destination artifact. Do not roll
back, delete, repeat an uncertain persistent mutation, or continue with later
parts. Use exact readback to resolve an uncertain install, activation, or
project assignment when possible. App activation is process-local. After an
app-server restart, it may run again only when authoritative readback reports
the exact task as `notLoaded`.

Project assignment is destination app-server state and is not written into the
split manifest. Install does not assign or inherit a sidebar section.

## Final gate

A successful `split execute` result is authoritative for plan matching, exact
raw coverage, generated identity rewriting, hashes, manifest validation, and
atomic staging publication. Report the staging root, manifest, generated
session ids, number of windows, largest window response, and any oversized
record.

A successful `split install` result reports the resolved `native_project_id`
and proves the destination effects for each completed manifest part, including
native project assignment. Re-read Codex App projects and require the original
App project ID, host, and CWD. Then use Codex App `read_thread` with that host
and each generated task id. Require the requested CWD and persisted task
history. This host-bound App readback is the final visibility authority. Do
not compare App project IDs with native app-server project IDs.

`rehome` is not a split installation path. It moves one existing task with the
same identity and archives its source. Split installation creates new manifest
identities and leaves the original source and staging bundle intact.
