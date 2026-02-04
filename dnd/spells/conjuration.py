"""Conjuration spells - creating objects and summoning creatures.

Contains: CallLightning, PoisonSpray, AcidSplash
"""
from typing import Optional, List
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType, BaseAction, Cost
from dnd.core.dice import AttackOutcome
from dnd.core.events import EventPhase, RangeType, Range, EventType, EventHandler, Trigger, Damage, Event
from dnd.core.modifiers import DamageType
from dnd.entity import Entity
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
        from dnd.spells.evocation import validate_line_of_sight

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

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc
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

        target.health.take_damage(damage_roll.total, DamageType.POISON, caster.uuid)

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
        from typing import cast as type_cast
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply acid splash damage to current target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # DEX save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc
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

        target.health.take_damage(damage_roll.total, DamageType.ACID, caster.uuid)

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
        from dnd.core.gridmap import get_map
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
