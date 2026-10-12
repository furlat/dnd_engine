"""Disclosed item light after-values survive the player boundary unchanged."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.content.items.environment_item_builders import build_wall_torch
from dnd.core.events import EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.torches import build_torch
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.projection import begin_projection, project_lineage
from dnd.player.event_record import RecordedEvent
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from pydantic import TypeAdapter


@pytest.fixture
def world():
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    actors = []
    for name, position in (("Carrier", (5, 5)), ("Witness", (6, 5))):
        actor = Entity.create(uuid4(), name, config=EntityConfig(position=position))
        actor.compose_entity()
        game.deploy_entity(actor, position)
        actors.append(actor)
    try:
        yield built, actors
    finally:
        game.close()
        reset_engine_runtime()


def capture(built, observer):
    return capture_interval(name="source-light projection", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=observer.uuid,
        battlefield_id=built.definition.battlefield_id)


def test_fixed_source_overrides_and_native_activation_survive_reduction(world):
    built, (owner, _) = world
    torch = build_wall_torch()
    torch.very_bright_radius_feet = 7
    torch.bright_radius_feet = 17
    torch.dim_radius_feet = 23
    torch.place_on_grid((5, 6))
    owner.update_entity_senses(max_distance=8)
    projection, initial = begin_projection(capture(built, owner))
    state = reduce_initialization(initial)
    assert state.objects[torch.uuid].item.is_lit is False
    for lit in (True, False, True):
        action = next(row for row in owner.get_available_actions().all_actions
            if row.source_item_uuid == torch.uuid)
        root = execute_use_action(owner, torch.uuid, action.template_name)
        assert root is not None and not root.canceled
        for native in capture_lineages((root,), observer_uuid=owner.uuid,
                known_actor_uuids=frozenset(state.actors)):
            assert not native.dispositions
            packet = project_lineage(projection, native)
            if packet is not None:
                state = reduce_lineage(state, packet)
        item = state.objects[torch.uuid].item
        assert (item.is_lit, item.very_bright_radius_feet,
            item.bright_radius_feet, item.dim_radius_feet) == (lit, 7, 17, 23)


def test_carried_source_keeps_inventory_private_to_controller(world):
    built, (owner, witness) = world
    torch = build_torch(owner.uuid)
    torch.bright_radius_feet = 35
    torch.dim_radius_feet = 15
    assert owner.loot_item(torch)
    views = {}
    for observer in (owner, witness):
        observer.update_entity_senses(max_distance=8)
        projection, initial = begin_projection(capture(built, observer))
        views[observer.uuid] = projection, reduce_initialization(initial)
    for lit in (True, False, True):
        root = execute_use_action(owner, torch.uuid, "Ignite Torch" if lit else "Extinguish Torch")
        assert root is not None and not root.canceled
        for observer in (owner, witness):
            projection, state = views[observer.uuid]
            for native in capture_lineages((root,), observer_uuid=observer.uuid,
                    known_actor_uuids=frozenset(state.actors)):
                assert not native.dispositions
                codec = TypeAdapter(tuple[RecordedEvent, ...])
                restored = codec.validate_json(codec.dump_json(native.events))
                assert tuple(type(row) for row in restored) == tuple(type(row) for row in native.events)
                packet = project_lineage(projection, native)
                if packet is not None:
                    state = reduce_lineage(state, packet)
            views[observer.uuid] = projection, state
            actor = state.actors[owner.uuid]
            assert not any(row.item_uuid == torch.uuid for row in actor.visual_loadout.layers)
            if observer is owner:
                item = next(row for row in actor.controlled_items if row.item_uuid == torch.uuid)
                assert (item.is_lit, item.bright_radius_feet, item.dim_radius_feet) == (lit, 35, 15)
            else:
                assert actor.controlled_items is None
                assert torch.uuid not in state.objects


@pytest.mark.parametrize("lit", (False, True))
def test_disclosed_equipment_source_after_values_preserve_activation(world, lit):
    # Value-boundary test: portable torches are intentionally not equippable.
    # Supply an admitted equipment record to test the general VisualItem DTO;
    # this does not claim that the native torch supports an equip command.
    built, (owner, witness) = world
    torch = build_torch(owner.uuid)
    assert owner.loot_item(torch)
    witness.update_entity_senses(max_distance=8)
    captured = capture(built, witness)
    admitted = []
    for row in captured.admissions:
        if row.actor.uuid == owner.uuid:
            item = torch.to_item_presentation_state().model_copy(update={
                "is_lit": lit, "very_bright_radius_feet": 6,
                "bright_radius_feet": 19, "dim_radius_feet": 31})
            row = replace(row, actor=replace(row.actor, items=(item,),
                equipment=(("weapon_melee_off", torch.uuid),)))
        admitted.append(row)
    _, initial = begin_projection(replace(captured, admissions=tuple(admitted)))
    state = reduce_initialization(initial)
    actor = state.actors[owner.uuid]
    source, = actor.visual_loadout.layers
    assert actor.controlled_items is None
    assert (source.is_lit, source.very_bright_radius_feet,
        source.bright_radius_feet, source.dim_radius_feet) == (lit, 6, 19, 31)
