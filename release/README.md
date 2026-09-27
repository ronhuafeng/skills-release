# Release

Develop and review changes in the public repository. Merging to `main` makes
the current Skills available through the install command in the root README.
There is no export, mirror, or private-source synchronization step.

For a versioned release:

1. Update `CHANGELOG.md` with user-visible changes and merge the change.
2. Require `verify` to pass for the exact public commit being released.
3. List and install from the public URL with a recorded Skills CLI version.
   For runtime changes, verify the installed executable outside the checkout.
4. Tag that public commit and publish the GitHub Release:

```sh
git tag -a <version> <verified-commit> -m "Agent Skills <version>"
git push origin refs/tags/<version>
gh release create <version> --repo ronhuafeng/skills-release \
  --verify-tag --title "Agent Skills <version>" --notes-file <release-notes>
```

Read back the remote tag target and release metadata. Keep published tags
immutable; correct a release with a new version. Publication does not install
Skills or runtimes on any user's machine.
