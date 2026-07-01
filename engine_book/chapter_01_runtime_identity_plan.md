# Chapter 01 Plan: Runtime Identity And Registries

## Status

Published to the local Astro webbook for human browser review.

Public page:

- `src/content/manual/01-runtime-identity-and-registries.mdx`

Private draft prepared:

- `engine_book/drafts/01-runtime-identity-and-registries.mdx`

Diagram assets prepared:

- `runtime-identity-and-registries.svg`
- `runtime-identity-and-registries.excalidraw`

Test preparation completed:

- Added `tests/manual/test_01_runtime_identity_and_registries.py`.
- Added `tests/manual/__init__.py`.
- Ran `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py`.
- Result: 4 passed.

Working public file, after review:

- `src/content/manual/01-runtime-identity-and-registries.mdx`

Prepared test file:

- `tests/manual/test_01_runtime_identity_and_registries.py`

The tests should be ordinary pytest tests with real tutorial code. They must not
wrap old examples, parameterize over hidden test functions, or expose
`engine_book`/parity language.

## Reader Promise

By the end of the chapter, the reader should understand:

- Why runtime identity exists in a videogame engine.
- What a UUID does for live objects.
- Why NeuroDragon has several registry families instead of one global table.
- How a small object, a value, a block, and an entity enter their lookup
  surfaces.
- How an entity's grid position is tracked in entity indexes and the map.
- Why the next chapter can safely talk about actor anatomy.

The chapter should feel like the first code chapter of a manual. It should not
feel like a test dump.

## Evidence Studied From Source

Current-source evidence read for this plan:

- `dnd/core/base_object.py`
- `dnd/core/values.py`
- `dnd/core/base_block.py`
- `dnd/entity.py`
- `dnd/core/gridmap.py`
- `dnd/utils/test_utils.py`
- `tests/engine_book/test_chapter_01_registries.py`
- `tests/engine_book/test_manual_03_objects_identity_registries.py`
- `pyproject.toml`

Evidence conclusions below come from source inspection, not old prose.

## Source Facts To Teach

### BaseObject

`BaseObject` is the root identity model for UUID-addressable objects. It is a
Pydantic model with:

- `uuid`
- `source_entity_uuid`
- optional target identity
- optional display names
- optional context
- `use_register`
- class-level `_registry`

`model_post_init()` registers an instance in `self.__class__._registry` when
`use_register` is true.

`BaseObject.get()` returns `None` for a missing UUID and raises `ValueError` if
the UUID resolves to an object that is not an instance of the lookup class.

`add_to_register()` is for objects created with `use_register=False`; it raises
if the object is already configured to use a registry.

### BaseValue

`BaseValue` inherits from `BaseObject`, but defines its own `_registry`.

That means values are looked up through the value registry, not through
`BaseObject.get()`.

Important subclass lookup behavior:

- `BaseValue.get()` returns any registered `BaseValue`.
- `StaticValue.get()` raises when the UUID is missing or the registered value is
  not a `StaticValue`.
- `ContextualValue.get()` returns `None` for a missing UUID and raises for the
  wrong value type.
- `ModifiableValue.get()` returns `None` for a missing UUID and raises for the
  wrong value type.

The public chapter should mention the subclass differences only after teaching
the main registry separation. They are useful as a "sharp edge" box, not as the
first lesson.

### BaseBlock

`BaseBlock` is not a `BaseObject`. It has its own UUID, source/target/context
fields, child block/value discovery, and class-level `_registry`.

`BaseBlock.model_post_init()` registers the block in `BaseBlock._registry`.

Blocks discover direct child blocks and `ModifiableValue` instances, then
propagate source identity into those children. This prepares the reader for the
next chapter about actor anatomy, but this chapter should keep the explanation
to identity and lookup.

### Entity

`Entity` inherits from `BaseBlock`.

Creating an entity through `Entity.create(source_entity_uuid=..., config=...)`
builds configured child blocks and values, then constructs an `Entity` whose
`uuid` and `source_entity_uuid` match.

During `model_post_init()` the entity enters:

- `BaseBlock._registry`
- `Entity._entity_registry`
- `Entity._entity_by_position`
- `GridMap` entity position tracking

`Entity.update_entity_position(entity, new_position)` updates:

- the entity position index,
- `entity.position`,
- `entity.senses.position`,
- and the global `GridMap` position tracking.

`Entity.get_all_entities_at_position(position)` returns the live list stored in
the position index. Because the registry is a `defaultdict(list)`, asking for a
previously unused position creates an empty list entry.

`Entity.register_entity(entity)` only updates `_entity_registry`; it does not
populate position indexes, block registry, or map position tracking. The public
tutorial should use `Entity.create(...)`, not manual registration.

### GridMap

`GridMap.register_entity()` and `GridMap.move_entity()` track entity UUIDs by
position and fire spatial enter/leave events when events are enabled. The first
identity chapter should mention only position tracking. Event firing belongs to
the later event/world chapters.

## Concepts Allowed In This Chapter

Allowed:

- UUID
- live object
- registry
- lookup
- source identity
- target identity as a field, not as a combat mechanic
- context as a field, not as contextual modifier behavior
- object/value/block/entity registry family
- position index
- map position tracking
- `Entity.create(...)`

Allowed as future landmarks only:

- actor anatomy
- values
- events
- conditions
- actions
- senses

The chapter may say "later chapters use these IDs to connect events, effects,
actions, and clients." It must not explain those systems yet.

## Concepts Forbidden In This Chapter

Do not teach:

- `EventQueue`
- event phases
- handlers
- modifiers
- dice
- conditions
- action templates
- combat flow
- spellcasting
- equipment rules
- pathfinding
- senses internals
- APIs

Do not use hidden helpers from old tests.

Forbidden public names:

- `RegistryProbe`
- `EB-01-*`
- parity
- `tests/engine_book`
- note links

## Public Page Shape

### 1. Why Identity Exists

Start from the game:

The engine receives an action, condition, item interaction, or map update at one
moment and must recover the same live actor or object later. UUIDs give the
runtime stable names for live objects.

### 2. The Four Lookup Families

Teach the table first:

| Family | Runtime role | Lookup |
| --- | --- | --- |
| Object | Root UUID-addressable object. | `BaseObject.get(uuid)` or subclass `get(uuid)` |
| Value | Numbers and roll states used by rules. | `BaseValue.get(uuid)` and value subclass lookups |
| Block | Containers for values and child blocks. | `BaseBlock.get(uuid)` |
| Entity | Playable/AI actor and positioned creature. | `Entity.get(uuid)` and position lookup |

Explain why this is good: each family has clearer ownership and type checks.

### 3. Where The Imports Come From

This is the first public import-map table. It must appear before the first code
snippet.

| Symbol | Import | Why it appears |
| --- | --- | --- |
| `uuid4` | `from uuid import uuid4` | Creates stable IDs for the tutorial scene. |
| `BaseObject` | `from dnd.core.base_object import BaseObject` | Shows the smallest registry-aware object. |
| `BaseValue` | `from dnd.core.values import BaseValue` | Shows the value registry family. |
| `BaseBlock` | `from dnd.core.base_block import BaseBlock` | Shows the block registry family. |
| `Entity`, `EntityConfig` | `from dnd.entity import Entity, EntityConfig` | Creates the first actor and position lookup example. |
| `get_map` | `from dnd.core.gridmap import get_map` | Verifies map-level entity position tracking. |

Do not include reset helpers in this public import map unless the page is
explicitly showing a test file. The tutorial snippets should be readable as
conceptual examples.

### 4. Tutorial Object

Define the small teaching class visibly:

```python
from uuid import uuid4

from dnd.core.base_object import BaseObject


class TutorialMarker(BaseObject):
    """Small concrete object used to demonstrate registry behavior."""


source_id = uuid4()
marker = TutorialMarker(source_entity_uuid=source_id, name="door marker")

assert TutorialMarker.get(marker.uuid) is marker
```

Explain:

- `BaseObject` is abstract in role, but not in Python mechanics.
- A tiny subclass makes the registry behavior visible.
- The `source_entity_uuid` says who produced or owns the object in the relevant
  subsystem.

### 5. Opt Out And Re-enter The Registry

```python
draft_marker = TutorialMarker(
    source_entity_uuid=source_id,
    name="draft marker",
    use_register=False,
)

assert TutorialMarker.get(draft_marker.uuid) is None

draft_marker.add_to_register()
assert TutorialMarker.get(draft_marker.uuid) is draft_marker

draft_marker.remove_from_register()
assert TutorialMarker.get(draft_marker.uuid) is None
```

Explain when transient identity is useful without dragging in events yet.

### 6. Registry Families Are Separate

```python
from dnd.core.base_block import BaseBlock
from dnd.core.values import BaseValue


value = BaseValue(source_entity_uuid=source_id, name="tutorial value")
block = BaseBlock(source_entity_uuid=source_id, name="tutorial block")

assert BaseValue.get(value.uuid) is value
assert BaseObject.get(value.uuid) is None

assert BaseBlock.get(block.uuid) is block
assert BaseValue.get(block.uuid) is None
```

Explain:

- Values inherit object fields but use the value registry.
- Blocks are a separate container family.
- Looking up through the wrong family returns `None` instead of pretending the
  object is something else.

### 7. Entity Registers As Actor, Block, And Positioned Object

```python
from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig


hero_id = uuid4()
hero = Entity.create(
    source_entity_uuid=hero_id,
    name="Hero",
    config=EntityConfig(position=(2, 3)),
)

assert Entity.get(hero_id) is hero
assert BaseBlock.get(hero_id) is hero
assert hero in Entity.get_all_entities_at_position((2, 3))
assert get_map().get_entity_position(hero_id) == (2, 3)
```

Then move it:

```python
Entity.update_entity_position(hero, (4, 5))

assert hero.position == (4, 5)
assert hero.senses.position == (4, 5)
assert hero not in Entity.get_all_entities_at_position((2, 3))
assert hero in Entity.get_all_entities_at_position((4, 5))
assert get_map().get_entity_position(hero_id) == (4, 5)
```

Keep the senses line as an observed fact: the entity's spatial block follows the
entity position. Do not teach senses yet.

### 8. Sharp Edges Box

Briefly list:

- `StaticValue.get()` raises on missing UUIDs; several other lookups return
  `None`.
- `Entity.get_all_entities_at_position()` returns a live registry list.
- `Entity.register_entity()` is not the construction path for gameplay actors.
- Registry cleanup in tests must clear object/value/block/entity/map state.

This section should be short and practical. It must not sound like a bug list.

### 9. What Comes Next

Next chapter: entity anatomy.

Identity makes an actor recoverable. Entity anatomy explains what that actor
owns: abilities, skills, saves, health, equipment, inventory, senses, actions,
resources, spellcasting, faction, and active conditions.

## Diagram Requirement

Create a fresh diagram, not a reused old one unless reviewed:

- `runtime-identity-and-registries.svg`
- `runtime-identity-and-registries.excalidraw`

Visual shape:

- Left: one `uuid`.
- Four columns/families: object, value, block, entity.
- Entity branch also points to position index and grid map position tracking.
- Caption: "A UUID names a live object, but the family you search determines
  what kind of object you expect to recover."

## Test Requirement

Write a new professional test file before publishing:

- `tests/manual/test_01_runtime_identity_and_registries.py`

The file should include:

- Visible imports only.
- Visible tutorial classes.
- `reset_identity_state()` defined in the file, with a docstring explaining the
  global state it clears.
- Tests named around behavior, not EB numbers.
- No wrappers around examples.
- No imports from `examples`.
- No imports from `tests.engine_book`.
- No `iter_example_tests`.

Required test functions:

- `test_tutorial_marker_registers_and_can_opt_out()`
- `test_registry_families_are_separate()`
- `test_entity_creation_populates_actor_block_position_and_map_lookup()`
- `test_value_subclass_lookup_contracts_are_explicit()`

Run focused only:

```bash
uv run pytest tests/manual/test_01_runtime_identity_and_registries.py
```

Do not run the full test suite.

## Public Acceptance Gate

Before publishing the page:

- Opening chapter has been human-reviewed.
- Chapter 01 includes the import map before code.
- Every code symbol is imported or defined before use.
- No public note/test/parity links.
- No hidden helpers.
- No handler/event/action terminology before it is introduced.
- Diagram renders at desktop and narrow widths.
- Focused pytest file passes.
- Astro build passes.
- Route returns `200`.
- Public hygiene scan finds no `engine_book`, `tests/`, `parity`, `notes/`,
  `TODO`, `placeholder`, or old helper names.
