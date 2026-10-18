# Event-native deltas on the player wire (study, 2026-10-18)

## Revision 2: stateless publication (the human's rule; supersedes C1/C2 and D1/D2 below)

Status: **exploration, nothing decided.** The human: "not sure this is the correct thing to do … let's explore this direction before going full stateful; if this works it should be much cheaper". The rescans under this rule are in [event_native_deltas_2026-10-18/stateless/](event_native_deltas_2026-10-18/stateless/):

- [world.md](event_native_deltas_2026-10-18/stateless/world.md)
- [actors_items_hud.md](event_native_deltas_2026-10-18/stateless/actors_items_hud.md)
- [sensory_effects_lineage.md](event_native_deltas_2026-10-18/stateless/sensory_effects_lineage.md)
- [remembered.md](event_native_deltas_2026-10-18/stateless/remembered.md)

### The rule

Publication keeps no remembered state. An update for an agent is the change in what it perceives now against just before, plus the event's own change:

- **Perceived before and after the event:** the event's keyed change, disclosed per field (a change touching only hidden fields sends nothing).
- **Entering perception:** the current state, in full. Examples: a door opens, a room is entered (even one seen an hour ago: "the full room is delta, there is no remembered room"), a light turns on, a creature steps out of cover.
- **Leaving perception:** nothing. What the client shows for things out of sight is client policy.

Per-seat server knowledge is what is perceived now (perception already computes what enters and leaves) plus which static content ids were sent. There are no client-value copies and no last-seen stamps.

### What each family becomes

- **World.**
  - Tiles in view get keyed changes from the events: field partials, conditions by name, residues by (cell, material, contribution), light from `light_level_map`.
  - Entering cells get a mask, packed columns of current values, their conditions and residues, and a static row only for a tile uuid never sent.
  - Objects: after-values by uuid. Entering sends look (once per uuid), placement and state. A non-sensory removal is key-only.
  - Contents: full set when granted, keyed while granted.
  - Connectors: full on entry, keyed while visible.
  - Deleted:
    - `remembered.tiles/.objects/.connectors`, `apply_world_update(remembered)`;
    - `_tile_changes` and the tile diff loop;
    - `remembered_positions/order`, `observed_values`, `_observed_plain_or_object`;
    - the remembered merges in `_observed_object`;
    - the removal, contents-clearing and connector-gate rules judged against memory.
- **Bodies and items.**
  - Per seat only: composed perception, control, and the ids whose birth fields or static item look were sent.
  - Scalars carry the event's value. `layers`, `conditions` and `controlled_items` become keyed changes. Entering view sends all changeable fields.
  - Deleted: the body diff, `item_patch`, `_holdings/_gear_observation`, the whole-holdings `EquipmentFact`, the known-removal machinery, the permanent `known` set, and per-observer re-acquisition.
  - One change record per event case, built inside `advance_capture` and shared by every seat.
- **Sensory, effects, lineage.**
  - The perception record is already native before/after.
  - Light rows and sightings become *added (full) / patched (changed fields only)* from the before/after the native code already holds. A walking torch-bearer's patch is its position.
  - Deleted: `spatial_values`, the sighting filter, the per-seat spatial revisions, content value checks, equality scans.
  - Restatements fixed:
    - the envelope (`audience`, generation, observer) once, with the audience at initialization (4.8 / 9.4 / 33.2 / 9.4 KB);
    - the spell declaration root-only, and `SpellFact.application` deleted (restated by the resolution row);
    - `cause_occurrence` deleted (always equals `parent_event`);
    - in-group `parent_lineage` and `PlayerNode.lineage` dropped;
    - REMOVED state sends `removed_positions` only;
    - admission contacts not duplicated (5.7 KB each in Sleet and Darkness).

### Where memory lives (the separate "remembered" question)

- **Engine rules** need only *which*, never *what*:
  - the explored bitmask `Senses.seen` (routes may cross visible or once-seen cells);
  - discovered trap/effect ids (a real D&D rule: known traps feed hazard flags and safe paths);
  - turn-scoped collision cells.
  
  No rule uses remembered values or last-known creature positions.
- **Found leak:** inside remembered cells, pathfinding reads the *current objective terrain* (`test_restored_paths_use_current_terrain_in_remembered_cells` asserts it). The options:
  - keep the leak;
  - visible-only planning;
  - engine-side remembered terrain values: the one place the engine would hold "what" memory.
- **Server AI:** builds its own memory by folding the native stream (`knowledge_system.py:37-39`). It never reads publication, so moving publication memory to the client costs it nothing today.
  - It keeps a full objective copy per assignment and never forgets (memory work: next refactor).
  - Only `basic.py:858-897` (advance toward last-known hostiles) and the tactical focus read its memory.
  - A future AI connected as a client would need a few fields `PlayerActor` lacks: creature type, damage affinities, healing blocked.
- **Client:** it already remembers by never deleting. To own memory fully it adds:
  1. `seen |= visible` (so `seen_cells_added` can leave the wire);
  2. forget an object when its cell is seen without it;
  3. the wall-face merge;
  4. effect footprint memory, retired when seen empty.

### Reconnect

- **Short drop, client memory intact:** the client sends its last applied sequence number; the server replays the seat's spool after it. Exact, and it exists.
- **Fresh client:**
  - (a) a snapshot of current perception only (exact for now; the explored map is lost);
  - (b) journal replay from 0 (exact memory; the spool exists today);
  - (c) the client persists its own memory, plus (a) or the short-drop replay.
- **An AI running as a client** follows the same cases.

### Native changes

- Residues get a keyed-change field (≈30–50 lines).
- Terrain writers record `walking_cost` changes (≈10–20 lines). `default_light` needs nothing: live edits already go through world_authoring.
- Per-event actor change records: which fields of a condition or its stats changed, an item's previous slot and holder, and the fields changed inside whole-item snapshots.
- A settlement marker on `SensoryUpdateEvent`, for a composed seat view.
- The composed view's entered and left masks, exposed from `_fold_view_cells` (today the member mask is used, which is wrong for multi-observer seats).

### Bugs that become visible without the diff (fix regardless)

- The client and engine folds disagree on temporary HP in a condition's `resulting_stats` and on INTERNAL conditions. Without the diff, an actor kept in view drifts permanently. The fix is to build the change record from the engine fold's own case.
- Non-controllers keep a ghost layer for a destroyed equipped item; only the controller gets the charge fact (projection.py:808-811).
- Connectors are read from init only (projection.py:1224).
- The startup fold lacks LIGHT_CHANGED/TILES_CHANGED, so initial light can be stale.

### Bytes (estimates, not measured)

- World part: Fireball ≈119 → ≈30 KB; Sleet ≈25 → ≈8 KB; SG walk ≈38.5 → ≈15–30 KB; Darkness/Daylight ≈2 → ≈2–4 KB.
- The new worst case is re-opening a room already seen (≈0 today → ≈12–23 KB), mostly wall placements.
- Bodies entering view: ≈250 B for a viewer, ≈1.2 KB for the controller; a condition ≈400–900 B.
- A room re-entry gallery case is needed to measure.

### Decisions for the human (revision 2)

1. **Multi-observer seats: what "the agent" in the rule means.** In every option the server already holds the composed view, because all disclosure reads it.
   - (A) per member, the client composes: two compositions, revisions on the wire leak unseen counts, divergence stays;
   - (B) the seat's composed view, one fact per settlement: the fact part shrinks by up to 1 − 1/N (N = 4 amber, 26 blue); the client loses per-character views;
   - (C) composed plus one member's own view: a few KB per focus switch.
2. **Remembered-cell pathfinding:** keep the current-terrain leak, visible-only, or engine-side remembered terrain.
3. **HUD:** eleven sheet field groups change with no event (action and movement counters, spell slots, resources, handler toggles, initiative, …; `reset_all_costs` runs every op out of combat). Whole sheets are too big (91 KB for blue). The options:
   - H1: an event per economy change;
   - H2: one engine writer publishing only what changed since the actor's own last publication (≈6 call sites plus toggle and join/leave events);
   - a declared exception.
4. **Smaller ones:**
   - tell a caster when its condition on an unseen target ends, or keep "leaving: nothing";
   - send body birth fields and an instance's fixed parts (tile static row, object look) once per seat, or with every entry;
   - packed columns for entering tiles (≈15 B per cell) or whole rows (≈400 B);
   - keep the objective resolved light on the wire;
   - connector names in the log;
   - initiative.
5. **Reconnect** for a fresh client: (a), (b) or (c).
6. **Numbering:** keep the per-seat occurrence numbering (remembered knowledge) rather than native ids, which would leak how many undisclosed events happened. Integrator's recommendation: keep it.
7. **Composition cursors:** the composition's contact and effect cursors are last-seen stamps used to merge hidden effect cells. Under (B)/(C) they stay server knowledge.

### Human answers (2026-10-18), recorded with the integrator's reading (to confirm)

1. **Multi-observer seats.**
   - The wire sends the seat's composed view; every perceived thing keeps its attribution to the seat members who perceive it ("which characters does what is always important").
   - The capacity gate is the worst case, one character per seat, where composed and per-character coincide. Byte and time gates are measured on a "one seat per character" gallery variant, not on the composed 26-observer seat.
2. **The caster case.** A caster learns that its concentration ended from its own `Concentrating` condition, on its own body, which it always perceives. "Leaving: nothing" stays for the unseen target. The other small decisions take defaults and are logged.
3. **Objective light.** Keep both the objective resolved light and the perceived light for cells the seat sees ("it makes sense to know it is dark but you see due to darkvision").
4. **Reconnect** is exactly the same as having been connected from the start: journal replay of the seat's spool, kept for the whole game. The client's memory rules must be deterministic so replay rebuilds the same memory.
5. **Numbering.** Keep the per-seat occurrence numbering.

Still open: remembered-cell pathfinding (decision 2), the HUD (decision 3), connector names in the log.

---

## Revision 1 (first study; C1/C2 and D1/D2 superseded by revision 2)

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
