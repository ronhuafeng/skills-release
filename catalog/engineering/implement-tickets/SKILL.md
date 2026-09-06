---
name: implement-tickets
description: Process an ordered list of confirmed tickets one at a time through implementation and repository-defined remote integration. Use when the user asks Codex to complete a ticket queue, issue set, milestone slice, or ordered backlog in a temporary or persistent repository environment.
---

# Implement Tickets

Coordinate confirmed tickets through `$implement` and the repository's remote
workflow. The ticket body owns the accepted scope. `$implement` owns the
implementation, tests, review, and implementation commit.

For a new or changed Live Story or outcome-driving Live assertion, the ticket
body does not create product authority by itself. Require, in order, an
accepted `live-story-review` result, Story and ticket reconciliation, and an
accepted `live-gate-review` of the proposed assertion matrix or current gate
before implementation. Require a second review of the exact executable gate
before remote validation or integration.
Stop when a prerequisite is absent, blocked, superseded, or inconsistent. An
outcome-driving acceptance or gate change invalidates downstream review and
validation evidence; a candidate change invalidates that candidate's
validation.

## Precheck

Load the explicitly named `$implement`, `$tdd`, and `$code-review` from Codex
discovery locations. Absence from the initial Skill summary is not failure. If
no valid enabled Skill can be loaded, report the observed state and ask the
user to
[install](https://github.com/mattpocock/skills/blob/main/skills/engineering/README.md),
enable, or reload the dependency as required, then stop.

## Inputs

Obtain:

- the complete pending ticket list in its explicit priority or source order;
- each ticket id, title, and body;
- the repository environment;
- the validation permission for each relevant category: locally allowed,
  remote-only, or prohibited;
- the repository-defined remote validation gates and the boundaries for remote
  publication and integration;
- for Live work, the accepted Story review, reconciled Story/Issue identities,
  proposed or current gate review, its unresolved findings, and the exact gate
  review required before remote execution;
- the maximum `$implement` rounds, which defaults to 10 per ticket.

Do not skip or reorder tickets. Report the ordered ids and titles. If the list
is empty, report `no pending ticket` and stop. Ask the user only when an input is
missing, contradictory, or cannot be derived from the provided environment.
Do not infer execution permission from tool availability.

## Process One Ticket

Record the current branch head as the fixed review base. Run `$implement` in
the current task. Use an implementation subagent only when the user explicitly
requests delegation.

Provide `$implement` with:

- the ticket body;
- the fixed review base;
- the validation permissions and repository-defined gates;
- for Live work, the exact accepted Story review identity, reconciled
  Story/Issue identity, proposed or current gate review identity, and every
  gate-review finding that the candidate must resolve;
- unresolved findings from the preceding round, if any.

Do not start the first implementation round while a prerequisite Live review
has an unresolved outcome-driving finding. When the gate design review permits
implementation with required corrections, pass those corrections as explicit
acceptance inputs and require the implementation result to account for each
one. A review for a different Story, Issue, or gate revision does not satisfy
this input.

Require this result:

- `implementation_commit`;
- `test_evidence`;
- `review_findings`;
- `blocker`, if the ticket cannot continue.

`test_evidence` identifies each relevant validation as run, remote-required, or
unavailable. It maps each ticket acceptance criterion and affected component or
deliverable to the test or repository-defined gate that verifies it. Do not
copy test procedures or repository commands into this Skill.

An `$implement` attempt consumes one round only when the three required result
fields are present and `implementation_commit` exists. A capacity pause or
read-only audit without a commit remains in the same round. Resume that round
unless an external or permission condition makes continuation impossible and
requires a blocker.

The review findings must apply to the exact `implementation_commit` returned
for that round. Any ticket-owned change after the review invalidates the result.
Produce a new commit, test evidence, and review before publication.

If findings remain, run `$implement` again for the same ticket. Do not create
another ticket, expand the scope, or advance in the queue. If the configured
round limit is reached with findings, mark the ticket `unresolved` and stop.

When no findings remain, require the implementation commit to be `HEAD` and
require no ticket-owned uncommitted changes. For Live work, obtain an accepted
review of the exact executable gate at that commit before remote execution.
Then:

1. Publish that commit to the remote work branch and read it back.
   Treat a publication-transport failure as a blocker.
2. Run the repository-defined remote validation against that exact published
   commit. Record the validation result separately from failure attribution.
   If the candidate changes, discard validation evidence for the previous
   commit. Return a repository-owned failure that can be corrected within the
   ticket scope as findings for the same ticket's next `$implement` round.
   Treat an `external_environment` failure or missing execution permission as
   a blocker. If the evidence is `inconclusive`, use allowed read-only
   inspection to resolve it; otherwise stop without product changes,
   integration, or an automatic validation rerun.
3. Only after remote validation passes, complete the integration workflow and
   verify that the target branch contains the final commit.

Only then mark the ticket `completed` and advance. A blocker means an external,
permission, or unresolved evidence condition prevents safe continuation. A
repository-owned defect that can be corrected within the ticket scope is a
finding, not a blocker.

## Output

When the queue completes or stops, report each processed ticket as:

| Field | Meaning |
|---|---|
| `ticket` | Ticket id and title |
| `status` | `completed`, `blocked`, or `unresolved` |
| `implementation_commit` | Commit produced by `$implement` |
| `test_evidence` | Test result returned by `$implement` |
| `review_findings` | Remaining findings, or `none` |
| `remote_publication` | Work-branch publication readback |
| `remote_validation` | Exact candidate, result, and `repository`, `external_environment`, or `inconclusive` attribution when failed |
| `integration` | Target-branch integration readback |
| `blocker` | External, permission, or unresolved evidence stop reason, or `none` |
