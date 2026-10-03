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
