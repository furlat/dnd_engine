# AntiOOP review: EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 (draft)

Reviewer: antiOOP (AGENTS.md; plan §6a of ENGINE_SINGLE_PASS_CHANGE_PROPAGATION_PLAN_2026-10-16). Read-only. Tree: `/home/tommaso/.codex/worktrees/event-native-deltas/dnd_engine` (branch `codex/event-native-deltas`, f84729140). "Plan Lnn" = line of `agent_docs/plans/EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18.md`. Nothing was run.

Summary: the pieces the plan adds are meant to be data plus functions, and the plan adds no class with behaviour. The hazards are in what the plan leaves unnamed. It does not say who owns the session fold. It does not say where the change records live, or which representation each consumer reads. It keeps a partly emptied client-state type as server state. And it keeps two owners for three memory facts.

---

## 1. BLOCKER: the session fold has no owner, no type and no single writer, and E3 has an escape hatch that keeps the per-seat folds

**Plan text.** L105: "The session fold: one per session, written only from event after-values … The per-seat `ProjectionState.world` / `.actors` is deleted once projection runs event-major across seats; if that is too large for this phase, it is logged as its own step." L73: O1 compares against "a snapshot built from the session fold".

**Problem.**
- A shared fold already exists. `CaptureCheckpoint` (capture.py:159-176) is "the session's one recorded fold" (application.py:21). `advance_capture` (capture.py:784-856) writes it. It holds actors, contacts and positions, but no world. The plan does not say whether the session fold *is* that checkpoint extended with world facts, or a new structure. A new structure means two shared objective actor folds.
- Today the same actor-holdings fact has several writers:
  - `remove_previous_item_holdings` in `advance_capture` (capture.py:837-838);
  - the same call in capture's `apply_world_fact` (capture.py:386), which also rewrites `target.actors` for owned items (389-394);
  - the per-seat walk (projection.py:1431).
- The per-seat world fold is seat-skewed:
  - a sensory event applies its `observed_changes` sources early, at that seat's observer (projection.py:1452-1460);
  - the sensory event's own tile after-values are written into the seat's world (1461-1465).

  A session fold cannot do either per seat. The plan does not say what replaces them (the world study's "apply at commit version", world.md §1.2).
- With the escape hatch, entering snapshots still read the per-seat, seat-skewed fold. That leaves two folds, and O1 has no "session fold" to compare against.

**Fix.**
- Name `CaptureCheckpoint` as the session fold and add `world: WorldFacts` to it. `advance_capture` is its only writer. Delete the actor writes in capture's `apply_world_fact` and in the projector walk.
- Turn early application into an objective rule in the fold, applied at commit version.
- The fold takes no subjective sensory tile values.
- Make event-major projection a phase of its own (between E2 and E3) with its own gate. Remove the escape hatch.
- Entering snapshots are stateless functions `(fold, mask/ids, seat knowledge) -> rows`. There is no versioned or lazily materialized fold.

## 2. MAJOR: `ProjectionState.remembered: PlayerState` survives half-emptied, as a disguised client replica

**Plan text.** E3 deletes `remembered.tiles/.objects/.connectors`, the body and item diffs, and so on (L99-103). E5 keeps "a per-seat snapshot diff" for the HUD (L114). Per-seat state is listed as "perception (composed and members), control, the static-content-sent sets, disclosed lineages and public cursors" (L105).

**Problem.**
- After E3, `remembered` is still the client's own type (facts.py:1181-1208). It holds:
  - `hud_snapshot` (projection.py:2167-2170);
  - `content` (application.py:47, 68-69, 89-95; server/worker.py:98);
  - `senses` and `perception` (projection.py:1474-1475, via `fold_senses`);
  - `spatial_content` (projection.py:1759, 2071);
  - `actors`, used for log names and known actors (application.py:67, 72);
  - `connectors` (application.py:74);
  - `viewing_audience`, a computed property (facts.py:1206-1208; worker.py:94).
- The projector imports ten client-reducer functions (projection.py:61-62), and initialization runs the client fold to admit content (application.py:47, `reduce_initialization`).
- So any PlayerState field left over silently remains a copy of client values. O1 would again compare the reducer against itself, which is the fault the plan gives for retiring the replica test (L109).

**Fix.**
- Replace `remembered` with a seat-knowledge dataclass whose fields are exactly the allowed ones:
  - audience;
  - composition;
  - observed objects and granted containers;
  - static-sent ids;
  - numbering maps;
  - the HUD exception, as one named field `hud_sent`, listed in RULE_VIOLATIONS.
- Log names and known connectors come from the static-sent birth ids and the connectors visible now.
- Cut every import of `dnd.player.reduction` from `projection.py`, `capture.py` and `application.py`, and add an architecture test that forbids it. Server code never runs the client fold.

## 3. MAJOR: where the change records live and what produces them. Either two dispatches, or a false gate

**Plan text.** L90-93: "One `ActorChange` / `ItemChange` per event case, built in `advance_capture` from the engine fold's own case." L95: "the AI-knowledge fold and the capture unchanged."

**Problem.**
- The engine fold is `dnd/actor_projection.py:64-139`, a single `match`. Its callers:
  - AI (knowledge_reduction.py:8, 209);
  - capture, through the player wrapper that strips INTERNAL (player/actor_projection.py:14-21; capture.py:449, 801, 840, 1198);
  - the projector (projection.py:1431).
- A separate `actor_change(before, event)` would be a second dispatch over the same events. Two folds disagreeing is the class of bug E1.1 fixes.
- Making `apply_actor_fact` return the change changes the AI fold, which contradicts the L95 gate.
- The plan names no module for the type. The study puts it next to `dnd/types/actor_facts.py`. If it went into `dnd/player`, the producer (`dnd/actor_projection.py`, an engine-level module) would have to import player code. Nothing forbids attaching it to the Event (a memo on a runtime object, banned by §6a) or computing it lazily.

**Fix.**
- Put frozen `ActorChange`, `ItemChange` and the `ChangeField` enum in `dnd/types/actor_facts.py` (leaf).
- The one `match` in `dnd/actor_projection.py` returns the change, and `apply_actor_change(state, change)` is the one fold for AI, capture and projector.
- Reword the gate as "AI fold *output* identical".
- The records are values in `CaptureContext`, keyed by event uuid. They are never attributes on the Event and never cached properties.
- INTERNAL stripping and disclosure are projector functions, not methods on the record.

## 4. MAJOR: E2's native fields leave two representations of the same change on the event

**Plan text.** L87-95: residues are recorded as keyed rows; light and effect rows become *added* or *patched*; "engine events gain fields; nothing else changes"; the AI fold and capture stay unchanged.

**Problem.**
- If nothing else changes, the whole `tile_states` stays. The world folds (world_facts and the AI) read it.
- Whole light and effect rows stay too. `sensory_fold.py:64-68` and the `SensoryDelta` protocol (senses.py:187-191) read them, and the AI reads them through `apply_current_senses`.
- So the session fold is written from one field and the wire sends another. That is two ways to publish one change, and the drift E1.1 fixes, rebuilt natively.

**Fix.** Choose once for each field:
- either the keyed or patched field *replaces* the whole one, and every consumer moves in E2 (the study's N5 list: sensory_fold, audience, AI reducer, capture `_reduce_sensory_fact`, `validate_replay_payload`, recordings, SDK), and the gate wording changes;
- or there is no native field, and the change is derived in capture from the whole rows against the session fold.

In both cases the session fold and the wire read the same field.

## 5. MAJOR: new wire fact types extend the isinstance chains, and the item compare invites field loops

**Plan text.** E3 turns `EquipmentFact` into "a holdings delta". The study adds a condition patch, a stats-only change and an effect value (actors_items_hud.md §6). E2 records "the fields changed inside whole-item snapshots". L14 says "no diffs".

**Problem.**
- Facts are already dispatched by `isinstance`:
  - projection.py:1519, 1607, 1610, 1864, 1870, 2062, 2073;
  - content_composition.py:79, 85;
  - reduction.py:393, 443, 447 (`match`).
  
  Each new fact class adds a branch to every chain. The census lists these chains as a violation category.
- `ItemPresentationState` has about 40 fields (item_types.py:150-190). A compare over a whole snapshot is where a `model_dump` or `model_fields`+`getattr` loop gets written, which is the pattern the census fixed in `value_fields`.
- The study's "compare once with the shared fold" is a diff, which L14 says does not exist.

**Fix.**
- One wire `ActorChangeFact` carrying keyed rows tagged by `ChangeField`. Disclosure is a table from `ChangeField` to a predicate (the study's §3 table), with explicit code per field and no `getattr`.
- Split items into look, profile and state, so only the small dynamic state is compared, field by field.
- Reword L14: "no per-seat diffs; the one seat-independent before/after compare is in capture".

## 6. MAJOR: last-seen stamps kept without saying so, and memory facts with two owners

**Plan text.** L105: per-seat "perception (composed and members)". L56-60: the client rules `seen |= visible` and "effect-footprint retirement when seen empty".

**Problem.**
- The design source's rule says "no last-seen stamps" (EVENT_NATIVE_DELTAS L20). The plan's restatement (L14) drops that clause.
- `AudiencePerception.contact_cursors/effect_cursors/effect_absences` (audience.py:69-74) are exactly such stamps. Study R1 asked the human about them, and the Human answers do not cover it.
- Footprint retirement is server-side (audience.py:76-117, 629-671). The engine still publishes retained footprints (sensory.py:2384-2408), and memory retention is out of scope. Adding the client rule gives two owners.
- `seen_cells_added` is not deleted, so `seen |= visible` gives the seen mask two sources.

**Fix.**
- List the cursors explicitly and get the human's ruling on R1. Under (B), contacts can rank without cursors.
- Give each memory fact one owner. Either the wire carries current sightings and `seen_cells_added` leaves it, or the client rules for them are dropped.

## 7. MAJOR: exposing the composed change invites scratch fields on `AudienceComposition`, and composition stays in the client reducer

**Plan text.** E1.5: "expose entered/left from `_fold_view_cells`". L34: "one fact per settlement … with attribution".

**Problem.**
- `apply_current_audience` returns nothing and works by mutation (audience.py:586-765). `contact_overrides` (audience.py:456) is already scratch state that the client reducer writes (reduction.py:189, 339) and the composition consumes (audience.py:602-604).
- Settlement-level before/after and entered/left will tend to become `last_entered` / `pending_settlement` fields.
- The world study routes entered/left through `fold_senses` in **reduction.py**:358-366, but under (B) the client no longer composes.
- Attachment to "the first member node" borrows a native identity.

**Fix.**
- `apply_settlement(composition, member_events) -> ComposedChange`, a frozen return value: entered, left, contacts set and removed, attribution changes. The before state is held in locals, and a settlement closes within one group (assert).
- Move composition out of reduction.py, so that projection calls audience.py directly.
- Derive attribution from the per-member layers and the `*_members` sets that already exist (audience.py:440-451), not from a new index.
- Key the fact by the native settlement marker.

## 8. MINOR: static content goes through five parallel channels and sent sets

**Plan text.** L45 lists tile rows, item look and profile, birth fields, residue materials and spatial content.

**Problem.**
- Each channel has its own store, its own sent set and its own code. Content descriptors are a sixth (content_composition.py).
- The study suspects spatial content restates `ContentDescriptor` (R10).
- Residue headers would ride on every native event to avoid the lazy `_PROFILES` registry (residues.py:84-89).
- Sent sets updated in the middle of the walk can lie when group-final disclosure drops facts (projection.py:1627-1630).

**Fix.**
- One sent set per seat, keyed by `(StaticKind, id)`, updated only from the final emitted update. One client static store.
- Add "static stores are never pruned" to the client contract in §3.8.

## 9. MINOR: "touches the entered cells" is defined inside an engine-side index

**Plan text.** L123: "The client and server must define 'touches the entered cells' identically."

**Problem.** The rule lives inside `_index_object` (world_facts.py:68-79). `dnd/world_facts.py` imports `dnd.blocks.base_item`, and reduction.py does not import it. The client would reimplement the rule (in Python, and again in Godot) or import engine modules.

**Fix.** Extract a leaf `placement_support_cells(placement)` into `dnd/types/world_placement.py`, and use it in both world_facts and reduction.

## 10. MINOR: second paths for initialization and admission

**Plan text.** L39-44 (entering), L82 (E1.6 fixes `acquired` in capture), L125 ("admission moves … into the projector walk").

**Problem.**
- Initialization (`begin_projection`, projection.py:2179-2208) is not stated to use the entering-snapshot functions.
- E1.6 fixes code (capture.py:808, 877) that E3 deletes.

**Fix.**
- Initialization means "everything perceived at the startup cursor enters", built by the same functions.
- Do E1.6 in the E3 walk and keep only its failing-first test from E1.

---

Import DAG: no step *needs* dnd/core→dnd/player, engine→player, player→server or a cycle, if findings 3 and 9 are followed. The risks are finding 3 (where the change type lives) and finding 2 (the server-side import of the client reducer, a direction today's code already has).
