"""Enchantment spells - affecting minds and behavior.

Contains: HoldPerson, HoldPersonEffect
"""
from typing import Optional, List, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition
from dnd.core.events import Event, EventPhase, RangeType, Range, EventType, EventHandler, Trigger

from dnd.actions import SpellAction, SpellEvent
from dnd.entity import Entity
from dnd.conditions import Paralyzed

class HoldPersonEffect(BaseCondition):
    """
    The spell effect condition applied to the target of Hold Person.

    This condition:
    - Has Paralyzed as a sub-condition (same entity, auto-cleanup)
    - Can be targeted by Dispel Magic
    - Allows spell-specific immunity (immune to "Hold Person" but not all paralysis)
    - Is linked to caster's Concentrating via external_conditions

    When this condition is removed (by breaking concentration, dispel, or repeat save),
    the Paralyzed sub-condition is automatically removed.
    """
    name: str = "Hold Person"
    description: str = "Magically held in place"

    # Track the caster for repeat saves
    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], Optional[Event]]:
        

        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        if not isinstance(target, Entity):
            return [], [], [], declaration_event.cancel(status_message=f"Target is not an Entity")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        execution_event = declaration_event.phase_to(
            EventPhase.EXECUTION,
            update={"condition": self},
            status_message=f"Applying Paralyzed sub-condition to {target.name}"
        )

        # Apply Paralyzed as a sub-condition (same entity = existing mechanism)
        paralyzed = Paralyzed(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid  # Links child to parent
        )
        sub_condition_event = target.add_condition(paralyzed)

        if sub_condition_event is not None and sub_condition_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(paralyzed.uuid)

        # Register handler for repeat saves at end of target's turn
        if self.caster_uuid:
            handler = self._create_repeat_save_handler()
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Hold Person effect to {target.name}"
        )

        return [], handler_uuids, sub_condition_uuids, effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """Create handler for repeat WIS saves at end of target's turn."""
        from dnd.entity import Entity

        # Capture values for closure - these are validated before handler creation
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid: UUID = self.target_entity_uuid
        caster_uuid: UUID = self.caster_uuid
        effect_uuid: UUID = self.uuid
        dc: int = self.spell_dc

        def repeat_save_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            """At end of target's turn, allow repeat WIS save."""
            _ = source_entity_uuid  # Unused but required by signature

            # Only trigger for target's turn end
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            # Check if still affected by this Hold Person
            hold_person = target.active_conditions.get("Hold Person")
            if not hold_person or hold_person.uuid != effect_uuid:
                return None

            # Make repeat WIS save
            caster = Entity.get(caster_uuid)
            if not caster:
                # Caster gone, end the spell by removing the effect
                target.remove_condition("Hold Person")
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                # Remove concentration from caster - this will automatically
                # remove HoldPersonEffect via external_conditions, which removes Paralyzed via sub_conditions
                if "Concentrating" in caster.active_conditions:
                    from dnd.conditions import Concentrating
                    conc = caster.active_conditions.get("Concentrating")
                    if conc and isinstance(conc, Concentrating) and conc.spell_name == "Hold Person":
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

        Structure:
        - Caster: Concentrating(spell_name="Hold Person")
                      │
                      └── external_conditions ──► Target: HoldPersonEffect
                                                              │
                                                              └── sub_conditions ──► Paralyzed
        """
        from dnd.entity import Entity
        from dnd.conditions import Concentrating

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

        # 5. On failed save: apply HoldPersonEffect (which applies Paralyzed as sub-condition)
        hold_effect = HoldPersonEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        target.add_condition(hold_effect)

        # 6. Link Concentrating → HoldPersonEffect via external_conditions
        # When concentration breaks, HoldPersonEffect is removed, which removes Paralyzed
        concentration.add_external_condition(target.uuid, hold_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} - {target.name} is held (concentration)"
        )
