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
