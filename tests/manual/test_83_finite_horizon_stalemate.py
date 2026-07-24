"""Real-engine regression for finite-horizon draw adjudication."""

from ai.evaluation.config_ladder.match_runner import _termination_adjudication
from ai.evaluation.config_ladder.worker_contracts import DEFAULT_RATING_MAX_COMMANDS
from ai.external_selfplay import (
    run_external_selfplay_with_arena_factory,
    STALEMATE_COMMAND_WINDOW,
)
from dnd.core.modifiers import DamageType, ResistanceModifier, ResistanceStatus
from dnd.scenarios.evaluation.assembler import assemble_composed_arena


def test_non_damaging_match_reaches_typed_stalemate_draw() -> None:
    def arena_factory():
        arena = assemble_composed_arena(
            "hero.fighter_l5_wounded_necrotic",
            "monsters.srd_goblinoid_warband",
            "battlefield.arcane_device_bright",
            "neutral.battlefield.arcane_device_bright",
            opening_faction="monsters",
        )
        for actor in (*arena.side_a, *arena.side_b):
            for damage_type in DamageType:
                actor.health.damage_reduction.self_static.add_resistance_modifier(
                    ResistanceModifier(
                        source_entity_uuid=actor.uuid,
                        target_entity_uuid=actor.uuid,
                        name=f"Finite-horizon immunity to {damage_type.value}",
                        value=ResistanceStatus.IMMUNITY,
                        damage_type=damage_type,
                    )
                )
        return arena

    result = run_external_selfplay_with_arena_factory(
        "finite-horizon-stalemate-regression",
        arena_factory,
        max_commands=DEFAULT_RATING_MAX_COMMANDS,
        random_seed=20260717,
    )
    adjudication = _termination_adjudication(result)

    assert result.status == "stalemate_draw"
    assert result.command_count < DEFAULT_RATING_MAX_COMMANDS
    assert result.stalemate_evidence is not None
    assert result.stalemate_evidence.command_window == STALEMATE_COMMAND_WINDOW
    assert result.stalemate_evidence.end_command_index - result.stalemate_evidence.start_command_index + 1 == STALEMATE_COMMAND_WINDOW
    assert adjudication.kind == "stalemate_draw"
    assert adjudication.no_progress_command_window == STALEMATE_COMMAND_WINDOW
