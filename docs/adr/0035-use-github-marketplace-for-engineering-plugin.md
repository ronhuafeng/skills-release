---
status: accepted
---

# Use the public GitHub marketplace for engineering Plugin delivery

The public `ronhuafeng/skills-release` repository is the default and only
active engineering Plugin distribution source. Its committed
`.agents/plugins/marketplace.json` points to the Git repository root, where
`.codex-plugin/plugin.json` exposes the canonical `catalog/engineering/`
Skills. A consumer adds the GitHub marketplace; no generated `dist/` tree,
ZIP, or maintainer packaging step is required to discover the Plugin.

This amends ADR 0034's package-first distribution default. ADR 0034 still
governs the deterministic portable builder, provenance, and six publication
states when an operator explicitly undertakes a ZIP release. Marketplace
availability, client installation, and live activation are separate evidence
from those states. Neither marketplace registration nor a green structural CI
job proves activation, package verification, directory approval, or public
publication. `npx skills` remains a standalone Skills compatibility path, not
an engineering Plugin distribution channel.

Keep the CI owners distinct: distribution checks the clean committed GitHub
source; activation reports missing live evidence as unavailable; the release
ladder checks the optional ZIP builder and publication-state rules. A supported
client must establish actual installation and Skill selection separately.

This decision corrects the future distribution default without reopening
completed package work in #6–#9. The read-only release audit in #14 is separate.
