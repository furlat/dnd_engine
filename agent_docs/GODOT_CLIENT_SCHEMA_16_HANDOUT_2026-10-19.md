# Godot client: integrating player schema 16 (one handout)

Engine: `codex/event-native-deltas` at c66ea3de5. Identity: protocol 1, player schema 16, digest
`49d14bc20920f5698eb4f09e3aeece442380242cd1453893d45f94ea9fb0c8a5`. Saved `PlayerSequence` files are schema 9.

This handout replaces the five fold notes (`GODOT_CLIENT_FOLD_{SCHEMA_14,SCHEMA_15,WORLD,BODIES,HUD}_2026-10-18.md`).
Where it disagrees with them, it follows the later code. The executable spec is `dnd/player/reduction.py` (bodies,
sensory, HUD, log, order), `dnd/player/world_reduction.py` (world) and `dnd/player/world_columns.py` (codecs). When
this text and the code disagree, the code is right. `sdk/protocol/README.md` still describes schema 15; do not use it
for 16.

**Where NDClient is now** (checked 2026-10-19 on the furlat/NDClient checkout
`/mnt/c/Users/tommaso/Documents/Dev/NDClientGodot`, branch `feature/opus-refactor`):
- `sdk/protocol-identity.json` and `sdk/player-api-v1.schema.json` pin schema **9** (digest `377b1982…`) on every branch.
- `sdk/reducer.gd` keys world updates by `event_uuid` and reads `observations`. Those are pre-12 shapes.
- `authoring/server_ids.json` is a schema-15 snapshot of the NPC lane (ef82cb7ba).

So implement the fold from §2 as a full spec. §1 is only a map of what moved.

---

## 1. What changed (15 → 16; the 14 → 15 rows are still in force)

| Area | Schema 15 | Schema 16 |
| --- | --- | --- |
| Envelope | `PlayerLineage.generation`, `.observer_uuid`, `.audience`; `PlayerOperation.audience` | Stated once: `PlayerUpdate`/`PlayerOperation` `generation` and `observer_uuid`. The audience is only in `PlayerInitialization.audience` |
| Nodes | `PlayerNode.lineage` | Gone. A node's lineage is its `version_rows` entry (`occurrences[i]` → `lineages[i]`) |
| Spells | `SpellFact.application`; the declaration on every node | `application` is gone. The declaration (`source_entity_uuid`, `behavior_id`, `name`, `source_position`, `declared_target_entity_uuids`, `cast_origin`, `area_propagation`) is only on the cast. An application node carries none, and its cast's node is in the same group |
| Trap removal | `SpatialEffectStateFact.positions` always | A removal sends `removed_positions` only (`positions` is left out) |
| Bodies | `observations` (`PlayerObservation`, `ActorChanges`, `ItemPatch`) | `bodies`: `BodyRecord {occurrence, actor_uuid, birth?, body: BodyState, loadout?, items?: ItemRecord[]}` |
| Body changes | `EquipmentFact`, `ConditionChangeFact`, `ItemEffectChangeFact` | One `ActorChangeFact {kind: "actor_change", actors: [{actor_uuid, rows}], items?}` (§2.6) |
| Conditions | `ConditionFact` (`event_uuid`, `resulting_*`, `consumed`) | `ConditionMember {condition_uuid, name, category, behavior_id, state}` |
| Item effects | `ItemLook.item_effects` | `PlayerItem.effects`; the look is static |
| World tiles | `WorldUpdate.tiles` (whole `WorldTileState`) | `entered`, `tiles_unchanged`, `tile_looks`, `tile_statics`, `tile_columns`, `tile_conditions`, `residue_materials`, `residues`, `residues_removed` |
| Tile changes | `WorldTileChanges` carries surface, name, condition names, residues | Scalars only. Look: static. Own conditions: `tile_conditions`. Residues: keyed rows |
| World objects | `objects: [PlayerObject]` | `object_looks` (static) + `objects` (`ObjectColumns`) + `objects_unchanged`. Also new: `contents`, `contents_changed`, `connectors_removed`, `boundary_structures` |
| Sensory | One fact per member (`observer` index), `observer_position` always, `cause_occurrence`, `seen_cells_added`, `spatial_effect_sightings`, `light_sources_changed`, removal revisions | One **composed** fact per settlement. `observer_position` only when it changed. Seen cells not sent. Effects `added`/`patched`/`removed`/`cells_retired`. Lights `added`/`patched`/`removed`. Member bitsets on contact and effect rows |
| Sensory rows | `light_removal_uuid_index`, `light_removal_revisions`; `LightRow.revision`, `.affected_tiles`; `SpatialEffectSighting.owner_revision` | Removed. New columns: `contact_members`, `sighting_members`, `patch_uuid_index`, `sighting_patches`, `retired_uuid_index`, `retired_cells`, `light_patches` |
| HUD | `PlayerHUDPatch.generation`, `observer_uuid`, `revision`, `sheet_order`; sheet `name`, `portrait_key`, `normal_hp`, `maximum_hp` | Removed (read those from the body). New: `SheetPatch.resource_values` |
| Enums | — | `ConditionRemovalTrigger` + `encounter_end`. `EventType` + `actor_sheet`, `initiative_order_changed` |
| 14 → 15 (still in force) | — | `RowBits` subsets, group cell tables, contact columns, `LightRow`, sightings as `CellMask`, `PlayerNode.resolution` index, `version_rows` as two columns, `WorldUpdate.resolved_light` |

Combat-log types did not change; Choices did not change between 15 and 16, but see §2.9 for free aim, which a schema-9 client has never seen.

---

## 2. The fold model

### 2.1 Encodings

- **Absent means default:** `[]`, `{}`, `false`, `null`, `0`, or the default named for that field. Never use truthiness: a
  present `sense_modes: []` or `passive_perception: 0` is a real value.
- **`CellMask {x0, y0, width, height, bits}`:** cell `(x0+i, y0+j)` is bit `i*height + j` of `bits`, least significant
  bit first in each byte. `bits` is padded URL-safe base64. Cell order is x, then y. An empty set has width 0.
- **`CellValues {cells, values}`:** one byte per cell of `cells`, in cell order. Every other byte column (tile columns)
  is base64 too.
- **`RowBits {start, bits}`:** row `8*start + i` of a row table is in the subset iff bit `i` of `bits` is set. A bit
  past the end of the table is an error.
- **Ids are opaque:** `look_id`, `structure_id` and `visual_loadout_id` are server digests. Never recompute them.

### 2.2 What the client holds (`PlayerState`)

| Store | Key | Written by |
| --- | --- | --- |
| `tiles` | cell | world: entered columns, keyed tile rows |
| `objects` (`{placement, item, contained_items}`), `object_members` | item uuid | world object rows, contents |
| `connectors` | uuid | world |
| `static` | see §2.4 | static rows, never pruned |
| `senses` (visible, seen, light, hazard, entity and object contacts, effects, position, capability scalars, `paths_dirty`) | — | composed sensory facts |
| `entity_members`, `object_contact_members`, `effect_members` | uuid | sensory contact and effect rows |
| `light_sources` | source uuid | sensory light rows |
| `remembered_effects` | effect uuid | sensory fold (memory) |
| `spatial_content` | effect uuid | `SensoryFact.spatial_effect_content` |
| `actors` (bodies), `items` | uuid | body records, `ActorChangeFact` and the other record facts (§2.6) |
| `round_number`, `current_actor_uuid` | — | `TurnFact` |
| `hud_snapshot` (sheets, initiative), `content`, `combat_log_appends` | — | update envelope |
| `reducer_cursor`, `spatial_commit_cursors` | — | order bookkeeping |

The client creates nothing beyond this. The server keeps no copy of the client, so the client's memory is exactly
what these rules produce.

### 2.3 Order

**Initialization** (`reduce_initialization`): fold its nodes as one group (below), set `reducer_cursor = end_cursor`,
apply `hud`, then store `content_additions`.

**Each operation** (`reduce_operation`), in this order:
1. `generation` and `observer_uuid` must match.
2. `content_additions`: an id that comes back with another definition is an error.
3. Each lineage in order: `start_cursor` must equal `reducer_cursor` (no gap), then fold the group and set
   `reducer_cursor = end_cursor`.
4. `hud`, then `combat_log_appends`.

**One group** (`PlayerLineage`, or the initialization):
- Resolve `sensory_rows` once for the group. Its indices are valid only inside that group.
- Walk the nodes in order. Before each node, enter every `BodyRecord` whose `occurrence` ≤ the node's occurrence
  (bodies after the last node are entered at the end). At the node's occurrence, fold its `WorldUpdate` (if any),
  then its `fact` (unless `canceled`).
- A `SpatialFact` that enters or leaves (`ENTITY_ENTERED`/`ENTITY_LEFT`) is folded only if no nested commit
  supersedes it (`spatial_commits.commit_current`). This is unchanged from 15.
- Overlapping roots arrive as **one** group in native order: nested roots are parentless lineages inside it (vector
  `groups/g1`). A node's parent lineage is the group node that lists it in `children_lineages`, else its own
  `parent_lineage`. `lineage_branch` gives a root's branch.
- A spell application without its cast in the group is an error (`check_spell_declarations`).

### 2.4 World update (`fold_world_update`), one per occurrence

**Static stores.** They are sent once per seat, never pruned, and an id never changes value (an id naming another
value is an error):

| Store | Key | Arrives in |
| --- | --- | --- |
| tile looks (`surface`, `name`) | `look_id` | `WorldUpdate.tile_looks` |
| tile statics (`position`, `tile_uuid`, `look`) | cell (latest wins: a replaced tile brings a new row) | `tile_statics` |
| residue materials (`name`, `description`, `max_amount`) | `residue_id` | `residue_materials` |
| object looks (`ObjectLook`), for floor objects and contained items | item uuid | `object_looks` |
| boundary structures | `structure_id` | `boundary_structures` |
| visual loadouts (`active_weapon_set`, `layers`) | `visual_loadout_id` | `BodyRecord.loadout` |
| spatial-effect content (`content_ref`, `name`, `description`) | effect uuid | `SensoryFact.spatial_effect_content` |
| body birth; item look and profile | actor or item uuid | the first `BodyRecord` / `ItemRecord` |

The reference fold overwrites `spatial_content` without the same-value check (verify against reduction.py if you
add one).

**Steps, in order:**

1. **Static rows** into the stores.
2. **Removals.**
   - Pop `objects_removed` (and their `object_members`): the seat saw the object go, or saw its support without it.
   - Pop `connectors_removed`.
   - Each must name something held.
3. **Entered cells (`entered`) are authoritative.** For each entered cell:
   - Drop the held tile, unless the cell is in `tiles_unchanged`. Then install `tile_columns`, which cover exactly
     the entered cells not in `tiles_unchanged`.
   - Drop every held object whose support cells touch the cell (`placement_support_cells`; a boundary object also
     touches the opposite incident cell), unless the object is in `objects` or in `objects_unchanged`.
   - Remove the cell from the `construction_suppressions` positions of every object still held.
   - Drop every connector with an endpoint there.

   These are errors: a `tiles_unchanged` cell that is not entered or not held; an `objects_unchanged` object that is
   not held.
4. **Object rows, in row order.**
   - The look must be held. The placement is the row's, else the held one (one of them must exist).
   - Item = look ⊕ state, with the boundary structure taken from its store by id.
   - Residues: the row is authoritative for its `observed_faces`. Held residues keep their faces outside them, merged
     by `condition_uuid`. Drop empty residues and sort by `condition_uuid` as a string.
   - Suppressions: the row's providers replace the held rows of those providers, and the other held rows follow.
   - `contained_items` stays as held.
   - `object_members[uuid]` = the row's `members`. Absent means 1, and is legal only for a one-observer seat.
5. **Contents.**
   - `contents` sets a held container's whole contents, sorted by uuid string. Looks come through `object_looks`.
   - `contents_changed` removes, then upserts, by uuid. Its container's contents must be held.
6. **Tile rows.**
   - `tile_changes` (scalars), then `resolved_light`. These name only cells held before and after, never an entered cell.
   - `tile_conditions` replaces a tile's own names.
   - `residues`: a row with `condition_uuid` is whole and replaces what is held. Without it, the row is keyed: `amount`
     when present, and `contributions` set by index, where index = length appends.
   - Then `residues_removed`.
   - These also fill the tiles of entered cells built in step 3, which start with no conditions and no residues.
   - Finally, `condition_names` = own names + residue material names, by `residue_id` order.
   - A keyed row on a tile that is not held is an error.
7. **Connector upserts** (whole rows), by uuid.

**`tile_columns`.**
- There is one byte per cell per column, in cell order: `walking_cost`, `flying_cost`, `swimming_cost`,
  `burrowing_cost`, `default_light`, `resolved_light`, and `flags`.
- `flags`: bit 0 `blocks_optics`; bit 1 `blocks_propagation`; bits 2-3 surface kind (0 ordinary, 1 stairs, 2 ramp);
  bits 4-5 slope axis (0 none, 1 north-south, 2 east-west).
- `elevation_steps` is a signed list. Absent means all 0.
- A tile = its cell's static row (`tile_uuid`) + that row's look (`surface`, `name`) + the column values.

**`ObjectColumns`** (row *i* = `item_uuids[i]`):
- `name` and `map_char` are dense.
- Every other field is a `Column {rows?: RowBits over the update's rows (absent: every row), values}`, left out when no
  row holds a non-default value.
- A skipped row holds the default: `null`/`[]`, `stack_count` 1, `is_pickable` true, `blocks_propagation` false,
  `integrity` intact, no `members`, no `observed_faces`.
- `visual_item_name` absent means it equals `name`.
- `placements {rows?, position[], top_height_steps[], …}`: `position` and `top_height_steps` are dense over the placed
  rows; every other placement field is a `Column` over the placed rows.
- Decode a placement:
  - `object_uuid` = the row's uuid;
  - `kind` = `boundary` iff `boundary_direction` is present, else `center`;
  - `tile_uuid` absent = the static tile row at `position` (an error if none is held);
  - `covered_supports` absent = the single anchor support;
  - `occupies_bands` true; `base_height_steps` 0; `orientation` null; `removed_bands` `[]`.
- `construction_geometry` is state, not look: a cut wall changes it.

### 2.5 Composed sensory fact (`fold_composed_sensory`), one per settlement

The seat's node at a settlement's first member event carries the whole seat's change. The cells are the composed
view: the client cannot tell which cells each member sees, only which contacts and effects it perceives.

**Group rows (`SensoryRows`).** Every identity a row or removed list names is in `uuids` once. The tables:

| Table | Row *i* |
| --- | --- |
| contacts | `uuids[contact_uuid_index[i]]` at `contact_positions[i]`, `visual` iff *i* ∈ `contact_visual`, `contact_special_senses[i]` (column absent: `[]`), members `contact_members[i]` |
| sightings (entering effects) | `uuids[sighting_uuid_index[i]]` as `sightings[i]`, members `sighting_members[i]` |
| effect patches | `uuids[patch_uuid_index[i]]` changed by `sighting_patches[i]` |
| retired cells | `uuids[retired_uuid_index[i]]` left `retired_cells[i]` (a member saw it go) |
| light sources (entering) | `light_sources[i]` (`LightRow`; `source`, `anchor_entity`, `anchor_item` index `uuids`) |
| light patches | `light_patches[i]` (`source`, `changes`; an anchor index, or null when it became undisclosed) |
| cells | `cells` (mask order) |
| light levels, hazards | layered `CellValues`: rows by cell in cell order, then by layer (the k-th layer holds each cell's (k+1)-th smallest value) |

A one-observer seat leaves out both member columns: every row is that observer's. A multi-observer seat without them
is an error.

**Fold, in the reference order:**
1. **Entry.** `initial` creates the perception from `observer_position`, `passive_perception`, `visual_access` and
   `sense_modes`, with empty cells. It happens once. Any later fact needs the entered perception.
2. **Cells.**
   - visible := visible − `visible_cells_removed` + `visible_cells_added` (both `RowBits` over `cells`).
   - Light and hazard: overwrite with `effective_light_levels_changed` / `hazardous_cells_changed`, which are `RowBits`
     over their tables. Keep values only at visible cells. A newly visible cell without a value is 0.
   - **seen := seen ∪ visible added.**
3. **Contacts**, entities then objects.
   - `*_removed` (indices into `uuids`): delete the contact and its members.
   - `*_changed` (contact row indices): set the contact whole and its members. A row whose members alone changed is
     sent again.
4. **Content:** merge `spatial_effect_content`.
5. **Effects.**
   - `spatial_effects_removed` (uuids): pop the effect and its members, and remember all its cells.
   - `spatial_effects_patched`: apply the patch.
     - `positions_added`/`_removed` and `volume_added`/`_removed` are `CellMask`s. A patch removes only held cells and
       adds only new ones.
     - `upper_added` / `upper_removed` are keyed by `(position, lower_height_planes)`.
     - `changes` hold after-values (null means it became unset).
     - `members` is present only when it changed.
     - Remember the removed cells.
   - `spatial_effects_added`: the content must be held. Set the sighting (cells unpacked in cell order) and its members.
   - Then update the memory (§3) with `spatial_effect_cells_retired`.
6. **Lights.**
   - `light_sources_removed` (uuids): pop.
   - `light_sources_patched`: set the changed fields.
   - `light_sources_added`: the source enters whole.
   - Lights carry **no members**.
7. **Scalars.**
   - `observer_position` when present.
   - `sense_modes`, `passive_perception` and `visual_access` only when their `*_changed` flag is set.
   - `paths_dirty` is sticky: the fold ORs it in and never clears it.
8. **Bodies.**
   - `observer_position` sets the stream observer's body `last_visual_position`.
   - Each changed entity contact with `visual` places its held, present body at the contact's position.
   - Then clear ghost bodies (§3).

These are errors: a list naming one identity twice; removing or patching a record not held; adding one that is held.

An effect's `duration` goes only to its owner. A non-owner's tick sends nothing.

### 2.6 Bodies, change rows, items

**`BodyRecord`** (a body entering the composed view, `enter_body`):
- If the held body has `present` false, ignore the record.
- `birth` is present only the first time; a first record without it is an error.
- Replace **every** `BodyState` field. Absent fields mean: no grant, no conditions, not controlled (`controlled_items`),
  no occupancy layer, no size, no faction, remains intact, present.
- Keep `last_visual_position`: contacts set it.
- `loadout` is the value of `body.visual_loadout_id` the first time; afterwards take the value from the store.
- Enter `items` (below). Each item the body shows (`controlled_items`, else its loadout layers) with no record here
  has its effects cleared.
- A re-entering body whose value equals what the seat holds is **not sent at all** (digest stamps). Keep it as held.

**`ActorChangeFact`:** enter `items` first, then each actor's rows in order. An actor the client does not hold is an
error. A body with `present` false ignores its rows.

| `field` | Fold |
| --- | --- |
| `normal_hp`, `maximum_hp`, `temporary_hp`, `armor_class`, `resolved_size`, `spatial_disposition` | replace with `value` |
| `temporary_hp_grant` | replace (null: none) |
| `active_weapon_set` | replace the loadout's weapon set |
| `condition` | with `member`: upsert by `condition_uuid` (in place if held, else appended). Without it: remove (`consumed` says how it ended; removing an absent one does nothing) |
| `condition_duration` | replace the held member's `state.duration`. Nothing if it is not held |
| `layer` | with `layer`: upsert by `slot`. Without it: remove the slot (re-wearing a slot = remove then set, so it moves last) |
| `inventory` | `held`: append to `controlled_items` if absent; else remove. An error without `controlled_items` |
| `item_effects` | replace that item record's `effects` |
| `item_effect_duration` | replace that effect's `duration` |
| `item_state` | replace those fields of that item record's `state` |

An item row for an item, effect or `state` the client lacks does nothing. Durations travel only to the controller.
Layer and weapon-set rows change the body's own loadout value, never the store entry.

**`ItemRecord`** (the item record is `{look, profile?, state?, effects}`, never pruned):
- `look` and `profile` are kept from the first time; a first record without a look is an error.
- `state` replaces when present.
- `effects` replace (absent: none).

**Other record facts** (unchanged from 15):
- `faction` sets the faction.
- `spatial`:
  - a terminal departure sets `present=false`, `last_visual_position=null`, `occupancy_layer=null`, and ends the
    entity's contact for every member;
  - `ENTITY_ENTERED` sets the disposition to present, and a controlled body takes the fact's position (the stream
    observer's own entry also sets the perception's position);
  - an `occupancy_layer` present sets it.
- `item_charge` (the controller only):
  - `item_destroyed` drops the item from the inventory and the loadout layers; its record stays;
  - otherwise it sets `charges` and `stack_count`.
- `attack` sets the weapon set.
- `damage` (stage `applied`) and `heal` (not blocked) set normal and temporary HP. The grant is kept only while
  temporary HP > 0.
- `temporary_hit_points` sets temporary HP and the fact's grant.
- `life` sets the life state, normal HP and remains.
- `turn` sets `round_number` when present. `turn_start` sets `current_actor_uuid`, and `turn_end` /
  `encounter_end` clear it. Other `event_type` values (including the new `actor_sheet` and
  `initiative_order_changed`) change nothing else; verify against reduction.py.

### 2.7 HUD and initiative (`apply_hud`, `displayed_initiative`)

- A sheet the client does not hold arrives whole (every `SheetChanges` field, no `resource_values`) and is appended.
  At initialization the sheets come in display order.
- For a held sheet, the present `changes` replace their fields. Then each `resource_values` row
  `{key, current, maximum}` replaces those values of the held `resources` row with that key. A key that is not held is
  an error.
- `resources` is whole only when its key sequence changes.
- Name, portrait and HP are the body's: `actors[actor_uuid].name`, `.appearance.portrait_key`, `.normal_hp`,
  `.maximum_hp`.
- `initiative` replaces the held order when present. The first HUD must carry it.
- **Display** the held order filtered to the controlled actors plus the composed entity contacts now. Leaving
  perception sends nothing; the filter hides it.

### 2.8 Combat log

- Q8 changed only how the server builds the log: each entry is rendered once per distinct disclosure and shared by
  the seats. Wire and text are identical to 15.
- `PlayerNode.combat_log` holds a node's entry. Its children are composed from `children_lineages`: a child lineage
  without its own entry contributes its children's entries. `target_entry_indices` index those children.
- `PlayerUpdate.combat_log_appends` are appended in order. Each must match the seat's `generation` and
  `observer_uuid`, have `operation_end_cursor` ≤ `reducer_cursor`, and have `encounter_log_index` equal to the count
  already held.

---

### 2.9 Addendum: free-aim targeting in Choices (position spells)

Not a 15 → 16 change: it landed earlier (PD1b and the free-aim lane). A schema-9 client has never seen it.

**Which rows.** A Choices row whose `target_type` is `position`, `position_los` or `position_aoe` carries a
`position_region` (`PositionRegion`). Examples: Wall of Fire, Freezing Sphere, Forcecage, Delayed Blast Fireball,
Conjure Elemental, Planar Ally, Summon Dragon, Create or Destroy Water, Call Lightning.

**The row lists no cells.** Discovery no longer enumerates every legal cell; enumerating the whole region cost
most of Choices for zone spells. The row's target set is often **empty**. That does not mean unavailable:
read `availability_status`, never infer availability from an empty target list.

**Two ways to aim:**

| Way | When | Selection to send |
|---|---|---|
| A listed target | AoE rows also list one aim point per perceived creature, each with its hit set | `target_indices=[i]`, as for any row |
| Free aim | Any point inside the region, including any row with an empty target list | `target_indices=[]`, `extra_target_positions=[aim, ...]`: the first position is the aim, the rest are the row's further positions if it needs any |

The worker rejects a free aim with no position as `invalid_selection` (server/worker.py `retained_selection`).

**`PositionRegion` fields** (dnd/core/base_actions.py `PositionRegion`). Use them to highlight and pre-filter
cells for the player. The server is the authority:

| Field | Meaning |
|---|---|
| `range_feet` | Maximum distance from the caster; `null` means the action states no range limit |
| `candidate_source` | `visible`: cells the actor sees; `reachable`: cells it can reach |
| `requires_unoccupied` | The cell must look unoccupied to the actor |
| `requires_walkable` | The cell must look walkable to the actor |
| `requires_axis_or_diagonal_alignment` | Straight or diagonal line from the caster only |
| `exclude_source_position` | The caster's own cell is not allowed |

**Flow.**
1. Choices: the player picks the row.
2. The player clicks a cell; filter it locally with the region fields.
3. Preview with the free-aim selection. The server validates that exact point with the same per-point legality
   rule execution uses (`valid_positions_among` / `in_visible_region`) and returns the preview footprint.
   Show `can_confirm` and the footprint.
4. Command (`ExecuteSelectionIntent`) with the same selection. Execution validates the aim again.

Verify against the worker: the exact preview payload for an illegal aim (an error string, or `can_confirm=false`).

## 3. Memory rules (what the client keeps)

| Rule | Detail |
| --- | --- |
| Leaving view sends nothing | Tiles, objects, contents, connectors, bodies and items stay as last held |
| Entered cells reset | Only what the update carries or confirms (`tiles_unchanged`, `objects_unchanged`) stays there |
| Unchanged re-entry | A record off the entered cells (a contact regained, a body re-entering) whose value is unchanged is not sent. The client must still hold it, so never evict on your own |
| Object forgotten | When its support is seen without it (entered cell or `objects_removed`) |
| Wall faces | Unseen faces keep their last residues; a face cleaned in view goes |
| Suppressions | Cells retire where they enter view; a perceived provider's row replaces its own |
| Contents | Kept when the seat stops seeing in; whole again when it sees in again |
| Seen cells | Every cell ever visible |
| Effects | Cells leaving an effect's visible part are remembered with its last-perceived row (volume and upper surfaces dropped). So is the whole effect when it leaves perception. A remembered cell is forgotten when it is perceived again, when retired (a member that held the effect saw it go), or, for an `apparent_presence` effect, when the cell is seen without it. A concealed effect's cell seen by a member that never found it stays (vectors `sensory/v4`–`v6`) |
| Ghost bodies | After every sensory fact: a body that is present, not dead, not controlled by the seat, not an entity contact now, and whose `last_visual_position` is a visible cell loses that position. Its other values stay (`clear_unseen_positions`, vector `bodies/v4`) |
| Departed bodies | `present` false: later records and rows are ignored |
| Items | Never pruned; a destroyed item's record stays |
| Member bits as of the last row | `object_members` changes only with an object row (an unchanged or unsent object keeps its bits). Contact members change with each contact row; effect members with each sighting row and with `patch.members` when sent. Bits go with their record's removal. Lights have none |
| Static stores | Never pruned |

What to draw from memory (stale tiles, closed containers' contents, suppressions of unperceived providers) is the
client's display policy.

## 4. Rendering obligations

- **Member bits.** Bit *i* is `PlayerInitialization.audience.observers[i]`. A seat without an audience has one
  observer, the stream observer.
  - Contacts, objects and effects whose bits are a strict subset of the members must be shown as perceived by those
    members only ("seen by A only"), named by their bodies.
  - The bits say nothing about cells: cells are composed.
- **Targets come only from Choices**, never from perception. Every rule (targeting, advantage, stealth, reactions)
  uses each creature's own senses.
  - A contact seen only by A must never be offered for B. B's Choices already leave it out.
  - Build every target, position and preview from the Choices/Preview bindings (`subjects`, `positions`,
    `target_sets`), not from contacts, effects or member bits.
- Never infer anything from "whole" versus "unchanged": a digest equal to the held value is the only reason a record
  is confirmed.

## 5. Content and catalog changes

**Multiattack is one public action `action.monster.multiattack`.**
- Its ref is unchanged (`content.srd_5_1_cc`, action, v1, contract hash `b348fe0a…`). It went from internal
  "Multiattack Runtime" to public "Multiattack", with icon key `ui.filter-attacks`.
- `ActionFact.behavior_id` is `action.monster.multiattack`.
- Each creature's steps live in its recipe. The menu label comes from the engine, e.g. "Multiattack: 2 × Scimitar,
  1 × Dagger": show what Choices sends.

60 per-creature ids are retired, as `action.monster.multiattack.<suffix>`:
- **18 were on the integration line:** `bandit_captain.melee`, `bandit_captain.ranged`, `brown_bear`, `cult_fanatic`,
  `dretch`, `fellwing_devil`, `goblin_briarling`, `goblin_gloomplate`, `huntsman_wing_devil`, `knight`,
  `polar_bear`, `scout.longbow`, `scout.shortsword`, `spy`, `stegosaurus`, `thug`, `veteran.melee`, `veteran.ranged`.
- **42 existed only on the NPC lane** (NDClient's snapshot has them):
  - barbarians: `barbarian_cinderplate`, `barbarian_farshot`, `barbarian_red_rage`, `barbarian_saffron_ward`,
    `barbarian_venom_ritualist`, `barbarian_windmark`;
  - devils: `blade_marshal_devil`, `bow_harrier_devil`, `bulwark_devil`, `contract_cutter_devil`,
    `debt_collector_devil`, `gate_guard_devil`, `gate_tyrant_devil`, `glaive_warden_devil`, `ivory_marksman_devil`,
    `night_archer_devil`, `oath_captain_devil`, `oathblade_devil`, `tollbreaker_devil`, `twinhaft_mote_devil`,
    `wardblade_devil`, `wing_regent_devil`;
  - characters: `character_blue_spark`, `character_briarline`, `character_gilded_ward`,
    `character_violet_oathbreaker`, `character_white_streak`, `character_whiteplate`;
  - enemies: `enemy_arcane_sentinel`, `enemy_bellringer`, `enemy_blue_twinblade`, `enemy_bronze_watch`,
    `enemy_dockwall`, `enemy_gateplate`, `enemy_gold_knuckle`, `enemy_reliquary`;
  - `orc_mudrunner`;
  - undead: `undead_ash_crown`, `undead_black_fletch`, `undead_bonewheel`, `undead_flareblade`, `undead_pikeward`.

NDClient references to change (decide the exact shape on the client side):
- `authoring/catalog/body_action_recipes.json` has 10 recipes keyed by retired ids, whose `definitionRef.content_id`
  names retired content: `bandit_captain.melee`, `bandit_captain.ranged`, `cult_fanatic`, `knight`, `scout.longbow`,
  `scout.shortsword`, `spy`, `thug`, `veteran.melee`, `veteran.ranged`.
- `authoring/catalog/body_action_bindings.json` maps `action.monster.multiattack` → `source_recipe:
  action.monster.multiattack.knight`. `presentation/authoring.gd` resolves the ActionFact's `behavior_id` through this
  binding, so Multiattack plays the knight recipe today, and deleting that recipe breaks it.
  - One minimal fix: re-key the knight recipe as `action.monster.multiattack`, with the public declaration's
    `definitionRef`. Then drop the binding and the other nine recipes.
- Regenerate `authoring/server_ids.json` (`tools/snapshot_server_ids.py`) against this engine. Against head it differs
  only by the 60 retired ids, plus its header (schema 16 and the new digest).
- Regenerate or re-record the other files naming retired ids: `generated/studio_*` and
  `tests/fixtures/player/initialization.json`.
- Icons: the public declaration's `icon_key` is `ui.filter-attacks`, and `authoring/ui/resources.json` already has
  `icon:ui.filter-attacks`. Its `icon:action.monster.multiattack` row names the live id, not a retired one; check
  which key NDClient resolves.

**`encounter_end` removal trigger.**
- `ConditionRemovalTrigger` gains `encounter_end`. It travels in `ConditionMember.state.removal_triggers`.
- Today only `condition.attack_assistance` (from Help Attack) carries it. When the encounter ends, the engine removes
  such conditions, and the seat sees an ordinary `condition` removal row.
- Accept the value in any trigger enum or badge mapping.

**New catalog entries** (all public, against the integration line before the NPC merge; NDClient's snapshot already
lists them):
- 123 creatures: 28 fiends (`*_devil`, `*_imp`), 41 humanoids (`barbarian_*`, `character_*`, `enemy_*`, `orc_*`),
  8 `undead_*`, 46 zombies (`zombie_hd_*`, `zombie_top_*`).
- `action.help_attack` (a standard action on every creature) and `action.monster.shield_bash` (it replaces one of
  three Multiattack attacks). NDClient has no recipe or binding for either.
- `condition.attack_assistance` and `condition.consumable.weapon_coat.assassin_poison`.
- `reaction.class_feature.fighter.protection`.
- `trait.assassinate`, `trait.evasion`, `trait.spell_damage_resistance`.

Player-visible rules that came with them: Assassinate works on the assassin's first turn only; Brute adds one die of
the held weapon; Leadership is hear-only.

## 6. How to verify

1. **Identity.**
   - Copy `sdk/protocol/player-api-v1.schema.json` and `protocol-identity.json` into NDClient's `sdk/`.
   - Check each record's `protocol` against `{1, 16, 26c80694…99532}`.
   - The digest is the SHA-256 of the schema JSON re-serialized with sorted keys and separators `(",", ":")`
     (Python `json.dumps`, ASCII-escaped: `server/protocol.py:protocol_identity`). It is checked on the exported file.
2. **Golden vectors** (`sdk/protocol/fold-vectors/`). On the engine they pass with
   `pytest tests/player/test_{world,client,body,group}_fold_vectors.py` (41 passed at c66ea3de5). A file is
   `{name, rule, observers, [controlled], steps: [{<input>, expected}]}` (`groups/`: `initial`, `group`, `expected`).
   Fold the inputs from an empty seat whose audience is `observers`, and compare `expected` after each step.

   | Folder | Input per step | Expected shape defined by |
   | --- | --- | --- |
   | `world/w1`–`w14` | `update` (`WorldUpdate`) | `tests/player/test_world_fold_vectors.py:client_world_view` |
   | `sensory/v1`–`v8` | `sensory_rows` + `fact` | `tests/player/test_client_fold_vectors.py:client_sensory_view` |
   | `bodies/v1`–`v9` | `body` (`BodyRecord`), `change` (`ActorChangeFact`), `spatial` (`SpatialFact`), or `seen` | `tests/player/test_body_fold_vectors.py:body_view`, `item_view` |
   | `groups/g1` | `initial` (`WorldUpdate`), then `group` (`PlayerLineage`) | `test_group_fold_vectors.py`: held objects and the root branch's occurrences |

   A body vector's `seen` step is a test shortcut, not a wire record: set the composed view to its `visible` cells and
   `contacts`, run the ghost clearing, then place each visual contact's body.
   The vectors also pin the errors: a multi-observer seat without member columns, keyed rows on what is not held,
   re-entering what is held (see each test file's error tests).
3. **Replay a recorded spool.**
   - Record a seeded oracle run:
     `PYTHONHASHSEED=0 PYTHONPATH=<tree> python devtools/performance/gallery_transcript.py record <tree> <out.json> --case fireball --mode ordinary --name <stem> --seats faction --oracle <dir>`.
   - The reference replay is
     `PYTHONHASHSEED=1 PYTHONPATH=<tree>:<tree>/sdk/python/src python devtools/performance/spool_replay.py <dir>`.
   - Each seat's spool `<dir>/<sha256(seat)>.frames` holds frames of a 4-byte big-endian length plus the exact JSON:
     frame 0 is the initialization record, then the operations.
   - Fold the frames in Godot and diff each record's state against the reference fold of the same frames
     (`reduce_initialization` / `reduce_operation`; `seat_oracle.state_data` dumps `PlayerState` as JSON).
   - No Godot-side comparer exists; match the field names against `PlayerState` in reduction.py.

## 7. Reconnect

- **Journal replay is the protocol.** Attach, `GET /initialization` (record 0), then `GET /events?after=0`. The spool
  prefix is the backfill. Fold everything from an **empty** state.
  - A dropped stream on the same attachment (same `acquisition_id`) resumes with `after=<last consumed sequence>`.
  - A new attachment can only start at 0 (`/events` refuses `after` beyond what that attachment was sent).
  - A client that persists its own exact fold may resume after its cursor on the same attachment only.
- **Never start from partial memory.** `tiles_unchanged`, `objects_unchanged` and unsent unchanged bodies name records
  the client must already hold. A client that skipped records will raise on them.
- **The digest stamps need nothing from the client.**
  - They are per-seat server knowledge, kept with the seat.
  - When restored, they are rebuilt from the seat's own spool by the reference fold (`dnd/player/stamp_replay.py`;
    exercised by `spool_replay.py`). Without stamps, every re-entry is simply whole.
  - On the server side, body stamps have no restore function today, so a body re-enters whole. Either way the client
    does nothing.
- A server restart ends the game today (no save/load). A new game epoch is a new journal.

## 8. Not shipped yet

- **Q5/Q9 shared vision:** one **side part** per faction (perception, world, bodies and facts, numbered per side,
  identical for every player of the side), plus a **per-player overlay** (HUD, Choices, its own characters'
  controller-only details).
  - It was decided in principle and is not built. It is a future wire change, and this handout will need an update.
  - Still open: whether teammates see each other's controller-only details.
  - Today each seat gets its own composed view. The member-bit rendering of §4 is already required for multi-observer
    seats, and shared vision will reuse it.
- Not decided: whether a settlement that only sets `paths_dirty` will stop sending a fact.
