"""Real-engine regression for bounded non-damaging AI gameplay validation."""

from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    ResistanceModifier,
    ResistanceStatus,
)
from tests.ai.support import (
    advance_native_ai_test_game,
    build_native_ai_test_game,
)


def test_non_damaging_match_respects_the_test_decision_budget() -> None:
    """A pathological game cannot make the AI validation test itself hang."""
    game = build_native_ai_test_game(
        "encounter.srd_goblinoid_warband",
    )
    initial_hit_points = {
        actor.uuid: actor.get_normal_hp()
        for actor in game.assembled.entities
    }
    for actor in game.assembled.entities:
        for damage_type in DamageType:
            actor.health.damage_reduction.self_static.add_resistance_modifier(
                ResistanceModifier(
                    source_entity_uuid=actor.uuid,
                    target_entity_uuid=actor.uuid,
                    name=f"Test immunity to {damage_type.value}",
                    value=ResistanceStatus.IMMUNITY,
                    damage_type=damage_type,
                )
            )

    result = advance_native_ai_test_game(
        game,
        maximum_decisions=80,
    )

    assert result.decision_count == 80
    assert result.terminal is False
    assert result.stopped_on_status == "decision_budget_exhausted"
    assert {
        actor.uuid: actor.get_normal_hp()
        for actor in game.assembled.entities
    } == initial_hit_points
