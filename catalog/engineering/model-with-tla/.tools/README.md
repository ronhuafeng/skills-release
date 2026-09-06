# Bundled TLA+ Tools

This directory owns the bundled `tla2tools.jar`, its exact
[`toolchain.json`](toolchain.json) identity and provenance, the retained
[`LICENSE.tlaplus.txt`](LICENSE.tlaplus.txt), and the canonical `tla-check`
entrypoint. The unmodified JAR also retains its packaged dependency licenses
and notices.

TLA+ Tools are distributed under the upstream MIT license. This directory
retains the license copy distributed with the JAR; the upstream license remains
available at <https://github.com/tlaplus/tlaplus/blob/master/LICENSE>.

The original URL used to obtain this pre-release build was not retained. The
SHA-256 digest and embedded revision and build timestamp are its exact identity.
The current rolling build and `v1.8.0` release asset have different bytes and
are not claimed as reproducible sources for this JAR.

The pinned pre-release contains the upstream correction for the critical
`FcnLambdaValue`/`EXCEPT` soundness and completeness defect #1302. There is no
system, Maven, Toolbox, nightly, or older-version fallback.

A maintainer upgrade replaces the JAR and manifest together, verifies the
embedded upstream revision, then runs the orchestration integration suite and
one live reproducer. Ordinary Skill execution never downloads a replacement.
