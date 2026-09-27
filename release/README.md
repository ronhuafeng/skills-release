# Public Sync and Release

Share the current Skills and their dependencies without publishing private
development history. Private `origin/main` owns development. Public
`release/main` contains snapshots with independent Git ancestry.

[`public-files.txt`](public-files.txt) selects public content. The catalog and
its dependencies sync together, including additions, edits, and deletions.
Apply corrections to the private source, then export again.

## Export one source commit

```sh
./release/export <source-commit> </absolute/new-output-directory>
```

The command reads both the allowlist and tracked files from that exact commit.
It rejects an empty allowlist, missing paths, an existing output directory,
symbolic links, and private journals. `SOURCE_REVISION` records the source SHA;
it does not import that commit or its ancestors into public history.

## Sync public main

Run from the private repository with a clean, committed `main`. Stop if a
command fails. Use the existing public history in a detached worktree; no
local `public` branch is needed.

```sh
git switch main
test -z "$(git status --porcelain=v1)"
git push origin main
git fetch release main

source_commit=$(git rev-parse HEAD)
sync_tmp=$(mktemp -d /tmp/skills-sync.XXXXXX)
export_dir="$sync_tmp/export"
public_dir="$sync_tmp/public"

./release/export "$source_commit" "$export_dir"
git worktree add --detach "$public_dir" release/main
```

Replace tracked public files with the full export. This also removes files
that no longer belong in the public tree.

```sh
git -C "$public_dir" rm -r -- .
cp -a "$export_dir"/. "$public_dir"/
git -C "$public_dir" add -A
git -C "$public_dir" diff --cached --check
git -C "$public_dir" diff --cached --stat
git -C "$public_dir" diff --cached
```

If the staged tree is unchanged, remove the worktree and finish without a
commit. Otherwise, review the complete diff and scan the export with a dedicated
secret scanner. Confirm the bundled TLA+ checksum and retained license against
its toolchain manifest and third-party notice.

Commit the reviewed snapshot, then run the commands in
[public CI](../.github/workflows/verify.yml) from that clean candidate. Keep
generated build output outside the worktree. Run these checks once per candidate.

```sh
git -C "$public_dir" commit -m "Sync public Skills from $source_commit"
public_commit=$(git -C "$public_dir" rev-parse HEAD)
```

Before pushing, confirm the public commit descends from `release/main` and has
no common ancestor with the private source commit. Verify that its tracked tree
matches the export exactly. Push only the candidate after verification passes:

```sh
git -C "$public_dir" push release HEAD:refs/heads/main
```

Read back the remote SHA and `SOURCE_REVISION`. Require the `verify` workflow
for `public_commit` to pass, then perform the installation proof below. If a
repository defect is found, correct the private source and create a new export;
preserve published public history. A failed push must be read back before retry.

Remove the temporary worktree with `git worktree remove "$public_dir"` when
done. Keep `origin` as the default push remote. Always name the public ref
explicitly; never push private branches, all branches, or all tags to `release`.

## Versioned releases

Routine sync updates `release/main` without a tag. For a formal release, update
the source changelog and sync it first. After validation, tag the verified public
commit and create a GitHub Release:

```sh
version=v0.2.0
git tag -a "$version" "$public_commit" -m "Agent Skills $version"
git push release "refs/tags/$version"
gh release create "$version" --repo ronhuafeng/skills-release \
  --verify-tag --title "Agent Skills $version" \
  --notes "Release generated from source revision $source_commit"
```

Read back the tag target and release metadata. A tag must point to a public
commit, never the private source commit.

## Installation proof

Record the exact `skills` CLI version used. List the public repository and
compare its discovered Skills with the published catalog:

```sh
npx skills@<recorded-version> add ronhuafeng/skills-release --list
```

Install a changed Skill for Codex in an isolated directory. Confirm the copied
content matches the published Skill. Runtime discovery requires a separate
Codex discovery check; file placement alone does not prove it.

The `verify` Action validates pushes and pull requests. Sync remains a manual
maintainer operation using this procedure and `release/export`.
