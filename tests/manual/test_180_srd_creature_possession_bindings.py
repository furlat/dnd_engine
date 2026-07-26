"""Canonical item bindings for every equipped SRD creature possession."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from dnd.blocks.base_item import EquippedVisualPolicy
from dnd.blocks.equipment import BodyArmor, Weapon
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeOrigin,
)
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.events import RangeType
from dnd.core.modifiers import DamageType
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
)
from dnd.runtime_reset import reset_engine_runtime


_EQUIPMENT_ATTRIBUTES = (
    "weapon_melee_main",
    "weapon_melee_off",
    "weapon_ranged_main",
    "weapon_ranged_off",
    "helmet",
    "body_armor",
    "gauntlets",
    "greaves",
    "boots",
    "amulet",
    "cloak",
    "ring_left",
    "ring_right",
)


@dataclass(frozen=True)
class _WeaponExpectation:
    name: str
    damage_dice: int
    dice_numbers: int
    damage_type: DamageType
    range_type: RangeType
    normal_range: int
    long_range: int | None
    visual_item_name: str | None
    visual_policy: EquippedVisualPolicy


_MIGRATED_WEAPON_EXPECTATIONS = {
    ("kobold", "weapon_ranged_main"): _WeaponExpectation(
        "Sling", 4, 1, DamageType.BLUDGEONING, RangeType.RANGE, 30, 120,
        "Sling", EquippedVisualPolicy.VISIBLE,
    ),
    ("spy", "weapon_ranged_main"): _WeaponExpectation(
        "Hand Crossbow", 6, 1, DamageType.PIERCING, RangeType.RANGE, 30, 120,
        "Light Crossbow", EquippedVisualPolicy.VISIBLE,
    ),
    ("bandit_captain", "weapon_ranged_main"): _WeaponExpectation(
        "Thrown Dagger", 4, 1, DamageType.PIERCING, RangeType.RANGE, 20, 60,
        "Dagger", EquippedVisualPolicy.VISIBLE,
    ),
    ("orc", "weapon_ranged_main"): _WeaponExpectation(
        "Thrown Javelin", 6, 1, DamageType.PIERCING, RangeType.RANGE, 30, 120,
        "Javelin", EquippedVisualPolicy.VISIBLE,
    ),
    ("bugbear", "weapon_melee_main"): _WeaponExpectation(
        "Morningstar", 8, 1, DamageType.PIERCING, RangeType.REACH, 5, None,
        "Morningstar", EquippedVisualPolicy.VISIBLE,
    ),
    ("bugbear", "weapon_ranged_main"): _WeaponExpectation(
        "Thrown Javelin", 6, 1, DamageType.PIERCING, RangeType.RANGE, 30, 120,
        "Javelin", EquippedVisualPolicy.VISIBLE,
    ),
    ("ogre", "weapon_melee_main"): _WeaponExpectation(
        "Greatclub", 8, 2, DamageType.BLUDGEONING, RangeType.REACH, 5, None,
        "Club", EquippedVisualPolicy.VISIBLE,
    ),
    ("ogre", "weapon_ranged_main"): _WeaponExpectation(
        "Thrown Javelin", 6, 2, DamageType.PIERCING, RangeType.RANGE, 30, 120,
        "Javelin", EquippedVisualPolicy.VISIBLE,
    ),
    ("wolf", "weapon_melee_main"): _WeaponExpectation(
        "Bite", 4, 2, DamageType.PIERCING, RangeType.REACH, 5, None,
        None, EquippedVisualPolicy.HIDDEN,
    ),
    ("dire_wolf", "weapon_melee_main"): _WeaponExpectation(
        "Bite", 6, 2, DamageType.PIERCING, RangeType.REACH, 5, None,
        None, EquippedVisualPolicy.HIDDEN,
    ),
    ("zombie", "weapon_melee_main"): _WeaponExpectation(
        "Slam", 6, 1, DamageType.BLUDGEONING, RangeType.REACH, 5, None,
        None, EquippedVisualPolicy.HIDDEN,
    ),
    ("ogre_zombie", "weapon_melee_main"): _WeaponExpectation(
        "Morningstar", 8, 2, DamageType.BLUDGEONING, RangeType.REACH, 5, None,
        "Morningstar", EquippedVisualPolicy.VISIBLE,
    ),
    ("ghoul", "weapon_melee_main"): _WeaponExpectation(
        "Claws", 4, 2, DamageType.SLASHING, RangeType.REACH, 5, None,
        None, EquippedVisualPolicy.HIDDEN,
    ),
    ("ghoul", "weapon_melee_off"): _WeaponExpectation(
        "Bite", 6, 2, DamageType.PIERCING, RangeType.REACH, 5, None,
        None, EquippedVisualPolicy.HIDDEN,
    ),
}

_MIGRATED_ARMOR_EXPECTATIONS = {
    ("wolf", "body_armor"): ("Natural Armor", 13),
    ("dire_wolf", "body_armor"): ("Natural Armor", 14),
}


def _materialize(
    creature_id: str,
    *,
    possession_mode: CreaturePossessionMode = (
        CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
    ),
):
    declaration = SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
    return materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=uuid4(),
        display_name=declaration.descriptor.display_name,
        faction="monsters",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.srd_possessions.{creature_id}",
        ),
        possession_mode=possession_mode,
    )


def test_every_equipped_srd_creature_item_has_an_exact_runtime_binding() -> None:
    """No creature possession may fall back to a Python class or display name."""
    for creature_id in SRD_CREATURE_RECIPES_BY_ID:
        reset_engine_runtime(grid_size=(8, 8))
        entity = _materialize(creature_id)
        for attribute_name in _EQUIPMENT_ATTRIBUTES:
            item = getattr(entity.equipment, attribute_name)
            if item is None:
                continue
            binding = ITEM_RUNTIME_BINDINGS.require(item.uuid)
            assert item.content_ref == binding.recipe.ref


def test_migrated_srd_possessions_preserve_their_exact_mechanical_profiles() -> None:
    """Registry migration must not silently alter the existing stat blocks."""
    by_creature: dict[str, object] = {}
    for creature_id, _ in (
        *_MIGRATED_WEAPON_EXPECTATIONS,
        *_MIGRATED_ARMOR_EXPECTATIONS,
    ):
        if creature_id in by_creature:
            continue
        reset_engine_runtime(grid_size=(8, 8))
        by_creature[creature_id] = _materialize(creature_id)

    for (creature_id, attribute_name), expected in (
        _MIGRATED_WEAPON_EXPECTATIONS.items()
    ):
        entity = by_creature[creature_id]
        item = getattr(entity.equipment, attribute_name)
        assert isinstance(item, Weapon)
        assert (
            item.name,
            item.damage_dice,
            item.dice_numbers,
            item.damage_type,
            item.range.type,
            item.range.normal,
            item.range.long,
            item.visual_item_name,
            item.equipped_visual_policy,
        ) == (
            expected.name,
            expected.damage_dice,
            expected.dice_numbers,
            expected.damage_type,
            expected.range_type,
            expected.normal_range,
            expected.long_range,
            expected.visual_item_name,
            expected.visual_policy,
        )

    for (creature_id, attribute_name), (name, armor_class) in (
        _MIGRATED_ARMOR_EXPECTATIONS.items()
    ):
        entity = by_creature[creature_id]
        item = getattr(entity.equipment, attribute_name)
        assert isinstance(item, BodyArmor)
        assert item.name == name
        assert item.ac.normalized_score == armor_class
        assert item.max_dex_bonus.normalized_score == 0
        assert item.equipped_visual_policy is EquippedVisualPolicy.HIDDEN


def test_structure_only_mode_retains_intrinsics_but_omits_possessions() -> None:
    """Natural body mechanics survive the same deployment-mode boundary."""
    reset_engine_runtime(grid_size=(8, 8))
    wolf = _materialize(
        "wolf",
        possession_mode=(
            CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
        ),
    )
    assert wolf.equipment.weapon_melee_main is not None
    assert wolf.equipment.body_armor is not None
    assert ITEM_RUNTIME_BINDINGS.require(
        wolf.equipment.weapon_melee_main.uuid,
    ).origin is ItemRuntimeOrigin.INTRINSIC
    assert ITEM_RUNTIME_BINDINGS.require(
        wolf.equipment.body_armor.uuid,
    ).origin is ItemRuntimeOrigin.INTRINSIC

    reset_engine_runtime(grid_size=(8, 8))
    kobold = _materialize(
        "kobold",
        possession_mode=(
            CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
        ),
    )
    assert kobold.equipment.weapon_melee_main is None
    assert kobold.equipment.weapon_ranged_main is None
