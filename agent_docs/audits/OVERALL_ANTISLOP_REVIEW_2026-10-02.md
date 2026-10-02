# Overall anti-slop review — 2026-10-02

**Completed architectural source review: 12 findings.** The findings distinguish
observed contract defects, design debt and review-process failures. They are not
12 independently reproduced gameplay bugs.

October 3 follow-up: the [cleanup plan](../ANTISLOP_CLEANUP_PLAN_2026-10-03.md)
maps all findings to concrete removals/repairs and adds an event-ownership audit.
`current_speed()` existed at HEAD; finding 2 concerns its changed implementation
and the new parallel state, not the introduction of that method. No implementation
or tests were performed for the follow-up plan.

Implementation is stopped. This review makes no production changes and does not
authorize repairs. No agents or other chats were contacted for this review.
The human has also stopped testing. The review continues through source reading
and report writing only. Diagnostics mentioned below were run before that
correction; they are retained evidence, not ongoing review work.

The subject is avoidable complexity, poor ownership and misleading contracts
across the work. ECS composition and import direction are evidence within that
review; passing an import check is not the conclusion.

## Assessment and coverage

The current changes contain real design problems beyond the name
`roster_support.py`: duplicate representations of movement, ammunition data that
does not describe its execution, feature-specific APIs on universal base models,
and repeated renderer lifecycle traversal. The previous architectural approval
does not establish that these choices are acceptable.

Baseline: `3f2158f934f198f7edcb93f559fb1fda8b70e1f0`, branch
`codex/recovery-design`, including the uncommitted working tree. This is a shared
checkout: the report distinguishes additions in the current batch, older debt,
and concurrent visual work. It does not attribute every modified file to one
author merely because it appears in `git status`.

Coverage:

- Repository-wide static import inspection of 542 Python modules across `dnd`,
  `game`, `server`, `ai`, `cli`, `custom_ai` and `services`.
- Semantic inspection of the new spell/trait/item batch, movement changes,
  ordinary attack payload resolution, affected base models, and selected renderer
  lifecycle/authoring boundaries.
- Source tracing of functional item composition through native materialization,
  equipped properties, action eligibility, Multiattack substitution and shared
  held/ground item materials. Inspection of window/prop composition and the
  placement/contact contracts distinguishes existing reusable mechanisms from
  the unnecessary additions identified below.
- Targeted inspection of existing discovery/reflection and review documentation.

This is not a claim that every existing game mechanic, renderer path, server
module or authoring tool has received a complete semantic review. Import coverage
is broader than semantic coverage. Findings below are concrete; unverified risks
are listed separately.

## Findings

### 1. `roster_support.py` makes an implementation task into a runtime owner

**Priority: medium. Introduced in the current native batch.**

[roster_support.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/roster_support.py:1)
collects Longstrider, Barkskin, Produce Flame, Fire Shield, Fly and Shillelagh
because this batch requested them. They belong to several spell schools already
represented in the codebase. The file also owns reusable flying movement and
effect-lifetime helpers.

This is more than an unfortunate filename. Spell and condition registration,
catalog content, creature traits and powered items now import it. Future work has
to know which task introduced a spell to find its implementation. Shared mechanics
are becoming dependencies of a temporary content grouping.

The same pattern appears in runtime modules `monsters/roster_abilities.py` and
`items/roster_carried_powers.py`. A cold roster definition table can reasonably be
grouped by its content source; that does not justify using the roster as the owner
of general runtime mechanisms. Moving or renaming files alone would leave the
dependencies and mixed responsibilities unresolved.

### 2. Movement now has two answers, with cleanup hidden inside a query

**Priority: high. Current batch; discrepancy reproduced.**

[ActionEconomy.current_speed](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py:996)
deep-copies the existing movement value, removes selected modifiers, substitutes a
mode base and applies a second factor registry. Haste and Slow write both ordinary
numerical modifiers and entries in that registry. Exhaustion similarly writes a
cap plus a factor. Reading `current_speed` also mutates the registry to prune old
handles.

A native in-memory diagnostic, with no movement spent, produced:

| State | Existing `movement.normalized_score` | New `current_speed()` | `movement_remaining()` |
| --- | ---: | ---: | ---: |
| Base | 30 | 30 | 30 |
| Longstrider | 40 | 40 | 40 |
| Longstrider + Haste | 70 | 80 | 80 |

The new result can implement the intended rule while the old public value still
reports another result. This is a split contract, not evidence that current move
execution necessarily spends the wrong amount. The inspected movement consumers
have been migrated to the resolver; leaving the contradictory value available
still makes future consumers and inspection unsafe.

Sources:
[Haste](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py:648),
[Slow](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py:325),
[Exhaustion](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/conditions.py:821).

Mode-specific speed and one expenditure ledger are legitimate requirements. The
problem is retaining two interpretations and making a read perform lifecycle
cleanup. The existing name-based identification of costs and `Dashing` is older
debt on which this new resolver also relies. No performance claim is made without
measurement.

### 3. The ammunition schema promises data-driven damage that execution ignores

**Priority: high. Introduced in the current native batch.**

[AttackAmmunitionPayload](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/attack_types.py:45)
accepts damage type, die, count and an optional save DC. The diagnostic successfully
constructed a payload specifying 2d6 fire with DC 15.

However, any non-null save DC selects
[this attack branch](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:2400),
which calls `append_saved_poison` with the name “Venom arrow”.
[That helper](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/damage_payloads.py:12)
uses a Constitution save, nonmagical basic-poison effect metadata, one damage die,
and poison damage. The payload's damage type and count are ignored in this branch.
Meanwhile,
[the discovery profile](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:2005)
does use the declared damage type and count. The disagreement is therefore
between two real consumers of the same payload, not merely unused schema fields.

The four currently authored arrow definitions fit those assumptions. The defect
is the broader accepted contract: adding another otherwise valid saved payload
would silently execute different damage from its data. Merely making the model
frozen and typed did not make the mechanism data-driven. Admission must describe
only supported forms, or execution must actually honor the accepted fields.

### 4. Innate flight inherits a concrete spell instead of sharing its capability

**Priority: medium. Introduced in the current native batch.**

[InnateFlight](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/monsters/roster_abilities.py:51)
subclasses `FlyEffect`. The inherited implementation grants
[FlyingMovement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/roster_support.py:376),
whose registered identity is `action.spell.fly.move`, with parent spell `Fly`.
Innate movement therefore inherits both behavior and a spell-specific action
identity. Dragon Wings separately maintains another flight grant/removal path.

This is an ownership problem even though the imports are acyclic. Ordinary
creature flight should not depend on the implementation details or provenance of
one spell. The common capability is supported traversal with an owned speed
grant; spell concentration and innate lifetime are distinct producers of it.

### 5. Feature-specific behavior expands universal base models

**Priority: medium. Introduced in the current native batch.**

[BaseItem](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:163)
now gives every item an ammunition payload field and default no-op methods for
ammunition availability, preparation and commitment. This reaches scenery and
other possessions with no ammunition role. The batch also adds a default
`permits_use_by` implementation to
[BaseBlock](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:411)
to support an equipped-use restriction.

The practical cost is that each new feature teaches the universal model another
specialized vocabulary, usually returning false, true or nothing for unrelated
objects. Avoiding `getattr` by adding every possible feature to a common ancestor
does not by itself satisfy the ECS requirement.

Some shared hooks are appropriate in this adapted engine. The finding concerns
these specialized hooks and where their state belongs, not a blanket objection
to every class or method. An optional, explicit item capability must have a clear
owner and admission rules; inheritance alone is not proof of composition.
The ammunition methods on
[UsableItem](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:1033)
delegate to the existing charge preparation/commit mechanism. That resource
transaction is reused; the criticism is spreading an ammunition-specific wrapper
interface over all items, not an invented claim that charges have a second engine.

### 6. New item authoring mixes recipes, mechanics and private implementation details

**Priority: medium. Introduced in the current native batch.**

[roster_carried_powers.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/roster_carried_powers.py:18)
imports the private `_TimedFireWeaponCoatCondition` from consumables. In the same
module it defines activation behavior, equipment admission, seven item recipes
as positional tuples, and builders.

This bypasses the clean separation just established for ordinary item definition
data and supported property composition. Changing a consumable implementation can
affect a reusable quiver power, and expanding recipes requires navigating runtime
code and tuple positions instead of a clear authoring contract.

The canonical `build_authored_item` remains the single public builder: there is
no evidence here of a second item registry. The problem is the ownership and data
shape below that entry point. This is also not a request for seven new factories
or a universal effect scripting language.

### 7. Renderer lifecycle families repeat traversal of the same timeline structure

**Priority: medium. Existing duplication extended by current visual work.**

The following independently traverse choreography, movement and nested reactions,
carrying absolute offsets:

- [condition lifetimes](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/condition_media_lifetime.py:112)
- [spatial lifetimes](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/spatial_media_lifetime.py:41)
- [concentration lifetimes](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/concentration_media.py:50)
- [construction lifetimes](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/construction_media_lifetime.py:49)

Condition membership, observed spatial effects, concentration slots and physical
sections do need different ownership policies. That does not require each family
to implement the common timeline walk again. A new nesting or offset correction
must currently be carried into several implementations, creating opportunities
for visuals to disagree about the same event history.

The duplication is confirmed by source inspection. No new timing failure is
claimed from this review alone. A correction should isolate common traversal
without collapsing distinct lifetime policies into another oversized framework.

### 8. Presentation schema admission must be manually synchronized in two places

**Priority: medium. Existing arrangement; a current integration failure exposed it.**

[WorldBindingsSource](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/assets.py:129)
admits presentation sections as dictionaries of JSON values.
[animation_data](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py:456)
separately reads that file and decodes their concrete models.

Adding `construction_media` initially updated only one admission path. An existing
coated-dagger transfer test then failed while loading the shared catalog with
`WorldBindingsSource: construction_media: extra_forbidden`. The missing field was
subsequently added and that test passed. This is a recorded integration defect,
not a claim that it remains broken now.

The unnecessary coupling is that unrelated item replay could not load because a
wall-media schema name had to be remembered in another owner. Fixing that one
field resolved the symptom, while the manual synchronization requirement remains.

### 9. Discovery still guesses concrete action fields through reflection

**Priority: medium. Existing at HEAD; not introduced by this native batch.**

[Entity action discovery](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:4824)
uses `getattr` for spell damage type, spell level, cast level and variant status.
Missing attributes fall back to null or false rather than satisfying an explicit
typed discovery contract.

This lets the import graph remain clean while the shared owner still knows and
probes concrete spell-shaped data. It can silently omit metadata when an action
does not match those assumptions. This is the kind of type/ownership shortcut the
repository instructions prohibit; a clean DAG does not detect it.

The inventory records 155 reflection call sites. That is not a count of 155
proven defects: schema introspection and dynamic gameplay probing require separate
classification. The concrete discovery examples above were checked against HEAD
and must not be presented as new regressions.

### 10. Review receipts were stronger than the evidence justified

**Priority: medium. Review and delivery failure.**

The [native implementation record](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/ROSTER_ABILITIES_IMPLEMENTATION_2026-10-02.md:66)
records independent anti-slop and ECS approval. That review did not prevent the
ownership and contract problems above. It should not have been used to reassure
the user that the implementation was architecturally settled.

Behavior tests and typing results support particular contracts; they cannot stand
in for checking whether state has two owners, whether inheritance couples the
wrong concepts, or whether accepted authoring data matches execution.

The historical 2,431-pass suite is explicitly from before the Grapple scope
reduction. The final broad run was interrupted at the user's instruction. It is
not a current complete-suite pass. Repeated approval paragraphs and historical
counts must not obscure what is actually verified at the current checkout.

### 11. Exact recipe IDs undermine the promised composable item system

**Priority: high. New consumers expose a missing semantic contract.**

[named_item](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/item_composition.py:12)
creates a named variant by replacing its ID and name while preserving the base
definition's other properties. The canonical materializer then produces a weapon
with that new ID. This is the agreed way to author upgraded or flavored weapons.

But [Shillelagh eligibility](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/roster_support.py:490)
accepts only the literal IDs `weapon.club` and `weapon.quarterstaff`, repeating
the same check at application. A club or staff produced through `named_item`
therefore fails eligibility solely because it has a new content identity.

The Wight Multiattack substitution similarly requires
[an exact item ID](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/monsters/traits.py:534),
authored as `weapon.longsword`. Equipping an Ember or psychic longsword changes
that answer although these are explicitly composed from the longsword base.

This is established by following the source predicates; no new test was run.
It exposes a missing distinction between recipe identity and mechanically
relevant weapon kind/material. Adding more IDs to the allowlists would spread
the same defect as content grows. The fix belongs in that semantic contract,
not a new per-variant script or a renderer-name inference.

### 12. A generic Multiattack extension contains one creature's specific content

**Priority: medium. Introduced in the current native batch.**

[MultiattackAction](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/monsters/traits.py:528)
adds an optional replacement attack, replacement slot, required item ID and a
selection flag. Its discovery code then labels every substitution
[`(Life Drain)`](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/monsters/traits.py:545),
regardless of the replacement action supplied.

The shared action now contains a Wight-specific assumption behind apparently
general fields. Authoring another replacement would require editing the generic
mechanism or accepting incorrect discovery text. The four related fields also
permit partially specified substitution configurations instead of expressing
one complete optional choice.

The correct part is retained: selected children execute through ordinary Attack.
There is no second attack resolver here. The unnecessary part is putting one
creature's choice semantics into the common action rather than keeping the
replacement's identity and admission data together.

## What the review does not justify replacing

- **Functional item creation and the canonical builder.** Immutable definitions,
  `named_item`, supported property transforms and
  [materialize_item_definition](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_builders.py:255)
  already provide the intended creation path. Findings 6 and 11 concern consumers
  and recipe organization around it. Another item framework would worsen this.
- **Ordinary attack execution and attack budgets.** Special arrows and Multiattack
  children use the ordinary attack path. Source inspection found no reason to
  restore a separate AttackObject action or create UseArrow combat execution.
  Ammunition preparation delegates to existing item-charge transactions. The
  payload and interface defects do not invalidate that reuse.
- **Existing condition/modifier/event machinery.** Longstrider contributes a
  numerical modifier; Barkskin contributes an AC floor; spell effects use native
  condition application, removal and owned handles. Distinct spell effects are
  not automatically duplicates of basic conditions. Innate invisibility's
  configurable reveal triggers reuse the existing effect. The movement registry
  and spell-derived innate flight are the specific ownership problems.
- **Item-owned properties and shared material rendering.**
  [Property contribution cleanup](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/property_composition.py:99)
  removes exact owned handles.
  [Held items](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_draw.py:456)
  and [ground items](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/item_draw.py:23)
  call the same material function using received item effect data. Palette
  replacement and bounded bloom do not need a new weapon-art pipeline.
- **Typed environment composition.** Window assemblies use existing WorldItems,
  placement, destruction profiles and traversal connectors. Contact passage is
  an explicit policy over attack access types. Prop debris uses an ordinary
  AreaCondition. This source inspection supplies no basis for throwing away
  those systems or inventing per-prop executors.

These are architectural retention judgments from source inspection, not fresh
functional certifications. Preserving them limits a future repair to the actual
findings instead of turning this review into another rewrite.

## Completed coverage and conclusion

| Area | Inspected responsibility | Review outcome |
| --- | --- | --- |
| Spell/creature content | Registration owners, effect composition, innate flight and Life Drain | Findings 1, 4 and 12; retain ordinary effect/attack machinery |
| Movement/conditions | Speed representation, modifiers, mode grants, cleanup and affected consumers | Finding 2; the extra interpretation of movement is the central defect |
| Items/equipment | Definition transforms, canonical materialization, properties, gear powers and item eligibility | Findings 5, 6 and 11; keep the existing composition path |
| Actions/resources | Discovery metadata, payload resolution, Multiattack, preparation and commitment | Findings 3, 5, 9 and 12; retain normal attack budgets and charge transactions |
| Rendering | Timeline traversal, ownership matching, schema admission, item appearance/material consumers and sampled cloud/wall dispatch | Findings 7 and 8; construction owner matching remains an unproven risk |
| Environment | Placement/footprints, window assembly, physical contact policy, prop destruction/debris composition | Existing shared mechanisms identified; no additional confirmed defect from this inspection |
| Imports | Complete static graph for the stated roots, late/dynamic imports and selected reflection use | No observed import cycles; semantic direction and reflection still need the findings above |
| Review/delivery | Approval claims, historical results and actual completion boundaries | Finding 10; prior approval was insufficient |

**Conclusion:** the current work must not be treated as a clean foundation for
further content expansion without addressing these findings. The highest-priority
contract problems are duplicate movement meaning, saved-arrow execution disagreeing
with its data, and recipe-ID checks breaking item composition. The broader pattern
is introducing an apparently reusable mechanism for one immediate example, then
spreading its assumptions into shared owners.

The review is complete at the architectural coverage stated above. It does not
claim exhaustive behavioral verification of the entire repository. Findings
include the dependency spread, existing owner and practical consequence needed
for discussion. No implementation or new verification run follows automatically.

## Unresolved evidence, separate from confirmed design findings

- Construction creation/removal associates section objects with effects using
  geometry equality in
  [construction_transitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/construction_transitions.py:23)
  and
  [construction_media_lifetime.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/construction_media_lifetime.py:47).
  Equal shapes are not necessarily the same owner. This deserves a concrete
  overlapping/replacement-construction check; this review has not reproduced an
  incorrect ownership association and does not label it a confirmed runtime bug.
- The recorded Ice presentation test failed because discovery supplied no ordinary
  attack choice against the expected adjacent section:
  `test_real_cast_attack_and_removal_keep_sections_independent[ice]`. The failure
  is retained; its backend cause is not established here. No backend change or
  test relaxation was made to hide it.
- The paused server still has a recorded cold-start failure importing removed
  `dnd.core.senses`. It is distinct from the dependency checks below.

## Supporting import/ECS evidence

The static snapshot contains 3,619 distinct internal import edges across 542
modules. It found **no cyclic components and no function-local imports**. One
dynamic import occurs in the existing, explicitly checked content import boundary
at `dnd/content_system/import_boundary.py:10`.

The targeted dependency/action-discovery architecture run passed **26 tests in
63.42 seconds**. This does not include the separately failing server cold-start
check or certify every architecture test.

[Dependency-direction enforcement](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/architecture/test_dependency_boundaries.py:967)
checks package boundaries and Entity's concrete dependencies. It does not reject
the creature-trait-to-Fly-effect coupling. There is therefore no contradiction
between a passing graph check and findings 1, 4, 5 or 9.

The ECS concern is concrete: producer-specific inheritance and universal base
hooks are being used where explicit capability ownership is needed. No assertion
is made that all inheritance in this adapted engine is invalid, or that every
large module is automatically a defect.

## Evidence and stop state

Private, non-production evidence is under
[.runtime/antislop-review-20261002](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/antislop-review-20261002):

- `import-inventory.json`: source hashes, graph summary, late/dynamic imports,
  reflection locations and selected dependency lists.
- `contract-probes.json` and `movement-probe.log`: native movement diagnostic and
  accepted saved-arrow payload.

The verification logs referenced here remain at their original temporary paths:
`/tmp/overall_antislop_architecture_20261002.log`,
`/tmp/roster_projection_final.log`, `/tmp/roster_transfer_recheck.log` and
`/tmp/roster_ice_attack_issue.log`. They were not copied into the evidence directory.

All inventoried source hashes were unchanged when rechecked before writing this
report. No production files, tests, existing plans, assets or Git history were
changed by this review. The findings are for discussion; implementation remains
stopped. This report is not a newly approved repair plan.

## October 3 extension — committed code and rendering contracts

The [current-source rendering audit](RENDER_EVENT_CONTRACT_REVIEW_2026-10-03.md)
adds nine findings, with committed-baseline checks for R1–R5. The main concerns
are ownership inferred from art availability, application matching by target and
time, weak result variants/cardinality, and sensory-node splitting inside
choreography. This extends the main review; it does not narrow it to rendering.

A fresh static inventory covers 543 production modules and 3,644 internal edges,
with no static cyclic components or function-local imports. Different ownership
or semantic defects can exist in an acyclic graph. No tests or native executions
were run for this extension, and no production code was changed.

The [cleanup plan](../ANTISLOP_CLEANUP_PLAN_2026-10-03.md) now names the typed
contract changes and the exact heuristics to remove before consolidating
presentation traversal. Implementation remains stopped. The user subsequently
required independent reviews as a narrow exception to the communication ban.
Both approved the corrected design; [review receipts](ANTISLOP_CLEANUP_PLAN_REVIEWS_2026-10-03.md)
record the exact plan revision and the changes requested before approval.
These approvals do not certify an implementation or authorize production edits.
