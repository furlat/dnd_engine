"""Packed sets of map cells: plain bytes and ints, no numpy.

A `CellMask` is a set of map cells over its bounding box; a `CellValues` is
one byte per cell of a mask, in the mask's cell order. Both are canonical: a
mask's box is the bounding box of its cells, so equal sets are equal values
and an empty set has width and height 0. The array operations on them live in
`dnd.core.cells`.
"""

from typing import Annotated

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass

# Bytes are base64url on the wire. A pydantic dataclass keeps that in every dump,
# including the event archive's `serialize_as_any` one.
PACKED = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")


@dataclass(frozen=True, slots=True, config=PACKED)
class CellMask:
    """A set of map cells: cell (x0 + i, y0 + j) is bit i * height + j of `bits`,
    least significant bit first within each byte."""

    x0: int
    y0: int
    width: int
    height: int
    bits: bytes


@dataclass(frozen=True, slots=True, config=PACKED)
class CellValues:
    """One byte per cell of `cells`, in its cell order (x, then y)."""

    cells: CellMask
    values: bytes


EMPTY_CELLS = CellMask(0, 0, 0, 0, b"")
EMPTY_VALUES = CellValues(EMPTY_CELLS, b"")


def cell_in(mask: CellMask, position: tuple[int, int]) -> bool:
    """Whether a map cell belongs to the set."""
    i, j = position[0] - mask.x0, position[1] - mask.y0
    if not (0 <= i < mask.width and 0 <= j < mask.height):
        return False
    index = i * mask.height + j
    return bool(mask.bits[index >> 3] >> (index & 7) & 1)


def value_at(values: CellValues, position: tuple[int, int]) -> int | None:
    """A cell's value, None for a cell outside the set."""
    mask = values.cells
    i, j = position[0] - mask.x0, position[1] - mask.y0
    if not (0 <= i < mask.width and 0 <= j < mask.height):
        return None
    index = i * mask.height + j
    byte, bit = index >> 3, index & 7
    if not mask.bits[byte] >> bit & 1:
        return None
    rank = int.from_bytes(mask.bits[:byte], "little").bit_count() + (mask.bits[byte] & ((1 << bit) - 1)).bit_count()
    return values.values[rank]


def no_cells(mask: CellMask) -> bool:
    return mask.width == 0


def no_values(values: CellValues) -> bool:
    return values.cells.width == 0


# A changed-cells field: the empty value is its default and is left out of a dump.
CellMaskField = Annotated[CellMask, Field(exclude_if=no_cells)]
CellValuesField = Annotated[CellValues, Field(exclude_if=no_values)]


__all__ = ["CellMask", "CellValues", "EMPTY_CELLS", "EMPTY_VALUES", "CellMaskField", "CellValuesField", "cell_in", "value_at", "no_cells", "no_values"]
