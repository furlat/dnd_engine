"""Canonical NPC recipes produce the selected kits and perform native commands.

Inputs are roster recipes, possession mode and ordinary action/item selections.
Outputs are printed stat totals, real transferable possessions, costs and damage.
"""

from collections import Counter
from uuid import uuid4

import pytest

from dnd.actions import Attack, AttackEvent, SpellAction
from dnd.actions_functional import execute_use_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.health import HealthConfig
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.action_types import ActionSelection, ActionVariantFacet
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.core.modifiers import AdvantageStatus, ResistanceStatus
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.roster_humanoids import HUMANOID_ROSTER_RECIPES_BY_ID
from dnd.monsters.traits import MultiattackAction, SneakAttackFeature
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import BurningHands, FireBolt, MagicMissile
from dnd.spells.illusion import Invisibility


# Independent acceptance rows: identity, HP, equipped AC, bare AC, speed.
EXPECTED = (
    ("orc_rededge",15,11,11,30),("orc_yellowtusk",15,11,11,30),
    ("orc_redblade",15,11,11,30),("orc_greenfang",15,13,11,30),
    ("orc_bristlejaw",15,11,11,30),("orc_longspike",15,11,11,30),
    ("orc_frostmane",40,12,12,30),("orc_brassbrow",40,12,12,30),
    ("orc_blackplate",15,13,11,30),("orc_mudrunner",15,11,11,30),
    ("orc_ironjaw",15,11,11,30),
    ("enemy_bellringer",112,17,12,30),("enemy_blue_quarrel",78,17,13,30),
    ("enemy_gateplate",112,20,12,30),("enemy_blue_twinblade",78,15,13,30),
    ("enemy_gold_knuckle",112,17,12,30),("enemy_reliquary",52,18,10,30),
    ("enemy_far_eye",78,15,13,30),("enemy_dockwall",112,12,12,30),
    ("enemy_magister_nine",99,12,12,30),("enemy_pale_ember",40,12,12,30),
    ("enemy_arcane_sentinel",119,16,16,30),("enemy_bronze_watch",112,17,12,30),
    ("barbarian_gatebreaker",59,9,9,40),("barbarian_cinderplate",112,18,12,30),
    ("barbarian_saffron_ward",65,18,13,30),("barbarian_red_rage",58,11,11,30),
    ("barbarian_farshot",58,11,11,30),("barbarian_stonejaw",67,11,11,30),
    ("barbarian_windmark",58,16,11,30),("barbarian_venom_ritualist",65,16,13,30),
    ("barbarian_sun_ring",27,11,11,30),
    ("character_whiteplate",52,20,10,30),("character_briarline",58,11,11,30),
    ("character_golden_orbit",40,12,12,30),("character_gilded_ward",52,20,10,30),
    ("character_white_streak",78,15,13,30),("character_azure_current",40,12,12,30),
    ("character_violet_oathbreaker",112,20,12,30),("character_hex_sovereign",40,12,12,30),
    ("character_blue_spark",58,16,11,30),
)


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(16,12))
    get_map().create_rectangle(0,0,16,12)
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(16,12))


def npc(game,key,*,mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,position=(4,4)):
    result = materialize_creature(HUMANOID_ROSTER_RECIPES_BY_ID[key],runtime_entity_uuid=uuid4(),
        display_name=key,faction="roster",position=position,
        deployment_role=CreatureDeploymentRole(role_id="test.roster"),possession_mode=mode)
    result.compose_entity()
    game.deploy_entity(result,position)
    return result


def target(game,position=(5,4)):
    actor = Entity.create(uuid4(),"Target",config=EntityConfig(faction="opponents",
        health=HealthConfig(max_hit_points_bonus=1000)))
    actor.compose_entity()
    setup_standard_actions(actor)
    game.deploy_entity(actor,position)
    Entity.update_all_entities_senses()
    return actor


def perform(actor,template,victim,*,faces=(15,)*100):
    Entity.update_all_entities_senses()
    with fixed_dice_faces(*faces):
        event = actor.perform(template,ActionSelection(template_uuid=template.uuid,target_uuids=(victim.uuid,)))
    assert event is not None and not event.canceled
    return event


@pytest.mark.parametrize("key,hp,ac,bare_ac,speed",EXPECTED)
@pytest.mark.parametrize("mode",tuple(CreaturePossessionMode))
def test_all_41_recipes_have_exact_stat_and_possession_policy(game,key,hp,ac,bare_ac,speed,mode):
    actor = npc(game,key,mode=mode)
    assert actor.content_ref == HUMANOID_ROSTER_RECIPES_BY_ID[key].ref
    assert actor.get_normal_hp() == actor.get_max_hp() == hp
    assert actor.ac_bonus().normalized_score == (ac if mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS else bare_ac)
    assert actor.action_economy.current_speed() == speed
    assert actor.creature_type is (CreatureType.GIANT if key == "barbarian_gatebreaker" else
        CreatureType.ELEMENTAL if key == "enemy_arcane_sentinel" else CreatureType.HUMANOID)
    assert actor.size is (Size.LARGE if key == "barbarian_gatebreaker" else Size.MEDIUM)
    assert actor.appearance.visual_scale == 1.0
    equipped = actor.equipment.get_all_equipped_items()
    if key == "enemy_arcane_sentinel":
        assert {item.item_id for item in equipped} == {
            "weapon.creature.arcane_sentinel_slam","armor.creature.arcane_sentinel_natural"}
        assert all(not item.is_pickable and item.intrinsic_owner_uuid == actor.uuid for item in equipped)
    elif mode is CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY:
        assert not equipped and not actor.inventory.items
    else:
        assert equipped and all(item.is_pickable and item.owner_uuid == actor.uuid for item in equipped)


@pytest.mark.parametrize("key,count,die,bonus",[
    ("enemy_gold_knuckle",3,8,4),("enemy_dockwall",3,8,4),
    ("enemy_arcane_sentinel",2,8,3),("enemy_bellringer",3,6,4),
    ("barbarian_red_rage",3,8,3),("orc_mudrunner",2,6,3),
])
def test_selected_multiattacks_hit_with_exact_native_damage(game,key,count,die,bonus):
    actor = npc(game,key)
    victim = target(game)
    multi = next(action for action in actor.registered_actions if isinstance(action,MultiattackAction))
    before = EventQueue.event_cursor()
    dice = 3 if key == "enemy_bellringer" else 2 if key == "enemy_arcane_sentinel" else 1
    perform(actor,multi,victim,faces=tuple(face for _ in range(count) for face in (15,*([1]*dice))))
    attacks = [event for event in (event for _,event in EventQueue.iter_events_since(before))
        if isinstance(event,AttackEvent) and event.phase is EventPhase.COMPLETION]
    assert len(attacks) == count
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.bonus_actions.normalized_score == 1
    assert all(event.damage_rolls and event.damage_rolls[0].total >= bonus+1 for event in attacks)
    assert attacks[0].damages[0].damage_dice == die
    if key in ("enemy_gold_knuckle","enemy_dockwall"):
        assert all(event.source_item_uuid is None and event.damages[0].dice_numbers == 1 for event in attacks)
        assert {condition.name for condition in actor.active_conditions_by_uuid.values()}.isdisjoint({"Brute","Parry"})
    if key == "enemy_arcane_sentinel":
        assert all(event.damages[0].dice_numbers == 2 for event in attacks)
    if key == "enemy_bellringer":
        assert all(sum(packet.dice_numbers for packet in event.damages) == 3 for event in attacks)  # 2d6 Maul + one Brute die.
    if key in ("barbarian_red_rage","orc_mudrunner"):
        assert attacks[-1].damage_rolls[0].total == bonus+1  # Source offhand includes ability.


@pytest.mark.parametrize("key",["enemy_blue_quarrel","enemy_far_eye","enemy_blue_twinblade","character_white_streak"])
def test_assassin_kits_supply_finite_real_vials_and_four_sneak_dice(game,key):
    actor = npc(game,key)
    vials = [item for item in actor.inventory.items.values()
        if item.item_id == "consumable.weapon_coat.assassin_poison"]
    assert len(vials) == 1 and vials[0].stack_count == 3
    sneak = next(condition for condition in actor.active_conditions_by_uuid.values()
        if isinstance(condition,SneakAttackFeature))
    assert sneak.dice_numbers == 4
    assert actor.health.get_resistance(DamageType.POISON) is ResistanceStatus.RESISTANCE
    assert actor.skill_bonus(None,"stealth").normalized_score == 9
    assert actor.saving_throw_bonus(None,"dexterity",None).normalized_score == 6
    assert actor.saving_throw_bonus(None,"intelligence",None).normalized_score == 4
    assert actor.creature_proficiencies.knows_language("language.thieves_cant")
    coat = "Coat Main Hand" if key == "enemy_blue_twinblade" else "Coat Ranged Main Hand"
    event = execute_use_action(actor,vials[0].uuid,coat)
    assert event is not None and not event.canceled
    assert actor.inventory.has_item(vials[0].uuid) and vials[0].stack_count == 2
    assert actor.action_economy.actions.normalized_score == 0


@pytest.mark.parametrize("key,slot,kind",[
    ("enemy_blue_quarrel",WeaponSlot.RANGED_MAIN,"musket"),
    ("enemy_far_eye",WeaponSlot.RANGED_MAIN,"musket"),
    ("orc_longspike",WeaponSlot.RANGED_MAIN,"shortbow"),
    ("orc_ironjaw",WeaponSlot.MELEE_MAIN,"scimitar"),
])
def test_real_weapon_selection_ordinary_attack_and_transfer(game,key,slot,kind):
    actor = npc(game,key)
    victim = target(game,position=(7,4) if slot is WeaponSlot.RANGED_MAIN else (5,4))
    weapon = actor.equipment.get_weapon(slot)
    assert weapon is not None and weapon.item_id == f"weapon.{kind}"
    attack = next(action for action in actor.registered_actions if isinstance(action,Attack) and action.weapon_slot is slot)
    event = perform(actor,attack,victim,faces=(15,2))
    assert isinstance(event,AttackEvent) and event.source_item_uuid == weapon.uuid
    assert actor.action_economy.actions.normalized_score == 0
    if kind == "musket":
        assert event.damages[0].damage_dice == 12
        assert not any(isinstance(action,MultiattackAction) for action in actor.registered_actions)
    assert actor.unequip_item(slot) is weapon
    assert actor.drop_item(weapon.uuid) and victim.loot_item(weapon)
    assert victim.equip_item(weapon.uuid,slot)
    assert weapon.owner_uuid == victim.uuid


def test_commander_archmage_retains_spellcasting_and_actual_defenses(game):
    actor = npc(game,"enemy_magister_nine")
    spells = {action.behavior_binding.behavior_id for action in actor.registered_actions if isinstance(action,SpellAction)}
    assert {"spell.fire_bolt","spell.light","spell.shocking_grasp","spell.mage_armor","spell.magic_missile",
        "spell.mirror_image","spell.misty_step","spell.fly","spell.lightning_bolt","spell.banishment",
        "spell.fire_shield","spell.stoneskin","spell.cone_of_cold","spell.wall_of_force",
        "spell.globe_of_invulnerability","spell.invisibility"} <= spells
    assert actor.spell_attack_bonus().normalized_score == 9
    assert actor.skill_bonus(None,"arcana").normalized_score == 13
    assert actor.saving_throw_bonus(None,"wisdom",None).normalized_score == 6
    assert actor.saving_throw_bonus(None,"intelligence",None).normalized_score == 9
    assert actor.action_economy.spell_slot_value(9).normalized_score == 1
    assert actor.health.spell_damage_resistance_sources
    assert actor.health.get_resistance(DamageType.SLASHING,attack_magical=False) is ResistanceStatus.NONE
    assert not actor.get_event_handlers_by_name("Shield")
    assert actor.get_event_handlers_by_name("Counterspell")
    assert actor.ac_bonus().normalized_score == 12  # No free Mage Armor or Stoneskin.
    invis = next(action for action in actor.registered_actions if isinstance(action,Invisibility))
    before = actor.action_economy.spell_slot_value(2).normalized_score
    result = actor.perform(invis,ActionSelection(template_uuid=invis.uuid,target_uuids=(actor.uuid,)))
    assert result is not None and not result.canceled
    assert actor.action_economy.spell_slot_value(2).normalized_score == before
    assert actor.action_economy.actions.normalized_score == 0


def test_commander_counterspell_spends_actual_third_level_slot_and_reaction(game):
    commander = npc(game,"enemy_magister_nine")
    caster = target(game,position=(8,4))
    caster.action_economy.spell_slot_value(1).base = 1
    register_spell(caster,MagicMissile)
    missile = next(action for action in caster.registered_actions if isinstance(action,MagicMissile))
    hp = commander.get_normal_hp()
    with fixed_dice_faces(*([1]*20)):
        event = caster.perform(missile,ActionSelection(template_uuid=missile.uuid,target_uuids=(commander.uuid,)))
    assert event is not None and event.canceled
    assert commander.get_normal_hp() == hp
    assert commander.action_economy.spell_slot_value(3).normalized_score == 2
    assert commander.action_economy.reactions.normalized_score == 0


@pytest.mark.parametrize("key,spell",[
    ("orc_frostmane","spell.web"),("orc_brassbrow","spell.web"),
    ("character_golden_orbit","spell.burning_hands"),("character_azure_current","spell.web"),
    ("character_hex_sovereign","spell.slow"),("barbarian_sun_ring","spell.produce_flame"),
])
def test_native_caster_selections_and_spell_attack_scaling(game,key,spell):
    actor = npc(game,key)
    offered = get_available_actions(actor,legal_only=False)
    assert spell in {action.behavior_id for action in offered.all_actions}
    if key != "barbarian_sun_ring":
        victim = target(game,position=(8,4))
        firebolt = next(action for action in actor.registered_actions if isinstance(action,FireBolt))
        assert firebolt.caster_level == 9
        before = victim.get_normal_hp()
        perform(actor,firebolt,victim,faces=(15,2,2))
        assert before-victim.get_normal_hp() == 4
    if key == "character_hex_sovereign":
        assert "spell.fly" not in {action.behavior_id for action in offered.all_actions}


def test_cinderplate_innate_burning_hands_costs_one_daily_use(game):
    actor = npc(game,"barbarian_cinderplate")
    victim = target(game,position=(6,4))
    spell = next(action for action in actor.registered_actions if isinstance(action,BurningHands))
    resource_name = "innate.spell.burning_hands.1"
    assert actor.action_economy.get_resource_current(resource_name) == 1
    with fixed_dice_faces(1,2,2,2):
        event = actor.perform(spell,ActionSelection(template_uuid=spell.uuid,positions=((6,4),)))
    assert event is not None and not event.canceled
    assert actor.action_economy.get_resource_current(resource_name) == 0
    assert actor.action_economy.actions.normalized_score == 0
    assert victim.get_normal_hp() < victim.get_max_hp()
    assert all(actor.action_economy.spell_slot_value(rank).normalized_score == 0 for rank in range(1,10))


def test_gilded_ward_spends_real_single_slot_for_divine_eminence(game):
    actor = npc(game,"character_gilded_ward")
    action = actor.get_action_template("Divine Eminence")
    assert action is not None and actor.action_economy.spell_slot_value(1).normalized_score == 1
    event = actor.perform(action,ActionSelection(template_uuid=action.uuid))
    assert event is not None and not event.canceled
    assert actor.action_economy.spell_slot_value(1).normalized_score == 0
    assert actor.action_economy.bonus_actions.normalized_score == 0
    assert actor.action_economy.actions.normalized_score == 1


@pytest.mark.parametrize("key,item_id",[
    ("barbarian_farshot","gear.wayfarer_pack"),("barbarian_windmark","gear.ember_quiver"),
    ("enemy_blue_quarrel","gear.warden_pack"),
])
def test_specialist_backpacks_are_real_transferable_possessions(game,key,item_id):
    actor = npc(game,key)
    recipient = target(game)
    backpack = next(item for item in actor.equipment.get_all_equipped_items() if item.item_id == item_id)
    assert backpack.charges == 1
    assert actor.unequip_item(BodyPart.BACKPACK) is backpack
    assert actor.drop_item(backpack.uuid) and recipient.loot_item(backpack)
    assert recipient.equip_item(backpack.uuid,BodyPart.BACKPACK)
    assert backpack.owner_uuid == recipient.uuid and backpack.charges == 1


def test_assassin_supplies_consume_three_to_zero_across_transfer(game):
    assassin = npc(game,"enemy_blue_twinblade")
    recipient = target(game)
    vial = next(item for item in assassin.inventory.items.values()
        if item.item_id == "consumable.weapon_coat.assassin_poison")
    assert vial.stack_count == 3
    result = execute_use_action(assassin,vial.uuid,"Coat Main Hand")
    assert result is not None and not result.canceled and vial.stack_count == 2
    assert assassin.drop_item(vial.uuid) and recipient.loot_item(vial)
    weapon = assassin.unequip_item(WeaponSlot.MELEE_MAIN)
    assert weapon is not None and assassin.drop_item(weapon.uuid) and recipient.loot_item(weapon)
    assert recipient.equip_item(weapon.uuid,WeaponSlot.MELEE_MAIN)
    assert vial.owner_uuid == recipient.uuid
    for remaining in (1,0):
        recipient.on_turn_start()
        result = execute_use_action(recipient,vial.uuid,"Coat Main Hand")
        assert result is not None and not result.canceled
        assert recipient.action_economy.actions.normalized_score == 0
        if remaining:
            assert vial.stack_count == remaining and recipient.inventory.has_item(vial.uuid)
        else:
            assert not recipient.inventory.has_item(vial.uuid) and vial.charges == 0


def test_gateplate_protection_competes_with_parry_for_one_reaction(game):
    defender = npc(game,"enemy_gateplate")
    ally = npc(game,"enemy_dockwall",position=(4,5))
    attacker = target(game,position=(5,4))
    template = next(action for action in attacker.registered_actions
        if isinstance(action,Attack) and action.weapon_slot is WeaponSlot.MELEE_MAIN)
    first = perform(attacker,template,ally,faces=(15,5,1))
    assert isinstance(first,AttackEvent) and first.dice_roll.advantage_status is AdvantageStatus.DISADVANTAGE
    assert defender.action_economy.reactions.normalized_score == 0
    attacker.on_turn_start()
    second = perform(attacker,template,defender,faces=(20,1,1))
    assert isinstance(second,AttackEvent) and defender.action_economy.reactions.normalized_score == 0


@pytest.mark.parametrize("key",["enemy_gateplate","character_violet_oathbreaker"])
def test_authored_shield_substitution_is_one_of_three_actual_attacks(game,key):
    actor = npc(game,key)
    victim = target(game)
    multi = next(action for action in actor.registered_actions if isinstance(action,MultiattackAction))
    shield = actor.equipment.get_equipped_shield()
    before = EventQueue.event_cursor()
    # Natural ones keep later variable item packets irrelevant; the first attack
    # hits and tests the authored real-shield damage/save before two normal misses.
    with fixed_dice_faces(15,1,1,*([1]*30)):
        event = actor.perform(multi,ActionSelection(template_uuid=multi.uuid,target_uuids=(victim.uuid,),
            facets=(ActionVariantFacet(key="form",value="substitution",label="Shield Bash"),)))
    assert event is not None and not event.canceled
    attacks = [row for _,row in EventQueue.iter_events_since(before)
        if isinstance(row,AttackEvent) and row.phase is EventPhase.COMPLETION]
    assert len(attacks) == 3
    bash = attacks[0]
    assert shield is not None and bash.source_item_uuid == shield.uuid
    assert len(bash.damages) == 1 and bash.damages[0].dice_numbers == 2 and bash.damages[0].damage_dice == 4
    assert bash.damage_rolls[0].total == 6 and "Prone" in victim.active_conditions
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.bonus_actions.normalized_score == 1


def test_witchdoctor_uses_selected_silver_sword_and_two_basic_poison_doses(game):
    actor = npc(game,"barbarian_venom_ritualist")
    sword = actor.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    assert sword is not None and sword.item_id == "weapon.roster.silver_longsword"
    assert "silvered" in sword.tags and not sword.is_magical
    vial = next(item for item in actor.inventory.items.values()
        if item.item_id == "consumable.weapon_coat.basic_poison")
    assert vial.stack_count == 2
    event = execute_use_action(actor,vial.uuid,"Coat Main Hand")
    assert event is not None and not event.canceled and vial.stack_count == 1
    assert actor.action_economy.actions.normalized_score == 0


def test_storm_arrow_and_old_custom_signatures_are_absent(game):
    actor = npc(game,"character_blue_spark")
    assert Counter(item.item_id for item in actor.equipment.get_all_equipped_items()) == Counter({
        "weapon.longbow":1,"gear.quiver":1,"armor.half_plate":1})
    assert not any("storm" in action.behavior_binding.behavior_id for action in actor.registered_actions)
