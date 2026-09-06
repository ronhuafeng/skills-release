# skills-openai-metadata

Primitive APIs for inspecting and validating optional Codex skill
`agents/openai.yaml` metadata.

## API

- `inspect_openai_metadata(skill_dir)`
- `validate_openai_metadata(skill_dir)`

Inspection reports file presence, effective `allow_implicit_invocation`, and
validation errors. The default policy is `true` when the file or policy field
is absent. Validation requires YAML mappings for the document and `policy`,
and a boolean `policy.allow_implicit_invocation` when specified.
