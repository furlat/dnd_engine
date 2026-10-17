"""New spell shapes survive real worker choices, preview and command capture."""
from uuid import uuid4
from dnd.core.base_block import BaseBlock
from dnd.core.modifiers import NumericalModifier
from dnd.core.gridmap import get_map
from dnd.core.view import cell_visible, visible_positions
from dnd.items.created_items import GoodberryItem
from dnd.spells.enchantment import Hex, HideousLaughter
from tests.engine.test_bg3_spell_hit_riders import equip
from tests.manual.spell_regression_support import force_save_result

from dnd.spells.necromancy import Revivify, RayOfSickness
from dnd.core.creature_types import DamageType
from dnd.core.life_types import LifeState
from tests.engine.test_bg3_rank_one_two_spells import combatant
import pytest
from dnd.actions import SpellEvent, AttackEvent
from dnd.actions_functional import register_spell
from dnd.core.events import EventQueue, EventPhase
from dnd.core.dice import fixed_dice_faces
from dnd.player.commands import ActionSelection
from dnd.spells.evocation import StarryWisp, SorcerousBurst, FaerieFire, FireBolt, ChromaticOrb, FlameBlade, DancingLights, Moonbeam
from dnd.spells.transmutation import Goodberry, DragonsBreath, CreateOrDestroyWater, PlantGrowth
from dnd.spells.summoning import SpiritualWeapon, FlamingSphere
from dnd.spells.enchantment import Heroism
from dnd.spells.abjuration import GlyphOfWarding
from server.protocol import EndTurnIntent, CommandRequest, ExecuteSelectionIntent, PreviewRequest
from server.worker import dispatch, needs_advance
from server.worker_protocol import Advance, Command, Preview
from tests.player.test_compact_choices import world, request_choices, rows


@pytest.mark.parametrize('spell,behavior',[
    (StarryWisp,'starry_wisp'),(SorcerousBurst,'sorcerous_burst'),(FaerieFire,'faerie_fire'),
    (ChromaticOrb,'chromatic_orb'),(FlameBlade,'flame_blade'),(DancingLights,'dancing_lights'),
    (Moonbeam,'moonbeam'),(Goodberry,'goodberry'),(DragonsBreath,'dragons_breath'),
    (CreateOrDestroyWater,'create_or_destroy_water'),(PlantGrowth,'plant_growth'),
    (SpiritualWeapon,'spiritual_weapon'),(FlamingSphere,'flaming_sphere'),
    (Heroism,'heroism'),(GlyphOfWarding,'glyph_of_warding'),(RayOfSickness,'ray_of_sickness'),
])
def test_worker_discovers_previews_executes_and_records_new_spell_shapes(world,spell,behavior):
    runtime,seat,publication=world
    actor=runtime.session.game.entities[publication.boundary.input_actor_uuid]
    register_spell(actor,spell,caster_level=7)
    choices=request_choices(world).choices
    candidates=[row for row in rows(choices) if row.behavior_id=='spell.'+behavior and row.can_afford
        and (choices.target_sets[row.target_set] or row.position_region is not None)]
    if behavior=='chromatic_orb':
        candidates=[row for row in candidates if any(facet.key=='side' and facet.value=='ground' for facet in row.variant_facets)]
    assert candidates,behavior
    action=candidates[0]
    listed=choices.target_sets[action.target_set]
    # A free-aim row lists no cells: aim at a seen point two cells away (plan §14.4).
    aim=(actor.position[0]+2,actor.position[1])
    selection=(ActionSelection(action_index=action.discovery_index,target_indices=(listed[0].index,)) if listed
        else ActionSelection(action_index=action.discovery_index,target_indices=(),extra_target_positions=(aim,)))
    before=EventQueue.event_cursor()
    _,_,preview=dispatch(runtime,Preview(seat_id=seat,request=PreviewRequest(actor_uuid=actor.uuid,
        state_revision=publication.state_revision,discovery_generation=choices.discovery_generation,
        correlation_id=uuid4(),selection=selection)))
    assert preview.preview.can_confirm,behavior
    assert EventQueue.event_cursor()==before
    with fixed_dice_faces(15,*([2]*100)):
        reply,records,_=dispatch(runtime,Command(seat_id=seat,request=CommandRequest(command_number=1,
            actor_uuid=actor.uuid,state_revision=publication.state_revision,
            intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation,selection=selection))))
    assert reply.rejection is None,behavior
    assert records,behavior
    accepted=[event for _,event in EventQueue.iter_events_since(before) if isinstance(event,SpellEvent)
        and event.source_entity_uuid==actor.uuid and not event.canceled]
    assert accepted,behavior


@pytest.mark.parametrize('relocate',[False,True])
def test_worker_revivifies_dead_companion_with_optional_compound_destination(world,relocate):
    runtime,seat,publication=world
    actor=runtime.session.game.entities[publication.boundary.input_actor_uuid]
    ally=combatant(runtime.session.game,'Fallen companion',(4,7),actor.faction)
    ally.is_player_companion=True
    ally.receive_damage(ally.get_hp(),DamageType.FORCE,actor.uuid)
    assert ally.health.life_state is LifeState.DEAD
    register_spell(actor,Revivify,caster_level=7)
    choices=request_choices(world).choices
    action=next(row for row in rows(choices) if row.behavior_id=='spell.revivify' and row.can_afford
        and any(facet.key=='form' and facet.value==('relocate' if relocate else 'in_place') for facet in row.variant_facets))
    assert choices.target_sets[action.target_set],(ally.is_deployed,ally.position,cell_visible(actor.senses.cells, ally.position),Revivify(source_entity_uuid=actor.uuid,target_entity_uuid=ally.uuid).pre_validate(),actor.is_ally(ally))
    target=next(binding for binding in choices.target_sets[action.target_set]
        if choices.subjects[binding.subject].uuid==ally.uuid)
    selection=ActionSelection(action_index=action.discovery_index,target_indices=(target.index,))
    _,_,response=dispatch(runtime,Preview(seat_id=seat,request=PreviewRequest(actor_uuid=actor.uuid,
        state_revision=publication.state_revision,discovery_generation=choices.discovery_generation,
        correlation_id=uuid4(),selection=selection)))
    destination=ally.position
    if relocate:
        assert not response.preview.can_confirm and response.preview.next_positions
        destination=next(response.preview.positions[index] for index in response.preview.next_positions
            if response.preview.positions[index]!=ally.position)
        selection=ActionSelection(action_index=action.discovery_index,target_indices=(target.index,),extra_target_positions=(destination,))
        _,_,response=dispatch(runtime,Preview(seat_id=seat,request=PreviewRequest(actor_uuid=actor.uuid,
            state_revision=publication.state_revision,discovery_generation=choices.discovery_generation,
            correlation_id=uuid4(),selection=selection)))
    assert response.preview.can_confirm
    reply,records,_=dispatch(runtime,Command(seat_id=seat,request=CommandRequest(command_number=1,
        actor_uuid=actor.uuid,state_revision=publication.state_revision,
        intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation,selection=selection))))
    assert reply.rejection is None and records
    assert ally.health.life_state is LifeState.ALIVE and ally.get_normal_hp()==1
    assert ally.position==destination



def test_worker_mixed_spell_encounter_returns_to_human_with_owned_effects_cleaned(world):
    """One real server sequence combines items, summon, control, field and Hex."""
    runtime,seat,_=world
    actor=runtime.session.game.entities[runtime.publications[seat].boundary.input_actor_uuid]
    actor.equipment.ac_bonus.self_static.add_value_modifier(NumericalModifier(
        name='Durable integration caster armor',value=100,source_entity_uuid=actor.uuid))
    actor.max_concentration_slots.self_static.add_value_modifier(NumericalModifier(
        name='Existing three-slot concentration fixture',value=2,source_entity_uuid=actor.uuid))
    enemies=[entity for entity in runtime.session.game.entities.values() if actor.is_enemy(entity)]
    for enemy in enemies:
        enemy.health.max_hit_points_bonus.self_static.add_value_modifier(NumericalModifier(
            name='Durable integration opponent',value=200,source_entity_uuid=enemy.uuid))
        force_save_result(enemy,'constitution',succeeds=False)
        force_save_result(enemy,'wisdom',succeeds=False)
    equip(actor)
    actor.receive_damage(20,DamageType.FORCE,enemies[0].uuid)
    for spell in (Goodberry,SpiritualWeapon,Hex,Moonbeam,HideousLaughter,FireBolt):register_spell(actor,spell,caster_level=7)
    number=0

    def submit(behavior,*,target_uuid=None,position=None,level=None,near=None,facets=()):
        nonlocal number
        publication=runtime.publications[seat]
        assert publication.boundary.input_actor_uuid==actor.uuid
        choices=request_choices((runtime,seat,publication)).choices
        options=[row for row in rows(choices) if row.behavior_id==behavior and row.can_afford and (level is None or row.cast_at_level==level)
            and all(any(facet.key==key and facet.value==value for facet in row.variant_facets) for key,value in facets)]
        chosen=None
        for row in options:
            bindings=choices.target_sets[row.target_set]
            if near is not None:
                bindings=sorted(bindings,key=lambda binding:max(abs(choices.positions[binding.position][0]-near.position[0]),
                    abs(choices.positions[binding.position][1]-near.position[1])))
            for binding in bindings:
                if target_uuid is not None and (binding.kind!='subject' or choices.subjects[binding.subject].uuid!=target_uuid):continue
                if position is not None and (binding.position is None or choices.positions[binding.position]!=position):continue
                chosen=(row,binding);break
            if chosen is not None:break
        if chosen is None and position is None and near is not None:
            # A free-aim row lists no cells: aim at a seen, empty cell beside the creature.
            position=next(cell for cell in sorted((near.position[0]+dx,near.position[1]+dy)
                for dx in (-1,0,1) for dy in (-1,0,1) if (dx,dy)!=(0,0))
                if cell_visible(actor.senses.cells, cell) and not get_map().get_entities_at(cell))
        if chosen is None and position is None and near is None:
            # Any seen, empty point two to three cells from the actor.
            position=next(cell for cell in sorted(visible_positions(actor.senses.cells))
                if 2<=max(abs(cell[0]-actor.position[0]),abs(cell[1]-actor.position[1]))<=3
                and not get_map().get_entities_at(cell))
        if chosen is None and position is not None:
            # A free-aim row lists no cells: aim at the requested point (plan §14.4).
            free=next((row for row in options if row.position_region is not None),None)
            assert free is not None,(behavior,[(row.template_name,len(choices.target_sets[row.target_set])) for row in options])
            selection=ActionSelection(action_index=free.discovery_index,target_indices=(),extra_target_positions=(position,))
        else:
            assert chosen is not None,(behavior,[(row.template_name,len(choices.target_sets[row.target_set])) for row in options])
            row,binding=chosen
            selection=ActionSelection(action_index=row.discovery_index,target_indices=(binding.index,))
        _,_,preview=dispatch(runtime,Preview(seat_id=seat,request=PreviewRequest(actor_uuid=actor.uuid,
            state_revision=publication.state_revision,discovery_generation=choices.discovery_generation,
            correlation_id=uuid4(),selection=selection)))
        assert preview.preview.can_confirm
        number+=1
        # Opponents pass their turns, leaving the ranged caster unthreatened.
        faces=((15,) if behavior=='spell.fire_bolt' else ())+((2,)*100)
        with fixed_dice_faces(*faces):
            reply,records,_=dispatch(runtime,Command(seat_id=seat,request=CommandRequest(command_number=number,
                actor_uuid=actor.uuid,state_revision=publication.state_revision,
                intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation,selection=selection))))
        assert reply.rejection is None and records
        return records

    def next_turn():
        nonlocal number
        publication=runtime.publications[seat]
        number+=1
        reply,_,_=dispatch(runtime,Command(seat_id=seat,request=CommandRequest(command_number=number,
            actor_uuid=actor.uuid,state_revision=publication.state_revision,intent=EndTurnIntent())))
        assert reply.rejection is None
        for _ in range(100):
            if needs_advance(runtime.session):
                with fixed_dice_faces(15,*([2]*100)):dispatch(runtime,Advance())
                continue
            if runtime.publications[seat].boundary.input_actor_uuid==actor.uuid:return
            other_seat,other_publication=next((key,value) for key,value in runtime.publications.items()
                if value.boundary.input_actor_uuid is not None)
            number+=1
            reply,_,_=dispatch(runtime,Command(seat_id=other_seat,request=CommandRequest(command_number=number,
                actor_uuid=other_publication.boundary.input_actor_uuid,state_revision=other_publication.state_revision,
                intent=EndTurnIntent())))
            assert reply.rejection is None
        raise AssertionError('Server did not return to the caster input boundary')

    submit('spell.goodberry',target_uuid=actor.uuid)
    berries=[item for item in actor.inventory.items.values() if isinstance(item,GoodberryItem)]
    assert len(berries)==4
    submit('spell.spiritual_weapon',near=enemies[0],level=2)
    summon=next(entity for entity in runtime.session.game.entities.values() if entity.name=='Spiritual Weapon')
    cursor=EventQueue.event_cursor()
    next_turn()
    strikes=[event for _,event in EventQueue.iter_events_since(cursor) if isinstance(event,AttackEvent)
        and event.source_entity_uuid==summon.uuid and event.phase is EventPhase.COMPLETION and not event.canceled]
    assert strikes and strikes[0].damages[0].damage_type is DamageType.FORCE
    quarry=min(enemies,key=lambda enemy:actor.senses.get_feet_distance(enemy.position))
    control=next(enemy for enemy in enemies if enemy is not quarry)
    submit('spell.hex',target_uuid=quarry.uuid)
    submit('spell.moonbeam',position=quarry.position,level=2)
    next_turn()
    submit('spell.hideous_laughter',target_uuid=control.uuid)
    assert not control.can_take_actions()
    hp=actor.get_hp()
    submit('action.spell.goodberry.eat')
    assert actor.get_hp()>hp and sum(BaseBlock.get(item.uuid) is not None for item in berries)==3
    next_turn()
    submit('action.spell.moonbeam.move')
    next_turn()
    hp=quarry.get_hp();cursor=EventQueue.event_cursor()
    submit('spell.fire_bolt',target_uuid=quarry.uuid)
    hits=[event for _,event in EventQueue.iter_events_since(cursor) if isinstance(event,SpellEvent)
        and event.source_entity_uuid==actor.uuid and event.phase is EventPhase.COMPLETION and not event.canceled]
    assert hits and len(hits[0].damages)==2 and quarry.get_hp()<hp
    next_turn()
    submit('action.drop_concentration')
    assert control.can_take_actions()
    assert not any(field.get_display_name()=='Moonbeam' for field in get_map().get_spatial_conditions())
    submit('action.summon.dismiss',target_uuid=summon.uuid)
    assert summon.uuid not in runtime.session.game.entities
    actor.on_long_rest()
    assert all(BaseBlock.get(item.uuid) is None for item in berries)
