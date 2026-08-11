# Move-Family Settlement, Path Integrity, and Opportunity-Attack Truth — Lean Implementation Plan

**Status:** DRAFT REVISION 5 — DESLOPPED CAUSAL/PRIVACY CORRECTIONS; EXTERNAL RE-REVIEW REQUIRED

**Date:** 2026-08-05

**Scope:** Move, Swim, and Fly through the existing `Move` executor; objective
opportunity-attack eligibility; collision learning and senses parity; focused
event/log contract regeneration and movement-log privacy projection

## 1. Decision and boundary

This unit repairs one existing core-gameplay transaction:

```text
accepted Move path
    -> provisional Step fact
    -> ordered pre-entry reactions
    -> objective state/transition revalidation
    -> recompute exact current edge cost
    -> affordability and exact movement debit
    -> position commit and arrival effects
    -> committed Step completion
    -> optional continuation decision
    -> truthful root settlement
```

It does not redesign the event engine or locomotion architecture. The plan is
forward-looking and requires no knowledge of an earlier implementation branch.

### Included now

- Move, Swim, and Fly settlement through the existing `Move` class;
- family-local copy isolation for root and PATH-Step handler proposals, with
  queue-owned child/evidence metadata restored from the authoritative input;
- accepted-event ownership of immutable request facts, accepted path/mode,
  fixed-cost evidence, and aggregate movement estimates;
- a closed Move-family handler surface: safe status text only, with route,
  mode, costs, identity, lifecycle, and parentage frozen;
- exact path validation against the mover's subjective knowledge;
- per-edge objective transition, post-reaction cost recomputation, and
  affordability revalidation;
- movement debit before arrival effects;
- actual voluntary endpoint/path/cost and objective endpoint after child
  displacement;
- truthful zero-step settlement: DECLARATION/EXECUTION rejection cancels, while
  EFFECT cancellation becomes a same-EFFECT stop marker and every published
  EFFECT settles through completion because an earlier EFFECT handler may have
  already changed mechanics without emitting a child event;
- continuation decisions after a committed arrival, including no-reason
  interruption and objective death/action-denial precedence;
- neutral opportunity-attack provocation and objective reactor eligibility;
- ordered-reactor suppression after an earlier reaction kills, denies, or
  displaces the mover;
- hidden-reactor privacy;
- collision-memory publication, final senses refresh/delta, and Swim/Fly
  discovery parity;
- forced-movement separation;
- structured combat-log, subjective coordinate redaction, and
  generated-contract parity.

### Explicitly deferred

Two separate future units own the issues below.

**Jump traversal semantics:** Jump currently models airborne travel as planar
cell-by-cell occupancy. Changing that to an atomic landing would alter
opportunity attacks, hazards, range, and interruption rules. This plan does not
silently make that product decision. Jump receives only shared OA eligibility
corrections arising in `dnd/reactions.py`. The PATH-Step family guard in this
unit is explicitly gated by dependency-neutral `MovementTrajectory.PATH`, so
`DIRECT_ARC` Jump Steps retain their existing handler behavior and executor.

**Generic handler integrity:** no change is made to proposal tokens, child
reconciliation, handler-origin provenance, or generic cancellation/completion
behavior. One polymorphic selector replaces the queue's existing “method is
overridden” test: `Event.guards_handler_result()` returns that same test by
default, while Step returns true only for PATH. `_invoke_handler()` and
`preflight()` use the selector both to decide whether to detach the proposal and
whether to call family `validate_handler_result()` afterward. Every other event
family is behavior-identical.
This is the minimum needed to avoid silently guarding DIRECT_ARC Jump; it is
not a new queue policy. Any other generic hardening requires a separate plan.

## 2. Required gameplay truth

For every voluntary Move edge:

```text
uncommitted edge
    movement debit = 0
    no voluntary position entry

committed edge
    exact edge cost is debited first
    objective position then enters the destination
    arrival children may resolve
    StepMovementEvent completes committed=True
```

The root result must distinguish:

```text
requested_end_position
    original requested destination retained by the lineage

end_position
    last position voluntarily committed by Move

objective_end_position
    actor's actual position after synchronous child displacement

path
    inclusive ordered positions voluntarily committed by Move

costs[movement]
    exact sum of committed voluntary edge costs
```

Normally `end_position == objective_end_position == path[-1]`. If a child
forcibly displaces the actor, `end_position == path[-1]` remains the voluntary
truth while `objective_end_position` carries the actual final position. The
forced destination is never appended to `path` and never charged as voluntary
movement.

## 3. Existing owners remain authoritative

### 3.1 Move event lineage owns admitted intent and settlement history

The `Move` action constructs an unregistered declaration. Once its event has
passed handlers and validation, execution reads the accepted event version.
It does not return to `self.path`, `self.movement_mode`, `self.costs`, or
`self.use_movement_cost` for mechanics.

No duplicate `declared_path` or `admitted_costs` fields are added. Movement
lineage versions use an immutable path tuple plus detached root-version cost
facts/list containers, so the queue's handler proposal cannot alias and mutate
an earlier stored version. EventQueue already retains each lineage version:

- DECLARATION/EXECUTION/EFFECT retain the admitted path and costs;
- COMPLETION or CANCEL carries actual settlement.

That existing versioned history preserves request versus result without
duplicating the same authority on one event version. `requested_end_position`
is immutable original intent. `end_position` before settlement is the frozen
accepted endpoint. On the terminal version it becomes the last voluntarily
committed endpoint.

### 3.2 GridMap owns structural movement truth

`GridMap.can_transition()` owns edge legality. Tile movement-cost APIs own
terrain cost. Occupancy and structural collision stay in GridMap.

The action may sequence these queries; it may not reproduce wall, door, tile,
or occupancy logic.

### 3.3 Entity owns position mutation

`Entity.update_entity_position()` remains the only position-commit API used by
Move. Direct writes to entity position, senses position, map occupancy, or
entity position indices are forbidden.

### 3.4 ActionEconomy owns movement balance

`ActionEconomy.consume("movement", step_cost_feet)` owns the debit. The root
`movement_spent` accumulator is evidence only, not another balance.

### 3.5 EventQueue owns reactions and history

The existing `StepMovementEvent(EFFECT)` remains the reaction boundary.
Opportunity attacks and other trusted handlers resolve before the action
commits that edge.

This patch consumes the handler-returned Step and validates objective state
before mutation. It does not add another queue, transaction log, or reducer.

### 3.6 Continuation guard remains an observer

`MovementContinuationGuard.after_committed_step()` observes an already paid,
already committed boundary and returns `CONTINUE` or `INTERRUPT`. It does not
move the entity, pay/refund movement, rewrite events, wait for I/O, or become a
command authority.

## 4. Files in scope

Core production:

```text
dnd/core/action_execution.py
dnd/core/combat_log.py
dnd/core/events.py          # guard selector plus Movement/PATH-Step contracts
dnd/actions.py
dnd/reactions.py
dnd/entity.py
dnd/classes/sorcerer.py    # Fly accepted-route capability hook only
dnd/monsters/traits.py     # Aggressive accepted-route rule only
server/combat_log_projection.py
```

Mechanical generated outputs:

```text
server/event_contract.generated.json
sdk/typescript/src/generated/contract.generated.json
sdk/typescript/src/generated/contracts.generated.ts
```

New owner regression file:

```text
tests/engine/test_move_settlement.py
```

Existing focused consumers that may receive narrow assertions:

```text
tests/engine/test_combat_actions.py
tests/engine/test_action_discovery.py
tests/engine/test_senses_light_stealth.py
tests/manual/test_09_action_discovery_and_costs.py
tests/manual/test_50_movement_revalidation.py
tests/manual/test_102_game_summary.py
tests/manual/test_97_event_wire_contract.py
tests/manual/test_113_subjective_combat_log_projection.py
tests/manual/test_121_canonical_presentation_mapper.py
tests/manual/test_122_canonical_replication_runtime.py
tests/progression/test_sorcerer_character_grant_appliers.py
```

Read-only reference unless a focused red proves a directly required defect:

```text
dnd/core/gridmap.py
dnd/blocks/action_economy.py
```

## 5. Non-goals

Do not add or change:

- Jump execution, Jump path geometry, Jump interruption, or Jump settlement;
- generic EventQueue lifecycle/ordering, validation tokens, callback ordering,
  or child reconciliation. The only queue plumbing change is calling the
  default-preserving `guards_handler_result()` selector in the two existing
  guard-selection sites;
- a movement service, scheduler, checkpoint, journal, worker, task, thread, or
  async queue;
- server routes, hosted runtime lifecycle, persistence, replication reducers,
  or frontend code; the existing combat-log projector receives only the narrow
  movement-coordinate redaction required by this unit;
- reciprocal wall/door identity, connectors, stairs, roofs, elevation, water
  volumes, or a z-axis;
- player animation cues or locomotion timelines;
- speculative rollback of movement, reactions, damage, or event history;
- deep copies, serialization, hashing, registry scans, or all-map pathfinding
  inside the per-edge execution loop.

Generated SDK files are mechanical mirrors only. No handwritten SDK behavior
is in scope.

## 6. Minimal contract additions

### 6.1 Termination vocabulary

Retain the existing values and add only the explicit reasons this transaction
cannot otherwise report:

```python
class MovementTerminationReason(str, Enum):
    COMPLETED = "completed"
    COLLISION = "collision"
    INSUFFICIENT_MOVEMENT = "insufficient_movement"
    STEP_CANCELED = "step_canceled"
    INCAPACITATED = "incapacitated"
    ACTION_DENIED = "action_denied"
    DEAD = "dead"
    SUBJECTIVE_REVALIDATION = "subjective_revalidation"
    POSITION_DIVERGED = "position_diverged"
    INVALID_PATH = "invalid_path"
    INVALID_COST = "invalid_cost"
    CANCELED = "canceled"
```

`canceled_from_phase` already records DECLARATION versus EXECUTION versus
EFFECT. Do not create three duplicate termination enum values for those phases.

`can_take_actions() == False` is neutral action denial, not proof of the
specific D&D Incapacitated condition: a “turn spent” transform can close action
permission while leaving reactions legal. New settlement therefore emits
`ACTION_DENIED` for this generic gate. Retain `INCAPACITATED` for existing
compatibility, but do not infer it from a concrete condition name.

### 6.2 Copy-isolated MovementEvent contract

Add the two facts execution or settlement cannot otherwise represent:

```python
movement_mode: MovementMode = Field(
    default=MovementMode.WALKING,
    description="Accepted transition and terrain-cost mode for this lineage.",
)
objective_end_position: Optional[Tuple[int, int]] = Field(
    default=None,
    description="Actual actor position after synchronous child displacement.",
)
```

Keep the existing `path`, `requested_end_position`, `end_position`, `costs`,
`trajectory`, `termination_reason`, and controller-revalidation meanings, but
make every handler-writable mutable container on MovementEvent detached from
the stored input:

```python
class MovementEvent(ActionEvent):
    path: Optional[tuple[MovePosition, ...]] = None
```

A MovementEvent retains the inherited `ActionEvent.costs: List[BaseCost]` type;
do not install an incompatible tuple override. Add one MovementEvent-local
proposal-copy helper with the exact base signature. It delegates to
`super().model_copy(...)`, then detaches costs and nested BaseCost values,
declared-target collections, observer maps and their sets, child collections,
and child-lineage collections. MovementEvent has no generic mutable `context`
field; do not invent or copy one. The path itself is an immutable tuple. This is
a shallow domain copy plus copies of the event's few mutable containers, not a
world/entity deep copy.

The family validator does not let a handler own queue-maintained fields.
Before a valid proposal is stored, restore `children_events`,
`lineage_children_events`, `children_lineages`, identity/location observer
maps from the authoritative stored input. Legitimate child events published
during a handler—especially an
opportunity attack—therefore remain attached even though the detached proposal
was created before the child existed. A handler cannot erase, inject, or alias
those collections.

This makes root lifecycle versions and the existing guarded handler proposal
copy-isolated without changing ActionEvent's writable base-field contract or
deep-copying the world. It is exercised only for the small root MovementEvent,
never inside the per-edge Step loop. Other ActionEvent families keep their
current behavior; `BaseCost` itself is not changed globally.

After path setup has produced the request-side movement estimate,
`Move._create_declaration_event()` snapshots `self.effective_costs` exactly once,
not raw `self.costs`. This retains action overrides, dynamic/restricted grants,
and named-resource transforms in the event that §6.4 re-admits. It also copies
each runtime Cost through its serialized `BaseCost` dump/validation boundary so
evaluator callbacks do not enter event evidence, and copies the action's
mode/path into the declaration. Later mechanics use only returned event
versions and the local settled-cost tuple.

`MovementEvent.get_affected_positions()` is recipient discovery, not a dump of
every coordinate serialized on the objective event. Before terminal settlement
it returns only the source/start cell. On COMPLETION it adds the actually
committed voluntary path. It never adds the uncommitted requested endpoint or
the child-forced objective endpoint; those coordinates require their own Step
or forced-movement evidence. The controlled mover still receives its event as
a participant, while subjective projection separately redacts fields under
§13.

### 6.3 Exact coordinates without breaking JSON round trips

Move must not silently accept booleans, floats, numeric strings, or the wrong
coordinate arity. JSON legitimately represents tuples as arrays, and objective
event/replay import must remain able to round-trip serialized positions.
Therefore require strict integer coordinates while allowing Pydantic to
normalize a two-element JSON array to the engine tuple:

```python
MovePosition = Tuple[StrictInt, StrictInt]
```

Use it on `Move.path`, `Move.end_position`, and the corresponding
`MovementEvent` position fields. After validation every engine value is a
tuple of exact ints; a JSON input list is normalized at the construction/import
boundary and is not itself treated as a mechanics or privacy violation.
Add one small boundary normalizer for a position and one for a path. Use them
at ordinary construction/import, `_setup_path()`, `set_target_position()`, and
`instantiate(**overrides)` before assignment or unchecked
`model_copy(update=...)`. A malformed override fails before it can enter an
action/event. `Move.instantiate()` also rejects a `movement_mode` override: the
registered Move/Swim/Fly template owns that capability. Do not scatter ad-hoc
`isinstance` checks through execution.

### 6.4 Closed Move-family cost admission

Move-family subclasses may own legitimate non-movement costs. The maintained
`AggressiveMoveAction(Move)` consumes a bonus action, and future authored Move
subclasses may use a named resource. This revision therefore does not ban those
costs or silently break subclass content.

All MovementEvent cost facts are copy-isolated `BaseCost` values, and family
validation requires both `cost >= 0` and `resource_cost >= 0`. Handlers may not
add, remove, or rewrite them. Non-movement/named facts are exact fixed-cost
admission. The optional aggregate movement fact remains request-side
affordability evidence only. Although route/mode are frozen, reactions may
change terrain or mover capabilities, so the aggregate is never consumed and
is replaced by exact committed movement at the terminal root. Per-edge
revalidation—not rewriting stored EFFECT evidence—owns current affordability.

Allow at most one aggregate `cost_type="movement"` fact, and require that fact
to have `resource_name=None` and `resource_cost=0`. Any named resource attached
to a Move-family action must be a separate fixed-cost fact, so replacing the
movement estimate cannot erase already-consumed resource evidence. Duplicate
movement facts or a resource-bearing movement fact terminate INVALID_COST
before any consumption.

`set_target_position()` and `instantiate()` must preserve authored fixed costs.
Replace only the generated aggregate `cost_type="movement"` fact before path
recomputation; never reset the whole list. This retains Aggressive's bonus
action and any legitimate named/non-movement fact. Test direct retargeting and
template instantiation, since both live entry points currently erase costs.

After the published EFFECT returns, run objective source-position/life/action
precedence. A stop marker completes without cost. Otherwise, after the content
prerequisite gate passes, settle fixed costs before the first edge:

1. aggregate all positive non-movement action-economy amounts by `cost_type`;
2. aggregate all positive named-resource amounts by `resource_name`;
3. re-check every aggregate against the source Entity's current
   ActionEconomy/resource owner;
4. if any aggregate is unavailable, consume nothing and complete the accepted
   EFFECT with zero movement and `INVALID_COST`;
5. after all checks pass, synchronously consume each aggregate once, then mark
   those accepted costs settled in the local Move execution state;
6. only then may the first Step be published.

The engine is synchronous across this check/consume block; it invokes no
handler, callback, event publication, or await between aggregate preflight and
consumption. Aggregation prevents two individually affordable facts from
overdrawing the same bucket. Movement itself remains per-edge and is excluded
from this up-front settlement.

Authoritative edge debit uses the post-reaction cost from §9. Terminal root
costs contain the exact settled non-movement/named facts plus one movement
fact replaced with the exact committed sum. `Move._apply_costs()` becomes a
no-op returning the terminal MovementEvent because every accepted cost has
already settled. No cost can overdraft or cancel after position COMMIT/terminal
COMPLETION.

`StepMovementEvent.guards_handler_result()` returns true only for
`trajectory is MovementTrajectory.PATH`. PATH proposals detach mutable
inherited containers, validate the exact edge contract, and restore queue-owned
child/evidence metadata. DIRECT_ARC (Jump) follows the default unguarded path it
used before this unit. `Event.guards_handler_result()` preserves the queue's
current override-detection rule for every other family; the selector gates both
proposal copying and post-handler family validation.

## 7. Path admission

### 7.1 Validate the exact accepted route

Replace the reachable-cell-membership fallback. A valid route requires:

1. at least two positions;
2. `path[0] == source.position`;
3. `path[-1] == end_position`, the accepted endpoint; the separately retained
   `requested_end_position` remains the original request;
4. exact strict position types from §6.3;
5. no repeated position or cycle;
6. no more than `remaining_movement // 5` edges at initial admission;
7. every position currently visible or remembered by the mover;
8. a disclosed endpoint under the existing discovery policy;
9. every consecutive edge legal under subjective `GridMap.can_transition()`
   using the accepted event `movement_mode`;
10. the mover's remembered `collision_blocked` and
    `directional_collision_blocked` evidence passed exactly as discovery does.

The edge bound runs once, at initial admission. Every grid edge costs at least
five feet, so difficult terrain can only reduce the executable prefix; it
cannot justify a longer unbounded request. Because handlers cannot rewrite the
route, no second dynamic length bound is needed. A reaction that reduces
movement causes later per-edge `INSUFFICIENT_MOVEMENT`; it does not relabel the
already-admitted route `INVALID_PATH`.

For walking, require the endpoint in `source.senses.paths`. A caller may submit
a longer disclosed route rather than the cached shortest route, provided every
cell was disclosed and every edge passes the same subjective transition rule.

For Swim/Fly modes, retain the existing mode-specific discovery policy and
require the endpoint currently visible. Do not expose an objective hidden
blocker during admission.

### 7.2 Closed root-handler surface

`MovementEvent.validate_handler_result()` is a local family guard using the
existing pre-storage hook. For every non-canceled handler result it requires:

1. exact runtime type `MovementEvent`, not a subclass or another Event;
2. the existing `handler_result_preserves_lifecycle()` contract;
3. exact equality for every model field except the small allowed transform set
   and ordinary version metadata;
4. immutable/copy-isolated path and cost runtime shapes from §6.2–§6.3.

The only domain field a handler may rewrite is:

```text
status_message
```

Ordinary event-version metadata (`uuid`, `timestamp`, `modified`) may change as
the existing event API requires. Everything mechanical is frozen against the
received version: event type, phase, lineage, registration mode, source/target
UUIDs and names, parent event and lineage, behavior/action/item attribution,
trajectory, start/end/requested positions, path, movement mode, costs, declared
targets, presentation kind, and controller/terminal fields. There is no live
Move handler that needs to rewrite route geometry or grant a movement mode.
Freezing these fields deletes the need for a second transformed-route authority
and prevents ordinary Move/Aggressive from becoming FLYING or BURROWING.

A legal cancellation is rebuilt from the authoritative received version as in
§8.2. Any other mismatch becomes that same exact cancellation before storage or
callbacks. This is a one-field presentation/text allowance, not generic
EventQueue hardening.

### 7.3 One route admission plus one current-state prerequisite hook

Implement one private pure route validator for `_validate()` before EXECUTION.
After generic route validation, call one protected pure extension hook such as
`_validate_move_prerequisites(event, source)`. Base Move accepts, while
Move-family content may reject its own authored route/capability facts.

Use the content hook twice:

1. during `_validate()` after initial route admission;
2. in `_apply()` after a published EFFECT returns without a stop marker and after objective
   source/position/life/action precedence, before fixed costs or the first
   Step.

The second call does not reclassify a route against a newly reduced movement
balance. It only rechecks current content capability such as Dragon Wings or
Aggressive's current enemy-relative rule. Objective topology and affordability
remain per-edge owners. The route, mode, original request, source, lifecycle,
and attribution cannot move between phases.

The execution snapshot is then:

```python
effect_event = execution_event.phase_to(EventPhase.EFFECT, ...)
# MovementEvent validation guarantees EFFECT results are same-phase and
# non-canceled, translating a veto into termination_reason=CANCELED.

objective_failure = _move_objective_preexecution_failure(
    effect_event,
    source_entity,
)
if objective_failure is not None:
    return _complete_accepted_move_effect(effect_event, objective_failure)

if effect_event.termination_reason is MovementTerminationReason.CANCELED:
    return _complete_accepted_move_effect(
        effect_event,
        MovementTerminationReason.CANCELED,
    )

prerequisite_failure = self._validate_move_prerequisites(
    effect_event,
    source_entity,
)
if prerequisite_failure is not None:
    return _complete_accepted_move_effect(effect_event, prerequisite_failure)

execution_path = tuple(effect_event.path or ())
execution_mode = effect_event.movement_mode
admitted_costs = tuple(effect_event.costs)
```

After this snapshot, the loop never reads the action object's parallel fields.

`AggressiveMoveAction` is the route-rule proof. Its “must move closer to a
visible enemy” rule currently reads `self.end_position`. Migrate it into the
hook and calculate from the supplied `MovementEvent.end_position`. The second
call handles an enemy moving during EFFECT without reading action caches. Add
no monster-specific branch to base Move.

`Fly` is the capability proof. Migrate its Dragon Wings prerequisite from the
current one-time `_validate()` override into the same hook, reading the
accepted event plus current source condition authority. The event mode is
immutably FLYING. If EFFECT mechanics remove Dragon Wings, complete the root
without entering a flying edge. Do not add a generic capability registry or a
content-name switch to base Move.

### 7.4 Collision learning, discovery, and final senses parity

Preserve the existing hidden-topology learning branch. When an edge was
subjectively legal but the objective transition is blocked:

1. classify cell versus directional blockage through GridMap;
2. add exactly the existing `collision_blocked` or
   `directional_collision_blocked` memory;
3. publish `SpatialChangeEvent.movement_collision(...)` with the exact root,
   from/to positions, direction evidence, and movement channel;
4. settle the edge/root according to §8.3 without entering or debiting.

Do not duplicate wall/door logic in Move. This branch remains a reveal/sensory
fact owned by GridMap and the existing spatial event.

Every non-walking `compute_paths()` call in Move setup, declaration creation,
and `Entity` action discovery must pass the mover's same
`collision_blocked`/`directional_collision_blocked` evidence. Walking continues
to consume the already memory-filtered senses paths. Preserve the final
`update_entity_senses(...)` plus `emit_sensory_update_delta(...)` in `finally`
for success, partial settlement, and zero-step termination.

## 8. Truthful cancellation without EventQueue redesign

### 8.1 Normalize action-owned rejection

Every Move-owned rejection during DECLARATION/EXECUTION—including source lookup
failure and invalid initial route—calls one helper before `.cancel()`:

```python
def _unsettled_move_cancel_updates(
    event: MovementEvent,
    source: Optional[Entity],
    reason: MovementTerminationReason,
) -> dict[str, object]:
    return {
        "end_position": event.start_position,
        "objective_end_position": (
            source.position if source is not None else event.start_position
        ),
        "path": (event.start_position,),
        "costs": [],
        "termination_reason": reason,
        "controller_revalidation": False,
        "controller_revalidation_reason": None,
        "outcome_code": f"movement.{reason.value}",
    }
```

Once the EFFECT version is published, this cancel helper is forbidden. EFFECT
handlers are allowed to mutate mechanics without returning a child (Slowed does
so), therefore EFFECT vetoes and every later failure use zero/partial-movement
COMPLETION under §8.3 even when no cost, child, or edge is visible.

### 8.2 Normalize handler cancellation through the existing family hook

The §7.2 override is phase-specific:

- during DECLARATION/EXECUTION, a legal handler cancellation—or any invalid
  result—calls `invalid_handler_result_cancellation()` on the authoritative
  received event, preserves a safe status/fallback, and applies
  `_unsettled_move_cancel_updates(..., CANCELED)`;
- during EFFECT, a handler cancellation or invalid result cannot rewind the
  already published causal boundary. Rebuild an exact detached copy of the
  authoritative EFFECT with `canceled=False`, the same EFFECT phase,
  `termination_reason=CANCELED`, `outcome_code="movement.canceled"`, safe
  status, and restored queue-owned metadata. Mark it modified so EventQueue
  stores the stop version.

Remaining EFFECT handlers receive that exact stop version and may publish their
ordinary ordered mechanics; they cannot clear or rewrite the stop marker. After
dispatch, `_apply()` first applies objective
DEAD/ACTION_DENIED/POSITION_DIVERGED precedence. If none applies, it detects the
marker before content prerequisites/fixed costs/Steps and creates a
zero-movement root COMPLETION. This preserves handler order and causal truth
without a generic EventQueue stop flag or rollback.

This guarantees exact source, parentage, lineage, phase, original request, and
zero settlement before the handler-produced version becomes observable. The
family-local detached proposal prevents in-place mutation of stored versions;
queue-owned child/evidence fields are restored before storage.

A Movement DECLARATION/EXECUTION cancellation remains a true veto. An EFFECT
cancellation means “do not enter a movement edge,” not “pretend this EFFECT was
never published.” The maintained Slowed handler mutates and returns `None`; a
test orders Slowed before an EFFECT canceller and proves the mutation plus
root COMPLETION are both retained.

### 8.3 Exhaustive root/Step terminal table

The rule is deliberately simpler than a transaction-history predicate:

```text
DECLARATION/EXECUTION rejection -> root CANCEL
published EFFECT (including a veto stop marker) -> root COMPLETION
```

No child scan decides the phase. Children already attached during EFFECT are
preserved by §6.2, but completion does not depend on discovering them. Exact
branches are:

| Result | Step terminal | Root terminal | Movement cost | Root reason |
|---|---|---|---:|---|
| request-side affordability fails before declaration | none | no event | 0 | no result |
| invalid path/cost or root-handler veto during DECLARATION/EXECUTION | none | `CANCEL` | 0 | exact invalid/canceled reason |
| EFFECT handler veto/invalid result after an earlier mutation/child or none | none | `COMPLETION` | 0 | `CANCELED` |
| fixed-cost unavailable after accepted EFFECT | none | `COMPLETION` | 0 movement, no fixed cost | `INVALID_COST` |
| first-edge pre-Step DEAD/ACTION_DENIED/POSITION_DIVERGED | none | `COMPLETION` | 0 | objective reason |
| first-edge objective collision | none | `COMPLETION` | 0 | `COLLISION` |
| any zero-edge branch after non-movement/named cost settled | as otherwise required | `COMPLETION` | 0 movement plus exact fixed costs | exact reason |
| handler cancels Step | existing Step `CANCEL` | `COMPLETION` | committed sum | DEAD/ACTION_DENIED/POSITION_DIVERGED, else `STEP_CANCELED` |
| uncanceled Step rejected after reactions for DEAD/ACTION_DENIED/POSITION_DIVERGED/COLLISION/INSUFFICIENT_MOVEMENT | action-owned `COMPLETION, committed=False` | `COMPLETION` | 0 | exact objective reason |
| any prior edge committed, then a later pre-Step or canceled-Step branch | as above/none | `COMPLETION` | committed sum | exact objective reason |
| one or more edges commit and path ends/guard interrupts | `COMPLETION, committed=True` per edge | `COMPLETION` | committed sum | exact terminal reason |

For an EFFECT stop marker combined with death, action denial, or displacement
caused during the same ordered dispatch, the objective reason wins. CANCELED is
used only when those higher-priority facts are absent.

Root `CANCEL` produces no completion callback/combat log. Root `COMPLETION`
does. A handler-produced Step `CANCEL` is already the terminal Step version and
must never be followed by a fabricated Step completion. Conversely, an
action-owned rejection of an uncanceled Step completes it exactly once with
`committed=False`; only the executor may create that version.

Delete the proposed child-sensitive root-phase predicate and its bounded
lineage scan. A boolean local fact—`effect_published`—is enough. It becomes true
before EFFECT dispatch; from that boundary the executor constructs exactly one
terminal root COMPLETION with the causal facts accumulated so far.

For `trajectory is MovementTrajectory.PATH`,
`StepMovementEvent.validate_handler_result()` locally requires exact event
type, lifecycle, source, parent, from/to, index, path length, trajectory,
provisional cost, and `committed=False`. A handler cannot advance to
COMPLETION, set committed, replace the lineage, or forge cancellation metadata;
invalid proposals become an exact Step CANCEL through the existing pre-storage
family hook. The validator restores child/observer metadata from the
authoritative Step input so OA children remain nested. DIRECT_ARC Steps bypass
this family rule and preserve Jump semantics.

Before posting a Step, retain its executor-created `step_event.lineage_uuid`
and the full planned edge contract. `Event.post()` intentionally creates a new
stored UUID, so the unposted object's UUID is not a valid history locator.
After publication, require `processed_step.uuid` to resolve to that exact stored
Step value and match the captured lineage, event type, registration mode,
parent root, and immutable edge contract. The returned UUID is only a locator
after family validation; it cannot redefine the lineage. No descendant/history
scan is needed to choose the root phase.

## 9. One private voluntary-edge helper

Add one private dataclass and helper in `dnd/actions.py`:

```python
@dataclass(frozen=True, slots=True)
class _MoveStepSettlement:
    committed: bool
    path: tuple[tuple[int, int], ...]
    movement_spent: int
    objective_position: tuple[int, int]
    termination_reason: Optional[MovementTerminationReason]
    continuation_decision: MovementContinuationDecision
    continuation_reason: Optional[str]
```

The continuation decision is explicit because `INTERRUPT` may legally have no
reason string.

The helper receives an exact uncanceled `StepMovementEvent(EFFECT)` plus the
accepted root event and owns this order after every matched Step handler has
returned:

1. require `source.position == from_position`; otherwise complete the Step
   `committed=False` and return `POSITION_DIVERGED`;
2. if source life state is exactly DEAD, complete false and return `DEAD`;
3. if source cannot take actions—including DYING or STABLE—complete false and
   return `ACTION_DENIED`;
4. objectively re-run `GridMap.can_transition()` for the accepted mode,
   publishing the §7.4 collision-learning fact when subjectively legal but
   objectively blocked;
5. recompute the exact edge cost from the current destination tile, accepted
   mode, and current mover capabilities after all reactions;
6. re-read normalized movement and require affordability against that newly
   computed cost;
7. phase an action-owned rejected Step to COMPLETION `committed=False` for any
   failure in 1–6, without debit or entry;
8. capture fresh subscriber sets for the exact voluntary from/to cells after
   reactions and immediately before mutation;
9. consume the exact recomputed edge cost;
10. call `Entity.update_entity_position(..., parent_event=step.uuid)`;
11. append the voluntarily entered destination and add that same recomputed
    cost;
12. resolve the authoritative stored Step after arrival, including the
    queue-owned children attached during synchronous spatial effects; make one
    detached local copy whose position-evidence map is replaced by the captured
    voluntary from/to grants;
13. phase that detached source to COMPLETION with `committed=True`, replace its
    provisional `movement_cost` with the recomputed cost, and retain the
    returned stored completion;
14. capture `source.position` after synchronous arrival children as the
    objective position;
15. build the existing `MovementStepBoundary` using
    `step_event_uuid=completed_step.uuid`;
16. invoke the continuation guard unconditionally for this committed edge;
17. return objective termination plus the explicit controller decision.

Only an uncanceled, executor-accepted Step follows the action-owned false/true
completion paths. A handler-canceled Step remains CANCEL as §8.3 requires.
Never debit or call `update_entity_position()` before the action-owned true
completion path has passed all revalidation.

Step coordinate evidence must not be recomputed from the mover's objective
position at Step completion. Arrival children run synchronously and may already
have forced the mover elsewhere. The provisional Step keeps the existing
intent evidence for reaction-time privacy. After reactions/revalidation and
immediately before debit/entry, recapture subscribers of the exact voluntary
`from_position` and `to_position` into a local detached map. Install those two
grants by copying—not mutating—the authoritative post-arrival stored Step, so
the completion source also carries its current queue-owned child lists. For
PATH only, `completion_position_observer_evidence()` reads the detached
source's saved from/to map and never substitutes
`completion_locations[source_uuid]` for the voluntary destination. Then call
`phase_to(COMPLETION)` on that detached source; the completion algorithm may
rebuild its output map, but it rebuilds from the saved evidence. DIRECT_ARC
keeps the existing completion-location behavior. The forced-movement child
owns evidence for its own destination. This is two cell-subscriber reads and
one small event copy, not a stored-event mutation, observer service, or public
schema.

`StepMovementEvent.generate_combat_log()` returns `None` when
`committed=False`. The terminal root carries the failure reason; the Step must
not claim “steps to” or `success=True` for a cell never entered. Child OA logs
remain collectable through the event tree even when the false Step itself has
no log.

The provisional Step cost exists so reactions can inspect the pending edge. It
is not authority after reactions. The single recomputed value from step 5 is
used for affordability, debit, Step completion, `MovementStepBoundary`, and the
root committed sum. Reactions that increase or decrease terrain cost, grant or
remove difficult-terrain immunity, or change swimming capability therefore
settle consistently; a newly unaffordable edge remains uncommitted and free.

### 9.1 Debit before arrival is non-negotiable

`Entity.update_entity_position()` synchronously publishes spatial entry.
Hazards can damage, incapacitate, kill, or forcibly displace the mover.
Therefore the correct transaction is:

```python
source.action_economy.consume("movement", step_cost_feet)
Entity.update_entity_position(source, to_position, parent_event=step.uuid)
```

Do not add a refund or rollback after arrival effects.

### 9.2 Boundary truth

Extend `MovementStepBoundary` only with:

```python
objective_position: tuple[int, int]
step_movement_cost: int
```

It already carries actor/root/lineage/Step UUIDs, from/to positions, traversed
path, cumulative spend, remaining movement, and event cursors.

The boundary `to_position` is the voluntary cell paid by this Step.
`objective_position` is where the actor stands after synchronous arrival
children. They may differ.

The focused test must resolve `step_event_uuid` and prove it identifies the
exact `StepMovementEvent(COMPLETION, committed=True)`, not its EFFECT version.

Do not add mode, trajectory, path length, connector, presentation, or transport
fields to this boundary. Consumers can resolve the existing root/Step event
identities when needed.

## 10. Move execution loop

The loop remains in `Move._apply()`. No second executor or service is added.

After an EFFECT returns, apply one root-level gate in this exact order:

1. source still exists and occupies the frozen accepted path start;
2. exact DEAD, otherwise ordinary action permission (DYING/STABLE are
   ACTION_DENIED);
3. if no objective failure won, an EFFECT stop marker completes CANCELED;
4. if no marker exists, run the current-state content prerequisite hook;
5. only then settle fixed costs and begin Steps.

POSITION_DIVERGED, DEAD, or ACTION_DENIED completes the published EFFECT
without consuming a fixed cost and outranks CANCELED. Do not run a second
dynamic movement/path bound before these objective facts.

For every `(from_position, to_position)` in the immutable EFFECT snapshot:

1. before publishing a Step, require current objective position equals
   `from_position`; report exact DEAD, otherwise require action permission
   (DYING/STABLE therefore report ACTION_DENIED);
2. perform the early objective transition check; if it is blocked, retain
   collision memory/publication under §7.4 and use the terminal table;
3. calculate a provisional edge cost using the accepted `movement_mode`, but do
   not terminalize affordability before reactions;
4. construct one `StepMovementEvent(EFFECT, committed=False)` and retain its
   executor-created lineage plus exact planned edge contract;
5. publish that Step, require the returned UUID to resolve to the stored value,
   and require it to remain an exact uncanceled
   `StepMovementEvent(EFFECT, committed=False)` with the planned source,
   parent, from/to positions, index, path length, trajectory, and provisional
   edge cost;
6. if it is canceled, leave the Step at CANCEL and settle only the root under
   §8.3; an invalid handler proposal is already normalized to that cancellation;
7. otherwise pass it to `_commit_move_step()`, which repeats objective checks
   and recomputes exact cost after reactions before any commit;
8. copy returned path/spend/objective/controller facts;
9. terminate or continue according to §10.1.

This is an executor precondition, not a generic handler-security system. It
prevents a trusted Step handler from accidentally making the loop commit a
different edge. It does not add proposal tokens, rewrite EventQueue history,
or define a new interceptor policy.

### 10.1 Terminal precedence after a committed arrival

The guard always sees the committed boundary. The owning loop then chooses:

```text
DEAD
  > ACTION_DENIED
  > POSITION_DIVERGED
  > SUBJECTIVE_REVALIDATION
  > COMPLETED
```

The controller decision and optional reason remain orthogonal evidence even
when objective death/action denial wins. `controller_revalidation` derives from
`decision is INTERRUPT`, never from whether `reason` is non-null.

If an interrupt occurs at the accepted EFFECT endpoint (`effect_event.path[-1]`
and `effect_event.end_position`), termination remains `COMPLETED` while
controller evidence records the interrupt. The original
`requested_end_position` is intent evidence only and never owns final-edge
classification.

### 10.2 Terminal root construction

All completion branches derive from the exact accepted EFFECT event. Preserve
only the non-movement/named facts actually settled by §6.4 and replace the
stale aggregate movement estimate. `settled_fixed_costs` starts empty and is
assigned the exact admitted fixed-cost tuple only after aggregate consumption
fully succeeds:

```python
actual_costs = [
    *settled_fixed_costs,
    BaseCost(
        name="Movement Cost",
        cost_type="movement",
        cost=movement_spent,
    ),
]

return effect_event.phase_to(
    EventPhase.COMPLETION,
    end_position=voluntary_path[-1],
    objective_end_position=source.position,
    path=voluntary_path,
    costs=actual_costs,
    termination_reason=termination_reason,
    controller_revalidation=(decision is INTERRUPT),
    controller_revalidation_reason=decision_reason,
    outcome_code=f"movement.{termination_reason.value}",
)
```

Move's later `_apply_costs()` returns this event unchanged because §6.4 paid
non-movement/named costs before mechanics and committed edges paid movement.

### 10.3 `use_movement_cost=False`

Retain this flag only as existing request-side aggregate-affordability policy.
It may suppress generation of the up-front aggregate movement cost.

It does not make movement free. Every committed edge is still consumed by the
helper, and every root COMPLETION reports the exact actual movement sum.

No new event flag is required because execution never branches on
`use_movement_cost`; it always settles committed edges identically.

## 11. Opportunity-attack corrections

### 11.1 One provocation rule

Replace the concrete condition-name check in
`opportunity_attack_processor()`:

```python
if "Disengaging" in mover.active_conditions:
    return event
```

with the existing neutral rules value:

```python
if (
    mover.action_economy
    .provokes_opportunity_attacks.normalized_score
    <= 0
):
    return event
```

Disengage continues to work because it owns that modifier. Other authored
effects can suppress provocation without a reaction-layer name switch.

### 11.2 Objective reactor capability

Add one high-level Entity query because it combines lifecycle and the reaction
channel:

```python
def can_execute_opportunity_attack(self) -> bool:
    return (
        self.health.life_state is LifeState.ALIVE
        and self.action_economy.reactions.normalized_score >= 1
    )
```

Call it before constructing `Attack`. The existing Attack pre-validation then
proves weapon/range/target/cost details and consumes the ordinary reaction.

Do not use `can_take_actions()` here. The engine intentionally permits a pure
reaction after a rules-owned “turn spent” transform, while incapacitation and
reaction-denial transforms cap reactions to zero.

Before each OA handler constructs its Attack, also re-read the pending mover:

```python
if mover.position != event.from_position:
    return event
if mover.health.life_state is not LifeState.ALIVE:
    return event
if not mover.can_take_actions():
    return event
```

EventQueue invokes matching handlers in order. These objective checks occur
inside every invocation, so if an earlier OA or other reaction kills, denies,
or forcibly displaces the mover, later OA handlers do not attack against the
stale edge. This does not cancel the Step itself; the Move executor observes the
same state after all reactions and settles DEAD, ACTION_DENIED, or
POSITION_DIVERGED.

### 11.3 Discovery remains privacy-safe

Visible preview uses only coarse non-secret truth:

- reactor is subjectively visible;
- reactor life state is exactly ALIVE;
- reactor is hostile;
- disclosed path exits its threat domain;
- mover currently provokes.

Do not inspect or disclose the reactor's remaining reaction count or handler
toggle during preview. A visible preview may conservatively remain after that
reactor spent its reaction; objective execution is exact.

Hidden reactors remain absent from preview but may execute a legal OA
objectively.

## 12. Forced movement

Shove and every existing `ForcedMovementEvent` remain separate:

- no voluntary `StepMovementEvent` for the forced leg;
- no debit from the displaced creature's movement;
- no voluntary continuation callback;
- no voluntary OA caused by the forced leg.

If a child forcibly moves the voluntary mover before entry:

- pending Step completes `committed=False`;
- voluntary path/end remain at the last committed cell;
- objective end is the actual forced position;
- root terminates `POSITION_DIVERGED`;
- the forced leg is not charged and does not start another voluntary edge.

If a child forcibly moves the mover during arrival:

- the voluntary arrival remains paid and committed;
- the boundary `to_position` remains the voluntary arrival;
- boundary/root objective position reports the forced destination;
- remaining Move path terminates `POSITION_DIVERGED` unless DEAD or
  ACTION_DENIED has precedence.

## 13. Combat-log and wire parity

Add to `MovementLogData`:

```python
objective_end_position: Optional[Tuple[int, int]] = Field(
    default=None,
    description="Actual position after synchronous child displacement.",
)
```

Legacy producers may leave it null. New Move terminal logs always copy the
event's explicit value.

Move's log must agree with its terminal event for:

- start position;
- requested destination;
- voluntary endpoint;
- objective endpoint;
- committed voluntary path;
- geometric path distance;
- actual movement cost;
- termination reason;
- controller decision/reason.

Do not infer forced displacement from the path and do not append the forced
destination to it.

`get_affected_positions()` and event-time observer evidence determine who may
receive an event/log; they do not by themselves authorize every coordinate in
the structured summary. Therefore make one narrow change in the existing
`server/combat_log_projection.py` movement owner:

- a controlled mover may retain its complete owned movement geometry;
- a non-controlled mover's subjective root movement geometry is always rebuilt
  exclusively from `committed=True` Step children whose two endpoints survived
  the existing position-evidence checks; an action-owned false Step is attempt
  evidence, never a traversed segment;
- `requested_end_position` and `objective_end_position` are omitted for a
  non-controlled mover, even when every voluntary Step was observed;
- the projected path/end/text/cost use only contiguous observed Step segments;
- an unobserved forced destination, interrupted requested endpoint, or hidden
  collision endpoint never survives merely because the root log was visible;
- objective/admin logs remain unchanged.

Reuse `_sanitize_unlocated_movement_step()` and the existing observed-segment
builder. Extend `_sanitize_partially_observed_movement()` (or rename it to the
truth it now owns) so all non-controlled movement summaries pass through that
step-derived projection, not only summaries missing a Step. Do not add a second
projector or query live Entity/GridMap state.

Regenerate only checked-in generated artifacts through their owners:

```bash
uv run python devtools/generate_event_contract.py
uv run python devtools/generate_event_contract.py --check
uv run python devtools/generate_typescript_sdk.py
uv run python devtools/generate_typescript_sdk.py --check
npm --prefix sdk/typescript run check
```

No handwritten TypeScript change is permitted. Generator freshness and the
TypeScript compile gate are both required; neither substitutes for the other.

## 14. Focused regression matrix

Use parameterized cases where the transaction is identical. The gate is the
behavioral matrix, not a target test count.

### Settlement and modes

- four-position walking path: three committed Steps, 15-foot debit, exact root;
- difficult terrain, Swim, and Fly use the accepted mode and one executor;
- a root handler cannot rewrite walking/Aggressive into FLYING/BURROWING;
- Fly succeeds only while Dragon Wings remains authoritative at both initial
  admission and post-EFFECT execution entry;
- `use_movement_cost=False` still debits/reports every committed edge;
- terminal movement cost equals the sum of committed Step completion costs;
- harmful/lethal arrival debits and commits before damage, then reports exact
  objective termination.

### Root identity, alias isolation, and path integrity

- wrong start, accepted endpoint mismatch, skipped edge, cycle, and overlong
  route reject with normalized zero settlement;
- strict coordinates reject bool/float/string/wrong arity while a serialized
  two-int JSON array round-trips to the tuple contract;
- a longer disclosed legal route executes; an undisclosed/remembered-blocked
  route rejects without objective topology disclosure;
- path, endpoint, and mode handler rewrites produce one exact pre-storage
  cancellation; accepted route geometry has one authority;
- Aggressive's event-owned “move closer” rule is checked initially and again
  after EFFECT against current enemy state;
- root handlers attempting to rewrite runtime type, phase, lineage, source,
  parent, attribution, trajectory, start, original request, terminal fields, or
  costs produce one exact pre-storage CANCEL;
- attempted in-place path/cost/declared-target/observer/child mutation cannot
  alter earlier stored versions or forge grants; nested cost/map/set isolation
  and queue-owned OA-child restoration are exercised;
- constructor, setter, retarget, and `instantiate()` each reject malformed
  coordinates; JSON two-int arrays still normalize and round-trip; instantiate
  cannot override the template-owned movement mode.

### Fixed costs and post-reaction edge costs

- Aggressive Move re-admits and consumes its bonus action exactly once before
  the first Step; `_apply_costs()` performs no second spend;
- Aggressive template instantiation and later retargeting preserve that bonus
  cost while replacing exactly one generated movement estimate;
- declaration snapshots `effective_costs`, including a dynamic/restricted fixed
  cost, rather than bypassing it through raw action costs;
- multiple facts sharing a bucket/resource are aggregate-checked; unavailable
  named resource or action bucket consumes nothing and terminates INVALID_COST;
- unavailable fixed cost after accepted EFFECT yields root COMPLETION and zero
  movement/no fixed cost, whether or not an EFFECT child is visible; any
  attached child remains preserved;
- negative cost/resource values, duplicate movement facts, and a resource
  attached to the aggregate movement fact reject before consumption;
- a handler attempt to add/increase/remove any accepted cost cancels before
  mechanics and cannot create a late overdraft;
- reactions that increase or decrease terrain cost, toggle difficult-terrain
  immunity, or change swimming capability cause the post-reaction recomputed
  value to appear identically in affordability, debit, Step completion,
  boundary, and root;
- a newly unaffordable recomputed edge completes `committed=False`, enters no
  cell, and spends no movement;
- a zero-edge terminal after a fixed cost settled is root COMPLETION retaining
  that exact fixed cost, never a lying zero-cost CANCEL.

### Reactions and settlement order

- ordinary OA damages, then a legal affordable edge commits and pays;
- lethal OA, action denial, forced displacement, blocked transition, and newly
  insufficient movement all stop before entry/debit with their exact reason;
- with two ordered reactors, the second OA does not execute after the first
  kills, denies, or displaces the mover;
- if the first reaction merely damages without stopping the edge, the second
  legal OA still executes.

### Exhaustive zero-commit lifecycle

- parameterize DECLARATION/EXECUTION rejection and assert root CANCEL, zero
  movement, and no completion callback/log;
- order Slowed before an EFFECT canceller/invalid result and assert same-EFFECT
  stop normalization, retained Slowed mutation, zero Step, and root COMPLETION;
- combine the EFFECT stop marker with handler-caused death and displacement;
  assert DEAD/POSITION_DIVERGED precedence, zero cost, and no Step;
- parameterize every post-accepted-EFFECT zero-step branch and assert root
  COMPLETION regardless of whether a visible child/cost exists; include the
  real Slowed EFFECT mutation with no child event;
- an action-owned rejected uncanceled Step stores exactly one COMPLETION with
  `committed=False`, emits no lying Step movement log, and the root completes;
- a canonical handler Step CANCEL stays CANCEL and is never followed by Step
  completion; the already accepted root EFFECT still completes;
- handler attempts at premature Step completion, committed rewrite, subtype,
  lineage/parent/edge/cost/cancellation rewrite become exact Step CANCEL before
  callbacks;
- returned Step UUID is only a validated locator for the captured executor
  lineage/parent/edge contract; queue-owned OA children remain attached after
  proposal restoration.

### Continuation and displacement

- `INTERRUPT` with `reason=None` remains an interruption;
- lethal arrival plus interruption terminates DEAD while retaining controller
  evidence; accepted-final-cell interruption keeps COMPLETED and original
  request evidence never drives the decision;
- pre-entry and post-arrival DYING/STABLE report ACTION_DENIED, never DEAD;
- boundary Step UUID resolves to exact committed COMPLETION with the recomputed
  cost and actual objective position;
- pre-entry displacement is free and divergent; arrival displacement preserves
  the paid voluntary cell and reports objective position separately.

### OA rules, collision memory, discovery, and privacy

- Disengage and a differently named neutral suppression source suppress preview
  and execution without a condition-name switch;
- visible preview remains coarse; hidden hostile is absent but may execute;
- dead/incapacitated/reaction-zero reactor cannot execute, while a merely
  turn-spent ALIVE reactor with a reaction remains legal;
- hidden cell and directional blockers add the exact remembered collision,
  publish one movement-collision spatial fact, enter/debit nothing, and are
  removed from later Move/Swim/Fly discovery;
- final senses refresh/delta runs for success, partial movement, and zero-step
  termination;
- controlled movement log retains owned geometry; a non-controlled log is
  rebuilt from authorized committed Step segments even when every voluntary Step was
  visible, and omits hidden requested/objective endpoints.
- `MovementEvent.get_affected_positions()` never contributes an uncommitted
  requested or child-forced endpoint to recipient discovery;
- forced displacement during synchronous arrival cannot grant forced-cell
  observers coordinate evidence for the voluntary Step destination.

### Cancellation, forced movement, and contracts

- DECLARATION and EXECUTION root cancellations preserve immutable
  request/attribution and exact `canceled_from_phase`;
- an EFFECT canceller becomes an exact same-EFFECT CANCELED stop marker and
  root COMPLETION; ordered Slowed-then-canceller proves earlier no-child
  mechanics are retained and no Step begins;
- Shove remains ForcedMovementEvent, spends no target movement, invokes no
  continuation, and provokes no voluntary OA;
- objective Move combat-log data equals the terminal event, while subjective
  projection obeys the narrower coordinate policy;
- event JSON and generated Python/TypeScript contracts contain the additive
  facts, generator checks pass, and the generated TypeScript package compiles.

### Regression boundary for deferred work

- PATH Step proposals are guarded; DIRECT_ARC Jump proposals retain their
  existing semantics and focused Jump tests remain unchanged/green;
- current condition, Counterspell, and dice-interceptor tests remain green,
  proving no generic EventQueue behavior changed.

## 15. Implementation sequence

### Phase 0 — freeze the dirty baseline

Record exact status and semantic diffs for every scoped file. Preserve existing
CRLF/LF state. Do not reset, checkout, restore, commit, or roll back anything.

### Phase 1 — write the owner regressions

Add the smallest red probes for:

- debit-before-arrival;
- lethal OA free edge;
- discontinuous path rejection;
- immutable root identity and alias-isolated history;
- Aggressive/fixed-cost admission and unavailable named resource;
- post-reaction cost increase/decrease/unaffordable settlement;
- canonical Step CANCEL versus action-owned false completion;
- frozen accepted mode ownership and Dragon Wings post-EFFECT capability;
- forced pre-entry and arrival displacement;
- no-reason continuation;
- neutral OA suppression and objective reactor capability;
- ordered two-reactor stop behavior;
- collision memory/discovery parity;
- subjective movement-coordinate redaction.

Prove each failure before production edits. Do not encode timing, random UUIDs,
global event counts, or exact prose.

### Phase 2 — close contracts and admission

Add the termination reasons, MovementEvent fields, immutable path plus isolated
root/PATH-Step mutable containers, queue-owned metadata restoration, local
strict positions, fixed-cost-preserving retarget/instantiate paths, closed
handler guards, route/cost validators, DECLARATION/EXECUTION cancellation
normalizer, and EFFECT stop-marker normalization.

### Phase 3 — implement the one edge helper and migrate Move

Add aggregate fixed-cost re-admission/settlement, then extract the existing good
Move order into `_commit_move_step()` with post-reaction cost recomputation.
Make every post-accepted-EFFECT exit complete. Keep walking green, then verify
Swim/Fly use the same frozen-mode path and Fly rechecks Dragon Wings.

### Phase 4 — close OA and displacement truth

Replace the name switch, add the objective Entity capability query and per-OA
mover-state recheck, preserve collision learning/senses refresh, thread memory
through Swim/Fly discovery, and add forced-displacement assertions.

### Phase 5 — logs and generators

Add objective endpoint to objective structured logs, close the existing
subjective movement projection, and regenerate the exact generated owners. Do
not touch handwritten SDK/frontend code.

### Phase 6 — focused verification and external review

Run only the bounded commands in §16. Stop implementation and request an
independent read-only review. Do not repair findings during that review.

## 16. Focused commands

Run files individually:

```bash
uv run pytest tests/engine/test_move_settlement.py -q
uv run pytest tests/engine/test_combat_actions.py -q
uv run pytest tests/engine/test_action_discovery.py -q
uv run pytest tests/engine/test_senses_light_stealth.py -q
uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q
uv run pytest tests/manual/test_50_movement_revalidation.py -q
uv run pytest tests/manual/test_97_event_wire_contract.py -q
uv run pytest tests/manual/test_113_subjective_combat_log_projection.py -q
uv run pytest tests/manual/test_126_jump_legacy_contract.py -q
```

The focused Jump owner is a regression fence only; do not change its semantics
or add new Jump behavior assertions in this unit.

Run the exact direct-consumer nodes rather than promoting several multi-thousand
line files into a new batch gate:

```bash
uv run pytest tests/progression/test_sorcerer_character_grant_appliers.py::test_dragon_wings_materializes_a_reversible_flying_action -q
uv run pytest tests/manual/test_121_canonical_presentation_mapper.py::test_committed_step_events_form_one_ordered_movement_segment -q
uv run pytest tests/manual/test_121_canonical_presentation_mapper.py::test_hidden_step_reaction_does_not_leak_through_movement_segmentation -q
uv run pytest tests/manual/test_121_canonical_presentation_mapper.py::test_step_completion_freezes_pre_and_post_position_evidence_for_logs -q
uv run pytest tests/manual/test_121_canonical_presentation_mapper.py::test_boundary_location_grant_does_not_disclose_movement_origin -q
uv run pytest tests/manual/test_122_canonical_replication_runtime.py::test_each_committed_movement_step_has_authoritative_perception_frame -q
uv run pytest tests/manual/test_122_canonical_replication_runtime.py::test_spike_damage_is_scheduled_after_its_destination_arrival -q
uv run pytest tests/manual/test_102_game_summary.py::test_representative_terminal_match_reduces_objective_typed_evidence -q
```

These are the actual Fly, presentation, replication, arrival-order, privacy,
and summary consumers. The 4,000-line spell-family file is not a mandatory gate
unless implementation touches a spell family or a focused red identifies a
direct dependency.

Run the generic event families most exposed to accidental EventQueue drift:

```bash
uv run pytest tests/engine/test_condition_content_evidence.py -q
uv run pytest tests/engine/test_dice_event_semantics.py -q
```

Run generator checks and the TypeScript compile check from §13, then scoped
Pyright over only changed production and focused test files.

Never run:

```bash
pytest
uv run pytest
uv run pytest tests
uv run pytest tests/manual
```

Never batch archived server tests.

## 17. Complexity and dependency gates

Move execution remains:

```text
O(attempted path edges + normal matching handler work)
```

Per edge, the patch may perform constant-time state checks plus the existing
GridMap transition, cost, event, and position operations.

Forbidden in the loop:

- path recomputation;
- action discovery;
- global EventQueue scans;
- entity/world deep copies;
- JSON or SDK projection;
- catalog/registry scans;
- server calls;
- locks, threads, tasks, sleeps, waits, futures, or queues.

Dependency direction remains:

```text
actions/entity
    -> core event/action-execution/grid contracts
```

No local import, `TYPE_CHECKING`, dynamic import, or server dependency may be
added to hide a cycle.

## 18. Acceptance gates

This unit is complete only when all are true.

### Mechanics

- [ ] Every committed Move edge pays before objective entry.
- [ ] Every uncommitted edge is free and does not voluntarily move.
- [ ] Move, Swim, and Fly use one executor and the accepted event mode.
- [ ] Root/Step stored history cannot be mutated through shallow aliases.
- [ ] Root handlers can change only safe status text; route, endpoint, mode,
      costs, causal identity, and queue-owned metadata are frozen/restored.
- [ ] Accepted fixed costs are aggregate-rechecked and consumed exactly once
      before Steps; later `_apply_costs()` is a no-op.
- [ ] Retargeting/instantiation replace only generated movement estimates and
      preserve Aggressive/named/authored fixed costs.
- [ ] Declaration snapshots `effective_costs`; aggregate movement evidence
      cannot also hide a named-resource cost.
- [ ] Every edge cost is recomputed after reactions and the same value owns
      affordability, debit, Step, boundary, and root evidence.
- [ ] Terminal path/end/movement-cost contain only committed voluntary movement;
      legitimate fixed costs remain exact.
- [ ] Objective end truthfully carries child displacement.
- [ ] `use_movement_cost=False` does not create free committed movement.
- [ ] Lethal pre-entry OA is free; lethal arrival is paid and committed.
- [ ] Position divergence never teleports the actor back onto the route.
- [ ] DECLARATION/EXECUTION rejection cancels; EFFECT veto/invalid results
      become same-EFFECT stop markers; every published EFFECT completes without
      a child-history predicate.
- [ ] Exact DEAD is distinct from DYING/STABLE ACTION_DENIED, before and after
      an edge.
- [ ] A `committed=False` Step produces no successful movement log.

### Path and continuation

- [ ] Submitted routes are strict, bounded, contiguous, disclosed, and checked
      with remembered collision evidence.
- [ ] Constructor, setter, retarget, and instantiate overrides enforce exact
      coordinates while JSON two-int arrays round-trip.
- [ ] Execution uses the exact validated EFFECT event, not action caches.
- [ ] Move-family content constraints consume accepted event facts; Aggressive
      remains “toward a visible enemy” and Fly requires current Dragon Wings
      after EFFECT.
- [ ] The guard observes every committed arrival before termination.
- [ ] No-reason interruption is representable.
- [ ] Objective death/action denial outranks controller interruption.
- [ ] Boundary Step UUID identifies the exact committed completion.
- [ ] The returned Step UUID resolves to the captured executor
      lineage/parent/edge contract rather than redefining it.
- [ ] Collision memory/publication and final senses refresh/delta are preserved.
- [ ] Swim/Fly discovery uses the same remembered collision evidence.

### OA and privacy

- [ ] OA execution uses neutral provocation, not a condition name.
- [ ] Objective reactor lifecycle/reaction capability is checked.
- [ ] A later OA cannot execute after an earlier reaction kills, action-denies,
      or displaces the mover; topology and affordability remain Move-owned.
- [ ] A merely spent turn does not incorrectly suppress reactions.
- [ ] Hidden reactors remain absent from preview.
- [ ] Discovery does not leak reaction balance or handler toggle.
- [ ] Forced movement does not become voluntary OA/movement.
- [ ] Non-controlled movement logs derive coordinates only from authorized Step
      segments and omit requested/objective endpoints.
- [ ] `MovementEvent.get_affected_positions()` excludes uncommitted
      requested/forced endpoints; generic participant visibility is not
      misrepresented as movement-coordinate authority.
- [ ] A forced arrival child cannot lend its destination observers to the
      voluntary Step coordinate grant.

### Scope

- [ ] PATH Step guard is local; no Jump executor/event-schema redesign or
      DIRECT_ARC behavior change occurred.
- [ ] EventQueue/preflight use only the default-preserving guard selector; no
      token, lifecycle, ordering, or child-reconciliation change occurred.
- [ ] No server route/runtime/frontend/handwritten-SDK code changed; the only
      server edit is the existing movement combat-log privacy projector.
- [ ] No new service, reducer, journal, thread, task, or queue was added.
- [ ] Generated mirrors are fresh through checked-in generators.
- [ ] Generated TypeScript compiles with `npm --prefix sdk/typescript run check`.
- [ ] Focused tests and scoped Pyright are green.
- [ ] The maintained action-cost owner proves effective-cost construction,
      `model_copy` transforms, discovery, and consumption remain green.
- [ ] Semantic diff contains no unrelated formatting or line-ending churn.

## 19. Independent reviewer checklist

Reject the patch for any of these:

1. committed edge without matching debit;
2. debit or voluntary entry for an uncommitted edge;
3. requested destination/path reported as actual after stopping early;
4. execution reading `self.path`, `self.movement_mode`, or `self.costs` after
   the accepted EFFECT snapshot;
5. handler rewrite of route/mode/root causal identity, forged observer/child
   metadata, alias mutation of stored history, or lost legitimate OA child;
6. fixed cost lost, consumed twice, partially consumed after failed aggregate
   admission, bypassed by reading raw rather than effective costs, hidden on a
   replaced movement fact, or consumed after root COMPLETION;
7. stale pre-reaction edge cost used for affordability/debit/evidence;
8. malformed, cyclic, undisclosed, or remembered-blocked route accepted;
9. Move-family content such as Aggressive/Fly validating action caches instead
   of accepted event facts and current content authority;
10. arrival effects running before debit;
11. wrong CANCEL/COMPLETION phase for any executor zero-commit branch;
12. handler-canceled Step followed by fabricated false completion, or child
    lookup anchored to an unvalidated returned lineage;
13. collision memory/reveal or final senses delta removed;
14. death/action denial hidden by an optional controller reason;
15. forced destination appended to voluntary path or charged/provoking OA;
16. a later OA firing after an earlier reaction killed, denied, or displaced the
    mover;
17. dead/incapacitated OA or incorrect suppression of a merely turn-spent
   reaction;
18. hidden-reactor preview or subjective movement-coordinate leak;
19. uncommitted Step claiming successful movement, or forced-destination
    observers granted the voluntary arrival coordinate;
20. malformed coordinate accepted through setter/instantiate/model-copy paths;
21. PATH guard changing DIRECT_ARC Jump handler semantics;
22. any EventQueue change beyond the default-preserving guard selector, or any
    Jump redesign;
23. second movement executor/authority;
24. global/per-creation work added for this action;
25. handwritten SDK/frontend coordination;
26. tests passing without asserting exact phase, position, path, cost, and
    termination on each core branch.

The reviewer may recommend separate Jump or generic-event follow-up work, but
must not require those deferred designs to be implemented inside this unit.

## 20. Handoff format

The implementer's final report must contain:

1. exact files changed;
2. final edge transaction order;
3. focused red probes that became green;
4. exact commands/results;
5. scoped Pyright result;
6. generator/check result;
7. semantic diff and line-ending audit;
8. any unrelated pre-existing failure separated from this unit;
9. explicit confirmation that Jump and generic EventQueue were not redesigned.

This unit succeeds when Move-family mechanics become truthful and remain
simple. It does not succeed by proving the engine resilient to every
hypothetical handler or by claiming a locomotion model the game does not yet
own.
