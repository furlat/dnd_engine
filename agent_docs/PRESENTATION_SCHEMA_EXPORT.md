# Passive presentation contracts

Run `python -m game.export_schema OUTPUT_DIRECTORY` to export JSON Schema
2020-12 from the production Python types. No asset loader, native entity/event
runtime, server or raster initialization is required.

`player-sequence-v2.schema.json` is the version-2 permitted player recording.
Its typed operation, application and damage-result identities are the causal
input. An explicit unknown owner remains unknown. Legacy missing ownership is
not permission to guess from an attack parent.

The remaining files describe the existing admitted authoring documents:
presentation drafts and world bindings; damage, death, healing, death-save,
life-state, equipment and movement contexts; attack and condition recipes; body
rigs and shared rig tables. These are unversioned individual records from their
own authored document, not a new transport version. Field constraints and nested
records come directly from `game/animation_types.py`, `game/condition_types.py`
and `game/world_binding_types.py`.

A client uses those timings and rigs to digest the permitted event sequence.
Export availability is not a claim that a TypeScript renderer has been ported.


## Shared runtime exports

`presentation-catalog-v1.schema.json` describes the effective `AnimationData`
catalog. `game.presentation_export.export_catalog` exports that same catalog
with package-relative filesystem paths, preserving logical resource identities.
It rejects files outside the declared package. It excludes unused archive source
JSON and original production-source/preview locations. No textures are decoded
and no assets are copied. SHA-256 of canonical export bytes identifies the
effective authored catalog.

## Runtime and authoring

The narrative feature was removed at the user's request on October 5. There is
no narrative schema, text-replay command, second outcome formatter or
Scene/Split/Narrative toggle. The encounter uses its original observer-projected
combat log. Historical narrative exports are archival only.

Continue authoring existing rig, spell, attack, condition and world documents.
Authored motion descriptions remain catalog metadata; they do not generate
another log. Shared binding, timing evidence, retained lifetime owners and
portable catalog export remain in use by graphical playback and review traces.

Stable pygame-ce 2.5.8 was rechecked on October 5 against
https://pypi.org/project/pygame-ce/ and is already pinned in pyproject.toml/uv.lock.
Development documentation is not a dependency version recommendation.

## Timing evidence identity and validation

Dependency tables explain arithmetic at the existing binder, rather than run a
second schedule. A row identifies its owner, application where present, anchor,
actual operands and local producer index. Earlier local references are validated
for order and value; explicit measured external anchors remain external.
Cross-head retained snapshots additionally carry `admission_uuid`: reacquisition
may recreate an owner's local table, so owner UUID plus index alone is not a
global producer identity. Consumers must preserve that admission boundary.

This does not export a complete executable global graph or certify every
external anchor through such a graph. Existing family binders and functional
samplers remain authoritative. Times on nested projected rows include their
outer offset; operand times receive the same translation. The six retained
lifetime owners already use absolute presentation time.
