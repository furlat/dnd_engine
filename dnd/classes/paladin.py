"""Paladin class features.

Contains: Divine Smite (per-level handlers that add radiant damage on melee hit).
"""
from typing import Optional, List
from uuid import UUID

from dnd.core.base_actions import spell_slot_cost_type
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger,
    Damage, DamageRollResultEvent,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.dice import AttackOutcome
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.values import ModifiableValue
from dnd.core.base_conditions import SpellProtectionRegistry
from dnd.core.geometry import bresenham_line
from dnd.core.effect_types import EffectOrigin
from dnd.spells.content_metadata import srd_reaction_identity
from dnd.core.content.registration import get_content_declaration

from dnd.entity import Entity

MAX_SMITE_DICE = 5
MAX_SMITE_DICE_VS_UNDEAD_OR_FIEND = 6


def _is_melee_weapon_slot(weapon_slot: WeaponSlot) -> bool:
    """Check if weapon slot is a melee slot."""
    return weapon_slot in (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF)


def _target_grants_extra_smite_die(target_entity_uuid: Optional[UUID]) -> bool:
    """Return whether Divine Smite gains its creature-type bonus die."""
    if target_entity_uuid is None:
        return False

    target = Entity.get(target_entity_uuid)
    if not isinstance(target, Entity):
        return False

    return target.creature_type in (CreatureType.UNDEAD, CreatureType.FIEND)


def create_divine_smite_processor(slot_level: int):
    """Create a closure-based processor for a specific spell slot level.

    Args:
        slot_level: The spell slot level this handler uses (1-5).

    Returns:
        EventProcessor callable for this smite level.
    """
    def divine_smite_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        """Divine Smite: on melee weapon hit, add radiant damage dice and consume spell slot."""
        if not isinstance(event, DamageRollResultEvent):
            return None

        if event.source_entity_uuid != source_entity_uuid:
            return None

        if event.attack_kind!="weapon" or event.weapon_slot is None or not _is_melee_weapon_slot(event.weapon_slot):
            return None

        if event.attack_outcome not in (AttackOutcome.HIT, AttackOutcome.CRIT):
            return None

        if event.context is not None and event.context.get("divine_smite_applied"):
            return None

        if event.target_entity_uuid is None or Entity.get(event.target_entity_uuid) is None:
            return None

        entity = Entity.get(source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return None

        if entity.is_spellcasting_blocked() and entity.uuid not in entity.spellcasting.divine_smite_entitlements:
            return None
        if not entity.action_economy.can_afford(spell_slot_cost_type(slot_level), 1):
            return None

        target=Entity.get(event.target_entity_uuid)
        if target is None or SpellProtectionRegistry.is_protected(target.position,entity.position,1) or SpellProtectionRegistry.get_antimagic_suppressions(set(bresenham_line(entity.position,target.position))):
            return None
        if any(level>slot_level and (handler:=entity.event_handlers.get(identity)) is not None
                and handler.enabled and entity.action_economy.can_afford(spell_slot_cost_type(level),1)
                for level,identity in entity.spellcasting.divine_smite_handler_uuids.items()):
            return None
        creature_type_bonus = 1 if _target_grants_extra_smite_die(event.target_entity_uuid) else 0
        dice_count = min(
            min(1 + slot_level, MAX_SMITE_DICE) + creature_type_bonus,
            MAX_SMITE_DICE_VS_UNDEAD_OR_FIEND,
        )

        entity.action_economy.consume(spell_slot_cost_type(slot_level), 1)

        smite_damage_bonus = ModifiableValue(
            source_entity_uuid=source_entity_uuid,
            name="Divine Smite Damage Bonus"
        )
        smite_damage = Damage(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.target_entity_uuid,
            name="Divine Smite",
            effect_origin=EffectOrigin.spell(source_id="spell.divine_smite",source_event_lineage_uuid=str(event.lineage_uuid),
                source_position=entity.position,base_spell_level=1,effective_spell_level=slot_level),
            damage_dice=8,
            dice_numbers=dice_count,
            damage_bonus=smite_damage_bonus,
            damage_type=DamageType.RADIANT
        )

        smite_dice = smite_damage.get_dice(
            attack_outcome=event.attack_outcome,
            crit_extra_dice=0
        )
        smite_roll = smite_dice.roll

        modified_event = event.append_damage_roll(
            smite_damage,
            smite_roll,
            "Divine Smite",
            f"Level {slot_level} spell slot",
        )
        context = {
            **(modified_event.context or {}),
            "divine_smite_applied": True,
            "divine_smite_slot_level": slot_level,
            "divine_smite_dice_count": dice_count,
            "divine_smite_creature_type_bonus": creature_type_bonus,
        }

        entity_name = entity.name if entity else "Unknown"
        return modified_event.with_updates(
            context=context,
            status_message=(
                f"{entity_name} uses Divine Smite "
                f"(L{slot_level} slot, {dice_count}d8 radiant)"
            ),
        )

    return divine_smite_processor


class DivineSmiteHandler(EventHandler):
    """One authored reaction whose selected spell-slot level remains runtime data."""


def create_divine_smite_handler(
    source_entity_uuid: UUID,
    slot_level: int,
) -> DivineSmiteHandler:
    """Create a Divine Smite handler for a specific spell slot level.

    Args:
        source_entity_uuid: The entity UUID (paladin).
        slot_level: The spell slot level this handler covers (1-5).
    """
    return DivineSmiteHandler(
        name=f"Divine Smite (L{slot_level})",
        semantic_key="reaction.class_feature.paladin.divine_smite",
        content_kind=RuntimeBehaviorKind.REACTION,
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


def register_divine_smite(entity: Entity, max_slot_level: int = 5, *, entitlement_uuid: UUID | None=None) -> List[EventHandler]:
    """Register Divine Smite handlers on an entity.

    Feature and learned origins share one toggle per entitled slot level.
    Each processor selects the highest enabled affordable level independently
    of registration order; the hit context prevents duplicate payment.

    Args:
        entity: The paladin entity.
        max_slot_level: Maximum spell slot level to register handlers for (default 5).

    Returns:
        List of registered EventHandler objects.
    """
    entity.spellcasting.divine_smite_entitlements[entitlement_uuid or entity.uuid]=max_slot_level
    handlers: List[EventHandler] = []
    for level in range(max_slot_level, 0, -1):
        identity=entity.spellcasting.divine_smite_handler_uuids.get(level)
        existing=entity.event_handlers.get(identity) if identity is not None else None
        if existing is not None:
            handlers.append(existing)
            continue
        handler = create_divine_smite_handler(entity.uuid, level)
        entity.add_event_handler(handler)
        entity.spellcasting.divine_smite_handler_uuids[level]=handler.uuid
        handlers.append(handler)
    return handlers


def unregister_divine_smite(entity: Entity,entitlement_uuid: UUID) -> None:
    """Remove only this entitlement; feature and learned spell share five toggles."""
    entity.spellcasting.divine_smite_entitlements.pop(entitlement_uuid,None)
    maximum=max(entity.spellcasting.divine_smite_entitlements.values(),default=0)
    for level,identity in tuple(entity.spellcasting.divine_smite_handler_uuids.items()):
        if level<=maximum:
            continue
        handler=entity.event_handlers.get(identity)
        if handler is not None:
            entity.remove_event_handler(handler)
            handler.remove_from_register()
        entity.spellcasting.divine_smite_handler_uuids.pop(level,None)


@srd_reaction_identity(content_id="reaction.spell.divine_smite",display_name="Divine Smite Entitlement",
    description="Knowing Divine Smite supplies the shared automatic per-slot toggles.",
    source_page=None,srd_version="5.2",sort_order=3020,
    adaptation_notes="BG3 automatic on-hit adaptation; five existing slot toggles, no accept-reaction UI.")
class LearnedDivineSmiteHandler(EventHandler):
    """Own the learned spell's entitlement without a second damage processor."""
    def on_admitted(self) -> None:
        caster=Entity.get(self.source_entity_uuid)
        if caster is not None:
            register_divine_smite(caster,entitlement_uuid=self.uuid)

    def on_removed(self) -> None:
        caster=Entity.get(self.source_entity_uuid)
        if caster is not None:
            unregister_divine_smite(caster,self.uuid)


def create_learned_divine_smite_handler(source_entity_uuid: UUID) -> LearnedDivineSmiteHandler:
    return LearnedDivineSmiteHandler(name="Divine Smite Entitlement",source_entity_uuid=source_entity_uuid,
        trigger_conditions=[],event_processor=lambda event,source:None,player_toggleable=False,
        content_kind=RuntimeBehaviorKind.REACTION,semantic_key="reaction.spell.divine_smite")

DIVINE_SMITE_REACTION_DECLARATION=get_content_declaration(LearnedDivineSmiteHandler)
