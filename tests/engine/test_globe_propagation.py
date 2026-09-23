"""Native blast reach and attributable Globe suppression, including floor state."""

import pytest
from dataclasses import replace
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.residues import ASHEN_RESIDUE, POISON_RESIDUE, deposit_residue
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.core.aoe import Sphere
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import GlobeOfInvulnerability, GlobeZone
from dnd.spells.evocation import Fireball
from dnd.spells.ice_knife import IceKnife, ICE_KNIFE_BURST
from dnd.types.world import CardinalDirection
from tests.manual.spell_regression_support import (
    create_spell_regression_actor, force_save_result, reset_spell_regression_arena,
)


@pytest.fixture(autouse=True)
def arena():
    reset_spell_regression_arena(24, 17)
    yield
    reset_engine_runtime()


@pytest.mark.parametrize("opening, expected_count", [(False, 36), (True, 49)])
def test_fireball_spreads_around_open_doorway_within_original_radius(opening, expected_count):
    caster = create_spell_regression_actor("Caster", (5, 8), "heroes", spell_slots={3: 1})
    for y in range(4, 13):
        if opening and y == 8:
            continue
        build_directional_wall().place_on_grid((6, y), boundary_direction=CardinalDirection.EAST)
    Entity.update_all_entities_senses(max_distance=120)
    spell = Fireball(source_entity_uuid=caster.uuid, end_position=(5, 8))
    with fixed_dice_faces(*([1] * 30)):
        result = spell.apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    reached = set(result.resolved_area_positions or ())
    assert len(reached) == expected_count
    assert all((x - 5) ** 2 + (y - 8) ** 2 <= 16 for x, y in reached)
    assert ((7, 10) in reached) == opening
    assert {position for position, tile in get_map().get_all_tiles().items()
            if "Ashen" in tile.active_conditions} == reached
    assert spell.aoe_shape is not None
    preview = spell.aoe_shape.compute_subjective(caster.position, caster.senses)
    assert preview.affected_positions == reached.intersection(caster.senses.visible)


def test_connected_spread_contacts_solid_cell_but_does_not_cross_it():
    reset_spell_regression_arena(9, 1)
    get_map().set_tile(4, 0, blocks_propagation=True)
    shape = Sphere(source_entity_uuid=uuid4(), target=(2, 0), radius_feet=20, propagation="connected")
    shape.compute_objective((2, 0))
    assert shape.affected_positions == {(x, 0) for x in range(5)}


@pytest.mark.parametrize("spell_kind", ["fireball", "ice_knife"])
def test_globe_suppresses_damage_and_area_with_provider_attribution(spell_kind):
    owner = create_spell_regression_actor("Globe", (10, 7), "heroes", spell_slots={6: 1})
    protected = create_spell_regression_actor("Protected", (12, 7), "heroes")
    outside = create_spell_regression_actor("Outside", (13, 7), "heroes")
    caster = create_spell_regression_actor("Caster", (2, 7), "monsters", spell_slots={2: 1, 6: 1})
    for actor in (protected, outside):
        force_save_result(actor, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=120)
    globe = GlobeOfInvulnerability(source_entity_uuid=owner.uuid).apply()
    assert globe is not None and not globe.canceled
    zone = next(row for row in get_map().get_spatial_conditions() if isinstance(row, GlobeZone))
    protected_hp, outside_hp = protected.get_hp(), outside.get_hp()
    start = EventQueue.event_cursor()
    spell = (Fireball(source_entity_uuid=caster.uuid, end_position=(13, 7), cast_at_level=6)
        if spell_kind == "fireball" else
        IceKnife(source_entity_uuid=caster.uuid, target_entity_uuid=outside.uuid, cast_at_level=2))
    with fixed_dice_faces(*([1] * 80)):
        result = spell.apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled, result.status_message
    assert protected.get_hp() == protected_hp
    assert outside.get_hp() < outside_hp
    events = [event for _, event in EventQueue.iter_events_since(start)
              if isinstance(event, SpellEvent) and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)]
    area = next(event for event in events if event.resolved_area_positions is not None
                and (spell_kind == "fireball" or event.effect_id == ICE_KNIFE_BURST))
    assert set(area.resolved_area_positions or ()).isdisjoint(zone.affected_positions)
    assert area.suppressions and area.suppressions[0].provider_uuid == zone.uuid
    assert protected.position in area.suppressions[0].positions
    assert any(event.canceled and event.target_entity_uuid == protected.uuid
               and event.suppressions[0].provider_uuid == zone.uuid for event in events)
    for position in zone.affected_positions:
        tile = get_map().get_tile(*position)
        assert tile is not None and "Ashen" not in tile.active_conditions


@pytest.mark.parametrize('layout,count', [('l-wall', 26), ('corridor', 23)])
def test_connected_reference_l_wall_and_corridor(layout, count):
    caster = create_spell_regression_actor('Caster', (10, 8), 'heroes', spell_slots={3: 1})
    edges = ([((11, y), CardinalDirection.EAST) for y in range(4, 10)] +
        [((x, 9), CardinalDirection.NORTH) for x in range(6, 12)] if layout == 'l-wall' else
        [((x, y), direction) for x, direction in ((9, CardinalDirection.WEST), (11, CardinalDirection.EAST))
         for y in range(3, 14)])
    for position, direction in edges:
        build_directional_wall().place_on_grid(position, boundary_direction=direction)
    result = Fireball(source_entity_uuid=caster.uuid, end_position=(10, 8)).apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.resolved_area_positions is not None
    assert len(result.resolved_area_positions) == count
    assert {p for p, tile in get_map().get_all_tiles().items() if 'Ashen' in tile.active_conditions} == set(result.resolved_area_positions)


@pytest.mark.parametrize('protected', [False, True])
def test_ice_knife_burst_and_every_application_publish_terminal_lineages(protected):
    caster = create_spell_regression_actor('Caster', (2, 7), 'monsters', spell_slots={1: 1})
    owner = create_spell_regression_actor('Globe', (10, 7), 'heroes', spell_slots={6: 1})
    create_spell_regression_actor('Inside', (12, 7), 'heroes')
    outside = create_spell_regression_actor('Outside', (13, 7), 'heroes')
    Entity.update_all_entities_senses(max_distance=120)
    if protected:
        GlobeOfInvulnerability(source_entity_uuid=owner.uuid).apply()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([4] * 80)):
        result = IceKnife(source_entity_uuid=caster.uuid, target_entity_uuid=outside.uuid).apply()
    assert result and not result.canceled
    latest = {}
    for _, event in EventQueue.iter_events_since(cursor):
        if isinstance(event, SpellEvent) and event.effect_id == ICE_KNIFE_BURST:
            latest[event.lineage_uuid] = event
    assert len(latest) == 3
    assert all(event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL) for event in latest.values())
    assert sum(event.canceled for event in latest.values()) == int(protected)


def test_surface_membership_preserves_sight_and_updates_hazards_immediately():
    observer = create_spell_regression_actor('Observer', (5, 7), 'heroes')
    create_spell_regression_actor('Target', (8, 7), 'monsters')
    Entity.update_all_entities_senses(max_distance=120)
    cell = get_map().get_tile(7, 7)
    assert cell is not None
    before = capture_senses_snapshot(observer.senses)
    deposit_residue(cell, ASHEN_RESIDUE)
    after_ash = capture_senses_snapshot(observer.senses)
    assert before.visible == after_ash.visible and before.entities == after_ash.entities
    deposit_residue(cell, POISON_RESIDUE)
    after_poison = capture_senses_snapshot(observer.senses)
    assert after_poison.hazardous_cells[cell.position]
    observer.update_entity_senses(max_distance=120)
    assert replace(after_poison, paths_dirty=False) == replace(capture_senses_snapshot(observer.senses), paths_dirty=False)
    assert cell.remove_condition(POISON_RESIDUE.name)
    after_removal = capture_senses_snapshot(observer.senses)
    assert not after_removal.hazardous_cells[cell.position]
    observer.update_entity_senses(max_distance=120)
    assert replace(after_removal, paths_dirty=False) == replace(capture_senses_snapshot(observer.senses), paths_dirty=False)
