# Runtime evidence and optional distribution

[Development and acceptance policy](./carry-forward.md) governs source
changes. This document owns only the **distinct backend, execution-subject,
artifact and delivery** boundaries. Publishing a document, building a binary
or enabling a workflow does not establish a supported user-visible result.

## What each result means

| Evidence | Establishes | Does not establish |
| --- | --- | --- |
| Trusted exact stock | Agreed upstream source input | Downstream correctness after modification |
| Rust/Go native and controlled Integration | The executed assertions on the identified source/binary | Real Grok backend or all product Stories |
| Direct Grok Facts | Actual backend response for a specific request/environment | Codex product policy or same-thread behavior |
| Product Live | Identified Codex binary + actual backend behavior for selected Story/scenario | Other scenarios, platforms or upstream stock tests |
| Package build/consumer smoke | Layout, helpers, launch and actual selected target behavior | Live/backend behavior, other targets or separate source acceptance |

Backend Facts and Live must be explicitly opted into with trusted credentials
where needed. A skipped, empty or stale run is **not** a pass. Errors,
redacted metadata and time-bound observations must be scoped to actual
run/attempt, source SHA, executable SHA-256 and environment where those affect
reproducibility. Never leak credentials, plaintext reasoning, model output or
private paths to untrusted PRs.

## Execution and CI boundaries

The product version branch owns the real `grok.yml`, reusable native
`grok-proof.yml`, Go test packages, packaging and optional Live/Facts
workflows. Their supported events, required selectors and trust boundaries
must be verified against **that branch's** current workflow; neither this
document nor workflow YAML alone proves a job was invoked or passed.

- The ordinary applicable Go/Rust/native/Integration checks support
  development decisions on the actual changed HEAD.
- Backend-only `grok-facts.yml` remains independent of Codex binary and
  package availability. Real backend observation is not necessarily a
  required paid run for an unrelated code change.
- `grok-live.yml` is an explicitly authorized diagnostic using an identified
  binary/artifact and a separately identified harness run; do not silently
  choose the latest successful producer. A diagnostic does not certify
  omitted product scenarios.
- Formal enabled Live may use a same-run verified package, with a distinct
  actual source/build/run identity. If the build failed, its dependent Live
  is not proved. Skips and ineligible or missing credentials never become
  positive evidence.
- Changes to package/live/facts orchestration must have their own focused
  deterministic tests, without reimplementing Rust/Go Story oracles in
  shell and without maintaining a separate test-name registry.

The current version branch's `grok/TESTING.md` owns exact local commands,
opt-ins, evidence formats and selection flags. The Go scenario catalog
owns formal/Smoke/diagnostic selection; workflows consume that catalog.

## Complete package and honest delivery

An optional human-use package includes the actual runtime, necessary helper
binaries and resources, launcher/install assets, and the shipped
Provider profile/catalog. Verify source revision, supported target, selected
runtime digest, manifest and installed executable behavior; use actual
package-consumer tests, not a Go harness alone. A native Linux GNU run does
not prove Linux-musl or macOS package behavior.

Keep the user's dedicated product Home isolated; do not overwrite unrelated
configuration or silently migrate existing state. A package can be
unavailable or expired without changing the result of tests already
performed on its source. Conversely, a successful artifact build does not
authorize a claim of real backend success, publication or release.

Support target-specific builds when users need them, and reuse the same-run
artifact for dependent trusted Live when configured. Preserve original build
failures and check residual effects before retrying non-idempotent operations.
Publication is a separately
authorized operation using the existing release workflow and its actual
security and permissions.

## Triage and report

State what was actually observed: source/test/binary/package identity,
workflow and attempt, required job conclusions, backend scope, and missing
evidence. Classify an actual failure at its source (native code, harness,
provider/backend, environment or package) rather than inferring ownership
from which runner happened to fail. Preserve the original failure record;
a later passing SHA does not change it. Correct a test only when the
product contract or a valid test oracle has changed, not to manufacture
a green run.
