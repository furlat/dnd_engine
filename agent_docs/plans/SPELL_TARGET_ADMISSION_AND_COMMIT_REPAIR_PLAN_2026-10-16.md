# Spell target admission and condition commit repair

2026-10-16. Current worktree:
`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
The user requests detailed investigation, native test coverage, an exact change
plan, two independent reviews, then implementation. Production edits must wait
for anti-slop and anti-OOP approval of this concrete plan.

## Scope and starting evidence

Repair the remaining spell findings GA-04 and GA-08 and their natively reproduced
same-boundary SRD siblings. This is **30 existing SRD spells**: 29 have a missed
spell EFFECT admission, and Enhance Ability has a premature condition grant.
Call Lightning has both an initial cast and a retained activation affected by
one shared spell helper. Hold Person is single-target, unlike the other
per-target convolution roots; its actual single-target EFFECT also fails.

Other class, monster, item and character-authoring findings remain separate.
The repaired Paladin aura implementation, client, transport/schema, spell
catalog, supported-spell set and unrelated pending fixes are outside this batch.

Baseline source/positive-control/native refusal probes established each root
below. Their maintained regression file is
`tests/engine/test_spell_target_admission_repairs.py`; run it before production
edits and record desired failures separately from any invalid test setup.
The previous global-audit file already reproduces the original five spell
failures. All starting dirty work is preserved. Copies of the seven prospective
spell files and that existing test file are kept under
`/tmp/spell_admission_repair_before` to isolate this batch's delta from earlier
uncommitted work; no checksum/archive or Git reset is required.

## Exact production accounting

Only these **seven production files** are authorized by this plan. Each row
lists the existing code owner; no name switches in a shared dispatcher.

| File | Spell / owner | Failure and exact repair |
| --- | --- | --- |
| spells/abjuration.py | Aid._apply | Return its refused target EFFECT before preparing/applying Aid; use existing owned condition admission |
| spells/abjuration.py | BeaconOfHope._apply | Admit target EFFECT then use apply_owned_condition instead of manual condition/ensure/link |
| spells/conjuration.py | AcidSplash._apply | Return refused target EFFECT before rolling or applying acid damage |
| spells/conjuration.py | _apply_call_lightning | One canceled guard before damage rolls/HP mutation; covers CallLightning and its registered CallLightningStrike |
| spells/enchantment.py | Bane._apply | Honor target admission and use existing owned condition/concentration preparation; retain normal admitted-save replacement policy |
| spells/enchantment.py | Bless._apply | Open/check target EFFECT before condition/concentration; use apply_owned_condition |
| spells/enchantment.py | HoldPerson._apply | Honor single-target EFFECT, then owned condition/concentration; preserve admitted-save replacement policy |
| spells/enchantment.py | HoldMonster._apply | Same ownership repair at its per-target EFFECT, preserving admitted-save replacement policy |
| spells/enchantment.py | Sleep._apply | Stop on refused target EFFECT and use existing owned condition path |
| spells/evocation.py | MagicMissile._apply | Open/check each dart EFFECT before roll/damage; attach results with with_updates on that admitted event |
| spells/evocation.py | BurningHands._apply | Return canceled target EFFECT before damage roll/HP mutation |
| spells/evocation.py | LightningBolt._apply | Same target guard; preserve existing save/half-damage behavior |
| spells/evocation.py | Thunderwave._apply | Same target guard before both damage and forced movement |
| spells/evocation.py | Shatter._apply | Same target guard before damage |
| spells/evocation.py | ConeOfCold._apply | Same target guard before damage |
| spells/evocation.py | FlameStrike._apply | Same target guard before either damage component |
| spells/evocation.py | PrismaticSpray._apply | Same target guard before color selection and all existing color branches |
| spells/evocation.py | DivineWord._apply; DivineWordEffect._apply / _commit_application | Honor target EFFECT and owned condition admission; move the existing lethal mutation to condition commit using a selected-branch private flag; existing admitted HP-tier mechanics are not redesigned |
| spells/evocation.py | PrayerOfHealing._apply | Stop before healing-roll events and HP mutation |
| spells/evocation.py | MassHealingWord._apply | Same target guard; keep bonus-action cost and healing scaling |
| spells/evocation.py | MassCureWounds._apply | Same target guard; keep existing area selection and healing scaling |
| spells/evocation.py | MassHeal._apply | Same target guard before heal, pool debit, blindness/deafness cleanup; debit actual healing as before |
| spells/evocation.py | GustOfWind._apply | Stop direct recipient push after refusal; retain independent admitted root field/turn/entry behavior |
| spells/illusion.py | Fear._apply | Honor target EFFECT, then existing owned condition/concentration preparation |
| spells/illusion.py | HypnoticPattern._apply | Same target/condition/concentration repair; retain charm and damage-break handlers |
| spells/illusion.py | ColorSpray._apply | Honor target EFFECT then existing owned condition path; leave HP targeting budget/expiry intact |
| spells/necromancy.py | BlindnessDeafness._apply | Honor target EFFECT then existing owned condition path; retain chosen branch and repeat-save handler |
| spells/transmutation.py | Slow._apply | Honor target EFFECT then owned condition/concentration; preserve its existing save/repeat-save/cost transforms |
| spells/transmutation.py | CreateOrDestroyWater._apply | Stop direct RainWetEffect lease after target refusal; preserve the independent root-owned admitted water surface/dousing/drying |
| spells/transmutation.py | EnhanceAbilityEffect._apply / _commit_application | Keep provisional advantage ownership; move Constitution's complete roll+temporary-HP grant to admitted condition commit |

This is **28 spell _apply bodies**, **one shared spell-family helper**, and
**two conditions' _apply plus their existing-style commit hooks**: 33 function
owners, including two newly supplied commit methods. Prefix paths with `dnd/`.
No production changes to BaseAction, SpellAction, Entity, BaseCondition,
MembershipAreaCondition, damage delivery, resource payment or event dispatch.

## Admission and ownership rules

1. Retain existing root and child lineage/application identities, ordinals,
   ordered iteration, admitted application facts and aggregate result policy.
   A refused child can coexist with an admitted root and successful siblings.
   Do not create a central pre-effect spell executor or publish a second target
   EFFECT merely to attach result metadata.
2. Existing save-before-EFFECT paths retain their save timing/payload. Stop
   mechanics immediately when the spell's returned EFFECT is canceled. No fake
   saving throw, synthetic roll or general event-transaction layer is added.
3. Retained conditions use SpellAction.apply_owned_condition: prepare the target
   and sustain, commit the exact links/memberships, then publish. A target
   condition or later concentration rejection must leave previous sustain intact.
4. Bane/HoldPerson/HoldMonster previously establish concentration even when all
   admitted targets save. Preserve that accepted behavior explicitly: only
   after target EFFECT admission, their saved branch uses existing
   ensure_concentration; cleanup closes an empty new sustain as before. Their
   failed-save branch uses apply_owned_condition. Slow/Fear/Hypnotic Pattern
   retain their existing all-saved policy instead of acquiring a new rule.
5. Enhance Ability must not grant temporary HP during preparation, even if its
   own condition EFFECT passed: concentration may still fail later. Use its
   native commit hook, preserving the existing max-grant choice, provenance,
   duration and post-removal temporary-HP policy.
6. Late spell/condition refusal does not refund already paid action/slot/item
   costs. Successful siblings continue. Mass Heal's unchanged actual-healing
   debit allows later recipients to use the pool after either spell-target
   refusal or lower native HEAL refusal; unchanged cure policy is tested apart
   from spell-target refusal.
7. Direct rain leases and independent ground-water membership are different
   native owners. A refused direct rain recipient must receive no RainWetEffect;
   the admitted cast root still creates water. Gust likewise keeps its root
   field while refusing the direct child push. No per-spell engine exception
   or global exclusion list is needed.

## Regression matrix before and after

`tests/engine/test_spell_target_admission_repairs.py` covers:

- Every affected convolution root, excluding independent rain handling below:
  admitted, root-refused, all-children-refused and mixed refused/admitted
  recipients; check HP/max HP/life/position/conditions and native application
  commit facts. Real failure/success save inputs; low-HP Sleep/Color Spray/
  Divine Word recipients; actual wounded healing recipients.
  Prismatic color selection uses a seeded standard random state restored after
  each cast; fixed engine dice alone do not control its color selection.
- Eight retained concentration spells: target EFFECT refusal, target condition
  refusal and later concentration refusal; preserve the exact prior Haste and
  concentration UUIDs and all recipient state.
- Bane and both Holds: admitted successful-save controls retain the previous
  accepted concentration replacement behavior.
- Enhance Ability: admitted 2d6 grant, condition refusal, concentration refusal,
  and preservation of the existing lower temporary-HP grant on rejection.
- Divine Word: admitted lethal control, its own condition EFFECT refusal, and
  refused replacement/removal of an existing nonlethal Divine Word. Rejection
  must preserve life/HP and the previous exact retained condition. The original
  admitted force-damage lethality is retained; its damage-vs-instant-death rule
  behavior is not silently changed in an admission repair.
- Hold Person's ordinary single-target EFFECT refusal.
- Create Water direct-rain refusal while the independently admitted water field
  still exists; the direct RainWetEffect is the asserted recipient lease.
- Magic Missile's rejected middle dart: [0,1,2] application order, two successful
  commits, actual/reported damage match and exactly one action/slot payment.
- Real granted Call Lightning Strike with admission/refusal; retained Sunbeam
  Strike supplies a clean shared-boundary control. Preserve their source grants.
- Mass Heal's rejected first recipient leaves the full 700 pool for the later
  wounded recipient; lower HEAL refusal does likewise. Target refusal preserves
  blindness/deafness instead of curing the refused recipient.

Remove only GA-04/GA-08 expected-failure marks in the old global audit once their
five known spell scenarios pass. Its other 31 expected failures remain pending.
Do not relax assertions to obtain green tests. Fix invalid test setup separately
and record baseline failure counts only after admitted controls are valid.

## Qualification and review gates

1. Save this plan and verify the test baseline before production edits.
2. Anti-slop reviewer checks admission timing, repeat routing, accounting,
   unsupported scope and whether the proposed change adds redundant machinery.
3. Anti-OOP reviewer checks condition/resource/source ownership, provisional
   rollback, existing sustain, accepted-save policy and isolated mechanics.
4. Both must approve this exact plan before implementation. The independent
   plan-adherence monitor remains active through implementation and qualification.
5. Implement the closed seven-file change. Compare against task-start copies;
   record the actual changed functions, additions/deletions and test mapping in
   the repair report. Unexpected owner edits require explicit plan reconciliation.
6. Run repaired regressions and existing root-admission, spell-family, healing,
   sustained/repeat, hit/damage/wizard, condition-ownership and native Paladin
   regression lanes as relevant. Record real baseline failures instead of
   changing unrelated expectations. No full repository pass is assumed.
7. Obtain both actual-code reviews and adherence signoff. Update the original
   audit's spell finding status with exact repaired scope and qualification.

Additional artifacts are this plan, the repair report/accounting table and
bounded test/qualification evidence. No commit or push is requested.

## Pre-implementation gate record

Anti-slop and anti-OOP reviewers independently **approved this written plan**
before production edits. The plan-adherence monitor verified the closed
30-spell/7-file/31-function inventory and 149 native test cases.

The valid pre-edit test baseline is **64 passed, 85 failed**, with no setup
errors. Admitted, root-refusal, admitted-save and lower-heal controls pass.
The initial fixture attempt was corrected to upcast Blindness/Deafness and
Hold Monster for two actual recipients, isolate concentration-refusal scenes
from other automatic area recipients, and seed/restore Prismatic's standard RNG.
Invalid setup was not counted as spell evidence. Mass Heal explicitly retains
its existing cure behavior when the spell is admitted but lower healing is
refused. Implementation is now authorized under both reviews and the user request.

## Bounded condition-commit amendment

After the initial31-owner approval, the monitor reproduced a second premature
condition mutation in the already-listed Divine Word: rejecting its own
condition EFFECT leaves no membership but still kills a 10-HP recipient. The
same irreversible mutation can precede a refused old-condition replacement.
Neither the spell target guard nor apply_owned_condition can undo such a death.

Add only DivineWordEffect._apply and its _commit_application to the owner list
(final33, same30spells and7files), plus three native cases (final152). Store the
already-selected lethal branch as condition-owned preparation state and perform
the existing lethal mutation only on commit. Record this amendment's baseline
separately from the original149-case pre-edit run. Both reviewers must approve
this amendment before these two additional production owners are edited.

Amendment gate closed: anti-slop and anti-OOP both explicitly approved it before
the extra owner edits. Its independent pre-edit native baseline is **1 passed,
2 failed** (condition EFFECT refusal and previous-removal refusal), recorded
separately from the original149 cases. Implementation may proceed at final33
owners/152 cases; admitted lethal mechanics remain unchanged.

## Implementation and qualification complete

Implemented the closed amended inventory: **30 existing SRD spells, seven
production files, 33 function owners; +138 / -68 production lines** against
task-start copies. No shared-engine or client implementation was changed by
this batch. Both reviewers independently approved the final actual-code diff.
The separate plan-adherence monitor approved the final scope/mechanics and
independently verified the qualification XML (701 cases, zero failures,
31 expected failures).

All **152 new native regressions pass**. The 25-file qualification passed
**670 tests, with 31 strict expected failures** for the unrelated pending
class/item/authoring audit cases (119.57s). Only the five repaired spell xfails
were removed. The separate baseline/amendment history above remains intact.

The [repair report](../SPELL_TARGET_ADMISSION_REPAIR_REPORT_2026-10-16.md)
contains exact file/function/line accounting, the scoped source/test patch,
the complete qualification command and retained limitations. The original
audit now records GA-04 and GA-08 as repaired and preserves its original
before evidence. No commit or push was performed for this batch.

## Follow-up: incomplete dice override coverage (implemented)

The human requested verification of a direct-random/UUID/time/replay claim after
the completed repair above. Source inspection confirms a dice-control gap.
`fixed_dice_faces` replaces only `dnd.core.dice._randint`; direct calls to
Python's `random.randint` do not consume its queue. The cited spell line numbers
were stale in this worktree; the Fighter reference still matches.

Native witness: cast real Bless, then roll the recipient's Wisdom save inside
`fixed_dice_faces(10, 4)`. With Python RNG seeds 0 and 1, the original d20 is
10 in both runs, while Bless contributes respectively +4 and +2. A following
ordinary Dice d4 still consumes the queued 4 in both runs. The test restores
Python's prior RNG state. Thus the hook misses the rider rather than merely
using a different queue order. This is a temporary diagnostic, not a newly
maintained regression or evidence of a spell-admission regression.

### Exact reviewed production scope

Use one small face-generation function in the existing dice module, delegating
to the current `_randint` seam. Ordinary Dice and these raw rule faces use the
same function; retain `fixed_dice_faces`' existing scoped queue, nesting, range
and exhaustion behavior. This needs no RNG service, new condition hierarchy,
fake attack/save/healing rolls, recursive roll-result events or event dispatcher
changes. In particular a Prismatic d7 choice is a bounded random face, not a new
`Dice.value` type or a fabricated damage roll.

| File | Exact proposed owners | Existing direct calls / required behavior |
| --- | --- | --- |
| dnd/core/dice.py | New `roll_die_face`; Dice._roll; Dice._roll_with_advantage; Dice._roll_with_disadvantage | Delegate ordinary and supplementary faces to the existing hook; positive integer sides, inclusive 1..sides |
| dnd/spells/abjuration.py | _resistance_processor (2474) | One d4; retain save-only registration and one-use cleanup |
| dnd/spells/enchantment.py | Sleep.get_all_targets (1070); _bane_processor (1333); _bless_processor (1348) | Preserve cached/upcast HP-pool selection and both existing signed d4 result modifications |
| dnd/spells/divination.py | _guidance_processor (288) | One d4; retain check-only registration and one-use cleanup |
| dnd/spells/illusion.py | ColorSpray.get_all_targets (778) | Preserve cached/upcast HP-pool selection, immunity/visibility filters and current selection stage |
| dnd/spells/evocation.py | PrismaticSpray._apply (4017, 4020, 4021, 4023) | One d8; on 8 retain distinct d7 choices and existing duplicate reroll policy |
| dnd/classes/fighter.py | great_weapon_fighting_processor (358) | Reroll each eligible low primary weapon die once; preserve offhand/two-handed/versatile eligibility, extra packets and existing result evidence |

Closed inventory: **seven production files, 12 functional owners**
(eight existing rule owners, three Dice methods, one new face helper), covering
**11 direct randint call sites** in the six rule files. Only imports and the
existing hook's descriptive text may additionally change in those files. This
is a separate delta, not part of the completed 7-file/33-owner accounting.
Do not change rule amounts, admission boundaries, resource costs, event categories
or existing roll-modification ownership while repairing control of the faces.

### Native acceptance cases before any production edits

Add a focused `tests/engine/test_rule_dice_override_coverage.py`. Start with
real casts/registered handlers/weapon attacks and assert observable roll results,
HP-pool recipients, conditions and event modification evidence. Establish
desired failures before changing the named owners; keep valid admitted controls.

- Bless and Bane: fixed d20+d4 determines exact signed delta on both attack and
  save; an unrelated check consumes no rider face. Guidance/Resistance: exact
  d4 on their own roll category, no effect on the others, consumed once with
  normal condition/sustain cleanup. Include combined eligible handlers in their
  actual native dispatch order; assert totals rather than private call traces.
- Sleep and Color Spray: exact base/upcast pools, a boundary recipient fitting
  exactly and a following recipient excluded, repeated selection preserving
  its cached result without another roll, and existing immunity/visibility
  filters. Use explicit actor UUIDs when equal-HP order matters; preserve the
  current UUID tie-break rather than introducing a targeting policy change.
- Prismatic Spray: force each single color, color 8's distinct pair, and one
  repeated d7 choice followed by a distinct one. Assert the actual damage or
  condition, using the required saves/damage faces as well. An undersupplied
  queue must fail visibly instead of falling back to uncontrolled randomness.
- Great Weapon Fighting: actual two-handed/versatile attacks with low and high
  base dice, a low reroll that stays low (no second reroll), ineligible offhand
  or occupied-offhand cases, and unchanged extra damage packets. Assert final
  damage and modification evidence, not mocked handler calls.
- Existing dice controls: advantage/disadvantage, critical damage, nested fixed
  contexts, invalid/exhausted faces and restoration after exceptions. Repeat
  native scenarios under different saved/restored Python seeds: fixed faces
  must give the same rule result. No global monkeypatch or seed is the fix.

Run the new lane plus relevant cases in `test_dice_event_semantics.py`,
`test_spell_families.py`, `tests/progression/test_direct_fighter_progression.py` and the completed
152-case spell repair suite. Existing tests that patch `random.randint` for
these rules may be migrated to the native hook only as necessary, with explicit
file/case accounting; preserve their original gameplay assertions. Obtain
anti-slop and anti-OOP plan/code reviews and keep a plan-adherence subagent
active if implementation is requested.

### UUIDs, time and replay are separate boundaries

Fresh Event/Dice/DiceRoll/BaseObject defaults generate UUIDs; Event defaults and
phase transitions also generate current timestamps. Fixing dice faces does not
make independent live runs byte-identical. Sleep and Color Spray also sort
equal-HP candidates by UUID, so UUID variation can affect those tied selections,
not just serialized metadata. Controlled identities belong in focused fixtures;
this follow-up does not change production identity, time or target tie policy.

The current passive replay path is recorded initialization plus retained event
lineages (`dnd/player/recorded.py::decode_sequence`), decoded with
`PASSIVE_EVENT_REPLAY`, then projected/reduced. `event_record.decode_event`
requires recorded fields including identities/timestamp and does not execute a
spell or rebuild executable engine graphs. Public server recording separately
stores committed packet bytes (`server/recording.py`). Thus recorded playback
does not require rerunning RNG or reproducing newly generated UUIDs/timestamps.
This is evidence for these existing playback paths, not a claim that arbitrary
engine save/resimulation or every legacy replay module is supported.

Verification for this follow-up: the current native recording/reduction tests
`tests/player/test_spell_ownership_recording.py` and
`tests/engine/test_recorded_world_facts.py` pass **11 cases in 0.76s**. Older
manual tests still mention removed server replay modules; those names were not
used as evidence of a current implementation. No replay, schema, server, UUID,
clock or client production change is proposed for this dice-control gap.

A bounded broader search also found raw hit-die generation/short-rest healing in
`dnd/blocks/health.py` (109, 154), environmental interaction healing in
`dnd/items/environment_interactables.py` (645), and non-dice tie choices in
`dnd/core/values.py`. They are outside this spell/Fighter follow-up inventory;
do not describe its completion as global control of all engine randomness.

Plan-review status: anti-slop and anti-OOP independently **approved this proposed
addition**, verified the exact inventory and current replay source, and found
no blocking corrections. Anti-slop also independently reran the 11 recording
cases (all passed in 0.77s). These approvals cover the plan, not implementation.
At that gate the human had requested investigation and a plan update; no
production files or maintained tests had yet been changed for this follow-up.

### Dice follow-up implementation gate

The human subsequently requested implementation in this worktree. Both written
plan reviews above remain applicable; a separate adherence monitor is active.
The final 78-case native pre-production baseline is **28 passed, 50 failed in
13.81s**, with no setup failures. The monitor independently verified the XML:
40 desired assertion mismatches, nine Prismatic queue-range mismatches caused
by uncontrolled color selection, and one missing exhaustion exception. Earlier
invalid faction/advantage/filter fixtures were corrected and excluded.

Existing dice semantics, spell families, direct Fighter progression and content
recovery behavior tests pass before edits: **96 passed in 19.52s**. Task-start
copies under `/tmp/dice_override_coverage_before` will isolate this follow-up
from the prior dirty work. The exact active Counterspell fixture using the
retiring `abjuration.random` import will migrate to the native face hook;
production scope remains the reviewed seven files and 12 function owners.

### Dice follow-up implementation complete

Implemented exactly the reviewed production scope: **12 functional owners in
seven files, +29 / -27 production lines** against task-start copies. The allowed
`fixed_dice_faces` docstring is a 13th AST function segment with no behavior
change. All 11 raw rule calls use the existing hook through `roll_die_face`;
ordinary Dice, native handlers, pools, distinct-color selection and GWF remain
their existing owners. No excluded production area was changed.

The new test file has **90 cases**: the original 78 plus 12 new face-helper
boundary cases. The historical 28/50 pre-edit count above belongs to that
earlier fixture revision. After the first repaired run (74 passed, four fixture
assertions failed), the shared pool fixture explicitly computed its native
geometry and moved its four recipients into a diagonal cone. Color Spray
resolves a copied shape and leaves the authored shape uncomputed; the original
downstream assertion incorrectly inspected it. The earlier random-pool mismatch
had masked those assertions. This was a test-fixture correction, with no
production targeting/geometry change and no invented replacement baseline.

Two existing test functions migrated off the retired `abjuration.random`
attribute: the active Counterspell function's failed/successful-check scenarios
and the runnable archived Cleric Resistance scenario. Their original gameplay
assertions are retained. The complete archived Cleric file also passes. The
other archived Counterspell module cannot collect because it imports removed
`server.agent_runtime`; it is unchanged and excluded from passing counts.

Final bounded qualification: **373 passed across nine distinct files**:
90 new cases (17.14s), 259 existing dice/spell/Fighter/recording cases (56.40s,
including all 152 admission repairs), and 24 archived Cleric cases (2.01s).
These are three disjoint runs, not a full repository pass. Both actual-code
reviewers approved the implementation; independent runs passed 90 cases
(anti-OOP), 91 including the migrated Counterspell function (anti-slop), and
90 with the adherence monitor. Their counts overlap the qualification.
Both reviewers approved both test migrations; the adherence monitor approved
final source/test scope, documentation and accounting closure.

The [dice repair report](../DICE_OVERRIDE_COVERAGE_REPAIR_REPORT_2026-10-16.md)
records exact file/test accounting, scoped diff, run commands, remaining
randomness exclusions and the pre-existing legacy collection/lint limitations.
No commit or push was requested or performed for this follow-up.
