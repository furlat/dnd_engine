# Bodies, items and HUD under the no-memory rule (read-only rescan)

Worktree `/home/tommaso/.codex/worktrees/event-native-deltas/dnd_engine`, head `55bf034cc`.
`git diff 094b528f7 HEAD -- dnd/` is empty, so the line numbers of the earlier study still hold; every one cited below was re-read at this head.
Paths are relative to the worktree. Nothing was run.

**The rule (human, authoritative).** Publication keeps no remembered state.
1. Perceived or known before and after an event: the event's own change, disclosed.
2. Entering perception or knowledge: its current state in full. There is no memory of earlier sightings.
3. Leaving: nothing.

Per-seat server knowledge is only what is perceived or disclosed now, plus which static content ids were sent. No client values, no last-seen stamps.

What changes against the earlier study (`agent_docs/event_native_deltas_2026-10-18/actors_items_hud.md`):
- D1 is decided as (a). Option (b), last-seen revisions and references to lapsed states, is ruled out.
- D4(b), a per-actor previous sheet, is ruled out as publication state.
- "known" stops being a monotone set: it becomes "perceived now".

---

## 0. Findings in brief

1. **Per-seat state for this family shrinks to three things:**
   - the seat's composed perception, which already exists (`AudienceComposition.entity_members`, `audience.py:448`; maintained at `672-674`);
   - control (`audience.py:48-49`);
   - two monotone *static-content* sets: actor uuids whose birth part was sent, and item uuids whose static look and profile were sent.

   `remembered.actors`, `remembered.items` and `remembered.hud_snapshot` stop being server state.
2. **Bodies:** almost every change already travels as an event after-value (Damage, Heal, TempHP, Life, Faction, Attack stance, Spatial, Condition, ItemCharge). Only these still need a diff or a whole resend:
   - the re-acquisition body;
   - `EquipmentFact`;
   - the gear observations;
   - item records;
   - the HUD;
   - the known-removal value.

   All six disappear or become keyed changes.
3. **The rule forces exactness that the diff used to hide.** Three fold disagreements become permanent drift for any continuously perceived actor (always for one's own actors) unless the change record comes from the engine fold's own case:
   - temporary HP and its grant carried in `resulting_stats`;
   - the stats of INTERNAL conditions;
   - a destroyed equipped item's layer seen by non-controllers. This one is newly found.
4. **Re-acquisition per observer (`capture.py:808`, `877`) disappears by definition.** Entering is a seat-level transition of the composed contacts. The cost: every genuine seat-level re-entry sends the full current mutable body. Bytes are not measured; ask before probing.
5. **HUD.** Eleven sheet field groups change with no event that carries their value (§4.1). Under the rule the HUD must become event-native, which needs native writers. The cheapest native form still compares the actor with its own last publication inside the engine (the `publish_owner_state` pattern, `conditions.py:2084-2110`). The human must say whether that counts as event-native.

---

## 1. Per kind: what each becomes, and what is deleted

### 1.1 Per-seat knowledge that remains (and nothing else)

| Knowledge | What it is | Where it exists today |
|---|---|---|
| perceived actors | `controlled` ∪ the seat's composed entity contacts (any kind of contact; today's admission uses `holders`, `capture.py:881-886`) | `audience_composition.entity_members` / `view.entities` (`audience.py:448`, `672-674`, `714-735`); the walk folds it at `projection.py:1474` |
| control | `PlayerAudience.controls` | `audience.py:48-49` |
| actor static ids sent | the uuids whose birth fields went out | new set; replaces the keys of `remembered.actors` (`projection.py:1343`, `application.py:67`, `72`) |
| item static ids sent | the uuids whose static look went out, and the uuids whose profile went out | new sets; replace `remembered.items` (`reduction.py:157-170`) |
| event-time disclosure | identity and location grants on the event | `events.py:380-395`, accumulated in `2383-2405`, read by `_identified` `projection.py:67-69` |
| lineage disclosure and cursors | already per-seat knowledge (other study) | `projection.py:1598-1637`, `1653-1689` |

The identity grant is the native "perceived at this event": an observer subscribed to the cell identifies a participant "when the participant is among that observer's contacts" (`encounter.py:109-137`). So *perceived-before* (composed contacts at the event's entry) and *disclosed-at* (`_identified`) agree, except where identity accumulates from parent versions (`events.py:2397-2404`).

**Per-seat decision for an event e that changes actor X:**
- **Change:** X is perceived at e's entry (controlled, or in the composed contacts) and `_identified(e, X)`. Emit X's change for e, disclosed (§3).
- **Entering:** X enters the composed contacts, which happens at a sensory fact, or at initialization or control start. Emit the full current record, read from the shared evidence row at that version (`capture.py:821-834`).
- **Nothing:** every other case, including leaving.

### 1.2 `PlayerActor` / `ActorChanges` fields (`facts.py:324-349`, `352-381`)

| Field | Under the rule | Event change from | Entering | Deleted with it |
|---|---|---|---|---|
| `name`, `character_body_id`, `creature_content_ref`, `appearance`, `structural_base_size`, `manifestation` | **Static content keyed by actor uuid, sent once per seat.** No event writes them: `apply_actor_fact` has no case for them (`actor_projection.py:64-139`); set at birth (`20-41`). | — | Only if the uuid is not in "actor static sent". A literal "full body" would resend about 300 B of appearance each time (`types/appearance.py:11-…`). | The diff on them (`projection.py:209-216`, `241-242`) |
| `normal_hp`, `temporary_hp`, `temporary_hp_grant`, `maximum_hp`, `armor_class`, `life_state`, `remains_disposition`, `resolved_size`, `spatial_disposition`, `faction`, `occupancy_layer` | Mutable scalars: the event change (scalar replace) | §2 table | Full current values | Their lines in `actor_changes` (`217-254`) as a diff |
| `visual_loadout.active_weapon_set` | Scalar | `AttackEvent` (`actor_projection.py:91-95`); `EquipmentEvent.active_weapon_set_after` (`blocks/equipment.py:60`; writers `1302`, `1856`, `1859`, `1926`) | Full | The whole-loadout resend in `EquipmentFact` (`projection.py:812-818`) |
| `visual_loadout.layers` | **Keyed by slot:** set (slot → item, `is_lit`) or removed | Item location, holdings-released, resource-destroyed, FLOOR events (§2) | The whole tuple | `_holdings` (`257-260`) |
| `conditions` | **Keyed by `condition_uuid`:** upsert on application, field patch on state change, key-only removal | Condition events (§2) | The whole tuple, as membership state only. Drop the `resulting_*` after-values, which are change payloads, not membership. | The whole-tuple diff (`230-231`) |
| `controlled_items` | **Keyed by item uuid, controller only:** append if absent, remove | Item location and holdings events; `ItemResourceChangeEvent.item_destroyed` | The whole tuple (controller) | `234-235`, `_holdings` |
| `last_visual_position` | Perception, not body. It stays derived from contacts (`reduction.py:410-418`). | SensoryFact contacts | Witness contact position (`capture.py:892-894`) | — |
| `present` | No server state. The engine pops the actor at terminal release (`capture.py:841-848`), so it cannot re-enter. | `SpatialFact.terminal_departure` (`reduction.py:380-383`) | — | The `present` guard (`projection.py:2051-2053`) |

### 1.3 Items (`facts.py:209-321`)

| Type / part | Under the rule |
|---|---|
| `ItemLook`: `item_id`, `item_kind`, `visual_item_name`, `visual_variant_id`, `equipped_visual_policy`, radii | Static per item uuid: sent once per seat. Radii are authored item fields (`items/torches.py:237-241`, `308-309`); that radii never change is assumed, not verified. |
| `ItemLook.item_effects` | **Keyed by `effect_uuid`** (= the condition uuid): upsert, duration patch, remove. Whole only when entering. |
| `ItemProfile` | Static ("the fields its use does not change", `facts.py:225`): sent once per seat, when the item first enters a controlled inventory |
| `ItemState` | Controller only. Keyed or field changes from events: `charges`/`stack_count` (`ItemResourceChangeEvent`); `concentration_slots` keyed by slot; `is_lit`; and the fields a whole-snapshot event changed (§2). Whole when the item enters a controlled inventory, or again when control resumes. |
| `VisualItem` / `VisualLoadout` | Layers keyed by slot (§1.2). `is_lit` stays in the layer for viewers; for the controller it is in `ItemState` too, a duplicate (`facts.py:283`, `315`). |
| `PlayerItem` / `ItemPatch` | `ItemPatch` survives only as the entering record of an item: static parts if not sent, dynamic parts in full. Today's patch against `remembered.items` goes. |

An item enters the seat's knowledge when:
- its holder enters perception: the equipped looks, plus the whole inventory if the seat controls the holder;
- it becomes equipped on a perceived body;
- it enters a controlled inventory.

An item leaves when it moves into a foreign hidden inventory, its holder leaves, or it goes to the floor. Leaving sends nothing more than the holder's layer or inventory removal, which is the holder's change. A floor item belongs to the world study.

### 1.4 Carrier facts

| Fact | Today | Under the rule |
|---|---|---|
| `PlayerObservation` (`facts.py:384-393`) | Admission and re-acquisition bodies plus gear observations, diffed in `_emit_bodies` (`projection.py:2049-2059`) | **The entering record only:** full mutable body, static part if not sent, contact, entering item records. Gear observations go. |
| `EquipmentFact` (`facts.py:639-646`) | Whole loadout, inventory, AC and every item record per event (`projection.py:812-818`), then diffed (`2062-2066`) | Replaced by a keyed **holdings change**: owner, item, inventory add or remove (controller), layer set or remove, AC after, plus the item's entering record only if it enters. `EquipmentEvent` contributes only `active_weapon_set_after`. |
| `ItemEffectChangeFact` (`facts.py:658-665`) | Key edge without value; **not folded by the client**; the value rides in the gear-observation diff | It carries the effect value (upsert) or a duration patch, or the key alone (removal), and the client folds it |
| `ConditionChangeFact` (`facts.py:649-655`) | Whole `ConditionFact`, including `resulting_stats`, `resulting_tile` and `resulting_item`, per event | Application: upsert of the membership state. State change: a patch of the named `ConditionState` fields. Removal: the key (plus `consumed`). Stats travel as named scalar changes. |
| Known removal (`projection.py:1508-1518`, `2073-2080`) | The source's controller receives the removal of a membership on an absent target, carrying the value from `remembered` | **Deleted by the rule** ("leaving: nothing"). If the human wants the source told when its own effect ends, that is a control-based disclosure: send the key only, and the client fold must tolerate a missing body (D-A, §7). |
| `ItemChargeFact` (`facts.py:706-715`) | Keyed after-values, controller only | Unchanged for the controller. Add the layer removal of a destroyed *equipped* item for identifying non-controllers (bug C, §5). |

### 1.5 HUD types (`facts.py:91-175`)

- `PlayerHUDSnapshot` stops being server state. `remembered.hud_snapshot` (`projection.py:2167-2170`) is deleted.
- `PlayerHUDPatch` / `SheetPatch` stay for initialization, as full sheets. After that, sheet changes travel as per-actor sheet facts at their event version, keyed:
  - resources by `key` (`facts.py:84`);
  - handlers by `uuid` (`core/action_types.py:28`);
  - compatible slots by item uuid;
  - prepared selections by `casting_source_id` (`events.py:5609`).

  This needs the native events of §4.
- The `revision` boundary gate (`projection.py:2152-2163`) goes, because the facts are ordered by their occurrence.
- `initiative`: the seat's view is the encounter order filtered by *perceived now*, not by the live engine senses as now (`session.py:127-134`). Send the filtered order whole (a few uuids) at each event that changes it: start, join, leave, or a combatant entering perception. No memory is needed. The join and leave carriers are missing (§4.1, item 11).

### 1.6 `PlayerInitialization` (`facts.py:1143-1158`)

- Under the rule it is "everything entering at once":
  - full current bodies of the perceived actors (`observations`);
  - their items;
  - the full HUD of the controlled actors (`hud`, `application.py:43-45`).
- It seeds the static-sent sets.
- The startup walk (`begin_projection`, `projection.py:2179-2208`) still works. Its `_emit_bodies` diff becomes a plain emit.

### 1.7 Deleted structures and code

| What | file:line |
|---|---|
| `remembered.actors` / `items` / `hud_snapshot` as diff bases and fold targets | `projection.py:2051`, `2058`, `2063`, `2074`, `2082`, `2167-2170`; the `ProjectionState` docstring `1899-1907` |
| The body diff | `actor_changes` used as a diff (`207-254`): it stays only as the full-record builder. `_emit_bodies` diff branch `2049-2059`; EquipmentFact re-diff `2062-2066` |
| Item diffs | `item_patch` `181-186`, `_item_patches` `1931-1934` |
| Gear observations | `_holdings` `257-260`, `_gear_observation` `263-267`, call sites `1424-1429`, `1433-1443` |
| Whole-holdings `EquipmentFact` | `812-818`; disclosure pass `1610-1611`; public pass `1870` |
| Known removal | `held_conditions` `1345-1349`, `members` `1344`, `1416`; the special case `1508-1518`; `change_membership` on local members `1519-1520`; `known_removals` plumbing; value substitution `2073-2080` |
| Monotone `known` | `projection.py:1343`, replaced by the perceived set; `known_actor_uuids=remembered.actors` and `names` (`application.py:67`, `72`), replaced by the static-sent set plus engine birth names |
| Re-acquisition | `acquired` evidence (`capture.py:803-813`); the `\| acquired` bypass (`877`); the cross-root `newly_known` (`capture.py:973-984`) becomes the walk's perceived set |
| HUD diff | `sheet_changes` `2087-2130` (only the full builder stays); `hud_patch` `2133-2141`; the snapshot diff in `project_after_values` `2165-2171`; `apply_hud` on `remembered` |
| Per-seat engine replica (recommended, not forced) | `ProjectionState.actors` (`1909`). It is engine values, identical across seats except `last_visual_position`; replace it with one shared per-lineage fold of the change records. |
| Content composition reading `remembered` actors and items | `content_composition.py:103-106`, replaced by the static-sent sets and the engine fold |
| Test oracle | `tests/player/test_emitted_update_replica.py:70-87` (client == `remembered`, same reducer twice), replaced by §6 |

---

## 2. The per-event change record

**Where it is computed.** In `advance_capture` (`capture.py:836-840`), once per version, for every seat. `apply_actor_fact` (`actor_projection.py:64-139`) already dispatches per event kind and writes a fixed set of fields per case. Each case also returns its change as an explicit frozen record, with no `getattr` and no field loop. The record is stored beside `AdmissionEvidence`, keyed by event uuid. It is never compared with any seat value.

**Shape** (a leaf type next to `dnd/types/actor_facts.py`):
- `ActorChange`:
  - `actor_uuid`;
  - optional scalar after-values (HP, temporary HP, grant set or cleared, max HP, AC, life, remains, size, disposition, faction, occupancy, weapon set);
  - `conditions_set` / `conditions_patched` (uuid plus changed `ConditionState` fields) / `conditions_removed`;
  - `inventory_added` / `inventory_removed`;
  - `layers_set` / `layers_removed`;
  - `items: tuple[ItemChange]`;
  - `changed: frozenset[ChangeField]`.
- `ItemChange`:
  - `item_uuid`;
  - `effects_set` / `effects_patched` / `effects_removed`;
  - item field after-values (charges, stack, integrity, current HP, `is_lit`, slots keyed by slot uuid, …);
  - `record` (the event's own `ItemPresentationState`) for entering;
  - `changed`.

| Event kind | Change | Native carrier | Must be recorded / derived | Size (est., JSON) |
|---|---|---|---|---|
| `EntityFactionChangedEvent` (`events.py:976`; writer `entity.py:1791`) | `faction` | `faction_after` | — | ~40 B |
| `DamageAppliedEvent` (`events.py:5473`; `entity.py:3616`) | `normal_hp`, `temporary_hp`; grant cleared iff temporary HP is 0 | `resulting_normal_hp/temporary_hp` | The grant clear is a fold rule (`actor_projection.py:96-99`), named in the change | ~40 B (the fact also carries the presentation) |
| `HealEvent` (`5640`; `entity.py:3918`) | same as damage | yes | — | ~40 B |
| `TemporaryHitPointsChangedEvent` (`5527`; `health.py:796`) | `temporary_hp`, grant | yes | — | ~80 B |
| `LifeStateChangeEvent` (`5847`; `entity.py:2583`) | life, `normal_hp`, remains | yes | — | ~60 B |
| `AttackEvent` with outcome | weapon set | derived from slot / source kind (`actor_projection.py:91-95`) | — | ~20 B |
| `EquipmentEvent` | weapon set | `active_weapon_set_after` | Stop treating it as holdings (`projection.py:812`) | ~20 B |
| `ItemLocationStateEvent` INVENTORY/EQUIPMENT (`base_item.py:91-136`; writer `413-470`, entity path `entity.py:4874-4909`) | owner: inventory add, layer set at `equipment_slot` or the previous slot removed, AC after; previous holder: inventory and layer removal; item entering record | owner, slot, `entity_armor_class_after`, the whole `item_state` | (1) The previous slot of the same owner: from the shared fold before the event, or record `previous_equipment_slot`. (2) The previous holder: usually native (`source_entity_uuid` on the FLOOR path `entity.py:4904`; `ItemHoldingsReleasedEvent.source_entity_uuid` on transfers, `base_item.py:396-404`); the scan `remove_previous_item_holdings` (`actor_projection.py:142-154`) stays as the fallback. (3) Non-location item fields changed in the snapshot: compare once against the shared fold's previous item (seat-independent), or record them at the writer. | ~120 B; plus the record when entering (look ~250 B, controller profile ~600 B and state ~400 B) |
| `ItemLocationStateEvent` FLOOR/DESTROYED/MERGED | previous holder: inventory and layer removal | item uuid | As above | ~80 B |
| `ItemHoldingsReleasedEvent` (`base_item.py:82-88`) | holder: inventory and layer removal | `source_entity_uuid`, `item_uuid` | — | ~80 B |
| `ItemResourceChangeEvent` (`base_item.py:1615-1642`) | item charges and stack; if destroyed, inventory removal, **layer removal** and item gone | yes | Disclose the layer removal to identifying non-controllers (missing today) | ~60 B |
| `ConditionApplicationEvent` (`base_conditions.py:168-185`; completion `base_block.py:1886-1891`) | membership upsert (non-INTERNAL); stats; for an item target, effect upsert plus item fields | `condition_state`; `resulting_stats` is a whole snapshot of 7 wire values | Which stat fields changed: compare once with the shared fold. INTERNAL: stats only. | condition 400–900 B; stats ≤7 scalars |
| `ConditionStateChangedEvent` (`base_conditions.py:229-236`) | patch of the changed `ConditionState` fields; stats | whole `condition_state` and `resulting_stats` | **The changed-field names.** The duration-tick writers already compare: `entity.py:2330-2336`, `base_block.py:1676-1679` (`before = snapshot_duration()`); `publish_owner_state` compares state and stats (`conditions.py:2096-2098`). Other writers (`spells/illusion.py:1103`, `necromancy.py:1744`, `conjuration.py:4510`, `monsters/traits.py:1689`, `base_block.py:1652`) use the shared-fold compare. | a duration patch is ~120 B, against today's whole `ConditionFact` |
| `ConditionRemovalEvent` (`base_conditions.py:239-258`) | membership key; stats; for an item, effect key | key plus snapshot | Stats subset, as above | ~60 B |
| Item-condition events (`resulting_item`: `base_block.py:1429`, `1656`, `1891`; floor `conditions.py:2090-2093`) | `ItemChange`: effect set, patch or remove keyed by `effect_uuid`, plus `is_lit` and slots | whole `ItemPresentationState` | The changed item fields: native prior at `conditions.py:2090-2093` (floor), else the shared-fold compare | effect ~200 B |
| `SpatialChangeEvent` entered/left | disposition PRESENT, occupancy, terminal | already `SpatialFact` | — | as today |
| `EntityCreatedEvent` | an entering record when perceived | birth | — | full body |

In the table, "whole snapshot" means the event records an after-state, not its change. The change is that event's before against its after, both engine values: the writer's own before, or the shared fold one version earlier. It is seat-independent and is not a client copy.

---

## 3. Disclosure per seat: exactly, with a hidden-only change sending nothing

The change is computed once (§2) and **names its changed leaf fields** (`ChangeField`).

Example names:
- `NORMAL_HP`, `TEMP_HP`, `TEMP_GRANT`, `MAX_HP`, `AC`, `LIFE`, `REMAINS`, `SIZE`, `DISPOSITION`;
- `FACTION`, `OCCUPANCY`, `WEAPON_SET`, `LAYERS`, `INVENTORY`;
- `CONDITION_MEMBERSHIP`, `CONDITION_STATE`, `CONDITION_DURATION`;
- `ITEM_EFFECT_MEMBERSHIP`, `ITEM_EFFECT_DURATION`, `ITEM_STATE_*`, `SLOT_LINEAGE`.

Per seat:
1. **Gate (§1.1):** change, entering or nothing.
2. **Visibility per field.** Each predicate is the existing rule, now applied to a change:

| Field(s) | Visible to the seat iff | Today's rule |
|---|---|---|
| body scalars, condition membership and state (non-INTERNAL) | `_identified(e, X)` | `projection.py:425`, `781-806`, `897` |
| `FACTION` | identified **and** located | `785-788` |
| `OCCUPANCY` | arrival or departure allowed | `859-879` |
| `LAYERS`, item look, `ITEM_EFFECT_MEMBERSHIP` | identified holder (or controller); for the previous holder, perceived *previous* holder | `176-178`, `380-389`, `1424-1429` |
| `INVENTORY`, `ITEM_STATE_*`, profile, charges | `controls(holder)` | `204`, `808-811` |
| `CONDITION_DURATION`, `ITEM_EFFECT_DURATION` | `controls(owner)` | `1653-1661`, `1670-1674` |
| `event_uuid`, `applied_source_event_cursor` | mapped (public versions and cursors), not hidden | `1655-1659` |
| `SLOT_LINEAGE` (concentration slot cast lineage) | value-dependent: the lineage is disclosed | `1279-1308` |

3. **Drop rule:** emit iff `changed ∩ visible(seat) ≠ ∅`. The fact carries only the visible changed fields, each passed through today's per-value maps:
   - `_disclosed_condition` / `_disclosed_slots` (lineage, applied after the walk, as today `1598-1637`);
   - `_public_condition` / `_public_item_effects` (cursors and duration, `1653-1689`).

   Example: a duration tick (`entity.py:2335`) names only `CONDITION_DURATION`, so a non-owner seat gets nothing. Today it gets the whole `ConditionFact` with `duration=None`, a resend of a value it already holds.
4. **Value-dependent maps.** For `SLOT_LINEAGE`, the field name alone cannot tell whether the visible value changed: L1 undisclosed → L2 undisclosed maps to None → None.
   - Exact: the change also carries that sub-field's *objective before* (from the writer or the shared fold), and the seat compares mapped(before) with mapped(after). That is still not seat memory.
   - Cheap: accept a rare redundant send (no leak).
5. **Group-final lineage disclosure:** build the per-seat facts in the walk and disclose after it, as observations are today (`1627-1630`).

No step reads a client value. The seat contributes only its gate, its control, its grants and its disclosed lineages.

---

## 4. The HUD under the rule

The controlled actor is always perceived, so every sheet change is case (1): the event's own change. The sheet is pull-evaluated from the live engine once per op (`session.py:138-172`, called at `482`).

### 4.1 Sheet fields that change without any event carrying their value (exact list)

1. **`resources`: actions, bonus actions and reactions `current`.**
   - Consumption is cost modifiers: `consume`, `consume_prevalidated`, `install_prevalidated_aggregate_with_receipt`, `consume_aggregate_with_receipt`, `commit_fixed_costs_without_dispatch` (`action_economy.py:1120-1313`).
   - Refund: `undo_prevalidated_debit` (`1261`).
   - Reset: `reset_all_costs` (`1072-1084`) at turn start (`entity.py:2998`) and **per op outside combat** (`session.py:470-473`, no event at all).
   - `TurnStartEvent` carries only the four turn-start counts (`events.py:5784-5792`, written `entity.py:3003-3013`).
   - `ActionCostsCommittedEvent` carries named costs only (`events.py:5547-5554`, written `base_actions.py:2197-2203`).
2. **Their `maximum`** (`channel_capacity`, `action_economy.py:1007`): capacity contributions (`135-158`), added by features and conditions.
3. **Movement `current`:** `movement_remaining` (`1058`) = speed − spent. It is debited by steps and changed by `grant_speed` / `remove_speed_grant` (`1028-1036`) and by condition speed modifiers.
4. **Movement `maximum`:** speed-derived.
5. **Spell slots `current` and `maximum`:** casting costs; `recover_spell_slots` (`1099`); `reset_spell_slot_costs` (`1086`); `set_normal_spell_slot_capacity` / `remove_normal_spell_slot_capacity` (`885`, `973`).
6. **Named resources `current` and `maximum`:**
   - `consume_resource` (`732`), `set_resource_current` (`744`), `recover_for` (`212`);
   - `on_turn_start` (`766-775`, including `extra_attacks`);
   - `add_resource` / `remove_resource` and contributions (`620-720`).
   - `RestResourcesRecoveredEvent` carries names only (`events.py:5565-5570`).
7. **`handler_details`:**
   - The `enabled` toggle (`base_block.py:1062-1076`, via `session.py:598-607`) publishes no event.
   - The set of toggleable handlers changes when features or conditions register handlers (`entity.py:5582-5616`), with no event naming them.
8. **`compatible_item_slots`:** derived from each item's static baseline plus the actor's `one_handed_offhand_grants` (`equipment.py:1554-1563`). Inventory changes are evented but do not carry it. The grant has no event.
9. **`abilities`:** `ability_score.score` is the modified total (`values.py:189-191`), so modifiers from conditions or items change it silently.
10. **`proficiency_bonus`, `skills`, `expertise`, `saves`:** modifiable values and proficiency sets. They are normally static in an encounter, but nothing records a change. Unverified whether any rule changes them mid-encounter.
11. **`initiative`:**
    - Combatant join and leave mutate the order (`encounter.py:436-460`, `468-475`, `520-529`) with no order-carrying event. Only `EncounterStartEvent.initiative_order` exists (`events.py:5738`).
    - Visibility reads the live senses (`session.py:127-134`).

Already evented, with their after-values:
- `normal_hp` / `maximum_hp`, duplicates of the body;
- `class_levels` (`SpellMasteryStudiedEvent`, `events.py:5587-5592`);
- `scribed_spell_ids` (`SpellbookChangedEvent`, `5595`);
- `permanent_feature_uses` (`PermanentFeatureUsedEvent`, `5572`);
- `prepared_spell_selections` (`SpellPreparationChangedEvent`, `5604`, per casting source).

Static: `name`, `portrait_key`, `species`, `species_variant`, `background`, `origin`.

### 4.2 The minimal native events

| Option | Native change | Size | Rule fit |
|---|---|---|---|
| **H1. Per-mutation economy events** | An `ActionEconomyChangedEvent(entity, set: (key, current, maximum)…, removed: key…)` from each mutation in `action_economy.py` (about 20 methods); a `resulting_economy` beside `resulting_stats` on condition events for capacity and speed changes; `HandlerToggledEvent(entity, handler, enabled)` at `base_block.py:1072-1075`; handler-set changes on condition and feature registration; ability scores added to `EntityStatsState` (`types/actor.py:84-99`) and to an entity-stats after-value on `ItemLocationStateEvent` (today AC only, `entity.py:4905`); combatant join and leave events carrying the uuid and its order anchor | **Large**, invasive (the modifier machinery feeds capacities and speed) | Fully event-native |
| **H2. One native sheet publication at boundaries** | One writer, `publish_sheet_state(actor, parent_event)`. It snapshots the same values as `session.py:142-171` (moved into the engine), compares them with the actor's **own last committed publication** (the `publish_owner_state` pattern, `conditions.py:2084-2110`; the duration ticks `entity.py:2330-2336` compare the same way), and registers an event with only the changed keys. Called at: cost commit (`base_actions.py:2193`), action completion and cancel, turn start (`entity.py:2998-3014`), condition membership commit (`base_block.py:1877-1882`), the out-of-combat reset (`session.py:470-473`, before `end_cursor`). Plus `HandlerToggledEvent` and combatant join/leave. | **Small to medium**: one writer, about 6 call sites, 3 event types | Publication becomes event-native. The compare lives in the engine, per actor, against its own last *event* (history, not a client copy). **The human must accept or reject this.** |
| D4(b) per-actor previous sheet in publication | `previous_sheets` beside `session.py:482` | Small | **Violates the rule** (a copy of client values, shared) |
| Whole sheets every op | none | — | Rule-compliant but unaffordable: blue's whole HUD is 91,468 B (`agent_docs/plans/ENGINE_SINGLE_PASS_CHANGE_PROPAGATION_PLAN_2026-10-16.md:686`); `top.hud` is 4–10.6 KB per case as patches today (`byte_census.txt`) |

`compatible_item_slots` can leave the per-op sheet: send each item's baseline slots once in its controlled record (it is static per item), plus the actor's off-hand grant as one field, which changes rarely.

---

## 5. The two bugs of the earlier study under the rule

**A. The client fold and the engine fold disagree.**
- The client's condition fold applies HP, max HP, AC, disposition and size from `resulting_stats`, but **not `temporary_hp` / `temporary_hp_grant`** (`reduction.py:447-463`). The engine's `apply_stats` does (`actor_projection.py:157-165`).
- INTERNAL conditions send no fact (`projection.py:897`), while the per-seat replica applies their stats (`player/actor_projection.py:14-21` strips only the membership).
- Today the drift sits in `remembered` and in the client alike: `_emit_bodies` folds the *client* reducer into `remembered`, `2058`/`2082`. It is corrected only when a later re-acquisition diff compares against the engine body.
- A controlled actor is never in its own `acquired` (`capture.py:808` takes contacts only), so its drift is never corrected. Its HUD (live) and its body disagree.
- The replica test cannot see this, because it compares the same reducer with itself (`test_emitted_update_replica.py:84`).

Under the rule:
- The diff is gone. Re-entry still sends a full current body, so drift is corrected at re-entry, but a continuously perceived actor drifts forever. **The rule exposes the bug.**
- It is removed structurally when the change record is the engine fold's own case output (§2): the client then applies exactly the fields `apply_actor_fact` writes. Condition stats name `TEMP_HP` and `TEMP_GRANT`, and INTERNAL conditions emit a stats-only change to identifying seats.

**C (new, same class). A destroyed equipped item stays as a layer for non-controllers.**
- `ItemResourceChangeEvent` with `item_destroyed` removes the layer in the engine fold (`actor_projection.py:83-89`).
- Only the controller receives `ItemChargeFact` (`projection.py:808-811`), so other seats keep a ghost layer until re-acquisition today, and forever under the rule.
- The change record's `LAYERS` removal, disclosed to identifying seats, fixes it.
- More generally: whenever an item mutation changes a body or sheet field, `ItemLocationStateEvent` must carry the after-value, and today it carries only AC (`entity.py:4905`). Unverified: no implemented item seems to set ability scores or max HP; such items appear only in `content_data/ledgers/srd_5_1_source_coverage.json`.

**B. Re-acquisition is counted per observer.**
- `acquired = entity_contacts_changed − member` is computed per observer (`capture.py:808`). It is admitted past the known check (`877`).
- A 26-observer seat re-admits X whenever any member regains X, even while another member still holds it. Today the diff drops the body fields, but the observation still goes out with its contact (`projection.py:2056`). This is part of `body.contact` / `body.actor_uuid`, 5.7 KB and 4.0 KB in sleet and darkness (`byte_census.txt`).
- Under the rule, entering is a **seat-level** transition: the composed contacts go ∅ → non-∅ (`entity_members`, `audience.py:672-674`). X held by another member is "perceived before and after", so no record goes out; the SensoryFact's contact row already carries the contact. **The rule removes the bug by definition.**
- The cost: a genuine seat-level re-entry now sends the full current mutable body (no diff to drop it when it is unchanged).
- Structural consequence: the composed view lives in the projector, so admission moves from capture's `_derive_admissions` (`capture.py:858-896`, computed up front against a monotone `known`) into the walk after `fold_senses` (`projection.py:1474`). Capture keeps only the shared per-version evidence (the actor values at the version).

---

## 6. Risks

- **Bytes at re-entry.** Every seat-level re-entry sends a full current body with its conditions and dynamic item parts.
  - Trimming `ConditionFact.resulting_*` out of the body's membership tuple (they are change payloads) cuts this.
  - Sleet Storm (frequent visibility changes) is the worst case. The previous study counted 234 re-acquisitions without splitting seat-level from per-observer. Not measured; per memory, ask before probing.
- **Fog of war belongs to the client.**
  - The server cannot rebuild stale out-of-sight bodies, so reconnect must stay journal replay (`sdk/python/src/dnd_player/transport.py:370-457`).
  - A fresh-snapshot reconnect would show only what is perceived now.
- **Ordering.**
  - The entering record must precede the changes at its version. Today's admission is applied before the event and carries the before-state (`projection.py:1410-1418`, `capture.py:821-840`), and that carries over.
  - Payloads can complete before their sensory child (`projection.py:725`). A change on X before X's sensory entry in the same lineage sends nothing, and the entering record then carries it (correct state, but the *fact*, its animation, is lost).
  - Summon creation witnesses (`projection.py:863-872`) need X perceived at the `SpatialFact`.
  - Keep today's "candidate held as a contact" admission point, evaluated against the perceived set.
- **Grant/contact skew.** Identity accumulates over versions and parents (`events.py:2383-2405`).
  - A grant can outlive a contact inside a lineage. The result is a change to a seat that no longer perceives X (natively disclosed; harmless).
  - A contact without a grant sends nothing, and the body drifts until re-entry, as today.
- **Hidden-only drop needs leaf names.** Duration-tick and owner-state writers already compare natively. The other condition writers and the whole-item snapshots need the shared-fold compare, written explicitly (no `getattr` field loops, per AGENTS.md).
- **Previous-holder routing.** Its removal must go at the location event's version to seats perceiving the *previous* holder.
- **Idempotence.**
  - Inventory adds are "append if absent, keep position" (the engine dict rule, `actor_projection.py:126-128`).
  - Layers are keyed by slot.
  - A removal of something absent is a no-op.
  - The client fold must accept "all mutable fields" for a re-entry when static fields were sent earlier. `observed_actor` (`reduction.py:148-155`) requires every field today.
- **HUD.** Until H1 or H2 lands, the HUD is either a rule exception or 91 KB per op.
- **Per-seat engine replica.** `ProjectionState.actors` is per-seat state beyond "perceived or disclosed". It is engine values, not client values, but it is redundant. Sharing it means one per-lineage fold of the change records for all seats.
  - The in-walk reads depend on it: `_held_item_disclosed` 380-389, `_held_content_at_event` 392-405, source-condition checks 698-703 / 765-770 / 776-779, LifeFact preserved items 800-806, faction `control_lost` 1527-1542.
- **Schema.** New and changed wire types: holdings change, the effect value, the condition patch, the stats-only change, sheet facts. This needs a schema bump, a new SDK protocol digest and a Godot fold note.
- **Test oracle.** Replace the D16-C replica with: at each op end, the client fold restricted to the perceived set equals the public projection of the shared fold, built by the same functions as entering records. It would have caught bugs A and C.

---

## 7. Decisions for the human

- **D-A.** Should the source's controller still be told when its condition on an *unperceived* target ends (key only, tolerant client fold)? Or does "leaving: nothing" apply (delete `projection.py:1508-1518`, `2073-2080`)?
- **D-B.** Static birth fields and static item look/profile sent once per seat (the "static content ids" clause)? Or resent with every entering body (the literal "full current body")?
- **D-C. HUD:**
  - H1, per-mutation events (large);
  - H2, a native boundary publication comparing with the actor's own last event (small to medium; a compare inside the engine);
  - or a declared HUD exception.
  - D4(b) is out under the rule.
- **D-D.** Initiative: send the seat-filtered order whole on order events and on perception entry? This needs native join/leave carriers.

A plan built from this note must add the antislop and antiOOP reviewers (AGENTS.md).
