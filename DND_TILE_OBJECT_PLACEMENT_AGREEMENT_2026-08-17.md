# Tile object placement agreement

Status: superseded by
`DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md`.

This note records the narrow placement model agreed on before the Tile/GridMap
refactor. It is not an implementation plan and does not settle unrelated item,
content, event, or rendering work.

## Fixed constraints

- The game has one physical `Tile` for each `(x, y)` coordinate. There are no
  stacked backend surfaces at the same XY.
- `Tile` owns the persistent forward record of objects placed in its center and
  on each of its four cardinal boundaries.
- `GridMap` coordinates every placement, movement, rotation, and removal and
  maintains reverse indices so an object is never found by scanning all Tiles.
- The placed object does not own its current Tile, boundary, or orientation.
- A world-item class or instance owns its intrinsic placement behavior:
  whether it is a center or boundary object, whether it exclusively claims that
  placement slot, and which movement/vision/light/propagation channels it
  affects.
- The caller chooses the requested Tile, boundary, and game-space orientation.
  The caller cannot override whether the object occupies the slot.

## Placement vocabulary

Center versus boundary is a distinct placement-kind fact. Boundary direction
and object orientation reuse the existing `CardinalDirection`; no second
direction enum should be introduced.

- `CENTER`: the object is stored in the Tile center collection.
- `BOUNDARY`: the object is stored in the collection for one required cardinal
  boundary.
- Orientation is optional and independent of placement. A center chest may face
  north. A wall attached to the east boundary normally derives its orientation
  from that boundary unless it has a genuinely independent facing.

## Tile storage shape

The exact field names remain open, but the required information is equivalent
to:

```python
center_objects: dict[UUID, CardinalDirection | None]
boundary_objects: dict[
    CardinalDirection,
    dict[UUID, CardinalDirection | None],
]

center_occupant_uuid: UUID | None
boundary_occupant_uuids: dict[CardinalDirection, UUID]
```

The object dictionaries contain every placed object and its optional
orientation. The occupant fields identify the one object, if any, that
exclusively reserves the corresponding physical slot.

Consequently, a stone wall may reserve the east boundary while a drape and wall
torch coexist in the same east-boundary collection without reserving it. A
crate may reserve the center while nonblocking small objects coexist in the
center collection.

## GridMap indices and invariants

GridMap retains or adds reverse lookup equivalent to:

```python
object_uuid -> tile_position
object_uuid -> boundary_direction | center
```

These indices are synchronized by the GridMap mutation boundary and can be
rebuilt from Tile placement records after loading.

Placement must reject:

- an object whose intrinsic placement kind does not match the requested center
  or boundary location;
- an occupying object when the requested slot already has an occupant;
- two occupying boundary objects representing the same physical edge through
  opposite sides of adjacent Tiles; and
- direct caller attempts to weaken an object's intrinsic slot claim.

Movement and removal use the reverse indices, update the old and new Tile
records atomically, recompute affected blocking, and publish the corresponding
event facts.

## Rendering boundary

Position, center/boundary placement, cardinal direction, orientation, material,
height, and blocking semantics are backend game facts. Sprite names, asset
families, pivots, painter layers, pixel offsets, and renderer rotations remain
client binding responsibilities.
