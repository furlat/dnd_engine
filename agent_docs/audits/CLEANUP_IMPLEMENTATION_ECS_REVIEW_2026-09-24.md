# Cleanup implementation plan — ECS and portability review

Status: independent source review, formal written-plan round 1 and revised-plan
round 2 complete. Approved for implementation from the ECS/portability boundary;
no required plan changes remain from this review.

Scope: the September 24 detailed implementation plan. This review reads the
current code and prior architecture audit; it does not edit production code,
change approved art, rerun the broad suite or implement the future TS client.

## Verified owners and minimum changes

| Boundary | Current owner | Bounded implementation requirement |
| --- | --- | --- |
| Finite cast completion | `game/animation.py`, `_compile_anchored_cast`, `compile_cast`, `media_track_duration` | Share the existing finite-media end calculation, including negative-start rejection. Join it before recovery starts in both compile paths. Preserve contact/release timing and do not introduce a scheduler or change nonblocking contact tails. |
| Render command semantics | `game/draw_commands.py`; consumers in `app.py`, `portal_draw.py`, `animation_draw.py` | Name role, owner and relevant world contact; carry device facing/frame explicitly where needed. Preserve passive commands and derive optional diagnostics independently. Rendering must work with diagnostic evidence absent. |
| Storage alternatives | `game/animation_types.py`, `game/projectile_media.py` | Enforce existing alternatives at the existing decode/binding boundary: one of pattern/pages/partsByFacing/parts per layer; layers versus surfaceFrames; packet pattern versus componentsByFacing. Validate cheap frame/map relationships against the real consumer. Do not read or hash the raster corpus. |
| Raster registration | `game/registered_media.py`, `cast_media.py`, `animation_draw.py`, `spatial_media_draw.py` | Preserve the shared sparse-rectangle/pivot transform and paired numeric/color sampling. Make basis/reference scale/composition explicit at their current ownership boundary. Storage selection cannot silently select behavior. |
| Catalog input types | `game/device_art.py`, `portal_art.py`, `condition_media.py`, `environment_art.py`, `world_animation.py`, `asset_types.py` | Type small authored documents at their current load points. Retain passive runtime values, immutable maps and lazy rasters. Add finite/positive/frame/camera/map constraints only where the consumers need them. |
| Narrow contact media | `game/spatial_contact_media.py`, `game/stationary_media.py` | Reject attachment/offset/actor-scale/orientation fields that the stationary consumer does not execute, or factor only its actual common finite-media core. Do not silently accept the entire cast attachment vocabulary. |
| Coverage | `game/presentation_coverage.py`, `game/media_coverage.py` | Extend existing initialized-owner inventory and observed-lineage evidence. Keep binding selected, observed, partial and accepted omission distinct; no recursive asset scanner at startup. |
| Portable schema identity | `game/condition_types.py`, `game/authoring_conversion.py`, `game/data/PRESENTATION_CONTRACT.md` | Preserve original NeuroStudio readers and identify local extensions honestly. Local condition additions currently reuse NeuroClient version 12; migrate the local document identity while retaining original v12 intake. |

## Dependency direction

`animation_types.py` already imports condition/device/portal records. Those
lower-level modules must not import `animation_types.AuthoredRecord` to obtain
validation helpers. Keep their small source types local, or extract only common
primitive aliases/configuration into a dependency-free leaf when actual reuse
warrants it. Do not use late imports or type-checking guards to conceal a cycle.
`environment_art.py` and `world_animation.py` already consume animation types;
their existing downward dependency can remain.

The cleanup does not require entity subclasses, one class per effect, plugin
registration, a universal track graph or a universal media decoder. Rules and
subjectivity stay in the engine. Event reduction and historical presentation
remain independent; typed draw values remain the raster adapter's output.

## Registration details that must survive migration

- Current finite/maintained media often use `authoredScale * TILE_WIDTH /
  data.rig.TILE_W * camera.zoom`. With current 128/64 reference sizes, an authored
  0.5 renders at native resolution at maximum zoom. It is not a generic 50%
  downsample opportunity.
- Actor visual scaling and observed native radius scaling are independent
  dynamic terms. Body media, area media and device media need their existing
  registration meanings retained rather than one arbitrary multiplier.
- `registered_media_samples` rounds shared rectangle edges about the anchor.
  Preserve that behavior when migrating metadata, including fractional zoom.
- Color, raw XY/XYZ and ownership must select matching source samples. Numeric
  coordinates do not pass through color transforms and do not shrink simply
  because their raster resolution changes.
- Source/camera vector rotation differs from world-position translation. XYZ
  impacts use their authored camera banks; travel sprites may use residual
  screen rotation. Component order remains meaningful within world-depth cuts.
- The wall-cap correction is an intentional visual geometry fix, separate from
  a behavior-preserving metadata migration. It cannot be hidden in a schema
  change or implemented by changing native propagation.

## TypeScript boundary

The reusable material is JSON authoring, public event values, passive sampled
values and documented deterministic algorithms. Python `Path`, Pygame surfaces
and NumPy arrays are runtime adapter products; they do not belong in portable
authoring. The existing NeuroClient serializer reconstructs its v6 fields and
would drop local `media`, `contact`, `childAttack` and effect draft data. A future
reader/editor must retain the explicit local extensions.

This unit should document and retain a small set of ordinary JSON value fixtures
for frame/timing selection and registration. It should not build a TS renderer,
cross-language schema generator or second executable implementation now. Shared
algorithms remain code where expressing them as authoring data would add a DSL.

## Existing useful validation surfaces

Use `tests/game/test_animation.py` for composed finite-track completion;
`test_projectile_media.py` and `test_xyz_media.py` for source decoding, paired
coordinates, crop registration and authored material order;
`test_animation_draw.py`, `test_world_depth_commands.py`, `test_portal_draw.py`
and `test_device_animation.py` for real draw output with evidence disabled;
`test_spatial_contact_media.py` for honest accepted contact fields; existing
environment/condition/device/portal tests for source input behavior;
`test_presentation_coverage.py` and `test_media_coverage.py` for developer reports.
Use the corresponding current importer tests for behavior-preserving reimports.

Do not freeze private function names or insist on a particular record layout in
feature tests. Exercise authored values through the stable compiler/sampler or
ordinary saved-event input and assert timing, registration and rendered output.

## Formal validation

### Round 1 — written plan reviewed

Read the full
`agent_docs/RENDERING_ASSET_CLEANUP_IMPLEMENTATION_PLAN_2026-09-24.md` and checked
its U3–U7 and A3 ownership statements against current producers/consumers.

The intended structure passes: passive records and existing shared execution
remain central; all three implicit composition switches are covered; source
registration preserves current effective transforms; finite cast completion is
separate from nonblocking stationary/contact tails; catalog typing respects the
import DAG. The future TS boundary does not become an implementation project or
a universal schema generator. Packing reuses existing readers and gives indexed
XYZ storage a bounded adapter. The discovered packet-cache interpretation hazard
is correctly a prerequisite for new sharing, not a blanket claim that existing
distinct-path effects render incorrectly.

Required corrections:

1. **Complete the general catalog boundary in U3.** The owners list covers the
   newer environment/device/portal/condition documents but omits
   `game/assets.py:catalog_from_documents` and
   `game/asset_types.py:image_resources`, identified in the original audit.
   Active image registration, world bindings and water/catalog fields still
   flow through broad dictionaries and casts there. Name these current source
   documents and type their actual consumed fields at the same load boundary.
   This does not require merging all catalog families or typing inactive legacy
   source content for its own sake.
2. **Make diagnostics independence an observable U3 gate.** Replay/render a
   representative device, portal and deposited-material case with diagnostic
   evidence omitted and assert equal pixels/behavior to evidence-enabled output.
   Checking only that named fields were added would miss a surviving tuple read.
   No permanent visual framework is necessary.
3. **Correct the U6 owner path.** `surface_volume.py` is not the current module;
   use `game/volume_media.py:compose_volume` and the real area/fixture owner seams.

Clarification recommended: choose the local schema revision and exact legacy
normalization boundary in the unit introducing new composition fields. U7 can
document and verify the final identities, but should not be the first point at
which earlier intermediate documents acquire an unambiguous meaning. This is
not a demand to bump every schema for additive implementation details.

No production code or media was changed, and no tests were run for this plan-only
review.

### Round 2 — revised plan independently re-read

Re-read the full revised plan and all round-1 findings. Closure:

| Finding | Revised written contract | Result |
| --- | --- | --- |
| Omitted general catalog boundary | U3 names `assets.py:catalog_from_documents` and `asset_types.py:image_resources`, and scopes typing to consumed image/world/water/prop documents while preserving fallbacks | Closed |
| Hidden tuple protocol could survive generic comparison | U3 explicitly renders the same named commands with evidence omitted and requires device pose, portal clipping and deposit lighting/visibility to remain correct | Closed |
| Nonexistent geometry owner path | U6 identifies `volume_media.py:compose_volume` | Closed |
| Version identity decided after semantic migration | U4 owns the revision/normalization at the same time as new composition meaning; U7 verifies and documents it | Closed |

The added archive round-trip gate preserves missing historical knowledge without
constructing a generic provenance system. The known modular-art gap is reported
separately from packaging omissions, avoiding a false all-outfits-supported
completion claim. Public normalized bindings remain with the code; private
installation writes media and asset-local indexes. Raw XY page packing now
explicitly respects the shared color/coordinate rectangle contract. These
additions are consistent with the existing ownership and DAG recommendations.

The written plan is approved for implementation. This is approval of scope,
dependencies and acceptance contracts, not proof that future code or generated
assets already pass them. Implementation must still demonstrate the finite join,
evidence independence, schema intake and same-input registration comparisons at
the listed existing boundaries. TypeScript execution, new content, general 3D
transparency, optional new compression and historical Git cleanup remain outside
the primary renderer acceptance claim. No production changes or test executions
were performed by this review.

## Implementation review — September 24

The plan review above is historical. Implementation is now authorized. This
agent implemented U2 importer ownership, U3 catalog intake, and the environment
portion of A3; those units' results below are self-validation, not independent
approval of its own work. The review of the root/U1/U6 changes is independent.

### Root/U1/U4/U5/U6 ECS and portability findings

- `PlayerFact` no longer runs an indiscriminate union-wide Python conversion.
  The historical propagation adaptation belongs to `SpellFact` and preserves
  explicit modern policy. Native completion admission is limited to observed
  completed/noncanceled Action/Movement/Spell families. Its private omission set
  is codec metadata, not a gameplay state or a new event lifecycle. Current live
  receipts remain explicit; retained omissions survive re-encoding. No reverse
  import from the engine into the client has been introduced.
- `DrawCommand` remains a passive record. Role, owner, contact cell and device
  facing/frame now carry the actual required semantics. Remaining diagnostic
  tuple slices decorate reporting; they do not select bodies or gameplay state.
  The device, portal, deposit and feedback producers/consumers were migrated
  together rather than adding a second dispatcher.
- The three composition branches are selected by authored fields. Legacy
  inferred values are normalized at authoring intake, with local recipe version
  3 distinguished from NeuroStudio v6. Packed source addresses and the
  composition choice are separate. XYZ registration decodes world coordinates
  with the declared reference pixel scale; camera zoom is removed from physical
  scaling. Source pixels, XYZ samples and ownership use the same nearest-source
  indices. The named packet cache key includes the decoding coordinate metadata.
- `finite_media_end` shares the existing finite-track timing formula. Both cast
  compilers join that end before recovery. This change does not absorb maintained
  condition clocks, deposited surfaces or nonblocking contact tails into a new
  action scheduler. The timing test checks the observable recovery start.
- U6 uses the actual submitted boundary silhouettes for visual occlusion and
  disclosed edge placement for depth. Native propagation and suppression remain
  the supplied gameplay contract. The cap correction belongs to the existing
  volume compositor; it does not reconstruct fixture solids from screen pixels,
  require an entity renderer subclass, or add backend art data.
- The ZIP reader adds one storage address form and a bounded handle cache;
  it does not scan or verify source assets during playback. Small portable JSON
  examples exercise projection, sampling, coordinate decoding and finite joins.
  They establish a TS-facing value contract, not a claim that a TS runtime has
  been implemented.

No additional blocking change was found in those reviewed units. This review is
limited to the actual patch and retained acceptance surface; it is not evidence
that every future spell/geometry/authoring combination is supported.

### U2/U3/A3 validation and remaining adapter finding

U2: 46 importer tests passed; 3 unchanged palette-rebake cases were not rerun.
Narrow typing was clean. All 23 importers were inspected. Production behavior
JSON and art were not regenerated by these fixes. The explicit dev dependency
update added Pillow only, matching the existing offline sleep importer.

U3: all complete passive values from the typed device, portal, condition,
environment and world loaders compared equal with the HEAD loaders. This
included original nonuniform sample times, zero-duration static banks, fallback
FPS, pivots, scale, prop selectors and maps. 167 targeted intake and behavior
cases passed. Source typing remains local at its current ownership boundary;
low-level catalog modules do not import `animation_types` back.

Warm metadata-only median timings over five measured repetitions on the shared
WSL `/mnt/c` checkout, with the same Linux environment, were:

| Loader | HEAD | Typed |
| --- | ---: | ---: |
| Device | 7.41 ms | 6.73 ms |
| Portal | 4.48 ms | 4.78 ms |
| Environment | 10.71 ms | 11.41 ms |
| World | 14.75 ms | 17.35 ms |

These are intake timings, not cold-start or raster-decoding measurements.

A3: explicit `{path, rect}` addresses preserve full source cell dimensions;
color and depth rectangles may have different cell sizes. Original sheet forms
remain readable. The actual staged/applied pack was compared against its
recorded `before` sources: 640 sampled render comparisons at four views and five
zoom levels covered the shabby door opening/frame-only/destruction, blade
breakage, largest winged-statue bank, and 76 loose resources. RGBA, destinations
and depth-partitioned scenes matched. The statue has no authored depth, so that
case asserts color/placement only. This run took 5.51 seconds, with no hashes.
139 existing fixture/environment/mechanism tests passed again against the live
packed catalogs. A separate test proves one page decode shared by multiple loose
resources across all supported zooms.

One shared-contract gap was identified after packing: `AssetSpec.rect` is also
admitted for static condition attachments, but `condition_draw` originally loaded
the complete file. The selected 480 packed resources are mechanisms, so current
condition artwork is unchanged; the shared rectangle still needs to be consumed
there rather than left as a silently ignored field. This is a bounded crop
adapter, not a request to pack additional condition assets or introduce another
cache framework. Closure will be recorded below after implementation/verification.

Closure: `condition_draw.load_condition_layers` now honors the same optional
rectangle, shares a decoded page within its existing preload call, and retains
its existing session row cache. A tiny independently colored back/body/front
composition proves registration and layer order, and records one decode for two
attachments. All 10 Web condition-layer tests passed; final typing across the
changed catalog and adapter modules reported zero errors. No unresolved blocking
finding remains from this ECS/portability review.

Applied-pack evidence owner:
`/home/tommaso/Dev/neurodragon_art-packed-environment-20260924/packed-environment.json`.
Its guarded records identify 177 color banks, 136 paired depth banks, 12 static
frame banks, 480 loose resources and 650 generated pages. The two original
mechanism depth strips remain selected unchanged. The reusable test boundary is
`tests/game/test_packed_environment_media.py`; the one-off full sampled pack
comparison used the handoff's original `before` records against its selected
`after` records (640 matching comparisons, 76 loose resource identities).

The equivalent-render gate was repeated after the root applied these addresses:
139 fixture/environment/mechanism tests passed against the actual production
selection. No SHA/source audit or speculative pixel-regression framework was
introduced. Historical source files were read only for the explicit comparison;
ordinary catalog loading and rendering remain demand-driven.

### Production-only installation check

The Linux validation installation with 24,781 production files exposed a test
that required every historical resource binding to name an installed file.
The three missing baseline files were exactly the inventoried source-only
`Slash1/Attack5`, `Slash2/Attack5` and `Magic2/Attack5` overlays. The default loader
also retains three superseded aliases: the old Guiding Bolt and Eldritch Blast
weapon glows, and `pending-spells/retreat/cast`. Selected recipes instead use the
authored `spell-palettes` glows and `pending-spells/expeditious_retreat/cast`.
No selected dependency was omitted by these six exclusions.

The reference roundtrip test now checks the exact original URL-to-absolute-path
mapping without requiring archived source media to be installed. Its companion
decode test retains the full root body/equipment clip matrix and decodes the
selected Fire Bolt glow and projectile. Five focused source/roundtrip checks
passed against the production-only installation in 4.47 seconds. No media was
restored, no production binding changed, and no runtime existence scan was added.

The next production-only pass exposed one genuine packaging defect: the blade
and crusher `ground-depth-rg.png` strips serve both a now-packed EnvironmentBank
and an unchanged `PropAnimation.actor_depth` sampler. The plan correctly retained
the two resource samplers, but `build_environment` incorrectly classified every
packing input as fully replaced. It now subtracts explicit retained resource
paths when emitting `replaced_inputs`. A tiny shared-source test proves the bank
can be paged while the resource keeps its original strip. All three offline
environment-packaging tests passed. The staged manifest was corrected by exactly
two removals from `replaced_inputs`; generated pages were untouched. The parent
task owns restoring these two original files and their existing manifest records.

The remaining reported failures assumed archived addressing: the finite catalog
test decoded all historical entries, the combat-map fixture loaded an unselected
original cast overlay, and the cannon test traversed all four historical pitch
banks although production selects the authored 15-degree bank. Tests now decode
the complete directly selected world image set (including fixture depth), use
production Fire Bolt media for map occlusion while retaining a dedicated original
geometry-dart case, and compare live/break/wreck pixels across four cameras and
eight aim rows at the selected cannon pitch. These 15 cases passed on the packed
Linux installation in 11.50 seconds. No runtime rendering behavior changed.

The Web fringe test likewise opened an archived static duplicate only as an
additional image oracle after loading the correct production resting frame.
It now reconstructs that selected frame directly; exact full-image equality,
real overspill, partial removal, partial visibility, empty ownership and backward
reconstruction remain checked in all four cameras. All four cases passed on the
production-only installation in 0.59 seconds. No runtime dependency was missing.

A separate bounded manifest/member-index check of all 18 packed phases (ten XYZ,
eight color) found no sibling of the reported Gust of Wind diagonal hold gap:
the other 17 contain every declared frame in all eight facings. Current world
bindings expand to 29 spatial/deposit variants and 133 distinct asset/phase
requests; 305,680 logical frame/facing samples require only the four missing Gust
windows, 252–359 for SE/SW/NW/NE. The final 360–431 Gust frames are unselected:
the finite intro uses 0–251 and the maintained loop uses 252–359. This independent
check read no media payloads and made no changes; the packing owner handles that
repair. Other maintained fields and deposits select E rotated through four
camera views, and Globe suppression explicitly selects cardinal banks.

### A3 cold selected-frame and decoded-memory comparison

Two fresh Python processes used the same current `environment_command`, `_sheet`
and `_frame` code, SDL dummy display, camera 0, zoom 1 and unchanged authored
scale `128/127`. Each loaded only frame 52 of the east-facing
`prop.interior-winged-statue.break` bank, the largest original environment sheet.
The original binding came from Git HEAD `508f5f8d38c` and its media from the private
source archive; the packed binding came from current public data and its media
from the private production repository. Imports, metadata parsing and display
initialization finished before timing. Both image caches began empty.

| Measurement | Original sheet | Packed selected page |
| --- | ---: | ---: |
| First selected-frame wall time | 648.79 ms | 33.77 ms |
| Decoded source dimensions | 39,936 × 1,536 | 1,920 × 1,920 |
| Returned frame dimensions | 387 × 387 | 387 × 387 |
| Retained source + frame cache surfaces | 234.57 MiB | 14.63 MiB |
| Process RSS before frame load | 88.64 MiB | 88.61 MiB |
| Process RSS after frame load | 323.31 MiB | 103.57 MiB |
| Peak process RSS | 557.14 MiB | 117.11 MiB |

The measured frame load was 19.21 times faster and retained 93.76% fewer decoded
surface bytes. Both paths retained one source surface and one scaled frame;
`convert_alpha`'s temporary decode/conversion allocation is included in peak RSS.
There is no regression in this bounded case. Peak process RSS includes the common
Python/Pygame baseline and allocator overhead; retained surface bytes are counted
exactly as pitch × height for each independently owned cached surface.

Limits: this is one representative cold decoder request, not a throughput or
whole-session memory benchmark. The OS filesystem cache was not cleared. It does
not measure four-camera working-set churn or assert a universal 19-times speedup.
The earlier four-camera/five-zoom pixel and depth comparisons supply correctness
evidence independently of this timing measurement.

Reproducible one-off script and untouched JSON outputs:
`.runtime/cleanup-implementation-20260924/a3-cold-frame/measure.py`,
`original.json`, and `packed.json`. No production code, assets, or framework was
added for this measurement.
