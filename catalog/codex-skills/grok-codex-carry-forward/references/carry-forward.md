# Grok contract- and test-driven development

Adapted for standalone use: the skill now owns this process and supplies the
preflight path. [Source and license notice](../NOTICE).

This skill owns the development process for Harness-X-Harness/codex. **An actual branch HEAD
is acceptable when all applicable required CI for that exact SHA succeeds.**
Stock upgrades use the [complete downstream delta](#updating-to-a-newer-stock-tag)
as their mechanical starting point, followed by adaptation and verification.

## Authorities and boundary

| Authority | What it owns |
| --- | --- |
| Trusted upstream stock tag/commit | Pinned starting source, stock architecture, existing behavior, native tests and generators. Trust in stock is a premise, not downstream proof after modification. |
| Current product Stories on the version branch | Consumer-visible positive/negative behavior and deliberate support or retirement decisions. |
| Rust/Go source and its adjacent tests | Current implementation and executable safety/behavior contracts; stock regression tests remain with their native owner. |
| `grok/internal/scenarios/catalog.go` on the version branch | Names, selection and invocation budgets of Go-owned Live/Facts scenarios; workflows do not maintain a second catalog. |
| `grok/TESTING.md` on the version branch | Actual local/test-tier commands and interpretation of evidence. |
| Git commit and GitHub Actions | Tested source identity, applicable checks, run/attempt outcomes and artifacts. |
| This skill | Development and review process, not product code, experiments or evidence. |

A new `grok/rust-vX.Y.Z` line can be created at the **exact pinned stock
commit** by an authorized operation; read back the ref and inspect protections
actually configured. The previous formal Grok HEAD supplies the complete
downstream delta and the retained behavior contracts for an upgrade. Work
may proceed on ordinary feature branches and through PRs to the appropriate
product branch; no particular working-branch name is inherently authoritative.
Do not reset, force-push, bypass protections, or rewrite a protected line
without separate authorization.

## The ordinary development path

1. **Define the behavior change.** Use an existing Story or
   concrete bug/Issue. State the observable success and failure, safety
   boundaries, and non-goals. For a pure refactor, preserve the current
   contract rather than inventing a new one. A support-policy change needs an
   explicit reviewed product decision.
2. **Find its current owner and real dependencies.** Examine the relevant
   stock seam, callers, config, protocol/schema, history, tools, generated
   representations, and actual consumers. Trusting untouched stock does not
   excuse regressions caused by our delta. Read history only when a current
   invariant cannot otherwise be established.
3. **Make the contract executable at the lowest useful layer.** For new or
   broken behavior, add a focused failing regression/positive test before
   implementing when practical; for cleanup, verify existing positive and
   material negative oracles before removing anything. Keep Rust internal
   correctness in Rust, Go observation in Go, real-Codex composition in
   Integration, and real backend behavior in explicitly authorized Live/Facts.
   A mock, skip, or expected-unsupported diagnostic is never a positive
   product Story.
4. **Implement the smallest complete change.** Update the owning source,
   affected consumers, config, schemas/generators, build inputs, documentation
   and tests together. Delete replaced behavior and its dead paths at their
   actual owner. Split work only at an
   independently useful, tested **technical** dependency; otherwise one
   coherent PR is preferable.
5. **Verify locally, then on the actual HEAD.** Run the affected tests,
   validations and checks, broadening for shared or uncertain impact. Keep
   fail-closed tests for authorization, identity, external effects, history,
   resource bounds and confidentiality. Before accepting a code change,
   obtain settled, nonempty, applicable required CI on its actual source HEAD.
   A PR synthetic merge SHA is a different subject and must not be relabeled
   as feature-HEAD proof.
6. **Review and merge normally.** Inspect changes and evidence using
   [review.md](./review.md); follow the repository's real branch protection
   and ordinary Git operations. A squash/rebase changes the commit identity,
   so its resulting HEAD is evaluated by the applicable CI for that SHA.

A successful test proves only its own assertion, source, executable and
environment. Genuine scope gaps remain explicitly `NOT_RUN`/unproven until
the correct layer has actually observed them. Do not infer facts from
historical green runs, completed setup, or workflow YAML.

## Tests selected by changed behavior

| Boundary | Responsible checks | What a pass does not establish |
| --- | --- | --- |
| Go observer and deterministic contracts | `go -C grok test ./...`; affected `-race`, vet, formatting, fixture and result-checker controls | Rust composition or real Grok backend |
| Rust Provider, tool, history, App Server, stock seam | Affected native Rust tests, lint and owned protocol/schema/generator/stock regressions | Real Codex/Go consumer or paid provider outcome |
| Real Codex + controlled Grok HTTP | `go -C grok test -tags=integration ./tests/integration` with an explicit built executable | Actual xAI responses, unrelated product Stories or packaged target execution |
| Real Grok product | Authorized `-tags=live ./tests/live`, appropriate selected scenario and exact binary/artifact provenance | Unselected scenarios, other platforms, all stock contracts |
| Direct backend facts | Authorized `-tags=facts ./tests/facts` | Codex product behavior or acceptance |
| Packages and distribution | Native target builds, packaging tests and appropriate actual package consumers/smoke | Other platform execution or unrun Live |

These paths describe ownership, not an obligation to run every tier on every
change. Use the target branch's `TESTING.md` and workflows for supported
flags, authentication, subject verification and exact commands. The CI
applicability mechanism is orchestration only: it must not mask a required
native test, silently choose an empty suite, or grant credentials to
untrusted PRs. If a broad shared seam changes, broader Rust/Go/Integration
and affected stock proof is appropriate. Remove redundant tests only when
the preserved invariant has equal or stronger coverage.

## Updating to a newer stock tag

Pin and verify three full commit SHAs: the old upstream stock baseline
(`OLD_STOCK`), the previous formal Grok HEAD (`OLD_GROK`), and the requested
new upstream stock (`NEW_STOCK`). Exclude unmerged diagnostic branches and
uncommitted experiments. Confirm that the old stock baseline is an ancestor
of the old Grok HEAD; if not, stop and resolve the baseline rather than
silently substituting a merge base.

Carry the **complete net difference** from old stock to formal old Grok as
one temporary commit. Its only parent is `OLD_STOCK` and its tree is exactly
`OLD_GROK`'s tree. This includes source, tests, configuration, generated files,
build/CI inputs and documentation, including deletions. Do not select only
individual Stories or replay the old commit sequence.

For example, after resolving the three variables to verified full SHAs, run
in a clean, isolated worktree. Stop on any failed command:

```sh
set -eu
git merge-base --is-ancestor "$OLD_STOCK" "$OLD_GROK"
carry=$(git commit-tree "$(git rev-parse "$OLD_GROK^{tree}")" \
  -p "$OLD_STOCK" -m "Temporary complete downstream delta")
test "$(git show -s --format=%P "$carry")" = "$OLD_STOCK"
test "$(git rev-parse "$carry^{tree}")" = \
  "$(git rev-parse "$OLD_GROK^{tree}")"
# WORK_BRANCH is a new development branch name chosen for this upgrade.
git switch -c "$WORK_BRANCH" "$NEW_STOCK"
git cherry-pick "$carry"
```

The parent/tree checks verify this one mechanical transfer, not product
correctness. Apply the entire temporary commit on the new stock working
branch. Preserve conflicts and resolve them at their actual owners; do not
use blanket `ours`/`theirs` strategies or copy/restore the old tree over new
stock. The result must retain new stock changes as well as the adapted Grok
delta; its tree is not expected to equal the old Grok tree.

The temporary commit is a transfer vehicle, not a requirement on final PR
or merge history. After this mechanical starting point, use current Stories,
regression tests and stock owners to make the smallest complete adaptations.
Where stock now owns behavior, prefer stock and retire redundant Grok code.
Keep affected consumers, generators and tests with their owning changes.
Resolve incompatibilities through scoped tests and coherent PRs, split only
for real technical dependencies or independently testable outcomes. Update a
Story only when consumer behavior or supported scope intentionally changes.
Verify the actual resulting HEAD under the ordinary development and test
rules above; successful cherry-pick or tree checks do not establish acceptance.

### Inspect the candidate before acceptance

Inventory the **committed product candidate**, not the skill repository or
uncommitted changes. Set `SKILL_DIR` to the absolute directory containing
this loaded skill's `SKILL.md`, and `PRODUCT_REPO` to the separate local
product clone. Resolve all four pins to full verified commit SHAs.

```sh
python3 "$SKILL_DIR/scripts/carry_forward_preflight.py" "$PRODUCT_REPO" \
  "$OLD_STOCK" "$OLD_GROK" "$NEW_STOCK" "$CANDIDATE"
```

Use Git with `--no-lazy-fetch`, full commit SHAs, and a local clone with the
objects and history to prove both ancestry relations. The command does not check out or modify the
product. Its JSON compares old stock → old Grok, old stock → new stock,
and new stock → candidate. Review paths touched on both sides, **including
clean applications**, as well as deleted paths and both names of renames (an unmatched
rename can appear as delete/add). For a stock workflow still different from
new stock, restore stock or explain the present Grok requirement and its
test. Do not prefilter the original delta, discard all CI changes, or treat
an empty intersection as proof: changes in another file can affect a
caller, configuration key, generator or observable behavior. A zero exit
means that the Git inventory was produced, not that the port passed.

Use these findings to choose the version branch's existing owners and tests:

1. **Compile before iterating on behavior.** Build affected production,
   unit and integration test targets together, including clean-applied
   consumers of changed stock APIs; use the version CI's locked toolchain,
   profile, features and lint settings. Regenerate affected schema/SDK/lock
   outputs with their owner and compare exact bytes, not just parsed values.
   Follow compile-only checks with nonempty native tests and the affected
   stock and Grok behaviors. If local prerequisites are missing, record what
   did not run and use the corresponding credential-free CI, not a substitute.
2. **Explain changed assertions.** Cite the current Story or owning stock
   behavior. Demonstrate the original failure and test the intended observable
   result, including material negative cases, without loosening the oracle.
   Before attributing a suspected stock defect, run the same controlled
   reproduction on the pinned pristine new stock; if not reproducible or not
   run, leave the cause unresolved. For timing failures, establish the
   relevant readiness event rather than adding a sleep or removing assertions.
3. **Record the subject and limits in the PR.** Cite the pins, candidate,
   materially retained/replaced stock differences and their evidence. Name the
   actual checkout and run/attempt separately from PR head and base. Give
   the commands or links to the executed steps, with their outcomes. Separate
   controlled fixtures, real-provider runs and individual package targets.
   Mark skipped or missing evidence `NOT_RUN`; do not start paid runs to fill
   the report. Refresh evidence for the final candidate. No new manifest, test catalog or aggregate is needed.

## Evidence, delivery and maintenance

Maintain the distinction between source SHA, binary SHA-256, PR merge
subject, run/attempt, package target and backend environment where they
affect reproducibility. Required checks must be actually selected and settled
successfully; pending, failed, cancelled, skipped, stale, neutral or empty
required checks are not green. Source/branch names, old proof records and
metadata-only claims are not tests.

Actual external Grok API calls need explicit opt-in and trusted credentials.
Facts, real-provider Live, and package smoke establish different things;
their availability is not evidence they ran. Distribution is optional and
belongs to [distribution.md](./distribution.md). Changes with external effects need correct target binding,
truthful residual-effect handling and authoritative readback; do not blindly
retry non-idempotent actions.

GitHub Issues coordinate unresolved outcomes and genuine dependencies. The
Story index and test owners define functional acceptance; Actions records
actual execution results. Preserve original failure evidence while fixing
current behavior or policy.
