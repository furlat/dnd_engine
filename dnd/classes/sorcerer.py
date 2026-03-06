"""
Sorcerer Class Features & Metamagic

Implements:
- SorceryPointsFeature: Grants SP resource + registers metamagic & Font of Magic actions
- MetamagicActive: Condition that modifies spell templates via alt-field overrides
- Metamagic actions: QuickenedSpell, TwinnedSpell, DistantSpell
- Font of Magic: ConvertSlotToSP, ConvertSPToSlot
- Draconic Bloodline: DraconicResilience, ElementalAffinity
"""

from typing import Any, Optional, List, Tuple, Dict
from uuid import UUID
from pydantic import Field

from dnd.core.base_conditions import BaseCondition, ConditionCategory
from dnd.core.base_actions import (
    BaseAction, ActionCategory, TargetType, Cost, CostType,
    ActionEvent, spell_slot_cost_type,
)
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger,
    RangeType,
)
from dnd.core.modifiers import (
    NumericalModifier, DamageType,
    ResistanceModifier, ResistanceStatus,
)
from dnd.entity import Entity
from dnd.actions import (
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
    entity_action_economy_cost_applier,
    SpellAction,
)
from dnd.actions_functional import apply_action_overrides, clear_action_overrides


# =============================================================================
# DRACONIC RESILIENCE CONDITION (L1)
# =============================================================================

class DraconicResilience(BaseCondition):
    """Draconic Bloodline L1: +1 HP per level, AC = 13 + DEX when unarmored."""
    name: str = "Draconic Resilience"
    description: str = "AC = 13 + DEX when unarmored, +1 HP per sorcerer level"
    hp_bonus: int = 1  # Total HP bonus (= sorcerer level, set by factory)

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

        # +hp_bonus to max HP
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


# =============================================================================
# ELEMENTAL AFFINITY CONDITION (L6 Draconic)
# =============================================================================

class ElementalAffinity(BaseCondition):
    """Draconic Bloodline L6: Resistance to ancestry damage type."""
    name: str = "Elemental Affinity"
    description: str = "Resistance to draconic ancestry damage type"
    damage_type: DamageType = DamageType.FIRE

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

        resist_mod = ResistanceModifier(
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            name="Elemental Affinity",
            value=ResistanceStatus.RESISTANCE,
            damage_type=self.damage_type,
        )
        mod_uuid = target.health.damage_reduction.self_static.add_resistance_modifier(resist_mod)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Elemental Affinity ({self.damage_type.value}) applied",
        )
        return [(target.health.damage_reduction.uuid, mod_uuid)], [], [], [], effect_event


# =============================================================================
# METAMAGIC ACTIVE CONDITION
# =============================================================================

class MetamagicActive(BaseCondition):
    """Applied when a metamagic action is used.

    Modifies spell templates via alt-field overrides.
    Auto-removes on next CAST_SPELL from this entity.
    """
    name: str = "MetamagicActive"
    description: str = "Metamagic is active — next spell cast will be modified"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    metamagic_type: str = "quickened"  # "quickened", "twinned", "distant"

    # Track modified template UUIDs for cleanup (exclude from serialization)
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

        # Apply overrides based on metamagic type
        if self.metamagic_type == "quickened":
            self._modified_uuids = apply_action_overrides(
                target,
                filter_fn=lambda a: isinstance(a, SpellAction) and any(
                    c.cost_type == "actions" for c in a.costs
                ),
                overrides={"alt_cost_type": "bonus_actions"},
            )
        elif self.metamagic_type == "twinned":
            # Per-template: set target override + SP cost = max(0, spell_level - 1)
            # Total SP = 1 (activation) + max(0, level-1) (at cast) = max(1, level)
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
            # Distant: RANGE spells → double range, REACH spells → 30ft range
            self._modified_uuids = []
            for template in target.registered_actions:
                if isinstance(template, SpellAction):
                    if template.spell_range.type == RangeType.RANGE:
                        template.alt_range = template.spell_range.normal * 2
                        self._modified_uuids.append(template.uuid)
                    elif template.spell_range.type == RangeType.REACH:
                        template.alt_range = 30
                        self._modified_uuids.append(template.uuid)

        # Handler: auto-remove on next CAST_SPELL from this entity
        handler = EventHandler(
            name="MetamagicAutoRemove",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[Trigger(
                name="CastSpell",
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=self.target_entity_uuid,
            )],
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
        """Auto-remove MetamagicActive after spell is cast."""
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


# =============================================================================
# METAMAGIC ACTIONS
# =============================================================================

class QuickenedSpell(BaseAction):
    """Quickened Spell: Cast a spell as a bonus action (2 SP)."""
    name: str = Field(default="Quickened Spell")
    description: str = "Next spell costs a bonus action instead of an action"
    target_type: TargetType = TargetType.SELF
    action_category: ActionCategory = ActionCategory.ABILITY
    costs: List[Cost] = Field(default_factory=lambda: [Cost(
        name="Quickened Spell",
        cost_type="actions",
        cost=0,
        resource_name="sorcery_points",
        resource_cost=2,
        evaluator=entity_action_economy_cost_evaluator,
        resource_evaluator=entity_resource_cost_evaluator,
    )])

    def pre_validate(self) -> bool:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False
        if "MetamagicActive" in entity.active_conditions:
            return False
        if not self.check_costs():
            return False
        return True

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
    """Twinned Spell: Target a second creature with a single-target spell (1 SP)."""
    name: str = Field(default="Twinned Spell")
    description: str = "Next single-target spell targets two creatures"
    target_type: TargetType = TargetType.SELF
    action_category: ActionCategory = ActionCategory.ABILITY
    costs: List[Cost] = Field(default_factory=lambda: [Cost(
        name="Twinned Spell",
        cost_type="actions",
        cost=0,
        resource_name="sorcery_points",
        resource_cost=1,
        evaluator=entity_action_economy_cost_evaluator,
        resource_evaluator=entity_resource_cost_evaluator,
    )])

    def pre_validate(self) -> bool:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False
        if "MetamagicActive" in entity.active_conditions:
            return False
        if not self.check_costs():
            return False
        return True

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
    """Distant Spell: Double the range of a spell (1 SP)."""
    name: str = Field(default="Distant Spell")
    description: str = "Next spell has double range"
    target_type: TargetType = TargetType.SELF
    action_category: ActionCategory = ActionCategory.ABILITY
    costs: List[Cost] = Field(default_factory=lambda: [Cost(
        name="Distant Spell",
        cost_type="actions",
        cost=0,
        resource_name="sorcery_points",
        resource_cost=1,
        evaluator=entity_action_economy_cost_evaluator,
        resource_evaluator=entity_resource_cost_evaluator,
    )])

    def pre_validate(self) -> bool:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False
        if "MetamagicActive" in entity.active_conditions:
            return False
        if not self.check_costs():
            return False
        return True

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


# Metamagic action lookup table
METAMAGIC_ACTIONS: Dict[str, type] = {
    "quickened": QuickenedSpell,
    "twinned": TwinnedSpell,
    "distant": DistantSpell,
}


# =============================================================================
# FONT OF MAGIC ACTIONS
# =============================================================================

# SP cost to create a spell slot (SRD table)
SP_TO_SLOT_COST: Dict[int, int] = {1: 2, 2: 3, 3: 5, 4: 6, 5: 7}


class ConvertSlotToSP(BaseAction):
    """Spend a spell slot to gain sorcery points equal to slot level.

    One action per slot level (L1-L5). slot_level field selects which.
    """
    name: str = Field(default="Convert Slot to SP")
    description: str = "Spend a spell slot to gain sorcery points"
    target_type: TargetType = TargetType.SELF
    action_category: ActionCategory = ActionCategory.ABILITY
    slot_level: int = Field(default=1, ge=1, le=5)
    costs: List[Cost] = Field(default_factory=list)

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

        # Grant SP equal to slot level
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
    """Spend sorcery points to create a spell slot (max L5).

    SP costs: L1=2, L2=3, L3=5, L4=6, L5=7
    """
    name: str = Field(default="Convert SP to Slot")
    description: str = "Spend sorcery points to create a spell slot"
    target_type: TargetType = TargetType.SELF
    action_category: ActionCategory = ActionCategory.ABILITY
    slot_level: int = Field(default=1, ge=1, le=5)
    costs: List[Cost] = Field(default_factory=list)

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

    def pre_validate(self) -> bool:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False
        # Check entity has spell slots at this level (base > 0)
        slot_value = entity.action_economy._get_spell_slot_value(self.slot_level)
        base_mod = slot_value.get_base_modifier()
        if not base_mod or base_mod.normalized_value <= 0:
            return False
        return self.check_costs()

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message=f"{SP_TO_SLOT_COST.get(self.slot_level, 2)}SP\u2192Slot L{self.slot_level} validated")

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        # Restore 1 spell slot by removing a cost modifier
        slot_cost_type_name: CostType = f"spell_slot_{self.slot_level}"  # type: ignore
        slot_value = entity.action_economy._get_spell_slot_value(self.slot_level)

        # Find the most recent cost modifier and remove it to "restore" a slot
        cost_modifiers = entity.action_economy.get_cost_modifiers(slot_cost_type_name)
        if cost_modifiers:
            # Remove the last cost modifier (restores 1 slot)
            slot_value.self_static.remove_value_modifier(cost_modifiers[-1].uuid)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{SP_TO_SLOT_COST.get(self.slot_level, 2)}SP\u2192Slot L{self.slot_level}: created slot",
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# SORCERY POINTS FEATURE (L2+)
# =============================================================================

class SorceryPointsFeature(BaseCondition):
    """Grants the sorcery points resource + registers metamagic & Font of Magic actions."""
    name: str = "Sorcery Points Feature"
    description: str = "Sorcery points for metamagic and Font of Magic"
    sorcery_points: int = 2  # = sorcerer level (set by factory)
    metamagic_choices: List[str] = Field(default_factory=list)  # e.g., ["quickened", "twinned"]

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

        from dnd.blocks.action_economy import RechargeType
        target.action_economy.add_resource(
            "sorcery_points", self.sorcery_points, RechargeType.LONG_REST
        )

        # Register metamagic actions
        for choice in self.metamagic_choices:
            action_cls = METAMAGIC_ACTIONS.get(choice)
            if action_cls:
                target.register_action(action_cls(
                    source_entity_uuid=target.uuid, template=True
                ))

        # Register Font of Magic actions (one per slot level 1-5)
        for slot_level in range(1, 6):
            # Only register if entity has base slots at this level
            slot_value = target.action_economy._get_spell_slot_value(slot_level)
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

            # Unregister metamagic actions
            metamagic_names = {
                "quickened": "Quickened Spell",
                "twinned": "Twinned Spell",
                "distant": "Distant Spell",
            }
            for choice in self.metamagic_choices:
                action_name = metamagic_names.get(choice)
                if action_name:
                    target.unregister_action(action_name)

            # Unregister Font of Magic actions
            for slot_level in range(1, 6):
                target.unregister_action(f"Slot\u2192SP L{slot_level}")
                sp_cost = SP_TO_SLOT_COST.get(slot_level, 2)
                target.unregister_action(f"{sp_cost}SP\u2192Slot L{slot_level}")

            # Remove MetamagicActive if present
            if "MetamagicActive" in target.active_conditions:
                target.remove_condition("MetamagicActive", parent_event=event)

        return super()._remove(event)
