# Single-pass propagation: progress log

Plan: `agent_docs/plans/ENGINE_SINGLE_PASS_CHANGE_PROPAGATION_PLAN_2026-10-16.md`
(v3.6; approved 2026-10-17, §14 reviews folded in v3.6).

Worktree: `/home/tommaso/.codex/worktrees/single-pass-propagation/dnd_engine`
(branch `codex/single-pass-propagation` from `d13e6ad`). Agents don't commit.

Hard rules:

- One correct path.
- No old paths kept, no fallbacks.
- Breakage means the plan missed a case: fix it in the one path and record the
  plan correction here.

## Phase status

| Phase | Status | Notes |
| --- | --- | --- |
| P0a | ✅ done | worktree/env/docs done; 11 sensory/cache counters + 5 discovery counters (rows, emitted targets, aims, footprints, validations); GC harness `devtools/performance/gallery_crowd.py` loads (Fireball counts run passed); test cleanup running |
| PB1 | ✅ done (A, B, K fixed with failing-first tests) | stale tests: 69/69 known failures fixed (tests only, see STALE_TEST_REPAIR_2026-10-17.md); test_application_review.py pending human decision; crash fixes A/B/K pending |
| P0b | ✅ done (P0b-1 + P0b-2, all §1 rows) |
| P1 | ✅ done (commit 9944b4adb; gate below) |
| P2 | ✅ done (commit ebff512eb) |
| PD1a | ✅ done (commit 6beb44d87) | one footprint; footprint gate carried to PD1b |
| P3 (+PB2) | ✅ done (commits 6beb44d87, f3728625a) | every §6 row within 30 P per group |
| PB3 | ✅ done except L12 (protocol decision) | gas-trap fence test left for sign-off |
| Re-measure | ✅ done (timings + ranked residual terms) | P4b justified (route walk ≈1 s); P7 owns the top two terms |
| PD1b | in progress (core API, round 0 profile hooks, round 1 rule_error fan-out) | rows, legality, selection |
| PD1c | — | after D14 approval |
| P4a | partial (obscurement index, in 6beb44d87) | |
| P5 | — | |
| PD2 | — | session cache conditional |
| P4b | — | conditional |
| P6 | — | |
| P7 | partial (light-source deltas, in 6beb44d87) | |
| P8 | ✅ done except "stats snapshot on change" (not delivered, see log) | commits 36463af6c..3b50daaf5 on `codex/single-pass-p8` |
| PC | — | other repo; human |

## Log

- 2026-10-17: plan approved; worktree created on `d13e6ad`; environment synced;
  docs copied.
- 2026-10-17: human paused cast-plan implementation to bring available-actions discovery into scope. Decided: env use actions kept (reach-bounded) + move+use suggestions; no object attack targets; no global wall/object/position enumeration; AoE = one aim point per perceived creature with hit sets + legal region, free aim validated on demand; spells listed once with allowed levels; idea: single shared space scan per actor solving all spells by lookup. Three discovery studies running.
- 2026-10-17: stale-test repair done (69 pass in 6 s, verified).
- 2026-10-17: human decision: KEEP the movement destination list (reachability needs paths anyway, important for AI; its cost is package size). Fix only its compute overhead: cache key sorting all path costs on every call, per-destination path copies, per-destination OA exposure recomputation. Discovery studies: consumers/evidence done (LOS/wall enumeration = 77 s of 90 s instrumented), wall placement done; engine-core cost map pending.
- 2026-10-17: §14 antislop (13) + antiOOP (14) reviews and the whole-world redesign folded into plan v3.6 (PD1a/b/c split; legality one path via non-eventful hooks; one footprint; selection identity; PD2 = costs of kept things). Open human questions in §14.10. v3.6 re-reviews running.
- 2026-10-17: WSL crash killed all agents; test-cleanup agent and tracker resumed from transcripts.
- 2026-10-17: GC harness written and loading on the real worker path. First counts run (Fireball, cast by an ally by mistake, since fixed to the sorcerer): 926 full recomputes, 3,078 hazard-only, 1,578 event versions, 6 deaths as designed, 7.1 s native (counts mode, not timing-qualified).
- 2026-10-17: human answers: D14 approved; Q-W1 destinations = sight ∩ empty ∩ range; Q-W2 perceived preview; Q-W3 delete; Q-W4 objects from perception; Q-W5 yes; Q-W6 required ("any is bad in general"); order left to the plan → sensory first, PD1a before P3, PD1b after P3. Plan v3.7 (re-reviews folded; rules keep world access after the human's objection).
- 2026-10-17: P0a counts runs: Sleet cast 5,931 FR / 264 s, drop 5,901 FR / 31.7 s; Fireball (sorcerer) 8.7 s, 926 FR; godmode Choices miss 392.7 s (LOS 378.7 s, 148,567 validations, 209,734 emitted targets, 577 rows), hit 0.2 ms, Preview 3.6 ms, Command 6.9 s.
- 2026-10-17: test cleanup done: collect-only 5,915 collected / 0 errors (15 files adapted, 91 deleted, 4 orphaned support modules deleted; table in STALE_TEST_REPAIR). 57 kept tests fail on pre-existing issues (53: authored catalog references uninstalled `creature.player.sorcerer@1`/`fighter@1`; 1 AI trap-lever semantics by old class path; 1 conditions without name/description; 2 missing content declarations) — reported to the human, not fixed. P0a closed.
- 2026-10-17: PB1 done. A+B: `_resolve_activation_admission` latest wins for different content (same content keeps the potency rule); footprint moves (`SpatialCondition` and the full `AreaCondition` override) share `_begin_footprint_change`. K: `clear()` bumps every revision monotonically and clears the path cache; `create_rectangle` reseeds light contributions like `set_tile`. Lanes: spatial 25, surface/cloud/zone 500, grid/light/sensory 706 — all pass.
- 2026-10-17: P0b split (P0b-1 now for the P1/P2 gate rows; P0b-2 before P3) so P1 starts; P0b-1 ordinary runs started.
- 2026-10-17: **P0b-1 baselines** (ordinary = timing-qualified, pre-P1 snapshot; reports in `.runtime/single-pass/gallery_crowd/baseline_pre_p1/`):

  | Row | Ordinary total | Counts | Model (§6) |
  | --- | --- | --- | --- |
  | Sleet cast | 228.5 s | 5,931 FR | ~270 s (−15 %, edge) |
  | Sleet drop | 30.1 s | 5,901 FR | ~30 s |
  | Ice Storm | 9.6 s | 1,506 FR | 1,654 FR (−9 %), ~13 s (−26 %: per-FR constant fitted at V=6 is high) |
  | Fireball | 6.8 s | 926 FR + 3,078 hazard-only | ~816 + ~750 barrel FR (−41 %: barrel term overestimated → model correction) |
  | Caster Choices (47 spells) | miss 373.7 s, hit 0.2 ms, Preview 4 ms, Command 8.8 s | 148,567 validations | — |
  | Fighter Choices | miss 224 ms, hit 0.1 ms | — | — |

  P0b-2 smoke rows (counts, same snapshot): Spike Growth cast 11.6 s / 1,470 FR, drop 9.7 s / 1,440; Web 4.8 s / 540, drop 4.0 s / 512; Daylight over Darkness 5.7 s / 150; Darkness 3.7 s / 90; Cloudkill 2.4 s / 60; Grease 1.5 s / 180; Circle of Death 1.0 s / 7 FR + 4,013 hazard-only (7 deaths); Chain Lightning, Magic Missile, Holy Aura, Mass Heal, Delayed Blast < 0.7 s.
- 2026-10-17: **P0b-2 baselines** (ordinary ms / counts FR / hazard-only, pre-P1 snapshot, `baseline_pre_p1/p0b2_*`): Spike Growth 8,075 / 1,470 / 1, drop 7,105 / 1,440; Thunderwave→Spike Growth: install 5,699 / 1,062, Thunderwave 781 / 30 / 693; Web 3,732 / 540 / 5, drop 2,995 / 512; Darkness 2,805 / 90, Daylight 4,787 / 150; Cloudkill 2,245 / 60, drop 1,033 / 30; Circle of Death (7 deaths) 1,374 / 7 / 4,013; Grease 1,112 / 180; Chain Lightning 593 / 60 / 1,039; Holy Aura 525; Delayed Blast 207 / 30; Magic Missile 149 / 0 / 813; Mass Heal 38; caster step ~175 ms / 1 FR; turn handoff ~10 ms. Remaining §1 rows needing new actors/objects (Turn Undead, plate/vent, portal, Wall of Stone, summon retirement, Gust walk, Spirit Guardians walk) are added before P3.
- 2026-10-17: **P1 gate** (ordinary, timing-qualified, archive of 9944b4adb vs `baseline_pre_p1`): Sleet cast 228.5 s → 5.7 s (FR 5,931 → 90), drop 30.1 → 1.87 s (FR 5,901 → 60); Ice Storm 9.6 → 1.95 s (FR 1,506 → 4); Fireball 6.8 → 2.76 s; Spike Growth 8.1 → 0.37 s, drop 7.1 → 0.22 s (FR 1,470 → 0); Grease 1.1 → 0.18 s (FR 180 → 0); Web 3.7 → 0.53 s, drop 3.0 → 0.73 s (FR 540 → 0). Residue = per-cell hazard-only (e.g. Spike Growth 1,471), removed by P2's single tile fact / P3's single settle.
- 2026-10-17: P2 in progress: single reducer entry (both manual calls removed; D8 resolved: no APPEAR effect needs the field observed first, 1,227 zone/sensory/player tests pass); duration ticks take the hazard-only path (1 reducer pass, 0 FR); terrain install/release = one `TILES_CHANGED` fact (`GridMap.commit_tile_mechanics`, rows of `WorldTileState`, folded by `world_facts`, residue fear reads `get_affected_positions`); light = one fact per cause; `invalidate_spatial_caches` deleted → owner entry points (`commit_tile_mechanics`, `commit_entity_presence`, `spatial_condition_changed`, `commit_object_blocking`); private GridMap owner API made public (`commit_entity_membership`, `publish_entity_membership`, `publish_committed_spatial_event`, `publish_spatial_event`, `shift_observer_boundaries`, `validate_entity_position`); AST ban `tests/architecture/test_gridmap_private_access.py`. Sleet dousing's per-torch light facts collapse in P3 (group close settles pending lights). Found by P1: the first spatial condition on a map flips the propagation solver (PD1a's one primitive fixes it).
- 2026-10-17: **P2 gate** (ordinary, archive of ebff512eb; reports `gallery_crowd/p2_gate/`): Sleet cast 5.7 → 3.06 s (FR 30, hazard-only 31, versions 1,058 → 274), drop 1.87 → 1.56 s; Ice Storm 1.95 → 0.41 s; Spike Growth 0.37 → 0.15 s, drop 0.22 → 0.06 s; Grease 0.18 → 0.10 s; Web 0.53 → 0.18 s, drop 0.73 → 0.11 s; Darkness 2.8 → 1.43 s, Daylight 4.8 → 1.85 s; Fireball 2.73 s and Circle of Death 1.56 s unchanged (P3 rows). Full engine/player/architecture lane: 4,024 pass; 20 architecture failures all pre-existing at d13e6ad (frozen in `.runtime/single-pass/known_failures_architecture_base.txt`); 1 expected: protocol schema (regenerate with `devtools/export_player_protocol.py` at the PD1a/P3 commit).
- 2026-10-17: **P0b-2 complete** (rows built by sub-agent, pre-P3 snapshot ebff512eb, `gallery_crowd/baseline_pre_p3/`): Turn Undead 6 skeletons 387 ms / 31 FR; plate→gas vent 750 ms / 32 FR / 633 hazard; plate→3 portals 1,006 ms; Wall of Stone 3,217 ms / 337 FR; summon cast/drop 266/201 ms; Gust cast 575 ms then ~480–770 ms and 30 FR per caster step; Spirit Guardians cast 141 ms then ~1.1–1.5 s and 90 FR per 3-cell step (§1 assumed membership-only; anchored zone moves cost a full pass per observer per step → investigate in re-measure); round step 89 ms / 0 FR / 60 hazard (predicted 180 FR); Mass Healing Word 69 ms; first AI decision 1.86 s with 0 FR (non-sensory). Harness rows: `crowd_recipe` options (`undead`, `wall`, `damaged_party`, `blue_ai`), actor-named steps, setup steps, fixed dice, END_ROUND.
- 2026-10-17: **P3 in progress** (with PD1a delegated in parallel): group mechanism (`EventQueue.group`, `OpenGroup`, `GroupEntryKind`; the reducer records and settles once per observer at the outermost close, attaching settled deltas and the one pending light fact to the still-open root; GridMap holds light publication during groups), cold-oracle tests `tests/engine/test_simultaneous_groups.py`, entries at the convolution branch, zone install/move/removal, round step, Moonbeam cast exposure. Counts with groups: Fireball 30 FR / 0 hazard-only (was 194 / 3,263), 421 ms native; Circle of Death 7 FR / 23 hazard-only (was 4,013), 627 ms. Phase B: `HandlerGroupDispatch.AFTER_GROUP` handlers deferred and replayed in arrival order (concentration check split: no damage-event rewrite), architecture test `tests/architecture/test_after_group_handlers.py`; summon departures deferred to the group close. PB2 bugs: E Counterspell root-only, F Greater Invisibility root-only + root creation lineage, J no silent re-concentration mid-batch, N admit-before-slow, Q 10 geometry readers on objective positions, D Sleep/Color Spray pool spent only on admitted applications (per-target `_apply_target_application`), C fence keyed by (target, arrival/TURN_START/TURN_END), L8 Moonbeam exposure through `_admit_trigger(APPEAR)`, S `resolution_order_key` (no getattr). Deferred to PD1b: per-target state off `self.target_entity_uuid` (every `_apply` reads it; PD1b's selection carries targets). `requires_paths` / `_paths_dirty` deletion owned by P5 (path freshness by revisions).
- 2026-10-17: **PD1a done** (sub-agent; reviewed by an antislop/anti-OOP reviewer, findings applied: aim-major priming deleted, Gust zone takes the action's shape, direction validation restored, explicit shape parameter, footprint identity includes the source for source-centered shapes, one `cube_axis`). Gate (a) `tests/engine/test_aoe_footprint_parity.py` (26 spells, U1/U2 failing-first) and `tests/engine/test_propagation_line_of_effect.py` (150 rooms) pass. Footprints 7,938 → 6,364: the ≤580 gate is carried to PD1b (per-cell aims). Solver: native ray everywhere (outcome changes listed by the agent: corner grazing, holes/condition crossings now block, full-envelope reach, on-map cells only, caster counted). Wire: cylinders report `"ignore_barriers"`.
- 2026-10-17: **PB3** (`tests/engine/test_rules_deviation_fixes.py`, each case failing on the P2 snapshot first): L1 Hypnotic Pattern needs sight; L2 Silence thunder immunity; L4/L11 Slow and Mass Cure Wounds 6 targets lowest HP first (`lowest_hp_first`); L9 Daylight dispels only ≤3rd-level Darkness; I difficult terrain is a floor of 2; L6 Web lowers light one level (tile `dimmers`, non-stacking); M every zone turn trigger at EXECUTION (20 sites + `tests/architecture/test_zone_turn_trigger_phase.py`). M consequence: Nauseated ends at the turn end. L12 blocked on a protocol decision (half-cell centre). P recorded only.
- 2026-10-17: **P3 remainder**: shared staged loop `dnd/spatial/area_reach.py` (Fireball + `payload_blast`, barrier integrity + destruction lineage, no revision counter); entries for wall formation, Ice Knife burst, Glyph payload, `payload_blast`, nested batches, plate pulses, trap fire, portal transfer, material interactions (`resolve_interaction`, 8 emitters); phase B takes callables (`EventQueue.after_group`); scoped roll sharing for nested entries; group settlers (GridMap flushes its light fact without a reducer: fixed a lost light publication in observer-less worlds). Regressions found and fixed: Moonbeam activation spent the fence before the cast loop (L8); P4a obscurement index stale after removal on removed support.
- 2026-10-17: **P3 gate, counts mode** (FR / hazard-only per operation, 30 observers; baseline `baseline_pre_p3` in brackets): Fireball 30 / 0 [194 / 3,263]; Circle of Death 7 / 23 [7 / 4,013]; Ice Storm 4 / 26; Sleet cast 30 / 1, drop 30 / 1 [30 / 31 each at P2]; Darkness 30 / 1, Daylight over Darkness 30 / 1 [90, 150 FR at P0b]; Web 30 / 1 (Web now dims light), Grease 0 / 31, Spike Growth 0 / 31; Wall of Stone 30 / 0 [337 FR]; Turn Undead 0 / 30 [31 FR]; plate→gas vent 30 / 31 [32 / 633]; plate→3 portals 30 / 31 [1,006 ms, 90 FR]; Gust walk 1 / 60 per step [30 FR per step]; Spirit Guardians walk 3–9 / 90 per 3-cell move [90 FR]; Thunderwave→Spike Growth 30 / 0; round step 0 FR; summon cast 31 / 2, drop 30 / 1; Delayed Blast 30 / 2. Every row is within the §6 conservative "30 P per group". Fixes made for the gate: anchor loss inline / anchor movement in phase B (a destroyed trap no longer strikes inside its own group), one group per plate press, Daylight's install and dispel in one group, zone-membership/terrain facts read no occupancy (anchored zones no longer force a full recompute mid-step), and a group declares the facts that complete right after its settle (`OpenGroup.completes_after`) so observers do not settle a zone's own change twice.
- 2026-10-17: **Re-measure after P3** (ordinary = timing-qualified, archive of f3728625a, `p3gate_*_ordinary.json`; P0b baseline in brackets): Sleet cast 2.0 s [228.5 s], drop 0.89 s [30.1 s]; Fireball 0.79 s [6.8 s]; Ice Storm 0.41 s [9.6 s]; Circle of Death 1.08 s [1.37 s]; Spike Growth 89 / 41 ms [8.1 / 7.1 s]; Web 204 / 198 ms [3.7 / 3.0 s]; Grease 87 ms [1.1 s]; Darkness 1.20 s [2.8 s], Daylight 1.39 s [4.8 s]; Wall of Stone 576 ms [3.2 s]; plate→vent 263 ms [750 ms]; plate→3 portals 431 ms [1,006 ms]; Turn Undead 123 ms [387 ms]; Gust walk ~171 ms per step [~480–770 ms]; Spirit Guardians walk ~410–690 ms per 3-cell move [~1.1–1.5 s]; Thunderwave into Spike Growth 252 ms [781 ms]; summon cast/drop 276 / 211 ms [266 / 201 ms]; turn handoff 12–15 ms; first AI decision 1.81 s, then 0.2–0.7 s (non-sensory: discovery, PD1b). The caster Choices row was not re-timed (373.7 s pre-PD1b at P0b; PD1a counts 373 s): it is PD1b's gate.
- 2026-10-17: **Re-measure ranking** (profile mode, frozen f3728625a, sub-agent; shares × ordinary time, summed over Circle of Death, Sleet, Darkness/Daylight, AI decision, Fireball, Spirit Guardians walk; raw data `scratchpad/residuals/`). Owner phase in brackets:
  1. Audience view composition `apply_current_audience` ≈2.9 s, top-2 in every spell op (each sensory delta applied twice, projection + reduction; `max(owners)` per changed cell per member). This is Circle of Death's residue: its 7 death deltas cost 947 ms profiled vs 24 ms for the recomputes [P7].
  2. AI knowledge fold catch-up `consume` ≈1.35 s of the first AI decision (1,009 events replayed; `_refresh_world` sorts all observers per position) [P7].
  3. Directional FOV ≈1.05 s; `supercover_slope_order` re-sorts the same offsets per observer and quadrant [P4a: objective input shared once].
  4. Obscured route walk `get_optical_obscurements_on_route` ≈0.97 s (one ray per visible cell; 28 % of Sleet, 35 % of Darkness) [P4b: justified].
  5. Capture deep copy `_detach_retained_event` ≈0.8 s [P7 / PD2].
  6. Discovery ≈0.7 s in AI decisions (5,436 `attack_object_contact` calls per decision) [PD1b / PD2].
  7. Torch light fan-out `_update_light` ≈0.7 s (walk: 18 steps × 30 observers) [P4a light index / P5].
  8. Hazard refresh ≈0.56 s [P5].
  9. Rules ≈0.3 s: Circle of Death builds each save bonus twice (evocation.py:1855) [P8].
  10. Event store observer identification 8–9 % of Circle of Death / Fireball [P6].
  11. `prepare_sensory_delta` re-parses `"x,y"` light keys (11 % of the Sleet drop) [P7].
  Not material: the death chain itself (0.3 %), encoding (< 1.5 %).
- 2026-10-17: **PD1b in progress** (commits aedcfc17d core types, 2b838c8a7 WIP): one legality path (`_admission_error` final on BaseAction; `_family_admission_error` only on BaseAction/SpellAction; actions state their rule in `rule_error(scan, selection)`; `tests/architecture/test_admission_single_path.py`); copy-free discovery (`discovery_error` on a `replace`d selection, one `action_scan()` per `get_available_actions`); free-aim region rows (`PositionRegion`, `position_region`; empty `target_indices` + positions = free aim, validated at preview); AoE aims one per perceived creature. Caster Choices (counts mode, godmode, 47 spells): 392.7 s → 6.0 s; footprints 7,938 → 205 (gate ≤ 580 met); validations 148,567 → 15,977 (none eventful); emitted targets 209,734 → 11,260; rows still 577 (one per cast-level variant: "spells listed once with levels" pending). Round 2 (5 agents): canonical rule helpers in `spell_utils`, per-target reads from the event, field-setting `_validate`s into `_create_declaration_event`, `physical_access_error` overrides → `rule_error`.
- 2026-10-17: **P7 audience composition (first cut)**: `AudienceComposition.cell_owners` keeps the per-cell owner (seeded from `tile_observers` at composition start); `apply_current_audience` skips cells whose observer set did not change and keeps the current holder unless a higher-ranked member now sees the cell. Oracle `test_owner_handover_matches_the_cold_composition` (incremental = cold composition). Circle of Death profile: `apply_current_audience` 947 → 418 ms, operation 3.27 → 2.69 s. Remaining P7: capture deep copy `_detach_retained_event` (661 ms, 802 events × deepcopy), AI fold, light-key parsing.
- 2026-10-17: **Ranking correction (term 5, capture deep copy)**: attributed by event type with `gc.callbacks` (Circle of Death, ordinary, p7a snapshot): one gen-2 collection (441 ms) fell inside `_detach_retained_event` and was charged to 36 SavingThrowEvents; the copies themselves cost ≈230 ms (SpatialChangeEvent, SensoryUpdateEvent 79 ms / 466, WorldInitializedEvent 77 ms / 2). Whole process: 9 gen-2 collections outside capture = 1.74 s. So term 5 is ≈0.23 s of copying plus collector pauses that land wherever allocation peaks; collector tuning is not in the plan (reported, not changed).
- 2026-10-17 (after the WSL out-of-memory restart: five parallel agent pytest runs at 15–20 GB each; test runs are now capped with `systemd-run --scope -p MemoryMax=14G` and run on frozen snapshots). **PD1b exit items 1–2**: one admission path with one scan per action (`_admit`; the legacy `targeting_error` / `position_placement_error` / `physical_access_error` chain, `validate_requirements_for_discovery` and `StructuredAction._validate` deleted; handler admission is the named hook `handler_admission_error`, Summon only); `_apply_target_application` no longer mutates `self.target_entity_uuid`. **Perception leak fixed** (round 2 had moved checks into `rule_error`, which read the true map in discovery): `ActorScan.subjective` is the knowledge mode, every `action_scan(subjective=...)` states it, every scan reader passes `subjective=scan.subjective`, occupancy through `cell_occupied(scan, cell)`; fixed sites: connector passage, Blade Barrier/Forcecage/walls placement, Multiattack, touch contact, door closing, Conjure/Revivify destinations, Chain Lightning contact, Hide (unseen enemies), Naturally Stealthy cover, Forcecage push-outs; `tests/architecture/test_rule_knowledge_mode.py`. **Discovery**: Chain Lightning per-primary secondary pools deleted (§14.4; 14.4 of 21 s profiled), LOS regions open-or-not once per registered action with early exit, threat domains / per-cell hazard / fixed costs once per call in the path collector, AoE hit-set HP from `CreatureFacts.has_positive_hp`. **Sensory/P4**: snapshot route obscurement by membership instead of per-cell calls, batch routes in the origin frame, slope sort in C, center optical blocking cached per optical revision. **P7**: AI knowledge inverted observer indexes and precomputed adjacent offsets; audience contact holders (like cell owners). **P8**: 16 spells read the applied save bonus from the roll instead of rebuilding it.
- 2026-10-17: **Ordinary timings, tree after the items above minus the last three** (o1 snapshot; a test run overlapped, so noisy): Choices miss 1.65 s [373.7 s P0b], Command 698 ms [8.8 s]; first AI decision 1.08 s [1.81 s]; Sleet cast 1.74 s [2.0 s after P3], drop 785 ms [890 ms]; Fireball 806 ms [790]; Circle of Death 1.21 s [1.08]; Darkness 1.50 s [1.20], Daylight 1.18 s [1.39]; Ice Storm 558 ms [410]; Wall of Stone 551 ms [576]; Spirit Guardians walk 437–775 ms per move [410–690]; Gust walk 161–178 ms per step [171]. Darkness, Ice Storm and Circle of Death to be re-timed quietly before any conclusion.
- 2026-10-17: **Commits c217b0cde, b98543e50, 823a015ca, 0cc536211** (after the WSL restart). Ordinary timings at c217b0cde (single runs): Sleet cast 1.23 s / drop 1.12 s; Fireball 739 ms; Circle of Death 1.07 s; Darkness 1.02 s, Daylight 884 ms; Ice Storm 322 ms; caster Choices miss 1.75 s, Command 745 ms; fighter Choices 162 ms; first AI decision 1.17 s; Wall of Stone 597 ms; Spirit Guardians move 432–793 ms; Gust step 175–197 ms; Spike Growth 107 / 48 ms; Web 262 / 206 ms; Grease 85 ms. After the later commits (min of 3): first AI decision 955 ms; Circle of Death 634 ms (median 979); Fireball 669 ms. Full sweep at c217b0cde: the 69 failures already failing at 2b838c8a7 plus one (undeclared crossing rule contract), fixed in b98543e50.
- 2026-10-17: **Measurement method correction.** cProfile and counts mode both distort Python-call-heavy code (the boundary snapshot read 415 ms profiled vs ~45 ms real); a thread sampler is biased toward GIL-releasing syscalls (uuid4 showed 20 % but was 2,651 calls ≈ 3 ms). The reliable tools: a SIGPROF/ITIMER_PROF CPU sampler (`scratchpad/residuals/sample_ops.py`) and min-of-3 ordinary runs (`best_of.sh`); single ordinary runs vary by ±300 ms from collector pauses.
- 2026-10-17: **Found: residue splatter multiplies events (R1).** Every damaged creature's body response deposits blood/residue tile by tile; each new tile is a full condition-application lineage (4 versions + 2-version membership commit), each accumulation was its own tile fact. Stubbing body responses (measurement only): Circle of Death 1.15–1.23 s → 0.58–0.62 s and 1,298 → 542 versions; Fireball 739 → 624 ms (1,126 → 804); Ice Storm 322 → 276 ms (430 → 244). Done (0cc536211): accumulations are one inert tiles fact per splatter (1,298 → 1,054). **Needs the human:** the new-tile part is the per-tile condition model itself (one TileResidueCondition membership per cell, with amounts, contributions and connected-material fear). Collapsing it to one condition per splatter / per connected residue region (amounts per cell, one application, one fact) would remove most of the remaining ~500 versions per area spell, but changes the residue data model, material interactions and fear provenance.
- 2026-10-17: **Remaining large terms (CPU sampler, ordinary).** Sleet cast: sensory settle 56 % (routes 16 %, volume geometry 7 %, FOV 6 %, boundary snapshot 5 %), publication 33 % (audience folds 22 %, projection 18 %, current fold 11 %), UUID `__hash__` 8 % leaf. Circle of Death: engine apply 52 % (event registration/phase_to 22 %), publication 42 %, UUID `__hash__` + `__str__` 18 % leaf (diffuse; biggest single caller is per-version identity grants, D4/P6). First AI decision: knowledge fold 74 % (tile projections 28 %). **Needs the human:** "one fold per seat" (P7): each seat folds every delta twice (projection's private composition and the current state's composition, fed the same deltas); merging them crosses the "validate every seat before any current state changes" boundary.
- 2026-10-17: **Human decisions D15–D17** (plan §8): one residue condition per material for the whole map; one sensory fold per seat; spells listed once with castable levels, AI casts the base level. Order: D16, D15, D17. Also since the last entry: max HP reads the Constitution modifier directly (P8, 34cd5a9cf); a light update refreshes an observer's footprint only when its visibility or contacts changed (9b2d15713); audience membership through frozen sets (919b0c036). Min-of-runs now: Sleet cast 1.13 s / drop 0.93 s; Circle of Death 0.69 s; Fireball 0.67 s; caster Choices miss 1.17–1.65 s, Command 0.65 s; first AI decision 0.96 s; Gust step 146–161 ms; Spirit Guardians move 0.40–0.71 s.
- 2026-10-17: **D15 done (f7e4736fa)**: one residue field per material; event versions Circle of Death 1,298 → 632, Fireball 1,126 → 564, Ice Storm 430 → 274; min-of-3 Circle of Death 694 → 514 ms, Ice Storm 289 ms, Fireball 646 ms. **D17 done (56baf7fd5)**: spells listed once with castable levels (`cast_levels`; the selection's `cast_at_level`; extra targets validate at that level; AI keeps the row's level); caster Choices miss 1.65 s → 0.70 s. Protocol schema + Python SDK regenerated; TypeScript `contracts.generated.ts` left for the client repo (PC). **D16 deferred**: the client fold also folds admitted observations and terminal departures between deltas (contact inserts + overrides), the projection's fold does not, so one shared composition needs the projection to fold those too, in order (changes the projector's private senses used for disclosure); smallest gain of the three.
- 2026-10-17: **§4 scoped delta and fold costs (e1a752e09..0e09bbd35).** AI knowledge projects each visible tile once per consume (first decision 0.96 → 0.53 s). One scoped sensory pass for facts that leave sight geometry intact (cells, contacts, hazards the facts name; center objects no longer bump every covering field; propagation reaches only fields with non-visual senses): Fireball full recomputes 30 → 6. Own conditions change no hazard verdict under a current field; group settlements include the zone change that completes after the group (the gallery oracle caught stale ally hazards under Spirit Guardians before this). Footprints kept per delta scope; emitter revisions logged in order, a scoped pass re-observes only revised, lighting or attached emitters (P4a). Audience folds: per-cell rank order kept (no n² re-ranking), effect observations and light rows joined once (n-way). Gallery oracle added (scratchpad `oracle_probe.py` / `pub_oracle.py`): after every op, settled views, light descriptors, footprints and reverse indexes equal a cold recompute; seat views equal cold compositions — clean on every case. Sensory share now: Circle of Death 31 ms, Fireball 45, Ice Storm 28, Sleet cast/drop 490/326, Gust ~45/step. Ordinary totals: Fireball ~390 ms, Circle of Death ~436, Ice Storm ~240, Sleet 1.1 s / 0.65 s, Gust step ~115, Spirit Guardians step ~300–350. Tried and reverted: inverse route-shadow index for obscurement routes (exact but slower: near cells' shadows dominate at 40-cell radii). Publication ≈ half of every row; next: D16 one fold per seat.
- 2026-10-17: **Vectorization and per-read costs (2d315ac5a..4d04c5d22; numpy approved by the human).** Supercover route table (every line within 40 cells, equal to the scalar line row by row); obscurement routes and volume entries gathered and OR-reduced per observer (equal to per-route intersection on random worlds); cells classified by (range, obscurement bits) with batched distances. `SpatialChannel.OBSCUREMENT` and an observer obscurement revision: obscuring zones no longer clear physical FOV/directional caches, and full recomputes shift the retained boundary snapshot whenever optical/propagation geometry is unchanged. Hazard-capable prefilter (cells with a tile condition, hazardous residue, object or spatial condition). Engine models read pydantic private attributes directly (~350 → ~40 ns; no private default is a descriptor). Identity grants from the reverse contact index, memoized per creature and cell between contact/subscription changes (0 mismatches vs the per-subscriber scan over ~7,600 versions). AI knowledge folds deltas in place (equal to cold replay at every consume). Navigation direct-path preference memoizes hazards, exits, transitions and edge costs per call (equal on every real call). Dependent observers tested once per batch. Review fixes: no getattr in the effect join; the emitter change log has no trimmed fallback. Test `tests/engine/test_scoped_sensory_settlement.py` (plan §7 oracle, default lane, ~1 s; fails at 557ea18ed). Min-of-3 ordinary (before the AI/navigation/grant-memo commits): Sleet 500 / 484 ms, Fireball 346, Circle of Death 382, Ice Storm 207, Gust step ~100, Spirit Guardians move (3 steps) 248–308, first AI decision 313, caster Choices miss 252, Command 359. Pending human: D16 option A (drop the server mirror's duplicate sensory fold) or B. `tests/manual/test_160_content_pack_loader.py` (13) already failed before this work.
- 2026-10-17: **P4b obscurement delta measured and not adopted.** A reroute path (every route's crossed obscurement re-gathered and compared with the field's; only changed cells re-resolved, then the scoped pass) was exact on the gallery oracle and replaced all 30 Sleet full recomputes, but ~53 % of each observer's cells change under Sleet (26.6k of 50.5k), and the scoped per-cell work costs what the full recompute does: cast 508 / drop 737 ms, unchanged. Reverted (no gain for the complexity). Also since the last entry: shared capture lineage graphs per operation (P7), plain object observations memoized in the projection (3,244 rebuilds for 3 changes under Sleet), identity grants memoized per creature and cell. Sleet drop carries one gen-2 collection (~266 ms over ~660k tracked objects); cast none. D16: human asked why the mirror exists; the server reads only content, audience and HUD from it (worker.py 89/94/164) — proposed option C: drop the mirror fold from the live path, read bookkeeping from the outgoing update, move the replica check to tests. Awaiting the human.
- 2026-10-17: **P8 value layer (36463af6c, ae123149f, f6e381846, 3b50daaf5, branch `codex/single-pass-p8`).** (1) *Min/max once per read:* each channel reads its additive total and its bounds once (`bounded_score`); `ModifiableValue._score` clamps each channel and the aggregate with those same bounds, the passive scalar path likewise, through one `_clamped`. Before, static constraints were walked up to 3× and contextual constraint callables evaluated up to 3× per read. Observable only to stateful callables: one evaluation per read (the test pinning 3× now states once), and contextual bounds evaluate min before max (was max first). The only production contextual constraint (Frightened zero speed) is pure. (2) *Bounded breakdown cache:* `ContextualModifier` keeps the latest evaluation only (`breakdown_result(source, target, lineage)`), not one string-keyed entry per lineage copied with every value copy. (3) *Snapshot:* `Health.damage_affinities()` evaluates resistance once for the stats snapshot, the actor fact builder and the AI projection (were 13 `get_resistance` reads each); counter `health.resistance_evaluation`. **Not delivered: "stats snapshot on change"**: the snapshot is cheaper, still recomputed at each commit. **No result caches** (passive perception, max HP, resistance, snapshot): no owner-write invalidation set is complete, because `contributions_active()` reads world state at read time: owner registry membership (conditions, items), equipped item and its owner (Devotee's Mace), anchor spatial suspension (area conditions), Paladin aura faction and grid distance between two entities (a move of either changes the value), plus arbitrary contextual callables. **Gate** (exact call counts inside the measured operation, pre-P8 → P8): resistance evaluations Circle of Death 252 → 36, Fireball 145 → 25, Gust walk 26 → 2, AI decision 26 → 2; passive-perception evaluations unchanged (30, 30, 605, 369); channel min/max evaluations −60 % (Gust 64.8k → 25.9k), contextual constraint evaluations −60 % (Gust 3,025 → 1,210). Per read: score 2.17 → 1.46 µs, max HP 19.0 → 13.4 µs, snapshot 205 → 127 µs, passive 16.5 → 14.5 µs. Interleaved min-of-3 ordinary (slow machine period): Circle of Death 793 → 760 ms, Fireball 739 → 727, Gust step ≈ equal (112–125 vs 111–123), AI decisions 361/133/115/407 → 337/114/108/387. Differentials: 307k value reads and 24k passive reads equal to the pre-P8 implementation over all seven gallery cases; breakdown latest-only vs old dict equal on 47 gallery and 207 test reads (5 contextual rows). **For the human:** 98 % of passive-perception evaluations come from sensory `_field_is_current`, called up to 3× per observer per fact (`__call__`, `_can_scope`, `_reduce_observer`), ≈1.2 ms per Gust step; the gallery has no concealed hazards. Not changed (sensory.py, outside P8). The largest value-layer cost is the per-save target binding: `saving_throw_bonus` with an opponent ≈1.2 ms, about half `set/clear_target_entity` over every value of both entities, ~37 % deep copies; out of P8. `composed_passive_score` still falls back to the composed path for uncommon inputs (pre-P8 second path, untouched).
- 2026-10-17: **Sleet studied from first principles; plan v3.8–v3.11 (D18, D19, D16-C).**
  - **Human targets.** No operation over 100 ms (≤50 acceptable, ≤20 / ≤16 goal), no update over 100 KB, and GC treated as an alarm.
  - **Area makes no difference.** Darkness (~28 cells), Cloudkill (~50) and Sleet (~200) all cause 30 full recomputes over the same 50,535 observer-cell pairs: obscurement is a per-cell filter over the whole wall field of view.
  - **Payloads.**
    - The blue seat receives 1,690,695 B on the Sleet cast and 5,177,992 B on the drop.
    - `observed_changes` is 51 % of the cast payload and derivable.
    - The drop is 76 % re-sent bodies: 234 re-acquisitions of 20 actors, caused by the `| acquired` term in `_capture_actor_admissions`.
  - **Spike** (codex/single-pass-arrays-spike 55b97682b, devtools only).
    - Vision is computed as a sense × interceptor table applied as arrays. It matched today's results with 0 mismatches over 750 observer states across 7 cases.
    - Per observer: 0.75 ms median against 7.9 ms; vision alone is ~0.12 ms, and the rest is per-target Python.
    - Sleet over 30 observers: ~20 ms (cast) and ~19 ms (drop), against 248 / 170 ms, plus a 5 ms grid build.
  - **PV1a** (sensory, GridMap and rules readers) has started in codex/single-pass-pv1a.
  - **Merged:** PD1c (whole-world scans → bounded owners; sweep r9 0 new failures), P8 (value-layer reads, resistance once per snapshot), P6 (handler reads once per event, no completion lookup, identity grants from the memo; per-seat transcripts identical on 7 cases).
- 2026-10-17: **Merged PD2, P5, P7** (sweeps r10 and r11: 0 new failures; r12 for P5 + P7 running).
  - **PD2.**
    - Choices are projected from native rows without dump/validate. On a caster miss: `model_dump` 1,998 → 1, `model_validate` 2,198 → 201, `deepcopy` 3,460 → 1,722.
    - The preview is cached as its frozen projection; choices are encoded once, and a cache hit takes 5.6 → 0.16 ms.
    - The AI profile key has no per-epoch dumps.
    - Movement-list collector 82 → 51 ms.
    - Not adopted: U5 (inexact: equal-length path choice). Open: free-aim declared zones stop at the first legal point (~22 ms of the miss), `BaseCost.model_validate` passthrough, retained-graph release.
  - **P5.**
    - Cache entries keep their read boxes, and writes drop only the entries that intersect; wipes go to 0 (Fireball 12, Gust walk 29, Spirit Guardians walk 37).
    - Path keys hold every requester input. Navigation and entity caches use per-chunk traversal stamps, and the barrier set is maintained.
    - Exact (every kept answer equals a cold compute over 92 ops); timing unchanged, since the remaining misses are new origins.
    - Open: `requires_paths` / `paths_dirty` removal (a wire field; goes to PV1b / PT).
    - **For sign-off:** lit areas behind a newly formed Wall of Stone now go dark (matching a cold solve).
  - **P7 (D16-C).**
    - The server mirror is deleted; `projection.remembered` is the one per-seat fold.
    - One shared capture checkpoint with no history refold (summon_retirement used to refold 2 × 3,572 events per seat). Replica test: `tests/player/test_emitted_update_replica.py`.
    - Wire output byte-identical on 22 cases.
    - Publication, loaded: Sleet cast 734 → 201 ms, drop 349 → 230 ms, Fireball 564 → 468 ms; later AI knowledge updates 25 → 3 ms.
    - GC alarm: a ~300 ms gen-2 pause still lands inside the Fireball and Circle of Death publication.
  - **Conflict resolution (P5 × PD2, `entity.py` `_position_preview_facts`):** PD2's per-call snapshot was kept. Its context still keys `movement_revision`, which P5 had dropped: correct, possibly over-invalidating.
  - **Earlier sign-off items (PD1c).** Stone-escape order; Opulent Revival no longer revives off-grid; Turning, Preserve Life, Sunder and Opulent now process targets in (position, uuid) order; the Forcecage preview no longer checks `is_deployed` on perceived contacts.
- 2026-10-17: **Pre-existing perception bugs found by P5, assigned to PV1a.**
  1. Removing a non-wall optical zone (Wall of Fire, Wall of Thorns) does not re-light, so the light stays stale and observer views are wrong.
  2. `commit_entity_presence`'s anchor scan assumes that no entity-anchored zone blocks optics, and nothing checks it.
  Both get failing-first tests.
- 2026-10-17: **Human sign-offs.**
  - Wall of Stone: lit areas behind a new wall go dark. Approved.
  - BG3 Haste eligibility: approved.
  - The walk contact change rides the zone fact instead of the light fact: fine.
  - Human: focus on engine speed, not rules minutiae. From now on, rule-level side effects of speed work are logged here, not raised one by one.
- 2026-10-17: **PD1b close-out (branch codex/single-pass-pd1b, 6f273d251..HEAD).** Q-W6 (no actor in profile hooks). Discovery admits AoE aims and declared positions through the one path. Variants -> `facet_domain` + `discovery_selections` + final `discovery_forms` (shallow read-only forms); every variant/template-name/facet/`selection_preview_error` override, `generate_variants`/`_create_variant`/`at_cast_level`, the name resolvers, `_bind_executable_action`, `apply_from_control` and `RestrictedActionGrantProvider` deleted; rows perform the registered action by the uuid `ActionSelection` through `Entity.perform`, the only `.apply(` in `dnd/` (AST test). Contract-less position zones are region rows. Gallery: gate (b) caster 4,250 selections / fighter 451, 0 refused, 0 admission cancels in 57 + 11 executed samples; caster Choices 0 event versions, 1,972 admissions, 936 emitted targets, 205 footprints, 123 rows, LOS collector 8.8 ms (counts); ordinary min-of-3 Choices miss caster 245 ms, fighter 114 ms; walk rows 1 scan per action. Wire unchanged (index selection, one row per facet combination, next vertices): listed for sign-off.
- 2026-10-17: **PH-1 on Sleet, measured over 3 runs each.** The cast still carries one gen-2 pass: base 323–358 ms, PH-1 299–353 ms, within noise. The heap is 9 % smaller, but the trigger (~112K young survivors per op) is unchanged.
  - Human: "you can't just push costs out of course total cost is still important". The AI knowledge advance runs in the op and is counted there (the post-reply move was reverted); PV1b owns its cost.
  - **Unowned term found:** Sleet zone install (terrain per tile, condition application models, dousing items), ~50–75 ms loaded. It goes to a PV1a follow-up after PV1a merges (same grids).
- 2026-10-17: **PR findings.**
  - **Player-visible bug, pre-existing, to fix separately:** `actions.py:2272` `set_context` replaces the attack context set at `entity.py:3425`, so `attack_ability` is missing during a real weapon-attack roll. Reckless Attack's contextual advantage never applies. PR preserves the behaviour exactly.
  - **First-use pydantic schema builds inside ops** (`defer_build` kept): Fireball 12.6–14.6 ms, Ice Storm 7.3–8.3, Circle of Death 2.7–2.9, once per process per model.
  - The value-read lineage only keyed a "latest evaluation" slot; it is deleted with the frozen reading.
- 2026-10-17: **PV1a, rule-level side effects** (logged per the human's direction):
  - perception radius capped once at 80 cells (400 ft);
  - entity-anchored optics blockers now raise (the construction invariant P5 flagged);
  - the mover's contact change rides the zone fact.
- 2026-10-17: **Merged PT's AI knowledge system (AIK).**
  - One system owns every assignment's knowledge, advanced at batch dispatch (in the op); reads advance their own assignment.
  - The cold fold runs at assignment start. The whole-history pull and the lazy branch are deleted.
  - Exact against base (every field at all 10 reads); decisions and wire identical.
  - **Residue fix:** TILES_CHANGED signals every tile it writes, so seats now receive the blood / oil rows they missed (choices_caster Command: amber 368,208 → 407,733 B).
  - **First AI Advance: 346 → 185 ms.**
  - Fold cost in the op per 26-observer AI side (owned by PV1b): Sleet cast 68–84 ms, drop 59–62, Fireball 40–55, caster step ~2.
  - Open:
    - batch-callback errors are logged by `_dispatch_event_batch`, not surfaced (existing passive-observer behaviour);
    - a rebind re-folds full history;
    - the summon-cast cold fold (30–39 ms) grows with history.
- 2026-10-17: **AIK follow-up merged.**
  - Batch-callback errors are fatal.
  - A CREATED assignment raises at decision instead of auto-starting.
  - `open` and `unbind` are strict.
  - Edge left open: a summon committed while `has_runtime_agency()` is false is never started, and would raise if it got a turn. Not reached by any test.
- 2026-10-17: **Regression found after the PV1a merge (fixed in PV1a-2, item 0).** Move rows got slower:

  | Row (native) | Before PV1a | After PV1a |
  | --- | --- | --- |
  | Gust of Wind move | 51–63 ms | ~152 ms |
  | Spirit Guardians move | 123–166 ms | 409–433 ms (first move 649 ms) |

  - Cause: the one settlement path fully recomputes ~30 observers' views on every occupancy change, though occupancy only feeds contacts.
  - Fix: stage dependency inside the one path. The view is f(walls, obscurement, light, position, senses) and contacts are g(view, occupancy, target facts); a settlement recomputes only the stages whose inputs changed.
  - PV1a's report did not include move rows; integration timing should have caught this before the merge.
  - Also: the gen-2 pause (~260 ms) now lands inside Sleet's event construction in all 3 base runs.
- 2026-10-17: **Sweep r17 (PV1a merge): 10 new failures**, all in PV1a's code; fix owned by PV1a-2 item −1.
  - Cold-runtime counters `perception_revision` / `_identity_grants_revision` are not falsy (5 pack-loader tests).
  - D3 regression: a duration tick re-solves observers.
  - The terrain tile-fact count changed.
  - Creator-object discovery order (×2), and dead-target filters in discovery.
  - End to end at 859a48752 (one loaded run):
    - Sleet cast 539 ms (native 336 with gen-2 inside, publication 180);
    - Fireball 605 ms (native 441 with gen-2);
    - Spirit Guardians moves 533–781 ms (native 423–668);
    - AI decisions 113–189, with the acting decision at 757 ms (gen-2).
- 2026-10-17: **Merged PW (71242cb61) and PV1a-2 items −1 and 0 (782fb01be, b70e21b31). Sweep r19: 0 new failures.**
  - **PW.** Bodies and items are patches; `observed_changes` is off the player wire; the HUD is sent as patches; the combat log is flattened; versions are identified by occurrence index; player schema 12.
    - Largest seat update: initialization 20.4 → 5.2 MB, Sleet drop 5.17 → 1.14 MB, Cloudkill drop 7.5 → 0.82 MB, Fireball 1.02 → 0.36 MB, end-turn ~98 → ~6 KB.
    - Every cast and move is still over 100 KB (per-observer cell and contact lists → PV1b).
    - Publication: casts much faster (Fireball 443 → 165 ms); drops and walks 10–20 % slower (PV1b investigates).
  - **PV1a-2 item −1:** the cold identity-grant memo (cleared at every perception write); contacts in evidence order; `test_eb_09_008` now expects the evidence order (the old expectation was set iteration order).
  - **PV1a-2 item 0:** the view split into sight and light stages by declared inputs, and passive perception read before the settlement's world (fixes a stale contact table under nested placement). Sight solves per move: Gust 90 → 1, Spirit Guardians 270 → 3. Move ms are not yet improved: contacts, fixtures and emit still run per observer.
- 2026-10-17: **Fully merged head bea589ae9** (PR, PV1a-2 move work, PS schema builds merged).
  - One loaded run per case. Baseline values are 7f836e17b medians.

    | Row | Baseline ms | Now ms | Without the gen-2 pass |
    | --- | --- | --- | --- |
    | Sleet cast | 513 | 577 | ~370 |
    | Sleet drop | 769 | 314 | 314 |
    | Fireball | 323 | 514 | ~300 |
    | Circle of Death | 334 | 496 | ~274 |
    | Ice Storm | 203 | 364 | ~162 |
    | Gust move | ~95 | ~136 | ~136 |
    | Spirit Guardians move | 233–308 | 355–394 | 355–394 |
    | Choices miss | 252 | 173 | 173 |
    | Caster Command | 668 | 313 | 313 |
    | AI first step | ~300 | 152 | 152 |

  - Every run carries one gen-2 pass (202–222 ms) in one of the first sizeable ops after Start. The worker's `gc.collect(); gc.freeze()` runs at boot, before Start creates ~540K objects.
  - Moves are still slower than baseline (PV1a-2: one settlement per step; the human: "seems okay").
  - Publication is now 130–280 ms on casts (PV1b).
  - Nothing is under the 100 ms ceiling yet.
- 2026-10-17: **PS merged.**
  - Schema builds happen at creation: ~250 `creates` declarations, AST-checked, 0 in-op builds across 31 cases.
  - Tiles have no private default factories (battlefield build 658 → 538 ms).
  - Assembly deploys as one group: Start ~8.5 → ~5.2 s, seat initialization 4.3 → 1.6 s.
  - The birth fact is built once less.
  - **Finding:** the seat merge (`audience.py:_contacts`) ranks a multi-observer seat's contact by observation cursor, so the merged contact's `special_senses` depends on event history order, not on state. Grouped deploys flip it for two torches in turn_undead. Proposed next-phase fix: a state-based merge (union of the seat's observers' senses).
- 2026-10-18: **Integrator decision, logged per the human's "log, don't raise": a move step settles perception once (PV1a-3, 753daa151 / 4c4080606).** This supersedes plan §5.2's "each Move step settle per fact" and "Move steps aren't groups".
  - An arrival opens a MOVE_STEP group; its zone moves and lights settle once per step, never across steps.
  - Effects:
    1. one sensory update per observer per step, caused by the arrival (Spirit Guardians 180 → 90 per move);
    2. a light consumer reads the settled step, in every group;
    3. phase-B work deferred by a joining zone move runs at the step's close.
  - Per-step and per-op observer state, objective events and the cold oracle are equal on 7 cases.
- 2026-10-18: **Event-version census (Fireball, 564 versions, 193 lineages).**
  - 371 versions are intermediate phases. Rules fetch 8 of them, handlers run on 12, and 97 are a child's parent.
  - 273 (48 % of all versions) are used by nothing except the machinery (`phase_to` fetching the previous version) and the iterating consumers (capture's version rows, the AI's open-events map).
  - Next (integrator, after P7b merges): lazy version materialization. The current version stays in a per-lineage slot and is stored only when a child, a handler, a rule fetch or an iterating consumer needs it.
  - Then area-effect batching: Fireball has 10 blood-residue deposits from damage applications and 5 item-destruction object changes, each its own lineage × 4 phases.
- 2026-10-18: **P7b merged (ddc108493), with PV1b (f7d644c60) and PV1a-3 (9687bfa43), in the int2 copy.**
  - P7b rows 1–3: stored versions are frozen, capture holds them by reference, and grants are shared when unchanged. Fireball publication 130.5 → 89.9 ms, young survivors 61K → 45K (agent medians at its base).
  - Row 4 (141 equal WorldTileState rebuilds at completion) stays: a deferred removal fact is published after light writes, so the earlier state can't be reused.
  - Logged rule-level differences (test-built events only):
    1. Earlier versions that carry a pre-set combat log no longer get the completion's `sub_entries` written into them afterwards.
    2. The Greater Invisibility check's log is on its completion, not also on the stored EFFECT version.
  - Logged bug, pre-existing: about 30 `phase_to(..., update={"condition": self})` calls leave a stray `update` key in the version's `__dict__`.
- 2026-10-18: **Lazy version materialization measured and dropped (integrator).** Prototype saved as a scratch patch, not committed.
  - Fireball at the P7b head, cProfile: storing all 564 versions is ~35 ms profiled, about 15 ms unprofiled out of ~226 ms. Over half of that is the per-version grant computation (`_compute_identified_entity_observers`, 564 calls), which a held version still needs.
  - Consumers iterating versions are cheap: `iter_events_since` 0.2 ms, `get_events_by_lineage` 0.3 ms.
  - The prototype stored 514 of 564 versions, and the time it saved was within noise.
  - It changed AI behaviour: a held version stored later lands after its lineage's later versions in the occurrence index, so the AI's open-events map saw versions out of order. ai_decision ran 1 op instead of 4.
  - The settlement multiplier is already gone: Fireball emits 30 SensoryUpdateEvents (one per observer), not one per spatial lineage. Residue and item-destruction lineages each cost their own rule work, ~4 ms all together.
  - Conclusion: event volume is not a remaining multiplier. The lazy-version idea was the integrator's (census entry above), not a plan item, and it would have been a lazy store against §6a; it is dropped.
- 2026-10-17 (logged late): **Worker GC policy (9568bffbc), human decision** ("i am fine with 1-3"): no automatic collection inside requests; after each reply, collect that request's survivors and freeze them; cycles are printed as an alarm; EndGame unfreezes and collects. The gallery times the post-reply collection per op as `collect_after_ms`.
- 2026-10-18: **Open from PV1a-2/PV1a-3, not done:** 2-D batching of the light stage, hazards, fixtures, emitter lit words and emit (only contacts are batched); the emit still builds the pydantic payload; the mover's own wall FOV is ~4 ms per step. PT navigation as a cost grid is not started.
- 2026-10-18: **Long game (50 turns, blue AI) did not finish:** stopped by its 60-minute timeout with no report; RSS 8.8 GB at 47 min; every AI advance printed one 15-object cycle (tuple/function/cell, one runtime type). Memory retention is the next refactor (human).
- 2026-10-18: **PH-2 parked, not merged** (branch ph2b; step-2 review of 380e7c484 done, step 3 unfinished; the implementing agent stopped at the usage limit).
  - Review found no accidental mutation of owned records, and every old combine site goes through `composed()`.
  - Needs the human's decision: a single value used to be read live; `parts()` now snapshots its rows when called (opponent-side reads and single-value damage packets: equipment.py:579/:1369, spellcasting.py:633, paladin.py:207, consumables.py:142, traits.py:795). EB-02-010 was rewritten to the snapshot behaviour but is still named `..._read_live`.
  - To fix before merging:
    - `with_rows` gives extra rows the last part's normalizer, and dedupes on only one path.
    - `remove_all_modifiers` makes a read return `normalizer(0)`.
    - `_validated_parts` has a silent fallback.
    - `value_bounds`, `outgoing_advantage` and `value_resistance` are second mechanisms used only by tests.
    - 57 temporary `parts(ModifiableValue(...))` records still register (a pre-existing leak).
    - The `sort_keys` change in gallery_transcript.py belongs in its own commit.
- 2026-10-18: **Exit re-time at b1ce2a00c (+ ff37e2a29 for gas_vent_plate).** 31 gallery cases, 3 ordinary runs each, no other load; full table in scratchpad `logs/exit3_table.md`.
  - **GC.** 0 collections inside any op. Post-reply collection: median 1–11 ms; the worst is the caster's Choices miss at ~70 ms. Every Start prints a ~11.9K-object cycle alarm (runtime-created functions, cells and types).
  - **Fixed during the pass.** gas_vent_plate failed on the merged head: `projection.py:570` still used `in` on a packed mask (PV1b). Fixed in ff37e2a29; the case now runs at 95 ms.
  - **Over 100 ms (median total; native / publication):**

    | Op | ms | Native / publication |
    | --- | --- | --- |
    | Wall of Stone | 225 | 169 / 48 |
    | Sleet drop | 211 | 60 / 140 |
    | Daylight | 210 | 66 / 134 |
    | Choices caster command | 195 | — |
    | Cloudkill drop | 188 | 48 / 131 |
    | Spirit Guardians moves | 169–189 | 110–127 / 51–55 |
    | Round Sleet | 183 | 81 / 92 |
    | Fireball | 177 | 100 / 68 |
    | Circle of Death | 175 | 95 / 70 |
    | Sleet cast | 172 | 79 / 83 |
    | Choices caster miss | 168 | — |
    | AI decision, 1st | 144 | — |
    | AI decision, 4th | 262 | — |
    | Cloudkill cast | 112 | — |
    | Ice Storm | 111 | — |
    | Portal plate move | 106 | — |
    | Darkness | 101 | — |

  - **Seat updates over 100 KB:** 22 ops. The largest are Sleet drop 615 KB, Daylight 502 KB, Cloudkill drop 484 KB, CoD 330 KB, Fireball 327 KB, Sleet 321 KB, SG moves ~230 KB and Wall of Stone 223 KB.
  - **Everything else is ≤100 ms.** Gust moves ~75, caster steps ~53, end turns ~9, single-target and small-area spells 20–90.
  - **Against bea589ae9** (single loaded runs, without the gen-2 pass): Fireball ~300 → 177, CoD ~274 → 175, Ice Storm ~162 → 111, Sleet cast ~370 → 172, Sleet drop 314 → 211, Gust move ~136 → ~75, SG move 355–394 → 169–189, Command 313 → 195.
- 2026-10-18: **Closing push, human: "let's get below 100 ms on everything … also profile the wall".**
  - **Pyright as the packed-mask detector.** It flags `in` on a CellMask (checked with a probe). The head has 0 such sites across dnd, server and devtools. It can't see untyped (`Any`) sites.
  - **PV2 (shared contacts and light sources once per seat, schema 14) started.**
    - Sleet drop, blue seat: 26 observers repeat 230 distinct object contacts 2,706 times (250 KB) and 46 light sources 532 times (190 KB). Together that is 73 % of a 601 KB update.
    - A Godot fold note comes with it.
  - **Wall of Stone profiled** (239 ms; native 179, publication ~53):
    - The scalar wall FOV is ~70 ms: `compute_fov` → `_sparse_directional_visibility`, 64 calls (30 sight, 34 light).
    - Light recompute is ~40 ms (`resolved_light_level`, 10,040 calls).
    - `stone_enclosure_escapes` is ~21 ms (rule geometry).
  - **PV1a-4 started (plan §6b):** the wall FOV as route × edge-grid arrays, one path, equal to the scalar path by oracle. Then per-tile light resolution as array reads.
- 2026-10-18: **Unfinished plan items, measured (integrator; probes in scratchpad residuals/dup_probe.py, settle_probe.py).**
  - **Choices: use-object contacts.** `_collect_use_actions` (entity.py:7272–7281) calls `manual_object_contact` from every Move destination for every usable or pickable object: ~2,900–4,000 calls per menu or AI decision, nearly all with distinct arguments, so sharing per pair saves nothing.
    - Exact cut: skip candidates farther than the object's reach (5 ft, or 0 for boundary handles) in plain grid distance from every surface cell. `support_distance_feet` = max(grid distance, vertical) ≥ grid distance, and the loop already skips surfaces beyond reach.
    - Estimate: Choices ~20 ms, AI first decision ~35 ms.
  - **Choices: AoE previews.** 326 aim-point footprints cost ~28 ms. Free-aim legal regions (`get_valid_positions` of zone spells) cost ~10 ms (was 22). `BaseCost.model_validate` is ~0 ms now; nothing left there.
  - **AI first decision:** discovery as above, plus `materialize_navigation` at turn start (~40 ms, PT's cost grid).
  - **Spirit Guardians move (~175 ms real):** all 30 observers change on every step (torch 30/30, aura 30/30, caster contact 29/30), so no observer can be skipped. The cost is the same change built 30 times:
    - seat fold `apply_current_audience`, 90 calls: ~35 ms (sent to the PV2 agent);
    - per-observer `_publish` and `_emit_settled`: ~32 ms (aura refresh ~10, torch ~4, cell deltas ~4);
    - identity grants (`identifying_observers` / `observers_granted`): ~11 ms;
    - version grants: ~12 ms;
    - the mover's wall FOV: ~6 ms (PV1a-4);
    - navigation after the move: ~6 ms;
    - HUD sheets: ~7 ms.
- 2026-10-18: **PH-2 merged (f908ec95e)** (branch ph2b: 0e0b590da step 1, 380e7c484 step 2, 914cc6847 step 3 with the review fixes, 7b04aa5c2 replay check).
  - Single values are read live again (EB-02-010 is back to its live contract).
  - `with_rows` keeps each extra row's own normalizer and dedupes it; a cleared value reads 0; the test-only second mechanisms are deleted.
  - Gates (agent):
    - full sweep, 0 new failures vs r21;
    - transcripts identical and published updates byte-identical vs ff37e2a29 on 7 cases;
    - value-read differential, 0 mismatches over 31 cases.
  - Tracked objects after Start: 828K → 688K (block values 155K → 19K). Fireball's ~5.4K kept value objects → 0.
  - Time (native, ff37e2a29 → PH-2):
    - Fireball 99 → 93;
    - CoD 90 → 85;
    - Sleet cast 82 → 74;
    - SG moves −5 to −9;
    - Command 187 → 178 total.
  - **For the human (AGENTS.md "no getattr to cheat"):** `BaseBlock.value_fields()` reads value fields by `getattr` over names recorded per class from `model_fields`. That is narrower than the per-instance getattr + isinstance scan it replaces, which also remains for child blocks (base_block.py:405). The explicit alternative is a per-class `value_fields()` in ~14 classes. Merged as is, pending your ruling.
  - Left as is: transient records ("Object AC", dice bonuses) still register by default, as before.
- 2026-10-18: **Discovery merged (8d1b1d78f; abf1918aa, 0472a895b).**
  - Use-object contacts are traced only from origins within the object's reach: `GridMap.manual_object_contact_origins`, and one pure `contact_surface(placement)` shared with `attack_object_contact`.
  - The plan's §14.2 #4 names this `contact_ring_cells`, with the intersection in Entity. Here the ring and the exact check are one GridMap query (same mechanism, different name and owner).
  - Gates (agent, vs f908ec95e):
    - every Choices/Preview/Command response and available-actions result identical;
    - brute-force oracle: 0 mismatches over 2,024 queries / 253,725 origins;
    - agreement cases identical;
    - transcripts byte-identical; folded states equal;
    - sweep 0 new vs r21; pyright 0 new.
  - `manual_object_contact` calls: caster menu 2,943 → 34, AI decision 3,978 → 33.
  - Time (median of 3, loaded machine):
    - caster menu 160 → 148;
    - fighter menu 85 → 75;
    - AI decisions 2 / 3 / 4: 104 → 91, 104 → 82, 271 → 255;
    - AI decision 1 flat at ~150.
  - **Free-aim (A2): not changed; needs a decision.** The menu's only consumer of zone spells' `get_valid_positions` (`_aoe_aim_points`) needs the legality of at most C+1 aim points, but the whole legal region is enumerated (~8 ms). The exact fix is a per-point legality check, which changes the `get_valid_positions` contract.
  - **Left (next owners):**
    - per-template `attack_object_contact` from a single origin inside weapon or spell range: ~18 ms caster, ~30 ms fighter menu / AI. 169 per fighter menu are exact duplicates: entity.py:5842 repeats base_actions.py:1441's call.
    - target HP reads through the value layer: ~21 % of the caster menu.
    - AoE aims ~24 %; footprints ~10 %, which fall to ~22–25 ms with PV1a-4's arrays and ~4–10 ms with a per-cell PROPAGATION entry grid (A3 estimate).
    - turn-start navigation: ~23 % of AI decision 1 (PT).
- 2026-10-18: **PV2 progress (agent, not merged yet).** Shared rows per group, with removals in the same interning; folded client state strictly equal to 73c4fd0ea on 9 cases.
  - Largest seat update: Sleet cast 321 → 149 KB, Sleet drop 615 → 186, SG moves ~230 → 114–127, Fireball 327 → 254, CoD 330 → 263.
  - Integrator approved, within PV2: default-valued SensoryFact scalars left out of the dump by the cells' exclude_if rule (SG moves ~90 KB).
  - Still over 100 KB:
    - Fireball/CoD: world_updates ~70 KB, combat_log 41–57, resolution_ref ~14, version_rows ~13.
    - Sleet drop: per-observer cells 70 KB.
- 2026-10-18: **PV2 multi-observer seats merged (9795ef06f; df54787a8 … c357ba7e6), schema 14, PlayerSequence 7.**
  - Each group's distinct contacts, sightings, light sources and removal identities are sent once as columns (`sensory_rows`). Facts name them by index. Default-valued scalars are left out by the cells' `exclude_if` rule.
  - One-observer seats use the same shape. Plan line 671 says "plain per-observer"; the human may confirm the text.
  - The SDKs (Python, TS 63/63) are regenerated. Godot note: agent_docs/GODOT_CLIENT_FOLD_SCHEMA_14_2026-10-18.md.
  - Gates (agent, vs f908ec95e): folded client state strictly equal on 9 cases; sweep 0 new; pyright 0 new.
  - Largest seat update:
    - Sleet cast 321 → 142 KB; Sleet drop 615 → 179;
    - Cloudkill cast 237 → 65; Cloudkill drop 484 → 138;
    - Darkness 185 → 60; Daylight 502 → 204;
    - Fireball 327 → 247; CoD 330 → 262;
    - SG moves 221–235 → 94–107; Gust moves 81–102 → 37–58;
    - blue initialization 3.28 → 2.12 MB.
  - SG moves: publication 46–49 → 39–43 ms. `_current_effect` 90 → 6 calls per move.
  - Still over 100 KB, and what dominates:
    - Fireball/CoD: world_updates ~70 KB, combat_log 41–57, resolution_ref ~14, version_rows ~13.
    - Daylight: sightings 47 KB, cells 47.
    - Sleet drop: cells 70 KB.
    - SG moves 3 of 6 at 101–107 KB.
  - Publication now: the slow drop and light ops are dominated by `_world_update`, the per-observer cell fold and `dataclasses.replace`, not by rows.
- 2026-10-18: **PV1a-4 merged (7fde9516a; 275ae9057 … c5e588ed6).** The wall FOV is one array solve (`view.wall_visibility`) over per-channel `GridMap._transit` grids. The sparse and dense scalar solvers and their four dict memos are deleted.
  - Re-gated on the merge with discovery and PV2:
    - transcripts identical and updates byte-identical, merged vs pre-merge, on 9 cases;
    - scalar-solver oracle: 0 mismatches over ~600 solves on 4 cases (the agent: 8 cases plus ~79K random-world queries);
    - sweep: 63 failures, 0 new; test_gas_traps' shared-exposure test now passes.
  - Logged for the human:
    - edge answers are settled on first read inside GridMap, not written by the writers (eager writes measured +12 ms of unread predicates);
    - a directional solve raises beyond 80 cells;
    - shadowcast still serves maps without optical boundaries.
  - Light-level resolution as arrays (item 2) is blocked: a Tile reading a GridMap grid inverts the import DAG (open in §6b).
- 2026-10-18: **Close-out (integrator).**
  - a2ff92854: blocks name their value fields explicitly. PH-2's getattr discovery is gone, and an architecture test guards the lists. d506a0d58: the four test-defined example blocks follow the new authoring rule (transcripts identical on 5 cases).
  - e260e92e1: unused imports and a dead map lookup from the perception merges removed.
  - agent_docs/RULE_VIOLATIONS_2026-10-18.md: the refactor's census against AGENTS.md and §6a.
    - getattr +1 −2, now 0 added; isinstance net −123 (20 new call texts, classified); 0 in-function imports.
    - Open: the union-field checks (`bonus: int | ValueReading`, `ac: int | value`), the target-kind checks, the modifier-kind filter.
- 2026-10-18: **Final Exit re-time at d506a0d58** (same code as e260e92e1 apart from the unused imports).
  - 29 gallery cases, 3 runs each; table in scratchpad `logs/exitF_table.md`.
  - Load was 12.7 at the start and 4.9 at the end, from other sessions' git and IDE I/O: provisional by §6a.
  - 0 GC passes inside any op. The post-reply collection is ≤8 ms, except the caster's Choices miss at ~68 ms.
  - First Exit (b1ce2a00c) → final, median total ms (largest seat update):

    | Op | ms | Bytes |
    | --- | --- | --- |
    | Wall of Stone | 225 → 159 | 223 → 94 KB |
    | SG moves | 169–189 → 133–151 | 221–235 → 93–107 KB |
    | Gust moves | ~75 → ~63 | 82–85 → 37–40 KB |
    | Sleet cast | 172 → 164 | 321 → 142 KB |
    | Sleet drop | 211 → 213 | 615 → 179 KB |
    | Round-step Sleet | 183 → 152 | 321 → 142 KB |
    | Fireball | 177 → 176 | 327 → 247 KB |
    | CoD | 175 → 166 | 330 → 262 KB |
    | Ice Storm | 111 → 106 | 188 → 123 KB |
    | Cloudkill cast | 112 → 114 | 237 → 65 KB |
    | Cloudkill drop | 188 → 191 | 484 → 139 KB |
    | Darkness | 101 → 102 | 185 → 60 KB |
    | Daylight | 210 → 220 | 502 → 203 KB |
    | Chain Lightning | 89 → 94 | 143 → 98 KB |
    | Portal move | 106 → 88 | — |
    | Gas vent | 95 → 76 | — |
    | Caster Choices miss / command | 168 / 195 → 154 / 176 | — |
    | Fighter Choices miss | 98 → 70 | — |
    | AI decisions | 144 / 100 / 98 / 262 → 116 / 78 / 67 / 210 | — |

  - Everything else is ≤100 ms and ≤100 KB:
    - single-target and small-area spells 20–71 ms;
    - caster steps ~52, end turns 6–8.
  - **Still over 100 ms:** Daylight 220, Sleet drop 213, AI decision 4 210, Cloudkill drop 191, Fireball 176, caster command 176, CoD 166, Sleet cast 164, Wall of Stone 159, caster Choices miss 154, round Sleet 152, SG moves 133–151, AI decision 1 116, Cloudkill cast 114, Ice Storm 106, Darkness 102.
  - **Still over 100 KB:** CoD 262, Fireball 247, Daylight 203, Sleet drop 179, Sleet cast and round Sleet 142, Cloudkill drop 139, Ice Storm 123, SG moves (3 of 6) 101–107.
  - **What dominates what is left** (measured this session), with the next owner of each:
    1. **Publication on drops and light changes** (130–148 ms: Daylight, Sleet drop, Cloudkill drop) is `_world_update` per sensory event, the per-observer cell fold and `dataclasses.replace` of the view.
    2. **Per-observer settlement fan-out on moves:** the same aura, torch and contact change built for 30 observers (~32 ms per SG move); 2-D batching.
    3. **Fireball and CoD bytes:** world_updates ~70 KB, combat_log 41–57, resolution_ref and version_rows ~13 each.
    4. **Discovery:**
       - duplicate weapon-reach contacts (169 per fighter menu; entity.py:5842 repeats base_actions.py:1441);
       - target HP reads through the value layer;
       - AoE aims;
       - free-aim legality per point, which changes the `get_valid_positions` contract (decision).
    5. **Turn-start navigation** (~23 % of AI decision 1): PT's cost grid, not started.
    6. **Light bookkeeping** (~30 ms of Wall of Stone): re-adding unchanged contributions. The exact skip is cheap; arrays need the DAG decision.
    7. **Memory retention over a long game** (8.8 GB at 47 min): the next refactor, per the human.
  - **Decisions for the human, collected:**
    - PV2 one-observer seats use the shared-row shape (plan line 671);
    - discovery's bound is named `manual_object_contact_origins` (§14.2 #4 says `contact_ring_cells`);
    - PV1a-4's lazy edge answers, its 80-cell limit, and shadowcast as a second sight rule;
    - the light-array DAG inversion;
    - free-aim's `get_valid_positions` contract;
    - the union fields in events and AC.
  - The Godot client must follow schema 14: agent_docs/GODOT_CLIENT_FOLD_SCHEMA_14_2026-10-18.md.
- 2026-10-18: **Next wave, after the stop-hook review: "the plan's Exit is not met".** The closed lanes stay closed. Four plan items that need no human decision were started from d6a5ba8e7. Each comes back to the single integration worktree.
  - **S: PV1a-2's remaining items** (codex/single-pass-fanout): shared changes per settlement as arrays over observers, identity grants per settlement, volume and effect loops vectorized, area-independent emit.
  - **W: the rest of PV2 plus the publication of drops and light changes** (codex/single-pass-wire2), schema 15: cells once per seat with per-observer bit lists, Fireball/CoD world_updates and combat log, `_world_update` once per group, the cell fold over arrays.
  - **D: PD1b/PD2 and PV1a-4 leftovers** (codex/single-pass-leftovers): duplicate weapon-reach contacts, skipping an unchanged light contribution, discovery HP reads, a hoisted wall predicate set, and AoE footprints if exact.
  - **N: PT navigation as a cost grid with a predecessor array** (codex/single-pass-nav): the same chosen paths, costs and safe sets, by oracle.
  - Still parked on the human: free-aim's contract, light arrays (DAG), the union fields, and the Godot client (PC).
- 2026-10-18: **Leftovers merged (a59707d29 … 60ff97d6a).**
  - The admitted physical-access contact is carried from admission to the target list: `BaseAction._physical_access_contact`, `@final`, listed in the admission architecture test. `attack_object_contact` calls: fighter menu / AI decision 819 → 650, caster menu 851 → 774. An oracle found 0 mismatches over 15,551 listed targets.
  - Object HP is read once per check, and `Health.get_max_hit_dices_points` skips the count read when the modifier is 0.
  - `Tile._add_illumination` skips an identical installed level.
  - `SolidWallZone.blocks_crossing_between` builds its admitted cells once per call. Forcecage (wall_constructions.py:831) still rebuilds them per section.
  - Gates (agent, vs d6a5ba8e7):
    - discovery dumps and agreement counts identical;
    - transcripts byte-identical on 6 cases;
    - sweep = r21; pyright 0 new.
  - Time (5 interleaved runs, base → new):
    - caster menu 138 → 130; fighter menu 72 → 58;
    - AI decisions 1 / 2 / 3: 138 → 113, 91 → 76, 80 → 66;
    - Wall of Stone 172 → 161; Daylight 205 → 196.
  - Assumption recorded: the carried contact traces `template.source_entity_uuid` where the deleted call traced `self.uuid`. They were equal at every sampled site, but nothing enforces it.
  - Left: the AoE aim footprints (~16 ms) need a new kept per-cell PROPAGATION grid. The other single-origin callers feed a rule's own subjective contact, so they still repeat the admission check (169 per fighter menu).
- 2026-10-18: **The wall FOV's 80-cell raise removed (human: "kinda unacceptable").**
  - PV1a-4's solve raised past its kept 80-cell route table, so a light or area radius over 80, or an unbounded `compute_fov`, on a map wider than 80 cells would have crashed an action. The scalar solver it replaced answered any reach.
  - The fix: `supercover_route_steps` is the one stepping rule. The kept table is its output within 80, and `wall_visibility` sizes its frame to the window, with batches beyond the table.
  - Checks:
    - the kept table is bit-identical;
    - 3,000 long routes equal the scalar supercover line;
    - FOV oracle 0 mismatches on 2 cases;
    - new 200-cell corridor contract cases, which raised on the previous head.
  - Integrator note: I logged this limit as "a decision for the human" at merge. It should have blocked the merge as a crash path.
  - Perception reach itself stays 80 cells (400 ft), as in the base engine (`update_all_entities_senses(max_distance=80)`; `sense_radius_cells` clamps to it).
- 2026-10-18: **PT navigation merged (f45916449; e7a5200d2 … 4a521a12b).**
  - One path search over cell arrays: `GridMap.path_search` / `compute_paths` return `Routes`, and paths are rebuilt from predecessors (new pure `dnd/core/navigation.py`).
  - Senses' `walkable` and collision fields are read-only CellLayers with named writers. `dijkstra.py`, `_prefer_direct_navigation_paths`, `path_costs` / `safe_path_costs` and `GridMap.get_distance` are deleted.
  - Gates (agent, vs ee9216784):
    - navigation oracle: 0 mismatches over 11 gallery cases and 400 random worlds (8,039 materializations, 4,800 searches, 1,579 moves);
    - array edges equal `can_transition` on ~1.66M edges;
    - transcripts byte-identical on 11 cases;
    - sweep 0 new; pyright −2.
  - Per gallery run: `can_transition` ~79K → ~290 calls, `is_walkable_for` ~85K → ~5K.
  - Turn-start materialization 31.8 → 4.6 ms. AI decision 1 126 → ~95 ms (loaded).
  - Heap after setup: 249K → 207K tracked objects. The caster's post-reply collection 59–66 → 11–13 ms.
  - Plan wording: "one path search" holds in representation, but BFS and weighted Dijkstra both remain, because their tie-breaking differs.
  - Logged:
    - `AreaCondition.crossing_channels` defaults to None, which makes undeclared zones (Gust's among them) global crossing owners that force Python step checks;
    - a kept movement-cost grid was not adopted (writer completeness unproven);
    - `EventQueue.is_first_at_phase` compares wall-clock timestamps (latent; no effect seen).
  - Census gap closed: `Entity._navigation_traversal` (P5) is an entity-held memo against §6a, now listed in RULE_VIOLATIONS.
