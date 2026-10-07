# Server implementation: bounded anti-slop review and repair receipt

Date: 2026-10-07. Scope: the authorized server implementation and measured capture
history cost in the [implementation plan](../../SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md)
and [stream contract](../../SERVER_STREAM_AND_SDK_CONTRACT_2026-10-07.md).
This records reviewed boundaries and concrete tests; overall encounter, SDK,
startup-cohort and retention acceptance belong to the implementation receipt.

## Source ownership and resolved findings

- The common native application owns capture and reduction. HTTP handlers submit
  finite native requests; they do not reconstruct legality, game effects or private
  actor data. Direct item snapshots already contain their authored information;
  the proposed extra item/feature metadata registry was dropped.
- Command reservation distinguishes an authorized stale/out-of-turn command's
  durable rejection from a foreign actor's forbidden request. Identity headers
  and strict JSON selection coordinates are checked before native admission.
- An SSE send that overlaps the final publication drains through the current
  final cursor. Failed startup returns a non-retryable game failure. Missing
  committed history and expired retention return explicit resume-unavailable
  responses instead of treating them as a game still starting.
- Terminal native workers close while their exact public prefix remains available
  for the specified retention interval. Expiry removes the owned spool and keeps
  final status/cursor. Queued queries receive a typed closed response during
  shutdown; interrupted accepted mutation receipts remain indeterminate.
- One per-game delivery byte owner accounts for the immutable public catalog,
  active spool chunks and retained query output. Query response credit survives
  a slow socket and is released on completion/cancellation. Excess query work
  receives the existing finite busy response without blocking the native owner.
- Canceled parent capture now retains its normalized child-lineage header.
  Original version rows, actor admission evidence and native event objects remain
  unchanged. The completed child survives a retained branch traversal.

## Measured capture repair

Before repair, every `capture_context()` rebuilt full-history dictionaries and
each lineage's actor admission reconstructed the entire event prefix. The paired
profile attributed the growth to those scans while native end-turn work stayed
approximately constant.

`CaptureContext` now stores only generation and end cursor. Selected lineage
versions come from `EventQueue`'s existing lineage and UUID indexes. The native
queue additionally owns one UUID-to-append-index map; its ordinary reset and the
cold-pack runtime inventory include that map. No per-boundary full-history index
is retained by capture.

Each existing `AudienceRuntime` owns one `CaptureCheckpoint`: recorded actor
after-values, that audience's contacts/observer positions, generation and cursor.
The same admission fold serves cold and resumed capture. Forward captures read
new event suffixes. Older or overlapping reads, a changed audience, and generation
changes clear the checkpoint and reconstruct from original events. A terminal
native owner release drops its private actor/contact state while the existing
public reducer retains already admitted identity. Temporary loss of sight or
world presence does not discard state needed for a later native re-entry.

The checkpoint is current reconstruction state, not a second event journal and
not a copy of latest public state used to guess earlier observations. It remains
bounded by the actors whose native lifetime has not ended and the current
audience's contacts. Native history and its new index still grow with recorded
events. At 10,010 entries the new index measured **575,272 bytes**: 294,992 bytes
for the dictionary and 280,280 bytes for integer values. UUID objects are shared
with existing indexes. This is an explicit retained-history cost, not a claim of
constant total engine memory.

## Paired history evidence

The same `devtools.player_server_acceptance.performance history` probe used
ordinary native end-turn/advance work with capture enabled. Sources were read
under WSL from `/mnt/c`; the environment and source hashes are in each result.
These are individual profiled end-turn samples, not latency percentiles. The
baseline was contended, and the fixed run also includes native timing hooks.

| Audience configuration | Events before command | Baseline dispatch | Fixed dispatch |
|---|---:|---:|---:|
| Two grouped seats | 106 | 18.48 ms | 19.01 ms |
| Two grouped seats | 10,006 | 105.67 ms | 21.95 ms |
| One seat per entity | 106 | 28.54 ms | 27.46 ms |
| One seat per entity | 10,006 | 1,170.84 ms | 33.13 ms |

The grouped endpoints both emit four new native events, two public roots and two
records (about 13 KiB). The per-entity endpoints both emit four events, four roots
and four records (about 21 KiB). The per-entity baseline's 1,170.84 ms sample was
dominated by time charged to context construction and may include allocator/GC
delay; it must not be presented as a typical cost or a reliable speedup ratio.
The fixed grouped native cost is 5.59/5.36 ms at the two history endpoints; capture
is 13.07/16.33 ms. Full-history context/admission scans disappear from the dominant
call tree. Remaining measured work includes content admission and boundary
projection; this patch does not optimize those separate owners.

Artifacts: `.runtime/server-recovery/history-grouped-20261007/result.json`,
`history-grouped-fixed-20261007/result.json`,
`history-per-entity-20261007/result.json`, and
`history-per-entity-fixed-20261007/result.json`, with their saved profiles.

## Focused validation

Environment: `UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv`,
`uv run --no-sync python -m pytest`. Checks were limited to changed boundaries.

- Delivery/transport review: **16 passed, 21.85 s**, including actual native
  queries with held/canceled ASGI sends, startup failure, authentication, missing
  history, expiry, shutdown, receipts and final SSE publication.
- Capture/application/archive selection: **13 passed, 8.55 s**. Hot and cold
  capture compare original retained values, encoded public packets and reduced
  state through hidden discovery, later damage in the same operation, native
  condition/equipment changes, loss/reacquisition, death, retirement, historical
  recapture and generation reset. The selection also includes the canceled-child
  regression, original device/door/web archives and witnessed doorway death.
- Native append-order and reset checks: **2 passed** in the index integration
  selection.
- A minimal external cold pack that constructs a native event is rejected, and
  rollback removes both the event and its position index: **1 passed, 1.51 s**.

The old manual cold-loader registry tests were not counted as passing evidence:
two access removed `Entity._entity_by_position` before invoking the loader, and
one assumes an empty registry after a preceding test explicitly preserves native
objects. Those unrelated legacy fixtures were left unchanged. A separate minimal
cold-pack rollback regression covers the new event-position index directly.

The performance patch was implemented by this reviewer. The independent ECS
review approved the final index/checkpoint/retirement/canceled-lineage ownership;
its separate selection passed **4 tests in 10.15 s**. See [ECS_REVIEW.md](ECS_REVIEW.md).
These targeted checks do not establish complete gameplay acceptance.

## Allocation follow-up review

The bounded follow-up preserves existing owners and is approved by source review:

- `admitted_content` reuses the existing player state's immutable descriptor
  tuple when nothing is newly disclosed. Only newly admitted descriptors have
  related references filtered to public content. Descriptors and their nested
  presentation, ordering and reference values are frozen; the native catalog
  remains unchanged. The reducer skips catalog reconstruction for an empty
  addition list and still rejects a changed definition under an admitted
  identity. This adds no cache or parallel registry.
- The new `use_register=False` option reaches newly created combined value
  roots, all primary/imported channels and generated base modifiers. Defaults
  stay registered. Only audited scalar HP, passive-skill, equipment scoring and
  snapshot AC readers opt out. Calculation, normalization, bounds, contextual
  evaluation and advantage handling remain the same. Shared owned modifiers
  are not unregistered; target/context assignment operates on newly combined
  channels. The AC base-delta constructor has the same fields/defaults as the
  previous factory. These value changes introduce no registry cleanup sweep
  or GC setting; the later process-entry policy is reviewed separately below.
- The public occurrence map has one writer, which inserts a new mapping with
  the next strictly increasing audience-local occurrence number. It is not
  reordered or pruned. Therefore the first reversed entry below a native cursor
  gives the same maximum as the former full scan, including later disclosure
  of an older native occurrence. Historical queries retain the exact fallback
  scan and no new index is added.

The native patch author's six focused regressions passed. The root reports 49
existing value/equipment regressions and five boundary-file tests passing; the
boundary cases include empty maps and late disclosure of older native events.
This review inspected those changes without running concurrent benchmark work.

The independently authored
`test_content_reuse_preserves_private_links_and_prior_player_states` in
`tests/player/test_application_review.py` covers serialized admission, private
link filtering, no-addition reuse, subsequent admission, unchanged source/prior
state and conflicting-definition rejection. The root's final **83-test**
player/HUD/party/resolution selection passed, including this regression. The
allocation changes' latency and retention effects are reserved for the separate
measured performance receipt; source review does not establish those results.

## Transient turn values and process-lifetime GC policy

The final six-line native ownership change is approved. `TurnContext` and
`AdvanceResult` now default to `use_register=False`; explicit registration is
still available. Their current and legacy consumers pass them directly as
transient values, without UUID lookup, contribution ownership or retirement.
Controllers, combatants, encounters and retained events keep their existing
registration. The two new regressions exercise automated-to-human advancement,
repeated stable waits/context output, original event retention, owned lookup and
explicit registration. The author reports those two and two existing encounter
API tests passing: **4 passed in 2.27 s**. This reviewer inspected the source and
tests without running competing runtime work.

The subsequent GC change is an explicit production policy change, superseding
the earlier statement that no GC policy would change. The fresh single-game
worker entry `run_process()` rejects installed content or pre-existing native
events, warms the process-lifetime protocol identity, runs a full collection,
freezes the surviving import graph, then enters the normal packet loop. Reusable
`start()`, `dispatch()` and `main()` do not freeze objects. Normal GC remains
enabled with unchanged thresholds for later native/session allocations.

This source boundary is approved with its stated tradeoff. Python freezes every
currently tracked object, including mutable import objects, rather than only
immutable schemas. Pre-existing cycles orphaned later may therefore survive
until the single-game worker exits. This does not repair a live-object leak or
prove a universal command-latency bound. Native history continues growing and
remains subject to normal collection. See the
[Python GC contract](https://docs.python.org/3.13/library/gc.html#gc.freeze).

The final measurement wrapper delegates to the exact production
`worker.run_process()` entry. Its timing wrappers call the original identity,
collection and freeze functions, then restore them before the packet loop; it
adds no alternative collection policy. Separate fields report protocol warming,
pre-Start collection, instrumentation cost, frozen counts, ordinary collection
activity, allocated blocks and RSS. A labelled diagnostic creates a new cyclic
object after Start and requests generation-0 collection to verify reclamation;
this instrumentation cohort is explicitly excluded from plain latency samples.
Wrapper parity is approved by source review.

Post-freeze `gc.get_objects()` excludes the frozen generation, so lower tracked
counts alone are not evidence of lower memory usage. Startup measurements must
include protocol warming and collection.

Final saved evidence was inspected without running another test or benchmark.
The uninstrumented `http-long-process-policy-20261007/result.json` contains
**1,000 commands**, 500 per seat, with consumed-cursor **p95 62.45 ms**, **p99
73.64 ms**, and **maximum 109.08 ms**. Both seats consumed 2,002 records through
cursor 2,001. Its host receipt records native command maximum **52.43 ms** and
worker exit code zero. Every shared source hash matches the separate
`http-long-process-policy-profile-20261007/worker-profile.json` cohort.

The instrumentation confirms zero registered native objects/values and event
cursor zero before freezing; the newly allocated post-Start cycle is reclaimed.
GC stays enabled and thresholds remain `(2000, 10, 10)`. From Start through
1,000 commands, value registrations remain **2,000**, object registrations remain
**535**, and the post-Start frozen count remains **459,464**. Ordinary runtime
generation-2 collection still executes, taking **43.57 ms** in the recorded
sample and reclaiming 776 objects. This demonstrates that runtime cyclic
collection remains active.

The policy does not eliminate retained-history memory growth: history advances
from **49 to 9,299 events**, and RSS rises from **316.57 MB to 375.55 MB** in the
instrumented process. Measured pre-Start collection costs **209.37 ms** and
protocol warming costs **120.63 ms**; the separately identified pre-freeze
census adds **177.86 ms** only in instrumentation. These are distinct from
ordinary command latency. The bounded ownership/GC evidence is approved; it
does not establish constant total memory or a universal maximum latency.
Cold-replay completion is recorded separately by the SDK acceptance reviewer.

## Continued Gate B owner review

The resumed investigation has bounded independent source approval for the
following repairs; this does not declare the full performance plan complete.

- `Entity.materialize_navigation` tests each distinct cell from the already
  audience-filtered route suffixes once. It retains the same observer UUID,
  excludes route origins as before, and uses the same native hazard predicate.
  The result is existential, so removing duplicate queries and changing their
  order preserves it. Safe-route construction, hidden-hazard perception,
  faction and occupancy-layer rules remain with their original owners. The
  call-local set adds no persistent cache or invalidation scheme.
- `GridMap.has_any_hazards` inspects tile-owned active conditions directly.
  Its former `get_tiles_with_conditions()` filter first assembled each tile's
  combined conditions, including independent spatial owners, only for the caller
  to inspect `tile.active_conditions` again. Direct tile iteration preserves
  that predicate; placed objects and independent spatial owners are still
  checked separately, each in the existing path.
- `SpatialSensesSystem._refresh_hazards` no longer scans the whole map before
  querying the cells whose hazard facts need refresh. It still limits those
  queries to newly visible or affected visible cells, removes facts outside
  current visibility, and invokes the authoritative observer-specific native
  predicate. It does not reuse private map state or weaken hazard disclosure.
- The ECS-authored value changes skip multiplying a static channel by an empty
  factor product and construct combined-channel factors only in the branch
  that uses them. The omitted product is exactly one; the unused tuple has no
  effect on the other branch. Bounds, normalization, exclusion, incoming
  channels and existing factor evaluation are unchanged. No native subclass
  override of `arithmetic_factor` was found in the source review.

The root reports **64 native hazard tests** and **24 value tests** passing.
This reviewer did not rerun them during the SDK timing slot. Paired native and
actual HTTP measurements belong to the performance receipt; source equivalence
alone does not establish their timing results.

This reviewer separately authored two small startup repairs in
`dnd/player/application.py` and `player_server/protocol.py`: attach admitted
immutable content to the once-reduced initialization, and generate the existing
public roots' shared schema definitions in one Pydantic pass. Those authored
changes are **not counted as independent approval by this reviewer**. The root
has reviewed the source; a further ECS review is in progress.

Five application regressions pass, including cold initialization equality and
content privacy. A focused schema regression passes against the actual published
`sdk/protocol/player-api-v1.schema.json`: all **312 definitions**, canonical JSON
and digest `0b99402cf980671394c96bb2afb9b7afd74cbfaeddb66f6367ac31f78b325cf7`
are unchanged. No SDK or schema files were regenerated. The test initially
referenced the obsolete planning overlay, failed, and was corrected to the
production export; no production expectation was changed to obtain the pass.

Three alternating paired owner-function samples on one fixed two-seat startup
show schema preparation median **113.13 → 59.46 ms** and audience initialization
median **24.82 → 21.73 ms**. Initializations and latest states compare equal and
native event cursor 49 remains unchanged. These small samples are function-cost
observations, not startup percentiles or whole HTTP readiness. Source copies,
fingerprints and samples are under
`.runtime/server-recovery/startup-owner-repair-20261007/`.

At this checkpoint the actual HTTP combat cohort and ten whole HTTP startup
measurements remain running or pending. The older direct-worker startup probes
bypass `run_process()` and omit HTTP-host/pipe-launch stages; listener readiness
also precedes native readiness. They cannot close the original full-startup
acceptance requirement. Broader command/scaling and retained-memory dispositions
must likewise follow the actual final-source evidence rather than the earlier
End Turn-only result.

### HTTP startup attribution and finite-combat probe source review

The first zero-command HTTP smoke's roughly 7.72-second marker was explicitly
SDK consumption, including the separate client process, connection, attachment,
schema validation, recording and acknowledgement. Its roughly 1.72-second
listener marker was not native readiness. Neither value isolates the host's
first committed human-input publication. Older native import measurements
also exclude the current host and production process prelude; they cannot be
subtracted from this smoke to claim a corrected startup result.

This reviewer authored a bounded probe repair: `test_host.py` now timestamps
the existing publication-condition notification only after every seat has an
initial publication and one seat has a legal waiting-for-human boundary.
`http_run.py` reports this separately from SDK-consumed readiness. The SDK probe
retains its initial connection while polling scope-validated status and uses
the current attachment epoch; it explicitly waits for the first human boundary
even with zero commands. These are acceptance-harness changes, not a production
startup optimization. Functional smoke and the ten-run same-fixture cohorts
remain pending at this checkpoint; this author's changes need independent
review rather than being counted as independently approved here.

The source pass found `public_schema()` and `protocol_identity()` cached once
per process and a single content bootstrap during `Start`. The worker eagerly
imports native content declarations needed by that bootstrap. The host still
imports executable native definitions through the existing query DTOs in
`dnd/core/base_actions.py`; a passive-owner extraction could reduce that closure,
but its actual benefit has not been measured and no additional owner split is
approved by this review. Native process isolation and the current import DAG
remain intact.

The finite-combat probe selects ordinary offered SDK actions and targets,
completes selections through native previews, and uses authored creature HP
and ordinary initial grants. It reports discovery/preview separately from
submit-to-consumption latency, rejects a fight that exceeds its command budget,
and requires the requested action to have been exercised. This supports the
bounded eight-case functional workload, not 100 samples of each spell, native
AI percentiles, largest-map scaling or long-lived spatial effects. Cold replay
currently reports final terminal state; the live client is the owner asserting
terminal completion. The replay assertion/report distinction was sent to its
author for a bounded correction. No additional runtime checks were run during
the other reviewer's measurement slot.

### Connected topology and Python SDK validation review

Compared `dnd/core/gridmap.py` and `dnd/core/aoe.py` with their exact saved
pre-repair sources under
`.runtime/server-recovery/discovery-grid-owner-repair-20261007/`. The bounded
changes have independent source approval:

- Connected propagation retains cardinal adjacency, its supplied geometric
  footprint, missing-tile exclusion, inclusion of a solid terminal surface,
  and emission from a solid origin. It reuses the map's existing objective
  blocking/transition caches with exactly their existing predicates and keys.
  Propagation-revision changes and map reset already clear both caches;
  placed-object, boundary and independent spatial-condition owners retain
  that invalidation. No observer-filtered result enters these caches and no
  additional history or persistent footprint cache was introduced.
- The empty-boundary fast paths consult the same tile-side membership that
  builds edge contributions. No members means no contributions to evaluate.
  Cardinal channel queries still call `spatial_crossing_allows` with the same
  requester, movement mode and subjective flag. Straight physical reach still
  performs its spatial-crossing check before the side loop, and populated
  boundaries keep their existing height, terminal-provider and knowledge rules.

The focused new topology tests inspect actual footprint membership across door
open/close/destruction and solid-cell cases without changing native history.
They were read, not rerun by this reviewer during the author's paired timing
slot. Native parity results remain the author's separately recorded evidence.

The Python SDK's `jsonschema-rs` replacement also has independent source
approval. It compiles the unchanged packaged Draft 2020-12 schema, retains one
validator per requested root, explicitly enables formats and rejects unknown
format definitions. Incoming records retain bounded strict UTF-8 JSON parsing,
non-finite rejection and the special initialization/operation cursor checks.
The public Python-value validation path first checks JSON serializability with
`allow_nan=False`, preventing the compiled binding's non-finite-to-null
conversion; parsed incoming records avoid that unnecessary second encoding.
Successful validation returns the original value and adds no fields or defaults.
The new dependency and native-wheel/source-build requirement are documented;
no generated schema, SDK type declarations or gameplay rules were replaced.

The SDK author reports **42 tests passing**. This reviewer read the strict
extras, UUID formats, union tags, coordinate tuples, booleans, safe counters,
non-finite values and nullable-value/non-mutation cases but did not rerun them
during native measurement. The measured 2.61 MB choices response motivates the
validator change; source approval does not turn five validator samples into an
HTTP percentile or close remaining Gate B workloads.

The root independently approved this reviewer's three startup-harness changes.
Their functional smoke remains pending. Final host receipts now fingerprint
`dnd/core/aoe.py`, `dnd/player/session.py`, the Python SDK transport and its
dependency file in addition to the previously recorded owners.

### Discovery-result detachment follow-up

Independently approved the two return-site replacements in
`discover_player_actions`: reconstruct `AvailableActionsResult` from the
existing detached model's field dump instead of Python deep-copying that
model. This is the same detachment mechanism already used when creating the
cache, without JSON encoding, a new cache or a second DTO. Typed nested models,
targets and mutable lists are rebuilt. Immutable UUID/enum values may safely
be shared. The existing validators check field consistency; the outcome-profile
post-initializer only freezes its damage-component tuple and is idempotent.

The retained native result remains separate. Excluded cost callbacks and
private execution templates, inventory action sources and registered variants
cannot enter the returned field dump. Command execution still resolves the
original row and target after checking runtime, generation and indices.
The expanded existing selection-contract test mutates both first and cached
discovery targets/list contents, verifies a later discovery remains intact,
and executes the original admitted target despite modified caller data. This
is meaningful isolation coverage rather than a copy-method assertion. The
test was source-reviewed; no runtime test or benchmark was run by this reviewer.

The startup publication timestamp was also rechecked against the host owner:
`commit_records` and the full seat-publication assignment precede the existing
condition notification. SDK-consumed readiness remains a separate field. This
recheck does not count as independent approval of this reviewer's own harness;
the root's earlier independent source approval remains the recorded review.

### Narrow behavior-schema deferral: source and semantic evidence

Independently reviewed the exact production delta recorded in
`.runtime/server-recovery/startup-behavior-deferral-20261007/scoped.patch`.
Only `BaseAction` and `BaseCondition` add Pydantic's supported
`defer_build=True`. The action root retains its explicit
`arbitrary_types_allowed=True`; the condition root retains that setting through
Pydantic's existing base-configuration merge. Fields, defaults, validators,
serializers, native registration hooks, catalog imports and behavior identities
are unchanged. BaseObject, block, value, event and public-model policies remain
outside this delta. The installed Pydantic owner establishes model fields before
the deferral branch, preserving the catalog's existing lifecycle-default reads.
No eager-completion hook or private validator lookup in the affected native
owners was found that requires a further repair.

The recorded command in `test-command.txt` and `tests.log` establish **212
passing tests**. The selection includes malformed missing/null condition anchors,
exact Counterspell action/handler provider bindings and spending, prepared and
canceled condition ownership, summon retirement, shared application/cold
reduction and an exact comparison with the published public schema and digest.
The separate 17-case native receipt adds successful ordinary execution,
projection, encoding, decoding and shared reduction across melee, ranged,
reactions, multi-target spells, areas, walls and summons. Those cases run in one
fresh process; they are not 17 independent cold first uses or an exact comparison
against an eager-policy baseline. This reviewer inspected sources and receipts
without running competing tests or measurements.

Source and this bounded semantic evidence are approved without a blocker.
Final implementation acceptance remains pending the complete first-use HTTP,
natural-GC and fresh-host receipts. Section 11.3 still requires ten starts per
configuration; the author will extend the current five-per-platform cohort to
ten. Deferred schemas can enter the ordinary post-Start GC graph, so import
speed and the earlier eager-policy GC receipt do not establish the new policy's
runtime latency or memory behavior. Overall Gate B completion is not asserted.

### Final §14 evidence acceptance — October 7

**Verdict: retain the narrow BaseAction/BaseCondition deferral.** The completed
`startup-behavior-deferral-20261007/summary.json`, individual host receipts,
`gc-1000/worker-profile.json` and `http-replay.json` close the pending evidence
above. This reviewer independently recomputed the startup means and ranges from
all ten records per platform, checked all 25 worker exit codes and matching
host-recorded source fingerprints, and verified that the separately recorded
two-root source hashes still match the reviewed files. No samples were excluded.

| Fresh host, normal filesystem caches | Human-ready mean | Human-ready maximum | SDK-consumed mean |
| --- | ---: | ---: | ---: |
| Native Windows, 10 starts | 2756.77 ms | 3389.59 ms | 2863.46 ms |
| WSL, 10 starts | 4995.88 ms | 5514.48 ms | 5184.32 ms |

The corresponding prior human-ready means were 3916.65 and 6273.47 ms.
Listener, published human boundary and SDK consumption remain separate. WSL's
maximum still exceeds five seconds; this evidence establishes the first bounded
startup improvement, not universal budget attainment or cold-disk performance.

The ordinary 1,000-command run has consumed p95/max **37.50/56.91 ms**. The
separate instrumentation run retains enabled GC and unchanged thresholds,
empty native registries/event history before freezing, and a reclaimed post-Start
cycle. Object/value registries remain **535/2000**; the observed natural runtime
generation-2 collection takes **31.26 ms**. Frozen objects remain 334488 after
Start while retained events grow 49→9299 and RSS grows 188.25→245.66 MB. Deferred
first-use schemas remain ordinary runtime allocations; no live-world freeze or
new GC policy was introduced by this patch.

All three spell fights finish, totaling 70 commands and 215 records. First
selected Fireball/Wall of Fire/Conjure Animals consumption is
490.56/101.72/93.69 ms, with discovery and preview reported separately.
The matching eager-policy observations were 483.40/97.61/79.68 ms. These are
single observations, including small possible first-use costs, rather than spell
percentiles; they do not outweigh the measured startup saving. Separate-process
cold replay passes **50 prefixes, 8623 records and 2150 commands**, including all
six terminal spell-seat prefixes. The initial incorrect CLI file glob is retained
as a distinct failed harness attempt, not counted as successful replay evidence.

Signed: local anti-slop reviewer, October 7, 2026. No additional tests or timed
processes were run by this reviewer. Approval closes the reviewed §14 first
solution only; broader engine-performance acceptance remains open.

### Final §15 acceptance — warm worker reuse

October 7, 2026. Recorded by the implementation owner from the independent
`server_implementation_antislop` review: **accepted, no remaining blocker**.
The reviewer approved the bounded source after the lifecycle corrections and
independently checked the final evidence; it did not rerun tests or benchmarks.

The reviewer recomputed the ten warm-game means per platform, checked all 32
game rows, one worker PID per platform, zero owned workers after shutdown, and
all 20 recorded production fingerprints per platform against current source.
Separate cold replay accepts 62 audience prefixes, 747 records and 191 commands,
with terminal expectations matching. The final Python cohort has 146 passes,
followed by the corrected exact dispatcher-consumer assertion passing separately:
147 distinct checks. TypeScript has 24 passes; scoped Pyright has zero errors.

Warm ordinary readiness averages **217.77 ms Windows / 208.27 ms WSL**; separate
retirement averages **32.38 / 30.92 ms**. These readiness figures exclude host
imports/configuration and must not replace §14's full cold-host figures. Windows
RSS measured the launcher, not the interpreter, and is excluded. WSL ordinary
retirement RSS settles, while first use of additional content grows retained
allocations; constant memory across all content is not claimed.

This closes the bounded §15 server reuse work and supports beginning separately
scoped client development. It does not close all engine-performance targets.
See [the closure receipt](WARM_WORKERS.md) for source changes and raw evidence.
