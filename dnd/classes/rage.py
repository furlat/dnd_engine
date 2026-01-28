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
from dnd.core.base_actions import (
    BaseAction, ActionEvent, Cost, TargetType, BaseCost
)
from dnd.core.events import (
    Event, EventPhase, EventType,
    Trigger, EventHandler,
    WeaponSlot,
)
from dnd.core.modifiers import (
    NumericalModifier, AdvantageModifier, AdvantageStatus,
    ContextualNumericalModifier,
    ResistanceModifier, ResistanceStatus, DamageType
)
from dnd.blocks.equipment import ArmorType, ArmorEquipEvent
from dnd.blocks.action_economy import RechargeType
from dnd.entity import Entity
from dnd.actions import (
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
    Attack, AttackEvent,
)
from typing import Optional, List, Tuple, cast
from uuid import UUID


# =============================================================================
# RAGE SYSTEM: Contextual Modifier Functions
# =============================================================================
# Note: Rage maintenance now uses generic HasAttacked and HasTakenDamage
# conditions from dnd/conditions.py instead of the Barbarian-specific KeepRage.
# This aligns with the SRD rule: "if you haven't attacked a hostile creature
# since your last turn or taken damage since then"

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
    _ = target_entity_uuid, context  # Suppress unused warnings

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Must be raging
    raging = entity.active_conditions.get("Raging")
    if not raging:
        return None

    # No bonus if wearing heavy armor (Rage Impeded per BG3)
    body_armor = entity.equipment.body_armor
    if body_armor and body_armor.type == ArmorType.HEAVY:
        return None

    # Get rage damage from the Raging condition
    rage_damage = getattr(raging, 'rage_damage', 2)

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Rage Damage",
        value=rage_damage
    )


# =============================================================================
# RAGE SYSTEM: Event Handler Processors
# =============================================================================

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
    # Only on OUR turn start
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Must be raging
    if "Raging" not in entity.active_conditions:
        return None

    # Persistent Rage (L15+) skips this check
    if "PersistentRage" in entity.active_conditions:
        return None

    # Check for attack OR damage this turn (using global combat state conditions)
    has_attacked = "HasAttacked" in entity.active_conditions
    has_taken_damage = "HasTakenDamage" in entity.active_conditions

    if not has_attacked and not has_taken_damage:
        # No attack or damage this turn - rage ends
        entity.remove_condition("Raging")
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
    # Only care about our own equipment changes
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Must be raging
    if "Raging" not in entity.active_conditions:
        return None

    # Check if the equipped armor is heavy
    # Cast to ArmorEquipEvent to access armor field
    armor_event = event if isinstance(event, ArmorEquipEvent) else None
    if armor_event and armor_event.armor is not None:
        if armor_event.armor.type == ArmorType.HEAVY:
            entity.remove_condition("Raging")
            return event.model_copy(update={
                "modified": True,
                "status_message": f"{entity.name}'s rage ends (equipped heavy armor)"
            })

    return None


# =============================================================================
# RAGE SYSTEM: Handler Factory Functions
# =============================================================================
# Note: Attack and damage tracking is now handled by global HasAttacked and
# HasTakenDamage handlers registered in setup_standard_actions(). We only
# need the maintenance handler (and armor/unconscious handlers) here.

def create_rage_maintenance_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create handler that checks rage maintenance at turn start (before conditions expire)."""
    return EventHandler(
        name="Rage Maintenance",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EXECUTION  # Fires BEFORE conditions expire in on_turn_start()
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


def rage_unconscious_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    End rage when falling unconscious.

    SRD: "Your rage ends early if you fall unconscious."

    Triggers on UNCONSCIOUS at EXECUTION phase (when HP drops to 0).
    """
    # Only when WE go unconscious
    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Must be raging
    if "Raging" not in entity.active_conditions and "Frenzied" not in entity.active_conditions:
        return None

    # End rage - remove Frenzied first if present (cascades to Raging)
    if "Frenzied" in entity.active_conditions:
        entity.remove_condition("Frenzied")
    elif "Raging" in entity.active_conditions:
        entity.remove_condition("Raging")

    return event.model_copy(update={
        "modified": True,
        "status_message": f"{entity.name}'s rage ends (fell unconscious)"
    })


def create_rage_unconscious_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create handler that ends rage when falling unconscious."""
    return EventHandler(
        name="Rage Unconscious End",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.UNCONSCIOUS,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=rage_unconscious_processor
    )


# =============================================================================
# RAGE SYSTEM: Raging Condition
# =============================================================================

class Raging(BaseCondition):
    """
    Active rage state - applied when Rage action is used.

    While raging, the barbarian gains:
    - Advantage on STR checks and saves
    - Rage damage bonus to melee attacks (if not in heavy armor)
    - Resistance to bludgeoning/piercing/slashing damage (if not in heavy armor)

    The condition also registers handlers to track:
    - Turn end (to check if rage should end based on HasAttacked/HasTakenDamage)
    - Turn end (to check if rage should end)

    Rage ends if:
    - Barbarian ends turn without attacking or taking damage (unless PersistentRage)
    - Barbarian falls unconscious
    - Barbarian chooses to end it (not implemented yet)
    """
    name: str = "Raging"
    description: str = "In a primal rage - bonus damage, resistance, advantage on STR"
    rage_damage: int = 2  # +2 at L1-8, +3 at L9-15, +4 at L16+

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        Optional[Event]           # completion event
    ]:
        if not self.target_entity_uuid:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        # Mindless Rage (L6+): If charmed or frightened when entering rage,
        # the effect is suspended (removed, BG3-style)
        if "Mindless Rage" in target.active_conditions:
            for cond_name in ["Charmed", "Frightened"]:
                if cond_name in target.active_conditions:
                    target.remove_condition(cond_name)

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # 1. Advantage on STR checks (Athletics skill)
        athletics = target.skill_set.get_skill("athletics")
        str_adv_mod = AdvantageModifier(
            name="Raging",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = athletics.skill_bonus.self_static.add_advantage_modifier(str_adv_mod)
        outs.append((athletics.skill_bonus.uuid, mod_uuid))

        # 2. Advantage on STR saves
        str_save = target.saving_throws.get_saving_throw("strength")
        str_save_adv = AdvantageModifier(
            name="Raging",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = str_save.bonus.self_static.add_advantage_modifier(str_save_adv)
        outs.append((str_save.bonus.uuid, mod_uuid))

        # 3. +rage_damage to melee attacks (contextual - checks heavy armor)
        rage_dmg_mod = ContextualNumericalModifier(
            name="Rage Damage",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=rage_damage_check
        )
        mod_uuid = target.equipment.melee_damage_bonus.self_contextual.add_value_modifier(rage_dmg_mod)
        outs.append((target.equipment.melee_damage_bonus.uuid, mod_uuid))

        # 4. Resistance to bludgeoning/piercing/slashing
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

        # 5. Register handlers for rage maintenance
        # Note: Attack and damage tracking is now handled globally by
        # HasAttacked and HasTakenDamage conditions (registered in setup_standard_actions)

        # Handler A: Check rage maintenance at turn end
        maintenance_handler = create_rage_maintenance_handler(target.uuid)
        target.add_event_handler(maintenance_handler)
        handler_uuids.append(maintenance_handler.uuid)

        # Handler D: End rage if heavy armor is equipped
        armor_handler = create_rage_armor_handler(target.uuid)
        target.add_event_handler(armor_handler)
        handler_uuids.append(armor_handler.uuid)

        # Handler E: End rage if falling unconscious (SRD)
        unconscious_handler = create_rage_unconscious_handler(target.uuid)
        target.add_event_handler(unconscious_handler)
        handler_uuids.append(unconscious_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} enters a rage!"
        )

        return outs, handler_uuids, [], effect_event


# =============================================================================
# RAGE SYSTEM: Rage Action
# =============================================================================

class Rage(BaseAction):
    """
    Enter a rage as a bonus action.

    Prerequisites:
    - Not already raging
    - Not wearing heavy armor (per BG3 - prevents activation)
    - Have rage resource available

    On activation:
    - Applies Raging condition (which registers maintenance handlers)
    - Consumes 1 rage resource
    """
    name: str = "Rage"
    description: str = "Enter a primal rage"
    target_type: TargetType = TargetType.SELF
    rage_damage: int = 2  # Set by RageFeature based on level

    costs: List[Cost] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.costs = [
            Cost(
                name="Rage",
                cost_type="bonus_actions",
                cost=1,
                resource_name="rage",
                resource_cost=1,
                evaluator=entity_action_economy_cost_evaluator
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

        # If Frenzy is available, don't show Rage (Frenzy is strictly better)
        if "Frenzy Feature" in entity.active_conditions:
            return False

        # Cannot rage in heavy armor (per BG3)
        body_armor = entity.equipment.body_armor
        if body_armor and body_armor.type == ArmorType.HEAVY:
            return False

        # Cannot already be raging/frenzied
        if "Raging" in entity.active_conditions or "Frenzied" in entity.active_conditions:
            return False

        # Check rage resource
        if not entity.action_economy.can_afford_resource("rage", 1):
            return False

        # Check bonus action
        if not entity.action_economy.can_afford("bonus_actions", 1):
            return False

        return True

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate Rage can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return declaration_event.cancel(status_message="Entity not found")

        # Cannot rage in heavy armor (per BG3)
        body_armor = entity.equipment.body_armor
        if body_armor and body_armor.type == ArmorType.HEAVY:
            return declaration_event.cancel(status_message="Cannot rage in heavy armor")

        # Already raging?
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

        # Apply Raging condition
        raging = Raging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage
        )
        entity.add_condition(raging)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} enters a rage!"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply the costs (consume bonus action and rage resource)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# RAGE SYSTEM: End Rage Action
# =============================================================================

class EndRage(BaseAction):
    """
    End your rage voluntarily as a bonus action.

    SRD: "You can also end your rage on your turn as a bonus action."

    This removes the Frenzied condition first (if present), which cascades
    to remove Raging. Otherwise, removes Raging directly.
    """
    name: str = "End Rage"
    description: str = "End your rage voluntarily"
    target_type: TargetType = TargetType.SELF

    costs: List[Cost] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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

        # Must be raging or frenzied
        if "Raging" not in entity.active_conditions and "Frenzied" not in entity.active_conditions:
            return False

        # Must have bonus action available
        if not entity.action_economy.can_afford("bonus_actions", 1):
            return False

        return True

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate End Rage can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return declaration_event.cancel(status_message="Entity not found")

        # Must be raging or frenzied
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

        # Remove Raging - this cascades to remove Frenzied (sub-condition)
        if "Raging" in entity.active_conditions:
            entity.remove_condition("Raging")

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name}'s rage ends voluntarily"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply the costs (consume bonus action)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# RAGE SYSTEM: Rage Feature (grants resource + action)
# =============================================================================

class RageFeature(BaseCondition):
    """
    Barbarian Level 1 Feature: Rage

    In battle, you fight with primal ferocity. On your turn, you can enter a rage
    as a bonus action.

    Rage uses scale with level:
    - Level 1-2: 2 uses
    - Level 3-5: 3 uses
    - Level 6-11: 4 uses
    - Level 12-16: 5 uses
    - Level 17-19: 6 uses
    - Level 20: Unlimited

    Rage damage scales with level:
    - Level 1-8: +2
    - Level 9-15: +3
    - Level 16+: +4

    This condition grants the 'rage' resource and registers the Rage action.
    """
    name: str = "Rage Feature"
    description: str = "Can enter a primal rage as a bonus action"
    rage_uses: int = 2  # Number of rage uses per long rest
    rage_damage: int = 2  # Rage damage bonus

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        Optional[Event]           # completion event
    ]:
        if not self.target_entity_uuid:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        # Add rage resource (long rest recharge, or unlimited at L20)
        # For unlimited, we use a very high number
        recharge = RechargeType.LONG_REST if self.rage_uses < 999 else RechargeType.NEVER
        target.action_economy.add_resource(
            name="rage",
            maximum=self.rage_uses,
            recharge_type=recharge
        )

        # Register Rage action template
        rage_action = Rage(
            source_entity_uuid=target.uuid,
            rage_damage=self.rage_damage,
            template=True
        )
        target.register_action(rage_action)

        # Register End Rage action template (SRD: end rage as bonus action)
        end_rage_action = EndRage(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(end_rage_action)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Rage ({self.rage_uses} uses, +{self.rage_damage} damage) to {target.name}"
        )

        return [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up resource and action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("rage")
            target.unregister_action("Rage")
            target.unregister_action("End Rage")

            # Also remove Raging if active
            if "Raging" in target.active_conditions:
                target.remove_condition("Raging")

        return super()._remove(event)


# =============================================================================
# FRENZY SYSTEM: Frenzied Condition
# =============================================================================

class Frenzied(BaseCondition):
    """
    BG3-style Frenzy - enhanced rage state for Berserker Barbarians.

    When activated (via Frenzy action):
    - All normal Rage benefits (STR advantage, rage damage, resistance)
    - Grants FrenziedStrike action (bonus action melee attack each turn)
    - NO exhaustion (BG3 adaptation)

    Duration: Same as Rage (ends on conditions outlined in Raging)

    NOTE: This condition is a sub-condition of Raging (set by Frenzy action).
    When rage maintenance removes Raging, the cascade automatically removes
    Frenzied. The parent-child relationship is inverted from intuition to
    make rage decay work correctly.
    """
    name: str = "Frenzied"
    description: str = "In a frenzied rage - can make bonus action melee attacks"
    rage_damage: int = 2  # Same scaling as Rage

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        # Only register FrenziedStrike action - Raging is already applied by Frenzy action
        # (Frenzied is now a sub-condition of Raging, not the parent)
        frenzied_strike = FrenziedStrike(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(frenzied_strike)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is frenzied!"
        )

        return [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up FrenziedStrike action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.unregister_action("Frenzied Strike")
            # Note: Frenzied is now a sub-condition of Raging, so it gets
            # removed automatically when rage maintenance removes Raging

        return super()._remove(event)


# =============================================================================
# FRENZY SYSTEM: Frenzied Strike Action
# =============================================================================

class FrenziedStrike(BaseAction):
    """
    Bonus action melee attack during Frenzy.

    Available while the Frenzied condition is active.
    Costs a bonus action but no other resources.
    Uses the equipped melee weapon.
    """
    name: str = "Frenzied Strike"
    description: str = "Make a bonus action melee attack while frenzied"
    target_type: TargetType = TargetType.ENTITY
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN

    costs: List[Cost] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.costs = [
            Cost(
                name="Frenzied Strike",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for frenzied strike."""
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = source_entity.name if source_entity else None
        target_name = target_entity.name if target_entity else None

        weapon_name = None
        if source_entity:
            weapon = source_entity.equipment._get_weapon_by_slot(self.weapon_slot)
            weapon_name = weapon.name if weapon and hasattr(weapon, 'name') else "Unarmed"

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
        """Check if frenzied strike can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False

        # Must be frenzied
        if "Frenzied" not in entity.active_conditions:
            return False

        # Must have bonus action available
        if not entity.action_economy.can_afford("bonus_actions", 1):
            return False

        # Must have a melee weapon
        weapon = entity.equipment._get_weapon_by_slot(self.weapon_slot)
        if weapon is None:
            return False

        return True

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        """Validate the frenzied strike."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        # Must be frenzied
        if "Frenzied" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Must be in a frenzy")

        # Validate target
        if not self.target_entity_uuid:
            return declaration_event.cancel(status_message="No target specified")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        # Validate line of sight
        if self.target_entity_uuid not in entity.senses.entities:
            return declaration_event.cancel(status_message="Target not visible")

        # Validate range
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


# =============================================================================
# FRENZY SYSTEM: Frenzy Action
# =============================================================================

class Frenzy(BaseAction):
    """
    Enter a frenzy as a bonus action (Berserker Path).

    Similar to Rage but applies Frenzied condition instead of Raging.
    The Frenzied condition includes all Rage benefits plus FrenziedStrike action.
    """
    name: str = "Frenzy"
    description: str = "Enter a frenzied rage"
    target_type: TargetType = TargetType.SELF
    rage_damage: int = 2

    costs: List[Cost] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.costs = [
            Cost(
                name="Frenzy",
                cost_type="bonus_actions",
                cost=1,
                resource_name="rage",
                resource_cost=1,
                evaluator=entity_action_economy_cost_evaluator
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

        # Cannot frenzy in heavy armor
        body_armor = entity.equipment.body_armor
        if body_armor and body_armor.type == ArmorType.HEAVY:
            return False

        # Cannot already be raging/frenzied
        if "Raging" in entity.active_conditions or "Frenzied" in entity.active_conditions:
            return False

        # Check rage resource
        if not entity.action_economy.can_afford_resource("rage", 1):
            return False

        # Check bonus action
        if not entity.action_economy.can_afford("bonus_actions", 1):
            return False

        return True

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        # Cannot frenzy in heavy armor
        body_armor = entity.equipment.body_armor
        if body_armor and body_armor.type == ArmorType.HEAVY:
            return declaration_event.cancel(status_message="Cannot frenzy in heavy armor")

        # Already raging/frenzied?
        if "Raging" in entity.active_conditions or "Frenzied" in entity.active_conditions:
            return declaration_event.cancel(status_message="Already raging")

        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")

        # 1. Apply Raging condition first (will be the parent)
        # This is reversed from the intuitive order so that rage maintenance
        # can remove Raging and cascade to remove Frenzied automatically
        raging = Raging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage
        )
        entity.add_condition(raging)

        # 2. Apply Frenzied as sub-condition of Raging
        # KEY: Frenzied is child of Raging, so when rage maintenance removes
        # Raging (due to no attacks), Frenzied is automatically removed too
        frenzied = Frenzied(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            rage_damage=self.rage_damage,
            parent_condition=raging.uuid  # Frenzied is child of Raging
        )
        entity.add_condition(frenzied)

        # 3. Link parent-child: add Frenzied to Raging's sub_conditions list
        # This enables cascade removal when Raging is removed by rage maintenance
        raging.sub_conditions.append(frenzied.uuid)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} enters a frenzy!"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# FRENZY SYSTEM: Frenzy Feature
# =============================================================================

class FrenzyFeature(BaseCondition):
    """
    Berserker Path Level 3: Frenzy

    Grants the Frenzy action which allows entering a frenzied rage.
    While frenzied, you can make a single melee weapon attack as a
    bonus action on each of your turns.

    BG3 Adaptation: No exhaustion after frenzy ends.
    """
    name: str = "Frenzy Feature"
    description: str = "Can enter a frenzied rage for bonus action attacks"
    rage_damage: int = 2

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        # Register Frenzy action template
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

        return [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up Frenzy action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.unregister_action("Frenzy")

            # Also remove Frenzied if active
            if "Frenzied" in target.active_conditions:
                target.remove_condition("Frenzied")

        return super()._remove(event)
