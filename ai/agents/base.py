"""Turn-running agents built from tactical decision primitives."""

from abc import ABC, abstractmethod

from ai.interface import GameInterface
from ai.models import TacticalState
from ai.primitives.behavior_tree import BTContext, BTNode, NodeStatus
from ai.primitives.utility import UtilityAI

MAX_TURN_ITERATIONS = 20


class BaseAgent(ABC):
    """Base class for agents that play one actor's turn."""

    def __init__(self, iface: GameInterface, entity_uuid: str):
        self.iface = iface
        self.entity_uuid = entity_uuid

    @abstractmethod
    def take_turn(self, state: TacticalState) -> None:
        """Choose and execute behavior from a tactical state.

        Args:
            state: Current tactical snapshot for the controlled actor.
        """
        raise NotImplementedError

    def run_turn(self) -> None:
        """Fetch tactical state and let the agent play the turn."""
        state = self.iface.get_tactical_state(self.entity_uuid)
        self.take_turn(state)


class BehaviorTreeAgent(BaseAgent):
    """Agent that ticks a behavior tree until the turn is spent or blocked."""

    def __init__(self, iface: GameInterface, entity_uuid: str, tree: BTNode):
        super().__init__(iface, entity_uuid)
        self.tree = tree

    def take_turn(self, state: TacticalState) -> None:
        """Run the behavior tree inside a bounded turn loop."""
        ctx = BTContext(
            iface=self.iface,
            state=state,
            entity_uuid=self.entity_uuid,
            blackboard={},
        )
        iterations = 0
        while (
            not ctx.state.action_economy.is_empty
            and iterations < MAX_TURN_ITERATIONS
        ):
            result = self.tree.tick(ctx)
            if result == NodeStatus.FAILURE:
                break
            iterations += 1


class UtilityAgent(BaseAgent):
    """Agent that repeatedly executes the best positive-scoring option."""

    def __init__(self, iface: GameInterface, entity_uuid: str, utility: UtilityAI):
        super().__init__(iface, entity_uuid)
        self.utility = utility

    def take_turn(self, state: TacticalState) -> None:
        """Run utility selection inside a bounded turn loop."""
        iterations = 0
        while iterations < MAX_TURN_ITERATIONS:
            state = self.iface.get_tactical_state(self.entity_uuid)
            best = self.utility.pick_best(state)
            if not best or best.score <= 0:
                break
            self.iface.execute(
                self.entity_uuid,
                best.action.template_name,
                best.target.index if best.target else 0,
            )
            iterations += 1
