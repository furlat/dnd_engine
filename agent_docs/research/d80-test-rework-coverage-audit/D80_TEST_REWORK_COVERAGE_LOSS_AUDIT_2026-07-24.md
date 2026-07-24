# D80 test-rework coverage-loss audit

Date: 2026-07-24  
Primary commit: `d80dab27adda8fdd1949048b5a9fd1e37cedd10d` (`big test rework - a few refactors ongoing`)  
Adjacent migration commits reviewed: `a9883fa`, `b865acf`, and the later AI-test migration in `3fdc402`

## Bottom line

The old Haste test really did exist. Two distinct things made that fact less
protective than it looked:

1. `examples/test_haste.py` was moved to `to_archive/examples/test_haste.py`.
2. Its attack helper always spent Extra Attack before another regular Attack.
   It therefore covered `Attack -> Extra Attack -> Haste Attack`, but never the
   user's failing ordering:

   `Attack -> Haste Attack -> pending Extra Attack`

The current bug was not created by the July test rework. The generic
`+1 actions` Haste design dates to `b57849d6`, and its action-count heuristic
could destroy a still-pending Extra Attack batch. The test migration removed an
important executable specification from the maintained suite, while the old
specification itself omitted the bad permutation.

The larger audit confirms that `d80dab27` was not a behavior-for-behavior test
migration. It created a broad and assertion-dense engine-book suite, but its
parity gate worked in only one direction: every new `EB-*` test needed a matrix
row. Nothing required every legacy file, logical case, ordering, or assertion
to have an active replacement.

This should be described accurately as **migration/parity loss and archival of
legacy executable specifications**, not as removal from an already-running
default pytest suite. Before `d80dab27`, `pyproject.toml` already contained:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
```

There were zero tracked files under `tests/` at the parent commit. The old
`examples/` scripts were manually executable specifications, not default
pytest collection.

## Complete audit artifacts

The following generated ledgers are part of this report:

- `d80_test_surface_changes.tsv` — all 245 test-surface records changed by the
  commit, including additions, modifications, renames, and the archived shell
  test.
- `d80_file_inventory.tsv` — every displaced Python example/test surface,
  archive destination, rename similarity, case/assertion counts, and leading
  active candidates.
- `d80_case_coverage_map.tsv` — every old logical case and its three closest
  active candidates.
- `d80_assertion_coverage_map.tsv` — all 3,462 old assertions, exact normalized
  AST matches, and closest non-exact candidates.
- `d80_legacy_migration_manifest.tsv` — the central reviewed disposition for
  all 1,458 old logical selectors, including an exact maintained selector only
  where review evidence exists.
- `d80_legacy_migration_unresolved.tsv` — the unresolved-selector report. It is
  now header-only because the reviewed queue is closed.
- `d80_mapping_summary.txt` — deterministic aggregate counts.
- `generate_coverage_map.py` — regenerates the lexical inventory, case,
  assertion, file, and summary artifacts from Git history and the current
  active test tree.
- `manage_legacy_migration_manifest.py` — rebuilds the reviewed manifest from
  explicit maintained ledgers and validates complete old-selector coverage,
  unique rows, valid dispositions, and live selector existence.

The similarity columns are audit aids, not proof of semantic equivalence. Only
an explicit behavior review can promote a candidate to a true replacement.

Regenerate with:

```bash
uv run python agent_docs/research/d80-test-rework-coverage-audit/generate_coverage_map.py
uv run python agent_docs/research/d80-test-rework-coverage-audit/manage_legacy_migration_manifest.py --build
uv run python agent_docs/research/d80-test-rework-coverage-audit/manage_legacy_migration_manifest.py
```

The first command regenerates lexical evidence. The `--build` command
incorporates only explicit reviewed-ledger evidence, and the final command
validates the checked-in result without rebuilding it. Lexical candidates
never become live mappings automatically.

The final reviewed manifest contains all 1,458 displaced logical selectors:
446 active, 978 strengthened, 21 stale, 13 retired, and **0 unresolved**.
The audit originally stopped with 725 selectors still requiring manual review.
That queue was closed one case at a time: 630 gained strengthened maintained
coverage, 80 were proven to have an adequate active replacement, 7 old
expectations were classified as stale with a live replacement, and 8
implementation-shaped surfaces were deliberately retired with a live
contract-level replacement. `manage_legacy_migration_manifest.py` validates
that every row is unique and that every maintained selector still exists.

## Exact inventory and count reconciliation

### Commit-level change inventory

| Surface | Count | Meaning |
|---|---:|---|
| Changed test-surface records | 245 | Complete `d80dab27` inventory |
| Renamed records | 166 | 156 Python files under `examples/`, 9 empty `interactive_ruleset/tests/**/__init__.py` markers, and 1 server shell test |
| Added active Python files | 72 | 68 collectable `test_*.py` files plus 4 package markers |
| Modified test/support modules | 7 | Existing `dnd/**/test_*` and `server/test_*` support modules |
| Deleted test-surface records | 0 | Rename detection found archival moves rather than deletions |

Of the 166 renames, 154 were byte-identical. Twelve changed while moving:
11 Python surfaces and `examples/server_tests/test_session_api.sh`. The Python
rows and exact similarity percentages are in `d80_file_inventory.tsv`.
Notable semantic edits include Lucky determinism, a Fireball half-damage bound,
condition/action-economy expectations, and skeleton spell/action variants.

### Old logical behavior surface

| Metric | Count |
|---|---:|
| Displaced Python example/test surfaces in the map | 165 |
| Conventional test scripts | 150 |
| Manual/live scripts without a conventional test filename | 5 |
| Empty package markers | 10 |
| Top-level named `test_*` cases | 1,407 |
| Decorated anonymous `@test("label")` cases | 51 |
| Total mapped logical cases | 1,458 |
| Assertions in all old functions/helpers | 3,462 |

The separate static scan reported 156 Python files and 1,414 `test*`
functions. Both figures are compatible with this map:

- 156 is the number of renamed Python files under `examples/` alone. The
  generated inventory additionally includes 9 empty
  `interactive_ruleset/tests/**/__init__.py` markers.
- The raw 1,414 function count includes 1,407 top-level `test_*` cases, six
  helper/decorator functions literally named `test`, and one nested
  `test_processor` helper.
- The logical-case map excludes those seven helpers and adds the 51 real cases
  hidden behind `@test("...") def _():`, producing 1,458 cases.

### New active suite at `d80dab27`

| Metric | Count |
|---|---:|
| Python files under `tests/` | 72 |
| Collectable test files | 68 |
| Named test cases | 780 |
| Assertions, including helpers | 9,320 |

The new suite was deeper in assertion volume. It was not one-to-one in behavior.

### Current dirty-worktree snapshot

At the final regeneration during this audit:

| Metric | Count |
|---|---:|
| Active test files | 244 |
| Active cases | 2,482 |
| Active assertions, including helpers | 20,458 |
| Old assertions with an exact normalized-AST match | 956 / 3,462 |
| Strong lexical case candidates | 445 |
| Partial lexical case candidates | 613 |
| Weak lexical case candidates | 333 |
| Lexically unmapped candidates | 67 |

Even an exact normalized assertion can be coincidental if fixture semantics
differ. The 956 figure is an upper bound on easy structural reuse, not a
coverage guarantee. Conversely, the 67 lexically unmapped candidates are not
unresolved coverage: every old selector has a reviewed manifest disposition.

## Why the parity gate missed this

`engine_book/parity_matrix.md` explicitly said:

- the 139 top-level `examples/test_*.py` files were the minimum regression
  floor;
- script/profiler-style files still counted as baseline behavior;
- rows marked `covered` represented 1:1 parity.

However, `tests/engine_book/test_book_integrity.py` checked:

- every active engine-book function had a parity-matrix row;
- every matrix row naming an engine-book test pointed to a live function;
- written chapters did not advertise `TBD` or `missing`;
- engine-book tests no longer remained in `examples/`.

It did **not** check:

- that all 139 top-level legacy files appeared in the matrix
  (`examples/test_legacy_migration.py` was omitted);
- that every legacy test function mapped to an active function;
- that all custom-runner cases were represented;
- that old assertions or important action orderings survived;
- that a feature-level replacement exercised the same variants.

This allowed a matrix row to call “Haste”, “Jump”, “action overrides”, or
“inventory actions” covered while retaining only a representative happy path.

## Prioritized migration manifest

### P0 — defects found and fixed during this audit

#### 1. Haste and Extra Attack ordering

Displaced selectors that provided only partial historical coverage:

- `examples/test_haste.py::test_2_haste_extra_attack_suppression`
- `examples/test_haste.py::test_3_haste_action_surge`
- `examples/test_haste.py::test_7_haste_slow_action_surge`
- `examples/test_haste.py::test_10_haste_mid_turn_action_surge`

Historical omission:

- no case spent the Haste action before a still-pending Extra Attack;
- the `_attack_until_done()` helper deliberately chose Extra Attack first.

Current active replacements:

- `tests/manual/test_125_haste_restricted_action.py::test_haste_attack_and_normal_attack_batches_are_order_independent`
- `...::test_haste_dash_does_not_poison_later_action_surge_attack_batch`
- `...::test_haste_and_action_surge_preserve_both_extra_attack_batches`
- `...::test_slow_keeps_haste_and_surge_actions_but_suppresses_extra_attacks`
- `...::test_replacing_haste_preserves_the_new_conditions_owned_budget`
- `...::test_haste_weapon_attack_can_use_an_equipped_off_hand_weapon`

The implementation now uses an explicit, condition-owned restricted budget
rather than a generic extra action plus remaining-action heuristic.

Validation:

```bash
uv run pytest -q tests/manual/test_125_haste_restricted_action.py
# 20 passed
```

Two related findings must remain distinctly classified:

- **Off-hand Haste weapon attack:** found while reviewing the new grant model,
  fixed in the current worktree, and protected by the active test above.
- **Use an Object:** a pre-existing/unimplemented rules surface, not a d80
  regression and not an old lost test. No current action owns a typed
  Use-an-Object restricted kind. The unused enum branch was removed rather
  than shipping an action that could never be discovered. Implement this only
  when the engine has a real costed Use-an-Object action.

The old Haste file now fails 10/10 because it asserts the intentionally removed
generic `+1 actions` model and a named `Incapacitated` child rather than the
current direct lethargy transform. It is historical evidence, not a test to
reactivate unchanged.

#### 2. Gust of Wind path restoration

Displaced selector:

- `examples/test_gust_of_wind.py::test_gust_terrain_reactive_paths`

It initially reproduced a current defect:

- targets before wind: 9;
- targets with difficult terrain: 6;
- targets after concentration removal: still 6.

The terrain modifier was removed and `_paths_dirty` was set, but the spatial
movement cache was not invalidated. The current worktree now fixes that and
adds:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_045_gust_terrain_removal_restores_cached_move_targets`

Validation:

```bash
uv run pytest -q tests/engine_book/test_chapter_15_spell_families.py \
  -k gust_terrain_removal_restores_cached_move_targets
# 1 passed

uv run python -m pytest -q \
  to_archive/examples/test_gust_of_wind.py::test_gust_terrain_reactive_paths
# 1 passed
```

#### 3. Generated override variants charged named resources twice

The 51 displaced action-override cases had only representative active
replacements. Restoring the execution matrix exposed a current normalization
defect: `_get_costs_for_level()` copied `alt_extra_costs` into a generated
variant's concrete costs, but the variant retained the transform and
`effective_costs` appended it again. A legal command could therefore be
rejected as unaffordable or spend the same named resource twice.

Generated variants now clear the cost transforms after normalizing their
executable costs. `test_126_action_override_runtime.py` maps all 51 old IDs
into 26 deterministic active cases covering discovery, execution, routing,
event hierarchy, target convolution, concentration ownership, AoE
finalization, upcasting, resource use, and same-turn cleanup.

#### 4. Slow lockout listened to only one action event family

The displaced Slow suite described the action-or-bonus-action restriction but
asserted only the ordinary-action-first direction. `SlowedEffect` listened
only for `BASE_ACTION`, while attacks, movement actions such as Jump, and
spells publish their own typed event families. A bonus-action Jump could
therefore leave the ordinary action usable, and other action families escaped
the same lockout handler.

The handler now observes the explicit `BASE_ACTION`, `ATTACK`, `MOVEMENT`, and
`CAST_SPELL` effect families and derives the lock from positive typed action
economy costs. Free, reaction, and movement-feet-only costs remain non-locking.
`test_126_slow_legacy_contract.py` restores all seven old groups and adds the
inverse direction, event-family, reset, direct-removal, and idempotent
constraint-lifecycle checks (14 active cases).

#### 5. Item action reconstruction erased the Wand of Fire's cast level

The Wand of Fire advertised a three-charge level-3 Fireball and a four-charge
level-4 Fireball. `SpellScroll.get_use_actions()` rebuilt each discovered
variant from the spell's base level and discarded the explicit template
`cast_at_level`, so both branches actually cast level 3. Their discovery
identities also collided. The archived test accepted either charge decrement
and did not assert spell level or damage.

Item-backed spell variants now preserve the explicit template cast level and
use distinct canonical machine identities. The active regression proves exact
three/four-charge consumption, 8d6/9d6 damage, no spell-slot consumption, and
no mutation or leakage between source templates.

#### 6. Command branches expired or acted outside their commanded turn

The displaced Cleric Batch 1 Command matrix did not preserve a deterministic
next-turn lifecycle assertion. Restoring it exposed three coupled defects:

- the one-round wrappers expired at the target's next turn before their
  `TURN_START/EFFECT` handlers could run;
- Halt and Grovel applied their turn denial or Prone behavior at cast time;
- Flee changed the grid directly, bypassing ordinary movement events and
  movement costs, and could consume a stale path cache.

The three branches now activate on the target's actual next turn start, remain
owned through that turn end, and remove themselves by exact UUID. Flee
refreshes the Entity-owned senses/path cache and executes the ordinary `Move`
pipeline, preserving costs, step events, and opportunity attacks. Halt and
Grovel install the same reaction-preserving turn-spent transform; Grovel
applies an independent Prone condition which survives the Command wrapper
until ordinary stand-up timing.

Validation:

```bash
uv run python -m pytest -q tests/manual/test_134_cleric_batch1_legacy_contract.py
# 16 passed

uv run python -m pytest -q tests/engine_book/test_condition_transform_ownership.py
# 13 passed

uv run pyright dnd/spells/enchantment.py dnd/creature_transforms.py \
  dnd/core/base_actions.py dnd/conditions.py \
  tests/manual/test_134_cleric_batch1_legacy_contract.py \
  tests/engine_book/test_condition_transform_ownership.py
# 0 errors
```

#### 7. Field Focus bypassed canonical item-event construction

`DeployFieldFocus` hand-built an `ActionEvent` and omitted
`source_item_uuid`, the frozen item presentation, and `item_charge_cost`.
Carried and floor Field Kits therefore completed successfully without
consuming their charge. The redundant declaration builder was removed so the
action uses `BaseAction`'s canonical item-event path. Both ownership routes now
prove one charge and one bonus action are spent while the ordinary action
remains available.

#### 8. `GridMap.clear()` left live floor items at stale locations

The destructive grid clear erased only `_object_positions` and
`_objects_by_position`. A live `BaseItem` retained its old `tile_uuid` and
continued to report the former location. The archived assertion checked only
the grid index half of the invariant. `GridMap.clear()` now snapshots its floor
objects and invokes the existing authoritative removal callback exactly once
before clearing indexes and tiles. This is O(number of floor objects) only on
clear/reset, not on gameplay paths.

### P1 — confirmed high-risk migration gaps

These are confirmed migration gaps, not merely low-similarity candidates.

| Displaced surface | Exact cases | Audit result | Maintained replacement |
|---|---:|---|---|
| `test_action_overrides.py` + `test_action_overrides_exec.py` | 51 | Representative coverage had omitted runtime combinations and exposed a real duplicate-resource-cost defect. | `test_126_action_override_runtime.py`: all 51 legacy IDs mapped into 26 deterministic cases. |
| `test_sorcerer_factory.py` | 77 | Feature representatives did not preserve the full level/config/slot/metamagic/Font/combat matrix. | `test_128_sorcerer_factory_legacy_contract.py`: all 77 IDs explicitly map to 44 behavioral executions plus one manifest test. |
| `test_inventory_use_actions.py` | 47 | Four cases had exact maintained coverage, one had a stale two-bonus-action fixture, and the remaining behavior matrix lacked exact active selectors. The audit exposed Wand cast-level and item-event/charge defects. | `test_131_inventory_use_actions_legacy_contract.py`: all 47 old cases explicitly map to 16 behavior selectors plus a manifest test. |
| `test_items_phase1_advanced.py` | 36 | Ownership/visibility representatives omitted the exact LOS, isolation, drop, capacity, destruction, transfer, and targetability matrix. | `test_131_advanced_item_world_legacy_contract.py`: all 36 old cases map to 12 behavior selectors plus a manifest test. |
| `test_tier1_spells.py` | 21 | Eight groups had exact maintained coverage; thirteen were missing. | `test_131_tier1_spell_legacy_gaps.py` restores the 13 gaps as 24 deterministic cases; 21 groups now resolve to 28 active cases. |
| `test_shatter.py` | 8 | No active test instantiated Shatter. | `test_126_shatter.py`: 8 groups restored as 12 deterministic cases. |
| `test_lightning_bolt.py` | 10 | No active behavior test instantiated Lightning Bolt. | `test_127_lightning_bolt.py`: 10 groups restored as 14 deterministic cases. |
| `test_slow.py` | 7 | The representative test missed bidirectional lockout and several event families; the audit exposed a real engine defect. | `test_126_slow_legacy_contract.py`: 14 cases, including typed event-family and lock-lifecycle regressions. |
| `test_jump.py` | 8 | Representative movement tests did not preserve the full Jump matrix. | `test_126_jump_legacy_contract.py`: 9 deterministic cases. |
| `test_two_weapon_fighting.py` | 8 | Slot/style representatives did not preserve execution and cleanup semantics. | `test_126_two_weapon_fighting_legacy_contract.py`: 9 deterministic cases. |
| `test_action_surge_extra_attack.py` | 4 | Recharge/scaling representatives omitted action-order matrices. | `test_126_action_surge_extra_attack_legacy_contract.py`: four one-to-one cases. |
| `test_barbarian_unarmored_defense.py` | 7 | No exact maintained matrix covered every armor/shield/ability combination. | `test_132_barbarian_unarmored_defense.py`: seven one-to-one cases using dependency-neutral enums. |

Run the custom-runner suites in their intended isolated mode:

```bash
uv run python -m to_archive.examples.test_action_overrides
uv run python -m to_archive.examples.test_action_overrides_exec
uv run python -m to_archive.examples.test_sorcerer_factory
uv run python -m to_archive.examples.test_inventory_use_actions
uv run python -m to_archive.examples.test_items_phase1_advanced
uv run python -m to_archive.examples.test_tier1_spells
```

Do not infer a regression from collecting `test_inventory_use_actions.py`
directly with pytest. That legacy file relies on its `run_test()` wrapper to
reset global registries between cases; direct pytest collection produces
cross-case pollution. Its intended runner is 47/47 green.

### P1 — stale high-level spell fixtures migrated with legal resources

Several archived suites create a now-correct level-5 generic caster and then
cast spells above level 3. `create_caster()` was changed to grant the
level-appropriate full-caster slot table; the old fixture no longer has
impossible high-level slots.

| Surface | Unadapted result | Maintained result | Migration |
|---|---|---|---|
| `test_antimagic_field.py` | 2 passed, 12 failed because level 5 has no level-8 slot | `test_128_antimagic_field.py`: 14/14 pass | Uses an explicit legal level-8 slot and preserves zone/block/suppress/restore/entry/exit/follow/concentration and lineage cases. |
| `test_disintegrate.py` | 3 passed, 4 failed because level 5 has no level-6 slot | `test_129_disintegrate.py`: 10/10 pass | Uses an explicit legal level-6 slot and preserves full/zero damage, kill, force type, range, upcast, and no-concentration cases. |
| `test_tier2_spells.py` | 10 passed, 13 failed for the same slot-fixture reason | `test_130_tier2_spells.py`: 27/27 pass | Uses explicit legal resources and retains Cone/Circle/Blight/PWK/Protection/Stoneskin matrices. |

Changing `create_caster()` back to a level-5 actor with every spell slot would
be the wrong fix. The tests should declare the capability they require.

### P2 — static review queue closed

`d80_case_coverage_map.tsv` remains a lexical audit aid, so its weak/unmapped
candidate counts must not be confused with reviewed coverage. The authoritative
case-level manifest has no unresolved rows. The former high-volume queue was
reviewed across spells, items, conditions, geometry and dice, perception and
privacy, reactions, AI/server/session behavior, map editing, class actions,
event lifecycle, and spatial-zone behavior. Where an archived fixture encoded
an obsolete implementation detail, the manifest records `stale` or `retired`
and points to the maintained behavioral replacement; it does not silently call
the old assertion covered.

## Adjacent migration commits

The rework did not end cleanly at one commit:

### `a9883fa` — `bringing back ai folder`

Thirty-six minutes after `d80dab27`, this commit moved three active Chapter 18
tests into `to_archive/tests/test_archived_cli_orchestration.py`:

- guarded Codex exec invocation;
- stream metrics/current-item trajectory;
- parent-marked AoE combat-log filtering.

The first two relate to the replaced CLI/AI implementation. The third is still
a privacy/visibility invariant and should remain represented by the current
subjective combat-log projection suite.

### `b865acf` — `new ai controller and codex wrapper`

This added the replacement external AI/controller architecture and active
manual tests 28–30. It is part of the immediate migration sequence and should
be reviewed together with the tests removed by `a9883fa`.

### `3fdc402` — later AI/server migration

This later wave removed manual 26/27 with the old tactical AI implementation,
added a much larger replacement test surface, and changed pathfinding
tie behavior. It explains the current stale exact-path golden in
`tests/manual/test_09_action_discovery_and_costs.py`: two equal-cost safe paths
remain valid, but BFS now selects the opposite side from the old Dijkstra heap.
That is a stale golden unless left/right determinism is itself a contract.

## Recommended enforcement so this cannot recur

1. Check in a machine-readable legacy-case migration manifest with one row per
   logical case, not one row per feature/file.
2. Give each row one of:
   - active replacement selector;
   - intentionally retired, with design reason;
   - blocked/stale fixture, with migration owner;
   - uncovered.
3. Make CI validate both directions:
   - every active parity test has a manifest row;
   - every non-retired legacy row resolves to a live active test.
4. Preserve ordering dimensions explicitly. For action economy, parameterize
   permutations instead of relying on helpers that always choose one action
   first.
5. Require effect tests to assert state, not only discovery or metadata. A
   charge-consumption test does not prove the item-bound spell damaged its
   target.
6. Keep custom-runner behavior out of `test_*.py`, or convert it to real pytest
   fixtures with an autouse global reset. A function-shaped test that is unsafe
   under pytest gives false confidence.
7. Never mark a feature family “covered” from a representative spell when the
   implementation contains distinct geometry, save, cleanup, or target-type
   branches.

## Validation performed during this audit

Focused, non-server validation only:

- current Haste restricted-action suite: 20 passed;
- fixed Gust path restoration: active replacement and archived selector pass;
- maintained action-override suite: 26 passed;
- maintained Sorcerer factory suite: 45 passed;
- maintained inventory item-use suite: 17 passed;
- maintained advanced item ownership/visibility suite: 13 passed;
- maintained tier-1 spell-gap suite: 24 passed;
- maintained Shatter suite: 12 passed;
- maintained Lightning Bolt suite: 14 passed;
- maintained Slow suite: 14 passed;
- maintained Jump suite: 9 passed;
- maintained two-weapon fighting suite: 9 passed;
- Action Surge + Extra Attack: 4/4 pass;
- maintained Unarmored Defense suite: 7 passed;
- maintained Antimagic Field suite: 14 passed;
- maintained Disintegrate suite: 10 passed;
- maintained tier-2 spell matrix: 27 passed;
- repaired AI runtime-performance file: 63 passed, with focused Pyright clean;
- public-manual structural selection: 106 passed, 1 failed, 144 deselected;
  the sole failure requires the absent canonical
  `engine_book/parity_matrix.md` source;
- reviewed migration manifest, rebuilt and then independently validated:
  1,458 selectors = 446 active + 978 strengthened + 21 stale + 13 retired +
  0 unresolved;
- manifest and unresolved report line counts: 1,459 and 1 respectively, so the
  unresolved report contains only its header.

No broad pytest run and no archived server-test batch were used.
