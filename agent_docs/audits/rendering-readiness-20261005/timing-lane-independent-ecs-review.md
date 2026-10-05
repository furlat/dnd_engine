# Bounded timing evidence — independent ECS/import-DAG review

2026-10-05. Source review of `game/timing_evidence.py`, timing additions in
`game/choreography.py`, dependency projection in `game/presentation_timing.py`,
and the text/review-trace export consumers. Governing scope is the shared
presentation plan and `dependency-and-state-cut-ecs-review.md`. No production
edits, new tests, runtime probes, or pixel acceptance are claimed.

## Disposition: changes requested

The ownership and dependency direction are sound. Passive records live below
both binder and projection; choreography does not import the projection.
Playback continues to use the existing clocks and state reduction. No new
scheduler, engine query, callback registry or client-side rule execution was
introduced by this lane. Text and trace call the same dependency projection.
Local producer indices disambiguate successive calculation stages, and the
validator checks backward references, matching values and recorded arithmetic.

Two evidence-identity defects remain before approving this bounded lane.

### P2 — object clearance is exported as a spatial-owner reference

`game/choreography.py:1539–1542` unconditionally labels each removal target and
start operand `kind='spatial'`. However, the producer at lines 1047–1056 also
creates removal transitions with a concrete `SpatialFact.object_uuid` for an
ordinary construction section. Those UUIDs identify objects, not spatial-effect
owners. The resulting world-floor dependency is arithmetically valid but claims
the wrong owner kind, so consumers cannot resolve it through the declared typed
identity. Formation already distinguishes concrete sections as `kind='object'`.

Preserve the removal producer's actual owner kind when recording clearance;
keep the existing equation and dates. Verify an individual construction-object
removal as well as whole spatial-owner removal through the exported dependency
boundary.

### P2 — child binding contributions lose concrete source identity

`game/choreography.py:1530–1542` and `1550–1558` retain each contributing
construction offset only as `(value, authored_field)`. Every emitted operand
then points to the parent spatial start. When several construction objects
contribute, the export contains their binding paths but not their concrete
object UUIDs. Multiple sections with the same item ID become indistinguishable
inputs. The prerequisite design explicitly asks for concrete child construction
owners/bindings; the shared plan also requires exact evidence/instance identity.

Retain the concrete binding-owner identity alongside the offset contribution.
It should remain attribution for the actually executed parent-start-plus-offset
equation, not falsely claim an independently measured child start. Verify two
contributing sections sharing a binding and a mixed-binding maximum. No second
scheduler or additional gameplay state is needed.

## Bounded limits

The previously documented uncovered dependency families remain uncovered; this
review does not approve plan D as a whole. The inspected existing Stone Wall
tests check arithmetic, atomic world boundaries and final reduction, but do not
assert these owner-kind and contributing-instance distinctions. Their execution
results must be reported by the implementation owner; I did not rerun them.
