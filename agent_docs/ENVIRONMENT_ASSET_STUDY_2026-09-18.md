# Environment interaction assets — September 18, 2026

This is a bounded asset study for the user's request to develop doors, lootable
boxes/chests and other environmental interactions alongside action delivery.
It does not add mechanics, import an asset pack, or change rendering. The root
task separately traces the current native actions and recorded event facts.

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
4. Keep fire, breakable barrels, gates, cages and coffins as explicit later
   candidates. The art's existence does not authorize adding associated rules
   before their native ownership is studied and included in the recovery plan.

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
