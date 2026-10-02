"""Restored saving-throw, turn-end, and combat-log hierarchy contracts."""

from collections import Counter
from dataclasses import dataclass
from typing import Literal
from unittest.mock import patch
from uuid import UUID

from dnd.core.combat_log import CombatLogEntryType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SavingThrowEvent,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.residues import ASHEN_RESIDUE
from dnd.spells.evocation import Fireball
from tests.engine.test_combat_actions import (
    reset_core_action_state,
    strong_entity,
)
from tests.engine.test_spell_families import (
    assert_completed_spell,
    create_family_caster,
    create_family_target,
    penalize_save,
    reset_spell_family_state,
)


CoverageStatus = Literal["active", "strengthened"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived lifecycle case's maintained replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_148_event_lifecycle_legacy_contract.py"
SAVE_SELECTOR = (
    f"{THIS_FILE}::test_saving_throw_effect_handler_sees_and_replaces_result"
)
TURN_SELECTOR = (
    f"{THIS_FILE}::test_turn_end_handlers_receive_all_mutable_phases_once"
)
LOG_SELECTOR = (
    f"{THIS_FILE}::test_fireball_emits_one_parent_log_with_isolated_target_children"
)


SAVING_THROW_EVENT_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_saving_throw_phases": LegacyCoverage(
        "active",
        SAVE_SELECTOR,
        "The maintained test asserts declaration through completion for one lineage.",
    ),
    "test_handler_intercepts_effect_phase": LegacyCoverage(
        "active",
        SAVE_SELECTOR,
        "The effect handler receives typed roll and result facts.",
    ),
    "test_handler_can_modify_result": LegacyCoverage(
        "strengthened",
        SAVE_SELECTOR,
        "A deterministic failed save is replaced with success and returned to the caller.",
    ),
}


TURN_END_HANDLER_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_turn_end_handler": LegacyCoverage(
        "active",
        TURN_SELECTOR,
        "The execution handler fires once and its modified event reaches completion.",
    ),
    "test_turn_end_phases_progress": LegacyCoverage(
        "strengthened",
        TURN_SELECTOR,
        "All mutable phases dispatch while completion remains observation-only.",
    ),
}


COMBAT_LOG_HIERARCHY_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_fireball_combat_log_hierarchy": LegacyCoverage(
        "strengthened",
        LOG_SELECTOR,
        "The maintained deterministic cast asserts one parent and one isolated target branch per affected creature.",
    ),
}


def test_event_lifecycle_manifests_account_for_all_6_cases() -> None:
    """Every archived event-lifecycle case has an exact disposition."""
    assert len(SAVING_THROW_EVENT_LEGACY_CASES) == 3
    assert len(TURN_END_HANDLER_LEGACY_CASES) == 2
    assert len(COMBAT_LOG_HIERARCHY_LEGACY_CASES) == 1
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for ledger in (
            SAVING_THROW_EVENT_LEGACY_CASES,
            TURN_END_HANDLER_LEGACY_CASES,
            COMBAT_LOG_HIERARCHY_LEGACY_CASES,
        )
        for case, row in ledger.items()
    )


def test_saving_throw_effect_handler_sees_and_replaces_result() -> None:
    """Saving-throw effect interception changes the authoritative result."""
    reset_core_action_state()
    saver = strong_entity("Saver", (1, 1), "heroes")
    caster = strong_entity("Caster", (2, 1), "monsters")
    effect_events: list[SavingThrowEvent] = []

    def force_success(event: Event, _source_uuid: UUID) -> Event | None:
        if not isinstance(event, SavingThrowEvent):
            return None
        effect_events.append(event)
        assert event.phase is EventPhase.EFFECT
        assert event.dice_roll is not None
        assert event.result is False
        return event.model_copy(
            update={
                "result": True,
                "modified": True,
                "status_message": "Test handler forced success",
            }
        )

    saver.add_event_handler(
        EventHandler(
            name="Force Save Success",
            source_entity_uuid=saver.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SAVING_THROW,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=saver.uuid,
                )
            ],
            event_processor=force_success,
        )
    )
    request = caster.create_saving_throw_request(
        target_entity_uuid=saver.uuid,
        ability_name="wisdom",
        dc=30,
    )

    with patch("dnd.core.dice.random.randint", return_value=1):
        outcome, roll, success = saver.saving_throw(request)

    assert success is True
    assert outcome.value == "Hit"
    assert roll.total < 30
    assert len(effect_events) == 1
    phases = {
        event.phase
        for event in EventQueue.get_events_by_type(EventType.SAVING_THROW)
        if event.lineage_uuid == request.lineage_uuid
    }
    assert phases == {
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    }
    completion = next(
        event
        for event in EventQueue.get_events_by_type(EventType.SAVING_THROW)
        if event.lineage_uuid == request.lineage_uuid
        and event.phase is EventPhase.COMPLETION
    )
    assert isinstance(completion, SavingThrowEvent)
    assert completion.result is True
    assert completion.modified is True


def test_turn_end_handlers_receive_all_mutable_phases_once() -> None:
    """TURN_END dispatches declaration/execution/effect but not completion."""
    reset_core_action_state()
    entity = strong_entity("Turn Actor", (1, 1), "heroes")
    phases_seen: list[EventPhase] = []

    def track_phase(event: Event, _source_uuid: UUID) -> Event | None:
        phases_seen.append(event.phase)
        if event.phase is EventPhase.EXECUTION:
            return event.model_copy(
                update={
                    "modified": True,
                    "status_message": "Execution handler ran",
                }
            )
        return None

    for phase in EventPhase:
        entity.add_event_handler(
            EventHandler(
                name=f"Turn End {phase.value}",
                source_entity_uuid=entity.uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.TURN_END,
                        event_phase=phase,
                        event_source_entity_uuid=entity.uuid,
                    )
                ],
                event_processor=track_phase,
            )
        )

    completion = entity.on_turn_end()

    assert phases_seen == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
    ]
    assert completion.phase is EventPhase.COMPLETION
    assert completion.modified is True


def test_fireball_emits_one_parent_log_with_isolated_target_children() -> None:
    """One Fireball completion owns distinct per-target combat-log branches."""
    reset_spell_family_state(width=20, height=12)
    caster = create_family_caster(
        position=(2, 5),
        spell_slots={3: 1},
    )
    targets = [
        create_family_target(
            name=f"Fireball Target {index}",
            position=position,
        )
        for index, position in enumerate(((8, 5), (8, 6), (9, 5)), start=1)
    ]
    for target in targets:
        penalize_save(target, "dexterity")
    hp_before = {target.uuid: target.get_hp() for target in targets}
    Entity.update_all_entities_senses(max_distance=80)
    captured: list[Event] = []
    EventQueue.set_combat_log_callback(captured.append)
    try:
        with fixed_dice_faces(*([2] * 27)):
            result = Fireball(
                source_entity_uuid=caster.uuid,
                end_position=(8, 5),
                template=False,
            ).apply()
    finally:
        EventQueue.set_combat_log_callback(None)

    result = assert_completed_spell(result)
    assert result.total_targets == len(targets)
    assert len(captured) == 1
    parent_log = captured[0].combat_log
    assert parent_log is not None
    assert parent_log.entry_type is CombatLogEntryType.MULTI_ENTITY_ACTION
    target_ids = {str(target.uuid) for target in targets}
    target_logs = [entry for entry in parent_log.sub_entries if entry.target_uuid in target_ids]
    residue_logs = [entry for entry in parent_log.sub_entries if entry.target_uuid not in target_ids]
    assert len(target_logs) == len(targets)
    assert {entry.target_uuid for entry in target_logs} == target_ids
    assert parent_log.data["total_targets"] == len(targets)
    assert parent_log.data["total_damage"] == 48
    assert parent_log.data["per_target_damage"] == [16, 16, 16]
    assert parent_log.data["saves_failed"] == 3
    assert parent_log.data["saves_succeeded"] == 0
    per_target_logs = parent_log.data["per_target_logs"]
    assert len(per_target_logs) == len(targets)
    assert {entry["target_uuid"] for entry in per_target_logs} == target_ids
    assert all(target.get_hp() == hp_before[target.uuid] - 16 for target in targets)
    for entry in target_logs:
        assert entry.entry_type is CombatLogEntryType.SPELL_SAVE
        assert entry.data["save_success"] is False
        assert entry.data["final_damage"] == 16
        assert Counter(child.entry_type for child in entry.sub_entries) == Counter({
            CombatLogEntryType.SAVING_THROW: 1,
            CombatLogEntryType.DAMAGE_TAKEN: 1,
        })
        descendants = list(entry.sub_entries)
        while descendants:
            child = descendants.pop()
            assert child.target_uuid in {None, entry.target_uuid}
            descendants.extend(child.sub_entries)

    # Inert residue remains causal log evidence, without becoming a spell target.
    residue_tile_ids = set()
    assert result.resolved_area_positions
    for position in result.resolved_area_positions:
        tile = get_map().get_tile(*position)
        assert tile is not None and ASHEN_RESIDUE.name in tile.active_conditions
        residue_tile_ids.add(str(tile.uuid))
    assert len(residue_logs) == len(residue_tile_ids)
    assert {entry.target_uuid for entry in residue_logs} == residue_tile_ids
    assert all(entry.entry_type is CombatLogEntryType.CONDITION_APPLIED for entry in residue_logs)
    assert len(parent_log.sub_entries) == len(targets) + len(residue_tile_ids)
