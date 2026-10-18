"""Area line of effect has one semantics: the native propagation ray.

Boundary: ``GridMap.compute_propagation_fov`` in random rooms. Brute force
traces the native ray (``raycast_clear`` on the propagation channel) to every
cell. Total cover comes from blocking cells, missing cells, directional
boundaries and spatial-condition crossings; nothing else in the room, such as
an unrelated condition far away, may change who an area reaches.
"""

import random
from uuid import uuid4

import pytest

from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import Event, EventPhase, EventType
from dnd.core.gridmap import get_map
from dnd.items.environment import DirectionalWall
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import SpatialCondition
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.world import CardinalDirection, SpatialChannel, WorldEdgeChannel

SIZE = 9
RADII = (None, 2.5, 4)
FURNISHINGS = ("bare", "boundaries", "conditions", "boundaries+conditions")


def content_ref(name: str) -> ContentRef:
    return ContentRef(pack_id="test.line_of_effect", definition_kind=ContentDefinitionKind.CONDITION,
        content_id=f"condition.{name}", content_version=1, definition_contract_hash="0" * 64)


class PaneCrossing(SpatialCondition):
    """A footprint whose border stops propagation, like a sealed force pane."""

    crossing_channels = frozenset({WorldEdgeChannel.PROPAGATION})

    def spatial_channels(self):
        return super().spatial_channels() | {SpatialChannel.PROPAGATION}

    def blocks_crossing_between(self, start, end, channel, requester_uuid, mode, terminal_provider_uuid=None):
        return (channel is WorldEdgeChannel.PROPAGATION
            and (start in self.affected_positions) != (end in self.affected_positions))


def activate(condition: SpatialCondition) -> None:
    result = condition.activate(parent_event=Event(source_entity_uuid=condition.source_entity_uuid,
        event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT))
    assert result is not None and not result.canceled


def unrelated_zone(position) -> SpatialCondition:
    return SpatialCondition(source_entity_uuid=uuid4(), content_ref=content_ref("unrelated"),
        position=position, affected_positions={position}, layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING)


def random_room(seed: int, furnishing: str) -> random.Random:
    rng = random.Random(seed)
    reset_engine_runtime()
    grid = get_map()
    grid.create_rectangle(0, 0, SIZE, SIZE)
    cells = sorted(grid.get_all_tiles())
    for x, y in rng.sample(cells, 9):
        grid.set_tile(x, y, blocks_propagation=True, blocks_optics=rng.random() < .5)
    for x, y in rng.sample(cells, 3):
        grid.remove_tile(x, y)
    if "boundaries" in furnishing:
        for position in rng.sample(sorted(grid.get_all_tiles()), 4):
            DirectionalWall(source_entity_uuid=uuid4(), item_id="test.line_of_effect.pane",
                blocked_channels=(WorldEdgeChannel.PROPAGATION,)).place_on_grid(
                position, boundary_direction=rng.choice(list(CardinalDirection)))
    if "conditions" in furnishing:
        x, y = rng.randrange(1, SIZE - 2), rng.randrange(1, SIZE - 2)
        pane = {cell for cell in ((x, y), (x + 1, y), (x, y + 1)) if grid.has_tile(*cell)}
        if pane:
            activate(PaneCrossing(source_entity_uuid=uuid4(), content_ref=content_ref("pane"),
                position=min(pane), affected_positions=pane, layer=SpatialEffectLayer.FIELD,
                occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING))
    return rng


def reach(origin, radius) -> set[tuple[int, int]]:
    return set(get_map().compute_propagation_fov(origin, radius))


def native_rays(origin, radius) -> set[tuple[int, int]]:
    grid = get_map()
    return {position for position in grid.get_all_tiles()
        if (radius is None or (position[0] - origin[0]) ** 2 + (position[1] - origin[1]) ** 2 <= radius ** 2)
        and grid.raycast_clear(origin, position, WorldEdgeChannel.PROPAGATION)}


@pytest.fixture(autouse=True)
def clean_runtime():
    yield
    reset_engine_runtime()


@pytest.mark.parametrize("furnishing", FURNISHINGS)
@pytest.mark.parametrize("seed", range(30))
def test_propagation_reach_is_the_native_ray_in_random_rooms(seed, furnishing):
    rng = random_room(seed, furnishing)
    for origin in rng.sample(sorted(get_map().get_all_tiles()), 6):
        for radius in RADII:
            assert reach(origin, radius) == native_rays(origin, radius), (origin, radius)


@pytest.mark.parametrize("seed", range(30))
def test_an_unrelated_condition_elsewhere_changes_no_reach(seed):
    rng = random_room(seed, "bare")
    origins = rng.sample(sorted(get_map().get_all_tiles()), 6)
    before = {(origin, radius): reach(origin, radius) for origin in origins for radius in RADII}
    activate(unrelated_zone((SIZE - 1, SIZE - 1) if get_map().has_tile(SIZE - 1, SIZE - 1) else (0, 0)))
    after = {(origin, radius): reach(origin, radius) for origin in origins for radius in RADII}
    assert after == before


def long_corridor(seed: int) -> random.Random:
    """A 200 x 5 corridor, far wider than the 80-cell kept route table, with boundaries beyond it."""
    rng = random.Random(seed)
    reset_engine_runtime()
    grid = get_map()
    grid.create_rectangle(0, 0, 200, 5)
    cells = sorted(grid.get_all_tiles())
    for x, y in rng.sample(cells, 12):
        grid.set_tile(x, y, blocks_propagation=True, blocks_optics=True)
    for position in rng.sample(sorted(grid.get_all_tiles()), 6):
        DirectionalWall(source_entity_uuid=uuid4(), item_id="test.line_of_effect.pane",
            blocked_channels=(WorldEdgeChannel.PROPAGATION,)).place_on_grid(
            position, boundary_direction=rng.choice(list(CardinalDirection)))
    return rng


@pytest.mark.parametrize("seed", range(3))
def test_propagation_reach_beyond_eighty_cells_is_the_native_ray(seed):
    rng = long_corridor(seed)
    origins = [(0, 2), (199, 2)] + rng.sample(sorted(get_map().get_all_tiles()), 2)
    for origin in origins:
        for radius in (None, 150):
            reached = reach(origin, radius)
            assert reached == native_rays(origin, radius), (origin, radius)
    assert any(abs(x - origin[0]) > 80 for origin in origins for x, _ in reach(origin, None))
