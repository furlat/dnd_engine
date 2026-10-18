# Rule census of the single-pass refactor (2026-10-18)

The human asked for every rule violation the refactor adds to be written down. The rules come from AGENTS.md ("no late imports, no circularity, no getattr or typecheck to cheat; imports form a DAG") and plan §6a ("no new cache or memo attributes on entities, blocks, values, conditions or runtime dataclasses; no manager or registry classes, no lazy properties"; "GC tuning … not fixes").

The census compares the refactor's base `d13e6ad` with the integration head, over `dnd/` and `server/`. Each added line is matched against the removed lines. A call whose text existed before the refactor was moved or rewritten, not added.

## Counts

| Pattern | Added lines | Removed lines | Net |
| --- | --- | --- | --- |
| `getattr(` | 1 (now 0) | 2 | −1 (now −2) |
| `hasattr(` | 0 | 1 | −1 |
| `isinstance(` | 76 | 199 | −123 |
| `setattr(` | 0 | 0 | 0 |
| in-function imports | 0 | 0 | 0 |

Of the 75 added `isinstance` calls, 55 repeat a call the base already made (moved or rewritten), and 20 are new.

## getattr

| Site | What | Status |
| --- | --- | --- |
| `dnd/core/base_block.py` `value_fields()` (PH-2) | A block's values are read by `getattr` over field names recorded per class from `model_fields` annotations. It is narrower than the per-instance `getattr` + `isinstance` scan it replaced. | **Fixed at close (a2ff92854):** each of the 13 value-holding block classes returns its value fields from an explicit `value_fields()`, in declaration order, as tiles already did. `tests/architecture/test_block_value_fields.py` checks that every declared value field is listed, in order. Authoring contract change: a block that holds values must list them. The four example blocks in the block-context tests follow it (d506a0d58). |
| `dnd/core/base_block.py` `_populate_blocks` | A child-block scan by `getattr` over every model field, plus `isinstance(…, BaseBlock)`. | Older than the refactor (the `isinstance` was kept, the value branch removed). Not changed. |

## The 20 new isinstance calls, by kind

**Union fields: a field holds two types and readers test which one (the "typecheck to cheat" kind).**
- `dnd/core/events.py:3068/3070/3168/3170`: `bonus: Optional[Union[int, ValueReading]]` (field at ~2993). Readers branch on `isinstance(self.bonus, ValueReading)`. Fix: the field is one type (the reading), and an int bonus becomes a reading without rows.
- `dnd/entity.py:261`: `target_ac = ac if isinstance(ac, int) else ac.normalized_score`. Same fix: one AC type.

**A target that may be a creature or an object.**
- `dnd/actions.py:1981`, `dnd/actions.py:4790`, `dnd/spatial/area_reach.py:38`: branch on `isinstance(target, BaseItem)`. The engine has no component that states "this target is an object", so these replace older checks on concrete classes. Fix: a target-kind field on the target or its placement (next refactor).

**Dispatch over a closed family of facts or events** (tagged-union reads; `match` would be the same).
- `dnd/player/projection.py:1445/1534/1739/1912`: `SpatialFact` / `EquipmentFact`, the player fact types PW and PV2 introduced.
- `dnd/conditions.py:2813`, `dnd/spells/abjuration.py:943`, `dnd/spells/illusion.py:1285`, `dnd/spells/necromancy.py:2306`: rule code reads whether the triggering event is a spell or action event with an application. These replace reads of an attribute the base event no longer carries.
- `server/worker.py:228`: the worker treats a `ChoicesResponse` differently when it records the packet.

**Modifier kind, read from the result's type rather than the row's own Kind column.**
- `dnd/core/values.py:816` (`_contextual_status`): contextual modifiers are evaluated and filtered by `isinstance(result, payload)`, while each `Row` already has a `kind` column. Fix: filter on `Row.kind` and evaluate only matching rows. Exact if a modifier's evaluated payload always matches its row kind, which must be checked.

**Rule shape.**
- `dnd/classes/fighter.py:1180`: a Shield in the off-hand slot (a rules test).

**Guards.**
- `dnd/core/events.py:3463`: passive replay refuses runtime objects (block, event, value record or callable) in a payload. This is a validation of input, not dispatch.

## Other §6a and AGENTS.md items

- **GC policy in the worker** (`server/worker.py`: no automatic collection inside a request; collect and freeze after the reply). §6a lists GC tuning as "not a fix". The human approved this policy on 2026-10-17 ("i am fine with 1-3"). The post-reply collection is timed per op as `collect_after_ms` and reported beside the op time.
- **Kept answers owned by systems**, each keyed by named revisions:
  - `GridMap._transit` edge answers (PV1a-4), settled on first read and cleared at the bump;
  - the contact target table (PV1a-2);
  - the FOV caches (P5, scoped).
  
  A second one, found by the contact fan-out lane: `SpatialSensesSystem._target_ids` (dnd/blocks/sensory.py, added in da41b695b) is a mutable, append-only intern map holding one id per uuid ever listed, cleared only on `reset`. It is system-owned but neither frozen nor revision-keyed (§6a). Contact-row matching relies on its "a key is never rebound" invariant, stated in the plan. Not changed yet.

  One exception, found later by the navigation lane: `Entity._navigation_traversal` (entity.py:632, added in P5, 6d9528cc4) is a private memo on the entity. It holds the read box and traversal stamp of its last navigation materialization, so a later discovery can tell whether its paths are still current. §6a bans exactly this kind of entity-held memo; it should be a system-owned frozen value, keyed by the grid's traversal stamp. Not changed yet. PV1a-4 settles edge answers on first read instead of at the writer, because eager writes cost +12 ms of unread predicates per Wall of Stone cast. That is a lazy answer inside GridMap: a decision for the human.
- **Second paths still present:** `shadowcast.compute_fov` serves maps without optical boundaries and ignores local crossing owners (PV1a-4 left it untouched). A gallery_crowd-only `long_game` case exists for measurement.
- **Plan text versus code:**
  - One settlement per move step (amended in §5.2, with the human's "seems okay").
  - The discovery bound is `GridMap.manual_object_contact_origins`, where §14.2 #4 names `contact_ring_cells` in Entity.
  - PV2 one-observer seats use the shared-row shape, where plan line 671 says "plain per-observer".
- **Import DAG:** no in-function imports were added. PV1a-4's light-array item (Tile reads a GridMap grid) is not done because it would invert the DAG. The known architecture test failures (dependency_boundaries ×4, ai_import_direction, action_discovery_requirements, presentation_schema_export, content_recovery ×3) all predate this work: r21 is the reference list, and every sweep since matches it.

## Slop removed at close

e260e92e1 removes imports and a map lookup that the perception merges left unused: `CENTER`, `reach_mask` and `cell_key` in sensory.py, `SpatialChannel` in entity.py, and an unused `grid = get_map()`.

## Cleanup lane (codex/enp-cleanup, base 2b2dcc45e)

Items the integrator assigned after the census. Each is done exactly or skipped with its reason. Gallery transcripts (fireball, circle_of_death, sleet_storm, wall_of_stone, spirit_guardians_walk, choices_caster, ai_decision) are compared with the base after each item.

- **Dead code.** `GridMap.publish_tile_state_changed` had no callers and is deleted. `PlayerCausalIndex` / `index_player_lineage` (dnd/player/reduction.py) were called only from `game_obsolete/`. Nothing live or under `tests/` imports `game_obsolete`, and the package cannot be imported anyway (its modules import `game.*`, which no longer exists), so both are deleted.
- **Forcecage crossing query.** `ForcecageZone.blocks_crossing_between` built its admitted-cell set once per section; it is now built once per query, as `SolidWallZone` does (4c66092b2). `allows_contribution_at` only reads. The ground-band `model_copy` stays per section: it copies that section's own geometry, and keeping a banded copy between queries would be a stored derived value on the condition (§6a), refreshed whenever a breach rewrites `sections`.
- **Union fields (fixed).** `D20Event.bonus` is `Optional[ValueReading]`, as `D20RollResultEvent.bonus` already was. It held an int in two places: the unread default 0 on a request, and a seat's detached body, where it was a copy of `dice_roll.bonus`. Both are now None: before the roll no reading exists, and the detached body keeps its total in `dice_roll`, where it already was, including after an Indomitable reroll that read a different bonus. A "reading without rows" would mean making up a reading owner for the request and a total that can disagree with the roll. The two log readers test `is not None`. `determine_attack_outcome` takes an int target number. Its two attack callers pass the read AC's `normalized_score`, the only part it read. **Transcripts:** published updates byte-identical and logs identical on all seven cases. Stored event dumps differ in one field only: an unread D20 request's `bonus` is `null` where the base had `0` (fireball 10, circle_of_death 18, wall_of_stone 1, choices_caster 10 events). The scratchpad check `cln/bonus_projection.py` maps that field and finds everything else identical. The isinstance calls at events.py:3068/3070/3168/3170 and entity.py:261 are gone.
- **Modifier kind (fixed).** `_contextual_status` reads the rows of one (channel, kind) bucket, so the row's kind already selects them; it now keeps the results that are not None instead of testing `isinstance(result, payload)`, and the payload type parameter is gone from it and from `_override`. Exact because every contextual status row returns its kind's payload or None: an AST scan of every `add_modifier(...)` and `Row(...)` in dnd/ and server/ (260 sites) finds three contextual CRITICAL/AUTO_HIT/SIZE/DAMAGE_TYPE rows (Underwater and Charmed auto-miss in conditions.py, the close-range auto-critical in creature_transforms.py), and each callable returns `AutoHitModifier`/`CriticalModifier` or None; `evaluate` returns None when the row is inactive or raises. No call passes a channel or kind as a variable except `add_modifier` itself. The numerical, advantage and resistance readers keep their older isinstance filters (not new in the refactor, not in this item). Transcripts byte-identical to item 3's head.
- **First version at a phase.** `EventQueue.is_first_at_phase` compared wall-clock timestamps. The clock can return the same value for two versions, and then an earlier version at the same phase was missed. It now walks the lineage index, which is in store order, and stops at the event itself. Its one caller (the HasAttacked tracker, on attack execution) always passes a stored version: `register` and `publish_committed_phase` store before dispatch. Transcripts byte-identical.

## How to re-run

The census is the `git diff d13e6ad HEAD --unified=0 -- 'dnd/*.py' 'server/*.py'` scan recorded in the integrator's scratchpad (`logs/rule_census_final.txt`). It counts added and removed lines per pattern and separates new `isinstance` call texts from moved ones.
