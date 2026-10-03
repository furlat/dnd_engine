"""Fixed window assemblies expose real damage, boundary and traversal behavior."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import Attack, TraverseConnector
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.content.items.window_builders import place_window
from dnd.content.items.window_definitions import WINDOW_DEFINITIONS
from dnd.core.base_block import BaseBlock, LightLevel
from dnd.core.base_tiles import Tile
from dnd.core.creature_types import DamageType, Size
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, ItemDestructionEvent, SpatialChangeEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection
from dnd.world_facts import WorldFacts, apply_world_fact


@pytest.fixture
def arena() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def actor(game: Game, *, size: Size = Size.MEDIUM, position: tuple[int, int] = (2, 2)) -> Entity:
    entity = Entity.create(uuid4(), "Window tester", config=EntityConfig(position=position, size=size,
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=2, mode="maximums")])))
    setup_standard_actions(entity)
    entity.install_initial_items(((build_authored_item("weapon.greataxe", entity.uuid), WeaponSlot.MELEE_MAIN),))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def passage(entity: Entity) -> list:
    Entity.update_all_entities_senses()
    return TraverseConnector(source_entity_uuid=entity.uuid).get_discovery_variants(entity)


@pytest.mark.parametrize("family", tuple(WINDOW_DEFINITIONS))
def test_every_family_builds_targetable_components_and_parent_cascades_once(arena: Game, family: str) -> None:
    assembly = place_window(family, (2, 2), CardinalDirection.EAST)
    assert assembly.wall.is_breakable()
    if assembly.insert is not None:
        assert assembly.insert.is_breakable() and assembly.insert.supported_by_uuid == assembly.wall.uuid
    assembly.wall.receive_damage(100, DamageType.BLUDGEONING, uuid4())
    assembly.wall.receive_damage(100, DamageType.BLUDGEONING, uuid4())
    identities = {assembly.wall.uuid} | ({assembly.insert.uuid} if assembly.insert else set())
    completions = [e for _, e in EventQueue.iter_events_since(0)
        if isinstance(e, ItemDestructionEvent) and e.phase is EventPhase.COMPLETION]
    assert {e.target_entity_uuid for e in completions} == identities
    assert len(completions) == len(identities)
    assert get_map().can_transition((2, 2), (3, 2))
    assert not get_map().get_connectors_at((2, 2))
    facts = WorldFacts()
    for _, event in EventQueue.iter_events_since(0):
        apply_world_fact(facts, event)
    assert all(BaseBlock.get(identity) is not None for identity in identities)
    assert all(facts.objects[identity].item.integrity is ItemIntegrity.DESTROYED for identity in identities)
    if assembly.insert is not None:
        assert assembly.insert.integrity is ItemIntegrity.DESTROYED
        assert facts.objects[assembly.insert.uuid].item.supported_by_uuid == assembly.wall.uuid


@pytest.mark.parametrize("side", ((2, 2), (3, 2)))
def test_insert_can_be_smashed_from_either_side_without_harming_frame(arena: Game, side: tuple[int, int]) -> None:
    assembly = place_window("environment.window.fantasy_g8", (2, 2), CardinalDirection.EAST)
    entity = actor(arena, position=side)
    assert assembly.insert is not None
    hp = assembly.wall.get_hp()
    with fixed_dice_faces(19, 12):
        entity.update_entity_senses()
        result = Attack(weapon_slot=WeaponSlot.MELEE_MAIN, source_entity_uuid=entity.uuid, target_entity_uuid=assembly.insert.uuid).apply()
    assert result is not None and not result.canceled, result.status_message if result is not None else None
    assert assembly.insert.integrity is ItemIntegrity.DESTROYED
    assert assembly.wall.get_hp() == hp
    assert not get_map().can_transition((2, 2), (3, 2), entity.uuid)
    assert len(passage(entity)) == 1


@pytest.mark.parametrize("cost", (1, 2))
def test_cleared_aperture_costs_twice_normal_terrain_and_moves_once(arena: Game, cost: int) -> None:
    grid = get_map()
    grid.set_tile(3, 2, tile=Tile.create((3, 2), walking_cost=cost))
    place_window("environment.window.fantasy_g7", (2, 2), CardinalDirection.EAST)
    entity = actor(arena)
    before = entity.action_economy.movement_remaining()
    choices = passage(entity)
    assert len(choices) == 1
    result = choices[0].apply()
    assert result is not None and not result.canceled
    assert entity.position == (3, 2)
    assert entity.action_economy.movement_remaining() == before - 10 * cost


def test_grille_size_and_opposite_wall_each_gate_traversal(arena: Game) -> None:
    assembly = place_window("environment.window.fantasy_a4", (2, 2), CardinalDirection.EAST)
    entity = actor(arena, size=Size.SMALL)
    assert not passage(entity)
    assert assembly.insert is not None
    assembly.insert.receive_damage(100, DamageType.BLUDGEONING, entity.uuid)
    assert len(passage(entity)) == 1
    blocker = build_directional_wall()
    blocker.place_on_grid((3, 2), boundary_direction=CardinalDirection.WEST)
    choices = passage(entity)
    before = entity.action_economy.movement_remaining()
    for choice in choices:
        result = choice.apply()
        assert result is not None and result.canceled
    assert entity.position == (2, 2) and entity.action_economy.movement_remaining() == before
    blocker.retire()
    entity.size = Size.MEDIUM
    assert not passage(entity)


def test_stale_crossing_revalidates_before_spending_and_cold_wreck_has_no_break(arena: Game) -> None:
    assembly = place_window("environment.window.fantasy_g8", (2, 2), CardinalDirection.EAST,
        insert_destroyed=True)
    entity = actor(arena)
    choice = passage(entity)[0]
    before = entity.action_economy.movement_remaining()
    assembly.wall.receive_damage(100, DamageType.BLUDGEONING, entity.uuid)
    result = choice.apply()
    assert result is not None and result.canceled
    assert entity.position == (2, 2) and entity.action_economy.movement_remaining() == before
    assert assembly.insert is not None
    assert not [e for _, e in EventQueue.iter_events_since(0)
                if isinstance(e, ItemDestructionEvent) and e.target_entity_uuid == assembly.insert.uuid]


def test_parent_removal_and_rejected_assembly_leave_no_orphan(arena: Game) -> None:
    assembly = place_window("environment.window.fantasy_g9", (2, 2), CardinalDirection.EAST)
    assert assembly.insert is not None
    assert get_map().remove_object(assembly.wall.uuid)
    assert BaseBlock.get(assembly.insert.uuid) is None
    assert not get_map().get_connectors_at((2, 2))
    before = get_map().iter_object_placements()

    def reject(event: Event, _source_uuid) -> Event:
        return event.cancel("No passage here")

    handler = EventHandler(name="Reject passage", source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED, event_phase=EventPhase.DECLARATION)],
        event_processor=reject)
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(ValueError, match="registration was canceled"):
            place_window("environment.window.fantasy_g9", (2, 2), CardinalDirection.EAST)
    finally:
        EventQueue.remove_event_handler(handler)
    assert get_map().iter_object_placements() == before


def test_canceled_child_removal_preserves_entire_registered_assembly(arena: Game) -> None:
    assembly = place_window("environment.window.fantasy_g9", (2, 2), CardinalDirection.EAST)
    assert assembly.insert is not None
    insert_uuid = assembly.insert.uuid

    def reject(event: Event, _source_uuid) -> Event:
        return event.cancel("Insert retained") if isinstance(event, SpatialChangeEvent) and event.object_uuid == insert_uuid else event

    handler = EventHandler(name="Retain insert", source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_REMOVED, event_phase=EventPhase.DECLARATION)],
        event_processor=reject)
    EventQueue.add_event_handler(handler)
    try:
        assembly.wall.retire()
        assert BaseBlock.get(insert_uuid) is assembly.insert
        assert BaseBlock.get(assembly.wall.uuid) is assembly.wall
        assert get_map().get_object_placement(insert_uuid) is not None
        assert get_map().get_object_placement(assembly.wall.uuid) is not None
    finally:
        EventQueue.remove_event_handler(handler)


def test_shutter_break_recomputes_existing_light_and_projectile_boundary(arena: Game) -> None:
    grid = get_map()
    for x in range(8):
        for y in range(8):
            grid.set_tile_base_light((x, y), LightLevel.DARKNESS)
    assembly = place_window("environment.window.fantasy_g9", (2, 2), CardinalDirection.EAST)
    grid.add_light_source((2, 2), bright_radius_feet=5, dim_radius_feet=0)
    far = grid.get_tile(3, 2)
    assert far is not None and far.resolved_light_level is LightLevel.DARKNESS
    assert not grid.can_propagate_transition((2, 2), (3, 2))
    assert assembly.insert is not None
    assembly.insert.receive_damage(100, DamageType.BLUDGEONING, uuid4())
    assert far.resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert grid.can_propagate_transition((2, 2), (3, 2))
    assert not grid.can_transition((2, 2), (3, 2))


@pytest.mark.parametrize("rejection", (EventType.SPATIAL_OBJECT_PLACED, EventType.TRAVERSAL_CONNECTOR_CHANGED))
def test_rejected_composition_is_atomic_even_when_removal_is_vetoed(arena: Game, rejection: EventType) -> None:
    before = get_map().iter_object_placements()
    placed = 0

    def reject(event: Event, _source_uuid) -> Event:
        nonlocal placed
        if event.event_type is EventType.SPATIAL_OBJECT_REMOVED:
            return event.cancel("Removal forbidden")
        if event.event_type is EventType.SPATIAL_OBJECT_PLACED:
            placed += 1
            if placed != 2:
                return event
        return event.cancel("Assembly rejected")

    handler = EventHandler(name="Reject assembly without rollback", source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(event_type=rejection, event_phase=EventPhase.DECLARATION),
            Trigger(event_type=EventType.SPATIAL_OBJECT_REMOVED, event_phase=EventPhase.DECLARATION)],
        event_processor=reject)
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(ValueError):
            place_window("environment.window.fantasy_g9", (2, 2), CardinalDirection.EAST)
    finally:
        EventQueue.remove_event_handler(handler)
    assert get_map().iter_object_placements() == before
    assert not get_map().get_connectors_at((2, 2))
