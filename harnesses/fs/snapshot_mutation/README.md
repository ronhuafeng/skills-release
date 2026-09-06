# Snapshot Mutation

API-only primitive that applies a previously reviewed managed-snapshot plan by
staging copied content beside the destination and renaming it into place.
Only a plan marked authoritative can overwrite conflicting target content.
