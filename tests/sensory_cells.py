"""Recorded sensory delta values written as positions, packed into the event's cell values."""

from dnd.core.cells import mask_from_positions, mask_positions, values_from_items

CELL_SETS = ("visible_cells_added", "visible_cells_removed", "seen_cells_added")
CELL_VALUES = ("effective_light_levels_changed", "hazardous_cells_changed")


def packed_cells(values: dict) -> dict:
    """Delta values with cell sets given as positions and cell values as {(x, y): value}, packed."""
    result = dict(values)
    for key in CELL_SETS:
        if key in result:
            result[key] = mask_from_positions(result[key])
    for key in CELL_VALUES:
        if key in result:
            result[key] = values_from_items({position: int(value) for position, value in result[key].items()})
    return result


def cells(mask) -> set[tuple[int, int]]:
    return set(mask_positions(mask))
