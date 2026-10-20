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
  - **Player-visible bug, pre-existing, to fix separately:** `actions.py:2272` `set_context` replaces the attack context set at `entity.py:3425`, so `attack_ability` is missing during a real weapon-attack roll. Reckless Attack's contextual advantage never applies. PR preserves the behaviour exactly. **Fixed 2026-10-18 (codex/enp-cleanup):** the attack read's context now starts from the attack value's own context (`Attack._resolve_attack`); `tests/progression/test_reckless_attack_roll.py` failed first.
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
  - `SolidWallZone.blocks_crossing_between` builds its admitted cells once per call. Forcecage (wall_constructions.py:831) still rebuilds them per section. **Fixed in 18f88c8cc (codex/enp-cleanup).**
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
    - `EventQueue.is_first_at_phase` compares wall-clock timestamps (latent; no effect seen). **Fixed in 387645d3a (codex/enp-cleanup): store order.**
  - Census gap closed: `Entity._navigation_traversal` (P5) is an entity-held memo against §6a, now listed in RULE_VIOLATIONS. **Fixed in 4345392a6 (codex/enp-cleanup): a `SpatialSensesSystem` frozen `NavigationRead`.**
- 2026-10-18: **PV2 wire part 2 merged (777ecce99; 8b4673143 … 312d4a8b8): player schema 15, PlayerSequence 8.**
  - Wire changes:
    - each group sends its visible cells once, and light and hazard (cell, value) tables once; each observer's cell lists are bit lists over them;
    - observer and contacts are named by index; light sources are compact rows;
    - spatial-effect cell lists are packed;
    - resolutions and spell applications use the seat's lineage index;
    - 78 default-valued fact fields are left out;
    - changed resolved light is one packed set per world update.
  - Publication:
    - a re-observed body builds each item record once per walk;
    - no `dataclasses.replace` when nothing changes;
    - `_world_update` skips tiles the seat already holds as the same object.
    - Once-per-group `_world_update` is NOT exact (the object-removal rule is judged per event against a view that can lose cells mid-group) and was not done.
  - The Python SDK validator now registers `base64url`. Messages with packed cells couldn't be validated since schema 13.
  - Gates (agent): folded client state strictly equal per op and seat on 10 cases vs 983e85d1d (and three earlier bases); sweep = r21; SDK tests TS 64/64, Python 91/91; pyright 0 new.
  - Time and bytes (3 runs, loaded, base 983e85d1d → new):
    - Sleet drop 182 → 145 ms (179 → 85 KB); Daylight 195 → 159 (204 → 83); Cloudkill drop 171 → 126 (139 → 74);
    - Sleet cast 150 → 145 (142 → 96); Ice Storm 98 KB; SG moves 53–66 KB;
    - Fireball 247 → 201 KB; CoD 262 → 220 KB.
    - Client fold cost +0 to +3 ms per update.
  - **For the human:** Fireball and CoD can't fit 100 KB without (a) a residue-patch world-update type (each blood or ash change re-sends the tile's whole residue list, 53–56 KB) and (b) a combat-log redesign (41–57 KB, one entry per native event). Both are wire-design decisions.
  - Also: `PlayerCausalIndex` / `index_player_lineage` are only called from `game_obsolete/`, so deleting them is the human's call. **Deleted in d96f0b973 (codex/enp-cleanup).** One more fact-family `isinstance` (`SpellFact`, `_public_occurrences`).
- 2026-10-18: **PV1a-2 fan-out merged (codex/single-pass-fanout, head 2c52b957d).**
  - Settlement runs each stage over all views in turn. The rule hooks read only the observer's own senses or the world (reorder checked by both reviewers).
  - Fixtures are re-observed in one pass per condition footprint, and emitters (light) are one masked OR over stacked views (`GridMap.light_slot_words`).
  - Identity grants live only in a frozen `GrantTable`. It is None while no observer holds grants: the content-pack loader treats a truthy system attribute as live state (logged; worth a look).
  - The (subject, cell) `identifying_observers` memo is kept as in the base (Fireball 87 → 104 ms native without it).
  - One emit loop; the cell change returns its "differs" flags.
  - Gates (agent, vs ead1f2458):
    - 0 differences in per-settlement observer state and sensory payloads on 8 cases;
    - transcripts byte-identical;
    - sweep = r21; pyright 0 new.
  - Time (total / native): SG moves 131–153 / 89–106 → 114–129 / 68–80; AI decision 4 216 → 182; Fireball 162 / 91 → 152 / 76; Sleet cast 154 → 145; Gust moves 60–66 → 51–56; Wall of Stone 143 → 136.
  - Measured and not done:
    - the stacked cell delta (slower: 2.1 vs 1.3 ms per 30-observer settlement);
    - the sphere-volume loop (never runs in these cases);
    - zone install (it is light work in `recompute_lights_at_positions`, ~63 ms profiled on Wall of Stone).
  - Remaining on SG moves: publication ~40, the contact fan-out ~10, view ~7.
- 2026-10-18: **Wave close: final re-gate and re-time at 094b528f7.**
  - Re-gate: events/logs identical to d6a5ba8e7 on 9 cases (published bytes differ by schema 15, whose folded states were proven equal by the wire lane); navigation oracle equal on 9; FOV oracle 0 mismatches on 4; sweep = r21.
  - Re-time: 29 cases × 3, load 10–12 from read-only study agents, so provisional. Table: scratchpad `logs/exitG_table.md`. Before → after this wave:

    | Op | ms | KB |
    | --- | --- | --- |
    | Daylight | 220 → 142 | 203 → 83 |
    | Sleet drop | 213 → 141 | 179 → 85 |
    | Cloudkill drop | 191 → 116 | 139 → 74 |
    | Fireball | 176 → 147 | 247 → 201 |
    | CoD | 166 → 140 | 262 → 220 |
    | Sleet cast | 164 → 142 | 142 → 96 |
    | Wall of Stone | 159 → 138 | — |
    | SG moves | 133–151 → 117–137 | — |
    | AI decisions | 116 / 78 / 67 / 210 → 88 / 71 / 61 / 194 | — |
    | caster Choices miss / command | 154 / 176 → 136 / 155 | — |
    | fighter Choices miss | 70 → 57 | — |
    | Ice Storm | 106 → 81 | — |
    | Cloudkill cast | 114 → 91 | — |
    | Darkness | 102 → 82 | — |
    | Gust moves | ~63 → ~55 | — |

  - 0 in-op GC passes. The caster menu's post-reply collection went 68 → 10 ms.
  - Over 100 KB: Fireball and CoD only.
  - Over 100 ms: Fireball, Sleet cast and drop, round Sleet, Daylight, CoD, Wall of Stone, caster Choices and command, SG moves, Cloudkill drop, AI decision 4.
- 2026-10-18: **Event-native delta study (read-only; scratchpad `delta/`).** Human: deltas come from the game-state change at event arrival, with no per-seat copy of client values, complete across the board; the combat log and memory are out of scope.
  - Findings: most of the wire is already event-native. Whole sends remain for light rows, sightings, residue lists, equipment/loadout, item records, the HUD, and collection fields. The per-seat copies (`remembered` world/actors/items, `spatial_values`, `observed_values`) exist only to produce diffs. Restatements inside one update: audience/envelope per lineage, N² spell declarations, double tree edges.
  - Latent bugs:
    1. connectors are read from init only, so changes never reach seats;
    2. the client and engine folds disagree on temp HP in a condition's `resulting_stats` and on INTERNAL conditions, and the replica test can't see it;
    3. re-acquisition is counted per observer, not per seat;
    4. entered cells are taken from member events (wrong for multi-observer seats);
    5. server and client seat composition fold different values (possible divergence).
  - Proposed rule: one objective fold per session plus per-seat knowledge only. Each item is (a) the event's keyed change, disclosed; (b) an entering snapshot from the session fold; or (c) a key-only removal or lapse. Static content goes once per content id; nothing is restated.
  - Open decisions for the human:
    - D1: re-entry by full resend, or by revision stamps;
    - D2: fog of war kept client-side;
    - D3: per-member deltas, or a server-composed seat view;
    - D4: HUD event-native, or a per-actor previous sheet;
    - D5: is objective resolved light needed on the wire.
- 2026-10-18: **Contact fan-out as arrays merged into codex/event-native-deltas (109b87268, 82d823820).**
  - `_contact_maps` builds every view's contact maps in one batch, and rows are matched as packed int64 pairs.
  - Gates (agent, vs 55bf034cc): recorder 0 differences on 8 cases; transcripts byte-identical; in-process A/B 0 mismatches over 38,323 test-suite settlements; sweep = r21; pyright 0 new.
  - `_contacts` time: SG moves 8.9–13.6 → 6.1–10.3 ms; Wall of Stone 10.1 → 6.8; AI decision 4 22.5 → 18.3.
  - Op totals moved 2–4 ms. Every op that was over 100 ms still is: the budget is decided by publication (~40 ms per SG move) and Wall of Stone's light work.
  - Branches never hit by the gallery or the tests: multi-row entities, and side rows over cell rows.
  - `_target_ids` is listed in RULE_VIOLATIONS (append-only intern map).
- 2026-10-18: **Wall FOV shared across origins merged into codex/event-native-deltas (7b484f736).**
  - `wall_visibility` builds the 8 quadrant entry layers once per group of origins (`compact_window_groups` bounds each group's box). `compute_fovs` solves at most once per origin, the relight solves its sources as one batch, and the settlement solves its wall FOVs together (`SightScope`, `_wall_fov_routes`).
  - A kept map-wide layer was prototyped and rejected (saves ~1.5 ms, needs a revision at 6 writers). The batch saves ~4 ms and keeps nothing.
  - Gates (agent, vs ff7701f9a): FOV oracle 0 mismatches on 8 cases; random worlds 0 mismatches over 26,776 queries and 49,860 batch answers; kernel fuzz 0/14,978; transcripts byte-identical; sweep = r21; pyright 0 new.
  - Wall of Stone 144 → 136 ms (native 95 → 87). The other rows are within load noise.
  - The scalar-solver oracle moved to scratchpad `wf/fov_oracle_batch.py`; the old `pv1a4/fov_oracle.py` wraps a deleted method.
  - Next, decided by the integrator: sensory re-converts each sight answer (~1,800 tuples) to arrays and repeats the route lookup the solve made (~9 ms per Wall of Stone op). The solve returns its rows instead (own lane).
- 2026-10-18: **Inert-fact skip merged into codex/event-native-deltas (2b2dcc45e; 1ca67753e, f39d062e2).** An inert TILES_CHANGED fact (residue amounts, harmless material; hint == empty `SensesUpdateHint`) settles no observer alone. In a group, an observer is dropped only if all its recorded facts are inert, so `_reason_for(events[-1])` is unchanged.
  - Gates:
    - the agent's, on b58417f4a;
    - re-run by the integrator on the merge against an export of 585b86e2e, after the human's go-ahead (the subagent's own merge was blocked by the permission check): per-settlement recorder 0 differences on 9 cases (432 settlements, padded recorder for the skipped passive reads); transcripts byte-identical on 9; sweep = r21.
  - Magic Missile settlement 30 → 3 observers, native 22 → 17 ms. Other rows are within noise.
  - Dead code noted: `GridMap.publish_tile_state_changed` (the cleanup lane deletes it).
- 2026-10-18: **Test memory re-measured:** the former 15–20 GB spell tests peak at 0.23 GB, and a 25-file sweep chunk at 0.29 GB. Parallel test lanes are fine; the caps stay as a safety net.
- 2026-10-18: **Correction to the PT-navigation entry ("`AreaCondition.crossing_channels` defaults to None"):** stale.
  - `AreaCondition` declares `frozenset()` (area_conditions.py:1061), and so do the trap and mechanism families. Only the base `SpatialCondition` keeps `None`, restored in b98543e50 because the contract test `test_undeclared_custom_rule_still_blocks_outside_registered_footprint` requires undeclared rules to stay global.
  - Crossing oracle (enp-crossing lane):
    - 66 zone classes;
    - gallery, 9 cases: 46,272 crossing queries, 0 with a global owner;
    - tests: 1,575,580 queries, global owners only the contract test's remote rule and bare test conditions;
    - 0 unconsulted zones that would block.
  - Decision (integrator): no change; the gain is zero.
  - Open: whatever made navigation take Python per-step checks in Gust is something else (to look at in the native study).
- 2026-10-18: **E1 merged into codex/event-native-deltas (78ecee85c … ae39ca050).**
  - **Startup:** capture admits LIGHT_CHANGED and TILES_CHANGED, so seats no longer start with stale light (lantern crypt: 49 first-seen tiles were DARKNESS against BRIGHT) or without startup residues. This is player-visible.
  - **Connectors:** the projector reads the recorded connectors instead of the init event's, so changes after init reach seats at the projection boundary. **Open:** on the live path a connector edit still raises "Unprojected committed state" (application.py ~77; `TraversalConnectorChangeEvent` is an unsupported header). Nothing edits connectors outside tests today. Assigned to E3-world.
  - **Strict xfails** (hand-built facts, latent on head) for the temp-HP/INTERNAL fold disagreement and the destroyed-item ghost layer. Kept as the "client fold == engine fold" contract; they turn green with E3-bodies.
  - **Transcript differences**, all classified: a constant occurrence shift (amber +28, blue +44, from the larger initialization), removed light corrections, true first-sight light, and no residue re-sends.
  - **O3 baselines** must be recorded on this head.
  - Not admitted at startup (out of scope): TILE_CHANGED / TILE_REMOVED.
- 2026-10-18: **FOV-rows merge re-gated by the integrator:** recorder 0 differences on 6 cases; transcripts byte-identical; sweep = r21.
- 2026-10-18: **Sweep r29 on the E1 merge:** 64 failures, the same set as r21.
- 2026-10-18: **Plan revision 3 (a8d40ed55, 5779fecb6).**
  - E3a can't be byte-identical: today's wire diffs against each seat's held values, and keeping it would need a second fold. It is dissolved into E3-world, then E3-bodies, then E3-sensory.
  - The E3 gates become O1–O4 plus identical log entries, with named re-entry byte exceptions. The human: "ensure the client has all the information needed to play and we do not have regression in how we handle subjective and boundaries of who sees what".
  - O4, the disclosure boundary, is added to E0.
  - The lane decisions are in scratchpad `e3design/*_brief.md`.
- 2026-10-18: **E5 merged into codex/event-native-deltas (c157a21f7, a95edcaef, b505e60eb): the HUD as an op-end engine sheet publisher, H2c, player schema 16.**
  - **Design.** One frozen published sheet per actor on `Session` (never per seat), compared at op end. A keyed `ActorSheetEvent` carries only the changed groups. `InitiativeOrderChangedEvent` is emitted at the three initiative writers. The per-seat HUD diff and `hud_snapshots` are deleted.
  - **Gates on b505e60eb** (a8d40ed55 + E5):
    - the HUD fold is equal at every op and seat on 9 cases;
    - payloads minus `hud` are identical, initialization included;
    - native events are identical except the added events;
    - op-end HUD oracle and one-caller architecture test;
    - sweep 0 unexpected against r29 (`test_gas_traps` share-one-exposure depends on test order);
    - pyright 0 new.
  - **HUD bytes per op** (G1): Fireball 5.2 → 2.7 KB, SG walk 1.5 → 0.4 KB, init 109 → 105 KB.
  - **ms:** within load noise; E5's own CPU is lower or equal.
  - **For the human:** H2c (a kept sheet per actor) instead of H2a (the whole sheet on each event), accepted by the integrator.
- 2026-10-18: **Cleanup lane merged into codex/event-native-deltas (fefaae23c).**
  - **Removed:** `publish_tile_state_changed`, `PlayerCausalIndex`, the per-query Forcecage cell set, the `_contextual_status` isinstance filter, and timestamp order in `is_first_at_phase`.
  - **`D20Event.bonus`** is an optional reading (the int duplicated `dice_roll.bonus`).
  - **Navigation:** `Entity._navigation_traversal` became `NavigationRead`, owned by `SpatialSensesSystem`.
  - **`_target_ids`** is kept: no exact, not-slower alternative.
  - **Player-visible rules fix:** Reckless Attack with a Strength melee weapon now grants advantage.
  - **Gates:**
    - published updates byte-identical on 7 cases;
    - the only native difference is `bonus` 0 → null on unread D20 requests;
    - sweep = r29;
    - pyright 0 new.
- 2026-10-18: **E3-bodies prep (codex/enp-e3-bodies)** on top of E2's tip:
  - **Startup-damage grant fix (5e937d6a1):** roster setup runs under the encounter's identity and location rule. 250 startup versions change only in their grants. Amber starts with crowd 1–6 at 6 HP instead of 44. This is player-visible.
  - **Static-look census:** no held item's look or profile changes over 29 gallery cases and 4,139 tests.
  - **Ruling (a):** one per-event conversion turns E2's named after-values into keyed rows, shared by every seat.
- 2026-10-18: **E3-sensory prep (codex/enp-e3-sensory, 314105098):** the native settlement marker, with native events identical apart from it and the wire byte-identical; schema-16 sensory types in a staging module; the client fold; vectors V1–V8.
- 2026-10-18: **Free-aim per point and GC alarms (codex/enp-freeaim: f02305211, 2b3fc5be6, 0405ae2d6), merged with 6810854a2 (c903b3dce).**
  - **Free aim:** Create or Destroy Water, Call Lightning and its Strike answer each aim point by one per-point rule (`valid_positions_among`), and `get_valid_positions` lists that rule's cells. Caster menu `_collect_aoe_actions` 41 → 32 ms (minimum of 30 in-process repeats).
  - **GC alarms:** pydantic reads a default factory's signature at every schema build in play and every `model_construct`. A C callable's (`list`/`set`/`frozenset`/`tuple`, `time.time`) leaves a class cycle (`inspect._signature_fromstr`).
    - The 71 fields of models built in play and `DecisionEpoch.created_at` use Python factories (`dnd/core/base_object.py`).
    - The content registry's recursive closure is a module function.
    - Per-op `cycles_found` is 0 on 31 gallery cases (AI decisions 15 → 0). Start 11,947 → 317.
  - **Known Start garbage:** 317 objects, once per process. numpy 2.5's `np.unique` reads `np.ma`, so numpy imports numpy.ma at the first `np.unique` (`view.py` `frame_rows`, at Start), and that import parses 5 C signatures. Integrator: no eager import; the alarm stays an alarm.
  - **Gates vs 6810854a2:** discovery dumps equal on 3 cases; seeded agreement reports equal; transcripts byte-identical on 4 cases; sweep = r29; pyright 0 new.
  - **Schema builds (measured, not changed):** none inside a timed gallery op. The harness builds each case's cast spells before its ops, as character creation would: 1–9 builds, 2.6–19.5 ms per case. Start plus setup: 81 builds, 137–204 ms (godmode 194 builds, 358–378 ms).
- 2026-10-18: **Free-aim/GC merged into codex/event-native-deltas (9394c24d0; ec2b72c0c).** Free-aim legality is per point, so zone spells no longer list their region in Choices (discovery 41 → 32 ms, controlled). The GC fix stops pydantic re-parsing C signatures on models built in play: `cycles_found` is 0 per op on 31 cases, and Start drops 11,947 → 317 objects (from numpy.ma's import, left as known). No gallery case builds a schema inside a timed op.
- 2026-10-18: **E2 merged into codex/event-native-deltas (a8299d110; 5e884c209).**
  - World (Q4 W): `KeyedTileChange` with its one fold `apply_keyed_tile_change`.
  - Actors: `ActorFactChange` in `AdmissionEvidence`, with one dispatch and one fold. `RecordedSequence` is schema 4.
  - Gates:
    - wire byte-identical except the accepted Fireball light cell (41,13);
    - AI knowledge equal on 10 of 10;
    - the (C) oracle exact except that cell;
    - pyright 0 new;
    - integrator sweep r30 on a8299d110: 64 failures, the same set as r29.
  - Native completion payload: Fireball 128 → 61 KB, Sleet 203 → 28 KB.
- 2026-10-18: **long_game measured (integrator, 9394c24d0).** The case is degenerate: the party is down in round 1 and stabilizes, the basic AI never finishes stable characters, and the harness loops AI-only rounds forever. That's the "hour".
  - Per-op time is flat with game length: AI advances average 147–250 ms over 20 rounds, and a profiled window at round ~10 is cheaper than one at round ~3.
  - Memory grows ~100 MB per round.
  - In the long game, ~50 % of an AI advance is the action menu: ~1,200 attack admissions per decision, with `attack_object_contact` 14 s profiled per 90 decisions.
  - New lanes: codex/long-game-case (a real game with a per-round curve) and codex/ai-step (an exact reach prefilter in discovery).
- 2026-10-18: **Native-exact merged into codex/event-native-deltas (ba7861260).**
  - Eleven byte-identical native fixes; the item list and dispositions are in scratchpad `native/ITEMS.md`. Item 11 is skipped because the light-row inputs have writers that can't all bump a revision.
  - Kept state lives only in owning systems: the registry's attachment index, `SpatialSensesSystem.identity_epoch` and `_id_texts`, the encounter's `_IDENTITY_CARRY`, and `EventQueue._contained_grants`.
  - Native ms, loaded machine: Wall of Stone 91 → 86, Fireball 88 → 79, Circle of Death 82 → 72, SG move 91 → 85.
  - Projected after E3, quiet machine: Wall of Stone ≈98 and Fireball ≈103. What remains:
    - Wall of Stone: the formation settlement (PV1), the zone install with its relight (P7), and the escape Move.
    - Fireball: per-target rules (PR, PD1c), the settlement (PV1), and per-version event machinery (P6, P7b).
- 2026-10-18: **The long-game case is real (c256ba3e8).**
  - Setup: the `immune_party` roster, 50 of 50 human turns over 13–14 rounds, about 5 min wall time. The old setup now fails its ≥45-turn assertion.
  - Per round, on a loaded machine:
    - AI advances average 130–200 ms;
    - Choices goes 62 → 110–124 ms over the game (to investigate);
    - RSS grows ~105–123 MB per round (0.57 → 1.94 GB) with `cycles_found` 0 throughout, so it is retained state.
  - Seeded runs reproduce the game exactly.
- 2026-10-18: **Sense-modes key merged (c6f8a832c).** `sense_modes_hash` (a per-process `hash()`) becomes the stable `sense_modes_key` tuple, which fixes E0 O2 on turn_undead. Transcripts are byte-identical.
- 2026-10-18: **Long-game Choices growth is world state, not history** (seeded game, c7ee71e6c).
  - Choices ms ≈ 65 + 0.093 × candidate target rows (r = +0.59). Against events stored, registry size and combat log, r ≈ −0.15.
  - Round 13 holds 32× round 1's events and is faster (56 vs 67 ms) at the same target count.
  - The rows grow with movement budget (Haste and Dash: move and jump destinations 135 → 500) and with the crowd in reach.
  - The cost is per-candidate admission: `discovery_admission` / `_requirements_contact` run once per (row × target).
  - Scratch: `lgc/choices_prof.py`, `prof_diff.py`.
- 2026-10-18: **AI-step part 1 merged (62764eb4c): an exact reach prefilter for weapon attacks on objects.** On the seeded long game, Choices is −8.3 % and AI advances −6.4 %.
  - The premise was partly wrong. Ranged long range (a 600 ft longbow) covers the map, so most object candidates are in reach.
  - An in-reach object costs ~135 µs per admission, and half of that is a duplicated contact trace: `weapon_reach` and then `_physical_access_contact` on subjective scans.
  - **Next:**
    - (A) drop the duplicate trace on subjective scans;
    - (2) evaluate the candidate-independent Jump and move values once per discovery call;
    - (1) an incremental AI fold, ~12–15 ms of ai_decision op 4.
  - ai_decision op 4 is dominated by the per-step engine settlement: ~197 of 449 ms profiled.
- 2026-10-18: **E0 merged into codex/event-native-deltas (8874757e2; branch head 60adf05eb).**
  - **What it adds:**
    - seat layouts G1 (faction), G2 (character) and G3 (batch:5);
    - the room_reentry case;
    - log and non-log bytes per seat;
    - the O1–O4 seat oracles (devtools/performance/seat_oracle.py, spool_replay.py);
    - tests/player/test_seat_oracle.py.
  - **Harness changes that shift numbers:** setups are now published as one unmeasured op, and every record is client-folded outside the timed spans.
  - **Base data, git-ignored, lost if the E0 worktree is removed:** /home/tommaso/.codex/worktrees/enp-e0/dnd_engine/.runtime/enp_e0_oracle/60adf05eb/ (t_<case>_F1|F2|F3, plus e0c_table.md and census_over_100k.txt).
  - **The ms columns were recorded under load.** Bytes are deterministic. The E6 re-time runs on a quiet machine with lanes paused.
  - **O1 classes on ad08ffa45 (G1 / G2 / G3):**
    - body.normal_hp 456 / 21,253 / 2,964 and life_state – / 17 / 1: starting damage (E3-bodies);
    - body.conditions 222 / 2,185 / 617: INTERNAL conditions (E3-bodies), plus the stale Prone from root overlap (fixed in E3-world by merged walk groups);
    - cells.hazard on portal_plate 6 / 90 / 21: see below;
    - the room_reentry ghost body 3 / 81 / 15 (E3-bodies H3).
  - **O2:** 87 of 90 runs pass. The turn_undead failure is fixed by the sense-modes key (c6f8a832c).
  - **Live-path bug found by O1:** `materialize_portal`, `materialize_pressure_plate` and `materialize_gas_vent` publish a bare `Event(BASE_ACTION)` root. Capture marks it UNSUPPORTED, and `capture_application_operation` raises "Unprojected committed state" (application.py ~82). Any mid-game trap materialization would therefore raise. This is the same class as E1's open connector-edit item; both go to E3-world.
  - **Rows over 100 KB non-log on the head:**
    - G1, G2 and G3: Fireball, choices_caster and Circle of Death (residues, combat log, spell facts);
    - **G2 mass_healing_word: 758 KB.** It is ally 1's first sight of the lit hall after being down: world tiles 444 KB and objects 201 KB.
- 2026-10-18: **E3-world Phase A and staging (codex/enp-e3-world, f597ad58d; not merged).**
  - **Phase A, byte-identical** (12 gallery cases: transcripts, every seat's PlayerUpdate and every startup record; tests/engine, ai, player and architecture failures = r29; pyright 0 new):
    - ab38e526a: the dead sensory `apply_world_fact` call goes; the server ends a departed contact through `audience.depart_contact`.
    - 3bffe3446: `ProjectionState.audience`; `dnd/player/static_sent.py` `StaticSent` (one typed id set per kind: `actor_births`, `content`); `CaptureCheckpoint.names` (never popped); `known_connector_uuids`; startup content is public + witnessed (equal to the old rule on 114 test startups); the architecture test that application, capture and worker never import the client fold.
    - f11f06ea9: the event-major walk (`_begin_walk`/`_enter_event`/`_leave_event`/`_end_walk`, drivers `project_lineages` and `begin_projections`); the native keys once per session in `SessionProjection`.
  - **Decisions recorded (coordinator):**
    - The session's one world fold lives in `SessionProjection` beside `capture` in `AudienceRuntime`, written only by the event-major driver's shared step through E2's `world_facts.apply_world_fact`. This replaces plan §5's "CaptureCheckpoint gains world facts"; `advance_capture` keeps only the evidence (actors, contacts, names).
    - The startup world is a recorded session-level interval, folded by the same step on the live and recorded paths.
    - The shared step folds in walk order and asserts each version is folded at most once. **Latent and unchanged (antiOOP F11):** roots are walked in completion order, so a root completing inside another root's execution is walked first; two overlapping roots writing one record end on the walk-order value, as today's per-seat folds do. Measured on f597ad58d: 101 of 586 root projections in tests/player + tests/ai, and 2 of 149 in 12 gallery cases (summon_retirement's initiative roots, which write no world), start below the previous root's last cursor.
    - `object_members` has one writer, the world object rows; sensory's contact rows keep `object_contact_members`.
  - **Staging** (no projector change): schema-16 world types, codec, client fold and vectors W1-W10 at `sdk/protocol/fold-vectors/world/` (49432f670, e6cd2593c); a look census over 29 gallery cases moved a floor item's visual name into its state.
  - **Expected test change:** `test_content_local_admission.py::test_catalog_replacement_admits_public_values_and_keeps_private_links_hidden` still passes, but a replacement catalog no longer back-fills content witnessed before it (unreachable from the worker).
  - Next: Phase B after E2 and E0 merge.
- 2026-10-18: **E3-world: roots whose versions interleave are one walk group (codex/enp-e3-world, 759f3b0c5; coordinator).**
  - **The rule, for E3-bodies and E3-sensory:** `capture_context` groups an operation's roots. A root starting before the last version of the group open so far joins it. The group's graph holds its roots' lineages and versions together, in source order, and is named by its root completing last. It is captured once, walked once by every seat and published as one `PlayerLineage` with its nodes in native order; the nested roots are parentless nodes inside the root's interval. A root that overlaps no other is its own group. Every fold walks these groups: the session world, the seats' and the clients'.
  - **Why:** the client folds a seat's lineages in emission order, so only one native-order lineage fixes it. This replaces the latent F11 note above. In round_step_zones a Prone removal root completed inside its TurnStart root, was published first and left the seat showing Prone. Probe (each seat's client mirror vs the native entity after each of the 63 operations): 168 stale Prone rows before, 0 after.
  - **Merged groups (all of them):**
    - gallery:
      - round_step_zones ×3: TurnStart + Prone removal;
      - summon_retirement: Conjure Animals + InitiativeOrderChanged and three rider conditions (Bite Prone Rider, Keen Hearing and Smell, Pack Tactics);
      - summon_retirement: Drop Concentration + InitiativeOrderChanged.
    - tests (tests/player, ai, engine), all in test_bg3_spell_transport.py:
      - Flame Blade + two ItemLocationState, WeaponEquip, WeaponUnequip;
      - Flaming Sphere + InitiativeOrderChanged;
      - Spiritual Weapon ×2 + InitiativeOrderChanged;
      - Dismiss Summon + InitiativeOrderChanged.
    - The other 10 gallery cases merge nothing. The earlier "101 of 586" counted repeated walks of one history and was not a merge count.
  - **Gate vs ad08ffa45:** 12 gallery cases byte-identical (summon_retirement's merged roots publish the same bytes); tests/player, ai, architecture failures = r29.
- 2026-10-18: **E3-world: the schema-16 world wire (codex/enp-e3-world, 657dff66c; not merged).**
  - **What changed.** The server keeps no copy of a seat's world, and each world update is built from what the occurrence wrote.
    - Source: E2's fold returns `AppliedWorldFact`, which names the records written. Values are read from the session world as of the occurrence. `world_publication` compares no world values, and an architecture test pins that.
    - A record perceived before and after the occurrence travels as a keyed change.
    - A record entering perception travels whole. Entering cells (cells coming into view, or a visible tile written whole) are authoritative: every object touching them, every connector with an endpoint there, and the tile as a static row (once per uuid) plus packed columns.
    - The seat sees an object go when the occurrence wrote it, or when it sees the object's support without it.
    - Leaving perception sends nothing.
    - Static rows go once per seat: the tile's surface and name, a residue material, an object's look, and a boundary structure keyed by a digest of its value.
    - Placements are compact: no derivable uuid, kind or lone support, no defaults. `visual_item_name` is left out when it equals `name`.
    - The client fold is `world_reduction.fold_world_update`. Godot note: `agent_docs/GODOT_CLIENT_FOLD_WORLD_2026-10-18.md`. Vectors: `sdk/protocol/fold-vectors/world/w1-w12` and `groups/g1`.
    - A record publishes once per seat (a walked event's own, or a change its members saw happen). A kept tile's keyed rows and a connector removal need the cells seen before and after.
  - **Decisions (coordinator):**
    - **Object members** are exact whenever an object row is sent. Between rows, the client holds the last row's bits, and a contact's members are E3-sensory's `object_contact_members`. Members-only rows were dropped: they cost about 100-215 KB per G1 update.
    - **A perceived record written again by another occurrence travels again.**
      - That re-admits a node carrying only a world update. Fireball adds 5 nodes per seat that sees the breaking objects: G1 +10 over 2 seat updates, G2 +150 over 30, G3 +35 over 7. The other 8 oracle cases add none.
      - **Native follow-up (not this lane):** `BaseItem.destroy` (dnd/blocks/base_item.py) emits `refresh_object_state` (OBJECT_CHANGED) and later `publish_location_state(FLOOR)` with the same after-value. A wall torch also emits `put_out`'s FLOOR fact (dnd/items/torches.py) in between, so the Wall Torch breaking gives OBJECT_CHANGED at 195 and FLOOR at 196 and 197.
    - **Placement as static content by revision is not built.** It touches the no-remembered-room rule; it stays the human's option if a row is still over 100 KB after the three E3 lanes.
    - **RecordedSequence 5** carries the startup world interval (E3-bodies' H4 rides on it).
  - **Re-entry rows (D1).** Largest seat update in KB, base → 2095deeff:
    | Row | G1 | G2 | G3 |
    |---|---|---|---|
    | Sleet drop | 85.7 → 88.8 | 38.6 → 115.5 | 58.1 → 139.7 |
    | Daylight | 83.7 → 92.3 | 45.0 → 139.9 | 65.5 → 95.4 |
    | room_reentry door_open | — | 27.8 → 87.6 | — |
    - Re-entered walls are the bulk: 214 walls in Sleet drop G2.
    - Measured, not built (columnar object rows): Sleet drop G2 → 79.0, Daylight G2 → 101.9, mass_healing_word G2 → 344.7, door_open G2 → 68.3.
  - **Other rows** (no regression):
    - Fireball 202.0 → 160.7 (G1), 178.7 → 137.2 (G2), 187.7 → 146.3 (G3).
    - mass_healing_word G2 758.8 → 382.7 (world 301.3: the healed ally's first sight of the lit hall, entering whole).
    - Sleet cast, Spirit Guardians steps, Wall of Stone, portal_plate and round_step_zones are equal or smaller.
    - The largest startup record per G2 seat drops 1.73 → 1.20 MB.
    - Op ms (one run each, on a machine loaded by the batches): lower on most rows; the few higher ones are within run noise. The 3-run quiet timing is not done.
    - Measured, not built: mass_healing_word G2's 1,070 tile static rows are 174 KB (one distinct surface and name). Interning surface and name would make them about 115 KB.
  - **Gates.** Against E0's base (60adf05eb, seeded): 9 oracle cases (fireball, sleet_storm, darkness_daylight, spirit_guardians_walk, room_reentry, wall_of_stone, round_step_zones, portal_plate, mass_healing_word) × G1/G2/G3, at dab1966d3.
    - **O1.** Every class count equals the base's, and no world class (tiles, objects, connectors) appears. Two changes: round_step_zones `body.conditions` goes 41 → 0 on all three layouts (the stale Prone), and portal_plate `cells:field:hazard` goes → 0 after e7f7e19c4.
    - **O2.** 27 of 27 spool replays pass in a fresh process with hash seed 1.
    - **O3.** The views equal the base's, except round_step_zones: 41 `body.conditions` (the Prone fix).
    - **O4.**
      - Bounded on all 27 runs: no seat learns anything the base did not tell it.
      - Object member bits: every bit sent to a multi-member seat equals what its client derives from the per-member views the sensory wire carries (18 runs on G1 and G3, 0 mismatches).
    - **Transcripts** (`--representation world-16`): events and logs are identical everywhere. Published updates outside `world_updates` are byte-identical, except Fireball's renumbered nodes (listed above).
    - **Sweep** (r29's directories): 66 failures = r29's 64 plus 2 `cr0_evidence` tests that need git (a snapshot has none; they pass in the worktree).
    - **pyright:** 0 new.
  - **Expected test changes (merge note).** Each change follows the rule.
    - `test_projection_local_world`: a composite keeps naming an attachment whose look was sent; contents and a suppressed cell stay as last seen after leaving view.
    - `test_storage_loot`: closing the chest or losing sight keeps the last contents seen (renamed `…keeps_last_contents…`).
    - `test_tile_field_updates`:
      - entering rows, not whole tiles;
      - a tile written whole re-enters;
      - a tile's surface and name never change for its uuid (raises);
      - the "already known tile" errors stay.
    - `test_light_source_projection`: the light's after-value reaches the seat before the light's completion, which sends it again.
    - `test_foreign_sensory_capture`: projects per walk group.
    - `test_content_local_admission`, `test_emitted_update_replica`, `test_world_after_values_reach_seats`: the new fields (object looks; the server holds no world copy; connectors as a dict).
    - `test_seat_oracle`: the start record carries the seat's startup content.
    - SDK fixtures: tile field changes hold scalars only.
  - **End reviews (antislop, antiOOP) — fixed in dab1966d3 / 657dff66c:**
    - one publication per record (antislop blocker: a removal sent twice made the client raise);
    - keyed tile rows and connector removals need cells seen before and after;
    - a key-only `AppliedWorldFact`;
    - one rule for a tile's own condition names (`tile_own_condition_names`), and one client static-row writer (`fold_static_rows`);
    - the senses fold is its own walk step;
    - seat knowledge passed by keyword;
    - dead walk fields, members-only leftovers and stale docstrings removed;
    - `test_foreign_sensory_capture` projects per walk group;
    - every tile field is in the vectors (w12, with the column bytes checked against the Godot note).
    The 12 gallery cases are byte-identical before and after these fixes.
  - **Kept, with the reason:**
    - The walk-local `pending` static rows: plan §3.5 says "never mid-walk".
    - `CaptureCheckpoint.names`: Phase A, accepted.
    - The T6 look-constancy and T8 delta-arithmetic tests: the look census over 29 gallery cases stands in for T6, and T8 is not built.
    - `seat_oracle` still imports `world_facts` privates. This is E0's harness.
    - The minor items are listed in the lane report.
  - **World-changing roots are supported (coordinator, from E0's portal_plate O1 class and E1's open connector-edit item).**
    - `materialize_portal`, `materialize_pressure_plate` and `materialize_gas_vent` now publish a typed `MechanismInstallEvent` root instead of a bare `Event`.
    - Capture retains that root, and also `TraversalConnectorChangeEvent` (its live connectors left out, since the connector's cold rows are its world fact's), as recorded families.
    - A mid-game connector edit or mechanism install now publishes through the keyed world path. Before this, the live operation projector raised "Unprojected committed state".
    - The harness publishes `portal_plate`'s and `gas_vent_plate`'s setups.
    - O1 on portal_plate: `cells:field:hazard` 6/90/21 → 0 on G1/G2/G3. `body.normal_hp` (E3-bodies) is counted at one more checkpoint, the published setup.
    - Test: `test_live_connector_edits_and_mechanism_installs_publish_to_every_seat`. It raised before the fix.
    - The 12 gallery cases are byte-identical apart from portal_plate's published updates (its setup is now published). The trap tests and tests/player, ai and architecture match r29.
- 2026-10-18: **E3-world merged into codex/event-native-deltas (e85b4af33; lane head 3fb491bc9).**
  - **What it does:** the schema-16 world wire. The server keeps no per-seat world copy.
    - Keyed rows come from E2's `AppliedWorldFact`; entering rows are read from `SessionProjection`'s world as of the occurrence. Static rows go once per seat.
    - Compact placement and content-addressed boundary structures.
    - Overlapping roots form one walk group, which fixes the stale Prone.
    - Mechanism installs and connector edits are now published, which closes E1's open item and E0's portal finding.
  - **Gates vs E0's base:**
    - O1 classes equal the base: Prone 41 → 0, portal hazard → 0;
    - O2 27/27;
    - O3 equal except the Prone fix;
    - O4 bounded;
    - transcripts identical except Fireball's repeat-write nodes (accepted);
    - sweep = r29;
    - pyright 0 new.
  - **Largest seat KB (non-log), base → new:**

    | Row | G1 | G2 | G3 |
    |---|---|---|---|
    | Fireball | 202 → 161 | 179 → 137 | 188 → 146 |
    | Sleet drop | 86 → 89 | 39 → 116 | 58 → 140 |
    | Daylight | 84 → 92 | 45 → 140 | 66 → 95 |
    | mass_healing_word | – | 759 → 383 | – |

  - **Follow-ups, encoding only:** content-addressed tile static rows and columnar object rows (measured: Sleet drop G2 → 79, Daylight G2 → 102), plus tests T6, T8 and T9.
  - **Native follow-up:** `BaseItem.destroy` and the torch's `put_out` write the same object's FLOOR fact two or three times.
- 2026-10-18: **AI-step round 2 merged (b53e533c6).**
  - Three changes: one contact trace per subjective attack admission (`ObjectContact` through `rule_admission`); an incremental AI fold that keeps rows whose inputs are unchanged, with cell lists moved by deltas; and Jump range once per scan.
  - **Seeded long game:** Choices −13.6 %, advances −5.2 %. ai_decision op 4: 179 → 172 ms.
  - **Profile of op 4:** of 447 ms profiled, 164 ms is sensory settlement over 6 steps (~0.9 ms per observer settlement). All 30 observers re-settle fully at every step. For 29 of them the only change is the mover's contact position and its torch's light.
  - **Proposed next (for the human):** a settlement fast path. Observers whose sight inputs held update only the moved contact and the cells inside the light's old and new radius.
- 2026-10-18: **E3-world encoding follow-ups (codex/enp-e3-world-encoding, from e85b4af33: 26b4cd834, 85bc0cfcd, 11a37f971, 25cb86820; merged as 7feebee85).** Encoding only, no rule change.
  - **1. Tile looks are content-addressed.** A tile's surface and name travel once per value per seat (`tile_looks`, keyed by a digest), and a tile's static row names its look. On its own this took mass_healing_word G2 from 382.7 to 312.5 KB: its 1,070 tile static rows share one look.
  - **2. Object rows travel as columns** (`ObjectColumns`, `PlacementColumns`, `Column`: `rows` left out selects every row; a column with no non-default value is left out). Vectors (w13 added: placed and unplaced rows in one update) and the Godot note are updated. On small updates the per-column wrappers cost a little: Fireball's 11 object rows, spread over several updates, go 4.6 → 5.7 KB.
  - **3. The missing tests.**
    - **T6** (`tests/player/test_object_look_static.py`): a door opened, closed, damaged and destroyed; a chest looted with its contents; a Wall of Stone section cut by Disintegrate. Each scenario's completed versions are folded with `world_facts`, and every object's look stays its first.
      - It failed on the cut: a construction's geometry (`removed_sections`) changes in place, so a seat kept drawing the uncut wall. As the brief's R3 prescribes, `construction_geometry` moved from `ObjectLook` to `ObjectState`. No gallery case cuts a wall, so O1 never saw it.
    - **T8:** `world_placement.boundary_sides` is the one definition of a boundary's faces and incident cells. Publication, the fold's support cells and the seat oracle all use it. An architecture test forbids the direction tables in those modules; the only exception is world_facts iterating neighbours.
      - The test covers the player modules, world_facts and the seat oracle. `dnd/core/gridmap.py` has a second definition, which it does not cover: `BOUNDARY_FACING` plus `contact_surface`, the cells a contact lands on.
      - **Follow-up:** replace gridmap's `BOUNDARY_FACING` and `contact_surface` with `world_placement.boundary_sides`, and extend the test to gridmap.
      - The extended import rule `projection` ↛ `reduction` waits on E3-bodies. The projection still imports reduction's body fold: `apply_record_fact`, `change_membership`, `commit_current`, `fold_senses`, `observe_body`, `observed_actor`, `occurrence_order`.
    - **T9:** O1 names an object kept at its old placement on a re-entered cell, and a stale suppressed cell on a re-entered cell.
  - **4. Review fixes (antislop and anti-OOP).**
    - Commit 3 had changed `placement_support_cells`: it added a boundary's own cell even when every band there was removed. The sweep caught this in `test_recorded_world_object_queries`. The rule is restored, and a test case now pins it.
    - A column's `rows` is None for every row, so `RowBits` keeps its one meaning.
    - Column schemas are named by their value type. Before, the TypeScript SDK numbered them `Column1…Column14` by order.
    - `members` keeps its minimum of 1.
    - The round-trip test sets every field, and a test checks that the columns cover every field.
  - **Largest seat update, KB** (E0's base 60adf05eb → lane head e85b4af33 → 25cb86820; seeded oracle runs):
    | Row | G1 | G2 | G3 |
    |---|---|---|---|
    | Sleet drop | 85.7 → 88.8 → 88.7 | 38.6 → 115.5 → 79.9 | 58.1 → 139.7 → 102.2 |
    | Daylight | 83.7 → 92.3 → 92.2 | 45.0 → 139.9 → 102.7 | 65.5 → 95.4 → 84.3 |
    | Fireball | 202.0 → 160.7 → 161.7 | 178.7 → 137.2 → 138.1 | 187.7 → 146.3 → 147.4 |
    | mass_healing_word | 49.1 → 48.5 → 48.4 | 758.8 → 382.7 → 276.1 | 49.1 → 48.5 → 48.4 |
    | room_reentry door_open | 42.1 → 43.6 → 43.4 | 27.8 → 87.6 → 69.2 | 28.0 → 30.1 → 29.3 |
    - room_reentry's largest update over all its operations is door_open, except base G2 (48.7 KB, move_to_21_6).
    - G2 and G3 are still about 2× the base on Sleet drop, Daylight and door_open; G1 is about even. What dominates now is re-entered walls.
      - Sleet drop G2 (79.9 KB): the world part is 45.6 KB, the rest about the base's size. That 45.6 KB is object columns 23.5 (about 220 re-entered walls: uuids 8.3, placements 4.0, names 3.0, structure ids 2.6), tile columns 14.4 and residues 7.4.
      - Daylight G2 (102.7 KB): objects 24.5, residues 18.1, tile columns 15.6.
  - **Gates** at 25cb86820, against E0's base (60adf05eb, seeded), on 9 cases × G1/G2/G3:
    - **O1:** no world class appears. Every class count equals the base's, apart from the lane's known differences: round_step_zones' Prone fix, and portal_plate's published setup.
    - **O2:** 27 of 27 spool replays pass in a fresh process with hash seed 1.
    - **O3/O4:** equal to and bounded by the base, except round_step_zones (the Prone fix) and portal_plate. portal_plate's setup is now published, so O4 names the setup's hazard cells and trap effects. Against the lane head, portal_plate's views are equal and its knowledge is bounded.
    - **Member bits:** 18 runs on G1 and G3, 0 mismatches.
    - **Transcripts** (`world-16`): events and logs are identical everywhere. Published updates outside `world_updates` are byte-identical to the base, except Fireball's renumbered nodes and portal_plate's setup. Against the lane head (Fireball, portal_plate), they are byte-identical.
    - **Sweep:** 66 failures, the same set as the lane's (r29's 64, plus 2 `cr0_evidence` tests that need git).
    - **pyright:** 0 new against e85b4af33.
  - **Not done (reviewers' minors, left for the coordinator):**
    - TypeScript column names keep pydantic's generic spelling (`ColumnInt_`, `ColumnTuple_CardinalDirection__________`). They are stable now, but clean names would need concrete column types per value kind or a schema rename hook.
    - Each field's default is still written in the pack filter, the unpack default and the dataclass. The round-trip test pins them.
    - `content_composition` and `projection` read column internals.
    - `facts.py` still holds the column types; they could live in a module below it.
  - **Rulings (coordinator, at the merge):**
    - `construction_geometry` moves to `ObjectState`: accepted. It fixes a bug merged with e85b4af33: after a Disintegrate cut, a seat kept drawing the uncut wall.
    - `player_schema_version` stays 16, although the wire and the protocol digest changed: accepted, because the E-series is unreleased.
    - No squash. Commit 3 alone fails `test_recorded_world_object_queries`; commit 4 fixes it.
- 2026-10-18: **Shared-vision prototype (Q5; test-only, codex/shared-vision-proto 09b97617f..8da90b428, NOT merged).**
  - **What it adds:** the `--seats character-shared` layout (one seat per character, observers = the side), a 3-faction roster, and a dedupe that composes once per audience in the event-major walk.
  - **Gates:** exactness against the naive shared run (every seat's frames and client digests identical); O1–O4 equal; 0 controller-only leaks to teammates.
  - **Publication ms (G1 / G2 / naive shared / deduped shared, loaded machine):**
    - Fireball 67 / 463 / 934 / 452;
    - CoD 60 / 437 / 824 / 486;
    - SG step 53 / 177 / 1057 / 276.
  - **Deduped ≈ G2, not G1.** Occurrence numbering and controller-only nodes are per seat, so encoding and the per-seat node walk can't be shared. The per-seat combat log is 413 of 1,478 profiled ms (Q8 addresses it).
  - **Proposal for the human:** per-side occurrence numbering plus a per-seat controller-only overlay. That makes a side's publication ≈ G1 plus the overlay. It is a wire change after E3-sensory.
- 2026-10-18: **Settlement fast path merged (4cefc2424; Q7).**
  - **Mechanism:** the objective light change is computed once per settlement. An observer whose sight inputs held keeps its view and is re-lit only at the changed rows. The proof is `_changed_light_rows`' docstring.
  - **Fast-path rate:** ai_decision 177 of 183, SG walk 553 of 571. Fireball, Wall of Stone, Sleet and Daylight take the full path by design.
  - **Gates:** exact; recorder and transcripts 0 differences on 10 cases.
  - **Timing:** ai_decision op 4 203 → 185 ms (settlement only 184 → 141); SG moves −3 to −14 %.
  - **What remains for op 4:** passive perception re-read (~9 ms; values have no revision key); building SensoryUpdateEvent (~7); identity grants at register (~7); contacts (~24); the AI decision itself.
  - **Tooling:** scratchpad fanout/record_steps.py needs the new `measured_request(driver, mode, kind, request)` signature (fixed copy in sf/). wf/fov_oracle_batch.py is stale.
    - The wire changed and the protocol digest with it, but `player_schema_version` stays 16. That is fine as long as no client consumes 16 yet.
    - Commit 3 alone fails `test_recorded_world_object_queries` (commit 4 fixes it). Squash commit 4 into commits 1-3 if one commit per item matters at merge.
    - `construction_geometry` as state is a public wire change. It fixes a bug merged with e85b4af33, which is also on codex/enp-e3-bodies: after a Disintegrate cut, a seat keeps drawing the uncut wall.
- 2026-10-18: **E3-bodies (codex/enp-e3-bodies, on e85b4af33 and 7feebee85; head b8268ec2c; not merged).** The schema-16 bodies and items wire: the server keeps no per-seat actor or item copy.
  - **Commits:** 5e937d6a1 (startup-damage grant fix, failing first), cb6b25671 (types, client fold, golden vectors `sdk/protocol/fold-vectors/bodies/`), f7f68cca9 (projector switch), f9c682f88 (oracle reference from `entering_body`; fold-equality assertion), 27086b960 (SDK), e0267745d (Godot note), f49ed8a2c (a controlled body never enters through the composed view), 282b8bfd1 (both views once per event; static parts in the walk's pending), b11720e68 (merge 7feebee85), 4ec6caa5a (brief §4 tests), c6ef760b1 / bca2a0922 / b8268ec2c (clean-ups).
  - **The rules:**
    - One conversion, `bodies.change_rows`: an event's E2 record becomes rows once, for every seat. Scalars are the record's after-values; memberships, holdings and item operations are keyed against the session fold's value before the event (coordinator ruling (a)). `change_views` turns them into the controller's and the observer's rows once per event; each seat picks one through `actor_view` (the controller; else a born body, its owner by the event's identity grant, another holder by a visual contact).
    - One table, `DISCLOSURE`: controller for durations, inventory and item state; observer for stats, memberships, layers, weapon set and the effects of worn items; nobody for healing_blocked and affinities. INTERNAL memberships have no rows.
    - A body entering a seat's composed view (a member's changed contact the seat did not hold) goes out whole as a `BodyRecord`, its birth only the first time; a controlled body enters once, when the session holds it. Leaving sends nothing (no known removal).
    - H3: a living body remembered on a cell the seat sees, which is not a composed contact, loses its position.
  - **Why two actor folds (H4, confirmed by the coordinator):** `CaptureCheckpoint.actors` is capture's: it is advanced to the operation's end before any seat walks, its frozen per-version rows are the admission evidence, the AI fold's and the recordings' input, and it takes an arrival at its effect phase. `SessionProjection.actors` is projection's: folded version by version during the walk, so each event's rows are keyed against the value just before that event. Both use the same functions (`fold_birth`, `fold_completed_actors`, `ended_lifetime`) and are equal at every operation end (gallery_crowd's `after_operation` raises otherwise; test_emitted_update_replica asserts it). Each has one writer (architecture test).
  - **RecordedSequence 6:** the startup world interval carries its versions' actor change records; engine-free replay builds bodies from births and records. Nothing of it reaches a spool, the wire or a replay's output.
  - **Gates** at c6ef760b1 (the head's code), seeded, 30 cases x G1/G2/G3, against 7feebee85 (and E0's 60adf05eb):
    - **O1:** every class 0 on all 90 runs, no new class. The base had G1 normal_hp 468, conditions 181, extra 3; G2 21,703 / 2,144 / 81, life_state 17; G3 3,032 / 576 / 15, life_state 1.
    - **O3:** differs from the base only at those bug sites: normal_hp and life_state (the grant fix) and room_reentry's ghost body (H3).
    - **O4 exceptions (the only two):** (1) setup facts at initialization: a seat seeing a creature at setup learns its roster starting damage (normal_hp, life_state) in its initialization; every such leaf is first held at operation 0. (2) H3: `last_visual_position` null on a ghost's cell (1 / 14 / 3 leaves), no information.
    - **O2:** 90 of 90 replays (hash seed 1, resume cut).
    - **Logs:** node entries and appends, and content_additions, identical to 7feebee85 on 90 of 90 runs (against E0: the 3 cases E3-world changed).
    - **AI knowledge:** equal on E2's 10 cases.
    - **Sweep:** 64 failures, 7feebee85's set (its export adds the 2 `cr0_evidence` tests that need git); E1's 3 xfails are green.
    - **pyright:** 0 new on the touched files.
  - **Bytes** (largest seat update, non-log, 7feebee85 -> head, KB):
    - **Re-entry rows (H6, named):** Sleet drop 77.7 -> 102.2 (G2), 100.1 -> 113.6 (G3); Cloudkill drop 97.3 -> 132.9 (G2), 123.1 -> 140.2 (G3); Daylight 99.9 -> 135.3 (G2); room_reentry 68.7 -> 94.7 (G2 door_open), 28.7 -> 34.1 (G3); mass_healing_word's first sight 275.3 -> 290.2 (G2). On G1 every one of them is lower (Sleet 86.2 -> 75.5, Cloudkill 83.8 -> 74.9, Daylight 88.6 -> 80.4).
      - What dominates: a re-entering observer's body is ~1 KB, against the plan's ~250 B estimate: its visual loadout ~720 B (each layer's uuid, item id and slot) and its items' records ~220 B (uuids, the looks already sent). Sleet drop G2: 20 bodies, 26.3 KB.
    - **Other rows that grow** (1-10 KB): Fireball 120.4 -> 125.6 (G1), Circle of Death 128.3 -> 137.7, Choices 129.5 -> 135.3, Ice Storm 64.9 -> 68.0, mass_heal, Magic Missile, Chain Lightning, Turn Undead, SG walk +0.8.
      - Cause: E2's record of a condition event names every resulting stat, and the rows carry them as they are (ruling (a)), so INTERNAL condition events now send stat rows (brief §4's expected "INTERNAL-stats actor_change facts").
      - Adopted (coordinator): a scalar row only when its after-value differs from the session fold's value of that field before the event, the collections' rule. Measured on a scratch tree first: Fireball +5.2 -> +2.8, Circle of Death +9.4 -> +5.1, Choices +5.8 -> +3.4, Ice Storm +3.1 -> +1.7, SG walk +0.8 -> -4.5, O1 0.
      - **Native follow-up:** E2's records of condition events name every resulting stat (`resulting_stats`), changed or not; the record could name only the changed ones.
    - Worst non-log row: G1 Circle of Death 137.7, G2 mass_healing_word 290.2, G3 Cloudkill 140.2 (against 100).
  - **ms** (3 ordinary runs per case and layout, head and 7feebee85 run side by side; LOADED, load average 10-25 from other lanes, so single rows move ±20-50 % between runs of one tree):
    - Sum over every op of the min-of-3 publication ms: G1 1,505 -> 1,421 (-5.6 %), G2 5,266 -> 5,030 (-4.5 %), G3 2,124 -> 2,005 (-5.6 %). No op's publication is more than 15 % and 5 ms slower.
    - Total ms, same measure: G1 -3.5 %, G2 -2.7 %, G3 -1.5 %; the two ops beyond 15 % (caster_steps op 2, choices_fighter op 0) move in native time or have no publication.
    - Worst op over 100 ms (median, head): G1 ai_decision 221, Choices 171, Fireball 161; G2 Circle of Death 566, Fireball 561, Choices 474; G3 Fireball 233, Circle of Death 224 (all as before; E6's).
  - **Expected test changes** (each follows the removed wire types or the rules): test_body_fold_agreement (xfails removed; row-reproduction cases), test_operation_audience_reduction (BodyRecord), test_high_level_spell_transport (bodies), test_duration_spatial_review (`effects`), test_spell_ownership_recording and test_recorded_boundary (no ProjectionState actors), test_light_source_projection (holdings through births and records), test_emitted_update_replica (the server holds no bodies; the folds agree), test_patch_fields (item effects partition), test_delivery_review, test_transport_review and both SDK transport tests (`observations` gone), test_change_records (replaced_item reaches holders), test_dependency_boundaries (bodies never imports the client fold). New: test_startup_setup_disclosure, test_body_fold_vectors, test_body_entering, test_body_disclosure, tests/architecture/test_body_change_single_path.
  - **Defaults taken:** `dnd/player/bodies.py`; whole effect tuples per item; duration-only changes as duration rows; `ConditionMember` without event fields; typed row classes per value shape; the log view and the census as scratch devtools (logview.py, bodycensus.py), not repo code.
  - **End reviews:** antislop and anti-OOP. Fixed: both views once per event, ItemsSent gone, the brief's §4 tests, one writer per actor fold, the duration helper, `audience.granted`, the item gate's one definition, stale comment and metric, Godot edge cases. Kept with the reason: healing_blocked and affinities in the table (brief §1.4), E2's server fold untouched, the reviewers' renames.
  - **Open, escalated (brief §1.10/§2.5):** capture still derives each seat's `ActorAdmission`s (`_derive_admissions`, `acquired`, `newly_known`) on the live path; their only live use is the combat log's names, which are identical to the base. Moving the names to the walk needs the native log per node in `CompletedLineage`, a recorded-format change beyond RecordedSequence 6's scope.
- 2026-10-18: **NPC content merge (codex/npc-merge from 4872892f0; NPC lane codex/npc-abilities-mechanics ef82cb7ba).**
  - **Commits:**
    - 75ecbf29e, the merge. Conflicts are resolved onto the integration's structure: Attack's shield attack goes through `weapon_reach`/`weapon_attack_admission`/`rule_admission` with ObjectContact; `weapon_attack_range` takes the shield, so the reach prefilter measures it; ShieldBash overrides `rule_admission`; the `empty_*` factories are kept.
    - fb17e4422 removes `dnd/core/encounter_facts.py`, a cast over the contribution registry; Encounter now owns `OpeningTurnFacts`.
    - 9c0f7cdc3, review fixes:
      - Leadership loses its language gate. No creature data authors languages, so it disabled Leadership for every SRD ally.
      - Assassinate requires the assassin's own first turn.
      - The Gladiator numbers move out of core `ShieldAttackSpec` into ShieldBash.
      - `register_multiattack(attack_replacement=...)`.
      - Innate casts use `alt_extra_costs`.
      - Typed `InnateReactionSpell` rows.
      - One `register_protection`, and Protection is no longer retired.
      - Data fields replace identity checks.
    - 2fab113d8, harness (see below).
    - 03a249f1c, the contract with `encounter_end`.
  - **Harness:**
    - What changed: Help Attack is a new standard template on every creature, and its identity draws shifted every later seeded identity. `gallery_transcript.py` now routes identities drawn while a `_POST_BASELINE_TEMPLATES` instance (HelpAttack) is constructed to a fourth seeded generator. The seat oracle records through it.
    - Result: against the 4872892f0 export, published updates are byte-identical. Events differ only by this branch's new fields: `TakeDamageEvent.critical_hit`/`damage_save` and `AttackEvent.shield_attack`.
  - **Contract:**
    - `ConditionRemovalTrigger.ENCOUNTER_END` is on the wire. The schema, identity, openapi, field ledger, Python and TypeScript types were regenerated; `player_schema_version` stays 16.
    - `devtools/generate_typescript_sdk.py` cannot run, on 4872892f0 too: it imports the retired `server.api_models`. The TypeScript types come from `sdk/player-typescript/tools/generate.mjs`.
  - **Gates at 03a249f1c:**
    - **Transcripts (5 cases vs the 4872892f0 export):** published updates are byte-identical. Events differ only by the new fields: 60 TakeDamageEvent versions each in fireball and choices_caster, and 14 AttackEvent versions in ai_decision. spirit_guardians_walk and wall_of_stone are identical.
    - **Seat oracles (fireball, spirit_guardians_walk × G1/G2):** O3 equal. O4's only leak class is the public `content:` catalog (704 → 877 leaves per seat: the new public NPC declarations). O1 classes equal base.
    - **Sweep:** 64 failures, all in r30. test_protocol_schema_review passes again.
    - **NPC suites:** 906 passed, 22 xfailed. pyright: 0 new (474 vs 474). SDK tests: TypeScript 64/64, Python 91/91.
  - **Follow-ups (deferred, with owners):**
    - **Published order depends on the seeded uuid stream.** Publication and sensory processing follow identity order, so one extra template draw reorders observers, contacts and forced movements. Owner: publication lanes (E3).
    - **AttackSource unification.** This branch added `ShieldAttackSpec` beside `NaturalWeaponSpec`, threaded as a second Optional through Attack, Entity and Equipment (including Equipment's hard-coded `"Strength"` damage context). Proposal: one tagged attack-source type on Attack/AttackEvent, read once in Equipment. Owner: combat mechanics / NPC lane.
    - **Save-for-half carrier.** `TakeDamageEvent.critical_hit`/`damage_save` are new in this branch. About 25 delivery sites halve locally and attach the save by hand; Evasion reads the result in Health. Proposal: callers pass unreduced damage and the save, and one owner applies the fraction, merged with `resolve_saved_spell_damage`. Owner: combat mechanics.
    - **Recipe scaffolding.** Install chains and dependency chains are kept in sync by hand, and `_equipped` is repeated, across the humanoid, undead and fiend rosters. The author's plan forbids an NPC rules DSL; test_creatable_models and the declaration tests catch drift. Proposal: a shared roster helper if wanted. Owner: NPC lane.
    - **Shared foundations.** MAGE, BERSERKER, GLADIATOR and ARCHMAGE are defined in both `roster_humanoids` and `undead_roster`, and the SRD stat arrays are copied from `srd_roster`. The undead `archmage`/`wight` flags differ from the humanoid fields. Proposal: one foundation table. Owner: human (product), then NPC lane.
    - **Zombie Slam.** The NPC zombies use a NaturalAttack Slam; the SRD Zombie has the intrinsic `weapon.creature.zombie_slam`. The numbers are the same. Owner: human (product).
    - **Leadership gaps.**
      - No sight check.
      - "Ends if the knight is incapacitated" is a pause.
      - "Understand" is not enforced: no language data is authored.
      Owner: NPC lane; language data is a human content decision.
    - **Assassin poison.** Coating costs an action, which spends the first turn Assassinate needs. Owner: human (product).
    - **Shield Bash 1-of-3.** Shield Bash replaces at most one of the Gladiator's three attacks; the SRD allows three melee attacks. This is the author's choice. Owner: human (product).
    - **NPC test slop.** Recipe-data re-assertions, the coverage test driven by agent_docs CSVs, private-state asserts (`spell_damage_resistance_sources`, handler dispatch counts), and fake provider wiring in `test_innate_reaction_spell_costs`. Owner: NPC lane.
    - **test_183 icon ledger.** `tests/manual/test_183_content_icon_bindings.py` has no rows for content newly public from the merged lanes (e.g. `creature.oath_captain_devil`, `spell.charm_monster`) and needs regenerating. Owner: content/icon ledger.
- 2026-10-18: **NPC authoring merged (a4eb223b1; npc-merge 507c6ab6c).**
  - 123 new native NPCs (148 identities) and their shared mechanics, after review and repositioning.
  - Multiattack is one public parametrized action: 60 declarations with 6 patterns are retired.
  - The contract is regenerated with `encounter_end`; schema stays 16.
  - **Player-visible rules:**
    - Assassinate applies on the assassin's first turn only;
    - Brute adds a die of the held weapon (goblins included);
    - Leadership is hear-only;
    - Help Attack is a new standard action;
    - Shield Bash replaces 1 of 3 Multiattack attacks;
    - Multiattack labels are derived from the steps.
  - **Gates:** published updates byte-identical; O3 equal; O4 only the public catalog; sweep nothing new; pyright 0 new.
  - **Follow-ups with owners are in the lane's entry above.** Notable ones:
    - one attack-source type;
    - one save-for-half carrier;
    - summon data-only subclasses (~12) could be parametrized like Multiattack;
    - the `_POST_BASELINE_TEMPLATES` harness allowlist;
    - NDClient references to retired multiattack ids.
- 2026-10-18: **Revision stamps for re-entry, world part (codex/enp-revision-stamps: 5755b3a56, 7a628ad99; not merged).** Approved by the human.
  - **Rule.** A tile entering perception (an entered cell), or an object entering perception (newly observed, or touching an entered cell), travels whole only when it was written since the seat last had it whole. Otherwise it is sent as `tiles_unchanged` (a cell mask) or `objects_unchanged` (uuids of objects on entered cells), or not sent at all (an object off them).
    - An object is also sent whole when it shows a face the seat's last row of it did not, or when its observing members differ.
    - Suppressions, remnants and cast-lineage concentration slots always travel whole. They are disclosed by view or by seat knowledge, not by the record.
    - Connectors still travel whole.
  - **Revisions.** The single session fold (`_fold_version`) records each record's last write, as a native index, from `AppliedWorldFact`. A tile's revision covers its cell: scalars, light, own conditions and residues. An object's covers its uuid. The fold refuses to go out of native order.
  - **Seat stamps.** `ProjectionState.revision_stamps` holds the native index at which the seat last had the record whole, plus the faces and members of the object's last row.
    - Each walk derives `StampChanges` from the updates it builds, and they join the seat's stamps at emission, next to the static rows.
    - Only a whole send or an unchanged confirmation advances a stamp. A keyed change does not, because an unpublished write may precede it.
    - The rule is `revision_stamps.unchanged_since`, for E3-bodies to apply to `BodyRecord`.
  - **Restore.** `stamp_replay.replay_revision_stamps` rebuilds a seat's stamps from the world updates the seat received, folded by the client fold. It needs the seat's `public_cursors`, because the spool carries no native indexes. There is no production reopening path; without stamps, every re-entry is whole.
  - **Gates** (9 oracle cases × G1/G2/G3, seeded):
    - **Per record:** every seat's client state digest equals the 7feebee85 baseline's on all 27 runs and every record. Unchanged therefore leaves the client exactly as whole did.
    - **O1–O4 against E0's base:** no world class. Only the lane's known differences remain (round_step_zones Prone, portal_plate's published setup, Fireball's renumbered nodes).
    - **Against 7feebee85:** the O3 views are equal and O4 knowledge stays bounded on all 27 runs. Outside `world_updates`, the transcripts are byte-identical.
    - **O2:** 27/27 pass, 4,294 records replayed. The restored stamps equal the live ones; the excuse for one-sided stamps written since was used 0 times.
    - **Sweep:** 66 = r29's 64 plus the two `cr0_evidence` tests that need git.
    - **pyright:** 0 new.
  - **Largest seat update, KB** (E0 base 60adf05eb → 7feebee85 → stamps):

    | Row | G1 | G2 | G3 |
    |---|---|---|---|
    | Sleet drop | 85.7 → 88.7 → 84.9 | 38.6 → 79.9 → 56.2 | 58.1 → 102.2 → 78.8 |
    | Daylight | 83.7 → 92.2 → 90.9 | 45.0 → 102.7 → 75.4 | 65.5 → 84.3 → 77.2 |
    | room_reentry door_open | 42.1 → 43.4 → 42.3 | 27.8 → 69.2 → 33.0 | 28.0 → 29.3 → 28.1 |
    | mass_healing_word | 49.1 → 48.4 → 48.4 | 758.8 → 276.1 → 270.7 | 49.1 → 48.4 → 48.4 |
    | Fireball | 202.0 → 161.7 → 161.7 | 178.7 → 138.1 → 138.1 | 187.7 → 147.4 → 147.4 |

    - mass_healing_word is first sight: new records, which stamps cannot help.
    - Fireball's largest update carries only records written now.
  - **What still travels** (census summed over seats).
    - Sleet drop G2 tiles: 14,619 unchanged, 2,366 written unseen, and 4,678 that were written while seen (delivered as keyed changes, so the stamp did not advance).
    - Daylight G2 tiles: 7,524 unchanged, 870 written unseen, 3,543 written while seen.
  - **Memory:** about 1,650 tile and 250 object stamps per seat, about 0.31 MB per seat as Python objects. The session's revisions are about 0.25 MB.
  - **For the human:**
    - (a) Whether a record arrives unchanged or whole tells the seat it was written while unperceived, even if the value ends the same (a door opened and closed unseen). Before stamps, re-entry was always whole, so no such signal existed. The alternative that closes the channel is a digest of the disclosed value.
    - (b) A finer advance rule would save the "written while seen" re-sends: advance on a keyed change when the record's revision before that write is not after the stamp. This needs approval and a proof test.
  - **Follow-ups:** the plan's vector w15 was folded into w14 (an entered cell's unsent torch is dropped). The wire names are `tiles_unchanged`/`objects_unchanged` (the plan said `*_kept`).
- 2026-10-18: **Digest stamps for re-entry, world part (codex/enp-revision-stamps; supersedes the revision-stamps entry above).** The human chose digests.
  - **Stamp.** Per seat, a stable digest (SHA-256 of the record's JSON) of each world record as the seat holds it: sent whole, or confirmed unchanged. Objects add their faces, members and held placement.
    - A keyed change keeps the stamp only while the record still digests to it, and drops it otherwise. The review's hole was a write folded but published to the seat late, under an observed source. It is now a test.
    - Suppressions, item effects and concentration slots always travel whole.
  - **Rule.** `world_stamps.unchanged_since(stamps, key, digest)`, for E3-bodies.
  - **Side channel closed:** a record written and written back unseen re-enters unchanged.
  - **Cache.** Tile digests are cached per value by the session (`world_digests`), and `_fold_version` forgets them on each write.
  - **Restore.** `stamp_replay` refolds and redigests the received updates. It needs no numbering, and O2 requires equality.
  - **Close-out gates** (at 362895a17 plus this entry; sleet_storm, darkness_daylight and room_reentry × G1/G2):
    - Per record, every seat's client state digest equals the a4eb223b1 baseline's.
    - O1 classes are equal; O3 equal and O4 bounded against the baseline.
    - O2 6/6 with restore.
    - Transcripts outside `world_updates` are byte-identical.
    - tests/player: r29's set.
    - pyright: 0 new.
  - **KB, largest seat update, a4eb223b1 → digests (G1 | G2):** Sleet drop 77.6 → 73.9 | 104.1 → 80.4; Daylight 83.1 → 81.9 | 137.6 → 110.1; door_open 43.4 → 42.3 | 95.3 → 59.0.
  - **Not done:** a stamp advance on keyed changes that change the value, which needs per-seat unpublished-write tracking and the human's approval. The unsound version of it measured Sleet/Daylight G2 world 21.8/31.5 → 10.1/10.4 KB.
- 2026-10-18 (session end): **Digest stamps merged (61b51584e).** G2 largest KB: Sleet drop 104 → 80, Daylight 138 → 110, door_open 95 → 59. A change seen in view keeps the stamp only if the value matches (sound against late publication).
  - **Unfinished, committed as WIP on their branches:**
    - E3-sensory (codex/enp-e3-sensory): S-3 wire switch;
    - E3-bodies follow-ups (codex/enp-e3-bodies): admissions removal, the build-once combat log (Q8), visual-loadout encoding, body stamps.
  - **Next session, in order:**
    1. finish and merge E3-sensory and the E3-bodies follow-ups;
    2. Q9, one side part per faction plus a per-player overlay (design on codex/shared-vision-proto);
    3. E6 quiet re-time and the final table.
  - **Follow-up 1 (4cd5e36f5, on the merged head 3b4aefae2): capture keeps no per-seat admissions** (coordinator, brief §1.10/§2.5).
    - `CompletedLineage` carries each retained node's native combat log (`RecordedCombatLog`: the private archive encoding, grants kept; RecordedSequence 6). Its per-seat admissions are gone.
    - `SessionProjection.names` (every born actor's name, never popped, written by `_fold_actors`) replaces `CaptureCheckpoint.names`.
    - The walk projects each node's entry with the names of the bodies the seat holds at that event (births sent and the walk's, inclusive), the op-start connectors and content ids, and one memo per group and seat. The initialization's entries stay as its capture projects them.
    - Deleted: `acquired`, `newly_known`, the per-operation `_derive_admissions` call, `known_actor_uuids` and the capture log inputs of `capture_lineages`, capture's `stage_*`. `_derive_admissions` remains only for the startup interval's presentation target. A capture of versions the checkpoint has passed is refused once per context. `capture.reduce_lineage` folds births.
    - G2 Fireball: capture 149-189 → 18-22 ms (30 seats); projection 222-272 → 322-350 ms, the per-seat log projection having moved into the walk.
    - Gates (against 3b4aefae2, 30 cases x G1-G3): log entries and content_additions identical 90/90; O1 0; O3 equal; O4 bounded; O2 18/18 (six-case subset); tests/player + architecture 0 new; pyright 0 new.
  - **Follow-ups 2-4 (2026-10-19), each gated by one batch** (log entries and content_additions identical, O1-O4 on fireball and spirit_guardians_walk x G1/G2, O2 on Fireball G2, tests/player + architecture 0 new):
    - (2) 1d279d944, build-once combat log (coordinator: "do it only once then anonymize", made exact): each seat decides what of a native entry it may see; the entry is rendered once per distinct decision and shared (`SharedRenders`). G2 Fireball publication 339.7 -> 300.6 ms (median of 3); its log projection 62 -> 31 ms.
    - (3) d6681c02a, visual loadout by content id (sent once per seat), item records carrying nothing left out; vectors v8/v9; SDK regenerated. Bytes unchanged on the gated cases (their largest records have no re-entering body).
    - (4) add500779, body digest stamps (`world_stamps.unchanged_since`): a re-entering body whose record digests to the seat's stamp is confirmed, not sent; a fact the seat is sent drops its stamps of the bodies the event wrote; records the emission maps (application cursors, concentration slots, item effects) travel whole. Merged with E3-sensory (65e480cd8) at 55cdecfdc.
    - Found on the integration head 65e480cd8, not from this lane: the TS SDK tests no longer compile (light-observations.test.ts: LightRow.revision, affected_tiles; transport.test.ts: PlayerOperation.audience), and sdk/python/tests fail (test_light_observations) and hang.
- 2026-10-18: **E3-sensory lane (codex/enp-e3-sensory), walk-independent part, waiting for E3-world and E3-bodies.**
  - **Settlement marker (f08ef192c).** `SensoryUpdateEvent.settlement` is a counter on `SpatialSensesSystem`, drawn once per `_emit_settlement` pass and once per explicit refresh.
    - A refresh is its own settlement even when a group's settlement emits it: it has no cause, registers at once as its own root, and is captured apart from the group. A settlement composes only within one captured group. (Coordinator: accepted.)
    - Gate: transcripts on 6 cases are identical apart from the field, and published bytes are byte-identical.
  - **Schema-16 sensory types.** They are staged in `dnd/player/sensory_facts.py`, imported only by the client fold and the vector tooling. At the projector switch they move into facts.py and the module is deleted.
  - **Client reference fold:** `reduction.fold_composed_sensory`.
  - **Golden vectors V1–V8:** `sdk/protocol/fold-vectors/sensory/`, from `devtools/fold_vectors_sensory.py`.
  - **Shape choices to confirm:**
    - client lights move out of `senses` into `PlayerState.light_sources` (`PlayerLightSource`), because `PerceivedLightSource.revision` is required and server-only;
    - attribution is three dicts (`entity_members`, `object_members`, `effect_members`).
    - O1 and seat_oracle must read both from these places at the switch.
- 2026-10-18: **E3-sensory S-1 to S-3 (codex/enp-e3-sensory): one composed sensory change per settlement on the wire.**
  - **S-1 (33f4f9c69, c585c44fa):** `apply_settlement` composes a settlement once from the members' snapshots (visible parts only; contacts by (visual, -uuid); no cursors or absences); a terminal departure ends the contact for every member. Fast gates (7 cases × G1/G2/G3): O1 0, O2 0, O3 equal, O4 bounded, logs identical.
  - **S-2 (a2dbc38b4):** the envelope once per update, the spell declaration on its cast, lineages and in-group parents derived, REMOVED without positions. Same fast gates, all green.
  - **S-3 (the switch):** the schema-16 types moved into facts.py (`sensory_facts.py` deleted). The seat's node at a settlement's first member event carries one composed `SensoryFact` (`_settlement_fact` over the `ComposedChange`): records entering travel whole, records perceived before and after as patches (sightings, light sources: changed disclosed fields only), records leaving by key; member bitsets per contact and effect row (left out on one-observer seats); retired cells (D1 (a)) only for effects the seat was sent; an effect's duration only to its owner, so a non-owner's tick sends nothing; content once per effect (`StaticSent.spatial_content`). Deleted: the per-member facts, the spatial filter and revision maps, `ProjectionState.remembered` (`commit_current` lives in the leaf `spatial_commits`; projection joins the publishers that never import the client fold). The client folds composed facts only (`fold_composed_sensory`); `PlayerState.perception` is gone; initiative reads the composed contacts.
  - **Deviation (coordinator: approved):** no `ObjectiveRow.settlement` and no `_walk_group` key collapse. Later member events of a settlement make fact-less nodes that are never admitted, so version rows, children lineages and occurrences list the settlement once. The lost check is a test instead (`test_composed_sensory_wire`): each settlement marker lies in one walk group; one fact per settlement; no later member's version or lineage reaches the seat.
  - **Oracle (§5.3):** member cells dropped; contacts and effects name their members (bitsets); lights name none (D2) and drop the native revision; a `seen` category; O4 counts remembered effect cells; base views mapped to this shape.
  - **Also fixed:** `export_world_authoring.py` (stale since the sense-modes key and S-2), movement_scaling's seat metrics, the delivery and transport review tests (S-2 envelope).
  - **Done:** S-1, S-2, S-3 committed (98ec72336), merged with a4eb223b1 (NPC authoring) at 5a1fb9140, SDK regenerated.
  - **Left:** merge the digest-stamps head and regenerate sdk/; antislop small fixes (a stale `_sensory_fact` error string at projection.py:510, a stale oracle comment, effect bitsets compared by value in test_composed_sensory_wire); optional: `paths_dirty`-only settlements send nothing (as in schema 15).
  - **Gates at 5a1fb9140** (fireball, sleet_storm, spirit_guardians_walk, room_reentry × G1/G2 against a9d10bebd): O1 0, O3 equal, logs identical; O4: the only leaves not in the base are 132 public catalog content ids at setup (op 0), added by the NPC merge, not sensory; tests/player + tests/architecture = the base's 29 failures. Worst non-log KB G1/G2: fireball 89.4/83.4, sleet 44.9/100.8, SG walk 18.1/17.9, room_reentry 31.4/93.4 (base 123.2/99.8, 75.2/101.9, 52.8/20.0, 42.8/94.7).
- 2026-10-19: **E3-sensory, final state (96244ddab + this log).** Merged 0cb0a5571 (stamps, bodies follow-ups, build-once log); sdk/ regenerated, unchanged; the antislop must-fixes applied (2be7ff07b).
  - **Gates** (fireball, sleet_storm, spirit_guardians_walk, room_reentry × G1/G2 against a9d10bebd): O1 0, O3 equal, logs identical; O4: only the NPC merge's 132 public catalog content ids at setup. Sweep: the base's 29 failures plus test_the_session_actor_fold_has_one_writer, inherited from 0cb0a5571 (capture.reduce_lineage calls fold_birth; the lane does not touch capture.py).
  - **G2 time** (sequential, interleaved, 3 runs, min total ms base -> head): fireball 477 -> 396 (-17 %), spirit_guardians_walk 1431 -> 1412 (-1 %), sleet_storm 439 -> 424 (-3 %). One op is slower: the sleet cast, 175 -> 186 (pub 110 -> 118, native +3), while the sleet drop is faster, 260 -> 238.
- 2026-10-19: **Pre-production cleanup and a green gate (4ad5948be … 12ca35e6b).** Dead code and alternative paths cut before the branch goes to the production folder; the 64 known failures fixed, adapted or removed.
  - **Removed:** `game_obsolete/`, `server_obsolete/`, `devtools/animation_review/`, every devtools module importing the retired `game` package or pygame, `player_server_acceptance/corpus.py`; the pygame-ce dependency. `/game_obsolete/assets` stays git-ignored: that art was never committed and still sits in checkouts (backed up to `Dev/dnd_engine_game_obsolete_assets_backup_2026-10-19`, checksums equal).
  - **Fold cut (78ab2e928):** capture keeps what publication reads (seat admission, world interval, logs, actor change records, lineage graph). Gone: `PresentationTarget` and its reducers, admissions, the envelope's dispositions/door/torch ids/per-seat actor changes, the checkpoint's own actor/contact/position fold, `dnd/player/actor_facts.py`, `ActorState.last_visual_position`, `copy_world_facts`, `capture_history`/`encode_sequence`/`decode_sequence`. RecordedSequence 7.
  - **Bugs fixed:** a body the seat's view takes before its birth completes enters at the birth (Summon Dragon: the caster's seat perceived its summon with no body, O1; 328d563a8); a device's AoE row with a free-aim region is offered when nothing is listed; a free aim for an area that requires a creature is refused at admission when the area holds none (12ca35e6b).
  - **Tests adapted to the current design:** free-aim rows list no cells (D13), so tests aim with `free_aim_target` and check `selection_admission_error`/preview; tile conditions commit as one keyed batch; a gas turn start is its own trigger (human Q2); a hidden target cancels as "not visible"; summon forms are facets; a cast that ends the encounter resets turn costs (Freezing Sphere launch). Architecture tests retargeted: `dnd.types.cells` and `dnd.types.spatial_effects` declared safe leaves; tagged-union `kind` tags of the published log models exempt from the field-description rule (the client schema digest is unchanged); encounter comments moved into docstrings; checks of deleted files and of commits absent from this repository removed; CRLF checkouts normalized.
  - **Known gaps (strict xfail, product decisions):** a device's Wall of Fire row names no form (item-use rows skip facet domains); Conjure Elemental's slot-six Myrmidon forms are not offered (D17 lists facets at the base level; the human: leave it for now).
  - **Gates:** r36 over ai/architecture/engine/player/progression (r32's folders): 5619 passed, 0 failed, 27 xfailed (r32: 64 failed). Seat oracle O1 0 on summon_retirement and fireball × G1/G2. `tests/manual` (outside the gate) still has ~298 failures from older APIs (`_entity_by_position`, `bind_runtime_behavior`'s signature, log data subscripting), none from this cleanup.
- 2026-10-19: **The audits' MUST-CUT items (980a6a90a).** Cut: `Entity.action_scan`'s `with_navigation` and the five never-read `ActorScan` fields (reach cells, threat domains, slot capacity, free-cast grants, item charges); six unread `CreatureFacts` fields; `BaseAction.target_dependent_costs` (always False) and its four discovery branches; `StructuredAction` with `BaseAction._validate` (a second pipeline); `BaseObject.set_context`, `BaseCondition.clear_context`; `emit_sensory_update_delta`'s `contact_changes` and `layer_positions`' `mask`; gridmap's `BOUNDARY_FACING`/`contact_surface` (the one rule is `placement_support_cells`; the incident-cell check covers gridmap); the summons' `setattr`. `movement_profile_worker` no longer names deleted functions; the sdk/protocol and server READMEs state schema 16. test_126 action overrides pass. Gate r37: 5619 passed, 0 failed, 27 xfailed; no new pyright errors in the touched files (16 vs 25).
  - **Left as SHOULD (not done):** `configured_action_ref` (always None, still on the published schema: cutting it changes the digest); the TypeScript SDK and `generate_typescript_sdk.py` describe the old server's replication routes; `tests/manual` legacy contracts (~298 failures, old APIs); the other SHOULD-CUT items in the audit reports.
- 2026-10-19: **Item-use rows per facet; `configured_action_ref` gone (3ccb37dae).** A use action's authored choices each make a row (`BaseAction.facet_forms`), so a device's Wall of Fire offers and casts its forms. `configured_action_ref` (always None) left the contract; sdk/protocol, sdk/python and sdk/player-typescript regenerated; schema digest `49d14bc20920…` (player schema 16; the Godot handout updated). Gate r38: 5620 passed, 0 failed, 26 xfailed.
  - **Waiting on the human:** the fast-forward of the production folder; whether to delete the stale TypeScript SDK (`sdk/typescript`, old replication routes, its generator no longer runs); what to do with `tests/manual`'s legacy contracts (~298 failures); Conjure Elemental's slot-six forms (deferred by the human).

- 2026-10-19: **Restore specialized authored characters after the generic-premade substitution.** The human explicitly requested the original specialized builds. `8ae300a54` made retired class recipes constructible by mapping them to three generic level-5 premades, but lost equipment presets, fighting styles, ASIs, caster levels and spell choices.
  - Restored the 14 distinct original configurations as ordinary frozen `CharacterBuild` entries in `premades.py`: five Fighter, three Barbarian and six Sorcerer variants. They use the existing `prepare_character` path; no retired factory or new materializer was introduced. The seven existing general premades are unchanged.
  - The original spell-learning choices were recovered from the retired factory's source, including its legal fallback choices. The projectile scenario therefore still has its historical Burning Hands/Acid Splash fallback; its old “no AoE” title overstates the original behavior. This repair does not invent a different spell selection.
  - Updated 62 source references across reusable and embedded rosters. The build-restoration comparison confirmed only those IDs and dependent recipe digests changed; names, roles and formations remain intact. A separate final repair corrects two Goblin starting-damage values, described below. Scenario setup owns torches, avoiding the duplicate torch introduced by the generic premade substitution.
  - Boundary: prepare the real encounter, then inspect the committed character's equipment, fighting-style effects, ability scores, class levels, slot capacity, spells and single birth event. `tests/engine/test_authored_character_builds.py` covers all 14 configurations. The migrated `test_every_authored_spell_matrix_preserves_requested_runtime_spells` covers the original 25 reusable/embedded spell cases and checks actual installed spells after setup.
  - Validation: those 15 tests pass; `pyright dnd/content/characters/premades.py` reports zero errors. The broader character/encounter batch had 127 passes and 10 remaining older manual failures. Independent antislop, antiOOP and plan-adherence reviews found no blocking issues.
  - **Full-suite baseline at `211b71134`, requested separately by the human:** 7,172 collected; 6,942 passed, 204 failed, 26 xfailed in 520.174 seconds. Run from the Linux worktree with Python 3.13 and the locked uv environment. Engine (4,801 passed, 22 xfailed), player (368 passed, 1 xfailed), AI (36 passed), progression (296 passed, 3 xfailed), performance (3 passed) and root tests (39 passed) had no failures. Failures: manual 202; architecture 1 from a tutorial test fixture lacking `value_fields`; paused-server 1 importing the removed `server.spell_catalog`. SDK baselines: Python 91/91 and TypeScript 64/64. This is not a green full-suite claim.
  - **Full rerun after build restoration:** 7,200 collected; 6,976 passed, 198 failed, 26 xfailed in 745.326 seconds. No new failing nodes; six old failures now pass (25-member spell matrix, high-level duel, class-party equipment, ranged equipment, condition-lock spells and torch count). All 28 added cases pass: 14 new engine cases plus 14 existing progression cases parameterized over the restored builds. Remaining failures in this run: 196 manual, one tutorial-fixture architecture failure, one retired server-catalog test. This run used the primary `/mnt/c` checkout; baseline used Linux storage, so elapsed times are not a performance comparison.
  - **Final authored-scenario repair, after the full run:** the projectile Goblin has native maximum HP 7 but inherited starting damage 7, so it spawned dead and disappeared from valid targets. The existing test requires 3 HP and three live missile targets. Changed damage to 4 in the reusable and embedded roster, retaining the original assertions. Final focused batch: **17 passed in 7.99 seconds**, covering the 14 builds, original 25-member spell matrix, every canonical encounter assembly and the projectile scenario. The full-run failure count above intentionally remains the measured pre-repair count.
  - **Audit and worklist:** [EVENT_NATIVE_TEST_AUDIT_2026-10-19.json](audits/EVENT_NATIVE_TEST_AUDIT_2026-10-19.json) records every baseline failing node, its after-run status, evidence, confidence and next step; it includes reproducible production cases and all 26 existing xfails. For the 198 failures in the full rerun: 19 have behavior verified by corrected probes; 98 are blocked by removed APIs or invalid fixtures with later behavior unverified; 69 need contract/gameplay review; five leads expose three production defects; seven are verified retirement/redundancy candidates. The Goblin defect was subsequently repaired as above.
  - **Sensory evidence:** all six sense-buff cases pass when reading effective senses; both spike-zone cases pass after explicit composition/deployment. Reactive light reveal/extinction, carried-light movement, invisible collision, subjective-path privacy and independent Hidden/Invisible stacking pass corrected boundary probes. These results do not clear known xfails: refused torch use changes light state, transferring a torch retains light at the old carrier, and rejected wall-torch authoring leaves a registered object.
  - **Unfixed production findings:** forced movement can finish on an allied creature (Thunderwave puts two creatures at `(9, 4)`, although the endpoint is illegal). Separately, AI `AffordanceSet` serialization removes the default `position_selection.kind` discriminator, so a real Dimension Door decision epoch fails its own JSON decoder. The audit preserves exact reproduction steps. These were not folded into the character restoration.
  - **Removal candidates:** six source-token tests of the retired AI observer HTML/README, and the paused old-server catalog wrapper test whose current bootstrap equivalent already passes in architecture. Nothing was deleted or hidden to make the suite green. The lane remains open pending the recorded fixes and test migrations.

- 2026-10-19: **Post-audit repair work order (human requested).** Sol migrates obsolete APIs and invalid test fixtures while the parent investigates and repairs actual bugs. The original specialized builds and behavioral/privacy coverage remain the contract.
  - **Test migration boundary:** current native setup, commands and typed events, preserving observable assertions. Start with the audit's 98 API/fixture blockers and 19 verified corrections; review the remaining assertions against established behavior. Remove retired or implementation-only checks only with recorded retirement/replacement evidence. Sol owns manual tests and their tutorial fixtures; newly exposed production defects are reported to the parent.
  - **Forced movement boundary:** issue a real push with occupied support cells; the final committed position must be a legal stopping cell, and emitted displacement must describe actual movement. Whether forced movement may traverse allies is pending the human's answer: current execution and the Shove docstring disagree. Reproduce first; no movement architecture redesign.
  - **AI transport boundary:** build a real decision epoch, serialize its affordances and decode them; required tagged selections and action meaning must survive. Preserve the current wire shape and source factoring.
  - **Torch boundaries:** refused ignition/extinction must leave light state unchanged; moving a lit torch between owners must release the old carrier's light; rejected character creation must leave no created world object. Use existing failing audit cases and observable light/object state, with scoped additional cases where necessary.
  - **Review and validation:** `plan_adherence` tracks scope; `build_review` performs antislop and antiOOP review. Reproduce each actual defect before fixing it, run focused checks per boundary, then one combined suite after the coordinated changes settle. No new product rule, compatibility layer or weakened assertion is authorized by this work order.

  - **First repair batch:** required AI union tags restored; portable and fixed torch uses now admit their own effect before changing light; accepted torch transfers use the existing loot hook to reanchor to the new carrier or extinguish in storage, with refusal preserving the old light. Character validation rejects the seven existing independently-owned world builders before allocation. Focused batch: 128 passed, 20 existing xfailed. Five former expected failures are now ordinary passing cases. Typecheck: zero new diagnostics; the existing builds.py:185 AbilityName diagnostic is identical on baseline 211b71134.
  - **Further real bugs exposed by migrated tests:** current direct Sorcerer actions supplied four semantic keys that the AI lookup did not recognize (Quickened, Twinned, both Font of Magic conversions). Added those exact keys to their existing semantic builders; retained class keys because direct SorceryPointsFeature grants still use them. Trap-lever semantics now derive from the selected desired state independently of catalog identity; only deactivation promises hazard deactivation. WetSurface, IceSurface, ElectrifiedWater and SteamCloud were visible with empty descriptions; added their concrete public summaries. Four semantic cases and four actual sensory observations failed before repair; the repaired batch and related native environment/control tests passed 48/48. No generic class-default descriptions or new semantic framework.
  - **Authored catalog migration:** current explicit inventories contain 20 battlefields, 42 encounters, 60 reusable rosters and 146 reusable members; the nine original reusable deployments remain exact. General lifecycle checks now use each recipe's declared roster slots/factions, preserving the original 38 encounter tags and the four newer scenario IDs. Cold battlefield tests start empty; current movement costs replace removed tile.walkable. Closed chests are opened through the native command before asserting loot availability; disabled spikes remain installed but nonhazardous, as required by existing environment_controls tests. Extra Attack permission is evaluated at target admission and reports NO_VALID_TARGETS when no grant exists. Authored batch plus AI transport: 107 passed, one unresolved catalog coverage assertion (Dretch is absent from reusable and embedded rosters). Do not invent a new roster merely to satisfy this census.
  - **Historical icon tests:** retained live rows still authenticate assets; the current expanded catalog is not the frozen icon ledger. Malformed-ledger tests now validate a closed, known-good Move binding before tampering. Nine focused tests pass. No artwork, ledger, runtime validator or generated icon bindings changed.
  - **Migration accountability before the full rerun:** 45 previous test names have exact dispositions in the audit: 15 renamed/migrated and 30 retired. Every listed successor exists; the frozen icon ledger remains independently guarded. The 77-case privacy accountability ledger retains every historical case while identifying truly retired HTTP/CLI consumers explicitly. No new skips or xfails. Code was frozen before the combined run; Sol owns and monitors `/tmp/dnd-full-suite-repair.{log,xml}`.

  - **Combined full-suite result:** 7,195 collected; **7,157 passed, 17 failed, 21 xfailed**, one warning in 627.23 seconds, primary `/mnt/c` checkout. Every ordinary failure is in manual tests; AI, architecture, engine, player, progression, performance and root lanes passed. Five known xfails were repaired; no skips or xfails were added. Relative to the 204 initial failures, 143 pass under their original names, 15 renamed successors pass, 30 have explicit retirement evidence, and 16 still fail. The seventeenth failure is the synthetic lever test's obsolete semantic key. Full artifacts: `/tmp/dnd-full-suite-repair.{log,xml}`.
  - **Post-full fixture isolation and repair:** thirteen cold-loader failures were reproduced by manual152's deferred-controller fence test followed by manual160's cold discovery test. The shared controller helper used raw native factory results without composition/deployment, then wrote navigation outside the registered sensory lifecycle. Migrated that helper through ordinary composition/deployment; no production reset edit or private-state clear. Corrected manual42's synthetic lever fixture to the explicit deactivation key while retaining all typed assertions. **133 passed in 27.24 seconds**, covering all controller-helper consumers (24/152/184), chronological 150/151/152/154/155/159 followed by 160/164, and semantic module42. Artifacts: `/tmp/dnd-controller-cold-repair.{log,xml}`. The earlier full-run result stays 17 failures; this focused result repairs fourteen of them and is not a second full-run claim.
  - **Lane remains open:** forced movement can share an occupied final cell, with allied traversal awaiting the human's rule; four current actions remain unmodeled by AI semantics (Drop, AllyHelp, HelpAttack, DismissSummon); Dretch has no reusable or embedded roster member. Twenty-one pre-existing xfails remain: fifteen refused class/monster/item benefits, four refused feature grants, slot-six Myrmidon discovery, and the strength-only armor requirement. Sense-affecting potion refusal defects remain among those cases. Corrected visibility/privacy probes and the complete native lanes pass, but this does not clear those cancellation defects. Specialized builds and the original spell matrix remain intact. Independent reviews found no blocking issue; final diff check passes.

- 2026-10-19: **Rules-checking follow-up in the human-requested isolated worktree.** Branch `feature/rules-checking` starts at `cdfafea0c`; the primary client checkout is untouched. The human clarified that a blocking ally or other creature stops a shove on the preceding free tile, and requested detailed review of boundary walls and cliff falls.
  - **Authorized correction:** use existing physical endpoint occupancy at every attempted ground forced step, in both prediction and authoritative commit. Inputs are real Shove commands and direct forced-movement events; outputs are final position, actual distance and retained blocker position. Preserve voluntary ally traversal, dead/nonblocking exceptions and current wall/fall behavior. `plan_adherence` tracks scope; `build_review` performs antislop and antiOOP review.
  - **Review evidence before edits:** 66 existing tests passed, one known Thunderwave occupancy test failed. Twelve actual Shove probes confirmed tile-edge walls, allied pass-through/overlap, blocked enemy cells, a 20-foot supported fall, and blocked explicit cliff-face/occupied/missing/water landings. No new cliff geometry or void behavior is authorized by this correction. A separate effect-veto probe confirmed Shove can report 10 feet despite no displacement; record for follow-up.
  - **Correction validated:** four allied-occupancy regressions failed before repair (eight control cases passed). The existing physical endpoint guard now runs for each predicted and committed ground push cell. All **214 focused cases passed in 11.60 seconds**, including the original Thunderwave failure, 12 new occupancy/boundary cases, supported falls, combat actions, portals, residue reactions and high-level movement controls. Plan-adherence, antislop and antiOOP reviews pass; no new full-suite claim. Detailed geometry findings and the separate canceled-push reporting defect are recorded in the audit’s `rules_checking_followup`.

- 2026-10-20: **Production backend handoff repairs, isolated on `feature/rules-checking`.** Fetched `origin/event-native-deltas`: it, the local integration branch and this worktree base all remain `cdfafea0c9645819470dc8f5337a3de2abd401e0` (0 ahead/0 behind). The client evidence targets the older frozen `211b71134` export. No merge, rebase, stash, primary-checkout edit or client edit was needed. These repairs remain uncommitted and unpromoted.
  - **Authorized boundary:** investigate the exact backend review and why tests missed it; repair existing discovery, native event completion and typed publication. Preserve specialized builds, gameplay policy, disclosure and the optimized capture/fold architecture. The [handoff audit](audits/BACKEND_HANDOFF_TEST_GAPS_2026-10-20.json) maps 20 issue groups, original evidence, existing tests, each blind spot and current disposition. Plan-adherence, antislop and antiOOP review accompanied implementation.
  - **Sixteen repaired groups:** Dragon's Breath grant lifecycle; Vitriolic residue identity and initial footprint; selected Burst/Orb elements on misses; portable sphere throw destination/area; terminal capture for three attack-backed smites; Magic/Sacred Weapon membership; emitted-only Blessed Healer/Destroy Undead attribution; attributed native rider components; concrete condition selectors and dragon readiness; Frenzied parent and quarry sustain owners; actual Prismatic colours and result ancestry; existing spell-form facets; DYING patient discovery; Help's returned secondary selection; equipped Devotee's Mace use discovery. Damage component amounts are before packet-wide reductions/HP allocation, not separate final HP losses.
  - **Capture correction and review:** Prismatic outcomes use each actual saving throw as their cause, without extra ray spell events. Capture follows legitimate children emitted after a parent completes, bounds graph and raw links to the same exclusive operation cursor, and leaves native evidence unchanged. Reviewer found loss of spell provenance when changing that parent: passing the original spell origin explicitly to damage rolls and conditions repaired it. Nine new native provenance assertions failed before that correction; the final affected batch passed **276 cases in 21.44 seconds**. Cutoff/cold-load checks include refusing an unfinished child whose completion is outside the captured interval.
  - **Why green tests missed it:** native `.apply`/HP/condition tests bypassed offered choices and worker capture; the generic spell transport check required records and a noncanceled spell, not exact consumer fields; some attribution tests injected prefilled evidence. Added **100 handoff regressions** covering real choices/commands, JSON-serialized independent seats, exact owners, misses, hidden-source filtering, lifecycle retirement and cold replay. The separate allied caster/recipient Dragon's Breath test passed in 1.26 seconds and verifies the ally's Exhale with original-caster damage attribution and caster-driven removal.
  - **Full sweep:** **7,283 passed, 2 failed, 21 xfailed**, one warning, 7,306 collected in 595.29 seconds. The two failures are unchanged: manual31's four unmodeled AI actions (Drop, AllyHelp, HelpAttack, DismissSummon), and manual71's missing Dretch roster member. No new skips/xfails or weakened assertions. This run collected 99 handoff cases and began before the final Prismatic origin refinement; the 276-case final supplement and one later ally case qualify those subsequent changes separately. Artifacts: `/tmp/dnd-handoff-full-suite.{log,xml}` and `/tmp/rules-checking-prismatic-final.log`.
  - **Protocol and sensory verification:** regenerated schema/OpenAPI/ledger and both SDKs (protocol 1, schema 16, digest `2c11d7a9919c8aa9b1490628fff224627f19d6388c3884171d14a4a5cbecea22`; 379 definitions, 1,925 fields). Python SDK 91 passed, Monty 9 passed, TypeScript build/tests 64 passed. Scoped typecheck has the same 188 existing diagnostics as baseline and no additions; capture has zero. Fireball G1 and room re-entry G2 (31 independent seats) have zero O1 differences. Fresh-process SDK replay, connection interruption/resume and per-record state/stamps match on both runs. See `/tmp/rules-checking-handoff-{fireball,room}-oracle` and corresponding replay logs.
  - **Final ordinary Fireball sample:** three baseline and three final runs, same cached Python 3.13 environment and Linux source, final timing after test processes stopped. Median command 120.078 → 120.738 ms; publication 47.900 → 47.150 ms. Largest packet 130,728 → 133,102 bytes (+2,374); log bytes unchanged at 41,332, with the same 571 native versions and six deaths. No material slowdown in this small sample; it is not a latency distribution.
  - **Remaining boundaries:** retained bead dice/DC presentation needs a contract decision; developer Test Bless remains a named ordinary-roster setup failure; voluntary Drop Prone remains excluded by explicit current policy; the older Hellish Rebuke area/group case remains unisolated. Slot-six Myrmidon discovery remains its existing strict xfail. Frozen client originals have not been re-recorded and Play/Studio visuals have not been qualified. The work lane remains open for these boundaries, the two ordinary test failures and the recorded existing expected failures.

- 2026-10-20: **Human-requested main checkout and production handoff.** Saved the complete rules-checking work in local commit `a97bb55b0a5138d9b26289c7d58aeb8ee25678dc`, detached the earlier worktree at that commit, and checked out `feature/rules-checking` in `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine`. The main checkout was clean before the switch; earlier runtime evidence remains in the detached worktree. No source changes followed the recorded validation. The [client production handoff](BACKEND_CLIENT_PRODUCTION_HANDOFF_2026-10-20.md) identifies the fixes revision, exact schema digest, public fields, original client cases to re-record and remaining gaps. No remote push, client frozen-export replacement or client production qualification is claimed by this checkout change.

- 2026-10-20: **Lazy position-region SDK admission followup (`09e93c439`).** The client supplied an unchanged Choices response whose available Drop rows 15/16 have empty target sets and nonnull regions. Python refused it before Preview; TypeScript had the same obsolete relation. Both validators now follow the existing native availability contract, including sparse-default `{}` regions and unavailable rows retaining region metadata. Schema, affordability, references, ordinals and generations remain checked; no cells are manufactured and no gameplay code changed.
  - **Why tests missed it:** SDK fixtures lacked available lazy regions; native region/compound tests never crossed SDK admission. Added 15 public ChoicesResponse regression cases per SDK; the two available-region cases failed in each SDK before the fix. The unchanged original response now passes validate/decode in both SDKs without normalization.
  - **Validation:** Python SDK 106 passed (4.24 seconds); TypeScript build and 79 tests passed; existing native compound/Preview cases 4 passed (3.00 seconds). Plan-adherence, antislop and antiOOP review passed. Prior full engine and performance results remain historical; no full rerun for this SDK-only repair.
  - **Handoff:** the production handoff now pins the cumulative fixes commit. Reinstall/rebuild the recorder SDK from that revision even with a matching schema identity. Immutable export promotion and unchanged Fireball/Magic Missile targeting recordings remain on the client adoption path; the original zero-check failure is preserved as failed evidence.

- 2026-10-20: **Solid-wall worker cancellation and Holy Nimbus ownership (`59291eddead29e3002d8efae996dadb22aec3491`).** Reproduced the original Force configuration and all three Force/Ice/Stone worker failures: the chosen displacement side was occupied by the target's ally; correct forced-movement refusal left application/CREATED events unfinished. Planner now checks path occupancy/reservations with caster-relative subjective disclosure and objective ground transitions. Failed spatial activation cancels its two actual opened events; capture's terminal invariant is unchanged. The blocked original left side is unconfirmable without spending; a legal right side forms and retires normally. Real placement-veto tests prove complete cancellation and no partial wall.
  - **Nimbus:** the real burn now passes its exact condition UUID into existing damage attribution. Two real Paladin20 owners, actual turn starts, hidden-owner redaction, ordinary Radiant and removal are tested. No schema change or broader handler exposure.
  - **Evidence:** original wall batch 3 failed first; second-placement veto capture fails on all three baseline spells; Nimbus 2 failed first. Final affected batch **151 passed in 26.37 seconds**; crowded Stone O1 has **zero differences**. Independent plan/antislop/antiOOP review passed. No new full-suite run or client production qualification claimed.
  - **Human-requested timings:** same cached Python 3.13, Linux baseline/final sources, fixed inputs, our tests stopped, three sequential samples per case. Crowded Stone median total **107.533 -> 109.043 ms**, publication **26.244 -> 26.212 ms**; packet **39,128 bytes**, **192 event versions**, no deaths on both. Six four-actor Force/Ice/Stone cases retain bytes/events, with largest median increase **2.063 ms** (displaced Ice). Raw samples, including the Force baseline outlier, and limits are retained in [the content blocker audit](audits/BACKEND_CONTENT_BLOCKERS_2026-10-20.json). No zero-overhead or latency-distribution claim. The client production handoff pins the cumulative fixes revision.

- 2026-10-20: **Remaining client contact attribution (`0c2e5a0d74919402c6e528f40c580b7ca3c22e93`).** Flaming Sphere END damage now passes its exact zone UUID; Ram retains action attribution. Four Elemental Multiattack bonuses and three Myrmidon strikes attach their real condition semantic IDs and damage-roll lineage to the actual added Damage objects, with ACTION classification and magical attack flags preserved. Tenacity supplies its exact condition UUID on miss damage. No new schema or handler-publication system.
  - **Healing Incense:** native turn-start heals now carry the emitting zone UUID, admitted only through current observed-spatial membership or the prior recipient-condition rule. Reproduction found the zone was also invisible by inherited default, contrary to the report assumption. Its authored visible presence now publishes existing membership, observed footprint and normally disclosed caster anchor. No new item field or art changes.
  - **Evidence and old gap:** 20 new public cases failed before their respective fixes; prior tests checked HP/dice/riders, charge/activation or birth selectors but not the later exact owner join. New tests cover distinct owners, real source damage UUIDs, hidden-source redaction, ordinary-result negatives, native BODY/HELD distinction, Chilled vulnerability and spell resistance, Sphere retirement and Incense unequip cessation. Combined affected batch **250 passed in 54.17 seconds**. Independent plan/antislop/antiOOP review passed. Full-suite and client recording reruns are not claimed; known Myrmidon worker discovery omission is unchanged.
  - **Requested timings:** sequential Linux-source baseline/final, tests stopped, one excluded warmup plus five measured samples per row. Median total milliseconds: two Incense activations **30.996 -> 33.436**, two Incense heals **7.012 -> 7.417**, two Sphere END contacts **13.026 -> 12.319**, Fire Elemental bonus Multiattack **17.001 -> 15.424**, Fire Myrmidon strike **12.505 -> 12.391**, Tenacity miss **8.731 -> 8.759**. Incense activation's newly visible zones add **4 native versions** and **2,748 bytes** to the largest update; other rows retain event counts and add only attribution bytes. Native/publication/encoding splits, every raw sample and exact runner are retained in [the content blocker audit](audits/BACKEND_CONTENT_BLOCKERS_2026-10-20.json). This is not a zero-overhead, speedup or latency-distribution claim.
  - **Handoff:** production document pins this cumulative fixes revision. The client's report says its frozen engine/SDK selected the earlier `59291edde`; new engine promotion and fresh client recordings remain client work. Existing reusable Incense art needs no backend art change. No push or client-file changes made.
