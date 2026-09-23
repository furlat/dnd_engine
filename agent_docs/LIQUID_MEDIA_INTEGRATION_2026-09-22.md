# Approved liquid media — production integration

**Completed:** see the [production result](LIQUID_MEDIA_INTEGRATION_RESULT_2026-09-22.md)
for all 18 imported variants, 28 paired clips, verification and explicit limits.
The export requests and partial checkpoints below record the approved sequence.

## Contract and approved input

The user says to keep working through integration and use the Godot expert for
missing exports. Work stays on liquid barrels until finished; the separately
queued spell batch is not part of this unit.

[Approved handoff](</home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/delivery-liquid-spills-v1/HANDOFF.md>):
six materials × three deterministic irregular splats. Approval supersedes the
earlier quarter-tile proposal for this appearance. The delivered L experiment
was not approved. Current delivery is one camera, whole 3×3 capture with combined
floor and airborne pixels; it cannot honestly cover every production case yet.

Each 384×384 logical canvas has ground pivot (192,192), 1152 observations at
144 Hz: intro [0,864), sustain [864,1152). Source ground vectors (32,16),(-32,16)
map to engine vectors (64,32),(-64,32): one 2×camera.zoom factor. Preserve crop
offsets and authored pixels. No browser timer/zoom, source hash audit, eager
decoding of all pages, pixel recoloring or new fluid simulation.

## Native ownership

Keep current same-UUID destruction, bounded admitted ground footprint, contact
mechanics and quantity caps. Existing conditions remain the material owners.

The actual gap is durable deposition geometry: tile residue snapshots contain
amount and injury ellipses but lose a barrel spill's common origin. Introduce one
immutable `MaterialDepositSource`: actual destruction **lineage UUID**, world origin,
radius in cells. Carry it optionally on existing spatial conditions/observations
and residue contributions. It contains no asset, variant, animation clock or
source item identity. Current condition/tile membership remains the only actual
coverage; do not duplicate the reached set inside the record.

Residue contributions group by geometry and deposition source and retain only
positive newly admitted amount. Saturation does not append history or replace
the old pool. Preserve existing injury shapes. Ground material transforms retain
their deposition frame while native content/coverage changes normally. Optional
defaults preserve older packets without inventing old provenance.

Observed material fragments carry their deposit-space geometry, as existing
residue ellipse fragments do. Its frame origin can lie outside a currently
observed fragment; it is intrinsic material geometry, not a discovered source
contact. Keep `anchor_position` gated by existing visibility rules. This record
exposes neither additional receiving cells nor a hidden barrel/actor identity.
Cold replay must work after wreck retirement, without searching native events or
the live map. Do not infer origin from observed-cell bounds or connectivity.

## Presentation and media

- Reuse `ProjectileFrameLayer.partsByFacing`, sparse frame storage and
  `registered_media_blits`. Split application and sustain into metadata windows
  over unchanged pages. Imports translate storage only; material behavior stays
  in one passive authored binding.
- Normalize current spatial-material owners and tile contributions into observed
  deposited pieces in presentation code. Select one variant deterministically
  from the retained deposit identity; do not randomize per frame or per camera.
- Reuse the shared historical clock and maintained-media timing. Witnessed
  discharge starts at the existing destruction transition plus an authored
  rupture frame from the actual barrel bank. Inspect that bank before choosing
  the value. Gameplay state still commits at contact; settling does not extend
  the turn/action or delay the next action. Cold acquisition starts sustained
  material, and visibility changes do not replay discharge.
- Draw floor-only media with existing `field_cell` partition, per-cell height,
  light and painter ordering. Native membership controls which pieces exist;
  subjective disclosure controls which of those pieces are drawn. Preserve
  native transforms and removals with no invented clear animation.
- Airborne media uses exported world footpoints for native-cell/visibility
  clipping and existing `partition_world_depth` for actor/wreck ordering. A
  companion registration extends existing sparse storage narrowly. Do not cut
  elevated droplets using screen-space floor diamonds or put the whole sprite
  at a single blanket front/back depth.
- Suppress earlier static pool output only where new deposited material owns
  coverage; ordinary injury contributions retain their existing geometry.

## Godot extension already requested

Godot task `01a0b6af-5fa9-7ec0-9915-0ecee0a6baec` is preparing water seed 0 first:
four cameras of the same saved simulation, separate floor/air color, aligned
air world-X/Z footpoint data. Production maps Godot Z to world Y. Data encoding
must bypass color quantization/blending; coverage comes from the color alpha.
Validate that prototype before multiplying the accepted 18 variants. The author
retains approved palette/motion and GPU pixelation. No game code changes there.

Request concrete wall/door-trimmed, missing-corner and partial-removal composition
examples. Strict clipping protects gameplay but is not proof that the transformed
appearance is approved. L and arbitrary topology remain outside current visual
approval. Single-layer transparency/depth limitations must be stated honestly.

## Verification and review

Input is native attacks, breaks, movement, transforms and removal. Rendering uses
saved public events after engine teardown. Check both subjective perspectives
and four camera views, with actors in front of/behind the rupture.

- Same source frame and deterministic pattern after serialization, cold snapshot,
  wreck retirement and partial removal; no added contribution at quantity cap.
- Physical radius/coverage and disclosure preserved; no private inventory or
  hidden-cell expansion. Other authored surfaces and shaped injuries unchanged.
- Actual rupture/release alignment; intro→sustain without reset; absolute-time
  seek stable; later actions continue while the pool settles.
- Footpoint/depth atlas correspondence and floor scale/pivot across four cameras.
- Door/wall limits, raised ground, partial removal, oil→fire replacement,
  maintained Grease state, and cold/reacquired observation.
- Focused native/replay/media tests, typing, and paired gameplay gallery. Keep
  existing lazy/bounded decode; ordinary timing checks may measure actual cost.

Anti-slop review: `presentation_antislop_review` (existing storage, clocks and
draw primitives), plus `backend_ecs_review` (native deposition ownership).
Independent anti-OOP/ECS review: `spell_orientation_antislop` before final wiring.
Record review decisions and actual results below. Do not count asset delivery
as finished integration or claim the pending camera/depth/footprint gaps solved.

Independent review approved the existing-owner approach with the two details
above: phase events have distinct UUIDs, so use the lineage UUID; physical shape
registration does not grant a source contact. The inspected barrel bank opens
at frame 6 (500 ms at 12 fps); author this release marker on that bank once.

## Implementation checkpoint

Native source retention, the sparse footpoint extension, source-aware floor/air
drawing, rupture dates and shared painter partition are implemented. The existing
maintained-frame calculation is shared with spatial media; no second animation
clock was introduced. The saved water story passes both observers and four
cameras; inspected splash and settled frames are at
`.runtime/liquid-media-20260922/water-{splash,settle}.png`. Intro continues while
movement proceeds. Review cases now hold their ending for five seconds to include
the settled loop without slowing actual gameplay.

The verified water prototype was returned to the Godot task as the production
export contract. All eighteen exports are being produced incrementally at
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/delivery-liquid-depth-v1/batch.json`.
Only water seed 0 is installed at this checkpoint. Do not call the full batch
integrated until all bindings, tests and paired gameplay clips are complete.

Independent final implementation reviews approved native ownership, recorded
geometry/disclosure, clock semantics and existing painter reuse. Focused media
storage checks passed 41 tests; exact source comparisons preserved 304 color
crops and 272 ownership crops. Full engine and broader rendering checks are in
progress; final results belong in a separate result record.
