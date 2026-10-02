# One attack route for creatures and destructible objects

Date: 2026-10-01. Status: approved implementation and focused verification
complete; see the
[implementation record](ATTACKS_AND_DESTRUCTIBLE_OBJECTS_IMPLEMENTATION_2026-10-01.md)
for current verification, review clips and the full-suite gate. Independent
review status is recorded below. The complete engine subset passed; the full
project run failed and its wider app defects remain open for discussion in the
[integrity review](APP_INTEGRITY_REVIEW_2026-10-01.md). The user clarified that
completion of this approved plan continues while additional repairs await review.

## Agreed objective

Remove `AttackObject`. A selected attack can target an eligible creature or
placed object through the same declaration, validation, costs, roll, damage and
attacker presentation. This includes ordinary weapons, unarmed/natural attacks,
Extra Attack and Frenzied Strike. Reactions retain their own trigger eligibility.
Spell attacks retain spell rules, and spells affect objects only when their
authored effects permit it. Grouping scenery targets in a menu is independent
of the gameplay action used to attack them.

The user requested a small, thoroughly reviewed refactor covering the backend
and event-driven frontend, including AoE destruction and the possibility of a
Fireball breaking a door and propagating through the resulting opening. Preserve
Extra Attack, both Haste policies, Action Surge, bonus attacks and reactions.
Do not reopen cloud compositing, window traversal, asset packing, multi-Z or the
separate NPC roster. Do not change the user's Git state.

Read with the [correctness study](audits/ATTACK_OBJECT_CORRECTNESS_STUDY_2026-10-01.md),
[anti-slop study](audits/ATTACK_OBJECT_ANTISLOP_STUDY_2026-10-01.md) and
[ECS study](audits/ATTACK_OBJECT_ECS_STUDY_2026-10-01.md).

## What is actually broken

| Current split | Observable consequence |
| --- | --- |
| `AttackObject` emits a generic action and hardcodes `MELEE_MAIN` | Longsword damage can be presented as a bow swing; object attacks never select the visible loadout. |
| It bypasses normal Attack events and object discovery skips cost variants | No ordinary Extra Attack batch, no discoverable Haste object variant, no `HasAttacked`. |
| Manual object contact hardcodes five feet | Ranged and reach object attacks cannot use their actual weapon range. |
| Damage rolls are summed under the main damage type | A sword's fire component bypasses an object's fire immunity as slashing. A native probe reproduced 12 damage where the typed result should be 6. |
| Extra Attack and Frenzied Strike duplicate creature validation | Updating only ordinary Attack would leave those attacks unable to select objects. |
| NaturalAttack and TrueStrike temporarily rewrite equipment | Attack-local data can affect nested mechanics/observation; visible source identity is harder to keep consistent. |
| Fireball resolves only Entity recipients once, before effects | Props receive no HP damage, and destroying a blocker cannot admit further recipients during the same cast. Ashen residue is not damage. |
| Frontend Attack projection/binding requires an actor recipient | Passing an object UUID into the existing event alone does not produce a correct recorded attack. |

The current object action deliberately auto-hits. There is **no existing object
AC field** to reuse; wearable armor AC is a different property. The existing
87 preservation tests passed in the audit, but do not cover the object failures.

## Explicit rule recommendations to settle before implementation

1. **Object defense:** use the normal attack roll against an authored numeric
   object AC, with existing damage affinities after the hit. This replaces the
   old automatic hit deliberately. Material defaults belong in native content
   authoring, with explicit overrides for assemblies/devices; never derive them
   from renderer materials or HP. Ordinary hit/miss/critical rules then remain
   shared. AC is structural difficulty, not an object dodging. The
   [2014 object rules](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/running-the-game)
   support object AC/HP/affinities. Do not add damage thresholds or redesign all
   object durability in this lane.
2. **Fireball:** explicitly allow direct fire damage to placed, unattended,
   damageable objects contacted by the blast, without a creature saving throw.
   A destroyed blocker admits continued propagation inside the original cast
   shape. A surviving blocker still stops it. This is an authored game rule:
   the [2014 Fireball text](https://www.dndbeyond.com/spells/2102-fireball) specifies
   creature damage and ignition of unattended flammable objects, not universal
   structural damage or a detailed within-cast breach algorithm.

These recommendations were accepted with the full implementation plan on October 1. The shared route does not require retaining
both auto-hit and AC as permanent selectable object modes. Pick the rule before
implementing it. If AC is rejected, specify automatic outcome semantics inside
the same attack route; do not preserve `AttackObject`.

## 1. Inventory and one query for attack choices

Keep the existing entity-owned action registration and its once-expanded
`get_discovery_variants` snapshot. Do not introduce an attack registry or maintain
a hardcoded list of classes in UI, AI or tests that selects runtime actions.

Provide a pure `AvailableActionsResult.attack_actions` query over the existing
available rows. It returns the same identities, configured references, weapon
slots, costs, targets and availability reasons; it does not reconstruct actions,
expand Haste again or allocate new UUIDs. Inventory/device-supplied attack choices
are included through the existing discovery results. Consumers can filter by
availability or target kind without deleting the explanation for unavailable
choices. Structural registration remains inspectable through the already retained
`registered_action_variants` and inventory-use sources.

For this query, add the minimal `performs_attack` semantic predicate to action
authoring and its projected row. Its default uses the existing ATTACK category;
the implemented spell-attack classes and True Strike explicitly declare it too.
This is needed because `is_attack` currently excludes those spells and outcome
profiles are missing for some of them. Do not compute probabilities or mutate
equipment merely to classify an action. This predicate means only that an action
performs one or more attacks: **it never authorizes Extra Attack, Haste, costs or
target eligibility**. Existing category and outcome metadata retain their jobs.

| Producer | Shared mechanics | Specific rules that remain with the producer |
| --- | --- | --- |
| Attack, each equipped slot | Existing Attack lifecycle | Default main-hand action/off-hand bonus cost; authored weapon reach/range. |
| Empty-main unarmed fallback | Same Attack lifecycle | Genuine unarmed identity/damage; visible hands rather than a leftover bow. |
| Extra Attack | Same lifecycle | Earned resource, selected slot, no new ordinary action and no Haste replacement. |
| Frenzied Strike | Same lifecycle | Active Frenzied condition, existing melee weapon prerequisite and bonus-action cost. |
| NaturalAttack | Same lifecycle | Authored natural source, range, damage, ability and physical access. |
| Rampage Bite | Granted NaturalAttack variant | Bonus-action attack with finite condition lifetime; only its existing eligible creature kill grants it. |
| Multiattack | Parent composes ordinary child attacks | Parent spends once; exact authored sequence/count; children spend no action. |
| Opportunity Attack | Trigger handler invokes Attack | Moving hostile creature, threatened boundary, reaction cost, movement parent. |
| Retaliation | Trigger handler invokes Attack | Actual received damage from a nearby creature, living defender, reaction availability. |
| True Strike | Spell parent invokes Attack | Spellcasting ability and local radiant rider; spell action owns the cost. |
| Spell attack rolls | Existing SpellAction and spell attack roll resolver | Casting/slots, concentration, repeated rays and spell-specific target rules. |

Frenzy, Reckless Attack and Action Surge are setup/grant/modifier actions, not
additional damaging attacks. Save-only spells are not attack rolls. Reaction
handlers stay in the existing reaction interface: they are not always-selectable
menu attacks. The audit inventory must list them even though the action query
does not invent rows for them. No implemented Monk/Flurry action was found;
do not add one under the guise of preserving it.

The audited spell attack selections are Fire Bolt, Ray of Frost, Scorching Ray,
Shocking Grasp, Guiding Bolt, Eldritch Blast, Chill Touch, Inflict Wounds and Ice
Knife, plus True Strike's weapon attack. Include every configured/upcast/repeated
allocation variant supplied by their real discovery. Ice Knife's save burst on
hit or miss is separate from its attack roll. Magic Missile, Fireball, Eyebite
Strike and Sunbeam Strike do not become attack-roll choices because they deal
damage or contain “Strike” in the name.

## 2. Consolidate existing attack behavior

Make ExtraAttack and FrenziedStrike thin variants of the existing `Attack`,
retaining their authored identities, providers, costs and prerequisite checks.
NaturalAttack already uses this inheritance. Shared declaration, target
admission, physical validation, range/pressure, roll, damage and stance selection
should have one implementation. This is reuse of an existing action behavior,
not an entity inheritance hierarchy or a generic strategy framework.

Before changing bases, remove implicit default-cost replacement: ordinary
off-hand defaults must not overwrite a feature's explicit extra-attack resource,
bonus cost or `costs=[]` child. Resolve defaults only when the ordinary Attack
caller asks for them. Set restricted-action eligibility deliberately on each
variant; inherited `WEAPON_ATTACK` must not make a Frenzy/Extra Attack row buyable
with Haste. Preserve current Haste policies and supplied reaction costs.

Use a small passive selected attack-source value for equipment-slot, unarmed
or natural input. Reuse existing modifier-aware `attack_bonus`, `get_damages`
and declaration metadata. NaturalAttack supplies its own source inputs without
clearing the real weapon slot. True Strike passes its ability override and
additional typed damage locally without pushing/popping shared equipment lists.
Do not replace those component computations with a raw dice shortcut.

No global `if name == Frenzied Strike`, `isinstance` chain of attack subclasses,
or additional dispatcher. Existing method overrides supply actual rule variation.
A finite target-kind branch at defense/application is appropriate and explicit.

Make ordinary Extra Attack batch grants part of the existing successful Attack
cost commitment, before externally cancelable EXECUTION dispatch. A probe found
that handler registration order currently determines whether a committed but
canceled Attack grants its batch. Use the current `Attack._apply_costs` seam and
existing ActionEconomy multiplicity data, not EventQueue priority adjustments.
Adapt the legacy ExtraAttackFeature to the existing multiplicity grant rather
than leaving a second count source; remove its source-owned contribution on
cleanup. Numeric bookkeeping stays in ActionEconomy alongside its existing
multiplicity/resource data. Move ExtraAttacksGranted to `dnd/conditions.py`,
beside HasAttacked/HasTakenDamage; actions already imports that lower owner and
fighter can import the marker from it. Never import fighter from actions.
Preserve its turn lifetime and causal parent. The EXECUTION value in `_apply_costs`
is still detached: parent the marker fact to the already published DECLARATION
of the same lineage, not to an event the queue has not registered. Reposting
event phases cannot grant again.
An ordinary action paid before interruption earns its batch; rejection before
commitment earns none. Slow suppresses that grant regardless of installation order.
Represent Slow's multiplicity cap through ActionEconomy-owned data using the
existing source-owned modifier/receipt pattern; remove only that contribution
on cleanup. Both commitment and Extra Attack admission consult the same effective
entitlement. Do not recreate suppression via listener priority or an
`Attack` import/check of `SlowedEffect` by class or condition-name string.

Retaliation currently spends its reaction after resolution, unlike opportunity
attacks. Correct this in the common-cost migration: pass its reaction cost into
Attack, debit once at commitment, reject before debit when invalid, and retain
the debit on a post-commit interruption. Keep its current damage trigger and
creature eligibility. This is a stated correctness change, not an accidental
side effect of changing class inheritance.

## 3. One target selection, correct contact geometry

Add one single-target routing option admitting creature or placed object, with
an explicit recipient-kind discriminator on the selected target/facts. Ordinary
Attack and eligible variants use it. Do not globally widen ENTITY or turn every
spell/interaction into an object-capable action. PickUp and manual uses remain
ordinary object interactions with their existing costs/range.

For each exact registered attack variant, gather its known eligible creature and
object contacts, validate with the same declaration and return one action row.
Scenery targets can be grouped separately in the picker; changing target group
must not change the action identity, weapon or cost. Creature faction filters do
not classify furniture as an enemy or silently remove it from object selection.

Generalize existing object contact geometry to accept attack range and physical
access. Retain `manual_object_contact` as its five-foot hand-use wrapper. The
attack query must cover rotated multicell supports, either side of a boundary,
height bands and attached inserts, and choose an actually reachable support.
Only the target provider is exempt from blocking contact with itself. A different
wall, a parent around an inaccessible insert or another co-located obstruction
must still block appropriately. Traversing through an object is a different query.

Discovery uses received contacts and known obstacles. Native admission and late
execution checks use actual geometry. Keep range/long-range disadvantage and
Light-weapon window restrictions. Do not grant knowledge of unseen supports,
hidden contents or back rooms just because an item's anchor UUID is known.

Record the chosen kind/identity and contact/placement with the existing cold
attack declaration. No later lookup of live equipment, target Entity or renderer
sprite bounds may decide what the attack hit. Preserve existing creature-only
facts/defaults for old normal-attack recordings; avoid a wholesale UUID-field
rename unrelated to behavior.

## 4. Shared damage arithmetic, existing consequence owners

Keep `create_weapon_attack_declaration_event`, AttackEvent, attack-roll outcome,
DamageRollResultEvent and typed DamageRollPacket processing. Source/equipment
modifiers and each eligible target modifier run once. Creature defense imports
its real contextual AC; object defense uses its authored AC. Objects do not get
fabricated creature senses, conditions, saving throws or defensive reactions.

Extend the existing item damage entry to preserve typed components and their
real roll evidence, using `Health.preview_damage_components`. Keep a scalar
wrapper for existing scalar callers if necessary, with one arithmetic owner.
Do not collapse elemental riders into the main weapon type or invent d4 roll
metadata for already rolled damage. Mitigate components once, apply the health
result once and destroy once if it reaches zero.

After shared resolution, creature and item consequences remain distinct:

- Entity owns temporary HP, concentration, life/death, creature hit reactions
  and blood/material effects.
- BaseItem owns its TakeDamage/ItemDestruction lifecycle, same-UUID wreck,
  attachment cascade, connectors, item-sustained effects, light and liquid spills.

Do not automatically broadcast creature DamageApplied semantics for objects.
If a recipient discriminator must be added to an existing notification, migrate
every consumer with explicit eligibility. Objects must not bleed or perform
death saves. Native destruction continues to invalidate geometry immediately;
the renderer delays presentation according to its existing authored clearance.

## 5. Preservation and deliberate fixes

| Case | Required observable behavior |
| --- | --- |
| Normal Attack then Extra Attack, 2/3/4 attacks | An ordinary paid Attack grants the existing batch; later attacks can mix creature/object recipients without resetting it. |
| Haste before/after ordinary attacks, both policies | Restricted debit once; no new ordinary batch and no removal of one already earned. |
| Action Surge | Each extra ordinary Attack action grants its correct batch. |
| Off-hand / Frenzied Strike | Correct bonus debit and weapon eligibility; feature-local costs survive common default handling. |
| Multiattack / True Strike children | Parent debit once; cost-free children never grant extra ordinary batches. |
| Slow | Existing action/bonus lock and extra-attack suppression persist regardless of target kind. |
| Opportunity / Retaliation | Existing trigger and parent lineage; one committed reaction; static objects never provoke or retaliate. |
| Invalid or interrupted action | Before-commit rejection has no debit; after-commit interruption keeps the debit. Preserve recorded cancellation phase. |
| Range and windows | Normal/long range, threatened disadvantage, reach and requester-relative Light-weapon access all use the selected attack. |
| Roll/damage features | Lucky, critical threshold, size contribution, fighting styles, GWF and eligible typed equipment damage use the common packets. |
| Creature-only riders | Sneak Attack, Smite and condition-on-hit effects check recipient eligibility before spending resources. Smite currently needs that missing guard. |
| Rage tracking | A real object Attack counts for attack economy, but furniture must not satisfy the hostile-creature requirement that sustains Rage. Qualify that predicate rather than suppressing the attack event. |
| Hidden/Invisibility/Sanctuary | Accepted attack reveal and ward rejection stay at their current phases; no double notifications or fabricated object saves. |
| Destruction | Same UUID, original placement/material, exactly-once cascade, native channels/light/concentration/spills remain correct. |

Do not use `performs_attack`, display names or target kind as the Extra Attack
grant condition. Preserve the actual paid ordinary Attack event/cost predicate.
**Human-confirmed rule:** ordinary off-hand attacks may be used first. There is
no prerequisite to make a main-hand attack earlier in the turn; preserve this
deliberate game rule for creature and object targets. Hand choice does not change
the existing action/bonus-action costs. Add an off-hand-first acceptance sequence.
Opportunity attacks continue to use `MELEE_MAIN` and one reaction, independently
of which hand attacked earlier or which loadout was last displayed. They do not
grant an ordinary Extra Attack batch.

The expanded study reproduced three cost/suppression defects. These are explicit
fixes in the proposed refactor, rather than expected outputs to preserve:

- A post-commit cancellation could leave either zero or N-1 extra attacks based
  solely on handler registration order. Move the grant to commitment as above.
- Haste pays through a named resource, so its effective ordinary-action cost is
  zero. Slow consequently failed to lock bonus actions. Retain the original
  action channel separately from its funding source; use it for both directions
  of Slow's action/bonus exclusion. Do not inspect Haste display-name suffixes.
- Slow applied after earning a batch allowed one more Extra Attack before
  clearing credits. On Slow entry, discard outstanding extra-attack credits
  immediately and prevent new grants while active. Removing Slow releases its
  lockouts but does not recreate old credits; a newly paid ordinary Attack after
  removal can earn a fresh batch. This is the proposed explicit mid-turn policy,
  matching existing credit clearing without its timing loophole.

### Required Haste × Extra Attack × Action Surge × Slow grid

`N` is the total attacks granted by one ordinary Attack action, not the number
of additional attacks. `N=1` means no Extra Attack feature. Count attack attempts,
including misses, with sufficient surviving/legal recipients and no interruptions.
These totals exclude independent bonus-action and reaction attacks. Spend all
available ordinary actions on Attack and, when Hasted, its restricted action on
one ordinary weapon attack. One available use of Action Surge is assumed.

| Attacks per ordinary action N | No Haste, no Surge | No Haste, Surge | SRD Haste, no Surge | SRD Haste, Surge | BG3 Honour Haste, no Surge | BG3 Honour Haste, Surge |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 2 | 2 | 3 | 2 | 3 |
| 2 | 2 | 4 | 3 | 5 | 3 | 5 |
| 3 | 3 | 6 | 4 | 7 | 4 | 7 |
| 4 | 4 | 8 | 5 | 9 | 5 | 9 |

Without Slow: `N × (1 + Surge) + Haste`, where the last two terms are 0 or 1.
Both current Haste policies grant one weapon attack; they differ in which
other actions can consume the restricted budget.

**Slow uses the current game's explicitly tested rule:** it suppresses Extra
Attack but retains ordinary actions supplied by Action Surge and the Haste
restricted action. This is a preservation table, not a claim that every D&D
edition uses this interpretation. Do not silently switch to a different rule.

| With Slow active throughout; N | No Haste, no Surge | No Haste, Surge | SRD Haste, no Surge | SRD Haste, Surge | BG3 Honour Haste, no Surge | BG3 Honour Haste, Surge |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 2 | 2 | 3 | 2 | 3 |
| 2 | 1 | 2 | 2 | 3 | 2 | 3 |
| 3 | 1 | 2 | 2 | 3 | 2 | 3 |
| 4 | 1 | 2 | 2 | 3 | 2 | 3 |

With Slow: `1 + Surge + Haste`. Extra-attack credits remain zero and reactions
remain unavailable. Using ordinary actions locks out bonus actions; the reverse
order must preserve the current action/bonus exclusion too. Restricted costs
must not create an accidental loophole in that exclusion; characterize the
Haste-first/bonus-first cases explicitly rather than assuming raw cost names
express action meaning correctly.

The 48 table cells are required behavioral cases, run with creature recipients,
object recipients and legal mixed target sequences after unification. Expected
costs and state are checked after each action, not only the final attack total:

| Operation | Ordinary actions | Haste resource | Extra-attack credits | Other resource |
| --- | --- | --- | --- | --- |
| Ordinary paid Attack, no Slow | -1 | unchanged | First batch becomes N-1; later batches add N-1 to unspent credits | unchanged |
| Ordinary paid Attack, Slow | -1 | unchanged | 0 | bonus actions locked |
| One Extra Attack | unchanged | unchanged | -1 | unchanged |
| Haste-funded weapon Attack, no Slow | unchanged | -1 | unchanged, including a partly spent batch | unchanged |
| Haste-funded weapon Attack, Slow | unchanged | -1 | 0 | Slow's action/bonus exclusion still applies |
| Action Surge activation | +1 | unchanged | unchanged until its ordinary Attack is used | Surge use -1 |
| Off-hand or Frenzied Strike | unchanged | unchanged | unchanged | bonus action -1; subject to Slow lockout |
| Opportunity or Retaliation | unchanged | unchanged | unchanged | reaction -1, disallowed by Slow |
| Multiattack or True Strike child | unchanged | unchanged | no ordinary batch grant | parent already paid |

For `N=1`, the extra-attacks resource may be absent; absence is not a reason to
omit the ordinary no-feature case. Do not clamp two accumulated batches to the
usual single-batch capacity.

Exercise orderings which can expose different code paths:

1. Haste before the first ordinary Attack, between Attack and its extra attacks,
   during a partly consumed batch, and after the batch is exhausted.
2. Surge before either Attack action, after a partly spent batch, and after the
   first batch is exhausted. Two ordinary Attacks may accumulate their credits
   before those credits are spent.
3. Haste spent on an allowed non-attack first, then an ordinary/surged Attack.
   SRD and BG3 Honour must preserve their different admitted action sets.
4. Creature→object→creature, reverse order, and changing eligible weapon slots
   within those sequences. Target type must not select a different budget.
5. Misses still consume the attempt; invalid pre-commit target/cost does not.
   Post-commit cancellation consumes the actual paid resource and preserves
   exactly-once grant timing rather than granting a fresh batch during reposting.
6. Slow applied before/after feature registration, already present at turn start,
   applied after earning a partial batch, and removed during/at the end of a turn.
   No handler registration order may resurrect suppressed extra attacks. Assert
   immediate credit clearing and no recreation on removal, as specified above.
7. Haste removal/replacement, ordinary turn recharge and Slow lockout cleanup.
   Expired Haste cannot leave a usable restricted variant; lethargy is preserved.

Current audit evidence: 87 existing tests pass and a separate native creature
probe matches all 48 count cells, including true N=1 with no feature/resource
and partly consumed batch accumulation. Existing named tests cover several
N=2/3/4 Haste order cases, two N=2 Surge orders and N=2 Slow with/without Surge.
The timing defects above were reproduced separately. The complete grid and
ordering cases are **required after implementation, not yet validated for the
refactor or object targets**.
Also exercise the legacy ExtraAttackFeature and source-owned progression grant
paths for representative order cases; their authoring sources must resolve the
same multiplicity rules without duplicate grants.

## 6. Spell recipients and destruction during an AoE

Share recipient admission/contact and typed item damage with eligible spells;
do not route Fireball through a weapon Attack command. Fire Bolt is the first
single-target spell object case. Creature-only spells remain creature-only.
Audit the implemented damage spells into an explicit applicability table before
changing declarations: damage type alone is not object permission. Worn/carried
gear and container contents are outside this placed-object pass.

For the proposed Fireball rule, use its existing connected propagation and
original finite geometric envelope. The native area calculation returns reached
cells plus contacted boundary/body providers. Boundary contact must inspect both
sides of WorldEdge contributions: scanning only objects in reached cells misses
a closed door stored on the unreached side.

Resolve finite stages:

1. Compute the currently reached cells and exposed/contacted eligible recipients.
2. Apply the cast to each newly reached creature/object once. Preserve existing
   spell roll policy; Fireball currently rolls per recipient. Do not add a reroll
   every time the area is recomputed or silently change all spells to shared dice.
3. Item destruction uses its real lifecycle and native physical refresh. Query
   reach again only when those effects can expose additional cells/providers.
4. Continue inside the same original envelope until no new recipients/reach
   remain. Keep visited recipient UUIDs across stages and footprint faces.

No radius restart at a broken door, no direct deletion of barriers, and no
repeated damage until a resistant door eventually breaks. Surviving, immune and
unbreakable blockers remain barriers. Two successive doors can create two stages;
one surviving provider on a shared boundary still blocks. Resolve attached parent
and child identity once: parent cascade must not produce a second hit/break on
an already destroyed insert. Use stable spatial/identity ordering rather than
set or registration iteration. Termination follows finite cells/unique providers,
not a guessed retry count.

Evaluate spell eligibility and protection on each newly exposed recipient.
Globe immunity excludes protected effects, not geometry: it must not accidentally
act as a stone wall stopping propagation beyond it. Objects need the same
spatial spell-protection decision without requiring `Entity.get`. Cancellation
before the first effect prevents all dependent stages; a later interruption stops
future stages without undoing already applied damage/destruction. Secondary barrel effects retain
their own causal children; they are not additional Fireball applications.

Established persistent cloud occupancy remains unchanged by later door closure.
Do not enable dynamic breach/retraction for every persistent spell. No cloud
renderer, XYZ ownership or black visibility mask changes belong here.

## 7. Retained events and presentation

Extend the existing AttackEvent → subjective projection → AttackFact → reducer
and attack binder together. Use one attacker animation/profile/weapon/projectile
path with either a received creature contact or a received object contact. Item
damage/destruction facts join at that same impact; creature body reactions are
only for creatures. No dummy actor for a prop and no fixed Attack1 object recipe.

Retain explicit selected source kind/mode. Missing source-item identity is not
proof of unarmed, since observation may withhold identity. Modular hands must
not inherit a ranged layer; natural fixed-artwork rigs keep their authored source
presentation. The attack slot/source must drive both reducer stance and binder
selection; presence of a projectile VFX must not independently choose equipment.
Keep the approved creature anchors and wall/window/shadow occlusion.

For breach, add one small native area-reach fact per stage with cast identity,
stage index, newly reached cells and causal predecessor destruction/reach IDs.
Applications are children of their stage; the final root footprint remains the
union for existing area consumers. These are gameplay facts, with no fps, frame
or millisecond values. Emit only one authoritative propagation result; the client
does not solve geometry again.

The presentation compiler schedules later reached regions and their dependent
damage after the relevant object's authored physical-clearance time, using the
existing destruction staging. XYZ area samples must use displayed reached cells
and displayed barriers. Do not show the final expanded fire region or its victim
damage at frame zero while the door is still visibly intact. The final debris
frame is not the clearance instant. Multiple causal barriers must be respected
without delaying unrelated first-stage hits behind every destruction animation.
Keep one coherent explosion clock and original contact; do not restart the
Fireball sheet for every reach stage or freeze the whole explosion while a door
breaks. The visual acceptance case must prove both causal clearance and continuous
authored playback. If the current explosion duration cannot accommodate the
existing clearance, resolve that bounded presentation contract explicitly before
calling the breach feature complete.

Subjective projection must filter new contact/reach facts and dependencies just
as it filters current events. Do not leak hidden doors/recipients through a stage
payload or dependency ID. Both Python and a future TypeScript client receive
passive serializable facts; neither needs native registries during replay.

## Implementation order and completion gates

1. **Characterize and settle rules.** Preserve the current saved inputs and
   user-approved visuals. Confirm object AC and Fireball structural damage rule.
   Add smallest failing public scenarios for bow→object melee and mixed typed
   damage. Record current feature costs, cancellation and discovery identities.
2. **Inventory/query and shared attack variants.** Add the pure query and explicit
   spell markers; consolidate Extra/Frenzy validation; remove temporary equipment
   mutation from natural/True Strike. Feature/cost/creature regressions must pass
   before enabling object targets. No helper-specific snapshot tests.
3. **Native object targets and damage.** Implement shared selection/contact,
   authored defenses, typed item damage and rider guards. Migrate registration,
   real action callers and fixtures; delete AttackObject. Cover ranged, reach,
   unarmed, Frenzy, multicell and boundary recipients through discovered commands.
4. **Frontend shared attack playback.** Extend projection, facts, serialization,
   stance, binder, delivery visibility, picker and AI recipient routing. Remove
   the live object-only recipe/binding. Validate replay with no native registries
   and no equipment reconstruction from final state.
5. **Spell object effects and breach.** Add the applicability table, Fire Bolt
   object recipient, Fireball finite reach stages and filtered causal facts.
   Preserve unaffected spells, both Globe cases and unchanged persistent clouds.
6. **Presentation and removal check.** Schedule reach behind authored break
   clearance. Produce a small real-event review with real H1 floor tiles, both
   observers/four cameras. Inspect weapons and impacts, not just “no gaps”.
   Re-run anti-slop, correctness and ECS reviews against the actual patch.
7. **Full-suite completion gate.** After the user has accepted this plan and the
   implementation is complete, run the entire engine test collection, including
   tests outside `tests/engine`. Run the repository's full configured `tests/`
   collection so manual combat, progression, runtime, AI, product, architecture,
   game/replay and packaging checks are not silently excluded. Retain the full
   log and totals. Investigate every failure; targeted passes or a label of
   “preexisting” are not a substitute for this run or evidence of completion.

Required acceptance scenarios, using normal discovery/execution and received
records rather than private helper calls:

- One attack choice offers creature and object targets; no live AttackObject
  behavior/template/executor remains. Query includes unavailable explanations,
  all earned feature variants and spell attack choices without setup false positives.
- Bow→longsword object hit→bow, ranged object impact and actual unarmed hands;
  hit/miss/critical and interruption show the same selected source as native rules.
- Mixed slashing/fire versus fire immunity; resource-limited creature riders
  stay unspent on objects. Once-only damage/destruction across multicell supports.
- The cost matrix above, with mixed recipients; Frenzy gain/removal; reaction
  late cancellation; natural source and True Strike do not alter equipment.
- Rotated cart far support, boundary from either side, broken/intact window
  insert, unrelated blocker and currently hidden object; no observer leakage.
- Fireball with weak/strong/immune doors, two serial doors, parallel blockers,
  parent+insert and an object beyond the original radius. First-stage recipients
  never take a second hit. Reversed registration order does not change semantics.
- Globe suppression inside versus eligible effects outside, including object
  contact; root cancellation and one slot/concentration transaction.
- Serialized replay shows door contact → destruction clearance → newly reached
  region/victim, with correct wall ordering in all four cameras. Existing cloud
  movement, open map fringe and Globe baselines remain unchanged.
- Destruction still removes device-maintained effects and light, updates native
  physics, spills liquids and retains the authored wreck exactly once.

Follow `HOW_TO_TEST.MD`. Reuse existing engine and cold-replay suites. Extend
behavior-level cases, not private method/call-order assertions or a new visual
testing platform. Run scoped typing/import boundaries and relevant feature suites
during development, then the **mandatory full suite** before handoff. The normal
command is `uv run --no-sync python -m pytest tests` in the documented installed
environment, with headless SDL settings where needed. Resolve environment or
collection failures rather than silently omitting those tests. Record skips and
their actual reasons separately. If a failure requires an unrelated product
decision, report it for direction and do not call the whole gate passed.
Inventory assertions should use
public authored fixtures/rows; don't freeze every incidental template UUID.

Delete live AttackObject imports, catalog registration, default setup, executor,
picker assumptions, recipe/binding and fixture helper. Keep original historical
records preserved; any needed old-data reader is read-only and cannot retain a
second live attack path or infer absent old weapon evidence from current gear.

## Independent review record

- Anti-slop: consolidated plan approved; actual implementation still requires
  review. Coherent explosion timing across breach stages is an explicit gate.
- Correctness: consolidated design and 48-cell interaction grid approved with
  the three reproduced commitment/Slow fixes included above. Baseline evidence
  is 87 existing tests plus 48 native creature probes, not refactor acceptance.
- Anti-OOP/ECS: consolidated plan approved; actual implementation still requires
  review. Existing Health, destruction, spatial and action owners remain in place.

No runtime implementation or new visual acceptance is claimed by this document.

## C7 clearance selection during implementation

The closed C7 clear-destruction bank (`door.desert-c7.debris`, bound by
`environment.door.desert_c7` as `closed.clear`) previously inherited the default
frame-zero state change. Inspection of all four installed poses through
`environment_command` compared original frames 0, 3, 4 and 5. Frame 3 still
shows broad upright breaking panels; at frame 4 the leaf has separated and
rotated away from its blocking plane, while later frames finish settling the
fragments. The authored clearance is therefore **frame 4, 250 ms**.

Only this bank's passive `state_change_frame` changed. It retains all twelve
frames, its original 16 FPS sampling, 750 ms duration, pivots, depth data and
pixels. Other door banks retain their existing unreviewed markers. This is a
measured visual clearance choice for the breach preview, not a duration formula
or a new backend delay. Evidence: `.runtime/attack-review/c7-clearance-four-poses.png`.
