# Summoning backend plan — independent anti-slop review

Reviewed: 2026-10-03.
Plan: `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`.
Exact reviewed SHA256: `ea1b68c459dad4a66336befb7dd4cd939e2d962288ef9f4256b415a6a90b1758`.

**Verdict: changes required.** This is a design review, not an implementation
approval. No production code or tests were changed or executed. Inspection used
AGENTS.md, the current recovery plan, HOW_TO_TEST.MD and the actual native owners.
The proposed one-creature rule, slot table and duration remain explicit proposals
for the human; this review does not convert them into prior user decisions.

## Blocking findings

### AS1 — Preserve the actual resource commitment boundary

Plan section 5, steps 3–5 (lines 159–169), promises all rejected pre-commit
admission is a resource no-op while describing effect/concentration admission
before action/slot spending. The existing action owner does the opposite:
`BaseAction._apply_action` commits costs before publishing EXECUTION and before
calling the authored `_apply` (`dnd/core/base_actions.py:2299`). Its second access
check explicitly treats changed geometry after EXECUTION as an interruption
without a refund. Condition/concentration veto can occur inside `_apply` after
those costs have committed.

**Required correction:** distinguish pre-cost validation from pre-spawn
admission. Invalid form/faction/binding/placement discovered before the cost
boundary spends nothing. Counterspell, changed geometry and effect/concentration
veto after that boundary retain ordinary committed costs, while preserving the
previous summon/concentration and discarding only provisional incoming objects.
Do not move or refund shared spell costs to satisfy an imprecise transaction
promise. Require public cases for both sides of the boundary. Limit the
section's retry guarantee to the same accepted operation identity; a fresh cast
is a fresh action, not an implicit idempotent network retry.

### AS2 — Bound item changes to the selected native forms

Sections 3, 4, 9 and 12 require immutable temporary-item provenance, cross-holder
expiry and stack-merge changes. The exact selected forms have no ordinary
conjured equipment or stacks: Wolf and Dire Wolf have intrinsic natural armor
and bite, Dretch has intrinsic natural armor/bite/claws
(`dnd/monsters/srd_roster.py:1292–1336`); both authored demon variants reuse that
Dretch composition (`dnd/monsters/demon_variants.py:27`). Fey uses the same wolf
composition. Consequently the temporary stack and transferable conjured-gear
machinery serves no admitted content in this bounded plan.

**Required correction:** retire exact intrinsic anatomy with its summoned owner
and preserve real possessions acquired later through existing item ownership.
Defer nonintrinsic conjured equipment, temporary stacks and temporary containers
until a selected approved recipe actually needs them, rejecting such recipes at
the allowlist/composition boundary in this slice. Remove those speculative item
changes and acceptance cases from the implementation scope. Keep the real-item
drop/preservation and intrinsic retirement cases: those exercise actual behavior.
If transferable conjured equipment is required now, name the concrete requested
form and exact item recipe that makes the work necessary rather than authoring
extra infrastructure for unspecified future content.

### AS3 — Define terminal cleanup semantics instead of delegating the decision

Section 8 (lines 262–268) requires both pre-admitted vetoable cleanup and a
non-vetoable natural-expiry/source-death/close path. It does not choose the owner
operation or commit behavior when required real-item release/landing or a linked
condition rejects removal. Current BaseBlock removal preflights and aborts the
entire graph on a veto (`dnd/core/base_block.py:988–1039`);
`BaseItem.retire` can return on rejected floor removal and otherwise ignores
condition-removal results (`dnd/blocks/base_item.py:711–741`). Neither operation
already implements the stated forced terminal contract.

**Required correction:** name the bounded terminal retirement mode in the
existing owners, its admissible causes, and which published operations are
facts after irreversible departure rather than cancelable requests. Specify
where real items are preserved when their holder leaves and whether any
remaining failure is pre-commit rejection or a committed publication error.
Avoid a universal force flag that bypasses cancellation throughout unrelated
conditions/items. Add exact observable cases for natural expiry and Game.close
with real possessions and a relevant rejected removal, contrasted with a
vetoable voluntary replacement that preserves the old summon.

### AS4 — Make the single lifetime clock concrete

Sections 1/4 promise ten rounds and one lease clock, but never assign the lease
to a specific ticking entity or state the first decrement and exact final
departure boundary. Section 7 (lines 246–248) additionally asserts ordinary
outside-combat world time continues ticking it, without identifying a caller.
The inspected `Game` has no world-time advance operation. Entity-owned Duration
progression runs at `Entity.on_turn_start` and
`Entity.advance_duration_condition` (`dnd/entity.py:1726`, `:2322`); Encounter's
other clock concerns spatial/tile/floor-item effects.

**Required correction:** locate the lease on its exact native owner, define cast
turn versus first/last decrement and explain how multiple exact concentration
slots obtain independent condition identities. Name an actual outside-combat
public duration boundary and its explicit caller, or clearly propose that the
lease remains until normal owner ticks resume. Do not imply an existing
automatic world clock or introduce a second timer. Public tests must prove
expiry across encounter end/rejoin under the chosen rule.

## Small correction

Section 1 says Conjure Fiend "includes demon and devil recipes" (line 42), but
the proposed table contains only Dretch and two authored Dretch variants. Say
the family can later admit either subtype; the bounded initial table is demons.
Do not add devil content merely to repair this sentence.

## Sound decisions retained

- The installed materializer, existing condition/concentration graph, Game world
  ownership, Encounter turns and native AI pipeline are the right existing
  owners. The explicit warning about incoming effect application preceding
  required concentration admission correctly prevents premature birth.
- One native assignment per currently proposed one-body cast avoids resizing
  party AI memory and stale departed-member sensory authority. No policy fork
  or master command stream is needed.
- Faction-less casters are explicitly rejected before costs rather than silently
  generating a hostile summon. Exact source recipe and manifestation data are
  separate from future artwork.
- Live turn insertion/removal and stable turn identity are necessary concrete
  gaps, not justification for a second scheduler. The public-boundary removal
  cases are useful.
- Reversible Game removal is correctly distinguished from terminal retirement.
  Preserving independent effects, event history and real possessions is required.
- Undead, rendering, server, full asset roster and general creature transforms
  remain excluded. The test plan correctly uses native public boundaries.

Re-review the revised exact hash after AS1–AS4 and the small scope correction are
resolved. No conditional or stale-hash approval is given.

## Re-review — 2026-10-03

Exact revised plan SHA256:
`91d5eceab68ded40dc287bdcd4425cd79ecfeed76853bce1d84cbdd2f87a435c`.
The hash was checked before and after the complete revised-plan read.

**Verdict: APPROVED as an isolated backend implementation plan. No remaining
anti-slop blocker was found in this revision.** This supersedes the initial
verdict only for this exact hash. It is neither implementation authorization nor
a claim that unimplemented behavior has passed tests. Human approval of the
explicit gameplay proposals remains the plan's separate next gate.

Findings resolved:

| Initial finding | Verified resolution |
| --- | --- |
| AS1, resource boundary | Section 5 now preserves BaseAction's cost-before-EXECUTION order. Pre-cost validation is a no-op; post-cost counterspell/placement/condition interruption retains expenditure while discarding only provisional incoming state and preserving the old summon. Same-operation duplicate delivery is distinguished from a newly issued cast; no retry cache is added. |
| AS2, speculative item scope | Section 9 limits admitted forms to their actual intrinsic natural gear, validates this before birth, and defers temporary stacks, containers and transferable conjured equipment. Real acquired gear/bags retain existing identity and are preserved on departure. The work and test matrix now match those selected forms. |
| AS3, terminal cleanup | Section 8 defines voluntary vetoable preparation separately from mandatory release authorized by exact lease identity and committed cause. Existing owners receive a bounded typed terminal context, rather than a global force bypass. Real possessions land through native nonblocking ground-item ownership; missing supported tiles are invariant failures that preserve item identity, not permission to destroy possessions. Publication errors remain distinct from rollback. |
| AS4, lifetime clock | Section 4 places a cast-unique lease on the casting Entity, links the exact concentration slot, and states the first and tenth subsequent owner interval. Other turns do not tick it; duplicate intervals do not retick it. Section 7 explicitly pauses ticks outside combat and resumes on owner turns after rejoin; it no longer invents an existing automatic world clock. |
| Demon/devil wording | Section 1 now accurately describes the initial table as demons only; adding future devils is not part of this implementation. |

The new explicit backend binding and close/rebind/reset contracts close concrete
ownership gaps without adding a second summon registry, action economy or AI
policy. I inspected the relevant existing EventQueue lifecycle registration/reset
and Game close boundaries: the proposal uses the native indexed lifecycle system
and separates live causal close from silent generation reset. Its new Game close
callback is a bounded composition seam, not serialized mechanics or a service
locator.

The revised plan retains the required apply-before-concentration warning,
post-admission birth boundary, stable active-turn identity and safe deferred
encounter membership cleanup. Its public acceptance matrix is sufficient to
challenge those implementation risks without freezing private helper signatures.
The single-body default and limited form table are clearly disclosed proposals;
the excluded undead, full roster, artwork, rendering and server work have not
returned through the cleanup or testing requirements.

Documentation-only review. No production edits, tests or test runs.

## Final integration re-review — 2026-10-03

Exact final plan SHA256:
`aa1bb2068c4380004b4886b59ee10cf33b69c300ef94aa058721452da056c60a`.
The hash was verified before and after reading the revised binding contract and
remaining lifecycle/acceptance sections.

**Verdict: APPROVED. No remaining anti-slop blocker for this exact revision.**
The prior resolutions remain intact. This approval supersedes the previous
hash-bound approval for the final document; gameplay proposals still require
the human's approval and no implementation has been authorized by this audit.

The discovery correction is concrete and uses the existing validation boundary:
the dedicated unpublished summon-admission proposal goes through
`EventQueue.preflight` from both discovery and actual pre-cost validation.
I checked that the native preflight owner requires unregistered proposals and
validation-only matching handlers and rejects emitted events
(`dnd/core/events.py:1934`). Keeping this a narrowly typed pure query avoids
running ordinary spell reaction handlers or creating provisional actors during
discovery. Execution still revalidates the exact binding; no admission cache,
service lookup or second message bus is introduced.

Encounter end now relies on the actual native controller lifecycle. I checked
that `Encounter.end` notifies controllers before directly constructing its
COMPLETION fact (`dnd/encounter.py:503`), and that notifications call
`controller.on_encounter_end` (`dnd/encounter.py:1051`). The plan correctly avoids
expecting a phase-transition pre-completion callback there. Explicit rebind and
close release old references while preserving surviving leases; no duplicate
expiry or new encounter-end mechanics are added.

The revised header appropriately separates the proposed plan from review receipts
and implementation authorization. Content, ownership boundaries, item scope,
clock, resource semantics and excluded work remain as approved above.

Documentation-only re-review. No production edits, tests or test runs.

## Creature independence clarification — 2026-10-03

Exact clarified plan SHA256:
`18f468caa0dd424537e4836b18b1176653b886869729c60c684a54d21c0886ac`.

**Verdict: APPROVED. No anti-slop blocker in this clarification.** This focused
re-review covers the added user invariant, the two creature-ownership paragraphs
in section 2 and the matching acceptance row. It does not reopen the previously
approved architecture or expand implementation scope.

The clarification correctly keeps one canonical recipe for ordinary and summoned
instances. The creature constructor needs no summoner or lease; stats, abilities,
gear and ordinary action execution are defined once. The summoning relationship
owns the selected instance's lifetime, allegiance, initiative admission and
departure policy. Explicit FEY adaptation is confined to the incoming instance
before birth and cannot mutate the recipe or another creature. There is no new
summoned statblock, species executor or constructor branch.

The intrinsic-only restriction remains local to this bounded summoning adapter,
so it cannot strip or prohibit ordinary creature gear. The new public acceptance
row directly tests construction independence and unchanged ordinary death/items
alongside instance-local adaptation; it does not test private class layout.
Rendering identity is preserved as content data without authorizing rendering
work. Prior scope exclusions and the separate human implementation-approval gate
remain in force.

Documentation-only clarification review. No production edits, tests or test runs.

## Concrete implementation design re-review — 2026-10-03

Exact reviewed plan SHA256:
`ad8fc389b313c205de78ca1064a71ee41810e6a8a7a737432fa1b97a3d86bce1`.

**Verdict: CHANGES REQUIRED.** The direct condition design and Fey control
exception are sound. Two bounded placement corrections are needed before this
revision is approved; neither calls for additional geometry or visibility work.
Earlier approvals do not cover this substantially revised document.

### AS5 — Preserve native creature occupancy rather than imply new footprints

Section 2 promises a "full footprint" check, creation step 4 prepares an
"entire world footprint," and the matrix repeats footprint acceptance. Native
creature membership is one coordinate/Tile per Entity:
`GridMap._commit_entity_membership` replaces one old Tile membership with one new
Tile membership (`dnd/core/gridmap.py:2207–2284`). Its multi-cell footprint APIs
are for world objects and spatial conditions. Dire Wolf is Size.LARGE
(`dnd/monsters/srd_roster.py:980`) but still uses ordinary Entity membership.

**Required correction:** explicitly retain the existing one-anchor-tile creature
occupancy and native support/access/occupant rules for both ordinary and summoned
creatures. Replace the ambiguous full-footprint promises and acceptance wording.
Multi-cell creature placement/movement is deferred. Do not introduce it only for
summoned Dire Wolves or copy world-object footprint rules into this feature.

### AS6 — Preserve subjectivity in pure placement discovery

Section 6 reuses one summon-admission preflight for discovery and actual pre-cost
validation, but its proposal/helper has no stated subjective/objective mode.
The native placement contract deliberately distinguishes them:
`BaseAction.validate_requirements_for_discovery` passes its `subjective` flag to
`position_placement_error` (`dnd/core/base_actions.py:1966–1990`), and
`Entity.can_end_movement_at` explicitly retains a candidate hidden-occupied cell
during discovery (`dnd/entity.py:1505–1530`). An authoritative Game occupancy
check shared unconditionally with discovery would reveal that unseen blocker by
removing the candidate from the menu.

**Required correction:** carry the existing discovery subjectivity through the
shared helper/typed preflight proposal. Discovery checks only caster-known
occupancy/support/access; real execution checks objective native placement.
Failed execution reports the ordinary placement outcome without disclosing a
hidden entity identity. Add the one observable case in which an undisclosed
occupant does not alter discovery but prevents real overlapping placement.
Reuse the native observation/placement rules, not a summon-specific knowledge
policy.

### Verified improvements retained

- Animals/fiends link Concentrating directly to the finite Summoned condition;
  native nonconcentration creation applies that same condition directly. There
  is no uniform duplicate control condition.
- Fey alone uses the untimed control child. Control loss preserves the same
  Entity, AI, resources and one remaining Duration. Existence removal suppresses
  a transient hostility change; original control membership gates dismissal.
- A unique nonempty hostile faction uses existing faction comparison and avoids
  confusing hostility with unknown observation data. The ordinary faction-change
  fact updates shared retained actor/AI state; no new tactical policy is proposed.
- The creature-owned clock, birth-interval skip and encounter rejoin behavior are
  explicit. The 600-interval duration and one-action dismissal are clearly pending
  gameplay defaults, not presented as previously authorized decisions.
- Prepared initial condition/concentration/world/join owners now identify the
  real publication gap. Resource commitment remains separate and ordinary
  wrappers preserve current behavior. No generic rule engine or retry cache is
  introduced.
- Intrinsic-only admission, real-item preservation, canonical creature
  independence, deferred art/roster/undead/server work and documentation-only
  authorization remain intact.

This pass inspected the complete revised plan and the concrete placement owners;
it did not reopen unrelated code or request new infrastructure. No production
edits, tests or test runs. Re-review the corrected exact hash after AS5–AS6.

## Concrete design re-review — 2026-10-03

Exact revised plan SHA256:
`f25f04b5d80357bad5417743ac73afc248880550320ce84527e275e39c06feed`.

**Verdict: APPROVED. No remaining anti-slop blocker for this exact revision.**
This replaces the changes-required verdict for `ad8fc389…6bce1`; it does not
authorize implementation or claim unimplemented behavior has passed tests.

AS5 is resolved explicitly in section 2, the creation sequence and selection
acceptance cases. Both ordinary and summoned creatures retain the native
one-anchor-tile model, including Large Dire Wolf. Multi-cell creature geometry
and movement are expressly deferred; no world-object footprint machinery is
repurposed for summoned actors.

AS6 is resolved in the placement contract and typed admission proposal. Discovery
carries the native subjective mode and preserves a candidate occupied only by an
unseen creature. Actual pre-cost and final admission use objective placement,
without disclosing the hidden occupant's identity. The required public case
tests that distinction directly. No second visibility policy is introduced.

I read the complete revised design, including the additional staged-birth,
condition-owner and removal-scope corrections. They retain concrete native
ownership:

- Prepared condition data belongs to BaseBlock/BaseCondition; Concentrating
  owns its slot transfer, and Entity commits its own initial composition. The
  high system coordinates accepted owner tokens without copying their rules.
- PreparedBirth separates the existing creation flag from publication while
  ordinary compose_entity remains the wrapper. Specific accepted facts and
  after-values replace the previously ambiguous publication ordering; there is
  no arbitrary event buffer or second birth event.
- The outer removal scope records exact committed condition results and settles
  them after parent links/publications, rather than recursively destroying an
  actor from a child's completion handler. It is bounded to the existing graph
  operations and consumes consequences once; it does not add a general deferred
  work scheduler.
- Required involuntary sustain loss is an explicit lower-owned policy for
  Summoned and the Fey control child. Voluntary removal and unrelated effects
  retain their existing semantics. Fey still keeps its independent Duration and
  identity after control loss; Animals/Fiend still use the direct dependency.

The content table, intrinsic-only summon admission, real acquired-item
preservation, single creature-owned clock, native AI, independent ordinary
creatures and deferred rendering/roster/undead/server scope remain intact. The
public acceptance matrix covers the new owner boundaries without requiring
private call-order tests. The proposed gameplay defaults remain clearly subject
to the human's implementation approval.

Documentation-only design review. No production edits, tests or test runs.

## Bounded creature-batch expansion review — 2026-10-03

Exact reviewed pair:

- Main plan SHA256:
  `e2b10dacbeb9e69d60822af251e66db89a361c1342ddb9c7ede15bdf6ad3a094`.
- Companion `SUMMONING_CREATURE_BATCH_2026-10-03.md` SHA256:
  `ccdddc29658280d92bc93c7d01309cff1dde87f97bf7f3e3995d9135f7894888`.

**Verdict: APPROVED. No anti-slop blocker for this exact paired revision.**
This approves the proposed bounded expansion for human consideration, not its
implementation or the readiness of unbuilt creature/art bindings. Earlier
lifecycle approvals alone did not cover this content and presentation work.

The batch answers the user's requested one-to-two-dozen scale with 24 actual
canonical recipes: 18 beasts/dinosaurs and six fiends. Four existing recipes are
reused and 20 are new. Fey selections reuse the 18 canonical beast bodies and
do not increase that count. Slot counts agree with the table; higher slots retain
lower choices without copying or scaling their stats. All selected recipes must
work as ordinary creatures independently of summoning. The forms table stores
references and admission parameters, not another creature constructor or stat
catalogue. Existing Wolf/Dretch/demon-variant identities remain authoritative.

The selected gameplay remains feasible through existing shared owners:

- `dnd/monsters/multiattack_definitions.py` already expresses repeated and mixed
  weapon-slot sequences; the selected bear, tail and fiend sequences need content
  definitions, not a second attack executor or new target policy.
- `HitSaveRiderFeature` and ordinary Prone own the selected save riders. Its
  present weapon-name matching is an identified shared-owner correction, not a
  license for 17 species-specific event processors. Both advertised action
  profiles and execution must use the selected attack's real identity.
- `dnd/blocks/sensory.py` already evaluates `SensesType.DEVILS_SIGHT` through
  magical darkness; `MagicResistance` and `InnateFlight` are existing trait
  owners. The chosen C04/C05/C27 study rows do not pull in the other authored
  devils' reactions, grappling, spellcasting or legendary-action proposals.
- Charge/Pounce chains, Relentless, split-target Tyrannosaurus Multiattack,
  holding/grappling, unsupported movement modes and multi-cell creature geometry
  are explicitly excluded or adapted. These are openly proposed game rules,
  not claims of source-exact SRD implementation.

The presentation expansion is bounded to existing art and shared data. The
source studies identify literal variants and inspected primary clips while
explicitly withholding claims about production timing or every secondary
attack. The batch carries that distinction forward and requires all ordinary
action mappings to be resolved before accepting each unit. Paired with-shadow
and shadowless sheets are not claimed to be independent shadow layers; the
per-rig shadow policy remains an authored binding obligation. Existing
`game/condition_animation.py` body-ramp/alpha composition and
`game/animation_draw.py` cached body-ramp drawing provide a shared owner for the
Fey material. No duplicated blue sprite export or summon-specific renderer is
proposed.

Completion still requires every selected ordinary and summoned recipe, exact
family/slot boundaries, unchanged canonical recipes after Fey creation, native
AI/actions/items, all rig/action bindings and representative in-engine review.
That work is explicitly outstanding; available source artwork and this review
are not presented as evidence that it already passed. Special summon VFX,
remaining roster conversion, armed fiends, undead and server work stay outside
the approved plan scope. The previously reviewed lifecycle owners and cleanup
requirements remain in force.

Documentation/source review only. Read the referenced source studies and the
existing composition, attack, sense, trait and presentation seams; no production
edits, tests or test runs.

## Anatomical-attack prerequisite re-review — 2026-10-03

Exact reviewed pair:

- Main plan SHA256:
  `d32f941cbca1329356b047cf3600ce112a694f89660fcb875f553b93800e0bff`.
- Companion SHA256:
  `d901ac3bade5f823db72561c442b8154fa4847996a7959e92eecd121dbed220c`.

**Verdict: APPROVED. No anti-slop blocker remains in this bounded correction.**

The prerequisite is real. `Weapon.compatible_equipment_slots` currently gates
the secondary melee slot on LIGHT; `Attack.adjust_cost_for_off_hand` supplies a
bonus-action default; both `Equipment.get_weapon_damage_profiles` and the live
base-damage path select off-hand ability contributions by slot. The existing
Dretch description even records the incidental bonus attack. My previous
statement that these mixed anatomical sequences needed only content definitions
was incomplete: the existing sequence executor is reusable, but its slot-selected
children require this explicit shared weapon-policy correction.

The new design addresses those exact owners with one passive held/body usage
value. Intrinsic ownership validates body usage; names, sprites and summoning
state do not infer it. Template composition supplies ordinary action costs while
preserving explicit Multiattack/reaction costs. The same usage query governs
runtime damage, AI/outcome profiles and natural physical access. This avoids a
second resolver, special per-creature attack classes, copied damage formulas or
an additional action budget. Main-position threat/opportunity selection stays
explicit, and the roster needs no more than two distinct attack positions.

The behavioral correction to the selected existing wolf/dretch anatomy is now
declared rather than hidden under an assertion that every current behavior is
unchanged. Their content identity, statistics, dice and intended kit are reused;
ordinary held weapons and unrelated definitions retain their defaults. Native
and AI damage agreement, full body modifiers in either position, absent accidental
bonus-action entitlement, explicit parent-owned Multiattack costs and unchanged
held-weapon behavior are required acceptance cases. Existing content independence,
24-creature scope and lifecycle requirements remain intact.

Reviewed the bounded delta and its equipment/template/access source owners.
Documentation only; no production edits, tests or test runs.

## Unified end-to-end plan review — 2026-10-03

Exact single-document SHA256:
`a633f48b625c7bf091492faca60cd5606003683326f3f77430cbadd324eaa9cf`.

**Verdict: APPROVED. No anti-slop blocker for this exact unified revision.**
This verdict applies to the sole implementation plan, not the superseded
creature-batch pointer or an inferred combination of older receipts.

Compared the consolidated text with both saved pre-consolidation documents and
read the complete new delivery and arena contracts. The accepted creature table,
slot tiers, explicit adaptations, body-weapon correction, condition graph,
admission/publication boundaries, one clock, Fey control loss, exact item/actor
retirement and native AI ownership remain present. Material moved out of the
former companion now has owners and acceptance requirements in this document;
the linked source studies supply evidence and numerical baselines rather than
additional work queues. No accepted behavior was lost in consolidation.

The delivery order is concrete: ordinary body-attack semantics precede canonical
content; passive/native lifecycle owners precede the high binding and spell
adapters; retained facts and all existing-art bindings precede complete fight
acceptance. Fact fields/reducers may be added alongside their producer rather
than postponed until presentation. One ledger covers all 24 recipes and their
actions/bindings, while representative bodies can cover shared lifecycle
permutations. This avoids both a wolf-only completion claim and needlessly
duplicating every lifecycle test for every species.

The presentation contract remains bounded to the exact existing pack variants,
all required ordinary actions, reviewed motion reuse and one shared Fey material.
Manifestation survives through retained birth/codec/subjective facts; drawing does
not query a live caster, controller or condition. Control loss changes allegiance
without replacing the creature or its material. No new summon VFX or renderer
framework has entered the scope.

The added mini-dungeon is fixture authoring through existing owners. Source
inspection confirms `BattlefieldDefinition` already accepts positive width/height,
`GridMap.create_rectangle` constructs authored dimensions, and the existing
battlefield builders/encounter assembler compose walls, doors and one native
encounter. The 64x64 and 128x128 targets therefore require authored geometry and
scenario data, not a new arena engine. The plan keeps native one-anchor creature
occupancy and prevents room/view changes from recreating actors or resetting
lifetime, initiative or budgets.

Arena acceptance separates map growth from actor-count growth, rotates all 24
creatures through real recorded fights, and records route/decision timing and
live ownership counts without claiming an unmeasured performance guarantee.
Four-camera presentation and real floor tiles remain required. Campaign
generation, progression, multi-Z, multi-cell creature geometry, special arena AI
and an open-ended optimization project remain excluded.

Planning/source comparison only. No production edits, tests or test runs.

## Final scope-withdrawal re-review — 2026-10-03

Exact single-document SHA256:
`001c6bed12ad477b1b386bd985e6cb5f8293f6d644de9be8908121b61575e815`.

**Verdict: APPROVED. No remaining anti-slop blocker for this revision.**

The user explicitly withdrew the arena request as belonging to another thread.
The current plan removes the arena subsection, 64x64/128x128 targets, connected
mini-dungeon authoring and expanded map-scale acceptance. The preceding
`a633f48b…aa9cf` review is historical and does not retain any arena obligation.

Representative recorded native fights, distinct body families, large-creature
and Fey presentation checks, and validation of all 24 rigs and primary/secondary
actions remain in sections 10–11. This preserves the original content and
presentation acceptance without carrying the withdrawn fixture work forward.
The unified dependency order, creature/adaptation/body-attack contracts and
native lifecycle/item/event/AI ownership remain unchanged. The superseded
companion remains a pointer; this single document is the implementation authority.

Reviewed the withdrawal delta and verified the exact hash. Documentation only;
no production edits, tests or test runs.

## Alternate-rig design and visual-gap addendum review — 2026-10-03

Exact reviewed documents:

- Sole implementation plan SHA256:
  `001ec7cedbd75d639daf9d43063d865c34605b3ce441a391686479b5646daac9`.
- `SUMMONING_VISUALS_ADDENDUM_2026-10-03.md` SHA256:
  `fadcebe641f88e0f43a487e07f272f75a9ce4b0c63ad1764074b8b8f4069a34d`.

**Verdict: APPROVED. No anti-slop blocker for this exact revision and addendum.**

Compared the main-plan delta with the saved pre-addendum document and inspected
the existing rig/profile, body-action, condition and movement owners. The changes
address actual gaps. `AnimationData.creature_rigs/rigs` and `_additional_rigs`
already provide the registry. `AttackProfileMatch` lacks a rig constraint, and
`bind_attack` currently selects a profile before resolving the retained source
rig. `BodyClip` aliases resolve sheets and clocks; they do not replace the
profile's contact frame, outcome choice or effect tracks. Movement and condition
paths likewise select global clips, including jump/connector choices and the
Prone Die/reverse-Die sequence.

The design extends those owners without creating another renderer. Optional rig
IDs refine the existing attack-profile selector; exact retained attack/item
facts still select the action. The non-attack table belongs to BodyRig, uses
finite context roles and registered references, and supplies passive body/anchor
data to one pure binding helper. Existing samplers, causal choreography, effects,
trajectory and feedback keep their responsibilities. Attack selection remains
outside that table. No new registry, runner, event subscriber, callbacks or
creature-name dispatch is proposed. Compatible defaults and unchanged modular
behavior remain available, with ambiguity and required missing mappings rejected.

The addendum accurately separates four installed fixed rigs from twenty pending
bindings. I checked their recorded aliases and the existing Prone/Frightened
recipe data. Source inventories and inspected primary strips are described as
evidence, not calibrated action coverage. The 24-row action ledger calls out
secondary attacks, actual contact timing, miss/critical/OA/Multiattack selection,
flight and living Prone poses. It does not claim that a Roll alias, a human
off-hand profile or an exploding death strip solves those cases. Unresolved
required body motion stays an incomplete integration row, not optional VFX.

The later VFX list is bounded and does not authorize production. Arrival and
departure consume the existing typed lifecycle facts; halo/control-break accents
are optional; shared Fey palette/alpha remains current integration. Existing
fear, residue, damage and passive mechanics do not become duplicate per-species
effect projects. Hidden events, reacquisition, playback seeking and silent reset
retain their observation/lifecycle rules. Claims concern absent selected
production bindings, not an unsupported assertion that original artwork cannot
exist elsewhere.

The addendum is a linked evidence/acceptance ledger under the sole main plan,
not a second implementation sequence. Only the human may deliver a later brief
to the VFX thread. New artwork, external delivery and the withdrawn arena work
remain unauthorized. The new binding validation belongs to packet 5 and retains
the ordinary/summoned equivalence and Fey-material-only distinction.

Documentation/source review only. No production edits, tests, test runs, new
source-strip visual acceptance or communication with other chats.

## Exact motion/phase binding re-review — 2026-10-03

Exact reviewed documents:

- Main plan SHA256:
  `d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`.
- Visual addendum SHA256:
  `28dbdf5dec4fcc45afe6a5434ca297ec22da58715a0f044dcd37b9ca18011075`.

**Verdict: APPROVED. No anti-slop blocker for this bounded revision.**

The refined selector is both concrete and restrained. `MovementFact` really
contains trajectory, movement mode and connector presentation key, with no
action behavior reference. Matching that whole signature, or one exact content
reference, followed by at most one role-default avoids a wildcard/precedence
rule engine. Duplicate keys and unavailable required fact fields cannot be
resolved by row order, guessed names or native object lookup.

The phase correction covers the actual consumers. `bind_shove` uses ShoveFact
outside body_action; forced movement has a brace frame and currently rereads a
global recovery during sampling; body actions also separately time and sample
recovery. The revised contract resolves and retains each required primary and
recovery binding on existing cues and covers markers, reversal and held poses.
It therefore changes both timing and sampling through the same accepted data,
not merely the final sprite lookup. Native motion, feedback and child joins
remain with their current owners. Disabled neutral gestures retain an ordinary
action cue and its child/effect joins instead of returning None to hide it.

The source-kind clarification matches
`Equipment.snapshot_attack_source_metadata`: intrinsic item-backed attacks
currently record equipped plus their exact item identity. NATURAL physical
access does not require rewriting that discriminator or introducing a second
attack representation. The existing separate NaturalAttack route is not
repurposed to satisfy presentation matching.

These additions close specific shared binding gaps without new registries,
samplers, runners, timelines with separate ownership, artwork authorization or
per-creature dispatch. The main plan remains authoritative; the addendum remains
the linked evidence/acceptance ledger and later human-delivered VFX list.

Documentation/source review only. No production edits, tests or test runs, and
no communication with other chats.
