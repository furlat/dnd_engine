# Spatial-Effect Reveal Idempotency — Complete Implementation Plan

**Status:** forward implementation specification

**Date:** 2026-08-05

**Scope:** one engine correctness patch plus focused tests

## 1. Mission

Make `SpatialEffect.publish_revealed()` a one-way, idempotent objective state
transition.

After this patch:

- the first reveal of an installed hidden spatial effect clears its objective
  concealment state and publishes exactly one typed reveal lifecycle;
- later reveal requests are true no-ops;
- an effect installed without concealment does not manufacture a reveal event;
- an uninstalled or retired effect cannot be revealed;
- the existing typed spatial-effect event remains the sole notification for
  this transition;
- no server, frontend, runtime coordination, persistence, SDK, or background
  work is added.

This document is self-contained. Implement it directly against the current
tree using only the owners and gates defined below.

## 2. Files in scope

Production:

```text
dnd/spatial_effects.py
```

New focused regression:

```text
tests/engine/test_spatial_effect_reveal_idempotency.py
```

One existing integrated regression receives one additional assertion:

```text
tests/manual/test_spike_zone_movement_legacy_contract.py
```

No other production, server, SDK, frontend, content-definition, dependency, or
documentation file should need modification.

## 3. Existing ownership model

### 3.1 SpatialEffect owns objective world identity and perceivability

`SpatialEffect` is an independent `BaseBlock` representing one persistent
ground, cloud, or field phenomenon. Its relevant state is:

```python
stealth_dc: Optional[int]
_created_event_published: bool
affected_positions: Set[Tuple[int, int]]
```

`stealth_dc` is inherited from `BaseBlock`. Its meaning is:

- integer: the effect is objectively concealed from observers whose passive
  perception does not beat the DC;
- `None`: the effect is not concealed by this mechanism.

`BaseBlock.is_perceivable_by()` reads this field. Therefore a reveal event
without clearing `SpatialEffect.stealth_dc` is internally contradictory: the
event says “revealed” while the effect remains concealed.

### 3.2 A controller owns its own mechanical disclosure policy

Some spatial effects also have controller-level concealment. The spike-trap
controller uses:

```python
condition_stealth_dc: Optional[int]
```

This field gates hazard knowledge through `BaseBlock.is_hazardous_for()`. It is
not a duplicate of `SpatialEffect.stealth_dc`:

- `SpatialEffect.stealth_dc` controls whether the world effect itself is
  perceivable;
- `SpatialEffectController.condition_stealth_dc` controls whether the
  controller-owned hazard mechanics are disclosed as hazardous.

The authored spike-trap recipe initializes both values from the same authored
DC. Its controller already performs the correct controller-side transition:

```python
def _reveal(self, *, parent_event: Event) -> None:
    """Reveal the complete linked trap network after its first trigger."""
    if self.condition_stealth_dc is None:
        return
    self.condition_stealth_dc = None
    effect = self._effect_host()
    if effect is None:
        raise RuntimeError("Spike trap controller has no spatial-effect owner")
    effect.publish_revealed(parent_event=parent_event)
```

Do not move this controller-specific logic into `SpatialEffect`. A generic
spatial effect must not guess which controller facts a particular authored
hazard wants to clear.

### 3.3 The typed reveal event is already the correct notification

`SpatialEffect._publish_change()` creates a
`SpatialEffectChangeEvent(operation=REVEALED)` and publishes it through:

```python
EventQueue.publish_lifecycle(event)
```

That lifecycle already provides:

- objective effect UUID;
- exact authored `ContentRef`;
- layer;
- anchor position;
- canonical current and previous footprint;
- causal `parent_event` linkage;
- a typed spatial-effect combat log;
- spatial dispatch across the effect footprint;
- sensory cache/path invalidation through `SpatialSensesCallback`.

Consequently, the patch must not also call `BaseBlock.set_stealth_dc(None)`.
That helper emits a generic `SPATIAL_PERCEIVABILITY_CHANGED` event. Calling it
here would create two notifications for one state transition and could produce
duplicate sensory work. The correct implementation mutates the effect field,
then publishes the already-specific reveal lifecycle.

## 4. Defect

The current method validates installation and publishes a reveal event, but it
does not use `stealth_dc` as the one-way transition latch:

```python
def publish_revealed(
    self,
    *,
    parent_event: Event,
) -> Optional[SpatialEffectChangeEvent]:
    """Publish the one-way transition from hidden to globally revealed."""
    if not self._created_event_published:
        raise RuntimeError("Cannot reveal an uninstalled spatial effect")
    return self._publish_change(
        SpatialEffectChangeOperation.REVEALED,
        previous_positions=set(self.affected_positions),
        parent_event=parent_event,
    )
```

This permits both invalid outcomes:

1. the method emits `REVEALED` while `self.stealth_dc` remains non-`None`;
2. repeated calls emit repeated reveal lifecycles.

The existing controller guard masks the second problem on one normal spike
trap path, but the effect method itself still violates its contract and remains
unsafe for other callers.

## 5. Required state machine

The method is governed by two facts, evaluated in this order:

```text
_created_event_published    stealth_dc       result
------------------------    ----------       -------------------------------
False                       any value        raise RuntimeError
True                        None             return None; publish nothing
True                        integer          clear DC; publish one REVEALED
```

The installation check must remain first. A retired effect sets
`_created_event_published=False`; it must raise even though retirement may also
leave `stealth_dc=None`. Returning a no-op for a retired owner would hide a
lifecycle misuse.

An installed effect authored as visible starts with `stealth_dc=None`. A call
to `publish_revealed()` on it is harmless and silent. No transition occurred,
so no reveal event is valid.

## 6. Exact production implementation

Replace only `SpatialEffect.publish_revealed()` in `dnd/spatial_effects.py`
with the following complete method:

```python
def publish_revealed(
    self,
    *,
    parent_event: Event,
) -> Optional[SpatialEffectChangeEvent]:
    """Publish the one-way transition from hidden to globally revealed."""
    if not self._created_event_published:
        raise RuntimeError("Cannot reveal an uninstalled spatial effect")
    if self.stealth_dc is None:
        return None
    self.stealth_dc = None
    return self._publish_change(
        SpatialEffectChangeOperation.REVEALED,
        previous_positions=set(self.affected_positions),
        parent_event=parent_event,
    )
```

This is the entire production-code change.

### 6.1 Why the state changes before event publication

The reveal lifecycle describes an already-committed world transition. Existing
spatial-effect methods follow the same order: update the objective effect and
grid state first, then publish `_publish_change()` as the immutable lifecycle
fact.

Pre-completion sensory callbacks handling the reveal must observe the new
state. Clearing `stealth_dc` after publication would let a callback process a
`REVEALED` event while the effect still answered “concealed.”

### 6.2 Why no rollback wrapper is added

`EventQueue` is the in-process authoritative event owner, not an external
durability port. The spatial-effect subsystem already uses commit-then-publish
ordering for footprint changes and retirement. This small patch must preserve
that existing engine transaction model rather than introducing a special
one-method rollback protocol.

### 6.3 Why direct assignment is correct here

Do this:

```python
self.stealth_dc = None
```

Do not do this:

```python
self.set_stealth_dc(None, parent_event=parent_event.uuid)
```

The latter would publish `SPATIAL_PERCEIVABILITY_CHANGED` in addition to the
typed `SPATIAL_EFFECT_CHANGED/REVEALED` lifecycle. The typed reveal event
already reaches sensory invalidation and is the more precise fact.

## 7. Complete focused regression file

Create `tests/engine/test_spatial_effect_reveal_idempotency.py` with the
following complete contents:

```python
"""One-way and idempotent spatial-effect reveal regressions."""

from __future__ import annotations

from typing import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.content_system.spatial_effect_materialization import (
    materialize_spatial_effect,
)
from dnd.core.events import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
    SpatialEffectChangeEvent,
)
from dnd.core.spatial_effect_types import SpatialEffectChangeOperation
from dnd.environmental_effect_runtime import materialize_spike_trap_effect
from dnd.environmental_effects import SpikeTrapGroundEffect
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial_effect_content import spike_trap_effect_recipe


def _begin_parent_effect(source_entity_uuid: UUID) -> Event:
    """Publish one real causal parent through its effect phase."""
    declaration = Event(
        name="Reveal Spatial Effect",
        source_entity_uuid=source_entity_uuid,
        source_entity_name="Environment",
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    accepted = EventQueue.publish_declaration(declaration)
    assert not accepted.canceled
    execution = accepted.phase_to(EventPhase.EXECUTION)
    assert not execution.canceled
    effect = execution.phase_to(EventPhase.EFFECT)
    assert not effect.canceled
    return effect


def _completed_reveals_since(
    cursor: int,
    effect_uuid: UUID,
) -> Iterator[SpatialEffectChangeEvent]:
    """Yield completed reveal facts for one exact spatial effect."""
    for _, event in EventQueue.iter_events_since(cursor):
        if (
            isinstance(event, SpatialEffectChangeEvent)
            and event.phase is EventPhase.COMPLETION
            and event.spatial_effect_uuid == effect_uuid
            and event.operation is SpatialEffectChangeOperation.REVEALED
        ):
            yield event


def test_hidden_effect_reveals_once_then_becomes_a_true_noop() -> None:
    """The effect DC is the one-way latch for one typed reveal lifecycle."""
    reset_engine_runtime(grid_size=(4, 4))
    positions = {(1, 1), (2, 1)}
    effect = materialize_spike_trap_effect(positions, stealth_dc=20)
    parent = _begin_parent_effect(effect.source_entity_uuid)
    cursor_before_reveal = EventQueue.event_cursor()

    assert effect.stealth_dc == 20

    first = effect.publish_revealed(parent_event=parent)

    assert first is not None
    assert first.phase is EventPhase.COMPLETION
    assert first.operation is SpatialEffectChangeOperation.REVEALED
    assert first.parent_event == parent.uuid
    assert first.spatial_effect_uuid == effect.uuid
    assert first.spatial_effect_content_ref == effect.content_ref
    assert first.affected_positions == tuple(sorted(positions))
    assert first.previous_positions == tuple(sorted(positions))
    assert first.combat_log is not None
    assert first.combat_log.data["operation"] == "revealed"
    assert effect.stealth_dc is None

    cursor_after_first = EventQueue.event_cursor()
    second = effect.publish_revealed(parent_event=parent)

    assert second is None
    assert effect.stealth_dc is None
    assert EventQueue.event_cursor() == cursor_after_first
    assert list(_completed_reveals_since(
        cursor_before_reveal,
        effect.uuid,
    )) == [first]

    completed_parent = parent.phase_to(EventPhase.COMPLETION)
    assert not completed_parent.canceled


def test_installed_visible_effect_does_not_invent_a_reveal() -> None:
    """An effect authored without concealment has no reveal transition."""
    reset_engine_runtime(grid_size=(4, 4))
    effect = materialize_spike_trap_effect({(1, 1)}, stealth_dc=None)
    parent = _begin_parent_effect(effect.source_entity_uuid)
    cursor = EventQueue.event_cursor()

    assert effect.stealth_dc is None
    assert effect.publish_revealed(parent_event=parent) is None
    assert effect.stealth_dc is None
    assert EventQueue.event_cursor() == cursor
    assert list(_completed_reveals_since(cursor, effect.uuid)) == []

    completed_parent = parent.phase_to(EventPhase.COMPLETION)
    assert not completed_parent.canceled


def test_uninstalled_effect_cannot_be_revealed() -> None:
    """Installation truth takes precedence over the concealment latch."""
    reset_engine_runtime(grid_size=(4, 4))
    source_entity_uuid = uuid4()
    effect = materialize_spatial_effect(
        spike_trap_effect_recipe(stealth_dc=20),
        source_entity_uuid,
        position=(1, 1),
        faction=None,
        expected_type=SpikeTrapGroundEffect,
    )
    parent = _begin_parent_effect(source_entity_uuid)
    cursor = EventQueue.event_cursor()

    assert effect.stealth_dc == 20
    with pytest.raises(
        RuntimeError,
        match="Cannot reveal an uninstalled spatial effect",
    ):
        effect.publish_revealed(parent_event=parent)

    assert effect.stealth_dc == 20
    assert EventQueue.event_cursor() == cursor
    assert list(_completed_reveals_since(cursor, effect.uuid)) == []

    completed_parent = parent.phase_to(EventPhase.COMPLETION)
    assert not completed_parent.canceled
```

## 8. Existing integration regression enhancement

In
`tests/manual/test_spike_zone_movement_legacy_contract.py`, locate:

```python
def test_hidden_spike_trap_reveals_its_exact_effect_once_when_triggered() -> None:
```

Immediately after the existing assertion that the controller concealment is
cleared:

```python
assert controller.condition_stealth_dc is None
```

add:

```python
assert effect.stealth_dc is None
```

The resulting local block should read:

```python
controller = effect.active_conditions["Spike Trap"]
assert isinstance(controller, SpikeTrapController)
assert controller.condition_stealth_dc is None
assert effect.stealth_dc is None
reveal_events = [
    event
    for _, event in EventQueue.iter_events_since(cursor)
    if isinstance(event, SpatialEffectChangeEvent)
    and event.phase.value == "completion"
    and event.spatial_effect_uuid == effect.uuid
    and event.operation is SpatialEffectChangeOperation.REVEALED
]
assert len(reveal_events) == 1
```

This integrated assertion proves that the real trap-trigger call path clears
both independently meaningful concealment facts:

- controller hazard disclosure;
- effect perceivability.

Do not otherwise rewrite or broaden that legacy-contract test.

## 9. Required behavioral invariants

All of the following must hold:

1. `publish_revealed()` validates installation before testing concealment.
2. The first installed-hidden call clears `SpatialEffect.stealth_dc`.
3. The first installed-hidden call publishes exactly one completed
   `SpatialEffectChangeEvent` with operation `REVEALED`.
4. The event is causally linked to the supplied parent event.
5. The event retains the exact effect UUID and authored `ContentRef`.
6. Current and previous footprints are unique, sorted, and equal for reveal.
7. The reveal combat log remains typed and reports `operation="revealed"`.
8. A second call returns `None`.
9. A second call does not advance `EventQueue.event_cursor()`.
10. A second call does not produce a second combat log.
11. An installed-visible effect returns `None` without publishing anything.
12. An uninstalled effect raises and retains its original `stealth_dc`.
13. A retired effect continues to fail the installation check.
14. The spike-trap trigger clears both controller and effect concealment.
15. The effect footprint, controller, content identity, and registry ownership
    do not change during reveal.

## 10. Event-order proof

For a triggered hidden spike trap, the intended causal sequence is:

```text
SPATIAL_ENTITY_ENTERED (EFFECT)
  -> SpikeTrapController._reveal(parent_event=entry)
     -> condition_stealth_dc = None
     -> SpatialEffect.publish_revealed(parent_event=entry)
        -> SpatialEffect.stealth_dc = None
        -> SPATIAL_EFFECT_CHANGED / REVEALED lifecycle
           -> sensory callbacks invalidate relevant visibility/path caches
           -> completed typed spatial-effect combat log
  -> spike damage causal work continues
```

On later entries into any cell of the same trap network:

```text
SpikeTrapController._reveal(...)
  -> condition_stealth_dc is None
  -> return without calling SpatialEffect.publish_revealed()
```

Even if another correct caller invokes `publish_revealed()` directly after the
first reveal, `SpatialEffect.stealth_dc is None` independently enforces the
same no-op result.

This gives both layers local idempotency without creating a new coordinator.

## 11. Performance requirements

The production delta performs:

- one boolean/private-state check already present;
- one `Optional[int]` comparison;
- one field assignment on the first transition;
- the already-existing event lifecycle only on the first transition.

Expected complexity:

```text
first actual reveal: existing event cost + O(1)
later reveal call:   O(1), zero events
game creation:       no additional work
normal movement:     no additional work unless the reveal occurs
```

The implementation must not add:

- observer/subscriber scans;
- per-position observer evidence construction;
- visibility recomputation inside `publish_revealed()`;
- action discovery;
- movement-path construction;
- serialization or deserialization;
- hashing or digests;
- server or SDK projection;
- persistence;
- locks, queues, tasks, executors, or threads.

Sensory work remains event-driven through the existing
`SpatialEffectChangeEvent` callback path.

## 12. Dependency requirements

The production method uses only names already imported by
`dnd/spatial_effects.py`:

- `Event`;
- `SpatialEffectChangeEvent`;
- `SpatialEffectChangeOperation`.

No new production import is required.

In particular, do not import:

- `Entity` into this method/module for reveal handling;
- server projection or transport code;
- player-facing contracts;
- concrete spike-trap content into the generic `SpatialEffect` owner;
- a second event or sensory service.

## 13. Focused validation commands

Run tests individually, never the whole suite:

```bash
uv run pytest tests/engine/test_spatial_effect_reveal_idempotency.py
uv run pytest tests/manual/test_spike_zone_movement_legacy_contract.py
```

Then run the nearest maintained sensory regression individually because the
typed reveal event drives sensory invalidation:

```bash
uv run pytest tests/engine/test_senses_light_stealth.py
```

Do not batch archived server tests and do not run unbounded `pytest`.

## 14. Static review checklist

Before reporting completion, inspect the final diff and confirm:

```text
[ ] only the expected production method changed
[ ] the focused test file was added
[ ] the integrated test gained only the missing effect-state assertion
[ ] no production import was added
[ ] no server/frontend/runtime SDK file changed
[ ] no generic perceivability event was added
[ ] no observer enumeration was added
[ ] no thread/task/queue/lock was added
[ ] no content name or Python path became an identity
[ ] no unrelated formatting churn is present
```

Useful read-only checks:

```bash
git diff -- dnd/spatial_effects.py
git diff -- tests/engine/test_spatial_effect_reveal_idempotency.py
git diff -- tests/manual/test_spike_zone_movement_legacy_contract.py
rg -n "def publish_revealed|set_stealth_dc|located_position_observer" dnd/spatial_effects.py
```

The source scan supports review but does not replace the behavioral tests.

## 15. Explicit non-goals

Do not expand this patch into any of the following:

- subjective/player projection changes;
- new observer-evidence payloads;
- combat-log enum renames;
- spatial-effect presentation cues;
- SDK generation;
- replay or persistence work;
- generalized stealth redesign;
- automatic controller introspection;
- trap damage, movement, or opportunity-attack changes;
- footprint transition or retirement changes;
- content recipe changes;
- server endpoint changes;
- frontend changes;
- performance instrumentation frameworks.

If one of these appears necessary during implementation, stop and report the
exact evidence. It is outside this patch rather than permission to broaden it.

## 16. Completion definition

This patch is complete only when:

- the exact production state machine is implemented;
- all three focused test commands pass;
- the integrated spike-trap path proves both concealment facts are cleared;
- repeated reveal proves no event-cursor movement;
- installed-visible and uninstalled branches are covered;
- the final diff satisfies the scope and dependency checklists;
- no unrelated failure is silently repaired or ignored.

The implementation report must include:

```text
Files changed:
Exact tests run:
Pass/fail counts:
Production diff summary:
Confirmation of zero new imports:
Confirmation of zero server/frontend/SDK changes:
Confirmation of zero thread/task/queue additions:
Any unexpected existing failure and its deterministic reproducer:
```
