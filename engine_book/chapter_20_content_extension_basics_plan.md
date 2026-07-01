# Chapter 20 Plan: Content Extension Basics

## Reader Promise

This chapter teaches the first extension pattern a developer needs after
learning the runtime: build a small content pack from ordinary engine pieces.
The pack defines a condition, an action that applies it, a usable item that
provides the action, an actor factory that carries the content, and a tiny scene
that proves discovery and execution.

## Concepts Introduced For The First Time

- Local content-pack classes.
- Custom `BaseCondition` subclasses.
- Custom `BaseAction` subclasses.
- Item-provided action templates through `UsableItem`.
- Actor factory composition for custom content.
- Scene factory composition for map plus actors plus floor objects.

## Concepts Kept Out Of This Chapter

- Spell-specific extension.
- Class feature progression tables.
- Full encounter balance.
- Renderer asset registration.
- Persistent scenario documents.

Those deserve follow-on extension chapters instead of being hidden inside a
single oversized example.

## Runtime Sources Studied

- `dnd/core/base_conditions.py`
- `dnd/core/base_actions.py`
- `dnd/blocks/base_item.py`
- `dnd/entity.py`
- `dnd/actions_functional.py`
- `dnd/actions.py`
- `dnd/monsters/skeleton_abilities.py`
- `dnd/monsters/bestiary.py`

## Game Meaning

A content extension should feel like adding game content, not changing the
engine. A condition owns its ongoing state. An action validates intent and
applies the condition. A usable item exposes the action through the same
discovery surface as standard game actions. An actor factory composes the
content into a playable creature, and a scene factory places that creature and
object into a small map.

## Visual

Add `/diagrams/content-extension-basics.svg` and matching Excalidraw source.
The diagram should show:

- game concept;
- condition;
- action template;
- usable item;
- actor factory;
- scene factory;
- discovery/execution path.

## Public Example Contract

Use one named exact-execution group:

- `content-extension-basics`

Example blocks:

- EB-20-001: define the content pack.
- EB-20-002: apply and remove the condition directly.
- EB-20-003: register the action as an actor ability and execute it by index.
- EB-20-004: package the same action inside an inventory item.
- EB-20-005: expose the item as a nearby floor object.
- EB-20-006: compose a custom actor and scene factory.

Public setup routines must be visible and tutorial-facing:

- `reset_content_extension_state`
- `find_action_info`
- `find_item_action`
- `inventory_item_named`
- `create_field_kit`
- `create_field_medic`
- `create_field_training_scene`

## Verification

Focused test:

```bash
uv run pytest tests/manual/test_20_content_extension_basics.py tests/book_examples/test_public_mdx_snippets.py
```

The exact public snippet runner should increase by one example group and the
chapter should stay free of private source references and meta verification
language.
