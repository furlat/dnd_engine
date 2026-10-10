# Chapter 17 Plan: Encounters, Turns, And Controllers

## Reader Promise

This chapter teaches the runtime layer that makes actors take turns in a
playable scene. By the end, the reader should understand how an `Encounter`
owns combatants, initiative order, round and turn state, controller boundaries,
combat-log capture, and faction-based ending.

## Concepts Introduced For The First Time

- `Encounter`
- `CombatantState`
- `EncounterState`
- `TurnState`
- `TurnContext`
- `Controller`
- `HumanController`
- `PassController`
- `advance_until_player()`
- Encounter combat-log listeners
- Encounter death checks

## Concepts Kept Out Of This Chapter

- HTTP sessions and server endpoints.
- Event-stream payload details.
- Map-editor scenario APIs.
- Codex orchestration internals.
- Full AI strategy design.

Those belong after the encounter loop is explained.

## Runtime Sources Studied

- `dnd/encounter.py`
- `dnd/controller.py`
- `dnd/entity.py`
- `dnd/core/events.py`
- `dnd/core/combat_log.py`
- `dnd/conditions.py`
- `dnd/monsters/bestiary.py`
- `dnd/actions_functional.py`

Existing examples and old engine-book tests were used only as discovery
material. The new public snippets and `tests/manual` checks are the chapter's
verification contract.

## Rules Relationship

- D&D combat proceeds by initiative, rounds, turns, actions, movement, bonus
  actions, reactions, and death/defeat. The chapter presents those as the game
  meaning.
- NeuroDragon implements a videogame table manager: the engine owns active
  encounter state, advances turns deterministically, pauses for external-input
  controllers, captures combat logs automatically, and ends the encounter when
  faction survival leaves only one side alive.
- Faction-based ending is the engine's game-loop policy. It replaces GM fiat for
  runtime testing and videogame play.

## Visual

Add `/diagrams/encounters-turns-controllers.svg` and matching Excalidraw source.
The diagram should show:

- entities become combatants;
- combatants enter initiative order;
- the current turn builds `TurnContext`;
- the controller chooses an action or waits for external input;
- actions create events and combat logs;
- death checks can end the encounter.

## Public Example Contract

Use one named exact-execution group:

- `encounter-turn-flow`

Example blocks:

- EB-17-001: start and end an encounter.
- EB-17-002: start/end turns and advance rounds.
- EB-17-003: run automated turns until a human-controlled actor needs input.
- EB-17-004: execute an action through the encounter and capture combat logs.
- EB-17-005: mark death and end the encounter by faction survival.

The public imports and helper classes must be visible in the first example
block. Helpers must be small and tutorial-facing:

- `RecordingController`
- `reset_encounter_tutorial_state`
- `create_encounter_pair`
- `start_ordered_encounter`
- `make_melee_attack_auto_hit`
- `clear_melee_attack_modifier`

## Verification

Focused test:

```bash
uv run pytest tests/manual/test_17_encounters_turns_controllers.py tests/book_examples/test_public_mdx_snippets.py
```

Expected focused manual test count before public harness enrollment:

- `tests/manual/test_17_encounters_turns_controllers.py`: 5 passed.

After public page and harness enrollment, the exact public snippet runner should
increase by one example group.
