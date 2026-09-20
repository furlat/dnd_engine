"""Native location and effect operations respect authored occupancy layers."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.core.modifiers import ResistanceStatus
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import (
    ElectrifiedWater,
    FireSurface,
    WetSurface,
    materialize_spike_trap_condition,
)
from dnd.types.traps import TrapState
from dnd.types.world import OccupancyLayer


@pytest.fixture
def occupant() -> Iterator[Entity]:
    reset_engine_runtime(grid_size=(4, 3))
    game = Game()
    entity = Entity.create(uuid4(), "Layer traveler", config=EntityConfig(
        position=(0, 1),
        health=HealthConfig(hit_dices=[
            HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums"),
        ]),
    ))
    entity.compose_entity()
    game.deploy_entity(entity, entity.position)
    try:
        yield entity
    finally:
        game.close()
        reset_engine_runtime()


def cause(entity: Entity) -> Event:
    return Event(
        name="Native spatial operation", event_type=EventType.BASE_ACTION,
        phase=EventPhase.EFFECT, source_entity_uuid=entity.uuid,
    )


def test_ground_crossing_does_not_consume_air_entry_allowance(occupant: Entity) -> None:
    """An excluded entry neither wets nor consumes this turn's eligible damage."""
    field = ElectrifiedWater(
        source_entity_uuid=occupant.uuid,
        position=(1, 1), affected_positions={(1, 1)},
        affected_occupancy_layers=frozenset({OccupancyLayer.AIR}),
    )
    field.activate(parent_event=cause(occupant))
    hp = occupant.get_hp()
    turn = EventQueue.begin_turn_execution()
    try:
        operation = cause(occupant)
        Entity.update_entity_position(occupant, (1, 1), parent_event=operation.uuid)
        assert occupant.get_hp() == hp
        assert "Wet" not in occupant.active_conditions
        with fixed_dice_faces(1):
            Entity.update_entity_position(
                occupant, (1, 1), occupancy_layer=OccupancyLayer.AIR,
                parent_event=operation.uuid,
            )
        assert occupant.get_hp() == hp - 2
        assert "Wet" in occupant.active_conditions
        Entity.update_entity_position(
            occupant, (1, 1), occupancy_layer=OccupancyLayer.GROUND,
            parent_event=operation.uuid,
        )
        assert "Wet" not in occupant.active_conditions
        Entity.update_entity_position(
            occupant, (1, 1), occupancy_layer=OccupancyLayer.AIR,
            parent_event=operation.uuid,
        )
        assert "Wet" in occupant.active_conditions
        assert occupant.get_hp() == hp - 2
    finally:
        EventQueue.end_turn_execution(turn)
    next_turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(1):
            occupant.on_turn_start(round_number=2)
        assert occupant.get_hp() == hp - 4
    finally:
        EventQueue.end_turn_execution(next_turn)


@pytest.mark.parametrize("includes_ground", (False, True))
def test_same_cell_landing_preserves_only_compatible_membership(
    occupant: Entity, includes_ground: bool,
) -> None:
    operation = cause(occupant)
    Entity.update_entity_position(
        occupant, occupant.position, occupancy_layer=OccupancyLayer.AIR,
        parent_event=operation.uuid,
    )
    layers = {OccupancyLayer.AIR}
    if includes_ground:
        layers.add(OccupancyLayer.GROUND)
    field = WetSurface(
        source_entity_uuid=occupant.uuid, position=occupant.position,
        affected_positions={occupant.position},
        affected_occupancy_layers=frozenset(layers),
    )
    field.activate(parent_event=operation)
    wet = occupant.active_conditions["Wet"]
    Entity.update_entity_position(
        occupant, occupant.position, occupancy_layer=OccupancyLayer.GROUND,
        parent_event=operation.uuid,
    )
    assert ("Wet" in occupant.active_conditions) is includes_ground
    assert occupant.health.get_resistance(DamageType.FIRE) is (
        ResistanceStatus.RESISTANCE if includes_ground else ResistanceStatus.NONE
    )
    Entity.update_entity_position(
        occupant, occupant.position, occupancy_layer=OccupancyLayer.AIR,
        parent_event=operation.uuid,
    )
    assert "Wet" in occupant.active_conditions
    assert (occupant.active_conditions["Wet"].uuid == wet.uuid) is includes_ground


@pytest.mark.parametrize("layer", (OccupancyLayer.GROUND, OccupancyLayer.AIR))
@pytest.mark.parametrize("appears_on_occupant", (False, True), ids=("moving-field", "appearance"))
def test_air_field_occupant_paths_admit_only_air(
    occupant: Entity, layer: OccupancyLayer, appears_on_occupant: bool,
) -> None:
    operation = cause(occupant)
    Entity.update_entity_position(
        occupant, occupant.position, occupancy_layer=layer, parent_event=operation.uuid,
    )
    field_position = occupant.position if appears_on_occupant else (1, 1)
    field = WetSurface(
        source_entity_uuid=occupant.uuid, position=field_position,
        affected_positions={field_position},
        affected_occupancy_layers=frozenset({OccupancyLayer.AIR}),
    )
    field.activate(parent_event=operation)
    if not appears_on_occupant:
        assert "Wet" not in occupant.active_conditions
        field.change_footprint({occupant.position}, parent_event=operation)
    assert ("Wet" in occupant.active_conditions) is (layer is OccupancyLayer.AIR)
    field.change_footprint({(2, 1)}, parent_event=operation)
    assert "Wet" not in occupant.active_conditions


def test_all_layer_damage_keeps_horizontal_and_periodic_cadence(occupant: Entity) -> None:
    operation = cause(occupant)
    field = FireSurface(
        source_entity_uuid=occupant.uuid, position=(0, 1),
        affected_positions={(0, 1), (1, 1)},
    )
    field.activate(parent_event=operation)
    hp = occupant.get_hp()
    Entity.update_entity_position(
        occupant, occupant.position, occupancy_layer=OccupancyLayer.AIR,
        parent_event=operation.uuid,
    )
    assert occupant.get_hp() == hp
    with fixed_dice_faces(1, 1):
        Entity.update_entity_position(occupant, (1, 1), parent_event=operation.uuid)
    assert occupant.get_hp() == hp - 2
    with fixed_dice_faces(1, 1):
        occupant.on_turn_start(round_number=1)
    assert occupant.get_hp() == hp - 4
    Entity.update_entity_position(
        occupant, occupant.position, occupancy_layer=OccupancyLayer.GROUND,
        parent_event=operation.uuid,
    )
    assert occupant.get_hp() == hp - 4


def test_raised_spikes_ignore_airborne_occupant_until_ground_contact(occupant: Entity) -> None:
    operation = cause(occupant)
    Entity.update_entity_position(
        occupant, occupant.position, occupancy_layer=OccupancyLayer.AIR,
        parent_event=operation.uuid,
    )
    trap = materialize_spike_trap_condition(
        {occupant.position}, trap_state=TrapState.DEACTIVATED,
    )
    hp = occupant.get_hp()
    assert trap.set_trap_state(TrapState.ACTIVATED, parent_event=operation)
    assert occupant.get_hp() == hp
    with fixed_dice_faces(1, 1):
        Entity.update_entity_position(
            occupant, occupant.position, occupancy_layer=OccupancyLayer.GROUND,
            parent_event=operation.uuid,
        )
    assert occupant.get_hp() == hp - 2


@pytest.mark.parametrize("current_layer", (OccupancyLayer.GROUND, OccupancyLayer.AIR))
def test_explicit_hazard_layer_and_observation_keep_distinct_meanings(
    occupant: Entity, current_layer: OccupancyLayer,
) -> None:
    operation = cause(occupant)
    Entity.update_entity_position(
        occupant, occupant.position, occupancy_layer=current_layer,
        parent_event=operation.uuid,
    )
    materialize_spike_trap_condition({(1, 1)})
    field = FireSurface(
        source_entity_uuid=occupant.uuid, position=(2, 1),
        affected_positions={(2, 1)},
        affected_occupancy_layers=frozenset({OccupancyLayer.AIR}),
    )
    field.activate(parent_event=operation)
    occupant.update_entity_senses()
    grid = get_map()
    assert {
        (position, layer): grid.is_position_hazardous_for(
            *position, occupant.uuid, occupancy_layer=layer,
        )
        for position in ((1, 1), (2, 1))
        for layer in (OccupancyLayer.GROUND, OccupancyLayer.AIR)
    } == {
        ((1, 1), OccupancyLayer.GROUND): True,
        ((1, 1), OccupancyLayer.AIR): False,
        ((2, 1), OccupancyLayer.GROUND): False,
        ((2, 1), OccupancyLayer.AIR): True,
    }
    assert not grid.is_walkable_for(1, 1, occupant.uuid, walk_in_danger=False)
    assert grid.is_walkable_for(2, 1, occupant.uuid, walk_in_danger=False)
    assert occupant.senses.hazardous_cells[(1, 1)] is True
    assert occupant.senses.hazardous_cells[(2, 1)] is False
