"""Deterministic spike-zone movement regressions displaced by d80."""

from unittest.mock import patch

from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.life_types import LifeState
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.spatial.environmental_conditions import (
    materialize_spike_trap_condition,
)
from tests.engine.support import get_hp, reset_combat_state, set_hp

def test_spike_zone_activation_and_deactivation_are_one_shared_hazard() -> None:
    """One shared handler and tile markers activate and retire atomically."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 8)
    positions = {(2, 4), (3, 4), (4, 4)}
    condition = materialize_spike_trap_condition(positions)
    tiles = [grid.get_tile(*position) for position in sorted(positions)]
    assert all(tile is not None for tile in tiles)
    handler_uuid = condition.spatial_handler_uuids[0]
    observer = create_skeleton(
        name="Spike Hazard Observer",
        position=(0, 4),
    )

    assert {tile.position for tile in tiles} == positions
    assert all(tile.name == "Floor" for tile in tiles)
    assert all(condition.uuid in tile.get_conditions() for tile in tiles)
    assert all(
        tile.get_conditions()[condition.uuid].hazard_filter is not None
        for tile in tiles
    )
    assert all(
        grid.is_position_hazardous_for(*position, observer.uuid)
        for position in positions
    )
    assert all(
        handler_uuid
        in {
            candidate.uuid
            for candidate in EventQueue.get_spatial_handlers_at(position)
        }
        for position in positions
    )

    condition.deactivate(parent_event=Event(
        name="Deactivate Spike Trap",
        source_entity_uuid=condition.source_entity_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.EFFECT,
    ))

    assert all(condition.uuid not in tile.get_conditions() for tile in tiles)
    assert all(
        not grid.is_position_hazardous_for(*position, observer.uuid)
        for position in positions
    )
    assert all(
        handler_uuid
        not in {
            candidate.uuid
            for candidate in EventQueue.get_spatial_handlers_at(position)
        }
        for position in positions
    )


def test_spike_zone_applies_damage_for_each_committed_entry() -> None:
    """Each objective entry resolves the network's one shared handler."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 8)
    materialize_spike_trap_condition({(2, 4), (3, 4), (4, 4)})
    walker = create_skeleton(
        name="Spike Step Walker",
        position=(0, 4),
    )
    hp_before = get_hp(walker)

    with patch("dnd.core.dice.random.randint", return_value=2):
        Entity.update_entity_position(walker, (2, 4))
        Entity.update_entity_position(walker, (3, 4))
        Entity.update_entity_position(walker, (4, 4))

    assert walker.position == (4, 4)
    assert hp_before - get_hp(walker) == 12
    damage_logs = [
        event.combat_log
        for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == walker.uuid
        and event.combat_log is not None
    ]
    assert len(damage_logs) == 3


def test_lethal_spike_entry_commits_canonical_life_state() -> None:
    """Lethal entry commits canonical death rather than a Dead condition."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 8)
    materialize_spike_trap_condition({(2, 4), (3, 4), (4, 4)})
    walker = create_skeleton(
        name="Lethal Spike Walker",
        position=(0, 4),
    )
    set_hp(walker, 2)

    with patch("dnd.core.dice.random.randint", return_value=4):
        Entity.update_entity_position(walker, (2, 4))

    assert walker.position == (2, 4)
    assert walker.health.life_state is LifeState.DEAD
    assert "Dead" not in walker.active_conditions
