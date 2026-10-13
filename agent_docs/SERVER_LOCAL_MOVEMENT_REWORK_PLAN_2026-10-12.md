# Server movement: preserve local work from mutation to publication

Date: 2026-10-12. Status: independently validated; implementation authorized on
2026-10-13; steps 1–5 in progress. This document answers the human's request for a
complete, validated plan after rejecting incremental speedups as sufficient.

## 1. Objective and boundary

Make ordinary movement substantially faster and make its cost depend on changed
inputs, affected observers and required output. Increasing distant world size,
unrelated conditions, explored memory or retained history must not introduce
corresponding work into an otherwise equivalent local movement command.

The scope is the existing server path: movement/rules, GridMap, sensory
production, event routing and handlers, native event capture, audience projection,
retained current state, encoding and committed publication. Inspect the whole path; change the owners
responsible for demonstrated unnecessary work. This is not a replacement engine.

The human additionally requires full temporary instrumentation of this path,
progressively drilling into expensive work, including repeated serialization and
event handlers whose work grows with map size. Build that diagnostic coverage
before reworking owners, use it throughout the rework, then remove the added
runtime instrumentation and verify the final result without it. Section 8.3
defines coverage, drill-down and removal.

The user initially authorized planning and validation, then explicitly authorized
implementation. Do not treat validation of this document as completed work or permission to change product
rules. The client renderer, prediction, graphics, asset pipeline, protocol
serialization contract, worker concurrency model, startup redesign and unrelated
gameplay features remain outside this rework. Do not edit NDClientGodot or read
other chats. Coordinate a native-client acceptance run with the human when needed.

The four testing-boundary statements required by HOW_TO_TEST.MD are:

| Item | Definition |
|---|---|
| Requested behavior | Fast, locally bounded server movement with unchanged gameplay and disclosure |
| Observable boundary | Ordinary SDK choices/preview/command through committed, recorded public operation and canonical reduction |
| Input | The live Crypt-to-Lantern-Gallery route, plus small native scenarios and controlled scaling variants |
| Expected output | Identical semantic state and intermediate observations, rules, causal ancestry/order, receipts and cursors; materially lower latency and no scans proportional to unrelated retained data |

## 2. Evidence and starting state

Read AGENTS.md, RECOVERY_PLAN.md and HOW_TO_TEST.MD before execution. The recovery
file retains the client plan reference and links this server plan; this document governs the explicitly
requested server movement rework. Historical context is in
[HISTORY_BEFORE_ME.md](HISTORY_BEFORE_ME.md),
[the sensory study](SENSORY_EVENT_FLOW_STUDY_2026-09-12.md),
[September's plan](PERFORMANCE_FIX_PLAN_2026-09-12.md), and
[its results](PERFORMANCE_REPAIR_RESULTS_2026-09-12.md). The broader existing
[server plan](SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md)
provides measurement and contract precedent, not additional feature scope.

Relevant history:

- At July commit `4ebe523`, `_apply_hint` treated changed light cells separately
  from changed sight geometry and updated local contacts. Its old contact types
  are not a drop-in implementation for today's rules.
- Commit `a57d104035a` recovered stationary entity-contact updates and restricted
  owner refresh reuse. It deliberately retained full solves for moving observers
  and light changes; its small encounter measurements made no large-map claim.
- Current GridMap already emits an atomic light delta per step and indexes cell
  subscribers. Senses already skip redundant LEFT work and reuse a current field
  after a light child. Capture already has lineage/event indexes and checkpoints.
  Keep these mechanisms; do not rebuild them under different names.

Measurements use the C: checkout through WSL, Python 3.13.12, and the existing
Linux environment `/home/tommaso/.cache/dnd-engine/venv`. Imports/setup are outside
command timings. The backend-only driver executes normal live SDK requests; it
does not replay recorded commands into a fake server or bypass mechanics.

| Current evidence | Observation |
|---|---|
| Plain baseline, 16 Gallery moves | Median worker dispatch 1,984.6 ms |
| Initial two optimizations, same cohort | Median worker dispatch 753.2 ms |
| Plain command 50, six cells | 2,231.8 → 817.3 ms dispatch; execute 1,798.1 → 714.2 ms; audience capture/projection 433.3 → 102.9 ms |
| After-change CPU profile, command 50 | 18 complete sensory solves, 103,144 boundary-route queries, 72 full sensory snapshots, 18 world updates, about 4,130 object conversions |
| Route comparison | 58 commands, sequence 101, final position (68,20), 1,761 disclosed tiles, 360 objects; action/actor/position/HP/disclosure counts and per-command sequences match |

These are a small-cohort measurement and diagnostic counts, not stable p95
results or full intermediate-event equivalence proof. Profile times include
instrumentation and overlap; do not add inclusive spans. Raw evidence is in
`.runtime/server-latency/{before,before-plain,after-plain,after-diagnostic}/`.
The temporary orchestration is `/tmp/dnd_server_gallery_profile.py`; it reuses
NDClientGodot's `tools/gallery_recording.py`, `profile_host.py` and
`profile_worker.py` read-only. Original native-client evidence is in that repo's
`generated/live_pipeline_diagnostic.json` and the run directory
`.runtime/player-runs/20261012T212010.040988Z/`.

The original measured source was clean Git revision
`dbbc125aa02da3a8d8cf2b36688ecf1cbe93b877`. Four files now contain uncommitted
investigation changes: `dnd/core/gridmap.py`,
`dnd/blocks/sensory.py`, `dnd/player/projection.py`, and
`tests/engine/test_sensory_movement_origin.py`. The projection change removes a
proved quadratic observed-object scan. The optical guard evaluates actual
contributions once per solve, but still scans spatial-owner footprints and is an
intermediate optimization. Preserve useful behavior/tests; supersede that scan
through the ownership work below. These changes stay frozen during this
planning-only turn. Step 0 records the original baseline and current candidate
separately, then identifies which investigation changes are retained or replaced
by each owner change. The 753.2 ms candidate is not the original baseline or
the approved final architecture. No automatic reset or blanket replacement.
The selected existing suite passed 114 cases; the six movement-origin cases,
including two new optical regressions, also passed. This is starting evidence,
not validation of the unimplemented rework.

## 3. Cost model and performance objectives

For each committed step, distinguish:

- the moving observer's bounded sight/range domain;
- the moved light's old/new reach and actual changed illumination cells;
- stationary observers whose evidence depends on those cells;
- changed contacts, hazards, surfaces and disclosed facts;
- current action/reaction descendants and required serialized bytes.

The intended work is: movement legality and reactions + required mover/light
geometry + affected observation updates + capture of this operation's evidence
+ audience-specific changed facts + encoding/recording of required output.
Do not multiply all observers by all visible cells by all objects for a local
illumination change. Do not copy all explored/history state per sensory child.
Where every observer is genuinely affected, work can grow with that population.
Audience iteration and protocol-required per-seat output are real costs and
must be reported; unrelated native observers must not cause extra field solves.

Moving the observer can change every sight ray. A bounded full solve is legitimate
there. Its cost must be accounted for and optimized, not hidden behind a claim
that all movement is constant time. Initialization and actual bulk world changes
also have broader costs. A local move must not grow with unseen distant rooms or
old event history when its local inputs and output are held fixed.

The human updated the performance objective on 2026-10-13 to **100× less time**.
Against the step-0 ordinary six-cell command-50 result of 948.73 ms, the equivalent
SDK-to-committed-record target is approximately **9.5 ms**. This supersedes the
initial planning proposal of 50 ms median / 100 ms p95. The single-command ratio
is progress evidence; a qualifying cohort and distribution are still required.
Use the same native command and observation endpoint, with equivalent measurement
cadence for before/after comparisons. The original 10 ms receipt-poll interval
cannot resolve this target: refine the runner cadence, retain actual elapsed
transport/probe time, and never subtract an estimated overhead from results.
The target clock starts immediately before SDK `submit_command`, after ordinary
choices/preview, and stops when the SDK observes a `committed` receipt for that
command number and its result cursor. In `server/host.py`, `_exchange` commits
the encoded record to the recording index and updates publication before `run`
stores this receipt. Verify that same cursor is retrievable. This endpoint
includes command transport, queuing, execution, encoding, recording and receipt
delivery; it excludes subsequent probe file writing and canonical reduction.
Report discovery/preview, host recording/publication, receipt polling cadence,
stream arrival, probe reduction and ACK separately. Never subtract polling or
probe interference from reported elapsed time; use host timestamps to explain it.
The existing worker-dispatch figures are attribution, not this end-to-end metric;
step 0 must measure the selected metric for a comparable starting state.
Reaction-bearing moves and unusually large disclosures
remain visible cohorts with their own counts and timings. The older server
plan's ordinary-command p95 ≤250 ms / max ≤500 ms is a historical ceiling, not
a stopping point for this rework.

Both speed and scaling evidence are required. Do not call the rework complete
while hundreds of milliseconds remain unexplained, while the target is unmet,
or while unrelated-data scans remain in the normal movement path. If necessary
semantics prevent the proposed target, report the measured remaining cost and
bring the explicit tradeoff to the human; do not silently weaken the objective.

## 4. Correctness constraints

1. Keep every committed movement step, opportunity reaction, interruption,
   rule handler, and causal light/sensory child at its current boundary. Do not
   defer perception to the end of a move or merge away intermediate sightings.
2. Commit authoritative spatial inputs before any pre-completion callback can
   observe them. A child may carry the after-value before its parent's terminal
   event; projection must retain that ordering.
3. Preserve visual versus nonvisual contacts, sense ranges, passive perception,
   stealth/invisibility, creator-only knowledge, effective brightness, hazards,
   and movement/path invalidation. A subscription is not a visibility grant.
4. Preserve directed wall exit/entry evidence, multicell objects, heights,
   windows/doors, fog/darkness, and upper-volume surfaces. Losing one contributing
   face/cell must not erase another valid contact route.
5. Preserve audience-specific knowledge at each event. Hidden mutations do not
   refresh remembered values. Loss of a current contents grant clears contents;
   discovering one object does not disclose hidden attachments.
6. Preserve deterministic ordering within a run, parent/lineage identities,
   intermediate after-values, cold replay, receipts, revisions and cursor rules.
   Earlier detached snapshots/packets must not change when live state changes.
7. Existing ECS systems own work; entities/components hold their existing data.
   Add no generic dependency engine, event bus, transaction framework, alternate
   journal, reflective capability detection, late imports or import cycles.
8. Keep normal runtime GC, rules, logging and protocol behavior enabled. No
   artificial pauses or scheduling changes may hide work outside measurements.

## 5. Authoritative dependencies and owners

| Changed input | Owner and existing evidence | Required affected work |
|---|---|---|
| Entity position/occupancy | GridMap committed LEFT/ENTERED, old/new positions, step lineage | Mover geometry; stationary subject contact; relevant hazards, paths and reactions |
| Illumination | GridMap light delta and `light_level_map`/hint cells | Effective light/visibility in dependent optical cells; dependent contacts and volume surfaces |
| Physical optical/propagation topology | GridMap channel revisions, placements, incident sides | Mark dependent fields stale; recompute required geometry before observation |
| Conditional optics | Explicit optical contributions and authoritative spatial-condition footprints/state | Reconcile changed owner cells after owner settlement; invalidate dependent optical evidence |
| Observer capabilities | Senses/condition/turn after-values and native capability checks | Rebuild affected sense domains; perception-only changes refilter relevant contacts/hazards |
| Object state/location/support | Recorded object/tile/item facts, previous/current placement | Update directly changed objects, incident faces, contents and composite dependents |
| Sensory knowledge | Existing SensoryUpdateEvent deltas and observed source references | Project new/lost/changed grants at this source-order position |
| Event routing and handler work | EventQueue position/trigger registries, native predicates, handler identities and dispatch evidence | Admit exactly the required ordered handlers; measure discovery separately from invocation and nested descendants |
| Operation history | EventQueue lineage/version indexes and CaptureCheckpoint | Traverse current roots and newly consumed evidence, preserving referenced historical versions |
| Audience/current canonical state | ProjectionState, AudienceRuntime, existing reducers | Apply changed facts without repeatedly cloning unrelated remembered state |

### 5.1 Local optical inputs

Use GridMap's existing explicit optical contribution map and Tile condition
membership. Capture local query-ready values once over the bounded region needed
by the current solve, then reuse them across its rays. Evaluate each local
condition's native per-cell predicate against settled state. This is a call-local
snapshot, not a new persistent active-contribution cache or selected fog registry.
No query scans every spatial condition to discover whether local optics exist.
Preserve owner identity, multiple contributions sharing one UUID, and
`excluded_owner_uuid` behavior for volume sight.

Cover every tested ray cell and volume entry/preceding-light sample, including
explicit contributions on absent support cells. Optical input collection grows
with local cells and their memberships; unrelated remote and nonoptical owners
add no work. Local nonoptical owners are checked once rather than for every ray.
Retained observer invalidation still belongs after authoritative footprint,
suppression and anchor settlement, before dependent child publication. The
existing `set_spatial_condition_positions` alone is too early for that invalidation.

Validate activation, movement/resizing, partial displacement, suppression and
restoration (including parent contributions), anchor suspension/resumption,
removal, existing failed-mutation/rollback behavior, tile removal and reset.
Explicit contribution APIs retain their publication behavior. Add neither
duplicate sensory events nor rollback where the current owner has none.

### 5.2 Retained observer evidence and local invalidation

Extend the existing ObserverField/Senses data, separating:

- physical optical candidates and per-sense propagation reach;
- range/obscurement evidence establishing eligible sight modes;
- current illumination-filtered visible cells/effective light;
- concrete evidence for affected entity, center-object and boundary contacts;
- volume dependencies and the observer inputs under which evidence was resolved.

Use existing SpatialSensesSystem registration/subscriptions. Mark affected
observer channels dirty at the spatial commit boundary before nested callbacks.
Keep that delivery within the current dependency DAG: GridMap must not import
Senses or SpatialSensesSystem. Use GridMap-owned subscription dirtiness read by
the existing sensory system, or an existing dependency-inverted notification
seam; choose the concrete seam in step 0.
Do not equate a changed global illumination revision with invalid geometry.
Keep global revision behavior for existing public FOV/path query caches while
removing it as the sole validity test for observer-local retained evidence.
Never mark an old field current by merely replacing its global revision number.

Geometry dependency coverage must include possible occluders and both incident
edge sides, dark/occluded candidate cells, diagonal corner dependencies, and
upper-volume tested routes. A bounded conservative influence region is acceptable;
an exact graph for every ray is not required. A field outside a mutation's
influence keeps valid evidence. Unknown mutation coverage temporarily invalidates
conservatively and is exposed in diagnostics; ordinary covered cases must not
permanently fall back to invalidating every observer.

Retained data belongs to the current observer/world generation. Replace it on
origin/range/capability changes as required; clear it on replay replacement,
existing observer removal and map/runtime reset. A death event alone does not
authorize new unregistration behavior. Index size must track current
fields/objects, not number of previous steps or historical viewpoints.

### 5.3 Incremental sensory processing

A stationary light update intersects changed light cells with retained optical
evidence. Reevaluate only dependent visibility/effective-light cells and contacts.
Handle brightness changes even when visibility stays true. Reuse unchanged
nonvisual reach and unrelated contact evidence.

For changed contacts, reaggregate the current evidence for that subject: all
relevant occupied cells or boundary faces, visual/special senses and concealment.
Reevaluate affected hazards and navigation dirty transitions. Preserve creator
knowledge separately from sight. Do not turn the update into an all-object scan.

Volume observations need explicit dependencies: current code may sample light at
the first fog surface or the preceding cell for magical darkness. A change there
can affect a larger disclosed surface. Retain that mapping or conservatively
recompute the affected volume owner's observation, using its current geometry;
do not recompute every volume or assume only the changed target tile matters.

Capture old values only for the concrete touched cells/contacts/effects and emit
the existing SensoryUpdateEvent fields/provenance at the same causal boundary.
Do not take two or three whole SensesSnapshot copies to emit a small delta. Keep
the public snapshot API and the full solve for initialization and genuinely broad
changes. Full recomputation is an offline test reference, not a second runtime
validation pass. Every branch must produce equivalent intermediate semantics.

This locality also applies to accumulated discovery. The current full solve
constructs `set(senses.seen) | set(visible)`, and snapshots/diffs copy the entire
`seen` set. Keep discovery in its current authoritative owner and derive new
entries from the currently evaluated cells. Moving-observer deltas may compare
bounded old/new fields, but must not copy all historical discovery per step.
Explicit public snapshots remain detached, including their historical discovery.

### 5.4 Moving observer and required geometry

Every new observer origin gets correct range and geometry evidence at that step.
If a light child already solved that committed origin, the parent reuses it as
today. No reuse across intervening geometry/capability changes.

After stationary work is narrowed, profile the remaining bounded solve. Keep
current supercover, diagonal transition, directed boundary, support-height and
occlusion semantics. If repeated relative-ray preparation/cache churn remains
material, prepare reusable rays for the actual active radius using the existing
caches with an explicit bounded working set; do not grow caches with explored
positions. Select this work from the profile, not merely because a cache exists.
Share compatible optical work between a mover and its attached lights only when
origin/topology/query semantics match; different radii may use an existing valid
superset. Pure geometry preparation must not reorder light commitment or callbacks.

Read local settled channel/illumination inputs once per required batch where
possible instead of rebuilding provider models or resolving tile values repeatedly.
Any derived edge/cell data is owned and invalidated by GridMap's existing spatial
mutation paths. Preserve the full solver's reference behavior. A different FOV
algorithm is justified only by remaining measured geometry cost and exact behavior
equivalence across the geometry matrix, not by its advertised asymptotic speed.

Remove the full solve's `get_all_object_positions()` scan for creator knowledge.
Maintain creator candidates through existing object placement/knowledge ownership,
then apply the native `is_object_known_to` predicate to those candidates. Cover
creation, changed creator/knowledge declarations, movement and removal; distant
unrelated objects must not enter this work. A creator can legitimately know
distant objects, so retain those grants without granting visual sight or refreshing
unrelated contacts. Resolve the concrete candidate owner in step 0 rather than
introducing a second object registry.

### 5.5 Projection from changes, with remembered state preserved

At each source event, carry affected cells/object IDs through the existing
recorded fold instead of reducing scope to a `world_changed` boolean. Reuse
`dnd/world_facts.py`, `world_event_positions`, and recorded sensory deltas. Audit
their costs first: current `world_event_positions` can itself scan all objects
for containment. Reusing a helper is insufficient if it preserves a global scan.

Keep current-world spatial membership, boundary, containment and necessary
composite reverse indexes at the existing recorded-world/projection owner. Today
capture creates a short-lived WorldFacts wrapper and discards its boundary index;
use one retained owner for those same facts, not two drifting world copies.
Update old/new memberships from recorded facts at their source-order position.

Affected output includes:

- changed and newly visible tiles, incident wall faces and affected object contacts;
- direct item/object/placement changes and observed removals;
- contents grants lost through closing, concealment or loss of observation;
- residues on faces actually observed, preserving other remembered faces;
- construction/volume suppression evidence and its known providers;
- remnant attachments whose identity just became known, even if the remnant
  itself did not emit a new object event;
- connector output under the existing complete connector-tuple contract.

Preserve known remembered identities as well as currently observed identities.
Never refresh unseen after-values from the private recorded world. Destruction's
pre-removal contact uses knowledge at its exact event boundary, not root-entry
knowledge or end-of-command knowledge. Initial projection can visit all admitted
facts; ordinary incremental projection must not revisit all world objects.

### 5.6 Capture, reduction, copying and publication

Keep common native work independent of audience count. Reuse EventQueue indexes
and CaptureCheckpoint for current roots/new evidence. Preserve historical version
references without scanning event zero on every operation. Measure detachment,
copy cardinalities, content/HUD/log work, encoding and recording separately.

The current `copy_target`/`reduce_nodes` path copies dictionaries of remembered
tiles, objects and senses. This can leave a map-size cost even after sensory and
projection loops are local. Resolve that ownership explicitly: immutable detached
packets/history stay immutable; current privately owned runtime folds may update
their existing state through existing apply primitives. Preserve public
non-mutating reducer APIs and callers that retain before-states. Do not silently
alias those before-states or weaken multi-audience publication/failure semantics.

During the first ownership checkpoint, identify exactly which current states are
retained by callers and when all potentially failing validation completes. Select
the narrow internal current-state application path only after this is established;
test prior-state isolation and failure behavior. If necessary copying remains,
report its cardinality and reason, and address demonstrated scaling before calling
the rework complete. Do not introduce a generic persistent-state/transaction library.

Published operations remain detached and encoded through the current contract.
Measure full dispatch-to-record latency, including bytes and normal GC. Preserve
current receipt/ACK/spool/backpressure semantics. Moving work into the host,
next request, client, or an unmeasured background job is not a speed improvement.

### 5.7 Event routing and handlers

Include EventQueue itself and every active handler in the locality investigation.
In `dnd/core/events.py`, `_get_handlers_for_spatial_event` and
`_get_handlers_for_non_spatial_event` use indexes but also iterate
`_event_handlers.values()` for remaining trigger predicates. The spatial lookup
can repeat that work for each dispatch position before outer deduplication.
This is a concrete candidate for population-dependent overhead, not proof that
all those predicates can be skipped.

Measure indexed candidates, fallback candidates tested, predicate calls/matches,
deduplication, and actual handler invocations separately. Attribute a slow handler
both to its own work and to any nested events/callbacks it triggers. Include
pre-completion systems and passive event/sequence/batch callbacks: sensory work
is not the only possible expensive callback.

Use the evidence to narrow discovery through existing event/phase/position
indexes or remove repeated work inside the responsible handler. Preserve native
trigger predicates, registration/dispatch order, enabled and lifecycle behavior,
preflight/veto/cancellation and result-version semantics. A `NO_EFFECT` invocation
can be a necessary rule check; it is not permission to delete or bypass a handler.
In a multiposition event, current discovery can interleave the first position's
handlers, matching global handlers, and later positions' unseen handlers. Do not
reorder it into two global/positional batches. Preserve source/target matching,
suppression and registration/reorder/removal/reset behavior. Native
`HandlerDispatchEvidence` and `effective_handler_presentations` support public
behavior attribution; they remain when temporary diagnostic instrumentation is
removed.
Do not replace the event system or add an alternative dispatch route. If a handler
needs the entire map by rule, account for that requirement explicitly; unrelated
handlers or distant registrations must not produce an unexplained per-step scan.

## 6. Execution sequence and completion evidence

Keep a plan-adherence subagent active throughout implementation. Anti-slop and
anti-OOP reviewers inspect each substantive checkpoint and the final integrated
result. Their findings must refer to actual source/behavior, not create unrelated
requirements. Record completed steps and unresolved costs in this document.

| Step | Concrete work | Required evidence before advancing |
|---|---|---|
| 0. Instrumented baseline and dependency closure | Make the existing backend-only route reproducible within existing server acceptance tools; retain route data/public SDK behavior; add temporary full-path instrumentation from §8.3; inventory mutation settlement points, dependency-DAG delivery seam, creator candidates and retained-state owners; record source/baseline and investigation-change disposition | Baseline route/cohorts with exact command-to-committed-receipt endpoint; complete diagnostic span/handler coverage and initial cost attribution; dependency/ownership table with source functions; current behavior reference, environment and target; no new benchmark framework |
| 1. Local spatial inputs | Capture settled optical values once per bounded query domain from existing tile memberships; establish local observer invalidation at correct settlement points; cover activation/removal/suppression/reset and existing failed-mutation/rollback behavior; eliminate the temporary all-owner presence scan | Optical/antimagic/geometry outputs unchanged, local query work independent of unrelated conditions, reset/owner lifetime tests |
| 2. Observer-local sensory updates | Separate retained geometry from light filtering; establish local invalidation; update stationary affected cells/contacts/volumes and emit sparse deltas | Every-event replay/full-reference parity, unchanged movement/reaction order; stationary light updates no longer perform full-field reconstruction or explored-state copies; distant changes do not stale unrelated fields |
| 3. Required mover work | Measure and optimize bounded mover/light geometry and contact discovery using settled local inputs; remove global creator-candidate scans and accumulated-discovery copies; use bounded reusable ray work only if justified by the profile | Exact geometry/range parity, no repeated solve for already-current committed observer inputs; measured remaining execution breakdown, radius scaling and independence from unrelated objects/explored memory |
| 4. Incremental audience projection | Retain recorded spatial indexes, preserve changed scope, project only dependent facts including composite/contents cases | Cold recorded replay and per-event audience equivalence; no all-world object scan per local event; unaffected remembered values preserved |
| 5. Remaining operation cost | Close measured event-discovery/handler, capture/current-state copy/HUD/content/serialization work; preserve dispatch, reducer and publication contracts | No unrelated-map/handler/history/explored-memory-proportional normal movement work; snapshot/failure isolation; justified serialization boundaries; complete recorded-result timings with rules/GC enabled |
| 6. Integrated validation | Serial live routes, controlled local/remote scaling, sustained operations and independent final reviews | Latency target and scaling evidence, behavior matrix, memory accounting, remaining-cost report and reviews closed |
| 7. Remove temporary instrumentation | Remove added runtime timing/counter/trace hooks and diagnostic-only production state; retain compact evidence and existing-family external runners | Final behavior checks and equivalent uninstrumented live/scaling runs still pass; reviewers verify no temporary runtime instrumentation remains |

Steps 2–5 are one coherent rework. A partial gain does not finish it. Remeasure
after each substantive checkpoint to select work inside the next owner; avoid
repeated full runs for tiny formatting changes. If an implementation fails parity,
repair or revert that isolated change while retaining useful tests/evidence.
Event discovery and individual handlers are inspected from step 0. If they dominate
or block locality, resolve that owner at the first relevant checkpoint rather
than postponing a known dominant cost until step 5. Drill down within expensive
spans after each meaningful change as described in §8.3.
Do not discard unrelated working changes. Temporary conservative fallbacks are
listed with trigger counts and a removal/justification disposition.

## 7. Behavior validation

Use small data-driven native or recorded-input scenarios with public outcomes.
Existing test files are starting coverage, not a mandate to duplicate them.

| Scenario family | Assertions |
|---|---|
| Movement/light | Every step's committed origin, attached and independent light sources, effective brightness without visibility change, dark-cell reveal/hide, no duplicate parent delta |
| Reactions | Opportunity attack and interruption before/after relevant step; reveal then occlude during one command remains in history |
| Event dispatch | Equivalent admitted handler order and public effects, custom predicates, multicell deduplication, lifecycle removal, cancellation/modification, child events and pre-completion ordering |
| Contacts | Hidden/invisible, darkvision/devil's sight/truesight/blindsight/tremorsense, range edges, capability changes, multicell/boundary evidence, creator-only knowledge |
| Geometry | Directed exit/entry layers, doors/windows, partial blocking, diagonal corners, support height/stairs, rejected sight routes, distant versus local topology changes |
| Conditional optics | Nonoptical traps coexist with sight; explicit and spatial optical owners; overlapping contributions; partial/full antimagic suppression and restoration; moving/resizing/removing areas |
| Volumes | Fog/darkness first surfaces, near-side illumination dependence, upper surfaces and reopening occluders; no hidden interior/occupant disclosure |
| Projection | Newly known/current/remembered/never-disclosed objects, contents grant loss, hidden mutations, remnant/attachment identity changes, residues by observed face, destruction/replacement within one root |
| Multiple observers/audiences | Existing shared-observer union/attribution; distinct audience memories; no cross-audience reuse of grants; one native mutation |
| Lifecycle/isolation | Deploy/unregister/reset/replay replacement; index cleanup; detached previous snapshots survive later mutations; publication/reduction failure behavior unchanged |
| End-to-end | Committed receipt/cursor, no duplicate spending, canonical state, causal order and cold replay after native runtime is unavailable |

For differential checks, execute equivalent deterministic inputs against the
reference and optimized path in separate owned runs, or evaluate the pure full
reference from the same committed inputs in the test lane. Establish identity
correspondence without removing parent/lineage links. Compare every relevant
intermediate observation/operation, not just final HP or counts. Do not change
expected values merely to approve a faster implementation. Keep the complete
solver as the existing broad-change owner, not a second production validation pass.

Relevant current tests include `tests/engine/test_sensory_movement_origin.py`,
`test_senses_light_stealth.py`, `test_sensory_initial_replay.py`,
`test_world_geometry_contract.py`, `test_spatial_conditions.py`,
`test_antimagic_retained_contributions.py`, and player light-source, storage-loot,
capture-checkpoint, capture-index and canceled-lineage tests. Add missing composite
and incremental-prefix cases at their proper boundary. Use the existing dependency
architecture check for import ownership; it does not prove gameplay.

Run tests with the documented prepared environment:
`UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run --no-sync python -m pytest ...`.
The environment has already been prepared. Preserve SDK/client tooling extras in
this shared environment; do not remove them by repeating an exact sync. The old
`tests/player/test_application_review.py` currently fails collection because it
imports the removed `game.runtime_protocol`; report this limitation and use current
server acceptance boundaries, rather than expanding this task into legacy repair.

## 8. Performance and scaling validation

### 8.1 Measurement lanes

1. **Ordinary live runs:** same 58-command route, normal SDK discovery/preview,
   native rules/reactions, capture/projection/serialization, natural GC and prompt
   ACK. Nested hooks/cProfile are off. Outer timers are constant-size diagnostics;
   label them and corroborate with ordinary host/recorded-result timing.
2. **Attribution runs:** same inputs with selected-command profiles and disabled
   timing-aggregate inclusion for profiled samples. Count field/cell/edge/contact
   work, handler candidates/invocations, serialized/copied entries and bytes,
   changed/output facts and conservative fallback triggers. Use the complete
   temporary coverage in §8.3, then deepen the expensive branches.
3. **Behavior/reference lane:** deterministic native and recorded-input comparison.
   Replay validates semantics but never substitutes for live timing.
4. **Allocation/lifetime lane:** allocation/retention tooling only for demonstrated
   remaining growth. Distinguish intentional retained events/spool/history from
   current indexes, caches and temporary state. Do not report traced timing as speed.

Promote only the small necessary backend route orchestration into the existing
`devtools/player_server_acceptance` family so another checkout can reproduce it.
Retain the original fixture seed and public command selection. Store private
configs, journals, profiles and bulky traces under ignored `.runtime/`; commit
only the runner and compact results. Never include tokens or configs in reports.

Repeat equivalent routes serially. Report command number, behavior, actor,
start/end positions, steps, reactions, new facts/events, bytes, audiences, sequence,
and execution/capture/projection/encode/publication times. Separate six-cell
ordinary moves from shorter moves and reaction/disclosure-heavy cases. Keep
first-use samples visible. Do not use native client latency as the backend result.

Collect at least 100 qualifying live samples before claiming a warm cohort p95;
use repeated complete routes or a normal SDK-driven continuation of the same
large scene. Report sample count, median, p95 and max; for small cohorts report
individual/min/max observations. Run comparable before/after processes serially
and record CPU/OS/interpreter/source location/runtime/GC configuration once per
batch. No checksum ceremony between individual commands.

### 8.2 Independent scaling axes

Hold the local command, affected geometry/population, party capabilities and
audience output constant while varying each irrelevant axis separately through
small/medium/large feasible authored variants:

| Axis | What must be held fixed / observed |
|---|---|
| Distant tiles/rooms | Outside sight/light/propagation dependencies; exclude construction time; local field visits unchanged |
| Distant objects | No local placement/grant/containment changes; projected object visits do not grow with them |
| Remote nonoptical/optical conditions | No local contribution or intersecting dependency; neither presence scans nor ray cost grows with remote owners |
| Unaffected observers | No overlap with the changed domain; no full registered-observer set materialization/field solves per local event |
| Remote handler registrations | Same local event types, affected positions and required handlers; measure discovery/predicate work separately from invocation and nested work as distant native owners/conditions add registrations |
| Explored memory | Same current view with progressively larger remembered map/object sets; no per-child whole-memory copying |
| Retained history | Equivalent native states after roughly 100, 1,000 and 10,000 retained events; capture visits new/root-referenced facts, not the prefix |

Remote change tests must also mutate a distant light/occluder and then execute the
same local move, to catch global revision invalidation that looks flat in a static
world. Build fixtures through existing world/scenario APIs and preserve ordinary
live command execution; do not manufacture timing gains by skipping initialization
requirements or forging packets. Validate equivalent local results before using
a sample pair. Scaling fixtures are diagnostics, not new gameplay content.

Separately grow genuinely affected light cells, contacts/observers, authored sight
radii, and seats receiving output. Show that cost follows required work/output
without unnecessary products of population sizes. Global effects can legitimately
affect the whole world; do not label such work an unrelated-data regression.

Use work/cardinality evidence alongside elapsed times to establish independence;
measure run noise before interpreting small slopes. No invented percentage
tolerance can conceal an observed full scan. Run a sustained mixed live lane with
at least 100 operations to check cleanup and late-history behavior; report elapsed
duration and avoid a new arbitrary duration gate. Preserve existing longer server
tests of configured lifetime/expiry behavior only when this rework changes that
owner; identify the applicable test and lifecycle interval at that checkpoint.

### 8.3 Temporary full-path instrumentation and progressive drill-down

Instrument the complete path first so unexplored work cannot disappear between
coarse timers. Reuse existing action-timing and passive dispatch evidence where
they cover a boundary, with temporary explicit spans/counters for missing areas.
Matched-handler evidence alone does not cover time spent discovering handlers,
and a worker-dispatch timer does not cover all encoding and host recording.

| Boundary | Initial coverage and counters |
|---|---|
| SDK/HTTP and host admission | Submission, request decode/validation, admission/queue wait, receipt storage/response, stream availability/arrival and ACK; separate discovery/preview and probe decode/reduction/file writing |
| Worker exchange | Request encoding/decoding, framing and pipe reads/writes/waits, worker dispatch, reply encoding/decoding; distinguish bytes transferred from models reconstructed |
| Native action and event production | Each committed movement step, legality/path work, reactions, authoritative spatial mutations, light updates, event creation/storage/versioning and current-root capture |
| Event discovery | Spatial/nonspatial lookup, number of dispatch positions, indexed hits, registry candidates visited, trigger predicates tested/matched, deduplication and final admitted count |
| Handler/callback execution | Every active handler and pre-completion/passive callback by existing semantic/system identity; calls, inclusive/exclusive time, outcomes, nested events and repeated invocations within a command |
| Spatial and sensory | Mutation settlement, affected cells/subscribers, invalidation, full/local field solves, geometry/rays/edges, contacts/creator candidates, volumes, hazards, snapshots, discovery updates and delta emission |
| Capture/projection/reduction | Current roots/versions visited, audience admission, source references, world-fold/index changes, objects/tiles considered versus emitted, contents/composite dependents, copied collection entries, HUD/content/log work |
| Serialization and recording | Each actual model validation/copy/dump, JSON encode/decode, text-to-bytes conversion, frame payload, spool stage/flush/commit, record read and stream write; counts, sizes and relevant state cardinalities |
| Allocation/runtime | GC pauses during measured commands, temporary allocations/retained working sets in the separate allocation lane, diagnostic buffer/output costs and unattributed elapsed remainder |

For command attribution, use existing command number, game/audience identity,
result cursor, root/event/lineage IDs and registered handler/system identity.
Keep diagnostics outside public events, packets and canonical state. Correlate
process-local spans with those existing identities; distinguish a causal parent
from the active timing parent. Nested handler/light/sensory time is inclusive:
derive exclusive time from the synchronous nesting, and do not add a host wait
to the worker work it already contains. Keep CPU time distinct from wall time
and blocked I/O where available. Never infer serialization cost by subtracting
two overlapping spans.

Record counters from the work being performed rather than rescanning a world or
serializing an event just to describe it. Use explicit identities or existing
semantic keys, not new reflection or per-call dynamic labeling. All handlers in
the selected diagnostic command are covered, including handlers that return
without an effect; include skipped-candidate and no-match discovery totals.
For an expensive handler, progressively instrument its actual collections,
queries and child calls to reveal whether the cost is the computation, a global
scan, repeated reconstruction, allocation, or downstream work.

Make a concrete serialization/copy inventory: representation entering/leaving,
owner and trust boundary, call count, input/output bytes or collection entries,
and reason it is needed. Current worker command timing is recorded before the
publication loop calls `record.model_dump_json().encode()`, so that work must
have its own span. `server/connection.py` stages public payload bytes and
`server/app.py` streams recorded bytes; preserve that existing path rather than
inventing another decode/encode cycle. Measure both actual repeated conversions
and model/deep-copy reconstruction within native capture/projection. Remove only
redundant same-boundary work; preserve wire validation, exact recorded bytes and
detached-history guarantees. No new zero-copy or serialization framework.

At every substantive checkpoint:

1. Compare plain live timing with the diagnostic command's span tree and work
   counts. Identify the largest remaining exclusive cost, repeated work, and
   any unexplained remainder. Keep diagnostic overhead visible.
2. Split that span at its real owner boundaries, down to collection/query/encode
   operations when needed. Do not stop at labels such as "execute", "events",
   "sensory" or "projection" if they still hide material work.
3. Run the relevant small/medium/large scaling axis with equivalent local input
   and output. Report handler discovery cost, individual handler cost and nested
   work separately, along with visited entries and emitted facts. A large map
   must not camouflage one handler's unnecessary world scan in an average.
4. Remove the demonstrated repeated or unrelated work at its current owner,
   establish behavior parity, then repeat attribution on the new dominant cost.
   Keep going until the latency and locality criteria are supported and the
   remaining costs are explained as required work, I/O or measured runtime cost.

Diagnostic tracing is opt-in for owned runs. Keep scalar counters and selected
command traces in bounded memory, flush outside the timed command, and report
truncation explicitly; rerun a narrower command/span if detail overflowed. Do
not log every cell synchronously, retain live event graphs in trace buffers,
change GC scheduling, or export private payload/config contents. Error/cancel
paths close spans without changing exception or publication behavior. Measure
the difference between instrumentation-on and plain runs; never claim the
instrumented elapsed time or a subtracted-overhead estimate as achieved speed.

Before completion, save the compact attribution/scaling evidence and remove all
new runtime-only tracing, timing wrappers, counters, switches, callbacks and
diagnostic state. Preserve pre-existing runtime behavior and diagnostic APIs;
the external acceptance runner can retain ordinary boundary measurements.
Run the final behavior selection and live performance/scaling batches on this
clean implementation. Removal is a required final checkpoint, not an optional
future cleanup or a reason to discard reproducible evidence.

## 9. Decision points, risks and deliverables

The plan fixes the ownership and work boundaries now. These implementation
decisions require concrete evidence in step 0/3/5:

- precise post-settlement synchronization hooks for every optical owner lifecycle
  and the existing-DAG seam for observer-local dirty channels;
- the concrete placement/knowledge owner for creator-contact candidates;
- the cheapest exact bounded geometry representation after broad observer work is
  removed, including whether relative-ray cache churn remains material;
- which server current-state copies can be removed while retaining public reducer
  immutability and publication/failure semantics.

Resolve these at their stated checkpoint, record the selected design and review
it before changing that owner's behavior or retained-state ownership. They are not reasons to begin an unrelated redesign
or silently leave the scaling requirement unfinished. A proposed new public
contract or gameplay change requires human guidance.

Deliverables are the scoped implementation, meaningful regression tests, the
reproducible existing-family backend driver, compact before/after/scaling results,
temporary detailed attribution evidence followed by instrumentation removal,
and independent final review. Report target attainment, actual remaining work,
test limitations and uncommitted/committed state truthfully. No client performance
or full native graphics validation is implied by backend completion.

## 10. Independent plan validation

Required reviewers:

- **Plan adherence:** `plan_adherence` — complete objective, scope, sequence and
  acceptance; prevents stopping at tactical gains or drifting into unrelated work.
- **Anti-slop:** `antislop` — necessary work versus repeated reconstruction,
  measurement honesty, achievable evidence and absence of invented obligations.
- **Anti-OOP / ECS:** `antioop` — authoritative owners, passive retained data,
  commit/publication ordering, lifetime, dependency completeness and import DAG.

All three reviewers read the complete revised plan, including the human's added
temporary-instrumentation requirement, and approved it on 2026-10-12 with no
remaining blocking findings.

| Reviewer | Findings resolved before approval |
|---|---|
| Plan adherence | Freeze/disposition of prior investigation edits; original versus candidate source baseline; exact SDK-to-recorded-receipt timing endpoint; lifecycle tests tied to changed owners; full instrumentation, progressive drill-down and final removal integrated without scope drift |
| Anti-slop | Ray/cache changes made conditional on measured cost; rollback limited to existing semantics; full-path/handler/serialization attribution with honest overhead; independent latency/scaling proof; removal followed by clean measurement |
| Anti-OOP / ECS | Observer dirtiness preserves the import DAG; death does not invent a new unregister lifecycle; creator candidates and discovery stay with existing owners; event ordering/native dispatch evidence preserved; diagnostics remain temporary and outside canonical state |

Source checks confirmed the host records/publishes before committing the receipt,
the worker's existing timer excludes publication encoding, and indexed event
discovery still has registry fallback scans. Plan links and whitespace checks
passed. This planning update changes only this document and its recovery link;
the four previously identified investigation files were frozen during planning.

Approval validates the plan's coherence, ownership, scope and executable
acceptance method. It does not prove the proposed speed, scaling, or correctness
of the unimplemented rework. The behavior and live measurement checkpoints above
remain required during implementation; the earlier test results validate only
their stated starting-state coverage.

## 11. Implementation checkpoints

### Step 0 — baseline complete, 2026-10-13

The human authorized implementation with the expectation of a large improvement.
The plan-adherence reviewer remains active; the anti-slop reviewer owns the
existing-family live acceptance driver and temporary diagnostic coverage, and
the ECS reviewer is checking concrete spatial ownership. The starting plain and selected-command diagnostic runs completed before the
production freeze was lifted. Evidence is under
`.runtime/server-latency/step0-{plain,diagnostic}/`, with exact reproduction
commands in `step0-summary.json`. Both runs completed 58 commands, sequence 101,
final position (68,20), 1,761 disclosed tiles, 360 objects and 102 records totaling
6,483,257 raw journal bytes. Plain ordinary six-cell command 50 took 948.73 ms to
the SDK committed receipt; reaction-bearing command 36 took 983.84 ms. The
16-move mixed cohort median was 845.55 ms; this is not the qualified warm p95.
Profiling found 18 full observer solves and 103,144 boundary-route queries for
command 50. JSON encoding and host recording were small measured costs.
Spatial/sensory and recorded projection ownership work is now underway.

Source review selected a simpler exact implementation of §5.1: resolve a bounded
region's optical contributions once per solve from existing Tile membership and
explicit optical sources. Store per-cell/per-owner values only for that pure
query batch, preserving exclusion and multiple contributions from one identity.
Spatial predicates then read already-settled parent suppression and anchor state;
there is no new persistent active-contribution cache to synchronize. This replaces
the temporary whole-map presence scan without adding another condition registry.
The ECS reviewer approved this concrete ownership choice.

For retained observer validity, the selected design is fixed-size per-observer
channel versions maintained by GridMap through existing cell subscriptions.
Known mutation footprints dirty only subscribers they reach; unknown coverage
uses an explicit conservative fallback. Senses subscribe a bounded influence
region including blocked/absent cells and edge dependencies. Support-height and
conditional-suppression changes must dirty retained geometry before light children,
even where the existing global XY-FOV revision would remain unchanged. A sparse
light update must prove it covers all intervening local changes, not merely
advance a version stamp.

Copy ownership review distinguishes public retained before-states from exclusive
server current state. Existing application callers retain `AudienceRuntime.latest`,
and projection retains event-entry senses for delivery/destruction disclosure.
Neither may be silently mutated through shared references. Actual live attribution
also covers audience union/provenance, final disclosure normalization and content
admission; passive capture helpers with similar names are not presumed hot.


### Steps 1–5 — first combined checkpoint, still in progress

The first combined plain and diagnostic runs are saved in
`.runtime/server-latency/checkpoint1-{plain,diagnostic}/`. Command 50 improved from
948.73 to 714.91 ms to the committed receipt. Full observer solves fell from 18
to 6, boundary-route queries from 103,144 to 41,884, and recorded object conversions
from 4,128 to 60. These are intermediate results, substantially above the target.
The profile still exposes moving geometry, empty-cell optical collection,
audience composition and repeated current-state copying; these owners remain active work.

This checkpoint **failed semantic acceptance**: all 58 command actions, positions,
HP and final disclosed map/object counts matched, but six extra log-only AI
operations were disclosed (sequence 107 instead of 101). Source review traced them
to conservative sensory dependency subscriptions entering the existing combat-log
perceiver query. Preserve the old exact observation-grant membership and store
invalidation dependencies separately at GridMap, using bounded chunk lookup with
exact per-observer domain filtering. The next live run must prove those extra logs
are gone. No projection filter is being added to conceal the upstream mistake.

Measured radius-80 solves scanned 25,921 mostly empty optical cells each. The
selected replacement is a bounded chunk index of candidate cells containing any
native spatial condition or explicit optical contribution; predicates still run
against settled native owner state during the solve. This is candidate membership,
not cached active optics. Retained dependency regions use rectangle bounds and
exceptional tested cells, avoiding one membership allocation per absent cell.
Call-local boundary snapshots reuse native ordered sides/provider structures;
FOV cache lifetime and relative-ray working-set changes preserve the selected
geometry algorithm. Public observation grants remain independent of these caches.

Sensory deltas now compare bounded current cells and newly discovered entries,
retain stationary light/volume dependencies, and index remembered effect cells so
unrelated effect history need not be copied per child. Recorded world projection
uses changed fact/knowledge scopes and current/remembered placement and suppression
memberships. Cold regressions cover late remnant knowledge, contents isolation,
opposite wall faces, zero-band objects and remote construction suppression cells.
Event discovery now uses existing source/target trigger buckets, preserving native
predicates, simple-first order, multiposition interleaving, legacy spatial handler
registration and removal. Seven dispatch behavior checks passed. Current-state
ownership, remaining content scans, broader differential/scaling runs and temporary
instrumentation removal remain unfinished.

### Checkpoint 2 and detailed phase attribution — 2026-10-13

Checkpoint 2 plain command 50 completed in **426.97 ms** (2.22× faster than
948.73 ms). This remains far from the human's subsequently explicit 100× target.
The first checkpoint-2 comparison found premature door-opening sensory events:
broad invalidation dependencies had also been used to admit sensory callbacks.
Restoring the original grant-based callback admission retains broad invalidation
without introducing new observation boundaries. A public two-light door regression
failed before that correction and passed afterward.

The following `checkpoint2-detail` live run restored baseline parity: 58 commands,
102 records, sequence 101, 6,483,257 raw journal bytes, occurrence cursor 3188.
Independent comparison matched ordered facts, source indices, combat logs, content
additions and each WorldUpdate at its event prefix after normalizing run UUIDs and
UUID-dependent object tuple order. All 102 remembered tile states matched too.
Its source includes the door correction and further content/capture locality work;
its instrumented elapsed time is not a new plain performance result.

The human requested a continuously updated HTML preview with exact work status,
method costs and deeper steps. The ignored local artifact is
`.runtime/server-latency/progress/index.html`, served on localhost during this
work. Its JSON records the latest published checkpoint and explicitly separates
plain latency, instrumented self/inclusive timings, open checks and pending work.

Temporary phase timings now split observer recomputation into 16 sequential
stages. In the detailed command-50 profile, physical FOV used 500 ms, optical/light
filtering 124 ms, boundary snapshot 72 ms, cell contacts 53 ms and boundary evidence
50 ms across six full observer solves. Inner FOV instrumentation materially inflates
these timings; they identify work, not achieved speed. FOV traversed 255,119 path
steps over 24,105 distinct edges: 254,845 transition-cache hits versus 274 misses,
and 242,802 blocking-cache hits versus six misses. The dominant repeated work is
walking rays and looking up already-resolved answers, rather than native predicate
misses. Actual record encoding remains a small separately measured cost.

The next observer change uses GridMap-owned sparse boundary/contact cell indexes
maintained with authoritative Tile membership. Boundary snapshots distinguish
covered empty cells from outside coverage and retain both incident directions;
native exit-blocks-entry filtering remains unchanged. Optical filtering reads light
once and shares immutable eligibility values for identical native range/obscurement
inputs within a solve. The selected moving-FOV design shares exact supercover
prefixes, preserves native directed transitions and terminal-before-opacity, and
bounds pure geometry retention. Its cold construction, retained records and first
query must remain in performance evidence; cache hits alone cannot justify success.
The plan-adherence reviewer approved these concrete ownership/algorithm choices.

Selected evidence before the next combined checkpoint: 105 sensory, spatial and
live-membership checks passed after observer changes; a separate 25-case lifecycle
batch passed after sparse light-contact routing. The content/log slice passed 44
selected cases and independent source review, then seven focused cases after a
root-local capture-set hoist. These are separate runs. Full scaling, qualified
100-sample latency, remaining owned-state checks, temporary diagnostic removal and
clean final reruns remain outstanding.


### Checkpoint 3 rejection and exact sweep replacement — 2026-10-13

Checkpoint 3 plain command 50 regressed to **633.6 ms**. Diagnostic attribution
isolated 668.5 ms in cold shared-prefix preparation versus 59.0 ms traversal,
with seven graph builds and 249 ms of GC pauses. The prefix representation and
cache are rejected; increasing retention would conceal the wrong computation
shape. Sparse observer changes did improve boundary evidence (about 50 to 3 ms)
and cell contacts (53 to 13 ms) in the instrumented command.

The replacement under implementation groups exact target slopes using integer
half-cell crossing inequalities and sweeps native blocking edges/centers in
outward order. It preserves the native cardinal/diagonal ties, missing support,
directed transition policy and visible opaque endpoint. The plan reviewer approved
the derivation after a 14,846-case pure incidence check; public native-query parity
and live cold/warm measurements remain required before acceptance.

The latest route was not fully comparable: UUID ordering changed cross-observer
interleaving, and equal-distance attack selection changed the command-14 target.
Comparable prefix values/native logs matched, but two fewer final records do not
establish a visibility regression or parity. The devtool now breaks selection ties
by disclosed semantics, records resolved commands and observer order, and can reject
an incompatible reference trace before submitting a differing command. Production
UUID generation is unchanged.

Tile objective light now retains the resolved value with its current contribution
inputs and updates it through the existing Tile mutation methods. Preview resolution
remains pure; direct authored default replacement refreshes the value. The selected
78-case light/optics/movement batch passed, including overlapping sources/caps,
replacement seeding and detached-copy checks. The HTML preview now includes an
expandable actual cProfile caller/callee tree and phase totals/means/maxima.

The human explicitly requested additional GPT-6.1-Sol extra-high read-only agents
for independent first-principles review while implementation continues. Geometry
and whole-pipeline reviewers are active; their work does not replace implementation,
correctness, scaling, diagnostic removal or the 100× acceptance requirement.

### Checkpoints 4–6: exact geometry and allocation ownership — 2026-10-13

The exact integer-ranked sweep reduced command 50 from checkpoint 4 plain
**289.53 ms** to checkpoint 5e plain **234.31 ms**. Independent read-only review
matched all 58 resolved semantic commands and all 100 recorded payloads through
an injective 6,397-identity mapping. Event order, ancestry, source indices, world
prefixes, HUD, logs and content matched; only UUID-dependent collection order was
normalized. Host exchange improved from 236.87 to 218.89 ms, so polling/probe
phase explains part of the larger SDK change. These are individual checkpoints,
not qualified latency distributions or whole-route historical baseline parity.

Checkpoint 5 diagnostic splits command 50 into six observer solves totaling
210.51 ms, twelve directional FOV calls totaling 107.04 ms, navigation 94.81 ms,
and capture/application 72.40 ms. The observer's physical field is 97.49 ms,
optical filtering 44.87 ms, boundary snapshot 27.13 ms, cell contacts 11.92 ms,
boundary contacts 9.32 ms and perception commit 7.69 ms. Nested totals overlap
and include substantial instrumentation overhead. GC was 10.42 ms with no
generation-2 collection; checkpoint 4's 207.78 ms GC pause had been charged to
an otherwise cheap invisibility predicate. Do not attribute that difference to
geometry or redesign the predicate based on that paused self-time.

The next implemented slice removes temporary passive-score model composition:
scalar evaluation remains in the values owner and preserves source UUID bucket
precedence, channel normalization, exact factors, clamps and contextual callback
order. Cases with contextual proficiency state requiring legacy isolation retain
that path explicitly. No persistent score cache or alternative model hierarchy
was added. The independent pipeline reviewer approved the source and 111 selected
value/transient/entity/senses cases passed; the final focused passive file passed
24 cases. Capture now detaches known primitive containers through its local copy
memo and shares only exact native immutable PerceivedContact leaves. Mutable
extensions, modes, effects, costs and logs retain deep detachment. Twenty-six
selected capture/projection/world cases passed, including later native mutation
isolation. The recorded-world test helper was brought onto the existing audience
argument contract; its earlier five failures occurred before exercising the new
world-light guard. That guard preserves source events while avoiding replacement
of an unchanged immutable tile-light value.

Checkpoint 6 plain is running against this frozen source. Remaining architectural
work includes navigation's global unit-cost branch discovery and repeated spatial
crossing discovery, required local sensory passes, distant topology first-query
costs, and multi-audience common capture. No gain from those unimplemented changes
is claimed. Three requested GPT-6.1-Sol extra-high read-only reviewers completed
or contributed geometry, pipeline and measurement reviews; implementation and
plan-adherence work continue alongside them. The ~9.5 ms objective, independent
scaling/retained-state evidence and removal of temporary diagnostics remain open.

### Checkpoint 7 and sparse physical inputs — 2026-10-13

Checkpoint 6 plain completed at 270.67 ms for command 50. Checkpoint 7 plain
completed at 194.16 ms, but its reversed observer order makes it a different
interleaving cohort. The same-order checkpoint-7 detail run independently matches
all 58 commands and all 100 recorded payloads against checkpoint 6 through an
injective 6,397-identity mapping, preserving source indices and causal order.
The opposite-order plain/coarse runs retain different remembered brightness at
24 final tiles; this is a real cohort difference, not normalized away as tuple order.

Checkpoint 7 coarse command 50 measured 165.12 ms worker time: execute 144.15,
capture/application 18.80, observer recomputation 88.17 across six steps, and
12 directional fields totaling 43.20 ms. Inclusive spans overlap. Exhausted
movement navigation fell from 32.83 to 1.44 ms after avoiding unused radius-20
paths; custom path consumers, positive budgets and Dash remain supported. The
shared navigation worker is now the timing owner, so trimmed calls remain visible.
Command 36 measured 445.35 ms including 189.93 ms of natural GC pauses.

A dense successor/cutoff representation passed 105 native cases but did not
improve the selected integer-mask sweep in isolated cold/open/sparse/dense/hole
scenes. It was reverted. The new candidate instead acquires sparse physical
inputs before constructing angular events: existing boundary/contact/optical
memberships, intrinsic Tile flags and a chunked missing-support frontier maintained
on support insertion/removal/rectangle creation/reset. Native predicates still
resolve directed cardinal and diagonal candidates. Exact angle cutoffs retain
opaque terminals and failed entering edges. Empty obstruction sets admit all
ordered supported targets without angular preparation.

Crossing coverage is explicitly declared at native registration: unknown is the
safe default; an empty channel set declares no crossing effect; a channel set
promises footprint-local crossing. SpikeTrap declares no crossing, SolidWallZone
all three channels, and WindWallZone movement. Undeclared owners retain native
conservative discovery and the dense FOV fallback. This does not yet establish
independence from all distant conditions. Source reviews approve the sparse
candidate proof, lifecycle and ECS ownership. Initial native geometry/senses
validation passed 109 cases; the broader current wall/spatial/antimagic/local
batch passed 127. The legacy solid-wall test file cannot collect because
`tests.game` is absent; no unrelated repair was made.

Isolated sparse FOV timings show open radius-20 warm median 3.54→0.64 ms and
open radius-60 cold 157.86→13.86 ms; dense radius-60 regresses cold 17.16→51.44 ms
and warm median 19.42→25.16 ms. All sampled visibility counts match; native ray
parity is separate evidence. The dense regression and a 556.82 ms hole-scene
outlier remain open, so the solver is not accepted as universally faster.
Gallery-specific measurement is next.

The observer boundary snapshot now represents its exact cardinal halo without
materializing every halo tuple. The existing Tile-side candidate index retains
ordered side tuples at band commit; snapshots detach the mapping and continue
resolving live provider structure. 124 selected cases passed, including negative
chunk edges and captured-empty versus outside-live semantics. Recorded world
object membership now includes incident boundary neighbors in the existing index,
reducing five local lookups to one; 22 focused cases passed. Neither slice is
claimed to remove a previously existing global scan.

The 100× objective, positive-budget navigation scaling, independent remote axes,
qualified warm cohort, retained-state/failure checks and diagnostic removal are
still unfinished. Instrumented checkpoints and isolated geometry timings are
not substitutes for final SDK-to-committed-receipt acceptance.

### Checkpoint 8 and checkpoint 9 candidate — 2026-10-13

Checkpoint 8 plain completed at 173.96 ms for command 50 and 245.02 ms for
reaction command 36. Independent comparison against checkpoint 6 plain and
checkpoint 7 detail passes all 58 semantic commands and all 100 recorded
payloads through the 6,397-identity bijection. Same observer order, causal
indices, intermediate observations, remembered light, HUD, logs and content
are preserved. The 100× goal remains about 18× away for this selected command.

Checkpoint 8 coarse command 50 was 302.65 ms including 188.37 ms GC (181.07 ms
generation 2). Execute was 104.86 ms, six observer solves 58.67 ms, twelve
directional FOV calls 22.43 ms, navigation 1.20 ms. Capture lineages includes
the GC pause; its 186.22 ms is not a pure algorithm cost. Full instrumentation
measured 449.53 ms including 184.23 ms GC, this time inside boundary contacts.
Those pauses remain part of latency evidence. The unchanged pre-existing worker
entry freezes imported schemas before Start; both plain and diagnostic lanes
use that entry. This work does not add freezing or change GC scheduling.

The checkpoint-9 candidate derives optical/propagation diagonal admission from
the already-resolved native bridge centers and directed cardinal legs. Unknown
spatial owners still use the previous native dense path. 144 selected native
cases passed, then seven expanded declared-crossing cases passed. The expanded
fixture includes a real distant directional boundary to select that existing
solver: ordinary center-only shadowcasting has different opaque-terminal
semantics and is intentionally unchanged. Dense radius-60 cold time fell
51.44→23.99 ms; warm median 25.16→24.49 ms. This still trails the selected
old integer-mask solver (17.16/19.42 ms); it is a bounded tradeoff, not a reason
to introduce an unmeasured solver-selection framework. A 567.21 ms hole-scene
outlier remains visible. Sample counts match; public native-ray parity is the
separate behavior evidence.

Current-field sensory parents now capture only touched hazards/effects when
their light child has already refreshed the field. Native hazard evaluation,
capability/path metadata, initial/stale fallbacks and topology checks are
preserved. Changed light/hazard entries are filtered before sorting. Four new
native residue and child/parent replay cases pass. An unused EventQueue
timestamp bucket index is removed without removing history; chronological
queries already use the retained event list. The earlier handler-order index
is now included in the existing pack-import rollback snapshot. Integration
validation is in progress; obsolete legacy tests that fail before this boundary
are not changed to manufacture a green suite.

A separate scalar ownership audit found 326,719 tracked objects after imports,
505,024 after native Gallery creation, and 529,221 after startup capture. It
bypasses worker entry, so its import graph is not evidence of the live GC scan.
The 12,225 registered values comprise 2,445 ModifiableValue roots and their
4,890 static/4,890 contextual children. Around 1,900 roots belong to health
compositions of 380 world props. Audience world capture adds about 21,203
tracked nodes with duplicate frozen world leaves, about 4% of this audit heap;
sharing those cannot be claimed to eliminate the entire GC pause. No broad
health/schema redesign or GC scheduling change is authorized by this finding.

The runner now optionally supports 1 ms receipt polling and records the actual
committed receipt alongside consumed cursor. Default remains 10 ms for current
checkpoint comparability; final qualification requires matching finer cadence.
Whole-command checkpoint 9, independent scaling, retained-state/failure
acceptance, at least 100 equivalent ordinary moves, and diagnostics cleanup
remain outstanding.

### Checkpoints 9–10 and angular obstruction envelope — 2026-10-13

Checkpoint 9 plain command 50 is 140.15 ms; checkpoint 10 is 144.75 ms.
Independent read-only validation matches all 58 commands and 100 records
against checkpoints 9, 8 and 6 through the 6,397-identity mapping. All 58
committed receipts match their command and journal cursor. Checkpoint 10's
mixed nine-six-cell median is 145.22 ms; total committed-command time falls
4,864→4,419 ms but representative medians show no clear gain. Whole route
20.232→20.013 seconds remains essentially flat. These are small mixed cohorts.

Checkpoint 10 reuses ordinary moving-observer overlap light only after exact
new FOV, unchanged optical/propagation revisions and an authoritative light
batch, with unchanged ordinary capabilities and no prior/current obscurant
eligibility. Missing terminal coordinates from native shadowcasting retain
its original Tile-is-absent skip. Contact predicates still run; identical
native immutable contact leaves can be retained. Native candidate traversal
and creator placement order are restored without scanning unrelated placements.
73 selected perception/capture cases and three creator lifecycle/discovery
cases pass; EB-09-008 passes without changing expected action order.

Coarse checkpoint 10 measures worker97.07 ms including GC6.23, execute79.42,
six observer solves45.64 and twelve directional FOV calls24.31. Checkpoint 9
was102.43/7.64/86.42/53.19/22.35 respectively. Full instrumentation reports
250.81 ms including GC8.18; FOV54.87 includes enumeration26.78 and obstruction
preparation15.38. Boundary snapshot14.89, cell contacts12.35 and boundary
contacts8.36 remain significant. The preview now includes this fresh call tree.

The next candidate replaces target-angle sorting with the exact angular
obstruction envelope. Existing native center/cardinal/diagonal acquisition is
unchanged. Separating integer ranks express each blocker as a half-open angular
interval of allowed depth; a sweep of interval starts/ends retains the minimum
active depth. Native targets query that envelope without building and sorting
quadrant endpoint lists. Axis branches, strict corner equality, opaque terminals,
map clipping and unknown-owner dense fallback are preserved. There is no new
persistent geometry cache, origin history or prewarm. Plan/anti-slop and
independent Sol proof reviews cover interval strictness, axes and simultaneous
start/expiry handling. Anti-OOP review remains required before final acceptance.

The initial envelope passes 73 native geometry/perception checks. Isolated
radius-60 warm medians improve sparse18.26→10.64 ms and dense24.49→16.15 ms;
all sampled visibility counts match, with native ray parity separate. A529.89 ms
dense-scene outlier remains visible. The further direct-target traversal change
is under validation; no live checkpoint-11 latency gain is claimed yet.

The 100× target, native reaction-handler remote scaling, positive-budget global
path classification, retained-state/failure evidence, at least100 equivalent
ordinary moves and diagnostic removal are still open.

### Checkpoints 11–12 and the next scaling boundary — 2026-10-13

Checkpoint 11 plain command 50 is 137.45 ms, command 36 is 173.10 ms and the
whole route is 18.529 seconds. Independent comparison passes all 58 commands,
100 records and 58 receipts against same-order checkpoints 10/9/6. The direct
angular-envelope traversal and anti-OOP review are complete; 88 selected native
geometry/boundary/sensory/world-query cases pass, including a very large radius
on a small clipped map. No persistent origin graph or prewarming was added.

Checkpoint 12 plain command 50 is **96.57 ms**, command 36 is 160.21 ms and the
route is 17.944 seconds. Its Fighter→Sorcerer order matches checkpoint 7 plain,
not checkpoint 11. Independent comparison passes all 58 commands and 100 records
through 6,397 identities against that matching cohort, including all 58 receipts.
Checkpoint 12 coarse has Sorcerer→Fighter order and independently matches all
checkpoint-11 records. Across opposite cohorts, 24 remembered light values still
differ; these are real interleaving differences and are not normalized away.
The matching-order checkpoint-7→12 mixed nine-six-cell median is 194.16→122.53 ms;
this is a small mixed sample, not a qualified p95.

The checkpoint-12 boundary owner reuses immutable provider structures and the
unchanged overlap of its exact current cardinal halo after matching local
optical/propagation revisions. Added base cells acquire their new halo; departed
layers/providers and reverse routes are pruned. Explicit full refresh remains
fresh. Native `get_objects_at` uses the existing committed side index. Opportunity
attacks query native threat predicates only at the from/to endpoints, preserving
the default full-domain API. Grease and FogCloud explicitly declare their inherited
always-false crossing behavior; unknown custom owners retain the native fallback.
No new global dependency or callback framework was introduced.

Selected validation passes 88 geometry/boundary/sensory/world cases, 148 cloud/
spatial/antimagic cases, three new native reach/barrier/Disengage reaction cases,
and 54 other reaction/preference cases in separate batches. An existing near-door
assertion also fails on an isolated clean HEAD export; its expected output is
unchanged. A legacy movement file cannot collect its removed server import.
These limitations are not reported as successful full-suite validation.

Checkpoint-12 coarse command 50 is 100.63 ms including 7.95 ms GC, with observer
46.37, FOV22.94 and capture/application18.39 ms (inclusive, overlapping spans).
Full instrumentation is 194.67 ms including 4.95 ms GC: observer72.28, FOV31.91,
boundary snapshot6.91, cell contacts11.79 and boundary contacts8.35 ms. Boundary
provider evaluation is 8 fresh / 1,008 reused. The HTML preview now exposes this
call tree and both cohorts explicitly. Natural earlier generation-2 tails remain
in the evidence; these latest samples do not establish their removal.

Next, measure positive-budget navigation through native SDK Dash followed by the
same six-cell move, with public movement resources checked at 60→30 feet. Dash,
discovery and preview are outside the movement clock in every matched variant.
The ordinary 30→0 lane remains separate. Measure independent remote tile,
optical/nonoptical owner and handler axes before selecting further owner changes.
A proposed Tile write-hook/index-link scheme is rejected for now: its copy
semantics and incomplete raw/modifier write coverage would add infrastructure
without proving locality. The current BFS/Dijkstra branch has a real global
cost dependency and differing path ties; local-only classification is not equivalent.

The 9.5 ms end-to-end target, positive-budget and independent remote scaling,
retained-state/failure evidence, at least 100 qualifying ordinary moves, and final
diagnostic removal remain open. Plan-adherence and independent Sol reviewers
continue to check implementation and the next measurement boundary.

### Checkpoint 14 measured candidate — 2026-10-13

The checkpoint-13 row-run FOV output experiment was rejected and surgically
reverted. It passed 58 native geometry cases, but only reduced the instrumented
output phase 6.81→6.10 ms without a clear whole-solve benefit. Its plain 124.14 ms
sample in a different observer-order cohort is retained as evidence, not credited
as an improvement from that discarded implementation.

Checkpoint 14 generates only the blocker diagonals that can satisfy the existing
outward Manhattan-depth predicate. Native cardinal/bridge checks, strict corner
rules, target order and unknown-owner fallback remain unchanged. Independent
algebra review and 58 native geometry cases pass. Isolated dense-radius-60 warm
median is 15.33→12.06 ms; holes 12.07→9.96 ms. Unchanged open-scene samples vary,
and disappearance of one cold outlier is not proof that GC tails are eliminated.

Empty spatial-condition queries use the existing committed candidate membership
before looking up a Tile. GridMap's native footprint/tile settlement maintains
this union for all spatial conditions. There is no additional index or Tile
mutation hook. 117 native spatial/navigation cases pass. Directly creating an
invalid dangling reference through a low-level Tile primitive is not proof of a
valid committed owner lifecycle; its former error timing is not claimed here.

Capture extends its existing local deepcopy memo with immutable native Event
identities, timestamp, frozen handler-presentation tuple and omission frozenset.
Every event family and subclass still uses generic deepcopy; mutable resolution
and observed provenance are not shared wholesale. Anti-OOP source review approves
this bounded change. Thirteen native capture, cold-load, canceled-lineage and
all-seat cases pass, including later mutation of Event and nested provenance
extensions. No native-class copier/schema duplication was introduced.

Checkpoint 14 plain command 50 is 127.44 ms, command 36 156.92 ms and route18.228 s.
All three lanes use Sorcerer→Fighter order. Same-order checkpoint11 plain was
137.45 ms; checkpoint12's 96.57 ms is the opposite order. These are small samples.
Full ordered journal/identity/receipt comparison is running, not yet claimed.
Coarse worker79.59 ms includes4.37 ms GC, versus same-order checkpoint12
100.63/7.95 ms: directional FOV22.94→12.41 ms, observer46.37→35.48 ms and
capture/application18.39→13.89 ms. Full instrumentation188.90 ms includes4.40 ms
GC, with FOV27.50 (enumeration13.01, inputs4.51, events0.75, cutoffs1.66,
output6.78), observer71.49, boundary snapshot10.49, cell contacts12.03 and
boundary contacts8.24 ms. Inclusive spans overlap and profiling overhead remains.

Native positive-budget Dash→six-cell scaling now verifies public movement60→30.
At10,325 versus20,225 tiles, the old unit-cost classifier costs about45 versus
85 ms; checkpoint14's empty-membership shortcut reduces those to28 versus54 ms.
Three samples per size are diagnostic, not qualified latency or full intermediate
payload proof. This remains O(total tiles), so locality acceptance is still open.
A concrete native reproduction proves that one unreachable rough tile can switch
BFS to Dijkstra and change an equally short local route. The human was asked
whether to use the existing weighted solver consistently. This gameplay path-tie
decision remains pending; no solver change is implemented.

A one-shot opportunity-handler subscriber gate was also rejected: handler
selection precedes invocation, so an earlier handler/child can move or reveal a
reactor before its later native slot. Current live-state semantics cannot be
replaced by admission-time visibility without proving that ordering boundary.
No generic re-admission framework or new handler purity contract was introduced.

The 9.5 ms full-command target, independent remote scaling, retention/failure and
100 equivalent ordinary-move evidence, finer matched receipt cadence, and removal
of temporary diagnostics remain open. Continue measured owner work before final
acceptance; these checkpoint gains do not complete the rework.

Independent checkpoint-14 comparison is now complete: all three lanes match both
checkpoint11 plain and checkpoint12 coarse in all58 commands/all100 ordered
records through an injective6,397-identity mapping. All58 receipts per lane match
the corresponding command and journal cursor, including timing arithmetic.
Each lane retains6,307,680 bytes. CP11→14 plain mixed16-move median119.589→117.405
ms; mixednine-six-cell median137.451→127.442 ms; summed58receipts3.663→3.639 s.
This confirms output parity but only modest aggregate gain in these samples.

### Checkpoint 15 and projection input separation — 2026-10-13

Checkpoint15 keeps the exact newly acquired boundary layers and new halo. When
those layers equal the previous snapshot, it copies the previous provider and
route maps rather than reconstructing their incidence. All mutable mappings stay
detached. 48 native boundary/sensory cases pass, including shifted coverage and
mutation of every old snapshot mapping. This has no demonstrated Gallery phase
gain: full boundary snapshot10.27→12.99 ms includes differing GC placement/cohort.
Do not credit the shortcut for a speedup without appropriate measurement.

Hazard refresh now receives the caller's possible visibility-change cells. A
stationary light refresh changes only its declared cells; the already-current
movement-parent branch changes none. Full moving/explicit refresh retains the
full fallback, and capability refresh with no affected-cell restriction still
reevaluates the whole visible hazard domain. Volume surfaces/active effects keep
their original processing. There is no new retained state. 111 native light,
hazard, spatial and antimagic cases pass, including moving-light reveal/loss,
hidden corrosive-residue removal and exact sensory replay. Full hazard cost
8.025→5.566 ms across24calls; profiling remains included.

CP15 plain command50 is126.803 ms, command36 143.785 ms, route17.771 s in
Sorcerer→Fighter order. Coarse/detail use Fighter→Sorcerer: coarse76.136 ms
includingGC6.109; full186.231 includingGC6.574. Independent comparison passes
all58commands/100records/6397identities and58receipts for every lane against the
matching historical cohort. The341-entry source-at-start manifests match.
CP14→15 plain mixed16median117.405→115.492; mixednine-six-cell127.442→124.526.
However total58receipt time rises4.08%, and mixed16sum rises10.13%, with worker
spikes at command54 (observed336.288/worker277.481 ms) and15 (153.132/126.030).
Unprofiled data cannot attribute these spikes to GC. They remain in the results.

The apparent host gap is mostly client observation delay in CP14coarse cmd50:
worker encoding/writes end atsubmit+84.187ms; committed receipt stored+85.592;
SDK observes+125.102. Probe journal writing3.483ms and validation/reduction17.904ms
block the same polling event loop. Record staging is1.161ms, index commit0.0048ms;
the host preserves encoded worker bytes without a second record conversion.
SDK JSON/schema validation followed by the gallery's Pydantic parse is duplicate
client conversion. No probe delay is subtracted; polling changes need matched
cohorts and must not be reported as engine optimization.

Cross-origin intrinsic-opacity retention was rejected: direct public Tile field
writes do not advance GridMap revisions, while a new viewpoint currently reads
those fields fresh. Support-only retention and NumPy output conversion would
address bounded constant factors, not the dominant remaining pipeline costs.

Current checkpoint16 candidate separates exact light Tile comparison cells from
object/incident-support discovery cells in the existing recorded-world projector.
LIGHT_CHANGED changes only exact light-map cells; object dependencies continue
through visibility additions/removals, contacts, provider/construction memberships
and pending remnant knowledge. Nonlight footprints remain conservative. Every
existing world-update boundary and connector comparison stays in source order.
No dirty index, cache, schema copier or event merger is introduced. Independent
anti-OOP review approves;35 native/cold world/light/owned-current/multicell cases
pass. A native shared two-observer child-before-parent light/cold replay check is
being completed before live measurement. No checkpoint16 speed claim yet.

Checkpoint 16 measurements are complete. All three runs use Fighter→Sorcerer
order: plain command 50 is 119.924 ms, command 36 is 138.606 ms, and the route is
17.701 s. Coarse worker time is 75.144 ms including 5.929 ms GC; projection is
5.615 ms versus checkpoint 15's 7.995 ms. Full instrumentation is 179.728 ms
including 7.258 ms GC. Tile comparison positions fall from 2,379 to 748; object
discovery uses 174 positions and 26 explicit identities. Native shared-observer
light ordering, missing-Tile behavior, cold replay and selected content/isolation
checks pass. Complete ordered packet comparison is still running. No target or
sustained latency acceptance is claimed.

The existing Gallery runner now has an optional native continuation: position the
leader at (47,20), keep the companion still through ordinary end-turn commands,
perform four warmup moves, then alternate (47,20)↔(53,20). Each measured selection
must have seven path positions, six cardinal steps, native cost 30 feet, the exact
destination and public movement budget 30→0. Discovery and preview remain outside
the submit-to-observed-committed-receipt clock. This repeated-viewpoint warm-cache
cohort is explicitly separate from fresh route command 50. Validate the runner
with a small live continuation before collecting at least 100 samples; retain all
outliers and provide p95 only at that sample count. Final before/after comparisons
still require matched receipt cadence and equivalent intermediate records.

The next owner candidate reconciles the current observer's boundary snapshot.
Checkpoint 16 scans 992 occupied layers and 1,016 provider occurrences across six
steps, although only eight providers are fresh. Under the existing light-child
and matching local optical/propagation revision gate, changed halo membership can
only occur at changed base cells or their four cardinal neighbors. Acquire entering
layers and prune departing layers; recompute incident routes only at changed owner
positions and their neighbors, preserving enum direction order. Native boundary
placements have one owner position/direction, so no reference-count index is needed.
Prepare fresh outer dictionaries and never mutate shared inner side dictionaries;
install the candidate only at the existing field replacement boundary. Keep the
public detached snapshot API and explicit full refresh unchanged. Contact predicates
still evaluate every current subject at every origin. This is a measured candidate,
not a promised gain: native movement/route parity and actual timings determine
whether it is retained. Anti-OOP and plan-adherence reviews remain required.

Independent checkpoint 16 validation now passes every lane: 58 semantic commands,
100 ordered records, 6,397 injectively mapped identities and 58 committed receipts
against matching-order checkpoint 12. Every receipt maps to its command-numbered
journal packet; later probe consumption may legitimately advance beyond it. All
341 source-at-start entries match across the three checkpoint 16 lanes.

The first sustained continuation completed 100 moves, 281 total commands and
875 records in 157.733 seconds. Its raw median/p95/max are 83.634/97.300/115.445 ms,
but independent audit found the companion moving and taking damage during setup
and early samples. It also publishes six sensory facts per sample rather than the
reference command's twelve across two observers. This run is retained as diagnostic
evidence and DOES NOT qualify fixed-party or equivalent-output latency acceptance.
Correct the native setup and explicitly verify party state and affected population
before another qualification run. The original ordered route parity remains valid.

The private boundary reconciliation candidate is implemented. Sixty-nine native
geometry, local-input and moving-sensory cases pass, including opposite owner sides
with different channel contributions, shifted/disjoint coverage, exact full-refresh
agreement, emitted sensory replay and stable earlier public contact snapshots.
Independent actual-source anti-OOP review approves its current ownership and route
logic; full recorded intermediate-order parity remains required. Four additional
recorded content-attribution cases pass for equipped/hidden foreign providers and
foreign handlers on a controlled parent, with serialized sequence/packet parity.
The latter cases do not claim a native emitted combat reaction or live-reset replay.
Checkpoint 17 plain/coarse/detail measurement follows with source frozen.

### Checkpoint 17: current boundary reconciliation — 2026-10-13

The measured boundary snapshot phase falls from 13.846 to 1.535 ms across six
observer updates under full instrumentation. The field still contains 992 occupied
rows and 1,016 provider occurrences in aggregate, with eight fresh providers, but
only 17 changed rows and 80 incident routes are reconciled. Every native contact
predicate still runs. No additional persistent index or reference count was added.

Plain command 50 is 78.346 ms observed SDK receipt, of which native worker dispatch
is 66.715 ms. Its Sorcerer→Fighter cohort matches checkpoint 15 (126.803 ms observed,
79.596 ms dispatch). Receipt/SSE scheduling accounts for part of the observed gap;
this is not a claim that boundary reconciliation alone saved 48 ms. Command 36 is
141.596 ms; the full route is 17.667 s and all 100 records retain 6,307,680 bytes.
Coarse uses Fighter→Sorcerer order: 74.723 ms worker including 6.071 ms GC, six
observer updates 35.045 ms, twelve directional FOV calls 17.797 ms, execute 61.528 ms
and capture/application 11.737 ms. Full instrumentation is 174.433 ms including
6.586 ms GC; perception-commit GC placement differs from the previous run.
Independent ordered packet and receipt validation passes for all three lanes:
58 semantic commands, 100 ordered records, 6,397 injectively mapped identities
and 58 committed receipts per lane, against matching observer-order references.
All 341 source-at-start entries agree. No event, causal ordering or remembered
light value is omitted from comparison.

The optional sustained continuation was removed after its invalid cohort was
identified. Native curator pursuit, shove and damage put the companion into the
dying state before its measured samples; simply issuing end-turn did not hold the
party fixed. Retain the ignored recordings as diagnostic evidence, not acceptance.
Final sustained qualification will repeat the unchanged native route, separating
command, reaction/disclosure load, affected observers and output bytes. Do not pool
different strata into command-50 p95. No gameplay or encounter-end behavior changed.

Further audience aggregation work was rejected as the next substantial slice.
Checkpoint 17 applies 12 non-initial sensory facts to the projector and committed
state, appending 69 new seen cells per fold without scanning the 39,832 retained
seen cells available. The entire remaining coarse application overhead beyond
lineage capture and projection is 1.558 ms. This does not justify merging folds or
weakening privacy/cursor/all-seat failure isolation. The measured remaining time
is predominantly native execution and perception; the 9.5 ms target remains open.

### Next measured owners: geometry enumeration and handler discovery

Checkpoint 18 candidate derives each column's exact integer circle interval in
GridMap's existing directional FOV enumeration. This removes per-target radius
arithmetic and outside-circle Tile lookups while preserving x/y traversal, fresh
native intrinsic-opacity predicates, obstruction acquisition and output. It adds
no retained data. Unbounded queries and finite radii whose square overflows to
infinity keep clipped rectangle enumeration. Seventy-six selected native geometry,
spatial crossing, moving-light and sensory cases pass, including the existing
ordered ray reference matrix and a huge finite-radius input. Live gain and complete
ordered Gallery parity remain unmeasured.

Remote native-owner diagnostics completed three ordinary six-cell samples each.
Observer counts 7→37 (registered handlers 48→228) leave six recomputes, 48 sensory
candidates and 24 handler invocations unchanged. Instrumented receipt medians are
140.074→139.968 ms. Extra deployed creatures lack active opportunity-attack
registrations, so this establishes no remote reaction-handler result.

Remote Grease conditions 10→1,000 increase rejected handler-index candidates from
84 to 6,024 and event discovery from about 1.3 to 9.7–11.0 ms instrumented, while
actual invocations stay at 24 and sensory candidates at 48. Local result/operation
shape comparisons pass, but direct small/large ordered packet comparison finds a
local observer-order cohort difference. Full cross-axis matching cohorts pass all
78 packets (39 per seat) and one shared injective 1,243-identity mapping:
observer-small with Grease-large, observer-large with Grease-small. No event or
light-value ordering was normalized away. These three-sample diagnostics are not
latency-distribution acceptance; the Grease axis couples conditions and handlers.
The demonstrated rejected-candidate scan is the next event-owner investigation.

Checkpoint 18 complete validation passes all three lanes: 58 commands, 100 ordered
packets, 6,397 injective identities, 58 committed receipts and identical 341-entry
source manifests. Plain uses Fighter→Sorcerer; coarse/detail use Sorcerer→Fighter.
Enumeration is 12.333 ms versus 13.405 ms in checkpoint 17's detailed run, and FOV
is 25.840 versus 27.750 ms. Actual visited coordinates fall to 16,518 while the
12,552 admitted targets are unchanged. Coarse worker is 71.906 ms including
5.293 ms GC; six observer recomputes are 29.195 ms and twelve FOV calls 13.785 ms.
Plain command 50 is 116.360 ms observed receipt and 67.365 ms native dispatch;
command 36 is 139.909 ms, route 17.629 seconds. Receipt variation dominates the
apparent regression against checkpoint 17's 78.346 ms receipt/66.715 ms dispatch.
This is a modest geometry simplification, not evidence of another large speedup.

Checkpoint 19 candidate removes one duplicate event-discovery bucket. Positioned
events already read their local position index and global simple-handler index.
The unfiltered trigger bucket contains those same global handlers or positional
registrations that the old loop subsequently rejects. Skip that bucket only for
positioned fallback lookup; source/target-filtered predicates, their order, all
non-positioned lookup and native opportunity-attack invocation remain unchanged.
No new registry or index is added. Existing positional lifecycle updates stay in
charge. A new public mixed-handler case covers multi-position order, simple and
source/target/both filters, disabled handlers, position updates, removal and the
legacy non-positioned fallback. Thirty-eight focused native cases pass, including
Grease entry/turn cleanup, spatial lifecycle, opportunity attacks and loader
rollback. A broader event batch has 50 passes and three existing CombatLogEntry
fixtures fail because they omit the required data field before reaching this
changed boundary; their expectations and models are not modified.

Checkpoint 19's measured Grease candidate visits are now 24 at both 10 and 1,000
remote zones. Discovery is 1.015–1.120 ms at the small size and 1.021–1.033 ms at
large, versus 9.720–11.037 ms for the prior large run. Actual invocations remain24;
local recomputes and sensory candidates stay fixed. The small worker outlier at
219.852 ms remains included. These are instrumented three-sample diagnostics.
Gallery plain command50 is 80.013 ms observed receipt and 67.952 ms dispatch;
coarse worker70.796 ms includes3.191 ms GC. Full ordered validation is running.

The next separate scaling axis explicitly installs native opportunity-attack
handlers on distant opposing goblins through the same helper used by encounter
assembly. They remain outside the four human turn-bearing combatants. Setup checks
positive native reaction budget and actual adjacent melee threat before measurement.
This distinguishes active remote reaction slots from the earlier observer-only
axis. Observer/possession/handler co-growth remains an explicit native-fixture
confound; no gameplay or reaction-dispatch optimization is implied by the probe.

Checkpoint 19 Gallery validation is complete: all three lanes match 58 semantic
commands, 100 ordered packets, 6,397 identities and 58 committed receipts with
exact timestamp arithmetic. All 341 source entries match across the lanes.
Plain/detail are Fighter→Sorcerer; coarse is Sorcerer→Fighter. Large Grease scaling
passes all 78 packets jointly across two seats with 1,243 identities. Small Grease
passes all 39 seat-0 packets against the matching old and new large cohort, but
seat-1 initialization has a different native local observer order. This remains
an explicit full-two-seat parity limit for the small lane. Each scaling lane has
21 command→journal cursor bindings and three validated ordinary 30→0 moves.
Scaling stores elapsed summaries and receipt-derived cursors, not raw receipt
timestamps; exact timestamp arithmetic is established by Gallery, not reconstructed
for scaling. No source/event/observer order was discarded to force equivalence.

Active remote reaction diagnostics now pass full two-seat ordered comparison
against matching native observer-order references: 78 packets, one injective
1,243-identity mapping and 21 command-to-journal bindings per size. Adding 2→32
distant active reactors raises handler invocations 36→216 and threat queries
24→204. Full instrumented invocation cost is 1.295→6.660 ms; processors account
for 0.481→2.992 ms. Six local recomputes and 48 observer candidates stay fixed.
Native observer/possession/handler co-growth and differing observer-order cohorts
remain explicit limits; this is not a pure axis or distribution acceptance.

Checkpoint 20 avoids creating passive dispatch evidence only after an unchanged
native invocation has produced NO_EFFECT and no dispatch observer is registered.
Listeners are checked after execution so a handler or child can install one for
the current dispatch. Every invocation still advances the dispatch cursor; all
effective and subscribed paths retain their existing DTO, validation and native
presentation logic. Empty handler names retain the original validation path.
Binding identities were already validated in the immutable native BehaviorBinding.
No handler is pruned, and no cache or new owner is added. Fifty-three selected
native queue, opportunity-attack, dice and class-presentation cases pass, including
late subscriptions, nested-child order, cursor gaps and callback-free effective
interventions. Independent actual-source review, live timings and full recorded
parity are still required. This can improve a constant factor; it does not resolve
the remaining linear scan of active remote reactions or meet the whole target.

Checkpoint 20 validation passes all three Gallery lanes against the matching
Fighter→Sorcerer reference: 58 commands, 100 ordered packets, 6,397 identities,
58 receipts and exact timing arithmetic per lane. All five Gallery/reaction
source manifests have the same 341 entries. Plain command 50 is 117.853 ms
observed receipt and 67.376 ms dispatch; coarse is 72.948 ms including 5.771 ms
GC, and detail is 177.349 ms including 6.309 ms GC. No whole-route improvement
is established. The remote reaction wrapper falls from 6.660–6.929 to
4.380–4.874 ms at 216 invocations; native processor timing also varies, so not
all wrapper savings are attributed to the omitted DTO. Small scaling passes
all 78 two-seat packets with one shared 1,243-identity correspondence. Large
scaling has a new joint observer-order cohort: each seat's 39 packets matches
its appropriate historical cohort, but no shared two-seat correspondence is
claimed. Both retain 21 cursor bindings and three ordinary 30→0 moves.

A supplementary legacy manual no-effect test could not collect because it
imports the removed AuthoredBehaviorAttribution symbol. It remains unchanged
and is not counted among the 53 passing native cases. An event trigger-key
rewrite is deferred: the apparent 3.25 ms lookup self cost contains a confirmed
3.03 ms GC pause, leaving only about 0.33 ms of directly removable construction,
hashing and equality work. Independent one-seat capture review likewise finds
no large duplicate serialization pass: 49 retained detachments preserve mutable
payload isolation; graph traversal and the one BaseCost conversion are small.

The next authorized diagnostics vary distant objects, retained native history
and explored memory using the existing native scaling runner. A separate geometry
candidate would enumerate only existing local support coordinates through a
GridMap-owned support index. It must preserve x/y order, every fresh Tile flag
and predicate read, and all support add/remove/replace/clear/rollback behavior.
No origin cache or opacity retention is proposed. The current Gallery's 3,966
absent positions out of 16,518 probes limit its potential gain; dense-map overhead
and retained index size must be measured before retaining the experiment.

Checkpoint 20's object/history/memory sweep is complete. All 18 instrumented
samples keep six observer recomputes, 24 native handler invocations, 48 observer
candidates and 36 world updates. Objects 10→1,000 pass complete joint two-seat
measured packet comparison. Retained history 10,462→20,341 events differs only by
documented command/cursor/revision/version offsets; raw packets are not identical.
Explored memory grows from 373 to 10,285 seen cells and 14 to 1,000 objects for
seat 0 while seat 1 stays fixed. The memory-large worker samples are 134.596,
107.423 and 101.319 ms versus 101.232, 101.516 and 98.745 ms small. The tail has
no established cause. Native exploration also grows history and changes observer
order in both seats, limiting pure-axis and full ordered payload claims.

Checkpoint 21 indexes support coordinates only, in bounded sorted column chunks
owned by GridMap. Every committed assignment updates it idempotently, including
reentrant acceptance and partial failure; remove/clear/reset and loader rollback
retain their existing ownership. FOV traverses supported coordinates in the same
x/y order with fresh native Tile predicates. No opacity values or prior viewpoints
are retained. Initial geometry measurements use ten distinct origins at each
radius, normal GC and setup outside timing. Radius-60 means after the first call
are open 6.533→3.999 ms, sparse blockers 11.040→8.204, dense blockers
11.368→11.740, and holes 8.720→8.606. These small diagnostics show a promising
enumeration reduction and dense-case overhead; they are not live acceptance.

The new reentrant lifecycle fixture exposed an existing native failure boundary:
an acceptance handler removes the old Tile, then outer replacement commits before
old-owner cleanup raises. Its preflight membership also leaves a missing-support
frontier entry. The test observes the restored cell from a fresh zero-radius
origin, then validates normal removal/recreation. This rework does not repair or
bless the unrelated stale neighboring route after that interrupted mutation.

Checkpoint 21 is retained as a modest geometry change after 80 selected native
cases and complete ordered Gallery parity. All three Fighter→Sorcerer lanes
match 58 commands, 100 packets, 6,397 identities and 58 committed receipts with
exact timestamp arithmetic; their 341 source entries match. Plain command 50 is
83.034 ms observed receipt and 69.124 ms worker dispatch versus checkpoint 20's
117.853 and 67.376 ms. Thus no whole-command engine gain is established. Coarse
worker is 64.850 ms including 1.501 ms GC; twelve FOV calls total 10.313 ms and
six observer recomputes total 26.956 ms. The previous coarse run included 5.771 ms
GC, so the entire 8.098 ms elapsed difference is not algorithmic savings.
Detailed enumeration drops 12.463→10.736 ms and supported probes
16,518→12,552, with the same 12,552 admitted targets. Native 129×129 support
retains about 1.24 MB of index containers and coordinate tuples, roughly
74 bytes per current Tile, excluding allocator overhead and shared integers.
This index never retains previous viewpoints. Further geometry micro-variants
are deferred in favor of coherent repeated event/observer work.

The next observer-input slice replaces the existing position-only contact index
with immutable ordered entity/center-object membership rows at the same GridMap
commits. It adds no parallel registry. Sensory discovery retains its occupied-cell
filter, candidate-position order, complete entity authentication before predicates,
and a fresh center-membership read after entity predicates. Every visibility,
stealth, invisibility and sense predicate remains live. Public defensive getters
and height-specific bands keep their contracts. This removes repeated band
flattening, empty membership copies and UUID sorting; the measured getter/sort
ceiling is about 3.8 ms under full instrumentation, not a several-fold command
gain. Native occupancy rollback, object placement/move/removal/destruction,
multiband membership, reset and cold replay must pass before live measurement.
The separate event-store audit finds no large duplicate pass: only 0.424 ms full
profile is even theoretically available in repeated completion evidence, whose
later evidence boundary is semantically required. That micro-change is deferred.

Checkpoint 22's membership rows are implemented and actual-source anti-OOP review
passes. Sixty-one selected native movement, initial replay, occupancy, geometry,
crossing, hazard and loader cases pass, followed by 18 multicell/contact cases.
Three new cases validate multiband/multicell rotation, movement and removal,
defensive public getters, historical snapshots and cold sensory replay. The
contextual-modifier cases add/remove an object during an entity's passive-contact
query; later object observation and replay must see the committed membership.
Broader direct touched-delta emission is deferred: its measured 8.756 ms full
profile ceiling includes required comparisons/output sorting, and borrowing old
maps would lose current detached-before semantics under reentrant callbacks.
Live source is now frozen for checkpoint 22's plain/coarse/detail measurements.

Checkpoint 22 passes complete Gallery validation: all 58 commands, 100 ordered
packets, 6,397 identities and 58 committed receipts per lane with exact timestamp
arithmetic. The three 341-entry source manifests match. Plain/detail use
Fighter→Sorcerer; coarse uses Sorcerer→Fighter and its matching historical cohort.
Plain command 50 is 107.152 ms observed receipt and 62.389 ms dispatch versus
checkpoint 21's 83.034 and 69.124 ms. Detailed cell-contact work falls
11.977→8.946 ms with the same cohort, while boundary contacts remain about
8.3 ms. This supports the bounded membership saving, not attribution of the
entire plain dispatch change. Coarse worker is 62.564 ms including 1.407 ms GC;
six recomputes total 24.472 ms and twelve directional FOV calls total 10.656 ms.
An isolated 36-cell membership query compares exact ordered values with normal
GC: medians 0.068→0.016 ms for one object/cell/one band and 0.165→0.016 ms for
eight objects/cell/three bands. Those are getter measurements, not command times.

The next qualification lane uses 200 ordinary alternating native six-cell moves
in the existing all-human scaling fixture. This checks sustained current-state
retention and tails without AI changing the local observer cohort. It is a
separate two-seat/radius-10 fixture, not the large Gallery target cohort. Retain
each direction/output stratum separately and do not call its aggregate p95 the
Gallery result. Four constant-time current-index size counters extend the
existing temporary census; ordinary runtime code is unchanged. Final target,
matched fine-cadence Gallery qualification and diagnostic removal remain open.

The checkpoint-22 sustained fixture completes 200 ordinary moves, 100 per
direction, and 400 two-seat packets. Each move has six committed walking steps,
30→0 feet, fixed observers and identical within-direction local values and
ordered operation/log shapes. Receipt median is 82.800 ms; worker median 40.207.
East receipt/worker p95 is 92.237/40.983 ms; west is 218.142/206.031 ms. Pooled
receipt p95 94.013 ms hides the west tail. Seven major worker pauses grow from
169.881 to 419.839 ms while native history grows 10,314→40,114 events. Support,
contact and FOV index counts stay 715/2/11; path entries are 6 before and 1 after
each move. These are current-index cardinalities, not a bounded-heap proof.
No GC cause is established by this plain lane. A matched 200-move lane now
records passive GC start/stop timestamps and generation only; collection policy,
normal output, receipt clock and native commands stay unchanged.

Independent output-axis diagnostics completed seats, sight radius and affected
observers at small/large sizes. The 100-contact fixture failed setup because its
last row lacked supporting Tiles; the failed run is retained and makes no
performance claim. Both contact sizes now receive the same fixed support strip
before native placement and will be rerun. The worker revealed a separate
ownership lead: BaseCost.model_validate(Cost) returns the identical runtime Cost,
including its bound Move callback and action→cost cycle, despite BaseCost's
explicit callback-free serialized-payload contract. A tiny native identity check
confirms that behavior; the public five serialized fields are unchanged. Exact
movement consumers and event-time cost isolation are under independent review
before a narrowly scoped ownership repair or any latency claim.

The passive GC lane confirms the sustained tail's immediate cause: seven
generation-2 collections cost 129.250→377.999 ms and report zero collected
objects. The same commands have 37.863–39.967 ms of non-GC work. These diagnostic
attributions do not replace or subtract from raw receipt/worker latency.

Checkpoint 23 repairs the existing callback-free movement cost boundary at the
two Move producers: declaration and EFFECT explicitly copy BaseCost's five
finite fields. Runtime affordability callbacks remain on the action; fixed
payment, native step spending and actual-cost completion remain unchanged.
A native regression first reproduced historical cost rewriting after a later
runtime edit. It now passes, including action lifetime release while EventQueue
history remains readable and cold-encodable. Sixty-five selected native cost,
navigation, reaction, combat-action and occupancy cases pass. Independent review
notes one removed accidental behavior: an in-place declaration cost mutation no
longer aliases back into runtime Move.costs; no authored handler uses it. This
is explicit historical-data ownership, not a general callback-purity assumption
or a global Cost schema change. A matched 200-move GC lane measures whether the
retention repair materially affects the tail; no gain is claimed in advance.

The next capture slice follows a measured output multiplier: adding 30 locally
affected observers causes 360 extra retained sensory copies (30×6 steps×2 seats),
although neither audience observes those additional actors. Full instrumented
detachment grows about 25.7→97.7 ms. Preserve all original terminal/version
admission, actor checkpoints and observed-source selection. Only the application
projection path may replace an unobserved native sensory payload with the existing
technical Event header, explicitly marked NOT_DISCLOSED. Require no context,
combat log or effective handler presentation, and retain every exact referenced
source payload. Default native capture remains complete. Headers preserve actual
identities, phase, grants and ancestry; no empty fabricated sensory delta or new
wire family is introduced. All other unsupported/failed capture dispositions
remain fatal. Anti-slop and anti-OOP review must cover actual producer/consumer
closure, native multi-observer light/movement output, attributed/logged fallback,
referenced versions, failure isolation and cold replay before live measurements.

Checkpoint 23's matched sustained run confirms the lifetime repair but not a
substantial GC tail improvement: seven gen-2 pauses still grow 127.966→373.515 ms.
All 200 native six-step commands and 400 packets pass local/budget checks. Full
ordered parity is established for seat 0 only; seat 1 has reversed native
observer order. Gallery has full 58-command/100-packet/6,397-identity parity and
58 exact receipt bindings. Command 50 is 75.080 ms receipt and 61.505 ms worker.
This uses 1 ms receipt polling versus checkpoint 22's 10 ms, so the 32 ms receipt
difference is not an engine gain. Fixed current index counts do not bound heap.

Checkpoint 24's guarded foreign sensory admission passes actual-source anti-OOP
review and 34 selected native capture/projection/replay cases. Native light tests
compare first-only, second-only and shared audiences through DIM→DARK→BRIGHT,
including complete source evidence, public packets, retained PresentationTarget
folds and cold archives. Single audiences retain their last observed DIM value
when darkness removes their grant; the shared audience observes DARK before its
last grant closes. Recorded context/log/handler fixtures retain complete payloads;
logs and handler attribution survive actual public projection and cold replay.
An invisible native torch user keeps witnessed light children without disclosing
its action. Split-seat application lineages equal independently initialized full
capture. Existing mutable isolation and later-seat failure checks also pass.
The retained native reducer recognizes exactly a sensory Event header carrying
NOT_DISCLOSED after its concrete sensory case; unsupported handling stays intact.
Plain Gallery with 1 ms polling and the affected-observer output axis now measure
the candidate. No speedup is claimed before these measurements and full parity.

The next reduction slice follows the measured receipt-reader delay: canonical
public reduce_operation currently copies/folds the full audience and recomposes
its visible view for every SensoryFact, although all facts belong to one atomic
operation. Reuse the existing AudienceComposition only within this detached
successor operation. Initialize it after the existing cursor-gap check, before
the first lineage containing a non-canceled SensoryFact; forward it through the
existing _apply_lineage/_apply_nodes path and reuse it across later lineages.
Only the existing sensory case publishes its perception/view. Do not eagerly
replace the copied senses, publish at operation end, or acquire anything for a
no-sensory operation. Existing contact_overrides preserve intervening observations
and terminal departures; scalar own-entry placement remains until the next real
sensory boundary. Public inputs/prior outputs remain detached, rejection remains
atomic, and no runtime persistent owner, cache, packet or protocol is added.
Read-only pipeline review approves this minimal plumbing. Validate all saved
Gallery operation outputs against the frozen previous reducer, native/cold
multi-observer packets, no-sensory/trailing observation/departure behavior and
late rejection isolation. Anti-slop and anti-OOP review the actual source and
measurement before retention. Benchmark parsing/reduction and live receipts
separately; do not call a probe-only saving native engine work.

Checkpoint 24 live validation passes 58 commands, 100 ordered packets, 6,397
identities and 58 exact receipt bindings against the matching Sorcerer→Fighter
reference (6,307,680 bytes). All three 341-source manifests match. Worker/receipt
command 50 are 61.806/104.648 ms. Affected-observer detachment under full profiling
falls about 90–98→53–60 ms at size 32; headers still have required copy work.
Both scaling seats reverse native observer order versus checkpoint 22. The
three samples per size pass local before/after values, ordered local shapes,
endpoints, budgets, output bytes and census, but complete ordered packet parity
is not established. Small sample 3 has a 282.091 ms receipt spike; no GC timing
was collected, so its cause remains unattributed and it stays in the results.

Checkpoint 25's minimal public operation fold passes actual-source anti-slop and
anti-OOP review. Forty-two selected native/recorded/cold cases pass in 7.38 s,
including twelve grouped/separate permutations of no/live/canceled sensory,
observations, own-entry placement, terminal departure and late rejection. A
selected legacy application test cannot collect because it imports removed game
modules; it is unchanged and not counted. Independent replay of all 100 saved
checkpoint-23 records equals the frozen prior reducer at every state and leaves
every input state unchanged. Five naturally collected command-50 samples give
public reduction median 14.795→3.281 ms, a 77.8% reduction. Profiling confirms
12 complete audience traversals become one acquisition and 12 local folds.
Typed JSON validation is separate and includes an unattributed 98.178 ms outlier.
The first live same-order/1-ms-polling command gives receipt 104.648→92.884 ms,
worker 61.806→61.842 ms; complete new-lane validation is pending. This is reader
latency improvement, not a native worker gain. One detached acquisition still
scans current audience memory; no memory-locality or whole-target claim follows.

Native history review confirms an unresolved contract boundary behind growing
GC scan cost. The queue retains original Event identity until reset, and native
lifecycle tests require historical UUID lookup to return that same object and
late children to update completed parents' raw child lists while frozen lineage
metadata stays fixed. Acyclic live Pydantic events remain GC-tracked. Replacing
old events with serialized/lazily reified records would change that historical
identity/mutation contract; it is not an authorized optimization here. No GC
policy changes, hidden collection or history deletion are introduced. The cost
ownership repair remains valid, but a second comparable native leak has not
been established. Remaining native geometry/dataflow work is under review.

Checkpoint 25 final lane audit passes: plain/coarse/detail each match the
Sorcerer→Fighter reference across all 100 ordered packets, 6,397 injective
identities, 58 semantic commands and 58 exact committed receipt/cursor bindings.
Each journal retains 6,307,680 bytes. All 341 source entries match across lanes;
only reduction.py changed from checkpoint 24. Coarse command 50 is 61.711 ms
including 1.373 ms GC, with six observer recomputes 23.491 ms, twelve directional
FOVs 9.754 ms, capture/application 11.547 ms. Full profile is 170.100 ms including
5.006 ms GC. Its overhead must not be mistaken for plain runtime work.

The same coarse endpoint trace stores the committed receipt at submit+67.542 ms,
sends the successful GET body at +74.020 ms, and the SDK observes it at +94.342 ms.
The SSE record completes at +73.827 ms; consumption enters at +78.417 ms, then
journal writing takes 3.437 ms and typed validation/reduction 5.847 ms. Host stage
and flush take 1.158 ms and index commit 0.004 ms. These observations keep client
loop/probe interference in the acceptance clock; no latency is subtracted.

The corrected current-contact output axis passes native placement and output
validation at 1/100 daggers, three moves per size. Both have the same 10,270 Tiles,
45-cell support strip, five observers, 36 handlers and matching 341 source entries.
Every move has six cardinal walking steps, twelve spatial and twelve sensory
facts, one movement fact, no attack/reaction/log/content additions, and HUD budget
30→0. Both seats initially observe all contacts. At size 100 the mover retains
94 east/99 west contacts while its companion retains 100; movement deltas change
or remove only 1–6 identities, and the other seat's current contacts remain
unchanged. This is a current-visible-contact axis, not 100 newly emitted contacts
per step. Profiled receipts are small 148.554/135.403/115.873 ms and large
157.466/149.021/150.983 ms; no stable latency distribution or equal-output claim.

The human rejected immutable archival replacement of completed native history
on 2026-10-13. Preserve all native events, their same-object historical lookup,
later mutation and existing relationships. Do not implement the archival direction
below. Its feasibility notes remain only to document the rejected alternative.

Rejected history direction (not implementation authority):
archive quiescent completed lineages after native execution, nested callbacks,
batches and all-seat capture, retaining unfinished/interleaved resource work as
live events. Preserve every version UUID, cursor, exact referenced source and
frozen completion metadata; later-child relationships remain queue-owned. Keep
a single history owner and no decoded-history cache. Existing passive recording
schemas cover ordinary movement, but condition application/removal require their
existing ConditionFact plus neutral EffectOrigin: future children inherit that
origin from parents, and the current generic header loses it. Duration and its
executable expiry callbacks stay with the live condition owner. EventQueue may
not import the higher player codec; ownership/composition must respect the DAG.
Unrepresentable payloads stay live, archive preparation failure retains the
original lineage, and fallback growth must be measured before claiming a bounded
GC graph. External references and other native indexes may still retain objects.
Any encoding/rehydration belongs inside the full operation/lifetime measurement;
this direction could reduce history scan tails but does not establish a faster
ordinary command or the 9.5 ms goal. The exact architecture and native-consumer
changes need a separately validated extension after human guidance.

Further NumPy output filtering and event micro-adjustments are deferred after
independent review. Directional sparse output is only 7.13 ms of 24.31 ms under
full profiling; zero-cost output leaves about 16.4 ms. About 90% of acquired
supports are visible, six light solves cost only 1.96 ms full, and native contact
outputs already reuse 1,328 of 1,380 values. The application capture stage totals
11.55 ms coarse, so even eliminating it leaves about 50 ms dispatch. These are
measured ceilings, not proof that the whole target is impossible. They do not
justify replacing a demonstrated owner problem with another speculative small
geometry/copy variant. The accepted reader reduction remains the measured gain;
the target, history decision, positive-budget path-choice decision, full latency
qualification and final diagnostic removal are still open.

Checkpoint 25 independent review is complete with no blockers for the retained
capture and reduction changes. The archival history direction was subsequently
rejected by the human. Any alternative's eventual validation must
include archival preparation, detach/encode, index replacement, allocation/GC
and later exact-version reads in their actual full command/lifetime clocks.
Publication may not move archival cost after the receipt to hide it. Immutable
payloads could reduce GC traversal, but serialized bytes and queue indexes would
still grow; neither bounded history nor history-independent latency is established.

Human clarification on 2026-10-13 distinguishes route choice from movement
distance. The saved unreachable-rough-tile witness has identical returned cost
maps; its one differing route has three diagonal steps and costs three units
(15 feet) under both solvers. This proves a choice change in that case, not a
general guarantee about execution cost: flying elevation, route-dependent rules
and interruptions require separate coverage. Changing tied routes has not yet
been authorized. No navigation solver change is implemented.

The next authorized investigation preserves native history and uses a separate
allocation/ownership lane on the actual production worker entry. Add an opt-in
heap census to the existing temporary movement-scaling diagnostic. Capture before
the first measured native move and after the final move, using the same 200-move
fixture. Report gc.get_objects type counts and shallow sizes plus explicit native
history/index/current-owner reachability among those actual tracked objects.
Exclude frozen import objects and executable/module/class graph traversal; label
those exclusions and overlap instead of calling root counts exclusive ownership.
Separate Event metadata and registry growth from required family payloads. Return
only scalar summaries and release census references after each boundary. Keep
the existing collection policy unchanged. Census work perturbs allocation and
collection, so no timing from this lane qualifies as a speed improvement; retain
raw operation timings and census durations. Fix only demonstrated surplus owners,
duplicate retained values or unnecessary allocation, with native history identity,
late-child mutation and cold-replay tests at the actual changed boundary. Root
performs edits; Sol 6.1 xhigh agents remain read-only adherence/anti-slop,
anti-OOP/navigation and retained-graph reviewers. No new history owner, lifecycle
policy, collector replacement or generic retention framework is introduced.

The live 200-move ownership census completes with history 10,351→40,114 and
collectible tracked inventory 349,595→859,665. History reaches 494,312 of the
510,070 additional tracked objects; overlapping current/audience counts cannot
be added. The current BaseObject registry grows 649→848, entirely explained by
199 additional ExtinguishTorchAction instances, absent from history's graph.
All other measured registry counts remain flat. This is a demonstrated surplus
owner, but its ceiling is small: current-native reachability outside history
grows only 2,915 objects. Removing it cannot by itself solve the major GC slope.

The bounded ownership repair sets use_register=False on the four on-demand
portable/fixed torch action constructors. Discovery results retain and pass the
actual action; execution already copies it unregistered. Preserve all binding,
affordance, source-item snapshots and held discovery-row execution. Do not change
the shared dynamic-action binder, authored/directly constructed actions, registry
policy or any native Event. Native tests must reproduce repeated query retention,
then verify discarded query actions are released while held rows still execute
ignite/extinguish and prior Event identity/cold records remain intact. Reviewers
confirm the actual producer/consumer boundary before retention. Any improvement
claim needs a matched lifetime census; no large latency gain is predicted.

The human subsequently requested safer tied routes, fewer unnecessary zig-zags,
and investigation of a clear direct-route shortcut. This supersedes the unresolved
question about accepting arbitrary current solver ties. The working interpretation
preserves minimum movement cost and prefers known safety and straighter tied
routes; it does not authorize more expensive detours, hidden-world knowledge or
new hazard severity weights. Validate a concrete routing extension before source
changes. Distinguish all-destination discovery from one selected route; an optical
ray alone does not prove movement legality, minimum cost or comparative safety.
Continue the history-preserving ownership work alongside this routing design.

Checkpoint 26 ownership repair is independently validated. The matched 200-move
heap lane keeps BaseObject at 645→645 and ExtinguishTorchAction at 1→1, versus
649→848 and 4→203 before. Tracked growth falls 510,070→506,886: 3,184 avoided
surplus objects. All native history/index graphs, Event metadata and family
counts are identical at both measurement boundaries; history remains
10,351→40,114 Events. Complete ordered parity passes all 400 measured two-seat
packets with one injective mapping of 26,855 identities. Both lanes have 1,006
commands, 3,624 journal records and 55,718,097 bytes. Only torches.py and the
temporary census runner differ in their 341-entry source manifests. No speed
or GC-slope improvement is claimed from these allocation diagnostics.

The three new native torch lifetime tests fail before the fix and pass after.
The selected batch has 36 passes and three failures in unchanged Event lifecycle
fixtures constructing CombatLogEntry without required data. They fail model
validation before the relevant behavior and are not counted as passing. The
repair preserves held discovery templates through execution and native history
identity/encoded values through later toggles.

Routing clarification: existing prefer_safe already permits a longer affordable
hazard-free alternative. Preserve that policy; minimum-cost tie improvements
apply within normal and hazard-avoiding searches, rather than removing safe
detours. All-target discovery and exact preview-to-execution retained paths
remain the public boundary. A clear optical ray is insufficient: direct
movement candidates need native transition, known-domain, endpoint and actual
cost checks. Safety evidence must come only from existing perceived hazards
and visible-hostile threat domains. Do not invent relative severity weights
or claim globally minimum risk from checking a bounded set of candidates.

The independent discovery-locality slice removes two whole-map has_any_hazards
guards from Entity movement target collection. Requested behavior: all offered
paths, costs, hazard flags, safe alternatives and OA evidence stay the same while
hazard work depends on offered paths. Boundary/input: native available-action
discovery after current navigation and current conditions, in both fast and
requirement-bearing movement templates. Expected output: identical choices,
previewed route and committed steps with known/hidden/local/remote hazards.
Keep the existing per-path is_position_hazardous_for calls and their order; do
not cache hazard callbacks, invent purity, or change GridMap.has_any_hazards for
other callers. This is independent of the still-reviewed tied-route solver
extension. Anti-slop/adherence and anti-OOP reviewers must review the actual
change and selected native cases. Measure the same positive-budget large-map
lane before/after; discard the change if extra local work defeats the benefit.

Discovery-locality review identifies one existing temporal artifact: the slow
branch captured the global hazard flag before per-target requirement/cost
callbacks. If such a callback introduced the first hazard, the old false flag
suppressed subsequent local hazard queries during that discovery. Unconditional
local queries observe the current hazard instead. This follows the requested
current known-safety behavior, but is explicitly not a claim of arbitrary
callback-mutation parity. No new hazard cache or callback-purity assumption is
introduced. Fifty-eight selected grid, current-hazard, movement-demand, OA and
server preview→command cases pass in 6.84 seconds after removing the guards.

Validated navigation locality design: retain the existing BFS and Dijkstra,
including their fractional-cost behavior. For a finite movement budget, inspect
unit-cost eligibility only for supported cells in the clipped Chebyshev box
centered at the origin with radius equal to that budget. Reuse the existing
current support-column index; read costs fresh and add no retained cost cache.
Every admitted native terrain cost is an integer at least one and spatial
expenditure is nonnegative. Even legacy fractional distance truncation advances
at least one unit per entered cell, so a budget-admitted route cannot leave
this box. Keep the unlimited query's existing classifier and zero-distance
sentinel. Negative budgets have no destination beyond the origin.

Requested behavior/boundary: a bounded native path query must not change its
local route or cost because an unreachable distant rough Tile was added. Keep
all destination coverage, local weighted terrain, corners, subjective collision
and navigation demand. This deliberately removes remote terrain's accidental
solver tie influence under the user's route-choice guidance. It does not claim
to preserve side effects from evaluating unrelated remote contextual costs.
Anti-OOP review accepts this proof and prefers reusing the existing algorithms
over a new integer frontier plus fractional fallback. Adherence review checks
the actual bounded enumeration. Tests reproduce the remote-rough witness at the
GridMap boundary; native route/preview/step suites protect resulting behavior.
Measure small/large positive-budget cohorts before claiming a locality gain.

Bounded route-preference extension: keep normal and hazard-avoiding path maps
separate. Entity compares each retained walking path with at most the two
monotone adjacent candidates (diagonal-then-cardinal and cardinal-then-diagonal).
For an axis or 45-degree destination these collapse to the straight route.
Preserve all destination ordering and the existing safe-route selection policy.
Reject candidates with unknown vertices, illegal native transitions/endpoints,
nonpositive costs, noninteger per-edge costs, or different actual cost from the
retained route and its published cost. The integer eligibility is deliberate:
Move currently rounds total declaration cost and individual paid steps
differently for fractional expenditure; this work must not silently change
that boundary. Leave such routes untouched.

Compare disclosed hazard-cell sets and visible-reactor exit sets using subset
dominance. Add no new hazard or reactor. Prefer a strictly safer candidate;
when safety sets are equal, prefer fewer turns. Keep the original for
incomparable risks or equal ties; never invent severity weights. No Pydantic
exposure objects are needed for comparison, only the existing threat domains.
When the retained path already achieves the 0/1-turn lower bound and has no
known risk, it needs no alternative. This is bounded candidate selection, not
a global risk optimizer or a replacement for all-destination reachability.
Preview and execution continue to bind the same retained path. Validate native
known/hidden hazards, known OA exposure, terrain/corners, actual paid cost,
fractional exclusion and ordinary server route binding before retention.

Checkpoint 28 bounded classification passes 67 selected native cases. Its
remote-rough regression fails before and passes after; weighted boundaries,
negative coordinates, holes and explicit fractional compatibility pass. In the
matched three-sample large-map positive-budget diagnostic, compute_paths changes
60.820/59.963/58.837 ms → 5.127/5.209/5.125 ms, with unit classification
55.696/54.940/53.919 ms → 0.405/0.402/0.414 ms. Discovery median changes
43.468→25.970 ms including the separate global hazard-guard removal. These are
profiled owner/three-sample measurements, not a latency distribution or final
Gallery qualification. Local before/after values, endpoints, budgets and ordered
operation shapes pass against the pre-change lane; full packet review follows.

Checkpoint 29 implements the bounded walking-route preference and passes 74
selected cases in 7.58 seconds. Native regression fixtures reproduce avoidable
turns and known hazard exposure before the change. The resulting paths preserve
actual step facts and paid movement while rejecting more expensive rough terrain,
known hazard/reactor exposure and blocked diagonal corners; hidden hazards do
not influence choices. The blocked-corner fixture was corrected before this
implementation to its observed legal four-step, 20-foot route. Existing normal
versus safe preview→command tests still pass. Actual-source anti-OOP/adherence
review and isolated preference-overhead measurements are required before
retention. No literal single-destination ray bypass has been added.

Actual-source anti-OOP and adherence review approve the route-preference
implementation. The requested Entity-level fractional exclusion regression
also passes: a legal one-turn alternative exists, but discovery retains the
existing fractional solver path and cost. This adds one passing native case
to the 74-case batch. The updated manual discovery test cannot collect because
its legacy module imports removed ai.knowledge; it is not counted as passing.
The old zero-local-predicate-call assertion was replaced by public hazard-free
choice output, directly matching the requested locality change.

The three diagnostic navigation lanes have matching local values, budgets,
endpoints, shapes and censuses. Independent packet review detects changed
native UUID-based observer order, so complete ordered packet parity is not
claimed for these lanes. Preserve causal array order in reporting rather than
sorting it to manufacture equivalence. This does not affect CP26's separately
validated complete 400-packet comparison.

Checkpoint 29 final method comparison reports the route-quality cost separately.
Large-map path queries remain 4.970/5.100/5.257 ms; route preference adds
3.481/3.295/3.608 ms and known-threat acquisition 0.722/0.719/0.774 ms. Total
materialization changes 6.775–6.986→10.819–11.272 ms under profiling. This
feature is not itself a speed improvement. The small-map check (10,325 versus
20,225 Tiles) gives path queries 5.248/5.359/5.125 ms and classification near
0.4 ms at both sizes. Preference costs 3.429–3.852 ms at the small size. These
three-sample diagnostics establish remote-tile locality, not final p95. The
HTML now has a separate navigation comparison and an actual expandable CP29
positive-budget call tree, distinct from Gallery CP25 measurements.

The guard-removal callback caveat also includes fast-path fallback movement-cost
evaluation: a callback can introduce a first hazard after the old global guard.
Fresh local checks then see the current hazard. No arbitrary side-effect parity
is claimed or new predicate cache introduced.

The human requested clarification because the preview still showed 92.88 ms.
That was the previous Gallery CP25 result; new navigation data came from a
separate positive-budget fixture. A fresh unprofiled Gallery rerun on CP29 now
completes 58 commands and 100 records (6,301,170 bytes, final sequence 99).
Command 50 keeps the same six-cell route (47,20)→(53,20): SDK observed receipt
76.860554 ms, recorded update consumed 92.921354 ms. Its discovery is
292.025265 ms and preview 8.377771 ms; these remain reported separately from
the established submit→receipt endpoint. No cause is assigned to the discovery
outlier without instrumentation. Native observer order is Fighter→Sorcerer,
versus CP25's reverse; command 11 intentionally changes an equal-length route
from two turns to one. This is a fresh current result, not proof of a controlled
17% speedup or complete old-packet parity. The separate five-move unprofiled
large positive-budget fixture has receipt median 54.843605 ms, range
53.448822–96.052833 ms. No p95 claim from either small sample. The preview now
separates these cohorts and receipt versus consumed-update clocks explicitly.

Independent CP29 Gallery validation completes: all 58 receipt command/cursor
bindings match journal command records with exact ordered clock arithmetic.
All 29 movement commands and 116 committed StepFacts match selected routes,
source actors/endpoints and native 5-foot-per-step spending. Commands 11 and
50 each spend 30→0 feet in six steps; only command 11 changes its intended
equal-cost route. Other actor/stage/endpoint/HP/disclosure counts and cursor
sequences match CP25/CP23. This is command/step/binding validation, not full
old-packet parity. Command50 worker dispatch is 62.223794 ms versus CP25
61.841571 ms: no material worker improvement. Receipt76.860554 ms and consumed
update92.921354 ms use their distinct established clocks. The positive-budget
pathfinding improvement does not reduce the exhausted-budget command50 path
search, which was already origin-only. The remaining ordinary worker cost,
GC tails, final sustained qualification and diagnostic removal remain open.

### Checkpoint 30: remaining worker attribution and isolated execution experiment

The human requested a fresh breakdown of the remaining 62 ms and continued
rework toward 9.5 ms, with a current preview. Ordinary server integration is
verified: server.__main__ creates the production app; connection.launch starts
`-m server.worker` using the repository containing connection.py as cwd.
A restarted server from this checkout therefore uses these retained changes.
Ordinary startup does not import movement_profile_worker.

Fresh CP30 coarse command50 measures 65.388 ms including diagnostic wrappers:
execution51.427, capture/application12.408, dispatch remainder0.196, writes0.218,
and1.138 outside those owners. Execution contains moving-light settlement41.130;
that contains mover recomputation26.255, stationary delta emission2.949,
light FOV0.912 and11.014 outside its wrapped children. Mover recomputation
contains its FOV11.144 and15.111 outside it. GC1.786 ms is already included.
These are attribution clocks, not a new plain speed sample. CP29 plain remains
worker62.224/receipt76.861/consumed92.921. The preview now exposes a disjoint
coarse table that sums to the measured diagnostic window, plus CP30 full phases
and call tree (full elapsed172.046 ms).

Three read-only Sol6.1 extra-high reviews find no established large safe removal.
Contact admission remains fresh; native AreaCondition.get_spatial_observation
reads prior senses.entities/objects, so partial in-place contact publication
would change real inputs. Gallery already has exactly one evidence evaluation
per contact. Capture49 detachments are43 terminal versions plus6 distinct
referenced source versions, with reference deduplication already present.
The two audience folds use different native/public cursors and revisions.
Three JSON dumps cost1.365 ms full. Snapshot/delta and constant-map variants
have measured small ceilings and do not justify another broad rewrite by
assuming their inclusive parents can disappear. No such variant is implemented.

Next investigate execution overhead without changing these semantics. An isolated,
ignored experimental build may compile the existing hot Python owner functions
and run the same ordinary Gallery with normal GC/history/output. It must not
change production imports, shared Python dependencies, packaging or gameplay.
Requested behavior: lower execution cost for the same computations. Boundary:
existing native owner calls and ordinary recorded command/receipt. Input: the
same Gallery route on copied current function bodies. Expected output: exact
ordered native/public results, with all native callbacks and current-state commit
barriers retained. Keep arbitrary Python integer/annotation semantics; do not
introduce unchecked fixed-width arithmetic, speculative caches or parallel work.
Report native callback overhead and copy/serialization costs that compilation
cannot remove. Retain all samples, including regressions; this is an experiment,
not an adopted server architecture or an end-to-end speed claim.

Plan-adherence/anti-slop and anti-OOP reviewers must review this experiment's
scope and evidence. Any production compiled module/build dependency requires
human architectural guidance under HOW_TO_TEST.MD after a concrete result and
proposal are available. A failed or small-gain experiment is not justification
for adding a deployment requirement. The target and diagnostic cleanup remain open.
