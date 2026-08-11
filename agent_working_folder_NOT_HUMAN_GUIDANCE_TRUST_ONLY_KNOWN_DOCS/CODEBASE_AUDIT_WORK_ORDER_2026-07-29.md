# Codebase Audit Work Order — 2026-07-29

Audit of branch `feat-authored-content` for dead code, hacks, and design misfits.
Scope: whole repo except `to_archive/` (deliberately archived, ignored throughout).

## How to read this document

Every item carries a verification tag:

- **[VERIFIED]** — the finding was reproduced by running a command or reading the
  cited code directly during the audit. Trust it.
- **[REPORTED]** — found by a sweep and quoted from the code, but not
  independently re-run. Re-confirm before editing.

**Line numbers may have shifted.** The working tree changed *during* the audit
(three separate collection results in one hour). Locate each finding by grepping
the quoted symbol, not by jumping to the line number.

## Hard constraints for whoever executes this

From `CLAUDE.md` / `AGENTS.md`, non-negotiable:

- **No git operations.** No commit, no checkout, no rollback, no stash. Tommaso
  does all git work.
- **Never run `pytest` over the whole suite.** Run individual files:
  `python -m pytest tests/<area>/test_<name>.py -q`. `--collect-only` over
  `tests/` is safe and fast (~20s) and is the recommended pre-flight check.
- **Zero late imports, zero `TYPE_CHECKING`, zero circular deps.** If you need
  one, the code is in the wrong place.
- **Pydantic models use `model_post_init`, never `def __init__(self, **kwargs)`.**
- **No duck typing** via `getattr`/`hasattr` probing on types this repo owns.
- **`Health.life_state` is the sole creature-lifecycle authority.** Never derive
  lifecycle from HP, `is_active`, or condition names.
- Items marked **DECISION REQUIRED** must not be implemented autonomously. Ask
  Tommaso first — they change architecture or public contracts.

## What is already healthy — do not "fix" these

Measured across five independent sweeps. These invariants hold and the
enforcement machinery works; leave it alone.

| Invariant | Result |
| --- | --- |
| Late imports (imports inside functions) | 0 |
| `TYPE_CHECKING` usage | 0 (only in `content_system/pack_loader.py`, which *forbids* it at AST level, and in `tests/architecture/`, which detects it) |
| Pydantic `__init__` overrides | 0 |
| `TODO`/`FIXME`/`HACK`/`XXX` markers | 1 in 747 files (a test comment describing history) |
| Surviving shims for the deleted AI architecture | 0 |
| `dnd`/`server`/`services`/`custom_ai` importing top-level `ai/` | 0 |
| Generated TS SDK in sync | `generate_typescript_sdk.py --check` → exit 0; `generate_event_contract.py --check` → exit 0; no hand-edits |
| `skip`/`skipif`/`xfail`/`if False:` tests | 0 |
| Duplicate test function names | 0 across ~3300 tests |

Debt in this repo lives in `KNOWN_ISSUES.md`, not in code comments. That is
deliberate. Do not add `TODO` comments.

---

# P0 — Red right now

Current measurement **[VERIFIED]**:

```
python -m pytest --collect-only -q tests/ --continue-on-collection-errors
→ 3287 tests collected, 2 errors
```

Plus one failing test. Fix these three first; all are small.

## P0-1 — `tests/engine/test_spellcasting.py` fails to import

**[VERIFIED]**

```
E ImportError: cannot import name 'register_spells_by_name' from 'dnd.actions_functional'
```

`register_spells_by_name` was removed. `dnd/actions_functional.py` now exposes
only `register_spell(entity, spell_class, caster_level=1, *, spellcasting_source_id=None)`.
No plural or by-name replacement exists anywhere in `dnd/` or `server/`
(grepped for `def register_spells`, `spells_by_name` — no hits).

Dangling references to the removed symbol:

| Location | What it is |
| --- | --- |
| `tests/engine/test_spellcasting.py:10` | import — causes the collection error, 1009 lines of tests dark |
| `tests/engine/test_spellcasting.py:630` | `register_spells_by_name(caster, ["Fire Bolt", "Magic Missile"], caster_level=5)` |
| `tests/engine/test_spellcasting.py:642` | `register_spells_by_name(caster, ["Not A Spell"])` — asserts the unknown-name error path |
| `CLAUDE.md:627,629` | documents it as **public API** |
| `AGENTS.md:669,671` | same |
| `devtools/generate_legacy_behavior_migration_ledger.py:218,222` | cites `#register_spells_by_name_source.1/.2` |
| `tests/manual/test_161_legacy_behavior_migration_ledger.py:221` | maps `"register_spells_by_name": "register_spells_by_name_source"` |

**DECISION REQUIRED.** Two coherent resolutions, and the choice is Tommaso's:

- **(a) Reinstate** `register_spells_by_name(entity, names, caster_level=1)` in
  `dnd/actions_functional.py`, resolving names through `dnd.spells.ALL_SPELLS`
  and raising on unknown names. Keeps the docs, the ledger refs and both tests
  valid, including the `"Not A Spell"` error-path test.
- **(b) Confirm the removal is intended**, then update all seven reference sites:
  rewrite the two test call sites to `register_spell` + an explicit `ALL_SPELLS`
  lookup, delete or rewrite the unknown-name test (the error path it covers stops
  existing), correct `CLAUDE.md`/`AGENTS.md`, and re-generate the behavior ledger.

Do not silently pick (b) by deleting the test.

**Verify:** `python -m pytest tests/engine/test_spellcasting.py -q`

## P0-2 — `tests/manual/test_25_live_replication_streams.py` fails to import

**[VERIFIED]**

```
E ImportError: cannot import name 'live_replication' from 'server'
```

`server/live_replication.py` was deleted (uncommitted ` D`) and its helpers moved
to `tests/manual/live_replication_support.py`. That move was correct — it was
test scaffolding sitting in the production package, imported by nothing outside
`tests/`. Nine other test files already import the new location. This one was
missed:

- `tests/manual/test_25_live_replication_streams.py:14` — `from server import live_replication`
- `tests/manual/test_25_live_replication_streams.py:146` — `inspect.getsource(live_replication.reset_live_stream_state)`

**Fix:** repoint both to `tests.manual.live_replication_support`. Confirm
`reset_live_stream_state` actually moved there; if it did not, that is a second
gap in the move.

**Verify:** `python -m pytest tests/manual/test_25_live_replication_streams.py -q`

## P0-3 — `test_157` creature-ledger citation test is failing

**[VERIFIED]**

```
python -m pytest tests/manual/test_157_legacy_creature_migration_ledger.py::test_every_ledger_row_cites_existing_measuring_test -q
→ 1 failed
E FileNotFoundError: .../tests/manual/test_16_monsters_preset_actors.py
```

`content_data/ledgers/legacy_creatures.json:905,936,998` cite
`tests/manual/test_16_monsters_preset_actors.py`, which is deleted (` D`).
`test_157_legacy_creature_migration_ledger.py:319-331`
(`_top_level_test_names(relative_path)`) opens the cited file with **no existence
guard**, so it raises `FileNotFoundError` instead of producing a readable
assertion.

Note the asymmetry: the sibling `tests/manual/test_156_legacy_item_migration_ledger.py:483-486`
**does** guard with `assert test_path.is_file()` and a message **[REPORTED]**.
The item ledger got the careful implementation; the creature ledger got a sloppy
copy of it.

**Fix, both halves:**

1. Repoint the 3 ledger rows in `content_data/ledgers/legacy_creatures.json` at
   whichever test file now measures that creature coverage (likely a
   `tests/engine/test_manual_19_monsters_and_preset_actors.py` or
   `tests/engine/*` successor — confirm before editing), or regenerate via
   `devtools/generate_legacy_creature_migration_ledger.py`.
2. Add the missing existence guard to `test_157`, copying the message style from
   `test_156:483`. A dangling citation must fail as an assertion, not a traceback.
   The ledger's stated premise is "migration evidence is executable, not an
   unchecked prose citation" — a crash defeats that.

**Verify:** `python -m pytest tests/manual/test_157_legacy_creature_migration_ledger.py -q`
and `python -m pytest tests/manual/test_156_legacy_item_migration_ledger.py -q`

---

# P1 — Correctness bugs

These can produce wrong game outcomes. Ordered by blast radius.

## P1-1 — `Attack._validate` re-dispatches the DECLARATION event three extra times

**[VERIFIED]**

`Event.phase_to()` → `Event.post()` → `EventQueue.register(updated_event)`
(`dnd/core/events.py:740-743`), and `register` notifies every matching handler.
All three attack validators return a `phase_to` into the phase the event is
**already in**:

| Location | Call |
| --- | --- |
| `dnd/actions.py:1387` | `validate_range` → `phase_to(new_phase=EventPhase.DECLARATION, ...)` |
| `dnd/actions.py:232` | `validate_line_of_sight` → same |
| `dnd/actions.py:1417` | `check_ranged_conditions` → same |

`phase_to` is being used as "attach a status message", but its documented
purpose is "Create, post, and return a new event version at another phase" — the
handler broadcast is a side effect nobody intended here.

Consequence: any handler registered on `ATTACK` at `DECLARATION` fires up to four
times per attack. `dnd/spells/abjuration.py:2788` registers `Sanctuary Ward`
exactly there, and its processor **rolls a WIS save and cancels the attack** — so
one attack forces up to four Sanctuary saves. Same pattern at
`dnd/monsters/traits.py:659` **[REPORTED]**.

**Fix:** same-phase state updates must not re-post. Either add a non-posting
update path (e.g. `Event.with_updates(**fields)` returning a copy without
`EventQueue.register`), or have the validators return `self.model_copy(update=...)`
directly. Then audit every `phase_to` call whose `new_phase` equals the current
phase — grep `phase_to(new_phase=EventPhase.DECLARATION` and the EXECUTION/EFFECT
equivalents.

**Write a red test first**: register a counting handler on `ATTACK`/`DECLARATION`,
execute one attack, assert the handler fired exactly once. It should fail before
the fix.

**Verify:** the new test, plus `python -m pytest tests/engine/test_event_lifecycle.py -q`,
`tests/engine/test_combat_actions.py -q`, and the Sanctuary coverage in
`tests/manual/test_protection_reaction_legacy_contract.py -q`.

## P1-2 — `materialize_character` leaks items on rollback, so respec is not exactly reversible

**[VERIFIED]**

`dnd/content_system/character_materialization.py:1032-1066` loots, equips and
ignites items **after** `apply_character_composition`, then on failure:

```python
except Exception:
    if composition_receipt is not None:
        remove_character_composition(entity, composition_receipt)
    raise
```

`remove_character_composition` touches no inventory and no equipment — its only
item-adjacent call is `remove_armor_class_formula_candidate`. Anything already
`loot_item`'d, `equip_item`'d or `torch.ignite`'d before the failing row stays on
the Entity. Appearance is likewise applied outside any receipt
(`character_materialization.py:1015` **[REPORTED]**), so it is also
irreversible.

The pattern to reuse already exists: `dnd/content_system/creature_possessions.py:215-221`
calls `_discard_provisional_items` **[REPORTED]**.

This directly undercuts the "EXACTLY reversible" property that respec depends on.
Note `remove_character_composition` has **no production caller** — only tests and
the two internal rollback paths **[REPORTED]** — so the gap is currently
exercised only under failure, but respec is the feature it was built for.

**Fix:** track provisional items and reverse them in the `except` block, mirroring
`_discard_provisional_items`. Then decide whether item/appearance state belongs
in `CharacterCompositionReceipt` so a single `remove_character_composition` call
is genuinely total. That second half is **DECISION REQUIRED** — it changes the
receipt contract.

**Write a red test first**: make the last holdings row fail (unequippable item in
an equipped slot), assert the Entity ends with an empty inventory, no equipped
items, and no lit torch.

**Verify:** `python -m pytest tests/progression/test_schema2_character_materialization.py -q`,
`tests/progression/test_character_grant_receipt_cleanup.py -q`,
`tests/progression/test_character_respec_rebase.py -q`

## P1-3 — `Entity.is_active` is HP-based and gates lifecycle decisions

**[VERIFIED]**

```python
# dnd/entity.py:2521
@property
def is_active(self) -> bool:
    """Entity is active if it has HP."""
    return self.has_hp
```

```python
# dnd/core/base_actions.py:1264 — the include_dead=False AoE target filter
targets = [uid for uid in targets if (block := BaseBlock.get(uid)) and block.is_active]
```

A `DYING`/`STABLE` creature at 0 HP is silently excluded from "not dead"
targeting, and a `DEAD` creature with HP restored would be included. `CLAUDE.md`
explicitly warns about this exact property ("do not use it for senses because
DYING/STABLE entities at 0 HP remain perceivable"), and `base_actions.py` does the
warned-against thing.

Other lifecycle-gating consumers **[REPORTED]**: `dnd/spells/abjuration.py:3073`
(re-application of an Antimagic-suppressed condition),
`dnd/spells/transmutation.py:835` (Haste Lethargy).

Currently **latent** for schema-2 players, because `dnd/player_character_body.py`
sets `uses_death_saves=False` so 0 HP commits `DEAD` directly. It is live for any
actor that uses death saves.

**Fix:** replace the three lifecycle-gating reads with
`entity.health.life_state is not LifeState.DEAD` (match how `Senses` filters).
Leave non-lifecycle uses of `is_active`/`has_hp` alone. Consider renaming
`Entity.is_active` to make the HP semantics explicit — **DECISION REQUIRED**,
it is a widely-read public property.

**Verify:** `python -m pytest tests/engine/test_life_state_ownership.py -q`,
`tests/manual/test_112_server_life_state_contract.py -q`, and an AoE test with a
DYING target.

## P1-4 — Non-reentrant process-wide GC toggle in a threaded server

**[VERIFIED]**

```python
# dnd/ai/runtime/decision_epoch.py:235
gc_was_enabled = gc.isenabled()
if gc_was_enabled:
    gc.disable()
try:
    ...
finally:
    if gc_was_enabled:
        gc.enable()
```

No lease counting. Called from request handlers (`server/event_server.py:4079`
**[REPORTED]**). Two concurrent threads race: A disables; B observes
`isenabled() == False` and so will never re-enable; A's `finally` re-enables GC
while B is still inside its hot path.

The correct implementation already exists at `ai/subjective/runtime_gc.py:48-70`
— `_lease_lock` + `_active_leases`, restoring only after the last owner releases.
The correct version is in the client package and the broken one in the engine.

**Fix:** move the lease-counted mechanism into `dnd/ai/` (it must not import
`ai/`) and use it in `decision_epoch.py`. Do not simply copy the file — see
D-2 below; this is a case where one implementation should be shared, not
duplicated a third time.

**Verify:** `python -m pytest tests/ai/test_instrumentation.py -q`,
`tests/manual/test_43_ai_runtime_performance.py -q`

## P1-5 — `DiceRollResultEvent` is a false abstraction

**[VERIFIED]**

Three sibling event classes whose shared method is incompatible in each, silenced
by `# type: ignore`:

| Class | `roll_modifications` | `replace_roll` arity | Roll fields |
| --- | --- | --- | --- |
| `DiceRollResultEvent` (`dnd/core/events.py:3766`) | `List[Tuple[str, str]]` | 3 args | `original_roll`, `final_roll` |
| `DamageRollResultEvent` (`:3887`) | `List[Tuple[str, int, int, int, str]]` — `# type: ignore[assignment]` | **4 args** (leading `index`) — `# type: ignore[override]` | `original_rolls`, `final_rolls` (lists) |
| `HealRollResultEvent` (`:3923`) | inherits 2-tuple | 3 args — `# type: ignore[override]` | `original_roll`, `final_roll` |

Verified consequences:

- Every consumer must hand-branch. `dnd/analytics/game_summary.py:848-882`
  `isinstance`-dispatches all three shapes explicitly; the base type buys nothing.
- Two producers bypass `replace_roll` entirely and hand-build damage-shaped
  tuples: `dnd/items/weapons.py:950`
  (`("Unseen Strike", len(event.final_rolls) - 1, 0, result, "1d6 piercing (unseen attacker)")`)
  and `dnd/monsters/traits.py:793`. The audit-trail invariant is owned by nobody
  — three write paths, no validation.
- 10 call sites across `dnd/classes/fighter.py:361`, `dnd/classes/feats.py:50`,
  `dnd/monsters/traits.py:1298`, `dnd/origins/halfling.py:100`,
  `dnd/spells/{abjuration,enchantment,divination}.py` all use the 3-arg form. A
  handler written against the base type breaks on damage events.

This matters because `CLAUDE.md` advertises these events as *the* extension point
for dice manipulation (Great Weapon Fighting, Savage Attacker, Lucky, Portent).

**DECISION REQUIRED** — this is a core event-system contract. Options to put to
Tommaso:

- Unify on a single `RollModification` typed model (handler, index, old, new,
  reason) with `index=None` for single-roll events, one `replace_roll` signature
  taking a keyword `index`, and remove all three `type: ignore`s.
- Or split the hierarchy honestly: a `SingleRollResultEvent` and a
  `MultiRollResultEvent` base, so no consumer needs `isinstance` and no subclass
  overrides its parent incompatibly.

Either way, the two manual-append producers must go through the API.

**Verify:** `python -m pytest tests/engine/test_dice_event_semantics.py -q`
(1500 lines, this is the owning suite), plus
`tests/manual/test_spell_critical_dice_legacy_contract.py -q`

## P1-6 — Fail-open default in the hosted worker proxy authorizer

**[VERIFIED]**

```python
# server/worker_proxy.py:163
if upper_method in {"GET", "HEAD"} or normalized == "session/{session_id}/ping":
    return ProxyRouteKind.OBSERVE
```

Two defects in one line:

1. `normalized` is a **concrete** path (built from
   `"/games/{game_id}/runtime/{worker_path:path}"`), so it can never equal the
   literal template string. Dead disjunct — and redundant with the very next line,
   which already handles `POST session/*/ping`.
2. The `GET`/`HEAD` catch-all means every route added to `event_server.py`
   defaults to `OBSERVE` (reachable by any observer token) instead of `DENIED`.
   The deny list above it is a hand-maintained string mirror of the route table;
   forget to update it and the new route is public. Non-GET correctly falls
   through to `DENIED` at the end of the function.

**Fix:** delete the dead disjunct. Then invert the default so unknown GET paths
return `DENIED` and observe-safe reads are enumerated explicitly — this is the
same fail-closed shape the non-GET branch already has.

**DECISION REQUIRED** for the inversion: it will deny any read route not on the
new allowlist, so the allowlist must be built from the current
`event_server.py` route table in one pass. Coordinate with Tommaso; do not
half-apply it.

**Verify:** `python -m pytest tests/manual/test_110_multi_game_gateway.py -q`,
`tests/manual/test_119_gateway_replay_access.py -q`

---

# P2 — Dead code to delete

All confirmed by repo-wide grep including `tests/`, `sdk/`, `devtools/`, and
docs. Delete unless noted.

| # | Location | Size | Evidence | Tag |
| --- | --- | --- | --- | --- |
| D-A | `dnd/blocks/appearance_catalog.py` | 88 L | Zero importers anywhere. Taxonomy was reimplemented in `dnd/content_system/character_appearance.py` (606 L, 5+ importers, own `runtime_value="NakedBody"` specs). Tracked, committed at `2cc3f36`. | **[VERIFIED]** |
| D-B | `dnd/core/combat_log.py:628,682,714` | 122 L | `format_attack_roll_line`, `format_damage_line`, `format_d20_roll_line` — one occurrence each repo-wide (own `def`), not in `__all__`. Superseded by per-event `generate_combat_log()`. | **[VERIFIED]** |
| D-C | `dnd/core/combat_log.py:588` `get_text` + `:761` `md_bold` | — | Zero references. Note `get_text(verbosity: CombatLogVerbosity)` is the *typed* path and is dead, while the live `get_text_with_children(verbosity: str = "compact")` at `:614` resolves by `getattr(self, verbosity, self.compact)` — attribute probing on its own model with a silent fallback that turns a typo into "compact". Fix by making the live path take the enum. | **[REPORTED]** |
| D-D | `CharacterGrantReceipt.condition_handles` (`dnd/content_system/character_grant_types.py:86`) | field + 7-line loop | Never written anywhere. Its only reader is `character_materialization.py:356`. Two tests **assert it is always empty** (`tests/progression/test_fighter_champion_materialization.py:332`, `test_barbarian_berserker_materialization.py:301`). Its `RuntimeError` guard is unreachable. Delete the field, the loop, the guard, and the two now-vacuous assertions. | **[VERIFIED]** |
| D-E | `ai/observation/`, `ai/protocol/`, `ai/semantics/` | 3 dirs | Contain only `__pycache__` — no `__init__.py`, no source. Graves of the pre-`dnd/ai/contracts` layout. **Before deleting**, note their names survive as wire tags in `ai/codex_tools/session_transcript.py:166,181,205,217` (`payload_type="ai.observation.ObservationSnapshot@v1"`). Decide whether those tags should be renamed — changing them is a recorded-artifact compatibility question. | **[VERIFIED]** |
| D-F | `dnd/core/base_tiles.py:476-522` | ~50 L | `can_exit_to`, `can_see_from`, `can_light_from`, `can_propagate_from` — one occurrence each; `can_enter_from`'s only callers are those dead methods. Their `subjective` and `requesting_entity_uuid` parameters are never read, advertising subjective perception that is not implemented. | **[REPORTED]** |
| D-G | `PolicySpec.maximum_decisions_per_turn` (`dnd/ai/specification.py:190`) and `dnd/ai/policies/basic.py:53` | field | Declared in the policy contract, never read. Enforcement comes from constructor args in `dnd/ai/runtime/assignment.py:209` and `server/registered_ai_controller.py:247`. Either wire the spec through or delete the field — a declared contract the runtime ignores is worse than no field. | **[VERIFIED]** |
| D-H | `dnd/reactions.py:97-99` `create_opputinity_attack_handler` | 3 L | Deliberately misspelled legacy alias forwarding to `create_opportunity_attack_handler`. One occurrence repo-wide including tests. | **[REPORTED]** |
| D-I | `dnd/tiles.py:145-201` `spikes_terrain_factory`; `dnd/tile_conditions.py:730-747` `_apply_to_tiles`; `:721-728` `get_tile_effect_class` | ~90 L | All three self-document as DEPRECATED (one with a runtime `warnings.warn`) and have zero callers; `get_tile_effect_class`'s only caller is the dead `_apply_to_tiles`. The deprecation machinery guards nothing. | **[REPORTED]** |
| D-J | `dnd/items/test_items.py:158` `InteractDoorAction`, `:205` `TestDoorB` | ~90 L | Module docstring says "Door (two approaches) ... pattern examples, not final game items". `TestDoorA` is live in 3 places; `TestDoorB` occurs only inside `test_items.py` plus two `isinstance` checks in `InteractDoorAction`, which is itself reachable only via a content-registry name string. | **[REPORTED]** |
| D-K | `dnd/premade_characters.py:53-62` `PREMADE_LEVEL_5_SORCERER_SPELLS`; `:238,245,252` `*_STARTER_HOLDINGS` | — | Exported in `__all__`, zero consumers. The `*_STARTER_HOLDINGS` constants each call `starter_holdings_for_build` **at import time**. | **[REPORTED]** |
| D-L | `dnd/core/content/durable_characters.py:350` `GrantId` | class | Zero references anywhere. Its siblings `ClassLevelId`/`SpellcastingSourceId` are live. | **[REPORTED]** |
| D-M | `server/event_server.py:4337` `_publish_command_result_ack`; `:1899` `_event_filter_http_exception`; `server/game_directory/canonical.py:43` `text_digest`; `server/player_replication_contract.py:933` `AreaShape`; `server/game_creation_catalog.py:21` `GameCreationCatalogError`; `server/agent_runtime/movement_revalidation.py:39` `from_snapshot` | 6 symbols | Zero callers. `AreaShape` and `GameCreationCatalogError` are in `__all__` but never raised/used. `_event_filter_http_exception` also reaches `EventQueue._all_events`. | **[REPORTED]** |
| D-N | `sdk/typescript/src/validation.ts:303` `decodeServerEvent`, `:308` `isConcreteServerEvent` | 2 exports | Sole reference is each own definition. A further ~50 exports are re-exported via `index.ts` (13 × `export *`) with zero references anywhere — including all 17 `renderProjection.ts` interfaces, `mergeObserverVisibility`, `deliveryWatermarks`, `validateServerEvent`. **DECISION REQUIRED** for the ~50: `export *` makes them public API. Narrowing `index.ts` to intentional exports is the real fix. | **[REPORTED]** |
| D-O | `devtools/generate_event_contract.py:317-341` (`--client-engine-dir`) and `:252-302` (`render_typescript`) | ~75 L | The flag writes `eventContract.generated.json` / `eventModels.generated.ts` — filenames referenced only by the generator itself. `render_typescript` is reachable only from that dead branch; the canonical renderer is `devtools/generate_typescript_sdk.py`. The flag's own help text admits this. Also `generate_typescript_sdk.py:500-507` re-writes the manifest `generate_event_contract.py:331` owns and then **re-execs itself via subprocess** — two entry points, one artifact. Consolidate. | **[REPORTED]** |
| D-P | `tests/architecture/test_no_legacy_character_factory_dependencies.py:21-25,33-35` | ~10 L | `LEGACY_IMPLEMENTATION_PATHS` filters out `dnd/classes/{barbarian,fighter,sorcerer}_factory.py`, while `:43-46` asserts those files do not exist. The filter can never match. The import scan the test also performs is real work — keep that, delete the vestigial filter. | **[REPORTED]** |
| D-Q | `tests/architecture/test_ai_import_direction.py:47-110` | ~90 L | `RETIRED_EVALUATION_IMPORT_PREFIXES`, `RETIRED_EVALUATION_SYMBOLS` (39 names), `RETIRED_SCENARIO_SYMBOLS`, `RETIRED_EVALUATION_SOURCE_PATHS` — denylists for files that no longer exist. **Do not blanket-delete**: `test_deleted_server_owned_ai_contract_modules_are_not_imported` (`:462`) is a legitimate absence guard, but it **omits four** modules the design says are deleted (`server.agent_protocol.observation_replay`, `server.agent_protocol.service`, `server.agent_runtime.service*`, `server.agent_runtime.subprocess_service`). Prune the dead constants **and complete the guard**. | **[REPORTED]** |

Agent-reported additional dead symbols in the engine core, worth a batch pass
with a repo-wide grep each **[REPORTED]**: `dnd/core/events.py` —
`TypedEventListener`, `GenericEventModifier`, `Event.get_trigger`,
`Event.set_parent_event`, `Event.get_history`, `BaseHandler.get_declaration_event`,
`EventQueue.remove_pre_completion_callback`, `EventQueue.remove_event_handlers_by_uuid`,
`EventQueue.get_latest_events`, `EventQueue.get_events_by_timestamp`;
`dnd/core/gridmap.py` — `occupancy_revision`, `is_position_hazardous`,
`create_room`, `unregister_entity`, `get_all_entity_positions`,
`get_visible_entities`, `entity_count`, `subscription_count`;
`dnd/core/values.py` — `get_generation_chain`, `get_generated_from`,
`remove_modifiers`; `dnd/encounter.py` — `remove_combatant`, `get_combatant`,
`get_initiative_order_display`, `get_remaining_action_economy`,
`_advance_entity_conditions`; `dnd/entity.py` — `reduce_condition_by_tag`,
`skill_bonus_cross`, `create_senses_copy_at_position`; `dnd/blocks/health.py` —
`remove_damage`, `take_damage_components`; `dnd/blocks/sensory.py` —
`unregister_observer`.

**Special case:** `Encounter._advance_entity_conditions` has a docstring
asserting a live SRD rule ("*makes turn-based conditions (Dash, Dodge,
Disengage) last until the start of your next turn*") and **nothing calls it**.
Before deleting, confirm whether that rule is implemented elsewhere or is
genuinely missing. If missing, that is a rules bug, not dead code — report it
rather than deleting the evidence. `skill_bonus_cross` is also documented as a
public high-level API in `CLAUDE.md`; deleting it means correcting the doc.

---

# P3 — Hacks worth fixing without a design decision

## H-1 — `getattr` probing over a total method

**[VERIFIED]** `dnd/analytics/game_summary.py:1222-1235` probes a parameter its
own docstring types as "Typed BaseCondition":

```python
semantic_key_getter = getattr(condition, "get_semantic_key", None)
if callable(semantic_key_getter): ...
semantic_key = getattr(condition, "semantic_key", None)
name = getattr(condition, "name", None)
return f"{condition_type.__module__}.{condition_type.__qualname__}"
```

`BaseCondition.get_semantic_key()` (`dnd/core/base_conditions.py:320-326`)
always exists and always returns a non-empty `str` (final branch returns
`f"unbound:{...}"`). **Every branch after the first is unreachable.** Replace all
14 lines with `condition.get_semantic_key()`.

## H-2 — Duplicated reflective accumulator

**[VERIFIED]** `dnd/analytics/game_summary.py:136` and `:428` are the identical
`setattr(self, f, getattr(self, f) + getattr(other, f))` loop over a hardcoded
field-name tuple, in two different classes. Extract one helper (or use a typed
`__add__`).

## H-3 — `walking_cost` / `active_conditions` guarded as if optional

**[REPORTED]** `hasattr(tile, "walking_cost")` at
`server/agent_runtime/observation_projector.py:1547`,
`server/world_projection.py:344-348`, and `:489-493`. `Tile.walking_cost` is a
declared field (`dnd/core/base_tiles.py:37`). Proof the guard is superstition:
`dnd/ai/runtime/state_projection.py:549` reads it unguarded, and the adjacent
line in the same projector reads `tile.walkable` unguarded. Same file `:1549`
does `getattr(tile, "active_conditions", {})` — also a declared `BaseBlock`
field. Remove all four guards.

## H-4 — `getattr` probing on owned models in the AI runtime

**[REPORTED]**

- `dnd/ai/runtime/decision_epoch.py:1147-1157` branches on
  `isinstance(cost, dict)` for a `List[BaseCost]`, then reads four fields via
  `getattr(..., default)`. `BaseCost` (`dnd/core/base_actions.py:536`) declares
  all four. Dead branch + unnecessary probing.
- `dnd/ai/runtime/execution.py:194` — `getattr(event, "outcome_code", None)`;
  `Event.outcome_code` is declared at `dnd/core/events.py:320`.
- `dnd/content_system/builtin_character_builds.py:219-226` — parameter typed
  `object`, then `getattr(class_definition, "level_definitions")` with a constant
  string. Every call site passes a real `ClassDefinition`. Type the parameter.
- `dnd/content_system/character_materialization.py:901-922` — `item: object`
  then `hasattr(item, "stack_count")` / `getattr(item, "max_stack")`, while
  `:915` in the same function correctly uses `isinstance(item, UsableItem)`.
- `dnd/entity.py:2826,2840,2873` — `getattr(self.action_economy, f"spell_slot_{level}", None)`
  in three near-identical copies, when `ActionEconomy` declares `spell_slot_1..9`
  as fields **and** already has the typed dispatcher `_get_spell_slot_value(level)`
  (`dnd/blocks/action_economy.py:614-624`). Same stringly-typed pattern at
  `dnd/blocks/saving_throws.py:284-287`, `skills.py:349`, `abilities.py:362`.

## H-5 — Blind `except Exception` swallows

**[REPORTED]** Each hides a real bug behind a plausible default. Replace with a
narrow exception type plus `logger.exception(...)`, following the pattern already
used at `server/game_gateway.py:288-292`.

- `dnd/core/modifiers.py:346-352` — contextual-modifier evaluation catches
  everything, sets `result = None`, **and memoizes the None**, so any bug in any
  contextual advantage/AC/resistance modifier becomes a silent "no modifier" that
  cannot even be observed intermittently. Worst instance in the list. Ten lines
  up, `:312-315` is `except ValueError as e: raise ValueError(str(e))` — pure
  ceremony that discards the traceback.
- `dnd/encounter.py:914-918` and `dnd/core/events.py:579,1384,1450,1536,1941` —
  `except Exception: pass` around every observer/listener dispatch.
- `server/event_stream.py:715-718` — same, in combat-log source-barrier
  finalization.
- `server/mapeditor_support.py:163-164,194-195` — silently drops unparseable
  saved maps from the list response.

## H-6 — Hand-rolled target save/restore that loses the previous target

**[REPORTED]** `dnd/actions.py:1458-1467` open-codes set/clear of the source
entity's target and calls `clear_target_entity()` on the way out, which sets it
to `None`. `Entity._temporary_target` (`dnd/entity.py:841-861`) is a
`@contextmanager` that does the same thing and **restores the previous target**;
it is used correctly at `entity.py:1742,1770,1809,1884`. The `actions.py` copy
also needs five manual `clear_temporary_targets()` call sites
(`:1527,1561,1579,1597,1668`) that `with` would eliminate. Switch to the context
manager.

## H-7 — `uuid4()` as a default argument, plus a debug print handler in library code

**[REPORTED]** `dnd/monsters/circus_fighter.py:44`:

```python
def create_warrior(source_id: UUID = uuid4(), ...) -> Entity:
```

Evaluated once at import, so every caller omitting `source_id` shares one UUID
for the process lifetime. Same file `:30-37` defines a `print(...)`-only
`attack_processor` registered onto entities when `blinded=True` (`:127-131`).
Remove both.

## H-8 — `locals()` introspection and a pointless sleep

**[REPORTED]**

- `server/event_server.py:3833-3836` — `if "subscription" in locals():` for
  cleanup. The only `locals()` use in the package. Bind `subscription = None`
  before the `try`, or use a context manager; `server/event_stream.py:339-341`
  already does it correctly.
- `server/event_server.py:7000` — `time.sleep(0.5)` after
  `kill_process_on_port`, which already polls to a 5s deadline and raises if any
  PID survives. Delete.

## H-9 — Stale `type: ignore` and a stale docstring

**[REPORTED]**

- `dnd/actions.py:2251` — `# type: ignore[call-arg]` on `stealth_result=`;
  `Hidden.stealth_result` is a declared field (`dnd/conditions.py:1917`), so
  `call-arg` cannot fire. Remove.
- `dnd/blocks/saving_throws.py:142-162` — docstring claims *"Returns a lambda
  function... If proficient: returns lambda x: x (multiplier of 1)"*. There is no
  lambda and no multiplier. Rewrite to describe the actual `max(legacy, sources)`
  behavior — and see D-4 below for the underlying ambiguity.

## H-10 — Redundant lifecycle predicate

**[REPORTED]** `dnd/encounter.py:212-218` — `Combatant.is_alive` has the
docstring "*not dead and has HP > 0*" but never checks HP; it returns
`entity.is_encounter_alive`, i.e. `life_state is not DEAD`. That makes
`if combatant.is_dead or not combatant.is_alive:` (`:685`, `:1187`) a doubled
predicate. Collapse to one and fix the docstring. (The behavior is correct — it
reads `life_state`, unlike P1-3 — only the redundancy and docstring are wrong.)

## H-11 — `os.environ` written inside an HTTP handler

**[REPORTED]** `server/event_server.py:2569-2578` smears a typed
`HostedWorkerAssignment` DTO into five process-global env vars
(`DND_HOSTED_GAME_ID`, `DND_PUBLIC_GAME_BASE_URL`, `DND_WORKER_INSTANCE_ID`,
`DND_WORKER_GENERATION`, `DND_WORKER_RUNTIME_DIR`) so eight unrelated readers can
pick them up. `server/hosted_worker.py:394-399` already sets all five correctly
at spawn time, so the writes are redundant as well as illegitimate. Thread the
DTO instead of the environment. Verify with
`python -m pytest tests/manual/test_109_hosted_game_runtime.py -q`.

---

# D — Duplication and design misfits (DECISION REQUIRED)

Do not refactor these autonomously. Each needs Tommaso to choose a direction.
They are listed because they are the root cause of most of the P1/P2 items:
in every case, two implementations of one concept were allowed to coexist and
then drift.

## D-1 — The subjective projector is forked, and the forks have already drifted

**[VERIFIED]** `dnd/ai/runtime/state_projection.py` (646 L) and
`server/agent_runtime/observation_projector.py` (2553 L) both produce
`ObservationSnapshot` / `ObservationEntityFact` / `ObservationTileFact`. **All 12
same-named private helpers exist in both files** (confirmed by grep):
`_observer_state`, `_session_state`, `_encounter_state`, `_controlled_observers`,
`_damage_affinities`, `_observers_that_see`, `_visible_tile_fact`,
`_adjacent_domain_knowledge`, `_directional_blocks`, `_object_state`,
`_json_safe_state_value`, `_tile_key`. Several are byte-identical
(`_json_safe_state_value`, `_directional_blocks` modulo a docstring).

Drift already present **[REPORTED]**:

- the server's `_object_state` omits `is_hazardous`/`hazardous`, which
  `dnd`'s includes;
- `state_projection.py:148` never populates `combat_logs`
  (`list(self._world.combat_logs) if self._world else []` — always `[]`), while
  the server projector filters visible logs;
- `dnd`'s `_adjacent_domain_knowledge` lacks the server's revision-keyed cache.

Both are live: native AI goes through `state_projection` (via
`dnd/ai/runtime/assignment.py:132`), `RegisteredAIController` through the same,
and `event_server.py:320` through the server projector. **Two AI execution paths
see different worlds.** This violates the stated rule that `dnd/ai` owns
projection and `server` owns transport only. `server/subjective_parity_diagnostics.py`
(785 L, a deliberately independent third projector) is the standing cost of
leaving the fork unresolved.

Highest-value architectural item in the audit.

## D-2 — AI assignment lifecycle implemented three times

**[REPORTED]** `dnd/ai/runtime/assignment.py:395` and
`server/registered_ai_controller.py:512` contain a verbatim
`_live_controlled_entities` (only the error string differs), plus duplicated
`_record_limit_feedback`, `_reset_turn_counters`, `start()` ownership check, and
`_consecutive_canceled_actions` streak logic. `ai/subjective/policy_agent.py` is
a third copy of the same loop. Four independent copies of the `=32` per-turn
decision limit exist (`dnd/ai/specification.py:190` — dead, see D-G;
`assignment.py:39`; `registered_ai_controller.py:43`;
`ai/subjective/policy_agent.py:43` uses **20**). The GC fix in P1-4 lands here.

## D-3 — Five copies of one grant-applier framework, already drifted into a bug

**[REPORTED]** `fighter_`, `barbarian_`, `sorcerer_`, `extra_attack_`, and
`builtin_character_grant_appliers.py` total ~2245 L. Duplicated helpers:
`_grant_id`, `_require_ref`, `_base_receipt`, `_is_first_grant_for_ref`,
`_<class>_level`, `_register_bound_action`, static-modifier installer, handler
installer.

**The drift is already a bug:** `fighter_character_grant_appliers.py:146-147`
guards `entry.content_ref is None → return False`; the barbarian (`:162`) and
sorcerer (`:147`) copies omit that guard and will match the first schedule row
whose `content_ref` is `None`. Fix that guard in all copies now (that part is
safe and does not need a decision); the extraction of the shared framework is the
decision.

Also duplicated bodies: `barbarian:368-392` (`_apply_danger_sense`) vs `:395-418`
(`_apply_fast_movement`) are the same 24 lines, and both re-inline what
`fighter:187-212` already abstracts. The
"add resource contribution → install action/handler → rollback → `_base_receipt`"
block appears 4× in `fighter` alone.

## D-4 — Two competing proficiency authorities reconciled with `max()`

**[REPORTED]** `dnd/blocks/skills.py:159-178` and
`dnd/blocks/saving_throws.py:142-162`:

```python
legacy = proficiency_bonus if self.proficiency else 0
return max(legacy, self.proficiency_sources.apply(proficiency_bonus))
```

The boolean `proficiency`/`expertise` flags (still written by `set_proficiency`
and by every `SkillConfig(proficiency=True)` in `dnd/monsters/`) and the
source-owned `proficiency_sources` ledger are both live. `max()` papers over
which one is authoritative. Given that source-owned receipts are the whole point
of the new progression system, this probably wants to become source-only — but
that touches every monster definition.

## D-5 — `server/event_server.py` hand-rolls the engine's private turn-advance state machine, twice

**[VERIFIED]** `server/event_server.py:5220-5224` (and again at `:5814`
**[REPORTED]**):

```python
sim.encounter.end_turn()
sim.encounter.current_turn_index += 1
if sim.encounter.current_turn_index >= len(sim.encounter.initiative_order):
    sim.encounter._advance_round()
sim.encounter.turn_state = TurnState.NOT_STARTED
```

This is the body of `dnd/encounter.py:778 next_turn()` (lines 788-797) minus the
trailing `return self.start_turn()`, calling the private `_advance_round()` and
assigning `current_turn_index`/`turn_state` from an HTTP handler. Violates
"engine authority stays in `dnd`". Fix is a **public** `Encounter` method (e.g.
`advance_turn_index_without_start()`) used at both sites.

Related private reaches from `server/` **[REPORTED]**:
`event_server.py:1925` (`EventQueue._all_events`),
`mapeditor_support.py:598-601` (`EventQueue._spatial_handlers`,
`._event_handlers`, `._handler_positions`),
`objective_state.py:80` / `mapeditor_support.py:552,891` (`grid._object_positions`),
`world_projection.py:342` (`grid._tiles`).

## D-6 — Gateway routes are degraded hand-copies of standalone routes

**[REPORTED except where noted]** Four instances of the same anti-pattern:

1. `/content/manifest` and `/content/catalog` — bodies byte-identical between
   `game_gateway.py:2516-2549` and `event_server.py:2605-2642`, including the
   ETag/`if-none-match`/304/`Cache-Control` handling. Only the content-system
   source differs.
2. `_character_ruleset_digest` / `_game_creation_ruleset_digest` — the same
   function twice (`game_gateway.py:2872-2888`, `event_server.py:6504-6519`),
   differing only in exception class.
3. `compose_game_creation` / `preview_game_creation` — **drifted**. Both raise
   `game_creation_content_changed` / `game_creation_ruleset_changed` 409s, but the
   standalone version attaches correction context
   (`expected_content_set_digest`, `current_content_set_digest`,
   `event_server.py:6528-6543`) and the gateway version attaches none
   (`game_gateway.py:866-877`). Clients cannot handle these uniformly.
4. `/game-creation/catalog` — **[VERIFIED]** `game_gateway.py:2055` calls
   `build_game_creation_catalog()` with **no arguments**, relying on the
   permissive `ai_policies=None` default in
   `server/game_creation_catalog.py:76-86` (native-only), while
   `event_server.py:6545` passes `ai_policies=_game_creation_ai_policy_options()`
   which merges native + registered providers. The gateway result is
   *accidentally* correct: change that default and the gateway silently
   advertises policies no hosted worker can run. There is also no
   `/admin/ai/providers` route on the gateway and no provider plumbing in
   `hosted_worker.py`, so **no hosted game can use a registered AI provider at
   all**.

Minimum safe fix now: make both call sites pass `controllers=` and `ai_policies=`
explicitly and remove the permissive defaults from `build_game_creation_catalog`.
Closing the hosted-provider gap itself is a larger design question (per-worker
provider registration plus cross-worker capacity accounting) — see
`KNOWN_ISSUES.md`.

## D-7 — `server/external_ai_registry.py` is in the wrong package

**[VERIFIED]** 609 lines of **provider-side** policy execution
(imports `dnd.ai.policies.basic`, `dnd.ai.registry`, `dnd.ai.runner`) living in
the transport package. Its only importers are
`services/ai_policy_server/app.py:22`, `services/ai_policy_server/composition.py:13`,
and `tests/ai/live_socket_provider_app.py:24`. Nothing in `server/` imports it.
Any provider deployment must pull in the whole game-server package to get it.
Move to `services/ai_policy_server/`. `server/external_ai_protocol.py` (the wire
DTOs) legitimately stays.

## D-8 — The shipped native policy uses a different distance metric than the engine

**[VERIFIED]** `dnd/ai/policies/basic.py:915 _grid_distance` returns Chebyshev
`max(|dx|, |dy|)`. The engine canonical metric is floored Euclidean
(`dnd/core/base_tiles.py:18 _tile_distance_feet`). The Chebyshev value drives
`_progress_value` (`:902,907`), which decides whether the AI is advancing — so
approach progress is scored on a metric the reach/range rules do not use.
`custom_ai/tactical/memory.py:172 _known_distance` repeats it inline.
`ai/knowledge/topology.py:84` and `ai/policy/candidates.py:4668` are two further
copies of the *correct* metric. Five implementations, two disagreeing semantics.

## D-9 — `is_dead` re-derived in DTOs, five different ways

**[REPORTED]** `server/world_contracts.py:322-323` (and `:494-498`,
`player_replication_contract.py:253-254`) carry both `life_state` and a derived
`is_dead`. Producers: `world_projection.py:322,541`,
`observation_projector.py:1134,1255,2386` all do
`is_dead=life_state is LifeState.DEAD`, but
`player_replication/world_projection.py:527` does
`is_dead=life_state.value == "dead"` — stringly-typed and inconsistent. The same
file already validates a derived field
(`world_contracts.py:365-367` enforces `conditions == [d.name for d in condition_details]`),
so either drop `is_dead` or add the equivalent validator.

## D-10 — Over-engineering worth pruning

**[REPORTED]**

- `dnd/core/feature_grants.py` — 93 lines around a 4-field dataclass.
  `FeatureCombinationGroup` has one member, is only ever its own default, **and
  is then validated to equal that member** (`:54-57`) — a check that cannot
  fail — and no consumer reads it. `AttackMultiplicityApplicability` likewise
  (its only consumer, `dnd/blocks/action_economy.py:431-432`, passes the
  default). `required_weapon_tags` / `required_body_tags` /
  `required_action_refs` are never set to a non-default anywhere, and the
  docstring says they are for "**future** grants".
- Same single-member-enum-never-read pattern: `ConditionApplicationPolicy`
  (`dnd/core/content/effects.py:58`), `ItemStackCompatibility`
  (`dnd/core/content/item_definitions.py:19`).
- `dnd/core/content/icon_bindings_generated.py` — **[VERIFIED by running]**
  669/669 entries have `value[0] == key.split('#')[1]`, and 669/669 have a
  `disposition` fully derivable from whether `icon_key is None`. The "stale
  contract" check at `dnd/core/content/descriptors.py:172-186` builds the key
  from the same two fields it then compares — structurally unreachable. ~669
  lines of zero-information data plus a dead check, inside a 4029-line generated
  file. Fix the generator, not the file.
- **22 field-less Pydantic `*Parameters` models**, 11 existing solely to satisfy
  `creature_factory(parameters=...)` and immediately discarded via
  `_ = parameters` (`dnd/player_character_body.py:104`,
  `dnd/premade_characters.py:149,177,203`).
- `dnd/core/content/durable_characters.py:333-356` `_StableProgressionId` — a
  1-field frozen model whose only logic uses `cls.__name__` as an error label;
  one of its three subclasses is dead (D-L) and all three accept identical input.
- `character_build_validation.py:2300-2357` re-enumerates the `_SingleRefChoice`
  / `_MultiRefChoice` subclasses by name in three separate `isinstance` tuples
  instead of using the base classes, so adding a choice type requires editing all
  three. Visible consequence: `_choice_all_refs` has two adjacent branches both
  returning `()` (`:2348-2356`), and `StartingApparelPackageChoice` is checked
  against `allowed_refs` but never `_resolve_declaration`'d, unlike every other
  single-ref choice (`character_build_validation.py:1924-1929`).

## D-11 — `extra_attack` family installer reads runtime state, not the sealed revision

**[REPORTED]** `dnd/content_system/extra_attack_character_grant_appliers.py:95`:

```python
if not entity.action_economy.get_attack_multiplicity_grants():
    return None
```

The install decision reads mutated `Entity` state instead of
`preview.grant_schedule`, and depends on running strictly after every rank
applier (`character_materialization.py:630` calls it after the grant loop). Its
receipt `grant_id` comes from an inline magic string
`"character-structural-family:v1:extra_attack"` with `grant_token=None`, so it is
not addressable by token like every other grant. Violates "immutable revisions
are authoritative; the runtime Entity is a derived projection."

## D-12 — Silent-drop whitelist in the applier dispatcher

**[REPORTED]** `dnd/content_system/builtin_character_grant_appliers.py:224-234`
raises for an unmatched `content_ref` only when
`definition_kind in {CLASS_FEATURE, FEAT}`; every other kind `return None` and
the grant is **silently dropped**. A `TRAIT`, `SUBCLASS`, `SPECIES` or
`BACKGROUND` structural grant with no installed applier vanishes with no
diagnostic — the inverse of the exhaustive-receipt intent.

## D-13 — Type hole in receipt construction

**[REPORTED]** `dnd/content_system/builtin_character_grant_appliers.py:134`
declares `modifier_handle: ModifierHandle | None = None`, and `:189` passes
`modifier_handles=(modifier_handle,)`. It is non-`None` on the success path
today, but the receipt's declared element type is violated and
`remove_character_composition:435` would `AttributeError` on `handle.value_uuid`.
Build it as a list, like the sibling `proficiency_handles`.

## D-14 — Receipt digests copied but never verified; asymmetric proficiency removal

**[REPORTED]**

- `CharacterCompositionReceipt.definition_revision/definition_digest/loadout_revision/loadout_digest`
  (`character_materialization.py:102-105`) are written and **never read** — grep
  for `receipt.definition_digest` etc. returns nothing in `dnd/`, `server/`, or
  `tests/`. (The *revision* digests are genuinely verified at
  `durable_characters.py:1607,1738`, just not through the receipt.) Either verify
  them on removal or drop the fields.
- `character_materialization.py:285-321` `_remove_proficiency_handle` **silently
  returns** on a bad `subject_id` prefix, while the matching
  `_install_proficiency:159-283` **raises** on the same condition. The silent
  returns are unreachable given install raises — dead defensive code hiding a
  real asymmetry.

## D-15 — Parallel ad-hoc instrumentation inside `dnd/ai`

**[REPORTED]** `dnd/ai/runtime/decision_epoch.py:1243-1345` interleaves 15+
`time.perf_counter()` calls with logic and threads a hand-rolled
`record_timing: Optional[Callable[[str, float], None]]` through six functions
(`:128,216,232,445,1247`). This is a second timing system beside the canonical
`dnd/ai/instrumentation.py:156 AIInstrumentation.measure`. The native path passes
`None` for all of it; the sole consumer is `server/event_server.py:4371` — i.e.
the parameter exists so `server` can inject its own clock into `dnd/ai`, which
contradicts "`dnd/ai` owns all timing/instrumentation".

Related dead/near-dead in the same file: `:212`
`_build_affordance_set_from_actions` is a private forwarding wrapper that discards
the execution authority and is called only by `tests/manual/test_31_*` and
`test_43_*`; production uses the two-value version at `:149`.

## D-16 — Redundant declarative/imperative policy gating

**[REPORTED]** `dnd/ai/policies/basic.py:51 BASIC_POLICY_SPEC` expresses tag sets
and `minimum=0.000_001` thresholds declaratively as `PolicyRuleSpec` rules, and
`:806 _has_positive_policy_utility` restates the same tag sets and thresholds
imperatively — in the same file. Also `:455-466 _canonical_tags` is a provable
no-op: `row.tags` is built only by `decision_epoch.py:1225 _display_tags`, whose
only `ActionTag` source is `semantics.tags`, so the loop can never add a member,
and its `except ValueError: continue` fires by design on the non-ActionTag
display strings.

## D-17 — Score-max + tie-break selection implemented three times

**[REPORTED]** `dnd/ai/specification.py:251-266` (`DataDrivenPolicy.decide`),
`custom_ai/tactical/policy.py:167` (`_select`), and `ai/policy/utility.py:26`
(`UtilityArbiter._sort_key`) all implement: max score, then min by
`(replay_key or (candidate_id,), candidate_id)`. Also
`dnd/ai/runtime/decision_epoch.py:1096` and `:1128` are two verbatim copies of
the same 11-key cost-profile construction in adjacent functions, with a third at
`ai/policy/economy.py:347`.

## D-18 — 53 test files hand-clear private registries despite a public helper

**[REPORTED]** `dnd/runtime_reset.py:18 reset_engine_runtime()` exists and 70
files use it. In parallel, **53 files** poke `BaseObject._registry.clear()`,
`BaseBlock._registry.clear()`, `BaseValue._registry.clear()`,
`Dice._registry.clear()`, `Entity._entity_registry.clear()`, `EventQueue.reset()`
— **each an arbitrary different subset**. Examples:
`tests/engine/test_entity_composition.py:51-53`,
`tests/engine/test_dice_event_semantics.py:77-82`,
`tests/manual/test_103_worker_game_summary_store.py:43-49`,
`tests/engine/test_action_discovery.py:47-49`,
`tests/engine/test_block_context.py:86-88`,
`tests/engine/test_combat_actions.py:65-67`,
`tests/engine/test_encounter_apis.py:120-122`.

These fixtures are what guarantee isolation across ~3300 tests, so some tests
leak state and nothing tells you which. Compounding it: `tests/conftest.py` is
**14 lines with one fixture** and there are **zero** per-package conftests. The
`_reset_engine` fixture body is duplicated in 18 files (identical modulo a
`grid_size` arg), `clean_runtime` in 8 (byte-identical in 4), and 13 further
non-trivial helper bodies are byte-identical across files (`_remove` ×3,
`fixed_randint` ×2, `_recipe` ×2, `_parse_sse` ×2, ...).

The repo already has the right pattern — 7 `*_support.py` modules in
`tests/manual/`, all genuinely consumed (`tests/ai/support.py` by 85 files) — it
just is not applied to resets. **Highest-value consolidation available**, but it
touches 53 files, so agree the target shape with Tommaso first.

---

# T — Test-suite and docs hygiene

## T-1 — Test numbering is meaningless but used as a cross-reference key

**[REPORTED]** 23 numbers collide across 60 files in `tests/manual/`. Two
systematic authoring accidents rather than 23 independent ones:

- **101→104**: a `codex_*` series (`101_codex_local_inspection`,
  `102_codex_representation_projector`, `103_codex_representation_runtime`,
  `104_codex_subjective_geometry`) collides slot-for-slot with a
  directory/summary/artifact series (`101_game_directory_*`, `102_game_summary`,
  `103_worker_game_summary_store`, `104_game_artifact_store`).
- **178→181**: a `*_content_identity` series collides slot-for-slot with an
  item/possession series.
- Plus the D80 `*_legacy_contract` run (126, 131, 133, 134, 135, 138) numbered
  from the same pool as the live spell/item series — 6 collisions in one batch.

`test_189_game_creation_visual_preview.py` is new/untracked and **took an
already-occupied slot**. Meanwhile 21 files in `tests/manual/` carry no number at
all. Slot *recycling* after deletion is deliberate (`test_37`, `test_71`,
`test_73`, `test_84` are all being reused) — which is precisely why the number is
not a stable key.

No rule is being violated because **no rule is written down**: `AGENTS.md`
mentions `tests/manual/` once and states no numbering convention; `CLAUDE.md`
never mentions it. Yet `KNOWN_ISSUES.md` and `content_data/ledgers/*.json` use
`test_NNN_name.py::test_fn` as a stable cross-reference key — which is how P0-3
happened.

**DECISION REQUIRED:** either write the convention into `AGENTS.md`/`CLAUDE.md`
and enforce uniqueness with a guard test in `tests/architecture/`, or drop numbers
entirely and follow the 21 unnumbered files. Do not renumber anything without
that decision — renumbering invalidates every ledger and `KNOWN_ISSUES.md`
citation.

## T-2 — `KNOWN_ISSUES.md` cites 13 nonexistent test files

**[REPORTED]** Most sit in the Historical Issue Ledger (beyond line ~959), which
is defensible. **One does not:** `KNOWN_ISSUES.md:348` is inside the *active*
"Canonical AI hard cut" issue and cites deleted
`tests/manual/test_38_ai_validation_server_start.py`. Fix that one; leave the
historical ledger alone.

Full dangling list: `test_38_ai_validation_server_start.py` (:348, 998-1006),
`test_35_subjective_external_ai.py`, `test_23_standard_arena_game_modes.py`,
`test_29_external_ai_subprocess.py`,
`tests/engine_book/test_architecture_surface_audit.py`,
`test_39_ai_validation_harness.py`,
`tests/engine_book/test_manual_18_class_features_feats_factories.py`,
`tests/engine_book/test_srd_rule_mapping.py`,
`test_55_gauntlet_live_watcher_server.py`,
`tests/book_examples/test_public_mdx_snippets.py`,
`test_142_class_action_legacy_contract.py`, `test_15_class_features.py`,
`tests/test_equipment_api.py`. Also 8 dangling test refs in
`agent_docs/plans/SINGLE_PLAYER_PROFILE_AND_CHARACTER_PROGRESSION_PLAN_2026-07-26.md`.

Separately: `examples/` **no longer exists**, but `CLAUDE.md` instructs
`python examples/test_<feature>.py` throughout and `KNOWN_ISSUES.md:2002`
references it. Update the testing instructions to `tests/`.

## T-3 — `tests/engine/` carries two parallel naming families

**[REPORTED]** 10 of 37 files are leftover `test_manual_NN_*` twins of
topic-named files covering the same chapter:

| Topic file | tests | Legacy twin | tests |
| --- | --- | --- | --- |
| `test_standard_conditions.py` | 16 | `test_manual_10_standard_conditions.py` | 6 |
| `test_entity_composition.py` | 17 | `test_manual_07_entity_composition.py` | 4 |
| `test_grid_pathfinding.py` | 23 | `test_manual_11_grid_tiles_terrain_movement.py` | 6 |
| `test_combat_actions.py` | 26 | `test_manual_14_core_combat_flow.py` | 6 |
| `test_condition_lifecycle.py` | 13 | `test_manual_09_conditions.py` | 6 |

The `engine_book/` → `engine/` migration renamed some files and not others.
Identifier overlap for the conditions pair is 0.46 — the highest cross-family
pair in the repo. Encouragingly this is the *only* near-duplicate cluster: no
file pair in `tests/` exceeds 0.58 overlap, and the top pair (barbarian vs
fighter materialization) is legitimately parallel class coverage.

## T-4 — One assert-free test

**[REPORTED]** `tests/manual/test_36_seamless_subjective_runtime.py:136`
`test_runtime_service_readiness_requires_successful_stream_sync` — 18 lines, no
`assert`, no `pytest.raises`. It builds a `SubjectiveRuntime`, calls
`wait_until_stream_synced(timeout=0.5)`, closes. Its docstring claims readiness
succeeds only after the pump consumes a sync, but nothing observes the sync
cursor. Its sibling at `:157` does use `raises`. This is the only genuine
instance — the other ~120 assert-free functions all delegate to `pytest.raises`
or to `_assert_*` helpers that assert internally.

## T-5 — Enormous single test functions

**[REPORTED]** A failure at assert 12 hides asserts 13-88. Worst:
`tests/engine/test_spell_families.py:822-1167`
`test_eb_15_025_protective_abjurations_prevent_and_absorb_effects` — **345 lines,
88 asserts**, spanning Protection from Poison, Poisoned cleanup, and unrelated
abjurations. Others ≥40 asserts:
`tests/progression/test_barbarian_berserker_materialization.py:244` (67/268),
`tests/engine/test_standard_conditions.py:243` (61/115),
`tests/progression/test_fighter_champion_materialization.py:181` (55/309),
`tests/manual/test_178_remaining_possession_item_roots.py:135` (48/90),
`tests/manual/test_186_character_directory_service.py:641` (48/215),
`tests/manual/test_122_canonical_replication_runtime.py:396` (44/178),
`tests/manual/test_102_game_summary.py:491` (43/55),
`tests/manual/test_11_equipment_inventory_and_items.py:724` (43/162),
`tests/manual/test_103_worker_game_summary_store.py:149` (41/92),
`tests/manual/test_153_registered_ai_game_creation.py:234` (40/203).
Split opportunistically when touching them; not worth a dedicated pass.

## T-6 — 67 assertions on private implementation details

**[REPORTED]** Highest-value examples:
`tests/manual/test_113_subjective_replication_routes.py:286,297`
(`canonical_subjective_replication_runtime._contexts == {}`),
`tests/manual/test_187_standalone_local_game_lifecycle.py:621`
(`event_server._publish_local_terminal_game(...)`),
`tests/manual/test_160_content_pack_loader.py:509` (`pack_loader._hash_pack_directory`),
`tests/engine/test_spellcasting.py:406-413` (8 asserts on
`cantrip._get_cantrip_dice_count`),
`tests/engine/test_life_state_ownership.py:139-183` (`grid._light_sources`),
`tests/engine/test_grid_pathfinding.py:631-632` (`zone._compute_affected_positions()`),
`tests/engine/test_effect_origin.py:54,67` (`zone._protection_spell_level()`),
`tests/engine/test_items_inventory_equipment.py:901,908` and
`tests/engine/test_spell_families.py:2716-2738` (`torch._light_source_uuid`).
Convert to public-surface assertions when touching the owning module.

## T-7 — An architecture guard shells out to `ripgrep`

**[REPORTED]** `tests/architecture/test_ai_import_direction.py:154-172` runs
`subprocess.run(["rg", "-l", "--glob", "*.py", ...])`. `rg` is an undeclared
binary dependency (`pyproject.toml` lists none), so on a machine without it the
test raises `FileNotFoundError` instead of reporting a missing prerequisite. The
same file already maintains a pure-Python `ignored_directories` filter
(`:146-151`) duplicating the `--glob !**/...` args, and every other guard in
`tests/architecture/` uses `ast` + `rglob`. Port it.

## T-8 — Stale plan docs present the deleted AI architecture as current

**[REPORTED]** These describe modules that no longer exist and will actively
mislead anyone (human or agent) reading them for orientation:

- `ai/UNIFIED_AGENT_ARCHITECTURE.md:334-460` — §7 "Dependency Direction" and §8
  "Current Package Layout" list `server/agent_protocol/{immutable,semantics,control,observation}.py`,
  `agent_runtime/{action_semantics,epochs,service,service_manager,subprocess_service}.py`,
  `gauntlet.py`, `external_agent.py`, `external_selfplay.py`, `evaluation/` — all
  deleted — and asserts `server.agent_protocol`/`server.agent_runtime` are
  "game-server core", which is now false (contracts live in `dnd/ai/contracts`).
- `ai/AGENT_SIDE_CLIENT_PLAN.md:44,279-280,326,1336`
- `ai/CODEX_SUBJECTIVE_REPRESENTATION_PLAN.md:79`
- `ai/CURRENT_AI_LIMITS_AND_NEXT_GENERATION.md:559` treats deleted
  `external_selfplay.py` as an active release gate.

`ai/readme.md` is correct and updated — use it as the model. Add a
"superseded" header to the stale docs or move them under `to_archive/`.

## T-9 — `CLAUDE.md` is behind `AGENTS.md`

**[VERIFIED]** `CLAUDE.md` was last updated at commit `b2b3930`; `AGENTS.md` got
the `d0d17c8` update plus an uncommitted edit. They diverge by **177 diff lines**.
`CLAUDE.md` — the file auto-loaded into agent context — has **no** content-system
or character-progression guidance, does not list the new dependency-neutral
leaves (`dnd/core/proficiency_types.py`, `progression.py`, `feature_grants.py`)
that the uncommitted `AGENTS.md` edit adds, still documents removed
`register_spells_by_name` (P0-1), and still instructs `python examples/test_*.py`
against a deleted directory (T-2).

Sync `CLAUDE.md` from `AGENTS.md`. This is cheap and it improves every subsequent
agent session.

## T-10 — Repo hygiene

**[REPORTED]** Six junk files are **tracked in `HEAD`** (`git check-ignore`
reports NOT IGNORED for each): `KNOWN_ISSUES.md.orig`,
`ai/policy/generations/current_candidate.py.orig`,
`ai/policy/generations/registry.py.orig`, `ai/policy/source.py.orig`,
`cli_debug.log`, `entity_snapshot.json`. All six are ` D` in the working tree, so
the in-flight refactor is already removing them — **but `.gitignore` (36 lines)
has no `*.orig`, `*.rej`, `*.bak`, `*~`, or `*.log` rule**, and four `.orig`
files at once means this has already recurred. Add those rules.

Also: `lore.md` is 0 bytes and tracked; `to_archive/` is listed in `.gitignore`
but **1277 files are still tracked** (gitignore does not untrack — the exclusion
is cosmetic); and 7 of 36 `.gitignore` lines point at a `/ui/` tree that no
longer exists.

Properly ignored and fine — do not touch: `Tomb of the Serpent_Kings v4.pdf`,
`game_logs/`, `.runtime/`.

## T-11 — The TypeScript SDK is behind no automated gate

**[REPORTED]** No `.github/`, no `Makefile`, no CI config anywhere.
`sdk/typescript/package.json` defines `test`/`check`/`build`, and no Python test
shells out to `npm` or `tsc` — `tests/manual/test_98_typescript_replication_sdk.py`
only exercises the Python generator side. So the 10 `src/tests/*.test.ts` files
and `tsc --noEmit` run only when a human remembers. Generated output **is**
currently in sync (both `--check` runs pass), so this is about keeping it that
way.

Also `sdk/typescript/IMPLEMENTATION_PLAN.md` is 1435 lines of plan with zero
completion markers, committed beside the code it plans.

---

# Do NOT "fix" these — verified deliberate

Three findings look like defects and are not. Leave them unless Tommaso says
otherwise.

1. **Error payloads expose every session.** `server/session.py:377` puts
   `known_sessions: [s.to_dict() ...]` — including each player's
   `controlled_entities`, `observer_entities`, `active_observer_uuid` — into
   action-authority failure details, and `validate_action:436-445` returns it on
   a **401 `invalid_session`**, i.e. before authorization. **[VERIFIED]** This is
   an information-disclosure property in a PvP server, **but it is deliberate and
   contract-pinned**: `tests/engine/test_encounter_apis.py:1311,1319,1368,1538`
   and `tests/manual/test_18_sessions_api_client_contract.py:274,284` assert its
   presence and contents, and `tests/architecture/test_source_model_hygiene.py:762`
   *mandates* structured correction payloads over bare strings. Raise it with
   Tommaso as a design tradeoff; do not unilaterally strip the field.
2. **`server/subjective_parity_diagnostics.py` is a third world projector**
   (785 L). **[VERIFIED]** Its module docstring explicitly states it must not
   import the projector it validates — it is an independent differential-testing
   oracle. Legitimate. (Its existence is evidence for D-1, not a defect itself.)
3. **`server/character_equipment_mutation_worker.py`,
   `server/game_creation_preview_worker.py`, `ai/codex_tools/heavy_cli.py` look
   unimported.** **[VERIFIED]** They are launched as `python -m` subprocess
   module strings from `server/character_equipment_mutation.py:135`,
   `server/game_creation_preview.py:133`, and
   `ai/codex_tools/wire_cli.py:257`. Live. Any automated dead-module scan will
   flag them — do not delete.

Also note **`worker_generation` is permanently `1`** **[REPORTED]** — zero
increments repo-wide, yet threaded through four SQLite tables with
`CHECK (worker_generation >= 1)` and a `UNIQUE (worker_id, worker_generation)`
index, plus validation in `game_gateway.py:315-343,1985-1997`. Given the open
`KNOWN_ISSUES.md` entry about durable terminal-ready manifests and gateway
restart adoption, the increment is probably *intended and unfinished*. Do not
delete the plumbing; ask.

---

# Suggested execution order

1. **P0-2** and **P0-3** — mechanical, unblock the suite. **P0-1** needs the
   decision first.
2. **T-10** `.gitignore` rules — one line each, prevents recurrence.
3. **T-9** sync `CLAUDE.md` from `AGENTS.md` — improves every later session.
4. **P1-1** and **P1-2** — the two bugs that change game outcomes. Red test
   first for each.
5. **P1-3**, **P1-4** — lifecycle gate and GC race.
6. **P3** H-1 … H-11 — independent, small, no decisions needed. Batch them.
7. **P2** dead-code deletions — batch, but honour the three noted special cases
   (D-E wire tags, `_advance_entity_conditions` possible rules gap, D-Q
   incomplete guard).
8. **D-3**'s missing `content_ref is None` guard in the barbarian and sorcerer
   appliers — safe to fix immediately, ahead of the framework extraction.
9. Everything else in **D** — bring to Tommaso with options before writing code.

## Standing verification loop

After each change:

```bash
source .venv/bin/activate
python -m pytest --collect-only -q tests/ --continue-on-collection-errors | tail -3
python -m pytest tests/architecture -q
python -m pytest <the specific owning test file> -q
```

`tests/architecture` is fast (~40s, 38 tests) and guards import direction,
dependency boundaries, and the AI boundary — run it after any move or deletion.
Never run the whole suite.

## Audit method, for reproducibility

Five parallel read-only sweeps (engine core; server; the four AI packages;
content/progression; tests/SDK/devtools/hygiene) plus independent mechanical
scans: AST import-graph for unreferenced modules and public symbols, forbidden-
pattern greps, `pytest --collect-only`, and direct execution of the specific
failing tests. Every **[VERIFIED]** item was reproduced by command or by reading
the cited code. `to_archive/` was excluded throughout.
