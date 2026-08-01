"""Small canonical encounter fixtures for AI gameplay tests.

This module deliberately owns no alternate arena, scheduler, persistence, or
rating model.  It assembles one authored product recipe, installs the bundled
native controller through its public runtime boundary, and advances a bounded
number of controller decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from dnd.ai.instrumentation import (
    AIInstrumentation,
    BoundedAIInstrumentationSink,
)
from dnd.ai.contracts.decision import PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.policies.basic import BASIC_POLICY_ID, register_basic_policy
from dnd.ai.registry import PolicyRegistry
from dnd.ai.runtime.controller import NativeAIController
from dnd.encounter import EncounterState
from dnd.scenarios.encounter_assembler import (
    AssembledEncounter,
    assemble_encounter_recipe,
)
from dnd.scenarios.encounter_catalog import encounter_recipe


@dataclass(frozen=True, slots=True)
class NativeAITestGame:
    """One canonical encounter plus test-visible native instrumentation."""

    assembled: AssembledEncounter
    controllers: tuple[NativeAIController, ...]
    instrumentation_sinks: tuple[BoundedAIInstrumentationSink, ...]


@dataclass(frozen=True, slots=True)
class NativeAITestRun:
    """Bounded outcome of advancing a test-owned native AI game."""

    decision_count: int
    terminal: bool
    stopped_on_status: str


def build_native_ai_test_game(
    encounter_id: str,
    *,
    maximum_decisions_per_turn: int = 32,
) -> NativeAITestGame:
    """Assemble one authored recipe and assign native AI per roster."""
    registry: PolicyRegistry[SubjectiveWorldState, PolicyIntent] = (
        PolicyRegistry()
    )
    register_basic_policy(registry)
    assembled = assemble_encounter_recipe(
        encounter_recipe(encounter_id),
        start_encounter=False,
    )
    controllers: list[NativeAIController] = []
    sinks: list[BoundedAIInstrumentationSink] = []
    for roster_slot in assembled.recipe.roster_slots:
        entities = assembled.entities_by_roster_slot[
            roster_slot.roster_slot_id
        ]
        controlled = tuple(entity.uuid for entity in entities)
        sink = BoundedAIInstrumentationSink(
            maximum_timings=4096,
            maximum_events=2048,
        )
        controller = NativeAIController.create(
            source_entity_uuid=controlled[0],
            game_id=assembled.recipe.encounter_id,
            assignment_id=f"test:{roster_slot.roster_slot_id}",
            controlled_entity_uuids=controlled,
            registry=registry,
            policy_id=BASIC_POLICY_ID,
            instrumentation=AIInstrumentation(sink=sink),
            maximum_decisions_per_turn=maximum_decisions_per_turn,
        )
        for entity in entities:
            assembled.encounter.set_controller_for(entity.uuid, controller)
        controllers.append(controller)
        sinks.append(sink)
    assembled.encounter.start_encounter()
    return NativeAITestGame(
        assembled=assembled,
        controllers=tuple(controllers),
        instrumentation_sinks=tuple(sinks),
    )


def advance_native_ai_test_game(
    game: NativeAITestGame,
    *,
    maximum_decisions: int,
) -> NativeAITestRun:
    """Advance at most ``maximum_decisions`` canonical controller decisions."""
    if maximum_decisions < 1:
        raise ValueError("maximum_decisions must be positive")
    last_status = "decision_budget_exhausted"
    for decision_count in range(1, maximum_decisions + 1):
        result = game.assembled.encounter.advance_one_controller_action_boundary()
        last_status = result.status
        if game.assembled.encounter.state is EncounterState.ENDED:
            return NativeAITestRun(
                decision_count=decision_count,
                terminal=True,
                stopped_on_status=last_status,
            )
    return NativeAITestRun(
        decision_count=maximum_decisions,
        terminal=False,
        stopped_on_status="decision_budget_exhausted",
    )


__all__ = [
    "NativeAITestGame",
    "NativeAITestRun",
    "advance_native_ai_test_game",
    "build_native_ai_test_game",
]
