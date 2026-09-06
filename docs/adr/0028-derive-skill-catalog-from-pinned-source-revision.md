---
status: accepted
---

# Derive the Skill catalog from the pinned source revision

The Fleet Manifest stores one canonical Git origin and one full accepted
revision for each source. The catalog inspection primitive derives every Skill
name, relative path, and Git tree object ID from that exact revision. The
manifest does not persist a second catalog table.

This makes the pinned revision the single source-catalog authority. A path move
with the same Skill name is a catalog move. A new name enters the catalog but
does not enter any placement. A removed name leaves every managed placement by
default. The Agent preserves those placements under a candidate name only when
contract evidence and user intent support a semantic replacement. Name
similarity alone does not prove a rename.

The Agent compares the complete old and candidate catalogs before mutation and
shows additions, removals, moves, content changes, replacements, and affected
placements. Guarded link and snapshot plans revalidate the exact source and
target state for each filesystem mutation. Git tree object IDs remain exact
runtime evidence for source and placement checks, but they are not durable
duplicate configuration or workflow state.

Schema 3 replaced the source alias tables from schema 2. There is no schema-2
reader, fallback catalog, or dual authority.
