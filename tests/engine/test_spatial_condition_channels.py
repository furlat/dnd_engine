"""Spatial conditions invalidate only the observer channels their data changes.

Installing or removing a zone leaves the optical revision of every observer
untouched unless the zone obscures or blocks sight; observers still perceive the
zone's hazards, path costs and obscurement through the public senses.
"""

from dataclasses import dataclass
from typing import Callable
from uuid import UUID, uuid4

from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.events import Event, EventPhase, EventType
from dnd.core.gridmap import get_map
from dnd.core.navigation import route_cost
from dnd.entity import Entity
from dnd.items.environment import DirectionalWall
from dnd.spatial.area_conditions import AreaCondition
from dnd.spells.conjuration import FogCloudZone, GreaseZone
from dnd.spells.transmutation import SpikeGrowthZone
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state
from dnd.types.cells import CellMask, cell_in, value_at

ZONE_CELLS = frozenset({(4, 0), (4, 1), (4, 2)})
BEYOND = (6, 1)


@dataclass(frozen=True)
class Observation:
    visible: CellMask
    hazards: dict[tuple[int, int], int | None]
    path_cost_beyond: int | None
    perceived_effects: frozenset[UUID]


@dataclass(frozen=True)
class ZoneCase:
    name: str
    build: Callable[[UUID], AreaCondition]
    moves_optical: bool
    # Hazard entry of the zone cells once installed; None when they are no longer visible.
    zone_hazard: bool | None
    difficult: bool
    hides_beyond: bool


def _cause(source: UUID) -> Event:
    return Event(event_type=EventType.BASE_ACTION, source_entity_uuid=source,
                 phase=EventPhase.EFFECT)



def _obscured(grid) -> bool:
    """Whether the zone cells carry optical obscurement (the channel an obscuring zone writes)."""
    return any(grid.optical_obscurement_bits_at(cell) for cell in ZONE_CELLS)


def _observe(observer: Entity) -> Observation:
    observer.materialize_navigation(max_distance=8)
    snapshot = capture_senses_snapshot(observer.senses)
    return Observation(
        visible=snapshot.visible,
        hazards={cell: value_at(snapshot.hazardous_cells, cell) for cell in ZONE_CELLS},
        path_cost_beyond=route_cost(observer.senses.paths, BEYOND),
        perceived_effects=frozenset(snapshot.spatial_effects),
    )


def check_zone(case: ZoneCase) -> None:
    reset_senses_state(width=9, height=3)
    grid = get_map()
    # Propagation is solved directionally once the room has any propagation
    # boundary or zone; this one keeps the solver fixed across the case.
    DirectionalWall(source_entity_uuid=uuid4(), item_id="test.channels.propagation_boundary",
        blocked_channels=(WorldEdgeChannel.PROPAGATION,)).place_on_grid(
            (1, 0), boundary_direction=CardinalDirection.NORTH)
    observers = [create_skeleton(name="Near observer", position=(0, 1), darkvision=False),
                 create_skeleton(name="Far observer", position=(8, 1), darkvision=False)]
    for observer in observers:
        observer.update_entity_senses(max_distance=8)
    near = observers[0]
    before = _observe(near)
    assert before.hazards == dict.fromkeys(ZONE_CELLS, False), case.name
    assert cell_in(before.visible, BEYOND), case.name
    optical_before = grid.optical_revision

    source = uuid4()
    zone = case.build(source)
    zone.activate(parent_event=_cause(source))
    assert zone.affected_positions == ZONE_CELLS, case.name
    # None of these zones blocks physical optics; only an obscuring one writes obscurement.
    assert grid.optical_revision == optical_before, case.name
    assert _obscured(grid) is case.moves_optical, case.name

    installed = _observe(near)
    assert installed.hazards == dict.fromkeys(ZONE_CELLS, case.zone_hazard), case.name
    assert installed.perceived_effects == before.perceived_effects | {zone.uuid}, case.name
    before_cost, installed_cost = before.path_cost_beyond, installed.path_cost_beyond
    assert before_cost is not None, case.name
    if case.hides_beyond:
        assert not cell_in(installed.visible, BEYOND), case.name
    else:
        assert installed.visible == before.visible, case.name
        assert installed_cost is not None, case.name
        assert (installed_cost > before_cost) is case.difficult, case.name

    zone.deactivate(parent_event=_cause(source))
    assert not _obscured(grid) and grid.optical_revision == optical_before, case.name
    assert _observe(near) == before, case.name


def test_zones_change_only_the_world_channels_they_write() -> None:
    cases = [
        ZoneCase("grease: movement and hazard only",
                 lambda source: GreaseZone(source_entity_uuid=source, position=(4, 1),
                                           affected_positions=set(ZONE_CELLS)),
                 moves_optical=False, zone_hazard=True, difficult=True, hides_beyond=False),
        ZoneCase("spike growth: perceived hidden hazard",
                 lambda source: SpikeGrowthZone(source_entity_uuid=source, position=(4, 1),
                                                affected_positions=set(ZONE_CELLS), spell_dc=0),
                 moves_optical=False, zone_hazard=True, difficult=True, hides_beyond=False),
        ZoneCase("fog cloud: heavy obscurement",
                 lambda source: FogCloudZone(source_entity_uuid=source, position=(4, 1),
                                             affected_positions=set(ZONE_CELLS)),
                 moves_optical=True, zone_hazard=None, difficult=False, hides_beyond=True),
    ]
    for case in cases:
        check_zone(case)
