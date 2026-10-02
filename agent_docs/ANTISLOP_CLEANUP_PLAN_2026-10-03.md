# Cleanup plan: remove unnecessary machinery, retain requested gameplay

Status: proposed implementation plan; production edits and testing remain stopped.
Prepared on October 3, 2026 against HEAD
`3f2158f934f198f7edcb93f559fb1fda8b70e1f0` and the shared working tree.
The checkout contains accepted item work, the subsequent ability batch and
concurrent visual changes. HEAD is a comparison point, not a safe rollback target.

This supersedes the implementation structure and approval claims in the roster
ability plan, not the user's accepted gameplay choices. Evidence starts with the
[12-finding source review](audits/OVERALL_ANTISLOP_REVIEW_2026-10-02.md).
The event audit below and the
[whole-source event/rendering review](audits/RENDER_EVENT_CONTRACT_REVIEW_2026-10-03.md)
extend it. The latter confirms several ownership/timing workarounds already in
HEAD. Steps 5–6 now address those contracts, not just repeated walkers. No new
tests, gameplay probes or agent messages were run for this plan. Historical test
totals are not current acceptance.

This is a **replacement design and implementation plan**, not just a defect
register. The intended result is the following:

| Responsibility | Resulting design |
| --- | --- |
| Gameplay | Existing action/condition/item systems remain authoritative. Remove rejected ammunition machinery; retain the agreed spells/powers through existing owners and shared execution. |
| Movement | One resolved speed/budget contract, read without mutation. Walking and ground-to-ground flying spend through the same existing Move path. |
| Items | Cold recipes plus composable supported properties; semantic weapon kind/material; possession-owned charges and coatings. No per-variant executor or universal ammunition hooks. |
| Native events | One committed operation/result with explicit causality and instance ownership. Preparation, committed change and presentation time have distinct meanings. |
| Player contract | Typed permitted facts with complete valid result variants, existing action/application/owner references and source order. No private engine object is needed to interpret them. |
| Presentation | One causal index and existing choreography compiler bind results to authored milestones; shared primitives sample them. Lifetime consumers traverse that same compiled timing. |
| Portability | The actual player/authoring schema is exportable; Pygame remains an output adapter. No second recipe language, scheduler or gameplay implementation. |

Each numbered implementation step below names what replaces the old code, what
must be deleted, and its exit contract. The completion table accounts for every
finding in both audits. Documenting a defect, moving a file, adding a type beside
an unchanged workaround, or recording a passing narrow test does not close it.

## 1. Decisions

The user explicitly confirmed on October 3: **keep the six requested spells and
three backpack powers; clean their implementation.** Do not quietly drop Fly or
the powered items to make the refactor easier. The new ammunition integration is
removed. Special-arrow mechanics are not reintroduced under another name.

| Keep | Remove or exclude |
| --- | --- |
| Produce Flame, Shillelagh, Longstrider, Barkskin, Fly, Fire Shield, with the previously agreed rules | The task-owned runtime module `spells/roster_support.py` and dependencies on it |
| Ember Quiver, Wayfarer's Pack, Warden's Pack; one item-owned use per long rest | Ammunition inventory requirements, arrow selection/payload plumbing in Attack/Multiattack, the four new arrow builders and their public admissions |
| Accepted item recipes, 113 appearances, psychic/ember properties, palette replacement/bloom and the BACKPACK slot | New weapon art, quiver compartments, ordinary ammunition consumption, firearm proficiency, specialist focus/tool simulation |
| Item-owned coatings surviving unequip/drop/loot; actual held and ground item identity | Generic item callbacks whose only purpose is the rejected ammunition feature; private coating imports between unrelated item modules |
| Existing creature/object Attack path and every accepted attack budget | A second AttackObject/UseArrow executor, creature-specific branches inside generic Multiattack, new attack resources |
| Selected Magic Resistance, innate Invisibility, innate flight and Wight Life Drain | Additional invented signature abilities, grapple/drag/hand-reservation work, zombie creation, new boss/legendary systems |
| Existing shared conditions and ownership/removal events | Per-roster copies of standard conditions; concrete spell inheritance used as a generic capability |
| Accepted walls, cloud propagation, XYZ/visibility rules, window traversal and destructible props | Another cloud/wall compositing experiment, new movement animations, multi-Z/hovering/falling, scenario or UI redesign |

Removing arrow admissions must not erase possessions from an existing save.
Preserve the source data and saves; provide an explicit unsupported-content
diagnostic at admission for the four retired IDs. Do not silently turn them into
ordinary arrows, delete them from inventories or retain a hidden active executor.
The three powered backpacks are separate from these retired consumables.

The scope is the defects and unnecessary mechanisms named here. It is not a
rewrite of all 542 previously inspected modules, all content, or the paused server.
An adjacent defect is recorded for discussion rather than silently added to the
implementation. Existing failing game contracts cannot be concealed as success.

### Backend versus presentation scope

| Layer | Findings and correction boundary |
| --- | --- |
| Backend rules/state | The earlier review's split/mutating movement state, item eligibility/coating ownership, generic attack coupling, resource consumption/recharge/stale operations and duplicate concentration publication. These concern engine behavior independently of drawing. Preserve the agreed rules while correcting their implementation. |
| Native-to-player contract | Missing application/owner/commit references and incomplete result variants. First use existing native identities and facts. Change a producer only where a required relationship is genuinely absent; otherwise fix projection/types. An incomplete client packet does not by itself prove incorrect native gameplay. |
| Rendering/presentation | Recipe-dependent result ownership, target/time association, one-packet binding limits, formation-specific sensory splitting, repeated timing/traversal and inaccurate capability reporting. These mostly account for R1–R9 and belong in client binding/choreography/data admission. |
| Dependency/portability | Passive schema ownership and export of the actual player contract. This is architectural preparation, not a gameplay defect or authorization to revive the server. |

R5's commit-cursor workaround and several other source findings are design risks,
not newly reproduced engine failures. Every implementation change must identify
which layer is wrong; a visual symptom does not authorize unrelated rule changes.

## 2. Rules for the resulting design

1. **One owner for each fact.** Item identity/charges/coatings belong to the item;
   speed and movement expenditure to action economy; effect lifetime to its
   native condition; presentation time to existing choreography.
2. **Content supplies data to existing execution.** A new recipe does not require
   a new executor. An existing condition applied by a different spell is still
   that condition. A truly different effect can have its own implementation.
3. **One authoritative event operation.** Projections describe committed native
   changes. They cannot cause damage, consume charges, infer a cast or repair
   native state. Native events are recorded once and replayed without mutation.
4. **No parallel public answers.** Discovery, execution, snapshots and replay
   must agree. Compatibility at file input is allowed; a second live state model,
   duplicate scheduler or a proxy hiding contradictory values is not.
5. **Dependencies point toward shared data and mechanisms.** No late imports,
   circular imports, gameplay `getattr`, class-name switches or runtime type
   probes used to disguise a missing contract. Boundary validation of a declared
   typed union is different from guessing what capabilities an object has.
6. **No general framework without a current need.** No universal effect language,
   feature registry, transaction manager, modifier scripting engine, new moment
   resolver or sweeping file reorganization. Every addition below replaces named
   code or fills a specific missing contract.

## 3. Final ownership and imports

| Responsibility | Destination | What disappears |
| --- | --- | --- |
| Produce Flame and its retained light/hurl/dismiss | `dnd/spells/conjuration.py` | Its entries in `roster_support.py` |
| Shillelagh, Longstrider, Barkskin, Fly and spell-owned effects | `dnd/spells/transmutation.py` | Same; imports from creatures/items into the task module |
| Fire Shield and retaliation/light/dismiss | `dnd/spells/evocation.py` | Same |
| Shared flying traversal | Existing `Move` implementation in `dnd/actions.py`, selected by movement mode | `action.spell.fly.move` as the identity of innate traversal; duplicate spell/class traversal bodies |
| Reusable creature traits and natural attacks | `dnd/monsters/traits.py`; authored choices in existing monster content | `monsters/roster_abilities.py`; Wight content embedded in generic Multiattack |
| Wearable finite-use spell capability | Existing `dnd/items/spell_items.py`, equipment and usable-item composition | Backpack-specific admission overrides; `BaseBlock.permits_use_by` |
| Three powered-item recipes | Cold definitions under `dnd/content/items`, through `build_authored_item` | Positional recipe tuples and builders mixed with mechanics in `roster_carried_powers.py` |
| Shared timed weapon coating | Existing item-effect owner, with one public application contract | Import of `_TimedFireWeaponCoatCondition`; any duplicate quiver coating implementation |
| Passive world-binding schema | One passive schema owner consumed by `assets` and `animation_data` | Raw JSON passthrough and repeated section admission |
| Resolution/application/result relationships | Existing native provenance and typed player facts, using existing lineage/application IDs | Recipe-dependent ownership, target/time matching and single-packet assumptions |
| Observed change identity and commit order | Existing event versions and subjective projection | Formation-only synthetic sensory nodes and inferred commit phases |
| Shared presentation timing | Existing choreography/compiler and authored milestones | Repeated independent retiming of state, injury and feedback |
| Timeline nesting/absolute offsets | One walker beside existing choreography | Four copies of movement/reaction recursion |

Keep `content/items/roster_item_definitions.py` where it is useful as **cold
source-grouped data**. The word “roster” is not itself a bug; runtime dependency
ownership is. Do not replace three task buckets with one giant `support.py`.

Import direction after the change:

```text
passive dnd/types + dnd/core data
    <- values / item / action-economy mechanisms
    <- entity + existing action execution
    <- spell schools / creature traits / usable-item mechanisms
    <- content registration and builders (composition boundary)

native event + snapshot contracts
    <- observer projection and player facts
    <- reduction and choreography
    <- lifetime policies and drawing

passive world-binding types <- asset and animation loaders
```

Arrows mean “is imported by”. Core mechanisms cannot import the content builder
tables. Creature traits cannot import concrete spell effects to obtain movement.
Rendering cannot consult live native registries to fill missing recorded facts.

## 4. Ordered implementation

Each numbered step is a reviewable change with a removal result and a behavior
boundary. This is an execution sequence after approval, not permission to stop
after moving a file or passing one focused test.

### Step 0 — preserve and establish the exact starting state

- Save tracked diffs, untracked source/doc files, HEAD identity and a file-hash
  manifest outside tracked production content. Include accepted item work; do not
  copy private artwork into Git or modify asset storage/history.
- Mark the exact files/hunks belonging to this cleanup. Re-read a shared file
  before editing it; concurrent visual edits are preserved, not overwritten with
  a stale copy. Agent communication remains restricted to the two requested
  independent plan reviews once the plan is finalized; other coordination stays
  stopped.
- Record retained content IDs and the four retired arrow IDs. Keep previously
  reported failures separately from unverified risks. Preserve existing replay
  inputs as evidence; do not overwrite old recordings with new output.
- Do not reset to HEAD: it predates accepted work this plan must retain.

Exit: a recoverable source snapshot and a bounded change list.

### Step 1 — remove ammunition expansion completely

Remove `AttackAmmunitionPayload`, `AttackAmmunitionMetadata`, selected-ammunition
fields on actions/events/discovery, Attack/Multiattack arrow discovery and release
branches, and ammunition wrappers on `BaseItem`/`UsableItem`/`BaseAction`.
Remove the four new arrow recipes from canonical builder/content admission.
Remove `supports_arrow_payload` after replacing its remaining quiver eligibility
consumer with the semantic weapon contract in Step 2.

Primary files: `dnd/core/attack_types.py`, `dnd/core/base_actions.py`,
`dnd/blocks/base_item.py`, `dnd/blocks/equipment.py`, `dnd/actions.py`,
`dnd/monsters/traits.py`, `dnd/entity.py`, item definitions/builders and their
projection/registration references.

Delete the new `_commit_release_costs` hook if ammunition was its only consumer.
Do not remove finite usable-item charges: scrolls and powered gear still need
them. Do not revert all of `BaseAction.apply` indiscriminately; Step 5 specifies
the retained item transaction and interruption boundary.

`damage_payloads.py` cannot be deleted blindly: Basic Poison also uses it.
With arrows removed, put the exact poison helper back with its existing coating
owner if no other consumer remains. Keep Basic Poison's accepted behavior.
Remove arrow-only profile fields only after checking surviving consumers.

Exit: ordinary ranged attacks require no ammunition; no rejected selection route
remains in discovery, Multiattack, serialization or replay. No new attack route.

### Step 2 — make item eligibility semantic; retain functional authoring

Add the minimum passive weapon facts to the existing definition/runtime records:
weapon kind and material, using existing material vocabulary where compatible.
Keep three identities distinct: recipe/content ID, possession UUID, weapon kind.
Author these facts on base recipes; functional transforms preserve them unless a
transform explicitly changes the relevant fact. No parsing names or sprite IDs.

- Shillelagh checks held club/quarterstaff **and wood**, then revalidates the exact
  possession at application. A named/enhanced wooden staff remains eligible.
- Ember Quiver checks bow/crossbow kind and the exact equipped ranged possession.
  It grants a fire coating, not arrows or an ammunition supply.
- Multiattack's eligible longsword replacement uses weapon kind, not
  `item_id == 'weapon.longsword'`.
- Do not add weapon-specific booleans to `BaseItem`, scenery or `BaseBlock`.

Replace Multiattack's four loosely related substitution fields with one complete
optional, typed replacement choice: eligible sequence entry, weapon predicate,
replacement action and maximum replacement count. Validate the whole choice at
authoring. Derive its label/profile from the selected action; delete the literal
“Life Drain” label from the generic mechanism. Wight content supplies that choice.
Children continue through ordinary Attack, with the existing single Multiattack
cost and no new Extra Attack/Haste eligibility.

Exit: a new named longsword/staff uses the same eligibility rules as its base;
generic Multiattack contains no Wight identity and still has one execution path.

### Step 3 — replace the split movement representation, without new movement rules

Correction to earlier discussion: **`current_speed()` already existed at HEAD.**
The batch replaced its simple query with copying, mode substitution, mirrored
factor bookkeeping and cleanup during reads. Renaming that code is not a fix.

Keep action economy as the owner. Separate **speed** from **feet spent this turn**
inside that existing component. They are different facts, not duplicate pools:

| Fact | Authoritative representation |
| --- | --- |
| Walking/flying speed | Existing modifiable-value mechanism, one value per supported mode |
| Source-owned flight permission/base speed | One owned grant collection; no duplicate grant on the actor or action template |
| Speed changes | Existing owned modifiers; one arithmetic contribution per effect per applicable mode |
| Movement already paid | One shared expenditure ledger, independent of mode |
| Dash | Explicit turn-owned credit/count through the existing Dash action |

The old `movement` value must not remain a writable second answer to remaining
movement. Migrate its consumers to the explicit speed/budget contract in the same
step. Legacy input may be decoded once; no live compatibility proxy with different
arithmetic and no second serialization of the same remaining distance.

Concrete boundary: `current_speed(mode)` reads the mode's value;
`movement_remaining(mode)` derives its unspent budget; movement admission and
commit use that same budget. Spending records actual feet, not a negative speed
modifier. Dash grants are turn state, not modifiers identified by the display name
`Dashing`. Turn reset clears expenditure and Dash, not persistent speed effects.
Existing creation settings still initialize base walking speed at input.

The existing numeric value implementation supports sums and constraints, but not
the multiplicative speed contributions currently simulated by mirrored entries.
Add one owned, typed arithmetic factor to that existing value mechanism, with
exact ratio data for 2 and 1/2, normal UUID cleanup and a documented evaluation
order: additive speed, factors, bounds, integer normalization. Default identity
factors leave all unrelated values unchanged. Do not introduce a parallel speed
modifier framework, per-spell evaluator or callbacks named after Haste/Slow.
All value combination/removal/snapshot paths must support this one operation;
adding it to just one aggregation branch would repeat the current defect.
Apply the factor to the complete additive value, not separately inside one
channel; the existing self/contextual/imported contributions must participate in
the same calculation. Remove by the normal owned modifier UUID. Audit the full
numeric-value callers when verifying this change; this is not a Fly-only patch.

Flight grants determine the mode's base at grant/removal transitions. Their
effective base is derived by the owning component from admitted grants, not
independently authored twice. Removing one grant preserves another. Longstrider
and speed factors also apply when a flight grant is installed after those effects.
An inactive mode does not become usable merely because it has a speed bonus.

Queries are pure: no deepcopy, registry pruning, condition cleanup or repairing
missing owners while reading. Remove `movement_speed_factors` and the ordinary
numerical/cap copies that represent the same factor. Removal uses normal source
ownership. Source grants are released on committed effect removal, never on a
failed/vetoed removal.

Keep one definition of remaining feet for mode switching and Dash. Under the
currently implemented mode-switching policy it is the mode's effective speed,
including Dash credits, minus shared expenditure, floored at zero. No reset on
mode switch. Ordinary Move, Jump/crawl, path admission, reactions, discovery and
snapshots all consume the same result. Attack counts, actions, bonus actions,
reaction resources and spell slots keep their existing owners and policies.

The required writer migration includes Haste, Slow, Exhaustion, immobilizing
conditions, Dash, Longstrider, Dragon Wings, Fly, innate flight, origin/class speed
grants, contextual Barbarian speed, transforms, existing speed-reducing spells,
field-focus and circus traits. Readers include `actions`, `actions_functional`,
`entity`, `encounter`, action-economy costs and recorded actor stats. This is not
finished by fixing only Fly's tests.

Flying traversal becomes the existing mode-aware Move capability. Spell, innate
trait and Dragon Wings supply ownership and speed; none inherits another one's
spell identity. Supported ground-to-ground legs, walls/doors, path interruptions,
hazards and reactions keep their agreed rules. No hovering, multi-Z, falling,
flight immunity or new animation contract is added.

Exit examples: walking 30 + Longstrider 10 + Haste yields 80 everywhere; adding
Slow yields 40. Walking 30/flying 60 after spending 20 feet reports 10/40 remaining.
Zero-speed conditions still prevent movement; expiration removes only its owner.
Repeated reads cannot alter serialized state.

### Step 4 — relocate retained effects and simplify item composition

Move the six spells to the school owners in Section 3, preserving content IDs,
provenance, durations, target selection and media bindings. Update canonical
registrations/imports, then delete the old module; do not leave re-export shims
for this uncommitted structure.

Keep spell-specific effects when they express distinct gameplay. Remove tiny
task-only wrappers where the existing application/removal API already expresses
the operation. If shared effect installation is genuinely needed by multiple
schools, put the one operation on the existing SpellAction mechanism, preserving
condition admission, concentration ownership and failure cleanup. No new effect
executor or per-character standard-condition types.

Move selected creature capabilities to existing trait ownership. Innate
Invisibility composes the existing Invisible/Concentrating behavior; Magic
Resistance uses actual magical provenance; Life Drain uses ordinary attack,
damage, maximum-HP and condition-state contracts. Keep its agreed max-HP behavior,
but add no zombie creation, regeneration or extra riders.

For powered equipment:

- Put the three named recipes in the cold item definitions; use the existing
  canonical builder and finite spell-granting item mechanism. Retain existing
  equipment identity and owned actions rather than a backpack-specific executor.
- `PoweredBackpack` currently combines existing item capabilities; it is not
  evidence of a second spell executor. Retain that composition where needed as
  one reusable spell-granting wearable type in `spell_items.py`, with slot and
  action templates supplied by data. Delete its bespoke action mutation and
  permission overrides; no per-recipe subclass or new wearable hierarchy.
- Use a complete typed source-use requirement on the existing item-use contract
  (equipped in BACKPACK here). Admission and release revalidate it through the
  item/equipment domain. Delete `BaseBlock.permits_use_by`; unrelated blocks do
  not acquire a permissive placeholder hook.
- Share the exact existing fire-coating application/lifetime through a public
  item-effect operation. No import of a private consumable implementation.
- Long-rest recharge remains item-owned. Unequip/drop/loot cannot recharge it.
  Ordinary quivers and canisters remain ordinary gear without implicit powers.

Exit: delete `roster_support.py`, `roster_abilities.py` and
`roster_carried_powers.py` after consumers have migrated. Retain the six spells,
three powers and selected traits; no new item registry or standard condition.

### Step 5 — repair event ownership at producers and consumers

Use the source audit and operation contracts in Section 5. This step must not
be reduced to deduplicating rendered effects after receiving bad native facts.
It also owns the schema corrections for R1–R7 of the rendering review. Implement
each changed producer/projection/consumer boundary as a complete migration with
step 6; do not leave an intermediate client guessing at partially migrated facts.

- Keep one finite-item resource operation. Preparation is not consumption.
  Terminal commit is once per resource-operation lineage; a prepared stale event
  cannot become valid again after a recharge restores the old numbers.
- Give every prepared operation an explicit terminal result: completion or
  cancellation. A canceled parent cannot leave an indefinitely ready preparation;
  completed child operations retain their committed results.
- Keep existing action-cost timing: rejected admission spends nothing;
  interruption after committed action expenditure retains that expenditure.
  Resource admission/commit cannot mint, refund or independently spend attacks.
  Item removal/ownership changes during handlers are revalidated before use.
- Remove ammunition-only staging; retain only the item-resource staging actually
  needed for ordinary finite-use actions. Do not add a second transaction ledger.
- Model consumption/recharge as explicit operations in the existing resource
  event family; migrate all consumers together. Preserve the existing wire event
  identity for historical records, with the old missing operation meaning consume.
  Name/document the shared family as a resource change internally; do not publish
  both an old and a new event for one mutation.
- Publish actor concentration state once after each committed owner mutation,
  only when its observable snapshot changes. Condition removal still produces
  its proper removal event. Floor-item ownership continues through item location
  snapshots. Delete unconditional duplicate publishers at call sites.
- Carry actual construction owner UUID and concentration slot identity into
  recorded facts where required. These IDs already exist in native ownership;
  they are not new rule systems. Remove geometry/name matching as ownership.

Event UUID, operation lineage, parent lineage, target and packet identity have
different meanings. `phase_to` creates event versions; checking only the prepared
version's UUID does not prove its operation was not committed. Use the existing
event history/lineage contract, not a new event bus or global dedup cache.

#### Cancellation and the existing finite-item release boundary

Cancellation belongs to the concrete operation and phase, not an automatic
rollback of its ancestry or descendants. Preserve the existing finite-item
release point in `BaseAction.apply`: after execution-handler/access revalidation,
before applying the item's effects. This cleanup does not change that policy.

| Exit point | Action cost | Finite-item charge | Effect results |
| --- | --- | --- | --- |
| Admission rejected before costs | Not spent | Not spent; cancel any still-pending preparation | No effect was executed |
| Interrupted after action expenditure but before item release | Remains spent | Not spent; cancel still-pending preparation | Preserve any independently completed handler results |
| Item release vetoed or revalidation fails before resource commit | Remains spent | Not spent; resource operation terminates canceled | No item effect is started |
| Item release commits | Remains spent | Spent exactly once; resource operation completes | Item effect may now execute |
| Later effect admission fails or the parent cancels | Remains spent | Already committed consumption remains | Preserve completed child results; cancel only outstanding preparations |

For example, a coating application veto after Ember Quiver's release retains the
committed charge; it does not create an implicit refund rule. Obvious admission
errors still fail at the existing earlier checks. A canceled damage request and
an already committed `DamageAppliedEvent` likewise have different meanings.

`BaseAction.apply` owns closing the item preparation it created on each exit.
`_commit_item_charge` owns that child's terminal resource transition; the item
owns the charge mutation. Cleanup checks the existing operation history and
closes only a still-pending child. Do not put whole-tree cancellation/refunds on
Event, EventQueue, Entity or a new transaction manager.

For nested condition teardown, use the existing prepared-removal/commit boundary:
capture the affected owner snapshots, perform admitted link/slot mutations, then
publish changed surviving owners once. Internal unlink helpers do not separately
publish the same batch mutation. Direct single-slot operations use the same
boundary. Compare the recorded condition/state-and-stats payload, not just a
condition's name or duration. This avoids a new global transaction manager and
does not defer unrelated real changes until the end of a whole game lineage.

#### Typed resolution and committed-change contract

Keep `PlayerSequence`, `PlayerNode`, the fact union and the existing version
rows. Strengthen their meanings rather than introducing a parallel event model.

The following are chosen contract shapes, not alternative approaches left for
implementation:

- A resolution reference has two variants: an **event resolution**, naming its
  owning existing lineage, or an **application resolution**, naming that lineage
  and its existing application ID. Event resolution covers attacks, independent
  reactions and environmental operations without pretending all causes are
  spells. An undisclosed cause is explicitly absent, not an invented root.
- Cast application membership is a complete record (owning cast lineage,
  application ID, index); the cast root has no application membership. Replace
  independently nullable membership fields with this all-or-none record.
- The damage fact family has request and committed-result variants. Result
  references are an ordered tuple under an application. Keep the native result
  payloads as the single source of their values; do not copy HP totals into a
  second authoritative result model.
- Observed components refer back to an existing source event and typed changed
  field/owner. A component has one causal reference and one native source-order
  position. The compiler consumes these references; it does not fabricate
  partial sensory events with the same event UUID. Add components only for
  independently committed changes; an indivisible committed change remains
  indivisible.
- These records are passive data owned by the existing event/player contract
  layer. They have no `apply`, rendering, dispatch or lifecycle methods. Indexes
  contain references into the received sequence, not another mutable state.

The producer-to-reference mapping is fixed as follows. Origin identifies what
established an effect; trigger identifies what activated it now; resolution
identifies the particular operation whose results are being presented. They are
not interchangeable.

| Producer | Resolution owner | Origin/trigger retained separately |
| --- | --- | --- |
| Ordinary weapon/unarmed/natural Attack, including object target | That existing Attack lineage | Existing source item/effect provenance and causal parent |
| One spell application, including repeated targets | Owning cast lineage + existing application ID | Existing cast origin and parent structure |
| Fire Shield callback retaliation | The retaliation's own existing `TakeDamageEvent` lineage | Incoming hit remains its trigger/parent; the earlier shield cast remains effect origin |
| Damage during field creation | The actual creation cast application when present, otherwise its existing creation operation lineage | Field instance from `SpatialDamageSource`; actual creation cause |
| Later persistent-field entry/turn exposure | That exposure's own existing damage-request lineage | Triggering movement/turn operation, spatial field instance and original effect provenance |

Mark an independent callback/exposure resolution when the ordinary damage
request is created, and carry that reference into its committed result. The
shared damage path transports the typed relation; it contains no Fire Shield,
spell-name, damage-type or reversed-source/target inference. This requires no
synthetic retaliation AttackEvent or new identity generator. Projection retains
only disclosed references and removes hidden origin/trigger links independently;
the result can remain visible when its cause is unknown. A renderer never falls
back to the incoming attack or the historical shield cast as retaliation owner.

1. **Resolution ownership:** name the action/application that owns a result.
   Reuse event lineage and `application_id`; do not generate a second resolution
   UUID. A reference to an action and a reference to a particular application
   are distinct typed variants. An application reference contains its owning
   action lineage and application ID together. Where typed existing ancestry
   already proves this relation, index it once; where it does not, the producer
   records the missing link through existing provenance. The public projection
   strips undisclosed causes rather than revealing their identities.
2. **Root versus application:** validate the existing cast cases so an
   application cannot carry an ID without its index/owner or pretend to be the
   cast root. Retain the explicit distinction between no disclosed result and
   a resolved empty area. Conditions, items and environmental effects use the
   same causal reference where applicable, not new per-content event classes.
3. **Requested versus committed damage:** give the existing fact family typed
   stage variants. A committed identified-target result requires its actual
   damage and resulting normal/temporary HP. An interruptible request does not
   contain invented committed values. Misses, saves, prevention and cancellation
   remain their actual outcomes, never fabricated zero/positive damage events.
4. **Result collection:** one application can reference multiple committed
   results, each with its own native identity/order. Retaliation belongs to its
   actual resolution. Body reaction, numbers and HP projection must not consume
   the same result twice. Feedback may group related values visually without
   collapsing native commits or dropping intermediate resulting state.
5. **Observed changes:** distinguish an operation's completion from its state
   commit using the existing version/source cursor. A sensory batch containing
   changes from different causes exposes individually referenceable components,
   identified by source event + field/owner, with their permitted causal links.
   Do not emit duplicate native events or create anonymous synthetic event UUIDs.
   Preserve existing source order inside every presentation milestone.
6. **Instance ownership:** carry construction owner/section and concentration
   slot links already present natively. Type incomplete/undisclosed references
   explicitly; do not backfill them from geometry, content names or later state.

No field in this contract carries a sprite, animation recipe, frame, visual
duration or Pygame value. `EffectOrigin` and `SpatialDamageSource` retain their
existing gameplay meanings; an art-binding flag must not be added to them.
Source links must survive a missing visual binding without reparenting results.

The present sensory producer records one batch cause and a before/after delta;
that is not automatically sufficient component provenance. When separate causes
were coalesced, retain the actual cause/version at the native mutation or refresh
boundary before coalescing. Projection may then filter and reference those
components. Do not relocate the existing formation/ancestry heuristic into
projection and call it typed provenance. A component's disclosure cannot be
moved earlier than the observation that actually granted it.

The target public schema is version 2 when incompatible required fields land.
Keep a single input migration from version 1 where existing facts/version rows
determine the answer. Never consult current live entities or asset availability
to reconstruct history. Preserve original recordings. If a legacy packet lacks
the necessary provenance, diagnose that precise ambiguity; do not guess an owner
or mark its playback as passing. Where the preserved native recording supplies
the missing relationship, reproject through the same observer-permission rules.

Move only public passive declarations currently imported from runtime modules
to existing dependency-leaf type owners as required. Native events and player
facts then import one shared definition. No duplicate enums, mirrored transport
classes for every engine object, late imports or client dependency on concrete
spell/item implementations.

Exit: one terminal mutation per operation, accurate consumer interpretation,
preserved causal parentage, validated result variants and explicit instance/
application links. No renderer-created gameplay events.

### Step 6 — make event digestion explicit, then remove duplicated presentation work

The previous walker-only version of this step was insufficient. The resulting
path stays within the current client:

```text
native committed facts and causal references
  -> observer-permitted PlayerSequence
  -> pure state reduction + one causal/version index
  -> existing recipe binding + existing choreography compiler
  -> shared sampling/lifetime policies
  -> Pygame drawing adapter
```

**6a. Bind from semantic ownership.** Migrate `attack.py`, `combat.py` and
`choreography.py` to the step-5 relationships. Build the causal/version index
once per received group. Remove `behavior_id in data.drafts` as a test of who
owns damage; it remains valid for selecting available art. Replace the target +
floating-point arrival-time search with the application reference. Extend the
existing bound application data to retain its ordered results, and remove the
one-positive-packet restriction. Keep shared creature/object Attack routing.
An unknown cause still permits presentation of a disclosed result without
inventing its unseen source. A missing recipe records a gap, not a new owner.

**6b. Schedule once from authored milestones.** Retain the existing release,
contact, formation, movement-arrival and destruction-clear timing primitives.
Resolve a result's placement from its causal/application reference and the
relevant authored milestone. Derive injury, feedback and displayed committed
state from that one placement, preserving native order for linked changes.
Remove the `formation_starts`/`formation_senses` node-splitting repair and
independent retiming passes as their callers migrate. This is consolidation
inside existing choreography, not a new moment resolver or scheduling service.

Mechanical sequencing and presentation duration remain separate. Multiple
targets from the same formation may play together when their causes permit it;
distinct turn-end triggers are not made simultaneous just because they share
an effect name. A camera change, slower clip or missing art changes no cause,
outcome or permitted observation. World destruction/formation changes become
visible at their proper shared milestones without showing a future footprint
at frame zero. Keep current movement visibility behavior throughout.

**6c. Share resolved traversal, retain distinct lifetimes.**

Extract one typed iterator over existing BoundChoreography/MotionTimeline nesting,
including reaction children, carrying absolute offsets and native event identity.
Use it in condition, spatial, concentration and construction lifetime registration.
The walker only traverses already-bound timing; it does not decide damage time,
recalculate release/arrival, bind media again or create another schedule.

Keep distinct lifetime policies: condition membership, spatial observation,
concentration slots and construction sections are different owners. Share the
walk, not a giant policy switch. Delete old recursive walkers after migration.

**6d. Admit presentation data once and report actual capabilities.**

Use one typed world-binding source document, decoded once per asset-data load.
`assets.py` already imports passive `animation_types`; reuse the concrete media
binding types. Extract the existing world-source declarations into a passive
schema module only as needed to avoid a loader-to-loader dependency. Both loaders
consume that admitted document. Remove JsonValue placeholders, raw rereads and
independent section-name allowlists; do not weaken `extra=forbid`. The admitted
world-source document retains the existing `WorldBindingsSource` definition,
moved into passive `game/world_binding_types.py` and completed with concrete
existing section types. `assets.py` and `animation_data.py`
consume it; neither loader imports the other to obtain schema definitions. This
replaces their duplicate admissions rather than adding a third loader. Move
`PropAnimationSource` and its passive nested source declarations there too;
do not import them from runtime `world_animation.py` into the passive schema.
Keep conversion to runtime `PropAnimation` in the existing conversion owner.

Preserve the Studio/local recipe vocabulary; do not move Python special cases
into a general JSON program. Supported primitives interpret declared fields.
Capability reporting reads the admitted fields/media, not a fixed historical
sentence about all wall modules. An unsupported requirement in a selected active
recipe fails admission. Historical, inactive imported vocabulary may remain
archived without an executor. A missing binding for an otherwise valid received
action produces a precise presentation gap while its facts still reduce; it
does not authorize a partial interpretation of a selected unsupported recipe.
Parsed vocabulary is not reported as an implemented visual. No new artwork or
rendering primitive is required solely to make unused schema fields executable.

Preserve the three already accepted potion source-strip omissions (healing,
haste, greater invisibility): the admitted local recipe explicitly omits that
optional strip, while the original import and omission receipt stay preserved.
Body/effect timing remains active. This is not permission to ignore arbitrary
required fields; report these exact omissions as omissions, not implemented art.

**6e. Make the current contract exportable.** Add a generated schema entry point
for the current `PlayerSequence` and admitted presentation data, independent of
the paused server SDK. Reuse existing generation machinery only where it fits
without importing server runtime. Record version, units, ID/union/null semantics,
source order and deterministic sampling rules in `PRESENTATION_CONTRACT.md`.
Use fixture expectations for the public records and semantic cue times, not
Pygame object serialization. The TypeScript client itself is future work.

Keep `DrawCommand` as a local raster output. Portable input is the player facts
and presentation data; shared cue records describe IDs, transforms and timing.
Do not create a second network protocol carrying pixels or serialize every
internal Python cache as a supposed portable model.

Retained source changes must not regress accepted formation-before-damage,
item transfer, movement visibility, window traversal or wall/cloud compositing.
Unknown observation is not deletion. Retirement is driven by witnessed removal,
not absent visibility, wall geometry coincidence or the final state painted
backwards through an entire movement clip.

Exit: no recipe-dependent ownership, target/time association, one-packet binding
limit, formation-specific synthetic node splitting, geometry-derived ownership
or duplicate lifetime walks. One schema admission and one documented compiler
path, with existing accepted visual behavior preserved.

### Step 7 — remove reflection at the affected discovery boundary

Replace the concrete spell-field `getattr` probes in `Entity` with an action-owned,
typed discovery description. Reuse existing outcome/setup/effect profiles for
their present meanings. Runtime cast level/variant information must come from
the action, not guesses from a catalog default or a class-name branch.

Put the passive description beside existing action types. Entity consumes it;
the implementation that knows the action supplies it. Do not add a separate
`get_*` method for each future spell/item feature or replace reflection with a
growing `isinstance` chain in Entity. Spell schools must not be imported by Entity.
This is the concrete discovery boundary in finding 9, not a promise to rewrite
all 155 historical reflection sites regardless of purpose.

Exit: the affected actions have identical descriptions in discovery/execution;
no silent fallback hides missing required data.

### Step 8 — verify and close, after implementation is authorized

Use [HOW_TO_TEST.MD](../HOW_TO_TEST.MD). Tests enter through public commands,
content admission or recorded facts and assert visible results; they do not
freeze private helpers. Architecture checks protect the separate import policy.

Run the focused contracts in Section 6, then the complete engine suite, game
suite, affected typing and architecture checks once the shared source state is
stable. Record exact revision/diff and environment. If concurrent edits change
that state, label the result precisely rather than claiming a combined pass.

Classify every failure: a regression to fix here, a previously reported failure,
or newly discovered work needing discussion. Do not silently weaken expectations,
exclude failing game tests, or dismiss defects because they predate this change.
The paused server remains a separately reported inactive integration, not a new
server repair project.

Only after native/replay checks, use the existing in-engine gallery for a small
acceptance set covering retained features and repaired timing. No new preview
site format, shader experiment, art job or screenshot-only completion claim.

Update the recovery checkpoint once with the actual removals, retained behavior,
verification and remaining disclosed issues. Historical “approved” paragraphs
must not supersede this evidence. No automatic commit, push or branch rewrite.

## 5. Event audit and required contracts

The [rendering contract review](audits/RENDER_EVENT_CONTRACT_REVIEW_2026-10-03.md)
adds R1–R9 across current and committed source. Its strongest findings are
recipe-dependent resolution ownership, time/target association, insufficient
result variants/cardinality and formation-specific sensory splitting. The
following E1–E6 remain applicable; they do not exhaust the event cleanup.

### Findings established from source

| ID | Evidence | Required change |
| --- | --- | --- |
| E1 | `UsableItem.on_long_rest` emits `ItemChargeConsumptionEvent(resource_change='recharge')`; `analytics/game_summary.py:1030` counts every completion as spent | Keep one resource family; every consumer distinguishes mutation kind where relevant. Actor/item snapshots consume actual after-state; analytics counts only real expenditure. Confirmed interpretation mismatch, not a freshly executed test. |
| E2 | `commit_prepared_charge` checks item/charge/stack equality but not prior terminal completion of that operation | Enforce one terminal commit and close canceled preparations. Equality alone is not an operation identity. Reusing a stale preparation after balances return is a source-level risk; no ordinary-play reproduction claimed. |
| E3 | `Concentrating.drop_slot`, `unlink_condition` and `SpellAction._cleanup_concentration` can all publish owner state; cleanup publishes unconditionally | One commit-boundary publisher per actual owner change. Nested teardown must not publish duplicate unchanged snapshots. Preserve real intermediate changes. Confirmed overlapping responsibility; exact duplicate counts have not been measured here. |
| E4 | Native `WallSection.wall_owner_uuid` exists, but presentation strips it; construction lifetimes/transitions match `construction_geometry` against spatial sections | Project the permitted owner ID and use it. Equal geometry is not identity. Overlapping constructions are a risk, not a claimed reproduced disappearance. |
| E5 | Concentration media infers a new slot by before/after differences and spell ID | Record the exact slot association when the cast commits, including item-sustained casts. Historical absent associations remain unknown; do not guess and grant visibility. |
| E6 | Four lifetime implementations separately recurse into movement/reaction timelines | Shared traversal only. Native operation count and presentation playback time stay distinct. |

### Producer → fact → consumer

| Operation | Authoritative owner and recorded contract | Downstream responsibility |
| --- | --- | --- |
| Attack/cast | Existing action declaration/execution/outcome; child targets retain their own causal identities | Suggestions describe it; choreography binds it. Neither spends resources or re-executes it. Multi-target child outcomes are not duplicate casts. |
| Damage | `TakeDamageEvent` is the interruptible request; existing `DamageAppliedEvent` is committed damage/HP result | Preserve both meanings. HUD, damage reactions and replay consume the appropriate committed result once. Never apply damage from both records or merge them merely because both mention damage. |
| Fire Shield retaliation | One qualifying hit causes one ordinary child damage operation with magical provenance and parent hit identity | Preserve zero-damage-hit qualification and the no-recursive-retaliation rule. Separate melee hits in Multiattack may each retaliate; repeated versions of the same hit may not. No synthetic second attack. |
| Condition apply/remove | Existing native condition lifecycle with actual owner UUID | Projection snapshots and media membership follow admitted facts. Failed removal is not a visual retirement. No duplicate per-spell condition family. |
| Condition state update | Owner publishes a changed snapshot for an already active condition | Update state without pretending the condition was newly applied. Concentration-slot maintenance and cumulative Life Drain must not re-trigger application media. |
| Item consume/recharge | Existing item resource operation, item UUID, kind, before/after charges and stacks, terminal outcome | Actor/world projection and analytics interpret the same mutation. Recharge is not an attack, use animation or charge spent. |
| Drop/pickup/equip | Existing native ownership/location and equipment operations | Old floor representation is removed on pickup; recipient/observer filtering is retained. Item UUID, coat lifetime and material state survive transfer. |
| Movement | Existing committed path/leg facts, movement mode, actual positions and expenditure | Replay only committed progress. Visibility/lifetimes use time-local observed states, not final masks. No render-side refunds or speculative path mutation. |
| Spatial field/construction | Existing spatial owner plus section UUID/owner association and actual mutation/removal | Geometry positions art; IDs establish ownership. Destroyed, removed and merely unseen are different outcomes. |

The added `TakeDamageEvent.effect_origin` is provenance, not evidence of a second
damage pipeline. Preserve it where necessary for Magic Resistance/retaliation.
Do not remove accepted typed metadata simply to reduce field count.

Event acceptance rules:

- Cancellation before an operation's commit prevents that mutation. Later parent
  cancellation does not undo completed children or family-specific committed
  costs. Finite item release follows step 5's phase table; only still-pending
  preparations are canceled. No universal rollback/refund semantics.
- Native publishers own mutations. Actor/world/player projections are derived
  views, not additional authoritative publishers.
- Different event versions share an operation lineage but are not interchangeable
  with different attacks/targets. Dedupe by the actual operation, never by spell
  name, frame, target position, source alone or an entire multi-target parent.
- Replaying, seeking backwards, repeating observations or switching camera cannot
  consume, recharge, damage, grant actions or remove conditions.
- Actual transitions remain ordered. Do not collapse an entire lineage to its
  final state to hide duplicate publication: that recreated the movement bugs.
- Projection includes only authorized observations. Explicit native owner IDs do
  not license showing hidden geometry, targets or conditions.
- Older accepted records with absent optional metadata remain valid inputs.
  Migrate at the existing versioned record boundary; do not fabricate ownership.

## 6. Acceptance matrix

These are contracts to verify later, not tests run during this planning task.

| Area | Inputs and required observable result |
| --- | --- |
| Scope | Six spells and three powered packs still admitted; four rejected arrow IDs not offered; normal bows/muskets work without ammunition. No new art or character roster rollout. |
| Functional items | Base/named/+bonus wooden staff accepts Shillelagh; nonwood or wrong kind does not. Replacing/transferring the exact possession does not buff an unrelated weapon. Accepted enchantments and coatings survive. |
| Attack economy | Existing Extra Attack × Haste × Action Surge × Slow matrix, including either-hand-first, offhand eligibility, Frenzy, opportunity attacks and object targets, stays valid. Multiattack substitution replaces one eligible strike rather than adding one. |
| Movement | Longstrider/Haste/Slow in different application/removal orders; exhaustion/zero-speed bounds; shared walking/flying expenditure; Dash, grant loss and remaining grant; contextual speed; interruption and turn reset. Public stats, discovery and execution agree. |
| Effects | Accepted spell targeting/durations, Barkskin floor, Produce Flame light/hurl/dismiss, Fire Shield hit/zero-damage/miss/ranged/multiple-hit cases, innate lifetime versus spell concentration. No leaked grant or light after removal. |
| Powered gear | Equip/use/unequip/drop/loot/re-equip/rest; correct source possession and one charge; no transfer recharge; ordinary action/slot rules; accepted fire coating and Longstrider/Resistance behavior. |
| Resource events | Admission rejection, interruption before release, owner loss, successful use, release followed by effect rejection/parent cancellation, repeat commit, recharge, duplicate rest visitation and stale prepared reference. One actual charge mutation; committed release is not refunded; no recharge counted as expenditure; no orphan prepared operation. |
| Condition events | Cumulative Life Drain, concentration child replacement/removal/veto, multiple slots and item sustainer. One published changed state per committed mutation; unchanged cleanup emits nothing; removal does not masquerade as apply. |
| Replay and privacy | Record native action once; repeat/reseek/camera-switch without changing engine state. Two observers receive only permitted facts. Transfer removes floor copy; condition/media retirement matches witnessed events. |
| Causal binding | Same facts with a recipe present/missing/retimed retain identical result owners and final native state. Repeated applications to the same recipient, equal arrival times, retaliation and multiple committed packets do not merge or disappear. |
| Typed public facts | Invalid partial application references and applied damage without required committed HP fail boundary validation. Unknown cause stays unknown. New-schema JSON round trips and deterministic legacy migrations preserve source order; ambiguous old packets receive an explicit diagnostic. |
| Visual milestones | Formation appears before its resulting injury; HP/numbers/body reaction use the same application contact. Destruction changes footprint at the authored clear milestone. Native turn-end triggers retain their own identity. No synthetic duplicate sensory node or final movement mask painted backwards. |
| Portability and capability | Export covers the actual player packet and admitted recipe fields without server/Pygame constructors. Recorded facts plus admitted data determine semantic cue identity/timing. Changing a wall bank changes capability reporting; parsed-but-unexecuted fields cannot claim completion. |
| Constructions | Same-geometry sections with different owners; one owner removed or damaged; unseen sections remain unknown/remembered per existing rules. No cross-owner retirement. |
| Timeline | Movement with nested reaction, simultaneous targets, interrupted cast, creation before impact feedback, sight loss/regain. Shared offsets preserve previously accepted clips. |
| Admission and imports | One world schema, reject unsupported data at admission, canonical IDs/registrations construct, retained wire records load, no cycles/late imports/reflection workarounds. |

## 7. Independent approval gate and author checks

The user explicitly requires independent approvals and permits finalizing the
plan first. Before implementation, two separate reviewers must inspect the final
plan and cited source: one anti-slop reviewer and one ECS/anti-OOP/import-DAG
reviewer. This is a narrow exception to the earlier agent-communication ban;
unrelated agent/thread coordination remains stopped. Both initial independent
reviews requested changes: preserve committed child operations on later parent
cancellation, and specify callback-damage resolution ownership. The revisions
above address those requests; final independent dispositions are recorded in a
separate review receipt so the reviewed design can remain identifiable.

Record each review against the exact plan revision, with findings and an explicit
approve/request-changes disposition. Resolve blockers in the plan and have the
affected changes re-reviewed before claiming approval. Independent approvals do
not themselves authorize implementation. The checks below remain **author
self-reviews**, not either required independent approval.

### Anti-slop reviewer pass

- Retained behavior is explicitly enumerated; no feature is silently abandoned.
- Rejected ammunition is deleted end to end, not renamed “payload support”.
- Three runtime task buckets and four repeated timeline walks have named removal
  results. Cold source-grouped data is preserved where it remains useful.
- Semantic weapon data replaces expanding ID allowlists. Native owner IDs replace
  geometry/spell-name inference. No patch merely adds another special case.
- One necessary arithmetic operation replaces mirrored speed machinery. This is
  the largest change; it is not disguised as moving a spell file. Its complete
  writer/reader migration is part of the step, not a later cleanup promise.
- A helper/schema extraction must delete its old implementations. No catch-all
  framework, dead compatibility executor or unbounded rule expansion is allowed.
- Historical green tests and previous approval text are not architecture evidence.
- R1–R9 include specific committed-source evidence, not just the latest diff.
  Each new relation/variant removes a named inference or invalid state. Existing
  lineage, application, slot and version IDs are reused; there is no extra bus,
  scheduler, scripting language or event class per spell.
- Typed semantic branches and shared geometry algorithms stay. Converting every
  branch to JSON would move the problem rather than simplify the design.

### ECS / anti-OOP / import-DAG reviewer pass

- Entities remain data/composers; no new creature class hierarchy or per-item
  enchanted subclass family. Existing finite action/condition implementations
  remain the owners of genuinely distinct operations.
- Spell, innate and class sources compose movement; they do not inherit Fly.
- Passive records carry weapon semantics, source-use requirements and ownership.
  Runtime mechanisms do not import authored recipe tables.
- Source-owned modifiers/grants have explicit removal paths and veto behavior;
  reads never perform cleanup. No duplicate factor/state ownership remains.
- Native state → recorded event → observer facts → reduction → presentation has
  no reverse rule dependency. A render-side cache cannot become a rule authority.
- Event operation/phase identity and typed data are preserved without new buses,
  registries, late imports or reflective capability tests.
- The current AST inventory is acyclic (543 production modules); this does not
  excuse public schema imports from runtime modules or recipe-dependent cause
  interpretation. Passive values move to dependency leaves only where needed.
- Player facts carry permitted causes/results; recipes carry visual milestones;
  one compiler binds them. No server frame numbers, client gameplay execution,
  future-state visibility grants or Pygame values in the portable packet.

Source-review conclusion: this is a concrete repair design, not proof of a correct
implementation. The arithmetic and event-phase changes require the full acceptance
gates above. No “flawless”, “all green” or independent approval claim is justified yet.

## 8. Completion accounting

| Prior finding | Closing step |
| --- | --- |
| 1 Runtime task buckets | 3–4: neutral movement plus existing spell/trait/item owners; delete old modules |
| 2 Split/mutating movement reads | 3: single speed/budget contract and complete consumer migration |
| 3 Arrow data disagrees with execution | 1: rejected feature removed, Basic Poison preserved |
| 4 Innate flight inherits Fly | 3–4: compose shared mode-aware Move |
| 5 Specialized universal base hooks | 1 and 4: remove ammo hooks and BaseBlock permission placeholder |
| 6 Recipes mixed with mechanics/private imports | 4: cold definitions, canonical builder, public coating operation |
| 7 Repeated presentation traversal | 6: one walk, separate policies |
| 8 Duplicate schema admission | 6: one typed admitted source document |
| 9 Discovery reflection | 7: typed action-owned description |
| 10 Overstated review receipts | 8: exact-state validation and honest checkpoint |
| 11 Recipe IDs used as weapon semantics | 2: kind/material survive composition |
| 12 Wight inside generic Multiattack | 2: complete authored replacement choice |
| E1–E3 Resource/state publication | 5: operation semantics, terminal state and one mutation publisher |
| E4–E6 Presentation ownership/traversal | 5–6: exact recorded IDs and shared traversal |
| R1–R3 Causality and insufficient result types | 5 and 6a: resolution/application references, validated stage variants and ordered results |
| R4–R5 Observation timing and commit-phase inference | 5 and 6b: referenced observed changes, existing commit order and shared milestones |
| R6 Persistent instance ownership | 5 and 6c: actual owner/slot links, no geometry/name inference |
| R7 Public contract portability | 5 and 6e: passive shared types, generated current-player schema and documented semantics |
| R8 Capability reporting | 6d: admitted metadata and explicit unsupported requirements |
| R9 Repeated digestion/traversal | 6a–6c: one causal/version index, compiler and resolved walker |

Completion means retained behavior works through the same public paths, the
named redundant mechanisms are gone, and the full active game validation has an
honest disposition. A smaller diff or a renamed module alone does not complete it.
