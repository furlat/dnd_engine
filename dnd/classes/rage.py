"""
Barbarian Rage and Frenzy Systems

Contains all rage/frenzy related code:
- Rage maintenance handlers and processors
- Raging condition
- Rage and EndRage actions
- Frenzy system (Berserker path)

Permanent Rage/Frenzy ownership is installed by the character composer.
"""

from dnd.core.base_conditions import BaseCondition
from dnd.core.base_block import BaseBlock
from dnd.core.base_actions import (
    ActionOutcomeProfile,
    BaseAction,
    Cost,
    TargetType,
    ActionCategory,
)
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventType,
    Trigger,
    EventHandler,
)
from dnd.core.events.encounter_events import (
    DeathEvent,
)
from dnd.core.events.resolution_events import (
    RangeType,
)
from dnd.types.equipment import ArmorType, WeaponSlot
from dnd.types.damage import DamageType
from dnd.types.abilities import AbilityName, SkillName
from dnd.core.modifiers import (
    NumericalModifier,
    AdvantageModifier,
    ContextualNumericalModifier,
    ResistanceModifier,
)
from dnd.types.rolls import AdvantageStatus
from dnd.types.damage import ResistanceStatus
from dnd.core.events.item_events import (
    ArmorEquipEvent,
)
from dnd.blocks.equipment import (
    Armor,
)
from dnd.entities.entity import Entity
from dnd.actions.standard import (
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
    Attack,
    AttackEvent,
    build_weapon_attack_outcome_profile,
    create_weapon_attack_declaration_event,
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

        if self.mindless_rage:
            for cond_name in ["Charmed", "Frightened"]:
                if cond_name in target.active_conditions:
                    target.remove_condition(cond_name)

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        athletics = target.skill_set.get_skill(SkillName.ATHLETICS)
        str_adv_mod = AdvantageModifier(
            name="Raging",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = athletics.skill_bonus.self_static.add_advantage_modifier(str_adv_mod)
        outs.append((athletics.skill_bonus.uuid, mod_uuid))

        str_save = target.saving_throws.get_saving_throw(AbilityName.STRENGTH)
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
        mindless_rage: Whether the resulting rage purges charm and fear.
        persistent_rage: Whether inactivity can end the resulting rage.
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

        raging = Raging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage,
            mindless_rage=self.mindless_rage,
            persistent_rage=self.persistent_rage,
        )
        entity.add_condition(raging, parent_event=execution_event)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} enters a rage!"
        )

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
        target.register_condition_action(self, frenzied_strike)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is frenzied!"
        )

        return [], [], [], [], effect_event

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

    def get_discovery_weapon_slot(self) -> Optional[WeaponSlot]:
        """Return the equipped slot used by this frenzied strike."""
        return self.weapon_slot

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

class Frenzy(BaseAction):
    """Action that enters a Berserker frenzy as a bonus action.

    Attributes:
        name: Action name displayed for entering Berserker frenzy.
        description: Short rules-facing summary of the Frenzy action.
        target_type: Frenzy always targets the acting barbarian.
        rage_damage: Damage bonus copied into the applied Raging and Frenzied conditions.
        mindless_rage: Whether the resulting frenzy purges charm and fear.
        persistent_rage: Whether inactivity can end the resulting frenzy.
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
            rage_damage=self.rage_damage,
            mindless_rage=self.mindless_rage,
            persistent_rage=self.persistent_rage,
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
