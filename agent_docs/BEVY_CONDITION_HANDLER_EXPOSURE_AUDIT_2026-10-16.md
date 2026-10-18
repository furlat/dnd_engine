# Condition and handler exposure in a headless Bevy port

## Finding and scope

The source audit found **no condition/handler family requiring an unavailable Bevy capability**. The reviewed mechanics can be represented by typed native components, queries, resources and concrete systems. That is an architectural feasibility conclusion. It does not establish a finished translation, behavior parity, queue liveness, unrestricted parallelism or a speedup.

The default remains direct native translation. A different internal mechanism is considered only when a demonstrated integration corner makes the existing implementation shape awkward or unsafe across queued work. Supported rules, causal visibility, accepted outcomes and source ownership remain the constraints. This is not a cleanup agenda or an authorization to edit the Python engine. The user selected design-first treatment of any such alternatives.

This audit supplements and corrects the [Bevy design](BEVY_REACTIVE_ENGINE_DESIGN_2026-10-16.md) and [language-independent architecture](DND_ENGINE_LANGUAGE_INDEPENDENT_ARCHITECTURE_2026-10-16.md). The earlier structural claim was broader than its concrete condition/handler evidence. Medium-reasoning subagents inspected foundations, spells, features/world and grants, followed by integration-site coverage and an independent native API review. AntiOOP, antislop and adherence review are included in those reports and final review notes. There were no production/test edits in this audit.

## What was actually inventoried and reviewed

The reproducible [AST inventory](audits/bevy-condition-handler-audit-20261016/inventory.py) parsed 302 Python files with zero parse failures. Its 3,203 overlapping rows include:

| Indexed category | Static count | Meaning and limit |
|---|---:|---|
| Condition declarations | 252 | Includes BaseCondition and transitive subclasses, including data-only specializations. Source declarations and local/inherited lifecycle boundaries were assigned to reviewers. |
| Handler declarations | 12 | Includes base/specialized configuration classes, not 12 distinct gameplay behaviors. |
| Handler constructor / processor-argument sites | 153 / 153 | Sites, not runtime instances. Factories and loops install more instances. Required BaseHandler field declaration is a separate non-callable row. |
| Contextual modifier construction / callable sites | 43 / 43 | Concrete evaluators were traced; source immunity callbacks and other indirect callable seams were additionally inspected. |
| Registration, removal or direct invocation sites | 148 | Mixed event, pre-completion, lifecycle and passive APIs; not 148 mechanical interceptors. |
| Condition constructions / methods | 217 / 829 | Discovery index; inherited methods and surrounding integration bodies require source review. |
| Interaction calls | 1,343 | Includes phase/update plumbing and unrelated collection remove calls. Not a behavior/test count. |

Exact source ownership and read classifications are in the [combined ledger](audits/bevy-condition-handler-audit-20261016/consolidated-coverage.tsv) and [coverage accounting](audits/bevy-condition-handler-audit-20261016/coverage-accounting.md). A report-scope assignment is explicitly distinguished from an exact keyed source-read ledger row. Infrastructure is reviewed at its relevant mechanical boundary, not declared wholly read or behaviorally certified.

The spell integration second wave reviewed 811 indexed integration sites in 344 enclosing functions, plus 37 supplemental functions found through concentration/source/finalization scans. This matters: constructors alone miss dynamic wall construction, source validation, target-pool selection and area finalization. Feature/world coverage similarly includes lifecycle callbacks with no EventHandler constructor. No assertion is made that all 302 parsed files were read in full, every transitive helper was audited, or arbitrary third-party Python packs are ported.

Source reports: [foundations](audits/bevy-condition-handler-audit-20261016/foundations.md), [spell conditions/processors](audits/bevy-condition-handler-audit-20261016/spells.md), [spell integration](audits/bevy-condition-handler-audit-20261016/spells-integration.md), [features/world](audits/bevy-condition-handler-audit-20261016/features-world.md), [permanent grants/extensions](audits/bevy-condition-handler-audit-20261016/content-grants.md), [infrastructure](audits/bevy-condition-handler-audit-20261016/infrastructure.md), and [native API exposure](audits/bevy-condition-handler-audit-20261016/bevy-exposure.md). Later integration reports supersede earlier explicit coverage gaps and the initial unqualified Silence alias concern.

## The mechanical contract that must be exposed

A condition is addressable runtime rule data. It can own exact modifier IDs in several values, handler registrations, source-set claims, actions, lights, capabilities and graph links. It has recipient membership, source/provenance, duration and suppression. These are distinct axes. A concrete native condition payload does not require a Rust condition class hierarchy.

An installed handler is configuration plus state and a native processor registration. A selected invocation is a separate record: event/view identity, discovery position, current accepted version, cause, required child, emitted descendants and any operation guard. Many invocations can refer to one installation; installation state cannot stand in for each pending invocation.

The dispatcher still performs exact event/phase/source/target matching, existing bucket/cell ordering and live eligibility checks. It accepts in-place mutation, returned replacement, cancellation and side effects according to the actual publication API. A returned None means no replacement, not no payment, RNG draw or world change. A sibling Bevy observer broadcast does not provide this ordered accepted-result protocol.

There are also concrete lifecycle entry points outside that dispatcher: membership/placement change, forced-movement landing, removal admission participants, graph-settled hooks, restraint repair before completion, direct admitted summoning Effect, game close and required sensory pre-completion. Expose each as an ordinary native domain system. Bevy component hooks are useful for storage invariants after admission; they do not return veto/results or implement these domain stages.

## Concrete native storage and execution

| Existing responsibility | Native Bevy representation | Required timing |
|---|---|---|
| Condition identity and authored parameters | Condition entity with header, typed payload, duration, recipient/source IDs | Query names/keys/tags as well as payload type; external rules use those indexes. |
| Numerical contribution | Typed owner value maps with exact contribution IDs and contextual rule configuration | Respect the installed contribution gate and live input boundary; no universal Applied filter. |
| Cleanup, provenance, suppression authority | Separate typed links/tokens; contribution owner is optional | Do not infer suppression from cleanup ownership or source existence. |
| Installed handler | Native entity/configuration plus concrete typed processor registration | Keep dispatch rank and enabled policy explicit. |
| Pending invocation or application | Typed family execution component containing IDs, stage/cursor and required result | Own data across yields; release Query/World borrows before returning. |
| Shared manifestations | Explicit source/lease/manifestation graph and exact reverse indexes | Admission/removal/winner commitment is ordered for the affected graph. |
| Accepted damage/save/healing | Typed request/result records referring to canonical event versions | Resume the actual consumer only at its consumed boundary. |
| Permanent grants | Typed source sets and family receipts | Preserve exact UUID, resource contribution and template restoration order. |

Concrete processors can be ordinary scheduled systems with Query/SystemParam access. A synchronous accepted-result seam can use native System input/output or a narrow exclusive system. A queued processor writes a concrete result record and resumes another system later. Native Commands::run_system_with returns no child result to its caller and executes exclusively; it is not an await protocol. A saved native System instance is execution machinery; condition/cast counters and captured gameplay state belong in typed ECS data.

The independent review checked actual Bevy 0.20 source: [System input/output and execution](https://github.com/bevyengine/bevy/blob/v0.20.0/crates/bevy_ecs/src/system/system.rs), [registered systems](https://github.com/bevyengine/bevy/blob/v0.20.0/crates/bevy_ecs/src/system/system_registry.rs), [Commands](https://github.com/bevyengine/bevy/blob/v0.20.0/crates/bevy_ecs/src/system/commands/mod.rs), and [component lifecycle](https://github.com/bevyengine/bevy/blob/v0.20.0/crates/bevy_ecs/src/lifecycle.rs). Public API expressibility is established for these surfaces; complete translated gameplay families are not qualified.

## Corrections to the earlier design

**Cleanup ownership does not universally imply suppression ownership.** BaseCondition.contributions_active checks graph/provider state, not applied membership. Concentrating installs its damage/death handler after the general contribution-binding pass; that handler has no contribution_owner_uuid. Invisibility reveal explicitly runs suppressed; Greater Invisibility's check does not. The port must preserve these actual policies. Querying only active condition membership would hide intended provisional contributions; automatically gating every installed handler would add a rule.

**Post-commit does not universally mean immutable notification.** Entity._complete_damage_applied_event advances DamageApplied through ordinary mutable dispatch after HP commitment. Body responses return body_release annotations; concentration returns concentration_broken. Those returned versions are accepted. Explicit publish_committed_phase has a different deep-working-view/ignore-return policy. Select the publication mode from the producer operation, not an event name or the fact that HP already changed.

**Condition operations do not universally roll back all effects.** Prone can spend half movement and cancel application; Dashing earns turn credit at membership and removal does not refund it; Exhaustion can cause death during provisional install. Shield and several actions ignore child admission outcomes. AegisTraining mutates action registration outside its generic provisional cleanup handles. These observations constrain an honest translation; the architecture cannot invent one universal transaction or success prerequisite. A demonstrated malformed authoring corner can be reconsidered against supported rules during the port, without making cleanup a separate task.

**Behavior is distributed beyond condition classes.** Named Prone auto-stand lives in a standard actor handler. Metamagic changes exact future installed spell templates and is consumed at specific cast phases. Permanent feature installers own source sets and restoration receipts. Summoning has validators, direct processors and graph/close hooks. Porting only condition payload classes would miss mechanics.

## Hard corners and narrow alternatives if needed

| Demonstrated integration corner | Rule dependency that remains | Native alternative when crossing that boundary |
|---|---|---|
| Guardian scans history after damage | Applied damage updates one zone budget before later dependent triggers/retirement | Exact damage receipt and ordered Guardian budget continuation; preserve ancestry filtering and actual applied amount. |
| Harm also scans after damage | Completed TakeDamage.final_damage decides max-HP reduction | Receipt exposes that distinct accepted measure; do not replace it with Guardian's applied-damage field. |
| Mass Heal shares one cast pool | Subtract actual accepted healing in authored application order | Cast-owned pool and ordered commitment; pure arithmetic may be separate, recipient applications are not automatically independent. |
| Gust guard lives around nested movement | Same zone/target cannot re-push while that operation is still in flight | Operation-owned guard persists through save/movement/cleanup, including failure. |
| First plate pulse can release its own plate | Outer invocation still emits its originally selected later outputs | Invocation-owned selected tuple and cursor; do not gate resumed pulses on current pressed state. |
| Temporary save bonus is installed on a live target | Originating and nested saves may observe it; unrelated work must not acquire leaked authority | Keep a small atomic save scope, or qualify exact scope-aware visibility/claims before yielding. A private save-only copy is not automatically equivalent. |
| Telekinesis passes on_landing callback | Damage, fall damage, life check, save and Prone settle before forced-movement completion | Typed landing execution and exact child results; ordinary component insertion hook is insufficient. |
| Material replacement exposes provisional footprint | Incoming mechanics and exact restoration/finalization see the authored state | Domain-specific displacement preparation/claims/compensation; no global world rollback framework. |
| Shared restraint repairs before completion | Surviving leases must own the admitted replacement manifestation | Typed reconciliation stage which awaits replacement and graph rebind. |
| Metamagic mutates future installed templates | Exact originally selected template set, phase-sensitive consumption and running-cast values remain | Native source-owned overlay is an option if mutable template fields become awkward; do not broaden it to newly added templates automatically. |

These are implementation corners, not evidence that the gameplay rules are incompatible with Bevy. Direct translation remains appropriate where it fits. Detailed evidence and qualification limits are in [spell integration](audits/bevy-condition-handler-audit-20261016/spells-integration.md) and the [feature/world alternatives](audits/bevy-condition-handler-audit-20261016/features-world-rewrites.md).

Silence's captured set alias is a useful example of the user's decision rule. The source describes a fixed origin and existing tests cover stationary blocking/overlap/cleanup. There is no discovered supported footprint-movement case establishing an integration blocker. The port need not invent movable Silence or an alias framework in advance. Revisit the alias only if an actual supported path needs it.

## Central light, sensory and navigation work without losing reactions

One authoritative spatial commit updates grid membership and revision channels. Typed dirty queues then identify affected light regions, observers and knowledge/navigation caches. Deduplicate recomputation for the same owner/revision only inside compatible observation boundaries. Preserve separate causal facts and rule admissions even when their expensive derived computation is shared.

Light systems consume objective geometry/emitter/suppression inputs. Sensory systems consume the exact geometry/light/capability state needed by the observer's boundary, update contacts/knowledge and publish required sensory children. Navigation caches belong to the actor's knowledge and movement policy, so a path job is keyed by that knowledge revision and route constraints, not just current objective terrain. Compute paths on demand and revalidate the next authoritative step after reactions.

A consumer waits only for the result it uses. The next Fireball reach stage waits for relevant barrier destruction and propagation. An unseen-attacker modifier waits for its relevant perception input. An injury capture waits for required body-release/residue annotation. Root completion waits for required children and observation closure. None should wait for every queue to become globally empty.

The queue implementation must keep values-current readiness separate from fully closed ancestor observation. Otherwise a child can wait on an ancestor that is waiting for that child. Pending data must name a real producer/result or a declared external input; ready work gets bounded service; long computations need bounded chunks or revisioned background work. Equivalent dirty requests are coalesced without erasing rule causes. Revision mismatch invalidates/recomputes a derived result before authoritative use. Errors must settle guards/receipts and surface through the owning operation rather than leave a silent permanent pending record. Cycle and runaway diagnostics are necessary failure reporting, not permission to drop effects.

These are design obligations. The existing queue probe demonstrates a small bounded cascade; it does not prove general fairness, failure cleanup, dynamic cycle prevention or cost limits for the full engine.

## Where parallelism actually exists

There are two distinct questions. Native Query/resource declarations tell Bevy whether scheduled systems have conflicting memory access. Domain state tells the engine whether two rule operations may commit independently. Distinct target entities answer neither question by themselves: queries can broadly conflict on the same component type, and targets can share a protector reaction, caster slot, Guardian budget, cast healing pool, condition manifestation, RNG assignment, spatial cell or observation input.

Natural initial parallel work is immutable geometry/illumination/perception/path computation against named revisions, and invocation-owned arithmetic after deterministic input/RNG assignment. Authoritative event interception, contested resources, graph admission and overlapping spatial commitments retain ordered short stages. Narrow components, disjoint query filters, per-job outputs and batch/parallel iteration may reduce actual memory conflicts; a global ResMut<Grid> or ResMut<EventQueue> in every system would serialize the schedule. Merely queueing registered systems with Commands would also leave exclusive execution.

Parallel preparation can feed deterministic ordered commitment. Revalidate revisioned results where the source consumes live state, and do not perform retries of already observable RNG/payment/child effects as if they were pure computation. The initial runtime can remove producer blocking and redundant cascades while keeping authoritative commits sequential. Additional CPU parallelism is a separately measured implementation step; no speed multiplier is established here.

## Qualification that remains

No new gameplay tests/probes were added or run in this audit. The earlier native mechanism probes and Python test batches retain exactly their previous scope: 238 Python tests passed, two replay-helper failures remained; native examples establish only their stated mechanism cases. They do not establish any complete family above.

Prioritize translated scenarios covering: ordered mutable/replacement/cancel dispatch and selected handler removal; provisional/suppressed/ungated contribution authority; Guardian/Harm distinct receipts and near-exhausted Mass Heal pool; Gust guard and plate output reentry; temporary save scope with nested/unrelated saves; Telekinesis landing and damage/death before blindness; shared restraint/winner graphs and multislot sustain returns; exact permanent reaction/template restoration; Antimagic presence/light refresh; summon existence/control/agency retirement; and per-invocation contextual evidence. Validate each at observable phase/commitment boundaries, then measure full command latency and queue progress. Architecture expressibility, rule fidelity and measured performance remain separate claims.

Final review: the spell reviewer checked this consolidated report for source fidelity/antislop; the feature/world reviewer checked antiOOP, source fidelity and adherence to the user's scope; the independent native reviewer checked this report and the amended architecture/design API claims. No actionable findings remained. Coverage reconciliation verified exact equality with all 3,203 unique inventory rows; 144 local document/source links resolved within file bounds. These are document/inventory validations, not gameplay tests.
