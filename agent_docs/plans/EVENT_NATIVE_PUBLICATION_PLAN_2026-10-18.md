# Event-native, stateless publication: plan (draft for review, 2026-10-18)

Design source: [EVENT_NATIVE_DELTAS_2026-10-18.md](../EVENT_NATIVE_DELTAS_2026-10-18.md), revision 2 and "Human answers", with the studies in [event_native_deltas_2026-10-18/](../event_native_deltas_2026-10-18/). Base: branch `codex/event-native-deltas`, engine at integration `a6ee21389`, player wire schema 15.

Status: **draft. AGENTS.md requires the antislop and antiOOP reviews before approval, and the human approves before implementation.**

## 1. Goal and targets

- **The human's targets:** every seat update ≤100 KB, every op ≤100 ms (≤50 acceptable). Total cost counts: no work moved to the client or to the next request.
- **The human's rule:** publication keeps no remembered state.
  - Perceived before and after an event: the event's keyed change, disclosed per field.
  - Entering perception: the current state, in full.
  - Leaving perception: nothing.
  - Per-seat server state is what is perceived now and which static content ids were sent. There are no client-value copies and no diffs.
- **Native behaviour is unchanged.** The engine's events, logs, AI and rules stay identical, except the native fields this plan adds (§4 E2) and the bug fixes (§4 E1), which have their own contract tests.

## 2. Scope

- **In scope:**
  - the player wire and the projector: world, bodies and items, sensory, spatial effects, lineage and facts;
  - the native change records the wire needs;
  - the seat-layout gates;
  - the latent bugs the studies found.
- **Out of scope** (the human):
  - the combat log;
  - memory retention;
  - remembered-cell pathfinding (deferred; the current-terrain leak stays);
  - reconnect beyond the decided rule (journal replay of the seat's spool, "the same as having been there from the start");
  - the HUD until the H1/H2 study is decided (§4 E5);
  - the Godot client itself. It is the human's; each schema bump ships a Godot fold note.

## 3. The decided rules

1. **Composition.** The wire carries the seat's composed view. Every perceived thing keeps its attribution: the bits of the seat members who perceive it. One fact per settlement, never member by member, because transient add-then-remove states must not reach the wire.
2. **Keyed changes.** A record perceived before and after an event gets the event's change, keyed: residue (cell, material, contribution); condition uuid; item uuid; loadout slot; light source; effect.
   - Scalars carry their new value.
   - Cell sets go as packed added and removed masks.
   - The change record names its fields, so a change to hidden fields alone sends nothing.
3. **Entering perception** (the composed view's transition, never a member's) sends:
   - for cells: a packed mask, packed columns of current values, current conditions and residues, and objects and connectors touching the cells;
   - for bodies: all changeable fields;
   - for items and effects: their current state.
   
   The client resets what it holds for those cells and records, then applies the snapshot.
4. **Static content once per content id per seat:** residue material name, description and max amount; an item's look and profile; a body's birth fields; a tile's static row; spatial-effect content (already).
5. **Nothing restated in one update:**
   - the envelope (generation, observer) once, with the audience in the initialization only;
   - the spell declaration on the root application only, and `SpellFact.application` deleted (the resolution row carries it);
   - `cause_occurrence` deleted (it always equals `parent_event`);
   - in-group `parent_lineage` and `PlayerNode.lineage` dropped (ordered `children_lineages` and `parent_event` stay);
   - `observer_position` only when it changed;
   - a REMOVED state sends `removed_positions` only;
   - an admission doesn't repeat the sensory contact.
6. **Both light levels:** the objective resolved light and the perceived light, for cells the seat perceives.
7. **Numbering:** keep the per-seat occurrence numbering, so the wire doesn't leak the count of undisclosed events.
8. **Reconnect:** journal replay of the seat's spool. The client's memory rules must be deterministic:
   - `seen |= visible`;
   - forget an object when its cell is seen without it;
   - the wall-face merge;
   - effect-footprint retirement when seen empty.

## 4. Phases

Dependencies: E0 → (E1 ∥ E2) → E3 → E6. E5 follows the HUD decision. Each phase is its own lane in its own worktree, merged into `codex/event-native-deltas` after its gates.

### E0: harness and baselines (no engine change)
- `gallery_crowd.py` and `gallery_transcript.py` get a seat-layout option:
  - **G1:** one seat per faction (today: amber 4, blue 26);
  - **G2:** one seat per character, the capacity worst case;
  - **G3:** blue batched into seats of 5.
- A **room re-entry** case: see a room, leave, close the door, reopen it, step in. This is the new rule's worst case.
- The **new oracles**, written before the change and run on the current head:
  - **O1:** at each op end, per seat, the client fold restricted to what the seat perceives equals a snapshot built from the session fold by the same functions that build entering snapshots;
  - **O2:** the spool fold equals the live fold;
  - **O3:** the perceived part of the folded client state equals the base recording's, on a common representation.
- **Baseline:** bytes and ms for every case on G1, G2 and G3 at the head, 3 runs on a quiet machine.

### E1: latent bugs (each with a failing-first contract test)
1. The client and engine folds disagree on temporary HP and its grant in a condition's `resulting_stats`, and on INTERNAL conditions changing a body without a fact. The change record is built from the engine fold's own case.
2. Non-controllers keep a ghost layer for a destroyed equipped item (projection.py ~808-811).
3. Connectors are read from the init event only (projection.py ~1224).
4. The startup fold lacks LIGHT_CHANGED/TILES_CHANGED, so initial light can be stale.
5. Entered cells come from the member event instead of the composed view (projection.py ~1466; expose entered/left from `_fold_view_cells`, audience.py ~396-405, ~711).
6. Re-acquisition is counted per observer instead of per seat (capture.py ~808, ~877).
7. The server and client compose seats over different values (`owner_revision`, audience.py ~161). This is removed by §3.1, and E1 adds the test that would catch it.

### E2: native keyed change records (engine events gain fields; nothing else changes)
- **Residues:** `deposit_residues` / `remove_residues` record (cell, material, amount, contribution) on their event (≈30–50 lines).
- **Terrain writers** record `walking_cost` changes (≈10–20 lines).
- **One `ActorChange` / `ItemChange` per event case,** built in `advance_capture` from the engine fold's own case and shared by every seat:
  - which fields of a condition or its stats changed;
  - an item's previous slot and holder;
  - the fields changed inside whole-item snapshots.
- **`SensoryUpdateEvent`** gets a settlement marker, and light sources and effects become *added* (whole) / *patched* (changed fields; cells added and removed) from the before/after the native code already holds (sensory.py ~2516-2534, ~2379-2403).
- **Gate:** native transcripts identical apart from the added fields; the AI-knowledge fold and the capture unchanged; sweep 0 new; pyright 0 new.

### E3: stateless projector (schema 16)
- **World:**
  - delete `remembered.tiles/.objects/.connectors`, `apply_world_update(remembered)`, `_tile_changes` and the diff loop;
  - delete `remembered_positions/order`, `observed_values`, `_observed_plain_or_object`, the remembered merges in `_observed_object`, and the removal, contents-clearing and connector-gate rules judged against memory;
  - entering snapshots read the session fold as of the occurrence.
- **Bodies and items:** delete the body diff, `item_patch` / `_item_patches`, `_holdings` / `_gear_observation`, the whole-holdings `EquipmentFact` (it becomes a holdings delta), the known-removal machinery, the permanent `known` set, and `acquired`.
- **Sensory and effects:** delete `spatial_values`, the sighting filter, the per-seat spatial revisions, the content value checks and the equality scans. Composed seat facts with member attribution.
- **Restatements:** §3.5.
- **The session fold:** one per session, written only from event after-values. Per seat: perception (composed and members), control, the static-content-sent sets, disclosed lineages and public cursors. The per-seat `ProjectionState.world` / `.actors` is deleted once projection runs event-major across seats; if that is too large for this phase, it is logged as its own step.
- **The client:** the Python reference fold (`dnd/player/reduction.py`) adds the four memory rules of §3.8. SDKs are regenerated. The Godot fold note is `agent_docs/GODOT_CLIENT_FOLD_SCHEMA_16_*.md`.
- **Gate:**
  - O1, O2 and O3 on every case and on G1, G2 and G3;
  - the "client == remembered" replica test is replaced by O1;
  - sweep 0 new; pyright 0 new; SDK tests;
  - the bytes and ms table on G1, G2 and G3.

### E5: HUD (after the human decides from the H1/H2 study)
Placeholder. The HUD stays a per-seat snapshot diff until then, the one declared exception, and is listed as such in RULE_VIOLATIONS.

### E6: exit
Re-time every case on G1, G2 and G3 on a quiet machine, 3 runs. Report every row over 100 ms or 100 KB with what dominates it.

## 5. Risks

- **The composed view changes what a multi-member seat's client can show per character.** Attribution bits keep "who sees what"; if the UI needs a character's own full view, that is a later per-member stream.
- **Re-entry bytes:** the room re-entry case is the new worst case, mostly wall placements. Packed tile columns and compact placements are the mitigation; measure in E0 and E3.
- **Objects destroyed or moved while unseen** are corrected only when their cell is re-entered. The client and server must define "touches the entered cells" identically, tested by O1.
- **Ordering:** updates stay one per occurrence (once per group is not exact for removals). A fact arriving before its sensory child must not be lost (summon creation witnesses).
- **Admission** moves from capture into the projector walk.
- **Schema and SDK digest bump;** old recordings need the common-representation compare (O3).
- **Event volume:** E2 adds fields, not versions. Check retained-event growth (memory is out of scope, but don't regress it knowingly).

## 6. Reviews and tracking

- **Before approval:** one antislop and one antiOOP reviewer over this plan; accepted findings are folded in and rejected ones listed with reasons.
- **During implementation:** a plan-adherence tracker sub-agent per AGENTS.md; each lane runs its own reviewers on its design and at its end.
