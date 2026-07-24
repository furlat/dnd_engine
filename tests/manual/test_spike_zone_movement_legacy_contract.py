"""Deterministic spike-zone movement regressions displaced by d80."""

from unittest.mock import patch

from dnd.actions_functional import execute_action, get_available_actions
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.tiles import create_spike_zone, deactivate_spike_zone
from dnd.utils import get_hp, reset_combat_state, set_hp


def _move_target(entity: Entity, position: tuple[int, int]):
    actions = get_available_actions(entity)
    move = next(
        action
        for action in actions.position_actions
        if action.template_name == "Move"
    )
    return next(target for target in move.valid_targets if target.position == position)


def _walk_log_tree(entry: CombatLogEntry):
    yield entry
    for child in entry.sub_entries:
        yield from _walk_log_tree(child)


def test_spike_zone_activation_and_deactivation_are_one_shared_hazard() -> None:
    """One shared handler and tile markers activate and retire atomically."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 8)
    positions = {(2, 4), (3, 4), (4, 4)}
    tiles, handler = create_spike_zone(positions)
    for tile in tiles:
        grid.set_tile(*tile.position, tile=tile, fire_event=False)
    observer = create_skeleton(
        name="Spike Hazard Observer",
        position=(0, 4),
    )

    assert {tile.position for tile in tiles} == positions
    assert all(tile.name == "Floor" for tile in tiles)
    assert all("Spike Trap" in tile.active_conditions for tile in tiles)
    assert all(
        tile.active_conditions["Spike Trap"].hazard_filter is not None
        for tile in tiles
    )
    assert all(
        grid.is_position_hazardous_for(*position, observer.uuid)
        for position in positions
    )
    assert all(
        handler.uuid
        in {
            candidate.uuid
            for candidate in EventQueue.get_spatial_handlers_at(position)
        }
        for position in positions
    )

    deactivate_spike_zone(tiles, handler)

    assert all("Spike Trap" not in tile.active_conditions for tile in tiles)
    assert all(
        not grid.is_position_hazardous_for(*position, observer.uuid)
        for position in positions
    )
    assert all(
        handler.uuid
        not in {
            candidate.uuid
            for candidate in EventQueue.get_spatial_handlers_at(position)
        }
        for position in positions
    )


def test_spike_zone_applies_damage_for_each_committed_step() -> None:
    """A multi-cell traversal resolves the shared spatial handler per entry."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 8)
    create_spike_zone({(2, 4), (3, 4), (4, 4)})
    walker = create_skeleton(
        name="Spike Step Walker",
        position=(0, 4),
    )
    Entity.update_all_entities_senses()
    hp_before = get_hp(walker)

    with patch("dnd.tiles.random.randint", return_value=2):
        result = execute_action(
            walker,
            "Move",
            _move_target(walker, (5, 4)),
        )

    assert result is not None
    assert not result.canceled
    assert walker.position == (5, 4)
    assert hp_before - get_hp(walker) == 12
    assert not walker.senses._paths_dirty
    assert result.combat_log is not None
    assert sum(
        entry.entry_type is CombatLogEntryType.DAMAGE_TAKEN
        for entry in _walk_log_tree(result.combat_log)
    ) == 3


def test_lethal_spike_step_stops_remaining_movement_with_life_state() -> None:
    """Lethal entry stops the path and commits canonical death, not a Dead condition."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 8)
    create_spike_zone({(2, 4), (3, 4), (4, 4)})
    walker = create_skeleton(
        name="Lethal Spike Walker",
        position=(0, 4),
    )
    set_hp(walker, 2)
    Entity.update_all_entities_senses()

    with patch("dnd.tiles.random.randint", return_value=4):
        result = execute_action(
            walker,
            "Move",
            _move_target(walker, (5, 4)),
        )

    assert result is not None
    assert not result.canceled
    assert walker.position == (2, 4)
    assert walker.health.life_state is LifeState.DEAD
    assert "Dead" not in walker.active_conditions
    assert not walker.senses._paths_dirty
