# Cloud propagation — implementation unit

September 30. The user authorized implementation after narrowing the combined
[cloud/window design](CLOUDS_AND_WINDOWS_BACKEND_DESIGN_2026-09-30.md).
The user clarified that the cloud rendering is already okay: this unit fixes
backend spread around walls/openings and subsequent door handling. The approved
renderer stays unchanged. Windows follow after this unit; their handoff is saved.

## Behavior and boundary

Fog Cloud, Cloudkill, Stinking Cloud, Incendiary Cloud, Darkness and Insect Plague
use the existing connected area propagation at creation and actual movement,
within their existing spherical footprint. A closed boundary blocks initial
spread; an opening allows connected spread around corners within the radius.

An established cloud keeps its occupied cells when a door opens, closes or breaks.
Those changes still affect current sight and wall occlusion. Existing duration,
movement, turn triggers, damage, wind, concentration and Globe rules retain their
owners and timing. The backend does not recalculate occupancy on a door change.
Recorded subjective events remain sufficient for the existing passive playback.

Input: real casts, movement/turns, door actions and complete subjective lineages.
Output: resolved native cells and mechanics, serializable observed state, and
matching replay with preserved XYZ, wall occlusion, moving map-edge fringe and
Globe visibility/exclusions.

## Work

1. **Native data.** Add the existing typed propagation policy to the area owner;
   select connected in these six zone definitions and use it in shape creation.
   Inspect their casting/discovery paths to keep any actual footprint preview
   consistent. Keep other area definitions unchanged.
2. **Recorded facts.** Carry this policy with existing spatial observations,
   geometry, resolved cells and native suppressions through the current event
   serialization/reducer. Keep old recordings readable and replay their recorded
   facts. Do not add an objective-world snapshot or change visibility rules.
3. **Preserve rendering.** Use the approved renderer unchanged. Replay the
   recorded outcomes; do not change XYZ, clipping, frame clocks, assets or
   geometry authoring. No current renderer defect is part of this request.
4. **Validation and review.** Add native behavior and passive replay regressions,
   run relevant existing tests, and replay reference cloud cases. Generate a small
   review with both observers and all four cameras, including new cast/door
   narratives. Independently review the implementation for anti-slop/correctness
   and ECS/anti-OOP before reporting completion.

## Acceptance

- All six native zones reach connected cells around a corner within radius;
  a sealed boundary prevents initial spread. Resolved state and any native
  preview agree under the existing subjective visibility rules.
- Cast through an open door, then close/open/break it: occupied cells and zone
  identity persist; geometry changes cause no new cloud damage or footprint event.
  Current sight/light changes normally. A real subsequent movement resolves its
  new footprint and existing turn/entry effects still work.
- Saved events replay after resetting the engine, retaining only each observer's
  permitted cells, geometry and protection facts. No renderer-native lookups.
- Far-side occupancy remains native game state after door closure, independently
  of each observer's changing visibility. Verify native damage/condition behavior.
- Preserve approved static/moving open-map edge, real-wall edge, raised support,
  Globe overlap and removal clips. New clips use the same event-driven harness.

No window/attack/light changes, other AoE migration, cone/line solver repair,
vertical/Cylinder policy, new artwork, asset repacking, multi-Z or new test
framework in this unit. Shared changes get existing consumer regressions rather
than expanding feature scope. Read HOW_TO_TEST.MD before writing tests.

Review: both independent reviewers approved the cloud-only native plan. The
subsequent user correction removes renderer changes from scope. Final code review
and validation results follow.

## Completed backend — September 30

The shared area owner now carries the existing `line_of_effect | connected`
policy, with `connected` authored for the six zones above. Shape creation and
actual movement use that policy. Spatial observations serialize it as an optional
typed field; historical recordings retain their original cells and default to no
recorded policy. No solver, door handler, renderer or asset was changed.

Validation on the final backend-only diff:

- **121 passed:** new native/replay regressions plus existing spatial condition,
  movement, suppression, spell-fact and Globe tests. Real Cloudkill damage reaches
  the corner cell only through an initially open route, continues after door
  closure, and native turn movement resolves its next connected footprint.
- **244 passed:** existing area surfaces, scene occlusion, volume ownership and
  spatial-field media tests with the approved renderer unchanged.
- Touched backend Pyright: **0 errors, 0 warnings**. Diff whitespace check clean.
- Independent anti-slop/correctness and ECS/anti-OOP reviewers approve. The
  correctness review requested the real damage/movement tests; these were added
  and approved on a second review.

The [eight-clip review](http://127.0.0.1:8767/runs/20260930T205448Z-f7eb73/index.html)
contains Cloudkill beside a wall, Fog Cloud at a real wall edge, Fog/Globe overlap,
and Insect Plague cast → close → reopen → close → attack door until destroyed →
end concentration. All are native actions recorded once, then replayed from
public events for both observers and four cameras. All eight clips pass their
consistency checks with no missing presentation bindings, across **3,326 frames**.
Representative wall, Globe, open/closed/destroyed door frames were inspected.

### Observed visual follow-up, outside this backend-only change

The new door narrative exposes an existing compositor limitation at about
**3.3 seconds**: closing the door hides Insect Plague on the caster side even
though the received observation still includes those cells and native damage
continues. `compose_volume` currently recomputes source reachability against
current barriers as well as doing camera occlusion. This unit deliberately does
not change that approved renderer. A follow-up must distinguish retained native
occupancy from camera occlusion; the clip is evidence, not visual approval.

Windows remain the next separate backend feature. Their handoff is
`/home/tommaso/Dev/terrain-prefab-study-2026-09-24/window-inventory/BACKEND-HANDOFF.txt`;
no window or multi-Z implementation was included here.

## Human review correction — inset-wall cut is not accepted

The user marked `persistent-cloudkill-wall`, camera 0 at approximately
2.956 seconds: the cloud has an unnatural cut above the wall. Passing tests and
unchanged renderer source did not establish that this visual result was correct.
The prior completion report overstated acceptance.

Read-only diagnosis (no production changes during this investigation):

- Six relevant renderer modules, including the painter, fixture depth, volume
  composition and field ownership, equal commit `db78d05baf9` after ordinary
  newline normalization. The temporary earlier renderer edits had been reverted.
- The approved `cloud-boundary-cloudkill` recording has walls at x=14, at the
  map edge. The reported `persistent-cloudkill-wall` places them at x=11, inside
  the cloud. These are not interchangeable regression controls.
- Replaying the old inset-wall input from `20260924T092816Z-e2a9fc` and the new
  input at the same static media sample shows the marked cut in both. Their
  observed cloud cells change from 36 to 37; only (12,5) is added, none removed.
- A clearly isolated diagnostic that bypasses cell admission removes the cut.
  This identifies the ownership/admission boundary, **not a safe fix**: admitting
  all cells would discard subjective visibility. It was not saved as a gameplay
  recording or added to the review gallery.

Evidence is in `.runtime/cloud-wall-regression-20260930/`: `old-inset.png`,
`new-inset.png`, `approved-wall-reference.png`, `reported.png`, and the diagnostic
script. The unresolved issue is how permitted volume geometry gets cut by ground
cell admission before XYZ wall composition. Do not change visibility rules or
introduce another renderer patch on the assumption that broader admission is
authorized. Keep this issue separate from the established-cloud/closing-door
reachability problem documented above, and preserve both concrete reproductions.

## Authorized XYZ wall repair — September 30

The user explicitly authorized fixing the marked holes with existing XYZ data.
This expands the preceding backend-only scope to this concrete presentation bug.

Input: the same real inset-wall cast and paired saved-event views; unchanged art.
Output: the cloud's exposed upper volume survives, real wall pixels still occlude
it, and hidden ground/actors remain hidden. Map-edge movement and Globe controls
must retain their approved behavior.

Implementation: retain full-column observations unchanged; add optional cold
`upper_volume_surfaces` with per-cell lower height planes for already established
obscuring fields. Native occupied cells, optical radius, light and other-owner
obscuration remain the gates. Finite boundary tops give conservative clearance
from the observer's existing support elevation, without introducing eye/body
height rules. Corner rays select intersected segments; planes conservatively
apply across each granted cell. These are permissions, not new ground visibility,
Globe-surface grants or hidden wall snapshots. Recompute/clear with perception.
The shared XYZ sampler evaluates those planes before existing camera occlusion.
Maintained fields use already resolved occupancy rather than recomputing source
reach after a door closes; instantaneous effect propagation remains unchanged.

Both independent anti-slop/correctness and ECS/anti-OOP reviewers approved this
bounded extension. Required validation: native upper-only admission and tall wall,
range/other-obscurer exclusions, cold replay, numerical XYZ probes, same marked
clip plus edge/movement/Globe/door controls. Do not label checks as visual approval.

### Wall-cap review and ad-hoc options

The user accepted that the hole is gone, then rejected cloud pixels covering the
stone cap and requested drawing the wall above the cloud in that situation.
`boundaryOcclusion: field` is authored for the six clouds; a registered boundary
in front of the field origin preserves its complete silhouette. The ordinary
per-sample policy remains the default for other media. Actual doorway holes and
translucent edges retain their alpha.

The [ad-hoc comparison](http://127.0.0.1:8767/cloud-wall-options-20260930/index.html)
shows A (sample depth) and B (foreground wall silhouette), at two media samples
from the same saved cast state and four cameras, with wall close-ups. These are
clearly identified still-image proposals, not replacement gameplay recordings.
The camera-0 held-cloud probe changes **zero opaque wall pixels** under B; A
changed 2,908. Both retain the upper-volume repair.

The correctness reviewer also reproduced stale upper sight after a tall door
behind a low wall closed. Upper sight now subscribes privately to tested route
dependencies, including rejected candidates; close and reopen update through
ordinary native events. Added a real close/reopen regression without manual
perception refresh. This subscription change grants no floor/actor visibility.

Validation after the repair and wall-policy addition: **241 passed** across the
native cloud, player replay, real-art wall/door, XYZ, moving field and ownership
suites; **100 passed** in the separate native spatial/Globe and player suppression
control run before the final wall display policy. Scoped production Pyright:
**0 errors, 0 warnings**. Both independent reviewers now approve their respective
permission/lifecycle and presentation-policy surfaces; the latter independently
passed **136 scene-occlusion tests**. Human visual feedback on A/B is still pending.
No art repacking, window work or backend ground/actor visibility changes were made.

### Human refinement — corners retain XYZ depth

The A/B feedback prefers XYZ sample depth at wall ends/corners and wall-first
composition where the finite wall fully blocks the cloud. Refine the same `field`
policy: a foreground wall overrides sample depth only where the field-origin to
sample segment crosses its actual finite connected interval. Else preserve sample
depth. This affects only overlapping wall artwork; it does not trim cloud volume,
re-run propagation, change occupancy, or introduce another authoring mode.
Input/output proof: same saved cast and cameras in a C comparison, plus numerical
end/corner probes and the existing actual-art wall/door and XYZ suites. Both
existing anti-slop/correctness and anti-OOP reviewers review this refinement.

C is implemented and rendered in the same comparison (camera 1 selected by
default). A/B images remain unchanged. The real-art wall/door and numerical XYZ
suites pass **185 tests**; scoped Pyright has **0 errors, 0 warnings**. Tests cover
both finite ends, exact endpoint rounding, continuous wall seams versus gaps,
and all four camera rotations. The anti-OOP reviewer independently passed all
12 new endpoint/seam cases and approved the final code. No native state, asset,
permission or propagation changes were included in this refinement.

### October 1 — authoritative occupancy and the remaining cutoff

The human judged B/C effectively identical, confirmed **A at camera 1** and
**B at camera 0** as the desired references, and asked whether the cloud actually
occupies the disputed corner. C is not visually accepted.

The new [coverage artifact](http://127.0.0.1:8767/cloud-wall-options-20260930/coverage.html)
reads the saved native creation event, not a reconstructed circle: **49 occupied
cells, including 13 with x ≥ 12**. Six wall segments form x=11.5 over y=5.5…11.5.
The occupied route `(10,8) → (10,5) → (11,5) → (12,5) → (12,8)` goes around the
open end. The artifact supplies exact tile overlays for four cameras, a top-down
map, and the recorded facts. The shorter route notation here abbreviates its
cardinal steps; the artifact draws each step.

Recentring the camera with a larger viewport does not remove the right-hand cut.
The recorded caster is at `(3,6)`: it receives 37 full cloud columns and upper
surface permissions behind the wall. A diagnostic which supplies all 49 native
cloud cells removes the cut without changing the ground or actor state. A
separate finite observer-to-sample ray probe retains the cut: this is not fixed
merely by making the boundary's endpoints finite. Cloud surfaces genuinely
hidden from the caster are being removed before another camera views the cloud,
exposing a cross-section. Whole-field wall priority then cannot restore them.

The complete-cloud comparison is explicitly labelled an objective diagnostic,
not a gameplay recording, permission grant, or proposed production rule. It also
shows why treating the whole wall as completely separating the cloud was an
incorrect premise: the native connected field occupies both sides. Resolving
that presentation/observation distinction needs the human's guidance before
changing the existing visibility contract. This diagnostic made no production
code changes and did not rerun gameplay or replace the saved events.

### October 1 — human closes the visibility discussion: black unseen cut

The user chose to retain the current visibility and move on, asking that the
unseen part blend into the black map instead of showing through to background.
This supersedes the pending full-cloud-versus-caster-sight question.

Requested behavior / boundary: saved player state into the shared XYZ field
sampler; the currently removed lower surface below an existing upper-only grant
becomes the same near-black as the unseen map. Visible pixels, native footprint,
ground/actor sight, wall occlusion and unknown columns do not change. The existing
RGBA alpha preserves formation/removal fades. No new authoring field or native
event is needed. `UNSEEN_COLOR` is shared with the map background through the
existing passive draw-values module; no import cycle or new framework.

The existing numerical XYZ regression was first updated to this requested
behavior and failed on the missing black pixel. It now verifies black hidden
height, unchanged visible color, no unknown-column disclosure, four cameras,
two elevations and fractional motion. Ownership/movement, real-art wall/door
and XYZ suites pass **230 tests**, with **0 typing errors or warnings** in the
three touched production modules. Recentered before/after images were inspected
in all four cameras; camera 0 now joins the unseen black area while retaining
the wall. The [comparison](http://127.0.0.1:8767/cloud-wall-options-20260930/unseen-black.html)
preserves the old samples and uses the same saved player input.

The [refreshed paired clips](http://127.0.0.1:8767/runs/20260930T221044Z-3049d2/index.html)
pass **2/2 cases**, at 32 FPS in all four cameras. Both sequences were compared
directly with the saved inputs and are unchanged; this was replay, not a new
simulation. The encoded camera mosaic was also inspected around the marked cut.


### October 1 — black-mask experiment removed at the user's request

The user rejected movement artifacts and subsequently ordered removal of the
black fix and an end to cloud iteration. Restored the pre-black renderer: no
black replacement pixels, no unseen-surface composition pass, and no new
before/after movement-permission sampler. Removed the tests specific to that
canceled experiment; retained the existing XYZ ownership, upper-surface and
moving-edge tests. Earlier native cloud propagation and wall handling remain.

The black gallery and the intermediate movement captures are rejected historical
experiments. They do not represent the restored code. The previous paired replay
`20260930T221537Z-b0d2c5` was generated with the restored pre-black behavior.
The stopped experiment is locally preserved under
`.runtime/cloud-black-mask-rejected/`; it is not production code or a pending task.
Do not resume cloud-mask work without a new user request.


### October 1 — rollback was incomplete; repair moving sight without black

The user rejected the pre-black replay as still broken in movement. The rollback
had restored an intermediate state, not the accepted moving renderer: the new
upper-plane mask still used destination coordinates, and the field-center wall
policy changed ordering as the center crossed the wall. Both predated the black
fill. The prior completion claim was wrong.

Removed the field-center wall policy, its six bindings, authoring field and
policy-specific tests. Restored normal XYZ sample depth. Kept the separation
between established native occupancy and current camera occlusion.

Moving sight now uses the recorded before/after permissions at displayed XYZ.
Fringe ownership remains separate and follows the current sphere, including the
map edge. Future upper grants are bounded by the current sphere's height; they do
not appear at departure. This also fixed a smaller camera-3 future-fringe grant.
No black pixels or extra composition pass remain. The correction changes neither
native perception/occupancy nor assets, frame timing, observers or saved inputs.

Regression checks include actual wall-cast departure, the first nonzero moving
instant, arrival, a low/high XYZ probe crossing the wall sight plane, and the
existing four-camera fully observed moving-edge artwork equality and fixed Globe
exclusion checks. The experimental black code remains archived locally only.

Validation: **225 tests passed** across movement, field ownership, XYZ, actual-art
scene occlusion and cold cloud replay; the strengthened departure/arrival subset
was rechecked after adding the final pre-arrival equality assertion (**5 passed**).
Touched production Pyright reports **0 errors, 0 warnings**. The saved wall replay
was visually sampled across both movement intervals, rather than only at rest.

The [replacement review](http://127.0.0.1:8767/runs/20260930T224312Z-ab00bf/index.html)
contains **4/4 passing saved-event clips**: wall crossing and the previously
accepted open-edge movement, each from both observers and all four cameras at
32 FPS. All four embedded event sequences equal their saved inputs. No scenario
was recaptured or changed to hide the defect. Visual approval remains with the
human; the prior pre-black rollback clip is superseded.

### October 1 — retain the hidden wall face over upper-only cloud

The user identified stone overwritten at 6.482 seconds in the new wall replay,
then clarified why: the isometric camera exposes wall faces on a side the
character cannot see. Existing upper-surface grants expose the cloud above that
side, not foreground cloud in front of its stone face. Fully observed cloud in
the opposite camera views legitimately covers the wall.

The received full/upper-only distinction now reaches the shared XYZ compositor.
The registered stone silhouette covers upper-only samples along its finite edge;
normal XYZ remains for fully observed samples and exposed corners. The same
moving permission calculation supplies the distinction during translation.
No authoring field, new backend permission, black pixels or field-center policy
was introduced. Actual wall pixels, openings and translucent edges still own
their normal alpha composition.

Two real native-cast regression cases failed on the previous renderer and now
pass. Added coverage preserves fully observed foreground cloud, finite ends and
transparent/partial/opaque wall pixels. The departure/arrival checks now also
exercise actual wall artwork in all four cameras. Their first run exposed only
irrelevant RGB in alpha-zero pixels, not visible motion differences; the test
normalizes those before comparison. Validation: 232 cases passed in the broader
run, then all nine movement checks passed after that test correction, covering
234 distinct cases overall. Production typing and whitespace checks pass.

The [paired wall replay](http://127.0.0.1:8767/runs/20260930T230008Z-93ff39/index.html)
uses the unchanged saved events, both observers and four cameras. Both movement
intervals and the marked static moment were inspected. The user has not yet
approved the replacement output.
