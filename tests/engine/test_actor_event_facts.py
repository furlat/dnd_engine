"""Committed actor changes remain sufficient after their runtime owners change."""

from uuid import uuid4

from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.events import EventPhase, EventQueue, TemporaryHitPointsChangedEvent
from dnd.core.gridmap import get_map
from dnd.entity import EntityConfig
from dnd.spells.abjuration import ProtectionFromEnergyEffect
from dnd.spells.necromancy import NoHealing
from dnd.types.actor import ConditionState, EntityStatsState
from tests.engine.support import create_test_entity, reset_combat_state


def test_condition_records_keep_health_and_affinity_after_values() -> None:
    reset_combat_state()
    get_map().create_rectangle(0, 0, 3, 1)
    actor = create_test_entity(name="Actor", config=EntityConfig(position=(1, 0)))
    blocked = NoHealing(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    resistant = ProtectionFromEnergyEffect(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    applied = actor.add_condition(blocked)
    assert isinstance(applied, ConditionApplicationEvent) and not applied.canceled
    assert applied.resulting_stats is not None and applied.condition_state is not None
    assert applied.resulting_stats.healing_blocked is True
    saved_condition = applied.condition_state.model_dump_json()
    saved_stats = applied.resulting_stats.model_dump_json()

    protected = actor.add_condition(resistant)
    assert isinstance(protected, ConditionApplicationEvent) and not protected.canceled
    assert protected.resulting_stats is not None
    assert ("Fire", "Resistance") in protected.resulting_stats.damage_affinities
    assert protected.resulting_stats.healing_blocked is True
    cursor = EventQueue.event_cursor()
    actor.remove_condition(blocked.name)
    removed = next(event for _, event in EventQueue.iter_events_since(cursor)
                   if isinstance(event, ConditionRemovalEvent) and event.phase is EventPhase.COMPLETION)
    assert removed.resulting_stats is not None and removed.condition_state is not None
    assert removed.resulting_stats.healing_blocked is False
    assert ("Fire", "Resistance") in removed.resulting_stats.damage_affinities
    assert removed.condition_state.condition_uuid == blocked.uuid
    actor.remove_condition(resistant.name)
    reset_combat_state()

    assert EntityStatsState.model_validate_json(saved_stats).healing_blocked is True
    restored = ConditionState.model_validate_json(saved_condition)
    assert restored.condition_uuid == blocked.uuid
    assert restored.name == "No Healing"


def test_temporary_hp_grants_and_clearing_record_exact_after_values() -> None:
    reset_combat_state()
    get_map().create_rectangle(0, 0, 3, 1)
    actor = create_test_entity(name="Actor", config=EntityConfig(position=(1, 0)))
    source = uuid4()
    cursor = EventQueue.event_cursor()
    actor.health.add_temporary_hit_points(7, source)
    actor.health.add_temporary_hit_points(3, source)
    actor.health.clear_temporary_hit_points()
    events = [event for _, event in EventQueue.iter_events_since(cursor)
              if isinstance(event, TemporaryHitPointsChangedEvent)]
    assert [event.resulting_temporary_hp for event in events] == [7, 0]
    assert all(event.entity_uuid == actor.uuid and event.phase is EventPhase.COMPLETION for event in events)
    reset_combat_state()
