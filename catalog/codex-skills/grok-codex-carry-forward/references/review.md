# Review a complete, test-backed change

Apply the [current Grok development and acceptance policy](./carry-forward.md).
Review whether the requested behavior and its affected contracts are
protected by the appropriate executable evidence.

## Subject and current contract

- Identify the repository, actual source branch HEAD, PR/base/merge subject
  if applicable, relevant Story or Issue, and exact stock input when adopting
  a new upstream version. Distinguish a tested PR merge from the feature HEAD.
- Read current source and tests at the affected owner, its direct consumers,
  and only the related Story requirements. Consult old migration notes only
  when a still-operative constraint cannot be resolved from current sources.
- State the consumer-visible positive behavior, material negative/safety
  boundaries, intentional scope changes and non-goals. A change of supported
  product behavior needs a reviewed decision, not just altered test expectations.

## Impact and smallest complete implementation

- Inspect stock/provider seams, callers, shared dependencies, configuration,
  public protocols, generated representations, history, resources, and
  external-effect ownership affected by the diff. Unchanged files may still
  be impacted; a short diff is not proof of a small behavioral footprint.
- Confirm that each necessary source/config/schema/generator/build change
  travels with its owning test and consumer. No half-implemented API or
  deferred mandatory safety proof.
- Prefer the actual owner and the smallest complete PR. Split for a
  demonstrated technical prerequisite or independently testable outcome.
- For context reduction, identify the current consumer/invariant of each
  extra layer, field, historical compatibility path and test. Remove dead
  authorities and their consumers together; keep real security, recovery,
  provenance and privacy boundaries.

## Tests and execution evidence

| Type of change | What to inspect or execute |
| --- | --- |
| Pure local behavior | Closest unit/property tests, material failure cases, ordinary Go/Rust lint and formatting |
| Shared Rust/protocol/tool/history | Affected stock regressions, native Rust, generated ABI/consistency and cross-owner tests |
| Go SDK/observer or actual product wiring | Offline Go, relevant real-binary Integration, causal ID/status/history/side-effect checks |
| Shipped configuration, helpers or package | Current catalog/profile checks, staging/launcher and actual affected target package consumers |
| Real-backend capability claim | Explicitly authorized, scoped real Codex + Grok Live, or independent backend Facts when that is the claimed fact |

Check that tests **ran**, completed and asserted the claimed behavior: a
compile-only target, empty suite, `t.Skip`, outdated snapshot, mock HTTP or
expected-unsupported result is not an actual product success. An offline
negative test should still guard security-sensitive rejected actions,
wrong identity, local redispatch, unpaired replay, stale state, resource
overflow, secret leakage, and unauthorized effects when material.

A cleanup may remove redundant tests if an identified current invariant
remains covered. Do not preserve historical test counts or exact instance
lists for their own sake. Conversely, deleting a test solely to turn CI green
does not retire the invariant.

## Actual HEAD, merge and release evidence

- Review applicable workflow/job selections for **the exact changed source
  HEAD**, its checked-out SHA and settled conclusions. Required failures,
  skips, missing owners, stale runs or cancelled/pending jobs block that
  claim. Use the actual configured branch protections; a particular branch
  name is not a test.
- Do not promote a PR synthetic merge result as source-HEAD proof.
  Squash/rebase may change SHA: inspect the applicable checks on the
  resulting source HEAD.
- Preserve source/build/package and executable digests at boundaries that
  need them. GNU/native Integration does not certify Linux-musl/macOS
  packages; one Live result cannot certify an untested target, backend or
  scenario. If paid Live/Facts were not run, say **NOT_RUN**.
- If a non-idempotent external operation can leave partial effects, check
  bounded retries, truthful cleanup/uncertainty and authoritative readback.
  An old green run is never a substitute for its changed subject.

## Reviewer output

Report material findings with the owner, violated invariant, concrete
source/test evidence, consequence, smallest fix and risk. If none, say
`none`. State exact tested SHA/run/attempt, what passed or was not executed,
and unresolved uncertainty. Leave behavior and test ownership in code,
current contracts in Stories and CI evidence in Actions.

Review does not authorize code, branch-protection, release or historical
ref mutations without the user's explicit request.
