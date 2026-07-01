"""Finite-state-machine primitives for tactical agents."""

from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Union

from ai.interface import GameInterface
from ai.models import TacticalState

ANY_STATE = "*"
MemoryValue = Union[str, int, float, bool, None]
Memory = Dict[str, MemoryValue]
TransitionCondition = Callable[[TacticalState], bool]


class FSMContext:
    """Mutable context passed to finite-state-machine states.

    Args:
        iface: Game interface used to execute selected action rows.
        state: Current tactical snapshot for the controlled actor.
        entity_uuid: Controlled actor UUID serialized as text.
        memory: Optional scratch memory shared by the state machine.
    """

    def __init__(
        self,
        iface: GameInterface,
        state: TacticalState,
        entity_uuid: str,
        memory: Optional[Memory] = None,
    ):
        self.iface = iface
        self.state = state
        self.entity_uuid = entity_uuid
        self.memory: Memory = memory or {}


class FSMState(ABC):
    """One named state in a tactical finite-state machine."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def execute(self, ctx: FSMContext) -> None:
        """Run this state's behavior for the current tick.

        Args:
            ctx: Mutable finite-state-machine context.
        """
        raise NotImplementedError

    def enter(self, ctx: FSMContext) -> None:
        """Run when this state becomes current."""

    def exit(self, ctx: FSMContext) -> None:
        """Run before this state stops being current."""


class Transition:
    """Directed transition between finite-state-machine states.

    Args:
        from_state: Source state name, or `ANY_STATE` for a global transition.
        to_state: Destination state name.
        condition: Predicate that enables the transition.
        priority: Higher priority transitions are evaluated first.
    """

    def __init__(
        self,
        from_state: str,
        to_state: str,
        condition: TransitionCondition,
        priority: int = 0,
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition
        self.priority = priority


class StateMachine:
    """Evaluate prioritized transitions and execute the current state."""

    def __init__(
        self,
        states: Dict[str, FSMState],
        transitions: List[Transition],
        initial_state: str,
    ):
        self.states = states
        self.transitions = sorted(transitions, key=lambda transition: -transition.priority)
        self.current = initial_state

    def tick(self, ctx: FSMContext) -> None:
        """Evaluate transitions, then execute the active state.

        Args:
            ctx: Mutable finite-state-machine context.
        """
        for transition in self.transitions:
            if transition.from_state not in (ANY_STATE, self.current):
                continue
            if transition.to_state == self.current:
                continue
            if transition.condition(ctx.state):
                self.states[self.current].exit(ctx)
                self.current = transition.to_state
                self.states[self.current].enter(ctx)
                break

        self.states[self.current].execute(ctx)
