# Ordinary breakable walls: native and Pixi handoff

8 October 2026. Native mechanics and the authored media export are ready.
**Pygame is off. Pixi browser delivery is not certified.** The current
`/home/tommaso/Dev/NDClient` source/tools/public directories were externally
removed; this task does not recreate them. This document records the consumer
work that remains, without claiming that a retired renderer proves it.

## Coverage and existing owners

`DirectionalWall` composes existing Health and ItemDestructionProfile: wood
18 HP, stone 27 HP, existing material armor class. The same native attack path
discovers walls from either incident support, applies nonlethal damage, then
destroys once. Destruction clears the wall's boundary channels and occupied
bands while retaining UUID, owner cell, physical edge and committed base height.
Existing item destruction owns supported-item cascade and connector refresh.

Direct solid IDs: `environment.wall.fantasy_a1`, `fantasy_c1`, `fantasy_d1`,
`fantasy_d8`, `fantasy_f1`, `fantasy_f8`, `fantasy_g1` (each with the same
`environment.wall.` prefix). The generic `environment.directional_wall` keeps
its existing stone/wood straight and corner resources. A corner has two provider
UUIDs: destroying one changes only its edge; its intact peer uses the existing
straight selector. Do not combine a destroyed provider with an intact corner.

Existing fantasy window families A4/A5/C4/D16/D7/F16/F7/G7/G8/G9 remain on their
approved wall/insert banks, masks and mechanics. Window/bars are independent
targets; insert destruction preserves the wall. Wall destruction also destroys
its supported insert. Existing native movement, crawl/climb/attack actions and
parent/insert health remain authoritative. No window opening work was resumed.
`environment.cliff_face` remains nonbreakable terrain.

## Data the consumer must use

The canonical `PresentationCatalogExport.environment` carries
`game/data/environment_art.json`. `EnvironmentBankSource.clear_at_end` is a
boolean, default false. `EnvironmentDocument.wall_destructions` maps native
material strings to generic wall bank IDs. Solid sibling `props` have their
own explicit `destructions.default` IDs. Use the existing canonical schema to
generate consumer types; do not maintain handwritten substitutes.

For generic walls select by the received boundary material; for solid sibling
and window IDs use their prop declaration. For a window parent whose insert was
already destroyed, select its existing `destructions_without_attachments` entry
using the received remnant state's `intact_supported_items`. Do not replay an
intact insert inside the parent animation after it was separately broken.

| Source bank | Assigned solid sources | Clock |
| --- | --- | --- |
| `wall.fantasy.debris.stone` | A1 | 16 samples, 12 FPS, clear at 1300 ms |
| `wall.fantasy.debris.wood_large` | C1 and generic wood/C2 | same |
| `wall.fantasy.debris.wood_stone` | D1/D8 and generic stone/D2 | same |
| `wall.fantasy.debris.wood_small` | F1/F8/G1 | same |

F1/F8's Wood Small assignments are literal Unity TileData selections. They are
not a claim that wood debris is the ideal physical art for those masonry walls.
The preserved originals make that mismatch reviewable; no recolor or replacement
was silently introduced.

The original 256×256 effects mount at the native owner's **cell center and base
height**, with scale `128/127`. Top-left pivots: Stone `(128,209.92)`; the others
`(128,207.36)`. All four pose keys address the same unrotated source frames.
Rotate the camera projection of XYZ; do not rotate/flip the effect artwork or
add a wall-edge pixel translation to its source cell-center pivot. Intact walls
keep their own authored pose, edge contact and registration. The existing
[positioning handoff](PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md)
owns adjacency, corners, projection and base-height rules.

At lethal impact remove the intact wall and begin the finite effect. Each new
bank declares `state_change_frame=0`. At elapsed 1300 ms stop drawing it; its last
sample still contains smoke. A late destroyed snapshot has cleared mechanics and
**no active effect**. Do not hold the last frame as rubble. Other window/door
banks retain their existing persistent endpoint behavior (`clear_at_end=false`).
When transitions become empty, invalidate a previously animated cached layer
once so it cannot retain smoke or an old intact corner.

Public `OBJECT_CHANGED` now retains the real spatial cause under the existing
current-contact privacy gate. Keep its native ancestry: wall clearance, newly
visible floor and newly visible actor commit together at the attack's actual
impact. Do not substitute a client-side height pass or guess timing from a newly
visible actor. This same correction preserves existing door open/close causes.

## Preserved inputs and validation

Durable private directory:
`/home/tommaso/Dev/neurodragon_art/sources/solid-wall-debris-20261008/`.
It holds four packed unchanged atlases, the source SHA receipt, previous
production manifest, exact crop/copy verification and `recorded-inputs/`.
The nine native experiments each include attacker/witness views, `native.json`
and public `input.json` with `sequence_format=player-v2`; they can be consumed
without rerunning or manually editing the engine.

Existing review catalog IDs:
`solid-wall-stone-corner-breach`, `solid-wall-wood-corner-breach`, and
`solid-wall-{a1,c1,d1,d8,f1,f8,g1}-breach`. Each places the actual wall at owner
`(5,4)`, EAST, base Z2, performs real repeated weapon attacks, then walks through
the breach. These are recorded inputs, not new wall artwork or a browser gallery.

Native tests cover attack discovery from both sides, nonlethal blocking, once-only
destruction, surviving corner channels, supported-item cascade and cliff exclusion.
Public replay checks cover both observers, retained owner/base/edge, finite source
bank selection, late snapshots and no live engine state during replay. Source
review verifies 64 exact frame crops, all four atlas copies, 11,180 unchanged prior
manifest entries and unchanged approved window banks/registrations.

Final native/public replay cohort: **28 passed**. Existing privacy/contact cohort:
**16 passed**. Earlier canonical presentation/schema export cohort: **2 passed**.
No Pygame raster run is counted as Pixi acceptance.

Pixi still needs to consume the above contract and be checked interactively for
all four cameras, raised walls, both corner materials, passage at impact, late
snapshots, backward seeking and finite effect cleanup. Native/data verification
does not certify those browser behaviors. Independent existing trap ancestry
failure is documented in the [ECS receipt](audits/wall-breakability-20261008/ECS_REVIEW.md);
its exact recordings are preserved in `native-diagnostics/` for separate repair.
