"""Exact legacy coverage for equippable-item hooks and location tracking."""

from dataclasses import dataclass
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import PrivateAttr

from dnd.blocks.base_item import BaseItem, EquippableItem
from dnd.blocks.equipment import BodyArmor, Cloak, Shield, Weapon
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_conditions import BaseCondition
from dnd.core.equipment_types import (
    ArmorType,
    BodyPart,
    EquipmentSlot,
    WeaponSlot,
)
from dnd.core.events import AbilityName, Event, EventPhase, Range, RangeType
from dnd.core.modifiers import DamageType, NumericalModifier
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.items.armors import LEATHER_ARMOR_RECIPE, WOODEN_SHIELD_RECIPE
from dnd.items.weapons import LONGSWORD_RECIPE
from dnd.monsters.bestiary import create_skeleton
from tests.engine_book.test_chapter_13_items_inventory_equipment import (
    put_in_inventory,
    reset_item_state,
)


CoverageStatus = Literal["active", "strengthened"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived equip-hook case's reviewed replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_142_item_equip_hooks_legacy_contract.py"
DIRECT_SELECTOR = (
    f"{THIS_FILE}::"
    "test_direct_equipment_tracks_concrete_items_slots_containers_and_positions"
)
EB13_FILE = "tests/engine_book/test_chapter_13_items_inventory_equipment.py"
TRANSFER_SELECTOR = (
    f"{EB13_FILE}::"
    "test_eb_13_004_equip_and_unequip_move_items_between_inventory_and_equipment"
)
SWAP_SELECTOR = (
    f"{EB13_FILE}::"
    "test_eb_13_005_equipment_validates_weapon_slots_and_replaces_existing_items"
)
EXACT_HOOK_SELECTOR = (
    f"{THIS_FILE}::"
    "test_direct_modifier_and_condition_equipment_hooks_clean_exact_state"
)
MIXED_DAMAGE_SELECTOR = (
    "tests/engine_book/test_chapter_10_core_actions_combat.py::"
    "test_eb_10_016_mixed_weapon_damage_applies_resistance_per_component"
)


ITEM_EQUIP_HOOK_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_reparenting_isinstance": LegacyCoverage(
        "active",
        DIRECT_SELECTOR,
        "Each concrete weapon, armor, and shield factory is asserted as both EquippableItem and BaseItem.",
    ),
    "test_equip_sets_tracking": LegacyCoverage(
        "active",
        DIRECT_SELECTOR,
        "Direct equip asserts owner, equipment container, active flag, and typed slot.",
    ),
    "test_unequip_clears_tracking": LegacyCoverage(
        "active",
        DIRECT_SELECTOR,
        "Direct unequip clears only equipped state while retaining the caller-owned container.",
    ),
    "test_get_position_equipped": LegacyCoverage(
        "active",
        DIRECT_SELECTOR,
        "Equipped-item position follows its entity owner.",
    ),
    "test_get_position_inventory_vs_equipped": LegacyCoverage(
        "strengthened",
        TRANSFER_SELECTOR,
        "The maintained high-level transfer asserts both authoritative containers and ownership.",
    ),
    "test_equip_from_inventory": LegacyCoverage(
        "strengthened",
        TRANSFER_SELECTOR,
        "The maintained test checks the complete inventory-to-equipment transaction.",
    ),
    "test_unequip_to_inventory": LegacyCoverage(
        "strengthened",
        TRANSFER_SELECTOR,
        "The maintained test checks the complete equipment-to-inventory transaction.",
    ),
    "test_equip_swap": LegacyCoverage(
        "strengthened",
        SWAP_SELECTOR,
        "The maintained test also validates slot compatibility and displaced state cleanup.",
    ),
    "test_defender_sword": LegacyCoverage(
        "strengthened",
        EXACT_HOOK_SELECTOR,
        "The maintained direct-modifier fixture asserts Defender Sword AC application and exact cleanup.",
    ),
    "test_cloak_protection": LegacyCoverage(
        "strengthened",
        EXACT_HOOK_SELECTOR,
        "The maintained condition-owned fixture asserts Cloak AC and all six saves through equip and cleanup.",
    ),
    "test_flaming_sword_attack": LegacyCoverage(
        "strengthened",
        MIXED_DAMAGE_SELECTOR,
        "Maintained combat coverage asserts typed base and elemental packets through resistance.",
    ),
    "test_existing_factories": LegacyCoverage(
        "active",
        DIRECT_SELECTOR,
        "The three concrete factories are instantiated and equipped through canonical slots.",
    ),
    "test_get_item_by_slot": LegacyCoverage(
        "active",
        DIRECT_SELECTOR,
        "Every populated and empty weapon/body lookup is asserted.",
    ),
    "test_armor_equip_tracking": LegacyCoverage(
        "active",
        DIRECT_SELECTOR,
        "Body armor carries canonical owner, container, and slot tracking.",
    ),
    "test_shield_equip_tracking": LegacyCoverage(
        "active",
        DIRECT_SELECTOR,
        "Shield tracking resolves through its canonical off-hand weapon slot.",
    ),
}


SAVE_ABILITIES: tuple[AbilityName, ...] = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)
CLOAK_PROTECTION_CONDITION_NAME = "Cloak of Protection Effect"


class _DefenderSword(Weapon):
    """Test fixture proving the direct-modifier equipment-hook pattern."""

    _ac_modifier_uuid: Optional[UUID] = PrivateAttr(default=None)

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if not isinstance(entity, Entity):
            return
        modifier = NumericalModifier(
            name="Defender Sword +1 AC",
            value=1,
            source_entity_uuid=entity_uuid,
            target_entity_uuid=entity_uuid,
        )
        self._ac_modifier_uuid = (
            entity.equipment.ac_bonus.self_static.add_value_modifier(modifier)
        )

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if not isinstance(entity, Entity) or self._ac_modifier_uuid is None:
            return
        entity.equipment.ac_bonus.self_static.remove_modifier(
            self._ac_modifier_uuid
        )
        self._ac_modifier_uuid = None


class _CloakOfProtectionCondition(BaseCondition):
    """Test fixture owning the cloak's AC and saving-throw modifiers."""

    name: str = CLOAK_PROTECTION_CONDITION_NAME
    description: str = "+1 AC and +1 to all saving throws while equipped"

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[
        list[tuple[UUID, UUID]],
        list[UUID],
        list[UUID],
        list[UUID],
        Optional[Event],
    ]:
        entity = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if not isinstance(entity, Entity):
            return (
                [],
                [],
                [],
                [],
                declaration_event.cancel(status_message="Target not found"),
            )

        owned_modifiers: list[tuple[UUID, UUID]] = []
        ac_modifier = NumericalModifier(
            name="Cloak of Protection AC",
            value=1,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
        )
        ac_modifier_uuid = (
            entity.equipment.ac_bonus.self_static.add_value_modifier(ac_modifier)
        )
        owned_modifiers.append(
            (entity.equipment.ac_bonus.uuid, ac_modifier_uuid)
        )

        for ability in SAVE_ABILITIES:
            saving_throw = entity.saving_throws.get_saving_throw(ability)
            save_modifier = NumericalModifier(
                name=f"Cloak of Protection {ability.title()} Save",
                value=1,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
            save_modifier_uuid = (
                saving_throw.bonus.self_static.add_value_modifier(save_modifier)
            )
            owned_modifiers.append(
                (saving_throw.bonus.uuid, save_modifier_uuid)
            )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Cloak of Protection modifiers applied",
        )
        return owned_modifiers, [], [], [], effect_event


class _CloakOfProtection(Cloak):
    """Test fixture proving the condition-owned equipment-hook pattern."""

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if not isinstance(entity, Entity):
            return
        entity.add_condition(
            _CloakOfProtectionCondition(
                source_entity_uuid=entity_uuid,
                target_entity_uuid=entity_uuid,
            )
        )

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if (
            isinstance(entity, Entity)
            and CLOAK_PROTECTION_CONDITION_NAME in entity.active_conditions
        ):
            entity.remove_condition(CLOAK_PROTECTION_CONDITION_NAME)


def _create_defender_sword(owner_uuid: UUID) -> _DefenderSword:
    """Create the archived direct-modifier hook fixture."""
    return _DefenderSword(
        source_entity_uuid=owner_uuid,
        name="Defender Sword",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[],
        range=Range(type=RangeType.REACH, normal=5),
    )


def _create_cloak_of_protection(owner_uuid: UUID) -> _CloakOfProtection:
    """Create the archived condition-owned hook fixture."""
    return _CloakOfProtection(
        source_entity_uuid=owner_uuid,
        name="Cloak of Protection",
        type=ArmorType.CLOTH,
        body_part=BodyPart.CLOAK,
        ac=ModifiableValue.create(
            source_entity_uuid=owner_uuid,
            base_value=0,
            value_name="Cloak Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=owner_uuid,
            base_value=99,
            value_name="Cloak Maximum Dexterity Bonus",
        ),
    )


def test_item_equip_hook_manifest_accounts_for_all_15_cases() -> None:
    """Every archived equip-hook case has a reviewed maintained disposition."""
    assert len(ITEM_EQUIP_HOOK_LEGACY_CASES) == 15
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for case, row in ITEM_EQUIP_HOOK_LEGACY_CASES.items()
    )


def test_direct_equipment_tracks_concrete_items_slots_containers_and_positions() -> None:
    """Direct and high-level equipment paths retain one location authority."""
    reset_item_state()
    entity = create_skeleton(
        name="Equipment Auditor",
        position=(2, 2),
        darkvision=False,
    )
    sword = materialize_item(
        LONGSWORD_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    armor_owner_uuid = uuid4()
    armor = materialize_item(
        LEATHER_ARMOR_RECIPE,
        armor_owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    shield = materialize_item(
        WOODEN_SHIELD_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )

    assert isinstance(sword, EquippableItem)
    assert isinstance(armor, EquippableItem)
    assert isinstance(shield, EquippableItem)
    assert isinstance(sword, BaseItem)
    assert isinstance(armor, BaseItem)
    assert isinstance(shield, BaseItem)
    assert (sword.is_equippable, armor.is_equippable, shield.is_equippable) == (
        True,
        True,
        True,
    )

    put_in_inventory(entity, sword)
    assert sword.get_position() == entity.position
    assert entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert sword.get_position() == entity.position
    assert (
        sword.is_equipped,
        sword.equipped_slot,
        sword.owner_uuid,
        sword.stored_in_uuid,
    ) == (
        True,
        WeaponSlot.MELEE_MAIN.value,
        entity.uuid,
        entity.equipment.uuid,
    )

    assert entity.equipment.equip(armor)
    assert entity.equipment.equip(shield)
    assert entity.equipment.get_item_by_slot(WeaponSlot.MELEE_MAIN) is sword
    assert entity.equipment.get_item_by_slot(BodyPart.BODY) is armor
    assert entity.equipment.get_item_by_slot(WeaponSlot.MELEE_OFF) is shield
    assert entity.equipment.get_item_by_slot(WeaponSlot.RANGED_OFF) is None
    assert entity.equipment.get_item_by_slot(BodyPart.HEAD) is None
    assert (
        armor.is_equipped,
        armor.equipped_slot,
        armor.owner_uuid,
        armor.stored_in_uuid,
    ) == (True, BodyPart.BODY.value, entity.uuid, entity.equipment.uuid)
    assert (
        shield.is_equipped,
        shield.equipped_slot,
        shield.owner_uuid,
        shield.stored_in_uuid,
    ) == (
        True,
        WeaponSlot.MELEE_OFF.value,
        entity.uuid,
        entity.equipment.uuid,
    )

    unequipped = entity.equipment.unequip(WeaponSlot.MELEE_MAIN)
    assert unequipped is sword
    assert sword.is_equipped is False
    assert sword.equipped_slot is None
    assert sword.owner_uuid == entity.uuid
    assert sword.stored_in_uuid == entity.equipment.uuid
    assert sword.get_position() == entity.position


def test_direct_modifier_and_condition_equipment_hooks_clean_exact_state() -> None:
    """Direct and condition-owned hooks both restore their exact baseline."""
    reset_item_state()
    entity = create_skeleton(
        name="Hook Auditor",
        position=(2, 2),
        darkvision=False,
    )
    defender_sword = _create_defender_sword(entity.uuid)
    base_ac = entity.equipment.ac_bonus.normalized_score

    assert entity.equipment.equip(
        defender_sword,
        WeaponSlot.MELEE_MAIN,
    )
    assert entity.equipment.ac_bonus.normalized_score == base_ac + 1
    assert (
        entity.equipment.unequip(WeaponSlot.MELEE_MAIN)
        is defender_sword
    )
    assert entity.equipment.ac_bonus.normalized_score == base_ac

    cloak = _create_cloak_of_protection(entity.uuid)
    base_saves = {
        ability: entity.saving_throws.get_saving_throw(
            ability
        ).bonus.normalized_score
        for ability in SAVE_ABILITIES
    }

    assert entity.equipment.equip(cloak)
    assert entity.equipment.ac_bonus.normalized_score == base_ac + 1
    assert CLOAK_PROTECTION_CONDITION_NAME in entity.active_conditions
    assert {
        ability: entity.saving_throws.get_saving_throw(
            ability
        ).bonus.normalized_score
        for ability in SAVE_ABILITIES
    } == {
        ability: score + 1
        for ability, score in base_saves.items()
    }

    assert entity.equipment.unequip(BodyPart.CLOAK) is cloak
    assert entity.equipment.ac_bonus.normalized_score == base_ac
    assert CLOAK_PROTECTION_CONDITION_NAME not in entity.active_conditions
    assert {
        ability: entity.saving_throws.get_saving_throw(
            ability
        ).bonus.normalized_score
        for ability in SAVE_ABILITIES
    } == base_saves
