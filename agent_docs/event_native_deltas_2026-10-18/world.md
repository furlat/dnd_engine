# World payload family: event-native deltas, read-only design study

Repository: `/home/tommaso/.codex/worktrees/single-pass-propagation/dnd_engine`. The study started at
`ead1f2458`; the head moved to `094b528f7` while I read (a merge; inside this scope only
`dnd/core/gridmap.py` changed, by ±10 lines). All gridmap line numbers below were re-checked on `094b528f7`.
Nothing was run or measured. Every byte figure marked "estimate" is reasoning, not measurement.

Scope: `WorldUpdate` (tiles, `tile_changes` / `WorldTileChanges`, resolved_light, objects / `PlayerObject` /
`FloorItem` incl. surface_residues and contained_items, objects_removed, connectors), `PlayerWorld`, and the
world part of `PlayerInitialization`.

---

## 0. How the world wire is produced today

- **The projector holds two world copies per seat.**
  - `ProjectionState.world: PresentationTarget` is the objective recorded fold (`WorldFacts`). Each seat folds
    the same retained events into its own copy: projection.py:1909, created per seat in `begin_projection`
    (projection.py:2186), folded by `world_facts.apply_world_fact` (world_facts.py:224-384).
  - `ProjectionState.remembered: PlayerState` holds `.tiles`, `.objects` and `.connectors` (facts.py:1180-1186).
    This is the mirror of the client.
  - `WorldProjectionIndex` (projection.py:1104-1114) holds knowledge: `observed`, `remembered_positions`,
    `remembered_order` and `knowledge_removed`. It also holds one value cache, `observed_values`.
- **The walk** (`_project_nodes`, projection.py:1311). For each retained terminal event:
  - `world_event_footprints` gives the candidate cells (world_facts.py:206-221);
  - `apply_world_fact` folds the event into the private world (projection.py:1449-1450);
  - a `SensoryUpdateEvent` of an audience observer first applies its `observed_changes` source events early
    (projection.py:1451-1461), then adds `visible_cells_added` / `visible_cells_removed` as candidates
    (1466-1469), folds the senses (1474-1475) and calls `_world_update` (1477-1481).
- **`_world_update`** (projection.py:1170-1239):
  - **Tiles.** For every candidate cell visible now, it compares `remembered.tiles` with the fold's tile. A
    missing tile or a different `tile_uuid` sends the whole `WorldTileState`. Otherwise `_tile_changes`
    (1137-1167) compares 14 fields and sends each changed field with its whole value. A changed light goes to
    the packed `resolved_light`.
  - **Objects.** `_observed_object` (1022-1076) builds the observed value by merging the current object with
    the remembered one (face residues, suppressions). An object is sent whole when it is `!=` the remembered
    value.
  - **Connectors.** All currently visible connectors are re-sent in every emitted update.
  - **Fold.** It then folds its own update into `remembered` (`apply_world_update`, 1237).
- **Client fold** (`apply_world_update`, reduction.py:132-145): tiles replace; field patches merge, and a
  patch for an unknown tile raises; objects are removed, then upserted; connectors are replaced. It is applied
  per occurrence, before that occurrence's fact (reduction.py:521-537).

---

## 1. Per field: what is sent, how it is computed, the native source, the deciding knowledge, the risks

Shorthand:
- "diff" = compared against the per-seat `remembered` copy;
- "fold" = the per-seat objective `ProjectionState.world`;
- "vis" = `senses.visible`, the composed seat view from `AudienceComposition` (audience.py:431-458, folded
  in `_fold_view_cells`, audience.py:364-408).

### 1a. Tiles

| Field | (1) Sent now | (2) Computed | (3) Native keyed change at event arrival? | (4) Deciding knowledge | (5) Risks |
|---|---|---|---|---|---|
| `tiles` (whole `WorldTileState`) | Whole record on first sight, or when the remembered `tile_uuid` differs (projection.py:1183-1185) | diff (`remembered.tiles.get`) | Whole rows: `WorldInitializedEvent.tiles` (events.py:788-800), `WorldModifiedEvent.after` (803-886), `SpatialChangeEvent.tile_state` (TILE_CHANGED, 3720), `.tile_states` (TILES_CHANGED, 3723). Keyed by position. The authored baseline is the init row. | First sight = the seat's `seen` mask transition: `SensoryUpdateEvent.seen_cells_added` (events.py:3378), composed at audience.py:747-748. Replacement = current `tile_uuid` ≠ baseline `tile_uuid` (objective). | A replacement while the cell is hidden: with no per-seat copy the projector can't know which `tile_uuid` the client holds. Rule: resend the static row on every entry while the cell's `tile_uuid` differs from its init row (replacements are rare). |
| `tile_changes.surface`, `.name` | Field patch with the whole value | diff | Change only by replacement, i.e. the `tiles` row | as above | none beyond `tiles` |
| `.blocks_optics`, `.blocks_propagation`, `.walking/flying/swimming/burrowing_cost` | Field patch with the whole value | diff | **TILE_CHANGED:** yes, partial after-values `tile_*` (events.py:3712-3758; builder at gridmap.py:1146-1157). **TILES_CHANGED** from terrain floors (area_conditions.py:1405-1407, 1447-1449 → `commit_tile_mechanics`, gridmap.py:1968-1990): complete rows only, which field changed is not recorded. **Writer change, small:** `commit_tile_mechanics(…, fields=…)` emits `TileFieldUpdate` rows for the declared fields. | vis at the occurrence | Disclosure: send only for cells visible at the occurrence (today's rule). |
| `.elevation_steps`, `.surface_kind`, `.slope_axis` | Field patch | diff | **Yes:** `TileElevationChangeEvent.new_height_steps / new_surface_kind / new_slope_axis` (events.py:4311-4330; gridmap.py:1784; fold at world_facts.py:311-318) | vis | none |
| `.default_light` | Field patch, but in practice only through replacement | diff | **No.** `set_tile_base_light` (gridmap.py:5238-5290) publishes LIGHT_CHANGED with the resolved level only (5256-5262). No event records the new `default_light`, and the fold never learns it (world_facts.py:344-354). **Writer change, small:** record `default_light` on that fact, or drop the field from the wire. | vis | A latent gap today: the wire only carries default_light changes that come through replacement. |
| `.condition_names` | Whole tuple per change | diff | Composite (base_tiles.py:371): `(*active_conditions, *residue names)`. **Tile conditions:** yes, `ConditionFact.name / condition_uuid` with `resulting_tile` (types/actor_facts.py:18-33; built at capture.py:769-781; admitted for every seat, capture.py:270-272) is a keyed add/remove of one name. **Residue names:** no; they come from `Tile._residue_names` via the residue writer (base_tiles.py:382-387). | vis | Every residue deposit re-sends the whole `condition_names` too. Residue names belong to residue static content (per `residue_id`), not to the tile's condition list. |
| `.residues` (`tuple[TileResidueState]`, all materials, each with all `contributions`) | **Whole field per deposit occurrence.** Fireball: 50.7 KB of 196 KB, 29.4 KB of it superseded within the same update (caller's measurement). | diff | **No.** TILES_CHANGED carries complete rows (gridmap.py:1956-1966, 1968-1990), re-snapshotted at completion (`_spatial_world_after_values`, gridmap.py:3638-3640). The writer has the keyed change in hand: `deposit_residues` (residues.py:186-246) knows `(position, residue_id)`, the after-amount, and whether it appended a contribution or bumped matching contribution *k* (residues.py:212-232); `remove_residues` (261-286) knows `(position, residue_id)` removed. **Writer change, small:** pass these rows through `publish_tiles_state_changed` / `commit_tile_mechanics` onto the fact. Static per material (name, description, max_amount): `ResidueProfile`, registered in the module-level `_PROFILES` (residues.py:85). | vis at the occurrence; entering cells via the composed enter mask (§4.3) | **Ordering:** Fireball deposits ash over the area once (evocation.py:851 → residues.py:320-358), then blood per injury (body_responses.py:132), so per-occurrence keyed rows remove the superseded re-sends. **Idempotence:** upsert contributions by index, never append; the early `observed_changes` application (projection.py:1451-1461) can apply a source twice. **Disclosure:** cells ∩ vis. |
| `resolved_light` (packed `CellValues` per update) | Packed (cell, level) for known visible tiles whose light changed (projection.py:1190-1191) | diff (`previous.resolved_light != current.resolved_light`) | **Yes:** LIGHT_CHANGED `light_level_map` (events.py:3759; built at gridmap.py:5893-5905, single-cell at 5261) and TILE_CHANGED `new_light_level` (gridmap.py:3646-3648) | vis; entering cells take the fold's current level | The sensory fact already carries subjective light for entering cells (PV2). Whether the objective light must also stay on the wire is a question for the human. |

### 1b. Objects, contents, connectors, `PlayerWorld`, initialization

| Field | (1) Sent now | (2) Computed | (3) Native keyed change? | (4) Deciding knowledge | (5) Risks |
|---|---|---|---|---|---|
| `objects` (whole `PlayerObject`: placement + `FloorItem`'s ~35 fields + `contained_items`) | Whole record per object whose observed value `!=` the remembered one (projection.py:1214-1216), per occurrence | diff, plus the remembered merge in `_observed_object` (1035-1065), plus the value cache `observed_values` (1079-1101, 1114) | **Record-level after-values, keyed by `item_uuid`:**<br>• `SpatialChangeEvent.object_state` (complete `ItemPresentationState`, gridmap.py:3650-3652) with `placement` / `previous_placement`;<br>• `ItemLocationStateEvent.item_state` + `world_placement` (base_item.py:91-130, 442-460);<br>• `ConditionFact.resulting_item`;<br>• `ItemResourceChangeEvent` charges / stack (keyed fields; fold at world_facts.py:283-292).<br>**Field-level:** no. It would need many writers. A look/state component split needs no writer change. | Observed before = `world_index.observed` (projection.py:1107, 1204-1206). Observed after = `_object_observed` (1001-1019): the composed contacts `senses.objects` (audience.py:713-735) or a boundary support cell in vis. | Static and dynamic fields are mixed in one record. On re-entry with no copy, the whole state is re-sent: wall faces re-observed on every move. |
| `FloorItem` static fields (`item_id`, `name`, `visual_*`, `map_char`, `boundary_structure`, `contact_passage`, `supported_by_uuid`, light radii, `maximum_hit_points`, `door_mechanism` / `door_swing`, `construction_owner_uuid` / `geometry`, `known_to_creator`, `concentration_capacity`) | Inside every whole-object send | diff | Constant per `item_uuid` (destruction makes a new uuid: `replacement_item_uuid`, base_item.py:126-129) | A knowledge set "looks sent" (`set[UUID]`); it replaces membership tests on `remembered.objects` (projection.py:1067, 1563) | `name` or visual variant changes, if any writer changes them, would need a look re-send. Not verified. |
| `FloorItem.surface_residues` | Inside the whole object, filtered to visible faces and **merged with remembered faces** (1033-1051) | diff + retention | **Yes:** `ObjectResidueCondition` (residues.py:305-318, applied 358) → `ConditionFact(condition_uuid, resulting_item)`; the changed row is the `resulting_item.surface_residues` row with that `condition_uuid` | Face visibility = support cells in vis (1027-1032) | **Player-visible:** today the seat accumulates faces seen over time. With no copy it gets the currently visible faces only, unless the client itself keeps the union. Decision for the human. |
| `FloorItem.construction_suppressions` | Inside the object; positions ∩ vis; provider geometry is kept from remembered while the provider isn't perceived (1052-1065) | diff + retention | The item after-value; the provider's `PerceivedSpatialEffect` in senses | vis + `senses.spatial_effects` | The same retention issue (Forcecage / wall constructions); niche |
| `concentration_slots`, `item_effects` | Inside the object | Stateless transforms: `_disclosed_object` (1642-1650), `_public_object` (1692-1698, 1892-1893), plus a rewrite of `remembered` (1636-1637) | after-values | `LineageDisclosure`, `public_cursors` | Keep the transforms; drop the `remembered` rewrite |
| `contained_items` | Whole tuple inside the object; a lost grant re-sends the whole object with `None` (1217-1222) | diff (`previous.contained_items`) | **Yes:** `ItemLocationStateEvent(location=INVENTORY, owner_uuid=container)` adds one item; `ItemHoldingsReleasedEvent` removes one (world_facts.py:105-116, 268-282) | Grant = open or destroyed ∧ visual contact (projection.py:1069-1072); knowledge set "contents granted" | **Disclosure:** contents only while granted. Send the snapshot on gaining the grant and an explicit clear on losing it. |
| `objects_removed` | Keyed uuid list (1209-1213) | Remembered placement positions ∩ vis, object not observed; ordered by `remembered_order` | **Yes:** OBJECT_REMOVED (`object_uuid`), `ItemLocationStateEvent` to a non-FLOOR location (world_facts.py:270-286, 355-356) | Last-known positions = the knowledge index `remembered_positions` (1117-1134). This is knowledge, not a value copy. | Removal while hidden is learned on re-entry of the last-known cells. Needs the index, not `remembered.objects`. The progress log says the rule is per event, not once per group. |
| `connectors` | **The whole visible set in every emitted update** (1224-1226); the client replaces its set (reduction.py:145) | All init connectors with both endpoints in vis; the emit is gated by `== remembered.connectors` (1227) | Read from `world.world.connectors`, the **init event only**. Post-init `WorldModifiedEvent` connector rows are folded into `recorded_world.connectors` (world_facts.py:263-267) but never read: a latent gap. `TraversalConnectorChangeEvent` (events.py:4331) is neither admitted nor folded. | Both endpoints in vis; knowledge set "visible connectors" | Redundant bytes on maps with connectors. The known-connector set also feeds log redaction (application.py:74). |
| `PlayerWorld` | Once, in the initialization (facts.py:1113-1120) | From `WorldInitializedEvent` (projection.py:2181-2185) | Static | none | none; already static-once |
| `PlayerInitialization.world_updates` | The same walk over the startup interval (projection.py:2179-2208): no senses until the initial sensory facts, then entering snapshots | as above | The startup interval admits only some world families (capture.py:257-305): objects, `WorldModifiedEvent`, `TileElevationChangeEvent`, tile/item conditions, spatial effects. TILES_CHANGED and LIGHT_CHANGED are **not** admitted there. | Initial sensory folds | **Reconnect:** the journal is replayed from the initialization (server records), so a delta stream folded in order is enough. An entering snapshot reads the fold, so its correctness equals the fold's completeness at startup (existing behavior). |

---

## 2. Ordering inside one update, and whether the client animates per occurrence

- **One `WorldUpdate` per occurrence**, keyed by the public occurrence index (projection.py:1478-1481,
  1892-1893). The client applies it before that node's fact (reduction.py:521-537).
- **Intermediate-state consumers:** `state_before_event` (reduction.py:539-549) and `lineage_branch`
  (607-637) slice world updates by occurrence. Nothing in `dnd/`, `devtools/` or `server/` calls them.
  - `devtools/animation_review` reads states at lineage level: `before.tiles` for elevation (record.py:125,
    162, 169) and end-state residues (trace.py:87-89).
  - `game_obsolete/choreography.py` timed residue reveals from per-event world updates (469, 2594-2636).
    That code is obsolete and on an older schema.
  - There is no Godot code here, and the human said to ignore it.
- **Conclusion:** per-occurrence placement is a fold contract with no live per-occurrence animation consumer.
  Keep occurrence placement anyway. With keyed rows, the only repeats left are genuine sequential changes of
  the same key, so nothing needs coalescing. The progress log also says once-per-group is not exact for
  removals.
- **Early application.** A source's world after-values are applied at its first observed sensory reference
  (projection.py:1451-1461), before the source's COMPLETION, where the fold normally applies it. Any delta
  emitted at both points must be an idempotent keyed upsert, so the second application is a no-op.

---

## 3. What reads `remembered` world records besides the diff, and can they go?

| Reader | What it reads | Replacement |
|---|---|---|
| `_observed_object` face-residue retention (projection.py:1033-1051) | previous `surface_residues` | current visible faces; any union lives in the client (decision) |
| `_observed_object` suppressions (1052-1065) | previous suppression rows | the provider's current perception; client-side retention (decision) |
| `_observed_remnant(…, remembered.objects, …)` (1067, 1563) | membership only | knowledge set "looks sent" |
| `_observed_plain_or_object` (1089) | previous residues, to choose the slow path | deleted together with the value cache |
| removal rule (1209-1213) | remembered placement positions | `remembered_positions` index (already knowledge) |
| contents clearing (1217-1222) | `previous.contained_items is not None` | knowledge set "contents granted" |
| connectors gate (1227) | `remembered.connectors` | knowledge set "visible connectors" |
| `_disclosed_object` rewrite (1636-1637) | rewrites remembered | deleted |
| `application.py:74` | `known_connector_uuids` for log redaction | the connector knowledge set |
| `content_composition.admitted_content` (content_composition.py:99-110, called with `remembered` at application.py:89 when the catalog is replaced) | `item_id` / `behavior_id` of objects and contents | a known content-id set (item ids of the looks sent) |
| devtools counters: movement_scaling.py:71-72, movement_profile_worker.py:304 | sizes | the knowledge-set sizes |
| tests | No test reads `remembered.tiles/.objects/.connectors` directly; 8 player test files read `projection.remembered` | — |

- **Can it be deleted? Yes.**
  - `remembered.tiles` has no reader other than the diff and devtools counts.
  - `remembered.objects` is replaced by knowledge sets the projector already half-keeps: `observed`,
    `remembered_positions` / `remembered_order`, plus "looks sent" and "contents granted".
  - `remembered.connectors` is replaced by "visible connectors".
- **What stays.** The client `PlayerState` keeps its tiles, objects and connectors; `reduction.py` is the
  client fold. The projector's per-seat state then stops being a `PlayerState` for the world.
- **D16-C replica test.** For the world, it becomes: client fold within view == objective fold filtered by the
  seat's view. That is a history-free check.

---

## 4. Event-native delta design for the world family

### 4.1 Rules

1. **One objective world**, the recorded fold. It is seat-independent and should be held once per session,
   not once per seat. Entering-view snapshots read it as of the occurrence, never the live GridMap (the
   operation has already completed, so live state is later than the occurrence).
2. **Per-seat state is knowledge only:**
   - the composed view (visible, seen, contacts);
   - the observed objects, and each known object's last-known positions;
   - the object looks sent, and the containers whose contents are granted;
   - the visible connectors, and the residue materials whose static content was sent.

   No value copies.
3. For each occurrence *o* and each world collection:
   - **visible before and after** *o*, and the event at *o* changed it → send **the event's keyed change**;
   - **entering** the seat's view at *o* → send **the current state from the objective world**;
   - otherwise → **nothing** (disclosure is unchanged from today).
4. **Every op is a keyed upsert or remove.** Ops are idempotent and never append. Snapshot/delta overlap from
   the early `observed_changes` application, or from a cell entering and changing at one occurrence, is then
   harmless.
5. **Static content once per content id:**
   - tile static row once per cell (first seen, or replacement);
   - object look once per `item_uuid`;
   - residue material once per `residue_id`;
   - connector row on entering view.

### 4.2 Wire shape per collection (one `WorldUpdate` per occurrence)

**Tiles**
- `tile_static: tuple[WorldTileState]`. The authored or replacement row: identity plus baseline fields. It is
  sent:
  - on the seat's first sight of the cell (seen-mask transition);
  - when the cell is replaced while visible;
  - on entering view while the cell's `tile_uuid` differs from its init row.
- `entered: CellMask` (packed). The seat-composed cells newly visible at *o*. The client resets each one's
  mutable tile state to its static row; this update's rows then apply. This replaces "the server knows what
  the client still holds".
- `tile_fields: tuple[TileFieldUpdate]`, keyed (cell, field) → after-value:
  - for a visible cell: from the event (TILE_CHANGED partials, `TileElevationChangeEvent`, terrain
    `TileFieldUpdate` rows);
  - for an entering cell: the fields where the objective current row differs from the objective baseline row.
    That is a seat-independent comparison against authored state, never against a per-seat copy.
- `light: CellValues`. The event's `light_level_map` ∩ vis, plus the current level for entering cells.
- `tile_conditions_added: (cell, name)` / `tile_conditions_removed: (cell, name)`, from `ConditionFact` on a
  tile. On entering: the current tile conditions. Residue names leave this list.
- `residue_amounts: (cell, residue, amount)`, `residue_contributions: (cell, residue, index, ResidueContribution)`
  and `residues_removed: (cell, residue)`:
  - from the residue rows the writer records on the fact;
  - on entering: the cell's complete current residues, as rows;
  - `residue` names a material whose static content (name, description, max_amount) the seat received once.

**Objects**
- `object_looks: (item_uuid, static FloorItem part)`, once per `item_uuid`.
- `objects: (item_uuid, placement, mutable FloorItem part)`, a keyed upsert:
  - for an observed object changed at *o*: the event's after-value;
  - on entering observation: the objective current value;
  - after the stateless disclosure transforms (visible faces, visible suppression positions, disclosed slots,
    public cursors).
- `objects_removed: (item_uuid)`. From native removal while observed, or on re-entry of last-known cells
  (from the index).
- `contents: (container, FloorItem rows)` when the grant is gained; `contents_added` / `contents_removed`
  keyed while granted; `contents_cleared: (container)` when the grant is lost.

**Connectors**
- `connectors_entered: (WorldConnectorState)` and `connectors_left: (connector_uuid)`, plus an upsert on a
  `WorldModifiedEvent` connector change while visible.
- Read from the folded `recorded_world.connectors`, not from the init event.

**`PlayerWorld`**: unchanged.

**Initialization**: the same rules over the startup walk. Every first-sight cell gets `tile_static`; every
initially visible cell is `entered`.

### 4.3 The entering-view rule, exactly

- **Tiles.**
  - E(*o*) = composed `shown` after minus `shown` before at the seat's sensory fold. `_fold_view_cells`
    already holds both (`held` vs `composed`, audience.py:396-405), so exposing them is a small change.
  - The walk must use E(*o*), not the member event's `visible_cells_added` (projection.py:1466). For
    multi-observer seats the two differ.
- **Objects.** Entering = `_object_observed` after ∧ ¬`world_index.observed` before.
- **Contents.** The grant transition.
- **Connectors.** Both endpoints in view: after vs before.
- **Snapshot source.** The fold as of *o*.

### 4.4 Native changes needed

| # | Change | Where | Size |
|---|---|---|---|
| N1 | The residue writer records keyed rows `(position, residue_id, amount \| removed, contribution index, contribution)` on its TILES_CHANGED fact | residues.py:186-246, 261-286 → `publish_tiles_state_changed` / `commit_tile_mechanics` (gridmap.py:1956, 1968) → new `SpatialChangeEvent` field; `_spatial_world_after_values` (gridmap.py:3634-3640) leaves it | small |
| N2 | Terrain writers declare the changed field; GridMap emits `TileFieldUpdate` rows | area_conditions.py:1405-1407, 1447-1449; gridmap.py:1968-1990 | small |
| N3 | `default_light` recorded on its fact (or dropped from the wire) | gridmap.py:5238-5290; world_facts.py:344-354 | small |
| N4 | Residue static content per `residue_id`, through the existing content admission (content_composition.py:154-165), or a static row on the first fact | residues.py:42-49, 85 | small–medium |
| N5 | Composed enter/leave masks out of the view fold | audience.py:364-408, 586-756 | small |
| N6 | Connectors read from the fold (also fixes the init-only read) | projection.py:1224-1226 | small |
| N7 | One objective fold per session, applied at each fact's commit version (removes the per-seat early-apply branch). Optional for correctness; it removes N_seats duplicate folds. Overlaps P7. | projection.py:1449-1465, 1909, 2186; capture.py:384-405 | medium |
| — | **No native change** for: light (`light_level_map`), elevation, TILE_CHANGED partials, tile conditions (`ConditionFact`), object records (whole after-values by uuid), contents, removals | — | — |

**AI knowledge folds** (knowledge_reduction.py:30, 220, 247) and **world_facts** keep reading complete
`tile_states`. The keyed rows are added beside them. Dropping the complete rows instead, to save memory, needs
the fold to apply keyed rows and residue static content (for `condition_names`).

### 4.5 What it deletes

- `PlayerState.tiles/.objects/.connectors` inside the projector. `remembered` becomes knowledge for the world.
- `_tile_changes` (projection.py:1137-1167) and the tile diff loop (1179-1191).
- `apply_world_update(remembered, …)` (1237).
- `WorldProjectionIndex.observed_values` and `_observed_plain_or_object` (1079-1101, 1114).
- The remembered merges in `_observed_object` (1033-1065), and the `_disclosed_object` rewrite of
  `remembered` (1636-1637).
- The `connectors == remembered.connectors` gate and the per-update connector tuple.
- Residue names in the wire `condition_names`.
- The superseded whole-field `residues` re-sends.
- The per-cell pydantic equality in `_world_update`. The progress log names `_world_update` as the dominant
  publication cost on drops and light changes (ENGINE_SINGLE_PASS_PROGRESS_2026-10-17.md:434).

Expected Fireball effect (estimate, not measured):
- the 29.4 KB of superseded residue re-sends disappear;
- ash rows become (cell, material, amount);
- blood re-sends only the new contribution;
- description, max_amount and the residue name leave the per-cell rows.

### 4.6 Open risks and decisions for the human

1. **Fog memory (player-visible).** Today the client shows remembered residues, wall-face residues, objects and
   silhouettes in explored, out-of-view cells, and the server corrects them by diff on re-entry. With no
   server copy:
   - on re-entry, the `entered` mask resets the cell's mutable state, and current values follow;
   - whether the client keeps showing stale out-of-view values meanwhile is the client's choice;
   - the face-residue union and the retained suppression rows move to the client or are dropped.
2. **Re-entry bytes.** A cell that differs from baseline (blood, terrain) re-sends its overlay on every entry,
   and re-observed walls re-send their object state. Today those cost 0 if unchanged.
   - Fallback without value copies: an objective last-change stamp per cell/object component, plus a
     per-seat last-visible stamp (knowledge). Send only components changed since last seen. This requires
     that the client keeps its stale values.
   - Measure against the ≤100 KB gate before choosing.
3. **Idempotence.** Contributions must be keyed by index. A non-idempotent append breaks under the early
   `observed_changes` application (projection.py:1451-1461).
4. **Multi-observer seats.** Entering must use the composed mask (N5), not member masks.
5. **Disclosure.** Event rows are filtered to cells and objects visible at the occurrence. The existing gates
   stay:
   - attachments observed only by their own grant (`supported_by_uuid`, projection.py:1009-1012);
   - remnant `intact_supported_items` filtered by known looks;
   - contents only while granted.
6. **Tile replacement while hidden.** The static row is re-sent on each entry while the cell's `tile_uuid`
   differs from its init row.
7. **Initialization completeness.** The startup interval doesn't admit TILES_CHANGED or LIGHT_CHANGED
   (capture.py:257-305), so baseline correctness relies on the init rows (existing behavior).
8. **Memory.** Keyed rows added beside complete `tile_states` grow retained events (the 8.8 GB / 47 min issue
   in the progress log), unless the complete rows are replaced (see §4.4).
9. **Objective `resolved_light` vs sensory light.** Is it still needed on the wire?
10. **Latent gaps found:**
    - connectors are read from the init event only;
    - `default_light` changes are not recorded;
    - residue profiles live in a module-level registry (residues.py:85).

### 4.7 Anti-slop and anti-OOP check

- **Data and systems, not classes.** Writers record data on events. The projection system holds knowledge sets
  and reads one objective fold. No new behavior classes, no `getattr` / `isinstance` dispatch (event `match`
  stays as in world_facts.py), no fallbacks.
- **One path.** The rule is the same for initialization, live updates and reconnect.
- **Only real deletions.** Nothing is kept "for compatibility": the diff path is removed, not flagged off.
