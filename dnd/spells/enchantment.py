"""Enchantment spells - affecting minds and behavior.

Contains: HoldPerson
"""
from typing import Optional
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.events import EventPhase, RangeType, Range, EventType, EventHandler, Trigger

from dnd.actions import SpellAction, SpellEvent


class HoldPerson(SpellAction):
    """Hold Person - 2nd level Enchantment (Concentration)

    Choose a humanoid that you can see within range. The target must succeed
    on a Wisdom saving throw or be paralyzed for the duration. At the end of
    each of its turns, the target can make another Wisdom saving throw.
    On a success, the spell ends on the target.

    At Higher Levels: Target one additional humanoid per slot level above 2nd.
    (Note: Multi-target not yet implemented)
    """
    name: str = Field(default="Hold Person")
    description: str = Field(default="Target must succeed on WIS save or be paralyzed")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="enchantment")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""
        from dnd.entity import Entity
        from dnd.spells.evocation import validate_line_of_sight

        # Validate line of sight
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        # Validate range
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = source_entity.senses.get_feet_distance(target_entity.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute Hold Person - WIS save or Paralyzed.

        IMPORTANT: Concentration begins when the spell is cast, BEFORE the save.
        This ensures casting a concentration spell always breaks existing concentration,
        even if the target succeeds on their save.
        """
        from dnd.entity import Entity
        from dnd.conditions import Paralyzed, Concentrating

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Apply Concentrating condition FIRST (breaks existing concentration)
        # This happens regardless of whether the target saves
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Hold Person"
            # spell_effect_uuid will be set later if target fails save
        )
        caster.add_condition(concentration)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            status_message=f"Requesting WIS save DC {dc}"
        )

        # 3. Request WIS save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = effect_event.post(
            save_success=success,
            status_message=f"WIS save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        # 4. On successful save: spell has no effect (but concentration is active)
        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} - target saved (still concentrating)"
            )

        # 5. On failed save: apply Paralyzed condition
        paralyzed = Paralyzed(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(paralyzed)

        # 6. Update concentration with linked spell effect
        concentration.spell_effect_uuid = paralyzed.uuid
        concentration.spell_effect_target_uuid = target.uuid

        # 7. Register handler for repeat saves at end of target's turn
        handler = self._create_repeat_save_handler(caster.uuid, target.uuid, paralyzed.uuid, dc)
        target.add_event_handler(handler)

        # Store handler UUID on the concentration so it can be cleaned up
        # We'll add the handler to be removed when concentration breaks
        self._register_handler_cleanup(caster, handler.uuid, paralyzed.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} - {target.name} is Paralyzed (concentration)"
        )

    def _create_repeat_save_handler(
        self, caster_uuid: UUID, target_uuid: UUID, paralyzed_uuid: UUID, dc: int
    ) -> EventHandler:
        """Create handler for repeat WIS saves at end of target's turn."""
        from dnd.entity import Entity

        def repeat_save_processor(event, source_entity_uuid: UUID) -> Optional[SpellEvent]:
            """At end of target's turn, allow repeat WIS save."""
            # Only trigger for target's turn end
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            # Check if still paralyzed by this spell
            paralyzed = target.active_conditions.get("Paralyzed")
            if not paralyzed or paralyzed.uuid != paralyzed_uuid:
                return None

            # Make repeat WIS save
            caster = Entity.get(caster_uuid)
            if not caster:
                # Caster gone, end the spell
                target.remove_condition("Paralyzed")
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc
            )
            _, save_roll, success = target.saving_throw(save_request)

            if success:
                # Remove paralyzed - this will also break caster's concentration
                # via the linked spell effect
                target.remove_condition("Paralyzed")

                # Also remove concentration from caster
                if "Concentrating" in caster.active_conditions:
                    from dnd.conditions import Concentrating as ConcentratingCond
                    conc = caster.active_conditions.get("Concentrating")
                    if conc and isinstance(conc, ConcentratingCond) and conc.spell_effect_uuid == paralyzed_uuid:
                        caster.remove_condition("Concentrating")

            return None

        return EventHandler(
            name=f"Hold Person Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=repeat_save_processor
        )

    def _register_handler_cleanup(self, caster, handler_uuid: UUID, _paralyzed_uuid: UUID) -> None:
        """Register cleanup to remove repeat save handler when concentration breaks."""
        from dnd.core.events import EventQueue

        caster_uuid = caster.uuid

        def cleanup_processor(event, _source_entity_uuid: UUID):
            """When Concentrating is removed, clean up the repeat save handler."""
            from dnd.conditions import Concentrating

            # Only trigger for caster's condition removal
            if event.target_entity_uuid != caster_uuid:
                return None

            # Check if this is the Concentrating condition for Hold Person
            if not hasattr(event, 'condition'):
                return None

            condition = getattr(event, 'condition', None)
            if not condition:
                return None

            if not isinstance(condition, Concentrating):
                return None

            if condition.spell_name != "Hold Person":
                return None

            # Remove the repeat save handler from the target
            if condition.spell_effect_target_uuid:
                # Use EventQueue to remove by UUID
                EventQueue.remove_event_handlers_by_uuid(handler_uuid)

            return None

        cleanup_handler = EventHandler(
            name=f"Hold Person Cleanup ({caster_uuid})",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_REMOVAL,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=cleanup_processor
        )

        caster.add_event_handler(cleanup_handler)
