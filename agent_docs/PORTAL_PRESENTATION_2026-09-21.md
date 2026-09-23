# Portal presentation integration

The accepted contact-trigger-v5 artwork completes the existing native portal
feature. The observable boundary is saved public event playback: a clothed actor
walks/jumps onto the hatch, it opens, the actor falls through, and an authorized
exit opens before arrival. Camera changes and seeking keep the same clock.

Use a passive PortalTransferCue, bound only to committed PortalTransferFact.
Start/end permissions are independent. A blocked crossing may open the hatch
through SpatialEffectStateFact but has no fall or exit. Preserve native jump
landing and movement costs. No presentation data enters the engine.

One small JSON catalog owns the accepted atlas registration, phase windows and
transfer markers. Maintained entrance art follows received trap_state. The exit
is a finite accent of a successful crossing, not another native portal. Missing
camera banks must be exported from the actual Godot source; never mirror q0.
Hatch and portal ground pivots share one world point. A falling actor is clipped
at the authored aperture and by the delivered near hardware pass. This clipping
affects that actor only and does not hide geometry intersection or other actors.

Arrival discovery and departure removal are scheduled inside the complete
lineage; no remote endpoint lookup and no fabricated actor discovery. Arrival
hazards remain real child events at arrival. Open/hold/close and body sampling
are pure functions of the same historical clock, with lazy bounded raster caches.

Validation: real walk and jump landings, bare active portal, blocked exit,
activation under occupant; traveler plus witnesses on each side of an opaque
wall; public JSON replay after engine reset; four-camera clips and seek samples.
Retain jaw/pressure-plate regression tests. Jaw hop independently requires an
explicit successful native save, not absence of damage.

ECS review: gore_antislop approved passive ownership and independent endpoint
grants, requiring blocked-crossing/no-fall and ordinary jump completion first.
Anti-slop review: graphics_antislop approved, with the observed native reveal
ordering defect fixed before capture. Opening completes before its dependent
transfer; both remain children of the still-open original movement/lever event.
This preserves complete child metadata and the existing indexed sensory hook.

Implemented: four genuine camera banks, shared pivots, state-owned entrance,
finite exit, local aperture/near-hardware actor clipping, and optional disclosed
endpoints. Departure-only jumps no longer demand a visible final actor.
Jaw avoidance uses the existing single-cycle Rolling jump pose. The user's later
correction supersedes its initial visual out-and-return displacement: a successful
save now retreats to the actual previous cell when native passage permits it.

Validation: 119 related native/replay tests pass; selected typechecks are clean.
All 17 clips pass in the [combined review](http://127.0.0.1:8767/runs/20260920T234430Z-25b076/index.html),
covering 15 portal perspectives and two jaw save perspectives with four cameras
each. The separate jaw save/failure review passed four clips. Portal frames were
visually inspected through approach, fall and arrival. No missing bindings.

The subsequent BLOOD-ONLY-HANDOFF.md integration is now complete; see
[the result](BLOOD_MATERIAL_INTEGRATION_2026-09-21.md). Its demonstration spell
behavior remains excluded.

## September 21 — original follow-up study (upright passages now deferred)

The user found the bare entrance's falling actor visibly continuing above the
floor. The current body clip incorrectly requires hatch hardware. The aperture
belongs to the portal surface; a bare portal needs its own authored aperture
registration, while the hatch's near-hardware pass remains optional. Root is
correcting that existing ground-portal path and checking actual saved clips.

The user also requests upright, wall-like entrances and exits: the body crosses
the opening horizontally instead of falling through a horizontal floor portal.
Reuse the same native Portal owner, committed transfer fact, private exit and
independent endpoint disclosure. This does not introduce a second teleport rule,
wall collision, paired-portal simulation or a view of the remote world.

Recover the accepted portal source and request an upright variant from the
existing Godot task. Deliver genuine four-camera views of one declared world
orientation, ground pivot, upright aperture polygon/plane, near-rim ownership,
open/hold/close phases and finite exit. Keep source geometry and actor passage
registration explicit; rotating the floor PNG cannot supply this geometry.
The art's opening dimensions remain presentation data, not a gameplay footprint.

Extend the existing passive portal catalog/cue only where the delivered
registration requires it: surface orientation selects ground fall versus plane
crossing; actual permitted approach/arrival contacts supply body travel. Keep
actor clipping local to the crossing actor and the exact authored plane. Do not
apply a whole foreground portal over unrelated actors, or invent an extra native
Move to animate the crossing. A blocked transfer has no passage or exit accent.

Current Portal observations carry state and footprint but no direction; the
shared PerceivedSpatialEffect already has optional direction. If configurable
upright facing is required, add only the authored native orientation and expose
it through that existing field. An exit orientation needed by arrival playback
must travel with the permitted endpoint fact, never be read from private portal
configuration. Confirm the exact small field set against the art handoff before
implementation; fixed-orientation media alone does not authorize new rules.

Acceptance: actual walking transfer with entry/exit witnesses and traveler,
blocked exit, four cameras, both sides of the upright plane, elevation, clipping
during crossing, no body before permitted arrival, and saved replay/backward
seek. Ground/bare/hatch transfers must retain their established behavior.

Anti-slop review (graphics_antislop): GO for the bounded presentation addition;
the current native transfer mechanism already supplies the rule. ECS review
(graphics_ecs_review): GO for the same owner and existing observed direction,
with exit orientation gated by the permitted arrival fact. Art delivery and upright
implementation remain pending; they are not covered by the earlier 119 tests.


## Current ground-portal follow-up

Bare entrances and all ground exits use the actual circular bank opening
(56 by 28 source pixels), represented by 28/14 ellipse half-axes. The hatch uses
its own exported 49.78032/24.89016 diamond half-axes plus the front hardware pass.
These are separate authored apertures: applying the hatch diamond to the bare
ring was still visibly wrong even after removing the hatch-only clipping guard.

Open entrances begin the fall immediately; opening hatches delay only 50 ms.
The 450 ms accelerating descent now travels 80 pixels, enough for the reviewed
clothed body to disappear completely through the aperture before relocation.
The 400 ms exit emergence reverses that shape, easing onto the floor. Shadows are
suppressed while passing through either aperture. Actual arrival discovery is
retained; arrival hazards play at emergence completion with the exit contact.
Neither camera changes nor a later draw can change the native destination.

New recordings include visible closed/open hatches and jumping into an already
open hatch. Tests check the exact jump-to-fall boundary, complete disappearance,
progressive emergence, independent endpoint visibility and immutable cached art.
The original 17-clip gallery above is historical and predates these corrections.

**Upright portals are explicitly deferred by the user to another day.**
Their design/request above is retained as background only. No upright media or
passage implementation is claimed; the Godot task has been told to park it.

The exit-onto-spikes recording also exposed a real packet-timing problem:
the traveler's arrival sensory fact, including its terrain disclosure, was nested
under exit damage. Moving the actor first left it without disclosed floor support.
The received arrival packet now enters playback intact at emergence start; actual
damage remains at settlement. No hidden terrain, previous HP or sensory state is
invented. Regression playback samples every 24 fps tick and the exact boundaries,
in all four cameras and all three perspectives, after JSON replay and engine reset.

That same received packet already contains the spikes' resulting raised state.
The renderer now holds the explicitly recorded previous pose until the native
transition's presentation contact, then plays the rise once. This removes the
observed raised/lowered/raised reset. It leaves the received state intact and
does not infer old values when a transition supplies none. Finite activation,
creation and hit cues do not acquire this prior-state hold.

The final correction passed **145 focused tests** spanning full portal playback,
spike/mechanism poses, bloodied spikes, fixture depth, jaw hops and maintained
Gust. Selected Pyright reports no errors or warnings. The earlier combined
integration selection passed **426 tests with six existing expected failures**
for raised terrain/stair-displacement occlusion. Test selections overlap and are
not totals to add together. Those terrain limits remain separate from the fixed
portal aperture and enclosing-fixture overlaps.

Final [combined review](http://127.0.0.1:8767/runs/20260921T003217Z-4b06e1/index.html):
**41/41 views pass**, 4,463 frames, each containing all four cameras, without
reported presentation gaps. This replays saved native-derived public inputs;
the renderer does not run the game again. The selection covers 27 portal views,
eight jaw/blade/crusher avoidance views, four blade/crusher injury views and two
bloodied-spike narratives. Bare entry, open-hatch jump, emergence and the final
exit-spike sequence were inspected as frame sequences. The exit spikes now stay
down during emergence and rise once at contact. Human visual approval remains
separate from automated capture checks.
