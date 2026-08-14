"""Authoritative reset operation for shared in-process engine state."""

from typing import Optional

from dnd.controller import Controller
from dnd.content_system.creature_bindings import CREATURE_RUNTIME_BINDINGS
from dnd.content_system.item_bindings import ITEM_RUNTIME_BINDINGS
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.dice import Dice, DiceRoll
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.spatial_effects import SpatialEffect


def reset_engine_runtime(
    *,
    grid_size: Optional[tuple[int, int]] = None,
) -> GridMap:
    """Clear every engine-owned global registry and create a fresh grid.

    Server-specific streams, sessions, and simulation state remain the
    responsibility of their owning server components. Callers may pass a
    ``(width, height)`` pair when they want this operation to build the base
    rectangular map as part of the reset.

    Args:
        grid_size: Optional positive rectangular grid dimensions.

    Returns:
        The fresh global :class:`GridMap` singleton.

    Raises:
        ValueError: If either requested grid dimension is not positive.
    """
    if grid_size is not None and any(dimension <= 0 for dimension in grid_size):
        raise ValueError("grid dimensions must be positive")

    # Event systems reset first so registered systems can discard references
    # to live entities before their owning registries are cleared.
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    SpellProtectionRegistry.reset()

    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    Dice._registry.clear()
    DiceRoll._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    SpatialEffect._effect_registry.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    CREATURE_RUNTIME_BINDINGS.reset()
    ITEM_RUNTIME_BINDINGS.reset()

    GridMap.reset()
    grid = get_map()
    if grid_size is not None:
        grid.create_rectangle(0, 0, *grid_size)
    return grid


__all__ = ["reset_engine_runtime"]
