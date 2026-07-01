# Chapter 06 Plan: Reactions To Events

## Status

Published with real tutorial tests. The public Astro page is available for
browser review.

Prepared test file:

- `tests/manual/test_06_reactions_to_events.py`

Focused test run:

- `uv run pytest tests/manual/test_06_reactions_to_events.py`
- Result: 6 passed.

Manual arc focused test run:

- `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py tests/manual/test_02_entity_anatomy.py tests/manual/test_03_values_and_modifiers.py tests/manual/test_04_dice_rolls.py tests/manual/test_05_event_lifecycle.py tests/manual/test_06_reactions_to_events.py`
- Result: 28 passed.

Public file:

- `src/content/manual/06-reactions-to-events.mdx`

Public route:

- `http://127.0.0.1:4327/manual/06-reactions-to-events/`

Astro build:

- `npm run build`
- Result: 8 pages built.

## Reader Promise

By the end of the chapter, the reader should understand:

- Why reactions exist after the base event lifecycle.
- How `Trigger` selects event type, phase, and optional source/target filters.
- How `EventHandler` processors can ignore, modify, or cancel matching events.
- Why completion is a log/observation boundary, not a handler-dispatch phase.
- How dice result events create a controlled window for roll replacement.
- How `SpatialHandler` uses grid positions instead of trigger matching.
- Why voluntary step movement and forced movement are separate reaction
  surfaces.

## Evidence Studied From Source

Current-source evidence read for this plan:

- `dnd/core/events.py`
- `dnd/core/dice.py`
- `dnd/actions.py`
- `dnd/reactions.py`
- `dnd/classes/fighter.py`
- `dnd/classes/feats.py`
- `dnd/spells/abjuration.py`
- `dnd/spells/enchantment.py`
- `tests/manual/test_06_reactions_to_events.py`

Evidence conclusions below come from source inspection and focused tests, not
old prose.

## Source Facts To Teach

### Trigger

`Trigger` is a hashable event predicate. It matches:

- `event_type`,
- `event_phase`,
- optional `event_source_entity_uuid`,
- optional `event_target_entity_uuid`.

Source and target filters are optional. When absent, the trigger matches any
source or any target.

### EventHandler

`EventHandler` stores:

- `name`,
- `source_entity_uuid`,
- `trigger_conditions`,
- `event_processor`,
- `enabled`,
- `player_toggleable`,
- optional `owner_block`.

The queue discovers handlers from trigger indexes before completion. A handler
processor receives `(event, source_entity_uuid)` and may return:

- `None`: no change,
- a modified event copy,
- a canceled event.

When a result is canceled, queue dispatch stores it and stops later handlers in
that registration pass.

Completion events are stored but do not dispatch handlers.

### Registration

This chapter can use `EventQueue.add_event_handler()` because it teaches the
low-level event system directly. Later entity-owned features should prefer
owner registration so cleanup has a block-local owner.

### Dice Result Events

`AttackD20RollResultEvent`, `SavingThrowD20RollResultEvent`, and
`SkillCheckD20RollResultEvent` inherit d20 replacement behavior from
`D20RollResultEvent`.

`DamageRollResultEvent` replaces entries in `final_rolls` while preserving
`original_rolls`.

The current real processor pattern is:

- inspect the effective roll,
- create a replacement `DiceRoll`,
- call `event.replace_roll(...)`,
- return `event.model_copy(update={"modified": True})`.

### SpatialHandler

`SpatialHandler` is a position-indexed handler:

- stored in `_spatial_handlers`,
- indexed by `(event_type, event_phase)` and grid position,
- discovered for spatial events with a position,
- moved with `EventQueue.update_spatial_handler_positions(...)`,
- removed with `remove_spatial_handler(...)`.

It is the right surface for zone and terrain effects.

### Voluntary And Forced Movement

`StepMovementEvent` has `event_type=STEP_MOVEMENT` and is emitted during
cell-by-cell movement.

`ForcedMovementEvent` has `event_type=FORCED_MOVEMENT` and represents pushes,
pulls, and similar displacement.

The opportunity attack handler in `dnd/reactions.py` listens to
`STEP_MOVEMENT` at `EFFECT`, not `FORCED_MOVEMENT`.

## Concepts Allowed In This Chapter

Allowed:

- trigger
- event handler
- event processor
- enabled handler
- canceling handler
- result event
- d20 result replacement
- damage result replacement at conceptual level
- spatial handler
- spatial position index
- voluntary step movement
- forced movement

Allowed only as examples, not deep systems:

- opportunity-style reaction
- terrain/zone entry effect

## Concepts Forbidden In This Chapter

Do not teach:

- condition lifecycle
- condition cleanup trees
- concentration
- spell catalogs
- class feature factories
- complete attack action flow
- full movement/pathfinding internals
- encounter/session APIs

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

### 1. Why Reactions Exist

Start from the game:

The engine has already recorded intent and phases. A rules engine also needs
systems that can listen during resolution: wards, reactions, rerolls, terrain,
and zone effects.

### 2. Three Reaction Surfaces

Teach:

- trigger-indexed event handlers,
- dice result events,
- spatial handlers.

### 3. Where The Imports Come From

Import map must appear before code.

### 4. Triggered Handler

Show a handler that rings an alarm only for a specific source/target effect.

### 5. Disabled And Completion Boundary

Show `enabled=False` and explain completion does not dispatch handlers.

### 6. Cancellation

Show a ward canceling an effect and stopping later handlers.

### 7. D20 Result Processor

Show deterministic d20 roll, result event, replacement roll, audit entry.

### 8. Spatial Handler

Show position-indexed thorny ground and moving the handler to another cell.

### 9. Voluntary Step Versus Forced Movement

Show `STEP_MOVEMENT` handler observes a voluntary step but not a
`FORCED_MOVEMENT` event.

## Diagram Requirement

Create:

- `event-reaction-surfaces.svg`
- `event-reaction-surfaces.excalidraw`

Caption:

> Reactions run before completion: trigger-indexed handlers listen to event
> type and phase, result processors replace roll records, and spatial handlers
> listen through position indexes.

## Test Requirement

The test file must remain a real pytest file:

- `tests/manual/test_06_reactions_to_events.py`

It must include:

- visible imports,
- no wrappers around examples,
- no imports from `examples`,
- no imports from `tests.engine_book`,
- no `iter_example_tests`,
- behavior names instead of EB numbers.

Required focused tests:

- `test_triggered_handler_modifies_matching_effect_event()`
- `test_disabled_handlers_and_completion_handlers_do_not_fire()`
- `test_canceling_handler_stops_later_handlers()`
- `test_d20_result_processor_replaces_low_attack_roll()`
- `test_spatial_handler_uses_position_index_and_can_move()`
- `test_step_movement_and_forced_movement_are_different_reaction_surfaces()`

Run focused only:

```bash
uv run pytest tests/manual/test_06_reactions_to_events.py
```

Do not run the full test suite.

## Public Acceptance Gate

Completed before keeping the page public:

- Chapter 06 includes the import map before code.
- Every code symbol is imported or defined before use.
- No public note/test/parity links.
- No hidden helpers in public snippets.
- No condition lifecycle, concentration, class factory, encounter API, or full
  attack-flow explanation before introduced.
- The voluntary movement versus forced movement distinction is explicit.
- Diagram renders at desktop and narrow widths.
- Focused pytest file passes.
- Manual arc focused tests pass.
- Astro build passes.
- Route returns `200`.
- Public hygiene scan finds no `engine_book`, `tests/`, `parity`, `notes/`,
  `TODO`, `placeholder`, or old helper names.
