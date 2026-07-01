"""Training scene surfaces for the agent tactical interface manual."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from ai.agents.base import BaseAgent
from ai.models import TacticalState
from dnd.controller import Controller, PassController
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import AutoHitModifier, AutoHitStatus
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton


@dataclass(frozen=True)
class AgentTrainingScene:
    """Started encounter scene used by tactical-interface examples."""

    agent_actor: Entity
    target: Entity
    encounter: Encounter


class FirstAttackAgent(BaseAgent):
    """Agent that executes the first affordable attack against the nearest enemy."""

    actions_taken: int = 0

    def take_turn(self, state: TacticalState) -> None:
        """Pick one attack from the tactical snapshot and execute it.

        Args:
            state: Tactical snapshot for the controlled actor.
        """
        nearest = state.nearest_enemy()
        if nearest is None:
            return
        attack = state.find_attack_targeting(nearest.uuid)
        if attack is None:
            return
        result = self.iface.execute(
            self.entity_uuid,
            attack[0].template_name,
            attack[1].index,
        )
        if result.success:
            self.actions_taken += 1


def reset_agent_interface_state(width: int = 12, height: int = 8) -> None:
    """Clear global runtime state and create an agent training arena.

    Args:
        width: Arena width in tiles.
        height: Arena height in tiles.
    """
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)


def create_agent_scene(
    agent_position: tuple[int, int] = (2, 2),
    target_position: tuple[int, int] = (3, 2),
) -> AgentTrainingScene:
    """Create a started encounter where the agent actor has the current turn.

    Args:
        agent_position: Starting position for the controlled actor.
        target_position: Starting position for the visible enemy.

    Returns:
        Scene containing the agent actor, target, and active encounter.
    """
    reset_agent_interface_state()
    agent_actor = create_skeleton(
        name="Agent Skeleton",
        position=agent_position,
        faction="monsters",
    )
    target = create_goblin(
        name="Training Hero",
        position=target_position,
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)

    encounter = Encounter(name="Agent Interface Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(agent_actor, PassController(source_entity_uuid=agent_actor.uuid))
    encounter.add_combatant(target, PassController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [agent_actor.uuid, target.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    return AgentTrainingScene(
        agent_actor=agent_actor,
        target=target,
        encounter=encounter,
    )


def make_melee_attack_auto_hit(entity: Entity) -> UUID:
    """Add an explicit auto-hit modifier to the entity's melee attack bonus.

    Args:
        entity: Attacking entity.

    Returns:
        UUID of the temporary attack modifier.
    """
    modifier = AutoHitModifier(
        name="Agent Interface Auto Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return entity.equipment.melee_attack_bonus.self_static.add_auto_hit_modifier(modifier)


def clear_melee_attack_modifier(entity: Entity, modifier_uuid: UUID) -> None:
    """Remove an explicit melee attack modifier from an entity.

    Args:
        entity: Entity whose attack bonus was modified.
        modifier_uuid: UUID returned by `make_melee_attack_auto_hit`.
    """
    entity.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)
