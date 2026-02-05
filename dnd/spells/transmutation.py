"""Transmutation spells - transforming matter and energy.

Contains: SpikeGrowth
"""
import random
from typing import Optional, List
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType, Cost
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger, Range, RangeType
)
from dnd.core.modifiers import DamageType
from dnd.entity import Entity
from dnd.conditions import Concentrating
from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator
from dnd.tile_conditions import ZoneControlCondition, parse_dice_string


class SpikeGrowthZone(ZoneControlCondition):
    """Zone control condition for Spike Growth spell.

    Creates a 20ft radius sphere of difficult terrain that deals
    2d4 piercing damage per 5ft traveled through it.

    Applied to the caster, manages the zone via position-indexed handlers.
    """
    name: str = "Spike Growth Zone"
    description: str = "Sharp spikes and thorns deal 2d4 piercing per 5ft traveled"

    # Zone configuration
    zone_shape: str = Field(default="sphere")
    zone_radius_feet: int = Field(default=20)
    adds_difficult_terrain: bool = Field(default=True)

    # Spell parameters
    spell_dc: int = Field(default=10, description="Spell DC for perception to notice")
    damage_dice: str = Field(default="2d4")

    def _has_entry_effect(self) -> bool:
        """Spike Growth damages entities when they enter."""
        return True

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry damage (2d4 piercing per tile entered)."""
        source_uuid = self.source_entity_uuid
        damage_dice = self.damage_dice

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            # Get entity from the spatial event
            entity_uuid = getattr(event, 'entity_uuid', None)
            if not entity_uuid:
                return None

            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            # Don't damage the caster
            if entity.uuid == source_uuid:
                return None

            # Roll and apply damage (using receive_damage for proper event firing)
            count, value = parse_dice_string(damage_dice)
            damage = sum(random.randint(1, value) for _ in range(count))
            entity.receive_damage(damage, DamageType.PIERCING, source_uuid)

            return None

        return EventHandler(
            name="Spike Growth Entry Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )


class SpikeGrowth(SpellAction):
    """Spike Growth - 2nd level Transmutation (Concentration)

    The ground in a 20-foot radius centered on a point within range
    twists and sprouts hard spikes and thorns. The area becomes difficult
    terrain for the duration. When a creature moves into or within the area,
    it takes 2d4 piercing damage for every 5 feet it travels.

    The transformation of the ground is camouflaged to look natural.
    Any creature that can't see the area at the time the spell is cast must
    make a Wisdom (Perception) check against your spell save DC to recognize
    the terrain as hazardous before entering it.

    Duration: Concentration, up to 10 minutes
    """
    name: str = Field(default="Spike Growth")
    description: str = Field(default="20ft radius difficult terrain, 2d4 piercing per 5ft traveled")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="transmutation")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=150)
    )

    # Action cost
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Spike Growth Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in range and visible."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        # Check visibility
        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        # Check range (150ft = 30 tiles)
        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Position out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Spike Growth - create zone and apply concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Spike Growth at {target_pos}"
        )

        # Create and apply the zone condition to the caster
        zone = SpikeGrowthZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc
        )
        caster.add_condition(zone)

        # Apply Concentrating condition
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Spike Growth"
        )
        caster.add_condition(concentration)

        # Link zone to concentration for cleanup
        concentration.add_external_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Spike Growth active: 20ft radius at {target_pos}, difficult terrain + 2d4 damage per 5ft"
        )
