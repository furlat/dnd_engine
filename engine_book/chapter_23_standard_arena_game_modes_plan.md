# Chapter 23 Plan: Standard Arena Game Modes

## Reader Promise

Explain the concrete game assembled on top of the engine: the standard arena.
The reader should understand how the product composes environment, hero class
selection, monster-side actors, controller mode, sessions, and client-facing
state into a playable live game.

## Concepts Introduced

- Standard arena environment as a product assembly.
- Hero class selection through fighter, sorcerer, and barbarian presets.
- Human-vs-AI and PvP/Codex controller modes.
- Live human-mode startup route.
- AI session ownership for monster-side entities.
- Joined human session ownership of the hero.
- Client-facing live arena state, visibility, controlled entities, and full
  entity detail payloads.

## Concepts Forbidden

- New engine primitives.
- Alternate rules profiles.
- Private notes or verification language.
- Repeating the full API tutorial already covered by Chapter 18.

## Required Visual

- Arena assembly diagram: environment, hero class, monster side, control mode,
  session join, turn handoff, client state.

## Source Files Verified

- `server/event_server.py` for `setup_arena_combat()`, live start routes, hero
  class selection, controller assignment, and `SimulationState`.
- `server/session.py` for session and game ownership.
- `dnd/maps/arena_layout.py` for standard arena environment ingredients.
- `tests/engine_book/test_manual_21_arena_game_sessions_client_state.py` as
  legacy coverage reference only.
- `tests/manual/test_18_sessions_api_client_contract.py` to avoid duplicating
  the generic API chapter.
- `tests/manual/test_22_playable_scenario_packages.py` to position this
  chapter as the concrete product assembly after scenario packages.

## Public Example Contract

- One named MDX flow: `standard-arena-game-modes`.
- The visible public code uses the actual `setup_arena_combat()` and FastAPI app
  routes to assert standard arena composition, class-selected hero kits,
  PvP/Codex controller mode, human-mode session join, and live state payloads.

## Verification

- Focused manual checks:
  `uv run pytest tests/manual/test_23_standard_arena_game_modes.py`
- Exact public snippet execution:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
- Combined manual gate:
  explicit manual files 01-23 plus `tests/book_examples/test_public_mdx_snippets.py`.
