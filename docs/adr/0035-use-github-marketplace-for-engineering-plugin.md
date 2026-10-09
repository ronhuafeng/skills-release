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

The committed root Codex manifest owns shared Plugin identity and version. The
tracked canonical engineering tree owns discovered Skill inventory and every
bundled resource. One scoped source validator serves marketplace contracts,
optional packaging, activation fixture validation and release reporting, requiring
semantic shared identity parity with the distinct Claude manifest and safe,
committed inputs. Native clients still own installation and refresh behavior.

ZIP configuration owns only package-specific presentation, keywords and assets;
it must not restate identity, inventory or parity rules. This removes the
marketplace's dependency on optional release metadata and prevents a new Skill
from requiring a shadow-list update. Deterministic portable artifacts, provenance,
archive limits and publication evidence remain governed by ADR 0034.

A rolling `main` marketplace source and an installed immutable cache are distinct.
Client evidence is bound to the resolved installed commit and client version;
a marketplace refresh or evidence for an older revision cannot establish
candidate activation. Claude structural/parity checks do not establish Claude
runtime support. Refactor acceptance is tracked by #19.
