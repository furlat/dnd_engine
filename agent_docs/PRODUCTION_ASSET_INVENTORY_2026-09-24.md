# Complete production asset inventory — 24 September 2026

This inventory covers every installed art file in the current recovery baseline,
`508f5f8d38cc2e6982b73c44ee7f911b794c042a`. It separates current runtime
dependencies, archive-only source material, fixed-size bake candidates and
packing work. The initial tables below describe the pre-implementation inventory.
The Gust correction recorded at the end supersedes its original frame selection;
the [implementation status](CLEANUP_IMPLEMENTATION_STATUS_2026-09-24.md) records
the actual selected, packed release and validation.
The preserved installed-art snapshot remains at `/home/tommaso/Dev/neurodragon_art`.

Three local agents reviewed VFX sizing, characters/equipment/UI, and environment
states. The separate private-assets task completed VFX frame reachability. The
primary task reconciles their claims by physical path; actual consumers override
negative claims, and a demonstrated runtime selector can narrow a conservative
catalog-only inclusion. This is not a list derived from one gallery or encounter.

## Measured file inventory

<!-- BEGIN GENERATED TOTALS -->
| Stage | Files / payloads | Encoded bytes | Decimal GB |
| --- | ---: | ---: | ---: |
| Preserved installed-art set | 62,769 files | 26,660,655,022 | 26.661 |
| Archive-only for current production | 5,551 files | 5,959,706,594 | 5.960 |
| Retained production references | 57,218 files | 20,700,948,428 | 20.701 |
| Repeated payloads within retained set | 14,250 aliases | 5,781,548,704 | 5.782 |
| Unique retained payloads, before new packing/compression | 42,968 payloads | 14,919,399,724 | 14.919 |

**Measured source-to-unique reduction: 11.741 GB (44.04%), before further compression or cell compaction.** Zero unresolved files, unmatched claim paths or retained files without a packing/scale owner. These are candidate payload totals, not savings already applied to disk.

| Installed family | Keep files | Keep bytes | Archive files | Archive bytes |
| --- | ---: | ---: | ---: | ---: |
| `persistent_spells` | 22,916 | 17,601,266,781 | 22 | 1,597,067 |
| `fireball_surface` | 384 | 998,438,407 | 1,920 | 5,043,261,535 |
| `aoe_surface` | 23,088 | 1,255,843,173 | 1,063 | 291,412,451 |
| `spell_recovery` | 5,178 | 22,165,149 | 920 | 206,949,836 |
| `pending_spells` | 770 | 87,071,128 | 1,019 | 121,140,908 |
| `area_spells` | 3 | 244,910 | 257 | 207,678,435 |
| `cantrips` | 603 | 195,009,778 | 0 | 0 |
| `support_spells` | 842 | 121,754,192 | 0 | 0 |
| `ice_spells` | 256 | 58,716,067 | 112 | 40,193,628 |
| `healing_spells` | 242 | 81,590,267 | 27 | 7,242,324 |
| `environment` | 984 | 75,050,789 | 88 | 8,027,599 |
| `control_spells` | 236 | 45,670,463 | 120 | 31,741,829 |
| `liquid_media` | 1,072 | 67,964,928 | 0 | 0 |
| `neuroclient` | 374 | 52,472,406 | 3 | 460,982 |
| `globe_media` | 149 | 25,601,892 | 0 | 0 |
| `rigs` | 88 | 9,286,229 | 0 | 0 |
| `torch` | 19 | 1,158,730 | 0 | 0 |
| `water` | 3 | 895,369 | 0 | 0 |
| `counterspell_media` | 10 | 385,012 | 0 | 0 |
| `codexfx` | 1 | 362,758 | 0 | 0 |
<!-- END GENERATED TOTALS -->

These are encoded file bytes. They exclude future indexes and any change from
repacking or compression. Archive-only bytes and duplicate bytes **within the
retained production set** are disjoint. Do not add the whole source archive's
duplicate count to these savings. Frame-cell compaction and optional resizing
are additional opportunities whose encoded savings have not been measured.

The source manifest already records identities and sizes; this review reuses
that offline evidence. It introduces no runtime hashing, asset validation scan,
source audit, or startup work.

## What belongs where

| Domain | Current production decision | Archive-only / packing decision |
| --- | --- | --- |
| Fireball explosion | Keep the selected 48 source samples in each of eight views: 384 cropped RGBA/XYZ/ownership packets, 998,438,407 bytes. | Preserve the other 1,920 source packets only in the archive: 5,043,261,535 bytes. Bundle selected packets by effect/view without expanding them to the 1536² logical canvas. |
| Remaining VFX | Follow every selected recipe, interruption, condition, spatial/deposit owner, phase, view and preload. Complete frame/part addresses are in the ledger. | Exclude unselected owners and frames; retain alternate reachable travel windows. Reuse existing atlas pages; compact unused cells only with an explicit remap. |
| Persistent fields | Keep paired color and raw coordinate pages for selected volumes and field states. These are real consumers, not merely old exports. | Share identical payloads while preserving each use's crop, offset, coordinate bounds and blend order. This is the major remaining storage cost. |
| Characters | Keep 461 sheets covering eight rigs, modular identities/gear and selected body/attack clips. Cross-reference 67 spell actor-overlay sheets rather than double counting them. | Three unselected historical overlays remain source-only. Keep existing per-layer/per-clip spritesheets; do not flatten combinations of clothes, equipment and body identity. |
| Environment | Keep all selected destruction, remnant, opening/rearming, trap, pressure-plate, portal and device states, including real legacy/fallback paths. | Exclude unused door leaf components, nonselected cannon pitches, superseded flat chest/lever pictures and unused residue images. Repage wide strips and combine loose mechanism frames. |
| Source metadata | Runtime consumes the normalized contracts in `game/data`. | Export reports, delivery READMEs and source-side manifests remain with authoring/licensing material. Do not confuse these with runtime data contracts. |

The inventory is exhaustive for the installed manifest. It does not claim the
entire purchased source packs or external unintegrated handoffs are production
dependencies. Those remain archive/source material until a real consumer is
introduced. It also does not erase missing content by substituting an available
image: supported but absent modular gear/appearance is recorded separately.

## What can actually be resized

The effective transform is decisive. Most VFX use authored scale × `128/64` ×
camera zoom. An authored scale of `0.5` therefore already displays native pixels
at zoom `1`. The supported zooms are `.15`, `.35`, `.5`, `.75`, `1`.

Across **532 selected owner/asset/phase rows**, 381 have fixed factor `1`, 137
upscale, and 14 downscale. Four of the downscale rows are preload duplicates.
These are owner counts, not disjoint images. The following exhausts the VFX
families with fixed factors below one:

| Consumer | Source → reference display canvas | Decision |
| --- | --- | --- |
| Color Spray front/back | 768² → approximately 683² | Candidate fixed bake. Preserve current native assets until comparison verifies registration and output. Its world position scale is already adjusted; do not multiply it again. |
| Shocking Grasp target sparks | 384² → 138² | Optional derivative only. The same source is needed at native resolution on the caster. A smaller copy adds storage rather than replacing the original. |
| Blur using Misty Step transition | 384² → 269², before actor scaling | Optional derivative only; actor size remains dynamic. |
| Mirror Image using Misty Step transition | 384² → 288², before actor scaling | Optional derivative only. Shared Misty Step also renders at native size and at factor 1.3. |
| Ashen floor motifs | Four source motifs → four 70² intermediates | A concrete fixed bake: the current floor reader always makes these exact nearest-scaled intermediates before later rotation/opacity. Preserve that operation and registration. |

The large Fireball, XYZ area and persistent-volume banks have no general fixed
downsize to remove at the supported maximum zoom. Character appearance, width,
condition scaling and field radius remain runtime inputs. Baking an upscale
increases stored pixels without adding detail and still does not eliminate zoom.

A resize followed by another resize at fractional zoom is not generally equal
to the present single-stage sampling. Candidate reference dimensions are not a
pixel-equivalence claim. RGBA, geometry and ownership must select matching
samples; raw world coordinate values are **not** multiplied by raster resize.
Logical canvas, crop and pivot move together, while world geometry/occupancy
remain unchanged. This is why sizing is separated from the lossless reductions.

## What is already a spritesheet, and what still needs packing

There is no need to turn existing sheets back into loose frames. Across the 332
selected VFX asset phases, storage is:

| Existing storage | Phases | Concrete next treatment |
| --- | ---: | --- |
| Sparse part atlas | 247 | Keep exact part rectangles, offsets and ordered blends; share repeated payloads. Repack only where selected-cell compaction has a measured benefit. |
| Grid-page atlas | 61 | Keep page addressing, or remap selected cells to smaller pages. Preserve temporal/source-frame aliases. |
| Legacy sheet | 6 | Three shared physical sheets: Fire Bolt, Magic Missile and Sleep projectile. Split oversized sheets into bounded pages without changing cells or anchors. |
| Loose color frames | 8 | Pack Acid Splash, Eldritch Blast, Guiding Bolt and Fireball projectile phases into ordinary bounded atlas pages. |
| Loose component XYZ packets | 9 | Bundle cropped component packets with an explicit index per effect/view; preserve order and RGBA/XYZ/ownership pairing. A standard color atlas is not already a numeric packet decoder. |
| Loose combined XYZ packets | 1 | Bundle Fireball's selected packets while retaining lazy frame access and exact crops. |

Characters are already sheets with 15 columns and eight direction rows, using
128px cells (64px for the wolf). Their neutral tintable layers and shadow stay
separate. Environment has additional concrete opportunities:

- 177 color strips exceed 2048px width; the largest is 39,936px. Page their
  selected cells and paired depth without changing their timeline.
- Twelve indoor structural-frame atlases declare 1,152 cells but only 48 are
  selected: column zero in four views. Full animated door bodies remain separate.
- Hatch body columns `0,2,3,4,5,6,7,8,9,10,11` and front-mask columns
  `0,2,3,4,5,6` are the real subsets. Keep their logical indices.
- Each portal bank has 433 reachable logical frames. Last pages use 49 of 64
  cells; indefinite hold makes all hold frames valid.
- Ashen floor/wall readers select only the four top-row motifs of each 4×4
  source atlas. Wall motif dimensions vary; do not force the floor's 70² bake
  onto walls.
- Combine loose ground mechanisms, levers, spikes and dart entries by their
  existing frame/view selectors. Keep current 15° cannon sheets and wrecks.
- Water's repeated normal/ripple textures retain their sampling domains; an
  installation bundle can contain them without converting them into an ordinary
  color atlas that introduces seams.

Bounded pages such as 2048² are a practical candidate, not a new mandatory
texture standard: one decoded RGBA page already occupies 16 MiB. Shipping fewer
files and allocating fewer pixels are different goals. No final packaged-file
count or additional compression saving is claimed before a pack is built.

## Frames, supported alternatives and known gaps

Frame selection follows the actual compiler/sampler and current legal contexts.
The nine previously unresolved projectile bounds are now closed: Distant Spell,
the middle of a three-projectile Magic Missile spread and other valid contexts
make their full travel phases reachable. The full 720-frame Chill Touch phase
also remains reachable. First-nonempty preload reads are separate dependencies.

Some source timelines run at 144 FPS. A single 60 FPS video cannot prove unused
source frames because arbitrary elapsed times can select different samples.
Deliberately resampling an export to a lower production cadence is a possible
separate quality/performance decision, not a behavior-preserving file exclusion
and not a saving included here. The ledger preserves exact clocks and aliases.

The review retained conditional paths that an ordinary clip would miss: four
body-release strips for airborne/unknown-pattern damage, bone/corrosive ground
fallbacks, old binary doors, complete trap rearming, all supported direction
rows and maintained portal loops. Alternate cannon pitches are archived because
the current authored device producer always selects 15°, not because one demo
happened to fire that way.

There is one substantial character-content coverage gap: of 281 mechanically
supported authored equipment selections, 65 bind completely and 216 share
absent modular categories. Including allowed appearance options, the ledger
names 81 missing categories and 1,134 requested clip bindings. The existing
Barbarian premade requests missing `Head17`. This is not 216 separate mechanics
bugs, not an argument to remove supported gear, and not an import implemented by
this inventory. No portraits/icons/fonts occur in the installed art manifest;
the actual Pygame and OS font dependencies are documented separately.

## Evidence and review

The consolidated machine-readable inventory is in
`.runtime/asset-inventory-20260924/`:

- `inventory.jsonl`: every physical path, encoded bytes, decision, consumer
  claims and links to its packing/scale records.
- `packaging-index.json`: complete VFX phase records, including actual factors,
  dynamic inputs, registrations, geometry, current packing and recommendations.
- `shared-content.jsonl`: exact retained-payload aliases, using existing offline
  manifest identities. Different registrations remain on their respective uses.
- `claim-conflicts.json`: explicit catalog-inclusion versus selector-exclusion
  reconciliation; no silent override of actual consumers.
- `summary.json`: reconciled totals, families, unmatched claims and completeness.
- `characters/`, `environment/`, `vfx-scale/`, `vfx-ancillary/`, `remainder/`:
  detailed source evidence and reproducing offline diagnostics.

The local diagnostics are intentionally outside the shipped/runtime package.
Durable specialist reports are
[VFX sizing/packing](audits/ASSET_SCALE_BAKE_INVENTORY_2026-09-24.md),
[characters/equipment/UI](audits/CHARACTER_UI_ASSET_INVENTORY_2026-09-24.md), and
[environment/state packing](audits/ENVIRONMENT_ASSET_INVENTORY_2026-09-24.md).
VFX frame proofs and the source manifest remain with the separate private-assets
task under `/home/tommaso/.codex/worktrees/5b97/dnd_engine/.runtime/vfx-usage-audit`.

Ancillary closure checked the final 822 previously catalog-only dependencies:
733 Web field images still render through the prop-animation path, eight Web
cables fit their endpoint distance, 80 static condition images follow their
registered actors, and one 512² noise texture feeds Chill Touch's hit palette.
The noise is a numerical palette sampler, not a character overlay. A bounded
Pygame probe showed that baking it to 128² and then sampling to 64² differs from
sampling the original directly to 64²; retain the original. All these paths now
have explicit consumer, sizing and packing records.

<!-- BEGIN REVIEW CLOSURE -->
Independent anti-slop and anti-OOP/data-contract cross-reviews passed. They
checked the populated master report, joins, exact arithmetic, shared-owner
claims, current fallback branches and scope. Corrections incorporated: distinguish
palette noise from overlays, preserve dynamic factors on aggregate bake records,
and describe the archive as the installed-art snapshot rather than every purchased
source pack.

The final reconciliation accounts for all 62,769 unique paths and every byte,
with zero unresolved files, unmatched claims, missing packing owners or dropped
concrete positive consumers. Forty-four conservative environment catalog claims
were narrowed by individually checked selectors. VFX travel reachability is
closed; character checks called the real layer/request selectors for all eight
rigs and 281 supported equipment choices; environment checks covered 226 state
selections across 208 banks. Verification is recorded in `verification.json`.
These establish dependency selection, not new artistic approval or whole-render
pixel equivalence.
<!-- END REVIEW CLOSURE -->

No broad game suite was rerun for this inventory. The existing architecture
audit's failures remain real and separately classified in
[the rendering review](RENDERING_ARCHITECTURE_REVIEW_2026-09-23.md). Inventory
completion does not mean those defects were fixed or that the assets have
already been packed. Applying the measured exclusions and aliases, then packing
loose frames/packets, is the next implementation unit; resizing remains limited
to the concrete cases above.

## Implementation correction and actual release

Fresh production-only replay demonstrated that Gust's maintained line renderer
can select all eight world/camera facings. The initial inventory omitted 108
maintained frames in each of four diagonal banks. The corrected ledger retains
**57,650 source references / 20,837,176,152 bytes** and archives **5,119 files /
5,823,478,870 bytes**. All 62,769 original files remain preserved. See the
[Gust repair and sibling selection review](audits/GUST_RELEASE_SELECTION_REPAIR_2026-09-24.md).

After exact sharing and packing, the actual private release is **24,783 files /
15,065,521,247 bytes**. These are installed payloads, not the earlier unique-content
estimate. Two depth strips remain alongside their packed consumers because other
current consumers still use the originals. The final implementation status records
fresh-install tests, pixels and release identifiers; the initial audit's failures
are historical findings rather than an ongoing waiver.
