"""
Sorcerer Class Features & Metamagic

Implements:
- SorceryPointsFeature: Grants SP resource + registers metamagic & Font of Magic actions
- MetamagicActive: Condition that modifies spell templates via alt-field overrides
- Metamagic actions: QuickenedSpell, TwinnedSpell, DistantSpell
- Font of Magic: ConvertSlotToSP, ConvertSPToSlot
- Draconic Bloodline: DraconicResilience, ElementalAffinity
"""

from typing import Any, Optional, List, Tuple, Dict, Literal
from uuid import UUID
from pydantic import Field

from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.base_actions import (
    BaseAction, ActionCategory, TargetType, Cost, CostType,
    ActionEvent, spell_slot_cost_type,
)
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger,
    RangeType,
)
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.entity import Entity
from dnd.actions import (
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
    entity_action_economy_cost_applier,
    Move,
    MovementEvent,
    SpellAction,
)
from dnd.actions_functional import apply_action_overrides, clear_action_overrides
from dnd.blocks.action_economy import RechargeType
from dnd.core.base_block import MovementMode
from dnd.conditions import Charmed, Concentrating, Frightened


class DraconicResilience(BaseCondition):
    """Apply Draconic Bloodline durability to a sorcerer.

    Attributes:
        name: Display name for the Draconic Bloodline resilience feature.
        description: Rules summary for the resilience benefit.
        hp_bonus: Maximum hit point bonus granted per sorcerer level.
    """
    name: str = Field(default="Draconic Resilience", description="Display name for the Draconic Bloodline resilience feature.")
    description: str = Field(default="AC = 13 + DEX when unarmored, +1 HP per sorcerer level", description="Rules summary for the resilience benefit.")
    hp_bonus: int = Field(default=1, description="Maximum hit point bonus granted per sorcerer level.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        outs: List[Tuple[UUID, UUID]] = []

        hp_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Draconic Resilience HP",
            value=self.hp_bonus,
        )
        mod_uuid = target.health.max_hit_points_bonus.self_static.add_value_modifier(hp_mod)
        outs.append((target.health.max_hit_points_bonus.uuid, mod_uuid))

        con_mod = target.ability_scores.get_ability("constitution").get_combined_values().normalized_score
        max_hp = target.health.get_max_hit_dices_points(con_mod) + target.health.max_hit_points_bonus.score
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Draconic Resilience applied",
            resulting_max_hp=max_hp
        )
        return outs, [], [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            con_mod = target.ability_scores.get_ability("constitution").get_combined_values().normalized_score
            max_hp = target.health.get_max_hit_dices_points(con_mod) + target.health.max_hit_points_bonus.score
            return {"resulting_max_hp": max_hp}
        return {}


class ElementalAffinityResistance(BaseCondition):
    """Temporary ancestry resistance purchased with one sorcery point.

    Attributes:
        name: Player-facing temporary resistance name.
        description: Rules summary for the temporary resistance.
        damage_type: Ancestry damage type resisted by this instance.
    """

    name: str = Field(
        default="Elemental Affinity Resistance",
        description="Player-facing temporary resistance name.",
    )
    description: str = Field(
        default=(
            "Gain resistance to the damage type associated with your "
            "draconic ancestry for 1 hour."
        ),
        description="Rules summary for the temporary resistance.",
    )
    damage_type: DamageType = Field(
        default=DamageType.FIRE,
        description="Ancestry damage type resisted by this instance.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.name = (
            f"Elemental Affinity Resistance ({self.damage_type.value})"
        )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if target is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Elemental Affinity target does not exist",
            )
        modifier = ResistanceModifier(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            name=self.name,
            value=ResistanceStatus.RESISTANCE,
            damage_type=self.damage_type,
        )
        modifier_uuid = (
            target.health.damage_reduction.self_static
            .add_resistance_modifier(modifier)
        )
        return [
            (target.health.damage_reduction.uuid, modifier_uuid),
        ], [], [], [], declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=(
                f"{target.name} gains {self.damage_type.value} resistance "
                "from Elemental Affinity"
            ),
        )


class ElementalAffinityResistanceAction(BaseAction):
    """Spend one sorcery point for one hour of ancestry resistance.

    Attributes:
        name: Human-readable Elemental Affinity action name.
        description: Rules summary for the resistance decision.
        target_type: Elemental Affinity affects only the sorcerer.
        action_category: Classifies Elemental Affinity as a class ability.
        damage_type: Selected ancestry damage type.
        costs: One sorcery point and no action-economy cost.
    """

    name: str = Field(
        default="Elemental Affinity Resistance",
        description="Human-readable Elemental Affinity action name.",
    )
    description: str = Field(
        default=(
            "Spend 1 sorcery point to gain your ancestry damage resistance "
            "for 1 hour."
        ),
        description="Rules summary for the resistance decision.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Elemental Affinity affects only the sorcerer.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ABILITY,
        description="Elemental Affinity is a class ability.",
    )
    damage_type: DamageType = Field(
        default=DamageType.FIRE,
        description="Selected ancestry damage type.",
    )
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Elemental Affinity Resistance",
                cost_type="actions",
                cost=0,
                resource_name="sorcery_points",
                resource_cost=1,
                evaluator=entity_action_economy_cost_evaluator,
                resource_evaluator=entity_resource_cost_evaluator,
            ),
        ],
        description="One sorcery point and no action-economy cost.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.name = (
            f"Elemental Affinity ({self.damage_type.value} Resistance)"
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        if Entity.get(self.source_entity_uuid) is None:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Elemental Affinity resistance validated",
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")
        effect = ElementalAffinityResistance(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            damage_type=self.damage_type,
            duration=Duration(
                duration=600,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
            ),
        )
        entity.add_condition(effect, parent_event=execution_event)
        if not effect.applied:
            return execution_event.cancel(
                status_message="Elemental Affinity resistance failed",
            )
        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=(
                f"Elemental Affinity grants {self.damage_type.value} "
                "resistance for 1 hour"
            ),
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(
            completion_event,
            self.source_entity_uuid,
        )


class DragonWingsActive(BaseCondition):
    """Mark manifested draconic wings as an evented creature state."""

    name: str = Field(
        default="Dragon Wings",
        description="Player-facing name for manifested dragon wings.",
    )
    description: str = Field(
        default="Manifested wings permit flying movement at normal speed.",
        description="Rules summary for the active wing state.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Dragon Wings target is missing",
            )
        target = Entity.get(self.target_entity_uuid)
        if target is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Dragon Wings target does not exist",
            )
        return [], [], [], [], declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target.name} manifests dragon wings",
        )


class Fly(Move):
    """Use manifested dragon wings for ordinary movement expenditure."""

    name: str = Field(
        default="Fly",
        description="Human-readable flying movement action name.",
    )
    description: str = Field(
        default="Move through traversable space using manifested wings.",
        description="Rules summary for Dragon Wings movement.",
    )
    movement_mode: MovementMode = Field(
        default=MovementMode.FLYING,
        description="Dragon Wings always use flying traversal costs.",
    )

    def _validate(self, declaration_event: MovementEvent) -> MovementEvent:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or "Dragon Wings" not in entity.active_conditions:
            return declaration_event.cancel(
                status_message="Dragon Wings are not manifested",
            )
        return super()._validate(declaration_event)


class DragonWings(BaseAction):
    """Manifest or dismiss the Draconic Bloodline's wings."""

    name: str = Field(
        default="Dragon Wings",
        description="Human-readable Dragon Wings action name.",
    )
    description: str = Field(
        default="Manifest or dismiss wings as a bonus action.",
        description="Rules summary for the Dragon Wings toggle.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Dragon Wings affect only the sorcerer.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ABILITY,
        description="Dragon Wings are a class ability.",
    )
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Dragon Wings",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            ),
        ],
        description="Bonus-action cost to manifest or dismiss the wings.",
    )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        if Entity.get(self.source_entity_uuid) is None:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Dragon Wings toggle validated",
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")
        active = entity.active_conditions.get("Dragon Wings")
        if active is not None:
            entity.remove_condition_by_uuid(
                active.uuid,
                parent_event=execution_event,
            )
            status = "Dragon wings dismissed"
        else:
            entity.add_condition(
                DragonWingsActive(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                ),
                parent_event=execution_event,
            )
            status = "Dragon wings manifested"
        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=status,
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(
            completion_event,
            self.source_entity_uuid,
        )


DraconicPresenceMode = Literal["awe", "fear"]


class DraconicPresenceImmunity(BaseCondition):
    """Remember one creature's successful save against one sorcerer."""

    name: str = Field(
        default="Draconic Presence Immunity",
        description="Source-specific Draconic Presence immunity marker.",
    )
    description: str = Field(
        default=(
            "This creature succeeded against one sorcerer's Draconic Presence "
            "and is immune to that sorcerer's aura for 24 hours."
        ),
        description="Rules summary for the source-specific immunity.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.STATUS,
        description="Visible rules state retained for its full duration.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.name = (
            f"Draconic Presence Immunity:{self.source_entity_uuid}"
        )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        return [], [], [], [], declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Draconic Presence immunity applied",
        )


class DraconicPresenceAura(BaseCondition):
    """Concentration-owned 60-foot aura of awe or fear."""

    name: str = Field(
        default="Draconic Presence",
        description="Active Draconic Presence aura name.",
    )
    description: str = Field(
        default=(
            "Hostile creatures that start their turns within 60 feet must "
            "save or become charmed by awe or frightened by fear."
        ),
        description="Rules summary for the active aura.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.STATUS,
        description="Active class-feature state.",
    )
    mode: DraconicPresenceMode = Field(
        default="awe",
        description="Whether the aura charms through awe or frightens.",
    )

    @staticmethod
    def _immunity_name(source_entity_uuid: UUID) -> str:
        return f"Draconic Presence Immunity:{source_entity_uuid}"

    def _on_hostile_turn_start(
        self,
        event: Event,
        _source_entity_uuid: UUID,
    ) -> Optional[Event]:
        if event.event_type is not EventType.TURN_START:
            return None
        caster = (
            Entity.get(self.source_entity_uuid)
            if self.source_entity_uuid is not None
            else None
        )
        target = (
            Entity.get(event.source_entity_uuid)
            if event.source_entity_uuid is not None
            else None
        )
        if (
            caster is None
            or target is None
            or not caster.is_enemy(target)
            or caster.senses.get_feet_distance(target.position) > 60
            or self._immunity_name(caster.uuid)
            in target.active_conditions
        ):
            return None

        effect_name = "Charmed" if self.mode == "awe" else "Frightened"
        existing = target.active_conditions.get(effect_name)
        if (
            existing is not None
            and existing.source_entity_uuid == caster.uuid
        ):
            return None

        request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=caster.spell_save_dc(),
            parent_event=event.uuid,
            condition_context=self.name,
        )
        _, _, success = target.saving_throw(request)
        if success:
            target.add_condition(
                DraconicPresenceImmunity(
                    source_entity_uuid=caster.uuid,
                    target_entity_uuid=target.uuid,
                    duration=Duration(
                        duration=14_400,
                        duration_type=DurationType.ROUNDS,
                        source_entity_uuid=caster.uuid,
                        target_entity_uuid=target.uuid,
                    ),
                ),
                parent_event=event,
            )
            return None

        effect_type = Charmed if self.mode == "awe" else Frightened
        effect = effect_type(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        )
        target.add_condition(effect, parent_event=event)
        if effect.applied:
            self.add_linked_condition(target.uuid, effect.uuid)
        return None

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Draconic Presence target is missing",
            )
        caster = Entity.get(self.target_entity_uuid)
        if caster is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Draconic Presence caster does not exist",
            )
        handler = EventHandler(
            name=f"Draconic Presence ({self.mode})",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    name="Hostile turn starts in Draconic Presence",
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                ),
            ],
            event_processor=self._on_hostile_turn_start,
        )
        caster.add_event_handler(handler)
        return [], [handler.uuid], [], [], declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=(
                f"{caster.name} projects a Draconic Presence aura of "
                f"{self.mode}"
            ),
        )


class DraconicPresence(BaseAction):
    """Spend sorcery points to begin a concentration aura of awe or fear."""

    name: str = Field(
        default="Draconic Presence",
        description="Human-readable Draconic Presence action name.",
    )
    description: str = Field(
        default=(
            "Spend 5 sorcery points and concentrate for up to 1 minute on a "
            "60-foot aura of awe or fear."
        ),
        description="Rules summary for Draconic Presence.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Draconic Presence is centered on the sorcerer.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ABILITY,
        description="Draconic Presence is a class ability.",
    )
    mode: DraconicPresenceMode = Field(
        default="awe",
        description="Selected aura mode.",
    )
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Draconic Presence",
                cost_type="actions",
                cost=1,
                resource_name="sorcery_points",
                resource_cost=5,
                evaluator=entity_action_economy_cost_evaluator,
                resource_evaluator=entity_resource_cost_evaluator,
            ),
        ],
        description="One action and five sorcery points.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.name = f"Draconic Presence ({self.mode.title()})"

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        if Entity.get(self.source_entity_uuid) is None:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Draconic Presence ({self.mode}) validated",
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return execution_event.cancel(status_message="Entity not found")

        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name=self.name,
        )
        caster.add_condition(concentration, parent_event=execution_event)
        installed = caster.active_conditions.get("Concentrating")
        if not isinstance(installed, Concentrating):
            return execution_event.cancel(
                status_message="Draconic Presence concentration failed",
            )

        aura = DraconicPresenceAura(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            mode=self.mode,
            duration=Duration(
                duration=10,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid,
            ),
        )
        caster.add_condition(aura, parent_event=execution_event)
        if not aura.applied:
            installed.cleanup_if_no_effects(parent_event=execution_event)
            return execution_event.cancel(
                status_message="Draconic Presence aura failed",
            )
        installed.add_linked_condition(caster.uuid, aura.uuid)
        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=(
                f"Draconic Presence ({self.mode}) is active"
            ),
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(
            completion_event,
            self.source_entity_uuid,
        )


class MetamagicActive(BaseCondition):
    """Track the temporary override from an activated metamagic option.

    Attributes:
        name: Internal condition name for the active metamagic modifier.
        description: Rules summary for the pending metamagic override.
        condition_category: Condition category used for lifecycle and cleanup.
        metamagic_type: Metamagic option currently modifying spell templates.
    """
    name: str = Field(default="MetamagicActive", description="Internal condition name for the active metamagic modifier.")
    description: str = Field(default="Metamagic is active — next spell cast will be modified", description="Rules summary for the pending metamagic override.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS, description="Condition category used for lifecycle and cleanup.")
    metamagic_type: str = Field(default="quickened", description="Metamagic option currently modifying the caster's spell templates.")

    _modified_uuids: List[UUID] = []

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        if self.metamagic_type == "quickened":
            self._modified_uuids = apply_action_overrides(
                target,
                filter_fn=lambda a: isinstance(a, SpellAction) and any(
                    c.cost_type == "actions" for c in a.costs
                ),
                overrides={"alt_cost_type": "bonus_actions"},
            )
        elif self.metamagic_type == "twinned":
            self._modified_uuids = []
            for template in target.registered_actions:
                if (
                    isinstance(template, SpellAction)
                    and template.target_type == TargetType.ENTITY
                ):
                    template.alt_target_type = TargetType.MULTI_ENTITY
                    template.alt_target_count = 2
                    extra_sp = max(0, template.spell_level - 1)
                    if extra_sp > 0:
                        template.alt_extra_costs = [Cost(
                            name="Twinned Spell SP",
                            cost_type="actions",
                            cost=0,
                            resource_name="sorcery_points",
                            resource_cost=extra_sp,
                            evaluator=entity_action_economy_cost_evaluator,
                            resource_evaluator=entity_resource_cost_evaluator,
                        )]
                    self._modified_uuids.append(template.uuid)
        elif self.metamagic_type == "distant":
            self._modified_uuids = []
            for template in target.registered_actions:
                if isinstance(template, SpellAction):
                    if template.spell_range.type == RangeType.RANGE:
                        template.alt_range = template.spell_range.normal * 2
                        self._modified_uuids.append(template.uuid)
                    elif template.spell_range.type == RangeType.REACH:
                        template.alt_range = 30
                        self._modified_uuids.append(template.uuid)

        handler = EventHandler(
            name="MetamagicAutoRemove",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    name="CastSpell",
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
                Trigger(
                    name="CommittedCastCanceled",
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.CANCEL,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
            ],
            event_processor=self._on_spell_cast,
        )
        target.add_event_handler(handler)
        handler_uuids = [handler.uuid]

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Metamagic ({self.metamagic_type}) activated",
        )
        return [], handler_uuids, [], [], effect_event

    def _on_spell_cast(self, event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
        """Consume metamagic after a successful or execution-canceled cast."""
        if (
            event.phase is EventPhase.CANCEL
            and event.canceled_from_phase is not EventPhase.EXECUTION
        ):
            return event
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and self.name in target.active_conditions:
            target.remove_condition(self.name, parent_event=event)
        return event

    def cleanup_own_state(self, expire: bool = False, parent_event: Optional[Event] = None) -> bool:
        """Clear alt fields from modified templates."""
        if self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target:
                clear_action_overrides(target, self._modified_uuids)
        self._modified_uuids = []
        return super().cleanup_own_state(expire=expire, parent_event=parent_event)


class QuickenedSpell(BaseAction):
    """Activate Quickened Spell for the caster's next eligible spell.

    Attributes:
        name: Display name for the Quickened Spell metamagic action.
        description: Rules summary for the Quickened Spell override.
        target_type: Targeting mode for applying the metamagic to the caster.
        action_category: Discovery and reveal category for the action.
        costs: Sorcery point cost required to activate Quickened Spell.
    """
    name: str = Field(default="Quickened Spell", description="Display name for the Quickened Spell metamagic action.")
    description: str = Field(default="Next spell costs a bonus action instead of an action", description="Rules summary for the Quickened Spell override.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Quickened Spell targets the caster's own next spell template.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category used for discovery and reveal behavior.")
    costs: List[Cost] = Field(default_factory=lambda: [Cost(
        name="Quickened Spell",
        cost_type="actions",
        cost=0,
        resource_name="sorcery_points",
        resource_cost=2,
        evaluator=entity_action_economy_cost_evaluator,
        resource_evaluator=entity_resource_cost_evaluator,
    )], description="Sorcery point cost required to activate Quickened Spell.")

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        if "MetamagicActive" in entity.active_conditions:
            return declaration_event.cancel(status_message="Metamagic already active")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Quickened Spell validated")

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        entity.add_condition(MetamagicActive(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            metamagic_type="quickened",
        ), parent_event=execution_event)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message="Quickened Spell activated",
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class TwinnedSpell(BaseAction):
    """Activate Twinned Spell for the caster's next eligible spell.

    Attributes:
        name: Display name for the Twinned Spell metamagic action.
        description: Rules summary for the Twinned Spell override.
        target_type: Targeting mode for applying the metamagic to the caster.
        action_category: Discovery and reveal category for the action.
        costs: Base sorcery point cost required to activate Twinned Spell.
    """
    name: str = Field(default="Twinned Spell", description="Display name for the Twinned Spell metamagic action.")
    description: str = Field(default="Next single-target spell targets two creatures", description="Rules summary for the Twinned Spell override.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Twinned Spell targets the caster's own next eligible spell template.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category used for discovery and reveal behavior.")
    costs: List[Cost] = Field(default_factory=lambda: [Cost(
        name="Twinned Spell",
        cost_type="actions",
        cost=0,
        resource_name="sorcery_points",
        resource_cost=1,
        evaluator=entity_action_economy_cost_evaluator,
        resource_evaluator=entity_resource_cost_evaluator,
    )], description="Base sorcery point cost required to activate Twinned Spell.")

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        if "MetamagicActive" in entity.active_conditions:
            return declaration_event.cancel(status_message="Metamagic already active")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Twinned Spell validated")

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        entity.add_condition(MetamagicActive(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            metamagic_type="twinned",
        ), parent_event=execution_event)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message="Twinned Spell activated",
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class DistantSpell(BaseAction):
    """Activate Distant Spell for the caster's next eligible spell.

    Attributes:
        name: Display name for the Distant Spell metamagic action.
        description: Rules summary for the Distant Spell override.
        target_type: Targeting mode for applying the metamagic to the caster.
        action_category: Discovery and reveal category for the action.
        costs: Sorcery point cost required to activate Distant Spell.
    """
    name: str = Field(default="Distant Spell", description="Display name for the Distant Spell metamagic action.")
    description: str = Field(default="Next spell has double range", description="Rules summary for the Distant Spell override.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Distant Spell targets the caster's own next eligible spell template.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category used for discovery and reveal behavior.")
    costs: List[Cost] = Field(default_factory=lambda: [Cost(
        name="Distant Spell",
        cost_type="actions",
        cost=0,
        resource_name="sorcery_points",
        resource_cost=1,
        evaluator=entity_action_economy_cost_evaluator,
        resource_evaluator=entity_resource_cost_evaluator,
    )], description="Sorcery point cost required to activate Distant Spell.")

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        if "MetamagicActive" in entity.active_conditions:
            return declaration_event.cancel(status_message="Metamagic already active")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Distant Spell validated")

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        entity.add_condition(MetamagicActive(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            metamagic_type="distant",
        ), parent_event=execution_event)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message="Distant Spell activated",
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)

METAMAGIC_ACTIONS: Dict[str, type] = {
    "quickened": QuickenedSpell,
    "twinned": TwinnedSpell,
    "distant": DistantSpell,
}

SP_TO_SLOT_COST: Dict[int, int] = {1: 2, 2: 3, 3: 5, 4: 6, 5: 7}


class ConvertSlotToSP(BaseAction):
    """Convert one spell slot into sorcery points.

    Attributes:
        name: Display name for converting a spell slot into sorcery points.
        description: Rules summary for slot-to-sorcery-point conversion.
        target_type: Targeting mode for applying the conversion to the caster.
        action_category: Discovery and reveal category for the action.
        slot_level: Spell slot level converted into sorcery points.
        costs: Generated bonus-action and spell-slot costs for this conversion.
    """
    name: str = Field(default="Convert Slot to SP", description="Display name for converting a spell slot into sorcery points.")
    description: str = Field(default="Spend a spell slot to gain sorcery points", description="Rules summary for slot-to-sorcery-point conversion.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Font of Magic conversion targets the caster's own resources.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category used for discovery and reveal behavior.")
    slot_level: int = Field(default=1, ge=1, le=5, description="Spell slot level converted into sorcery points.")
    costs: List[Cost] = Field(default_factory=list, description="Generated bonus-action and spell-slot costs for this conversion.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        slot_cost_type = spell_slot_cost_type(self.slot_level)
        self.name = f"Slot\u2192SP L{self.slot_level}"
        self.costs = [
            Cost(
                name=f"Slot\u2192SP L{self.slot_level}",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            ),
            Cost(
                name=f"L{self.slot_level} Spell Slot",
                cost_type=slot_cost_type,
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            ),
        ]

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message=f"Slot\u2192SP L{self.slot_level} validated")

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        resource = entity.action_economy.resources.get("sorcery_points")
        if resource:
            resource.current = min(resource.current + self.slot_level, resource.maximum)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Slot\u2192SP L{self.slot_level}: gained {self.slot_level} SP",
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class ConvertSPToSlot(BaseAction):
    """Convert sorcery points into one spell slot.

    Attributes:
        name: Display name for converting sorcery points into a spell slot.
        description: Rules summary for sorcery-point-to-slot conversion.
        target_type: Targeting mode for applying the conversion to the caster.
        action_category: Discovery and reveal category for the action.
        slot_level: Spell slot level created from sorcery points.
        costs: Generated bonus-action and sorcery-point costs for conversion.
    """
    name: str = Field(default="Convert SP to Slot", description="Display name for converting sorcery points into a spell slot.")
    description: str = Field(default="Spend sorcery points to create a spell slot", description="Rules summary for sorcery-point-to-slot conversion.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Font of Magic conversion targets the caster's own resources.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category used for discovery and reveal behavior.")
    slot_level: int = Field(default=1, ge=1, le=5, description="Spell slot level created from sorcery points.")
    costs: List[Cost] = Field(default_factory=list, description="Generated bonus-action and sorcery-point costs for this conversion.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        sp_cost = SP_TO_SLOT_COST.get(self.slot_level, 2)
        self.name = f"{sp_cost}SP\u2192Slot L{self.slot_level}"
        self.costs = [
            Cost(
                name=f"{sp_cost}SP\u2192Slot L{self.slot_level}",
                cost_type="bonus_actions",
                cost=1,
                resource_name="sorcery_points",
                resource_cost=sp_cost,
                evaluator=entity_action_economy_cost_evaluator,
                resource_evaluator=entity_resource_cost_evaluator,
            ),
        ]

    def validate_requirements_for_discovery(self) -> bool:
        """Require a class-owned slot family independently of current costs."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False
        if not entity.has_spell_slot_capacity(self.slot_level):
            return False
        return super().validate_requirements_for_discovery()

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message=f"{SP_TO_SLOT_COST.get(self.slot_level, 2)}SP\u2192Slot L{self.slot_level} validated")

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        slot_cost_type_name: CostType = spell_slot_cost_type(self.slot_level)
        slot_value = entity.action_economy.spell_slot_value(self.slot_level)

        cost_modifiers = entity.action_economy.get_cost_modifiers(slot_cost_type_name)
        if cost_modifiers:
            slot_value.self_static.remove_value_modifier(cost_modifiers[-1].uuid)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{SP_TO_SLOT_COST.get(self.slot_level, 2)}SP\u2192Slot L{self.slot_level}: created slot",
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class SorceryPointsFeature(BaseCondition):
    """Grant sorcery points and related class-feature actions.

    Attributes:
        name: Display name for the Sorcery Points class feature.
        description: Rules summary for sorcery point resources and actions.
        sorcery_points: Maximum sorcery points granted by this feature.
        metamagic_choices: Metamagic option keys registered as actions.
    """
    name: str = Field(default="Sorcery Points Feature", description="Display name for the Sorcery Points class feature.")
    description: str = Field(default="Sorcery points for metamagic and Font of Magic", description="Rules summary for sorcery point resources and granted actions.")
    sorcery_points: int = Field(default=2, description="Maximum sorcery points granted by this feature.")
    metamagic_choices: List[str] = Field(default_factory=list, description="Metamagic option keys registered as actions by this feature.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        target.action_economy.add_resource(
            "sorcery_points", self.sorcery_points, RechargeType.LONG_REST
        )

        for choice in self.metamagic_choices:
            action_cls = METAMAGIC_ACTIONS.get(choice)
            if action_cls:
                target.register_action(action_cls(
                    source_entity_uuid=target.uuid, template=True
                ))

        for slot_level in range(1, 6):
            slot_value = target.action_economy.spell_slot_value(slot_level)
            base_mod = slot_value.get_base_modifier()
            if base_mod and base_mod.normalized_value > 0:
                target.register_action(ConvertSlotToSP(
                    source_entity_uuid=target.uuid, slot_level=slot_level, template=True
                ))
                target.register_action(ConvertSPToSlot(
                    source_entity_uuid=target.uuid, slot_level=slot_level, template=True
                ))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Sorcery Points Feature applied",
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("sorcery_points")

            metamagic_names = {
                "quickened": "Quickened Spell",
                "twinned": "Twinned Spell",
                "distant": "Distant Spell",
            }
            for choice in self.metamagic_choices:
                action_name = metamagic_names.get(choice)
                if action_name:
                    target.unregister_action(action_name)

            for slot_level in range(1, 6):
                target.unregister_action(f"Slot\u2192SP L{slot_level}")
                sp_cost = SP_TO_SLOT_COST.get(slot_level, 2)
                target.unregister_action(f"{sp_cost}SP\u2192Slot L{slot_level}")

            if "MetamagicActive" in target.active_conditions:
                target.remove_condition("MetamagicActive", parent_event=event)

        return super()._remove(event)
