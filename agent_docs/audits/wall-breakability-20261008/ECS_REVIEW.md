# Wall breakability: ECS and public replay review

8 October 2026. Reviewer: `wall_break_ecs_review`. Bounded review under
`WALL_BREAKABILITY_COMPLETION_2026-10-08.md`; no production edits by this reviewer.

## Composition receipt

Approved within the wall scope. `DirectionalWall` composes existing Health and
ItemDestructionProfile, using stone 27 HP / wood 18 HP and existing material armor
classes. Its structural queries now honor the destroyed profile. The seven direct
solid builders reuse this owner; `build_cliff_face` explicitly remains
non-targetable and has no destruction profile.

Damage, supported-item cascade, UUID, edge/base placement, and spatial revision
ownership remain in the existing native lifecycle. A corner still comprises two
independent UUIDs. The presentation material map is justified because the generic
wall item ID represents both materials and must preserve the intact legacy corner
selector. The finite `clear_at_end` bank field expresses the source effects'
cleanup endpoint without adding a second wall lifecycle or artwork. Source media
provenance is covered separately by `SOURCE_REUSE.md`. The human subsequently
confirmed that Pygame is off. This receipt approves native composition and
authored data; it does not certify an active renderer or client integration.

## Completion and privacy verification

The `OBJECT_CHANGED` addition in `dnd/player/projection.py` uses the existing
object-spatial disclosure gate: noncanceled COMPLETION, an object UUID, current
recorded sensory contact, current placement, and contact position inside that
placement. No remembered-contact fallback or inferred observation-to-wall cause
is added. Object removal keeps its existing declaration-contact gate.

Passive replay of the exact pinned native inputs through projection, public
encode/decode, reduction, and choreography confirmed:

- `/tmp/wall-review-native.json`: lethal raised stone corner support and Witness
  admission commit together at the recorded attack impact, 666.6666666666666 ms;
  one timed world update, no choreography gaps.
- `/tmp/door-review-native.json`: inward opening and closing each retain their
  real spatial ancestry and commit at 250 ms, with matching true/false endpoints.
- Entity registry and EventQueue remain empty after passive replay. Summary:
  `/tmp/wall-break-ecs-passive-verification.json`.

Existing privacy/contact cohort: **16 passed in 23.12 s**:

```text
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run --no-sync python -m pytest -q tests/game/test_player_projection.py tests/game/test_spatial_removal_projection.py
```

These saved-input choreography measurements were taken before the human clarified
that Pygame is off. They establish the retained public causal source and timing
in that existing consumer, not acceptance of an active client. The parent is
replacing this task's raster checks with native/public replay and authored-data
checks and removing the task's `app.py` patches. Native lifecycle and
privacy/contact verification remain applicable.

## Independent existing trap replay defect

Pinned unchanged native recordings for separate repair:
`/tmp/trap-review-native-attacker.json` and
`/tmp/trap-review-native-witness.json`. They were captured once from
`tests/game/trap_hardware_scenarios.py::trap_hardware_history()` with the default
swinging-blade stone workshop hardware, undeployed.

Both observers reproduce the same mismatch with the current projector and an
ephemeral previous-behavior branch that returns no fact for `OBJECT_CHANGED`:
mechanism removal commits at 0 ms while hardware remains intact; hardware
destruction commits at 666.6666666666666 ms. Restricting the new wall disclosure
does not repair it.

The native ancestry is present and exact:

```text
ItemDestruction -> SpatialChange(OBJECT_CHANGED)
  -> Event(CONDITION_REMOVAL) -> SpatialEffectChange(REMOVED) -> SensoryUpdate
```

`dnd/spatial/area_conditions.py::_create_anchor_handler` deactivates the mechanism
with the real changed-object event as parent. The public projector's
`_public_occurrences` drops the generic condition-removal bridge because it has
no admitted fact/update/log, then clears the removal node's parent lineage.
Choreography consequently sees mechanism removal as an independent root.
Preserving that recorded bridge requires separate projection-policy review;
there is no basis for inventing renderer ownership or material heuristics.
No trap or ancestry policy was changed for this wall task.

## Historical renderer evidence; investigation stopped

A later read-only trace of the pinned stone-corner and F1 native recordings
retained their wall owner and base height 2 throughout. In the existing Pygame
renderer, `reveal_visible_supports` changed the intact corner, surviving straight
leg, and F1 global alpha from 255 to 65 in all four views. Their destinations,
painter keys, and nontransparent pixel counts remained unchanged. Later opaque
terrain covered only a minority of wall pixels; the main visual suppression was
that existing fade pass. Neither inspected intact wall bank had an actor-depth
sample. Diagnostic script/log: `/tmp/wall-occlusion-review.py` and
`/tmp/wall-occlusion-review.txt`.

This is historical Pygame evidence only. The human's correction stopped the
investigation immediately; no fade, depth, offset, or renderer repair was made,
and this result is not presented as active-client behavior.
