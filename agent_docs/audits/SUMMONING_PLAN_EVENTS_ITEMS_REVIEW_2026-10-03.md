# Summoning plan — events and items review

Date: 2026-10-03. Scope: independent source and plan review only.

Reviewed plan: `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`

SHA256: `ea1b68c459dad4a66336befb7dd4cd939e2d962288ef9f4256b415a6a90b1758`

**Verdict: changes requested.** One bounded lifecycle ambiguity must be resolved
before this exact plan is approved. No production files changed and no tests ran.

## Blocking finding

**EI-1 — Make all mandatory departures use the non-vetoable terminal mode.**

Section 8 explicitly makes natural expiry, source death and game teardown
non-vetoable, but does not include defeat at zero HP or involuntary concentration
loss. The same section otherwise requires admitting every condition/item removal
and real-item landing before lease removal. An item or condition removal veto
could therefore preserve an authoritative defeated or unsustained summon unless
the plan says which rule wins.

This is an existing owner contract, not a hypothetical event framework concern:
`BaseBlock._remove_condition_tree` (`dnd/core/base_block.py:985`) returns false on
any rejected node; `BaseItem.retire` (`dnd/blocks/base_item.py:711`) returns early
on rejected floor removal and presently ignores individual condition-removal
failure. Calling those operations does not itself guarantee terminal cleanup.

Required correction: explicitly include zero-HP defeat and involuntary
concentration loss in the mandatory terminal mode. Carry that mode through the
same narrowly extended condition/item/real-item-placement owners so one child
cannot retain the expired actor or its conjured equipment. Preserve the admitted
no-op behavior for voluntary dismissal/replacement and ordinary effects. Add the
observable case that a removal veto cannot preserve a defeated or involuntarily
unsustained summon, while real possessions survive and unrelated conditions
retain their normal cancellation semantics.

## Contracts correctly retained by the draft

- **One birth and one presence owner.** `Entity.compose_entity`
  (`dnd/entity.py:1276`) publishes the finished `EntityCreatedEvent`; the draft
  keeps initial possessions inside that fact. `GridMap._publish_entity_membership`
  (`dnd/core/gridmap.py:2287`) already supports causal parent IDs, so the proposed
  forwarding through Game/Entity does not require a second creation journal.
- **Provisional state stays unpublished.** The draft explicitly accounts for
  incoming condition application preceding required concentration admission and
  delays birth/deployment until the accepted membership boundary. It preserves
  committed publication errors rather than claiming visible mutations rolled back.
- **Terminal removal differs from detachment.** `Game.remove_entity`
  (`dnd/game.py:33`) retains an entity for later redeployment. The wolf anatomy
  regression at `tests/engine/test_gear_ownership_regressions.py:77` depends on
  that behavior. Terminal retirement must not repurpose this existing API or
  misuse `discard_uncommitted` on a published actor.
- **Temporal ownership survives transfer.** Inventory insertion stamps
  `source_entity_uuid` to the current holder (`dnd/blocks/inventory.py:133`). The
  immutable lease reference and original temporal-item IDs avoid treating this
  mutable field as origin. Cross-lifetime merging is forbidden; real later
  possessions preserve their UUID, coating, charges and data.
- **Expiry uses retirement, not breakage.** `BaseItem.destroy` triggers physical
  destruction/remnants; `retire` owns terminal disappearance. The draft names
  the existing admission shortfall, preserves anatomy through
  `intrinsic_owner_uuid`, and excludes unsupported temporary storage instead of
  silently destroying real contents.
- **Subjective disclosure stays authoritative.** Existing spatial projection
  (`game/player_projection.py:443`) requires event-time identity and coordinate
  permissions. The draft distinguishes true departure from contact loss, retains
  pre-removal witnessing, and requires passive typed cause/provenance without
  revealing undisclosed caster/form/loot information.
- **Exact teardown and history.** Conditions retain their graph ownership and
  child-first removal. The draft preserves independent consequences on other
  actors, ends only the exact sustainer, closes native AI/subscriptions, and
  requires archive replay without rebuilding actors or rerunning mechanics.

## Implementation acceptance boundary

Approval after EI-1 is corrected will concern this plan only. Implementation
review must inspect the actual typed membership/item cause fields and their
subjective projection, confirm exact cleanup ownership, and verify the public
behavior matrix. No visual implementation, undocumented global forced-removal
policy or new universal lifecycle/event bus is approved by this review.

## Re-review — revised plan approved

Reviewed 2026-10-03 against the complete revised plan, SHA256:

`91d5eceab68ded40dc287bdcd4425cd79ecfeed76853bce1d84cbdd2f87a435c`

**Verdict: approved for this exact plan. No remaining events/items blocker.**
This supersedes the initial changes-requested verdict for the older hash only;
the initial finding remains above as the review history. This is plan approval,
not implementation authorization or implementation acceptance.

**EI-1 resolved.** Section 8 now explicitly covers expired, defeated, source
died, involuntary concentration loss and game closed as mandatory terminal
causes. The exact live lease and committed causal event authorize release through
the existing owners; no universal force flag or global cancellation override is
introduced. Real possessions land through committed ordinary nonblocking item
placement. A corrupt/missing last supported tile preserves registered item
identity and produces a hard invariant failure instead of item destruction.
Voluntary dismissal/replacement remains admitted before mutation. The acceptance
matrix includes vetoing listeners against mandatory causes and the contrasting
voluntary rejection behavior.

The narrowed item scope is supported by the actual content:

- `dnd/monsters/srd_roster.py:1291` and `:1301` give Wolf and Dire Wolf only
  intrinsic natural armor and bite; `:1333` gives Dretch only intrinsic natural
  armor, bite and claws.
- `dnd/monsters/demon_variants.py:27` composes the two selected demon variants
  from Dretch and installs a body-response profile, without adding possessions.
- Fey rows reuse the wolf compositions. The plan rejects any future ordinary
  default equipment/inventory at form admission and defensively before birth.
  It therefore does not claim to solve transferred conjured gear without lifetime
  provenance. That later policy is retained explicitly, while real acquired
  weapons, coatings, bags and contents remain required to survive departure.

The revised creation contract preserves ordinary BaseAction cost timing:
pre-cost invalid input spends nothing; later effect/admission rejection retains
paid costs while preserving the old summon and concentration. Birth still waits
for accepted condition/concentration membership and remains one canonical fact.
Duplicate delivery of the same operation does not become a second birth;
independently issued casts retain their ordinary cost and identity.

The explicit binder and close/reset paths also agree with existing event owners.
`PreCompletionSystem` is the dependency-neutral lifecycle protocol at
`dnd/core/events.py:128`; EventQueue reset invokes system reset only after the
event archive/handler tables have been cleared (`:2646`). The plan correctly
separates silent reset from causal Game.close departure. Actual death/encounter
lifecycle work justifies the indexed pre-completion registration, and safe
encounter unwinding remains outside that event callback.

The one-birth, causal-presence, event-time disclosure, reversible-detachment,
exact condition ownership and passive archive requirements remain intact.
No production or test files were edited; no tests were run during either review.

## Final re-review — admission and encounter-end correction

Reviewed 2026-10-03 against the final revised plan, SHA256:

`aa1bb2068c4380004b4886b59ee10cf33b69c300ef94aa058721452da056c60a`

**Verdict: approved for this exact plan. No remaining events/items blocker.**
Prior findings and verdicts above remain historical receipts for their respective
hashes. This verdict is independent plan review, not implementation permission.

The explicit discovery/pre-cost helper now uses the existing pure
`EventQueue.preflight` contract (`dnd/core/events.py:1935`) with a dedicated
unpublished typed proposal. Matching handlers must be validation-only; the
proposal carries passive admission identity and does not publish facts, mutate
resources, reserve a lease or construct a creature. Revalidation at mechanical
execution preserves the actual cast boundary. This makes the binder reachable
from discovery without adding another event store or exposing executable runtime
references in recorded facts.

The encounter-end correction matches the native source:
`Encounter.end_encounter` (`dnd/encounter.py:476`) calls controller notifications
before constructing its direct COMPLETION event; it does not run the phased
pre-completion lifecycle path. `NativeAIController.on_encounter_end`
(`dnd/ai/runtime/controller.py:109`) already closes assignment ownership. The
plan now uses that real owner and reserves indexed pre-completion registration
for phase-transition death facts. This explicitly corrects the preceding
re-review's overly broad reference to death/encounter pre-completion work.
Rebind and normal close/reset idempotently release retained controller/encounter
references while encounter end alone preserves the existing summon and lease.

EI-1 remains resolved. Mandatory and voluntary release contracts, preservation
of acquired real items, intrinsic-only form admission, one canonical birth,
causal departure, subjective witnessing and passive replay remain unchanged and
approved. No production/test files changed and no tests ran in this re-review.

## Focused clarification review — independent creature definitions

Reviewed 2026-10-03 against plan SHA256:

`18f468caa0dd424537e4836b18b1176653b886869729c60c684a54d21c0886ac`

**Verdict: approved for this exact plan. No events/items blocker introduced.**
This review covers the declared creature-independence clarification in sections
1–2 and its acceptance row; unchanged lifecycle/event/item requirements retain
the preceding full review's approval.

The clarification correctly keeps canonical body, stats, actions and possessions
constructible without summoner, spell or lease data. Summoning relationships and
departure policy belong only to the resulting instance. Fey adaptation is applied
before that instance's one birth fact and cannot mutate the recipe or other
actors. This preserves recorded source identity while carrying explicit
manifestation semantics separately.

Ordinary creatures retain their existing death and possession behavior; the
intrinsic-only restriction applies only to admission through this summoning
adapter. The added public acceptance cases make that separation observable,
including ordinary equipped recipes and a second unaffected instance. No
duplicate creature state, event owner or item-lifetime mechanism is introduced.

Plan review only. No production/test files changed and no tests ran.

## Concrete implementation design review — independent existence/control

Reviewed 2026-10-03 against plan SHA256:

`ad8fc389b313c205de78ca1064a71ee41810e6a8a7a737432fa1b97a3d86bce1`

**Verdict: changes requested.** This revision replaces the earlier reviewed
lifecycle design. One concrete birth API/order gap remains; prior hash approvals
do not approve these bytes.

### EI-2 — Stage birth explicitly before committing world presence

Section 6, creation step 6, commits aggregate/world/encounter state; step 7 then
publishes the birth. The proposed surface still exposes only
`entity.compose_entity(...) -> EntityCreatedEvent` for this birth boundary.
That cannot implement the stated sequence with its existing guards:

- `Entity._attach_to_world` (`dnd/entity.py:678`) requires
  `creation_committed` before deployment.
- `Entity.validate_initial_composition` (`:1208`) rejects committed or deployed
  entities.
- `Entity.compose_entity` (`:1276`) also rejects both, and couples setting
  `creation_committed` with immediate completed-fact publication.

The proposed catch-all exception correction is necessary but does not resolve
this ordering conflict. Calling compose before authority commit exposes a birth
too early; calling it afterward hits the existing guards.

Required bounded change to the plan: explicitly split this existing birth owner
into preparation of the complete unregistered birth value while undeployed,
commit of `creation_committed` with the rest of authoritative state, and
publication of that exact prepared value after deployment/join commitment.
`compose_entity` remains the ordinary prepare/commit/publish wrapper. Name these
seams or put the prepared birth inside the already proposed native prepared
aggregate operation. Do not recapture mutable actor state after publication
callbacks, create a second birth, or introduce a generic event buffer.

### Revised contracts accepted

- Animals/Fiend use the direct Concentrating -> Summoned relationship;
  nonconcentration uses Summoned alone. Only Fey adds an untimed control child.
  The finite Duration belongs only to Summoned and survives Fey control loss.
- The graph suppresses hostility when control is removed as part of terminal
  existence teardown. Independent accepted control removal changes allegiance
  and revokes dismissal authority while preserving the same actor, possessions,
  native AI assignment, turn budget and remaining duration.
- A normal faction mutation fact fills an actual source gap. The shared actor
  reducer and recorded AI knowledge currently learn faction at birth only;
  explicit post-commit faction after-values avoid live-state/replay disagreement.
  A nonempty independent faction avoids `None`'s redacted/unknown ambiguity, and
  its broader hostility under equality-only factions is explicitly disclosed.
- Concentration preparation names the real current defects: incoming condition
  application precedes required concentration admission, and linking currently
  follows condition completion. The revised design requires shared preparation,
  exact link commit and deferred completion publication rather than sequential
  public calls or a second transaction framework.
- Item retirement now has explicit acceptance/rejection and causal container
  release. Real gear runs normal unequip cleanup and survives on the ground;
  anatomy retires under its exact owner. Future transferable conjured equipment
  remains unsupported and ordinary creature possessions remain unaffected.
- Mandatory terminal release, event-time witnessing, one actual departure,
  hidden-observer reacquisition and passive finite archive decoding retain the
  required boundaries. A faction change is not a birth, departure or timer reset.

The unchanged implementation acceptance requirements remain: exercise native
casts/actions and committed output, prove no orphan completed facts on rejection,
and verify exact live registration cleanup and committed publication errors.
This was documentation/source review only; no production/test files changed and
no tests ran.

## Re-review — prepared birth and settled native removal

Reviewed 2026-10-03 against the complete revised plan, SHA256:

`f25f04b5d80357bad5417743ac73afc248880550320ce84527e275e39c06feed`

**Verdict: approved for this exact plan. No remaining events/items blocker.**
This supersedes the changes-requested verdict for `ad8fc389...` above. It is
approval of the proposed design, not implementation authorization or evidence
that the planned behavior already exists.

**EI-2 resolved.** The plan now defines Entity-owned `prepare_birth`,
`commit_birth` and `publish_birth`. Preparation validates the undeployed,
uncommitted aggregate and captures one complete unregistered birth fact;
commitment sets the creation flag before world/encounter membership commits;
publication then stores that exact staged fact once. The ordinary
`compose_entity` path remains the prepare/commit/publish wrapper. Initial
condition after-values are included, and committed publication errors cannot
silently discard the born actor.

The related native owner changes are explicit enough to implement and review:

- Prepared condition/concentration records remain with the lower owners.
  Conditions, concentration, deployment and encounter join separate their
  admitted state commit from publication for this bounded operation. The high
  owner does not acquire another implementation of condition or slot mechanics.
- Settled removal is after the complete outer operation, including incoming
  condition publication, slot deletion/synchronization and parent after-values.
  Per-child completion cannot recursively retire its still-committing owner.
  Exact committed consequences are consumed before dispatch; the active scope
  is cleared first; publication errors still settle committed cleanup.
- Typed involuntary sustain loss enters before a veto can retain required
  summon/control authority. Exact Summoned or Fey control branches release
  independently of unrelated voluntary vetoes. Animals/Fiend retire; Fey keeps
  the same existence condition, actor, AI and remaining Duration and becomes
  hostile only after control removal settles.
- Subjective discovery checks known placement; objective execution checks the
  real tile without disclosing a hidden occupant. The selected Large creature
  uses the existing native one-anchor placement rules, avoiding an unrelated
  multi-cell creature geometry change.

The direct concentration graph and Fey-only extra control condition, one finite
clock, causal item release with explicit outcomes, ordinary faction after-value
fact, one birth/actual departure, event-time disclosure and passive archive
contracts remain approved. Historical identity survives while live authority
and intrinsic registrations are removed; real acquired possessions survive.

Implementation acceptance must still exercise the documented native behavior
matrix, including exact staged birth, rejected admission, outer-scope cleanup,
forced sustain loss, hidden-observer reacquisition and committed publication
failure. No production/test files changed and no tests ran in this review.

## Paired re-review — 24 canonical creatures and existing-art assignments

Reviewed 2026-10-03 against this exact pair:

- `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`, SHA256
  `e2b10dacbeb9e69d60822af251e66db89a361c1342ddb9c7ede15bdf6ad3a094`
- `agent_docs/SUMMONING_CREATURE_BATCH_2026-10-03.md`, SHA256
  `ccdddc29658280d92bc93c7d01309cff1dde87f97bf7f3e3995d9135f7894888`

**Verdict: approved for this exact pair. No events/items blocker.** This
approves the expanded proposed design, not an implementation or its validation.
The earlier EI-1 and EI-2 resolutions remain applicable.

The expanded content preserves the lifecycle boundary:

- The 18 beasts and six fiends are ordinary canonical recipes. Fey reuses the
  beast recipes with instance-local type and manifestation; neither that material
  nor a higher slot duplicates a creature identity or changes another instance.
  The cumulative slot counts match the 24-row table.
- The selected bodies have intrinsic default attacks/defenses. The three new
  fiend profiles C04/C05/C27 explicitly carry no ordinary default gear; the
  existing Wolf, Dretch and two demon variants retain their existing identities.
  Natural attacks remain owned intrinsic items, including each configured
  Multiattack weapon. They retire with their actor and cannot become loot.
  Real acquired possessions still leave through the same causal release owners
  and survive terminal retirement. No transferable conjured-item system is
  required by this batch.
- The attack/save adaptations use existing native action and rider owners.
  Tightening the shared hit rider to typed attack identity is explicitly required;
  animation clip names do not identify gameplay attacks or create mechanics.
  Large creatures and grounded flight retain the existing world/AI model.

The presentation additions also retain the event and replay boundary. Existing
`game/animation_data.py` rig ingestion binds explicit canonical content references
to `BodyRig`/`BodyClip` data and local resources; the plan uses that owner rather
than putting sprite paths in recipes or summon facts. The companion requires
each actual secondary attack mapping, timing/contact data, pivot, directions and
shadow policy to be resolved before accepting a unit. Its primary-clip table is
therefore an art assignment, not a claim that all new bindings already exist.

Fey manifestation is a passive semantic birth/origin value consumed through the
main plan's finite codec, shared actor reduction and subjective projection. The
shared material must use that retained value in both native presentation and
passive replay; rendering must not inspect a live Summoned condition, summon
controller or hidden caster identity. This follows the paired plans' typed-fact
and disclosure contract. Any required body-material binding remains the explicit
bounded presentation extension in the companion. Palette/alpha changes neither
create a new birth nor alter intrinsic items, control, duration or hostility.

The approved staged birth, settled condition removal, Fey control exception,
causal actual departure and historical-versus-live registration contracts are
unchanged. Acceptance now covers all 24 ordinary and summoned recipes, slot and
family boundaries, native AI attacks and intrinsic retirement, plus all rig
bindings and representative native clips including Fey material and shadows.
Ordinary lifecycle/replay tests remain independent of rendering.

Documentation/source review only. No production/test files changed and no tests
ran.

## Paired re-review — explicit anatomical weapon usage

Reviewed 2026-10-03 against this exact revised pair:

- `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`, SHA256
  `d32f941cbca1329356b047cf3600ce112a694f89660fcb875f553b93800e0bff`
- `agent_docs/SUMMONING_CREATURE_BATCH_2026-10-03.md`, SHA256
  `d901ac3bade5f823db72561c442b8154fa4847996a7959e92eecd121dbed220c`

**Verdict: approved for this exact pair. No events/items blocker.** The previous
24-creature approval is superseded by this correction to the existing attack
owners. This is design approval only.

Source confirms why this correction is necessary. Weapon slot admission in
`dnd/blocks/equipment.py` currently depends on LIGHT/hand eligibility;
`Attack.adjust_cost_for_off_hand` in `dnd/actions.py` defaults a secondary attack
to a bonus action unless explicit costs are supplied. Both Weapon base damage
and Equipment's damage profiles separately use the off-hand modifier branch.
`Entity.get_weapon_physical_access` currently treats an equipped intrinsic bite
as a weapon. None of these defaults establishes correct anatomy semantics.

The revised plan covers these shared boundaries without creating another item
or attack lifecycle:

- Explicit held/body usage belongs to existing authored WeaponDefinition and
  Weapon data. Body usage requires intrinsic ownership and is revalidated by
  the existing equipment owners. It is not inferred from a display name, art,
  summon state or creature catalog. Ordinary held weapons keep their defaults.
- Both selectable body attacks remain exact owned items in the existing melee
  positions. The normal template author supplies an action cost for each body
  choice; the existing Attack validator already preserves explicit costs.
  Configured Multiattack children retain `costs=[]` because their parent pays.
  There is no accidental secondary bonus-action entitlement or new budget.
- Both live damage and Equipment's AI/outcome profiles receive the same full
  body-attack ability modifier. The existing Attack route retains the source
  item UUID, rolls and recorded results; NATURAL physical access does not turn
  these items into anonymous unarmed attacks or substitute NaturalWeaponSpec
  execution for their item-backed route.
- The primary selection is explicit and remains the existing opportunity-attack
  and threat source. Secondary choices add no reaction entitlement. The targeted
  Wolf/Dretch anatomical definitions receive the same correction as new batch
  definitions while preserving authored stats, dice, traits and Multiattack.

Intrinsic nontransferability, terminal item retirement, real-item preservation,
causal birth/departure and passive replay remain unchanged. Existing recorded
attack results are facts and are not recalculated under the new body policy
during playback. Acceptance explicitly covers both positions, native/AI damage
agreement, standalone and Multiattack budgets, Haste/Extra Attack/Slow boundaries
and unchanged held/off-hand behavior. These checks belong to implementation;
none was run for this documentation review.

No production/test files changed and no tests ran.

## Single-plan re-review — consolidated delivery and connected combat arena

Reviewed 2026-10-03 against the sole implementation plan,
`agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`, SHA256:

`a633f48b625c7bf091492faca60cd5606003683326f3f77430cbadd324eaa9cf`

**Verdict: approved for this exact single document. No events/items/lifecycle
blocker.** This supersedes the prior paired-document verdict for the current
proposed scope. It does not establish implementation acceptance.

Read the complete consolidated plan and the superseded companion pointer.
Compared its lifecycle/item sections against the archived approved pair
`d32f941c...` / `d901ac3b...` under
`.runtime/summoning-plan-review/pre-consolidation/`. Sections 5–9 are unchanged,
and the anatomical-attack contract is unchanged. Section 3 only replaces the
historical instruction to delete a caster lease with the invariant that none
exists. The companion contains no competing work queue or substantive rules.

The single document retains the accepted owner and publication contracts:

- Canonical creatures remain independent; all 24 rows, their cumulative slot
  tiers, actual intrinsic possessions and explicit body-attack usage are in
  section 2. Real acquired items retain exact identity, coatings, charges and
  bag contents through causal release. Mandatory terminal cleanup, voluntary
  vetoes and ordinary creature death/loot remain distinct.
- Prepared birth is captured uncommitted and undeployed, then committed with
  native condition/concentration/world/encounter authority before its single
  publication. Paid action costs, precommit failure and committed publication
  failure retain their documented different outcomes.
- Direct Concentrating -> Summoned, standalone finite Summoned and the Fey-only
  untimed control child preserve one existence clock. Outer graph settling,
  mandatory sustain-loss routing, exact retirement and explicit controller
  close/rebind survive consolidation. No extra registry, lease or event bus is
  introduced by the content or arena sections.
- Recorded birth, ordinary faction change and actual spatial departure remain
  the authorities. Section 10 now explicitly carries Fey manifestation through
  finite codec, shared reduction, subjective facts, historical playback and
  reacquisition. Hostility changes faction without changing its spirit body.
  Presentation reads retained facts, never a live condition/controller/caster.

The delivery sequence is coherent end to end: ordinary body attacks/content,
native owner seams, lifetime/AI, all three spell adapters, recorded presentation,
then complete acceptance. Its presentation packet explicitly permits required
fact fields/reducers alongside their producing packets; it does not defer
authoritative event support until after dependent mechanics. One ledger covers
every creature's construction, allowed selections, native attacks and bindings;
representative lifecycle permutations cannot excuse an omitted creature row.

The new arena scope does not weaken lifecycle or evidence requirements. It uses
one connected ordinary Game/GridMap/Encounter, with existing walls/doors and
visibility. Room/camera transitions preserve UUIDs, conditions, initiative and
resources; contact loss remains distinct from departure. The 64-by-64 and
128-by-128 fixtures are acceptance targets, not claimed engine limits or measured
performance. Keeping the same roster when increasing map area separates area
growth from actor-count growth. Required route completion, decision/frame timing
and actor/controller/handler counts across creation/departure/rebind provide
specific evidence for scale and retained ownership. Small contact clips cannot
replace complete recorded fights or the larger-map checks.

All previous scoped implementation acceptance obligations remain in the unified
matrix. This review only inspected documentation/source and appended this audit;
no production/test files changed, no tests or arena experiments ran, and no
performance claim is made.

## Final single-plan re-review — withdrawn arena scope

Reviewed 2026-10-03 against the final intended sole plan,
`agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`, SHA256:

`001c6bed12ad477b1b386bd985e6cb5f8293f6d644de9be8908121b61575e815`

**Verdict: approved for this exact single document. No events/items/lifecycle
blocker.** This supersedes the preceding `a633f48b...` verdict for current scope.

The human clarified that the arena request was intended for another chat. The
plan therefore removes the arena subsection, 64-by-64/128-by-128 fixture targets
and map-scale acceptance. Those requirements in the preceding historical review
are no longer part of this task. Packet 6 and the acceptance matrix instead
require representative native fights across body families, large creatures and
Fey appearance/shadows, together with all 24 rig/action bindings.

This reduction preserves the approved content, anatomical-attack, staged birth,
condition/control/duration, item retirement, subjective fact, passive replay and
retained manifestation contracts. The complete 24-row ledger and all three spell
adapters remain required, as do exact live-registration cleanup and the full
scoped lifecycle matrix. The consolidated document remains the sole authority;
the superseded companion supplies no additional implementation requirements.

Documentation review only. No production/test files changed and no tests ran.

## Visual-binding re-review — recorded attacks and later VFX ledger

Reviewed 2026-10-03 against these exact bytes:

- Sole implementation plan: `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`,
  SHA256 `001ec7cedbd75d639daf9d43063d865c34605b3ce441a391686479b5646daac9`.
- Linked evidence/acceptance ledger:
  `agent_docs/SUMMONING_VISUALS_ADDENDUM_2026-10-03.md`,
  SHA256 `fadcebe641f88e0f43a487e07f272f75a9ce4b0c63ad1764074b8b8f4069a34d`.

**Verdict: approved for this exact plan and linked addendum. No scoped
events/items blocker.** This approval covers the proposed presentation binding
extension and later-VFX classification, not completed media or implementation.

Source supports the stated gap and the proposed existing-owner route:

- `game/player_projection.py` builds AttackFact from the recorded attack,
  including stable source item ID, instance UUID and attack source kind.
  `game/attack.py:select_attack_profile` already selects authored variants by
  these passive source facts and explicit precedence; it currently lacks a rig
  constraint. `bind_attack` presently selects the profile before resolving its
  retained source actor. The plan explicitly moves rig resolution ahead of
  selection and extends the existing selector, rather than adding an event
  consumer or looking up native equipment.
- The current shared off-hand profile selects Attack5/contact frame 8. The
  existing binder calculates contact and body duration from the selected
  BodyClip's FPS/frames and authored profile anchors. Rig-scoped item/source-kind
  profiles therefore correct both motion and timing through the existing route.
  Exact intrinsic items remain the attack authority; portable mappings select
  their recorded stable item identities, while instance UUIDs retain causal
  identity. No display-name matching or per-species attack event is needed.
- The new passive body-context table covers only non-attack body presentation.
  Its pure helper consumes retained context/movement/condition facts and feeds
  existing samplers. It cannot change native trajectories, costs, outcomes or
  conditions. Required coverage, unique selection and marker/resource validation
  are explicit; absent art cannot remove a legal action or silently count as a
  completed row. Attacks retain their single existing profile owner.
- Ordinary and summoned instances resolve the same canonical body/action data;
  Fey adds retained material only. Empty separated AttackVfx tracks are explicit
  where the source body already contains the effect, preventing a second human
  slash while preserving the recorded damage and normal feedback.

The addendum distinguishes actual catalogue evidence from future production.
Prone's existing Die entry/hold/reverse presentation, Frightened front/back media
and corrosive/dread residue bindings exist in the referenced data; their adequacy
for each new body still requires validation. Existing conditions and independently
lived residues are reused. Missing flight/body mappings remain current integration
gaps, not new VFX commissions or permission to declare those rows complete.

Later V1–V3 cast/arrival/departure cues consume actual cast lineage, the single
birth and actual typed terminal departure. Optional halo/control-break accents
create neither conditions nor a second state journal. The addendum explicitly
orders causal visual milestones without a timer controlling native existence,
preserves observed last body/position, and excludes hidden transitions, ordinary
contact loss, reacquisition and silent reset from replaying a summon/exit cue.
The application-close exclusion is consistent with retaining causal cleanup
facts while selecting no magical-exit media for that cause. Fey control loss
changes recorded allegiance without replacing the actor, body or lifetime.

The main plan remains the sole implementation sequence. The addendum is its
mapping/evidence ledger and future human-delivered brief; no VFX-thread contact
or delivery was performed. Prior lifecycle, item retirement and real-possession
preservation contracts remain approved. Documentation/source inspection only:
no production/test files changed, no tests ran and no new source-strip visual
acceptance is claimed.

## Final visual-binding refinement — exact facts and retained body timing

Reviewed 2026-10-03 against the narrow refinement at these exact hashes:

- `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`, SHA256
  `d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`.
- `agent_docs/SUMMONING_VISUALS_ADDENDUM_2026-10-03.md`, SHA256
  `28dbdf5dec4fcc45afe6a5434ca297ec22da58715a0f044dcd37b9ca18011075`.

**Verdict: approved for this exact main plan and linked addendum. No scoped
events/items blocker.** This supersedes the preceding visual-binding verdict.

The refinement makes the recorded-fact contract more precise without adding
event ownership:

- Source confirms that ordinary item-backed Attack records `equipped` when its
  source item UUID exists, including intrinsic weapons. NATURAL physical access
  is a separate mechanical property. The plan now explicitly preserves that
  source kind and exact item UUID/ID; it does not require NaturalAttack's
  discriminator or rewrite a recorded event to select art.
- MovementFact has movement mode, trajectory and connector presentation key,
  but no action behavior reference. The complete recorded signature, including
  explicit missing values, distinguishes direct-arc jump and connector motion
  without inferred names or native lookups. Exact qualifier, one role-default
  and verified shared fallback give deterministic selection; older records do
  not gain invented movement facts.
- Body playback/marker data is resolved once and retained for both primary and
  recovery on the existing cue. Timing, joins, reverse playback, held poses and
  sampling therefore consume the same authored result. Source confirms that
  current body-action and forced-movement recovery otherwise reread global clip
  data. Explicitly including `bind_shove`, `bind_forced_movement` and
  `sample_forced_body` covers their actual owners rather than assuming ShoveFact
  enters the ordinary body-action route.
- A legitimate disabled gesture retains its effect/child join and feedback.
  The proposed valid neutral binding or skipped unused lookup addresses the
  current unconditional `body_clip` lookup in `bind_body_action`; returning None
  and dropping the action remains prohibited. Required attack/travel/Prone
  coverage cannot be disabled to hide missing media.

The existing rig/profile system remains the only binding authority. Native
movement, item identity, outcomes, resources, condition state and shared causal
join semantics remain recorded authorities. Later VFX scope, event-time
permissions, one birth/departure and silent reset/reacquisition constraints are
unchanged. No additional journal, subscriber, per-species event or lifecycle is
introduced. Documentation/source review only; no production/test files changed,
no tests ran and no other-chat contact occurred.
