"""Maintained direct-item mechanics proof for circus possessions."""

from uuid import uuid4

from dnd.blocks.equipment import Weapon
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.creature_types import DamageType
from dnd.core.events import RangeType
from dnd.core.equipment_types import WeaponProperty
from dnd.core.modifiers import AdvantageStatus
from dnd.runtime_reset import reset_engine_runtime


def test_circus_weapon_materialization_preserves_all_mechanical_profiles() -> None:
    """All four direct weapons retain their exact mechanical profiles."""
    reset_engine_runtime(grid_size=(4, 3))
    owner_uuid = uuid4()
    rusty, flaming, longsword, morningstar = (
        build_authored_item(item_id, owner_uuid)
        for item_id in (
            "weapon.circus.rusty_dagger",
            "weapon.circus.flaming_scimitar",
            "weapon.circus.longsword_plus_one",
            "weapon.circus.soul_draining_morningstar",
        )
    )
    assert all(
        isinstance(item, Weapon)
        for item in (rusty, flaming, longsword, morningstar)
    )

    assert rusty.item_id == "weapon.circus.rusty_dagger"
    assert rusty.name == "Rusty Dagger"
    assert rusty.damage_dice == 4
    assert rusty.dice_numbers == 1
    assert rusty.damage_type is DamageType.PIERCING
    assert tuple(rusty.properties) == (
        WeaponProperty.FINESSE,
        WeaponProperty.LIGHT,
        WeaponProperty.THROWN,
    )
    assert rusty.range.type is RangeType.REACH
    assert rusty.range.normal == 5
    assert rusty.attack_bonus.advantage is AdvantageStatus.DISADVANTAGE

    assert flaming.item_id == "weapon.circus.flaming_scimitar"
    assert flaming.name == "Flaming Scimitar"
    assert flaming.visual_item_name == "Scimitar"
    assert flaming.visual_variant_id == "30000017"
    assert flaming.damage_dice == 6
    assert flaming.dice_numbers == 1
    assert flaming.damage_type is DamageType.SLASHING
    assert tuple(flaming.properties) == (
        WeaponProperty.FINESSE,
        WeaponProperty.LIGHT,
    )
    assert flaming.extra_damage_dices == [6]
    assert flaming.extra_damage_dices_numbers == [1]
    assert tuple(flaming.extra_damage_type) == (DamageType.FIRE,)

    assert longsword.item_id == "weapon.circus.longsword_plus_one"
    assert longsword.name == "Longsword +1"
    assert longsword.damage_dice == 8
    assert longsword.damage_type is DamageType.SLASHING
    assert tuple(longsword.properties) == (WeaponProperty.VERSATILE,)
    assert longsword.attack_bonus.normalized_score == 1
    assert longsword.damage_bonus is not None
    assert longsword.damage_bonus.normalized_score == 1

    assert morningstar.item_id == "weapon.circus.soul_draining_morningstar"
    assert morningstar.name == "Soul-Draining Morningstar"
    assert morningstar.damage_dice == 8
    assert morningstar.damage_type is DamageType.PIERCING
    assert morningstar.properties == []
    assert morningstar.extra_damage_dices == [4]
    assert morningstar.extra_damage_dices_numbers == [1]
    assert tuple(morningstar.extra_damage_type) == (DamageType.NECROTIC,)
