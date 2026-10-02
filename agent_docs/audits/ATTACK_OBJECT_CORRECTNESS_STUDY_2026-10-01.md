# Attacks and destructible objects — correctness study

Date: 2026-10-01. Read-only production audit; no runtime implementation changes.

The user has clarified the intended endpoint: **delete `AttackObject`; an object
is another permitted target of the normal attack selected by the player.** Do
not retain an object executor hidden behind a renamed UI row. Grouping nearby
scenery separately is a UI affordance, not a different combat rule.

## Verified current behavior

A bounded runtime probe equipped longsword and longbow, activated the ranged
loadout, placed an adjacent clay stove, and added Extra Attack plus Haste. Under
both existing Haste policies the public action list exposed only
`Attack Object / action.attack_object` for the stove. A successful object strike:

- dealt 4 damage and spent the ordinary action;
- left the active stance `ranged`;
- left the Haste resource at 1 and extra attacks at 0;
- did not add `HasAttacked`;
- emitted `EventType.BASE_ACTION`, not an attack event.

This is not solely a playback defect. The source explains every result:

| Surface | Ordinary attack | Current object attack |
| --- | --- | --- |
| Selection | Equipped weapon slot, optional ability override | Hardcoded `MELEE_MAIN` |
| Target | Creature lookup and creature contact | Breakable placed `BaseItem` |
| Range | Weapon reach, normal/long range | `manual_object_contact` hard limit 5 ft |
| Resolution | d20, AC, outcome, crit, damage roll handlers | Automatic hit, direct damage rolls |
| Damage | `Entity.get_damages`, typed packets, size dice and roll hooks | `equipment.get_damages`, totals collapsed to primary type |
| Event | Cold `AttackEvent` with weapon snapshot | Generic action event |
| Stance | Selected slot activated on accepted hit or miss | Not changed |
| Haste | Named restricted discovery variants | Object collector never expands variants |
| Extra Attack | First committed ordinary action grants a batch | No `ATTACK` trigger, no batch |

Sources: `dnd/actions.py:1546,1769,1849,1944,2070,2182,2314,5196`;
`dnd/core/gridmap.py:2400`; `dnd/entity.py:2858,5219,6372`;
`dnd/actions_functional.py:214`; `dnd/blocks/equipment.py:798,1214`.

`AttackObject` is explicitly documented as auto-hit. There is **no target-object
AC field** on `BaseItem`; equipment armor AC is an unrelated wearer property.
Its breakability is optional `Health` plus targetability/integrity. Do not invent
an alleged existing object AC to explain this branch (`dnd/blocks/base_item.py:114,
695,718`).

The action-category value `ATTACK` alone does not make a generic action behave
like an attack: handlers subscribe to event types, phases and cost facts.

## One attack path, without making every item a creature

Use the existing attack pipeline and its cold event for all valid attack targets.
The minimum new data is explicit target eligibility and the small defense/contact
facts that differ between creatures and placed damageable objects. This should
be passive data/functions consumed by existing owners, not an `Attackable`
object hierarchy, a target adapter registry, or another parallel damage engine.

1. **Discover once per attack/cost variant**, then combine its known valid
   creature and object contacts. One longsword Attack row can target either.
   The same expansion must work for Extra Attack, the Haste variant and relevant
   authored natural/bonus attacks. Object lists must still come from subjective
   senses; do not scan all registered objects into the player list.
2. Preserve explicit target domain. Extending the current `ENTITY` collection
   globally would accidentally let creature-only spells and riders target props.
   Add the smallest typed permission/routing distinction needed for attacks to
   include objects; execution and discovery must consult the same declaration.
3. Resolve the selected target's **reachable contact**, not its anchor cell.
   Reuse full rotated occupancy and boundary support registration. Generalize the
   existing object contact query to the attack's actual reach/range and selected
   physical channel; leave hand-operated uses at 5 ft. Exempt only the targeted
   terminal obstruction from its own collision, not a different blocker in front.
4. Create one `AttackEvent` containing the chosen weapon/unarmed metadata,
   selected target identity/kind, observed placement/contact and effective costs.
   The target snapshot must not require a later creature lookup to recover an
   object's name or a multi-cell impact position. Keep source item snapshots cold.
5. Run existing validation, cost commitment, attack outcome, damage-roll event,
   loadout update and completion once. Only target defense and target damage
   application differ. Feed **typed damage components** through the existing
   `Health.preview_damage_components` owner for objects too; do not collapse
   bonus fire/poison into slashing. Preserve item damage cancellation and exactly
   one destruction cascade.
6. Delete object-attack registration, definition, template and executor; migrate
   tests/scenarios and presentation binding to the normal attack behavior. A
   bounded old-recording reader may decode historical generic events, but must
   not leave an alternate live command. `PickUp` and actual object interactions
   keep their object targeting path.

**Unarmed:** the ordinary attack implementation already resolves an empty slot
as unarmed and snapshots `Unarmed`/bludgeoning. Standard weapon-template discovery
currently removes a row when there is no weapon; Extra Attack's variants also
skip empty slots. Expose the same main-hand unarmed fallback to both target kinds
rather than letting deletion of `AttackObject` remove the only empty-hand object
attack. Render hands through the ordinary selected stance; do not add a new
manual weapon-swapping mechanic to fix this. An always-available unarmed choice
while holding a weapon would be a further deliberate content/UI choice, not an
implicit requirement of this refactor.

## Combat interactions which must survive

| Mechanic | Current owning path | Required preservation / object guard |
| --- | --- | --- |
| Ordinary action | `BaseAction._apply_action`, `Attack._apply_costs` | Invalid known/authoritative target is rejected before debit; late interruption keeps spent cost. One accepted attack debit regardless of target kind. |
| Extra Attack | `extra_attack_resource_processor` (`fighter.py:1178`) | First `ATTACK/EXECUTION` with a **positive ordinary actions cost** grants N-1; subsequent normal actions add a batch. It uses `ExtraAttacksGranted`, not `HasAttacked`. An object strike is now a real Attack action and must grant/spend these batches too. |
| Haste, both policies | `BaseAction.get_discovery_variants`/effective costs; `transmutation.py:824` | SRD permits weapon attack; BG3 Honour permits standard actions. One Haste resource use, no normal action debit and no Extra Attack grant. Haste before/after the ordinary batch must neither create nor erase it. |
| Action Surge | `fighter.py:925` and existing action transform | It adds an ordinary action. Each spent Attack action grants its full ordinary batch, including mixed creature/object targets. Do not reset the resource when target kind changes. |
| Off-hand | `Attack.adjust_cost_for_off_hand`, equipment damage | Default costs one bonus action; explicit caller costs, including empty child costs, override that default. No Haste replacement of a bonus action. Keep off-hand ability-damage rules. Current source does not gate ordinary off-hand attacks on a prior main-hand attack; do not claim SRD completeness or silently change that rule here. |
| Multiattack | `monsters/traits.py:517` | Composite spends its own action, children `costs=[]`; preserve prescribed slots/count/target restrictions. Do not grant an Extra Attack batch for each child. |
| Natural attacks | `monsters/traits.py:587` | Preserve authored natural range, physical access, ability and damage override; do not force every claw/bite through the carried sword. The current natural resolver temporarily substitutes unarmed data and invokes normal consequences; this is an existing seam, not license to create an item-specific copy. |
| Frenzied Strike | `classes/rage.py:926` | Same attack event/resolution with its existing Frenzied prerequisite and bonus-action cost. Extend target admission through the shared target support, not a duplicate object strike. |
| Opportunity attacks | `reactions.py:17` | Continue using Attack with reaction cost and StepMovement parent. Only moving enemy creatures provoke; extending attacked target kinds must not make ordinary props threaten or provoke. Window/Light/reach access and late barrier checks remain shared. |
| Range/pressure | `Attack.validate_range`, `check_ranged_conditions` | Both normal/long range and threatened ranged disadvantage use the selected attack, including objects. Reach works at the reachable object surface. |
| Roll features | `roll_d20`, AttackEvent execution, crit threshold | Preserve Lucky, crit threshold, Dueling/Archery/Defense/etc contextual data and reroll lineage. Object roll behavior needs explicit defense policy first. |
| Damage features | `DamageRollResultEvent`, GWF, coatings, size dice | Weapon-side modifiers, typed weapon bonus damage and rerolls remain in the common pipeline. Keep roll packet ordering; GWF changes primary weapon dice only. |
| Creature-only riders | `BonusDamageFeature`, condition-on-hit traits, assassin dagger | Existing processors resolve `Entity` and skip absent creatures: preserve that guard before spending once-per-turn resources or applying paralysis/prone/poison. Objects are not creatures with fabricated senses/saves. |
| Divine Smite | `classes/paladin.py:45` | **Migration hazard:** current processor checks slot/outcome/source/budget but does not require a creature target. After common object damage events it would consume a spell slot on furniture. Make intended creature eligibility explicit before enabling new events. |
| HasAttacked / Rage | `conditions.py:328`, `classes/rage.py:155` | Current tracker records every ATTACK execution, while Rage's documented requirement is attacking a hostile creature. If the generic marker starts receiving object attacks, do not allow furniture to sustain Rage accidentally. Separate/qualify the Rage predicate without suppressing real object Attack economy. Current attack-on-ally behavior also lacks hostile filtering; document rather than silently expanding this lane. |
| Hidden/Invisibility | `conditions.py:2197,2371,2489` | Current object BASE_ACTION already reveals on accepted EFFECT, through a generic fallback. Shared ATTACK must keep one reveal/check, correct first/last phase and creation-lineage guard, with no duplicate checks from compatibility events. |
| Sanctuary | `abjuration.py:2888-2990` | Ward gates attacks on its creature at DECLARATION before cost; self-break checks hostile creature recipients. Preserve guards; attacking an object must not perform an object WIS save or break the ward just because a shared event exists. |
| Defender reactions | Shield, Mirror Image, protection style, retaliation, monster hit riders | Only attach creature-owned defensive context when the target really is a creature. Preserve ordered interrupts and no-refund post-commit cancellation. |
| Slow | `transmutation.py:426-543` | Keep action/bonus lockout and suppression of Extra Attack; Haste/Surge must not recreate suppressed extra attacks, regardless of target kind. |
| Destruction aftermath | `BaseItem.receive_damage/destroy` | Keep same UUID wreck, physical revisions, attachment destruction, item concentration termination, liquids and light cleanup exactly once. Do not emulate creature death or produce creature blood for an object. |

**Why these guards matter:** “all targets use one Attack” means shared attack
lifecycle, not “all attack-triggered creature abilities work on furniture.”
Source-only/equipment rules and target-eligibility rules have different scopes.

## Object defense is a small explicit rule decision

Two lean choices are possible without a second action:

- Retain automatic hit as an explicitly authored object-defense resolution in
  the common Attack pipeline. This preserves old damage reliability, but needs
  an outcome that does not pretend an attack roll/critical happened and explains
  which roll-dependent effects are inapplicable.
- Author a numeric object defense/AC and use the existing attack roll. This is
  more uniform but changes current gameplay and requires defensible per-material
  data plus hit/miss/critical expectations. Do not repurpose wearable armor AC.

Recommendation for the intended cleaner combat model: prefer one normal attack
roll against a small authored object AC **if the user approves that rule change**;
otherwise keep an explicit automatic resolution while migrating the path. Never
silently invent a universal AC from HP or copy the old auto-hit exception into a
new `AttackObject` class. Item damage resistances/immunities remain separate from
hit chance either way.

## Fireball boundary relevant to attack correctness

Fireball is a **spell**, not a weapon Attack event. Sharing damageable targets
must not make it grant Extra Attack, trigger weapon-only riders, or spend an
attack resource. Its current per-target code resolves `Entity` and a DEX save
(`evocation.py:923`); destruction-enabled object recipients need an explicit
object-affecting effect policy, not fake creature saves. The area/propagation
study owns whether destruction in this same blast expands the reachable area.
Whichever policy is chosen, resolve a multi-cell object once, preserve one
root spell lineage, and avoid double damage as doors/attachments disappear.

## Focused public acceptance set

Use commands/discovered rows, resulting budgets/HP/item state and serialized
received event replay. Do not validate by asserting calls into new helpers.

1. One main-hand Attack row targets a creature and a visible object; bow,
   reach weapon, off-hand and empty-main fallback all select correct source
   metadata and shown loadout. No live Attack Object row exists.
2. Fire weapon versus fire-resistant prop resolves base and fire packets
   separately. GWF/size bonus still apply where eligible; creature-only
   Sneak Attack/Smite do not spend resources on props.
3. Normal Attack + Extra Attack can alternate creature/object targets. Haste
   before/after does not alter the ordinary batch; Surge adds the second batch;
   Slow suppresses it. Retain existing N=2/3/4 attack-count coverage.
4. Off-hand, Multiattack children and opportunity attacks keep explicit cost
   ownership. A reaction remains a movement child; a static object never provokes.
5. Known and hidden barriers reject before cost as today; a barrier introduced
   after commitment interrupts without refund. The selected wall remains
   attackable even when it blocks paths through itself. Reach/long-range work
   from any genuinely reachable visible support of a rotated two-cell object.
6. Hit/miss/critical (if chosen), canceled rolls and successful damage carry one
   consistent attack identity; accepted empty-hand attacks cannot display a bow.
   Damage/destruction agree for both observers and do not require live engine
   lookups during replay.
7. One destruction releases the same native blocker, kills a maintained device
   effect, cascades attached pieces once, and retains correct aftermath. Attack
   on already-destroyed target rejects without cost.
8. Hidden/Invisibility still break at their accepted action phase, and furniture
   does not sustain hostile-creature Rage or acquire creature rider conditions.

## Validation performed

Ran existing preservation tests without production changes:

`tests/manual/test_125_haste_restricted_action.py`
`tests/engine/test_window_attack_access.py`
`tests/engine/test_monster_sneak_attack.py`

**47 passed in 7.09 seconds.** Runtime: existing WSL virtual environment
`/home/tommaso/.cache/dnd-engine/venv/bin/python`; repository read through `/mnt/c`.
The separate native probe described above confirmed the current object-economy
and stance defects. Passing these existing creature tests establishes a baseline;
it does not certify the proposed extension before implementation.

## Complete attack inventory and discovery contract (follow-up)

This inventory distinguishes selecting an action that performs attacks from
qualifying for the ordinary Attack action's Extra Attack grant. They are not
interchangeable. Every new object target must reuse the selected existing action
instance, effective costs, source slot and parent lineage.

| Existing path | Cost and eligibility | Current target admission | Migration requirement |
|---|---|---|---|
| `Attack` (`actions.py:1849`) main melee/ranged | Ordinary action; selected slot; authored reach/range; API empty slot resolves unarmed | Creature; currently entity-only resolver/discovery | Normal object target using the same declaration, roll and damage phases. Discover empty-main unarmed fallback explicitly. |
| Off-hand `Attack` | Default bonus action; explicitly supplied costs override this default | Creature; off-hand equipment constraints | Preserve the actual selected slot and bonus-action cost for object targets; never replace with main-hand melee. |
| Generated Haste Attack variant | Exact restricted-resource binding from discovery; SRD only permitted capabilities, BG3 broader standard-action variants | Same as underlying action | Reuse the variant. Do not reconstruct by class/name or broaden capability using an inventory flag. |
| `ExtraAttack` (`classes/fighter.py:1268`) | `extra_attacks:1`, ordinary actions zero; grant marker; per-slot discovery variants | Creature, visible and in shared weapon range | Object recipients join this same action. Ordinary target alternation must preserve remaining batch. Empty-main fallback needs deliberate discovery repair. |
| `FrenziedStrike` (`classes/rage.py:921`) | Bonus action; `Frenzied` condition; selected/default melee-main weapon; discovery currently requires a weapon | Creature, visibility and shared weapon range | Included even though it is a `BaseAction`, not `Attack` subclass. Same object admission and weapon event path; no Extra Attack grant. |
| `NaturalAttack` (`monsters/traits.py:588`) | `Attack` subclass; authored dice/type/count/range/ability; ordinary action unless caller overrides | Creature; natural reach or projectile physical access | Preserve innate attack definition, do not show a held weapon. Allow object target through the common attack path where physically legal. |
| `MultiattackAction` (`monsters/traits.py:517`) | One action; authored sequence of weapon slots/counts; child `Attack(costs=[])` | Single creature; preflight any legal child; stops when target has no HP | Same composite supports one object target, checks object integrity between children, and damages each child once. The composite is not an ordinary Attack-action Extra Attack grant. |
| Rampage Bite (`monsters/traits.py:1456`) | Data-created `NaturalAttack`; bonus action; granted one round following eligible creature melee kill | Creature target in ordinary NaturalAttack path | A discovered granted bite can target an object; destroying furniture must not grant Rampage. |
| Opportunity Attack (`reactions.py:17`) | Reaction; selected melee main; normal `Attack` child of provocation movement | Provoking creature leaving threat, excluding Disengage | Preserve existing reaction path and weapon access through windows. Objects never become threat sources or provoke. It is not a freely selectable registered row. |
| Retaliation (`classes/barbarian.py:1063`) | Reaction available; positive applied damage from creature within 5 ft; main melee weapon present | Damage source resolves as creature | Preserve creature trigger admission. Currently invokes `Attack(costs=[])`, then consumes reaction after uncanceled result; see existing seam below. |
| True Strike child | Child `Attack(costs=[])`; outer spell owns cost; selected main weapon; spellcasting ability override; cantrip radiant rider | Creature | Shared normal weapon target support without granting an extra action batch or paying twice. Replace temporary weapon mutation with attack-local rider data. |

`Frenzy` (`rage.py:1042`) is a **setup** action: bonus action plus Rage resource,
not already Raging/Frenzied, no heavy armor; it installs Raging/Frenzied and the
latter registers Frenzied Strike. `RecklessAttack` (`barbarian.py:233`) is a
zero-cost self setup that installs its condition. Neither performs an attack.
Their later strength/reach checks and condition cleanup must remain intact.
Action Surge, Rage, End Rage, Leadership and Divine Eminence likewise are not
attack selections merely because they alter later attacks.

Retaliation's post-resolution reaction debit is an observed preexisting
implementation difference from Opportunity Attack. A canceled or nested attack
could expose different commitment behavior. This study does not establish an
actual failing nested-reaction case. The plan should explicitly preserve the
present behavior during target migration or deliberately align commitment with
a separate behavioral test; it must not falsely claim all reactions already use
one atomic cost path.

### Spell attack selections

All nine classes that actually call `SpellAction.resolve_spell_attack`
(`actions.py:4631`) must be present in a general attack-selection inventory.
Their events and economy stay spell-owned; this is not permission to convert
all spells to weapon attacks or make their recipients universally objects.
Creature-only riders require an explicit creature check if the spell itself is
authored to accept an object.

| Spell action | Gate/cost and resolution retained |
|---|---|
| Fire Bolt (`spells/evocation.py:111`) | Cantrip/action; 120 ft ranged spell attack; projectile access. Description mentions objects but current resolution requires Entity. |
| Ray of Frost (`evocation.py:279`) | Cantrip/action; 60 ft ranged spell attack; cold damage plus creature speed rider. |
| Scorching Ray (`evocation.py:667`) | Level 2 slot/action; 120 ft; three rays plus upcast; separately rolled rays and repeated allocation preserved. |
| Shocking Grasp (`evocation.py:2199`) | Cantrip/action; 5 ft hand access; metal-armor advantage and creature reaction-denial rider. |
| Guiding Bolt (`evocation.py:2465`) | Level 1 slot/action; 120 ft ranged attack; subsequent attack advantage rider. |
| Eldritch Blast (`evocation.py:2603`) | Cantrip/action; 120 ft; level-scaled 1–4 beams, separate rolls and repeated allocation. |
| Chill Touch (`spells/necromancy.py:246`) | Cantrip/action; 120 ft; no-healing and undead creature rider. |
| Inflict Wounds (`necromancy.py:1748`) | Level 1 slot/action; 5 ft hand access; melee spell attack. |
| Ice Knife (`spells/ice_knife.py:46`) | Level 1 slot/action; 60 ft attack; separate cold DEX-save burst occurs on hit **or miss**. |
| True Strike (`evocation.py:3801`) | Cantrip/action; main-melee and main-ranged variants registered at `3898`; requires the weapon, uses spell ability, then normal cost-free weapon attack child. |

Save-only/automatic spells such as Fireball and Magic Missile are not attack-roll
selections. Neither are Eyebite Strike (WIS save) or Sunbeam Strike (CON save),
despite their names. There are no implemented Monk/Flurry of Blows/Martial Arts/
Stunning Strike action paths in the inspected `dnd` tree; unarmed equipment and
Monk AC enum entries are not proof those actions exist. Do not invent registry
entries for them in this lane.

### Lean helper and exact source of truth

Keep existing `BaseAction.is_attack` and `AvailableActionInfo.is_attack`
(`core/base_actions.py:945,2401`) meaning category `ATTACK`. A small
`BaseAction.performs_attack` property may default to `is_attack`, with explicit
true declarations on the nine spell-attack classes above and True Strike. This
property answers only the inventory/query question. It must **never** authorize
Extra Attack, restricted Haste, cost exemption or target eligibility. Multiattack
correctly answers true while retaining its composite economy. There is no need
for an AttackKind enum, static class list, second registry or outcome-profile
framework for this question.

A helper should read the already expanded instances from the **same**
`Entity.get_available_actions()` query (`entity.py:6846`):
`AvailableActionsResult.registered_action_variants`,
`inventory_use_action_sources`, and the resulting public rows
(`core/base_actions.py:2488–2535`). This preserves current registered templates,
Frenzy/Rampage granted lifetime, Haste binding, selected slot, item charges and
True Strike choices without repeating discovery or rebuilding actions from names.
Distinguish registered choices from current executable rows (costs/targets may
make a registered choice unavailable), and keep triggered-only reactions in the
existing handler list rather than fabricate free selectable actions. When a
public row exposes the classification, serialize the same declared value.

Filtering by `isinstance(Attack)` loses Extra Attack, Frenzied Strike and
Multiattack. Filtering by existing outcome profiles loses Shocking Grasp, Ice
Knife and True Strike because those classes do not supply the necessary attack
profile. Probability metadata must not decide whether an action actually attacks.

Additional acceptance checks: discovery includes and correctly costs Frenzied
Strike while Frenzied, removes it at condition expiry, and supports an object
recipient; includes exact spell/True Strike/Haste variants once; excludes setup
and save-only actions; verifies Rampage and Retaliation remain creature-triggered.
The helper tests must compare public choice meaning/eligibility and execution,
not mirror an implementation list of classes.

### Additional preservation baseline

`tests/progression/test_direct_barbarian_progression.py` and
`tests/manual/test_53_srd_monster_traits.py`: **40 passed in 5.71 seconds**.
Together with the earlier three files, **87 existing tests passed**. This confirms
the inspected existing combat paths have a passing baseline; object expansion
still needs the behavioral checks described above.

## Independent consolidated-plan correctness review

Reviewed `agent_docs/ATTACKS_AND_DESTRUCTIBLE_OBJECTS_PLAN_2026-10-01.md`
independently after completing the expanded inventory. **Approved as an
implementation plan, conditional on the two explicitly pending gameplay choices
(object AC and Fireball structural damage). No additional correctness blocker was
found in the proposed architecture.** This is not patch approval or proof of
implementation.

The plan correctly removes AttackObject rather than disguising it, keeps all
weapon/composite/feature producers in the same lifecycle, retains actual paid
costs for Extra Attack, and prevents a broad attack-inventory predicate from
widening Haste or target permissions. Thin Extra Attack/Frenzied Strike variants
are sound provided the planned explicit defaults/capabilities are implemented.
Natural input and True Strike riders remain passive local values; keeping the
modifier-aware computations avoids the original bypass. The planned Retaliation
change is a deliberate fix: reaction debit at common commitment closes the
post-resolution owner difference; cover both rejection and late interruption.

The spell/area design correctly separates recipient eligibility, spatial reach
and protection: Globe rejects an eligible effect without becoming a propagation
wall; source/slot costs remain spell-owned; item cascades run their existing
lifecycle; finite UUID-visited stages cannot grind a surviving door down through
retries. Presentation must consume the staged native facts and their filtered
causal dependencies rather than infer final spatial state or rerun propagation.

Three implementation notes clarify the boundaries without expanding the plan:

1. The producer table should explicitly include the data-granted **Rampage Bite**
   under NaturalAttack, or reference the expanded inventory. It is covered by the
   proposed predicate automatically, but object destruction must not grant it.
2. Spell classification must explicitly cover all **nine resolver callers plus
   True Strike** listed above. It should neither fabricate an attack profile for
   selection nor imply every such spell can damage objects. The separate spell
   applicability table remains necessary.
3. Root cancellation means no dependent effects when canceled before effects
   begin, and no further committed stages when interrupted later. Never roll back
   already applied damage/destruction by deleting previous facts, and never let
   an already canceled spell reach the first stage. Exercise normal existing
   cancellation phases; this does not require a transactional world rollback.

Tests and replay acceptance in the plan are appropriately public and focused.
The 87-test passing baseline is stronger than the earlier 47-test figure in the
plan, but remains a baseline, not certification of the new object semantics.

## Required Haste × Slow × Extra Attack × Action Surge matrix

This section answers the explicit follow-up request for a full grid. `N` is the
number of attacks per ordinary Attack action: 1 (no Extra Attack feature), 2, 3,
or 4. `Surge=on` means one available Action Surge is actually used this turn.
`Haste=on` means its one restricted action is spent on a normal weapon attack.
These totals exclude bonus attacks, reactions, composite Multiattack and spells.
They count attack attempts, including misses, against surviving eligible targets.

Current source semantics: ordinary paid ATTACK execution grants `N−1` additional
attacks (`fighter.py:1178`); Haste replaces ordinary action cost with its own
resource and therefore grants none (`base_actions.py:1544`,
`transmutation.py:824`); Action Surge adds one ordinary action (`fighter.py:925`).
Slow zeros the extra-attack resource and disables reactions, but **does not cap
all attacks from separate action budgets to one per turn**
(`transmutation.py:285,426,522`). The existing preservation test explicitly
expects ordinary + Haste + Surge attacks to remain separately usable while Slow
suppresses Extra Attack (`test_125_haste_restricted_action.py:709`). Do not
silently substitute another rules interpretation during this refactor.

| Slow | N | Haste off, Surge off | Haste off, Surge on | SRD Haste, Surge off | SRD Haste, Surge on | BG3 Honour Haste, Surge off | BG3 Honour Haste, Surge on |
|---|---:|---:|---:|---:|---:|---:|---:|
| Off | 1 | 1 | 2 | 2 | 3 | 2 | 3 |
| Off | 2 | 2 | 4 | 3 | 5 | 3 | 5 |
| Off | 3 | 3 | 6 | 4 | 7 | 4 | 7 |
| Off | 4 | 4 | 8 | 5 | 9 | 5 | 9 |
| On | 1 | 1 | 2 | 2 | 3 | 2 | 3 |
| On | 2 | 1 | 2 | 2 | 3 | 2 | 3 |
| On | 3 | 1 | 2 | 2 | 3 | 2 | 3 |
| On | 4 | 1 | 2 | 2 | 3 | 2 | 3 |

Equivalently, without Slow `T=N×(1+S)+H`; with Slow `T=1+S+H`, where `S,H`
are zero/one. SRD and BG3 Honour match in this weapon-only grid. Their discovery
permissions still differ: SRD permits weapon Attack/Dash/Disengage/Hide, while
BG3 Honour can replace a broader ordinary action cost, including a spell's action
cost. Neither policy pays spell slots, bonus actions, reactions or extra-attacks
resources, and neither produces a second Haste resource from a feature row.

### Current verification versus required post-refactor tests

Ran a bounded, read-only native probe for **all 48 combinations** in the table,
using existing test fixtures and public discovery/index execution. All 48 matched.
N=1 had no Extra Attack feature. The probe consumed Haste first, performed an
ordinary attack, consumed one Extra Attack for N≥3, used Surge if present before
exhausting the first batch, then drained the remaining extra attacks. This also
verified accumulated partial batches: N=4 with one extra attack used has E=2,
then E=5 after the second ordinary paid Attack; it is not clamped to the normal
single-batch maximum. Each probe ended with ordinary actions and any Haste/Extra
Attack resources exhausted. These were current **creature** probes, not newly
committed tests and not certification of future object behavior or every order.

Existing committed tests cover BG3 N=2/3/4 Haste-before/after ordinary attack,
structural Extra Attack N=2, BG3 N=2 Surge before/after a completed first batch,
and Slow N=2 with/without Surge. They do not by themselves cover the full grid,
SRD execution counts, N=1, partial-batch accumulation, every interruption phase,
or mixed object recipients.

Post-implementation, run the entire requested repository suite, not these probes
or a focused subset as a completion substitute. The full suite gate includes
engine, manual, progression, game, architecture and other collected tests under
`tests/`, following `HOW_TO_TEST.MD`; report exact commands and remaining failures.

### Resource ledger and ordering checks

Represent observable state as `(A,H,E,B,R,U)`: ordinary actions, restricted Haste
resource, extra attacks, bonus actions, reactions, remaining Surge uses. A missing
Haste/Extra resource is absent, not an invented zero-capacity resource. Start of
a fresh eligible turn is A=1, E=0, H=1 when Haste exists, B=1, R=1 unless Slow
sets R=0; U contains the authored available uses.

| Accepted operation | Required state transition, before any independent effect |
|---|---|
| Ordinary main-hand/unarmed/natural Attack | A decreases 1; E gains N−1 when not Slow; no H/B/R/U debit. First grant begins a batch, subsequent grants add without overwriting leftovers. |
| Extra Attack | E decreases 1; no ordinary action/H/B/R/U debit and no fresh grant. |
| Haste-funded weapon Attack | H decreases 1; ordinary A and an existing E batch remain unchanged (Slow keeps E=0). |
| Action Surge | U decreases 1, A increases 1; E/H/B/R unchanged. The Surge action itself grants no attacks. A second same-turn Surge remains prohibited by its existing marker. |
| Ordinary off-hand / Frenzied Strike | B decreases 1; no E grant; genuine existing weapon/condition prerequisites remain. |
| Opportunity / Retaliation | R decreases 1 at the respective common commitment; no E grant. Slow prohibits them. Retaliation's deliberate debit migration is covered separately. |
| True Strike child / Multiattack child | No child budget debit or E grant; actual parent owns its cost. |

For non-Slow ordinary Attack sequences after `a` paid attacks and `e` extra
attacks, E=`a×(N−1)−e`; Haste interleaving must not change that equation. Following
one paid attack and `k` of its extras (0≤k≤N−1), E=`N−1−k`. Surge itself leaves E
alone. The next paid attack produces E=`2(N−1)−k`. This must work for a completely
unspent, partly spent and exhausted first batch. For N=1 the extra rows/resources
are absent; the ordinary budgets still yield the first table.

Required execution orders, using freshly discovered real variants at each step:

- Haste before the first ordinary Attack; immediately after that attack; between
  two extra attacks where N allows it; after the first exhausted batch; and after
  both exhausted Surge batches.
- Surge before any attack, while E=N−1, with some E consumed (N≥3), and after E=0.
  When Surge and Haste coexist, spend Haste on either side of the second ordinary
  attack while checking the E ledger at every step.
- Repeat a representative late-Surge case with Haste spent on Dash, so an unused
  haste attack is not silently counted and no `HasAttacked` shortcut controls E.
- Preserve existing N=2 structural grant coverage; extend at least the N=4 partial
  batch case to source-owned multiplicity, rather than relying solely on legacy
  `ExtraAttackFeature` construction.
- For object migration, run the full 48-cell core grid with attack targets
  alternating creature/object where more than one attack exists. Include N=1's
  sole object attack separately. Keep target HP high enough to distinguish budget
  exhaustion from target destruction; destruction stopping a composite has its
  own test.

### Failures, misses and cancellations

Check remaining budgets and usable discovered rows, not just hit count:

- Unaffordable choice, nonexistent/destroyed/out-of-range/blocked target, or
  declaration cancellation before commitment: no budget/resource debit and no
  new E grant. Existing E must remain intact; target HP is unchanged.
- Miss, critical and successful hit: identical selected action cost and E grant.
  Damage outcome cannot decide action economy.
- A barrier appearing after commitment (initial execution, before roll, after
  roll) consumes the selected A/H/E/R budget once and causes no hit. With an
  already accepted ordinary Attack batch, E is retained; Haste and Extra Attack
  interruptions cannot create a fresh batch. Existing window tests prove the A
  debit but do not presently assert the whole E/H ledger.
- A stale Haste row after its resource is exhausted or condition removed cannot
  fall back to ordinary action spending. A stale Extra Attack row after E=0
  cannot become an ordinary attack or buy itself with Haste.
- Slow must continue clearing E for all selected recipient kinds, and action/bonus
  lockout plus no-reactions must survive ordinary attack target migration. Bonus,
  Haste and cancellation edge cases below must be characterized explicitly rather
  than claiming broad Slow correctness from the weapon-only grid.

### Confirmed timing gaps discovered while validating the grid

The ordinary 48-cell grid passes, but three small probes exposed real current
edge defects. They require stated fixes, not misleading claims of preservation:

1. **Post-commit cancellation can change Extra Attack entitlement by handler
   registration order.** With N=4, a cancellation handler subscribed to ATTACK
   EXECUTION before the feature handler left A=0/E=0; registering the same handler
   after it left A=0/E=3. Both canceled before damage. Declaration cancellation
   in either order left A=1/E=0. Required corrected contract: accepted ordinary
   Attack commitment grants its batch exactly once, even if that committed
   attempt is then interrupted; pre-commit cancellation grants nothing.
2. **Slow's lockout currently ignores the meaning of a substituted Haste cost.**
   After Haste Attack while Slowed, the probe still had A=1/B=1/H=0/E=0 and a legal
   off-hand attack. Executing off-hand then left A=0/B=0/H=0/E=0. The source handler
   examines only positive effective `cost_type` values, so Haste's actions=0
   resource replacement bypasses the action/bonus exclusion. Required correction:
   retain the action channel being exercised independently from which resource
   pays for it; Haste is still an action for Slow exclusion, though it is not an
   ordinary paid Attack for granting E. Bonus-first must likewise prohibit the
   action-channel Haste variant. Do not infer this from a display-name suffix.
3. **Applying Slow during an earned batch does not suppress it immediately.**
   N=4 ordinary Attack plus one Extra Attack left E=2. Applying Slow preserved E=2
   and the Extra Attack row; one extra attack still executed and only then cleared
   E=0. Removing Slow before that extra attack retained E=2. Recommended explicit
   correction: Slow entry discards unspent E immediately; while active, no new E
   can be granted; removal clears Slow's own lockouts but does not recreate old
   credits. A later newly paid ordinary Attack after removal earns its normal
   fresh batch. This matches the existing destructive clear when a Slowed attack
   actually executes, while removing the accidental timing window.

The smallest deterministic grant seam is existing `Attack._apply_costs`
(`actions.py:2343`), after its successful atomic cost commit and before
`BaseAction` publishes externally cancelable EXECUTION (`base_actions.py:1975–2006`).
Feature bookkeeping must run there once, not via EventQueue handler-priority
special cases or a new event framework. Reposting Attack phases cannot invoke it
again. Moving the present fighter-owned handler directly into an import from
`actions` would create a cycle; reuse the already existing ActionEconomy
attack-multiplicity grant data, adapt legacy ExtraAttackFeature to that same data,
and place shared marker/bookkeeping below actions in the import DAG. Preserve its
causal lineage. Slow's authored suppression must be visible at this commitment
boundary regardless of condition/feature installation order.

Validated section 5's updated main-plan tables and resource transitions against
these sources/probes. N=1 truly had no ExtraAttackFeature **and no extra-attacks
resource**. The off-hand default rule currently preserves an explicitly supplied
resource/reaction/empty cost; the refactor must also preserve feature-authored
subclass defaults when `costs` was not supplied by the caller. In particular,
ExtraAttack with an off-hand slot still consumes E, not B, and a cost-free
Multiattack off-hand child remains free. The inherited `WEAPON_ATTACK` capability
alone is not enough to create a Haste variant: cost replacement must still find
an eligible positive ordinary-action cost. Extra/Frenzy/resource-only rows must
not gain a paid Haste substitute after changing their base class.

**Updated review verdict:** the complete grid is correct for the intended current
game rules. Approve the plan with the three explicit corrections above included;
implementation must prove them and run the full requested `tests/` suite. Current
48-cell probes and earlier 87 passing tests are baseline evidence only.

## Implementation validation — economy slice

Implemented the approved changes without a second object-attack executor:

- `ActionEconomy.grant_attack_batch` consumes existing ranked multiplicity grants,
  credits one committed lineage once, preserves pending Surge batches, and applies
  owned suppression. Extra Attack source-owned progression and legacy feature
  adapters now feed the same data. The obsolete execution-order handler is gone.
- BaseAction's commitment hook (root implementation) records original action vs
  bonus-action meaning independently of restricted funding. Slow owns its
  exclusion and multiplicity limit, discards pending credits on entry, and does
  not restore them on removal.
- ExtraAttack and FrenziedStrike inherit normal Attack resolution and preserve
  their resource/bonus costs even for explicit off-hand slots.
- Retaliation commits its reaction before cancelable execution. Divine Smite
  rejects object recipients before slot consumption. HasAttacked remains a
  generic attack marker and separately records hostile-creature targeting for
  Rage maintenance. The ExtraAttacksGranted marker is a typed one-round condition
  parented to the published attack declaration.

The economy/progression selection now passes **269 tests**: the full 48-cell
matrix repeated over creature, object, and mixed targets (144 cases), 18
Haste/Surge ordering cases, declaration/execution cancellation in both handler
installation orders, Slow installation/midbatch/removal, genuine feature-absent
N=1, direct fighter/barbarian progression, and 10 focused off-hand/Frenzy/
Retaliation/Rage/Smite recipient tests. Command uses the project's Python 3.13
venv, dummy SDL drivers, and `pytest --assert=plain -q --tb=short`.

The object-consumer migration selection initially had 521 passing tests and 10
remaining failures. Six were a fixture interval that included the newly correct
HasAttacked marker in an assertion intended only for destruction descendants;
the interval now starts after the verified nonlethal hit. Two elevated cannon
fixtures placed the attacker 10 ft below the target and now use genuine matching
raised supports. One unarmed test now supplies the normal damage die after its
attack die. Those three files subsequently pass all **69 tests**. The final
remaining disabled Fire Bolt scroll discovery row is assigned to the ECS agent's
combined creature/object contextual-target implementation.

Attack fixtures select explicit melee slots and UUIDs and supply a separate
noncritical d20 face of 19 before their previous damage dice. Face 18 legitimately
missed AC 19 metal doors; this is why the deterministic fixture face changed.
The destruction helper asserts actual damage progress, preventing an accidental
miss from leaving its existing destruction loop unbounded. Native events,
physical reach, AC, per-packet damage and normal equipment changes remain active.

The four older Action Surge fixtures and seven combat tutorial cases previously
used undeployed bestiary factories or a removed global position registry. Their
setup now composes/deploys through Game and uses the shared runtime reset. No
production visibility rule or combat expectation was weakened.

This is bounded implementation evidence, not a claim that the complete project
suite passes. Root is running the required whole `tests/` suite and separately
recording unrelated collection failures from older removed content APIs.

Final bounded follow-up: all five direct-device range/sector cases plus the
unaffordable combined-target scroll case selection pass (6 parameterized checks
in total). ECS review requested explicit empty restricted-action eligibility on
ExtraAttack and FrenziedStrike; these now override inherited WEAPON_ATTACK, and
all 8 focused discovery/off-hand/cancellation checks still pass. Scoped production
and economy/scenario typing passes with no errors. The common Attack commitment,
recipient selection, object-contact revalidation and inherited-cost flow match
this audit's accepted contracts; no correctness blocker remains in this owned
slice. Final full-suite status belongs to the root run.

The subsequent whole-suite triage, including preserved Sanctuary/Twinned Fire
Bolt behavior and explicit remote lever admission, is recorded in
[ATTACK_FULL_SUITE_TRIAGE_2026-10-01.md](ATTACK_FULL_SUITE_TRIAGE_2026-10-01.md).
