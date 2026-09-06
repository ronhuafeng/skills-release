---
status: superseded by 0027
---

# Separate semantic content from rollout metadata

Journal and split share `ContentSnapshot`, composed of `SelectedRollout` and
`ContentTimeline`.

`SelectedRollout` binds the caller-selected session id, Codex home,
active/archive selection, native rollout filename timestamp, exact path,
source-line boundary, and prefix digest. The selected id locates and labels the
rollout. It does not require embedded `session_meta`, Goal, parent, or delegated
thread ids to agree.

`ContentTimeline` contains only source-located user, commentary, final, and Goal
semantic content. Journal and split use it with eligible user-message anchors.
Codex supplies objective titles and anchors; shared read-only partition planning
revalidates the source and derives `P001…PN` with selected anchors and complete
physical ranges. Journal authors one source-session Markdown fragment from that
plan. Split execution consumes and rederives the exact plan before separately
adding generated identities, paths, staging, and a manifest.

Split rewrites every identity-bearing `session_meta` and Goal field in generated
rollouts and validates the generated identity as an output invariant. Input
metadata identity consistency is not a semantic-input gate.

This replaces the shared `SessionSnapshot` portion of ADR 0012. No compatibility
type, legacy JSON field, or fallback collection path remains.
