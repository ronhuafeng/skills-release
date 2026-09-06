# skills-symlink-plan

Primitive APIs for computing symlink plans.

## API

- `DesiredLink`
- `CurrentEntry`
- `LinkAction`
- `LinkPlan`
- `plan_links(scope, directory, desired, current_entries, create_dir=False)`
- `current_entries_from_directory(directory)`
- `existing_symlink_targets(directory)`
- `desired_links_from_sources(desired_names, sources, reusable_targets=None)`
- `plan_directory(scope, directory, desired_names, sources, reusable_targets=None)`
- `dedupe_actions(actions)`

`plan_links` is the pure planning API. The filesystem helper APIs only snapshot
current symlink state and validate source directories; they do not mutate files.
