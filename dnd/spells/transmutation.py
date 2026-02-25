"""Transmutation spells - transforming matter and energy.

Contains: SpikeGrowth, Slow, Haste
"""
import random
from typing import Any, Optional, List, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType, Cost, ActionEvent
from dnd.core.base_conditions import BaseCondition, HazardFilter, DurationType
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger, Range, RangeType, SpatialChangeEvent
)
from dnd.core.modifiers import NumericalModifier, AdvantageModifier, AdvantageStatus, DamageType
from dnd.core.values import ModifiableValue
from dnd.core.aoe import AoEShape, Cube
from dnd.entity import Entity
from dnd.conditions import Concentrating, Incapacitated
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

    # Tile markers — hazardous to everyone except caster, hidden (perception check)
    marker_name: Optional[str] = Field(default="Spike Growth")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.NON_SOURCE)

    # Spell parameters
    spell_dc: int = Field(default=10, description="Spell DC for perception to notice")
    damage_dice: str = Field(default="2d4")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        # Sync marker_stealth_dc from spell_dc (SRD: Perception check vs spell DC)
        self.marker_stealth_dc = self.spell_dc

    def _has_entry_effect(self) -> bool:
        """Spike Growth damages entities when they enter."""
        return True

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry damage (2d4 piercing per tile entered)."""
        source_uuid = self.source_entity_uuid
        damage_dice = self.damage_dice

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            # Get entity from the spatial event
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            # Don't damage the caster
            if entity.uuid == source_uuid:
                return None

            # Roll and apply damage (using receive_damage for proper event firing)
            count, value = parse_dice_string(damage_dice)
            damage = sum(random.randint(1, value) for _ in range(count))
            entity.receive_damage(damage, DamageType.PIERCING, source_uuid, parent_event=event.uuid)

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
        caster.add_condition(zone, parent_event=effect_event)

        # Apply Concentrating condition
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Spike Growth"
        )
        caster.add_condition(concentration, parent_event=effect_event)

        # Link zone to concentration for cleanup
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Spike Growth active: 20ft radius at {target_pos}, difficult terrain + 2d4 damage per 5ft"
        )


# =============================================================================
# Slow (3rd-level Transmutation, Concentration)
# =============================================================================

class SlowedEffect(BaseCondition):
    """Effect from Slow spell applied to each target that fails WIS save.

    Effects:
    1. Speed halved
    2. -2 AC
    3. -2 DEX saving throws
    4. Can't use reactions
    5. Action OR bonus action per turn, not both
    6. No Extra Attack (max one attack per turn)
    7. (SKIPPED) Spell casting delay

    Repeat WIS save at end of each turn to end effect.
    """
    name: str = "Slowed"
    description: str = "Speed halved, -2 AC, -2 DEX saves, no reactions, limited actions"

    spell_dc: int = Field(default=0, description="DC for repeat WIS save")
    caster_uuid: Optional[UUID] = Field(default=None, description="UUID of the caster")

    # Dynamic lockout tracking (for action-or-bonus lockout)
    _lockout_modifier_uuid: Optional[UUID] = None
    _lockout_target_mv_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(type_cast(UUID, self.target_entity_uuid))
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target not found"
            )

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # 1. Speed halved
        base_speed_modifier = target.action_economy.movement.get_base_modifier()
        if base_speed_modifier:
            speed_penalty = -(base_speed_modifier.value // 2)
            speed_mod = NumericalModifier(
                name="Slowed",
                value=speed_penalty,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
            target.action_economy.movement.self_static.add_value_modifier(speed_mod)
            outs.append((target.action_economy.movement.uuid, speed_mod.uuid))

        # 2. -2 AC
        ac_mod = NumericalModifier(
            name="Slowed",
            value=-2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        target.equipment.ac_bonus.self_static.add_value_modifier(ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, ac_mod.uuid))

        # 3. -2 DEX saving throws
        dex_save = target.saving_throws.get_saving_throw("dexterity")
        dex_mod = NumericalModifier(
            name="Slowed",
            value=-2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        dex_save.bonus.self_static.add_value_modifier(dex_mod)
        outs.append((dex_save.bonus.uuid, dex_mod.uuid))

        # 4. No reactions (max constraint = 0)
        reaction_constraint_uuid = target.action_economy.reactions.self_static.add_max_constraint(
            constraint=NumericalModifier(
                name="Slowed",
                value=0,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((target.action_economy.reactions.uuid, reaction_constraint_uuid))

        # Handler 1: Action/Bonus Lockout
        lockout_handler = self._create_action_bonus_lockout_handler()
        target.add_event_handler(lockout_handler)
        handler_uuids.append(lockout_handler.uuid)

        # Handler 2: Turn Start Reset (clears lockout)
        turn_reset_handler = self._create_turn_start_reset_handler()
        target.add_event_handler(turn_reset_handler)
        handler_uuids.append(turn_reset_handler.uuid)

        # Handler 3: No Extra Attack
        no_ea_handler = self._create_no_extra_attack_handler()
        target.add_event_handler(no_ea_handler)
        handler_uuids.append(no_ea_handler.uuid)

        # Handler 4: Repeat WIS save at turn end
        if self.caster_uuid and self.spell_dc > 0:
            repeat_save_handler = self._create_repeat_save_handler()
            target.add_event_handler(repeat_save_handler)
            handler_uuids.append(repeat_save_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Slowed to {target.name}"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_action_bonus_lockout_handler(self) -> EventHandler:
        """When entity uses action → lock bonus actions, and vice versa."""
        target_uuid = type_cast(UUID, self.target_entity_uuid)
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, ActionEvent):
                return None
            if event.source_entity_uuid != target_uuid:
                return None
            # Already locked out? Don't double-apply
            if condition._lockout_modifier_uuid is not None:
                return None

            entity = Entity.get(target_uuid)
            if not entity:
                return None

            # Check what type of cost was used
            for cost in event.costs:
                if cost.cost_type == "actions":
                    # Used an action → lock bonus actions
                    lock_uuid = entity.action_economy.bonus_actions.self_static.add_max_constraint(
                        constraint=NumericalModifier(
                            name="Slowed: Bonus Locked",
                            value=0,
                            source_entity_uuid=target_uuid,
                            target_entity_uuid=target_uuid
                        )
                    )
                    condition._lockout_modifier_uuid = lock_uuid
                    condition._lockout_target_mv_uuid = entity.action_economy.bonus_actions.uuid
                    return None
                elif cost.cost_type == "bonus_actions":
                    # Used a bonus action → lock actions
                    lock_uuid = entity.action_economy.actions.self_static.add_max_constraint(
                        constraint=NumericalModifier(
                            name="Slowed: Actions Locked",
                            value=0,
                            source_entity_uuid=target_uuid,
                            target_entity_uuid=target_uuid
                        )
                    )
                    condition._lockout_modifier_uuid = lock_uuid
                    condition._lockout_target_mv_uuid = entity.action_economy.actions.uuid
                    return None
            return None

        return EventHandler(
            name="Slowed: Action/Bonus Lockout",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=target_uuid
                )
            ],
            event_processor=processor
        )

    def _create_turn_start_reset_handler(self) -> EventHandler:
        """Reset the action/bonus lockout at turn start."""
        target_uuid = type_cast(UUID, self.target_entity_uuid)
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            entity = Entity.get(target_uuid)
            if not entity:
                return None

            # Remove lockout constraint if one exists
            if condition._lockout_modifier_uuid is not None and condition._lockout_target_mv_uuid is not None:
                mv = ModifiableValue.get(condition._lockout_target_mv_uuid)
                if mv:
                    mv.self_static.remove_max_constraint(condition._lockout_modifier_uuid)
                condition._lockout_modifier_uuid = None
                condition._lockout_target_mv_uuid = None

            return None

        return EventHandler(
            name="Slowed: Turn Start Reset",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=target_uuid
                )
            ],
            event_processor=processor
        )

    def _create_no_extra_attack_handler(self) -> EventHandler:
        """Zero the extra_attacks resource after it's granted, preventing Extra Attack."""
        target_uuid = type_cast(UUID, self.target_entity_uuid)

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            entity = Entity.get(target_uuid)
            if not entity:
                return None

            # Only affect action-cost attacks (not OA, not bonus action attacks)
            if isinstance(event, ActionEvent):
                has_action_cost = any(c.cost_type == "actions" for c in event.costs)
                if not has_action_cost:
                    return None

            # Zero extra_attacks resource if it exists
            if entity.action_economy.has_resource("extra_attacks"):
                entity.action_economy.resources["extra_attacks"].current = 0

            return None

        return EventHandler(
            name="Slowed: No Extra Attack",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=target_uuid
                )
            ],
            event_processor=processor
        )

    def _create_repeat_save_handler(self) -> EventHandler:
        """WIS save at end of turn to end the Slowed effect."""
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        effect_uuid = self.uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            # Check if still affected
            slowed = target.active_conditions.get("Slowed")
            if not slowed or slowed.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                # Caster gone, end the effect
                target.remove_condition("Slowed", parent_event=event)
                return None

            # Repeat WIS save
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Slowed", parent_event=event)

            return None

        return EventHandler(
            name=f"Slowed: Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=target_uuid
                )
            ],
            event_processor=processor
        )


class Slow(SpellAction):
    """Slow - 3rd level Transmutation (Concentration)

    You alter time around up to six creatures of your choice in a 40-foot cube
    within range. Each target must succeed on a WIS saving throw or be affected.

    Duration: Concentration, up to 1 minute.
    """
    name: str = Field(default="Slow")
    description: str = Field(default="40ft cube, WIS save or Slowed")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="transmutation")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
    )

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="all")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                size_feet=40,
                centered=True
            )

    def get_range(self) -> Range:
        return self.spell_range

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not in LOS")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Slow to current target (called per target via convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # WIS save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "wisdom").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"WIS save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Slow"
            )

        # Apply SlowedEffect
        slowed = SlowedEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        target.add_condition(slowed, parent_event=effect_event)

        # Apply Concentrating (only on first target)
        if "Concentrating" not in caster.active_conditions:
            concentration = Concentrating(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid,
                spell_name="Slow"
            )
            caster.add_condition(concentration, parent_event=effect_event)

        # Link effect to concentration
        conc = caster.active_conditions.get("Concentrating")
        if conc and isinstance(conc, Concentrating) and conc.spell_name == "Slow":
            conc.add_linked_condition(target.uuid, slowed.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is Slowed"
        )


# =============================================================================
# Haste (3rd-level Transmutation, Concentration)
# =============================================================================

class HasteEffect(BaseCondition):
    """Effect from Haste spell applied to the target.

    Effects:
    1. Speed doubled (+base_speed modifier)
    2. +2 AC bonus
    3. Advantage on DEX saving throws
    4. +1 action (but haste action limited to single weapon attack)

    When Haste ends (any reason: concentration, expiry, dispel), target suffers
    lethargy (Incapacitated for 1 round). Handled via _remove().
    """
    name: str = "Haste"
    description: str = "Speed doubled, +2 AC, advantage on DEX saves, +1 action"

    caster_uuid: Optional[UUID] = Field(default=None, description="UUID of the caster")
    apply_lethargy: bool = Field(default=True, description="Apply Incapacitated when Haste ends")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(type_cast(UUID, self.target_entity_uuid))
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target not found"
            )

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # 1. Speed doubled: add base_speed as modifier
        base_speed_modifier = target.action_economy.movement.get_base_modifier()
        if base_speed_modifier:
            speed_bonus = base_speed_modifier.value
            speed_mod = NumericalModifier(
                name="Haste",
                value=speed_bonus,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
            target.action_economy.movement.self_static.add_value_modifier(speed_mod)
            outs.append((target.action_economy.movement.uuid, speed_mod.uuid))

        # 2. +2 AC
        ac_mod = NumericalModifier(
            name="Haste",
            value=2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        target.equipment.ac_bonus.self_static.add_value_modifier(ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, ac_mod.uuid))

        # 3. Advantage on DEX saving throws
        dex_save = target.saving_throws.get_saving_throw("dexterity")
        dex_adv = AdvantageModifier(
            name="Haste",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        dex_mod_uuid = dex_save.bonus.self_static.add_advantage_modifier(dex_adv)
        outs.append((dex_save.bonus.uuid, dex_mod_uuid))

        # 4. +1 action
        action_mod = NumericalModifier(
            name="Haste",
            value=1,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        target.action_economy.actions.self_static.add_value_modifier(action_mod)
        outs.append((target.action_economy.actions.uuid, action_mod.uuid))

        # Handler: Extra Attack suppression on last action (haste action)
        ea_handler = self._create_extra_attack_suppression_handler()
        target.add_event_handler(ea_handler)
        handler_uuids.append(ea_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Haste to {target.name}"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_extra_attack_suppression_handler(self) -> EventHandler:
        """Suppress Extra Attack on the last remaining action (the haste action).

        Logic: When remaining_actions <= 1, this is the haste action — suppress EA.
        Otherwise, normal action — EA allowed.
        """
        target_uuid = type_cast(UUID, self.target_entity_uuid)

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            entity = Entity.get(target_uuid)
            if not entity:
                return None

            # Only affect action-cost attacks (not OA, not bonus action attacks, not Extra Attack)
            if isinstance(event, ActionEvent):
                has_action_cost = any(
                    c.cost_type == "actions" and c.cost > 0 for c in event.costs
                )
                if not has_action_cost:
                    return None

            # Check remaining actions: if <= 1, this is the haste action
            remaining_actions = entity.action_economy.actions.normalized_score
            if remaining_actions <= 1:
                # Suppress Extra Attack by zeroing the resource
                if entity.action_economy.has_resource("extra_attacks"):
                    entity.action_economy.resources["extra_attacks"].current = 0

            return None

        return EventHandler(
            name="Haste: Extra Attack Suppression",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=target_uuid
                )
            ],
            event_processor=processor
        )

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Apply lethargy (Incapacitated 1 round) when Haste ends, if apply_lethargy is True."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self.apply_lethargy and target and target.is_active:
            lethargy = Incapacitated(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
            lethargy.duration.duration_type = DurationType.ROUNDS
            lethargy.duration.duration = 1
            target.add_condition(lethargy, parent_event=event)
        return super()._remove(event)


class Haste(SpellAction):
    """Haste - 3rd level Transmutation (Concentration)

    Choose a willing creature that you can see within range. Until the spell ends,
    the target's speed is doubled, it gains a +2 bonus to AC, it has advantage on
    Dexterity saving throws, and it gains an additional action on each of its turns.
    That action can be used only to take the Attack (one weapon attack only),
    Dash, Disengage, Hide, or Use an Object action.

    When the spell ends, the target can't move or take actions until after its
    next turn, as a wave of lethargy sweeps over it.
    """
    name: str = Field(default="Haste")
    description: str = Field(default="Double speed, +2 AC, DEX adv, +1 action")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="transmutation")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30)
    )
    valid_target_filter: str = Field(default="all")

    def get_range(self) -> Range:
        return self.spell_range

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target is in LOS and range."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return declaration_event.cancel(status_message="No target")

        if target.uuid not in caster.senses.entities:
            return declaration_event.cancel(status_message=f"{target.name} not visible")

        distance = caster.senses.get_feet_distance(target.senses.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Haste to the target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Hasting {target.name}"
        )

        # Apply HasteEffect to target
        haste_effect = HasteEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid
        )
        target.add_condition(haste_effect, parent_event=effect_event)

        # Apply Concentrating to caster
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Haste"
        )
        caster.add_condition(concentration, parent_event=effect_event)

        # Link HasteEffect to Concentrating
        conc = caster.active_conditions.get("Concentrating")
        if conc and isinstance(conc, Concentrating) and conc.spell_name == "Haste":
            conc.add_linked_condition(target.uuid, haste_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is Hasted"
        )

