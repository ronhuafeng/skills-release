# Session Management

This glossary defines stable language shared by session-management commands and
packages. Command documents own procedures and protocol fields. Package READMEs
own executable mechanics.

## Language

**Raw Rollout Line**:
One persisted JSONL record together with its source position and original
bytes. It remains evidence even when no current typed view consumes it.
_Avoid_: normalized message, command-specific model

**Session Metadata**:
The persisted metadata that establishes a session's original identity and
defaults. It is evidence about creation, not a universal statement about the
session's current execution state.
_Avoid_: current thread state, destination configuration

**Rollout Reader**:
The single Codex-specific package that reads Raw Rollout Lines and exposes
narrow persisted facts without replacing the raw evidence authority.
_Avoid_: command-local decoder, complete in-memory rollout

**Visible Message Projection**:
A human-facing view of persisted user and assistant messages. It is a derived
view and never replaces the Raw Rollout Lines.
_Avoid_: complete rollout, response transcript

**Selected Rollout**:
One explicitly selected rollout and the fixed source revision used by a
read-only or mutation plan. Later append-only records are outside that selected
revision.
_Avoid_: current live tail, inferred session identity

**Partition Window**:
One bounded, source-ordered portion of semantic session evidence and legal
objective anchors from a Selected Rollout.
_Avoid_: complete timeline, arbitrary page

**Scan Receipt**:
The executable proof that one partition inspection covered its complete frozen
source revision. It proves protocol coverage, not semantic understanding.
_Avoid_: partial continuation, semantic correctness proof

**Objective Ledger**:
Codex's transient compact memory of objectives, evidence, completion state, and
boundary judgment while reviewing Partition Windows. Session-management does
not persist it.
_Avoid_: second transcript, executable classifier

**Partition Plan**:
The validated chronological mapping from Codex-authored objective titles and
legal anchors to complete source ranges in one Selected Rollout. Journal and
split share it.
_Avoid_: split manifest, durable segmentation state

**Session Rename**:
The host-bound title mutation performed through the app-server that owns the
task and verified through Codex App.
_Avoid_: SQLite write, rollout mutation

**Session Delete**:
Permanent removal of one host-bound root task and its native spawned subagent
subtree through the owning app-server.
_Avoid_: rollout deletion, root-only deletion

**Default Resume CWD**:
The persisted working directory used when resume has no explicit override.
_Avoid_: current indexed CWD, repository membership

**Indexed Thread CWD**:
The current working directory in Codex's derived thread metadata.
_Avoid_: historical turn CWD, repository ownership

**Turn Execution CWD**:
The working directory persisted for one historical turn.
_Avoid_: current session CWD, destination workspace

**Historical Session Provider**:
The provider persisted when the session was created.
_Avoid_: current provider, destination provider

**Persisted Current Provider**:
The latest provider represented by persisted session history.
_Avoid_: initial provider, destination default

**Current Thread Model**:
The latest model represented by persisted thread history, independent of
provider identity.
_Avoid_: destination default model

**Destination Effective Provider**:
The provider selected by the destination app-server for the destination
workspace at execution time.
_Avoid_: source provider, global assumption

**Session Rehome**:
Same-identity session relocation to a valid working directory on a registered
remote Codex host, including destination proof and source archival. It does not
move Git state or worktree ownership.
_Avoid_: fork, new session identity, SQLite transfer
