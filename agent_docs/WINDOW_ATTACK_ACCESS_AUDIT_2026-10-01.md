# Attack access: implementation audit for fixed windows

October 1. Read-only code audit extending
[the window plan](WINDOWS_IMPLEMENTATION_PLAN_2026-10-01.md), following the user's
request to study all affected actions and especially opportunity attacks.
No attack, reaction, movement or spell behavior was changed by this audit.

## Required contract

Attack passage is requester-dependent spatial evaluation, following the existing
provider/map pattern. It is separate from seeing a target, being within range,
affording an action, and having a walking route. The actor and actual selected
attack supply context; the same unchanged opening may admit a dagger and block a
greataxe. Discovery also respects observer knowledge. Execution checks current
authoritative facts with the actor's actual capabilities.

The rule belongs in spatial data/evaluation, not a window-name branch in combat.
Every crossed provider must admit the request. Parent frame restriction plus an
intact insert restriction remains blocked; removing the insert exposes the frame's
remaining restriction. An unrelated blocker on either side is never ignored.

The user proposed Light-weapon contact through an empty/broken opening. The Light
predicate is not equivalent to “not Heavy” or “piercing”: it includes a handaxe
and excludes spear/rapier in current content. Nonweapon contact policy still needs
explicit selection. This audit identifies every consumer without silently choosing
those remaining rules.

## 1. Exact action integration points

Paths below are relative to the repository. Function names are the durable
integration references; line numbers refer to the audited working tree.

| Consumer | Current code and behavior | Required change |
| --- | --- | --- |
| Main/offhand melee and ranged weapons | `dnd/actions.py`, `Attack.validate_range` (1918), `_validate` (2271): range, visual contact, then ranged pressure | Resolve selected-slot contact/projectile context and run shared spatial admission before costs; retain distinct main/offhand costs |
| Extra Attack | `dnd/classes/fighter.py`, `ExtraAttack._validate`/`_apply` (1370–1421): directly calls range helper and damage resolver | Include the same admission; a patch only in `Attack._validate` misses this path; preserve `extra_attacks` resources |
| Frenzied Strike | `dnd/classes/rage.py`, `FrenziedStrike` (1000–1030): another direct range/damage path | Same admission; retain Frenzy prerequisites and bonus-action accounting |
| Natural attacks and Rampage Bite | `dnd/monsters/traits.py`, `NaturalAttack._validate`/`_apply` (642–689), Rampage (1448) | Build context from the actual natural attack mode; `natural_range` also supports RANGE, so do not force every natural attack through contact policy. Never use its proxy `MELEE_MAIN` equipment to decide passage |
| Multiattack | `dnd/monsters/traits.py`, sequence validation/execution (546–578) | Parent discovery considers permitted children; each child revalidates current passage. Keep legal partial sequences and one parent action cost |
| True Strike | `dnd/spells/evocation.py`, `TrueStrike` (3799–3909): parent checks LOS/weapon, then runs child `Attack` after payment | Parent must validate the selected weapon's spatial context before paying. Child-only rejection is too late. Do not classify it as an empty-hand touch spell merely from a REACH range |
| Opportunity Attack | `dnd/reactions.py`, `opportunity_attack_processor` (17–70): threat exit, then main-hand `Attack` with reaction cost | Trigger geometry and executed main-hand attack must use the same context; retain provocation/handler/resource gates |
| Retaliation | `dnd/classes/barbarian.py`, retaliation processor (1066–1108): damage source/distance/resource gate then ordinary `Attack` | Inherits shared attack admission. Preserve its existing reaction-payment contract; this feature does not redesign it |
| Ordinary touch spells | `dnd/actions.py`, `SpellAction.targeting_error` (4510) | Remove the ordinary-actor early return for the relevant spatial check; shared preflight covers harmful and beneficial touch, with action-specific weapon wrappers distinguished |
| Shake Awake / Shove | `dnd/actions.py`, their validators and execution | Add actual contact admission; a successful contact check does not authorize bodily movement through a frame. Existing forced-movement destination/transition admission remains separate |
| Attack Object | `dnd/actions.py`, `AttackObject._validate`/`_apply` (5159 onward), `GridMap.manual_object_contact` (2269) | Preserve terminal surface contact; passing through the target is not required to hit it. Query intervening providers and selected weapon where applicable |
| Pick Up / Use Object | `dnd/actions.py` and `dnd/actions_functional.py:639`, object discovery in `Entity` | Preserve current hand/contact requirements. Do not apply Light-weapon eligibility because the actor happens to hold a dagger. Deliberate remote controls keep their own semantics |
| Direct placed-object actions | Door, chest, lever, rest and cooking actions; `BaseAction.source_item_error` | Discovery and command execution already check local contact, but direct native application can bypass that wrapper. Enforce local-use contact in the native path; preserve carried consumables and explicitly remote uses |
| Drop | `dnd/actions.py`, `Drop` (5241): adjacent visible destination | Explicitly decide admission for physical item placement through an aperture. It cannot inherit Light-weapon permission merely from the actor's equipment |

No new thrown-weapon executor is implied. Current THROWN metadata does not itself
select a general thrown attack mode in the audited path. A supported ranged attack
uses projectile access according to its actual execution mode, not the size of
the weapon held by the shooter.

## 2. Opportunity attacks: timing and policy

The existing movement timing is already correct for before-departure reactions:

1. `Move._apply` publishes `StepMovementEvent(EFFECT)` at `actions.py:843–867`.
2. The reaction processor compares `event.from_position` and `event.to_position`.
   The mover still occupies the source cell; the reaction targets that creature
   there through the ordinary attack path.
3. Movement debit and actual relocation follow at `actions.py:899–906`, subject
   to interruption checks. Lethal OA can leave the mover at the source without
   charging the uncommitted step.

`Jump._apply` (3352–3400) and `TraverseConnector._apply` (1452–1506) use the same
predeparture ordering. Connector traversal also revalidates after the reaction.
Do not temporarily relocate the mover, strike its future destination, or add a
second opportunity event for the window animation.

### Shared reach does not mean one undifferentiated threat predicate

`Senses.get_threathened_positions` (`dnd/blocks/sensory.py:317`) currently returns
eight adjacent visible/walkable cells admitted by PROPAGATION. It ignores the
selected weapon and its actual reach. It feeds all of these:

| Consumer | Owner | Required distinction |
| --- | --- | --- |
| Actual OA trigger | `opportunity_attack_processor` | Effective supported reaction attack, then provocation and reaction affordability |
| Movement risk preview | `Entity._visible_hostile_threat_domains` (3347), `_opportunity_attack_exposures_for_path` (3372) | Only disclosed hostile threats; record source/destination exit of the same domain used by execution |
| Normal and safe-path previews | `Entity._collect_fast_move_targets` and declared-position discovery | Both routes use the same recomputed threat domains; no stale equipment-dependent cache |
| Ranged weapon pressure | `Entity.is_threatened` (3326), `Attack.check_ranged_conditions` | Physical close-range pressure, independently of whether the enemy has spent an action/reaction |
| Ranged spell pressure | `SpellAction.spell_attack_outcome_profile`, `resolve_spell_attack` | Preview and resolved roll must agree with the same close-range pressure policy |

Do not implement threat geometry by calling `Attack.pre_validate`: it includes
cost affordability. Spending a reaction prevents another actual OA, but does not
magically remove the creature's physical pressure. Likewise, extending OA to
actual longer weapon reach must not automatically extend the separate close-range
disadvantage distance. Reuse passage evaluation, keep these rule gates distinct.

The current OA action is main-hand `Attack`. Do not claim a union of every natural
and offhand attack is threatened while execution still chooses the main hand.
For example, a blocked greataxe in the main hand cannot produce a promised dagger
OA merely because a dagger exists in another slot. Expanding reaction attack
selection would be explicit additional work, not an incidental window fix.

Preserve Disengage, reaction availability/toggles, life/action restrictions and
the event's provocation policy. Forced movement and Misty Step do not acquire
opportunity attacks from this query. Walking, jumping, and window traversal retain
their own currently authored provocation. Earlier nested events can change an
actor or barrier, so actual admission must still recheck before resolution.

## 3. Discovery, execution and cost boundary

`Entity._validate_entity_targets` (`dnd/entity.py:4797`) binds each target to the
actual action variant and invokes `validate_requirements_for_discovery`. That
method (`dnd/core/base_actions.py:1690`) calls `targeting_error` and `_validate`
without affordability; the outer discovery code reports affordability separately.

`execute_available_action` (`dnd/actions_functional.py:489`) can receive a previously
discovered row. It binds and applies the actual template rather than treating the
row as permanent permission. `BaseAction._apply_action` reruns targeting and
validation at 1902 before costs at 1928 and item charges. Maintain that boundary:

- Initially blocked target: native validation cancellation, no resource debit,
  no attack roll/damage/automatic damage to the wall.
- Previously legal menu row after a weapon swap, window change or movement:
  reevaluate the current attack and world before payment.
- Reaction interruption after execution commitment: use existing cancellation
  semantics and already-paid resources; do not refund indiscriminately or disguise
  the interruption as initial validation failure.
- A wrapper paying for child attacks must validate the child's effective context
  before its parent payment, and still revalidate the child when executed.

Both discovery and execution currently call `targeting_error()` without a query
context. Distinguish known-provider discovery from authoritative execution at
those callers with an explicit argument or a small shared helper. Do not invent
an ambient/global discovery mode, or assume the existing call already supplies it.

Ordinary weapon templates already refresh on equipment events in
`dnd/actions_functional.py:update_weapon_template(s)`. Preserve that flow. Movement
preview caches already include computed threat-domain signatures (`entity.py:5392`
and 5926); compute those from current capability-aware results. Do not add a
global per-tile `can_attack` cache or a second target-discovery service.
`Entity.get_available_actions` rebuilds choices on each call, and the encounter
client clears its choices after an operation. No new action-menu revision service
is needed for this feature; test retained rows against current execution facts.

Known-state admission and actor-relative capability evaluation are different
inputs. A hidden reactor may react without being disclosed in the mover's risk
preview. Do not leak hidden objects/gear by returning an omniscient disabled
target explanation. Execution may reject a route that was unknown when offered.

## 4. Spell and contact boundaries

An AST inventory found 117 `SpellAction` family classes, with none overriding the
shared apply, targeting or discovery-validation path outside `SpellAction` itself.
`SpellAction.targeting_error` currently returns early for ordinary
actor casts; only source-item/sector cases receive its target-position checks.
That early return must not bypass the new relevant spatial admission.

Touch is not synonymous with harmful: healing and buffs require actual contact too.
Resolve explicit primary targets/centers for ENTITY, MULTI_ENTITY and POSITION
forms, including self as a zero-crossing case. Do not apply a caster-to-recipient
contact ray to secondary AoE victims. True Strike supplies weapon context; ordinary
touch supplies its actual hand/contact context. A natural attack supplies its own
authored mode and contact/delivery, not the equipped weapon used as damage plumbing.

The contact inventory includes Mage Armor, Protection from Energy, Stoneskin,
Lesser/Greater Restoration, Remove Curse, Protection from Poison, Death Ward,
Freedom of Movement, Resistance, True Seeing, Guidance, Shocking Grasp, Light,
Continual Flame, Cure Wounds, Invisibility/Greater Invisibility, Inflict Wounds,
Bestow Curse, Darkvision, Jump, Enhance Ability and Regenerate. Continual Flame
uses a POSITION target. Guidance, Resistance and Light have no custom `_validate`,
so patching only individual spell validators would miss them.

For source-item casts, operator-to-device contact and device-to-spell-target
delivery are different checks. Preserve the actual spell origin; a distant target
does not require the operator's hand to reach it. Native placed-object use also
needs the local contact check when called directly, without the UI command wrapper.

Do not infer gameplay collision from `projectile_type`: its current declaration
explicitly describes VFX delivery. Nor does RANGE alone prove physical projectile
travel. Non-contact spell targeting, teleportation and secondary area propagation
retain their native owners. This contact work must not silently impose a straight
projectile rule on every spell, redraw clouds or expand the AoE migration.

Hand contact, unarmed/natural attacks and body displacement through the aperture
remain explicit policy decisions before implementing their cases. “Allows Light
weapons” must not accidentally authorize all of them or make a healing spell
depend on which weapon the caster equipped.

## 5. Spatial data and query work

1. Extend the existing authored provider capability and boundary facts with contact
   passage policy. Keep the types dependency-neutral. Ordinary structural behavior
   defaults to structural movement obstruction; a window supplies its restriction.
   Never copy occupied-cell/pathfinding rejection into attack reach.
2. Carry it through `BoundaryStructure`, `WorldEdgeStructuralContribution`, current
   item/boundary presentation and retained spatial facts. Reuse the current physical
   change/sensory lifecycle on destruction. A boolean directional summary alone
   cannot express Light versus greataxe permission for a future client.
   `dnd/ai/runtime/world_projection.py` reconstructs structural contributions and
   selects public object flags; preserve the policy there as well. A policy-only
   change must publish updated spatial facts even when the old boolean channels
   remain equal. Reuse existing events rather than creating new event vocabulary.
3. Build neutral current attack-context facts at action ownership, not in cold
   geometry. Do not import `Entity`, `Attack` or `Weapon` into leaf spatial types.
   Reuse requester-relative provider evaluation, not a callback/modifier registry.
4. Apply the query to structural center and boundary providers along the actual
   segment. Intersect all crossed contributions, including opposite-side owners.
   Hitting a provider terminates at its contacted surface; only that terminal
   contact is exempt from needing passage through itself.
5. Pin diagonal/corner cases geometrically. Current `raycast_clear` uses straight
   grid traversal but delegates diagonal admission to an either-bridge transition.
   An available L-shaped walking route is not proof that the attack segment clears
   a corner. Add explicit attack-segment tests without changing cloud/vision corner
   behavior as a side effect.
6. Integrate all owners in sections 1–4 before claiming a complete shared rule.
   Range-only helpers must not become the sole hidden carrier of unrelated policy;
   keep distance, perceived target eligibility, spatial passage and resource gates
   explicit in shared validation.

## 6. Behavioral acceptance matrix

Tests use public actions, real events and observed state under `HOW_TO_TEST.MD`.
Do not freeze private helper call counts or add one test per generated content row.

| Proof | Observable assertions |
| --- | --- |
| Same actor, different weapons | Dagger versus greataxe across intact/broken/full-breach states; visibility/range unchanged; lawful discovery and execution agree |
| Literal Light policy | Handaxe permitted; spear/rapier excluded if that predicate is selected; no damage-type or animation heuristic |
| Main/offhand and class paths | Correct selected slot and distinct costs; Extra Attack/Frenzied Strike cannot bypass the barrier |
| Natural and touch context | Weapon swap cannot change the legality of an unrelated bite, touch heal or touch damage spell |
| True Strike | Initially blocked selected weapon rejects before outer spell cost; admitted weapon delegates with correct costs |
| Multiattack | Mixed admitted/rejected children, one parent cost, each child rechecks after earlier changes |
| OA at a window | Broken aperture admits only permitted reaction attack; intact insert blocks; full breach restores normal reach |
| OA timing | Walk, jump and connector attacks occur at departure; lethal interruption preserves source and unpaid step |
| OA gates | One reaction, Disengage, disabled handler, nonprovoking movement, forced movement and teleport retain behavior |
| Pressure versus reaction budget | Spent action/reaction does not erase physical close pressure; unavailable reaction still prevents actual OA |
| Weapon reach versus close pressure | Longer reach has correct OA exit; does not enlarge ranged-disadvantage distance by accident |
| Preview agreement | Ordinary/safe path risk and actual OA share known effective geometry; hidden reactors remain undisclosed |
| Stale selection | Change equipped weapon or insert state between discovery and action; current validation wins before debit |
| Terminal object contact | Heavy weapon can hit the insert/frame itself while attacks beyond are blocked; earlier unrelated wall still blocks |
| Direct native object use | Calling the native placed-object action cannot bypass the contact restriction checked by discovery/commands; carried and explicitly remote actions preserve their rules |
| Multiple providers and corners | Parent/inset/opposite-side blocker combine; diagonal/long-reach attacks cannot take a walking detour |
| Target forms | Beneficial/harmful touch, self, position and multiple primary targets; no extra caster-ray rejection of AoE recipients |
| Retained state | Replay disclosed policy and destruction after engine reset; no live map lookup or leaked hidden provider |

Existing baseline checked during this audit:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv \
/home/tommaso/.local/bin/uv run --no-sync python -m pytest \
  tests/engine/test_combat_actions.py tests/engine/test_action_cost_atomicity.py \
  -q -k 'opportunity or threatened or shove or atomic'
```

Result: **16 passed, 21 deselected**, 5.16 seconds reported by pytest. These verify
existing reaction/pressure/cost behavior, not the unimplemented window rule.
Other relevant existing suites include action discovery, Misty Step, condition
transform ownership, traversal connectors, item destruction and trap ground contact.
`tests/engine/test_multicell_objects.py` already covers unrelated barriers,
execution-time interception and stale local-use contact; extend those observable
contracts instead of introducing a separate object-contact test framework.

## Review status

`/root/windows_anti_slop` completed the combat-consumer and reaction-timing audit.
`/root/interiors_backend_review` completed the spell/contact and data ownership audit.
Both independently reviewed this detailed companion against the main window plan
and approved it. The anti-slop reviewer requested preserving ranged natural-attack
mode; that clarification is included. No completed runtime behavior is implied by
this read-only study. The remaining authored physical/contact choices are explicit.
