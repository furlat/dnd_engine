"""The cells a placed object touches (`placement_support_cells`): the one rule the world fold indexes objects by and
the seats' world snapshots and the client's reset of entered cells read."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from dnd.types.world import CardinalDirection
from dnd.types.world_placement import (WorldObjectPlacement, WorldObjectSupport, WorldPlacementKind,
    placement_support_cells)


@dataclass(frozen=True)
class Case:
    name: str
    kind: WorldPlacementKind
    supports: tuple[tuple[int, int], ...]
    expected: frozenset[tuple[int, int]]
    boundary_direction: CardinalDirection | None = None
    removed_bands: tuple[tuple[int, int, int], ...] = ()


CASES = (
    Case("center on one support", WorldPlacementKind.CENTER, ((3, 4),), frozenset({(3, 4)})),
    Case("center over several supports", WorldPlacementKind.CENTER, ((3, 4), (4, 4), (4, 5)),
         frozenset({(3, 4), (4, 4), (4, 5)})),
    Case("a support whose every band is removed is not touched", WorldPlacementKind.CENTER, ((3, 4), (4, 4)),
         frozenset({(3, 4)}), removed_bands=((4, 4, 0), (4, 4, 1))),
    Case("a support keeping one band is touched", WorldPlacementKind.CENTER, ((3, 4), (4, 4)),
         frozenset({(3, 4), (4, 4)}), removed_bands=((4, 4, 0),)),
    Case("a boundary touches its owner and the incident cell beyond it", WorldPlacementKind.BOUNDARY, ((3, 4),),
         frozenset({(3, 4), (3, 5)}), boundary_direction=CardinalDirection.NORTH),
    Case("west boundary", WorldPlacementKind.BOUNDARY, ((3, 4),), frozenset({(3, 4), (2, 4)}),
         boundary_direction=CardinalDirection.WEST),
)


def placement(case: Case) -> WorldObjectPlacement:
    supports = tuple(WorldObjectSupport(position=position, tile_uuid=uuid4()) for position in case.supports)
    return WorldObjectPlacement(object_uuid=uuid4(), tile_uuid=supports[0].tile_uuid, position=case.supports[0],
        kind=case.kind, occupies_bands=True, boundary_direction=case.boundary_direction, base_height_steps=0,
        top_height_steps=2, covered_supports=supports, removed_bands=case.removed_bands)


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_placement_support_cells(case: Case) -> None:
    assert placement_support_cells(placement(case)) == case.expected, case.name
