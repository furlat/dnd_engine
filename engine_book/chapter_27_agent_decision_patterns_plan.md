# Chapter 27 Plan: Agent Decision Patterns

## Reader Promise

Explain how tactical snapshots become behavior. The reader should understand
behavior-tree control flow, reusable behavior-tree agents, composite
move-and-attack actions, interrupt detection between refreshed states,
utility scoring, and utility-agent execution.

## Concepts Introduced

- `BTContext`, `Selector`, `Sequence`, `Condition`, `BTAction`, and
  `NodeStatus`.
- Prebuilt behavior-tree predicates and actions such as
  `has_affordable_attack`, `attack_nearest`, `has_enemies`,
  `move_and_attack_nearest`, and `dodge_action`.
- Example behavior factories such as `create_melee_fighter_bt`.
- `MoveAndAttack` and `CompositeResult`.
- `detect_interrupts()` and `InterruptType`.
- `UtilityAI`, `DamageScorer`, `FocusFireScorer`, and `UtilityAgent`.

## Concepts Forbidden

- External CLI orchestration.
- Server sessions or stream replication.
- Full state-machine authoring.
- Treating AI behaviors as alternate rules.
- Public references to internal planning, legacy notes, or coverage files.

## Required Visual

- Decision-pattern diagram: tactical state enters behavior tree, composite, or
  utility scorer; chosen action returns through the interface and refreshes
  tactical state.

## Source Files Verified

- `ai/primitives/behavior_tree.py` for behavior-tree nodes, predicates, and
  action functions.
- `ai/primitives/utility.py` for scoring classes and option ranking.
- `ai/composites.py` for composite actions and interrupt detection.
- `ai/agents/base.py` for `BehaviorTreeAgent` and `UtilityAgent` execution
  loops.
- `ai/agents/examples.py` for ready-made behavior factories.
- `tests/manual/test_26_agent_tactical_interface.py` to build on the tactical
  interface without repeating its full explanation.

## Public Example Contract

- One named MDX flow: `agent-decision-patterns`.
- The visible public code creates deterministic behavior scenes and asserts:
  behavior-tree action priority and refresh, factory behavior movement/attack,
  composite move-and-attack result, interrupt detection, utility ranking, and
  utility-agent execution.

## Verification

- Focused manual checks:
  `uv run pytest tests/manual/test_27_agent_decision_patterns.py`
- Exact public snippet execution:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
- Combined manual gate:
  explicit manual files 01-27 plus `tests/book_examples/test_public_mdx_snippets.py`.
