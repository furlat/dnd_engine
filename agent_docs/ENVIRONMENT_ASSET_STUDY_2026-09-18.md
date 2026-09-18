# Environment interaction assets — September 18, 2026

This is a bounded asset study for the user's request to develop doors, lootable
boxes/chests and other environmental interactions alongside action delivery.
It does not add mechanics, import an asset pack, or change rendering. The root
task separately traces the current native actions and recorded event facts.

**Scope correction:** the first pass concentrated too narrowly on doors and
containers. The user's follow-up explicitly includes levers, extinguishing
placed lights and other environment mechanics. The expanded study below covers
those existing features, the original client's actual world rendering, and
additional packed atlases. Missing ideal artwork is not grounds to defer an
already supported native interaction.

## What can be reused immediately

The current game already has the Fantasy wooden door's closed/open pictures in
all four directions. The same pack contains three complete closed/open chest
picture pairs and ordinary wooden crates, barrels and a stone fire ring. These
are sufficient to make the existing door and loot interactions visible without
creating new artwork. A pictured open chest does not establish a native open
state, and an emptied container is not automatically an opened container.

The chest and door pictures are **static states**, not frame sequences. Genuine
prop animation sequences also exist, principally barrel destruction and looping
fire. They are a separate capability from selecting an authored state picture.

For the broadened unit, **levers and placed lights are already actionable**.
NeuroClient had a simple actual world drawing for interactables and lit/unlit
lights. MapEditor has a more legible lever base and handle drawing. These can
carry the existing interaction while better sprites remain an independent art
choice. The current native oil barrel also already has destruction, spilled-oil
and fire-contact consequences; the art study must not present that established
behavior as an invented future mechanic.

## Expanded findings: controls, placed lights and environmental consequences

### Levers: an existing world drawing, plus distinct UI art

The source of the original working representation is
`/home/tommaso/Dev/NeuroClient/app/src/tiles.ts`, `buildFloorObjects`, around
line 711. Objects with `object_kind === "interactable"` receive a gray vertical
2 × 10 stick and a circular knob. The container is clickable, uses the object's
actual map position and enters ordinary world depth sorting. This is a world
marker built from geometry, not an imported bitmap, and it has one displayed
pose; it does not contain a hidden authored lever-pull animation.

Two existing clearer geometric descriptions are available:

- `/home/tommaso/Dev/MapEditor/app/src/objectMarkers.ts:54`:
  a 12 × 8 base at `(-6,-4)`, a 3-pixel handle from `(0,-4)` to `(2,-20)` and
  a radius-3 knob at `(2,-21)`; colors `0x8d8d82`, `0xc8c2a0`, `0xe8d479`.
- `/home/tommaso/Dev/NeuroClient/app/src/ui/battlefieldPreview.ts:156`:
  a 14 × 6 base and 3-pixel handle from `(0,2)` to `(5,-10)`.

Those sources prove that the native feature did not require a packaged pixel
lever sheet. Reuse the small geometric representation or select suitable art
through ordinary presentation data. Do not copy the old MapEditor's
name-matching dispatch into the game, invent a generic marker engine, or infer
new toggle mechanics from the direction of a drawn handle. Native
`PullLeverAction` currently deactivates one linked `SpikeTrap`; `TrapLever`
records that exact linked condition identity. It does not establish an
arbitrary door-wiring system or a persistent `is_pulled` field.

The following already-authored **UI icons** were visually inspected:

`/home/tommaso/Dev/NeuroClient/app/public/game-icons/fantasy-classic-v1/icons/`

- `object.trap-lever.webp`
- `action.pull-lever.webp`
- `object.wall-torch.webp`
- `action.extinguish-wall-torch.webp`
- `action.light-wall-torch.webp`
- `object.oil-barrel.webp`
- `object.campfire.webp`
- `item.torch.webp`

All are 256 × 256 framed, painted illustrations, with opaque scene backgrounds.
They suit an action/object panel and cannot be treated as transparent isometric
world sprites. The separate pull/extinguish/light illustrations are action
icons, not frames of an object animation. Their inspection sheet is
[interaction UI icons](../.runtime/environment-study/interaction-ui-icons.png).

### Placed lights: existing lit/unlit state and independent flame layer

`NeuroClient/app/src/tiles.ts:626` already draws `light_source` objects
differently from actual `is_lit`: a lit orange center with a larger translucent
yellow circle, or a dark unlit center. The rendering record retains `is_lit`,
so there is a proven visual state distinction to preserve.

Current native `dnd/items/torches.py`, `WallTorch` and the standing fixture
variant, own the light state. `WallTorch.to_item_presentation_state` includes
`is_lit` and its light radii; use-action discovery selects Ignite or Extinguish
from that state. Extinguishing removes the fixture's light source. Native
exposed-flame interaction also supports dousing. These facts make extinguish,
relight and resulting subjective sight changes meaningful gameplay clips,
independent of whether a new flame strip is imported.

The already inspected Fantasy art offers a standing torch body (`Torch2.png`),
two named wall-fixture pictures (`Torch East.png`, `Torch West.png`), a stone
brazier (`Misc C8_{E,N,S,W}.png`) and unlit campfire base (`FirePlace.png`). The
separate `Animations/Props/Torch 1/` and `Fire/` flame sequences can follow the
same recorded lit state. The two wall pictures include small warm-colored
pixels at their tips; no distinct authored unlit wall-torch pair was found.
Do not promise a perfect off-state by treating the whole lit picture as a
removable flame. The current standing body plus a separately controlled flame,
or the original geometric light marker, supports this feature now.

Neither brazier art nor a campfire picture creates a native switch action.
Current campfire Rest/Cook are their own existing interactions. The explicit
ignite/extinguish feature belongs to fixtures whose native owners expose it.

### Breakable props: oil already has gameplay consequences

`dnd/content/items/environment_item_builders.py:42` defines the existing
`OilBarrel._on_destroy` path; `build_oil_barrel` at line 295 creates the targetable,
movement-blocking item with 12 HP. Destruction at the item's committed position
activates `OilSurface`. When the destroying damage includes FIRE, the native
lineage additionally carries an IGNITE spatial interaction. Presentation should
show those recorded outcomes; it should not independently decide that every
damaged barrel explodes.

The Fantasy static `Misc A8` barrel or the previously identified Barrel 1 idle
picture are usable intact art. Barrel 1's wood-debris sequence is useful
destruction art, with the one-projection limitation recorded below. Barrel 2
visibly spills **blue water**, and Barrel 3 **green material**; neither is an
accurate oil visual merely because the backend object is a liquid container.
Spilled oil and resulting fire belong to their native persistent effect state,
not to a fabricated permanent state of the disappearing barrel object.

The Desert archive also has explicitly named material impact sequences under
`D/Animations/Destructible tiles/`: `Wood damage/` (16 PNGs), `wood explosion
Small/` (17), `wood explosion large/` (17), `Stone damage/` (17), `stone
explosion Small/` (17), `stone explosion large/` (17), and `Clay explosion/`
(17). Their existence was checked by entries only; their visual content and
per-direction alignment have not been reviewed. These are optional subsequent
art inputs, not dependencies for enabling the existing object damage path.

### Additional atlases inspected beyond the Fantasy Misc sheet

The old Godot project includes packed rural object atlases at:

`/mnt/c/Users/tommaso/Documents/dev/smallscale_template/assets/tilemaps/zombie_rural_grouped/`

- `objects_1_15.png`: 512 × 3840
- `objects_16_30.png`: 512 × 3840
- `objects_31_44.png`: 512 × 3584

All three were visually inspected. The project's
`resources/tilesets/zombie_interior_128_256.tres` explicitly uses 128 × 256
atlas regions with texture origins such as `(0,80)`; these are placement data,
not animation frames. Matching original `ObjectN_{E,N,S,W}.png` files are under
`assets/tilemaps/zombie_rural/`.

Relevant confirmed candidates:

| Original family | Visually inspected content | Actual availability |
| --- | --- | --- |
| `Object1_{E,N,S,W}.png` | Intact dark metal barrel | Four static 128 × 256 views |
| `Object9_{E,N,S,W}.png` | Small upright pipe/control with a red handwheel, visually a valve/standpipe | Four static views; no alternate wheel position or semantic metadata; do not label it a proven lever |
| `Object17_{E,N,S,W}.png` | Open dark metal barrel | Four static views; not a demonstrated damaged frame of Object1 |
| `Object18_{E,N,S,W}.png` | Rusted/open metal barrel | Four static views |
| `Object23_{E,N,S,W}.png` | Utility pole and electrical equipment | Modern decoration, unsuitable as an assumed fantasy light fixture |
| `Object25_{E,N,S,W}.png` | Loose wooden boards | Four static debris views; no identified originating break sequence |
| `Object34_{E,N,S,W}.png` | Small stump/chopping setup with a dark tool | Does not establish a pressure-plate or spike-trap sprite |

The modern metal/utility style is a choice, not an automatic import. The red
handwheel could support a later authored valve/control, while the original
geometric lever remains the more faithful immediate representation of the
existing TrapLever behavior.

The Desert-only `Misc B62`–`B66` pictures were also inspected: they depict thorny
root/barricade arrangements, not switches. `Misc D6`–`D8` are bone/skull
decorations. These cannot fill the lever gap by filename speculation.

Directory inventories of the HD Zombie 1, Zombie 2 and HD Enemy 1 archives
confirm primarily actor spritesheets rather than another hidden environment
catalog. No additional lever/switch/pressure-plate sheet was identified. This
is a bounded search result, not a claim that no such art exists anywhere on the
machine.

Further inspection sheets:

- [Rural object atlas 1–15](../.runtime/environment-study/zombie-objects_1_15.png)
- [Rural object atlas 16–30](../.runtime/environment-study/zombie-objects_16_30.png)
- [Rural object atlas 31–44](../.runtime/environment-study/zombie-objects_31_44.png)
- [Selected rural props](../.runtime/environment-study/zombie-interaction-details.png)
- [Red-handwheel control detail](../.runtime/environment-study/zombie-object9-detail.png)
- [Additional Desert props](../.runtime/environment-study/desert-additional-props.png)

## Sources and scope

Archives inspected by directory listing, selected image decoding and selected
Unity animation metadata reads:

- `/mnt/c/Users/tommaso/Downloads/Fantasy tileset - 2D Isometric V1.1.zip`
- `/mnt/c/Users/tommaso/Downloads/2D Desert Fantasy tileset v1.0.zip`

An already extracted Fantasy source is also present at:

`/mnt/c/Users/tommaso/Documents/dev/assets/Fantasy tileset - 2D Isometric V1.1/Fantasy tileset - 2D Isometric/`

The following tables use these exact archive prefixes:

| Prefix | Exact archive directory |
| --- | --- |
| `F/` | `Fantasy tileset - 2D Isometric/` |
| `D/` | `2D Desert Fantasy tileset v1.0/` |

`{E,N,S,W}` means four separate PNG files, not four animation frames. Direction
availability was checked in the archive listing; the East images were visually
inspected. Representative images were extracted only under ignored
`.runtime/environment-study/`. Contact sheets preserve source artwork, with
scaling and labels solely for inspection. No hashing, source audit or startup
validation was introduced.

`Documents/assets/smallscale` contains the already known actor packs; its top
level does not identify an additional environment pack. `Documents/assets/lelu`
and `binbun` contain VFX projects. Those were not recovered or rendered for this
environment gameplay study.

## Authored state pictures

All listed Fantasy pictures are 256 × 256 PNGs. Actual artwork occupies only
part of that canvas; preserve its authored placement rather than trimming and
recentering each state independently.

| Subject | Exact paths beneath `F/` | Confirmed visual states | Directions |
| --- | --- | --- | --- |
| Small rounded chest | `Environment/Chest A1_{E,N,S,W}.png`, `Chest A2_{E,N,S,W}.png` | A1 closed; A2 same chest with lid open | Four each |
| Small square chest | `Environment/Chest A3_{E,N,S,W}.png`, `Chest A4_{E,N,S,W}.png` | A3 closed; A4 same chest open | Four each |
| Large gold-banded chest | `Environment/Chest B1_{E,N,S,W}.png`, `Chest B2_{E,N,S,W}.png` | B1 closed; B2 same chest open | Four each |
| Arched wooden door | `Environment/Door A1_{E,N,S,W}.png`, `Door A2_{E,N,S,W}.png` | A1 closed; A2 swung open | Four each |
| Dark barred gate | `Environment/Door C1_{E,N,S,W}.png`, `Door C2_{E,N,S,W}.png` | C1 full gate; C2 raised/retracted bars | Four each |
| Pale barred gate | `Environment/Door C3_{E,N,S,W}.png`, `Door C4_{E,N,S,W}.png` | C3 full gate; C4 raised/retracted bars | Four each |
| Gridded portcullis | `Environment/Door C5_{E,N,S,W}.png`, `Door C6_{E,N,S,W}.png` | C5 full grille; C6 short visible lower portion of raised grille | Four each |
| Coffin | `Environment/Misc B22_{E,N,S,W}.png`, `Misc B23_{E,N,S,W}.png` | B22 covered coffin; B23 open coffin containing bones | Four each |
| Cage | `Environment/Misc C12_{E,N,S,W}.png`, `Misc C13_{E,N,S,W}.png` | C12 closed cage; C13 cage with door open | Four each |

For repeated filenames in a cell, the directory remains `Environment/`.
The gate classification describes the pictures; it does not decide which
mechanical movement/vision rules or opening direction should be authored.
Likewise, coffin B23 contains bones in the image: it is not a general-purpose
empty-container picture.

The Desert archive provides the same named chest and door families under
`D/Environment/Sprites/`, with a different color/material treatment. It adds
`Door C7/C8` (boarded opening, closed/open) and `Door C9/C10` (plain plank door,
closed/open), each with E/N/S/W entries. Selected East images are 256 × 256.
These are alternatives; they need not be imported together with the Fantasy
family to establish the first working interaction.

No chest-opening animation strip or door-swing strip was found in either
archive. In particular, `Animations/Equipment/Chest1Animation` and
`Chest2Animation` in the Desert pack are **character torso equipment layers**,
with Walk/Attack/Die sheets. They are not animated loot containers.

## Ordinary props that need no new artwork

Exact paths below are beneath `F/Environment/`. Every `Misc` entry listed has
E/N/S/W pictures, each 256 × 256.

| Picture | What is actually drawn | Limits |
| --- | --- | --- |
| `Misc B1_{E,N,S,W}.png` | Single wooden crate | No open or emptied variant identified |
| `Misc B2_{E,N,S,W}.png` | Three stacked crates | Arrangement, not a state of B1 |
| `Misc B3_{E,N,S,W}.png` | Large wooden crate | Distinct size; not B1's damaged state |
| `Misc A8_{E,N,S,W}.png` | Intact wooden barrel | Static; separate destruction frames discussed below |
| `Misc A2_{E,N,S,W}.png` | Lidded ceramic jar | No open/damaged pair identified |
| `Misc A1_{E,N,S,W}.png` | Bones on the ground | Decoration; not a live actor or an event outcome by itself |
| `Misc B42_{E,N,S,W}.png` | Roofed well containing water | No operation sequence identified |
| `Misc C8_{E,N,S,W}.png` | Stone brazier with dark fuel | Fire can be a separate visual layer if supported by native state |
| `FirePlace.png` | Stone fire ring with unlit wood | One picture; no directional suffix |
| `Torch East.png`, `Torch West.png` | Small wall torch bodies | Two named views, not a four-direction set |
| `Torch2.png` | Standing torch body | One picture; already the game's `torch.body` art |

No lever or switch was confidently identified by filename or visual review of
the Fantasy Misc inventory. Do not relabel a training dummy, sign or crane as
the lever just to claim complete media coverage. A native lever interaction can
remain a documented media gap until a suitable authored prop is selected.

## Genuine animation sequences

These directories are present in both archives under
`F/Animations/Props/` and `D/Animations/Props/`. Counts below are PNG file counts,
not inferred durations. Their files are single pictures per timestamp, without
E/N/S/W suffixes; the inspected frames show one camera projection. They do not
establish four-direction animated coverage.

| Directory | Exact numbered files | Size | Visually confirmed behavior |
| --- | --- | --- | --- |
| `Barrel 1/` | `0001.png` through `0033.png`, odd numbers; 17 files | 256 × 256 | Intact barrel breaks into wooden debris and smoke |
| `Barrel 2/` | `0001.png` through `0031.png`, odd numbers; 16 files | 256 × 256 | Open water-filled barrel breaks and spills blue liquid |
| `Barrel 3/` | `0001.png` through `0033.png`, odd numbers; 17 files | 256 × 256 | Green-liquid barrel breaks with green cloud and residue |
| `Fire/` | `0001.png` through `0031.png`, odd numbers; 16 files | 128 × 128 | Fire flicker, suitable as a separate layer |
| `Torch 1/` | `0001.png` through `0031.png`, odd numbers; 16 files | 256 × 256 | Small flame flicker, not a torch-body destruction sequence |
| `PortalOpen/` | `0001.png` through `0031.png`, odd numbers; 16 files | 256 × 256 | Portal grows from nearly absent to fully visible |
| `PortalIdle/` | 16 PNGs, from `0033.png` to `0062.png`; numbering is irregular | 256 × 256 | Standing portal flicker |

Additional directories `Fire2/` (16), `Gas/` (16),
`Skeleton explosion/` (16), and `Turret1/` (`CB1.png` through `CB8.png`)
exist. They were counted from filenames but not visually characterized as part
of the actionable shortlist.

The **Desert** archive includes Unity `.anim` files. Useful authored timing:

- `Animations/Props/Fire/New Animation.anim`: 16 sprite samples at 12 fps,
  stop time 1.3333334, looping.
- `Barrel 1/Barrel_Destroy.anim`: 16 samples at 12 fps, stop time 1.3333334,
  nonlooping, despite 17 PNG files in that directory.
- `Barrel 2/Barrel 2_Destroy.anim`: 16 samples at 12 fps, 1.3333334,
  nonlooping.
- `Barrel 3/Barrel 3_Destroy.anim`: 17 samples at 12 fps, 1.4166667,
  nonlooping.
- `PortalIdle/PortalIdle.anim`: 16 samples at 12 fps, 1.3333334, looping.
- `PortalOpen/PortalAni.anim`: 16 samples at 12 fps, 1.3333334, also marked
  looping in Unity. A filename alone is not evidence of correct one-shot
  playback settings.
- `Torch 1/Torch 1_Destroy.anim` has 16 samples, 12 fps, nonlooping, while
  the pictures visibly show flame flicker. The clip's name is not a semantic
  instruction to destroy a torch in this game.

Neither archive includes `.png.meta` files in its entry list. Unity sprite GUIDs
inside these clips therefore do not directly establish the filename-to-sample
mapping. Do not silently treat all PNGs as frames with the same inferred timing.
For the initial native door/loot work, none of this Unity recovery is required.

## Existing alignment and presentation data

Current sources in this repository:

- `game/data/assets.json` already maps wooden door states to
  `game/assets/environment/door-a1-{e,n,s,w}.png` and `door-a2-{e,n,s,w}.png`.
  Their native canvas is 256 × 256, pivot `[128, 209.92]`, scale
  `1.0078740157480315`.
- `game/data/world_bindings.json` exposes `wood_door_closed`, `wood_door_open`
  and `stone_door_frame` directional maps. Its item map currently binds only
  `environment.standing_torch` to `torch.body`; there is no chest asset binding.
- `game/data/neuroclient/source/src/render/data/animation/contentActionPresentationRecipes.json`
  already contains environment action entries for directional/ordinary door
  open and close, chest `loot_all`, campfire rest and trap-lever pull. The
  inspected entries disable the actor, select `Idle`, have no media, and put
  `action_start`, `effect` and `recover` at frame zero. These entries preserve
  the authored schema but do not prove those actions currently have body or
  object animation.

Reusable external reference data:

- `/home/tommaso/Dev/NeuroMapEditor/public/assets/fantasy/catalog.json` lists
  chest IDs such as `fantasy.chest.a1.e`, their exact original archive paths,
  256 × 256 size and default pivot `[128, 208]`; `animation` is null.
- `/home/tommaso/Dev/MapEditor/app/src/assetCatalog.ts` additionally records
  per-view visual bounds. For example A1 East is `(96,161,65,63)`, while A2
  East is `(97,141,78,83)`: the open lid expands upward on the same canvas.

These are useful alignment references. The old catalog's generic semantics
mark chests as floor/decal, nonblocking and non-occluding; that must not override
the current native object's actual geometry or justify copying an old map
subsystem. Static art and native behavior are separate authored inputs.

## Bounded use in the resumed gameplay work

1. Use the already imported door pair for real open/close actions, preserving
   the native door's state, path/vision consequences and subjective recording.
2. Select one chest or crate family to display existing native storage and
   LootAll. Keep the object picture tied to actual recorded object state. Do
   not invent an `is_open` fact from inventory emptiness or from the existence
   of an open picture in the pack.
3. Use the existing NeuroStudio recipe format and current world asset binding
   data for the visual choices; actor interaction timing and prop state timing
   remain part of the same complete lineage. There is no need for a new object
   animation manager to draw a static state change.
4. Include the user's explicitly requested lever and placed-light interactions:
   native trap deactivation, extinguishing and relighting fixtures, and their
   resulting sensory changes. Use existing world drawings or suitable sprites;
   missing ideal lever art is not a blocker to the native feature.
5. Connect existing oil-barrel destruction and environmental consequences when
   included in the implementation plan. Gates, cages, coffins and valve artwork
   remain additional options; their appearance alone does not define new rules.

This study makes no claim of implementation or full pack audit. The next
behavioral acceptance belongs to the implementation: real interactions,
permitted observers, loss/reacquisition of sight, independently delayed
playback, and four camera corners using the saved event sequence.

## Inspection artifacts

These files are local, ignored review aids and may be regenerated from the
source archives; they are not production assets:

- [Fantasy chest and door states](../.runtime/environment-study/chests-doors.png)
- [Desert chest and door states](../.runtime/environment-study/desert-chests-doors.png)
- [Fantasy miscellaneous props](../.runtime/environment-study/misc-overview.png)
- [Interaction prop details](../.runtime/environment-study/interaction-prop-details.png)
- [Animated prop samples](../.runtime/environment-study/animated-props-samples.png)

The small number of extracted originals sit beside these sheets. No test suite
was run because this task changed only this study document and ignored
inspection output.

## Selected imports made by the implementation unit

The presentation implementation subsequently imported exactly two wall-torch
pictures from the inspected Fantasy source, without modifying their bytes:

| Original archive entry | Repository resource |
| --- | --- |
| `Fantasy tileset - 2D Isometric/Environment/Torch East.png` | `game/assets/torch/wall-east.png` (`torch.wall.e`) |
| `Fantasy tileset - 2D Isometric/Environment/Torch West.png` | `game/assets/torch/wall-west.png` (`torch.wall.w`) |

Both use the existing 256 × 256 canvas, common pivot `[128, 209.92]` and scale
`128/127` (`1.0078740157480315`). The passive prop binding explicitly aliases
camera poses `e`/`n` to the East picture and `s`/`w` to the West picture. These
are **two real views**, not four independently authored orientations. The
shared original flame loop is displayed only when received `is_lit` is true.
When that loop is off, the static wall pictures retain their authored small
warm-colored tip pixels; no perfect unlit picture was invented or claimed.

`game/assets/environment/lever-marker.svg` transcribes the existing MapEditor
`objectMarkers.ts:54–63` base, handle and knob geometry, with source credit in
the SVG. Its 16 × 32 canvas uses pivot `[8,26]` and an explicit display scale
of `2`. This is presentation sizing, not a proven conversion between tile
conventions: MapEditor's current `tilemapConfig.ts` also specifies a 128-pixel
wide tile (64 pixels high). It is a **single
neutral marker pose**; spent charges do not select an invented pulled handle,
and the lever does not acquire a flame layer.

These resources enter the existing image catalog and the shared passive prop
bindings. No source-image audit, digest or new animation subsystem accompanies
the import. Earlier statements about the original standing-only binding record
the pre-implementation state; the implemented `props` table now covers standing
torch, wall torch and trap lever.
