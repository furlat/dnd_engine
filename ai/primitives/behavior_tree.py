"""Behavior-tree primitives for tactical agents."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Dict, List, Optional, Union

from ai.composites import MoveAndAttack
from ai.interface import GameInterface
from ai.models import TacticalState

BlackboardValue = Union[str, int, float, bool, None]
Blackboard = Dict[str, BlackboardValue]
StatePredicate = Callable[[TacticalState], bool]
ActionFunction = Callable[[GameInterface, TacticalState, str], "NodeStatus"]


class NodeStatus(Enum):
    """Result returned by one behavior-tree node tick."""

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class BTContext:
    """Mutable context shared by behavior-tree nodes.

    Args:
        iface: Game interface used to execute selected actions.
        state: Current tactical snapshot for the controlled actor.
        entity_uuid: Controlled actor UUID serialized as text.
        blackboard: Optional scratch memory shared by nodes in this tree.
    """

    def __init__(
        self,
        iface: GameInterface,
        state: TacticalState,
        entity_uuid: str,
        blackboard: Optional[Blackboard] = None,
    ):
        self.iface = iface
        self.state = state
        self.entity_uuid = entity_uuid
        self.blackboard: Blackboard = blackboard or {}


class BTNode(ABC):
    """Base class for behavior-tree nodes."""

    @abstractmethod
    def tick(self, ctx: BTContext) -> NodeStatus:
        """Evaluate this node against a behavior-tree context.

        Args:
            ctx: Mutable context for the current tree tick.

        Returns:
            Node status after evaluation.
        """
        raise NotImplementedError


class Selector(BTNode):
    """Try children in order until one avoids failure."""

    def __init__(self, children: List[BTNode]):
        self.children = children

    def tick(self, ctx: BTContext) -> NodeStatus:
        """Return the first child result that is not failure."""
        for child in self.children:
            result = child.tick(ctx)
            if result != NodeStatus.FAILURE:
                return result
        return NodeStatus.FAILURE


class Sequence(BTNode):
    """Run children in order until one does not succeed."""

    def __init__(self, children: List[BTNode]):
        self.children = children

    def tick(self, ctx: BTContext) -> NodeStatus:
        """Return success only when every child succeeds."""
        for child in self.children:
            result = child.tick(ctx)
            if result != NodeStatus.SUCCESS:
                return result
        return NodeStatus.SUCCESS


class Condition(BTNode):
    """Leaf node that evaluates a tactical-state predicate."""

    def __init__(self, predicate: StatePredicate):
        self.predicate = predicate

    def tick(self, ctx: BTContext) -> NodeStatus:
        """Return success when the predicate accepts the current state."""
        return NodeStatus.SUCCESS if self.predicate(ctx.state) else NodeStatus.FAILURE


class BTAction(BTNode):
    """Leaf node that executes an action through the game interface."""

    def __init__(self, action_fn: ActionFunction):
        self.action_fn = action_fn

    def tick(self, ctx: BTContext) -> NodeStatus:
        """Execute the action and refresh context state afterward."""
        result = self.action_fn(ctx.iface, ctx.state, ctx.entity_uuid)
        ctx.state = ctx.iface.get_tactical_state(ctx.entity_uuid)
        return result


class Inverter(BTNode):
    """Decorator that swaps success and failure results."""

    def __init__(self, child: BTNode):
        self.child = child

    def tick(self, ctx: BTContext) -> NodeStatus:
        """Evaluate the child and invert terminal success or failure."""
        result = self.child.tick(ctx)
        if result == NodeStatus.SUCCESS:
            return NodeStatus.FAILURE
        if result == NodeStatus.FAILURE:
            return NodeStatus.SUCCESS
        return result


class Succeeder(BTNode):
    """Decorator that converts every child result to success."""

    def __init__(self, child: BTNode):
        self.child = child

    def tick(self, ctx: BTContext) -> NodeStatus:
        """Evaluate the child and always return success."""
        self.child.tick(ctx)
        return NodeStatus.SUCCESS


def is_threatened(state: TacticalState) -> bool:
    """Return whether the controlled actor is threatened in melee."""
    return state.is_threatened


def has_action(state: TacticalState) -> bool:
    """Return whether the controlled actor has an action remaining."""
    return state.action_economy.has_action


def has_movement(state: TacticalState) -> bool:
    """Return whether the controlled actor has movement remaining."""
    return state.action_economy.has_movement


def is_enemy_in_melee(state: TacticalState) -> bool:
    """Return whether at least one visible enemy is within five feet."""
    return bool(state.enemies_in_range(5))


def is_low_hp(threshold: float = 0.3) -> StatePredicate:
    """Build a predicate that checks the actor's hit-point fraction.

    Args:
        threshold: Fraction below which the actor counts as low on health.

    Returns:
        Predicate over a tactical state.
    """
    def check(state: TacticalState) -> bool:
        return state.me.hp_fraction < threshold

    return check


def enemy_in_range(range_feet: int) -> StatePredicate:
    """Build a predicate that checks for enemies within a range.

    Args:
        range_feet: Maximum enemy distance in feet.

    Returns:
        Predicate over a tactical state.
    """
    def check(state: TacticalState) -> bool:
        return bool(state.enemies_in_range(range_feet))

    return check


def has_enemies(state: TacticalState) -> bool:
    """Return whether the actor can see any enemies."""
    return bool(state.enemies)


def has_affordable_attack(state: TacticalState) -> bool:
    """Return whether an affordable attack with targets is available."""
    return state.has_affordable_attack()


def has_affordable_spell(state: TacticalState) -> bool:
    """Return whether an affordable spell with targets is available."""
    return state.has_affordable_spell()


def attack_nearest(
    iface: GameInterface,
    state: TacticalState,
    entity_uuid: str,
) -> NodeStatus:
    """Attack the nearest visible enemy with the first legal attack row."""
    nearest = state.nearest_enemy()
    if not nearest:
        return NodeStatus.FAILURE
    attack = state.find_attack_targeting(nearest.uuid)
    if not attack:
        return NodeStatus.FAILURE
    result = iface.execute(entity_uuid, attack[0].template_name, attack[1].index)
    return NodeStatus.SUCCESS if result.success else NodeStatus.FAILURE


def attack_weakest(
    iface: GameInterface,
    state: TacticalState,
    entity_uuid: str,
) -> NodeStatus:
    """Attack the lowest-hit-point visible enemy with a legal attack row."""
    weakest = state.weakest_enemy()
    if not weakest:
        return NodeStatus.FAILURE
    attack = state.find_attack_targeting(weakest.uuid)
    if not attack:
        return NodeStatus.FAILURE
    result = iface.execute(entity_uuid, attack[0].template_name, attack[1].index)
    return NodeStatus.SUCCESS if result.success else NodeStatus.FAILURE


def move_toward_nearest(
    iface: GameInterface,
    state: TacticalState,
    entity_uuid: str,
) -> NodeStatus:
    """Move along the best available row toward the nearest visible enemy."""
    nearest = state.nearest_enemy()
    if not nearest:
        return NodeStatus.FAILURE
    move = state.find_move_toward(nearest.uuid)
    if not move:
        return NodeStatus.FAILURE
    result = iface.execute(entity_uuid, move[0].template_name, move[1].index)
    return NodeStatus.SUCCESS if result.success else NodeStatus.FAILURE


def move_away_from_enemies(
    iface: GameInterface,
    state: TacticalState,
    entity_uuid: str,
) -> NodeStatus:
    """Move along the best available row away from the nearest enemy."""
    nearest = state.nearest_enemy()
    if not nearest:
        return NodeStatus.FAILURE
    move = state.find_move_away_from(nearest.position)
    if not move:
        return NodeStatus.FAILURE
    result = iface.execute(entity_uuid, move[0].template_name, move[1].index)
    return NodeStatus.SUCCESS if result.success else NodeStatus.FAILURE


def dodge_action(
    iface: GameInterface,
    state: TacticalState,
    entity_uuid: str,
) -> NodeStatus:
    """Execute Dodge when it is available and affordable."""
    action = state.find_self_action("Dodge")
    if not action or not action.can_afford:
        return NodeStatus.FAILURE
    result = iface.execute(entity_uuid, action.template_name, 0)
    return NodeStatus.SUCCESS if result.success else NodeStatus.FAILURE


def disengage_action(
    iface: GameInterface,
    state: TacticalState,
    entity_uuid: str,
) -> NodeStatus:
    """Execute Disengage when it is available and affordable."""
    action = state.find_self_action("Disengage")
    if not action or not action.can_afford:
        return NodeStatus.FAILURE
    result = iface.execute(entity_uuid, action.template_name, 0)
    return NodeStatus.SUCCESS if result.success else NodeStatus.FAILURE


def dash_action(
    iface: GameInterface,
    state: TacticalState,
    entity_uuid: str,
) -> NodeStatus:
    """Execute Dash when it is available and affordable."""
    action = state.find_self_action("Dash")
    if not action or not action.can_afford:
        return NodeStatus.FAILURE
    result = iface.execute(entity_uuid, action.template_name, 0)
    return NodeStatus.SUCCESS if result.success else NodeStatus.FAILURE


def move_and_attack_nearest(
    iface: GameInterface,
    state: TacticalState,
    entity_uuid: str,
) -> NodeStatus:
    """Run the move-and-attack composite against the nearest enemy."""
    nearest = state.nearest_enemy()
    if not nearest:
        return NodeStatus.FAILURE
    result = MoveAndAttack(nearest.uuid).execute(iface, state, entity_uuid)
    return NodeStatus.SUCCESS if result.success else NodeStatus.FAILURE
