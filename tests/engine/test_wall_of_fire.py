"""Wall commands retain physical placement and resolve the SRD damage lifecycle."""

import pytest

from dnd.action_dispatch import dispatch_available_action
from dnd.actions import SpellEvent
from dnd.actions_functional import execute_by_index, execute_available_action, get_extra_position_options, register_spell
from dnd.content.items.environment_item_builders import build_spell_device
from dnd.content.items.world_prop_builders import build_world_prop
from dnd.spells.abjuration import GlobeOfInvulnerability
from dnd.core.base_tiles import Tile
from dnd.content.items.window_builders import place_window
from dnd.core.base_tiles import water_factory
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue, SensoryUpdateEvent
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import WallPresentationGeometry
from dnd.entity import Entity
from dnd.spells.walls import WallOfFire, WallOfFireZone
from dnd.types.physical_access import PhysicalAccess
from dnd.types.world import CardinalDirection, OccupancyLayer
from tests.manual.spell_regression_support import create_spell_regression_actor, force_save_result, reset_spell_regression_arena


def scene(*, level=4):
    reset_spell_regression_arena(20, 20)
    caster = create_spell_regression_actor("Caster", (1, 1), "heroes", spell_slots={level: 2})
    return caster


def actor(name, position):
    return create_spell_regression_actor(name, position, "monsters")


def cast(caster, *, origin=(5, 5), end=(9, 5), **fields):
    if fields.get("wall_form") == "ring":
        end = None
    with fixed_dice_faces(*([4] * 200)):
        result = WallOfFire(source_entity_uuid=caster.uuid, end_position=origin, extra_target_positions=[end] if end is not None else [], **fields).apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    zones = [zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WallOfFireZone)]
    assert len(zones) == 1
    return result, zones[0]


@pytest.mark.parametrize("success,damage", [(False, 20), (True, 10)])
def test_wall_appearance_saves_only_for_flame_contact(success, damage):
    caster = scene()
    flame = actor("In flames", (7, 5))
    hot = actor("Hot side", (7, 6))
    cold = actor("Cold side", (7, 4))
    force_save_result(flame, "dexterity", succeeds=success)
    before = [target.get_hp() for target in (flame, hot, cold)]
    result, zone = cast(caster)
    assert [initial - target.get_hp() for initial, target in zip(before, (flame, hot, cold))] == [damage, 0, 0]
    assert result.area_geometry.width_feet == 1 and result.area_geometry.height_feet == 20
    assert get_map().is_blocking_optics(7, 5)
    assert not get_map().is_blocking_optics(7, 6)
    assert get_map().can_reach_between((7, 4), (7, 6), PhysicalAccess.PROJECTILE, caster.uuid)
    assert get_map().can_transition((6, 4), (6, 5), caster.uuid)


@pytest.mark.parametrize("position,exposure,appearance", [((7, 5), "contact", True), ((7, 6), "radiated_heat", False)])
def test_wall_damage_records_exact_source_and_physical_contact(position, exposure, appearance):
    caster = scene()
    target = actor("Exposed", position)
    cursor = EventQueue.event_cursor()
    _, zone = cast(caster)
    if not appearance:
        with fixed_dice_faces(*([4] * 100)):
            target.on_turn_end()
    applied = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION]
    assert len(applied) == 1 and applied[0].applied_damage > 0
    source = applied[0].spatial_source
    assert source is not None and source.spatial_effect_uuid == zone.uuid
    assert source.position == (7, 5) and source.target_position == position
    assert source.exposure == exposure and source.base_height_steps == zone.geometry.base_height_steps
    assert DamageAppliedEvent.model_validate_json(applied[0].model_dump_json(), context=PASSIVE_EVENT_REPLAY).spatial_source == source


def test_overlapping_walls_keep_their_separate_damage_sources():
    caster = scene()
    other = create_spell_regression_actor("Other caster", (1, 8), "allies", spell_slots={4: 1})
    target = actor("Between walls", (7, 6))
    _, first = cast(caster)
    with fixed_dice_faces(*([4] * 200)):
        result = WallOfFire(source_entity_uuid=other.uuid, end_position=(5, 7),
            extra_target_positions=[(9, 7)], hot_side="right").apply()
    assert result is not None and not result.canceled
    walls = [zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WallOfFireZone)]
    assert len(walls) == 2
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([4] * 100)):
        target.on_turn_end()
    sources = [event.spatial_source for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION]
    assert len(sources) == 2 and all(source is not None for source in sources)
    assert {source.spatial_effect_uuid for source in sources} == {wall.uuid for wall in walls}
    assert {source.position for source in sources} == {(7, 5), (7, 7)}


def test_fire_immunity_produces_no_applied_wall_damage_accent():
    caster = scene()
    target = actor("Immune", (7, 6))
    target.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
        source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        value=ResistanceStatus.IMMUNITY, damage_type=DamageType.FIRE, name="Fire immunity"))
    cast(caster)
    before = target.get_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([4] * 100)):
        target.on_turn_end()
    assert target.get_hp() == before
    assert not any(isinstance(event, DamageAppliedEvent) for _, event in EventQueue.iter_events_since(cursor))


def test_heat_entry_is_safe_and_does_not_consume_first_flame_entry_allowance():
    caster = scene()
    target = actor("Entering", (7, 8))
    cast(caster)
    before = target.get_hp()
    turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(*([4] * 200)):
            Entity.update_entity_position(target, (7, 6))
            assert target.get_hp() == before
            Entity.update_entity_position(target, (7, 5))
            assert before - target.get_hp() == 20
            Entity.update_entity_position(target, (7, 4))
            Entity.update_entity_position(target, (7, 5))
            assert before - target.get_hp() == 20
            target.on_turn_end()
            assert before - target.get_hp() == 40
    finally:
        EventQueue.end_turn_execution(turn)
    turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(*([4] * 200)):
            Entity.update_entity_position(target, (7, 4))
            Entity.update_entity_position(target, (7, 5))
        assert before - target.get_hp() == 60
    finally:
        EventQueue.end_turn_execution(turn)


@pytest.mark.parametrize("side,position,damage", [("left", (7, 6), 20), ("left", (7, 4), 0),
    ("right", (7, 4), 20), ("right", (7, 6), 0), ("left", (7, 8), 0)])
def test_only_chosen_ten_foot_heat_band_damages_at_turn_end(side, position, damage):
    caster = scene()
    target = actor("Neighbor", position)
    before = target.get_hp()
    cast(caster, hot_side=side)
    with fixed_dice_faces(*([4] * 100)):
        target.on_turn_end()
    assert before - target.get_hp() == damage


@pytest.mark.parametrize("side,expected", [("inside", [20, 0]), ("outside", [0, 20])])
def test_ring_inward_and_outward_heat_leave_the_opposite_side_safe(side, expected):
    caster = scene()
    center = actor("Center", (10, 10))
    outside = actor("Outside", (10, 13))
    before = [target.get_hp() for target in (center, outside)]
    _, zone = cast(caster, origin=(10, 10), wall_form="ring", hot_side=side)
    assert (10, 10) not in zone.flame_positions
    with fixed_dice_faces(*([4] * 100)):
        center.on_turn_end()
        outside.on_turn_end()
    assert [initial - target.get_hp() for initial, target in zip(before, (center, outside))] == expected


@pytest.mark.parametrize("origin,end,side,expected", [
    ((5, 5), (9, 5), "left", [20, 0]),
    ((9, 5), (5, 5), "left", [0, 20]),
    ((5, 5), (9, 5), "right", [0, 20]),
    ((9, 5), (5, 5), "right", [20, 0]),
])
def test_reversing_ordered_endpoints_reverses_the_hot_side(origin, end, side, expected):
    caster = scene()
    neighbors = (actor("Positive Y", (7, 6)), actor("Negative Y", (7, 4)))
    before = [target.get_hp() for target in neighbors]
    cast(caster, origin=origin, end=end, hot_side=side)
    with fixed_dice_faces(*([4] * 100)):
        for target in neighbors:
            target.on_turn_end()
    assert [initial - target.get_hp() for initial, target in zip(before, neighbors)] == expected


def test_upcast_damage_and_parented_events_preserve_retained_geometry():
    caster = scene(level=5)
    target = actor("Contact", (7, 5))
    force_save_result(target, "dexterity", succeeds=False)
    before = target.get_hp()
    result, zone = cast(caster, cast_at_level=5)
    assert before - target.get_hp() == 24
    events = [event for _, event in EventQueue.iter_events_since(0)]
    damages = [event for event in events if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION]
    assert len(damages) == 1 and damages[0].parent_event is not None
    restored = SpellEvent.model_validate_json(result.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    assert restored.area_geometry == result.area_geometry
    observed = [event.spatial_effects_changed[zone.uuid]
        for event in events if isinstance(event, SensoryUpdateEvent) and zone.uuid in event.spatial_effects_changed]
    assert observed and observed[-1].area_geometry == result.area_geometry
    assert set(observed[-1].positions).issubset(zone.flame_positions)


@pytest.mark.parametrize("expiry", [False, True])
def test_concentration_removal_and_round_expiry_remove_mechanics_and_handlers(expiry):
    caster = scene()
    _, zone = cast(caster)
    target = actor("Later crossing", (7, 4))
    if expiry:
        for _ in range(10):
            zone.progress_spatial_duration()
    else:
        caster.remove_condition("Concentrating")
    assert zone not in get_map().get_spatial_conditions()
    assert not get_map().is_blocking_optics(7, 5)
    assert zone.spatial_handler_uuids == [] and zone.event_handlers_uuids == []
    before = target.get_hp()
    Entity.update_entity_position(target, (7, 5))
    target.on_turn_end()
    assert target.get_hp() == before


@pytest.mark.parametrize("invalid", ["water", "missing_surface", "range", "side", "coincident", "missing_end", "long"])
def test_invalid_wall_placement_does_not_spend_resources(invalid):
    caster = scene()
    fields = {"end_position": (5, 5), "extra_target_positions": [(9, 5)]}
    if invalid == "water":
        get_map().set_tile(7, 5, tile=water_factory((7, 5)), fire_event=False)
    elif invalid == "missing_surface":
        fields["extra_target_positions"] = [(20, 5)]
    elif invalid == "range":
        fields["end_position"] = (17, 17)
        fields["extra_target_positions"] = [(19, 19)]
    elif invalid == "side":
        fields["hot_side"] = "inside"
    elif invalid == "coincident":
        fields["extra_target_positions"] = [(5, 5)]
    elif invalid == "missing_end":
        fields["end_position"] = None
        fields["extra_target_positions"] = []
    else:
        fields["extra_target_positions"] = [(18, 5)]
    before = caster.action_economy.actions.normalized_score
    result = WallOfFire(source_entity_uuid=caster.uuid, **fields).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == before
    assert caster.has_spell_slot(4)
    assert get_map().get_spatial_conditions() == []


def test_wall_endpoints_discover_and_execute_through_normal_spell_route():
    caster = scene()
    register_spell(caster, WallOfFire)
    available = caster.get_available_actions()
    rows = [row for row in available.position_actions if row.display_name.startswith("Wall of Fire")]
    assert len(rows) == 3
    assert {tuple((facet.key,facet.value) for facet in row.variant_facets) for row in rows} == {
        (("form","segment"),), (("form","ring"),("side","inside")), (("form","ring"),("side","outside"))}
    chosen = next(row for row in rows if tuple((facet.key,facet.value) for facet in row.variant_facets)==(("form","segment"),))
    assert chosen.position_selection.kind == "path"
    target_index = next(index for index, target in enumerate(chosen.valid_targets) if target.position == (5, 5))
    assert (9, 5) in get_extra_position_options(caster, chosen, chosen.valid_targets[target_index])
    with fixed_dice_faces(*([4] * 200)):
        result = execute_by_index(caster, chosen.template_name, target_index, available=available, extra_target_positions=[(9, 5)])
    assert isinstance(result, SpellEvent) and not result.canceled
    assert isinstance(result.area_geometry, WallPresentationGeometry)
    assert result.area_geometry.path.start == (5, 5) and result.area_geometry.path.end == (9, 5)


@pytest.mark.parametrize("start,end,hot,cold", [
    ((5, 5), (9, 5), (7, 6), (7, 4)),
    ((9, 5), (5, 5), (7, 4), (7, 6)),
    ((5, 5), (7, 7), (5, 7), (7, 5)),
])
def test_ordered_endpoints_define_geometry_and_the_heated_side(start, end, hot, cold):
    caster = scene()
    heated, safe = actor("Hot", hot), actor("Cold", cold)
    before = heated.get_hp(), safe.get_hp()
    result, _ = cast(caster, origin=start, end=end)
    assert result.area_geometry.path.start == start and result.area_geometry.path.end == end
    with fixed_dice_faces(*([4] * 200)):
        heated.on_turn_end()
        safe.on_turn_end()
    assert before[0] - heated.get_hp() == 20 and safe.get_hp() == before[1]


def test_second_endpoint_at_exact_maximum_length_and_cast_range_is_allowed():
    caster = scene()
    Entity.update_entity_position(caster, (0, 5))
    # An endpoint exactly 120 feet away, with a 60-foot wall.
    reset_grid = get_map()
    for x in range(20, 25):
        for y in range(20):
            reset_grid.set_tile(x, y, tile=Tile.create((x, y)), fire_event=False)
    Entity.update_all_entities_senses(max_distance=200)
    result, _ = cast(caster, origin=(12, 5), end=(24, 5))
    assert result.area_geometry.path.end == (24, 5)


@pytest.mark.parametrize("change", ["hidden", "solid", "boundary"])
def test_endpoint_selection_rechecks_changed_world_before_spending(change):
    caster = scene()
    template = WallOfFire(source_entity_uuid=caster.uuid, template=True)
    assert (9, 5) in template.get_valid_extra_target_positions((5, 5))
    if change == "hidden":
        caster.senses.visible[(9, 5)] = False
    elif change == "solid":
        get_map().set_tile(7, 5, tile=Tile.create((7, 5), blocks_propagation=True), fire_event=False)
    else:
        # Opaque shutter faces across the segment; the endpoints stay legal terrain.
        place_window("environment.window.fantasy_g9", (7, 5), CardinalDirection.EAST)
    assert (9, 5) not in template.get_valid_extra_target_positions((5, 5))
    before = caster.action_economy.actions.normalized_score
    result = template.instantiate(end_position=(5, 5), extra_target_positions=[(9, 5)]).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == before and caster.has_spell_slot(4)


def test_one_position_starts_in_first_cell_toward_target_and_excludes_caster():
    caster = scene()
    before = caster.get_hp()
    result, zone = cast(caster, origin=(5, 1), end=None)
    assert result.area_geometry.path.start == (2, 1)
    assert result.area_geometry.path.end == (5, 1)
    assert zone.position == (2, 1) and caster.position not in zone.flame_positions
    assert caster.get_hp() == before


def test_explicit_endpoints_can_place_flames_under_caster():
    caster = scene()
    force_save_result(caster, "dexterity", succeeds=False)
    before = caster.get_hp()
    result, zone = cast(caster, origin=caster.position, end=(5, 1))
    assert result.area_geometry.path.start == caster.position
    assert zone.position == caster.position and before - caster.get_hp() == 20


@pytest.mark.parametrize("target", [(1, 1), (2, 1)])
def test_one_point_cannot_create_a_zero_length_wall_at_or_next_to_caster(target):
    caster = scene()
    result = WallOfFire(source_entity_uuid=caster.uuid, end_position=target).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1 and caster.has_spell_slot(4)


def test_extra_position_query_offers_caster_cell_for_an_explicit_reversed_wall():
    caster = scene()
    template = WallOfFire(source_entity_uuid=caster.uuid, template=True)
    assert caster.position in template.get_valid_extra_target_positions((5, 1))
    result, _ = cast(caster, origin=(5, 1), end=caster.position)
    assert result.area_geometry.path.start == (5, 1) and result.area_geometry.path.end == caster.position


def test_discovered_first_point_does_not_substitute_a_witness_for_missing_extra_point():
    caster = scene()
    template = WallOfFire(source_entity_uuid=caster.uuid, template=True)
    anchor = (15, 5)
    partial = template.instantiate(end_position=anchor)
    assert partial.validate_requirements_for_discovery(allow_partial_position=True)
    assert not partial.validate_requirements_for_discovery()
    result = partial.apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1 and caster.has_spell_slot(4)


@pytest.mark.parametrize("form,side", [("segment", "left"), ("ring", "inside")])
def test_fire_wall_rejects_excess_position_allocation_before_cost(form, side):
    caster = scene()
    result = WallOfFire(source_entity_uuid=caster.uuid, end_position=(5, 5),
        extra_target_positions=[(9, 5), (9, 9)], wall_form=form, hot_side=side).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1 and caster.has_spell_slot(4)


def test_device_wall_extra_position_dispatch_and_origin_shorthand_share_the_route():
    caster = scene()
    grant = WallOfFire(source_entity_uuid=caster.uuid, template=True, cast_origin="source_item")
    device = build_spell_device(item_id="environment.fireball_cannon", name="Wall device",
        spell_templates=[grant], charges=2)
    device.place_on_grid((2, 1))
    Entity.update_all_entities_senses()
    info = next(row for row in caster.get_available_actions().position_actions if row.source_item_uuid == device.uuid)
    selected = next(target for target in info.valid_targets if target.position == (5, 5))
    assert (9, 5) in get_extra_position_options(caster, info, selected)
    result = dispatch_available_action(caster, action_info=info, target=selected,
        extra_target_positions=((9, 5),)).event
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.area_geometry.path.start == (5, 5) and result.area_geometry.path.end == (9, 5)
    zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WallOfFireZone))
    assert zone.deactivate()
    caster.action_economy.reset_all_costs()
    selected = next(target for target in info.valid_targets if target.position == (6, 1))
    result = execute_available_action(caster, info, selected)
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.area_geometry.path.start == (3, 1) and result.area_geometry.path.end == selected.position
    assert device.charges == 0


def test_movement_within_flames_is_not_a_new_entry_but_turn_end_still_damages():
    caster = scene()
    target = actor("Already in flames", (6, 5))
    force_save_result(target, "dexterity", succeeds=True)
    cast(caster)
    before = target.get_hp()
    turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(*([4] * 200)):
            Entity.update_entity_position(target, (7, 5))
            assert target.get_hp() == before
            target.on_turn_end()
            assert before - target.get_hp() == 20
    finally:
        EventQueue.end_turn_execution(turn)


def test_underground_creature_is_safe_until_it_emerges_into_flames():
    caster = scene()
    target = actor("Burrower", (7, 5))
    Entity.update_entity_position(target, target.position, occupancy_layer=OccupancyLayer.UNDERGROUND)
    before = target.get_hp()
    cast(caster)
    target.on_turn_end()
    assert target.get_hp() == before
    with fixed_dice_faces(*([4] * 200)):
        Entity.update_entity_position(target, target.position, occupancy_layer=OccupancyLayer.GROUND)
    assert before - target.get_hp() == 20


def test_wall_retains_raised_support_and_excludes_heat_on_other_elevation():
    caster = scene()
    grid = get_map()
    for x in range(5, 10):
        grid.set_tile(x, 5, height=2, fire_event=False)
    grid.set_tile(7, 6, height=2, fire_event=False)
    grid.set_tile(8, 6, height=3, fire_event=False)
    heated, higher = actor("Same elevation", (7, 6)), actor("Other elevation", (8, 6))
    before = heated.get_hp(), higher.get_hp()
    Entity.update_all_entities_senses()
    result, zone = cast(caster)
    assert result.area_geometry.base_height_steps == 2 and result.area_geometry.height_feet == 20
    assert (7, 6) in zone.heat_positions and (8, 6) not in zone.affected_positions
    restored = SpellEvent.model_validate_json(result.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    assert restored.area_geometry.base_height_steps == 2
    with fixed_dice_faces(*([4] * 200)):
        heated.on_turn_end()
        higher.on_turn_end()
    assert before[0] - heated.get_hp() == 20 and higher.get_hp() == before[1]


def test_wall_rejects_a_segment_crossing_different_support_elevations():
    caster = scene()
    get_map().set_tile(7, 5, height=1, fire_event=False)
    result = WallOfFire(source_entity_uuid=caster.uuid, end_position=(5, 5), extra_target_positions=[(9, 5)]).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1 and caster.has_spell_slot(4)


def test_solid_center_object_cannot_be_covered_by_a_flame_cell():
    caster = scene()
    stove = build_world_prop("environment.furniture.clay_stove")
    stove.place_on_grid((5, 5))
    Entity.update_all_entities_senses()
    result = WallOfFire(source_entity_uuid=caster.uuid, end_position=(5, 5), extra_target_positions=[(9, 5)]).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1 and caster.has_spell_slot(4)


def test_globe_suppresses_fire_flame_and_heat_with_retained_cause():
    caster = scene()
    owner = actor("Globe owner", (7, 5))
    globe = GlobeOfInvulnerability(source_entity_uuid=owner.uuid, costs=[], alt_skip_slot=True).apply()
    assert globe is not None and not globe.canceled
    _, zone = cast(caster, origin=(3, 5), end=(11, 5))
    assert (7, 5) not in zone.flame_positions and (7, 6) not in zone.heat_positions
    assert zone.spatial_suppressions and (7, 5) in zone.spatial_suppressions[0].positions


def test_distant_flames_cannot_bypass_shelter_from_local_heat():
    caster = scene()
    target = actor("Sheltered", (5, 7))
    get_map().set_tile(5, 6, blocks_propagation=True, fire_event=False)
    before = target.get_hp()
    _, zone = cast(caster)
    assert (5, 7) not in zone.heat_positions
    target.on_turn_end()
    assert target.get_hp() == before


def test_ring_authoring_keeps_the_accepted_fixed_ten_foot_radius():
    caster = scene()
    with pytest.raises(ValueError):
        WallOfFire(source_entity_uuid=caster.uuid, end_position=(10, 10),
                   wall_form="ring", hot_side="inside", wall_radius_feet=5)
