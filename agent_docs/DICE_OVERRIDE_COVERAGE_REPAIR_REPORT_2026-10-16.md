# Dice override coverage repair

2026-10-16. Implemented in the existing
`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine` worktree under the
[independently reviewed follow-up plan](plans/SPELL_TARGET_ADMISSION_AND_COMMIT_REPAIR_PLAN_2026-10-16.md#follow-up-incomplete-dice-override-coverage-implemented).

## Result and exact accounting

`fixed_dice_faces` now controls the supplementary faces for Resistance, Bane,
Bless, Guidance, Sleep, Color Spray, Prismatic Spray and Great Weapon Fighting.
A small `roll_die_face(sides)` function in the existing dice module delegates to
the existing `_randint` seam. Ordinary Dice also use it. Positive bounds,
inclusive faces, fixed queue exhaustion/range errors, nested restoration and
normal unoverridden randomness remain at that existing boundary.

The current task changes **seven production files, 12 functional owners,
+29 / -27 lines**. The existing fixed-context docstring is also updated, so an
AST comparison sees 13 function segments including that text-only change.
Module import cleanup accounts for the remaining lines.

| Production file | Added / removed | Functional owners |
| --- | --- | --- |
| dnd/core/dice.py | +12 / -5 | New roll_die_face; Dice._roll; Dice._roll_with_advantage; Dice._roll_with_disadvantage |
| dnd/spells/abjuration.py | +2 / -3 | _resistance_processor |
| dnd/spells/enchantment.py | +4 / -5 | Sleep.get_all_targets; _bane_processor; _bless_processor |
| dnd/spells/divination.py | +2 / -2 | _guidance_processor |
| dnd/spells/illusion.py | +2 / -3 | ColorSpray.get_all_targets |
| dnd/spells/evocation.py | +5 / -6 | PrismaticSpray._apply |
| dnd/classes/fighter.py | +2 / -3 | great_weapon_fighting_processor |

All **11 raw randint call sites** in these six rule files now use the same
face generator as ordinary Dice. The existing handlers still own signed d20
modifications, one-use cleanup, reroll eligibility and result evidence. The
spell owners still cache their HP pools and select recipients at the same
stage. Prismatic color 8 still draws two distinct d7 choices using its existing
duplicate reroll loop. No fake save/heal/damage roll events were introduced.

No action/event dispatch, resource policy, native condition ownership, spell
amount, targeting policy, UUID, timestamp, replay, server, schema or client
implementation changed. Source defaults still use Python's RNG; fixed contexts
control only these delegated calls, preserving its state during those calls.

The [scoped source/test patch](DICE_OVERRIDE_COVERAGE_SCOPED_DIFF_2026-10-16.patch)
compares task-start copies with final files. Earlier dirty work, including the
previous 30-spell admission repairs, is preserved and excluded from this delta.
Additional documentation changes are this report and the plan's completion
record; no commit or push was performed.

## Native regression coverage and fixture migrations

New file: `tests/engine/test_rule_dice_override_coverage.py`, **90 cases**.
Every case runs under two saved/restored Python RNG seeds, while the expected
rule faces remain identical:

- Signed d4 attack/save/check category filtering, one-use Guidance/Resistance
  cleanup, and native Bless/Bane/Resistance composition.
- Exact base/upcast HP pools, boundary recipients, cached selection, meaningful
  immunity/state filtering with all candidates inside the native shape, and
  explicit-UUID equal-HP order.
- All seven Prismatic single colors, their actual committed damage types or
  conditions, distinct two-color selection with and without a duplicate, and
  explicit queue exhaustion.
- Real GWF two-handed/versatile/offhand attacks: high dice unchanged, each low
  die rerolled once even when it remains low, occupied offhand exclusion and
  unaffected extra damage packets. Actual HP loss and modification evidence
  remain observable through the native attack pipeline.
- Ordinary advantage/disadvantage, critical dice, normal and exceptional nested
  queue restoration, no fallback after exhaustion, and the new raw-face helper's
  d1/d7/d20, nonpositive-bound and out-of-range acceptance cases.

Two existing test functions also changed, without changing their gameplay
assertions:

| File / owner | Migration | Added / removed |
| --- | --- | --- |
| tests/engine/test_content_recovery_behavior_semantics.py::test_counterspell_check_outcomes_spend_exact_committed_resources | Replace two module-random patches with native fixed faces: failed check plus seven level-5 missile darts, or a successful check that stops the spell. Remove unused imports and order the touched import group. | +16 / -23 |
| tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py::test_resistance_modifies_one_save_then_cleans_concentration | Replace split global patch/d20 hook with fixed d20+d4 faces; remove unused patch import. | +1 / -5 |

The new file adds 322 lines. No changes were needed in the existing spell-family
or dice-semantics tests: their Python/default-RNG patches still reach the
existing default seam. No global monkeypatch was added to the new tests.

## Baselines, final qualification and reviews

The pre-edit 78-case fixture revision produced **28 passed, 50 failed in
13.81s**, with no setup exception: 40 desired assertion mismatches, nine
Prismatic queue-range mismatches because its uncontrolled color left queued
faces in the wrong position, and one missing exhaustion exception. The existing
four-file dice/spell-family/Fighter/content behavior lane passed **96 tests in
19.52s** before production changes.

The first repaired 78-case run passed 74 and exposed four downstream Color Spray
fixture assertions. The test read an uncomputed authored shape, while native
target resolution computes a copy. The corrected fixture explicitly computes
ordinary geometry and places all four filtering candidates inside a diagonal
cone. No production geometry was changed. Those downstream assertions had been
masked by the pre-fix pool mismatch; the historical 28/50 figure is retained
for its original fixture revision, not presented as execution of every line of
the final version. The helper's 12 new API acceptance cases were added after
the helper existed and are not included in the old 78-case baseline.

Final bounded qualification: **373 passed across nine distinct files**,
collected from these three disjoint commands:

```bash
python -m pytest -q tests/engine/test_rule_dice_override_coverage.py --tb=short --assert=plain
# 90 passed in 17.14s

python -m pytest -q \
  tests/engine/test_dice_event_semantics.py \
  tests/engine/test_spell_families.py \
  tests/progression/test_direct_fighter_progression.py \
  tests/engine/test_content_recovery_behavior_semantics.py \
  tests/engine/test_spell_target_admission_repairs.py \
  tests/player/test_spell_ownership_recording.py \
  tests/engine/test_recorded_world_facts.py \
  --tb=short --assert=plain
# 259 passed in 56.40s, including all 152 admission repair cases

python -m pytest -q tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py --tb=short --assert=plain
# 24 passed in 2.01s
```

Runtime: `/home/tommaso/.cache/dnd-engine/venv/bin/python` (Python 3.13), with
source/tests in the Linux worktree above. This is a bounded qualification,
not a full repository pass. The reviewers' independent counts overlap these
files and are not added to 373.

Anti-slop and anti-OOP independently approved the written plan and the final
implementation. Anti-slop independently passed 91 cases (90 plus the migrated
Counterspell function); anti-OOP passed all 90. The separate adherence monitor
verified scope, baseline chronology and the corrected fixture, and independently
passed all 90. No additional production fixes were requested by review.
Both reviewers also approved the narrow archived Resistance migration;
anti-slop independently passed its complete 24-case file. The adherence monitor
approved final source/test scope, documentation and accounting closure.

Ruff passes for the new file and active Counterspell test file. The migrated
archived Cleric file retains its two pre-existing lint findings (import order
and unused Weapon import), confirmed against its task-start copy. The worktree
diff check is clean.

## Explicit remaining limits

This does not control all engine randomness. Raw hit-die generation/short-rest
healing (`dnd/blocks/health.py`), campfire healing
(`dnd/items/environment_interactables.py`) and non-dice tie choices
(`dnd/core/values.py`) remain outside the reviewed inventory.

Fresh-run UUIDs/timestamps remain variable, and equal-HP target ties retain
their UUID order. Existing passive playback reads recorded facts/packets;
no deterministic executable resimulation facility is introduced or required.

`tests/manual/test_50_counterspell_engine_contract.py` still imports the removed
`server.agent_runtime` package and cannot collect (confirmed in 0.07s). That
unchanged archived module retains its old module-random patches. Its import
failure precedes those tests and is excluded from passing counts; restoring
retired server test infrastructure is outside this dice task. Its rescued
active Counterspell counterpart is migrated and passes.
