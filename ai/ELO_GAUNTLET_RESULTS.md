# Atomic Arena Baseline Results

## Retained Atomic Baseline

This run is a complete regression, subjectivity, arena-balance, and performance
baseline. It is not a global configuration rating experiment. Each hero roster
was paired with only the monster roster from its fixed arena, producing 38
disconnected two-participant comparison components. Ratings from those pairs
cannot be compared across arenas or interpreted as hero or monster
configuration Elo.

The retained complete atomic evaluator baseline is:

```text
matrix_id: 20260717T170610Z-ai-elo_matrix-4fda7cba
schedule_hash: f9d5db78227de43a
controller_profile: unified_ai_current
policy_version: 2026-07-17.shared-policy-v31-result-feedback-search
subjectivity_validator: external_selfplay_event_history_perception_witness_v3
```

The matrix covered all 38 constructible AI validation arenas, seeds 1 through
10, and both opening-side treatments. All 760 matches ended normally and all
760 entered the rating ledgers. There were no command caps, timeouts, crashes,
unknown outcomes, missing artifacts, rating exclusions, or subjectivity
violations.

| Gate | Result |
| --- | ---: |
| Scheduled | 760 |
| Completed | 760 |
| Rating eligible | 760 |
| Failed | 0 |
| Skipped | 0 |
| Pending | 0 |
| Subjectivity passes | 760 |
| Subjectivity violations | 0 |

The outcome total was 304 hero wins and 456 monster wins. This is an arena
balance result, not a comparison between two AI implementations: both factions
used the same policy. Hero-first treatments produced 164 hero wins from 380
matches; monster-first treatments produced 140. The observed opening treatment
therefore shifted the hero win rate from 36.84% to 43.16% in this catalog.

## Runtime Accounting

The retained evidence now separates complete evaluator wall time from self-play
time and from command-loop stages.

| Measurement | Result |
| --- | ---: |
| Evaluator wall time | 35m 43.0s |
| Summed self-play time | 15m 12.5s |
| Evaluator/evidence overhead | 20m 30.5s |
| Self-play share of wall time | 42.58% |
| Wall throughput | 21.28 matches/min |
| Matches | 760 |
| Commands | 25,341 |
| Distinct actor-turns | 7,469 |
| Mean commands/match | 33.34 |
| Mean actor-turns/match | 9.83 |
| Mean final round | 3.38 |
| Self-play commands/s | 27.77 |
| Self-play actor-turns/s | 8.19 |
| Wall commands/s | 11.83 |
| Wall actor-turns/s | 3.49 |
| Mean match | 1,200.6 ms |
| p95 match | 3,066.4 ms |
| Slowest match | 7,453.6 ms |

Evaluator overhead includes work outside each retained self-play timer: exact
arena setup and manifest work, independent evidence audits, checkpointing,
serialization and writing of 2.1 GB of forensic JSON on the mounted filesystem,
and final aggregation. It is deliberately reported separately from gameplay
latency.

### Command Loop

The full client loop was measured on all 25,341 commands: mean 27.71 ms, p95
50.67 ms, p99 78.79 ms, maximum 212.53 ms.

| Stage | Mean | p95 | Share |
| --- | ---: | ---: | ---: |
| Pre-command stream sync | 1.56 ms | 13.73 ms | 5.64% |
| Typed fact reduction | 0.95 ms | 2.35 ms | 3.42% |
| Shared policy | 1.45 ms | 3.63 ms | 5.22% |
| Command/server round trip | 22.07 ms | 40.99 ms | 79.64% |
| Follow-up stream sync | 0.51 ms | 1.34 ms | 1.84% |
| Other client overhead | 1.18 ms | 2.37 ms | 4.24% |

Selected deep diagnostics were sampled independently of the complete top-level
loop:

| Component | Samples | Mean | p95 |
| --- | ---: | ---: | ---: |
| Server command total | 25,341 | 20.69 ms | 39.43 ms |
| Decision epoch build | 25,341 | 6.70 ms | 17.03 ms |
| Engine action total | 2,262 | 11.10 ms | 28.28 ms |
| Engine execute-by-index | 2,262 | 10.13 ms | 27.07 ms |
| Available-action construction | 2,408 | 4.62 ms | 11.44 ms |
| Affordance serialization | 2,408 | 3.35 ms | 6.94 ms |
| Observation projection | 2,262 | 1.97 ms | 5.89 ms |
| Senses updates | 2,021 | 3.26 ms | 12.91 ms |

## Arena Results

`H-M` is the hero/monster win count. Hero Elo is the final hero-side rating in
the independent `arena_balance` ledger. Elo is chronological and therefore
slightly path dependent; the win count should always be read beside it.

| Arena | H-M | Hero Elo | Mean | p95 | Cmd/m | Turns/m | Round |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `arcane_device_control` | 16-4 | 1085.6 | 533 ms | 781 ms | 9.8 | 3.0 | 1.60 |
| `buff_consumable_ambush` | 0-20 | 834.6 | 1003 ms | 1167 ms | 29.5 | 6.7 | 2.00 |
| `caster_crossfire` | 0-20 | 834.6 | 864 ms | 1021 ms | 25.1 | 7.0 | 2.05 |
| `class_party_mirror_scramble` | 0-20 | 834.6 | 742 ms | 969 ms | 18.6 | 4.2 | 1.35 |
| `cleanse_support_triage` | 0-20 | 834.6 | 897 ms | 973 ms | 21.6 | 6.8 | 2.00 |
| `concentration_control_crossroads` | 15-5 | 1075.1 | 888 ms | 1371 ms | 16.5 | 4.4 | 2.15 |
| `condition_lock_sanctum` | 0-20 | 834.6 | 973 ms | 1185 ms | 21.5 | 5.8 | 1.95 |
| `damage_affinity_weapon_lab` | 0-20 | 834.6 | 443 ms | 587 ms | 7.1 | 2.5 | 1.00 |
| `darkness_reveal_labyrinth` | 0-20 | 834.6 | 1633 ms | 2089 ms | 43.3 | 9.4 | 2.85 |
| `double_door_dark_hunt` | 20-0 | 1165.4 | 1318 ms | 1809 ms | 51.6 | 13.4 | 4.75 |
| `field_cache_loot_race` | 0-20 | 834.6 | 807 ms | 990 ms | 18.2 | 5.5 | 1.85 |
| `forced_movement_hazard_bridge` | 0-20 | 834.6 | 1133 ms | 1735 ms | 34.5 | 8.7 | 2.75 |
| `goblin_water_skirmish` | 0-20 | 834.6 | 651 ms | 734 ms | 20.0 | 5.1 | 1.85 |
| `guardian_choke_body_block` | 0-20 | 834.6 | 1108 ms | 1455 ms | 25.6 | 6.7 | 2.05 |
| `guardian_zone_shrine` | 0-20 | 834.6 | 776 ms | 1178 ms | 12.2 | 3.8 | 1.35 |
| `high_level_spell_resource_duel` | 18-2 | 1141.8 | 1144 ms | 2079 ms | 18.8 | 4.8 | 2.45 |
| `item_resource_gauntlet` | 5-15 | 928.1 | 1104 ms | 1232 ms | 25.6 | 8.2 | 3.85 |
| `line_aoe_corridor` | 15-5 | 1087.1 | 696 ms | 1458 ms | 12.8 | 4.0 | 1.80 |
| `multi_object_control_room` | 0-20 | 834.6 | 1209 ms | 1565 ms | 32.5 | 8.2 | 2.60 |
| `multi_projectile_no_aoe_lab` | 20-0 | 1165.4 | 338 ms | 450 ms | 3.4 | 1.8 | 1.00 |
| `multi_target_missile_allocation` | 20-0 | 1165.4 | 403 ms | 546 ms | 4.2 | 1.8 | 1.00 |
| `necrotic_anti_healing_duel` | 0-20 | 834.6 | 552 ms | 670 ms | 8.8 | 2.8 | 1.00 |
| `ranged_loadout_kiting_ring` | 11-9 | 1008.5 | 2073 ms | 2909 ms | 76.0 | 20.2 | 6.40 |
| `reaction_counterspell_lab` | 0-20 | 834.6 | 816 ms | 1152 ms | 16.4 | 4.5 | 1.45 |
| `resistance_weapon_counterplay` | 0-20 | 834.6 | 742 ms | 962 ms | 18.4 | 4.6 | 1.50 |
| `skeleton_anti_aoe_split` | 20-0 | 1165.4 | 903 ms | 1057 ms | 25.2 | 9.4 | 3.30 |
| `skeleton_mark_focus_fire` | 14-6 | 1037.2 | 2471 ms | 3066 ms | 105.3 | 38.9 | 13.55 |
| `sorcerer_barbarian_duel` | 17-3 | 1114.7 | 513 ms | 665 ms | 11.7 | 3.0 | 1.80 |
| `srd_divine_cult_cell` | 16-4 | 1100.7 | 972 ms | 1858 ms | 15.8 | 4.4 | 1.80 |
| `srd_elite_mercenary_contract` | 16-4 | 1102.8 | 3179 ms | 5205 ms | 77.9 | 27.0 | 8.05 |
| `srd_goblinoid_warband` | 20-0 | 1165.4 | 3080 ms | 4213 ms | 100.8 | 25.6 | 8.00 |
| `srd_low_cr_patrol` | 18-2 | 1135.8 | 2677 ms | 3733 ms | 83.5 | 25.6 | 7.40 |
| `srd_undead_crypt` | 11-9 | 1024.2 | 3247 ms | 4105 ms | 118.0 | 38.0 | 12.75 |
| `standard_skeleton_doors` | 20-0 | 1165.4 | 833 ms | 1199 ms | 21.5 | 5.6 | 2.45 |
| `support_attrition_cache` | 0-20 | 834.6 | 909 ms | 1217 ms | 24.6 | 7.5 | 2.20 |
| `teleport_escape_skirmish` | 0-20 | 834.6 | 1213 ms | 1863 ms | 27.8 | 7.4 | 2.20 |
| `trap_lever_killzone` | 12-8 | 1031.2 | 1711 ms | 2129 ms | 55.2 | 19.8 | 8.30 |
| `zone_control_web_gauntlet` | 0-20 | 834.6 | 1065 ms | 1339 ms | 27.7 | 7.5 | 2.20 |

The closest fixtures were `ranged_loadout_kiting_ring` and
`srd_undead_crypt`, both 11-9, followed by `trap_lever_killzone` at 12-8.
Several fixtures swept 20-0 in one direction. Those are useful balance and
policy-pressure signals, but they should not be mistaken for evaluator failure.

The slowest individual match was `item_resource_gauntlet`, seed 5,
hero-first. It ended normally after 39 rounds, 222 commands, and 7.45 seconds.
Its 92 movement commands and 33 Dodge actions identify a real long-horizon
policy behavior worth investigating; the evaluator retained it rather than
classifying a long valid fight as a failure.

## Rating Interpretation

The useful baseline ledgers in a one-policy self-play matrix are
`setup_side`, `arena_balance`, and `roster`. They compare the two constructed
sides inside each arena. `policy_global` is intentionally empty because the same
policy identity cannot receive an Elo update against itself.

`policy_side` records faction-role history, but this schedule groups arenas and
Elo is recency weighted. It must not be used as a global policy-quality score.
A real policy ladder requires at least two policy identities and a balanced,
deterministically interleaved cross-policy schedule. This matrix establishes the
current policy's reproducible baseline for that future comparison.

All 20-game arena standings retain the `unstable` warning because the evaluator's
confidence threshold is 30 games. Ratings are evidence, not certainty.

## Evidence And Dashboard

Canonical files:

- `ai/evidence/elo_gauntlets/20260717T170610Z-ai-elo_matrix-4fda7cba/summary.json`
- `ai/evidence/elo_gauntlets/20260717T170610Z-ai-elo_matrix-4fda7cba/dashboard.json`
- `ai/evidence/elo_gauntlets/20260717T170610Z-ai-elo_matrix-4fda7cba/schedule.json`
- `ai/evidence/elo_gauntlets/20260717T170610Z-ai-elo_matrix-4fda7cba/matches/`
- `ai/evidence/elo_gauntlets/20260717T170610Z-ai-elo_matrix-4fda7cba/runs/`
- `ai/evidence/elo_gauntlets/latest.json`
- `ai/evidence/elo_gauntlets/latest.dashboard.json`

The matrix retains 760 typed match records and 760 raw run artifacts. The
dashboard projection is 2.7 MB and contains no forensic command traces. Its Elo
series stores only participants whose ratings changed on each match, avoiding
the former quadratic repetition of unchanged standings.

Open `ai/ELO_GAUNTLET_DASHBOARD.html` and load the matrix-local `dashboard.json`
or `latest.dashboard.json`. Every displayed value comes from retained JSON.

## Diagnostic History

The completed baseline followed two useful non-canonical runs:

1. `20260717T145043Z-ai-elo_matrix-3a6e3e62` completed 754 eligible rows and
   retained six command caps under the earlier policy.
2. `20260717T165248Z-ai-elo_matrix-11a6d770` exposed eight false-positive
   subjectivity reports in forced-movement fixtures. Forced movement briefly
   revealed cells and objects inside one action, but the old independent witness
   sampled only command-boundary senses. The v3 witness now consumes completed
   `SensoryUpdateEvent` history for controlled observers and correctly retains
   transient perception.

That investigation also fixed two real data defects before the canonical run:

- inventory-owned items no longer inherit a fake `(0, 0)` floor location in
  subjective spatial projection;
- damage and healing patches now use event-time HP values, preserving chronology
  when multiple effects are projected in one batch.

The canonical matrix then passed all 20 forced-movement rows and the complete
760-match eligibility audit.
