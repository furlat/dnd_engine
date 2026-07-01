# Chapter 07 Plan: Conditions And Cleanup

## Status

Published with real tutorial tests. The public Astro page is available for
browser review.

Prepared test file:

- `tests/manual/test_07_conditions_and_cleanup.py`

Focused test run:

- `uv run pytest tests/manual/test_07_conditions_and_cleanup.py`
- Result: 5 passed.

Manual arc focused test run:

- `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py tests/manual/test_02_entity_anatomy.py tests/manual/test_03_values_and_modifiers.py tests/manual/test_04_dice_rolls.py tests/manual/test_05_event_lifecycle.py tests/manual/test_06_reactions_to_events.py tests/manual/test_07_conditions_and_cleanup.py`
- Result: 33 passed.

Public file:

- `src/content/manual/07-conditions-and-cleanup.mdx`

Public route:

- `http://127.0.0.1:4327/manual/07-conditions-and-cleanup/`

Astro build:

- `npm run build`
- Result: 9 pages built.

## Reader Promise

By the end of the chapter, the reader should understand:

- How D&D ongoing states become NeuroDragon condition objects.
- What a condition owns at runtime: modifiers, event handlers, spatial handlers,
  subconditions, linked conditions, and duration.
- How `_apply(...)` returns owned artifacts for cleanup.
- How a block indexes active conditions by name, UUID, and source.
- How removal traverses same-block subconditions and cross-block links.
- How reverse linked cleanup uses `child_removal_policy`.
- How round duration expiry routes through the same cleanup path.

## Evidence Studied From Source

Current-source evidence read for this plan:

- `dnd/core/base_conditions.py`
- `dnd/core/base_block.py`
- `dnd/conditions.py`
- `dnd/entity.py`
- `dnd/tile_conditions.py`
- `tests/manual/test_07_conditions_and_cleanup.py`

Evidence conclusions below come from source inspection and focused tests, not
old prose.

## Source Facts To Teach

### BaseCondition

`BaseCondition` owns:

- `duration`,
- `applied`,
- `modifers_uuids`,
- `event_handlers_uuids`,
- `spatial_handler_uuids`,
- `parent_condition`,
- `sub_conditions`,
- `linked_conditions`,
- `parent_link`,
- `child_removal_policy`,
- tags and condition category metadata.

`declare_event(...)` creates a `ConditionApplicationEvent`.

`_apply(...)` is overridden by subclasses and returns:

- modifier UUID pairs,
- event handler UUIDs,
- same-block subcondition UUIDs,
- spatial handler UUIDs,
- effect event.

`apply(...)` records those returned artifacts, marks the condition applied, and
completes the application event.

`cleanup_own_state(...)` declares removal, runs `_remove(...)` or `_expire(...)`,
removes owned modifiers, event handlers, and spatial handlers, clears parent
subcondition membership, marks the condition unapplied, and completes removal.

### BaseBlock Condition Indexes

`BaseBlock.add_condition(...)` applies a condition when
`allow_events_conditions=True`, then indexes it by:

- condition name,
- condition UUID,
- source UUID.

If a condition with the same name already exists, the old one is removed first.

### Removal Tree

`BaseBlock.remove_condition(...)` pops the root condition and same-block
descendants from indexes first, then calls `_remove_condition_tree(...)`.

`_remove_condition_tree(...)`:

- recurses into same-block `sub_conditions`,
- removes cross-block `linked_conditions`,
- calls `condition.cleanup_own_state(...)`,
- uses a child's `parent_link` to notify the cross-block parent.

`child_removal_policy` controls reverse cleanup:

- `none`: no reverse removal,
- `any`: remove the parent when any linked child is removed,
- `last`: remove the parent when no linked applied children remain.

### Duration

`DurationType.ROUNDS` decrements with `advance_duration(...)`. When it reaches
zero, the block removes the condition with `expire=True`, so modifier and
handler cleanup remains the same path as explicit removal.

### Entity Add-Condition Surface

`Entity.add_condition(...)` adds entity-specific behavior:

- source/target names for logs,
- condition immunity checks,
- optional application saving throws.

This chapter teaches lower-level block lifecycle first. Entity combat
conditions appear later when actor combat is in scope.

## Concepts Allowed In This Chapter

Allowed:

- condition
- condition application event
- condition removal event
- owned modifier
- owned event handler
- owned spatial handler at a conceptual level
- same-block subcondition
- cross-block linked condition
- reverse parent link
- duration
- condition indexes
- `BaseBlock.add_condition(...)`
- `BaseBlock.remove_condition(...)`

Allowed as D&D examples without full combat flow:

- Poisoned
- Grappled
- Paralyzed
- Incapacitated

## Concepts Forbidden In This Chapter

Do not teach:

- full spell concentration
- spell catalogs
- class feature factories
- full attack action flow
- encounter/session APIs
- inventory/equipment lifecycles
- tile zone authoring in detail

Do not use hidden helpers from old tests.

Forbidden public names:

- `EB-*`
- parity
- `tests/engine_book`
- private notes
- `make_bonus`
- `make_damage_roll`
- `make_d20_roll`
- `fixed_randint`
- `completed_damage_events`
- `RegistryProbe`

## Public Page Shape

### 1. Conditions As Runtime Packages

Start from the game:

D&D names persistent states. NeuroDragon turns each state into a runtime package
that owns the state it added and can remove it cleanly.

### 2. Lifecycle

Teach:

- application declaration,
- `_apply(...)`,
- artifact ownership,
- active condition indexes,
- removal declaration,
- cleanup tree.

### 3. Where The Imports Come From

Import map must appear before code.

### 4. Tutorial Actor Block

Define `TutorialActor` and `create_tutorial_actor(...)` visibly.

### 5. Modifier-Owning Condition

Define and apply `GuardedCondition`.

### 6. Handler-Owning Condition

Define `ListeningCondition`, show that the handler stops after removal.

### 7. Same-Block Subcondition

Define `FocusBlockedCondition` and `StunnedTutorialCondition`.

### 8. Cross-Block Linked Cleanup

Define `LinkedAuraCondition` and `LinkedMarkCondition`, show forward and reverse
cleanup.

### 9. Duration Expiry

Show a two-round guarded condition expiring through `advance_duration(...)`.

## Diagram Requirement

Create:

- `condition-cleanup-tree.svg`
- `condition-cleanup-tree.excalidraw`

Caption:

> A condition owns the runtime artifacts it adds; removal walks subconditions
> and linked conditions before cleaning the condition's own modifiers and
> handlers.

## Test Requirement

The test file must remain a real pytest file:

- `tests/manual/test_07_conditions_and_cleanup.py`

It must include:

- visible imports,
- visible tutorial block and condition classes,
- no wrappers around examples,
- no imports from `examples`,
- no imports from `tests.engine_book`,
- no `iter_example_tests`,
- behavior names instead of EB numbers.

Required focused tests:

- `test_condition_application_indexes_owned_modifier_and_removal_cleans_it()`
- `test_condition_owned_event_handler_is_removed_with_condition()`
- `test_parent_condition_removes_same_block_subcondition_tree()`
- `test_linked_condition_cleanup_runs_forward_and_reverse()`
- `test_round_duration_expiry_removes_condition_and_owned_modifier()`

Run focused only:

```bash
uv run pytest tests/manual/test_07_conditions_and_cleanup.py
```

Do not run the full test suite.

## Public Acceptance Gate

Completed before keeping the page public:

- Chapter 07 includes the import map before code.
- Every code symbol is imported or defined before use.
- No public note/test/parity links.
- No hidden helpers in public snippets.
- No spell concentration, class factory, encounter API, inventory/equipment
  lifecycle, or full attack-flow explanation before introduced.
- The page makes entity-specific condition application a later layer, while
  still explaining why entity behavior exists.
- Diagram renders at desktop and narrow widths.
- Focused pytest file passes.
- Manual arc focused tests pass.
- Astro build passes.
- Route returns `200`.
- Public hygiene scan finds no `engine_book`, `tests/`, `parity`, `notes/`,
  `TODO`, `placeholder`, or old helper names.
