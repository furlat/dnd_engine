"""Behavior-tree policy for the first external melee AI."""

from __future__ import annotations

from enum import Enum
from typing import Callable, List, Optional, Tuple

from pydantic import BaseModel, Field

from ai.external.state import ExternalActionRow, ExternalActionTarget, ExternalAgentState, ExternalKnownObject


class AgentCommandType(str, Enum):
    """Command kinds produced by the external behavior tree."""

    EXECUTE = "execute"
    END_TURN = "end_turn"
    WAIT = "wait"


class AgentCommand(BaseModel):
    """Executable command selected by the external behavior tree."""

    command_type: AgentCommandType = Field(description="Selected command kind.")
    entity_uuid: Optional[str] = Field(default=None, description="Acting entity UUID.")
    template_name: Optional[str] = Field(default=None, description="Action template name to execute.")
    target_index: int = Field(default=0, description="Target index to execute.")
    reason: str = Field(default="", description="Behavior-tree leaf that selected this command.")


class ExternalBTNode:
    """Behavior-tree node that may produce an agent command."""

    def tick(self, state: ExternalAgentState) -> Optional[AgentCommand]:
        """Evaluate this node against the reduced external state."""
        raise NotImplementedError


class ExternalSelector(ExternalBTNode):
    """Try child nodes until one returns a command."""

    def __init__(self, children: List[ExternalBTNode]) -> None:
        """Create a selector from ordered child nodes."""
        self.children = children

    def tick(self, state: ExternalAgentState) -> Optional[AgentCommand]:
        """Return the first command produced by any child."""
        for child in self.children:
            command = child.tick(state)
            if command is not None:
                return command
        return None


class ExternalActionLeaf(ExternalBTNode):
    """Leaf node backed by a command-producing function."""

    def __init__(self, chooser: Callable[[ExternalAgentState], Optional[AgentCommand]]) -> None:
        """Create a leaf from a chooser function."""
        self.chooser = chooser

    def tick(self, state: ExternalAgentState) -> Optional[AgentCommand]:
        """Run the chooser."""
        return self.chooser(state)


def create_external_melee_tree() -> ExternalBTNode:
    """Create the v1 external melee behavior tree."""
    return ExternalSelector([
        ExternalActionLeaf(_cast_visible_enemy_spell),
        ExternalActionLeaf(_attack_visible_enemy),
        ExternalActionLeaf(_move_toward_visible_enemy),
        ExternalActionLeaf(_open_adjacent_door),
        ExternalActionLeaf(_move_toward_closed_door),
        ExternalActionLeaf(_end_turn),
    ])


def choose_external_melee_command(state: ExternalAgentState) -> AgentCommand:
    """Return the next command for the v1 external melee policy."""
    if not state.is_my_turn or state.actor_uuid is None:
        return AgentCommand(command_type=AgentCommandType.WAIT, reason="not_my_turn")
    command = create_external_melee_tree().tick(state)
    if command is None:
        return AgentCommand(command_type=AgentCommandType.WAIT, reason="no_command")
    return command


def _attack_visible_enemy(state: ExternalAgentState) -> Optional[AgentCommand]:
    """Select the first affordable attack row with a target."""
    for action in state.entity_actions:
        if action.action_category != "attack" or not action.can_afford:
            continue
        for target in action.valid_targets:
            if target.target_uuid:
                return _execute(state, action, target, "attack_visible_enemy")
    return None


def _cast_visible_enemy_spell(state: ExternalAgentState) -> Optional[AgentCommand]:
    """Select the first affordable entity-targeting spell against a visible enemy."""
    visible_enemy_uuids = {enemy.uuid for enemy in state.visible_enemies}
    if not visible_enemy_uuids:
        return None
    for action in state.entity_actions:
        if action.action_category != "spell" or not action.can_afford:
            continue
        for target in action.valid_targets:
            if target.target_uuid in visible_enemy_uuids:
                return _execute(state, action, target, "cast_visible_enemy_spell")
    return None


def _move_toward_visible_enemy(state: ExternalAgentState) -> Optional[AgentCommand]:
    """Move closer to the nearest visible enemy."""
    if not state.visible_enemies or state.actor_position is None:
        return None
    nearest = state.visible_enemies[0]
    return _move_toward_position(state, nearest.position, "move_toward_visible_enemy")


def _open_adjacent_door(state: ExternalAgentState) -> Optional[AgentCommand]:
    """Select an available open-door action from any action bucket."""
    for action in state.all_actions:
        if not action.can_afford or not _is_open_door_action(action):
            continue
        target = action.valid_targets[0] if action.valid_targets else ExternalActionTarget(index=0)
        return _execute(state, action, target, "open_adjacent_door")
    return None


def _move_toward_closed_door(state: ExternalAgentState) -> Optional[AgentCommand]:
    """Move closer to the nearest known closed door when no enemy is visible."""
    if state.visible_enemies or state.actor_position is None:
        return None
    door = _nearest_closed_door(state)
    if door is None:
        return None
    return _move_toward_position(state, door.position, "move_toward_closed_door")


def _end_turn(state: ExternalAgentState) -> Optional[AgentCommand]:
    """End the active external AI turn."""
    if state.actor_uuid is None:
        return None
    return AgentCommand(
        command_type=AgentCommandType.END_TURN,
        entity_uuid=state.actor_uuid,
        reason="end_turn",
    )


def _move_toward_position(
    state: ExternalAgentState,
    target_position: Tuple[int, int],
    reason: str,
) -> Optional[AgentCommand]:
    """Select the movement row that most reduces Manhattan distance."""
    if state.actor_position is None:
        return None
    current_distance = _distance(state.actor_position, target_position)
    best: Optional[tuple[ExternalActionRow, ExternalActionTarget, int]] = None
    for action in state.position_actions:
        if action.action_category != "movement" or not action.can_afford:
            continue
        for target in action.valid_targets:
            if target.position is None:
                continue
            distance = _distance(target.position, target_position)
            if distance >= current_distance:
                continue
            if best is None or distance < best[2]:
                best = (action, target, distance)
    if best is None:
        return None
    return _execute(state, best[0], best[1], reason)


def _execute(
    state: ExternalAgentState,
    action: ExternalActionRow,
    target: ExternalActionTarget,
    reason: str,
) -> AgentCommand:
    """Build an execute command for one action-target row."""
    return AgentCommand(
        command_type=AgentCommandType.EXECUTE,
        entity_uuid=state.actor_uuid,
        template_name=action.template_name,
        target_index=target.index,
        reason=reason,
    )


def _nearest_closed_door(state: ExternalAgentState) -> Optional[ExternalKnownObject]:
    """Return the nearest known closed door to the actor."""
    if state.actor_position is None or not state.known_closed_doors:
        return None
    actor_position = state.actor_position
    return min(
        state.known_closed_doors,
        key=lambda door: _distance(actor_position, door.position),
    )


def _is_open_door_action(action: ExternalActionRow) -> bool:
    """Return whether an action row is an Open Door use action."""
    text = f"{action.template_name} {action.display_name}".lower()
    return "open door" in text


def _distance(origin: Tuple[int, int], target: Tuple[int, int]) -> int:
    """Return Manhattan grid distance."""
    return abs(origin[0] - target[0]) + abs(origin[1] - target[1])
