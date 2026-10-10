# Fireball: single-view, 24 FPS export for the Pixi interaction proof

Date: 8 October 2026. Recipient: Godot artwork/export author, forwarded by the human.
The export request and standalone preview below are historical: the accepted v4
delivery and demo already exist. Reuse them; this document requests no new export,
demo or runtime work. Production remains stopped under the master plan.
No between-chat communication.

## Current default delivery — v4, selected 8 October 2026

Use **`fireball-single-view-24fps-v4`** for the standalone Pixi demo and planned
NDClient Fireball migration. The human supplied this replacement for the shorter
ignition. Preserve v1–v3 as historical deliveries. Engine/Pygame bindings are unchanged.

* Author delivery: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fireball-single-view-24fps-v4/HANDOFF.md`.
* Preserved private source: `/home/tommaso/Dev/neurodragon_art/sources/fireball-single-view-24fps-v4/`.
* Demo's physical ignored copy: `.runtime/ndclient-fireball-proof/media/fireball-single-view-24fps-v4/`.
* Manifest SHA-256: `192fa78c65c8cc1f574a317d64f78663898dbe49e0078b8ce756e8b3cc703061`.
* Runtime payload: 184 files, 26,675,421 compressed bytes. Both planes/bands keep
  the same channel, camera, pivot and normal-transform contract.

**Timing override to §3:** now **46 frames at 24 FPS, lasting 1.916667 seconds**.
The small ignition drops from six to four frames (source ticks 1,3,7,9); all eight
burst/collapse frames and the remaining tail stay intact. The retained pixels and
geometry are byte-identical to v3. Source ticks/sample times remain provenance;
play using the uniform frame index. Frame loading and retirement use the selected
manifest's frame count, FPS and duration, without assuming 48 frames/two seconds.

The selected manifest retimes its light curve too: peak at 0.44 s, relative
intensity 0.04 at 1.64375 s, zero at 1.916667 s. Receiving light, the inherited
v3 grey-ring repair and depth/wall shaders need no artwork/material changes.

Hookup check: all 184 paired payload files passed compressed/decoded hashes and
sizes. All 46 frames presented in order, with no page/HTTP errors or buffering in
one complete cast, and no contribution after expiry. Requests used only v4 media.
The solid-wall/open-doorway fixtures were captured in all four cameras. Evidence:
ignored `.runtime/ndclient-fireball-proof/v4-review/`. This checks asset replacement;
it does not expand the two-room reach proof into arbitrary-map acceptance.

Historical v3 hookup evidence stays under `v3-review/` (48 frames, two seconds,
manifest `018d1390ebb54cd1f641f582b2fb99030933e49e66d828c97ef04b19df54efa8`).
The v1 performance receipt also remains historical. The original specification
below is retained; this selected delivery's timing takes precedence.

## 1. What the human requested

Re-export the accepted Fireball as **one view, 24 FPS, eight byte channels per
represented depth layer**. Preserve the two-second impact, palette, scale-one
appearance, plume, smoke and intentional overhang. This deliberately supersedes
the earlier keep-32-FPS instruction **for this Fireball proof only**.

The companion runtime is a real interactive **PixiJS 8.22.0 / WebGL2** scene:
existing isometric grid, a few accepted floor tiles and walls, a Globe of
Invulnerability, and a few lights. Clicking a floor location casts there, so the
human can examine occlusion, dome intersection and lighting interactively.
Godot produces the export; it does not implement or substitute for that client.

“Eight channels” here means two RGBA8 data planes, **8 bytes per texel per depth
layer**. It does not mean eight float channels, eight views or eight layers.
The first delivery has **two genuinely separated depth layers**, near and far.
Thus two fully occupied layers total 16 bytes per ray sample, before cropping.
Do not hide this factor in the size report. The source's smoke/fire components
are blend components; they are not the requested near/far split.

## 2. Use this exact existing source

Read the existing source handoff and capture project:

`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fireball-surface-export/HANDOFF.md`

Use its accepted LeLu Fireball20ftGround scene and the **SE** capture bank with
the exact recorded source transform. The old handoff identifies the approved
`../source/lelu_explosion` donor and warns against the later generic working copy.
Keep source materials, palette choice and source import settings. Do not replace
the effect with a newly designed explosion. Preserve originals and current exports.

Known source registration: 1536×1536 untrimmed canvas; pivot (768,768);
orthographic camera (12,9.797958971,12), targeting the origin, size
25.455844122715707. The supplied grid coordinates are source coordinates ×2/3;
one grid unit is five feet. Export the actual numeric matrices as well as these
human-readable facts; consumers must not reconstruct matrices from bank names.

At source scale, relative to that pivot:

```text
u = 64 (X - Z)
v = 32 (X + Z) - 78.383671769 Y
```

The host uses 128×64 floor diamonds and 64 pixels per height unit. Its appearance
registration uses H = sqrt(6)/2 × Y. Keep this explicit in the source-to-host
matrix, with a corresponding inverse-transpose normal transform. Do not silently
stretch colour or compare stretched points to an unstretched dome.

## 3. Time, crop and scale

* **48 frames at 24 FPS, duration 2 seconds.** Simulate at the original stable
  144 Hz and sample once per output frame; do not run the simulation at 24 Hz.
* Use midpoint samples `sampleTime[i]=(i+0.5)/24`, i=0..47 (native ticks 3,9,...285).
  Frame i occupies playback interval [i/24,(i+1)/24). Include source times in JSON.
  Keep t=0 and t=2 reference images as diagnostics, outside the playback sequence.
* Preserve the actual impact/expansion/smoke progression. Sampling less frequently
  must not accelerate it. Record source phase/impact markers rather than inventing
  new gameplay event times.
* One source pixel at scale one stays one source pixel. No colour downsampling,
  additional pixelation, eight-view duplication, or arbitrary fitting to a cell.
* Crop only empty borders. Emission with zero alpha is **not empty**. Near/far
  layers may have different rectangles; each plane within a layer uses the same
  rectangle and pivot-relative offset. Do not trim away faint source content to
  meet a byte target. Keep source-size images only in the private reference output.
* A camera rotation in Pixi reuses this radial bank facing the camera. World
  geometry and depth transforms rotate together; do not rotate the flat plume.

## 4. Fixed channel contract

The two planes are byte data, not conventional browser colour images:

| Plane/channel | Meaning |
|---|---|
| Appearance R,G,B | Encoded premultiplied radiance C, including the source emission contribution |
| Appearance A | Opacity A=1-T, where T is scalar transmittance |
| Geometry R | High byte of quantized camera-ray depth |
| Geometry G | Low byte of quantized camera-ray depth |
| Geometry B,A | Octahedrally encoded normal, two unsigned 8-bit channels |

### Colour and transparency

Capture/compose each layer in a declared **linear colour working space** before
display conversion. Define its operation on a background B as `output = C + T*B`.
Smoke contributes opacity; additive fire contributes radiance with T=1. Capture
their contributions within the layer, retaining the source blend ordering.
Never force additive fire to become opaque to make it fit ordinary PNG alpha.

Use a positive **single scalar `radianceScale` for the entire effect**, declared
in the manifest. Decode `C=(RGB/255)*radianceScale`, `T=1-A/255`.
Choose the scale from the captured range; report quantization error and clipped
sample count (must be zero). This eight-byte representation is quantized, not an
assertion of lossless HDR capture. If the colour/palette comparison fails, report
that specific failure before changing channel count or silently clipping fire.
Do not vary the exposure/scale every frame to conceal clipped highlights.

RGB may be nonzero when A=0. Preserve those bytes through export, compression,
decode and upload. Do not pass them through a canvas/image routine that discards
RGB at alpha zero. Pixi uses raw byte uploads with no automatic premultiplication
or sRGB conversion; the compositor applies C/T exactly once and converts to display
colour once. The geometry plane is also raw: its A channel is a normal component.

The combined C/T represents the accepted lit/emissive appearance. It does **not**
separately encode albedo and emission, so do not claim we can independently relight
its smoke and flames from these eight bytes. Fireball stays self-emitting in the
proof; its light illuminates receiving floors/walls. Normal inspection is included.

### Depth

Use `code=256*R+G`. Zero means no represented sample. Codes 1..65535 decode as:

```text
t = depthMin + (code-1)*(depthMax-depthMin)/65534
P = rayOrigin(sourcePixelCentre) + t*rayDirection
```

Declare the orthographic ray origin function through a source-pixel-to-ray matrix,
unit ray direction, source units, and depthMin/depthMax shared across the clip.
Increasing t travels away from the source camera. Pixel centres use (x+0.5,y+0.5)
in the untrimmed top-left image convention; include a numerical decode example.
Do not export hardware non-linear Z or min/max depth normalized separately per frame.
Depth zero must not accompany visible C/opacity in the surface delivery. Audit this.
Geometry uses nearest sampling, no mipmaps, gamma conversion or lossy image codec.

### Normals

Encode a unit normal in the same declared source coordinate basis. Oct encoding:
divide N by |Nx|+|Ny|+|Nz|, fold the lower hemisphere, map the resulting xy from
[-1,1] to [0,255], round. Define sign(0)=+1 in the fold. Supply three known-vector
encode/decode examples so axis/handedness mistakes are visible before integration.
The consumer transforms by the inverse transpose and normalizes afterward.

Volumetric smoke has no unique physical surface normal. State whether this normal
comes from an actual contributing surface, a particle card, or the documented
fitted envelope. A proxy normal is acceptable if honestly labelled; do not call
it a measured smoke surface. The normal describes the same represented sample as
depth, not a separately sampled card elsewhere. The scale-one normal debug view
must remain stable across frames. Normals are not evidence of shadow visibility.

## 5. Actual near/far separation and bloom

Split **source contributions before final flattening** into two camera-depth bands.
For this first delivery use a fixed camera-depth split through the source origin;
record `splitDepth` and keep it fixed for the clip. Near/far each capture their own
C/T and representative depth. Do not copy the complete explosion onto both layers,
halve its opacity, or classify a flattened composite by its nearest old XYZ value.
The representative depth is the nearest contributing source surface in that band;
the audit records its limits. A band remains an approximation to its interior.

Recompose near over far using `C=Cnear+Tnear*Cfar`, `T=Tnear*Tfar`.
Show it against the unchanged source on black, mid-grey, white and checkerboard.
Depth separation can reveal incompatibility with source material draw ordering;
show the error instead of changing the accepted look unnoticed. Two bands are
the requested first representation, not proof of exact volumetric reconstruction.

**Do not bury screen-space bloom in fictitious surface coordinates.** For this
eight-byte delivery, export the two bands before screen-space bloom; keep intrinsic
soft particle coverage. Provide the existing bloom/glow settings and small source
reference composites. Pixi derives the halo by brightness-threshold filtering of
composited, visible radiance C through one shared bounded bloom operation. This
cannot isolate flame emission from smoke in the combined C/T format: it is a
documented bright-pass approximation, not a separately recovered emission channel.
This adds no per-frame ownership/XYZ
plane. It is an appearance approximation that must be compared against the accepted
source. If the bloom cannot be separated without a visible loss, document that
failure; do not silently add a ninth channel, erase the halo or reuse borrowed XYZ.

Shader exclusions act on actual represented points. A soft halo is generated after
its emitting contribution is hidden/suppressed; it can extend visually over an edge.
Neither opacity nor bloom may be clipped to affected/visible floor-cell diamonds.

### Globe companion: reuse its appearance, calculate its depth and normal

The human asks whether the same data is needed for Globe of Invulnerability.
It needs the same geometric answers, but **do not export an eight-byte geometry
bank for a regular sphere**. Intersect the camera ray with its registered sphere
or ellipsoid to obtain the near/far shell depths. Derive the sphere normal as
`normalize(P-centre)`; for an ellipsoid transform its gradient by the inverse
transpose. This supplies depth/normal to the same compositor without new maps.

Current `game/data/globe_media/{projectile-assets,bindings}.json` already registers
separate `globe.apply.back/front`, `globe.hold.back/front` and
`globe.response.back/front` appearance. Reuse those accepted assets and their
32 FPS clocks. The latest 24 FPS request concerns the new Fireball export only.
Select one radial hold/application view for the proof; impact response can retain
its existing meaningful direction selection. A directional response is not an
excuse to duplicate the entire steady globe.

**These inputs already exist; no Globe delivery is requested from the artist.**
The native `GlobeZone` in `dnd/spells/abjuration.py` has sphere radius 10 feet.
The existing projected protection carries its centre/anchor elevation and geometry;
`game/cast_media.py:cast_surface_volume` already consumes those values. The spatial
binding in `game/data/world_bindings.json` supplies `surfaceHeightScale` equal to
1.224744871391589, scale 0.5 and the rear/front media roles. The media catalogue
supplies a 448×448 source canvas and pivot (0.5,0.5), with 22 application frames,
128 looping hold frames and 62 response frames, all at 32 FPS. Reuse those fields
and the existing crop registrations. The Pixi client checks their projection as
part of its integration; do not request a duplicate globe-registration file,
new artwork, new normal/depth bank or second native sphere definition.

Visible shell geometry and the native exclusion radius have explicit registration;
do not inflate the exclusion sphere to fit glow. Preserve decorative rim/halo
overhang when fitting the visual shell. If the source actually deforms enough that
an analytic shell fails, show that specific comparison before requesting depth or
normal textures. The material/lighting debug mode can use its calculated normals;
the accepted magical appearance is not repainted just because normals are available.

## 6. Files and metadata to deliver

Create a **new** private sibling directory, for example:

`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fireball-single-view-24fps-v1/`

Do not overwrite the old Fireball export, game/assets, production manifests or
game/data. No public repository should receive the images or binary payloads.

Deliver:

1. `manifest.json`: version, source provenance/hash, SE view, rate/duration/sample
   times, untrimmed dimensions/pivot, both depth layer names, exact channel contract,
   radianceScale, depth range/split, normal provenance, source/camera/host transforms,
   source phase markers and bloom settings. Also the light curve described below.
2. `frames/near/0000.{appearance,geometry}.rgba8.gz` and the corresponding far/frame
   files through 0047. Each decompresses to row-major RGBA bytes, width*height*4,
   no header; widths/heights/crop offsets, byte sizes and SHA256s live in the manifest.
   Use gzip transport only; these are not eight-channel PNGs or float EXRs at runtime.
   Empty frames/layers are explicit zero-area entries with no payload.
3. `reference/`: small private images/contact sheets, the unchanged full source
   and reconstructed animation comparison, plus depth/normal diagnostics. These
   are not loaded by the runtime. No huge contact-sheet/EXR bank required.
4. `validation.json`: the finite checks in §8, compressed bytes, decoded bytes,
   maximum frame working set and counts; no claim that Godot FPS measures Pixi FPS.
5. `HANDOFF.md`: exact entry point, reproduction command, known approximations,
   any failed comparison and the location of the preserved originals.

This is a local proof delivery format, not a second game/SDK schema. On acceptance,
the existing media-registration owner gains only the selected representation fields;
the importer owns this file-layout adapter. No generic shader graph or asset DSL.

No atlas padding inflation is required for the initial per-frame transport.
For byte reporting use `8*sum(layerFrameWidth*layerFrameHeight)`; report the raw
full-bank total independently of the much smaller active-frame working set.
If every one of 48 frames used two full 1536² layers, it would still be 1.69 GiB
decoded: “one view” and “eight channels” do not make careless packing small.
Preserve colour resolution, crop honestly, and never preload that full decoded bank.

## 7. Fireball light and the Pixi preview owned by the client

Provide one compact authored light curve: time in seconds, source-local position,
linear RGB, relative intensity and radius in grid units. It follows the flash,
expansion and fade; use a few keys, not one light per pixel or particle. Record
whether values come from the source or are fitted. Do not add damage/light rules.
Globe shell/impact media, floor/wall art and optional existing projectile are reused
from the accepted client assets; this handoff does not request new versions of them.

The client proof has the following fixed scope:

* A small room patch at scale one with accepted floor tiles, a tall wall, low wall,
  doorway, raised support and the existing Globe appearance on an analytic sphere.
  Use registered surfaces; wall thickness, apertures and floor height are real.
* Pointer picking intersects those admitted supports. One floor click launches
  the existing Fireball travel art from a fixed visible origin, then plays this
  impact at arrival. No fake backend damage or new spell implementation. The
  existing asset is reused for travel; its original rate/socket/heading policy
  does not get changed by this impact-export request.
* Warm and cool lights plus the Fireball light show floor/wall receiving faces.
  Compute normals from those meshes. Use the same finite wall geometry for bounded
  light-visibility tests in this small proof, including door apertures. No CPU
  pixel loops and no light leaks through a finite-height wall; a light above it can
  correctly reach over. Camera depth alone is not the light's shadow map.
* Scene depth, reconstructed effect depth and applicable sphere exclusion are
  handled in the material shader. Native applicability is supplied by labelled
  existing fixture facts: admitted area exclusion versus unaffected application.
  Free placement is a **visual geometry probe**, not a replacement for spell rules.
  Do not make every visible dome automatically immune to all magic.
* Ordinary depth-tested solids, direct ordered transparency where sufficient,
  and **local depth peeling** for crossing transparent contributions. Reuse the
  stable-tie and finite-pass-bound algorithm in the linked mathematics chapter.
  Two Fireball bands and both Globe shell surfaces participate; nothing is cut
  on the CPU. Each nearest-layer selection pass writes its own current peeling
  depth attachment; final transparent accumulation does not write scene depth.
  An ordinary depth buffer is insufficient for these crossings.
* Depth, normal decoding, sphere tests and light evaluation can share one material
  program. **A single total pass is not an acceptance promise**: solid/depth input,
  transparent composition, shared bloom and UI have actual dependencies. Report
  draw/pass counts. Do not build a hardcoded full-scene raytracer just to claim
  “one pass”, or disable correct transparency/shadows to meet that wording.
* Minimal controls: click cast, pause/scrub/replay, Q/E camera rotation, toggle
  exclusion/light/debug views and a small FPS/frame-time counter. The grid is
  attached to the floor before walls/effects. No action bar, roster or server UI.
* Same effect-time sampler/material functions are retained for future Studio/play;
  scene setup and scripted fixture facts are the bounded proof harness only.
  No second ECS, event reducer or Python rendering path is introduced.

The requested layers and interactive preview were subsequently delivered, as the
current-default section records. Remaining production integration belongs to the
master plan after the user resumes it; no repeat artist delivery or demo is needed.

## 8. Finite acceptance — no open-ended validation loop

The original export checks below are retained as evidence of the channel contract.
The selected v4 manifest supplies its actual frame count; these are not instructions
to repeat delivery or revalidate the accepted export before client integration:

* Timing, crop/pivot alignment, eight-byte count, zero lost emission at A=0,
  no invalid depth under represented colour, source-edge contact and no clipped HDR.
* Source versus recomposed near/far on four backgrounds; report maximum/RMS linear
  colour/transmittance error and visually inspect birth, peak, expansion, smoke tail.
  Quantization and two-band errors are reported separately where measurable.
* Three known depth/pixel decode samples and normal basis vectors, with matrices;
  source-to-host registration reprojection error measured in source pixels.
* No tile mask, frame-duration change, hidden colour downscale or extra camera bank.

The client then checks the actual Pixi interactions: clear burst; tall-wall near
and far sides; doorway; low-wall overhang; raised origin; Globe disjoint, edge and
centre overlap; four camera rotations; multiple concurrent cast ages; lights
above/below wall top; pause/seek/replay. Include a retained floor visibility edge
under an admitted burst to prove that it does not cut the art.

Measure cold prepare/decode/upload separately from resident playback; report
CPU/GPU timing when available, missed frames, draw/pass counts and memory including
all depth/transparency/bloom targets. Missing GPU timer support is labelled.
There is no runtime readback to decide each frame, no source decode on every cast,
and concurrent casts share the same prepared frame resources. Measure **one and
four simultaneous casts with distinct start times**, not only four synchronized
copies sharing one frame. Report resident effect textures, decoded buffers,
intermediate render targets and environment textures separately; no arbitrary
cache allowance decides acceptance. Runtime residency shares identical frame
resources and prepares active/upcoming samples. Investigate actual buffering or
memory pressure without dropping effects or resizing art. Arbitrarily many distinct
cast ages can cover the full bank; current/next alone does not guarantee bounded
memory. Do not duplicate the bank per camera or retain every sampled age forever.

One anti-slop review and one anti-OOP/ECS/boundary review assess this contract and
later the measured proof. Reviews protect the finite scope; they are not a request
for repeated whole-client schema generation or an indefinite asset-quality gate.

## 9. References and review status

* [Mathematics, projection evidence and Pixi API source](NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md)
* [Integrated client plan](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md)
* [Media representation](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md)
* [Asset ownership/preservation](../ASSETS.md)

Contract review: **approved by independent anti-slop and anti-OOP/ECS reviewers**.
See the [bounded review receipt](audits/ndclient-plan-20261008/FIREBALL_HANDOFF_REVIEWS.md).
The current-default section and proof receipt record the delivered export, preview
and measurements. They do not claim full-client acceptance or authorize production.
