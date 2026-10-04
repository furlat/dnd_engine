# Spell spatial correction — ECS plan review

**Outcome: approved as amended.** The initial admission blocker below is closed
by the existing sphere-ownership policy described in the amendment review at the
end. Final implementation/evidence review remains required. No production edits,
tests, renders or external communication were performed for this review.

Reviewed the bounded plan, actual diagnostic pixel counts and Fireball/Sleep
before/isolated-mask images, `projectile_contact`, cast/volume composition,
staged-area drawing, observation projection, and relevant floor, finite-boundary,
Globe, Sleep observation and Fireball breach tests.

## Initial blocker: gameplay cells also carry subjective admission

`game/player_projection.py:347` filters `resolved_area_positions` to the
observer's witnessed cells. `load_animation_media` passes those positions to
`AreaMedia.admitted`; `cast_surface_volume` passes them to the XYZ compositor.
`game/app.py:1507` has no later subjective mask for those volume samples.
Consequently, simply setting transient `admitted=None` removes both the unwanted
gameplay-edge stencil and the observation boundary. Finite physical propagation
and silhouette occlusion do not replace that grant: visibility can be partial
for other reasons, and Sleep can remove sight at contact.

Amend step 2 to preserve the already received observation-time admission
separately from continuous artwork coverage. Keep this within the existing
passive bind/load/sample data flow; no spell registry, backend visibility query,
or per-spell branch is needed. Require a partially observed transient-area pixel
check and retain the pre-contact Sleep observation after its own sight loss.
The existing `test_area_spell_projection.py` and `test_sleep_area_projection.py`
prove the source disclosure contract but alone do not prove the new draw mask.

## Accepted bounded implementation shape

- Curve displacement must use inverse rotation as a vector: subtract the
  inverse-rotated origin. The current function rotates an offset about the fixed
  map center, creating the reported 63-cell painter contacts. Correct only that
  displacement; retain world heights, endpoints, curve shape and clocks.
- One literal physical/raised support policy on the existing projectile-phase
  and media-track records, passed into passive `SurfaceVolume`, is sufficient.
  Default physical preserves current behavior. Raised ignores supports at/below
  the registered effect base and still clips higher terrain; compare against the
  registered base including attachment translation when relevant. It must not
  translate the geometry, change depth, infer unknown terrain or disable barriers.
- Select raised only for the authored Sleep ground cloud. Keep real Ice Knife
  tail floor clipping, slope support sampling, and additive RGB/alpha clipping.
- Stop using gameplay-cell edges to shape the fully observed blast, while
  retaining observation ownership, clump selection, native reach facts and
  staged destruction topology. If `resolved_occupancy` previously skipped
  physical propagation because an admitted stencil supplied it, the new path
  must explicitly restore continuous propagation against the current stage's
  finite barriers. Do not use the final map before its clearance milestone.
- Matching Shocking Grasp's own colors to the existing lightning selection is
  ordinary recipe data. If main media needs replacement, the existing asset
  `paletteSwap` path is available; no new shader/per-spell renderer is warranted.

## Required bounded evidence

Four-camera contact/curve checks; original Fireball round fringe; partial
observation and Sleep's retained incoming sight; Sleep on level and higher
supports; default Ice Knife below-floor rejection; finite wall/door silhouettes
and openings; Globe exclusions; and forward/backward staged breach playback.
Update the existing breach test's representation-level assertion if necessary,
but replace it with actual before/after-clearance pixel evidence rather than
dropping the no-premature-propagation contract.

The images support the reported mask causes: disabling admission removes
Fireball's angular tile cuts, while Sleep changes only when its same-level floor
mask is removed. These diagnostics do not establish safety of globally removing
subjective admission. Final source and focused evidence review remains separate.

## Amendment review — blocker closed

The amended step 2 retains the exact observation-time `admitted` grant and maps
rounded world XYZ cells through the existing `sphere_field_owners` helper before
permission lookup. Reviewed that helper and its current persistent-field use:
its owner lattice comes from the complete declared circle intersected with known
world bounds, never the observed subset. Interior cells map to themselves, so
an unadmitted interior or edge owner cannot gain pixels. Decorative exterior
borrows the corresponding stable full-geometry edge; it does not create native
cells or redisclose occupants. The originally identified blanket-permission
removal is no longer proposed.

Passing existing world bounds from `draw_frame` into `compose_volume` as an
optional argument is a lean composition dependency. Standalone callers can use
the full declared circle bounds; they must not derive them from admitted cells.
Handle the helper's empty-owner result as no admitted pixels. Apply this mapping
only within the existing admitted-permission path for a positive circular
radius; noncircular line constraints and unadmitted/raw references retain their
existing semantics. Persistent XYZ fields already partition ownership before
constructing SurfaceVolume and do not pass its admitted field, so their current
path need not change.

`volume_media -> spatial_field -> projection/core geometry` remains a DAG; no
new runtime state, registry, observation event, or gameplay field is required.
Transient `resolved_occupancy=False` restores continuous finite-barrier checks
alongside the retained grant, including staged current topology. The amended
raised-support definition also explicitly includes vertical translation.

**No remaining plan blocker.** Implementation checks must still prove the
partially observed interior/edge cases, native map boundaries, Sleep's retained
incoming grant, and staged before/after-breach pixels in addition to the original
round-fringe and support-clipping corrections.

## In-progress implementation review

Reviewed the current shared source changes without running tests or rendering.
No native-path source blocker was found; this is not final acceptance.

- `projectile_contact` now subtracts the inverse-rotated origin when converting
  the curve displacement. This fixes the general absolute-position/vector
  mismatch for every curved sprite projectile, preserving endpoints, elevation
  and the authored curve. Other inverse-rotation consumers either already
  subtract zero for displacements or intentionally invert absolute positions.
- The native `draw_frame` passes declared world bounds. Admission maps through
  the full circular lattice before checking the exact received grant. Missing
  interior/edge owners remain missing; an empty full lattice admits nothing.
  Actual native circular/cylindrical inputs supply positive radius. Current
  line/cone/cube inputs supply zero, retain their existing admission, and retain
  line clipping where present. Current circular XYZ consumers are anchored on
  their declared area center. Persistent volumes have no `admitted` field and
  continue their existing partitioned/resolved path.
- Restoring transient continuous barrier propagation preserves received staged
  admission while allowing the stable decorative fringe. Finite silhouette,
  protected-sphere and RGB/alpha rejection remain active. No gameplay geometry,
  observation event, registry or late/circular import was introduced.
- Raised support compares known terrain against the registered base including
  vertical attachment translation; physical remains the default. Sleep's
  authored impact is the only raised selection. Neither mode changes sample
  coordinates or painter depth, and unknown supports remain unknown.

One bounded parity discrepancy remains relative to the proposed amendment:
`compose_volume` only maps the circular fringe when `world_bounds` is supplied;
its default standalone call retains the old cell stencil rather than using the
full declared circle bounds. The native path supplies bounds, so this is not a
native hidden-cell leak. Resolve the standalone contract explicitly rather than
silently presenting direct compositor checks as identical to native composition.

Evidence is still in progress. The inspected new tests cover four-camera curve
contacts and fully observed Fireball/Sleep source-pixel preservation. The latest
inspected `focused.log` ends with 50 passes and eight invalid `Body1` fixture
failures; those cases never reached composition. Partial interior/edge grants,
raised/higher/sloped Sleep supports, native map bounds, and actual before/after
staged breach pixels still need the bounded evidence requested above. Existing
observation and breach fact tests alone cannot establish new mask correctness.
The original 298-recording gallery was not modified by this review.
