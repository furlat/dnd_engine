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
| P0b | — | |
| P1 | ✅ done (commit 9944b4adb; gate below) |
| P2 | — | |
| PD1a | — | one footprint |
| P3 (+PB2) | — | |
| PB3 | — | |
| Re-measure | — | |
| PD1b | — | rows, legality, selection |
| PD1c | — | after D14 approval |
| P4a | — | |
| P5 | — | |
| PD2 | — | session cache conditional |
| P4b | — | conditional |
| P6 | — | |
| P7 | — | |
| P8 | — | |
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
