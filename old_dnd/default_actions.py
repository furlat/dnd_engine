from old_dnd.actions import Action, ActionType, ActionCost, Targeting, SelfCondition
from old_dnd.core import DurationType, TargetType
from old_dnd.conditions import Dashing, Dodging,  Duration
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from old_dnd.statsblock import StatsBlock

class Dodge(SelfCondition):
    def __init__(self, stats_block: 'StatsBlock'):
        super().__init__(
            name="Dodge",
            description="Until the start of your next turn, any attack roll made against you has disadvantage if you can see the attacker, and you make Dexterity saving throws with advantage. You lose this benefit if you are incapacitated or if your speed drops to 0.",
            cost=[ActionCost(type=ActionType.ACTION, cost=1)],
            limited_usage=None,
            targeting=Targeting(type=TargetType.SELF),
            stats_block=stats_block,
            conditions=[
                Dodging(
                    name="Dodging",
                    description="Disadvantage on attack rolls against you, advantage on Dexterity saving throws",
                    duration=Duration(time=1, type=DurationType.ROUNDS)
                )
            ]
        )

class Dash(SelfCondition):
    def __init__(self, stats_block: 'StatsBlock'):
        super().__init__(
            name="Dash",
            description="You gain extra movement for the current turn. The increase equals your speed, after applying any modifiers.",
            cost=[ActionCost(type=ActionType.ACTION, cost=1)],
            limited_usage=None,
            targeting=Targeting(type=TargetType.SELF),
            stats_block=stats_block,
            conditions=[
                Dashing(
                    name="Dashing",
                    description="Double movement speed",
                    duration=Duration(time=1, type=DurationType.ROUNDS)
                )
            ]
        )
