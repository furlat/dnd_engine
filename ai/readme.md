# AI Package

The `ai` package is the local Python decision layer for videogame-controlled
turns. It sits above the D&D engine: it can import `dnd`, inspect available
actions through the public engine APIs, and execute chosen actions, but the core
engine must not import `ai`.

This package is separate from the archived subprocess CLI in `to_archive/cli`.
That older surface is kept for reference, while `ai` is the active in-process
gameplay AI surface.

## Dependency Direction

Runtime dependencies flow in one direction:

```text
dnd/controller.py
  defines TurnRunner Protocol and AIAgentController

ai/*
  imports dnd public APIs where needed
  implements TurnRunner-compatible agents
```

`dnd/controller.py` owns only the small `TurnRunner` protocol. That keeps the
engine able to run any compatible turn runner without depending on this package.

## Layers

The package has five layers.

```text
ai.models
  Engine-agnostic Pydantic DTOs and expected-value helpers.

ai.interface
  GameInterface Protocol and LocalGameInterface adapter.

ai.composites
  Multi-step tactical routines such as move-and-attack and retreat.

ai.primitives
  Behavior tree, finite-state machine, and utility-scoring primitives.

ai.agents
  Turn runners that loop primitives until the turn is complete.
```

## Models

`ai.models` contains the data an AI needs to reason about a turn without holding
live engine objects:

- `TacticalState`: subjective snapshot for one acting entity.
- `TacticalEntity`: HP, AC, position, faction, and conditions.
- `ActionOption`: an available action plus cost, range, targets, and combat data.
- `TargetOption`: target identity plus target-side math such as AC or save bonus.
- `AttackData` and `SpellData`: roll, DC, damage, and concentration metadata.
- `ActionResult`: engine execution result normalized for AI control flow.

The expected-value helpers live here too: `hit_chance`, `crit_chance`,
`attack_ev`, `spell_save_ev`, and `action_ev`.

## Interface

`GameInterface` is the minimal Protocol used by primitives and agents:

```python
class GameInterface(Protocol):
    def get_tactical_state(self, entity_uuid: UUID) -> TacticalState: ...
    def execute(self, entity_uuid: UUID, template_name: str, target_index: int = 0) -> ActionResult: ...
```

`LocalGameInterface` is the concrete adapter for the current engine. It imports
engine modules at module scope so dependency direction stays visible. It builds
`TacticalState` from `Entity.get_available_actions(target_filter="all")`,
visible allies/enemies, action economy resources, spell slots, and per-target
combat math. It executes actions through `execute_by_index`.

## Composites

`ai.composites` contains action sequences that may span multiple engine actions.
They snapshot state before and after each step and detect interrupts such as:

- damage taken during movement
- target death
- newly visible enemies
- new conditions on the acting entity

Each composite defines whether an interrupt aborts or allows the routine to
continue.

## Primitives

`ai.primitives.behavior_tree` provides selectors, sequences, decorators,
conditions, and actions. `BTAction` refreshes tactical state after execution so
later nodes reason from current action economy and positions.

`ai.primitives.state_machine` provides named states, transitions, and priorities
for mode-based behavior.

`ai.primitives.utility` enumerates affordable action/target pairs and ranks them
with weighted scorers such as damage, focus-fire pressure, threat avoidance, and
self-preservation.

## Agents

`ai.agents.base` contains `BaseAgent`, `BehaviorTreeAgent`, and `UtilityAgent`.
An agent owns a `GameInterface` and an `entity_uuid`, then runs until it can no
longer make useful progress or the safety cap is reached.

`ai.agents.examples` contains small factory functions for reusable starter
agents.

## Scenario Fixtures

Reusable demonstration scenes live in `dnd/scenarios`, not in this package. The
AI-related scenario modules create controlled maps and entities that exercise
this package from the outside:

- `agent_tactical_training.py`: tactical-state and local-interface examples.
- `agent_decision_training.py`: behavior-tree, state-machine, utility, and
  composite examples.

Those modules are tutorial and testing surfaces. They are not new D&D rules.
