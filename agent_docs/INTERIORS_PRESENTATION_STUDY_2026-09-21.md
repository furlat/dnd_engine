# Interiors presentation study — 2026-09-21

Status: read-only study of the supplied handoff and active game. This is the anti-slop review input for the implementation plan, not authorization to implement every recovered asset. No production changes, asset generation, source hashes or runtime audits were performed.

Read with [RECOVERY_PLAN.md](../RECOVERY_PLAN.md). Native mechanics, observation rules, complete event lineages and recorded playback remain the authority. The companion backend study and the final plan's anti-OOP review must resolve native representation decisions.

## Conclusion

The handoff contains usable authored layouts, placement data and reviewed art. It does **not** contain a production-ready house runtime. The smallest useful integration is one actual single-storey house, rendered by the existing game and traversed through native actions, with a small explicit furniture catalog. Keep the layout's walls, doors and furniture meaningful to movement and perception; do not import only an attractive background.

Reuse existing object state, door animation, damage/destruction, observed world updates, support projection and replay. Extend their data registration where the new content demonstrates a missing field or selector. Do not copy the preview's painter, automatic door substitution, global break mode, pathfinder or server.

Stacked floors are a separate native representation dependency. Rendering upper floor pictures is not the missing work: both native and retained worlds currently index supports by XY, and controls select targets by XY. A single-storey first slice must be described as such, without flattening a multistorey export and claiming it is integrated.

## Material inspected

The external source root in the following references is:

`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/`

Inspected the consolidated handoff; `handoff-interiors-2026-09-21/{item-matrix,prefab-inventory}.json`; the eight `room-dressing/prefab-review/*-layout.json` exports; `wall-connections.json`, `surface-profiles.json`, `interior-furniture.json`, `room-prefabs.json`; reviewed destruction bindings; and `parametric.py`, `interiors.py`, `furnishing.py`, `animated_assets.py`.

Visually inspected the existing `6-floor-0-camera-0.png` and `0-floor-1-camera-0.png` previews. They demonstrate useful art composition and an upper staircase opening. They do not demonstrate native visibility, actor interleaving, occupied furniture footprints or real door states. Some interior walls obscure furnishings even in the preview's exterior cutaway; cutaway cannot be assumed solved by those images.

Active production inspected: `game/app.py`, `assets.py`, `environment_draw.py`, `projection.py`, `controls.py`, `player_facts.py`, `player_reduction.py`; native world placement, world snapshots/authoring and GridMap storage. Existing graphics cleanup and control-spell work are preserved dependencies, not replaced implementations.

## Reuse boundary

| Source material | Reusable part | What must not be inferred or copied |
| --- | --- | --- |
| Exported `parts` | Explicit family, local ID, pose, position, base height, component and support references | A picture's role does not establish native solidity, interactability or destructibility. |
| Interior plans | Room membership, door thresholds, furniture footprint/approach cells, parent sockets, stair openings | Room labels do not implement resting, crafting, shops or inventories. Preview connectivity assumes doors can open. |
| Reviewed object destruction bindings | Exact reviewed bank, material/mount description and source-art identity | Art identity is not native item registration; a wreck picture does not decide collision, loot or support release. |
| Existing door/trap production banks | Four-view opening, breakdown and persistent aftermath already integrated | Do not rebuild the working door/trap runtime to accommodate furniture. |
| Wall/surface profiles | Family-specific straight/corner/window/frame choices; flat floor registration | Do not use material alone to substitute an unrelated wall; do not use raised tile edges as flat interior flooring. |
| Parent/socket records | Authoritative intended attachment and measured local registration | A tabletop offset is not a new walkable floor, and a mounted sprite is not a floating ordinary floor item. |
| Decal cutouts | Authored floor versus upright placement and alpha | They are not an adjacency atlas, fire simulation or native hazard condition. |
| Preview rendering | Reference images and registration measurements | No global open-door mode, whole-house depth groups, eager image cropping/cache generation or hidden child deletion in production. |

The recovered asset inventory is intentionally broader than the first slice. The reviewed destruction allowlist supersedes earlier generated impact banks; four held banks (`misc-b22`, `misc-b48`, `misc-b49`, `misc-b50`) are not approved. Boats/crane and the unrelated source catalogs need not enter this integration. Keep the selected manifest small and explicit; production should load used rasters through its existing caches.

## Concrete presentation gaps and smallest justified changes

### 1. Wall identity must survive registration and selection

`game/app.py:947–989` selects stone/wood wall art and groups corners by `(position, material)`. That preserves existing generic boundaries but cannot distinguish recovered C log walls, D/F ground and upper panels, G interior partitions, windows and open E braced frames. Merging two different profiles merely because both are wood would produce an incorrect corner.

Native item facts already carry `visual_item_name` and `visual_variant_id` (`game/player_facts.py:426–447`); those fields should be considered before introducing another skin identity. The current world renderer selects by material or `item_id`, so existing transport is not the same as implemented selection. Use a finite authored visual-profile registration and include the selected compatible profile in wall grouping. Keep physical material, blocking channels and door state independent of the art key.

A source window/frame requires an explicit mechanical profile. An open timber frame is not a closed wall merely because it belongs to a wall catalog. A window may block movement while passing vision, light or projectiles according to the authored game rules. The current `BoundaryStructure` has channel blockers but no detailed opening height/shape; the backend review must distinguish a sufficient whole-edge policy from a genuinely required aperture model. Do not build a general aperture solver without a selected gameplay case requiring it, or pretend an image provides collision geometry.

### 2. Coordinate conversion is an import responsibility

The authoring preview uses `e=(+1,0), s=(0,+1)`. Native north is `(0,+1)` (`dnd/core/gridmap.py:752`). `game/projection.py:325` intentionally maps native north to the source `s` camera row at camera zero. Copying source pose strings into native compass fields would rotate some parts incorrectly.

Use one documented conversion for source cells, physical boundary directions, furniture facing and source bank rows. Furniture exports distinguish facing from artwork pose, so do not force those to be identical either. Keep source pivots, scale and exact door pose offsets in authored registration; do not accumulate per-house fixes in the draw loop.

Acceptance is geometric: a door occupies its actual threshold from all four cameras; furniture footprint rotates with native orientation; wall-mounted objects remain on the same physical edge; floor and tabletop registration remain stable when the camera changes.

### 3. Furniture cannot be only a sprite at an origin

`interiors.py:90–96` and `furnishing.py` author blocking footprints and approach cells; beds can occupy two cells. The exported support graph removes occupied furniture cells. `WorldObjectPlacement` currently transports one tile/position and vertical extent, without an explicit footprint or parent socket. Do not silently discard a bed's second occupied cell or substitute the preview graph for native pathfinding.

For the first slice, either use existing native occupancy that genuinely expresses the selected footprint, or add only the required finite footprint data through the current placement path after the backend review. Do not create fake independent furniture items per occupied cell. A chair in front of a desk is not automatically a implemented sitting interaction; the preview's `approach_via_seat` is layout intent.

Selection has a related real limit: `game/controls.py:111–117` picks a support then chooses the first valid action target with that position. A table and independently targetable tabletop item can share XY. The existing Tab/target list can disambiguate, but mouse picking is not already object-specific. Do not start a pixel-perfect picking framework merely to place decoration; explicitly test the current target list for the selected interaction, and address object-specific picking only when that interaction needs it.

### 4. Parent support is useful data; break consequences are native rules

`interiors.py:102–106` supplies `parent_id`, `top-center`, separate visual height and parent sort identity for tableware, papers and candlesticks. Wall fixtures carry a support edge, mounting offset and height (`interiors.py:127–151`). These are good authoring inputs.

The preview currently hides a child when the parent's global furniture-break preview begins (`parametric.py:240–242`). This is **not** a drop event, a destroyed child or a supported production policy. Its attachment metadata itself proposes different consequences, including detach/drop.

Resolve local parent references to native object identities once during world construction. Retain whichever support relation and offset the selected actual gameplay needs through cold world state and subsequent events. Rendering follows that retained relation; it must not query a live parent or guess that a child disappeared because a break animation started. This does not require a general-purpose scene graph.

The initial implementation should choose an explicit bounded policy for one example: noninteractive combined decoration, or an actual child that detaches/remains/destroys when its support breaks. Do not promise all independently lootable tabletop objects before the state transition exists. A decorative grouping is legitimate if declared as decoration and not silently treated as independent inventory.

### 5. Existing object damage and aftermath should be extended

There is already a suitable event boundary: `ObjectDamageFact`, `ObjectDestroyedFact`, observed replacement UUID/placement and `ItemRemnantState` (`game/player_facts.py:354–378`). `game/app.py:745–835` already draws finite door/trap breakdown and retained wreck state. Ordinary props also have state/lit/transition bindings (`game/assets.py:34–40`, `game/app.py:1076–1189`).

Prefer finite furniture registrations into these existing paths. Share ordinary object damage/destruction behavior; do not generate one handler or draw branch per recovered cabinet/chair/bed. The remaining backend choices are actual HP, damage susceptibility, contents, support release and wreck occupancy—not media playback cues.

Bank mounting matters. A floor collapse cannot be translated upward and used as a wall-hung collapse: its final debris would float. Use the corresponding authored mounted/fall bank or deliberately leave that object's destruction unimplemented until the required art exists. This is an asset-specific limitation, not a reason for a general rigid-body solver.

Chest pairs deserve one direct registration check: current native StorageChest uses A1/A2, while reviewed A3/A4 and B1/B2 are additional styles. Open/closed choices are states/styles of the same storage behavior, not six new behaviors. The newly reconstructed destruction-bank intact image can differ from the old static raster; preserve/reconcile the pair so destruction frame zero does not visibly change the chest. There is no authored smooth chest-opening bank in this handoff; do not manufacture one by playing a break sequence.

### 6. Floors, roof removal and cutaway are different concerns

Flat interior profiles intentionally select D1 stone or F1 wood. `game/app.py:392–408,530–536` currently binds floors by material. A different flooring appearance may use a registered tile appearance identity if needed; do not mutate material/conditions merely to choose a floor image. Rugs and decorative stains should remain declared decoration unless gameplay requires their own physical state.

The preview's interior mode removes the roof/other levels, hides camera-near exterior walls and supported fixtures, and renders all doors open (`parametric.py:244–256`). Only the first three operations are candidate viewing policies. The fourth falsifies game state.

Any production cutaway must operate on already received world content. It must neither reveal an unobserved room's contents nor change LOS, pathfinding, lighting or door state. Hiding a wall visually does not make its actors visible. Preserve real actor/wall ordering in the existing common compositor; do not use the preview's whole-house/floor-first sort (`parametric.py:261`). Keep cutaway separate from destruction so a hidden roof is not a destroyed object.

For an initial one-storey game scene, a declared roofless review view or explicit user-controlled roof/cutaway mode is sufficient. An automatic observer-sensitive cutaway policy is a product decision; it is not required just to import a valid floor plan. Interior walls may still obscure content, so the four-camera review must include walking next to partitions, not only an empty house screenshot.

### 7. Multistorey is a real dependency, not a local renderer fix

The exports have fourteen floors across eight examples, with real overlapping XY supports, staircase holes, landings and terraces. `interiors.py:161–170` produces an XYZ graph, explicitly labeled preview navigation that assumes doors may be opened. It is useful desired geometry, not a second runtime graph to install beside GridMap.

Active constraints:

- `dnd/core/gridmap.py:131` indexes `_tiles` by XY.
- `game/player_facts.py:506` and `game/player_reduction.py:34–35` retain/update tiles by XY.
- `game/app.py:1406` picks from those retained tiles and later looks up by XY.
- `game/controls.py:111–117,143` resolves target selection/previews by XY.
- `game/projection.py:290–322` can intersect support planes at multiple elevations, but its current tie-breaking and its callers do not establish independent floors at the same XY.

Connectors already retain support tile UUIDs and endpoint heights (`dnd/core/events.py:834`), which is useful existing foundation. They do not by themselves repair actor support identity, movement, occupancy, sensing, light, targeting, recorded world keys and picking. These dependencies must be designed together before enabling a second overlapping floor. Do not change `_tiles` alone, and do not represent two physical floors as unrelated draw-only layers.

## Recommended staged integration

1. **Freeze a small explicit content selection.** Use a genuine single-floor export. Layout 6, the L-shaped lodge, is a useful candidate: one floor, twelve furniture placements, two tabletop decorations and seven wall fittings. Layout 1 is a simpler rectangular topology but has twenty-two furnishings. Keep unsupported part identities listed explicitly; do not silently drop them. Decide the selected window and attachment semantics with the backend review.
2. **Import the shell and actual door states.** Translate the selected exported data once into the existing native world-authoring path. Register the required wall/floor appearances and reuse the already integrated door profiles. Test source orientation, all boundaries and observation through a real opening. Keep the existing world renderer and replay packets.
3. **Make the selected furnishings physical.** Add the small finite content definitions, footprints, interaction choices and approved art. Include one chest, one obstructing table/bed and one actual light. A correct bounded inventory is better than declaring every recovered sprite interactive.
4. **Exercise damage and support consequences.** Add reviewed breakdown/wreck registrations through the existing object lifecycle. Include one tabletop or mounted example only with an explicit native consequence and correct debris mounting. Any additional content follows the same authoring route.
5. **Review playable room presentation.** Use real recorded actions from two observers and all four cameras. Add only the cutaway behavior needed to make this selected room readable without changing disclosure. Retain approved existing door/trap and projectile scenes as focused regression references.
6. **Return to multistorey deliberately.** If required next, write a separate native support/addressing plan with both anti-slop and anti-OOP reviews. Use the provided stairs/holes/terraces as acceptance geometry, not as justification for a parallel scene-graph engine.

Steps 1–5 are a coherent first playable unit. They are not a claim that all household art or all eight prefabs are done. The implementation plan should name precisely which native interactions are included rather than importing a directory and deriving behavior from filenames.

## Narrative tests and review clips

These should reuse the existing native-history capture and four-camera gallery. Do not introduce a new renderer, pixel-regression framework or exhaustive full-catalog startup check.

| Narrative | Native/replay assertions | Visual check |
| --- | --- | --- |
| Approach a closed outer door, open it, enter, close it | Real available action and door state; observer acquires/loses contents according to existing senses; same serialized sequence replays cold | Correct edge, hinge row, contact timing and actor occlusion from four cameras; cutaway never substitutes open art |
| Walk from corridor through an interior doorway past furniture | Real path respects walls and full chosen furniture footprint; interacting actor reaches the actual approach location | No sprite crossing walls or furniture because of whole-house sorting; no reversed furniture facing |
| Two actors on opposite sides of a selected window/open frame | Authored movement/optical/propagation policy is exercised; undisclosed content remains absent | The apparent opening agrees with mechanics; camera rotation only changes view |
| Open/loot/close a chest, then damage and destroy it | Real contents policy, HP, removal/replacement, persistent wreck and cold admission | Approved closed/open pair and destruction frame zero align; final wreck does not revert after playback |
| Damage a table with an attached decoration | Only if included: explicit real child outcome and correct placement after support loss | Child does not silently disappear at the first animation frame; floor debris rests on the floor |
| Extinguish/reignite an actual wall or table light | Native light change alters senses; no light mechanically created just because art glows | Flame and action timing follow recorded state; wall mount remains registered across cameras |
| Toggle the chosen cutaway view, rotate, replay history | Native state and available actions unchanged; no newly disclosed object introduced by view mode | Actor ordering remains physical; associated cutaway fixtures follow their support without deletion events |

A bed-footprint test is necessary if a two-cell bed is selected; it is not necessary to test every furniture pixel against movement. A mounted-break test is necessary if mounted destruction is included; otherwise record that limitation rather than adding placeholder behavior. Capture each narrative once from native events and reuse the saved inputs for media iterations.

## Decisions to resolve in the implementation plan

- **Initial scope:** which single-floor house and which actual interactions, or whether the user instead wants the larger multilevel native change first.
- **Apertures:** physical policies for the selected windows/open frames. Existing rule/channel choices should be used where sufficient; only request a new height aperture contract when selected gameplay needs it.
- **Attached decoration:** cosmetic grouping versus independently observed/interactable child, and what happens when its support breaks.
- **Aftermath:** selected furniture wreck occupancy and chest contents policy. These are backend content rules, not conclusions from artwork.
- **View behavior:** initially roofless/manual cutaway versus automatic cutaway tied to the observer. Rendering must preserve subjectivity in either case.

These are concrete authoring/product choices. They do not justify stopping to ask about low-level implementation details that the existing contracts settle. The root implementation plan should make bounded recommendations and obtain human input only for unresolved gameplay choices that affect the selected unit.

## Anti-slop review verdict

Proceed with a bounded, authored single-floor integration once the selected native policies are agreed. The shared game paths are sufficiently useful that a new scene graph, hierarchy of room/furniture classes, preview server, parallel path graph, startup audit or generalized physics system would be unjustified here.

The important missing work is explicit content/state registration and the few actual physical relations demonstrated by the selected house. Existing item/variant identity, native object lifecycle and world snapshots should be reused before adding fields. A future second floor requires a coherent native addressing change, not more clever painter ordering. Preserve that distinction in the final plan and its independent reviews.
