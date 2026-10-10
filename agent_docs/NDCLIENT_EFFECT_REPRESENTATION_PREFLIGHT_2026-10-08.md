# NDClient compact media, blood and receiver contract

**Superseded migration route — 9 October user correction:** old spell/VFX XYZ
banks are fully replaced by new exports. Any legacy-packet conversion procedure
below is historical reference, not work to implement or a fallback to install.
The current [complete master plan](NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md#21-new-capabilities-versus-recovered-behavior)
owns this policy. Preserve original archives and full recipe/lifecycle semantics.
Broader depth/normal coverage is the preferred staged direction; it is not a
mandatory all-library export prerequisite.

Date: 8 October 2026. Companion to the [master plan](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md).
Status: **settled N−1 design; production remains stopped.** This chapter specifies
the finite representations, owner-local fields and conversion algorithms to
implement after the human resumes production. It does not authorize runtime work.
The Fireball [proof receipt](audits/ndclient-plan-20261008/FIREBALL_PROOF.md) records
the bounded implementation already measured. Its remaining visual, delivery and
integration limits become production acceptance in N1/N3/N5; they are not open
schema choices or a requirement to build another standalone demonstration.

The user explicitly rejects carrying the gigantic Python media representation into
the new client. Better shaders, extracted auxiliary data and static approximations
are permitted. Blood particles and ground effects are first-class cases too.
**Implement the contract below through the existing owners.** Keep original artwork
and source registrations as references, not mandatory runtime memory layouts.
N−1 records the design decisions. N0 exports/installs the complete selected library
alongside production integration; N1 implements shared rendering, N3 closes all
authored families, and N5 measures the integrated result. Usable media enters the
renderer immediately; unrelated conversion/packing is not a global prerequisite.
Design readiness is not achieved frame-rate or visual parity.

This supersedes the earlier requirements to reproduce Python's occupied-depth mean
algorithm and deliver every full-resolution XYZ plane losslessly at runtime. Keep
accepted appearance, physical intersections, chronology and disclosure. Do not
preserve a slow painter heuristic merely because it exists. Existing durations,
32 FPS spell samples, creature rates and semantic event playback remain unchanged,
except for the later explicit human request: the
[single-view Fireball proof](FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md) uses
selected v4’s 46 frames at 24 FPS over 1.916667 seconds. That handoff fixes the
implemented baseline: two real depth bands, eight bytes per layer texel, scene depth
and local depth peeling. Whole-effect receiving light now uses the same depth and
normals, independently of emitted light; no new texture or pass was required.
It does not authorize a library-wide FPS conversion.
The whole renderer follows this first-principles Pixi design rule, as specified in
the master plan. These expensive effects were the first proof workload, not the only
families allowed to depart from Pygame internals. Do not treat "cheaper Python path"
as the brief: decide the needed visual information, then its simplest GPU expression.

## 1. What is measured and what is only source evidence

The [occlusion mathematics/Pixi chapter](NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md)
specifies the operations, depth reconstruction, transparent-layer limitations,
shared wall geometry, actual API path and numerical/library evidence. The finite
assignments and formats below settle the earlier candidate discussion. Godot is
an offline source owner, not the runtime.
In particular, gameplay/disclosed cell sets are not visual alpha masks, and Globe
and Antimagic remain separate native-driven suppression cases. The identified
Antimagic attribution gap is repaired at its existing owner before relying on a
specific boundary response. This is not a new protocol or suppression system.

The existing October 7 GPU/media study provides the following **historical**
measurements, not new browser results. Sources are
[the study](GPU_RENDERER_AND_MEDIA_READINESS_2026-10-07.md) and its private
`.runtime/playtest-recovery-20261006/gpu-proof/{working_set,packing-audit,result}.json`.

| Observation | Design implication |
|---|---|
| Four selected Fireball impact camera banks: 3,567,450,592 decoded bytes; 632,914,618 archive bytes | Complete bank data is not a reasonable active-effect allocation. These are full-bank totals, not a measurement that all four banks are simultaneously GPU-resident. |
| Same packets contain 1,297,254,016 RGBA bytes, 1,945,881,024 XYZ bytes and 324,313,504 ownership bytes, plus 2,048 header bytes | Geometry/ownership account for about 64% of decoded data. Colour is still large after removing them. Values calculated from the existing audit's dimensions, not a new decode run. |
| Exact zero-border crops retain 2.88 GB; sparse 32px blocks estimate 2.01 GB for those four banks | Better packing alone does not solve the representation. Sparse figure is an estimate, not a working codec. |
| One source component expanded into 159 copied CPU pieces at 163 peer cuts | Avoid a draw/copy expansion for every nearby particle or object. |
| Isolated resident-frame GPU proof: GPU p95 about 0.53 ms; feeding the complete impact took seconds, with >50 ms upload stalls in both streaming probes | Shader arithmetic and delivery/working-set costs must be measured separately. This proof does not validate full-scene transparency or browser performance. |

Blood has source-confirmed amplification, but **no isolated blood timing has been
established in this pass**. Do not invent a percentage of frame time:

* `game/particle_media.py:sample_region_particles` evaluates trajectories repeatedly
  from the same source, targets and schedules. The current blood template has 56
  particles per region; critical copies can double it, with additional vapor.
* `game/blood_draw.py:blood_particle_image` allocates and rasterizes a new Surface
  per live droplet per sampled frame. `animation_draw.py:action_media_draw_commands`
  creates individual commands; vapor creates more little images.
* `game/surface_residue.py:geometric_residue_image` includes changing landing fractions
  and response ages in texture keys. During landing/response animation it rebuilds
  fields, noise/shading and projected tile images. Settled fields do have caches;
  the problem is not accurately described as every stain being rebuilt forever.
* Those projected image keys include camera quadrant, zoom and light multiplier.
  Reusing source coverage independently of camera/light avoids that duplication.
* `game/deposit_draw.py:deposit_draw_commands` scans supported cells, creates masks
  and copies cropped pieces of airborne registered material. This shares the
  volume-expansion problem; ground spills must not inherit that implementation.
* `game/app.py` and `deposit_media.py:observed_deposits` collect residue membership
  from retained tiles while drawing. Derive and update these batches at displayed
  fact commits, rather than walking the entire retained map every display frame.

Profile native damage/deposition separately from presentation compilation, sampling,
GPU submission, fragment work, decode and upload. GPU work cannot fix an expensive
native residue update. Keep the server's existing typed facts and mechanics owners.

## 2. Finite representations and complete family assignment

Use three geometry families: registered planes/meshes, analytic ellipsoids and
paired scalar-depth media. They feed the same physical point/depth/material path.
There is no volumetric raymarcher, fluid simulation, runtime XYZ fallback or
spell-specific renderer. Eight bytes per band texel remains Fireball's contract;
planes and ellipsoids need no per-pixel geometry texture.

Radial explosions, globes and directionless clouds use one shared view-facing
appearance bank. Preserve world anchor, extent, source scale, phase and physical
composition; random smoke/flame detail is deliberately camera-facing. Do not
screen-rotate a vertical plume or pair colour with another bank's geometry.
Directional cones, beams, walls and flow-directed effects retain their meaningful
headings. Source view selection is saved in existing `viewFacing`/bank bindings;
shared storage uses existing `ProjectileFrameLayer.parts`, not eight copied banks.

| Authored family | Chosen runtime representation |
|---|---|
| Selected Fireball v4 | Its two genuine near/far bands; paired radiance/opacity and depth/normal; shared SE bank, 46 frames at 24 FPS |
| Globe and Antimagic maintained shells | Existing distinct front/back appearances on near/far analytic sphere surfaces; actual native applicability still selects suppression, independently of shell artwork |
| Fog Cloud, Cloudkill, Stinking Cloud, Incendiary Cloud, Darkness, Insect Plague, Sleep | One shared appearance bank, per-source-frame fitted ellipsoid, two representative contributions using the transmittance split in §2.1 |
| Existing front/back radial Shatter and Sunburst | One shared view per existing component; fitted near/far ellipsoid surface registration; each original component contributes once |
| Ice Knife radial burst | One shared view with scalar depth for each existing normal/add component; blend components are not relabelled front/back |
| Burning Hands, Gust of Wind, Color Spray, Sunbeam, Sleet and existing directional cone/flow components | Retain directional banks/components and convert calibrated source XYZ to scalar depth; source floor components remain receiver surfaces |
| Thunderwave | Preserve all 18 authored components and their sibling order; scalar depth per component, not a fictitious single front/back pair |
| Wall modules, rings, force/ice constructions and procedural wind/thorns | Existing finite meshes/module placements and material operators; planar intact faces use registered geometry, sculpted/animated surface imagery uses scalar depth |
| Stone fracture with `material_rest_xyz` | Current scalar depth plus source-piece ownership and per-frame current-to-rest transforms (§2.4); rest coordinates are never interpreted as current camera depth |
| Ground magic, rune loops, water, settled liquid, contact shadows | Actual receiver plane/mesh with original animated appearance and existing material/footpoint registration |
| Ordinary flat projectiles, cast/condition/attachment sprites, small accents and markers | Registered plane/billboard with original bank, pivot, socket and blend; only the existing authored residual alignment is permitted |
| Noise ribbon, darkness mesh, plasma trail, orbits, intake, weapon trails, native mesh constructions and particle templates | Existing finite mesh/ribbon/analytic trajectory operators; no raster XYZ conversion or new effect framework |
| Modular/fixed bodies, equipment, terrain, ordinary walls, doors and props | The exact contact/face/depth assignments in §2.5 |

The source census found 186 `surfaceFrames` registrations in current binding
documents, including 24 `material_rest_xyz` fracture registrations. It includes
the preserved old Fireball binding and is not a new selected release count. N0's
existing selected inventory maps every exported registration to one row above;
unused originals remain provenance. No selected family is left for a later design
competition. Visual failures are defects against this contract, recorded and fixed
in the owning registration/export/render function during N1/N3.

### 2.1 Ellipsoid approximation and original appearance

For flattened clouds, source RGBA does not reveal a true depth distribution. The
selected approximation places two contributions at the quarter and three-quarter
points of each camera ray's ellipsoid chord. Given original linear premultiplied
radiance `C` and transmittance `T = 1 - A`:

```text
T_half = sqrt(T)
A_half = 1 - T_half
C_half = C / (1 + T_half)
```

Near-over-far reconstructs the unoccluded original C/A; additive pixels give C/2
and zero opacity per contribution. Both draws reference the same appearance page,
so colour storage is not doubled. Each representative point is independently
tested against scene depth and applicable exclusions. This is a two-sample visual
approximation, not recovered smoke density or continuous volume integration.
Preserve authored normal/add component order; do not interpret those blend modes
as physical front/back labels. Existing true front/back appearances use their
original C/A once each and never use the half-transmittance split.

The exporter fits one ellipsoid key per existing source frame, in registered
source units. Set centre to the valid-position bounding-box centre, initialize
radii from its positive half-extents, and multiply them by the largest normalized
radial distance so all valid source positions lie inside. A zero extent receives
half a registered source-pixel width in that axis. Uniformly enlarge the ellipsoid
until every occupied colour-pixel ray intersects it: the required factor is the
maximum, over occupied rays, of the minimum normalized ray distance to the centre,
with a half-source-pixel conservative margin. Occupied means any RGB or alpha is
nonzero for additive/combined radiance, and nonzero alpha for ordinary normal art.
Empty frames have no draw and no fitted key. Use the source frame's key directly;
do not interpolate geometry on a second clock. Normals follow the ellipsoid
gradient, with inverse-transpose transformation. Coarse internal structure and
camera-facing random detail are explicit approximations to review in N1/N3.

### 2.2 Exact existing-owner additions

All additions below are passive typed values at existing source owners. Defaults
preserve existing source files; the generated browser release resolves defaults
explicitly. The names below are the implementation contract, not examples of
several possible schemas. No new media, normal, material or timing registry exists.

| Existing owner | Additions / retained fields |
|---|---|
| `game/animation_types.py:ProjectileFrameLayer` | `appearanceEncoding: Literal["srgb_straight_rgba8", "linear_premultiplied_rgba8"] = "srgb_straight_rgba8"`; `radianceScale: Positive = 1`; `geometry: MediaGeometry \| None = None`; `receiving: ReceivingMaterial` with the defaults below. Existing source selection, `blendMode`, gain and depth fields remain. |
| `ProjectileFramePart` | `geometryFile: Identifier \| None = None`; `ownership: OwnerPlane \| None = None`. Existing `file`, `rect`, `offset`, `footpoint`, `colorMasks` remain the sole frame-region registration. A companion has identical page size, rectangle and offset. |
| `ProjectileFrameStorage` | `emitter: VisualEmitter \| None = None`; reuse existing layers and mutually exclusive source `surfaceFrames`, with no new release registry or duplicate phase definition. |
| `EnvironmentBankSource` / compiled `EnvironmentBank` | `surface_geometry_by_pose`, mapping existing pose IDs to calibrated plane/mesh registration; same source helper types as media. Existing pivots, ground origins, rows, sample times, frame/leaf sources and depth frames remain owners. |
| `EnvironmentDepthSource`, `PropDepthSource` / compiled `PropDepth` | `encoding: Literal["rg16le_contact", "rg16be_oct8_ray"] = "rg16le_contact"`; `geometry: RayDepthGeometry \| None`. Converted release uses the second value plus complete ray registration. Existing depth range, cells, rows, pixels-per-unit and `depth_frames_by_pose`/source resource addresses are reused. |
| `BodyRig`, `EnvironmentBankSource`, `ImageResourceSource` | The same `receiving: ReceivingMaterial` value for the owning drawable. Ordinary bodies retain their current contact/pose-socket geometry; no body depth map or new rig registry is added. |

`ReceivingMaterial` contains `enabled: bool = True`,
`diffuseReflectanceLinear: tuple[NonNegative, NonNegative, NonNegative]` and
`preserveEmission: bool = False`; reflectance defaults to `(0.18, 0.18, 0.18)`.
Ordinary baked sprites use enabled receiving with the world policy's conservative
response; combined Fireball radiance preserves emission. UI, text, head markers
and source-declared unlit layers explicitly disable receiving. Existing palette/condition/item
material recipes remain separate and unchanged in meaning. These fields describe
light response, not a replacement shader/material registry.
Resolve one receiving value per draw from its existing owner: rig body/equipment
layers use `BodyRig.receiving`; independent registered media uses its
`ProjectileFrameLayer.receiving`; environment banks use their bank value; ordinary
world images use `ImageResourceSource.receiving`. Do not stack these values or copy
them onto individual actors. Explicit unlit UI/marker roles bypass world receiving.

`MediaGeometry` is discriminated by `kind`, with exactly these passive variants:

* `plane`: normal and offset in local cells/height steps, plus the existing
  source-pixel/pivot registration. World point comes from ray/plane intersection.
* `mesh`: vertices in local cells/height steps, triangle indices, source UVs and
  stable face IDs. Environment faces additionally carry source-pixel polygons
  assigning irregular artwork overhang to its continuing plane; the polygon
  registration is visual and never changes native blocking geometry.
* `ellipsoid`: `keysByFrame` of centre XYZ and positive radii XYZ;
  `contribution: Literal["near_surface", "far_surface", "near_quarter", "far_quarter"]`;
  `colourShare: Literal["original", "equal_transmittance_half"]`.
* `ray_depth`: `depthRange: tuple[float, float]` with increasing finite values;
  `encoding: Literal["rg16be_oct8_rgba8"]`; `pixelToRayOrigin: Matrix3`;
  `rayDirection: Vec3` nonzero; optional `restTransforms` from §2.4.

All variants use `basis: Literal["camera_local", "object_local"]` and a finite
invertible affine `sourceToLocal` matrix. Matrix storage is row-major, multiplied
by column vectors; XYZ means source axes as registered, and host output is
`(world X, elevation H, world Z)`. There is no guessed axis permutation. Geometric
normals are local/source normals; transform by the inverse transpose and normalize.
`keysByFrame` and transforms are indexed by existing selected source-frame indices,
not elapsed times or a new frame count. A plane parallel to the viewing ray has
no intersection; its registered edge-on source coverage must therefore be empty.

`OwnerPlane` is a discriminated union with two exact formats:

* `kind="source_class"`, `format="r8uint"`, `file: Identifier`: raw one byte per
  texel, zero unowned, nonzero source classification codes retained byte-for-byte.
  The importer retains the source code meaning in its receipt; production tests
  membership/nonzero only where that is the current owner contract. It does not
  invent new world IDs or treat a missing owner as native exclusion evidence.
* `kind="rest_piece"`, `format="r16uint"`, `file: Identifier`: little-endian
  uint16 transport decoded once into an integer upload buffer; zero unowned,
  codes 1..65535 index the source-piece transform table. Every referenced code
  must exist in that frame. A single part has at most one ownership plane;
  rest-piece zero/nonzero also supplies fracture source ownership.

Both formats are unsigned integer GPU textures, nearest sampled, without colour
decode, alpha premultiplication, interpolation or mipmaps. If existing ownership
is exactly geometric validity, omit `source_class` and use depth code validity;
otherwise retain it. This is a deterministic exporter rule, not runtime guessing.

`VisualEmitter` stores position XYZ, linear RGB, nonnegative intensity and positive
range keyframes with `elapsedMs` on that **existing phase clock**, and
`interpolation: Literal["linear"]`. It has no own duration/FPS or wall-clock start.
Only disclosed occurrences instantiate it. Fitted source curves are converted
offline to this piecewise-linear form with maximum relative peak-intensity error
0.01; selected v4 retains its 0.44 s peak, 1.64375 s faint tail and 1.916667 s end.

### 2.3 Scalar-depth conversion, precision and paired validity

V4 establishes the packed runtime depth/normal format. Decode the geometry as raw
RGBA8: RG are big-endian depth, BA are octahedral normal components. Code zero is
invalid; valid depth codes are 1..65535:

```text
code = 1 + round((t - low) * 65534 / (high - low))
t = low + (code - 1) * (high - low) / 65534
Psource = O(pixelCentre) + t * D
Plocal = sourceToLocal * Psource
```

`pixelCentre` is the untrimmed source `(x+0.5, y+0.5)` obtained from the existing
part offset/rect and pivot. It does not change when cropped or repacked. Appearance
uses `C + (1-A)*background`; combined linear radiance is RGB times radianceScale,
including RGB at A=0. Do not multiply by opacity a second time. Ordinary sRGB
straight-alpha art decodes to linear and premultiplies exactly once for composition.
Current normal/add/screen blend meaning and palette ordering remain explicit.

For each legacy `camera_local_xyz` packet, decode its big-endian uint16 axes from
`PackedSurfaceFrames.bounds`, then use its position/reference-pixel/vertical scales
and component pivot to build the source registration. Project the source sample
onto its pixel ray:

```text
t = dot(Psource - O, D) / dot(D, D)
P_on_ray = O + t * D
```

Preserve source-declared registration/calibration guarantees. For a required
conversion, report reprojection and quantization error in source pixels and host
units, and inspect its effect on visible contacts and ordering. Do not impose new
universal pixel/cell/angle tolerances or repeatedly split ranges to satisfy them.
RG16's half-step bound is `(high-low)/(2*65534)` before the registered transform;
use that actual precision when choosing a range. Keep channels finite and never
clamp out-of-range geometry silently.
Normals use source normals when delivered. Otherwise derive them offline from
adjacent reconstructed positions on the same continuous component/piece, preserving
registered boundaries. Where that neighbourhood does not define a stable surface,
use the registered face/card normal. Any discontinuity threshold is source-specific
calibration, not a renderer-wide requirement. No source normal is inferred to be a
physical smoke scattering normal.

Nonzero source appearance without native geometry keeps its original pixels and
uses bounded continuation of its nearest valid tangent plane, at the **same colour
pixel's ray**. The selected v4 retains its delivered fringe treatment unchanged.
Other conversions require a <=16-source-pixel continuation distance, with count and
maximum distance recorded per frame. No valid source normal/plane within that
distance is an export failure requiring source-registration repair, not permission
to omit artwork, borrow another bank, silently expand the bound or ship XYZ.
At uncut whole-source rendering those pixels remain visible; source ownership,
where required for material/native section cuts, stays distinct from this proxy
geometry validity. Geometry padding is always invalid; appearance padding is zero.

### 2.4 Stone fracture: retain rest-space cuts without rest-XYZ planes

`devtools/export_solid_fracture_rest.py:raster_material` already evaluates source
mesh triangles and `ownerLocalTransform`, producing both rest and current positions.
Its current packer stores rest XYZ and discards the returned current positions.
Extend that exporter to retain the winning source-piece code and current scalar
depth. For the same reconstructed current point:

```text
P_rest = M_rest * inverse(M_current) * P_current
```

`restTransforms` is an array indexed by `rest_piece` code, with immutable source
piece identity and `currentToRestByFrame: Mapping[sourceFrame, Matrix3x4]`.
Use the original captured transform and original spawn/rest transform for each
piece, including source object scale; check determinant/non-singularity offline.
Apply this transform to reconstructed `Psource` before `sourceToLocal`; convert
the captured row-vector transform convention offline to the declared column-vector
runtime matrices. Transform rest and current positions into the registered host
basis separately before the material-cut and current-depth tests respectively.
The shader obtains all three rest coordinates for the existing native removed-cube
test in `game/construction_media.py:_section_mask`, while camera depth and lighting
use current coordinates. Keep source ownership invalid where the source had none.
This adds two bytes per owned raster texel and a small transform table, not six
rest-coordinate bytes or a new rigid-body runtime. The source's 24 fracture pieces
are a bank fact, not a renderer-wide piece limit.

### 2.5 Ordinary body, wall, door and prop geometry

Bodies/equipment are registered vertical billboards at their existing ground-depth
contact, with all owned layers sharing that plane and authored sibling ties. Reuse
`BodyRig.pose_sockets`, including `ground_depth`, rest anchors, full-cell clip
registration and presented contact/elevation. A prone/corpse crop cannot move the
depth plane. This deliberately retains flat body geometry and baked shading; it
does not claim a volumetric body or fit a capsule from rules creature size.

Floors, raised supports and slopes use disclosed native support geometry. Grid,
ground feedback, shadows and settled materials lie on their actual receiver.
Regular walls use asset-calibrated front/back/top/end faces in
`EnvironmentBankSource.surface_geometry_by_pose`. Source-pixel face polygons assign
irregular stone overhang to the same continuing plane; original source alpha owns
the silhouette. Native displayed geometry independently owns finite physical
blocking. Adjacent collinear pieces share receiving faces, with no internal end
normals. D1's 0.25-cell thickness and height 2 remain D1 calibration only.

Doors use the authored leaf pose/frame and separate frame/insert/leaf sources.
Retain existing pivots, ground origins, `selection_masks_by_pose`,
`aperture_masks_by_pose`, release/state-change frames and parent-destruction variants.
An open aperture has no invisible solid rectangle. A faded wall's visual alpha
does not change its native blocker. Irregular props and animated destruction use
their existing depth companions converted to the common scalar-depth format.

That conversion must account for the source's **different encoding and meaning**:
`game/fixture_depth.py` reads environment depth as `R + 256*G`, not v4's big-endian
RG. Decode the existing contact depth with its bounds, multiply by
`pixels_per_unit_by_pose * asset_scale`, and include the existing ground-origin
versus mounting-pivot depth offset. Convert that registered ground-depth pixel
offset to host `d=X+Z` with the host 32 pixels per unit; use the source pixel's
unzoomed pivot-relative `(u,v)` to reconstruct:

```text
X = (d + u/64) / 2
Z = (d - u/64) / 2
H = (32*d - v) / 64
```

Then encode the shared ray depth/normal. Source code zero takes the existing
contact-plane registration, not arbitrary zero world height. Validate selected
doorway/prop contact landmarks against the original calibrated projection. Source
`actor_depth` is calibrated contact depth, not an already-compatible camera-Z map.

### 2.6 Owners, temporal pages and clocks

The implementation extends these owners; paths below name functions/modules to
change after resumption, not changes performed by this planning pass:

| Owner | Required work |
|---|---|
| `game/animation_types.py`, `game/environment_art.py`, `game/world_binding_types.py`, `game/asset_types.py` | Define/validate the passive additions above and retain current authoring/registration ownership. Shared geometry/receiving/ownership helper values live in the existing lower-level `asset_types.py`; higher-level source owners import them statically. `asset_types.py` must not import `animation_types.py`, which already reaches it through `condition_media.py`. |
| `game/animation_data.py` and existing environment/world loaders | Resolve the same authored IDs, fields and defaults; validate compact companion closure without loading textures. |
| Existing media conversion and packing tools | Reuse accepted media directly where supported. Implement required scalar/ellipsoid conversion at its existing owner; use the existing repackers only for actual texture/access constraints or measured delivery improvements. Preserve timing/views; do not duplicate the tools or turn conversion into mandatory repacking. |
| `devtools/export_solid_fracture_rest.py:raster_material`, `pack_material` | Emit current depth, source-piece ownership and captured current-to-rest transforms from the existing source geometry. |
| `devtools/pack_environment.py` | Preserve colour/geometry page registration and convert calibrated environment depth; export authored face registrations with the same banks. |
| `game/presentation_export.py:export_catalog`, `game/export_schema.py:export_schemas` | Export the complete existing-owner catalog/resource closure and generated declarations once, including tool-only provenance separately; no raw Godot manifest parser in runtime spells. |
| NDClient `src/presentation/` and `src/render/` | Existing master-plan compiler/sampler produces passive draws and release/receiver buffers. Shared registered-media, geometry, material, resource and particle/deposit functions consume them; Studio calls the same functions. |

Reuse accepted independently addressable frames/pages under the master's §7.1
resource policy. Respect the actual device texture limit; a source that exceeds
it can use existing lossless `ProjectileFramePart` registration. Do not split usable
frames to meet a made-up byte budget. Where packing is justified, use one aligned
layout per band for appearance, depth and ownership, preserving pixels and offsets.
Shared sources and in-flight work have one owner. Avoid eager whole-animation
multipack loading. Ordinary colour sheets retain their existing image path;
combined radiance and numeric planes retain lossless raw-byte loading. No blanket
packing, GPU-compression or asset-size optimization campaign is required.

The single resource owner pins coupled appearance/geometry/ownership through the
last use, with current demand and byte-budgeted lookahead across all active ages.
Decode/upload readiness is atomic for each pair/companion closure; a seek changes
speculative demand without evicting another occurrence's active page. Release at
source granularity; retain CPU raw-buffer costs in accounting. Measure the combined
active set and actual memory pressure before choosing cache policy. No per-cast or
global CPU/GPU quota is prescribed. Current demand takes precedence over speculative
loads; resources still in use are never evicted to satisfy an arbitrary number.

Existing phase FPS/duration, `timeMap`/`timeMapsByFacing`, environment sample times
and SpatialMediaBinding windows remain the only clocks. V4's `sampleTimesSeconds`
and ticks are **original capture provenance**, reaching 1.979167 s. Playback uses
its 46 `intervalSeconds` at 24 FPS, ending at 1.916667 s. Preserve this distinction;
do not replay its source simulation timestamps as presentation time. No other
family receives Fireball's 24-FPS exception. Camera changes reproject/reselect the
registered view without advancing time or duplicating decoded pages.

## 3. Physical composition without repeating the Pygame explosion

One shared projection and local spatial index selects the actual overlapping
supports, walls, apertures and effect proxies. Compact fields/geometry come from
the **displayed disclosed state**, not the latest state or private native map.
Scene depth handles camera occlusion; support/aperture and spell-volume policy
handles physical clipping. These are separate from native propagation and fog.

Use the shared solid colour/depth pass and registered geometry for opaque receivers.
Existing 2D pictures need registered contact/face
geometry; enabling WebGL depth testing alone does not supply it. Keep transparent
parts out of opaque depth writes. Clear/reuse depth resources correctly, including
camera rotation, door animation, wall cutaway and raised floors.

Transparent walls/domes, two overlapping clouds and actors inside them require an
explicit finite layer/order policy. A single nearest-depth buffer cannot solve all
transparent intersections. Use directly ordered contributions where valid and the
selected local depth-peeling path at crossings, with separate selection attachments,
stable ties and finite conservative bounds. Section 2 fixes each family's geometry;
N1/N3 validate those representations in the production compositor.
Do not multiply a large volume into one pass per droplet. Do not reproduce Python's
alpha-dependent mean-depth sort using GPU readbacks or huge prefix-statistics tables.
Retain authored sibling order, blend modes and complementary-frame mixing.

Soft intersection fade may hide a hard physical seam; it is visual treatment, not
permission to flow through a closed wall or to treat every magical dome as solid.
Use the received/authored blocking and suppression policies. No new client collision
or spell propagation rules. Static approximations are disallowed where they remove
door openings, create stale blockers or move a floor contact.
Keep established field membership independent from later occlusion changes:
`resolved_occupancy` does not authorize recomputing a cloud's native spread when a
door closes. Stable source-owner mapping and explicit upper-only height permissions
survive the representation change. Actual disclosed three-dimensional exclusions
and native suppression remain effective. An absent affected/visible floor-cell
entry is not an exclusion volume and must never punch a hole in admitted artwork.

Keep the accepted continuous visible Fireball/cloud silhouette. **Do not mask each
pixel by whether the floor tile underneath it is visible**: that caused the user's
cut-off clouds and serrated domes. Preserve the source's distinction between an
admitted upper effect and a disclosed receiving floor. Nor may a proxy invent an
unknown room, unseen target, damage outcome or independently hidden effect fragment.

## 4. Blood: compact trajectories, shared landing, settled appearance

Use existing `WorldParticle`, `LandingTemplate`, `ReleaseFamily`, `BloodResponse`,
`MaterialDepositSource` and `TileResidueState` as the source of truth. No new blood
gameplay system, one entity/class per droplet, simulation tick or JSON per particle.

### Airborne particles

1. At a disclosed release, expand only its authored template/admitted region into
   a compact reusable buffer: start/end positions and heights, delay, duration,
   gravity, size, tail parameters, appearance and stable identity. Precompute
   region membership, shape selection and landing schedule once per occurrence.
   Start at the presented body contact, including interpolated interrupted movement,
   rather than substituting the latest body's tile. Never invent receiving cells.
2. Evaluate position and tail from **absolute presentation time**. Ballistics are
   already analytic in `_flight_point`; they need no step-by-step GPU simulation.
   Use a shared batched mesh/vertex shader with camera/time uniforms. Existing
   scalar trajectory formulas can check numeric samples; this does not require
   implementing another production CPU particle renderer.
3. Preserve authored spray/ragged/bead/frozen shapes and damage-specific accents
   through a small shared shape atlas/mesh and finite material parameters. Camera
   rotation changes projection, not flight. Group draws by compatible depth/material
   batches; do not allocate images, filters or large-scene depth cuts per droplet.
4. Preserve critical copies, vapor, bone fragments and non-red creature fluids.
   First measure the real concurrent release counts. Do not impose a hidden particle
   cap or skip an attack/death event to reach a frame target.

Use shared Pixi Mesh/Shader instance buffers for these world particles so Z,
receiver contact and transparent world order use the same renderer. Do not add a
ParticleContainer adapter or a second CPU particle renderer for this family.

The compiler produces contiguous numeric buffers from existing templates:
source/goal XYZ, delay, duration, gravity, size, stable identity, response/template
index and fragment vertex range. No new canonical JSON particle schema is needed.
For local particle age `t` in seconds, preserve `_flight_point` exactly:

```text
Vxy = (goal.xy - source.xy) / duration
Vz = (goal.h - source.h + 0.5*g*duration*duration) / duration
Pxy(t) = source.xy + Vxy*t
H(t) = source.h + Vz*t - 0.5*g*t*t
```

`particle_schedule` retains family/response delay/duration scaling, the critical
copy's 1.08 duration factor and authored melt. The shader samples velocity for
the tail; preserves tail seconds/min/max, source snap and palette; and uses the
existing spray/ragged/bead shapes or frozen fragment mesh with cube-root shrink.
Vapor samples its original emission time on that same trajectory and then its
finite rise/drift/lifetime. Deterministic identities preserve detail flicker/shape
selection on backwards seek. Neither camera rotation nor draw frequency changes
flight or landing times.

### Landing and ground/wall effects

The flight and floor reveal use **the same schedule** (`particle_schedule` /
`landed_fraction`). A settled stain is not a lifetime collection of flying objects.
Transient appearance must meet the matching registered receiver at its landing time.
Critical copies add visible flight, not native deposited amount: the primary
template schedule owns the ground increment, matching current `landed_fraction`.
The decorative critical copy finishes its own 1.08-scaled flight at the same
receiver without a second contribution. Native amount/max_amount remain authority.

* Build coverage in floor/support or wall-face coordinates. Use reusable template
  kernels/masks; GPU drawing of a changing landing increment must not re-run all
  historical kernels on every frame. Keep fresh treatment separate from old blood,
  so a new fire/acid/frozen response does not recolour every existing stain.
* Retain settled coverage per local receiver/chunk, as an evictable material texture
  or geometry batch; update only changed contributions/supports. Use gutters/shared
  world sampling to avoid tile seams. Camera zoom/rotation and lighting are uniforms,
  not reasons to generate a second coverage field or repaint every stain.
* Animated ground magic, liquid shading and rune loops remain animated shader/media
  layers on the same support model. Do not cache a changing material as a static
  screenshot. Raised floors, slopes, floor holes and wall apertures are explicit.
* Native removal/replacement, known support destruction, visibility changes and
  backwards seek invalidate only affected derived chunks. Rebuild an evicted chunk
  from retained historical facts; do not rely on irreversible blend-once splats.
  Forward settles must not appear in an earlier displayed frame after a seek.
  Include neighboring cells needed for edge continuity and release/material revision
  changes in invalidation. Cold discovery shows settled deposits, not a fabricated
  discharge. Preserve the existing witnessed-break condition for deposit intros.
* GPU coverage is a cache, never authoritative residue quantity, gameplay collision
  or event history. Bound resident texture/buffer bytes; retain replay data separately.
  No per-frame synchronous readback or ever-growing full-map render texture.

Preserve existing ownership suppression: a contribution handled by deposit media
must not also draw through the generic residue path. Ground deposits may be shown
as seen memory where authorized; airborne deposit portions need current visibility.
Wall soot uses registered face UVs and marked-face ownership, never a whole-wall
colour change. These are shared material/depth rules, not per-spell exceptions.

The concrete cache layout is a 4×4-cell receiver chunk at 64 source texels per cell
plus one-texel gutters: a 258×258 field. It is keyed by audience/displayed support
or face identity, chunk coordinates, source/material revision and retained
contribution revision; camera/light/time are not settled-cache keys. Use R16F for
liquid kernel fields and R8 coverage for fragment masks. The shared renderer's
required float-render-target capability also covers this cache; an unsupported
device reports that capability failure instead of silently clipping field values.
World/support UVs and copied neighbour gutters avoid seams. Only actual receiver
membership clips ground coverage, independently from admitted upper effects.

Retain contribution descriptors from `TileResidueState`, `ResidueContribution`
and `MaterialDepositSource` in the displayed indexes. Reconstruct an evicted chunk
from those descriptors, never by replaying all historical injury events during a
draw. Reuse the exact template/kernel equations from `surface_residue._deposit_patch`:
`s = sqrt(landedFraction * contributionWeight)`, translate each kernel centre toward
its particle target by s, scale both radii by s, and add
`kernel.mass * max(0, 1-q/1.5)^2` for its rotated normalized squared distance q.
Handle s=0 as no contribution; fragment polygons use the same scaled vertices.

Keep a settled base field, active growing increments, and finite fresh-response
fields separate. Rerasterize only active increments while their fraction changes;
shade their sum once with the existing finite liquid/noise/response operators.
Do not accumulate each frame's fraction irreversibly. When growth finishes, merge
its full increment into the settled base; fresh response stays separately weighted
until its `surfaceSeconds` expires. Old blood is never recoloured by a new response.
Removal/replacement and backward seek rebuild affected chunks from the retained
prefix, including neighbouring gutters. The shared resource owner tracks their
resident bytes and evicts unused derived fields under actual memory pressure,
never facts or active contributions to enforce an invented quota. No per-frame
map scan, kernel replay for settled history, camera-specific coverage or GPU readback.

`game/deposit_media.py:observed_deposits` supplies the existing grouping semantics;
move its equivalent work to displayed-fact commits. `register_deposit_starts`
retains witnessed `ObjectDestroyedFact` plus authored environment release-frame
timing. Cold acquisition therefore shows settled material, without a fabricated
discharge. `game/residue_media.py:particle_schedule`, `landed_fraction`,
`landing_template`, `landing_point` and `target_cell` remain the numeric source
contract; `game/particle_media.py`, `blood_draw.py` and `surface_residue.py` provide
the retained formulas, not CPU raster/cache structures to transplant.

## 5. Implementation acceptance after production resumes

N−1 is this settled design. Preserve `.runtime/ndclient-fireball-proof/` and its
receipts as source/reference evidence; do not expand it into another required demo
track. The existing WSL NDClient and incomplete scaffold remain preserved. The
human must resume production before runtime edits, copying, packing, installs or
browser acceptance. This planning update performs none of them.

The accepted v4 example has 46 frames at 24 FPS and a bounded solid-wall/open-door
case using continuous native-authorized regions. Its 264 objective footprints do
not prove general geometry or private-stream integration. Historical v1 observed
no single-cast buffering but about 1.87 s with four distinct ages. V4's single-cast
hookup does not reattribute those v1 performance numbers or close concurrency.
Two representative bands, source-card normals, proxy fringes and calibrated coarse
walls remain explicit approximations. New ellipsoid clouds and ordinary-body
billboards are likewise approximations, not recovered three-dimensional artwork.

The master and [occlusion §1.1](NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md#11-native-reach-to-continuous-render-regions)
own the settled audience-safe reach/stage and typed suppression contracts. Their
implementation is required alongside this media work. No affected-cell stencil, connected-spread origin wedge, inferred hidden provider
or unbounded client propagation returns. Native line-of-effect areas use the
separate sample-labelled geometry partitions specified in occlusion §1.1.

| Stage / bounded work | Acceptance evidence |
|---|---|
| N0 source/export coverage | Every selected registration maps to §2 and its existing owner; preserve coupled dimensions, offsets, timing and registration. Complete dependencies alongside consumer integration. Required conversion serves that consumer; global packing is not a starting gate. |
| N1 common depth/material/resources | Four-camera raised-support/door/prop/body cases; exact unlit appearance and paired alignment across pages; opaque/fractional-alpha separation; first/repeated/four-age v4 playback; page-source sharing, seek and context restoration. |
| N3 all media families | Fireball, Sleep/Fog, each persistent-cloud material, existing front/back burst/shell media and directional beam/cone/sleet; every source frame resolves. Actors inside/near/far, source-rest section cuts and overlapping transparency use the shared renderer, with unoccluded C/T preserved. |
| N3 blood and receivers | Single/critical plus concurrent victims; flight/landing/settled phases; red, bone, non-red, frozen and vapor; old/new response isolation, support/wall membership, witness/cold-discovery distinction and removal/rewind/eviction. |
| N5 integrated stress | Blood inside large effects, bodies across a wall/door, two elevations, another transparent volume, animated ground material, pan/zoom/rotation and retained replay seek; long-fight memory and first/repeat/four-age media delivery. |

N1 snapshots and N3/N5 real-event cases use the one production reducer,
compiler/sampler, resource owner and renderer; Studio exposes those same inputs.
No extra test-only gameplay runtime is needed. Retain actual source screenshots
and sampled numeric cases as evidence, not another independently authored scene
release or duplicate animation compiler.

Report CPU preparation/submission, GPU elapsed, uploaded bytes/stalls, draws/peels,
HTTP/decode repeats/source creation, occupied/allocated page bytes and separate
compressed/decoded/GPU high-water marks. Record real concurrent particles and
active/settled receiver chunks. Use identical displayed histories/camera paths on
the Windows browser at 2560×1440, with 1920×1080 and 1280×720 checks. The full-scene
measurements follow the master's §11: responsive real play, first-use and repeated
casts, camera movement and resource lifetimes, with causes for observed hitches.
There are no inherited numerical pass/fail budgets or fixed-duration test rituals.
No silently dropped frames, effects, particles or transparent contributions can
make a failed measurement pass.

Missing/corrupt required registration or paired bytes fails export/admission.
Recoverable resource loading holds presentation at the last complete frame while
SDK ingestion/input continue. Only a track already authored with
`omit_optional_track` may be omitted. Unsupported required GPU capability reports
an explicit failure; no hidden painter fallback or lower-quality release is
substituted. A measured visual defect is repaired within its named source/export/
render owner and rerun against the failing case; this does not reopen a broad
representation competition or claim performance before it is measured.

The anti-slop reviewer checks finite scope, existing-owner/export/resource reuse
and the absence of alternate demo/registry paths. The anti-OOP/ECS/DAG reviewer
checks passive records/shared functions, static imports and no per-spell or
per-particle controller hierarchy. Reviews cover the design now and implementation
at N1/N3/N5. The [shared receipt](audits/ndclient-plan-20261008/PLAN_REVIEWS.md)
records their scope; plan approval is not shader, artwork or frame-rate approval.

## 6. Technical references

* [Pinned local Pixi Mesh guide](references/pixijs-8.22.0-20261008/guides/components/scene-objects/mesh.md)
  and [ParticleContainer guide](references/pixijs-8.22.0-20261008/guides/components/scene-objects/particle-container.md):
  available mechanisms, not proof of performance in this scene.
* [Official Pixi particle explanation](https://pixijs.com/blog/particlecontainer-v8):
  static/dynamic attribute costs and the distinction from full Sprites.
* [NVIDIA GPU Gems: off-screen particles](https://developer.nvidia.com/gpugems/gpugems3/part-iv-image-effects/chapter-23-high-speed-screen-particles):
  scene-depth comparison and soft intersections; this supports the selected technique,
  not an assertion that a single depth layer solves all transparent composition.
