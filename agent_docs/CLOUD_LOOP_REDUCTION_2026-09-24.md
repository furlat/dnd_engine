# Shorter maintained cloud media

Subsequent approved five-cloud replacement and current measurements: see
[CLOUD_TWO_SECOND_INTEGRATION_2026-09-24.md](CLOUD_TWO_SECOND_INTEGRATION_2026-09-24.md).
The entries below retain the earlier sequence of work and renderer corrections.

User authorization: ship new VFX at 32 FPS, measure actual savings, and shorten
cloud loops. Finish the support-condition integration first. This follow-up
changes media storage and authored sampling windows, not native spell rules,
area occupancy, sensory behavior, propagation or rendering geometry.

## Existing contract and bounded implementation

The six maintained fields are Fog Cloud, Darkness, Stinking Cloud, Cloudkill,
Incendiary Cloud and Insect Plague. Their current color/paired XZ pages total
11,485,840,285 bytes. Four smoke holds are 28 seconds, fire is 16 seconds and
insects are 8 seconds, all at 144 FPS. `import_persistent_spells.import_volume`
already installs declared four-camera color/raw-coordinate pages. The runtime
already samples their explicit FPS and hold window with the existing XY volume
compositor. No new runtime codec, renderer, scheduler or generic resampler is
needed for a compatible delivery.

1. The Godot author creates actual periodic sources, retaining existing art and
   source projects privately. Current candidates: smoke 5.625 seconds (180
   samples at 32 FPS), fire 3.25 seconds (104), insects 6 seconds (192). These
   become production choices only after source validation: same shape, palette,
   density, apparent speed, four cameras and a clean boundary. Changing playback
   speed or truncating an arbitrary source interval does not satisfy this.
2. Export color and raw XZ from the same source timestamp into matching atlas
   cells. Preserve canvas, pivot, crop offsets, coordinate bounds, raw channel
   values and camera basis. Prefer direct 32 FPS export; preserve existing
   144 FPS originals and reproducible authoring sources. If incoming media is
   still 144 FPS, select source times jointly and repack the matched pair before
   import. The support billboard packer is not suitable for coordinate pages.
3. Preserve new delivery/source material privately. Install through the existing
   volume importer, with its twelve stable apply/hold asset IDs. Preserve six
   seconds of application for smoke/fire (192 frames at 32 FPS), and two seconds
   for insects (64 frames). Exclude the duplicated period endpoint from the
   runtime `[0, T)` hold bank. Update only the corresponding
   `world_bindings.json` hold frame counts/FPS and any explicit media-track FPS
   that actually references the replaced phases. Preserve scale, mechanical
   radius, application duration, removal fade/easing and movement speed. The
   current removal is 630ms smoothstep; moving clouds advance two cells/second.
   importer must not author those behaviors.
4. Compare decoded registration and paired bytes on selected source/installed
   samples and run existing volume/import/sampling/native replay tests. Review
   real saved-event captures for application and its join to hold, at least two loop boundaries,
   moving fields, actors crossing the volume, raised ground/walls and removal
   across four cameras. Use existing scenarios and capture infrastructure.
5. Measure encoded production pages after packing. Build the new private release
   by replacing exactly the prior file references of both phases of the six
   selected volumes (twelve assets). Retain any old file still referenced by another selected asset.
   Preserve old release tags/source archives; relocate obsolete installed pages
   privately so physical installation size reflects the new release. No blanket
   directory deletion, repository-wide hashing or startup validation is needed.

## Completion and review

Anti-slop review checks whether the existing importer/sampler already suffice,
whether measured savings correspond to a complete release, and whether native
events/semantics stayed authoritative. Anti-OOP/ECS review checks passive data
ownership, paired color/geometry, stable registration and reuse of the current
draw path. Both review this plan before implementation and inspect actual
changes afterward. Record measured sizes, test scope and reviewed captures;
do not call source pilots or hypothetical frame-count ratios release savings.

Both independent reviewers approved the plan after clarifying the twelve
apply/hold assets, unchanged application durations and half-open loop boundary.
Existing focused lane: `test_persistent_media_import.py`,
`test_spatial_field_media.py`, `test_spatial_field_movement.py`, and
`test_persistent_spell_gameplay.py`. Compare incoming and installed paired bytes;
old/new art pixel equality is not expected from newly authored periodic sources.

## Implementation and verification

All six delivered banks are installed at 32 FPS through the existing volume
importer. Only twelve apply/hold media records and six hold-window FPS/count
pairs changed. No cloud runtime, importer, backend rule, area geometry or
movement/removal implementation changed. Source exports and delivery audits are
preserved at `/home/tommaso/Dev/neurodragon_art/sources/short-cloud-loops32-v1/`.

The Godot source uses periodic cohorts, with paired color/coordinates sampled
at the same simulation time. The extra captured period endpoint is excluded
from the runtime hold bank. Four smoke loops are 5.625 seconds, Incendiary Cloud
is 3.25 seconds, and Insect Plague is six seconds. Application remains six
seconds for smoke/fire and two seconds for insects.

Both independent implementation reviews approved the result. Anti-slop review
matched all 8,144 nonempty paired frame references and their registrations.
ECS review decoded 144 selected source/installed samples across all six spells,
two phases and four cameras: 140 color/coordinate pairs matched exactly and
four empty frames remained empty. Runtime samples also preserved raw coordinate
alpha; it is not opacity. These are scoped checks, not an every-pixel baseline.

The four-file focused lane passes **59 tests**, with clean scoped typing. It
covers 32/144 FPS import, all six application/hold clocks, two half-open loop
boundaries, late observation, phase-preserving 630ms smoothstep removal, and
real saved Cloudkill movement at two cells/second and concentration removal.
Whole-game and changed capture-tool/scenario typing is also clean.

Long review cases retain the actual maintained field by omitting the scenario's
ordinary drop-concentration command. Their additional presentation tail creates
no backend turns or invented events. Existing lifecycle captures separately
exercise real removal, moving clouds, walls, raised ground and an upcast radius.

The independent reference ledger accounts for shared apply/hold pages and reused
filenames. Twelve old phases contain 16,597 pages / 11,485,840,285 bytes; their
replacement contains 1,702 pages / 1,443,158,147 bytes. No other current data
document references any retired page. Release assembly removes 14,985 obsolete
paths, replaces 1,612 reused paths and adds 90 new paths; old originals/releases
remain private. Exact evidence is in
`/home/tommaso/Dev/neurodragon_art/records/cloud-loops-32fps-20260924/`.

The [combined production review](http://127.0.0.1:8767/runs/20260924T093843Z-clouds-32fps/index.html)
contains **30/30 passing clips with zero reported gaps**: twelve long-loop
observer views and eighteen existing lifecycle/geometry views. Each video
contains all four cameras. The gallery links to original saved inputs, traces
and encoded videos without duplicating them. Rendered traces expose the actual
application-to-hold join and at least two complete hold boundaries. Production
frames at those boundaries and representative four-camera wall/height views
were inspected; this records agent review, not human artistic approval.

## Completed private release

Private Git LFS commit `11ec352cceaab1e89a6a96ffb26214d52e991ab6`, tag
`cloud-loops-32fps-20260924`, contains **10,116 files / 5,051,942,205 bytes**.
Both the actual installed tree and private production tree match the complete
manifest: zero missing files, extra files or size mismatches. This saves
10,042,682,138 bytes (66.53%) from the preceding support release. The six cloud
banks themselves shrink 87.44%; no reduction is claimed for preserved archives.
Older source exports, production Git LFS history and all retired installed pages
remain separate from the current installation. No game artwork is tracked by
the code repository. Private release records contain the matching public data
and identify the current uncommitted engine work; the old code base alone is
not a compatible checkout for this release.

## Subsequent correction: map-edge overhang

The human review identified a hard cloud cut at the outer map boundary. The
earlier passing capture checks did not cover that visual requirement. XY media
was partitioned strictly into received effect cells, so the absent exterior
support behaved like a wall even though no physical barrier existed.

The shared XY field renderer now lends an admitted edge cell's ownership and
height to its authored exterior fringe. It resolves bounds using displayed
coordinates, including cloud movement, and preserves original pixel positions
and world depth. A short owner-to-sample ray uses the existing received wall and
solid geometry. Exterior ownership is assigned once; ordinary in-bounds
admission, hidden cells, floor media and native occupancy are unchanged. No new
schema, backend event, spell switch or art export is needed.

Both anti-slop and ECS implementation reviews approved this bounded correction.
The regression fails against the previous renderer and passes with the repair.
The focused field suite passes 49 tests; movement, deployment, import and native
persistent-spell suites add 50 passes. Scoped typing is clean. Tests cover four
cameras, exterior edges/corners, raised/cold supports, translated clouds and
real boundary/solid blocking, alongside existing visibility and floor behavior.

The user also requested fresh wall and Globe review footage. Twelve new native
scenarios cover a real wall on the map edge, three other maintained cloud/wall
setups, three Fireball/Globe overlap directions, a wall opening with an active
Globe, and four cloud/Globe overlaps. Existing boundary, raised-field and corridor
inputs are replayed alongside them. All retain native events and paired observer
perspectives; no new native spell or protection behavior is introduced by these
capture scenarios. Globe and corridor footage uses the existing actor framing
mode to make the interaction readable. The original event sequences are retained;
only saved camera metadata changes for those closer replays.

Eight saved subjective-state checks confirm Fog Cloud, Darkness and Cloudkill
exclude the Globe's protected cells, while level-8 Incendiary Cloud overlaps them.
The existing Globe replay suite adds nine passing tests (108 focused tests total);
the expanded scenario/catalog/producer typing also passes.

**Observed visual limitation, not fixed by the map-edge correction:** lower-level
clouds still cut out the Globe using excluded tile ownership, producing a jagged
interior silhouette rather than a smooth sphere intersection. This is visible in
the new Fog Cloud and Cloudkill clips and labelled in the review. The caster can
also lose sight of the Globe's center while the protected observer still sees
its shell; both subjective views are included. Correct state/replay checks do
not make the interior silhouette visually approved. This correction intentionally
does not alter interior exclusion or discover hidden ground to hide that issue.

The [final 30-clip review](http://127.0.0.1:8767/runs/20260924T101505Z-walls-globe-clouds/index.html)
puts wall and Globe interactions first. All 30 replay checks pass with no reported
binding gaps; the interior cloud/Globe silhouette above remains a visual issue.
Each clip has four synchronized cameras and a paired observer. The map-edge
Cloudkill input is identical to the earlier capture; the frame near 7.2 seconds
now retains the previously missing exterior cloud pixels. Representative real
edge-wall, interior-wall, raised-ground, corridor, Fireball/Globe and cloud/Globe
frames were inspected. Close framing can let peripheral effect pixels leave the
viewport; original wide captures remain saved. The gallery reuses existing media
and traces rather than copying video files. Evidence and saved-state occupancy
checks are in `.runtime/cloud-edge-fix-20260924/`. No art release changed.

## Corrective integration: genuine XYZ and shield-surface visibility

The preceding gallery was rejected. Its checks missed foreground wall leakage;
calling the missing shield an acceptable visibility limitation was also wrong.
Packing kept X/Z tile owners but discarded native Y even though the source
exports had it. A lower frame rate did not require that loss. The correction
restores the actual source samples, rather than estimating height from screen Y.

All six cloud families now use the existing PackedSurfaceFrames contract and
SurfaceVolume compositor. RGBA, frame order, 32 FPS, phase duration, crop, pivot
and four-camera registration are unchanged. The importer only changes storage.
Explicit spatial bindings select xyz_volume. Their per-cell support partition
preserves native occupancy, unknown-cell admission and decorative map-edge
overhang; the final scene compositor applies actual wall/door silhouettes. There
is no extra DrawCommand format, spell-specific compositor or alternate Y guess.

Native footprint resolution now retains the actual protection overlap using
SpellSuppression. Observer projection supplies only disclosed provider geometry
and currently permitted overlap cells, including cold serialized replay. Cloud
pixels above/outside the sphere can survive in those columns without restoring
suppressed game cells. Before/after protection geometry remains active during
cloud motion; only after-state cells extend its after-state ownership stencil.
Provider removal preserves the existing resolved native footprint until normal
re-resolution, without querying a vanished protection or inventing a new rule.

The missing shield was a separate error: the renderer required sight of its
center ground tile. A currently observed cloud/protection intersection now
reports the active, already-known protection surface in visible_volume_positions.
The renderer submits that shell using its received anchor height and lets
geometry determine pixel occlusion. Hidden ground/actors are not exposed.
Unknown/removed providers, real walls and unrelated obscurers remain hidden.
Current surface evidence is required; merely remembering a shield does not draw
it. Camera-side cloud surfaces can still correctly cover parts of the shield.

Both independent anti-slop and ECS reviews approve the final implementation.
One review caught the departing-cloud loss of before-state exclusion; a real
saved-native regression fails the old seam and passes the repair. The shield
visibility regression also failed before its correction. Final-compositor tests
cover real walls, closed/open doors and both sides in four cameras, protecting
opaque pixels while retaining exposed cloud and open-doorway pixels. Small real
XYZ packets test fractional motion/cold/raised ownership without mistaking the
wide map's larger admitted footprint for the small map's expected pixels.

Validation lanes (overlap between lanes is intentional, not an additive total):

- 234 rendering/field/movement/volume/depth tests passed in 49.66s.
- 119 final field/visibility/ownership/import/native-receipt tests passed in 23.13s.
- 74 native attribution, shield visibility, Globe and sensory tests passed in 47.34s.
- Whole-game and touched native typing: zero errors.
- 144 representative production sampler comparisons: exact RGBA and placement;
  horizontal packet quantization error below 0.000062 world units. The delivery
  also checks every color frame and selected original surface owner.

The native Y source has finite 5/253-unit resolution. Packets retain one selected
rendered surface, not hidden rear layers or a complete volumetric density field.
This is sufficient for the represented surface's wall/sphere interaction; it
cannot conjure unseen billows behind a cut surface. This limitation is explicit
in the existing presentation contract, not disguised by a tile-mask fallback.

Private release `cloud-xyz-32fps-20260924` (`e19b33b1`) contains 8,438 files /
5,612,659,685 bytes. The 24 new archives total 2,003,875,627 bytes, replacing
1,702 old cloud page files / 1,443,158,147 bytes. Retaining Y costs 560,717,480
bytes; it does not restore the prior 144 FPS library. All originals, prior
production pages and complete new export are preserved privately. ASSETS.md
records the locations. Runtime does not scan, hash or validate this library.

Evidence, source snapshots, logs and selected review frames are under
`.runtime/cloud-xyz-restoration-20260924/`. The engine changes remain uncommitted;
the private art tag requires these corresponding public bindings/consumers.

The replacement [18-clip review](http://127.0.0.1:8767/runs/20260924T105442Z-cloud-xyz-shield-fix/index.html)
passes all native/replay checks with zero reported presentation gaps. It starts
with an explicitly wall-free map edge and a separate real wall at the same edge,
then the other cloud/wall cases, followed by four cloud/Globe pairs. Every clip
contains all four cameras; caster/target views are paired. Edge and wall inputs
are the original saved sequences. Globe inputs were freshly captured so the
native shield-surface observation reaches replay. The first XYZ-only capture
still exhibited the absent shield; it is retained as evidence, not delivered as
the fix. Final inspected Fog, Darkness and Cloudkill frames contain the shield
where the genuine cloud surface exposes it. Incendiary Cloud is the intentional
higher-level, unsuppressed control. Visual approval remains with the human.

## Follow-up: moving edge and bottom notches (September 24)

Human review rejected the moving Cloudkill at 5.692s/frame182 and Fog Cloud / Globe
at 5.540s/frame177 in `20260924T105442Z-cloud-xyz-shield-fix`. Static captures and
passing mechanics checks did not establish these visual results. The previous
ownership test had excluded the fractional XYZ case after treating its comparison
as a fixture issue; that left the real moving-edge defect uncovered.

The exact saved inputs isolate two consequences of the same ownership mistake:

- `(10,8) → (12,8)`, map east edge x14: at translation −0.5625, the translated
  owners stop at x13 while decorative exterior samples still seek owner x14.
  Thousands of valid pixels disappear until the receiving owner rounds back.
- Fog application frame104: cutting the image by the discrete native circle
  removes about 2,000–3,000 pixels per camera, making the repeated bottom notches.
  True XYZ sphere clipping and observed support-height clipping do not cause
  those notches. The ground-height mask removes zero pixels in the reported frame.

### Bounded repair

The full declared sphere lattice and known map bounds determine a stable geometric
owner, just as existing line fields associate their authored fringe with a full
line. Exterior decorative samples borrow that geometric edge, then the existing
subjective permission check applies. We never choose the nearest *observed* cell:
undisclosed or genuinely removed owners retain their holes and their missing fringe.

Ownership is resolved before the existing after-receipt animation translation.
The image, XYZ and receiving support move; map-clipped owner identities do not.
The existing SurfaceVolume compositor handles real walls, ground, Globe exclusion
and painter depth. No new backend rule, event, visibility grant, schema field,
asset export or per-spell branch was introduced. Original XYZ and media are unchanged.

Required anti-slop and anti-OOP/ECS reviewers independently reproduced the cause
and approved this repair. The anti-slop reviewer verified the exact rejected
source frames in all four cameras: ownership now preserves all their covered
pixels before physical composition. The former one-row ownership probe was corrected:
a sample outside that row is decorative fringe; a wider-map variant now separately
proves that a genuinely undisclosed interior cell remains hidden.

### Regression boundary and evidence

Input: actual native Cloudkill cast and turn movement, serialized and replayed after
runtime teardown; actual authored Fog XYZ bank; partial subjective owners and raised
supports. Output: the complete translated registered picture on open ground,
unchanged missing-owner pieces, and existing wall/Globe clipping. No live registry
or new synthetic gameplay sequence is consulted during rendering.

The native movement fixture explicitly requests enough sight distance and asserts
that all 43 map-clipped after-cells are observed. With the default radius of 10,
six east-edge cells are correctly undisclosed; a whole-image expectation would be
invalid there. The strict image oracle remains unchanged. All four cameras and
six movement phases, including the rejected 0.71875 phase, compare byte-for-byte.

Validation so far: 37 movement/ownership tests and 221 field/wall/Globe/native tests
pass; typing of both modified production files is clean. All 12 new whole-image
regressions fail against the previous owner path, confirming that they detect this
repair. Exact failed-frame recomposition has been visually inspected. Full saved
paired clips are being regenerated; artifact and final review status follow below.

Final focused review:
http://127.0.0.1:8767/runs/20260924T112844Z-cloud-ownership-correction/index.html

All 18 clips replay byte-for-byte identical saved subjective sequences (10 edge/wall,
8 Globe), each with four cameras. Their replay checks pass. Exact reported frames,
six moments across movement, real map-edge wall occlusion, and Fog/Darkness Globe
composition were visually inspected. Both implementation reviewers approve the
bounded ownership repair. Human approval remains pending.

### Remaining inset-wall propagation mismatch — explicitly not closed

Further final inspection found that Fog's higher triangular cuts above its inset
wall persist. This is not the repaired bottom fringe and not a Y-packing issue.
The native saved `SpatialEffectChangeEvent` itself owns only 36 cells, ending at
x11. `AreaCondition._area_shape()` constructs a default line-of-effect Sphere;
`SurfaceVolume` defaults to connected propagation. At Fog hold frame95, the
received-owner columns remove 27,279 / 24,916 covered pixels in cameras 0/1 that
continuous physical composition with the actual registered wall sprites would
retain. Those cuts also occur in the preceding gallery.

The replay must not silently invent the withheld native region. The user has been
asked whether the prior full-propagation agreement applies to all six maintained
cloud families. That decision affects gameplay behind walls. A legitimate follow-up
aligns native area policy and its retained/rendered contract, preserves real dispersal
and subjective holes, and captures fresh native sequences if the rule changes.
It must not relabel old 36-cell recordings as evidence of a new propagation rule.
The gallery labels this remaining limitation. Passing replay checks are not a claim
that this separate wall silhouette has been fixed.
