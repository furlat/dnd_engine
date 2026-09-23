"""Physical pressure and exact linked consequences through native membership events."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import Jump, Move
from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.environment_item_builders import build_directional_door, build_standing_torch
from dnd.core.creature_types import DamageType
from dnd.core.events import EventPhase, EventQueue, SpatialEffectChangeEvent
from dnd.entity import Entity, EntityConfig
from dnd.items.environment_controls import control_value
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.spatial.portals import materialize_portal
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.spells.conjuration import MistyStep
from dnd.types.controls import ActivationLink, ControlLink
from dnd.types.traps import TrapState
from dnd.types.world import CardinalDirection, OccupancyLayer


@pytest.fixture
def game() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(10, 5))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def actor(game: Game, position: tuple[int, int]) -> Entity:
    creature = Entity.create(uuid4(), "Traveler", config=EntityConfig(position=position,
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
        action_economy=ActionEconomyConfig(spell_slots={2: 2}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence")))
    setup_standard_actions(creature)
    register_spell(creature, MistyStep, caster_level=3)
    creature.compose_entity()
    game.deploy_entity(creature, position)
    return creature


def edges(plate_uuid, cursor=0) -> list[bool]:
    return [event.pressed for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialEffectChangeEvent) and event.spatial_effect_uuid == plate_uuid
        and event.phase is EventPhase.COMPLETION and event.pressed is not None]


@pytest.mark.parametrize("target_kind", ("door", "light"))
def test_held_plate_tracks_all_ground_occupants_and_installation(game, target_kind):
    first = actor(game, (2, 1))
    second = actor(game, (1, 2))
    target = build_directional_door() if target_kind == "door" else build_standing_torch()
    if target_kind == "door":
        target.place_on_grid((8, 1), boundary_direction=CardinalDirection.EAST)
    else:
        target.place_on_grid((8, 1))
    plate = materialize_pressure_plate({(2, 1), (2, 2)},
        ControlLink(target_item_uuid=target.uuid, target_kind=target_kind))
    assert plate.pressed and edges(plate.uuid) == [True]
    assert control_value(target)
    Entity.update_entity_position(second, (2, 2))
    Entity.update_entity_position(first, (3, 1))
    assert plate.pressed and edges(plate.uuid) == [True]
    game.remove_entity(second.uuid)
    assert not plate.pressed and edges(plate.uuid) == [True, False]
    assert not control_value(target)


def test_multi_cell_walk_has_only_outer_press_and_release(game):
    traveler = actor(game, (0, 1))
    torch = build_standing_torch()
    torch.place_on_grid((8, 1))
    plate = materialize_pressure_plate({(1, 1), (2, 1)},
        ControlLink(target_item_uuid=torch.uuid, target_kind="light"))
    traveler.update_entity_senses()
    result = Move(source_entity_uuid=traveler.uuid, end_position=(3, 1),
        path=[(0, 1), (1, 1), (2, 1), (3, 1)], prefer_safe=False).apply()
    assert result is not None and not result.canceled
    assert edges(plate.uuid) == [True, False]
    assert not torch.is_lit


@pytest.mark.parametrize("movement,position,expected", (
    ("jump", (1, 1), []), ("jump", (3, 1), [True]),
    ("misty_step", (1, 1), []), ("misty_step", (3, 1), [True]),
))
def test_jump_and_teleport_press_only_at_ground_arrival(game, movement, position, expected):
    traveler = actor(game, (0, 1))
    torch = build_standing_torch()
    torch.place_on_grid((8, 1))
    plate = materialize_pressure_plate({position}, ControlLink(target_item_uuid=torch.uuid, target_kind="light"))
    traveler.update_entity_senses()
    command = Jump if movement == "jump" else MistyStep
    result = command(source_entity_uuid=traveler.uuid, end_position=(3, 1)).apply()
    assert result is not None and not result.canceled
    assert traveler.occupancy_layer is OccupancyLayer.GROUND
    assert edges(plate.uuid) == expected


def test_takeoff_releases_and_removal_withdraws_held_input(game):
    traveler = actor(game, (1, 1))
    torch = build_standing_torch()
    torch.place_on_grid((8, 1))
    plate = materialize_pressure_plate({(1, 1)}, ControlLink(target_item_uuid=torch.uuid, target_kind="light"))
    result = Jump(source_entity_uuid=traveler.uuid, end_position=(3, 1)).apply()
    assert result is not None and not result.canceled
    assert edges(plate.uuid) == [True, False]
    Entity.update_entity_position(traveler, (1, 1))
    assert torch.is_lit
    assert plate.deactivate()
    assert not torch.is_lit


def test_pulse_activates_spikes_without_lowering_them_on_release(game):
    traveler = actor(game, (0, 1))
    spikes = materialize_spike_trap_condition({(7, 1)}, trap_state=TrapState.READY)
    plate = materialize_pressure_plate({(1, 1)}, ActivationLink(target_condition_uuid=spikes.uuid))
    Entity.update_entity_position(traveler, (1, 1))
    assert spikes.trap_state is TrapState.ACTIVATED
    Entity.update_entity_position(traveler, (2, 1))
    assert not plate.pressed and spikes.trap_state is TrapState.ACTIVATED


def test_nested_transfer_releases_the_plate_without_a_duplicate_press(game):
    traveler = actor(game, (0, 1))
    portal = materialize_portal({(1, 1)}, (7, 1), trap_state=TrapState.READY)
    plate = materialize_pressure_plate({(1, 1)}, ActivationLink(target_condition_uuid=portal.uuid))
    Entity.update_entity_position(traveler, (1, 1))
    assert traveler.position == (7, 1)
    assert not plate.pressed
    # The portal can run before the sensor's entry callback. No stale entry may
    # manufacture pressure once the creature has already transferred away.
    assert edges(plate.uuid) in ([], [True, False])


def test_deployed_body_keeps_plate_pressed_until_removed(game):
    traveler = actor(game, (1, 1))
    torch = build_standing_torch()
    torch.place_on_grid((8, 1))
    plate = materialize_pressure_plate({(1, 1)}, ControlLink(target_item_uuid=torch.uuid, target_kind="light"))
    traveler.receive_damage(999, DamageType.BLUDGEONING, uuid4())
    assert traveler.is_deployed and plate.pressed and torch.is_lit
    assert edges(plate.uuid) == [True]
    game.remove_entity(traveler.uuid)
    assert not plate.pressed and not torch.is_lit
