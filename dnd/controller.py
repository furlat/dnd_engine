"""
Controller - Base class for entity control during encounters.

Controllers determine what actions an entity takes during their turn.
Subclass this for different control modes:
- HumanController: Waits for UI/input
- AIController: Computes actions via AI/heuristics
- ScriptedController: Follows a predefined action sequence
"""

from typing import Optional, Dict, List, ClassVar, TYPE_CHECKING
from uuid import UUID
from pydantic import Field

from dnd.core.base_object import BaseObject

if TYPE_CHECKING:
    from dnd.entity import Entity
    from dnd.core.base_actions import BaseAction


class TurnContext(BaseObject):
    """
    Context passed to controller during a turn.

    Contains all the information a controller needs to make decisions
    without needing a reference to the Encounter itself.
    """

    entity_uuid: UUID = Field(description="UUID of the entity whose turn it is")
    round_number: int = Field(default=1, description="Current round number")
    turn_index: int = Field(default=0, description="Position in initiative order")

    # Action economy remaining
    actions_remaining: int = Field(default=1)
    bonus_actions_remaining: int = Field(default=1)
    reactions_remaining: int = Field(default=1)
    movement_remaining: int = Field(default=30)

    # Visible entities (UUID -> position)
    visible_enemies: Dict[UUID, tuple] = Field(default_factory=dict)
    visible_allies: Dict[UUID, tuple] = Field(default_factory=dict)



class Controller(BaseObject):
    """
    Base controller class for managing entity actions during encounters.

    Controllers are responsible for:
    1. Deciding what action an entity should take
    2. Responding to turn lifecycle events

    The base implementation returns None from get_next_action,
    which signals "end turn". Subclass to implement actual behavior.
    """

    _controller_registry: ClassVar[Dict[UUID, 'Controller']] = {}

    name: str = Field(default="Controller", description="Name of this controller")
    controller_type: str = Field(default="base", description="Type identifier")

    def __init__(self, **data):
        super().__init__(**data)
        self.__class__._controller_registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['Controller']:
        """Get a controller by UUID."""
        return cls._controller_registry.get(uuid)

    @classmethod
    def get_all(cls) -> List['Controller']:
        """Get all registered controllers."""
        return list(cls._controller_registry.values())

    @classmethod
    def clear_registry(cls) -> None:
        """Clear the controller registry (for testing)."""
        cls._controller_registry.clear()

    def get_next_action(
        self,
        entity: 'Entity',
        context: TurnContext
    ) -> Optional['BaseAction']:
        """
        Get the next action for the entity to take.

        Called repeatedly during an entity's turn until:
        - Returns None (signals end turn)
        - Entity has no more action economy
        - Turn is forcibly ended

        Args:
            entity: The entity whose turn it is
            context: Turn context with action economy, visible entities, etc.

        Returns:
            BaseAction to execute, or None to end the turn
        """
        return None

    def on_turn_start(self, entity: 'Entity', context: TurnContext) -> None:
        """Called when the entity's turn starts."""
        pass

    def on_turn_end(self, entity: 'Entity', context: TurnContext) -> None:
        """Called when the entity's turn ends."""
        pass

    def on_encounter_start(self, entities: List['Entity']) -> None:
        """Called when an encounter starts with entities this controller manages."""
        pass

    def on_encounter_end(self, entities: List['Entity']) -> None:
        """Called when an encounter ends."""
        pass

    def can_continue_turn(self, entity: 'Entity', context: TurnContext) -> bool:
        """
        Check if the controller wants to continue the turn.

        Default: True (let encounter check action economy).
        """
        return True


class PassController(Controller):
    """A controller that always passes (ends turn immediately)."""

    name: str = Field(default="Pass Controller")
    controller_type: str = Field(default="pass")

    def get_next_action(
        self,
        entity: 'Entity',
        context: TurnContext
    ) -> Optional['BaseAction']:
        return None

    def can_continue_turn(self, entity: 'Entity', context: TurnContext) -> bool:
        return False


class HumanController(Controller):
    """
    Controller for human-controlled entities.

    Actions come via external API calls, not from get_next_action.
    This controller immediately exits the run_turn loop so the server
    can wait for human input.
    """

    name: str = Field(default="Human Player")
    controller_type: str = Field(default="human")

    def get_next_action(
        self,
        entity: 'Entity',
        context: TurnContext
    ) -> Optional['BaseAction']:
        # Never returns actions - humans provide actions via API
        return None

    def can_continue_turn(self, entity: 'Entity', context: TurnContext) -> bool:
        # Always return False to exit run_turn loop immediately
        # Server will handle human turn via API endpoints
        return False
