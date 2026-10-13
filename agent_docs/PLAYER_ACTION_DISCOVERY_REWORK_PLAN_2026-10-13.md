# Player action discovery: shared legal choices and on-demand effects

Date: 2026-10-13. Status: implemented, independently reviewed and qualified within the limits below.
The human authorized implementation after the full plan passed review.
Stages 1–7 are complete for this server/SDK rework; residual native discovery
cost and the separate movement target remain open. It continues checkpoint 33 of the
[server performance plan](SERVER_LOCAL_MOVEMENT_REWORK_PLAN_2026-10-12.md).

## 1. Outcome and scope

Return exact playable choices without computing and transmitting the predicted
result of every possible aim. Send subject identities and coordinates once,
share equal eligibility sets across action variants, and compute an exact
subjective AoE preview only for a requested aim. The client can predict effects
from disclosed world data and the action's declared geometry. Native execution
remains authoritative and does not require an earlier preview request.

The human explicitly proposed separate finite subject and position sets, a
shared position-to-legal-spells relation, nonduplicating AoE information and
proper handling of multiple-target selection. This plan adopts that approach.
Targetability is current actor/action data, not a permanent property of a tile.

Scope: native player-discovery computation, retained discovery ownership, server
choices/preview encoding, generated contracts, Python and TypeScript SDKs,
focused tests, temporary measurement, HTML progress and a client handoff.
NDClient implementation remains the other side of that handoff. The earlier
event-associated tile field updates remain intact. Native event/history identity,
movement rules and the removed C++ experiment are not changed by this work.

The four testing-boundary statements from HOW_TO_TEST.MD are:

| Item | Definition |
|---|---|
| Requested behavior | Faster, smaller complete choices with exact legal selections and optional selected-aim effects |
| Boundary | Native discovery → retained server generation → HTTP/SDK choices → ordered preview/command → native result |
| Input | Actual Gallery choices after movement, plus small native spell, object, movement and compound-selection scenes |
| Expected output | Same admitted options, indexes/order, unavailable reasons, costs, subjectivity and execution; fewer unrequested computations and repeated wire values |

The movement target of approximately 9.5 ms remains a separate, unmet metric.
Choices time was excluded from that command receipt clock. Do not claim that
shrinking choices meets the movement target or that a byte estimate is a timing.

## 2. Evidence and cost model

The unchanged Gallery choices 55, immediately after the Sorcerer moves from
(34,15) to (40,20), is 2,399,276 bytes and contains 4,199 target occurrences.

| Contributor | Observed cost |
|---|---|
| Fireball | 1,288 aims; 962,989 bytes |
| Burning Hands, three slot variants | 897 aims each; 416,390 bytes each; three identical target arrays |
| Those four AoE action rows | 92.20% of the reply |
| Fire Bolt | 141 targets, including 140 objects and 82 walls; 69,435 bytes, 2.89% |
| Phase-instrumented choices 55 dispatch | 301.589 ms; native top-level phases 212.542 ms |
| Native entity actions / AoE discovery | 112.408 ms / 75.567 ms |
| Two result dumps + two validations | 39.312 ms + 36.413 ms |
| JSON encoding | 9.713 ms |

These are diagnostic timings. A separate profiled Sorcerer query spends 253.605 ms
in 1,142 connected-propagation floods. Repeated whole flood materialization is the
main AoE owner in that sample; boundary checks themselves are a small part.
Equivalent Burning Hands variants already share native preview computation;
serialization and detachment expand that sharing again.

Node/WSL SDK admission measured 10–21 ms warm and 286 ms on its first decode including
validator compilation; the Python SDK measured 38.23 ms. The SDKs do not account
for the reported browser 2.5-second validation/normalization delay. Preserve that
distinction and measure SDK work once; frontend normalization is outside edits.

The relevant sizes are: distinct subjects **U**, distinct coordinates **P**, exact
action-option links **E**, selected-prefix constraints **C**, and the cells and
recipients in requested previews **F**. Work should track necessary native
admission plus U/P/E/C and requested F. Current eager discovery additionally
solves/materializes F for every aim and copies many repeated target trees.
Reversing the eligibility relation alone does not remove E. It is not generally
possible to evaluate every spell's custom legality once per tile.

Offline representation studies:

| Form | Choices 55 bytes | Status |
|---|---:|---|
| Current response | 2,399,276 | Actual server bytes |
| Omit explicit schema defaults | 1,511,392 | Exact reversible prototype |
| Also share full ordered target sets | 1,047,355 | Exact reversible prototype |
| Also share footprints | 1,033,830 | Only 13,525 bytes more saved; not the preferred design |
| Shared subjects/positions/sets, defer optional AoE details | 231,294 | About 90.36% smaller; preserves all 4,199 non-preview options; new prediction-descriptor overhead excluded |

The last prototype has 1,347 coordinates, 142 subject identities and 8 target sets.
It is a design estimate, not the final schema, validation or server implementation.
Its packet has no secondary pools. All 58 captured replies reverse exactly through
the earlier full-detail prototype, but that naive deepcopy/JSON-key algorithm
costs median 303.73 ms to pack and 279.79 ms to expand: do not implement it.

## 3. Authoritative data and passive wire records

Keep the existing response identity: game/epoch/audience, actor, state revision,
correlation, force-attack and discovery generation. All table references below
are scoped to that one response. Use checked integer array references; there is
no cross-request registry, hash identity or remembered target-delta baseline.

### 3.1 Shared domains

**Subjects:** one record per disclosed subject identity, with creature/object
kind, UUID and label. Include the subjects admitted by native primary or scoped
secondary choices; do not enumerate extra world objects to fill a catalog. Allies
and self remain valid where the rule permits them. A subject-table entry alone
does not grant any action or identify an AoE recipient for every aim.

**Positions:** one coordinate array, referenced by aim options and contact
options. A creature/object and a ground position are different selection types.
A third passive binding kind, self/no-input, retains the native index without a
subject or position reference (for example Dash). Keep object identity
when attacking a wall: a coordinate alone cannot identify overlapping objects.

### 3.2 Exact eligibility relation

Each action retains its exact variant identity, discovery action index, closed
availability reason, cost/resource metadata and native selection rules. Reference
an ordered target set instead of embedding its full target tree. A set contains
typed subject, position or self bindings, preserving each native target index.

Bindings reference shared domains and carry values that actually depend on the
action/target pair: contact position, distance, selected cost, movement data and
primary-dependent continuation. A multicell object's chosen contact can differ
with action origin, access or range. Do not move that contact or distance into a
universal subject record. Do not identify variants by spell name/behavior alone.

Share sets only when all ordered binding values and continuation meanings agree.
Retain unavailable action rows; an empty set does not replace the authoritative
unavailable reason. Sparse optional fields have explicit documented defaults.
Absence, empty lists and deferred data must not acquire ambiguous meanings.

The canonical relation is action→shared ordered set. It also answers “which
actions are legal at this position?” The SDK may build that inverse index once
when requested; do not transmit a second copy of the same authoritative relation.
Do not fill the index by scanning all spells on each hover. Exclude secondary-only
bindings from primary eligibility in either direction.

Use passive typed records in the existing contract/selection modules. Share
common action metadata definitions where necessary to avoid drifting field copies,
but do not introduce a second action class hierarchy or general graph framework.
Native rules do not import server/SDK wire types; preserve the import DAG.

### 3.3 AoE descriptor and optional detail

Expose sufficient declared geometry once per action: shape and dimensions,
origin/aim relationship, relevant resolved fixed origin and propagation mode.
Range origin and area origin need not be identical; derive both from their native
owners. Existing `AoEPresentationGeometry` describes a selected shape, not a
parametric aiming rule; reuse its shape vocabulary and snapshot conversion while
adding only the missing passive aiming information. Current ordinary AoE action
metadata is not enough for a client to infer this from spell names.

Predictable native shapes can be presented locally. If a native shape/origin rule
cannot be represented faithfully, expose that prediction is unavailable and use
the existing preview request. Never approximate target admission or inspect
private action fields through a reflective server adapter to guess geometry.

Distinguish predicted geometry from predicted recipients. Recipient eligibility
also depends on native visibility/perception, self inclusion, relationship and
life-state policy. Expose only the rule policy already disclosed for that action
and use current public world facts for optional approximate highlights. Where
those facts/policies cannot support a recipient claim, predict geometry only and
obtain exact subjective recipients from Preview. The shared legal subject table
is not the universe of things hit by an AoE; directly targetable walls do not
automatically become AoE recipients. Test identical geometry with differing
recipient policy, hidden occupants, and deferred versus computed-empty effects.

Choices explicitly mark optional AoE effects as deferred. They do not carry each
aim's affected cells, names, UUIDs and counts. The selected-preview response
returns computed subjective geometry, affected positions and the recipient
summary when requested. A computed empty result is distinct from deferred data.
Predicted client effects are never accepted as native execution input.

## 4. Computation: avoid unnecessary work at its owner

### 4.1 Separate legal aims from preview materialization

Add an explicit player discovery materialization choice through the existing
functional/native owner. Keep rich discovery the default for native callers/AI:
AI decision construction and scoring consume eager affected cells and entities.

For `aoe_require_targets=False`, preserve the current source affordability check,
native/custom `get_valid_positions`, subjective range/visibility, aim compaction,
index assignment, distance and action metadata callbacks. Build admitted aim
records directly. In the current owner, footprint/recipient computation rejects
an aim only when the action requires affected targets; it is optional detail for
Fireball and Burning Hands. Avoid computing it, rather than computing it and
discarding it during serialization. Cover the analogous item-use AoE path too.

For `aoe_require_targets=True`, compute the geometry/recipient evidence necessary
to decide exact aim membership. Retain current native filtering for self,
faction, life state and custom candidates. Share existing per-discovery evidence
across equivalent variants when the native cache already proves equivalence.
Do not drop valid empty-ground casts from other spells as an optimization.

Keep detailed and deferred materialization from contaminating each other in the
native AoE cache: include mode in the relevant preview-cache context or keep bare
rows query-local. The application session cache also needs an explicit contract:
within an unchanged actor/seat/force-attack/revision/cursor, compact→rich and
rich→compact calls retain the same admitted options, indexes and generation.
Rich callers receive complete details, computed on demand if only bare options
were retained; compact callers do not trigger rich enrichment. Enrichment cannot
silently rerun admission with different indexes or mutate previously returned
models. Invalidate all materializations together when the admission context
changes. Test both directions and repeated calls; do not add a second admission
cache to work around a missing materialization check.
Preserve footprint topology invalidation. Do not add a second
tile eligibility cache or unbounded actor-origin history cache. Caching previously
solved Fireball floods across moves is a later measured option, not a dependency
of avoiding thousands of unrequested floods in the first place.

### 4.2 Compute one requested subjective preview

After normal retained-generation and selection checks, resolve the exact native
template and selected aim. Reuse `Entity._compute_aoe_at_position` and its current
propagation-footprint path for that aim, or extract that exact computation,
including propagation, visible-cell intersection and perceived recipient filters.
Do not call objective `get_all_targets`/`compute_objective` to populate a player
preview: that can disclose hidden occupants. Extend preview output with the
recipient summary currently available only in eager choices.

Do not substitute another shape method just because its name says subjective.
For example, Cylinder's current targeting method and Entity's eager discovery
apply different cell filtering. Selected preview must match the existing
discovery semantics, including its visible-cell clipping, rather than repairing
or silently adopting a neighboring geometry policy. Cover a Cylinder with hidden
cells and a blocker in rich-versus-selected-preview parity.

Retain the existing bounded current-generation preview cache, invalidated by the
same revision/cursor/context changes. Key it by exact action, ordered prefix,
extra positions, route preference and requested materialization. Cache completed
computations, including legitimate partial-prefix results with `can_confirm=False`;
a failed computation must not leave partial data masquerading as a ready preview.
Include retained preview memory and lookup cost in measurement.

Execution keeps ordinary native validation and objective resolution. It must
work with a valid command even when the client never requested a preview. Do
not invent a mandatory preview receipt, predicted-footprint checksum or new
confirmation handshake.

Today `execute_player_action` calls `preview_player_selection` internally to
check completeness. Separate required selection admission from optional effect
materialization at that existing owner. Commands retain identical prefix checks,
selected-route behavior and rejection reasons but request no optional subjective
AoE effect data before objective execution. A status-only cached result must not
satisfy a later detail request as if it contained a computed empty blast. Reuse
complete cached admission where valid, without creating a second rules path.
Measure both explicit Preview→Command and direct Command: deferral must not hide
an internal unrequested preview solve.

### 4.3 Bound other discovery work and account for the residual

The existing point-threat correction passes only the actor's cell to
`get_threathened_positions`, preserving its native close-pressure checks. Keep
it. In a profiled Fighter query, 203 calls drop 210.666 → 3.192 ms; this is owner-level
evidence, not an ordinary whole-system claim.

Profile remaining entity/object admission by source checks, candidate gathering,
target action binding/copy, rule validation, selected costs, contact solving and
DTO creation. Run target-independent checks once per variant where the native
owner already declares them independent. Share disclosed candidate enumeration
where its policy key is equal; still perform target-specific/custom validation.

Deep action copies and repeated object contact solves are measured candidates,
not blanket removal instructions. Before replacing deep copies, identify what
native validation can mutate and prove isolation across candidates and templates.
Reuse a native contact result only across the same validated query/inputs; do
not globally cache arbitrary callbacks or change their ordering. Make any next
change at the owning native boundary and demonstrate exact outcome parity.
If those costs remain material after the main rework, report and address them
before calling discovery optimized; do not silently drop this computation work.

## 5. Multiple targets and compound position selection

Keep the existing command model: discovery action index, ordered target-index
prefix, extra positions and route preference. Global subject/position references
are lookup identities, not a replacement for native selection indices.

| Native case | Contract to retain |
|---|---|
| Magic Missile / Scorching Ray | Repeated selections, projectile limits and `fill_primary` completion |
| Chain Lightning | Distinct recipients; branches constrained from the original primary, potentially outside caster primary range; object endpoints |
| Acid Splash | Individually admitted subjects do not make every pair legal |
| Primary-specific secondaries | Local indexes are scoped to the chosen primary; the same number can name another recipient for another primary |
| Entity then destination | Legal destination depends on the selected entity and current native placement rules |
| Wall/path placement | Next positions depend on the entire prefix and segment/total length, support and barrier rules |
| Movement | Preserve selected cost, normal/safe route choice, hazards and opportunity-attack evidence |

A primary binding can reference a shared secondary set. Preserve the distinction:
an absent secondary override inherits the ordinary action pool; an explicit
reference to an empty secondary set offers no secondary options. Only primary
bindings carry this override. Validate unique target indexes within each
applicable primary/secondary pool, never globally across branches/actions. Do not
flatten secondary-only subjects
into a primary set, or mistake independent membership for legal combinations.

The existing Preview endpoint remains the ordered-prefix authority: confirmable
status/reason, legal next targets and legal next positions. Return compact next
bindings using the same definitions. **Preview responses are self-contained:**
their subject/position table references resolve only within that Preview response,
including new landing or path coordinates absent from Choices. No Preview integer
implicitly points into a Choices table. These local offsets are not native target
indexes; the latter retain the selected action/primary context. This avoids a
second reference namespace and lets both SDKs validate a reply using the existing
request plus connection, without implicitly retaining another response. It may
repeat the small requested domain, not the full choices graph. Keep request,
generation and ordered-prefix correlation exact. Test colliding local offset 0,
new positions and obsolete-generation replies before freezing the schema; do not
add a new endpoint or a generic continuation engine.

## 6. Ownership and one-pass server projection

Today fresh server discovery retains native originals, creates a detached full
result through dump/validation, then repeats dump/validation for the caller.
Those boundaries protect native templates, admitted selections and caller
mutation. Remove the repeated representation, not the protections.

Native discovery establishes one session-owned admission snapshot and retains
the exact private execution templates. Its detached option values are the single
source for both what is offered and how a selection is resolved; the compact wire
tables are a lossless representation of that admission, not a second membership
or rules owner. Build them directly at the existing player boundary. Do not first
materialize the old rich wire tree and then normalize it. Factor already-shared
rows/sets before dumping; compare distinct values with typed keys/equality at the
necessary boundary, not by repeatedly serializing large graphs as JSON keys.
Include factorization/validation cost in the benchmark.

Server selection resolves exact local indexes and branch scope through that one
retained admission to the native template and selected values. Do not maintain
independent native-versus-wire legality decisions. Copy any aliased native option
values necessary to protect the retained admission from later mutable native
discovery caches, once at capture. A returned public model must not alias mutable
retained admission/native data. Preserve the
existing public rich API's detached-return behavior. The worker may encode a
private snapshot through a narrowly owned internal path if it cannot escape to
mutable callers; do not expose it as an ordinary public borrowed DTO.

Repeated choices for the same current discovery reuse its compact snapshot.
Any retained encoded data must stay within that current discovery; envelope
correlation/identity remains correct per request. No arbitrary historic cache or
new GC policy is part of this work. Measure live allocations and retained memory
alongside CPU, without altering native mutable event history.

## 7. SDK, protocol and client handoff

Regenerate the protocol schema, identity, field ledger, Python types and
TypeScript types from the canonical definitions. Change only the applicable
schema/version boundary; establish whether shared native type edits also affect
saved records before deciding their version. Existing handshake mismatch remains
explicit; do not silently serve two discovery semantics under one identity.

Both SDKs validate compact structure once and validate reference integrity in one
bounded pass: integer/range checks, domain kind, action-local indexes, secondary
set references and current response scope. Reject malformed references rather
than coercing them or treating them as absent. Cross-reference checks must not
revalidate every shared target object for every action that references it.

Provide lightweight lookup/selection helpers for action→options, binding→subject
or position, primary→secondary options, ordered command selections and optional
position→legal-actions indexing. Preserve structural sharing as read-only data;
this is an explicit documented consumer contract, with read-only TypeScript
helper views where expressible, not a claim of runtime immutability. Decoded
Python dictionaries and JavaScript objects remain ordinary values; do not add
deep freezes, proxies or defensive whole-graph copies. UI selection state lives
separately. Callers that mutate a shared snapshot mutate their own shared view,
never server admission. SDK helpers must not mutate it. The SDKs do not populate
JSON-schema defaults: helpers interpret explicit omitted defaults on lookup,
without normalizing or expanding every record. Document this migration from
consumer code that attached state to individual duplicated target rows.

Helpers must not reconstruct the former full object graph or attach consumer
state to shared target records. Measure
inverse-index construction separately and perform it only when requested.

Keep existing server query behavior: pending queries for a seat can supersede
one another, and an in-flight reply can still arrive. The handoff must explain
correlation/generation/action/prefix checks and discarding obsolete previews;
do not change scheduling/concurrency or introduce a mandatory request per frame.

Handoff examples must cover subject targeting, wall targeting, ground AoE with
local prediction, optional exact preview, repeated missiles, Chain Lightning
branches, entity destination, and safe movement. State precisely how a new server
and regenerated SDK are deployed together, and what client reducer/selection
changes are required. Update the existing SDK/protocol READMEs; no NDClient edits.

## 8. Implementation stages and validation gates

| Existing source owner | Responsibility in this rework |
|---|---|
| `dnd/entity.py` | Native target admission, legal aim collection, AoE/item-use computation and existing caches |
| `dnd/actions_functional.py` | Rich/native API, ordered selection validation and optional preview materialization |
| `dnd/core/base_actions.py` | Existing action/target metadata and selection contracts; no server imports |
| `dnd/core/aoe.py`, `dnd/core/presentation_geometry.py` | Native area semantics and passive geometry export |
| `dnd/player/session.py`, `dnd/player/selection.py` | One retained admission, mode enrichment, detached projection and selection lookup |
| `server/protocol.py`, `server/worker.py` | Canonical wire records and ordinary choices/preview/command integration |
| Existing SDK generators, Python transport and TypeScript `src/index.ts` | Generated types/schema, single admission, reference checks and lookup helpers |

Add passive player-layer records or small projection functions only where needed
to keep these responsibilities and import direction clear. Do not migrate the
engine or copy its rule implementations into transport code.

| Stage | Work and owner | Exit evidence |
|---|---|---|
| 0. Baseline | Temporary existing Gallery and small-scene diagnostics | Raw choices, target counts/bytes and separated native/copy/encode/SDK clocks; preserve all samples |
| 1. Contract design | Passive records and relation mapping at player/selection/protocol owners; reviewers | Round trips of admitted options, compact compound fixtures, complete preview-domain mapping, no ambiguous defaults or alias ownership |
| 2. Native computation | Separate player aims from optional AoE detail; selected subjective preview | Rich/deferred exact eligibility parity, required-target cases, AI unaffected, execution without preview |
| 3. Retention/projection | One owned compact snapshot and native selection resolution | Public mutation isolation, stale/seat/context rejection, repeat-query correctness; no full-result double conversion on worker path |
| 4. Wire/SDK | Canonical schema, generation, bounded reference admission and lookup helpers | Both SDK suites and HTTP/preview/command contract checks; malformed references rejected; no eager expansion |
| 5. Residual compute | Profile remaining entity/object validation/copy/contact work | Targeted owner changes only where measured and proved; no callback bypass or rule change |
| 6. Integrated qualification | Live Gallery, compound scenes, replay/receipt checks and scale axes | Correct native results, disclosed intermediate records unchanged, ordinary timing/bytes/memory reported separately from profiles |
| 7. Handoff/cleanup | SDK docs, final reviews, temporary production instrumentation removal | Concrete client migration, preview reflects actual status; correctness and ordinary measurement rerun after removing probes |

Keep each stage reviewable. Do not call stages 3–7 complete based on offline byte
prototypes. Do not introduce cross-request deltas, persistent tile spell flags,
compression experiments, compiled code or a new query scheduler as prerequisites.

### Correctness matrix

- Exact action variants, ordered targets/local indexes and availability/cost
  reasons match rich native discovery. Compare values without sorting away
  causal/selection order. Same-runtime comparisons need no UUID normalization.
- AoE: empty-area casts; required-target filtering; blocked/connected propagation;
  hidden occupants; Cylinder visible-cell/blocker parity; self/allied/dead filters;
  item-sourced origins; core shapes;
  detailed discovery before/after deferred discovery; unavailable custom preview.
- Subjects: creatures and objects, multicell contact differences, target-dependent
  costs and mutable template isolation; preserve custom validation behavior.
- Compound selections: all cases in section 5, full ordered prefix and partial
  allocation, invalid combinations rejected without spending, and valid execution
  with no preview request.
- Retention: repeated discovery, compact→rich→compact and rich→compact→rich
  calls in the same unchanged session, caller mutation, changed actor/seat/force-attack,
  cursor/revision/generation expiry, out-of-order preview responses and bounded
  preview-cache retention. Do not invent thread races in the single worker.
- Wire/SDK: real captured replies plus small compound fixtures; empty versus
  inherited secondary pool; self/no-input bindings; invalid/out-of-range/wrong-kind
  references; new Preview-only positions and colliding local offsets; protocol
  identity mismatch; omitted defaults and helper non-mutation; same helpers
  usable without expanding shared trees.
- Integrated: ordinary choices→preview→command, public event/receipt sequencing,
  existing tile field updates and native history stay intact. Domain tests cover
  detailed rule matrices; HTTP/SDK tests cover admission/wiring, not fake rules.

Use the smallest relevant existing tests: action discovery, position costs,
Chain Lightning, entity-destination selection, window/object access, player
session admission and transport. Add only missing observable cases after reading
HOW_TO_TEST.MD. No private-call-count assertions as gameplay proof. Performance
operation counts belong in temporary diagnostics, not frozen implementation tests.

### Performance matrix

Measure native admission, optional geometry actually solved, target construction,
detachment/projection, factorization, validation, encoding, actual raw bytes,
pipe/HTTP, SDK decode/admission, optional inverse index and selected-preview
latency. Report cold/warm samples and retain normal GC. Native profiling overhead
must not be presented as ordinary latency.

Run the unchanged Gallery workload and exact command semantics before/after.
Keep native observer order cohorts and outliers visible. Add bounded scenes that
vary aim count, affected area, same-eligibility slot variants, subject count,
primary/secondary fan-out and repeated hover. Hold local rules/output fixed when
varying unrelated map size or retained history. Record necessary output growth
instead of claiming all target enumeration is constant-time.

Demonstrate that optional AoE footprint solves depend on requested previews,
not all legal aim cells; repeated equal sets do not create repeated DTO trees;
same-generation reads reuse the owned compact snapshot; selected-preview cost
does not hide a deferred full rediscovery; direct command admission does not
materialize an unrequested subjective AoE preview before native execution.
Report the residual per-target native
cost honestly. A smaller packet alone does not satisfy computation acceptance.

## 9. Review and current state

Required reviewers: plan-adherence/anti-slop reviewer, anti-OOP reviewer, and a
server/SDK selection-contract reviewer. Reviews must inspect this complete plan,
not merely endorse the general idea. Record their concrete corrections and final
disposition here before marking the plan ready.

| Independent review | Final disposition |
|---|---|
| Plan adherence / anti-slop | Approved; final rereview found no blocking scope or unnecessary-mechanism issue |
| Anti-OOP / native computation | Approved; native owners, passive tables, AI isolation and subjective geometry boundaries preserved |
| Server / SDK selection contract | Approved; binding roles, response-local references, recipient prediction and SDK ownership/default behavior are explicit |

Corrections incorporated before approval: rich↔compact session enrichment within
one admission generation; required command selection validation without optional
AoE preview computation; one retained admission authority; completed nonconfirmable
preview caching; exact Entity/Cylinder subjective semantics; self/no-input and
primary/secondary binding roles; self-contained Preview reference domains;
separate geometry/recipient prediction; documented read-only consumption without
claiming runtime frozen SDK data or implicit default population.

These are approvals of the plan, not evidence that the planned implementation
passes its correctness or performance gates. All three reviewers inspected the
complete document and their revised sections read-only.

Current implementation: the normal Python server worker now uses compact shared
choices and self-contained compact Preview domains, with optional AoE computation
at the native owner. Public rich/native discovery remains detached and complete;
compact/rich calls share one admission generation. Both SDKs and supported
acceptance consumers are migrated. Schema 8 is generated; saved PlayerSequence
schema remains 5. The earlier tile field updates remain intact.

Independent source review finds no rule-owner, ownership, DAG or framework blocker.
It identified a native include_dead=True deferred-preview context edge case; the
fix retains one private query flag per action row, avoiding a dictionary on every
aim. Its focused verification is part of the final native batch.

The same-world audit passes all 58 Gallery choices and 40,472 target occurrences:
exact metadata, costs, native indices and order, excluding only intentionally
deferred affected_* values. Queries generate no events or RNG changes. Actual
compact replies pass both SDKs; current suites report 82 Python and 55 TypeScript
tests plus the TypeScript build. Native/compound/server tests cover mode order,
public mutation, item origins, hidden recipients, scoped branches, repeated
missiles, landing/path domains and direct command admission.

First diagnostic choices55 result: 2,399,276 → 267,836 bytes (88.8% smaller),
301.59 → 172.28 ms dispatch, 9.71 → 4.24 ms JSON encoding, 38.23 → 5.32 ms Python
SDK decode. The before/after diagnostic observer orders differ; this is not a
paired latency distribution. Normal-worker client-timed runs in the same
Sorcerer→Fighter order as CP32-repeat report choices55 188.55 and 193.21 ms versus
362.25 ms previously. Two samples do not establish percentiles. Movement command50
receipts are 102.16 and 74.14 ms; the separate 9.5 ms goal is still unmet.

New capture ownership uses a memoized typed leaf conversion. An alternating
same-input study on 4,199 bare targets measures 29.80 → 12.24 ms median versus
generic deepcopy, with exact values. This is a capture microbenchmark, not a
second whole-query speed claim. Native residual profiling still finds repeated
object-contact/validation work material. Current side-occupancy checks now ask a
fresh boolean from authoritative Tile bands instead of allocating defensive UUID
sets. They retain all crossing predicates and do not cache mutable callback
results. General early radius rejection or cross-validation contact reuse was
rejected: overridable origins/ranges, dynamic costs and snapshot/validation hooks
intervene, and object anchors are not valid contact-distance lower bounds.

Selected-effect/direct-command, retained-allocation, bounded scaling, HTTP and
ordinary receipt/cold replay qualification are recorded below. Final source and
evidence review found no blocking ownership, rules, DAG, scope or framework issue.
The known nearby-door test fails with the prior implementation as well; no
unrelated door rule change is included and no full-suite pass is claimed.

Source/environment: C: checkout via WSL; Python 3.13.12 in the existing
`/home/tommaso/.cache/dnd-engine/venv`; no environment synchronization. Evidence is
in `.runtime/server-latency/checkpoint33-{choices,point-query,point-audit}/` and
the `study_choices33*.py` scripts. The existing HTML preview must show this plan's
stage and distinguish prototype estimates, implemented checks and measurements.

## 10. Implementation qualification

All evidence below uses normal GC. Temporary probes live under `.runtime/` and
are absent from the production choices path. No C++ module is needed. Existing
opt-in movement diagnostics are unchanged by this query rework.

### Ordinary Gallery queries

The final-source Gallery completes the same 58 semantic commands, 100 records,
and final position (68,20), with 5,195,706 recorded bytes. The three ordinary
worker runs have Sorcerer→Fighter observer order, matching CP32-repeat:

| Lane | Choices 55 total request | Python SDK admission | Movement command 50 receipt |
|---|---:|---:|---:|
| Earlier CP32-repeat | 362.25 ms | Not separately captured | 89.29 ms |
| CP34-plain | 188.55 ms | 5.77 ms | 102.16 ms |
| CP34-repeat | 193.21 ms | See raw sample | 74.14 ms |
| CP34-final, source frozen | 191.11 ms | 5.31 ms | 98.50 ms |

These are individual samples, not percentiles. Choices improve approximately
47%; movement receipts do not demonstrate improvement from this change. The
ordinary worker has no action-phase hooks or profiler. The client retains
Gallery stream/reduction/ACK timings, raw choices and SDK decode probes; this is
not an uninstrumented browser measurement. Each lane includes a supplemental
`measurement-qualification.json` correcting the recorder's historical generic
diagnostic label without replacing its original values.

### Requested effects and repeated queries

Six actual worker combat samples, alternating direct Fireball command and
Preview→Command, produce identical damage and two seat records per command.
Optional discovery solves are zero; explicit Preview performs one subjective
solve, its repeat performs none, and both command paths perform none before
objective native execution. Shatter and Thunderwave still require 42 and 1
discovery solves respectively to establish legal membership in this fixture.

- Selected Preview: 0.912–0.990 ms; repeated current-generation Preview:
  0.096–0.141 ms. These include worker projection, excluding HTTP/encoding.
- Same-generation Choices dispatch: 0.051–0.071 ms; no rediscovery.
- One retained selected preview: 963 serialized bytes, one cache entry. This
  measures the existing cache's serialized accounting, not live object size.
- Direct command: 167.40, 180.85 and 368.90 ms. Preview→Command: 166.71,
  166.83 and 169.82 ms. Preserve the direct outlier; this is no claim that an
  extra preview accelerates native execution or eliminates GC tails.

Evidence: `checkpoint34-scale/selected-command.json` and
`choices34_selected.py`. Operation counts are temporary diagnostic evidence,
not private-call-count gameplay tests.

### Bounded output and allocation axes

Three samples per scene; timings below are medians. Actor/world setup is outside
the clocks. The area axis uses the same authored Fireball, same 112 legal aims
and different selected aims, producing different visible clipped footprints.
It does not modify authored spell geometry or claim a pure radius experiment.

| Scene | Aims | Shared sets | Native admission | Capture | Selected preview | Reply bytes |
|---|---:|---:|---:|---:|---:|---:|
| Fireball, selected footprint 49 cells | 112 | 1 | 1.12 ms | 1.02 ms | 0.56 ms | 9,915 |
| Same aims, selected footprint 23 cells | 112 | 1 | 1.06 ms | 0.93 ms | 0.49 ms | 9,915 |
| More visible aims | 316 | 1 | 1.91 ms | 2.05 ms | 0.64 ms | 23,827 |
| Double unrelated map width | 112 | 1 | 1.13 ms | 0.93 ms | 0.71 ms | 9,915 |
| Burning Hands, one slot variant | 72 | 1 | 1.04 ms | 0.58 ms | 0.29 ms | 7,301 |
| Burning Hands, three slot variants | 72 each | 1 | 1.32 ms | 0.68 ms | 0.27 ms | 11,845 |
| Fireball, six nearby subjects | 112 | 1 | 1.46 ms | 0.95 ms | 0.67 ms | 9,915 |

All 21 samples perform zero optional discovery area solves and one selected
solve. Three equal variant sets carry 216 logical links through 72 stored
bindings. Additional aims still require admission and output work; the design
does not make enumeration constant-time.

A separate synthetic same-scene tracemalloc pass compares native rich discovery
plus the prior detached result against deferred discovery plus retained native
and compact results. Current traced allocations are 1,936,326 → 488,583 bytes;
peaks are 2,168,278 → 524,007 bytes. This is neither RSS nor whole-game retained
memory: tracing starts after world setup and excludes native history, world and
wire bytes. No timing claim uses this traced pass. Evidence:
`checkpoint34-scale/{timings,memory}.json` and `choices34_scale.py`.

The native boundary boolean microbenchmark separately measures 328 queries over
82 objects: 17.425 → 16.668 ms median (4.55%), with the same 154 admitted contacts
and unchanged events/memberships. Its scope is that owner, not the whole query.

The Fireball subject axis above varies perceived recipients, not the compact
subject table. A separate registered Chain Lightning fixture exercises that
table and primary-scoped secondary branches: 4 → 7 admitted subjects/primaries
(including the caster, as the native spell allows), 8 → 34 secondary links,
5 → 8 shared sets, and 3,236 → 5,541 bytes. Three-sample native-admission medians
are 2.23 → 3.39 ms and capture medians 0.27 → 0.44 ms. Reconstructed compact
primary/secondary values equal native values exactly; no branch indexes are
flattened. Evidence: `checkpoint34-scale/fanout.json`, `choices34_fanout.py`.

For a bounded history axis, actual completed saving throws grow the same native
history from 583 → 1,283 → 7,583 event versions. Whole compact values remain
identical, 9,915 bytes at every point. Three warm samples per point give native
admission medians 0.57 / 0.56 / 0.61 ms and capture 0.63 / 0.68 / 0.67 ms. No
history is archived, frozen or removed; no GC settings are changed. There is no
generation-2 collection within these query clocks, so this does not establish
long-history GC-tail behavior. Evidence: `checkpoint34-scale/history.json`,
`choices34_history.py`. The independent plan/anti-slop reviewer checked both
scripts and artifacts and closed these bounded qualification gates.

### Focused and live validation

The final-source focused batch passes **46 tests**: compact session choices,
compound selections, protocol/schema, world retirement, movement preferences,
deferred native AoE and boundary contacts. Prior related native batches pass
45 regressions and the final native owner's 28 focused cases; these batches
overlap and are not added together. Both SDK suites pass **82 Python** and
**55 TypeScript** tests, and the TypeScript build. Both SDKs also admit all 58
captured actual compact choices. The broader contact/transport batch previously
passed 53 cases and reproduced the known nearby-door failure with the old
implementation; this is not a full-suite pass claim.

Production HTTP + SDK finite fights reach terminal state:

| Scene | Commands | Public records across both seats | Observed selection |
|---|---:|---:|---|
| Fireball / six goblins | 2 | 8 | One aim, six affected goblins |
| Magic Missile | 42 | 126 | Three casts preserve A→B→A ordered repeated recipients |
| Wall of Fire | 14 | 42 | Initial vertex (9,7), then Preview-local endpoint (10,8) |

The first missile smoke's eight-command harness budget was too short for the
fight; its diagnostic is retained and the complete 128-budget rerun finishes in
42 commands. The first wall run finished after 19 commands with only its first
confirmable vertex. The acceptance policy now deliberately appends one offered
endpoint before confirmation; the 14-command rerun exercises that continuation.
Neither adjustment changes native rules or client application code. HTTP clocks
from these overlapping functional checks are not used as production latency
benchmarks. Evidence folders: `checkpoint34-http-fireball`,
`checkpoint34-http-missile-complete`, `checkpoint34-http-wall-vertices`.

Cold HTTP replay admits all six audience prefixes and **176 records** through
the SDK and native reducer, including public reference closure, ordered command
numbers, byte counts and terminal boundaries. Evidence:
`checkpoint34-http-replay.json`.

The independent Gallery audit checks four CP34 lanes: **400 actual records**,
**232 exact command receipt/cursor/clock bindings**, all 58 ordered command
semantics against prior cohorts, closed public occurrence references and native
reduction. Both SDKs validate all 400 journal records. Each route ends at (68,20)
and sequence 99; the Gallery route stops at its goal, not at combat terminal.
On the final lane, the earlier tile field changes equal synthetic full records
at **273 world-event prefixes** and all **100 reduced states**, covering
**2,950 field updates**. No causal arrays are sorted or UUIDs normalized. These
checks prove current stream integrity and representation equivalence, not
independent old-native event parity. Evidence under `checkpoint34-final/`:
`qualification.json`, `typescript-journal-qualification.json`,
`tile-fields-audit.json`.

### Optional inverse lookup and handoff

Both SDKs build the optional position→action inverse from already admitted
Choices 55: 1,347 positions and 4,185 primary position memberships. Subject and
self options account for other target occurrences; secondary-only bindings do
not become primary eligibility. The original snapshot is unchanged, defaults
are not populated, and no full target graph is reconstructed.

Nine construction samples per SDK, recorded separately from decoding: Python
first 0.846 ms / warm median 0.826 ms; TypeScript first 0.663 ms / warm median
0.375 ms. These measurements overlap functional qualification and are not
idle-machine or production latency samples. All samples, including Python's
2.921 ms outlier, remain in `checkpoint34-final/inverse-{python,typescript}.json`.
The index is built only when requested, not per hover or automatically on every
reply.

The [protocol handoff](../sdk/protocol/README.md) and both SDK READMEs describe
lookup-based action/subject/wall selection, AoE geometry and recipient limits,
optional exact Preview, repeated/branch targets, destinations and paths, safe
movement, missing-field defaults, read-only consumption and stale-response
handling. Deploy the ordinary server and rebuilt/reinstalled schema-8 SDK
together; old clients fail the existing identity handshake. NDClient migration
is the receiving frontend task. This checkout contains no new production
measurement probes; temporary experiments remain under ignored `.runtime/`.
The HTML preview reports final ordinary samples separately from the first
diagnostic call tree and keeps the 9.5 ms movement goal visibly open.

## 11. Post-integration server review and agent sandbox compatibility

The human requested a fresh anti-slop/general server review and agent sandbox
update while frontend integration proceeds. The review covers the current server,
session ownership and selection boundaries, SDK consumers, and active Monty
sandbox. Retired code and native AI's separate rich contract are not migrated.

Concrete compatibility findings: Monty's installed local SDK is still schema 6;
its executable `examples/scouts.py` reads `valid_targets`, and the session guide
describes `next_targets`. Update that sample and guide to schema-8 shared domains,
refresh the installed local SDK, and document required restart/source reload.
Keep existing transport, authority, commands and raw event history; no adapter
that reconstructs the old target graph, new callbacks or sandbox framework.

| Testing boundary | Definition |
|---|---|
| Requested behavior | Existing agent workspace can discover and select through schema 8 |
| Boundary | Real MCP/Monty execution → installed SDK → ordinary server |
| Input | Shared choices, response-local previews, existing two-game scout trial |
| Expected output | Valid native selections and receipts, complete matches, preserved archive/source-export isolation |

Read-only reviewers: plan-adherence/anti-slop, anti-OOP/native-server, and
SDK/sandbox compatibility. Run the existing sandbox and server boundary tests,
then the real two-game workspace trial. Fix reproduced compatibility regressions
within these owners; record unrelated findings without redesigning them.

Sandbox migration is implemented: direct shared-table lookups in the sample,
correct Preview-local and sparse-default guidance, tile-field instructions, and
explicit package-refresh/restart guidance. The local non-editable SDK install
was refreshed with the locked Monty project and now has the same schema-8 digest
as the server. The host callbacks already forward admitted SDK values correctly;
no compatibility expansion or additional callback was added. Historical evidence
and exported source bundles are not rewritten; old helper source needs migration.

Validation: nine Monty tests pass in 7.06 seconds. The actual two-game MCP/Monty
trial passes with the installed SDK: 3 + 13 committed player commands, 12 + 36
records, both native matches terminal. One workspace retains both archives
after their servers stop; old authority is rejected, and exported helpers work
in a fresh workspace without saved globals or game references. Evidence:
`.runtime/monty-schema8-workspace/proof.json` and
`.runtime/server-latency/checkpoint35-sandbox-{sync,tests,trial}.log`.

The broader server batch passes 34 tests in 68.48 seconds: HTTP admission,
transport lifecycle, bounded delivery, service/worker reuse, session admission,
schema and world retirement. This is scoped functional qualification, not a
load test, whole-suite pass or comprehensive security audit. Evidence:
`checkpoint35-server-review-tests.log`.

A server review also reproduced a preexisting loss of submitted selections:
Command discarded additional position/self bindings while converting extras
to UUIDs, then executed the first choice despite Preview rejecting the full
selection. Move, Fireball and repeated Dodge reproduce the defect. The bounded
fix rejects UUID-less extras at this lossy conversion boundary and preserves
the remaining ordered UUID list. Native selection validation continues to own
cardinality, repeats and branch rules; no extra AoE computation or parallel
selection implementation is needed. All six new cases in
`tests/player/test_worker_selection_cardinality.py` pass in 4.68 seconds:
three malformed selections reject without changing cursor, RNG, position or
HUD/resources, and three single choices execute without a Preview request.
The anti-slop/anti-OOP reviewer approved the installed guard and regression
scope. No further material defect was found in the inspected ownership,
stale-context, forwarding, reference-validation or import-DAG paths. The server
README's stale schema number is corrected. The existing HTML preview records
these findings and completed checks separately from the latency measurements.
