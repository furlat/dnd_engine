# Assets — current NDClient migration

Updated 10 October 2026. Previously selected asset copying and core tracked authoring preparation are complete. The next
work is application integration using these installed inputs. The Goblin/Demon leaf material and
asset review are implemented; game renderer, UI and SDK integration have not started in the recreated `/home/tommaso/Dev/NDClient` repository.
The [implementation plan](agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md)
owns implementation; this file owns current artwork selection and locations.

## Installed folder layout

One Git-ignored `.media/` tree in NDClient, with meaningful source filenames:

| Folder under `.media/` | Selection |
| --- | --- |
| `smallscale/modular/` | Complete unified Fantasy Character Creator V1.3, 3,888 source sheets. Original layer/action folders; no separate old 1,281-sheet subset. |
| `smallscale/authored/` | All ten owned creature packs, including unimplemented creatures: animals, barbarians, characters, demons, dinosaurs, enemies, orcs/goblins, undead and both zombie packs. Combined/with-shadow bodies; original separate effects/shadows and existing derived shadows retained. Original clean Goblin/Demon bodies are also installed under each pack’s `Bodies/`, as authorized inputs for independent layer controls. |
| `environment/{doors,walls,windows,props,traps,devices}/` | Selected registered images, state/destruction banks, frames, masks and existing companions, grouped by family. |
| `environment/{terrain,fixtures,portals,lighting,water}/` | Selected surfaces, fixture animations, hatch, torch and water channels. |
| `environment/library/{fantasy,animated,registered,props,depth}/` | Preserved Fantasy originals and workshop exports, including unused library assets. No redundant `current/environment` or `production-media/packed/environment` import wrappers. |
| `ui/icons/smooth48/` | 594 selected smooth icons; no parallel pixelated or full-size library. |
| `ui/portraits/192x256/` | 661 portraits by source bank and readable name, including assigned creatures and free/player choices. Scale smaller as needed; cropping is a UI choice. |
| `vfx/spells/`, `conditions/`, `areas/`, `actions/`, `shared/` | Full spell cycles, independent condition lifetimes, world effects, action effects and shared dependencies. Modular casting accents reuse `smallscale/modular/`. |
| `vfx/areas/<spell>/<component>/` | Paired replacement packets alongside their named spell family, e.g. `fireball/explosion/{near,far}/`. No batch-name or nested `media/` wrapper. |

`authoring/` is the Git-tracked editable client copy: recipes, selected media
definitions/storage, paired bank metadata, world/image bindings, the selected
environment document and schema. `authoring/items/index.json` assembles the
existing hand/ground appearances, item materials, variant inventory and source
palettes, with their existing types and source values retained. Equipment sheets
resolve through the existing rig/resource records into the installed modular library.
`authoring/ui/index.json` now assembles the existing five UI sections: 620 icon
keys, 43 delivered creature portrait assignments, 618 free portraits, five new
documented premade defaults and all 103 choice-icon records. It uses the selected
images above; no new copy, legacy skin or duplicate native content registry.
The modular Skeleton Warrior portrait assignment and dedicated Unarmed icon are
explicit remaining art gaps, recorded in client `authoring/ui/README.md`.
`authoring/catalog-index.json` is its entry point. Only artwork and local/generated
records are ignored. `authoring/environment/index.json` assembles 324 selected banks and
their door/prop/trap/wreck mappings, existing depth and frame registrations.
The 60 delivered source assembly/placement records are tracked in
`authoring/environment/source-records/`; existing relevant door/prop records link
to them. Their source qualifications remain explicit; the six door mounts and timber
flight now contain the delivered physical assembly closure. The 10 October
assembly pre-phase connected the physical contacts, camera mappings, effective
mounts and member/support data to existing typed owners; master §6.1 records it.
`world.wall_corner_faces` preserves the existing wall join mapping, separately
from cliff corners. Runtime assembly consumption remains application work;
compatibility is not inferred from similar filenames.
`.runtime/<family>-assets/` retains source references and copy receipts;
`.runtime/vfx-replacements/` records the replacement intake. These are not another
editable binding system. Future `/media/` serving maps to `.media/` directly;
Vite `public/` and `dist/` must not duplicate the library.

## Authoring sources

All Windows asset sources are under `/mnt/c/Users/tommaso/Documents/assets/`
(`C:\Users\tommaso\Documents\assets` in Windows).

- **Godot VFX factory:** [VFXFactory](/mnt/c/Users/tommaso/Documents/assets/VFXFactory/).
  Open `project.godot`; native preview is `factory/scenes/preview.tscn`.
  Recipe data/code and shared factory components remain there. Current selected
  [delivery handoff](/mnt/c/Users/tommaso/Documents/assets/VFXFactory/exports/selected-23-completion-20261009/delivery/HANDOFF.md)
  and its `manifest.json` own the replacement selection, overriding older partial
  export checklists. Do not copy the entire Factory or its captures/review images.
- **Blender destructible walls/windows:**
  [window-reconstruction/destruction-showcase](/mnt/c/Users/tommaso/Documents/assets/window-reconstruction/destruction-showcase/).
  `build.py` and per-family `<family>/{wall,window,wall-after-insert}/*.blend`
  contain the authored scenes. `dense-production/` holds dense parent-wall
  exports; `insert-only-production/` holds independent inserts. Keep original
  idle art separate from Blender rest renders. Ordinary solid-wall source debris
  has its own [handoff](agent_docs/WALL_BREAKABILITY_PIXI_HANDOFF_2026-10-08.md).
- **Environment consolidation:**
  [fantasy-unified-catalog](/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/):
  `a-original/`, `b-animated-versions/`, `c-new-props/`, plus `provenance/workshops/`
  for Blender prop/trap tools. The received `data-authoring-2026-10-09/` supplies
  missing contacts, dimensions and assembly evidence. `arena-study/` and
  `environment-production-audit/` retain placement/adjacency studies.
- **UI source and assignments:**
  [dnd-engine-icons-and-portraits/README.md](/mnt/c/Users/tommaso/Documents/assets/dnd-engine-icons-and-portraits/README.md).
- **Preserved original packs:** `/home/tommaso/Dev/neurodragon_art/sources/`,
  source archives under the Windows asset root and existing engine sources.
  Exact selected archive members are recorded by `tools/prepare_character_assets.py`
  and `.runtime/character-assets/`; originals are not deleted or overwritten.

## Current VFX selection and remaining work

The completed Factory delivery supplies **28 spells, 193 paired banks and 400
media IDs**, covering all 38 formerly pending XYZ references, including ground
fire/burning Web. The copy tool is `tools/prepare_vfx_replacements.py`; ordinary
VFX use `prepare_vfx_assets.py`. Read the [intake record](agent_docs/audits/NDCLIENT_VFX_ASSET_INTAKE_2026-10-09.md)
for installed status. Preserved 2D conditions/projectiles and live procedural
lightning accompany the new depth/normal packets. **No retired XYZ import,
conversion or fallback.** This is not a claim that every condition has new normals.

Preserve full recipes, state transitions, sockets, frame windows, directions,
coalescing groups, radiance, crop/pivot and camera matrices. Fireball is 46 frames
at 24 FPS; other rates stay authored. New planes do not replace layer/elevation
and contact registration. Ice Knife's burst is enabled in the new client recipe;
renderer support remains future work. Pygame behavior/bindings in `game/data/`
were not overwritten. NDClient edits now belong to the tracked `authoring/` copy;
no new creature assignments follow merely from copying artwork.

The existing-ID connection in [master plan §5.1.1](agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md#511-connect-canonical-recipes-to-the-prepared-artwork)
is prepared: `tools/import_vfx_authoring.py` seeded the full effective authoring
once, using existing Python owners plus paired-bank fields. It refuses overwrites.
`tools/build_authoring.py` reads client JSON without the engine or receipts and
resolves 126,959 distinct authored media references. It assembles catalog/world/assets/environment,
the four existing item/palette sections and the five existing UI sections;
complete application-release integration, environment rendering consumers
and UI runtime consumption are still pending. Fireball’s impact storage now carries
the accepted v4 demo’s seven-key world-light curve, including its position transform
and effective intensity. This completes that authoring association. Other spell
VFX world-light curves are deferred until Fireball is tested in the shared
renderer, per the user's 10 October decision. This does not hold up authoring
preparation; the separate assembly-connection correction is recorded below.
Later curves will use the same optional field. Raw Factory manifests
live in `.runtime/vfx-replacements/` as provenance; the editable bank metadata is
in `authoring/media/banks/`. Copy receipts are not runtime bindings.

The [environment depth/normal export handoff](agent_docs/ENVIRONMENT_DEPTH_NORMAL_EXPORT_HANDOFF_2026-10-09.md)
lists each selected bank/resource and all copied catalog families, with existing
data and exact exporter work. The two client omissions found there are repaired:
static `ImageResourceSource.geometry_region` holds the companion file/rectangle
alongside its existing ray calibration, and water mask/normal/ripple resources
are registered against their existing files. Environment companion adoption is complete (10 October): 42,805 required files (1114.43 MiB) were copied into the existing readable family folders. Tracked authoring now includes all 324 selected banks (24,632 pose/frame associations), the selected static resources, device/hatch layers and 725 library families (67,272 explicit samples). All seven assembly closures are connected to typed authoring; the source records remain provenance.

The accepted [delivery](agent_docs/ENVIRONMENT_GEOMETRY_DELIVERY_2026-10-10.md) and
[corrected metadata](agent_docs/ENVIRONMENT_GEOMETRY_INTAKE_RESPONSE_2026-10-10.md)
are now adopted per master §6.1. Selected owners carry typed frame-local sampling,
normal transforms, receiving meshes, support/component masks and semantic roles.
Unused library samples preserve original views, variant slots and available clocks;
they acquire no gameplay bindings. No raw XYZ, proof images, scenes or duplicate
enlarged packets were copied. The one-time importer is
`tools/adopt_environment_geometry.py`; its local report is
`.runtime/environment-geometry/adoption.json`. Do not repeat this migration.
Rendering, light obstruction and Studio consumers remain application work.

Character data and current controls are described in client
`authoring/characters/README.md`. All 1,368 Goblin/Orc and Demon combined sheets
(65 characters) now use the authored `source_interaction` method with original
body/shadow/effect inputs. The 1,368 clean bodies add 198.69 MiB; 1,089 obsolete
generated masks for these packs were retired. Neutral output preserves the source;
body/shadow/VFX strengths and independent body/VFX hue/tint are implemented in one
Pixi material used by the inspection page. Existing rig identities and source art
are unchanged. The 12,705 total character records include initial partitions for
other packs; those are not newly certified by this two-pack composition work.
A bounded observed-shadow/colour treatment does not recover hidden 3D geometry.
The authoring connections are now complete for registered Goblin/Demon and
animal/dinosaur rigs: 85 explicit FX selections (19 on, 66 off), 98 added animal
body/shadow source associations and existing layer-owner material controls. This
step changed tracked JSON/schema only, with no artwork copies or new rig identities.
The actual game renderer and resource/event integration remain future work.

Desert and arena/crowd selection remain deferred. The new geometry delivery includes
six generated indoor-door mount closures and the timber flight's fractional-rise
assembly closure. Their active bank/door/library placement fields and effective
mounted transforms are now connected and checked. Source records retain the
original evidence. Master §6.1 records completion without recopying files. Original image pivots remain separate from physical mounts. The [earlier environment handoff](agent_docs/audits/ndclient-environment-assets-20261009/README.md)
remains provenance; do not repeat its now-delivered exporter work.

Keep readable folders and original meaningful names. No checksum/deduplication
system, bulk re-export, arbitrary packing budget or duplicate asset variants.
The old file is preserved verbatim in the [asset diary](agent_docs/history/ASSETS_DIARY_2026-10-09.md).
Consult it only for historical evidence; it is not current migration instruction.
