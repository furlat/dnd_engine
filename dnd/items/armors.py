"""Armor factory functions for D&D 5e armors."""

from typing import Optional
from uuid import UUID
from dnd.blocks.equipment import BodyArmor, Boots, Helmet, Shield, ArmorType
from dnd.core.events import BodyPart, EquipmentSlot
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, ContextualNumericalModifier, NumericalModifier
from dnd.entity import Entity


def heavy_armor_strength_penalty(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None,
) -> Optional[NumericalModifier]:
    """Return the heavy-armor movement penalty when Strength is too low.

    Args:
        source_entity_uuid: Entity wearing the armor.
        target_entity_uuid: Unused contextual target UUID.
        context: Unused contextual data.

    Returns:
        A `NumericalModifier` for -10 feet of speed when the wearer does not
        meet the armor Strength requirement; otherwise `None`.
    """
    _ = target_entity_uuid, context
    entity = Entity.get(source_entity_uuid)
    if entity is None:
        return None
    body_armor = entity.equipment.body_armor
    if body_armor is None or body_armor.strength_requirement is None:
        return None
    strength_score = entity.ability_scores.strength.ability_score.score
    if strength_score >= body_armor.strength_requirement:
        return None
    return NumericalModifier(
        name=f"{body_armor.name} Strength Requirement",
        value=-10,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=source_entity_uuid,
    )


class StealthDisadvantageBodyArmor(BodyArmor):
    """BodyArmor subclass that applies stealth disadvantage on equip.

    Armors with `stealth_disadvantage=True` use this hook-bearing subclass so
    equip and unequip can add and remove the stealth and heavy-armor movement
    modifiers through the owning entity.
    """
    _stealth_mod_uuid: Optional[UUID] = None
    _stealth_mod_value_uuid: Optional[UUID] = None
    _movement_mod_uuid: Optional[UUID] = None
    _movement_mod_value_uuid: Optional[UUID] = None

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
            if self.strength_requirement is not None:
                modifier = ContextualNumericalModifier(
                    name=f"{self.name} Strength Requirement",
                    source_entity_uuid=entity_uuid,
                    target_entity_uuid=entity_uuid,
                    callable=heavy_armor_strength_penalty,
                )
                self._movement_mod_uuid = entity.action_economy.movement.self_contextual.add_value_modifier(modifier)
                self._movement_mod_value_uuid = entity.action_economy.movement.uuid

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        if self._stealth_mod_uuid:
            entity = Entity.get(entity_uuid)
            if entity and isinstance(entity, Entity):
                entity.skill_set.stealth.skill_bonus.self_static.remove_modifier(self._stealth_mod_uuid)
            self._stealth_mod_uuid = None
            self._stealth_mod_value_uuid = None
        if self._movement_mod_uuid:
            entity = Entity.get(entity_uuid)
            if entity and isinstance(entity, Entity):
                entity.action_economy.movement.self_contextual.remove_value_modifier(self._movement_mod_uuid)
            self._movement_mod_uuid = None
            self._movement_mod_value_uuid = None


def create_padded_armor(source_id: UUID) -> StealthDisadvantageBodyArmor:
    """Create padded armor.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Light armor with AC 11 plus Dexterity and Stealth disadvantage.
    """
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
    """Create leather armor.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Light armor with AC 11 plus Dexterity.
    """
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
    """Create studded leather armor.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Light armor with AC 12 plus Dexterity.
    """
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Studded Leather",
        description="Tough leather reinforced with close-set rivets.",
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=12, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


def create_hide_armor(source_id: UUID) -> BodyArmor:
    """Create hide armor.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Medium armor with AC 12 plus Dexterity, capped at +2.
    """
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
    """Create a chain shirt.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Medium armor with AC 13 plus Dexterity, capped at +2.
    """
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
    """Create scale mail.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Medium armor with AC 14 plus Dexterity capped at +2, and Stealth
        disadvantage.
    """
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
    """Create a breastplate.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Medium armor with AC 14 plus Dexterity, capped at +2.
    """
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
    """Create half plate.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Medium armor with AC 15 plus Dexterity capped at +2, and Stealth
        disadvantage.
    """
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


def create_ring_mail(source_id: UUID) -> StealthDisadvantageBodyArmor:
    """Create ring mail.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Heavy armor with AC 14 and Stealth disadvantage.
    """
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
    """Create chain mail.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Heavy armor with AC 16, Strength 13 requirement, and Stealth
        disadvantage.
    """
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
    """Create splint armor.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Heavy armor with AC 17, Strength 15 requirement, and Stealth
        disadvantage.
    """
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
    """Create plate armor.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Heavy armor with AC 18, Strength 15 requirement, and Stealth
        disadvantage.
    """
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


def create_cloth_armor(source_id: UUID) -> BodyArmor:
    """Create cloth armor.

    Args:
        source_id: Entity UUID that owns the armor item.

    Returns:
        Cloth body armor that counts as unarmored for class features.
    """
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Cloth Armor",
        description="Simple clothing that provides no protection.",
        type=ArmorType.CLOTH,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


def create_robes(source_id: UUID, visual_variant_id: Optional[str] = None) -> BodyArmor:
    """Create robes.

    Args:
        source_id: Entity UUID that owns the armor item.
        visual_variant_id: Optional visual variant identifier.

    Returns:
        Cloth body outfit that counts as unarmored for class features.
    """
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Robes",
        visual_item_name="Robes" if visual_variant_id is not None else None,
        visual_variant_id=visual_variant_id,
        description="Cloth robes suitable for an arcane caster.",
        type=ArmorType.CLOTH,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


def create_cloth_shoes(source_id: UUID, visual_variant_id: Optional[str] = None) -> Boots:
    """Create cloth shoes.

    Args:
        source_id: Entity UUID that owns the boots.
        visual_variant_id: Optional visual variant identifier.

    Returns:
        Cloth footwear with no armor bonus.
    """
    return Boots(
        source_entity_uuid=source_id,
        name="Cloth Shoes",
        visual_item_name="Cloth Shoes" if visual_variant_id is not None else None,
        visual_variant_id=visual_variant_id,
        description="Soft cloth shoes.",
        type=ArmorType.CLOTH,
        body_part=BodyPart.FEET,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


def create_leather_boots(source_id: UUID, visual_variant_id: Optional[str] = None) -> Boots:
    """Create leather boots.

    Args:
        source_id: Entity UUID that owns the boots.
        visual_variant_id: Optional visual variant identifier.

    Returns:
        Leather footwear with no armor bonus.
    """
    return Boots(
        source_entity_uuid=source_id,
        name="Leather Boots",
        visual_item_name="Leather Boots" if visual_variant_id is not None else None,
        visual_variant_id=visual_variant_id,
        description="Sturdy leather adventuring boots.",
        type=ArmorType.LIGHT,
        body_part=BodyPart.FEET,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


def create_iron_helmet(source_id: UUID, visual_variant_id: Optional[str] = None) -> Helmet:
    """Create an iron helmet.

    Args:
        source_id: Entity UUID that owns the helmet.
        visual_variant_id: Optional visual variant identifier.

    Returns:
        Heavy headgear with no armor bonus.
    """
    return Helmet(
        source_entity_uuid=source_id,
        name="Iron Helmet",
        visual_item_name="Iron Helmet" if visual_variant_id is not None else None,
        visual_variant_id=visual_variant_id,
        description="A sturdy metal helmet.",
        type=ArmorType.HEAVY,
        body_part=BodyPart.HEAD,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


def create_wizard_hat(source_id: UUID, visual_variant_id: Optional[str] = None) -> Helmet:
    """Create a wizard hat.

    Args:
        source_id: Entity UUID that owns the hat.
        visual_variant_id: Optional visual variant identifier.

    Returns:
        Cloth headgear with no armor bonus.
    """
    return Helmet(
        source_entity_uuid=source_id,
        name="Wizard's Hat",
        visual_item_name="Wizard's Hat" if visual_variant_id is not None else None,
        visual_variant_id=visual_variant_id,
        description="A pointy cloth hat favored by arcane casters.",
        type=ArmorType.CLOTH,
        body_part=BodyPart.HEAD,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


def create_crown(source_id: UUID, visual_variant_id: Optional[str] = None) -> Helmet:
    """Create a crown.

    Args:
        source_id: Entity UUID that owns the crown.
        visual_variant_id: Optional visual variant identifier.

    Returns:
        Decorative headgear with no armor bonus.
    """
    return Helmet(
        source_entity_uuid=source_id,
        name="Crown",
        visual_item_name="Crown" if visual_variant_id is not None else None,
        visual_variant_id=visual_variant_id,
        description="A decorative crown.",
        type=ArmorType.CLOTH,
        body_part=BodyPart.HEAD,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=10, value_name="Max Dex Bonus")
    )


def create_shield(source_id: UUID) -> Shield:
    """Create a standard shield.

    Args:
        source_id: Entity UUID that owns the shield.

    Returns:
        Shield with +2 AC.
    """
    return Shield(
        source_entity_uuid=source_id,
        name="Shield",
        description="A wooden or metal shield.",
        ac_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, value_name="Shield AC Bonus")
    )


def create_wooden_shield(source_id: UUID) -> Shield:
    """Create a wooden shield.

    Args:
        source_id: Entity UUID that owns the shield.

    Returns:
        Shield with +2 AC and a distinct display name.
    """
    return Shield(
        source_entity_uuid=source_id,
        name="Wooden Shield",
        description="A crude wooden shield.",
        ac_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=2, value_name="Shield AC Bonus")
    )
