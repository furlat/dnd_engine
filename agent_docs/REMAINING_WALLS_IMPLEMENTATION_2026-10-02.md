# Remaining walls: backend checkpoint

The approved [plan](REMAINING_SRD_WALLS_PLAN_2026-10-01.md) is implemented for
Thorns, Wind, Ice, Stone and Force within its ground-level boundary. This is
backend acceptance, not production artwork or in-game visual acceptance.

## Native behavior

| Spell | Implemented |
| --- | --- |
| Thorns | Straight/ring formation saves, piercing formation damage, slashing entry/end-turn damage, opacity and independent movement expenditure. |
| Wind | Continuous ordered paths, formation-only damage, ordinary missile interception with exact contact facts, Small/Tiny flyer and gaseous crossing restrictions, typed gas interactions. |
| Ice | Transparent solid panels and hollow dome; flat panels have local destruction; dome has shared 120 HP, AC 12 and fire vulnerability. Destruction creates exact-shell frigid air with first-passage saves/upcasting. |
| Stone | Supported connected cardinal panels, both prescribed panel dimensions/HP, creature displacement, enclosure save/reaction escape and ordinary opportunity attacks, local destruction and full-duration permanence. |
| Force | Transparent invisible physical obstruction, flat panels/hollow dome, immunity to damage and whole-owner Disintegrate removal. Creator knowledge does not satisfy Disintegrate's visual requirement. |

Construction sections are ordinary world items owned by one spatial condition.
Native creation/removal preflight prevents partial placements or cancellation gaps.
Successful destruction cascades collision/observation changes; expiry creates no
frigid air, including after a vetoed break. Retained observations expose live
section geometry, not an inferred reconstruction from artwork.

Disintegrate uses the normal spell route for creatures and eligible placed objects.
It requires actual visual contact and respects explicit magical-item immunity.
Natural/equipped missiles share native Wind interception. Ground geometry and
missile contacts are passive data in player projection; no live-engine renderer
queries or new wall-specific attack executors were introduced.

## Validation

- Full engine suite: **1,897 passed**, 201.31 seconds.
- Focused walls, Fire and object/spell checks: **92 passed**, 20.93 seconds.
- Wall/area/attack replay and point-selection checks: **73 passed**, 40.49 seconds.
- Final wall suite: **33 passed**, 9.05 seconds, including the explicit magical
  True Seeing potion flag.
- Scoped native/presentation typing: **zero errors and warnings**.
- Independent anti-slop and ECS reviewers approved the bounded rules/ownership
  changes after cleanup-veto, actual sight, displaced enclosure and contact fixes.

The broader engine/architecture run reported **1,963 passed and five failed**:

1. `test_current_and_accepted_artifact_hashes_are_exact`: frozen content evidence.
2. `test_srd_source_inventory_and_proof_overlay_are_exact`: frozen inventory/status evidence.
3. `test_every_structural_definition_has_one_exact_authored_owner`: frozen structural count.
4. `test_cri_public_item_inventory_is_complete_and_direct`: old public-item inventory.
5. `test_content_bootstrap_and_composed_spell_catalog_cold_start`: paused server
   imports removed `dnd.core.senses` through `server/world_contracts.py`.

These failures remain documented for discussion. No frozen expectations were
weakened and no paused server repair was folded into this lane.

## Remaining boundaries

- New wall materials/media have not been imported or visually accepted. Existing
  Fire formation timing, cloud rendering and windows were not changed here.
- Stone and flat Ice placement admit only four native grid headings.
- Prismatic remains gated pending complete layer counters and planar disposition.
- Multi-Z, floating/full spheres, horizontal/stacked panels and true over-wall
  trajectories remain unsupported. Domes are hollow ground-anchored shells.
- Huge-object partial Disintegrate remains explicitly rejected; eligible ordinary
  objects and complete Force removal are supported.
- Wind uses existing per-cloud interaction policies; current local affected-cell
  removal is not claimed as complete SRD cloud dispersal. That policy needs its
  own agreed follow-up, rather than an incidental cloud rewrite.
- Thorns' artist handoff remains explicitly unsent, not installation authorization.
