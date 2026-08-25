"""Executable contract for the engine-wide runtime reset boundary."""
from dnd.types.materials import Material, TileSurface

from typing import Any, cast
from uuid import uuid4

from dnd.encounters.controllers import Controller
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.events.events_registry import (
    EventQueue,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.core.values import BaseValue
from dnd.encounters.encounter import Encounter
from dnd.entities.entity import Entity
from dnd.runtime_reset import reset_engine_runtime


def test_reset_engine_runtime_clears_every_engine_registry_and_rebuilds_grid() -> None:
    """One authoritative operation resets all shared engine state."""
    marker_uuid = uuid4()
    marker = cast(Any, object())
    BaseObject._registry[marker_uuid] = marker
    BaseBlock._registry[marker_uuid] = marker
    BaseValue._registry[marker_uuid] = marker
    Entity._entity_registry[marker_uuid] = marker
    Controller._controller_registry[marker_uuid] = marker
    Encounter._encounter_registry[marker_uuid] = marker
    Encounter._active_encounter = marker
    Encounter._combat_log_listeners.append(marker)
    SpellProtectionRegistry._protections.append(marker)
    EventQueue._combat_log_callback = marker
    EventQueue._all_events.append(marker)

    GridMap.reset()
    old_grid = get_map()
    old_grid.create_rectangle(0, 0, 2, 2, surface=TileSurface(base_material=Material.STONE))

    new_grid = reset_engine_runtime(grid_size=(4, 3))

    assert new_grid is get_map()
    assert new_grid is not old_grid
    assert new_grid.tile_count() == 12
    # Building tiles legitimately registers their blocks, values, and
    # modifiers; the pre-reset marker must not survive that reconstruction.
    assert marker_uuid not in BaseObject._registry
    assert marker_uuid not in BaseBlock._registry
    assert marker_uuid not in BaseValue._registry
    assert Entity._entity_registry == {}
    assert Controller._controller_registry == {}
    assert Encounter._encounter_registry == {}
    assert Encounter._active_encounter is None
    assert Encounter._combat_log_listeners == []
    assert SpellProtectionRegistry._protections == []
    assert EventQueue._all_events == []
    assert EventQueue._combat_log_callback is None


def test_reset_engine_runtime_can_leave_the_new_grid_empty() -> None:
    """Callers that construct bespoke maps can request an empty singleton."""
    grid = reset_engine_runtime()

    assert grid is get_map()
    assert grid.get_all_tiles() == {}
    assert BaseObject._registry == {}
    assert BaseBlock._registry == {}
    assert BaseValue._registry == {}
