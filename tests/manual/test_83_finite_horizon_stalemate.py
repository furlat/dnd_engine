"""Real-engine regression for finite-horizon draw adjudication."""

from ai.evaluation.config_ladder.match_runner import _termination_adjudication
from ai.evaluation.config_ladder.worker_contracts import DEFAULT_RATING_MAX_COMMANDS
from ai.external_selfplay import (
    run_external_selfplay_with_arena_factory,
    STALEMATE_COMMAND_WINDOW,
)
from dnd.scenarios.evaluation.assembler import assemble_composed_arena


def test_kiting_attack_control_loop_reaches_typed_stalemate_draw() -> None:
    def arena_factory():
        return assemble_composed_arena(
            "hero.fighter_l5_wounded_necrotic",
            "monsters.srd_goblinoid_warband",
            "battlefield.arcane_device_bright",
            "neutral.battlefield.arcane_device_bright",
            opening_faction="monsters",
        )

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
