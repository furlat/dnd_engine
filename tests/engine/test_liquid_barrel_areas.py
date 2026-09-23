"""Authored barrels spill onto connected surrounding floor through real attacks."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import AttackObject, Jump
from dnd.blocks.base_item import BaseItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_door, build_directional_wall
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventPhase, EventQueue, SavingThrowEvent, SpatialEffectInteractionEvent
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import FireSurface, OilSurface, SteamCloud, WetSurface
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from dnd.types.world import CardinalDirection
from tests.engine.test_liquid_barrels import CONTENTS, actor, completed, walk


AREA = {(x, y) for x in range(2, 5) for y in range(2, 5)}


@pytest.fixture
def world() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(7, 7))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def barrel_and_attacker(world: Game, contents: str, *, position: tuple[int, int] = (3, 3)) -> tuple[BaseItem, Entity]:
    attacker = actor(world, (position[0], position[1] - 1) if position[1] else (position[0], 1))
    barrel = build_authored_item(f"environment.blocker.{contents}_barrel", attacker.uuid)
    barrel.place_on_grid(position)
    return barrel, attacker


def break_barrel(barrel: BaseItem, attacker: Entity) -> Event:
    with fixed_dice_faces(8, *([20] * 10)):
        result = AttackObject(source_entity_uuid=attacker.uuid, target_entity_uuid=barrel.uuid).apply()
    assert result is not None and not result.canceled
    assert barrel.integrity is ItemIntegrity.DESTROYED
    return result


def material_cells() -> set[tuple[int, int]]:
    grid = get_map()
    return {(x, y) for x in range(7) for y in range(7)
            if grid.get_spatial_conditions_at((x, y))
            or (tile := grid.get_tile(x, y)) is not None and tile.to_world_tile_state().residues}


@pytest.mark.parametrize("contents", CONTENTS)
def test_every_authored_barrel_spills_nine_cells_including_grounded_occupants(world: Game, contents: str) -> None:
    barrel, attacker = barrel_and_attacker(world, contents)
    nearby = actor(world, (4, 4))
    hp = nearby.get_hp()
    break_barrel(barrel, attacker)
    assert material_cells() == AREA
    if contents in {"oil", "water", "grease"}:
        owner, = get_map().get_spatial_conditions()
        assert owner.affected_positions == AREA
    if contents == "water":
        assert "Wet" in nearby.active_conditions and "Wet" in attacker.active_conditions
    if contents in {"poison", "dread_blood"}:
        # Existing residue deposition is inert; no fabricated entry event.
        assert nearby.get_hp() == hp and "Frightened" not in nearby.active_conditions
    if contents == "blood":
        assert all(get_map().get_tile(*position).to_world_tile_state().residues[0].amount == 5
                   for position in AREA)


@pytest.mark.parametrize("opened", (False, True))
def test_closed_wall_and_door_constrain_spill_but_open_door_connects_floor(world: Game, opened: bool) -> None:
    for y in (2, 4):
        wall = build_directional_wall()
        wall.place_on_grid((3, y), boundary_direction=CardinalDirection.EAST)
    door = build_directional_door(is_open=opened)
    door.place_on_grid((3, 3), boundary_direction=CardinalDirection.EAST)
    barrel, attacker = barrel_and_attacker(world, "oil")
    break_barrel(barrel, attacker)
    assert material_cells() == (AREA if opened else {position for position in AREA if position[0] <= 3})


def test_unsupported_raised_and_solid_cells_block_spill_and_diagonal_tunneling(world: Game) -> None:
    grid = get_map()
    grid.set_tile_elevation((3, 4), height=1, surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    solid = BaseItem(source_entity_uuid=uuid4(), item_id="test.solid_prop", name="Solid prop",
                     blocks_movement=True, blocks_propagation_field=False)
    solid.place_on_grid((4, 3))
    grid.remove_tile(2, 2)
    barrel, attacker = barrel_and_attacker(world, "oil")
    break_barrel(barrel, attacker)
    assert material_cells() == AREA - {(3, 4), (4, 3), (4, 4), (2, 2)}


def test_map_edge_clips_real_floor_without_inventing_supports(world: Game) -> None:
    barrel, attacker = barrel_and_attacker(world, "water", position=(0, 0))
    break_barrel(barrel, attacker)
    assert material_cells() == {(0, 0), (1, 0), (0, 1), (1, 1)}


@pytest.mark.parametrize("all_occupied", (False, True))
def test_incompatible_ground_material_is_preserved_without_aborting_destruction(world: Game, all_occupied: bool) -> None:
    barrel, attacker = barrel_and_attacker(world, "oil")
    prior = AREA if all_occupied else {(3, 3), (4, 3)}
    water = WetSurface(source_entity_uuid=attacker.uuid, position=(3, 3), affected_positions=prior)
    water.activate(parent_event=completed(0)[-1])
    break_barrel(barrel, attacker)
    assert water.affected_positions == prior and water.applied
    oil = [condition for condition in get_map().get_spatial_conditions() if isinstance(condition, OilSurface)]
    assert len(oil) == int(not all_occupied)
    if oil:
        assert oil[0].affected_positions == AREA - prior


def test_fire_break_ignites_every_admitted_cell_and_preserves_incompatible_water(world: Game) -> None:
    barrel, attacker = barrel_and_attacker(world, "oil")
    water = WetSurface(source_entity_uuid=attacker.uuid, position=(4, 3), affected_positions={(4, 3)})
    water.activate(parent_event=completed(0)[-1])
    barrel.receive_damage(12, DamageType.FIRE, attacker.uuid)
    fire, = [condition for condition in get_map().get_spatial_conditions() if isinstance(condition, FireSurface)]
    assert fire.affected_positions == AREA - {(4, 3)}
    assert water.applied and water.affected_positions == {(4, 3)}
    assert not any(isinstance(condition, OilSurface) for condition in get_map().get_spatial_conditions())


def test_partial_ignition_and_dousing_keep_materials_on_their_actual_cells(world: Game) -> None:
    barrel, attacker = barrel_and_attacker(world, "oil")
    break_barrel(barrel, attacker)
    selected = {(4, y) for y in range(2, 5)}
    event = SpatialEffectInteractionEvent(source_entity_uuid=attacker.uuid,
        operation=SpatialEffectInteractionOperation.IGNITE, positions=tuple(sorted(selected)))
    event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
    oil, = [condition for condition in get_map().get_spatial_conditions() if isinstance(condition, OilSurface)]
    fire, = [condition for condition in get_map().get_spatial_conditions() if isinstance(condition, FireSurface)]
    assert oil.affected_positions == AREA - selected and fire.affected_positions == selected
    event = SpatialEffectInteractionEvent(source_entity_uuid=attacker.uuid,
        operation=SpatialEffectInteractionOperation.DOUSE, positions=((4, 3),))
    event.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
    assert oil.affected_positions == AREA - selected and fire.affected_positions == {(4, 2), (4, 4)}


@pytest.mark.parametrize("contents", ("oil", "water", "grease", "poison", "blood"))
def test_outer_cells_have_real_effects_and_jump_can_clear_or_land_on_area(world: Game, contents: str) -> None:
    barrel, attacker = barrel_and_attacker(world, contents)
    traveler = actor(world, (1, 4))
    break_barrel(barrel, attacker)
    hp = traveler.get_hp()
    cursor = EventQueue.event_cursor()
    jump = Jump(source_entity_uuid=traveler.uuid, end_position=(5, 4)).apply()
    assert jump is not None and not jump.canceled
    assert traveler.get_hp() == hp and not {"Wet", "Prone"}.intersection(traveler.active_conditions)
    assert not any(isinstance(event, SavingThrowEvent) for event in completed(cursor))
    traveler.on_turn_end(round_number=1, turn_index=0)
    traveler.on_turn_start(round_number=2, turn_index=0)
    # Spend enough movement first to preserve the engine's normal immediate
    # stand policy while making a failed landing retain Prone for this case.
    if contents == "grease":
        walk(traveler, [(5, 4), (5, 5), (6, 5)])
        walk(traveler, [(6, 5), (6, 4), (5, 4)])
    with fixed_dice_faces(2):
        landing = Jump(source_entity_uuid=traveler.uuid, end_position=(4, 4)).apply()
    assert landing is not None and not landing.canceled
    assert traveler.position == (4, 4)
    assert traveler.get_hp() == hp - (2 if contents == "poison" else 0)
    assert ("Wet" in traveler.active_conditions) is (contents == "water")
    assert ("Prone" in traveler.active_conditions) is (contents == "grease")


def test_grease_appearance_reaches_adjacent_grounded_attacker_with_no_caster_exemption(world: Game) -> None:
    barrel, attacker = barrel_and_attacker(world, "grease")
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(8, 1):
        result = AttackObject(source_entity_uuid=attacker.uuid, target_entity_uuid=barrel.uuid).apply()
    assert result is not None and not result.canceled
    assert "Prone" in attacker.active_conditions
    save, = [event for event in completed(cursor) if isinstance(event, SavingThrowEvent)]
    assert save.result is False


def test_water_appearance_and_exit_do_not_clear_another_wet_owner(world: Game) -> None:
    barrel, attacker = barrel_and_attacker(world, "water")
    traveler = actor(world, (4, 4))
    cause = break_barrel(barrel, attacker)
    assert "Wet" in traveler.active_conditions
    cloud = SteamCloud(source_entity_uuid=attacker.uuid, position=(5, 4), affected_positions={(5, 4)})
    cloud.activate(parent_event=cause)
    walk(traveler, [(4, 4), (5, 4)])
    assert "Wet" in traveler.active_conditions
    cloud.deactivate(parent_event=cause)
    assert "Wet" not in traveler.active_conditions
