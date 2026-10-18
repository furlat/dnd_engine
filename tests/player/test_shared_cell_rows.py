"""A group's shared cell rows (player schema 15): each fact's cells come back exactly from its row subset.

The boundary is the wire encoding the client resolves: the server packs every
fact's cell lists against one row table per group, the client selects each
fact's rows. Cases are data: per-fact cell sets or (cell, value) maps.
"""
from dataclasses import dataclass

import pytest

from dnd.core.cells import (layer_rows, mask_from_positions, mask_rows, selected_mask, selected_values, shared_cells,
    shared_values, update_cells, values_from_items, zeros_left_out)
from dnd.types.cells import EMPTY_CELLS, EMPTY_VALUES, RowBits


@dataclass(frozen=True)
class ValuesCase:
    name: str
    facts: tuple[dict[tuple[int, int], int], ...]
    rows: int  # distinct (cell, value) pairs in the group


VALUE_CASES = (
    ValuesCase("one observer", ({(0, 0): 3, (1, 0): 2},), 2),
    ValuesCase("observers agree on a cell", ({(4, 4): 3}, {(4, 4): 3, (5, 4): 1}), 2),
    ValuesCase("observers see one cell at two levels", ({(2, 2): 1}, {(2, 2): 3}, {(2, 2): 1, (3, 2): 4}), 3),
    ValuesCase("negative coordinates and an empty fact", ({(-3, -1): 0, (-2, 5): 2}, {}), 2),
)


def check_values(case: ValuesCase) -> None:
    sent = [values_from_items(fact) for fact in case.facts]
    layers, bits = shared_values(sent)
    rows = layer_rows(layers)
    assert rows.xs.size == case.rows, case.name
    assert [selected_values(rows, row) for row in bits] == sent, case.name


@pytest.mark.parametrize("case", VALUE_CASES, ids=lambda case: case.name)
def test_value_lists_resolve_to_the_sent_values(case: ValuesCase) -> None:
    check_values(case)


def test_cell_lists_resolve_to_the_sent_sets() -> None:
    sent = [mask_from_positions(cells) for cells in ({(0, 0), (9, 9)}, set(), {(9, 9), (-1, 4)})]
    table, bits = shared_cells(sent)
    assert [selected_mask(mask_rows(table), row) for row in bits] == sent
    assert table == mask_from_positions({(0, 0), (9, 9), (-1, 4)})


def test_a_subset_outside_its_table_or_naming_one_cell_twice_is_rejected() -> None:
    layers, _ = shared_values([values_from_items({(2, 2): 1}), values_from_items({(2, 2): 3})])
    rows = layer_rows(layers)
    with pytest.raises(ValueError):
        selected_values(rows, RowBits(0, bytes([0b111])))
    with pytest.raises(ValueError):
        selected_values(rows, RowBits(0, bytes([0b11])))


def test_a_zero_left_out_at_a_cell_coming_into_view_folds_the_same() -> None:
    visible = mask_from_positions({(0, 0)})
    light, hazard = values_from_items({(0, 0): 2}), values_from_items({(0, 0): 1})
    added = mask_from_positions({(1, 0), (2, 0)})
    light_changed = values_from_items({(1, 0): 0, (2, 0): 3})
    hazard_changed = values_from_items({(1, 0): 0, (2, 0): 0})
    expected = update_cells(visible, light, hazard, EMPTY_CELLS, added, light_changed, hazard_changed)
    assert zeros_left_out(hazard_changed, added) == EMPTY_VALUES
    assert update_cells(visible, light, hazard, EMPTY_CELLS, added, zeros_left_out(light_changed, added),
        zeros_left_out(hazard_changed, added)) == expected
