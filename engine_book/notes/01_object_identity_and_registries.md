# 01. Object Identity And Registries

## Purpose

Object identity is the engine's lowest shared contract: engine objects carry UUIDs, and many subsystems use class-level registries to recover live objects from those UUIDs during event processing, condition cleanup, action execution, senses updates, and item interactions.

This chapter is deliberately narrow. It documents what the current implementation does, not what older comments or docs say it does.

## Source Files Studied

- `dnd/core/base_object.py`
- `dnd/core/values.py`
- `dnd/core/base_block.py`
- `dnd/entity.py`
- `examples/test_entity_blocking.py`
- `examples/test_inventory_use_actions.py`
- `examples/test_torch_items.py`
- `tests/engine_book/test_chapter_01_registries.py`

## Rules Relationship

Registry behavior is engine infrastructure. It has no direct SRD rule counterpart.

Status: `Engine extension`.

The SRD describes characters, objects, conditions, movement, and combat outcomes. The registry layer is the engine's implementation mechanism for relating those game objects to one another by UUID.

## Core Identity Fields

`BaseObject` defines the basic identity fields used by modifiers, actions, events, conditions, and other object-like models:

- `uuid`: the object's own unique identifier.
- `source_entity_uuid`: the entity that created, owns, or caused the object, depending on subsystem.
- `target_entity_uuid`: the entity targeted by the object when applicable.
- `source_entity_name` and `target_entity_name`: optional display names carried alongside UUIDs.
- `context`: optional runtime context.
- `use_register`: whether a `BaseObject` instance should enter its registry on creation.

These fields are not enough to infer gameplay meaning by themselves. Their meaning depends on the subsystem using the object. For example, a condition's source is the applier, while a value's source is usually the entity whose block owns the value.

## Registry Families

The implementation has several related but separate registry families.

| Family | Class | Registry | Registered by default | Lookup |
|---|---|---|---|---|
| Generic objects | `BaseObject` and subclasses without their own `_registry` | `BaseObject._registry` or subclass-shadowed registry | Yes, if `use_register=True` | `BaseObject.get()` or subclass `get()` |
| Values | `BaseValue` and value subclasses | `BaseValue._registry` | Yes | `BaseValue.get()`, `StaticValue.get()`, `ContextualValue.get()`, `ModifiableValue.get()` |
| Blocks | `BaseBlock` and block subclasses | `BaseBlock._registry` | Yes | `BaseBlock.get()` |
| Entities | `Entity` | `Entity._entity_registry` and `Entity._entity_by_position` | Yes | `Entity.get()`, `Entity.get_all_entities_at_position()` |

The important finding is that there is not one universal object registry. A `BaseValue` is discoverable through the value registry, not through `BaseObject.get()`. A `BaseBlock` is discoverable through the block registry, not through the generic object registry.

## BaseObject Lifecycle

`BaseObject.model_post_init()` inserts the instance into `self.__class__._registry` when `use_register` is true. This means subclasses that do not shadow `_registry` share the inherited registry, while subclasses that define their own `_registry` use that one.

Example EB-01-001:

```python
from uuid import uuid4

from dnd.core.base_object import BaseObject


class RegistryProbe(BaseObject):
    pass


source_uuid = uuid4()
registered = RegistryProbe(source_entity_uuid=source_uuid)
assert RegistryProbe.get(registered.uuid) is registered

transient = RegistryProbe(source_entity_uuid=source_uuid, use_register=False)
assert RegistryProbe.get(transient.uuid) is None

transient.add_to_register()
assert RegistryProbe.get(transient.uuid) is transient

transient.remove_from_register()
assert RegistryProbe.get(transient.uuid) is None
```

Parity test: `tests/engine_book/test_chapter_01_registries.py::test_eb_01_001_base_object_registration_lifecycle`.

## Typed Lookup

`BaseObject.get()` looks in the class registry and then checks that the recovered object is an instance of the class used for lookup. If another object type is found at the UUID, lookup raises `ValueError` instead of returning the wrong type.

Example EB-01-002:

```python
other = OtherRegistryProbe(source_entity_uuid=source_uuid)

try:
    RegistryProbe.get(other.uuid)
except ValueError:
    rejected = True
else:
    rejected = False

assert rejected is True
```

Parity test: `tests/engine_book/test_chapter_01_registries.py::test_eb_01_002_base_object_lookup_is_typed`.

## Value And Block Separation

`BaseValue` inherits from `BaseObject`, but it defines its own `_registry`. Because `BaseObject.model_post_init()` writes to `self.__class__._registry`, value instances enter the value registry rather than the generic `BaseObject._registry`.

`BaseBlock` does not inherit from `BaseObject`. It is a separate Pydantic model with its own `_registry` and `model_post_init()`.

Example EB-01-003:

```python
source_uuid = uuid4()

value = BaseValue(source_entity_uuid=source_uuid)
block = BaseBlock(source_entity_uuid=source_uuid)

assert BaseValue.get(value.uuid) is value
assert BaseObject.get(value.uuid) is None

assert BaseBlock.get(block.uuid) is block
assert BaseValue.get(block.uuid) is None
```

Parity test: `tests/engine_book/test_chapter_01_registries.py::test_eb_01_003_value_and_block_registries_are_separate`.

## Value Subclass Lookup

All value subclasses share `BaseValue._registry`, but their typed lookup methods do not all handle misses the same way.

Example EB-01-005:

```python
static_value = StaticValue(source_entity_uuid=source_uuid)
contextual_value = ContextualValue(source_entity_uuid=source_uuid)
modifiable_value = ModifiableValue.create(source_entity_uuid=source_uuid)

assert BaseValue.get(static_value.uuid) is static_value
assert BaseValue.get(contextual_value.uuid) is contextual_value
assert BaseValue.get(modifiable_value.uuid) is modifiable_value

assert StaticValue.get(static_value.uuid) is static_value
assert ContextualValue.get(contextual_value.uuid) is contextual_value
assert ModifiableValue.get(modifiable_value.uuid) is modifiable_value
```

The typed methods reject values of the wrong subclass. `ContextualValue.get()` and `ModifiableValue.get()` return `None` for missing UUIDs, while `StaticValue.get()` raises `ValueError` for both missing UUIDs and wrong value types.

Parity test: `tests/engine_book/test_chapter_01_registries.py::test_eb_01_005_value_subclass_lookup_contracts`.

## Entity Registration

`Entity` inherits from `BaseBlock`. On creation, `Entity.model_post_init()` first registers the entity as a block through `BaseBlock.model_post_init()`, then registers it in entity-specific indexes:

- `Entity._entity_registry[entity.uuid] = entity`
- `Entity._entity_by_position[entity.position].append(entity)`
- the global `GridMap` also receives the entity UUID and position

This is why `BaseBlock.get(entity.uuid)` returns the entity itself, while `Entity.get(entity.uuid)` returns the same object through the entity registry.

Example EB-01-004:

```python
entity_uuid = uuid4()
config = EntityConfig(position=(2, 3))

entity = Entity.create(
    source_entity_uuid=entity_uuid,
    name="Registry Hero",
    config=config,
)

assert Entity.get(entity_uuid) is entity
assert BaseBlock.get(entity_uuid) is entity
assert entity in Entity.get_all_entities_at_position((2, 3))

Entity.update_entity_position(entity, (4, 5))

assert entity.position == (4, 5)
assert entity.senses.position == (4, 5)
assert entity not in Entity.get_all_entities_at_position((2, 3))
assert entity in Entity.get_all_entities_at_position((4, 5))
```

Parity test: `tests/engine_book/test_chapter_01_registries.py::test_eb_01_004_entity_registers_as_block_and_entity`.

## Current Edge Cases And Constraints

- `BaseObject.remove_objects(permanent_delete=True)` removes the registry entry and deletes the local variable, but other references may still keep the object alive in Python.
- `BaseObject.add_to_register()` refuses to run when `use_register` is already true, even if the object is missing from the registry.
- `BaseObject.register()` and the similar registry methods overwrite existing UUID entries without collision checks.
- `StaticValue.get()` differs from several other lookup APIs: a missing UUID raises `ValueError` because the implementation does not special-case `None`.
- Combining or deriving values can create registered calculation artifacts, so the value registry is not only a table of long-lived character stats.
- `BaseBlock.unregister()` removes from `BaseBlock._registry`, but it does not update `Entity._entity_registry`, `Entity._entity_by_position`, or `GridMap`.
- `Entity.register_entity()` writes only to `Entity._entity_registry`; it does not update position indexes or the block registry.
- `Entity.get_all_entities_at_position()` returns the live list stored in the position registry. Because the registry is a `defaultdict`, querying an unused position creates an empty list entry.
- `Entity.update_entity_position()` assumes the entity is present in the old position list.
- Removing a modifier from a value removes the UUID from that value's modifier dictionary, but does not unregister the modifier object from `BaseObject._registry`.
- Removing a condition from a block removes active-condition indexes and the condition's owned effects, but does not by itself erase every possible reference to the condition object from generic registries.
- Test helpers such as `reset_combat_state()` clear entity, event, and map state, but not every low-level registry. Registry-specific tests must clear `BaseObject._registry`, `BaseValue._registry`, and `BaseBlock._registry` when isolation matters.

These are not necessarily bugs. They are current contracts to account for when writing tests, cleanup paths, or higher-level APIs.

## Coverage Status

Existing baseline coverage touches this subsystem indirectly:

- `examples/test_entity_blocking.py` verifies that `BaseBlock.get(entity.uuid)` returns an `Entity` and dispatches entity methods.
- `examples/test_inventory_use_actions.py` verifies item destruction unregisters consumed items from `BaseBlock`.
- `examples/test_torch_items.py` verifies extinguishing a torch does not unregister it from `BaseBlock`.

The direct parity coverage for this chapter is:

- `tests/engine_book/test_chapter_01_registries.py`

Status: `covered` for EB-01-001 through EB-01-005.

## Hygiene Notes

The Chapter 01 hygiene pass reviewed the object/block/entity identity surface in `dnd/core/base_object.py`, `dnd/core/base_block.py`, and the registry-focused top section of `dnd/entity.py`.

The pass replaced generated attribute-list prose with concise Google-style responsibility docstrings, moved identity/index meaning into Pydantic field descriptions, and removed low-value comments from the registry/source-discovery path. The broader `Entity` comments and docstrings outside the registration surface belong to their later chapters: conditions, turns, actions, senses, inventory, equipment, and spellcasting.
