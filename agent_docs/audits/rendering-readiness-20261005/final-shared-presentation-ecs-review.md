# Frozen shared presentation — final ECS/DAG/disclosure review

2026-10-05. Source review against the shared presentation plan, with particular
attention to the integrated motion/damage/life annotations, retained admission
boundaries, narrative phases/inspection and portable exports. No production
changes or new runtime/visual checks were performed for this review. The full
suite was still running when this receipt was written.

## Disposition: source correction verified; bounded integration approved

Follow-up source review verified `_phase_state` now selects the admitted local
snapshot for every attack, cast preparation/release/recovery, fallback gesture,
and body-action call. Delivery and movement use the same helper. Outer timeline
offsets affect the emitted timestamp only, preserving local snapshot lookup.
The new `test_late_gesture_uses_visibility_at_its_phase_not_action_admission`
regression retains initial preparation while rejecting release/recovery after
an admitted loss of visibility. Its execution belongs to the parent's running
test report; this review checked its source. No outstanding source blocker
remains within the reviewed integration. The original finding follows for audit.

**P2 — gesture disclosure uses the beginning of the head for later phases.**
`game/presentation_text.py:gesture_entries` passes `timeline.before` to every
call of its visibility/name helper, including cast release/recovery, attack body
completion and body-action completion. Those dates can follow an admitted
within-head sensory change. A caster visible at the beginning but hidden before
recovery still receives recovery wording; the graphics path builds its legal
actors from the currently displayed state (`body_presentation.py`,
`scene_actors.py`). Conversely, a later genuinely disclosed body cannot acquire
phase wording through this initial-only check.

Use the phase-local admitted state for each call, with the existing initial
snapshot fallback, as delivery and movement descriptions already do. Preserve
local versus outer offsets, exact native identity and authored text. A focused
before/after visibility regression should show that preparation can remain while
the later hidden phase is omitted. This requires no new reducer or live query.

## Accepted integration boundaries

- Passive timing records remain below their binders and consumer projection.
  Producer annotations carry executed values; playback continues to consume its
  original cue dates and specialized samplers. No new engine owner, generic
  scheduler, renderer registry, reverse `dnd -> game` edge or late-import
  workaround was found in the reviewed changes.
- Motion increments distinguish physical spans from dwell and preserve ordered
  local producer stages. Damage/life annotations retain actual result and causal
  references instead of matching unrelated equal dates. Portal/shove/displacement
  cues remain presentation records over disclosed inputs.
- `PresentationDependencies.admission_uuid` and its assignment from
  `presentation.primary.root.uuid` correctly separate retained snapshots in the
  exported transcript. Resolve their local indices within admission, scope and
  owner; do not collapse them into an assumed monotonic owner history. This
  addresses pruning/reacquisition without a new retained-state owner.
- Text reuses the native grouping, reducer, binder, state cuts and clock.
  Delivery labels use permitted spell names and neutral phase wording; repeated
  applications have separate component identities. Persistent inspection states
  what configuration is known, labels memory, and does not invent application
  occurrences or claim sampled marker selection.
- Catalog export passes through the existing typed `AnimationData`, rewrites
  actual filesystem paths within a declared package, rejects outside resources,
  and strips optional source/preview metadata. `game.export_schema` now exports
  both catalog and narrative schemas from production types. The Pygame narrative
  adapter owns layout only; schema/headless paths do not depend on that adapter.

## Independence and limits

I authored the retained-lifetime implementation in this task and do not give an
independent approval of that code here. Its independent anti-slop review is
`retained-timing-antislop-review.md`; the parent's separate integration review
and recorded lifetime tests remain relevant evidence. This receipt independently
checks the consumer admission-boundary decision and the other integrated lanes.

Producer validation establishes only recorded local references and arithmetic,
not a complete causal graph for unannotated external inputs. Quiet acquisition
does not prove an application date. Neutral effect/attachment prose is not rich
geometric artwork description, and configuration inspection is not pixel
visibility proof. Full-suite results, paired-observer executions and current
rendered comparisons must be reported separately; historical galleries do not
become fresh visual acceptance through this source review.

## Final bounded addition

Rechecked `finite_media_entries`: it consumes already-bound strips, stationary
and contact media, checks source-version membership and phase-local actor/ground
disclosure, and describes neutral effects without inferring artwork semantics.
Lifecycle media is not selected again from recipes. Contact occurrence keys
include the event, track, absolute start and admitted attachment, so nested
motion copies deduplicate while separately timed occurrences survive. The
focused regression exercises one track retained through both paths. No new
mechanics, state reduction or import reversal was introduced.

The F4 change applies a screen-space shift of one quarter of the available scene
width when entering split view and reverses that shift when leaving it. It
does not alter world coordinates, presentation clocks or disclosure. This
review approves that bounded transition; it does not establish new split-view
rotation/zoom anchor behavior or constitute a pixel review. No additional
source blocker was found.

## Cold import boundary correction

Verified the 18 modules that previously imported passive event facts through
`dnd.core.events` now import the same definitions from `dnd.types.event_facts`.
The native module explicitly reexports these definitions: `EventType`,
`MovementTrajectory`, `SpatialChangeType` and `WorldTileState` retain their
identity. Likewise, `animation_data.AppearanceConfig` now comes directly from
`dnd.types.appearance`, and `condition_animation.ConditionFact` from
`dnd.types.actor_facts`; the previous modules reexport those same definitions.
No parallel types module, runtime dispatch or late import was added. Actual
event/queue adapters keep their native dependency.

Inspected the cold subprocess guards and the recorded result in
`/tmp/shared-cold-schema-final.txt`: **2 passed in 8.69s**. These checks cover
exporting all 18 schemas without native execution or graphics modules and
loading shared binding/catalog paths while actively rejecting those imports.
This removes the schema import-boundary integration defect without changing
type identity or presentation behavior. No additional blocker was found.

## Fear and Hold regression assertion repair

Reviewed the bounded test-only correction for accepted overhead markers. Fear
still requires exactly two non-marker layers, now separately requiring one
frightened marker; native geometry and save assertions remain. Native Hold
requires exactly two non-marker layers and the original exact chain asset set,
plus one paralyzed marker. The explicit count was restored after review to
prevent duplicate chain layers from passing a set-only assertion.

Quiet Hold now captures removed layers by the Hold owner, matching production
registration. It preserves phase-zero quiet samples, exact chain blend timing,
frozen pose and outline, and removal of every chain while the independently
owned paralysis marker survives. No production change is needed for these
failures. The earlier affected-file run passed 16 tests in 19.48s; the final
count-restoration rerun is recorded separately by the implementer. The source
correction resolves the last test-repair review issue.

## Web regression assertion repair

Approved the test-only Web correction. The shared assertion requires exactly
two non-marker layers, their exact back/front wrap asset IDs, exactly one
restrained marker and no unsupported appearance. It cannot silently accept
duplicate wraps or extra markers. Contact-before absence, contact-after pixel
change, reverse seek, successful-save absence, escape cleanup, surviving field,
final cleanup and duplicate-source membership coverage remain intact. The
generic restraint-only case still demands its exact marker asset, while the
Web-only activity-selection case still demands two layers. The full affected
file rerun recorded in `/tmp/shared-web-final.txt` passed **10 tests in 18.70s**.
No production repair or assertion weakening was found.

## Portal first-arrival observation repair

Approved the bounded choreography correction after independent source review.
The existing first-arrival selection still requires an admitted arrival endpoint,
no admitted departure, and a received visual observation for that actor at the
exit position. The new override uses both observation event UUID and actor UUID;
other actor snapshots sharing the event retain their ordinary commit floors.
It carries the received snapshot unchanged, including already-injured HP,
rather than constructing undisclosed pre-injury state.

Final observation dating emits that exact snapshot once at the existing portal
arrival clock and skips its duplicate registration. The passive equation
references the portal event's existing arrival anchor at the same date, while
other observations keep their maximum admission/cause floor. No second clock,
queue or state owner was introduced. Existing arrival-minus-epsilon visibility,
arrival HP, traveler ground-settle damage, hazard frame and reverse-seek
assertions remain unchanged. The implementer reports all 11 portal tests and
scoped typing passing; this receipt records source approval, not a separate
rerun. No additional blocker was found for this correction.

## Slow regression assertion repair

Approved the test-only Slow correction: initial appearance requires exactly two
body layers with the original back/front asset IDs, exactly one slow marker and
no unsupported appearance. Existing frame 127/0/40 and removal alpha assertions
remain attached to the body media whose authored cycle they describe. The
independently animated marker is excluded only from those body-cycle checks;
the final removal additionally requires the complete layer collection to be
empty. This does not permit a leaked marker. Full affected-file result in
`/tmp/shared-slow-final.txt`: **5 passed in 15.74s**. No source blocker found.

## Shield of Faith authoring correction

Approved the final data-only correction: both existing media tracks use the
existing contact clock, contact delay is 83.33333333333326 ms, and condition
delay remains zero. The binder already passes the contact date into the effect
condition anchor, so adding that delay again would be incorrect. With the
583.3333333333334 ms release and existing -666.6666666666666 ms media offsets,
media begins at zero and contact/condition occurs at 666.6666666666666 ms with
source frame 21. No new field, scheduler, parser or spell mechanic is introduced.

The native support regression checks media start, source frame and actual
condition cue alignment, preserving its prior outcome/lifetime checks. Final
support/volley execution remains the implementer's evidence. The companion
anti-slop receipt initially described both delays as nonzero; that stale prose
was reported for correction and is not the source approved here. No source
blocker found in the final one-delay implementation.
