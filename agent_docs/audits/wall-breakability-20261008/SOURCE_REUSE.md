# Ordinary wall destruction: existing source reuse

8 October 2026. Source review only; no gameplay, renderer or artwork changes are
certified by this receipt. Read with
[the wall registration audit](../WALL_FLOOR_ASSET_ALIGNMENT_AUDIT_2026-10-06.md).

The preserved explosions are usable as finite cosmetic destruction debris.
Existing Unity TileData assigns the same unrotated effect to all four directions
of each listed wall, including D2/C2 corners. This is evidence for generic debris
reuse, not a matching replacement silhouette or calibrated 3D fracture geometry.

## Source locations and identity checks

- Unity source root (`U` below):
  `/mnt/c/Users/tommaso/Documents/UnityProjects/SmallscaleExplore/Assets/SmallScaleInt/Fantasy kingdom Tileset/`.
- Preserved original effects (`P` below):
  `/home/tommaso/Dev/terrain-prefab-study-2026-09-24/recovered-architecture/source-animations/fantasy/Destructible tiles/`.
  Original PNG identifiers and SHA-256 hashes are recorded in the adjacent
  `recovered-architecture/source-animation-inventory.json`.
- Original vendor archive:
  `/mnt/c/Users/tommaso/Downloads/Fantasy tileset - 2D Isometric V1.1.zip`.
- Existing solid sibling originals:
  `/mnt/c/Users/tommaso/Documents/assets/window-reconstruction/destruction-showcase/existing-solid-siblings/`.

All 64 Unity effect PNGs exactly match the preserved original files and their
inventory hashes. All 28 admitted solid sibling sprites match the corresponding
Unity `U/Environment/Sprites/Wall <code>_<pose>.png` RGBA pixels. The 16 installed
legacy D1/D2/C1/C2 sprites also match their corresponding Unity source pixels.
These checks identify the media; they do not certify native composition.

## Exact TileData selections

For each row, all four files
`U/Example scene/Scripts/Tiles/TileData/DT_Wall <code>_<pose>.asset`, with
`<pose> = E,N,S,W`, resolve `sourceTile` to the corresponding
`U/Environment/Tiles/Wall <code>_<pose>.asset` and select the listed
`destroyVfxPrefab`. Prefabs are under
`U/Example scene/Prefabs/Destructible tiles/`.

| Current media identity | Source code | Source prefab | Original effect folder |
| --- | --- | --- | --- |
| `environment.wall.fantasy_a1` | A1 | `Destructible Wall prop stone.prefab` | `Wall Stone explosion` |
| `environment.wall.fantasy_c1`; legacy `wood.wall.straight.*` | C1 | `Destructible Wall B C Large.prefab` | `Wall Wood explotion Large` |
| Legacy `wood.wall.corner.*` | C2 | `Destructible Wall B C Large.prefab` | `Wall Wood explotion Large` |
| `environment.wall.fantasy_d1`; legacy `stone.wall.straight.*` | D1 | `Destructible Wall D prop stone.prefab` | `Wall wood+stone explosion` |
| Legacy `stone.wall.corner.*` | D2 | `Destructible Wall D prop stone.prefab` | `Wall wood+stone explosion` |
| `environment.wall.fantasy_d8` | D8 | `Destructible Wall D prop stone.prefab` | `Wall wood+stone explosion` |
| `environment.wall.fantasy_f1` | F1 | `Destructible Wall B C Small.prefab` | `Wall Wood explosion Small` |
| `environment.wall.fantasy_f8` | F8 | `Destructible Wall B C Small.prefab` | `Wall Wood explosion Small` |
| `environment.wall.fantasy_g1` | G1 | `Destructible Wall B C Small.prefab` | `Wall Wood explosion Small` |

The F1/F8 Wood Small selections above are literal existing Unity selections.
Their masonry appearance is not evidence for changing those pointers or native
materials. This receipt records media reuse, not physical material rules or a
claim that every source selection is visually ideal.

Prefab GUIDs: Stone `d54af7d484ee9bb4eaed37e877bf1d04`; Wood Large
`798e2d6c13e5ddf4c8fcd9cc2fa28820`; wood+stone
`ed3f2d8cdf51ffb4cae770d092e804d0`; Wood Small
`1a0d399a773999d43982809b74223283`.

## Registration and authored clocks

Each original folder under `P` contains 16 unchanged 256×256 RGBA PNGs, ordered
`0001.png,0003.png,...,0031.png`. The matching Unity folders are
`U/Animations/Destructible tiles/<folder>/`; their PNG `.meta` files declare
127 pixels per unit, custom alignment, and the pivots below. Unity normalized
pivots use bottom-left coordinates; screen pivots below use top-left coordinates.

| Effect folder | Unity Destroy clip | Normalized pivot | Screen pivot |
| --- | --- | --- | --- |
| `Wall Stone explosion` | `Generic Wall Explosion Stone_Destroy.anim` | `(0.5,0.18)` | `(128,209.92)` |
| `Wall Wood explosion Small` | `Wall B C Explo Wood Small_Destroy.anim` | `(0.5,0.19)` | `(128,207.36)` |
| `Wall Wood explotion Large` | `Wall B C Explosion Stone_Destroy.anim` | `(0.5,0.19)` | `(128,207.36)` |
| `Wall wood+stone explosion` | `Wall D Explosion Stone_Destroy.anim` | `(0.5,0.19)` | `(128,207.36)` |

All Destroy clips select those 16 PNGs at **12 FPS**: sample times `i/12` seconds
for `i=0..15`, final sample `1.25s`, clip stop `1.3333334s`, and `m_LoopTime=0`.
The Idle clips hold the first image and are not destruction playback. Wood Large
and wood+stone Destroy/Idle clips exactly match the vendor ZIP. Stone/Small clips
and all sprite import metadata are evidenced by the Unity project; the vendor ZIP
does not contain their clips or PNG `.meta` files.

The source prefabs have unit scale, identity rotation, no flips and no children.
`TileDestructionManager.cs` spawns each prefab at
`map.GetCellCenterWorld(targetCell)` with `Quaternion.identity`; that explicit
spawn overrides its saved root position. Do not import saved prefab positions as
wall offsets or derive directional rotations. Mount at the original owner's
registered contact and committed base height, accounting for the existing legacy
versus padded-bank registrations; source-unit arithmetic does not certify a
native four-view seam or depth result.

## Visibility and cleanup

`U/Example scene/Scripts/Utility/DestructibleProp2D.cs` and the prefabs establish
`destroyOnSpawn=1`, delay `0`, and `hideAnimatedSpritesUntilDestroyed=1`.
Destruction reveals animated sprites, enables the animator and sends `Destroy`;
the controller transition has zero duration. There is no source-authored camera
rotation or directional frame selection.

`U/Example scene/Scripts/Tiles/TileDestructionManager.cs` removes the intact tile
immediately on the lethal branch, explicitly so the VFX is visible. The listed
TileData rows set `destroyVfxCleanup=1.3s` and `swapDelay=1.2s` for their separate
source rubble tile. Thus the clip duration and Unity cleanup deadline are distinct
source values. The four effects do not fade to transparency: their final PNGs
still contain smoke and debris. A finite consumer must clear the effect and must
not hold that final sample as the permanent remnant.

The authorized native integration hides the intact wall at impact and clears the
finite effect after its recorded lifetime. Persistent source rubble admission is
not part of this source receipt. Nonlethal impact behavior is also not established
by these four Destroy banks. Native item damage/destruction, corner provider UUIDs,
boundary channels, attachments and replay remain with their existing owners.
No new wall images, derived camera variants or window-parent substitutions are
required by this reuse.

Source script SHA-256 pins:

- `TileDestructionManager.cs`: `c35f40c302dc81d2eea61309a2be4d9a1f8d68a6ffd454e0f6812111fada4214`.
- `DestructibleProp2D.cs`: `37d95bce52b88a398e70b1614d8c602fcae09ce6c05a251834ffc60e7f97cfdb`.

## Final installed-media and plan check

Reviewed against
[the bounded completion plan](../../WALL_BREAKABILITY_COMPLETION_2026-10-08.md).
The new registration adds exactly the four debris banks listed above. All 64
installed atlas crops retain the original RGBA bytes; all four local/private
production atlas hashes match. Every pose addresses the same unrotated samples.
The installed banks retain the documented pivots, 12 FPS, `state_change_frame=0`,
the source's 1300 ms cleanup deadline and `clear_at_end=true`.

All 47 existing `window.*` banks and 19 `environment.window.*` prop registrations
remain identical to the repository HEAD document. Existing intact solid banks and
legacy corner resources are retained; no replacement wall pixels were generated.
The seven new solid destruction bindings and the generic stone/wood selections
match this receipt's literal source mappings.

The reviewed native changes compose existing item Health/destruction, respect the
after-state's cleared bands/channels, and leave terrain cliffs explicitly
nonbreakable. The required Pixi consumer must exclude destroyed providers from
intact corner batching, render the surviving constituent through its existing
straight selector and clear temporary debris without holding its last smoke frame.
The parent removed this task's retired Pygame renderer patches after the human
corrected the destination; these are consumer requirements, not delivered browser
behavior.
No new wall architecture or expanded asset-family intake was found in this change.

This verifies plan adherence and installed media preservation. It does not certify
browser delivery: NDClient's source/tools/public directories were externally
removed and are not restored by this task. The parent retains native paired
observer recordings and owns the execution/render verification receipt; those
recordings and source arithmetic are not a substitute for unavailable browser
acceptance.
