# Delta study: the sensory, spatial-effect, lineage and combat-log family

Read-only static study. Nothing was run. Repository: `/home/tommaso/.codex/worktrees/single-pass-propagation/dnd_engine`.

The head moved during the study, from ead1f2458 (PV2 wire part 2, schema 15) to 094b528f7 (PV1a-2 fan-out merged). Only `dnd/blocks/sensory.py` changed in scope. All `sensory.py` citations below are at 094b528f7. The `dnd/player/*` and `dnd/core/events.py` citations hold at both heads.

The human's rule, as given in the brief:
- every player wire payload is a delta, produced from the game-state change that produced the event;
- the projector keeps no per-seat copy of client values to diff against;
- the only per-seat state is what the seat can see or know (perception and audience-composition transitions);
- nothing is sent twice in one update.

---

## 0. Findings in brief

1. **The sensory wire is mostly event-native already.**
   - Cells, contacts, removals and scalars come straight from the native `SensoryUpdateEvent`, which `emit_sensory_update_delta` builds from the observer's own before/after (`sensory.py:467-640`).
   - Native per-observer perception already gives "first sight / back in view = whole current value": the `before` lacks the identity.
2. **Two records are whole per change, though the native code holds the keyed change.**
   - **Light rows.** The descriptor is rebuilt whole when any of its 10 inputs changes. At that point the native code holds the old input tuple and the new one (`sensory.py:2516-2531`).
   - **Sightings.** The whole `PerceivedSpatialEffect` (full `positions` mask, geometry, suppressions, volume surfaces) is re-sent. The native merge holds `previous`, `kept` and `observed` (`sensory.py:2379-2403`), and the emitter compares whole values (`sensory.py:513-517`).
3. **The projector copies of client values in this family are all on the sighting path.**
   - `ProjectionState.spatial_values` (`projection.py:1922`): each member's last sighting with its revision removed.
   - The content value comparisons (`projection.py:1759,1772`; `2069-2071`).
   - Their only job is to drop changes the seat cannot see once the projector has removed fields from them (duration for effects the seat does not own, native `owner_revision`).
   - A native field-level patch, with those fields removed, says the same thing: an empty patch means nothing the seat can see changed. No copy is needed.
4. **The audience composition holds full member snapshots and the composed view.** It does not produce the sensory wire: the wire is per-member native deltas, and the client composes again.
   - Two compositions exist over different values. The projector's folds native events, with full `duration` and native `owner_revision` (`projection.py:1474`). The client's folds seat facts, with those fields removed or renumbered (`reduction.py:365,673`).
   - The join rule depends on `owner_revision` (`audience.py:149,161`), so the two composed views can differ.
5. **Restatements inside one update, from the code:**
   - generation, observer and audience on every lineage, and again on the update and on every log append;
   - `SensoryRows` (uuids, contacts, lights) per lineage, not per update;
   - `observer_position` on every sensory fact, even when it is unchanged;
   - per-target `SpellFact`s copy the cast's declaration: declared targets give N² UUIDs, plus geometry, name, origin and effect id;
   - `application_id` is sent twice;
   - every tree edge is sent twice (`parent_lineage` and `children_lineages`), and every node's lineage is also in `version_rows`;
   - the identity fields of `ConditionFact` are repeated in `ConditionState`;
   - a removal of a membership the seat already holds is sent with the seat's own copy of that member;
   - `SpatialEffectStateFact` REMOVED sends `positions == removed_positions`;
   - combat-log entries restate the node's fact (each UUID 3×), aggregate their children (spell-save and multi-entity entries), and repeat renderings: at least 34 producer lines set one rendering equal to another.

---

## 1. Per-kind table

Legend for "source": **N** means taken from the native event of that occurrence; **C** means filtered or derived through a per-seat copy of client values; **K** means it uses per-seat knowledge (perception, composition, identity maps).

### 1a. Sensory and spatial-effect kinds

| Kind | (1) Delta or whole; granularity | (2) Source | (3) Does the native event hold the keyed change? | (4) Repeated within one update | (5) Risks |
|---|---|---|---|---|---|
| `SensoryFact` scalars (`facts.py:862-907`) | Delta: flag plus after-value for position, sense modes, passive perception, visual access, paths (`sensory.py:524-536, 619-629`). But `observer_position` is always present (`facts.py:882`, no default). | N (`projection.py:360-377`) | Yes | `observer_position` repeated on every fact. The fold reads it only when `observer_position_changed` (`sensory_fold.py:73`). | None new. `initial=true` carries the whole member state (`events.py:3428` validator). |
| Visible / seen cell lists (`RowBits` over `SensoryRows.cells`) | Delta: masks of added and removed cells (`sensory.py:393-447`) | N (`projection.py:356-359`, `FactRow`), packed once per group (`projection.py:2000-2011`) | Yes | Cells are once per group. Per lineage, not per update: each lineage has its own `_shared_rows` (`projection.py:2242`). | Ordering is per group. The update-level gate is the cursor (`reduction.py:669`). |
| Light / hazard value lists (`RowBits` over `light_levels`, `hazards`) | Delta: after-value at cells added or changed (`sensory.py:442-446`); zeros are left out at added cells (`projection.py:2003-2006`) | N | Yes | Once per group, as above | "Back in view gets current value" already holds: `light_changed` includes `~before_visible` (`sensory.py:442`). |
| Contact rows (`contact_uuid_index`, `contact_positions`, `contact_visual`, `contact_special_senses`) | Whole small record per changed contact (position, visual, senses), from the native `_contact_delta` (`sensory.py:450-464`) | N; interned per group by `==` (`projection.py:1979-1996`) | Yes. The record is 3 fields, effectively a patch already. | Interned per group, not per update. The `PlayerObservation.contact` of an admission restates the witness's contact (`capture.py:888-892`) that the same group's sensory fact may also carry. | The client composition ranks contacts by (visual, cursor, uuid) (`audience.py:503-519`). |
| Contact / effect removal (`*_removed`, index into `uuids`) | Delta: identities | N | Yes | — | — |
| `LightRow` (`facts.py:781-800`, built `projection.py:1937-1945`) | Whole `PerceivedLightSource` per change: revision, position, height, radii ×3, appearance, actor_anchored, anchors. A moving torch re-sends about 10 fields to change 2. `affected_tiles` is always empty live: the only constructor sets none (`sensory.py:2526-2530`). | N, interned per group by `==` (`projection.py:2020-2021`); natively shared per settlement by key `("light", identity, values)` (`sensory.py:2521`) | **Yes.** The old input tuple `previous_values[identity]` and the new `values` are side by side (`sensory.py:2516-2518`). The tuple is `revision, position, height, appearance, very_bright, bright, dim, actor_anchored` (`gridmap.py:5548-5551`) plus the disclosed anchors. | Whole record per change; a group with K steps sends K whole rows. | `revision` is the raw native light revision. A seat can count unseen changes between sightings (true today). The client composition unions `affected_tiles`, a dead path live (`audience.py:239-251`). |
| Light removal rows (`light_removal_uuid_index`, `light_removal_revisions`) | Delta: (source, revision at removal) (`sensory.py:2544-2549`, emit `522-523`) | N | Yes | — | The revision is required: the composition retires stale member rows by it (`audience.py:218-236`). |
| `SpatialEffectSighting` (`facts.py:748-778`, built `projection.py:270-282`) | **Whole** per change: the `positions` mask is the whole retained footprint (hidden cells keep their last observation), plus `area_geometry`, `construction_sections`, `suppressions`, `upper_volume_surfaces` (planes per cell), duration and anchors. Built per member; interned per group by `==` (`projection.py:343-351`, `1987-1993`). | N, then **C** (filtered): `duration` removed for effects the seat does not own (`projection.py:1748-1749`); a row is kept only if it differs from `state.spatial_values[(observer, effect)]`, or its seat revision moved, or its content changed (`projection.py:1754, 1766-1781`). The native `owner_revision` is renumbered to a per-seat count (`projection.py:1715-1731, 1840-1841`). | **Yes.** The merge has `previous` (the member's held value), `kept` and `observed` (`sensory.py:2380-2400`), and returns the before values (`2379`). The emitter compares the whole before and after (`sensory.py:513-517`). Cells added = `observed.positions − previous.positions`; cells removed = `previous.positions − kept`. | Whole footprint per change per member. Members with different visible parts do not intern (Sleet / Cloudkill / Darkness). | **Disclosure:** duration and native revision are removed today through the copy. **Ordering:** the seat revision is assigned at first admission of (effect, native revision), which is monotone in native order. **Divergence:** the projector composes native values, the client seat values (finding 4). |
| `spatial_effect_content` (`facts.py:903-904`) | Whole static content (content_ref, name, description), once per seat | **C**: built for every changed effect (`projection.py:366`), then filtered by value against `remembered.spatial_content` (`projection.py:2069-2071`). The sighting filter also compares content (`1759,1772`). | Static: sampled producers return the condition's own content (`area_conditions.py:182`, `gas_traps.py:91`) | Keyed by UUID string, though `uuids` already holds the identity | A content change re-sends the sighting. With static content that never happens, so a knowledge set would do. |
| `SpatialEffectStateFact` (`facts.py:910-923`) | Mixed. FOOTPRINT_CHANGED: `positions` is the whole visible current footprint, `removed_positions` a delta (`projection.py:464-476`). REMOVED: `positions` and `removed_positions` are **the same tuple** (`projection.py:459-462`). Pair lists, not masks. | N plus K (filtered by composed `senses.visible` / `observed.positions` and `DeclarationSenses`) | The native event holds whole before and after footprints (`events.py:3548-3549`), so the delta is computable natively | REMOVED doubles its cell list. CREATED / FOOTPRINT_CHANGED `positions` restate what the same update's sightings carry as masks. Not folded into state by the reducer (no case in `reduction.py:369-463`): a presentation cue. | Disclosure reads the projector's composed effect positions, which may differ from the client's (finding 4). |

### 1b. Per-event facts

| Kind | (1) | (2) | (3) | (4) | (5) |
|---|---|---|---|---|---|
| `AttackFact` (`facts.py:396-421`, `projection.py:538-564`) | One fact per native attack event (the event is the delta) | N plus K (identity grants, object observation) | Yes | Its log entry restates source/target UUIDs twice more (entry plus data), the outcome (`success`, `is_hit`, `is_crit`, `outcome`), `weapon_slot`, and the children's damage (`total_damage`, `target_hp`) (`actions.py:1829-1862`) | — |
| `SpellFact` (`facts.py:433-470`, `projection.py:565-641`) | One per native version. Per-target applications are `execution_event.model_copy(...)` (`base_actions.py:2403-2414`), so every child carries the cast's declaration. | N plus K | Yes | Each of N children restates `declared_target_entity_uuids` (N UUIDs, so N² per cast), `area_geometry`, `aoe_position`, `source_position`, `name`, `behavior_id`, `effect_id`, `cast_origin`, `area_propagation`. At about 39 B per UUID in JSON, 10 targets is about 3.9 KB of declared targets per seat; 20 targets about 15.6 KB. `resolved_area_positions` is not repeated: the copy source is the EXECUTION version, the area is set on EFFECT (`base_actions.py:2714-2722`). | Per-child disclosure uses the child's own grants (`projection.py:624-626`), so a root-only declaration needs a check that the grants agree. |
| `SpellApplication` (`facts.py:424-430`) / `PlayerResolution` (`facts.py:1025-1030`) | Identity | N, mapped to seat lineage index (`projection.py:917-929, 1855-1857, 1831-1837`) | `application_id` is `uuid5(lineage, "target-application:i")` (`base_actions.py:2402-2404`) | The `application_id` UUID is sent in both `SpellFact.application` and the group's `resolutions` row. `(lineage, index)` already identifies the application inside the wire. | — |
| `DamageRequestFact` / `DamageResultFact` (`facts.py:557-581`) | One per native event; the result carries after-HP | N plus K | Yes | The result restates the request's source / target / source condition (linked by ancestry, `reduction.py:83-96`). The log's `DamageTakenLogData` restates damage and type (`events.py:5426,5462`). | — |
| `SavingThrowFact` (`facts.py:587-596`) | One per native save | N | Yes | `SavingThrowLogData` restates target, ability, success (`events.py:3092`). The parent application's `SpellSaveLogData` restates the save roll, DC, success and damage again (`actions.py:4325-4341`). | — |
| `ConditionChangeFact` (`facts.py:649-655`, `projection.py:890-899`) | Application: whole `ConditionFact` plus whole `ConditionState` plus whole `resulting_stats` (and `resulting_tile` / `resulting_item`). Removal by a seat that holds the member: the projector reads the seat's own copy and sends it back (`projection.py:2073-2080`). | N; the removal path is **C** | The application carries after-values; the per-field change of stats is not in the event | Inside one fact, `ConditionFact.condition_uuid / name / category` equal `state.*` (`actor_projection.py:177-179`); `resulting_max_hp / resulting_ac` restate `resulting_stats` for state changes (`180-183`); `consumed` appears both as the fact field and on the condition (`projection.py:898-899`). `condition.event_uuid` is a native UUID string (`projection.py:1655`), restating the node's occurrence. | The removal could be `condition_uuid` alone: the client holds the member (`reduction.py:447-452`). |
| `MovementFact` / `StepFact` / `ForcedMovementFact` / `SpatialFact` | One per native event | N plus K | Yes | One step states the mover's cell in `StepFact.to_position` (`facts.py:506-507`), in `SpatialFact.position` ×2 (left / entered, `facts.py:680`), in the mover's own `SensoryFact.observer_position`, and in other members' contact rows. A jump's `MovementFact.path` restates the steps' `disclosed_path`. | The fold needs `SpatialFact.commit_occurrence` for ordering (`reduction.py:466-479`). |

### 1c. Lineage and log kinds

| Kind | (1) | (2) | (3) | (4) | (5) |
|---|---|---|---|---|---|
| `PlayerNode` (`facts.py:1000-1022`, built `projection.py:1589-1597`, mapped `1882-1887`) | One per lineage: the final version. Identity fields are indices. | N mapped through K (`public_versions`, `public_lineages`, `disclosed_lineages`, `disclosed_turns`: identity knowledge, not client values) | Yes | `lineage` repeats `version_rows.lineages` at the node's occurrence. Every in-group edge is sent twice: `parent_lineage` on the child and `children_lineages` on the parent (both from native, `1589-1592`). `content_attributions.emitted_lineages` re-list children. | Order: log composition reads `children_lineages` order (`facts.py:182-186`), and final-version order can differ from creation order. Keep `children_lineages`; drop `parent_lineage` when the parent is in the group. |
| `VersionRows` (`facts.py:1033-1042`, built `projection.py:1806-1817`) | Every admitted version as (occurrence, lineage) | K | — | The occurrences column is mostly the contiguous range `[start_cursor, end_cursor)`, plus late disclosures of older versions (`projection.py:2152-2157`). Each node's own (occurrence, lineage) pair also appears here. | Reconnect replays stored bytes, so the identities stay stable. |
| `PlayerLineage` / `PlayerInitialization` (`facts.py:1122-1158`) | Group envelope | — | — | `generation`, `observer_uuid` and the whole `audience` (UUID tuples) on every lineage (`projection.py:2247-2251`), and again on `PlayerUpdate.audience` (`application.py:97`). `lineage` is derivable from `events[root]`. | — |
| `PlayerLogEntry` on a node (`facts.py:178-197`; `seat_log_entry` `capture.py:621-640`) | One rendered entry per native log, with no nested copies (PV2) | N, rendered per seat | — | Restates the node's fact (each UUID 3×: fact, entry, data); `source_name/target_name` repeat `data` names; `success` repeats the fact outcome; ≥34 producer lines set one rendering equal to another (e.g. `base_actions.py:917-918, 977-978`; `actions.py:4320`; `projection.py:88`). Aggregates: `SpellSaveLogData` copies the child save and damage; `MultiEntityLogData` totals and `per_target_damage` sum the children (`base_actions.py:964-970`). Progress log: Fireball / CoD combat log is 41–57 KB of 201 / 220 KB. | Plan v3.13 decided strings stay server-side (plan:694, 1058). Removing `data` needs a decision. |
| `CombatLogAppend` (`facts.py:200-206`; `application.py:81-84`) | Standalone (not node-attached) native log, rendered per seat | N | — | `generation` and `observer_uuid` on every append | Ordered by `encounter_log_index`, gated by cursor (`reduction.py:677-681`) |
| `PlayerUpdate` / `PlayerSequence` (`facts.py:1161-1177`) | Envelope per operation / saved stream | — | — | See envelope fields above | Reconnect is a replay of retained records from sequence 0 (`server/app.py:181-189, 255-269`); expiry gives `resume_unavailable` (`app.py:132-139`). |

---

## 2. Per-seat copies and compositions in this family

| State (`ProjectionState`, `projection.py:1898-1928`) | What it is | Copy of client values or knowledge? | Used for |
|---|---|---|---|
| `remembered: PlayerState` | The projector's mirror of the client (`ProjectionState` docstring) | Copy | Bodies, items, tiles and HUD patches (other families). In this family: content filter (`2069-2071`), the known-removal restatement (`2073-2080`), `apply_record_fact` for sensory facts (`reduction.py:410-418`). |
| `remembered.senses`, `remembered.perception`, `audience_composition` | Member `SensesSnapshot`s folded from **native** events (`projection.py:1474`, `audience.py:662-663`), plus the composed view and layer arrays (`audience.py:430-458`) | Perception and composition, which the human allows. It holds whole member values (contacts, effects with content, lights, cell layers). | Disclosure of every other fact (`senses.visible`, `.entities`, `.spatial_effects`) and `_world_update`. **Not** for the sensory wire. |
| `spatial_values[(observer, effect)]` (`1922`) | Each member's last-sent sighting without revision | **Copy** | Dropping no-op sightings after duration and revision are removed (`1725-1731, 1766-1781`) |
| `spatial_revisions`, `spatial_versions` (`1923-1924`) | Seat revision per (effect, native revision) | Knowledge (a count of the changes the seat was admitted) | Hiding unobserved changes; client ranking and join (`audience.py:149,161,524`) |
| `owned_spatial_effects` (`1921`) | Effects whose creating source the seat controls (`2197-2198, 2217-2218`) | Knowledge | Duration disclosure |
| `public_versions/cursors/lineages`, `disclosed_lineages`, `disclosed_turns`, `next_occurrence`, `next_log_append` | Native → seat identity | Knowledge | Index identity, cursor gates |
| `SensoryTable` (`297-320`), including `built_sightings` | A local of one group, not kept between groups | Neither (a per-group local) | Interning by `==` |

Divergence, from the code and not executed: the projector's composition folds native `owner_revision` and `duration`; the client's folds seat-renumbered and stripped values. `_join_effects` unions only rows with equal `owner_revision` (`audience.py:161`). Two members that saw native revisions 3 and 4, with no seat-visible difference, therefore join in the client view (seat revision equal) but not in the projector view. Effect-position disclosure checks (`projection.py:463-490, 709-716`) read the projector view. The docstring already records one divergence: "no contacts from admitted observations" (`projection.py:1904-1906` vs `reduction.py:186-189`).

---

## 3. Risks, by category

- **Ordering.** Within a group the fold order is occurrence order (`reduction.py:506-518`), and groups are contiguous by cursor (`reduction.py:669`). Field patches are safe under this order because each names a base the same member held at the previous occurrence. Under per-update interning, row indices must be update-scoped while `lineage_branch` / `state_before_event` slices (`reduction.py:539-549, 607-637`) still resolve them.
- **Entering and leaving view.**
  - The native code gives full values when `before` lacks an identity: light `current is None` (`sensory.py:2532-2533`); sightings `previous is None` (`2382`); contacts (`464`).
  - Leaving view: lights by removal at revision (`2544-2549`); effects keep their last observation (hidden cells retained), and are removed only when observed absent (`517`).
  - Back in view: a patch against the retained observation. The native code has it.
  - At a knowledge transition (for example the seat starts to own an effect), the current value of the newly disclosed field is read from the member snapshot. The composition holds native values, so no client copy is needed.
- **Disclosure.**
  - Removed fields (duration, native revision, undisclosed anchors) must be removed from patches. An empty patch is dropped.
  - Raw light `revision` leaks counts of unseen changes. This is true today.
  - Root-only spell declarations must not widen a child's disclosure (children are filtered by their own grants).
- **Reconnect.** The stored bytes are replayed from the initialization (full projected history from cursor 0, `application.py:39-45`). Deltas stay valid on replay. There is no current-state snapshot path, the same as today.
- **Idempotence.** The reducer is cursor-gated, not value-idempotent (`reduction.py:599-600, 669`). Patches should assign after-values, never increment: cell add / remove are set operations; light `revision` is an after-value.
- **Native consumers of `SensoryUpdateEvent`.** Changing the event (patches) touches:
  - `sensory_fold.apply_current_senses` / `prepare_sensory_delta` (shared with the AI knowledge reducer);
  - capture `_reduce_sensory_fact` (`capture.py:522`);
  - `AdmissionEvidence` (`capture.py:139-156`);
  - the recorded native archives (`event_record.py`; old recordings need reprojection, `reduction.py:645-649`).

---

## 4. Design under "event-native deltas; first sight = current state; nothing restated in an update"

### 4.1 Native changes (dnd/blocks/sensory.py, dnd/core/events.py)

1. **`SensoryUpdateEvent` light rows: added versus patched.**
   - `light_sources_added: Dict[UUID, PerceivedLightSource]`: whole value, when the observer's `previous` lacks the source.
   - `light_sources_patched: Dict[UUID, LightPatch]`: `revision` plus only the inputs that differ between `previous_values[identity]` and `values`, plus anchor disclosure changes.
   - Built where both tuples already meet (`sensory.py:2516-2531`). Shared per settlement under the same `shared` key, so equal patches are one object across observers.
   - `affected_tiles` is removed from `PerceivedLightSource` and `LightRow` (never set live). That waits on the old-recording decision.
2. **Spatial effects: added versus patched.**
   - `spatial_effects_added`: the whole perceived effect, when `before` lacks it.
   - `spatial_effects_patched: Dict[UUID, EffectPatch]`: `positions_added` / `positions_removed` masks, `visible_volume_positions` and `upper_volume_surfaces` as after-values (per-view transient), and changed scalars only, including `owner_revision` and `duration`.
   - Built in the merge, from `previous` vs the new value (`sensory.py:2380-2403`). Shared per settlement like lights.
   - Masks natively, so `projection._sighting`'s conversion (`270-282`) goes.
3. **`observer_position` only when changed:** an optional field when unchanged (`sensory.py:598`). The fold already ignores it (`sensory_fold.py:73`).
4. **`SpatialEffectChangeEvent` carries `positions_added` / `positions_removed`** instead of the two whole tuples (`events.py:3548-3549`), or in addition while rule readers migrate. Its producers know the diff.
5. **Shared reducer.** `apply_current_senses` folds added and patched entries. The AI knowledge reducer, capture and audience composition pick this up through the one reducer.

### 4.2 Projection (dnd/player/projection.py)

1. **Sightings without `spatial_values`.**
   - Remove `duration` from patches unless the seat owns the effect; map `owner_revision`.
   - An empty patch is dropped, and a fact left empty becomes None (the existing check, `1783-1791`).
   - Seat revision rule: bump on the first (effect, native revision) whose stripped patch, for any member, is non-empty. This is the same as today's `changed` test without the copy: the seat value is the fold of stripped patches.
   - Deletes `spatial_values`, `_map_sightings`' duration pass, the previous-value bookkeeping in `_public_occurrences` (`1748-1781`) and `built_sightings` / `_group_sighting` (`320, 343-351`).
2. **Content.** Sent with `spatial_effects_added` only, when the identity is not in a seat knowledge set of effect identities with content, keyed by `uuids` index. Deletes the value comparisons (`1759, 1772, 2069-2071`).
3. **One `SensoryRows` per `PlayerUpdate`.** Uuids, contacts, light rows and patches, sightings and patches, and cell tables are interned across the operation's lineages, by identity (`is`), since the native values are shared. Deletes the per-lineage tables and the `==` scans (`1979-1985`).
4. **`SpatialEffectStateFact`.**
   - REMOVED carries `removed_positions` only.
   - CREATED / FOOTPRINT_CHANGED carry the native added / removed masks restricted to the seat's visible cells, and no whole-footprint list (the sighting in the same update holds it).
5. **Spell children.** The root `SpellFact` carries the declaration. A child carries `target_entity_uuid`, the application index (owner = the resolution lineage), `propagation`, `attack_outcome` and its object-target fields. `SpellApplication.application_id` and `PlayerResolution.application_id` are replaced by the application index. Needs a check that per-child grants never disclose a declared target the root withholds (`projection.py:624-626`).
6. **Conditions.**
   - A removal of a membership the seat holds carries `condition_uuid` only; delete `_emit_bodies`' restatement (`2073-2080`).
   - An application sends `ConditionState` once: drop `ConditionFact`'s repeated name / category / uuid, `resulting_max_hp/ac` when `resulting_stats` is present, and the repeated `consumed`.
   - `event_uuid` becomes the occurrence index or is dropped (it is the node's own).
7. **Nodes.**
   - Drop `PlayerNode.lineage` (read from `version_rows`).
   - Drop `parent_lineage` when the parent is in the group (read from the parent's ordered `children_lineages`). Keep it for a group root whose parent is in an earlier group.
   - `version_rows.occurrences` becomes a range plus exceptions.
8. **Envelope.** `generation`, `observer_uuid` and `audience` once per `PlayerUpdate` / `PlayerSequence`; delete them from `PlayerLineage`, `CombatLogAppend` and `PlayerHUDPatch`.
9. **Combat log**, by index: the entry stays on its node, so the reference is the node itself.
   - Drop `source_uuid/target_uuid/source_name/target_name/success` where the node has a fact.
   - Send `verbose` / `detailed` only when they differ from the shorter rendering.
   - Drop `data` fields equal to the node's fact or to its children's entries: AttackLogData identities, outcome and damage; SpellSave's save roll, DC and damage; MultiEntity totals and `target_names`.
   - Log-only data (rolls, breakdowns, AC, DC) stays.

### 4.3 Multi-observer seats: a decision for the human

- **(A) Status quo, allowed:** per-member native deltas, and the client runs `audience.py` composition. To be consistent, the projector's composition should fold the same stripped seat values the client folds, not the native ones.
- **(B) Composed-view deltas.**
  - `apply_current_audience` already computes per fold:
    - the changed shown cells (`audience.py:386-402`);
    - contact-holder changes (`714-735`);
    - recomposed effects (`736-746`);
    - recomposed lights (`750-758`).
  - It would emit those as the seat's one sensory delta per occurrence.
  - Deletes the client composition and N member facts per occurrence (N → 1), and the projector/client divergence. Matches PV2's "the client derives nothing".
  - The composition's held view is perception state, which the human allows. It is not a client mirror kept only to diff against.

### 4.4 What this deletes

- **Copies:**
  - `ProjectionState.spatial_values`;
  - the `remembered.spatial_content` value checks (replaced by an identity set);
  - the known-removal restatement from `remembered.actors`.
- **Per-group value interning:** `SensoryTable.built_sightings`, `_group_sighting`, the `==` loops in `_shared_rows`.
- **Dead or restated fields:**
  - `LightRow.affected_tiles` and `_merged_light`'s tile union;
  - unchanged `observer_position`;
  - REMOVED `positions`;
  - per-child spell declarations;
  - both `application_id`s;
  - `PlayerNode.lineage`, in-group `parent_lineage`;
  - envelope fields per lineage and append;
  - repeated `ConditionFact` fields;
  - repeated log fields and renderings.
- **Under (B):** the client `begin_audience_composition` / `apply_current_audience` path (`reduction.py:667-674, 365`) and the per-member fact multiplicity.

### 4.5 Open risks and decisions

1. The patch-shaped `SensoryUpdateEvent` ripples to the AI knowledge reducer, capture and native recordings. Old recordings: reproject (current policy, `reduction.py:645`) or an upgrade step in `event_record.py`.
2. `owner_revision`: keep the seat counter (knowledge), or replace it. A public-occurrence revision changes the join rule (members across an unseen native bump would no longer union).
3. Spell-child disclosure parity with the root.
4. `children_lineages` order is the log contract. Keeping it and dropping in-group `parent_lineage` is the safe direction.
5. Per-update `SensoryRows` changes how saved `PlayerSequence` lineages are self-contained (`facts.py:1161-1167`). Rows would need to be per saved operation.
6. Combat-log `data` scope versus the v3.13 "strings server-side" decision.
7. Cross-family items this design touches but does not settle:
   - `_world_update`'s re-entry tile diff against `remembered.tiles` (`projection.py:1179-1192`). Under the rule, back in view sends the whole current tile.
   - Body patches (PV3).
   - `ConditionChangeFact.resulting_stats` whole after-stats.
8. Any plan built from this needs an antislop reviewer and an anti-OOP reviewer (AGENTS.md).
