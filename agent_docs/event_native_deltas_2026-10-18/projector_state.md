# Per-seat publication state and its lifecycle under event-native deltas (read-only study)

Tree: `/home/tommaso/.codex/worktrees/single-pass-propagation/dnd_engine`. The head moved from ead1f2458 to 094b528f7 (the PV1a-2 fan-out merge) while I was reading. Nothing in scope changed: `git diff ead1f2458 HEAD` is empty for `dnd/player`, `server`, `dnd/core/sensory_fold.py`, `dnd/world_facts.py` and the replica test. Code citations are at 094b528f7. Plan line numbers are also at 094b528f7; §6b moved by +15 lines.

Plan context:

- P7 / D16-C (plan :835, :883) took the second mirror fold off the live path. The one fold that remains is `ProjectionState.remembered`, the server's copy of what the client holds. Capture and bookkeeping read it.
- PV3 (plan :699–705) makes every observation "a patch against `ProjectionState.remembered`".
- The D16-C replica test (`tests/player/test_emitted_update_replica.py:72-99`) asserts that the client's fold of the updates equals `remembered`, field by field, on exactly the fields the mirror holds (`what_capture_reads`: actors, items, spatial_content, connectors, content, hud_snapshot, tiles, objects; :67-69).

Below, **MIRROR** means a per-seat copy of client-visible values. **KNOWLEDGE** means identities, cells, cursors or revisions that the seat knows. **OBJECTIVE COPY** means a per-seat fold of seat-independent state.

---

## 1. Inventory

### 1A. `AudienceRuntime` (dnd/player/application.py:17-26)

It holds three things per seat:

- `projection: ProjectionState`;
- `capture: CaptureCheckpoint`, one object shared by every seat (built at :36-37, checked at :61-62);
- `content_catalog`, also one shared object.

It is the worker's per-seat handle (`server/worker.py:38-43`, `:85`, `:196`).

### 1B. `ProjectionState` (dnd/player/projection.py:1898-1928)

| Field | Holds | Writers | Readers | Class | Growth |
|---|---|---|---|---|---|
| `world: PresentationTarget` (actor_facts.py:14-41) | `WorldFacts` (world_facts.py:31-45): the whole map's tiles, all objects, connectors, 6 membership indexes; `senses` (aliased to `remembered.senses`, projection.py:1475); door/torch fields; an `actors` dict that projection never writes (apply_world_fact's holdings branch runs on an empty dict) | `apply_world_fact` in `_project_nodes` (projection.py:1452-1475 → capture.py:384-404 → world_facts.py:224-384) | `_world_update` (1170-1238), `_object_observed` (1001), `_observed_object` (1022), `_project_fact`, destroyed-contact capture (1398-1403) | **OBJECTIVE COPY** per seat. World after-values are not redacted per audience (`_retained_body`, capture.py:656-737), so N seats fold the same world N times | O(map + objects), flat. Values are shared by reference; the dicts and index sets are per seat |
| `actors: dict[UUID, ActorState]` | objective actor fold (births, actor facts, owned-item updates) plus the seat's admissions with a seat-specific `last_visual_position` | `_project_nodes` 1410-1438 | `_project_fact`, `_gear_observation`, faction `control_lost` (1527-1541), `_held_content_at_event` | **OBJECTIVE COPY**, duplicating `CaptureCheckpoint.actors` (capture.py:172) apart from the admission positions | O(actors ever) |
| `remembered: PlayerState` | see 1C | | | **MIRROR** | |
| `disclosed_lineages: set[int]` | native keys of the lineages disclosed to the seat | 1594, 1806 | `LineageDisclosure` (1266-1277), `lineage()` (1819-1821) | **KNOWLEDGE**, monotone | O(disclosed lineages) |
| `version_cursors: dict[UUID,int]` | native cursor of **every** captured version (all versions of every root graph) | `_remember_versions` 1260-1263 (called at 2194, 2220) | `NativeKeys` (1242-1257), 2228, 2245 | KNOWLEDGE-shaped, but a **duplicate of the engine index** `EventQueue._event_indexes_by_uuid` (events.py:1323, :2427) | **O(all versions), never pruned** |
| `lineage_keys: dict[UUID,int]` | lineage → its first version's cursor | same | same | duplicate of `EventQueue._events_by_lineage` (events.py:1317) | O(all lineages) |
| `public_versions: dict[UUID,int]` | version uuid → the seat's occurrence index | 1811-1812 | 1815-1816, `_public_condition` 1865, `_public_changes` 1889 | KNOWLEDGE, but **redundant**: it always equals `public_cursors[version_cursors[u]]` | O(disclosed versions) |
| `public_cursors: dict[int,int]` | native cursor → the seat's occurrence index | 1813 | `version()` 1822-1823; `project_after_values.boundary` reverse scan (2150-2155); `_public_set` 2174; 2245 | **KNOWLEDGE** (the seat's dense numbering of disclosed versions) | O(disclosed versions) |
| `public_lineages: dict[int,int]` | native lineage key → the seat's lineage index | 1815 | 1817, 1883-1885 | KNOWLEDGE | O(disclosed lineages) |
| `disclosed_turns: set[UUID]` | turn executions the seat may name | 1826-1827 | 1886 | KNOWLEDGE | O(turns) |
| `owned_spatial_effects: set[UUID]` | effects whose source the seat controls | 2197, 2217 | 1748-1749 (whether duration is shown) | KNOWLEDGE. It could also be computed per event from `controls(source)` | O(owned effects ever) |
| `spatial_values: dict[(observer, effect), Sighting]` | each member's last sighting, without its revision | 1731, 1779 | 1725, 1754 (change detection) | **MIRROR** | O(live member × effect) |
| `spatial_versions: dict[(effect, native_rev), seat_rev]` | native → seat revision of a sighting | 1727-1730 | 1771, 1841 | KNOWLEDGE (renumbering that hides unseen changes) | O(effect revisions ever), never pruned |
| `spatial_revisions: dict[effect, int]` | the seat's per-effect revision counter | 1729 | 1728, 1755 | KNOWLEDGE | O(effects ever) |
| `next_occurrence`, `next_log_append` | counters | | | KNOWLEDGE | O(1) |
| `world_index` | see 1D | | | | |
| `audience_composition` | see 1E | | | | |

### 1C. `PlayerState` as `remembered` (dnd/player/facts.py:1180-1208)

The server mutates it with the client's own reducer (`dnd/player/reduction.py`).

| Field | Writer (server) | Reader (server) | Class | Growth |
|---|---|---|---|---|
| `tiles` | `apply_world_update` (reduction.py:132-145) called from `_world_update` 1237. A `tile_changes` row makes a per-seat `model_copy` (reduction.py:140), so a changed tile is no longer shared | `_world_update` 1181-1193 (`previous is current`, `_tile_changes` diff) | **MIRROR** (tile memory) | O(tiles ever seen) ≤ map |
| `objects` | `apply_world_update`; `_disclosed_object` rewrite 1636-1638 | `_observed_object` 1035 and 1053 (wall-face residues and construction suppressions are **merged** with the remembered value); removal and change at 1210-1222; remnant filtering 1562 | **MIRROR** (object memory, including out-of-view silhouettes) | O(objects remembered) |
| `connectors` | `apply_world_update` 145 | 1227; application.py:74 | **MIRROR** | tiny |
| `senses`, `perception` | `fold_senses` (reduction.py:358-366), aliasing `audience_composition.view` / `.perception` | everywhere | **KNOWLEDGE** | see 1E |
| `spatial_commit_cursors` | `commit_current` (reduction.py:466-479) via 1521 | same | KNOWLEDGE (per-entity commit cursor) | O(movers) |
| `actors` | `observe_body` (`_emit_bodies` 2058); `apply_record_fact` 2082 | patch bases 2051-2054 and 2063; the held member value for known removals 2074; `known` 1343; `held_conditions` 1346-1349; names and known-set for capture (application.py:67, :72); `admitted_content` (content_composition.py:103) | **MIRROR** | O(actors ever known); never deleted (terminal → `present=False`) |
| `items` | `apply_item_patches` (reduction.py:157-169); deleted on a destroyed charge (reduction.py:399) | `_item_patches` 1931-1934; `admitted_content` | **MIRROR** | O(items ever seen) |
| `spatial_content` | `apply_record_fact` (reduction.py:411) | 2071, 1759 | **MIRROR** | O(effects ever seen), never pruned |
| `hud_snapshot` | `apply_hud` 2170 | 2167-2169 | **MIRROR** (the last HUD; blue's whole HUD is 91,468 B on the wire, plan §6b) | bounded |
| `content` | application.py:47, 89-95 | application.py:68-69 | MIRROR as stored; KNOWLEDGE in use (only identity keys are read) | ≤ catalog |
| `current_actor_uuid`, `round_number` | TurnFact | — | trivial | O(1) |
| `combat_log_appends` | never on the server (only `reduce_operation`, reduction.py:681) | — | client-only | — |

### 1D. `WorldProjectionIndex` (projection.py:1103-1114)

- `observed` (W 1205-1206): KNOWLEDGE. The objects the seat currently holds an observation grant for.
- `remembered_positions` / `remembered_order` / `next_order` (`_remember_object` 1117-1134): KNOWLEDGE. Where the seat remembers each object, and a stable removal order. This is exactly what the removal rule needs, with no values.
- `knowledge_removed`: transient between two world updates (1201-1203, 1236).
- `observed_values` (1095-1099): a memo of the last computed `PlayerObject` per plain object, keyed by the identity of the recorded value. Mirror-adjacent, and deleted with the mirror.

### 1E. Perception: `AudiencePerception` (audience.py:67-73), `AudienceComposition` (audience.py:430-457), `SensesSnapshot` (types/senses.py:211-232)

`perception.members` holds, per member observer, the folded `SensesSnapshot`:

- packed visible / seen / light / hazard masks (frozen values);
- contact dicts, advanced in place (sensory_fold.py:57-70);
- sightings, light sources, `light_source_removals`.

These are the observers' published perception, folded once per seat from their `SensoryUpdateEvent`s. **KNOWLEDGE.** This is the per-seat state the human says to keep.

Unpruned growth inside it:

- `contact_cursors` and `effect_cursors` (audience.py:665-667) are never popped: O(observers × identities ever).
- `effect_absences` (668-671) keeps the cells of every effect that disappeared: O(cells of effects ever).
- `light_source_removals` (sensory_fold.py:67) keeps one entry per removed source.

`AudienceComposition`:

- its member layers and shown arrays live over a window that only grows (≤ map);
- its membership indexes and `contact_holders` are bounded by current state.

All of it is derived: the cold composition rebuilds it from `members` (`begin_audience_composition`, audience.py:477), which is the replica test's third assertion.

### 1F. `CaptureCheckpoint` (capture.py:158-176): one per session, shared by all seats

It folds once per version (`advance_capture`, capture.py:784-855):

- `actors`: the objective actor fold;
- `contacts`: per tracked observer;
- `positions`;
- `root_of`, `trees` and `pending` evidence of open roots, pruned when a root completes (850-854). Actors are pruned on terminal release (843-849).

It is OBJECTIVE, plus the observers' contacts, and is not per seat. It is the natural owner of a shared objective fold (§6). `CaptureContext` (914-928) is per operation and transient.

### 1G. Server and host, per seat

- `Runtime.publications` (worker.py:38-43, 205-223): a cursor, a revision and a boundary. Tiny.
- The recording spool (server/recording.py:17-27) is the **journal**. The bytes are on disk; memory holds `offsets: list[(pos, len)]`, O(ops).

### 1H. Transient per walk (not retained)

- `SensoryTable` (projection.py:297-323);
- `DeclarationSenses` copies of the contact dicts per delivery lineage (1404-1408);
- `members`, `records`, `destroyed_contacts`, `content_at_event` in `_project_nodes`.

---

## 2. Initialization and reconnect

### Today

1. `initialize_audiences` (application.py:29-50) runs once at Start (`server/worker.py:85`).
   - It builds one `CaptureCheckpoint` and one `capture_context(..., end_cursor=now)`, which folds versions 0..now once.
   - Per seat:
     - `capture_interval(start=0, end=now)` (capture.py:308-381) retains the admitted startup events and derives admissions;
     - `begin_projection` (projection.py:2179-2208) runs **the same walk as every later lineage**: `_project_nodes` → `_public_occurrences` → `_shared_rows` → `_emit_bodies`;
     - `project_after_values` adds the HUD;
     - startup content is admitted from a server-side run of the client reducer on the initialization (`reduce_initialization`, application.py:47).

   So initialization already is "the first group of deltas from cursor 0". It is not a separate snapshot path.
2. The worker writes `InitializationResponse` as spool record 0 (worker.py:96-101). Every operation is one numbered record (worker.py:196-224).
3. The client:
   - `GET /initialization` streams record 0 (server/app.py:181-188);
   - `GET /events?after=n` streams records n+1… from the spool file (app.py:228-283);
   - a missing record gives `ErrorResumeUnavailable`;
   - it folds with `reduce_initialization` / `reduce_operation` (reduction.py:552, 654). Each operation runs a cold `begin_audience_composition` before folding sensory facts (reduction.py:672-673).
4. **Reconnect is journal replay.** The client resumes after a cursor it holds, or refetches 0 and replays. The server computes nothing and keeps no snapshot. P7 says the same: "Reconnect and recording work from the journal" (plan :835). A seat cannot join mid-game: seats are fixed at Start (worker.py:79-80).
5. A second consumer of the same projector: `project_sequence` (dnd/player/recorded.py:109-124) projects saved native recordings **with no engine** ("no native queries", projection.py:2180).

### What an event-native design needs here

- **Initialization stays one path.** It is the delta stream over startup, folded against empty knowledge, so no snapshot code exists. Startup memory is empty: anything seen during setup is folded in order, as now.
- **Reconnect stays journal replay.** The journal is exact, on disk, and needs no server state. Nothing changes.
- **A real snapshot** (mid-game join, or a lost journal) at cursor c, read from engine state plus the seat's knowledge:
  - *Perceived now:* exact. For every identity or cell in the composed view (members' senses), read the current value from the shared objective fold or engine. Use the **same production functions** that build first-sight bodies: `_public_actor` (189), `_item_records` (171), `_observed_object` (1022), visible tiles. Add the HUD of the controlled actors and the causal rows those values reference.
  - *Remembered, out of view:* **not reproducible from current state.** Using current values would leak changes made out of sight (fog of war). There are two exact sources:
    - (a) the journal;
    - (b) the event store, if knowledge stores per (identity, family) the **cursor of the event whose after-value was last disclosed**. The snapshot then reads that event's after-value. This needs (i) families whose value is carried whole by one event (HP, life, faction, an item's state, an object's recorded value) and per-membership cursors for set-valued families (conditions, residue faces); (ii) the memory refactor pinning the referenced events if it ever prunes the store.

  Rule: don't build (b) unless the human wants late join. Otherwise keep journal replay and keep `ErrorResumeUnavailable`.

---

## 3. Determinism, idempotence and the oracle that replaces the mirror

**Today:**

- the D16-C replica test: client fold == `remembered` on `what_capture_reads`, plus client senses == a cold composition (test_emitted_update_replica.py:82-99);
- `test_application_review.py:77-93`: `after_values(client) == after_values(remembered)`;
- the PV2 / PW gate: "folded client state strictly equal per op and seat on 10 cases" against base commits (progress :515, :369). This is a differential oracle and needs no mirror.

The first two depend on the mirror. 28 sites in 8 test files and 3 devtools read `projection.remembered`.

**Replacement oracle:**

- **O1, perceived part (each op end, each seat).** `restrict(client_fold(init..op), perceived) == snapshot_perceived(seat)`, computed from engine and shared-fold state.
  - "Perceived" covers: the composed view (cold composition of the members, already a leg); actors with a visual contact or control (`_public_actor`); their items; observed objects; visible tiles with light and hazard; sighted effects; the controlled HUD.
  - `snapshot_perceived` is the same production code that builds first-sight bodies, not a second projector kept for tests. It checks *stream ⟹ state*, with no projector state involved.
- **O2, memory part.** The harness carries forward its own O1 snapshots: for each remembered identity the client holds and no longer perceives, value == the harness's value at the last op end where it was perceived. Values are absolute after-values, so this is well-defined.
  - Limit: perception that lasts only inside one op is invisible at op granularity. A group-close hook, or O3, covers it.
- **O3, differential.** Folded client state per op per seat equals the base recordings on the GC cases (the PV2 method, with `gallery_transcript.py` recording the seats' updates). Because the protocol changes, compare **folded state projected to a common representation**, not bytes.
- **O4, idempotence and resume.** Deltas carry absolute after-values (HP, membership by id, tile and object values, masks by add/remove). Re-applying a delta is then a no-op per (identity, family). Two consequences:
  - `fold(snapshot_c) ∘ updates(c..n] == fold(0..n)` on the perceived part;
  - folding the spool bytes from 0 == the live client fold (the decode path).
- Keep the third leg of today's test: client senses == cold composition.
- The PV3 gate, "no body bytes for unchanged re-acquisitions", becomes: count re-acquisition observations that carry a body family whose engine revision is ≤ the seat's seen revision. It must be 0.

---

## 4. Mirror-based features that break, and what replaces each

1. **Body patches** (`_emit_bodies` 2034-2084: `actor_changes(before=remembered.actors[x], …)`).
   - Most changes to a perceived actor already arrive as facts carrying after-values: DamageResult (resulting HP), LifeFact, ConditionChangeFact, EquipmentFact, TemporaryHitPoints, Faction.
   - Bodies only travel on (re)acquisition. The replacement is a per-(seat, actor, family) **seen revision**, compared with an objective per-(actor, family) **change revision** that the shared fold writes from events.
   - If any family changed, send that family's value from the shared fold. First sight sends every family.
   - Byte cost: a changed family is sent whole where PV3 sends only the changed fields. The Sleet-drop case (234 identical re-acquisitions, plan §6b) sends nothing either way.
2. **"Unchanged re-acquisition sends no body bytes."** Kept by the revision comparison above. The `| acquired` admission term (capture.py:808, :877) stays: it is what produces the re-acquisition event.
3. **Item patches** (`_item_patches` 1931-1934). Replaced by "known item" plus a state seen revision. First sight sends the full record (58 of 59 fields are static per `item_id`, plan §6b); after that, only state when its revision moves.
4. **Known-membership removal carries the held member value** (2073-2079). Replaced by a removal by `condition_uuid` only; the client already holds the value. Knowledge needed: the set of (actor, condition_uuid) the seat holds. Protocol change.
5. **Object observation merge** (`_observed_object` 1035-1076). Faces of wall residues and construction suppressions that are not visible now keep their remembered value. This is the one place the *value* is a merge of observations over time.
   - Event-native: the server sends only the parts visible at the event (per face, per provider), and **the client reducer merges**. This is a protocol change in the Python and TS SDKs, and the Godot client must follow.
   - Suppression of unchanged parts: a per-(object, face/provider) seen revision against the objective revision.
6. **Tile diff** (`_world_update` 1181-1193). Replaced by:
   - a per-seat `uint32` seen-revision grid over the map (0 = never seen);
   - an objective per-cell change-revision grid in the shared fold.

   A tile is sent when it is visible at the event that changes it (taken from the event's after-values), or when it re-enters view with change-revision > seen-revision. A field-level patch on re-entry needs per-field objective revisions, a few `uint32` grids per map that are shared and not per seat; otherwise the whole tile is sent. Fireball's 53–56 KB residue re-send (progress :521) is still the separate residue-patch decision.
7. **Removal rule judged against the view at each event** (1210-1213; the reason once-per-group `_world_update` is not exact, progress :513). It needs only knowledge:
   - the view at that event (the composition's mask, a frozen packed value that is cheap to hold per event);
   - `remembered_positions` / `remembered_order`.

   It stays per event, with no values.
8. **Connectors diff** (1224-1227). It re-sends the visible connectors tuple whenever an update is non-empty. Replace with a visibility set or bitset over the init connectors.
   - Observation: it reads `world.world.connectors`, the **init event**, not `recorded_world.connectors`. Connector changes after init never reach a seat.
9. **Spatial sightings** (`spatial_values` 1722-1731, 1754-1779). The engine emitter already diffs per observer, so `spatial_values` is a mirror of a diff the engine has done and is deleted.
   - The seat-local revision renumbering (`spatial_versions` / `spatial_revisions`) stays as knowledge, with pruning (§6).
   - Effect content goes through a per-effect "content known at revision" instead of `spatial_content.get(id) != content` (2071, 1759).
10. **HUD patch** (2144-2171). It diffs a full snapshot recomputed from engine state at every op end (session.py:466-486) against `hud_snapshot`. This is the one feature that is **not event-native today**. See R1.
11. **Capture inputs read from the mirror** (application.py:64-75). These become reads of the knowledge sets:
    - `known_actor_uuids`;
    - `known_entity_names` (from the shared fold if names are immutable, else a name-knowledge map);
    - `known_connector_uuids`;
    - `known_content_ids`.
12. **Disclosure monotonicity, today:**
    - lineages, actors, tiles, spatial content and content only grow (a terminal actor is never resurrected, reduction.py:172-179);
    - objects leave memory only when seen absent at an event;
    - items leave only on a destroyed charge;
    - contacts and the view are current-only.

    Event-native keeps this as monotone identity sets with the same two explicit removals, judged per event against the view.
13. **Object memory for cells out of view** stays on the client only. The server keeps where the seat remembers each object (1D) and its seen revision, never the value.

---

## 5. Memory (estimates; no probe was run)

These figures come from CPython container sizes and the plan's counts. Dict slot ≈ 45 B; an int > 256 is 28 B; event UUIDs are shared with the EventQueue.

**Mirror values per seat** (1C, plus 1B `world`/`actors`):

- bounded by the world and by identities ever seen;
- GC: ≤1,895 tiles, ~126 objects, ~30–60 actors, hundreds of items, one HUD, spatial content;
- the plan's attribution counts the whole player runtime at **84K tracked objects** at setup (plan :764), roughly 10–20 MB;
- it grows only slowly (summons, created items, zones).

**Per-seat O(history)** (1B causal maps), per native version:

- `version_cursors` ~75 B;
- `lineage_keys` ~45 B per lineage (~1/3 of versions);
- `public_versions` + `public_cursors` ~120 B per disclosed version;
- public lineages and disclosed sets ~80 B per disclosed lineage.

At 50 % disclosure that is **~165 B per version per seat**. Fireball (564 versions, 193 lineages, progress :238) is ~80 KB per op per seat.

**Event store:** +16–20K tracked objects per op (plan :765), roughly 2–6 MB per op, never pruned, plus 7 indexes (events.py:1317-1328).

**8.8 GB at 47 min** (progress :259). The long game is `blue_ai=True` (gallery_crowd.py:910), so **one seat**. At ~4 MB per op, 8.8 GB is about 2,200 ops in 2,800 s, which is plausible.

- Per-seat causal maps: ~2,200 × 80 KB ≈ **~0.2 GB (≈2 %)**.
- Mirror values: **~10–20 MB (≈0.2 %)**.

**What event-native deltas save:**

- Deleting the mirror saves almost no memory; its value is CPU (the diffs) and the removal of a second state.
- Deleting the duplicate maps (`version_cursors`, `lineage_keys`, `public_versions`) and storing the public numbering as an `int32` array cuts per-seat growth from ~165 to ~8 B per version.
- The dominant retention is outside this scope: EventQueue keeps every version forever, and AI knowledge too.

Confirming this needs a heap attribution by owner on the long game. Per the memory note, that is a probe to ask the human about first.

---

## 6. Conclusions

### Minimal per-seat KNOWLEDGE state

Ints, ids and masks only; no client values.

- **K1. Perception.** `AudiencePerception.members` plus `AudienceComposition` (as today).
  - Invalidation: advanced only by the members' SensoryUpdateEvents; `initial` resets a member; derived indexes are rebuilt by the cold composition.
  - Add pruning: drop `contact_cursors`, `effect_cursors` and `effect_absences` for identities no member holds; keep only the highest removal revision per light source.
  - The history-dependent contact ranking (progress :230) is a separate fix; it would delete the cursors.
- **K2. Identity knowledge with seen revisions.**
  - actors: per (actor, family) seen revision, a terminal flag, held condition ids;
  - items: state seen revision (membership means known);
  - objects: `observed`, `remembered_positions`, `remembered_order`, plus a seen revision per object and per face or provider;
  - tiles: a `uint32` seen-revision grid;
  - spatial effects: native → seat revision, kept only for revisions some member still holds, plus a content revision; the owned-effect set;
  - connectors: a visibility bitset;
  - content: a set of identity keys;
  - `spatial_commit_cursors`.
  - Invalidation: a seen revision advances only at an event disclosed to the seat; sets are monotone except an object seen absent at an event and a destroyed item.
- **K3. Causal knowledge.**
  - native cursor → seat occurrence index as an `int32` array (`boundary()` becomes a bisect);
  - native lineage → seat lineage index;
  - disclosed lineage set and disclosed turns;
  - `next_occurrence`, `next_log_append`.
  - Append-only.
- **All of K** is dropped on an EventQueue generation change. An audience change stays unsupported: it raises today (projection.py:2213-2215).

### Shared per session, not per seat

One objective fold, extending the existing `CaptureCheckpoint` and advanced once per version:

- one `WorldFacts`;
- the actors it already holds;
- per-identity change revisions: actor family, object and face, cell and field, item state, effect content.

It is written only from event after-values, so the recorded path (`project_sequence`) keeps working with no engine.

### Deleted

- `PlayerState` as a server value: tiles, objects, connectors, actors, items, spatial_content, hud_snapshot, the content descriptors;
- `ProjectionState.world` and `ProjectionState.actors` (N copies);
- `spatial_values`;
- `observed_values`;
- `version_cursors`, `lineage_keys` and `public_versions`;
- the replica test's "client == `remembered`" leg;
- the `remembered` reads in capture.

### Snapshot and reconnect rule

Initialization = the delta stream over startup, folded against empty knowledge (one path). Reconnect = journal replay (unchanged). A snapshot from state is exact only for what is perceived now. It is built from the same functions that build first-sight values, and is used as the oracle (O1). Late join is refused unless the human chooses event-store-pinned memory.

### Oracle

- O1: perceived part == `snapshot_perceived`, at each op end;
- O2: the harness carry-forward for memory;
- O3: base differential on folded state;
- O4: idempotence (snapshot + tail == full fold; spool fold == live fold);
- the cold-composition leg stays.

### Open risks and decisions for the human

- **R1. HUD.** Fields may change without an event that touches the actor. Options:
  - (a) send the whole sheets of controlled actors touched by the op's events, after an audit that every sheet field is evented;
  - (b) keep one bounded HUD mirror as the only exception;
  - (c) a per-sheet fingerprint (still a diff against client state).
- **R2.** The face and suppression merge moves to the client reducer: a protocol change in the SDKs and the Godot client.
- **R3.** Family-level patches on changed re-acquisitions cost more bytes than today's field patches, unless per-field revisions are added.
- **R4.** Projecting inline at event arrival from live engine state, which is the literal reading of "the engine knows it", would break the engine-free `project_sequence`. The shared fold avoids that.
- **R5. Privacy.** Seat-local occurrence and revision numbering hide how many undisclosed versions or changes happened. Putting native cursors on the wire would delete K3's maps but leak those counts.
- **R6.** Perception that lasts only inside one op needs a group-close hook or O3.
- **R7.** If the memory refactor prunes the event store, the events that seen cursors point to must be pinned (only if snapshot option (b) is chosen).
- **R8.** Event-native deltas alone do not address the 8.8 GB.
- **R9.** Connectors are read from the init event only (projection.py:1224).

Any plan built from this study needs the antislop and antiOOP reviewers (AGENTS.md).
