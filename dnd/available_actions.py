"""
Available Actions Query System

Determines what actions an entity can currently perform based on:
- Action economy state (remaining actions, bonus actions, reactions, movement)
- Active conditions (Incapacitated, Grappled, etc.)
- Equipment (weapons determine attack options)
- Senses (visible targets, reachable positions)

This is a read-only query system - it reports what's possible, doesn't execute actions.
"""

from typing import List, Tuple, Optional, Literal
from uuid import UUID
from pydantic import BaseModel, Field

from dnd.core.base_actions import CostType
from dnd.core.events import WeaponSlot, RangeType


ActionCategory = Literal["action", "bonus_action", "reaction", "movement", "free"]


class AvailableAction(BaseModel):
    """Represents a single action the entity can take."""

    # Identity
    action_id: str = Field(description="Unique identifier: 'attack_main_hand', 'move', 'dash', etc.")
    name: str = Field(description="Display name: 'Attack (Longsword)', 'Move', 'Dash'")
    description: str = Field(default="")

    # Cost
    cost_type: CostType = Field(description="'actions', 'bonus_actions', 'reactions', 'movement'")
    cost_amount: int = Field(description="How much it costs")
    can_afford: bool = Field(description="Can entity currently afford this?")

    # Targeting - one of these will be populated based on action type
    requires_target: bool = Field(default=False)
    valid_targets: List[UUID] = Field(default_factory=list, description="For targeted actions (Attack)")
    valid_positions: List[Tuple[int, int]] = Field(default_factory=list, description="For movement")

    # Metadata for UI/AI
    category: ActionCategory = Field(description="Grouping for UI display")
    weapon_slot: Optional[WeaponSlot] = Field(default=None, description="For attacks")


class AvailableActionsResult(BaseModel):
    """Complete result of available actions query."""

    entity_uuid: UUID

    # Grouped by category for easy UI rendering
    attacks: List[AvailableAction] = Field(default_factory=list)
    movement: List[AvailableAction] = Field(default_factory=list)
    other_actions: List[AvailableAction] = Field(default_factory=list, description="Dash, Dodge, Disengage")
    bonus_actions: List[AvailableAction] = Field(default_factory=list)
    reactions: List[AvailableAction] = Field(default_factory=list)
    free_actions: List[AvailableAction] = Field(default_factory=list, description="Drop Prone")

    # Summary flags
    can_attack: bool = Field(default=False)
    can_move: bool = Field(default=False)
    remaining_movement: int = Field(default=0)

    # Blocking conditions (for UI display: "You are Incapacitated")
    blocking_conditions: List[str] = Field(default_factory=list)


# Import Entity here to avoid circular import
from dnd.entity import Entity


def _get_blocking_conditions(entity: Entity) -> Tuple[bool, bool, List[str]]:
    """
    Check which conditions block actions.

    Returns:
        can_act: bool - Can take any actions at all
        can_move: bool - Can move
        blocking: List[str] - Names of blocking conditions
    """
    blocking = []
    can_act = True
    can_move = True

    # Incapacitated blocks all actions
    if "Incapacitated" in entity.active_conditions:
        can_act = False
        can_move = False
        blocking.append("Incapacitated")

    # These include Incapacitated as sub-condition
    for cond in ["Stunned", "Paralyzed", "Unconscious"]:
        if cond in entity.active_conditions:
            can_act = False
            can_move = False
            if cond not in blocking:
                blocking.append(cond)

    # Movement blockers (don't block actions, just movement)
    if "Grappled" in entity.active_conditions:
        can_move = False
        blocking.append("Grappled")

    if "Restrained" in entity.active_conditions:
        can_move = False
        blocking.append("Restrained")

    return can_act, can_move, blocking


def _get_weapon(entity: Entity, weapon_slot: WeaponSlot):
    """Get the weapon in a slot (helper using Equipment's _get_weapon_by_slot)."""
    from dnd.blocks.equipment import Weapon
    item = entity.equipment._get_weapon_by_slot(weapon_slot)
    # Return only if it's a Weapon (not a Shield)
    if isinstance(item, Weapon):
        return item
    return None


def _get_valid_attack_targets(entity: Entity, weapon_slot: WeaponSlot) -> List[UUID]:
    """Get entities that can be attacked with the weapon in this slot."""
    weapon = _get_weapon(entity, weapon_slot)
    if weapon is None:
        return []

    targets = []
    weapon_range = weapon.range

    for target_uuid, target_pos in entity.senses.entities.items():
        if target_uuid == entity.uuid:
            continue  # Can't attack self

        distance = entity.senses.get_feet_distance(target_pos)

        if weapon_range.type == RangeType.REACH:
            # Melee: within reach (usually 5ft)
            if distance <= weapon_range.normal:
                targets.append(target_uuid)
        else:
            # Ranged: within long range (normal range has no disadvantage penalty here)
            long_range = weapon_range.long if weapon_range.long is not None else weapon_range.normal
            if distance <= long_range:
                targets.append(target_uuid)

    return targets


def _get_valid_melee_targets(entity: Entity, reach: int = 5) -> List[UUID]:
    """Get entities within melee reach (for unarmed strikes)."""
    targets = []

    for target_uuid, target_pos in entity.senses.entities.items():
        if target_uuid == entity.uuid:
            continue

        distance = entity.senses.get_feet_distance(target_pos)
        if distance <= reach:
            targets.append(target_uuid)

    return targets


def _get_attack_options(entity: Entity, can_act: bool) -> List[AvailableAction]:
    """Get all attack actions available."""
    if not can_act:
        return []

    attacks = []
    can_afford_action = entity.action_economy.can_afford("actions", 1)
    can_afford_bonus = entity.action_economy.can_afford("bonus_actions", 1)

    # Check each weapon slot (melee and ranged, main and off)
    for slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF]:
        weapon = _get_weapon(entity, slot)
        if weapon is None:
            continue

        valid_targets = _get_valid_attack_targets(entity, slot)
        slot_id = slot.value.lower()  # e.g., "melee_main", "ranged_off"

        # Two-Weapon Fighting: off-hand attacks cost a bonus action
        is_off_hand = slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF)
        cost_type: CostType = "bonus_actions" if is_off_hand else "actions"
        can_afford = can_afford_bonus if is_off_hand else can_afford_action
        category: ActionCategory = "bonus_action" if is_off_hand else "action"

        # Add (off-hand) suffix for clarity
        name_suffix = " (off-hand)" if is_off_hand else ""

        attacks.append(AvailableAction(
            action_id=f"attack_{slot_id}",
            name=f"Attack ({weapon.name}){name_suffix}",
            description=f"{weapon.dice_numbers}d{weapon.damage_dice} {weapon.damage_type.value}" + (" [no ability mod]" if is_off_hand else ""),
            cost_type=cost_type,
            cost_amount=1,
            can_afford=can_afford and len(valid_targets) > 0,
            requires_target=True,
            valid_targets=valid_targets,
            category=category,
            weapon_slot=slot
        ))

    # Unarmed strike - always available if no weapons or as additional option
    valid_melee = _get_valid_melee_targets(entity)
    str_mod = entity.ability_scores.strength.modifier  # Returns int directly
    attacks.append(AvailableAction(
        action_id="attack_unarmed",
        name="Unarmed Strike",
        description=f"1 + {str_mod} bludgeoning",
        cost_type="actions",
        cost_amount=1,
        can_afford=can_afford_action and len(valid_melee) > 0,
        requires_target=True,
        valid_targets=valid_melee,
        category="action"
    ))

    return attacks


def _get_movement_options(entity: Entity, can_move: bool) -> List[AvailableAction]:
    """Get movement action with all valid positions."""
    if not can_move:
        return []

    remaining = entity.action_economy.movement.normalized_score
    if remaining <= 0:
        return []

    # Check for Prone (costs double to move while crawling)
    is_prone = "Prone" in entity.active_conditions
    movement_multiplier = 2 if is_prone else 1

    # Filter paths by remaining movement
    valid_positions = []
    for pos, path in entity.senses.paths.items():
        cost = len(path) * 5 * movement_multiplier
        if cost <= remaining and pos != entity.senses.position:
            valid_positions.append(pos)

    if not valid_positions:
        return []

    return [AvailableAction(
        action_id="move",
        name="Move",
        description=f"{remaining}ft remaining" + (" (crawling)" if is_prone else ""),
        cost_type="movement",
        cost_amount=0,  # Variable, depends on destination
        can_afford=True,
        requires_target=False,
        valid_positions=valid_positions,
        category="movement"
    )]


def _get_other_actions(entity: Entity, can_act: bool) -> List[AvailableAction]:
    """Get Dash, Dodge, Disengage actions."""
    if not can_act:
        return []

    can_afford = entity.action_economy.can_afford("actions", 1)
    actions = []

    # Dash - always available if can act
    base_movement = entity.action_economy.get_base_value("movement")
    actions.append(AvailableAction(
        action_id="dash",
        name="Dash",
        description=f"Gain {base_movement}ft extra movement",
        cost_type="actions",
        cost_amount=1,
        can_afford=can_afford,
        category="action"
    ))

    # Dodge - always available if can act
    actions.append(AvailableAction(
        action_id="dodge",
        name="Dodge",
        description="Attackers have disadvantage, advantage on DEX saves",
        cost_type="actions",
        cost_amount=1,
        can_afford=can_afford,
        category="action"
    ))

    # Disengage - always available if can act
    actions.append(AvailableAction(
        action_id="disengage",
        name="Disengage",
        description="Movement doesn't provoke opportunity attacks",
        cost_type="actions",
        cost_amount=1,
        can_afford=can_afford,
        category="action"
    ))

    return actions


def _get_prone_actions(entity: Entity, can_move: bool) -> List[AvailableAction]:
    """Get Stand Up and Drop Prone actions."""
    actions = []
    is_prone = "Prone" in entity.active_conditions
    remaining_movement = entity.action_economy.movement.normalized_score
    base_movement = entity.action_economy.get_base_value("movement")
    half_movement = base_movement // 2

    if is_prone and can_move:
        # Stand Up - costs half your base movement
        can_stand = remaining_movement >= half_movement
        actions.append(AvailableAction(
            action_id="stand_up",
            name="Stand Up",
            description=f"Costs {half_movement}ft movement",
            cost_type="movement",
            cost_amount=half_movement,
            can_afford=can_stand,
            category="movement"
        ))
    elif not is_prone:
        # Drop Prone - always free
        actions.append(AvailableAction(
            action_id="drop_prone",
            name="Drop Prone",
            description="Drop to the ground (free)",
            cost_type="movement",
            cost_amount=0,
            can_afford=True,
            category="free"
        ))

    return actions


def get_available_actions(entity: Entity) -> AvailableActionsResult:
    """
    Get all available actions for an entity.

    This is the main entry point for the query system.

    Args:
        entity: The entity to query

    Returns:
        AvailableActionsResult with all available actions grouped by category
    """
    # Step 1: Check blocking conditions
    can_act, can_move, blocking = _get_blocking_conditions(entity)

    # Step 2: Get action economy state
    remaining_movement = entity.action_economy.movement.normalized_score

    # Step 3: Gather actions by category
    attacks = _get_attack_options(entity, can_act)
    movement = _get_movement_options(entity, can_move)
    other_actions = _get_other_actions(entity, can_act)
    prone_actions = _get_prone_actions(entity, can_move)

    # Separate prone actions into movement vs free
    movement_actions = [a for a in prone_actions if a.category == "movement"]
    free_actions = [a for a in prone_actions if a.category == "free"]

    # Combine movement with stand up if applicable
    all_movement = movement + movement_actions

    # Determine can_attack and can_move flags
    can_attack = any(a.can_afford and a.valid_targets for a in attacks)
    has_movement = len(movement) > 0 and len(movement[0].valid_positions) > 0

    return AvailableActionsResult(
        entity_uuid=entity.uuid,
        attacks=attacks,
        movement=all_movement,
        other_actions=other_actions,
        bonus_actions=[],  # Future: two-weapon fighting, etc.
        reactions=[],      # Future: opportunity attack readiness
        free_actions=free_actions,
        can_attack=can_attack,
        can_move=has_movement,
        remaining_movement=remaining_movement,
        blocking_conditions=blocking
    )
