# Global native spell, class and authoring audit

2026-10-16. Worktree: `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.

The original scan found **eight new correctness finding groups and one measured
performance finding**. There are **36 reproduced failing scenarios**, grouped
by cause rather than described as 36 independent systems. **GA-04 and GA-08's
five spell scenarios are now repaired**; the other **31 scenarios across six
correctness groups remain strict expected failures** pending separate repair.

Follow-up status: the user-authorized GA-P1 Paladin aura repair is now implemented;
see the [repair report](PALADIN_AURA_LOCAL_REFRESH_FIX_REPORT_2026-10-16.md).
The audit baseline and searched-source counts below are retained as the original
before evidence. The follow-up also fixes a separately reproduced aura recovery
listener mistake using existing committed damage/healing events.

The subsequent [spell repair report](SPELL_TARGET_ADMISSION_REPAIR_REPORT_2026-10-16.md)
records the GA-04/GA-08 repair and reproduced siblings: 30 existing SRD spells,
seven production files and 33 function owners. All 152 new regressions pass;
the bounded 25-file qualification passed 670 tests with the 31 unrelated
strict expected failures. Both plan and implementation received independent
anti-slop and anti-OOP review. Original findings below describe the before state.

## Ranked findings

The table is ordered by recommended repair value and reach. Findings are P2:
the admission failures require an actual refusal at the stated boundary; the
remaining cases affect specific lifecycle/authoring inputs or unnecessary work.
Scenario count alone is not evidence for a more severe priority.

| Priority | ID | Confirmed problem | Original failing scenarios | Current status |
| --- | --- | --- | ---: | --- |
| P2 | GA-08 | Refusing an individual spell target application still permits damage, healing or Bless | 4 | Repaired |
| P2 | GA-01 | Class and authored monster actions commit benefits despite their own EFFECT refusal | 11 | Pending |
| P2 | GA-02 | Item uses commit healing, buffs, coatings or torch changes despite their own EFFECT refusal | 12 | Pending |
| P2 | GA-03 | Rejected feature conditions leave registered actions or resources | 4 | Pending |
| P2 | GA-04 | Rejected Constitution Enhance Ability condition still grants temporary HP | 1 | Repaired |
| P2 | GA-05 | Transferred lit torch still illuminates its previous carrier | 1 | Pending |
| P2 | GA-P1 | Paladin aura refresh enumerates unrelated actors on live change boundaries | Separate work-count experiment | Repaired |
| P2 | GA-06 | Rejected character loadout leaves unowned items in the public item registry | 2 | Pending |
| P2 | GA-07 | Strength-only armor requirement is accepted but produces no movement penalty | 1 | Pending |

### GA-08: per-target spell refusal

**Repaired in the spell follow-up**, including 25 additional spell identities
across GA-04/GA-08's combined five-spell starting inventory. The linked report
records the closed 30-spell inventory and native refusal/positive controls.

The earlier repaired admission matrix refuses the **cast root**. This audit
allows that root and refuses only CAST_SPELL/EFFECT events with an actual
`application` membership: the individual target/dart boundary.

Native outcomes with fixed dice:

| Spell | Actual result after target refusal |
| --- | --- |
| Magic Missile | All three refused darts still deal 15 total damage |
| Acid Splash | Refused recipient still takes 4 damage |
| Bless | Refused recipient still retains Bless |
| Mass Heal | Refused recipient still receives 25 HP |

Owners: `dnd/core/base_actions.py::_apply_target_batch`,
`dnd/spells/evocation.py::MagicMissile._apply` / `MassHeal._apply`,
`dnd/spells/conjuration.py::AcidSplash._apply`, and
`dnd/spells/enchantment.py::Bless._apply`.

Magic Missile mutates before its target EFFECT; the other reproduced paths
continue after their target EFFECT has been canceled. `_apply_target_batch`
observes the canceled result after those mutations. A canceled child also
cannot authorize a new condition merely because its parent root was admitted.

Repair direction: honor each existing target application's native admission
before committing its mechanics, including each dart. Retain the existing
application membership and damage/healing/condition handlers. The regression
requires a refused recipient to remain unchanged; it does not prescribe whether
the aggregate cast result should be canceled or successful. Other recipients
and paid-cost policy must be preserved. The four reproduced spells are a
confirmed lower bound, not a complete count of affected legacy spell roots.

### GA-01: class and monster action EFFECT admission

All eleven native registered actions have admitted controls and refused cases:

| Provider | Action | Benefit incorrectly retained after refusal |
| --- | --- | --- |
| Fighter | Second Wind | Healing |
| Fighter | Action Surge | ActionSurging condition |
| Barbarian | Rage | Raging condition |
| Sorcerer | Dragon Wings | Flight condition |
| Sorcerer | Elemental Affinity Resistance | Elemental resistance condition |
| Sorcerer | Quickened Spell | MetamagicActive condition |
| Sorcerer | Convert Slot to Sorcery Points | Sorcery point credit |
| Sorcerer | Convert Sorcery Points to Slot | Spell-slot credit |
| Authored Priest | Divine Eminence | Divine Eminence Active |
| Authored Knight | Leadership | Leadership Used and activated aura |
| Skeleton archer | Mark Target | Concentrating, Mark Cooldown and recipient Marked |

Owners are the corresponding action `_apply` bodies in
`dnd/classes/fighter.py`, `rage.py`, `sorcerer.py`,
`dnd/monsters/traits.py`, and `skeleton_abilities.py`.

These are real `create_character` builds or authored creature factories, not
isolated replacement actions. The tests execute registered native templates.
Refusal reaches the action's actual BASE_ACTION/EFFECT boundary.

Repair direction: move the existing benefit mutation behind that action's
admission; use the current condition/resource APIs. Spell-slot/sorcery point
credits are effects, while previously paid costs are separate. No refund is
asserted or recommended solely because a late EFFECT was refused.

### GA-02: item uses mutate before their own EFFECT

All twelve action variants were executed through `execute_use_action`:

- Healing Potion, Haste Potion, Greater Invisibility Potion, True Seeing Potion.
- Fire, Lightning, Basic Poison, Concentration Fire and Timed Fire weapon coats.
- Ember Quiver activation with an equipped bow and equipped quiver.
- Portable torch ignition and extinguishing.

Canceled uses still heal, install conditions or change torch state. A canceled
Concentration Fire coat also leaves Concentrating. Ember Quiver's CAST_SPELL
boundary and the other actions' BASE_ACTION boundaries were tested separately.

Owners: the potion and `_ApplyWeaponCoatAction._apply` implementations in
`dnd/items/consumables.py`, `dnd/items/spell_items.py::EmberQuiverActivation`,
and `dnd/items/torches.py::IgniteTorchAction` / `ExtinguishTorchAction`.

Repair direction: admit each existing action before its native heal,
condition/concentration, coating or light mutation. Keep actual item charge,
stack consumption and action costs at their existing payment boundaries; the
tests deliberately do not require refunds. This is not an item resource revision
or event-history problem.

### GA-03: refused feature membership leaves grants

Applying each condition through `Entity.add_condition`, then refusing
CONDITION_APPLICATION/EFFECT, leaves no active membership but still grants:

| Condition | Orphan grant |
| --- | --- |
| SecondWindFeature | `second_wind` resource and Second Wind action |
| ActionSurgeFeature | `action_surge` resource and Action Surge action |
| LuckyFeature | `luck_points` resource |
| RampageAvailable | Rampage Bite action |

Owners: `dnd/classes/fighter.py`, `dnd/classes/feats.py`,
`dnd/monsters/traits.py`, followed through the existing prepared-condition owner.
This is a rejected **condition** boundary, distinct from executing an already
granted action in GA-01.

Repair direction: install grants at admitted membership commit and clean them
through that same condition's exact ownership. Reuse the existing prepared
condition lifecycle rather than scanning all actions/resources to guess which
ones to remove.

### GA-04: Bear's Endurance temporary HP after rejection

**Repaired in the spell follow-up.** The complete Constitution roll/grant now
waits for the native condition commit. Own-condition and later concentration
refusal both preserve the previous temporary HP and exact sustain.

`dnd/spells/transmutation.py::EnhanceAbilityEffect._apply` phases its condition
to EFFECT, then grants Constitution's 2d6 temporary HP without checking refusal.
The spell correctly reports cancellation and the condition is absent, but the
recipient retains 8 temporary HP with fixed dice 4,4. The admitted control grants
the expected condition and 8 temporary HP.

Repair direction: grant temporary HP from the existing admitted condition commit
hook. Its ordinary provisional ability modifier already has ownership rollback;
the missing boundary is the temporary HP grant.

### GA-05: lit torch transfer retains the old carrier's light

In a dark map, ignite a carried torch at (2,2), then transfer it through
`Inventory.transfer_to` to a carrier at (15,2). Transfer succeeds and the item
owner changes. The torch stays lit, (2,2) remains VERY_BRIGHT, and (15,2) remains
DARKNESS. No veto or invalid command is needed for this case.

`dnd/items/torches.py::Torch.ignite` fixes the light anchor to the initial
carrier; `_on_drop` cleans it, but ordinary inventory transfer takes another
committed holding path in `dnd/blocks/inventory.py::Inventory.transfer_to`.

Recommendation: keep the torch lit and reanchor its exact light contribution to
the new carrier on committed transfer. If transfer should instead extinguish
torches, that is a small explicit behavior decision. The regression allows
either policy and requires only that the former carrier stop emitting that
torch's light. Preserve rejected-transfer behavior and unrelated light sources.

### GA-P1: live Paladin aura refresh scans the world

**Repaired in the follow-up.** The measurements in this section are the original
baseline; the linked repair report records the implementation and matched after
measurements, with zero world enumeration and unrelated removal attempts.

A level-10 Paladin has three auras and only its owner locally present. Native
work counts for adding Poisoned to the owner, changing a distant actor's faction,
or moving the owner one tile:

| Distant actors | Global entity enumerations per operation | Remote membership removal attempts |
| ---: | ---: | ---: |
| 1 | 3 | 3 |
| 25 | 3 | 75 |
| 100 | 3 | 300 |

The local membership apply count stays 3 for condition/faction changes and 6 for
movement. Movement already uses nine existing `_occupants_at` calls. Remote
movement, owner turn start and remote turn start each produce **zero** such
enumerations/removal attempts in all three sizes. Removal attempts here do not
mean 300 real retained conditions were destroyed.

Baseline live owner: `dnd/classes/paladin.py::PaladinAuraRoot.on_owner_placement_committed`,
plus its broad faction-change triggers. The apparent turn-start loop in
`PaladinAuraZone._create_zone_turn_start_handler` is dormant because TURN_START
is not declared in its trigger kinds; it is **not** a measured hot-path finding.

Repair direction: filter irrelevant faction events and refresh existing local
zone occupants plus exact retained members through current area ownership.
No new manager, whole-world reconciliation pass or encounter cache is needed.
Measure this change using the same native operations before claiming gains.

The maintained diagnostic is
`tests/manual/global_paladin_aura_refresh_performance.py`; raw environment and
18 operation rows are saved in
`GLOBAL_NATIVE_PALADIN_AURA_WORK_COUNTS_2026-10-16.jsonl`.
These are measured work counts, not an elapsed-time or whole-engine speedup claim.

### GA-06: rejected character build leaves registered environmental items

An explicit CharacterBuild loadout containing `environment.directional_wall` or
`environment.wall_torch` raises the current ownership validation error. The actor
is discarded, but an unowned item remains observable through public
`BaseItem.get_all_items()`. This finding does **not** claim the item was deployed
or that environmental props should be legal character inventory choices.

Owners: environmental wrappers in
`dnd/content/items/authored_item_builders.py`, their builders in
`environment_item_builders.py`, and failure cleanup in
`dnd/content/characters/builds.py` / `dnd/entity.py::discard_uncommitted`.
These builders ignore the supplied actor source UUID; source-based actor cleanup
therefore misses the provisional item.

Repair direction: preserve rejection while disposing of the exact provisional
materialization, even if its source differs from the actor. Alternatively reject
environment-only loadouts before allocating them. Propagating the source UUID
is appropriate only where the item really belongs to that source. Do not add a
global registry sweep to every successful character build.

The retained regression includes an unknown-item rejection control; an actual
longsword build also succeeded during the audit. Private dummy-template registry
residues were not promoted to extra gameplay findings.

### GA-07: strength-only authored armor metadata is inert

A wearable definition with `strength_requirement=15`,
`stealth_disadvantage=False`, and no explicit item properties materializes and
equips successfully on a Strength-10 actor, but leaves speed at 30. Passing the
same definition through existing `with_armor_penalties` produces speed 20.

`dnd/content/items/authored_item_builders.py::_build_wearable` only synthesizes
`ArmorPenalties` when stealth disadvantage is true. The strength field itself
has no runtime fallback. Maintained heavy armor currently sets stealth
disadvantage, so this is an accepted authoring configuration gap, **not** a claim
that current Chain Mail lacks its ordinary penalty.

Repair direction: compose existing ArmorPenalties when either authored penalty
needs it, preserving an explicitly supplied property. No additional rules system
is required.

## Coverage and limits

The file-level inventory is
`GLOBAL_NATIVE_SPELL_CLASS_AUTHORING_COVERAGE_2026-10-16.csv`. Its selected-scope
and native-evidence columns distinguish search hits from actual body reads and
executed scenarios. A body entry means the named selected implementation was
inspected; it does not mean every method or rule branch in that file was read.

| Searched domain | Python files | Source lines |
| --- | ---: | ---: |
| Spells | 24 | 31,780 |
| Classes | 11 | 9,206 |
| Character authoring/progression | 16 | 10,212 |
| Item authoring | 14 | 4,179 |
| Item runtime | 14 | 5,669 |
| Monsters/abilities | 17 | 10,863 |
| Content-system composition | 21 | 5,488 |
| Total | 117 | 77,397 |

These totals describe searched source, **not** complete manual or gameplay
coverage. Additional shared owners were followed for concrete candidates and
are separately labeled in the inventory.

Searches covered broad entity/condition/event enumeration, history reconstruction,
admission ordering, direct condition/resource/action mutation, ownership cleanup,
dynamic lookups/imports and accepted authoring fields. A bounded constructor
check imported the six direct domains and found no unknown explicit keyword
names in calls resolving to Pydantic models through module globals, with no
module-import failures. That check does not prove field consumption or resolve
every dynamic call; GA-07 is an example of an accepted field that can be inert.

Additional investigated cases were not promoted:

- Heroism's fear cleanup and temporary HP already use admitted commit ownership.
- Aid's provisional modifiers and Magic Weapon's tracked contribution have owners;
  the search hits alone did not demonstrate modifier rollback leaks. Aid's
  separate target-admission defect was reproduced and repaired in the follow-up.
- Holy Aura/Turn Undead/Preserve Life selection, restoration targeting, Daylight
  darkness overlap and Sunburst darkness cleanup enumerate on cast/discovery.
  Their existence alone does not establish recurring hot-handler cost.
- Authored creature possession mode correctly gates the inspected shield/equipment
  callers. Partial possession construction has provisional cleanup.
- Metadata bootstrap reflection is not interchangeable with gameplay handler
  dispatch; no generic ban on every source-search hit was inferred.

The earlier turn-history, Fireball-stage history and residue ancestry candidates,
and deferred shared temporary-HP damage accounting, remain in the earlier owned
state report. They were not counted as new discoveries. Existing repaired
catalog findings were also not relabeled as new.

## Regression evidence and review

The two new files are:

- `tests/engine/test_global_native_audit_regressions.py`.
- `tests/progression/test_global_authoring_audit_regressions.py`.

The original default rewritten-assertion run finished with **35 passed, 36 strict xfailed
in 7.01s**. An independent `--runxfail --assert=plain` run produces **35 passed,
36 failed**; failures are at the desired state invariant, not setup errors.
Native admitted controls accompany every action/condition/item variant, with
explicit refusal witnesses. Failed expressions use bounded scalar snapshots.

Existing controls: **235 passed**, comprising 170 in the spell-root admission,
fixed-torch/discovery, direct character/Fighter/Barbarian/Sorcerer, and native
Cleric/Paladin/Wizard feature/interaction suites (15.67s), plus 65 creature roster,
carried-gear and preset cases (6.18s). The latter are
`test_goblin_roster.py`, `test_roster_carried_gear.py`, and
`test_monster_presets.py`. These controls do not constitute a full repository
test pass. Ruff passes for all three new Python files; the worktree diff check
is clean.

Anti-slop and anti-OOP reviewers independently checked their assigned runtime
and authoring boundaries and approved the native regression artifacts. A
separate monitor tracked scope, honest coverage and the regression boundary.
All three roles approved the original audit artifacts. Review corrected a five-action
Sorcerer coverage count, refined selected-handler scope labels, and downgraded
configured-creature evidence to body inspection. GA-04 and GA-08 have since been
repaired as linked above; the six remaining correctness groups await separate
repair. All proposed directions above reuse current handlers, conditions,
resources and ownership boundaries.
