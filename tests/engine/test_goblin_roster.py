"""The authored Goblin kits fight and transfer ordinary equipment without summoning."""

from uuid import uuid4

import pytest

from dnd.actions import Attack, AttackEvent
from dnd.actions_functional import setup_standard_actions, get_available_actions
from dnd.blocks.health import HealthConfig
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.equipment_types import BodyPart, WeaponSlot, WeaponKind, WeaponProperty
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue, EventPhase
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.monsters.goblins import GOBLIN_RECIPES_BY_ID
from dnd.monsters.traits import MultiattackAction
from dnd.runtime_reset import reset_engine_runtime


RECIPES = {"goblin": BESTIARY_CREATURE_RECIPES_BY_ID["goblin"], **GOBLIN_RECIPES_BY_ID}
EXPECTED = (
    ("goblin",7,12,30), ("goblin_wispbinder",40,12,30), ("goblin_reedshot",7,12,30),
    ("goblin_buckler_rat",7,15,30), ("goblin_longpoint",7,12,30), ("goblin_ironhide",7,15,30),
    ("goblin_briarling",7,13,30), ("goblin_redcap",40,12,30), ("goblin_quicktail",7,13,30),
    ("goblin_spearline",7,13,30), ("goblin_packtrail",7,14,40), ("goblin_ashhide",7,15,40),
    ("goblin_thornrunner",7,12,30), ("goblin_buckler_hex",7,15,30), ("goblin_gloomplate",27,13,30),
    ("goblin_mossbreaker",7,14,30), ("goblin_gutterknife",7,12,30),
)


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(10,10))
    get_map().create_rectangle(0,0,10,10)
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(10,10))


def goblin(game, key, mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS):
    actor = materialize_creature(RECIPES[key], runtime_entity_uuid=uuid4(), display_name=key,
        faction="goblins", position=(4,4), deployment_role=CreatureDeploymentRole(role_id="test.ordinary"),
        possession_mode=mode)
    actor.compose_entity()
    game.deploy_entity(actor, (4,4))
    return actor


def ordinary(game, position, faction="enemies"):
    actor = Entity.create(uuid4(), "Humanoid", config=EntityConfig(faction=faction,
        health=HealthConfig(max_hit_points_bonus=500)))
    setup_standard_actions(actor)
    actor.compose_entity()
    game.deploy_entity(actor, position)
    return actor


@pytest.mark.parametrize("key,hp,ac,speed", EXPECTED)
@pytest.mark.parametrize("mode", tuple(CreaturePossessionMode))
def test_ordinary_roster_stats_and_optional_manufactured_gear(game,key,hp,ac,speed,mode):
    actor = goblin(game,key,mode)
    assert actor.get_hp() == hp
    assert actor.action_economy.current_speed() == speed
    assert actor.appearance.visual_scale == 1.0
    assert actor.ac_bonus().normalized_score == (ac if mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS else 12)
    gear = actor.equipment.get_all_equipped_items()
    if mode is CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY:
        assert not gear
    else:
        assert gear and all(item.is_pickable and item.intrinsic_owner_uuid is None for item in gear)
    if key in ("goblin_wispbinder","goblin_redcap"):
        spells = {action.behavior_id for action in get_available_actions(actor, legal_only=False).all_actions}
        assert {"spell.web", "spell.fireball", "spell.ice_storm", "spell.cone_of_cold"} <= spells
        assert "spell.misty_step" not in spells


def test_pistol_uses_normal_attack_budget_and_survives_loot(game):
    shooter = goblin(game,"goblin_gutterknife")
    victim = ordinary(game,(7,4))
    recipient = ordinary(game,(4,5),"goblins")
    Entity.update_all_entities_senses()
    weapon = shooter.equipment.get_weapon(WeaponSlot.RANGED_MAIN)
    assert weapon is not None and weapon.weapon_kind is WeaponKind.PISTOL
    assert WeaponProperty.TWO_HANDED not in weapon.properties
    hp = victim.get_hp()
    with fixed_dice_faces(15,4):
        event = Attack(source_entity_uuid=shooter.uuid,target_entity_uuid=victim.uuid,
            weapon_slot=WeaponSlot.RANGED_MAIN).apply()
    assert event is not None and not event.canceled
    assert victim.get_hp() < hp and shooter.action_economy.actions.normalized_score == 0
    assert event.source_item_uuid == weapon.uuid
    assert shooter.unequip_item(WeaponSlot.RANGED_MAIN) is weapon
    assert shooter.drop_item(weapon.uuid) and recipient.loot_item(weapon)
    assert recipient.equip_item(weapon.uuid,WeaponSlot.RANGED_MAIN)
    assert recipient.equipment.get_weapon(WeaponSlot.RANGED_MAIN) is weapon
    assert weapon.item_id == "weapon.pistol" and weapon.visual_item_name == "Musket"


def test_selected_robe_keeps_palette_when_looted_by_modular_character(game):
    owner = goblin(game,"goblin_redcap")
    recipient = ordinary(game,(4,5))
    robe = owner.unequip_item(BodyPart.BODY)
    assert robe is not None and robe.visual_variant_id == "roster.51a81ec5104c"
    assert owner.drop_item(robe.uuid) and recipient.loot_item(robe)
    assert recipient.equip_item(robe.uuid,BodyPart.BODY)
    assert robe.visual_variant_id == "roster.51a81ec5104c"
    assert robe.intrinsic_owner_uuid is None


@pytest.mark.parametrize("key", ("goblin_briarling","goblin_gloomplate"))
def test_two_weapon_multiattack_is_one_action_with_two_owned_weapon_hits(game,key):
    owner = goblin(game,key)
    victim = ordinary(game,(5,4))
    Entity.update_all_entities_senses()
    template = next(action for action in owner.registered_actions if isinstance(action,MultiattackAction))
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([15,3,3]*5)):
        result = template.model_copy(update={"target_entity_uuid":victim.uuid,"template":False}).apply()
    assert result is not None and not result.canceled
    attacks = [e for _,e in EventQueue.iter_events_since(cursor) if isinstance(e,AttackEvent) and e.phase is EventPhase.COMPLETION]
    assert len(attacks)==2
    assert {e.source_item_uuid for e in attacks} == {owner.equipment.get_weapon(slot).uuid for slot in (WeaponSlot.MELEE_MAIN,WeaponSlot.MELEE_OFF)}
    assert owner.action_economy.actions.normalized_score==0


@pytest.mark.parametrize("key", ("goblin_ironhide","goblin_packtrail","goblin_ashhide","goblin_buckler_hex"))
def test_guard_protection_uses_existing_single_reaction_and_requires_shield(game,key):
    guard = goblin(game,key)
    ally = ordinary(game,(4,5),"goblins")
    enemy = ordinary(game,(4,6))
    Entity.update_all_entities_senses()
    first = Attack(source_entity_uuid=enemy.uuid,target_entity_uuid=ally.uuid,weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert first is not None and not first.canceled
    assert guard.action_economy.reactions.normalized_score==0
    guard.action_economy.reset_all_costs()
    enemy.action_economy.reset_all_costs()
    assert guard.unequip_item(WeaponSlot.MELEE_OFF) is not None
    second = Attack(source_entity_uuid=enemy.uuid,target_entity_uuid=ally.uuid,weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert second is not None and not second.canceled
    assert guard.action_economy.reactions.normalized_score==1
