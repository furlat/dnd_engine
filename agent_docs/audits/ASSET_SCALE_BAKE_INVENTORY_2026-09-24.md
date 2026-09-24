# VFX production sizes and packing inventory — 2026-09-24

Read-only inventory for the production-packaging decision. No art, runtime code,
recipes, scale values, timings, decoder, or importer changed. This complements
the private-assets task's exact file/frame dispositions; it does not recompute
reachability or authorize deleting the full-resolution archive.

The important measurement is **effective pixel scale**, not the authored `scale`
field alone. `TILE_WIDTH = 128` and the selected root rig's `TILE_W = 64`, so most
VFX use `authored scale × 2 × zoom`. An authored `.5` is native raster resolution
at zoom `1`, not a reason to halve its images.

## Complete measured scope

Inputs are the initialized production owner graph and requests from
`/home/tommaso/.codex/worktrees/5b97/dnd_engine/.runtime/vfx-usage-audit`, augmented
with the active `condition-media.json` and passive image registrations because
the exported condition snapshot omits image scale/pivot. Byte counts come from
the existing file ledger/archive manifest. Only bounded PNG headers and the first,
middle and last selected XYZ packet headers per camera/component were read;
no source directories or full raster banks were scanned. A later bounded probe decoded the single512×512 palette-noise image in memory to compare two candidate resize paths; no image was written.

The machine-readable inventory is under
`.runtime/asset-inventory-20260924/vfx-scale/`:

| File | What is exhaustive |
| --- | --- |
| `owner-scales.jsonl`, `owner-scales.csv` | All 1,131 selected requests merged into 532 owner/asset/phase rows: 483 visible owners and 49 preload dependencies. Exact fixed factor, dynamic inputs, all five legal zoom factors/sizes, selected facings/frame windows, source canvas, candidate dimensions and draw-function evidence. |
| `asset-phase-scales.json`, `asset-phase-scales.csv` | All 332 selected phases across 324 asset IDs. Cross-owner factors, logical canvas/pivots, atlas/packet form, selected physical files/bytes, sparse crop bounds, XYZ bounds/component pivots/position conversion, representative source headers and packing recommendation. |
| `ancillary-scales.json` | 80 static condition attachment/facing references, 71 cast overlay references and one palette-noise sampler, four conditional body-release strips, and four procedural body-release owners. |
| `summary.json` | Counts, all non-unit scale cases, shared-size conflicts and dynamic-scale patterns. |
| `inventory.py` | Offline reproduction from existing ledgers; no engine initialization, hashing, full-image decoding, media mutation or runtime dependency. |

All selected owners were classified. Counts by owner family: 122 draft rows,
142 condition rows, 175 spatial rows, 72 deposit rows, 12 movement rows and nine
interruption rows. Counts include repeated assets for different roles; physical
file totals must be unioned, not summed across phases. In particular Fire Bolt
and Magic Missile reuse one physical sheet across phases.

## Fixed-size recommendations

These are logical canvas dimensions, **not occupied opaque bounds**. Sparse
parts retain offsets inside that canvas; rescaling the bounding box alone would
move the effect. `A` below is the historical actor's `visual_scale`, and `Z` is
camera zoom. The renderer permits exactly `.15, .35, .5, .75, 1.0`
(`game/projection.py:14,35`). There is no need to guess those zoom levels.

| Selected owner/asset family | Source canvas | Effective fixed factor before dynamic inputs | Concrete production recommendation |
| --- | --- | --- | --- |
| Fire Bolt prepare/travel/impact | 128×128 | 2 | Keep 128×128 source cells; approved output is 256×256 at `Z=1`. Baking an upscale adds pixels without detail or removing zoom work. |
| Fireball projectile | 256×256 | 1.2 | Keep 256×256; reference displayed canvas rounds to 307×307. Preserve phase-local residual rotation. |
| Fireball explosion | 1536×1536 logical; cropped packets | 1 | Keep native selected packets. No fixed-scale saving. This is the large eight-camera bank where frame selection removes source-only frames. |
| Acid Splash; Eldritch Blast; Guiding Bolt; Magic Missile | 256×256 | 1 | Keep native frame cells; atlas loose frames, retain authored timing and per-phase orientation. |
| Sleep projectile | 256×256 | 1.5 | Keep native256; displayed reference is384. No enlarged production derivative. |
| Sleep area | 813×389 logical; cropped component packets | 1 | Keep native selected geometry packets and their pivots. |
| Burning Hands | 512×512 | 1 | Keep native XYZ. |
| Gust of Wind | 1536×1024 | 1 | Keep native XYZ; maintained line and initial cast share registration. |
| Thunderwave | 256×256 | 1 | Keep native XYZ. |
| Ice Knife impact; Shatter back/front | 512×512 | 1 | Keep native XYZ. |
| Color Spray back/front | 768×768 | .8888888895833333 | Only unique-owner XYZ downsample candidate: approximately683×683 reference canvas. Keep768 until comparison proves acceptable registration/pixels at all zooms. Its world `positionScale` is already .8888888895833333 and must **not** be scaled again when resampling. |
| Shocking Grasp back/front, source-hand use | 384×384 | 1 | Keep384 source. |
| Same Shocking Grasp, small target-body use | 384×384 | .36 | Optional138×138 derivative, not a global replacement. Larger source-hand use still needs384. A derivative adds storage unless measured loading/rendering benefit warrants it. |
| Misty Step back/front, ordinary owner | 384×384 | 1 | Keep384 source. |
| Same Misty Step, Blur application | 384×384 | .7 × A | Optional269×269 reference derivative; actor scale remains dynamic. Source remains needed. |
| Same Misty Step, Mirror Image copy application/removal | 384×384 | .75 × A | Optional288×288 derivative. Source remains needed. |
| Same Misty Step, Enlarge/Reduce transitions | 384×384 | 1.3 × A | Keep384 source; no stored499×499 upscale. This is another reason not to replace the shared source with a Blur-sized bake. |
| Blinded/deafened/charmed/command/sleep condition sequences | 256×256 | 1.1111111111111112 × A | Keep256 source; displayed reference284. 44 owner rows are explicit in the table. |
| Silence application/sustain back/front | 768×768 | 1.2222222231770834 | Keep768 source; displayed reference939. This is world-sized, not actor-scaled. |
| Counterspell success/failure camera banks | 256×256 | 2 | Keep256 per-bank source cells; displayed reference512. |
| Counterspell dissipation mask | Asset's native canvas, listed separately | 1 at mask construction | Keep native mask. It is resized to the intercepted projectile canvas before crop/final projectile transform; it does not inherit the reaction burst's factor2. |
| All six liquid deposit materials, three variants, floor/air, application/sustain | 384×384 | 2 | Keep384 source; reference768. World geometry and footprint stay unchanged. All72 phase rows are recorded. |
| Remaining finite spell/condition/movement media | Per-asset exact values in332-row phase table | 1, plus explicitly listed dynamic factors | Keep the registered native size. No blanket half-size bake. |

Across the complete532-row phase inventory,381 already have fixed factor1.
Only14 rows have factors below1; four of those rows are preload duplicates.
The remaining137 use upscales. The small candidates are not a mechanism for
shrinking the multi-gigabyte persistent-field banks.

No compressed-byte savings are extrapolated from squared image dimensions.
PNG entropy, raw coordinates, sparse crops and duplicated physical files make
that misleading. Even a fractional single-stage nearest resize is not generally
equal to an offline resize followed by a second resize at fractional zoom.
The candidate dimensions above are rounded reference sizes, not permission to
replace authored scale with1 and forget subpixel registration.

## Dynamic dimensions that must remain dynamic

| Consumer | Actual executor formula and implication |
| --- | --- |
| Projectile raster phases | `phase.scale ?? projectile.scale`, multiplied by `2Z` (`game/animation.py:649`, `game/animation_draw.py:535`). Actor size moves source/target sockets; it does not resize the carrier image. Residual rotation can enlarge its screen rectangle; it is not a size to bake per target. |
| Finite Studio media | `track.scale × 2Z`, times`A` only when `scaleWithActor` is true (`game/cast_media.py:100`). Greater Restoration, Heal, Lesser Restoration, Mass Cure Wounds and Mass Heal enable this for both recipient layers:20 rows including preloads. |
| Registered condition media | `condition_media.scale × 2ZA` (`game/condition_draw.py:58`). Current horizontal actor stretch changes condition offsets, not registered-media image width. Preserve actual behavior in packaging; do not silently “correct” it. |
| Static condition PNG attachments | `AssetSpec.scale × ZA` vertically, additionally `visual_scale_x` horizontally (`game/condition_draw.py:86`). All80 selected entries have fixed image scale1; source native canvases and pixel pivots are recorded. This path has no extra factor2 for the image itself. |
| Persistent volume fields | `binding.scale × 2Z × radius/referenceRadiusFeet` for sphere volume composition (`game/spatial_field_media.py:51`). Cloudkill, Fog Cloud, Incendiary Cloud, Insect Plague and Stinking Cloud reference20ft; Darkness references15ft. Apply and hold canvases are896×896, fixed factor1. World XY footpoints and layer offsets scale with that same radius ratio. Do not infer a universal maximum actor/spell radius from a demonstration encounter. |
| Floor/clump fields; legacy sphere/line banks | `binding.scale × 2Z`; no automatic actor or sphere-radius resize. Floor/clump follows its recorded geometry/cell masking. Legacy sphere front/back uses radius for depth positioning, not image size. Suppression bursts use their binding's fixed scale through the stationary consumer. |
| Movement/contact tracks | `track.scale × 2Z` (`game/stationary_media.py:48`). A body-attached movement cue follows body position/height but does not add actor-size multiplication. `fitToMotion` changes time, not size. |
| Liquid deposits | `variant.scale × 2Z`; no actor/radius multiplier (`game/deposit_draw.py:48`). Disclosed deposit cells cut floor/air parts; geometry cannot be enlarged by baking pixels. |
| Blood/bone/corrosive/dread legacy release strips | 128×128 cells, fixed2, times`ZA` and horizontal actor stretch. Blood18frames; the other strips12. Needed when region data is unavailable or release is airborne. |
| Procedural body release | Four particle owners have track scale1. Their live world trajectories, droplet size and damage response produce pixels (`game/blood_draw.py:12`). No source image or atlas to shrink. Retain their data. |
| Cast-hand/rig effect overlays | Fixed2 then actor axes/zoom after body composition (`game/animation_draw.py:491`). Keep rig cells; exact per-rig file/frame inventory is owned by the rig review. Pixel sockets are registration data, not independent shrinkable artwork. |

There is no newly inferred beam-length stretch in the selected projectile
consumers. The existing Web cable is a separate affine endpoint-fit consumer
listed in the ancillary closure below. Ray of Frost uses its existing directional projectile media. If a
future beam explicitly scales by endpoint distance, that is a new runtime
input; it is not a current packaging assumption.

## Concrete packing groups

| Existing selected storage | Count of asset phases | Proposed offline production treatment |
| --- | ---: | --- |
| Sparse part atlas |247| Reuse the existing pages and exact part rectangles. First apply the private-assets dedup/disposition ledger. Do not unpack/repack merely to call the result an atlas. Any repack keeps offsets, common canvas, ordered blends and all temporal aliases. |
| Grid page atlas |61| Keep page addressing. Later partial-page compaction can remove unused cells only through an explicit remap of retained source samples; byte savings are not established by logical frame counts. |
| Legacy grid atlas |6| Three physical sheets: Fire Bolt5760×1024, Magic Missile11264×2048, Sleep projectile3072×2048. Keep source cells and registration; a production grid/parts mapping can split large sheets into bounded pages without changing playback. Do not resize cells to fill an atlas. |
| Loose color frames |8| Acid Splash travel/impact; Eldritch Blast cast/travel/impact; Guiding Bolt travel/impact; Fireball travel. All256×256. Pack per effect/phase/facing into up to2048×2048 pages, using current page/part metadata. At most64 full cells per page; smaller final pages are fine. Keep separate blend/material semantics and no padding-induced pivot shift. Exact existing grid-frame sampling needs no new universal packaging schema. |
| Loose component RGBA/XYZ/ownership packets |9| Burning Hands, Gust of Wind, Thunderwave, Color Spray back/front, Ice Knife impact, Shatter back/front, Sleep area. Preserve native cropped packets and component order first. An optional indexed file per effect/camera can bundle packets with bounded random reads. That needs a small storage reader; current storage is loose files. Do not imply a standard color atlas already supports numeric packet components. |
| Loose combined packets |1| Fireball explosion: retain the384 selected packets already identified by the private-assets task. Archive the unselected source frames. An indexed per-camera packet bundle can reduce file count without expanding crops to1536² or merging normal/additive components. |

The30 phases with raw XY are the12 persistent volume apply/hold phases plus18
liquid air phases. Their color and coordinate pages must be aligned. If duplicate
coordinate pages are shared independently of color, keep the association on each
part reference. Raw coordinate alpha is numeric data, not image transparency.
The other10 geometry phases use XYZ/ownership packets. Exact storage formats,
bounds and pivots for every one are included in the phase JSON.

A2048² RGBA page decodes to16MiB; a4096² page decodes to64MiB before any copied
frames/geometry. This is why the recommendation keeps existing atlases and
suggests bounded pages for the small loose frames, rather than building one
large bank per spell catalog. The current shared frame cache counts decoded
ownership at640MiB (`game/projectile_media.py:87`); changing that ceiling is not
part of this inventory.

## Registration and acceptance boundary

For a future fixed-size derivative, resample color, XY or XYZ and ownership with
matching source-sample identities. Retain numeric coordinate bounds, axis units,
`positionScale`, `verticalScale`, camera bank and component order. Do not multiply
world coordinates by the pixel-bake ratio. Scale pixel canvas/crops/pivots and
emission-point registrations together; leave world offsets and native occupancy
alone. The exact virtual scaled pivot can be fractional even when the stored
canvas is an integer size.

The registered path rounds **shared rectangle edges around a placed anchor**
(`game/registered_media.py:52`), not each part width in isolation. Nearest sampling
at different zoom/anchor subpixels can therefore choose different source pixels.
For color-only data preserve alpha/blend preparation order; for numeric geometry
never apply palette conversion, premultiplication or ordinary image filtering.

Production choices that preserve current pixels can proceed in this order:
use the measured frame/file dispositions, resolve exact duplicate storage, keep
native sizes, and pack loose color frames or existing packets through explicit
addresses. Small resized derivatives are a separate measured option. Compare
those only where useful against the same saved events and supported zooms,
including cross-owner Misty Step/Shocking Grasp uses; no broad new screenshot
framework or runtime source audit is needed.


## Ancillary owner closure

The final join exposed822 files that had only a broad “ancillary” owner label.
They are now explicitly resolved in
`.runtime/asset-inventory-20260924/vfx-ancillary/files.jsonl`, with a reproduction
script and summary alongside it. This pass reviewed826 files:822 production
files totaling6,973,637bytes and four source-only files. There are no unresolved
cases in this family.

| Files | Real runtime owner and selection | Size and packing |
| --- | --- | --- |
|733 Web field PNGs|`world_bindings/spatial_effects/spatial_effect.spell.web` remains active through `game/app.py:1324`. `game/choreography.py:504` binds observed creation; `game/assets.py:64` samples logical0..189 at288FPS, then holds189. Four camera poses resolve their source aliases.|Each existing cropped `AssetSpec` has fixed scale1, a pixel pivot, and its own native dimensions; all are recorded per file. Camera zoom is the only pixel-size multiplier. Per-camera color pages can preserve those crops/pivots. No XYZ companion and no factor2 rig conversion.|
|80 condition PNGs|Guidance, Light, Resistance and Shield of Faith supply64 selected facing images; Web-bound supplies16. Each active condition layer/facing owner is listed.|Fixed image scale1, then historical actor axes/zoom. These are already cropped images; keep pivots. Optional small atlas requires region-aware attachment loading.|
|8 Web tether PNGs|`game/sustained_draw.py:89` follows the current disclosed device concentration slot and muzzle/field endpoints. All eight authored facing choices are possible.|Transverse width is `AssetSpec.scale × zoom` (fixed1). Length is fitted to projected endpoint distance. Source sizes range from20×184/185 vertical to352×19/20 horizontal; four diagonals are256×133/134. Keep canonical crops and measured endpoints. No fixed cable-length bake.|
|1 palette-noise PNG|Active Chill Touch hit flash: `drafts/spell.chill_touch/damage/hitFlash/palette/noiseSheet`, through `game/animation_draw.py:445` and `game/spell_palette.py:49`.|This is a512×512 numeric red-channel sampler, **not a cast overlay**. The selected rigs sample it at128×128 or64×64 before recoloring body pixels. Keep512 source in the current package.|

The noise sampler supplied a useful concrete counterexample to naive baking:
using actual Pygame nearest resizing, `512→128→128` matches `512→128`, but
`512→128→64` does **not** match `512→64` byte-for-byte. Evidence is
`vfx-ancillary/noise-resize-probe.json`. Two explicitly selected128/64 derivatives
could preserve those separate sampled results, but substituting one128 image
for the current source would change the wolf's palette pattern. This tiny image
does not justify a new variant system on its own.

The phase aggregate now retains dynamic factor sets on each fixed-factor bake
candidate as well as per owner; it does not imply actor/radius inputs disappear.
A cross-review by the ECS/content reviewer checked the size formulas and raised
the sampler distinction, which is incorporated here.
