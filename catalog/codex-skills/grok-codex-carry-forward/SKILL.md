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
