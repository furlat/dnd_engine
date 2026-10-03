# Summoning packets 1–2: independent ECS and import-DAG implementation review

Reviewed 2026-10-03 in `/mnt/c/users/tommaso/documents/dev/dnd_engine`.
This is a source review by the independent ECS reviewer, not an implementation
self-approval. No production files or tests were changed, and no tests were run
by this reviewer. No other chats were read or contacted.

## Scope and receipts

The requested inputs were:

- `agent_docs/audits/SUMMONING_PACKET1_IMPLEMENTATION_2026-10-03.md`, SHA256
  `c5e85bb1ce39dcd5f04dc54ee93ab6c5a12de5506f55df2c6358749aae6bcbed`.
- `agent_docs/audits/SUMMONING_PACKET2_RETIREMENT_IMPLEMENTATION_2026-10-03.md`,
  SHA256 `a099eee0e4897b2a50ec62b392368efdc6acecea1b32cc3377b43fe0bf32df4f`.

All 18 packet-specific source/test hashes in the packet 1 report were rehashed
and matched. Shared-file hashes for the packet 1 methods examined were:

| File | SHA256 |
| --- | --- |
| `dnd/actions.py` | `c6f80514f1fe304d931d9e334ff5ad44287391a707c737cc2f223a6cb65aaf7f` |
| `dnd/entity.py` | `6876b16d744b6ad623fc82f135e5959ee71581cd8a19b78697f62eea0cf6881a` |
| `dnd/blocks/equipment.py` | `fc010396a8ed626a693d9b8c36e0e291305fb3423a198c30d04d9eefffc7647d` |

Other retirement/ownership source at the closing read:

| File | SHA256 |
| --- | --- |
| `dnd/core/base_block.py` | `cb0c39c297e5321201116d210934a19baa73113c9b85900adc8d18b2c36da74b` |
| `dnd/core/values.py` | `3c8ac004dc669bec37ffe15a1efae20afc06aec04ff62eb472677961f6e2a122` |
| `dnd/blocks/base_item.py` | `30555a08e97b46537fcc3d2a7e54e59f7bde3d61ae9b70b3479808dbc770b4bc` |
| `dnd/blocks/health.py` | `160f359a004c398184c52bbda2c825c02c5d6748b9d26bebfd7cfedb1f822a29` |
| `dnd/actions_functional.py` | `145aea78804754cf10497d3581c89e731d4d82136ea493cdf7ec5bfa626b1f12` |
| `dnd/game.py` | `dee158751f31d3bba15a76cd1088775eca15f43935362566e60fc748f8692eba` |
| `dnd/core/gridmap.py` | `cbad5ec4f32492d7d6f36ff5824786ea9c33466faf844bcfa407c13a5b070259` |
| `dnd/blocks/inventory.py` | `23d06b624c7f6cccbbce4e208d9f6828bf2447596d01264d5420c73133ac1f22` |
| `tests/engine/test_summon_retirement_ownership.py` | `85ffc700be3c3e06dde56c251ae036e08fa7b71ce8bb6f9f1e2ba155985a5fb6` |

The shared checkout changed during this review. These receipts do not certify
later condition, wall, birth, controller or retirement edits. In particular,
callback-free condition commitment, rollback and publication repairs tracked
by the separate anti-slop review are still in progress and were expressly
excluded from this final implementation verdict.

## Packet 1 verdict: approved within its stated native scope

No remaining concrete ECS, body-attack or import-DAG blocker was found in the
ordinary 24-creature prerequisite. This does not accept downstream summoning,
rendering or the whole repository's regression suite.

The 20 new recipes are ordinary Entity compositions over the existing SRD
composer, with four existing recipes reused. Cold rows define stats, explicit
possessions and parameters for existing native features. They contain no caster,
lease, Game, controller or summon-aware creature subclass. The imports stay
acyclic: builtin composition imports the family modules; those consume existing
recipe/feature declarations, Entity and the shared composer. Neither a lower
item/Attack owner nor the passive equipment enum imports the new roster.

The anatomy change is one explicit held/body value on existing definitions and
Weapon instances. Ownership validation requires an intrinsic natural item.
Equipment admission, actual damage, AI damage profiles and physical access all
consult that value. The Attack default-cost validator preserves explicitly
supplied costs, including Multiattack's empty child costs and reactions, while
the ordinary secondary body attack costs one action and receives its full
ability damage. The normal Attack resolver and recorded equipped-item identity
remain authoritative. No species-name routing or second attack executor appears.

Multiattack keeps its authored sequence, uses the parent action budget and does
not obtain a whole sequence from a restricted Haste discovery variant. Ordinary
Extra Attack, Haste single attacks, Action Surge, Slow and primary-slot
opportunity attacks continue through their existing owners. The exact item-ID
HitSaveRider selector is shared by runtime and AI metadata and does not confuse
display names or the separate NaturalAttack event kind.

The body-size adjustment is necessary and correctly bounded here:
`Entity.get_size_damage_dice` compares a body weapon's current size with
`structural_base_size`, which Entity.create takes from the ordinary recipe's
configured size. Thus the Huge Tyrannosaurus's authored 4d12+7 bite does not
silently gain another 2d4. Enlarging it by one size adds the existing one d4
through both the actual damage and outcome-profile callers. Held weapons and
the independent NaturalWeaponSpec route retain their existing baseline. This
does not introduce a new size or polymorph system.

I inspected the authored native tests and existing receipt logs. The logs report
76 packet checks passed, 419 expanded checks passed with one disclosed obsolete
`creature.player.fighter@1` scenario reference, and scoped Pyright with zero
errors. These are author-run receipts, not reruns by this reviewer. The obsolete
scenario reference remains an overall validation reconciliation item, not a
reason to restore a retired factory in this packet.

## Packet 2 verdict: changes requested for exact ownership completeness

The ownership direction is sound: Game delegates exact actor retirement to
Entity; Entity snapshots current inventory/equipment membership, keeps real
items intact on supported ground, and separately retires intrinsic items.
BaseBlock traverses owned composition edges; ModifiableValue releases its own
four channels and merely detaches imported target channels. Neither retirement
path sweeps matching source UUIDs, so unrelated recipient effects and real loot
are not selected merely because their source matches the departing creature.
Spatial exit is published while actor identity remains available, and senses,
attached light and Game membership have native release paths.

However, the traversal only covers authority explicitly retained by these
owners. The following omissions prevent accepting the report's complete
handler/action/block/value release claim.

### ECS-I1 — P2: weapon refresh handlers must have a retained native owner

At the initial read, `actions_functional._setup_weapon_event_handlers` registered
both weapon refresh handlers directly with EventQueue, while retirement only
released handlers in each block's `event_handlers`. Every canonical creature
uses this setup through `create_creature_entity`; both handlers and their
BaseObject identities therefore survived actor retirement.

The shared checkout was corrected during this review: at SHA
`145aea78804754cf10497d3581c89e731d4d82136ea493cdf7ec5bfa626b1f12`,
`actions_functional.py:208`–209 uses `entity.add_event_handler` for both. Source
inspection confirms the intended exact owner now reaches them. The final
implementation receipt should include this repair and exercise ordinary
canonical creature retirement; no source sweep is needed.

### ECS-I2 — P2: replaced action templates remain registered

`Entity.unregister_action` (`entity.py:5090`–5096 at the recorded hash) only
filters `registered_actions`. BaseAction instances register with BaseObject,
and the method never releases the removed objects. This is exercised without
unusual input: `apply_creature_possessions` calls `update_weapon_templates`
after initial setup; weapon release publications replace templates again while
the actor is still live. Retirement unregisters only the final remaining list.
Earlier owned templates have already fallen out of that list and survive.

Release the exact removed template objects in the existing action replacement
owner, as `unregister_action_by_uuid` already does. The reset in
`setup_standard_actions` must likewise release the exact templates it replaces.
Verify both current and replaced canonical Attack template identities disappear
after retirement, without removing independent actions by matching source UUID.

### ECS-I3 — P2: Health's owned hit-dice collection is absent from traversal

`Health.hit_dices` is a list of HitDice blocks (`health.py:344`), populated for
every canonical creature. BaseBlock's existing population helper adds only
direct BaseBlock-valued fields to `blocks`; the new `owned_block_tree`
(`base_block.py:701`–711) traverses only that dictionary. Consequently the actor's
HitDice block and its two ModifiableValues/four owned channels are omitted from
retirement. This is an actual owned collection, not an unrelated source match.

Expose or release these exact collection members through the Health owner.
`remove_hit_dice_by_uuid` already demonstrates exact release without reflection
or a source sweep. Include the collection in preparation if it can own condition
memberships. Check any directly owned list-valued channels at their actual
owners as part of the same bounded repair; do not recursively scan arbitrary
model fields or delete imported/shared values. A canonical recipe retirement
must leave no live registration for its retained hit dice and owned channels.

The bounded list inventory found by source inspection is Health.hit_dices,
Weapon.extra_damage_bonus, Equipment.extra_attack_damage_bonus and
Spellcasting.extra_spell_damage_bonus. Authored weapon building creates the
first damage-bonus list directly (`authored_item_builders.py:178`), and
Spellcasting.create creates its list values directly (`spellcasting.py:702`–717).
Weapon coating conditions also append their own exact bonus values and remove
them on condition cleanup (`consumables.py:483`, 510–515); that condition owner
must settle first, and transferable weapons must retain their item-owned list.
No runtime writer outside the Equipment field was found for the equipment-wide
extra-attack list in this bounded search, so that is an owner-contract edge,
not a claim that one of these 24 recipes currently populates it. Scalar dice
arrays, passive sense modes and BaseModel resource records are not additional
registered value/block ownership requiring recursive discovery.

The existing ten retirement tests cover real loot/coatings/charges/containers,
intrinsics, conditions, a currently registered action, independent source-equal
effects, vetoes, observer failures and attached light. They do not establish
I2/I3's omitted ownership paths. Condition authority/publication repairs and the
later content-binding/controller integration also need their own frozen final
review; this packet's positive ownership direction is not approval of those
still-changing seams.

## Packet 2 correction review — condition, birth and spatial prerequisites

**Verdict: CHANGES REQUESTED. I1–I3 are resolved in the inspected source; the
shared prerequisite still has the concrete I4–I6 blockers below.** Packet 1's
earlier approval remains unchanged. Mandatory wall-section terminal authority
was explicitly excluded because its implementation was still being finished.

The rewritten condition report has SHA256
`5b5bce41a238cb53bb72cf9df1db0d616cac194b4861fcfb632725a48563f6b9`.
The expanded retirement report has SHA256
`be711f8468cdd8da8e5a293e77ee8afe880bac42055fbe72351955b21c705988`.
The report records 143 focused condition checks, 470 expanded passes plus the
then-open mixed spatial-child order failure, 69 final checks and zero typing
errors. Retirement records 125/132/13 passes and zero scoped typing errors.
These are author receipts. I read the completed root spatial-correction log,
which reports **58 passed**; no tests were run by this reviewer.

### Corrections accepted in source

- Exact weapon refresh handlers now belong to the Entity. Action replacement
  and standard-action reset release the exact old template identities.
- Health exposes its typed hit-dice children; Weapon, Equipment and Spellcasting
  expose their exact bonus-value lists. The native traversal and release use
  these explicit edges. The new canonical-Wolf regression observes owned block,
  value, channel and modifier identities disappearing while an independent
  source-equal value and acquired weapon bonus survive. There is no source
  sweep or arbitrary field recursion.
- Prepared application owns its cancellation record before replacement and
  required-concentration admission. Concentrating retains its partial transfer
  record before admitting children. These corrected paths drain their admitted
  records. Invisibility's direct flag and Haste's restricted grant now commit
  at the native hook; failed preparation does not keep either, and Haste
  lethargy is a post-membership consequence.
- The removal publication list preserves actual mixed ordinary/spatial
  child-before-parent order. It attempts all rows after publication errors.
  The outer condition scope resets its contexts before running each settled
  callback, and does not skip later callbacks after one failure.
- PreparedBirth retains one passive birth fact, commits creation once, and
  does not erase authoritative identity after a publication error. Prepared
  Game deployment commits world and Game membership before presence
  publication. These owners remain concrete and acyclic; no high summoning
  runtime is imported into BaseBlock/BaseCondition/Entity/Game.
- The single Banished return admits displacement before commitment, restores
  silently and publishes afterward. Antimagic's suppression markers are now
  exact linked children; restoration happens after the parent authority is
  removed. The multi-return interaction remains I4 below.

### ECS-I4 — P1: independent return reservations can conflict within one graph

`Entity.prepare_spatial_return` creates a new local `reserved` set for each
Banished condition (`entity.py:902`). In one existing upcast Banishment
concentration, two returning creatures can select the same free adjacent cell
for their respective current occupants. `Concentrating.prepared_removal_occupancies`
collects positions afterward but neither coordinates nor rejects overlaps.

For example, return origins `(2, 3)` and `(3, 2)` are occupied; `(2, 4)` is
blocked and `(3, 3)` is free. Both returns can select `(3, 3)` for displacement.
All tokens pass the initial validation in `_commit_prepared_condition_removals`.
The first return then occupies `(3, 3)`; the second `commit_spatial_return`
revalidates, fails, and leaves the first return/condition removal committed
while the concentration replacement has not completed. Distinct blocking
occupants suffice; no speculative new movement mode is needed.

Share bounded reservations across the same removal graph, or reject conflicting
native prepared occupancies before any authority mutation. A normal successful
upcast return should use distinct legal cells when available; a rejected graph
must leave both old conditions/positions intact. This is a reservation/admission
correction in existing owners, not a request for another movement resolver.

### ECS-I5 — P1: callback-free removal still has reachable native exceptions

The repaired Invisibility/Haste/Banished/Antimagic examples do not make all
condition graphs consumed by this generic seam silent. Actual remaining paths:

- `Hidden._remove` (`conditions.py:2417`) calls `set_stealth_dc`, which publishes
  perceivability during `commit_owned_condition_removals`. Canonical creatures
  can Hide using their standard actions, so this is directly reachable on actor
  retirement.
- LightEffect, ContinualFlameCondition, ProduceFlameEffect and FireShieldEffect
  remove a light source with ordinary publication enabled. SeeInvisibility,
  TrueSeeing and Darkvision cleanup directly notify perceivability. These are
  real recipient conditions the ending actor can own, not new creature content.
- `SpiritGuardiansSlowSource._remove` (`conjuration.py:2242`) publicly removes
  the last shared slow manifestation. Its application creates/reuses that
  manifestation without adding a child/link consumed by the prepared graph.
  `SpatialRestraintSource._remove` (`restraints.py:220`) does the same for the
  last shared Restrained manifestation. Concentration replacement of existing
  Spirit Guardians/Entangle/Web can therefore recurse through vetoable public
  removal during the advertised authority-only phase.

Split these existing native cleanup effects into silent committed state and
retained publication, using the same bounded owner contracts as the repaired
cases. The shared manifestations must be admitted into the current exact
graph, or have their existing owner supply an equivalent prepared removal and
ownership transfer. Merely moving the outer condition completion is insufficient.
This remains the original AS-1 contract, with additional concrete reachable
owners; it does not authorize an event buffer or blanket veto bypass.

### ECS-I6 — P2: direct spatial removal still drops partial admission ownership

`SpatialCondition._remove_spatial_graph` (`area_conditions.py:836`) restores
operation metadata in `finally`, but does not cancel accumulated prepared
entries if a later child's admission raises. `_prepare_condition_removal_tree`
cancels the current failing node only. A native parent or an earlier child can
therefore retain accepted removal resources while its committed graph remains
alive. The ordinary BaseBlock removal and Concentrating wrappers now have the
necessary exceptional cleanup; this spatial wrapper needs the same bounded
drain and original-error preservation. The issue is the wrapper's exception
path, independent of the unfinished mandatory wall policy.

### Correction-review snapshot

Shared-file hashes identify the inspected revision and do not approve subsequent
parallel edits:

| File | SHA256 |
| --- | --- |
| `dnd/core/base_block.py` | `585f3cf7f76ae38334deefa392e12c405fa937881f363cd2906df6eee91043d8` |
| `dnd/core/base_conditions.py` | `2198c803c05fc771fc76dd22992d22aa3f13a5416a3045f9aeed58312c5dd01f` |
| `dnd/conditions.py` | `1385b4076bed84f7cf35ecd9b164d5905e5ec9ce3ed6aa877633482673aeb083` |
| `dnd/entity.py` | `9365b7f8839b53b63036b606ff4f313d5f971b721b89cf017d70c1eb54130dc4` |
| `dnd/actions.py` | `c6f80514f1fe304d931d9e334ff5ad44287391a707c737cc2f223a6cb65aaf7f` |
| `dnd/spells/abjuration.py` | `45608c304f1cc5d446e8b611201d66498e1cc6864b099b24210709d3a14481a5` |
| `dnd/spells/transmutation.py` | `7427b5a2396a62be4aeec5aacab346071e27e75bdd94bc3b9291eb2d77964bc1` |
| `dnd/spatial/area_conditions.py` | `a27b93e8690d6c1027e1d78cdd9e8e7349a6a7f3bfff3d4bf2a8442ee7a19da6` |
| `dnd/blocks/health.py` | `fe1dd60829b44df54d6fdaa72d26fed9de6ec8cd4e782e5d77306ef6b611fba8` |
| `dnd/blocks/equipment.py` | `05b77fddd9dcb317d07a1c7dd281b319f494ca8e7e8260b7ed3d7dfcbc987a76` |
| `dnd/blocks/spellcasting.py` | `5f065f7d996ce645a9328fb2ce787473deab23bf0c089c2817d65648945d0a77` |
| `dnd/actions_functional.py` | `246fe0555ce8c4ffd314176de43491deb0a6f3fdb0dea3fb6b8c66a80b5c2d84` |
| `tests/engine/test_summon_retirement_ownership.py` | `48ff488196ea0e784088da4b69c936b81e2b36d4e0418fc328e898ed93c77088` |
| `tests/engine/test_prepared_condition_lifecycle.py` | `26dac70baa071b86163a240f28876f5bfd18ac3d0f30abbb4f8855b3216cdbec` |
| `tests/engine/test_prepared_entity_birth.py` | `af2b1437fc3a71794396748f743927c288cce049f11d83bc5291c2a9eea57667` |
| `/tmp/summoning-spatial-removal-corrections.log` | `960e825a09a4cbe01c15f1a5c1c754039efd6f37f09dd69270333a34bd6db5da` |

Additional method receipts use `ast.get_source_segment` over UTF-8 source with
universal-newline normalization:

| Method | SHA256 |
| --- | --- |
| `Hidden._remove` | `fc37dd2780e42b2c15829637b99e112f6e195b53d62ef8c3d43377e8c64a6f15` |
| `SpiritGuardiansSlowSource._remove` | `4d9ba6faf3dc73ced2b9f776b66b2fbcd60fc5b0da51ca69a9cb2706b7c0c175` |
| `SpatialRestraintSource._remove` | `885f5a55d813c6a7d9fd1b60776875edfa7fe35fb6c403af2527ef74cd878acb` |
| `ProduceFlameEffect._release_owned_runtime_state` | `c5bbdd48090b22e937ebb9a1ee1554842d4415c267c2c1f433f5995727cc8fa2` |

Only this audit was appended. No production changes, test execution, external
chat reads or external chat messages occurred during this review.


## Native packets 2–4 final source re-review (2026-10-03)

**Verdict: approved within the native ECS, ownership, lifecycle, spell-dispatch
and existing AI scope inspected below.** Packet 1's earlier bounded approval
stands. No remaining concrete blocker was found in these native packets after
the corrections in this section. This is not approval of presentation/artwork
or a claim that the entire repository regression suite is green.

The approved authority remains the unified plan at SHA256
`d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`
and its visual addendum at SHA256
`28dbdf5dec4fcc45afe6a5434ca297ec22da58715a0f044dcd37b9ca18011075`.
This append preserves the earlier findings rather than rewriting their history.
The reviewer read source, authored tests and existing execution receipts;
**the reviewer did not execute tests or change production/test files**.

### Earlier native findings resolved

- **I1–I3:** Weapon refresh handlers use the Entity's owned handler API; exact
  action unregistration releases its BaseObject template; Health owns HitDice
  through typed composition edges, and Weapon/Equipment/Spellcasting own the
  three typed damage-bonus lists. Successful retirement follows these exact
  owned blocks/values and releases their local channels without removing an
  unrelated same-source value or the bonuses of real acquired loot.
- **I4:** Aggregate condition-removal validation checks all retained spatial
  return occupancies before mutation. Conflicting simultaneous Banished
  displacements reject the old graph's removal intact instead of committing
  the first return and failing on the second.
- **I5–I6:** Hidden, native sight grants and light owners separate committed
  authority from their retained observation. Shared Spirit Guardians and
  restraint manifestations use the existing child graph. The direct spatial
  wrapper drains prior admitted entries on a later exception. Child ownership,
  independent manifestations and surviving shared sources remain explicit.
- **I7:** Wall, item and actor preparation retain accepted tokens before the
  next admission callback. Exceptional cancellation attempts every accepted
  token despite an earlier cleanup error and preserves original/cleanup errors.
  GridMap publishes cancellation for explicitly registered accepted effects,
  while wholly unpublished mandatory proposals remain unpublished. Wall-section
  terminal authority proves the exact parent/section/condition ownership edges;
  an unrelated same-source object does not receive that authority.
- **I8:** PreparedEntityRetirement retains exact item container identities, and
  Equipment validates the admitted item, owner and slot before commitment.
  Same-actor reslotting, equipping or moving an admitted item cannot pass using
  an unchanged inventory UUID set.
- **I9:** Haste and Antimagic's membership consequences recognize the exact
  retiring target from TerminalOwnerRelease. They do not recreate state on that
  departing actor, while a surviving external recipient retains ordinary
  lethargy/restoration consequences. This is an exact target test, not a broad
  source-based suppression policy.

### Corrections found during complete integration review

**I10 — mixed condition completion order: resolved.** Deferring ordinary
condition completions until settled lifetime consequences initially left
independent spatial completions immediate. A spatial parent could therefore
complete before an ordinary child. Both now enter the same ordered
`condition_removal_scope.completions`; the independent row delegates to its
existing native publisher at its proper position. Committed authority still
changes before publication, and the outer scope drains settled callbacks and
all retained completions after errors. The later 38-check spatial/replay receipt
covers the reported regression.

The related immediate-agency correction is also sound: the dependency-neutral
ConditionRemovalParticipant commit callback runs immediately after the native
condition membership indexes are discarded. The high system revokes the exact
existence owner's agency there, before an incoming birth observer can attempt
an action or reaction through the departing actor. Actual retirement and
Encounter list surgery remain with their settled/native action boundaries.
No high SummoningSystem import or executable event payload was added below.

**I11 — creation before remaining EFFECT vetoes: resolved.** The initial high
creation handler ran inside ordinary CAST_SPELL EFFECT dispatch. A later native
EFFECT handler could reject or raise after birth, deployment and old
concentration replacement had already committed. SummonSpell now finishes
ordinary `phase_to(EFFECT)` dispatch and checks its returned cancellation before
invoking the explicitly admitted mechanical owner. The existing EventHandler
registry retains that owner as a direct-only SYSTEM handler whose UUID is the
bound identity. EventQueue's narrow `invoke_admitted_system_effect` delegates
through the existing invocation helper, preserving behavior provenance and
passive dispatch evidence; it adds no registry, queue, new command event or
callable replay payload. It rejects missing/disabled/non-system/triggered
handlers and non-EFFECT/canceled/unregistered inputs. The spell's temporary
executable registration spans both admission and direct invocation and is
removed in `finally`, including a raised ordinary handler. Already-committed
cast lineages return their existing event and do not create another actor.

### Executable ownership and dependency assessment

The canonical 24 recipes remain ordinary creature data/compositions. The three
spells expose 42 authored family/form/slot choices, one selected destination and
native costs. Pure discovery uses the dedicated unpublished admission proposal;
it neither materializes an Entity nor prepares lifetime/concentration resources.
Player spell input does not select a different sustain policy. The trusted
independent-effect route can supply NONE without authorizing another spell.

Summoned is the sole duration owner on the incoming creature. Animals and fiends
link it directly to Concentrating. Fey alone adds an untimed SummonControl:
control loss preserves its Entity, controller and remaining duration, commits
its hostile faction and publishes that exact change. The canonical recipe and
other natural instances are not mutated. The clock skips its birth interval,
deduplicates an already-progressed encounter/round interval, and pauses while
there is no native encounter progression.

The high binding prepares native initial conditions, optional concentration,
birth, Game deployment and Encounter insertion before their authority commits.
The retained birth contains the initial summon provenance/conditions and is
published once after those owners commit. Failed admission cancels unpublished
preparations; a publication failure after committed birth does not unregister
an authoritative actor. Concentration's mandatory sustain links use the lower
passive policy and exact involuntary-loss cause, independently of unrelated
voluntary veto branches.

Removal admission is common to ordinary and mandatory native paths through the
lower participant protocol. The high binding owns its exact prepared retirement
and validates/cancels it through Entity. Existence removal revokes agency at
commitment; settled receipts trigger the exact retirement, item drop/intrinsic
release, Game removal and controller release. Deferred condition closure keeps
terminal departure/faction observations inside their causal event lineage.
Dismiss Summon uses the existing action pipeline and checks both the original
summoner and current control authority; uncontrolled Fey cannot be dismissed
through the expired bond.

One existing NativeAIController/assignment owns each summoned actor. Encounter
insertion preserves the active actor and uses the existing execution UUID for
turn/AI budget identity, rather than a mutable initiative index. Current-actor
removal waits for the native membership execution boundary after immediate
agency revocation. Rebinding a survivor releases the old inactive CombatantState
and controller, retains creature identity/conditions/HP/clock, and uses existing
initiative for an uncontrolled Fey lacking its former caster. Close and silent
reset release their explicit handler, participant, settled-hook, lifecycle and
Game-callback registrations.

Fey faction updates invalidate native movement knowledge through the existing
actor-state key. Autonomous actors use ordinary AI fact projection and action
availability, without master commands or direct player turns. Multiattack's
new child binding is the normal `action.attack` behavior provided by
`action.monster.multiattack`; the original Attack resolver and empty child
costs remain in use. Packet 1's distinction between authored structural body
size and extra magical size damage remains intact.

The import direction remains lower passive types/native protocols and owners
up to the explicit summoning composer. BaseBlock, BaseCondition, Entity, Game,
Encounter and the generic spell/Attack owners do not import the high summoning
runtime. No late-import workaround, reflective source sweep for successful
retirement, second creature hierarchy or new AI framework was introduced.

### Validation receipts and limits

The available author report records 148 focused retirement/condition checks and
zero scoped typing errors for the I7 correction. The I9 report records 51 checks
covering its eight new native cases and neighbors. Existing logs inspected here
record 71 expanded lifecycle checks, then 38 mixed-closure/spatial/replay checks,
and **87 checks in 32.22s** for the subsequent native dispatch run. The lifecycle
source includes all 42 authored form choices, interruption before birth, source
death despite voluntary veto, duration, dismissal, independent sustain,
rebind/close and the incoming-birth agency observation. The final duplicate
lineage return was inspected directly after that 87-check run; no new execution
receipt is claimed for that two-branch adjustment.

The first broad engine/AI/architecture receipt finished with **2520 passed and
5 failed**. Its failures were the standard-action handler-count fixture, the
mixed spatial ordering regression subsequently covered by the 38-check run,
a structural-definition-count fixture and two Encounter metadata/docstring
checks. Joined-after metadata has since been corrected in the inspected source.
The separate broad typing log reports zero errors. The implementer still owns
closing/rerunning the remaining broad checks; this source approval must not be
reported as a completed full-suite run or presentation acceptance.

### Closing native snapshot

Hashes below identify the inspected shared-file revision. They do not certify
later parallel edits or uninspected presentation files.

| File or receipt | SHA256 |
| --- | --- |
| `dnd/core/base_block.py` | `0ea5a0b5160eb38d6745be9541e220b98c74272f413fa1a71d06e360547ff405` |
| `dnd/core/base_conditions.py` | `2198c803c05fc771fc76dd22992d22aa3f13a5416a3045f9aeed58312c5dd01f` |
| `dnd/core/events.py` | `7bf91ba0330a9882a3b54c27c0d93d1cdba3c87806ce99c3b85b9ce986dbbf59` |
| `dnd/conditions.py` | `332700c8e3d2870f42f4c968ea879ea9c74df7fb044528c0364af28b403eb4b4` |
| `dnd/entity.py` | `17fe81d7636e478fa05e0ff2f26fee4a8035dc92af0fe3a0e957bef5c5f5649a` |
| `dnd/game.py` | `dee158751f31d3bba15a76cd1088775eca15f43935362566e60fc748f8692eba` |
| `dnd/encounter.py` | `ad10b9b964dc601865bf12755af2b3e2e5f7d0abecbfce37b1e8768c0ce718a8` |
| `dnd/blocks/base_item.py` | `187528f66182b6028ee7079e75a8a9112311b22b31dc60798827455dc935fe7e` |
| `dnd/blocks/equipment.py` | `c4fc444fe9fde70638210ce96f5d8e3c1ac47a654abfe07834f4240b2c1b027f` |
| `dnd/core/gridmap.py` | `c5808bfba32961491a86c5ded8847ce51c8f0e7434de82e252020197f4eeea23` |
| `dnd/spatial/area_conditions.py` | `21dc0944eac2c088699da3eea81949d9e8d9ba186f5e53de1e6ecb162f599c00` |
| `dnd/spells/transmutation.py` | `4704405af6bba947d0d796fee58b5aedd246c98ef8df62e642a068bfef8703d9` |
| `dnd/spells/abjuration.py` | `ab475a88c457f025c4c335c1e6fce33dc8dae03f8c7f81e38e8406df4f437f8f` |
| `dnd/summoning/system.py` | `6d2dbbda64b924d3389da7848319c56ff521a93ffbccb2570c97009f5177e009` |
| `dnd/summoning/conditions.py` | `909880597f3a082bde34cdcc4ca35cf33e4d0f325329b91dd56ff62f1e3d22d4` |
| `dnd/summoning/actions.py` | `db5ded8cb35967b350a853adaa1759a22f2d2bb62eaf92e49adc4c5fa765110a` |
| `dnd/summoning/forms.py` | `145d4c0c4c6c2d89572ee4a9de876794da4c76584fe81c6fde53770646c0b3dd` |
| `dnd/spells/summoning.py` | `a18ddb8c702f89986bff296507469e33efe98199d6f713177f110b05d8b158fb` |
| `dnd/types/summoning.py` | `861905da36883018471c12627f77acb9d5d3e76a9bc8a297e8fa56a42a443ed6` |
| `dnd/monsters/traits.py` | `9c524d7b59cde21a0e399fd5e9f14d90cd192f792066d2c1005fc9e4b5494137` |
| `tests/engine/test_summoning_lifecycle.py` | `be303e3bdf4655d037f4801d5e5df0d6f9c98d9df9011e78e0db9748b78cd4f0` |
| `agent_docs/audits/SUMMONING_PACKET2_RETIREMENT_IMPLEMENTATION_2026-10-03.md` | `99aee6506181cfa5c0cf28d41a39559384b56fd719229e5f2f9f32f14f2e09ad` |
| `agent_docs/audits/SUMMONING_CONDITION_SEAMS_IMPLEMENTATION_2026-10-03.md` | `d63983acd3f0e1fcb46d55726778fd943dd128ad9268f9793c1f954d70a2fe65` |
| `/tmp/summoning-lifecycle-expanded.log` | `3892480f8c9d75666196720f5d3a7f9e47b53d9df5520874517da58cc1241e86` |
| `/tmp/summoning-mixed-closure-tests.log` | `ccb31c213aec79c282dfecced9bc03f70dcff4d526e40b01af26263c4c2dd6b2` |
| `/tmp/summoning-lifecycle-dispatch.log` | `ddc399123354e37efac10b87836a2f15d7b502dd57589c3b4d322079d6b07151` |
| `/tmp/summoning-full-engine-ai-architecture.log` | `7060d3aa74011c0b8c28c00b210baf5bc400a964327ac95c2c09cf0a3684aaeb` |
| `/tmp/summoning-full-types.log` | `46a6c7834c9080ada23a415afd925abecc37d531f5c6e3d14ad0a7ff579096cb` |

Only this audit was appended. No production/test edits, test execution,
external chat reads or external chat messages were performed by this reviewer.


## Bounded closure and human content amendment (2026-10-03)

**Verdict: approved.** The Wet ownership correction, committed drop-error drain
and amended canonical Raptor data introduce no remaining concrete ECS,
ownership or import-DAG blocker. This extends the native approval above;
rendering quality and the active renderer regression run remain outside this
review. Only this audit was edited, and the reviewer ran no tests.

WetSurfaceMembership now records Wet in the existing shared subcondition graph.
When that membership creates Wet, it supplies the primary parent; when it borrows
an existing Wet it adds only a shared parent. Thus ordinary independent Wet keeps
its independent lifetime, overlapping surfaces can transfer primary ownership,
and the final owning source removes the manifestation through the same prepared
native graph. The former nested public `remove_condition_by_uuid` call during
cleanup is gone. The existing overlapping-water regression and the new dismissal/
expiry cases exercise the real manifestation, modifiers and terminal removal.
No separate lease registry or condition-removal executor was introduced.

Entity's committed retirement now catches `item.drop` failures into its existing
publication-error collection and continues exact cleanup. The inspected Torch
hook commits its unlit state and GridMap removes its light authority before
publication can throw. The retained real item has already been released to its
admitted floor position; the error no longer prevents later possessions,
intrinsics, world membership, registries or controller cleanup from finishing.
The native lit-Torch regression verifies the raised error together with removed
actor authority and the surviving unlit floor item. This is an exceptional
committed-publication drain, not a rollback of a completed departure.

The additional late EFFECT exception and duplicate-delivery tests now exercise
the I11 correction directly. The former preserves the existing concentration
and creature with no incoming birth after paying the action; the latter returns
the same admitted effect without another actor or cost. The prior final source
verdict's execution-receipt limitation for that duplicate return is therefore
closed by the subsequent native correction run.

The human amendment replaces this batch's Tyrannosaurus gameplay recipe with
ordinary **Raptor** content using the already-selected Blue Raptor numerical
baseline: Large, 51 HP, AC 13, speed 60. It defines separate intrinsic BODY items
for Bite (2d10 piercing) and Tail (1d8 bludgeoning), both reach 5 with normal
Strength damage and native one-action standalone attacks. It does not retain
Tyrannosaurus Multiattack/grapple behavior. The unlock is slot 5 for Animals and
slot 6 for Fey through the existing family floor. This remains one of 24
canonical recipes and 42 family/form choices; natural instances still construct
without summon state. The vendor rig/art identity can remain
`smallscale.tyrannosaurus` while its exact content selector names
`creature.raptor@1` and its attack selectors use the new exact item IDs.

Raptor explicitly retains `Appearance.visual_scale = 1.55`. The approved larger
beast adjustments are cold per-creature values assigned to the existing passive
Appearance component; they do not change native size, attack mechanics,
occupancy or the one-anchor placement rule. The visual quality of those choices
requires the separate presentation review. The mechanical size-damage regression
now uses Mammoth to retain the original Huge-body-versus-magical-enlargement
assertion after the human removed the Huge Tyrannosaurus recipe.

Inspected execution receipts, without rerunning them:

- Native correction batch: **130 passed, two failed** only because the new Wet
  fixtures omitted the required activation parent. After that fixture correction,
  the Wet/terminal batch is **35 passed**.
- Full native follow-up: **2531 passed, one failed** because a new Continual Flame
  test asserted its completed publication inside the still-open outer removal
  scope. The same assertion now runs after that scope; **all 19 checks** in its
  file pass, with no production change for this correction. This reconciles
  that last native failure without claiming an additional all-green broad run.
- Raptor combined content/lifecycle run: **150 passed, one failed** in the size
  regression's exhausted fixed-dice fixture after switching to Mammoth. That
  includes the **75 lifecycle checks**. Supplying the legitimate extra save roll
  makes **all 76 canonical checks pass** in the corrected content run.
- Final whole-project typing receipt: **0 errors**.

The earlier failures remain visible in their original logs and this audit;
only the specified corrected follow-up receipts are treated as passing.

### Bounded closing source and receipt hashes

| File or receipt | SHA256 |
| --- | --- |
| `dnd/spatial/environmental_conditions.py` | `7288db6270c4f86487e4d84fba411083f83d14b8e0f21270ccc61c52dee0421c` |
| `dnd/entity.py` | `668b500925582c27347835129c20745c853a5adae56b196a765316ab0fe7e15d` |
| `dnd/core/base_conditions.py` | `2198c803c05fc771fc76dd22992d22aa3f13a5416a3045f9aeed58312c5dd01f` |
| `dnd/core/base_block.py` | `0ea5a0b5160eb38d6745be9541e220b98c74272f413fa1a71d06e360547ff405` |
| `dnd/core/events.py` | `7bf91ba0330a9882a3b54c27c0d93d1cdba3c87806ce99c3b85b9ce986dbbf59` |
| `dnd/summoning/system.py` | `6d2dbbda64b924d3389da7848319c56ff521a93ffbccb2570c97009f5177e009` |
| `dnd/items/torches.py` | `a8eb44c0e879e569cd1451745ae84985a77491eac066d6b9b751c01cd698b0ad` |
| `dnd/monsters/beasts.py` | `b1e5f333a1e6d0d95be749dd05d83aefec9c40dc682f63babd401b6cd52de15f` |
| `dnd/monsters/multiattack_definitions.py` | `57f186b79f76aa1daa5e966ae462a7d6fbcecaa6c34bcb2a8200b4d68d21baa0` |
| `dnd/content/items/authored_item_definitions.py` | `7625ef04c218bf17d17ce949d8762cffb2df3137ea9bf6d51933a7267685ad69` |
| `dnd/summoning/forms.py` | `64e17b956869d915f47d35aba694e5a031ae26c3aa884d4a91231c2c9a04140a` |
| `dnd/blocks/appearance.py` | `acad55f1b0aa839ce23ec565c5bc8cc7d1a21031424a13355c5cc2156b861d07` |
| `game/data/rigs/tyrannosaurus.json` | `5c61dd730a06c6f9e1c94bfb6c41824771e45a95ae42c62071f13649afad7856` |
| `game/data/neuroclient/attack-profiles.json` | `d9e4ccb3e3571e6b3b818e18e27a1f0cd468ea7214b248e02543f6bd853ea9d2` |
| `tests/engine/test_summon_terminal_consequences.py` | `571777b5c820b359a5097d3a0a534b5790bd0898f45a9d9cef69ec11c67f3591` |
| `tests/engine/test_summoning_lifecycle.py` | `ed7e277f5f7a0d79195b6131d1945b498f1c66c0ae3a9f9e0cd130df477194f8` |
| `tests/engine/test_condition_silent_removal.py` | `e0fcb30658a1a3de85b46a103fba51f83a3b8811005a6a45a5832a91dc772ad5` |
| `tests/engine/test_canonical_body_creatures.py` | `6f173c6b34d379e98eea30834c7a84945462ac41c1b3839e7752186ab3570578` |
| `/tmp/summoning-wet-terminal-final.log` | `093addcbc498dcac675cabd1fed6411f54196dad5bade0064430478167df4942` |
| `/tmp/summoning-native-corrections-final.log` | `f8391b10cc68c83c6ed1f06c55c1e224eec5f60d2acb278ca3adcbab9bd4b1b4` |
| `/tmp/summoning-full-native-final.log` | `3713bfc5d9d46aec9362026882c5bdc8b338ebfe9295905338af0e42dbc228da` |
| `/tmp/summoning-silent-removal-corrected.log` | `353cd58b3ad0caa858f182bf3a57d300e83ba84a1c949b2ef3ae1580aae56988` |
| `/tmp/summoning-raptor-content.log` | `f123b5ba68f19ab845d491ddad931ff2ac72de1a42114f3f0cd7787fc13585ac` |
| `/tmp/summoning-raptor-content-corrected.log` | `eee37770aac698133c4f9781fbe627a6ea47b1504fa6fee449b040368cb60f2f` |
| `/tmp/summoning-final-types.log` | `46a6c7834c9080ada23a415afd925abecc37d531f5c6e3d14ad0a7ff579096cb` |

No production/test changes, reviewer-run tests, external chat reads or external
chat messages occurred during this bounded closure review.


## Final independent native acceptance addendum (2026-10-03)

**Verdict: APPROVED for the final native ECS/anti-OOP/import-DAG scope. No
remaining concrete native blocker was found in this bounded final review.
Whole-delivery acceptance remains qualified by the separate final game and
artwork receipts; this is not a claim that the still-running game suite passed.**

Reviewed the unified plan, implementation ledger, this audit's previous native
approvals and the full anti-slop audit against the final native delta. Rehashing
the latest recorded entries in this audit found 33 of 39 native source/test
files unchanged. The six changed entries were inspected against their subsequent
reviewed contracts: actions, standard-action composition, Entity, Encounter,
retirement ownership tests and prepared-birth tests. The later amendment's
canonical creature/form/item data remain identical to its approved hashes.

The ordinary `Entity.compose_entity` convenience boundary now restores cleanup
only for an undeployed aggregate whose exact prepared birth UUID is absent from
the event index. An indexed birth remains authoritative if notification is
interrupted. The observed-birth test uses `KeyboardInterrupt` to reach that
actual escaping path; ordinary observer Exceptions are swallowed by the existing
queue, so the test does not pretend those Exceptions escape. Pre-completion
callbacks can already have run before indexing: this acceptance certifies the
indexed-fact boundary, not rollback of arbitrary callback side effects.

The explicit `prepare_birth` / `commit_birth` / `publish_birth` path remains
irreversible once committed. `SummoningSystem._commit` uses those exact APIs,
commits native condition/world/encounter ownership before birth publication and
continues the retained publications after errors. The corrected convenience
wrapper is not called by this committed summon path. Its AST source-segment
SHA256 is still `92fc1cd1db34635de46960bc025bd66907cfb3a14edd947e7928da1b84c53f07`,
matching the ordinary-birth correction reviewed in the anti-slop audit. The final
Entity field-description edit accurately describes commitment before publication.

Independently reviewed and accepted the two new autonomous-turn acceptance tests.
They create real summons with the existing fixture and invoke
`Encounter.advance_one_controller_action_boundary`, with no replaced AI policy
or manually selected summon Attack. The allied Wolf chooses and damages its
adjacent enemy while preserving adjacent caster HP and spending its normal action.
The released Fey first spends five feet through native Move, then retains its
same Entity, controller, execution UUID, remaining duration and remaining budgets
through actual concentration loss. Its normal controller chooses and damages the
former caster after faction reclassification. These checks close the concrete
controller-execution gap described by the anti-slop reviewer; they do not claim
an exhaustive tactical-policy matrix. Root independently ran the exact test file:
**2 passed in 2.34s**. This reviewer neither authored nor reran those tests.

The existing ECS owner split is preserved: canonical recipes own body/stat/attack
composition, passive form rows reference those recipes, native conditions own
existence/control/duration, and the high system holds native membership and
prepared-operation references. Passive summon event data contains IDs, choices
and provenance, not executable callbacks or copied creature state. The EventQueue
owns direct admitted system invocation; no parallel bus/registry was added.
Raptor remains ordinary canonical content at appearance scale 1.55. The other
13 larger beast scales remain cold values on the existing Appearance component,
without native size/occupancy changes or summon-specific rule duplication.

Reviewer-run static AST inspection covered the nine new native modules and
their 203-module `dnd` import closure. It found **zero import cycles**, zero
function-local imports or reflective calls in the nine new modules, and no
import of `dnd.summoning.system` from the checked lower Entity/Game/Encounter,
Action, event, block, condition, item or equipment owners. This is dependency
policy evidence, not a gameplay execution test. The retained JSON receipt is
`/tmp/summoning-final-ecs-static.json`.

Inspected receipts retain their precise scope: **2,531 passed plus one failed**
in the broad native run; the unchanged production owner with the corrected
post-scope assertion then passed **all 19** cases, reconciling the 2,532 collected
native checks. The progression/root/birth/summon regression run passed **336**;
the later indexed-birth file passed **6**; active dnd/game typing reports **zero
errors and warnings**. These are inspected execution receipts, not reruns by
this reviewer, and the later checks are not represented as a new broad run.

The final whole-game result must still be reconciled with the later presentation
changes on their actual source snapshots. Final original-shadow/scale/Fey visual
inspection and the implementation ledger's receipt merge also remain separate
completion gates. One documentation reconciliation was reported to root: the
paragraph after the creature table still listed pre-Raptor choice counts despite
the corrected section-2 table; current form data correctly gives Animals
7/10/14/16/17/18 at slots 3/4/5/6/7/8–9 and Fey 16/17/18 at slots 6/7/8–9.
No additional production design or scope is requested by this note.

### Final native review snapshot

These exact hashes identify this addendum's inspected bytes. A later document
receipt merge or later artwork change is not implicitly certified by them.

| Source or receipt | SHA256 |
| --- | --- |
| `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md` | `2037908ca8d4880bf61cf4dbc4afa98563c8da7e2a5f51ed35704b09cd7d36c6` |
| `dnd/entity.py` | `b8ed7d53b137a0bb9f9a81c672523908b81c17acb963bf9759962568118df82b` |
| `dnd/core/events.py` | `7bf91ba0330a9882a3b54c27c0d93d1cdba3c87806ce99c3b85b9ce986dbbf59` |
| `dnd/actions.py` | `2934d3374572188a6e152e5d6b042ddaa994ace500d2af249d181ddb4b2b2ad3` |
| `dnd/actions_functional.py` | `18dc90b1a9d795daf001194148682143c57fe701de40a198142dcf498c6a733a` |
| `dnd/encounter.py` | `71bc0ef26342e47e8faeb671b9d4f18c9d75583addabbecbdb869c4ea473576c` |
| `dnd/summoning/system.py` | `6d2dbbda64b924d3389da7848319c56ff521a93ffbccb2570c97009f5177e009` |
| `dnd/summoning/conditions.py` | `909880597f3a082bde34cdcc4ca35cf33e4d0f325329b91dd56ff62f1e3d22d4` |
| `dnd/summoning/actions.py` | `db5ded8cb35967b350a853adaa1759a22f2d2bb62eaf92e49adc4c5fa765110a` |
| `dnd/summoning/forms.py` | `64e17b956869d915f47d35aba694e5a031ae26c3aa884d4a91231c2c9a04140a` |
| `dnd/spells/summoning.py` | `a18ddb8c702f89986bff296507469e33efe98199d6f713177f110b05d8b158fb` |
| `dnd/types/summoning.py` | `861905da36883018471c12627f77acb9d5d3e76a9bc8a297e8fa56a42a443ed6` |
| `dnd/monsters/beasts.py` | `b1e5f333a1e6d0d95be749dd05d83aefec9c40dc682f63babd401b6cd52de15f` |
| `dnd/monsters/fiends.py` | `01850efda56fbbd4193d48578f87324d3745042708944f9882df24816fc26513` |
| `tests/engine/test_prepared_entity_birth.py` | `66f0aead6cd447330118c704d3329dd8b3e5773f1c0dd75cf137b911ecdf011d` |
| `tests/engine/test_summoning_autonomous_turns.py` | `4c3e0dbdcb353d38cde1e6bc78a8a42330f87f52e2cccae17272996d8ecd12dc` |
| `/tmp/summoning-autonomous-root-review.log` | `73c9079bcf0cf5962ac22b776dff3c79349392f5e91e036e959d4b069cd1a5a1` |
| `/tmp/summoning-birth-regression-fixed.log` | `682c54594eae5c7847a3e653a12e10b5a334aaa7780001c3a4de25f7e84969c6` |
| `/tmp/summoning-observed-birth-corrected.log` | `08677330b64a7f09506f9a0a0740c5ef87a70d15d31a580f66be55294a6ddb3d` |
| `/tmp/summoning-full-native-final.log` | `3713bfc5d9d46aec9362026882c5bdc8b338ebfe9295905338af0e42dbc228da` |
| `/tmp/summoning-silent-removal-corrected.log` | `353cd58b3ad0caa858f182bf3a57d300e83ba84a1c949b2ef3ae1580aae56988` |
| `/tmp/summoning-final-types-after-shadow.log` | `46a6c7834c9080ada23a415afd925abecc37d531f5c6e3d14ad0a7ff579096cb` |
| `/tmp/summoning-final-ecs-static.json` | `8f3e14b497037e6a1c4d43a9dfe7080b170d8f07476a4bb262940679321960c5` |

Only this audit was appended and the static receipt written. No production or
test files were edited; no gameplay suite was run; no external chat, thread or
artist was read or contacted by this reviewer.
