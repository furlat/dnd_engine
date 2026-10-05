"""Ray's victim membership and source-turn clock share native condition events."""
import pytest

from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import RayOfFrost
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


@pytest.mark.parametrize('hit', [True, False])
def test_ray_membership_belongs_to_victim_and_expires_on_caster_turn(hit):
    reset_spell_regression_arena(15, 12)
    try:
        caster = create_spell_regression_actor('Caster', (2, 5), 'heroes')
        target = create_spell_regression_actor('Victim', (5, 5), 'enemies')
        Entity.update_all_entities_senses(max_distance=100)
        speed = target.action_economy.movement_remaining()
        cursor = EventQueue.event_cursor()
        with fixed_dice_faces(*([20 if hit else 1] + [3] * 50)):
            RayOfFrost(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
        name = 'Ray of Frost Effect'
        assert name not in caster.active_conditions
        assert (name in target.active_conditions) == hit
        assert target.action_economy.movement_remaining() == speed - (10 if hit else 0)
        if not hit:
            return
        condition_uuid = target.active_conditions[name].uuid
        applied = [e for _,e in EventQueue.iter_events_since(cursor)
            if isinstance(e, ConditionApplicationEvent) and e.phase is EventPhase.COMPLETION
            and e.condition_state is not None and e.condition_state.condition_uuid == condition_uuid]
        assert applied and all(e.target_entity_uuid == target.uuid for e in applied)
        target.on_turn_start()
        assert name in target.active_conditions
        assert target.action_economy.movement_remaining() == speed - 10
        caster.on_turn_start()
        assert name not in target.active_conditions
        assert target.action_economy.movement_remaining() == speed
        removed = [e for _,e in EventQueue.iter_events_since(cursor)
            if isinstance(e, ConditionRemovalEvent) and e.phase is EventPhase.COMPLETION
            and e.condition_state is not None and e.condition_state.condition_uuid == condition_uuid]
        assert removed and all(e.target_entity_uuid == target.uuid for e in removed)
    finally:
        reset_engine_runtime()
