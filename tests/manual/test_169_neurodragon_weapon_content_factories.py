"""Direct runtime coverage for NeuroDragon's custom weapons."""

from uuid import uuid4

from dnd.blocks.equipment import Weapon
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import WeaponProperty, WeaponSlot
from dnd.core.events import RangeType
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime


def test_assassin_dagger_mechanics_and_equip_scoped_handler_are_exact() -> None:
    reset_engine_runtime(grid_size=(4, 3))
    attacker = Entity.create(source_entity_uuid=uuid4(), name="Assassin")
    dagger = build_authored_item("weapon.assassin_dagger", attacker.uuid)

    assert isinstance(dagger, Weapon)
    assert dagger.item_id == "weapon.assassin_dagger"
    assert dagger.name == "Assassin's Dagger"
    assert dagger.visual_item_name == "Dagger"
    assert dagger.visual_variant_id == "10000004"
    assert dagger.damage_dice == 4
    assert dagger.dice_numbers == 1
    assert dagger.damage_type is DamageType.PIERCING
    assert tuple(dagger.properties) == (
        WeaponProperty.FINESSE,
        WeaponProperty.LIGHT,
    )
    assert dagger.range.type is RangeType.REACH
    assert dagger.range.normal == 5

    assert attacker.equipment.equip(dagger, WeaponSlot.MELEE_MAIN)
    handler = attacker.get_event_handler_by_name("Unseen Strike")
    assert handler is not None
    assert handler.behavior_binding is not None
    assert handler.behavior_binding.behavior_id == dagger.item_id
    assert handler.behavior_binding.provided_by_id == dagger.item_id
    assert handler.behavior_binding.origin_root_id == dagger.item_id

    assert attacker.equipment.unequip(WeaponSlot.MELEE_MAIN) is dagger
    assert attacker.get_event_handler_by_name("Unseen Strike") is None


def test_double_bladed_sword_mechanics_are_exact() -> None:
    sword = build_authored_item("weapon.double_bladed_sword", uuid4())

    assert isinstance(sword, Weapon)
    assert sword.item_id == "weapon.double_bladed_sword"
    assert sword.name == "Double-Bladed Sword"
    assert sword.damage_dice == 4
    assert sword.dice_numbers == 2
    assert sword.damage_type is DamageType.SLASHING
    assert tuple(sword.properties) == (
        WeaponProperty.TWO_HANDED,
        WeaponProperty.MARTIAL,
    )
    assert sword.range.type is RangeType.REACH
    assert sword.range.normal == 5


def test_arcane_staff_modifier_is_exactly_equip_scoped() -> None:
    reset_engine_runtime(grid_size=(4, 3))
    caster = Entity.create(source_entity_uuid=uuid4(), name="Arcane wielder")
    staff = build_authored_item("weapon.arcane_staff", caster.uuid)
    base_spell_attack = caster.spellcasting.spell_attack_bonus.normalized_score

    assert isinstance(staff, Weapon)
    assert staff.item_id == "weapon.arcane_staff"
    assert staff.name == "Arcane Staff"
    assert staff.visual_item_name == "Quarterstaff"
    assert staff.visual_variant_id == "1000000f"
    assert staff.damage_dice == 6
    assert staff.dice_numbers == 1
    assert staff.damage_type is DamageType.BLUDGEONING
    assert tuple(staff.properties) == (WeaponProperty.VERSATILE,)
    assert staff.range.type is RangeType.REACH
    assert staff.range.normal == 5

    assert caster.equipment.equip(staff, WeaponSlot.MELEE_MAIN)
    assert (
        caster.spellcasting.spell_attack_bonus.normalized_score
        == base_spell_attack + 1
    )
    assert caster.equipment.unequip(WeaponSlot.MELEE_MAIN) is staff
    assert (
        caster.spellcasting.spell_attack_bonus.normalized_score
        == base_spell_attack
    )
