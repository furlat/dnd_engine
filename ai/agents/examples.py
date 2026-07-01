"""Ready-made tactical agents for common combat roles."""

from ai.agents.base import BehaviorTreeAgent, UtilityAgent
from ai.interface import GameInterface
from ai.primitives.behavior_tree import (
    BTAction,
    Condition,
    Selector,
    Sequence,
    attack_nearest,
    attack_weakest,
    disengage_action,
    dodge_action,
    has_affordable_attack,
    has_enemies,
    has_movement,
    is_threatened,
    move_and_attack_nearest,
    move_away_from_enemies,
    move_toward_nearest,
)
from ai.primitives.utility import (
    DamageScorer,
    FocusFireScorer,
    SelfPreservationScorer,
    ThreatAvoidanceScorer,
    UtilityAI,
)


def create_melee_fighter_bt(iface: GameInterface, entity_uuid: str) -> BehaviorTreeAgent:
    """Create a melee behavior that attacks, closes distance, or dodges.

    Args:
        iface: Game interface used by the agent.
        entity_uuid: Controlled actor UUID serialized as text.

    Returns:
        Behavior-tree agent with melee pressure priorities.
    """
    tree = Selector([
        Sequence([
            Condition(has_affordable_attack),
            BTAction(attack_nearest),
        ]),
        Sequence([
            Condition(has_enemies),
            BTAction(move_and_attack_nearest),
        ]),
        Sequence([
            Condition(has_movement),
            Condition(has_enemies),
            BTAction(move_toward_nearest),
        ]),
        BTAction(dodge_action),
    ])
    return BehaviorTreeAgent(iface, entity_uuid, tree)


def create_goblin_archer_bt(iface: GameInterface, entity_uuid: str) -> BehaviorTreeAgent:
    """Create a ranged skirmisher behavior tree.

    The function name is kept for existing callers. The behavior retreats from
    melee pressure, attacks the weakest available target, closes distance when
    needed, and dodges when no stronger branch applies.

    Args:
        iface: Game interface used by the agent.
        entity_uuid: Controlled actor UUID serialized as text.

    Returns:
        Behavior-tree agent with ranged skirmisher priorities.
    """
    tree = Selector([
        Sequence([
            Condition(is_threatened),
            BTAction(disengage_action),
            BTAction(move_away_from_enemies),
        ]),
        Sequence([
            Condition(has_affordable_attack),
            BTAction(attack_weakest),
        ]),
        Sequence([
            Condition(has_movement),
            BTAction(move_toward_nearest),
        ]),
        BTAction(dodge_action),
    ])
    return BehaviorTreeAgent(iface, entity_uuid, tree)


def create_utility_fighter(iface: GameInterface, entity_uuid: str) -> UtilityAgent:
    """Create a utility-scored fighter behavior.

    Args:
        iface: Game interface used by the agent.
        entity_uuid: Controlled actor UUID serialized as text.

    Returns:
        Utility agent that balances damage, focus fire, threat avoidance, and
        self-preservation scores.
    """
    utility = UtilityAI([
        DamageScorer(weight=1.0),
        FocusFireScorer(weight=0.5),
        ThreatAvoidanceScorer(weight=0.3),
        SelfPreservationScorer(weight=1.0),
    ])
    return UtilityAgent(iface, entity_uuid, utility)
