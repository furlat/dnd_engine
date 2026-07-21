from ai.evaluation.config_ladder.normalization import normalize_selfplay_result
from ai.external_selfplay import (
    ExternalSelfPlayResult,
    ExternalSelfPlayTrace,
    STALEMATE_COMMAND_WINDOW,
    is_stalemate_window,
)


def test_semantic_hash_ignores_uuid_session_and_timing_noise() -> None:
    first = _result(session_id="session-a", actor_uuid="actor-a", target_uuid="target-a", elapsed_ms=12.0)
    second = _result(session_id="session-b", actor_uuid="actor-b", target_uuid="target-b", elapsed_ms=99.0)

    first_normalized = normalize_selfplay_result(first)
    second_normalized = normalize_selfplay_result(second)

    assert first_normalized.semantic_hash == second_normalized.semantic_hash
    assert first_normalized == second_normalized


def test_semantic_hash_changes_when_decision_or_outcome_changes() -> None:
    first = _result(session_id="session", actor_uuid="actor", target_uuid="target", elapsed_ms=12.0)
    changed_trace = first.traces[0].model_copy(update={"template_name": "Dash", "semantic_key": "movement.dash"})
    changed = first.model_copy(update={"traces": [changed_trace]})

    assert normalize_selfplay_result(first).semantic_hash != normalize_selfplay_result(changed).semantic_hash


def test_semantic_hash_ignores_runtime_item_uuid_suffixes() -> None:
    first = _result(session_id="session", actor_uuid="actor", target_uuid="target", elapsed_ms=12.0)
    first_trace = first.traces[0].model_copy(
        update={"template_name": "Drink Haste Potion__item_11111111-1111-1111-1111-111111111111"}
    )
    second_trace = first.traces[0].model_copy(
        update={"template_name": "Drink Haste Potion__item_22222222-2222-2222-2222-222222222222"}
    )

    first_normalized = normalize_selfplay_result(first.model_copy(update={"traces": [first_trace]}))
    second_normalized = normalize_selfplay_result(first.model_copy(update={"traces": [second_trace]}))

    assert first_normalized.commands[0].template_name == "Drink Haste Potion"
    assert first_normalized.semantic_hash == second_normalized.semantic_hash


def test_stalemate_window_uses_objective_hp_progress_not_action_names() -> None:
    base = _result(session_id="session", actor_uuid="actor", target_uuid="target", elapsed_ms=12.0).traces[0]
    traces = [
        base.model_copy(update={
            "command_index": index,
            "template_name": ("Attack" if index % 3 == 0 else "Dodge"),
            "semantic_key": ("dnd.actions.Attack" if index % 3 == 0 else "dnd.actions.Dodge"),
            "outcome_logical_tags": (["attack_missed"] if index % 3 == 0 else []),
        })
        for index in range(STALEMATE_COMMAND_WINDOW)
    ]
    unchanged_hp = [(('hero', 18), ('monster_2', 15))] * STALEMATE_COMMAND_WINDOW

    assert is_stalemate_window(traces, unchanged_hp)
    damage_progress = [*unchanged_hp[:-1], (('hero', 18), ('monster_2', 10))]
    assert not is_stalemate_window(traces, damage_progress)


def _result(*, session_id: str, actor_uuid: str, target_uuid: str, elapsed_ms: float) -> ExternalSelfPlayResult:
    trace = ExternalSelfPlayTrace(
        command_index=0,
        round_number=1,
        turn_index=0,
        session_id=session_id,
        actor_uuid=actor_uuid,
        actor_name="Configured Hero",
        actor_faction="heroes",
        actor_position=(2, 2),
        actor_hp=20,
        entity_action_count=1,
        position_action_count=3,
        command_type="execute",
        row_id=f"entity|Attack|uuid={target_uuid}",
        template_name="Attack",
        semantic_key="attack.weapon",
        target_uuid=target_uuid,
        target_name="Configured Monster",
        target_position=(3, 2),
        reason="Attack a visible hostile.",
        logical_tags=["offense"],
        command_status="accepted",
        action_resolution="hit",
        outcome_code="attack.hit",
        outcome_logical_tags=["damage_dealt"],
        total_ms=elapsed_ms,
        policy_ms=elapsed_ms / 2.0,
    )
    return ExternalSelfPlayResult(
        arena_id="composed-test",
        status="encounter_ended",
        command_count=1,
        elapsed_ms=elapsed_ms,
        session_ids_by_faction={"heroes": session_id},
        final_round=1,
        final_state="completed",
        final_hp_by_actor={"Configured Hero": 20, "Configured Monster": 0},
        final_faction_by_actor={"Configured Hero": "heroes", "Configured Monster": "monsters"},
        traces=[trace],
    )
