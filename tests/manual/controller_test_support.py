"""Test fixtures for exercising built-in turn controllers."""

from uuid import uuid4

from dnd.controller import Controller, TurnContext
from dnd.types.equipment import WeaponSlot
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.runtime_reset import reset_engine_runtime


def reset_controller_catalogue_state(width: int = 10, height: int = 8) -> None:
    """Clear global runtime state and create a rectangular controller arena.

    Args:
        width: Arena width in tiles.
        height: Arena height in tiles.
    """
    reset_engine_runtime(grid_size=(width, height))


def create_controller_pair(
    hero_position: tuple[int, int] = (1, 1),
    monster_position: tuple[int, int] = (2, 1),
) -> tuple[Entity, Entity]:
    """Create opposing combatants for controller examples.

    Args:
        hero_position: Starting position for the hero-side actor.
        monster_position: Starting position for the monster-side actor.

    Returns:
        Hero and monster entities with current senses.
    """
    hero = create_goblin(name="Controller Hero", position=hero_position, faction="heroes")
    monster = create_skeleton(
        name="Controller Skeleton",
        position=monster_position,
        faction="monsters",
    )
    Entity.update_all_entities_senses(max_distance=20)
    return hero, monster


def create_melee_only_skeleton(
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    """Create a skeleton whose available attacks are melee-only.

    Args:
        name: Entity display name.
        position: Starting grid position.
        faction: Faction identifier used for ally/enemy detection.

    Returns:
        Skeleton entity with its ranged weapon unequipped.
    """
    skeleton = create_skeleton(name=name, position=position, faction=faction)
    removed = skeleton.equipment.unequip(WeaponSlot.RANGED_MAIN)
    if removed is None:
        raise RuntimeError("Expected skeleton to start with a ranged weapon")
    if skeleton.get_action_template("Attack_RANGED_MAIN") is not None:
        raise RuntimeError("Expected ranged attack template to be removed")
    return skeleton


def start_ordered_controller_encounter(
    hero: Entity,
    monster: Entity,
    hero_controller: Controller,
    monster_controller: Controller,
    first_actor: Entity,
) -> Encounter:
    """Create an active encounter with a deterministic controller order.

    Args:
        hero: Hero-side combatant.
        monster: Monster-side combatant.
        hero_controller: Controller assigned to the hero.
        monster_controller: Controller assigned to the monster.
        first_actor: Actor whose turn should be first.

    Returns:
        Active encounter with a two-actor initiative order.
    """
    encounter = Encounter(name="Controller Catalogue", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, hero_controller)
    encounter.add_combatant(monster, monster_controller)
    encounter.roll_initiative()

    second_actor = monster if first_actor.uuid == hero.uuid else hero
    encounter.initiative_order = [first_actor.uuid, second_actor.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    return encounter


def make_turn_context(entity: Entity) -> TurnContext:
    """Build the narrow controller context used by direct examples.

    Args:
        entity: Actor whose turn context is being described.

    Returns:
        Turn context with current budgets and visible actor maps.
    """
    return TurnContext(
        source_entity_uuid=entity.uuid,
        entity_uuid=entity.uuid,
        actions_remaining=entity.action_economy.actions.normalized_score,
        bonus_actions_remaining=entity.action_economy.bonus_actions.normalized_score,
        reactions_remaining=entity.action_economy.reactions.normalized_score,
        movement_remaining=entity.action_economy.movement.normalized_score,
        visible_enemies=entity.get_visible_enemies(),
        visible_allies=entity.get_visible_allies(),
    )


def manhattan_distance(start: tuple[int, int], end: tuple[int, int]) -> int:
    """Return grid distance in cells for controller movement checks.

    Args:
        start: First grid position.
        end: Second grid position.

    Returns:
        Manhattan distance between positions.
    """
    return abs(start[0] - end[0]) + abs(start[1] - end[1])
