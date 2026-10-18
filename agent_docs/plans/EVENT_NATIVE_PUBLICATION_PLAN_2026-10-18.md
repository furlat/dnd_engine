# Event-native, stateless publication: plan (revision 2, after the antislop and antiOOP reviews, 2026-10-18)

Design source: [EVENT_NATIVE_DELTAS_2026-10-18.md](../EVENT_NATIVE_DELTAS_2026-10-18.md), revision 2 and "Human answers", with the studies in [event_native_deltas_2026-10-18/](../event_native_deltas_2026-10-18/). Base: branch `codex/event-native-deltas`, engine at integration `a6ee21389`, player wire schema 15. The reviews are kept in [event_native_deltas_2026-10-18/plan_reviews/](../event_native_deltas_2026-10-18/plan_reviews/) (antislop: 17 findings; antiOOP: 10). §9 maps every finding to its resolution.

Status: **revision 2, decisions taken (§8); implementation started with E0 (the human: "we are in a worktree so we can fail fast and find a better solution if needed").**

## 1. Goal, targets and what this plan can reach

- **The human's targets:** every seat update ≤100 KB, every op ≤100 ms (≤50 acceptable). Total cost counts: no work moved to the client or the next request.
- **The human's rule:** publication keeps no remembered state.
  - Perceived before and after an event: the event's keyed change, disclosed per field.
  - Entering perception: the current state, in full.
  - Leaving perception: nothing.
  - Per-seat server state is knowledge only: what is perceived now, control, which static content ids were sent, disclosed lineages and public cursors. There are no copies of client values.
  - Changes are computed once per event against the session's single objective fold or recorded by the writer, never against a per-seat copy.
- **What this plan cannot reach alone (stated up front).** Fireball (≈201 KB) and Circle of Death (≈220 KB) fall to an estimated ≈140 KB, not under 100 KB: the combat log (41–57 KB), out of scope by the human, remains. These two rows are named exceptions owned by the combat-log redesign (Q2).
- **Metrics:**
  - ms is the gallery `total_ms` per op (wall clock, as today) on each seat layout;
  - the post-reply collection is reported beside it;
  - the client fold time per update is reported;
  - bytes are the largest seat update per op, per layout.

## 1b. Where publication time goes today (integrator's profile at ff7701f9a; cProfile ms; real ≈ ÷2)

| Case | Publication | Seat audience fold (`fold_senses` → `apply_current_audience`, once per member fact) | `_world_update` | HUD `_snapshot_sheets` | `advance_capture` |
| --- | --- | --- | --- | --- | --- |
| SG move | 104 | 47 (90 calls) | 6 | 18 | 7 |
| Sleet drop | 282 | 105 (30) | 77 | 18 | 7 |
| Daylight | 270 | 118 (30) | 46 | 18 | 8 |
| Fireball | 197 | 44 (30) | 35 | 19 | 18 |
| Wall of Stone | 123 | 41 (30) | 29 | 18 | 9 |

- **Inside the audience fold, most of the time is per-member remembered-effect machinery** (`_current_effect`, `visible_positions`, `_membership` ×15K, `any()` ×2.2K per Daylight op): ≈50–60 %. §3.2 (visible part only, no absences or footprint memory) deletes it.
- **What remains** (the cell fold 6–9, senses 4–6, light rows up to 11) runs once per settlement under §3.1, not once per member fact.
- `_world_update` is replaced by the stateless world lane, and the HUD by E5.
- **Projection, real ms:** after E3 and E5, publication is Daylight ≈86 → ≈35–40, Sleet drop ≈90 → ≈35, Fireball ≈65 → ≈25, Wall of Stone ≈39 → ≈15. Totals are then ≈95 / ≈85 / ≈105 / ≈115: Fireball and Wall of Stone become native-bound.
- **Wall of Stone native** (≈90 real) is no longer light work: `recompute_lights_at_positions` is ≈23 profiled. It is settlement ≈85 profiled (mostly the 30 views' wall-FOV re-solves, owned by the wall-FOV lane), the escape rule ≈38 (its escape Move ≈31), and the zone install ≈46.

## 2. Scope

- **In scope:**
  - the player wire and the projector: world, bodies and items, sensory and spatial effects, lineage and facts;
  - the change records the wire needs;
  - the seat-layout gates;
  - two latent bugs fixable on today's head, plus tests for the rest that turn green with E3.
- **Out of scope** (the human):
  - the combat log. Its inputs must stay byte-identical: the log's known names and connectors come from structures this plan deletes, so the plan keeps a log-input path and gates on byte-identical log appends;
  - memory retention;
  - remembered-cell pathfinding (deferred; the current-terrain leak stays);
  - reconnect beyond the decided rule (journal replay of the seat's spool);
  - (the HUD is now in scope: E5, decided H2-exact);
  - the Godot client. Each schema bump ships a Godot fold note.

## 3. The decided rules

1. **Composition.** The wire carries the seat's composed view. One composed change per settlement, keyed by the settlement marker: never member by member, never "the first member node". Attribution of perceived things to seat members follows Q1.
2. **Visible part only.** Effects publish their *visible* cells only. Hidden-cell retention (today sensory.py ~2384-2399 and the composition's footprint merge, audience.py ~76-117) leaves publication. The composition's last-seen cursors and absences (audience.py ~69-74) then have no publication use and are deleted from it. `seen_cells_added` leaves the wire: the client derives `seen |= visible`. Each memory fact has exactly one owner, the client.
3. **Keyed changes.** A record perceived before and after gets the event's change: residue (cell, material, contribution); condition uuid; item uuid; loadout slot; light source; effect.
   - Scalars carry their new value; cell sets go as packed added and removed masks.
   - **One generic fact** `ActorChangeFact`: rows tagged by a `ChangeField` enum, disclosed through one table (field → who may see it). No new fact class per change kind, and no longer `isinstance` chains.
   - Items split into look, profile and state; only the small state changes, field by field.
4. **Entering perception** (the composed view's transition) sends, read statelessly from the session fold as of the occurrence:
   - for cells: a packed mask, packed columns of current values, conditions, residues;
   - **every** object and connector touching the cells, including the empty case, so the client knows the set is authoritative;
   - for bodies: all changeable fields;
   - for items and effects: their current visible state.
   
   The client resets what it holds for those cells and records, then applies. "Touching the cells" is one leaf function, `placement_support_cells` (new, in `dnd/types/world_placement.py`), used by server and client. **Initialization uses the same entering functions**, so there is no second path.
5. **Static content once per (kind, id) per seat:** one sent set, updated from the final emitted update, never mid-walk. The client contract says static stores are never pruned.
6. **Nothing restated:**
   - envelope once, audience in the initialization;
   - spell declaration on the root only. Parity: a child is disclosed only together with its root (test it), so a child never needs a declaration its root didn't carry;
   - `SpellFact.application`, `cause_occurrence`, in-group `parent_lineage` and `PlayerNode.lineage` deleted;
   - `observer_position` only when it changed;
   - REMOVED sends `removed_positions` only;
   - an admission doesn't repeat the sensory contact;
   - `affected_tiles` and the per-seat spatial revision fields deleted.
7. **Both light levels** (objective and perceived) for perceived cells. **Per-seat occurrence numbering** kept. **Reconnect** by journal replay; the client's memory rules are deterministic and come with golden test vectors.

## 4. Architecture of the new pieces

All of these are data plus system functions: no behaviour on records, no managers, no lazy state.

- **The session fold is `CaptureCheckpoint`** (capture.py ~159), extended with the world facts and per-record state. `advance_capture` is its only writer, and the three holdings writers (capture.py ~838, ~386-394, projection.py ~1431) collapse into it. Snapshot builders are stateless functions over it.
- **Change records:**
  - frozen types in `dnd/types/actor_facts.py`;
  - **one** `match` over event kinds produces the change;
  - **one** `apply_actor_change` folds it for everyone: the session fold, the client reference fold and the AI knowledge fold;
  - the records live in the capture context keyed by event uuid, never on `Event` and never lazily.
  
  The AI-fold gate is "AI knowledge equal", not "AI fold code unchanged".
- **Native events carry the change, not the whole row (Q4).**
  - Residue and terrain writers record their keyed change.
  - Consumers of the whole `tile_states` rows (sensory_fold.py ~64-68, the `SensoryDelta` protocol, the AI) move to applying the change.
  - Light and effect patches are computed in the projector from the composed before/after the composition already holds (audience.py ~736-758). No native schema change there.
- **Seat knowledge** replaces `remembered: PlayerState`: a dataclass with only the allowed fields (perception composed and members, control, the static sent set, disclosed lineages, public cursors). The HUD, unchanged until E5, is one named field.
  - Projection, capture and application must not import `dnd/player/reduction.py`, guarded by an architecture test.
  - Composition leaves reduction.py: `apply_settlement(...) -> ComposedChange` is a frozen return, with its "before" in locals, and each settlement closes within its group.
- **Event-major projection:** one walk per event across all seats, not per seat. This is its own gated phase (E3a), with no escape hatch.

## 5. Phases

Dependencies: E0 → E1 → E2 → E3a → (E3-world ∥ E3-bodies ∥ E3-sensory) → E6. Each is a lane in its own worktree, merged into `codex/event-native-deltas` after its gates. A plan-adherence tracker runs throughout.

- **E0: harness and baselines** (after Q3).
  - **Seat layouts:** G1 one seat per faction (today), G2 one seat per character (the capacity worst case), G3 blue batched into seats of 5. The harness's `seat == 'blue'` checks (gallery_crowd.py ~866, ~913) become per-layout.
  - **A room re-entry case:** see, leave, close the door, reopen it, step in. Its bytes are estimated until measured.
  - **Oracles:**
    - **O1 (perceived equality):** at each op end, per seat, the reference is built **from the live engine** (each perceived record read through the disclosure functions), not from the new snapshot code. It is compared with the client fold restricted to the records **the client holds in currently visible cells** (catches ghost objects).
    - **O2 (replay):** a fresh process with a different `PYTHONHASHSEED` replays the seat's spool through transport resume. Its fold equals the live fold.
    - **O3 (baseline):** the perceived client states folded at the head are stored as data (not re-derived by the old reducer), and re-recorded after E1.
  - **Baselines:** G1, G2 and G3 bytes and ms, 3 runs, quiet machine.
- **E1: bugs fixable on the head, each failing first.**
  - Connectors read from init only (projection.py ~1224).
  - Stale initial light (startup fold lacks LIGHT_CHANGED/TILES_CHANGED).
  - Failing-first tests, without fixes, for the fold disagreement (temporary HP in `resulting_stats`, INTERNAL conditions) and the ghost layer of a destroyed equipped item. They turn green in E3-bodies.
  - Re-acquisition per seat and entered cells from the composed view are fixed by E3's design and keep their tests there.
  - The composition divergence (never reproduced) is covered by O1.
- **E2: change records.**
  - The residue and terrain writers record keyed changes, and their whole-row consumers move to applying changes (Q4).
  - `ActorChange` / `ItemChange` per §4.
  - **Gate:** published updates byte-identical (the wire doesn't change yet); AI knowledge equal; native events identical apart from the replaced fields, listed; sweep with the expected test changes listed up front; pyright 0 new.
- **E3a: seat knowledge and event-major projection.**
  - `remembered: PlayerState` is replaced by seat knowledge, with the reducer-import architecture test.
  - `CaptureCheckpoint` gains world facts.
  - Projection becomes event-major across seats.
  - **Gate:** published updates byte-identical, O1–O3, log appends byte-identical.
- **E3-world / E3-bodies / E3-sensory** (schema 16, one bump, lanes merged in order):
  - each family's deletions (lists in revision 2 of the design doc);
  - §3's rules;
  - the client reference fold's memory rules with golden vectors;
  - SDK regeneration;
  - the Godot note.
  - **Gate:** O1–O3 on G1, G2 and G3; log appends byte-identical; no regression in ms or bytes on any row; ≤100 KB on every row except Q2's named exceptions; the expected test changes listed and justified.
- **E5: HUD, decided H2-exact** (study: [stateless/hud.md](../event_native_deltas_2026-10-18/stateless/hud.md); runs in parallel from now).
  - **Why not H1:** the HUD's action, movement and ability values are computed when read and change with no write to the actor (Frightened's sight-dependent cap, paladin auras, spatial suppression, equip state). The writers are an open set, so H1 can't be exact.
  - **The change:**
    - One engine HUD publisher, called once per op at op end (session.py ~474, after the cost reset, before `end_cursor`) and once at startup.
    - It evaluates each player actor's sheet, minus the fields that already have events (HP, levels, spellbook, feature uses, prepared spells) and static fields.
    - It compares with that actor's last published sheet event, reached through a per-actor pointer the publisher owns (the `publish_owner_state` pattern, conditions.py ~2084-2110), and emits a keyed native sheet event with only the changed fields.
    - Initiative gets explicit native join/leave events (encounter.py ~458, ~475, ~527), filtered by perception like every fact.
  - **Deleted:** the per-seat HUD diff (projection.py ~2133-2171) and the `hud_snapshots` side channel.
  - **Gates:**
    - a differential test against base-commit recordings (every op's HUD fold equal);
    - an op-end oracle;
    - a one-caller architecture test;
    - sweep with the expected test changes listed; pyright 0 new;
    - bytes: Fireball HUD ≈5.1 → 0.3 KB, SG walk ≈10.6 → 2 KB (estimates, to measure).
  - **Size:** ≈+350/−200 lines, ~12 files.
  - **Against the rule, stated honestly:** the comparison base is the engine's own last sheet event, one per actor, not a per-seat client copy. For computed values it is the only exact alternative to whole sheets every op.
- **E6: exit.** Re-time every case on G1, G2 and G3, quiet machine, 3 runs. Every row over 100 ms or 100 KB is listed with what dominates it, and the human decides the next owner.

**Expected test changes (to list per lane):** about 70 test files reference fields this plan reshapes, so "0 new failures" means "0 unexpected". Each lane lists the tests whose expected outputs change, with the reason, before merging.

## 6. Risks

- **Composition** changes what a multi-member seat's client can show per character (Q1).
- **Re-entry bytes:** the room re-entry case, estimated at ≈12–23 KB (mostly wall placements); measured in E0.
- **Objects destroyed or moved while unseen** are corrected only on re-entry. `placement_support_cells` is the single definition, and O1 tests it.
- **Ordering:** updates stay one per occurrence. A fact arriving before its sensory child must not be lost (summon creation witnesses).
- **Spool size:** about 80–250 MB per seat estimated for a long game, against the 1 GiB per-seat default (config.py ~33), which caps game length. Logged; memory work is next refactor.
- **Old recordings** compare through O3's stored perceived states.

## 7. Reviews and tracking

The revision-2 plan gets one confirming pass from each reviewer, on whether the findings are resolved, before approval. Each lane runs its own antislop and antiOOP reviews at design time and at the end, and a plan-adherence tracker runs during implementation.

## 8. Decisions (2026-10-18)

- **Q1: member attribution per row, option (a).** Each contact, object and effect row carries the bitset of seat members who perceive it; cells stay composed. Measured on the dumped G1 updates:
  - per-character cell lists cost 2.9 / 18.8 / 34.0 / 14.2 KB (Fireball / Sleet / SG walk / Darkness-Daylight);
  - the row bitsets cost ~0 / 2.8 / 0.6 / 3.1 KB;
  - so (a) saves 3–33 KB per case, up to 8.4 KB in one update.
  - What is lost: the client can't tell which *cells* each character sees, only which creatures, objects and effects. The human: "a) seems good".
- **Q2: the combat log is counted separately.** Every gate reports log bytes and the rest apart. The ≤100 KB gate applies to the non-log bytes, and the log is handled later (human).
- **Q3: measurements run without asking** (human: "why do you even have to ask??").
- **Q4: decided (W)** ([study](../event_native_deltas_2026-10-18/stateless/q4_world_change_origin.md)).
  - The residue and terrain writers record the keys they changed, and completion fills in only those keys' after-values. The whole `tile_states` rows leave TILES_CHANGED. Everything else is already keyed.
  - One `match` in capture produces each event's change, and one `world_facts` function applies it to the session fold, the capture targets and the AI fold.
  - The capture diff (C) is a test oracle only; (S) is rejected (see the study).
  - Numbers: exact on 652/653 rows (the one mismatch is a light value the whole row carried 34 versions early); native −0.3 to −7 ms per op; native payload −71 to −93 %; wire unchanged.
  - Correction: only `world_facts.apply_world_fact` reads whole tile rows; sensory_fold.py ~64-68 reads effect and light rows.
- **`_world_update` today is 85–98 % sensory-driven** (re-observing objects at every member cell, per member event) and is deleted by the composed-entering rule. A mock of the replacement costs ≤0.9 ms per op.
- **Side lane, started:** skip settling observers for inert tile facts (measured: Magic Missile settlement 9.6 → 4.5 ms, digest and wire identical), with full recorder gates.

## 9. Review findings → resolution

| Finding | Resolution |
| --- | --- |
| antislop 1 (BLOCKER), antiOOP 6: remembered footprints, cursors, two owners | §3.2 |
| antislop 2: attribution undesigned | Q1 |
| antislop 3: O1 self-referential | §5 E0 O1 |
| antislop 4: O2 can't fail | §5 E0 O2 |
| antislop 5: O3 undefined | §5 E0 O3 |
| antislop 6: E1/E2 overlap | §5 E1 |
| antislop 7, antiOOP 1 (BLOCKER): escape hatch, fold owner | §4, E3a |
| antislop 8, antiOOP 4: E2 second path | §4, Q4 |
| antislop 9: combat log inputs | §2, gates |
| antislop 10: targets not gates | §1, §5 gates, Q2 |
| antislop 11: "0 new" impossible | §5 "Expected test changes" |
| antislop 12: mega-lane | E3 split |
| antislop 13: spell parity | §3.6 |
| antislop 14: deletion list, seen mask | §3.2, §3.6 |
| antislop 15: HUD wording | §2 |
| antislop 16: probe count, `seat == 'blue'` | Q3, E0 |
| antislop 17: estimate as fact | §6 |
| antiOOP 2: disguised replica | §4 seat knowledge, import test |
| antiOOP 3: change record home | §4 |
| antiOOP 5: isinstance chains, item compare | §3.3 |
| antiOOP 7: composition scratch state | §4 |
| antiOOP 8: static channels | §3.5 |
| antiOOP 9: "touches" helper | §3.4 |
| antiOOP 10: second init path, E1.6 | §3.4, §5 E1 |
