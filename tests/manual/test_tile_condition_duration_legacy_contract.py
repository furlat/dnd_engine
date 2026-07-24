"""Tile-owned duration and encounter environment-step regressions."""

from uuid import uuid4

from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.utils import reset_combat_state, setup_combat_arena


class TileDurationProbe(BaseCondition):
    name: str = "Tile Duration Probe"


class EntityDurationProbe(BaseCondition):
    name: str = "Entity Duration Probe"


def _duration(rounds: int, source_uuid, target_uuid) -> Duration:
    return Duration(
        duration=rounds,
        duration_type=DurationType.ROUNDS,
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
    )


def test_tile_duration_expiry_removes_owned_cross_block_effect() -> None:
    """Tiles use BaseBlock duration and linked-condition cleanup unchanged."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 8, 8)
    target = create_skeleton(
        name="Tile Duration Target",
        position=(3, 3),
    )
    tile = grid.get_tile(3, 3)
    assert tile is not None
    source_uuid = uuid4()
    tile_effect = TileDurationProbe(
        source_entity_uuid=source_uuid,
        target_entity_uuid=tile.uuid,
        duration=_duration(2, source_uuid, tile.uuid),
    )
    target_effect = EntityDurationProbe(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target.uuid,
    )
    tile.add_condition(tile_effect)
    target.add_condition(target_effect)
    tile_effect.add_linked_condition(target.uuid, target_effect.uuid)

    assert not tile.advance_duration(tile_effect.name)
    assert tile_effect.name in tile.active_conditions
    assert target_effect.name in target.active_conditions

    assert tile.advance_duration(tile_effect.name)
    assert tile_effect.name not in tile.active_conditions
    assert target_effect.name not in target.active_conditions


def test_encounter_round_boundary_advances_tile_durations() -> None:
    """The environment step advances each tile exactly once per completed round."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 8, 8)
    first = create_skeleton(
        name="Tile Duration First",
        position=(0, 0),
        faction="first",
    )
    second = create_skeleton(
        name="Tile Duration Second",
        position=(1, 0),
        faction="second",
    )
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(first, second)
    tile = grid.get_tile(5, 5)
    assert tile is not None
    source_uuid = uuid4()
    tile_effect = TileDurationProbe(
        source_entity_uuid=source_uuid,
        target_entity_uuid=tile.uuid,
        duration=_duration(2, source_uuid, tile.uuid),
    )
    tile.add_condition(tile_effect)
    encounter.start_encounter()

    encounter.start_turn()
    encounter.end_turn()
    encounter.next_turn()
    encounter.end_turn()
    encounter.next_turn()

    assert tile_effect.name in tile.active_conditions

    encounter.end_turn()
    encounter.next_turn()
    encounter.end_turn()
    encounter.next_turn()

    assert tile_effect.name not in tile.active_conditions
