# Codebase Audit Close-out — 2026-07-29

This is the live execution ledger for closing
`agent_docs/CODEBASE_AUDIT_WORK_ORDER_2026-07-29.md`.

The close-out is not complete merely because production code imports or a
focused happy path works. Completion requires:

1. every maintained test file collects and passes when run individually;
2. every retired artifact-only test is deleted instead of rebuilding its
   retired production surface;
3. every fixed correctness issue has a direct deterministic regression;
4. production dead paths and duplicate authorities identified in the work
   order are removed or explicitly classified as distinct responsibilities;
5. generated contracts are regenerated once after the final wire-model change;
6. focused Pyright, generator checks, TypeScript build/tests, and
   `git diff --check` pass.

## Scope decisions

- Do not restore deleted convenience or compatibility APIs solely to satisfy an
  old test or document.
- Keep executable engine/rules regressions; delete tests whose only subject is
  a retired migration ledger, tutorial wrapper, exact incidental count, or
  abandoned evaluation harness.
- The player renderer projector and AI tactical projector remain distinct
  output contracts. Visibility authority remains `Entity.senses`; there is one
  canonical AI fact projector.
- `server/subjective_parity_diagnostics.py` remains an independent diagnostic
  oracle by design.
- Hosted registered-provider orchestration is a product feature, not hidden
  cleanup. The hosted catalog must remain truthful and native-only until that
  feature is deliberately implemented.
- Do not merge class-specific mechanics merely to reduce line count. Extract
  only repeated authority/lifecycle machinery.

## Live checklist

### A. Collection and retired-artifact cleanup

- [x] Replace stale `register_spells_by_name` test/document usage with the
      canonical class-based `register_spell` surface.
- [x] Repoint the live-replication test to maintained test support.
- [x] Remove retired creature/item/behavior migration-ledger tests and their
      dangling generators/references where the underlying artifacts are gone.
- [x] Remove exact tutorial readout assertions while retaining stream fanout,
      cursor, and completion-before-log behavior assertions.
- [x] Audit the non-exact engine-book migrations. The D80 reviewed migration
      manifest classifies all 1,458 legacy selectors as 446 active, 978
      strengthened, 21 stale, and 13 retired, with zero unresolved selectors.
      All 43 genuine behavior modules now live under `tests/engine/`; the
      deprecated book wrapper is absent.
- [x] Run every affected test file individually.

### B. Correctness and direct regressions

- [x] Add a direct regression proving one Attack declaration dispatches
      declaration handlers exactly once.
- [x] Character-materialization failure destroys provisional items/bindings and
      leaves no light source.
- [x] Lifecycle gates derive from `LifeState`.
- [x] Automatic-GC suppression is lease-counted and nested.
- [x] Worker proxy authorization denies unknown reads.
- [x] Attack target context restores both actors on success and exception.
- [x] Replace the incompatible dice-result inheritance/tuple contracts and
      delete dead `DamageRolledEvent`.

### C. Remaining production cleanup

- [x] Replace dangerous blind exception swallowing with explicit propagation or
      logged observer isolation according to the owning boundary.
- [x] Replace the duplicated reflective analytics accumulators with explicit
      typed field ownership.
- [x] Correct stale saving-throw documentation and redundant encounter
      lifecycle predicates.
- [x] Consolidate decision-epoch timing into canonical AI instrumentation.
- [x] Audit the production reachability of `ai.subjective.policy_agent`; delete
      it and its wrapper-only tests if it is a retired executor.
- [x] Remove remaining duplicate policy selection/gating implementations when
      they encode the same semantics.
- [x] Finish the event/SDK generator single-owner cleanup.
- [x] Remove the parallel permanent-class-feature condition installers.
      Permanent Fighter, Barbarian, Sorcerer, and feat structure must have one
      authority: exact structural declarations plus reversible character-grant
      appliers. Runtime conditions remain only for genuinely evented state such
      as Raging, Frenzied, and Reckless Attacking.

### D. Generated contract freeze

- [x] Regenerate the event contract and TypeScript SDK once after the dice-event
      contract is closed.
- [x] Run generator `--check`, SDK build, SDK tests, and focused Python contract
      tests.
- [x] Record final contract hashes here before any coordinated service restart.

### E. Maintained-suite sweep

- [x] Enumerate maintained Python test files.
- [x] Run each file individually; never invoke an unbounded repository-wide
      Pytest command.
- [x] Fix implementation failures or update/delete genuinely retired tests.
- [x] Run full Pyright over the configured production/test scope.
- [x] Run architecture gates, `git diff --check`, and record the final census.

## Evidence log

### 2026-07-29 — initial reconciliation

- `tests/engine/test_spellcasting.py`: collection error, deleted
  `register_spells_by_name`.
- `tests/manual/test_25_live_replication_streams.py`: collection error, deleted
  `server.live_replication`.
- `tests/manual/test_157_legacy_creature_migration_ledger.py`: collection error,
  deleted `LegacyContentClassification`; its creature ledger and generator are
  already retired.
- Engine-book move audit: 502 former test functions; 428 have exact normalized
  bodies in the maintained suite and 74 require explicit semantic review.
- Old server-owned AI projector is deleted. Native AI and server observation
  transport both import `dnd.ai.runtime.subjective_projection`.
- Focused production dead-code scan found no additional high-confidence
  unreferenced production function after the current cleanup batch.

### 2026-07-29 — first collection block closed

- `tests/engine/test_spellcasting.py`: 19 passed.
- `tests/manual/test_25_live_replication_streams.py`: 15 passed after removing
  obsolete exact cursor/count transcript assertions.
- `tests/manual/test_155_content_inventory_contracts.py`: 3 passed; only the
  maintained official-source coverage contract remains.
- `tests/manual/test_180_environment_content_identity.py`: 6 passed after
  removing its dependency on the retired item migration ledger.

## Roll-result event hierarchy closeout

The dice-result and action-declaration interceptor cleanup is complete. The
authoritative design, defect inventory, implementation checklist, exact
contract hashes, and focused green evidence are recorded in
`agent_docs/plans/ROLL_RESULT_EVENT_HIERARCHY_2026-07-29.md`.

The frozen post-closeout hashes are:

- SDK: `da4bd3626e65d728fc9469cdd4a3350eaf914eeac1221af9871f019ba75aac0d`
- player replication:
  `0bdba516d5c20f2c711c0621f63aab363e1dcf6f62246545980e06db2740de91`
- event:
  `9aee4d4913a2121033f6bfbb9afea4efa6d88b8f9bdd3e6b01f8346921805e82`
- generated TypeScript source:
  `e85f34dff3eb16124c8820b3589ced3e5aef6c4f5853d1de749abf05af60aa06`

### 2026-07-30 — retired subjective policy executor removed

- Repository-wide production reachability found no import or caller of
  `ai.subjective.policy_agent`; only its dedicated wrapper test imported it.
- Native and registered-provider execution are owned by `dnd.ai` assignment
  runners. Codex execution is owned by `ai.codex_tools.hot_runtime`, which
  directly consumes the shared `PolicyHost`.
- The removed 535-line wrapper independently reimplemented epoch waiting,
  selection, submission, result recording, rejection constraints, resync,
  command execution, and telemetry.
- Its door-routine, visible-combat, and rejected-row assertions are already
  owned by maintained policy-host/routine/hot-runtime tests. The client policy
  source manifest remains covered by
  `tests/manual/test_30_codex_takeover_tools.py`.

### 2026-07-30 — current-tree dead leaf and reflection cleanup

- Removed unreachable private spacing/distribution helpers from the shared
  policy implementation, the unused objective event-cursor escape hatch from
  the AI projector, and an unused dark-arena fixture constructor.
- Deleted the duplicate top-level spike-deactivation function. Runtime trap
  retirement remains owned by `PullLeverAction`, whose regression now proves
  both linked-handler and linked-marker cleanup without touching another trap.
- Replaced the two reflective analytics merge loops with explicit typed field
  accumulation.
- Replaced string-built spell-slot attribute probes with
  `ActionEconomy.spell_slot_value()` in server action serialization, summary
  capture, and decision-epoch projection.
- Confirmed every observer-isolation boundary named in the audit now logs its
  exception; authoritative turn/setup paths propagate. Corrected the obsolete
  saving-throw converter documentation and removed doubled dead/alive checks
  while retaining the useful canonical-life-state property.
- Removed the event generator's unused standalone-client output mode and its
  second TypeScript renderer. The SDK generator now builds and writes the event
  manifest plus SDK artifacts in one process, reusing the exact same event
  manifest instead of recursively spawning itself and rebuilding it.

### 2026-07-30 — AI authority and generated-data cleanup

- Removed the server-injected micro-timing callback threaded through decision
  epoch construction. Native AI phase ownership remains in
  `dnd.ai.instrumentation`; the HTTP boundary retains its total epoch-build
  timing. Decision construction no longer interleaves gameplay projection with
  dozens of ad-hoc clocks.
- Removed the Basic policy's imperative utility whitelist and permissive
  fallback. Candidate admission now asks the same typed `PolicyRuleSpec` rows
  that perform selection, so tags and thresholds have one owner.
- Added one replay-stable `PolicyCandidate` ranking key used by both the bundled
  data-driven policy and the custom tactical example. The top-level Codex
  `UtilityArbiter` remains a distinct ordered `PolicyProposal` ranking contract,
  not a duplicate engine-candidate selector.
- Centralized the neutral action-cost payload shared by primitive and detailed
  engine cost encodings.
- Moved the test-only public-affordance projection wrapper out of production
  `dnd.ai`; tests now discard execution authority through explicit test support.
- Removed the unused allocating Dijkstra neighbor-list helper while retaining
  direct hot-loop traversal and its cost/bounds/directional-edge regression.
- Removed Evocation's exact copy of the shared spell line-of-sight validator.
- Reduced the generated exact icon binding table from 4,029 to 2,691 lines.
  Each row now stores only icon key and asset digest; the exact lookup key
  already authenticates the definition contract hash, and null icon keys
  already encode the binding disposition. The impossible post-lookup stale-hash
  branch was deleted from runtime resolution.

### 2026-07-30 — immutable temporary action rules

- Removed the metamagic/action override path that mutated shared registered
  templates and later wrote a hard-coded table of generic defaults over them.
  That cleanup could destroy authored non-default facts such as an innate
  spell's slot policy, and Twinned/Distant bypassed the helper with more direct
  mutations.
- `Entity` now owns independently removable action-overlay leases. Registered
  templates remain authored facts; discovery and execution receive shallow
  effective copies. Overlapping leases compose in installation order and
  removing either lease preserves the other.
- Quickened, Twinned, and Distant use the same lease authority. AI capability
  fallback and ordinary action execution resolve the same effective templates,
  while standard-action replacement clears all stale leases.
- Direct regressions prove authored non-default fields survive cleanup and two
  simultaneous leases are independently removable.
- Green focused evidence: `test_spellcasting.py`, 20/20 before the additional
  lease-stacking case; `test_126_action_override_runtime.py`, 26/26;
  `test_schema2_sorcerer_runtime_actions.py`, 4/4;
  `test_bg3_spell_action_economy.py`, 1/1; `test_action_discovery.py`, 12/12;
  touched production/test Pyright, zero errors.

### 2026-07-30 — lifecycle, materialization, and owned-model authority

- Rejected condition applications now roll back provisional modifiers,
  handlers, child identities, and global registration instead of leaving an
  applied-but-unindexed condition. Rejected removals retain their indexes and
  runtime state; expiration reports the actual removal result.
- Ordinary self actions now share `BaseAction` declaration construction,
  including the source-as-target invariant. Redundant constructors were removed
  from core actions and Fighter/Barbarian actions while specialized attack,
  movement, shove, and spell events remain explicit.
- Bestow Curse's attack bonus damage no longer rolls and applies an unrelated
  second damage event. It appends one immutable necrotic
  `DamageRollResultEvent` packet, so the typed roll-modification fact and combat
  log are children of the causal attack like Divine Smite and monster bonus
  damage.
- Item and creature materializers no longer cold-bootstrap an uninstalled
  content runtime. Startup and worker composition install one authenticated
  registry; gameplay materialization consumes that registry or fails closed.
- Canonical content JSON hashing now has one dependency-neutral owner used by
  definition contracts, recipes, presets, battlefields, durable characters,
  pack manifests, icon bindings, authored item visuals, and content-set
  construction. The distinct encounter serializer remains separate because it
  intentionally accepts string-converted domain values.
- Server canonical JSON now owns its SHA-256 operation as well; directory and
  terminal-summary storage consume the same serializer instead of maintaining
  another local encoder.
- Removed the stale Codex compatibility probe for the deleted
  `SubjectiveRuntime.flush_agent_events` method. Queued policy telemetry has one
  flush owner.
- Player and AI action discovery now consume explicit BaseAction spell, weapon,
  and movement metadata capabilities. The engine no longer probes owned action
  subclasses with `getattr`; True Strike, Extra Attack, Frenzied Strike, and all
  Move modes expose their exact specializations through the same contract.
- Replaced remaining owned-model probes in inventory item discovery, Sneak
  Attack parent-roll inspection, Exhaustion reduction, and Freedom of Movement
  condition-tag inspection with typed, fail-closed contracts.
- Focused evidence: condition lifecycle 16/16; standard conditions 20/20;
  action discovery 13/13; combat actions 33/33; subjective runtime epochs
  60/60; Haste restricted actions 25/25; spellcasting 22/22; True Strike spell
  batch 15/15; spell families 54/54; monster traits 15/15; content bootstrap
  6/6; content catalog 5/5; icon bindings 12/12; creature runtime 9/9; item
  runtime 3/3; player replay 7/7; Hot Codex runtime 26/26; focused Pyright zero
  errors.

### Next bounded cleanup after spatial-effect freeze

Do not interleave these with the water/material contract regeneration:

1. remove the fallback/shadow policy registry and bare instrumentation
   assertion from `dnd/ai/runtime/controller.py`;
2. replace remaining owned-domain `getattr` probes with declared protocols or
   exact type narrowing;
3. give `ActionOutcomeProfile` and `DamageRollProfile` one dependency-neutral
   owner and delete the engine/AI JSON bridge;
4. centralize repeated character-grant install/rollback scaffolding behind the
   existing transactional grant-applier authority.

### 2026-07-30 — post-spatial production cleanup

- Removed the native-AI controller's private fallback policy registry.
  Controller construction now receives the one explicitly composed registry;
  assignment refresh cannot silently rebuild a second policy universe.
- Replaced the remaining audit-listed owned-object probes with declared
  surfaces: `SensesView`/`BaseBlock.get_senses`, exact spell narrowing,
  explicit event-union narrowing, typed ability-score access, appearance-owned
  configuration application, and neutral runtime behavior protocols.
- Moved `AdvantageStatus` to `dnd/core/roll_types.py` and moved
  `OutcomeResolution`, `OutcomeApplicationScope`, `DamageRollProfile`, and
  `ActionOutcomeProfile` to `dnd/core/action_outcomes.py`. Engine action
  discovery and AI decision epochs now carry the same immutable profile
  instance; the two per-row JSON dump/validate bridges and duplicate AI models
  are deleted.
- Added `CharacterGrantInstallation`, the one exception-safe authority for
  resource contributions plus bound action/handler and numerical-modifier
  installation. Fighter, Barbarian, Sorcerer, and active origin appliers use
  it; the private Fighter contextual-modifier helper and repeated manual
  resource/action/handler rollback blocks are gone. Scheduled Extra Attack,
  Remarkable Athlete, and active origin grants use the canonical deterministic
  grant id and receipt builders.
- Direct regression:
  `test_action_surge_installation_rolls_back_resource_when_binding_fails`
  proves a failed behavior bind publishes neither resource nor action.
  `test_engine_and_policy_share_one_outcome_profile_instance` proves there is
  no engine-to-AI clone, while the hot epoch regression observes zero
  `ActionOutcomeProfile.model_validate` bridge calls.

### 2026-07-30 — class-feature parallel-authority finding

- The canonical character composer installs permanent class features through
  exact `ContentRef` grant-applier bindings and source-owned receipts.
- Thirty old `BaseCondition` feature classes still contain complete imperative
  installers for the same modifiers, handlers, resources, and actions. None is
  constructed by production code; only a small set of legacy-oriented tests
  still invokes them. Their classes are retained by the catalog solely as
  behavior-identity carriers.
- This is a real second construction path: the old conditions use name-level
  `add_resource`/`remove_resource` and action registration, while the canonical
  composer uses source-owned contributions and exact UUID cleanup. Applying an
  old condition can erase another class/source contribution during removal.
- Close-out action: replace those fake persistent-condition identities with
  explicit structural class-feature declarations, keep their existing content
  IDs and authored metadata, move action/reaction dependencies to those
  declarations, delete the imperative condition bodies, and rewrite the few
  behavioral tests to install features through source-owned grants or canonical
  character materialization. No compatibility alias remains.

## Final handoff

The roll-result, generated-contract, and bounded spatial-effect handoffs are
complete. The repository-wide cleanup closeout remains open until section E and
the production-authority continuation below are complete.

### 2026-07-30 — post-spatial reconciliation

The spatial-effect tranche closed several findings that were still red in the
independent re-scan:

- content-set and built-in artifact digests are deterministic across processes;
- collection/import breakage introduced by moved runtime modules is repaired;
- the dependency-boundary allowlist includes the new cold spatial-effect leaf;
- event and SDK artifacts are regenerated and pass `--check`;
- the action-overlay regression is green;
- condition rejection invokes subclass cleanup and rolls back provisional
  runtime state;
- every legacy zone, spike, and environmental interaction path has been hard
  cut to the canonical spatial-effect owner;
- `dnd/scenarios/evaluation/compatibility.py`,
  `dnd/scenarios/ai_validation_arenas.py`, and `server/arena_mode.py` are gone;
  `dnd/scenarios/__init__.py` is inert.

The bounded spatial handoff hashes are:

- SDK: `fa789d0ceaba411b26c39b7e7a811f04da0b80246bda84e3600af9551f3740b7`
- player replication:
  `7a991b0ca4808e788893d2f8ceece46791a984f912e9236f53e09c121881fab3`
- event:
  `2e7e98cc04b8dee0c8217a7c49d3b0ef78c818f42cff4d59834e27152577ae68`

The remaining cleanup is not spatial architecture:

1. remove the fallback/shadow native-AI policy registry;
2. replace remaining owned-model reflection with declared narrowing surfaces;
3. finish canonical-JSON/digest single ownership;
4. remove the duplicated engine/AI outcome-profile model and JSON bridge;
5. decouple custom policy candidate admission from the bundled policy rules;
6. finish the maintained per-file test census and the 74 non-exact
   engine-book migrations;
7. only then prune lower-risk empty parameter boilerplate, SDK blanket exports,
   and stale documentation.

### 2026-07-30 — replacement post-spatial freeze

The four bounded production cleanups named above are now closed:

- native AI receives one explicit policy registry and has no fallback/shadow
  registry;
- audit-listed owned-model reflection is replaced by declared surfaces or exact
  type narrowing, including the last generic enum boundary;
- engine and AI share the one immutable outcome-profile model without a JSON
  bridge;
- active class/origin grant appliers use the shared exception-safe
  installation transaction for resources, actions, handlers, and numerical
  modifiers.

While exercising the isolated frontend against this freeze, terminal settlement
exposed a separate multi-character defect. The settlement projector compared
one character's holdings with the generation-global set of persisted item
bindings, so every multi-character deployment failed at game end. The
projector now authenticates exactly one binding for each item in the character
being settled while allowing other deployed characters' bindings to coexist.
`test_terminal_settlement_scopes_persisted_bindings_per_character` reproduces
the former failure with two materialized premades and proves both resulting
holdings revisions contain only their own exact item identities.

The old high-cardinality policy artifacts retain their deterministic choice,
candidate-factoring, instrumentation, and bounded-work assertions. Their
hardware-dependent 3.5/5.0 ms pytest thresholds were removed: repeated
isolated runs varied between 4.2 and 6.0 ms on the same code and those gates
were not product behavior. Broader AI latency instrumentation remains in the
runtime and its dedicated infrastructure tests.

Replacement wire/content identities:

- SDK:
  `8b305373aeaf57be720dffccc62ad2dc4565b7423ab083a90912859db9515cbd`
- player replication:
  `7a991b0ca4808e788893d2f8ceece46791a984f912e9236f53e09c121881fab3`
- event:
  `98708547e749ea40be7b564e212be64a515a5ab30c74130f8fa9b61e50aa01f5`
- generated TypeScript source:
  `78b21abda2e0e17b9f9fb29c77d75860a2290574e7650a56ddf0f3c630294ae1`
- content set:
  `68a8c5e453b1c0b4b5711468d9db54d6c43c04150093eccb80e858ebf5ed724d`
- content catalog:
  `4682851f157694efca7953bb398ceea5a575147da4549774123dd6f96c86fe74`

The remaining broader rescan work is deliberately separate from the spatial
and four-item closeout: retire the unused imperative class-feature condition
bodies, decouple custom policy candidate admission from bundled policy rules,
finish the maintained per-file test census, and then prune low-risk export and
documentation residue.

### 2026-07-30 — final production-authority reconciliation

The remaining production correctness and duplicate-authority findings from the
independent re-scan are now closed:

- The thirty unreachable imperative permanent-class-feature condition
  installers are deleted. Exact structural feature declarations plus
  source-owned grant appliers are the only permanent feature authority.
- Condition rejection and removal are transactional across subclass-owned
  state, completion publication, modifiers, handlers, child identities, and
  global registration. Failed character materialization likewise destroys
  provisional items, bindings, entity indexes, handlers, and light sources.
- Origin innate spellcasting and structural grants use the shared
  `CharacterGrantInstallation` boundary; constructor, behavior-bind, and
  unsupported-reaction failures publish no resource/action/handler residue.
- Native AI assignment distinguishes expected validation/policy rejection from
  engine execution failure. Authoritative engine failures propagate instead of
  being converted into an ordinary rejected action.
- The custom tactical policy builds neutral candidates independently of the
  bundled Basic policy rules. Basic policy applies its own data-driven
  admission specification at its own boundary.
- Ordinary `BonusDash` declaration now uses the canonical `BaseAction`
  declaration path and its effective costs. No action-local constructor can
  bypass action overlays or dynamic costs.
- `Entity.initiative` is no longer a stale Dexterity snapshot.
  `initiative_bonus` derives live Dexterity plus independent initiative
  modifiers, and encounter rolls consume the same value.
- Canonical server JSON, datetimes, SHA-256, and directory capability hashing
  have one owner. The duplicate `server/game_directory/canonical.py` facade is
  deleted.
- Frozen dataclass exception subclasses on terminal/history boundaries are
  replaced by ordinary typed exceptions with stable `args`, copy, and pickle
  semantics.
- Hosted/local terminal settlement uses exact repository filters rather than
  repeated Python scans or bare `next`. Local staged retries authenticate the
  incoming evidence and both replay digests before reusing a pending commit.
  The regression proves a conflicting retry is rejected and the exact retry
  reaches settlement and recovers after restart.
- The production-only unimplemented Aegis feature declaration is gone.
  Fail-closed coverage now injects a fixture-only declaration instead of
  polluting the public content set.
- Dead `Invisible.can_see_invisible`, handler-source lookup, optional-bool
  parser, write-only composition receipt data, and deprecated executable test
  wrappers are removed.

The remaining items from the broad scan are explicitly classified rather than
silently left ambiguous:

- server observation-journal timings measure projection/cache/SSE work and are
  separate from native AI policy instrumentation;
- recipe parameter models are the authenticated construction schemas, including
  intentionally empty closed schemas;
- the TypeScript package barrel is its public import surface, not a second
  decoder or protocol authority;
- reflection used for Python callable metadata, Pydantic model metadata, or
  fixed owned-field iteration is not gameplay duck typing;
- `ConditionApplicationPolicy` now carries both replace-existing and
  most-potent-active semantics and is not a single-member placeholder.

Current verification before the per-file census:

- collection: 3,419 tests, zero collection errors;
- complete Pyright scope over production plus AI/architecture/engine/
  progression tests: zero errors and zero warnings;
- event generator `--check`: green;
- SDK generator `--check`: green;
- TypeScript SDK build: green;
- TypeScript SDK tests: 81/81 green;
- standalone local lifecycle: 15/15 green before the final focused retry
  assertion; the deterministic staged-retry case is green independently.

### 2026-07-30 — maintained-suite census and final source freeze

- Enumerated 301 maintained Python test files and ran each file in its own
  Pytest process. The current-tree result is 301/301 files and 3,418/3,418
  tests green, with zero skips, xfails, xpasses, collection errors, or
  unmeasured open failures.
- The census exposed a real test-harness race in staged terminal recovery:
  pytest ended the encounter from its own thread while the ASGI activation
  coordinator was still publishing its opening event batch. The fixture now
  waits for activation and mutates the encounter on the TestClient event loop;
  the exact former failure is green in five consecutive runs and the complete
  lifecycle file is 15/15 green.
- The native-AI terminal-persistence fixture no longer uses an unbounded random
  one-versus-three matchup. It uses a fixed dice stream and a canonical
  one-versus-one authored roster while retaining real native AI, death,
  settlement, objective replay, subjective replay, and history coverage. The
  exact test is green in three consecutive runs at roughly 29–31 seconds.
- Event generator `--check`: green.
- TypeScript SDK generator `--check`: green.
- Full Pyright: zero errors, warnings, or informational diagnostics.
- TypeScript SDK build: green.
- TypeScript SDK tests: 81/81 green.
- `git diff --check`: green.

Final frozen identities:

- SDK:
  `7c68b65172c69fa5098b250c2f66ae1d81143227f3c686a57b5f9f7d96b635a9`
- player replication:
  `7a991b0ca4808e788893d2f8ceece46791a984f912e9236f53e09c121881fab3`
- event:
  `98708547e749ea40be7b564e212be64a515a5ab30c74130f8fa9b61e50aa01f5`
- generated TypeScript source:
  `ff28a2212ad03c52694b3b87493314e9573b660e10438d90aba292f554a094c9`
- content set:
  `f8c4bc7bc287812178f5b8c97926622048c819c86e7f23912e475df39e094baf`
- content catalog:
  `38f7683dda0e3ba179882a030048fd25a514f170e99b252a4ac353c4e2df5e7d`
  (schema 7; 670 public definitions, 205 presets, 867 safe
  presentations).

The codebase-audit close-out is complete.

### 2026-07-31 — coordinated normal-port validation

- Restarted the standalone backend once from the frozen source and retained
  the existing Vite process.
- Direct `:8000` and proxied `:5173` catalog reads agree on schema 7, content
  set `f8c4bc7bc287812178f5b8c97926622048c819c86e7f23912e475df39e094baf`,
  catalog `38f7683dda0e3ba179882a030048fd25a514f170e99b252a4ac353c4e2df5e7d`,
  670 public definitions, 205 presets, and 867 safe presentations.
- NeuroClient's exact live gates are green: zero icon blockers; 141 profiled
  condition identities and 141 lifecycle rows; 240 declared/245 expanded
  effects; deterministic compiled presentation bindings; action-bar smoke;
  and a real two-persistent-character setup with independent controllers,
  saved-roster CAS, exact saved encounter, and the closed-hazard deployment.
- No concrete backend or frontend gap remains in this close-out tranche.
