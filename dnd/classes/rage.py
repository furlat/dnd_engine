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
from dnd.core.base_actions import (
    ActionOutcomeProfile, BaseAction, ActionEvent, Cost, TargetType, BaseCost, ActionCategory
)
from dnd.core.events import (
    Event, EventPhase, EventType,
    Trigger, EventHandler,
    WeaponSlot, DeathEvent,
)
from dnd.core.modifiers import (
    NumericalModifier, AdvantageModifier, AdvantageStatus,
    ContextualNumericalModifier,
    ResistanceModifier, ResistanceStatus, DamageType
)
from dnd.blocks.equipment import ArmorType, ArmorEquipEvent, Armor
from dnd.blocks.action_economy import RechargeType
from dnd.entity import Entity
from dnd.actions import (
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
    entity_resource_cost_evaluator,
    Attack, AttackEvent, build_weapon_attack_outcome_profile,
)
from pydantic import Field
from typing import Any, Optional, List, Tuple, cast
from uuid import UUID


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
    _ = target_entity_uuid, context

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

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Rage Damage",
        value=rage_damage
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

    if "Raging" not in entity.active_conditions:
        return None

    if "PersistentRage" in entity.active_conditions:
        return None

    has_attacked = "HasAttacked" in entity.active_conditions
    has_taken_damage = "HasTakenDamage" in entity.active_conditions

    if not has_attacked and not has_taken_damage:
        entity.remove_condition("Raging", parent_event=event)
        return event.model_copy(update={
            "modified": True,
            "status_message": f"{entity.name}'s rage ends (no attack or damage)"
        })

    return None


def rage_armor_equip_handler(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    End rage if heavy armor is equipped.

    Triggers on ARMOR_EQUIP at EXECUTION phase.
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
            return event.model_copy(update={
                "modified": True,
                "status_message": f"{entity.name}'s rage ends (equipped heavy armor)"
            })

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
                event_phase=EventPhase.EXECUTION
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

    if "Frenzied" in entity.active_conditions:
        entity.remove_condition("Frenzied", parent_event=event)
    elif "Raging" in entity.active_conditions:
        entity.remove_condition("Raging", parent_event=event)

    return event.model_copy(update={
        "modified": True,
        "status_message": f"{entity.name}'s rage ends (died)"
    })


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

        if "Mindless Rage" in target.active_conditions:
            for cond_name in ["Charmed", "Frightened"]:
                if cond_name in target.active_conditions:
                    target.remove_condition(cond_name)

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        athletics = target.skill_set.get_skill("athletics")
        str_adv_mod = AdvantageModifier(
            name="Raging",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = athletics.skill_bonus.self_static.add_advantage_modifier(str_adv_mod)
        outs.append((athletics.skill_bonus.uuid, mod_uuid))

        str_save = target.saving_throws.get_saving_throw("strength")
        str_save_adv = AdvantageModifier(
            name="Raging",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = str_save.bonus.self_static.add_advantage_modifier(str_save_adv)
        outs.append((str_save.bonus.uuid, mod_uuid))

        rage_dmg_mod = ContextualNumericalModifier(
            name="Rage Damage",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=rage_damage_check
        )
        mod_uuid = target.equipment.melee_damage_bonus.self_contextual.add_value_modifier(rage_dmg_mod)
        outs.append((target.equipment.melee_damage_bonus.uuid, mod_uuid))

        for damage_type in [DamageType.BLUDGEONING, DamageType.PIERCING, DamageType.SLASHING]:
            resist_mod = ResistanceModifier(
                name=f"Rage Resistance ({damage_type.value})",
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                value=ResistanceStatus.RESISTANCE,
                damage_type=damage_type
            )
            mod_uuid = target.health.damage_reduction.self_static.add_resistance_modifier(resist_mod)
            outs.append((target.health.damage_reduction.uuid, mod_uuid))

        maintenance_handler = create_rage_maintenance_handler(target.uuid)
        target.add_event_handler(maintenance_handler)
        handler_uuids.append(maintenance_handler.uuid)

        armor_handler = create_rage_armor_handler(target.uuid)
        target.add_event_handler(armor_handler)
        handler_uuids.append(armor_handler.uuid)

        death_handler = create_rage_death_handler(target.uuid)
        target.add_event_handler(death_handler)
        handler_uuids.append(death_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} enters a rage!"
        )

        return outs, handler_uuids, [], [], effect_event


class Rage(BaseAction):
    """Action that enters a rage as a bonus action.

    Attributes:
        name: Action name displayed for entering rage.
        description: Short rules-facing summary of the Rage action.
        target_type: Rage always targets the acting barbarian.
        rage_damage: Damage bonus copied into the applied Raging condition.
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

    def pre_validate(self) -> bool:
        """Check if rage can be activated (for action availability filtering)."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False

        if "Frenzy Feature" in entity.active_conditions:
            return False

        body_armor = entity.equipment.body_armor
        if body_armor and body_armor.type == ArmorType.HEAVY:
            return False

        if "Raging" in entity.active_conditions or "Frenzied" in entity.active_conditions:
            return False

        if not entity.action_economy.can_afford_resource("rage", 1):
            return False

        if not entity.action_economy.can_afford("bonus_actions", 1):
            return False

        return True

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

        raging = Raging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage
        )
        entity.add_condition(raging, parent_event=execution_event)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} enters a rage!"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply the costs (consume bonus action and rage resource)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


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

    def pre_validate(self) -> bool:
        """Check if End Rage can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False

        if "Raging" not in entity.active_conditions and "Frenzied" not in entity.active_conditions:
            return False

        if not entity.action_economy.can_afford("bonus_actions", 1):
            return False

        return True

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
            EventPhase.COMPLETION,
            status_message=f"{entity.name}'s rage ends voluntarily"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply the costs (consume bonus action)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


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
            template=True
        )
        target.register_action(frenzied_strike)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is frenzied!"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up FrenziedStrike action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.unregister_action("Frenzied Strike")

        return super()._remove(event)


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
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = source_entity.name if source_entity else None
        target_name = target_entity.name if target_entity else None

        weapon_name = None
        if source_entity:
            weapon = source_entity.equipment._get_weapon_by_slot(self.weapon_slot)
            weapon_name = weapon.name if weapon else "Unarmed"

        display_name = f"Frenzied Strike ({weapon_name})" if weapon_name else "Frenzied Strike"

        return AttackEvent(
            name=display_name,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name,
            weapon_name=weapon_name
        )

    def pre_validate(self) -> bool:
        """Check whether Frenzied Strike can currently execute against its target."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False

        weapon = entity.equipment._get_weapon_by_slot(self.weapon_slot)
        if weapon is None:
            return False

        return super().pre_validate()

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

        if self.target_entity_uuid not in entity.senses.entities:
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

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply bonus action cost."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class Frenzy(BaseAction):
    """Action that enters a Berserker frenzy as a bonus action.

    Attributes:
        name: Action name displayed for entering Berserker frenzy.
        description: Short rules-facing summary of the Frenzy action.
        target_type: Frenzy always targets the acting barbarian.
        rage_damage: Damage bonus copied into the applied Raging and Frenzied conditions.
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

    def pre_validate(self) -> bool:
        """Check if frenzy can be activated."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False

        body_armor = entity.equipment.body_armor
        if body_armor and body_armor.type == ArmorType.HEAVY:
            return False

        if "Raging" in entity.active_conditions or "Frenzied" in entity.active_conditions:
            return False

        if not entity.action_economy.can_afford_resource("rage", 1):
            return False

        if not entity.action_economy.can_afford("bonus_actions", 1):
            return False

        return True

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

        raging = Raging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage
        )
        entity.add_condition(raging, parent_event=execution_event)

        frenzied = Frenzied(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage,
            parent_condition=raging.uuid
        )
        entity.add_condition(frenzied, parent_event=execution_event)

        raging.sub_conditions.append(frenzied.uuid)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} enters a frenzy!"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


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
