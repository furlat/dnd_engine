# Rendering geometry / XYZ audit — 2026-09-23

Read-only review of the current recovery branch. This report is the only repository
file changed by this reviewer. It covers registered media, world composition,
area clipping, object depth metadata and the boundary between authored geometry
and received gameplay facts. It is one part of the larger review; it does not
certify every reducer, importer or native rule.

## Conclusion

The new XYZ path is a real shared rendering capability, not a separate Fireball
executor. It consumes retained player observations and paired source pixels and
coordinates. The important architecture is sound: gameplay resolves outcomes;
historical presentation supplies observed geometry; a renderer clips and orders
the author's pictures. There are no native registry queries or synthetic damage
events in the modules reviewed here.

It is not yet an entirely explicit authoring contract. Storage format currently
selects some rendering behavior; different coordinate representations have
implicit conventions; image scale and physical coordinate scale must be kept in
agreement manually; and old wall artwork does not exactly fit its physical
occluder. These are specific cleanup subjects. They do not justify replacing the
timeline, building a general 3D engine, or rewriting already approved effects.

## What actually exists

| Representation | Current consumers | Ownership / placement | Deliberate limits |
| --- | --- | --- | --- |
| Ordinary registered RGBA billboard | Recipient healing, condition curtains, many finite spell tracks | Full canvas, authored pivot, crop offsets, body/ground attachment and authored back/front order | One billboard depth unless another representation is declared |
| Planar floor pieces | Persistent floor spells and liquid residue | Authored image cut into received cell ownership; each cell lends its observed support height | It is a floor picture, not a cloud reconstructed from screen pixels |
| RGBA plus raw XY footpoints | Liquid airborne splashes, persistent obscuring volumes | Each pixel has an authored world-ground owner; only disclosed owners are submitted; depth follows footpoint | No independently sampled height, so not a general XYZ occluder |
| RGBA plus XYZ plus ownership | Fireball, Burning Hands, Thunderwave, Gust, Shatter, Color Spray, Sleep mist, Ice Knife burst | Source-bank coordinates become world samples; supports, finite barriers and admitted protections clip samples; painter receives ground depth | One sampled surface per pixel/component, not a deep transparent volume |
| RG-packed horizontal depth atlas | Doors and enclosing trap/prop artwork | Each fixture pixel partitions around other submitted scene depths | Ground depth only; does not reconstruct a 3D object |
| Rear/front sphere halves | Globe's authored shell | Authored halves get near/far sphere depth; eligible incoming samples are excluded against the observed sphere | A sphere-specific composition policy, not arbitrary mesh intersection |
| Legacy planar area wall composition | Color-only area assets | Uses received boundaries plus actual wall/door silhouettes; an exposed rear face can receive a wall-contact slice | Ground-plane approximation; intentionally superseded by XYZ for the migrated effects |

These representations are not all duplicates. A flat puddle, a recipient curtain,
a doorway and a Fireball genuinely need different information. Requiring XYZ for
every one of them would add work without serving their current behavior.

## Coordinate and composition trace

1. `game/projectile_media.py:150` decodes requested packed frames only. A packet
   contains RGBA, XYZ uint16 values and ownership, with component ordering retained.
   Coordinates do not pass through tinting or color conversion. Sparse PNG parts
   and ordinary atlases continue through the same frame-loading boundary.
2. `game/registered_media.py:45` selects the facing pivot, retains full-canvas crop
   offsets and applies a common scale/registration. Shared rectangle edges are
   rounded, rather than separately rounding each band's width and creating seams.
   XYZ uses the same nearest sample indices as its picture. Residual screen
   rotation is explicitly rejected for XYZ (`:83`); authored banks own its views.
3. `game/cast_media.py:59` resolves source/target/area attachment. Source sockets,
   recipient body anchors and rest-pose offsets are authored values. In
   `:121`, the only protection volumes are providers already attributed by native
   facts and disclosed in player state.
4. `game/volume_media.py:153` rotates a camera-local XZ vector into world axes,
   adds recorded origin, converts source height once and adds support height.
   Compatible observed ramp/stair neighbors supply local support interpolation.
   Unknown terrain remains unknown, not an implicit height-zero floor.
5. Continuous propagation clips on observed barriers; camera-ray intersections
   clip against finite barrier heights; observed protection spheres exclude
   eligible samples. Alpha and RGB are both cleared so additive light cannot
   survive a clipped pixel.
6. `game/app.py:1417` consumes volume/area attachments before the ordinary painter.
   `game/fixture_depth.py:101` splits samples at overlapping external depths.
   Components belonging to one authored composite retain their authored order
   within common bands. This is the appropriate fix for smoke/fire flicker:
   independently sorting component mean depths would change the author's blend.

The projection is the existing isometric one: screen X is `64*(x-z)` and screen Y
is `32*(x+z)-64*height`, before zoom/pan. Consequently the camera ray direction in
view-grid/host-height coordinates is `(1,1,1)`. The constants in the XYZ code are
consistent with this projection. They should eventually use named projection
constants; their existence is not itself evidence of a tuning hack.

## Findings that warrant cleanup

### 1. Physical scale and image scale have no single typed registration owner

Evidence: `game/registered_media.py:57` scales the picture using caller `scale`;
`:90` scales decoded XYZ using `position_scale`. `game/cast_media.py:100` derives
picture scale from Studio scale and optional actor scale. The two values have no
declared reference relationship in `PackedSurfaceFrames`
(`game/animation_types.py:564`).

**Current data is consistent.** The current AoE banks use recipe scale `.5` and
position scale `1`. Color Spray uses `.44444444479166667` and
`.8888888895833333`, the same 8/9 correction on both representations. Camera zoom
correctly changes pixels without changing world coordinates. No current asset
was found with an incorrect ratio, and this review does not propose changing
the approved sizes.

However, changing a legal Studio `scale` field alone changes the visible footprint
while leaving its XYZ clipping/depth at the previous physical size. An XYZ media
track can also legally opt into `scaleWithActor`, with the same mismatch. None
of the current recipient healing tracks has XYZ, so the recent healing change
does not currently trigger this problem.

Minimal contract: declare the source projection/reference pixel scale together
with its coordinate unit conversion. Derive a single authored physical scale
delta for picture and numeric samples; apply camera zoom separately. Preserve all
current outputs exactly during migration. Do not turn this into a startup raster
audit or ask authors to update two independent copies of the same number.

Confidence: high architectural defect; no demonstrated wrong current scale.

### 2. Storage encoding is being used as a composition selector

Evidence: `game/animation_draw.py:763` sees `surfaceFrames` and immediately assumes
a ground-target world-volume effect, including `assert source.ground_target is
not None`. The sampled projectile's ordinary attachment and trajectory path are
bypassed. `game/cast_media.py:173` similarly treats the presence of coordinates as
the instruction to invoke world clipping. `game/spatial_media_draw.py:124` treats
an XYZ line specially inside `composition == "legacy"`.

All installed XYZ projectile phases are ground impacts; therefore the first
branch works for its current content. It is not a generic alternate storage
format for any projectile, despite that wording in the presentation document.
Installing an XYZ travel projectile or an actor-targeted impact through the same
otherwise valid storage record would either assert or attach it to the wrong
place. The newest Gust implementation also has to call itself `legacy` to reach
its modern path. Conversely `composition == "volume"` currently means XY
footpoints, not the new XYZ volume.

Minimal contract: explicitly separate **storage representation** from
**composition/attachment intent**. The existing finite/maintained records can
declare the small set already implemented: billboard, floor-owned media,
footpoint-owned media, world-surface media and split shell. No new executor per
spell is needed. Do not implement absent use cases merely because the vocabulary
can name them; unsupported combinations should be explicit at authoring time.

Confidence: high. This is a scope/typing defect, not a failure in all current
effects.

### 3. The old stone-wall raster and its physical occluder disagree at the cap

This was investigated beyond simply trusting a failing test. The old
`test_area_scene_occlusion.py` overwrites native wall height 2 with height 1 while
retaining unchanged wall art (`:89`). Its assertion that no opaque wall pixel may
change is also too broad for the newly approved physical rendering: visible wall
contact is allowed, and genuinely foreground particles can overlap a silhouette.
Those tests must not be blindly reinstated as the governing XYZ contract.

A second probe used an **unmodified native Fireball history**, actual height-2
stone walls and the complete historical support/solid snapshot. In camera 0,
267 opaque wall-cap pixels still change. Per-sample inspection explains why:

* Every retained smoke sample at those pixels is on the far side of the wall:
  world X `6.7966423..7.4992905`, wall plane X `7.5`.
* Its ray crosses that plane at height `2.0036075..2.254191`, just above the
  declared height-2 occluder. Fire samples give the same range.
* Thus the mathematical clipper is correctly treating the rays as above the
  native plane. The existing billboard cap occupies those screen pixels anyway.
  This is a visual/physical registration mismatch, not fire propagating through
  a blocked wall or an unapproved near-face contact.

The stone east raster has resource scale `1.0078740157480315`, pivot
`(128,207.36)`, scaled bounds `(104,73,98,173)` with blit origin `(-129,-209)`.
Its visible cap reaches higher than the zero-thickness edge's projected native
top. Camera 1 shows the same issue; cameras 2/3 in the probe do not.

Diagnostic files from this audit: `/tmp/xyz-wall-audit.png` contains bare,
composed and highlighted cap differences; `/tmp/xyz-wall-audit-capture.txt`
contains the sample coordinates. The durable measurements are above.

Minimal resolution: align the visual occluder registration with the authored
wall's actual cap/thickness while retaining its gameplay interval. This may be
an explicit small visual hull/registration or corrected artwork registration.
Do not change all gameplay walls to height 3 because that happens to hide the
pixels; do not globally mask every wall silhouette and thereby erase permitted
near-face contact. Preserve and separately test front/back contact, above-wall
samples, openings and all four banks.

Confidence: high for the measured cap mismatch. It is a bounded visible defect,
not evidence that the full XYZ system needs replacement.

### 4. Propagation and visual occlusion currently share one barrier set

`game/combat.py:255` and `game/spatial_media_draw.py:45` collect structures which
block **propagation**. `game/volume_media.py:170` uses that set both for area
reachability and camera-ray occlusion. They have different meanings. The native
structure already carries distinct optical and propagation channels; the render
input loses that distinction by flattening to one placement tuple.

The delivered opaque walls and large opaque props mostly use the same channels,
so this is not evidence that their current clips all fail. The limitation becomes
concrete for authored transparent/physical or opaque/nonphysical boundaries, or
for animation frames whose visual shape differs from their native blocking plane.
The native non-movement edge contract also blocks channels independently of
source elevation (`dnd/core/world_edges.py:79`), whereas the render propagation
slice removes barriers above/below the effect's origin (`game/volume_media.py:105`).
That difference needs a declared presentation policy before claiming general
height-aware equivalence with native reachability.

Minimal contract: keep received propagation topology separate from a visual
occluder representation. Use the data the observer already received; no new
objective queries. A full backend multi-Z or lighting redesign is outside this
review. Confidence: high code-level conflation; mixed-channel/raised-origin
gameplay failure was not reproduced here.

### 5. Screen-only hand correction picks a 3D interpretation implicitly

`game/cast_media.py:161` converts an attachment's screen displacement to
`(dx/TILE_WIDTH, -dy/HEIGHT_STEP_PIXELS, -dx/TILE_WIDTH)`. This is a valid
projection-preserving translation, but not the unique physical hand position:
all vertical screen displacement is called height and the ground-depth delta is
set to zero. Color Spray uses it after subtracting the authored baked emission
point. The source importer projects the original emission XYZ into a 2D point.

With one ordinary scale-1 modular actor, the current four views yield small
different world translations: approximately `(0.0026,.0587,-.0026)`,
`(.0389,.0879,.0389)`, `(-.002,.1188,.002)`, `(.037,.0867,.037)` in X/height/Z.
The screen alignment is intentional and source sprite hands are not exact 3D
reconstructions. This is therefore **not a demonstrated gameplay or visual
regression**. It is an important distinction for the typed contract: an authored
screen attachment correction is not a measured world-space socket.

Keep this modest, explicit approximation for the current approved effect unless
a clip demonstrates a defect. If future physical wall contacts require a true
world socket, preserve the source's 3D attachment metadata rather than reverse
engineering one from two screen values. Do not start rig keypoint authoring for
every animation as a consequence of this observation.

## Deliberate limits that are not cleanup bugs

* Single nearest surface per transparent component cannot reveal a farther
  particle when the nearest one is clipped. That information is absent from the
  asset. Keep the source's declared limit instead of describing these packets as
  complete 3D volumes.
* The painter partitions against other commands' scalar depths. It is not a
  per-pixel depth comparison between arbitrary interpenetrating translucent
  effects (`game/fixture_depth.py:110`). Existing actor billboards and separate
  near/far shells are designed for that model. Overlapping XYZ-vs-XYZ effects are
  not proven by the present single-effect tests. This is a coverage/representation
  limit, not authorization for a new renderer.
* Unknown sample ownership keeps original source pixels only in raw reference
  composition; active physical clipping clears unresolved samples. This explicit,
  tested policy avoids unresolved glow bypassing walls/protection/floors.
* Finite native outcomes and graphical fringes are not identical masks. Fireball
  uses native connected policy plus continuous observed geometry to avoid square
  stenciling; damage and Ashen still come from events. Gust's visual fringe uses
  received line ownership. No emitter is allowed to invent recipients.
* Whole-origin component ordering is mathematically necessary for source-over
  and additive materials. `world_depth_group` is an authored-composite concept,
  not a Fireball-name exception.

## Object metadata

The recent environment records are passive bank/state data, not a hierarchy of
behavioral renderer objects. `game/environment_art.py` declares finite banks,
door/open-state bindings, trap-state frames and destruction-bank mappings.
`game/environment_draw.py:48` correctly distinguishes the source ground origin
from its mounting pivot and the physical boundary's painter contact. That
distinction prevents moving hardware depth accidentally when the sprite is
mounted on an edge. Existing prop depth atlases feed the same splitter as other
world depth.

Some object authoring still uses manually decoded dictionaries instead of the
shared validated authoring models. The important missing model is not another
"object renderer" class. It is a clear record of reference projection, visual
origin, placement/footprint, frame timing, physical-clearance marker, and optional
occlusion/depth registration, with each field having one owner. Native damage,
integrity and channel changes remain events; authored release/clearance frames
control only when historical presentation reveals them.

The older stone/wood wall path still selects two materials and straight/corner
assets explicitly in `game/app.py:740`. That is a bounded older renderer, not
proof that the newly integrated 21 props each added custom code. Preserve its
approved corner behavior during any future registry unification.

## Performance / boundedness

There are no runtime SHA checks, source-package audits or broad startup raster
validation in these geometry modules. Decoding is demand-driven and the shared
decoded frame cache counts RGBA/XYZ/ownership bytes (`game/projectile_media.py:87`).

Do not call its 640 MiB source-cache ceiling a total renderer memory bound.
`field_cell` is a 512-entry LRU whose keys retain complete input surfaces
(`game/spatial_field.py:76`); environment frames and fixture depth arrays have
separate count-limited caches. Those are finite but not included in the source
cache metric, and can retain scaled pictures after source eviction. This audit
did not reproduce runaway memory or establish a frame-time bottleneck. Measure
retained raster bytes if this becomes visible; do not respond by adding an asset
validation framework.

XYZ composition is proportional to sampled pixels, relevant barriers and
visibility origins; depth splitting is proportional to overlapping command
depths. Support tuples/geometry keys are rebuilt or hashed for cached lookup.
These operations are actual geometry work, unlike the earlier file-audit mistake.
No claim of acceptable full-frame performance is made from source inspection.

## Evidence and cleanup order

Executed the existing XYZ and AoE-surface tests: **30 passed**. The following
legacy scene-occlusion group produced **16 failures** before I interrupted it
to investigate the repeated failure rather than rerunning the whole matrix.
The fixture-depth tests at the end of that command were not reached. The parent
review has a separate full-suite run; do not add this partial run to its totals.

The independent wall probe included real native events, full player-state
geometry, sample-coordinate inspection and visual inspection. Other findings
above explicitly distinguish code-level capability limits from reproduced bugs.

Recommended order, subject to the parent review's synthesis:

1. Preserve exact current clip inputs and authored visual values. Do not equate
   a previous passing test expectation with a newly agreed geometric contract.
2. Repair importer ownership and define explicit composition plus registered
   source scale/basis. These are small passive-data extensions; do not create a
   second animation language or runtime loader audit.
3. Migrate current packets/banks without changing their resulting pixels. Prove
   four-camera/color/XYZ registration and active vs quiet/lifetime timing.
4. Fix the measured wall-cap registration using the correct visual geometry;
   update old synthetic tests to cover physical front/back/above relationships
   and the allowed visible facade contact, rather than forbidding any overlap.
5. Name the remaining composition limits accurately. Add only the small missing
   cases needed for current content (particularly interacting depth-bearing
   objects/effects), not a speculative generic 3D test program.

The goal is to remove hidden ownership and assumptions while retaining approved
presentation, not to minimize every branch or force every asset into one format.

## Full-suite follow-up — 24 September

The root's selected game run completed with 2,052 passed, 206 failed, seven setup
errors and 15 deselections. This reviewer classified its 90 geometry/media
failures from the final traces:

- 64 foreground-wall cases use blanket opaque-pixel equality with the altered
  height fixture. The invalid broad oracle and the independently measured cap
  mismatch coexist; do not call every failure harmless.
- 25 rear-face cases fail the final ground-shadow-mask assertion. An elevated XYZ
  sample need not project into its ground shadow, and approved connected spread
  may pass through the open doorway. The old mask is not a general XYZ oracle.
- One Fireball storage test requires two allocated 1536×1536 surfaces. The source
  still declares that logical canvas, but the first E packet is cropped to
  650×324 at offset (-322,-166), and its tail to 1112×724 at (-566,-436). Other
  banks have their own crops. The 48 selected source frames and normal/additive
  components remain intact. Test registered color/XYZ/ownership and crop/pivot
  invariance, not full-canvas allocation or a hard-coded replacement crop size.

No further distinct runtime geometry defect was established by this failure
classification. Keep timing, component order and cache bounds in the corrected
tests. The main report records the remaining codec/archive/setup classifications.
