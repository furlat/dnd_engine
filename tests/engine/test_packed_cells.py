"""Packed cell sets behave as the sets and per-cell maps they replace."""

import random

from pydantic import BaseModel

from dnd.core.cells import (mask_difference, mask_from_positions, mask_intersection, mask_positions, mask_union,
    update_cells, values_from_items, values_items)
from dnd.types.cells import EMPTY_CELLS, CellMask, CellValues, cell_in, no_cells, value_at


class Carrier(BaseModel):
    mask: CellMask
    values: CellValues


def random_cells(rng: random.Random) -> set[tuple[int, int]]:
    x0, y0 = rng.randint(-3, 6), rng.randint(-3, 6)
    return {(x0 + rng.randint(0, 9), y0 + rng.randint(0, 9)) for _ in range(rng.randint(0, 25))}


def check(first: set[tuple[int, int]], second: set[tuple[int, int]], levels: dict[tuple[int, int], int],
          removed: set[tuple[int, int]]) -> None:
    a, b = mask_from_positions(first), mask_from_positions(second)
    assert set(mask_positions(a)) == first and len(mask_positions(a)) == len(first)
    assert no_cells(a) is (not first) and (a == EMPTY_CELLS) is (not first)
    assert all(cell_in(a, (x, y)) is ((x, y) in first) for x in range(-4, 17) for y in range(-4, 17))
    assert set(mask_positions(mask_union(a, b))) == first | second
    assert set(mask_positions(mask_difference(a, b))) == first - second
    assert set(mask_positions(mask_intersection(a, b))) == first & second
    # Equal sets are equal values, whatever box they were built over.
    assert mask_union(a, b) == mask_from_positions(first | second)
    # A delta: `removed` leaves, `second` arrives with light 7 and hazard 1.
    previous = values_from_items({cell: levels[cell] for cell in first})
    hazards = values_from_items({cell: 0 for cell in first})
    after, updated, hazard = update_cells(a, previous, hazards, mask_from_positions(removed), b,
        values_from_items({cell: 7 for cell in second}), values_from_items({cell: 1 for cell in second}))
    kept = (first - removed) | second
    expected = {cell: 7 if cell in second else levels[cell] for cell in kept}
    assert set(mask_positions(after)) == kept
    assert dict(values_items(updated)) == expected
    assert dict(values_items(hazard)) == {cell: int(cell in second) for cell in kept}
    # The same cells, values changed on some of them (and named outside them: ignored).
    same, light_after, hazard_after = update_cells(a, previous, hazards, EMPTY_CELLS, EMPTY_CELLS,
        values_from_items({cell: 5 for cell in second}), values_from_items({cell: 1 for cell in second}))
    assert same == a
    assert dict(values_items(light_after)) == {cell: 5 if cell in second else levels[cell] for cell in first}
    assert dict(values_items(hazard_after)) == {cell: int(cell in second) for cell in first}
    assert all(value_at(updated, cell) == value for cell, value in expected.items())
    assert value_at(updated, (99, 99)) is None
    carrier = Carrier(mask=a, values=updated)
    for dumped in (carrier.model_dump_json(), carrier.model_dump_json(serialize_as_any=True)):
        assert Carrier.model_validate_json(dumped) == carrier


def test_packed_cells_match_set_and_map_semantics():
    rng = random.Random(7)
    for _ in range(300):
        first, second = random_cells(rng), random_cells(rng)
        check(first, second, {cell: rng.randint(0, 3) for cell in first}, {cell for cell in first if rng.random() < 0.3})
