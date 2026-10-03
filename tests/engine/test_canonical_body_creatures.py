"""Ordinary creature recipes and anatomical Attack contracts, without summoning."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions import Attack, Move
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.health import HealthConfig
from dnd.classes.fighter import ActionSurge, ActionSurgeFeature, ExtraAttackFeature
from dnd.content.items.authored_item_definitions import AUTHORED_WEAPON_DEFINITIONS
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.dice import fixed_dice_faces
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import WeaponSlot, WeaponUsage
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.beasts import BEAST_RECIPES_BY_ID
from dnd.monsters.demon_variants import CORROSIVE_DEMON_RECIPE, DREAD_DEMON_RECIPE
from dnd.monsters.fiends import FIEND_RECIPES_BY_ID
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.monsters.traits import MultiattackAction
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.transmutation import EnlargeReduceEffect, HasteEffect, SlowedEffect
from dnd.types.physical_access import PhysicalAccess
from dnd.types.world import MovementMode


RECIPES = {**BEAST_RECIPES_BY_ID, **FIEND_RECIPES_BY_ID,
    "wolf": SRD_CREATURE_RECIPES_BY_ID["wolf"], "dretch": SRD_CREATURE_RECIPES_BY_ID["dretch"],
    "corrosive_demon": CORROSIVE_DEMON_RECIPE, "dread_demon": DREAD_DEMON_RECIPE}
EXPECTED = {
    "hound": (5,12,40), "boar": (11,11,40), "stag": (13,10,50), "jaguar": (13,12,50),
    "bison": (19,11,40), "ostrich": (19,11,50), "brown_bear": (34,11,40), "lion": (26,12,50),
    "tiger": (37,12,40), "polar_bear": (42,12,40), "rhinoceros": (45,11,40), "blue_raptor": (51,13,60),
    "stegosaurus": (68,15,30), "elephant": (76,12,40), "triceratops": (95,13,50),
    "mammoth": (126,13,40), "raptor": (51,13,60), "claw_mote_devil": (7,11,25),
    "huntsman_wing_devil": (93,16,30), "fellwing_devil": (136,16,30),
}


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(8,8))
    get_map().create_rectangle(0,0,8,8)
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(8,8))


def creature(game, key, mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS):
    owner = materialize_creature(RECIPES[key], runtime_entity_uuid=uuid4(), display_name=key,
        faction="beasts", position=(5,5), deployment_role=CreatureDeploymentRole(role_id="test.ordinary"),
        possession_mode=mode)
    owner.compose_entity()
    game.deploy_entity(owner, (5,5))
    return owner


def target(game):
    actor = Entity.create(uuid4(), "Target", config=EntityConfig(faction="targets",
        health=HealthConfig(max_hit_points_bonus=1000)))
    actor.compose_entity()
    game.deploy_entity(actor, (6,5))
    setup_standard_actions(actor)
    Entity.update_all_entities_senses()
    return actor


def execute(owner, target_entity, name):
    available = get_available_actions(owner, legal_only=True)
    row = next(row for row in available.all_actions if row.template_name == name)
    chosen = next(value for value in row.valid_targets if value.target_uuid == target_entity.uuid)
    result = execute_by_index(owner, row.template_name, chosen.index, available=available)
    assert result is not None and not result.canceled
    return result


@pytest.mark.parametrize("mode", list(CreaturePossessionMode))
@pytest.mark.parametrize("key", tuple(RECIPES))
def test_all_24_canonical_creatures_are_independent_and_keep_intrinsics(game, key, mode):
    owner = creature(game, key, mode)
    assert owner.content_ref == RECIPES[key].ref
    assert not any(name.startswith("Summon") for name in owner.active_conditions)
    if key in EXPECTED:
        assert (owner.get_hp(), owner.ac_bonus().normalized_score, owner.action_economy.current_speed()) == EXPECTED[key]
    for item in owner.equipment.get_all_equipped_items():
        assert item.intrinsic_owner_uuid == owner.uuid
        assert not item.is_pickable
        assert not owner.drop_item(item.uuid)
    for slot in (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF):
        weapon = owner.equipment.get_weapon(slot)
        if weapon is None:
            continue
        assert owner.get_weapon_physical_access(slot) is PhysicalAccess.NATURAL
        assert weapon.is_body_attack
        assert [(cost.cost_type,cost.cost) for cost in owner.get_action_template(f"Attack_{slot.value}").costs] == [("actions",1)]


@pytest.mark.parametrize("key", ("jaguar", "brown_bear", "polar_bear", "raptor", "fellwing_devil", "dretch"))
@pytest.mark.parametrize("slot", (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF))
def test_each_body_attack_matches_ai_formula_and_spends_an_action(game, key, slot):
    owner = creature(game,key); victim = target(game)
    weapon = owner.equipment.get_weapon(slot)
    assert weapon is not None
    action = Attack(source_entity_uuid=owner.uuid, target_entity_uuid=victim.uuid, weapon_slot=slot)
    profile = action.get_outcome_profile(owner)
    assert profile is not None
    assert profile.damage_rolls[0].flat_bonus == owner.ability_scores.strength.modifier
    before = victim.get_hp()
    with fixed_dice_faces(15, *([2] * 30)):
        result = action.apply()
    assert result is not None and not result.canceled
    assert before - victim.get_hp() == weapon.dice_numbers * 2 + owner.ability_scores.strength.modifier
    assert owner.action_economy.actions.normalized_score == 0
    assert owner.action_economy.bonus_actions.normalized_score == 1
    assert result.attack_source_kind == "equipped"
    assert result.source_item_uuid == weapon.uuid
    assert result.source_item_presentation.item_id == weapon.item_id


@pytest.mark.parametrize("key,count", [("brown_bear",2),("polar_bear",2),("stegosaurus",2),
    ("huntsman_wing_devil",2),("fellwing_devil",3),("dretch",2)])
def test_configured_body_multiattack_is_one_action_with_full_child_damage(game,key,count):
    owner = creature(game,key); victim = target(game)
    template = next(action for action in owner.registered_actions if isinstance(action,MultiattackAction))
    faces = []
    for slot, repetitions in template.attack_sequence:
        weapon = owner.equipment.get_weapon(slot)
        assert weapon is not None
        for _ in range(repetitions):
            faces.extend([15, *([2] * weapon.dice_numbers)])
    with fixed_dice_faces(*faces):
        result = template.instantiate(target_entity_uuid=victim.uuid).apply()
    assert result is not None and not result.canceled
    attacks = [event for event in EventQueue.get_events_by_type(EventType.ATTACK)
        if event.phase is EventPhase.COMPLETION and event.source_entity_uuid == owner.uuid]
    assert len(attacks) == count
    assert all(event.behavior_id == "action.attack" for event in attacks)
    assert all(event.damages[0].damage_bonus.normalized_score == owner.ability_scores.strength.modifier for event in attacks)
    assert owner.action_economy.actions.normalized_score == 0
    assert owner.action_economy.bonus_actions.normalized_score == 1


@pytest.mark.parametrize("slow", [False, True])
@pytest.mark.parametrize("surge", [False, True])
def test_secondary_body_attacks_share_haste_extra_attack_surge_and_slow(game,slow,surge):
    owner = creature(game,"brown_bear"); victim = target(game)
    owner.add_condition(ExtraAttackFeature(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid,extra_attacks=1))
    owner.add_condition(HasteEffect(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid,
        caster_uuid=owner.uuid,apply_lethargy=False))
    owner.action_economy.resources["extra_attacks"].current = 0
    if surge:
        owner.add_condition(ActionSurgeFeature(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid))
        result = ActionSurge(source_entity_uuid=owner.uuid).apply()
        assert result is not None and not result.canceled
    if slow:
        owner.add_condition(SlowedEffect(source_entity_uuid=victim.uuid,target_entity_uuid=owner.uuid,
            caster_uuid=victim.uuid,spell_dc=0))
    names = {row.template_name for row in get_available_actions(owner,legal_only=True).all_actions}
    assert "Attack_MELEE_OFF__grant_haste" in names
    assert not any("Multiattack" in name and "__grant_haste" in name for name in names)
    with fixed_dice_faces(*([15,2] * 40)):
        execute(owner,victim,"Attack_MELEE_OFF")
        assert owner.action_economy.resources["extra_attacks"].current == (0 if slow else 1)
        if not slow:
            execute(owner,victim,"Extra Attack_MELEE_OFF")
        execute(owner,victim,"Attack_MELEE_OFF__grant_haste")
        assert owner.action_economy.resources["extra_attacks"].current == 0
        if surge:
            execute(owner,victim,"Attack_MELEE_OFF")
    # Slow itself prevents taking the bonus action after taking an action.
    assert owner.action_economy.bonus_actions.normalized_score == (0 if slow else 1)


def test_body_usage_cannot_be_claimed_by_ordinary_transferable_gear():
    with pytest.raises(ValueError, match="intrinsic natural"):
        replace(AUTHORED_WEAPON_DEFINITIONS["weapon.dagger"], usage=WeaponUsage.BODY)


@pytest.mark.parametrize("key,speed", [("huntsman_wing_devil",40),("fellwing_devil",50)])
def test_authored_wings_grant_supported_flight_only(game,key,speed):
    owner = creature(game,key)
    assert owner.action_economy.current_speed(MovementMode.FLYING) == speed
    assert owner.action_economy.current_speed() == 30
    assert "Concentrating" not in owner.active_conditions


def test_knockdown_uses_item_identity_even_when_display_names_change(game):
    owner = creature(game,"jaguar"); victim = target(game)
    claws = owner.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    bite = owner.equipment.get_weapon(WeaponSlot.MELEE_OFF)
    claws.name = "Renamed talons"
    bite.name = "Claws"
    # Matching the old display name cannot put the Claw rider on Bite.
    bite_attack = Attack(source_entity_uuid=owner.uuid,target_entity_uuid=victim.uuid,weapon_slot=WeaponSlot.MELEE_OFF)
    assert bite_attack.get_target_effect_profile(owner) is None
    with fixed_dice_faces(15,2,1):
        result = bite_attack.apply()
    assert result is not None and not result.canceled
    assert "Prone" not in victim.active_conditions
    owner.action_economy.reset_all_costs()
    claw_attack = Attack(source_entity_uuid=owner.uuid,target_entity_uuid=victim.uuid,weapon_slot=WeaponSlot.MELEE_MAIN)
    with fixed_dice_faces(15,2,1):
        result = claw_attack.apply()
    assert result is not None and not result.canceled
    assert "Prone" in victim.active_conditions


def test_large_body_dice_already_include_natural_size_and_enlarge_adds_only_the_change(game):
    owner = creature(game,"mammoth"); victim = target(game)
    before_profile = Attack(source_entity_uuid=owner.uuid,target_entity_uuid=victim.uuid,weapon_slot=WeaponSlot.MELEE_MAIN).get_outcome_profile(owner)
    assert before_profile is not None
    assert [(row.dice_count,row.die_size,row.flat_bonus) for row in before_profile.damage_rolls] == [(4,8,7)]
    owner.add_condition(EnlargeReduceEffect(source_entity_uuid=owner.uuid,target_entity_uuid=owner.uuid,mode="enlarge"))
    attack = Attack(source_entity_uuid=owner.uuid,target_entity_uuid=victim.uuid,weapon_slot=WeaponSlot.MELEE_MAIN)
    profile = attack.get_outcome_profile(owner)
    assert profile is not None
    assert [(row.dice_count,row.die_size,row.flat_bonus) for row in profile.damage_rolls] == [(4,8,7),(1,4,0)]
    before = victim.get_hp()
    with fixed_dice_faces(15,2,2,2,2,2,20):
        result = attack.apply()
    assert result is not None and not result.canceled
    assert before - victim.get_hp() == 17


def test_body_opportunity_attack_uses_primary_and_one_reaction(game):
    owner = creature(game,"brown_bear"); victim = target(game)
    add_opportunity_attack_handler(owner)
    before = victim.get_hp()
    with fixed_dice_faces(15,2,2):
        result = Move(source_entity_uuid=victim.uuid,end_position=(7,5)).apply()
    assert result is not None and not result.canceled
    assert victim.position == (7,5)
    assert before - victim.get_hp() == 8
    attacks = [event for event in EventQueue.get_events_by_type(EventType.ATTACK)
        if event.phase is EventPhase.COMPLETION and event.source_entity_uuid == owner.uuid]
    assert len(attacks) == 1
    assert attacks[0].weapon_slot is WeaponSlot.MELEE_MAIN
    assert attacks[0].source_item_presentation.item_id == "weapon.creature.brown_bear_claws"
    assert owner.action_economy.reactions.normalized_score == 0
    assert owner.action_economy.actions.normalized_score == 1
    assert owner.action_economy.bonus_actions.normalized_score == 1


@pytest.mark.parametrize("key", tuple(RECIPES))
def test_canonical_body_injury_uses_one_authored_blood_response(game, key):
    owner = creature(game, key)
    cursor = EventQueue.event_cursor()
    owner.receive_damage(1, DamageType.SLASHING, owner.uuid)
    injury, = (event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION)
    expected = {"corrosive_demon": "body.corrosive_blood", "dread_demon": "body.dread_blood"}.get(key, "body.blood")
    assert injury.body_release is not None and injury.body_release.release_id == expected
    assert injury.body_release.deposited_position == owner.position
    tile = get_map().get_tile(*owner.position)
    assert tile is not None and len(tile.to_world_tile_state().residues) == 1
