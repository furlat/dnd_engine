# Consolidated interiors asset coverage — 2026-09-21

Status: **complete content-disposition plan, no implementation**. Companion to [the integration plan](INTERIORS_INTEGRATION_PLAN_2026-09-21.md), subordinate to [RECOVERY_PLAN](../RECOVERY_PLAN.md). The current user request covers the entire consolidated handoff, including reusable content absent from the eight preview houses. A small room is an implementation proving case, not the completion boundary.

The separate overlapping-floor discussion is outside this document. Preserve incoming layout/elevation metadata; do not flatten those layouts or claim their assembly is supported here. Existing single-surface height, ordinary slopes/stairs, boundary placement and fixture mounting remain relevant content properties.

## Sources, totals and status meanings

Source root: `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/`.

| Authority under that root | Coverage |
| --- | --- |
| `INTERIORS-CONSOLIDATED-HANDOFF.md` | Delivery scope, explicit exclusions and superseded readiness claims |
| `handoff-interiors-2026-09-21/item-matrix.json` | All 160 rows enumerated below |
| `decor-study/reviewed-manifest.json` + `decor-study/object-destruction-bindings.json` v3 | Exact 129 accepted subjects /135 destruction banks; original review scopes remain attached |
| `interior-furniture.json` | All 49 selection choices enumerated below; not 49 new objects on top of the matrix |
| `handoff-interiors-2026-09-21/prefab-inventory.json`, `room-dressing/prefab-review/{0..7}-layout.json` | All 73 used families, 3,171 placed parts, 8 recipes /14 floors; concrete footprints and parent/socket relations |
| `wall-connections.json`, `surface-profiles.json`, `parametric.py`, `parametric-assets.json` | Supported architectural families, flat surfaces, selected roof library and source registration |
| `../architecture-handoff/backend-mapping.json`, `excluded-source-entries.json` |225 wall/frame configurations and 79 configurations outside that earlier wall-only study; physical proposals, **not** runtime definitions |
| `room-dressing/decals.json` | All 12 receiver-bound cosmetic cutouts |

No source hashes were calculated or checked. This document uses explicit IDs and current reviewed selection; it proposes no runtime registry, checksum gate or directory scan. The current recovery checkout remains implementation authority, not the artist's detached backend checkout.

- **ADD:** integrate through shared native composition/data and corresponding passive presentation binding. It is not currently an exact registered species. All accepted banks are intake scope, even if unused by the example layouts; physical policy and mounting applicability are authored separately.
- **PAIR:** reconcile a state pair through the existing container owner; six source rows represent three styled containers.
- **KEEP:** preserve the existing production identity/mechanics/media. Reconcile source references, do not create a duplicate or blindly replace installed media.
- **HOLD:** retain explicit delivery exclusion; no silent intake through the broader request.
- **SOURCE:** integrate the delivered original/static content only. Missing fracture/thermal animation remains missing, not a reason to omit the original asset or invent mechanics.

Count reconciliation: 160 = 106 recovered non-foliage + 27 foliage + 21 generated household sets + 6 indoor doors. Equivalently, 160 = 129 accepted subjects + 4 held subjects + 27 foliage. 135 = 129 subjects + 6 extra alternative banks. These are overlapping inventories, not additive gameplay counts.

## Native composition and physical-data ownership

The short codes in the tables are documentation groups, **not proposed Python classes, runtime enums or a new registry**. They select existing composers and identify the actual data work.

| Code | Reuse / required passive facts | Limits that prevent invented behavior |
| --- | --- | --- |
| P — ordinary physical prop | Existing `WorldItem`/authored-item factory; item identity, appearance, floor placement, oriented footprint, physical extent, movement/optical/propagation policy, optional Health and native remnant | Tables, beds, carts and machinery remain ordinary world objects unless an actual action is separately authored. No seating, vehicles, crafting, commerce, restraints or fuel inferred from a name. |
| A — aperture/structural prop | Existing boundary/placement composition, explicit solid portions and gaps, material, local height and channel policy | A painted opening is not a full opaque rectangle; shutters do not gain an invented opening animation. Source geometry must be authored before availability. |
| C — container state pair | Existing `StorageChest`, Inventory/Open/Close/Loot owners, explicit health/targetability and causal spill/remnant policy | One native object per chest, closed/open selects art. Wardrobes/barrels do not automatically become containers. |
| M — mounted prop | Ordinary item plus the planned passive parent/mount relation, physical wall face/local height, footprint and aftermath | Mounted art is exposed world state, not private inventory. Floor-baked destruction is used only at a real floor aftermath, not lifted intact onto the wall. |
| T — tabletop prop | Ordinary item plus exposed parent/socket relation and selected detach/break aftermath | Source set can stay one composed object; painted plates/books need not become individually lootable items. |
| L — light fixture | Existing light/torch ownership composed with P/M/T placement, explicit lit state and authored light/fuel policy | Bright pixels alone emit no light. Ovens/stoves need an explicitly chosen light capability; they do not inherit campfire Rest/Cook automatically. |
| D — flat dressing | Receiver-bound passive world content with identity, floor/wall relation and nonblocking navigation policy | No invented hazard, concealment or HP merely to enter a health-mandatory blocker table. Where a rug has selected destructible item behavior, compose that explicitly with a nonblocking P object. |
| F — foliage | Low ground cover and wall ivy use receiver dressing; bushes use a physical prop profile with measured extent/channel choices | Original 27 families are in scope. No supplied fracture, burning or scorch animation; no automatic concealment/walkability assumption for a tall bush. |
| S — stair/structural assembly | Existing native terrain/stair/slope and boundary owners with authored rise/run/footprint and art identity | Intake static geometry/appearance and available banks; no automatic walkable platform, climb action or destructive support collapse from a sprite. |
| K — existing door | Existing authored door factory/profile, mechanism, health, channels and remnant state | Keep native IDs and installed opening/destruction/depth behavior. |
| H — held | No new native definition or media selection | Preserve source identity and explicit hold even where an old label is misleading. |

Before declaring an ADD/SOURCE row integrated, author its native description, exact item/visual identity, placement kind, real footprint, facing, physical base/extent, movement blocking, optical blocking, propagation blocking, targetability, health/material response if applicable, remnant occupancy, and any chosen parent/mount/light relation. Absence of an interaction is an explicit valid result; absence of collision/visibility data is not. Reuse `StaticBlockerDefinition` where its health-bearing semantics fit; otherwise use existing optional-health item/world composition. Do not invent arbitrary 1 HP or ten-foot geometry to satisfy its constructor.

The handoff has measured image registration and preview placements, **not** verified HP/physical height for every prop. Finish those values with bounded offline inspection/authoring through the shared schema before admitting that content. Sprite padding, material label and `blocking:true` do not supply a 3D envelope or optical opacity. Physical furniture footprint, gameplay height, image pivot and local visual lift are distinct. Store no camera-derived native position.

Existing `environment.blocker.crate` is 20 HP but nonblocking; do not silently change it to match preview crate occupancy. Use an explicitly authored blocking variant if required. Ordinary barrels remain separate from the existing oil-spill barrel. The wheeled cannon is not automatically an ArcaneDevice, and the stone arch is not automatically a teleport portal.

## Every item-matrix row

Exact `asset` keys are shown. For `misc-aN`…`misc-eN`, the source family is `fantasy.misc.aN`…`fantasy.misc.eN`; for `chest-*`, it is `fantasy.chest.*`. `generated-X` uses `authored.interior.X`, except `generated-indoor-door-X` uses `authored.indoor-door.X`. Flora IDs are already complete. `fireplace` maps source group `FirePlace` but still has no source-catalog family; assign an explicit local mapping, not a guessed existing family. B4 is absent in the source sequence.

“Banks” counts the exact selected metadata rows in the reviewed matrix; 0 for held/foliage does not mean the original source image is absent. All ADD rows have accepted destruction artwork, but native behavior and mounted/floor applicability still need the contracts above.

| Exact matrix asset | Source meaning | Composer / disposition | Banks |
| --- | --- | --- | ---: |
| `chest-a1` | chest variant | C / PAIR | 1 |
| `chest-a2` | chest variant | C / PAIR | 1 |
| `chest-a3` | chest variant | C / PAIR | 1 |
| `chest-a4` | chest variant | C / PAIR | 1 |
| `chest-b1` | chest variant | C / PAIR | 1 |
| `chest-b2` | chest variant | C / PAIR | 1 |
| `fireplace` | fire pit | L+P / ADD | 1 |
| `misc-a1` | spent fire / ashes | D / ADD | 1 |
| `misc-a2` | single pottery jar | P / ADD | 2 |
| `misc-a3` | paired pottery jars | P / ADD | 1 |
| `misc-a4` | pottery cluster | P / ADD | 1 |
| `misc-a5` | tall clay oven | P; optional authored L / ADD | 1 |
| `misc-a6` | low clay stove | P; optional authored L / ADD | 1 |
| `misc-a7` | small lidded vessel | P / ADD | 1 |
| `misc-a8` | barrel | P / ADD | 1 |
| `misc-a9` | barrel cluster | P / ADD | 1 |
| `misc-b1` | crate | P / ADD | 1 |
| `misc-b10` | covered market counter | P / ADD | 1 |
| `misc-b11` | handcart | P / ADD | 1 |
| `misc-b12` | fabric market canopy | P / ADD | 1 |
| `misc-b13` | wooden tabletop/planks | P / ADD | 1 |
| `misc-b14` | pale market stall | P / ADD | 1 |
| `misc-b15` | training dummy | P / ADD | 1 |
| `misc-b16` | grindstone | P / ADD | 1 |
| `misc-b17` | red produce stall | P / ADD | 1 |
| `misc-b18` | rough market stall | P / ADD | 1 |
| `misc-b19` | green market stall | P / ADD | 1 |
| `misc-b2` | crate stack | P / ADD | 1 |
| `misc-b20` | produce tub | P / ADD | 1 |
| `misc-b21` | hide drying rack | P / ADD | 1 |
| `misc-b22` | conflicting hay bedding/coffin label | H / HOLD | 0 |
| `misc-b23` | feed trough | P / ADD | 1 |
| `misc-b24` | notice board | P / ADD | 1 |
| `misc-b25` | wooden platform | S+P / ADD | 1 |
| `misc-b26` | bench | P / ADD | 1 |
| `misc-b27` | wooden crib | P / ADD | 1 |
| `misc-b28` | small wooden table | P / ADD | 1 |
| `misc-b29` | gallows platform | S+P / ADD | 1 |
| `misc-b3` | large crate stack | P / ADD | 1 |
| `misc-b30` | hanging trade sign 1 | M / ADD | 1 |
| `misc-b31` | hanging trade sign 2 | M / ADD | 1 |
| `misc-b32` | hanging trade sign 3 | M / ADD | 1 |
| `misc-b33` | hanging trade sign 4 | M / ADD | 1 |
| `misc-b34` | hanging trade sign 5 | M / ADD | 1 |
| `misc-b35` | hanging trade sign 6 | M / ADD | 1 |
| `misc-b36` | hanging trade sign 7 | M / ADD | 1 |
| `misc-b37` | red covered table | P / ADD | 1 |
| `misc-b38` | pale covered table | P / ADD | 1 |
| `misc-b39` | red rug | D / ADD | 1 |
| `misc-b40` | pale rug | D / ADD | 1 |
| `misc-b41` | rough hide tent | P / ADD | 1 |
| `misc-b42` | roofed well | P / ADD | 1 |
| `misc-b43` | large fabric tent | P / ADD | 1 |
| `misc-b44` | freestanding red banner, short | P / ADD | 1 |
| `misc-b45` | freestanding red banner, tall | P / ADD | 1 |
| `misc-b46` | red canopy | P / ADD | 1 |
| `misc-b47` | red small tent | P / ADD | 1 |
| `misc-b48` | conflicting siege engine/crane label | H / HOLD | 0 |
| `misc-b49` | sailboat | H / HOLD | 0 |
| `misc-b5` | cart | P / ADD | 1 |
| `misc-b50` | cargo boat | H / HOLD | 0 |
| `misc-b51` | wooden cage | P / ADD | 1 |
| `misc-b52` | signpost frame | P / ADD | 1 |
| `misc-b53` | wooden chair | P / ADD | 1 |
| `misc-b54` | window/shutter frame | A / ADD | 1 |
| `misc-b55` | tall scaffold | S+P / ADD | 1 |
| `misc-b56` | scaffold | S+P / ADD | 1 |
| `misc-b57` | archery target | P / ADD | 1 |
| `misc-b58` | felled log | P / ADD | 1 |
| `misc-b59` | ladder | S+P / ADD | 1 |
| `misc-b6` | loaded hay wagon | P / ADD | 1 |
| `misc-b60` | armillary/workshop apparatus | P / ADD | 1 |
| `misc-b61` | alchemy bench | P / ADD | 1 |
| `misc-b7` | water trough | P / ADD | 1 |
| `misc-b8` | timber pile | P / ADD | 1 |
| `misc-b9` | wheelbarrow | P / ADD | 1 |
| `misc-c1` | stone fireplace | L+P / ADD | 1 |
| `misc-c10` | rough grave marker | P / ADD | 2 |
| `misc-c11` | slender monument | P / ADD | 2 |
| `misc-c12` | small metal cage | P / ADD | 1 |
| `misc-c13` | large metal cage | P / ADD | 1 |
| `misc-c14` | stone portal / monumental arch | A / ADD | 1 |
| `misc-c2` | anvil | P / ADD | 1 |
| `misc-c3` | wheeled cannon | P / ADD | 1 |
| `misc-c4` | cannonball pile | P / ADD | 1 |
| `misc-c5` | animal statue on round plinth | P / ADD | 2 |
| `misc-c6` | winged figure statue on round plinth | P / ADD | 2 |
| `misc-c7` | square ornamental pedestal | P / ADD | 2 |
| `misc-c8` | stone well | P / ADD | 1 |
| `misc-c9` | stone bench | P / ADD | 1 |
| `misc-d1` | patterned hanging banner | M / ADD | 1 |
| `misc-d2` | plain hanging banner | M / ADD | 1 |
| `misc-d3` | narrow hanging banner | M / ADD | 1 |
| `misc-d4` | quartered hanging banner | M / ADD | 1 |
| `misc-d5` | striped hanging banner | M / ADD | 1 |
| `misc-e1` | hay bale arrangement | P / ADD | 1 |
| `misc-e10` | loose straw / hay patch | D / ADD | 1 |
| `misc-e11` | loose straw / hay patch | D / ADD | 1 |
| `misc-e2` | hay bale arrangement | P / ADD | 1 |
| `misc-e3` | hay bale arrangement | P / ADD | 1 |
| `misc-e4` | hay bale arrangement | P / ADD | 1 |
| `misc-e5` | loose straw / hay patch | D / ADD | 1 |
| `misc-e6` | loose straw / hay patch | D / ADD | 1 |
| `misc-e7` | loose straw / hay patch | D / ADD | 1 |
| `misc-e8` | loose straw / hay patch | D / ADD | 1 |
| `misc-e9` | loose straw / hay patch | D / ADD | 1 |
| `fantasy.flora.a1` | ground moss / low foliage a1 | F / SOURCE | 0 |
| `fantasy.flora.a2` | ground moss / low foliage a2 | F / SOURCE | 0 |
| `fantasy.flora.a3` | ground moss / low foliage a3 | F / SOURCE | 0 |
| `fantasy.flora.a4` | ground moss / low foliage a4 | F / SOURCE | 0 |
| `fantasy.flora.a5` | ground moss / low foliage a5 | F / SOURCE | 0 |
| `fantasy.flora.a6` | ground moss / low foliage a6 | F / SOURCE | 0 |
| `fantasy.flora.a7` | ground moss / low foliage a7 | F / SOURCE | 0 |
| `fantasy.flora.b1` | shrub / bush b1 | F / SOURCE | 0 |
| `fantasy.flora.b2` | shrub / bush b2 | F / SOURCE | 0 |
| `fantasy.flora.b3` | shrub / bush b3 | F / SOURCE | 0 |
| `fantasy.flora.b4` | shrub / bush b4 | F / SOURCE | 0 |
| `fantasy.flora.b5` | shrub / bush b5 | F / SOURCE | 0 |
| `fantasy.flora.b6` | shrub / bush b6 | F / SOURCE | 0 |
| `fantasy.wallflora.a1` | wall ivy / climbing foliage a1 | F / SOURCE | 0 |
| `fantasy.wallflora.a10` | wall ivy / climbing foliage a10 | F / SOURCE | 0 |
| `fantasy.wallflora.a11` | wall ivy / climbing foliage a11 | F / SOURCE | 0 |
| `fantasy.wallflora.a12` | wall ivy / climbing foliage a12 | F / SOURCE | 0 |
| `fantasy.wallflora.a13` | wall ivy / climbing foliage a13 | F / SOURCE | 0 |
| `fantasy.wallflora.a14` | wall ivy / climbing foliage a14 | F / SOURCE | 0 |
| `fantasy.wallflora.a2` | wall ivy / climbing foliage a2 | F / SOURCE | 0 |
| `fantasy.wallflora.a3` | wall ivy / climbing foliage a3 | F / SOURCE | 0 |
| `fantasy.wallflora.a4` | wall ivy / climbing foliage a4 | F / SOURCE | 0 |
| `fantasy.wallflora.a5` | wall ivy / climbing foliage a5 | F / SOURCE | 0 |
| `fantasy.wallflora.a6` | wall ivy / climbing foliage a6 | F / SOURCE | 0 |
| `fantasy.wallflora.a7` | wall ivy / climbing foliage a7 | F / SOURCE | 0 |
| `fantasy.wallflora.a8` | wall ivy / climbing foliage a8 | F / SOURCE | 0 |
| `fantasy.wallflora.a9` | wall ivy / climbing foliage a9 | F / SOURCE | 0 |
| `generated-candlesticks` | candlesticks | L+T / ADD | 1 |
| `generated-plain-dining-table` | plain dining table | P / ADD | 1 |
| `generated-tableware` | tableware | T / ADD | 1 |
| `generated-hanging-utensils` | hanging utensils | M / ADD | 1 |
| `generated-preparation-counter` | preparation counter | P / ADD | 1 |
| `generated-wall-shelves` | wall shelves | M / ADD | 1 |
| `generated-wash-basin` | wash basin | P / ADD | 1 |
| `generated-ingredient-shelves` | ingredient shelves | P / ADD | 1 |
| `generated-tool-rack` | tool rack | M / ADD | 1 |
| `generated-work-stool` | work stool | P / ADD | 1 |
| `generated-sack-bundles` | sack bundles | P / ADD | 1 |
| `generated-storage-shelving` | storage shelving | P / ADD | 1 |
| `generated-bed` | bed | P / ADD | 1 |
| `generated-bedside-stand` | bedside stand | P / ADD | 1 |
| `generated-wardrobe` | wardrobe | P / ADD | 1 |
| `generated-washstand` | washstand | P / ADD | 1 |
| `generated-bookshelf` | bookshelf | P / ADD | 1 |
| `generated-papers-and-ink` | papers and ink | T / ADD | 1 |
| `generated-writing-desk` | writing desk | P / ADD | 1 |
| `generated-timber-stair-flight` | timber stair flight | S+P / ADD | 1 |
| `generated-wall-candle-holder` | wall candle holder | L+M / ADD | 1 |
| `generated-indoor-door-shabby` | indoor door shabby | K / KEEP | 1 |
| `generated-indoor-door-elegant` | indoor door elegant | K / KEEP | 1 |
| `generated-indoor-door-shabby-plain` | indoor door shabby plain | K / KEEP | 1 |
| `generated-indoor-door-shabby-battens` | indoor door shabby battens | K / KEEP | 1 |
| `generated-indoor-door-shabby-patched` | indoor door shabby patched | K / KEEP | 1 |
| `generated-indoor-door-elegant-three-panel` | indoor door elegant three panel | K / KEEP | 1 |

## Destruction bank accounting and state ownership

All 135 selected banks are covered by the preceding table and the exact per-row paths in the source matrix/current reviewed allowlist. Preserve their review scope; no blanket new visual approval is claimed. Reconstructed `intact.png`, finite sequence and stable `wreck.png` belong together. Do not port the preview's older impact manifest.

| Native meaning | Source rows / exact selection | Disposition |
| --- | --- | --- |
| Chest style1 | A1 closed / A2 open | Reconcile existing generic original A1/A2 art before adding new collapse; preserve its identity/compatibility. |
| Chest style2 | A3 closed / A4 open | One new styled container; A3 is the 15-instance prefab choice. |
| Chest style3 | B1 closed / B2 open | One new styled container, even though neither is used in the saved houses. |
| Six alternative partition sets | `misc-a2`, `misc-c5`, `misc-c6`, `misc-c7`, `misc-c10`, `misc-c11` each have `impact-a` and `impact-b` | Both accepted banks are included; select an explicit authored presentation variant. Variant name does not prove hit direction or different native aftermath. |
| Remaining single-bank subjects | All other accepted matrix rows, including six already-installed indoor door designs | Import/reconcile by exact source identity. Already-installed doors keep their existing state/swing/outcome selection. |

Chest roots: closed A1/A3/B1 from `candidates-volumetric-timber-v3-contact`; open A2/A4 from `candidates-volumetric-timber-v9-contact`; open B2 from `candidates-volumetric-timber-v12-contact`, each under `decor-study/{root}/chest-{id}/impact-a`. Exact cells/pivots/frames/FPS come from each selected metadata file. There is no delivered smooth lid-opening sequence.

Accepted destruction is not approved mounted destruction at arbitrary height. All mounted/tabletop selections must retain a mechanically correct floor aftermath and explicit visual coverage status. Do not invent suspended debris, silently delete children, or omit the selected object's aftermath because an early preview did so. Generic prop/remnant selection must support stateless furniture without masquerading as a door/trap. Native HP/state/removal timing remains event-owned; collapse duration is presentation-owned.

## All 49 furniture selection choices

These reuse the matrix, not a second gameplay catalog.28 choices occur in the eight saved layouts (368 placed parts); 21 additional choices are intentionally available but unused. Preserve all 49. “Length” is source authoring, not proof of native collision; a dash means unspecified. The source mount/attachment declaration overrides the coarse matrix `floor` label.

| Selection key | Exact source family | Source placement / blocking / length | Saved uses |
| --- | --- | --- | ---: |
| `table` | `authored.interior.plain-dining-table` | floor; blocks; 1 | 9 |
| `bench` | `fantasy.misc.b26` | floor; blocks; — | 8 |
| `chair` | `fantasy.misc.b53` | floor; blocks; — | 19 |
| `rug` | `fantasy.misc.b39` | floor; nonblocking; — | 23 |
| `chest` | `fantasy.chest.a3` | floor; blocks; — | 15 |
| `pots` | `fantasy.misc.a3` | floor; blocks; — | 13 |
| `stove` | `fantasy.misc.a5` | floor; blocks; — | 9 |
| `alchemy` | `fantasy.misc.b61` | floor; blocks; — | 7 |
| `crate` | `fantasy.misc.b1` | floor; blocks; — | 6 |
| `bed` | `authored.interior.bed` | floor; blocks; 2 | 14 |
| `wardrobe` | `authored.interior.wardrobe` | floor; blocks; 1 | 14 |
| `bookshelf` | `authored.interior.bookshelf` | floor; blocks; 1 | 6 |
| `desk` | `authored.interior.writing-desk` | floor; blocks; 1 | 6 |
| `counter` | `authored.interior.preparation-counter` | floor; blocks; 1 | 9 |
| `washstand` | `authored.interior.washstand` | floor; blocks; 1 | 8 |
| `shelves` | `authored.interior.ingredient-shelves` | floor; blocks; 1 | 7 |
| `bedside` | `authored.interior.bedside-stand` | floor; blocks; 1 | 13 |
| `sacks` | `authored.interior.sack-bundles` | floor; blocks; 1 | 7 |
| `candlesticks` | `authored.interior.candlesticks` | tabletop; nonblocking; — | 13 |
| `tableware` | `authored.interior.tableware` | tabletop; nonblocking; — | 18 |
| `papers-and-ink` | `authored.interior.papers-and-ink` | tabletop; nonblocking; — | 6 |
| `stool` | `authored.interior.work-stool` | floor; blocks; 1 | 6 |
| `storage` | `authored.interior.storage-shelving` | floor; blocks; 1 | 22 |
| `wall-shelves` | `authored.interior.wall-shelves` | wall; nonblocking; — | 27 |
| `hanging-utensils` | `authored.interior.hanging-utensils` | wall; nonblocking; — | 9 |
| `tool-rack` | `authored.interior.tool-rack` | wall; nonblocking; — | 7 |
| `wall-candle-holder` | `authored.interior.wall-candle-holder` | wall; nonblocking; — | 56 |
| `wash-basin` | `authored.interior.wash-basin` | floor; blocks; — | 11 |
| `statue-animal` | `fantasy.misc.c5` | floor; blocks; 1 | 0 |
| `statue-winged` | `fantasy.misc.c6` | floor; blocks; 1 | 0 |
| `ornamental-pedestal` | `fantasy.misc.c7` | floor; blocks; 1 | 0 |
| `stone-bench` | `fantasy.misc.c9` | floor; blocks; 2 | 0 |
| `pottery-jar` | `fantasy.misc.a2` | floor; blocks; 1 | 0 |
| `pottery-cluster` | `fantasy.misc.a4` | floor; blocks; 1 | 0 |
| `barrel` | `fantasy.misc.a8` | floor; blocks; 1 | 0 |
| `barrel-cluster` | `fantasy.misc.a9` | floor; blocks; 1 | 0 |
| `rug-pale` | `fantasy.misc.b40` | floor-decal; nonblocking; 1 | 0 |
| `wall-banner-1` | `fantasy.misc.d1` | wall; nonblocking; 1 | 0 |
| `wall-banner-2` | `fantasy.misc.d2` | wall; nonblocking; 1 | 0 |
| `wall-banner-3` | `fantasy.misc.d3` | wall; nonblocking; 1 | 0 |
| `wall-banner-4` | `fantasy.misc.d4` | wall; nonblocking; 1 | 0 |
| `wall-banner-5` | `fantasy.misc.d5` | wall; nonblocking; 1 | 0 |
| `trade-sign-1` | `fantasy.misc.b30` | wall; nonblocking; 1 | 0 |
| `trade-sign-2` | `fantasy.misc.b31` | wall; nonblocking; 1 | 0 |
| `trade-sign-3` | `fantasy.misc.b32` | wall; nonblocking; 1 | 0 |
| `trade-sign-4` | `fantasy.misc.b33` | wall; nonblocking; 1 | 0 |
| `trade-sign-5` | `fantasy.misc.b34` | wall; nonblocking; 1 | 0 |
| `trade-sign-6` | `fantasy.misc.b35` | wall; nonblocking; 1 | 0 |
| `trade-sign-7` | `fantasy.misc.b36` | wall; nonblocking; 1 | 0 |

## All 73 families actually used by the saved layouts

This table catches architecture/state references absent from the 160-item matrix. Counts total3,171 parts, not 3,171 native objects. Floor tiles, roofs, wall courses, rugs and related assembly pieces must be interpreted by their actual component/placement role. A source family ending `.closed` remains state artwork for an existing door, not a second species.

| Exact family | Parts | Disposition |
| --- | ---: | --- |
| `authored.indoor-door.elegant-three-panel.closed` | 13 | KEEP existing indoor door; closed state alias |
| `authored.indoor-door.elegant.closed` | 13 | KEEP existing indoor door; closed state alias |
| `authored.indoor-door.shabby-battens.closed` | 6 | KEEP existing indoor door; closed state alias |
| `authored.indoor-door.shabby-patched.closed` | 6 | KEEP existing indoor door; closed state alias |
| `authored.indoor-door.shabby-plain.closed` | 18 | KEEP existing indoor door; closed state alias |
| `authored.interior.bed` | 14 | P / ADD |
| `authored.interior.bedside-stand` | 13 | P / ADD |
| `authored.interior.bookshelf` | 6 | P / ADD |
| `authored.interior.candlesticks` | 13 | L+T / ADD |
| `authored.interior.hanging-utensils` | 9 | M / ADD |
| `authored.interior.ingredient-shelves` | 7 | P / ADD |
| `authored.interior.papers-and-ink` | 6 | T / ADD |
| `authored.interior.plain-dining-table` | 9 | P / ADD |
| `authored.interior.preparation-counter` | 9 | P / ADD |
| `authored.interior.sack-bundles` | 7 | P / ADD |
| `authored.interior.storage-shelving` | 22 | P / ADD |
| `authored.interior.tableware` | 18 | T / ADD |
| `authored.interior.tool-rack` | 7 | M / ADD |
| `authored.interior.wall-candle-holder` | 56 | L+M / ADD |
| `authored.interior.wall-shelves` | 27 | M / ADD |
| `authored.interior.wardrobe` | 14 | P / ADD |
| `authored.interior.wash-basin` | 11 | P / ADD |
| `authored.interior.washstand` | 8 | P / ADD |
| `authored.interior.work-stool` | 6 | P / ADD |
| `authored.interior.writing-desk` | 6 | P / ADD |
| `fantasy.chest.a3` | 15 | C / PAIR |
| `fantasy.door.a1` | 11 | KEEP environment.door.fantasy_a1 |
| `fantasy.ground.d1` | 996 | ADD/reconcile explicit surface profile; floor/roof role comes from placement |
| `fantasy.ground.f1` | 496 | ADD/reconcile explicit surface profile; floor/roof role comes from placement |
| `fantasy.misc.a3` | 13 | P / ADD |
| `fantasy.misc.a5` | 9 | P; optional authored L / ADD |
| `fantasy.misc.b1` | 6 | P / ADD |
| `fantasy.misc.b26` | 8 | P / ADD |
| `fantasy.misc.b39` | 23 | D / ADD |
| `fantasy.misc.b53` | 19 | P / ADD |
| `fantasy.misc.b61` | 7 | P / ADD |
| `fantasy.roof.c1` | 100 | ADD passive roof assembly profile |
| `fantasy.roof.c6` | 28 | ADD passive roof assembly profile |
| `fantasy.roof.c8` | 10 | ADD passive roof assembly profile |
| `fantasy.roof.d1` | 108 | ADD passive roof assembly profile |
| `fantasy.roof.d6` | 32 | ADD passive roof assembly profile |
| `fantasy.roof.d8` | 4 | ADD passive roof assembly profile |
| `fantasy.roof.f1` | 96 | ADD passive roof assembly profile |
| `fantasy.roof.f6` | 20 | ADD passive roof assembly profile |
| `fantasy.roof.f8` | 4 | ADD passive roof assembly profile |
| `fantasy.wall.a13` | 6 | ADD selected existing-height stair assembly profile |
| `fantasy.wall.c1` | 26 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.c2` | 9 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.c4` | 34 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.c6` | 2 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.d1` | 54 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.d10` | 16 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.d12` | 62 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.d16` | 44 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.d2` | 12 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.d5` | 30 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.d6` | 4 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.d7` | 58 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.d8` | 152 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.e6` | 2 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.f1` | 15 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.f10` | 4 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.f12` | 16 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.f16` | 20 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.f2` | 4 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.f5` | 8 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.f6` | 1 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.f7` | 20 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.f8` | 53 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.g1` | 116 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.g10` | 18 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.g3` | 14 | ADD exact boundary/structural profile; retain openings |
| `fantasy.wall.g8` | 42 | ADD exact boundary/structural profile; retain openings |

## Architecture beyond those 73 used families

The architecture register is wider than the house selection: 225 wall/frame configurations = 87 Fantasy + 138 Desert. The earlier study excluded79 additional wall-named configurations (17 Fantasy + 62 Desert) **only from its wall-specific scope**. That did not reject the Fantasy stair/pillar/gable art. Current user exclusions still remove Desert/palisade house intake; already-installed Desert doors remain working production content.

All in-scope Fantasy profiles below need explicit data for placement, physical height/footprint, visible gaps and blocked channels before native admission. Existing generic `DirectionalWall`/material drawing is a capability analogue, not exact coverage. A `full`/`low`/`aperture` classification in `backend-mapping.json` is a proposal; it is not measured geometry. A window must be usable for its authored sight/attack policy, not a solid wall with a transparent picture. Keep operation rules separate: fixed bars do not imply shutters, and misc B54 does not supply an approved animated closure.

Exact `fantasy.wall.` suffixes below partition all 87 listed Fantasy configurations. The eight B-family profiles remain excluded palisade-family house content; no unrelated existing native barricade is removed.

| Visual role / native profile group | Exact `fantasy.wall.` suffixes | Count | Disposition |
| --- | --- | ---: | --- |
| arch | `a9`, `c6`, `d6`, `f6` | 4 | ADD shared boundary/structural data |
| arch_fragment | `a17`, `a18` | 2 | ADD shared boundary/structural data |
| barred_window | `a4`, `a5`, `c4`, `d16`, `d7`, `f16`, `f7`, `g8`, `g9` | 9 | ADD shared boundary/structural data |
| braced_palisade | `b11` | 1 | HOLD palisade-family house intake |
| corner | `a16`, `a2`, `c2`, `d10`, `d11`, `d2`, `f10`, `f11`, `f2`, `g3` | 10 | ADD shared boundary/structural data |
| curved_wall | `a20` | 1 | ADD shared boundary/structural data |
| damaged_corner | `g11` | 1 | ADD shared boundary/structural data |
| damaged_palisade | `b4` | 1 | HOLD palisade-family house intake |
| damaged_wall | `g5`, `g6` | 2 | ADD shared boundary/structural data |
| framed_wall | `c3` | 1 | ADD shared boundary/structural data |
| jamb | `a7`, `d3`, `d4`, `f3`, `f4` | 5 | ADD shared boundary/structural data |
| lintel | `a3`, `c5`, `d5`, `e10`, `e11`, `e12`, `e7`, `f5`, `g10` | 9 | ADD shared boundary/structural data |
| low_corner | `a11` | 1 | ADD shared boundary/structural data |
| low_palisade | `b3` | 1 | HOLD palisade-family house intake |
| low_wall | `a10`, `d19`, `f19` | 3 | ADD shared boundary/structural data |
| open_frame | `e2`, `e3`, `e4`, `e5`, `e6`, `e8`, `e9` | 7 | ADD shared boundary/structural data |
| palisade | `b1`, `b2` | 2 | HOLD palisade-family house intake |
| rail_corner | `e16` | 1 | ADD shared boundary/structural data |
| rail_corner | `b9` | 1 | HOLD palisade-family house intake |
| rail_fence | `e15`, `e17` | 2 | ADD shared boundary/structural data |
| rail_fence | `b7`, `b8` | 2 | HOLD palisade-family house intake |
| solid_wall | `a1`, `a15`, `c1`, `d1`, `d12`, `d13`, `d14`, `d15`, `d8`, `d9`, `f1`, `f12`, `f13`, `f14`, `f15`, `f8`, `f9`, `g1`, `g2` | 19 | ADD shared boundary/structural data |
| window | `g4`, `g7` | 2 | ADD shared boundary/structural data |

The other 17 Fantasy configurations are fully accounted for:

| Exact families | Count | Treatment |
| --- | ---: | --- |
| `fantasy.wall.a12`, `.a13`, `.a14`, `.a21`, `.a22` | 5 | Stair variants: reusable geometry/appearance; A13 already selected by every saved stair run. Author rise/run and placement through current terrain owners; do not guess from image padding. |
| `fantasy.wall.a6`, `.a19` | 2 | Pillars: shared physical object/structural profile, including footprint and sight behavior. |
| `fantasy.wall.a8` | 1 | Rubble: explicit low obstacle/dressing profile; not automatically the remnant of every masonry wall. |
| `fantasy.wall.d17`, `.d18`, `.f17`, `.f18` | 4 | Gables: architecture pieces with real placement/height and blocked regions, separate from full wall courses. |
| `fantasy.wall.e1`, `.e18` | 2 | Posts: structural object/partial-boundary data, not opaque whole bays. |
| `fantasy.wall.b5`, `.b6`, `.b10` | 3 | Palisade-set spikes/posts: held with excluded house family; no new intake by accidental broad glob. |

The six building style profiles remain A/C/D/E/F/G. `wall-connections.json` owns allowed adjacency, not generic `Material`: A ground 1/2/5/9; C1/2/4/6; D ground 1/2/7/6 with distinct 12/10/16 course pieces; E4/9/6 with open framing; F ground 1/2/7/6 with distinct 12/10/16; G1/3/8. Interior partitions use G1/D8/F8 and headers G10/D5/F5. Do not substitute thick exterior footings for partitions or an opaque wall for open timber. Unused compatible profiles stay in the library; the saved house generator need not pick every available piece.

| Further library | Exact families | Intake requirement |
| --- | --- | --- |
| Flat floors/decks | `fantasy.ground.d1`, `fantasy.ground.f1` | D1 is selected for A/D/F stone surfaces; F1 for C/E/G timber. Reconcile against installed floor bindings before creating duplicate media or a surface variant. Do not substitute raised D2/D3/F3. |
| Exterior ground | `fantasy.ground.a1` | Available preview ground, though not counted among the 73 house-part families; reuse/reconcile exact existing ground identity where present. |
| Roof slopes/corners/caps | `fantasy.roof.c1`, `.c6`, `.c7`, `.c8`; `fantasy.roof.d1`, `.d6`, `.d7`, `.d8`; `fantasy.roof.f1`, `.f6`, `.f7`, `.f8` | All 12 are loaded by the source library. Only 9 occur in saved recipes; include the three unused `*7` variants. Author assembly/physical and visual extent separately; roof art is not automatically a traversable floor. |
| Generated timber flight | `authored.interior.timber-stair-flight` | Already in the 160-row matrix; do not count twice or lose it because the generator currently always selects A13. |
| Room-shell geometry | Saved floor cells, boundary positions, true openings, doors and approaches | Import floor coverage independently of furniture-filtered preview reachability. Existing heights and physical mounts are data; drawing/cutaway cannot change their mechanics. |

Overlapping-floor assembly remains with the separate task. Retain those source records and source family choices; finish the reusable asset definitions, available single-floor assembly content and ordinary non-overlapping height cases here without importing that task's design.

## Existing doors and traps: explicit deduplication

Keep ten recovered native doors: `environment.door.fantasy_a1`, `environment.door.desert_a1`, `environment.door.fantasy_c1`, `fantasy_c3`, `fantasy_c5`, `desert_c1`, `desert_c3`, `desert_c5`, `desert_c7`, `desert_c9` (the last eight retain the same `environment.door.` prefix). Open source partners are even-numbered art states; do not register each as another door. Keep all six indoor IDs shown in the matrix, using `environment.door.indoor_door_` plus the style with underscores. Keep the generic `environment.directional_door` compatibility binding.

Keep all 12 existing `environment.trap.{swinging_blade|crusher}.{stone|wood}.{workshop|brassbound|fortress}` hardware profiles, their controls, damage/destruction and remnants. They are related handoff content, outside the 160-row count. Source reconciliation is not authorization to rebuild them or replace their established banks with similarly named decoration banks. The current implementation has 16 door profiles, 17 renderer door entries including the generic alias, and 12 trap entries; the source matrix's six rows do not reduce that coverage.

## Decals, foliage, attachments and omissions

All 12 decal IDs are included: floor `soot`, `dirt-scuff`, `moss-damp`, `plaster-chips`, `wine-spill`, `wax-drips`, `shoe-scuffs`, `straw`; wall `wall-crack`, `damp-streaks`, `candle-soot`, `watermark`. They have authored 128×128 source images, baked 0.6 alpha, wood/stone/plaster compatibility and `navigation_effect:false`. Keep receiver identity, position/rotation and observed persistence as passive dressing. Wall streaks stay upright. No adjacency atlas, damage condition, extinguishing or material interaction is supplied by this catalog.

All 27 foliage groups are already individually listed: 7 ground-cover A, 6 bushes B and 14 wall ivy. The matrix phrase `thermal_response_only` is **not** evidence that a thermal animation exists; the consolidated handoff says it does not. Keep static foliage usable and record the missing thermal/fracture coverage explicitly. Destruction/fire mechanics, if selected later, must come from real material/condition rules rather than an art-status string.

Tabletop ownership is supplied for candlesticks/tableware/papers-and-ink; wall mounting for wall-shelves/hanging-utensils/tool-rack/wall-candle-holder plus all 12 recovered sign/banner families. The examples contain 37 tabletop references and 99 wall-fitting records. The matrix incorrectly calls candlesticks/tool-rack simply `floor`; follow the exact selection/placement records.37/99 are placement totals, not additional asset families. All named parent references exist in the saved examples; preserve the relation and native destruction aftermath.

Actual absent artwork remains absent: guardrails/corner protection appropriate to these assemblies, fitted curtains and framed paintings/maps/portraits are not established by this selection. The twelve thematic building briefs are design material, not extra authored assets or a mandate for twelve crafting/trading/rest systems. Boats/crane subjects remain stopped. Blood, elemental splashes and fireball/scorch packages are separate completed/in-progress authorities, not new interiors imports.

## Completion evidence and review

Completion means every included row has a deliberate native identity or receiver-bound dressing/structural role, authored physical/visibility/walkability/placement/height data, and the correct passive media selection. Every accepted bank has an explicit use or retained variant mapping, with mounted applicability stated. An asset absent from a saved house is still covered. No renderer inference supplies missing gameplay values.

Use the existing initialization/content registry and native event/replay tests. Exercise representative shared capability families (footprint/rotation, sight/propagation, container state/spill, light toggle/removal, parent release, ordinary destruction/remnant) through real actions, plus lean identity/coverage checks over the explicit data. The four-camera gallery demonstrates those shared mechanics and all content shapes/material families; it is not a separate animation runtime or a per-sprite game implementation. Do not create a runtime asset auditor or require a full video for every duplicate bank before shared code can progress.

Inventory checks performed for this document: 160 unique matrix IDs, 49 unique furniture choices, 73 unique used families, 3,171 parts, 129 accepted subjects and 135 bank references, 4 held IDs and 27 foliage IDs. The three exact-ID tables were compared to their source sets with no omissions or duplicates; the 135 selected metadata paths match the current reviewed allowlist exactly. These were metadata/count comparisons, not image approval, gameplay tests or hashes. No production data/code or source assets were changed.

Independent anti-slop and anti-OOP/ECS reviews of the expanded main plan included this companion and are complete. The anti-slop reviewer independently compared all160 item IDs and all73 used families/3,171 parts with the sources, without omissions, extras or duplicate IDs. The ECS reviewer approved after the main plan separated object enumeration from spell recipient policy, made manual footprint access explicit, and completed child-side attachment cleanup. The main plan's review record contains the findings and amendments. This is plan approval, not gameplay or new visual validation.
