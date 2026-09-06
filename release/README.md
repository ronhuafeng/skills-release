# Public Release Contract

The private `origin` repository owns development. The public `release`
repository contains only independently versioned exports from
[`public-files.txt`](public-files.txt). The two repositories never share Git
ancestry.

## Export

Commit the source change, then export that exact commit into a new directory:

```sh
./release/export <source-commit> </absolute/new-output-directory>
```

The command reads only tracked content from the named commit. It rejects a
missing allowlisted path, an existing output directory, symbolic links, and
private journal material. It writes the exact source commit to
`SOURCE_REVISION`.

## Publish

Before every public push:

1. Run a dedicated secret scanner against the exported tree.
2. Run public CI from a clean checkout of the exported tree.
3. Confirm the TLA+ artifact checksum, embedded identity, and third-party
   notices. Do not substitute the current upstream artifact without a toolchain
   upgrade and its required verification.

For the first release, create the public repository with a new root commit. Do
not connect it to any private commit, branch, or tag. For later releases,
replace the public worktree with one new export, review the complete diff
against the previous public tag, and create one public commit. Tag the verified
commit with `vMAJOR.MINOR.PATCH`, push only that public branch and tag, then
read back the GitHub tree and release metadata.

## Installation proof

After public readback, record the exact `skills` CLI version used for the
release proof. Use that version to list the public repository and compare the
result with the Skill names derived from the published `catalog/`:

```sh
npx skills@<recorded-version> add ronhuafeng/skills-release --list
```

Then install one selected Skill globally for Codex, confirm its placement under
`~/.agents/skills`, and confirm that a new Codex task discovers it. Remove the
placement only when the proof created it. A local-path installation does not
replace this public GitHub proof.

Configure the `release` remote only after its public URL exists. Keep `origin`
as the default push remote. Never use `git push --all`, `git push --mirror`, or
a wildcard refspec with `release`.
