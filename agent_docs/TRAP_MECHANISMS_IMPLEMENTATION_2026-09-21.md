# Delivered trap mechanisms and grounded triggers

This implements the delivered-art portion of
[the reviewed trap plan](TRAPS_AND_TRIGGERS_PLAN_2026-09-20.md). The user corrected
the earlier priority: completing the portal backend did not complete that plan,
and portal artwork must not hold up the traps whose sprites already exist.

## Native behavior

- **Pressure plates:** one field owner stores its footprint, pressed state and
  exact private connection. Indexed departure/arrival handlers query current
  grounded occupants. First contact presses; last departure releases. Walking
  within a larger plate does not retrigger it, and a deployed corpse still
  supplies pressure. Jump takeoff releases, airborne crossings do not press,
  landing presses, and teleport only contacts its real endpoints.
- **Held controls:** the same native door/light operations serve levers and
  plates. Closing a door still checks occupancy. If occupied, the plate releases
  while the door retains one pending close request. The next relevant departure
  retries under that new lineage. A newer request supersedes the old one; no
  global scan or fabricated operator action is involved.
- **Darts, blades and crushers:** one finite resolver accepts passive lane or
  local-area geometry, avoidance save and damage/coating payload. Darts stop at
  the first reached obstruction or creature. Activation is a native event even
  when the fixture returns to Ready without a lasting state change. Art does
  not decide damage, affected cells or rearming.
- **Jaws:** grounded contact closes the jaws even when the creature avoids them.
  A failed save causes damage and an exact-source mundane restraint. The
  captive receives ordinary action-costed Athletics/Acrobatics escape choices.
  Escape does not reopen the hardware; reset does. Closed jaws do not bite on
  every crossing. Removing/resetting the owner releases only its own capture.
- **Tripwires:** a concrete adjacent-cell boundary is the input geometry.
  Accepted grounded walking/forced movement across that edge pulses its exact
  connection. Walking alongside it, deployment, airborne crossing and teleport
  do not count as crossing the wire.
- **Gas vents:** each release creates an independent stationary cloud with an
  authored footprint, duration, save, poison damage, Poisoned duration and
  optional obscuration. Appearance, entry and turn-start share the existing
  per-turn exposure fence. Disabling/removing the vent does not erase released
  gas. Native wind dispersal and same-gas overlap replacement apply to the cloud;
  untouched cells of an older cloud retain their own remaining lifetime.
- **Existing lever use:** finite mechanisms, jaws and vents expose Deactivate,
  Arm and Reset through the existing action identity. Spike and portal lever
  semantics remain their own authored state transitions.

These fixtures use the existing overlapping FIELD lifecycle. They do not replace
spike/residue surface ownership. Connections remain backend data: a client sees
the permitted facts of a press, activation, door state or injury, not the private
target reference that wired them together.

## Shared restraint seam

Web and jaws retain separate source memberships while sharing the public
Restrained mechanics. The shared manifestation is source-neutral; magical versus
mundane provenance belongs to the exact source. Ending one source preserves the
other, and an unrelated preexisting standalone restraint is not claimed or
deleted by the leases. Freedom of Movement's existing escape path releases an
eligible mundane lease for its native cost without erasing a remaining Web.
Antimagic removes/suppresses the magical source while a mundane jaw still holds.

This is a bounded correction to the existing membership owner. It does not add
another condition system or revise general immunity/stacking rules.

## Recorded presentation

`MechanismActivationEvent` records the actual mechanism, origin, direction,
accepted affected positions, reached endpoint and committed result. Public
projection retains only granted fixture identity and geometry. In particular,
a visible dart segment remains present when its launcher is hidden. A visible
gas release does not erase itself merely because its cloud obscures the vent
before completion. These use the event's own retained sensory evidence, not the
outer action's earlier sight.

All media enter the existing asset/prop catalog. The accepted Workshop v7 cells
remain at their delivered registration. Authored activation/contact frames and
separate plate press/release sequences drive the normal presentation clock.
Dart sprites use the provided directional art and source socket, with the
existing rig body/rest attachment as their target. Native consequences bind at
the authored strike or projectile arrival. No backend sleeps or animation cues
were introduced into mechanics.

Tripwire art is placed once at its disclosed boundary anchor, not once per
footprint cell. Jaw art holds closed until an actual reset. Its extra source
condition is explicitly state-only: the jaw prop and existing Restrained
presentation already convey capture. Escape actions reuse the retained Web
escape presentation record; a new gesture was not invented for this feature.

Three concrete replay omissions found by this work were corrected:

1. Movement visited arrival consequences but discarded departure descendants,
   losing plate release and delayed door closure.
2. A successful save or empty discharge could omit finite activation because
   the movement binder looked only for damage/condition descendants.
3. A permitted fixture change could be discarded when its moving operator was
   unseen. A reaction group can now play without inventing an operator pose.

Jump takeoff pressure release runs alongside the one existing jump arc. It does
not introduce a pause in midair or an extra jump loop.

## Review narratives

The `mechanisms` gallery selection records real game commands once, exports both
participants' public packets, resets the engine and renders those saved inputs
from all four camera corners. The selection includes:

- plate press, leave and press again for darts, blade and crusher;
- successful dart avoidance and a hidden-launcher/visible-flight case;
- held light and occupied-door release with eventual closure;
- jumping over a plate and jumping off a held-control plate;
- jaw capture, granted escape, safe closed-jaw crossing, lever reset and capture;
- successful jaw avoidance with the same physical closure/reset;
- tripwire walk versus jump crossings;
- gas release, departure/re-entry, vent deactivation and independent cloud expiry.

The gas **vent** cells are integrated. A clean maintained **cloud** asset is not
in Workshop v7; its delivery is requested from the existing Godot task after its
portal work. The recorded gas case exposes that presentation gap instead of
pretending the short baked vent puff depicts the cloud's whole lifetime.

## Validation and review

Targeted native tests cover actual mechanics and costs; replay tests cover public
serialization after reset, timing, secrecy and seekability. Human visual approval
remains separate from successful capture checks.

Independent review: `graphics_ecs_review` approved the native implementation after
68 focused checks and selected typechecks. `gore_antislop` approved projection and
cloud ownership, with 16 gas checks, seven projection checks and six recorded
narratives passing. `graphics_antislop` approved the delivered media and bounded
motion changes after 49 media checks and 12 replay checks. These selections
overlap the final aggregate lane; their counts are not additive.

The final motion review also covered a creature jumping out of an occupied
doorway after its control plate had been released. Actual closure belongs to
the first AIR-to-AIR departure from the launch cell, not the same-cell takeoff
event. It runs alongside the arc. The existing jump/OA regressions caught the
need to retain preflight reaction state while binding that earlier native subtree
within the enclosing root cursor interval; they were corrected, not waived.
The exporter now records an absent held pose as null for an unseen mover.

One older blood/spike test expectation was corrected during this run: the
already-approved spell-body work permits material release from poison as well
as physical injury. A spike with a positive physical packet and a separate
positive poison packet releases material twice. The existing floor saturation
limit remains five. No blood mechanics or approved High56 media changed here.

Portal timed presentation and movement-spell media remain separate queued work.
The rejected material-response experiments were not imported or revived.

Final native/public/media regression selection: **314 passed in 71.14 seconds**
under WSL `uv`, with source on `/mnt/c` and the native Linux virtual environment.
It includes the delivered traps, older spike controls/discovery/payloads, portal
and occupancy replay, jump/OA interruptions, visibility, Web restraints and
Antimagic. Selected changed-file Pyright checks report **zero errors**. This is
the relevant feature/regression selection, not a claim that the entire historical
repository test suite was run. Final clip evidence follows below.

[Combined saved-input gallery](http://127.0.0.1:8767/runs/20260920T231614Z-467e10/index.html):
**30/30 clips pass** at 24 FPS, each a four-camera 1600×1120 mosaic. Fifteen
native narratives have traveler and witness views. The final run consumes saved
public inputs (`input_mode: saved`), without native gameplay execution. All
capture checks pass and no binding gaps were reported. The gas description
explicitly retains the unrendered maintained-cloud limitation; an empty gap list
is not evidence that pending artwork exists. Reviewed sample frames confirm
fixture registration and directional darts; human approval is still pending.

Files persist under `.runtime/animation-review/runs/20260920T231614Z-467e10/`;
the HTML server only serves that saved directory. The earlier incomplete
`20260920T230932Z-40e542` run is superseded. The two failures there were the
review exporter's missing null check for an unseen mover's held pose, now fixed
and regression-covered. The corrected standalone door/jump recapture is also
included in the combined saved-input run.

## September 21 — successful avoidance really retreats

The user superseded the in-place dodge: a successful jaw save returns the
creature to the actual previous cell. The same behavior is an authored
`TrapSave.retreat_on_success` option on the shared finite mechanism; the blade
and crusher narratives enable it. Dart/poison saves retain their existing rules.

One shared helper finds the nearest entry of that exact target and uses its
recorded `old_position`. The existing ground-transition check and forced-movement
commit own legality, occupancy and arrival hazards. A blocked previous cell or
remote activation without an entry produces no invented step. There is no new
Jump action, opportunity attack or movement cost. Failed saves still damage and
capture normally; a jaw stays closed while the creature retreats.

Presentation requires both the exact successful save and a positive committed
forced displacement. The authored single-cycle hop goes from the received trap
contact to that actual landing; only the matching ordinary forced-movement
animation is replaced. Child hazards and pressure release play at landing, and
the remaining closure frames retain that position. Timing and height stay in
JSON; the former cosmetic horizontal distance is removed.

Validation: **51 native tests pass** (including blocked/occupied retreat,
previous-cell spikes, remote activation and costs); **49 public/movement checks
pass, with two existing xfails**, plus clean selected Pyright. These selections
overlap other reported validation. Independent anti-slop review approved the
shared native and presentation ownership. The review exporter's previous
Step/portal-only final-position check now also recognizes actual later forced
displacement instead of falsely flagging a correct retreat.

[Retreat review](http://127.0.0.1:8767/runs/20260921T001040Z-0e06cf/index.html):
**8/8 clips, 1,258 four-camera frames, no missing bindings**. Real native inputs
cover jaw failure/success and successful blade/crusher saves from both observers.
Jaw midair and final previous-cell placement were visually inspected in all four
cameras. This supersedes the earlier in-place jaw-hop clips.

## September 21 — enclosing fixture depth during injury

Blade/crusher arch sprites previously sorted as a whole at their center. An actor
at that depth could draw over the near arch according to its UUID. The delivered
RG16 ground-depth registration now partitions those fixtures around overlapping
painter depths. This uses a passive catalog registration and ordinary alpha
compositing; it does not modify actor/VFX pixels or the ordinary door path.

The reproduced camera-dependent differences were 80/528/300/540 pixels when only
actor identity changed; all are now zero for both fixtures. Regression coverage
includes front/center/back positions, contact and terminal poses, all cameras,
elevation, translucency and backward seeking. The selected depth/mechanism suite
passed 157 tests; the narrower raster suite passed 44. These selections overlap.
Both fixture injury sequences were inspected in all four cameras.

The wider `DOORS-AND-TRAPS-PRODUCTION-HANDOFF.md` is queued separately. New door
families and trap destruction behavior are not part of this correction.

## September 21 — every successful lever pull moves its handle

User review found the existing lever art did not move during several uses.
The jaw-reset recordings established the defect: the trap changed from activated
to ready, while the lever's recorded `is_engaged` remained false. The renderer
already consumes handle-state changes through the authored seven-frame sequence.
`PullLeverAction` incorrectly derived handle position from whether the requested
trap state was deactivated, so resetting an armed mechanism produced no handle
transition.

Bounded plan reviewed by `lever_antislop` and `lever_ecs`: toggle the existing
physical handle field after a successful pull and publish its ordinary item
state under the same action. Preserve trap commands, action validation, sensory
projection and the existing presentation clock. No animation cue or new state
field belongs in the backend. Finite/jaw/gas commands continue to depend on their
mechanism state; spike/portal commands retain their existing handle semantics.

Completed with a one-line runtime behavior change. Native regressions reproduce
the original failure for jaws, finite traps and gas vents; subsequent reset,
disable and arm uses move the handle back and forth. An existing veto scenario
also verifies a rejected reset leaves the handle still. Saved subjective replay
checks both observers, all seven lever poses, hand-contact timing, all four
cameras and backward seeking. Existing spike, portal, light, door and hidden
control checks remain passing. The 89 focused tests are green after correcting
the new test to assert only the requested handle behavior; scoped Pyright is
clean for the three edited Python modules.

[Lever review: 13 clips](http://127.0.0.1:8767/runs/20260921T082953Z-46a2a9/index.html)
contains fresh real-event recordings for jaw reset with failed/successful saves,
gas deactivation, spike controls, occupied portal activation and remote lights.
Every clip passes with no presentation gaps. The jaw reset's before/mid/end
frames were inspected in all four cameras. Older galleries retain their original
incorrect native handle facts and are not silently rewritten. Human visual
approval of this review is pending.
