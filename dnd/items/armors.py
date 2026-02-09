"""Armor factory functions for D&D 5e armors."""

from typing import Optional
from uuid import UUID
from dnd.blocks.equipment import BodyArmor, Shield, ArmorType
from dnd.core.events import BodyPart, EquipmentSlot
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus
from dnd.entity import Entity


class StealthDisadvantageBodyArmor(BodyArmor):
    """BodyArmor subclass that applies stealth disadvantage on equip.

    Uses _on_equip/_on_unequip hooks with proper Entity access.
    All armors with stealth_disadvantage=True should use this class.
    """
    _stealth_mod_uuid: Optional[UUID] = None
    _stealth_mod_value_uuid: Optional[UUID] = None

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity and isinstance(entity, Entity):
            self._stealth_mod_uuid = entity.skill_set.stealth.skill_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name=f"{self.name} Stealth Disadvantage",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=entity_uuid
                )
            )
            self._stealth_mod_value_uuid = entity.skill_set.stealth.skill_bonus.uuid

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        if self._stealth_mod_uuid:
            entity = Entity.get(entity_uuid)
            if entity and isinstance(entity, Entity):
                entity.skill_set.stealth.skill_bonus.self_static.remove_modifier(self._stealth_mod_uuid)
            self._stealth_mod_uuid = None
            self._stealth_mod_value_uuid = None


# =============================================================================
# LIGHT ARMOR
# =============================================================================

def create_padded_armor(source_id: UUID) -> StealthDisadvantageBodyArmor:
    """Padded - AC 11 + DEX, stealth disadvantage"""
    return StealthDisadvantageBodyArmor(
        source_entity_uuid=source_id,
        name="Padded Armor",
        description="Quilted layers of cloth and batting.",
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=11, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus"),
        stealth_disadvantage=True
    )


def create_leather_armor(source_id: UUID) -> BodyArmor:
    """Leather - AC 11 + DEX"""
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Leather Armor",
        description="Basic leather armor providing light protection.",
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=11, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


def create_studded_leather(source_id: UUID) -> BodyArmor:
    """Studded leather - AC 12 + DEX"""
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Studded Leather",
        description="Tough leather reinforced with close-set rivets.",
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=12, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


# =============================================================================
# MEDIUM ARMOR
# =============================================================================

def create_hide_armor(source_id: UUID) -> BodyArmor:
    """Hide - AC 12 + DEX (max 2)"""
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Hide Armor",
        description="Crude armor made from thick animal hides.",
        type=ArmorType.MEDIUM,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=12, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, value_name="Max Dex Bonus")
    )


def create_chain_shirt(source_id: UUID) -> BodyArmor:
    """Chain shirt - AC 13 + DEX (max 2)"""
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Chain Shirt",
        description="Interlocking metal rings forming a shirt.",
        type=ArmorType.MEDIUM,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=13, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, value_name="Max Dex Bonus")
    )


def create_scale_mail(source_id: UUID) -> StealthDisadvantageBodyArmor:
    """Scale mail - AC 14 + DEX (max 2), stealth disadvantage"""
    return StealthDisadvantageBodyArmor(
        source_entity_uuid=source_id,
        name="Scale Mail",
        description="Overlapping metal scales sewn to a leather coat.",
        type=ArmorType.MEDIUM,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=14, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, value_name="Max Dex Bonus"),
        stealth_disadvantage=True
    )


def create_breastplate(source_id: UUID) -> BodyArmor:
    """Breastplate - AC 14 + DEX (max 2)"""
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Breastplate",
        description="A fitted metal chest piece with leather straps.",
        type=ArmorType.MEDIUM,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=14, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, value_name="Max Dex Bonus")
    )


def create_half_plate(source_id: UUID) -> StealthDisadvantageBodyArmor:
    """Half plate - AC 15 + DEX (max 2), stealth disadvantage"""
    return StealthDisadvantageBodyArmor(
        source_entity_uuid=source_id,
        name="Half Plate",
        description="Shaped metal plates covering most of the body.",
        type=ArmorType.MEDIUM,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=15, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, value_name="Max Dex Bonus"),
        stealth_disadvantage=True
    )


# =============================================================================
# HEAVY ARMOR
# =============================================================================

def create_ring_mail(source_id: UUID) -> StealthDisadvantageBodyArmor:
    """Ring mail - AC 14, stealth disadvantage"""
    return StealthDisadvantageBodyArmor(
        source_entity_uuid=source_id,
        name="Ring Mail",
        description="Leather armor with heavy rings sewn into it.",
        type=ArmorType.HEAVY,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=14, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Max Dex Bonus"),
        stealth_disadvantage=True
    )


def create_chain_mail(source_id: UUID) -> StealthDisadvantageBodyArmor:
    """Chain mail - AC 16, STR 13 required, stealth disadvantage"""
    return StealthDisadvantageBodyArmor(
        source_entity_uuid=source_id,
        name="Chain Mail",
        description="Interlocking metal rings over quilted fabric.",
        type=ArmorType.HEAVY,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=16, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Max Dex Bonus"),
        strength_requirement=13,
        stealth_disadvantage=True
    )


def create_splint_armor(source_id: UUID) -> StealthDisadvantageBodyArmor:
    """Splint - AC 17, STR 15 required, stealth disadvantage"""
    return StealthDisadvantageBodyArmor(
        source_entity_uuid=source_id,
        name="Splint Armor",
        description="Narrow vertical strips of metal riveted to leather.",
        type=ArmorType.HEAVY,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=17, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Max Dex Bonus"),
        strength_requirement=15,
        stealth_disadvantage=True
    )


def create_plate_armor(source_id: UUID) -> StealthDisadvantageBodyArmor:
    """Plate - AC 18, STR 15 required, stealth disadvantage"""
    return StealthDisadvantageBodyArmor(
        source_entity_uuid=source_id,
        name="Plate Armor",
        description="Full plate armor providing maximum protection.",
        type=ArmorType.HEAVY,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=18, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Max Dex Bonus"),
        strength_requirement=15,
        stealth_disadvantage=True
    )


# =============================================================================
# CLOTH (No Armor)
# =============================================================================

def create_cloth_armor(source_id: UUID) -> BodyArmor:
    """Cloth - No AC bonus, counts as unarmored for class features."""
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Cloth Armor",
        description="Simple clothing that provides no protection.",
        type=ArmorType.CLOTH,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


# =============================================================================
# SHIELDS
# =============================================================================

def create_shield(source_id: UUID) -> Shield:
    """Shield - +2 AC"""
    return Shield(
        source_entity_uuid=source_id,
        name="Shield",
        description="A wooden or metal shield.",
        ac_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, value_name="Shield AC Bonus")
    )


def create_wooden_shield(source_id: UUID) -> Shield:
    """Wooden Shield - +2 AC (same as standard shield, distinct name)"""
    return Shield(
        source_entity_uuid=source_id,
        name="Wooden Shield",
        description="A crude wooden shield.",
        ac_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, value_name="Shield AC Bonus")
    )
