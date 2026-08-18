"""
Sorcerer Class Features & Metamagic

Implements:
- MetamagicActive: Condition that modifies spell templates via alt-field overrides
- Metamagic actions: QuickenedSpell, TwinnedSpell, DistantSpell
- Font of Magic: ConvertSlotToSP, ConvertSPToSlot
- Draconic Bloodline transient behavior: Elemental Affinity

Permanent Sorcery Point and Draconic Resilience structure is installed by the
character composer.
"""

from typing import Any, Optional, List, Tuple, Dict, Literal
from uuid import UUID
from pydantic import Field, PrivateAttr

from dnd.core.base_conditions import BaseCondition, Duration
from dnd.types.conditions import ConditionCategory, DurationType
from dnd.types.abilities import AbilityName
from dnd.core.base_actions import (
    ActionOverrideLease,
    ActionSelectionParameter,
    ActionSelectionParameterKind,
    BaseAction,
    ActionCategory,
    TargetType,
    Cost,
)
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.types.actions import CostType, spell_slot_cost_type
from dnd.core.action_execution import MovementTerminationReason
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventType,
    EventHandler,
    Trigger,
)
from dnd.core.events.resolution_events import (
    RangeType,
)
from dnd.types.spatial_effects import SpatialEffectTriggerKind
from dnd.types.damage import DamageType
from dnd.core.modifiers import ResistanceModifier
from dnd.types.damage import ResistanceStatus
from dnd.entities.entity import Entity
from dnd.actions.standard import (
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
    Move,
    MovementEvent,
    SpellAction,
)
from dnd.actions.operations import apply_action_overrides, clear_action_overrides
from dnd.types.world import MovementMode
from dnd.conditions import Charmed, Concentrating, Frightened
from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.content.spatial_effect_recipes import DRACONIC_PRESENCE_FIELD_RECIPE
from dnd.spatial.area_conditions import AreaCondition




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

    def _validate_move_prerequisites(
        self,
        event: MovementEvent,
        source: Entity,
    ) -> Optional[MovementTerminationReason]:
        """Require the accepted flying mode and currently manifested wings."""
        base_failure = super()._validate_move_prerequisites(event, source)
        if base_failure is not None:
            return base_failure
        if (
            event.movement_mode is not MovementMode.FLYING
            or "Dragon Wings" not in source.active_conditions
        ):
            return MovementTerminationReason.ACTION_DENIED
        return None


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


class DraconicPresenceAura(AreaCondition):
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
    zone_shape: str = Field(default="sphere", description="Aura shape.")
    zone_radius_feet: int = Field(default=60, description="Aura radius.")
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
            or target.position not in self.affected_positions
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
            ability_name=AbilityName.WISDOM,
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

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create the one exact hostile-turn handler for this field."""
        return EventHandler(
            name=f"Draconic Presence ({self.mode})",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    name="Hostile turn starts in Draconic Presence",
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                ),
            ],
            event_processor=self._on_hostile_turn_start,
        )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Draconic Presence caster does not exist",
            )
        return super()._apply(declaration_event)


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

        aura = materialize_spatial_condition(
            DRACONIC_PRESENCE_FIELD_RECIPE,
            caster.uuid,
            position=caster.position,
            faction=caster.faction,
            anchor_uuid=caster.uuid,
            condition_type=DraconicPresenceAura,
            condition_fields={
                "mode": self.mode,
                "duration": Duration(
                    duration=10,
                    duration_type=DurationType.ROUNDS,
                    source_entity_uuid=caster.uuid,
                    target_entity_uuid=caster.uuid,
                ),
                "effect_origin": execution_event.get_effect_origin(),
            },
        )
        aura_result = aura.activate(parent_event=execution_event)
        if aura_result is None or aura_result.canceled or not aura.applied:
            installed.cleanup_if_no_effects(parent_event=execution_event)
            return execution_event.cancel(
                status_message="Draconic Presence aura failed",
            )
        installed.add_linked_condition(aura.uuid, aura.uuid)
        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=(
                f"Draconic Presence ({self.mode}) is active"
            ),
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

    _override_lease: Optional[ActionOverrideLease] = PrivateAttr(default=None)

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
            self._override_lease = apply_action_overrides(
                target,
                filter_fn=lambda a: isinstance(a, SpellAction) and any(
                    c.cost_type == "actions" for c in a.costs
                ),
                overrides={"alt_cost_type": "bonus_actions"},
            )
        elif self.metamagic_type == "twinned":
            overrides_by_template: Dict[UUID, Dict[str, Any]] = {}
            for template in target.get_effective_action_templates():
                if (
                    isinstance(template, SpellAction)
                    and template.target_type == TargetType.ENTITY
                ):
                    overrides: Dict[str, Any] = {
                        "alt_target_type": TargetType.MULTI_ENTITY,
                        "alt_target_count": 2,
                    }
                    extra_sp = max(0, template.spell_level - 1)
                    if extra_sp > 0:
                        overrides["alt_extra_costs"] = [Cost(
                            name="Twinned Spell SP",
                            cost_type="actions",
                            cost=0,
                            resource_name="sorcery_points",
                            resource_cost=extra_sp,
                            evaluator=entity_action_economy_cost_evaluator,
                            resource_evaluator=entity_resource_cost_evaluator,
                        )]
                    overrides_by_template[template.uuid] = overrides
            self._override_lease = (
                target.install_action_template_overrides(
                    overrides_by_template,
                )
            )
        elif self.metamagic_type == "distant":
            overrides_by_template = {}
            for template in target.get_effective_action_templates():
                if isinstance(template, SpellAction):
                    if template.spell_range.type == RangeType.RANGE:
                        overrides_by_template[template.uuid] = {
                            "alt_range": template.spell_range.normal * 2,
                        }
                    elif template.spell_range.type == RangeType.REACH:
                        overrides_by_template[template.uuid] = {
                            "alt_range": 30,
                        }
            self._override_lease = (
                target.install_action_template_overrides(
                    overrides_by_template,
                )
            )

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

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release the exact override lease on removal or failed application."""
        del parent_event
        if self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target and self._override_lease is not None:
                clear_action_overrides(target, self._override_lease)
        self._override_lease = None


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
        self.selection_parameter = ActionSelectionParameter(
            kind=ActionSelectionParameterKind.LEVEL,
            value=self.slot_level,
        )
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
        self.selection_parameter = ActionSelectionParameter(
            kind=ActionSelectionParameterKind.LEVEL,
            value=self.slot_level,
        )
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
