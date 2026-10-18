"""Rule fixes that come with simultaneous resolution (plan §8.1 PB2; human Q2, Q3)."""

from unittest.mock import patch

from dnd.core.base_block import BaseBlock, resolution_order_key
from dnd.actions_functional import setup_standard_actions
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.entity import Entity
from dnd.spells.conjuration import Grease
from dnd.spells.enchantment import Sleep
from tests.engine.test_spell_families import (
    assert_completed_spell,
    create_family_caster,
    create_family_target,
    fixed_zone_randint,
    penalize_save,
    reset_spell_family_state,
)
from tests.engine.support import set_hp


def test_sleep_refunds_a_vetoed_candidate_and_continues_down_the_list() -> None:
    """Q3: a creature whose application is vetoed costs the pool nothing (bug D)."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 2})
    warded = create_family_target(name="Warded", position=(5, 3), hp_dice=1)
    next_lowest = create_family_target(name="Next lowest", position=(6, 3), hp_dice=1)
    set_hp(warded, 5)
    set_hp(next_lowest, 10)
    Entity.update_all_entities_senses()

    def ward(event: Event, _source: object) -> Event:
        return event.cancel(status_message="Warded against this spell")

    warded.add_event_handler(EventHandler(name="Test ward", source_entity_uuid=warded.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EXECUTION,
            event_target_entity_uuid=warded.uuid)], event_processor=ward))
    sleep = Sleep(source_entity_uuid=caster.uuid, end_position=(5, 3), template=False)
    sleep.hp_pool_rolled = 10
    sleep.hp_pool_remaining = 10
    assert_completed_spell(sleep.apply())
    assert "Sleep" not in warded.active_conditions
    assert "Sleep" in next_lowest.active_conditions
    assert sleep.hp_pool_remaining == 0


def test_entering_grease_does_not_consume_the_same_turns_end_of_turn_save() -> None:
    """Q2: arrival and end of turn are separate triggers within one turn (bug C)."""
    reset_spell_family_state(width=18, height=18)
    caster = create_family_caster(position=(1, 1), spell_slots={1: 1})
    target = create_family_target(name="Grease Walker", position=(8, 5))
    setup_standard_actions(target)
    penalize_save(target, "dexterity")
    Entity.update_all_entities_senses(max_distance=30)
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        assert_completed_spell(Grease(source_entity_uuid=caster.uuid, end_position=(5, 5), template=False).apply())
    turn = EventQueue.begin_turn_execution()
    try:
        with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
            Entity.update_entity_position(target, (5, 5))
        assert "Prone" in target.active_conditions
        target.remove_condition("Prone")
        with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
            target.on_turn_end(round_number=1, turn_index=0)
        assert "Prone" in target.active_conditions
    finally:
        EventQueue.end_turn_execution(turn)


def test_simultaneous_order_uses_objective_positions_and_puts_unplaced_blocks_last() -> None:
    """Carried and unplaced blocks no longer sort as if they stood at (0, 0) (bug S)."""
    reset_spell_family_state()
    near = create_family_target(name="Near", position=(1, 1), hp_dice=1)
    far = create_family_target(name="Far", position=(7, 3), hp_dice=1)
    keys = sorted([resolution_order_key(far), resolution_order_key(near)])
    assert keys[0][1:3] == (1, 1) and keys[1][1:3] == (7, 3)
    assert all(not key[0] for key in keys)
    assert isinstance(BaseBlock.get(near.uuid), Entity)
