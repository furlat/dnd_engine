"""Rescued in-process item semantics for the CR-0 evidence freeze."""

from __future__ import annotations

from uuid import uuid4

import pytest

from dnd.actions import Attack
from dnd.content.items.authored_item_builders import (
    DIRECT_ITEM_BUILDERS,
    build_authored_item,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core import dice as dice_module
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.equipment_types import ArmorType, WeaponProperty, WeaponSet, WeaponSlot
from dnd.core.creature_types import DamageType
from dnd.entity import Entity
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime


BODY_ARMOR_CASES = (
    ("armor.padded", "Padded Armor", ArmorType.LIGHT, 11, 10, True, None),
    ("armor.leather", "Leather Armor", ArmorType.LIGHT, 11, 10, False, None),
    ("armor.studded_leather", "Studded Leather", ArmorType.LIGHT, 12, 10, False, None),
    ("armor.hide", "Hide Armor", ArmorType.MEDIUM, 12, 2, False, None),
    ("armor.chain_shirt", "Chain Shirt", ArmorType.MEDIUM, 13, 2, False, None),
    ("armor.scale_mail", "Scale Mail", ArmorType.MEDIUM, 14, 2, True, None),
    ("armor.breastplate", "Breastplate", ArmorType.MEDIUM, 14, 2, False, None),
    ("armor.half_plate", "Half Plate", ArmorType.MEDIUM, 15, 2, True, None),
    ("armor.ring_mail", "Ring Mail", ArmorType.HEAVY, 14, 0, True, None),
    ("armor.chain_mail", "Chain Mail", ArmorType.HEAVY, 16, 0, True, 13),
    ("armor.splint", "Splint Armor", ArmorType.HEAVY, 17, 0, True, 15),
    ("armor.plate", "Plate Armor", ArmorType.HEAVY, 18, 0, True, 15),
)


def _deployed_bestiary_actor(
    game: Game,
    creature_id: str,
    *,
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    entity = materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=uuid4(),
        display_name=name,
        faction=faction,
        position=position,
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.cr0.item.{creature_id}.actor_{uuid4().hex}",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def test_equipment_and_attacks_preserve_active_weapon_stance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equipment transitions and committed attacks own one valid stance."""
    reset_engine_runtime(grid_size=(70, 3))
    game = Game()
    owner = Entity.create(source_entity_uuid=uuid4(), name="Dual loadout")
    owner.compose_entity()
    game.deploy_entity(owner, (1, 1))
    shortbow = build_authored_item("weapon.shortbow", owner.uuid)
    dagger = build_authored_item("weapon.dagger", owner.uuid)

    assert owner.equipment.active_weapon_set is WeaponSet.NONE
    assert owner.loot_item(shortbow)
    assert owner.equip_item(shortbow.uuid, WeaponSlot.RANGED_MAIN)
    assert owner.equipment.active_weapon_set is WeaponSet.RANGED
    assert owner.loot_item(dagger)
    assert owner.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
    assert owner.equipment.active_weapon_set is WeaponSet.RANGED
    assert owner.unequip_item(WeaponSlot.RANGED_MAIN) is shortbow
    assert owner.equipment.active_weapon_set is WeaponSet.MELEE
    assert owner.unequip_item(WeaponSlot.MELEE_MAIN) is dagger
    assert owner.equipment.active_weapon_set is WeaponSet.NONE

    reset_engine_runtime(grid_size=(70, 3))
    game = Game()
    attacker = _deployed_bestiary_actor(
        game,
        "goblin",
        name="Dual wielder",
        position=(1, 1),
        faction="heroes",
    )
    adjacent = _deployed_bestiary_actor(
        game,
        "skeleton",
        name="Adjacent target",
        position=(2, 1),
        faction="monsters",
    )
    out_of_range = _deployed_bestiary_actor(
        game,
        "skeleton",
        name="Out-of-range target",
        position=(69, 1),
        faction="monsters",
    )
    Entity.update_all_entities_senses(max_distance=80)
    monkeypatch.setattr(dice_module.random, "randint", lambda _low, _high: 2)

    assert attacker.equipment.active_weapon_set is WeaponSet.MELEE
    ranged = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=adjacent.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
    ).apply()
    assert ranged is not None and not ranged.canceled
    assert attacker.equipment.active_weapon_set is WeaponSet.RANGED

    attacker.action_economy.reset_all_costs()
    melee = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=adjacent.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()
    assert melee is not None and not melee.canceled
    assert attacker.equipment.active_weapon_set is WeaponSet.MELEE

    attacker.action_economy.reset_all_costs()
    canceled = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=out_of_range.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
    ).apply()
    assert canceled is not None and canceled.canceled
    assert attacker.equipment.active_weapon_set is WeaponSet.MELEE


def test_srd_club_materializes_through_current_public_boundary() -> None:
    """The direct public builder creates fresh mechanically equal Clubs."""
    owner_uuid = uuid4()
    first = build_authored_item("weapon.club", owner_uuid)
    second = build_authored_item("weapon.club", owner_uuid)

    assert first is not second and first.uuid != second.uuid
    assert first.attack_bonus.uuid != second.attack_bonus.uuid
    assert first.item_id == second.item_id == "weapon.club"
    assert first.name == second.name == "Club"
    assert first.dice_numbers == second.dice_numbers == 1
    assert first.damage_dice == second.damage_dice == 4
    assert first.damage_type is second.damage_type is DamageType.BLUDGEONING
    assert first.properties == second.properties == [WeaponProperty.LIGHT]
    assert first.range.normal == second.range.normal == 5


def test_spell_item_declarations_and_recipes_use_current_public_boundary() -> None:
    """Ten public spell-item identities construct directly and independently."""
    item_ids = (
        "spell_item.scroll_fireball",
        "spell_item.scroll_magic_missile",
        "spell_item.scroll_hold_person",
        "spell_item.scroll_mage_armor",
        "spell_item.scroll_spike_growth",
        "spell_item.scroll_fire_bolt",
        "spell_item.wand_magic_missiles",
        "spell_item.wand_fire",
        "consumable.acid_flask",
        "spell_item.scroll_invisibility",
    )
    owner_uuid = uuid4()
    for item_id in item_ids:
        first = build_authored_item(item_id, owner_uuid)
        second = build_authored_item(item_id, owner_uuid)
        assert first.item_id == second.item_id == item_id
        assert first.uuid != second.uuid


def test_all_recipe_presets_resolve_and_materialize_exact_authored_variants() -> None:
    """Every public direct catalog entry constructs its exact identity."""
    owner_uuid = uuid4()
    assert len(DIRECT_ITEM_BUILDERS) == 147
    for item_id in DIRECT_ITEM_BUILDERS:
        item = build_authored_item(item_id, owner_uuid)
        assert item.item_id == item_id


def test_srd_armor_materializes_exact_current_mechanics() -> None:
    """All twelve body armors and the shield preserve their exact mechanics."""
    owner_uuid = uuid4()
    for (
        item_id,
        name,
        armor_type,
        armor_class,
        max_dex_bonus,
        stealth_disadvantage,
        strength_requirement,
    ) in BODY_ARMOR_CASES:
        armor = build_authored_item(item_id, owner_uuid)
        assert armor.item_id == item_id
        assert armor.name == name
        assert armor.type is armor_type
        assert armor.ac.score == armor_class
        assert armor.max_dex_bonus.score == max_dex_bonus
        assert armor.stealth_disadvantage is stealth_disadvantage
        assert armor.strength_requirement == strength_requirement

    shield = build_authored_item("shield.shield", owner_uuid)
    assert shield.item_id == "shield.shield"
    assert shield.name == "Shield"
    assert shield.ac_bonus.score == 2
