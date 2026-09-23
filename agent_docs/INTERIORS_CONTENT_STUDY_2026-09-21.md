# Interiors content study — 2026-09-21

Status: read-only study for the user-relayed handoff. This proposes a bounded first integration; it does not authorize importing the whole catalog or redesigning the map. No production code, assets, registration data or saved gameplay inputs were changed. No artwork was generated, hashes checked, or engine/game suites rerun.

The active objective remains the [recovery plan](../RECOVERY_PLAN.md): native gameplay produces complete subjective lineages; recorded player bytes drive independent historical Pygame playback. Furniture is another consumer of those owners. The art preview and its animation clock are not a replacement game runtime.

## 1. Evidence and intake authority

Art root: `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/`.

Read the root `INTERIORS-CONSOLIDATED-HANDOFF.md`, the complete 160-row `handoff-interiors-2026-09-21/item-matrix.json`, `prefab-inventory.json`, `interior-furniture.json`, all eight concrete `room-dressing/prefab-review/*-layout.json` inventories, `decor-study/reviewed-manifest.json`, `object-destruction-bindings.json`, the six-chest repair handoff, selected per-bank metadata, and the preview binding/placement code. Source checksums already written in those documents are historical provenance; this study did not calculate or validate them and proposes no runtime checksum gate.

The current working checkout was inspected directly. Importing its cold direct-item table without constructing objects yields **179 builders, 16 authored door profiles and 12 doorway trap hardware profiles**. Current `game/data/environment_art.json` has **146 banks, 17 door entries including the generic alias, 12 trap entries and 40 wreck entries**. This corroborates the handoff's already-integrated door/trap boundary; its detached art-worktree engine is not used as current authority.

The approved destruction intake is the explicit `reviewed-manifest.json` allowlist together with the v3 `object-destruction-bindings.json` source-family mapping. That is **129 subjects / 135 banks**. `breakables/manifest.json`, raw experiment directories and an old document's 133/139 completion claim are not selection authorities. Some accepted bank metadata still says `review_candidate` or `pending independent review`; the later exact allowlist/review reference owns approval. Conversely, a file existing on disk does not restore a held bank.

Use a small explicit import selection containing source family, chosen approved metadata path/variant, destination resource identity and review reference. The importer moves original selected sheets and normalizes their passive metadata. It must not infer mechanical behaviors, select assets by directory glob, rewrite unrelated bindings, copy the preview server, or add startup verification. Review and ordinary schema/path loading are sufficient; no SHA system is proposed.

## 2. What the inventory actually contains

| Inventory | Count / exact distinction | Native meaning today |
| --- | --- | --- |
| Recovered non-foliage source groups | 106: six chest variants, FirePlace, Misc A/B/C/D/E groups | Most have no exact registered object. The crate/chest/campfire/barrel analogue columns identify capabilities, not aliases. |
| Foliage | 27: `fantasy.flora.a1..a7`, `fantasy.flora.b1..b6`, `fantasy.wallflora.a1..a14` | Source art only; no approved fracture or authored burn/scorch response. |
| Generated household sets | 21 under `authored.interior.*` | No exact household registration in the inspected direct table. |
| Generated indoor doors | Six designs | All six have current native profiles and animation; keep their production integration. |
| Item-matrix registration classifications | 6 exact native doors; 6 chest variants with generic mechanics; 27 foliage; 121 other unregistered exact rows | This is not a requirement for 121 classes or 121 bespoke actions. |
| Furniture selection registry | 49 choices | Preview composition data; includes options unused in the saved houses. |
| Concrete examples | Eight recipes / 14 floors / 73 used source families | Placement evidence, not a playable multi-floor import. |

The generated household families are exactly: `plain-dining-table`, `bed`, `wardrobe`, `bookshelf`, `writing-desk`, `preparation-counter`, `washstand`, `ingredient-shelves`, `bedside-stand`, `sack-bundles`, `candlesticks`, `tableware`, `papers-and-ink`, `work-stool`, `storage-shelving`, `wall-shelves`, `hanging-utensils`, `tool-rack`, `wall-candle-holder`, `wash-basin`, and `timber-stair-flight`. They share the `authored.interior.` prefix. The timber stair set exists but is not selected by these examples.

Recovered families can be grouped by the real capability under consideration:

| Exact source families | Artwork / potential gameplay meaning | Appropriate first treatment |
| --- | --- | --- |
| `fantasy.chest.a1/a2`, `a3/a4`, `b1/b2` | Three closed/open pairs | One existing container mechanism with three authored styles, not six independent containers. |
| `fantasy.misc.b1/b2/b3` | Crate and crate stacks | Plain breakable/blocker composition; do not assume a stack's physical footprint is one cell. |
| `fantasy.misc.a2/a3/a4/a7` | Jar, paired jars, pottery cluster, lidded vessel | Plain props unless an actual container use is authored. Six ceramic/stone subjects have alternate destruction partitions; those are not automatically hit directions. |
| `fantasy.misc.a8/a9` | Ordinary barrel / barrel cluster | Plain prop or explicitly authored storage. Do not alias either to the oil-spilling barrel. |
| `fantasy.misc.b13/b26/b28/b37/b38/b53` | Timber tabletop, bench, small table, covered tables, chair | Plain ground furniture; seating is a separate gameplay request. |
| `fantasy.misc.c5/c6/c7/c9/c10/c11` | Statues, pedestal, stone bench and monuments | Plain ground objects with authored material/extent; current art is sufficient without more statue generation. |
| `FirePlace` (source-family unresolved), `fantasy.misc.a1/a5/a6/c1` | Fire pit, spent ashes, clay oven/stove, stone fireplace | Do not give all of them campfire healing/cooking merely because that analogue exists. FirePlace needs an explicit local source mapping. |
| `fantasy.misc.b30..b36`, `fantasy.misc.d1..d5` | Seven trade signs and five banners | Wall-supported decoration; mounting/occlusion and support destruction are required before treating them as gameplay-attached props. |
| `fantasy.misc.b39/b40`, `fantasy.misc.e1..e11` | Rugs, hay bales and loose straw | Distinguish nonblocking floor dressing from physical hay piles. Matrix `floor` alone is not collision policy. |
| `fantasy.misc.b15/b16/b57/b60/b61`, `fantasy.misc.c2` | Dummy, grindstone, archery target, apparatus, alchemy bench, anvil | Art can be a prop now; training/crafting does not come with it. |
| `fantasy.misc.b7/b20/b23/b42`, `fantasy.misc.c8` | Troughs, tubs and wells | Prop appearance exists; water/container interactions require a chosen native contract. |
| `fantasy.misc.b51`, `fantasy.misc.c12/c13` | Wooden/metal cages | Prop appearance is not imprisonment, a new door, or restraint semantics. |
| `fantasy.misc.c3/c4/c14` | Wheeled cannon, cannonballs, monumental arch | Do not substitute these for current magic devices or portals just by name. |
| Other delivered Misc B sets | Market stalls/canopies, carts/wagons, crib, board, platforms, tents, scaffolds, ladder, log/timber and sign frame | Data reuse is possible after choosing their footprint and any actual use; these are not initial mechanisms to implement. B4 is absent from the delivered numbered sequence. |

Four banks are held: **`misc-b22`, `misc-b48`, `misc-b49`, `misc-b50`**. B22 and B48 have conflicting historical labels; no semantic guessing or repaired approval is appropriate. Boats/crane work remains stopped. The 27 foliage groups have no fracture; thermal art is also explicitly not authored.

The 12 decal cutouts (soot, dirt scuff, damp moss, plaster flecks, cracks, damp streaks, candle soot, tidemark, wine, wax, shoe scuffs, straw) are cosmetic source data, not an adjacency atlas or automatic damaging spatial conditions. Floor rotation and upright wall streaks are separate authored orientations. Existing blood/scorch gameplay packages remain separate.

## 3. Current production capabilities and genuine gaps

### Native composition and identity

`dnd/content/items/authored_item_builders.py::DIRECT_ITEM_BUILDERS` is the existing construction route. `StaticBlockerDefinition` and `_static_blocker_definition_builder` already compose a `WorldItem`, item identity, Health, targetability, channel flags and `WorldPlacementSpec`. Add ordinary furniture through cold data plus a shared constructor rather than subclassing table/chair/pot/vase individually.

The current static-blocker constructor always creates a targetable health-bearing object, and its definition does not carry a destruction remnant. Thus an ordinary breakable furniture row is near-content-only, but persistent authored wrecks need a small shared definition/constructor extension. Nonbreakable decorative rugs are not valid rows in that health-mandatory table unless its scope is deliberately changed; do not force them through it by inventing HP.

`BaseItem` already supports optional Health, damage/conditions, physical blocking, floor/inventory membership and `ItemDestructionRemnant`. `WorldItem` supplies explicit placement and boundary capabilities. `create_item_health` supports resistances/vulnerabilities and defaults poison/psychic immunity. Physical material authoring should use those existing mechanics where needed; this study does not invent per-furniture HP values or resistance rules. `Material` is not a palette label, and generic BaseItem does not currently have the same material field as DirectionalWall. A real material-response use should justify any shared material data extension; no enum per painted skin.

Avoid changing existing item meanings merely to match preview occupancy. For example `environment.blocker.crate` currently has20HP but `blocks_movement=False` and nonoccupying center bands. A preview crate marked blocking cannot silently redefine that existing species. Choose a separately authored blocking variant if the room needs it, or preserve the existing semantics and record the intended difference.

Proposed identity boundary:

- Keep current production door/trap and generic chest IDs valid.
- Give newly authored physical species ordinary stable IDs such as `environment.furniture.plain_dining_table`, `environment.furniture.wooden_chair`, `environment.decor.pottery_pair`, and `environment.storage_chest.small_wood`. These are proposed names, not existing registrations.
- Store art aliases such as `authored.interior.plain-dining-table` and `fantasy.misc.b53` in the presentation/intake mapping. Hyphenated source family names are not native item IDs.
- Mechanical species, runtime UUID, source art family, camera row and placed prefab-part ID are distinct identities. A prefab part maps to a newly constructed instance; its stable source family resolves an authored species, not a class name.
- Keep both original physical facing and the selected source-bank orientation. `furnishing.py` explicitly derives `pose` as the preceding slot of the `eswn` facing cycle. A source `pose='s'` can represent a physical `facing='w'`. Do not equate either to the camera, rotate backend placement on camera changes, or add a global guessed90-degree correction.

### Damage, destruction and retained aftermath

`BaseItem.destroy` already captures physical remnant state, invokes the concrete pre-cleanup hook, removes light and active conditions, removes the original floor object, places a declared remnant at the prior support/orientation and publishes the destroyed/replacement relationship. The replacement is real native state. `ItemRemnantState` currently records open state/swing/mechanism state; an ordinary prop legitimately has none of those.

The presentation route is not yet generic furniture destruction:

- `game/environment_art.py::EnvironmentArt` has banks/doors/traps/wrecks, but no plain prop entry.
- `select_environment_destruction` selects trap state or door state/swing/outcome only.
- `environment_animation.remnant_bank` returnsNone when remnant state isNone. That excludes a perfectly valid stateless broken stool.
- `game/choreography.py` admits environment destruction only for door/trap identities (device destruction has its existing separate source).
- `game/app.py` handles environment doors, traps and remnants; static `world_bindings.json.props` handles ordinary bodies and binary states.

The needed shared addition is a small authored plain-prop/destruction binding and corresponding selector admission. Reuse `EnvironmentBank`, `DestructionContact`, `WorldTransition`, existing raster treatment, observed object state and final-frame seek. A plain prop can select one bank without invented door/mechanism fields. A chest selects one of two banks using its actual retained open state. Do not encode furniture as a fake trap or call every object a door to pass those branches.

Mechanical removal/loot/replacement remain at the real damage contact. The finite collapse is presentation, and the final frame is a stable native remnant until actually cleared. `ItemRemnantState.door_open` currently receives `StorageChest.get_spatial_open_state` through the common getter; preserve existing semantics rather than inventing a second lid boolean solely for this import. If naming is later generalized, compatibility belongs to that separate data decision.

Authored multiple collapse banks should use an explicit deterministic selected variant; `impact-a/b` alone does not prove directional semantics. A hit-direction mechanic or new random fracture choice is unnecessary for the first set. If native mechanical remnant outcomes differ, that outcome must be native and replayed, as existing clear/jammed doors already do.

Current `world_transition_end` joins finite destruction to its historical head. Chest banks run roughly5.7–6.1seconds. That is a real visible consequence of exact intake, not a reason to quietly speed or trim approved art. The first review must show the full collapse at its authored speed. A later request for independently continuing aftermath would need a bounded shared timing decision; this study does not introduce it.

### Containers

`StorageChest` has independent `is_open`, existing Open/Close actions, a real Inventory, conditional LootAll availability and a destruction spill hook. `build_storage_chest` uses the generic ID and does not set health/targetability; the direct registry's generic builder also leaves optional LootAll off. The selected gameplay factory must deliberately enable contents/looting and health for a breakable chest. New styles need common builder data, not new action implementations.

One concrete code concern belongs in chest acceptance: `_on_destroy` currently discards `parent_event` and calls `item.place_on_grid(pos)` without it. This study has not executed a destruction history and does not claim a reproduced projection failure. Before enabling styled breakable chests, record a real contained-item spill and prove those visible item moves belong to the destruction lineage; if they do not, thread the existing causal parent through this existing hook. Do not create a second loot/serialization system.

Inventory ownership is private storage; tabletop support is not inventory. Chest destruction must not disclose unseen private contents before native spilling makes them observed.

### Lights and useful actions

Fixed light machinery exists in WallTorch/StandingTorch, including is_lit, brightness radii, ignition/extinguishing and anchored-light cleanup. `build_wall_torch` is direct-registered; `build_standing_torch` exists as a helper and its media is bound, but `environment.standing_torch` is absent from the inspected direct builder table. Factory existence and direct registration are separate facts.

A new fixture may reuse the appropriate existing light composer, authored radii and native use actions. A candle or wall lamp still needs exact identity, support and actual lit state. The floor label in the asset table does not turn mounted candlesticks into a standing torch, nor does candle artwork itself provide illumination. Destruction must remove the light through existing ownership. Fuel is an explicit content choice, not assumed from the art.

Campfire Rest/Cook, ArcaneDevice use, containers, levers and pressure plates already exist. Beds, workbenches, cages, shops and ordinary barrels must not inherit those behaviors merely because they are plausible analogues. Resting, crafting, merchants, seating, imprisonment and water management are separate gameplay scope, not prerequisites for furniture as a physical object.

## 4. Six chests: state-pair contract and exact current banks

All six have four ESWN rows,384×384 cells, pivot `[192,271.36]` and12FPS in the inspected metadata. Read the individual metadata even though the135 current approved banks happen to share384×384 cells; cell size is padding, not a guaranteed world footprint or future schema constant.

| Pair / state | Exact root under `decor-study/` | Frames / duration |
| --- | --- | --- |
| A1 closed | `candidates-volumetric-timber-v3-contact/chest-a1/impact-a` | 70 /5.833s |
| A2 open | `candidates-volumetric-timber-v9-contact/chest-a2/impact-a` | 71 /5.917s |
| A3 closed | `candidates-volumetric-timber-v3-contact/chest-a3/impact-a` | 70 /5.833s |
| A4 open | `candidates-volumetric-timber-v9-contact/chest-a4/impact-a` | 69 /5.750s |
| B1 closed | `candidates-volumetric-timber-v3-contact/chest-b1/impact-a` | 73 /6.083s |
| B2 open | `candidates-volumetric-timber-v12-contact/chest-b2/impact-a` | 68 /5.667s |

Current generic chest media uses the original A1/A2 images. Revised collapse banks reconstruct the entry geometry and provide `intact.png` and `wreck.png`; their entry images are not identical to the old originals. Use the matched reconstructed intact closed/open pair with the chosen destruction banks, after a four-view continuity review. Do not paste an original image into frame zero or select a new collapsed chest while retaining the old unmatched lid states. There is no newly authored smooth chest opening animation: native open/close can remain the existing binary state switch. Destruction frames are not a lid-opening animation.

The first styled chest should be A3/A4 because A3 is used15 times in the saved prefabs; the existing generic A1/A2 presentation can remain unchanged until explicitly selected for this reconciliation. B1/B2 and a separately styled A1/A2 pair are additional data after that mechanism is proven. Do not require all three styles before testing the existing chest behavior.

## 5. Prefabs: concrete placements, not screenshots or native topology

| Index | Recipe | Style / dimensions | Floors | Parts | Exported reachable supports |
| --- | --- | --- | --- | --- | --- |
|0|Compact artisan home|G /6×7|2|216|66/66|
|1|Long merchant house|C /8×12|1|302|75/75|
|2|Staggered townhouse|D /10×8|3|568|185/185|
|3|Great hall residence|F /12×10|2|566|197/197|
|4|Terraced apothecary|D /10×10|3|577|233/233|
|5|Courtyard residence|D /12×12|1|427|95/95|
|6|L-shaped lodge|C /10×10|1|211|53/53|
|7|Garden wings|G /12×10|1|304|77/77|

These are the generator's support-graph counts, not proof of native pathfinding or actor-wall collision. Every layout has concrete `parts`, source families, source poses, XY/base heights, assembly level, role and component; `interior.plans` retains room purpose, furniture footprints, approach cells, hallway/circulation, supports and connections. All37 tabletop attachment references found across these saved layouts name an existing parent part. There are99 wall-fitting records. The reader must retain those relationships, not flatten them into anonymous static blits.

Useful concrete example from layout1:

- Plain dining table at `(1,5)`, physical facingW/source poseS, footprint`[(1,5)]`, approach`(0,5)`.
- Chairs at`(1,4)` and`(1,6)` face the table with their own approaches; a rug also sits at`(1,5)` with an empty blocking footprint.
- A3 chest at`(2,7)`, facingN/source poseW, approach`(2,6)`.
- Tableware shares the table XY/base floor but records `parent_id`, `socket='top-center'`, `sort_parent_id` and `visual_height_steps≈0.5227082`.
- Wall candle holder at`(3,2)` records north supporting wall, visual offset`(0,-0.42)`, visual lift≈0.6495191steps, and mount lift1.05Blender units.
- The two-cell central hall and five explicit room-door edges remain circulation constraints, not extra furniture placement opportunities.

The source already avoids two unplaceable workshop stools rather than blocking access. Preserve that omission and its reason. Room `missing_art` lists are historical briefs: layout1 still calls tableware/table/candlesticks missing even though they are delivered and placed. They must not become automatic art-generation requests.

### Preview binding debt and label hazards

The255 furniture animation references still use `generated-interiors/impact-damage-manifest.json`. The56 indoor-door and11 recovered exterior-door references are existing preview authorities, not a reason to replace installed production doors. Recovered static furniture has no generic preview destruction resolver. Resolve source family through the current allowlist; discard embedded preview animation paths as runtime authority while preserving the concrete placement.

Matrix placement labels are summaries, not complete capability facts. For example generated candlesticks are marked `floor` there but `interior-furniture.json` marks them attachment-only and the concrete house places them on a bedside socket. Tool rack is marked `floor` in the matrix but is selected as a wall fitting. Conversely tableware/papers are explicitly support surfaces. Prefer the actual selected placement/support record and verify that the chosen bank was authored for it.

`animated_assets.py` also deliberately refuses mounted fixture break playback, mutates preview cache resources, adds indoor-door pixel pivots and controls animation from HTTP parameters. None of that should be copied into gameplay. Door geometry and pivots already have production owners.

### Architecture boundary

The six visual styles are A/C/D/E/F/G. A castle masonry is certified only for one storey; Desert/palisade are excluded. D/F upper-course12/10/16 is not foundation1/2/7; interior partitions use G1/D8/F8 with headersG10/D5/F5. Current production walls choose presentation largely by Material and generic directional shape. Doors being integrated does not establish all225 recovered wall configurations, their apertures, or compatible adjacency. Introduce explicit appearance/geometry mapping for the selected wall subset; do not silently replace open timber/window walls with opaque solid walls.

The map's `_tiles` is `Dict[tuple[int,int],Tile]`; `WorldObjectPlacement` resolves one tile/XY with integer vertical bands. There is no multi-cell furniture footprint in that value and no second walkable Tile at the sameXY. Existing terrain stairs/connectors are useful but do not solve stacked occupancy, paths, FOV or picking. Two-cell beds/benches and upstairs floors therefore are not content-only in current storage. Do not block only their anchor and call the footprint imported, put decorative table lift into terrain elevation, or overwrite downstairs with upstairs.

All exported stair flights currently select `fantasy.wall.a13`, even in timber houses. The generated timber flight is not automatically used. Preserve lower landing, run, intermediate height, upper landing and opening; do not duplicate the descending flight at upper-floor height. Multilevel support and destructible stair connectivity are later backend design work. For initial integration, use a deliberate single-floor subset and report omitted unsupported pieces.

## 6. Supported-object contract

Native `owner_uuid/stored_in_uuid` represent equipment/inventory relationships; native floor `WorldObjectPlacement` has no `parent_id`, socket or supported-child relation. The preview's attachment strings cannot be fulfilled by silently putting a tableware item into a private inventory or merely drawing it higher.

For a later explicitly selected attachment unit, the minimum required relationship is an observed native support identity plus a named authored attachment/socket, physical support location/orientation and a finite release policy. The presentation binding owns exact pixels and source registration; native state owns whether the child remains supported, becomes a grounded object or is destroyed. The source `visual_height_steps`, Blender lift and XY offset need a measured art adapter; they are not interchangeable units or native walkable support.

On support destruction, process the chosen detach/drop/destroy policy causally through existing item/location/damage machinery. The child must be observed in its new floor state and inherit the real parent action lineage, with its inventory/privacy meaning unchanged. A light attached to the child must follow that physical owner or end through native cleanup. Do not make the renderer delete a decoration because its parent sprite disappeared.

Current authored collapse is baked at specific support/ground heights. Raising the whole sheet onto a table or wall raises its final debris too. An intact mount and a floor-debris registration are distinct; use the delivered mount-compatible bank only when it actually describes that release. Do not add a generic ballistic/debris simulation to disguise a missing authored height. For the first furniture unit, omit loose supported children and wall fixtures instead of claiming fake support semantics. Existing approved hanging signs/banners can wait for this shared relationship rather than each receiving bespoke code.

## 7. Bounded first integration proposal

Start with **one floor-level room interaction set**, inside the existing validated ground/wall/camera framework. This proves physical content, destruction and container state without making multistorey support or wall attachments prerequisite work.

| Selection | Proposed native treatment | Approved art selection |
| --- | --- | --- |
| Existing crate reference | Preserve `environment.blocker.crate` semantics; alternatively add an explicitly different blocking species if required | `fantasy.misc.b1`; `candidates-wood-v6-contact/misc-b1/impact-a` (26frames@12FPS) |
| Plain dining table | One cold ground-furniture row; no crafting/seating or contents yet | `authored.interior.plain-dining-table`; `native-breakables/plain-dining-table` (22frames@12FPS) |
| Wooden chair | Same ordinary world-item composition | `fantasy.misc.b53`; `candidates-wood-v7-contact-only/misc-b53/impact-a` (26frames@12FPS) |
| Paired pottery | Same composition with explicitly chosen physical response; no automatic container | `fantasy.misc.a3`; `candidates-v5-family-review-r2/misc-a3/impact-a` |
| Small wooden chest | Existing StorageChest open/close/loot/spill with authored health, remnant and A3/A4 identity | The two approved chest banks in section4 |
| Existing indoor door + wall torch | Regression surroundings with current native/media IDs | Keep installed production door/light resources |

This is five object families and six destruction banks, not a full129-subject intake. Pick exact mechanical HP/blocking/remnant-clear policy in the implementation plan using existing content conventions; this study does not promote art labels into rules. A shared plain-prop selector, cold remnant field and styled-chest factory inputs should be enough for this set. Multi-cell furniture, lit new candle supports, rugs/decals, mounted signs, all theme services and multistorey houses remain named follow-ups.

Use positions/approaches inspired by layout1's dining room plus a small storage corner, but label it an intentionally authored integration fixture, not an exact native import of that complete merchant house. The smallest complete single-floor house candidate is layout6 (53supports); it still contains a two-cell bed and wall fittings, so full fidelity requires those explicit shared capabilities. A later prefab adapter should consume the concrete records and a closed source-family→native-content mapping; unsupported pieces are explicit, not substituted or silently discarded.

### Required review before implementation

- **Anti-slop reviewer:** verify that the proposed five families exercise requested gameplay, selected approval authority/pairs are exact, observed destruction joins have the intended timing, and missing mounts/footprints do not grow into a speculative world-physics project. Challenge any per-sprite behavior or redundant new queue/serializer/import validation.
- **Anti-OOP reviewer:** verify cold data plus current item/system composition, one shared prop/remnant selector, correct import direction, real item/location/Health/condition owners, and passive subjective replay. Support references must not overload private inventory or hide executable renderer logic in native data.
- Reconcile their concrete findings in the implementation plan. Source artwork review is not a substitute for these gameplay/design reviews; this study does not claim they have already approved the proposed integration.

### Observable acceptance at that boundary

Read HOW_TO_TEST before writing tests. Capture real native actions once and replay saved public player inputs thereafter.

1. An actor attempts movement around intact selected furniture: authored blocking/access matches the chosen profile, not its PNG silhouette. Door operation and current light state still work.
2. Nonlethal and lethal attacks against table/chair/pottery show actual object HP, hit response, destruction at contact, stable final wreck and explicit passability. Compare the native after-state with serialized replay; no live registry access is allowed during replay.
3. A chest can open, close and expose LootAll only when open/nonempty. Destroy both open and closed states with real contents. Contents become observed only when native spilling discloses them; replacement/body state is correct from both observers.
4. A late observer sees the persistent wreck without replaying the collapse; a hidden destruction does not generate knowledge. Existing door/trap regression scenes retain their approved resources and state transitions.
5. Four-camera playback includes intact entry, contact, intermediate collapse and final frame against actual floor/door/actor geometry. Validate facing and source-pose mapping, stable support-height/pivots, body occlusion and deterministic seek. Preserve full authored collapse duration for the first review.
6. Run the selected native item/destruction and presentation/replay modules, then affected typing. Do not add a new visual-diff framework, whole-catalog startup sweep, source audit, or generic asset validation framework.

The next unit after this bounded set is a decision among a complete single-floor layout adapter, supported tabletop/wall objects with lights, and multi-cell furniture. Multiple walkable supports at oneXY is a separate architecture decision, not an incidental importer option.
