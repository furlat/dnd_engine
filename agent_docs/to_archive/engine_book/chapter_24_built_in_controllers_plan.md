# Chapter 24 Plan: Built-In Controllers And Automated Turns

## Reader Promise

Explain the controller catalogue as the videogame input contract. The reader
should understand which controllers pause for outside decisions, which
controllers end turns automatically, and which controller marks an
out-of-process AI session turn.

## Concepts Introduced

- `controller_type` as the public turn-routing identifier.
- `HumanController` and `CodexController` as external-input boundaries.
- `PassController` as a deterministic no-action automated turn.
- `ExternalAIController` as the out-of-process AI session boundary.
- `TurnContext` as the narrow controller view of action economy and visible
  opponents.
- `advance_until_player()` as the loop that runs automated controllers and
  stops for human or Codex ownership.

## Concepts Forbidden

- A second ruleset or controller flag system.
- Repeating the full encounter lifecycle already covered by Chapter 17.
- Repeating the live arena startup payloads already covered by Chapter 23.
- Public references to internal planning, verification, or source notes.

## Required Visual

- Controller catalogue diagram: encounter current turn, controller type,
  external-input controllers, pass controller, external AI session boundary,
  and the return to the turn loop.

## Source Files Verified

- `dnd/controller.py` for `Controller`, `TurnContext`, `HumanController`,
  `CodexController`, `PassController`, and `ExternalAIController`.
- `dnd/encounter.py` for `run_turn()`, `advance_until_player()`, and controller
  context construction.
- `server/event_server.py` for live arena controller assignment and current
  turn payload semantics.
- `ai/subjective/` and `ai/policy/` for the event-first agent runtime and shared
  policy host above the controller boundary.
- `tests/engine_book/test_chapter_18_encounters_apis.py` as legacy coverage
  reference only.
- `tests/manual/test_17_encounters_turns_controllers.py` and
  `tests/manual/test_23_standard_arena_game_modes.py` to avoid duplicating
  earlier public chapters.

## Public Example Contract

- One named MDX flow: `built-in-controller-flow`.
- The visible public code asserts the exact controller behaviour:
  external-input controllers stop advancement, pass controllers finish
  immediately, and external AI turns wait for session-authorized commands.

## Verification

- Focused manual checks:
  `uv run pytest tests/manual/test_24_built_in_controllers.py`
- Exact public snippet execution:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
- Combined manual gate:
  explicit manual files 01-24 plus `tests/book_examples/test_public_mdx_snippets.py`.
