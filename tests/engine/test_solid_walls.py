"""Ordinary walls expose real attacks and clear only their own native edge."""

from uuid import uuid4

import pytest

from dnd.actions_functional import get_available_actions, execute_available_action, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import (
    SOLID_WALL_MATERIALS, build_cliff_face, build_directional_wall,
)
from dnd.content.items.window_builders import build_window_component
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue, ItemDestructionEvent
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from dnd.game import Game
from dnd.types.world import CardinalDirection
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.world_authoring import set_world_tile_elevation
from dnd.world_facts import WorldFacts, apply_world_fact


@pytest.fixture
def arena():
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def review_actor(game: Game, name: str, position: tuple[int, int], *, strength: int = 10) -> Entity:
    """Compose the clothed sword bearer from the retired door-destruction scenarios."""
    actor = Entity.create(uuid4(), name, config=EntityConfig(position=position, faction="heroes",
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=strength)),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")])))
    setup_standard_actions(actor)
    install_body_response(actor, BLOOD_BODY_RESPONSE)
    actor.install_initial_items((
        (build_authored_item("weapon.longsword", actor.uuid), WeaponSlot.MELEE_MAIN),
        (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
        (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
    ))
    actor.compose_entity()
    game.deploy_entity(actor, position)
    return actor


@pytest.mark.parametrize("item_id", ("environment.directional_wall", *SOLID_WALL_MATERIALS))
@pytest.mark.parametrize("side", ((2, 2), (3, 2)))
def test_discovered_attacks_damage_then_clear_wall_from_either_side(arena, item_id, side):
    wall = build_authored_item(item_id, uuid4())
    wall.place_on_grid((2, 2), boundary_direction=CardinalDirection.EAST)
    actor = review_actor(arena, "Wall attacker", side, strength=18)
    actor.update_entity_senses()
    choices = [(row, choice) for row in get_available_actions(actor).all_actions
        if row.behavior_id == "action.attack" and row.weapon_slot == WeaponSlot.MELEE_MAIN.value
        for choice in row.valid_targets if choice.target_uuid == wall.uuid]
    assert choices, "The wall must be an attackable object from either incident support"
    row, choice = choices[0]
    hp = wall.get_hp()
    with fixed_dice_faces(19, 1):
        result = execute_available_action(actor, row, choice)
    assert result is not None and not result.canceled
    assert 0 < wall.get_hp() < hp
    assert not get_map().can_transition((2, 2), (3, 2), actor.uuid)
    wall.receive_damage(100, DamageType.BLUDGEONING, actor.uuid)
    wall.receive_damage(100, DamageType.BLUDGEONING, actor.uuid)
    assert wall.integrity is ItemIntegrity.DESTROYED
    assert get_map().can_transition((2, 2), (3, 2), actor.uuid)
    assert wall.get_boundary_structure().blocked_channels == ()
    assert not wall.get_world_placement_spec().occupies_bands
    completions = [event for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, ItemDestructionEvent) and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == wall.uuid]
    assert len(completions) == 1


def test_destroying_one_raised_corner_leg_preserves_other_edge_and_attachment_cascades(arena):
    for position in ((2, 2), (3, 2), (2, 3)):
        set_world_tile_elevation(position, author_uuid=uuid4(), height=2,
            surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    east, north = build_directional_wall(), build_directional_wall()
    east.place_on_grid((2, 2), boundary_direction=CardinalDirection.EAST)
    north.place_on_grid((2, 2), boundary_direction=CardinalDirection.NORTH)
    child = build_window_component("environment.window.fantasy_g9", insert=True,
        source_entity_uuid=uuid4(), supported_by_uuid=east.uuid)
    child.place_on_grid((2, 2), boundary_direction=CardinalDirection.EAST)
    east.receive_damage(100, DamageType.BLUDGEONING, uuid4())
    assert north.integrity is ItemIntegrity.INTACT
    assert child.integrity is ItemIntegrity.DESTROYED
    assert get_map().can_transition((2, 2), (3, 2))
    assert not get_map().can_transition((2, 2), (2, 3))
    facts = WorldFacts()
    for _, event in EventQueue.iter_events_since(0):
        apply_world_fact(facts, event)
    for identity in (east.uuid, child.uuid):
        remnant = facts.objects[identity]
        assert remnant.item.integrity is ItemIntegrity.DESTROYED
        assert remnant.placement.position == (2, 2)
        assert remnant.placement.boundary_direction is CardinalDirection.EAST
        assert remnant.placement.base_height_steps == 2


def test_terrain_cliff_remains_nonbreakable(arena):
    cliff = build_cliff_face()
    assert not cliff.is_breakable()
    assert cliff.health is None and cliff.destruction_profile is None
