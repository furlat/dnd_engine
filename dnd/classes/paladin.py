"""Paladin class features.

Contains: Divine Smite (per-level handlers that add radiant damage on melee hit).
"""
from typing import Optional, List
from uuid import UUID

from dnd.core.base_actions import spell_slot_cost_type
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger,
    WeaponSlot, Damage, DamageRollResultEvent,
)
from dnd.core.dice import AttackOutcome
from dnd.core.modifiers import DamageType
from dnd.core.values import ModifiableValue

from dnd.entity import Entity


# =============================================================================
# DIVINE SMITE (Paladin Feature)
# =============================================================================

# Maximum smite dice (before crit doubling): 5d8
MAX_SMITE_DICE = 5


def _is_melee_weapon_slot(weapon_slot: WeaponSlot) -> bool:
    """Check if weapon slot is a melee slot."""
    return weapon_slot in (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF)


def create_divine_smite_processor(slot_level: int):
    """Create a closure-based processor for a specific spell slot level.

    Args:
        slot_level: The spell slot level this handler uses (1-5).

    Returns:
        EventProcessor callable for this smite level.
    """
    def divine_smite_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        """Divine Smite: on melee weapon hit, add radiant damage dice and consume spell slot."""
        # Must be a DamageRollResultEvent
        if not isinstance(event, DamageRollResultEvent):
            return None

        # Only trigger on own attacks
        if event.source_entity_uuid != source_entity_uuid:
            return None

        # Must be a melee weapon hit
        if not _is_melee_weapon_slot(event.weapon_slot):
            return None

        # Must be a hit or crit (not miss)
        if event.attack_outcome not in (AttackOutcome.HIT, AttackOutcome.CRIT):
            return None

        # Check if smite already applied this attack (flag in context)
        if event.context.get("divine_smite_applied"):
            return None

        # Check spell slot availability
        entity = Entity.get(source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return None

        if not entity.action_economy.can_afford(spell_slot_cost_type(slot_level), 1):
            return None

        # All checks passed — apply Divine Smite!

        # Calculate dice: 1 base + slot_level, capped at MAX_SMITE_DICE
        dice_count = min(1 + slot_level, MAX_SMITE_DICE)

        # Consume spell slot
        entity.action_economy.consume(spell_slot_cost_type(slot_level), 1)

        # Create smite damage
        smite_damage_bonus = ModifiableValue(
            source_entity_uuid=source_entity_uuid,
            name="Divine Smite Damage Bonus"
        )
        smite_damage = Damage(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.target_entity_uuid,
            name="Divine Smite",
            damage_dice=8,
            dice_numbers=dice_count,
            damage_bonus=smite_damage_bonus,
            damage_type=DamageType.RADIANT
        )

        # Roll the smite dice (crit auto-doubles via get_dice)
        smite_dice = smite_damage.get_dice(
            attack_outcome=event.attack_outcome,
            crit_extra_dice=0
        )
        smite_roll = smite_dice.roll

        # Append to damages and final_rolls
        event.damages.append(smite_damage)
        event.final_rolls.append(smite_roll)

        # Set flag to prevent lower-level handlers from also firing
        event.context["divine_smite_applied"] = True
        event.context["divine_smite_slot_level"] = slot_level
        event.context["divine_smite_dice_count"] = dice_count

        entity_name = entity.name if entity else "Unknown"
        return event.model_copy(update={
            "modified": True,
            "status_message": f"{entity_name} uses Divine Smite (L{slot_level} slot, {dice_count}d8 radiant)"
        })

    return divine_smite_processor


def create_divine_smite_handler(source_entity_uuid: UUID, slot_level: int) -> EventHandler:
    """Create a Divine Smite handler for a specific spell slot level.

    Args:
        source_entity_uuid: The entity UUID (paladin).
        slot_level: The spell slot level this handler covers (1-5).
    """
    return EventHandler(
        name=f"Divine Smite (L{slot_level})",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.DAMAGE_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=source_entity_uuid,
            )
        ],
        event_processor=create_divine_smite_processor(slot_level),
        player_toggleable=True
    )


def register_divine_smite(entity: Entity, max_slot_level: int = 5) -> List[EventHandler]:
    """Register Divine Smite handlers on an entity.

    Registers one handler per spell slot level from max_slot_level down to 1.
    Highest-level handler fires first (registered first → earlier in iteration order).
    Lower-level handlers skip due to the smite flag on the event context.

    Args:
        entity: The paladin entity.
        max_slot_level: Maximum spell slot level to register handlers for (default 5).

    Returns:
        List of registered EventHandler objects.
    """
    handlers: List[EventHandler] = []
    # Register highest first so it fires first
    for level in range(max_slot_level, 0, -1):
        handler = create_divine_smite_handler(entity.uuid, level)
        entity.add_event_handler(handler)
        handlers.append(handler)
    return handlers
