"""Controller classes for entity turns during encounters.

Controllers decide whether an encounter turn should run autonomously or wait for
external input, and may provide actions while the encounter owns turn flow.
"""

from typing import Any, Optional, Dict, List, ClassVar, Protocol, runtime_checkable

__all__ = [
    "TurnContext",
    "Controller",
    "HumanController",
    "CodexController",
    "MeleeAIController",
    "TurnRunner",
    "AIAgentController",
]
from uuid import UUID
from pydantic import Field

from dnd.core.base_object import BaseObject
from dnd.core.base_actions import ActionCategory, BaseAction
from dnd.actions_functional import get_available_actions
from dnd.entity import Entity


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


class Controller(BaseObject):
    """Base controller for managing entity actions during encounters.

    The base implementation returns ``None`` from ``get_next_action()``, which
    signals that the turn should end.

    Attributes:
        name: Display name of this controller.
        controller_type: Stable controller type identifier.
    """

    _controller_registry: ClassVar[Dict[UUID, 'Controller']] = {}

    name: str = Field(default="Controller", description="Display name of this controller.")
    controller_type: str = Field(default="base", description="Stable controller type identifier.")

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


class CodexController(Controller):
    """Controller for Codex-controlled entities.

    Like HumanController, actions come via external API calls.
    Has its own controller_type for proper identification and debugging.

    Attributes:
        name: Display name of this controller.
        controller_type: Stable controller type identifier.
    """

    name: str = Field(default="Codex Controller", description="Display name of this controller.")
    controller_type: str = Field(default="codex", description="Stable controller type identifier.")

    def get_next_action(
        self,
        entity: Entity,
        context: TurnContext
    ) -> Optional[BaseAction]:
        return None

    def can_continue_turn(self, entity: Entity, context: TurnContext) -> bool:
        return False


class MeleeAIController(Controller):
    """Simple AI that moves toward enemies and attacks in melee.

    Priority order is attack when affordable, move closer when an action is
    still available for a later attack, otherwise end the turn.

    Attributes:
        name: Display name of this controller.
        controller_type: Stable controller type identifier.
    """

    name: str = Field(default="Melee AI", description="Display name of this controller.")
    controller_type: str = Field(default="melee_ai", description="Stable controller type identifier.")

    def get_next_action(
        self,
        entity: Entity,
        context: TurnContext
    ) -> Optional[BaseAction]:
        """Return the next attack or movement action based on visible enemies.

        Args:
            entity: Entity controlled by this AI.
            context: Turn context containing visible enemy positions.

        Returns:
            Attack, movement action, or ``None`` when the AI should pass.
        """
        available = get_available_actions(entity)

        for attack_info in available.entity_actions:
            if attack_info.action_category != ActionCategory.ATTACK:
                continue
            if attack_info.can_afford and attack_info.valid_targets:
                target = attack_info.valid_targets[0]
                if target.target_uuid is None:
                    continue
                template = entity.get_action_template(attack_info.template_name)
                if template:
                    return template.instantiate(target_entity_uuid=target.target_uuid)

        can_still_attack = entity.action_economy.can_afford("actions", 1)
        if can_still_attack and available.position_actions:
            move_info = available.position_actions[0]

            closest_pos = None
            closest_dist = float('inf')
            current_min_dist = float('inf')

            for enemy_uuid, enemy_pos in context.visible_enemies.items():
                if enemy_uuid == entity.uuid:
                    continue
                dist = abs(entity.position[0] - enemy_pos[0]) + abs(entity.position[1] - enemy_pos[1])
                if dist < current_min_dist:
                    current_min_dist = dist

            for enemy_uuid, enemy_pos in context.visible_enemies.items():
                if enemy_uuid == entity.uuid:
                    continue
                for target in move_info.valid_targets:
                    if target.position is None:
                        continue
                    pos = target.position
                    dist = abs(pos[0] - enemy_pos[0]) + abs(pos[1] - enemy_pos[1])
                    if dist < closest_dist and dist < current_min_dist:
                        closest_dist = dist
                        closest_pos = pos

            if closest_pos and closest_pos != entity.position:
                template = entity.get_action_template(move_info.template_name)
                if template:
                    return template.instantiate(end_position=closest_pos)

        return None


@runtime_checkable
class TurnRunner(Protocol):
    """Protocol for AI agents that can run a full turn autonomously."""
    def run_turn(self) -> None: ...


class AIAgentController(Controller):
    """Controller that delegates to a TurnRunner (e.g. ai.agents.base.BaseAgent).

    The agent handles the entire turn internally via GameInterface,
    so this controller runs the agent once then signals turn end.

    Attributes:
        name: Display name of this controller.
        controller_type: Stable controller type identifier.
    """

    name: str = Field(default="AI Agent", description="Display name of this controller.")
    controller_type: str = Field(default="ai_agent", description="Stable controller type identifier.")

    _agents: ClassVar[Dict[UUID, TurnRunner]] = {}
    _has_run: ClassVar[Dict[UUID, bool]] = {}

    def set_agent(self, agent: TurnRunner) -> None:
        """Bind a TurnRunner to this controller."""
        self._agents[self.uuid] = agent

    def on_turn_start(self, entity: Entity, context: TurnContext) -> None:
        """Reset the delegated-run marker at turn start.

        Args:
            entity: Entity whose turn started.
            context: Turn context at start.
        """
        self._has_run[self.uuid] = False

    def get_next_action(
        self,
        entity: Entity,
        context: TurnContext
    ) -> Optional[BaseAction]:
        """Run the delegated agent once, then end the turn.

        Args:
            entity: Entity controlled by this controller.
            context: Current turn context.

        Returns:
            Always ``None`` because the agent owns any turn actions.
        """
        agent = self._agents.get(self.uuid)
        if agent:
            agent.run_turn()
        self._has_run[self.uuid] = True
        return None

    def can_continue_turn(self, entity: Entity, context: TurnContext) -> bool:
        """Return whether the delegated agent has not yet run this turn."""
        return not self._has_run.get(self.uuid, False)
