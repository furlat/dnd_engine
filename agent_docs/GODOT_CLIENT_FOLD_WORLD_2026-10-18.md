# Godot client: folding the schema-16 world

The world part of player schema 16 (E3-world). Reference fold: `dnd/player/world_reduction.py`
(`fold_world_update`), called by `dnd/player/reduction.py` at each node's occurrence; codec
`dnd/player/world_columns.py`. Golden vectors: `sdk/protocol/fold-vectors/world/*.json` (world updates)
and `sdk/protocol/fold-vectors/groups/*.json` (a walk group). Godot must reproduce their expected values.

The server keeps no copy of what a client holds. Each update says what the seat perceived change at one
occurrence, so the client's memory follows from the rules below and nothing else.

## 1. `WorldUpdate` (one per occurrence)

| Field | Meaning |
| --- | --- |
| `entered` (`CellMask`) | the update's authoritative cells: cells entering the seat's view, and visible cells whose tile was written whole |
| `tiles_unchanged` (`CellMask`) | entered cells whose tile nothing wrote since the seat last had it whole (its revision stamp): the client keeps the tile it holds there, with its condition names and residues |
| `tile_looks` | a tile surface and name under its content id (`look_id`, a digest of the value), once per id per seat |
| `tile_statics` | a tile's fixed part (`position`, `tile_uuid`, `look`: a `tile_looks` id), once per tile uuid per seat |
| `tile_columns` | the entered cells holding a tile, but those in `tiles_unchanged`: their changeable scalars as columns (§2) |
| `tile_conditions` | a tile's own condition names (never its residues' names), whole list per cell |
| `tile_changes` | a perceived tile's changed scalars (`WorldTileChanges`: costs, optics, propagation, elevation, surface kind, slope axis, default light) |
| `resolved_light` (`CellValues`) | a perceived tile's objective light |
| `residue_materials` | a residue material's fixed part (`residue_id`, `name`, `description`, `max_amount`), once per id per seat |
| `residues` | one material on one cell: whole when it carries `condition_uuid` (replaces what is held), else keyed (`amount`, and `contributions` set by index; the index after the last appends) |
| `residues_removed` | (cell, material) keys removed |
| `boundary_structures` | a boundary structure's value under its content id (a digest of the value), once per id per seat |
| `object_looks` | an object's fixed part (`ObjectLook`), once per item uuid per seat, floor objects and contained items alike |
| `objects` (`ObjectColumns`) | the update's object rows as columns (below); each row is `item_uuid`, `members`, `state` (`ObjectState`), `placement` (`ObjectPlacement`), `observed_faces` (§3) |
| `objects_unchanged` | objects on the entered cells that nothing wrote since the seat last had them whole: the client keeps them as held |
| `objects_removed` | objects the seat saw go |
| `contents` | a container's whole contents (`ContainedItem`: uuid and state; looks through `object_looks`) |
| `contents_changed` | keyed contents of a container the seat sees into: `upserted`, `removed` |
| `connectors` | connector upserts (whole rows) |
| `connectors_removed` | connector uuids the seat saw removed |

A field holding its default is left out.

### `ObjectColumns` (an update's object rows)

Row *i* is the *i*-th entry of `item_uuids`; field names travel once per update.
- `name` and `map_char` are dense: one value per row.
- Every other field of a row is a `Column` (`rows`, `values`), left out when no row holds a non-default value.
  - `rows` is a `RowBits` subset of the update's rows (left out: every row), and `values` holds one value per selected row, in row order.
  - A row the column skips holds the field's default: `None` / `[]`, `stack_count` 1, `is_pickable` true, `blocks_propagation` false, `integrity` intact, and no `members` (one observer) or `observed_faces`.
- `placements` (left out: no row carries a placement) has its own `rows` subset of the update's rows.
  - `position` and `top_height_steps` are dense over those rows.
  - Every other `ObjectPlacement` field is a `Column` over the placed rows, with that field's default when skipped.

### `ObjectState`

`visual_item_name` is left out when it equals `name`. `boundary_structure` is the content id of a
`boundary_structures` row. `construction_geometry` is state, not look: a cut construction's geometry changes.

### `ObjectPlacement` (an object row's placement, as `placements` decodes it)

It carries what the full `WorldObjectPlacement` holds that is neither derivable nor a default. To decode it:

| Field | When left out |
| --- | --- |
| `object_uuid` | always: it is the row's `item_uuid` |
| `kind` | always: `boundary` when `boundary_direction` is present, else `center` |
| `tile_uuid` | left out: it is the `tile_uuid` of the client's static tile row at `position` (an error if the client holds none) |
| `covered_supports` | left out: the single anchor support (`position`, `tile_uuid`) |
| `occupies_bands` | `true` |
| `base_height_steps` | `0` |
| `orientation` | `null` |
| `removed_bands` | `[]` |

`position` and `top_height_steps` are always present.

## 2. Tile columns

One byte per cell per column, in `cells` order (x, then y: the `CellValues` order):
`walking_cost`, `flying_cost`, `swimming_cost`, `burrowing_cost` (0..255), `default_light`,
`resolved_light` (`LightLevel`), and `flags`:

| Bits | Value |
| --- | --- |
| 0 | `blocks_optics` |
| 1 | `blocks_propagation` |
| 2-3 | surface kind: 0 ordinary, 1 stairs, 2 ramp |
| 4-5 | slope axis: 0 none, 1 north-south, 2 east-west |

`elevation_steps` is a list of signed ints, one per cell, absent when every cell is at 0. A cell's
tile is its static row (the latest one received for its position) joined with its column values.
Its surface and name are its static row's look. Its condition names start empty, and its rows in the same update
fill them.

## 3. Fold order of one update

1. **Static rows.** Store `tile_looks` by content id, `tile_statics` by position (the latest one wins), `residue_materials` and `object_looks` by id, and `boundary_structures` by content id. They are never pruned. A look, a material or a structure never changes for its id (an id naming another value is an error).
2. **Removals.** Pop `objects_removed` (with their members) and `connectors_removed`. Each names something the client holds.
3. **Reset `entered`.** For every entered cell:
   - drop its tile and rebuild it from the columns, unless the cell is in `tiles_unchanged` (then keep the held tile as it is);
   - drop every held object that touches the cell (its supports and, for a boundary, the opposite incident cell) and is in neither `objects` nor `objects_unchanged`;
   - remove the cell from the `construction_suppressions` positions of every object still held;
   - drop every connector with an endpoint there.

   A `tiles_unchanged` cell that is not entered, not held or also in `tile_columns`, or an `objects_unchanged` object the client does not hold, is an error. The client never evicts what it holds otherwise: a record unchanged since the seat had it is not sent at all when it re-enters perception off the entered cells (a contact regained), so the client must still hold it.
4. **Object rows, in order.**
   - Otherwise the item is the look joined with the state. The placement is the row's, or the held one.
   - Residues: the row's residues lie on its `observed_faces`. Held faces outside `observed_faces` are kept, and residues are united by `condition_uuid`. Drop empty ones and sort by `condition_uuid` as a string.
   - Suppressions: the row's providers replace the held rows of those providers, and the other held rows stay after them.
   - Contained items stay as held.
   - `members` is the row's bitset. A seat with one observer leaves it out, meaning 1.
5. **Contents.** `contents` sets the contained items (sorted by uuid as a string). `contents_changed` removes and upserts by uuid; the container's contents must be held.
6. **Keyed tile rows** (cells perceived before and after, never an entered cell).
   - Apply `tile_changes`, then `resolved_light`.
   - `tile_conditions` replaces the cell's own names.
   - Apply `residues` (whole or keyed), then `residues_removed`.
   - The cell's `condition_names` is its own names followed by its residues' material names, in `residue_id` order.
   - A keyed row on a cell the client does not hold is an error.
7. **Connector upserts**, by uuid.

## 4. The memory rules

| Rule | Where the wire is authoritative |
| --- | --- |
| Cells entering view (or a visible tile written whole) | `entered`: the client keeps only what the update carries or keeps there (`tiles_unchanged`, `objects_unchanged`) |
| An object is forgotten when its support is seen without it | `entered` (step 3), plus `objects_removed` (the seat saw it go, or saw its support without it) |
| A wall's unseen faces keep their last sight | each row's `observed_faces`, including faces now empty |
| A construction's suppressed cells retire where they enter view | `entered` (step 3), plus each row's perceived providers |
| Contents | kept when the seat stops seeing into the container; whole again when it sees in again |
| Leaving view | sends nothing: tiles, objects, connectors and contents outside the scopes above stay as held |

Display is the client's policy. For example, it may hide a held container's contents while the container is
closed or out of visual contact, or hide suppressions of providers it does not perceive now.

## 5. Object members (D2)

`members` is exact whenever an object's row is sent (entering or keyed). Between rows the client holds the
bits of the last row. The members holding a contact come from the sensory contact rows
(`object_contact_members`).

## 6. Walk groups

Roots whose versions interleave arrive as one `PlayerLineage`, named by the root completing last: the other
roots are parentless lineages inside the group, whose nodes are in native order. Fold a group's nodes in occurrence order (as for any lineage). A branch of the root keeps the
parentless lineages inside its interval (`lineage_branch`). Vector: `groups/g1_*.json`.
