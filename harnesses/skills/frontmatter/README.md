# skills-frontmatter

Primitive APIs for reading Codex skill frontmatter and discovering skill
directories.

## API

- `read_frontmatter(skill_md_or_dir)`
- `validate_frontmatter(skill_md_or_dir)`
- `skill_entry(path)`
- `scan_skill_dir(root)`
- `scan_source_roots(roots)`
- `duplicates(candidates, attr)`

`read_frontmatter` provides tolerant discovery of simple top-level fields.
`validate_frontmatter` enforces the current official Codex frontmatter schema
before a source is registered or exposed. This package does not recommend,
apply, or prune skills.
