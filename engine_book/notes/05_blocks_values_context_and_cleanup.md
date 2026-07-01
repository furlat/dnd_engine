# 05. Blocks, Values, Context, And Cleanup

## Purpose

`BaseBlock` is the engine's component container. Entities, tiles, items, equipment blocks, health blocks, senses blocks, and many smaller systems use the same core behavior:

- discover directly owned `ModifiableValue` fields.
- discover directly owned child `BaseBlock` fields.
- propagate targets and context through the owned tree.
- optionally own event handlers and conditions.
- remove condition state through one cleanup boundary.

This chapter documents current behavior in `dnd/core/base_block.py`, `dnd/core/base_conditions.py`, `dnd/core/values.py`, and `dnd/core/events.py`.

## Source Files Studied

- `dnd/core/base_block.py`
- `dnd/core/base_conditions.py`
- `dnd/core/values.py`
- `dnd/core/events.py`
- `dnd/entity.py`
- `examples/test_condition_removal_system.py`
- `examples/test_child_parent_notification.py`
- `examples/test_handler_toggle.py`
- `tests/engine_book/test_chapter_05_blocks_context.py`

## Rules Relationship

Status: `Engine extension` as engine infrastructure.

The SRD does not define engine blocks. Blocks are the internal structure that lets SRD mechanics attach to actors and objects: ability scores, saving throws, armor class, hit points, actions, conditions, equipment, light, terrain, and senses all need a common way to carry values, context, and cleanup.

Later chapters connect specific blocks to SRD rules. This chapter stays at the container boundary.

## Direct Discovery

During model validation, `BaseBlock.populate_blocks_and_values()` inspects declared Pydantic fields on the block class. Fields whose values are `ModifiableValue` instances go into `values`; fields whose values are `BaseBlock` instances go into `blocks`.

This discovery is shallow:

- `get_values()` returns direct values only.
- `get_values(deep=True)` recursively includes child-block values.
- `get_blocks()` returns direct child blocks only.
- `get_value_from_name()` and `get_value_from_uuid()` search direct values only.
- `get_block_from_name()` and `get_block_from_uuid()` search direct child blocks only.

Example EB-05-001:

```python
block = make_parent_block(source_uuid)

assert block.get_value_from_name("Direct Value") is block.direct_value
assert block.get_block_from_name("Child Block") is block.child
assert block.get_value_from_name("Leaf Value") is None

assert block.get_values() == [block.direct_value]
assert {value.uuid for value in block.get_values(deep=True)} == {
    block.direct_value.uuid,
    block.child.leaf_value.uuid,
}
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_001_blocks_discover_direct_and_deep_values`.

## Constructor Propagation

Constructor order matters. `BaseBlock` first discovers explicit Pydantic fields
that are `ModifiableValue` or child `BaseBlock` instances, then propagates the
parent source, target, and context through that discovered tree. A block
constructed with direct values or child blocks that previously belonged to a
different source is normalized to the parent owner during construction.

Example EB-05-013:

```python
foreign_child = LeafBlock(
    source_entity_uuid=foreign_source_uuid,
    leaf_value=foreign_leaf_value,
)
foreign_direct_value = make_value(foreign_source_uuid, "Foreign Direct Value", 2)

block = ParentBlock(
    source_entity_uuid=parent_source_uuid,
    target_entity_uuid=target_uuid,
    context={"phase": "construction"},
    direct_value=foreign_direct_value,
    child=foreign_child,
)

assert block.values == {foreign_direct_value.uuid: foreign_direct_value}
assert block.blocks == {foreign_child.uuid: foreign_child}
assert block.direct_value.source_entity_uuid == parent_source_uuid
assert block.child.source_entity_uuid == parent_source_uuid
assert block.child.leaf_value.source_entity_uuid == parent_source_uuid
assert block.direct_value.target_entity_uuid == target_uuid
assert block.child.context == {"phase": "construction"}
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_013_constructor_source_propagates_after_field_discovery`.

## Block Registry

Every `BaseBlock` registers itself in `BaseBlock._registry` during post-init. `BaseBlock.get(uuid)` retrieves the block if present and raises if the registry contains a non-block under that UUID.

Unlike `BaseObject`, `BaseBlock` does not expose a `use_register` opt-out field. Blocks are live world/component objects by default.

The registry is used by condition cleanup and cross-block links. A condition on one block can point at another block by UUID without importing that block's concrete class.

## Target Propagation

`BaseBlock.set_target_entity()` sets the block target and recursively propagates the same target to:

- every direct `ModifiableValue`.
- every direct child `BaseBlock`.
- all values inside child blocks through recursive calls.

For a `ModifiableValue`, target propagation reaches:

- the value itself.
- `self_static`.
- `self_contextual`.
- `to_target_static`.
- `to_target_contextual`.

`BaseBlock.clear_target_entity()` clears the same tree. On each `ModifiableValue`, clearing the target also clears `from_target_static` and `from_target_contextual`, because copied target modifiers are no longer valid without a target.

Example EB-05-002:

```python
block.set_target_entity(target_uuid, "Target")

assert block.direct_value.target_entity_uuid == target_uuid
assert block.direct_value.self_static.target_entity_uuid == target_uuid
assert block.direct_value.to_target_contextual.target_entity_uuid == target_uuid
assert block.child.leaf_value.target_entity_uuid == target_uuid

block.clear_target_entity()

assert block.direct_value.target_entity_uuid is None
assert block.direct_value.from_target_static is None
assert block.child.leaf_value.target_entity_uuid is None
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_002_target_propagation_reaches_values_and_child_blocks`.

## Context Propagation

`BaseBlock.set_context()` sets the block context and recursively propagates the same object to direct values and child blocks.

For a `ModifiableValue`, context propagation reaches:

- the value itself.
- `self_contextual`.
- `to_target_contextual`.

It does not write context to `self_static` or `to_target_static`. Static channels are not context-evaluated.

Example EB-05-003:

```python
context = {"range": "melee", "cover": "none"}
block.set_context(context)

assert block.context is context
assert block.direct_value.context is context
assert block.direct_value.self_contextual.context is context
assert block.direct_value.to_target_contextual.context is context
assert block.direct_value.self_static.context is None
assert block.child.leaf_value.context is context

block.clear_context()
assert block.direct_value.self_contextual.context is None
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_003_context_propagation_reaches_contextual_channels`.

## Lifecycle Gate

`BaseBlock` has an `allow_events_conditions` flag. It defaults to `False`.

When the flag is false:

- `add_condition()` returns `None`.
- `remove_condition()` does nothing.
- `advance_duration()` returns `False`.
- event-handler ownership helpers return without changing state.
- condition immunity helpers return without changing state.

When the flag is true, the block can own active conditions and event handlers.

Example EB-05-004:

```python
inert_block = make_parent_block(source_uuid)
condition = MarkerCondition(
    source_entity_uuid=source_uuid,
    target_entity_uuid=inert_block.uuid,
)

assert inert_block.add_condition(condition) is None
assert inert_block.active_conditions == {}

active_block.allow_events_conditions = True
applied_event = active_block.add_condition(active_condition)

assert applied_event.phase == EventPhase.COMPLETION
assert active_block.active_conditions["MarkerCondition"] is active_condition
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_004_conditions_are_gated_by_allow_events_conditions`.

## Condition Immunity Storage

`BaseBlock` also stores condition immunity declarations, but these helpers are
gated by `allow_events_conditions` just like conditions and handlers.

Static immunities are stored as `(condition_name, immunity_name)` tuples in
`condition_immunities`. Contextual immunities are stored under
`contextual_condition_immunities[condition_name]` as `(immunity_name, callable)`
pairs. A contextual immunity must provide an `immunity_name`; otherwise the
helper raises `ValueError`. Because callables are excluded from serialized
state, `contextual_immunity_names` exposes the serializable names.

Example EB-05-012:

```python
inert_block.add_condition_immunity("Poisoned", immunity_name="Antitoxin")
assert inert_block.condition_immunities == []

active_block.allow_events_conditions = True
active_block.add_condition_immunity("Prone")
active_block.add_condition_immunity("Poisoned", immunity_name="Antitoxin")
active_block.add_condition_immunity(
    "Frightened",
    immunity_name="Bravery",
    immunity_check=bravery_check,
)

assert active_block.condition_immunities == [
    ("Prone", None),
    ("Poisoned", "Antitoxin"),
]
assert active_block.contextual_immunity_names == {"Frightened": ["Bravery"]}

active_block.remove_condition_immunity("Poisoned")
assert active_block.condition_immunities == [("Prone", None)]
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_012_condition_immunity_storage_is_gated_and_named`.

## Condition Application

`BaseBlock.add_condition()` applies a condition and stores it only if `condition.apply()` succeeds.

Application behavior:

- A condition must have a name.
- If the condition has no target UUID, the block UUID becomes the target.
- Optional context is pushed into the condition and its duration.
- `condition.apply()` declares and progresses condition application events.
- If another condition with the same name already exists, the old condition is removed first.
- Successful conditions are indexed by name, UUID, and source UUID.

`Entity.add_condition()` extends this behavior with saving throw checks and entity-specific details. The lower-level block method does not perform saving throws.

Same-name conditions are replacement-based, not stacked. The new condition is
applied first; if application succeeds, the old active condition with that name
is removed and cleaned before the new condition is indexed.

Example EB-05-009:

```python
block.add_condition(first_condition)
first_modifier_uuid = first_condition.modifers_uuids[block.direct_value.uuid][0]
assert block.direct_value.normalized_score == base_score + 3
assert block.active_conditions["ValueBonusCondition"] is first_condition

block.add_condition(second_condition)
second_modifier_uuid = second_condition.modifers_uuids[block.direct_value.uuid][0]

assert first_condition.applied is False
assert second_condition.applied is True
assert block.active_conditions == {"ValueBonusCondition": second_condition}
assert first_modifier_uuid not in block.direct_value.self_static.value_modifiers
assert second_modifier_uuid in block.direct_value.self_static.value_modifiers
assert block.direct_value.normalized_score == base_score + 9
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_009_same_name_condition_replaces_old_condition`.

When the replacement condition has a different source UUID, the active
condition moves to the new source index. The old source key remains present with
an empty list because removal mutates the list but does not delete the key from
the `defaultdict`.

Example EB-05-014:

```python
block.add_condition(first_condition)
first_modifier_uuid = first_condition.modifers_uuids[block.direct_value.uuid][0]

assert block.active_conditions_by_source[first_source_uuid] == ["ValueBonusCondition"]

block.add_condition(second_condition)
second_modifier_uuid = second_condition.modifers_uuids[block.direct_value.uuid][0]

assert first_condition.applied is False
assert second_condition.applied is True
assert block.active_conditions == {"ValueBonusCondition": second_condition}
assert block.active_conditions_by_source[first_source_uuid] == []
assert block.active_conditions_by_source[second_source_uuid] == ["ValueBonusCondition"]
assert first_modifier_uuid not in block.direct_value.self_static.value_modifiers
assert second_modifier_uuid in block.direct_value.self_static.value_modifiers
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_014_duplicate_name_replacement_updates_source_indexes`.

If a condition `_apply()` returns no effect event, `BaseCondition.apply()`
returns a canceled event and leaves `condition.applied` false.
`BaseBlock.add_condition()` returns that canceled event for observability, but
does not index the inactive condition.

Example EB-05-010:

```python
event = block.add_condition(condition)

assert event is not None
assert event.canceled is True
assert event.phase == EventPhase.CANCEL
assert condition.applied is False
assert block.active_conditions == {}
assert block.active_conditions_by_uuid == {}
assert block.active_conditions_by_source[source_uuid] == []
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_010_no_effect_condition_returns_cancel_without_indexing`.

## Cleanup Boundary

`BaseBlock.remove_condition()` owns condition tree traversal. `BaseCondition.cleanup_own_state()` owns only that condition's local cleanup.

The block removal flow is:

1. Pop the main condition from block dictionaries.
2. Collect and pop same-block sub-conditions from block dictionaries.
3. Recurse into sub-conditions on the same block.
4. Remove linked conditions on other blocks.
5. Ask each condition to clean up its own modifiers and handlers.
6. Notify linked parents through `parent_link` and `child_removal_policy`.

This split is important: a condition should know how to remove its own modifiers, event handlers, spatial handlers, and custom hook state; the block knows where the condition tree lives.

Example EB-05-005:

```python
condition = ValueBonusCondition(
    source_entity_uuid=source_uuid,
    target_entity_uuid=block.uuid,
    target_value_uuid=block.direct_value.uuid,
    bonus=7,
)

base_score = block.direct_value.normalized_score
block.add_condition(condition)
assert block.direct_value.normalized_score == base_score + 7

block.remove_condition("ValueBonusCondition")
assert block.direct_value.normalized_score == base_score
assert condition.applied is False
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_005_condition_cleanup_removes_owned_modifiers`.

## Linked Conditions

`BaseCondition.add_linked_condition(target_block_uuid, condition_uuid)` records a condition on another block. It also writes a reverse `parent_link` on the child condition.

When the parent condition is removed, `BaseBlock._remove_condition_tree()` follows each linked condition and removes it from the target block.

Example EB-05-006:

```python
parent_block.add_condition(parent_condition)
child_block.add_condition(child_condition)
parent_condition.add_linked_condition(child_block.uuid, child_condition.uuid)

assert child_condition.parent_link == (parent_block.uuid, parent_condition.uuid)

parent_block.remove_condition("MarkerCondition")

assert parent_block.active_conditions == {}
assert child_block.active_conditions == {}
assert parent_condition.applied is False
assert child_condition.applied is False
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_006_linked_conditions_are_removed_across_blocks`.

## Event Handler Ownership

When lifecycle is enabled, `BaseBlock.add_event_handler()` stores the handler in local block dictionaries and registers it with `EventQueue`.

Local indexes:

- `event_handlers`: by handler UUID.
- `event_handlers_by_trigger`: by full trigger.
- `event_handlers_by_simple_trigger`: by simple trigger when the trigger has no source or target filter.

Removal must clear both local ownership and queue registration. The book test covers this because stale local handler ownership can otherwise leave toggles and cleanup APIs out of sync with the queue.

Example EB-05-007:

```python
block.add_event_handler(handler)
assert block.get_event_handler_by_name("engine book handler") is handler
assert EventQueue._event_handlers[handler.uuid] is handler

Event(
    source_entity_uuid=source_uuid,
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
).phase_to(EventPhase.EXECUTION)
assert calls == 1

block.remove_event_handler(handler)
assert handler.uuid not in block.event_handlers
assert handler.uuid not in EventQueue._event_handlers
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_007_event_handlers_are_owned_and_removed_by_block`.

## Handler Toggle Policy

`BaseBlock.set_handler_enabled(name, enabled)` and
`BaseBlock.set_handler_enabled_by_uuid(uuid, enabled)` only change handlers with
`player_toggleable=True`. Non-toggleable handlers remain enabled and the helper
returns `False`. Once a toggleable handler is disabled, ordinary event dispatch
skips it because `EventHandler.__call__()` returns `None` while `enabled` is
false.

Example EB-05-011:

```python
block.add_event_handler(locked_handler)
block.add_event_handler(toggleable_handler)

assert block.set_handler_enabled("Locked Handler", False) is False
assert locked_handler.enabled is True
assert block.set_handler_enabled("Toggleable Handler", False) is True
assert toggleable_handler.enabled is False

Event(
    source_entity_uuid=source_uuid,
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
).phase_to(EventPhase.EXECUTION)
assert calls == ["locked"]

assert block.set_handler_enabled_by_uuid(toggleable_handler.uuid, True) is True
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_011_handler_toggles_only_affect_player_toggleable_handlers`.

## Duration Advancement

`BaseBlock.advance_duration(condition_name)` progresses a condition duration and removes the condition if it expires.

This method does not run saving throws. It is suitable for non-entity blocks such as tiles and items. Entities should use their entity-level duration method when saves or entity-specific behavior matter.

Example EB-05-008:

```python
condition = MarkerCondition(
    source_entity_uuid=source_uuid,
    target_entity_uuid=block.uuid,
    duration=Duration(
        duration=1,
        duration_type=DurationType.ROUNDS,
        source_entity_uuid=source_uuid,
        target_entity_uuid=block.uuid,
    ),
)

block.add_condition(condition)
expired = block.advance_duration("MarkerCondition")

assert expired is True
assert condition.applied is False
assert block.active_conditions == {}
```

Parity test: `tests/engine_book/test_chapter_05_blocks_context.py::test_eb_05_008_advance_duration_expires_conditions_without_saves`.

## Current Edges To Preserve

- Direct lookup by name and UUID is shallow. Use `get_values(deep=True)` when recursive value traversal is needed.
- Context propagation intentionally reaches contextual channels, not static channels.
- Target propagation clears copied `from_target` channels when the target is cleared.
- `BaseBlock` condition lifecycle is opt-in through `allow_events_conditions`.
- `BaseBlock.advance_duration()` does not perform saving throws.
- `BaseBlock` owns tree traversal; `BaseCondition` owns its own modifier and handler cleanup.
- Constructor source propagation discovers explicit fields before normalizing
  source, target, and context; EB-05-013 preserves that fixed behavior.
- No-effect condition application returns a canceled event and is not indexed by `BaseBlock.add_condition()`; EB-05-010 preserves that fixed behavior.

## Hygiene Notes

The Chapter 05 hygiene pass reviewed the block container surface in `dnd/core/base_block.py`: direct child/value lookup helpers, target propagation, context propagation, computed lookup maps, local event-handler ownership, condition tree cleanup, duration advancement, and condition-immunity storage.

The pass converted method contracts to Google-style docstrings and removed low-value inline comments from the block/value/context and lifecycle helper paths. EB-05-013 documents the fixed constructor propagation ordering, and EB-05-010 documents fixed no-effect condition indexing behavior.
