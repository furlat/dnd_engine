# Sensory, spatial effects, per-event facts and lineage under the no-memory rule (read-only rescan, 2026-10-18)

Static study: nothing was edited, run, timed or measured. Repository `/home/tommaso/.codex/worktrees/event-native-deltas/dnd_engine` at `55bf034cc`. `dnd/` is unchanged since `094b528f7`, so the earlier study's line numbers still hold; every line below was re-read at this head. Combat log: out of scope (human). Bytes come from `agent_docs/event_native_deltas_2026-10-18/byte_census.txt`.

## The rule (the human's, authoritative)

Publication keeps **no remembered state**. A seat's update holds:

1. for things the agent perceived before **and** after an event: the event's own change;
2. for things **entering** perception: their current state, in full;
3. for things **leaving** perception: nothing.

Per-seat server knowledge is only what is perceived now, plus the static content ids already sent. There is no copy of client values and no last-seen stamp. Nothing is restated within one update.

How I read it:
- "Leaving: nothing" means no state about the leaving thing. The perceiver's own perception record still says that the thing left (a removed key, or cells removed). That key is the perceiver's change under (1), not state of the thing.
- The earlier study's D1(b) ("a per-record revision, plus the seat's last-seen revision") is now ruled out.

Gallery seats (`devtools/performance/gallery_crowd.py:131-165, 208-214`): amber has **4** observers (sorcerer and 3 allies); blue has **26** (10 + 6 + 10 crowd). A seat observes every member it controls (`dnd/player/session.py:287`). The census counts suggest one update per seat per op, and one lineage per update: top.audience and lineage.audience have equal bytes in all four cases.

---

## 0. Findings in brief

1. **The sensory perception record is already event-native.** Cells, light and hazard values, contacts and removals all come from the native before/after (`dnd/blocks/sensory.py:393-464, 467-640`). Under the rule, the only native gaps are light rows and sightings, which are sent whole per change.
2. **Most of what the rule deletes in this family is server memory.**
   - `spatial_values`, a mirror (`projection.py:1922`).
   - `spatial_versions` and `spatial_revisions`, per-seat stamp maps (`1923-1924`).
   - The content value checks (`1759-1772`, `2068-2071`).
   - The sighting equality scans (`343-351`, `1979-1985`).
   - The seat renumbering of `owner_revision` (`1715-1731`, `1840-1841`).
3. **The rule forbids per-seat stamps on the wire, and today's client composition needs them** (`owner_revision` joins, light removal revisions). This decides much of C3: only (B) and (C) need no revision on the wire at all.
4. **New restatements found**, besides the known ones:
   - `SensoryFact.cause_occurrence` always equals the node's `parent_event` (`sensory.py:603-606`), and no client code reads it.
   - `SpellFact.application` is fully restated by the node's `resolution` row, except for its index (`base_actions.py:2401-2418`; `projection.py:917-922, 1837`).
   - `PlayerNode.lineage` and in-group `parent_lineage` can be derived from `version_rows` plus `parent_event` / `children_lineages`.
5. **Two kinds of memory the rule, read literally, also forbids**, which are outside "copies of client values". The human must rule on both (§5, R1 and R2):
   - the audience composition's `contact_cursors`, `effect_cursors` and `effect_absences` (last-seen cursors per member and identity, `audience.py:69-74`);
   - the projector's seat numbering maps (`public_versions/cursors/lineages`, `disclosed_lineages`, `disclosed_turns`, `projection.py:1912-1920`).
6. **Every disclosure decision is already seat-level.** `_project_fact` and the declaration grants read the server's composed view (`projection.py:1405-1408, 1474-1475`). Only the sensory wire is per member. So all three C3 options keep the server composition, and (A) alone adds a second one on the client.

---

## 1. Per kind: what it becomes, and what is deleted

### 1a. Sensory perception record (`SensoryFact`, `SensoryRows`)

| Kind | Under the rule | Deleted / changed |
|---|---|---|
| Scalars: position, sense modes, passive, visual access, paths (`facts.py:879-907`) | (1): a flag plus the after-value only when changed. This is already true (`sensory.py:524-536`), except `observer_position`, which is always set (`sensory.py:598`, `projection.py:361`; required at `facts.py:882`). `initial` means the member's own perception enters (validator `events.py:3428-3437`). | `observer_position` becomes optional, sent only when `observer_position_changed`. The fold reads it only then (`sensory_fold.py:73`; `reduction.py:412-414`). The change is wire-only: capture still reads the native field unconditionally (`capture.py:808`). |
| `cause_occurrence` (`facts.py:885`) | Restated: natively `cause_event_uuid == parent_event` (`sensory.py:603-606`). The projector nulls it unless the cause lineage is disclosed (`projection.py:1602-1604`) and maps it like `parent_event` (`1854`). | Delete the field; `PlayerNode.parent_event` carries it. No reader in `dnd/player/reduction.py` or `server/`. |
| Visible / seen cells (`RowBits` over `SensoryRows.cells`) | (1)/(3): masks of added and removed cells from the member before/after (`sensory.py:393-447`). Already compliant. | Nothing under (A). Under (B), the composed view's change (§3). |
| Light / hazard values (`effective_light_levels_changed`, `hazardous_cells_changed`) | (1)+(2): after-values at changed cells, and at cells that enter view (`sensory.py:442-446`). Zero values are left out at entering cells (`projection.py:2003-2006`). Already compliant. | — |
| Contacts (`contact_*` columns) | A changed contact is position + visual bit + special senses (`sensory.py:450-464`). Strictly, only the position or the visual bit changes. But visual is one bit and senses are omitted when empty (`facts.py:827-828`), so the restated part costs about one bit. Entering is full: the native `before` lacks it. | Keep as is. Under (B), the composed holder's contact (`audience.py:714-735`), and delete `contact_overrides` (`audience.py:456`; `reduction.py:182-189`). |
| Removals (`entity/object_contacts_removed`, `spatial_effects_removed`) | (3): the key only. Already compliant. | — |
| Light removals (`light_removal_uuid_index`, `light_removal_revisions`) | (3): the key. The revision exists only for the client composition, which retires stale member rows by it (`audience.py:218-236`). | Under (B)/(C): delete the `light_removal_revisions` column. Under (A) it must stay, as a native revision. |
| `LightRow` (`facts.py:781-800`) | **Added (full)** when the member's published row was absent: `current is None` (`sensory.py:2532-2533`). **Patched** when it was replaced (`sensory.py:2534`): the fields of `values` that differ from `previous_values[identity]`. Both tuples meet at `sensory.py:2516-2518`; their layout is revision, position, height, appearance, three radii, actor_anchored, plus the two disclosed anchors (`gridmap.py:5547-5550`). A walking torch-bearer's patch is `{source, position}`, plus `revision` under (A). Patches can share one object per settlement under the existing `shared` key (`sensory.py:2521`). | `affected_tiles` is dead live: the constructor never sets it (`sensory.py:2526-2530`). Delete it from `PerceivedLightSource` (`senses.py:135`), `LightRow` (`facts.py:800`), `_light_row` (`projection.py:1945`), `sensory_values` (`reduction.py:253`), `_merged_light`'s tile union (`audience.py:239-251`) and the `not old.affected_tiles` test (`sensory.py:2518`). Interning by value (`projection.py:1979-1985, 2020-2021`) becomes by identity. Under (B)/(C), delete `LightRow.revision` from the wire too: it currently leaks counts of unseen changes. |

### 1b. Spatial effects

| Kind | Under the rule | Deleted / changed |
|---|---|---|
| `SpatialEffectSighting` (`facts.py:748-778`) | **Added (full)** when the member had no row (`previous is None`, `sensory.py:2382-2383`; new rows enter at `2403`). Content is sent as a content id, its body once per id (row below).<br><br>**Patched** when the row exists. The merge has `previous`, `kept` and `observed` side by side (`sensory.py:2379-2401`): after = `kept ∪ observed.positions`; `positions_added` = after − previous; `positions_removed` = previous − after.<br>• Scalars are sent only when changed: duration only if the seat owns the effect; trap_state, pressed, direction, anchors, energy, presence mode, sustainer, concentration slot, anchor position and elevation, area_geometry, construction_sections, area_propagation, deposit_source.<br>• View-transient fields go as after-values when changed: the `visible_volume_positions` mask, `upper_volume_surfaces` (keyed by (position, planes), as the join already keys them at `audience.py:155`, so as added/removed keys) and `suppressions`. The path where nothing was re-observed strips exactly these (`sensory.py:2324-2337`).<br>• An empty patch, once undisclosed fields are stripped, is dropped. The existing empty-fact test (`projection.py:1782-1791`) stays.<br><br>`owner_revision` is the native `condition.observation_revision` (`sensory.py:2350`). Under (A) it goes on the wire unrenumbered. Under (B)/(C) it does not go on the wire. | `ProjectionState.spatial_values` (`projection.py:1922`) and `_observe_spatial_revisions` (`1715-1731`).<br>In `_public_occurrences`, the whole change filter: `touched_spatial`, `previous_spatial`, `previous_revisions`, `content_held` and the `changed` test (`1749-1781`).<br>The duration `_map_sightings` pass (`1748`) becomes a strip per patch, done by a function of the effect's creator and the audience. That function replaces `owned_spatial_effects` (`1921`, `2197`, `2217`), which is memory.<br>Under (B)/(C), also the revision map pass (`1840-1841`), `spatial_versions` and `spatial_revisions` (`1923-1924`). Under (A) these maps are forbidden by "no last-seen stamps" anyway, so (A) must send the native revision.<br>`SensoryTable.built_sightings` / `_group_sighting` (`320`, `343-351`) become native sharing per settlement, as for lights. `_sighting` (`270-282`) goes if the native event carries masks. |
| `spatial_effect_content` (`facts.py:903-904`) | Static content: sent once per **content id** per seat. "Static content ids sent" is the one memory the rule allows. Today it is keyed by effect uuid and checked by value. The producers return the condition's own `content_ref`/`name`/`description` (`area_conditions.py:181-182`; other producers: `triggers.py:52,184`, `mechanisms.py:102`, `jaws.py:92`, `conjuration.py:909`, `sorcerer.py:651`, `environmental_conditions.py:1085`, `base_conditions.py:388`). | The value checks `projection.py:1759, 1772` and `2068-2071` go. `PlayerState.spatial_content` stays on the client (`facts.py:1195`), and the server keeps only a set of content ids. **To check:** that `name`/`description` depend on `content_ref` alone, and that they do not restate the `ContentDescriptor` (`display_name`, `description`) admitted for the same ref in the same update's `content_additions` (`content_composition.py:88, 113`). |
| `SpatialEffectStateFact` (`facts.py:910-923`) | A presentation cue: the reducer does not fold it (no case in `apply_record_fact`, `reduction.py:369-464`).<br>• REMOVED: `positions` equals `removed_positions` (`projection.py:459-462`). Send `removed_positions` only.<br>• FOOTPRINT_CHANGED: `positions` is the whole visible new footprint (`476-479`). Send the visible added cells, computed from the native event's own `previous_positions` and `affected_positions` (`events.py:3548-3549`). Removed cells are already a delta (`469-473`).<br>• CREATED: its `positions` restate the sighting (added) in the same update; it could name the effect only (cue-timing risk, R9).<br>• STATE_CHANGED restates `state`, which the sighting patch also carries as `trap_state`. Keep `previous_state` as the cue. | No native change needed: the event holds both footprints. |

### 1c. Per-event facts and lineage structure (restatements: §2)

| Kind | Under the rule |
|---|---|
| `SpellFact` (`facts.py:434-470`) | The cast root carries the declaration. Per-target children are `execution_event.model_copy` (`base_actions.py:2405-2416`); each child carries only `target_entity_uuid`, `target_kind/position/base_height_steps`, `propagation` and `attack_outcome`. `application` is deleted (see the next row). |
| `SpellApplication` / `PlayerResolution` (`facts.py:425-430, 1025-1030`) | The per-target event's `resolution_ref` equals its `application` minus the index: same lineage, same `application_id` (`base_actions.py:2401-2418`). Projection keeps both under the same disclosure condition (`projection.py:1604-1606` vs `1625-1626`) and maps both with `lineage()` (`1830-1837` vs `1855-1857`). So: `PlayerResolution(lineage, application_index)`, no `application_id` UUID, and `SpellFact.application` deleted. The only readers are row identity and `index_player_lineage` (`reduction.py:97-101`). |
| `PlayerNode` (`facts.py:1000-1022`) | Keep `occurrence`, `parent_event`, the ordered `children_lineages` (the log composition contract, `facts.py:182-186`) and the fact. `lineage` can be derived from `version_rows` at `occurrence`. `parent_lineage` can be derived from `parent_event` through `version_rows`, or from the parent's `children_lineages`: keep it only for a group root whose parent sits in an earlier update. This adds no disclosure: `version_rows` already gives the lineage of every admitted version (`projection.py:1808-1817`). |
| `VersionRows` (`facts.py:1033-1042`) | `occurrences` is mostly `[start_cursor, end_cursor)` (`projection.py:1808-1817`). Send it as a range plus exceptions (late disclosures). |
| `PlayerLineage` / `PlayerUpdate` envelope | §2, item 1. |

---

## 2. Restatements inside one update, with the exact fix

| # | Restatement (code) | Fix | Census bytes (fireball / sleet / SG walk / darkness) |
|---|---|---|---|
| 1 | Envelope. `audience` is on `PlayerUpdate` (`application.py:97`) and on every `PlayerLineage` (`projection.py:2206, 2250`). `generation` and `observer_uuid` are on every lineage (`2247`), every `CombatLogAppend` (`application.py:81`; `facts.py:202-203`) and `PlayerHUDPatch` (`facts.py:169-170`). | Once per update: delete them from `PlayerLineage`, `CombatLogAppend` and `PlayerHUDPatch`. The client checks (`reduction.py:201-204, 566-570, 594-599, 657, 677-680`) become one envelope check. The audience is fixed at Start (`server/worker.py:74-80`), so it is static sent knowledge: it can be sent only in `PlayerInitialization`. | lineage.audience 2.4 / 4.7 / 16.6 / 4.7 KB. Initialization-only would also remove top.audience: 4.8 / 9.4 / 33.2 / 9.4 KB in total (1.5 / 4.4 / 6.6 / 5.5 %). |
| 2 | Each child `SpellFact` copies the cast's declaration: declared targets (N² UUIDs), area_geometry, aoe/source position, name, behavior, effect, cast origin, propagation policy (`base_actions.py:2405-2416` → `projection.py:617-640`). | Declaration on the root only (§1c). Root and children lie in one capture group, so whether the root was disclosed is decided within the update; no memory is needed. | Part of fact.spell (27.0 KB on fireball). About 3.9 KB per seat at 10 targets (earlier estimate). |
| 3 | `SpellFact.application` versus the node's `resolution` row (both carry lineage and `application_id`). | Delete `SpellFact.application`; `PlayerResolution(lineage, application_index)`. | 2 UUIDs per application per seat (~78 B). |
| 4 | Tree edges: `parent_lineage` on the child **and** `children_lineages` on the parent (`projection.py:1589-1592, 1884-1885`). `parent_lineage` is also derivable from `parent_event`; `PlayerNode.lineage` duplicates `version_rows`. `ContentAttribution.emitted_lineages` re-lists children. | Keep the ordered `children_lineages` and `parent_event`. Drop in-group `parent_lineage` and `PlayerNode.lineage`. The client rebuilds them by inverting `children_lineages` (ancestry walk `reduction.py:78-96`, `lineage_branch` 607-638). | node.children_lineages 3.1 KB (SG walk); version_rows and node overhead (§1c). |
| 5 | `observer_position` on every sensory fact (`sensory.py:598`, `projection.py:361`). It also restates `StepFact.to_position` and the `SpatialFact` position for the mover. | Only when it changed. Under (B), only the anchor member's (`audience.py:759-762`). | ~27 B per sensory fact. |
| 6 | `cause_occurrence` equals `parent_event`. | Delete (§1a). | A few bytes per sensory fact. |
| 7 | REMOVED `SpatialEffectStateFact`: `positions == removed_positions` (`projection.py:459-462`). FOOTPRINT_CHANGED and CREATED `positions` restate the sighting in the same update. | §1b. | Half or more of fact.spatial_effect_state (5.8 / 14.6 / 0.8 KB, sleet / SG / darkness). |
| 8 | `PlayerObservation.contact` on an admission restates the witness member's contact, which the same group's sensory fact carries (`capture.py:891-894`). It is the source of the client-only `contact_overrides`, a known divergence (`projection.py:1904-1906`). | Under (B): delete it. Under (A): drop it when the sensory fact in the same update carries that member's contact. | body.contact 5.7 KB (sleet), 5.7 KB (darkness). |
| 9 | `SensoryRows` per lineage, not per update (`projection.py:2238-2251`): uuids, contacts and light rows repeat across an update's lineages. | One `SensoryRows` per `PlayerUpdate`, interned by identity (R7). | ~0 in the census (one lineage per update); real in multi-root ops. |
| 10 | Content: by effect uuid, and possibly also as a `ContentDescriptor` (§1b). | Once per content id; verify it against `content_additions`. | small |
| 11 | **(A) only:** one change of the seat's composed view is stated in up to N member facts (e.g. 26 bit lists naming the same cell, 26 sighting rows that do not intern because each member's visible part differs). | This is C3 (§3): it counts as a restatement only if "the agent" is the seat. | fact.sensory 16.0 / 60.7 / 164.3 / 45.9 KB |
| 12 | Whole `LightRow` / `SpatialEffectSighting` per change: unchanged fields restated. | Added / patched (§1a, §1b). | Part of lineage.sensory_rows 14.4 / 70.3 / 42.8 / 70.6 KB |

---

## 3. Multi-observer seats under the rule (C3)

C3 is the choice of what **"the agent"** in the rule is: (A) each member; (B) the seat; (C) the seat, plus one member.

Common ground:
- The server already folds every member into one composition per seat: `fold_senses(..., audience_composition)` at `projection.py:1474`, `apply_current_audience` at `audience.py:586-765`.
- Every disclosure reads the composed view: `private_world.senses`, declaration grants (`projection.py:1405-1408`), effect-state disclosure (`452-490`).
- So no option removes server-side composition.
- The members' snapshots are the members' native perception now. The rule allows them.

### (A) Per-member perception deltas; the client composes (today)

- **Entering.** Sensory rows enter per member: the native `before` lacks the identity (`sensory.py:464, 2382, 2533`). Records cannot enter per member, or the rule's (1) and "nothing restated" break:
  - a body re-admitted whenever any of 26 members regains sight of it (`capture.py:805-813` computes `acquired` per member; `_derive_admissions` adds `| acquired`, `capture.py:872-877`);
  - tiles re-sent from a member's added cells (`projection.py:1466`).

  So records enter per seat and rows per member. That needs the server composition for records and a client composition for rows.
- **Bytes.** Today's sensory share stays, minus the patches and `observer_position`: fact.sensory 16.0 / 60.7 / 164.3 / 45.9 KB is per-member bit lists, scalars and indices, and is untouched. The sensory total is 30.4 / 131.0 / 207.1 / 116.5 KB, which is 9.6 / 60.6 / 41.3 / 67.7 % of the four cases. Revisions must be on the wire: effect `owner_revision` (for joins and ranks, `audience.py:149, 161, 203, 524, 568`) and light revisions plus removal revisions (`218-236`).
- **Divergence** (`audience.py:161`).
  - Mechanism:
    - The server composes native values (native `owner_revision`, full `duration`).
    - The client composes wire values (`joined_effect`, `reduction.py:257-271`).
    - `_effect_signature` includes both `duration` and `owner_revision` (`audience.py:129-131`).
    - So members that saw native revisions 3 and 4 differing only in an undisclosed field join on the client but not on the server. The server's view then decides disclosure (`projection.py:452-490`) over a footprint the client does not show.
  - Under the rule, the per-seat renumbering is a stamp map and must go. The remaining fix is for the server to compose over exactly the wire values: strip before folding, use native revisions. That is two implementations (Python and Godot) that must agree exactly, and nothing tests it: the replica check compares the same reducer against itself.
  - Native revisions on the wire leak counts of unseen changes. Light revisions already do today.

### (B) The server sends the composed seat view's change (one fact per settlement)

- **What "occurrence" must mean.** One fact per **settlement**, not per member event.
  - The members' events of one settlement are registered as one completion sequence (`sensory.py:1127, 1274`).
  - Folding them one by one and emitting each fold's composed change would send transient states: a cell removed at A's fold and re-added at B's fold. That is a restatement, plus spurious seat-level "entering".
  - So: fold every member event of the settlement, then emit composed(before) → composed(after) once.
  - The before/after already exist inside the composition: cells as `held` vs `composed` (`audience.py:396-405`), contacts (`714-735`), effects (`736-746`), seen (`747-748`) and lights (`749-758`).
  - The fact sits on the settlement's first member node. The other member nodes carry no fact and drop out unless something else admits them.
- **Entering.** Per seat, for rows and records alike: the composed before lacks the identity or cell. Bugs 3 and 4 of the earlier study disappear by construction. Leaving is per seat too: the composed row is gone.
- **Bytes** (estimate; the census has no per-seat or per-member split).
  - fact.sensory scales with 1 fact per settlement instead of N active members (up to 4 amber, up to 26 blue). The upper bound on the saving is fact.sensory × (1 − 1/N_active), from 16.0 / 60.7 / 164.3 / 45.9 KB.
  - lineage.sensory_rows (14.4 / 70.3 / 42.8 / 70.6 KB) is already one union cell table per group. Under (B) only its member-specific parts shrink:
    - sightings, where members with different visible parts never intern (Sleet, Darkness);
    - volume surfaces: per member today, one composed union under (B). They are likely the bulk of Sleet's and Darkness's rows; confirm with a column split.
  - The composed cell changes are bounded by the cells the members' changes touch. They can include a light-owner switch, e.g. when the brightest member loses a cell another member still sees.
  - Also removed:
    - the member sensory nodes' share of node.phase and version_rows (9.5 + 11.9 KB on SG walk);
    - body.contact (5.7 + 5.7 KB);
    - the light removal revisions and every `owner_revision`.
- **Divergence.** None: one composition, on the server, and the client folds the result. Deletes on the client:
  - `fold_senses` with `begin_audience_composition` / `apply_current_audience` (`reduction.py:358-366, 671-674`);
  - `PlayerState.perception` (`facts.py:1202`), `contact_overrides`, and the `_observe` override (`reduction.py:182-189`).

  Deletes on the server: `spatial_versions` / `spatial_revisions`. The server stores nothing new.
- **Loss.** The client can no longer show one character's own view: its fog, or what it alone sees.

### (C) Composed by default, plus per-member detail for the controlled/selected agent

- **Entering.**
  - The composed part works as in (B).
  - Member detail is that member's native deltas.
  - When the selection switches, the new member's whole current perception enters: (2), the full member snapshot the server already holds. The old member's detail leaves: (3), nothing.
- **Bytes.**
  - (B) plus the selected member's own deltas: about 1/N of (A)'s member share while that member is active.
  - Plus one full member state per switch. That is visible/seen masks, light values, every contact, lit emitter and sighted effect: estimated at a few KB to ~10 KB, not measured.
  - If "controlled" means the input actor, the blue seat switches up to 26 times per round.
  - If detail is kept for every controlled member, (C) costs (A) + (B).
- **Divergence.** None: the detail is one member's native deltas, so the client has no composition. The client keeps two folds (composed, and one member).
- **Needs.**
  - If "selected" means the input actor: it is already server state (`BoundaryState.input_actor_uuid`, `server/host.py:132`), so no new message is needed.
  - If it means a UI selection: a client→server message, plus per-seat "selected member" state. That is seat control state, not perception; the rule does not cover it explicitly.

| | A | B | C |
|---|---|---|---|
| Unit of "entering" | member (rows) + seat (records) | seat | seat; member on detail, and on each switch |
| Sensory bytes | today minus patches | ≲ today / N_active (fact part) | B + 1 member + switch snapshots |
| Revisions on the wire | required (native: leaks counts) | none | none |
| Compositions | 2 (server and client) | 1 | 1 |
| Divergence at `audience.py:161` | stays unless the server folds the wire values | impossible | impossible |
| Per-character view on the client | yes | no | the selected one only |

---

## 4. Native changes needed

Needed for each option:

- **N1. A settlement boundary**, for (B)/(C). The projector must know which member sensory versions form one settlement. Grouping by contiguity alone is not enough: within one settlement, a member's cause can differ when `cause` is None (`sensory.py:1357` uses `events[-1]` per observer). Small fix: a settlement marker on `SensoryUpdateEvent` (count or index) at `_emit_settlement` (`sensory.py:1295-1318`).
- **N2. Seat-level acquisition for admissions**, all options (the rule's (1) and (2)). This is projection/capture code, not engine code. In `_derive_admissions` (`capture.py:858-897`), keep only those `acquired` identities that no other seat member holds in `row.holders`: only the sensory observer's contacts changed at that version. Under (B), take it from the settlement's composed contact change instead.

Optional; they save per-seat CPU, or are needed only if patches are built natively:

- **N3. Light rows added / patched** in `SensoryUpdateEvent` (`events.py:3348`).
  - Where: built at `sensory.py:2516-2534` (added when `current is None`, patched when `replaced`, patch = differing tuple fields), or in the emitter from `before.light_sources` vs `after` (`sensory.py:519-523`).
  - Shared per settlement under `shared`.
- **N4. Sightings added / patched.**
  - Where: from `previous` / `kept` / `observed` at `sensory.py:2379-2403`, or in the emitter from `effect_before` (`sensory.py:1334-1338`) vs after.
  - Its masks replace `_sighting` (`projection.py:270-282`).
- **N5. Consumers of a patch-shaped event**, which must move together:
  - the `SensoryDelta` protocol (`senses.py:152-200`) and the shared reducer (`sensory_fold.py:62-70`);
  - `observe_audience` and `apply_current_audience`, which read effect positions and light values from the event (`audience.py:88-93, 613-620, 653-660`; `_keeps_composed_*` at 546-584);
  - the AI knowledge reducer (`knowledge_reduction.py:223-240`, via `apply_current_senses`);
  - capture `_reduce_sensory_fact` (`capture.py:522-534`), `validate_replay_payload` (`events.py:3444-3460`), `devtools/player_server_acceptance/movement_profile_worker.py:316`;
  - recordings (`event_record.py`; reproject, `reduction.py:644-650`) and the SDK contracts (`sdk/python/src/dnd_player/contracts.py:1576, 2551`).

  The alternative needs no native change: the projector builds the patch from the composition's member snapshot (before) and the native event (after). That is perception-now plus the event, but it runs per seat instead of once per settlement.
- **N6. `affected_tiles` removal** from `PerceivedLightSource` (`senses.py:135`). It waits on the old-recording policy.

Not needed:
- spell children, `cause_occurrence`, `observer_position` and the envelope are wire-only;
- `SpatialEffectChangeEvent` already holds both footprints (`events.py:3548-3549`).

---

## 5. Risks

- **R1. Composition cursors vs "no last-seen stamps"** (needs the human).
  - What they are: `contact_cursors`, `effect_cursors` and `effect_absences` (`audience.py:69-74`, written at `76-117` and `664-671`). They are per (member, identity) or (identity, cell) cursors of the last sighting, never pruned (`projector_state.md` §1E).
  - Where they live: under (A) they exist on both server and client; under (B)/(C) on the server only.
  - What can go without them: contacts are current perception, so they can rank by (visual, member uuid) with no cursor.
  - What still needs them: merging members' *retained* effect cells (hidden parts keep their last observation, `sensory.py:2384-2385`) needs an age, for a cell no member sees now.
  - Options: keep them as allowed perception state; rank by native `owner_revision` only; or stop uniting retained cells across members.
- **R2. Seat numbering maps vs "no remembered state"** (needs the human).
  - `public_versions`, `public_cursors`, `public_lineages`, `disclosed_lineages`, `disclosed_turns` and `next_occurrence` (`projection.py:1912-1920, 1806-1827`) are per-seat memory.
  - Native ids on the wire would delete them, but leak how many undisclosed events happened.
  - References to earlier lineages also need the "was it disclosed" memory: `AreaReachFact` previous/prerequisite, `ActionReaction`, `ContentAttribution`, root `parent_lineage`, `SpatialFact.commit_occurrence` / `creation.birth_occurrence`. A reference to an undisclosed id leaks its existence.
- **R3. Retained native perception.** The rule constrains publication. Native perception keeps effects whose hidden cells keep their last observation, plus light removal revisions; the AI knowledge reducer uses both. Applying the rule natively would be a rules change.
- **R4. Settlement atomicity** (§3 B). Per-member folding creates transient composed states: restatements and spurious re-admissions. Compose per settlement (N1).
- **R5. Disclosure of patches.**
  - Strip `duration` for effects the seat does not own. Anchors are per-member grants (`area_conditions.py:187-190`); the join takes the first non-None (`audience.py:135-141`).
  - A patch that is empty once stripped is dropped, never sent.
  - Under (A), native revisions leak counts of unseen changes.
- **R6. Spell root-only parity.** Each child is disclosed by its own grants (`projection.py:565-641`, `_identified` per version). Check that no child grant discloses a declared target the root withholds, or the reverse.
- **R7. Per-update interning.** `state_before_event` / `lineage_branch` slice one lineage (`reduction.py:539-550, 607-638`). A saved `PlayerSequence` lineage is self-contained (`facts.py:1161-1167`). Shared rows across lineages need update-scoped indices.
- **R8. Deriving edges on the client.** Dropping in-group `parent_lineage` and `PlayerNode.lineage` moves inversions into the client index (`reduction.py:78-107`). The `children_lineages` order must stay the log order.
- **R9. The cue for CREATED / FOOTPRINT_CHANGED.** Making it reference the sighting assumes the sensory child arrives in the same update. It does: its causal updates are emitted before the parent completes (`events.py:3318-3323`). Animation timing is still the client's.
- **R10. Content by id.** It needs `name`/`description` to be fixed per `content_ref` (§1b), and a check against `content_additions`.
- **R11. CPU of (B).** Diff extraction per seat per settlement is new work, though the composition already computes before and after. The `_keeps_composed_*` shortcuts (`audience.py:546-584`) must still report "unchanged".
- **R12. Schema.** Bump the wire schema (`PlayerSequence.schema_version`, `facts.py:1163`). Add a Godot fold note, regenerate the SDK contracts, and reproject old recordings.

Any plan built from this needs the AGENTS.md antislop and anti-OOP reviewers.

## 6. For the human

- **C3:** (A), (B) or (C), and for (C), "selected" = the input actor or a UI selection.
- **R1:** are the composition cursors allowed perception state?
- **R2:** are the seat numbering maps an exception to "no remembered state", or do native ids go on the wire?
- **Envelope:** the audience only in the initialization (it is fixed at Start), or once per update?
