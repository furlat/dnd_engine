"""Training scenes for agent decision-pattern examples."""

from dataclasses import dataclass
from uuid import uuid4

from dnd.controller import PassController
from dnd.core.events import WeaponSlot
from dnd.core.modifiers import DamageType
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.scenarios.agent_tactical_training import (
    reset_agent_interface_state,
)


@dataclass(frozen=True)
class DecisionScene:
    """Started one-target encounter used by decision-pattern examples."""

    agent_actor: Entity
    target: Entity
    encounter: Encounter


@dataclass(frozen=True)
class TwoTargetDecisionScene:
    """Started two-target encounter used by utility-scoring examples."""

    agent_actor: Entity
    weak_target: Entity
    sturdy_target: Entity
    encounter: Encounter


def create_melee_only_skeleton(
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    """Create a skeleton whose agent decisions use melee attacks only.

    Args:
        name: Entity display name.
        position: Starting grid position.
        faction: Faction identifier used for ally/enemy detection.

    Returns:
        Skeleton entity with its ranged weapon unequipped.

    Raises:
        RuntimeError: If the skeleton does not expose the expected ranged gear.
    """
    skeleton = create_skeleton(name=name, position=position, faction=faction)
    removed = skeleton.equipment.unequip(WeaponSlot.RANGED_MAIN)
    if removed is None:
        raise RuntimeError("Expected skeleton to start with a ranged weapon")
    if skeleton.get_action_template("Attack_RANGED_MAIN") is not None:
        raise RuntimeError("Expected ranged attack template to be removed")
    return skeleton


def create_decision_scene(
    agent_position: tuple[int, int] = (2, 2),
    target_position: tuple[int, int] = (3, 2),
) -> DecisionScene:
    """Create a started encounter for one agent and one target.

    Args:
        agent_position: Starting position for the controlled actor.
        target_position: Starting position for the visible enemy.

    Returns:
        Scene containing the agent actor, target, and active encounter.
    """
    reset_agent_interface_state()
    agent_actor = create_melee_only_skeleton(
        name="Decision Skeleton",
        position=agent_position,
        faction="monsters",
    )
    target = create_goblin(
        name="Decision Hero",
        position=target_position,
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)

    encounter = Encounter(name="Agent Decision Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(agent_actor, PassController(source_entity_uuid=agent_actor.uuid))
    encounter.add_combatant(target, PassController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [agent_actor.uuid, target.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    return DecisionScene(
        agent_actor=agent_actor,
        target=target,
        encounter=encounter,
    )


def create_two_target_scene() -> TwoTargetDecisionScene:
    """Create a started encounter with two adjacent enemy targets.

    Returns:
        Scene containing the agent actor, wounded target, sturdy target, and
        active encounter.
    """
    reset_agent_interface_state()
    agent_actor = create_melee_only_skeleton(
        name="Decision Skeleton",
        position=(2, 2),
        faction="monsters",
    )
    weak_target = create_goblin(
        name="Wounded Hero",
        position=(3, 2),
        faction="heroes",
    )
    sturdy_target = create_goblin(
        name="Sturdy Hero",
        position=(2, 3),
        faction="heroes",
    )
    weak_target.health.take_damage(3, DamageType.FORCE, agent_actor.uuid)
    Entity.update_all_entities_senses(max_distance=20)

    encounter = Encounter(name="Agent Utility Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(agent_actor, PassController(source_entity_uuid=agent_actor.uuid))
    encounter.add_combatant(weak_target, PassController(source_entity_uuid=weak_target.uuid))
    encounter.add_combatant(sturdy_target, PassController(source_entity_uuid=sturdy_target.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [agent_actor.uuid, weak_target.uuid, sturdy_target.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    return TwoTargetDecisionScene(
        agent_actor=agent_actor,
        weak_target=weak_target,
        sturdy_target=sturdy_target,
        encounter=encounter,
    )
