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
- [ ] Audit the 74 non-exact engine-book test migrations and either map each
      behavior to maintained coverage or migrate its unique assertions.
- [ ] Run every affected test file individually.

### B. Correctness and direct regressions

- [ ] Add a direct regression proving one Attack declaration dispatches
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

- [ ] Replace dangerous blind exception swallowing with explicit propagation or
      logged observer isolation according to the owning boundary.
- [ ] Extract the duplicated analytics numeric accumulator.
- [ ] Correct stale saving-throw documentation and redundant encounter
      lifecycle predicates.
- [ ] Consolidate decision-epoch timing into canonical AI instrumentation.
- [x] Audit the production reachability of `ai.subjective.policy_agent`; delete
      it and its wrapper-only tests if it is a retired executor.
- [ ] Remove remaining duplicate policy selection/gating implementations when
      they encode the same semantics.
- [ ] Finish the event/SDK generator single-owner cleanup.

### D. Generated contract freeze

- [x] Regenerate the event contract and TypeScript SDK once after the dice-event
      contract is closed.
- [x] Run generator `--check`, SDK build, SDK tests, and focused Python contract
      tests.
- [x] Record final contract hashes here before any coordinated service restart.

### E. Maintained-suite sweep

- [ ] Enumerate maintained Python test files.
- [ ] Run each file individually; never invoke an unbounded repository-wide
      Pytest command.
- [ ] Fix implementation failures or update/delete genuinely retired tests.
- [ ] Run focused Pyright on every touched production/test module.
- [ ] Run architecture gates, `git diff --check`, and record the final census.

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

## Final handoff

Pending.
