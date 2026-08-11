# Known Issues

Bugs, failing tests, and hypotheses documented during implementation sessions. Updated by dispatching background sub-agents when issues are found during unrelated work.

## Format

```
### [SHORT TITLE]
- **Found**: [date or session context]
- **Test file**: `examples/test_xxx.py` (if applicable)
- **Error**: [brief error description]
- **Hypothesis**: [what might be causing it]
- **Status**: OPEN | INVESTIGATING | FIXED
```



## Current Actionable Issues

This section is the canonical status index as of 2026-07-24. The historical
ledger below is preserved as discovery evidence, but an older `OPEN` label does
not override a status recorded here.

### NeuroClient presentation smokes cannot enter the current Studio tab surface

- **Found**: 2026-08-10 while running adjacent consumer gates for the replay
  decorative-callback ownership fix.
- **Behavior**: three maintained NeuroClient browser smokes time out before
  their presentation assertions because the mounted app never exposes the
  expected Spell Studio tab button.
- **Automated reproducers** (from `/home/tommaso/Dev/NeuroClient/app`):
  - `npm run reaction-presentation:smoke` times out waiting for
    `#spell-studio button` with exact text `Actions` at
    `scripts/reaction-presentation-smoke.mjs:531`.
  - `npm run movement-presentation:smoke` times out waiting for the same
    `Actions` button at `scripts/movement-presentation-smoke.mjs:339`.
  - `npm run condition-presentation:smoke` times out waiting for the exact
    `Conditions` button at `scripts/condition-presentation-smoke.mjs:463`.
- **Hypothesis**: these smokes still depend on an older mounted Spell Studio
  navigation surface or do not establish the current route/workspace before
  selecting their authoring tab. The failure occurs before the presentation
  runtime assertions and is independent of ClipQueue callback fencing.
- **Status**: INVESTIGATING.

### NeuroClient cold-Rolling readiness fixture completes before its texture gate

- **Found**: 2026-08-10 while running adjacent request-frame clip gates for the
  replay decorative-callback ownership fix.
- **Behavior**: the cold Jump fixture reports `done=true`, requested/applied
  `Idle`, and position `(4, 0)` before `rollingGate.resolve()`, rather than
  retaining requested `Rolling` with an unresolved operation.
- **Automated reproducer**: from `/home/tommaso/Dev/NeuroClient/app`,
  `npm run animation-readiness:smoke` deterministically fails at
  `scripts/animation-readiness-smoke.mjs:411` with
  `cold Rolling started movement or the FSM before its textures were ready`.
- **Hypothesis**: the fixture's intended cold Rolling asset is already treated
  as resolved, or its gate no longer intercepts the current Jump clip loading
  owner. The case invokes `JumpClip.run` directly and does not cross the
  transaction callback lease changed by the replay fix.
- **Status**: INVESTIGATING.

### Stale Berserker assertion caused unbounded Pytest entity rendering

- **Found**: 2026-07-29 during the complete pre-commit manual-test sweep.
- **Behavior**: the
  `tests/manual/test_37_authored_encounter_mechanics.py::test_caster_crossfire_opens_door_and_mixes_frontline_ranged_and_spell_pressure`
  regression expected a normal `Rage` action from a canonical Berserker, whose
  authored class grant intentionally replaces that row with `Frenzy`. Pytest's
  failed-assertion rewriting then tried to render the recursive Pydantic
  `Entity`; the process ran for 10 minutes 50 seconds at roughly 98% CPU and
  reached 41.6 GB RSS before it was interrupted.
- **Resolution**: the four stale arena assertions now require the exact
  `Frenzy`/no-`Rage` surface and assert against bounded sets of action names.
  The two weapon-affinity cases also select their executable base-attack rows
  explicitly instead of accidentally selecting the stable unavailable Extra
  Attack rows. Entity-target discovery now reports those source-owned Extra
  Attack prerequisites as `requirements_unmet`, distinct from
  `no_valid_targets`.
- **Automated proof**: the exact former reproducer passes in 2.37 seconds at
  272 MB RSS under a 1.5 GB virtual-memory ceiling. The full
  `tests/manual/test_37_authored_encounter_mechanics.py` file reports `39
  passed in 32.12s`. Related action-discovery, Haste,
  Fighter-grant, and stable-action suites report 91 additional passes.
- **Status**: RESOLVED 2026-07-29.

### Isolated evaluation workers eagerly bootstrapped the full engine

- **Found**: 2026-07-29 during the complete pre-commit test sweep.
- **Behavior**: a protocol-only
  `python -m ai.evaluation.config_ladder.worker --help` process took roughly
  15 seconds and exceeded both 10-second isolated-worker regressions.
- **Cause**: the `config_ladder` and `promotion` package initializers re-exported
  executable schedule/model functions. Importing their worker contracts
  consequently bootstrapped scenarios, installed content, the policy runtime,
  NumPy, and SciPy before decoding a request.
- **Resolution**: the abandoned config-ladder, promotion, Elo, and evaluation
  worker platform was deleted. AI gameplay validation now starts canonical
  product encounters from focused `tests/ai/` regressions.
- **Automated proof**:
  `tests/architecture/test_ai_import_direction.py` rejects the removed worker
  packages, evaluator imports, and scenario-construction aliases throughout
  maintained production and test roots.
- **Status**: RESOLVED 2026-07-29.

### Inventory-provided authored actions disappeared after spending action economy

- **Found**: 2026-07-29 during the complete pre-commit test sweep.
- **Behavior**: charge-valid Wand of Fireballs actions disappeared after one
  cast even though entity-owned authored affordances are required to remain
  present with a closed unavailable status for stable action UI.
- **Cause**: `_collect_use_actions` dropped every inventory-provided row whose
  current action requirements failed instead of projecting the same
  `SOURCE_UNAFFORDABLE`, `REQUIREMENTS_UNMET`, or `NO_VALID_TARGETS` contract
  used by registered entity actions.
- **Resolution**: inventory-provided authored actions preserve their exact
  charge-valid variants and typed unavailable status. `legal_only` discovery
  still omits unavailable rows, finite-charge filtering remains item-owned,
  and contextual environment/object affordances remain sparse.
- **Automated proof**:
  `tests/manual/test_131_inventory_use_actions_legacy_contract.py` reports
  `17 passed`, including the spent-economy 3/4-charge Wand variants, and
  `tests/manual/test_09_action_discovery_and_costs.py` reports `30 passed`.
- **Status**: RESOLVED 2026-07-29.

### Provider-owned condition handlers used the provider block as runtime owner

- **Found**: 2026-07-29 during the complete pre-commit test sweep.
- **Behavior**: Bestow Curse damage placed its condition on the target and its
  handler on the caster; runtime admission rejected the handler because its
  attribution named the provider block instead of the handler's actual owner.
- **Resolution**: child handler attribution now binds the handler's exact
  source/owner UUID while preserving the provider behavior identity.
- **Automated proof**:
  `tests/manual/test_134_cleric_batch1_legacy_contract.py` reports `24 passed`
  and `tests/manual/test_172_behavior_runtime_binding.py` reports `22 passed`.
- **Status**: RESOLVED 2026-07-29.

### Subjective paths disclosed an imperceivable occupant as an endpoint

- **Found**: 2026-07-29 during the complete pre-commit test sweep.
- **Behavior**: subjective path construction could transit an imperceivable
  physical occupant, but endpoint selection exposed the occupied cell itself.
- **Resolution**: subjective endpoint checks ignore only imperceivable physical
  occupancy, preserving privacy without changing objective collision
  authority. Visible larger creatures still block Halfling endpoints while
  Halfling Nimbleness permits the intended transit.
- **Automated proof**:
  `tests/manual/test_12_perception_light_stealth_and_invisibility.py` reports
  `11 passed` and `tests/progression/test_halfling_origin_runtime.py` reports
  `5 passed`, including traverse-but-not-end coverage.
- **Status**: RESOLVED 2026-07-29.

### Origin feature content contract imported non-neutral engine modules

- **Found**: 2026-07-28 while validating origin innate-spell composition.
- **Behavior**: `dnd/core/content/origin_features.py` imports `DamageType` and
  `Size` from `dnd.core.modifiers`, `SavingThrowEffectTag` from
  `dnd.core.saving_throw_types`, and `SenseMode` from `dnd.core.senses`.
  The content-contract dependency boundary rejects all four edges because
  those modules are not dependency-neutral leaves allowed beneath
  `dnd.core.content`.
- **Cause**: `CreatureType`, `DamageType`, and `Size` were still defined in
  stateful `dnd.core.modifiers`, while the architecture allowlist also omitted
  the already dependency-neutral senses contract and saving-throw cause
  contract.
- **Resolution**: the three creature facts now have one canonical owner in
  `dnd.core.creature_types`; active engine, server, AI, and test imports use
  that leaf directly. The content-contract allowlist names the exact neutral
  sense and saving-throw contract edges. A static regression rejects importing
  the creature facts through `dnd.core.modifiers`.
- **Automated reproducer**:
  `tests/architecture/test_dependency_boundaries.py::test_content_contract_package_has_one_exact_import_surface_and_direction`
  deterministically fails and reports the four forbidden import edges.
- **Automated proof**:
  `test_safe_leaf_modules_have_no_project_dependencies`,
  `test_neutral_symbols_have_one_canonical_leaf_owner`,
  `test_creature_fact_enums_are_not_imported_from_stateful_modifiers`, and
  `test_content_contract_package_has_one_exact_import_surface_and_direction`
  all pass in `tests/architecture/test_dependency_boundaries.py`.
- **Status**: RESOLVED 2026-07-28.

### Hosted character terminal evidence has release-only holdings disposition

- **Found**: 2026-07-27 local-profile terminal-settlement convergence.
- **Resolution**: hosted workers now project the same exact runtime holdings
  evidence as the standalone lifecycle and include it in their
  generation-fenced terminal spool. The gateway binds that evidence to the
  pinned deployment and commits replay metadata, summary, the new holdings
  revision, settlement receipt, lease release, ended transition, and manifest
  adoption in one SQLite transaction. The release-only hosted disposition and
  its retry path were deleted.
- **Automated proof**:
  `tests/manual/test_101_game_directory_evidence.py::test_hosted_terminal_settles_pinned_character_holdings`
  now passes normally. It also injects a settlement failure after terminal
  publication begins and proves the whole transaction rolls back before the
  same staged manifest retries successfully.
- **Status**: RESOLVED 2026-07-27.

### Hosted terminal-ready evidence is not durable before gateway publication

- **Found**: 2026-07-27 terminal crash/restart audit.
- **Resolution**: each worker now fsyncs immutable summary, objective replay,
  subjective replay, and optional holdings components before atomically
  publishing a self-authenticating ready manifest last. The manifest is fenced
  by game, worker identity, worker generation, terminal coordinates, component
  schemas, byte sizes, and SHA-256 digests. Gateway startup imports and adopts
  valid filesystem or previously staged manifests before orphan interruption.
- **Automated proof**:
  `tests/manual/test_110_gateway_restart.py::test_gateway_directory_has_durable_terminal_ready_manifest`
  proves the immutable migration contract, and
  `tests/manual/test_110_gateway_restart.py::test_gateway_restart_adopts_ready_manifest_before_orphan_interrupt`
  proves a fresh gateway ends the game from the durable ready boundary instead
  of marking it interrupted. `tests/manual/test_189_worker_terminal_spool.py`
  covers ready-last ordering, incomplete writes, stale generations, component
  corruption, manifest tampering, and terminal-coordinate mismatches.
- **Status**: RESOLVED 2026-07-27.

### Persistent player bodies incorrectly entered a non-terminal death-save loop

- **Found**: 2026-07-27 live standalone AI game and NeuroClient terminal-flow
  audit.
- **Behavior**: the canonical schema-2 `PlayerCharacterBody` explicitly set
  `uses_death_saves=True`. A character reduced to zero hit points therefore
  entered `DYING` instead of `DEAD`; target discovery excluded the zero-HP
  actor while encounter faction survival still counted every non-dead actor.
  AI turns could continue without a lawful target, no `EncounterEndEvent` was
  committed, and replay/summary publication never reached its terminal
  barrier.
- **Resolution**: canonical persistent player bodies now follow the selected
  product rule `0 HP -> DEAD` and no longer opt into death saves. The ordinary
  death event, life-state presentation cue, encounter faction check, AI stop,
  replay close, and summary publication now share one terminal boundary.
- **Automated proof**:
  `tests/progression/test_player_character_body.py::test_player_body_is_public_but_owns_no_progression_or_possessions`
  and
  `tests/progression/test_schema2_character_materialization.py::test_schema2_player_zero_hp_commits_dead_and_terminal_encounter`
  cover the production materializer and exact engine event order.
  `tests/manual/test_187_standalone_local_game_lifecycle.py::test_ai_match_publishes_local_terminal_replays_and_game_history`
  covers AI scheduling, portable replay artifacts, durable summary, and the
  absence of terminal `DYING`/`STABLE` snapshots.
  NeuroClient's `app/scripts/encounter-end-presentation-smoke.mjs` covers exact
  `DEAD -> die -> encounterResult` ordering without inference.
- **Status**: RESOLVED 2026-07-27.

### Sorcerer runtime features without lawful engine primitives

- **Found**: 2026-07-26 reversible Sorcerer composition tranche.
- **Resolution**: Distant, Quickened, and Twinned Spell are the only
  metamagics offered by the current build selector. The other five SRD rows
  remain public future catalog content but are explicitly non-selectable and
  fail closed if called directly. The authored progression therefore selects
  two implemented options at Sorcerer 3 and the remaining implemented option
  at Sorcerer 10; it does not advertise an impossible fourth option at level
  17. Elemental Affinity now contributes the
  ancestry-matching Charisma damage bonus exactly once per cast and removes it
  by source receipt. Its optional half is an exact authored action that spends
  one sorcery point for 600 rounds of the ancestry-matching resistance; no
  permanent resistance condition survives materialization or respec. Draconic
  Presence now owns two exact aura-mode actions, ordinary concentration, a
  10-round 60-foot turn-start aura, source-specific 24-hour immunity, and
  cross-entity cleanup during respec.
- **Automated proof**:
  `tests/progression/test_sorcerer_character_grant_appliers.py`,
  `tests/progression/test_spell_damage_affinity_contributions.py`, and
  `tests/progression/test_sorcerer_progression_definitions.py`.
- **Status**: RESOLVED 2026-07-26.

### Existing-class composition had no cross-class release owner

- **Found**: 2026-07-27 pre-SDK character-progression release gate.
- **Error**: Fighter 10-20 fixture composition omitted Champion's second
  Fighting Style. Sorcerer 10-20 omitted its third implemented Metamagic and
  reselected an already-known cantrip. No maintained test materialized every
  Fighter, Barbarian, and Sorcerer level or the six ordered multiclass pairs,
  so these authored-choice gaps and cross-class combination policy were not
  measured together. Starting-equipment packages were also authored as ordinary
  class-level-one choices, incorrectly requiring a second package when level
  one of a later class was added.
- **Resolution**: the built-in authored composer now supplies the exact
  Fighter and Sorcerer choices, retains each newly learned cantrip, and uses
  the honest three-option Metamagic progression. The existing reversible
  structural installer is public as `apply_character_composition`, allowing
  one Entity to remove and replace its composition without touching holdings,
  identity, position, or unrelated body state. Starting equipment is now an
  exact first-class creation choice only; multiclass entry cannot request or
  grant it. An authored Fighter 2 / Sorcerer 3 premade proves that the general
  schema-2 ledger, validator, holdings composer, materializer, and cleanup path
  handle a real multiclass catalog build without a premade-only Entity path.
- **Automated proof**:
  `tests/progression/test_multiclass_composition.py` covers levels 1-20 for all
  three classes, all ordered pairs, first-class saves, restricted entry
  proficiencies, total-level proficiency, mixed HP/hit dice and short-rest
  spending, Extra Attack rank overlap, AC candidate resolution, spell-source
  retention, a three-class build, martial attack math, cleanup, and same-Entity
  recomposition, first-class-only starting equipment, and the canonical
  Fighter 2 / Sorcerer 3 premade.
  `tests/progression/test_starting_equipment_packages.py` owns package creation
  semantics, and
  `tests/progression/test_sorcerer_progression_definitions.py` owns the bounded
  Metamagic contract.
- **Status**: RESOLVED 2026-07-27.

### Neurodragon source digest was invalidated by a line-ending rewrite

- **Found**: 2026-07-26 character-progression baseline.
- **Automated reproducer**:
  `uv run python -c "import dnd.content_system.builtin"` failed deterministically
  before any pytest collection with `RuntimeError: Neurodragon original source
  document digest does not match its content-source contract`.
- **Cause**: the authenticated
  `content_data/sources/neurodragon_original_b2b3930.txt` working-tree artifact
  had been mechanically rewritten from LF to CRLF while its source contract
  correctly retained the digest of the canonical LF bytes.
- **Resolution requirement**: restore canonical LF bytes without weakening or
  recomputing the provenance assertion, then prove the same import and the
  focused content bootstrap test pass.
- **Resolution**: restored the authenticated source document to canonical LF
  bytes. The import reproducer now passes and
  `tests/manual/test_162_content_system_bootstrap.py` is green (`6 passed`).
- **Status**: RESOLVED 2026-07-26.

### Canonical AI hard cut

- **Native AI no longer uses a subprocess or self-HTTP gameplay client.**
  `NativeAIController` calls the `dnd.ai` policy kernel directly in process;
  the kernel owns subjective projection, memory reduction, validation,
  authoritative dispatch, feedback, and timing. The bundled policy and the
  `custom_ai.tactical` example contain decision logic only. Import-direction,
  zero-local-import, acyclic-boundary, and sole-dispatch-consumer invariants
  are measured by `tests/architecture/test_ai_import_direction.py`; policy,
  registry, instrumentation, and native execution are measured by
  `tests/ai/` and `tests/manual/test_151_native_ai_execution.py`.
  **Status: RESOLVED 2026-07-24.**
- **Registered external providers are a distinct deployment boundary over the
  same policy contract.** The main server authenticates provider handshakes,
  opens generation/token-fenced assignments, sends only
  `SubjectiveWorldState` plus ordered feedback, receives only typed
  `PolicyIntent`, and still performs the authoritative engine commit locally.
  Every external character receives a distinct controller, lease, token,
  policy object, memory object, and contiguous decision sequence. The
  real-socket matrix proves `builtin.basic` versus `external.basic`,
  `external.basic` versus `external.tactical`, replicated authoritative
  actions from both sides, four-character capacity rejection, and exact
  teardown in `tests/ai/test_live_ai_matchups.py`. Protocol, idempotency,
  controller fences, and rollback are covered by
  `tests/ai/test_external_ai_protocol.py`,
  `tests/ai/test_external_ai_service.py`,
  `tests/ai/test_registered_ai_provider.py`,
  `tests/ai/test_registered_ai_controller.py`, and
  `tests/manual/test_153_registered_ai_game_creation.py`.
  **Status: RESOLVED 2026-07-24.**
- **The bundled policy no longer burns a turn in no-progress cycles.**
  Assignment-owned, per-actor turn memory suppresses revisited movement,
  repeated successful setup/capability transforms, zero-utility inverse
  object toggles, and voluntary concentration teardown while deliberately
  preserving multiple legal attacks and interrupted movement replanning.
  Red-first regressions live in `tests/ai/test_basic_policy.py`.
  **Status: RESOLVED 2026-07-24.**
- **AI turns no longer monopolize the server event loop.** Encounter exposes
  one bounded autonomous action boundary at a time; the server coordinator
  yields between boundaries and uses an explicit deferred-provider fence.
  Actor/controller rotation, multi-step turns, and the existing complete-turn
  engine behavior are measured by
  `tests/manual/test_152_deferred_controller_boundary.py`. Hosted worker
  responsiveness and terminal publication are covered by
  `tests/manual/test_110_multi_game_gateway.py`.
  **Status: RESOLVED 2026-07-24.**
- **Game creation now has one prepared activation lifecycle.** Creation cannot
  execute an AI action before a client joins and captures replication
  identity. The exact sequence is start, join, bootstrap, activate, then
  follow using that same bootstrap. Server lifecycle and authority are covered
  by `tests/manual/test_150_prepared_scenario_lifecycle.py` and
  `tests/manual/test_150_native_ai_game_creation.py`; the SDK's no-second-fetch
  seed/reset semantics are covered by
  `sdk/typescript/src/tests/subjectiveClient.test.ts`.
  **Status: RESOLVED 2026-07-24.**
- **The old `ExternalAIController`, managed-service readiness path, and
  validation-start aliases are deleted.** `RegisteredAIController` is the sole
  production external-provider controller. Codex takeover remains functional
  through its public subjective surface. Retained Direct Codex artifact capture
  uses a focused tooling client for canonical game creation, joining, bootstrap,
  and activation; the production validation harness is deleted. Absence and
  retained Codex behavior are measured by
  `tests/manual/test_96_game_creation_api.py`,
  `tests/manual/test_30_codex_takeover_tools.py`,
  `tests/manual/test_38_ai_validation_server_start.py`,
  `tests/manual/test_47_direct_codex_artifacts.py`, and
  `tests/architecture/test_ai_import_direction.py`.
  **Status: RESOLVED 2026-07-24.**
- **Simulation delay correction metadata now agrees with the accepted
  boundary.** The engine default and endpoint accept `0.0`, so structured
  errors now advertise `min_delay=0.0` rather than the stale `0.1`.
  `tests/engine/test_encounter_apis.py::test_eb_18_014_replication_identity_and_simulation_errors_are_explicit`
  failed before the correction and owns the boundary.
  **Status: RESOLVED 2026-07-24.**

### Full active-suite audit

- The first exhaustive file-isolated pass ran all `244` active Python test
  files: `228` files passed, `16` files failed, and none timed out. The `59`
  failing selectors separated into `42` abandoned book/document checks and
  `17` stale retained-test contracts; no new production defect was found.
- Retired `267` book-coupled cases: `251` public-MDX prose/snippet cases whose
  executable behavior is duplicated by `192` maintained standalone tests,
  `7` missing-document audit cases, and `9` prose/parity checks from the mixed
  repository-integrity file. No book or parity artifact was recreated.
- Corrected the `17` retained failures in their existing measuring tests:
  authoritative potion cost/turn boundaries, threatened Fire Bolt dice,
  level-five spell slots, frozen objective replay source slots, UTC event
  timestamps, authoritative `LifeState` memory, trace authorization, arena
  route serialization, finite-horizon no-progress setup, and removal of an
  incidental entity-value count.
- The second exhaustive pass ran every remaining file separately:
  **`241/241` files and `2,590/2,590` tests passed, with zero failures,
  timeouts, skips, xfails, or xpasses.** Logs are retained under
  `/tmp/dnd-suite-final-shard0.PztvYk`,
  `/tmp/dnd-final-pytest-shard1of3-yUDNMR`, and
  `/tmp/dnd-pytest-final-shard2-e5lAVl`.

### Public content catalog had 23 unauthored game-icon assets

- **Found**: 2026-07-26 while reconciling the authenticated built-in icon
  ledger with the pinned 455-asset NeuroClient atlas.
- **Behavior**: `23` public definitions have the exact
  `missing_asset` disposition (`17` items, `4` actions, `1` spell, and `1`
  reaction); there are no ambiguous rows. The missing item roots propagate to
  `40` recipe-preset rows through exact definition inheritance. No condition
  definition is missing an icon.
- **Exact roots**: the item roots are `armor.cloth`,
  `armor.circus.performer_leather`, `apparel.bracers`,
  `apparel.chain_coif`, `apparel.cloth_hood`, `apparel.fine_clothes`,
  `apparel.gauntlets`, `apparel.great_helm`, `apparel.horned_helmet`,
  `apparel.leather_gloves`, `apparel.leather_hood`,
  `apparel.monster_hands`, `apparel.monster_helm`, `gear.field_kit`,
  `weapon.double_bladed_sword`, `weapon.sickle`, and `weapon.trident`.
  The behavior roots are `action.item.field_kit.deploy`,
  `action.core.drop`, `action.core.drop_prone`, `action.core.stand_up`,
  `spell.aegis_spark`, and
  `reaction.class_feature.paladin.divine_smite`.
- **Cause**: none of these exact authored identities or presentation keys
  exists in the pinned game-icon index. This is not a binding/import defect.
  Actor `equipment_sprites` belong to a separate renderer asset domain and
  cannot be substituted for inventory/action `icon_key` values.
- **Reachability**: the missing roots intersect neither the three approved
  premade templates nor any of the `20` hero and `38` monster-party current
  game-creation configurations. They remain public catalog/authoring content,
  so the gap must not be hidden with aliases or an inferred generic icon.
- **Minimum closure**: author and authenticate `22` definition-level atlas
  assets/binding decisions. The Field Kit item binding propagates to
  `action.item.field_kit.deploy` through its exact `GRANTS_ACTION` dependency,
  and the `14` variant-bearing root bindings close all `40` preset rows without
  variant-specific icon aliases.
- **Resolution**: the pinned NeuroClient manifest now authenticates `477`
  assets at SHA-256
  `dfcecb24af9b225dd8867eba9ee1801a6d986f440169744e7d3098ab2bd3dafc`.
  The `22` new semantic keys bind all `23` definitions, including exact
  `item.field-kit` inheritance for the provider-owned deploy action. The
  generated definition ledger has zero unresolved rows and the affected
  recipe presets inherit their exact definition binding.
- **Exact reproducer**:
  `tests/manual/test_183_content_icon_bindings.py::test_every_public_builtin_has_no_unresolved_icon_assets`
  now runs as a normal regression and asserts that public `missing_asset` and
  `ambiguous` rows are empty.
- **Status**: RESOLVED 2026-07-27.

### Recently resolved engine and rules defects

### Turn execution identity was request-context-local

- **Found**: 2026-07-27 while restoring the active AI validation harness after
  the character-factory hard cut.
- **Behavior**: a turn opened by `advance_encounter()` in one async task could
  not be closed by the later action/end-turn HTTP request, and events created
  between those requests lost their causal turn identity.
- **Cause**: `EventQueue` is the process-global owner of one event stream, but
  its active turn identity was stored in a `ContextVar`, whose value does not
  cross independent `asyncio.run()` or ASGI request contexts.
- **Resolution**: the active turn identity is now ordinary protected
  `EventQueue` state, reset and cold-load-audited alongside the rest of the
  singleton event stream.
- **Exact reproducer**:
  `tests/manual/test_184_turn_execution_identity.py::test_turn_identity_survives_separate_async_request_contexts`.
- **Status**: RESOLVED 2026-07-27.

### Schema-2 spell slots disappeared from AI decision epochs

- **Found**: 2026-07-27 after the request-context turn crash was fixed.
- **Behavior**: schema-2 Sorcerers could spend normal spell slots, but their
  subjective `ActionEconomyState.spell_slots` was empty. The policy therefore
  valued capability transforms against incomplete resource facts.
- **Cause**: normal multiclass spell-slot capacity is now an owned aggregate
  modifier, while the decision-epoch projector still treated only the retired
  base modifier as maximum capacity.
- **Resolution**: `ActionEconomy` exposes the installed aggregate capacities,
  and the AI projector uses those exact maxima while preserving current
  post-cost values.
- **Exact reproducers**:
  `tests/progression/test_normal_spell_slot_capacity.py::test_normal_slot_capacity_sets_all_ranks_without_touching_turn_resources`
  and
  `tests/progression/test_schema2_character_materialization.py::test_schema2_materializer_installs_one_shared_normal_slot_table`.
- **Status**: RESOLVED 2026-07-27.

### Retired standalone self-play omitted cold content startup

- **Found**: 2026-07-27 in the retained cross-process deterministic replay
  check.
- **Behavior**: calling `run_external_selfplay()` from a fresh Python process
  failed with `RuntimeError: Content system is not installed`; pytest masked
  the defect through its session fixture.
- **Resolution**: the abandoned standalone self-play/evaluation framework was
  deleted. Native/external and external/external gameplay validation now uses
  the ordinary server composition path in `tests/ai/test_live_ai_matchups.py`.
- **Automated proof**:
  `tests/architecture/test_ai_import_direction.py` requires
  `ai/external_selfplay.py` and `ai/validation_harness.py` to remain absent and
  rejects imports of either retired surface.
- **Status**: RESOLVED 2026-07-27.

### Weapon attack affordances dropped their exact dynamic icon provider

- **Found**: 2026-07-26 during the isolated live schema-5 NeuroClient
  action-bar gate.
- **Behavior**: `core.rules:action:action.attack@1` is deliberately
  `intentional_dynamic_provider`, but an armed Attack row exposed neither a
  catalog icon nor the equipped weapon UUID. Exact clients therefore had no
  lawful item presentation join and failed closed to `action.unavailable`.
- **Cause**: `Entity._collect_entity_actions()` read the equipped weapon for
  its display name and damage types but did not pass that same weapon instance
  into `AvailableActionInfo.source_item_uuid`.
- **Exact reproducer**:
  `tests/manual/test_181_affordance_content_identity.py::test_weapon_attack_affordance_names_its_exact_equipped_item_provider`
  asserts both the deliberate null action icon and the exact equipped
  `Weapon.uuid` on every weapon-slot affordance.
- **Resolution**: Weapon-slot affordances now carry the equipped weapon UUID
  while retaining `is_item_use=false`; Attack, Extra Attack, Frenzied Strike,
  and other weapon-slot variants share the same collector path. No wire shape
  or generic icon alias was added.
- **Status**: RESOLVED 2026-07-26.

### AI performance regressions encoded two retired discovery assumptions

- **Found**: 2026-07-26 in the focused post-fix AI/epoch matrix.
- **Behavior**:
  `test_required_target_aoe_prefilter_uses_action_relationship_filter`
  constructed an unauthored `BaseAction`, which the canonical content boundary
  correctly rejects, while
  `test_full_budget_move_refreshes_visibility_without_full_path_radius`
  still expected an exhausted Move action to disappear.
- **Resolution**: The AoE performance probe now uses the authored Fireball
  action contract with its relationship filter specialized for the test. The
  movement test now asserts the active stable-row contract:
  `target_cost_unaffordable` with no executable targets. Neither assertion was
  weakened; both still measure their original path-radius/prefilter behavior.
- **Exact reproducers**:
  `tests/manual/test_43_ai_runtime_performance.py::test_required_target_aoe_prefilter_uses_action_relationship_filter`
  and
  `tests/manual/test_43_ai_runtime_performance.py::test_full_budget_move_refreshes_visibility_without_full_path_radius`.
- **Status**: RESOLVED 2026-07-26.

### Synthetic game-summary evidence retained a legacy condition identity

- **Found**: 2026-07-26 while running the focused objective-summary reducer
  regression after the condition-content hard cut.
- **Behavior**: The synthetic Prone application in
  `tests/manual/test_102_game_summary.py` bypassed the normal condition
  lifecycle and therefore reduced to an unbound Python-path identity instead
  of `core.rules:condition:condition.prone@1`.
- **Resolution**: The fixture now uses the canonical runtime behavior-binding
  gateway before constructing its synthetic completion event, and its terminal
  snapshot and summary assertions use the same authenticated condition
  identity. Production condition application and the summary reducer were
  unchanged.
- **Verification**: `tests/manual/test_102_game_summary.py` passes (`6 passed`).
- **Status**: RESOLVED 2026-07-26.

### Objective parity guessed weapon stance from occupied slots

- **Found**: 2026-07-26 from live render-parity diagnostics for actors with
  both melee and ranged loadouts.
- **Behavior**: The canonical subjective world correctly projected the
  engine-selected ranged stance, while the independent parity oracle reported
  melee because it treated the presence of any melee-slot item as selection.
- **Cause**: `APIEquipmentOverview` exposed occupied slots but omitted the
  authoritative selected `WeaponSet`, so the objective oracle could only make
  a lossy inference.
- **Resolution**: `APIEquipmentOverview.active_weapon_set` is now a required
  dependency-neutral state fact projected directly from `Equipment`; both
  objective parity oracles consume it instead of inspecting slot occupancy.
- **Verification**:
  `tests/manual/test_125_subjective_objective_render_parity.py::test_parity_preserves_selected_ranged_stance_with_both_weapon_sets`
  reproduces the dual-loadout selected-ranged case and the complete parity
  file passes (`8 passed`). `tests/manual/test_125_active_weapon_stance.py`
  remains green (`3 passed`).
- **Status**: RESOLVED 2026-07-26.

### Environment-item regressions still constructed unbound legacy fixtures

- **Found**: 2026-07-26 while validating the action-discovery affordability
  separation.
- **Behavior**: Six maintained environment-item selectors failed closed in
  `BehaviorBinder` or `Entity._make_action_info()` because direct
  `TestDoorA`, `TrapLever`, `StorageChest`, and `UsableItem` constructors
  supplied actions with no authenticated item root:
  `test_override_and_default_door_actions_toggle_spatial_state`,
  `test_lever_depletion_removes_only_its_linked_trap`,
  `test_chest_discovery_loot_and_empty_state_are_one_contract`, and
  `test_multi_action_environment_item_executes_and_depletes` in
  `tests/manual/test_134_stackable_usable_item_legacy_contract.py`, plus
  `test_closed_door_invalidates_prepared_intercept_path_at_trigger_time` and
  `test_open_door_is_authoritative_when_dodge_roll_triggers` in
  `tests/manual/test_legacy_reactive_reaction_coverage.py`.
- **Cause**: The behavioral regressions predated the item-content hard cut and
  bypassed canonical recipe materialization. Production map-editor and runtime
  construction already used bound environment recipes.
- **Resolution**: The tests now materialize exact Door, Trap Lever, Storage
  Chest, Campfire, and nested Potion recipes. The encounter-local trap link is
  attached through `UsableItem.bind_dynamic_use_action()`, preserving the
  reviewed provider dependency without weakening or bypassing the binder.
- **Verification**:
  `tests/manual/test_134_stackable_usable_item_legacy_contract.py` and
  `tests/manual/test_131_inventory_use_actions_legacy_contract.py` pass
  together (`26 passed`), including all four original selectors. The complete
  reactive-reaction file passes (`27 passed`) and
  `tests/manual/test_180_environment_content_identity.py` passes
  (`7 passed`), including both additional door selectors.
- **Status**: RESOLVED 2026-07-26.

- **Spell catalog composition no longer creates a cold-start import cycle.**
  During closure of the public spell catalog, the native
  `dnd.spells.catalog_content` leaf briefly imported the extension package to
  include Aegis Spark. A fresh process then failed while importing
  `dnd.actions_functional` through the chain content bootstrap → class content
  factories → sorcerer → actions functional → spells catalog → extensions →
  field focus → bestiary. The extension join now lives at the higher
  `dnd.content_system.spell_catalog_composition` boundary; the native spell
  catalog has no extension dependency. The deterministic cold-start
  reproducer and an AST import-boundary assertion are
  `tests/architecture/test_spell_catalog_composition.py`.
  **Status: RESOLVED 2026-07-26.**
- **Encounter-start projection no longer poisons a bootstrapped player
  journal.** The staged game-creation regression bootstrapped a player before
  activation, then the first `EncounterStartEvent` was incorrectly mapped
  with `projected_combatant_uuids`. That field is terminal metadata and is
  valid only for `EncounterTransition.END`, so the canonical cue validator
  rejected the opening frame and made the journal unhealthy. Start cues now
  omit terminal combatants while encounter-end cues retain their safe terminal
  barrier and projected combatant set. Measured by
  `tests/manual/test_150_native_ai_game_creation.py::test_activation_requires_exact_joined_bootstrap_identity_and_is_idempotent`;
  the focused mapper and player-journal suites retain the END invariant.
  **Status: RESOLVED 2026-07-24.**
- **Standalone AI-vs-AI observation again installs an explicit subjective
  perspective.** The rolled-back NeuroClient sent `null` for both observer
  fields after creating an AI-vs-AI match and when attaching to an existing
  standalone match. The backend correctly rejected both zero-control joins
  with `400 observer_perspective_required`; embedded AI services were already
  starting and executing actions. The client now derives the deduplicated,
  lexicographically ordered union of both resolved side assignments, submits
  it as `observer_entity_uuids`, and selects the first member as
  `active_observer_uuid`. It does not request control, faction authority, or
  objective state. The red-first
  `/home/tommaso/Dev/NeuroClient/app/scripts/ai-vs-ai-observer-smoke.mjs`
  reproducer now covers both new-game and existing-game paths, asserts the
  exact join body/response, requires a `spectator_knowledge_union` bootstrap,
  live SSE, connected/ready rendered state, and a completed objective AI
  action from one of the created combatants. Backend standalone/hosted
  authority semantics and the player wire contract are unchanged.
  **Status: RESOLVED 2026-07-24.**
- **Movement-owned reactions now retain their exact pre-edge boundary.**
  Canonical projection coalesced every contiguous committed
  `StepMovementEvent` into one `MovementPresentationCue`, then mapped each
  step lineage to that same cue. Opportunity Attacks at different path
  indices consequently became children of one full-path movement and lost the
  timing needed for animation. The mapper now validates nonmovement semantics
  first, creates segment boundaries only for surviving delivered
  Attack/Spell/Shove reactions, and starts the owning segment at the exact
  triggering step. Hidden reactions cannot leak through an unexplained split;
  a visible reaction whose exact step is undisclosed remains a root cue rather
  than falling through to another disclosed segment, and a post-step
  descendant cannot be misclassified as pre-motion. Ordinary nonreactive runs
  remain coalesced. Real Move and Jump regressions execute two Opportunity
  Attacks at different steps and assert engine lineage/cursor timing, ordered
  trajectories, path indices, closed graph, JSON round-trip, hidden-reaction
  privacy, exact-step disclosure, and pre-edge ordering. The handwritten
  TypeScript decoder mirrors both movement-child kind and source-cursor
  invariants. The wire model, schema hash, and route family are unchanged.
  Mapper `20/20`, player contract `23/23`, journal
  `15/15`, runtime `9/9`, routes `16/16`, SDK `65/65`, generator check,
  focused Pyright, and diff check pass. **Status: RESOLVED 2026-07-24.**
- **Every ordinary weapon-attack constructor now freezes the same cold
  presentation metadata.** `ExtraAttack` and `FrenziedStrike` constructed
  `AttackEvent` independently and omitted weapon damage categories; hits
  happened to reconstruct them from damage packets, while misses reached the
  canonical player mapper with `damage_types=[]` and were correctly dropped.
  Normal Attack, Extra Attack, and Frenzied Strike now share one declaration
  boundary backed by `Equipment.snapshot_attack_event_metadata`; the snapshot
  includes ordered temporary and weapon-owned damage categories, so a missed
  scaled True Strike also retains its radiant identity. Natural attacks remain
  the single explicit non-equipment constructor, protected by an AST boundary
  test. **Status: RESOLVED 2026-07-24.**
- **Monster Multiattack no longer charges its off-hand child as a player bonus
  action.** `Attack` rewrote every off-hand cost list, including an explicitly
  supplied empty list. Bandit Captain and Veteran therefore completed only two
  of their three melee attacks whenever their bonus action was unavailable.
  Slot-based cost selection now applies only when the caller did not provide a
  cost contract; a real three-attack regression pre-spends the bonus action and
  proves the parent-owned Multiattack cost is unchanged.
  **Status: RESOLVED 2026-07-24.**
- **Shake Awake now ends every effect that declares the typed capability.**
  Sleep, Eyebite Asleep, and Hypnotic Pattern declare
  `ConditionRemovalTrigger.SHAKE_AWAKE`; the action no longer switches on
  concrete condition names. **Status: RESOLVED 2026-07-24.**
- **Flame Strike resolves fire and radiant as independent typed components.**
  Fire immunity now removes only the fire component while the radiant
  component still applies. **Status: RESOLVED 2026-07-24.**
- **Potion-created Greater Invisibility and Haste effects now carry the
  `MAGICAL` condition tag.** **Status: RESOLVED 2026-07-24.**
- **Potion of Haste now has one explicit lethargy contract.** Its description,
  setup profile, created `HasteEffect`, and removal regression all agree that
  lethargy applies when the effect ends. **Status: RESOLVED 2026-07-24.**
- **Chill Touch execution and its outcome profile now share the caster's spell
  critical threshold.** The maintained regression proves a modified natural-19
  threshold is both advertised and executed. **Status: RESOLVED 2026-07-24.**
- **Standard arena floor objects and saved Trap Levers now retain live
  authority.** Arena, evaluation, item-factory, drop/spill, and summoned-object
  code contained 18 direct `GridMap.place_object` calls for `BaseItem`
  instances. Fifteen left `tile_uuid`, `position`, and `get_position()` in
  conflict with the grid; three manually duplicated the canonical state
  update. Every item placement now flows through `BaseItem.place_on_grid`;
  the sole remaining raw call belongs to the intentional non-item
  `ContinualFlameObject`. Separately, a cold map rebuilt the spike handler
  under a new UUID without relinking the lever, so a loaded map silently lost
  `Pull Lever`. Loading now creates the action from the regenerated handler
  and tile identities. The crypt roundtrip asserts GridMap/BaseItem agreement,
  a live handler at every spike tile, and equality of every non-runtime
  projected field. **Status: RESOLVED 2026-07-24.**

### Reproduced focused test and contract failures

- **Accepted End Turn results now correlate through one canonical row.** Live
  embedded-AI validation returned an accepted `CommandResult` with
  `row_id="special|End Turn|index=0"`, but the policy host's stale
  `row_id is None` rule classified it as `UNMATCHED` and retained both the
  pending submission and submitted-epoch writer. The canonical epoch, runtime,
  and server already agreed on the special row; only host correlation and its
  test helper disagreed. `END_TURN_ROW_ID` now owns that dependency-neutral
  protocol identity. Epoch construction, runtime command tracking, every
  accepted/rejected/stale end-turn result, and `PolicyHost` use the same
  constant. The host fails closed on a missing or different row, but the
  canonical accepted result records `ACCEPTED` and consumes its pending
  submission. The previously masking helper now emits the real server shape.
  Regressions cover both a terminal fallback and a routine-bearing pursuit
  yield across the turn boundary, including exact disposition, routine plan,
  and pending consumption; the live route regression asserts the same row.
  Full policy-host tests pass `54/54`, focused host correlation passes `2/2`,
  the end-turn route passes `1/1`, epoch identity passes `2/2`, and focused
  production Pyright reports zero errors. The pre-existing test-only Pyright
  baselines remain `10` in `test_36` and `177` in `test_48`.
  **Status: RESOLVED 2026-07-24.**
- The gauntlet watcher, Quickened Spell dice, caster-potion cost, battlefield
  schedule, combined affordance equality, policy canceled-action memory, AI
  arena catalog, typed available-action access, and pre-Shove action-menu
  failures are resolved. The repairable public-manual structural drift is also
  resolved; its sole remaining selector requires the absent
  `engine_book/parity_matrix.md` source artifact tracked below.
- The AI runtime-performance audit is resolved. Twelve failures were stale
  retained-fixture, cache-count, or exact-golden contracts; one exposed real
  current-policy work that planned 242 movement endpoints before selecting the
  same dominant typed Haste setup. Canonical migrations and semantic
  assertions replace the stale fixtures, and current policy skips only
  dominated new starters for a durable setup that grants extra actions. The
  complete file passes `63/63`; focused Pyright is clean.
- The abandoned engine-book and public-MDX maintenance checks have been
  retired. Executable engine behavior remains covered by the maintained
  standalone tests; no missing prose artifact remains an active issue.

### Static typing debt

- The complete maintained production scope (`dnd`, `server`, `ai`,
  `custom_ai`, and `services`) plus AI, architecture, engine, and progression
  tests now passes Pyright with zero errors and zero warnings.
- The final close-out removed stale executable book wrappers, narrowed
  materialized item/event test fixtures to their declared types, and corrected
  directional environment recipes to use the same closed direction/channel
  literals as their runtime objects.
- Historical nonzero counts are retained only as discovery evidence.
  **Status: RESOLVED 2026-07-30.**

### Historical reports requiring fresh durable reproduction

- Subjective stream subscription/resync churn and the old 50K-character
  Sorcerer summary were recorded only in removed `/tmp` artifacts. They remain
  plausible performance concerns, but are not current verified failures.
- The old final-kill omission in a Codex brief is partially covered by current
  remembered-death tests; the exact terminal UI brief needs a fresh regression
  before being called open.
- The former NeuroClient event-sidebar unused-import report no longer matches
  the current source. The separate Spell Studio numeric-input locator failure
  remains an external harness issue.

### Recently verified fixes

- **Managed AI bootstrap no longer publishes executable authority before the
  opening turn starts.** A fresh live game exposed a startup race: game
  creation assigned the opening AI actor while the encounter remained
  `NOT_STARTED`, and the agent's readiness bootstrap received a decision epoch
  before `_advance_managed_start_or_abort()` began the turn. Its first legal
  Frenzy command was therefore rejected with `turn_not_in_progress`, after
  which resync recovered. The canonical epoch builder now requires
  `TurnState.IN_PROGRESS`, and the server also retires a cached epoch whenever
  the turn leaves that state. Cold-bootstrap and cached-authority regressions
  failed before the fix and now pass; adjacent publication checks and focused
  Pyright are green. No wire shape changed.
  **Status: RESOLVED 2026-07-24.**
- **The extended validation schedule now reaches the SRD Undead Crypt.** The
  crypt was the only catalog arena matching none of the rotating focus labels:
  its fixture contains a skeleton archer, but its metadata omitted the
  `skeletons` tag used by monster-side schedule slots. The corrected metadata
  makes the real arena eligible for `skeleton_side`; the maintained schedule
  regression asserts the exact `srd_undead_crypt` identity and focus while
  retaining full-catalog equality. **Status: RESOLVED 2026-07-24.**
- **Hot Codex release now drains actor-scoped telemetry before relinquishing
  ownership.** A live loopback takeover reproduced successful gameplay plus a
  teardown-only `403 agent_event_actor_not_controlled`: `HotCodexSession`
  released the upstream claim first, then closed its policy/runtime telemetry
  queues. Events already queued for the formerly controlled actor were
  therefore rejected even though command execution and claim restoration
  succeeded. Release now closes both local telemetry layers while the claim is
  authoritative and only then releases upstream control. The deterministic
  regression blocks an actor event until runtime close, proves delivery
  precedes upstream release, forces a post-flush runtime cleanup exception, and
  proves ownership is still released with that failure retained in the session
  transcript. The complete hot-runtime file reports `26 passed`; focused
  Pyright reports zero errors. **Status: RESOLVED 2026-07-24.**
- **Hot Codex release now interrupts the checked-out observation socket.**
  The observation worker blocks in HTTPX `Response.iter_lines()` with an
  intentionally unbounded SSE read timeout. Closing its `httpx.Client` only
  closes the idle connection pool; it does not interrupt the network stream
  already checked out by the worker. Release consequently spent its complete
  four-second runtime-cleanup deadline joining that worker, then reported both
  `subjective observation worker did not stop` and the secondary
  `runtime telemetry cleanup exhausted its deadline`. The runtime now
  registers the one active response under its lifecycle lock, shuts down the
  response transport's checked-out socket in both directions, and then closes
  its `network_stream` during cooperative shutdown. A first close-only repair
  was rejected by the live gate: `Client.close()`, `Response.close()`, and
  `SyncStream.close()` are not guaranteed to wake a blocking Linux `recv()` in
  another thread, whereas `socket.shutdown(SHUT_RDWR)` provides the required
  cross-thread wake-up without injecting an asynchronous exception.
  The worker observes the already-set stop flag, exits without producing a
  false stream error, and leaves the remaining aggregate deadline available
  to drain telemetry before upstream ownership is released. A deterministic
  ownership regression models the exact HTTPX checked-out-stream behavior, and
  a second regression runs a real Uvicorn SSE endpoint with an unbounded HTTPX
  read to prove bounded release. Seamless runtime `49/49`, Hot Codex runtime
  `26/26`, and focused production Pyright pass.
  **Status: RESOLVED 2026-07-24.**
- **The tutorial managed-agent stub now satisfies its structural protocol.**
  Focused Pyright over the restored Chapter 21 HTTP coverage found that the
  stub named its `preflight` parameter `_required_agents`, while
  `AgentProcessSpecBuilder` requires the structurally matched name
  `required_agents`. Runtime behavior was unaffected; the fixture now matches
  the protocol exactly. **Status: RESOLVED 2026-07-24; test-only typing fix.**
- **Perceivability transitions now invalidate subjective occupancy paths.**
  The maintained hidden-collision test covered a creature that was already
  Hidden before the observer's first path query. It did not cover the inverse
  sequence: compute paths while the creature is visible, then apply Hidden.
  `GridMap` could reuse the earlier authoritative-occupancy cache entry after
  the observer removed the creature from `senses.entities`, leaving the hidden
  cell absent from movement paths and leaking its occupancy. The map now
  consumes the existing declaration-phase
  `SPATIAL_PERCEIVABILITY_CHANGED` fact and invalidates its occupancy/path
  revision. EB-12-032 proves both visible-to-Hidden and Hidden-to-visible
  transitions update entity visibility and cached path occupancy.
  **Status: RESOLVED 2026-07-24.**
- **EB-17-011 now expects the canonical potion action cost.** The stale active
  assertion expected Greater Invisibility and Haste potion
  `effective_costs == []`, even though `PotionDrinkAction` canonically spends
  one typed bonus action and the maintained item tests enforce that cost. The
  engine behavior was correct; the assertion is being corrected to the exact
  bonus-action cost rather than weakening or bypassing item action economy.
  **Status: RESOLVED 2026-07-24; test-only expectation correction.**
- **GridMap.clear now clears live floor-item location authority.** The
  displaced Phase 1 test checked only that the grid index was empty. A live
  `BaseItem` kept its old `tile_uuid` and `get_position()` after destructive
  map clear, leaving the grid and item in contradictory states. `clear()` now
  snapshots registered floor objects and invokes the canonical
  `on_grid_object_removed(..., clear_location=True)` boundary exactly once per
  object before discarding indexes and tiles. The active regression asserts
  both sides of the invariant for two objects; focused item, grid,
  runtime-reset, Pyright, and dependency checks pass.
  **Status: RESOLVED 2026-07-24.**
- **Field Kit use now emits the canonical item-backed declaration.**
  `DeployFieldFocus` duplicated `BaseAction._create_declaration_event()` but
  omitted the source item UUID, frozen item presentation, and item charge
  cost. Carried and floor-kit actions therefore completed and spent the bonus
  action while never consuming the kit. The redundant override is removed;
  both extension paths now preserve the cold item facts, consume exactly one
  charge, spend only the bonus action, and remove the depleted action from
  discovery. The complete content-extension file reports `6 passed`.
  **Status: RESOLVED 2026-07-24.**
- **Item-backed same-name spell variants now execute the discovered level.**
  The Wand of Fire created distinct three- and four-charge Fireball templates,
  but `SpellScroll.get_use_actions()` rebuilt both at the base third level and
  item discovery gave both rows the same machine name. Direct execution then
  selected the first name match, so the nominal four-charge branch still dealt
  8d6. Item variants now preserve an explicit template `cast_at_level`, use
  the spell variant's exact discovery name, and resolve that exact name during
  execution. The active regression proves three charges/L3/8d6 versus four
  charges/L4/9d6, no spell-slot spending, and no source/discovery mutation
  between branches. **Status: RESOLVED 2026-07-24.**
- **The stacked-potion regression now models two legal turns.** EB-13-008
  attempted two bonus-action drinks in one turn, so the second use correctly
  failed affordability before it could test final-stack cleanup. The fixture
  now resets the actor's turn budget between uses and still proves that each
  completed use spends the bonus action, consumes exactly one stack unit, the
  surviving first unit remains registered with a restored charge, and the
  second legal use unregisters the exhausted item. Focused selector
  `test_eb_13_008_consumable_use_actions_consume_charges_and_stacks` passes.
  **Status: RESOLVED 2026-07-24.**
- **Slow's action-or-bonus-action lockout now covers every action event
  family.** The displaced
  `to_archive/examples/test_slow.py::test_2_action_bonus_lockout` described
  the rule bidirectionally but asserted only `Dodge -> bonus locked`.
  `SlowedEffect` subscribed solely to `BASE_ACTION`, so a bonus-action
  `Jump` (a `MOVEMENT` event) left the creature's action available; attacks
  and spells were outside the same handler as well. The handler now consumes
  the positive serialized action-economy cost from the explicit typed
  `BASE_ACTION | ATTACK | MOVEMENT | CAST_SPELL` family. Free actions,
  reactions, and movement-feet-only events remain non-locking. Active
  regressions cover Dodge, Attack, spell, and Jump representatives in both
  cost directions, the non-locking channels, and repeated Action Surge attacks
  retaining exactly one owned constraint that both turn reset and condition
  removal clean; the complete restored Slow file reports `14 passed`.
  **Status: RESOLVED 2026-07-24.**
- **Generated spell variants apply temporary extra costs exactly once.**
  `_get_costs_for_level()` already normalized `alt_extra_costs` into each
  generated/upcast variant, but the variant retained the same transform and
  `effective_costs` appended it again. This could reject an affordable command
  or consume the named resource twice. Variants now clear only the cost
  transforms after normalizing their executable costs. Active
  `test_126_action_override_runtime.py` maps all 51 displaced action-override
  cases into 26 deterministic tests and asserts both affordability and exact
  post-execution resource consumption. The new suite reports `26 passed`;
  six related tests, focused Pyright, and all 14 dependency-boundary checks
  also pass. **Status: RESOLVED 2026-07-24.**
- **Gust of Wind terrain teardown restores Move reachability.** The displaced
  `to_archive/examples/test_gust_of_wind.py::test_gust_terrain_reactive_paths`
  exposed a real cache-invalidation hole: tile movement costs were restored,
  but `GridMap.movement_revision` and its Dijkstra cache were unchanged, so
  discovery reused paths computed through difficult terrain. Terrain-zone
  application and removal now invalidate the movement cache. Active
  `test_eb_15_045_gust_terrain_removal_restores_cached_move_targets`
  deliberately seeds the affected cache key and verifies the complete
  `9 -> 6 -> 9` target transition and revision changes. The active regression,
  original archived regression, eight related zone/path/cache tests, focused
  Pyright, and dependency-direction checks pass.
  **Status: RESOLVED 2026-07-24.**
- **Haste restricted action no longer steals or suppresses Extra Attack.**
  There *was* substantial archived coverage in
  `to_archive/examples/test_haste.py`, including Haste + Extra Attack + Action
  Surge. The awkward gap is precise: those tests always consumed the ordinary
  Extra Attack before the Haste attack, and one even codified “no Extra Attack
  available after haste action.” They therefore protected the old
  remaining-action-count heuristic instead of the real independent-budget
  invariant. The prior implementation conflated the ordinary action/Extra
  Attack allowance with Haste's restricted one-attack budget, so
  `base attack -> Haste attack` could make the still-unspent Extra Attack
  disappear. The dedicated
  `tests/manual/test_125_haste_restricted_action.py` regression now covers both
  attack orderings, isolation of both budgets, allowed/forbidden restricted
  action families, either-hand weapon choice, both Action Surge orderings,
  Slow interaction, replacement ownership, direct-removal and duration-expiry
  cleanup, wire-name resolution, and turn reset. `uv run pytest
  tests/manual/test_125_haste_restricted_action.py -q` reports `20 passed`.
  **Status: RESOLVED 2026-07-24.**
- **Command branches now own the target's actual next turn.** The three branch
  wrappers used a generic one-round duration and therefore expired at the
  target's next turn before their `TURN_START/EFFECT` handlers could run.
  Halt and Grovel also applied their denial/prone behavior immediately at cast
  time, while Flee changed the grid directly, bypassing ordinary movement
  events and costs and sometimes following a stale path cache. The branches
  now activate on the target's next turn start, remain through that turn end,
  and clean up by exact condition UUID. Flee refreshes the Entity-owned path
  cache and executes an ordinary `Move`; Halt and Grovel use the same
  reaction-preserving turn-spent transform, with Grovel's independent Prone
  lifecycle retained for ordinary stand-up behavior. Focused validation
  reports `16 passed` in
  `tests/manual/test_134_cleric_batch1_legacy_contract.py`, `13 passed` in
  `tests/engine/test_condition_transform_ownership.py`, and zero Pyright
  errors across the changed production and test files.
  **Status: RESOLVED 2026-07-24.**
- **Join-gated human games report `waiting_for_human`.** The accidental
  engine-book expectation of `started` has been restored to the canonical
  response and the focused regression passes. **Status: RESOLVED 2026-07-24.**
- Reverified focused fixes: hosted AI terminal summary, policy-host LOS,
  policy-host consumer parity, Hold Person successful-save concentration
  cleanup, typed Move revalidation, stale/published epoch handling, remembered
  living/dead entity projection, Dash modified speed, and the EB-10 forced
  movement iterator regression.

## Historical Issue Ledger

### Full-project Pyright exposes unrelated config-ladder and request-timing typing debt
- **Found**: 2026-07-24 while completing managed-AI composition and objective-journal validation; focused Pyright over the files changed for that work is clean.
- **Command**: `uv run pyright`; reproduced in isolation with `uv run pyright ai/evaluation/config_ladder/coordinator.py ai/evaluation/config_ladder/experiment.py ai/evaluation/config_ladder/match_runner.py ai/evaluation/config_ladder/strength_model.py server/request_timing.py`.
- **Result**: `19 errors, 0 warnings, 0 informations`: 3 in `coordinator.py`, 2 in `experiment.py`, 5 in `match_runner.py`, 7 in `strength_model.py`, and 2 in `server/request_timing.py`.
- **Error**: The connected config-ladder paths pass the broad `ScheduleEntry` union, which also permits `PromotionScheduleEntry`, into APIs and factories requiring `ConnectedScheduleEntry`; the strength model has unresolved SciPy/NumPy return-shape indexing plus general-`str` values passed to literal-typed model fields; and the request-timing ASGI response-header copy is inferred as `Never`, rejecting iteration and append.
- **Resolution**: Connected-only schedule boundaries now narrow the schedule
  union explicitly, strength-model array/scalar results and literal fields are
  normalized through typed values, and request-timing response headers retain
  their concrete ASGI list type.
- **Verification**: `uv run pyright` reports
  `0 errors, 0 warnings, 0 informations` across the complete repository on
  2026-07-29.
- **Status**: RESOLVED 2026-07-29.

### Codex takeover test patched an obsolete action-execution wrapper
- **Found**: 2026-07-23 during focused registered-agent service validation; unrelated to the launcher changes.
- **Reproduced**: 2026-07-24 during focused legacy-coverage restoration.
- **Test file**: `tests/manual/test_30_codex_takeover_tools.py::test_ai_command_advances_when_accepted_action_ends_actor_turn`
- **Command**: `uv run pytest -q tests/manual/test_30_codex_takeover_tools.py`
- **Original result**: `1 failed, 14 passed`.
- **Error**: The selector supplied a monkeypatched accepted `ActionResult` whose
  payload says the actor's turn ended, and expects the command response to
  report `turn_continues=False`; the observed response reports
  `turn_continues=True`.
- **Resolution**: The command route intentionally calls
  `_execute_action_by_index_impl`, because that authoritative boundary retains
  epoch execution binding and movement metadata. The test patched the obsolete
  public `execute_action_by_index` wrapper, so its fake result was never used.
  The test now patches the implementation boundary and returns an
  `_ActionExecutionResult` containing the intended turn-ending `ActionResult`.
- **Verification**: The exact selector passes `1/1`, and
  `tests/manual/test_30_codex_takeover_tools.py` passes `15/15`.
- **Status**: RESOLVED 2026-07-24; stale test seam corrected, with no production
  route change.

### AI-validation catalog test omits five SRD arenas
- **Found**: 2026-07-23 while running focused registered-agent service validation; unrelated to the launcher refactor.
- **Test file**: `tests/manual/test_38_ai_validation_server_start.py::test_ai_validation_arena_list_endpoint_exposes_catalog_metadata`
- **Command**: `uv run pytest tests/manual/test_38_ai_validation_server_start.py::test_ai_validation_arena_list_endpoint_exposes_catalog_metadata -q`
- **Error**: The exact arena-ID assertion fails because the live catalog contains five additional entries beyond the 33 IDs in the test fixture; the first extra entry is `srd_low_cr_patrol`.
- **Hypothesis**: The catalog was deliberately expanded with five SRD validation arenas, but this exact expected-ID list was not refreshed. The test expectation is stale rather than the endpoint or registered-agent service being incorrect.
- **Resolution**: The route regression now compares every serialized metadata
  row with `list_ai_validation_arena_specs()` instead of duplicating the
  catalog's ordered ID list. The catalog test remains the one owner of exact
  membership.
- **Verification**: `tests/manual/test_38_ai_validation_server_start.py`
  passes (`4 passed`).
- **Status**: RESOLVED 2026-07-24; stale test golden corrected.

### Public-manual audit metadata and source anchors have unrelated drift
- **Found**: 2026-07-23 while validating the canonical transport cutover in public manual Chapters 18, 23, and 25; the transport-owned targeted checks are green.
- **Test file**: `tests/book_examples/test_public_mdx_snippets.py`
- **Command**: `uv run pytest -q tests/book_examples/test_public_mdx_snippets.py -k 'not test_public_book_example_executes'`
- **Original result**: `5 failed, 102 passed, 144 deselected`.
- **Cause**: The broad structural audit also reported failures outside the
  transport chapters: the import-panel prose-audit roster omitted Chapters 24,
  26, and 27; Chapters 17 and 22 imported `LifeState` without a
  `dnd.core.life_types` source row; 91 source-link anchors had become blank or
  out of range; and all 21 extension/scenario helper anchors no longer landed
  on their named definitions.
- **Resolution**: Enrolled all three import-panel chapters, added the two
  dependency-neutral `LifeState` source rows, and refreshed the public manual's
  source anchors to the current authoritative definitions and route
  declarations. The audits were preserved unchanged.
- **Verification**: The four repairable selectors pass `4/4`. The complete
  non-executable structural selection now reports `1 failed, 106 passed, 144
  deselected`; the sole failure is
  `test_parity_matrix_tracks_public_webbook_examples`, because the canonical
  `engine_book/parity_matrix.md` source file does not exist.
- **Status**: RESOLVED 2026-07-24 for all repairable metadata drift. The one
  remaining selector is owned by **Engine-book source fixtures are absent**;
  the archived document was not restored or treated as authoritative.

### Architecture-surface audit tests reference a missing manual document
- **Found**: 2026-07-23 during focused subjective replay validation; unrelated to replay persistence or command-response cleanup.
- **Test file**: `tests/engine_book/test_architecture_surface_audit.py` (3 failures)
- **Command**: `uv run pytest tests/engine_book/test_architecture_surface_audit.py -q`
- **Error**: All three checks fail because `engine_book/architecture_surface_audit.md` is missing.
- **Hypothesis**: The architecture-surface chapter was moved or never added while its integrity tests retained the old path. Restore the intended document or update the tests to its canonical location in a dedicated documentation change.
- **Status**: SUPERSEDED 2026-07-24 by **Engine-book source fixtures are
  absent**, which is the canonical missing-source-tree issue.

### Hosted AI match does not reach terminal summary before timeout
- **Found**: 2026-07-23 while validating subjective replay persistence; reproduced twice and unrelated to the replay endpoints.
- **Test file**: `tests/manual/test_110_multi_game_gateway.py::test_ai_match_publishes_canonical_terminal_evidence_from_terminal_event`
- **Error**: After 30 seconds the AI encounter had not published `EncounterEnd`; the game-directory row remained active until worker shutdown, and the worker returned only `terminal_summary_not_ready`. The new subjective replay endpoints were therefore never reached by this failing path.
- **Hypothesis**: The hosted AI encounter or controller loop was failing to reach its terminal event within the test deadline.
- **Verification**: Re-run on 2026-07-24:
  `tests/manual/test_110_multi_game_gateway.py::test_ai_match_publishes_canonical_terminal_evidence_from_terminal_event`
  passes.
- **Status**: RESOLVED 2026-07-24; retained as historical timeout evidence.

### Invalid-player session error supplies duplicate player-type context
- **Found**: 2026-07-23 during focused world DTO split validation; unrelated to the DTO changes.
- **Test file**: `tests/engine/test_encounter_apis.py::test_eb_18_013_session_and_game_errors_report_valid_sessions_and_entities`
- **Command**: `uv run pytest tests/engine/test_encounter_apis.py::test_eb_18_013_session_and_game_errors_report_valid_sessions_and_entities -q`
- **Error**: The invalid-player request reaches `_session_http_exception()`, which raises `TypeError: server.event_server._api_http_exception() got multiple values for keyword argument 'valid_player_types'` instead of returning the expected structured 400 response.
- **Cause**: `_session_context()` already supplied `valid_player_types`, while
  `create_session()` passed the same key explicitly for its invalid-player
  branch; expanding both dictionaries into `_api_http_exception()` duplicated
  the keyword.
- **Resolution**: `_session_http_exception()` now merges shared session context
  with call-site context before forwarding it, and the redundant explicit
  player-type argument was removed.
- **Verification**: The structured invalid-player regression and the complete
  Chapter 18 API file pass.
- **Status**: RESOLVED 2026-07-23

### Gauntlet watcher fixtures are classified as subjectivity violations
- **Found**: 2026-07-22 during focused AI/server ownership-migration validation; reproduced unchanged from a clean `HEAD` archive.
- **Test file**: `tests/manual/test_55_gauntlet_live_watcher_server.py::test_runner_can_publish_directly_to_server_live_stream` and `::test_runner_emits_match_failed_for_stale_completed_match`
- **Error**: Both synthetic `ExternalSelfPlayTrace` fixtures are classified as `subjectivity_violation`; the first therefore emits `MATCH_FAILED` instead of `MATCH_COMPLETED`, and the second reports `subjectivity_violation` instead of its expected `stale_command` reason.
- **Evidence**: The migrated gauntlet contract is byte-identical to `HEAD`; running these exact nodes from a clean `git archive HEAD` reproduces both failures.
- **Hypothesis**: The retained fake traces no longer satisfy the complete subjectivity witness contract. Refresh the fixtures with the required subjective evidence so each test reaches the gauntlet status branch it intends to cover.
- **Cause**: Each fixture disclosed the controlled actor in
  `subjective_known_entity_uuids` but omitted the independent evaluator witness
  from `audit_controlled_entity_uuids` and
  `audit_authorized_entity_uuids`, so the disclosure audit correctly rejected
  the actor UUID as unauthorized.
- **Resolution**: Both synthetic traces now carry the complete empty/controlled
  subjective witness, including visible and seen cells, controlled and
  authorized entity IDs, authorized object IDs, and authorized positions.
  The completed fixture now reaches `MATCH_COMPLETED`, while the stale fixture
  reaches its intended `stale_command` branch.
- **Verification**: Both exact selectors pass (`2 passed`), and
  `tests/manual/test_55_gauntlet_live_watcher_server.py` passes (`10 passed`).
- **Status**: RESOLVED 2026-07-24

### Subjective epoch tests subscript a typed available-actions response
- **Found**: 2026-07-22 during focused AI/server ownership-migration validation; confirmed pre-existing from the HEAD sources.
- **Test file**: `tests/manual/test_31_subjective_runtime_epochs.py::test_spell_epoch_rows_expose_full_spell_slot_costs` and `::test_concentration_requirement_reaches_typed_epoch_and_human_api`
- **Command**: `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py::test_spell_epoch_rows_expose_full_spell_slot_costs tests/manual/test_31_subjective_runtime_epochs.py::test_concentration_requirement_reaches_typed_epoch_and_human_api -q`
- **Error**: Both tests use `serialized["entity_actions"]`, but `serialize_available_actions()` returns `APIAvailableActions`, so Pydantic raises `TypeError: 'APIAvailableActions' object is not subscriptable`.
- **Evidence**: HEAD already contains both dictionary-style test accesses, while HEAD's `server/action_serialization.py` annotates and returns `APIAvailableActions`; the ownership migration did not change either contract.
- **Hypothesis**: The tests retained the former dictionary access style after the serializer became typed. They should either inspect typed attributes or call `model_dump(mode="json")` when explicitly validating the human wire representation.
- **Resolution**: The tests now use the typed response boundary.
- **Verification**:
  `test_spell_epoch_rows_expose_full_spell_slot_costs` and
  `test_concentration_requirement_reaches_typed_epoch_and_human_api` pass.
- **Status**: RESOLVED 2026-07-24.

### Policy contracts retain three unused typing imports
- **Found**: 2026-07-25 while validating the environment-content hard cut.
- **Automated reproducer**: `uv run pyright ai/policy/contracts.py`.
- **Expected diagnostic**: Pyright reports exactly three
  `reportUnusedImport` errors: `Union` on line 6, `EndTurnIntent` on line 26,
  and `ExecuteIntent` on line 27.
- **Hypothesis**: The policy intent contract was narrowed to `PolicyIntent`,
  leaving the prior union members and `typing.Union` import behind.
- **Resolution**: Removed only the three unused imports; the live contract
  continues to import and use `PolicyIntent`.
- **Verification**: `uv run pyright ai/policy/contracts.py` reports
  `0 errors, 0 warnings, 0 informations`.
- **Status**: RESOLVED 2026-07-25.

### Combined affordance rows do not support sequence-value equality
- **Found**: 2026-07-22 during focused AI/server ownership-migration validation; confirmed pre-existing from the HEAD sources.
- **Test file**: `tests/manual/test_40_unified_agent_protocol.py::test_control_protocol_embeds_in_subjective_event_envelopes`
- **Command**: `uv run pytest tests/manual/test_40_unified_agent_protocol.py::test_control_protocol_embeds_in_subjective_event_envelopes -q`
- **Error**: `AffordanceSet.all_rows == (affordance,)` is false because `all_rows` is a `CombinedActionRows` sequence with identity-based equality rather than tuple-like value equality.
- **Evidence**: HEAD already contains the same assertion in `tests/manual/test_40_unified_agent_protocol.py` and the canonical `ai/protocol/control.py::CombinedActionRows` has `__len__`, `__getitem__`, and `__iter__` but no `__eq__`; the ownership migration only relocated that implementation.
- **Hypothesis**: `CombinedActionRows` omitted the sequence-compatible equality implemented by `ActionBucketRows`; either give the combined view the same value-equality contract or make the test explicitly materialize it before comparing.
- **Cause**: `CombinedActionRows` is the public sequence view returned by
  `AffordanceSet.all_rows`, but unlike the established `ActionBucketRows`
  sequence contract it inherited identity equality from `object`.
- **Resolution**: `CombinedActionRows` now compares its canonical buckets to
  another combined view and materialized values to any other `Sequence`. The
  protocol fixture also constructs the canonical factored
  `ActionSourceDefinition` shape so the same contract is visible to Pyright.
- **Verification**: The exact selector passes, the full protocol file passes
  (`3 passed`), and the focused Pyright run reports `0 errors`.
- **Status**: RESOLVED 2026-07-24

### Stacked healing potion test attempts two bonus-action uses in one turn
- **Found**: 2026-07-21 during focused wardrobe validation; reconfirmed 2026-07-22 during dependency-neutral type extraction and the item-location fact refactor, unrelated to all three changes.
- **Test file**: `tests/engine/test_items_inventory_equipment.py::test_eb_13_008_consumable_use_actions_consume_charges_and_stacks`
- **Command**: `uv run pytest tests/engine/test_items_inventory_equipment.py -q` (`21 passed, 1 failed`).
- **Error**: The first use heals HP from 1 to 8, decrements the stack from 2 to 1, restores the surviving potion's charge, and keeps it registered. The immediate second `execute_use_action()` call returns `None`, while the test expects another non-canceled event.
- **Evidence**: `PotionDrinkAction` has a one-bonus-action cost in both the current tree and `HEAD`; the item-location work did not introduce this cost or alter the failing action-economy path.
- **Hypothesis**: The test expectation is outdated, not evidence of lost stack discoverability. The entity starts with one bonus action, the first completed potion use consumes it, and `BaseAction._apply_action()` returns `None` when the immediate second use fails `check_costs()`. The test must either begin a new turn/recharge the bonus action before checking final-stack consumption or explicitly configure enough bonus actions if two same-turn drinks are the intended contract.
- **Resolution**: The fixture now begins a second legal turn before the final
  stack use and asserts both bonus-action expenditures plus exact stack,
  charge, registry, inventory, and healing transitions.
- **Verification**: `test_eb_13_008_consumable_use_actions_consume_charges_and_stacks`
  passes in the focused item suite.
- **Status**: RESOLVED 2026-07-24

### Quickened Spell fixture exhausts mocked d20 rolls under disadvantage
- **Found**: 2026-07-21 during focused wardrobe validation; reproduced
  independently on 2026-07-24 while restoring active Sorcerer factory
  coverage.
- **Test file**: `tests/engine_book/test_manual_18_class_features_feats_factories.py::test_quickened_spell_uses_feature_resource_to_override_spell_template_until_cast`
- **Command**: `uv run pytest tests/engine_book/test_manual_18_class_features_feats_factories.py::test_quickened_spell_uses_feature_resource_to_override_spell_template_until_cast -q --tb=short`
- **Error**: The test raises `StopIteration` because the disadvantaged spell attack consumes two d20 values while the fixture provides only one mocked value.
- **Hypothesis**: The test's deterministic dice fixture predates the current disadvantage-aware roll consumption and needs to provide both d20 results without changing the Quickened Spell assertions.
- **Scope evidence**: The adjacent hostile target imposes disadvantage, while
  `fixed_class_randint(d20_values=[12])` contains one value. The restored
  Sorcerer regression file uses the correct spell-attack channel and passes;
  no production source was changed for this fixture failure.
- **Resolution**: The deterministic fixture now supplies `[12, 11]` and
  explicitly asserts that both disadvantaged d20 faces are retained on the
  spell event. No production behavior changed.
- **Verification**: The exact selector passes, the full class-feature file
  passes (`6 passed`), and the focused Pyright run reports `0 errors`.
- **Status**: RESOLVED 2026-07-24

### Caster potion action-cost expectation disagrees with current bonus-action cost
- **Found**: 2026-07-21 during focused wardrobe validation; unrelated to the wardrobe changes.
- **Test file**: `tests/engine/test_monster_presets.py::test_eb_17_011_create_caster_inventory_potions_are_item_use_actions`
- **Error**: The caster's potion use action exposes a bonus-action entry in `effective_costs`, while the test expects an empty list.
- **Hypothesis**: The test expectation is stale relative to the current potion action-economy contract, or the potion factory and monster-preset fixture disagree about the intended use cost.
- **Cause**: Both preset potions derive from `PotionDrinkAction`, whose
  canonical cost is one bonus action; the former empty-cost expectation was a
  stale fixture, not a production bypass.
- **Resolution**: EB17-011 asserts the exact cost for both potions, then proves
  behavior: Greater Invisibility consumes the bonus action and its item,
  applies `Invisible`, preserves the normal action, and an immediate Haste
  attempt fails without consuming the Haste potion or applying `Haste`.
- **Verification**: The exact selector passes and the complete Chapter 17 file
  passes (`12 passed`).
- **Status**: RESOLVED 2026-07-24

### Battlefield deployment neutral schedule has stale catalog cardinality expectations
- **Found**: 2026-07-20 during focused test validation; unrelated to the change under test.
- **Test file**: `tests/manual/test_72_battlefield_deployment_catalog.py::test_one_seed_neutral_schedule_has_all_9180_matches_and_zero_exclusions`
- **Error**: The test expects 9,180 schedule entries from a hardcoded set of 15 hero configurations, but the current canonical roster produces 13,680 entries after configuration expansion.
- **Hypothesis**: The assertion and count expectations are stale. They should derive from the current eligible catalog cardinalities instead of hardcoding the former 15-configuration total.
- **Cause**: The eligible catalogs now contain 20 hero configurations and 38
  monster-party configurations across 9 portable neutral
  battlefield/deployment contexts. Paired hero-first and monster-first
  treatments therefore produce 13,680 rows; the literal encoded an older
  15-by-34 catalog.
- **Resolution**: The renamed regression derives the exact eligible catalog
  identity cells, compares them to the schedule's full identity set, requires
  both opening treatments for every cell, and verifies identity-keyed hero and
  monster frequencies. Its only total is derived from those identities.
- **Verification**: The exact selector passes and the complete battlefield
  catalog file passes (`7 passed`).
- **Status**: RESOLVED 2026-07-24

### Sessions API client contract has stale exact cursor readouts
- **Found**: 2026-07-19 during focused regression validation; unrelated to the change under test.
- **Test file**: `tests/manual/test_18_sessions_api_client_contract.py` (2 failures)
- **Command**: `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q`
- **Failing tests**: `test_execute_action_by_index_returns_state_logs_and_cursors` and `test_event_and_combat_log_history_are_cursor_addressed`.
- **Actual vs expected**: Both tests hard-code event cursor/count `78`, while the current deterministic action and history responses consistently produce `72`.
- **Preserved semantics**: The event cursor equals the serialized event-history length, the API and queue cursors agree, all cursor-addressed history assertions pass, the expected 19 completion events remain present, and the combat logs and their cursor assertions pass. Only the exact golden cursor readouts fail.
- **Hypothesis**: The expected value `78` is a stale golden count after event-emission lifecycle changes, not evidence of an inconsistent session or history contract. Preserve the semantic history, completion, log, and cursor-equality assertions when refreshing the readout.
- **Resolution**: Refreshed the two tutorial readouts to the canonical 72-event lifecycle while preserving every route/queue equality, completion-count, combat-log, and cursor-order assertion.
- **Status**: RESOLVED 2026-07-20

### Spell catalog reports Fire Bolt as not using an attack roll
- **Found**: 2026-07-19 during focused regression validation; separate from the stale session cursor readouts.
- **Test file**: `tests/manual/test_18_sessions_api_client_contract.py::test_spell_catalog_route_exposes_design_time_spell_metadata`
- **Error**: The test expects `fire_bolt.attack_roll` to be `true`, while the current spell-catalog response reports `false`.
- **Cause**: The catalog projector recognized obsolete direct attack helpers but not the shared `SpellAction.resolve_spell_attack()` primitive used by Fire Bolt and the current spell-attack implementations.
- **Resolution**: The backend catalog now recognizes the shared spell-attack resolver. No NeuroClient override or duplicate spell metadata was added.
- **Verification**: `test_spell_catalog_route_exposes_design_time_spell_metadata` passes, focused Pyright is clean, and the restarted live route reports Fire Bolt with `attack_roll: true`, range 120, and entity targeting.
- **Status**: RESOLVED 2026-07-20

### Chapter 12 Fireball visibility test observes an unexpected level-3 slot count
- **Found**: 2026-07-16 while running an over-broad Chapter 12 light/senses regression selection during AI movement visibility optimization; unrelated to the bright-light fast path under test.
- **Test file**: `tests/engine/test_senses_light_stealth.py::test_eb_12_018_aoe_preview_hides_hidden_entities_but_execution_hits_them`
- **Command**: `uv run pytest tests/engine/test_senses_light_stealth.py -q -k "darkvision or magical or light or self_movement_updates_visibility or visibility_cache"`
- **Error**: The action resolves correctly, both hidden and visible targets take Fireball damage, and Hidden is removed, but the test expects `caster.action_economy.spell_slot_3.normalized_score == 2`; the current result is `1`.
- **Cause**: The level-5 caster starts with two level-3 slots and the valid
  Fireball cast correctly consumes one. The post-cast result of `1` is
  canonical; the expected value of `2` is stale.
- **Resolution**: The maintained test now asserts the two-slot precondition,
  one completed cast lifecycle, and the canonical one-slot postcondition while
  preserving its hidden-preview, objective-hit, and Hidden-removal assertions.
- **Verification**: The exact selector and complete Chapter 12 focused file
  pass.
- **Status**: RESOLVED 2026-07-24

### Policy-host LOS test stub rejects the production workspace keyword
- **Found**: 2026-07-15 during focused validation of the turn-duration augmentation change; pre-existing and unrelated to that change.
- **Test file**: `tests/manual/test_48_policy_host.py::test_enable_then_act_reuses_los_for_equivalent_subjective_geometry`
- **Command**: `uv run pytest tests/manual/test_48_policy_host.py -q` (`49 passed, 1 failed`)
- **Error**: The test-local `counted_line_of_sight` monkeypatch does not accept the `workspace=` keyword now passed by `ai/policy/routines.py::_route_costs_to_capability_envelope`, so the test fails with `TypeError`.
- **Scope**: Production behavior is unaffected; the failure occurs only in the stale monkeypatched test double.
- **Resolution**: The focused test stub now accepts and forwards the production
  `workspace` keyword.
- **Verification**:
  `tests/manual/test_48_policy_host.py::test_enable_then_act_reuses_los_for_equivalent_subjective_geometry`
  passes on 2026-07-24.
- **Status**: RESOLVED 2026-07-24.

### Hypnotic Pattern cannot be ended with Shake Awake
- **Found**: 2026-07-16 during a read-only audit of break-on-damage control effects.
- **Source**: `dnd/spells/illusion.py` says another creature can use an action to shake a Hypnotic Pattern target out of its stupor, but `dnd/actions.py::ShakeAwake` recognizes and removes only `Sleep` and `Eyebite Asleep`.
- **Impact**: Hypnotic Pattern correctly ends on positive post-mitigation damage, but the documented adjacent-creature wake-up path is unavailable through the existing Shake Awake action.
- **Hypothesis**: The Shake Awake target validation and removal branches have not been extended to the `Hypnotic Pattern` condition.
- **Resolution**: Shake Awake discovers removable effects through
  `ConditionRemovalTrigger.SHAKE_AWAKE`; Sleep, Eyebite Asleep, and Hypnotic
  Pattern declare that dependency-neutral capability.
- **Verification**:
  `tests/manual/test_140_shake_awake_trigger.py::test_shake_awake_uses_typed_removal_capability_for_every_supported_effect`
  passes.
- **Status**: RESOLVED 2026-07-24.

### Codex takeover turn-advance test patches an unused command symbol
- **Found**: 2026-07-16 during focused validation of the control-preservation change; unrelated to that change.
- **Reverified**: 2026-07-22 with `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q` (`14 passed, 1 failed`).
- **Test file**: `tests/manual/test_30_codex_takeover_tools.py::test_ai_command_advances_when_accepted_action_ends_actor_turn`
- **Error**: The test monkeypatches `server.event_server.execute_action_by_index`, but the command route no longer calls that symbol. The real movement therefore executes, and `payload.turn_continues` remains `True` instead of matching the mocked turn-ending result.
- **Hypothesis**: The test mock is stale and must patch the command route's current execution boundary rather than the obsolete imported symbol.
- **Status**: SUPERSEDED 2026-07-24 by the resolved **Codex takeover test
  patched an obsolete action-execution wrapper** entry; both headings describe
  the same selector.

### AI runtime performance suite has stale cache, policy, and retained-fixture expectations
- **Found**: 2026-07-22 during full-file validation of the AI/server ownership migration.
- **Test file**: `tests/manual/test_43_ai_runtime_performance.py`
- **Command**: `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q` (`50 passed, 13 failed`).
- **Final disposition**: Twelve failures were stale test contracts and one was
  a real current-generation performance regression. The three cache tests now
  establish an explicit cold state or a monotonic lookup ceiling; the four
  retained loaders run the canonical snapshot/frame semantic migration before
  immutably refreshing content addresses; and five policy goldens now assert
  typed damage, setup, movement, line-of-sight, and bounded-work outcomes
  instead of whole-model hashes or incidental row labels.
- **Production cause and repair**: Current-generation tactical rescoring maps
  the retained Haste setup to `64.5`, below the frozen v31 dominance threshold
  of `110`, so the inherited shortcut no longer recognized it and evaluated
  242 movement endpoints, 1,240 affordability pairs, and 1,120 line-of-sight
  checks before selecting the same setup. The current policy now recognizes
  only typed durable setups that grant extra actions and score at least `61.0`.
  That floor is derived from the fixed pursuit starter score `65.0` minus the
  existing position-then-pressure margin `4.0`, rather than being a refreshed
  golden.
- **Retained v194 evidence**: Current candidates score Haste `64.5`, Greater
  Invisibility `51.25`, and Dodge `-2.1625`. Without the shortcut, the explicit
  enable plan scores `48.36597975000001` and pursuit scores `65.0`; Haste is
  within the established four-point improvement margin and grants future
  action economy, so starter planning cannot justify its cost. With the repair,
  Haste is selected and all routine-work counters are zero.
- **Performance assertions**: Fresh-host decision timers instantiate the host
  outside the measured interval. The dense v222 contract retains a sub-5 ms
  median and a bounded sub-6 ms p99 under the sustained full-file run; the
  stricter v216 sub-5 ms p99 contract remains unchanged.
- **Verification**:
  - Repaired selector group: `13 passed, 50 deselected`.
  - Complete file: `63 passed, 1 warning in 50.49s`.
  - `uv run pyright ai/policy/generations/current_candidate.py tests/manual/test_43_ai_runtime_performance.py`:
    `0 errors, 0 warnings, 0 informations`.
- **Status**: RESOLVED 2026-07-24

### Reckless interposition performance fixture has a stale semantic reference
- **Found**: 2026-07-15 during focused validation of Reckless interposition; unrelated stale fixture failure.
- **Test file**: `tests/manual/test_43_ai_runtime_performance.py::test_reckless_augmentation_interposes_before_retained_move_attack_goal`
- **Error**: The test fails before policy evaluation while `_load_reckless_bridge_world_at_cursor` loads its retained fixture. The fixture expects semantic reference `setup.reckless_attack@v1:8e695d3ea70ac98c`, but the current computed reference is `setup.reckless_attack@v1:c11f9113b045a880`.
- **Hypothesis**: `_load_reckless_bridge_world_at_cursor` does not apply the repository's existing legacy semantic migration helper. Apply that helper at this retained-fixture loading boundary or refresh the fixture through the canonical migration path.
- **Preserved behavior**: The live exact-seed `caster_crossfire` replay now proves that Reckless augmentation interposes before the retained move-attack goal.
- **Status**: SUPERSEDED 2026-07-24 by **AI runtime performance suite has stale
  cache, policy, and retained-fixture expectations**, which includes this same
  retained fixture.

### Subjective observation stream test leaves unpacked encounter unused
- **Found**: 2026-07-15 during focused type checking; unrelated and pre-existing.
- **Test file**: `tests/manual/test_28_subjective_observation_stream.py`
- **Command**: `uv run pyright tests/manual/test_28_subjective_observation_stream.py`
- **Error**: `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/manual/test_28_subjective_observation_stream.py:1165:40 - error: Variable "encounter" is not accessed (reportUnusedVariable)`
- **Hypothesis**: A tuple result from `create_observation_game()` is unpacked, but the `encounter` value is unused in this test.
- **Resolution**: Removed the stale unused fixture binding while migrating the
  file to the canonical identity-bound player replication routes.
- **Verification**: All 48 tests in the file pass and scoped Pyright reports
  zero errors.
- **Status**: RESOLVED 2026-07-23

### Live replication tutorial has stale exact event-count readouts
- **Found**: 2026-07-15 during focused regression validation of the seamless subjective runtime; reconfirmed 2026-07-20 as unrelated to the current SDK work.
- **Test file**: `tests/manual/test_25_live_replication_streams.py` (3 failures)
- **Command**: `uv run pytest -q tests/manual/test_25_live_replication_streams.py::test_cursor_replay_returns_events_and_logs_after_saved_cursors tests/manual/test_25_live_replication_streams.py::test_live_subscription_fans_out_game_events_and_combat_logs tests/manual/test_25_live_replication_streams.py::test_combat_log_frames_follow_completion_events_in_the_queue`
- **Failing tests**: `test_cursor_replay_returns_events_and_logs_after_saved_cursors`, `test_live_subscription_fans_out_game_events_and_combat_logs`, and `test_combat_log_frames_follow_completion_events_in_the_queue`.
- **Actual vs expected**: `test_cursor_replay_returns_events_and_logs_after_saved_cursors` expects 26 game events, 6 completions, and final cursor 68, but receives 30 game events, 7 completions, and final cursor 72. `test_live_subscription_fans_out_game_events_and_combat_logs` expects 27 total envelopes / 26 game events and latest stream id `e=68;l=2`, but receives 31 total envelopes / 30 game events and `e=72;l=2`. `test_combat_log_frames_follow_completion_events_in_the_queue` expects the first combat log at index 26 after completion index 25 with 6 prior completions, but receives it at index 30 after completion index 29 with 7 prior completions.
- **Preserved semantics**: Cursor replay starts at the saved cursor, every event cursor equals its event index plus one, the latest event cursor matches `EventQueue`, stream ids match their cursor pairs, the latest game event is a completion, and the combat-log envelope remains strictly ordered after the final completion. Only the exact golden readout assertions fail.
- **Cause**: The canonical attack lifecycle now includes all four phases of the factual `DamageAppliedEvent`. Its completion accounts for the seventh completion, and the complete lifecycle moves the final cursor from 68 to 72.
- **Resolution**: Refreshed the tutorial readouts while retaining the semantic replay, cursor continuity, stream-id, completion ordering, and combat-log ordering assertions.
- **Status**: RESOLVED 2026-07-20

### Resolved: Spell-family manual test had stale Pyright annotations and optional narrowing
- **Found**: 2026-07-15 during focused type checking of entity and spell-family changes; unrelated and pre-existing relative to that work.
- **Test file**: `tests/manual/test_14_spell_families.py`
- **Command**: `uv run pyright dnd/entity.py dnd/spells/abjuration.py dnd/spells/illusion.py tests/manual/test_14_spell_families.py`
- **Current result**: A focused 2026-07-24 run reports `11` errors. The
  original general-`str` saving-throw argument and optional event/entity
  accesses remain, and later edits added further optional-member diagnostics.
- **Hypothesis**: These are stale test typing issues rather than production spell failures. The helper parameter should use `AbilityName`, and the readout paths should explicitly narrow the completed event fields and entity lookup before member access.
- **Resolution**: The test helpers now use the exact ability enum and explicitly
  narrow optional event fields and entity lookups before accessing typed
  members.
- **Verification**: `tests/manual/test_14_spell_families.py` passes all 14
  runtime tests, and focused Pyright over the maintained manual typing-debt
  set reports zero errors.
- **Status**: RESOLVED 2026-07-29.

### Local read-model test double does not satisfy the subjective runtime protocol
- **Found**: 2026-07-14 during focused type checking of the local read-model tests.
- **Test file**: `tests/manual/test_50_codex_local_read_model.py` (2 pyright errors at lines 29 and 63; both runtime tests pass)
- **Command**: `uv run pyright ... tests/manual/test_50_codex_local_read_model.py`
- **Error**: `_ArtifactRuntime` is passed to `HotCodexRuntime` but does not satisfy `SubjectiveRuntimeLike`; it is missing `wait_for_epoch`, `execute`, and `end_turn`.
- **Hypothesis**: This is an incomplete test double/type-check issue, not a production runtime failure. Make the fake explicitly implement the complete protocol with unreachable or stub command methods, or narrow the constructor dependency for read-only tests without weakening the production protocol.
- **Resolution**: The read-only fake now implements every runtime protocol method with explicit unreachable command stubs, uses the typed policy telemetry contract, and no longer exposes the deleted `materialized` state alias.
- **Status**: RESOLVED 2026-07-14; the focused test file passes all 3 tests and focused Pyright is clean.

### SRD rule mapping references a missing interactive-ruleset index
- **Found**: 2026-07-14 during focused `uv run pytest tests/engine_book/test_srd_rule_mapping.py -q`; unrelated and pre-existing relative to the AI legacy removal.
- **Test file**: `tests/engine_book/test_srd_rule_mapping.py::test_srd_rule_mapping_sources_exist_and_have_relationship_labels`
- **Error**: The historical failure referenced a missing
  `interactive_ruleset/README.md`; the current focused run fails earlier
  because `engine_book/srd_rule_mapping.md` itself is absent.
- **Status**: SUPERSEDED 2026-07-24 by **Engine-book source fixtures are
  absent**. The removed interactive-ruleset source remains historical context,
  but cannot be audited until the canonical mapping document exists.

### Subjective action query return type disagrees with its annotation
- **Found**: 2026-07-14 during the legacy AI cleanup focused type check; unrelated and pre-existing relative to the deleted legacy stack.
- **Command**: `uv run pyright ai dnd/controller.py dnd/scenarios/controller_catalogue.py dnd/scenarios/__init__.py tests/manual/test_24_built_in_controllers.py`
- **Error**: `ai/subjective/queries.py:32:16` returns `Tuple[ActionAffordance, ...]`, but its annotation promises `list[ActionAffordance]` (`reportReturnType`).
- **Hypothesis**: The return annotation should express an immutable tuple or `Sequence`, or the implementation should deliberately materialize a list, according to the intended query API contract.
- **Resolution**: The migrated query now preserves its public immutable tuple contract by materializing `tuple(current_epoch.affordances.all_rows)` from the neutral server protocol's `Sequence` view.
- **Status**: RESOLVED 2026-07-22; focused Pyright is clean.

### Engine-book integrity is missing five parity rows
- **Found**: 2026-07-14 while running focused validation during legacy AI cleanup; appears unrelated and pre-existing relative to that cleanup.
- **Test file**: `tests/architecture/test_source_model_hygiene.py`
- **Error**: The integrity checks report missing parity rows for `EB-11-022`, `EB-11-023`, `EB-12-020`, `EB-12-021`, and `EB-12-022`.
- **Hypothesis**: New or renumbered Chapter 11 and 12 examples were not added to the engine-book parity metadata.
- **Status**: SUPERSEDED 2026-07-24 by **Engine-book source fixtures are
  absent**; the parity matrix that would own these rows is missing.

### Engine-book Chapter 11 and 12 outline ranges are stale
- **Found**: 2026-07-14 while running focused validation during legacy AI cleanup; appears unrelated and pre-existing relative to that cleanup.
- **Test file**: `tests/architecture/test_source_model_hygiene.py`
- **Error**: Chapter 11 is expected to extend through `023` but the outline ends at `021`; Chapter 12 is expected to extend through `022` but the outline ends at `019`.
- **Hypothesis**: The chapter outline ranges were not updated when later examples were introduced.
- **Status**: SUPERSEDED 2026-07-24 by **Engine-book source fixtures are
  absent**; the outline source is missing.

### Engine-book integrity expects a missing timing middleware symbol
- **Found**: 2026-07-14 while running focused validation during legacy AI cleanup; appears unrelated and pre-existing relative to that cleanup.
- **Test file**: `tests/architecture/test_source_model_hygiene.py`
- **Error**: The integrity check expects a top-level `server.event_server.timing_middleware`, but that symbol is absent.
- **Resolution**: The current integrity inventory no longer requires the
  obsolete top-level symbol.
- **Status**: RESOLVED 2026-07-24; retained as historical metadata drift.

### advance_encounter lacks the required Google-style Args block
- **Found**: 2026-07-14 while running focused validation during legacy AI cleanup; appears unrelated and pre-existing relative to that cleanup.
- **Test file**: `tests/architecture/test_source_model_hygiene.py`
- **Error**: The docstring integrity check reports that `advance_encounter` has parameters but no Google-style `Args:` block.
- **Resolution**: `advance_encounter` now contains the required Google-style
  `Args:` block.
- **Status**: RESOLVED 2026-07-24.

### Seeded external self-play is not replay-stable across fresh UUID allocations
- **Found**: 2026-07-14 comparing `ai/evidence/runs/20260714-v133-spacing-sensory-validation.json` with `ai/evidence/runs/20260714-v134-nonoverlapping-timing-validation.json`, then reproducing with two fresh processes running `run_external_selfplay("skeleton_anti_aoe_split", random_seed=2026071406, hero_first=True)`.
- **Test file**: Add a UUID-renaming regression to `tests/manual/test_44_typed_agent_policy.py` and a normalized cross-subprocess replay check to `tests/manual/test_39_ai_validation_harness.py`.
- **Error**: Both artifacts have the same seed and policy hash, but v133 ends after 26 commands with final monster HP `-2/-3/-5`, while v134 ends after 20 with `-4/-1/0`. At command 9 both rank 41 proposals and select score `180.012`; v133 selects Warlock UUID `1b29...` and v134 selects Warrior UUID `6e57...`, respectively the lexicographically smallest monster UUID in each process. Fresh reproduction also selected different command-9 primaries and ended in 30 versus 26 commands.
- **Hypothesis**: `ai.external_selfplay.run_external_selfplay()` seeds only Python `random`, while arena actor IDs come from unseeded `uuid4()` calls. `ai/policy/candidates.py::_additional_targets()` and `_optimize_repeat_allocation()` sort UUID sets and break equal allocations by UUID, and `ai/policy/utility.py::UtilityArbiter._sort_key()` breaks equal proposal scores by a `row_id` containing the target UUID. The relevant sets are sorted, so raw hash iteration is not the observed cause; the unstable UUID sort key is. `dnd/spells/evocation.py::ScorchingRay.get_all_targets()` puts the UUID-selected primary first, then `dnd/core/base_actions.py::BaseAction.apply()` resolves that list sequentially, assigning the same seeded attack/damage stream to different creatures and cascading into different outcomes.
- **Recommendation**: Build two equivalent typed-policy contexts whose actor names, positions, HP, actions, and outcome profiles match but whose opaque UUID labels are permuted; assert identical target names, allocation order, and selected intent after UUID normalization. Also launch the arena twice via separate subprocesses and compare normalized semantic traces, command counts, and final HP. Replace UUID fallbacks in policy/allocation ordering with a stable semantic replay key before expecting the subprocess test to pass.
- **Resolution**: Added identity-independent semantic replay keys to production policy proposals and utility arbitration. Multi-target damage/control allocation, execution ordering, outcome evidence, spacing/contact selection, and bounded routines now order equal choices through disclosed action semantics plus known target/object positions and normalized names. Opaque `row_id` remains only as a compatibility fallback for custom proposals without a semantic replay key.
- **Verification**: `tests/manual/test_44_typed_agent_policy.py::test_equal_multi_target_choices_are_invariant_to_opaque_uuid_labels` permutes target UUIDs and preserves primary position and projectile allocation. `tests/manual/test_39_ai_validation_harness.py::test_external_selfplay_seed_replays_across_fresh_processes` launches fresh interpreters with different `PYTHONHASHSEED` values, confirms disjoint actor UUIDs and an equal composite policy hash, then reproduces the complete normalized split-skeleton trace and final HP. Full focused files pass: `40 passed` in test 44, `16 passed` in test 48, and `17 passed` in test 39.
- **Status**: RESOLVED

### Resolved: Combat tutorial test file had stale Pyright narrowing errors
- **Found**: 2026-07-04 while validating the prone auto-stand regression added during AI zone-control iteration.
- **Test file**: `tests/manual/test_10_combat_resolution.py`
- **Error**: `uv run pyright ai/external/state.py ai/external/policy.py dnd/actions_functional.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_10_combat_resolution.py` reports pre-existing typing issues in the combat tutorial file: an unused `DamageType` import, optional subscripts/member access, and generic `Event` values that are not narrowed before reading `contest_success` / `push_distance`.
- **Hypothesis**: Runtime tests pass, but the tutorial test file predates stricter pyright narrowing for concrete event subclasses. The issue is local to test typing, not the prone auto-stand behavior.
- **Resolution**: The tutorial now narrows concrete contest/forced-movement
  events and optional payloads before member access and no longer retains the
  unused damage-type import.
- **Verification**: `tests/manual/test_10_combat_resolution.py` passes all 7
  runtime tests, and focused Pyright over the maintained manual typing-debt
  set reports zero errors.
- **Status**: RESOLVED 2026-07-29.

### Hold Person initial save may leave caster concentrating with no held target
- **Found**: 2026-07-04 during `condition_lock_sanctum` external self-play while adding control outcome telemetry.
- **Test file**: Not isolated yet. Observed in `ai.external_selfplay.run_external_selfplay("condition_lock_sanctum")`.
- **Error**: One accepted `Hold Person__slot_2` command returned the message `Hold Person - target saved (still concentrating)`. If the initial save succeeds and no target is held, the expected rules-facing behavior is likely that the spell effect ends rather than leaving the caster concentrating.
- **Resolution**: The successful-initial-save path now cleans up concentration
  when no target received the held effect.
- **Verification**: The focused successful-save concentration-cleanup
  regression passes on 2026-07-24.
- **Status**: RESOLVED 2026-07-24.

### Free powerful consumable rows distort challenge measurements
- **Found**: 2026-07-04 across Barbarian, Sorcerer, skeleton, and hazard validation rotations.
- **Test file**: Not isolated as a failing rule test. Observed in external self-play batches including `buff_consumable_ambush`, `skeleton_mark_focus_fire`, `multi_projectile_no_aoe_lab`, and `forced_movement_hazard_bridge`.
- **Error**: Haste, Greater Invisibility, and healing potion rows can appear as free or low-friction item-use options. The policy can use them sensibly, but they strongly distort encounter difficulty and make challenge measurements hard to compare across arenas.
- **Current finding**: Potion use actions now have an explicit bonus-action
  cost, so the report that these rows are mechanically free is stale. Whether
  their availability still distorts arena calibration is a separate balance
  decision, not a demonstrated action-economy defect.
- **Status**: STALE AS WRITTEN 2026-07-24; open a new balance issue only with
  fresh challenge evidence.

### AI epoch Move row can be rejected by execute-by-index as failed movement
- **Found**: 2026-07-04 during `buff_consumable_ambush` external self-play after adding opening item-buff behavior.
- **Test file**: Not yet isolated. Observed in `ai.external_selfplay.run_external_selfplay("buff_consumable_ambush")`.
- **Error**: The Barbarian selected a legal decision-epoch `Move` row toward `(13, 6)` with reason `move_toward_visible_enemy`, but `/ai/sessions/{session_id}/commands/execute` returned `rejected` with message `Failed to move for Move`.
- **Resolution**: Movement execution now performs typed revalidation against
  the current world instead of relying on the obsolete serialized path shape.
- **Verification**: `tests/manual/test_50_movement_revalidation.py` reports
  `5 passed` on 2026-07-24.
- **Status**: RESOLVED 2026-07-24.

### Ranged-harrier hold-spacing command reports enemy position instead of spacing anchor
- **Found**: 2026-07-04 while validating the Sorcerer-Barbarian self-play harness with the broader external AI regression file.
- **Test file**: `tests/manual/test_35_subjective_external_ai.py::test_ranged_harrier_skips_healthy_melee_follow_up_after_spending_action`
- **Error**: The policy correctly ends turn with `hold_ranged_spacing` after spending the action, but `reference_entity_position` is `(3, 1)` while the test expects the spacing anchor `(5, 1)`.
- **Hypothesis**: The behavior is tactically correct, but the metadata contract is muddled: `reference_entity_position` currently means the referenced enemy position, while this test expects the desired spacing/anchor position. The policy payload likely needs a separate field for spacing anchor instead of overloading reference entity metadata.
- **Resolution**: Fixed by adding `spacing_anchor_position` to `AgentCommand` and keeping `reference_entity_position` as the actual subjective enemy position. The regression now asserts both fields explicitly.
- **Verification**: `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`; `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`.
- **Status**: RESOLVED

### Codex subjective final brief can omit the final killed enemy
- **Found**: 2026-07-02 during Codex barbarian full-game playtest through `ai.codex_tools`.
- **Test file**: Not yet covered. Observed after a completed `/simulation/start-human?character_class=barbarian` game with Codex controlling heroes and external AI controlling monsters.
- **Error**: After the final Frenzied Strike ended the encounter, `ai.codex_tools turn` showed no living enemies and listed the previously killed Skeleton Warrior and Skeleton Archer as dead, but did not list the final killed Skeleton Warlock in `visible_entities`/`dead_enemies`.
- **Hypothesis**: The final death/encounter-end observation frame may clear or fail to materialize the last killed entity for the Codex session, possibly because visibility projection stops after encounter end or because the death transition is not retained as remembered knowledge.
- **Current finding**: Focused remembered-living and remembered-death
  projection regressions pass. The exact terminal Codex brief from this report
  has no retained durable artifact, so the UI-level symptom is not presently
  reproducible.
- **Status**: RETIRED AS AN UNMEASURED HISTORICAL LEAD 2026-07-29. Current
  remembered-death and terminal-replay regressions pass; reopen only with a
  retained artifact and deterministic automated reproducer.

### External AI can submit a stale command immediately after turn-start epoch
- **Found**: 2026-07-02 in server logs during Codex barbarian playtest cleanup.
- **Test file**: Not yet isolated. Runtime logs from `/tmp/dnd_engine_barbarian.log`.
- **Error**: The external AI received a `turn_start` decision epoch, selected `Eldritch Blast`, then the command endpoint rejected it as stale because the current epoch had advanced to a `snapshot` epoch at the next observation cursor. The agent recovered through resync and retried successfully.
- **Resolution**: Published epochs survive control-cursor advancement, and
  epoch clearing is actor-aware.
- **Verification**: The focused published-epoch and previous-actor-clear
  regressions pass on 2026-07-24.
- **Status**: RESOLVED 2026-07-24.

### Directional environment example scripts have stale pyright types
- **Found**: 2026-06-28 during directional environment item metadata hygiene.
- **Test file**: `examples/test_directional_environment_items.py`, `examples/test_directional_arena_hotswap.py`
- **Error**: `uv run pyright dnd/items/environment.py examples/test_directional_environment_items.py examples/test_directional_arena_hotswap.py` reports optional-member access on `object_at(...).uuid` in the arena hotswap script and passes generic `Event` declarations into `Attack._validate()` where pyright expects `AttackEvent` in the directional environment script.
- **Hypothesis**: Runtime guards already protect these paths, but the script helpers do not narrow optional and event types enough for pyright. This appears to be a stale example typing issue, not a directional item behavior regression.
- **Resolution**: Fixed by narrowing attack declaration events with `isinstance(..., AttackEvent)` before calling `Attack._validate()` and by making the arena `object_at()` helper generic with explicit wall-object narrowing before reading `.uuid`.
- **Verification**: `uv run pyright dnd/items/environment.py examples/test_directional_environment_items.py examples/test_directional_arena_hotswap.py`, `uv run python examples/test_directional_environment_items.py`, and `uv run python examples/test_directional_arena_hotswap.py` pass.
- **Status**: RESOLVED

### Core action engine-book example has stale pyright types
- **Found**: 2026-06-28 during health block metadata hygiene.
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: `uv run pyright dnd/blocks/health.py examples/test_engine_book_entity_composition.py examples/test_engine_book_core_actions_combat.py` reports stale typing in the core-action example script: indirect `dnd.core.dice` monkeypatch attributes, generic `Event` values passed to `Attack._validate()`, optional status-message string access, generic event attributes, and shield/weapon union narrowing.
- **Hypothesis**: Runtime behavior is protected by the script and pytest parity layer, but the example uses dynamic test helpers and event filtering patterns that pyright cannot narrow. This appears to be an example typing backlog, not a health-block regression.
- **Resolution**: Fixed in `examples/test_engine_book_core_actions_combat.py` by importing the dice module directly for deterministic monkeypatching, narrowing attack declaration events with `isinstance(..., AttackEvent)` before validation, guarding optional status messages, filtering event history to concrete event payload classes, and narrowing melee-main equipment to `Weapon` before adding extra damage dice.
- **Verification**: `uv run pyright dnd/blocks/health.py examples/test_engine_book_entity_composition.py examples/test_engine_book_core_actions_combat.py`, `uv run python examples/test_engine_book_core_actions_combat.py`, `uv run pytest -q tests/engine/test_combat_actions.py tests/architecture/test_source_model_hygiene.py`, and `uv run pytest -q tests/engine_book` pass.
- **Status**: RESOLVED

### Retaliation reaction attack also spent the normal action
- **Found**: 2026-06-28 during Chapter 16 Retaliation parity expansion.
- **Test file**: `examples/test_engine_book_class_features.py`
- **Error**: `retaliation_processor()` instantiated a normal `Attack`, so a triggered Retaliation spent the Barbarian's normal action through `Attack._apply_costs()` and then spent the reaction manually.
- **Hypothesis**: Retaliation should own the reaction cost and the nested attack should be costless, matching the feature's reaction-attack contract.
- **Resolution**: Fixed in `dnd/classes/barbarian.py` by constructing the Retaliation `Attack` with `costs=[]` and leaving the explicit reaction spend in the handler.
- **Verification**: EB-16-022 proves a successful adjacent Retaliation reduces the attacker's HP, spends the reaction, preserves the Barbarian's action, and respects no-reaction, distance, weapon, and cleanup gates.
- **Status**: RESOLVED

### Indomitable Might skill-check mutation does not recompute outcome
- **Found**: 2026-06-28 during Chapter 16 Barbarian event-heavy parity expansion.
- **Test file**: Exploratory verification while extending `examples/test_engine_book_class_features.py`.
- **Error**: A forced-low Athletics `SkillCheckEvent` for a level-18 Barbarian with Indomitable Might emitted an EFFECT event whose dice total was replaced with the Strength score (`20`), but the event `result` stayed `False`, the completion event also kept `result == False`, and `Entity.skill_check()` returned the original pre-handler roll total (`6`) with `success == False`.
- **Hypothesis**: `Entity.skill_check()` computes `skill_check_outcome` and `success` before firing SKILL_CHECK EFFECT handlers. `indomitable_might_processor()` replaces `event.dice_roll.total`, but neither the processor nor `Entity.skill_check()` recomputes `result`, and the method returns the local pre-handler `roll` and `success`.
- **Resolution**: Fixed in `dnd/entity.py` by recomputing the skill-check outcome from the post-handler EFFECT event's final dice roll before phasing to COMPLETION, and by returning that final roll/result from `Entity.skill_check()`.
- **Verification**: EB-16-021 proves low Athletics checks are raised to the Strength score, the returned API result and completed `SkillCheckEvent.result` both become successful, non-Athletics checks are unchanged, and removing Indomitable Might removes the handler behavior.
- **Status**: RESOLVED

### Heal roll-result helper did not complete result events
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `fire_heal_roll_result()` fired `HEAL_ROLL_RESULT` through `EFFECT` and returned the final roll, but unlike d20 and damage result paths it did not phase the roll-result event to `COMPLETION`.
- **Hypothesis**: The helper mirrored handler interception but missed the lifecycle completion step that keeps event history and parent lineage consistent with other roll-result systems.
- **Resolution**: Fixed in `dnd/spells/spell_utils.py` by completing the `HealRollResultEvent` after EFFECT handlers run.
- **Verification**: EB-03-015 proves healing result events now store DECLARATION, EFFECT, and COMPLETION phases and preserve the parent lineage while returning the final roll.
- **Status**: RESOLVED

### HealEvent total_healing mutations were ignored during HP application
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `Entity.receive_healing()` let `HEAL` EFFECT handlers mutate `HealEvent.total_healing`, but HP application still called `self.health.heal(amount)` with the original requested amount. Canceled healing already blocked HP changes; reduced or increased healing did not.
- **Hypothesis**: The method treated the post-EFFECT `HealEvent` as observational metadata instead of the source of truth for the final amount to apply.
- **Resolution**: Fixed in `dnd/entity.py` by applying `max(0, heal_event.total_healing)` after EFFECT handlers run.
- **Verification**: EB-03-018 proves reduced healing applies the handler-mutated amount, while canceled healing leaves HP unchanged and completes with `actual_healing == 0`.
- **Status**: RESOLVED

### Chained d20 replacement audit used the original roll for every entry
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `D20RollResultEvent.replace_roll()` used `self.roll.total` as the old total for every audit entry. Later handlers received the current effective replacement, but the audit text for a second replacement still described original-to-new instead of previous-effective-to-new.
- **Hypothesis**: The single-roll d20 path predated the multi-handler audit pattern used by damage result events and did not call `get_effective_roll()` when creating its audit message.
- **Resolution**: Fixed in `dnd/core/events.py` by deriving the old total from `self.get_effective_roll().total` before storing the new `final_roll`.
- **Verification**: EB-03-019 proves simple exact attack d20 handlers run before filtered exact handlers, later handlers see the previous effective total, and audit entries record 5 to 12, then 12 to 15, then 15 to 18.
- **Status**: RESOLVED

### Real attack d20 result events lost weapon-slot context
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `Attack._apply()` created `AttackD20RollResultEvent` through `Entity.roll_d20()` without passing the active `weapon_slot`, so real attack d20 result handlers saw `weapon_slot is None`.
- **Hypothesis**: The attack pipeline threaded `weapon_slot` into attack validation and damage but skipped the result-event call.
- **Resolution**: Fixed in `dnd/actions.py` by passing `weapon_slot=weapon_slot` to `source_entity.roll_d20(...)`.
- **Verification**: EB-03-016 proves a real `MELEE_MAIN` attack completion event carries `weapon_slot == WeaponSlot.MELEE_MAIN`.
- **Status**: RESOLVED

### Great Weapon Fighting applied beyond eligible two-handed weapon dice
- **Found**: 2026-06-28 during Chapter 03 dice/result parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: The GWF processor rerolled every damage packet in `DamageRollResultEvent.final_rolls` using the main weapon's die size, and treated any versatile melee weapon as eligible even when a shield occupied the off hand.
- **Hypothesis**: The processor conflated all attack damage packets with primary weapon damage and had no explicit two-hand check for versatile weapons.
- **Resolution**: Fixed in `dnd/classes/fighter.py` by rerolling only the primary damage packet and by requiring versatile weapons to be in `MELEE_MAIN` with an empty melee off hand.
- **Verification**: EB-03-013 proves positive/no-low/ranged/one-handed GWF filters, EB-03-016 proves extra damage packets are preserved, and EB-03-017 proves shielded versatile weapons do not qualify while unshielded versatile weapons do.
- **Status**: RESOLVED

### Paralyzed did not grant attacker advantage
- **Found**: 2026-06-28 during Chapter 08 standard-condition parity expansion
- **Test file**: `examples/test_engine_book_standard_conditions.py`
- **Error**: `Paralyzed` applied Incapacitated, Strength/Dexterity save auto-failures, and close-range auto-critical hits, but did not add the SRD attacker-advantage modifier even though the condition description included that clause.
- **Hypothesis**: The severe-condition implementation added the close-range critical target-side contextual modifier but skipped the static target-side advantage modifier that similar conditions such as `Stunned` and `Unconscious` already use.
- **Resolution**: Fixed in `Paralyzed._apply()` by adding a static `AdvantageStatus.ADVANTAGE` modifier to the target's `equipment.ac_bonus.to_target_static`.
- **Verification**: EB-08-006 now proves paralyzed targets grant attacker advantage at both adjacent and distant ranges, while adjacent attackers still get `AUTOCRIT` and distant attackers do not.
- **Status**: RESOLVED

### Critical immunity status was ignored by attack outcome resolution
- **Found**: 2026-06-28 during Chapter 03 engine-book parity expansion
- **Test file**: `examples/test_engine_book_dice_events.py`
- **Error**: `ModifiableValue.critical` could resolve to `CriticalStatus.NOCRIT`, but `determine_attack_outcome()` ignored that status. Natural 20s, lowered critical thresholds, and `AUTOCRIT` could still return `AttackOutcome.CRIT` when the roll carried `NOCRIT`.
- **Hypothesis**: The value layer had a critical-immunity state, but the shared d20 outcome interpreter only checked `AUTOCRIT`.
- **Resolution**: Fixed in `determine_attack_outcome()` by downgrading otherwise-critical hits to ordinary hits when `roll.critical_status == CriticalStatus.NOCRIT`, while preserving `AUTOMISS`, `AUTOHIT`, natural 1, and miss behavior.
- **Verification**: EB-03-009 proves `AUTOMISS` beats natural 20, `AUTOHIT` beats natural 1, `AUTOCRIT` can upgrade auto-hits, `NOCRIT` suppresses natural-20 and threshold criticals, and `AUTOCRIT`/lowered thresholds do not make ordinary misses hit.
- **Status**: RESOLVED

### Inactive contextual damage-type modifiers raised during aggregation
- **Found**: 2026-06-28 during Chapter 02 engine-book parity expansion
- **Test file**: `examples/test_engine_book_modifiable_values.py`
- **Error**: `ContextualValue.damage_types` called `max(type_counts.values())` even when every contextual damage-type callable returned `None`, so inactive contextual damage-type modifiers could raise `ValueError` instead of contributing no type.
- **Hypothesis**: The contextual damage-type aggregation path missed the same empty-active-result guard already used by other contextual modifier channels.
- **Resolution**: Fixed by returning an empty damage-type list when contextual damage-type modifiers exist but none evaluate to a concrete `DamageTypeModifier`.
- **Verification**: EB-02-011 proves inactive contextual damage-type modifiers leave both the contextual channel and aggregate `ModifiableValue` with no damage type, then contribute normally when context activates the callable.
- **Status**: RESOLVED

### BaseBlock constructor source propagation runs before field discovery
- **Found**: 2026-05-29 during Chapter 05 engine-book parity expansion
- **Test file**: `examples/test_engine_book_blocks_context.py`
- **Error**: `BaseBlock.set_values_and_blocks_source()` and `validate_values_and_blocks_source_and_target()` run before `populate_blocks_and_values()` discovers explicit Pydantic `ModifiableValue` and child `BaseBlock` fields. Constructor-provided fields with mismatched sources can remain mismatched after construction.
- **Hypothesis**: `populate_blocks_and_values()` likely needs to run before source/target/context normalization and validation, or discovery should happen in a pre/post-init path before those validators depend on `self.values` and `self.blocks`.
- **Resolution**: Fixed on 2026-06-27 in `BaseBlock.set_values_and_blocks_source()` by populating direct value/block indexes before source, target, and context propagation or validation run.
- **Verification**: EB-05-013 now proves constructor-provided foreign direct values and child blocks are discovered and normalized to the parent source, target, and context.
- **Status**: RESOLVED

### BaseBlock indexes canceled no-effect condition applications
- **Found**: 2026-05-29 during Chapter 05 engine-book parity expansion
- **Test file**: `examples/test_engine_book_blocks_context.py`
- **Error**: `BaseCondition.apply()` returns a canceled event when `_apply()` returns no effect event, but `BaseBlock.add_condition()` treats that truthy event as success and indexes the condition even though `condition.applied` is `False`.
- **Hypothesis**: `BaseBlock.add_condition()` should probably require a non-canceled completion event, or `BaseCondition.apply()` should return `None` for failed application. Current behavior is documented as EB-05-010 until Tommaso approves a behavior change.
- **Resolution**: Fixed on 2026-06-27 in `BaseBlock.add_condition()` by indexing only when the returned event is not canceled and `condition.applied` is true.
- **Verification**: EB-05-010 and EB-07-010 now prove no-effect condition applications return a canceled event for observability but do not write active-condition name, UUID, or source indexes.
- **Status**: RESOLVED

### Repeated standard action setup duplicates handlers
- **Found**: 2026-05-29 during Chapter 06 engine-book parity expansion
- **Test file**: `examples/test_engine_book_entity_composition.py`
- **Error**: Calling `setup_standard_actions(entity)` twice clears action templates but leaves existing handlers registered. The second call doubles the source entity's global `EventQueue` handlers from 6 to 12 and doubles entity-tracked handlers from 4 to 8.
- **Hypothesis**: Standard action setup should either remove/replace prior handlers by name/source before registering new ones, or be documented as one-time initialization and guarded against repeated calls. Current behavior is documented as EB-06-014 until Tommaso approves a behavior change.
- **Resolution**: Fixed on 2026-06-27 in `setup_standard_actions()` by removing prior standard entity handlers and weapon-template handlers for the entity before re-registering the standard template/handler set.
- **Verification**: EB-06-014 now proves repeated setup leaves six global standard handlers and four entity-owned handlers with one copy of each standard handler name.
- **Status**: RESOLVED

### Intermittent control-spell repeat-save cleanup failure
- **Found**: 2026-06-27 during Chapter 07 condition-lifecycle hygiene verification
- **Test file**: `tests/engine/test_spell_families.py`
- **Error**: One run of `uv run pytest -s -q tests/engine_book` failed `test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup`: after `target.on_turn_end(...)`, `"Hold Person"` remained in `target.active_conditions`. Running the Chapter 15 spell-family parity file in isolation passed, and an immediate full `tests/engine_book` rerun also passed (`221 passed`).
- **Repeat**: Recurred on 2026-06-27 during Chapter 15 illusion hygiene verification. The full `tests/engine_book` run failed the same assertion after `target.on_turn_end(...)`; an immediate focused rerun of `tests/engine/test_spell_families.py::test_chapter_15_example_parity` passed (`21 passed`).
- **Repeat**: Recurred on 2026-06-27 during Chapter 15 necromancy hygiene verification. `uv run python examples/test_engine_book_spell_families.py` failed the same assertion in `test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup` after `target.on_turn_end(...)`, while the focused Chapter 15/book-integrity pytest layer passed in the same verification window.
- **Repeat**: Recurred again on 2026-06-27 during the same necromancy verification rerun. `uv run python examples/test_engine_book_spell_families.py` next failed the sibling assertion in `test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup`: after `target.on_turn_end(...)`, `"Hold Monster"` remained in `target.active_conditions`.
- **Repeat**: Recurred on 2026-06-27 during Chapter 15 conjuration hygiene verification. `uv run pytest -s -q tests/engine/test_spell_families.py tests/architecture/test_source_model_hygiene.py` failed `test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup` with `"Hold Monster"` still active after `target.on_turn_end(...)`; an immediate rerun of the same command passed (`27 passed`), and the full `tests/engine_book` suite passed in the same verification window (`221 passed`).
- **Repeat**: Recurred on 2026-06-27 during Chapter 15 evocation hygiene verification. `uv run pytest -s -q tests/engine/test_spell_families.py tests/architecture/test_source_model_hygiene.py` failed `test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup` with `"Hold Monster"` still active after `target.on_turn_end(...)`; an immediate focused Chapter 15 rerun passed (`21 passed`), the narrow Chapter 15/book-integrity gate passed (`27 passed`), and the full `tests/engine_book` suite passed (`221 passed`).
- **Hypothesis**: This looks like an intermittent full-suite ordering/state leak or nondeterministic handler/save interaction around repeat-save cleanup. Check global registries, `EventQueue` handlers, and spell-family reset helpers if it repeats.
- **Resolution**: Fixed on 2026-06-27 in `dnd/entity.py` by making `determine_attack_outcome()` apply natural 1/critical-face semantics only to `RollType.ATTACK`. Saving throws and skill checks now compare `DiceRoll.total` to DC, matching the SRD relationship recorded in Chapter 03. The apparent intermittent cleanup failure was a natural-1 repeat save with a total high enough to beat the DC being treated as `CRIT_MISS`, so the hold condition correctly stayed active under the old engine behavior.
- **Verification**: Added EB-03-007 in `examples/test_engine_book_dice_events.py`; 200-iteration Hold Person and Hold Monster cleanup repro loops passed; `uv run pytest -s -q tests/engine/test_dice_event_semantics.py tests/architecture/test_source_model_hygiene.py` passed (`13 passed`); `uv run pytest -s -q tests/engine/test_spell_families.py tests/architecture/test_source_model_hygiene.py` passed (`27 passed`); full `uv run pytest -s -q tests/engine_book` passed (`222 passed`).
- **Status**: RESOLVED

### Partial stack merge can mutate inventory before capacity failure
- **Found**: 2026-06-08 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: `Inventory.add_item()` merges as much of an incoming compatible stack as possible before checking whether the remaining stack can be inserted. If the final insert fails because of weight capacity, the method returns `False`, but the existing stack has already increased and the incoming stack has already decreased.
- **Hypothesis**: Stack insertion likely needs to precompute the full merge/remainder outcome before mutating either stack, or define `False` as partial-success-with-remainder and expose that explicitly. Current behavior is documented as EB-13-012 until Tommaso approves a behavior change.
- **Resolution**: Fixed on 2026-06-27 in `Inventory.add_item()` by using the same hypothetical merge/remainder plan for `can_add()` and `add_item()` before mutating stack counts.
- **Verification**: EB-13-012 now proves a failed capacity add leaves the existing stack, incoming stack, inventory membership, and total weight unchanged.
- **Status**: RESOLVED

### Transfer into existing stack can stamp consumed item as stored
- **Found**: 2026-06-27 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: `Inventory.transfer_to()` could transfer an item into an already-compatible target stack, let `Inventory.add_item()` consume and unregister the incoming object, then stamp that consumed object with the target owner and storage UUID even though it was not present in the target inventory.
- **Hypothesis**: Stack merge consumption should be an identity cleanup boundary. The surviving target stack remains stored, while the fully consumed incoming object should have `stack_count == 0`, no registry entry, and no authoritative owner/storage/tile fields.
- **Resolution**: Fixed on 2026-06-27 by clearing consumed item location fields inside `Inventory.add_item()` and by making `Inventory.transfer_to()` stamp target ownership only when the incoming object remains present in the target inventory.
- **Verification**: EB-13-017 now proves transfer into an existing stack increases the target stack, unregisters the consumed incoming object, and leaves the consumed object's owner/storage fields clear.
- **Status**: RESOLVED

### High-level equip cancellation can orphan inventory items
- **Found**: 2026-06-08 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: `Entity.equip_item()` removes an item from inventory before calling `Equipment.equip()`. If a `WEAPON_EQUIP` execution handler cancels the equip event, `Entity.equip_item()` still returns `True`, the equipment slot remains empty, and the item is no longer in the inventory even though `stored_in_uuid` still points at that inventory.
- **Hypothesis**: `Equipment.equip()` probably needs to return success/failure, and `Entity.equip_item()` should only remove from inventory after a successful equip or should roll back on canceled equipment events.
- **Resolution**: Fixed on 2026-06-27 by making `Equipment.equip()` return `False` when an equip event is canceled before slot assignment, and by having `Entity.equip_item()` remove the incoming item from inventory only after a successful equipment assignment.
- **Verification**: EB-13-013 now proves a canceled high-level weapon equip returns `False`, keeps the pre-existing equipped weapon in its slot, and leaves the incoming item in inventory with owner/storage fields intact.
- **Status**: RESOLVED

### Resolved two-handed weapon and shield policy gap
- **Found**: 2026-06-08 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: A weapon with `WeaponProperty.TWO_HANDED` can be equipped in `MELEE_MAIN` while a shield is equipped in `MELEE_OFF`. The engine validates ranged/melee slot type and off-hand light-weapon rules, but does not enforce a hand-occupancy policy for two-handed weapons versus shields.
- **Hypothesis**: Equipment needs a hand-occupancy model that resolves two-handed melee conflicts consistently while preserving the engine's parallel melee/ranged videogame loadouts.
- **Resolution**: Fixed on 2026-06-29 in `Equipment.equip()` by replacing hard-block validation with order-based melee slot displacement.
- **Verification**: EB-13-014 now proves a shield/off-hand item displaces an active two-handed melee main weapon, a two-handed melee main weapon displaces an occupied melee off hand, and high-level equip rehomes displaced items to inventory.
- **Status**: RESOLVED

### Equipped item destruction can leave stale equipment slots and modifiers
- **Found**: 2026-06-27 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: `BaseItem.destroy()` calls `container.remove_contained_item()` when an item has `stored_in_uuid`, but `Equipment` inherited the no-op `BaseBlock.remove_contained_item()`. Destroying an equipped shield cleared the shield object's own flags and registry entry, but left `entity.equipment.weapon_melee_off` pointing at the destroyed shield, so the shield AC bonus still contributed to `entity.ac_bonus()`.
- **Hypothesis**: Equipment needs to participate in the same container cleanup contract as Inventory. Because destruction is not a voluntary unequip action, the slot cleanup should run item unequip hooks but should not be cancelable by `*_UNEQUIP` event handlers.
- **Resolution**: Fixed on 2026-06-27 by adding `Equipment.remove_contained_item()`, which finds the slot containing the UUID, calls the item's unequip hook path directly, and clears the slot.
- **Verification**: EB-13-018 now proves destroyed equipped shields clear their slot and AC contribution, while destroyed chain mail clears its slot, Stealth disadvantage hook, heavy-armor movement hook, owner/storage fields, and registry entry.
- **Status**: RESOLVED

### Generic usable item actions can overspend charges
- **Found**: 2026-06-27 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: The base `UsableItem.get_use_actions()` only hid actions when `charges == 0`. A generic use action with `charge_cost=2` on an item with one charge was still discoverable; `execute_use_action()` applied the action, then ignored `consume_charge(False)`, leaving the item unchanged after the effect.
- **Hypothesis**: Base usable-item discovery should follow the same charge-cost filtering already implemented by `SpellScroll`, and `execute_use_action()` should reject stale/direct calls before applying effects.
- **Resolution**: Fixed on 2026-06-27 by filtering base usable action templates when `charges < charge_cost` and by adding a pre-execution charge guard in `execute_use_action()`.
- **Verification**: EB-13-020 now proves an undercharged generic healing potion exposes no action, direct execution raises before healing, charges remain unchanged, and the item stays in inventory.
- **Status**: RESOLVED

### Raw inventory add can leave items with multiple authoritative locations
- **Found**: 2026-06-27 during Chapter 13 engine-book parity expansion
- **Test file**: `examples/test_engine_book_items_inventory_equipment.py`
- **Error**: Calling `Inventory.add_item()` directly on a floor item inserted it into the inventory but left `tile_uuid` and the grid object index intact. Calling it directly on an item that was already in another inventory could also leave the previous inventory still claiming the same UUID.
- **Hypothesis**: Even though `Inventory.add_item()` is lower level than `Entity.loot_item()`, successful insertion should be a container boundary: detach previous floor/container membership first, then stamp owner/storage for surviving stacks.
- **Resolution**: Fixed on 2026-06-27 by making `Inventory.add_item()` detach successful inserts from previous containers and grid placement, clear floor tile state, and stamp surviving stacks with the inventory owner/storage UUIDs.
- **Verification**: EB-13-021 now proves raw inventory add removes a floor item from the grid, stamps owner/storage, and rehomes an item from one inventory to another without leaving the previous inventory membership.
- **Status**: RESOLVED

### Fireball scroll legacy test has an invalid saved-damage lower bound
- **Found**: 2026-06-27 during Chapter 13 equipment cancellation regression checks
- **Test file**: `examples/test_inventory_use_actions.py`
- **Error**: `test_scroll_fireball_actual_damage` failed with `AssertionError: Min 8d6 = 8 damage (even with save), got 7`. A successful Dexterity save halves Fireball damage, so the saved lower bound for 8d6 can be lower than 8.
- **Hypothesis**: The legacy assertion should account for save-for-half or force failed saves if it intends to assert raw 8d6 damage bounds. The engine-book parity suite passed in the same verification window.
- **Resolution**: `test_scroll_fireball_actual_damage` now asserts each target takes 4-48 fire damage, the valid range after 8d6 Fireball damage and save-for-half. This keeps the test focused on AoE scroll execution while respecting the SRD save clause.
- **Status**: RESOLVED 2026-06-27

### Entity.is_spellcaster ignores registered spell templates
- **Found**: 2026-06-08 during Chapter 14 engine-book parity expansion
- **Test file**: `examples/test_engine_book_spellcasting_core.py`
- **Error**: An entity with no spell slots but a registered `Fire Bolt` cantrip has a visible available spell action, but `Entity.is_spellcaster` still returns `False`. The property currently checks spell-slot base values and does not inspect registered `SpellAction` templates.
- **Resolution**: `Entity.is_spellcaster` now returns true for entities with positive base spell slots or registered spell action templates. EB-06-008 and EB-14-013 cover the slot-or-template behavior, including cantrip-only spellcasters.
- **Status**: RESOLVED 2026-06-27

### HP-pool spells mutate target-selection state across validation and application
- **Found**: 2026-06-27 during Chapter 15 engine-book parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `Sleep.get_all_targets()` and `ColorSpray.get_all_targets()` spend `hp_pool_remaining` while selecting targets. `SpellAction.apply()` can ask for targets during validation and again during application, so a deterministic pool that exactly covers one target can be depleted before the spell effect is applied.
- **Hypothesis**: HP-pool spell target selection needs a cached selected-target list for the action instance so validation and convolution use the same UUIDs.
- **Status**: FIXED — `Sleep` and `ColorSpray` now cache selected HP-pool target UUIDs per spell instance; EB-15-013 and EB-15-014 cover repeated target selection and exact-pool application.

### Sleep HP-pool selection included unconscious creatures
- **Found**: 2026-06-27 during Chapter 15 HP-pool parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `Sleep.get_all_targets()` skipped undead and charmed-immune creatures, but did not skip creatures already under `Unconscious`, while the local SRD Sleep text says unconscious creatures are ignored when ordering HP-pool targets.
- **Hypothesis**: Sleep should mirror Color Spray's existing unconscious skip before sorting and spending the HP pool.
- **Status**: FIXED — `Sleep.get_all_targets()` now skips active `Unconscious` creatures, and EB-15-030 covers upcast dice plus unconscious, undead, and charmed-immunity skips.

### Color Spray cannot-see clause is only partially represented
- **Found**: 2026-06-27 during Chapter 15 HP-pool parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-030 covers Color Spray skips for unconscious, already-blinded, and `Blinded`-immune targets. The local SRD text also excludes creatures that cannot see, but the engine does not expose a single sight-capability predicate that covers all possible reasons a creature cannot see.
- **Hypothesis**: Color Spray needs a shared sensory capability query, likely on `Senses` or `Entity`, before it can distinguish ordinary visible creatures from every sightless or currently unable-to-see creature without hard-coding spell-local cases.
- **Resolution**: `Entity` now exposes `has_ordinary_sight` and `can_see_visual_effects()`, which returns false for Blinded, Unconscious, and explicitly sightless creatures while preserving ordinary sight by default. `ColorSpray.get_all_targets()` uses that shared predicate before spending HP-pool budget, and EB-15-030 proves a 1 HP sightless target in the cone is skipped.
- **Status**: RESOLVED 2026-06-27

### Eyebite repeat strike cost and Sickened save ability diverged from SRD
- **Found**: 2026-06-27 during Chapter 15 Eyebite parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `EyebiteStrike` declared an action cost but inherited `BaseAction._apply_costs()`, so repeat strikes did not spend the caster's action. `SickenedCondition` also used a Constitution repeat save at turn end, while the local SRD Eyebite text says Sickened repeats the Wisdom saving throw.
- **Hypothesis**: Eyebite's granted action should opt into the standard action-economy cost applier, and Sickened's repeat-save handler should use the same Wisdom save ability as the initial Eyebite strike.
- **Status**: FIXED — `EyebiteStrike._apply_costs()` now applies its action cost, `SickenedCondition` repeats a Wisdom save, and EB-15-031 covers initial Sickened application, repeat strike cost, repeat-save ability, and concentration cleanup.

### Eyebite Panicked movement surfaces diverged from SRD
- **Found**: 2026-06-27 during Chapter 15 Eyebite parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-031 through EB-15-033 covered the granted action lifecycle for Sickened, successful-save retarget blocking, visible-target validation, and the action surface for waking `Eyebite Asleep`. `EyebitePanickedEffect` still applied `Frightened` plus a repeat Wisdom save rather than enforcing Dash movement away from the caster and ending when the target is at least 60 feet away and unable to see the caster.
- **Hypothesis**: Eyebite needed a movement/visibility end-condition model for Panicked before that SRD clause could be represented cleanly.
- **Status**: FIXED — EB-15-034 removes the Panicked repeat save, spends Dash on the panicked target's turn, moves it away along a selected safe route, and ends the effect only once it is at least 60 feet away and cannot see the caster.

### Condition-owned handler cleanup can leave stale block-local indexes
- **Found**: 2026-06-27 during Chapter 15 Shield parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Removing `Shield` at turn start removed its condition-owned handlers from `EventQueue`, but `shielded.get_event_handler_by_name("Shield: Magic Missile Block")` still found a stale local handler. `EventHandler.remove()` looked up the owner through `BaseObject.get(source_entity_uuid)`, while entities are registered as `BaseBlock` instances rather than `BaseObject` instances in this path.
- **Hypothesis**: Blocks that register handlers should stamp themselves as handler owners so handler cleanup can remove block-local indexes without importing upward from the event layer.
- **Status**: FIXED — `BaseBlock.add_event_handler()` now stores the registering block on the handler, and `EventHandler.remove()` uses that owner to clear block-local indexes; EB-15-020 covers Shield turn-start handler cleanup.

### Web lacks its SRD turn-start restraint save
- **Found**: 2026-06-27 during Chapter 15 zone-spell parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `WebZone` restrained creatures on entry and on initial cast, but did not register a turn-start handler. The SRD `Web` text requires a Dexterity save when a creature starts its turn in the webs.
- **Hypothesis**: `WebZone` should mirror the existing entry-save processor with a normal `TURN_START` handler that checks whether the acting entity's position is in `affected_positions`.
- **Status**: FIXED — `WebZone` now registers `Web Turn Start Save`, and EB-15-021 covers failed turn-start saves applying `Web Restrained` and its `Restrained` subcondition.

### Web zone omitted SRD light obscurement
- **Found**: 2026-06-27 during Chapter 15 Web parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: `WebZone` applied difficult terrain and restraint handlers but did not apply any tile obscurement, while the local SRD Web text says the area is lightly obscured.
- **Hypothesis**: Web should use `ZoneControlCondition`'s existing light modifier path with `sets_light_level=LightLevel.DIM_LIGHT` and `light_is_obscurement=True`.
- **Status**: FIXED — `WebZone` now applies dim-light obscurement through tile modifiers, and EB-15-029 covers obscurement application and cleanup.

### Web fire exposure lacks engine surface
- **Found**: 2026-06-27 during Chapter 15 Web parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-029 proves default 2D grid Web casts persist as floor-layered zones, and EB-15-037 now proves explicit unanchored/unlayered Web casts collapse at the caster's next turn start. The engine still did not expose environmental fire exposure for one-round burning Web cubes.
- **Hypothesis**: Web fire needs a shared environmental primitive: a way for position-targeted fire effects or flame objects to expose a tile to fire and burn away a specific 5-foot cube for one round.
- **Progress**: `Web.anchored_or_layered=False` now creates an unanchored Web zone that registers a collapse handler, removes the zone at the caster's next turn start, cleans terrain/light modifiers, and removes concentration through the linked-condition path.
- **Status**: FIXED — `FireExposureEvent` now exposes a grid position to environmental fire, `WebZone` burns away the affected cube, removes that cube's terrain/light/marker state, clears same-source `Web Restrained`, deals one-round 2d4 fire to creatures starting their turn in the burning cube, and preserves the rest of the concentration zone. EB-15-042 covers the full lifecycle.

### Spirit Guardians exit handling removes slow during internal zone movement
- **Found**: 2026-06-27 during Chapter 15 zone-spell parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Moving from one `Spirit Guardians` zone tile to another fired `SPATIAL_ENTITY_LEFT` for the old cell and removed `Spirit Guardians Slowed`, even though the entity remained inside the zone. The manually added exit spatial handler was also tracked as a normal handler, so concentration cleanup left stale spatial position indexes.
- **Hypothesis**: The exit processor should inspect the movement destination carried on the left event and only remove slow when the destination is outside `affected_positions`. The manual exit handler should be returned as a spatial handler UUID so `ZoneControlCondition` cleanup removes its position indexes.
- **Status**: FIXED — `SpiritGuardiansZone` now preserves slow during internal zone movement, removes it only on actual exit, and tracks the exit handler as a spatial handler; EB-15-021 covers internal movement, exit cleanup, and concentration cleanup of spatial indexes.

### Attack Object action cost diverged from discovery
- **Found**: 2026-05-29 during Chapter 09 engine-book parity expansion
- **Test file**: `examples/test_engine_book_action_templates_discovery.py`
- **Error**: `Attack Object` discovery reports `cost_type == "actions"` and `cost_amount == 1`, but executing the action leaves `entity.action_economy.actions.normalized_score == 1`.
- **Hypothesis**: `AttackObject` inherits `BaseAction._apply_costs()`, which only phases the event to completion and does not consume action economy. The subclass likely needs an `_apply_costs()` implementation similar to other concrete action classes, or `BaseAction._apply_costs()` should become the generic action-cost applier.
- **Status**: FIXED — `AttackObject._apply_costs()` now uses the standard action-economy cost applier, and EB-09-012 proves that destroying a breakable object spends the advertised action.

### Natural 20 attacks are not automatic hits against unreachable AC
- **Found**: 2026-05-29 during Chapter 10 engine-book parity expansion
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: A natural 20 attack roll against an AC raised beyond the final roll total resolves as `AttackOutcome.MISS`, even though the SRD attack-roll rule makes natural 20 an automatic critical hit.
- **Hypothesis**: `determine_attack_outcome()` checks natural 20 only inside the `roll.total >= target_ac` branch. It likely needs a natural-roll branch before the AC comparison, after explicit `AUTOMISS` handling.
- **Resolution**: Fixed on 2026-06-27 in `dnd/entity.py` by resolving `RollType.ATTACK` natural 20 as `AttackOutcome.CRIT` before the AC comparison, while preserving explicit `AUTOMISS` and `AUTOHIT` precedence.
- **Verification**: EB-03-007 now proves the primitive outcome rule directly, and EB-10-010 now proves an integrated `Attack` with natural 20 damages a target whose AC is unreachable by total alone.
- **Status**: RESOLVED

### Removed duplicate SRD Shove action surface
- **Found**: 2026-06-28 during Chapter 10 SRD-vs-engine tracking
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: The engine briefly carried both the videogame `Shove` action and an explicit `SrdShove` action, which made the runtime surface look like it supported selectable rulesets.
- **Resolution**: Fixed on 2026-06-29 by removing the `SrdShove`/`SrdShoveEvent` runtime surface and deleting its engine-book parity row. `Shove` remains the single supported videogame action: bonus action, passive target resistance, Strength-scaled forced movement, and no default SRD prone/push choice.
- **Verification**: EB-10-022 now proves the single shove contract through `test_eb_10_022_shove_uses_videogame_bonus_action_forced_movement`; SRD text remains reference material only.
- **Status**: FIXED

### Player-style death saving throw subsystem is not implemented
- **Found**: 2026-06-28 during Chapter 10 SRD-vs-engine tracking
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: The local SRD death text distinguishes instant death, falling unconscious at 0 HP, death-save successes/failures, natural 1/20 death-save effects, damage-at-0 failures, stabilization, and monster death defaults. The engine applies `DeathEvent` and `Dead` to any entity at 0 HP or below, with no player/monster distinction, death-save counters, stable state, start-turn death-save roll, or API-visible dying state.
- **Hypothesis**: Current HP flow models monster-style death for all entities. A future player-death subsystem would need new state, events, turn integration, healing/stabilization cleanup, damage-at-0 handling, and API fields.
- **Resolution**: `Entity` now has opt-in player-style death-save state through `uses_death_saves`, death-save counters, and authoritative `LifeState`. Default entities transition directly to `LifeState.DEAD` at 0 HP. Opted-in entities transition to `LifeState.DYING`, which derives unconscious mechanics without a synthetic condition, unless massive damage kills them; they roll `DeathSaveEvent` at turn start, stabilize after three successes, die after three failures, treat natural 1 as two failures, regain 1 HP on natural 20, add failures for damage at 0 HP, and clear death-save state on true healing.
- **Verification**: EB-10-023 pins default monster-style death. EB-10-025 proves turn-start player-style death saves and natural-1 death. EB-10-026 proves natural-20 healing, three-success stabilization, stable save skipping, critical damage-at-0 failures, healing reset, and massive-damage death.
- **Remaining scope**: Concrete Medicine-check and healer's-kit stabilization actions are still future action surfaces; the lower-level `Entity.stabilize()` primitive now exists.
- **Status**: RESOLVED 2026-06-28

### Mixed weapon damage applies resistance, vulnerability, and immunity using only the primary damage type
- **Found**: 2026-05-29 during Chapter 10 engine-book parity expansion
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: A weapon attack with 6 slashing plus 6 fire damage applies damage-type multipliers to the summed 12 damage using only the primary slashing type. Against slashing resistance it deals 6 total damage; against slashing vulnerability it deals 24 total damage; against slashing immunity it deals 0 total damage, canceling the fire component too.
- **Hypothesis**: `Attack.attack_consequences()` should apply resistance/vulnerability/immunity per `Damage` component, or `TakeDamageEvent`/`Entity.receive_damage()` should support typed damage components instead of one aggregate `damage_type`.
- **Resolution**: Fixed on 2026-06-27 by adding `Health.take_damage_components()` and routing unmodified multi-component `Entity.receive_damage()` calls through it. Each component applies its own resistance/vulnerability/immunity multiplier, then flat damage reduction and temporary HP are applied once to the combined post-multiplier damage.
- **Verification**: EB-10-016 now proves 6 slashing plus 6 fire against slashing resistance deals 9 total damage; EB-10-019 now proves slashing vulnerability deals 18 and slashing immunity still allows the 6 fire damage through.
- **Status**: RESOLVED

### Lethal opportunity attack movement advances into the next cell before stopping
- **Found**: 2026-05-29 during Chapter 10 engine-book parity expansion
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: A mover killed by an opportunity attack while leaving reach ends at the provoking step destination `(5, 7)` and `Move` completes as partial movement. `Jump` does the same state update, then raises `ValueError: Not enough bonus_actions...` because `Dead`/`Incapacitated` zeroes action economy before `Jump._apply_costs()` spends the bonus action. Under the usual SRD timing model, the opportunity attack interrupts just before the creature leaves reach, so a lethal OA should likely leave the creature in the origin cell `(5, 6)`.
- **Hypothesis**: `Move._apply()` and `Jump._apply()` fire `STEP_MOVEMENT`, let handlers apply OA, then update the entity position before checking for `Dead`. The death check may need to happen immediately after the processed step event and before `Entity.update_entity_position()`. `Jump` may also need to settle action costs before movement side effects or tolerate post-death cost application.
- **Resolution**: Fixed on 2026-06-27 in `Move._apply()` and `Jump._apply()` by checking authoritative life state and neutral action capability immediately after step-event handlers run and before `Entity.update_entity_position()`. Lethal opportunity attacks now leave the creature in the origin cell, and the interrupted step does not reach `COMPLETION`. `Jump._apply_costs()` now returns the existing completion event without consuming costs if the jumper is dead or lacks action agency.
- **Verification**: EB-10-017 now proves lethal Move opportunity attacks stop before leaving reach; EB-10-018 now proves lethal Jump opportunity attacks complete as partial jumps without raising the post-death bonus-action cost error.
- **Status**: RESOLVED

### Forced movement skips intermediate terrain and completes before final landing damage
- **Found**: 2026-05-29 during Chapter 10 engine-book parity expansion
- **Test file**: `examples/test_engine_book_core_actions_combat.py`
- **Error**: Shove-style forced movement updates the target directly from the start cell to the final cell. It emits no `STEP_MOVEMENT` events and no intermediate `SPATIAL_ENTITY_ENTERED` events, so hazardous terrain between start and landing is skipped. If the final landing cell deals terrain damage, the `TakeDamageEvent.parent_event` points at the `ForcedMovementEvent`, but the forced movement event has already completed and its combat log has no damage sub-entry.
- **Hypothesis**: `Shove._apply()` calls `ForcedMovementEvent.phase_to(COMPLETION)` before `Entity.update_entity_position()`. Forced movement may need a step/transition loop for terrain-sensitive effects, or at least a final-position update before completing the forced movement event so child damage can be collected in the combat log.
- **Resolution**: Fixed on 2026-06-27 in `Shove._apply()` by advancing forced movement through `EXECUTION` and `EFFECT`, updating the target one 5-foot transition at a time under the forced-movement event, and completing the forced-movement event only after terrain/spatial effects resolve.
- **Verification**: EB-10-021 now proves forced movement emits no `STEP_MOVEMENT`, preserves target movement economy, emits intermediate `SPATIAL_ENTITY_ENTERED` effects, applies both traversed spike cells, and nests the damage logs under the forced movement lineage.
- **Status**: RESOLVED

### Diagonal pathfinding cost and exact max-distance pruning disagree
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: `GridMap.compute_paths((0, 0))` returns a one-cell diagonal `(1, 1)` at cost `1`, but `GridMap.compute_paths((0, 0), max_distance=1)` excludes `(1, 1)` while including cardinal cost-1 neighbors. The hidden diagonal tie-break epsilon is included in pruning even though it is stripped from returned distances.
- **Hypothesis**: `dnd/core/dijkstra.py` should probably compare `max_distance` against the public true movement cost, or allow a tiny tolerance for epsilon-only overflow, while still using epsilon for queue tie-breaking.
- **Resolution**: Fixed on 2026-06-27 in `dnd/core/dijkstra.py` by comparing `max_distance` to the true movement distance before diagonal tie-break epsilon is applied to the priority distance.
- **Verification**: EB-11-012 now proves a one-cell diagonal with returned cost `1` is included by `GridMap.compute_paths(..., max_distance=1)` with the expected path.
- **Status**: RESOLVED

### Negative-coordinate tiles are not fully reachable by pathfinding
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: `GridMap` can store tiles at negative coordinates and `GridMap.can_transition((-2, 0), (-1, 0))` returns `True`, but `GridMap.compute_paths((-2, 0))` returns only the start tile. Starting from `(-1, 0)` can reach `(0, 0)`, but cannot reach deeper negative tile `(-2, 0)`.
- **Hypothesis**: `GridMap.compute_paths()` passes only width and height to `dijkstra()`, and `dnd/core/dijkstra.py::get_neighbors()` clamps raw coordinates to `0 <= nx < width` and `0 <= ny < height`. The pathfinder likely needs origin offsets or bounds-aware min/max coordinates rather than nonnegative width/height alone.
- **Resolution**: `dijkstra()` and `get_neighbors()` now accept `min_x` and `min_y` search origins, and `GridMap.compute_paths()` passes the map's actual bounds. EB-11-013 proves paths can move through negative-coordinate tiles in both directions.
- **Status**: RESOLVED 2026-06-27

### Raw GridMap object removal leaves BaseItem floor-location fields stale
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: `BaseItem.place_on_grid()` sets `item.tile_uuid` and `item.position`, but calling `GridMap.remove_object(item.uuid)` only removes the object UUID from grid indexes and observer senses. The item still has its previous `tile_uuid`, and `item.get_position()` still returns the removed floor position.
- **Hypothesis**: `GridMap.remove_object()` is intentionally type-unaware, but callers can easily mistake it for full item removal. Either higher-level item APIs should be the only public removal path for `BaseItem` objects, or `GridMap.remove_object()` should optionally notify/remove item location state through a polymorphic hook.
- **Resolution**: `GridMap.remove_object()` now calls `BaseBlock.on_grid_object_removed()`, and `BaseItem` clears `tile_uuid` when the removal is an authoritative location clear. Internal object re-placement opts out of location clearing, and EB-11-016 proves raw removal clears floor location without destroying the item.
- **Status**: RESOLVED 2026-06-27

### Generic ZoneControlCondition cone and line construction collapses to the origin
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: Direct `Cone` and `Line` AoE shapes expand correctly when given a caster origin plus a distinct target direction, but generic `ZoneControlCondition(zone_shape="cone"|"line", zone_direction=...)` computes only `{zone_center}`. The default zone builder passes `zone_center` as both the AoE target and the caster position, and passes `radius_feet`/`direction` fields that `Cone` and `Line` do not consume.
- **Hypothesis**: `ZoneControlCondition._compute_affected_positions()` likely needs shape-specific construction: convert `zone_direction` into a target endpoint and pass `length_feet`/`width_feet` for line-like zones, or make directional zone subclasses always override the method as `GustOfWindZone` does today.
- **Resolution**: `ZoneControlCondition._compute_affected_positions()` now converts `zone_direction` into a target endpoint for generic cone and line zones, passes `zone_radius_feet` as length, and exposes `zone_width_feet` for line width. EB-11-018 proves generic cone/line zones match direct AoE construction.
- **Status**: RESOLVED 2026-06-27

### Cylinder action previews can use wall-filtered subjective geometry
- **Found**: 2026-05-29 during Chapter 11 engine-book parity expansion
- **Test file**: `examples/test_engine_book_grid_tiles_pathfinding.py`
- **Error**: `Cylinder.compute_for_targeting()` and `Cylinder.compute_objective()` include the full geometric footprint through lateral walls, but inherited `Cylinder.compute_subjective()` applies propagation FOV and omits cells behind walls. `Entity._compute_aoe_at_position()` calls `shape.compute_subjective()` for all AoE action previews, so a cylinder spell preview can show a wall-filtered footprint even though execution affects the full cylinder area.
- **Hypothesis**: AoE preview should dispatch to `compute_for_targeting()` when a shape implements it, or `Cylinder` should override `compute_subjective()` with the same footprint semantics while preserving perception-filtered entity UUIDs.
- **Resolution**: `Cylinder.compute_subjective()` now delegates to the full-footprint targeting computation while preserving perception-filtered entity UUIDs. EB-11-019 proves subjective preview, targeting, and objective execution share the same footprint through lateral walls.
- **Status**: RESOLVED 2026-06-27

### Magical darkness zone removal does not recompute FOV for cells behind it
- **Found**: 2026-05-29 during Chapter 12 engine-book parity expansion
- **Test file**: `examples/test_engine_book_senses_light_stealth.py`
- **Error**: Applying a single-cell magical darkness zone uses the batched light path and emits `requires_fov=True`, so observers drop the magical darkness cell and cells behind it. Removing that same zone changes the tile back to bright light, but the removal batch computes `requires_fov=False` because no changed tile currently resolves to `MAGICAL_DARKNESS`. Observers refresh the former darkness cell but do not resubscribe to or restore visibility for cells behind it.
- **Hypothesis**: Light batch events likely need to know whether any changed position previously blocked vision, not only whether it blocks vision after the mutation. Zone light cleanup may need to pass old light/blocking state into `_fire_light_batch_events()`, or light modifier removal should explicitly request FOV recomputation when removing magical darkness.
- **Resolution**: Zone light apply/removal now detects old or new `MAGICAL_DARKNESS` at changed positions and passes `requires_fov=True` into the batch light event. EB-12-011 proves removing a magical-darkness zone restores cells and entities behind it.
- **Status**: RESOLVED 2026-06-27

### Daylight cannot dispel Darkness through the current visibility gate
- **Found**: 2026-06-27 during Chapter 15 zone-spell edge probing
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: After `Darkness` applies magical darkness to a target point, `Daylight` targeting the same point cancels during validation with `Position (...) not visible`. The `Darkness Zone` condition remains active and the tile remains `LightLevel.MAGICAL_DARKNESS`. This makes the SRD Daylight clause that dispels darkness from a spell of 3rd level or lower unreachable through that direct targeting path.
- **Hypothesis**: Light/obscurement spell validation may need a targeting exception for positions inside spell-created darkness, or `Daylight` needs an overlap/dispel path that can target the edge or an adjacent visible point and remove lower-level darkness zones in the affected area. The current implementation layers illumination/obscurement modifiers and does not remove the source darkness condition.
- **Status**: FIXED — `Daylight` now allows direct targeting of magical-darkness tiles and removes overlapping `Darkness Zone` conditions after computing the Daylight zone. EB-15-026 covers Fog Cloud obscurement cleanup, Darkness blocking darkvision, and Daylight dispelling the active Darkness zone.

### Insect Plague zone omitted SRD difficult terrain and light obscurement
- **Found**: 2026-06-27 during Chapter 15 damage-zone parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Before EB-15-027, `InsectPlagueZone` dealt piercing damage and created markers/handlers, but `adds_difficult_terrain` was `False` and no light/obscurement modifier was applied, while the SRD spell area is difficult terrain and lightly obscured.
- **Hypothesis**: The zone should use `ZoneControlCondition`'s existing terrain and light modifier channels: `adds_difficult_terrain=True`, `sets_light_level=LightLevel.DIM_LIGHT`, `light_is_obscurement=True`.
- **Status**: FIXED — `InsectPlagueZone` now applies difficult terrain and dim-light obscurement, and EB-15-027 covers damage, terrain/light cleanup, and upcast dice.

### Stinking Cloud over-locked action economy and ignored poison immunity
- **Found**: 2026-06-27 during Chapter 15 gas-zone parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Before EB-15-028, a failed Stinking Cloud save applied `NauseatedCondition` by capping actions, bonus actions, and reactions at zero. The local SRD text spends the creature's action, not every turn resource. The zone also forced a saving throw for poison-immune creatures.
- **Hypothesis**: `NauseatedCondition` should cap only `action_economy.actions`, and `StinkingCloudZone` should short-circuit when the entity has poison damage immunity.
- **Status**: FIXED — Stinking Cloud now leaves bonus actions, reactions, and movement available, skips poison-immune creatures, and EB-15-028 covers both behaviors.

### Sleet Storm used sphere propagation and DC 10 concentration disruption
- **Found**: 2026-06-27 during Chapter 15 ice-zone parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: Before EB-15-028, `SleetStormZone` used `zone_shape="sphere"`, so wall propagation could shadow cells that should be in the falling cylinder area. Its concentration disruption save was also hard-coded to DC 10 instead of using the caster's spell save DC.
- **Hypothesis**: Generic `ZoneControlCondition` should support the existing `Cylinder` AoE shape, `SleetStormZone` should select it, and the turn-start concentration check should use `self.spell_dc`.
- **Status**: FIXED — `ZoneControlCondition` now supports `zone_shape="cylinder"`, Sleet Storm uses it, concentration disruption uses the caster's spell save DC, and EB-15-028 covers wall-shadow, prone, terrain/obscurement, cleanup, and concentration-break behavior.

### Stinking Cloud and Sleet Storm environmental clauses lack engine surfaces
- **Found**: 2026-06-27 during Chapter 15 gas/ice-zone parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-028 covered poison immunity through the health resistance API, but the engine originally did not expose a general breathing requirement trait for Stinking Cloud's breathless-creature automatic success. The same slice did not find a wind model for Stinking Cloud dispersal or a flame object/state model for Sleet Storm flame dousing.
- **Hypothesis**: The remaining wind clause needed an explicit wind primitive with duration semantics before Stinking Cloud could disperse after 4 rounds in moderate wind or 1 round in strong wind without spell-local ad hoc flags.
- **Progress**: `Entity` now exposes `requires_breathing`, `EntityConfig` propagates it, and `StinkingCloudZone` skips turn-start saving throws and nausea for breathless creatures. `BaseItem` now exposes an exposed-flame dousing contract, `Torch` and `WallTorch` implement it, lit items emit `ExposedFlameEvent`, and `SleetStormZone` douses carried and placed exposed flames in its area. `WindExposureEvent` now carries wind speed and exposed positions, `GustOfWindZone` emits strong wind exposure from its line, and `StinkingCloudZone` consumes wind exposure to disperse after the SRD round thresholds.
- **Verification**: EB-15-041 proves a breathless creature inside Stinking Cloud receives no saving throw, no `Nauseated` condition, and no action loss. EB-15-043 proves Sleet Storm douses lit carried torches and placed wall torches on initial cast, immediately douses newly ignited flames inside an active storm, and preserves outside flames. EB-15-044 proves Stinking Cloud disperses after four cloud-caster turn starts in 10 mph wind and after one in 20 mph Gust of Wind exposure.
- **Status**: FIXED

### Passive perception sensory updates omit the paths-dirty payload flag
- **Found**: 2026-05-29 during Chapter 12 engine-book parity expansion
- **Test file**: `examples/test_engine_book_senses_light_stealth.py`
- **Error**: When a condition changes an observer's passive perception, `SpatialSensesCallback._handle_own_perception_change()` refilters visible entities and sets `observer.senses._paths_dirty = True`. The emitted `SENSORY_UPDATE` includes `passive_perception_changed=True`, the replacement `passive_perception`, and visible entity deltas, but `paths_dirty` remains `False`.
- **Hypothesis**: `_emit_update()` appears to compare before/after snapshots for `_paths_dirty` before or without capturing the mutation made during passive-perception refiltering. The payload should probably report `paths_dirty=True` whenever the callback marks the observer's path cache dirty.
- **Resolution**: `SpatialSensesCallback._emit_sensory_update()` now treats condition-driven passive-perception or sense-mode changes as path-refresh payloads whenever the observer's path cache is dirty after the update, even if the cache was already dirty before that event. EB-12-012 now asserts `paths_dirty=True` in the passive-perception replacement payload.
- **Status**: RESOLVED 2026-06-27

### Directional collision memory is not cleared at turn start
- **Found**: 2026-05-29 during Chapter 12 engine-book parity expansion
- **Test file**: `examples/test_engine_book_senses_light_stealth.py`
- **Error**: Hidden edge-like blockers record `Senses.directional_collision_blocked` entries such as `((0, 0), "east")`, while hidden cell blockers record `Senses.collision_blocked` positions. `Encounter.start_turn()` clears only `entity.senses.collision_blocked`, then refreshes senses. Directional collision memory persists into the new turn and continues blocking the remembered transition.
- **Hypothesis**: `Encounter.start_turn()` should probably clear both positional and directional collision memory before refreshing senses, or the persistence should be explicitly intentional and surfaced in the API. Current behavior is documented as EB-12-013.
- **Resolution**: `Encounter.start_turn()` now clears both `collision_blocked` and `directional_collision_blocked` before refreshing senses. EB-12-013 proves a remembered hidden directional blocker affects immediate replanning, then resets at the next turn start and allows the fresh direct subjective path again.
- **Status**: RESOLVED 2026-06-27

### Lucky feat example silently skips attack-roll coverage
- **Found**: 2026-05-28 during Chapter 16 engine-book parity validation
- **Test file**: `examples/test_lucky_feat.py`
- **Error**: `uv run python examples/test_lucky_feat.py` exits with status 0, but the attack-roll section prints `ERROR: No attack actions available` and returns without asserting attack-roll Lucky behavior.
- **Hypothesis**: The test creates skeleton attackers and calls `setup_standard_actions()`, but no usable attack action is surfaced in `get_available_actions()` for that scenario. The script should either equip/register an attack deterministically or fail when the attack-roll scenario is not exercised.
- **Resolution**: `setup_test_environment()` now creates a real grid, and `test_lucky_on_attack_roll()` equips the attacker with a longsword before standard action setup. The attack section asserts an attack action exists, forces a low attack d20 plus Lucky reroll, and requires one luck point plus at least one modified `ATTACK_D20_ROLL_RESULT`.
- **Status**: RESOLVED 2026-06-27

### Restoration spell implementations are narrower than SRD text
- **Found**: 2026-06-27 during Chapter 15 restoration parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-023 originally documented narrower behavior: `LesserRestoration` removed only a fixed condition list, and `GreaterRestoration` did not cover all SRD restoration categories.
- **Resolution**: `LesserRestoration` now handles disease-tagged conditions. `GreaterRestoration` now handles one curse-tagged condition, one petrification-tagged condition, one ability-score-reduction-tagged condition, one hit-point-maximum-reduction-tagged condition, and one `Exhaustion` level. `RemoveCurse` removes every active `ConditionTag.CURSE` condition instead of the first one.
- **Verification**: EB-15-023 proves disease-tagged Lesser Restoration removal, supported major-condition Greater Restoration removal with sub-condition cleanup, one curse-tagged Greater Restoration removal, and all-curse Remove Curse removal while unrelated `Poisoned` remains. EB-15-038 proves Greater Restoration removes the newer SRD-tagged effect surfaces and that ability-score and hit-point-maximum modifiers are cleaned up. EB-08-014 adds a standard `Petrified` condition model for the expressible SRD effects, EB-15-039 proves Greater Restoration removes it, EB-08-015 adds levelled `Exhaustion`, and EB-15-040 proves Greater Restoration reduces it one level at a time.
- **Status**: RESOLVED 2026-06-28

### Exhaustion recovery lifecycle is not wired to rests or revival
- **Found**: 2026-06-28 during Chapter 08 exhaustion implementation
- **Test file**: `examples/test_engine_book_standard_conditions.py`
- **Error**: EB-08-015 implements and documents the six cumulative Exhaustion levels, and EB-15-040 proves Greater Restoration reduces Exhaustion by one level. The SRD condition text also says finishing a qualifying long rest reduces exhaustion by 1, and being raised from the dead reduces exhaustion by 1. The current engine has resource-level `ActionEconomy.on_long_rest()` and condition duration `long_rest()` markers, but no general entity rest/revival lifecycle that reduces `Exhaustion.level`.
- **Hypothesis**: A future rest/revival lifecycle should either call a condition-level reduction helper or replace the active `Exhaustion` condition with `level - 1`, preserving condition cleanup semantics.
- **Resolution**: `BaseCondition` now exposes a polymorphic level-reduction hook, `Exhaustion` returns a lower-level replacement, `Entity.on_long_rest()` reduces living entities' Exhaustion by one level after resource/slot/long-rest-duration recovery, `Entity.revive()` transitions authoritative life state to `ALIVE`, replaces only the lifecycle-owned transform, and reduces Exhaustion by one level, and `GreaterRestoration` delegates to the shared entity reduction path.
- **Verification**: EB-06-015 proves long-rest Exhaustion reduction, `UNTIL_LONG_REST` condition expiry, spell-slot restoration, directional resource recharge, and revival cleanup plus Exhaustion reduction. EB-06-016 proves long-rest normal HP restoration, temporary HP expiry, and the dead/0-HP no-benefit guard. EB-06-017 proves Hit Dice spending/recovery, CON-modifier healing, HP-cap behavior, and long-rest half-total recovery. EB-15-040 still proves Greater Restoration reduces Exhaustion one level at a time.
- **Remaining scope**: Food/drink qualification, 24-hour long-rest cadence, and concrete resurrection spells remain separate unimplemented lifecycle/spell surfaces.
- **Status**: RESOLVED 2026-06-28

### Protective abjuration spells model narrower hooks than SRD text
- **Found**: 2026-06-27 during Chapter 15 protective-abjuration parity expansion
- **Test file**: `examples/test_engine_book_spell_families.py`
- **Error**: EB-15-025 originally documented narrower behavior: `ProtectionFromPoison` neutralized an active `Poisoned` condition and granted poison-save advantage, poison resistance, and future `Poisoned` immunity; `DeathWard` rewrote lethal damage to leave the target at 1 HP and negated one no-damage instant-death event; `FreedomOfMovement` bypassed difficult terrain, blocked magical speed reduction, blocked `Grappled`/`Restrained`, blocked magically tagged `Paralyzed`, and let a protected creature spend 5 feet of movement to escape active nonmagical `Grappled` or `Restrained`, but did not model the SRD underwater movement and attack clauses.
- **Hypothesis**: The gap needed explicit underwater attack context plus an action-level swimming movement lifecycle that chooses `MovementMode.SWIMMING`, accounts for creatures without swim speed, and gives Freedom of Movement a concrete traversal path to suppress those movement penalties.
- **Resolution**: `ProtectionFromPoison` now removes an already-active `Poisoned` condition before adding its persistent protection and adds contextual advantage to saving throw requests whose `condition_context` is `"Poisoned"`. `DeathWard` now handles `InstantDeathEvent`; `PowerWordKill` uses that no-damage primitive, so Death Ward can negate it once without changing HP. `FreedomOfMovement` now uses condition-aware contextual immunity to block only incoming `Paralyzed` conditions tagged `ConditionTag.MAGICAL`, its `ignore_magical_speed_reduction` flag prevents magical movement-speed penalties from `Slowed`, `Spirit Guardians Slowed`, and `Ray of Frost Effect`, its `ignore_underwater_penalties` flag suppresses `Underwater` attack penalties and no-swim-speed movement surcharges, and `Freedom of Movement Escape` spends 5 feet of movement to remove active nonmagical `Grappled` or `Restrained` while unregistering on cleanup. `Underwater` now models the SRD underwater attack penalties, and `Swim` uses `MovementMode.SWIMMING` for water traversal and registered-action discovery.
- **Verification**: EB-15-025 proves active poison neutralization, poison-save advantage, poison resistance, future `Poisoned` immunity, lethal-damage survival, no-damage instant-death negation, magical speed-reduction prevention, magical paralysis immunity, nonmagical restraint escape, underwater ranged/melee attack-penalty suppression, Swim discovery in water, Freedom-protected swim cost, unprotected no-swim-speed doubled swim cost, and cleanup.
- **Status**: RESOLVED 2026-06-28

### Equipment API test sends stale equip/unequip payloads
- **Found**: 2026-05-08 during edge-aware spatial foundation validation
- **Test file**: `examples/server_tests/test_equipment_api.py`
- **Error**: Running against a temporary `uvicorn server.event_server:app --port 8000` reaches the equipment endpoints, but `POST /entity/{uuid}/equip` and `POST /entity/{uuid}/unequip` return HTTP 422 because the request body omits required `entity_uuid`. The later expected 400/404 error-case checks then fail as follow-on failures.
- **Hypothesis**: The server request models were updated to require `entity_uuid`, but this manual integration test still sends the older payload shape with only `session_id`, `item_uuid`/`slot`. The test likely needs to include `entity_uuid` in equip/unequip payloads or the endpoint model needs compatibility handling.
- **Resolution**: The final command contract makes the route path the sole
  entity identity. `EquipRequest` is exactly `session_id`, `item_uuid`, and
  `slot`; `UnequipRequest` is exactly `session_id` and `slot`. Canonical route
  and generated-SDK tests enforce those shapes, so neither a compatibility
  field nor the obsolete example payload survives.
- **Status**: RESOLVED 2026-07-23

### WebSocket ping test assumes pong is the next frame
- **Found**: 2026-05-03 during spell catalog endpoint validation
- **Test file**: `server/test_websocket.py`
- **Error**: Running `PYTHONPATH=. .venv/bin/python server/test_websocket.py` reaches `test_websocket_connection`, sends `{"type": "ping"}`, then `assert data["type"] == "pong"` fails because the next received frame can still be an `"event"` frame.
- **Hypothesis**: The WebSocket stream is asynchronous and may have queued spatial events when the ping is sent. The test should drain/filter frames until it sees `pong` or times out, instead of assuming request/response ordering on a mixed event/control channel.
- **Resolution**: The mixed raw-event `/ws` surface and its helper script were
  deleted by the canonical transport hard cut. Player clients use the typed
  subjective SSE journal, and objective inspectors use the separately typed
  diagnostics SSE stream; there is no ping/event multiplexing contract left.
- **Status**: RESOLVED 2026-07-23

### Decision epochs can expose melee rows that execution rejects as out of reach
- **Found**: 2026-07-02 during Barbarian Hero vs enemy policy v3 playtest.
- **Observed artifact**: `/tmp/dnd_barbarian_v3_iteration/014_frenzied_warlock_r2.json`
- **Error**: The Codex turn summary exposed and recommended `entity|Frenzied Strike|uuid=...` against Skeleton Warlock while the Hero was still 10 ft away. The AI command endpoint rejected the row with `Target entity not in reach for Frenzied Strike (Greataxe)`.
- **Impact**: The decision epoch/action-row surface can claim a melee command is executable when the authoritative executor will reject it. This wastes an agent action attempt and makes recommendation ranking untrustworthy for melee turns.
- **Mitigation**: `ai.codex_tools.client.build_turn_summary()` now suppresses plainly out-of-reach melee rows from operator attacks/recommendations and warns the operator to move adjacent first.
- **Resolution**: Fixed the concrete source of this failure in `FrenziedStrike.pre_validate()`. Discovery now delegates to the normal action validation path after confirming a melee weapon exists, so out-of-reach or non-visible Frenzied Strike targets are filtered before decision epochs or summaries can expose them.
- **Verification**: `uv run pytest tests/manual/test_15_class_features.py::test_frenzied_strike_discovery_excludes_targets_outside_weapon_reach -q`
- **Status**: RESOLVED 2026-07-02

### `alt_skip_slot` getattr in BaseAction violates no-duck-typing principle
- **Found**: 2026-02-28
- **File**: `dnd/core/base_actions.py` line 274
- **Error**: `getattr(self, 'alt_skip_slot', False)` — parent class (`BaseAction.effective_costs()`) uses getattr to access a field (`alt_skip_slot`) that only exists on a subclass (`SpellAction`). This is duck-typing from parent to child, violating the codebase rule against getattr/hasattr.
- **Hypothesis**: `alt_skip_slot` should either be moved up to `BaseAction` (alongside the other `alt_*` override fields that are already there), or `effective_costs()` should be overridden in `SpellAction` to handle spell-slot-specific cost filtering. Moving the field up is the simpler fix since `alt_cost_type`, `alt_extra_costs`, `alt_target_type`, and `alt_target_count` are already on `BaseAction`.
- **Status**: FIXED — moved `alt_skip_slot` to `BaseAction` alongside other `alt_*` fields, removed duplicate from `SpellAction`


### Surprised combatants can take reactions before their skipped first turn
- **Found**: 2026-06-28 during Chapter 18 surprise/reaction parity expansion
- **Test file**: `examples/test_engine_book_encounters_apis.py`
- **Error**: `CombatantState.surprised` skipped a combatant's first round-1 turn, but the combatant still began the encounter with a usable reaction. This violated the SRD surprise rule in `interactive_ruleset/Gameplay/Combat.md`: a surprised creature cannot take reactions until its first turn ends. Opportunity-attack handlers could therefore fire before the surprised combatant's skipped turn occurred.
- **Resolution**: `Encounter.start_encounter()` now spends the starting reactions of surprised combatants. The surprised turn skip path runs the entity turn-start and turn-end hooks without asking the controller for an action, so the first-turn boundary still recharges reactions after the skipped turn ends.
- **Verification**: EB-18-019 proves a surprised monster cannot make an opportunity attack before its skipped first turn, then has its reaction available again when round 2 starts.
- **Status**: RESOLVED


### Removed MeleeAIController previously chose Shove before a melee attack
- **Found**: 2026-06-28 during Chapter 18 controller parity expansion
- **Test file**: `examples/test_engine_book_encounters_apis.py`
- **Error**: The former `MeleeAIController.get_next_action()` looped over all entity-targeted actions and instantiated the first affordable valid target. Because `Shove` is also entity-targeted and was registered before weapon attack templates, an adjacent melee AI chose `Shove` instead of `Attack_MELEE_MAIN`, contradicting the controller's documented priority.
- **Resolution**: The special-case melee controller and the later
  session-command `ExternalAIController` have both been removed. AI sides now
  use `NativeAIController` for in-process policy assignments or
  `RegisteredAIController` for the authenticated provider protocol; both
  execute through the canonical typed intent resolver.
- **Verification**: `tests/ai/test_basic_policy.py`,
  `tests/ai/test_registered_ai_controller.py`, and
  `tests/manual/test_151_native_ai_execution.py` cover selection, provider
  fencing, and canonical execution.
- **Status**: SUPERSEDED



### API error messages need improvement
- **Found**: 2026-02-24
- **Test file**: `examples/test_engine_book_encounters_apis.py`
- **Error**: Some HTTP 400/404 responses from the server still return generic string details with no structured context. The action, entity, handler, equipment, session/game, event-filter, simulation, and mapeditor endpoint slices now expose correction payloads, but other endpoint families can still leave an AI agent without the current state, valid alternatives, or endpoint-specific recovery hints.
- **Hypothesis**: Remaining endpoint families should move toward structured detail payloads with a machine-readable code, current resource state, and valid alternatives. The action routes can use available-action discovery as their correction source; other endpoints need endpoint-specific context.
- **Progress**: `/action/execute` now returns structured `detail` objects for unknown action names and invalid target indexes. `/action/self`, `/action/entity`, and ordinary `/action/position` now return the same structure for unknown actions and wrong endpoint/action-shape requests. EB-18-009 and EB-18-010 prove the payload includes `code`, `message`, acting entity identity, action economy, valid action names, and the grouped available-actions correction payload. EB-18-023 proves malformed or missing `/action/entity` target UUIDs also return structured target context, known entities, action economy, and available-action corrections. EB-18-011 proves `/entity/{uuid}` lookup and handler-toggle errors include known entities or valid handler choices. EB-18-012 proves equipment/item/equip/unequip errors include valid slots, inventory item UUIDs, equipped item UUIDs, and the current equipment snapshot. EB-18-013 proves session and game-join errors include valid player types, known sessions, active-game state, requested entities/faction, and known entities. EB-18-026 proves the lower-level session action-authority validator now reports invalid sessions, disconnected sessions, missing active games, unowned entities, wrong turns, and stopped turn states with structured context. EB-18-014 proves event-filter, SSE session UUID, and simulation-control errors include valid event/phase choices, cursor state, simulation state, requested delay, and delay bounds. EB-18-015 proves mapeditor failures include valid preset/tile/object/loot IDs, saved map IDs, current map summary, directional-patch required fields, and request-specific context. EB-18-024 proves `/tile/{x}/{y}` missing-tile errors include the requested position, current grid bounds, tile count, entity count, and object count. EB-18-025 proves `/action/end-turn` no-active-encounter errors include the requested session/entity, active game context, simulation state, and known entities.
- **Resolution**: Server action/API errors now use structured `detail` dictionaries. `server/event_server.py` and `server/session.py` have no bare string `HTTPException(detail=...)` calls; remaining direct constructors use structured helper payloads.
- **Verification**: EB-18-009 through EB-18-015 and EB-18-023 through EB-18-026 cover the endpoint families above. `tests/architecture/test_source_model_hygiene.py::test_server_http_errors_do_not_use_bare_string_details` guards the source-level contract, and `rg -n "HTTPException\\(|detail=\\\"|detail=f\\\"" server -g '*.py'` now reports only structured constructors/helper calls.
- **Status**: RESOLVED

### Raw ability-score modifiers were counted as direct ability-modifier bonuses
- **Found**: 2026-06-28 during Chapter 16 Primal Champion parity expansion
- **Test file**: `examples/test_engine_book_class_features.py`
- **Error**: `PrimalChampion` correctly raised raw Strength and Constitution scores from 20 to 24, but attack, save, skill, AC, and HP-derived paths treated the +4 raw score modifier as a +4 ability modifier in several entity assembly methods. SRD parity expects a +4 raw ability-score increase at 20 to become a +2 ability-modifier increase.
- **Resolution**: `Ability.modifier` and `Ability.get_combined_values()` now aggregate the raw score first and then apply the D&D ability-score normalizer. Entity skill, saving throw, attack, AC, and spell-attack assembly now use `Ability.get_combined_values()` instead of manually combining `ability_score` and `modifier_bonus`.
- **Verification**: EB-16-023 proves Primal Champion gives +2 to the relevant STR/CON-derived combat surfaces and +40 HP at Barbarian level 20.
- **Status**: RESOLVED

### Divine Smite omitted the SRD undead and fiend bonus die
- **Found**: 2026-06-28 during Chapter 16 Divine Smite parity expansion
- **Test file**: `examples/test_engine_book_class_features.py`
- **Error**: `create_divine_smite_processor()` capped smite dice at 5d8 from spell slot level but did not add the SRD +1d8 against undead or fiend targets, even though `Entity.creature_type` and `CreatureType.UNDEAD`/`CreatureType.FIEND` were available.
- **Resolution**: Divine Smite now checks the target entity's creature type in the damage-roll-result handler, adds one d8 for undead and fiend targets, and caps those target-type smites at 6d8. The handler records `divine_smite_creature_type_bonus` in event context.
- **Verification**: EB-16-024 proves humanoid targets keep the normal 5d8 cap, undead targets add the bonus d8 at 1st-level slots, and fiend targets can reach the 6d8 target-type cap with a 5th-level slot.
- **Status**: RESOLVED

### Lucky condition removal left its luck-point resource behind
- **Found**: 2026-06-28 during Chapter 16 Lucky policy parity expansion
- **Test file**: `examples/test_engine_book_class_features.py`
- **Error**: Removing `LuckyFeature` cleaned up the owned d20 handler through the base condition lifecycle, but the `luck_points` resource granted in `_apply()` remained on the entity.
- **Resolution**: `LuckyFeature._remove()` now removes the `luck_points` resource before delegating to the base removal phases.
- **Verification**: EB-16-025 proves Lucky's automatic policy gates, long-rest recharge, handler cleanup, and resource cleanup.
- **Status**: RESOLVED

### Pytest capture mode fails in the Codex shell during engine-book runs
- **Found**: 2026-06-28 during Chapter 18 API parity verification
- **Test file**: `tests/engine/test_encounter_apis.py`
- **Error**: Running `uv run pytest -q tests/engine/test_encounter_apis.py tests/architecture/test_source_model_hygiene.py` from the Codex shell reported `no tests ran`, then failed during pytest shutdown with `FileNotFoundError` in `_pytest/capture.py` while truncating the capture temp file. `uv run pytest --collect-only --capture=no -q tests/engine/test_encounter_apis.py` collected the expected ten Chapter 18 parity cases, and a `pytest.main(["-q", "--capture=no", "tests/engine_book"])` driver passed the full engine-book suite.
- **Hypothesis**: This looks like an interaction between pytest 9 capture handling and the current Codex shell/WSL output capture path rather than an engine failure.
- **Resolution**: `pyproject.toml` now sets pytest `addopts = ["--capture=no"]`, and the book-integrity test asserts that the uv-driven pytest contract keeps capture disabled.
- **Verification**: The previously failing no-`-s` command now passes, and full `uv run pytest -q tests/engine_book` runs through the configured capture mode.
- **Status**: RESOLVED 2026-06-28

### Intermittent EB-10 forced-movement spatial-entered ordering in full-suite runs
- **Found**: 2026-06-28 during full engine-book verification after Chapter 16 Primal Champion expansion
- **Test file**: `tests/engine/test_combat_actions.py`
- **Error**: One `uv run pytest -s -q tests/engine_book` run failed `test_eb_10_021_forced_movement_traverses_terrain_without_step_costs` because the collected `SPATIAL_ENTITY_ENTERED` EFFECT positions included the pushed target's starting cell `(6, 5)` after the expected traversal positions `(7, 5)`, `(8, 5)`, `(9, 5)`, `(10, 5)`.
- **Root cause**: `EventQueue._store_event()` appended to `_all_events` and then sorted the same list by timestamp. `event_cursor()` and `iter_events_since()` use `_all_events` length and slicing as an append-stream cursor, so a late-registered event with an older timestamp could move pre-cursor events after the cursor and hide the newly registered event. EB-10-021 then observed a pre-cursor starting-cell `SPATIAL_ENTITY_ENTERED` event as though it happened after the cursor.
- **Resolution**: `_all_events` is now append-stable. `get_events_chronological()` returns a timestamp-sorted copy for chronological reads, while cursor-based APIs keep raw append-stream semantics. EB-04-013 pins this invariant.
- **Verification**: A focused reproducer now returns only the late appended event after the cursor, `uv run python examples/test_engine_book_event_lifecycle.py` passes, `uv run pytest -q tests/engine/test_event_lifecycle.py tests/engine/test_combat_actions.py tests/architecture/test_source_model_hygiene.py` passes 46/46, `uv run pyright dnd/core/events.py examples/test_engine_book_event_lifecycle.py examples/test_engine_book_core_actions_combat.py` reports 0 errors, a 300-iteration EB-10-021 stress loop passes, full `uv run pytest -q tests/engine_book` passes 341/341, and the direct Chapter 10 example script passes.
- **Status**: RESOLVED 2026-06-28

### Barbarian unarmored-defense shield example assumed shield with two-handed weapon
- **Found**: 2026-06-28 during Chapter 13 armor factory hygiene verification.
- **Test file**: `examples/test_barbarian_unarmored_defense.py`
- **Error**: `test_unarmored_defense_with_shield()` used a helper that always equipped a greataxe, then tried to equip a shield in the melee off hand. The old hard-blocking equipment policy raised `ValueError`; the current videogame policy would instead displace the two-handed melee weapon.
- **Hypothesis**: The legacy test intended to verify Unarmored Defense plus shield AC, not the hand-occupancy policy already pinned by EB-13-014.
- **Resolution**: The test helper now accepts `equip_greataxe=False`, and the shield-specific test uses that setup before equipping the shield.
- **Verification**: `uv run python examples/test_barbarian_unarmored_defense.py` passes.
- **Status**: RESOLVED 2026-06-28

### Combat-log SSE can publish an action log before the matching completion event
- **Found**: 2026-06-28 during Chapter 18 SSE combat-log ordering expansion
- **Test file**: `examples/test_engine_book_encounters_apis.py`
- **Error**: A live stream subscription received the Dash `combat_log` envelope before the Dash completion `game_event`. `EventQueue.phase_to(COMPLETION)` calls the combat-log callback before posting the completion event, and the event passed to the callback still has the previous phase UUID. `server.event_stream.DndEventStream._on_combat_log()` only checked whether that UUID was already indexed, so it published the log immediately instead of holding it until the completion event was stored.
- **Resolution**: `DndEventStream._on_combat_log()` now treats registered events as pending when the stored event is missing or its stored phase differs from the callback event phase. Pending log payloads are released when `_on_event()` publishes the matching completion event, and their event cursor is updated to the completion event cursor before SSE formatting.
- **Verification**: EB-18-018 proves a Dash combat log follows the Dash completion game event and that the SSE id uses the completion event cursor plus the combat-log cursor.
- **Status**: RESOLVED



### Orchestrator drain timeout causes commands to execute against wrong entity
- **Found**: 2026-02-25, PvP session (Match 1, Round 2)
- **Test file**: N/A (orchestrator/CLI issue, not game engine)
- **Error**: Before the Codex CLI migration, after a 45-second drain timeout killed the autonomous subprocess, buffered commands (e.g. `dodge`) could execute against the *next* entity in turn order instead of the intended entity. In the observed case, a `dodge` command meant for Skeleton Warlock was applied to Skeleton Archer after the turn auto-advanced.
- **Root cause**: Two problems:
  1. The subprocess could keep generating or flushing output after the orchestrator had already detected the turn end and moved on.
  2. Orphaned commands were routed through the agent CLI without validating that the command still belonged to the entity whose turn originally spawned the subprocess.
- **Impact**: Entity gets actions applied without spending action economy (Archer got Dodging for free). Turn log file for the affected entity is never created.
- **Resolution**: The orchestrator now builds `codex exec --json` invocations and injects an exact guarded command prefix into each turn prompt: `uv run python -m cli.agent --token ... --expect-entity ... <command>`. The agent CLI validates the expected entity UUID against the server's current active controlled entity before executing any game command, so stale buffered commands are rejected instead of being applied to the next turn's entity. The old `claude` player/session/controller surface was migrated to `codex`.
- **Verification**: `uv run pyright dnd/controller.py dnd/encounter.py server/session.py server/event_server.py cli/agent.py cli/orchestrator.py examples/test_engine_book_encounters_apis.py` passed with 0 errors. `uv run pytest -q tests/engine/test_encounter_apis.py tests/architecture/test_source_model_hygiene.py` passed 35/35. `uv run python examples/test_engine_book_encounters_apis.py` passed.
- **Status**: RESOLVED 2026-06-28

### Codex self-play metrics missed current stream command and token events
- **Found**: 2026-07-01 during a real Codex-vs-Codex sorcerer self-play run.
- **Test file**: N/A yet; observed in `game_logs/selfplay_sorcerer_smoke_2`.
- **Error**: The orchestrator completed a one-turn victory and the turn log contains multiple `command_execution` stream items plus a `turn.completed` usage payload, but `metrics.json` reports `game_actions: 0`, zero action timestamps, and zero token usage.
- **Resolution**: `cli/orchestrator.py` now handles the current `thread.started`, `item.started`, `item.completed`, and `turn.completed` Codex stream events. It records Codex thread IDs for resume, counts completed `cli.agent` command executions, records first-action time, counts agent messages, reads current usage fields such as `cached_input_tokens`, and writes current-schema command steps into trajectory logs.
- **Verification**: EB-18-029 proves current Codex item streams produce nonzero command metrics, token metrics, and trajectory steps. `uv run pytest tests/engine/test_encounter_apis.py -q` passes 35/35, and `uv run pyright cli/orchestrator.py tests/engine/test_encounter_apis.py` reports 0 errors.
- **Status**: RESOLVED 2026-07-01

### Published AI decision epoch was rejected as stale after its own control frame
- **Found**: 2026-07-02 during Sorcerer challenge validation against external enemy policy v4.
- **Test file**: `tests/manual/test_36_seamless_subjective_runtime.py`
- **Error**: Skeleton Warrior selected `Move -> (7, 7)` from a valid `turn_start` decision epoch, but `/ai/sessions/{session_id}/commands/execute` rebuilt a `snapshot` epoch after the decision-epoch control frame had advanced the observation cursor. The row was then rejected as `stale` even though no gameplay state had changed.
- **Resolution**: `server.event_server` now tracks the current published decision epoch per session and reuses it while it still matches the active actor, round, and turn. Epochs rotate when a real action boundary publishes a new epoch or when the turn is cleared.
- **Verification**: `test_published_epoch_survives_control_cursor_advancement` proves a command based on the published epoch is accepted after the control frame advances the cursor. Focused seamless runtime tests and pyright pass.
- **Status**: RESOLVED 2026-07-02

### Subjective observation forgets living enemies after line-of-sight closure
- **Found**: 2026-07-02 during Sorcerer challenge validation against external enemy policy v4.
- **Test file**: N/A yet; live artifact `/tmp/dnd_sorcerer_v4_iteration/008_close_door.json`.
- **Error**: After the Hero closed the central door, living Skeleton Archer and Skeleton Warrior disappeared from `living_enemies` and did not appear in `remembered_enemies`. Only the dead Warlock remained remembered, with `position: null`. When Warrior reopened the door, the living enemies reappeared as visible.
- **Hypothesis**: The observation projector builds known entity facts from current `observer.senses.entities`, but does not retain last-known facts for visible-before living enemies when blockers remove current visibility.
- **Additional evidence**: 2026-07-03 Sorcerer v5 challenge playtest reached turns where visible `living_enemies` became empty while Skeleton Warlock was still alive elsewhere. The operator surface fell back to frontier exploration instead of last-known enemy search, increasing tool calls and movement churn.
- **Additional evidence**: 2026-07-03 skeleton-side Barbarian validation showed the same failure through a door loop. When a skeleton closed the central door, the living Barbarian Hero dropped out of `living_enemies` and did not appear as remembered/last-known, so the next compact surface treated reopening the door as fresh exploration instead of a known enemy line-of-sight recovery.
- **Progress**: 2026-07-03 external enemy policy v7 consumed remembered enemy facts when present; the projector was subsequently changed to retain observer-local remembered facts.
- **Verification**: Focused remembered-living and remembered-death projection
  regressions both pass on 2026-07-24.
- **Status**: RESOLVED 2026-07-24.

### Subjective runtime creates excessive resync/subscription churn in short fights
- **Found**: 2026-07-02 during Sorcerer challenge validation against external enemy policy v4.
- **Test file**: N/A yet; live server log `/tmp/dnd_sorcerer_v4_iteration/server.log`.
- **Error**: One short fight produced `41` AI observation snapshots, `20` observation subscribe requests, `10` resync starts, `10` resync completions, and pending `BoundedSubscription.get()` task warnings on disconnect.
- **Hypothesis**: The hot runtime treats normal stream closure/sync boundaries too aggressively as resync conditions, and the SSE generator still leaves pending subscription tasks around some disconnect paths.
- **Additional evidence**: 2026-07-03 Barbarian validation after the epoch-cache fix removed stale command acks, but still produced `75` snapshots, `36` observation subscribe requests, `15` resync starts, `15` resync completions, and `26` pending subscription task warnings. This confirms the churn is independent of the false-stale bug.
- **Progress**: 2026-07-03 found and fixed a command-follow-up bug where the hot runtime treated the normal initial SSE `sync` envelope as a resync trigger before consuming replayed `COMMAND_RESULT` and follow-up `DECISION_EPOCH` frames. A follow-up Barbarian rerun completed without hanging, but still showed `3` stale command acks. Those were traced to server-side epoch clears: a late clear for the previous actor could erase the newer active actor epoch, causing the next snapshot to mint a different `snapshot` epoch for the same actor/round/turn. Epoch clear is now actor-aware and does not discard another actor's current epoch.
- **Additional evidence**: 2026-07-03 Sorcerer v5 challenge playtest confirmed the stale/resync fixes worked in a full game: `0` stale command acks and `0` resync starts/completions. The remaining runtime issue is now clearer: the same game still produced `133` snapshot requests, `102` observation subscriptions, and `85` pending `BoundedSubscription.get()` task warnings.
- **Additional evidence**: 2026-07-03 skeleton-side Barbarian validation completed after the door-boundary fix, but the final-run server-log slice still showed `249` snapshots, `72` observation subscriptions, and `87` pending subscription task warnings. The run had `0` debug `/available-actions` hits, so this is stream/materialization pressure rather than fallback action polling.
- **Additional evidence**: 2026-07-03 default-monster Barbarian attempt with policy v6 timed out before a winner and showed command-result latency around `5077 ms` p50 and `21047 ms` max in the collected enemy trace. The tactical policy needed improvement too, but the latency confirms runtime throughput remains a separate bottleneck.
- **Additional evidence**: 2026-07-03 Sorcerer v7 victory still produced `105` snapshots, `90` observation subscriptions, `75` pending subscription task warnings, and external-AI command-result latency around `2731 ms` p50 / `24178 ms` max. The terminal Codex watch hang was fixed separately, so this issue is now specifically stream churn and command latency.
- **Additional evidence**: 2026-07-04 in-process `skeleton_mark_focus_fire` self-play timing shows policy selection is tiny (`0.19 ms` average, `0.635 ms` max), while snapshot fetch/validation, dense epoch reduction, and command submission dominate the command-loop cost. This narrows the speed problem away from the behavior-tree selector itself.
- **Additional evidence**: 2026-07-04 `forced_movement_hazard_bridge` self-play shows the same shape after route tracing: policy averaged `0.179 ms` with `0.742 ms` max, while snapshot, reduction, and command submission still produced larger spikes (`337.237 ms`, `282.276 ms`, and `399.482 ms` max respectively).
- **Verification**: `test_runtime_command_followup_ignores_initial_stream_sync` now proves `sync -> command_result -> decision_epoch` completes without snapshot resync. `test_epoch_clear_for_previous_actor_does_not_invalidate_current_server_epoch` proves a clear for actor A does not invalidate actor B's current server epoch. A fresh full game has now separated the concerns: false stale/resync appears fixed, but snapshot/subscription volume and disconnect cleanup remain open.
- **Status**: RETIRED AS AN UNMEASURED HISTORICAL LEAD 2026-07-29. The focused
  sync/epoch and stream-cleanup regressions pass; the quantitative evidence was
  confined to removed `/tmp` logs and predates the canonical replication
  runtime. Reopen only with a checked-in deterministic load gate.

### Codex watch blocked after encounter end
- **Found**: 2026-07-03 during Sorcerer v7 default-monster playtest.
- **Test file**: `tests/manual/test_30_codex_takeover_tools.py`
- **Error**: The Sorcerer defeated all three skeletons, `/game/status` reported `encounter_active=false`, but `CodexToolClient.watch()` opened another observation subscription and waited indefinitely because no future controlled turn could arrive.
- **Resolution**: `CodexToolClient.watch()` now checks `/game/status` after the current brief. If the encounter is over, it returns `WatchResult(status="encounter_ended", event="encounter_ended")` without opening another stream.
- **Verification**: `test_codex_watch_returns_when_encounter_already_ended` proves no stream is opened after terminal status. The live ended Sorcerer server returned `encounter_ended` in `13.73 ms`.
- **Status**: RESOLVED 2026-07-03

### Sorcerer turn summaries are still too large
- **Found**: 2026-07-03 during Sorcerer v7 default-monster playtest.
- **Test file**: N/A yet; live artifact `/tmp/dnd_sorcerer_v7_default_monsters/000_play_summary.json`.
- **Error**: The largest compact Sorcerer turn summary still reached `50222` characters and `653` normalized action choices.
- **Hypothesis**: Spell-slot variants, scroll variants, multi-target rows, and position-targeted area rows are still being serialized too broadly even after variant grouping. The agent needs a tighter default summary plus expandable detail, not every legal row in the primary surface.
- **Status**: RETIRED AS AN UNMEASURED HISTORICAL LEAD 2026-07-29. The only
  cited artifact was under `/tmp` and is unavailable; reopen only with a
  checked-in current compact-surface size regression.

### Caster useful movement could require raw fallback when no retreat row existed
- **Found**: 2026-07-03 during skeleton-side v7 playtest against external Barbarian.
- **Test file**: `tests/manual/test_30_codex_takeover_tools.py`
- **Error**: Skeleton Warlock had spent its action and had useful movement rows toward the visible Hero, but because Warlock is a spacing-preferring caster and no retreat row existed, the recommendation list stayed empty while `meaningful_commands_remaining` was true. The driver used raw `fallback:useful_moves` three times.
- **Resolution**: Useful visible-enemy movement is now recommended when a caster prefers spacing but no retreat move exists. Retreat still wins when available.
- **Verification**: `test_codex_turn_summary_recommends_caster_closing_when_no_retreat_exists` covers the Warlock shape, and `test_codex_turn_summary_prefers_retreat_over_adjacency_for_spellcaster_without_offense` proves retreat priority remains intact.
- **Status**: RESOLVED 2026-07-03

### Autonomous ranged enemies closed after spending their pressure action
- **Found**: 2026-07-03 while reviewing the enemy-AI challenge goal after skeleton-side v7 playtesting.
- **Test file**: `tests/manual/test_35_subjective_external_ai.py`
- **Error**: The external enemy behavior tree could cast or attack, then use leftover movement to walk toward the visible Hero because generic visible-enemy pursuit ran after the pressure rows were no longer affordable. This made archers and warlocks easier to punish.
- **Resolution**: The external reducer now carries action-economy values from decision epochs. The behavior tree has a ranged-spacing branch before generic pursuit: spent ranged/caster actors retreat when a farther movement row exists, otherwise they hold range; melee actors still close.
- **Verification**: `test_ranged_enemy_retreats_after_spending_pressure_action`, `test_ranged_enemy_holds_spacing_after_spending_action_when_no_retreat_exists`, and `test_melee_enemy_still_closes_after_spending_action` cover the policy boundary.
- **Status**: RESOLVED 2026-07-03

### Barbarian operator surface could fall into torch-toggle utility loops
- **Found**: 2026-07-03 during Barbarian Hero playtest against external skeleton AI.
- **Test file**: `tests/manual/test_30_codex_takeover_tools.py`
- **Error**: The first Barbarian run hit the step limit with `90` commands because the turn summary had no recommendations but still reported `meaningful_commands_remaining=true`. Raw fallback then executed `56` torch toggles plus free potion rows while the encounter remained active.
- **Root cause**: Basic/utility self interactions were too broadly counted as meaningful. Dash, Disengage, Dodge, Reckless Attack, End Rage, torch toggles, and free consumables could keep the turn alive even when no tactical recommendation existed.
- **Resolution**: Dash is now recommended when no-contact exploration stalls with zero movement and an action remains. Frenzy/Reckless recommendations require living-enemy pressure. End Rage, torch toggles, and free consumables no longer keep spent turns alive.
- **Verification**: `test_codex_turn_summary_recommends_dash_for_no_contact_exploration_when_movement_spent` covers the Dash replacement, and `test_codex_turn_summary_end_rage_and_light_toggles_do_not_keep_spent_turn_alive` covers the spent-turn utility boundary. A fresh live validation completed with `0` torch toggles and Hero victory.
- **Status**: RESOLVED 2026-07-03

### Persistent-zone policy chooses direct damage before approach-lane control
- **Found**: 2026-07-13 during a read-only AI architecture review.
- **Test command**: `uv run pytest tests/manual/test_35_subjective_external_ai.py -q` (`1 failed, 116 passed`).
- **Failure**: `test_persistent_zone_policy_uses_guardian_on_approach_lane_before_damage` expects `choose_external_melee_command` to return `Guardian of Faith__slot_4`, but it returns `Magic Missile__slot_1`.
- **Resolution**: The duplicate reduced-state evaluator and this implementation-specific test were removed. Persistent zones and direct damage now compete through typed shared-policy proposals and utility evidence; no controller can fall back to the former ordered leaf stack.
- **Status**: SUPERSEDED 2026-07-14 by the single `PolicyHost` architecture. Persistent-zone utility still requires scenario-level evidence in the continuing self-play loop.

### Fast Move discovery has an incompatible paths-by-position type
- **Found**: 2026-07-13 during a read-only AI architecture review.
- **Command**: `uv run pyright dnd/entity.py dnd/core/base_actions.py`.
- **Failure**: `dnd/entity.py:3459` passes `paths_by_position` with type `DefaultDict[...] | dict[...]` to `_collect_fast_move_targets`, whose parameter is annotated `DefaultDict[...]`, producing `reportArgumentType`. Runtime tests were not failing.
- **Repeat**: The same sole diagnostic appeared while type-checking the typed AI routine and entity-composition changes with `uv run pyright dnd/entity.py ai/policy/routines.py ai/external/policy.py ai/external_melee_agent.py ai/external_selfplay.py ai/evaluation/artifacts.py ai/knowledge/deriver.py ai/external/state.py tests/engine/test_entity_composition.py tests/manual/test_45_policy_routines.py`.
- **Hypothesis**: The helper annotation is narrower than the actual branch result. Its read-only access may accept a `Mapping[Tuple[int, int], List[Tuple[int, int]]]` rather than requiring default-factory behavior.
- **Status**: RESOLVED 2026-07-13; `_collect_fast_move_targets` now accepts the read-only `Mapping` contract used by walking and swimming path maps. Focused Pyright reports zero errors.

### Dash ignores effective speed modifiers such as Barbarian Fast Movement
- **Found**: 2026-07-13 while reviewing the live level-5 Barbarian run in `ai/evidence/runs/20260713-phase4-double-door-dark-hunt-seed8675310.json`.
- **Live evidence**: `Validation Door Barbarian` had `Fast Movement` and an effective movement value of `40`, but `self|Dash|index=0` reported `Applied Dashing - gained 30ft extra movement`. An isolated reproduction starts at `40` and ends at `70`; speed-relative Dash should grant `40` and produce `80` available movement before movement costs.
- **Root cause**: `Dashing._apply()` reads `movement.get_base_modifier().value`, and `Dash._apply()` reports `action_economy.get_base_value("movement")`. Both return the immutable `30` base and omit the contextual `+10` Fast Movement modifier.
- **Coverage gap**: Existing tests prove ordinary 30-foot Dash and Fast Movement separately, but do not combine Dash with modified speed.
- **Resolution**: Dash now uses the explicit effective current-speed surface
  instead of the immutable base movement value.
- **Verification**: The focused modified-speed Dash regression passes on
  2026-07-24.
- **Status**: RESOLVED 2026-07-24.

### Resolved: Action-discovery manual test had stale optional target narrowing
- **Found**: 2026-07-14 during focused Pyright validation over touched files; reproduced on 2026-07-15 during focused type checking of action changes.
- **Test file**: `tests/manual/test_09_action_discovery_and_costs.py` (9 Pyright errors at lines 117, 282, 605, 611, and 623)
- **Command**: `uv run pyright dnd/actions.py tests/manual/test_09_action_discovery_and_costs.py`
- **Error**: The test passes optional `target_uuid` values to `Entity.get()` without narrowing at all five locations (`reportArgumentType`) and accesses `.name` on optional `Entity.get()` results at lines 282, 605, 611, and 623 (`reportOptionalMemberAccess`).
- **Scope**: The newly changed `dnd/actions.py` itself has no reported error; these diagnostics are pre-existing test typing issues unrelated to the action changes.
- **Hypothesis**: The readout paths should explicitly narrow each target UUID and entity lookup before member access.
- **Resolution**: The affected readout paths now explicitly require target
  UUIDs and entity lookups before accessing their typed members.
- **Verification**: `tests/manual/test_09_action_discovery_and_costs.py` passes
  all 30 runtime tests, and focused Pyright over the maintained manual
  typing-debt set reports zero errors.
- **Status**: RESOLVED 2026-07-29.

### EB-10-021 reuses an exhausted event iterator
- **Found**: 2026-07-13 during focused forced-movement verification.
- **Test command**: `uv run pytest tests/engine/test_combat_actions.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs`.
- **Failure**: The later `next(...)` lookup raises `StopIteration`, even though `forced_event` was found during the first pass over the same event sequence.
- **Cause**: `indexed_events = EventQueue.iter_events_since(cursor)` is a one-shot iterator. The `new_events = [...]` comprehension exhausts it, and the test later attempts to reuse `indexed_events` in `next(...)`.
- **Resolution**: The test materializes the event sequence once before its two
  searches.
- **Verification**:
  `tests/engine/test_combat_actions.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs`
  passes on 2026-07-24.
- **Status**: RESOLVED 2026-07-24.

### Entity fast-move helper has a narrow path-map annotation
- **Command**: `uv run pyright dnd/entity.py`.
- **Error**: Around `dnd/entity.py:3460`, a `DefaultDict[...] | dict[...]` value is passed to `_collect_fast_move_targets`, whose parameter accepts only `DefaultDict[...]`, producing `reportArgumentType`.
- **Hypothesis**: The helper parameter annotation is narrower than its actual callers require; it likely needs a read-only mapping-compatible type rather than guaranteed `DefaultDict` behavior.
- **Status**: RESOLVED 2026-07-13; duplicate of the entry above. The helper now accepts `Mapping`, and focused Pyright reports zero errors.

### Live-replication tutorial fixtures hard-coded stale EventQueue cursors
- **Found**: 2026-07-14 during focused live-replication stream testing.
- **Test file**: `tests/manual/test_25_live_replication_streams.py` (`6` failures).
- **Failure**: Tutorial output originally hard-coded initial EventQueue cursor `52` and post-attack cursor `78`. The sensory-prefilter repair first reduced those totals to `48` and `74`; the later EventQueue identity repair removed exact-object duplicate registrations and established the current unique-version totals of `42` and `68`.
- **Root cause**: The old `52`-event setup included one empty, `paths_dirty`-only `SENSORY_UPDATE` lifecycle (four phases). `server/live_replication.py:65-67` creates both actors before the explicit senses initialization, and the current spatial prefilter in `dnd/blocks/sensory.py:531-539` now rejects the irrelevant setup spatial event before taking a senses snapshot or emitting that lifecycle. No observable facts were lost: `ai/observation/projector.py:1362-1382` already treats path dirtiness by itself as non-subjective.
- **Preserved behavior**: Fanout counts remain correct, and the attack still advances the cursor by exactly `26` events.
- **FOV check**: Bounded and unbounded shadowcast produced the same cursor at each stage, so the FOV optimization was not the source of either count correction.
- **Resolution**: The deterministic tutorial readouts now expect `42`/`68`. Event history contains unique event versions, the attack still advances by exactly `26` events, and the behavioral assertions continue to prove the meaningful attack delta and fanout counts.
- **Status**: RESOLVED 2026-07-14; `tests/manual/test_25_live_replication_streams.py` passes all 8 focused tests.

### Standalone spotted and hazard combat logs may not wake subjective observation sessions
- **Found**: 2026-07-14 while tracing standalone combat-log delivery into initialized subjective sessions.
- **Affected logs**: `ENTITY_SPOTTED` and `HAZARD_DETECTED` are emitted through `EventQueue.push_combat_log()` from `dnd/entity.py:3215-3234` and `dnd/blocks/sensory.py:1030-1083`.
- **Failure risk**: `EventQueue.push_combat_log()` creates an unregistered completion (`use_register=False`) and invokes only the combat-log callback (`dnd/core/events.py:979-995`). The encounter appends the entry and notifies encounter combat-log listeners (`dnd/encounter.py:804-835`), but the subjective projector is attached only through `EventQueue.add_on_event_callback()` and updates initialized sessions only when a registered completion arrives (`ai/observation/projector.py:146-149`, `ai/observation/projector.py:207-223`). A standalone spotted/hazard log can therefore advance the encounter combat-log history without publishing a subjective observation frame or waking that session live.
- **Root cause**: Subjective combat-log history is imported from the encounter when a projection cache first bootstraps (`ai/observation/projector.py:653-662`); after initialization, combat-log patches are produced while iterating registered EventQueue completions (`ai/observation/projector.py:688-715`, `ai/observation/projector.py:748-825`). There is no corresponding encounter combat-log listener for standalone entries.
- **Resolution**: `EventQueue.push_combat_log()` now marks its unregistered carrier explicitly as a standalone log boundary. The subjective projector attaches to the existing encounter combat-log listener, flushes pending registered completions first, filters the entry per session, and publishes one cursor-ordered `COMBAT_LOG` observation frame. Registered event logs remain owned exclusively by EventQueue completion projection. Spotted/hazard producers now include perceiver metadata, and spotted logs include observer-scoped identity grants so synchronous filtering preserves only the identity actually established by that observer.
- **Verification**: `tests/manual/test_28_subjective_observation_stream.py` covers live wakeup, replay equality, unchanged EventQueue cursor, exact combat-log cursor, observer filtering, target identity, and registered-log non-duplication.
- **Status**: RESOLVED 2026-07-14; all 25 focused subjective observation tests pass.

### Server action protocol boundaries have incompatible model and collection types
- **Command**: `uv run pyright server/event_server.py`.
- **Errors**: Around `server/event_server.py:3015`, a `dnd.core.base_actions.ActionOutcomeProfile` is passed where `ai.protocol.control.ActionOutcomeProfile` is expected. Around `server/event_server.py:3897`, a `Sequence[str]` is passed where `ExecuteByIndexRequest` requires `List[str]`.
- **Required correction**: Add deliberate protocol conversion/copying at both boundaries instead of relying on structurally similar models or broader collection types.
- **Resolution**: The server now converts the engine outcome profile into the protocol model and materializes the target UUID sequence as the request model's list type.
- **Status**: RESOLVED 2026-07-14; focused Pyright over `server/event_server.py` is clean.

### Potion of Haste contradicts its no-lethargy contract
- **Found**: 2026-07-14 during a focused rules audit.
- **Source**: `dnd/items/test_items.py:1474-1479` says `DrinkHastePotionAction` has no lethargy, but `dnd/items/test_items.py:1512-1516` creates `HasteEffect` without overriding its effective `apply_lethargy=True` default (`dnd/spells/transmutation.py:624`). On expiry/removal, `dnd/spells/transmutation.py:773-784` therefore applies one round of `Incapacitated`.
- **Required decision**: Choose one explicit ruleset for the potion: retain lethargy and correct the action contract, or disable lethargy in the potion-created effect. Do not silently reconcile the mismatch.
- **Resolution**: The potion contract explicitly retains Haste lethargy and
  the created effect carries the matching behavior.
- **Verification**:
  `tests/manual/test_11_equipment_inventory_and_items.py::test_magic_condition_potions_preserve_magical_origin_and_haste_lethargy`
  passes.
- **Status**: RESOLVED 2026-07-24.

### Potion-created spell effects omit the magical condition tag
- **Found**: 2026-07-14 during a focused rules audit.
- **Source**: Potion creation omits `ConditionTag.MAGICAL` for `GreaterInvisibilityEffect` at `dnd/items/test_items.py:1097-1100` and `HasteEffect` at `dnd/items/test_items.py:1512-1516`, so both inherit the empty tag set from `dnd/core/base_conditions.py:306-308`. Spell creation explicitly supplies the tag at `dnd/spells/illusion.py:860-864` and `dnd/spells/transmutation.py:843-848`.
- **Impact**: Identical named effects differ under antimagic-style and other tag-filtered behavior solely by whether a potion or spell created them.
- **Resolution**: Potion-created Greater Invisibility and Haste effects now
  carry `ConditionTag.MAGICAL`.
- **Verification**:
  `tests/manual/test_11_equipment_inventory_and_items.py::test_magic_condition_potions_preserve_magical_origin_and_haste_lethargy`
  passes.
- **Status**: RESOLVED 2026-07-24.

### Engine-book integrity metadata and documentation lag current coverage
- **Found**: 2026-07-15 while running unrelated focused validation; consolidated rerun of the four existing engine-book integrity issues above.
- **Command**: `uv run pytest tests/architecture/test_source_model_hygiene.py -q`
- **Result**: 27 integrity tests passed and four failed: parity rows are missing for `EB-11-022`, `EB-11-023`, `EB-12-020`, `EB-12-021`, and `EB-12-022`; outline ranges stop before Chapter 11 `023` and Chapter 12 `022`; the manifest expects missing `server/event_server.py::timing_middleware`; and `advance_encounter` lacks the manifest-required Google-style `Args:` block.
- **Hypothesis**: The integrity metadata and documentation lag the current code and tests.
- **Resolution**: Live code/test inventories and docstrings were updated during
  the canonical transport cleanup. The remaining inability to validate parity
  rows and outline ranges is now tracked by the later, more precise
  **Engine-book source fixtures are absent** entry.
- **Status**: SUPERSEDED 2026-07-23.

### Resolved: Spellcasting core test had Optional UUID typing errors
- **Found**: 2026-07-15 during focused Pyright validation of combat-log, base-action, and Eldritch Blast outcome-profile changes.
- **Command**: `uv run pyright tests/manual/test_13_spellcasting_core.py`
- **Error**: Six pre-existing Optional/UUID diagnostics occur at the current lines 369, 414, 620, and 623. Optional UUIDs reach `BaseObject.get()`, and optional event or lookup results are accessed through `.value` or `.name` without narrowing.
- **Scope**: The new Eldritch Blast test is not implicated. Focused runtime tests pass, and focused Pyright over the changed production, epoch, and policy files reports zero errors.
- **Hypothesis**: Narrow the optional event fields, UUIDs, and lookup results explicitly in the tutorial readout paths.
- **Resolution**: The tutorial now narrows optional event fields, UUIDs, and
  registry lookups before accessing values or names.
- **Verification**: `tests/manual/test_13_spellcasting_core.py` passes all 17
  runtime tests, and focused Pyright over the maintained manual typing-debt
  set reports zero errors.
- **Status**: RESOLVED 2026-07-29.

### Policy host consumer-parity fixture omits the current conditional-target trace node
- **Found**: 2026-07-15 during focused policy-host test validation.
- **Test**: `tests/manual/test_48_policy_host.py::test_policy_host_exposes_one_identical_decision_and_trace_to_every_consumer`
- **Failure**: The expected policy trace omits the current `ConditionalTargetEffects` node produced by the policy host, so the asserted trace no longer matches the production trace.
- **Resolution**: The fixture now includes the canonical conditional-target
  trace node.
- **Verification**:
  `tests/manual/test_48_policy_host.py::test_policy_host_exposes_one_identical_decision_and_trace_to_every_consumer`
  passes on 2026-07-24.
- **Status**: RESOLVED 2026-07-24.

### Resolved: Counterspell violated cast-cost, spell-level, and event-history contracts
- **Found**: 2026-07-15 during current AI protocol work on Counterspell interruption outcomes.
- **Original cast costs**: When Counterspell cancels the execution event, `BaseAction.apply()` returns at `dnd/core/base_actions.py:1179-1183`; `_apply_costs()` at `dnd/core/base_actions.py:1261-1266` is never reached, so the original caster spends neither the action nor the spell slot.
- **Cantrips**: `dnd/spells/abjuration.py:704-708` treats cast level `0` as ineligible and returns before Counterspell can react, incorrectly ignoring cantrips.
- **Minimum slot**: `dnd/spells/abjuration.py:710-716` searches from the incoming spell level, so a level-1 or level-2 spell can consume an illegal level-1 or level-2 Counterspell slot instead of enforcing Counterspell's minimum level-3 slot.
- **Duplicate cancel history**: `Event.cancel()` posts the CANCEL version at `dnd/core/events.py:460-477`, then the handler dispatcher appears to store the same canceled event UUID again at `dnd/core/events.py:1127-1151`.
- **Resolution**: `Event.canceled_from_phase` now distinguishes declaration rejection from execution interruption; `SpellAction` settles its serialized action and selected-slot costs only for the committed execution case. Counterspell accepts level-zero cantrips, enforces a minimum level-3 reaction slot, and emits a typed `CounterspellReactionEvent` plus subjectivity-filtered interruption log. Handler-produced event versions now use collision-safe identity, while exact-object re-registration is idempotent.
- **Verification**: `tests/manual/test_50_counterspell_engine_contract.py` covers automatic and checked interruption, failed checks, upcasts, declaration cancellation, event-history identity, reaction logs, and hidden-reactor redaction. Related event lifecycle, spell-family, subjective-observation, self-play, and Pyright checks pass.
- **Status**: RESOLVED on 2026-07-15.

### Forced-movement focused test reuses an exhausted event iterator
- **Found**: 2026-07-15 during focused Counterspell/EventQueue UUID-idempotency validation.
- **Test**: `tests/engine/test_combat_actions.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs` failed at approximately line 561; 24 other tests passed.
- **Failure**: The test consumes `EventQueue.iter_events_since(cursor)` into `new_events`, then calls `next(...)` on the same exhausted iterator, raising `StopIteration`.
- **Status**: SUPERSEDED 2026-07-24 by **EB-10-021 reuses an exhausted event
  iterator**, whose correction and passing regression are recorded above.

### EB-13-008 second potion use returns no result
- **Found**: 2026-07-15 while auditing unrelated Counterspell item-charge behavior.
- **Test**: `tests/engine/test_items_inventory_equipment.py::test_eb_13_008_consumable_use_actions_consume_charges_and_stacks`.
- **Failure**: The second `execute_use_action()` call returns `None`, failing the assertion that the second potion use succeeds and consumes the final stack item.
- **Status**: SUPERSEDED 2026-07-24 by **Stacked healing potion test attempts
  two bonus-action uses in one turn**, now resolved by advancing to a second
  legal turn before the final stack use.

### Flame Strike applies its radiant component as fire damage
- **Found**: 2026-07-15 while adding execution-honest spell outcome contracts for subjective AI.
- **Source**: `dnd/spells/evocation.py:3701-3725` rolls separate fire and radiant components and preserves both in the completion log, but combines their totals and calls `receive_damage(..., DamageType.FIRE, ...)` once.
- **Impact**: Fire resistance, vulnerability, or immunity is applied to the radiant component as well, while the combat log and intended spell contract still describe two damage types. A truthful AI outcome profile cannot currently agree with both HP mutation and the emitted log.
- **Required correction**: Apply the two typed damage components independently while preserving save-for-half semantics and coherent aggregate logging, with focused resistance/immunity tests.
- **Resolution**: Flame Strike applies fire and radiant as independent typed
  components.
- **Verification**:
  `tests/manual/test_134_cleric_batch1_legacy_contract.py::test_flame_strike_applies_fire_and_radiant_as_typed_components`
  passes.
- **Status**: RESOLVED 2026-07-24.

### Chill Touch ignores modified spell critical thresholds
- **Found**: 2026-07-15 while adding execution-honest spell outcome contracts for subjective AI.
- **Current source**: Chill Touch execution now uses the shared spell-attack
  resolver and therefore honors the caster's modified spell critical
  threshold. Its actor-side outcome profile still hard-codes threshold `20`.
- **Impact**: Planning/evidence can disagree with execution for a caster whose
  spell critical threshold is modified.
- **Required correction**: Derive the outcome profile from the same threshold
  as execution and add a focused modified-threshold contract test.
- **Resolution**: The outcome profile and execution share the caster's spell
  critical threshold.
- **Verification**:
  `tests/manual/test_13_spellcasting_core.py::test_chill_touch_profile_and_execution_share_spell_critical_threshold`
  passes.
- **Status**: RESOLVED 2026-07-24.

### EB-12-018 expects the pre-cast level-3 spell-slot count
- **Found**: 2026-07-15 during focused sensory-indexing validation.
- **Test**: `tests/engine/test_senses_light_stealth.py::test_eb_12_018_aoe_preview_hides_hidden_entities_but_execution_hits_them` fails at approximately line 774.
- **Failure**: The test expects `spell_slot_3 == 2` after a level-5 caster successfully casts Fireball.
- **Reproduction**: The exact focused test reproduces the failure. `create_caster` initializes the level-5 character with `full_caster_spell_slots_for_level(5)`, which provides two level-3 slots. One valid Fireball cast correctly consumes one slot, leaving `spell_slot_3 == 1`.
- **Hypothesis**: The assertion is stale; the spell behavior and action cost are correct.
- **Status**: SUPERSEDED 2026-07-24 by **Chapter 12 Fireball visibility test
  observes an unexpected level-3 slot count**, now resolved by correcting and
  strengthening the stale maintained assertion.

### Resolved: Seamless subjective-runtime test doubles did not match Starlette interfaces
- **Found**: 2026-07-15 during focused Pyright validation for unrelated subjective-runtime work.
- **Command**: `uv run pyright tests/manual/test_36_seamless_subjective_runtime.py`
- **Current result**: A focused 2026-07-24 Pyright run reports `10` errors,
  including the existing request/response/async-stream protocol mismatches and
  two newer accesses to `.closed` on a telemetry object that does not declare
  that member.
- **Hypothesis**: The test doubles and response annotations model only the runtime behavior used by the tests, but their declared types do not conform to the corresponding Starlette request, response, and async-stream interfaces.
- **Resolution**: The test doubles now implement the Starlette request,
  response, and async-stream surfaces they exercise, and telemetry probes
  declare the members asserted by the tests. The missing-engine-event
  regression also patches the canonical action-dispatch seam.
- **Verification**:
  `tests/manual/test_36_seamless_subjective_runtime.py` passes all 49 runtime
  tests, and focused Pyright reports zero errors.
- **Status**: RESOLVED 2026-07-29.

### Resolved: Policy-host fixtures used a Pydantic flat constructor shape invisible to Pyright
- **Found**: 2026-07-15 during focused Pyright validation for unrelated policy investigation.
- **Command**: `uv run pyright ai/policy/routines.py tests/manual/test_48_policy_host.py`
- **Result**: `ai/policy/routines.py` reports no errors; `tests/manual/test_48_policy_host.py` reports 177 construction errors.
- **Representative errors**: At line 1519, Pyright reports that `ActionAffordance(...)` is missing required parameter `source`; lines 1521-1527 then report no parameters named `bucket`, `template_name`, `display_name`, `action_category`, `target_type`, `can_afford`, or `cost`. The same pattern recurs in later fixture constructors, including around lines 1646 and 1752.
- **Hypothesis**: `ActionAffordance` statically declares the canonical factored `source: ActionSourceDefinition` field, while its Pydantic `mode="before"` validator accepts and factors the legacy flat input shape at runtime. Pyright sees only the canonical constructor signature. Tests should use the factored constructor or a typed fixture/factory (or deliberately validate a mapping) rather than relying on runtime-only input normalization.
- **Resolution**: The fixtures now construct the canonical factored source
  model instead of relying on the runtime-only flat-input normalizer.
- **Verification**: `tests/manual/test_48_policy_host.py` passes all 54 runtime
  tests, and focused Pyright over the maintained manual typing-debt set reports
  zero errors.
- **Status**: RESOLVED 2026-07-29.

### Ranged spell attacks did not receive Threatened disadvantage
- **Found**: 2026-07-16 during Rotation 13 in `standard_skeleton_doors`.
- **Observed behavior**: Validation Sorcerer at `(7, 12)` cast Scorching Ray against the adjacent Validation Skeleton Warrior at `(7, 11)`. All four spell-attack logs recorded `advantage_status=none`, `advantage_breakdown=[]`, and `is_threatened=false`.
- **Expected ruleset behavior**: In the chosen BG3/videogame ruleset, being Threatened imposes disadvantage on ranged attack rolls, including ranged spell attacks.
- **Evidence**: `ai/evidence/direct_codex_runs/20260716T150526_870617_0000-standard_skeleton_doors-direct-codex-bbfbd73d.json` retains the subjective run and engine-rule annotation.
- **Cause**: Spell subclasses rolled directly from `spell_attack_bonus()` and bypassed the shared ranged-attack consequence path. `SpellEvent` also lacked a field through which combat logs could retain the threat state.
- **Resolution**: `SpellAction.resolve_spell_attack()` now owns spell-attack propagation, ranged Threatened disadvantage, spell-specific advantage modifiers, d20 resolution, and typed result evidence. Every attack-roll spell uses it; actor-side outcome profiles apply the same rule; `SpellEvent` forwards `is_threatened` into `AttackLogData`.
- **Verification**: The adjacent-hostile regression passes, `tests/manual/test_14_spell_families.py` reports `14 passed`, `tests/engine/test_spell_families.py` reports `46 passed`, the existing weapon-threat contract passes, and touched production files report zero Pyright errors.
- **Status**: RESOLVED 2026-07-16.

### External self-play exact-policy assertion expects Hold Person
- **Found**: 2026-07-17 during focused arena-factory validation.
- **Reverified**: 2026-07-24 during the D80 semantic coverage audit.
- **Selector**: `tests/manual/test_39_ai_validation_harness.py::test_external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands`
- **Failure**: The second command is `Scorching Ray__slot_3`, while the test requires `Hold Person__slot_2`; execution therefore fails before reaching the held-Barbarian assertions.
- **Cause**: The exact-policy assertion was stale after typed scoring evolved.
  Hold Person remains legal, affordable, and tagged `control.hard`; its
  structured target-effect proposal scores `17.25` from disclosed action
  denial, while level-3 Scorching Ray scores `160.23` from disclosed expected
  damage, resource cost, and action economy after the transformation.
- **Resolution**: The real self-play regression now preserves the semantic
  integration contract without pinning one spell: the transformation and
  damaging/control follow-up must both execute, the Sorcerer must yield the
  turn, and the Barbarian must then execute movement and multiple real attacks
  through its distinct session and epoch.
- **Verification**: The focused selector passes with `1 passed`.
- **Status**: RESOLVED 2026-07-24; test-only stale golden correction.

### Policy host advances memory for an accepted but canceled action
- **Found**: 2026-07-18 during focused policy-host validation for unrelated work.
- **Command**: `uv run pytest tests/manual/test_48_policy_host.py -q`
- **Test**: `tests/manual/test_48_policy_host.py::test_policy_host_does_not_advance_memory_for_accepted_canceled_action`
- **Failure**: `PolicyHost.record_result()` returns `memory_advanced=True` for `CommandResultStatus.ACCEPTED` with `ActionResolutionStatus.CANCELED`, while the test expects `False` because the command produced no gameplay effect.
- **Scope**: The other 52 tests in `tests/manual/test_48_policy_host.py` passed.
- **Likely area**: Policy-host command-result correlation and memory advancement logic, specifically the branch that interprets command acceptance independently from the action's terminal canceled resolution.
- **Cause**: `record_result()` correctly retained the canceled row and semantic
  family for same-turn reranking, but included those failure-suppression fields
  in the calculation of `memory_advanced`. Transport acceptance therefore
  looked like committed gameplay progress even though the action resolution
  was `CANCELED`.
- **Resolution**: Cancellation suppression remains in actor policy memory, but
  it no longer counts as gameplay intention or routine advancement. The exact
  regression now asserts the accepted-canceled reason, `memory_advanced=False`,
  no routine progress, and retained row/semantic suppression; the routine
  regression carries the same distinction.
- **Verification**: Both focused policy selectors pass (`2 passed`);
  `tests/manual/test_48_policy_host.py` passes (`54 passed`) and
  `tests/manual/test_45_policy_routines.py` passes (`16 passed`). Focused
  Pyright over the changed production surfaces and maintained regressions
  reports `0 errors`.
- **Status**: RESOLVED 2026-07-24

### Spell Studio targeting smoke uses a stale numeric-input locator
- **Found**: 2026-07-20 while reproducing the existing NeuroClient smoke failure.
- **Command**: `npm run studio:targeting-smoke` from `/home/tommaso/Dev/NeuroClient/app`.
- **Observed output**: The process exited `1` after `8.19s` with `ok: false`, no `pageerror`, and correct target toggle/removal facts. The final fact reported `projectileSpeed: "18"` instead of the asserted `"220"`; the remaining console output was limited to Chromium WebGL `ReadPixels` performance warnings.
- **Hypothesis**: The harness's positional selector `input[type='number']:nth(1)` is stale and now selects the target-distance input, whose production control correctly clamps values to `18`, rather than the timeline's projectile-speed input. The elapsed time comes from navigation, studio readiness, fixed waits, screenshot capture, and browser teardown; no harness timeout fired.
- **Status**: RETIRED AS AN UNMEASURED HISTORICAL LEAD 2026-07-29. The mutable
  external UI no longer reproduces this locator failure; reopen only with a
  pinned, self-starting semantic-selector regression.

### External AI start-human response reports `started` instead of `waiting_for_human`
- **Found**: 2026-07-21 during focused external-AI subprocess validation.
- **Reverified**: 2026-07-23 by `tests/manual/test_23_standard_arena_game_modes.py::test_start_human_mode_creates_ai_session_and_waits_for_player_join`; the response still reports `status == "started"` where the test requires `"waiting_for_human"`.
- **Command**: `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- **Test**: `tests/manual/test_29_external_ai_subprocess.py::test_start_human_creates_ai_session_and_spawns_once`
- **Assertion**: The `/simulation/start-human` response payload should report `status == "waiting_for_human"`.
- **Observed behavior**: The endpoint currently reports `status == "started"`.
- **Scope**: The other three tests in `tests/manual/test_29_external_ai_subprocess.py` passed.
- **Hypothesis**: This is a stale server-start response contract or test expectation outside the Codex representation work.
- **Resolution**: Removed the `/simulation/start-human` response override that
  replaced the authoritative `advance_encounter()` status with the literal
  `"started"`; the endpoint now preserves `waiting_for_human` and its actor
  boundary from `AdvanceEncounterResult`.
- **Verification**: The focused start-human arena selector and external-AI
  subprocess contract pass with the semantic status restored.
- **Status**: RESOLVED 2026-07-23.

### Session API readout fixture omits the available `Shove` action
- **Found**: 2026-07-21 during focused session API contract validation.
- **Command**: `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q`
- **Test**: `tests/manual/test_18_sessions_api_client_contract.py::test_state_current_turn_and_available_actions_payloads`
- **Expected fixture**: The available-action readout includes `Attack_MELEE_MAIN` and `Attack_RANGED_MAIN` but omits `Shove`.
- **Observed behavior**: The actual action names include `Attack_MELEE_MAIN`, `Attack_RANGED_MAIN`, and `Shove`.
- **Scope**: The other eight tests in `tests/manual/test_18_sessions_api_client_contract.py` passed.
- **Hypothesis**: The expected-output fixture is stale; this does not appear to be a Codex representation regression.
- **Resolution**: Refreshed the action-menu readout to include the canonical `Shove` action while migrating the same test to the canonical subjective bootstrap.
- **Verification**: `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q` reports `8 passed`; focused Pyright is clean.
- **Status**: RESOLVED 2026-07-23

### Hosted-worker status test expects the obsolete three-field payload
- **Found**: 2026-07-21 during focused player-identity and persistent-character regression validation.
- **Reverified**: 2026-07-22 during focused subjective combat-log validation; the same exact-payload assertion remains stale.
- **Command**: `uv run pytest tests/manual/test_109_hosted_game_runtime.py -q`
- **Test**: `tests/manual/test_109_hosted_game_runtime.py::test_hosted_worker_uses_private_socket_and_stops_process_group`
- **Failure**: The test compares `/game/status` to exactly `{"active": false, "game": null, "sessions": []}`. The current typed standalone status contract also includes `active_entity_uuid`, `creation`, `encounter_active`, and `game_id`.
- **Hypothesis**: The worker and endpoint are healthy; the exact dictionary fixture predates the expanded reconnect/observation status contract and should assert the current typed model or only the fields relevant to worker lifecycle.
- **Scope**: This drift comes from the earlier status-contract expansion; the subjective combat-log work does not change the hosted status route, model, or assertion.
- **Resolution**: Updated the exact assertion to the canonical inactive payload `{"active": False, "game_id": None, "encounter_active": False, "active_entity_uuid": None, "sessions": [], "creation": None}`.
- **Verification**: `uv run pytest tests/manual/test_109_hosted_game_runtime.py -q` reports `7 passed`.
- **Status**: RESOLVED 2026-07-22; only the stale test expectation changed.

### Session action readout omits the chosen BG3 Shove
- **Found**: 2026-07-22 during focused session API validation.
- **Test**: `tests/manual/test_18_sessions_api_client_contract.py::test_state_current_turn_and_available_actions_payloads`
- **Failure**: The stale exact readout expects only `Attack_MELEE_MAIN` and `Attack_RANGED_MAIN`; current available actions correctly also include the chosen BG3 `Shove`.
- **Resolution**: Updated the exact command-discovery readout to include `Shove`; no production route or compatibility behavior was added.
- **Verification**: The complete session API client contract file reports `8 passed`, and focused Pyright reports zero errors.
- **Status**: RESOLVED 2026-07-23

### NeuroClient event-sidebar build fails on unused imports
- **Found**: 2026-07-22 during reconnect-history validation.
- **Command**: `npm run build` from `/home/tommaso/Dev/NeuroClient/app`.
- **Failure**: TypeScript reports TS6196/TS6133 in `src/ui/eventSidebar.ts` for unused `ActionLogData`, `AttackLogData`, several other combat-log data type imports, and `pinTileInspector` introduced by concurrent work.
- **Current finding**: The cited unused imports are no longer present in the
  current NeuroClient source. No frontend build was run during this backend
  audit because concurrent UI work owns that tree.
- **Status**: RETIRED AS STALE 2026-07-29. The cited imports no longer exist;
  any future frontend build failure requires its own exact current gate.

### Arena-mode inactive status omits the expected `game` field
- **Found**: 2026-07-22 during independent clean-HEAD arena/server-boundary validation.
- **Reverified**: 2026-07-23 during the objective-diagnostics route cutover; the same exact selector still raises `KeyError: 'game'` before any diagnostics assertion runs.
- **Selector**: `tests/manual/test_23_standard_arena_game_modes.py::test_arena_mode_exposes_local_client_readers_and_joined_start`
- **Failure**: The test raises `KeyError: 'game'` while reading the inactive `/game/status` response, which it expects to include `game: None`; execution stops before the joined-game start assertions.
- **Reproduction**: The exact selector fails the same way from a fresh `git archive HEAD`, independently of the current dependency migration.
- **Hypothesis**: The inactive arena status response and the local-client reader contract have drifted on whether the optional `game` field is always present.
- **Resolution**: The test now consumes the canonical typed
  `StandaloneGameStatusResponse.game_id` field instead of the removed untyped
  `game` alias; no compatibility field was restored.
- **Verification**: `tests/manual/test_23_standard_arena_game_modes.py`
  reports `6 passed`.
- **Status**: RESOLVED 2026-07-23.

### EB-18-022 mapeditor load treats a typed directional-block model as a mapping
- **Found**: 2026-07-22 during full Chapter 18 regression validation for unrelated architecture refactoring.
- **Command**: `uv run pytest tests/engine/test_encounter_apis.py -q`
- **Test**: `tests/engine/test_encounter_apis.py::test_eb_18_022_mapeditor_save_load_roundtrip_restores_entity_free_state`
- **Failure**: Map loading reaches `_restore_directional_tile_state()` and calls `.items()` on an `APIDirectionalBlockMap` at `server/mapeditor_support.py:532`, raising `AttributeError: 'APIDirectionalBlockMap' object has no attribute 'items'`.
- **Static corroboration**: Pyright flags the same invalid `.items()` access at that production line.
- **Scope**: The full Chapter 18 file reported 31 passed and 2 failed; the other failure is EB-18-013 below.
- **Resolution**: `_restore_directional_tile_state()` now serializes the typed
  `APIDirectionalBlockMap` with `model_dump()` before iterating its directional
  flags, preserving the cold DTO boundary without treating the model as a raw
  mapping.
- **Verification**: `tests/engine/test_encounter_apis.py`
  reports `33 passed`, including EB-18-022, and the final scoped Pyright run is
  clean.
- **Status**: RESOLVED 2026-07-23.

### EB-18-013 invalid-player error supplies duplicate session context
- **Found**: 2026-07-22 during full Chapter 18 regression validation for unrelated architecture refactoring.
- **Command**: `uv run pytest tests/engine/test_encounter_apis.py -q`
- **Test**: `tests/engine/test_encounter_apis.py::test_eb_18_013_session_and_game_errors_report_valid_sessions_and_entities`
- **Failure**: The invalid `player_type` branch passes `valid_player_types` explicitly to `_session_http_exception()`, while `_session_http_exception()` also expands `_session_context()` containing the same key at `server/event_server.py:1297`. Python raises `TypeError` for the duplicate `valid_player_types` keyword before the intended structured HTTP error can be returned.
- **Scope**: The full Chapter 18 file reported 31 passed and 2 failed; the other failure is EB-18-022 above.
- **Resolution**: `_session_http_exception()` now merges shared and call-specific correction context before forwarding it, and `/session/create` no longer redundantly supplies `valid_player_types`.
- **Verification**: `tests/manual/test_18_sessions_api_client_contract.py::test_invalid_session_player_type_returns_structured_400` passes and asserts the exact correction payload; focused Pyright reports zero errors.
- **Status**: RESOLVED 2026-07-23.

### Engine-book source fixtures are absent
- **Found**: 2026-07-22 during focused architecture-refactor validation; expanded and reverified 2026-07-23 during integrity cleanup.
- **Commands**:
  - `uv run pytest tests/architecture/test_source_model_hygiene.py::test_engine_book_required_files_exist tests/architecture/test_source_model_hygiene.py::test_every_engine_book_test_function_has_a_parity_matrix_row tests/architecture/test_source_model_hygiene.py::test_parity_matrix_rows_reference_existing_engine_book_tests tests/architecture/test_source_model_hygiene.py::test_outline_book_example_ranges_match_executable_tests tests/architecture/test_source_model_hygiene.py::test_goal_records_uv_pytest_parity_requirement -q`
  - `uv run pytest tests/engine_book/test_architecture_surface_audit.py -q`
- **Result**: The selected integrity checks report `5 failed` because `engine_book/goal.md`, `engine_book/outline.md`, and `engine_book/parity_matrix.md` cannot be read; the audit suite reports `3 failed` because `engine_book/architecture_surface_audit.md` is absent. The entire `engine_book/` source-documentation directory is missing in this workspace, while its executable tests remain under `tests/engine_book/`.
- **Hypothesis**: The documentation source tree was omitted from or removed before the current refactor. These are missing authoritative artifacts, not failures caused by the transport/API cleanup; reconstructing their contents from test expectations would fabricate project documentation.
- **Contract note**: Any authoritative restoration of the audit must preserve the migrated `server.agent_protocol` and `server.agent_runtime` surfaces rather than restoring the removed `ai.protocol` package.
- **Resolution**: The book project is abandoned. Its prose, parity, source-link,
  and document-presence tests were removed; no documentation was synthesized.
  Standalone executable engine tests remain active.
- **Status**: RETIRED 2026-07-24; not a product defect.

### Full-repository Pyright baseline has 22 pre-existing diagnostics
- **Found**: 2026-07-22 during final architecture-refactor validation with `uv run pyright` (`284` files analyzed).
- **Result**: `22 errors`, grouped as config-ladder schedule typing (`10`), strength-model typing (`7`), mapeditor typing (`3`; see EB-18-022 above for the known runtime-correlated defect), and request-timing typing (`2`). Git diff comparison found zero diagnostics on lines changed by this refactor.
- **Status**: SUPERSEDED 2026-07-24 by **Full-project Pyright exposes unrelated
  config-ladder and request-timing typing debt**, which records the current
  `19`-error baseline.

### Arena-mode controller assertions do not narrow optional lookups
- **Found**: 2026-07-23 while statically checking the objective-diagnostics test migration.
- **Command**: `uv run pyright tests/manual/test_23_standard_arena_game_modes.py`
- **Result**: `12 errors`; assertions around lines 88-116 and 239-248 access `.controller_type` on controller lookups typed as optional (`reportOptionalMemberAccess`).
- **Hypothesis**: Runtime setup guarantees those controllers in the exercised scenarios, but the tests need explicit non-`None` assertions or a typed lookup helper before dereferencing them.
- **Resolution**: The arena tests now bind each controller lookup, assert it is
  non-`None`, and only then inspect `controller_type`; the runtime assertions
  remain unchanged.
- **Verification**: Scoped Pyright for
  `tests/manual/test_23_standard_arena_game_modes.py` reports zero errors, and
  the file reports `6 passed`.
- **Status**: RESOLVED 2026-07-23.

### TypeScript SDK fixtures and reducer lag the life-state/effect-origin contract
- **Found**: 2026-07-22 while running `npm run check` after canonical SDK generation for the subjective combat-log transport work.
- **Error**: `src/reducer.ts:353` is no longer exhaustive because it lacks `LifeStateChangeEvent` and `ReviveEvent`; `src/fixtures.ts` omits `life_state` from `APIEntitySummary`/`APICombatant` fixtures and omits `effect_origin` plus `obscures_perceivability` from `BaseCondition` fixtures.
- **Hypothesis**: The handwritten reducer and fixtures were not updated with the preceding life-state and effect-origin contract refactor. The generated subjective-log models exposed the drift but did not cause it.
- **Resolution**: Updated the handwritten fixtures to the generated contract, made `LifeStateChangeEvent` update entity and encounter lifecycle projections, and classified `ReviveEvent` as a causal event whose state mutation is carried by the lifecycle fact.
- **Verification**: `npm run check` passes and `npm test` reports 26 passing SDK tests, including an alive → dying → dead → alive reducer regression.
- **Status**: RESOLVED 2026-07-22; the drift belonged to the preceding life-state/effect-origin refactor, not the subjective combat-log models.

### Session API contract test still expects the removed raw `/state` route
- **Found**: 2026-07-23 during canonical replication route and replay-compatibility cleanup.
- **Command**: `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q`
- **Test**: `tests/manual/test_18_sessions_api_client_contract.py::test_state_current_turn_and_available_actions_payloads`
- **Failure**: The test calls `GET /state`, receives HTTP 404 with `{"detail": "Not Found"}`, then raises `KeyError: 'entities'` while treating that error body as the former objective state payload.
- **Hypothesis**: The test predates the hard cut to the player `/replication/**` surface and separate `/diagnostics/objective/**` surface. It should be migrated deliberately to the appropriate authority model instead of restoring the raw objective player route.
- **Scope**: The other seven tests in the file pass; the scoped cleanup only removed a separate stale raw event/history test and did not modify `/state`.
- **Resolution**: Migrated the test to validate the joined session's typed `/replication/bootstrap` subjective world and encounter while retaining the existing action-discovery command route. No raw route or compatibility alias was restored.
- **Verification**: `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q` reports `8 passed`; `uv run pyright tests/manual/test_18_sessions_api_client_contract.py` reports zero errors.
- **Status**: RESOLVED 2026-07-23

### Engine-book arena tutorial expects pre-join AI game start
- **Found**: 2026-07-23 during the managed AI service refactor validation.
- **Command**: `uv run pytest tests/engine/test_manual_21_arena_game_sessions_client_state.py`
- **Test**: `tests/engine/test_manual_21_arena_game_sessions_client_state.py::test_start_human_mode_creates_ai_session_and_waits_for_player_join`
- **Failure**: The tutorial test expects the start payload status to be `"started"`, while the canonical route returns `"waiting_for_human"`.
- **Corroboration**: Other focused route tests explicitly expect `"waiting_for_human"` for the same join-gated start flow.
- **Resolution**: The tutorial expectation was restored to
  `waiting_for_human`, matching the canonical join-gated start contract.
- **Verification**: The focused engine-book regression passes on 2026-07-24.
- **Status**: RESOLVED 2026-07-24.

### Shake Awake hard-codes two spell names and omits Hypnotic Pattern
- **Found**: 2026-07-24 during the exhaustive d80 test-migration audit.
- **Behavior**: `ShakeAwake` recognized only conditions named `Sleep` or
  `Eyebite Asleep`, even though `HypnoticPatternEffect` explicitly states that
  another creature can end it by shaking the target awake.
- **Cause**: The action switched on concrete condition display names instead of
  consuming an engine-owned capability. This also made future wakeable effects
  invisible to action discovery.
- **Resolution**: Added the dependency-neutral
  `ConditionRemovalTrigger.SHAKE_AWAKE` fact, declared it on Sleep, Eyebite
  Asleep, and Hypnotic Pattern, and made action validation/removal consume that
  typed fact. One physical assistance action removes every active condition
  that explicitly declares the transition.
- **Verification**:
  `tests/manual/test_140_shake_awake_trigger.py`, EB-15-033, and the subjective
  condition-fact replay regression pass.
- **Status**: RESOLVED 2026-07-24.

### Gust of Wind recursively re-triggered its own entry push
- **Found**: 2026-07-24 while restoring the archived persistent-zone spell
  execution matrix.
- **Test**:
  `tests/manual/test_remaining_zone_spell_legacy_contract.py::test_gust_of_wind_executes_cast_entry_turn_wall_and_cleanup_edges`
- **Behavior**: Entering the Gust zone made the entry handler push the creature
  with `Entity.update_entity_position()`. Each cell relocation emitted another
  `SPATIAL_ENTITY_ENTERED` event in the same zone, so the same handler rolled
  another save and pushed again recursively instead of resolving one 15-foot
  push. A turn-start push could enter the same recursion through the entry
  handler.
- **Cause**: The zone owned no in-flight causal guard around its entry and
  turn-start push handlers.
- **Resolution**: `GustOfWindZone` now owns a private per-entity in-flight push
  set. Nested spatial events from the active push are ignored, while the guard
  is released in `finally` so a later independent entry or turn-start still
  resolves normally.
- **Verification**: The restored regression asserts one completed save, one
  completed forced movement, one 15-foot displacement, a later independent
  turn-start push, wall truncation, and no push after concentration cleanup.
- **Status**: RESOLVED 2026-07-24.

### Death during Frenzy left the owning Rage condition active
- **Found**: 2026-07-24 while restoring the archived class/action behavioral
  matrix.
- **Test**:
  `tests/manual/test_142_class_action_legacy_contract.py::test_rage_death_and_frenzy_cleanup_do_not_leave_stale_state`
- **Behavior**: Lethal damage removed `Frenzied` and its granted strike, but a
  dead Barbarian retained `Raging` and its mechanical transforms.
- **Cause**: The death handler removed the `Frenzied` child first and used
  `elif` for `Raging`. Child removal detaches only that child; it does not
  remove its owning parent.
- **Resolution**: The death handler now removes the owning `Raging` condition,
  letting `BaseBlock` perform its canonical recursive sub-condition cleanup. A
  defensive child-only branch remains for malformed legacy state.
- **Verification**: The focused regression asserts `LifeState.DEAD`, removal of
  both conditions, removal of the Frenzied Strike action, and absence of an
  exhaustion residue.
- **Status**: RESOLVED 2026-07-24.

### Guiding Bolt marks never expired without another attack
- **Found**: 2026-07-24 during exact reconciliation of the archived easy-tier
  spell matrix.
- **Behavior**: An actual Guiding Bolt hit registered removal on the next attack
  but no caster-turn expiry. If nobody attacked the marked target, its incoming
  attack advantage persisted indefinitely.
- **Coverage hole**: The archived duration test never cast Guiding Bolt. It
  manually created a mark with an injected two-round duration and advanced the
  target's turn twice, contradicting its own “end of caster's next turn”
  description.
- **Resolution**: `GuidingBoltMarked` now owns a second cleanup handler filtered
  to the caster's `TURN_END` effect. It ignores the current turn end, removes
  the mark at the end of the caster's next turn, and is cleaned with the
  condition if an attack consumes the mark first.
- **Verification**:
  `test_guiding_bolt_actual_cast_expires_at_end_of_casters_next_turn` casts the
  real spell, performs no attack, asserts survival through the current caster
  turn, and asserts mark plus handler cleanup at the next caster turn end. The
  existing first-attack cleanup regression also passes.
- **Status**: RESOLVED 2026-07-24.

### Safe-movement readout hard-codes one of two equivalent detours
- **Found**: 2026-07-24 while validating the exhaustive d80 spell/spatial
  migration ledger.
- **Test**:
  `tests/manual/test_09_action_discovery_and_costs.py::test_safe_movement_metadata_shapes_path_choice`
- **Behavior**: The live pathfinder returned the safe route through `(6, 5)`;
  the readout golden requires the symmetric route through `(4, 5)`. Both routes
  avoid the hazard, cost 15 feet, reach the same destination, and the command
  executes the disclosed safe path. Every semantic assertion passes; only the
  arbitrary tie-direction string comparison fails.
- **Hypothesis**: A neighbor-order or equally optimal tie-break changed while
  the tutorial output retained one exact path. The contract should assert the
  route's endpoints, legality, hazard exclusion, cost, and execution identity,
  not one arbitrary symmetric intermediate cell.
- **Resolution**: The maintained readout now accepts exactly the two symmetric
  shortest 15-foot detours while retaining hard assertions for endpoints,
  hazard exclusion, cost, disclosed-path execution identity, and final
  movement.
- **Verification**:
  `tests/manual/test_09_action_discovery_and_costs.py::test_safe_movement_metadata_shapes_path_choice`
  passes.
- **Status**: RESOLVED 2026-07-24.

### Two Fire Bolt tutorial readouts omit the threatened ranged-attack die
- **Found**: 2026-07-24 while validating maintained selectors referenced by
  the exhaustive d80 spell/spatial migration ledger.
- **Tests**:
  `tests/manual/test_13_spellcasting_core.py::test_first_spell_example_prints_visible_discovery_and_cast`
  and
  `tests/manual/test_13_spellcasting_core.py::test_fire_bolt_uses_spell_attack_bonus_scaling_and_damage`.
- **Behavior**: Both fixtures place the caster adjacent to a hostile target and
  provide fixed faces for one attack d20 plus two level-5 damage dice. The
  canonical ranged-while-threatened rule rolls two attack d20s at disadvantage,
  so the fourth required face is absent and both tests raise
  `RuntimeError: No fixed dice face remains for this roll`.
- **Corroboration**:
  `tests/manual/test_14_spell_families.py::test_ranged_spell_attacks_are_disadvantaged_while_threatened`
  passes and explicitly asserts the two-d20 disadvantage roll, combat-log
  breakdown, and threatened flag.
- **Resolution**: Both tutorial fixtures now provide and assert the complete
  threatened disadvantage roll (`[14, 12]`) before the two level-five damage
  dice. The spell still hits from the lower d20, deals the exact 11 damage, and
  spends one action.
- **Verification**: Both cited selectors pass independently.
- **Status**: RESOLVED 2026-07-24.

### Mark Target cooldown was enforced only during discovery
- **Found**: 2026-07-24 while restoring the archived specialized-skeleton
  behavioral matrix.
- **Behavior**: After using Mark Target once and ending concentration,
  `MarkTargetAction.pre_validate()` correctly rejected a second use because
  `Mark Cooldown` remained active, but a caller invoking `apply()` directly
  could still mark another target.
- **Cause**: The cooldown fact was checked only by the action-discovery
  pre-validation path. The authoritative `_validate()` execution boundary
  checked source, target, visibility, and range, but not the cooldown.
- **Resolution**: `MarkTargetAction._validate()` now rejects execution while
  the source owns `Mark Cooldown`, so discovery, direct engine calls, and
  server-triggered execution share the same rule.
- **Verification**:
  `tests/manual/test_138_skeleton_units_legacy_contract.py::test_mark_target_strips_existing_hidden_and_rejects_second_use`
  asserts both pre-validation rejection and a canceled direct `apply()`, with
  no second `Marked` or `Concentrating` state created.
- **Status**: RESOLVED 2026-07-24.

### Mode-specific pathfinding expanded from impassable start terrain
- **Found**: 2026-07-24 while restoring the archived terrain movement-mode
  matrix.
- **Behavior**: `GridMap.compute_paths()` correctly treated land as
  swimming-impassable when considering destination cells, but still seeded a
  land start and expanded from it into adjacent water. A single-mode swimming
  query could therefore produce a route whose first cell did not support
  swimming.
- **Cause**: The pathfinder deliberately retains the origin as a zero-cost
  sentinel, but no guard prevented BFS/Dijkstra edge expansion when the
  origin's movement cost for the requested mode was zero.
- **Resolution**: An absent or mode-impassable origin now returns only the
  zero-cost origin sentinel and no outgoing edges. Ordinary walkable origins
  retain the existing cached BFS/Dijkstra path.
- **Verification**:
  `tests/manual/test_remaining_zone_spell_legacy_contract.py::test_movement_mode_pathfinding_preserves_terrain_specific_routes`
  executes walking, flying, and swimming paths across difficult terrain,
  walls, water, and land. EB-11-002, EB-11-003, and EB-11-005 remain green for
  ordinary terrain and entity-origin paths.
- **Status**: RESOLVED 2026-07-24.

### Zone-spell migration ledger overclaimed broad family coverage
- **Found**: 2026-07-24 during the semantic spot-audit of the exhaustive d80
  spell/spatial migration ledger.
- **Behavior**: All archived Grease, Cloudkill, and Spirit Guardians cases were
  initially mapped to one broad EB-15 family test. That test did not exercise
  Cloudkill's initial damage or cleanup, Spirit Guardians' initial
  enemy/ally split or caster-following zone, and its Grease fixture omitted
  standard actions, so it incorrectly expected Prone to survive owner-turn
  auto-stand.
- **Resolution**: Three deterministic maintained regressions now execute each
  complete spell lifecycle. The EB Grease fixture now installs standard
  actions and asserts removal of Prone plus the exact 15-foot movement cost.
  Each archived selector maps to the corresponding exact lifecycle regression
  instead of the broad family test.
- **Verification**:
  `tests/manual/test_remaining_zone_spell_legacy_contract.py` asserts initial,
  entry, turn, movement/following, faction, once-per-turn, terrain, and
  concentration-cleanup edges with fixed dice.
- **Status**: RESOLVED 2026-07-24.

### Moving zones left stale tile markers behind
- **Found**: 2026-07-24 while restoring the archived generic zone-movement
  contract.
- **Behavior**: `ZoneControlCondition.move_zone()` moved terrain, light, and
  spatial-handler indices but did not remove marker conditions from departed
  cells or add them to newly occupied cells. Hazard routing and presentation
  could therefore describe the zone's old footprint after Cloudkill, Spirit
  Guardians, or another moving zone relocated.
- **Cause**: The movement path predated the linked tile-marker ownership path
  and updated only the original three spatial surfaces.
- **Resolution**: Zone movement now computes removed/retained/added cells once,
  removes zone-owned terrain, light, and marker facts only from removed cells,
  updates shared spatial indices once, and applies all three facts only to
  added cells. Retained cells preserve their condition and modifier identity.
- **Verification**:
  `tests/engine/test_grid_pathfinding.py::test_eb_11_020_zone_removal_cleans_spatial_handlers_terrain_and_markers`
  asserts the old marker/terrain disappear, the new marker/terrain and handler
  appear, and final zone removal cleans the union of both footprints.
- **Status**: RESOLVED 2026-07-24.

### AoE and hazard migration rows relied on broad proxy coverage
- **Found**: 2026-07-24 during the semantic spot-audit of the exhaustive d80
  spell/spatial migration ledger.
- **Behavior**: Archived generic AoE discovery/convolution rows were mapped to
  a Fireball family test that did not prove self-range discovery with no
  visible enemies, ally/self filters, preview-to-execution cardinality, or
  deterministic per-target convolution. Hazard-filter and spike-zone rows
  similarly pointed at broad pathfinding/zone examples that did not execute
  every `ALL`, `NON_SOURCE`, and `ENEMIES` requester branch, shared spike
  activation/deactivation, or Spike Growth's source immunity and hidden-hazard
  lifecycle.
- **Resolution**: Dedicated maintained regressions now use real spell/action,
  tile-condition, entity-faction, and GridMap surfaces for each contract. The
  migration ledger maps each archived row to the narrow regression that
  executes its semantic branch; no Fireball-only or generic-zone proxy remains
  for these cases.
- **Verification**:
  `tests/manual/test_remaining_spell_legacy_contract.py`,
  `tests/manual/test_remaining_zone_spell_legacy_contract.py`, and
  `tests/manual/test_spike_zone_movement_legacy_contract.py` jointly assert
  generic AoE discovery/execution, all requester filters, no-hazard defaults,
  spike activation/deactivation, per-step damage, and complete Spike Growth
  cleanup with deterministic dice.
- **Status**: RESOLVED 2026-07-24.

### Magic Missile and Shield migration rows pointed at narrower branches
- **Found**: 2026-07-24 during the final grouped-selector review of the d80
  spell/spatial ledger.
- **Behavior**: Five archived Magic Missile distribution cases were all mapped
  to a maintained single-target three-dart assertion; that selector did not
  prove split targets, repeated explicit targets, level-three dart count, or
  enemy-only cancellation. Several Shield non-firing/resource cases pointed at
  the marginal-hit selector, and the disabled-Magic-Missile case pointed at the
  enabled missile-block selector because the mapping checked `"mm"` before
  `"disabled"`.
- **Resolution**: One deterministic Magic Missile regression now executes
  single-target, split-target, repeated-target, level-three, and ally-rejection
  branches with exact per-dart damage and resource assertions. Shield rows now
  map to the existing exact marginal-hit, non-firing/cleanup, missile-block, or
  handler-toggle selector according to their actual branch.
- **Verification**:
  `tests/manual/test_remaining_spell_legacy_contract.py::test_magic_missile_preserves_dart_distribution_upcast_and_enemy_filter`
  passes alongside EB-15-009, EB-15-010, EB-15-020, EB-15-022, and the
  spell/spatial manifest unit.
- **Status**: RESOLVED 2026-07-24.

### Weapon-coat variants collapsed to one generic condition identity

- **Found**: 2026-07-26 while closing the exact condition-content inventory.
- **Behavior**: Applying the fire, lightning, concentration-fire, or timed-fire
  weapon coat created mechanically distinct effects, but an applied condition
  reported the generic authored identity
  `content.neurodragon:condition:condition.weapon_coat@1`. The fire gameplay
  regression expected its exact
  `condition.consumable.weapon_coat.fire` identity and failed.
- **Cause**: All variants instantiated one declared `_WeaponCoatCondition` and
  attempted to distinguish it with an instance `semantic_key`. An authenticated
  behavior binding correctly takes precedence over an untrusted instance
  string, so every variant resolved to the class's one generic declaration.
- **Resolution**: `_WeaponCoatCondition` is now an undeclared internal mechanic.
  Four concrete player-visible leaves own the exact fire, lightning,
  concentration-fire, and timed-fire definitions. The apply action declares a
  closed `APPLIES_CONDITION` dependency to all four and binds the selected
  condition through the action and originating item before admission.
- **Verification**:
  `tests/manual/test_170_neurodragon_consumable_content_factories.py::test_weapon_coat_condition_variants_own_exact_closed_identities`
  asserts the closed declaration/dependency set, while
  `tests/manual/test_170_neurodragon_consumable_content_factories.py::test_weapon_coat_variants_keep_exact_actions_conditions_and_cleanup`
  executes the fire coat and asserts its definition, immediate provider,
  durable item root, owner, mechanics, and removal cleanup. The condition and
  migration inventories remain guarded by `test_179_condition_content_identity.py`
  and `test_161_legacy_behavior_migration_ledger.py`.
- **Status**: RESOLVED 2026-07-26.

### Map-editor item identity retained a parallel legacy string catalog

- **Found**: 2026-07-26 during the final item/content coexistence audit.
- **Behavior**: Public placement requests and schema-1 saved maps selected
  items and environment objects through `catalog_id` strings. A separate
  reverse reference map and `legacy_item_recipes.py` rebuilt those strings
  beside the frozen content registry, so installed pack content was absent
  from discovery and save/load identity could diverge from the authenticated
  runtime binding.
- **Cause**: The experimental map editor predated `ContentRecipe`,
  `content_set_digest`, item persistence policy, and registry-owned recipe
  presets. Its compatibility layer remained after gameplay construction had
  completed the canonical content hard cut.
- **Resolution**: Map-editor object and loot discovery now reads the frozen
  registry directly. It exposes exactly the 14 public environment roots, 97
  public possession defaults, and 203 non-alias named variants. Placement,
  binding, and schema-2 save/load use the exact self-authenticating recipe and
  content-set digest; mutable door, light, charge, and regenerated trap-link
  state is separate. The reverse map, legacy loot branch, source-module
  projection, schema-1 acceptance, and `legacy_item_recipes.py` were deleted.
- **Verification**:
  `tests/manual/test_182_mapeditor_content_recipe_hard_cut.py` asserts exact
  discovery and deduplication, generically materializes all 111 default public
  roots, exercises integrity/kind/policy/content-set rejection, round-trips
  schema-2 runtime state, and statically proves the compatibility code is
  absent. `tests/manual/test_147_mapeditor_legacy_contract.py` retains the
  complete entity-free crypt save/load and regenerated trap-link lifecycle.
- **Status**: RESOLVED 2026-07-26.

### Spell-created environment objects exposed fake icon identities

- **Found**: 2026-07-26 while running the complete environment-content
  identity regression after the exact icon-ledger cut.
- **Behavior**:
  `test_bootstrap_registers_exact_public_environment_presentations` failed
  because Guardian of Faith and Heroes' Feast no longer retained their former
  content-ID placeholders, but their environment-object definitions had not
  yet received authenticated atlas keys.
- **Cause**: The old descriptors treated any non-null string as an icon key.
  Neither object content ID names a real frontend asset. The owning spell
  definitions already had the exact reviewed `spell.guardian-of-faith` and
  `spell.heroes-feast` assets, but the object definitions had no authenticated
  presentation link to them.
- **Resolution**: The offline icon importer now follows only exact
  `CREATES_OBJECT` dependency edges whose provider has one authenticated asset.
  Both object descriptors receive the owning spell asset during their original
  construction; the binding ledger pins the provider ref, key, and asset
  digest. No runtime name or display inference was added.
- **Verification**:
  `tests/manual/test_180_environment_content_identity.py::test_bootstrap_registers_exact_public_environment_presentations`
  passes for all 16 public environment roots, while
  `tests/manual/test_183_content_icon_bindings.py` verifies dependency-backed
  bindings, atlas membership, tamper rejection, and original declaration
  object identity.
- **Status**: RESOLVED 2026-07-26.

### Position action discovery conflates no target with target-cost unaffordability

- **Found**: 2026-07-26 while auditing target-dependent typed action costs.
- **Behavior**: Jump and Prepare Intercept can disappear from the authored
  action surface when there is no destination, while a previously selected
  destination can leak its movement cost into the next target-independent
  affordability check. The response cannot distinguish no rules-valid
  destination from rules-valid destinations blocked only by remaining
  movement.
- **Resolution**: Discovery now owns one required closed availability status,
  checks source and source-dynamic costs without consulting selected-target
  state, and evaluates target-dynamic costs only on target-specialized copies.
  Jump and Prepare Intercept share the typed declared-position path; authored
  rows remain stable while `legal_only` remains executable-only.
- **Verification**:
  `tests/manual/test_09_action_discovery_and_costs.py::test_position_action_rows_report_no_rules_valid_targets`
  and
  `tests/manual/test_09_action_discovery_and_costs.py::test_position_action_rows_report_target_cost_unaffordable`
  pass for both Jump and Prepare Intercept.
- **Status**: RESOLVED 2026-07-26.

### Entity action discovery mutates registered targets

- **Found**: 2026-07-26 during independent review of the availability hard cut.
- **Behavior**: Entity target validation calls `set_target_entity()` on the
  registered action template. A discovery read therefore leaves Shake Awake,
  Shove, and other reusable templates carrying the last candidate UUID.
- **Resolution**: Entity target validation now uses a target-specialized deep
  copy for both requirements and target-bound cost evaluation. Registered
  templates remain immutable across discovery calls.
- **Verification**:
  `tests/manual/test_09_action_discovery_and_costs.py::test_entity_action_discovery_does_not_retain_candidate_targets`
  passes for both Shake Awake and Shove.
- **Status**: RESOLVED 2026-07-26.

### Path movement row omits exact unavailable status

- **Found**: 2026-07-26 during independent review of the availability hard cut.
- **Behavior**: Move disappears when remaining movement is zero and when no
  rules-valid route exists, so the authored response cannot distinguish
  target-cost exhaustion from route absence.
- **Resolution**: Path discovery now probes only visible adjacent subjective
  transitions to distinguish route existence from movement-budget
  exhaustion. Default discovery retains the authored Move row with an exact
  status; `legal_only` continues to omit non-executable rows.
- **Verification**:
  `tests/manual/test_09_action_discovery_and_costs.py::test_move_row_reports_no_rules_valid_routes`
  and
  `tests/manual/test_09_action_discovery_and_costs.py::test_move_row_reports_movement_budget_exhaustion`
  pass.
- **Status**: RESOLVED 2026-07-26.

### Targetless registered AoE rows claim availability

- **Found**: 2026-07-26 during independent review of the availability hard cut.
- **Behavior**: Self-origin required-target AoEs such as Burning Hands,
  Thunderwave, and Lightning Bolt emit `available` with no executable target
  when no enemy is visible, and survive `legal_only`; execution by index then
  has no legal index.
- **Resolution**: Registered AoE discovery now emits one stable authored row
  after both cached and computed previews. An empty executable target set is
  `no_valid_targets` and is omitted by `legal_only`; contextual item AoEs stay
  sparse rather than emitting disabled rows.
- **Verification**:
  `tests/manual/test_remaining_spell_legacy_contract.py::test_self_range_aoe_discovery_survives_zero_visible_enemies`
  passes for Burning Hands, Thunderwave, and Lightning Bolt before and after a
  visible target enters the scene.
- **Status**: RESOLVED 2026-07-26.

### Generic position status confuses requirements and target cost

- **Found**: 2026-07-26 during independent review of generic position
  discovery.
- **Behavior**: A POSITION/POSITION_PATH action with subjective routes but no
  candidate passing its action requirements is labeled
  `target_cost_unaffordable`, even when it declares no target-bound cost.
- **Resolution**: Generic position discovery now counts candidates only after
  their non-cost requirements pass. Fast Move keeps its route-existence
  specialization; other POSITION/POSITION_PATH rows report target-cost
  exhaustion only when at least one rules-valid candidate then fails cost.
- **Verification**:
  `tests/manual/test_09_action_discovery_and_costs.py::test_generic_position_row_reports_requirements_not_target_cost`
  passes using a fresh Misty Step template.
- **Status**: RESOLVED 2026-07-26.

### Entity target cost failure is labeled no target

- **Found**: 2026-07-26 during independent review of entity-target
  availability status.
- **Behavior**: Entity target validation filters out a rules-valid target whose
  target-dependent cost is unaffordable, but the collector loses that
  distinction and reports `no_valid_targets`.
- **Resolution**: Entity target validation now returns both affordable targets
  and the count whose non-cost requirements passed. Registered entity-owned
  rows report target-cost exhaustion only when that count is nonzero;
  contextual item rows consume the same validation result but remain sparse.
- **Verification**:
  `tests/manual/test_09_action_discovery_and_costs.py::test_entity_row_reports_target_cost_unaffordable`
  passes with an adjacent armed attacker and an injected typed target movement
  cost.
- **Status**: RESOLVED 2026-07-26.

### Dragon Wings declaration omitted its active-condition dependency

- **Found**: 2026-07-29 while running the Sorcerer progression suite for the
  level-bounded spell-choice correction.
- **Behavior**: The public Dragon Wings structural declaration grants its
  toggle action but does not declare the exact
  `APPLIES_CONDITION -> class_feature.sorcerer.dragon_wings.active`
  relationship required by the authored catalog contract.
- **Resolution**: The pure structural declaration now carries an exact
  dependency-neutral `APPLIES_CONDITION` reference alongside its toggle-action
  dependency. The reference is constructed from the behavior contract without
  importing the concrete condition upward into the structural layer.
- **Verification**:
  `tests/progression/test_sorcerer_progression_definitions.py::test_dragon_wings_closes_toggle_flight_and_active_state`
  passes as an ordinary regression and asserts the complete two-edge
  dependency set.
- **Status**: RESOLVED 2026-07-29.

### Population-only content advances blocked durable character deployment

- **Found**: 2026-07-29 after the level-bounded Sorcerer spell catalog
  correction advanced the installed content-set digest.
- **Behavior**: otherwise unchanged persistent characters created under the
  immediately prior digest failed every encounter compose preview with
  `Character definition content set differs from this worker`.
- **Cause**: explicit content rebasing existed for respec and level-up, but the
  cold character-deployment boundary sent historical definition heads directly
  to the current-content preview worker.
- **Resolution**: deployment now resolves every persisted content reference
  through the canonical rebaser, validates the complete resulting build, and
  atomically appends current-content definition/loadout heads through the
  existing three-head CAS before recipe normalization. Historical choices that
  are no longer legal still fail closed; no digest or `ContentRef` check was
  weakened.
- **Automated reproducer**:
  `tests/manual/test_187_standalone_local_game_lifecycle.py::test_standalone_compose_rebases_prior_content_character_before_start`
  creates an exact persistent character under a prior digest and proves the
  same owned roster composes, previews, starts, pins current heads, and
  preserves the historical definition revision.
- **Status**: RESOLVED 2026-07-29.
