# Chapter 26 Plan: Agent Tactical Interface

## Reader Promise

Explain how local agents see and act in the game without reading `Entity`
objects directly. The reader should understand `TacticalState`,
`TacticalEntity`, `ActionOption`, `TargetOption`, combat math snapshots,
`LocalGameInterface`, expected-value helpers, and the minimal `BaseAgent`
turn-runner pattern.

## Concepts Introduced

- Agent-facing tactical snapshots.
- Engine action rows translated into `ActionOption` and `TargetOption`.
- Combat math snapshots through `AttackData`, `SpellData`, and `DiceSpec`.
- Query helpers on `TacticalState` for nearest enemies, targetable attacks,
  and movement choices.
- `LocalGameInterface.get_tactical_state()` as the engine-to-agent bridge.
- `LocalGameInterface.execute()` as the agent-to-engine command bridge.
- Expected-value helpers for hit chance, critical chance, and action scoring.
- `BaseAgent.run_turn()` as a minimal turn runner over a tactical state.

## Concepts Forbidden

- Full behavior-tree authoring.
- Full utility scorer configuration.
- Composite action interrupt policy details.
- CLI orchestration and external-process agent launching.
- Public references to internal planning, legacy notes, or coverage files.

## Required Visual

- Tactical interface diagram: engine state and available actions translated
  into tactical state, agent selects action/target, interface executes through
  the engine, state refreshes.

## Source Files Verified

- `ai/models.py` for tactical DTOs, query helpers, and expected-value helpers.
- `ai/interface.py` for `GameInterface`, `LocalGameInterface`,
  `get_tactical_state()`, and `execute()`.
- `ai/agents/base.py` for `BaseAgent`, `BehaviorTreeAgent`, and
  `UtilityAgent` turn-runner structure.
- `dnd/actions_functional.py` for `execute_by_index()` and action discovery
  routing used by the interface.
- `examples/ai/test_ai_framework.py` as legacy behavior reference only.

## Public Example Contract

- One named MDX flow: `agent-tactical-interface`.
- The visible public code creates one deterministic agent scene and asserts:
  tactical state construction, action and target translation, query helpers,
  expected-value math, interface execution, state refresh after execution, and
  a minimal agent subclass that performs one selected action.

## Verification

- Focused manual checks:
  `uv run pytest tests/manual/test_26_agent_tactical_interface.py`
- Exact public snippet execution:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
- Combined manual gate:
  explicit manual files 01-26 plus `tests/book_examples/test_public_mdx_snippets.py`.
