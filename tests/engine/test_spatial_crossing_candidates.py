"""Public crossing outcomes survive footprint-scoped candidate selection."""

from uuid import uuid4

import pytest

from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.creature_types import Size
from dnd.core.events import Event, EventPhase, EventType
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallSegment
from dnd.entity import EntityConfig
from dnd.items.environment import DirectionalWall
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spells.wall_constructions import WallOfForce, WallOfStone
from dnd.spells.wall_fields import WindWallZone
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.world import CardinalDirection, MovementMode, WorldEdgeChannel
from tests.engine.support import create_test_entity
from tests.engine.test_remaining_walls import cast
from tests.manual.spell_regression_support import create_spell_regression_actor


@pytest.fixture(autouse=True)
def arena():
    reset_engine_runtime()
    get_map().create_rectangle(-10, -10, 21, 21)
    yield
    reset_engine_runtime()


def cause(source):
    return Event(source_entity_uuid=source, event_type=EventType.BASE_ACTION,
        phase=EventPhase.EFFECT)


def wind(start, end):
    mover = create_test_entity(name="Small flyer",
        config=EntityConfig(position=(-9, -9), size=Size.SMALL))
    geometry = WallAssemblyPresentationGeometry(path=WallSegment(start=start, end=end),
        base_height_steps=0, width_feet=1, height_feet=15)
    zone = WindWallZone(source_entity_uuid=mover.uuid, position=(-1, 0),
        geometry=geometry, spell_dc=10)
    result = zone.activate(parent_event=cause(mover.uuid))
    assert result is not None and not result.canceled
    return zone, mover


@pytest.mark.parametrize("spell,optical_allowed", [(WallOfStone, False), (WallOfForce, True)])
def test_native_solid_wall_blocks_long_segments_in_both_directions(spell, optical_allowed):
    caster = create_spell_regression_actor("Caster", (-6, -6), "heroes", spell_slots={5: 1})
    cast(spell, caster, start=(-2, 0), end=(2, 0))
    grid = get_map()
    for start, end in (((-1, -9), (-1, 9)), ((-1, 9), (-1, -9))):
        for channel, allowed in (("movement", False), ("propagation", False),
                                 ("optical", optical_allowed)):
            assert grid.spatial_crossing_allows(start, end, channel, caster.uuid) is allowed
            assert grid.spatial_crossing_allows((7, start[1]), (7, end[1]), channel, caster.uuid)
    # Select transition-aware FOV, as a mixed construction/boundary scene does.
    distant = DirectionalWall(source_entity_uuid=caster.uuid, item_id="test.crossing.distant_wall",
        blocked_channels=(WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION))
    distant.place_on_grid((-10, -10), boundary_direction=CardinalDirection.NORTH)
    for origin in ((-3, -3), (0, -2), (3, 3)):
        for channel, query in (("optical", grid.compute_fov),
                               ("propagation", grid.compute_propagation_fov)):
            expected = {position for position in grid.get_all_tiles()
                if sum((a-b)**2 for a, b in zip(position, origin)) <= 36
                and grid.raycast_clear(origin, position, channel)}
            assert set(query(origin, 6)) == expected, (spell, channel, origin)
    zone, = grid.get_spatial_conditions()
    section = next(identity for identity, geometry in zone.sections.items()
        if geometry.path.start == (-2., 0.))
    for channel in ("movement", "optical", "propagation"):
        assert grid.spatial_crossing_allows((-1, -9), (-1, 9), channel, caster.uuid,
            terminal_provider_uuid=section)


@pytest.mark.parametrize("start,end,allowed", [
    ((-8, -8), (8, 8), False),
    ((8, 8), (-8, -8), False),
    ((-8, -7), (7, 8), True),
])
def test_wind_wall_exact_corner_contact_and_near_miss(start, end, allowed):
    # The first two paths touch the finite wall endpoint at the cell corner
    # (-0.5, -0.5); the third parallel path passes beyond that endpoint.
    _, mover = wind((-.5, -.5), (3., -.5))
    grid = get_map()
    assert grid.spatial_crossing_allows(start, end, "movement", mover.uuid,
        MovementMode.FLYING) is allowed
    assert grid.spatial_crossing_allows(start, end, "optical", mover.uuid)
    assert grid.spatial_crossing_allows(start, end, "propagation", mover.uuid)


def test_wind_suppression_and_footprint_replacement_preserve_current_crossings():
    zone, mover = wind((-3., 0.), (3., 0.))
    grid = get_map()

    def allowed(x):
        return grid.spatial_crossing_allows((x, -8), (x, 8), "movement",
            mover.uuid, MovementMode.FLYING)

    assert not allowed(-2) and not allowed(2)
    provider = uuid4()
    assert zone.set_suppression(provider, True)
    assert allowed(-2) and allowed(2)
    assert zone.set_suppression(provider, False)
    assert not allowed(-2) and not allowed(2)

    footprint = set(zone.affected_positions)
    assert zone.change_footprint({position for position in footprint if position[0] < 0},
        parent_event=cause(mover.uuid))
    assert not allowed(-2) and allowed(2)
    assert zone.change_footprint(footprint, parent_event=cause(mover.uuid))
    assert not allowed(-2) and not allowed(2)
    zone.deactivate()
    assert allowed(-2) and allowed(2)


class RemoteCrossingRule(SpatialCondition):
    """An undeclared custom rule whose support does not delimit its authority."""

    def blocks_crossing_between(self, start, end, channel, requester_uuid, mode,
                               terminal_provider_uuid=None):
        return (self.allows_contribution_at(None) and channel == "propagation"
            and min(start[0], end[0]) < .5 < max(start[0], end[0]))


def test_undeclared_custom_rule_still_blocks_outside_registered_footprint():
    source = uuid4()
    zone = RemoteCrossingRule(source_entity_uuid=source, position=(8, 8),
        content_ref=ContentRef(pack_id="test.crossing", definition_kind=ContentDefinitionKind.CONDITION,
            content_id="condition.remote_crossing", content_version=1, definition_contract_hash="0" * 64),
        layer=SpatialEffectLayer.FIELD, occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING)
    result = zone.activate(parent_event=cause(source))
    assert result is not None and not result.canceled
    assert zone.affected_positions == {(8, 8)}
    grid = get_map()
    assert not grid.spatial_crossing_allows((-8, 0), (8, 0), "propagation")
    assert not grid.spatial_crossing_allows((8, 0), (-8, 0), "propagation")
    assert grid.spatial_crossing_allows((-8, 0), (-1, 0), "propagation")
    assert grid.spatial_crossing_allows((-8, 0), (8, 0), "optical")

    # Keep the native directional branch active outside the queried radius.
    wall = DirectionalWall(source_entity_uuid=source, item_id="test.crossing.remote_wall",
        blocked_channels=(WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION))
    wall.place_on_grid((-10, -10), boundary_direction=CardinalDirection.NORTH)
    origin, radius = (-2, 0), 5

    def check_native_rays():
        for channel, query in (("optical", grid.compute_fov),
                               ("propagation", grid.compute_propagation_fov)):
            expected = {position for position in grid.get_all_tiles()
                if (position[0] - origin[0]) ** 2 + (position[1] - origin[1]) ** 2 <= radius ** 2
                and grid.raycast_clear(origin, position, channel)}
            assert set(query(origin, radius)) == expected

    check_native_rays()
    assert (2, 0) not in grid.compute_propagation_fov(origin, radius)
    assert (2, 0) in grid.compute_fov(origin, radius)
    zone.deactivate()
    assert grid.spatial_crossing_allows((-8, 0), (8, 0), "propagation")
    check_native_rays()
    assert (2, 0) in grid.compute_propagation_fov(origin, radius)
