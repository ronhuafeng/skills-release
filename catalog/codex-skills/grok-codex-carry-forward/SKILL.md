---
name: grok-codex-carry-forward
description: Manually guide Harness-X-Harness/codex Grok stock upgrades, product development, review, and release-evidence checks. Use only when explicitly invoked for this fork.
---

# Grok Codex carry-forward

Standalone adaptation of the former Grok development entrypoint. [Origin](NOTICE).

Use this skill only on explicit invocation and only for [Harness-X-Harness/codex](https://github.com/Harness-X-Harness/codex).
Start in the selected product checkout/ref, not the skills repository. Identify
the requested operation, target repo and actual source HEAD before acting.
The skill owns the process; the version branch owns the product Stories
(`grok/docs/stories/README.md`), test commands (`grok/TESTING.md`), source
and workflows. Use their current versions rather than recreating a catalog.

- **Stock upgrade or ordinary development:** use the [development policy](references/carry-forward.md).
  For upgrades, start with [updating stock](references/carry-forward.md#updating-to-a-newer-stock-tag);
  the [bundled preflight](scripts/carry_forward_preflight.py) inventories committed Git objects,
  not product behavior. It needs Python 3, Git with `--no-lazy-fetch`, and the target history.
- **Review:** apply the development policy and [review guide](references/review.md);
  distinguish exact source HEAD, synthetic merge checks, and untested claims.
- **Backend evidence, packaging or distribution:** apply the development policy and
  [distribution guide](references/distribution.md). Never treat a build as proof of
  real-backend execution, or permission to publish.

An invocation selects this procedure, not write permission. A read or review
does not authorize changes. Branch creation, PR, merge, release, real-provider
runs and other external effects remain subject to the user's requested scope,
repository protections and actual credentials. Never infer authority to reset,
force-push, change protections or delete refs. Verify authorized writes by readback.

## Improve the skill from use

When a run exposes friction, establish the failure, its owner, and why a fix
would help another run. For example, when a runner cannot supply a pinned
toolchain, check the pin against the publisher's supported platforms before
changing the pin or tests. A runner label belongs in its workflow, not here.

If there is a small, reusable correction, update the one owning instruction,
reference or helper; exercise it on a representative case. For an authorized
skill-improvement task, commit and push the verified change to its designated
open development PR and read back the head. If the target or write authority
is missing, report the proposed fix and evidence instead. Do not turn a
one-off workaround into policy, open a parallel PR, or infer permission to
merge, publish or modify a product from using this skill.
