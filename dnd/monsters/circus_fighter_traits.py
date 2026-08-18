"""Runtime evaluators for the authored Circus Fighter's intrinsic traits."""

from typing import Any, Optional
from uuid import UUID

from dnd.blocks.equipment import Weapon
from dnd.core.modifiers import AdvantageModifier, NumericalModifier
from dnd.entities.entity import Entity
from dnd.types.damage import DamageType
from dnd.types.equipment import WeaponProperty
from dnd.types.rolls import AdvantageStatus


def elemental_weapon_advantage(
    source_uuid: UUID,
    target_uuid: Optional[UUID],
    context: Optional[dict[str, Any]],
) -> Optional[AdvantageModifier]:
    """Grant attack advantage while either melee hand is elemental."""
    _ = context
    source = Entity.get(source_uuid)
    if not isinstance(source, Entity):
        return None
    elemental_types = {
        DamageType.ACID,
        DamageType.COLD,
        DamageType.FIRE,
        DamageType.LIGHTNING,
        DamageType.POISON,
        DamageType.THUNDER,
    }
    for weapon in (
        source.equipment.weapon_melee_main,
        source.equipment.weapon_melee_off,
    ):
        if not isinstance(weapon, Weapon):
            continue
        if (
            weapon.damage_type in elemental_types
            or any(row in elemental_types for row in weapon.extra_damage_type)
        ):
            return AdvantageModifier(
                source_entity_uuid=source_uuid,
                target_entity_uuid=target_uuid,
                name="Elemental Weapon",
                value=AdvantageStatus.ADVANTAGE,
            )
    return None


def dual_wielder_ac_bonus(
    source_uuid: UUID,
    target_uuid: Optional[UUID],
    context: Optional[dict[str, Any]],
) -> Optional[NumericalModifier]:
    """Grant +1 AC while both melee hands hold non-ranged weapons."""
    _ = context
    source = Entity.get(source_uuid)
    if not isinstance(source, Entity):
        return None
    main_hand = source.equipment.weapon_melee_main
    off_hand = source.equipment.weapon_melee_off
    if not isinstance(main_hand, Weapon) or not isinstance(off_hand, Weapon):
        return None
    if (
        WeaponProperty.RANGED in main_hand.properties
        or WeaponProperty.RANGED in off_hand.properties
    ):
        return None
    return NumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        name="Dual Wielder AC Bonus",
        value=1,
    )


__all__ = ["dual_wielder_ac_bonus", "elemental_weapon_advantage"]
