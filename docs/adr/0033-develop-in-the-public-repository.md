---
status: accepted
---

# Develop in the public repository

The public repository owns future development and accepts contributions
directly. It starts from the existing public snapshot, without importing private
Git ancestry. This removes the export allowlist, synchronization process, and
second source authority; private session and deployment data stay outside the
project. Skills with executable dependencies use the shared public source to
build a runtime instead of copying shared libraries into every installed Skill.
