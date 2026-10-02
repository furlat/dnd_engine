# Attacks and destructible objects: anti-slop study

2026-10-01. Read-only study of the current checkout, requested by the user.
No production edits or new gameplay ruling are authorized by this report.
Action-economy details and Fireball breach behavior have separate concurrent
reviews; the final plan must incorporate those findings before implementation.
The user has explicitly clarified that **AttackObject must disappear** and
normal Attack must target objects for every supported attack mode. Discovery
grouping may keep the menu readable; it is not permission for a second command.

## Finding

The observed bow swing is a real architectural split, not merely a missing
renderer flag. Object damage and destruction already have useful native owners.
The unnecessary duplication is the attack path that reaches those owners.

| Concern | Creature attack | Object attack |
| --- | --- | --- |
| Native command | `Attack` | `AttackObject` |
| Event | `AttackEvent` / ATTACK | ordinary `ActionEvent` |
| Weapon | selected slot | hardcoded MELEE_MAIN |
| Declaration | immutable weapon name, item presentation, damage types | no weapon declaration |
| Hit resolution | attack roll, AC, outcome | automatic hit |
| Damage construction | `Entity.get_damages`, size contribution, per-type packets | direct equipment damages, summed and relabeled as main type |
| Damage-roll hooks | `DamageRollResultEvent` | omitted |
| Active loadout | changes at accepted hit/miss effect | unchanged |
| Presentation | authored weapon/rig/damage/outcome variant | fixed Attack1/contact frame 8 |
| Recipient effects | creature damage/life events | existing item damage/destruction events |

Code anchors:

- `dnd/actions.py:1770`: `create_weapon_attack_declaration_event` already owns
  the cold weapon snapshot; this is the foundation to extend, not replace.
- `dnd/actions.py:1849`: ordinary Attack, including range/threatened/roll,
  result interception, accepted stance, and typed damage packet dispatch.
- `dnd/actions.py:5196`: AttackObject's duplicate path.
- `dnd/entity.py:2858`: entity-level weapon damage adds size contribution.
- `dnd/blocks/base_item.py:718`: item damage already uses TakeDamageEvent,
  Health preview/application, then native destruction.
- `game/data/neuroclient/object-attack-recipe.json`: independent fixed actor
  track, explaining why this bow-equipped actor can swing a bow like a sword.

The current AttackObject approach can also misapply damage resistance: a weapon
with slashing plus fire components becomes a single slashing amount. Changing
only its animation or calling activate_weapon_slot would leave that defect and
the missing attack hooks in place.

## Minimum coherent direction

Use **one weapon-attack command and one AttackEvent lifecycle**, admitting an
observed creature or damageable placed item. Target type may select the final
recipient resolution, but must not select another action budget, another weapon
selection path, or another attacker presentation executor.

1. Reuse the existing equipped/unarmed declaration snapshot and authored attack
   variants. Extend the declaration only with the target distinction/contact
   facts needed by real consumers. Do not build an AttackService, target class
   hierarchy, renderer registry, or generic capability framework.
2. Keep the existing Attack cost/validation/phase owner. Preserve its supplied
   costs override for off-hand, opportunity, Multiattack and restricted-action
   callers. A target-kind branch must not recreate those mechanisms.
3. Split only recipient-specific work: creature AC and creature damage sink;
   item admission and item damage sink. Preserve damage components and their
   original rolls through result handlers. A destructible item remains an item,
   not an actor with dummy AC, senses, life state or saving throws.
4. Keep item destruction where it is. Accepted ItemDestructionEvent cascades
   supported items, connectors, conditions, lights and spatial changes; the
   renderer consumes those retained consequences at authored contact/state
   change times. No second attack-specific destruction protocol.
5. Retire AttackObject as a live registered/mechanical path. If old command
   inputs need compatibility, normalize them once at the input boundary. Keep
   old recorded ActionFact playback readable as old data; do not translate old
   actions by consulting current equipment or re-executing them.

The hit rule remains an explicit choice. Keeping today's item automatic hit is
a compatibility baseline, not a claim that the SRD universally grants it. Moving
objects to authored AC/attack rolls changes gameplay and must be called out,
tested and approved separately. The refactor must not disguise that decision.

## Target admission is part of this refactor

Objects cannot just be fed to the existing Entity lookup. The current collectors
and targeting checks have meaningful separate responsibilities:

- `dnd/entity.py:4575` and `:4596`: entity/object action grouping.
- `dnd/entity.py:6372`: object discovery iterates received object contacts.
- `dnd/actions_functional.py:409` and `:446`: both execution routes bind the same
  target UUID, but target-type admission currently differs.
- `dnd/core/base_actions.py:1251`: OBJECT physical access is manual contact;
  entity delivery checks a path to a position.

One registered attack per selected weapon should admit both target kinds without
two independent action-cost or attack executors. Prefer a single-identity
creature-or-object target mode with a typed target-kind discriminator in native
admission/retained facts. Use the existing UUID and candidate record shape;
extend UI/AI target routing intentionally. Do not rename every ENTITY field or
widen all spells to items as collateral cleanup. Do not register hidden
AttackObject-like templates merely to preserve old UI grouping.

For object contacts, use actual placement/footprint/boundary geometry. A far end
of a two-cell object must be attackable from the near side, and the target must
not block its own approach ray. Ranged object attacks cannot reuse the current
manual-object-contact 5ft assumption. Existing boundary-relative physical access
and Light-weapon window rules should remain the query owners.

Equipment snapshot, target eligibility and costs need declaration-time
consistency, plus the existing execution recheck if a reaction changes a barrier
or recipient. Do not accidentally replace current late physical-access checks
with a stale discovery result.

## Frontend and cold replay

The UI cannot be repaired by putting the new event into the current binder alone:

- `game/player_projection.py:200` currently requires actor identification for
  an AttackEvent's source and target; object observation is held separately.
- `game/player_facts.py:86`: AttackFact carries slot/outcome/types/item ID.
- `game/attack.py:226`: bind_attack rejects targets absent from `before.actors`.
- `game/choreography.py:655`: delivery visibility similarly assumes actor
  participants. This gate must recognize a received object contact.
- `game/player_reduction.py:107`: AttackFact selects the actor's weapon stance.
- `game/choreography.py:552`: ObjectDamageFact and ObjectDestroyedFact already
  bind hit flashes, destruction and later physical visual changes.

Extend the existing attack binder to resolve a **target contact value** from the
received actor or object state. Attacker body/profile/projectile/release/contact
timing remains shared. Creature reaction/blood/life exists only for creature
targets. Object hit flash/breakage remains owned by the existing object facts and
joins at the same contact. A placed object must not gain a dummy BodyRig.

Keep geometric contact distinct from the target's animation response. For a
multi-cell or boundary object, freezing the selected legal contact in the event
or its projected passive value is preferable to targeting whichever placement
origin the current renderer happens to choose. Client projection should consume
recorded placement and authored object anchors, not backend objects or live
equipment. Use the same facts for Python and future TypeScript.

No new event stream is needed. Extend existing native records, typed projection,
player-fact serialization, reducer, and schema/coverage checks together. Test
old saved input replay and new cold replay with registries absent. Preserve
subjectivity: an observed hit on an object must not reveal a hidden attacker or
other unobserved components of an attached structure.

## Unarmed and loadout scope

`dnd/blocks/equipment.py:1055` already snapshots unarmed fallback; `:1214` builds
its native damage. WeaponSlot currently has four equipment slots and no separate
unarmed selection. Standard discovery registers attacks only for a real Weapon
(`dnd/actions_functional.py:213`), so bare fists exist mechanically but are not a
normal selectable choice. WeaponSet.NONE exists and the renderer can hide gear.

Do not let fixing AttackObject invent a manual equip/swap action economy. Keep
automatic stance selection based on the accepted attack. If this lane exposes
an explicit unarmed choice, author it through the same attack declaration and
recipe selector; retain a real unarmed identity in its facts, rather than using
`source_item_id is None` as an unconditional proof that fists are visible. Missing
item identity can also be incomplete observation. Shield/off-hand/natural fixed
rig behavior must be deliberate. At minimum, an empty melee attack must not
inherit a ranged bow layer and must select the supported unarmed body profile.

## Review gates and non-goals

The implementation is not acceptable with only zero presentation-gap counts.
Those prove a track exists, not that it depicts the selected weapon. Required
evidence includes:

- discovered longsword, bow and unarmed object attacks: actual native weapon,
  damage components, costs, visible layers and authored clip agree;
- target switch between creature and item within the same turn preserves Extra
  Attack, Haste, Action Surge and supplied reaction/bonus costs;
- creature-only riders/protections stay creature-only, while genuinely
  attack/damage-type hooks still run on eligible item attacks;
- rejection before payment, cancellation after payment, miss, nonlethal hit,
  lethal break, repeated attempt after destruction, attached child/parent
  collapse, rotated multicell target, ranged and reach contact;
- recorder uses normal available-action execution, then cold replay; inspect
  transitions ranged -> object melee -> ranged, and bare hands after ranged;
- paired observer/four-camera clips with the real H1 paving and existing
  occlusion, including one decisive arrow hitting an object and one break.

Do not rewrite generic ECS ownership, visuals, cloud clipping, item containment,
all spell target restrictions or all monster abilities as part of this lane.
An AoE may eventually share item damage application, but it is not a weapon
Attack command and must not acquire its cost/rider semantics. Breaching a door
and admitting later Fireball propagation is a separate explicit area-resolution
policy, to be reviewed against both native damage ordering and retained rendering
facts. Do not implement it as a renderer visibility exception.

## Second-pass status

This report identifies the current split and bounds a proposal; it does not yet
approve an implementation plan. Root will supply the combined design for a
second anti-slop pass after the independent correctness and AoE findings land.

## Follow-up: scattered attack wrappers and an all-attacks query

The human additionally requested the whole attack family, including Frenzy, to
use the same mechanism and asked about a reusable query for attack choices.

### Existing query facts are enough

`AvailableActionsResult.all_actions` already flattens the exact current discovery
result (`dnd/core/base_actions.py:2538`). Its rows include feature actions,
restricted-budget variants, item actions and their current targets/costs. Filter
that result; do not construct attacks again or maintain a list of attack class
names. A small query/helper on this returned result is sufficient.

Be precise about the requested set:

- `BaseAction.is_attack` and `AvailableActionInfo.is_attack` mean
  `ActionCategory.ATTACK` (`base_actions.py:945`, `:2401`). This includes ordinary
  weapon attacks, Extra Attack, Frenzied Strike and monster Multiattack. It does
  not mean that the row is exactly one attack or pays a normal action.
- `outcome_profile.resolution == ATTACK_ROLL` also catches spell attacks
  (`dnd/actions.py:4596`), which are not Haste weapon attacks. It is an outcome
  description, not a cost or reaction permission.
- If the UI requests both weapon attacks and attack-roll spells, the helper can
  combine these existing typed facts. If it requests weapon attacks only, use
  the attack category; do not relabel all offensive AoE spells as attacks.
- Reaction toggles already come from `handler_details` /
  `Entity.get_player_toggleable_handler_infos` (`entity.py:4706`). They are
  trigger affordances, not current targetable Attack commands. Do not inject an
  opportunity attack into `all_actions` just so an attack menu looks complete.

Keep budget/source variants distinct by their exact execution identity. A normal
attack, Haste attack and Extra Attack may share the same authored animation and
weapon while spending different budgets; deduplicating them by behavior ID would
lose legal choices. UI grouping can display them together without changing the
native rows. Reuse the existing discovery snapshot instead of calling discovery
again from a filter and recreating ephemeral variants.

### Thin variants are reasonable, but inheritance is not the fix itself

ExtraAttack (`fighter.py:1268`) and FrenziedStrike (`rage.py:921`) are BaseAction
wrappers that copy declaration, creature validation and cost plumbing, then call
`Attack.attack_consequences`. They should cease to own separate target/range/
roll/presentation paths. Existing Attack inheritance can express thin feature
variants with only authored cost, availability and source selection differences;
NaturalAttack already follows that shape. This does not require a new hierarchy
of target objects or execution services.

However, changing the base class alone is unsafe:

1. `Attack.adjust_cost_for_off_hand` (`actions.py:1890`) replaces costs when an
   off-hand slot has no explicitly supplied `costs` constructor field. A
   subclass's class default or model_post_init assignment is not necessarily an
   explicit constructor field. Extra Attack could silently start paying a bonus
   action. Make the ownership of a feature's explicit cost authoritative; keep
   ordinary slot-default selection a separate default-only operation.
2. Attack supplies `restricted_action_kinds={WEAPON_ATTACK}`. Feature wrappers
   currently do not. Restricted variants also require a compatible positive
   cost, so inheritance does not automatically create every bad variant, but
   Extra Attack/Frenzy must not gain a Haste/Action Surge spend path merely from
   the base-class change. Retain each feature's budget intent explicitly.
3. ExtraAttack's equipped-slot expansion currently supplies resource-paid
   ephemeral variants and declaration names. Preserve its structural-template
   identity, ordering and cost, including explicit off-hand variants. Do not
   use ordinary off-hand bonus defaults for these.
4. FrenziedStrike requires Frenzied at execution but discovery currently checks
   only weapon presence before generic validation. Its advertised melee-only
   contract is not enforced by a generic creature visibility check. Shared
   source eligibility must serve discovery and execution, while its actual
   allowed modes remain an explicit mechanic rather than an inherited accident.
5. Normal Attack's outcome profile includes eligible condition/rider profiles,
   whereas the feature wrappers call only the baseline helper. Centralizing
   those previews can correct a mismatch, but each contributing feature still
   needs target/source eligibility checks; don't broadly grant every rider.

Either thin existing-Attack subclasses or direct calls to a small shared attack
pipeline can work. Prefer the option that actually removes copied methods and
preserves current typed cost hooks. Do not keep both a new AttackSource hierarchy
and the old wrapper pipeline; that would add a third representation.

### Natural attacks expose a genuine hidden-state workaround

`NaturalAttack.get_outcome_profile` and `_apply` (`monsters/traits.py:601`, `:679`)
temporarily erase the actor's main weapon and rewrite unarmed damage dice/type,
then restore them with `finally`. Querying a preview therefore mutates gameplay
equipment, and damage hooks execute while the actor appears to have different
equipment. This belongs in the same cleanup lane if natural attacks are included
in the shared attack-source contract; preserve its existing rules rather than
leaving the mutation hidden beneath a renamed method.

Resolve selected equipped, unarmed or natural attack data directly. A passive
attack-source value or a narrow source-description method can provide range,
damage specification and actual weapon/natural identity to the same pipeline.
Natural data need not be copied into equipment, nor turned into an invisible
Weapon item. Attack bonus, affinity/rider eligibility and declaration identity
must all consult the selected source consistently, not a proxy MELEE_MAIN slot
whose actual equipment may be a sword. Avoid generic arbitrary callables in the
description; derive finite rules through existing typed owners.

Acceptance should include a natural attack while a conventional weapon is
equipped: discovery never changes equipment or visible loadout; resolution does
not erase/rewrite equipped items, and any visible stance change is the explicit
accepted attack contract. Natural range/dice/name are used, and weapon-specific riders do not
mistake the held sword for the chosen claw. Check normal, explicit off-hand,
Extra Attack, Frenzy, Haste, Action Surge and reaction costs before and after the
thin-variant refactor; structural simplicity is not proof of rule preservation.

## Consolidated-plan review

Reviewed `agent_docs/ATTACKS_AND_DESTRUCTIBLE_OBJECTS_PLAN_2026-10-01.md`
independently after the first study and the expanded attack-family request.

**Verdict: approved as a bounded implementation plan, conditional on the human's
two explicitly pending gameplay decisions (object AC and Fireball structural
damage/breach). No blocking anti-slop correction remains in the proposed design.**
This is not approval of unimplemented code or rendered output.

The plan removes the actual duplicate: one Attack lifecycle with finite
recipient dispatch, thin feature variants and the existing item damage and
destruction owners. It identifies frontend admission/stance/binder changes as
part of the migration, rather than promising that an event rename fixes the
bow. Natural/True Strike mutation cleanup belongs because those producers must
participate in the same selected-source contract. Retaliation's spend timing is
explicitly recorded as a correctness change rather than hidden by inheritance.
Fireball remains a spell-specific area-resolution policy with one native source
of geometry truth. No extra registry, target hierarchy, service layer or generic
physics simulation is introduced.

The query-only `performs_attack` declaration is acceptable. The initial study
recommended existing category/outcome metadata; the combined inventory shows
that incomplete spell profiles and True Strike cannot be reliably classified
from those alone. A pure Boolean declaration on the same authored action/row is
smaller than constructing previews, maintaining a spell-name list or introducing
a new attack registry. Its stated ban on granting costs, target permission or
Extra Attack is essential. Test public choices whose category/profile differ,
including True Strike and an attack-roll spell, plus negative setup/grant/save
actions. The declaration must not become a replacement for their execution rules.

Implementation watchpoints, already compatible with the plan:

- Keep the selected-source value finite and passive. It should replace the
  equipment mutation and copied declarations; do not leave both forms active.
- A pure attack-choice query must reuse the supplied discovery snapshot. Do
  not call `get_available_actions` or expand variants from inside the property.
- Preserve old replay inputs as historical records. Read-only compatibility
  does not mean adding new object attacks under a legacy behavior ID.
- Breach visuals need acceptance over time, not just final reach masks: the
  original explosion clock and authored contact/clearance joins must not yield a
  stalled or replayed explosion for each breach stage. Record native stage facts
  once, then inspect the actual saved-event animation.
- Perform the promised removal scan, including imports, registered templates,
  frontend fixed recipe and fixtures. A hidden AttackObject alias with its old
  mechanics would fail the agreed objective even if UI rows are renamed.

After implementation, approval still requires the economy/eligibility matrix,
packet-affinity regressions, cold replay, and direct weapon/impact visual review.
Passing event coverage alone is insufficient, as the original bug demonstrated.

## Implementation review — shared attack and presentation contracts

Reviewed the native implementation after the approved plan, independently of the
native authors. I also implemented the frontend slice, so frontend checks below
are implementation evidence rather than an independent approval of my own code.

The core removal is real. Normal `Attack` now owns creature/object admission,
range/reach, attack rolls and damage packets; `ExtraAttack`, `FrenziedStrike` and
`NaturalAttack` are finite variants. They do not define an object-specific command
or install a second attack registry. `AvailableActionsResult.attack_actions` is
a pure query over the supplied rows using `performs_attack`; it neither discovers
again nor decides costs. `NaturalWeaponSpec` is passive selected-attack data and
does not temporarily overwrite the equipped weapon or unarmed statistics.
Recipient dispatch at `Attack._resolve_attack_with_target_context` retains normal
item Health and destruction, with no fabricated actor for a prop. The native
`AttackObject` class and the live object-attack presentation recipe are removed.
The remaining old content key is historical generated icon/source data, not an
executable alternative.

Two concrete issues found during this pass were sent to the native author and
fixed in the shared path:

- Unarmed/natural attacks selected a hand slot and then left the authoritative
  stance as the equipped melee set. The shared result now explicitly selects
  `WeaponSet.NONE` for those source kinds, preserving the actual items and stats.
- Discovery and declaration duplicated source name/type/item selection.
  `Equipment.snapshot_attack_source_metadata` now delegates to the existing
  complete damage-palette snapshot and is used by both consumers.

The frontend now consumes received `target_kind`, object contact coordinates and
`attack_source_kind`. `ObjectContact` is a finite contact value, not an actor with
invented rig/vitals. Creature anchors and ordinary occlusion are unchanged. The
same cast contact union also renders Fire Bolt on a prop. Explicit source kind
and weapon slot choose visible equipment; projectile presence does not stand in
for equipment identity. Object Damage/Destroyed facts join the ordinary impact,
while creature-only body reactions and blood never run for object recipients.
`AreaReachFact` preserves native stage and destruction lineage identifiers for
the separate staged-AoE implementation; projection and cold replay do not rerun
propagation.

Validation completed for this slice: 33 existing creature-attack cases; six
hit/miss melee/ranged/unarmed object cases; two Fire Bolt object hit/miss cases;
32 passive-event/rig cases; and the existing picker coverage. New object tests
reset the engine, round-trip native and public packets, then bind/sample the real
renderer. They check selected equipment/profile, actual object geometry, no fake
actor, no blood/vitals, ordinary miss feedback, projectile contact in all four
cameras, and object hit-flash at the same impact time. A larger saved-history,
tether, Web and window regression run and full-root suite remain separate gates.

No additional registry, command wrapper, fake entity or generic service layer is
needed. The remaining acceptance is behavioral: full action-economy/progression
suite and real saved-event clips, especially serial Fireball breaches. Do not
infer visual approval from this code review or the event coverage counters.

The paired breach capture exposed a concrete privacy defect during the final
pass: the far observer's reach stage referenced the first door's destruction
lineage even though that observer received no destruction fact. Projection now
filters both previous-stage and prerequisite-destruction identifiers against
actually disclosed facts. The new native paired-capture regression demonstrates
that an undisclosed dependency exists and is removed, while visible dependencies
survive. This is part of the public contract, not a renderer-only concealment.
Final focused object/Fire Bolt/privacy run: **9 passed**. The separate window
presentation regression completed **42 passed** after restarting against the
current migrated attack helper; the earlier process had loaded the obsolete
fixture and was stopped at window setup. Recorded-history, tether and Web had
already completed their preceding 49 + 8 + 6 cases in that run.

Four ordinary catalog cases now capture bow-to-sword, bow-to-unarmed, Fire Bolt
on a crate, and Fireball breaching two real doors. Each records both actual
observers, uses H1 floor art and renders all four camera corners through the
normal saved-input pipeline. The breach fixture uses full room partitions so
its explosion and both doorway clearances can be judged without a narrow-corridor
sprite slice. The final normal pipeline produced 8/8 clips at
[the shared attack gallery](http://127.0.0.1:8767/runs/20261001T131720Z-b09a30/index.html).
Inspection around each door's clearance shows continuous explosion frames (3,
7, 11, 15, 19 across 1.25–1.75 seconds), with the second door and then the far
creature contacted 250 ms apart. Creature damage/blood belongs to its stage;
objects do not acquire blood. The far observer retains its own visibility.
These are review candidates, not a claim of human visual approval.

The later dense-breach overflow rule remains bounded to staged explosions whose
last native reach would occur after the authored clip ended. It stretches the
existing impact frame timeline continuously, preserving first contact and all
frames; it adds no restart, held final frame, second propagation pass, or separate
scheduler. The ordinary two-door gallery fits within the original two-second
impact and is unchanged by that rule.

The adjacent destruction suites had 102 old assertions against the removed
object-gesture lane. Those now join actual shared Attack contact while retaining
original pixel, seek, visibility and flash assertions. This exposed three real
secondary issues rather than hiding them: missing world support before a raised
door contact, delayed prop visibility at clearance, and actor Idle discontinuity
when a longer object break outlived the attack. Root owns the first two; the Idle
clock correction belongs to shared body presentation. Separately, all 166 area
scene/media/handoff replay tests pass after correcting the old deterministic
fixture's save/damage dice interleave for new object recipients. No area renderer
change was needed for that fixture error.

Final adjacent verification after the support/clearance and Idle corrections:
**167 passed** across environment, device and prop destruction plus body-action
and body-release playback; **61 passed** across device destruction, ordinary
attacks and object attacks; **166 passed** across area scene/media and spell
handoff replay. Existing exact pixel/seek/flash assertions remain active. Final
native-event capture regenerated all **8/8** cases after those corrections.
The generic newly-revealed-body filter and ObjectDestroyed-owned observation
clock received this independent review with no remaining blocker: they admit
already-received actors and matching world support together and do not relax
subjective visibility. Full-suite results remain root-owned acceptance work.

The final ECS audit caught a separate entry-binding defect: staging all future
world updates could replace a known intact object's height with its wreck height
before contact. Root limited staging to absent received rows, matching actor
staging, while normal prefix reduction still advances known geometry. Reviewed
that correction without a blocker; the same **167 destruction/body cases passed
again** afterwards. The current palette suite also passed **29/29**. These logs
are preserved in `.runtime/attack-review/validation/frontend-*.txt`.

Exact full-run triage additionally reproduced one `test_area_spell_projection`
fixture error: a scripted creature d20 face was consumed as the newly damaged
open door's d6. Uniform legal faces now exercise the same hidden-recipient
contract without assuming save/damage interleaving. All **4 projection cases
passed**, including the unchanged nondisclosure and native/public round-trip
assertions. This final fix changes only test inputs; the final gallery remains
current.
