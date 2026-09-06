# skills-profile-toml

Primitive APIs for Codex skill-manager profile TOML.

## API

- `load_profile(path, missing_ok=True)`
- `normalize_profile(profile)`
- `render_profile(profile)`
- `validate_skill_name(name, label="name")`
- `validate_source_path(path)`
- `include_list(table)`
- `vendor_list(table)`
- `source_map(profile)`
- `profile_source_roots(profile)`
- `profile_sources(profile)`
- `repo_profiles(profile, repo=None)`
- `repo_vendors(profile, repo=None)`
- `add_source_root(profile, alias, path)`
- `add_source(profile, alias, path)`
- `remove_source(profile, alias)`
- `add_repo(profile, repo)`
- `include_skill(profile, skill, global_scope=False, repo=None)`
- `exclude_skill(profile, skill, global_scope=False, repo=None)`
- `vendor_skill(profile, skill, repo=repo)`
- `unvendor_skill(profile, skill, repo=repo)`

`validate_source_path` requires a source directory containing `SKILL.md`. Skill
identity, full frontmatter, and harness metadata policies belong to the
orchestration that consumes the profile.

This package mutates in-memory profile dictionaries and renders canonical TOML.
Writing files and applying symlinks are separate capabilities.
