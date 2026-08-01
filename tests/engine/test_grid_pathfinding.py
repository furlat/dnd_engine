"""Engine semantic tests for grid, tiles, terrain, and pathfinding."""

from uuid import UUID, uuid4

import pytest

import dnd.core.gridmap as gridmap_module
from dnd.blocks.base_item import BaseItem
from dnd.core.aoe import Cone, Cylinder, Line, Sphere
from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory, HazardFilter
from dnd.core.base_object import BaseObject
from dnd.core.base_tiles import (
    difficult_terrain_factory,
    floor_factory,
    wall_factory,
    water_factory,
)
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, SpatialChangeEvent
from dnd.core.geometry import circle_positions, supercover_line
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.core.spatial_effect_types import SpatialEffectTriggerKind
from dnd.core.values import BaseValue
from dnd.actions import Jump, Move, Shove
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.spatial_effect_content import GREASE_SURFACE_RECIPE
from dnd.spatial_effects import GroundEffect
from dnd.spatial_effect_controllers import AreaSpatialEffectController
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


class EntryCleanupZone(AreaSpatialEffectController):
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
) -> tuple[GroundEffect, EntryCleanupZone]:
    """Install the cleanup fixture through the production spatial owner."""
    zone = EntryCleanupZone(
        source_entity_uuid=caster.uuid,
        zone_center=center,
    )
    effect = GroundEffect(
        name="Entry Cleanup Effect",
        source_entity_uuid=caster.uuid,
        content_ref=GREASE_SURFACE_RECIPE.ref,
        position=center,
        trigger_kinds=zone.trigger_kinds,
        first_per_turn_trigger_kinds=zone.first_per_turn_trigger_kinds,
    )
    parent = Event(
        source_entity_uuid=caster.uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    result = effect.install_controller(zone, parent_event=parent)
    assert result is not None
    assert not result.canceled
    return effect, zone


def reset_grid_state(width: int = 8, height: int = 8, x: int = 0, y: int = 0) -> None:
    """Clear global state and create a rectangular floor grid."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(x, y, width, height)


def test_eb_11_001_tiles_are_grid_stored_blocks_with_uuid_lookup() -> None:
    """EB-11-001: GridMap owns tile positions and UUID lookup."""
    reset_grid_state(width=1, height=1)
    grid = get_map()

    tile = grid.set_tile(3, 4, walkable=True, visible=True, name="Marble Floor")

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

    grid.set_tile_directional_border((0, 0), "movement", "east", False)
    one_bridge_distances, one_bridge_paths = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
    )

    assert not grid.can_transition((0, 0), (1, 0))
    assert grid.can_transition((0, 0), (0, 1))
    assert grid.can_transition((0, 0), (1, 1))
    assert one_bridge_distances[(1, 1)] == 1
    assert one_bridge_paths[(1, 1)] == [(0, 0), (1, 1)]

    grid.set_tile_directional_border((0, 0), "movement", "north", False)
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
    entity = create_skeleton(name="Mover", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

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
    mover = create_skeleton(name="Mover", position=(0, 0), faction="heroes")
    blocker = create_skeleton(name="Blocker", position=(1, 0), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

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
    mover = create_skeleton(name="Mover", position=(0, 0), faction="heroes")
    blocker = create_skeleton(name="Blocker", position=(2, 0), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

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
    assert mover.senses._paths_dirty is True

    mover.get_available_actions()

    assert mover.senses._paths_dirty is False
    assert mover.senses.paths[(2, 0)] == [(0, 0), (1, 0), (2, 0)]
    assert mover.senses.paths[(4, 0)] == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]


def test_eb_11_006_directional_borders_block_transitions_and_emit_metadata() -> None:
    """EB-11-006: directional border changes affect crossing, not whole tiles."""
    reset_grid_state(width=4, height=1)
    grid = get_map()
    cursor = EventQueue.event_cursor()

    changed = grid.set_tile_directional_border((1, 0), "movement", "east", False)

    events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_TILE_CHANGED
        and event.phase == EventPhase.DECLARATION
    ]
    event = events[-1] if events else None

    assert changed is True
    assert grid.is_walkable(1, 0)
    assert not grid.can_transition((1, 0), (2, 0))
    assert not grid.can_transition((2, 0), (1, 0))
    assert grid.can_transition((1, 0), (0, 0))
    assert event is not None
    assert event.directional_position == (1, 0)
    assert event.directional_directions == ["east"]
    assert event.directional_channels == ["movement"]
    assert {(1, 0), (2, 0)} <= event.get_affected_positions()


def test_eb_11_007_directional_channels_are_independent() -> None:
    """EB-11-007: movement, vision, light, and propagation are separate channels."""
    reset_grid_state(width=4, height=3)
    grid = get_map()
    screen = BaseItem(
        source_entity_uuid=uuid4(),
        name="Screen",
        is_pickable=False,
        blocks_vision_east=True,
        blocks_light_east=True,
        blocks_propagation_east=True,
    )
    grid.place_object(screen.uuid, (1, 1))

    assert grid.can_transition((1, 1), (2, 1))
    assert (2, 1) not in set(grid.compute_fov((1, 1), max_distance=3))
    assert (2, 1) not in set(grid.compute_light_fov((1, 1), max_distance=3))
    assert (2, 1) not in set(grid.compute_propagation_fov((1, 1), max_distance=3))
    assert (0, 1) in set(grid.compute_fov((1, 1), max_distance=3))


def test_eb_11_022_fov_cache_invalidates_when_vision_blockers_change() -> None:
    """EB-11-022: cached FOV cannot survive changed vision topology."""
    reset_grid_state(width=6, height=3)
    grid = get_map()

    first_fov = set(grid.compute_fov((0, 1), max_distance=6))
    first_revision = grid.vision_revision
    assert (5, 1) in first_fov

    wall = BaseItem(
        source_entity_uuid=uuid4(),
        name="Vision Cache Wall",
        is_pickable=False,
        blocks_vision_field=True,
    )
    grid.place_object(wall.uuid, (2, 1))

    second_fov = set(grid.compute_fov((0, 1), max_distance=6))

    assert grid.vision_revision > first_revision
    assert (5, 1) not in second_fov
    assert (1, 1) in second_fov


def test_eb_11_023_propagation_cache_reuses_results_and_invalidates_on_blockers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EB-11-023: AoE propagation caches follow physical blocker revisions."""
    reset_grid_state(width=6, height=3)
    grid = get_map()
    original_compute_fov = gridmap_module.compute_fov
    compute_calls = 0

    def track_compute_fov(*args, **kwargs):
        nonlocal compute_calls
        compute_calls += 1
        return original_compute_fov(*args, **kwargs)

    monkeypatch.setattr(gridmap_module, "compute_fov", track_compute_fov)
    first_fov = grid.compute_propagation_fov((0, 1), max_distance=6)
    first_revision = grid.propagation_revision
    first_fov.append((99, 99))
    second_fov = grid.compute_propagation_fov((0, 1), max_distance=6)

    assert compute_calls == 1
    assert (99, 99) not in second_fov
    assert (5, 1) in second_fov

    wall = BaseItem(
        source_entity_uuid=uuid4(),
        name="Propagation Cache Wall",
        is_pickable=False,
        blocks_vision_field=True,
    )
    grid.place_object(wall.uuid, (2, 1))
    third_fov = grid.compute_propagation_fov((0, 1), max_distance=6)

    assert grid.propagation_revision > first_revision
    assert compute_calls == 2
    assert (5, 1) not in third_fov


def test_eb_11_017_forced_movement_and_jump_respect_directional_blockers() -> None:
    """EB-11-017: push movement and Jump both consult directional blockers."""
    reset_grid_state(width=4, height=3)
    grid = get_map()
    actor = create_skeleton(name="Actor", position=(1, 1), faction="heroes")
    wall = BaseItem(
        source_entity_uuid=uuid4(),
        name="Directional Force Wall",
        is_pickable=False,
        blocks_movement_east=True,
        blocks_propagation_east=True,
    )
    grid.place_object(wall.uuid, (1, 1))
    Entity.update_all_entities_senses(max_distance=20)

    final_pos, distance, blocked, blocker_name = Shove.calculate_final_position(
        start=(1, 1),
        direction=(1, 0),
        distance_feet=10,
        target_uuid=actor.uuid,
    )

    assert final_pos == (1, 1)
    assert distance == 0
    assert blocked is True
    assert blocker_name == "obstacle"
    assert not grid.can_transition((1, 1), (2, 1), actor.uuid)

    jump = Jump(source_entity_uuid=actor.uuid, template=True)
    assert (3, 1) in actor.senses.visible
    assert not grid.raycast_clear((1, 1), (3, 1), channel="propagation", observer_uuid=actor.uuid)
    assert (3, 1) not in jump.get_valid_positions()

    jump_attempt = Jump(source_entity_uuid=actor.uuid, end_position=(3, 1))
    declaration = jump_attempt._create_declaration_event(use_register=False)
    assert declaration is not None
    validated = jump_attempt._validate(declaration)

    assert validated.canceled is True
    assert validated.status_message is not None
    assert "blocked" in validated.status_message.lower()


def test_eb_11_008_hazards_can_be_excluded_from_safe_paths() -> None:
    """EB-11-008: hazard-aware pathfinding treats dangerous cells as blocked."""
    reset_grid_state(width=3, height=2)
    grid = get_map()
    entity = create_skeleton(name="Pathfinder", position=(0, 0), faction="heroes")
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
    observer = create_skeleton(name="Observer", position=(0, 1), faction="heroes")
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
    Entity.update_all_entities_senses(max_distance=20)

    destination = (4, 1)
    initial_path = observer.senses.paths[destination]
    assert (2, 1) in initial_path
    assert not grid.is_position_hazardous_for(2, 1, observer.uuid)
    assert observer.senses.safe_paths == {}
    assert observer.senses._paths_dirty is False

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
    assert observer.senses._paths_dirty is True
    assert observer.senses.safe_paths == {}

    observer.get_available_actions()

    recomputed_path = observer.senses.paths[destination]
    safe_path = observer.senses.safe_paths[destination]
    assert (2, 1) in recomputed_path
    assert (2, 1) not in safe_path
    assert observer.senses._paths_dirty is False


def test_eb_11_009_geometry_and_aoe_are_grid_aware_where_needed() -> None:
    """EB-11-009: pure geometry feeds AoE shapes, which then consult the grid."""
    reset_grid_state(width=5, height=3)
    grid = get_map()
    grid.set_tile(2, 1, walkable=False, visible=False, name="Wall")
    caster = create_skeleton(name="Caster", position=(0, 1), faction="heroes")
    target = create_skeleton(name="Behind Wall", position=(3, 1), faction="monsters")

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

    generic_cone_zone = AreaSpatialEffectController(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        zone_shape="cone",
        zone_center=(2, 2),
        zone_radius_feet=30,
        zone_direction=(1, 0),
    )
    generic_line_zone = AreaSpatialEffectController(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        zone_shape="line",
        zone_center=(2, 2),
        zone_radius_feet=30,
        zone_direction=(1, 0),
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
    grid.set_tile(2, 1, walkable=False, visible=False, name="Wall")
    caster = create_skeleton(name="Caster", position=(0, 1), faction="heroes")
    target = create_skeleton(name="Behind Wall", position=(3, 1), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    subjective = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
    subjective.compute_subjective(
        caster.position,
        caster.senses,
        barrier_positions=grid.get_barrier_positions(),
        caster_uuid=caster.uuid,
    )

    targeting = Cylinder(source_entity_uuid=caster.uuid, target=(1, 1), radius_feet=15)
    targeting.compute_for_targeting(
        caster.position,
        caster.senses,
        barrier_positions=grid.get_barrier_positions(),
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
    caster = create_skeleton(name="Zone Caster", position=(0, 1), faction="heroes")
    effect, zone = install_entry_cleanup_effect(caster, center=(2, 1))

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
    assert zone.zone_center == (4, 1)
    assert moved_positions != affected_positions
    assert center_tile.get_movement_cost(MovementMode.WALKING) == 1
    assert moved_center.get_movement_cost(MovementMode.WALKING) == 2
    assert EventQueue.get_spatial_handlers_at((4, 1))

    effect.retire()

    assert zone.name not in effect.active_conditions
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
    caster = create_skeleton(
        name="Zone Caster",
        position=(0, 1),
        faction="heroes",
    )
    cursor = EventQueue.event_cursor()

    install_entry_cleanup_effect(caster, center=(2, 1))

    by_lineage: dict[UUID, list[EventPhase]] = {}
    for _, event in EventQueue.iter_events_since(cursor):
        if event.event_type is not EventType.SPATIAL_TILE_CHANGED:
            continue
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


def test_eb_11_010_walkability_is_cost_driven_not_the_legacy_flag() -> None:
    """EB-11-010: GridMap walkability reads movement cost, not only tile.walkable."""
    reset_grid_state(width=2, height=1)
    grid = get_map()
    tile = grid.get_tile(1, 0)
    assert tile is not None

    tile.walkable = False
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


def test_eb_11_011_replacing_object_position_removes_old_grid_membership() -> None:
    """EB-11-011: placing the same object twice keeps one authoritative position."""
    reset_grid_state(width=4, height=1)
    grid = get_map()
    crate = BaseItem(
        source_entity_uuid=uuid4(),
        name="Crate",
        is_pickable=False,
    )

    grid.place_object(crate.uuid, (1, 0))
    grid.place_object(crate.uuid, (2, 0))

    assert grid.get_object_position(crate.uuid) == (2, 0)
    assert crate.uuid not in grid.get_objects_at((1, 0))
    assert crate.uuid in grid.get_objects_at((2, 0))


def test_eb_11_016_raw_object_removal_clears_item_floor_location_state() -> None:
    """EB-11-016: GridMap removal clears floor location without destroying items."""
    reset_grid_state(width=4, height=1)
    grid = get_map()
    observer = create_skeleton(name="Observer", position=(0, 0), faction="heroes")
    raw_item = BaseItem(source_entity_uuid=uuid4(), name="Raw Floor Item")
    raw_item.place_on_grid((1, 0))
    Entity.update_all_entities_senses(max_distance=20)

    raw_tile_uuid = raw_item.tile_uuid
    assert raw_tile_uuid is not None
    assert grid.get_object_position(raw_item.uuid) == (1, 0)
    assert raw_item.uuid in observer.senses.objects

    grid.remove_object(raw_item.uuid)

    assert grid.get_object_position(raw_item.uuid) is None
    assert raw_item.uuid not in grid.get_objects_at((1, 0))
    assert raw_item.uuid not in observer.senses.objects
    assert raw_item.tile_uuid is None
    assert raw_item.get_position() is None
    assert BaseBlock.get(raw_item.uuid) is raw_item

    lifecycle_item = BaseItem(source_entity_uuid=uuid4(), name="Lifecycle Floor Item")
    lifecycle_item.place_on_grid((2, 0))
    assert lifecycle_item.tile_uuid is not None

    lifecycle_item.destroy()

    assert grid.get_object_position(lifecycle_item.uuid) is None
    assert lifecycle_item.tile_uuid is None
    assert lifecycle_item.owner_uuid is None
    assert lifecycle_item.stored_in_uuid is None
    assert BaseBlock.get(lifecycle_item.uuid) is None
