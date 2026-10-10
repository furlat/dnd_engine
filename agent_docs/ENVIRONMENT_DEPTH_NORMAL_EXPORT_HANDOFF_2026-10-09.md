# Environment depth/normal export — exact needs and current asset status

> **Completed delivery (10 October):** [Current files and validation](ENVIRONMENT_GEOMETRY_DELIVERY_2026-10-10.md). The original request inventory below is retained as a dated specification; all requested export records are now covered.

9 October 2026. Export instructions and a source inventory for the NDClient migration.
This does not change artwork, gameplay assignments, the renderer or the implementation plan.

## Read this first

We have the selected colour assets, animation clocks, many contacts/pivots, height
profiles and family-specific assembly evidence. Preserve them. The new work is
aligned surface depth and normals, plus the few explicitly named source corrections
below. Missing client registration is not proof that an export never existed.

Current editable client owners:

- `/home/tommaso/Dev/NDClient/authoring/environment/index.json`: selected animation banks,
  door/frame selections, prop/trap states, destruction and aftermath.
- `/home/tommaso/Dev/NDClient/authoring/assets.json`: image resource registrations.
- `/home/tommaso/Dev/NDClient/authoring/world.json`: terrain selection, stair contacts,
  support offsets, cliff profiles and material behavior.

The original engine `game/data/` remains unchanged. Export to a separate delivery;
the client adopts its file references intentionally. Do not overwrite those documents
from the art exporter or invent new spell/item/asset bindings.

## Exact lists: every selected bank/resource and every copied catalog family

These CSVs are handoff inventories, not runtime registries:

| File | Contents |
| --- | --- |
| [Selected animation banks](audits/environment-depth-normal-20261009/selected-animation-banks.csv) | **324 rows**, one existing bank ID per row, with uses, views, frame count, clock, cell size, scale, pivots, depth origin/calibration, installed colour/depth files, available source metadata and requested work. |
| [Selected world resources](audits/environment-depth-normal-20261009/selected-world-resources.csv) | **556 rows**, one audited environment image resource per row, including fixture animation frames, their regions/contacts, existing geometry and specific needs. All are registered in the client after restoring the three omitted water entries. |
| [Devices and hatch](audits/environment-depth-normal-20261009/devices-and-hatch.csv) | Cannon, arcane device and portal hatch: existing source owners and the additional component requirements. |
| [All copied environment families](audits/environment-depth-normal-20261009/copied-environment-families.csv) | **725 named catalog entries**, including originals, vendor animation packages, authored variants and candidates. Existing selected associations, source metadata, delivered profiles and assembly evidence are listed. Copying a candidate does not assign new gameplay. |

These counts overlap: a catalog family may supply several banks; a sheet may serve
many frame resources or aliases. They are not counts of separate meshes or required
new exports. Reuse one actual export for aliases of the same source. The current
client has 1,392 image resources overall; 556 describes this audited environment
subset, not the entire client. Desert and arena/crowd artwork remain outside the
selected migration scope. Family-specific assembly evidence is still relevant.

## What each exported asset actually needs

For each **existing source asset, state and authored view**, deliver:

1. **Exact correspondence.** Existing bank/resource ID when selected; otherwise
   existing catalog ID and original colour filename. Identify pose, state and frame
   index. Keep readable filenames and directories. A small delivery mapping to
   those existing identities is sufficient; no new identity or checksum system.
2. **The matching geometry image.** One RGBA8 companion carrying depth and normals
   for the same colour pixels. A static pose needs one sample; an animated bank
   needs the corresponding samples of its existing frames. Keep existing sheets
   or supply explicit page/frame rectangles. Do not export duplicate companions
   merely because multiple native items reference the same bank.
3. **Registration.** Retain original source canvas size, source crop/frame rectangle,
   image pivot, physical contact, display scale, pose mapping and source origin.
   A changed crop is acceptable only with its explicit source-canvas offset shared
   by colour and geometry. Atlas position is a texture address, not a world offset.
4. **Depth calibration.** Declare encoding, depth range, pixel-to-ray origin,
   ray direction and source-to-local/host basis and units. The existing
   `RayDepthGeometry` names are `depthRange`, `pixelToRayOrigin`, `rayDirection`,
   `sourceToLocal` and `basis`. State whether pixel coordinates are source-canvas
   or contact-relative and provide their exact conversion; never leave a pivot
   subtraction implicit. Include the pixel-centre convention.
5. **Normal calibration.** Declare the coordinate basis of the exported normals
   and its conversion to the same local/host coordinates used for depth. Transform
   normals with the inverse transpose under nonuniform source scaling. Do not mix
   camera, object and world normals or bake camera rotation into them twice.
6. **The existing clock.** Preserve `fps` or `sample_times_ms`, frame count,
   duration, release/state-change frames and `clear_at_end`. Preserve opening,
   hold, closing, damage, destruction and settled states that the source actually
   has. There is **no general 24 FPS conversion** for environment assets.

Existing E/S/W/N views remain their authored views. Supply the actual mapping
between source view and physical orientation. Do not add eight directions, mirror
asymmetric geometry, or assume every pack uses the same labels. Keep the camera
calibration fixed within each pose's animation when that is how the original was
captured. The environment owner supports per-pose surface geometry; arbitrary
per-frame camera changes would require an explicit client extension.

For ordinary opaque architecture/props, one visible surface sample per colour
pixel is the target. **Do not automatically split every object into Fireball-style
near/far layers.** Retain existing independent frame/leaf, parent/insert, front/overlay
components. Flag genuinely translucent multi-surface material separately if its
appearance requires more than one contribution.

### Byte format to reuse from the accepted Fireball

One geometry pixel is RGBA8:

- `R,G`: high byte and low byte of a 16-bit depth code: `code = 256*R + G`.
- `code == 0`: no geometric sample.
- Otherwise: `depth = min + (code - 1) * (max - min) / 65534`.
- `B,A`: the octahedral encoding of a unit normal, using the same encoding as the
  accepted Fireball bank. **A is normal data, not opacity.** Colour owns opacity.

Position reconstruction is the declared ray origin at that source pixel plus
`rayDirection * depth`, followed by the declared source-to-local transform and
the instance mount. This must recover the same contacts and physical surface for
every view; it must not depend on a renderer-specific correction.

Use lossless data storage. Existing Fireball runtime packets are gzip-compressed
raw RGBA8; lossless geometry PNGs are also suitable author delivery containers if
their four bytes are preserved. Client upload must bypass colour conversion and
alpha premultiplication and must not interpolate encoded depth bytes or generate
ordinary colour mipmaps. This is client handling, not a reason to require a new
export if correct lossless images already exist.

The existing 88 depth banks use **`rg16le_contact`**, which is a different encoding
and reconstruction convention. Retain that data or explicitly replace it with
the new calibrated packet. Renaming its encoding to Fireball's convention is wrong.
The existing environment enum calls the new convention `rg16be_oct8_ray`; its
nested `RayDepthGeometry.encoding` is `rg16be_oct8_rgba8`. These owner names are not
two distinct requested exports.

### Source correspondence matters more than matching dimensions

Original vendor idle art and a Blender reconstruction can have different silhouettes
despite identical image dimensions. The companion must describe the colour asset
actually selected. If exact source geometry is unavailable, identify the reconstruction
or approximate receiving surface honestly. Do not present a guessed flat box as
exact measured geometry, stretch colour to fit it, or discard original edge stones.

Keep image coverage, receiving geometry and actual blocking geometry distinct.
Shadows and cloth are not solid boxes. A hole in a door/window assembly must remain
an opening; a single visible-depth layer does not reconstruct all hidden surfaces
or a complete collision volume. Existing authored solids and aperture records
remain necessary. No general conversion of alpha silhouettes into collision is requested.

## What is already usable and what needs new channels

| Selected group | Banks | Existing registered depth | New channel work |
| --- | ---: | ---: | --- |
| Doors | 62 | 62 | Add aligned normals; reuse depth/calibration or explicitly deliver its replacement. Separate six mount corrections below. |
| Traps | 36 | 26 | Add normals for those 26; recover/export depth and normals for the other ten. Preserve mechanisms and state clocks. |
| Props/furniture | 168 | 0 | Recover/export matching depth/normals. Existing placement/contact data remains usable. |
| Window assemblies | 47 | 0 | Recover/export matching channels for parent wall, insert and existing post-insert/destruction variants. Preserve masks and passage points. |
| Wall banks/debris | 11 | 0 | Recover/export channels for the actual selected intact/debris art. Seven banks are single-frame; do not invent destruction clips for them. |
| **Total** | **324** | **88** | **236 have no depth registered; no bank currently registers normal maps.** |

“No depth registered” is a client/engine metadata observation, not a declaration
that all source depth is absent. Workshop exports already contain depth images
and `depth-geometry.json` records. Check the named source metadata first.

The ten trap banks without registered depth are the **intact** banks for
`trap.blade-brassbound`, `trap.blade-fortress`, `trap.blade-wood`,
`trap.blade-wood-brassbound`, `trap.blade-wood-fortress`,
`trap.crusher-brassbound`, `trap.crusher-fortress`, `trap.crusher-wood`,
`trap.crusher-wood-brassbound` and `trap.crusher-wood-fortress`
(append `.intact` for each exact bank ID). Their animated counterparts may already
have depth; inspect the corresponding rows rather than re-exporting both blindly.

### Static surfaces and specific corrections

| Asset / exact resource family | Data we already have | What is actually needed |
| --- | --- | --- |
| **D1 stone straight**, `stone.wall.straight.{e,s,w,n}` | Receiving mesh, UVs, source polygons and placement. | New sampled depth/normals improve the proxy. Preserve its authored mount. Visible faces alone are not a complete blocking solid; retain actual compatible joins and suppress internal end faces. |
| **D6 stone frame**, `stone.door.frame.{e,s,w,n}` | Receiving mesh, original aperture image and compatible door associations. | Real arch aperture/thickness registration for obstruction; current mesh is a rectangular receiving shell. The demo's side/top boxes are an approximation, not a universal arch definition. |
| **G17 selected stairs**, `terrain.stairs.{e,s,w,n}` | Calibrated slope proxy, all 12 image contacts and three world supports. | New channels can replace the proxy. Preserve the actual two-step flight and edge-on W/N art; do not demand invented individual treads. |
| **Floor stone/earth/wood**, `terrain.{stone,earth,wood}.{e,s,w,n}` | Colour, pivot, scale and known top-diamond registration. | Matching top and visible skirt surfaces. Do not infer a universal slab thickness from canvas height. |
| **G12/G13 cliffs**, `terrain.cliff.*` | Rise, support offset, corner directions and original registration. | Depth/normals or exact source mapping for upper rim, downhill faces, foot and side returns, using the existing support-relative mount. |
| **D2 stone corners**, `stone.wall.corner.*` | Original corner art, contact and two-face composition semantics. | Its own paired faces, cap and returns. Do not put two full straight-wall sprites underneath. |
| **C1/C2 wooden walls**, `wood.wall.{straight,corner}.*` | Images, poses and placement. | Their own surface channels; do not borrow stone-wall thickness. |
| **Tables/chests and other cutout props** | Existing source-specific contacts and pivots, including corrected covered tables. | New channels improve depth/light; no reauthoring of contact just to fix floor clipping. B37/B38 `(192,204.5)`, plain table `(192,272)` and chest B1 `(192,271.36)` are intentionally different. |
| **Lever, spikes and workshop trap image frames** | Current packed regions, pivots and state/frame selection. | Aligned per-state geometry for physical parts. Match the existing atlas/frame IDs in the world-resource CSV, not a second animation clock. |
| **Cannon / arcane device** | Direction/pitch banks and per-frame muzzle locations. | Aligned geometry for those same poses/pitches/frames. Keep muzzle coordinates and firing timing. |
| **Portal hatch** | Front/overlay split and apertures. | Preserve those components and add matching physical surface channels. |
| **Torch bases and flames** | Separate body/wall resources and flame animation. | Geometry for the physical base where needed; preserve the separate emissive flame. No new solid geometry or universal material replacement for its flame. |
| **Water** | Existing mask, normal, ripple textures and material parameters; client registrations restored. | **No new exporter work.** `water.mask`, `water.normal`, `water.ripple` use the copied pixels and original definitions. |

The 12 registered static geometry resources are D1 ×4, D6 ×4 and G17 ×4.
They are useful existing receiving proxies, not proof of exact reconstructed hidden
geometry or finished rendering. Empty geometry elsewhere does not invalidate its
existing position, height or support information.

## Assets with actual unresolved interpretation/registration

1. **Six generated indoor doors:** `indoor-door-shabby`, `indoor-door-elegant`,
   `indoor-door-shabby-plain`, `indoor-door-shabby-battens`,
   `indoor-door-shabby-patched`, `indoor-door-elegant-three-panel`.
   The supplied assemblies explicitly retain `shared_physical_mount_validated=false`.
   Source camera quarters E/S/W/N are 0/3/2/1, but recovered montage anchors use
   0/1/2/3; S/N residuals are `(-56,+28)` / `(+56,-28)` original pixels.
   Resolve this in the source registration/assembly, preserving colour correspondence.
   Do not repair it with runtime offsets or assume D1/D6 compatibility. Use the
   exact supplied family pairings; original Shabby's proposed pairing is not certified.
2. **Timber staircase:** its measured 12-tread flight rises 0.908693 height steps
   floor-to-top, 0.822968 entry-to-exit. This is measured data, not missing data.
   Keep its actual dimensions; do not stretch it into the different two-step G17 flight.
3. **B13:** supplied supported-platform/trestle interpretation conflicts with the
   native `loose_floorboards` assignment. Reconcile the identity; do not re-request
   its already delivered contacts or pretend it is a flat decal.
4. **B44 / B45:** delivered profiles identify a leaning pole/crossbar and an upright
   pole respectively. Preserve the cloth/shadow exclusions. Remaining native
   interpretation/adoption is our integration task, not an instruction to reauthor
   the same profiles or export their shadows as solids.

The **60 delivered records** remain available: three disputed families, 30 modified
Misc families, nine interiors, six door assemblies and 12 decals. Their original
estimates/qualifications must survive. For decals use the supplied receiver plane
and opacity; do not manufacture depth volumes or new mechanics.

## Adjacency and responsibilities

Existing family-compatible assemblies, source contacts, stair landings, cliff
returns and corner substitutions remain inputs. Depth/normals do not encode which
door fits which wall. Preserve the authored IDs and relative component placements.
The arena's geometric joining records apply to that kit; observed source layouts
are not a universal permission matrix for unrelated Fantasy families.

**Exporter work:** deliver matching channels and reconstruction metadata, plus
the explicitly unresolved source registration corrections. Identify unavailable
source geometry honestly. Preserve current images, timing and existing authoring.

**Client update, 9 October:** the 60 supplemental records are now tracked with
installed-media links and qualifications. Family files assemble the existing
EnvironmentDocument. Static `ImageResourceSource.geometry_region` now supplies
the companion `{path, rect}` alongside existing ray calibration; animated banks
already have companion slots. The three water resource registrations are restored.
Exporter output should identify the existing resource/bank and its companion;
no new client schema is needed. Rendering/selection consumption and raw geometry
uploads remain application implementation work; legacy depth keeps its encoding.

No gameplay rules, collision simulation, material/albedo overhaul, new ownership
planes, arbitrary page-size limits, checksums or bulk recreation of delivered
contacts is requested. Keep packing suited to the actual existing frames. Supply
brief reconstruction examples at known contacts and a matching colour/geometry
overlay when useful; do not build another exhaustive gallery or test framework.

## Source locations

- Consolidated originals, animations and workshops:
  `/mnt/c/Users/tommaso/Documents/assets/fantasy-unified-catalog/`.
- Supplied profiles and precise indoor-door qualifications:
  `data-authoring-2026-10-09/{HANDOFF.txt,DOOR-ASSEMBLIES-HANDOFF.txt,authoring-records.json}`
  under that catalog.
- Blender wall/window source: `/mnt/c/Users/tommaso/Documents/assets/window-reconstruction/destruction-showcase/`.
  Keep original idle art separate from reconstructed Blender rest renders.
- Prop placement work: `/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/placement-registration-53/`.
- Existing source assemblies: `/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/constructor/`
  and `/home/tommaso/Dev/NeuroMapEditor/`; exact per-family references are in the CSVs.
- Current passive types: engine `game/environment_art.py`, `game/asset_types.py`,
  `game/world_binding_types.py`. Accepted packet example:
  `/home/tommaso/Dev/NDClient/authoring/media/banks/core-fireball.json`.

This report classifies available metadata and concrete gaps. It is not a new visual
approval of every asset, nor a claim that all copied art is selected gameplay.
