# Spell target admission and condition commit repairs

2026-10-16. Implemented in the existing spell worktree under the
[reviewed plan](plans/SPELL_TARGET_ADMISSION_AND_COMMIT_REPAIR_PLAN_2026-10-16.md).

## Result and exact scope

Repaired **30 existing SRD spells**, including Call Lightning's retained strike.
Spell target rejection now stops the affected damage, healing, condition, push
and direct rain consequences. Target condition and concentration rejection use
existing owned preparation/commit APIs. Enhance Ability's temporary HP and
Divine Word's lethal branch now wait for their condition's committed admission.

The batch changes **seven production files and 33 function owners**, plus one
private selected-branch flag on DivineWordEffect. Against this task's start,
the production delta is **138 added / 68 removed lines**. Earlier uncommitted
work is excluded from that count and preserved.

| Production file | Added / removed | Changed function owners |
| --- | --- | --- |
| dnd/spells/abjuration.py | +10 / -6 | Aid._apply; BeaconOfHope._apply |
| dnd/spells/conjuration.py | +4 / -0 | AcidSplash._apply; _apply_call_lightning |
| dnd/spells/enchantment.py | +33 / -28 | Bane._apply; Bless._apply; HoldMonster._apply; HoldPerson._apply; Sleep._apply |
| dnd/spells/evocation.py | +56 / -13 | BurningHands._apply; ConeOfCold._apply; DivineWord._apply; DivineWordEffect._apply; DivineWordEffect._commit_application; FlameStrike._apply; GustOfWind._apply; LightningBolt._apply; MagicMissile._apply; MassCureWounds._apply; MassHeal._apply; MassHealingWord._apply; PrayerOfHealing._apply; PrismaticSpray._apply; Shatter._apply; Thunderwave._apply |
| dnd/spells/illusion.py | +17 / -13 | ColorSpray._apply; Fear._apply; HypnoticPattern._apply |
| dnd/spells/necromancy.py | +5 / -1 | BlindnessDeafness._apply |
| dnd/spells/transmutation.py | +13 / -7 | CreateOrDestroyWater._apply; EnhanceAbilityEffect._apply; EnhanceAbilityEffect._commit_application; Slow._apply |

These are 28 spell `_apply` methods, one existing shared Call Lightning helper,
and the `_apply`/commit pair on each of two conditions. The two commit methods
are newly supplied native hooks. No shared BaseAction/SpellAction/Entity,
event-dispatch, resource, schema or client implementation was edited by this
batch. The private `_lethal` flag retains Divine Word's selected preparation
branch; it is not exported or inferred from event history.

The [scoped source/test diff](SPELL_TARGET_ADMISSION_REPAIR_SCOPED_DIFF_2026-10-16.patch)
compares task-start copies with the final files. It includes only these seven
production files and the two test files below; the ordinary Git HEAD diff also
contains earlier work and should not be mistaken for this batch's accounting.

The other modified documentation artifacts are the reviewed plan, this report, and
the original global audit's follow-up status. No new spell identity or feature
was added.

## Native fixes

The straightforward damage/healing/push branches return their actual canceled
EFFECT before performing consequences. Existing save timing and saved damage
fractions are retained. Call Lightning's one guard covers its initial bolt and
the actual registered retained action.

Magic Missile opens each dart's EFFECT before rolling/dealing damage. Results
are attached to that admitted event with `with_updates`, without a second
EFFECT dispatch. Application identity/order, successful sibling commit facts,
reported damage and the single paid cast are preserved. The native test refusing
only ordinal 1 observes [0,1,2], two admitted commits, 10 actual/reported damage
and one action/slot payment.

Retained spell conditions use `apply_owned_condition` instead of hand-creating
concentration and linking a condition after it has independently committed.
That retains the old exact sustain when target condition or concentration
admission fails. Bane and both Holds retain their admitted successful-save
replacement policy through their existing saved branch. Their failed-save
branches use prepared ownership. Pending target/concentration admission now
leaves prior sustain present until the existing owned commit boundary.

Enhance Ability retains its provisional advantage modifier with native rollback
ownership. The entire Constitution temporary-HP roll/grant runs in condition
commit, so both its own EFFECT refusal and later concentration refusal preserve
the previous temporary-HP grant and sustain.

Review caught the same irreversible-preparation problem in DivineWordEffect
after the initial plan approval. Its own EFFECT refusal or an old-condition
removal veto could leave the recipient dead with no admitted new condition.
Both reviewers approved the explicit two-function amendment before those edits.
The selected lethal branch now runs in condition commit; rejected replacement
preserves the prior exact condition, HP and life state.

Gust keeps its admitted root-owned wind field when an individual immediate push
is refused. Create Water similarly keeps its independently admitted water
surface while rejecting the direct RainWetEffect lease. These are existing
distinct owners, without special global exceptions.

## Tests and evidence

New file: `tests/engine/test_spell_target_admission_repairs.py`, **152 native
cases** covering the whole closed inventory and interactions:

- Admitted/root-refused/all-targets-refused/mixed recipient cases, observing
  native HP, maximum HP, life, position, conditions and application commit facts.
- Eight retained spells with refused target EFFECT, target condition and later
  concentration; exact previous Haste/concentration identity survives.
- Admitted all-saved Bane and both Hold replacement controls.
- Enhance Ability's grant and refused preparation/concentration controls.
- Divine Word's admitted lethal and two rejected condition/replacement controls.
- Hold Person's separate single-target admission boundary.
- Deterministic Prismatic color selection with standard RNG state restored.
- Direct rain versus independent water membership, and real retained Call
  Lightning/Sunbeam actions as failure and clean-control paths.
- Mass Heal's remaining 700-HP pool after spell-target or lower HEAL refusal;
  target refusal retains blindness/deafness, while the separately admitted spell
  retains its previous cure behavior when lower healing is refused.

The valid original149-case pre-edit baseline was **64 passed, 85 failed**.
The later three-case Divine Word amendment baseline was **1 passed, 2 failed**,
recorded separately after some approved target-guard edits but before its
condition-owner edits. Invalid early multi-recipient/save fixtures were corrected
and excluded from these counts.

After repair: **152 passed in 22.89s**. Independent anti-slop validation also
passed all152 (25.01s). Both actual-code reviews approved the complete scoped
production diff. The adherence monitor independently checked all33 owners and
the separate initial/amendment approval records.

In `tests/engine/test_global_native_audit_regressions.py`, only GA-04 and GA-08's
five spell scenarios lost their strict expected-failure annotations. All
**31 unrelated class/item/authoring scenarios remain strict expected failures**.
The old file's actual checks are unchanged. Its header now distinguishes
repaired and pending cases.

The final bounded broad qualification passed: **670 passed, 31 strict xfailed
in 119.57s**, across the 25 files below. This total includes the 152 new cases;
the counts are not additive. All expected failures are the unrelated pending
audit cases. Ruff passes for both touched test files; the worktree diff check
is clean. This is not a full repository test claim.

Run from the worktree with the configured Python environment:

```bash
python -m pytest -q \
  tests/engine/test_spell_target_admission_repairs.py \
  tests/engine/test_global_native_audit_regressions.py \
  tests/progression/test_global_authoring_audit_regressions.py \
  tests/engine/test_spell_catalog_audit_admission_regressions.py \
  tests/engine/test_spell_families.py \
  tests/engine/test_spellcasting.py \
  tests/engine/test_roster_support_spells.py \
  tests/engine/test_bg3_rank_one_two_spells.py \
  tests/engine/test_high_level_spell_controls.py \
  tests/engine/test_high_level_spell_fields.py \
  tests/engine/test_high_level_spell_payloads.py \
  tests/engine/test_high_level_spell_review_regressions.py \
  tests/engine/test_call_lightning_area.py \
  tests/engine/test_prepared_condition_lifecycle.py \
  tests/engine/test_spell_handler_ownership_regressions.py \
  tests/engine/test_spell_catalog_repair_interactions.py \
  tests/engine/test_spell_reaction_admission_repairs.py \
  tests/engine/test_condition_transform_ownership.py \
  tests/progression/test_wizard_features.py \
  tests/progression/test_wizard_owned_packets.py \
  tests/progression/test_spell_damage_affinity_contributions.py \
  tests/progression/test_spellcasting_source_action_propagation.py \
  tests/progression/test_paladin_aura_local_refresh.py \
  tests/progression/test_paladin_features.py \
  tests/progression/test_paladin_interactions.py \
  --tb=short --assert=plain
```

The anti-slop and anti-OOP reviewers independently approved both the written
plan (including its bounded amendment) and the final production implementation.
The separate adherence monitor checked all 33 changed owners, original versus
amendment baseline accounting, and preservation of prior work, and approved
scope/mechanics. It independently verified the qualification XML: 701 cases,
zero failures, 31 expected failures.

## Limits retained explicitly

This is an admission/ownership repair, with current spell definitions retained.
In particular, Divine Word's existing admitted lethal implementation still uses
99999 force damage; this batch prevents rejected preparation from executing it,
and does not claim to correct that separate damage-versus-instant-death rule
behavior or its other admitted HP-tier mechanics.

Failed-save target/concentration rejection is covered by the retained-spell
matrix. The existing `ensure_concentration` edge behavior on an admitted saved
branch whose concentration is then refused is unchanged, and is not presented
as exhaustively repaired by those tests. Independent ground/field effects and
already paid costs retain their own admission/payment boundaries.

Other audit findings and previous deferred candidates remain separately recorded.
The completed Paladin aura repair is preserved.
