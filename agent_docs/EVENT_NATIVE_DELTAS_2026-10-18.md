# Event-native deltas on the player wire (study, 2026-10-18)

Status: **study only; nothing implemented.** The decisions D1–D5 below wait on the human. Base: branch `single-pass-propagation` (integration `a6ee21389`), wire schema 15. The combat log and memory retention are out of scope (human). This note sums up four read-only code studies and one byte census, kept in [event_native_deltas_2026-10-18/](event_native_deltas_2026-10-18/):

- [world.md](event_native_deltas_2026-10-18/world.md): tiles, residues, objects, connectors, light
- [actors_items_hud.md](event_native_deltas_2026-10-18/actors_items_hud.md): bodies, items, HUD
- [sensory_effects_lineage.md](event_native_deltas_2026-10-18/sensory_effects_lineage.md): perception, spatial effects, lineage, facts
- [projector_state.md](event_native_deltas_2026-10-18/projector_state.md): the projector's per-seat state, initialization, reconnect, test oracles
- [byte_census.txt](event_native_deltas_2026-10-18/byte_census.txt): bytes by payload kind (fireball, sleet_storm, spirit_guardians_walk, darkness_daylight)

## The human's rule

A delta is the change the event made. The engine knows it at event arrival, from its own state and history, and it may already be in the event. The projector therefore needs no per-seat copy of client values to produce deltas. The only per-seat knowledge is what the seat can see or know.

## What the wire does today

- **Already event-native.** Perception deltas (cells added and removed, contacts, removals), damage, heal, temporary HP, life, faction, conditions (keyed by uuid), movement and steps, item charges, light levels (`light_level_map`) and elevation.
- **Diffed against a per-seat copy (`ProjectionState.remembered`, `spatial_values`, `observed_values`).**
  - Tiles: `_world_update` → `_tile_changes`, field by field, each changed field sent whole.
  - Objects: the whole `PlayerObject` whenever it differs.
  - Re-acquired bodies.
  - `EquipmentFact`: the whole loadout, inventory and AC.
  - Item records.
  - The HUD: whole sheets diffed at op end.
  - Spatial-effect values.
  - The value sent with a known condition's removal.
- **Sent whole although the event holds the change.**
  - Light rows: the old and new inputs sit side by side in sensory.py.
  - Spatial-effect sightings: the whole footprint and volume per change.
  - Residue lists: Fireball re-sends a tile's whole list per deposit occurrence, 50.7 KB of a 196 KB update, of which 29.4 KB are earlier sends superseded in the same update.
  - Collection fields: conditions on admission, controlled items, loadout layers, item effects.
- **Restated inside one update.**
  - `audience` and the update envelope repeat on every lineage (identical bytes).
  - Each target's `SpellFact` copies the cast's declaration (N² declared-target ids).
  - Tree edges are sent twice (`parent_lineage` and `children_lineages`).
  - `observer_position` is on every sensory fact.
  - A REMOVED `SpatialEffectStateFact` sends `positions == removed_positions`.
- **Byte shares** (census):
  - Fireball: residues 32 %, combat log 25 %, spell facts 8.5 %.
  - Sleet: sensory 61 %.
  - Spirit Guardians walk: sensory 41 %.
  - Darkness/Daylight: sensory 68 %.
  - Sensory is already a delta. Its size is each observer's own change, so on drops, moves and light changes the multi-observer question (D3) matters more than delta versus whole.

## Proposed rule (one rule, every payload kind)

1. **Per session, one objective fold**, written only from event after-values: world facts, actor and item state, per-record change revisions. Entering snapshots read it as of the occurrence, never the live engine. The engine-free `project_sequence` keeps working. `CaptureCheckpoint` is already one shared fold per session.
2. **Per seat, knowledge only:**
   - perception: the composed visible and seen masks;
   - known identities and disclosure (the monotone sets);
   - disclosed lineages and public cursors;
   - seen revisions, if D1(b).
   
   There are no client values.
3. **Every update item is exactly one of three:**
   - **The event's keyed change, disclosed for the seat**, when the seat knew the record before and after the event. It is an upsert or remove by key: residue (cell, material) and (cell, material, contribution index); condition uuid; item uuid; loadout layer; light source; effect. Cells added and removed go as packed masks. Scalars carry their new value.
   - **An entering snapshot from the session fold**, when the record enters the seat's knowledge: first sight, or back in view.
   - **A key-only removal or lapse**, otherwise.
4. **Static content once per content id per seat:** residue material name, description and max amount; an item's look; spatial-effect content (already); a tile's static row.
5. **Nothing restated within one update:**
   - the envelope once;
   - the spell declaration on the root application only;
   - tree edges once, keeping the ordered `children_lineages`;
   - shared rows once per update;
   - `observer_position` only when it changed;
   - a removal sends its key.

Native changes needed: all are small except D4(b).

- **Residues:** `deposit_residues` / `remove_residues` (dnd/residues.py ~186–286) record (cell, material, amount, contribution) on their event.
- **Terrain writers** (area_conditions.py ~1405, ~1447) record which tile field changed.
- **`default_light` changes are recorded** (gridmap.py ~5238–5290).
- **The sensory event splits** light sources and spatial effects into *added* (whole) and *patched* (changed fields; cells added and removed).
- **One `ActorChange` / `ItemChange` per event case.** `apply_actor_fact` already handles each kind case by case; each case returns the fields it writes, with keyed `conditions`, `inventory` and `layers`. It is computed once per event and shared by every seat, then disclosed per seat.
- `EquipmentFact` becomes a holdings delta, keyed on `ItemLocationStateEvent`.

Deleted:

- the projector's value copies (`remembered` world/actors/items/hud as diff bases, `ProjectionState.world` and `.actors` repeated per seat, `spatial_values`, `observed_values`);
- `_tile_changes` and the tile comparison loop;
- the body diff in `_emit_bodies`;
- `item_patch` / `_item_patches`, `_holdings` / `_gear_observation`;
- the merges with remembered values in `_observed_object` (the wall-face residue union and the suppression rows move into the client reducer or go away);
- the superseded re-sends.

Test oracle replacing the mirror ([projector_state.md](event_native_deltas_2026-10-18/projector_state.md) §3):

- at each op end, the client fold restricted to what the seat perceives equals a snapshot built from the session fold by the same functions that build first-sight records;
- folded client states equal the base recordings on a common representation;
- the spool fold equals the live fold.

The cold-composition check stays. The "client == remembered" replica check goes: it compared the same reducer against itself.

## Latent bugs found (independent of any decision)

1. **Connectors** are read from the initialization event only (projection.py ~1224). Connector changes after init never reach a seat.
2. **Client and engine folds disagree.** The client's condition fold ignores the temporary HP carried in `resulting_stats` (reduction.py ~452–463 vs actor_projection.py ~161–165), and INTERNAL conditions change a body without sending a fact (projection.py ~897). Today these reach the client only at a later re-acquisition, and never for a self-observed actor. The replica test cannot see it.
3. **Re-acquisition is counted per observer, not per seat** (capture.py ~808, ~877). A 26-observer seat re-admits a body whenever any member regains sight of it.
4. **Entered cells come from the member event** (projection.py ~1466), which is wrong for seats with several observers. The composed view's before and after exist in `_fold_view_cells` (audience.py ~396–405) but are not exposed.
5. **The server and the client compose multi-observer seats over different values.** The projector folds native duration and revision; the client folds the stripped and renumbered ones. The join depends on `owner_revision` (audience.py ~161), so the two views can diverge. This was found in the code and not reproduced.
6. `audience` is sent twice per lineage (once at the top, once per lineage).

## Decisions for the human

- **D1. Re-entry after changes the seat didn't see.**
  - (a) Resend the current state of every record entering view. Simplest, but it costs bytes on every re-entry (blood-soaked cells, re-observed walls, bodies).
  - (b) A per-record change revision in the session fold, and the seat's last-seen revision as knowledge. Only records that changed while unseen are sent. These are stamps, not values, and they keep "no body bytes for unchanged re-acquisition".
  - *Integrator's recommendation: (b).*
- **D2. Fog of war.** With no server copy, the server no longer knows the stale explored-but-unseen state the client shows. The client keeps it itself. Is that acceptable as the model?
- **D3. Multi-observer seats.**
  - (A) Keep per-member deltas, with the client composing the seat view (today).
  - (B) The server emits the composed seat view's changes: one fact per occurrence instead of N, which also removes bug 5.
  - The human said earlier: "handle the per seat scenario per observer but of course when shared we should optimize". (B) is the largest cut on sensory, which is 41–68 % of the bytes on drops, moves and light changes. It decides whether the client can still show each character's own view.
- **D4. HUD.**
  - (a) Event-native: needs new action-economy events (costs, handler toggles), a large native change.
  - (b) One previous sheet per actor, shared by every seat that controls it: still a diff, but not per seat.
  - (c) A per-sheet hash.
- **D5. Objective resolved light.** Is it still needed on the wire next to the sensory light levels?

Also open, not blocking:

- whether native cursors may appear on the wire (they would delete the per-seat numbering maps, but would leak how many undisclosed events happened);
- the client must keep any wall-face residue union it wants to show.

## Expected effect (estimates, not measured)

- **Fireball.** Residues ~51 → ~10 KB, plus the superseded re-sends; the spell declarations (~4–10 KB) and the envelope go. About 201 → ~140 KB. Under 100 KB needs the combat log as well, which is out of this study's scope.
- **Drops, moves, light changes.** The light-row and sighting patches help; D3(B) is the large lever.
- **CPU.** The deleted diffs and copies come off publication: real but modest, not measured.

Any plan built from this note needs the AGENTS.md antislop and antiOOP reviewers, and a schema bump with a Godot fold note.
