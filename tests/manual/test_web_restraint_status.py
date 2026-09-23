"""Observed Web restraint identifies the real source without changing its mechanics."""

from uuid import uuid4

import pytest

from dnd.conditions import Restrained
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.condition_types import ConditionCategory
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spells.conjuration import EscapeWebAction, Web, WebRestrained, WebZone
from tests.manual.test_131_inventory_use_actions_legacy_contract import (
    create_caster, create_target, force_save, reset_item_arena,
)


@pytest.mark.parametrize("cleanup", ("escape", "concentration", "zone"))
def test_real_web_save_and_cleanup_publish_exact_stable_restraint_status(cleanup) -> None:
    reset_item_arena()
    caster = create_caster((4, 5))
    failed = create_target((8, 5))
    saved = create_target((8, 6))
    force_save(failed, "dexterity", succeeds=False)
    force_save(saved, "dexterity", succeeds=True)
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(10, 10):
        result = Web(source_entity_uuid=caster.uuid, end_position=(8, 5)).apply()
    assert result is not None and not result.canceled
    zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WebZone))
    applications = [event for _, event in EventQueue.iter_events_since(cursor)
                    if isinstance(event, ConditionApplicationEvent) and isinstance(event.condition, WebRestrained)
                    and event.phase is EventPhase.COMPLETION]
    assert len(applications) == 1 and applications[0].target_entity_uuid == failed.uuid
    applied = applications[0]
    assert applied.behavior_id == "condition.spell.web.restrained"
    assert applied.condition_state is not None
    state = applied.condition_state
    assert state.name == "Web restraint" and state.category is ConditionCategory.STATUS
    assert state.semantic_key == "condition.spell.web.restrained"
    assert str(zone.uuid) not in state.model_dump_json()
    assert "source_spatial_condition_uuid" not in state.model_dump() and "check_dc" not in state.model_dump()
    log = applied.generate_combat_log()
    assert log is not None and "Web restraint" in log.compact and str(zone.uuid) not in log.compact
    assert "Restrained" in failed.active_conditions and not saved.active_conditions

    cursor = EventQueue.event_cursor()
    if cleanup == "escape":
        template = next(action for action in failed.registered_actions if isinstance(action, EscapeWebAction))
        with fixed_dice_faces(20):
            escaped = template.instantiate().apply()
        assert escaped is not None and not escaped.canceled and str(zone.uuid) not in (escaped.status_message or "")
        assert get_map().get_spatial_condition(zone.uuid) is zone
    elif cleanup == "concentration":
        assert caster.remove_condition("Concentrating")
    else:
        assert zone.deactivate() is not None
    removals = [event for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, ConditionRemovalEvent) and isinstance(event.condition, WebRestrained)
                and event.phase is EventPhase.COMPLETION]
    assert len(removals) == 1 and removals[0].condition_state is not None
    assert removals[0].condition_state.condition_uuid == state.condition_uuid
    assert removals[0].condition_state.name == "Web restraint"
    log = removals[0].generate_combat_log()
    assert log is not None and "Web restraint" in log.compact and str(zone.uuid) not in log.compact
    assert not failed.active_conditions


def test_simultaneous_web_sources_keep_distinct_identity_until_last_source_ends() -> None:
    reset_item_arena()
    target = create_target((5, 5))
    cause = Event(source_entity_uuid=target.uuid, event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT)
    sources = [WebRestrained(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        source_spatial_condition_uuid=uuid4(), check_dc=12) for _ in range(2)]
    for source in sources:
        applied = target.add_condition(source, parent_event=cause)
        assert applied is not None and not applied.canceled
    snapshots = [source.snapshot_state() for source in sources]
    assert len({source.name for source in sources}) == len({state.condition_uuid for state in snapshots}) == 2
    assert {state.name for state in snapshots} == {"Web restraint"}
    assert len([action for action in target.registered_actions if isinstance(action, EscapeWebAction)]) == 2
    assert target.remove_condition_by_uuid(sources[0].uuid, parent_event=cause)
    assert sources[1].uuid in target.active_conditions_by_uuid and "Restrained" in target.active_conditions
    assert target.remove_condition_by_uuid(sources[1].uuid, parent_event=cause)
    assert not target.active_conditions
    assert not any(isinstance(action, EscapeWebAction) for action in target.registered_actions)


def test_leaving_web_does_not_remove_unrelated_restraint() -> None:
    reset_item_arena()
    caster = create_caster((4, 5))
    target = create_target((8, 5))
    unrelated = Restrained(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    target.add_condition(unrelated)
    force_save(target, "dexterity", succeeds=False)
    Entity.update_all_entities_senses()
    with fixed_dice_faces(10, 10):
        result = Web(source_entity_uuid=caster.uuid, end_position=(8, 5)).apply()
    assert result is not None and not result.canceled
    assert any(isinstance(condition, WebRestrained) for condition in target.active_conditions.values())
    assert caster.remove_condition("Concentrating")
    assert unrelated.uuid in target.active_conditions_by_uuid
    assert not any(isinstance(condition, WebRestrained) for condition in target.active_conditions.values())
