"""
Barbarian Rage and Frenzy Systems

Contains all rage/frenzy related code:
- Rage maintenance handlers and processors
- Raging condition
- Rage and EndRage actions
- RageFeature condition
- Frenzy system (Berserker path)
"""

from dnd.core.base_conditions import BaseCondition
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.base_actions import (
    ActionOutcomeProfile, BaseAction, ActionEvent, Cost, TargetType, BaseCost, ActionCategory
)
from dnd.core.events import (
    Event, EventPhase, EventType,
    Trigger, EventHandler,
    DeathEvent, RangeType,
)
from dnd.core.equipment_types import ArmorType, WeaponSlot
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    NumericalModifier,
    AdvantageModifier,
    AdvantageStatus,
    ContextualNumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.blocks.equipment import ArmorEquipEvent, Armor
from dnd.blocks.action_economy import RechargeType
from dnd.entity import Entity
from dnd.actions import (
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
    entity_resource_cost_evaluator,
    Attack, AttackEvent, build_weapon_attack_outcome_profile,
    create_weapon_attack_declaration_event,
)
from pydantic import Field
from typing import Any, Optional, List, Tuple, cast
from uuid import UUID


def _child_binding(parent_binding, behavior_id: str, runtime_owner_uuid: UUID):
    """Derive one exact direct child fact from this family-local provider."""
    if parent_binding is None:
        return None
    return parent_binding.model_copy(update={
        "behavior_id": behavior_id,
        "provided_by_id": parent_binding.behavior_id,
        "runtime_owner_uuid": runtime_owner_uuid,
    })


def _owning_template(action: BaseAction, entity: Entity) -> BaseAction:
    """Resolve the exact Entity-owned template that produced an execution."""
    template_uuid = action.registered_template_uuid
    if template_uuid is None:
        raise RuntimeError("Rage-family execution has no registered template owner")
    template = next(
        (
            candidate
            for candidate in entity.registered_actions
            if candidate.uuid == template_uuid
        ),
        None,
    )
    if template is None:
        raise RuntimeError("Rage-family registered template owner is missing")
    return template


def _purge_mindless_rage_conditions(
    entity: Entity,
    parent_event: Event,
) -> bool:
    """Atomically remove exact Charm/Fear state after rage commits."""
    conditions = tuple(
        condition
        for condition_name in ("Charmed", "Frightened")
        for condition in (entity.active_conditions.get(condition_name),)
        if condition is not None
    )
    prepared = []
    visited: set[UUID] = set()
    for condition in conditions:
        canceled = BaseBlock._prepare_condition_removal_tree(
            condition,
            condition_owner=entity,
            expire=False,
            parent_event=parent_event,
            prepared=prepared,
            visited=visited,
        )
        if canceled is not None:
            BaseBlock._cancel_prepared_condition_removals(prepared, canceled)
            return False
    BaseBlock._commit_prepared_condition_removals(prepared)
    return True


def rage_damage_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual check for rage damage bonus.

    Returns the rage damage bonus only if:
    - Entity is raging (has Raging condition)
    - Entity is NOT wearing heavy armor (rage impeded)

    The rage damage value comes from the Raging condition.
    """
    _ = target_entity_uuid

    if (
        context is None
        or context.get("attack_ability") != "strength"
        or context.get("range_type") != RangeType.REACH.value
    ):
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    raging = entity.active_conditions.get("Raging")
    if not isinstance(raging, Raging):
        return None

    body_armor = entity.equipment.body_armor
    if body_armor and body_armor.type == ArmorType.HEAVY:
        return None

    rage_damage = raging.rage_damage

    return NumericalModifier(
        source_entity_uuid=source_entity_uuid,
        name="Rage Damage",
        value=rage_damage,
        use_register=False,
    )


def rage_maintenance_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    Check if rage should end due to inactivity.

    Triggers on TURN_START at EXECUTION phase (BEFORE conditions expire).

    This timing is critical: HasAttacked/HasTakenDamage have 1-round duration
    and expire at TURN_START after EXECUTION. By checking at TURN_START EXECUTION,
    we can see if the barbarian attacked or took damage since their last turn
    before those markers are removed.

    Rage ends if:
    - No HasAttacked AND no HasTakenDamage condition present
    - Entity does NOT have PersistentRage (L15+)

    Per SRD: "Your rage lasts for 1 minute... It ends early if... your turn ends
    and you haven't attacked a hostile creature since your last turn or taken
    damage since then."
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    raging = entity.active_conditions.get("Raging")
    if not isinstance(raging, Raging):
        return None

    if raging.persistent_rage:
        return None

    has_attacked = "HasAttacked" in entity.active_conditions
    has_taken_damage = "HasTakenDamage" in entity.active_conditions

    if not has_attacked and not has_taken_damage:
        entity.remove_condition("Raging", parent_event=event)
        return event.with_updates(
            status_message=f"{entity.name}'s rage ends (no attack or damage)",
        )

    return None


def rage_armor_equip_handler(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    End rage if heavy armor is equipped.

    Triggers on ARMOR_EQUIP at EFFECT phase after the gear transaction commits.
    If the armor being equipped is heavy armor, rage ends immediately.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if "Raging" not in entity.active_conditions:
        return None

    armor_event = event if isinstance(event, ArmorEquipEvent) else None
    if armor_event:
        armor = cast(Armor, BaseBlock.get(armor_event.item_uuid))
        if armor is not None and armor.type == ArmorType.HEAVY:
            entity.remove_condition("Raging", parent_event=event)
            return event.with_updates(
                status_message=(
                    f"{entity.name}'s rage ends (equipped heavy armor)"
                ),
            )

    return None


def create_rage_maintenance_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create handler that checks rage maintenance at turn start (before conditions expire)."""
    return EventHandler(
        name="Rage Maintenance",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=rage_maintenance_processor
    )


def create_rage_armor_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create handler that ends rage when heavy armor is equipped."""
    return EventHandler(
        name="Rage Armor Watch",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ARMOR_EQUIP,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=rage_armor_equip_handler
    )


def rage_death_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    End rage when entity dies.

    SRD: "Your rage ends early if you fall unconscious."
    Note: We use DEATH instead of UNCONSCIOUS since monsters die at 0 HP.

    Triggers on DEATH at EXECUTION phase (when entity dies).
    """
    if not isinstance(event, DeathEvent) or event.entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if "Raging" not in entity.active_conditions and "Frenzied" not in entity.active_conditions:
        return None

    # Frenzied is owned by Raging as a sub-condition.  Remove the parent so
    # BaseBlock performs the complete condition-tree cleanup; removing only
    # Frenzied would leave the dead entity with the Raging transforms active.
    if "Raging" in entity.active_conditions:
        entity.remove_condition("Raging", parent_event=event)
    elif "Frenzied" in entity.active_conditions:
        # Defensive recovery for malformed legacy state where Frenzied exists
        # without its owning Raging condition.
        entity.remove_condition("Frenzied", parent_event=event)

    return event.with_updates(
        status_message=f"{entity.name}'s rage ends (died)",
    )


def create_rage_death_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create handler that ends rage when entity dies."""
    return EventHandler(
        name="Rage Death End",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.DEATH,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=rage_death_processor
    )


class Raging(BaseCondition):
    """Active rage state applied by the Rage action.

    Attributes:
        name: Condition name used for active rage state lookup and cleanup.
        description: Short rules-facing summary of the active rage state.
        rage_damage: Damage bonus supplied by the active rage state to melee attacks.
        mindless_rage: Whether this rage purges charm and fear.
        persistent_rage: Whether inactivity can end this rage.
        owning_action_template_uuid: Exact action template that owns this root.
    """
    name: str = Field(
        default="Raging",
        description="Condition name used for active rage state lookup and cleanup.",
    )
    description: str = Field(
        default="In a primal rage - bonus damage, resistance, advantage on STR",
        description="Short rules-facing summary of the active rage state.",
    )
    rage_damage: int = Field(
        default=2,
        description="Damage bonus supplied by the active rage state to melee attacks.",
    )
    mindless_rage: bool = Field(
        default=False,
        description="Whether this active rage purges charm and fear.",
    )
    persistent_rage: bool = Field(
        default=False,
        description="Whether inactivity can end this active rage.",
    )
    owning_action_template_uuid: Optional[UUID] = Field(
        default=None,
        exclude=True,
        description="Exact Rage or Frenzy template that owns this root.",
    )

    def _record_modifier(self, value_uuid: UUID, modifier_uuid: UUID) -> None:
        """Retain one exact modifier immediately after owner admission."""
        self.modifers_uuids.setdefault(value_uuid, []).append(modifier_uuid)

    def _admit_handler(self, target: Entity, handler: EventHandler) -> None:
        """Retain one exact handler immediately after owner admission."""
        try:
            target.add_event_handler(handler)
        except BaseException:
            handler.remove_from_register()
            raise
        self.event_handlers_uuids.append(handler.uuid)

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

        athletics = target.skill_set.get_skill("athletics")
        str_adv_mod = AdvantageModifier(
            name="Raging",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        try:
            mod_uuid = athletics.skill_bonus.self_static.add_advantage_modifier(
                str_adv_mod,
            )
        except BaseException:
            str_adv_mod.remove_from_register()
            raise
        self._record_modifier(athletics.skill_bonus.uuid, mod_uuid)

        str_save = target.saving_throws.get_saving_throw("strength")
        str_save_adv = AdvantageModifier(
            name="Raging",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        try:
            mod_uuid = str_save.bonus.self_static.add_advantage_modifier(
                str_save_adv,
            )
        except BaseException:
            str_save_adv.remove_from_register()
            raise
        self._record_modifier(str_save.bonus.uuid, mod_uuid)

        rage_dmg_mod = ContextualNumericalModifier(
            name="Rage Damage",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=rage_damage_check
        )
        try:
            mod_uuid = (
                target.equipment.melee_damage_bonus.self_contextual
                .add_value_modifier(rage_dmg_mod)
            )
        except BaseException:
            rage_dmg_mod.remove_from_register()
            raise
        self._record_modifier(target.equipment.melee_damage_bonus.uuid, mod_uuid)

        for damage_type in [DamageType.BLUDGEONING, DamageType.PIERCING, DamageType.SLASHING]:
            resist_mod = ResistanceModifier(
                name=f"Rage Resistance ({damage_type.value})",
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                value=ResistanceStatus.RESISTANCE,
                damage_type=damage_type
            )
            try:
                mod_uuid = (
                    target.health.damage_reduction.self_static
                    .add_resistance_modifier(resist_mod)
                )
            except BaseException:
                resist_mod.remove_from_register()
                raise
            self._record_modifier(target.health.damage_reduction.uuid, mod_uuid)

        maintenance_handler = create_rage_maintenance_handler(target.uuid)
        maintenance_handler.behavior_binding = self.behavior_binding
        self._admit_handler(target, maintenance_handler)

        armor_handler = create_rage_armor_handler(target.uuid)
        armor_handler.behavior_binding = self.behavior_binding
        self._admit_handler(target, armor_handler)

        death_handler = create_rage_death_handler(target.uuid)
        death_handler.behavior_binding = self.behavior_binding
        self._admit_handler(target, death_handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} enters a rage!"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Release the exact action-template root edge after state cleanup."""
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if target is not None and self.owning_action_template_uuid is not None:
            template = next(
                (
                    candidate
                    for candidate in target.registered_actions
                    if candidate.uuid == self.owning_action_template_uuid
                ),
                None,
            )
            if template is not None:
                template.active_raging_condition_uuid = None
        return super()._remove(event)

    def remove_condition_modifiers(self) -> bool:
        """Detach and unregister this Raging instance's exact modifiers."""
        owned = tuple(
            modifier
            for modifier_uuids in self.modifers_uuids.values()
            for modifier_uuid in modifier_uuids
            for modifier in (BaseObject.get(modifier_uuid),)
            if modifier is not None
        )
        removed = super().remove_condition_modifiers()
        if removed:
            for modifier in owned:
                modifier.remove_from_register()
        return removed

    def remove_event_handlers(self) -> bool:
        """Detach and unregister this Raging instance's exact handlers."""
        owned = tuple(
            handler
            for handler_uuid in self.event_handlers_uuids
            for handler in (BaseObject.get(handler_uuid),)
            if handler is not None
        )
        removed = super().remove_event_handlers()
        if removed:
            for handler in owned:
                handler.remove_from_register()
        return removed


class Rage(BaseAction):
    """Action that enters a rage as a bonus action.

    Attributes:
        name: Action name displayed for entering rage.
        description: Short rules-facing summary of the Rage action.
        target_type: Rage always targets the acting barbarian.
        rage_damage: Damage bonus copied into the applied Raging condition.
        mindless_rage: Whether the resulting rage purges charm and fear.
        persistent_rage: Whether inactivity can end the resulting rage.
        active_raging_condition_uuid: Exact active root owned by this template.
        costs: Bonus-action and rage-resource costs rebuilt after model initialization.
    """
    name: str = Field(default="Rage", description="Action name displayed for entering rage.")
    description: str = Field(
        default="Enter a primal rage",
        description="Short rules-facing summary of the Rage action.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Rage always targets the acting barbarian.",
    )
    rage_damage: int = Field(
        default=2,
        description="Damage bonus copied into the applied Raging condition.",
    )
    mindless_rage: bool = Field(
        default=False,
        description="Whether the resulting active rage purges charm and fear.",
    )
    persistent_rage: bool = Field(
        default=False,
        description="Whether inactivity can end the resulting active rage.",
    )
    active_raging_condition_uuid: Optional[UUID] = Field(
        default=None,
        exclude=True,
        description="Exact active Raging root produced by this template.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Bonus-action and rage-resource costs rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Rage",
                cost_type="bonus_actions",
                cost=1,
                resource_name="rage",
                resource_cost=1,
                evaluator=entity_action_economy_cost_evaluator,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        """Create the declaration event for Rage."""
        entity = Entity.get(self.source_entity_uuid)
        source_name = entity.name if entity else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name
        )

    def validate_requirements_for_discovery(self) -> bool:
        """Check non-cost prerequisites for exposing Rage as executable."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False

        if "Frenzied" in entity.active_conditions:
            return False

        return super().validate_requirements_for_discovery()

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate Rage can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return declaration_event.cancel(status_message="Entity not found")

        body_armor = entity.equipment.body_armor
        if body_armor and body_armor.type == ArmorType.HEAVY:
            return declaration_event.cancel(status_message="Cannot rage in heavy armor")

        if "Raging" in entity.active_conditions:
            return declaration_event.cancel(status_message="Already raging")

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Rage ready"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply Rage - enter the rage state."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")

        template = _owning_template(self, entity)
        raging = Raging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage,
            mindless_rage=self.mindless_rage,
            persistent_rage=self.persistent_rage,
            owning_action_template_uuid=template.uuid,
            behavior_binding=_child_binding(
                self.behavior_binding,
                "class_feature.barbarian.raging",
                entity.uuid,
            ),
        )
        applied = entity.add_condition(raging, parent_event=execution_event)
        if applied is None or applied.canceled:
            return applied
        template.active_raging_condition_uuid = raging.uuid
        purge_succeeded = (
            not raging.mindless_rage
            or _purge_mindless_rage_conditions(entity, applied)
        )

        return execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=(
                f"{entity.name} enters a rage!"
                if purge_succeeded
                else f"{entity.name} enters a rage; Mindless Rage purge was blocked"
            ),
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply the costs (consume bonus action and rage resource)."""
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


class EndRage(BaseAction):
    """Action that voluntarily ends the actor's active rage.

    Attributes:
        name: Action name displayed for voluntary rage cleanup.
        description: Short rules-facing summary of the voluntary rage-ending action.
        target_type: End Rage always targets the acting barbarian.
        costs: Bonus-action cost rebuilt after model initialization.
    """
    name: str = Field(default="End Rage", description="Action name displayed for voluntary rage cleanup.")
    description: str = Field(
        default="End your rage voluntarily",
        description="Short rules-facing summary of the voluntary rage-ending action.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="End Rage always targets the acting barbarian.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Bonus-action cost rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="End Rage",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        """Create the declaration event for End Rage."""
        entity = Entity.get(self.source_entity_uuid)
        source_name = entity.name if entity else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate End Rage can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return declaration_event.cancel(status_message="Entity not found")

        if "Raging" not in entity.active_conditions and "Frenzied" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Not currently raging")

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="End Rage ready"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply End Rage - remove rage state."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")

        if "Raging" in entity.active_conditions:
            entity.remove_condition("Raging", parent_event=execution_event)

        return execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{entity.name}'s rage ends voluntarily"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply the costs (consume bonus action)."""
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


class RageFeature(BaseCondition):
    """Barbarian feature that grants rage resources and actions.

    Attributes:
        name: Feature condition name for Barbarian rage.
        description: Short rules-facing summary of the Rage feature.
        rage_uses: Maximum rage resource uses granted by the feature.
        rage_damage: Rage damage bonus wired into registered Rage actions.
    """
    name: str = Field(default="Rage Feature", description="Feature condition name for Barbarian rage.")
    description: str = Field(
        default="Can enter a primal rage as a bonus action",
        description="Short rules-facing summary of the Rage feature.",
    )
    rage_uses: int = Field(
        default=2,
        description="Maximum rage resource uses granted by the feature.",
    )
    rage_damage: int = Field(
        default=2,
        description="Rage damage bonus wired into registered Rage actions.",
    )

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

        recharge = RechargeType.LONG_REST if self.rage_uses < 999 else RechargeType.NEVER
        target.action_economy.add_resource(
            name="rage",
            maximum=self.rage_uses,
            recharge_type=recharge
        )

        rage_action = Rage(
            source_entity_uuid=target.uuid,
            rage_damage=self.rage_damage,
            template=True
        )
        target.register_action(rage_action)

        end_rage_action = EndRage(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(end_rage_action)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Rage ({self.rage_uses} uses, +{self.rage_damage} damage) to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up resource and action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("rage")
            target.unregister_action("Rage")
            target.unregister_action("End Rage")

            if "Raging" in target.active_conditions:
                target.remove_condition("Raging", parent_event=event)

        return super()._remove(event)

class Frenzied(BaseCondition):
    """Active Berserker frenzy state applied by the Frenzy action.

    Attributes:
        name: Condition name used for active Berserker frenzy state lookup and cleanup.
        description: Short rules-facing summary of the active frenzy state.
        rage_damage: Damage bonus retained for the frenzied rage state.
        frenzied_strike_action_uuid: Exact action owned by this condition.
    """
    name: str = Field(
        default="Frenzied",
        description="Condition name used for active Berserker frenzy state lookup and cleanup.",
    )
    description: str = Field(
        default="In a frenzied rage - can make bonus action melee attacks",
        description="Short rules-facing summary of the active frenzy state.",
    )
    rage_damage: int = Field(
        default=2,
        description="Damage bonus retained for the frenzied rage state.",
    )
    frenzied_strike_action_uuid: Optional[UUID] = Field(
        default=None,
        exclude=True,
        description="Exact Frenzied Strike action owned by this condition.",
    )

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

        frenzied_strike = FrenziedStrike(
            source_entity_uuid=target.uuid,
            template=True,
            semantic_key="action.class.barbarian.frenzied_strike",
            behavior_binding=_child_binding(
                self.behavior_binding,
                "action.class.barbarian.frenzied_strike",
                target.uuid,
            ),
        )
        try:
            target.register_action(frenzied_strike)
        except BaseException:
            frenzied_strike.remove_from_register()
            raise
        self.frenzied_strike_action_uuid = frenzied_strike.uuid

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is frenzied!"
        )

        return [], [], [], [], effect_event

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release exact Frenzied state that may exist before admission."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None and self.frenzied_strike_action_uuid is not None:
            if not target.unregister_action_by_uuid(
                self.frenzied_strike_action_uuid,
            ):
                raise RuntimeError("Frenzied-owned strike action is missing")
            self.frenzied_strike_action_uuid = None
        super()._release_owned_runtime_state(parent_event=parent_event)


def _release_failed_frenzied_graph(
    entity: Entity,
    raging: Raging,
    parent_event: Event,
) -> None:
    """Release the exact provisional graph after Frenzied admission fails."""
    if not entity.remove_condition_by_uuid(
        raging.uuid,
        parent_event=parent_event,
    ):
        raise RuntimeError(
            "Frenzy admission failed and its Raging root could not be released",
        )


class FrenziedStrike(BaseAction):
    """Bonus-action melee attack available during Berserker frenzy.

    Attributes:
        name: Action name displayed for the Berserker bonus-action attack.
        description: Short rules-facing summary of Frenzied Strike.
        target_type: Frenzied Strike targets a visible entity in weapon reach.
        weapon_slot: Weapon slot used to resolve the bonus-action melee attack.
        action_category: Marks Frenzied Strike as an attack action for action discovery and reactions.
        costs: Bonus-action cost rebuilt after model initialization.
    """
    name: str = Field(
        default="Frenzied Strike",
        description="Action name displayed for the Berserker bonus-action attack.",
    )
    description: str = Field(
        default="Make a bonus action melee attack while frenzied",
        description="Short rules-facing summary of Frenzied Strike.",
    )
    target_type: TargetType = Field(
        default=TargetType.ENTITY,
        description="Frenzied Strike targets a visible entity in weapon reach.",
    )
    weapon_slot: WeaponSlot = Field(
        default=WeaponSlot.MELEE_MAIN,
        description="Weapon slot used to resolve the bonus-action melee attack.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ATTACK,
        description="Marks Frenzied Strike as an attack action for action discovery and reactions.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Bonus-action cost rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Frenzied Strike",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )
        ]

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return the same actor-baseline weapon profile as a normal attack."""
        return build_weapon_attack_outcome_profile(actor, self.weapon_slot)

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for frenzied strike."""
        return create_weapon_attack_declaration_event(
            action_name="Frenzied Strike",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=self.costs,
            parent_event=parent_event,
            use_register=use_register,
            append_weapon_to_name=True,
        )

    def validate_requirements_for_discovery(self) -> bool:
        """Check non-cost Frenzied Strike requirements for discovery."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False

        weapon = entity.equipment._get_weapon_by_slot(self.weapon_slot)
        if weapon is None:
            return False

        return super().validate_requirements_for_discovery()

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        """Validate the frenzied strike."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if "Frenzied" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Must be in a frenzy")

        if not self.target_entity_uuid:
            return declaration_event.cancel(status_message="No target specified")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        contact = entity.senses.entities.get(self.target_entity_uuid)
        if contact is None or not contact.visual:
            return declaration_event.cancel(status_message="Target not visible")

        attack_event = cast(AttackEvent, declaration_event)
        range_validated = Attack.validate_range(attack_event, self.source_entity_uuid)
        if range_validated is None or range_validated.canceled:
            return range_validated

        return range_validated.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Frenzied Strike validated"
        )

    def _apply(self, execution_event: Event) -> Optional[Event]:
        """Execute the frenzied strike attack."""
        attack_event = cast(AttackEvent, execution_event)
        return Attack.attack_consequences(attack_event, self.source_entity_uuid)

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply bonus action cost."""
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


class Frenzy(BaseAction):
    """Action that enters a Berserker frenzy as a bonus action.

    Attributes:
        name: Action name displayed for entering Berserker frenzy.
        description: Short rules-facing summary of the Frenzy action.
        target_type: Frenzy always targets the acting barbarian.
        rage_damage: Damage bonus copied into the applied Raging and Frenzied conditions.
        mindless_rage: Whether the resulting frenzy purges charm and fear.
        persistent_rage: Whether inactivity can end the resulting frenzy.
        active_raging_condition_uuid: Exact active root owned by this template.
        costs: Bonus-action and rage-resource costs rebuilt after model initialization.
    """
    name: str = Field(default="Frenzy", description="Action name displayed for entering Berserker frenzy.")
    description: str = Field(
        default="Enter a frenzied rage",
        description="Short rules-facing summary of the Frenzy action.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Frenzy always targets the acting barbarian.",
    )
    rage_damage: int = Field(
        default=2,
        description="Damage bonus copied into the applied Raging and Frenzied conditions.",
    )
    mindless_rage: bool = Field(
        default=False,
        description="Whether the resulting active rage purges charm and fear.",
    )
    persistent_rage: bool = Field(
        default=False,
        description="Whether inactivity can end the resulting active rage.",
    )
    active_raging_condition_uuid: Optional[UUID] = Field(
        default=None,
        exclude=True,
        description="Exact active Raging root produced by this template.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Bonus-action and rage-resource costs rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Frenzy",
                cost_type="bonus_actions",
                cost=1,
                resource_name="rage",
                resource_cost=1,
                evaluator=entity_action_economy_cost_evaluator,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        """Create the declaration event for Frenzy."""
        entity = Entity.get(self.source_entity_uuid)
        source_name = entity.name if entity else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        body_armor = entity.equipment.body_armor
        if body_armor and body_armor.type == ArmorType.HEAVY:
            return declaration_event.cancel(status_message="Cannot frenzy in heavy armor")

        if "Raging" in entity.active_conditions or "Frenzied" in entity.active_conditions:
            return declaration_event.cancel(status_message="Already raging")

        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")

        template = _owning_template(self, entity)
        raging = Raging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage,
            mindless_rage=self.mindless_rage,
            persistent_rage=self.persistent_rage,
            owning_action_template_uuid=template.uuid,
            behavior_binding=_child_binding(
                self.behavior_binding,
                "class_feature.barbarian.raging",
                entity.uuid,
            ),
        )
        raging_applied = entity.add_condition(raging, parent_event=execution_event)
        if raging_applied is None or raging_applied.canceled:
            return raging_applied

        frenzied = Frenzied(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage,
            parent_condition=raging.uuid,
            behavior_binding=_child_binding(
                raging.behavior_binding,
                "class_feature.barbarian.frenzied",
                entity.uuid,
            ),
        )
        try:
            frenzied_applied = entity.add_condition(
                frenzied,
                parent_event=execution_event,
            )
        except BaseException:
            _release_failed_frenzied_graph(
                entity,
                raging,
                parent_event=execution_event,
            )
            raise
        if frenzied_applied is None or frenzied_applied.canceled:
            _release_failed_frenzied_graph(
                entity,
                raging,
                parent_event=frenzied_applied or execution_event,
            )
            return frenzied_applied

        raging.sub_conditions.append(frenzied.uuid)
        template.active_raging_condition_uuid = raging.uuid
        purge_succeeded = (
            not raging.mindless_rage
            or _purge_mindless_rage_conditions(entity, raging_applied)
        )

        return execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=(
                f"{entity.name} enters a frenzy!"
                if purge_succeeded
                else f"{entity.name} enters a frenzy; Mindless Rage purge was blocked"
            ),
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


class FrenzyFeature(BaseCondition):
    """Berserker feature that grants the Frenzy action.

    Attributes:
        name: Feature condition name for Berserker Frenzy.
        description: Short rules-facing summary of the Frenzy feature.
        rage_damage: Rage damage bonus wired into registered Frenzy actions.
    """
    name: str = Field(default="Frenzy Feature", description="Feature condition name for Berserker Frenzy.")
    description: str = Field(
        default="Can enter a frenzied rage for bonus action attacks",
        description="Short rules-facing summary of the Frenzy feature.",
    )
    rage_damage: int = Field(
        default=2,
        description="Rage damage bonus wired into registered Frenzy actions.",
    )

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

        frenzy_action = Frenzy(
            source_entity_uuid=target.uuid,
            rage_damage=self.rage_damage,
            template=True
        )
        target.register_action(frenzy_action)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Frenzy to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up Frenzy action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.unregister_action("Frenzy")

            if "Frenzied" in target.active_conditions:
                target.remove_condition("Frenzied", parent_event=event)

        return super()._remove(event)
