"""Engine semantic tests for grid, tiles, terrain, and pathfinding."""
from dnd.types.materials import Material, TileSurface

from uuid import UUID, uuid4

import pytest

from dnd.blocks.base_item import (
    BaseItem,
)
from dnd.content.items.environment_item_builders import (
    build_directional_door,
    build_directional_wall,
)
from dnd.core.aoe import Cone, Cylinder, Line, Sphere
from dnd.core.base_block import BaseBlock
from dnd.types.world import CardinalDirection, MovementMode, WorldEdgeChannel
from dnd.core.base_conditions import BaseCondition
from dnd.types.conditions import ConditionCategory, HazardFilter
from dnd.core.base_object import BaseObject
from dnd.core.base_tiles import (
    difficult_terrain_factory,
    floor_factory,
    wall_factory,
    water_factory,
)
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.world_events import (
    ForcedMovementEvent,
    SpatialChangeEvent,
)
from dnd.core.geometry import circle_positions, supercover_line
from dnd.core.gridmap import get_map
from dnd.types.life import LifeState
from dnd.types.damage import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.types.spatial_effects import SpatialEffectTriggerKind
from dnd.core.values import BaseValue
from dnd.actions.standard import (
    Jump,
    Move,
    Shove,
)
from dnd.spells.evocation import Thunderwave
from dnd.entities.entity import Entity
from tests.engine.support import create_test_monster
from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.content.spatial_effect_recipes import SPIKE_GROWTH_SURFACE_RECIPE
from dnd.spatial.area_conditions import AreaCondition
from tests.engine.support import reset_combat_state


class PerceptionBoost(BaseCondition):
    """Test condition that raises passive perception through the skill system."""

    name: str = "Perception Boost"
    boost_amount: int = 10

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event | None]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if target is None:
            return [], [], [], [], None

        skill = target.skill_set.get_skill("perception")
        modifier_uuid = skill.skill_bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name="Perception Boost",
                value=self.boost_amount,
            )
        )
        effect_event = declaration_event.phase_to(EventPhase.EFFECT)
        return [(skill.skill_bonus.uuid, modifier_uuid)], [], [], [], effect_event


class EntryCleanupZone(AreaCondition):
    """Test region with terrain and one position-indexed entry handler."""

    name: str = "Entry Cleanup Zone"
    zone_shape: str = "sphere"
    zone_radius_feet: int = 5
    adds_difficult_terrain: bool = True
    hazard_filter: HazardFilter = HazardFilter.ALL
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({
        SpatialEffectTriggerKind.ENTER,
    })

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create a no-op spatial entry handler for cleanup assertions."""
        return EventHandler(
            name="Entry Cleanup Handler",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[],
            event_processor=lambda event, _source_uuid: event,
        )


def install_entry_cleanup_effect(
    caster: Entity,
    *,
    center: tuple[int, int],
) -> EntryCleanupZone:
    """Install the cleanup fixture through the production spatial owner."""
    zone = materialize_spatial_condition(
        SPIKE_GROWTH_SURFACE_RECIPE,
        caster.uuid,
        position=center,
        faction=caster.faction,
        condition_type=EntryCleanupZone,
    )
    parent = Event(
        source_entity_uuid=caster.uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    result = zone.activate(parent_event=parent)
    assert result is not None
    assert not result.canceled
    return zone


def reset_grid_state(width: int = 8, height: int = 8, x: int = 0, y: int = 0) -> None:
    """Clear global state and create a rectangular floor grid."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(x, y, width, height, surface=TileSurface(base_material=Material.STONE))


def test_eb_11_001_tiles_are_grid_stored_blocks_with_uuid_lookup() -> None:
    """EB-11-001: GridMap owns tile positions and UUID lookup."""
    reset_grid_state(width=1, height=1)
    grid = get_map()

    tile = grid.set_tile(
        3,
        4,
        surface=TileSurface(base_material=Material.STONE),
        walking_cost=1,
        blocks_optics=False,
        name="Marble Floor",
    )

    assert tile.position == (3, 4)
    assert grid.get_tile(3, 4) is tile
    assert grid.get_tile_by_uuid(tile.uuid) is tile
    assert grid.has_tile(3, 4)
    assert grid.bounds == (0, 0, 3, 4)

    grid.remove_tile(3, 4)

    assert grid.get_tile(3, 4) is None
    assert grid.get_tile_by_uuid(tile.uuid) is None


def test_eb_11_002_tile_movement_modes_define_walkability() -> None:
    """EB-11-002: movement mode costs determine tile passability."""
    reset_grid_state(width=1, height=1)

    floor = floor_factory((0, 0))
    wall = wall_factory((1, 0))
    water = water_factory((2, 0))
    difficult = difficult_terrain_factory((3, 0))

    assert floor.get_movement_cost(MovementMode.WALKING) == 1
    assert floor.get_movement_cost(MovementMode.FLYING) == 1
    assert floor.get_movement_cost(MovementMode.SWIMMING) == 0

    assert wall.get_movement_cost(MovementMode.WALKING) == 0
    assert wall.get_movement_cost(MovementMode.FLYING) == 0

    assert water.get_movement_cost(MovementMode.WALKING) == 0
    assert water.get_movement_cost(MovementMode.SWIMMING) == 1

    assert difficult.get_movement_cost(MovementMode.WALKING) == 2
    assert difficult.get_movement_cost(MovementMode.FLYING) == 1


def test_slice_6_2_tile_cost_inputs_are_strict_nonnegative_and_complete() -> None:
    """Public Tile construction owns exactly four strict traversal costs."""
    reset_grid_state(width=1, height=1)
    grid = get_map()
    tile = grid.set_tile(
        1,
        0,
        surface=TileSurface(base_material=Material.STONE),
        walking_cost=0,
        flying_cost=2,
        swimming_cost=3,
        burrowing_cost=4,
    )
    assert (
        tile.get_movement_cost(MovementMode.WALKING),
        tile.get_movement_cost(MovementMode.FLYING),
        tile.get_movement_cost(MovementMode.SWIMMING),
        tile.get_movement_cost(MovementMode.BURROWING),
    ) == (0, 2, 3, 4)
    assert "walkable" not in type(tile).model_fields

    movement_revision = grid.movement_revision
    optical_revision = grid.optical_revision
    propagation_revision = grid.propagation_revision
    cursor = EventQueue.event_cursor()
    tile = grid.set_tile(
        1,
        0,
        surface=TileSurface(base_material=Material.STONE),
        walking_cost=0,
        flying_cost=3,
        swimming_cost=3,
        burrowing_cost=4,
        name="Changed cost tile",
    )
    assert grid.movement_revision == movement_revision + 1
    assert grid.optical_revision == optical_revision
    assert grid.propagation_revision == propagation_revision
    changed_facts = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_TILE_CHANGED
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(changed_facts) == 1
    assert (
        changed_facts[0].tile_walking_cost,
        changed_facts[0].tile_flying_cost,
        changed_facts[0].tile_swimming_cost,
        changed_facts[0].tile_burrowing_cost,
    ) == (0, 3, 3, 4)

    for invalid_costs in (
        {"walking_cost": True},
        {"flying_cost": 1.5},
        {"swimming_cost": "1"},
        {"burrowing_cost": -1},
    ):
        with pytest.raises(ValueError):
            grid.set_tile(
                2,
                0,
                surface=TileSurface(base_material=Material.STONE),
                **invalid_costs,
            )


def test_eb_11_003_dijkstra_paths_sum_tile_costs_and_can_ignore_difficult_terrain() -> None:
    """EB-11-003: path distances are terrain-cost totals, not step counts."""
    reset_grid_state(width=5, height=1)
    grid = get_map()
    difficult_tile = grid.get_tile(2, 0)
    assert difficult_tile is not None
    difficult_tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=difficult_tile.uuid,
            name="Difficult Terrain",
            value=1,
        )
    )

    distances, paths = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)
    easy_distances, _ = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
        ignore_difficult_terrain=True,
    )

    assert distances[(1, 0)] == 1
    assert distances[(2, 0)] == 3
    assert distances[(4, 0)] == 5
    assert paths[(4, 0)] == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
    assert easy_distances[(4, 0)] == 4


@pytest.mark.parametrize(
    ("movement_mode", "value_name", "modifier_value"),
    [
        (MovementMode.FLYING, "flying_cost", 1),
        (MovementMode.SWIMMING, "swimming_cost", 1),
    ],
)
def test_ignore_difficult_terrain_never_underprices_nonwalking_modes(
    movement_mode: MovementMode,
    value_name: str,
    modifier_value: int,
) -> None:
    """Fly/Swim preview uses the same directed edge cost as execution."""
    reset_grid_state(width=2, height=1)
    grid = get_map()
    if movement_mode is MovementMode.SWIMMING:
        for position in ((0, 0), (1, 0)):
            grid.set_tile(*position, tile=water_factory(position))
    for position in ((0, 0), (1, 0)):
        tile = grid.get_tile(*position)
        assert tile is not None
        movement_value = getattr(tile, value_name)
        movement_value.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=tile.uuid,
                name="Mode-specific terrain cost",
                value=modifier_value,
            )
        )
    destination = grid.get_tile(1, 0)
    assert destination is not None
    assert destination.get_movement_cost(movement_mode) == 2
    assert grid.movement_edge_cost_units(
        (0, 0),
        (1, 0),
        movement_mode,
        ignore_difficult_terrain=True,
    ) == 2

    distances, paths = grid.compute_paths(
        (0, 0),
        movement_mode=movement_mode,
        ignore_difficult_terrain=True,
    )

    assert distances[(1, 0)] == 2
    assert paths[(1, 0)] == [(0, 0), (1, 0)]


def test_eb_11_012_diagonal_cost_return_and_exact_max_distance_match() -> None:
    """EB-11-012: diagonal tie-break epsilon stays out of max-distance pruning."""
    reset_grid_state(width=2, height=2)
    grid = get_map()

    distances, paths = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)
    limited_distances, limited_paths = grid.compute_paths(
        (0, 0),
        max_distance=1,
        movement_mode=MovementMode.WALKING,
    )

    assert distances[(1, 0)] == 1
    assert distances[(0, 1)] == 1
    assert distances[(1, 1)] == 1
    assert paths[(1, 1)] == [(0, 0), (1, 1)]

    assert (1, 0) in limited_distances
    assert (0, 1) in limited_distances
    assert limited_distances[(1, 1)] == 1
    assert limited_paths[(1, 1)] == [(0, 0), (1, 1)]


def test_eb_11_021_diagonal_transitions_need_one_cardinal_bridge_route() -> None:
    """EB-11-021: diagonal movement needs at least one passable bridge route."""
    reset_grid_state(width=2, height=2)
    grid = get_map()

    assert grid.can_transition((0, 0), (1, 1))

    east_wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    grid.place_object(
        east_wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    one_bridge_distances, one_bridge_paths = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
    )

    assert not grid.can_transition((0, 0), (1, 0))
    assert grid.can_transition((0, 0), (0, 1))
    assert grid.can_transition((0, 0), (1, 1))
    assert one_bridge_distances[(1, 1)] == 1
    assert one_bridge_paths[(1, 1)] == [(0, 0), (1, 1)]

    north_wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    grid.place_object(
        north_wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.NORTH,
    )
    no_bridge_distances, no_bridge_paths = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
    )

    assert not grid.can_transition((0, 0), (1, 0))
    assert not grid.can_transition((0, 0), (0, 1))
    assert not grid.can_transition((0, 0), (1, 1))
    assert (1, 1) not in no_bridge_distances
    assert (1, 1) not in no_bridge_paths


def test_eb_11_013_negative_coordinate_tiles_are_reachable() -> None:
    """EB-11-013: negative grid bounds are valid pathfinding bounds."""
    reset_grid_state(width=4, height=1, x=-2, y=0)
    grid = get_map()

    assert grid.bounds == (-2, 0, 1, 0)
    assert grid.has_tile(-2, 0)
    assert grid.has_tile(-1, 0)
    assert grid.has_tile(0, 0)
    assert grid.can_transition((-2, 0), (-1, 0))

    distances, paths = grid.compute_paths((-2, 0), movement_mode=MovementMode.WALKING)
    edge_distances, edge_paths = grid.compute_paths((-1, 0), movement_mode=MovementMode.WALKING)

    assert distances[(1, 0)] == 3
    assert paths[(1, 0)] == [(-2, 0), (-1, 0), (0, 0), (1, 0)]
    assert (0, 0) in edge_distances
    assert edge_paths[(0, 0)] == [(-1, 0), (0, 0)]
    assert edge_distances[(-2, 0)] == 1
    assert edge_paths[(-2, 0)] == [(-1, 0), (-2, 0)]


def test_eb_11_004_move_action_converts_tile_cost_units_to_feet() -> None:
    """EB-11-004: Move action costs use terrain costs times 5 feet."""
    reset_grid_state(width=5, height=1)
    grid = get_map()
    difficult_tile = grid.get_tile(2, 0)
    assert difficult_tile is not None
    difficult_tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=difficult_tile.uuid,
            name="Difficult Terrain",
            value=1,
        )
    )
    entity = create_test_monster("monster.skeleton", name="Mover", position=(0, 0), faction="heroes")
    Entity.materialize_all_navigation(max_distance=20)

    move = Move(source_entity_uuid=entity.uuid, end_position=(4, 0))
    event = move.apply()

    movement_cost = next(cost.cost for cost in move.costs if cost.cost_type == "movement")
    assert movement_cost == 25
    assert event is not None
    assert not event.canceled
    assert entity.position == (4, 0)
    assert entity.action_economy.movement.normalized_score == 5


def test_eb_11_005_occupants_and_objects_block_walkable_tiles_polymorphically() -> None:
    """EB-11-005: tiles stay walkable while occupants or objects can block an entity."""
    reset_grid_state(width=4, height=1)
    grid = get_map()
    mover = create_test_monster("monster.skeleton", name="Mover", position=(0, 0), faction="heroes")
    blocker = create_test_monster("monster.skeleton", name="Blocker", position=(1, 0), faction="monsters")
    Entity.materialize_all_navigation(max_distance=20)

    assert grid.is_walkable(1, 0)
    assert not grid.is_walkable_for(1, 0, mover.uuid)
    assert grid.identify_blocker_at((1, 0), mover.uuid) == blocker.name
    assert grid.is_walkable_for(1, 0, blocker.uuid)

    boulder = BaseItem(
        source_entity_uuid=uuid4(),
        name="Boulder",
        is_pickable=False,
        blocks_movement=True,
    )
    grid.place_object(boulder.uuid, (2, 0))

    assert grid.is_walkable(2, 0)
    assert not grid.is_walkable_for(2, 0, mover.uuid)
    assert grid.identify_blocker_at((2, 0), mover.uuid) == "Boulder"

    grid.remove_object(boulder.uuid)
    assert grid.is_walkable_for(2, 0, mover.uuid)


def test_eb_11_015_dead_entities_become_non_blocking_for_paths() -> None:
    """EB-11-015: dead entities stay positioned but no longer block walking."""
    reset_grid_state(width=5, height=1)
    grid = get_map()
    mover = create_test_monster("monster.skeleton", name="Mover", position=(0, 0), faction="heroes")
    blocker = create_test_monster("monster.skeleton", name="Blocker", position=(2, 0), faction="monsters")
    Entity.materialize_all_navigation(max_distance=20)

    assert blocker.blocks_walking(requesting_entity_uuid=mover.uuid) is True
    assert not grid.is_walkable_for(2, 0, mover.uuid)
    assert (2, 0) not in mover.senses.paths
    assert (4, 0) not in mover.senses.paths
    assert blocker.uuid in mover.senses.entities

    blocker.receive_damage(blocker.get_hp() + 5, DamageType.BLUDGEONING, mover.uuid)

    assert blocker.health.life_state is LifeState.DEAD
    assert blocker.non_blocking is False
    assert blocker.blocks_walking(requesting_entity_uuid=mover.uuid) is False
    assert grid.is_walkable_for(2, 0, mover.uuid)
    assert blocker.uuid not in mover.senses.entities
    path_revision_before_refresh = mover.senses.path_revision
    mover.get_available_actions()

    assert mover.senses.path_revision > path_revision_before_refresh
    assert mover.senses.paths[(2, 0)] == [(0, 0), (1, 0), (2, 0)]
    assert mover.senses.paths[(4, 0)] == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]


def test_eb_11_006_boundary_providers_block_transitions_and_emit_metadata() -> None:
    """EB-11-006: one boundary provider blocks crossing, not whole tiles."""
    reset_grid_state(width=4, height=1)
    grid = get_map()
    cursor = EventQueue.event_cursor()

    wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    placement = grid.place_object(
        wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
    )

    events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_OBJECT_PLACED
        and event.phase == EventPhase.COMPLETION
        and event.object_uuid == wall.uuid
    ]
    event = events[-1] if events else None

    assert placement.boundary_direction is CardinalDirection.EAST
    assert grid.is_walkable(1, 0)
    assert not grid.can_transition((1, 0), (2, 0))
    assert not grid.can_transition((2, 0), (1, 0))
    assert grid.can_transition((1, 0), (0, 0))
    assert event is not None
    assert event.placement == placement
    assert event.object_boundary_structure is not None
    assert event.object_boundary_structure.blocked_channels == (
        WorldEdgeChannel.MOVEMENT,
    )
    assert event.get_affected_positions() == {(1, 0), (2, 0)}
    assert event.senses_hint is not None
    assert event.senses_hint.directional_positions == {(1, 0)}
    assert event.senses_hint.directional_neighbors == {(2, 0)}
    assert event.senses_hint.directional_channels_changed == {"movement"}


def test_eb_11_007_directional_channels_are_independent() -> None:
    """EB-11-007: movement, optics, and propagation are separate channels."""
    reset_grid_state(width=4, height=3)
    grid = get_map()
    screen = build_directional_wall(
        display_name="Screen",
        blocked_channels=(
            WorldEdgeChannel.OPTICAL,
            WorldEdgeChannel.PROPAGATION,
        ),
    )
    grid.place_object(
        screen.uuid,
        (1, 1),
        boundary_direction=CardinalDirection.EAST,
    )

    assert grid.can_transition((1, 1), (2, 1))
    assert (2, 1) not in set(grid.compute_fov((1, 1), max_distance=3))
    assert (2, 1) not in set(grid.compute_propagation_fov((1, 1), max_distance=3))
    assert (0, 1) in set(grid.compute_fov((1, 1), max_distance=3))


def test_eb_11_022_fov_cache_invalidates_when_optical_blockers_change() -> None:
    """EB-11-022: cached FOV cannot survive changed optical topology."""
    reset_grid_state(width=6, height=3)
    grid = get_map()

    first_fov = set(grid.compute_fov((0, 1), max_distance=6))
    first_revision = grid.optical_revision
    assert (5, 1) in first_fov

    wall = BaseItem(
        source_entity_uuid=uuid4(),
        name="Vision Cache Wall",
        is_pickable=False,
        blocks_optics_field=True,
    )
    grid.place_object(wall.uuid, (2, 1))

    second_fov = set(grid.compute_fov((0, 1), max_distance=6))

    assert grid.optical_revision > first_revision
    assert (5, 1) not in second_fov
    assert (1, 1) in second_fov


def test_eb_11_023_propagation_cache_reuses_results_and_invalidates_on_blockers() -> None:
    """EB-11-023: public propagation results follow physical blocker revisions."""
    reset_grid_state(width=6, height=3)
    grid = get_map()
    first_fov = grid.compute_propagation_fov((0, 1), max_distance=6)
    first_revision = grid.propagation_revision
    first_result = tuple(first_fov)
    first_fov.append((99, 99))
    second_fov = grid.compute_propagation_fov((0, 1), max_distance=6)

    assert grid.propagation_revision == first_revision
    assert (99, 99) not in second_fov
    assert (5, 1) in second_fov
    assert tuple(second_fov) == first_result

    grid.get_world_edge((2, 1), (3, 1))
    first_diagnostics = grid.last_operation_diagnostics
    assert (
        first_diagnostics.operation,
        first_diagnostics.tiles_inspected,
        first_diagnostics.bands_inspected,
    ) == ("get_world_edge", 2, 0)

    wall = build_directional_wall(
        display_name="Propagation Cache Wall",
        blocked_channels=(WorldEdgeChannel.PROPAGATION,),
    )
    grid.place_object(
        wall.uuid,
        (2, 1),
        boundary_direction=CardinalDirection.EAST,
    )
    third_fov = grid.compute_propagation_fov((0, 1), max_distance=6)

    assert grid.propagation_revision > first_revision
    assert (5, 1) not in third_fov
    assert (2, 1) in grid.get_barrier_positions({(2, 1), (3, 1)})
    grid.get_world_edge((2, 1), (3, 1))
    assert grid.last_operation_diagnostics.tiles_inspected == 2
    assert grid.last_operation_diagnostics.bands_inspected == 2


def test_propagation_only_boundary_removes_threat_and_opportunity_attack() -> None:
    """A propagation-only edge removes threat while movement and optics pass."""
    reset_grid_state(width=5, height=3)
    grid = get_map()
    watcher = create_test_monster(
        "monster.skeleton",
        name="Watcher",
        position=(1, 1),
        faction="monsters",
    )
    mover = create_test_monster(
        "monster.goblin",
        name="Mover",
        position=(2, 1),
        faction="heroes",
    )
    Entity.materialize_all_navigation(max_distance=20)

    assert watcher.uuid in mover.senses.entities
    assert watcher.threatens_entity_at(mover)
    assert grid.can_transition((1, 1), (2, 1), mover.uuid)
    assert grid.can_optical_transition((1, 1), (2, 1))
    before_move = next(
        action
        for action in mover.get_available_actions().position_actions
        if action.template_name == "Move"
    )
    before_target = next(
        target for target in before_move.valid_targets
        if target.position == (3, 1)
    )
    assert [
        exposure.reactor_uuid
        for exposure in before_target.opportunity_attack_exposures
    ] == [watcher.uuid]

    boundary = build_directional_wall(
        display_name="Propagation Screen",
        blocked_channels=(WorldEdgeChannel.PROPAGATION,),
    )
    grid.place_object(
        boundary.uuid,
        (1, 1),
        boundary_direction=CardinalDirection.EAST,
    )

    assert not watcher.threatens_entity_at(mover)
    assert grid.can_transition((1, 1), (2, 1), mover.uuid)
    assert grid.can_optical_transition((1, 1), (2, 1))
    after_move = next(
        action
        for action in mover.get_available_actions().position_actions
        if action.template_name == "Move"
    )
    after_target = next(
        target for target in after_move.valid_targets
        if target.position == (3, 1)
    )
    assert after_target.opportunity_attack_exposures == []


def test_eb_11_017_forced_movement_and_jump_respect_directional_blockers() -> None:
    """EB-11-017: push movement and Jump both consult directional blockers."""
    reset_grid_state(width=4, height=3)
    grid = get_map()
    actor = create_test_monster("monster.skeleton", name="Actor", position=(1, 1), faction="heroes")
    wall = build_directional_wall(
        display_name="Directional Force Wall",
        blocked_channels=(
            WorldEdgeChannel.MOVEMENT,
            WorldEdgeChannel.PROPAGATION,
        ),
    )
    grid.place_object(
        wall.uuid,
        (1, 1),
        boundary_direction=CardinalDirection.EAST,
    )
    entry_wall = build_directional_wall(
        display_name="Directional Entry Wall",
        blocked_channels=(WorldEdgeChannel.MOVEMENT, WorldEdgeChannel.PROPAGATION),
    )
    grid.place_object(
        entry_wall.uuid,
        (2, 1),
        boundary_direction=CardinalDirection.WEST,
    )
    Entity.materialize_all_navigation(max_distance=20)

    final_pos, distance, blocked, blocker_name = Shove.calculate_final_position(
        start=(1, 1),
        direction=(1, 0),
        distance_feet=10,
        target_uuid=actor.uuid,
    )

    assert final_pos == (1, 1)
    assert distance == 0
    assert blocked is True
    assert blocker_name == wall.name
    assert not grid.can_transition((1, 1), (2, 1), actor.uuid)

    grid.remove_object(wall.uuid)
    final_pos, distance, blocked, blocker_name = Shove.calculate_final_position(
        start=(1, 1),
        direction=(1, 0),
        distance_feet=5,
        target_uuid=actor.uuid,
    )
    assert final_pos == (1, 1)
    assert distance == 0
    assert blocked is True
    assert blocker_name == entry_wall.name

    clear_diagonal = (0, 2)
    assert grid.can_transition((1, 1), clear_diagonal, actor.uuid)
    assert grid.identify_blocker_at(
        clear_diagonal,
        actor.uuid,
        source_position=(1, 1),
    ) is None

    bridge_wall = build_directional_wall(
        display_name="Diagonal Bridge Wall",
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    grid.place_object(
        bridge_wall.uuid,
        (1, 1),
        boundary_direction=CardinalDirection.WEST,
    )
    bridge_wall_other_leg = build_directional_wall(
        display_name="Diagonal Bridge Wall Other Leg",
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    grid.place_object(
        bridge_wall_other_leg.uuid,
        (1, 1),
        boundary_direction=CardinalDirection.NORTH,
    )
    assert not grid.can_transition((1, 1), clear_diagonal, actor.uuid)
    assert grid.identify_blocker_at(
        clear_diagonal,
        actor.uuid,
        source_position=(1, 1),
    ) == "obstacle"

    closed_door = build_directional_door(
        display_name="Closed Identity Door",
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    grid.place_object(
        closed_door.uuid,
        (1, 2),
        boundary_direction=CardinalDirection.EAST,
    )
    assert not grid.can_transition((1, 2), (2, 2), actor.uuid)
    assert grid.identify_blocker_at(
        (2, 2),
        actor.uuid,
        source_position=(1, 2),
    ) == closed_door.name

    thunderwave_caster = create_test_monster(
        "monster.generic_caster",
        name="Thunderwave caster",
        position=(0, 0),
        faction="heroes",
    )
    push_target = create_test_monster(
        "monster.skeleton",
        name="Thunderwave target",
        position=(1, 0),
        faction="monsters",
    )
    dead_non_blocker = create_test_monster(
        "monster.skeleton",
        name="Dead non-blocker",
        position=(2, 0),
        faction="monsters",
    )
    dead_non_blocker.receive_damage(
        dead_non_blocker.get_hp() + 5,
        DamageType.BLUDGEONING,
        actor.uuid,
    )
    assert dead_non_blocker.health.life_state is LifeState.DEAD
    assert dead_non_blocker.blocks_walking(
        requesting_entity_uuid=push_target.uuid,
    ) is False
    push_target.saving_throws.get_saving_throw(
        "constitution",
    ).bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=thunderwave_caster.uuid,
            target_entity_uuid=push_target.uuid,
            name="Forced Thunderwave failed save",
            value=-100,
        )
    )
    thunderwave = Thunderwave(
        source_entity_uuid=thunderwave_caster.uuid,
        target_entity_uuid=push_target.uuid,
        end_position=push_target.position,
    )
    cursor = EventQueue.event_cursor()
    thunderwave_result = thunderwave.apply()
    assert thunderwave_result is not None
    assert not thunderwave_result.canceled
    assert push_target.position == (3, 0)
    forced_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ForcedMovementEvent)
        and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == push_target.uuid
    ]
    assert len(forced_events) == 1
    assert forced_events[0].blocked_by_obstacle is False
    assert forced_events[0].blocked_by is None

    jump = Jump(source_entity_uuid=actor.uuid, template=True)
    assert (3, 1) in actor.senses.visible
    assert not grid.raycast_clear(
        (1, 1),
        (3, 1),
        channel="propagation",
        requester_uuid=actor.uuid,
    )
    assert (3, 1) not in jump.get_valid_positions()

    jump_attempt = Jump(source_entity_uuid=actor.uuid, end_position=(3, 1))
    declaration = jump_attempt._create_declaration_event(use_register=False)
    assert declaration is not None
    validated = jump_attempt._validate(declaration)

    assert validated.canceled is True
    assert validated.status_message is not None
    assert "blocked" in validated.status_message.lower()


def test_unknown_boundary_collision_records_directed_memory_before_reroute() -> None:
    """An unknown objective boundary first collides, then blocks remembered subjective routing."""
    reset_grid_state(width=3, height=1)
    grid = get_map()
    wall = build_directional_wall(
        display_name="Hidden remembered wall",
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    grid.place_object(
        wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
    )
    wall.set_invisible(True)
    actor = create_test_monster(
        "monster.skeleton",
        name="Unknown-collision actor",
        position=(0, 0),
        darkvision=False,
    )
    Entity.materialize_all_navigation(max_distance=10)

    assert wall.uuid not in actor.senses.objects
    assert grid.can_transition(
        (0, 0),
        (1, 0),
        actor.uuid,
        subjective=True,
        directional_collision_blocked=actor.senses.directional_collision_blocked,
    )
    assert not grid.can_transition((0, 0), (1, 0), actor.uuid)

    cursor = EventQueue.event_cursor()
    result = Move(
        source_entity_uuid=actor.uuid,
        end_position=(1, 0),
        use_movement_cost=False,
    ).apply()

    assert result is not None
    assert result.termination_reason.value == "collision"
    assert actor.position == (0, 0)
    assert wall.uuid not in actor.senses.objects
    assert grid.can_transition(
        (0, 0),
        (1, 0),
        actor.uuid,
        subjective=True,
        directional_collision_blocked=set(),
    )
    assert ( (0, 0), "east") in actor.senses.directional_collision_blocked
    collision_facts = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.MOVEMENT_COLLISION
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(collision_facts) == 1
    assert collision_facts[0].transition_from == (0, 0)
    assert collision_facts[0].transition_to == (1, 0)
    assert not grid.can_transition(
        (0, 0),
        (1, 0),
        actor.uuid,
        subjective=True,
        directional_collision_blocked=actor.senses.directional_collision_blocked,
    )


def test_eb_11_008_hazards_can_be_excluded_from_safe_paths() -> None:
    """EB-11-008: hazard-aware pathfinding treats dangerous cells as blocked."""
    reset_grid_state(width=3, height=2)
    grid = get_map()
    entity = create_test_monster("monster.skeleton", name="Pathfinder", position=(0, 0), faction="heroes")
    hazard_tile = grid.get_tile(1, 0)
    assert hazard_tile is not None
    hazard = BaseCondition(
        name="Burning Ground",
        source_entity_uuid=uuid4(),
        target_entity_uuid=hazard_tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
    )
    hazard_tile.add_condition(hazard)

    normal_distances, normal_paths = grid.compute_paths(
        (0, 0),
        requesting_entity_uuid=entity.uuid,
        walk_in_danger=True,
    )
    safe_distances, safe_paths = grid.compute_paths(
        (0, 0),
        requesting_entity_uuid=entity.uuid,
        walk_in_danger=False,
    )

    assert grid.is_position_hazardous_for(1, 0, entity.uuid)
    assert normal_paths[(2, 0)] == [(0, 0), (1, 0), (2, 0)]
    assert (2, 0) in safe_distances
    assert (1, 0) not in safe_paths[(2, 0)]
    assert normal_distances[(2, 0)] == 2
    assert safe_distances[(2, 0)] == 2


def test_eb_11_014_hidden_hazard_perception_change_recomputes_safe_paths() -> None:
    """EB-11-014: hidden hazards become safe-path blockers after perception changes."""
    reset_grid_state(width=5, height=3)
    grid = get_map()
    observer = create_test_monster("monster.skeleton", name="Observer", position=(0, 1), faction="heroes")
    trap_tile = grid.get_tile(2, 1)
    assert trap_tile is not None

    base_perception = observer.get_passive_perception()
    hidden_trap = BaseCondition(
        name="Hidden Trap",
        source_entity_uuid=uuid4(),
        target_entity_uuid=trap_tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
        condition_stealth_dc=base_perception + 5,
    )
    trap_tile.add_condition(hidden_trap)
    Entity.materialize_all_navigation(max_distance=20)

    destination = (4, 1)
    initial_path = observer.senses.paths[destination]
    assert (2, 1) in initial_path
    assert not grid.is_position_hazardous_for(2, 1, observer.uuid)
    assert observer.senses.safe_paths == {}
    path_revision_before_condition = observer.senses.path_revision

    observer.add_condition(
        PerceptionBoost(
            source_entity_uuid=observer.uuid,
            target_entity_uuid=observer.uuid,
            boost_amount=10,
        )
    )

    assert hidden_trap.condition_stealth_dc is not None
    assert observer.get_passive_perception() > hidden_trap.condition_stealth_dc
    assert grid.is_position_hazardous_for(2, 1, observer.uuid)
    assert observer.senses.safe_paths == {}

    observer.get_available_actions()

    assert observer.senses.path_revision > path_revision_before_condition
    recomputed_path = observer.senses.paths[destination]
    safe_path = observer.senses.safe_paths[destination]
    assert (2, 1) in recomputed_path
    assert (2, 1) not in safe_path


def test_eb_11_009_geometry_and_aoe_are_grid_aware_where_needed() -> None:
    """EB-11-009: pure geometry feeds AoE shapes, which then consult the grid."""
    reset_grid_state(width=5, height=3)
    grid = get_map()
    grid.set_tile(
        2,
        1,
        surface=TileSurface(base_material=Material.STONE),
        walking_cost=0,
        blocks_optics=True,
        blocks_propagation=True,
        name="Wall",
    )
    caster = create_test_monster("monster.skeleton", name="Caster", position=(0, 1), faction="heroes")
    target = create_test_monster("monster.skeleton", name="Behind Wall", position=(3, 1), faction="monsters")

    assert circle_positions((1, 1), radius=1) == {
        (1, 1),
        (0, 1),
        (2, 1),
        (1, 0),
        (1, 2),
    }
    assert supercover_line((0, 0), (3, 2))[0] == (0, 0)
    assert supercover_line((0, 0), (3, 2))[-1] == (3, 2)

    sphere = Sphere(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
    sphere.compute_objective(caster.position)
    cylinder = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
    cylinder.compute_objective(caster.position)

    assert target.uuid not in sphere.affected_entity_uuids
    assert (3, 1) not in sphere.affected_positions
    assert target.uuid in cylinder.affected_entity_uuids
    assert (3, 1) in cylinder.affected_positions


def test_eb_11_018_zone_control_cone_and_line_use_directional_geometry() -> None:
    """EB-11-018: generic ZoneControl cone/line setup maps direction into AoE geometry."""
    reset_grid_state(width=10, height=5)
    source_uuid = uuid4()

    direct_cone = Cone(source_entity_uuid=source_uuid, target=(8, 2), length_feet=30)
    direct_cone.compute_objective(caster_pos=(2, 2))
    direct_line = Line(source_entity_uuid=source_uuid, target=(8, 2), length_feet=30, width_feet=5)
    direct_line.compute_objective(caster_pos=(2, 2))

    generic_cone_zone = materialize_spatial_condition(
        SPIKE_GROWTH_SURFACE_RECIPE,
        source_uuid,
        position=(2, 2),
        faction=None,
        condition_type=AreaCondition,
        condition_fields={
            "zone_shape": "cone",
            "zone_radius_feet": 30,
            "zone_direction": (1, 0),
        },
    )
    generic_line_zone = materialize_spatial_condition(
        SPIKE_GROWTH_SURFACE_RECIPE,
        source_uuid,
        position=(2, 2),
        faction=None,
        condition_type=AreaCondition,
        condition_fields={
            "zone_shape": "line",
            "zone_radius_feet": 30,
            "zone_direction": (1, 0),
        },
    )

    assert (3, 2) in direct_cone.affected_positions
    assert (5, 2) in direct_cone.affected_positions
    assert (1, 2) not in direct_cone.affected_positions
    assert (2, 2) in direct_line.affected_positions
    assert (8, 2) in direct_line.affected_positions
    assert (2, 3) not in direct_line.affected_positions

    assert generic_cone_zone._compute_affected_positions() == direct_cone.affected_positions
    assert generic_line_zone._compute_affected_positions() == direct_line.affected_positions


def test_eb_11_019_cylinder_subjective_preview_matches_targeting_footprint() -> None:
    """EB-11-019: cylinder subjective previews use the same full footprint as targeting."""
    reset_grid_state(width=5, height=3)
    grid = get_map()
    grid.set_tile(
        2,
        1,
        surface=TileSurface(base_material=Material.STONE),
        walking_cost=0,
        blocks_optics=True,
        blocks_propagation=True,
        name="Wall",
    )
    caster = create_test_monster("monster.skeleton", name="Caster", position=(0, 1), faction="heroes")
    target = create_test_monster("monster.skeleton", name="Behind Wall", position=(3, 1), faction="monsters")
    Entity.materialize_all_navigation(max_distance=20)

    subjective = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
    subjective.compute_subjective(
        caster.position,
        caster.senses,
        caster_uuid=caster.uuid,
    )

    targeting = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
    targeting.compute_for_targeting(
        caster.position,
        caster.senses,
        caster_uuid=caster.uuid,
    )

    objective = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
    objective.compute_objective(caster.position)

    assert (3, 1) in subjective.affected_positions
    assert (3, 1) in targeting.affected_positions
    assert (3, 1) in objective.affected_positions
    assert subjective.affected_positions == targeting.affected_positions
    assert subjective.affected_positions == objective.affected_positions
    assert target.uuid not in subjective.affected_entity_uuids
    assert target.uuid not in targeting.affected_entity_uuids
    assert target.uuid in objective.affected_entity_uuids


def test_eb_11_020_region_retirement_cleans_spatial_handlers_and_terrain() -> None:
    """EB-11-020: retiring a spatial effect clears its handlers and terrain."""
    reset_grid_state(width=6, height=3)
    grid = get_map()
    caster = create_test_monster("monster.skeleton", name="Zone Caster", position=(0, 1), faction="heroes")
    zone = install_entry_cleanup_effect(caster, center=(2, 1))

    affected_positions = set(zone.affected_positions)
    center_tile = grid.get_tile(2, 1)
    assert center_tile is not None
    assert affected_positions == {(2, 1), (1, 1), (3, 1), (2, 0), (2, 2)}
    assert center_tile.get_movement_cost(MovementMode.WALKING) == 2
    assert len(zone.spatial_handler_uuids) == 1
    assert zone.spatial_handler_uuids[0] in EventQueue._handler_positions
    for pos in affected_positions:
        tile = grid.get_tile(*pos)
        assert tile is not None
        assert EventQueue.get_spatial_handlers_at(pos)

    assert zone.move_zone(
        (4, 1),
        parent_event=Event(
            source_entity_uuid=caster.uuid,
            event_type=EventType.BASE_ACTION,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ),
    )
    moved_positions = set(zone.affected_positions)
    moved_center = grid.get_tile(4, 1)
    assert moved_center is not None
    assert zone.position == (4, 1)
    assert moved_positions != affected_positions
    assert center_tile.get_movement_cost(MovementMode.WALKING) == 1
    assert moved_center.get_movement_cost(MovementMode.WALKING) == 2
    assert EventQueue.get_spatial_handlers_at((4, 1))

    zone.deactivate()

    assert BaseCondition.get(zone.uuid) is None
    assert center_tile.get_movement_cost(MovementMode.WALKING) == 1
    assert moved_center.get_movement_cost(MovementMode.WALKING) == 1
    assert zone.spatial_handler_uuids == []
    for pos in affected_positions | moved_positions:
        tile = grid.get_tile(*pos)
        assert tile is not None
        assert EventQueue.get_spatial_handlers_at(pos) == []


def test_zone_terrain_changes_publish_one_complete_spatial_lifecycle() -> None:
    """Zone-owned terrain notifications use the canonical spatial lifecycle."""
    reset_grid_state(width=6, height=3)
    grid = get_map()
    caster = create_test_monster("monster.skeleton", 
        name="Zone Caster",
        position=(0, 1),
        faction="heroes",
    )
    grid.set_tile(
        3,
        1,
        surface=TileSurface(base_material=Material.STONE),
        walking_cost=3,
        fire_event=False,
        name="Heterogeneous floor",
    )
    cursor = EventQueue.event_cursor()

    declaration_calls = 0

    def reject_tile_declaration(event: Event, _source_uuid: UUID) -> Event:
        nonlocal declaration_calls
        declaration_calls += 1
        return event.cancel("committed Tile facts cannot be vetoed")

    blocker = EventHandler(
        name="Reject committed Tile declarations",
        source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=reject_tile_declaration,
    )
    EventQueue.add_event_handler(blocker)

    zone = install_entry_cleanup_effect(caster, center=(2, 1))
    blocker.remove()
    assert declaration_calls == 0

    by_lineage: dict[UUID, list[EventPhase]] = {}
    activation_facts: list[SpatialChangeEvent] = []
    for _, event in EventQueue.iter_events_since(cursor):
        if event.event_type is not EventType.SPATIAL_TILE_CHANGED:
            continue
        if (
            isinstance(event, SpatialChangeEvent)
            and event.phase is EventPhase.COMPLETION
        ):
            activation_facts.append(event)
        by_lineage.setdefault(event.lineage_uuid, []).append(event.phase)
    assert by_lineage
    assert all(
        phases
        == [
            EventPhase.DECLARATION,
            EventPhase.EXECUTION,
            EventPhase.EFFECT,
            EventPhase.COMPLETION,
        ]
        for phases in by_lineage.values()
    )
    affected = sorted({event.position for event in activation_facts})
    assert affected == [(1, 1), (2, 0), (2, 1), (2, 2), (3, 1)]
    base_costs = {
        position: (1, 1, 0, 0)
        for position in affected
    }
    base_costs[(3, 1)] = (3, 1, 0, 0)
    expected_costs = {
        position: (walking + 1, flying, swimming, burrowing)
        for position, (walking, flying, swimming, burrowing)
        in base_costs.items()
    }
    assert {
        event.position: (
            event.tile_walking_cost,
            event.tile_flying_cost,
            event.tile_swimming_cost,
            event.tile_burrowing_cost,
        )
        for event in activation_facts
    } == expected_costs
    detached = dict(base_costs)
    for event in sorted(activation_facts, key=lambda row: row.position):
        detached[event.position] = (
            event.tile_walking_cost,
            event.tile_flying_cost,
            event.tile_swimming_cost,
            event.tile_burrowing_cost,
        )
    assert detached == expected_costs
    removal_cursor = EventQueue.event_cursor()
    assert zone.deactivate()
    removal_facts = [
        event
        for _, event in EventQueue.iter_events_since(removal_cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_TILE_CHANGED
        and event.phase is EventPhase.COMPLETION
    ]
    assert [event.position for event in removal_facts] == affected
    assert {
        event.position: (
            event.tile_walking_cost,
            event.tile_flying_cost,
            event.tile_swimming_cost,
            event.tile_burrowing_cost,
        )
        for event in removal_facts
    } == base_costs


def test_eb_11_010_walkability_is_cost_driven_not_the_legacy_flag() -> None:
    """EB-11-010: GridMap walkability reads movement cost only."""
    reset_grid_state(width=2, height=1)
    grid = get_map()
    tile = grid.get_tile(1, 0)
    assert tile is not None

    assert not hasattr(tile, "walkable")
    assert tile.get_movement_cost(MovementMode.WALKING) == 1
    assert grid.is_walkable(1, 0)

    tile.walking_cost.self_static.add_max_constraint(
        NumericalModifier.create(
            source_entity_uuid=tile.uuid,
            name="Closed",
            value=0,
        )
    )
    assert not grid.is_walkable(1, 0)


def test_eb_11_011_moving_object_replaces_old_grid_membership() -> None:
    """EB-11-011: explicit movement keeps one authoritative placement."""
    reset_grid_state(width=4, height=1)
    grid = get_map()
    crate = BaseItem(
        source_entity_uuid=uuid4(),
        name="Crate",
        is_pickable=False,
    )

    grid.place_object(crate.uuid, (1, 0))
    grid.move_object(crate.uuid, (2, 0))

    assert grid.get_object_position(crate.uuid) == (2, 0)
    assert crate.uuid not in grid.get_objects_at((1, 0))
    assert crate.uuid in grid.get_objects_at((2, 0))


def test_eb_11_016_raw_object_removal_clears_item_floor_location_state() -> None:
    """EB-11-016: GridMap removal clears floor location without destroying items."""
    reset_grid_state(width=4, height=1)
    grid = get_map()
    observer = create_test_monster("monster.skeleton", name="Observer", position=(0, 0), faction="heroes")
    raw_item = BaseItem(source_entity_uuid=uuid4(), name="Raw Floor Item")
    raw_item.place_on_grid((1, 0))
    Entity.materialize_all_navigation(max_distance=20)

    raw_placement = grid.get_object_placement(raw_item.uuid)
    assert raw_placement is not None
    assert grid.get_object_position(raw_item.uuid) == (1, 0)
    assert raw_item.uuid in observer.senses.objects

    grid.remove_object(raw_item.uuid)

    assert grid.get_object_position(raw_item.uuid) is None
    assert raw_item.uuid not in grid.get_objects_at((1, 0))
    assert raw_item.uuid not in observer.senses.objects
    assert grid.get_object_placement(raw_item.uuid) is None
    assert raw_item.get_position() is None
    assert BaseBlock.get(raw_item.uuid) is raw_item

    lifecycle_item = BaseItem(source_entity_uuid=uuid4(), name="Lifecycle Floor Item")
    lifecycle_item.place_on_grid((2, 0))
    assert grid.get_object_placement(lifecycle_item.uuid) is not None

    lifecycle_item.destroy()

    assert grid.get_object_position(lifecycle_item.uuid) is None
    assert grid.get_object_placement(lifecycle_item.uuid) is None
    assert lifecycle_item.owner_uuid is None
    assert lifecycle_item.stored_in_uuid is None
    assert BaseBlock.get(lifecycle_item.uuid) is None
