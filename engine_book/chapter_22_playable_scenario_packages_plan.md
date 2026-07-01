# Chapter 22 Plan: Playable Scenario Packages

## Reader Promise

Show how authored content becomes a running videogame scene. The reader should
understand how a scenario factory composes map state, actors, controllers, an
encounter, turn handoff, indexed player actions, combat-log capture, and
faction-survival ending.

## Concepts Introduced

- Scenario package as a product boundary around engine objects.
- Controller assignment for human and automated actors.
- Encounter startup from a scene factory.
- `advance_until_player()` as external-input handoff.
- `Encounter.execute_action()` as template-name plus target-index execution.
- Encounter combat-log capture from completed event chains.
- Encounter ending by living faction state.

## Concepts Forbidden

- Server API payload details already covered by Chapter 18.
- Map-editor editing APIs already covered by Chapter 19.
- Additional rule profiles or alternate encounter-ending policies.
- Public references to private notes, wrappers, or verification machinery.

## Required Visual

- Scenario package flow: map state, actors, controllers, encounter, turn
  handoff, action execution, outcome feed.

## Source Files Verified

- `dnd/encounter.py` for encounter lifecycle, action execution, combat logs,
  `advance_until_player()`, and faction ending.
- `dnd/controller.py` for human and pass controller behavior.
- `dnd/monsters/bestiary.py` for ready-to-play goblin and skeleton actors.
- `tests/manual/test_17_encounters_turns_controllers.py` for established
  encounter patterns.
- `tests/manual/test_19_map_editor_scenario_authoring.py` for the separation
  between authoring maps and running encounters.

## Public Example Contract

- One named MDX flow: `playable-scenario-package`.
- The visible public code defines recording human/pass controllers,
  `GatehouseScenario`, reset, scenario factory, deterministic melee attack
  setup, player handoff, action execution, combat-log capture, and faction
  ending.

## Verification

- Focused manual checks:
  `uv run pytest tests/manual/test_22_playable_scenario_packages.py`
- Exact public snippet execution:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
- Combined manual gate:
  explicit manual files 01-22 plus `tests/book_examples/test_public_mdx_snippets.py`.
