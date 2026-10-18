# Godot client: folding player schema 15

The changes from schema 14 only. Reference fold: `dnd/player/reduction.py` (`sensory_values`,
`sensory_changes`, `apply_record_fact`, `apply_world_update`, `_apply_nodes`).
`player_schema_version` is 15 with a new `schema_digest` (`sdk/protocol/protocol-identity.json`);
saved `PlayerSequence` packets are schema 8.

## 1. Row subsets: `RowBits`

`{start, bits}`: row `8 * start + i` of a row table is in the subset iff bit `i` of `bits` is set,
least significant bit first in each byte. `bits` is padded URL-safe base64, like `CellMask.bits`.
Absent (or `bits` empty) means the empty subset. A bit past the end of its table is an error.

## 2. A group's cell rows (`SensoryRows`)

Three row tables, each absent when empty:

| Field | Rows |
| --- | --- |
| `cells` (`CellMask`) | the cells of the mask, in cell order (x, then y) |
| `light_levels` (`[CellValues]`) | (cell, level) pairs, by cell in cell order, then by layer |
| `hazards` (`[CellValues]`) | (cell, value) pairs, the same way |

Layer k holds, for each cell having more than k values in the group, its (k+1)-th smallest
value; every cell of layer k+1 is in layer k. Rows: for each cell of layer 0 in cell order, one
row per layer holding it, in layer order.

## 3. `SensoryFact` changes

| Field | 14 | 15 |
| --- | --- | --- |
| `observer_uuid` | uuid | removed; `observer` is an index into `uuids` |
| `visible_cells_added`, `visible_cells_removed`, `seen_cells_added` | `CellMask` | `RowBits` over `cells` |
| `effective_light_levels_changed` | `CellValues` | `RowBits` over `light_levels` rows |
| `hazardous_cells_changed` | `CellValues` | `RowBits` over `hazards` rows |

Resolve each list to the schema-14 value: the selected rows' cells form the mask; for a value list,
each selected row gives its cell its value (a list never selects two rows of one cell).
A value list leaves out a 0 at a cell the same fact adds to view: when folding, a cell that comes
into view without a light or hazard value has value 0 (this is what the schema-14 fold produced
for those cells).

## 4. Contact and light source rows

Contacts are columns: contact row i is `uuids[contact_uuid_index[i]]` at `contact_positions[i]`,
`visual` iff row i is in `contact_visual` (`RowBits`), with special senses
`contact_special_senses[i]`; that column is absent when no row has any (read `[]`). The schema-14
`contacts` column is gone.

`light_sources[i]` is a `LightRow`. Resolve it to the schema-14 `PerceivedLightSource`:

| `LightRow` | `PerceivedLightSource` |
| --- | --- |
| `source` | `source_uuid = uuids[source]` |
| `anchor_entity`, `anchor_item` (absent: null) | `anchor_entity_uuid`, `anchor_item_uuid` = `uuids[...]` |
| `affected_tiles` (`CellValues`, absent: empty) | `affected_tiles = {"x,y": level}` |
| `base_height_steps` (absent: 0), `appearance` (absent: `"neutral"`), `actor_anchored` (absent: false) | same names |
| `revision`, `position`, `very_bright_radius_feet`, `bright_radius_feet`, `dim_radius_feet` | same |

## 5. Sightings

`SpatialEffectSighting.positions` and `.visible_volume_positions` are `CellMask`s (absent volume:
empty). Unpack each in cell order: that is the order of the perceived effect's sorted lists.
Every other sighting field holding its default (null, false, `[]`) is left out.

## 6. Nodes, versions, resolutions

- `PlayerNode.resolution_ref` is gone. `resolution` (absent: none) indexes the group's
  `resolutions` (`PlayerLineage`/`PlayerInitialization`, absent: `[]`): `{lineage, application_id?}`,
  `lineage` the seat's lineage index, `application_id` present for an application's resolution.
  Nodes with the same resolution name the same row.
- `SpellFact.application` is `{lineage, application_id, index}`; `lineage` is the seat's lineage index.
- `version_rows` is `{occurrences: [int], lineages: [int]}` (two equal-length columns; absent column: `[]`).
- Fields left out when they hold their default: on `PlayerNode` `parent_event`, `parent_lineage`,
  `fact`, `resolution`, `cancellation`, `combat_log`, `turn_execution_id` (null), `canceled` (false),
  `children_lineages`, `content_attributions` (`[]`); on `PlayerObservation` `changes` (`{}`),
  `contact` (null), `items` (`[]`); on every fact, a field whose default is null, false or `[]`
  (e.g. `DamageRequestFact.source_condition_uuid`, `SpellFact.target_position`, `SpatialFact.creation`).
  Fields without a default (e.g. `SpellFact.target_entity_uuid`) are still always present.

## 7. World updates

`WorldUpdate.resolved_light` (`CellValues`, absent: empty) is the changed resolved light of known
tiles: set each listed tile's `resolved_light` to its value (a `LightLevel`). `tile_changes` no
longer carry `resolved_light`. Apply `tiles`, then `tile_changes`, then `resolved_light`; their
fields never overlap.
