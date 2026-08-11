# Codebase Audit Re-scan — 2026-07-30

Delta against `agent_docs/CODEBASE_AUDIT_WORK_ORDER_2026-07-29.md` and the
remediation ledger `agent_docs/plans/CODEBASE_AUDIT_CLOSEOUT_2026-07-29.md`.

Tree state: branch `feat-authored-content` @ `4ebe523`, plus **214 modified /
17 untracked / 4 deleted** files (+8,102 / −10,638) not on `HEAD`.

Verification tags: **[VERIFIED]** = reproduced by running a command or reading
the cited code during this re-scan. **[REPORTED]** = found by a sweep, quoted
from code, not independently re-run.

> **Coverage:** all five sweeps completed (engine core, server, AI packages,
> content/progression, tests/docs/hygiene). The server sweep reported last and
> found the most severe defect in this re-scan — see **P0-0**, which also
> supersedes the diagnosis of P1-F.

---

# 1. Executive delta

## The remediation pass was real and large

Of the previous audit's findings, **the great majority are genuinely fixed**,
and several were fixed more cleanly than the work order proposed.

| Previous | Status | How |
| --- | --- | --- |
| **P0-1/2/3** — three red test files | **FIXED** | all three collect and pass **[VERIFIED]** |
| **P1-1** — Attack DECLARATION dispatched ≤4× | **FIXED** | new non-posting `Event.with_updates()` (`dnd/core/events.py:723`); zero `new_phase=EventPhase.DECLARATION` repo-wide; regression at `test_combat_actions.py:312` asserts `declaration_calls == 1` **[VERIFIED]** |
| **P1-3** — `is_active` HP-based lifecycle gate | **FIXED (better than proposed)** | `Entity.is_active` itself now returns `health.life_state is not LifeState.DEAD`, `has_hp` split out — the three call sites became correct by construction **[VERIFIED]** |
| **P1-4** — non-reentrant GC toggle | **FIXED (right layer)** | `dnd/ai/runtime_gc.py` lease-counted under a `Lock`; the only `gc.disable()` in the repo; client copy deleted **[VERIFIED]** |
| **P1-5** — `DiceRollResultEvent` false abstraction | **FIXED** | typed `RollModification` + `DamageRollPacket`; `type: ignore` 5 → **1**; both manual-append producers use the API; `DamageRolledEvent` deleted **[VERIFIED]** |
| **P1-6** — worker-proxy fail-open GET | **FIXED** | `worker_proxy.py` now ends `return ProxyRouteKind.DENIED`; regression in `test_109_hosted_game_runtime.py` asserts DENIED across 10 route shapes **[REPORTED]** |
| **D-1** — forked subjective projector (biggest finding) | **FIXED** | `server/agent_runtime/observation_projector.py` (2,553 L) deleted; one owner `dnd/ai/runtime/subjective_projection.py`; `is_hazardous` and the revision-keyed cache preserved **[VERIFIED that the file is gone]** |
| **D-2** — assignment lifecycle ×3 | **FIXED** | new `dnd/ai/runtime/assignment_lifecycle.py`; `_live_controlled_entities` gone; `ai/subjective/policy_agent.py` (535 L) deleted **[REPORTED]** |
| **D-3** — five-copy applier framework + the `content_ref is None` guard drift | **MOSTLY FIXED** | new `character_grant_applier_runtime.py` owns 8 shared helpers; the guard lives once **[REPORTED]** |
| **D-4** — two proficiency authorities reconciled by `max()` | **FIXED** | `proficiency`/`expertise` are now derived over `proficiency_sources`; no `max(legacy, …)` **[VERIFIED]** |
| **D-8** — five distance implementations, two semantics | **FIXED** | one owner `dnd/core/geometry.py grid_distance_cells` (floored Euclidean); zero Chebyshev in any AI module **[REPORTED]** |
| **D-16/D-17** — duplicate policy gating and ranking | **FIXED** | one `policy_candidate_rank_key`; imperative whitelist removed **[REPORTED]** |
| **D-O** — generator dead branch + self-re-exec | **FIXED** | one process, one `render_typescript`, no `subprocess` **[REPORTED]** |
| **Two strict xfails** | **FIXED, ledger consistent** | zero `xfail` markers under `tests/`; both files pass; `KNOWN_ISSUES.md:145-178` marks them RESOLVED and names the passing tests. Cleanest item in the audit. **[REPORTED]** |
| **D-5** — `event_server.py` hand-rolled the private turn state machine ×2 | **FIXED** | public `Encounter.complete_current_turn()` (`dnd/encounter.py:1033`); both HTTP sites converted; **zero** `encounter._*`/`grid._*`/`queue._*` reaches remain in `server/` **[REPORTED]** |
| **D-6** — four degraded gateway hand-copies | **FIXED, all three sub-items** | `build_game_creation_catalog` now takes `controllers`/`ai_policies` as **required keyword-only with no defaults**, both sites explicit; gateway 409s carry correction context; content routes extracted to `server/content_http.py` with both apps as thin delegates **[REPORTED]** |
| **D-7** — `external_ai_registry.py` in the wrong package | **FIXED** | moved to `services/ai_policy_server/`; `tests/architecture/test_ai_import_direction.py:24` pins the location **[REPORTED]** |
| **H-3/H-8/H-11** — `hasattr(tile,…)`, `locals()`, `os.environ` in a handler | **FIXED** | zero `locals()` and zero `os.environ[…] =` in `server/`; direct field access on `Tile` **[REPORTED]** |
| **Vestigial `agent_protocol`/`agent_runtime`** | **FIXED** | `observation_legacy.py` and `gauntlet.py` gone; what remains has live importers and is not duplicated logic **[REPORTED]** |
| **The 30 parallel class-feature installers** (the closeout's own open item) | **DONE, uncommitted** | all 31 classes deleted (`fighter −797`, `barbarian −696`, `sorcerer −245`, `rage −227`, `feats −95`); content IDs preserved in new `permanent_feature_definitions.py`; **zero** name-level `add_resource`/`remove_resource` remains, so the cross-source erasure is no longer expressible; 11 survivors are all genuinely evented **[REPORTED]** |

Mechanical delta **[VERIFIED]**:

| Metric | Before | Now |
| --- | --- | --- |
| `# type: ignore` | 5 | **1** (`dnd/monsters/traits.py:936`) |
| `getattr`/`hasattr` in `dnd`+`server`+`services`+`custom_ai` | 142 | **79** |
| `TODO`/`FIXME`/`HACK`/`XXX` | 1 | **0** |
| Late imports, `TYPE_CHECKING`, `__init__(**kwargs)` | 0 | **0** |
| Blanket `except: pass` | several dangerous | **9, all narrow & legitimate** (`asyncio.CancelledError` ×4, `KeyboardInterrupt`, `PermissionError`/`OSError` cleanup, 2 narrow `ValueError`) |
| Architecture gates | 38 tests | **56 tests** (coverage grew) |

Dead code deleted: `dnd/blocks/appearance_catalog.py`, `ai/subjective/policy_agent.py`,
`server/agent_runtime/observation_projector.py`, `server/live_replication.py`,
`ai/planning/regression.py`, `ai/planning/explain.py`, `ai/subjective/runtime_gc.py`,
`installed_creature_materialization.py`, `item_runtime_materialization.py`,
`server/agent_protocol/observation_legacy.py`, `dnd/spells/base.py`. Zero
references now for all three `combat_log` formatters, `condition_handles`,
`create_opputinity_attack_handler`, `spikes_terrain_factory`, `GrantId`,
`PREMADE_LEVEL_5_SORCERER_SPELLS`, the `base_tiles` directional family,
`PolicySpec.maximum_decisions_per_turn`, `InteractDoorAction`/`TestDoorB`, and
29 of the ~31 previously-listed unreferenced symbols.

## But the tree is in worse shape *right now* than at the last scan

Four things are red that were green, and all four trace to the same commit or
to work sitting uncommitted on top of it.

| Gate | Last scan | Now |
| --- | --- | --- |
| `pytest --collect-only tests/` | 3,287 / **2 errors** | 3,297 / **3 errors** **[VERIFIED]** |
| `tests/architecture` | 38 passed, 0 failed | **1 failed**, 55 passed **[VERIFIED]** |
| `tests/ai` | 50 passed, 0 failed | **1 failed**, 50 passed **[VERIFIED]** |
| `generate_event_contract.py --check` | exit 0 | **exit 1** — stale **[VERIFIED]** |
| `generate_typescript_sdk.py --check` | exit 0 | **exit 1** — stale **[VERIFIED]** |
| `tests/progression` | 393 passed | **5-6 failed** in a full-directory run, 0 when run in isolation **[REPORTED]** |

---

# 2. P0 — Red right now

## P0-0 — The content-set digest is NON-DETERMINISTIC across processes. Hosted play is broken, intermittently.

**[VERIFIED — reproduced]** This is the most severe finding in the re-scan and
it explains several other symptoms, including P1-F below.

Four fresh interpreters, identical inputs, four different digests:

```
$ for seed in 1 2 3 4; do PYTHONHASHSEED=$seed python -c \
  "from dnd.content_system.bootstrap import bootstrap_content_system; \
   from dnd.content_system.configuration import DEFAULT_CONTENT_PACK_ROOT; \
   l=bootstrap_content_system(pack_roots=(DEFAULT_CONTENT_PACK_ROOT,)); \
   print(l.content_set_digest[:32], l.built_in_artifact_digest[:16])"; done

seed=1  content_set= da02744745712e9a187bae1714083ebf   builtin_artifact= 02e14b63a8ca1847
seed=2  content_set= dafe82162f1750e797d13c90d5f1cdd4   builtin_artifact= 02e14b63a8ca1847
seed=3  content_set= c376e5c139d4a8df11748c6b24129715   builtin_artifact= 839b0855d2ffc0a8
seed=4  content_set= 8325f823c75b25a292e24fcf6284ba3c   builtin_artifact= 839b0855d2ffc0a8
```

> **CORRECTION (2026-07-30, later round).** The original text here said
> "`built_in_artifact_digest` also varies … so the blast radius is wider than the
> two fields identified below and warrants a sweep for every set-typed field."
> **That was wrong, and it caused wasted work** — it sent the remediation pass
> hunting a second unordered field that does not exist.
>
> `built_in_artifact_digest` was never broken by code. `dnd/content_system/builtin.py:119`
> sorts by repo-relative posix path and the file is **unmodified since `HEAD`**
> (`git diff` empty). Its apparent variance was a measurement artifact: that
> digest hashes file *contents*, and the working tree was being edited
> concurrently while I measured. **[VERIFIED]**
>
> Two independent completeness checks in the later round — a static walk of the
> digest payload's model graph (31 models from its four roots) and a runtime
> instance scan over all 707 loaded declarations — both conclude the offending
> fields are **exactly** the two named below and nothing else. A structural
> bisect isolated 48 differing payload paths, all in `trigger_kinds` /
> `first_per_turn_trigger_kinds`.
>
> Lesson recorded as N-7 in the round-3 section: never measure a digest against
> a tree under concurrent edit.

### Root cause **[VERIFIED]**

`dnd/core/content/spatial_effect_definitions.py:67-70`:

```python
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset()
    first_per_turn_trigger_kinds: frozenset[
        SpatialEffectTriggerKind
    ] = frozenset()
```

Pydantic serializes `frozenset` in **set iteration order**, which for `str`-enum
members depends on `PYTHONHASHSEED`. Demonstrated directly:

```
seed=1 ["turn_end", "enter", "appear"]
seed=2 ["turn_end", "enter", "appear"]
seed=3 ["turn_end", "appear", "enter"]      ← different order, same input
```

`dnd/content_system/pack_loader.py:1748` feeds
`declaration.spatial_effect_definition.model_dump(mode="json")` straight into the
content-set digest. Both `server/canonical_json.py` and
`dnd/core/content/canonical.py:9` use `sort_keys=True`, which canonicalizes
*key* order but **not list/set element order** — so the "one dependency-neutral
owner for canonical content hashing" cannot fix this on its own.

### Blast radius

Every cross-process digest fence rejects, non-deterministically:

- `server/hosted_worker.py:534-539` → `HostedWorkerError("Worker content set mismatch: expected …, received …")`
- `server/game_creation_preview_worker.py:45-47` → `ValueError("Content set digest changed between parent and preview worker.")`

`tests/manual/test_110_multi_game_gateway.py` → **6 failed, 5 passed**, every
failure one of those two messages with a *different* received digest each run
**[REPORTED]**. Introduced by `4ebe523`.

**This supersedes P1-F.** I originally diagnosed the `tests/progression`
failures as cross-file state pollution; they are the same non-determinism
surfacing through `character_build_preview`'s subprocess fence. That also
explains why the failure count varied between runs (6, then 5).

### Fix

Serialize the two `frozenset` fields in sorted order (a Pydantic
`field_serializer` returning `tuple(sorted(...))` is the smallest change), then
**audit every set-typed field that reaches a digest** — `built_in_artifact_digest`
varying proves at least one more exists. Consider making the canonical-JSON owner
reject or normalize unordered collections outright, so this class of bug cannot
recur.

## P0-A — Three collection errors, all from `4ebe523` deleting a surface without repointing importers

**[VERIFIED]** `3297 collected, 3 errors`. Two are the exact failure mode this
audit flagged last time (`live_replication`): a fix moves or renames a symbol
and a test still imports the old name.

| Error | Cause | Fix |
| --- | --- | --- |
| `tests/manual/test_36_seamless_subjective_runtime.py:45` | `ai.subjective.runtime_gc` deleted; the lease-counted GC moved to `dnd/ai/runtime_gc.py` — **caused by the P1-4 remediation** | repoint the import |
| `tests/manual/test_158_srd_5_1_source_coverage_ledger.py:16` | `SRD_ARMOR_RECIPES_BY_LEGACY_ID` removed from `dnd/items/armors.py`, replaced by `SRD_ARMOR_DECLARATIONS:1580` | repoint |
| `tests/manual/test_srd_armor_content_factories.py:28` | same | repoint |

All three are one-line fixes. **56 test functions are dark** (48 + 2 + 6)
**[REPORTED]** — and `test_36` is the *sole home* of the GC-lease nesting
regression that the closeout ticks as done. See §5.

## P0-B — `tests/architecture` is red: the content-contract dependency gate

**[VERIFIED]**

```
FAILED tests/architecture/test_dependency_boundaries.py::test_content_contract_package_has_one_exact_import_surface_and_direction
  dnd/core/content/spatial_effect_definitions.py:10 → dnd.core.spatial_effect_types  (×5 symbols)
1 failed, 55 passed
```

**This is a one-line fix and the dependency direction is actually correct.**
`dnd/core/spatial_effect_types.py` is 63 lines whose only import is
`from enum import Enum` — a genuine cold leaf, exactly like the six already
whitelisted (`condition_types`, `creature_types`, `equipment_types`,
`progression`, `saving_throw_types`, `senses`). Add
`"dnd.core.spatial_effect_types"` to `CONTENT_CONTRACT_ALLOWED_NEUTRAL_DEPENDENCIES`
at `tests/architecture/test_dependency_boundaries.py:113`.

Both files are untracked in-flight spatial-effect work. The gate was left red.

## P0-C — `tests/ai` is red: the flagship real-socket AI matrix

**[VERIFIED]**

```
tests/ai → 1 failed, 50 passed
FAILED test_live_ai_matchups.py::test_real_socket_native_external_and_external_external_matrix
```

`4ebe523` deleted the `/simulation/pause|resume|step|set-delay` routes —
`grep '"/simulation' server/event_server.py` returns **zero hits** — and left
callers:

| Caller | Consequence |
| --- | --- |
| `tests/ai/test_live_ai_matchups.py:719,894,949` | the native-vs-external matrix, red |
| `tests/manual/test_187_standalone_local_game_lifecycle.py:304,318` | red **[REPORTED]** |
| `tests/manual/test_110_multi_game_gateway.py:630` | proxies a route with nothing behind it |
| `server/worker_proxy.py:92` | still classifies `simulation/*` as a proxied worker path |

The deletion looks deliberate — `tests/manual/test_109_hosted_game_runtime.py:355-358`
asserts those routes are `DENIED`, consistent with removal. **DECISION
REQUIRED:** restore the control surface, or repoint the serial-AI-turn tests to
the coordinator API and drop the proxy classification.

That matrix was the flagship proof of the native-vs-external AI architecture and
was green in both previous scans.

## P0-D — Generated wire contracts are stale; all four frozen hashes are wrong

**[VERIFIED]**

```
python devtools/generate_event_contract.py --check  → exit 1  "Generated event contract is stale"
python devtools/generate_typescript_sdk.py --check  → exit 1  same
```

| Artifact | Frozen in closeout (and still in the committed files) | Actual now |
| --- | --- | --- |
| Event | `9aee4d4913a2…` | `b02ac2633fd1…` |
| SDK | `da4bd3626e65…` | `6f62404800a7…` |
| Player replication | `0bdba516d5c2…` | `b934714aebd8…` |
| Generated TS source | `e85f34dff3eb…` | `757a17c67193…` |

**[VERIFIED** for the event hash: the checked-in `contract_hash` is exactly
`9aee4d4913a2…`; the other three **[REPORTED]**.]

The in-flight spatial-effect work moved the model after the freeze: 5 new enums,
`spatial_effect` added to two existing enums, `temporary_hit_points` added, two
new event types (`spatial_effect_changed`, `spatial_effect_interaction`), and
**three event types removed** (`fire_exposure`, `exposed_flame_ignited`,
`wind_exposure`) — a ~3,118-line diff **[REPORTED]**.

Closeout section D ("Regenerate … **once after the final wire-model change**")
has four `[x]` boxes describing a state that no longer holds.

### This is a production outage path, not generator hygiene **[REPORTED]**

`server/event_contract.py:49-53` raises for any wire type absent from the
generated contract:

```python
    if event_contract is None:
        raise EventContractError(
            f"Event class {wire_type!r} is absent from the generated wire contract."
        )
```

Path: `EventQueue.publish_lifecycle` → `event_stream._on_event` →
`objective_timeline.freeze_objective_event_source_slot` → `ObjectiveTimelineError`
→ `event_stream.py:481 _fail_objective_event_source(...)`, which **permanently**
kills the objective event source for the whole session.

The triggers are ordinary gameplay, because the stale contract is missing three
event types the engine now publishes: `dnd/items/torches.py:340,677` publish
`SpatialEffectInteractionEvent` when a torch is lit, and `dnd/entity.py:2764`
publishes `TemporaryHitPointsEvent` on any temp-HP grant. Reproduced live:

```
tests/manual/test_109_hosted_game_runtime.py::test_direct_single_game_server_never_requires_sqlite
ERROR dnd_server: HTTP 409 on GET /diagnostics/objective/events:
  {'code': 'objective_diagnostics_window_unavailable',
   'message': 'objective event source is invalid: event record at index 50 violates the cold timeline contract'}
```

Also red for the same reason: `test_97_event_wire_contract.py` (3 failures) and
`test_98_typescript_replication_sdk.py::test_checked_in_sdk_contract_equals_backend_model_graph`.

### And it already breaks every TypeScript SSE handshake **[REPORTED]**

`sdk/typescript/src/subjectiveSse.ts:196-201` hard-compares the generated
constant against the runtime protocol value:

```ts
  if (protocol.player_replication_contract_hash !== PLAYER_REPLICATION_CONTRACT_HASH) {
    throw new ContractValidationError(
      "$subjective.protocol.player_replication_contract_hash",
      "player replication contract hash mismatch",
    );
```

`contracts.generated.ts:4` still holds `0bdba516d5c2…` while the Python runtime
emits `b934714aebd8…` (`server/player_replication_contract.py:1993`, +197 lines
across `ecbf365`+`4ebe523`). So `assertProtocol` throws on **every** subjective
SSE bootstrap. `tests/manual/test_117_player_replication_contract.py:2017` only
asserts the constant is self-consistent with the wire schema, so it passes and
hides this.

This upgrades §7's conclusion: the drift is not latent — it is already breaking
the client's live handshake, while the frontend's own `npm run check` cannot see
it.

## P0-E — `test_126_action_override_runtime.py` — a live regression in the new lease work

**[REPORTED]**

```
FAILED test_ice_storm_finalization_follows_effective_target_type[False]
  assert ('Ice Storm Terrain' in {}) is not False
  tests/manual/test_126_action_override_runtime.py:1116
```

25/26, while the closeout's evidence log records **26/26** for this file. It
passes for `[True]` and fails for `[False]`: with **no** override applied, the
effective `POSITION_AOE` path no longer installs the terrain condition. That is
precisely the semantics the immutable action-overlay lease refactor was meant to
preserve (the test docstring cites "terrain is gated by effective
POSITION_AOE"). Highest-probability real behavioural regression from the lease
work.

---

# 3. P1 — Correctness

## P1-A — The new condition rollback misses subclass-owned state, and it bites the newest feature

**[VERIFIED]**

`BaseBlock._discard_uncommitted_condition_tree` (`dnd/core/base_block.py:787`)
— the rollback the closeout added — unwinds modifiers, event handlers, spatial
handlers, owned actions, and global registration. It **never calls
`cleanup_own_state()`**, the declared hook for everything else `_apply` can
install. Six overrides exist, so six leak on rejection:

```python
# dnd/classes/sorcerer.py:735 — MetamagicActive.cleanup_own_state
if target and self._override_lease is not None:
    clear_action_overrides(target, self._override_lease)
```

That release is the only thing that frees the lease, so a **rejected**
`MetamagicActive` application leaves a permanent Quickened/Twinned/Distant
overlay on the caster's spell templates. The other five leak a
`SpellProtectionRegistry` registration (`abjuration.py:1125`, `:3097` — Globe of
Invulnerability, Antimagic Field), a Haste action/bonus `max_constraint`
(`transmutation.py:356`), and skeleton condition immunities
(`skeleton_abilities.py:96`).

Second gap, same function: the removal is gated on `if condition.applied:`
(`:815`) and `apply()` sets `applied` only *after* `_apply` returns — so an
exception raised **inside** `_apply` gets no rollback at all.
`SpatialEffect.install_controller` (`dnd/spatial_effects.py:133-140`) shows the
correct shape **[REPORTED]**.

## P1-B — A rejected condition application still publishes a COMPLETION event

**[REPORTED]** `dnd/core/base_conditions.py:685-702`. `apply()` guards
`declaration_event.canceled` and `execution_event.canceled` but then checks only
`if not effect_event:` — and a canceled `Event` is truthy. So it records
modifiers, sets `self.applied = True`, and calls
`effect_event.phase_to(EventPhase.COMPLETION)`. Because `EventPhase.CANCEL` is
not in `ordered_event_phases` (`dnd/core/events.py:262`), `phase_to` does not
early-return and posts a COMPLETION version of a canceled event, running
pre-completion callbacks and the top-level combat-log callback. Reproduced live
on a reachable SRD rule (`Prone` immediate stand-up, `dnd/conditions.py:1457`):

```
CONDITION_APPLICATION lineage: DECLARATION → EXECUTION → CANCEL(canceled=True) → COMPLETION(canceled=True)
```

Other reachable producers: `abjuration.py:419` (Mage Armor on an armored
target), `:2071`, `conjuration.py:486,609`.

## P1-C — `origin_character_grant_appliers` rollback silently no-ops on advantage modifiers

**[REPORTED]** `dnd/content_system/origin_character_grant_appliers.py:240-252`
is a third hand-written copy of the modifier-handle removal switch and dispatches
on one kind only:

```python
if handle.kind is ModifierHandleKind.RESISTANCE:
    channel.remove_resistance_modifier(handle.modifier_uuid)
else:
    channel.remove_value_modifier(handle.modifier_uuid)
```

Advantage modifiers are installed at `:146` via `add_advantage_modifier` and live
in `advantage_modifiers`; `remove_value_modifier` pops from `value_modifiers` —
a **silent no-op**. Any origin trait with `saving_throw_advantages` (Dwarven
Resilience, Gnome Cunning, Halfling Brave) that fails later in the install leaves
permanent unowned advantage on the entity. Canonical
`remove_character_composition` gets this right (`character_materialization.py:441-459`).

Same block: `capability_sources` is assigned only **after** the capability loop
completes (`:232`) while `add_origin_capability_source` runs inside it (`:230`),
so a mid-loop failure iterates an empty list.

## P1-D — `origin_innate_spellcasting` is a second removal authority with three reachable leaks

**[REPORTED]** `_remove_origin_innate_spellcasting` (`:68-98`) hand-reimplements
the receipt walk for **4 of the 19** `CharacterGrantReceipt` fields and diverges
from the canonical remover (silently skips a missing learned-reaction handler
where `character_materialization.py:370` raises). The resource contribution added
at `:169-174` sits outside the guarded region with its receipt appended only at
`:220`/`:266`, so it leaks on three reachable paths: `row.spell_type(...)`
raising at `:178`; `raise TypeError("origin spell row constructed another action")`
at `:204`; and `raise RuntimeError("Origin innate reaction spell has no
source-aware installer")` at `:231` — hit by **any** innate reaction spell other
than Hellish Rebuke with `uses_per_long_rest` set.

## P1-E — The native assignment's blanket `except Exception` swallows engine failures

**[REPORTED]** `dnd/ai/runtime/assignment.py:208-250` wraps *both* untrusted
policy code *and* `resolve_policy_intent` → `dispatch_available_action` → live
engine event execution. Any engine exception during an AI turn becomes
`ControllerStepResult(end_turn=True)` plus a `FAILED` feedback row — an engine
bug presents as "the AI ended its turn". The closeout claims authoritative turn
paths propagate; here they do not. The isolation boundary belongs around
`self._runner.decide(...)` only (`runner.py:43` already re-raises correctly).

## P1-F — `tests/progression` intermittent failures — SUPERSEDED BY P0-0

**[REPORTED symptom; root cause VERIFIED under P0-0]** 5-6 failures in a
full-directory run, **0 when the same three files run alone**, with the count
varying between runs:

```
server.character_build_preview.CharacterBuildPreviewError: Character visual preview
materialization failed: ValueError: Content set digest changed between parent and preview worker.
server/character_build_preview.py:68
```

I originally diagnosed this as cross-file state pollution. It is not — it is the
**non-deterministic content-set digest (P0-0)** surfacing through
`character_build_preview`'s subprocess fence. Fixing P0-0 should fix this
directory; re-measure afterwards rather than chasing test isolation.

Independently still true: the closeout's unchecked item E (run every file
individually) could not have caught this, because per-file runs pass. A
directory-level or seeded run is required.

## P1-G — `modifiers.py` still memoizes the contextual-modifier failure (PARTIAL fix)

**[VERIFIED]** The log was added, the cache write was not moved:

```python
except Exception:
    logger.exception("Contextual modifier %s (%s) failed during aggregation", self.name, self.uuid)
    result = None
key = f"{source_entity_uuid}|{target_entity_uuid or 'none'}|{event_lineage_uuid or 'none'}"
self.cached_results[key] = result   # ← still caches the failure
```

A raising contextual advantage/AC/resistance modifier is still permanently "no
modifier" for that key. Also unchanged 30 lines up: `except ValueError as e:
raise ValueError(str(e))`.

---

# 4. Still open from the previous audit

| Finding | Status | Note |
| --- | --- | --- |
| `ai/observation/`, `ai/protocol/`, `ai/semantics/` — `__pycache__`-only graves | **STILL OPEN** **[VERIFIED]** | wire tags still reference them (`session_transcript.py:166,181,205,217`); zero hits for those tags in `ai/evidence/` or `tests/`, so no compatibility justification. Two more graves found: `dnd/utils/`, `dnd/scenarios/evaluation/` **[REPORTED]** |
| `dnd/ai/runtime/controller.py` shadow registry + bare `assert` | **STILL OPEN** **[REPORTED]** | `_default_policy_registry()` still duplicates `server/ai_policy_composition.py` (now a **third** builder exists in `services/ai_policy_server/composition.py:40`); `_ensure_assignment` still silently substitutes it; bare `assert self._instrumentation is not None` at `:92`. Latent — production always injects |
| Stale `ai/*.md` plan docs presenting the deleted architecture as current | **STILL OPEN** **[REPORTED]** | no status/superseded markers on any of the four; `UNIFIED_AGENT_ARCHITECTURE.md:409` still lists `observation_projector.py` in its "current" tree |
| `content_packs/` holds only `README.md` vs 1,800-line `pack_loader.py` | **STILL OPEN** **[REPORTED]** | |
| `ConditionApplicationPolicy`, `ItemStackCompatibility` single-member enums | **STILL OPEN** **[REPORTED]** | `feature_grants.py` went 93 → **33 L** and its two single-member enums are gone, so this pattern was half-pruned |
| 22 field-less `*Parameters` models; `_ = parameters` ×49 | **STILL OPEN** **[REPORTED]** | |
| `character_build_validation.py` three-tuple choice enumeration | **STILL OPEN** **[REPORTED]** | still three `isinstance` tuples (`:2305,2316,2347`); two adjacent branches both return `()`; `StartingApparelPackageChoice` still never `_resolve_declaration`'d |
| `core/spell_execution.py` module-level `ContextVar` in a "dependency-neutral" leaf | **STILL OPEN** **[REPORTED]** | scoping is correct (`set`/`reset` token + conflict guard), so defensible |
| **T-1** test numbering | **REGRESSED** **[REPORTED]** | **25** colliding numbers (was 23) across **63** files (was 60); unnumbered files 21 → **32** of 215; still no written convention, still no uniqueness guard — while `KNOWN_ISSUES.md` still uses `test_NNN::test_fn` as a key |
| **T-2** `KNOWN_ISSUES.md` dangling citations | **REGRESSED badly** **[REPORTED]** | **40** cited test files do not exist (was 13); `:348` still cites deleted `test_38_ai_validation_server_start.py` inside the *active* issue; `CLAUDE.md` still instructs `examples/test_*.py` at 7 sites against a deleted tree |
| **T-3** `test_manual_NN_*` twins in `tests/engine/` | **STILL OPEN** **[REPORTED]** | all 10 twins present; the "74 non-exact engine-book migrations" item is unchecked **and no record of which 74 exists** — unauditable as written |
| **T-4** assert-free tests | **STILL OPEN + 3 NEW** **[REPORTED]** | original one unchanged (and in the file that no longer imports); new ones in `test_remaining_creature_content_factories.py:374`, `test_origin_integration_matrix.py:259,270` |
| **T-5/T-6** giant tests, private-detail assertions | **STILL OPEN** **[REPORTED]** | worst test 88 asserts / 347 lines; **207** asserts reference a `._private` attribute |
| **T-7** architecture guards shell out to `ripgrep` | **STILL OPEN, 3× wider** **[REPORTED]** | now in `test_ai_import_direction.py:160`, `test_dependency_boundaries.py:264`, `test_spell_catalog_composition.py:24`; still undeclared in `pyproject.toml` |
| **D-P** unreachable legacy-factory filter | **STILL OPEN, verbatim** **[REPORTED]** | |
| **D-Q** `RETIRED_*` bulk + incomplete guard | **PARTIAL** **[REPORTED]** | `observation_replay` added; still missing `agent_protocol.service`, `agent_runtime.service`, `agent_runtime.subprocess_service`, and the newly-deleted `agent_runtime.observation_projector` |
| **D-N** SDK blanket re-exports | **STILL OPEN** **[REPORTED]** | `index.ts` still has 13 `export *`. Cross-repo recheck: `decodeServerEvent`, `validateServerEvent`, `assertJsonValue`, `isJsonValue` are **0/0** in both repos; `isConcreteServerEvent` live in 1 client file; the other 8 have one internal SDK consumer and zero client consumers |
| **T-9** `CLAUDE.md` vs `AGENTS.md` drift | **REGRESSED** **[REPORTED]** | **190** diff lines (was 177). Both were edited at `4ebe523`, so CLAUDE.md is no longer stale-by-commit — it was touched and still not brought to parity. CLAUDE.md has **zero** references to `tests/manual`/`tests/engine`/`tests/progression`, `content_system`, `character_progression`, or the new neutral leaves |
| **T-10** hygiene | **PARTIAL** **[REPORTED]** | the junk deletions **were committed** (`git ls-files` for `.orig`/`.log`/`entity_snapshot.json` → zero) but **no ignore rule was added**, so they recur; 5 `/ui/…` lines still point at a deleted tree; `lore.md` still tracked at 0 bytes; `to_archive/` still ignored *and* 1,277 files tracked; `git diff --check` reports `ai/policy/memory.py:302: new blank line at EOF` |

---

# 5. Regression-coverage census

The closeout's own criterion 3 is "every fixed correctness issue has a direct
deterministic regression". **[REPORTED]**

| Fixed item | Regression | Status |
| --- | --- | --- |
| Attack declaration dispatched once (P1-1) | `test_combat_actions.py:312` | **PRESENT & GREEN** — closeout box B-1 is wrongly unchecked |
| Worker-proxy deny-unknown-reads (P1-6) | `test_109_hosted_game_runtime.py::test_public_runtime_route_classifier_blocks_worker_administration` | **PRESENT & GREEN** |
| Lifecycle gates from `LifeState` (P1-3) | `tests/engine/test_life_state_ownership.py` + 4 more | **PRESENT & GREEN** |
| Attack target-context restore (H-6) | `test_combat_actions.py:1252,1287`, `test_spellcasting.py:995` | **PRESENT & GREEN** — both success and exception arms |
| Condition-application rollback | `test_condition_lifecycle.py:281,332,353,393` | **PRESENT & GREEN** — but see P1-A: it does not cover `cleanup_own_state` leakage |
| Action-overlay lease composition | `test_spellcasting.py:786` | **PRESENT & GREEN**, but proves only *removability* — and its sibling `test_126[False]` fails (P0-E). Coverage gap |
| **GC lease-counting / nesting (P1-4)** | `test_36_seamless_subjective_runtime.py:2136` | **PRESENT BUT UNRUNNABLE** — the file fails to import. **No effective coverage today** |
| **Character-materialization rollback (P1-2)** | — | **MISSING.** `test_175` has 4 tests, all happy/fence path. No test asserts "no orphaned light source after failed materialization" — the exact P1-2 symptom |

Also, P1-2 itself is only **PARTIAL** **[REPORTED]**: items/equipment/bindings
are now discarded (`_discard_character_items`), but **appearance is still applied
outside any receipt and never reverted**, the orphan `Entity` and its
`CreatureRuntimeBindingRegistry` binding are never discarded (the registry has no
`discard`), and the existing test's `assert not get_map()._light_sources` is
**vacuous** — the fixture fails on holding #2 while torches ignite only after
the loop, so no torch is ever lit.

---

# 6. New findings not in the previous audit

**[REPORTED unless noted]**

| # | Severity | Finding |
| --- | --- | --- |
| N-1 | P1 | Two self-action declaration constructors survived the "removed redundant constructors" pass and **drop `effective_costs`**: `transmutation.py:1161` (`BonusDash`) and `conjuration.py:986` (`EscapeWebAction`) hand-build `ActionEvent` with raw `self.costs`, so every cost transform, dynamic cost and action-override lease is ignored, and their declaration events carry no declared-target or presentation identity. `origins/dragonborn.py:230` shows the correct form |
| N-2 | P2 | New write-only receipt field — `CharacterCompositionReceipt.automatic_grant_refs` written at `character_materialization.py:862,872`, **no reader** anywhere. Exactly the D-14 pattern the closeout just fixed for the four digests, recurring on a fifth field |
| N-3 | P2 | `Entity.initiative` is a DEX snapshot taken once at construction (`entity.py:616`), patched afterwards by a compensating delta modifier (`character_materialization.py:661-674`). Nothing keeps them in sync, so any post-composition DEX change leaves initiative stale — a derived value held as authoritative state |
| N-4 | P2 | `getattr(template, "_create_variant", None)` at `dnd/actions_functional.py:254` — a string-keyed probe for a **private** member of `SpellAction` from outside the owning class, plus a `cast` to erase the `Any`. `items/spell_items.py:129` does it correctly with `isinstance` |
| N-5 | P2 | `getattr(event, "effect_id", None)` at `dnd/analytics/game_summary.py:797,811` — declared field on three event types that this same file already `isinstance`-narrows. Identical shape to the H-1 fix, in the same module |
| N-6 | P2 | `getattr(source_block, 'senses', None)` at `dnd/core/base_actions.py:1363` — `BaseBlock.get_senses()` is the declared virtual. Worse, `if senses is not None` means any non-`Entity` source **skips visibility validation entirely** rather than failing closed |
| N-7 | P2 | `ActionOutcomeProfile`/`DamageRollProfile` declared field-for-field identically in `dnd/core/base_actions.py:192,212` and `dnd/ai/contracts/control.py:94,103`, bridged by a **JSON round-trip per action row per epoch build** (`decision_epoch.py:667,790`) |
| N-8 | P2 | `custom.tactical`'s candidate set is silently gated by the **bundled** policy's rule rows — `build_basic_candidates` admits only `any(rule.matches(candidate) for rule in BASIC_POLICY_SPEC.rules)` (`basic.py:430`) and `custom_ai/tactical/policy.py:76` consumes it. Every change to the bundled spec silently changes the example policy's options |
| N-9 | P2 | The hand-rolled `record_timing` system was **relocated, not removed** — 16 functions in `server/agent_runtime/observation_journal.py` still thread `record_timing` (151 references), driven by `_ServerCommandTiming`. `dnd/ai` is clean, but two timing owners remain |
| N-10 | P2 | Canonical content JSON hashing has **three remaining copies** beside the new `dnd/core/content/canonical.py`: `core/content/premade_characters.py:114` (identical, same package), `content_system/character_build_validation.py:2400` (**drifted** — omits `allow_nan=False`/`ensure_ascii=False`, and builds every `grant_token`), `core/progression.py:104` (arguably justified by leaf purity) |
| N-11 | P2 | `dnd/core/content/runtime.py` probes owned types with `getattr` 11× — structurally forced (neutral leaf can't import `BaseAction`/`EventHandler`) but the largest remaining concentration; a tiny neutral `Protocol` closes it. Also `character_materialization.py:485 getattr(definition.base_ability_scores, ability.value)` is the unfixed H-4 shape |
| N-12 | P2 | Appearance copied onto an owned model by a reflective `setattr` loop over two hand-duplicated 11-field lists (`character_appearance.py:587`, `blocks/appearance.py:20,82`) — the same shape the closeout says it replaced in analytics |
| N-13 | P3 | `remove_character_composition` still has **zero production callers**; production respec (`server/character_directory_service.py:1342`) commits new revisions and re-materializes. The exhaustive-receipt machinery is a rollback safety net, not the respec mechanism — worth stating, since work order, closeout and docstrings all justify it by "respec" |
| N-14 | P3 | `class_feature.aegis_training` is registered in `PERMANENT_CLASS_FEATURE_DECLARATIONS` (so it enters the frozen content set, catalog and icon table) but is the **only** one of 31 with no applier — it exists solely as the fixture for `test_unimplemented_structural_feature_fails_closed` |
| N-15 | P3 | Dead: `Invisible.can_see_invisible` (`conditions.py:1202`), `GridMap.unsubscribe_entity` (`gridmap.py:203`), `EventQueue.get_handlers_by_source_entity` (`events.py:2097`), `ai/knowledge/deriver.py:843 _optional_bool`, `ai/codex_tools/__main__.py`, and the whole `SizeModifier` write path (`values.py:337,1157` — zero callers, so `size_modifiers` is always empty and its aggregation at `:561` is unreachable; note it **is** serialized into the generated contract, so deleting is a wire change) |
| N-16 | P3 | Dead no-op branches in the new spatial code: `tile_conditions.py:757-761` clears a private attr while the real removal happens via `remove_event_handlers()`; `spatial_effects.py:154-163 create_default_controller` declares and ignores two params then raises; `:66-69` `Field(default=...)` with no `description=` against local convention |
| N-17 | P3 | `dnd/ai/contracts/control.py:7,1083` — `import time` and `created_at: float = Field(default_factory=time.time)` on `DecisionEpoch`, in the layer that is supposed to be dependency-neutral and where `dnd/ai` owns all clocks. Makes epochs non-replay-stable if ever hashed |
| N-18 | P3 | `SPATIAL_EFFECT_ARCHITECTURE_2026-07-30.md` §10's "still open" list is **already stale** — the interaction events, gateway install and transition table all exist and all 16 `ZoneControlCondition` subclasses migrated. What *is* genuinely half-applied: `_apply_tile_markers`/`ZoneMarkerCondition` footprints, and the raw-UUID spike/lever path in `environment_interactables.py:168-188` which still name-matches `"Spike Trap" in tile.active_conditions` |
| N-19 | P3 | Residual applier duplication: `fighter_character_grant_appliers.py:91 _install_contextual_modifier` is a private 6th helper that barbarian re-inlines twice; the "add resource → install action/handler → rollback" block still appears 4× in fighter; `extra_attack`/`builtin`/`origin` appliers still hand-build `CharacterGrantReceipt(...)` instead of using the shared `grant_receipt(...)` |
| N-21 | P2 | **Frozen-slots dataclass exceptions carry empty `args` and cannot round-trip.** `server/terminal_evidence.py:39` and `server/game_history.py:37` are `@dataclass(frozen=True, slots=True)` subclasses of `ValueError` whose `__init__` never calls `ValueError.__init__`, so `args == ()`, `repr()` erases the message, and both fail `pickle`/`copy` — on the worker→gateway terminal-evidence boundary with 14 raise sites. The other 37 error classes in `server/` use plain subclassing |
| N-22 | P2 | Canonical-JSON ownership is **still not single**: `worker_terminal_spool.py:163,207` open-code `sha256(canonical_json_bytes(...)).hexdigest()` instead of `canonical_json_sha256`, and `server/game_directory/canonical.py` is a shim whose `datetime_to_text` (`:21-37`) is a verbatim copy of `canonical_json._json_ready`'s datetime branch, `canonical_digest` a one-line alias, and `canonical_json` a pure re-export |
| N-23 | P3 | `server/local_game_lifecycle.py:570` uses a bare `next(... )` with no `default`, so a missing pinned deployment surfaces as raw `StopIteration` rather than the typed conflict its gateway twin raises (`game_gateway.py:407`). Same file `:346-360`: the idempotent-retry branch of `complete_terminal` silently ignores the caller's `evidence`/`objective_replay`/`subjective_replay` with no digest comparison, unlike the worker spool path which fences on `manifest_digest` |
| N-24 | P3 | `server/game_gateway.py:398-422` re-queries `list_character_deployment_leases(...)` and `list_character_deployments(...)` **inside** the `for holdings_row in holdings_evidence` loop and filters in Python, duplicating filtering the repository already accepts as parameters |
| N-25 | P3 | `server/event_server.py:1895` — residual unlogged swallow `except Exception: current_map = None`, with `current_map = None` assigned twice. Pre-existing, not in the previous audit |
| N-26 | P3 | `@model_validator(mode="after")` is used ~110× across `server/` where the stated convention prefers `model_post_init`, and no architecture test enforces the preference. Worth either enforcing or dropping the stated rule |
| N-20 | P3 | The composition→transient-condition cleanup iterates `Entity.get_all_entities()` × all their conditions **per grant** (`character_materialization.py:334-352`) — O(grants × entities × conditions) |

---

# 7. Cross-repo: the SDK seam has become *silently* lossy

**[VERIFIED]** In my earlier NeuroClient audit, `player-replication-boundary-smoke.mjs`
hard-coded value pins (`expectedGeneratedContractsSourceSha` etc.) and I flagged
the whole-file pin as too coarse — every unrelated backend edit red-lit
`npm run check`.

That has since been changed on the frontend side, and it went too far. The
hard-coded `expected*Sha` constants are **gone**; the script now does:

```js
const sdkContractHash = requiredContractHash("SDK_CONTRACT_HASH");
requiredContractHash("PLAYER_REPLICATION_CONTRACT_HASH");
requiredContractHash("EVENT_CONTRACT_HASH");
```

`requiredContractHash` regex-extracts the value **out of the SDK source** and
only asserts that a 64-hex string exists. Combined with `app/package.json`
linking `@neurodragon/dnd-engine-sdk` by `file:` straight into
`dnd_engine/sdk/typescript` with no vendored copy, this means:

**the frontend cannot detect the stale contract (P0-D). `npm run check` will not
go red; it will silently consume an SDK whose type surface no longer matches the
Python wire model.** That is a worse failure mode than a noisy pin.

Note the frontend gate is currently red anyway, but for a frontend-side reason
that fires *before* the hash checks:

```
AssertionError: src/api/bootstrap.ts does not import engineClient from ../engine/replication
  at player-replication-boundary-smoke.mjs:282 → :86
```

**Recommendation:** after regenerating (P0-D), add a value-pinned assertion on
the frontend for at least `EVENT_CONTRACT_HASH`, so wire drift is loud, and pair
it with a documented re-pin step so it does not become a reflex.

---

# 8. Notes on the closeout ledger's accuracy

It is a good ledger — specific, evidence-bearing, and honest about scope
decisions. Four accuracy issues to correct:

1. **B-1 is wrongly unchecked.** The attack-declaration-once regression exists
   and passes (`test_combat_actions.py:312`).
2. **Section D is now false.** All four frozen hashes are stale; both `--check`
   gates exit 1.
3. **`test_126_action_override_runtime.py` is logged as 26/26; it is 25/26.**
4. **Per-file green evidence is not sufficient.** `tests/progression` passes
   file-by-file and fails 5-6 in a directory run. The ledger's own unchecked
   item E is precisely the gap.

Two ledger claims that verify **true** and are worth keeping visible: the
projector merge preserved both sides' data (`is_hazardous`, revision-keyed
cache), and the class-feature parallel-authority removal genuinely eliminated the
data-loss mechanism (zero name-level `add_resource`/`remove_resource` remains).

---

# 9. Execution order

0. **P0-0 — sort the `frozenset` fields.** Highest priority: it is the only item
   here that makes hosted play fail intermittently, and it is the root cause of
   P1-F and of the `test_110_multi_game_gateway` failures. Then sweep every
   set-typed field that reaches a digest (`built_in_artifact_digest` varies too),
   and consider making the canonical-JSON owner normalize or reject unordered
   collections so this cannot recur.
1. **P0-A** — three one-line import repoints. Restores 56 dark tests, including
   the only GC-lease regression.
2. **P0-B** — one line in the architecture allowlist. Restores the gate.
3. **P0-D** — regenerate contracts **after** P0-0 (a digest fix changes them
   again), re-freeze the four hashes in the closeout, and note this is not
   cosmetic: the stale contract permanently fails the objective event source on
   ordinary gameplay (lighting a torch, granting temp HP) and already throws on
   every TypeScript SSE handshake. Then decide the frontend pinning question
   (§7).
4. **P0-C** — decide: restore `/simulation/*` or repoint the three callers and
   drop the `worker_proxy.py:92` classification. **DECISION REQUIRED.**
5. **P0-E** — the `test_126[False]` terrain regression. Real behaviour, in the
   newest code.
6. **P1-A** — call `cleanup_own_state()` from the rejection rollback and move the
   `applied` gate so an exception inside `_apply` also unwinds. The
   `MetamagicActive` lease leak is the concrete damage.
7. **P1-F** — the `tests/progression` content-set pollution. Until this is fixed
   the directory cannot gate anything.
8. **P1-B, P1-C, P1-D, P1-E, P1-G** — independent correctness fixes.
9. **Missing regressions** — materialization rollback (with a *non-vacuous*
   light-source assertion), and the un-overridden effective-template behaviour.
10. **T-2 / T-9** — `KNOWN_ISSUES.md` citation rot (40 dead refs, one in an
    active issue) and `CLAUDE.md` parity. Cheap, and CLAUDE.md is auto-loaded
    into every agent session, so its inaccuracy compounds.
11. **T-1** — write the test-numbering rule down or drop numbers, and add a
    uniqueness guard. It is regressing every pass and the ledgers key on it.
12. Everything in §4 and §6 — batch by area.

## Standing verification loop

```bash
source .venv/bin/activate
python -m pytest --collect-only -q tests/ --continue-on-collection-errors | tail -3
python -m pytest tests/architecture -q
python -m pytest tests/ai -q
python devtools/generate_event_contract.py --check   ; echo "exit=$?"
python devtools/generate_typescript_sdk.py --check   ; echo "exit=$?"
git diff --check
```

All six should be clean and currently five are not. Never run an unbounded
repository-wide pytest; run individual files.

## Method

Five parallel read-only sweeps (engine core, server, AI packages,
content/progression, tests/docs/hygiene) — **four reported; the server sweep did
not, see the coverage note at the top** — plus independent mechanical
verification: collection census, architecture and AI gates, generator `--check`
runs, forbidden-pattern delta counts, dead-symbol grep delta, and cross-repo
inspection of the NeuroClient contract gate. Every **[VERIFIED]** item was
reproduced by command or by reading the cited code. `to_archive/` excluded
throughout.

---

# 10. ROUND 3 STATUS — later on 2026-07-30

Re-verified after a further remediation pass (~239 modified / 23 untracked / 6
deleted, still all on `4ebe523`). Same tags: **[VERIFIED]** = reproduced here.

## THE TREE DOES NOT IMPORT **[VERIFIED]**

```
$ python -c "import dnd.content_system.builtin"
ValueError: icon ledger public-definition closure mismatch;
  missing=['content.neurodragon:condition:condition.environment.wet@1'], unknown=[]
  at dnd/content_system/icon_bindings.py:304
```

`dnd/content_system/builtin.py:71` calls `validate_builtin_content_icons` at
**module import time**, so this is fatal repo-wide: `pytest --collect-only`
collapses entirely (no longer "3,327 collected, 3 errors"), both generator
`--check` runs return to exit 1, and `tests/ai` goes from 50 passing to 100%
collection error.

Mechanism — mtimes **[VERIFIED]**:

| File | Last touched |
| --- | --- |
| `dnd/content_system/condition_definitions.py` (adds `"condition.environment.wet"` at :142) | **20:28:03** |
| `dnd/core/content/icon_bindings_generated.py` | **19:32:08** |

Ten minutes earlier the same tree failed differently —
`condition_definitions.py:432 ValueError: Co-located declaration for <class 'dnd.conditions.Wet'> has unexpected display identity`
— so both the ledger-closure fence and the display-identity fence are being
tripped by in-flight `Wet` work.

**Not a one-command fix.** The generator is
`devtools/import_neuroclient_content_icon_bindings.py` and its inputs are present
locally (`content_data/ledgers/neuroclient_game_icon_asset_index.json`,
`content_icon_bindings.json`) — no cross-repo dependency. But
`condition.environment.wet` has **zero** rows in `content_icon_bindings.json`
and is the only `condition.environment.*` definition in the codebase, so there is
no sibling to pattern from. An icon binding (reviewed icon, or an explicit
intentional-null) must be authored first, then regenerate. **[VERIFIED]**

## Fixed this round

- **P0-D** — both generators exit 0; contracts regenerated. Cross-repo break
  closed: `contracts.generated.ts:4 PLAYER_REPLICATION_CONTRACT_HASH = 7a991b0ca4808e78…`
  now equals the runtime constant exactly, so `subjectiveSse.ts:196` no longer
  throws on every SSE handshake. **[VERIFIED]** (Regressed to exit 1 only as
  collateral of the import break above.)
- **P0-D(a)** — the objective-event-source outage path is closed: all
  `test_97_event_wire_contract.py` tests pass; the fail-closed mechanism is
  intact but no longer triggers.
- **`git diff --check`** — clean. **[VERIFIED]**
- **N-1 (half)** — `EscapeWebAction` now subclasses `EscapeSpatialRestraintAction`
  with no hand-built declaration. `BonusDash` still open.
- **N-16** — `dnd/tile_conditions.py` and `dnd/tiles.py` hard-cut;
  `create_default_controller` is now a real virtual with 8+ overrides in
  `dnd/environmental_effects.py`.
- **N-18 (mostly)** — `_apply_tile_markers`/`ZoneMarkerCondition` now zero hits;
  the raw-UUID spike/lever path is typed (`isinstance(effect, SpikeTrapGroundEffect)`).
  Residue: `dnd/environmental_effect_runtime.py:89 effect.active_conditions.get("Spike Trap")`.
- An import smoke test of all **337** modules under `dnd/` + `server/` gave 0
  failures *before* the icon-ledger break — no dangling importers were introduced
  this round.

## Still open — including every one-line item

**[VERIFIED unless noted]** P0-0 (7 seeds → 7 digests; the two `frozenset` fields
still have **no** `field_serializer`, and only a cosmetic refactor to the new
canonical owner landed), P0-A (same three collection errors, 4th consecutive
scan), P0-B (**regressed 3× wider** — allowlist untouched while
`dnd/core/content/materialization.py:16` and `registry.py:31` became new
importers), P0-C, P0-E, P1-A (both halves, no regression test), P1-B, P1-C (both
halves), P1-D (all three leak paths), P1-E, P1-G (cache write still outside the
success path; the `raise ValueError(str(e))` ceremony did go), P1-2 (appearance
still unreverted, orphan `Entity` + creature binding still undiscarded —
`CreatureRuntimeBindingRegistry` still has no `discard`, and the test *pins* the
orphan; the light assertion is **still vacuous**), plus `worker_generation`,
N-2 through N-6, N-8 through N-15, N-17, N-19 through N-25.

`tests/architecture` → **3 failed, 53 passed** (was 1 failed, 55 passed).
`tests/progression` → **6 failed, 387 passed** twice, deterministically.

## P1-F is no longer intermittent

Two runs, identical failure set, all `Content set digest changed between parent
and preview worker`. Parent and subprocess always get different hash seeds, so
this is **deterministically red**, not flaky. Prediction from the earlier round
confirmed.

## The fix for P0-0 already exists in this repo, unused

`dnd/ai/contracts/semantics.py:956` defines `_UNORDERED_SEMANTIC_FIELDS` and
`:970 _canonicalize_semantic_payload`, whose docstring states the bug verbatim —
*"Pydantic serializes `set` and `frozenset` fields as JSON arrays. Their
process-dependent iteration order must therefore be restored … before content
addressing."* **[VERIFIED]**

Its guard exists too: `tests/manual/test_42_action_semantics_hashing.py:151` runs
the reference under `PYTHONHASHSEED` overrides and asserts a single digest.
**There is no equivalent for `content_set_digest`** — that one file is the only
`PYTHONHASHSEED` occurrence in the repo.

So the whole fix is: apply that canonicalizer (or a `field_serializer` returning
`tuple(sorted(...))`) to the two fields, and clone the seeded guard test. Note
`semantics.py:946` is also a **fourth** canonical-JSON copy (missed by N-10),
which argues for folding it into the single owner rather than leaving a private
twin.

## New this round

- **NEW-A (P1)** `tests/architecture/test_source_model_hygiene.py::test_combat_log_models_use_google_style_docstrings`
  — `dnd/core/combat_log.py::SavingThrowLogData.save_kind missing from docstring`.
  Field added at `:328`, Attributes block at `:316-326` not updated. **[VERIFIED]**
- **NEW-B (P1)** `tests/engine` → **12 failed, 527 passed** (green in both prior
  scans), from three defects: `RuntimeError: AreaSpatialEffectController requires
  an independent SpatialEffect owner` (`dnd/spatial_effect_controllers.py:662`)
  on ordinary SRD gameplay; authored spatial content that violated its own
  registry validator (a cross-layer `REPLACE_AFFECTED` on `water_surface` →
  `STEAM_CLOUD`, making every `POST /game-creation/compose` a 500 — edited at
  20:25, re-measure once quiesced); and a `footprint_target_key` signature change
  (`dnd/core/aoe.py:60`) whose mismatch went unstatically-caught because
  `shape_template` is annotated **`Any`** at `dnd/entity.py:5306`, in the AoE hot
  path on an owned type.
- **NEW-C (P1)** Freedom of Movement no longer rejects `Grappled`
  (`test_spell_families.py:1223`), while `Restrained`/`Slowed`/`Ray of Frost`
  rejections still hold. Plausibly the same root as P1-B.
- **NEW-D (P2)** `CLAUDE.md` and `AGENTS.md` still teach the deleted spatial
  architecture, including a worked example headed `# In ZoneControlCondition._apply():`
  (`CLAUDE.md:317`), "See `dnd/tile_conditions.py`" (`:324`),
  `SpikeTrapCondition`/`ZoneMarkerCondition` (`:693`), and both deleted files in
  the module index (`:1066`). `ZoneControlCondition` has zero Python references.
  CLAUDE.md is auto-loaded into every agent session.
- **NEW-E (P3)** `dnd/spatial_restraints.py:184 find_spatial_restraint_source` —
  zero callers.
- **NEW-F (P3)** Two counters regressed while on the open list: `_ = parameters`
  49 → **57**; test-number collisions 25 → **35** across 83 files, unnumbered 32
  → **108**. These need a guard, not another ledger line.
- **NEW-G (process)** Auditing a tree under concurrent edit produced two
  different failure signatures ten minutes apart and one phantom finding (see the
  P0-0 correction above). Take digest/artifact measurements against a quiesced
  tree or label them explicitly.

## Regression census: 8 items → 5 covered, 1 partial, 1 dark, 2 missing

Worse than the previous 6-of-8. Still dark: the GC-lease nesting regression
(4th consecutive scan, blocked by the unrepaired `ai.subjective.runtime_gc`
import). Still missing: materialization rollback, and now content-digest
determinism — for which `test_42_action_semantics_hashing.py` is a ready-made
template.

## Ledger accuracy

The closeout's new `post-spatial reconciliation` section makes 8 claims;
**four are false**: digest determinism, collection/import repair, the
dependency-boundary allowlist, and the action-overlay regression being green. The
old frozen-hash block also still presents four superseded hashes as current with
no marker, and the new block omits the generated-TypeScript-source hash
(actual `sha256` of `contracts.generated.ts` = `0832561040f9f1e5…`).

## Revised execution order

1. **Author the `condition.environment.wet` icon binding and regenerate the
   ledger.** Nothing else can be measured until the tree imports.
2. **P0-0** — apply `_canonicalize_semantic_payload` (or a sorting
   `field_serializer`) to the two `frozenset` fields, and clone the seeded guard
   from `test_42_action_semantics_hashing.py`. This alone fixes P1-F's 6
   deterministic failures and the hosted-worker/preview digest fences.
3. **The five one-line items**: three import repoints (P0-A), the allowlist entry
   (P0-B, now covering 3 importers), the `save_kind` docstring (NEW-A).
4. **NEW-B** — `tests/engine`'s 12 failures, and type `shape_template` properly.
5. **P1-A** — `cleanup_own_state()` in the rejection path plus moving the
   `applied` gate. Still the `MetamagicActive` permanent-lease leak.
6. Everything else per §9.

**Before any further commit, run the standing loop in §9.** Three rounds running,
generated artifacts and their sources have been edited out of step every time
(`runtime_gc`, `SRD_ARMOR_RECIPES_BY_LEGACY_ID`, now the icon ledger), and this
round it took the whole engine down rather than one test file.
