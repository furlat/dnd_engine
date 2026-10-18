"""Admitted undead recipes materialize real kits and execute native commands."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.actions import Attack, AttackEvent
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.health import HealthConfig
from dnd.blocks.spellcasting import SpellcastingSource
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.action_types import ActionSelection, ActionVariantFacet
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.dice import fixed_dice_faces
from dnd.core.effect_types import EffectOrigin, EffectOriginKind
from dnd.core.equipment_types import WeaponSlot
from dnd.core.modifiers import ResistanceStatus
from dnd.core.progression import CasterProgression
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import MultiattackAction, NaturalAttack, WightLifeDrain
from dnd.monsters.undead_roster import UNDEAD_ROSTER_RECIPES_BY_ID
from dnd.monsters.zombie_roster import ZOMBIE_ROSTER_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import BurningHands, FireBolt
from dnd.spells.transmutation import EnlargeReduceEffect
from dnd.types.senses import SensesType
from tests.manual.spell_regression_support import force_save_result


HEAVY = {"zombie_hd_hulk_1", "zombie_hd_hulk_2", "zombie_hd_monster_3"}
CRAWLERS = {"zombie_top_decay_01", "zombie_top_decay_04"}
ATHLETICS = {"zombie_hd_female_5", "zombie_hd_male_9", "zombie_top_09", "zombie_top_decay_05", "zombie_top_swamp_05"}
BLADES = {"zombie_top_swamp_01", "zombie_top_swamp_09"}
UNDEAD_FACTS = (
    ("undead_bonewheel",112,12,3), ("undead_ash_crown",45,20,2),
    ("undead_flareblade",45,19,2), ("undead_red_crescent",67,11,0),
    ("undead_pikeward",45,14,2), ("undead_black_fletch",45,12,2),
    ("undead_ossuary_hierophant",99,12,0), ("undead_ember_oracle",40,12,0),
)


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(10,8))
    result=Game()
    yield result
    result.close()
    reset_engine_runtime()


def summon(game,key,mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS):
    recipe={**ZOMBIE_ROSTER_RECIPES_BY_ID,**UNDEAD_ROSTER_RECIPES_BY_ID}[key]
    entity=materialize_creature(recipe,runtime_entity_uuid=uuid4(),display_name=key,
        faction="undead",position=(2,2),deployment_role=CreatureDeploymentRole(role_id="tests.npc_roster"),
        possession_mode=mode)
    entity.compose_entity()
    game.deploy_entity(entity,entity.position)
    return entity


def victim(game,position=(3,2)):
    entity=Entity.create(uuid4(),"Target",config=EntityConfig(faction="living",
        health=HealthConfig(max_hit_points_bonus=500)))
    entity.compose_entity()
    setup_standard_actions(entity)
    game.deploy_entity(entity,position)
    Entity.update_all_entities_senses()
    return entity


def perform(actor,template,*,target=None,position=None):
    return actor.perform(template,ActionSelection(template_uuid=template.uuid,
        target_uuids=(target.uuid,) if target else (),positions=(position,) if position else ()))


@pytest.mark.parametrize("key",tuple(ZOMBIE_ROSTER_RECIPES_BY_ID))
@pytest.mark.parametrize("mode",tuple(CreaturePossessionMode))
def test_all_46_zombie_kits_materialize_with_exact_bodies_and_real_possessions(game,key,mode):
    actor=summon(game,key,mode)
    assert actor.creature_type is CreatureType.UNDEAD
    assert actor.get_max_hp()==(85 if key in HEAVY else 22)
    assert actor.ac_bonus().normalized_score==8
    assert actor.size is (Size.LARGE if key in HEAVY else Size.MEDIUM)
    assert actor.action_economy.current_speed()==(30 if key in HEAVY else 15 if key in CRAWLERS else 20)
    assert actor.health.get_resistance(DamageType.POISON) is ResistanceStatus.IMMUNITY
    assert any(sense.sense_type is SensesType.DARKVISION and sense.range_feet==60 for sense in actor.senses.sense_modes)
    assert "Undead Fortitude" in actor.active_conditions
    assert actor.skill_set.athletics.proficiency == (key in ATHLETICS)
    equipped=actor.equipment.get_all_equipped_items()
    if key in BLADES and mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS:
        assert len(equipped)==(2 if key.endswith("09") else 1)
        assert all(item.is_pickable and item.intrinsic_owner_uuid is None for item in equipped)
    else:
        assert not equipped
    # Source palettes add no spells, bonus damage, or special maneuver action.
    assert not any(isinstance(action,(BurningHands,MultiattackAction)) for action in actor.registered_actions)


@pytest.mark.parametrize("key",tuple(ZOMBIE_ROSTER_RECIPES_BY_ID))
def test_every_zombie_executes_its_real_slam_with_one_action(game,key):
    actor=summon(game,key)
    target=victim(game)
    slam=next(action for action in actor.registered_actions if isinstance(action,NaturalAttack) and action.name=="Slam")
    hp=target.get_normal_hp()
    with fixed_dice_faces(15,3,3):
        result=perform(actor,slam,target=target)
    assert isinstance(result,AttackEvent) and not result.canceled
    assert target.get_normal_hp()==hp-(10 if key in HEAVY else 4)
    assert actor.action_economy.actions.normalized_score==0
    assert result.source_item_uuid is None
    assert {packet.damage_type for packet in result.damages}=={DamageType.BLUDGEONING}


@pytest.mark.parametrize("key,hp,ac,attacks",UNDEAD_FACTS)
@pytest.mark.parametrize("mode",tuple(CreaturePossessionMode))
def test_all_eight_champions_preserve_selected_stats_and_optional_gear(game,key,hp,ac,attacks,mode):
    actor=summon(game,key,mode)
    assert actor.creature_type is CreatureType.UNDEAD
    assert actor.get_max_hp()==hp
    assert actor.ac_bonus().normalized_score==(ac if mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS else
        11 if key=="undead_red_crescent" else 12)
    multis=[action for action in actor.registered_actions if isinstance(action,MultiattackAction)]
    assert len(multis)==(1 if attacks else 0)
    assert actor.health.get_resistance(DamageType.POISON) is ResistanceStatus.IMMUNITY
    wight=key in {"undead_ash_crown","undead_flareblade","undead_pikeward","undead_black_fletch"}
    assert any(sense.sense_type is SensesType.DARKVISION for sense in actor.senses.sense_modes)==wight
    assert actor.check_condition_immunity("Poisoned") and actor.check_condition_immunity("Exhaustion")
    if mode is CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY:
        assert not actor.equipment.get_all_equipped_items()
    if key=="undead_black_fletch" and mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS:
        assert actor.equipment.get_weapon(WeaponSlot.RANGED_MAIN).item_id=="weapon.shortbow"
        assert actor.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is None


def test_bonewheel_uses_three_ordinary_brute_greatsword_hits_and_held_weapon_parry(game):
    actor=summon(game,"undead_bonewheel")
    target=victim(game)
    action=next(action for action in actor.registered_actions if isinstance(action,MultiattackAction))
    hp=target.get_normal_hp()
    with fixed_dice_faces(*([15,2,2,2]*3)):
        result=perform(actor,action,target=target)
    assert result is not None and not result.canceled
    assert target.get_normal_hp()==hp-30  # Each Greatsword is 3d6+4 after Brute.
    assert actor.action_economy.actions.normalized_score==0
    assert actor.get_event_handlers_by_name("Parry")


@pytest.mark.parametrize("key",("undead_ash_crown","undead_flareblade","undead_pikeward"))
def test_wight_melee_can_replace_one_selected_weapon_attack_with_life_drain(game,key):
    actor=summon(game,key)
    target=victim(game)
    force_save_result(target,"constitution",succeeds=False)
    action=next(action for action in actor.registered_actions if isinstance(action,MultiattackAction))
    before=target.get_max_hp()
    # One Life Drain (1d6+2), then one equipped hit; Ember has 2d6 fire.
    with fixed_dice_faces(15,2,15,2,2,2):
        result=actor.perform(action,ActionSelection(template_uuid=action.uuid,
            target_uuids=(target.uuid,),facets=(ActionVariantFacet(
                key="form",value="substitution",label="Life Drain"),)))
    assert result is not None and not result.canceled
    assert target.get_max_hp()==before-4
    assert actor.action_economy.actions.normalized_score==0


def test_dark_archer_does_not_put_life_drain_on_arrows(game):
    actor=summon(game,"undead_black_fletch")
    target=victim(game,(6,2))
    before=target.get_max_hp()
    multi=next(action for action in actor.registered_actions if isinstance(action,MultiattackAction))
    with fixed_dice_faces(15,2,15,2):
        result=perform(actor,multi,target=target)
    assert result is not None and not result.canceled
    assert target.get_max_hp()==before
    assert any(isinstance(action,WightLifeDrain) for action in actor.registered_actions)


def test_ravager_innate_burning_hands_has_actual_cha_source_and_daily_use(game):
    actor=summon(game,"undead_red_crescent")
    target=victim(game)
    force_save_result(target,"dexterity",succeeds=False)
    spell=next(action for action in actor.registered_actions if isinstance(action,BurningHands))
    source=actor.spellcasting.sources[spell.spellcasting_source_id]
    assert source.provider_id=="creature.undead_red_crescent" and source.ability=="charisma"
    assert not actor.action_economy.spell_slot_1.normalized_score
    hp=target.get_normal_hp()
    with fixed_dice_faces(10,3,3,3):
        result=perform(actor,spell,position=target.position)
    assert result is not None and not result.canceled
    assert target.get_normal_hp()==hp-9
    actor.on_turn_start()
    exhausted=perform(actor,spell,position=target.position)
    assert exhausted is None or exhausted.canceled
    actor.on_long_rest()
    with fixed_dice_faces(10,3,3,3):
        recovered=perform(actor,spell,position=target.position)
    assert recovered is not None and not recovered.canceled


def test_necromancer_is_actual_archmage_with_both_defenses_and_owned_native_spells(game):
    actor=summon(game,"undead_ossuary_hierophant")
    target=victim(game,(6,2))
    assert actor.skill_bonus(None,"arcana").normalized_score==13
    assert actor.skill_bonus(None,"history").normalized_score==13
    assert len(actor.creature_proficiencies.language_sources)==6
    assert {"Magic Resistance","Spell Damage Resistance"}<=actor.active_conditions.keys()
    hp=actor.get_normal_hp()
    actor.receive_damage(10,DamageType.FIRE,target.uuid,effect_origin=EffectOrigin(kind=EffectOriginKind.SPELL))
    actor.receive_damage(10,DamageType.FIRE,target.uuid,effect_origin=EffectOrigin(kind=EffectOriginKind.ACTION,magical=True))
    assert actor.get_normal_hp()==hp-15
    firebolt=next(action for action in actor.registered_actions if isinstance(action,FireBolt))
    target_hp=target.get_normal_hp()
    with fixed_dice_faces(15,2,2,2,2):
        result=perform(actor,firebolt,target=target)
    assert result is not None and not result.canceled
    assert target.get_normal_hp()==target_hp-8
    assert not any(action.name=="Shield" for action in actor.registered_actions)


def test_heavy_zombie_slam_includes_native_size_and_enlarge_adds_only_growth(game):
    actor=summon(game,"zombie_hd_hulk_1")
    target=victim(game)
    slam=next(action for action in actor.registered_actions if isinstance(action,NaturalAttack))
    baseline=slam.get_outcome_profile()
    assert [(row.dice_count,row.die_size,row.flat_bonus) for row in baseline.damage_rolls]==[(2,8,4)]
    actor.add_condition(EnlargeReduceEffect(source_entity_uuid=actor.uuid,target_entity_uuid=actor.uuid,mode="enlarge"))
    enlarged=slam.get_outcome_profile()
    assert [(row.dice_count,row.die_size,row.flat_bonus) for row in enlarged.damage_rolls]==[(2,8,4),(1,4,0)]
    hp=target.get_normal_hp()
    with fixed_dice_faces(15,3,3,2):
        result=perform(actor,slam,target=target)
    assert result is not None and not result.canceled
    assert target.get_normal_hp()==hp-12


def test_authored_innate_source_accepts_creature_identity_and_keeps_slot_rules():
    fields=dict(source_kind="innate",source_id=uuid4(),ability="charisma",provider_level=1,maximum_spell_rank=1)
    source=SpellcastingSource(provider_id="creature.undead_red_crescent",**fields)
    assert source.source_kind=="innate" and source.caster_progression is None
    with pytest.raises(ValidationError,match="authored creature"):
        SpellcastingSource(provider_id="item.fake_caster",**fields)
    with pytest.raises(ValidationError,match="cannot contribute shared slots"):
        SpellcastingSource(provider_id="creature.undead_red_crescent",caster_progression=CasterProgression.FULL_CASTER,**fields)
