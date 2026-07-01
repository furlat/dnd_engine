# 07. Condition Application And Cleanup

## Purpose

Conditions are reusable state packages. They can add modifiers, install event handlers, install spatial handlers, create same-block sub-conditions, link effects across other blocks, and remove all of that state through one cleanup tree.

This chapter documents current behavior in `dnd/core/base_conditions.py`, `dnd/core/base_block.py`, and `dnd/entity.py`. The examples are executable in `tests/engine_book/test_chapter_07_condition_lifecycle.py`.

## Source Files Studied

- `dnd/core/base_conditions.py`
- `dnd/core/base_block.py`
- `dnd/core/events.py`
- `dnd/entity.py`
- `dnd/conditions.py`
- `dnd/tile_conditions.py`
- `examples/test_condition_removal_system.py`
- `examples/test_child_parent_notification.py`
- `examples/test_concentration.py`
- `examples/test_tile_condition_duration.py`
- `tests/engine_book/test_chapter_07_condition_lifecycle.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: conditions are named effects that change what a creature can do, how rolls are made, or how other creatures interact with that creature. This maps to `interactive_ruleset/Gamemastering/Conditions.md`.
- `SRD-aligned`: many applications and removals can be gated by saving throws, matching the save patterns in `interactive_ruleset/Gameplay/Combat.md`.
- `Engine extension`: condition application and removal are represented as event lifecycles.
- `Engine extension`: conditions own modifier UUIDs, event handler UUIDs, spatial handler UUIDs, sub-condition UUIDs, and linked cross-block condition UUIDs.
- `Engine adaptation`: same-name conditions do not stack. The new condition applies first, then the old same-name condition is removed and replaced.
- `Current edge`: if a condition `_apply()` returns a canceled event, `Entity.add_condition()` does not index it, but `BaseCondition.apply()` has already marked the condition object as `applied=True`.

## Application Layers

There are two application paths:

- `Entity.add_condition()` is the creature path.
- `BaseBlock.add_condition()` is the generic block path for tiles, items, and other block-like objects.

`Entity.add_condition()` adds entity-specific gates before a condition reaches `_apply()`:

1. Set missing target UUID.
2. Apply optional context to the condition and its duration.
3. Populate source and target names for combat logs.
4. Create a `ConditionApplicationEvent` at `DECLARATION`.
5. Check static and contextual condition immunities.
6. If configured, run `application_saving_throw`.
7. Call `BaseCondition.apply()`.
8. If the returned event is not canceled, store the condition by name, UUID, and source UUID.

`BaseBlock.add_condition()` skips immunity and saving throw gates. It applies the condition and stores it if application returns an event.

Example EB-07-001:

```python
condition = EngineBookMarkerCondition(
    source_entity_uuid=source.uuid,
    target_entity_uuid=target.uuid,
)

completed = target.add_condition(condition)

assert completed.phase == EventPhase.COMPLETION
assert completed.event_type == EventType.CONDITION_APPLICATION
assert condition.applied is True
assert target.active_conditions["EngineBookMarker"] is condition
assert target.active_conditions_by_uuid[condition.uuid] is condition
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_001_entity_condition_application_events_and_indexes`.

Generic `BaseBlock.add_condition()` follows the same success gate as entity
condition application: a canceled result is returned for observability, but it
does not place the condition in active-condition indexes.

Example EB-07-010:

```python
tile = get_map().get_tile(4, 4)
condition = EngineBookNoEffectCondition(
    source_entity_uuid=source.uuid,
    target_entity_uuid=tile.uuid,
)

canceled = tile.add_condition(condition)

assert canceled.phase == EventPhase.CANCEL
assert canceled.canceled is True
assert condition.applied is False
assert "EngineBookNoEffect" not in tile.active_conditions
assert condition.uuid not in tile.active_conditions_by_uuid
assert tile.active_conditions_by_source[source.uuid] == []
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_010_baseblock_add_condition_skips_canceled_no_effect`.

## Application Events

`BaseCondition.declare_event()` creates a `ConditionApplicationEvent` at `DECLARATION`.

Subclasses control the middle phases. Many conditions phase through:

```text
DECLARATION -> EXECUTION -> EFFECT -> COMPLETION
```

but this is not universal. Some conditions jump from `DECLARATION` to `EFFECT`. `COMPLETION` is centralized in `BaseCondition.apply()` after `_apply()` returns an effect event.

`_apply()` must return this five-part tuple:

```python
(
    modifier_pairs,
    event_handler_uuids,
    sub_condition_uuids,
    spatial_handler_uuids,
    effect_event,
)
```

If `effect_event` is missing, `BaseCondition.apply()` cancels the declaration and does not mark or store the condition.

Example EB-07-002:

```python
canceled = target.add_condition(EngineBookNoEffectCondition(...))

assert canceled.phase == EventPhase.CANCEL
assert canceled.canceled is True
assert condition.applied is False
assert "EngineBookNoEffect" not in target.active_conditions
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_002_apply_without_effect_event_cancels_and_does_not_index`.

## Canceled Returned Events

A returned event can itself be canceled. Current behavior is subtle:

1. `_apply()` returns a canceled event.
2. `BaseCondition.apply()` stores returned UUID metadata, sets `condition.applied = True`, and phases the canceled event to `COMPLETION`.
3. `Entity.add_condition()` sees the returned event is canceled and does not store the condition in `active_conditions`.

That leaves the object marked applied but unreachable through the entity condition dictionaries.

Example EB-07-003:

```python
completed = target.add_condition(EngineBookCanceledEffectCondition(...))

assert completed.phase == EventPhase.COMPLETION
assert completed.canceled is True
assert condition.applied is True
assert "EngineBookCanceledEffect" not in target.active_conditions
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_003_canceled_apply_event_is_not_indexed_but_marks_object_applied`.

## Immunity And Application Saves

Entity immunity is checked before `_apply()`.

Static immunities are stored as condition-name tuples. Contextual immunities are callables keyed by condition name. If either says immune, `Entity.add_condition()` pushes a failed combat log entry and returns a canceled declaration event.

Application saving throws also happen before `_apply()`. If `check_save_throw=True`, and `condition.application_saving_throw` exists, the target rolls the requested save. A successful save cancels application.

Example EB-07-004:

```python
immune_target.add_condition_immunity("EngineBookMarker")
immune_result = immune_target.add_condition(immune_condition)

assert immune_result.canceled is True
assert immune_condition.applied is False
assert "EngineBookMarker" not in immune_target.active_conditions

with fixed_randint(20):
    save_result = saving_target.add_condition(saved_condition)

assert save_result.canceled is True
assert saved_condition.applied is False
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_004_entity_immunity_and_application_save_cancel_before_apply`.

## Same-Name Replacement

Conditions are keyed by `condition.name`. They do not stack under the same name.

Replacement order is:

1. Apply the new condition.
2. If an old active condition has the same name, remove the old one.
3. Store the new condition.

This means the old condition is still active while the new condition's `_apply()` runs. After replacement, only the new condition is indexed, and old owned modifiers and handlers should be gone.

Example EB-07-005:

```python
target.add_condition(old_condition)
assert target.proficiency_bonus.normalized_score == original_base + 5

target.add_condition(new_condition)

assert old_condition.applied is False
assert new_condition.applied is True
assert target.active_conditions["EngineBookModifier"] is new_condition
assert target.proficiency_bonus.normalized_score == original_base + 2
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_005_same_name_replacement_cleans_old_condition_state`.

## Cleanup Tree

Condition removal is driven by `BaseBlock.remove_condition()`, not by `BaseCondition` alone.

The block first removes the condition from active dictionaries. It also pre-removes recursive same-block subconditions from the dictionaries. Then `_remove_condition_tree()` performs cleanup in this order:

1. Recurse into same-block `sub_conditions`.
2. Remove cross-block `linked_conditions`.
3. Clean the condition's own state.
4. Notify a linked parent through `parent_link`, if policy requires it.

Own-state cleanup is `BaseCondition.cleanup_own_state()`:

1. Declare a `ConditionRemovalEvent`.
2. Run `_expire()` if removal is expiration-driven.
3. Run subclass `_remove()`.
4. Remove owned modifiers from their `ModifiableValue`s.
5. Remove owned trigger-based event handlers.
6. Remove owned spatial handlers.
7. Unlink from same-block parent.
8. Set `applied=False`.
9. Complete the removal event.

## Same-Block Sub-Conditions

Sub-conditions are children on the same block. They use:

- child field: `parent_condition`
- parent field: `sub_conditions`

When the parent is removed, the child and all descendants are removed first.

Example EB-07-006:

```python
target.add_condition(parent)
sub_condition = BaseCondition.get(parent.sub_conditions[0])

assert target.active_conditions["EngineBookParent"] is parent
assert target.active_conditions["EngineBookSub"] is sub_condition

target.remove_condition("EngineBookParent")

assert parent.applied is False
assert sub_condition.applied is False
assert "EngineBookSub" not in target.active_conditions
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_006_parent_removal_cascades_to_same_block_subconditions`.

## Linked Conditions

Linked conditions connect a parent condition to a child condition on another `BaseBlock`.

`BaseCondition.add_linked_condition(target_block_uuid, condition_uuid)` does two things:

- appends `(target_block_uuid, condition_uuid)` to the parent's `linked_conditions`;
- writes `(parent_block_uuid, parent_condition_uuid)` to the child's `parent_link`.

Forward cleanup is parent-to-child: remove the parent, and all linked children are removed.

Reverse notification is child-to-parent. After child cleanup, `_remove_condition_tree()` checks the parent condition's `child_removal_policy`:

- `"none"`: leave the parent alone.
- `"any"`: remove the parent when any linked child is removed.
- `"last"`: remove the parent when no linked children remain applied.

Example EB-07-007:

```python
forward_parent.add_linked_condition(child_block.uuid, forward_child.uuid)
parent_block.remove_condition("EngineBookLinkedParent")

assert forward_parent.applied is False
assert forward_child.applied is False

reverse_parent.child_removal_policy = "last"
reverse_parent.add_linked_condition(child_block.uuid, reverse_child.uuid)
child_block.remove_condition("EngineBookReverseChild")

assert reverse_parent.applied is False
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse`.

The three reverse-notification policies have distinct edge behavior:

- `"any"` removes the parent when the first linked child is removed; parent forward cleanup then removes remaining siblings.
- `"last"` keeps the parent while at least one linked child is still applied.
- `"none"` leaves the parent applied and leaves the stale `(block_uuid, condition_uuid)` pair in `linked_conditions`.

Example EB-07-011:

```python
any_child_block_a.remove_condition("EngineBookAnyChildA")

assert any_parent.applied is False
assert any_child_a.applied is False
assert any_child_b.applied is False
assert "EngineBookAnyParent" not in any_parent_block.active_conditions
assert "EngineBookAnyChildB" not in any_child_block_b.active_conditions

last_child_block_a.remove_condition("EngineBookLastChildA")

assert last_parent.applied is True
assert last_child_a.applied is False
assert last_child_b.applied is True
assert last_parent_block.active_conditions["EngineBookLastParent"] is last_parent

last_child_block_b.remove_condition("EngineBookLastChildB")

assert last_parent.applied is False
assert "EngineBookLastParent" not in last_parent_block.active_conditions

none_child_block.remove_condition("EngineBookNoneChild")

assert none_parent.applied is True
assert none_child.applied is False
assert none_parent_block.active_conditions["EngineBookNoneParent"] is none_parent
assert none_parent.linked_conditions == [(none_child_block.uuid, none_child.uuid)]
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_011_child_removal_policies_any_last_and_none`.

## Owned Handlers

Conditions can own trigger-based `EventHandler`s and position-indexed `SpatialHandler`s.

The ownership contract is UUID-based:

- `_apply()` registers the handler.
- `_apply()` returns the handler UUID.
- `BaseCondition.apply()` stores it on the condition.
- `cleanup_own_state()` removes it during condition cleanup.

Spatial handlers are separate from normal event handlers. They live in `EventQueue._spatial_handlers` and position indices, not in the normal trigger-handler registries.

Example EB-07-008:

```python
target.add_condition(handler_condition)
Event(..., event_type=EventType.BASE_ACTION).phase_to(EventPhase.EFFECT)
assert handler_condition.calls == ["before cleanup"]

target.remove_condition("EngineBookHandler")
assert handler_uuid not in EventQueue._event_handlers

target.add_condition(spatial_condition)
target.move((4, 4))
assert spatial_condition.calls == [(4, 4)]

target.remove_condition("EngineBookSpatial")
assert EventQueue.get_spatial_handlers_at((4, 4)) == []
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_008_owned_event_and_spatial_handlers_are_removed_on_cleanup`.

## Duration

`Duration` supports:

- `ROUNDS`: integer countdown, expired when `duration <= 0`.
- `PERMANENT`: no automatic expiry.
- `UNTIL_LONG_REST`: expires when the duration is marked long-rested.
- `ON_CONDITION`: calls a contextual duration predicate.

`Entity.advance_duration_condition()` is the entity path. It first checks `removal_saving_throw` unless skipped. A successful removal save removes the condition immediately. Otherwise the duration progresses, and expired conditions are removed with `expire=True`.

`BaseBlock.advance_duration()` is the generic block path. It does not perform removal saves.

Example EB-07-009:

```python
condition = EngineBookMarkerCondition(
    source_entity_uuid=source.uuid,
    target_entity_uuid=target.uuid,
    duration=Duration(duration=1, duration_type=DurationType.ROUNDS),
)

target.add_condition(condition)
removed = target.advance_duration_condition("EngineBookMarker", skip_save_throw=True)

assert removed is True
assert condition.applied is False
assert "EngineBookMarker" not in target.active_conditions
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_009_entity_duration_advancement_expires_and_removes_condition`.

If an entity condition has `removal_saving_throw`, the save runs before duration progress. A successful save removes the condition and leaves the duration count unchanged.

Example EB-07-012:

```python
condition = EngineBookMarkerCondition(
    source_entity_uuid=source.uuid,
    target_entity_uuid=target.uuid,
    duration=Duration(duration=2, duration_type=DurationType.ROUNDS),
    removal_saving_throw=SavingThrowEvent(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        ability_name="dexterity",
        dc=5,
    ),
)

target.add_condition(condition)

with fixed_randint(20):
    removed = target.advance_duration_condition("EngineBookMarker")

assert removed is True
assert condition.applied is False
assert "EngineBookMarker" not in target.active_conditions
assert condition.duration.duration == 2
```

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_012_removal_save_succeeds_before_duration_decrements`.

## Item Conditions

`BaseItem` inherits the generic `BaseBlock` condition lifecycle but opts into condition and event support with `allow_events_conditions=True`. Item conditions use the same application indexes, same-name replacement, no-effect cancellation gate, and generic duration advancement as other blocks. Items add one important lifecycle hook: `BaseItem.destroy()` removes active item conditions before unregistering the item from `BaseBlock._registry`.

Example EB-07-013:

```python
item = BaseItem(source_entity_uuid=source.uuid, name="Conditioned Wand")
first = EngineBookMarkerCondition(
    source_entity_uuid=source.uuid,
    target_entity_uuid=item.uuid,
)
item.add_condition(first)

assert item.active_conditions["EngineBookMarker"] is first
assert item.active_conditions_by_source[source.uuid] == ["EngineBookMarker"]

replacement = EngineBookMarkerCondition(
    source_entity_uuid=source.uuid,
    target_entity_uuid=item.uuid,
)
item.add_condition(replacement)

assert first.applied is False
assert replacement.applied is True
assert item.active_conditions["EngineBookMarker"] is replacement

timed = EngineBookMarkerCondition(
    name="EngineBookItemTimed",
    source_entity_uuid=source.uuid,
    target_entity_uuid=item.uuid,
    duration=Duration(duration=1, duration_type=DurationType.ROUNDS),
)
item.add_condition(timed)
assert item.advance_duration("EngineBookItemTimed") is True

destroy_condition = EngineBookMarkerCondition(
    name="EngineBookDestroyCleanup",
    source_entity_uuid=source.uuid,
    target_entity_uuid=item.uuid,
)
item.add_condition(destroy_condition)
item.destroy()

assert destroy_condition.applied is False
assert item.active_conditions == {}
assert item.uuid not in BaseBlock._registry
```

The executable test also proves no-effect item conditions return a canceled event and do not enter item indexes.

Parity test: `tests/engine_book/test_chapter_07_condition_lifecycle.py::test_eb_07_013_item_conditions_index_expire_and_destroy_cleanly`.

## Deeper Coverage Still Needed

- EB-07-003 is documented and tested as current behavior. EB-07-010 now
  preserves the fixed generic-block no-effect indexing rule.
- Initial Chapter 07 edge backlog is covered; add new condition lifecycle rows only after further code study.
- Add direct SRD condition examples in Chapter 08, one condition at a time.

## Documentation Hygiene Notes

- This chapter records runtime behavior from source and executable examples, not from existing prose comments.
- Chapter 07 hygiene reviewed `dnd/core/base_conditions.py`: condition categories and tags, duration state, condition application/removal events, BaseCondition ownership, apply, cleanup, link, and duration-progress contracts, plus spell-protection metadata.
- Preserved behavior edges: EB-07-003 keeps the canceled-returned-event object marked applied but unindexed by `Entity.add_condition()`. EB-07-010 documents fixed `BaseBlock.add_condition()` behavior for canceled no-effect results.
- Broader SRD condition subclass cleanup belongs to Chapter 08, where each concrete condition can be checked against its executable behavior and SRD relationship.
