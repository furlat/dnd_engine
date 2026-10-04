"""Real fire casts ignite only existing admitted material contacts."""

import pytest

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell
from dnd.actions import ActionEvent
from dnd.actions import SpellEvent
from dnd.blocks.base_item import BaseItem
from dnd.content.items.environment_item_builders import build_authored_door
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, SpatialEffectInteractionEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spells.abjuration import GlobeOfInvulnerability
from dnd.spells.conjuration import WebZone
from dnd.spells.evocation import BurningHands, Fireball, FireBolt, LightningBolt
from dnd.spells.walls import WallOfFire
from dnd.spatial.environmental_conditions import BurningWeb, FireSurface, OilSurface, WetSurface
from dnd.types.world import CardinalDirection, OccupancyLayer
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


@pytest.fixture
def caster():
    reset_spell_regression_arena(16, 16)
    return create_spell_regression_actor("Caster", (1, 1), "heroes", spell_slots={1: 2, 3: 2, 4: 2})


def surface(caster, cells, condition_type=OilSurface):
    material = condition_type(source_entity_uuid=caster.uuid, position=min(cells), affected_positions=set(cells))
    result = material.activate(parent_event=ActionEvent(source_entity_uuid=caster.uuid, phase=EventPhase.EFFECT))
    assert result is not None and not result.canceled and material.applied
    return material


def burning_cells(condition_type=FireSurface):
    return {cell for row in get_map().get_spatial_conditions()
            if isinstance(row, condition_type) for cell in row.affected_positions}


def completed_interactions(cursor):
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SpatialEffectInteractionEvent) and event.phase is EventPhase.COMPLETION]


def descendants(event):
    for child in event.get_children_events():
        yield child
        yield from descendants(child)


def test_empty_fireball_ignites_reached_oil_without_spreading_beyond_its_area(caster):
    material = surface(caster, {(6, 6), (7, 6), (11, 6)})
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([4] * 200)):
        cast = Fireball(source_entity_uuid=caster.uuid, end_position=(6, 6)).apply()
    assert cast is not None and not cast.canceled
    assert burning_cells() == {(6, 6), (7, 6)} and material.affected_positions == {(11, 6)}
    assert len(completed_interactions(cursor)) == 1
    events = descendants(cast)
    assert any(isinstance(event, SpatialEffectInteractionEvent) for event in events)


def test_burning_hands_is_discoverable_without_creatures_and_ignites_only_its_cone(caster):
    material = surface(caster, {(3, 1), (1, 4)})
    register_spell(caster, BurningHands)
    caster.update_entity_senses()
    options = [(action, target) for action in get_available_actions(caster).all_actions
               if action.behavior_id == "spell.burning_hands" for target in action.valid_targets
               if target.position == (2, 1)]
    assert options
    with fixed_dice_faces(*([4] * 200)):
        cast = execute_available_action(caster, *options[0])
    assert cast is not None and not cast.canceled
    assert burning_cells() == {(3, 1)} and material.affected_positions == {(1, 4)}


@pytest.mark.parametrize("miss,air", [(False, False), (True, False), (False, True)])
def test_fire_bolt_hit_contact_does_not_ignite_ground_on_miss_or_air_target(caster, miss, air):
    target = create_spell_regression_actor("Target", (4, 1), "monsters")
    if air:
        Entity.update_entity_position(target, target.position, occupancy_layer=OccupancyLayer.AIR)
    material = surface(caster, {(4, 1), (5, 1)})
    with fixed_dice_faces(1 if miss else 19, *([4] * 200)):
        cast = FireBolt(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert cast is not None and not cast.canceled
    assert burning_cells() == (set() if miss or air else {(4, 1)})
    assert material.affected_positions == ({(4, 1), (5, 1)} if miss or air else {(5, 1)})


def test_fireball_transforms_web_to_its_existing_short_lived_fire(caster):
    web = surface(caster, {(6, 6), (11, 6)}, WebZone)
    with fixed_dice_faces(*([4] * 200)):
        cast = Fireball(source_entity_uuid=caster.uuid, end_position=(6, 6)).apply()
    assert cast is not None and not cast.canceled
    assert burning_cells(BurningWeb) == {(6, 6)} and web.affected_positions == {(11, 6)}
    fire = next(row for row in get_map().get_spatial_conditions() if isinstance(row, BurningWeb))
    assert fire.duration.duration == 1


def test_wall_flames_ignite_oil_but_its_heat_band_does_not(caster):
    material = surface(caster, {(6, 6), (6, 7)})
    with fixed_dice_faces(*([4] * 200)):
        cast = WallOfFire(source_entity_uuid=caster.uuid, end_position=(4, 6), extra_target_positions=[(8, 6)]).apply()
    assert cast is not None and not cast.canceled
    assert burning_cells() == {(6, 6)} and material.affected_positions == {(6, 7)}
    assert any(isinstance(event, SpatialEffectInteractionEvent) for event in descendants(cast))
    terminals = {event.lineage_uuid: index for index, event in EventQueue.iter_events_since(0)
                 if event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)}
    assert all(terminals[event.lineage_uuid] < terminals[event.parent_lineage]
               for event in descendants(cast)), "Ignition descendants finish before their parent terminals"


@pytest.mark.parametrize("spell_type", (Fireball, BurningHands))
def test_globe_protects_materials_from_external_low_level_fire(caster, spell_type):
    Entity.update_entity_position(caster, (4, 7))
    protector = create_spell_regression_actor("Protector", (7, 7), "allies", spell_slots={6: 1})
    with fixed_dice_faces(*([4] * 200)):
        globe = GlobeOfInvulnerability(source_entity_uuid=protector.uuid).apply()
    assert globe is not None and not globe.canceled
    oil = surface(caster, {(6, 7)})
    with fixed_dice_faces(*([4] * 200)):
        cast = spell_type(source_entity_uuid=caster.uuid, end_position=(7, 7)).apply()
    assert cast is not None and not cast.canceled
    assert not burning_cells() and oil.applied and oil.affected_positions == {(6, 7)}


def test_fireball_does_not_create_fire_on_water_or_unoccupied_floor(caster):
    water = surface(caster, {(6, 6)}, WetSurface)
    with fixed_dice_faces(*([4] * 200)):
        cast = Fireball(source_entity_uuid=caster.uuid, end_position=(6, 6)).apply()
    assert cast is not None and not cast.canceled
    assert not burning_cells() and water.applied


@pytest.mark.parametrize("breaks", (False, True))
def test_fireball_ignites_behind_a_door_only_after_that_door_breaks(breaks):
    reset_spell_regression_arena(12, 1)
    caster = create_spell_regression_actor("Caster", (0, 0), "heroes", spell_slots={3: 1})
    oil = surface(caster, {(4, 0)})
    door = build_authored_door("environment.door.desert_c7", hit_points=4 if breaks else 100)
    door.place_on_grid((3, 0), boundary_direction=CardinalDirection.WEST)
    with fixed_dice_faces(*([1] * 200)):
        cast = Fireball(source_entity_uuid=caster.uuid, end_position=(1, 0)).apply()
    assert cast is not None and not cast.canceled
    assert burning_cells() == ({(4, 0)} if breaks else set())
    assert oil.applied is not breaks
    assert any(isinstance(event, SpatialEffectInteractionEvent) and (4, 0) in event.positions
               for event in descendants(cast)) is breaks


@pytest.mark.parametrize("cancel_operation", (False, True))
def test_canceled_fire_cast_or_ignition_declaration_does_not_transform_oil(caster, cancel_operation):
    oil = surface(caster, {(6, 6)})
    def stop(event, _source):
        return event.cancel(status_message="Fire rejected")
    EventQueue.add_event_handler(EventHandler(name="Stop fire", source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_EFFECT_INTERACTION if cancel_operation else EventType.CAST_SPELL,
            event_phase=EventPhase.DECLARATION if cancel_operation else EventPhase.EFFECT)], event_processor=stop))
    with fixed_dice_faces(*([4] * 200)):
        cast = Fireball(source_entity_uuid=caster.uuid, end_position=(6, 6)).apply()
    assert isinstance(cast, SpellEvent) and cast.canceled is not cancel_operation
    assert not burning_cells() and oil.applied


def test_fire_bolt_object_contact_ignites_existing_oil_before_destruction(caster):
    target = build_authored_item("environment.furniture.clay_stove", caster.uuid)
    target.health = BaseItem.create_item_health(target.uuid, 1)
    target.place_on_grid((4, 1))
    oil = surface(caster, {(4, 1), (5, 1)})
    Entity.update_all_entities_senses()
    with fixed_dice_faces(19, *([4] * 200)):
        cast = FireBolt(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert cast is not None and not cast.canceled
    assert not target.is_breakable() and burning_cells() == {(4, 1)}
    assert oil.affected_positions == {(5, 1)}


def test_lightning_bolt_ignites_only_its_admitted_empty_line(caster):
    material = surface(caster, {(3, 1), (3, 2)})
    register_spell(caster, LightningBolt)
    caster.update_entity_senses()
    options = [(action, target) for action in get_available_actions(caster).all_actions
               if action.behavior_id == 'spell.lightning_bolt' for target in action.valid_targets
               if target.position == (2, 1)]
    assert options
    result = execute_available_action(caster, *options[0])
    assert isinstance(result, SpellEvent) and not result.canceled
    assert (3, 1) in (result.resolved_area_positions or ())
    assert (3, 2) not in (result.resolved_area_positions or ())
    assert burning_cells() == {(3, 1)} and material.affected_positions == {(3, 2)}
