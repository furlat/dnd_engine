"""Several approved effects coexist through actual native encounter turns."""
from uuid import uuid4

from dnd.actions import DropConcentration
from dnd.controller import HumanController
from dnd.core.base_block import BaseBlock
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.items.created_items import GoodberryItem
from dnd.spells.enchantment import Hex, HideousLaughter
from dnd.spells.evocation import Moonbeam, MoveMoonbeam, FireBolt
from dnd.spells.summoning import SpiritualWeapon
from dnd.spells.transmutation import Goodberry
from dnd.summoning.actions import DismissSummon
from dnd.ai.runtime.knowledge_system import bind_ai_knowledge
from dnd.summoning.system import bind_summoning
from tests.engine.test_bg3_rank_one_two_spells import combatant, game
from tests.engine.test_summoning_autonomous_turns import autonomous_attack
from tests.manual.spell_regression_support import force_save_result
from dnd.core.values import Channel, Kind, add_modifier


def accepted(action):
    result=action.apply()
    assert result is not None and not result.canceled,result.status_message if result is not None else 'No action result'
    return result


def advance_to_caster(encounter,caster):
    encounter.next_turn()
    for _ in range(12):
        with fixed_dice_faces(15,*([2]*80)):
            boundary=encounter.advance_one_controller_action_boundary()
        if boundary.status=='waiting_for_human':
            if encounter.get_current_entity() is caster:return
            encounter.next_turn()
        else:
            assert boundary.status in ('autonomous_action_completed','advanced_autonomous')
    raise AssertionError('No next caster input boundary')


def test_items_rider_field_control_and_autonomous_summon_share_native_turns(game):
    caster=combatant(game)
    enemy=combatant(game,'Quarry',(5,2),'foes')
    controlled=combatant(game,'Control recipient',(7,5),'foes')
    add_modifier(caster.max_concentration_slots, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
        name='Existing three-slot concentration capability',value=2,source_entity_uuid=caster.uuid))
    caster.receive_damage(20,DamageType.FORCE,enemy.uuid)
    for target,ability in ((enemy,'constitution'),(controlled,'wisdom')):
        force_save_result(target,ability,succeeds=False)
    encounter=Encounter(source_entity_uuid=uuid4(),name='Mixed spell encounter')
    for actor in (caster,enemy,controlled):
        encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
    encounter.initiative_order=[caster.uuid,enemy.uuid,controlled.uuid]
    encounter.start_encounter();encounter.start_turn()
    system=bind_summoning(game,encounter,bind_ai_knowledge())
    try:
        accepted(Goodberry(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
        berries=[item for item in caster.inventory.items.values() if isinstance(item,GoodberryItem)]
        assert len(berries)==4
        accepted(SpiritualWeapon(source_entity_uuid=caster.uuid,cast_at_level=2,end_position=(4,2)))
        member=next(iter(system.memberships.values()))
        assert caster.action_economy.actions.normalized_score==0
        assert caster.action_economy.bonus_actions.normalized_score==0
        encounter.next_turn()
        hp=enemy.get_hp()
        autonomous_attack(encounter,member.entity.uuid)
        assert enemy.get_hp()<hp
        # Finish the summon through the installed controller, then external turns.
        for _ in range(12):
            with fixed_dice_faces(15,*([2]*80)):boundary=encounter.advance_one_controller_action_boundary()
            if boundary.status=='waiting_for_human':break
        assert boundary.status=='waiting_for_human'
        assert encounter.get_current_entity() is enemy
        encounter.next_turn();encounter.next_turn()
        assert encounter.get_current_entity() is caster
        Entity.update_entity_position(enemy,(9,2));Entity.update_all_entities_senses()
        accepted(Hex(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid))
        hp=enemy.get_hp()
        with fixed_dice_faces(10,2,2):accepted(Moonbeam(source_entity_uuid=caster.uuid,end_position=enemy.position))
        assert enemy.get_hp()==hp-4
        assert caster.action_economy.actions.normalized_score==0 and caster.action_economy.bonus_actions.normalized_score==0
        advance_to_caster(encounter,caster)
        with fixed_dice_faces(10):accepted(HideousLaughter(source_entity_uuid=caster.uuid,target_entity_uuid=controlled.uuid))
        assert not controlled.can_take_actions()
        advance_to_caster(encounter,caster)
        move=next(action for action in caster.registered_actions if isinstance(action,MoveMoonbeam))
        accepted(move.instantiate(end_position=(9,3)))
        hp=caster.get_hp()
        with fixed_dice_faces(3):accepted(berries[0].get_use_actions(caster.uuid)[0].instantiate())
        assert caster.get_hp()==hp+3
        assert BaseBlock.get(berries[0].uuid) is None
        assert caster.action_economy.actions.normalized_score==0 and caster.action_economy.bonus_actions.normalized_score==0
        advance_to_caster(encounter,caster)
        hp=enemy.get_hp()
        with fixed_dice_faces(15,2,2):hit=accepted(FireBolt(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid))
        assert len(hit.damages)==2 and enemy.get_hp()==hp-4
        advance_to_caster(encounter,caster)
        accepted(DropConcentration(source_entity_uuid=caster.uuid))
        assert controlled.can_take_actions()
        assert not any(field.get_display_name()=='Moonbeam' for field in get_map().get_spatial_conditions())
        assert not any(isinstance(action,MoveMoonbeam) for action in caster.registered_actions)
        accepted(DismissSummon(source_entity_uuid=caster.uuid,target_entity_uuid=member.entity.uuid))
        assert not system.memberships and game.get_entity(member.entity.uuid) is None
        caster.on_long_rest()
        assert all(BaseBlock.get(item.uuid) is None for item in berries)
    finally:
        system.close()
