# HUD: H1 (an event per economy change) vs H2 (one engine writer)

Read-only comparative study. Worktree `/home/tommaso/.codex/worktrees/event-native-deltas/dnd_engine`, head `9397ebca6` (`git diff 55bf034cc HEAD -- dnd/` is empty, so the stateless study's line numbers hold). Paths are relative to the worktree. Nothing was run or measured: every millisecond and byte figure below is either quoted from a cited log or marked as an estimate.

Inputs: `agent_docs/EVENT_NATIVE_DELTAS_2026-10-18.md` (revision 2), `agent_docs/event_native_deltas_2026-10-18/stateless/actors_items_hud.md` §4, `byte_census.txt`, and the code below.

---

## 0. Answer in brief

1. **The decisive fact is that the sheet is derived, not stored.** `actions/bonus/reactions.current`, both maxima, movement and ability scores are `value_score` reads (`core/values.py:189-196`, `767-777`). They are composed of:
   - static rows gated by `contributions_active()` on their owner (`values.py:700-710`);
   - contextual rows, which are callables evaluated at read time (`values.py:712-725`).

   Both change with no write to the actor. Two examples:
   - **Frightened** caps speed at 0 while the frightener is in the frightened actor's sight (`conditions.py:1127-1129`, `1337-1340`). Any third party's step, light change or obscurement changes the HUD's movement.
   - **Activation gates** read remote state:
     - spatial suppression by position (`core/base_conditions.py:568-578`);
     - a paladin aura's provider and faction equality (`classes/paladin.py:748-758`);
     - an anchor's suspension (`spatial/area_conditions.py:208-212`);
     - an item's equip state and owner (`items/divine_rewards.py:64-72`).

   So the writers of these fields are an open set. H1 cannot be exact without a recompute-and-compare, and that recompute-and-compare is H2.
2. **H2 as specified (about 6 points) is not exact either.**
   - Reactors spend reactions and resources inside handlers of someone else's lineage (`classes/fighter.py:499`, `spells/infernal.py:201-209`, `spells/reaction_costs.py:109`, `encounter.py:765`, `classes/feats.py:43`, `origins/half_orc.py:43`).
   - Remote and contextual changes have no point at all.
   - **The exact minimal H2 is one op-end sweep** of the published actors (`session.py:474`), plus one startup call. That is the same evaluation as today, at the same boundary, compared per actor with that actor's last sheet event. The other points only add events.
3. **Bytes.** Both turn today's ~0.8–2.6 KB `top.hud` per update into ~0.1–0.3 KB keyed rows. Whole sheets were 91,468 B for blue.
4. **CPU.** H2 is about today's cost (the ~7 ms per op "HUD sheets" evaluation stays; the per-seat diff goes). H1 is cheaper only because it is inexact.
5. **Q5, honestly.** H2 is not a per-seat copy, but it *is* a comparison with what was last published. It is one per actor and lives in the engine's own event history, the same mechanism as `publish_owner_state` (`conditions.py:2084-2110`). When each actor has one controlling seat, today's per-seat copies are also one per actor. The real difference is where the comparison lives and that its output is a native event.
6. **Recommendation:** H2 (op-end sweep, keyed change on the wire), plus native join/leave events for initiative (the one place where H1 is exact and tiny). The human must still accept §5.

---

## 1. Today

| Step | Where | What |
|---|---|---|
| Evaluate | `player/session.py:138-172` (`_snapshot_sheets`), called once per op for **every** player actor at `482` | Live pull evaluation of 20 sheet fields |
| Out-of-combat reset | `session.py:469-473` | `reset_all_costs()` for every player actor, every op, no event |
| Per-seat snapshot | `session.py:121-135`, `483-484` | Filters sheets to `audience.controlled`. Initiative is filtered by the *live* senses of every seat observer (`127-134`) |
| Diff | `player/projection.py:2144-2171` | Whole-HUD equality against `state.remembered.hud_snapshot` (`2167`), then `hud_patch` (`2133-2141`) and `sheet_changes` (`2087-2130`). A changed field is sent **whole**, e.g. the entire `resources` tuple (`2110-2111`) |
| Fold | `player/reduction.py:566-585` (`apply_hud`) | The client reducer, also run on `remembered` (`projection.py:2170`) |
| Side channel | `player/recorded.py:27`, `115-125`; `session.py:114`; `application.py:44`, `61`, `85` | The HUD is not in the native history. It travels as `Operation.hud_by_seat` and `RecordedSequence.hud_snapshots` |

Cost: "HUD sheets: ~7 ms" per op in the Spirit Guardians move profile (30 published actors; `agent_docs/ENGINE_SINGLE_PASS_PROGRESS_2026-10-17.md:321`).

Bytes (`byte_census.txt`, `top.hud`):

| Case | Total | Per update |
|---|---|---|
| Fireball | 5.1 KB / 2 updates | 2.6 KB |
| Sleet | 4.0 KB / 4 | 1.0 KB |
| SG walk | 10.6 KB / 14 | 0.76 KB |
| Darkness | 4.6 KB / 4 | 1.15 KB |

Why it is large (estimate): the `resources` tuple is about 9–12 rows of `{key,label,current,maximum}`, ~55–75 B each, sent whole when any row changes. HP is also restated in the sheet, although the body facts already carry it (`projection.py:2116-2119`).

### The eleven field groups that change with no event carrying their value
(`stateless/actors_items_hud.md` §4.1, rechecked)

1. Actions, bonus actions and reactions `current`.
2. Their maxima.
3. Movement `current`.
4. Movement maximum.
5. Spell slots.
6. Named resources.
7. Handler toggles and the handler set.
8. Compatible slots.
9. Abilities.
10. Proficiencies.
11. Initiative.

Already evented: HP, `class_levels`, `scribed_spell_ids`, `permanent_feature_uses`, `prepared_spell_selections`.

---

## 2. H1 — a native event per economy change

### 2.1 Writers to change (exact census)

| Group | Owner-side writers (file:line) | Callers and bypasses that must also change |
|---|---|---|
| 1. Channel `current` (`normalized_score`) | `blocks/action_economy.py`: `install_prevalidated_aggregate_with_receipt` 1182 (debit at 1210, rollback 1219-1235), reached from `consume` 1120, `consume_prevalidated` 1133, `consume_aggregate_with_receipt` 1240 and `commit_fixed_costs_without_dispatch` 1313; `undo_prevalidated_debit` 1261 (1310); `reset_all_costs` 1072 (1084); `_sync_action_bonus_locks` 582 (596, 599), via `record_action_channels` 575, `add/remove_action_bonus_exclusion` 553/558 and `on_turn_start` 766-771 | `classes/fighter.py:499`, `spells/infernal.py:201`, `spells/hit_effects.py:282`, `encounter.py:765`; cost appliers `actions.py:317`, `1638`, `1648`, `spells/reaction_costs.py:109`, `spells/abjuration.py:2214`; resets `entity.py:2442`, `2998`, `encounter.py:680`, `player/session.py:473`. **Modifier rows from outside the block:** `fighter.py:917`, `spells/conjuration.py:3480`, `spells/necromancy.py:2136`, `conditions.py:2417`, `spells/transmutation.py:371`, `monsters/circus_fighter_conditions.py:380/388/483`, `creature_transforms.py:90-92/120-121`; the generic removal `core/base_conditions.py:1139-1143` |
| 2. Channel maxima (`channel_capacity` 1007-1014) | Same as group 1, minus the cost rows | Same |
| 3–4. Movement current and maximum (`movement_remaining` 1058-1059; capacity 1010-1011) | `movement_debits` 1196, 1307, 1079; `dash_count` reset 1080; `grant_speed` 1028, `remove_speed_grant` 1034, base write 1041 | Steps `actions.py:1055`, `3616`; `conditions.py:1705`; `actions_functional.py:165`; Dash `conditions.py:668`; flight `classes/sorcerer.py:398/429`, `transmutation.py:1987/1993/1999`, `monsters/spell_summons.py:245`; **23 `speed_values` modifier sites in 13 files**; `content/characters/origin_grants.py:448/837/925`; **contextual**: `classes/barbarian.py:549`, `content/characters/barbarian_grants.py:461`, `items/property_composition.py:91-97` (armor Strength requirement), `conditions.py:1128` (Frightened, reads senses) |
| 5. Spell slots | `reset_spell_slot_costs` 1086; `recover_spell_slots` 1099 (in-place `modifier.value +=` at 1110); `set_normal_spell_slot_capacity` 885; `remove_normal_spell_slot_capacity` 973; debits via group 1 | `classes/paladin.py:179`, `hit_effects.py:283`, `infernal.py:209`, `classes/wizard.py:207`, `entity.py:2443`, `classes/divine_intervention.py:281`, `content/characters/spellcasting_grants.py:96/99/104` |
| 6. Named resources | `add_resource` 620, `remove_resource` 635, `add/remove_resource_contribution` 639/676 (current recomputed at 169), `consume_resource` 732, `set_resource_current` 744, `on_short_rest` 756, `on_long_rest` 761, `on_turn_start` 766-775, `grant_attack_batch` 548/550, commit 1357 (rollback 1363) | About 60 call lines in 20 files (e.g. `feats.py:43/97/143`, `classes/cleric.py:214`, `classes/rage.py:765/795`, `fighter.py:847…1432`, `barbarian.py:788/844/876`, `sorcerer.py:1534/1565`, `half_orc.py:43`, `content/characters/progression.py:543`, `wizard_grants.py:108-258`, `origin_grants.py:285-1118`, `cleric_grants.py:74-219`, `fighter_grants.py:266-623`, `sorcerer_grants.py:331-898`, `caster_chassis.py:127-322`, `monsters/high_level_spell_summons.py:677-810`, `entity.py:2379/2444/2999`). **Direct writes that bypass the block:** `sorcerer.py:1412`, `paladin.py:1621`, `cleric_grants.py:234` |
| 7. Handlers | `core/base_block.py:1058`, `1074` (`set_handler_enabled[_by_uuid]`); the set: `add_event_handler` 961, `remove_event_handler[_from_dicts]` 983/994 | **Direct `handler.enabled =`:** `progression.py:548`, `sorcerer_grants.py:665/1141`, `spellcasting_grants.py:280`. Callers: `session.py:603`, `paladin_grants.py:148`, `builds.py:297`. 17 `player_toggleable=True` constructors |
| 8. Compatible slots (`blocks/equipment.py:1554-1563`) | `entity.py:5171-5173` (grant), `5175-5185` (revoke) | Inventory membership is already evented (`ItemLocationStateEvent`), but it carries no slots |
| 9. Abilities | `ability_score` modifier rows: `barbarian.py:1052/1060`; construction `blocks/abilities.py:181` | Plus the activation of each row's owner, which has no writer |
| 10. Proficiencies | Skill and save proficiency sources (`blocks/skills.py`, `blocks/saving_throws.py`; 16 grant sites in 5 content files); `proficiency_bonus` rows at `entity.py:1859`, `progression.py:112`, `circus_fighter_conditions.py:421` | Build and progression commands only, as far as found |
| 11. Initiative | `encounter.py:458` (join), `475` (release, out of combat), `527` (leaves), `588` (start; `EncounterStartEvent` carries it, `651`) | The per-seat filter reads live senses (`session.py:127-134`) |

Modifier-driven capacity, speed and ability changes caused by memberships would need a `resulting_economy` and abilities after-value beside `resulting_stats` on:
- condition application (`base_block.py:1886-1891`);
- condition state (`base_block.py:1650-1656`, `conditions.py:2096-2109`);
- condition removal;
- item location (`entity.py:4874-4909`; armor Strength penalty);
- creature transforms.

**Size (estimate).**
- Writers:
  - about 25 owner emission points;
  - `parent_event` threaded through about 90 caller lines (most economy methods take no parent: `consume`, `consume_resource`, `reset_all_costs`, `add_resource`…);
  - about 7 direct writes rerouted;
  - 5–6 event writers gaining economy and ability after-values;
  - 3–5 new event types (economy change, handler toggle, handler set, off-hand grant, join/leave).
- Lines: about 800–950 added, about 200 deleted (the HUD diff), across about 45 files.
- That is before the backstop of §2.2.

### 2.2 Exactness

**It misses changes by construction:**
- **Contextual rows** have no write: Frightened (senses), Fast Movement (armor), armor Strength requirement (Strength).
- **Activation gates** have no write on the actor: suppression positions, aura provider and faction, anchor suspension, the item's equip state, owner registry (`core/base_object.py:130-135`, `blocks/base_item.py:212-213`).
- **Modifier rows through variables.** There are 249 `add_modifier` and 50 `remove_modifier` call sites in 45 files, plus 5 in-place `modifier.value` writes (`spells/illusion.py:1096`, `origin_grants.py:1030`, `conjuration.py:4498`, `action_economy.py:1110`, `necromancy.py:1735`). The target value is often a loop variable (`for speed in …speed_values`).
- **The funnel can't publish.** `values.py` is below `events.py` (`events.py:45` imports values), so `add_modifier` cannot emit without a cycle or a late hook.

**Proof options:**
- An AST architecture test *can* forbid direct writes to `Resource.current`, `movement_debits`, `dash_count`, `handler.enabled` and `one_handed_offhand_grants` outside their owners.
- It *cannot* prove modifier-driven or contextual changes are evented.
- Only a differential test can: fold the controller's sheet facts and compare with live evaluation at every op end, over the 31 gallery cases and `tests/player`. It would fail on the contextual and activation cases.
- **Exact H1 therefore needs H2's sweep as a backstop.** It is then H2 plus extra events.

**Hazards specific to H1:**
- **Rollback paths write transient states:** `action_economy.py:1219-1235`, `1362-1368`; `progression.py:540-551`; `sorcerer_grants.py:655-668`. The event store is append-only, so emission must be deferred to the commit.
- **Preflight forbids publishing** (`core/events.py:2376`).
- **Orphan roots.** Writers with no parent (the reset at `session.py:473`, rests, grants) create orphan roots.

### 2.3 Runtime and bytes per op (estimates)

- **Native work.**
  - The op-end evaluation goes (−~7 ms) *only if there is no backstop*.
  - Each mutation costs 1–3 value reads plus a before/after compare (needed to skip no-change resets) plus 0–1 version.
  - One version stores in ≈25–30 µs (Fireball: 564 versions ≈ 15 ms, progress log :250-251).
- **Hot paths can ride existing events with an after-value field, adding 0 versions:**
  - `TurnStartEvent` already carries the four counts (`events.py:5784-5792`, written `entity.py:3003-3013`);
  - `StepMovementEvent.movement_cost` (`events.py:4630`);
  - `ActionCostsCommittedEvent` (`events.py:5547-5554`).
- **The long tail** (reactions in handlers, resources, rests, grants, toggles) adds ~0–2 new versions per op. NPCs emit too, because the economy is generic.
- **Total.** ≈0.1–0.5 ms per op, plus the per-seat capture walk and the AI fold per version. With the backstop: H2's cost plus this.
- **Bytes.** Keyed rows of ~25–40 B each plus a node envelope. Spread across more facts (one per step on a move), the SG walk becomes ≈3–5 KB instead of 10.6 KB.

### 2.4 Interactions

- **Volume.**
  - As separate events: ≈5–10 per actor turn (turn start 1, steps 4–6, cost 1–2, reactions 0–2), ≈150–300 per 30-actor round, NPCs included.
  - As fields on hot events: ~0–2 per op.
  - For scale: Fireball has 564 versions per op, and the lazy-version study concluded "event volume is not a remaining multiplier" (progress log :250-256).
- **Handlers.** None subscribe to the new types. COMPLETION-only registration runs no handler (`events.py:2032`). H1 would, however, let future rules react to "reaction spent", which is an opportunity and a hazard.
- **AI.** `knowledge_reduction.py:172-190` folds every version per assignment. Unknown kinds fall through `actor_fact_owner` and `apply_world_fact`, at a few µs each. The AI reads its own economy live, and must not fold PC sheets (hidden information).
- **Replay and journal.** The HUD enters the native history: the `hud_snapshots` side channel goes and the spool carries the facts. Capture needs a reducer branch per new event class (`player/capture.py:484` raises otherwise).

---

## 3. H2 — one engine writer, compared with the actor's own last publication

### 3.1 As specified (~6 points) and why it is not enough

The points:
1. cost commit (`core/base_actions.py:2192-2203`);
2. action completion;
3. action cancel;
4. turn start (`entity.py:2998-3014`);
5. membership commit (`base_block.py:1877-1882`);
6. the out-of-combat reset (`session.py:470-473`);

plus a handler-toggle event and join/leave events.

**What bypasses these points:**
- **A reactor's spend inside another actor's lineage:**
  - reaction spells commit through `reaction_costs.py:109`, not `_on_costs_committed`;
  - `fighter.py:499` (Protection), `infernal.py:201-209`, `encounter.py:765` (surprise), `feats.py:43` (Lucky), `half_orc.py:43`, `barbarian.py:788`, `fighter.py:1335`.
- **Every contextual or activation change.**
- **Grants and progression** outside a membership: off-hand grants, proficiency sources, slot capacity.

So this form needs the op-end sweep anyway, and with the sweep the six points only add events (and intra-op timing that today's HUD doesn't have either).

### 3.2 The exact minimal form

**Call sites:**
- **S1.** `player/session.py:474`: inside `_operation`, after the reset (`470-473`), before `end_cursor`. Publish for each `session.player_uuids` actor. It runs for player commands, AI advances and turn ends alike. Toggles end here too (`session.py:607`), so no `HandlerToggledEvent` is needed.
- **S2.** One startup publication before the startup capture's `end_cursor`: the end of `create_session` / `create_authored_session`, or `player/application.py:33`. The initialization then carries the full sheets as *entering*.
- **Initiative:** native order events at `encounter.py:458` and `527` (+ `475`). Alternatively, S1 compares the order with the last order event, with no writer change.

**The writer.**
- `Entity.snapshot_sheet_state()` is `session.py:142-171`, moved down beside `snapshot_entity_stats` (`entity.py:2460-2474`).
- It is restricted to the non-evented groups. HP, class levels, spellbook, permanent features and prepared selections already travel. Name, portrait, species, background and origin are static, sent once at entering.
- The type `ActorSheetState` goes into `dnd/types/actor.py` beside `EntityStatsState` (`types/actor.py:84-99`). `events.py` cannot import `dnd/player/facts.py`.
- `publish_sheet_state(actor, previous)`:
  - compares explicitly per group: resources by key, handlers by uuid, slots by item uuid, abilities by name, small tuples whole (no `getattr` loops);
  - registers one COMPLETION-only `ActorSheetStateEvent` when something changed;
  - follows the pattern of `conditions.py:2084-2110` (compare with the previous event; `ConditionStateChangedEvent` carries whole `condition_state` + `resulting_stats`).

**The base.**
- **H2a (recommended):** the event stores the whole sheet after-state (engine memory; unchanged groups reuse the previous event's tuples). The wire sends only the changed keys.
- **H2c:** the event stores the changed keys only, plus a folded sheet per actor held by the publisher (a declared copy).
- **Lookup:** one `actor → last sheet event uuid` map owned by `Session` (system state, not an entity attribute). The alternative is a reverse scan of `EventQueue.get_events_by_type` (`events.py:2946`), which is quadratic for idle actors over a long game.

**Wire.**
- The projector discloses the event to seats with `controls(actor)` (the same audience as today's filter, `session.py:135`).
- Rows: changed keys only; an added row whole (with its label); a removal key-only.
- **Initiative per seat:** the order filtered by the composed perception, resent whole on order events and when a combatant enters perception. Leaving sends nothing.
- `CaptureCheckpoint` (`capture.py:159-176`, already one shared actor fold) can fold the sheet events, so a seat that gains control receives the current sheet from the fold, not the live engine.

**Deleted:**
- `snapshot_player_hud` (`session.py:121-135`) and `Operation.hud_by_seat`;
- `sheet_changes`, `hud_patch` and the HUD half of `project_after_values` (`projection.py:2087-2171`);
- `apply_hud` (`reduction.py:566-585`) as a patch fold;
- `PlayerHUDSnapshot` / `SheetChanges` / `SheetPatch` / `PlayerHUDPatch` (`facts.py:117-175`), replaced by one sheet fact;
- `RecordedSequence.hud_snapshots` (`recorded.py:27`, `115-125`);
- the revision gate (`projection.py:2152-2163`).

**Size (estimate):** about +350 / −200 lines, about 12 files. `tests/player/test_transient_value_reads.py:99-115` moves to the pure evaluation function.

### 3.3 Exactness

- **Complete by construction:** the same evaluation function at the same boundary as today's diff. Like today, it can miss only intra-op transients.
- **What can still break:**
  - a write placed after S1 and before `end_cursor`;
  - a second caller of the evaluation.
- **Proof:**
  1. A differential test against recordings made at the base commit (the archived-arm method, `ENGINE_SINGLE_PASS_CHANGE_PROPAGATION_PLAN_2026-10-16.md:678`), over the 31 gallery cases and `tests/player`. At every op end, the controller's folded sheet must equal today's `remembered.hud_snapshot` for that actor.
  2. An op-end oracle: evaluated sheet == folded last sheet event, for every published actor.
  3. An architecture test: `snapshot_sheet_state` has exactly one caller in `dnd/`, and publication has no live HUD read.

### 3.4 Runtime and bytes per op (estimates)

- **Native work.**
  - The same sheet evaluation for all published actors (~7 ms per op today, mostly evaluation).
  - One compare per actor.
  - k COMPLETION-only versions (k = actors whose sheet changed, typically 1 plus reactors; ≈25–30 µs each).
- **Removed from publication:** per seat, the senses union over every observer (26 for blue), the whole-HUD equality, the patch build and the fold. Net: about today's cost or a little less.
- **Memory, H2a:** ≈2–6 KB per op. That is ≈18 MB over a 50-round, 30-actor game, against 8.8 GB RSS in the long game (progress log :259). The memory refactor is next.
- **Bytes.** ≈100–250 B per op with a change: e.g. `{"actor":…, "resources":[["actions",0,1],["spell_slot_3",1,2]]}` plus the node envelope.
  - Fireball ≈0.3 KB instead of 5.1 KB.
  - SG walk ≈2 KB instead of 10.6 KB.
  - Darkness and Sleet: only actual economy changes, likely <0.5 KB.
  - Entering (initialization, control start, journal replay from 0) still sends whole sheets, 91,468 B for blue once.

### 3.5 Interactions

- **Volume:** ≤k versions per op, ≈90–150 per 30-actor round, none for NPCs.
- **Handlers:** none (COMPLETION-only, `events.py:2032`).
- **AI:** folds and ignores them; must never read PC sheets.
- **Replay and journal:** the HUD becomes native. The spool replays it (the human's reconnect answer), and `project_sequence` derives it from lineages. Handler toggles get their first native record as a side effect.
- **Capture:** one reducer branch (`capture.py:484`).

---

## 4. Q5 — is H2 "a per-seat copy"?

**No, it is not per seat.** But it is a comparison with what was last published, which is memory of publication:
- **H2a:** that memory is the engine's own event history (the last sheet event) plus one pointer per actor.
- **H2c:** it is an explicit per-actor copy.

Facts that bear on the human's call:
- It is the mechanism the wire already treats as native for conditions: `publish_owner_state` compares with the condition's last committed publication (`conditions.py:2077-2110`), and the duration ticks compare before and after (`base_block.py:1676-1679`).
- With one controlling seat per actor (the gallery), today's per-seat `remembered.hud_snapshot` also holds one sheet per actor. So "per seat versus per actor" is not the material change.
- What does change:
  - the base moves from publication into the engine's history;
  - the change becomes a native event, seen by the journal, replay and the offline projection;
  - all per-seat HUD code goes.
- **No exact alternative avoids a comparison.** Contextual and activation-driven values have no writer, so exactness needs evaluation at a boundary. Avoiding resends then needs a base, unless the whole sheet is sent each op (91 KB).
- **If the human rejects H2 as memory**, the HUD needs a declared exception (decision 3, third option).

---

## 5. Hybrids considered

| Hybrid | Verdict |
|---|---|
| **H1 on the near-evented hot paths** (TurnStart, step, cost commit) **plus H2 for the rest** | **Rejected.** Channel and movement `current` also change through MAX rows and contextual rows (`normalized_score`), so both writers own the same fields. H2's base must then fold H1's after-values, or it resends: two sources of truth. It buys only intra-op timing, which today's HUD lacks too. A client can animate counters from `StepFact.movement_cost` as presentation. |
| **H2 sheet plus native join/leave order events** | **Recommended.** Initiative is per encounter, has 2–3 explicit writers (`encounter.py:458`, `527`, `475`) and no derived inputs, so H1 is exact and tiny there. The order event carries its own change. |
| **H2 with split evaluation** (counters every op; build groups only for "touched" actors) | Only with the human's OK. It is inexact under activation gates (e.g. suppression of a condition owning `barbarian.py:1052` rows). It saves part of the ~7 ms. |

---

## 6. Comparison

| | H1 (event per change) | H2 as specified (~6 points) | H2 exact (op-end sweep) |
|---|---|---|---|
| Sites changed | ~25 emitters + ~90 parent-event call lines + ~7 bypass reroutes + 5–6 event after-values + 3–5 event types | 6 + toggle + join/leave | 2 (S1, S2) + join/leave (2–3) |
| Lines (est.) | +800–950 / −200, ~45 files | +450 / −200 | +350 / −200, ~12 files |
| Exact? | **No.** Contextual and activation rows have no writer | **No.** Reactors and remote changes bypass it | **Yes** at op granularity (= today) |
| Completeness proof | AST test for direct writes only; the differential test fails without a sweep | Needs the sweep | Differential vs base recordings + op-end oracle + one-caller test |
| CPU per op | ≈0.1–0.5 ms (inexact); + ~7 ms with the backstop | ~7 ms + more versions | ≈ today's ~7 ms minus the per-seat diff |
| New versions | 0–2 per op (fields on hot events) or 5–10 per actor turn; NPCs too | 3–8 per op | ≤k per op (≈1–3); players only |
| HUD bytes per op | ~0.1–0.4 KB, more facts | ~0.1–0.3 KB | ~0.1–0.25 KB |
| Engine hazards | Rollback writes, preflight, orphan roots | Some | None new (one root per changed actor at op end) |
| AI / handlers | Ignore; NPC volume | Ignore | Ignore |
| Replay / journal | Native | Native | Native; `hud_snapshots` deleted |
| Rule fit | Event-native where writers exist; inexact elsewhere | Per-actor comparison | Per-actor comparison with the last event (§4) |
| Memory | Small fields | Like H2a | H2a ≈2–6 KB per op, or H2c ≈100 KB constant (a copy) |

---

## 7. Recommendation

**H2 in its exact minimal form, with join/leave order events for initiative.**

Reasons:
1. **Exactness.** H2 is exact by construction (the same function, the same boundary). H1 cannot be exact for derived values without becoming H2 plus events.
2. **Size.** 2 sites plus 2–3 order sites, against about 45 emitters plus about 90 plumbing lines. There is no rollback, preflight or orphan-root hazard.
3. **Bytes.** Equal or smaller than H1's. Both cut `top.hud` by ~90 %, and neither matters for the 100 KB gate (`top.hud` is 1.6–2.7 % of updates).
4. **CPU.** About today's cost. H1's saving exists only while it is inexact.
5. **One path.** It deletes the per-seat HUD machinery and the side channel, and reuses the engine's existing publish-against-last-publication pattern.

**Decisions for the human:**
- **(a)** Does H2's comparison with the actor's last published event count as event-native (§4)? If not, the HUD needs a declared exception.
- **(b)** H2a (whole after-state in the event, history as the base) or H2c (keyed event plus a per-actor folded copy).
- **(c)** The base pointer: a map in `Session` or an event-store scan.
- **(d)** Drop the already-evented and static fields from the sheet event.
- **(e)** Initiative: order events plus the perception filter, with "leaving: nothing".
- **(f)** Keep op-end timing (today's) or add intra-op points later.

A plan built from this must add the antislop and antiOOP reviewers (AGENTS.md), a schema bump, an SDK digest and a Godot fold note.
