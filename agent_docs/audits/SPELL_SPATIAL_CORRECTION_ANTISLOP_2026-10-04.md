# Spell spatial correction anti-slop review — 2026-10-04

**Amended plan approved within its stated scope, with the implementation details
below required.** This supersedes this review's initial blanket-removal
recommendation: transient admission also carries the observer's grant and must
be retained. This approves the bounded approach, not a completed fix or final
pixel result. No additional renderer subsystem, rules change or broad artwork
revision is warranted by the evidence.

Read `RECOVERY_PLAN.md`, the correction plan, `projectile_contact`,
`cast_surface_volume`, the shared volume compositor and relevant existing
projection, staged-topology and regression-test paths. Inspected the diagnostic
log and four diagnostic images under `.runtime/projectile-regression-20261004`:
Fireball current/no-admission and Sleep current/no-floor-mask. These images are
diagnostic recompositions of saved input phases, not evidence that a production
correction is already implemented.

## Findings

- **Magic Missile:** `inverse_rotate_position` rotates an absolute map point
  about the fixed map center. Its use on the curve displacement injects a map
  translation for cameras 1–3, even at a zero displacement. Subtracting the
  inverse-rotated zero is the appropriate vector conversion. It is already the
  convention used by `compose_volume`. Preserve curve pixels, attachments,
  height and clock; validate painter contact at endpoints and during the curve
  in every camera.
- **Fireball:** the viewed current frame has tile-shaped cutouts; removing
  admission restores its round lower ring. The logged increase from 4,848 to
  8,599 smoke pixels and 2,158 to 4,074 additive pixels retains separate support
  clipping, unlike the fully unmasked reference. An affected gameplay-cell set
  is not a suitable direct pixel boundary for this transient fringe. That
  diagnostic does not justify removing the observer's admission permission.
- **Retained permission with stable decorative owners:** reuse
  `sphere_field_owners` for the declared circular footprint. Its full geometry
  and native world bounds define the owner lattice. Interior cells own
  themselves, so removing an interior grant leaves a hole; exterior samples
  borrow their fixed nearest declared owner, not whichever visible cell remains.
  The existing field-ownership tests directly document these distinctions.
  Permission lookup still uses the unchanged `area.admitted`. Pass native world
  bounds from the existing app target as an optional compositor argument; never
  derive them from the observed subset. Without bounds, retain conservative
  direct admission; an empty declared owner lattice must not grant pixels.
- **Continuous propagation:** `cast_surface_volume` currently marks supplied
  admission as `resolved_occupancy=True`, bypassing continuous propagation.
  Retain admission but disable that bypass for transient casts. Keep finite
  barriers, visual boundary silhouettes, protected-sphere exclusions, line
  geometry and unresolved-ownership rejection. Persistent-cloud subjective
  admission and established-occupancy behavior stay unchanged.
- **Staged breach:** the existing choreography path supplies displayed
  boundaries/solids at authored destruction clearance. Keep that topology and
  its clock. The current breach regression's membership check in
  `volume.admitted` remains valid under the amendment. Also check actual pixels
  remaining blocked before clearance, becoming visible after clearance, and
  returning to the earlier result on backward seek.
- **Sleep:** the viewed floor-masked image has a conspicuous horizontal lower
  cut, and the no-floor-mask reference restores its soft fringe. Admission
  removal makes no difference in the log. One explicit physical/raised support
  policy in existing phase/track data is a lean correction. Physical stays the
  default. Raised ignores supports at/below the registered base while retaining
  higher terrain; use the base including vertical attachment translation and
  the existing sampled slope heights. Keep unknown-ownership rejection even
  where the same-level floor no longer clips. Select this only for Sleep's
  ground cloud; retain actual Ice Knife falling-tail clipping.
- **Shocking Grasp:** matching its owning palette to the existing Lightning/
  Chain palette is bounded, but describe the actual target accurately:
  `#1A9EE0`, `#8DE6FF`, `#FFAD23`; the third stop is amber. Automatic hand layers
  inherit owning colors, whereas separate baked main-media banks do not change
  solely because `elementColors` changes. Final inspection must distinguish
  those paths and cover the reported main effect as well as the hands. Any
  selected main-media correction must use the established exact replacement
  path and retain alpha/geometry, as the plan requires.

The proposed focused saved-input checks for all four cameras, real barriers,
Globe exclusion, higher terrain, physical falling particles and staged breach
are proportionate to these shared changes. Preserve the prior 298-clip gallery
and export only the reported corrected cases. Grease and persistent-field
redesign remain outside this correction.

Only this receipt was written. No production edits, tests, renders or external
chat communication were performed by this reviewer.
