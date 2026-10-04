# Modular casting-hand socket authoring — 2026-10-04

Added the named `hand` socket to `game/data/neuroclient/pose-sockets.json`. It follows the **casting/offhand palm**, consistently distinct from the main weapon grip, through the actual sampled modular clip/frame/facing. All points use original 128×128 actor-cell coordinates; the existing renderer handles scale, facing row and reverse playback. No standing-pose fallback, skin pixel edits, new artwork, reimport, source-bank registration or recipe change was made.

## Source measurement and visual evidence

The original installed `game/assets/neuroclient/spritesheets/Hands1/<clip>.png` sheets isolate the visible glove/palm pixels. Each has 15 columns and eight rows in E, SE, S, SW, W, NW, N, NE order. The matching original `Offhand1`, `Melee10` and `NakedBody` sheets establish hand identity and anatomical context; they are measurement references, not new runtime dependencies. In Attack5 and Special1, the casting hand extends while the other hand retains the weapon grip.

A bounded authoring script extracts original Hands1 components at alpha≥32 and measures alpha-weighted pixel-center centroids. Equipment grip overlap identifies the hand; enlarged visual review resolves additional components. Explicitly merged or indistinguishable palms remain absent. The runtime receives only the resulting points/nulls and performs no component, equipment-overlap or source-pixel search.

Evidence is retained under `.runtime/produce-hand-sockets-20261004/`: `measure.py`, per-clip `*-measured.png` contact sheets, the initial/main-grip/offhand reference sheets, `exceptions.png`, `death-full-cell.png`, exact measured source pixels in `measurements.json`, and `receipt.json` with full SHA256 for all source sheets. All 15 source clip sheets were visually reviewed. Taunt was inspected but withheld: its clasped/overlapping palms do not establish a reliable single-hand path. Death's full-cell proof checks hand positions beyond the standing crop.

## Available and absent frames

There are **1,585 measured points and 95 explicit nulls**, across 14 clips × eight facings × 15 frames. Frame numbers are zero-based. Null means the chosen hand is occluded or cannot be distinguished from the other hand in the source pixels; it is not an implied standing offset. The entire Idle NE row genuinely hides the casting hand. No fixed-sheet rig was measured, and no `hand` data was added to those rigs.

| Clip | Measured | Null cells by facing and frame |
| --- | --- | --- |
| Idle | 105/120 | NE 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14 |
| Run | 115/120 | E 4; N 12; NE 5,6,13 |
| Attack5 | 118/120 | NW 0,1 |
| Special1 | 120/120 | None |
| TakeDamage | 119/120 | N 11 |
| Die | 117/120 | SE 5; W 2; N 1 |
| Attack1 | 107/120 | E 8,10; SE 9; S 7,9; NW 11,12; N 10,11,13; NE 8,9,10 |
| Attack2 | 117/120 | N 2,12; NE 2 |
| Attack3 | 106/120 | E 4; SE 4; S 4,7; SW 4; W 4,5; NW 4,5; N 4,5; NE 3,4,5 |
| Attack4 | 115/120 | E 1,2,3,4,6 |
| Attack6 | 118/120 | N 11,12 |
| AttackRun | 114/120 | E 0,10; S 8; N 10,11; NE 13 |
| Kick | 111/120 | SE 7; SW 2; W 2; NE 0,3,6,10,13,14 |
| Rolling | 103/120 | E 1,3,9,10; SE 0,5,10; SW 4,7,8; W 4,7; N 1,3; NE 1,4,9 |

## Produce Flame source pivot

The accepted `nature-utility-compact-palm-v7/spec.json` and `media.json` give the held back/front bank a 384-pixel cell and pivot **(192, 248.43624367372445)**. Retain that emitter/base pivot when attaching the bank to `hand`; do not re-anchor to its alpha centroid. The original authoring producer at `output/weapon-vfx/nature-utility-batch/authoring/ProduceCapture.gd` sets the retained asset position to `Vector3.ZERO`, sets `FireTorch_AC8` to zero, and disables its trail and sparks. No standing actor's hand-height offset is embedded in that held emitter position.

The head visibly leans from its base: frame31's rear crop has offset(161,231), while its front crop has offset(185,246). Those are source shape/crop offsets, not a reason to move the hand socket or center the effect on its bright pixels. The held bank is separate from the +X throw fixture. Source-bank adaptation and actual Produce Flame integration remain the parent task's responsibility.

## Verification boundary

The completed JSON passes `TypeAdapter(PoseSockets)` admission. Every selected clip has all eight facing keys, exactly 15 point/null entries per row, and in-cell point coordinates. The five pre-existing socket groups are structurally identical to the pre-edit data. Result SHA256: `8b4c8a39995f3ea6ad90bcece45941fce7abc15b14d87718854f3087a621ebc7`.

This is source-pixel/socket authoring evidence, not completed gameplay or in-engine flame validation. The parent integration must still verify actual held-bank sampling, socket fallback policy (absent means absent), depth, camera transforms and owner lifecycle.
