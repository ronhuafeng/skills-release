# journal

## Goal

Create compact, evidence-backed working memory for one explicitly selected
session and maintain `codex_journal.md` as its index.

## Contract

- Read [partition.md](partition.md) and obtain one validated `PartitionPlan`
  before writing.
- Codex writes the journal from the validated plan and retained semantic
  evidence. The executable does not classify, summarize, render, verify, or
  write journal claims.
- Journal accepts `receipt.tail_open: true`. It records the frozen snapshot and
  keeps the last objective partial.
- Journal creates no split manifest, generated identity, staging Codex home, or
  generated rollout. If the same request includes split, pass the exact plan to
  `split execute` and require its final gate before writing the journal.
- Use Codex app session tools to resolve the journal root from the selected
  source session's `cwd`. Stop if the matching session or `cwd` is unavailable.
- Within that root, write only `codex_journal.d/*.md` and `codex_journal.md`.
  Never mutate rollout JSONL, SQLite, indexes, or thread state.

## Target authority

Resolve the requested task to exactly one `(hostId, threadId)` through Codex
App. The host must be registered, and the task CWD must belong to a matching
saved project. If the same thread id exists on more than one host, ask the user
to select the host.

Use the host-bound App `read_thread` result as the CWD authority. Run partition
against that same host and source. Do not substitute the current repository,
project root, or a same-id task on another host. Host and project identify the
operation; they do not become fields in the Partition Plan or journal.

Read the exact target again immediately before writing and require the same CWD.
After writing, read the same `(hostId, threadId)` and require that its CWD still
equals the journal root. If the task or CWD changes after the write, report the
exact residual journal location and stop. Do not move, rewrite, or remove the
written files automatically.

## Write the journal

Before any journal read or write, resolve the index, journal directory, and
fragment paths. Require every resolved path, or the resolved parent of a new
path, to remain inside the exact app-reported CWD. Stop if a symlink escapes
that root.

Write one source-session fragment:

```text
codex_journal.d/<YYYY-MM-DD>-<session-id>.md
```

Use the work date of the source session's first persisted user message. For
each plan part, use the Objective Ledger and evidence retained from windows
whose `source_line` falls within that part's inclusive range. Do not fetch or
copy raw lifecycle or tool records into the journal.

Use this semantic schema:

- **Intent** records the objective, in-scope boundary, and material constraints.
- **Decisions** records consequential choices and, when supported, their
  rationale or consequences.
- **Attempts** keeps only attempts with diagnostic value: what was tried, what
  was observed, and what the observation confirmed or ruled out.
- **Outcome** states the implemented or observed result and its validation
  state. Name stable artifacts when they matter.
- **Remaining Work** gives the exact next step or blocker. Use `None in scope`
  when no authorized work remains.

Never infer unsupported facts. Mention missing evidence only when it affects
the outcome, completion status, or ability to resume. Omit routine narration.
Use the smallest number of `Evidence: line N` citations needed to support
material claims. A source line proves location, not semantic support.

For one planned part, use its exact title and the five sections directly:

```markdown
# <P001 title>

- Session: <source-session-id>
- Snapshot: through line <last_source_line> · <open|closed> tail
- Part: P001
- Source range: lines <start>-<end>

## Intent

## Decisions

## Attempts

## Outcome

## Remaining Work
```

For multiple parts, add the task wrapper. Map `T001` to `P001`, `T002` to
`P002`, and so on. Use every exact part title and range once.

Assign status as follows:

- `completed`: the objective is achieved, required validation is complete, and
  no in-scope work remains;
- `blocked`: the next in-scope action requires an external condition or user
  decision;
- `partial`: the objective is unfinished and its next in-scope action can
  proceed;
- `abandoned`: the objective was explicitly cancelled or replaced.

Status and Remaining Work must agree. When `receipt.tail_open` is true, use
`open` in the Snapshot line, keep the last objective `partial`, and state that
later source records were outside this snapshot. A closed tail does not prove
that every objective is completed.

```markdown
# <long informative session title>

- Session: <source-session-id>
- Snapshot: through line <last_source_line> · <open|closed> tail

## Task Timeline

| Task | Part | Source Range | Status | Title |
|---|---|---|---|---|
| T001 | P001 | lines <start>-<end> | completed | <first exact part title> |
| T002 | P002 | lines <start>-<end> | partial | <second exact part title> |

## Tasks

### T001. <first exact part title>

#### Intent

#### Decisions

#### Attempts

#### Outcome

#### Remaining Work

### T002. <second exact part title>

...
```

Maintain one sorted index entry for the source session:

```text
- <date> / session <source-session-id> / title <title> / [fragment](codex_journal.d/<file>.md)
```

Read an existing fragment and index entry before changing them. Do not create a
second entry for the same session. Never replace a fragment with a snapshot
whose `last_source_line` is lower; one fragment advances monotonically as later
runs select larger append-only prefixes.

## Final gate

Read the fragment and index from their written paths. Finish only when the
journal root is exactly the selected source session's app-reported `cwd`, and
the session has exactly one fragment and one index entry. Require every planned
part exactly once, in order, with its exact title and source range, plus the
exact receipt tail state and last source line.

For one part, require the direct five-section shape. For multiple parts,
require every timeline status to agree with its Outcome and Remaining Work.
Preserve pre-existing journal changes.

A future agent must be able to recover:

1. each objective, scope, and constraint;
2. material decisions and their supported rationale or consequences;
3. useful attempts, observations, and learning;
4. the observable outcome, validation state, and material artifacts;
5. remaining work, blocker, or `None in scope`.

Do not finish when a material answer is missing or inferred without evidence.
