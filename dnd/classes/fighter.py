"""
Fighter Class Features and Fighting Styles

Implements Fighter-specific features as conditions that can be applied to entities.
Organized by D&D 5e level progression.

Level 1: Fighting Styles, Second Wind
Level 2: Action Surge
Level 3: Champion - Improved Critical
Level 5: Extra Attack
Level 9: Indomitable
Level 15: Champion - Superior Critical
Level 18: Champion - Survivor (DEFERRED)
"""

from typing import Any
from dnd.core.base_conditions import BaseCondition
from dnd.types.conditions import ConditionCategory, DurationType
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
from dnd.types.behaviors import RuntimeBehaviorKind
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventType,
    EventQueue,
    Trigger,
    EventHandler,
)
from dnd.core.events.resolution_events import (
    DamageRollResultEvent,
    RangeType,
)
from dnd.core.events.check_events import (
    SavingThrowEvent,
)
from dnd.types.equipment import ArmorType, WeaponProperty, WeaponSlot
from dnd.core.dice import DiceRoll, Dice
from dnd.types.rolls import RollType, AttackOutcome
from dnd.core.modifiers import NumericalModifier, AdvantageModifier
from dnd.types.rolls import AdvantageStatus
from dnd.core.values import ModifiableValue
from dnd.blocks.equipment import (
    Weapon,
    Shield,
)
from dnd.entities.entity import Entity, determine_attack_outcome
from dnd.actions.standard import (
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
    AttackEvent,
    Attack,
    build_weapon_attack_outcome_profile,
    create_weapon_attack_declaration_event,
)
from pydantic import Field
from typing import Any, Optional, List, Tuple, cast
from uuid import UUID, uuid4
import random


def create_modified_dice_roll(original: DiceRoll, new_results: List[int]) -> DiceRoll:
    """
    Create a new DiceRoll with different results but same metadata.

    Original rolls are immutable - this creates a new version with modified results.
    The bonus is preserved and added to the new total.

    Note: Additional dice processors (maximize_all, minimize_all, etc.) are in
    dnd/classes/dice_processor_utils.py for test/reference use.
    """
    return DiceRoll(
        dice_uuid=original.dice_uuid,
        roll_type=original.roll_type,
        results=new_results,
        total=sum(new_results) + original.bonus,
        bonus=original.bonus,
        advantage_status=original.advantage_status,
        critical_status=original.critical_status,
        auto_hit_status=original.auto_hit_status,
        source_entity_uuid=original.source_entity_uuid,
        target_entity_uuid=original.target_entity_uuid,
        attack_outcome=original.attack_outcome
    )




def defense_ac_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual check for Defense fighting style.
    Returns +1 AC only if the entity is wearing armor.
    """
    _ = target_entity_uuid
    _ = context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    body_armor = entity.equipment.body_armor
    if body_armor and body_armor.type != ArmorType.CLOTH:
        return NumericalModifier.create(
            source_entity_uuid=source_entity_uuid,
            name="Defense",
            value=1
        )

    return None




def dueling_damage_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual check for Dueling fighting style.
    Returns +2 damage only if wielding a melee weapon in one hand with no other weapon.
    """
    _ = target_entity_uuid
    _ = context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    main_weapon = entity.equipment.weapon_melee_main
    off_hand = entity.equipment.weapon_melee_off

    if main_weapon is None:
        return None

    if WeaponProperty.TWO_HANDED in main_weapon.properties:
        return None

    if off_hand is not None and not isinstance(off_hand, Shield):
        return None

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Dueling",
        value=2
    )




def great_weapon_fighting_processor(
    event: DamageRollResultEvent,
    source_entity_uuid: UUID
) -> Optional[DamageRollResultEvent]:
    """Reroll low primary weapon dice for Great Weapon Fighting.

    Args:
        event: Damage-roll result event before damage is applied.
        source_entity_uuid: Entity that owns the GWF handler.

    Returns:
        Modified damage-roll event when primary weapon dice were rerolled, or
        ``None`` when the event is not eligible.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    weapon = entity.equipment._get_weapon_by_slot(event.weapon_slot)
    if not weapon or isinstance(weapon, Shield):
        return None

    if not isinstance(weapon, Weapon):
        return None

    is_melee = weapon.range.type == RangeType.REACH
    has_two_handed = WeaponProperty.TWO_HANDED in weapon.properties
    versatile_wielded_two_handed = (
        WeaponProperty.VERSATILE in weapon.properties
        and event.weapon_slot == WeaponSlot.MELEE_MAIN
        and entity.equipment.weapon_melee_off is None
    )

    if not is_melee or not (has_two_handed or versatile_wielded_two_handed):
        return None

    modified_event = event
    for packet_index, packet in enumerate(modified_event.damage_packets):
        if packet_index != 0:
            continue
        original_roll = packet.final_roll
        results = original_roll.results if isinstance(original_roll.results, list) else [original_roll.results]

        needs_reroll = any(r <= 2 for r in results)
        if not needs_reroll:
            continue

        new_results = []
        rerolled_dice = []
        for r in results:
            if r <= 2:
                new_result = random.randint(1, weapon.damage_dice)
                new_results.append(new_result)
                rerolled_dice.append(f"{r}→{new_result}")
            else:
                new_results.append(r)

        new_roll = create_modified_dice_roll(original_roll, new_results)
        modified_event = modified_event.replace_roll(
            packet_index,
            new_roll,
            "Great Weapon Fighting",
            f"Rerolled: {', '.join(rerolled_dice)}"
        )

    return modified_event if modified_event is not event else None




def protection_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Event processor for Protection fighting style.

    Imposes disadvantage on attacks against nearby allies when:
    - Protector is NOT the target
    - Target is within 5ft of protector
    - Protector can see the attacker
    - Protector has a shield equipped
    - Protector has a reaction available

    Triggers on ATTACK events at EXECUTION phase.
    """
    protector = Entity.get(source_entity_uuid)
    if not protector:
        return None

    if event.target_entity_uuid == source_entity_uuid:
        return None

    target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
    if not target:
        return None
    distance = protector.distance_to_entity(target)
    if distance > 5:
        return None

    if event.source_entity_uuid not in protector.senses.entities:
        return None

    off_hand = protector.equipment.weapon_melee_off
    if not off_hand or not isinstance(off_hand, Shield):
        return None

    if not protector.action_economy.can_afford("reactions", 1):
        return None

    if not isinstance(event, AttackEvent) or not event.attack_bonus:
        return None
    attack_bonus = event.attack_bonus

    for modifier in attack_bonus.self_static.advantage_modifiers.values():
        if modifier.name == "Protection":
            return None

    attack_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            name="Protection",
            value=AdvantageStatus.DISADVANTAGE,
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.target_entity_uuid
        )
    )

    protector.action_economy.consume("reactions", 1)

    return event.with_updates(
        status_message=(
            f"{protector.name} uses Protection to impose disadvantage"
        ),
    )


class ProtectionReactionHandler(EventHandler):
    """Independently authored reaction installed by the Protection style."""


def create_protection_handler(source_entity_uuid: UUID) -> ProtectionReactionHandler:
    """Create an EventHandler for Protection fighting style."""
    return ProtectionReactionHandler(
        name="Protection",
        semantic_key="feature.fighter.protection",
        content_kind=RuntimeBehaviorKind.REACTION,
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=protection_processor,
        player_toggleable=True
    )




def twf_off_hand_melee_ability_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual modifier for TWF off-hand melee damage.
    Evaluated at damage time - checks weapon properties to determine correct ability.
    """
    _ = target_entity_uuid, context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    off_hand = entity.equipment.weapon_melee_off
    if not off_hand or isinstance(off_hand, Shield):
        return None

    if WeaponProperty.FINESSE in off_hand.properties:
        str_mod = entity.ability_scores.strength.modifier
        dex_mod = entity.ability_scores.dexterity.modifier
        bonus = max(str_mod, dex_mod)
    else:
        bonus = entity.ability_scores.strength.modifier

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Two-Weapon Fighting",
        value=bonus
    )


def twf_off_hand_ranged_ability_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """Contextual modifier for TWF off-hand ranged damage."""
    _ = target_entity_uuid, context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    off_hand = entity.equipment.weapon_ranged_off
    if not off_hand:
        return None

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Two-Weapon Fighting",
        value=entity.ability_scores.dexterity.modifier
    )




class SecondWind(BaseAction):
    """Fighter self-heal action that spends the Second Wind resource.

    Attributes:
        name: Action name displayed for the Fighter self-heal.
        description: Short rules-facing summary of the Second Wind action.
        target_type: Second Wind always targets the acting fighter.
        fighter_level: Fighter level added to the Second Wind healing roll.
        costs: Bonus-action and second-wind resource costs rebuilt after model initialization.
    """
    name: str = Field(default="Second Wind", description="Action name displayed for the Fighter self-heal.")
    description: str = Field(
        default="Heal 1d10 + level as a bonus action",
        description="Short rules-facing summary of the Second Wind action.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Second Wind always targets the acting fighter.",
    )
    fighter_level: int = Field(
        default=1,
        description="Fighter level added to the Second Wind healing roll.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Bonus-action and second-wind resource costs rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Second Wind Cost",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
                resource_name="second_wind",
                resource_cost=1,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return declaration_event.cancel(status_message="Entity not found")

        if entity.health.damage_taken == 0:
            return declaration_event.cancel(status_message="Already at full health")

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Second Wind ready"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")

        healing_dice = Dice(
            count=1,
            value=10,
            bonus=ModifiableValue.create(
                source_entity_uuid=self.source_entity_uuid,
                base_value=self.fighter_level,
                value_name="Fighter Level"
            ),
            roll_type=RollType.CHECK
        )
        healing_roll = healing_dice.roll
        total_healing = healing_roll.total

        roll_results = healing_roll.results
        roll_str = str(roll_results[0]) if isinstance(roll_results, list) and roll_results else "?"
        source_desc = f"Second Wind: d10({roll_str})+{self.fighter_level}"

        actual_healing = entity.receive_healing(
            total_healing, entity.uuid,
            source_description=source_desc,
            parent_event=execution_event.uuid
        )

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Second Wind heals {actual_healing} HP (d10+{self.fighter_level}={total_healing})"
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Second Wind complete - healed {actual_healing} HP"
        )



class ActionSurging(BaseCondition):
    """Temporary internal state granted by Action Surge.

    Attributes:
        name: Internal marker condition name for active Action Surge state.
        description: Short rules-facing summary of the temporary Action Surge state.
        condition_category: Marks ActionSurging as an internal lifecycle condition.
    """
    name: str = Field(
        default="ActionSurging",
        description="Internal marker condition name for active Action Surge state.",
    )
    description: str = Field(
        default="+1 action this turn (Action Surge used)",
        description="Short rules-facing summary of the temporary Action Surge state.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        description="Marks ActionSurging as an internal lifecycle condition.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 1

        outs = []

        modifier = NumericalModifier(
            name="Action Surge",
            value=1,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target_entity.action_economy.actions.self_static.add_value_modifier(modifier)
        outs.append((target_entity.action_economy.actions.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target_entity.name} surges with extra action!"
        )

        return outs, [], [], [], effect_event


class ActionSurge(BaseAction):
    """Fighter action that spends Action Surge for one extra action.

    Attributes:
        name: Action name displayed for Action Surge.
        description: Short rules-facing summary of the Action Surge action.
        target_type: Action Surge always targets the acting fighter.
        costs: Action-surge resource cost rebuilt after model initialization.
    """
    name: str = Field(default="Action Surge", description="Action name displayed for Action Surge.")
    description: str = Field(
        default="Take one additional action on your turn",
        description="Short rules-facing summary of the Action Surge action.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Action Surge always targets the acting fighter.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Action-surge resource cost rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Action Surge",
                cost_type="actions",
                cost=0,
                resource_name="action_surge",
                resource_cost=1,
                evaluator=None,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate Action Surge can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if "ActionSurging" in entity.active_conditions:
            return declaration_event.cancel(status_message="Already used Action Surge this turn")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Action Surge - grant extra action."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        surging = ActionSurging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        entity.add_condition(surging, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{entity.name} uses Action Surge!"
        )





class ExtraAttacksGranted(BaseCondition):
    """Internal marker for extra attacks granted during the current turn.

    Attributes:
        name: Internal marker condition name for Extra Attack resource grants this turn.
        description: Short lifecycle summary for the Extra Attack grant marker.
        condition_category: Marks ExtraAttacksGranted as an internal lifecycle condition.
    """
    name: str = Field(
        default="ExtraAttacksGranted",
        description="Internal marker condition name for Extra Attack resource grants this turn.",
    )
    description: str = Field(
        default="Extra attacks have been granted this turn",
        description="Short lifecycle summary for the Extra Attack grant marker.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        description="Marks ExtraAttacksGranted as an internal lifecycle condition.",
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
            status_message="Marked as ExtraAttacksGranted"
        )
        return [], [], [], [], effect_event


def extra_attack_resource_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Fighter-specific processor: manages extra_attacks resource for Extra Attack.

    This processor handles Action Surge compatibility:
    - First Attack action this turn: Set extra_attacks = num_extra_attacks
    - Subsequent Attack actions (via Action Surge): ADD num_extra_attacks

    This ensures that each Attack action grants the full number of extra attacks,
    even when Action Surge grants additional actions mid-turn.

    Triggers on ATTACK at EXECUTION phase (for action-cost attacks only).
    Uses ExtraAttacksGranted marker (not HasAttacked) to track first vs subsequent.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    if event.canceled:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if not EventQueue.is_first_at_phase(event):
        return None

    if not isinstance(event, ActionEvent) or not event.costs:
        return None

    action_cost_attack = any(
        c.cost_type == "actions" and c.cost > 0
        for c in event.costs
    )
    if not action_cost_attack:
        return None

    extra_attack_resource = entity.action_economy.resources.get("extra_attacks")
    attacks_per_action = (
        entity.action_economy.resolve_attacks_per_attack_action()
    )
    if attacks_per_action > 1:
        num_extra = attacks_per_action - 1
    else:
        return None

    if not extra_attack_resource:
        return None

    if "ExtraAttacksGranted" not in entity.active_conditions:
        extra_attack_resource.current = num_extra

        marker = ExtraAttacksGranted(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        marker.duration.duration_type = DurationType.ROUNDS
        marker.duration.duration = 1
        entity.add_condition(marker, parent_event=event)
    else:
        extra_attack_resource.current += num_extra

    return None


def create_extra_attack_resource_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create an EventHandler that manages extra_attacks resource for Fighter."""
    return EventHandler(
        name="Extra Attack Resource",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=extra_attack_resource_processor
    )


class ExtraAttack(BaseAction):
    """Fighter action that spends the extra-attacks resource for another attack.

    Attributes:
        name: Action name displayed for Fighter extra attacks.
        description: Short rules-facing summary of the Extra Attack action.
        target_type: Extra Attack targets a visible entity in weapon reach or range.
        weapon_slot: Weapon slot used to resolve the additional attack.
        action_category: Marks Extra Attack as an attack action for discovery and reactions.
        costs: Extra-attack resource cost rebuilt after model initialization.
        discover_equipped_weapon_slots: Whether the structural template expands
            into one discovery row per equipped weapon.
    """
    name: str = Field(default="Extra Attack", description="Action name displayed for Fighter extra attacks.")
    description: str = Field(
        default="Make an additional weapon attack",
        description="Short rules-facing summary of the Extra Attack action.",
    )
    target_type: TargetType = Field(
        default=TargetType.ENTITY,
        description="Extra Attack targets a visible entity in weapon reach or range.",
    )
    weapon_slot: WeaponSlot = Field(
        default=WeaponSlot.MELEE_MAIN,
        description="Weapon slot used to resolve the additional attack.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ATTACK,
        description="Marks Extra Attack as an attack action for discovery and reactions.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Extra-attack resource cost rebuilt after model initialization.",
    )
    discover_equipped_weapon_slots: bool = Field(
        default=False,
        description=(
            "Whether one structural family template expands into current "
            "equipped-weapon discovery variants."
        ),
    )

    def get_discovery_weapon_slot(self) -> Optional[WeaponSlot]:
        """Return the equipped slot used by this extra attack."""
        return self.weapon_slot

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Extra Attack",
                cost_type="actions",
                cost=0,
                resource_name="extra_attacks",
                resource_cost=1,
                evaluator=None,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def get_discovery_variants(self, entity: Any) -> List[BaseAction]:
        """Expand a structural family template over the current weapon set."""
        if not self.discover_equipped_weapon_slots:
            return super().get_discovery_variants(entity)
        if not isinstance(entity, Entity):
            return []
        variants: List[BaseAction] = []
        for slot in (
            WeaponSlot.MELEE_MAIN,
            WeaponSlot.MELEE_OFF,
            WeaponSlot.RANGED_MAIN,
            WeaponSlot.RANGED_OFF,
        ):
            weapon = entity.equipment._get_weapon_by_slot(slot)
            if weapon is None or isinstance(weapon, Shield):
                continue
            variants.append(
                self.model_copy(
                    deep=True,
                    update={
                        "uuid": uuid4(),
                        "name": f"Extra Attack_{slot.value}",
                        "weapon_slot": slot,
                        "template": False,
                        "use_register": False,
                    },
                ),
            )
        return variants

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return the same actor-baseline weapon profile as a normal attack."""
        return build_weapon_attack_outcome_profile(actor, self.weapon_slot)

    def validate_source_requirements_for_discovery(self) -> bool:
        """Require the attack-earned batch before exposing target legality."""
        entity = Entity.get(self.source_entity_uuid)
        return (
            isinstance(entity, Entity)
            and "ExtraAttacksGranted" in entity.active_conditions
        )

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for the extra attack action."""
        return create_weapon_attack_declaration_event(
            action_name="Extra Attack",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=self.costs,
            parent_event=parent_event,
            use_register=use_register,
            append_weapon_to_name=True,
        )

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        """Validate the extra attack action."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if "ExtraAttacksGranted" not in entity.active_conditions:
            return declaration_event.cancel(
                status_message="Must attack first before using Extra Attack"
            )

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

        ranged_conditions = Attack.check_ranged_conditions(range_validated, self.source_entity_uuid)
        if ranged_conditions is None or ranged_conditions.canceled:
            return ranged_conditions

        return ranged_conditions.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Extra Attack validated"
        )

    def _apply(self, execution_event) -> Optional[Event]:
        """Apply the extra attack - execute the actual attack logic."""
        attack_event = cast(AttackEvent, execution_event)
        return Attack.attack_consequences(attack_event, self.source_entity_uuid)



def indomitable_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Reroll failed saving throws.
    Triggers on SAVING_THROW at EFFECT phase.

    Per RAW: Must use the new roll, even if it's worse.
    """
    if event.target_entity_uuid != source_entity_uuid:
        return None

    if not isinstance(event, SavingThrowEvent):
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if event.result is not False:
        return None

    dc = event.get_dc()
    if dc is None:
        return None

    if not entity.action_economy.can_afford_resource("indomitable", 1):
        return None

    ability_name = event.ability_name
    save_bonus = entity.saving_throw_bonus(event.source_entity_uuid, ability_name)
    new_roll = entity.roll_d20(
        save_bonus,
        RollType.SAVE,
        ability_name=ability_name,
        parent_event=event.uuid,
    )

    if not entity.action_economy.consume_resource("indomitable", 1):
        return None

    new_outcome = determine_attack_outcome(new_roll, dc)
    new_success = new_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

    return event.with_updates(
        dice_roll=new_roll,
        result=new_success,
        status_message=(
            f"{entity.name} uses Indomitable! Reroll: {new_roll.total} "
            f"vs DC {dc} - {'Success' if new_success else 'Failure'}"
        ),
    )


def create_indomitable_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create EventHandler for Indomitable."""
    return EventHandler(
        name="Indomitable",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.SAVING_THROW,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=indomitable_processor,
        player_toggleable=True
    )






def survivor_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Turn start handler for Survivor.
    Heals 5 + CON mod if HP <= 50% and HP > 0.
    Triggers at EXECUTION phase, before conditions advance.

    Per SRD: At the start of each of your turns, you regain hit points equal
    to 5 + your Constitution modifier if you have no more than half of your
    hit points left. You don't gain this benefit if you have 0 hit points.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    current_hp = entity.get_hp()
    max_hp = current_hp + entity.health.damage_taken

    if current_hp <= 0:
        return None

    if current_hp > max_hp / 2:
        return None

    con_mod = entity.ability_scores.constitution.modifier
    healing = 5 + con_mod

    actual_healed = entity.receive_healing(
        healing, entity.uuid,
        source_description=f"Survivor: 5+{con_mod}",
        parent_event=event.uuid
    )

    return event.with_updates(
        status_message=f"Survivor heals {actual_healed} HP (5+{con_mod})",
    )


def create_survivor_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create EventHandler for Survivor turn start healing."""
    return EventHandler(
        name="Survivor",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=survivor_processor
    )
