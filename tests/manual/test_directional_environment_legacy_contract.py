"""Maintained directional wall/door regressions displaced by the d80 rework."""

from uuid import uuid4

from dnd.actions import Attack, AttackEvent
from dnd.actions_functional import execute_use_action, setup_standard_actions
from dnd.blocks.equipment import Weapon
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_block import BaseBlock
from dnd.core.events import (
    EventPhase,
    EventQueue,
    EventType,
    SpatialChangeEvent,
    StepMovementEvent,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.runtime_reset import reset_engine_runtime
from dnd.entity import Entity
from dnd.items.environment import (
    CloseDirectionalDoorAction,
    DirectionalDoor,
    DirectionalWall,
)
from dnd.items.environment_content import directional_door_recipe
from dnd.maps.arena_layout import (
    DOOR_POSITION,
    WALL_DIRECTIONS,
    WALL_POSITIONS,
    build_standard_arena_environment,
)
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.items.weapons import SHORTBOW_RECIPE
from dnd.reactions import opportunity_attack_processor
from server.mapeditor_support import (
    build_forgotten_crypt_arena_map,
    reset_editor_world,
)
from dnd.utils import reset_combat_state


def _reset_directional_scene() -> None:
    reset_combat_state()
    get_map().create_rectangle(0, 0, 9, 7)


def _assert_standard_directional_barrier() -> None:
    grid = get_map()
    door_objects = [
        BaseBlock.get(object_uuid)
        for object_uuid in grid.get_objects_at(DOOR_POSITION)
    ]
    doors = [obj for obj in door_objects if isinstance(obj, DirectionalDoor)]
    assert len(doors) == 1
    assert not doors[0].is_open
    assert set(doors[0].blocked_directions) == set(WALL_DIRECTIONS)
    assert not grid.can_transition((6, 7), (7, 7))
    assert grid.can_transition((8, 7), (7, 7))

    for position in WALL_POSITIONS:
        tile = grid.get_tile(*position)
        wall_objects = [
            BaseBlock.get(object_uuid)
            for object_uuid in grid.get_objects_at(position)
        ]
        walls = [obj for obj in wall_objects if isinstance(obj, DirectionalWall)]
        assert tile is not None
        assert tile.walkable
        assert tile.visible
        assert len(walls) == 1
        assert set(walls[0].blocked_directions) == set(WALL_DIRECTIONS)
        assert not grid.can_transition((position[0] - 1, position[1]), position)
        assert grid.can_transition((position[0] + 1, position[1]), position)


def test_live_and_editor_standard_builders_share_directional_barrier_contract() -> None:
    """Both public builders instantiate typed directional structures, not scalar walls."""
    build_standard_arena_environment(reset_engine_runtime())
    _assert_standard_directional_barrier()

    reset_editor_world()
    build_forgotten_crypt_arena_map()
    _assert_standard_directional_barrier()
    assert Entity.get_all_entities() == []


def test_directional_wall_blocks_only_declared_sides_and_stays_structural() -> None:
    """Walls route four spatial channels but never become player actions."""
    _reset_directional_scene()
    grid = get_map()
    hero = create_goblin(
        name="Directional Observer",
        position=(1, 3),
        faction="heroes",
    )
    setup_standard_actions(hero)
    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
        blocked_directions=("east",),
    )
    grid.place_object(wall.uuid, (2, 3))
    Entity.update_all_entities_senses(max_distance=50)

    assert grid.is_walkable(2, 3)
    assert not wall.blocks_walking()
    assert not wall.blocks_vision()
    assert not grid.can_transition((2, 3), (3, 3))
    assert not grid.can_see_transition((2, 3), (3, 3))
    assert not grid.can_light_transition((2, 3), (3, 3))
    assert not grid.can_propagate_transition((2, 3), (3, 3))
    assert grid.can_transition((2, 3), (1, 3))
    assert grid.can_transition((2, 3), (2, 4))
    assert (3, 3) not in set(grid.compute_fov((2, 3), max_distance=4))
    assert (3, 3) not in set(grid.compute_light_fov((2, 3), max_distance=4))
    assert (3, 3) not in set(
        grid.compute_propagation_fov((2, 3), max_distance=4)
    )
    assert wall.uuid not in hero.senses.objects
    available = hero.get_available_actions()
    assert all(
        target.target_uuid != wall.uuid
        for action in available.object_actions
        for target in action.valid_targets
    )
    assert all(
        action.source_item_uuid != wall.uuid
        for action in available.all_actions
    )


def test_directional_door_open_event_preserves_other_sides_and_rejects_close_occupancy() -> None:
    """Opening changes its configured plane; occupied closing is atomic."""
    _reset_directional_scene()
    grid = get_map()
    hero = create_goblin(
        name="Door User",
        position=(1, 3),
        faction="heroes",
    )
    setup_standard_actions(hero)
    hidden_target = create_skeleton(
        name="Behind Door",
        position=(5, 3),
        faction="monsters",
    )
    door = materialize_item(
        directional_door_recipe(
            blocked_directions=("east",),
        ),
        uuid4(),
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalDoor,
    )
    grid.place_object(door.uuid, (2, 3))
    door.set_directional_blocking("movement", "west", True)
    Entity.update_all_entities_senses(max_distance=50)

    assert not door.is_open
    assert not grid.can_transition((2, 3), (3, 3))
    assert hidden_target.uuid not in hero.senses.entities
    assert door.uuid in hero.senses.objects
    assert [action.name for action in door.get_use_actions(hero.uuid)] == [
        "Open Door"
    ]
    cursor = EventQueue.event_cursor()

    result = execute_use_action(hero, door.uuid, "Open Door")
    Entity.update_all_entities_senses(max_distance=50)

    assert result is not None
    assert not result.canceled
    assert door.is_open
    assert grid.can_transition((2, 3), (3, 3))
    assert not grid.can_transition((2, 3), (1, 3))
    assert hidden_target.uuid in hero.senses.entities
    events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_OBJECT_CHANGED
        and event.phase is EventPhase.DECLARATION
    ]
    assert len(events) == 1
    event = events[0]
    assert event.object_is_open is True
    assert event.directional_position == (2, 3)
    assert event.directional_directions == ["east"]
    assert set(event.directional_channels or []) == {
        "movement",
        "vision",
        "light",
        "propagation",
    }
    assert event.directional_blocks_movement is not None
    assert event.directional_blocks_movement["east"] is False

    Entity.update_entity_position(hero, (2, 3))
    close = CloseDirectionalDoorAction(
        source_entity_uuid=hero.uuid,
        source_item_uuid=door.uuid,
    ).apply()

    assert close is not None
    assert close.canceled
    assert door.is_open
    assert door.get_use_actions(hero.uuid) == []


def test_directional_propagation_wall_removes_threat_and_opportunity_attack() -> None:
    """Threat, OA, and ranged-threat state all use the propagation channel."""
    _reset_directional_scene()
    grid = get_map()
    threatening_enemy = create_skeleton(
        name="Directional Threat",
        position=(3, 3),
        faction="monsters",
    )
    mover = create_goblin(
        name="Directional Mover",
        position=(4, 3),
        faction="heroes",
    )
    setup_standard_actions(mover)
    Entity.update_all_entities_senses(max_distance=50)
    assert mover.is_threatened()

    screen = DirectionalWall(
        source_entity_uuid=uuid4(),
        blocked_directions=("east",),
        blocked_channels=("propagation",),
    )
    grid.place_object(screen.uuid, threatening_enemy.position)
    Entity.update_all_entities_senses(max_distance=50)

    assert not mover.is_threatened()
    assert mover.position not in threatening_enemy.senses.get_threathened_positions()
    cursor = EventQueue.event_cursor()
    step = StepMovementEvent(
        source_entity_uuid=mover.uuid,
        source_entity_name=mover.name,
        from_position=mover.position,
        to_position=(5, 3),
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    opportunity_attack_processor(step, threatening_enemy.uuid)
    assert [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.ATTACK
    ] == []

    _reset_directional_scene()
    grid = get_map()
    archer = create_skeleton(
        name="Directional Archer",
        position=(4, 3),
        faction="heroes",
    )
    archer.equipment.equip(
        materialize_item(
            SHORTBOW_RECIPE,
            archer.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.RANGED_MAIN,
    )
    adjacent_enemy = create_goblin(
        name="Directional Adjacent Enemy",
        position=(3, 3),
        faction="monsters",
    )
    far_target = create_goblin(
        name="Directional Far Target",
        position=(7, 3),
        faction="monsters",
    )
    Entity.update_all_entities_senses(max_distance=50)
    assert archer.is_threatened()
    ranged_screen = DirectionalWall(
        source_entity_uuid=uuid4(),
        blocked_directions=("east",),
        blocked_channels=("propagation",),
    )
    grid.place_object(ranged_screen.uuid, adjacent_enemy.position)
    Entity.update_all_entities_senses(max_distance=50)
    assert not archer.is_threatened()
    attack = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=far_target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
    )
    declaration = attack._create_declaration_event(use_register=False)
    validated = attack._validate(declaration) if isinstance(declaration, AttackEvent) else None

    assert validated is not None
    assert not validated.is_threatened
