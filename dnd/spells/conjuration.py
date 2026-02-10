"""Conjuration spells - creating objects and summoning creatures.

Contains: CallLightning, PoisonSpray, AcidSplash, Grease, Web
"""
import random
from typing import Optional, List, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType, BaseAction, Cost, ActionEvent, BaseCost
from dnd.core.base_conditions import BaseCondition, ConditionRemovalEvent
from dnd.core.dice import AttackOutcome
from dnd.core.events import EventPhase, RangeType, Range, EventType, EventHandler, Trigger, Damage, Event, EventQueue, SkillCheckEvent, SpatialChangeEvent
from dnd.core.modifiers import DamageType, NumericalModifier
from dnd.core.base_tiles import LightLevel
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.conditions import Concentrating, Prone, Restrained
from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator, entity_action_economy_cost_applier
from dnd.tile_conditions import ZoneControlCondition
from dnd.spells.evocation import validate_line_of_sight


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
            phase=EventPhase.DECLARATION,
            **kwargs
        )

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        """Validate target is in range and LOS."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        # Check caster is still concentrating on Call Lightning
        if "Concentrating" not in caster.active_conditions:
            return declaration_event.cancel(status_message="Not concentrating on Call Lightning")

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

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # Request DEX save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=self.spell_dc,
            parent_event=execution_event.uuid
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

        # Apply damage (child of effect event)
        target.receive_damage(
            amount=final_damage,
            damage_type=DamageType.LIGHTNING,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

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

        # 1. Initial strike - DEX save (child of effect event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=effect_event.uuid
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

        # Apply damage (child of effect event)
        target.receive_damage(
            amount=final_damage,
            damage_type=DamageType.LIGHTNING,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

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
        caster.add_condition(concentration, parent_event=effect_event)

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

        caster_uuid = caster.uuid

        def cleanup_processor(event, _source_entity_uuid: UUID):
            """When Concentrating on Call Lightning is removed, remove the strike action."""
    
            # Only trigger for caster's condition removal
            if event.target_entity_uuid != caster_uuid:
                return None

            # Check if this is the Concentrating condition for Call Lightning
            if not isinstance(event, ConditionRemovalEvent):
                return None

            if not isinstance(event.condition, Concentrating):
                return None

            if event.condition.spell_name != "Call Lightning":
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


class PoisonSpray(SpellAction):
    """Poison Spray - Conjuration Cantrip

    Range 10ft, CON save or 1d12 poison damage.
    Scales: 2d12 at 5th, 3d12 at 11th, 4d12 at 17th.
    """
    name: str = Field(default="Poison Spray")
    description: str = Field(default="CON save or 1d12 poison (10ft range)")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="conjuration")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=10))

    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="enemies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate LOS and 10ft range."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return declaration_event.cancel(status_message="Entity not found")

        distance = source.senses.get_feet_distance(target.position)
        if distance > 10:  # 10ft range
            return declaration_event.cancel(status_message=f"Out of range ({distance}ft > 10ft)")

        return los_event.phase_to(EventPhase.EXECUTION, status_message="Validated Poison Spray")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """CON save or poison damage."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Entity not found")

        dc = caster.spell_save_dc()

        # CON save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, _save_roll, success = target.saving_throw(save_request)

        if success:
            return execution_event.phase_to(
                EventPhase.COMPLETION,
                save_success=True,
                total_damage=0,
                status_message=f"{target.name} saves against Poison Spray"
            )

        # Roll damage - cantrip scaling
        num_dice = self._get_cantrip_dice_count(self.caster_level)
        damage_bonus = caster.get_spell_damage_bonus()

        poison_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=12,  # d12
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.POISON
        )

        damage_dice = poison_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        # Apply damage (child of execution event since no separate effect phase)
        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.POISON,
            source_entity_uuid=caster.uuid,
            parent_event=execution_event.uuid
        )

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            save_success=False,
            damages=[poison_damage],
            damage_rolls=[damage_roll],
            total_damage=damage_roll.total,
            status_message=f"Poison Spray: {damage_roll.total} poison to {target.name}"
        )


class AcidSplash(SpellAction):
    """Acid Splash - Conjuration cantrip

    You hurl a bubble of acid. Choose one or two creatures you can see
    within range. If you choose two, they must be within 5 feet of each other.
    A target must succeed on a DEX save or take 1d6 acid damage.

    Damage scales: 2d6 at 5th, 3d6 at 11th, 4d6 at 17th.
    """
    name: str = Field(default="Acid Splash")
    description: str = Field(default="1-2 targets within 5ft of each other, DEX save or 1d6 acid")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="conjuration")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))

    # Multi-entity configuration
    allow_same_target: bool = Field(default=False)  # Can't hit same target twice
    valid_target_filter: str = Field(default="enemies")

    include_self: bool = Field(default=False)

    def get_num_projectiles(self) -> int:
        """1-2 targets (max 2)."""
        return min(2, 1 + len(self.extra_target_entity_uuids))

    def get_all_targets(self) -> List[UUID]:
        """Return all targets (1-2)."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)
        return targets[:2]  # Max 2 targets

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range, LOS, and 5ft proximity for 2-target case."""
        source = Entity.get(self.source_entity_uuid)
        if not source:
            return declaration_event.cancel(status_message="Caster not found")

        all_targets = self.get_all_targets()
        if not all_targets:
            return declaration_event.cancel(status_message="No targets specified")

        target_entities = []
        for target_uuid in all_targets:
            target = Entity.get(target_uuid)
            if not target:
                return declaration_event.cancel(status_message="Target not found")

            # Check LOS
            if target_uuid not in source.senses.entities.keys():
                return declaration_event.cancel(status_message=f"{target.name} not in line of sight")

            # Check range
            distance = source.senses.get_feet_distance(target.position)
            if distance > self.spell_range.normal:
                return declaration_event.cancel(
                    status_message=f"{target.name} out of range ({distance}ft > {self.spell_range.normal}ft)"
                )
            target_entities.append(target)

        # If 2 targets, check they're within 5ft of each other
        if len(target_entities) == 2:
            t1, t2 = target_entities
            dx = abs(t1.position[0] - t2.position[0])
            dy = abs(t1.position[1] - t2.position[1])
            # 5ft = 1 tile in grid
            if dx > 1 or dy > 1:
                return declaration_event.cancel(
                    status_message=f"Targets must be within 5ft of each other (distance: {max(dx, dy) * 5}ft)"
                )

        # Call parent validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply acid splash damage to current target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # DEX save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "dexterity").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        # On save: no damage
        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                total_damage=0,
                status_message=f"{target.name} avoids the acid"
            )

        # On fail: roll damage
        num_dice = self._get_cantrip_dice_count(self.caster_level)
        damage_bonus = caster.get_spell_damage_bonus()

        acid_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.ACID
        )

        damage_dice = acid_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        # Apply damage (child of effect event)
        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.ACID,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[acid_damage],
            damage_rolls=[damage_roll],
            total_damage=damage_roll.total,
            status_message=f"Acid Splash: {damage_roll.total} acid to {target.name}"
        )


class MistyStep(SpellAction):
    """Misty Step - 2nd level Conjuration

    Briefly surrounded by silvery mist, you teleport up to 30 feet to an
    unoccupied space that you can see.

    Casting Time: Bonus action.
    """
    name: str = Field(default="Misty Step")
    description: str = Field(default="Bonus action teleport up to 30ft to a visible space")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="conjuration")
    target_type: TargetType = Field(default=TargetType.POSITION)  # Teleport to position
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    # Cost: Bonus action instead of action
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Misty Step Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    # Teleport range in feet
    teleport_range: int = Field(default=30)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate destination is visible and within range."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No destination specified")

        # Check visibility
        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Destination {target_pos} not visible")

        # Check range (30ft = 6 tiles)
        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.teleport_range:
            return declaration_event.cancel(
                status_message=f"Destination out of range ({distance}ft > {self.teleport_range}ft)"
            )

        # Check if destination is unoccupied
        grid = get_map()
        entities_at_dest = grid.get_entities_at(target_pos)
        if entities_at_dest:
            return declaration_event.cancel(status_message=f"Destination {target_pos} is occupied")

        # Check if destination is walkable
        if not grid.is_walkable_for(target_pos[0], target_pos[1], caster.uuid):
            return declaration_event.cancel(status_message=f"Destination {target_pos} is not accessible")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Teleport caster to destination."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No destination")

        start_pos = caster.senses.position

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} teleports from {start_pos} to {target_pos}"
        )

        # Teleport (direct position update, no path)
        # Note: Senses updated reactively via SPATIAL events from GridMap.move_entity()
        Entity.update_entity_position(caster, target_pos)

        distance = abs(target_pos[0] - start_pos[0]) * 5 + abs(target_pos[1] - start_pos[1]) * 5

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            start_position=start_pos,
            end_position=target_pos,
            distance_feet=distance,
            status_message=f"{caster.name} teleports {distance}ft via Misty Step"
        )


# =============================================================================
# Grease Spell
# =============================================================================

class GreaseZone(ZoneControlCondition):
    """Zone control condition for Grease spell.

    Creates a 10ft square of difficult terrain. Creatures entering or
    starting their turn in the area must make a DEX save or fall prone.

    Applied to the caster, manages the zone via position-indexed handlers.
    """
    name: str = "Grease Zone"
    description: str = "Slippery grease - DEX save or fall prone"

    # Zone configuration
    zone_shape: str = Field(default="cube")
    zone_radius_feet: int = Field(default=10)
    adds_difficult_terrain: bool = Field(default=True)

    # Spell parameters
    spell_dc: int = Field(default=10)

    def _has_entry_effect(self) -> bool:
        """Grease causes saves when entities enter."""
        return True

    def _has_turn_start_effect(self) -> bool:
        """Grease causes saves when entities start turn in zone."""
        return True

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - DEX save or fall prone."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            # Make DEX save (child of triggering event)
            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:
                # Fall prone
                prone = Prone(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid
                )
                entity.add_condition(prone, parent_event=event)

            return None

        return EventHandler(
            name="Grease Entry Save",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create handler for turn start in zone - DEX save or fall prone."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if event.event_type != EventType.TURN_START:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            # Check if entity is in the zone
            if entity.senses.position not in zone_condition.affected_positions:
                return None

            # Already prone? Skip
            if "Prone" in entity.active_conditions:
                return None

            # Make DEX save (child of triggering event)
            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:
                # Fall prone
                prone = Prone(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid
                )
                entity.add_condition(prone, parent_event=event)

            return None

        return EventHandler(
            name="Grease Turn Start Save",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EXECUTION  # Fire BEFORE auto-stand at EFFECT
            )],
            event_processor=processor
        )


class Grease(SpellAction):
    """Grease - 1st level Conjuration

    Slick grease covers the ground in a 10-foot square centered on a point
    within range and turns it into difficult terrain for the duration.

    When the grease appears, each creature standing in its area must succeed
    on a Dexterity saving throw or fall prone. A creature that enters the
    area or ends its turn there must also succeed on a Dexterity saving
    throw or fall prone.

    Duration: 1 minute (non-concentration in SRD, but we treat as concentration
    for BG3-style cleanup convenience)
    """
    name: str = Field(default="Grease")
    description: str = Field(default="10ft square difficult terrain, DEX save or prone")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="conjuration")
    concentration: bool = Field(default=True)  # For easy cleanup
    target_type: TargetType = Field(default=TargetType.POSITION)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )

    # Action cost
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Grease Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
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

        # Check range (60ft = 12 tiles)
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
        """Cast Grease - create zone, apply to creatures already there, concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=f"{caster.name} casts Grease at {target_pos}"
        )

        # Create and apply the zone condition to the caster
        zone = GreaseZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc
        )
        caster.add_condition(zone, parent_event=effect_event)

        # Apply Concentrating condition
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Grease"
        )
        caster.add_condition(concentration, parent_event=effect_event)

        # Link zone to concentration for cleanup
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        # Check creatures already in the zone
        grid = get_map()
        prone_count = 0
        for pos in zone.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue
                if ent.uuid == caster.uuid:
                    continue  # Don't affect caster
                # DEX save (child of effect event)
                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid,
                    ability_name="dexterity",
                    dc=dc,
                    parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)
                if not success:
                    prone = Prone(
                        source_entity_uuid=caster.uuid,
                        target_entity_uuid=ent.uuid
                    )
                    ent.add_condition(prone, parent_event=effect_event)
                    prone_count += 1

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Grease active: 10ft square at {target_pos}, {prone_count} creatures fell prone"
        )


# =============================================================================
# Web Spell
# =============================================================================

class WebRestrained(BaseCondition):
    """Restrained condition from Web spell.

    Has Restrained as sub-condition. Grants EscapeWebAction to escape.
    """
    name: str = "Web Restrained"
    description: str = "Restrained by sticky web - can use action to escape"

    spell_dc: int = Field(default=10)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []
        sub_conditions_uuids: List[UUID] = []

        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Target UUID not set")
        if self.source_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Source UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        # Add Restrained as sub-condition
        restrained = Restrained(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid
        )
        target.add_condition(restrained, parent_event=declaration_event)
        sub_conditions_uuids.append(restrained.uuid)

        # Grant escape action
        escape = EscapeWebAction(
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            restraining_condition_uuid=self.uuid,
            spell_dc=self.spell_dc,
            template=True
        )
        target.register_action(escape)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Web Restrained to {target.name}"
        )

        return outs, handler_uuids, sub_conditions_uuids, [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Remove granted escape action when this condition is removed."""
        if self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target:
                target.unregister_action("Escape Web")
        return super()._remove(event)


class EscapeWebAction(BaseAction):
    """Action to escape from Web spell's Restrained condition.

    Uses an action. Make STR check (Athletics) vs spell DC to escape.
    """
    name: str = Field(default="Escape Web")
    description: str = Field(default="Use action to attempt to escape the web")
    target_type: TargetType = Field(default=TargetType.SELF)

    restraining_condition_uuid: Optional[UUID] = Field(default=None)
    spell_dc: int = Field(default=10)

    # Action cost
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Escape Web Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Escape Web",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        # Must have Web Restrained condition
        if "Web Restrained" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Not restrained by web")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        # STR check (Athletics) vs spell DC
        check_event = SkillCheckEvent(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            skill_name="athletics",
            dc=self.spell_dc,
            source_entity_name=entity.name
        )
        _, _, success = entity.skill_check(check_event)

        if success:
            # Escape! Remove Web Restrained
            entity.remove_condition("Web Restrained", parent_event=execution_event)
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{entity.name} breaks free from the web!"
            )
        else:
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{entity.name} fails to escape the web"
            )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class WebZone(ZoneControlCondition):
    """Zone control condition for Web spell.

    Creates a 20ft cube of difficult terrain. Creatures entering must
    DEX save or become restrained.

    Applied to the caster, manages the zone via position-indexed handlers.
    """
    name: str = "Web Zone"
    description: str = "Sticky webs - DEX save or restrained"

    # Zone configuration
    zone_shape: str = Field(default="cube")
    zone_radius_feet: int = Field(default=20)
    adds_difficult_terrain: bool = Field(default=True)

    # Spell parameters
    spell_dc: int = Field(default=10)

    def _has_entry_effect(self) -> bool:
        """Web causes saves when entities enter."""
        return True

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - DEX save or restrained."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            # Already restrained by web? Skip
            if "Web Restrained" in entity.active_conditions:
                return None

            # Make DEX save (child of triggering event)
            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:
                # Apply WebRestrained condition
                web_restrained = WebRestrained(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid,
                    spell_dc=dc
                )
                entity.add_condition(web_restrained, parent_event=event)

            return None

        return EventHandler(
            name="Web Entry Save",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )


class Web(SpellAction):
    """Web - 2nd level Conjuration (Concentration)

    You conjure a mass of thick, sticky webbing at a point of your choice
    within range. The webs fill a 20-foot cube from that point for the duration.
    The webs are difficult terrain and lightly obscure their area.

    If the webs aren't anchored between two solid masses (such as walls or trees)
    or layered across a floor, wall, or ceiling, the conjured web collapses on
    itself, and the spell ends at the start of your next turn.

    Each creature that starts its turn in the webs or that enters them during its
    turn must make a Dexterity saving throw. On a failed save, the creature is
    restrained as long as it remains in the webs or until it breaks free.

    A creature restrained by the webs can use its action to make a Strength check
    against your spell save DC. If it succeeds, it is no longer restrained.

    The webs are flammable. (Not implemented)

    Duration: Concentration, up to 1 hour
    """
    name: str = Field(default="Web")
    description: str = Field(default="20ft cube of webs, DEX save or restrained, can escape with STR check")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="conjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )

    # Action cost
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Web Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
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

        # Check range (60ft = 12 tiles)
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
        """Cast Web - create zone, restrain creatures already there, concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=f"{caster.name} casts Web at {target_pos}"
        )

        # Create and apply the zone condition to the caster
        zone = WebZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc
        )
        caster.add_condition(zone, parent_event=effect_event)

        # Apply Concentrating condition
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Web"
        )
        caster.add_condition(concentration, parent_event=effect_event)

        # Link zone to concentration for cleanup
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        # Check creatures already in the zone
        grid = get_map()
        restrained_count = 0
        for pos in zone.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue
                if ent.uuid == caster.uuid:
                    continue  # Don't affect caster
                # DEX save (child of effect event)
                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid,
                    ability_name="dexterity",
                    dc=dc,
                    parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)
                if not success:
                    web_restrained = WebRestrained(
                        source_entity_uuid=caster.uuid,
                        target_entity_uuid=ent.uuid,
                        spell_dc=dc
                    )
                    ent.add_condition(web_restrained, parent_event=effect_event)
                    restrained_count += 1

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Web active: 20ft cube at {target_pos}, {restrained_count} creatures restrained"
        )


# =============================================================================
# Cloudkill Spell
# =============================================================================

class CloudkillZone(ZoneControlCondition):
    """Zone control condition for Cloudkill spell.

    Creates a 20ft radius sphere of heavily obscured poisonous fog.
    Creatures entering or starting their turn in the area take 5d8 poison
    (CON save for half).

    The cloud moves 10ft away from the caster at the start of each of the
    caster's turns.

    Applied to the caster, manages the zone via position-indexed handlers.
    """
    name: str = "Cloudkill Zone"
    description: str = "Poisonous fog - CON save or 5d8 poison, half on save"

    # Zone configuration
    zone_shape: str = Field(default="sphere")
    zone_radius_feet: int = Field(default=20)
    adds_difficult_terrain: bool = Field(default=False)  # Just obscured, not difficult

    # Spell parameters
    spell_dc: int = Field(default=10)
    damage_dice: str = Field(default="5d8")
    upcast_dice: int = Field(default=0)  # +1d8 per level above 5th

    def _has_entry_effect(self) -> bool:
        """Cloudkill causes damage when entities enter."""
        return True

    def _has_turn_start_effect(self) -> bool:
        """Cloudkill causes damage when entities start turn in zone."""
        return True

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone and add auto-move handler."""
        # Call parent to set up zone and standard handlers
        outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event = super()._apply(declaration_event)

        # Add auto-move handler (moves zone on caster's turn start)
        auto_move_handler = self._create_auto_move_handler()
        EventQueue.add_event_handler(auto_move_handler)
        handler_uuids.append(auto_move_handler.uuid)

        return outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - CON save, poison damage."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        base_dice = 5 + self.upcast_dice

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            # Make CON save (child of triggering event)
            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            # Roll 5d8 (+ upcast) poison damage
            damage = sum(random.randint(1, 8) for _ in range(base_dice))
            if success:
                damage = damage // 2

            entity.receive_damage(damage, DamageType.POISON, source_uuid, parent_event=event.uuid)

            return None

        return EventHandler(
            name="Cloudkill Entry Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create handler for turn start in zone - CON save, poison damage."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        base_dice = 5 + self.upcast_dice
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if event.event_type != EventType.TURN_START:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            # Check if entity is in the zone
            if entity.senses.position not in zone_condition.affected_positions:
                return None

            # Make CON save (child of triggering event)
            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            # Roll 5d8 (+ upcast) poison damage
            damage = sum(random.randint(1, 8) for _ in range(base_dice))
            if success:
                damage = damage // 2

            entity.receive_damage(damage, DamageType.POISON, source_uuid, parent_event=event.uuid)

            return None

        return EventHandler(
            name="Cloudkill Turn Start Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_auto_move_handler(self) -> EventHandler:
        """Create handler that moves zone 10ft away from caster at caster's turn start."""
        caster_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            if event.source_entity_uuid != caster_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                return None

            # Calculate direction away from caster
            cx, cy = caster.senses.position
            zx, zy = zone_condition.zone_center

            # If zone is at caster position, pick a default direction
            dx = zx - cx
            dy = zy - cy

            if dx == 0 and dy == 0:
                # Zone is at caster, move in a default direction
                dx = 1
                dy = 0

            # Normalize and move 2 tiles (10ft)
            length = max(abs(dx), abs(dy), 1)
            move_x = int(dx / length * 2) if dx != 0 else 0
            move_y = int(dy / length * 2) if dy != 0 else 0

            new_x = zx + move_x
            new_y = zy + move_y

            zone_condition.move_zone((new_x, new_y))

            return None

        return EventHandler(
            name="Cloudkill Auto-Move",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=caster_uuid
            )],
            event_processor=processor
        )


class Cloudkill(SpellAction):
    """Cloudkill - 5th level Conjuration (Concentration)

    You create a 20-foot-radius sphere of poisonous, yellow-green fog centered
    on a point you choose within range. The fog spreads around corners. It lasts
    for the duration or until strong wind disperses the fog, ending the spell.
    Its area is heavily obscured.

    When a creature enters the spell's area for the first time on a turn or starts
    its turn there, that creature must make a Constitution saving throw. The
    creature takes 5d8 poison damage on a failed save, or half as much damage on
    a successful one. Creatures are affected even if they hold their breath or
    don't need to breathe.

    The fog moves 10 feet away from you at the start of each of your turns,
    rolling along the surface of the ground.

    At Higher Levels: Damage increases by 1d8 for each slot level above 5th.

    Duration: Concentration, up to 10 minutes
    """
    name: str = Field(default="Cloudkill")
    description: str = Field(default="20ft sphere poison fog, 5d8 poison (CON half), moves away from caster")
    spell_level: int = Field(default=5)
    spell_school: str = Field(default="conjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
    )

    # Action cost
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Cloudkill Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
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

        # Check range (120ft = 24 tiles)
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
        """Cast Cloudkill - create zone, damage creatures already there, concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc()
        upcast_bonus = self.get_upcast_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            status_message=f"{caster.name} casts Cloudkill at {target_pos}"
        )

        # Create and apply the zone condition to the caster
        zone = CloudkillZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc,
            upcast_dice=upcast_bonus
        )
        caster.add_condition(zone, parent_event=effect_event)

        # Apply Concentrating condition
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Cloudkill"
        )
        caster.add_condition(concentration, parent_event=effect_event)

        # Link zone to concentration for cleanup
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        # Damage creatures already in the zone

        grid = get_map()
        damage_count = 0
        base_dice = 5 + upcast_bonus

        for pos in zone.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue
                # Note: Cloudkill affects everyone, including caster
                # CON save (child of effect event)
                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid,
                    ability_name="constitution",
                    dc=dc,
                    parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)

                # Roll damage
                damage = sum(random.randint(1, 8) for _ in range(base_dice))
                if success:
                    damage = damage // 2

                ent.receive_damage(damage, DamageType.POISON, caster.uuid, parent_event=effect_event.uuid)
                damage_count += 1

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Cloudkill active: 20ft sphere at {target_pos}, {damage_count} creatures damaged"
        )


# =============================================================================
# Spirit Guardians Spell
# =============================================================================

class SpiritGuardiansTriggered(BaseCondition):
    """Marker condition to prevent multiple Spirit Guardians damage in one turn.

    Applied when an entity takes Spirit Guardians damage. Lasts 1 round
    (removed at the entity's next turn end).
    """
    name: str = "Spirit Guardians Triggered"
    description: str = "Already damaged by Spirit Guardians this turn"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        # Create handler to remove at turn end
        handler = self._create_cleanup_handler()
        EventQueue.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Spirit Guardians damage marker applied"
        ) if declaration_event else None

        return [], [handler.uuid], [], [], effect_event

    def _create_cleanup_handler(self) -> EventHandler:
        """Remove this marker at the end of the target's turn."""
        target_uuid = self.target_entity_uuid
        if target_uuid is None:
            raise ValueError("Target UUID not set for Spirit Guardians Triggered")

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_END:
                return None
            if event.source_entity_uuid != target_uuid:
                return None

            entity = Entity.get(target_uuid)
            if entity and "Spirit Guardians Triggered" in entity.active_conditions:
                entity.remove_condition("Spirit Guardians Triggered", parent_event=event)

            return None

        return EventHandler(
            name="Spirit Guardians Triggered Cleanup",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


class SpiritGuardiansSlowed(BaseCondition):
    """Speed halving condition from Spirit Guardians.

    Applied to enemies within the Spirit Guardians zone.
    Removed when they leave the zone.
    """
    name: str = "Spirit Guardians Slowed"
    description: str = "Speed halved by Spirit Guardians"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        outs: List[Tuple[UUID, UUID]] = []

        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Target UUID not set")

        entity = Entity.get(self.target_entity_uuid)
        if not entity:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        # Halve speed via modifier (negative value = half base speed)
        current_speed = entity.action_economy.get_base_value("movement")
        half_speed = current_speed // 2

        mod = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            name="Spirit Guardians Slowed",
            value=-half_speed
        )
        mod_uuid = entity.action_economy.movement.self_static.add_value_modifier(mod)
        outs.append((entity.action_economy.movement.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{entity.name}'s speed halved by Spirit Guardians"
        ) if declaration_event else None

        return outs, [], [], [], effect_event


class SpiritGuardiansZone(ZoneControlCondition):
    """Zone control condition for Spirit Guardians spell.

    Creates a 15ft radius sphere centered on the caster. The zone follows
    the caster as they move. Enemies entering or starting turn in the zone
    must make WIS save or take 3d8 radiant damage (half on save).

    Only affects enemies. Allies are unaffected.
    """
    name: str = "Spirit Guardians Zone"
    description: str = "Spectral warriors damage enemies entering the zone"

    # Zone configuration
    zone_shape: str = Field(default="sphere")
    zone_radius_feet: int = Field(default=15)
    adds_difficult_terrain: bool = Field(default=False)

    # Spell parameters
    spell_dc: int = Field(default=10)
    damage_dice: str = Field(default="3d8")
    damage_type: DamageType = Field(default=DamageType.RADIANT)
    upcast_dice: int = Field(default=0)  # +1d8 per level above 3rd

    def _has_entry_effect(self) -> bool:
        """Spirit Guardians damages enemies when they enter."""
        return True

    def _has_turn_start_effect(self) -> bool:
        """Spirit Guardians damages enemies when they start turn in zone."""
        return True

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone and add follow-caster handler."""
        # Call parent to set up zone and standard handlers
        outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event = super()._apply(declaration_event)

        # Add follow-caster handler (zone moves when caster moves)
        follow_handler = self._create_follow_caster_handler()
        EventQueue.add_event_handler(follow_handler)
        handler_uuids.append(follow_handler.uuid)

        # Add exit handler (remove speed debuff when leaving)
        exit_handler = self._create_zone_exit_handler()
        EventQueue.add_spatial_handler(exit_handler, self.affected_positions, EventType.SPATIAL_ENTITY_LEFT, EventPhase.EFFECT)
        handler_uuids.append(exit_handler.uuid)

        return outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - WIS save, radiant damage (enemies only)."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        base_dice = 3 + self.upcast_dice
        dmg_type = self.damage_type

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            # Skip caster
            if entity.uuid == source_uuid:
                return None

            # Only affect enemies
            caster = Entity.get(source_uuid)
            if caster and entity.is_ally(caster):
                return None

            # Skip if already triggered this turn (marker condition)
            if "Spirit Guardians Triggered" in entity.active_conditions:
                return None

            # WIS save + damage (child of triggering event)
            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            # Roll damage
            damage = sum(random.randint(1, 8) for _ in range(base_dice))
            if success:
                damage = damage // 2

            entity.receive_damage(damage, dmg_type, source_uuid, parent_event=event.uuid)

            # Apply marker (prevents repeat damage this turn)
            marker = SpiritGuardiansTriggered(
                source_entity_uuid=source_uuid,
                target_entity_uuid=entity.uuid
            )
            entity.add_condition(marker, parent_event=event)

            # Apply speed debuff if not already slowed
            if "Spirit Guardians Slowed" not in entity.active_conditions:
                slowed = SpiritGuardiansSlowed(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid
                )
                entity.add_condition(slowed, parent_event=event)

            return None

        return EventHandler(
            name="Spirit Guardians Entry Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create handler for turn start in zone - WIS save, radiant damage (enemies only)."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        base_dice = 3 + self.upcast_dice
        dmg_type = self.damage_type
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if event.event_type != EventType.TURN_START:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            # Check if entity is in the zone
            if entity.senses.position not in zone_condition.affected_positions:
                return None

            # Skip caster
            if entity.uuid == source_uuid:
                return None

            # Only affect enemies
            caster = Entity.get(source_uuid)
            if caster and entity.is_ally(caster):
                return None

            # Skip if already triggered this turn (marker condition)
            if "Spirit Guardians Triggered" in entity.active_conditions:
                return None

            # WIS save + damage (child of triggering event)
            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            # Roll damage
            damage = sum(random.randint(1, 8) for _ in range(base_dice))
            if success:
                damage = damage // 2

            entity.receive_damage(damage, dmg_type, source_uuid, parent_event=event.uuid)

            # Apply marker (prevents repeat damage this turn)
            marker = SpiritGuardiansTriggered(
                source_entity_uuid=source_uuid,
                target_entity_uuid=entity.uuid
            )
            entity.add_condition(marker, parent_event=event)

            return None

        return EventHandler(
            name="Spirit Guardians Turn Start Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_exit_handler(self) -> EventHandler:
        """Create handler for zone exit - remove speed debuff."""
        source_uuid = self.source_entity_uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            # Remove speed debuff
            if "Spirit Guardians Slowed" in entity.active_conditions:
                entity.remove_condition("Spirit Guardians Slowed", parent_event=event)

            return None

        return EventHandler(
            name="Spirit Guardians Exit Cleanup",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_follow_caster_handler(self) -> EventHandler:
        """Create handler that moves zone to follow caster."""
        caster_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            # SPATIAL_ENTITY_ENTERED uses entity_uuid, not source_entity_uuid
            if not isinstance(event, SpatialChangeEvent) or event.entity_uuid != caster_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if caster:
                zone_condition.move_zone(caster.senses.position)

            return None

        return EventHandler(
            name="Spirit Guardians Follow",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT  # Must use EFFECT, not COMPLETION (COMPLETION skips handlers)
            )],
            event_processor=processor
        )


class SpiritGuardians(SpellAction):
    """Spirit Guardians - 3rd level Conjuration (Concentration)

    You call forth spirits to protect you. They flit around you to a distance
    of 15 feet for the duration. If you are good or neutral, their spectral
    form appears angelic or fey (your choice). If you are evil, they appear
    fiendish.

    When you cast this spell, you can designate any number of creatures you
    can see to be unaffected by it. An affected creature's speed is halved in
    the area, and when the creature enters the area for the first time on a
    turn or starts its turn there, it must make a Wisdom saving throw. On a
    failed save, the creature takes 3d8 radiant damage (if you are good or
    neutral) or 3d8 necrotic damage (if you are evil). On a successful save,
    the creature takes half as much damage.

    At Higher Levels: Damage increases by 1d8 for each slot level above 3rd.

    Duration: Concentration, up to 10 minutes

    NOTE: This implementation only affects enemies (not neutral creatures).
    """
    name: str = Field(default="Spirit Guardians")
    description: str = Field(default="15ft sphere around caster, enemies take 3d8 radiant (WIS half), speed halved")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="conjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF)
    )

    # Action cost
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Spirit Guardians Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    # Damage type (radiant for good/neutral, necrotic for evil)
    damage_type: DamageType = Field(default=DamageType.RADIANT)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Spirit Guardians is self-targeted, minimal validation needed."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Spirit Guardians - create zone centered on caster."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        dc = caster.spell_save_dc()
        upcast_bonus = self.get_upcast_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            status_message=f"{caster.name} casts Spirit Guardians"
        )

        # Create and apply the zone condition to the caster (centered on caster)
        zone = SpiritGuardiansZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=caster.senses.position,  # Centered on caster
            spell_dc=dc,
            damage_type=self.damage_type,
            upcast_dice=upcast_bonus
        )
        caster.add_condition(zone, parent_event=effect_event)

        # Apply Concentrating condition
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Spirit Guardians"
        )
        caster.add_condition(concentration, parent_event=effect_event)

        # Link zone to concentration for cleanup
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        # Damage enemies already in the zone

        grid = get_map()
        damage_count = 0
        base_dice = 3 + upcast_bonus

        for pos in zone.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue
                if ent.uuid == caster.uuid:
                    continue  # Skip caster
                if ent.is_ally(caster):
                    continue  # Skip allies

                # WIS save (child of effect event)
                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid,
                    ability_name="wisdom",
                    dc=dc,
                    parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)

                # Roll damage
                damage = sum(random.randint(1, 8) for _ in range(base_dice))
                if success:
                    damage = damage // 2

                ent.receive_damage(damage, self.damage_type, caster.uuid, parent_event=effect_event.uuid)
                damage_count += 1

                # Apply marker
                marker = SpiritGuardiansTriggered(
                    source_entity_uuid=caster.uuid,
                    target_entity_uuid=ent.uuid
                )
                ent.add_condition(marker, parent_event=effect_event)

                # Apply speed debuff
                if "Spirit Guardians Slowed" not in ent.active_conditions:
                    slowed = SpiritGuardiansSlowed(
                        source_entity_uuid=caster.uuid,
                        target_entity_uuid=ent.uuid
                    )
                    ent.add_condition(slowed, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Spirit Guardians active: 15ft sphere around {caster.name}, {damage_count} enemies damaged"
        )


# =============================================================================
# Fog Cloud Spell
# =============================================================================

class FogCloudZone(ZoneControlCondition):
    """Zone control condition for Fog Cloud spell.

    Creates a 20ft radius sphere of heavily obscured area (DARKNESS).
    Uses obscurement so darkvision cannot see through it.
    """
    name: str = "Fog Cloud Zone"
    description: str = "Heavily obscured fog — blocks vision including darkvision"

    zone_shape: str = Field(default="sphere")
    zone_radius_feet: int = Field(default=20)

    # Light: DARKNESS as obscurement (blocks darkvision)
    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.DARKNESS)
    light_is_obscurement: bool = Field(default=True)


class FogCloud(SpellAction):
    """Fog Cloud - 1st level Conjuration (Concentration)

    You create a 20-foot-radius sphere of fog centered on a point within range.
    The sphere spreads around corners, and its area is heavily obscured. It
    lasts for the duration or until a wind of moderate or greater speed (at
    least 10 miles per hour) disperses it.

    At Higher Levels: The radius increases by 20 feet for each slot level
    above 1st.

    Duration: Concentration, up to 1 hour
    """
    name: str = Field(default="Fog Cloud")
    description: str = Field(default="20ft sphere heavily obscured fog (blocks darkvision)")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="conjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Fog Cloud Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

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
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        # Radius scales: 20ft base + 20ft per upcast level
        radius = 20 + self.get_upcast_bonus() * 20

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Fog Cloud at {target_pos}"
        )

        zone = FogCloudZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            zone_radius_feet=radius
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Fog Cloud"
        )
        caster.add_condition(concentration, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Fog Cloud active: {radius}ft radius sphere at {target_pos}"
        )


# =============================================================================
# Darkness Spell
# =============================================================================

class DarknessZone(ZoneControlCondition):
    """Zone control condition for Darkness spell.

    Creates a 15ft radius sphere of magical darkness.
    Magical darkness blocks all vision including darkvision.
    Only Truesight and Devil's Sight can see through it.
    """
    name: str = "Darkness Zone"
    description: str = "Magical darkness — blocks all vision including darkvision"

    zone_shape: str = Field(default="sphere")
    zone_radius_feet: int = Field(default=15)

    # Light: MAGICAL_DARKNESS as obscurement
    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.MAGICAL_DARKNESS)
    light_is_obscurement: bool = Field(default=True)


class Darkness(SpellAction):
    """Darkness - 2nd level Evocation (Concentration)

    Magical darkness spreads from a point you choose within range to fill a
    15-foot-radius sphere for the duration. The darkness spreads around corners.
    A creature with darkvision can't see through this darkness, and nonmagical
    light can't illuminate it.

    If the point you choose is on an object you are holding or one that isn't
    being worn or carried, the darkness emanates from the object and moves with
    it. Completely covering the source of the darkness with an opaque object,
    such as a bowl or a helm, blocks the darkness.

    Duration: Concentration, up to 10 minutes
    """
    name: str = Field(default="Darkness")
    description: str = Field(default="15ft sphere magical darkness (blocks darkvision)")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="evocation")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Darkness Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

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
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Darkness at {target_pos}"
        )

        zone = DarknessZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Darkness"
        )
        caster.add_condition(concentration, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Darkness active: 15ft sphere at {target_pos}"
        )


# =============================================================================
# Daylight Spell
# =============================================================================

class DaylightZone(ZoneControlCondition):
    """Zone control condition for Daylight spell.

    Creates a 60ft radius sphere of very bright light.
    Dispels any magical darkness in the area.
    Entities hidden in the zone are revealed.
    """
    name: str = "Daylight Zone"
    description: str = "Very bright light — reveals hidden creatures"

    zone_shape: str = Field(default="sphere")
    zone_radius_feet: int = Field(default=60)

    # Light: VERY_BRIGHT as illumination (not obscurement)
    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.VERY_BRIGHT)
    light_is_obscurement: bool = Field(default=False)


class Daylight(SpellAction):
    """Daylight - 3rd level Evocation (not actually Concentration per SRD, but
    we use Concentration for cleanup convenience in our system)

    A 60-foot-radius sphere of light spreads out from a point you choose
    within range. The sphere is bright light and sheds dim light for an
    additional 60 feet.

    If you chose a point on an object you are holding or one that isn't being
    worn or carried, the light shines from the object with and moves with it.

    If any of this spell's area overlaps with an area of darkness created by a
    spell of 3rd level or lower, the spell that created the darkness is
    dispelled.

    Duration: 1 hour (using Concentration for cleanup)
    """
    name: str = Field(default="Daylight")
    description: str = Field(default="60ft sphere very bright light, reveals hidden, dispels darkness")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="evocation")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Daylight Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

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
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Daylight at {target_pos}"
        )

        zone = DaylightZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Daylight"
        )
        caster.add_condition(concentration, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Daylight active: 60ft sphere at {target_pos}"
        )
