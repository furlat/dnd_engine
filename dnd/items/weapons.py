"""Weapon factories and hook-bearing weapon test fixtures."""

import random
from typing import Optional
from uuid import UUID, uuid4

from dnd.blocks.equipment import Weapon, WeaponProperty, Range
from dnd.core.dice import DiceRoll, RollType, AdvantageStatus, CriticalStatus, AutoHitStatus
from dnd.core.events import (
    RangeType, Event, EventType, EventPhase, EventHandler, Trigger,
    DamageRollResultEvent, EquipmentSlot
)
from dnd.core.modifiers import DamageType, NumericalModifier
from dnd.core.values import ModifiableValue
from dnd.entity import Entity


def create_club(source_id: UUID) -> Weapon:
    """Create a club.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Simple melee weapon dealing 1d4 bludgeoning damage with Light.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Club",
        description="A simple wooden club.",
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_dagger(source_id: UUID) -> Weapon:
    """Create a dagger.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Simple melee weapon dealing 1d4 piercing damage with Finesse, Light, and
        Thrown metadata.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Dagger",
        description="A simple blade for quick strikes.",
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.THROWN],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_handaxe(source_id: UUID) -> Weapon:
    """Create a handaxe.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Simple melee weapon dealing 1d6 slashing damage with Light and Thrown.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Handaxe",
        description="A small axe that can be thrown.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.LIGHT, WeaponProperty.THROWN],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_javelin(source_id: UUID) -> Weapon:
    """Create a javelin.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Simple melee weapon dealing 1d6 piercing damage with Thrown metadata.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Javelin",
        description="A light spear designed for throwing.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.THROWN],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_mace(source_id: UUID) -> Weapon:
    """Create a mace.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Simple melee weapon dealing 1d6 bludgeoning damage.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Mace",
        description="A heavy headed club.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_quarterstaff(source_id: UUID) -> Weapon:
    """Create a quarterstaff.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Simple melee weapon dealing 1d6 bludgeoning damage with Versatile.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Quarterstaff",
        description="A wooden staff used as a weapon.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_spear(source_id: UUID) -> Weapon:
    """Create a spear.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Simple melee weapon dealing 1d6 piercing damage with Thrown and
        Versatile.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Spear",
        description="A pole weapon with a pointed tip.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.THROWN, WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )

def create_light_crossbow(source_id: UUID) -> Weapon:
    """Create a light crossbow.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Simple ranged weapon dealing 1d8 piercing damage at 80/320 feet.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Light Crossbow",
        description="A mechanical bow that fires bolts.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.RANGED, WeaponProperty.TWO_HANDED],
        range=Range(type=RangeType.RANGE, normal=80, long=320),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_shortbow(source_id: UUID) -> Weapon:
    """Create a shortbow.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Simple ranged weapon dealing 1d6 piercing damage at 80/320 feet.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Shortbow",
        description="A small bow suitable for quick shots.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.RANGED, WeaponProperty.TWO_HANDED],
        range=Range(type=RangeType.RANGE, normal=80, long=320),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )

def create_battleaxe(source_id: UUID) -> Weapon:
    """Create a battleaxe.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial melee weapon dealing 1d8 slashing damage with Versatile.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Battleaxe",
        description="A large axe suitable for battle.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.VERSATILE, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_greatsword(source_id: UUID) -> Weapon:
    """Create a greatsword.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial melee weapon dealing 2d6 slashing damage with Heavy and
        Two-Handed.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Greatsword",
        description="A massive two-handed sword.",
        damage_dice=6,
        dice_numbers=2,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.TWO_HANDED, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_greataxe(source_id: UUID) -> Weapon:
    """Create a greataxe.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial melee weapon dealing 1d12 slashing damage with Heavy and
        Two-Handed.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Greataxe",
        description="A massive two-handed axe favored by barbarians.",
        damage_dice=12,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.TWO_HANDED, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_longsword(source_id: UUID) -> Weapon:
    """Create a longsword.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial melee weapon dealing 1d8 slashing damage with Versatile.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Longsword",
        description="A versatile one-handed sword.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.VERSATILE, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_rapier(source_id: UUID) -> Weapon:
    """Create a rapier.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial melee weapon dealing 1d8 piercing damage with Finesse.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Rapier",
        description="A slender thrusting sword.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_scimitar(source_id: UUID) -> Weapon:
    """Create a scimitar.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial melee weapon dealing 1d6 slashing damage with Finesse and Light.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Scimitar",
        description="A curved slashing sword favored by goblins.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_shortsword(source_id: UUID) -> Weapon:
    """Create a shortsword.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial melee weapon dealing 1d6 piercing damage with Finesse and Light.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Shortsword",
        description="A short blade suitable for quick strikes.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_warhammer(source_id: UUID) -> Weapon:
    """Create a warhammer.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial melee weapon dealing 1d8 bludgeoning damage with Versatile.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Warhammer",
        description="A heavy hammer designed for combat.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.VERSATILE, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )

def create_longbow(source_id: UUID) -> Weapon:
    """Create a longbow.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial ranged weapon dealing 1d8 piercing damage at 150/600 feet.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Longbow",
        description="A tall bow capable of long-range shots.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.RANGED, WeaponProperty.TWO_HANDED, WeaponProperty.HEAVY, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.RANGE, normal=150, long=600),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_heavy_crossbow(source_id: UUID) -> Weapon:
    """Create a heavy crossbow.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Martial ranged weapon dealing 1d10 piercing damage at 100/400 feet.
    """
    return Weapon(
        source_entity_uuid=source_id,
        name="Heavy Crossbow",
        description="A powerful mechanical crossbow.",
        damage_dice=10,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.RANGED, WeaponProperty.TWO_HANDED, WeaponProperty.HEAVY, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.RANGE, normal=100, long=400),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )

def unseen_strike_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Add extra damage when the attacker is unseen by the target.

    Args:
        event: Event currently being processed.
        source_entity_uuid: Entity UUID that owns the unseen-strike handler.

    Returns:
        Mutated damage-roll event when the target cannot see the attacker;
        otherwise `None`.
    """
    if not isinstance(event, DamageRollResultEvent):
        return None
    if event.source_entity_uuid != source_entity_uuid:
        return None

    target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
    if not target or not isinstance(target, Entity):
        return None

    if source_entity_uuid in target.senses.entities:
        return None

    result = random.randint(1, 6)
    extra_roll = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.DAMAGE,
        results=[result],
        total=result,
        bonus=0,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=event.target_entity_uuid
    )
    event.final_rolls.append(extra_roll)
    event.roll_modifications.append(
        ("Unseen Strike", len(event.final_rolls) - 1, 0, result, "1d6 piercing (unseen attacker)")
    )
    return event


class UnseenStrikeDagger(Weapon):
    """Dagger that adds damage through a damage-roll-result handler."""
    _handler_uuid: Optional[UUID] = None

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Register the unseen-strike damage handler.

        Args:
            slot: Equipment slot receiving the dagger.
            entity_uuid: Entity UUID equipping the dagger.
        """
        entity = Entity.get(entity_uuid)
        if entity and isinstance(entity, Entity):
            handler = EventHandler(
                name="Unseen Strike",
                source_entity_uuid=entity_uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.DAMAGE_ROLL_RESULT,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=entity_uuid
                    )
                ],
                event_processor=unseen_strike_processor
            )
            entity.add_event_handler(handler)
            self._handler_uuid = handler.uuid

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Remove the unseen-strike damage handler.

        Args:
            slot: Equipment slot releasing the dagger.
            entity_uuid: Entity UUID unequipping the dagger.
        """
        if self._handler_uuid:
            handler = EventHandler.get(self._handler_uuid)
            if handler and isinstance(handler, EventHandler):
                entity = Entity.get(entity_uuid)
                if entity and isinstance(entity, Entity):
                    entity.remove_event_handler(handler)
            self._handler_uuid = None


def create_assassin_dagger(source_id: UUID) -> UnseenStrikeDagger:
    """Create an assassin's dagger.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Hook-bearing dagger that adds 1d6 damage when the target cannot see the
        attacker.
    """
    return UnseenStrikeDagger(
        source_entity_uuid=source_id,
        name="Assassin's Dagger",
        visual_item_name="Dagger",
        visual_variant_id="10000004",
        description=(
            "A shadowy blade that strikes harder when the target can't see you coming. "
            "+1d6 piercing when unseen."
        ),
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )

class ArcaneStaff(Weapon):
    """Quarterstaff that grants a spell-attack modifier while equipped."""
    _spell_mod_uuid: Optional[UUID] = None
    _spell_mod_value_uuid: Optional[UUID] = None

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Add the staff's spell-attack modifier.

        Args:
            slot: Equipment slot receiving the staff.
            entity_uuid: Entity UUID equipping the staff.
        """
        entity = Entity.get(entity_uuid)
        if entity and isinstance(entity, Entity):
            modifier = NumericalModifier(
                name="Arcane Staff",
                value=1,
                source_entity_uuid=entity_uuid,
                target_entity_uuid=entity_uuid
            )
            mod_uuid = entity.spellcasting.spell_attack_bonus.self_static.add_value_modifier(modifier)
            self._spell_mod_uuid = mod_uuid
            self._spell_mod_value_uuid = entity.spellcasting.spell_attack_bonus.uuid

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Remove the staff's spell-attack modifier.

        Args:
            slot: Equipment slot releasing the staff.
            entity_uuid: Entity UUID unequipping the staff.
        """
        if self._spell_mod_uuid and self._spell_mod_value_uuid:
            entity = Entity.get(entity_uuid)
            if entity and isinstance(entity, Entity):
                entity.spellcasting.spell_attack_bonus.self_static.remove_modifier(self._spell_mod_uuid)
            self._spell_mod_uuid = None
            self._spell_mod_value_uuid = None


def create_arcane_staff(source_id: UUID) -> ArcaneStaff:
    """Create an arcane staff.

    Args:
        source_id: Entity UUID that owns the weapon item.

    Returns:
        Hook-bearing quarterstaff that grants +1 to spell attack rolls while
        equipped.
    """
    return ArcaneStaff(
        source_entity_uuid=source_id,
        name="Arcane Staff",
        visual_item_name="Quarterstaff",
        visual_variant_id="1000000f",
        description="A staff crackling with arcane energy. +1 to spell attack rolls when equipped.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )
