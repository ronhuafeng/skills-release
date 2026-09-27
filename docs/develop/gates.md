# Verification gates

This page owns repository-wide validation routing. Exact package commands may
remain in the closest package README; they do not redefine what each gate
proves.

## Gates

| Gate | Evidence | Proves |
|------|----------|--------|
| **Structure** | `git diff --check`, changed links resolve, no generated or local-only artifact becomes Git-visible | Patch and documentation integrity |
| **Contract** | Focused tests for every changed primitive or orchestration boundary | The changed implementation invariants |
| **Integration** | Tests at the closest consumer boundary when an API or structured result changes | Callers still consume the changed contract |
| **Live** | One real user path on the affected host, app, registry, or session | The deployed/local environment actually completes the claimed outcome |

## Scope routing

| Change | Required validation |
|--------|---------------------|
| Documentation only | Structure; do not run unrelated code suites |
| Python primitive workspace | From `harnesses/`: `uv run pytest` |
| `skill-manager` orchestration | From the repository root, run the exact locked test command in the closest package README |
| Go primitive | In the changed module: `GOWORK=off go test ./... -count=1` |
| Session-management orchestration | From `catalog/codex-sessions/session-management/orchestration-go`: `GOWORK=off go test ./... -count=1`, `go vet ./...`, and build the command when executable wiring changes |
| Skill metadata or routing | The closest metadata validator plus a real Codex discovery check when invocation behavior is claimed |
| Host, registry, snapshot, session, or app mutation | Relevant Contract/Integration gates plus a scoped Live proof and post-mutation state readback |
| Runtime installation | Build with `install-runtime` into an isolated directory; run the installed executable on bounded synthetic input outside the checkout; verify the user-visible result |
| Release | Require CI for the exact public commit; list and install from the public URL with one recorded `skills` CLI version; verify the tag target and release metadata |

Use `uv run python ...` for repository Python execution. A one-off command that
needs a missing dependency uses a temporary uv dependency environment; it does
not add a project dependency or become a reusable helper by accident.

## Evidence boundaries

- Passing unit tests does not prove Codex/Grok discovery, app visibility, SSH
  environment behavior, or a host mutation.
- A successful command exit does not prove convergence; inspect the owning
  state or re-plan to no pending actions.
- A smoke check does not prove the complete user journey.
- One live observation proves only its recorded host, version, inputs, and
  time. Promote it to a broader contract only with stronger evidence.
- Do not add low-value tests for document wording or duplicated internal data.
  Mechanize only stable invariants whose regression would be costly or unsafe.
