"""Conjuration spells - creating objects and summoning creatures.

Contains: CallLightning
"""
from typing import Optional, List
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType, BaseAction, BaseCost, Cost
from dnd.core.dice import AttackOutcome
from dnd.core.events import EventPhase, RangeType, Range, EventType, EventHandler, Trigger, Damage, Event
from dnd.core.modifiers import DamageType

from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator


class CallLightningStrike(BaseAction):
    """Action granted by Call Lightning to strike with lightning each turn.

    This is NOT a spell - it's a special action granted while concentrating
    on Call Lightning. Uses an action, deals 3d10 lightning (DEX save).
    """
    name: str = Field(default="Call Lightning Strike")
    description: str = Field(default="Call down a bolt of lightning")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    costs: List[Cost] = Field(default_factory=lambda: [Cost(name="Strike Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])

    # Spell parameters passed from Call Lightning
    spell_dc: int = Field(default=10)
    damage_dice_count: int = Field(default=3)  # 3d10 base, +1d10 per upcast
    caster_uuid: Optional[UUID] = Field(default=None)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
    )

    def _create_event(self, **kwargs) -> Event:
        """Create a generic action event."""
        return Event(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            event_type=EventType.CAST_SPELL,
            event_phase=EventPhase.DECLARATION,
            **kwargs
        )

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        """Validate target is in range and LOS."""
        from dnd.entity import Entity

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        # Check caster is still concentrating on Call Lightning
        if "Concentrating" not in caster.active_conditions:
            return declaration_event.cancel(status_message="Not concentrating on Call Lightning")

        from dnd.conditions import Concentrating
        conc = caster.active_conditions.get("Concentrating")
        if not isinstance(conc, Concentrating) or conc.spell_name != "Call Lightning":
            return declaration_event.cancel(status_message="Not concentrating on Call Lightning")

        # Check LOS
        if target.uuid not in caster.senses.entities.keys():
            return declaration_event.cancel(status_message="Target not in line of sight")

        # Check range
        distance = caster.senses.get_feet_distance(target.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: Event) -> Optional[Event]:
        """Strike with lightning - DEX save for half damage."""
        from dnd.entity import Entity

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # Request DEX save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=self.spell_dc
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"DEX save: {save_roll.total} vs DC {self.spell_dc} - {'Success' if success else 'Failure'}"
        )

        # Roll damage: 3d10 + upcast dice
        damage_bonus = caster.get_spell_damage_bonus()
        lightning_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=self.damage_dice_count,
            damage_bonus=damage_bonus,
            damage_type=DamageType.LIGHTNING
        )

        damage_dice = lightning_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        # Half damage on save
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # Apply damage
        target.health.take_damage(final_damage, DamageType.LIGHTNING, source_entity_uuid=caster.uuid)

        save_text = " (save for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[lightning_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} dealt {final_damage} lightning damage{save_text}"
        )


class CallLightning(SpellAction):
    """Call Lightning - 3rd level Conjuration (Concentration)

    A storm cloud appears. When you cast the spell, choose a point you can see
    under the cloud. Each creature within 5 feet of that point must make a DEX
    saving throw. A creature takes 3d10 lightning damage on a failed save, or
    half as much on a successful one.

    On each of your turns until the spell ends, you can use your action to call
    down lightning in this way again, targeting the same point or a different one.

    At Higher Levels: Damage increases by 1d10 for each slot level above 3rd.
    """
    name: str = Field(default="Call Lightning")
    description: str = Field(default="Summon storm cloud, strike with lightning each turn")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="conjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
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
        """Cast Call Lightning - initial strike + grant repeatable action."""
        from dnd.entity import Entity
        from dnd.conditions import Concentrating

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # Calculate spell DC and damage dice
        dc = caster.spell_save_dc()
        damage_dice_count = 3 + self.get_upcast_bonus()  # 3d10 + 1d10 per upcast

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=f"Storm cloud appears - requesting DEX save DC {dc}"
        )

        # 1. Initial strike - DEX save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = effect_event.post(
            save_success=success,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        # Roll damage
        damage_bonus = caster.get_spell_damage_bonus()
        lightning_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=damage_dice_count,
            damage_bonus=damage_bonus,
            damage_type=DamageType.LIGHTNING
        )

        damage_dice = lightning_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        # Half damage on save
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # Apply damage
        target.health.take_damage(final_damage, DamageType.LIGHTNING, source_entity_uuid=caster.uuid)

        # 2. Register Call Lightning Strike action
        strike_action = CallLightningStrike(
            source_entity_uuid=caster.uuid,
            spell_dc=dc,
            damage_dice_count=damage_dice_count,
            caster_uuid=caster.uuid,
            template=True
        )
        caster.register_action(strike_action)

        # 3. Apply Concentrating condition (no linked effect - the action is the effect)
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Call Lightning"
            # No spell_effect_uuid - we handle cleanup via handler instead
        )
        caster.add_condition(concentration)

        # 4. Register cleanup handler to remove the action when concentration breaks
        self._register_action_cleanup(caster, strike_action.name)

        save_text = " (save for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[lightning_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} dealt {final_damage} lightning damage{save_text} - can strike again each turn"
        )

    def _register_action_cleanup(self, caster, action_name: str) -> None:
        """Register cleanup to remove Call Lightning Strike when concentration breaks."""
        from dnd.entity import Entity
        from dnd.core.events import EventQueue

        caster_uuid = caster.uuid

        def cleanup_processor(event, _source_entity_uuid: UUID):
            """When Concentrating on Call Lightning is removed, remove the strike action."""
            from dnd.conditions import Concentrating

            # Only trigger for caster's condition removal
            if event.target_entity_uuid != caster_uuid:
                return None

            # Check if this is the Concentrating condition for Call Lightning
            if not hasattr(event, 'condition'):
                return None

            condition = getattr(event, 'condition', None)
            if not condition:
                return None

            if not isinstance(condition, Concentrating):
                return None

            if condition.spell_name != "Call Lightning":
                return None

            # Remove the Call Lightning Strike action
            entity = Entity.get(caster_uuid)
            if entity:
                entity.unregister_action(action_name)

            return None

        cleanup_handler = EventHandler(
            name=f"Call Lightning Cleanup ({caster_uuid})",
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
