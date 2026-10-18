# World family under the no-memory rule (read-only rescan, 2026-10-18)

Repository: `/home/tommaso/.codex/worktrees/event-native-deltas/dnd_engine`, branch `event-native-deltas` (`55bf034cc`).
Nothing was run or measured. Every byte figure is an estimate from field sizes and
`agent_docs/event_native_deltas_2026-10-18/byte_census.txt`.

## The rule, applied to the world

For each occurrence *o*, and for each world record (tile cell, object, contents, connector):

- **Perceived before and after *o*:** send the event's own change, keyed.
- **Entering perception at *o*:** send its current state in full, read from the objective fold as of *o*.
  - "Entering" means a cell entering the seat's composed view, an object entering observation, a
    container's contents entering the grant, or a connector getting both endpoints in view.
  - It makes no difference whether the seat saw the record an hour ago.
- **Leaving perception:** send nothing. What the client shows out of view is its own business.

Per-seat server knowledge:
- what is perceived now: the composed view, the observed objects, the granted containers;
- which static content ids were already sent.

There are no copies of client values, no last-seen stamps and no object memory for unseen cells.

### Where this departs from the previous study (`agent_docs/event_native_deltas_2026-10-18/world.md`)

| Previous proposal | Under the new rule |
|---|---|
| §4.6 #2 fallback: a per-cell/object change stamp plus a per-seat last-visible stamp (D1(b)) | **Forbidden** (last-seen stamps). |
| `objects_removed` "on re-entry of last-known cells (from the index)", which keeps `remembered_positions` / `remembered_order` (§1b, §3, §4.2) | **Deleted.** That is object memory for unseen cells. The client's wholesale replacement of entered cells does the job (§4 below). |
| `tile_static` "on entering view while the cell's `tile_uuid` differs from its init row" (§4.2, §4.6 #6) | Keyed by **static ids sent**: a static row is sent iff its `tile_uuid` was never sent to the seat. |
| `connectors_left: (connector_uuid)` | **Nothing** on leaving. |
| `contents_cleared: (container)` when the grant is lost | **Nothing**. The client sees the chest's `is_open` change, or the contact change, and applies its own policy. |
| N3 "`default_light` is not recorded" | **Mostly wrong.** The live path records it (§3, N3). No native change needed. |
| The entering-cell snapshot as "fields where current differs from the authored baseline" | Allowed only if the baseline is objective. Simpler and truer to the rule: send every dynamic field over the entered mask as packed columns (§1.3). |

---

## 1. Per payload kind: what it becomes, and what is deleted

### 1.1 The per-payload rule

**Tiles**

| Payload (today) | Perceived before and after: event's change | Entering: full current state | Leaving |
|---|---|---|---|
| `tiles` (whole `WorldTileState`, facts.py:1104; sent on first sight or on a `tile_uuid` change, projection.py:1183-1185) | Only on replacement while visible (a new `tile_uuid`): the new static row plus the dynamic fields | A **static row** `(tile_uuid, position, surface, name)` iff that `tile_uuid` was never sent to this seat | nothing |
| `tile_changes.surface`, `.name` | Never change in place: `set_tile` always builds a new `Tile`, so a new uuid (gridmap.py:1162-1179) | part of the static row | — |
| `.walking/flying/swimming/burrowing_cost`, `.blocks_optics`, `.blocks_propagation` | Keyed `(cell, field → after)`, from:<br>• TILE_CHANGED partials (events.py:3715-3756; set at gridmap.py:1146-1157);<br>• terrain rows (N2);<br>• `WorldModifiedEvent` fields where `before != after` (events.py:803-809), computed from the event alone | the current value, as a packed byte column over the entered mask E | nothing |
| `.elevation_steps`, `.surface_kind`, `.slope_axis` | `TileElevationChangeEvent.new_*` (events.py:4311-4329) | packed column over E | nothing |
| `.default_light` | `WorldModifiedEvent` before/after (world_authoring.py:750-787) | packed column over E | nothing |
| `.condition_names` (the tile's conditions followed by its residue names, base_tiles.py:371) | **Tile conditions:** keyed `(cell, name)` add or remove, from `ConditionFact.name` with `resulting_tile` (types/actor_facts.py:18-33, capture.py:769-781).<br>**Residue names** leave the wire: they are residue static content. | the cell's current tile-condition names (the fold's `condition_names` minus the names of the residues present) | nothing |
| `.residues` (whole field per deposit; Fireball's biggest world item) | Keyed rows, recorded by the writer (N1):<br>• `(cell, residue_id, amount_after)`;<br>• `(cell, residue_id, contribution_index, contribution_after)`;<br>• `(cell, residue_id)` removed | the cell's complete current residue rows | nothing |
| `resolved_light` (packed, projection.py:1190-1191) | `light_level_map` ∩ visible (events.py:3759; gridmap.py:5893-5905, 5256-5262), plus TILE_CHANGED `new_light_level` | the current level, packed over E | nothing |

**Objects, contents, connectors**

| Payload (today) | Perceived before and after: event's change | Entering: full current state | Leaving |
|---|---|---|---|
| `objects` (whole `PlayerObject`, facts.py:1083-1088, when `!=` remembered, projection.py:1214-1215) | **The record's after-value from the event**, keyed by `item_uuid`: its mutable state, plus its placement if the event moved it. Sources:<br>• `SpatialChangeEvent.object_state` / `placement` (gridmap.py:3650-3652);<br>• `ItemLocationStateEvent.item_state` + `world_placement`;<br>• `ConditionFact.resulting_item`;<br>• `ItemResourceChangeEvent` charges.<br>The changed objects are only the event's explicit subjects (`world_event_objects`, world_facts.py:118-142) plus their containers, remnants and constructions. Objects that merely sit on touched cells are not resent. | **look** (if this `item_uuid`'s look was never sent) + **placement** + **state**, after the stateless transforms (visible faces, `_disclosed_object`, `_public_object`, the remnant filter) | nothing when the seat's perception changed (a sensory event) |
| `FloorItem` static fields (`item_id`, `visual_*`, `contact_passage`, `supported_by_uuid`, `door_mechanism/swing`, `maximum_hit_points`, `construction_owner_uuid/geometry`, `known_to_creator`, `concentration_capacity`, light radii) | — | the look, once per `item_uuid` (the actor family already does this with `ItemLook`, facts.py:209-222) | — |
| `FloorItem.surface_residues` | Inside the state row, faces ∩ visible faces, plus `observed_faces`, the faces whose support cell is visible | the same | nothing; keeping unseen faces is client policy |
| `construction_suppressions` | Positions ∩ visible, and only while the provider is perceived | the same | nothing; geometry retention moves to the client |
| `contained_items` | While granted: keyed add/remove from `ItemLocationStateEvent(INVENTORY, owner=container)` and `ItemHoldingsReleasedEvent` (world_facts.py:268-289); child state upserts by uuid | **On gaining the grant** (open or destroyed ∧ visual contact, projection.py:1069-1073): the whole contents, which replace the client's | nothing (no `None` clearing) |
| `objects_removed` (remembered positions ∩ visible, projection.py:1210-1213) | A key removal when a **non-sensory** event takes an observed object out of perception: destroyed, OBJECT_REMOVED, moved off the floor, moved into unseen cells, hidden | — | nothing |
| `connectors` (the whole visible set, re-sent in every update and read **from the init event only**, projection.py:1224-1227) | An upsert or removal from `WorldModifiedEvent(connector_uuid, after)` while both endpoints are visible (world_facts.py:263-267; written through world_authoring.py, e.g. 503) | the full `WorldConnectorState` when both endpoints are visible after *o* and at least one is in E | nothing |

**`PlayerWorld` and initialization**

- **`PlayerWorld`** (facts.py:1113-1119): static, sent once. Unchanged.
- **`PlayerInitialization.world_updates`**: the same rules over the startup walk (projection.py:2179-2208).
  - Every initially visible cell is in E.
  - The static-id sets start empty, so init bytes are about today's whole first-sight rows.

### 1.2 Deleted per-seat structures and code

**The projector's copy of the client world**
- `ProjectionState.remembered` as a world copy (projection.py:1911): its `.tiles/.objects/.connectors` (facts.py:1185-1187). The client's `PlayerState` keeps them.
- `apply_world_update(remembered, update)` (projection.py:1237).

**The tile diff**
- `_tile_changes` (projection.py:1137-1167).
- The tile diff loop in `_world_update` (1179-1191).

**`WorldProjectionIndex` memory and caches** (projection.py:1103-1114)
- `remembered_positions`, `remembered_order`, `next_order` (1108-1110): object memory for unseen cells.
- `_remember_object` (1117-1134), and its use at 1232-1236.
- The candidates taken from remembered positions (1194-1195).
- The removal order (1213).
- `observed_values` (1114) and `_observed_plain_or_object` (1079-1101): a value cache.

**`_observed_object`'s merges with remembered values** (1022-1076)
- Face-residue retention, unioning remembered faces (1035-1051).
- Suppression-row retention (1052-1065).
- `_observed_remnant(…, remembered.objects, …)` (1066-1067, 1562-1563): it becomes "looks sent ∪ observed".
- `destroyed_contacts` stops passing `remembered` (1402-1403).

**The rules judged against remembered values**
- Object removal (1210-1213).
- Change detection (1214-1215).
- Contents clearing on a lost grant (1216-1222).
- The connector gate `connectors == remembered.connectors` and the per-update connector tuple (1224-1227).
- The `_disclosed_object` rewrite of remembered (1634-1637).

**Readers outside projection.py**
- application.py:74: `known_connector_uuids` from `remembered.connectors`. Replace it with the connectors visible now, derived from the view and the fold; that keeps today's redaction semantics.
- application.py:89 and content_composition.py:107-111: content admission read from `state.objects`. Replace it with the content ids of the looks sent.
- devtools counters: movement_scaling.py:71-72, movement_profile_worker.py:304.

**`ProjectionState.world` per seat** (projection.py:1909; built at 2186)
- It holds no client values, but it is per-seat server state, and it is seat-skewed. The early `observed_changes` application (1452-1461) happens at *that seat's* observer's sensory reference.
- Deleting it needs one session fold, read "as of *o*". That means one of:
  - event-major projection: for each event, fold once, then project every seat. This inverts the seat loop of application.py:64-98 and the per-seat `_project_nodes` walk.
  - a fold that can be read at any version.
- The early-apply branch then becomes an objective "apply at commit version" (the previous study's N7).
- This is the one medium-to-large change. The rest is local.

**Kept per seat (world)**
- The composed view: `audience_composition` / `senses`.
- `world_index.observed`: the objects perceived now.
- New: `granted: set[UUID]`, the containers whose contents are perceived now.
- `knowledge_removed`: a one-step deferral for remnant dependents, not memory of client values.
- Static-id sets:
  - tile `tile_uuid`s, which can be a bit mask (see §5.9);
  - object looks (`item_uuid`);
  - residue materials (`residue_id`);
  - optionally content ids.

### 1.3 Proposed `WorldUpdate` shape (one per occurrence, as today)

- `entered: CellMask`: the seat-composed cells newly visible at *o*. The client replaces these cells wholesale.
- `tile_static`: `(tile_uuid, position, surface, name)` rows for tile uuids never sent to this seat.
  - Sent for E cells and for replacements while visible.
  - `TileSurface` (types/materials.py:32-40) could itself be interned as content.
- **Entering dynamic columns:** one byte column per field over E, in the mask's cell order (the `CellValues` convention, types/cells.py:34-39), sharing E's mask. Fields: the four costs, an optics/propagation flag byte, `elevation_steps` (needs a signed encoding), `surface_kind`, `slope_axis`, `default_light`, `resolved_light`.
- `tile_fields: tuple[TileFieldUpdate]`: the event's keyed field changes for cells visible before and after (the existing `WorldTileChanges` type minus `residues`/`condition_names`).
- `tile_conditions`: `(cell, name)`. Entering cells carry their full current list; visible cells carry keyed adds and removes.
- `residue_materials`: `(residue_id, name, description, max_amount)`, once per seat.
- `residues`: keyed rows (above), and the complete rows for E cells.
- `tiles_absent: CellMask`: tile removal (rare; authoring only, world_authoring.py:663-690).
- `object_looks`, `objects` (state rows with placement), `objects_removed`.
- `contents` (a whole set on grant gain), `contents_changed`, `contents_removed`.
- `connectors` (upserts), `connectors_removed` (only while visible).

---

## 2. Where "entering perception" comes from, and what is missing

**Cells: the composed view, never the member event**
- Today the walk takes candidates from the member event's `visible_cells_added` / `visible_cells_removed` (projection.py:1466-1469). Under a diff that is harmless (the diff drops cells already visible through another member).
- Without a diff, every cell a member gains that the seat already showed would be resent. So E must be the **composed** view's transition.
- It is computed inside `apply_current_audience` (audience.py:586-756), in `_fold_view_cells` (audience.py:364-408). Two cases:
  - **Box path:** `held[0]` (old `shown`) against `composed[0]` (new `shown`) at audience.py:396-402. Take `composed[0] & ~held[0]` **before** line 402: `held[0]` is a numpy view of `current.shown[part]` and is overwritten there.
  - **Restack path** (new member or initial, audience.py:376-377): only the whole window can be compared.
- **Missing.** The simplest general exposure: in `apply_current_audience`, keep `current.view.visible` before the `_fold_view_cells` call (audience.py:711). Then:
  - `entered = mask_difference(after, before)` and `left = mask_difference(before, after)` (dnd/core/cells.py:188);
  - return them through `fold_senses` (reduction.py:358-366) to the walk (projection.py:1474).
  - Dependencies stay a DAG: audience → reduction → projection.
- The hazards-only path (audience.py:388-394) never changes `shown`, so E is empty there.

**Objects**
- Entering = `_object_observed` after (projection.py:1001-1019, over the composed `senses.objects` built at audience.py:713-735, or a boundary support in view) ∧ not in `world_index.observed` before (projection.py:1204-1207). This exists today.
- The snapshot set must also hold every observed object touching E, even one already observed. The client drops held objects touching E (§4), and a boundary object straddling a visible cell and an entering cell must not be lost.
- So: snapshot = observed-after ∩ (entering ∪ objects touching E ∪ constructions whose suppression positions meet E ∪ remnants listing an entering attachment). "Touching" is the fold's `objects_by_position`, which includes the opposite incident support of a boundary (world_facts.py:60-94).
- Objects leaving, for maintaining `observed`: `world_objects_at(fold, left)` replaces today's member `visible_cells_removed` (projection.py:1468).

**Contents**
- The grant transition. **Missing:** a `granted` set (perception now). "Before" needs the contact before the sensory fold, but the fold mutates `remembered.senses` in place (projection.py:1474-1475).

**Connectors**
- Both endpoints in view after, and at least one in E. Nothing to store.
- **Missing:** reading `recorded_world.connectors` instead of `world.world.connectors` (the init event: projection.py:1224, latent bug 1), and an endpoint index or a scan (connectors are few).
- `world_event_positions` gives a connector `WorldModifiedEvent` no positions (world_facts.py:158-163), so connector edits need their own small path.

**The snapshot source**
- The fold as of *o*. Per seat today; one session fold if `ProjectionState.world` goes (§1.2).

---

## 3. Native writers: which must record their change in keyed form, and how small

| # | Writer | Today | Needed | Size |
|---|---|---|---|---|
| N1 | `deposit_residues` / `remove_residues` (residues.py:186-246, 261-286) | Complete `tile_states` through `publish_tiles_state_changed` / `commit_tile_mechanics` (gridmap.py:1956-1990), re-snapshotted at completion (gridmap.py:3637-3640) | **Yes.** The loop already knows, per cell, whether the residue is new, a contribution was appended, or contribution *k* was bumped (residues.py:203-232), and which cells were removed (269-275). | Add a `residue_changes` tuple and a material header to `SpatialChangeEvent` and pass it through the two gridmap calls; the header is `(residue_id, name, description, max_amount)`, from the `ResidueProfile`, so the projector never reads `_PROFILES` (residues.py:85). About 30-50 lines.<br>Row sizes:<br>• ash amount row: about 35 B;<br>• new blood contribution: about 110 B per ellipse plus about 90 B for `deposit_source`;<br>• bump: about 45 B;<br>• removal: about 30 B. |
| N2 | Terrain floors (area_conditions.py:1405-1407, 1447-1449) | Complete rows through `commit_tile_mechanics`; which field changed is not recorded | **Yes.** It only ever changes `walking_cost` (MIN modifier, 1380-1403). Emit `TileFieldUpdate(position, {"walking_cost": after})`. The residue-hazard calls to `commit_tile_mechanics` (residues.py:243, 283) change no field beyond N1's rows. | About 10-20 lines; about 30 B per cell. The deferred removal publication (1450-1452) carries the rows in the same fact. |
| N3 | `default_light` | Live edits go through `set_world_tile_base_light` (world_authoring.py:750-787), which wraps `set_tile_base_light` in a `WorldModifiedEvent` with whole before/after rows, so the fold learns it. The bare `set_tile_base_light` (gridmap.py:5238-5290) publishes LIGHT_CHANGED only if the resolved level changes (5255), but its direct callers are scenario builders that run before the `WorldInitializedEvent` snapshot (battlefield_catalog.py:922-970, 1443-1467; arena_layout.py:108; devtools movement_scaling_fixture.py:171). | **No native change.** Keep the invariant that post-init base light goes only through world_authoring. | 0 |
| — | Already keyed or derivable from the event alone | — | **None needed:**<br>• LIGHT_CHANGED `light_level_map`;<br>• TILE_CHANGED partials and `tile_state`;<br>• `TileElevationChangeEvent`;<br>• `WorldModifiedEvent` before/after (tile, object, connector);<br>• `ConditionFact` name and uuid (tile conditions, object residues);<br>• object after-values;<br>• removals;<br>• contents add/remove;<br>• `ItemResourceChangeEvent`. | — |
| (opt.) | `to_world_tile_state` (base_tiles.py:358-373) folds residue names into `condition_names` | — | No. The AI reads the composite (ai/runtime/world_projection.py:86). The projector strips residue names using the N1 header's names, which are held objectively in the fold. | — |

- **Objects need no writer change.** The state row is a record-level after-value the events already carry.
- Field-level object deltas would need every object writer to declare its fields. That is not worth it once the look and the placement are split out.
- **Residues without N1** could be diffed objectively (session fold before against the fact's `tile_states`; contributions compared by index). That is seat-independent, but "one path" says pick one, and the writer already holds the exact change.

---

## 4. Client consequences (reduction.py)

`apply_world_update` (reduction.py:132-145) becomes three ordered steps:

1. **Entered cells E, wholesale.** For each cell in E:
   - reset the tile to its static row (the client's static store, by the cell's `tile_uuid`; the new static row if one is sent);
   - set the dynamic fields from the columns;
   - replace the tile conditions and residues wholesale;
   - `tiles_absent` clears the cell;
   - **drop every held object whose held placement touches E** (placement positions plus boundary incident supports, defined exactly as world_facts.py:68-94);
   - drop every held connector with an endpoint in E.
2. **Snapshot rows.** Upsert looks into a static store that is never pruned. Upsert object state rows by uuid: an object the client held elsewhere moves. Contents snapshots replace the container's contents.
3. **Keyed event changes:** tile fields, conditions, residues, light, object state, `objects_removed`, contents add/remove, connector upserts and removals.
   - Ops are idempotent upserts or removes. Contributions are set by index, never appended. The early `observed_changes` application (projection.py:1452-1461) and a cell that enters and changes at one occurrence then cost bytes, not correctness.
   - The "patch for an unknown tile raises" check (reduction.py:138-140) stays as an invariant: keyed changes only arrive for cells visible before and after, which the client got on entry.

**Leaving.** Nothing arrives. The client knows what left from its own sensory fold (`visible_cells_removed`, contact removals). Keeping stale tiles, objects, silhouettes, contents and face residues, or dropping them, is client policy. A client that keeps them shows "last seen" fog. A wholesale entry corrects it.

**Faces and suppressions.** The state row carries `observed_faces`. The client replaces residue faces within `observed_faces` and keeps or drops others by policy. The same goes for suppression rows whose provider is not perceived.

**Contents.** `contained_items is None` no longer means "not observed". The client hides contents per policy when `is_open` turns false or the visual contact goes.

**Static stores** (tile static rows, object looks, residue materials):
- they must never be pruned, or the server's "sent" sets lie;
- reconnect replays the journal from the initialization, so they rebuild.

**Other client code**
- `stage_lineage` (reduction.py:200-215) must setdefault from static plus snapshot rows.
- `state_before_event` / `lineage_branch` (539-549, 607-637) are unchanged: they slice by occurrence.
- The client's `PlayerState.tiles` can stay `WorldTileState`: it rebuilds full rows from the static row and the columns.

**Order inside one occurrence.** The world update is applied before the node's fact (reduction.py:532-536). The world update carries `entered`, so the client needs neither its own composition nor a reorder. This also keeps the world independent of the server/client composition divergence (latent bug 5).

---

## 5. Correctness risks under the rule

1. **An object destroyed, removed or moved while unseen.** Nothing is sent at the time.
   - On any entry of a cell its held placement touches, the client drops it.
   - Its replacement or remnant (a new uuid) arrives as a snapshot. A moved object that is observed again is upserted by uuid (no duplicate).
   - Until then the client shows a stale silhouette: policy, accepted by the rule.
   - The risk is client and server disagreeing on "touches E". Both must use the same incident-support definition.
2. **Observed object lost through its own event vs through perception.**
   - A non-sensory event: destroyed, picked up, moved into an unseen cell, hidden. Send a key removal (the seat saw it go).
   - A sensory event: send nothing (leaving).
   - A source's change revealed through `observed_changes` counts as the source's event.
   - Getting this wrong either leaks nothing but leaves ghosts in visible cells, or deletes objects the client may keep.
3. **Container contents.**
   - Contents are only sent while granted (the disclosure gate is unchanged, projection.py:1069-1073). Changes while not granted are invisible, and the next grant replaces the contents wholesale.
   - Risk: the client keeps showing stale contents. Use policy, driven by `is_open` and the contact.
   - Risk: a contained item's state change while granted must be keyed by the child uuid. `world_event_objects` already adds the containing owner (world_facts.py:140-141).
4. **A door or connector changed while unseen.**
   - A door is an object: nothing is sent while unseen. On entry (either incident cell in E, or contact) its current `is_open` arrives.
   - If either incident support stays visible, the door counts as observed (projection.py:1013-1019), so its change is a keyed event change.
   - Connectors: nothing while unseen; the full row on entry; the client drops held connectors with an endpoint in E (this covers removal while unseen).
   - **The precondition is the fix for latent bug 1** (connectors read from the init event, projection.py:1224). Without it, post-init connector edits never reach any seat under either rule.
5. **Light on unseen cells.**
   - LIGHT_CHANGED on unseen cells sends nothing.
   - Light that makes cells visible arrives as a sensory event: those cells are in E and get their current objective light.
   - Light that hides cells means leaving: the client keeps its last light by policy.
   - Precondition: the fold's light is complete. The startup interval does not admit LIGHT_CHANGED or TILES_CHANGED (capture.py:257-305), so carried lights after the `WorldInitializedEvent` snapshot are stale in the fold. This is existing behavior, but entering snapshots are now the only correction path, so the fold must be right.
   - The objective `resolved_light` also duplicates the sensory subjective light for E (open question D5).
6. **Multi-observer seats.** E must be the composed transition (§2). Member masks would resend cells another member already shows.
7. **Snapshot timing.** It must read the fold as of *o*, never the live engine (which has moved past the operation), and never an end-of-operation fold: an object present at *o* and removed at *o2* would be lost to the animation. A per-seat fold gives this today. A session fold needs event-major projection.
8. **Disclosure transforms move into the snapshot path unchanged**, as stateless functions:
   - `_disclosed_object` (1642-1650) and `_public_object` (1692-1698);
   - the attachment grant (projection.py:1009-1012);
   - the remnant filter, now against "looks sent ∪ observed".
   - The last one slightly widens disclosure: a remnant may name an attachment whose look was sent but which the client has since dropped. That identity was already disclosed.
9. **Per-seat static sets and memory.**
   - A `tile_uuid` set grows with explored cells. It is still far smaller than today's whole `remembered.tiles` rows.
   - It can be a bit mask: tile uuids never move after init. The only position-moving `set_tile(tile=…)` is setup-time, with `fire_event=False` (arena_layout.py:137).
   - So "static row of the current tile at cell *c* sent" is one bit, cleared for every seat when a replacement event happens at *c*.
10. **The test oracle changes.** "Client == remembered" goes away. The replacement: at op end, the client fold restricted to the seat's composed view and observed objects equals a snapshot built from the fold by the same entering-snapshot functions. HOW_TO_TEST.md applies; no tests were written here.

---

## 6. Bytes against today (estimates, not measured)

**Unit costs (JSON plus base64)**

| Unit | Cost |
|---|---|
| Whole `WorldTileState` today | ≈ 380-430 B |
| Static row | ≈ 150 B (≈ 100 B with an interned surface) |
| Entering plain cell with packed columns (one byte per field per cell) | ≈ 13-15 B, plus the E mask (≈ 30-80 B per update) |
| Same cell sent as a whole row instead | ≈ 400 B |
| Residues on an entered cell | ash ≈ 35 B; blood ≈ 35 B plus ≈ 200-300 B per contribution |
| Tile-condition row | ≈ 30-80 B |
| Object: today's whole `PlayerObject` | ≈ 1.2-1.5 KB |
| Object look, once | ≈ 0.6-0.8 KB |
| Object state with today's placement | ≈ 0.45 KB (the placement alone ≈ 330 B, world_placement.py:57-72) |
| Object state with a compact placement that drops the uuids the client can derive (`object_uuid`, support `tile_uuid`s) | ≈ 0.18 KB |
| Connector row | ≈ 400 B |

**Per census case**

| Case | Today, world family | Under the rule | Why |
|---|---|---|---|
| fireball (316 KB, 2 updates) | ≈ 119 KB: residues 101.5, objects 13.2, light 2.3, condition_names 2.3 | **≈ 30 KB** | Keyed residues (≈ 51 → 10 KB per update, plus the superseded re-sends gone), names leave, looks split. No re-entry except cells revealed by destroyed objects. |
| sleet_storm (216 KB) | ≈ 25 KB: residues 19.9, objects 3.6, light 1.2 | **≈ 8 KB** | Sleet makes cells leave view, and leaving sends nothing. |
| spirit_guardians_walk (502 KB) | ≈ 38.5 KB: objects 25.0, tiles 9.9, light 3.6 | **≈ 15-30 KB** (uncertain) | First-sight tiles become static rows plus columns. Object rows shrink (look once), but every wall or torch touching an entered cell is resent at ≈ 0.18-0.45 KB. The count of re-entries per step is unknown: Lantern Gallery, 6 steps along y=7, gallery_crowd.py:900-901. |
| darkness_daylight (172 KB) | ≈ 2 KB: light 1.2, tiles 0.8 | **≈ 2-4 KB** | Daylight reveals ≈ 30-50 cells; their full state is ≈ 0.7 KB packed, plus the objects inside. |
| **New worst case: re-opening a door onto a room seen before** (10×10, 40 wall segments, 4 torches, 10 bloodied cells) | ≈ 0 when unchanged | **≈ 12-23 KB** (+≈ 38 KB if tiles go as whole rows) | "The full room is delta". Cost is dominated by wall placements. |

- **Net.** The rule removes the per-seat world copies and the diffs, and cuts the residue-heavy cases sharply.
- **What it costs:** re-entry. That is cheap for plain tiles if the entering columns are packed, and moderate for objects. The object cost is dominated by the placement encoding, not by the rule.
- **What decides the ≤ 100 KB gate:** the compact placement and the packed tile columns.
- **To measure:** run the census on the four cases plus a "walk out and back into a seen room" case before choosing the wire shape.

---

## 7. Anti-slop and anti-OOP check, and open questions for the human

**Checks**
- **Data, not classes.** Writers put keyed rows on events. The projection system reads one objective fold plus perception-now sets. `WorldUpdate` stays a passive record. Event dispatch is `match`, as in world_facts.py. No `getattr`, no type cheats, no late imports. The audience → reduction → projection DAG is unchanged.
- **One path.** The same rule for initialization, live play and reconnect. The diff path is deleted, not flagged off. There is no "remembered room" fallback.

**Open questions**
- **Q1.** Is an instance's immutable part a "static content id"? This covers a tile's `(tile_uuid, position, surface, name)` and an object's look per `item_uuid` (with precedent: `ItemLook` for actor items). Or must every entering cell and object restate it?
- **Q2.** Packed per-field columns over E for entering tiles (≈ 15 B per cell), or whole rows (≈ 400 B per cell)?
- **Q3.** Delete `ProjectionState.world` now? That needs event-major, all-seat projection and commit-version application (medium-to-large). The alternative is to keep the per-seat objective fold first: it holds no client values, but it breaks the rule's letter.
- **Q4.** Keep objective `resolved_light` on the wire next to the sensory light (D5)?
- **Q5.** Should connector-name redaction in the log use the connectors visible now (today's meaning, recommended) or every connector ever sent?
- **Q6.** Face-residue union and suppression retention: confirm they are client policy, with the server sending `observed_faces`.
