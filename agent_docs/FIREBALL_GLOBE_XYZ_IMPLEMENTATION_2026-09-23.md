# Fireball propagation and Globe XYZ integration

User-authorized scope: finish native Fireball propagation, shared Globe spell
suppression and their production Pygame presentation. The accepted Godot sources
are `output/weapon-vfx/handoff-globe-fireball-unsent/{HANDOFF,XYZ_FOLLOWUP}.md`
in worktree `1aac`. The user's September 23 dispatch supersedes their old unsent
label. Coordinate new exports with task `01a0b6af-5fa9-7ec0-9915-0ecee0a6baec`.

## Observable contract

* Fireball alone opts into connected propagation inside its original geometric
  radius. Traverse existing open cardinal propagation edges. Closed walls block;
  an open doorway permits lateral spread around its corner. No doorway radius
  reset, center-ray substitute, or change to unrelated spells.
* Native recipients and Ashen surfaces use the same admitted cells. Subjective
  events retain their existing visibility rules and complete lineages.
* Globe blocks eligible spells from outside, using base spell level, including
  cantrips. It is neither terrain nor untargetability. Inside-source spells and
  sufficiently high-level spells work. Outside-to-outside travel remains valid.
* Partial AoE suppression does not cancel the whole cast. Record the responsible
  protection and affected region on the actual event; a missing public cell is
  never evidence of protection. Ice Knife's unpaid burst must obey the same
  protection without becoming another cast or Counterspell opportunity.
* Production consumes authored paired color/XYZ media. Fireball keeps its
  approved projectile, trajectory, impact time and phase duration. Impact banks
  change with camera; the explosion receives no residual screen rotation.
* Globe uses accepted golden far/near shell layers, apply/hold/clear timing and
  the accepted nearest-diagonal contact response. Responses come from native
  suppression facts. Clear continues the held phase while fading.

## Ownership and implementation sequence

1. Extend the existing AoE shape data with an opt-in connected propagation
   policy. Reuse map propagation edges; no new physics engine or cache hierarchy.
2. Extend SpellEvent with passive attributable suppression records. The existing
   Globe handler filters area footprints at EFFECT and cancels protected target
   applications at their existing phase, including unpaid EFFECT applications.
   Reuse immutable source-position provenance. Public projection discloses only
   observed protection/positions, preserving existing subjectivity.
3. Extend existing projectile storage/registered-media sampling for paired XYZ
   packets. Preserve dense source frames on disk; decode only requested frames
   with a byte-bounded cache. No startup media scan, hashes, manifest audit, or
   eager asset decode. The 5.7 GiB source delivery is assets, not generated code.
4. Add shared XYZ composition to the existing draw-command pipeline: native
   reach owns ground admission; continuous registered samples handle finite
   boundary occlusion and eligible Globe exclusion. Preserve smoke alpha then
   additive fire, unknown-owner color, shared canvas registration, and source
   local vertical conversion. Do not combine the old ground silhouette mask
   with the XYZ compositor, and do not stencil the art into square cells.
5. Import accepted Globe layers through existing maintained spatial media;
   author cast/condition/response bindings as data. Reuse lifetime sampling and
   the presentation clock. No bespoke spell animation executor.
6. Produce saved-native-event reviews from both observer perspectives and all
   four cameras. Keep ongoing Godot XYZ work coordinated; later exports use
   this data contract, not new rules for each export.

## Acceptance and validation

Native scenarios: open/closed doorway, solid wall, L-wall and corridor; bounded
radius; direct low/high/upcast spell; inside/outside source; partial Fireball with
protected damage and floor residue; Ice Knife adjacent protected burst target;
Globe concentration removal. Compare exported reference connected-cell sets.

Replay: serialize once and run with no native live-state lookup. Suppression
provider survives only when disclosed. No hidden zone identity/geometry leaks.
Presentation: inspect all four cameras, front/back wall visibility, smoke/fire
layering, shell exclusion (not an oval screen cutout), shell contact direction,
formation/hold/clear, intact projectile timing and body anchors. Include a
timed representative decode/render sample, measuring costs separately from
native gameplay. Existing focused suites protect neighboring spell behavior.

## Review gates

Before implementing the contract, obtain anti-slop and anti-OOP/ECS reviews.
Record concrete corrections below. Reviewers should reject duplicate authority,
spell-name renderer branches, indiscriminate spell-rule changes, oversized
frameworks and hidden-information leakage. Source limitations (one nearest
surface per smoke/fire layer; four directional membrane responses) remain
explicit instead of being hidden by approximate hacks.

## Status

Both required reviews approve the architecture with concrete corrections now
included: honor center blockers/map holes; share connected propagation with the
optimized discovery path; retain Ice Knife's explicitly dispatched EFFECT
events; freeze effective emission separately from caster presentation position;
use immutable provenance for zone protection; disclose providers only from
received spatial observations. Implementation and focused verification are complete; the production gallery is ready for human visual review.


## Delivered behavior and review corrections

The production gallery contains 20 paired subjective clips, each displaying all
four cameras at 24 fps:
http://127.0.0.1:8767/runs/20260923T160308Z-1dfea8/index.html

Experiments cover Fireball intersecting the Globe edge, impact centered inside,
a separated control, an inside-source cast, a blocked Fire Bolt, Ice Knife's
secondary burst, and the solid wall/open doorway/L-wall/corridor fixtures.
Each experiment is generated with real discovered actions and saved once. The
renderer consumes serialized player events; native runtime is reset before
cold-replay tests. Formation, held shell, contact response and concentration
removal are exercised. Damage and Ashen are native results, not clip scripting.

Both final anti-slop and ECS reviewers approved after these concrete fixes:

* Rotate source **vectors**, not positions around the map center. A numerical
  four-camera exclusion test now catches the original three-camera error.
* Explicit Ice Knife EFFECT dispatch uses existing `post(use_register=True)`.
  Successful ordinary and protected application lineages all complete; canceled
  applications retain their actual cancellation.
* Carry already disclosed solid tile/item footprints into continuous obstruction
  outlines. Existing item height supplies finite camera occlusion; solid tiles
  without authored wall height provide topology only. Do not invent hidden holes.
* Globe's native visible-presence capability is enabled. Its shell is now an
  ordinary sensory observation, so public suppression attribution and visual
  state agree without a private registry query.
* Additive depth partitions clear excluded RGB as well as alpha. Otherwise the
  additive blend would duplicate supposedly removed fire across painter slices.
* Shell response tails extend blocked spell attempts only. Ordinary ground
  contact media retain their existing movement timing; regression tests caught
  and removed an overly broad duration extension.

Final verification: **218 selected tests passed**, including native rule tests,
residue/condition/sensory tests, cold public replay, existing interruptions,
maintained area media, packet decoding, cache bounds, additive partitioning and
four-camera geometric tests. All 20 captured clips pass their replay/state/frame
checks with **zero presentation gaps**. Changed production modules and new tests
pass scoped Pyright. These are implementation checks, not a claim that the human
has visually approved the new production captures.

## Measured gameplay and rendering cost

The timing diagnostic exposed an existing expensive Ashen cascade: every residue
membership forced a complete observer/contact solve. A 49-cell blast made 196
observer solves with four actors. Globe's optical-route presence amplified this.
The fix reuses the existing current observer field for the existing tile-residue
capability and refreshes only the affected cell's hazards. Optical/light/
propagation and occupancy guards remain. Each native condition and sensory delta
keeps its original completion point; no batching or deferred observations were
introduced. Ordinary non-residue conditions retain their prior route. The ECS
reviewer approved this narrow change, and poison addition/removal is compared
against an explicit full sensory refresh.

WSL Python 3.13.12, source on `/mnt/c`, four actors on 24×17 supports, with the
review recorder running concurrently:

| Measured operation | Before | After |
| --- | ---: | ---: |
| Protected Fireball, no profiler (includes damage/Ashen/events) | 2259 ms | 343 ms |
| Fireball without Globe, profiler enabled | 3767 ms | 484 ms |
| Fireball with Globe, profiler enabled | 6199 ms | 576 ms |
| Fireball without Globe, no profiler | not recorded | 188 ms |

Separate presentation sample: requested smoke/fire pair cold decode/registration
61 ms; cached pair registration plus spherical composition median 14.9 ms,
maximum 17.6 ms over 12 samples (603×446 displayed pixels/component). Decoded
source residency for that pair was 14.44 MiB. Authoring-data load measured 2.50 s
on the mounted source while recording. These are scoped measurements, not a
whole-game frame-rate claim or native-source filesystem benchmark.

## Boundaries and continuing handoff

The retained full Fireball delivery is about 5.7 GiB of paired binary media;
Globe pages are about 25 MiB. Only requested frames are decoded. No runtime asset
scan, hashes or source audits were added. Source color/alpha, component order,
pivots and sample registration remain authored. The shared schema extension is
recorded in `game/data/PRESENTATION_CONTRACT.md` for a later TS consumer.

This is registered nearest-surface composition, not a volumetric reconstruction.
Unknown ownership keeps its authored color; unknown world geometry stays unknown.
Four directional contact banks have a fixed contact altitude. Native reach owns
rules; the continuous renderer handles disclosed physical surfaces and finite
camera occlusion. No general flight, stacked-floor or 3D spell-rules refactor is
included.

The Godot author confirmed no further approved rule change beyond Fireball C and
Globe protection. Their seven-effect XYZ comparison batch is separately under
review; it does not authorize copying Fireball propagation onto other spells.

Latest author confirmation: the seven-effect **local review package** is complete
at `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/aoe-surface-export/HANDOFF.md`,
with `DATA_CONTRACT.md` alongside it. It contains Burning Hands, Gust of Wind,
Thunderwave, Shatter, Color Spray, Sleep arrival mist and Ice Knife burst, with
full-resolution RGBA/XYZ/owner packets under `delivery/` and previews under
`preview/`. The author reports 22,560 validated packets, 112 spell/wall/camera
comparisons and seven checked cached loops. These are author-reported checks,
not production integration or user acceptance.

Review: <http://127.0.0.1:8784/aoe-surface-review/?review=paired-seven-v2>;
contact sheets: <http://127.0.0.1:8784/aoe-surface-review/contact-sheets.html>.
User visual acceptance and per-spell event/area integration review remain pending.
The author explicitly says this status reply is not a production handoff; this
batch has not been integrated. Diagnostic C comparisons do not approve new rules;
`footprints.json` records footprint exceptions. Component ownership is surface
ownership, not deep volume. Reported unassigned antialias fringes: Ice Knife
1.555%, Shatter 0.559%, Color Spray 0.414%, Burning Hands 0.022%; others 0%.

Continue coordination with Godot task `01a0b6af-5fa9-7ec0-9915-0ecee0a6baec`.

## Fireball flicker correction — September 23

The human's playback review exposed a real renderer defect missed by the earlier
state and geometry checks. Requested behavior: retain the authored explosion
appearance throughout playback. Boundary/input: the same paired RGBA/XYZ frames
and saved public event clips, composed by the production world painter. Expected
output: stable smoke-before-additive-fire ordering while world objects and Globe
still occlude the appropriate depth bands.

The export contains all 288 native samples per bank. Production selects its
existing 48-frame schedule; missing exports were not the reproduced cause.
The before/after `globe-fireball-edge` draw traces both contain every impact
frame 0–47 once, in order, across 48 video frames at 24 fps. No impact samples
were skipped or repeated by that capture.
`split_world_depth` treated the smoke and fire components as each other's world
occluders, then sorted their fragments by independently changing mean depths.
This reversed blend order over time. A no-obstacle comparison of six real source
frames changed 3,024–27,927 pixels at 0.35 scale, visibly darkening some frames.

The correction adds one passive optional draw group for components of an authored
composite. Group members share the union of external overlapping depth cuts,
exclude their siblings as occluders and retain authored component order within
each stable depth band. No external peers means the original composite is kept.
The existing ungrouped fixture/terrain path is unchanged. No source pixels,
export, phase duration, sample schedule, gameplay rules or event timing changed.

The six source comparisons now have zero differing pixels. The regression first
failed before the fix and covers moving component depths, conflicting identities,
opaque world peers and unequal cropped layer bounds. The selected presentation
suite passes **95 tests**, and changed modules pass scoped Pyright. Anti-slop and
ECS reviewers both approved; the anti-slop reviewer independently verified the
15 XYZ tests and six real-frame comparisons. The Godot author was informed that
this defect does not require new exports.

Fresh [20 paired four-camera replays](http://127.0.0.1:8767/runs/20260923T175550Z-17c120/index.html)
all pass with zero presentation gaps, using the same saved inputs. Selected
sequential explosion frames and four-camera Globe-center, solid-wall and doorway
frames were visually inspected. A [before/after comparison](http://127.0.0.1:8767/runs/20260923T175550Z-17c120/fireball-layer-order-comparison.mp4)
retains the same event, camera, clock and 24 fps; old rendering is on the left.
The original run remains available as evidence. These checks are not a substitute
for the user's visual acceptance.
