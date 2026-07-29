"""
Barbarian Class Features

Implements Barbarian-specific features as conditions that can be applied to entities.
Organized by D&D 5e level progression.

Level 1: Rage (Unarmored Defense handled via EquipmentConfig)
Level 2: Reckless Attack, Danger Sense
Level 3: Berserker Path - Frenzy (BG3 version - no exhaustion)
Level 5: Extra Attack (reuses Fighter's ExtraAttackFeature), Fast Movement
Level 6: Mindless Rage
Level 7: Feral Instinct
Level 9/13/17: Brutal Critical
Level 10: Intimidating Presence
Level 11: Relentless Rage
Level 14: Retaliation
Level 15: Persistent Rage
Level 18: Indomitable Might
Level 20: Primal Champion
"""

from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import DurationType
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.base_block import BaseBlock
from dnd.core.base_actions import (
    BaseAction, ActionEvent, Cost, TargetType, BaseCost
)
from dnd.core.events import (
    Event, EventPhase, EventType,
    Trigger, EventHandler,
    DamageAppliedEvent, RangeType, TakeDamageEvent, SkillCheckEvent
)
from dnd.core.equipment_types import ArmorType, WeaponSlot
from dnd.core.modifiers import (
    NumericalModifier, AdvantageModifier, AdvantageStatus,
    ContextualNumericalModifier, ContextualAdvantageModifier,
)
from dnd.blocks.action_economy import RechargeType
from dnd.core.dice import RollType
from dnd.entity import Entity
from dnd.actions import (
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
    Attack,
)
from dnd.conditions import Frightened
from pydantic import Field
from typing import Any, Optional, List, Tuple
from uuid import UUID
from functools import partial

from dnd.classes.rage import (
    rage_damage_check,
    rage_maintenance_processor,
    rage_armor_equip_handler,
    create_rage_maintenance_handler,
    create_rage_armor_handler,
    rage_death_processor,
    create_rage_death_handler,
    Raging,
    Rage,
    EndRage,
    RageFeature,
    Frenzied,
    FrenziedStrike,
    Frenzy,
    FrenzyFeature,
)

__all__ = [
    "rage_damage_check",
    "rage_maintenance_processor",
    "rage_armor_equip_handler",
    "create_rage_maintenance_handler",
    "create_rage_armor_handler",
    "rage_death_processor",
    "create_rage_death_handler",
    "Raging",
    "Rage",
    "EndRage",
    "RageFeature",
    "Frenzied",
    "FrenziedStrike",
    "Frenzy",
    "FrenzyFeature",
    "RecklessAttacking",
    "RecklessAttack",
    "RecklessAttackFeature",
    "danger_sense_check",
    "DangerSense",
    "fast_movement_check",
    "FastMovement",
    "mindless_rage_immunity_check",
    "MindlessRage",
    "FeralInstinct",
    "BrutalCritical",
    "IntimidatingPresenceImmunity",
    "intimidating_presence_end_check_processor",
    "create_intimidating_presence_end_handler",
    "IntimidatingPresence",
    "ExtendIntimidatingPresence",
    "IntimidatingPresenceFeature",
    "relentless_rage_processor",
    "RelentlessRage",
    "retaliation_processor",
    "RetaliationReactionHandler",
    "create_retaliation_handler",
    "Retaliation",
    "PersistentRage",
    "indomitable_might_processor",
    "create_indomitable_might_handler",
    "IndomitableMight",
    "PrimalChampion",
]


def reckless_attack_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None,
) -> Optional[AdvantageModifier]:
    """Grant Reckless Attack advantage only to Strength melee attacks."""
    if (
        context is None
        or context.get("attack_ability") != "strength"
        or context.get("range_type") != RangeType.REACH.value
    ):
        return None
    return AdvantageModifier(
        name="Reckless Attack",
        value=AdvantageStatus.ADVANTAGE,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
    )


class RecklessAttacking(BaseCondition):
    """Active Reckless Attack state and exposed-target marker.

    Attributes:
        name: Marker condition name for active Reckless Attack state.
        description: Short rules-facing summary of the active Reckless Attack state.
    """
    name: str = Field(
        default="Reckless Attacking",
        description="Marker condition name for active Reckless Attack state.",
    )
    description: str = Field(
        default="Advantage on melee STR attacks, but attackers have advantage against you",
        description="Short rules-facing summary of the active Reckless Attack state.",
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

        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 1

        outs: List[Tuple[UUID, UUID]] = []

        melee_adv_mod = ContextualAdvantageModifier(
            name="Reckless Attack",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=reckless_attack_check,
        )
        mod_uuid = (
            target.equipment.melee_attack_bonus.self_contextual
            .add_advantage_modifier(melee_adv_mod)
        )
        outs.append((target.equipment.melee_attack_bonus.uuid, mod_uuid))

        attacker_adv_mod = AdvantageModifier(
            name="Reckless (Exposed)",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target.equipment.ac_bonus.to_target_static.add_advantage_modifier(attacker_adv_mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} attacks recklessly!"
        )

        return outs, [], [], [], effect_event


class RecklessAttack(BaseAction):
    """Barbarian action that enables Reckless Attack for the current turn.

    Attributes:
        name: Action name displayed for Reckless Attack.
        description: Short rules-facing summary of the Reckless Attack action.
        target_type: Reckless Attack always targets the acting Barbarian.
        costs: Reckless Attack has no action or resource costs.
    """
    name: str = Field(default="Reckless Attack", description="Action name displayed for Reckless Attack.")
    description: str = Field(
        default="Attack recklessly - advantage on attacks, but exposed to counter-attacks",
        description="Short rules-facing summary of the Reckless Attack action.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Reckless Attack always targets the acting Barbarian.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Reckless Attack has no action or resource costs.",
    )

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        source_name = entity.name if entity else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return declaration_event.cancel(status_message="Entity not found")

        if "Reckless Attacking" in entity.active_conditions:
            return declaration_event.cancel(status_message="Already attacking recklessly")

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Reckless Attack ready"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")

        reckless = RecklessAttacking(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        entity.add_condition(reckless, parent_event=execution_event)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} attacks recklessly!"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return completion_event


class RecklessAttackFeature(BaseCondition):
    """Barbarian feature that grants the Reckless Attack action.

    Attributes:
        name: Feature condition name for Reckless Attack lookup and cleanup.
        description: Short rules-facing summary of the Reckless Attack feature.
    """
    name: str = Field(
        default="Reckless Attack Feature",
        description="Feature condition name for Reckless Attack lookup and cleanup.",
    )
    description: str = Field(
        default="Can attack recklessly for advantage at cost of being easier to hit",
        description="Short rules-facing summary of the Reckless Attack feature.",
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

        reckless_action = RecklessAttack(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(reckless_action)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Reckless Attack to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.unregister_action("Reckless Attack")

        return super()._remove(event)


def danger_sense_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[AdvantageModifier]:
    """
    Contextual check for Danger Sense.

    Grants advantage on DEX saves against effects you can see,
    as long as you're not blinded, deafened, or incapacitated.
    """
    _ = context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    disabled_conditions = ["Blinded", "Deafened"]
    if any(c in entity.active_conditions for c in disabled_conditions):
        return None
    if not entity.can_take_actions():
        return None

    if target_entity_uuid and target_entity_uuid not in entity.senses.entities:
        return None

    return AdvantageModifier(
        name="Danger Sense",
        value=AdvantageStatus.ADVANTAGE,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid
    )


class DangerSense(BaseCondition):
    """Barbarian feature that grants conditional Dexterity save advantage.

    Attributes:
        name: Feature condition name for Danger Sense.
        description: Short rules-facing summary of the Danger Sense feature.
    """
    name: str = Field(default="Danger Sense", description="Feature condition name for Danger Sense.")
    description: str = Field(
        default="Advantage on DEX saves vs effects you can see",
        description="Short rules-facing summary of the Danger Sense feature.",
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

        outs: List[Tuple[UUID, UUID]] = []

        dex_save = target.saving_throws.get_saving_throw("dexterity")
        danger_mod = ContextualAdvantageModifier(
            name="Danger Sense",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=danger_sense_check
        )
        mod_uuid = dex_save.bonus.self_contextual.add_advantage_modifier(danger_mod)
        outs.append((dex_save.bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Danger Sense to {target.name}"
        )

        return outs, [], [], [], effect_event


def fast_movement_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual check for Fast Movement.

    Returns +10 ft speed if not wearing heavy armor.
    """
    _ = target_entity_uuid, context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    body_armor = entity.equipment.body_armor
    if body_armor and body_armor.type == ArmorType.HEAVY:
        return None

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Fast Movement",
        value=10
    )


class FastMovement(BaseCondition):
    """Barbarian feature that increases movement outside heavy armor.

    Attributes:
        name: Feature condition name for Fast Movement.
        description: Short rules-facing summary of the Fast Movement feature.
    """
    name: str = Field(default="Fast Movement", description="Feature condition name for Fast Movement.")
    description: str = Field(
        default="+10 ft speed when not in heavy armor",
        description="Short rules-facing summary of the Fast Movement feature.",
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

        outs: List[Tuple[UUID, UUID]] = []

        speed_mod = ContextualNumericalModifier(
            name="Fast Movement",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=fast_movement_check
        )
        mod_uuid = target.action_economy.movement.self_contextual.add_value_modifier(speed_mod)
        outs.append((target.action_economy.movement.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Fast Movement to {target.name}"
        )

        return outs, [], [], [], effect_event


def mindless_rage_immunity_check(
    entity: 'BaseBlock',
    target_entity: Optional['BaseBlock'],
    context: Optional[dict]
) -> bool:
    """
    Contextual immunity check for Mindless Rage.

    Returns True (immune) only if the entity is currently raging.
    """
    _ = target_entity, context

    if "Raging" in entity.active_conditions or "Frenzied" in entity.active_conditions:
        return True

    return False


class MindlessRage(BaseCondition):
    """Berserker feature that grants charm and fear immunity while raging.

    Attributes:
        name: Feature condition name for Mindless Rage.
        description: Short rules-facing summary of the Mindless Rage immunity feature.
    """
    name: str = Field(default="Mindless Rage", description="Feature condition name for Mindless Rage.")
    description: str = Field(
        default="Cannot be charmed or frightened while raging",
        description="Short rules-facing summary of the Mindless Rage immunity feature.",
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

        target.add_condition_immunity(
            "Charmed",
            immunity_name="Mindless Rage",
            immunity_check=mindless_rage_immunity_check
        )
        target.add_condition_immunity(
            "Frightened",
            immunity_name="Mindless Rage",
            immunity_check=mindless_rage_immunity_check
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Mindless Rage to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up condition immunities on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target._remove_contextual_condition_immunity("Charmed", "Mindless Rage")
            target._remove_contextual_condition_immunity("Frightened", "Mindless Rage")
        return super()._remove(event)


class FeralInstinct(BaseCondition):
    """Barbarian feature that grants initiative advantage.

    Attributes:
        name: Feature condition name for Feral Instinct.
        description: Short rules-facing summary of the Feral Instinct feature.
    """
    name: str = Field(default="Feral Instinct", description="Feature condition name for Feral Instinct.")
    description: str = Field(
        default="Advantage on initiative rolls",
        description="Short rules-facing summary of the Feral Instinct feature.",
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

        outs: List[Tuple[UUID, UUID]] = []

        init_adv = AdvantageModifier(
            name="Feral Instinct",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )

        mod_uuid = target.initiative.self_static.add_advantage_modifier(init_adv)
        outs.append((target.initiative.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Feral Instinct to {target.name}"
        )

        return outs, [], [], [], effect_event


class BrutalCritical(BaseCondition):
    """Barbarian feature that adds melee critical-hit damage dice.

    Attributes:
        name: Feature condition name for Brutal Critical.
        description: Short rules-facing summary of the Brutal Critical feature.
        extra_dice: Additional melee critical-hit damage dice granted by Brutal Critical.
    """
    name: str = Field(default="Brutal Critical", description="Feature condition name for Brutal Critical.")
    description: str = Field(
        default="Extra damage dice on critical melee hits",
        description="Short rules-facing summary of the Brutal Critical feature.",
    )
    extra_dice: int = Field(
        default=1,
        description="Additional melee critical-hit damage dice granted by Brutal Critical.",
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

        outs: List[Tuple[UUID, UUID]] = []

        brutal_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Brutal Critical",
            value=self.extra_dice
        )
        mod_uuid = target.equipment.crit_extra_dice_melee.self_static.add_value_modifier(brutal_mod)
        outs.append((target.equipment.crit_extra_dice_melee.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Brutal Critical ({self.extra_dice} dice) to {target.name}"
        )

        return outs, [], [], [], effect_event


def relentless_rage_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    Drop to 1 HP instead of 0 while raging (CON save).

    Triggers on TAKE_DAMAGE at EFFECT phase.
    DC starts at 10 and increases by 5 each time used.
    DC is calculated from resource: DC = 10 + (uses_consumed * 5)
    Resource resets on short rest, automatically resetting DC.
    """
    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if "Raging" not in entity.active_conditions and "Frenzied" not in entity.active_conditions:
        return None

    if not isinstance(event, TakeDamageEvent):
        return None

    current_hp = entity.get_normal_hp()
    preview = entity.preview_take_damage(event)
    if current_hp - preview.normal_hit_point_damage > 0:
        return None

    resource = entity.action_economy.resources.get("relentless_rage")
    if not resource or resource.current <= 0:
        return None

    uses_consumed = resource.maximum - resource.current
    current_dc = 10 + (uses_consumed * 5)

    con_save = entity.saving_throws.get_saving_throw("constitution")
    dice_roll = entity.roll_d20(
        con_save.bonus,
        RollType.SAVE,
        ability_name="constitution",
        parent_event=event.uuid,
    )
    total = dice_roll.total

    if total >= current_dc:
        entity.action_economy.consume_resource("relentless_rage", 1)

        damage_cap = max(0, current_hp - 1)
        if event.normal_hit_point_damage_cap is not None:
            damage_cap = min(damage_cap, event.normal_hit_point_damage_cap)
        return event.with_updates(
            normal_hit_point_damage_cap=damage_cap,
            status_message=(
                f"Relentless Rage! (CON save {total} vs DC {current_dc}) "
                "- survives with 1 HP"
            ),
        )
    else:
        return event.with_updates(
            status_message=(
                f"Relentless Rage failed "
                f"(CON save {total} vs DC {current_dc})"
            ),
        )


class RelentlessRage(BaseCondition):
    """Barbarian feature that can keep a raging barbarian at 1 hit point.

    Attributes:
        name: Feature condition name for Relentless Rage.
        description: Short rules-facing summary of the Relentless Rage feature.
    """
    name: str = Field(default="Relentless Rage", description="Feature condition name for Relentless Rage.")
    description: str = Field(
        default="CON save to drop to 1 HP instead of 0 while raging",
        description="Short rules-facing summary of the Relentless Rage feature.",
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

        handler_uuids: List[UUID] = []

        target.action_economy.add_resource(
            name="relentless_rage",
            maximum=5,
            recharge_type=RechargeType.SHORT_REST
        )

        handler = EventHandler(
            name="Relentless Rage",
            source_entity_uuid=target.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=relentless_rage_processor
        )
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Relentless Rage to {target.name}"
        )

        return [], handler_uuids, [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up resource on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("relentless_rage")
        return super()._remove(event)


class PersistentRage(BaseCondition):
    """Barbarian marker that prevents ordinary rage maintenance expiry.

    Attributes:
        name: Feature condition name for Persistent Rage.
        description: Short rules-facing summary of the Persistent Rage marker.
    """
    name: str = Field(default="PersistentRage", description="Feature condition name for Persistent Rage.")
    description: str = Field(
        default="Rage only ends if unconscious or chosen",
        description="Short rules-facing summary of the Persistent Rage marker.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Persistent Rage active"
        )

        return [], [], [], [], effect_event


def indomitable_might_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    If STR check total is less than STR score, use STR score instead.

    Triggers on SKILL_CHECK at EFFECT phase.
    Only applies to STR-based skill checks (Athletics).
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    if not isinstance(event, SkillCheckEvent):
        return None

    if event.skill_name != "athletics":
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    str_score = entity.ability_scores.strength.ability_score.score

    if not event.dice_roll:
        return None

    total = event.dice_roll.total

    if total < str_score:
        new_dice_roll = event.dice_roll.model_copy(update={"total": str_score})
        return event.with_updates(
            dice_roll=new_dice_roll,
            status_message=(
                f"Indomitable Might: using STR score {str_score} "
                f"instead of {total}"
            ),
        )

    return None


def create_indomitable_might_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create handler for Indomitable Might."""
    return EventHandler(
        name="Indomitable Might",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.SKILL_CHECK,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=indomitable_might_processor
    )


class IndomitableMight(BaseCondition):
    """Barbarian feature that floors Strength checks at the Strength score.

    Attributes:
        name: Feature condition name for Indomitable Might.
        description: Short rules-facing summary of the Indomitable Might feature.
    """
    name: str = Field(default="Indomitable Might", description="Feature condition name for Indomitable Might.")
    description: str = Field(
        default="STR checks can't be lower than STR score",
        description="Short rules-facing summary of the Indomitable Might feature.",
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

        handler_uuids: List[UUID] = []

        handler = create_indomitable_might_handler(target.uuid)
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Indomitable Might to {target.name}"
        )

        return [], handler_uuids, [], [], effect_event


class PrimalChampion(BaseCondition):
    """Barbarian capstone that boosts Strength and Constitution.

    Attributes:
        name: Feature condition name for Primal Champion.
        description: Short rules-facing summary of the Primal Champion feature.
    """
    name: str = Field(default="Primal Champion", description="Feature condition name for Primal Champion.")
    description: str = Field(
        default="+4 STR and CON (max 24)",
        description="Short rules-facing summary of the Primal Champion feature.",
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

        outs: List[Tuple[UUID, UUID]] = []

        str_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Primal Champion (STR)",
            value=4
        )
        mod_uuid = target.ability_scores.strength.ability_score.self_static.add_value_modifier(str_mod)
        outs.append((target.ability_scores.strength.ability_score.uuid, mod_uuid))

        con_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Primal Champion (CON)",
            value=4
        )
        mod_uuid = target.ability_scores.constitution.ability_score.self_static.add_value_modifier(con_mod)
        outs.append((target.ability_scores.constitution.ability_score.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Primal Champion to {target.name}: +4 STR, +4 CON"
        )

        return outs, [], [], [], effect_event


def retaliation_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    When taking damage from a creature within 5ft, make a reaction melee attack.

    Triggers after positive post-mitigation damage has been applied.
    """
    if event.target_entity_uuid != source_entity_uuid:
        return None

    if not isinstance(event, DamageAppliedEvent):
        return None

    if not event.source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity or not entity.has_hp:
        return None

    attacker = Entity.get(event.source_entity_uuid)
    if not attacker:
        return None

    distance = entity.senses.get_feet_distance(attacker.senses.position)
    if distance > 5:
        return None

    if not entity.action_economy.can_afford("reactions", 1):
        return None

    weapon = entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    if weapon is None:
        return None

    attack = Attack(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=event.source_entity_uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        costs=[],
        parent_event=event
    )
    result = attack.apply(parent_event=event)
    if result is not None and not result.canceled:
        entity.action_economy.consume("reactions", 1)

    return None


class RetaliationReactionHandler(EventHandler):
    """Independently authored reaction installed by Retaliation."""


def create_retaliation_handler(
    source_entity_uuid: UUID,
) -> RetaliationReactionHandler:
    """Create handler for Retaliation."""
    return RetaliationReactionHandler(
        name="Retaliation",
        semantic_key="feature.barbarian.retaliation",
        content_kind=RuntimeBehaviorKind.REACTION,
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.DAMAGE_APPLIED,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=retaliation_processor,
        player_toggleable=True
    )


class Retaliation(BaseCondition):
    """Berserker feature that reacts to nearby damage with a melee attack.

    Attributes:
        name: Feature condition name for Retaliation.
        description: Short rules-facing summary of the Retaliation feature.
    """
    name: str = Field(default="Retaliation", description="Feature condition name for Retaliation.")
    description: str = Field(
        default="Reaction melee attack when hit by adjacent creature",
        description="Short rules-facing summary of the Retaliation feature.",
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

        handler_uuids: List[UUID] = []

        handler = create_retaliation_handler(target.uuid)
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Retaliation to {target.name}"
        )

        return [], handler_uuids, [], [], effect_event


class IntimidatingPresenceImmunity(BaseCondition):
    """Marker for a target that resisted a Barbarian's Intimidating Presence.

    Attributes:
        name: Marker condition name for a target that resisted a Barbarian's Intimidating Presence.
        description: Short lifecycle summary of Intimidating Presence save immunity.
    """
    name: str = Field(
        default="Intimidating Presence Immunity",
        description="Marker condition name for a target that resisted a Barbarian's Intimidating Presence.",
    )
    description: str = Field(
        default="Immune to a specific creature's Intimidating Presence",
        description="Short lifecycle summary of Intimidating Presence save immunity.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Intimidating Presence immunity applied"
        )

        return [], [], [], [], effect_event


def intimidating_presence_end_check_processor(
    event: Event, source_entity_uuid: UUID, barbarian_uuid: UUID
) -> Optional[Event]:
    """
    Check if Frightened from Intimidating Presence should end at turn end.

    SRD: "This effect ends if the creature ends its turn out of line of sight
    or more than 60 feet away from you."

    Triggers on TURN_END at EXECUTION phase for the frightened creature.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    creature = Entity.get(source_entity_uuid)
    barbarian = Entity.get(barbarian_uuid)

    if not creature or not barbarian:
        return None

    frightened = creature.active_conditions.get("Frightened")
    if not frightened or frightened.source_entity_uuid != barbarian_uuid:
        return None

    distance = creature.senses.get_feet_distance(barbarian.senses.position)
    should_end = distance > 60

    if not should_end and barbarian_uuid not in creature.senses.entities:
        should_end = True

    if should_end:
        creature.remove_condition("Frightened", parent_event=event)
        reason = "out of range" if distance > 60 else "out of line of sight"
        return event.with_updates(
            status_message=(
                f"{creature.name} is no longer frightened "
                f"({reason} from {barbarian.name})"
            ),
        )

    return None


def create_intimidating_presence_end_handler(
    source_entity_uuid: UUID, barbarian_uuid: UUID
) -> EventHandler:
    """
    Create handler that checks if Frightened from Intimidating Presence should end.

    Uses functools.partial to bind the barbarian_uuid to the processor.
    """
    bound_processor = partial(
        intimidating_presence_end_check_processor,
        barbarian_uuid=barbarian_uuid
    )

    return EventHandler(
        name="Intimidating Presence End Check",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=bound_processor
    )


class IntimidatingPresence(BaseAction):
    """Berserker action that attempts to frighten a visible target.

    Attributes:
        name: Action name displayed for the Berserker frighten action.
        description: Short rules-facing summary of the Intimidating Presence action.
        target_type: Intimidating Presence targets one visible entity within range.
        costs: Action cost rebuilt after model initialization.
    """
    name: str = Field(
        default="Intimidating Presence",
        description="Action name displayed for the Berserker frighten action.",
    )
    description: str = Field(
        default="Frighten a creature within 30ft (WIS save)",
        description="Short rules-facing summary of the Intimidating Presence action.",
    )
    target_type: TargetType = Field(
        default=TargetType.ENTITY,
        description="Intimidating Presence targets one visible entity within range.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Action cost rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Intimidating Presence",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = entity.name if entity else None
        target_name = target.name if target else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name
        )

    def _is_target_immune(self, target: Entity) -> bool:
        """Check if target has immunity to this barbarian's Intimidating Presence."""
        for condition in target.active_conditions.values():
            if (condition.name == "Intimidating Presence Immunity" and
                    condition.source_entity_uuid == self.source_entity_uuid):
                return True
        return False

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if not self.target_entity_uuid:
            return declaration_event.cancel(status_message="No target specified")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        distance = entity.senses.get_feet_distance(target.senses.position)
        if distance > 30:
            return declaration_event.cancel(status_message="Target beyond 30ft")

        if self.target_entity_uuid not in entity.senses.entities:
            return declaration_event.cancel(status_message="Target not visible")

        if self._is_target_immune(target):
            return declaration_event.cancel(status_message="Target is immune (saved within 24h)")

        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not entity or not target or not self.target_entity_uuid:
            return execution_event.cancel(status_message="Entity or target not found")

        proficiency = entity.proficiency_bonus.normalized_score
        cha_mod = entity.ability_scores.charisma.modifier
        dc = 8 + proficiency + cha_mod

        request = entity.create_saving_throw_request(
            target_entity_uuid=self.target_entity_uuid,
            ability_name="wisdom",
            dc=dc
        )
        _, dice_roll, success = target.saving_throw(request)

        if success:
            immunity = IntimidatingPresenceImmunity(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
            target.add_condition(immunity, parent_event=execution_event)

            return execution_event.phase_to(
                EventPhase.COMPLETION,
                status_message=f"{target.name} resists Intimidating Presence (WIS save {dice_roll.total} vs DC {dc})"
            )
        else:
            frightened = Frightened(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
            frightened.duration.duration_type = DurationType.ROUNDS
            frightened.duration.duration = 1

            target.add_condition(frightened, parent_event=execution_event)

            end_handler = create_intimidating_presence_end_handler(
                source_entity_uuid=self.target_entity_uuid,
                barbarian_uuid=self.source_entity_uuid
            )
            target.add_event_handler(end_handler)
            frightened.event_handlers_uuids.append(end_handler.uuid)

            return execution_event.phase_to(
                EventPhase.COMPLETION,
                status_message=f"{target.name} is frightened by {entity.name}! (WIS save {dice_roll.total} vs DC {dc})"
            )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class ExtendIntimidatingPresence(BaseAction):
    """Berserker action that extends an existing Intimidating Presence fear.

    Attributes:
        name: Action name displayed for extending Intimidating Presence.
        description: Short rules-facing summary of the extension action.
        target_type: Extend Intimidating Presence targets a visible entity frightened by the acting Barbarian.
        costs: Action cost rebuilt after model initialization.
    """
    name: str = Field(
        default="Extend Intimidating Presence",
        description="Action name displayed for extending Intimidating Presence.",
    )
    description: str = Field(
        default="Extend the Frightened effect on a creature",
        description="Short rules-facing summary of the extension action.",
    )
    target_type: TargetType = Field(
        default=TargetType.ENTITY,
        description="Extend Intimidating Presence targets a visible entity frightened by the acting Barbarian.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Action cost rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Extend Intimidating Presence",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = entity.name if entity else None
        target_name = target.name if target else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name
        )

    def _is_frightened_by_me(self, target: Entity) -> bool:
        """Check if target is Frightened by this barbarian."""
        frightened = target.active_conditions.get("Frightened")
        if not frightened:
            return False
        return frightened.source_entity_uuid == self.source_entity_uuid

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if not self.target_entity_uuid:
            return declaration_event.cancel(status_message="No target specified")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        distance = entity.senses.get_feet_distance(target.senses.position)
        if distance > 30:
            return declaration_event.cancel(status_message="Target beyond 30ft")

        if self.target_entity_uuid not in entity.senses.entities:
            return declaration_event.cancel(status_message="Target not visible")

        if not self._is_frightened_by_me(target):
            return declaration_event.cancel(status_message="Target not frightened by you")

        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not entity or not target:
            return execution_event.cancel(status_message="Entity or target not found")

        frightened = target.active_conditions.get("Frightened")
        if frightened and frightened.source_entity_uuid == self.source_entity_uuid:
            frightened.duration.duration = 1

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} extends Intimidating Presence on {target.name}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class IntimidatingPresenceFeature(BaseCondition):
    """Berserker feature that grants Intimidating Presence actions.

    Attributes:
        name: Feature condition name for Intimidating Presence action registration.
        description: Short rules-facing summary of the Intimidating Presence feature.
    """
    name: str = Field(
        default="Intimidating Presence Feature",
        description="Feature condition name for Intimidating Presence action registration.",
    )
    description: str = Field(
        default="Can use action to frighten creatures within 30ft",
        description="Short rules-facing summary of the Intimidating Presence feature.",
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

        intimidate_action = IntimidatingPresence(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(intimidate_action)

        extend_action = ExtendIntimidatingPresence(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(extend_action)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Intimidating Presence to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up actions on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.unregister_action("Intimidating Presence")
            target.unregister_action("Extend Intimidating Presence")

        return super()._remove(event)
