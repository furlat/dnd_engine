# Remembered state: every reader, in three layers (read-only inventory)

Tree: `/home/tommaso/.codex/worktrees/event-native-deltas/dnd_engine`, branch `event-native-deltas` at `55bf034cc`. Nothing was edited, run or measured. Citations are file:line at that commit.

"Remembered" here means: the state of a cell, creature, object or effect as last perceived, now that it is out of perception. Three kinds of knowledge are kept apart below:

- **MEMORY (values)**: last-perceived values kept after perception ends (a tile's terrain, a body, a footprint, a position).
- **MEMORY (identity / mask)**: "has ever perceived X" as a set or bitmask, with no values.
- **NOT MEMORY**: current perception, or knowledge with no perception history (authorship, a turn-scoped event fact).

---

## 0. Findings in one page

1. **The engine's rules read very little memory, and almost none of it is values.** There are three things:
   - the explored mask `Senses.seen`, used as the navigation domain;
   - the ids of spatial effects held in `Senses.spatial_effects`, used as "known trap" and "known barrier" gates;
   - a turn-scoped collision memory.

   Inside remembered cells, subjective navigation reads **current objective terrain** (a test asserts this). It ignores creatures, objects and boundaries that are not currently perceived. Targeting, the action scan and the hazard mask use current perception only. No rule reads a last-known position.
2. **The engine pushes memory onto the wire in two places**, against the human's rule:
   - `seen_cells_added`, which the client could derive as the union of its visible cells;
   - **remembered spatial-effect footprints.** `Senses.spatial_effects` keeps the last observation of hidden parts, "even when the objective owner was removed". The sensory event diffs that memory, so it is published.
3. **The server AI keeps its own memory and never reads publication.**
   - `AIKnowledge` folds the unredacted native EventQueue. It turns lost contacts into REMEMBERED entities (last position kept), out-of-view tiles into SEEN (last values kept), and lost objects into REMEMBERED. It never forgets anything.
   - Only one built-in decision reads it: `basic.py` `_progress_value`, which approaches the last known positions of hostiles. The content-pack tactical policy also uses it, for target focus.
   - The tile and object memory and `seen_cells` are produced, but no live policy reads them.
   - **Moving publication memory to the client therefore costs the server AI nothing today.** The AI's legal rows come from engine discovery, so they depend on the engine's own memory (point 1), not on publication.
4. **Publication supports client memory mostly by omission, plus a few server merges.**
   - Tiles are never removed, actors never deleted, and `last_visual_position` changes only on a visual contact. These rules already live in the client reducer.
   - The server decides when an object is forgotten (when it is seen absent).
   - The server merges remembered wall faces, construction suppressions and effect footprints into the values it sends.
   - The server uses remembered identities (names, known actors, content) for disclosure.

   Under the new rule, the client would own the merges and the forgetting. The server would keep identity knowledge only.

---

## 1. Engine rules (dnd/blocks/sensory.py, dnd/entity.py, dnd/core/gridmap.py, dnd/core/navigation.py, actions, spells, spatial)

### E1. `Senses.seen`: the explored mask (MEMORY, mask)

- **Declaration.** `dnd/blocks/sensory.py:95-96`: "Cells this observer has previously seen".
- **Writer.** Each recompute ORs the newly visible cells in (`sensory.py:1808-1812`). It is never cleared, and there is no other writer.
- **Published.** As `seen_cells_added` (`sensory.py:402-415`; event field `dnd/core/events.py:3378-3381`). See §3a.
- **Readers in the rules.** E2 below.
- **Helper.** `cell_seen` at `dnd/core/view.py:487-489`.

### E2. Subjective navigation over remembered cells (reads E1 as a mask, never values)

- **Domain.** `known = visible | seen` decides which reached cells may appear on a route:
  - `dnd/entity.py:5308` → `admit` (`dnd/core/navigation.py:211-218`, which requires the whole path to be known);
  - non-walking modes: `entity.py:6450-6453`;
  - adjacent-step check: `entity.py:6569` (`_has_subjective_path_destination`).
- **Values read in those cells are current objective terrain** (the path search reads the grid).
  - `tests/engine/test_navigation_movement_demand.py:148-159` asserts it: a wall placed at (10,0), out of view but remembered, removes (11,0) from the targets, and removing the wall restores it.
  - So remembered cells are a *domain mask over live values*. This is a pre-existing leak of out-of-sight changes into planning.
- **Blockers in the same search are current perception only:**
  - creatures not in `senses.entities` are ignored (`gridmap.py:2181-2189`);
  - centre objects not in `senses.objects` are ignored (`gridmap.py:2191-2199`);
  - boundary providers (walls, doors as objects) not in `senses.objects` are ignored for MOVEMENT (`gridmap.py:2432-2440`);
  - connector frames likewise (`gridmap.py:1739`).
  
  A path through a remembered corridor can therefore cross a remembered closed door that is not currently perceived. The step then fails at execution (collision, E4).
- **Spatial-effect barriers.** These use E3's *remembered ids*: `gridmap.py:2497` skips owners not in `senses.spatial_effects`. The path cache signature also includes those ids (`gridmap.py:1004`).
- **Consumers of `senses.paths` / `safe_paths`** (all built over `visible | seen`):
  - Move selection and resolution:
    - `dnd/actions.py:631-642` (`_route_to`);
    - `actions.py:711-729` (`_path_to`);
    - `actions.py:824-825`.
  - Position discovery:
    - "reachable" candidates: `entity.py:6149`;
    - move targets: `entity.py:6442-6505`, `6612-6705`.
  - Compelled movement:
    - Turned flee: `dnd/classes/divine.py:178` (plus the hazard preference at 201-203);
    - Eyebite Panicked flee: `dnd/spells/necromancy.py:1102-1112`;
    - Command "flee": `dnd/spells/enchantment.py:1808`.
  - Player choices: `dnd/player/session.py:355` (`get_available_actions`).
  - AI rows: `dnd/ai/runtime/decision_epoch.py:150`, `:468`.
- **Is it a D&D rule?** No. 5e has no pathfinding rule. "You plan only through places you know" is an engine choice: realism and usability.
- **Could current perception alone satisfy it?** Yes, in a weaker form: routes only through visible cells. That loses:
  - retreating into dark, already-explored corridors;
  - long moves around corners;
  - flee spells using the explored map.
  
  The engine needs only the bitmask. It never reads remembered values.

### E3. `Senses.spatial_effects`: last observation of each spatial effect (MEMORY, values and ids)

- **Declaration.**
  - `sensory.py:97-99`: "Discovered fixture cells and their last observed state".
  - Type: `dnd/types/senses.py:84-112` (`PerceivedSpatialEffect`, "Last observed spatial effect and only its discovered footprint cells").
- **Retention.**
  - `sensory.py:2384-2408`: "Hidden parts retain their last observation, even when the objective owner was removed".
  - An entry is popped only when every remembered cell is re-observed and none still holds the effect (`2401-2402`).
  - Suppression rows and volume rows are cut to what is currently visible (`2357-2378`, `2396-2399`).
- **Readers:**
  - **(a) Known-trap gate, `is_hazard_perceived_by`.** "In `senses.spatial_effects`" counts as perceived.
    - Sites:
      - `dnd/spatial/mechanisms.py:96-100`;
      - `dnd/spatial/jaws.py:78-82`;
      - `dnd/spatial/gas_traps.py:162-166`;
      - `dnd/spatial/environmental_conditions.py:1047-1057` ("A previously discovered mechanism stays known to that observer");
      - `dnd/spatial/portals.py:71-77`.
    - The base rule is current: stealth DC < passive perception (`dnd/spatial/area_conditions.py:244-256`).
    - It feeds `is_hazardous_for` (`area_conditions.py:258-264`, plus the trap overrides) → `GridMap.is_position_hazardous_for` (`gridmap.py:2127-2143`) → each of:
      - `hazard_cells` (`gridmap.py:5210-5216`), which feeds the safe-path search (`entity.py:5311`, `walk_in_danger=False` at `gridmap.py:2208-2210`);
      - the published hazard mask of visible cells (`sensory.py:1771-1780`);
      - the hazard flags of move targets (`entity.py:6493-6496`, `6693`);
      - the safe-route preference of compelled flee (`divine.py:201-203`, `necromancy.py:1079-1086`);
      - for the AI, `is_hazardous` on visible tiles (`dnd/ai/runtime/world_projection.py:84`) and the movement guard (`dnd/ai/runtime/movement_revalidation.py:114-130`).
  - **(b) Discovery gate.** `discovered=condition.uuid in senses.spatial_effects` (`sensory.py:2346`) lets a once-discovered effect keep producing observations when the current gate fails. The callee checks are `if not discovered and not self.is_hazard_perceived_by(...)`, at:
    - `area_conditions.py:177`;
    - `dnd/spatial/triggers.py:54`, `:186`;
    - `mechanisms.py:104`;
    - `jaws.py:94`;
    - `gas_traps.py:170`;
    - `environmental_conditions.py:1090`;
    - `portals.py:89`;
    - `dnd/spells/conjuration.py:914`;
    - `dnd/spells/illusion.py:1242`;
    - `dnd/spells/evocation.py:2669`.
  - **(c) Trap hardware observability.** An item with a `perception_condition_uuid` is observable only while its condition yields an observation (`dnd/blocks/base_item.py:528-533`). The contact for a trap's hardware therefore depends on (a) and (b).
  - **(d) Subjective barrier gate.** `gridmap.py:2497`: an effect the agent does not "know" does not block its planned crossing.
  - **(e) Presentation geometry from memory.** When the anchor is not visible, the remembered `anchor_position` / `area_geometry` / `anchor_elevation_steps` is reused:
    - `area_conditions.py:1092-1098`;
    - `conjuration.py:919-921` (Web);
    - `illusion.py:1244-1247` (Silence);
    - `evocation.py:2671-2674` (wind).
    
    This is publication only.
- **Trap triggering does not read knowledge.** The trap classes' triggers never call `is_hazard_perceived_by`.
  - `GuardianOfFaithZone._admit_trigger` (`conjuration.py:4305`) and its damage handler (`conjuration.py:4320`) gate on `is_hazardous_for`.
  - Its base perceived check returns True with no stealth DC, so no memory is involved.
- **Is it a D&D rule?**
  - (a)–(c): yes. A trap once found stays known, and creatures can avoid it. This *cannot* come from current perception when the trap's DC beats passive perception. The case is real: environmental traps and portals are perceived while ACTIVATED (`environmental_conditions.py:1051`, `portals.py:72`), and after a reset only memory keeps them known.
  - (d): realism/convenience; current-only would just mean discovering the barrier at execution.
  - (e): presentation.
- **What the engine needs:** a per-agent **set of discovered effect ids**. It needs no footprints or geometry.

### E4. Collision memory (turn-scoped knowledge from an event, not perception memory)

- **Fields.** `Senses.collision_blocked` / `directional_collision_blocked` (`sensory.py:113-121`; helpers `navigation.py:534-575`).
- **Written** when a step is blocked objectively but allowed subjectively (`dnd/actions.py:943-957`). It is also published as a movement-collision spatial event.
- **Read by:**
  - `gridmap.py:2212` (`is_walkable_for`);
  - `gridmap.py:2334-2347` (`_remembered_transition_allows`);
  - `gridmap.py:5135-5150` (search candidates);
  - `entity.py:5301-5302`, `6282`, `6315`, `6577-6579`.
- **Cleared at turn start** (`dnd/encounter.py:887-898`; test `tests/engine/test_senses_light_stealth.py:757`).
- **Is it a D&D rule?** Close to one: bumping an unseen blocker tells you something is there. Current perception cannot satisfy it, because the blocker is imperceptible. It is bounded and stays as it is.

### E5. Creator knowledge (NOT memory)

- **Rule.** `BaseItem.is_object_known_to`: `known_to_creator and source_entity_uuid == observer` (`dnd/blocks/base_item.py:1001-1002`; default `dnd/core/base_block.py:622`; set by wall constructions, `dnd/spells/wall_constructions.py:96-104`).
- **Read by:**
  - known-construction contact rows (`sensory.py:1925-1943`);
  - `attack_object_contact` (`gridmap.py:3339-3349`).
- **Index.** `gridmap.py:3154-3180`.
- It is authorship with no perception history, so it is current-only by nature.

### E6. Checked, current perception only (no memory)

- `action_scan` (`entity.py:4379-4420`): creatures and objects from current contacts, `visible`.
- Target pools: `get_visible_enemies/allies` (`entity.py:4442-4470`, used at `7450-7452`); `base_actions.py:1835-1836` (`scan.creatures` / `scan.objects`).
- Hazard mask: published over visible cells only (`sensory.py:1780`). Only the *truth* of a hazard reads E3.
- Light sources: the emitters that light a currently visible cell (`sensory.py:2412` onward). `light_source_removals` is revision bookkeeping.
- Hide (`actions.py:3016-3030`, `observers_granted`). Unseen Attacker and Unseen Target are modifiers on current perception (`dnd/conditions.py:1453-1487`).
- **No rule targets a last-known or guessed position of an unseen creature.** Attacking an unseen creature's square is not implemented, so nothing reads a last known position in the engine.

---

## 2. Server-side AI (dnd/ai/**)

### 2a. What it keeps and how it is built

- **System.** One `AIKnowledgeSystem` per session (`dnd/player/session.py:233`, `:305`; also summons, `dnd/summoning/system.py:56-60`).
  - It folds **`EventQueue.iter_events_since`**: the native, unredacted stream (`dnd/ai/runtime/knowledge_system.py:37-39`).
  - It folds at every batch dispatch (`:30-34`) and before every decision or movement-guard read (`:71-76`).
  - When an assignment opens, it does a cold fold of the whole history (`:56-63`).
- **Contents of `AIKnowledge`** (`dnd/ai/runtime/knowledge_reduction.py:146-170`):
  - `world: WorldFacts`: an **objective** copy of the whole map and every object, folded from world facts (`:218-221`).
  - `actors`: an **objective** `ActorState` for every actor ever born (`:195-216`).
  - `senses`: the controlled observers' `SensesSnapshot`, folded from their own `SensoryUpdateEvent`s (`:223-251`). These carry the engine's E1 seen mask and E3 effect memory.
  - `observers`: rows that include `seen_cells` (`:83`, `:97-108`, `:310-328`).
  - `known_entities` / `known_objects` / `known_tiles`, plus indexes, `pending_conditions` and `open_events`.
- **Memory rules:**
  - **Entities** (`:293-308`):
    - VISIBLE while a controlled observer holds a contact.
    - On loss, `remember_entity` (`:33-44`) makes it REMEMBERED. It keeps `name`, `faction`, `creature_type`, **`position` (last perceived)** and DEAD, and strips HP, AC, conditions, protections and affinities.
    - On re-acquisition, the full *current* values are projected (test `tests/ai/test_event_knowledge.py:123-162`). This matches "entering = current state in full".
  - **Objects** (`:330-341`): REMEMBERED keeps the prior fact unchanged (position, state).
  - **Tiles:**
    - A visible tile is projected at its last visible touch (`:187-192`, `:229-238`, `:357-359`; `world_projection.py:28-92`).
    - Out of view, a tile becomes SEEN and **keeps its prior values** (`:346-350`).
    - A tile that was seen but never projected gets a SEEN row with `adjacent_domain` only (`:351-355`). That reads objective map extent (`world_projection.py:20-25`, UNKNOWN versus INVALID neighbours): a minor leak.
  - **It never forgets.** No path removes known entities, objects or tiles. An object destroyed out of sight stays REMEMBERED forever, unlike the projector's "seen absent" removal (§3b).
- **It is already a pure fold "without world queries"** (`knowledge_reduction.py:1`).
  - `tests/ai/test_event_knowledge.py:97-121` replays it from audience-retained native events (`dnd/player/capture.py` `_retained_event`, `resolve_audience`) and gets identical results. The case covers a brief doorway sighting remembered at (8,8).
  - So the AI is a client-like fold, but over *native events*, not over the player wire.

### 2b. Decisions that read remembered (not currently perceived) state

| Reader | Reads | Memory? |
|---|---|---|
| `dnd/ai/policies/basic.py:858-897` `_progress_value` | hostile `known_entities` with `knowledge_state in {VISIBLE, REMEMBERED}`; distance from the move destination to the **last known position** | **yes**. It is the only built-in decision reading memory ("approach the enemy that broke line of sight") |
| `custom_ai/tactical/memory.py:96-112`, `:138-151`, `:154-158` | focus target among VISIBLE or REMEMBERED hostiles (visible ranked first; last position used for distance) | **yes** (content-pack policy) |
| `basic.py:524-543` `_row_entity_facts` and the damage, healing and control metrics | facts of row targets | no: the targets come from engine discovery (current contacts), so they are VISIBLE |
| `dnd/ai/runtime/state_projection.py:144-160` | encounter rows | VISIBLE only |
| `dnd/ai/runtime/movement_revalidation.py:84-144` | newly VISIBLE hostile, hazard tile or object | current only (before versus after) |
| `basic.py:336-400` `BasicActorMemory` | turn-local visited positions, blocked rows | policy control memory, not world memory; reset per turn |
| `known_tiles` SEEN, `known_objects` REMEMBERED, `observers[*].seen_cells` | — | **produced, read by no live policy** |
| Indirect: `decision_epoch.py:150`, `:468`, `:492` | engine discovery (legal rows), `actor.senses.objects` | the rows read engine memory E2–E4 (routes over `seen`, known-trap safe paths and hazard flags, collisions) |

Dormant code:

- `dnd/ai/runtime/subjective_projection.py` reads the live `Senses.seen` (`:111`, `:442`) and merges remembered rows (`:121-160`, `:373-480`). It is imported only by tests (`tests/engine/test_recorded_world_facts.py`, `tests/manual/test_43_ai_runtime_performance.py`).
- `dnd/ai/contracts/observation_replay.py` is imported by no live code.

### 2c. Could the AI's knowledge be a fold of the seat's published stream?

Mostly, yes. The mapping:

- `known_entities` ← the folded `PlayerState.actors` plus the composed contacts. `last_visual_position` already gives the remembered position (`dnd/player/reduction.py:413-418`).
- `known_tiles` ← `PlayerState.tiles` plus the visible and seen masks.
- `known_objects` ← `PlayerState.objects`.

What it would lose or need:

1. **Nothing from "publication has no memory".** The AI builds its memory itself: it keeps last values when a contact or cell leaves. It needs only the leave deltas, which the stream carries (contacts removed, cells removed).
2. **Wire field gaps** (not memory).
   - `creature_type`, `healing_blocked` and `damage_affinities` are in `ActorState` (`dnd/types/actor_facts.py:57-59`) but not in `PlayerActor` (`dnd/player/facts.py:325-349`).
   - Condition `state` travels, but its `applied_source_event_cursor` is renumbered per seat (`projection.py:1653-1661`).
3. **Granularity.** The movement guard reads knowledge at a movement step, inside an op (`knowledge_system.py:71-76`; test `test_event_knowledge.py:181`). The published stream is per op, so a stream-fed AI could not interrupt a move mid-path on a newly visible hostile.
4. **Legal rows still come from the server** (choices), so the engine memory E1–E4 stays server-side either way.
5. **The memory semantics would change slightly, for the better.** Objects seen absent would be forgotten, and the `adjacent_domain` map-extent leak would go away.
6. **Interaction with D1(b)** (re-entry sends only changed records). The fold needs an explicit removal or a presence signal to learn that a remembered object is gone.

---

## 3. Publication and client (dnd/player/**, SDKs)

### 3a. Memory that the engine originates and the wire carries

- **Seen mask.**
  - Published as `seen_cells_added` (`sensory.py:402-415`; `events.py:3378-3381`).
  - Folded by the client and the projector in `sensory_fold.py:71`.
  - The seat view is the union of the members' masks (`dnd/player/audience.py:423`, `:747-748`).
  - Projector: wire bits `dnd/player/facts.py:888`, re-encoding `projection.py:292`, `:357-358`. Client decode: `reduction.py:298`.
  - **The client can derive it.** `seen_added = after.seen & ~before.seen`, and the seen mask is OR-ed from `cells.visible` (`sensory.py:1811`), so seen_added ⊆ visible-after. The client can therefore compute `seen |= visible`. The one exception is an `initial` event, which sends the whole seen layer (`sensory.py:414`); verify the cold-start case before dropping the field.
- **Remembered effect footprints.**
  - The sensory event diffs the engine's E3 memory (`sensory.py:512-516`). Footprints kept out of view are therefore on the wire, and an effect is removed only when its cells are re-observed empty (`sensory.py:2401-2402`).
  - The geometry kept from memory travels too (E3(e)).
  - The seat composition merges the members' remembered footprints and retires cells seen empty through `effect_absences`:
    - `audience.py:73`;
    - `audience.py:76-110` ("It retires only that cell of another member's remembered footprint");
    - `audience.py:200-215`;
    - `audience.py:629-671`.
  - The removal walk refuses to let "a remembered field" witness a removal (`projection.py:446-454`).
  - **This directly contradicts the new rule.**

### 3b. Projector-side support for client memory (`ProjectionState.remembered`, `projection.py:1899-1928`)

- **Tiles.**
  - Sent only while visible (`projection.py:1182-1183`) and never removed, so the client remembers by omission.
  - Diffed against the remembered tile (`1184-1193`; `_tile_changes` `1137-1168`).
- **Objects.**
  - *Forgetting is a server decision.* An object is removed only when one of its remembered cells is visible and it is not observed (`1210-1213`). This uses `WorldProjectionIndex.remembered_positions` / `remembered_order` (`1104-1134`, `1194-1195`, `1233-1236`).
  - The observation grant `_object_observed` (`1001-1019`) also grants boundary objects through a visible adjacent support cell.
  - "Remembered silhouettes may remain out of sight". Contents are cleared when the grant is lost (`1216-1222`).
- **Merges with remembered values.**
  - The wall-face residue union keeps faces not visible now (`_observed_object`, `1022-1051`; test `tests/engine/test_fireball_area_record.py:147`).
  - Construction suppressions are kept when the provider is not visible (`1052-1065`).
  - Remnant supported items are admitted if remembered (`_observed_remnant` `963-970`, used at `1067`, `1562-1563`).
  - `_disclosed_object` rewrites remembered objects (`1636-1637`).
- **Bodies.**
  - Re-acquisition is patched against the remembered actor (`_emit_bodies` `2051-2058`).
  - A terminal body is never resurrected (`reduction.py:174-176`).
  - A known removal carries the held member value (`2073-2079`).
  - Spatial content is sent once per seat (`2071`).
- **Identity knowledge (identities, not values).**
  - Admission skips actors already known (`known_actor_uuids=remembered.actors`, `application.py:72`; `capture.py:876-877`).
  - It re-admits on re-acquisition (`acquired`, `capture.py:808`).
  - Known names, connectors and content feed disclosure in the combat log (`application.py:67-73`, `:84`; `dnd/subjective_combat_log.py:62-70`).

### 3c. The client fold today

- `dnd/player/reduction.py` is the Python reference fold. The server runs it on the mirror.
- The SDKs are transports only:
  - Python: "No engine … reducer dependency", `sdk/python/src/dnd_player/__init__.py:1`;
  - player-typescript: "Consumers own reduction", `sdk/player-typescript/src/index.ts:1`.
- `sdk/typescript` targets a legacy `/replication/*` route family that `server/app.py:181`, `:229` does not serve.
- The Godot fold is outside this repository.

The reference fold already keeps memory by not forgetting:

- tiles are only added or updated (`apply_world_update` `132-145`);
- objects leave only through `objects_removed` (`142-143`);
- actors are never deleted; a terminal one becomes `present=False` (`382`);
- `last_visual_position` changes only on a visual contact or the seat's own move (`392`, `414`, `418`);
- perception is current; `seen` only grows (`358-366`; `sensory_fold.py:40-75`).

### 3d. What the client fold must do to own memory under "enter = full, leave = nothing, both = change"

1. **Tiles.** On entry, replace the tile with the full current one. On leave, keep it. No diff is needed.
2. **Objects.**
   - On entry, replace.
   - On leave, keep the silhouette and drop the contents (a client rule).
   - Forget a remembered object when one of its cells is visible and it was not observed at that event. The client must reproduce `_object_observed` (the boundary-side rule).
   - Alternatively, the server keeps `remembered_positions` (knowledge only) and sends a key-only removal. With D1(b) this is required, because an unchanged re-entry is not re-sent.
3. **Wall faces and suppressions.** The server sends the residues and suppressions of the visible faces only. The client merges per (object, condition, face), keeping the others.
4. **Actors.** Keep the body on contact loss, and the last position from the last visual contact (already done). On re-entry, replace it with the full body (conditions keyed by uuid).
5. **Spatial effects.** Keep each effect's last sighting cells and geometry, and retire cells seen empty (the `audience.py` absence logic, already shared code). The engine would then publish the current sighting only.
6. **Seen.** `seen |= visible`.
7. **The server still needs per-seat identity knowledge** (known actors, names, content, objects' remembered positions) to decide disclosure. That is knowledge, not values.

---

## 4. Table: every memory reader

| # | Layer | file:line | Needs | Possible with current perception only? |
|---|---|---|---|---|
| 1 | Engine | `entity.py:5308`, `6450-6453`, `6569`; `navigation.py:211-218` | explored mask `Senses.seen` as the route domain (values read live) | weaker: routes through visible cells only |
| 2 | Engine | `actions.py:631-642`, `711-729`, `824-825`; `entity.py:6149`, `6442-6505`, `6704-6705` | routes over #1 (move, position discovery) | weaker, as #1 |
| 3 | Engine | `divine.py:178`, `necromancy.py:1102-1112`, `enchantment.py:1808` | compelled flee routes over #1 | weaker, as #1 |
| 4 | Engine | `mechanisms.py:96-100`, `jaws.py:78-82`, `gas_traps.py:162-166`, `environmental_conditions.py:1047-1057`, `portals.py:71-77` | discovered-trap ids (known trap) | **no** (DC > passive perception after a reset) |
| 5 | Engine | `gridmap.py:2127-2143`, `5210-5216`; `entity.py:5311`, `6493-6496`, `6693`; `divine.py:201-203`; `necromancy.py:1079-1086`; `sensory.py:1771-1780` | hazard truth through #4 (safe paths, hazard flags, hazard mask) | no for known traps; yes otherwise |
| 6 | Engine | `sensory.py:2346` + the `discovered` gates listed under E3(b) | "already discovered" ids | no (same as #4) |
| 7 | Engine | `base_item.py:528-533` | trap hardware observability through #6 | no (same as #4) |
| 8 | Engine | `gridmap.py:2497`, `1004` | known barrier-effect ids for subjective crossing | yes (discover at execution) |
| 9 | Engine (publication) | `area_conditions.py:1092-1098`, `conjuration.py:919-921`, `illusion.py:1244-1247`, `evocation.py:2671-2674` | remembered anchor and geometry | yes; it is presentation and moves to the client |
| 10 | Engine (publication) | `sensory.py:2384-2408` (retention), `512-516` (diff) | remembered footprint values | yes; moves to the client |
| 11 | Engine | `actions.py:943-957`; `gridmap.py:2212`, `2334-2347`, `5135-5150`; `entity.py:5301-5302`, `6282`, `6315`, `6577-6579`; reset `encounter.py:887-898` | turn-scoped collision knowledge | no (the blocker is imperceptible); bounded, keep |
| 12 | Engine | `base_item.py:1001-1002`; `sensory.py:1925-1943`; `gridmap.py:3339-3349` | creator knowledge | not memory; stays |
| 13 | AI | `knowledge_system.py:37-39`; `knowledge_reduction.py:146-170` | own fold of the native stream: objective world and actors, controlled senses | — |
| 14 | AI | `knowledge_reduction.py:33-44`, `293-308` | REMEMBERED entity (last position, faction, name) | the fold keeps it itself |
| 15 | AI | `knowledge_reduction.py:330-359`, `229-238`; `world_projection.py:20-25` | REMEMBERED objects, SEEN tiles (last values; map-extent leak) | unused by policies, so droppable |
| 16 | AI decision | `basic.py:858-897` | last known hostile positions | weaker: no hunting after line of sight is lost |
| 17 | AI decision | `custom_ai/tactical/memory.py:96-112`, `138-158` | REMEMBERED focus target | weaker: focus resets on line-of-sight loss |
| 18 | AI (indirect) | `decision_epoch.py:150`, `468`, `492` | engine discovery → #1–#8, #11 | follows the engine decision |
| 19 | Publication | `sensory.py:402-415`; `events.py:3378-3381`; `audience.py:423`, `747-748`; `sensory_fold.py:71` | `seen_cells_added` | yes: the client derives `seen |= visible` (check `initial`) |
| 20 | Publication | `audience.py:73`, `76-110`, `200-215`, `629-671`; `projection.py:446-454` | footprint memory merge and absences | yes: client-side (shared code) |
| 21 | Publication | `projection.py:1182-1193`, `1137-1168` | tile memory diff base | yes: send entering tiles whole; the client keeps them |
| 22 | Publication | `projection.py:1104-1134`, `1194-1195`, `1210-1213`, `1233-1236` | object forgetting rule (remembered positions) | knowledge only (positions); the client can apply it, or the server sends key-only removals |
| 23 | Publication | `projection.py:1001-1019`, `1216-1222` | grant on boundary objects; contents cleared on leave | the client clears on leave |
| 24 | Publication | `projection.py:1022-1065` | wall-face union, suppression retention | yes: client-side merge |
| 25 | Publication | `projection.py:963-970`, `1067`, `1562-1563`, `1636-1637` | remnant items gated by remembered objects | needs a known-object identity set (knowledge) |
| 26 | Publication | `projection.py:2051-2058`, `2071`, `2073-2079`; `reduction.py:174-176` | body patch, content-once, held removal value | yes, under D1(a) or (b); a removal by uuid only |
| 27 | Publication | `application.py:67-73`, `84`; `capture.py:808`, `876-877`; `subjective_combat_log.py:62-70` | known actors, names, content (identities) | knowledge sets; stay per seat |
| 28 | Client | `reduction.py:132-145`, `172-179`, `382`, `392`, `414`, `418` | keeps tiles, objects, bodies, last position | already client memory |

---

## 5. The minimal memory the engine needs for its own rules (per-agent knowledge)

1. **M1. Explored mask** (`Senses.seen`): a bitmask with no values.
   - It is needed only if routes may cross cells that are not visible now (#1–#3).
   - The engine already reads live terrain there, so no value memory is involved.
   - If the human accepts planning through visible cells only, M1 can go.
2. **M2. Discovered spatial-effect ids**: a set per agent.
   - It is needed for D&D trap knowledge (#4–#7) and, optionally, for the barrier gate (#8).
   - Today this is the whole `PerceivedSpatialEffect` map. The rules read only its keys.
   - Footprints and geometry are publication and can move to the client once the engine publishes current sightings only.
3. **M3. Turn-scoped collision cells and sides** (#11): event-derived, already bounded.

Everything else is not engine-rule memory: tile values, object silhouettes, wall faces, effect footprints, last known positions, names. It is either client presentation or AI decision memory.

Pre-existing inconsistency, to note and not fix:

- In remembered cells the engine reads *current* terrain, which leaks out-of-sight changes.
- It also drops boundary and creature blockers that are not perceived now.

A values-free M1 is consistent with the new publication rule. The leak is a separate question for the human.

## 6. What moving memory to the client would cost the server AI today

- **Moving publication memory (§3) to the client: nothing.** The AI never reads publication. It folds the native stream and keeps its own REMEMBERED and SEEN memory (§2a).
- **Making the AI memoryless as well** (the "weaker server AI for now"):
  - only `basic.py:858-897` (no approach to last-seen hostiles) and the content-pack tactical focus degrade;
  - tile and object memory and `seen_cells` are unused and could be deleted freely.
- **Removing engine memory** is a separate decision, and it touches players too, since the same discovery feeds player choices (`session.py:355`):
  - M1: AI and players plan through visible cells only;
  - M2: they no longer avoid a rearmed trap they found earlier;
  - M3: they retry an invisible blocker within the turn.
- **Running the AI later as an external client** needs:
  - the wire fields in §2c(2);
  - acceptance of per-op instead of per-step movement interrupts;
  - legal rows still served by the engine.

  Its memory would then be its own fold of the seat's stream, which is exactly the client-side model.

One aside on cost: each AI assignment keeps an **objective** `WorldFacts` and all actors (`knowledge_reduction.py:152-153`). That is another per-assignment objective copy, like the projector's `ProjectionState.world`. It is not memory in the fog-of-war sense, but it falls under the same "one shared objective fold" idea.
