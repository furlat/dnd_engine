# Summoning backend plan — independent ECS / import-DAG / AI review

Date: 2026-10-03.
Reviewed plan: `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`.
SHA256: `ea1b68c459dad4a66336befb7dd4cd939e2d962288ef9f4256b415a6a90b1758`.
Verdict: **changes requested**. This is a plan review, not implementation approval.

Read AGENTS.md, the recovery plan's current status and design commitments,
HOW_TO_TEST.MD, relevant history/complaint contracts, and the actual Game,
Encounter, action/condition, creature materialization, native AI, movement and
event owners. No production files changed and no tests ran. The working tree
already contains unrelated changes; this receipt identifies the plan bytes,
not a frozen production revision.

## Required corrections

### R1 — Distinguish resource commitment from creature commitment

Plan lines 152–169 list birth/world/encounter commitment before spending action
and slot, then promise that every rejected "pre-commit admission" is a resource
no-op. That conflicts with the named existing owner. In
`dnd/core/base_actions.py:2297`, costs commit before the execution event is
dispatched at line 2316 and before the effect/condition is applied. The owner
explicitly retains costs when execution changes placement/access at lines
2327–2333. Required concentration is admitted later within
`dnd/core/base_block.py:1337`, after the incoming condition applies.

The two commitments cannot be called one atomic boundary. Preserve the ordinary
cast ordering: discovery/declaration validation rejects invalid selection,
placement or missing binding before costs; then action/slot costs commit;
execution reactions run; then effect/lease/concentration admission either
commits the creature or fails without replacing the previous summon. A
post-cost condition/placement veto preserves those already committed costs,
just as a post-cost interruption does. Add separate acceptance rows for a
pre-cost rejection and a post-cost child/admission rejection. If free rejection
after effect admission is actually desired, it requires a separately approved
resource-boundary change; it should not be hidden inside "reuse normal SpellAction."

### R2 — Name the complete binding and teardown seam without a reverse import

The direction `dnd/summoning.py -> Game/Encounter/AI` is sound, and using the
existing mechanical EventHandler pipeline is appropriate. The plan nevertheless
requires Game.close/reset to close this high owner, but does not identify how
Game retains/calls it without the reverse `Game -> dnd.summoning` import. Today's
`dnd/game.py:13` stores only entities and `:48` closes only those entities.
It also has no world/encounter binding registry to satisfy the missing-binding
pre-cost check.

Specify the public composition entry and the small dependency-neutral lifecycle
contract used for Game teardown. For example, an explicit backend bind function
receives the actual Game and Encounter, installs the existing typed mechanical
handler, and registers a close/reset participant through a lower protocol or
typed callback owned by Game. Game must not import the concrete summoning owner.
State how the normal spell declaration/validation identifies an admitted bound
request before costs, including what an unhandled request means, and how
encounter end/rebind differs from terminal Game close. The high owner can remain
one concrete system; this does not require a generic service registry or another
event bus. Identify the backend composition caller/API so this is an executable
connection rather than an implied current-game lookup.

## Accepted architecture in this revision

- One-entity assignments reuse NativeAIController and its existing policy,
  observation, execution and feedback pipeline. They avoid resizing controller,
  assignment, projector and AIKnowledge membership or resetting unrelated AI.
- Exposing Encounter.current_turn_execution_id through TurnContext and
  DecisionEpoch fixes both native decision budgets and basic-policy memory.
  Existing list indices remain positions, not turn identities.
- Encounter owns dynamic initiative and safe deferred removal. The explicit
  start/end/action/movement/reaction cases cover the current cached-controller,
  active-iterator and vanished-current-actor risks.
- The pending-departure authority gate is required because Entity.can_take_actions
  currently reads action permission only; ordinary Game detachment does not
  prevent continued movement or a stale reaction.
- The high system may import installed creature materialization; spell code
  imports passive summon data and normal authored mechanics only. No late
  imports, runtime type-name switches, new entity subclasses, policy rewrite or
  parallel scheduler are needed.
- Faction-less caster admission is explicitly rejected; otherwise merely copying
  None would make the summon hostile under Entity.is_ally/is_enemy.
- Complete recorded birth precedes the new AI assignment's first decision;
  terminal retirement is distinct from reversible remove/redeploy and fake death.

Re-review the revised plan's exact SHA256 after R1 and R2 are resolved. The
proposed spell values and one-creature default remain human decisions, not
decisions made by this reviewer.

## Re-review — revised composition and resource boundary

Reviewed SHA256:
`91d5eceab68ded40dc287bdcd4425cd79ecfeed76853bce1d84cbdd2f87a435c`.
Verdict: **changes requested** for one remaining discovery connection. R1 is
resolved. R2 now names an acyclic composition/teardown route, but its declaration
admission must also work through normal discovery.

### R3 — Pure discovery does not dispatch declaration handlers

The revision requires the bound validation handler to put an accepted binding
identity on a declaration and requires ordinary spell validation to reject an
unhandled declaration. However,
`dnd/core/base_actions.py:1982` constructs a `use_register=False` declaration
inside `validate_requirements_for_discovery`; line 1992 calls `_validate` directly
without publishing or dispatching declaration handlers. `pre_validate` uses the
same path. Following the newly specified connection would therefore make every
summon undiscoverable even when its high owner is bound correctly.

Specify a pure query path used by both discovery and real pre-cost validation.
The existing `EventQueue.preflight` (`dnd/core/events.py:1935`) can evaluate a
dedicated typed summon-admission event through the same validation-only handler,
without publishing a cast or constructing provisional actors. Do not preflight
the entire ordinary SpellEvent handler population: ordinary reaction handlers
are not all validation-only. Revalidate the accepted world/operation binding at
execution as the plan already requires. Add bound/unbound discovery and
discovery-no-mutation to acceptance.

The teardown change is compatible with actual reset ordering:
`reset_engine_runtime` resets EventQueue before Entity registries;
`EventQueue.reset` clears its event generation before calling registered system
reset methods, so the proposed silent reset is necessary and correct. Ordinary
Game close remains a separate causal operation through a lower callback type.

One implementation clarification is also needed for the named lifecycle hook:
Encounter.end_encounter directly constructs an EncounterEndEvent at COMPLETION.
`EventQueue.register` does not run pre-completion systems for that constructor.
Existing controller `on_encounter_end` already closes native assignments; use
that real boundary for encounter-end work, or explicitly route the fact through
the existing completed-fact publisher if more lifecycle bookkeeping is needed.
Do not assume merely indexing the high system for ENCOUNTER_END invokes it.

The revised exact caster-owned duration, encounter-end pause, explicit rebind,
intrinsic-only recipe admission, both stable AI turn keys and immediate departed
actor authority gate remain consistent with the bounded ECS design. No tests or
production changes were made during this re-review.

## Final re-review — ECS / import-DAG / AI approval

Reviewed SHA256:
`aa1bb2068c4380004b4886b59ee10cf33b69c300ef94aa058721452da056c60a`.
Verdict: **APPROVED as an implementation plan. No unresolved ECS, import-DAG,
AI or turn-lifecycle blocker remains in this revision.**

R1 is resolved by keeping existing action/slot commitment before execution and
separating it from creature/concentration commitment. R2 is resolved by explicit
`bind_summoning(game, encounter)`, a dependency-neutral Game close callback, and
the existing indexed system's separate silent reset. Game never needs a reverse
import of the concrete high owner.

R3 is resolved by the dedicated unpublished summon-admission proposal evaluated
with EventQueue.preflight. Both discovery and real pre-cost validation explicitly
call the same pure helper. Only its narrow validation-only handler participates;
no ordinary SpellEvent blanket preflight, event publication, actor creation,
lease preparation or persistent admission cache is introduced by discovery.
Execution revalidates the bound operation. This matches the actual preflight
contract and handles unregistered discovery declarations.

The encounter-end clarification is also resolved: existing controller
on_encounter_end closes assignments; explicit rebind and Game close/reset release
retained references. The plan no longer depends on a pre-completion system
receiving a directly constructed terminal EncounterEndEvent.

The reviewed design continues to reuse ordinary native AI with per-summon
assignments, passes the existing execution identity to both AI budget and policy
memory, and gives Encounter the live insertion/removal and safe-unwind boundary.
It explicitly revokes pending/departed action authority across movement and
reactions. Caster-owned unique leases, exact concentration links, intrinsic-only
form admission, recorded birth before AI, and cause-specific terminal cleanup
remain bounded compositions of the existing owners.

This approval is for the exact plan bytes above. Proposed spell values and
one-creature defaults still await human acceptance; implementation must pass its
specified behavior/architecture checks and independent implementation review.
Only this audit document was edited for this review. No production edits or test
runs occurred.

## Focused clarification review — independent creature definitions

Reviewed SHA256:
`18f468caa0dd424537e4836b18b1176653b886869729c60c684a54d21c0886ac`.
Verdict: **APPROVED as an implementation plan. The creature-independence
clarification introduces no ECS, anti-OOP or import-DAG blocker.**

This review covers the new section 1 invariant, two section 2 paragraphs and
the creature-independence acceptance row. Removing precisely those additions
in memory reproduces the previously approved SHA256
`aa1bb2068c4380004b4886b59ee10cf33b69c300ef94aa058721452da056c60a`;
the rest of the plan is unchanged.

The clarification places body, stats, gear and abilities in one canonical
creature recipe that constructs without a summoner, spell or lease. Summoning
adds relationships and lifetime/initiative/departure rules to the instantiated
entity through the existing high owner. It does not require creature constructors
to import or understand summoning, create summoned subclasses, or duplicate
statblocks and per-species executors. Fey adaptation is explicitly local to the
incoming instance before birth. The recipe and other instances remain unchanged.

The intrinsic-only restriction is correctly limited to admission by this
summoning adapter. It neither strips normal authored equipment nor changes
ordinary creatures' death, corpse or possession behavior. The added public
acceptance row compares ordinary and summoned construction from the same recipe
and explicitly covers instance isolation and ordinary equipped creatures.

Prior findings remain resolved and prior plan approval carries forward to these
exact revised bytes. This is documentation review only: no broad source audit,
production edits or test runs were performed. Only this audit was appended.

## Revised design review — direct dependencies and Fey control

Reviewed SHA256:
`ad8fc389b313c205de78ca1064a71ee41810e6a8a7a737432fa1b97a3d86bce1`.
Verdict: **changes requested** for three concrete native commit/lifecycle seams.
Earlier approvals do not approve this substantial revision.

The requested dependency simplification is correctly represented: optional
concentration links directly to Summoned for animals/fiends; nonconcentration
uses Summoned alone; only Fey needs an untimed control child. Summoned owns the
one creature clock. Control loss preserves Fey identity, duration, controller and
turn budget while changing recorded faction and dismissal authority. The module
separation, pure discovery and stable turn identity remain appropriate.

### R4 — Split prepared birth commitment from birth publication explicitly

Section 6 commits aggregate/world/encounter state in step 6, then publishes birth
in step 7. The listed `compose_entity(parent_event, summon_origin)` does not by
itself support that order. Entity.validate_initial_composition and compose_entity
reject an already committed or deployed entity (`dnd/entity.py:1208–1213` and
`:1276–1286`), while world attachment requires creation_committed (`:678–683`).
Fixing compose_entity's catch-all rollback alone does not resolve those mutually
exclusive preconditions.

Name a bounded prepared-birth seam: validate and capture the admitted birth before
commit, commit the entity identity/creation flag without publication, commit the
prepared Game/Encounter memberships, then publish that exact prepared birth.
Keep ordinary compose_entity as the wrapper for its ordinary undeployed caller.
The existing condition/concentration and presence publishers likewise must have
an explicit commit-versus-publication role so no callback observes half the new
authority graph.

The prepared-record ownership must also preserve the declared DAG. In particular,
Entity.commit_initial_conditions cannot import concrete Concentrating from
dnd.conditions or SpellAction from dnd.actions: both already import Entity.
State the lower-owned prepared condition token/BaseCondition commit hook, or keep
concentration orchestration in its existing upper action owner and pass only the
admitted lower condition/link results to Entity. No high-type local imports or
runtime type-name dispatch.

### R5 — Per-condition completion is still inside the removal graph

Section 7 correctly forbids recursive graph removal, but says to finish
retirement at the accepted condition completion boundary. Today's
`BaseBlock._commit_prepared_condition_removals` calls cleanup, index removal,
on_membership_changed and phase_to(COMPLETION) for each child while iterating
the graph (`dnd/core/base_block.py:1063–1106`), then publishes linked-parent state
at `:1108–1112`. The registered PreCompletionSystem runs even earlier, inside
phase_to at `dnd/core/events.py:436–437`. Neither is an outer graph-settled point.

Specify one existing-owner extension that exposes the settled outer removal
result or invokes a lower lifecycle hook after all children, parent links and
ordinary resulting-state publication finish. At actual removal commit, revoke
departing agency and retain the exact prepared retirement consequence. Drain
that consequence once at the outer graph boundary; do not reenter actor/condition
retirement from a per-child pre-completion callback. Nested concentration
replacement must join this same outer boundary. Do not use passive batch
observers for mechanics or introduce a general event-work queue.

### R6 — Involuntary concentration loss must enter the required release path

Mandatory retirement currently begins after a "committed loss" of the sustaining
effect. However, existing concentration damage/death handlers call ordinary
cancellable remove_condition (`dnd/conditions.py:2053`, `:2060`, `:2086`). A veto
on the concentration root, Summoned or Fey control can prevent that loss from
committing, so the new mandatory retirement handler never runs. Fey would remain
controlled after a failed concentration save instead of becoming hostile.

Name the typed involuntary sustain-loss entry from those concrete damage/death
handlers into the removal owner, and how it reaches the exact linked summon
condition/control child. This must distinguish involuntary loss from voluntary
DropConcentration/replacement and must not become a universal force flag or
silently rewrite unrelated cancellation semantics. Add failed-save/source-death
cases with a vetoing linked-effect handler: animal/fiend must depart and Fey must
lose control while preserving its remaining lifetime. The matching voluntary
rejection must preserve its current authority and links.

No production edits or tests were made. Only this review document was appended.
Re-review the corrected exact plan hash before claiming approval.

## Re-review — prepared birth, settled removal and required sustain loss

Reviewed SHA256:
`f25f04b5d80357bad5417743ac73afc248880550320ce84527e275e39c06feed`.
Verdict: **APPROVED as an implementation plan. No unresolved ECS, anti-OOP,
import-DAG, AI or turn-lifecycle blocker remains in this revision.**

R4 is resolved. Entity now owns a PreparedBirth captured while uncommitted and
undeployed; commit_birth changes creation authority without publication, then
prepared Game/Encounter membership can commit, and publish_birth publishes the
same fact without repeating the old undeployed precondition. Ordinary
compose_entity wraps those operations. Condition/concentration/deployment/join
owners explicitly separate state commitment from publication for these prepared
operations. Lower BaseBlock-owned prepared application records and the
BaseCondition commit hook keep Entity independent of concrete Concentrating and
SpellAction types; the upper owner orchestrates admitted lower tokens.

R5 is resolved. The removal scope belongs to the existing native condition owner
and covers complete outer removal, incoming application/replacement, drop_slot
and prepared summon creation. Nested calls share the scope. Per-child handlers
only revoke departing authority and retain the exact prepared consequence.
The dependency-neutral settled callback receives actual committed receipts after
parent links/publications, resets the scope before dispatch and consumes pending
consequences before execution. Publication errors still settle committed work.
No passive observer, generic work queue or high-owner import in BaseBlock is
needed.

R6 is resolved. Existing failed-save/zero-HP/death concentration handlers enter
typed InvoluntarySustainLoss before ordinary veto can retain the required link.
The lower passive policy is ordinary by default; only the actual Summoned or
Fey-control dependency requires release. An unrelated retained branch cannot
retain or recreate that exact link/slot authority. Voluntary drop/replacement
keeps its separate admission policy. The acceptance matrix covers the required
contrasting outcomes.

The final composition preserves the user's simplification: animals/fiends use
Concentrating -> Summoned; the direct nonconcentration path uses Summoned alone;
only Fey has an untimed control child. One creature-owned duration survives Fey
control loss and caster death. Recorded faction changes update the existing AI
pipeline, including movement revalidation, without new controllers, turns or
budgets. Independent creature definitions and ordinary corpse/item behavior stay
outside the summon instance's lifecycle.

The corrected placement boundary uses existing creature anchor-tile admission
for ordinary and summoned instances, with subjective discovery and objective
execution. It does not introduce multi-cell creature geometry or hidden-occupant
disclosure into this lane.

Approval applies to the exact design bytes above, not implementation correctness
or authorization to start coding. Proposed gameplay defaults remain subject to
human approval. The implementation still requires its stated contract checks and
independent reviews. Only this audit document changed; no production edits or
test runs were performed.

## Expanded creature batch — paired review

Reviewed exact SHA256 values:

- Main plan: `e2b10dacbeb9e69d60822af251e66db89a361c1342ddb9c7ede15bdf6ad3a094`.
- Creature batch: `ccdddc29658280d92bc93c7d01309cff1dde87f97bf7f3e3995d9135f7894888`.

Verdict: **CHANGES REQUESTED for one concrete native attack-composition gap
(R7).** The reviewed lifecycle design remains intact. The expansion otherwise
has a bounded ECS/import-DAG implementation route: 17 ordinary new beast recipes
and three ordinary new fiend recipes, plus four existing recipes; Fey reuses the
same 18 beast definitions. Cold form selection points toward those recipes;
the recipes do not point toward summoning or rendering. Intrinsic items and
explicit native trait/action grants remain existing composition owners.

### R7 — Two intrinsic attacks currently inherit off-hand weapon rules

The companion promises ordinary Bite/Claw or Bite/Tail alternatives and exact
bear/Fellwing Multiattack damage through existing intrinsic possessions and
configured Multiattack. Current native equipment cannot deliver those rules
merely by putting the second attack in MELEE_OFF:

- `Weapon.compatible_equipment_slots` admits that slot only for LIGHT weapons
  (`dnd/blocks/equipment.py:400–409`); the explicit diagnostic is at `:445–448`.
- `update_weapon_template` constructs an Attack without an explicit cost
  (`dnd/actions_functional.py:224–234`), so Attack assigns an off-hand bonus-action
  cost (`dnd/actions.py:1945–1958`). LIGHT therefore permits an additional attack
  contrary to the promised ordinary alternative/one-action sequence.
- Runtime weapon damage uses off-hand ability handling (`equipment.py:495–514`,
  `:1234–1245`); the separate AI damage-profile path does likewise (`:1031–1042`).
  Multiattack's `costs=[]` prevents extra child costs but does not restore the
  missing ordinary ability contribution.

State the bounded native correction before approval. A passive held/body usage
on authored Weapon definitions and runtime Weapon, defaulting to current held
behavior, can share one usage query across slot admission/revalidation, ordinary
template cost, actual damage, AI damage profiles and physical access. New body
attacks can then occupy the second intrinsic slot without LIGHT, cost one action
when standalone, and use ordinary ability damage in either slot. Existing
Multiattack still constructs the same Attack children with `costs=[]`; no second
resolver, controller or action-economy system is necessary. Apply this explicitly
to the new recipes rather than changing all existing intrinsic items by inference.

Also pin each new recipe's primary attack: the current opportunity attack and
threat-access owners use MELEE_MAIN (`dnd/reactions.py:49–60`,
`dnd/entity.py:3355–3359`). Keep exact item/attack identity for save riders and
presentation. Acceptance should check the actual standalone and composite
cost/damage paths, no unintended bonus attack, and matching AI outcome profiles.
Haste and Slow should continue through the existing Attack/restricted-action and
attack-multiplicity owners, without granting Haste an entire Multiattack.

The other selected capabilities are present: configured repeated attacks in
`dnd/monsters/traits.py:534`, save-based Prone riders at `:863`, MagicResistance
at `:1532`, InnateFlight at `:1552`, and Devil's Sight in the existing sensory
owner (`dnd/blocks/sensory.py:663–720`). They do not require the deferred charge,
pounce, grapple, hover or multi-target rule systems. Exact hit-rider identity
still needs the shared tightening already required by the companion.

Only this audit was appended. No production edits, tests or other-chat reads
were performed. Re-review the corrected pair of exact hashes before approval.

## Expanded creature batch — R7 re-review

Reviewed exact SHA256 values:

- Main plan: `d32f941cbca1329356b047cf3600ce112a694f89660fcb875f553b93800e0bff`.
- Creature batch: `d901ac3bade5f823db72561c442b8154fa4847996a7959e92eecd121dbed220c`.

Verdict: **APPROVED as the paired implementation plan. R7 is resolved; no
remaining ECS, anti-OOP, import-DAG, native-attack or AI/turn-lifecycle blocker
was found in these revisions.**

The companion now places one passive held/body value in existing authored and
runtime weapon data. Its shared query covers equipment admission/revalidation,
explicit standalone action costs, runtime damage, AI damage profiles and physical
access. Body usage requires exact intrinsic ownership and is explicitly authored;
it is not inferred from summoning, species, appearance or item names. The existing
Attack and Multiattack owners continue to resolve all attacks. No new entity
hierarchy, registry, anatomical inventory or action-budget implementation is needed.

Primary attacks are explicitly assigned, so existing main-position threat and
opportunity-attack selection remains coherent. Secondary body choices cost an
ordinary action, while Multiattack children retain their explicit empty costs.
The plan preserves native Haste/Extra Attack eligibility for individual attacks,
keeps Multiattack outside Haste's weapon-attack grant, and uses the existing Slow
and reaction limits. Acceptance now includes full ability modifiers in both
positions, native/AI profile parity and absence of an accidental bonus attack.

The opt-in also deliberately covers the selected existing wolf/dretch anatomical
definitions. This is a disclosed scope correction: canonical identities, base
stats, dice, traits and configured sequences remain, while Dretch's incidental
standalone off-hand bonus entitlement is corrected. It does not promise that
every legacy behavior is unchanged, infer body usage for unrelated intrinsic
items, or alter ordinary held-weapon semantics. The earlier review's suggestion
to preserve the four existing recipes completely is superseded by this explicit
and bounded choice.

Recipe composition remains independent of summoning; low weapon/equipment
owners import neither creature catalogs nor the high summoning owner. The
previously reviewed birth, condition graph, concentration/Fey exception, sole
duration, retirement and stable-turn design remains in place.

This approves the exact design pair, not implementation or proposed balance
defaults. The stated implementation checks and independent reviews remain
required. Only this audit was appended; no production edits or tests were made.

## Unified single-document plan — final review

Reviewed SHA256 of `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`:
`001c6bed12ad477b1b386bd985e6cb5f8293f6d644de9be8908121b61575e815`.

Verdict: **APPROVED as the unified implementation plan. No unresolved ECS,
anti-OOP, import-DAG, native-attack, AI/turn-lifecycle or merge-created dependency
blocker was found.** This single hash supersedes paired-document approval for
the current authority. The former creature document is only a superseded pointer.

The preserved pre-consolidation files match the previously approved hashes
`d32f941cbca1329356b047cf3600ce112a694f89660fcb875f553b93800e0bff`
and `d901ac3bade5f823db72561c442b8154fa4847996a7959e92eecd121dbed220c`.
Direct document comparison confirms that native sections 5–9 are unchanged
byte-for-byte. The complete creature authority, 24-row table, authored gameplay
adaptations and held/body attack policy are unchanged apart from heading
renumbering. The condition graph, lower prepared tokens, one committed birth,
settled removal callback, required sustain loss, Fey-only control exception,
single duration, exact retirement and stable turn execution identity all remain.

The merged ownership and delivery sequence is coherent. Ordinary weapon and
creature composition precedes native lifecycle seams; explicit Game/Encounter
binding and ordinary AI consume those seams; the three spell adapters connect
the canonical selection and admission route. Event fields and shared reducers
are implemented alongside their producers, with later presentation completion,
so the sequence does not require a temporary duplicate journal or renderer-owned
mechanics. One acceptance ledger accounts for every creature and action mapping.

Canonical recipes remain independent of summoning and art. The shared held/body
value remains passive lower weapon data. Presentation resolves content references
through existing rig/clip ingestion and retained actor facts. The source owners
are present: `game/animation_data.py:77` resolves actor layers,
`game/animation_types.py:692` and `:704` define BodyClip/BodyRig, and
`game/animation_draw.py:390` owns common body sampling/material application.
The planned shared Fey body-material binding is acknowledged implementation
work; it does not require native-condition queries or a per-species drawing path.
Manifestation persists independently of faction/control and is retained for
live presentation, historical playback and authorized reacquisition.

The misdirected arena request has been removed from this exact revision. No
large-map fixture, dungeon expansion, new geometry or special AI work is approved
by this verdict. Representative native combat recordings and validation of all
24 rigs and primary/secondary actions remain required.

Approval concerns the concrete design, not implemented behavior or authorization
to begin coding. Proposed gameplay defaults and final implementation acceptance
remain subject to the plan's human/reviewer gates. Only this audit was appended;
no production edits, test runs or other-chat reads were performed.

## Alternate-rig component and visual addendum — review

Reviewed exact SHA256 values:

- Main plan: `001ec7cedbd75d639daf9d43063d865c34605b3ce441a391686479b5646daac9`.
- Visual addendum: `fadcebe641f88e0f43a487e07f272f75a9ce4b0c63ad1764074b8b8f4069a34d`.

Verdict: **CHANGES REQUESTED for R8, the incomplete body-context selector and
resolved playback contract.** Keeping the existing BodyRig registry and adding
rig constraints to the existing pure attack-profile selector is a sound DAG/ECS
design. No second registry, native species dependency or new renderer/runner is
needed. The visual addendum correctly distinguishes source inventory/primary
inspection from unverified secondary motions, markers and flying poses. Its
later VFX list grants no mechanics or permission to contact another thread.

### R8 — Distinguish recorded motion and retain each resolved body phase

The proposed body-context selector has a role and optional action/condition
reference or movement mode. That cannot by itself distinguish ordinary travel,
jump and connector traversal as section 10.2.1 requires. MovementFact contains
trajectory and connector_presentation_key but no action/behavior reference
(`game/player_facts.py:166–181`). The existing movement binder chooses jump from
DIRECT_ARC and connector presentation from its exact key
(`game/choreography.py:1810–1816`). These motions can share a movement mode.
Use those existing retained values in an explicit discriminated selector, or
finite roles derived solely from them. Specify exact-match/default behavior;
independently optional wildcard fields must not introduce ambiguous fallback.

Complete the body-only result and consumer contract at the same boundary:

- Name looping, reversed transition, held/rest pose and named marker semantics
  using the existing passive records. ActionActor alone has none of the first
  three (`game/animation_types.py:1127–1133`); Prone entry/removal uses
  ConditionBodyAnimation.reversed and persistent pose selection
  (`game/condition_types.py:264`, `game/condition_animation.py:233–260`).
- Primary and recovery bindings must both be resolved and retained by the
  existing cue. `join_body_action` and `sample_body_action` use separate recovery
  fields (`game/body_action.py:171–195`), while `sample_forced_body` rereads the
  global forced-movement recovery (`game/forced_movement.py:169–187`). Merely
  replacing the primary clip can still request an unavailable human Taunt.
- Explicitly include `bind_shove`, `bind_forced_movement` and their samplers in
  `game/forced_movement.py`. ShoveFact does not enter the ActionFact/SpellFact
  body_action route. Likewise enumerate the existing healing and damage/life
  body owners for verified defaults or necessary overrides; they must not be
  omitted from the claimed reachable-context coverage.
- Define disabled gestures concretely: `bind_body_action` still looks up its
  clip before checking enabled (`game/body_action.py:159–163`). Author a valid
  neutral Idle record, or have that existing owner skip unused body lookup while
  preserving the effect and child join. Do not use a missing clip as a no-op.

For attack rows, retain the actual source representation: this batch's body
weapons are intrinsic items using the recorded equipped source kind and exact
item identity. The separate NaturalAttack route uses source kind natural.
Rig-scoped selectors must not silently require natural for the item-backed
attacks. Existing profile precedence remains the single attack selector.

These are bounded extensions to the proposed shared component, not requests
for new animation or gameplay frameworks. All previous lifecycle/body-attack
approvals remain unaffected. Only this audit was appended; no production changes,
tests, artwork edits or other-chat reads/messages were performed.

## Alternate-rig component and visual addendum — R8 re-review

Reviewed exact SHA256 values:

- Main plan: `d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`.
- Visual addendum: `28dbdf5dec4fcc45afe6a5434ca297ec22da58715a0f044dcd37b9ca18011075`.

Verdict: **APPROVED as the implementation design and its linked visual ledger.
R8 is resolved. No remaining concrete ECS, anti-OOP, import-DAG or alternate-rig
selector/timing/ownership blocker was found in these revisions.**

The discriminated qualifier now uses the actual retained movement signature,
including trajectory and connector identity, or an exact content reference.
Exact match, one role-default and a verified compatible shared recipe form an
explicit resolution order without overlapping wildcard combinations. Missing
historical facts are not reconstructed from names. The pure helper and authored
records remain beneath existing binding/sampling owners; no new registry or
event execution path is introduced.

The body result includes validated playback, reversal, held/rest poses, frame
keys and complete context markers. Existing cues retain resolved primary and
recovery data together for both timing and sampling. Shove and forced movement
are explicitly routed through their real binders/samplers; condition phases,
equipment, healing, optional save motion and damage/life defaults remain covered.
Disabled gestures use a valid neutral binding or skip only unused body lookup,
while preserving the action's ordinary effect and child join.

Attack selection remains solely in the existing profile owner with optional
rig constraints. Intrinsic body items keep their recorded equipped source kind
and exact item identity; NATURAL physical access is not confused with the
separate NaturalAttack event representation. Ordinary and summoned copies use
the same body/action records, with Fey manifestation changing retained material
only. No native creature module or live Entity lookup enters presentation.

The addendum remains an honest coverage ledger: source availability does not
prove secondary motion, contact, Prone or flying-pose adequacy. Required mapping
gaps must close in this batch; the identified later VFX remains separate and
requires the human's own handoff. No cross-thread delivery is authorized.

This is exact-design approval, not a claim that the media is already calibrated
or the implementation tested. Only this audit was appended; no production edits,
tests, artwork changes or other-chat reads/messages were performed.
