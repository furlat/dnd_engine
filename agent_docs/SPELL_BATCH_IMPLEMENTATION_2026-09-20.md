# Integrate the recovered spell batch

User authorization: integrate all seven selected updates and repair related
implementation problems. Work stays on `codex/recovery-design`; preserve the
existing uncommitted Sleep, cannon, graphics and gameplay work.

## Observable contract

- **Behavior:** actual Sacred Flame, Shocking Grasp, Poison Spray, Burning Hands,
  Thunderwave, Gust of Wind and Web actions use the selected frozen artwork,
  authored casting, palette and contacts. Native events continue to own outcomes.
- **Boundary:** a recorded subjective event sequence reduces and plays without
  rerunning the engine. Complete lineages finish; advancing rules does not speed
  playback. Camera choice cannot change contact or condition timing.
- **Input:** discovered native spell actions, saves/hits/misses, forced movement,
  concentration removal and Web escape/destruction, captured for both observers.
- **Output:** registered hand/ground/body effects, actual reactions and positions,
  persistent media only while the observed native state exists, and four-camera
  clips with useful trace evidence and no silently omitted selected features.

Authoritative source and revision selection: [intake record](SPELL_BATCH_RECOVERY_2026-09-20.md).
Import selected media and its registration metadata only. Recipes remain authored
JSON with one owner; importers must not copy another spell's generated behavior.
No checksum inventories, source audits or asset validation in game startup/draw.

## Implementation sequence and ownership

1. **Inspect and review the boundaries.** Independent anti-slop and anti-OOP/ECS
   reviewers check the plan against current code and the handoff. Reproduce the
   artist's geometry observations before deciding whether native code is wrong.
   Existing geometry is not silently redesigned to match a preview fixture.
2. **Direct and touch delivery.** Extend the existing finite cast/media sampler
   only for selected missing semantics: an effect's authored offset from release,
   source versus target attachment, back/actor/front ordering and body-following
   contact. Reuse existing paged media, palette bake and actor/hand sockets. Sacred
   Flame is ground anchored; Shocking Grasp uses separate short hand charge and
   lingering body arcs; Poison Spray originates at the palm. Preserve all source
   frames. If facing exports need different timing, resample their authored media
   to one camera-independent contact clock, never move mechanical contacts with
   the camera or copy review target coordinates into game logic.
3. **Area delivery.** Execute authored `StudioArea` through the existing cast and
   lineage compositor, using shared finite area media rather than Python spell-ID
   branches. Burning Hands uses its whole native cone; Gust uses its whole band
   packing; Thunderwave keeps its natural crest while reconciling the delivered
   spatial slices as storage/depth, not as a new gameplay-shaped alpha mask.
   Record actual native origin/direction/footprint, and bind each recipient's
   reaction/push to the shared authored area contact progression. Walls/supports
   and scene depth remain renderer concerns; they do not recalculate victims.
4. **Persistent presentation.** Web imports frozen v11 and adds reusable authored
   condition layers selected by exact observed restraint membership. Remove on
   actual escape/cleanup; saved actors never gain wraps. Preserve creation/final
   ground continuity and device ownership. Partition the natural field's fringe
   by authored full-footprint edge ownership, using only observed native owners
   and visible receiving support; do not infer a full field from partial bounds.
   Gust's initial traveling front must play once. Select and validate a maintained
   flow phase from the supplied hold, separate from that front, tied to the real
   observed zone/concentration lifecycle. Never replay saves with a visual loop.
5. **Correct demonstrated native defects.** Repair only reproduced targeting,
   displacement reporting or lifecycle inconsistencies needed by these spells,
   through their existing geometry/handlers/events. Do not add a new spell/device
   hierarchy, renderer state to engine entities, or speculative neighboring rules.
6. **Validate and show the whole batch.** Extend reusable native scenarios and
   the existing clip catalog. Cover both viewpoints and four corners, hit/save
   outcomes, adjacent/maximum-range direct effects, axial/diagonal areas, blocked
   push/walls, persistent expiry/escape/removal, and mage/device Web. Replay saved
   packets; test meaningful native/presentation contracts and relevant existing
   Sleep/cannon/ice/projectile regressions. Inspect actual frames. Measure affected
   loading/playback work if decoding becomes a bottleneck; do not add a benchmark
   or visual-regression framework. Update result notes and the recovery plan.

## Decisions requiring evidence during implementation

- Current 53-degree radial-center cone and even-width line rasterization may
  differ from the preview. Separate ordinary geometry policy from an actual
  disagreement between discovery, execution and persistent state.
- Gust's exported three-second example is finite. Identify a usable maintained
  flow interval from its pixels before authoring a loop; report a real asset
  limitation if it cannot support one rather than inventing substitute art.
- Thunderwave's delivered slices and Web's partial-cell removal must preserve
  natural source pixels while respecting visibility and physical occlusion.
- Existing presentation limitations are not blanket permission to rewrite the
  engine. A newly found issue must affect this selected behavior and have a
  reproducible native event or rendered example.

## Independent review

- Anti-slop reviewer: `/root/graphics_antislop` — approved with one shared
  anchored-media record/sampler, Sacred Flame's two depth layers preserved, and
  no unverified promise of a seamless Gust loop.
- Anti-OOP/ECS reviewer: `/root/graphics_ecs_review` — approved with reproduced
  native fixes only: diagonal push distance reporting, initial/persistent Gust
  direction agreement, observed Gust zone facts, exact Web source membership and
  persistent Gust respecting the initial cast's existing self-exclusion.
- Web/condition implementation study: `/root/area_projection` — approved bounded
  authored fringe ownership and existing condition-recipe composition.

Implementation and independent review are complete; see the
[implementation result](SPELL_BATCH_RESULT_2026-09-20.md) for tests, gallery and
the user's subsequent Web pacing correction. Cone/line rasterization policy remains unchanged;
the selected area spells now retain their actual native resolution for replay.
Sparse media rectangles extend existing paged storage rather than expanding a
long Gust canvas or decoding every direction at startup. Casting and hit palettes
use the literal delivered colors; already authored isolated hand sheets stay intact.

Native follow-up review approved the actual Gust turn-cycle fix: its ongoing
handler had pushed the caster even though the initial cast excludes them. The
shared push boundary now respects that existing exclusion; target saves and
continued pushes still execute. Web's stable public label identifies its existing
source membership without changing its UUID-indexed mechanical ownership.
Selected spell identities remain owned by the existing initialized catalog;
the raw uninitialized discovery probe did not establish a production defect,
so the proposed duplicate owner declarations were removed.

Native/capture validation: **131 passed in 100.78s**, covering the complete
existing spell-family module, the selected mechanics and observed-zone cases,
device concentration/destruction regressions, Web replay, ten cantrip encounters
from both observers, and the maintained older spell matrix. Two Fireball cases
were corrected to count exact recipient save entries separately from the 49
legitimate Ashen tile-condition log children; HP, costs, preview/execution targets
and total damage remain asserted. Selected new tests and the spatial DTO typecheck
cleanly. The broad native-file typecheck still reports 12 diagnostics whose
declarations/imports are unchanged from the committed baseline.

## Poison fixed-size range/contact follow-up

After removal of automatic raster enlargement, the artist measured the actual
retained rig contacts. Three maximum-range diagonal views never intersect the
old cloud at any source frame. A delay change alone cannot repair this. The
artist owns a corrected source export preserving particle size/palette, with
forward reach and transparent padding; no production asset is replaced until
that candidate is frozen and its measured coverage supplied.

The bounded shared extension is an optional per-facing list of
`{distancePx, sourceFrame}` contact measurements on a finite media track. It
replaces Poison's fixed per-facing time maps. Actual palm-to-body length divided
by the complete authored pixel scale supplies source-space distance. Interpolate
the measured contact frame, then sample the ordinary start/contact/end segments.
The contact time comes from the compiled application relative to media start;
the existing release + 400 ms remains one camera-independent timestamp. Export
data never moves that contact or native outcomes. No spell-ID branch, pixel scan,
new registry, state field, range-bank selector or detached-projectile substitute.

Acceptance: fixed scale/palm anchor, literal JSON roundtrip, distance interpolation
and deterministic monotone seeking, contact-frame sampling at the same logical
time for every camera/zoom, then real saved near/far axis/diagonal clips from both
perspectives. Actual source coverage at contact must be checked separately from
the mathematical interpolation. Beyond supplied measured coverage is an explicit
asset limitation; it does not authorize stretching or extrapolating reach.

Anti-slop reviewer `/root/graphics_antislop` and anti-OOP/ECS reviewer
`/root/graphics_ecs_review` both approved this scope. They rejected near/far banks
as unnecessary discontinuities and moving the existing emitter-bound puff as a
detached projectile. The source correction is a dependency, not evidence that
the new artwork already works. Support-spell integration remains deferred while
this user-prioritized correction is completed.
