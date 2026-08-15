"""Controller classes for entity turns during encounters.

Controllers decide whether an encounter turn should run autonomously or wait for
external input, and may provide actions while the encounter owns turn flow.
"""

from dataclasses import dataclass
from typing import Any, Optional, Dict, List, ClassVar

__all__ = [
    "TurnContext",
    "ControllerStepResult",
    "Controller",
    "PassController",
    "HumanController",
]
from uuid import UUID
from pydantic import Field

from dnd.core.base_object import BaseObject
from dnd.core.base_actions import (
    BaseAction,
)
from dnd.core.events.events_registry import (
    Event,
)
from dnd.entity import Entity
from dnd.types import encounter as encounter_types


class TurnContext(BaseObject):
    """Context passed to a controller during a turn.

    Contains all the information a controller needs to make decisions
    without needing a reference to the Encounter itself.

    Attributes:
        entity_uuid: UUID of the entity whose turn it is.
        round_number: Current encounter round number.
        turn_index: Position in initiative order.
        actions_remaining: Action count remaining.
        bonus_actions_remaining: Bonus action count remaining.
        reactions_remaining: Reaction count remaining.
        movement_remaining: Movement remaining in feet.
        visible_enemies: Visible enemy UUIDs mapped to positions.
        visible_allies: Visible ally UUIDs mapped to positions.
    """

    entity_uuid: UUID = Field(description="UUID of the entity whose turn it is.")
    round_number: int = Field(default=1, description="Current encounter round number.")
    turn_index: int = Field(default=0, description="Position in initiative order.")
    actions_remaining: int = Field(default=1, description="Action count remaining.")
    bonus_actions_remaining: int = Field(default=1, description="Bonus action count remaining.")
    reactions_remaining: int = Field(default=1, description="Reaction count remaining.")
    movement_remaining: int = Field(default=30, description="Movement remaining in feet.")
    visible_enemies: Dict[UUID, tuple] = Field(
        default_factory=dict,
        description="Visible enemy UUIDs mapped to positions.",
    )
    visible_allies: Dict[UUID, tuple] = Field(
        default_factory=dict,
        description="Visible ally UUIDs mapped to positions.",
    )
    encounter_uuid: Optional[UUID] = Field(
        default=None,
        description="Encounter identity when this turn belongs to an encounter.",
    )
    encounter_name: Optional[str] = Field(
        default=None,
        description="Encounter display name.",
    )
    encounter_state: Optional[encounter_types.EncounterState] = Field(
        default=None,
        description="Current encounter lifecycle state.",
    )
    initiative_order: List[UUID] = Field(
        default_factory=list,
        description="Objective initiative identities supplied to the controller runtime.",
    )
    initiative_totals: Dict[UUID, int] = Field(
        default_factory=dict,
        description="Initiative totals keyed by combatant UUID.",
    )
    turn_started_source_event_cursor: Optional[int] = Field(
        default=None,
        description="Source cursor of the current turn-start boundary.",
    )


@dataclass(frozen=True, slots=True)
class ControllerStepResult:
    """One controller-owned execution step returned to the encounter loop."""

    event: Optional[Event] = None
    end_turn: bool = False


class Controller(BaseObject):
    """Base controller for managing entity actions during encounters.

    The base implementation returns ``None`` from ``get_next_action()``, which
    signals that the turn should end.

    Attributes:
        name: Display name of this controller.
        controller_type: Stable controller type identifier.
    """

    _controller_registry: ClassVar[Dict[UUID, 'Controller']] = {}
    _execution_mode: ClassVar[encounter_types.ControllerExecutionMode] = (
        encounter_types.ControllerExecutionMode.AUTONOMOUS
    )
    _external_boundary_status: ClassVar[
        Optional[encounter_types.AdvanceStatus]
    ] = None

    name: str = Field(default="Controller", description="Display name of this controller.")
    controller_type: str = Field(default="base", description="Stable controller type identifier.")

    @property
    def execution_mode(self) -> encounter_types.ControllerExecutionMode:
        """Return whether the encounter should invoke this controller locally."""
        return self._execution_mode

    @property
    def external_boundary_status(self) -> Optional[encounter_types.AdvanceStatus]:
        """Return the stable wait status for an external controller boundary."""
        return self._external_boundary_status

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.__class__._controller_registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['Controller']:
        """Return a controller by UUID."""
        return cls._controller_registry.get(uuid)

    @classmethod
    def get_all(cls) -> List['Controller']:
        """Return all registered controllers."""
        return list(cls._controller_registry.values())

    @classmethod
    def clear_registry(cls) -> None:
        """Clear the controller registry."""
        cls._controller_registry.clear()

    def get_next_action(
        self,
        entity: Entity,
        context: TurnContext
    ) -> Optional[BaseAction]:
        """Return the next action for an entity.

        Called repeatedly during an entity's turn until:
        - this method returns ``None``;
        - the entity has no remaining action economy;
        - the turn is forcibly ended.

        Args:
            entity: Entity whose turn it is.
            context: Turn context with action economy and visible entities.

        Returns:
            Action to execute, or ``None`` to end the turn.
        """
        return None

    def execute_next_action(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> ControllerStepResult:
        """Execute one decision using the controller's authoritative path.

        Controllers may override this method when they need to execute a
        decision without returning a ``BaseAction`` instance.
        """
        action = self.get_next_action(entity, context)
        if action is None:
            return ControllerStepResult(end_turn=True)
        return ControllerStepResult(event=action.apply())

    def on_turn_start(self, entity: Entity, context: TurnContext) -> None:
        """Handle turn start notification.

        Args:
            entity: Entity whose turn started.
            context: Turn context at start.
        """
        pass

    def on_turn_end(self, entity: Entity, context: TurnContext) -> None:
        """Handle turn end notification.

        Args:
            entity: Entity whose turn ended.
            context: Turn context at end.
        """
        pass

    def on_encounter_start(self, entities: List[Entity]) -> None:
        """Handle encounter start notification.

        Args:
            entities: Entities controlled by this controller in the encounter.
        """
        pass

    def on_encounter_end(self, entities: List[Entity]) -> None:
        """Handle encounter end notification.

        Args:
            entities: Entities controlled by this controller in the encounter.
        """
        pass

    def can_continue_turn(self, entity: Entity, context: TurnContext) -> bool:
        """Return whether this controller wants to continue the turn.

        Args:
            entity: Entity whose turn is running.
            context: Current turn context.

        Returns:
            ``True`` when the encounter should ask for another action.
        """
        return True


class PassController(Controller):
    """Controller that always ends its turn immediately.

    Attributes:
        name: Display name of this controller.
        controller_type: Stable controller type identifier.
    """

    name: str = Field(default="Pass Controller", description="Display name of this controller.")
    controller_type: str = Field(default="pass", description="Stable controller type identifier.")

    def get_next_action(
        self,
        entity: Entity,
        context: TurnContext
    ) -> Optional[BaseAction]:
        return None

    def can_continue_turn(self, entity: Entity, context: TurnContext) -> bool:
        return False
class HumanController(Controller):
    """Controller for human-controlled entities.

    Actions come via external API calls, not from get_next_action.
    This controller immediately exits the run_turn loop so the server
    can wait for human input.

    Attributes:
        name: Display name of this controller.
        controller_type: Stable controller type identifier.
    """

    _execution_mode: ClassVar[encounter_types.ControllerExecutionMode] = encounter_types.ControllerExecutionMode.EXTERNAL
    _external_boundary_status: ClassVar[encounter_types.AdvanceStatus] = (
        encounter_types.AdvanceStatus.WAITING_FOR_HUMAN
    )

    name: str = Field(default="Human Player", description="Display name of this controller.")
    controller_type: str = Field(default="human", description="Stable controller type identifier.")

    def get_next_action(
        self,
        entity: Entity,
        context: TurnContext
    ) -> Optional[BaseAction]:
        return None

    def can_continue_turn(self, entity: Entity, context: TurnContext) -> bool:
        return False
