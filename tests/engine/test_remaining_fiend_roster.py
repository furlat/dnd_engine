"""All selected Devil recipes materialize; representative kits use native actions."""

from uuid import uuid4

import pytest

from dnd.actions import Attack, AttackEvent
from dnd.actions_functional import execute_by_index, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.action_types import ActionSelection
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.fiends import FIEND_RECIPES_BY_ID
from dnd.monsters.remaining_fiends import REMAINING_FIEND_DEFINITIONS, REMAINING_FIEND_RECIPES_BY_ID
from dnd.monsters.traits import InnateInvisibility, MultiattackAction
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import EldritchBlast, MagicMissile
from tests.engine.support import force_attack_hit


EXPECTED = (
    ("oathblade_devil",119,17),("blade_marshal_devil",142,18),("wing_regent_devil",207,17),
    ("glaive_warden_devil",110,17),("oath_captain_devil",152,20),("gate_tyrant_devil",199,20),
    ("ash_scribe_devil",45,12),("debt_collector_devil",39,14),("reaping_imp",10,13),
    ("wardblade_devil",52,17),("contract_cutter_devil",45,15),("bow_harrier_devil",27,14),
    ("night_archer_devil",52,16),("night_notary_devil",90,12),("gate_guard_devil",75,17),
    ("ivory_marksman_devil",90,17),("bastion_magus_devil",75,17),("bulwark_devil",85,18),
    ("tollbreaker_devil",90,14),("shieldwing_imp",10,15),("club_mote_devil",7,12),
    ("standard_mote_devil",13,13),("needle_mote_devil",7,12),("spear_mote_devil",9,12),
    ("bow_mote_devil",18,13),("buckler_mote_devil",27,15),("rod_mote_devil",18,12),
    ("twinhaft_mote_devil",27,16),
)
DEFINITIONS = {row.key:row for row in REMAINING_FIEND_DEFINITIONS}


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(16,12))
    get_map().create_rectangle(0,0,16,12)
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(16,12))


def fiend(game,key,mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS):
    actor = materialize_creature(REMAINING_FIEND_RECIPES_BY_ID[key],runtime_entity_uuid=uuid4(),
        display_name=key,position=(4,4),faction="fiends",
        deployment_role=CreatureDeploymentRole(role_id="tests.remaining_fiends"),possession_mode=mode)
    actor.compose_entity()
    game.deploy_entity(actor,actor.position)
    return actor


def target(game,position=(5,4),faction="enemies"):
    actor = Entity.create(uuid4(),"Target",config=EntityConfig(faction=faction,
        health=HealthConfig(max_hit_points_bonus=1000)))
    setup_standard_actions(actor)
    actor.compose_entity()
    game.deploy_entity(actor,position)
    return actor


@pytest.mark.parametrize("key,hp,ac",EXPECTED)
@pytest.mark.parametrize("mode",tuple(CreaturePossessionMode))
def test_every_selected_recipe_materializes_exact_stat_block_and_real_possessions(game,key,hp,ac,mode):
    actor = fiend(game,key,mode)
    definition = DEFINITIONS[key]
    assert actor.get_hp() == hp
    assert tuple(ability.ability_score.score for ability in actor.ability_scores.abilities_list) == definition.abilities
    assert actor.creature_type == CreatureType.FIEND
    assert actor.action_economy.current_speed() == definition.speed
    assert actor.appearance.visual_scale == 1.0
    assert actor.ac_bonus().normalized_score == (ac if mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        else 10+(definition.abilities[1]-10)//2)
    gear = actor.equipment.get_all_equipped_items()
    if mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS:
        assert sorted(item.item_id for item in gear) == sorted(row.item_id for row in definition.possessions if row.equipment_slot is not None)
        assert sorted(item.item_id for item in actor.inventory.items.values()) == sorted(row.item_id for row in definition.possessions if row.equipment_slot is None)
    elif key == "wing_regent_devil":
        assert [item.item_id for item in gear] == ["weapon.creature.wing_regent_devil_claws"]
    else:
        assert not gear
    assert all(item.intrinsic_owner_uuid == actor.uuid if item.item_id.startswith("weapon.creature.")
        else item.intrinsic_owner_uuid is None and item.is_pickable for item in gear)
    multi = [action for action in actor.registered_actions if isinstance(action,MultiattackAction)]
    assert [action.attack_sequence for action in multi] == ([definition.attacks] if definition.attacks else [])


@pytest.mark.parametrize("key,count",[("oathblade_devil",3),("contract_cutter_devil",2),
    ("tollbreaker_devil",2),("twinhaft_mote_devil",2),("wing_regent_devil",3),
    ("bow_harrier_devil",2),("debt_collector_devil",2)])
def test_discovered_multiattack_executes_exact_native_item_sequence_for_one_action(game,key,count):
    actor = fiend(game,key)
    victim = target(game,(7,4) if key == "bow_harrier_devil" else (5,4))
    Entity.update_all_entities_senses()
    available = actor.get_available_actions(include_aoe_preview=False)
    row = next(row for row in available.all_actions if row.behavior_id == "action.monster.multiattack")
    destination = next(item for item in row.valid_targets if item.position == victim.position)
    cursor = EventQueue.event_cursor()
    if key != "bow_harrier_devil":
        force_attack_hit(actor)
    with fixed_dice_faces(*([15,3]*10) if key == "bow_harrier_devil" else [3]*100):
        root = execute_by_index(actor,row.template_name,destination.index,available=available)
    assert root is not None and not root.canceled, root.status_message
    children = [event for _,event in EventQueue.iter_events_since(cursor)
        if isinstance(event,AttackEvent) and event.phase is EventPhase.COMPLETION]
    assert len(children) == count
    assert [event.weapon_slot for event in children] == [slot for slot,n in DEFINITIONS[key].attacks for _ in range(n)]
    assert all(event.source_item_uuid == actor.equipment.get_weapon(event.weapon_slot).uuid for event in children)
    assert all(event.parent_lineage == root.lineage_uuid for event in children)
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.bonus_actions.normalized_score == 1
    if DEFINITIONS[key].paired_weapon_training:
        off = next(event for event in children if event.weapon_slot is WeaponSlot.MELEE_OFF)
        assert off.damages[0].read_bonus().normalized_score == max((DEFINITIONS[key].abilities[0]-10)//2,
            (DEFINITIONS[key].abilities[1]-10)//2) + (2 if key == "oathblade_devil" else 0)


@pytest.mark.parametrize("key,kind,bonus",[("oathblade_devil",DamageType.PSYCHIC,6),
    ("blade_marshal_devil",DamageType.PSYCHIC,7),("glaive_warden_devil",DamageType.PSYCHIC,6),
    ("wardblade_devil",DamageType.PSYCHIC,5),("wing_regent_devil",DamageType.NECROTIC,6)])
def test_only_accepted_real_item_or_intrinsic_rider_is_delivered_once_per_hit(game,key,kind,bonus):
    actor = fiend(game,key)
    victim = target(game)
    Entity.update_all_entities_senses()
    template = next(action for action in actor.registered_actions if isinstance(action,Attack)
        and action.weapon_slot is WeaponSlot.MELEE_MAIN)
    with fixed_dice_faces(15,*([3]*30)):
        event = actor.perform(template,ActionSelection(template_uuid=template.uuid,target_uuids=(victim.uuid,)))
    assert event is not None and not event.canceled
    assert len(event.damages) == 2
    assert event.damages[0].read_bonus().normalized_score == bonus
    assert event.attack_bonus.normalized_score == bonus+DEFINITIONS[key].proficiency
    assert (event.damages[1].dice_numbers,event.damages[1].damage_dice,event.damages[1].damage_type) == (2,6,kind)


@pytest.mark.parametrize("key",["oath_captain_devil","gate_tyrant_devil","ivory_marksman_devil","bulwark_devil","tollbreaker_devil"])
def test_removed_inferred_infernal_weapon_rider_does_not_return(game,key):
    actor = fiend(game,key)
    slot = WeaponSlot.RANGED_MAIN if key == "ivory_marksman_devil" else WeaponSlot.MELEE_MAIN
    victim = target(game,(7,4) if slot is WeaponSlot.RANGED_MAIN else (5,4))
    Entity.update_all_entities_senses()
    template = next(action for action in actor.registered_actions if isinstance(action,Attack) and action.weapon_slot is slot)
    with fixed_dice_faces(15,*([3]*20)):
        result = actor.perform(template,ActionSelection(template_uuid=template.uuid,target_uuids=(victim.uuid,)))
    assert result is not None and not result.canceled
    assert len(result.damages) == 1


@pytest.mark.parametrize("key,level,beams",[("ash_scribe_devil",5,2),("night_notary_devil",11,3),
    ("bastion_magus_devil",5,2),("rod_mote_devil",1,1)])
def test_eldritch_blast_is_one_native_cast_at_explicit_level_without_free_multiattack(game,key,level,beams):
    actor = fiend(game,key)
    victim = target(game,(8,4))
    # Staff + dagger caster must free a hand for somatic casting.
    if key == "rod_mote_devil":
        assert actor.unequip_item(WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()
    spell = next(action for action in actor.registered_actions if isinstance(action,EldritchBlast))
    source = actor.spellcasting.sources[spell.spellcasting_source_id]
    assert source.provider_id == actor.content_ref.content_id
    assert source.source_kind == "innate" and source.provider_level == level and source.ability == "charisma"
    assert not any(isinstance(action,MultiattackAction) for action in actor.registered_actions)
    hp = victim.get_hp()
    with fixed_dice_faces(*([15,10]*10)):
        result = actor.perform(spell,ActionSelection(template_uuid=spell.uuid,target_uuids=(victim.uuid,)))
    assert result is not None and not result.canceled, result.status_message
    assert victim.get_hp() == hp - beams*10
    assert actor.action_economy.actions.normalized_score == 0
    assert all(actor.action_economy.spell_slot_value(rank).normalized_score == 0 for rank in range(1,10))


@pytest.mark.parametrize("key",["shieldwing_imp","reaping_imp"])
def test_only_two_armed_imps_keep_native_invisibility_and_flight_without_sting_or_shapechanger(game,key):
    actor = fiend(game,key)
    victim = target(game)
    Entity.update_all_entities_senses()
    template = next(action for action in actor.registered_actions if isinstance(action,InnateInvisibility))
    result = actor.perform(template,ActionSelection(template_uuid=template.uuid,target_uuids=(actor.uuid,)))
    assert result is not None and not result.canceled
    assert ("Invisible" in actor.active_conditions) and ("Concentrating" in actor.active_conditions)
    assert actor.action_economy.actions.normalized_score == 0
    assert not any("sting" in action.name.lower() or "shapechange" in action.name.lower() for action in actor.registered_actions)
    actor.on_turn_start()
    attack = next(action for action in actor.registered_actions if isinstance(action,Attack) and action.weapon_slot is WeaponSlot.MELEE_MAIN)
    with fixed_dice_faces(15,*([3]*20)):
        event = actor.perform(attack,ActionSelection(template_uuid=attack.uuid,target_uuids=(victim.uuid,)))
    assert event is not None and not event.canceled
    assert not ("Invisible" in actor.active_conditions)


def test_new_family_does_not_replace_the_six_existing_native_identities():
    assert len(REMAINING_FIEND_RECIPES_BY_ID) == 28
    assert not set(REMAINING_FIEND_RECIPES_BY_ID) & set(FIEND_RECIPES_BY_ID)
    assert set(FIEND_RECIPES_BY_ID) == {"claw_mote_devil","huntsman_wing_devil","fellwing_devil"}
    assert not {"thornback_devil","hookclaw_devil","ironhide_devil"} & set(REMAINING_FIEND_RECIPES_BY_ID)


@pytest.mark.parametrize("key",["ash_scribe_devil","bastion_magus_devil","oath_captain_devil"])
def test_native_daily_bless_spends_exact_owned_use_and_only_long_rest_recharges(game,key):
    actor = fiend(game,key)
    # Shielded captain's sword hand must be freed for somatic casting.
    if key == "oath_captain_devil":
        assert actor.unequip_item(WeaponSlot.MELEE_MAIN)
    Entity.update_all_entities_senses()
    spell = next(action for action in actor.registered_actions if action.behavior_binding.behavior_id == "spell.bless")
    source_id = spell.spellcasting_source_id
    source = actor.spellcasting.sources[source_id]
    resource = "innate.spell.bless.1"
    capacity = 1 if key == "ash_scribe_devil" else 3
    assert source.provider_id == actor.content_ref.content_id and source.ability == "charisma"
    assert source.source_kind == "innate" and source.maximum_spell_rank == 1
    assert actor.action_economy.get_resource_current(resource) == capacity
    for remaining in reversed(range(capacity)):
        actor.on_turn_start()
        result = actor.perform(spell,ActionSelection(template_uuid=spell.uuid,target_uuids=(actor.uuid,)))
        assert result is not None and not result.canceled, result.status_message
        assert actor.action_economy.get_resource_current(resource) == remaining
        assert actor.action_economy.actions.normalized_score == 0
    actor.on_turn_start()
    result = actor.perform(spell,ActionSelection(template_uuid=spell.uuid,target_uuids=(actor.uuid,)))
    assert result is None or result.canceled
    assert actor.action_economy.actions.normalized_score == 1
    actor.on_short_rest()
    assert actor.action_economy.get_resource_current(resource) == 0
    assert actor.on_long_rest()
    assert actor.action_economy.get_resource_current(resource) == capacity
    assert source_id in actor.spellcasting.sources


@pytest.mark.parametrize("key",[row.key for row in REMAINING_FIEND_DEFINITIONS if row.spells or row.reactions])
def test_every_selected_spell_has_exact_innate_source_rank_and_finite_resource(game,key):
    actor = fiend(game,key)
    definition = DEFINITIONS[key]
    for selection in definition.spells:
        action = next(row for row in actor.registered_actions if isinstance(row,selection.spell_type))
        source = actor.spellcasting.sources[action.spellcasting_source_id]
        assert source.ability == "charisma" and source.provider_id == actor.content_ref.content_id
        assert source.source_kind == "innate" and source.provider_level == selection.caster_level
        assert source.maximum_spell_rank == selection.rank and action.cast_at_level == selection.rank
        assert not any(cost.cost_type.startswith("spell_slot") for cost in action.effective_costs)
        if selection.daily_uses is not None:
            resource = f"innate.{action.behavior_binding.behavior_id}.{selection.rank}"
            assert actor.action_economy.get_resource_current(resource) == selection.daily_uses
            assert sum(cost.resource_cost for cost in action.effective_costs if cost.resource_name == resource) == 1
    for reaction,rank,uses in definition.reactions:
        ownership = actor.spellcasting.learned_reaction_spell_handlers[reaction.spell.ref.content_id]
        assert len(ownership.sources) == 1
        selected = next(iter(ownership.sources.values()))
        source = actor.spellcasting.sources[selected.source_id]
        assert source.source_kind == "innate" and source.ability == "charisma"
        assert source.provider_id == actor.content_ref.content_id
        assert selected.fixed_cast_rank == rank
        assert actor.action_economy.get_resource_current(selected.resource_name) == uses
    assert all(actor.action_economy.spell_slot_value(rank).normalized_score == 0 for rank in range(1,10))


@pytest.mark.parametrize("key",[row.key for row in REMAINING_FIEND_DEFINITIONS])
def test_shared_devil_lore_is_real_owned_language_senses_and_defense_data(game,key):
    actor = fiend(game,key)
    definition = DEFINITIONS[key]
    assert all(actor.creature_proficiencies.knows_language(language) for language in ("language.common","language.infernal"))
    assert actor.check_condition_immunity("Poisoned")
    assert actor.action_economy.flying_speed.normalized_score == (definition.flying_speed or 0)
    hp = actor.get_hp()
    for damage_type in (DamageType.FIRE,DamageType.POISON):
        actor.receive_damage(6,damage_type,source_entity_uuid=actor.uuid)
        assert actor.get_hp() == hp
    actor.receive_damage(6,DamageType.COLD,source_entity_uuid=actor.uuid)
    assert actor.get_hp() == hp-(3 if definition.imp else 6)


def test_wardblade_real_shield_protection_spends_one_reaction_and_stops_without_shield(game):
    guard = fiend(game,"wardblade_devil")
    ally = target(game,(5,4),"fiends")
    enemy = target(game,(5,5))
    Entity.update_all_entities_senses()
    attack = next(action for action in enemy.registered_actions if isinstance(action,Attack)
        and action.weapon_slot is WeaponSlot.MELEE_MAIN)
    with fixed_dice_faces(15,*([3]*20)):
        event = enemy.perform(attack,ActionSelection(template_uuid=attack.uuid,target_uuids=(ally.uuid,)))
    assert event is not None and not event.canceled
    assert guard.action_economy.reactions.normalized_score == 0
    guard.on_turn_start()
    enemy.on_turn_start()
    assert guard.unequip_item(WeaponSlot.MELEE_OFF)
    with fixed_dice_faces(15,*([3]*20)):
        event = enemy.perform(attack,ActionSelection(template_uuid=attack.uuid,target_uuids=(ally.uuid,)))
    assert event is not None and not event.canceled
    assert guard.action_economy.reactions.normalized_score == 1


def test_gate_tyrant_fixed_rank_three_thunderwave_uses_four_d8_and_cha_dc16(game):
    actor = fiend(game,"gate_tyrant_devil")
    victim = target(game)
    assert actor.unequip_item(WeaponSlot.MELEE_MAIN)
    Entity.update_all_entities_senses()
    spell = next(action for action in actor.registered_actions if action.behavior_binding.behavior_id == "spell.thunderwave")
    hp = victim.get_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2]*30)):
        result = actor.perform(spell,ActionSelection(template_uuid=spell.uuid,positions=((6,4),)))
    assert result is not None and not result.canceled
    assert victim.get_hp() == hp-8
    casts = [event for _,event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.CAST_SPELL and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == victim.uuid]
    assert len(casts) == 1
    assert casts[0].save_dc == 16 and casts[0].damages[0].dice_numbers == 4
    assert actor.action_economy.get_resource_current("innate.spell.thunderwave.3") == 2
    assert actor.action_economy.actions.normalized_score == 0


def test_bastion_selected_shield_is_a_real_finite_innate_reaction_without_shared_slots(game):
    actor = fiend(game,"bastion_magus_devil")
    enemy = Entity.create(uuid4(),"Caster",config=EntityConfig(faction="enemies",
        action_economy=ActionEconomyConfig(spell_slots={1:1})))
    setup_standard_actions(enemy)
    enemy.compose_entity()
    game.deploy_entity(enemy,(7,4))
    register_spell(enemy,MagicMissile)
    Entity.update_all_entities_senses()
    spell = next(action for action in enemy.registered_actions if isinstance(action,MagicMissile))
    hp = actor.get_hp()
    with fixed_dice_faces(*([1]*20)):
        event = enemy.perform(spell,ActionSelection(template_uuid=spell.uuid,target_uuids=(actor.uuid,)))
    assert event is not None and not event.canceled
    assert actor.get_hp() == hp
    assert actor.action_economy.reactions.normalized_score == 0
    assert actor.action_economy.get_resource_current("innate.spell.shield.1") == 2
    assert all(actor.action_economy.spell_slot_value(rank).normalized_score == 0 for rank in range(1,10))
