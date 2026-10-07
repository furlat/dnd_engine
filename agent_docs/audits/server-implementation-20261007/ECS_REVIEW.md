# Native/application ECS and import-boundary review

Reviewed 2026-10-07 on the working tree based on
`40eb37b9b4cac72ea75d00d7b1545a4e48a5d2a2`.

**Approved within this review's scope.** The final shared application, capture
checkpoint, native event indexes, passive reducer and HTTP documentation retain
their existing owners. The canceled-parent child-retention defect found during
review is resolved and its focused regression passes. No concrete ECS,
import-direction or capture-ownership finding remains open from this review.
This is source and bounded regression approval, not a claim that the full engine
or legacy server suite passes or that performance acceptance is complete.

## Ownership and authority

- Native entities, rules, event production and authored content remain under
  their existing `dnd` owners. Native code does not import `dnd.player`.
- `dnd/player/application.py` composes the same initialization, operation capture,
  projection and reduction path used by desktop and server adapters. Its runtime
  data does not introduce another rules engine or another recorded event tree.
- `EventQueue` owns the UUID-to-raw-index dictionary and lineage lookup. The new
  index is populated with the existing append, cleared by native reset and
  included in the content loader's existing state inventory.
- `CaptureContext` holds only the native generation and end cursor. Capture reads
  existing native indexes, rejects a changed generation, and does not retain an
  additional encounter-wide copy of event history.
- Each `AudienceRuntime` owns its own `CaptureCheckpoint`: recorded actor values,
  observer contacts, observer positions and the next native cursor. Backward or
  overlapping reads and generation/audience changes reset this private fold.
  Terminal retirement prunes private reconstruction without deleting previously
  admitted public identity.
- Admissions still use the original event's perception/identity/location grants
  at the corresponding occurrence. Hidden actor changes may update private
  reconstruction; that does not admit them to the public packet. The checkpoint
  itself is not an API value and does not query live entities to reconstruct the
  player's view.
- Native typed combat logs remain one causal detail tree. Player facts and logs
  refer to admitted recorded occurrences. The shared projector removes hidden
  identities and effect identifiers; it does not require a legacy server helper.
- Content admission uses public descriptors and identities actually disclosed by
  final or intermediate public facts. Existing direct item IDs retain their native
  snapshot fields. Reducers apply immutable descriptor additions before folding
  the operation; initialization supplies seed descriptors through its existing
  envelope field.

## Resolved canceled-lineage defect

The canceled parent was copied with normalized child lineage references during
traversal, but terminal retention then read the original indexed parent. Its
completed child was present in the captured events but absent from the retained
parent's child list. Requesting the whole root branch consequently dropped that
child.

The capture owner changed terminal retention to consume the normalized node.
Original indexed evidence still supplies chronology and admissions. The test
`tests/player/test_canceled_lineage_capture.py::test_canceled_parent_retains_completed_child_in_closed_lineage`
uses native `ActionEvent` publication, a completed child and parent cancellation.
It checks both retained occurrences, both causal directions, child completion,
and unchanged native evidence/cursor. It passes against the final source.

## Import review and OpenAPI

The final static AST review resolves project imports, including relative imports,
and checks each transitive closure. Results are recorded in
`.runtime/server-implementation-20261007/ecs-import-review.json`.

| Root | Local modules | Cycles | Forbidden dependencies |
| --- | ---: | ---: | ---: |
| `dnd.player.application` | 258 | 0 | 0 |
| `dnd.player.reduction` | 37 | 0 | 0 |
| `player_server.app` | 75 | 0 | 0 |
| `player_server.worker` | 263 | 0 | 0 |

Forbidden dependencies checked here are `game`, legacy `server`, `pygame`, `PIL`
and `OpenGL`. No function-local imports or `TYPE_CHECKING` import workarounds
appear in these closures, and there are no native-to-player import edges. The
existing fresh-process decoder/sampler/painter passive-import regression also
passes.

`player_server/openapi.py` and the route response declarations use the shared
protocol schemas. Generated OpenAPI 3.1 has 12 paths, 312 definitions and 625
references, all resolved. Documented game/audience/attachment headers match route
admission. The 400 validation response, command 200/202 receipts and SSE event
schemas match the adapter. No separate mechanics or duplicate protocol models
were introduced by these documentation changes.

## Verification and limits

- Final independent selection: canceled-lineage regression, both hot/cold
  checkpoint tests and the passive decoder/sampler/painter import test:
  **4 passed in 10.15 seconds**. Checkpoint cases compare original-history and
  resumed capture, public encoded values and reductions through discovery,
  hidden damage, reacquisition, equipment/condition changes, death, retirement,
  historical fallback and generation reset.
- Typed-log migration repairs were confined to assertions and one native action
  log fixture in `test_combat_actions.py`,
  `test_content_recovery_behavior_semantics.py` and
  `test_dice_event_semantics.py`. All three complete files passed:
  **62 passed in 13.48 seconds**. No native mechanics changed for these failures.
- The broader engine run was interrupted after it stalled with growing memory;
  its recovered result was **638 passed, 7 failed**, not a full-suite pass. Six
  failures were the typed-log test migrations repaired above. The remaining
  `test_environment_destruction.py` door case
  `[environment.door.fantasy_a1-clear-True-inward]` also fails in the baseline
  source with `ValueError: Item is out of reach` (**1 failed in 3.17 seconds**).
  That unrelated native mechanics issue was left unchanged.
- The manual subjective-stream file now uses typed payloads for all 15 log
  constructors and the common `project_combat_log` boundary. Its four selected
  source test functions passed when run with their native/common imports in
  isolation, including A/B/A application order and hidden-ID/effect-ID removal.
  Ordinary pytest collection is still blocked by unrelated legacy
  `server/world_contracts.py` importing removed `dnd.core.senses`. This is not a
  pytest pass for that file; the obsolete server architecture was not restored.
- Diff whitespace checks passed for this reviewer's changes. No graphics,
  artwork, broad metadata expansion or SDK regeneration was part of this review.

## Public archive policy supplement

The final cohort found that `decode_player_sequence` still attempted the obsolete
public v1/v2-to-v3 upgrade before validating the current v4 packet. The approved
[stream contract](../../SERVER_STREAM_AND_SDK_CONTRACT_2026-10-07.md) requires
audience-local public ordering, historical private-record compatibility outside
the live decoder, and explicit failure for unsupported versions. Old public
packets do not contain enough original grant evidence to safely infer the v4
projection. Relabeling their schema would also retain private ordering values.

The decoder now rejects missing or unsupported public schema versions with
`Unsupported player schema version; reproject the preserved native recording`.
It checks the version declared by the existing `PlayerSequence` owner. The unused
`upgrade_player_sequence` and `_upgrade_causality` public conversion functions
were removed from `compatibility.py`; no replacement conversion or schema
restamping was added.

Private `RecordedSequence`, `decode_event`, original-log upgrade, and explicit
native resolution/spatial/application compatibility remain unchanged. Ambiguous
native damage ownership still reports its specific missing-evidence error. The
old potion compatibility fixture now removes the additive field from a private
native archive and runs the existing decode/project/current-public path. Its
historical `ItemChargeConsumptionEvent` identity correctly preserves `CONSUME`,
and replay still reaches the same final player state.

Bounded verification: **11 public archive/current resolution cases passed**;
after adjusting that private potion fixture, **8 potion/native resource cases
passed in 4.16 seconds**. These cover missing, v1, v2, v3 and future public
versions, current ownership/movement/retaliation replay, retained native
ambiguity diagnostics, and both potion stack cases. No full suite or SDK
generation was run for this policy correction. Source changes are confined to
`dnd/player/reduction.py`, removal of the obsolete public functions in
`dnd/player/compatibility.py`, and the directly affected party, resolution and
consumable test fixtures. The ECS/import approval above remains unchanged.

## Allocation follow-up ownership review

The source review approves the bounded allocation follow-up. This reviewer
authored the native transient-value repair; the root and anti-slop reviewer
independently reviewed that repair. This review independently inspected the
root's content reuse, reducer and public after-value changes. Source approval
does not replace the separate end-to-end latency measurements.

The retained-allocation diagnostic traced actual `BaseObject.model_post_init`
calls. Before the repair, one maximum-HP read retained two `ModifiableValue`,
four `StaticValue`, four `ContextualValue` and one `NumericalModifier`; one
two-character HUD snapshot retained eight, sixteen, sixteen and four
respectively. The same reads after the repair retain no newly registered values.
The default `Ability.get_combined_values()` call still registers its original
eleven objects, confirming that the default behavior was not broadly changed.
Before/after creation stacks are in
`.runtime/server-implementation-20261007/transient-value-registration-before.json`
and `transient-value-registration-after.json`.

The existing `use_register` capability is propagated only through the newly
created value root, its primary/imported channels and its generated base
modifier. Defaults remain enabled. Audited scalar HP, passive-skill, AC formula
selection and snapshot AC paths explicitly opt out. Actual returned combat
values retain their existing default UUID lookup behavior. No shared modifier
is unregistered and no owned registry is swept. That repair made no GC policy
changes; the later worker-entry policy below supersedes that earlier scope. AC
base-delta modifiers preserve the prior factory's constructor fields and
defaults. Normalization, combined bounds, contextual contributions, authored
formula selection and advantage handling are unchanged. The four native files
add no imports, player dependencies, new system owner or parallel state store.

`admitted_content` reuses only descriptors already admitted to this audience.
Descriptors and their nested references, presentation and ordering are frozen.
Actual additions still come from public definitions or disclosed subjective
facts, including intermediate observations; their links are filtered against
public definitions. The catalog is not mutated. `reduce_operation` retains the
same immutable tuple when additions are empty, and still rejects changed
definitions under an admitted identity before folding. Previous player states
retain their content after later admissions.

The `project_after_values` reverse scan is equivalent to taking the maximum
qualifying local occurrence: `_public_occurrences` is the map's sole writer,
inserting each newly admitted native occurrence with the next increasing local
number. The map is neither reordered nor pruned. A late disclosure of an older
native event therefore still delays its covering HUD/log after-value until that
new public occurrence is consumed. Empty maps retain boundary zero. No private
native index enters the public result and no additional index is introduced.

Focused verification: `tests/player/test_transient_value_reads.py` reports
**6 passed in 1.68 seconds**. It covers both imported-channel merge branches,
active/inactive contextual contributions, combined normalization and bounds,
default combined UUID lookup, original owned modifier/value lookup, and repeated
HUD/stat/passive/AC reads with unchanged registry identities and native event
cursor. The root separately reports **49 existing value/equipment tests** and
**5 boundary-file tests** passing, plus clean scoped type checking. The
anti-slop review records its independently authored content-reuse regression and
its execution status. No broad suite ran as part of this follow-up review;
the earlier baseline-door and legacy-server collection limits remain as recorded
above. Performance acceptance remains in the separate performance receipt.

## Passive turn records and final worker-entry policy

This reviewer authored the six-line native ownership repair in
`dnd/controller.py` and `dnd/encounter.py`. `TurnContext` and `AdvanceResult`
override the existing inherited `use_register` default to false. Current and
legacy consumers pass these records directly; the caller audit found no UUID
lookup, contribution ownership or retirement dependency. Explicit registration
remains available. Controllers, combatants, encounters and events retain their
existing owners and lookup behavior. No inheritance, rules, API models or import
edges changed. The root and anti-slop reviewer independently reviewed this repair.

The two new regressions in `tests/player/test_transient_value_reads.py`, together
with the existing human/pass and Codex encounter-boundary cases, report
**4 passed in 2.27 seconds**. A real automated turn reaches the expected human
boundary; repeated waits and context reads preserve returned facts and exact
event history without retaining transient records. The tests also preserve
controller, combatant, encounter and event lookup, and explicit record opt-in.

The root's subsequent `player_server.worker.run_process()` policy received this
reviewer's independent source review. It rejects installed content or existing
native history, warms the process-lifetime protocol identity, collects and
freezes the surviving pre-Start graph, then enters the normal packet loop.
Reusable `start()`, `dispatch()` and `main()` do not freeze objects. This is an
explicit production process-lifetime GC policy change and **supersedes the
earlier no-GC-change statement**, rather than extending that statement to the
final implementation.

Imported registries, callback containers, ContextVars and caches include mutable
objects; freezing is not an immutability guarantee. Those owners remain rooted
for the fresh single-game process. No concrete path was found that would freeze
a newly created encounter or prevent collection of its subsequently released
cycles. Pre-existing cycles orphaned after freezing can nevertheless survive
until process exit. The policy therefore belongs only to the isolated worker,
not to an in-process multi-session API. Frozen objects are omitted from
`gc.get_objects()`, so a smaller normal tracked graph alone would not establish
lower memory use. The review retains this tradeoff and does not claim a universal
latency bound or a cure for live-object leaks.

The final instrumentation receipt
`.runtime/server-recovery/http-long-process-policy-profile-20261007/worker-profile.json`
resolves the source review's collection and lifecycle questions:

- Before freezing, native history, `BaseObject` registry and `BaseValue` registry
  are all empty. A newly allocated cycle is reclaimed after Start.
- GC remains enabled and thresholds remain `(2000, 10, 10)`. Frozen object count
  stays **459,464** from after Start through 1,000 commands, with no later live
  game freeze.
- `BaseValue` stays **2,000 → 2,000** and `BaseObject` stays **535 → 535**, with
  no registered `TurnContext` or `AdvanceResult`. Native event history grows
  **49 → 9,299** while RSS grows **316.57 → 375.55 MB**; this remaining runtime
  retention is reported separately from the repaired transient registries.
- Ordinary runtime collection continues, including a **43.57 ms generation-2
  collection**. The separate uninstrumented 1,000-command End Turn cohort
  measures **109.08 ms maximum consumed-cursor latency** and **52.43 ms maximum
  native dispatch**. These maxima need not belong to the same command.

The bounded worker policy is approved with the measured startup and retention
tradeoffs. The [performance receipt](PERFORMANCE.md) owns the complete evidence,
instrumentation exclusions, startup cost, command distributions and remaining
limitations. This supplement adds no new runtime checks, full-suite claim or
change to the baseline-door and legacy-server limits above.

## Continued Gate B: native reads and startup owners

Signed 2026-10-07 by `server_implementation_ecs`, the independent ECS/import
reviewer. This supplement approves the bounded source changes below. It does
not declare Gate B complete or extend the End Turn results to combat, movement,
AI or startup. The [performance receipt](PERFORMANCE.md) remains the owner of
the measured workloads and remaining acceptance work.

This reviewer independently inspected the navigation, hazard and sensory repairs
authored by the root. `Entity.materialize_navigation` asks the existing hazard
predicate once per distinct reachable path cell, with the same observer. Its
temporary set is exactly the union of the former path suffixes; it adds no
retained cache and changes no movement, collision or subjective-path rule.
`GridMap.has_any_hazards` reads tile-owned active conditions directly, while
independent spatial owners remain checked once by the existing separate loop.
It no longer resolves every area's membership through every map tile merely to
discard that result and inspect tile-owned conditions.

`SpatialSensesSystem._refresh_hazards` now calls the existing local hazard
predicate for the same newly visible or affected visible positions without a
preceding whole-map existence scan. The observer, occupancy-layer default,
spatial observations, suppression references and hidden-memory retention are
unchanged. The override audit covered base tile/item and area predicates,
spirit guardians, guardian of faith, traps and portals. Their existing filter,
perception, faction and activation rules remain at those owners. No new state
or disclosure is introduced. A full refresh on a hazard-free map now performs
local predicates per visible cell; that performance tradeoff belongs in paired
measurement, rather than being inferred from source approval.

This reviewer authored the two arithmetic changes in `dnd/core/values.py`:
`StaticValue._score` retains integer arithmetic when there are no factor
modifiers, and `ModifiableValue._score` evaluates channel factors only in the
branch that consumes them. The root and anti-slop reviewer independently
reviewed this patch. Exact `Fraction` arithmetic with factors, excluded
contributions, existing per-channel and combined constraints, final truncation,
normalization and registration semantics are unchanged. The existing value
semantics and transient-read files passed together: **24 passed in 2.33 seconds**.
This is the earlier focused execution, not a new test run during the SDK timing
lane. These native repairs add no import edges or additional system owner.

The startup repair received this reviewer's independent source review against
the preserved before-files. `initialize_audiences` reduces each audience's
initial facts once, then assigns `admitted_content` to that newly created local
`PlayerState`. Previously it repeated the same reduction solely to attach that
tuple. The reducer does not consult content while folding initialization, and
the returned admission tuple is already sorted by the same identity key. Its
descriptors remain frozen and filtered for that audience. The state has not yet
been published to `AudienceRuntime`; neither a prior state nor another audience
is mutated. Published initialization plus its existing envelope descriptors
therefore retains the same replay boundary and ownership.

`player_server.protocol.public_schema` now asks `TypeAdapter.json_schemas` to
visit the same public owners together in serialization mode. Shared definitions
come from that one generation; named roots, including the `ApiError` union,
still enter the same `oneOf`. Root-definition conflicts remain explicit. The
object-field closure, safe-integer bounds, canonical digest calculation and
existing process-lifetime cache are unchanged. There is no second protocol
model set, import-direction change or encounter-dependent schema. The existing
OpenAPI adapter copies this schema before adapting it.

The root reports exact parity with the published **312-definition schema and
digest**, plus all **5 application review tests** passing. This source review
also inspected those assertions, including complete initialization replay and
immutable content reuse. No tests or benchmarks were rerun for this supplement.
The source SHA-256 values for both startup files match
`.runtime/server-recovery/startup-owner-repair-20261007/paired-functions.json`.
That receipt contains three alternating samples on one fixed startup with 49
history entries and two seats: schema-generation median **113.13 to 59.46 ms**,
and audience-initialization median **24.82 to 21.73 ms**. Those are owner-function
samples, not latency percentiles or complete process/HTTP readiness results.
No concrete ECS, import, authority or privacy defect remains from this bounded
review; the earlier full-suite and legacy-server limits still apply.

## Spatial discovery: shared topology queries

Signed 2026-10-07 by `server_implementation_ecs`. This reviewer authored the
bounded `dnd/core/gridmap.py` and `dnd/core/aoe.py` repair; the root and anti-slop
reviewer independently approved its source invariants. Production changes stay
in those two owners and introduce no imports, protocol fields or additional
cache. This supplement does not close the remaining Gate B work.

`AoEShape._connected_positions` delegates connected reach to GridMap. The map
reuses its existing propagation-transition and cell-blocking dictionaries,
already cleared by propagation revision changes and map reset. Edge keys remain
ordered, and the cached policy remains objective propagation with no requester,
as in the old connected query. Each shape still computes reach within its own
finite geometry. The local remaining set iterates only that geometry and
removes admitted positions; it does not scan the full map for every center.
Blocking cells can receive the effect without carrying it onward, while a
blocking origin can still emit. Subjective callers still intersect the result
with admitted visibility after propagation.

The two existing boolean edge predicates avoid constructing `WorldEdgeView`
when both incident Tile-side provider sets are empty. Cardinal transition checks
still call the spatial crossing owner. Physical reach still performs its
whole-segment spatial crossing check before testing the individual sides. A
nonempty side uses the original contribution path, including subjective provider
knowledge, vertical intervals and contact rules. Endpoint existence, corner
checks and movement elevation rules remain in their existing paths. The broad
barrier-position set is deliberately not used as a cell-blocking substitute:
it includes side-boundary placements that need not make their owner cell solid.

The initial grid/world-geometry/window/cloud/fireball-breach selection reported
**91 passed**. Its two failures were an incorrect assertion about `destroy()`'s
return value in the new test, since corrected, and an existing door-contact
case. The corrected connected-query tests plus remaining-wall and selected
elevation cases reported **38 passed in 9.43 seconds**. The new tests verify
separate finite footprints across native door close/open/destroy, a reached
solid terminal surface, a solid origin, and no events emitted by these queries.
`test_window_attack_access.py::test_hand_operated_door_requires_nearby_contact[position1-True]`
also fails with both pre-change GridMap predicates and the pre-change AoEShape
traversal restored in an isolated diagnostic process (**1 failed in 2.79 seconds**).
That additional pre-existing door-contact issue remains outside this repair.

Before-files, source fingerprints, full detached choices and profiles are under
`.runtime/server-recovery/discovery-grid-owner-repair-20261007/`; the compact
comparison is `comparison.json`. Three ordinary samples and one profiled sample
ran sequentially for each existing Fireball-open and Wall-of-Fire fixture.
All **28 paired discovery results** preserve every detached field and reference
after a per-fixture UUID correspondence. Only the one-per-reactor opportunity
exposure lists require correspondence-based ordering, because the existing
native enumeration sorts fresh random UUIDs. Routes, target indices, affected
positions and every other list retain their order. All eight capture/replay
summaries also agree; this is not a claim of complete cross-run packet equality.

Native discovery medians are **66.52 to 19.54 ms** for Fireball, **208.20 to
155.83 ms** for the first Wall query, and **160.13 to 127.81 ms** for its later
expensive query. The profiled Fireball fixture's 224 discovery footprints spend
**165.11 to 19.78 ms** in connected reach; across all 228 connected queries in
that fixture, native transition calls fall **8,650 to 840**. These are counts
and owner-function measurements from a small fixture cohort, not HTTP
percentiles. No rules, targets, reactions, spatial facts or captured events were
disabled for timing. The timing lane was returned to the root for the remaining
live SDK, startup and broader acceptance measurements.

## Discovery return-value isolation

Signed 2026-10-07 by `server_implementation_ecs`. This is an independent
source-only approval of the root's two return-site changes in
`dnd/player/session.py` and the mutation-isolation extension in
`tests/game/test_player_selection_contract.py`. The anti-slop reviewer also
independently approved the change. No runtime checks or measurements were run
by this reviewer during the final sequential acceptance cohorts.

Both discovery returns rebuild `AvailableActionsResult` from the existing
detached model's Python field dump, using the same validation path that already
creates the detached cache. Nested mutable targets and containers are rebuilt;
sharing immutable UUIDs and enum values is harmless. The result retains the
same declared types without a JSON conversion. Current validation is passive:
it checks typed identities and availability consistency, while the outcome
profile's post-initializer idempotently freezes its damage-component tuple.
It does not query or register native actors, events or values.

Private execution templates, registered variants and inventory action sources
remain excluded. The retained native discovery, cached passive discovery and
caller-owned result remain separate. Cache admission still checks seat, actor,
mode, application revision and native cursor; generation/index resolution still
selects the authoritative original row and target for preview and execution.
No cache, schema, import edge or alternate authority path was added.

The expanded existing test mutates the first returned target and route, then a
cached return's target and target list. A subsequent discovery remains intact,
and execution using the modified caller handle still reaches the originally
admitted destination. This tests observable isolation and authority rather than
requiring a particular copying method. The root reports **17 selection/session
tests passing**. Its live Conjure Animals cohort reports warm HTTP discovery
p95 improving **132.66 to 98.89 ms**. The final receipt at
`.runtime/server-recovery/query-detached-final-conjure-20261007/result.json`
contains 100 unchanged warm queries, unchanged choices and state revision,
**70.96 ms median**, **291.09 ms maximum**, and **225.50 ms initial query**.
Those workload-specific results do not imply a universal latency bound or
complete Gate B acceptance; the [performance receipt](PERFORMANCE.md) retains
the complete measurement scope and remaining limits.

## Native behavior schema startup repair

Signed 2026-10-07 by `server_implementation_ecs`. Independent source and evidence
review accepts the human-approved `defer_build=True` change at `BaseAction` and
`BaseCondition`. The root authored this change. This reviewer ran no competing
tests or benchmarks and changed only this review receipt.

AST comparison against the saved before-files confirms that the change contains
only the two model configurations and the Pydantic `ConfigDict` import.
Pydantic merges inherited configuration, preserving the condition root's
`arbitrary_types_allowed=True`. Fields, defaults, validators, serialization,
registration, provider bindings and execution authority remain in their native
owners. No native import edge, alternate model, registry, loader, cache or late
import was added. Blocks, values, events, controllers and public models retain
their existing build policies. No custom schema-completion hooks require eager
completion. Final scoped source hashes match the tested source.

The exact test invocation is retained in
`.runtime/server-recovery/startup-behavior-deferral-20261007/test-command.txt`:
**212 tests pass**, including canonical public schema, malformed anchored
condition inputs, action ownership/atomicity, condition lifecycle and summon
retirement. All **17 native cases / 40 subjective views** execute, project,
serialize, decode and reduce, including Shield, Counterspell and summon control
loss. These cases share one process; they establish execution and reduction
coverage, not independent first-use timing or cross-run event equivalence.

Separate-process HTTP replay accepts **50 seat prefixes, 8,623 records and
2,150 commands**, including six terminal spell prefixes. It checks record and
command ordering, scoped identities, occurrence references, admitted content,
HUD authority and the shared reducer. The initial replay invocation accidentally
included `.log` siblings and failed on directory lookup; its retained failure
log is superseded by the successful directory-only invocation. All **25 workers
exit successfully**, and their recorded source hashes agree.

Ten fresh complete hosts per platform, without excluded samples, reduce native
Windows human-ready mean/max from **3916.65/4046.53 to 2756.77/3389.59 ms**;
WSL changes from **6273.47/6758.88 to 4995.88/5514.48 ms**. SDK-consumed means
are **2863.46 ms** and **5184.32 ms**, respectively. The ordinary 1,000-command
HTTP run measures consumed **37.50 ms p95 / 56.91 ms maximum**. Its separate
GC census confirms an empty native world before freeze, enabled GC with unchanged
`[2000, 10, 10]` thresholds, collectible post-Start cycles, and flat registries
of **535 objects / 2,000 values**. Frozen objects are stable from after Start;
newly compiled schemas remain subject to runtime GC. The observed natural
generation-2 collection takes **31.26 ms**, with no uncollectable objects.

The three first-spell HTTP fights reach terminal state in **70 commands /
215 records**. First selected Fireball, Wall of Fire and Conjure Animals commands
take **490.56, 101.72 and 93.69 ms** through consumption; discovery and preview
are measured separately. These values remain explicit residual costs. The
evidence supports this bounded startup repair without hiding first-use or GC
work; it does not establish universal latency, complete Gate B acceptance, or a
solution for the separate host passive-type dependency. Full measurements and
limitations remain in [PERFORMANCE.md](PERFORMANCE.md), backed by `summary.json`,
`http-replay.json` and the raw receipts in the directory above.

## Final §15 acceptance — native lifecycle and service ownership

October 7, 2026. Recorded by the implementation owner from the independent
`server_implementation_ecs` review: **accepted; no remaining ECS/DAG or native
ownership blocker**. The reviewer inspected source and final evidence without
running additional measurements or making implementation changes.

One exclusive native worker per active game preserves the engine's ownership.
Retirement uses existing native reset and AI cache owners, with epoch-acknowledged
cleanup before reuse. The service owns credentials, Hosts and recording budgets;
it does not acquire gameplay rules. The shared application invokes the existing
action dispatcher. No parallel action executor, public schema family or renderer
was introduced.

Both platforms reuse one worker across 16 games and shut down cleanly. Real-worker
checks cover cancellation, failed starts, retained recordings and retirement;
real summon/AI weak-reference checks cover native world collectibility. Recorded
source fingerprints match. Cold replay passes 62 prefixes, 747 records and 191
commands. The Python evidence contains 147 distinct passing checks across the
main cohort and corrected allowlist retest; TypeScript has 24 passes, with zero
scoped Pyright errors.

Ordinary warm readiness averages **217.77 ms Windows / 208.27 ms WSL**, excluding
host imports. Memory evidence correctly separates settled ordinary-game usage
from retained first-use content growth and excludes the Windows launcher sample.
This supports closing the approved server functionality and beginning separately
scoped client work, without asserting universal performance bounds. Detailed
scope and evidence are in [WARM_WORKERS.md](WARM_WORKERS.md).
