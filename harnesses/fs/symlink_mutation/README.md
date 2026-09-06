# skills-symlink-mutation

Primitive APIs for applying validated symlink plans.

## API

- `apply_plan(plan)`

The function refuses unresolved or conflicting plans. Ordinary plans can
remove or retarget only symlinks. Only an authoritative plan can overwrite or
remove a real registry entry. It does not compute desired state.
