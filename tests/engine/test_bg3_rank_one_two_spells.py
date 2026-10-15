"""Native paid-cast outcomes and interactions for the approved 36-spell batch.

Boundary: deployed entities, real action/slot/turn APIs and public spell discovery.
Inputs: selected spells/recipients with deterministic dice and authored immunity.
Outputs: HP/life states, paid resources, legal targets and exact retained effects.
"""
from uuid import uuid4

from dnd.spells.abjuration import AntimagicField
from dnd.spells.illusion import Silence
from dnd.spells.abjuration import register_counterspell_reaction
import pytest

from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.life_types import LifeState
from dnd.entity import Entity, EntityConfig
from dnd.spells.enchantment import AnimalFriendship, ViciousMockery
from dnd.spells.evocation import FireBolt, MagicMissile
from dnd.spells.necromancy import RayOfSickness, SpareTheDying
from tests.engine.test_roster_support_spells import game
from tests.manual.spell_regression_support import force_save_result

from dnd.core.base_block import LightLevel
from dnd.core.gridmap import get_map
from dnd.spells.evocation import StarryWisp
from dnd.spells.evocation import SorcerousBurst
from dnd.core.modifiers import AdvantageStatus
from dnd.spells.enchantment import DissonantWhispers
from dnd.spells.enchantment import DissonantFearEffect, Heroism
from dnd.spells.enchantment import Heroism
from dnd.spells.enchantment import HideousLaughter
from dnd.conditions import Charmed
from dnd.spells.abjuration import ProtectionFromEvilAndGood
from dnd.spells.evocation import FaerieFire
from dnd.blocks.action_economy import RechargeType
from dnd.classes.rage import Rage
from dnd.spells.enchantment import CalmEmotions, DissonantFearEffect
from dnd.spells.abjuration import PassWithoutTrace

def combatant(game, name="Caster", position=(2,2), faction="heroes", *, intelligence=18,
              creature_type=CreatureType.HUMANOID, slots=None):
    actor=Entity.create(uuid4(),name,config=EntityConfig(faction=faction,
        creature_type=creature_type,
        ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=intelligence)),
        health=HealthConfig(max_hit_points_bonus=200),
        action_economy=ActionEconomyConfig(spell_slots=slots or {1:4,2:3,3:3}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence")))
    actor.compose_entity()
    game.deploy_entity(actor,position)
    setup_standard_actions(actor)
    Entity.update_all_entities_senses()
    return actor


def paid(spell,caster,target,**kw):
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result=spell(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,**kw).apply()
    assert result is not None
    canceled = result.canceled
    assert not canceled,result.status_message
    assert caster.action_economy.actions.normalized_score==0
    return result


@pytest.mark.parametrize("stable",[False,True])
def test_spare_dying_stabilizes_without_healing_and_damage_resumes_dying(game,stable):
    caster=combatant(game)
    target=combatant(game,"Dying",(3,2))
    target.uses_death_saves=True
    target.receive_damage(target.get_hp(),DamageType.FORCE,caster.uuid)
    if stable: target.stabilize()
    target.death_save_failures=2
    paid(SpareTheDying,caster,target)
    assert target.health.life_state is LifeState.STABLE
    assert target.get_normal_hp()==0 and target.death_save_failures==0
    target.receive_damage(1,DamageType.FORCE,caster.uuid)
    assert target.health.life_state is LifeState.DYING


@pytest.mark.parametrize("creature_type,dying",[(CreatureType.HUMANOID,False),(CreatureType.UNDEAD,True),(CreatureType.CONSTRUCT,True)])
def test_spare_dying_rejects_ineligible_before_action_payment(game,creature_type,dying):
    caster=combatant(game)
    target=combatant(game,"Recipient",(3,2),creature_type=creature_type)
    if dying:
        target.uses_death_saves=True
        target.receive_damage(target.get_hp(),DamageType.FORCE,caster.uuid)
    result=SpareTheDying(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score==1


@pytest.mark.parametrize("saved",[False,True])
@pytest.mark.parametrize("level,dice",[(1,1),(5,2),(11,3),(17,4)])
def test_mockery_save_and_cantrip_scaling(game,saved,level,dice):
    caster=combatant(game)
    target=combatant(game,"Enemy",(4,2),"foes")
    force_save_result(target,"wisdom",succeeds=saved)
    hp=target.get_hp()
    with fixed_dice_faces(8,*([3]*dice)):
        paid(ViciousMockery,caster,target,caster_level=level)
    assert target.get_hp()==hp-(0 if saved else 3*dice)
    assert ("Vicious Mockery" in set(target.active_conditions)) is (not saved)


def test_mockery_is_spent_by_first_missed_spell_attack_not_automatic_spell(game):
    caster=combatant(game)
    target=combatant(game,"Enemy",(4,2),"foes")
    force_save_result(target,"wisdom",succeeds=False)
    with fixed_dice_faces(8,2): paid(ViciousMockery,caster,target)
    target.on_turn_start()
    with fixed_dice_faces(2,2,2): paid(MagicMissile,target,caster)
    assert "Vicious Mockery" in set(target.active_conditions)
    with fixed_dice_faces(20,1):
        result=paid(FireBolt,target,caster)
    assert result.attack_outcome is AttackOutcome.CRIT_MISS
    assert "Vicious Mockery" not in set(target.active_conditions)
    hp=caster.get_hp()
    with fixed_dice_faces(15,4): paid(FireBolt,target,caster)
    assert caster.get_hp()==hp-4


@pytest.mark.parametrize("intelligence,eligible",[(3,True),(4,False)])
def test_animal_friendship_beast_int_boundary_and_damage_break(game,intelligence,eligible):
    caster=combatant(game)
    beast=combatant(game,"Beast",(5,2),"foes",intelligence=intelligence,creature_type=CreatureType.BEAST)
    force_save_result(beast,"wisdom",succeeds=False)
    with fixed_dice_faces(8):
        result=AnimalFriendship(source_entity_uuid=caster.uuid,target_entity_uuid=beast.uuid).apply()
    assert result is not None and result.canceled is (not eligible)
    assert caster.action_economy.actions.normalized_score==int(not eligible)
    assert beast.faction=="foes"
    if eligible:
        assert "Animal Friendship" in {condition.get_display_name() for condition in beast.active_conditions_by_uuid.values()}
        outsider=combatant(game,"Other enemy",(6,2),"foes")
        beast.receive_damage(1,DamageType.FORCE,outsider.uuid)
        assert "Animal Friendship" in {condition.get_display_name() for condition in beast.active_conditions_by_uuid.values()}
        beast.receive_damage(1,DamageType.FORCE,caster.uuid)
        assert "Animal Friendship" not in {condition.get_display_name() for condition in beast.active_conditions_by_uuid.values()}


def test_animal_friendship_honors_native_charm_immunity(game):
    caster=combatant(game)
    beast=combatant(game,"Immune",(4,2),"foes",intelligence=3,creature_type=CreatureType.BEAST)
    beast.condition_immunities.append(("Charmed",None))
    force_save_result(beast,"wisdom",succeeds=False)
    with fixed_dice_faces(8): AnimalFriendship(source_entity_uuid=caster.uuid,target_entity_uuid=beast.uuid).apply()
    assert "Animal Friendship" not in {condition.get_display_name() for condition in beast.active_conditions_by_uuid.values()}


@pytest.mark.parametrize("saved",[False,True])
@pytest.mark.parametrize("hit",[False,True])
def test_ray_sickness_paid_attack_and_separate_poison_save(game,saved,hit):
    caster=combatant(game)
    target=combatant(game,"Enemy",(4,2),"foes")
    force_save_result(target,"constitution",succeeds=saved)
    hp=target.get_hp()
    slots=caster.action_economy.spell_slot_1.normalized_score
    with fixed_dice_faces(*([15,3,3,8] if hit else [1])):
        paid(RayOfSickness,caster,target)
    assert target.get_hp()==hp-(6 if hit else 0)
    assert ("Poisoned" in set(target.active_conditions)) is (hit and not saved)
    assert caster.action_economy.spell_slot_1.normalized_score==slots-1


@pytest.mark.parametrize("level,dice",[(1,1),(5,2),(11,3),(17,4)])
def test_wisp_damage_dim_light_and_caster_turn_expiry(game,level,dice):
    caster=combatant(game)
    target=combatant(game,"Enemy",(4,2),"foes")
    hp=target.get_hp()
    with fixed_dice_faces(15,*([3]*dice)): paid(StarryWisp,caster,target,caster_level=level)
    assert target.get_hp()==hp-3*dice
    assert "Starry Wisp" in {c.get_display_name() for c in target.active_conditions_by_uuid.values()}
    target.set_invisible(True)
    assert target.is_invisible is False
    get_map().set_tile_base_light(target.position,LightLevel.DARKNESS)
    observed_light=get_map().get_tile(*target.position).resolved_light_level
    assert observed_light is LightLevel.DIM_LIGHT
    caster.on_turn_start()
    caster.on_turn_end()
    assert "Starry Wisp" not in {c.get_display_name() for c in target.active_conditions_by_uuid.values()}
    assert target.is_invisible is True


@pytest.mark.parametrize("element",['acid','cold','fire','lightning','poison','psychic','thunder'])
def test_burst_elements_and_bounded_explosion(game,element):
    caster=combatant(game)
    target=combatant(game,"Enemy",(4,2),"foes")
    hp=target.get_hp()
    with fixed_dice_faces(15,8,8,8,8,8): paid(SorcerousBurst,caster,target,element=element)
    assert target.get_hp()==hp-40


@pytest.mark.parametrize("saved",[False,True])
def test_dissonant_damage_and_persistent_fear_outside_sight(game,saved):
    caster=combatant(game)
    target=combatant(game,"Enemy",(4,2),"foes")
    force_save_result(target,"wisdom",succeeds=saved)
    hp=target.get_hp()
    with fixed_dice_faces(8,3,3,3): paid(DissonantWhispers,caster,target)
    assert target.get_hp()==hp-(4 if saved else 9)
    assert ("Dissonant Whispers Fear" in set(target.active_conditions)) is (not saved)
    if not saved:
        caster.move((15,6))
        assert target.action_economy.current_speed()==0
        assert target.ability_check_bonus(None,"strength").advantage is AdvantageStatus.DISADVANTAGE
        target.on_turn_start(); target.on_turn_end()
        target.on_turn_start(); target.on_turn_end()
        assert "Dissonant Whispers Fear" not in set(target.active_conditions)
        assert target.action_economy.current_speed()>0


def test_heroism_removes_fear_refreshes_owned_hp_and_blocks_reapplication(game):
    caster=combatant(game)
    ally=combatant(game,"Ally",(3,2))
    enemy=combatant(game,"Enemy",(5,2),"foes")
    ally.add_condition(DissonantFearEffect(source_entity_uuid=enemy.uuid,target_entity_uuid=ally.uuid))
    paid(Heroism,caster,ally)
    assert "Dissonant Whispers Fear" not in set(ally.active_conditions)
    assert ally.health.temporary_hit_points.score==5
    ally.receive_damage(3,DamageType.FORCE,enemy.uuid)
    assert ally.health.temporary_hit_points.score==2
    ally.on_turn_start()
    assert ally.health.temporary_hit_points.score==5
    ally.add_condition(DissonantFearEffect(source_entity_uuid=enemy.uuid,target_entity_uuid=ally.uuid))
    assert "Dissonant Whispers Fear" not in set(ally.active_conditions)
    caster.remove_condition("Concentrating")
    assert "Heroism" not in set(ally.active_conditions)
    assert ally.health.temporary_hit_points.score==0
    assert "Dissonant Whispers Fear" not in set(ally.active_conditions)


def test_heroism_preserves_larger_and_later_independent_temp_hp(game):
    caster=combatant(game)
    caster.health.add_temporary_hit_points(12,caster.uuid,source_id="spell.false_life")
    paid(Heroism,caster,caster)
    caster.on_turn_start()
    assert caster.health.temporary_hit_points.score==12
    caster.remove_condition("Concentrating")
    assert caster.health.temporary_hit_points.score==12


@pytest.mark.parametrize("immunity,applied",[("Charmed",True),("Prone",False)])
def test_laughter_separate_immunity_profile_and_damage_recovery(game,immunity,applied):
    caster=combatant(game)
    target=combatant(game,"Enemy",(4,2),"foes")
    target.condition_immunities.append((immunity,None))
    with fixed_dice_faces(8):
        result=HideousLaughter(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid).apply()
    assert result is not None
    assert ("Hideous Laughter" in set(target.active_conditions)) is applied
    if applied:
        assert target.action_economy.actions.normalized_score==0
        assert target.action_economy.current_speed()==0
        with fixed_dice_faces(20,1): target.receive_damage(1,DamageType.FORCE,caster.uuid)
        assert "Hideous Laughter" not in set(target.active_conditions)
        assert target.action_economy.actions.normalized_score==1


@pytest.mark.parametrize("source_type,removed",[(CreatureType.FEY,True),(CreatureType.HUMANOID,False)])
def test_protection_removes_only_eligible_source_charm_and_prevents_new(game,source_type,removed):
    caster=combatant(game)
    ally=combatant(game,"Ally",(3,2))
    source=combatant(game,"Charmer",(5,2),"foes",creature_type=source_type)
    ally.add_condition(Charmed(source_entity_uuid=source.uuid,target_entity_uuid=ally.uuid))
    paid(ProtectionFromEvilAndGood,caster,ally)
    assert ("Charmed" not in set(ally.active_conditions)) is removed
    if removed:
        ally.add_condition(Charmed(source_entity_uuid=source.uuid,target_entity_uuid=ally.uuid))
        assert "Charmed" not in set(ally.active_conditions)
    caster.remove_condition("Concentrating")
    assert ("Charmed" not in set(ally.active_conditions)) is removed


def test_faerie_fire_cast_time_recipients_reveal_and_concentration_cleanup(game):
    caster=combatant(game)
    enemy=combatant(game,"Enemy",(6,2),"foes")
    force_save_result(enemy,"dexterity",succeeds=False)
    with fixed_dice_faces(8,8):
        result=FaerieFire(source_entity_uuid=caster.uuid,end_position=(6,2)).apply()
    assert result is not None
    assert "Faerie Fire" in {c.get_display_name() for c in enemy.active_conditions_by_uuid.values()}
    enemy.move((16,6))
    assert "Faerie Fire" in {c.get_display_name() for c in enemy.active_conditions_by_uuid.values()}
    late=combatant(game,"Late entrant",(6,2),"foes")
    assert "Faerie Fire" not in {c.get_display_name() for c in late.active_conditions_by_uuid.values()}
    enemy.set_invisible(True)
    assert enemy.is_invisible is False
    caster.remove_condition("Concentrating")
    assert "Faerie Fire" not in {c.get_display_name() for c in enemy.active_conditions_by_uuid.values()}
    assert enemy.is_invisible is True


def test_calm_removes_fear_and_blocks_native_rage_before_payment(game):
    caster=combatant(game)
    target=combatant(game,"Humanoid",(6,2))
    target.action_economy.add_resource("rage",3,RechargeType.LONG_REST)
    target.add_condition(DissonantFearEffect(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid))
    result=CalmEmotions(source_entity_uuid=caster.uuid,end_position=target.position).apply()
    assert result is not None
    assert "Dissonant Whispers Fear" not in set(target.active_conditions)
    action=Rage(source_entity_uuid=target.uuid)
    assert action.validate_requirements_for_discovery() is False
    result=action.apply()
    assert result is not None
    canceled=result.canceled
    assert canceled
    assert target.action_economy.bonus_actions.normalized_score==1


def test_pass_without_trace_following_aura_and_shared_sources(game):
    first=combatant(game)
    second=combatant(game,"Second caster",(3,2))
    ally=combatant(game,"Ally",(6,2))
    enemy=combatant(game,"Enemy",(7,2),"foes")
    baseline=ally.skill_bonus(None,"stealth").normalized_score
    enemy_baseline=enemy.skill_bonus(None,"stealth").normalized_score
    paid(PassWithoutTrace,first,first)
    paid(PassWithoutTrace,second,second)
    assert ally.skill_bonus(None,"stealth").normalized_score==baseline+10
    assert enemy.skill_bonus(None,"stealth").normalized_score==enemy_baseline
    first.remove_condition("Concentrating")
    assert ally.skill_bonus(None,"stealth").normalized_score==baseline+10
    second.move((16,6))
    assert ally.skill_bonus(None,"stealth").normalized_score==baseline
    second.move((3,2))
    assert ally.skill_bonus(None,"stealth").normalized_score==baseline+10
    second.remove_condition("Concentrating")
    assert ally.skill_bonus(None,"stealth").normalized_score==baseline


def test_mockery_deadline_expires_while_suppressed_by_antimagic(game):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(6,2),'foes')
    field_caster=combatant(game,'Field caster',(12,2),'foes',slots={8:1})
    force_save_result(enemy,'wisdom',succeeds=False)
    with fixed_dice_faces(10,2):paid(ViciousMockery,caster,enemy)
    assert 'Vicious Mockery' in set(enemy.active_conditions)
    result=AntimagicField(source_entity_uuid=field_caster.uuid).apply()
    assert result is not None and not result.canceled
    enemy.move((11,2))
    effect=enemy.active_conditions['Vicious Mockery']
    assert not effect.contributions_active()
    enemy.on_turn_end()
    field_caster.remove_condition('Concentrating')
    assert 'Vicious Mockery' not in set(enemy.active_conditions)


def test_heroism_forecast_uses_the_applied_condition_semantic_key(game):
    caster=combatant(game)
    profile=Heroism(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid).get_target_effect_profile(caster)
    paid(Heroism,caster,caster)
    effect=next(row for row in caster.active_conditions_by_uuid.values() if row.get_display_name()=='Heroism')
    assert effect.snapshot_state().semantic_key in profile.branches[0].condition_semantic_keys


@pytest.mark.parametrize('interruption',['silence','counterspell'])
def test_new_spell_obeys_native_cast_interruption_before_damage(game,interruption):
    caster=combatant(game)
    enemy=combatant(game,'Enemy',(6,2),'foes')
    if interruption=='silence':
        result=Silence(source_entity_uuid=enemy.uuid,end_position=caster.position).apply()
        assert result is not None and not result.canceled
    else:
        register_counterspell_reaction(enemy)
    hp=enemy.get_hp()
    with fixed_dice_faces(15,3):result=RayOfSickness(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid).apply()
    assert result is not None and result.canceled
    assert enemy.get_hp()==hp
    assert 'Ray of Sickness' not in set(enemy.active_conditions)
    assert caster.action_economy.actions.normalized_score==0
    assert caster.action_economy.spell_slot_1.normalized_score==3

