# Actor / item / HUD family: event-native deltas (read-only study)

Worktree `/home/tommaso/.codex/worktrees/single-pass-propagation/dnd_engine`, head `094b528f7`.
Every file cited here is unchanged since `ead1f2458`; only `dnd/blocks/sensory.py` moved, and it is not cited.
Paths are relative to the worktree, and `file:line` refers to that head.

## 0. Findings in brief

1. **Most body changes are already event deltas, not diffs.**
   - Damage, heal, temporary HP, life, faction, condition, spatial, attack stance, item charge and sensory position travel as *facts* carrying the native after-values.
   - The client folds them field by field, or by key, in `apply_record_fact` (`dnd/player/reduction.py:369-463`).
   - The per-seat diff against `ProjectionState.remembered` is used in only six places:
     - (a) admission and re-acquisition bodies (`projection.py:1410-1418` → `2050-2059`);
     - (b) `EquipmentFact` holdings + AC (`812-818` → `2062-2066`);
     - (c) "gear observations" (`1423-1429`, `1432-1443`, built by `_gear_observation` `263-267`);
     - (d) item records (`_item_records` `171-178` → `_item_patches` `1931-1934`, `item_patch` `181-186`);
     - (e) the HUD (`hud_patch` `2133-2141`, `project_after_values` `2144-2171`);
     - (f) the value of a known condition removal (`2073-2080`).
2. **Where the native change is not already keyed:**
   - Collections sent whole: `conditions` (admission only), `controlled_items`, `visual_loadout.layers`, `ItemLook.item_effects`, `ItemState.concentration_slots`/`surface_residues`, and the sheet tuples (`resources`, `handler_details`, `compatible_item_slots`, …).
   - The native item events carry a *whole* `ItemPresentationState`: `ItemLocationStateEvent.item_state` (`dnd/blocks/base_item.py:99-101`) and `ConditionFact.resulting_item` (`dnd/core/base_conditions.py:185,234,258`).
   - The HUD economy has **no** after-value events at all.
3. **The per-seat knowledge that decides "delta vs current state" is already computed**, as keys and grants, not values:
   - `known` = keys of `remembered.actors` (`projection.py:1343`) and capture's `known_actor_uuids` (`application.py:72`);
   - event-time identity grants (`events.py:380-387`, read by `_identified` `projection.py:67-69`);
   - seat-level contact membership (`AudienceComposition.entity_members`, `audience.py:448`, maintained at `672-674`);
   - control (`audience.py:48-49`);
   - disclosed lineages and public cursors (`projection.py:1912-1919`).

   Every disclosure transform is a per-value map, so it applies to a keyed delta exactly as it does to a diff.
4. **The diff hides mismatches between the client fold and the engine fold.** Deltas expose them:
   - The client's condition fold ignores `resulting_stats.temporary_hp`/`temporary_hp_grant` (`reduction.py:452-463`); the engine fold applies them (`dnd/actor_projection.py:161-165`).
   - INTERNAL conditions produce no fact (`projection.py:897`), yet their stats change the engine body (`dnd/player/actor_projection.py:14-21`).
   - Today these reach the client only at a later re-acquisition diff, and never for a self-observed actor.
   - The D16-C replica test (`tests/player/test_emitted_update_replica.py:72-84`) compares the client fold with `remembered`. Both use the same reducer, so the test cannot see this drift.
5. **Re-acquisition is per observer, not per seat:**
   - `acquired = entity_contacts_changed − member` per observer (`capture.py:808`);
   - it bypasses the known check through `| acquired` (`capture.py:877`).

   A 26-observer seat re-admits a body whenever *any* member re-acquires it, even while another member still sees it. Using the seat-level transition from `entity_members` is free knowledge.
6. **One open decision for the human** (§9.8): what re-entry sends. Either:
   - (a) the current mutable state (strict reading of "entering knowledge gets current state"; static birth fields are never re-sent), or
   - (b) exact, via a per-seat reference to the immutable engine `ActorState` at the lapse.

---

## 1. Today's pipeline for this family

| Stage | What | Where |
|---|---|---|
| Shared engine replica | `CaptureCheckpoint.actors` (seat-independent `ActorState` fold, once per version for every audience) | `capture.py:158-176`, `advance_capture` `784-855` (`apply_actor_fact` at `840`) |
| The fold itself | `apply_actor_fact`: per event family, the after-values it writes | `dnd/actor_projection.py:64-139`; birth `20-41`; previous holder `142-154`; stats `157-165` |
| Admission evidence | Per version: the actors, holders' contacts and positions of the candidates, observed and acquired identities, all *before* that event's own change | `capture.py:821-834` |
| Admissions | First knowledge (`candidates ∪ observed` not known), plus `acquired` unconditionally | `_derive_admissions` `capture.py:858-896` |
| Per-seat engine replica | `ProjectionState.actors` (`ActorState`), folded again per seat in the walk | `projection.py:1910`, walk `1410-1443` |
| Full body at admission | `_public_actor` → `actor_changes(None, …)` + `_item_records` | `projection.py:189-204`, `1410-1418` |
| Facts | `_project_fact` (Damage/Heal/TempHP/Life/Faction/Condition/Spatial/Equipment/ItemCharge/…) | `projection.py:419-914` |
| Disclosure passes | Lineage-dependent: after the whole walk | `projection.py:1598-1637` (bodies `1627-1630`) |
| Seat cursors | `_public_occurrences`: conditions and item effects get seat cursors; duration only if owned | `projection.py:1653-1689`, `1888-1891` |
| Diff and fold | `_emit_bodies`: patch vs `remembered.actors`/`items` in client order, then `observe_body` / `apply_record_fact` into `remembered` | `projection.py:2034-2084` |
| Client fold | `observed_actor`, `apply_item_patches`, `observe_body`, `apply_record_fact`, `apply_hud` | `reduction.py:148-179`, `369-463`, `566-585` |
| HUD | `_snapshot_sheets` (live evaluation, once per op for all players) → `snapshot_player_hud` (per seat filter) → `hud_patch` vs `remembered.hud_snapshot` | `session.py:121-172`, `466-485`; `projection.py:2087-2171` |

---

## 2. `PlayerActor` / `ActorChanges` fields

Types: `PlayerActor` `facts.py:324-349`, `ActorChanges` `352-381`.

Abbreviations:
- **adm** = admission body (first knowledge or re-acquisition);
- **diff** = `actor_changes(remembered, after)` (`projection.py:207-254`);
- **fact** = a native after-value already sent as a fact and folded by `apply_record_fact`.

| Field | (1) Sent now / granularity | (2) Computed | (3) Native keyed source at event arrival | (4) Seat knowledge / disclosure | (5) Risks |
|---|---|---|---|---|---|
| `name`, `character_body_id`, `creature_content_ref`, `appearance`, `structural_base_size`, `manifestation` | adm only; whole scalar or whole `AppearanceConfig` | diff (always unchanged after the first) | `EntityCreatedEvent` (`events.py:889-973`) via `actor_from_birth` (`actor_projection.py:20-41`). **No event ever rewrites them** (`apply_actor_fact` `64-139` has no case). | Anyone the event identifies; `name` also feeds log names (`application.py:67`) | None. They are static: send once at first knowledge, never again. |
| `visual_loadout.active_weapon_set` | Inside the whole `VisualLoadout` (adm, `EquipmentFact`, gear); keyed via `AttackFact` | diff of the whole loadout (`218-219`); `AttackFact` folded at `reduction.py:419-423` | `AttackEvent` slot/source kind (`actor_projection.py:91-95`); `EquipmentEvent.active_weapon_set_after` (`dnd/blocks/equipment.py:60-63`, written at `equipment.py:1302,1856,1859,1926`) | Identified owner | — |
| `visual_loadout.layers` (`VisualItem` slot/item/item_id/is_lit) | Whole tuple inside the whole loadout | diff (adm, `EquipmentFact` `817`, gear `259`, `1428`, `1443`) | `ItemLocationStateEvent` `location`/`owner_uuid`/`equipment_slot`/`item_state.is_lit` (`base_item.py:91-136`, writer `413-470`; entity path `entity.py:4865`, AC at `4905`): **keyed** (slot → item). `ItemHoldingsReleasedEvent` (`base_item.py:82-88`). The previous holder's removal comes from the shared fold (`actor_projection.py:142-154`). `is_lit` comes from the condition's `resulting_item` (`base_block.py:1650-1656`). | Everyone who identifies the holder sees the layers. A non-controller gets the equipped looks only (`projection.py:176-178`). | Layer order follows the engine dict keyed by slot (`actor_projection.py:129-134`), so the client must fold by slot. The previous holder's removal must reach the seats that know *that* holder (today `1423-1429` uses the seat's contacts). |
| `normal_hp`, `temporary_hp` | adm (whole body) **and** facts (scalar replace) | fact: `reduction.py:424-442`, `452-456`; diff only at adm | `DamageAppliedEvent.resulting_normal_hp/resulting_temporary_hp` (`events.py:5503-5508`, writer `entity.py:3616`); `HealEvent` (`events.py:5657-5664`, writer `entity.py:3918`); `TemporaryHitPointsChangedEvent` (`5527-5533`, writer `blocks/health.py:796`); `LifeStateChangeEvent.normal_hit_points` (`5861`, writer `entity.py:2583`); `resulting_stats` (`base_conditions.py:183,232,256`) | The target must be identified (`projection.py:704-706`, `773-775`, `781-784`, `789-790`). **No HP hiding:** any identifying seat gets exact HP. | The client ignores `resulting_stats.temporary_hp` (`reduction.py:452-463` vs `actor_projection.py:161-165`). INTERNAL conditions' stats are dropped (`projection.py:897`). |
| `maximum_hp` | adm + condition fact | fact `reduction.py:457-458` | `resulting_max_hp` / `resulting_stats` (`base_conditions.py:180-183`, `253-256`) | Same as above | INTERNAL drop, as above |
| `temporary_hp_grant` | adm + `TemporaryHitPointsFact`; cleared when temporary HP reaches 0 | fact `reduction.py:429,435,438` | `TemporaryHitPointsChangedEvent.grant` (`events.py:5533`), `resulting_stats.temporary_hp_grant` | Identified | The client's condition fold does not apply it (engine does, `actor_projection.py:162`) |
| `life_state`, `remains_disposition` | adm + `LifeFact` | fact `reduction.py:439-442` | `LifeStateChangeEvent` (`events.py:5847-5865`) | Identified (`projection.py:789-799`) | — |
| `armor_class` | adm + `EquipmentFact.changes["armor_class"]` (whole after-value from the per-seat replica, `projection.py:817-818`) + condition fact | diff (`EquipmentFact` at `2064`); fact `reduction.py:459-460` | `ItemLocationStateEvent.entity_armor_class_after` (`base_item.py:132-136`); `resulting_ac` / `resulting_stats` | Identified owner | INTERNAL drop |
| `conditions` | adm: **whole tuple** (any difference resends all of it, `230-231`). Changes go through `ConditionChangeFact`, which is keyed. | adm diff; fact keyed (`reduction.py:447-463`, `482-487`) | Application / removal / state-changed events with `condition_state` (`base_conditions.py:168-258`), keyed by `condition_uuid` → `ConditionFact` (`actor_projection.py:168-188`). The writer already de-duplicates against its last publication (`conditions.py:2089-2098`). | Non-INTERNAL only (`dnd/player/actor_projection.py:14-21`, `projection.py:897`). Duration only to the controller (`1653-1661`). Cast lineage of concentration slots only if disclosed (`1279-1295`). `event_uuid` only if public (`1655`). Cursor remapped (`1659`). | Re-acquisition after any condition change resends every `ConditionFact`, each with its `state` and `resulting_stats`. |
| `last_visual_position` | adm, from the witness contact (`capture.py:892-894`); then client-derived | Folded from sensory contacts and observer position (`reduction.py:410-418`), own entry (`390-392`), cleared on departure (`380-383`) | Not engine state: per-seat perception (`SensoryUpdateEvent.entity_contacts_changed`, `events.py:3382`) | Composed contacts (`audience.py:714-735`) | Keep as knowledge; it also decides `occupancy_layer` disclosure. |
| `controlled_items` | adm / `EquipmentFact` / gear: **whole tuple** (`projection.py:204`, `259-260`); `ItemChargeFact` destroyed removes by key (`reduction.py:397-403`) | diff (`234-235`) | `ItemLocationStateEvent` (INVENTORY/EQUIPMENT/FLOOR/DESTROYED, `owner_uuid`): keyed by item. Holdings released; `ItemResourceChangeEvent.item_destroyed` (`base_item.py:1639`) | **Controller only** (`projection.py:204`, `259-260`) | A naive inventory delta to a non-controller leaks item existence. Order rule: the engine keeps an item's position when updated and appends a new one (`actor_projection.py:127-128`). |
| `occupancy_layer` | adm (only if controlled or position known, `projection.py:202-203`) + `SpatialFact` | fact `reduction.py:388-389` | `SpatialChangeEvent.occupancy_layer` (`events.py:3690`) | Arrival or departure allowed (`projection.py:859-879`) | — |
| `resolved_size` | adm + condition fact | fact `reduction.py:461-463` | `resulting_stats.resolved_size` (`types/actor.py:96`) | Identified | INTERNAL drop |
| `faction` | adm + `FactionFact` | fact `reduction.py:375-378` | `EntityFactionChangedEvent.faction_after` (`events.py:976-983`, writer `entity.py:1791`) | Identified **and** located (`projection.py:785-788`) | — |
| `present` | Never sent as a value (`_public_actor` leaves the default `True`, `facts.py:347`); client-only | `SpatialFact` terminal (`reduction.py:380-383`); `_emit_bodies` skips non-present bodies (`2052`) | `SpatialChangeEvent.terminal_release` (`events.py:3686`) | Witnessed departure (`projection.py:844-849`) | Becomes the knowledge set `departed`. |
| `spatial_disposition` | adm + `SpatialFact` entry + condition stats | fact `reduction.py:385-387`, `453-454` | `ENTITY_ENTERED` (`actor_projection.py:79-80`), `resulting_stats.spatial_disposition` (`types/actor.py:99`) | Identified | — |

---

## 3. Carriers and their payloads

| Payload | Now | Computed | Native keyed? | Knowledge / disclosure | Risk |
|---|---|---|---|---|---|
| `PlayerObservation` (`facts.py:384-393`) | adm + gear observations; `changes`, `contact`, `items` | Diff in `_emit_bodies` (`2050-2059`); dropped when empty | adm = the engine state at version (`capture.py:828`), which is the "current state from the engine" | Witness choice (`capture.py:882-893`); `contact` is perception | Per-observer `acquired` (`capture.py:808`, `877`) |
| `EquipmentFact` (`facts.py:639-646`) | Whole `visual_loadout`, `controlled_items`, `armor_class`, plus a record for **every** inventory item (controller) or every equipped item (others), then diffed | `projection.py:812-818` → `2062-2066` | Yes: (owner, item, location, slot, AC after, weapon set after) on the events listed above | `_identified(owner)`; control decides inventory | Resends all item records per change; dropped only by the diff |
| `ConditionChangeFact` (`649-655`) | Keyed upsert or remove of one `ConditionFact` | `_project_fact` default case (`890-899`) | Yes | As for `conditions` above. A known removal carries the value the seat holds (`2073-2080`); the key alone suffices (`reduction.py:485`). | — |
| `ItemEffectChangeFact` (`658-665`) | Keyed edge (item, effect, event type) | `projection.py:891-896` | Yes, but without the effect's value | Held or observed item (`380-389`) | **Not folded by the client** (no case in `reduction.py`); the effect itself travels in a whole `ItemLook` patch from the gear observation |
| `ItemChargeFact` (`706-715`) | Keyed after-values (charges, stack, destroyed) | `projection.py:808-811`; fold `reduction.py:393-409` | Yes: `ItemResourceChangeEvent` (`base_item.py:1615-1642`, writers `1394`, `1550`) | Controller only | — |

---

## 4. Items

Types: `PlayerItem` `facts.py:286-295`, `ItemPatch` `298-305`, `ItemLook` `209-221`, `ItemProfile` `224-256`, `ItemState` `259-283`.

| Component / field | Now | Computed | Native source | Knowledge / disclosure | Risk |
|---|---|---|---|---|---|
| `ItemLook` static part (`item_id`, kind, visual name/variant, equipped policy, radii) | Whole look component the first time; again whenever any look field differs | `item_patch` component diff (`projection.py:181-186`) vs `remembered.items` | `item_state` whole (`base_item.py:446`); static per instance | Everyone who sees the item equipped; the controller sees the whole inventory (`171-178`) | — |
| `ItemLook.item_effects` | **Whole tuple** inside the look | Same diff | Whole `resulting_item` (`base_block.py:1656`, `1891`; floor path compares its prior at `conditions.py:2090-2093`); the keyed edge is `ItemEffectChangeFact` (value missing); `effect_uuid` is the key (`item_types.py:141`) | Duration only if owned (`projection.py:1670-1674`); cursor remapped | A non-owner's duration tick: the diff drops it today; an unfiltered delta would resend an identical value. |
| `ItemProfile` | Whole, once (controller) | Component diff | Static definitional values inside `item_state` | Controller only | Static: send once at first control. |
| `ItemState` `charges`, `stack_count` | `ItemChargeFact` (keyed) **and** in the whole `ItemState` of later records | fact + diff | `ItemResourceChangeEvent` (keyed) | Controller | — |
| `ItemState` other fields (`concentration_slots`, `surface_residues`, `is_lit`, `integrity`, …) | Whole `ItemState` component | diff | Whole snapshots only (`item_state`, `resulting_item`) | Controller; slot cast lineage only if disclosed (`1279-1308`) | Whole-tuple collections |
| `VisualItem` / `VisualLoadout` (`308-321`) | See §2 | — | — | — | `is_lit` is duplicated in the layer and in `ItemState` |
| `PlayerState.items` (`1197`) | Every item the seat has ever seen; removed only when destroyed (`reduction.py:399`) | — | — | Knowledge = the keys plus a tier (look or controlled) | A look can go stale while out of sight (lapse; §8) |

---

## 5. HUD and initialization

| Payload | Now | Computed | Native source | Knowledge | Risk |
|---|---|---|---|---|---|
| `PlayerHUDSnapshot` (`facts.py:117-125`) | Never on the wire; the per-seat diff base is `remembered.hud_snapshot` (`1200`) | `snapshot_player_hud` (`session.py:121-135`) from `_snapshot_sheets`, which is evaluated **once per op for every player** (`session.py:482`) | Pull evaluation of the live engine (`session.py:138-172`) | Sheets for controlled actors only (`135`) | — |
| `PlayerHUDPatch` (`161-175`) | Revision always; `initiative` and `sheet_order` whole when changed; the changed sheets | `hud_patch` vs `remembered.hud_snapshot` (`projection.py:2133-2141`); `boundary` maps the revision (`2152-2163`); folded into `remembered` (`2170`) | `initiative`: `EncounterStartEvent.initiative_order` (`events.py:5738`), filtered by the **live** senses (`session.py:127-134`) | Control is static per projection (`projection.py:2214`; `reduction.py:657-658`) | Initiative visibility reads live senses, not the seat's composed view. |
| `SheetChanges` fields (`128-152`) | Whole field per changed field (`resources`, `handler_details`, `compatible_item_slots`, `class_levels`, `prepared_spell_selections` are whole tuples) | `sheet_changes` (`projection.py:2087-2130`) | **No economy after-values:** `ActionCostsCommittedEvent` carries only named costs (`events.py:5547-5554`, writer `base_actions.py:2197`); `TurnStartEvent` carries turn-start counts (`5789-5792`); a handler toggle emits no event (`session.py:598-607`); `compatible_item_slots` is rule-derived (`session.py:170-171`). Progression after-values exist: `SpellbookChangedEvent` (`5595`), `SpellPreparationChangedEvent` (`5604`), `PermanentFeatureUsedEvent` (`5572`), `SpellMasteryStudiedEvent` (`5587`). | Controlled only | Sheet `normal_hp`/`maximum_hp` duplicate the body fields |
| `PlayerInitialization` (`1143-1158`) | `observations` = startup admissions (full bodies); `hud` = full HUD (`application.py:44-45`) | `begin_projection` (`projection.py:2179-2208`) | Admission evidence | — | Unchanged by this design: entering knowledge means current state. |

---

## 6. Per-seat knowledge and disclosure applied to deltas

**Already computed (keys and grants only):**
- `known` actors: `projection.py:1343` and `application.py:72`;
- held condition keys: `projection.py:1346-1349`, used at `1515`;
- departed actors: `remembered.actors[x].present`;
- event-time identity and location grants: `events.py:380-395`, read at `projection.py:67-69`, `92-94`;
- seat composed contacts and `entity_members`: `audience.py:448`, `672-674`, `714-735`;
- control: `audience.py:48-49`;
- disclosed lineages: `projection.py:1598`, `1913`;
- public versions and cursors: `1914-1919`.

**Disclosure transforms are pure per-value maps.** Each applies unchanged to every element of a keyed delta:
- `_public_actor` field selection (`189-204`);
- `_item_records` component selection (`171-178`);
- `_disclosed_condition` / `_disclosed_item` / `_disclosed_slots` (`1279-1308`);
- `_public_condition` / `_public_item_effects` (`1653-1689`).

One requirement carries over: lineage disclosure is final only for the whole group, so deltas must be built in the walk and disclosed after it, as observations are today (`1627-1630`).

**The one semantic difference: a diff runs *after* disclosure.**
- A native change that only touches a hidden part produces nothing today. Examples: an item-effect duration for a non-owner, or a slot whose cast lineage is undisclosed.
- An unfiltered event delta would resend an identical public value: a redundant send, not a leak.
- Conditions already behave like that today: `ConditionChangeFact` is sent without a diff.
- The exact fix needs no copy: the shared change record names the fields it changed, and the projector drops a delta whose changed fields are all hidden for the seat.

---

## 7. Readers of `remembered` actors, items and HUD other than the diff

| Reader | Needs | Replace with | Deletable |
|---|---|---|---|
| `projection.py:1343` `known` | Keys | `known: set[UUID]` | yes |
| `projection.py:1346-1349`, `1515`, `1520` held conditions | Keys (the values only seed `change_membership` on a local dict) | `held: dict[UUID, set[UUID]]` | yes |
| `projection.py:1523` `apply_sensed_fact(…, known)` | Keys | `known` | yes |
| `projection.py:2051-2053` `present` | Flag | `departed: set[UUID]` | yes |
| `projection.py:2074-2080` known removal value | The member value (to avoid disclosing the absent recipient's stats) | The removal key alone (`reduction.py:485` pops by key); the client already has the name | yes |
| `application.py:67` names for log rendering | Names | Engine birth names restricted to `known` (static, `actor_projection.py:23`) | yes |
| `application.py:47`, `94` → `admitted_content` (`content_composition.py:99-132`, reads `actors`/`items` at `103-106`) | Content ids | `remembered.content` (already kept) plus the engine fold over `known` | yes |
| `projection.py:2167-2170` HUD | Previous display | A seat-independent per-actor previous sheet (§9) | yes |
| `devtools/player_server_acceptance/performance.py:271` | `len(actors)` | `len(known)` | yes |
| `server/worker.py:89-98` | `viewing_audience`, `content` only | — | n/a |
| Tests: `test_emitted_update_replica.py:72-84`, `test_recorded_boundary.py:39-46`, `test_foreign_sensory_capture.py:235-238` | Equality with `remembered` | An engine-equality replica (§9.10) | rewrite |

---

## 8. Risks

- **Ordering.**
  - An admission is applied before the event at the same version (`projection.py:1410`). The admitted value is the before-state (`capture.py:827-840`), so a delta at that version still applies on top.
  - The previous holder's removal (`actor_projection.py:142-154`) must be emitted at the location event's version.
  - Today's patches depend on every earlier row of the group (`occurrence_order`, `reduction.py:506-518`). Self-contained deltas are more robust to `lineage_branch` (`reduction.py:607-637`) and `state_before_event` (`539-549`).
- **Losing and regaining sight.**
  - Nothing is sent on loss, now and in the design.
  - While unseen, undisclosed events change the engine body; the seat must learn of them at re-entry.
  - Today the diff does this. A copy-free design needs one of the options in §9.8.
  - Per-seat re-entry should use `entity_members` ∅ → non-∅, not the per-observer `acquired` (`capture.py:877`).
- **Disclosure leaks.**
  - Inventory deltas must never reach non-controllers (`projection.py:204`). A foreign inventory → equipment move appears to them as a new layer plus the item's look entering knowledge.
  - Concentration-slot lineage and condition/effect durations need the same maps as today.
  - Option (a) re-entry only reveals what a full re-send reveals. A per-field cursor variant would leak "this field was touched while unseen" (for example damage then a full heal) and is rejected.
- **HUD.**
  - Sheets are evaluated per op and diffed per seat.
  - Every seat that controls an actor receives the same sheet, because the evaluation is shared (`session.py:482-484`). The diff can therefore be per actor and seat-independent.
  - Fully event-native sheets need native economy writers (§9.6).
- **Reconnect.**
  - The SDK resumes from its consumed sequence and drops duplicates (`sdk/python/src/dnd_player/transport.py:370-457`, guard on sequence ≤ consumed).
  - Deltas are as valid as today's patches under journal replay.
  - Without a client copy, a *fresh-snapshot* reconnect could not rebuild last-known stale bodies for out-of-sight actors; it would send current values and leak. Reconnect must stay journal replay, as it is now.
- **Idempotence.**
  - Field replace and keyed upsert or remove are idempotent.
  - An inventory add must be "append if absent, keep position if present", the engine dict rule (`actor_projection.py:127-128`).
  - Layers are keyed by slot.
- **Fold mismatches.** The two in §0 item 4 must be fixed, or a delta-only client drifts silently:
  - temporary HP and its grant via `resulting_stats`;
  - INTERNAL-condition stats.

  It is unverified whether any rule changes temporary HP *only* through `resulting_stats`.
- **Schema.** The wire types change, so the SDK protocol identity and digest change (`sdk/protocol/README.md:274-281`).

---

## 9. Design: event-native deltas for actors, items and the HUD

### 9.1 Principle

The family's change is a property of the event, not of the seat:
- the shared engine fold computes it once per event, at arrival;
- the seat contributes only its knowledge (known, identified, controlled, disclosed) and its value maps.

### 9.2 Seat-independent change record (native, in the shared fold)

- `apply_actor_fact` (`dnd/actor_projection.py:64-139`) already dispatches per event family and writes a fixed set of fields per case. It should also return that case's change, as an explicit frozen record. There is no diffing and no `getattr` over fields.
- `ActorChange` (a leaf type in `dnd/types/actor_facts.py`) holds:
  - optional scalar after-values (HP, temporary HP and grant, maximum HP, AC, life, remains, faction, size, disposition, occupancy, weapon set);
  - `conditions_set` / `conditions_removed` (by `condition_uuid`);
  - `inventory_added` / `inventory_removed`;
  - `layers_set` (slot → item, `is_lit`) / `layers_removed`.
- `ItemChange` holds:
  - `record`, only for a first sighting;
  - `look_effects_set` / `look_effects_removed` (by `effect_uuid`);
  - `state` field after-values; whole-snapshot events are compared component by component against the shared fold's previous item, explicitly, once per event;
  - the changed field names, used for hidden-only dropping.
- **Where:** `advance_capture` (`capture.py:836-840`) stores the records in `AdmissionEvidence`, keyed by version and shared by every seat.
- The per-seat `ProjectionState.actors` replay stays only for the in-walk disclosure reads (`_held_item_disclosed`, the source-condition checks, `LifeFact` preserved items).
- Optional, cheaper writers: the condition writer already holds its previous publication (`conditions.py:2089-2098`), and `publish_location_state` (`base_item.py:413-470`) knows the previous location. Both could emit the item change directly.

### 9.3 Per-seat decision (in `_project_nodes`, replacing `_emit_bodies`' diff)

For each event that changes actor X:
- X is known and identified (`_identified`): emit the disclosed `ActorChange`. That is today's facts, plus `HoldingsFact` and the stats-only delta for INTERNAL conditions.
- X is not known and is admitted: emit the full first record. This is today's first observation; static birth fields go only here.
- X is known, not identified, and changed: mark X lapsed (§9.8).
- Seat-level re-entry: per §9.8.
- Otherwise: nothing.

Items follow the same rule, with a tier per item uuid (look, or controlled). Becoming controlled sends the profile and state.

### 9.4 Wire

- `ActorChanges` keeps scalar replace semantics.
  - Its `conditions` / `controlled_items` / `visual_loadout` become first-record-only, whole.
  - Their changes travel as keyed fields (`conditions_*` via `ConditionChangeFact`; `inventory_*`; `layers_*`; `active_weapon_set`).
- `EquipmentFact` becomes `HoldingsFact`, carrying:
  - owner and item;
  - an inventory add or remove (controller only);
  - a layer set or clear;
  - `armor_class_after` and `active_weapon_set_after`;
  - the item's first record if it newly enters knowledge.
- `ItemEffectChangeFact` gains the effect value (upsert) and is folded by the client.
- `ItemPatch` remains for first records and tier upgrades only.
- A known `ConditionChangeFact` removal carries the key alone.
- `SheetPatch` stays.
  - Optional: key `resources` by `key`, `handler_details` by `uuid` (`action_types.py:28`), and `compatible_item_slots` by item uuid.

### 9.5 Client fold (`reduction.py`)

- `apply_record_fact` gains:
  - `HoldingsFact`: inventory "append if absent", layers set by slot;
  - `ItemEffectChangeFact`;
  - the temporary HP and grant from `resulting_stats`.
- `observe_body` and `apply_item_patches` stay for first records.

### 9.6 Native changes, by size

| Change | Size |
|---|---|
| Change records returned by `apply_actor_fact` | ~15 explicit cases |
| Explicit component compare for the two whole-item events, once per event | Small |
| Emit a stats delta when an INTERNAL condition has `resulting_stats` | One case at `projection.py:897` |
| Seat re-entry from `entity_members` instead of `| acquired` | Small; `capture.py:877`, `audience.py:672-674` |
| HUD option A: a per-actor `previous_sheets` beside `_snapshot_sheets` (`session.py:482`); one `SheetPatch` per actor, shared by every controlling seat; full sheet at initialization | Small. **Still a pull diff**, but seat-independent. |
| HUD option B (fully event-native): an action-economy after-value event from `dnd/blocks/action_economy.py`, which has many mutation methods (consume / recharge / reset / recover / set resource / capacity contributions, `175-212`, `732-766`, `1072-1313`), plus capacity changes driven by modifiers, a handler-toggle event, and recomputing `compatible_item_slots` per inventory event | Large; ask the human |

### 9.7 Deletes

- `actor_changes` in `_emit_bodies` (`projection.py:2050-2066`); it remains only as the first-record builder.
- `item_patch` / `_item_patches` (`181-186`, `1931-1934`).
- The resend of every item record per `EquipmentFact` (`817-818`).
- `_holdings` / `_gear_observation` (`257-267`) and their call sites (`1423-1443`).
- The known-removal value substitution (`2073-2080`) and the `known_removals` value use.
- The `| acquired` bypass (`capture.py:877`).
- `remembered.actors` / `items` / `hud_snapshot` as diff bases and as fold targets (`2058`, `2082`, `2167-2170`). They are replaced by key sets (`known`, `departed`, `held`, item tiers).
- `hud_patch` against the per-seat snapshot.

### 9.8 Decision needed from the human: re-entry after unseen changes

- **(a) Strict.** Re-entry is "entering knowledge", so send the current *mutable* fields.
  - Static birth fields are never resent.
  - This needs no per-seat values.
  - Bytes return for re-entries that are really unchanged; whether that breaks the PV3 gate depends on how many of the 234 Sleet re-acquisitions are seat-level, which needs a measurement. Per memory, ask before probing.
- **(b) Exact.** At the first undisclosed change to known X, the seat keeps a *reference* to the immutable engine `ActorState` (or item state) before that change.
  - At re-entry, public(ref) vs public(now) gives an exact patch, then the reference is dropped.
  - The values held are engine values, frozen and shared, and only for lapsed records. The human must say whether that counts as a "per-seat copy".

### 9.9 Open risks

- Hidden-only deltas need the changed-field filter, otherwise they are redundant sends.
- Group-final lineage disclosure: build deltas in the walk, disclose after it.
- Previous-holder routing.
- Reconnect must stay journal replay.
- SDK digest.
- Whether rules change temporary HP only through `resulting_stats` (unverified).
- HUD remains pull-evaluated unless option B is chosen.

### 9.10 Gate

- Replace the D16-C replica with engine equality. For every known, present, tracked actor and item, the client fold of the emitted updates must equal the public projection of the shared engine fold. Lapsed records are checked at re-entry.
- No body or item bytes for unchanged re-entries under option (b), or the measured option (a) bytes.
- Every update ≤100 KB (plan PV2).
- A plan derived from this study must add the antislop and antiOOP reviewers (`AGENTS.md`).
