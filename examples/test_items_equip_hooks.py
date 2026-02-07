"""
Items Equip/Unequip Hooks Tests

Tests:
- Reparenting: Weapon/Armor/Shield are EquippableItem instances
- Location tracking: owner_uuid, stored_in_uuid, is_equipped, equipped_slot
- Hook calls: equip/unequip hooks fire on Equipment.equip()/unequip()
- Entity.equip_item/unequip_item: inventory ↔ equipment transfers
- Hook approaches: direct modifier, direct action, condition pattern
- Combat integration: reparented weapons still work in attacks
"""

import sys
import traceback
from typing import Optional
from uuid import UUID, uuid4

from dnd.utils import reset_combat_state, force_attack_hit, setup_combat_arena, get_hp
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType, NumericalModifier
from dnd.core.base_conditions import BaseCondition
from dnd.core.values import ModifiableValue
from dnd.core.events import WeaponSlot, BodyPart, EquipmentSlot, EventPhase, RangeType
from dnd.blocks.base_item import BaseItem, EquippableItem
from dnd.blocks.equipment import Weapon, Cloak, ArmorType, EquipmentConfig, Range
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.actions_functional import setup_standard_actions
from dnd.items.weapons import create_longsword
from dnd.items.armors import create_leather_armor, create_wooden_shield


tests_passed = 0
tests_failed = 0


def run_test(name, func):
    global tests_passed, tests_failed
    reset_combat_state()
    try:
        func()
        print(f"  PASS: {name}")
        tests_passed += 1
    except Exception:
        print(f"  FAIL: {name}")
        traceback.print_exc()
        tests_failed += 1


def create_test_entity(position=(3, 3), name="Hero", faction="heroes"):
    source_id = uuid4()
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="maximums")]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(name=name, source_entity_uuid=source_id, config=config)
    setup_standard_actions(entity)
    return entity


def create_test_grid(width=10, height=10):
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    return grid


# =========================================================================
# Test Item Subclasses (demonstrate hook approaches)
# =========================================================================

class DefenderSword(Weapon):
    """Approach 1: Direct modifier. +1 AC when equipped."""
    _ac_modifier_uuid: Optional[UUID] = None

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is None:
            return
        modifier = NumericalModifier.create(
            source_entity_uuid=entity_uuid,
            name="Defender Sword +1 AC",
            value=1
        )
        self._ac_modifier_uuid = entity.equipment.ac_bonus.self_static.add_value_modifier(modifier)

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is None or self._ac_modifier_uuid is None:
            return
        entity.equipment.ac_bonus.self_static.remove_modifier(self._ac_modifier_uuid)
        self._ac_modifier_uuid = None


class CloakOfProtection(Cloak):
    """Approach 3: Condition pattern. +1 AC and +1 all saves when equipped."""
    _condition_name: str = "Cloak of Protection Effect"

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is None:
            return
        cond = CloakOfProtectionCondition(
            source_entity_uuid=entity_uuid,
            target_entity_uuid=entity_uuid,
        )
        entity.add_condition(cond)

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is None:
            return
        if self._condition_name in entity.active_conditions:
            entity.remove_condition(self._condition_name)


class CloakOfProtectionCondition(BaseCondition):
    name: str = "Cloak of Protection Effect"
    description: str = "+1 AC and +1 all saving throws"

    def _apply(self, declaration_event):
        if self.target_entity_uuid is None:
            return [], [], [], [], None
        entity = Entity.get(self.target_entity_uuid)
        if entity is None:
            return [], [], [], [], None
        outs = []
        # +1 AC
        ac_mod = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            name="Cloak of Protection AC",
            value=1
        )
        mod_uuid = entity.equipment.ac_bonus.self_static.add_value_modifier(ac_mod)
        outs.append((entity.equipment.ac_bonus.uuid, mod_uuid))
        # +1 all saves
        for ability_name in ['strength_saving_throw', 'dexterity_saving_throw', 'constitution_saving_throw',
                             'intelligence_saving_throw', 'wisdom_saving_throw', 'charisma_saving_throw']:
            save = getattr(entity.saving_throws, ability_name)
            save_mod = NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name="Cloak of Protection Save",
                value=1
            )
            mod_uuid = save.bonus.self_static.add_value_modifier(save_mod)
            outs.append((save.bonus.uuid, mod_uuid))
        effect_event = declaration_event.phase_to(EventPhase.EFFECT,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid)
        return outs, [], [], [], effect_event


def create_defender_sword(source_id: UUID) -> DefenderSword:
    return DefenderSword(
        source_entity_uuid=source_id,
        name="Defender Sword",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[],
        range=Range(type=RangeType.REACH, normal=5, long=5),
    )


def create_cloak_of_protection(source_id: UUID) -> CloakOfProtection:
    return CloakOfProtection(
        source_entity_uuid=source_id,
        name="Cloak of Protection",
        type=ArmorType.CLOTH,
        body_part=BodyPart.CLOAK,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Cloak AC"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=99, value_name="Cloak Max Dex"),
    )


def create_flaming_sword(source_id: UUID) -> Weapon:
    return Weapon(
        source_entity_uuid=source_id,
        name="Flaming Sword",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[],
        range=Range(type=RangeType.REACH, normal=5, long=5),
        extra_damage_dices=[6],
        extra_damage_dices_numbers=[1],
        extra_damage_bonus=[ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Fire Bonus")],
        extra_damage_type=[DamageType.FIRE],
    )


# =========================================================================
# Tests: Reparenting
# =========================================================================

def test_reparenting_isinstance():
    """Weapon/Armor/Shield are EquippableItem and BaseItem instances."""
    sword = create_longsword(uuid4())
    armor = create_leather_armor(uuid4())
    shield = create_wooden_shield(uuid4())

    assert isinstance(sword, EquippableItem), "Weapon should be EquippableItem"
    assert isinstance(armor, EquippableItem), "Armor should be EquippableItem"
    assert isinstance(shield, EquippableItem), "Shield should be EquippableItem"
    assert isinstance(sword, BaseItem), "Weapon should be BaseItem"
    assert isinstance(armor, BaseItem), "Armor should be BaseItem"
    assert isinstance(shield, BaseItem), "Shield should be BaseItem"
    assert sword.is_equippable, "Weapon.is_equippable should be True"
    assert armor.is_equippable, "Armor.is_equippable should be True"
    assert shield.is_equippable, "Shield.is_equippable should be True"


# =========================================================================
# Tests: Location tracking on equip/unequip
# =========================================================================

def test_equip_sets_tracking():
    """After Equipment.equip(): is_equipped, equipped_slot, owner_uuid, stored_in_uuid set."""
    create_test_grid()
    entity = create_test_entity()
    sword = create_longsword(entity.uuid)

    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)

    assert sword.is_equipped, "is_equipped should be True"
    assert sword.equipped_slot == WeaponSlot.MELEE_MAIN.value, \
        f"equipped_slot should be '{WeaponSlot.MELEE_MAIN.value}', got '{sword.equipped_slot}'"
    assert sword.owner_uuid == entity.uuid, \
        f"owner_uuid should be entity UUID, got {sword.owner_uuid}"
    assert sword.stored_in_uuid == entity.equipment.uuid, \
        f"stored_in_uuid should be equipment UUID, got {sword.stored_in_uuid}"


def test_unequip_clears_tracking():
    """After unequip: is_equipped=False, equipped_slot=None. owner/stored still set."""
    create_test_grid()
    entity = create_test_entity()
    sword = create_longsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)

    entity.equipment.unequip(WeaponSlot.MELEE_MAIN)

    assert not sword.is_equipped, "is_equipped should be False after unequip"
    assert sword.equipped_slot is None, "equipped_slot should be None after unequip"
    # owner_uuid and stored_in_uuid are still set — caller hasn't placed it yet
    assert sword.owner_uuid == entity.uuid, "owner_uuid still set after Equipment.unequip"
    assert sword.stored_in_uuid == entity.equipment.uuid, "stored_in_uuid still set after Equipment.unequip"


def test_get_position_equipped():
    """get_position() returns entity.position for equipped item."""
    create_test_grid()
    entity = create_test_entity(position=(5, 5))
    sword = create_longsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)

    pos = sword.get_position()
    assert pos == (5, 5), f"Expected entity position (5,5), got {pos}"


def test_get_position_inventory_vs_equipped():
    """stored_in_uuid differs between inventory and equipped. get_position same."""
    create_test_grid()
    entity = create_test_entity(position=(4, 4))
    sword = create_longsword(entity.uuid)

    # Put in inventory
    entity.inventory.add_item(sword)
    sword.owner_uuid = entity.uuid
    sword.stored_in_uuid = entity.inventory.uuid
    inv_stored = sword.stored_in_uuid
    inv_pos = sword.get_position()

    # Move to equipment
    entity.inventory.remove_item(sword.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    equip_stored = sword.stored_in_uuid

    assert inv_stored != equip_stored, \
        f"stored_in_uuid should differ: inventory={inv_stored}, equipment={equip_stored}"
    assert inv_pos == (4, 4), f"Inventory position should be (4,4), got {inv_pos}"
    assert sword.get_position() == (4, 4), f"Equipped position should be (4,4), got {sword.get_position()}"


# =========================================================================
# Tests: Entity.equip_item / unequip_item
# =========================================================================

def test_equip_from_inventory():
    """Entity.equip_item(): item moves from inventory to equipment slot."""
    create_test_grid()
    entity = create_test_entity()
    sword = create_longsword(entity.uuid)

    # Add to inventory
    entity.inventory.add_item(sword)
    sword.owner_uuid = entity.uuid
    sword.stored_in_uuid = entity.inventory.uuid

    result = entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert result, "equip_item should return True"
    assert sword.uuid not in entity.inventory.items, "Item should be removed from inventory"
    assert entity.equipment.weapon_melee_main is sword, "Item should be in equipment slot"
    assert sword.is_equipped, "is_equipped should be True"
    assert sword.owner_uuid == entity.uuid, "owner_uuid should be entity UUID"
    assert sword.stored_in_uuid == entity.equipment.uuid, "stored_in_uuid should be equipment UUID"


def test_unequip_to_inventory():
    """Entity.unequip_item(): item moves from equipment to inventory."""
    create_test_grid()
    entity = create_test_entity()
    sword = create_longsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)

    item = entity.unequip_item(WeaponSlot.MELEE_MAIN)
    assert item is sword, "Should return the unequipped item"
    assert sword.uuid in entity.inventory.items, "Item should be in inventory"
    assert entity.equipment.weapon_melee_main is None, "Equipment slot should be empty"
    assert not sword.is_equipped, "is_equipped should be False"
    assert sword.owner_uuid == entity.uuid, "owner_uuid should be entity UUID (now in inventory)"
    assert sword.stored_in_uuid == entity.inventory.uuid, "stored_in_uuid should be inventory UUID"


def test_equip_swap():
    """Equip item in occupied slot: old item goes to inventory, new item in slot."""
    create_test_grid()
    entity = create_test_entity()
    sword1 = create_longsword(entity.uuid)
    sword2 = create_longsword(entity.uuid)
    sword2.name = "Longsword 2"

    # Put sword2 in inventory, equip sword1 directly
    entity.equipment.equip(sword1, WeaponSlot.MELEE_MAIN)
    entity.inventory.add_item(sword2)
    sword2.owner_uuid = entity.uuid
    sword2.stored_in_uuid = entity.inventory.uuid

    entity.equip_item(sword2.uuid, WeaponSlot.MELEE_MAIN)

    assert entity.equipment.weapon_melee_main is sword2, "New sword should be in slot"
    assert sword2.is_equipped, "New sword should be equipped"
    assert not sword1.is_equipped, "Old sword should not be equipped"


# =========================================================================
# Tests: Hook approaches
# =========================================================================

def test_defender_sword():
    """Direct modifier approach: Equip → AC +1. Unequip → AC back."""
    create_test_grid()
    entity = create_test_entity()
    sword = create_defender_sword(entity.uuid)

    base_ac = entity.equipment.ac_bonus.normalized_score
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    assert entity.equipment.ac_bonus.normalized_score == base_ac + 1, \
        f"AC bonus should increase by 1, was {base_ac}, now {entity.equipment.ac_bonus.normalized_score}"

    entity.equipment.unequip(WeaponSlot.MELEE_MAIN)
    assert entity.equipment.ac_bonus.normalized_score == base_ac, \
        f"AC bonus should return to {base_ac}, got {entity.equipment.ac_bonus.normalized_score}"


def test_cloak_protection():
    """Condition approach: Equip → +1 AC and all saves. Unequip → removed."""
    create_test_grid()
    entity = create_test_entity()
    cloak = create_cloak_of_protection(entity.uuid)

    base_ac = entity.equipment.ac_bonus.normalized_score
    base_str_save = entity.saving_throws.strength_saving_throw.bonus.normalized_score
    base_dex_save = entity.saving_throws.dexterity_saving_throw.bonus.normalized_score

    entity.equipment.equip(cloak)
    assert entity.equipment.ac_bonus.normalized_score == base_ac + 1, \
        f"AC should be +1, was {base_ac}, now {entity.equipment.ac_bonus.normalized_score}"
    assert entity.saving_throws.strength_saving_throw.bonus.normalized_score == base_str_save + 1, \
        f"STR save should be +1"
    assert entity.saving_throws.dexterity_saving_throw.bonus.normalized_score == base_dex_save + 1, \
        f"DEX save should be +1"
    assert "Cloak of Protection Effect" in entity.active_conditions, \
        "Condition should be on entity"

    entity.equipment.unequip(BodyPart.CLOAK)
    assert entity.equipment.ac_bonus.normalized_score == base_ac, \
        f"AC should return to {base_ac}"
    assert entity.saving_throws.strength_saving_throw.bonus.normalized_score == base_str_save, \
        f"STR save should return to {base_str_save}"
    assert "Cloak of Protection Effect" not in entity.active_conditions, \
        "Condition should be removed"


def test_flaming_sword_attack():
    """Reparented weapon + extra damage works in combat."""
    create_test_grid()
    attacker = create_test_entity(position=(3, 3), name="Attacker")
    target = create_test_entity(position=(4, 3), name="Target", faction="monsters")
    sword = create_flaming_sword(attacker.uuid)
    attacker.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    Entity.update_all_entities_senses()

    encounter = setup_combat_arena(attacker, target)
    encounter.start_encounter()
    encounter.start_turn()
    force_attack_hit(attacker)

    hp_before = get_hp(target)
    from dnd.actions import Attack
    attack = Attack(
        source_entity_uuid=attacker.uuid,
        name="Attack",
        weapon_slot=WeaponSlot.MELEE_MAIN,
        target_entity_uuid=target.uuid,
    )
    attack.apply()
    hp_after = get_hp(target)
    damage_dealt = hp_before - hp_after
    assert damage_dealt > 0, f"Should deal damage, dealt {damage_dealt}"


# =========================================================================
# Tests: Existing factories still work
# =========================================================================

def test_existing_factories():
    """create_longsword, create_leather_armor, create_wooden_shield work after reparenting."""
    create_test_grid()
    entity = create_test_entity()
    sword = create_longsword(entity.uuid)
    armor = create_leather_armor(entity.uuid)
    shield = create_wooden_shield(entity.uuid)

    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(armor)
    entity.equipment.equip(shield)

    assert entity.equipment.weapon_melee_main is sword
    assert entity.equipment.body_armor is armor
    assert entity.equipment.weapon_melee_off is shield
    assert sword.is_equipped
    assert armor.is_equipped
    assert shield.is_equipped


# =========================================================================
# Tests: get_item_by_slot
# =========================================================================

def test_get_item_by_slot():
    """Equipment.get_item_by_slot() returns correct items for all slot types."""
    create_test_grid()
    entity = create_test_entity()
    sword = create_longsword(entity.uuid)
    armor = create_leather_armor(entity.uuid)
    shield = create_wooden_shield(entity.uuid)

    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(armor)
    entity.equipment.equip(shield)

    assert entity.equipment.get_item_by_slot(WeaponSlot.MELEE_MAIN) is sword
    assert entity.equipment.get_item_by_slot(BodyPart.BODY) is armor
    assert entity.equipment.get_item_by_slot(WeaponSlot.MELEE_OFF) is shield
    assert entity.equipment.get_item_by_slot(WeaponSlot.RANGED_MAIN) is None
    assert entity.equipment.get_item_by_slot(BodyPart.HEAD) is None


# =========================================================================
# Tests: Armor equip tracking
# =========================================================================

def test_armor_equip_tracking():
    """Armor pieces get proper tracking on equip."""
    create_test_grid()
    entity = create_test_entity()
    armor = create_leather_armor(entity.uuid)

    entity.equipment.equip(armor)

    assert armor.is_equipped, "Armor should be equipped"
    assert armor.equipped_slot == BodyPart.BODY.value, \
        f"equipped_slot should be '{BodyPart.BODY.value}', got '{armor.equipped_slot}'"
    assert armor.owner_uuid == entity.uuid
    assert armor.stored_in_uuid == entity.equipment.uuid


def test_shield_equip_tracking():
    """Shields get proper tracking on equip."""
    create_test_grid()
    entity = create_test_entity()
    shield = create_wooden_shield(entity.uuid)

    entity.equipment.equip(shield)

    assert shield.is_equipped
    assert shield.equipped_slot == WeaponSlot.MELEE_OFF.value, \
        f"equipped_slot should be '{WeaponSlot.MELEE_OFF.value}', got '{shield.equipped_slot}'"
    assert shield.owner_uuid == entity.uuid
    assert shield.stored_in_uuid == entity.equipment.uuid


# =========================================================================
# Main
# =========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Items Equip/Unequip Hooks Tests")
    print("=" * 60)

    print("\n--- Reparenting ---")
    run_test("Reparenting isinstance checks", test_reparenting_isinstance)

    print("\n--- Location Tracking ---")
    run_test("Equip sets tracking fields", test_equip_sets_tracking)
    run_test("Unequip clears tracking fields", test_unequip_clears_tracking)
    run_test("get_position for equipped item", test_get_position_equipped)
    run_test("get_position inventory vs equipped", test_get_position_inventory_vs_equipped)
    run_test("Armor equip tracking", test_armor_equip_tracking)
    run_test("Shield equip tracking", test_shield_equip_tracking)

    print("\n--- Entity equip_item / unequip_item ---")
    run_test("Equip from inventory", test_equip_from_inventory)
    run_test("Unequip to inventory", test_unequip_to_inventory)
    run_test("Equip swap", test_equip_swap)

    print("\n--- Hook Approaches ---")
    run_test("Defender sword (direct modifier)", test_defender_sword)
    run_test("Cloak of Protection (condition)", test_cloak_protection)
    run_test("Flaming sword attack", test_flaming_sword_attack)

    print("\n--- Integration ---")
    run_test("Existing factories", test_existing_factories)
    run_test("get_item_by_slot", test_get_item_by_slot)

    print("\n" + "=" * 60)
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
    sys.exit(0 if tests_failed == 0 else 1)
