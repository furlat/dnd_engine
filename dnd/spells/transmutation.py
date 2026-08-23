"""Transmutation spells - transforming matter and energy.

Contains: SpikeGrowth, Slow, Haste, Darkvision, JumpSpell, ExpeditiousRetreat, Disintegrate,
          EnhanceAbility, EnlargeReduce, Regenerate
"""
from typing import Any, Dict, Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.core.base_actions import (
    ActionCategory,
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    ActionInformationOperation,
    ActionWorldEffectAnchor,
    ActionWorldEffectCertainty,
    ActionWorldEffectProfile,
    ActionWorldEffectScope,
    ActionWorldEffectShape,
    BaseAction,
    Cost,
    InformationEffectProfile,
    OutcomeResolution,
    PositionDiscoveryContract,
    TargetEffectDisposition,
    TargetType,
)
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.base_conditions import BaseCondition
from dnd.types.conditions import (
    ConditionAgencyDenial,
    ConditionTag,
    DurationType,
    HazardFilter,
)
from dnd.types.spatial_effects import SpatialEffectTriggerKind
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.registration import get_content_declaration
from dnd.types.actions import (
    ActionEconomyCostType,
    HasteActionPolicy,
    RestrictedActionGrant,
    RestrictedActionKind,
)
from dnd.types.senses import SensesType
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventType,
    EventHandler,
    EventQueue,
    Trigger,
)
from dnd.core.events.resolution_events import (
    Range,
    RangeType,
    Damage,
    Healing,
)
from dnd.core.events.world_events import (
    SpatialChangeEvent,
    ForcedMovementEvent,
)
from dnd.types.abilities import AbilityName
from dnd.types.rolls import AttackOutcome
from dnd.types.rolls import DieSize
from dnd.types.damage import DamageType
from dnd.types.creatures import Size
from dnd.core.modifiers import NumericalModifier, AdvantageModifier
from dnd.types.rolls import AdvantageStatus
from dnd.core.values import ModifiableValue
from dnd.core.aoe import AoEShape, Cube
from dnd.core.gridmap import get_map
from dnd.entities.entity import Entity
from dnd.conditions import (
    Concentrating,
    ConcentrationActionMarker,
    Dashing,
    GrantedSenseModeCondition,
    Restrained,
)
from dnd.entities.creature_transforms import apply_incapacitated_transform
from dnd.actions.standard import (
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
)
from dnd.spatial.area_conditions import AreaCondition
from dnd.spells.content_metadata import srd_action_identity, srd_spell_identity
from dnd.spells.spell_utils import fire_heal_roll_result
from dnd.content.spatial_effect_recipes import SPIKE_GROWTH_SURFACE_RECIPE


def _parse_damage_dice(dice_expression: str) -> tuple[int, int]:
    """Parse the condition's validated ``NdS`` damage expression."""
    count_text, separator, sides_text = dice_expression.lower().partition("d")
    if separator != "d" or not count_text.isdigit() or not sides_text.isdigit():
        raise ValueError(f"Invalid damage dice expression: {dice_expression!r}")
    return int(count_text), int(sides_text)


class SpikeGrowthZone(AreaCondition):
    """Manage the hidden damaging terrain created by Spike Growth.

    The condition independently owns position-indexed entry handlers. Entering
    creatures other than the caster
    take the configured piercing damage.
    """
    name: str = Field(default="Spike Growth Zone", description="Condition name.")
    description: str = Field(
        default="Sharp spikes and thorns deal 2d4 piercing per 5ft traveled",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    zone_shape: str = Field(default="sphere", description="Zone shape key.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether the zone marks terrain as difficult.")
    hazard_filter: Optional[HazardFilter] = Field(
        default=HazardFilter.NON_SOURCE,
        description="Hazard visibility filter owned by the spatial effect.",
    )
    spell_dc: int = Field(default=10, description="Spell DC for perception to notice")
    damage_dice: str = Field(default="2d4", description="Damage dice applied on each entered tile.")

    def model_post_init(self, __context: Any) -> None:
        """Synchronize the marker stealth DC with the caster's spell save DC."""
        super().model_post_init(__context)
        self.condition_stealth_dc = self.spell_dc

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry damage (2d4 piercing per tile entered)."""
        source_uuid = self.source_entity_uuid
        damage_dice = self.damage_dice

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            if entity.uuid == source_uuid:
                return None

            count, value = _parse_damage_dice(damage_dice)
            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=type_cast(DieSize, value), dice_numbers=count, damage_bonus=dmg_bonus,
                damage_type=DamageType.PIERCING
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
            entity.receive_damage(damage_roll.total, DamageType.PIERCING, source_uuid, parent_event=event.uuid)

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


@srd_spell_identity(
    content_id="spell.spike_growth",
    display_name="Spike Growth",
    description="Transform ground into hidden damaging spikes.",
    school="transmutation",
    level=2,
    source_page=182,
    sort_order=10,
)
class SpikeGrowth(SpellAction):
    """Create a concentration zone of difficult, damaging terrain.

    The spell creates a caster-owned `SpikeGrowthZone`, links it to
    concentration, and lets the zone condition handle terrain, hazards, and
    spatial-entry damage.
    """
    name: str = Field(default="Spike Growth", description="Spell name.")
    description: str = Field(
        default="20ft radius difficult terrain, 2d4 piercing per 5ft traveled",
        description="Rules-facing zone summary.",
    )
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.PIERCING, description="Primary damage type for VFX")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for spike growth targeting.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=150),
        description="Maximum range for the zone center.",
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Spike Growth Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action-economy costs paid to cast the spell.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in range and visible."""
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Spike Growth - create zone and apply concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Spike Growth at {target_pos}"
        )

        zone = materialize_spatial_condition(
            SPIKE_GROWTH_SURFACE_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=SpikeGrowthZone,
            condition_fields={
                "spell_dc": dc,
                "arbitration_potency": dc,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Spike Growth field could not be established",
            )

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Spike Growth active: 20ft radius at {target_pos}, difficult terrain + 2d4 damage per 5ft"
        )


class SlowedEffect(BaseCondition):
    """Apply Slow's per-target failed-save debuff bundle.

    The engine models speed, Armor Class, Dexterity-save, reaction, action or
    bonus-action lockout, and Extra Attack suppression. A repeat Wisdom save at
    turn end removes the condition on success.
    """
    name: str = Field(default="Slowed", description="Condition name.")
    description: str = Field(
        default="Speed halved, -2 AC, -2 DEX saves, no reactions, limited actions",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    spell_dc: int = Field(default=0, description="DC for repeat WIS save")
    caster_uuid: Optional[UUID] = Field(default=None, description="UUID of the caster")

    _lockout_modifier_uuid: Optional[UUID] = PrivateAttr(default=None)
    _lockout_target_mv_uuid: Optional[UUID] = PrivateAttr(default=None)

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

        base_speed_modifier = target.action_economy.movement.get_base_modifier()
        if base_speed_modifier and not target.ignore_magical_speed_reduction:
            speed_penalty = -(base_speed_modifier.value // 2)
            speed_mod = NumericalModifier(
                name="Slowed",
                value=speed_penalty,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
            target.action_economy.movement.self_static.add_value_modifier(speed_mod)
            outs.append((target.action_economy.movement.uuid, speed_mod.uuid))

        ac_mod = NumericalModifier(
            name="Slowed",
            value=-2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        target.equipment.ac_bonus.self_static.add_value_modifier(ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, ac_mod.uuid))

        dex_save = target.saving_throws.get_saving_throw(AbilityName.DEXTERITY)
        dex_mod = NumericalModifier(
            name="Slowed",
            value=-2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        dex_save.bonus.self_static.add_value_modifier(dex_mod)
        outs.append((dex_save.bonus.uuid, dex_mod.uuid))

        reaction_constraint_uuid = target.action_economy.reactions.self_static.add_max_constraint(
            constraint=NumericalModifier(
                name="Slowed",
                value=0,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((target.action_economy.reactions.uuid, reaction_constraint_uuid))

        lockout_handler = self._create_action_bonus_lockout_handler()
        target.add_event_handler(lockout_handler)
        handler_uuids.append(lockout_handler.uuid)

        turn_reset_handler = self._create_turn_start_reset_handler()
        target.add_event_handler(turn_reset_handler)
        handler_uuids.append(turn_reset_handler.uuid)

        no_ea_handler = self._create_no_extra_attack_handler()
        target.add_event_handler(no_ea_handler)
        handler_uuids.append(no_ea_handler.uuid)

        if self.caster_uuid and self.spell_dc > 0:
            repeat_save_handler = self._create_repeat_save_handler()
            target.add_event_handler(repeat_save_handler)
            handler_uuids.append(repeat_save_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Slowed to {target.name}",
            resulting_ac=target.ac_bonus().normalized_score
        )
        return outs, handler_uuids, [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            return {"resulting_ac": target.ac_bonus().normalized_score}
        return {}

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Remove the runtime action/bonus lockout on removal or rollback."""
        del parent_event
        if self._lockout_modifier_uuid is not None and self._lockout_target_mv_uuid is not None:
            mv = ModifiableValue.get(self._lockout_target_mv_uuid)
            if mv:
                mv.self_static.remove_max_constraint(self._lockout_modifier_uuid)
            self._lockout_modifier_uuid = None
            self._lockout_target_mv_uuid = None

    def _create_action_bonus_lockout_handler(self) -> EventHandler:
        """Lock bonus actions after an action is used, and actions after a bonus action."""
        target_uuid = type_cast(UUID, self.target_entity_uuid)
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, ActionEvent):
                return None
            if event.source_entity_uuid != target_uuid:
                return None
            if condition._lockout_modifier_uuid is not None:
                return None

            entity = Entity.get(target_uuid)
            if not entity:
                return None

            committed_cost_types = {
                cost.cost_type
                for cost in event.costs
                if cost.cost > 0
            }
            if ActionEconomyCostType.ACTIONS in committed_cost_types:
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
            elif ActionEconomyCostType.BONUS_ACTIONS in committed_cost_types:
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

        return EventHandler(
            name="Slowed: Action/Bonus Lockout",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=event_type,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=target_uuid
                )
                for event_type in (
                    EventType.BASE_ACTION,
                    EventType.ATTACK,
                    EventType.MOVEMENT,
                    EventType.CAST_SPELL,
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
        """Zero the extra-attacks resource for action-cost attacks while slowed."""
        target_uuid = type_cast(UUID, self.target_entity_uuid)

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            entity = Entity.get(target_uuid)
            if not entity:
                return None

            if isinstance(event, ActionEvent):
                has_action_cost = any(c.cost_type == "actions" for c in event.costs)
                if not has_action_cost:
                    return None

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

            slowed = target.active_conditions.get("Slowed")
            if not slowed or slowed.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Slowed", parent_event=event)
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name=AbilityName.WISDOM,
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
    """Apply Slow to failed-save targets in a forty-foot cube.

    Each target resolved by AoE convolution makes a Wisdom saving throw against
    the caster's spell save DC. Failures receive an individually linked
    `SlowedEffect`, allowing concentration cleanup to remove all affected
    targets.
    """
    name: str = Field(default="Slow", description="Spell name.")
    description: str = Field(default="40ft cube, WIS save or Slowed", description="Rules-facing spell summary.")
    spell_level: int = Field(default=3, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Maximum range for the AoE origin.",
    )
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Cube area used by Slow.")
    include_self: bool = Field(default=False, description="Whether the caster can be included in the AoE.")
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (0, 0),
                size_feet=40,
                centered=True
            )

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Slow's failed-save action-economy debuff branch."""
        if not isinstance(actor, Entity):
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.slow",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.slow.debuff",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="wisdom",
                    condition_fact_ids=(
                        "selected_target.condition.slowed",
                        "selected_target.reactions_blocked",
                        "selected_target.speed_reduced",
                    ),
                    condition_semantic_keys=frozenset({"dnd.spells.transmutation.SlowedEffect"}),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Slow to current target (called per target via convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.WISDOM,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.WISDOM).normalized_score

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

        slowed = SlowedEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(slowed, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if slowed.applied:
            concentration.add_linked_condition(target.uuid, slowed.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is Slowed"
        )


class HasteLethargyEffect(BaseCondition):
    """Own the one-round incapacitation transform left when Haste ends."""

    name: str = Field(default="Haste Lethargy", description="Condition name.")
    description: str = Field(
        default="Unable to move or take actions until the lethargy ends.",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and rules filters.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="Haste lethargy removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")
        outs = apply_incapacitated_transform(
            target,
            name=self.name,
            effect_source_uuid=self.source_entity_uuid,
        )
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Haste lethargy to {target.name}",
        )
        return outs, [], [], [], effect_event


class HasteEffect(BaseCondition):
    """Apply Haste's modifier bundle and cleanup lethargy.

    The effect doubles movement by adding the current base speed, grants +2 AC,
    advantage on Dexterity saves, and an explicitly restricted action budget.
    The budget never mutates ordinary actions or Extra Attack. Removal can apply
    one round of directly owned lethargy.
    """
    name: str = Field(default="Haste", description="Condition name.")
    description: str = Field(
        default=(
            "Speed doubled, +2 AC, advantage on DEX saves, "
            "one restricted Haste action"
        ),
        description="Rules-facing condition summary.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="UUID of the caster")
    apply_lethargy: bool = Field(default=True, description="Apply incapacitating lethargy when Haste ends")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(type_cast(UUID, self.target_entity_uuid))
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target not found"
            )

        outs: List[Tuple[UUID, UUID]] = []
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

        ac_mod = NumericalModifier(
            name="Haste",
            value=2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        target.equipment.ac_bonus.self_static.add_value_modifier(ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, ac_mod.uuid))

        dex_save = target.saving_throws.get_saving_throw(AbilityName.DEXTERITY)
        dex_adv = AdvantageModifier(
            name="Haste",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        dex_mod_uuid = dex_save.bonus.self_static.add_advantage_modifier(dex_adv)
        outs.append((dex_save.bonus.uuid, dex_mod_uuid))

        allowed_kinds = (
            frozenset({RestrictedActionKind.STANDARD_ACTION})
            if (
                target.action_economy.haste_action_policy
                is HasteActionPolicy.BG3_HONOUR
            )
            else frozenset(
                {
                    RestrictedActionKind.WEAPON_ATTACK,
                    RestrictedActionKind.DASH,
                    RestrictedActionKind.DISENGAGE,
                    RestrictedActionKind.HIDE,
                }
            )
        )
        target.action_economy.add_restricted_action_grant(
            RestrictedActionGrant(
                grant_id="haste",
                owner_uuid=self.uuid,
                resource_name="haste_action",
                display_name="Haste",
                allowed_kinds=allowed_kinds,
                replaced_cost_types=frozenset(
                    {
                        ActionEconomyCostType.ACTIONS,
                    }
                ),
            )
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Haste to {target.name}",
            resulting_ac=target.ac_bonus().normalized_score
        )
        return outs, [], [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            return {"resulting_ac": target.ac_bonus().normalized_score}
        return {}

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Apply the one-round Haste Lethargy effect when Haste ends."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if isinstance(target, Entity):
            target.action_economy.remove_restricted_action_grant(
                "haste",
                self.uuid,
            )
        if self.apply_lethargy and isinstance(target, Entity) and target.is_active:
            lethargy = HasteLethargyEffect(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
            lethargy.duration.duration_type = DurationType.ROUNDS
            lethargy.duration.duration = 1
            target.add_condition(lethargy, parent_event=event)
        return super()._remove(event)


class Haste(SpellAction):
    """Grant Haste to one visible target and link it to concentration.

    The target receives a `HasteEffect` linked from the caster's concentration
    condition. Cleanup removes the modifier bundle and, outside suppression
    paths, applies lethargy through the effect removal hook.
    """
    name: str = Field(default="Haste", description="Spell name.")
    description: str = Field(
        default=(
            "Double speed, +2 AC, DEX advantage, and one restricted action"
        ),
        description="Rules-facing spell summary.",
    )
    spell_level: int = Field(default=3, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for the target.",
    )
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target is in LOS and range."""
        return self._validate_entity_target_in_range_and_sight(declaration_event)

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

        haste_effect = HasteEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(haste_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if haste_effect.applied:
            concentration.add_linked_condition(target.uuid, haste_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is Hasted"
        )


class DarkvisionEffect(GrantedSenseModeCondition):
    """Grants 60ft darkvision to the target creature."""

    name: str = Field(default="Darkvision", description="Condition name.")
    description: str = Field(default="You can see in darkness within 60 feet", description="Condition description.")
    granted_sense_type: SensesType = Field(default=SensesType.DARKVISION)
    granted_sense_range_feet: int = Field(default=60, ge=0)


class DarkvisionSpell(SpellAction):
    """Second-level transmutation spell that grants 60-foot darkvision."""

    name: str = Field(default="Darkvision", description="Spell name.")
    description: str = Field(default="Grant 60ft darkvision to a willing creature", description="Spell description.")
    spell_level: int = Field(default=2, description="Spell slot level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=False, description="Darkvision does not require concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Spell range.")
    valid_target_filter: str = Field(default="self_or_allies", description="Valid target filter key.")

    def get_world_effect_profile(self, actor: Any) -> ActionWorldEffectProfile:
        """Declare the granted darkvision sense and possible discoveries.

        Args:
            actor: Entity discovering the spell. The sense contract is fixed.

        Returns:
            Typed information effects matching the runtime sense mode.
        """
        return ActionWorldEffectProfile(
            semantic_id="information.darkvision",
            information_effects=(
                InformationEffectProfile(
                    operation=ActionInformationOperation.GRANT_SENSE,
                    certainty=ActionWorldEffectCertainty.GUARANTEED,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.TARGET,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=60,
                    sense_type=SensesType.DARKVISION.name.lower(),
                ),
                InformationEffectProfile(
                    operation=ActionInformationOperation.REVEAL_REGION,
                    certainty=ActionWorldEffectCertainty.CONDITIONAL,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=60,
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} grants darkvision to {target.name}"
        )

        darkvision_effect = DarkvisionEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        darkvision_effect.duration.duration_type = DurationType.ROUNDS
        darkvision_effect.duration.duration = 4_800
        target.add_condition(darkvision_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} gains darkvision (60ft)"
        )


class Disintegrate(SpellAction):
    """Resolve Disintegrate's Dexterity save and force damage.

    Failed saves take 10d6 plus 40 force damage at the base slot level.
    Upcasting adds 3d6 per slot above sixth. Successful saves take no damage.
    """
    name: str = Field(default="Disintegrate", description="Spell name.")
    description: str = Field(
        default="DEX save or 10d6+40 force damage. 0 on save.",
        description="Rules-facing damage summary.",
    )
    spell_level: int = Field(default=6, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum ray range.",
    )
    projectile_type: Optional[str] = Field(default="ray", description="Client-facing projectile visual key.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FORCE, description="Primary damage type for VFX")

    include_self: bool = Field(default=False, description="Whether the caster can be included as a target.")
    valid_target_filter: str = Field(default="enemies", description="Target filter key for available action discovery.")

    base_damage_dice: int = Field(default=10, description="Number of d6 damage dice before upcasting.")
    base_damage_bonus: int = Field(default=40, description="Flat force damage bonus on a failed save.")

    def get_damage_dice_count(self) -> int:
        """10d6 base + 3d6 per level above 6th."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus * 3

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        num_dice = self.get_damage_dice_count()

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.DEXTERITY,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} dodges the ray"
            )

        damage_bonus = caster.get_spell_damage_bonus()
        force_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FORCE
        )
        damage_dice = force_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll
        final_damage = damage_roll.total + self.base_damage_bonus

        target.receive_damage(
            amount=final_damage,
            damage_type=DamageType.FORCE,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[force_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Disintegrate deals {final_damage} force damage to {target.name}"
        )


class JumpEffect(BaseCondition):
    """Triples the target's jump distance.

    Adds +2 to `entity.jump_distance_multiplier`, whose base value is 1.
    """
    name: str = Field(default="Jump", description="Condition name.")
    description: str = Field(default="Jump distance tripled", description="Rules-facing condition summary.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        outs: List[Tuple[UUID, UUID]] = []
        mod = NumericalModifier(
            name="Jump Spell",
            value=2,
            source_entity_uuid=self.source_entity_uuid or target.uuid,
            target_entity_uuid=target.uuid
        )
        mod_uuid = target.jump_distance_multiplier.self_static.add_value_modifier(mod)
        outs.append((target.jump_distance_multiplier.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self}
        ) if declaration_event else None

        return outs, [], [], [], effect_event


class JumpSpell(SpellAction):
    """Triple one creature's jump distance for one minute."""
    name: str = Field(default="Jump", description="Spell name.")
    description: str = Field(default="Triple a creature's jump distance", description="Rules-facing spell summary.")
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=False, description="Jump does not require concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Jump on {target.name}"
        )

        jump_effect = JumpEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        jump_effect.duration.duration_type = DurationType.ROUNDS
        jump_effect.duration.duration = 10
        target.add_condition(jump_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name}'s jump distance tripled"
        )


class BonusDash(BaseAction):
    """Bonus action Dash granted by Expeditious Retreat."""
    name: str = Field(default="Dash (Bonus)", description="Action name.")
    description: str = Field(default="Dash as a bonus action", description="Action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Bonus Dash", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action-economy costs paid to take the bonus Dash.")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        dashing = Dashing(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        dashing.duration.duration_type = DurationType.ROUNDS
        dashing.duration.duration = 1
        entity.add_condition(dashing, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{entity.name} dashes as a bonus action"
        )

class ExpeditiousRetreatEffect(BaseCondition):
    """Grants a bonus action Dash each turn."""
    name: str = Field(default="Expeditious Retreat", description="Condition name.")
    description: str = Field(default="You can Dash as a bonus action", description="Rules-facing condition summary.")
    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        bonus_dash = BonusDash(source_entity_uuid=target.uuid, template=True)
        target.register_condition_action(self, bonus_dash)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self}
        ) if declaration_event else None

        return [], [], [], [], effect_event

class ExpeditiousRetreat(SpellAction):
    """Grant the caster a concentration-linked bonus-action Dash template."""
    name: str = Field(default="Expeditious Retreat", description="Spell name.")
    description: str = Field(default="Bonus action Dash each turn", description="Rules-facing spell summary.")
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF),
        description="Self range used by action discovery and validation.",
    )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Expeditious Retreat"
        )

        retreat_effect = ExpeditiousRetreatEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            tags={ConditionTag.MAGICAL}
        )
        caster.add_condition(retreat_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, retreat_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} can now Dash as a bonus action"
        )


class EnhanceAbilityEffect(BaseCondition):
    """Grant advantage on one ability's checks.

    The constitution variant also grants 2d6 temporary hit points.
    """
    name: str = Field(default="Enhance Ability", description="Condition name.")
    description: str = Field(default="Advantage on one ability's checks", description="Rules-facing condition summary.")
    ability_type: str = Field(default="strength", description="Ability key enhanced by the condition.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        ability_name = type_cast(AbilityName, self.ability_type)
        ability = target.ability_scores.get_ability(ability_name)
        mod_uuid = ability.ability_score.self_static.add_advantage_modifier(
            AdvantageModifier(
                name=f"Enhance Ability ({self.ability_type.title()})",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid
            )
        )
        outs.append((ability.ability_score.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Enhanced {self.ability_type.title()} on {target.name}"
        )

        if self.ability_type == "constitution":
            healing = Healing(
                source_entity_uuid=self.source_entity_uuid,
                healing_dice=6, dice_numbers=2,
                healing_bonus=ModifiableValue.create(
                    source_entity_uuid=self.source_entity_uuid, base_value=0, value_name="Bear's Endurance"
                )
            )
            temp_hp = healing.get_dice().roll.total
            target.grant_temporary_hit_points(
                temp_hp,
                self.source_entity_uuid,
                source_description="Enhance Ability (Bear's Endurance)",
                parent_event=effect_event.uuid,
            )

        return outs, [], [], [], effect_event


class EnhanceAbility(SpellAction):
    """Apply a concentration-linked Enhance Ability effect.

    This implementation stores the selected ability on the action instance and
    applies the corresponding `EnhanceAbilityEffect` to the target.
    """
    name: str = Field(default="Enhance Ability", description="Spell name.")
    description: str = Field(default="Advantage on one ability's checks (concentration)", description="Rules-facing spell summary.")
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")
    enhance_ability_type: str = Field(default="strength", description="Ability key selected for enhancement.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_or_self_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        concentration = self.ensure_concentration(execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Enhancing {self.enhance_ability_type.title()} on {target.name}"
        )

        effect = EnhanceAbilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            ability_type=self.enhance_ability_type,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(effect, parent_event=effect_event)
        if effect.applied:
            concentration.add_linked_condition(target.uuid, effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Enhanced {self.enhance_ability_type.title()} on {target.name}"
        )

_SIZE_ORDER = [Size.TINY, Size.SMALL, Size.MEDIUM, Size.LARGE, Size.HUGE, Size.GARGANTUAN]


def _shift_size(current: Size, delta: int) -> Size:
    """Shift size up or down, clamping to valid range."""
    idx = _SIZE_ORDER.index(current)
    new_idx = max(0, min(len(_SIZE_ORDER) - 1, idx + delta))
    return _SIZE_ORDER[new_idx]


class EnlargeReduceEffect(BaseCondition):
    """Change target size and Strength roll advantage state.

    Enlarge increases size by one category and grants advantage on Strength
    checks and saves. Reduce decreases size by one category and grants
    disadvantage. Size-based damage dice are handled by `Entity.get_damages()`.
    """
    name: str = Field(default="Enlarge/Reduce", description="Condition name.")
    description: str = Field(default="Size changed by magic", description="Rules-facing condition summary.")
    mode: str = Field(default="enlarge", description="Either 'enlarge' or 'reduce'.")
    original_size: Optional[str] = Field(default=None, description="Original size value restored when the effect ends.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        self.original_size = target.size.value

        if self.mode == "enlarge":
            target.size = _shift_size(target.size, 1)
            adv_value = AdvantageStatus.ADVANTAGE
        else:
            target.size = _shift_size(target.size, -1)
            adv_value = AdvantageStatus.DISADVANTAGE

        str_ability = target.ability_scores.get_ability(AbilityName.STRENGTH)
        mod_uuid = str_ability.ability_score.self_static.add_advantage_modifier(
            AdvantageModifier(
                name=f"{'Enlarge' if self.mode == 'enlarge' else 'Reduce'} (STR checks)",
                value=adv_value,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid
            )
        )
        outs.append((str_ability.ability_score.uuid, mod_uuid))

        str_save = target.saving_throws.get_saving_throw(AbilityName.STRENGTH)
        save_mod_uuid = str_save.bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name=f"{'Enlarge' if self.mode == 'enlarge' else 'Reduce'} (STR saves)",
                value=adv_value,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid
            )
        )
        outs.append((str_save.bonus.uuid, save_mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{'Enlarged' if self.mode == 'enlarge' else 'Reduced'} {target.name} to {target.size.value}"
        )

        return outs, [], [], [], effect_event

    def _remove(self, removal_event: Optional[Event] = None) -> Optional[Event]:
        """Restore original size on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and self.original_size:
            try:
                target.size = Size(self.original_size)
            except ValueError:
                pass
        return super()._remove(removal_event)


class EnlargeReduce(SpellAction):
    """Apply Enlarge or Reduce with concentration-linked cleanup.

    Enemy targets receive a Constitution save before the size effect is applied.
    Willing targets and the caster are affected directly.
    """
    name: str = Field(default="Enlarge/Reduce", description="Spell name.")
    description: str = Field(
        default="Change creature size, STR advantage/disadvantage, +/-1d4 weapon damage",
        description="Rules-facing spell summary.",
    )
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")
    enlarge_mode: str = Field(default="enlarge", description="Either 'enlarge' or 'reduce'.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        if target.uuid != caster.uuid and caster.is_enemy(target):
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name=AbilityName.CONSTITUTION,
                dc=dc,
                parent_event=execution_event.uuid
            )
            _, _, success = target.saving_throw(save_request)
            if success:
                return execution_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"{target.name} resists {self.name} (CON save)"
                )

        concentration = self.ensure_concentration(execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{'Enlarging' if self.enlarge_mode == 'enlarge' else 'Reducing'} {target.name}"
        )

        effect = EnlargeReduceEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            mode=self.enlarge_mode,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(effect, parent_event=effect_event)
        if effect.applied:
            concentration.add_linked_condition(target.uuid, effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} {'enlarged' if self.enlarge_mode == 'enlarge' else 'reduced'} to {target.size.value}"
        )


@srd_action_identity(
    content_id="action.spell.telekinesis.restrain",
    display_name="Telekinesis: Restrain",
    description="Restrain the creature currently held by Telekinesis.",
    parent_spell_name="Telekinesis",
    source_page=185,
    sort_order=862,
)
class TelekinesisRestrain(BaseAction):
    """Restrain the creature currently grabbed by Telekinesis.

    This zero-cost granted action is registered after a failed Strength save,
    applies Restrained, links it to the caster's concentration, and then removes
    both temporary Telekinesis follow-up actions.
    """
    name: str = Field(default="Telekinesis: Restrain", description="Action name.")
    description: str = Field(default="Restrain the telekinetically grabbed creature", description="Action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category.")
    costs: List[Cost] = Field(default_factory=list, description="Action-economy costs paid by the follow-up action.")

    grabbed_entity_uuid: UUID = Field(description="UUID of the grabbed entity")
    _follow_up_action_uuids: Tuple[UUID, ...] = PrivateAttr(
        default_factory=tuple,
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        grabbed = Entity.get(self.grabbed_entity_uuid)
        if not grabbed:
            return declaration_event.cancel(status_message="Grabbed entity not found")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Validated Telekinesis: Restrain"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:

        caster = Entity.get(self.source_entity_uuid)
        grabbed = Entity.get(self.grabbed_entity_uuid)
        if not caster or not grabbed:
            return execution_event.cancel(status_message="Entity not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Restraining {grabbed.name} with Telekinesis"
        )

        restrained = Restrained(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=grabbed.uuid,
            tags={ConditionTag.MAGICAL}
        )
        grabbed.add_condition(restrained, parent_event=effect_event)

        conc = caster.active_conditions.get("Concentrating")
        if isinstance(conc, Concentrating):
            conc.add_linked_condition(grabbed.uuid, restrained.uuid)

        for action_uuid in self._follow_up_action_uuids:
            caster.unregister_action_by_uuid(action_uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{grabbed.name} restrained by Telekinesis"
        )


@srd_action_identity(
    content_id="action.spell.telekinesis.move",
    display_name="Telekinesis: Move",
    description="Move the creature currently held by Telekinesis.",
    parent_spell_name="Telekinesis",
    source_page=185,
    sort_order=861,
)
class TelekinesisMove(BaseAction):
    """Move the creature currently grabbed by Telekinesis up to thirty feet.

    This zero-cost granted action validates a nearby destination, emits a forced
    movement event, updates the entity's grid position, and removes both
    temporary Telekinesis follow-up actions.
    """
    name: str = Field(default="Telekinesis: Move", description="Action name.")
    description: str = Field(default="Move the telekinetically grabbed creature up to 30ft", description="Action summary.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category.")
    costs: List[Cost] = Field(default_factory=list, description="Action-economy costs paid by the follow-up action.")

    grabbed_entity_uuid: UUID = Field(description="UUID of the grabbed entity")
    _follow_up_action_uuids: Tuple[UUID, ...] = PrivateAttr(
        default_factory=tuple,
    )

    def get_valid_targets(self) -> List[Tuple[int, int]]:
        """Return walkable, unoccupied positions within 30ft of the grabbed entity."""
        grabbed = Entity.get(self.grabbed_entity_uuid)
        if not grabbed:
            return []
        grid = get_map()
        gx, gy = grabbed.senses.position
        valid = []
        for dx in range(-6, 7):
            for dy in range(-6, 7):
                x, y = gx + dx, gy + dy
                if abs(dx) + abs(dy) > 6:
                    continue
                if not grid.is_walkable(x, y):
                    continue
                entities_at = grid.get_entities_at((x, y))
                if entities_at and entities_at != {grabbed.uuid}:
                    continue
                valid.append((x, y))
        return valid

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        grabbed = Entity.get(self.grabbed_entity_uuid)
        if not grabbed:
            return declaration_event.cancel(status_message="Grabbed entity not found")

        target_pos = self.end_position
        if target_pos is None:
            return declaration_event.cancel(status_message="No target position")

        valid = self.get_valid_targets()
        if target_pos not in valid:
            return declaration_event.cancel(status_message="Invalid target position")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Validated Telekinesis: Move"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        caster = Entity.get(self.source_entity_uuid)
        grabbed = Entity.get(self.grabbed_entity_uuid)
        if not caster or not grabbed:
            return execution_event.cancel(status_message="Entity not found")

        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        start_pos = grabbed.senses.position

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Moving {grabbed.name} to {target_pos}"
        )

        forced_event = ForcedMovementEvent(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=grabbed.uuid,
            source_entity_name=caster.name,
            target_entity_name=grabbed.name,
            start_position=start_pos,
            end_position=target_pos,
            direction=(0, 0),
            intended_distance=abs(target_pos[0] - start_pos[0]) * 5 + abs(target_pos[1] - start_pos[1]) * 5,
            actual_distance=abs(target_pos[0] - start_pos[0]) * 5 + abs(target_pos[1] - start_pos[1]) * 5,
            cause="telekinesis",
            phase=EventPhase.DECLARATION,
            parent_event=effect_event.uuid,
            use_register=False,
        )
        forced_event = EventQueue.publish_declaration(forced_event)
        if not forced_event.canceled:
            forced_event = forced_event.phase_to(EventPhase.EXECUTION)
        if not forced_event.canceled:
            forced_event = forced_event.phase_to(EventPhase.EFFECT)
        if not forced_event.canceled:
            Entity.update_entity_position(
                grabbed,
                target_pos,
                parent_event=forced_event.uuid,
            )
            forced_event.phase_to(
                EventPhase.COMPLETION,
                end_position=grabbed.position,
                actual_distance=(
                    abs(grabbed.position[0] - start_pos[0])
                    + abs(grabbed.position[1] - start_pos[1])
                )
                * 5,
            )

        for action_uuid in self._follow_up_action_uuids:
            caster.unregister_action_by_uuid(action_uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{grabbed.name} moved to {target_pos} by Telekinesis"
        )


@srd_action_identity(
    content_id="action.spell.telekinesis.grab",
    display_name="Telekinesis",
    description="Maintain a telekinetic grab and expose its follow-up choices.",
    parent_spell_name="Telekinesis",
    source_page=185,
    sort_order=860,
    dependencies=(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=get_content_declaration(TelekinesisMove).ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        ),
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=get_content_declaration(TelekinesisRestrain).ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        ),
    ),
)
class TelekinesisGrab(BaseAction):
    """Contest one creature with Telekinesis and expose follow-up actions.

    The caster receives this action template while concentrating on Telekinesis.
    Each use costs one action. A failed Strength save registers zero-cost
    restrain and move follow-up actions against the grabbed creature.
    """
    name: str = Field(default="Telekinesis", description="Action name.")
    description: str = Field(default="Telekinetically grab a creature (STR save)", description="Action summary.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Telekinesis Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action-economy costs paid to use the maintained Telekinesis action.")

    spell_dc: int = Field(default=10, description="Strength save DC for the grab attempt.")
    valid_target_filter: str = Field(default="enemies", description="Target filter key for available action discovery.")

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not source or not target:
            return declaration_event.cancel(status_message="Entity not found")

        distance = source.distance_to_entity(target)
        if distance > 60:
            return declaration_event.cancel(status_message=f"Target out of range ({distance}ft > 60ft)")

        contact = source.senses.entities.get(target.uuid)
        if contact is None or not contact.visual:
            return declaration_event.cancel(status_message="Target not in line of sight")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Validated Telekinesis grab"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Entity not found")

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.STRENGTH,
            dc=self.spell_dc,
            parent_event=execution_event.uuid
        )
        _, _, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"STR save: {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Telekinesis (STR save)"
            )

        restrain = TelekinesisRestrain(
            source_entity_uuid=caster.uuid,
            grabbed_entity_uuid=target.uuid,
            template=True
        )
        move = TelekinesisMove(
            source_entity_uuid=caster.uuid,
            grabbed_entity_uuid=target.uuid,
            template=True
        )
        follow_up_action_uuids = (restrain.uuid, move.uuid)
        restrain._follow_up_action_uuids = follow_up_action_uuids
        move._follow_up_action_uuids = follow_up_action_uuids
        marker = caster.active_conditions.get("Concentration Action")
        if not isinstance(marker, ConcentrationActionMarker):
            return effect_event.cancel(
                status_message="Telekinesis concentration action owner missing",
            )
        caster.register_condition_action(marker, restrain)
        caster.register_condition_action(marker, move)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} grabbed by Telekinesis — choose Restrain or Move"
        )

class Telekinesis(SpellAction):
    """Begin maintaining Telekinesis and optionally grab an initial target.

    Casting registers a maintained `TelekinesisGrab` action on the caster and
    links that action marker to concentration cleanup. If the initial target is
    not the caster, the first grab resolves immediately without an extra action
    cost.
    """
    name: str = Field(default="Telekinesis", description="Spell name.")
    description: str = Field(default="Telekinetically grab, move, or restrain a creature (STR save)", description="Rules-facing spell summary.")
    spell_level: int = Field(default=5, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum range for the grab target.",
    )
    valid_target_filter: str = Field(default="enemies", description="Target filter key for available action discovery.")
    projectile_type: Optional[str] = Field(default="ray", description="Client-facing projectile visual key.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Telekinesis"
        )

        grab = TelekinesisGrab(
            source_entity_uuid=caster.uuid,
            spell_dc=dc,
            template=True
        )

        concentration = self.ensure_concentration(effect_event)
        marker = ConcentrationActionMarker(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            action_name=grab.name
        )
        caster.register_condition_action(marker, grab)
        caster.add_condition(marker, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, marker.uuid)

        if self.target_entity_uuid and self.target_entity_uuid != caster.uuid:
            first_grab = TelekinesisGrab(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=self.target_entity_uuid,
                spell_dc=dc,
                template=False,
                costs=[],
            )
            first_grab.apply()

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} channels Telekinesis"
        )


class RegeneratingEffect(BaseCondition):
    """Heal the target by one hit point at the start of each turn.

    The effect tracks ten combat rounds and removes itself once the counter is
    exhausted. It is not concentration-linked by the Regenerate spell.
    """
    name: str = Field(default="Regenerating", description="Condition name.")
    description: str = Field(
        default="Regenerating: heals 1 HP at the start of each turn",
        description="Rules-facing condition summary.",
    )
    rounds_remaining: int = Field(default=10, description="Remaining combat rounds before self-removal.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Register the turn-start healing handler."""
        if not self.target_entity_uuid:
            return [], [], [], [], None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        effect_event = declaration_event.phase_to(EventPhase.EFFECT)

        handler = EventHandler(
            name="Regenerating",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    name="Regenerating Turn Start",
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid
                )
            ],
            event_processor=self._on_turn_start
        )
        target.add_event_handler(handler)

        return [], [handler.uuid], [], [], effect_event

    def _on_turn_start(self, event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
        if self.rounds_remaining <= 0 or not self.target_entity_uuid:
            return event

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return event

        target.receive_healing(
            1, self.source_entity_uuid,
            source_description="Regenerate: 1 HP",
            parent_event=event.uuid
        )

        self.rounds_remaining -= 1
        if self.rounds_remaining <= 0:
            target.remove_condition("Regenerating", parent_event=event)

        return event


class Regenerate(SpellAction):
    """Apply Regenerate's burst heal and ongoing turn-start healing.

    The initial effect heals 4d8 plus 15 hit points. The follow-up
    `RegeneratingEffect` then heals one hit point at the start of the target's
    turns for the combat-duration approximation used by the engine.
    """
    name: str = Field(default="Regenerate", description="Spell name.")
    description: str = Field(default="Heal 4d8+15 instantly, then 1 HP/round for 10 rounds", description="Rules-facing healing summary.")
    spell_level: int = Field(default=7, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        healing = Healing(
            name="Regenerate",
            source_entity_uuid=caster.uuid,
            healing_dice=8,
            dice_numbers=4,
            healing_bonus=ModifiableValue.create(
                source_entity_uuid=caster.uuid,
                base_value=15,
                value_name="Regenerate Healing"
            )
        )
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Regenerate heals {target.name}"
        )

        healing_roll = fire_heal_roll_result(caster.uuid, target.uuid, healing, effect_event, "Regenerate")
        actual = target.receive_healing(
            healing_roll.total, caster.uuid,
            source_description=f"Regenerate: {healing_roll.total}",
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level
        )

        regen = RegeneratingEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(regen, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Regenerate heals {target.name} for {actual} HP + 1 HP/round"
        )
