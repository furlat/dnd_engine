# Server performance evidence — 2026-10-07

**Latest cross-game result:** [warm-worker receipt](WARM_WORKERS.md#final-measurements)
reports ten warm ordinary starts per platform at 217.77 ms Windows / 208.27 ms WSL,
plus 32.38 / 30.92 ms native retirement. These reuse loaded processes and exclude
host imports; do not compare them to full cold-service startup as identical measures.
Broader E01–E14/Gate B limits below remain explicit.

The historical eager-policy uninstrumented WSL HTTP/SSE End Turn run completes **1,000 ordinary End Turn commands, 500 per seat**, including the native turn/round advancement after each command. Command-to-consumed-cursor latency is **62.45 ms at p95, 73.64 ms at p99, and 109.08 ms maximum**, compared with 335.88 ms maximum in the preceding 1,000-command run. Each seat consumes 2,002 schema-validated records through cursor 2,001. Health/status p95 stays near 7.2 ms. These are End Turn measurements, not spell or movement latency distributions.

The native owner repairs remove retained scalar-read temporaries and passive turn-result registration. The production worker now collects and freezes its pre-game import graph before accepting Start; runtime GC remains enabled for new gameplay objects. This is an explicit process-lifetime policy change with a startup and memory-retention tradeoff, described below. The final instrumented run keeps both native registries flat through 1,000 commands and records a 43.57 ms runtime generation-2 collection, down from 307.86 ms in the preceding callback cohort.

The earlier capture repair removes repeated full-history scans. A matched grouped-seat end turn changes from 105.67 ms to 21.95 ms at 10,006 retained events under cProfile. The complete startup and cross-environment follow-up below supersedes the earlier worker-only startup scope and failed default-bind connection attempts.

## Approved first startup fix — behavior schema deferral

The user accepted the bounded first solution in plan §14. Production now sets
Pydantic `defer_build=True` on the existing **BaseAction and BaseCondition**
configurations. All other native/public model policies, static imports, fields,
validators, serializers, registration hooks and content admission remain unchanged.
The library compiles each deferred schema when needed and retains it normally;
there is no new loader, schema registry, warming scheduler or serialization path.
Inherited `arbitrary_types_allowed` remains intact for both roots.

### Complete fresh-host results

Ten sequential fresh processes per platform use the same four-goblin/two-seat
fixture as the ten-sample eager baseline. Timing starts at host process spawn;
fixture configuration construction and dependency installation are excluded.
Human-ready includes worker launch/imports, the existing pre-Start GC policy,
encounter initialization, advancement, encoding, transfer and publication commit.
SDK readiness additionally includes process startup, attachment, validation,
consumption and acknowledgement of both seats. Normal filesystem caches were not
flushed. No competing test/benchmark workload was run; no outliers were discarded.

| Platform | Human-ready mean, before → after | After range | SDK consumed mean, before → after | After SDK maximum | After listener mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native Windows | 3916.65 → **2756.77** ms | 2649.23–3389.59 ms | 4027.01 → **2863.46** ms | 3492.63 ms | 875.04 ms |
| WSL, mounted checkout | 6273.47 → **4995.88** ms | 4706.61–5514.48 ms | 6468.40 → **5184.32** ms | 5701.71 ms | 1275.85 ms |

These are means/ranges from ten observations, not percentiles or cold-disk claims.
The preliminary five-sample commentary is superseded by these complete values.
Native Windows saves about **1.16 seconds** at human readiness; WSL saves about
**1.28 seconds**. WSL still exceeds five seconds in some starts, and even its mean
SDK-consumed boundary is above five seconds. This closes the approved first fix,
not a universal startup target or the outstanding larger-map/native-AI work.

### First-use cost remains visible

Each row below is the first selected spell in a fresh real HTTP fight, compared
with the earlier `combat-after-spatial-20261007` cohort. Discovery and preview are
outside the command timer. Worker time includes native execution/capture/public
construction; SDK consumption includes transport and validation. All values are
milliseconds. These are single observations per spell, so small differences are
possible first-use costs, not an isolated causal attribution or a distribution.

| Spell | Discovery through SDK, before → after | Preview after | Command consumed, before → after | Worker command, before → after |
| --- | ---: | ---: | ---: | ---: |
| Fireball, six goblins | 105.70 → 105.29 | 8.68 | 483.40 → 490.56 | 438.91 → 448.21 |
| Wall of Fire | 242.99 → 248.54 | 28.25 | 97.61 → 101.72 | 70.38 → 79.40 |
| Conjure Animals | 206.20 → 219.19 | 10.90 | 79.68 → 93.69 | 55.62 → 67.01 |

The three fights reach terminal state with **70 commands and 215 records**.
The observed 4–14 ms command increases do not erase the approximately 1.2-second
small-fixture startup saving. Fireball's roughly 448 ms native worker command and
large discovery queries remain real costs; deferring schemas does not solve them.
The earlier disposable policy experiment separately measured about 31 ms more
encounter Start work. That diagnostic observation is not substituted for these
complete production startup/first-command measurements.

### Long-run GC and semantic evidence

The ordinary, uninstrumented WSL run completes **1,000 End Turn commands**, 500 per
seat, and **4,004 records**. Command-to-consumed-cursor latency is **37.50 ms p95,
39.04 ms p99 and 56.91 ms maximum**. Worker command p95/max is 5.68/8.31 ms;
following automatic advancement p95/max is 7.40/36.55 ms. The earlier eager cohort
reported consumed p95/max 62.45/109.08 ms. This demonstrates no regression in the
measured workload; it does not establish that schema deferral alone explains the
entire difference or bound spell/AI/movement latency.

A separate instrumented 1,000-command run retains the exact production worker
policy. GC remains enabled, thresholds stay `[2000, 10, 10]`, and the post-Start
weak-reference cycle probe is reclaimed. Before freeze, the event cursor and both
native registries are zero: no live encounter is frozen. After Start through
1,000 commands, registered objects stay **535**, values **2,000**, and the frozen
object count stays **334,488**. Schema completion reduces the earlier pre-Start
frozen count from 334,736; stability is claimed only from after Start. One natural
runtime generation-2 collection takes **31.26 ms** and collects 835 objects with
zero uncollectable objects. The separate import/pre-Start collection takes 117.81
ms and is not presented as a runtime pause. Census/cycle instrumentation is excluded
from the ordinary latency distribution.

Recorded history grows from 49 to 9,299 events and RSS from **188.25 to 245.66 MB**
(decimal). This preserves the existing history-retention cost; flat transient
registries do not mean constant total memory.

- **212 existing tests pass** in 52.84 s: all `tests/player`, plus content recovery
  semantics, anchored-condition inputs, condition lifecycle/preparation, action
  template ownership/cost atomicity, summoning lifecycle and retirement ownership.
  Exact command is retained in `test-command.txt`. Coverage includes malformed
  condition validation, Counterspell provider bindings, cancellation/cleanup,
  capture/replay and exact equality with the published public schema/digest.
- **17 existing native scenarios / 40 subjective views** complete execution,
  projection, JSON encoding/decoding and the shared reducer: reactions, repeated
  attacks/projectiles, Fireball, walls, repeated Call Lightning, conditions and
  summon control loss. These run in one fresh process and are not claimed as 17
  independently cold first uses or an eager/deferred state-equality assertion.
- **25 real owned hosts/workers** exit successfully: 20 startup cohorts, two long
  runs and three spell fights. A separate process replays all **50 subjective
  prefixes, 8,623 records and 2,150 own commands**, checking strict schema, scopes,
  cursor/command order, causal closure, private inventory/HUD and terminal spell
  outcomes. No native world is rerun by replay.
- Public schema remains **19 roots / 312 definitions / 1,612 fields**, digest
  `0b99402cf980671394c96bb2afb9b7afd74cbfaeddb66f6367ac31f78b325cf7`.
  No SDK generation or package changes were needed.

Evidence lives under
`.runtime/server-recovery/startup-behavior-deferral-20261007/`: `scoped.patch`,
pre-edit source snapshots, `source-before-checks.json`, `test-command.txt`, test/native
case receipts, per-host records, `summary.json` and `http-replay.json`. All 25 host
source inventories agree; the additional top-level fingerprint explicitly covers
both changed roots and is verified unchanged after acceptance. The first replay
CLI glob mistakenly included sibling `.log` files; its `NotADirectoryError` log
is preserved as a superseded harness invocation. The corrected directory-only
invocation completes all 50 prefixes. No unsuccessful invocation is counted as a
pass. Independent final verdicts belong to [anti-slop](ANTISLOP_REVIEW.md) and
[ECS/DAG](ECS_REVIEW.md), scoped to this two-owner change and its measurements.

## Follow-up: spatial work, real combat and SDK latency

This follow-up is required by the human's request to continue beyond End Turn and inspect spatial spell checks. It changes existing owners, with no protocol regeneration, alternate rules, new convolution library or frontend work. Native geometry still obeys directional doors, walls, terminal surfaces and spatial barriers; observer filtering remains separate. A geometric kernel alone would not preserve those directional/topological rules.

| Measured boundary | Before | After | Evidence scope |
| --- | ---: | ---: | --- |
| Warm full navigation p95 | 5.33 ms | 1.46 ms | 100 queries per side; same 222 paths and unchanged event cursor |
| Magic Missile native apply median | 319.66 ms | 48.83 ms | Six applies from three existing fixtures; excludes setup, capture and HTTP |
| Fireball native discovery median | 66.52 ms | 19.54 ms | Three unprofiled paired fixtures; same choices |
| Wall of Fire first native discovery median | 208.20 ms | 155.83 ms | Three unprofiled paired fixtures; same choices |
| Python validation of identical 2.61 MB choices | 808–840 ms | 11.51–11.93 ms | Five offline samples; unchanged schema |
| Actual Conjure Animals warm HTTP/SDK choices p95 | 132.66 ms | 98.89 ms | 100 unchanged queries per side, after compiled validation, before/after detached-copy repair |

The navigation owner evaluates hazardous cells once per unique position in a query, instead of once per overlapping path step. Hazard refresh stops scanning the whole map before checking its already selected visible cells, and the map's global hazard query reads tile conditions directly instead of constructing spatial-condition mappings for every tile. Empty modifier products retain the original value without multiplying by Fraction(1).

The GridMap owner now answers connected spread within the supplied footprint using its existing revision-invalidated cell and directed-edge queries. Across 228 Fireball connected queries (224 discovery footprints and four execution footprints), native crossing checks fall **8,650→840**. The profiled connected time falls **169.05→19.85 ms**; this is a profiler observation, not unprofiled latency. Empty boundaries use the same spatial-crossing predicate without constructing WorldEdge records; populated boundaries retain their original contribution rules. Fireball edge-record constructions fall **9,472→158**. The Wall fixture avoids its 26,299 empty edge-record constructions.

All **28 before/after discovery results across eight paired fixtures** agree, as do capture/replay summaries. Comparisons map fresh UUIDs and canonicalize only the two per-reactor opportunity-exposure lists whose existing order is sorted by those fresh UUIDs; target order/indices, paths, affected cells and every other field/list order stay exact. Door open/close/reopen/destruction, solid terminal cells and solid origins have focused behavior checks. One unrelated pre-existing door-contact failure is retained, not turned into an expected pass.

Python SDK validation uses the established compiled Draft 2020-12 validator over the identical packaged schema, keeping strict finite JSON, format, safe-counter and union checks. Complete decode costs **22.62–28.93 ms** in the five-sample offline comparison. It adds a pinned native-wheel dependency; Windows and WSL installs and 42 package tests pass. The [SDK receipt](SDK_REVIEW.md) contains attribution, dependency and strictness evidence. TypeScript already uses compiled Ajv and did not need an implementation change.

The subsequent live query run exposed another 53–59 ms in generic Python deep copying of the detached choices graph. Returning reconstructed field values through the existing typed detachment path replaces that traversal; no extra JSON encoding, new cache or schema is involved. Both original and cached public results remain isolated from callers. Seventeen session/selection tests pass, including mutation of cold and warm nested targets/lists followed by execution of the retained native target. The 100-query final Conjure cohort preserves complete choices, generation and state revision: initial **225.50 ms**, warm median **70.96**, p95 **98.89**, p99 **102.59**, maximum **291.09 ms** through SDK consumption. Worker warm p95 is **54.92 ms**, maximum **60.15 ms**; the larger end-to-end outlier therefore is not presented as native discovery cost. This is one large summon catalog, not a guarantee for all maps/content combinations.

### Real combat observations

The preceding eight completed fights contain **197 commands, 16 streams and 601 cold-replayed records**. Melee, ranged, Magic Missile A/B/A, Scorching Ray A/B/A, six-target Fireball, Hold Person, Wall of Fire and Conjure Animals are detailed in [SDK_REVIEW.md](SDK_REVIEW.md). Three complete post-repair fights add **70 commands and 215 records**, with normal native combat continuing to terminal. All six subjective streams cold-reduce after shutdown with exact command order, terminal facts, closed causal references and private HUD ownership checks. Summoned Wolf AI, concentration loss, spatial effects, damage, movement and opposing attacks stay active. No mid-command resource refresh, fixed damage, suppressed senses/logs/capture or fake operations are used.

| Selected spell | Before command consumed / worker | After command consumed / worker | Before → after discovery through SDK | After preview through SDK |
| --- | ---: | ---: | ---: | ---: |
| Fireball hitting six goblins | 845.28 / 473.22 ms | 483.40 / 438.91 ms | 578.01 → 105.70 ms | 8.44 ms |
| Wall of Fire | 158.69 / 71.29 ms | 97.61 / 70.38 ms | 796.41 → 242.99 ms | 28.51 ms |
| Conjure Animals | 79.85 / 54.27 ms | 79.68 / 55.62 ms | 1097.58 → 206.20 ms | 10.32 ms |

These are **one selected spell per finite fight per epoch**, not spell percentiles. Query time is separate from the command timer; a fast cast does not hide an expensive choice request. Native worker measurements include dispatch/capture/public construction and query serialization, excluding HTTP/SDK. Fireball still does considerably more native work than the two other spells. The 100-query distribution above measures repeated unchanged discovery independently.

The initialization owner also stops reducing the same initial public state twice. Public schema construction asks Pydantic for all 19 roots in one shared pass, preserving its exact canonical digest; three paired samples fall **113.13→59.46 ms**. These small owner repairs do not solve all Python import cost.

Raw evidence: `.runtime/server-recovery/navigation-owner-{before,after}-20261007/`, `native-command-owner-comparison-20261007.json`, `discovery-grid-owner-repair-20261007/comparison.json`, `sdk-choice-profile-20261007/`, `query-{final,detached-final}-conjure-20261007/`, `combat-http-20261007/`, and `combat-after-spatial-20261007/`. Old fingerprints and unsuccessful harness attempts remain distinct from final measurements.

## Complete startup on the same fixture

Ten fresh host processes on each platform use the same four-goblin/two-seat fixture, including native worker launch/imports, the ordinary pre-Start GC policy, initialization, advance to the first human boundary, encoding, pipe transfer and public-record commit. A condition notification records the first published human boundary; a separate SDK marker follows validated consumption and ACK for both seats. Timing starts at host process launch, excluding fixture configuration construction and uv installation. Filesystem caches are not flushed; these are fresh-process starts with normally warm disk caches, not cold-disk measurements. Runs are sequential, with no competing benchmark process.

| Platform | Host human-ready mean | Host maximum | SDK both-seats consumed mean | SDK maximum |
| --- | ---: | ---: | ---: | ---: |
| WSL | 6273.47 | 6758.88 | 6468.40 | 6930.27 |
| Native Windows | 3916.65 | 4046.53 | 4027.01 | 4134.73 |

All values are milliseconds. Ten observations are reported as means/maxima, with no p95/p99 claims. All twenty workers exit with code zero. Native Windows meets the five-second target; WSL in the `/mnt/c` checkout still misses it, while staying below the ten-second fresh-process target. Earlier import profiles identify Python/model import work as dominant; these complete measurements do not isolate filesystem cost from Python import/model construction. No claim that the mount alone explains the gap is made. The native Windows server plus WSL clients is now functionally proved and is the intended first deployment. The WSL five-second startup miss remains an explicit limitation, not a passed gate hidden by measuring listener liveness.

The earlier worker-only startup rows below remain historical and use different fixtures. Evidence: `http-startup-{wsl,windows}-20261007/` and `startup-complete-comparison-20261007.json` under `.runtime/server-recovery/`.

## Startup reopened after user review

The human explicitly rejected the approximately four-second native Windows startup as acceptable. Passing the original five-second budget therefore does not close startup work or the overall performance plan.

A fresh native Windows `-X importtime` probe imports `player_server.worker` in **2,681.9 ms**. Its content bootstrap subtree accounts for **2,284.0 ms**, including the built-in inventory/action/body declarations and their native spell/item/condition dependencies. These inclusive values overlap and must not be added. A separate cProfile import identifies **1,059 Pydantic model-construction calls** and 36,698 field-schema construction calls. Pydantic model construction occupies **5.516 of 6.196 profiled seconds**; profiling substantially increases wall time, so those seconds are attribution evidence, not the ordinary startup estimate. Repeated inherited model/field schema construction is the dominant observed CPU work.

The existing complete Windows startup sample01 records only **220.22 ms** in Start/initialization and **10.45 ms** in first advancement, against **3,977.27 ms** from host launch through public human readiness. That startup and the import-only probe are separate runs; the residual is not presented as an exact additive decomposition. Host startup, worker process launch, protocol preparation, pre-Start GC and publication also contribute. No production source was changed during this diagnosis.

This identifies an engine/content model-initialization cost, rather than attributing Windows startup to WSL or rendering. Further work belongs to the existing content/model import owners and must retain the single authoritative types, import DAG, complete validation and first-action readiness. Moving the same construction to the first cast would merely hide the cost. Evidence: `.runtime/server-recovery/startup-attribution-20261007/{worker-imports.txt,worker-imports.prof,worker-profile.txt,sources.json}`. Full-scale map/AI measurement limits remain as previously recorded.

## Detailed startup diagnosis — October 7 follow-up

The user's follow-up distinguishes merely importing content from explicitly
prevalidating everything. **The seconds-sized cost is eager Pydantic class/schema
construction during imports.** The explicit catalog bootstrap is separately
measured at **11.29 ms**: 475 admitted declarations, zero presets, zero external
packs, zero materialized runtime objects/events. Its separate CPU profile spends
about 3 ms in registry checks and 11 ms constructing the content-set digest
(overlapping a 15 ms profiled bootstrap). These profiled numbers are not ordinary
startup samples. Registry checks cover identities, references, dependencies,
condition metadata and construction cycles; they do not execute spells or create
all creatures. The built-in-only path does not run external-pack source/AST audits.

The import chain is `player_server.worker -> content_system.bootstrap -> builtin /
builtin_inventory -> action/condition/spell/item/creature modules`. Static imports
retain native class identities for the existing catalog. Defining each Pydantic
subclass eagerly assembles its schema and validator/serializer by default.
At the end of import, BaseObject/BaseValue registries and EventQueue are empty;
the content runtime is not installed. The count of 1,059 is model-class construction,
including the base model, not 1,059 spawned entities or spell executions.

The corrected fine-grained tracer observes 1,058 subclasses and **36,778 fields**,
of which **29,830 (81.1%)** are inherited rather than declared on that subclass.
The final instrumented worker import takes **2,678.92 ms**, after the probe's own
Pydantic setup; instrumentation and scope differ from an ordinary full process.

| Class family | Classes | Field entries | Class construction excluding measured GC |
| --- | ---: | ---: | ---: |
| Conditions | 250 | 13,892 | 796.55 ms |
| Actions | 219 | 13,026 | 484.80 ms |
| Blocks/entities/equipment | 53 | 3,373 | 255.79 ms |
| Native events | 74 | 3,185 | 152.68 ms |
| Other BaseObject descendants | 52 | 824 | 36.83 ms |
| Other passive/data models | 410 | 2,478 | 271.54 ms |

Inside that same import, `set_model_fields` accounts for **266.19 ms** excluding
measured GC, and `complete_model_class` for **1,659.47 ms**. The latter includes
**160.39 ms** at `create_schema_validator` and **33.92 ms** at the Rust serializer
constructor. Subtracting those nested spans leaves roughly **1,465 ms** in schema
preparation/cleaning and surrounding Python completion work. These are nested
attribution spans, not additional independent costs. The earlier CPU profile
locates repeated field construction and recursive schema cleaning inside this
Python work. This is not evidence of one slow user-written validation function.

Automatic GC during this import totals **315.70 ms**. A 139.83 ms collection lands
inside `GuardianOfFaith`; this does not make that spell's own schema uniquely slow.
The 4,766 directly observed BaseModel constructor calls total **28.69 ms exclusive**
(including their nested validation work), far below schema-construction time.
The separate census retains 7,763 model instances, principally descriptors,
references, recipes and metadata; it is not a constructor-call count. Nested Rust
construction need not invoke Python `__init__` separately.

The host separately imports 357 model classes in a 520.11 ms instrumented probe
(after Pydantic setup). `protocol.py` imports discovery records from
`core/base_actions.py`, which also imports native event/grid/sensory/condition
owners. Shared schemas are necessarily constructed separately in host and worker
processes. Some native import dependencies can potentially be removed, but the
whole 520 ms is not removable waste. This host-only probe is not added to another
run's worker timing as an exact decomposition.

A synthetic control confirms why the count alone is misleading: three samples of
1,059 instances of one two-field model take a median **0.69 ms**; defining 1,059
two-field model classes takes **107.09 ms**; defining 1,059 subclasses with 50
inherited integer fields plus one own field takes **853.57 ms**. The engine's nested
types are more complex. This control is explanatory, not a projected server target.

### Disposable build-policy experiments

These preimplementation experiments changed no production source. A disposable process injects only the supported
Pydantic `defer_build` configuration into selected existing roots before import.
It retains the same fields, classes, native validation and top-level imports; it
creates no alternative models. The library builds a deferred schema on first use.
See [Pydantic configuration](https://pydantic.dev/docs/validation/latest/api/pydantic/config/#defer_build)
and [architecture](https://pydantic.dev/docs/validation/latest/internals/architecture/).

Three fresh native Windows processes per policy run the same four-goblin/two-seat
fixture. Timings include imports, public schema, ordinary pre-Start collect/freeze,
fixture configuration, initialization/capture and advance to human input. They
exclude host startup, process-launch latency, pipes, HTTP and SDK. Normal disk
caches remain warm; runs are sequential. Values below are medians, not percentiles.

| Diagnostic policy | Import | Worker ready | Encounter Start | First choices | Through first choices |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current eager policy | 2687.37 | 3193.37 | 211.10 | 12.10 | 3205.58 |
| Defer BaseObject descendants | 1600.70 | 2202.10 | 256.87 | 10.85 | 2212.90 |
| Defer BaseObject + BaseBlock descendants | 1294.06 | 1908.65 | 417.65 | 10.78 | 1919.43 |
| **Defer only BaseAction + BaseCondition** | **1453.82** | **1904.84** | **242.33** | **12.56** | **1917.72** |

All values are milliseconds. The narrower behavior-only policy achieves the same
net benefit as broader deferral with less work shifted into Start. It leaves
blocks, values, events, controllers and public/data models on their current policy.
Completed per-class validators after import/ready are 587/602, versus 1056/1056 in
the baseline. These counters describe each class's completion flag, not a census
of every nested schema compiled as part of another type.

Single additional first-use samples per spell compare current vs behavior-only
policy through the real discovery, ordered preview, command, capture and public
state construction. These are diagnostic samples, not latency guarantees:

| First use | First choices, current → candidate | Command, current → candidate | Forced post-use full GC, current → candidate |
| --- | ---: | ---: | ---: |
| Fireball, six victims | 74.69 → 73.50 | 503.22 → 479.22 | 30.45 → 34.17 |
| Wall of Fire | 224.14 → 232.97 | 51.85 → 60.69 | 18.84 → 22.61 |
| Conjure Animals | 158.00 → 157.75 | 95.64 → 74.39 | 33.56 → 38.70 |

Each emits real records. For these samples both audiences' final names/HP/life
states/positions and the public schema digest match the baseline. That checks a
bounded state summary, not full event/replay equivalence. First commands complete
3/3/6 additional class validators, respectively. Broader BaseBlock deferral instead
raises Fireball/Conjure first discovery to 100.95/202.33 ms; it is not preferred.
All public schema digests remain
`0b99402cf980671394c96bb2afb9b7afd74cbfaeddb66f6367ac31f78b325cf7`.

Deferred schemas built after `gc.freeze()` remain in the ordinary runtime GC graph.
Behavior-only deferral grows the post-choice small-fixture graph from about 38,100
to 41,551 tracked objects; forced post-use GC remains about 5–7 ms versus 4.5 ms.
The spell rows expose the larger graph's measured cost. These deliberately forced
collections occur after the command timing and do not establish natural tail
latency; the previous 1,000-command proof must be repeated for any production change.
No live encounter is frozen and runtime GC remains enabled.

### Recommended bounded next work and review

Proceed with the behavior-only candidate at the existing BaseAction/BaseCondition
configuration owners, subject to the concrete validation in the startup addendum
of the server plan. Do not enable it globally, remove validation, replace fields
with ClassVar, add lazy imports, duplicate public/native types, persist callable
schemas or introduce a new content loader/cache. Full import elimination or
flattening the existing behavior architecture is a separate design change.

Both independent local anti-slop and ECS/DAG reviews agree with the attribution
and flag first-use/GC lifecycle as required checks, not proof already delivered.
The anti-slop review caught a profiler wrapper missing Pydantic's base-init marker;
that diagnostic was corrected with `wraps`, and both stage runs were repeated.
Earlier `*-stages-superseded-init-marker.json` files are explicitly superseded;
none of their constructor timings/counts are used here. Both reviewers subsequently approved the final diagnosis and server-plan §14
without blockers. Anti-slop recalculated stage/family totals and all policy medians;
ECS/DAG checked source fingerprints and native ownership. Both confirmed the
bounded state-summary/digest comparisons and required the documented semantic,
full-startup and natural-GC evidence before production acceptance. No production
implementation acceptance is claimed.

Evidence is under `.runtime/server-recovery/startup-model-study-20261007/`:
`worker-stages.json`, `host-stages.json`, `models.json`, `control.json`,
`bootstrap.json`, `bootstrap-profile.txt`, `experiment-*.json`, and `summary.json`
with source/probe hashes. Raw traces and instrumentation stay outside Git.

## Actual transport results

All latency columns are milliseconds. The actual Python SDK awaits its recording consumer, waits for the committed cursor, and explicitly ACKs it. Timing begins before command submission. A separate process probes health/status. Every command in these latency cohorts is an ordinary End Turn, followed by normal native turn/round progression for the same four-goblin, two-seat fixture. No renderer, capture suppression, synthetic native record, spell-specific percentile, or benchmark-only GC policy is involved.

| Phase / boundary | Samples | p50 | p95 | p99 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial baseline: consumed cursor | 200 | 39.83 | 62.23 | 76.18 | 316.37 |
| Value/content repair: consumed cursor | 1,000 | 43.08 | 61.06 | 71.42 | 335.88 |
| Final production policy: consumed cursor | 1,000 | 42.33 | 62.45 | 73.64 | 109.08 |
| Final command submission response | 1,000 | 6.20 | 7.44 | 11.72 | 25.44 |
| Final terminal command receipt | 1,000 | 42.27 | 62.42 | 73.61 | 109.05 |
| Final explicit ACK complete | 1,000 | 68.28 | 83.96 | 101.42 | 124.85 |
| Final host health | 5,942 | 5.53 | 7.16 | 10.24 | 30.34 |
| Final seat status | 5,942 | 5.59 | 7.20 | 9.63 | 22.60 |
| Windows-local consumed cursor, earlier smoke | 5 | 30.82 | — | — | 41.95 |

The 200- and 1,000-command rows have different sample counts; they use the same fixture and command/consumption path. The two long End Turn cohorts use identical production source fingerprints, with the policy-proof cohort adding labelled instrumentation. Its census and cycle-proof costs are excluded from the timing table.

Final native dispatch p95 / p99 / maximum is 6.92 / 7.94 / 52.43 ms; native automatic advance p95 / p99 / maximum is 12.41 / 15.75 / 22.57 ms. These worker measurements exclude HTTP, pipe, storage, SDK decode and consumer work and are not added to the end-to-end measurements. The worst final consumed-cursor observation, Amber command 329 (total command 658), contains only 5.39 ms of native dispatch; its adjacent advances are 12.10 / 17.50 ms and receipt-to-consumer adds 0.028 ms. The available timestamps place this remaining 109.08 ms outlier outside measured native dispatch but do not identify a particular host/client stage. The separate native maximum of 52.43 ms occurs at Amber command 279, whose consumed latency is 90.63 ms.

At final orderly shutdown each seat retains 500 receipts (approximately 194 kB) and a 13.15 MB exact-byte spool. Queued query bytes are zero. The 351,908 reserved delivery bytes include the host's content response reservation and are not reported as zero allocation. All measured workers exit with return code zero.

Receipts under `.runtime/server-recovery/`: `wsl-http-final-20261007/` (initial), `http-long-after-20261007/` (value/content repair), `http-long-process-policy-20261007/` (final ordinary run), `http-long-process-policy-profile-20261007/` (policy proof), and `windows-native-http-smoke-20261007/`. Each preserves configuration, actual SDK records, samples, worker measurements and source hashes. The Windows observation is a functional smoke, not a percentile estimate. The final runner's 1.58-second listener-start observation is **not native game readiness** and does not satisfy the full-startup target.

## Startup and comparable capture measurements

Ten fresh processes ran for each row below. Filesystem caches were not flushed. “Ready” on Windows measures native-worker imports through the first legal human boundary. The WSL ready value is the sum of the recorded import, Start/capture, encode and first-advance stages. These startup probes exclude HTTP-host imports and pipe launch. Outer process wall time additionally includes close and process exit.

| Environment / fixture | Ready mean | Ready maximum | Import mean | Start/capture mean | Outer process mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| WSL, four goblins, two grouped seats | 5,442.71 ms | 6,000.71 ms | 4,812.62 ms | 605.47 ms | 6,602.07 ms |
| WSL, four goblins, four individual seats | 5,460.13 ms | 5,824.96 ms | 4,817.09 ms | 613.77 ms | 6,587.17 ms |
| Windows, authored crypt | 3,205.15 ms | 3,323.01 ms | 2,630.97 ms | 560.33 ms | 4,573.97 ms |

The Windows and WSL rows use different fixtures and must not be treated as a same-workload platform comparison. The WSL native-worker stages alone exceed the 5-second warm-ready target. The Windows native-worker stage fits that target, but does not establish full HTTP-host readiness within five seconds. All measured fresh-process rows fit ten seconds in their stated scope.

The following paired rows use ordinary native end turns and advances to accumulate history. Capture, rules, senses, reactions, logs and audience processing remain enabled. Each displayed end turn produces four new native events. Times are individual cProfile dispatch measurements, not percentile estimates.

| Seats / retained history | Public roots | Public bytes plus reply | Baseline | Repaired |
| --- | ---: | ---: | ---: | ---: |
| Grouped / 106 | 2 | 13,118 B | 18.48 ms | 19.01 ms |
| Grouped / 10,006 | 2 | 13,172 B | 105.67 ms | 21.95 ms |
| Individual / 106 | 4 | 21,329 B | 28.54 ms | 27.46 ms |
| Individual / 10,006 | 4 | 21,435 B | 1,170.84 ms | 33.13 ms |

Baseline runs overlapped a heavy engine test process. The 1,170.84 ms result includes 1,037.49 ms charged to `capture_context` self time; it is an individual outlier, not a stable fanout estimate. No speedup ratio is claimed from it. Fixed cohorts ran sequentially after that competing process exited. Baseline profiles still identify the repeated scans, and repaired profiles show those scans absent from the dominant call tree. Native end-turn work remains approximately 5–6 ms. At the intermediate 1,002-event tier, a round boundary produces nine events, so that tier is not compared as equivalent four-event work.

## E01–E14 disposition

| ID | Measured evidence and disposition |
| --- | --- |
| E01 — startup | Complete ten-start, same-fixture measurements above replace the earlier worker-only observations. Windows meets five seconds, WSL on the mounted checkout misses five seconds but fits ten. Duplicate initialization reduction and schema-root generation repaired; remaining import/model construction cost is explicit. |
| E02 — full-history capture indexes | **Confirmed and repaired by the capture owner.** Matched grouped four-event dispatch changes from 105.67 ms to 21.95 ms at 10,006 retained events. Shared native indexes replace repeated history reconstruction. |
| E03 — actor admission reconstruction | **Confirmed and repaired by the capture owner.** Baseline admission folding costs approximately 39 ms across two audiences and 77 ms across four at 10,000 events. The repaired per-audience checkpoint preserves cold/hot parity and historical fallback. The measured individual-seat slope is now 27.46 to 33.13 ms. |
| E04 — event lookup | The existing EventQueue owner now supplies the UUID-to-raw-index lookup. At 10,010 entries its dict occupies 294,992 B and unique integer values 280,280 B: **575,272 B total**, excluding shared UUID objects. This is intentional retained-history growth. Sensory lookup alone was not independently shown to dominate. |
| E05 — discovery | Each history tier has 100 unchanged queries. Repaired grouped mean is approximately 2.25–2.34 ms, below the 100 ms warm target. Separate cold cProfile: 39.41 ms total, 25.01 ms native discovery. Warm profile: 14.23 ms total, 14.14 ms deep copy. Profiling overhead is substantial; these profile values are not unprofiled latency estimates. This small goblin-query observation predates the much larger Conjure response and the measured detachment/SDK repair above; no new cache was introduced. |
| E06 — preview | Each tier has 100 unchanged exact previews. Mean is approximately 0.020 ms. Separate cold/warm profiles are 0.476 / 0.194 ms; cold native predicate/route work is 0.208 ms. Existing bounded-cache behavior is retained. No cache-policy change was made. |
| E07 — sheets/content | After the initial capture fix, native sheet snapshots cost approximately 3.6–4.1 ms under profiling, content copying approximately 7.4 / 12.5 ms, and long-history `project_after_values` lookup approximately 3.95 / 6.56 ms for grouped / individual seats. Subsequent owner repairs remove repeated admitted-descriptor copies, reverse the existing boundary traversal, and stop registering scalar-read temporary values. The allocation comparison below verifies zero retained-value growth; the first combined follow-up still has one 335.88 ms worker outlier, followed by the final process-policy result above. These earlier profiles are not claimed as costs of the latest code. Equipment/resource mutations have functional crypt evidence, not separate latency distributions here. |
| E08 — path cache | Historical baseline, superseded by the follow-up navigation repair above: one native miss and 100 stable hits at distance 11 produce 222 admitted paths on the four-actor open-floor fixture. Complete navigation: cold 8.97 ms; warm mean 5.22 ms, p95 5.40 ms, maximum 5.92 ms. The cache-hit hook alone is approximately 0.0034 ms and excludes key construction/copying; the outer measurement includes both. |
| E09 — subjective path filtering | **Repaired:** call-local reuse of hazard results per unique path cell. The follow-up table gives paired measurements and unchanged complete paths/cursor. No persistent cache or native movement-rule change. Largest-map/hidden-blocker scaling remains unmeasured. |
| E10 — optical guard | No guard change was made. `test_inert_residue_changes_tile_facts_without_rebuilding_routes` passed in the final focused cohort. Native Fireball/wall fixtures retain normal senses and world updates. This is correctness evidence for the existing guard, not a new optical performance distribution. |
| E11 — native broad cases | Seventeen existing native fixtures pass capture, projection, public encoding and cold shared reduction: melee/ranged/opportunity; repeated Magic Missile; Scorching Ray A/B/A and miss; level-11 Eldritch; Fireball open/wall; wall/fire/ring; Call Lightning repeat; Shield/Magic Missile; Stoneskin; Counterspell; summon bear and Fey control loss. One unprofiled and one profiled execution per case; no percentiles. Setup-inclusive observations include Fireball 553 / 777 ms, two Magic Missile casts 2.266 s, and wall-fire fixture 1.230 s. These are not command-through-wire budget comparisons. Mixed-controller native advances are separately recorded below. |
| E12 — wire/storage | Model encoding for matched end turns is approximately 0.12–0.21 ms for 13–21 KiB including private reply. The actual HTTP table additionally covers pipe transfer, validation, spool, SSE, SDK decode, awaited consumer and ACK; it does not separately attribute every one of those stages. The cold prefix checks use the shared reducer, not an SDK rules implementation. |
| E13 — retention/GC | A 900.102-second run completes 179 native operations: 108 commands and 71 advances, plus 36 choices and previews. Pacing is excluded. Retained history grows from 71 to 1,363; process high-water memory from 327,725,056 to 391,426,048 B; four native/known actors remain stable. This does not prove or disprove every working-cache leak. The earlier capture-only repaired unpaced run completes 300 native operations in 10.313 s. Its 263 commands have p95 29.76 ms, p99 33.08 ms, maximum 455.22 ms. GC callbacks directly associate generation-2 pauses of 426.99 / 363.70 / 314.95 ms with command / discovery / advance outliers. Those collections recover 9 / 0 / 9 objects. Retained-graph scanning is an established tail cost. Subsequent value-owner repair eliminates 35,000 leaked tracked values per 200 commands and keeps the registry flat; the final process policy below then excludes the pre-game import graph from runtime collections while keeping runtime GC enabled and thresholds unchanged. This policy is reported explicitly rather than presented as unchanged global GC behavior. |
| E14 — audience fanout | Grouped and individual-seat comparisons above preserve the same native work; public roots, bytes, copying and projection scale with audiences. Mixed human/AI play reaches native terminal after 35 native operations in 1.376 s. Nine advances have maximum 120.27 ms, with no percentile claim. Its 28 commands include a 299.99 ms maximum containing a 274.18 ms generation-2 GC pause. The actual HTTP run exercises two independently scoped, promptly consuming seats. Slow-reader/backpressure behavior is covered by separate transport correctness tests, not this throughput result. |

## Replay, memory and source evidence

`http-process-policy-cold-prefix.json` cold-replays the final ordinary and instrumented cohorts: four seat prefixes, 8,008 real records, 500 commands per seat in each run, stable identities, closed references and owned HUD/inventory. All four goblins retain 7 HP in the shared reduced state.

`http-after-cold-prefix.json` additionally passes all 4,808 records from both after-repair cohorts (four seat prefixes), with exact command numbering, stable scope, closed references and owned HUD/inventory. All four goblins retain 7 HP in the final shared reduced state.

`http-cold-prefix.json` records cold replay of the real HTTP prefixes using the existing shared reducer and reference/privacy checks. The end-turn benchmark intentionally stops in an active encounter; no native terminal outcome is fabricated. Earlier completed gameplay evidence remains in `.runtime/server-implementation-20261007/`:

- `gameplay-final-cold-replay.json`: 16 final streams, 728 records, all pass.
- `gameplay-all-cold-replay.json`: 24 streams pass; two superseded v1 AI views expose the earlier undisclosed-child-reference defect. Corrected final views pass.
- `crypt-v5-cold-replay.json`: 56 records, 36 commands, nine spell applications including six nonfirst applications; closed references, authority and terminal replay pass. Strict world-object values are decoded through the owner's JSON-mode API.

For the recorded gameplay corpus, the isolated SDK decode pass retains no growing world/history. Python peak traced allocations are 3,977,147 B; TypeScript peak working heap/external delta is 29,198,496 B, with process maximum RSS 126,713,856 B. These fit the 128 MiB working budget for this corpus. They do not prove that a maximum-sized 64 MiB JSON record fits the decoded budget.

`PERFORMANCE_SOURCES.json` stores the final hot-path/lock/schema fingerprints and the concrete receipt paths. Full source/environment snapshots, private seed/configuration, root/event counts, bytes and profiles are retained under `.runtime/server-recovery/`. Fixed measurements snapshot source hashes at process import. Early baseline probes hashed files at completion and overlapped a passive descriptor import move, so their source attribution is narrower. The final actual HTTP hosts record source hashes at orderly shutdown; the measured hot-path files remained unchanged during those runs.

The supporting probes are `performance.py`, `performance_spells.py`, `startup.py`, `test_host.py`, `http_run.py`, `http_performance.py`, `gc_worker.py`, and `http_replay.py` under `devtools/player_server_acceptance/`. Timing hooks subtract the supplied start timestamp from `perf_counter`. No renderer, fake native records, capture suppression, extra gameplay reducer, or production benchmark endpoint is introduced.

## Windows/WSL transport and remaining scope

**H49 now passes with a native Windows server and both SDK clients in WSL.** The Windows process explicitly listens on its WSL virtual-adapter address, `172.19.208.1` on this machine. The Python and TypeScript clients complete **47 commands and 110 records**, and both receive terminal state. Both streams also pass cold shared reduction, cursor/reference closure and privacy checks after Windows shutdown. Windows host and worker exit cleanly. No firewall or system-policy change is made. The server README explains how to discover the adapter address; the machine-specific address is not a production default.

Earlier attempts listened on the wrong interface for this route and timed out; their preserved receipt did not establish a firewall failure. The explicit-bind health check and actual cross-environment match supersede that acceptance gap. Evidence: `.runtime/server-recovery/windows-wsl-explicit-bind-20261007/` and `windows-wsl-sdk-20261007/`.

No 100-sample dense-Fireball-through-HTTP percentile, separate native-AI p95, cold-disk startup distribution, largest-map scaling distribution, or allocation-by-owner proof for every working cache is claimed. Existing finite combat, mixed AI and topology fixtures plus explicitly scoped distributions are the evidence. Warm-query p95 is below the target for the measured large summon response, but individual SDK/host pauses remain recorded. Native event/spool history intentionally grows; the existing retention policy is not a persistent campaign save system.

## Allocation repair and the production worker policy

The exact slowest baseline command was Amber command 32, public cursor 128: submit 6.41 ms, terminal receipt 316.35 ms, consumed cursor 316.37 ms, and native worker 280.83 ms. Thus the worker accounts for approximately 89% of this spike; receipt-to-consumer adds only 0.03 ms. Adjacent native advances take 12.43 and 13.54 ms.

A separate instrumentation-only pass through the same 200-command HTTP workload confirms generation-2 GC inside native dispatch: 268.49 ms in a 275.97 ms command, 313.05 ms in a 321.88 ms command, and 348.91 ms in a 363.50 ms advance. None occurs inside the two object censuses. Those censuses add 126 / 195 ms at startup and the last command, so this pass is not used as a latency benchmark. The corpus remains 471 descriptors per seat, but tracked objects grow by 14,000 StaticValue, 14,000 ContextualValue and 7,000 ModifiableValue instances between startup and 200 commands. This growth requires native-owner attribution rather than being assumed intentional event history.

The native owner chain was `Ability.get_combined_values` creating and combining temporary values during max-HP, passive-perception and HUD scalar reads. A strong native registry retained those temporary values. The repair propagates an explicit `use_register=False` through these temporary computations; the default owned computation still registers its original 11 values. Independent before/after diagnostics show max-HP / passive-perception / HUD reads fall from 11 / 16 / 44 retained values to zero each. No arithmetic semantics or GC settings change.

The matched 200-command after census keeps the value registry exactly **2,000 → 2,000**, with zero growth in StaticValue, ContextualValue and ModifiableValue, compared with **14,000 / 14,000 / 7,000** additional tracked objects before. Native history is the same 49 → 1,899 in both passes; the catalog stays at 475 descriptors and admitted content at 471 per seat. Allocated-block growth falls from 684,000 to 85,985. Generation-0 / 1 / 2 collection counts fall from 792 / 72 / 4 to 92 / 8 / 1; the after run's sole generation-2 collection occurs during startup. The two after censuses add 131 / 134 ms and are excluded from latency claims.

The separate content repair reuses existing sanitized admitted descriptors and the unchanged content tuple instead of recreating every descriptor for every audience. The historical boundary lookup walks the existing insertion-ordered dictionary in reverse and retains the maximum eligible public-occurrence semantics, including late older disclosures. These owner changes introduce no extra cache or registry.

Receipts: `.runtime/server-recovery/http-allocation-comparison.json`, `http-allocation-before-20261007/worker-profile.json`, and `http-allocation-after-20261007/worker-profile.json`; content patch before sources were reconstructed by reversing only the two-block patch, with explicit hashes in `allocation-patch-source.json`. Native registration diagnostics are `.runtime/server-implementation-20261007/transient-value-registration-{before,after}.json`. The 1,000-command timing extension still exposes the worker pause documented above; the separate 1,000-command callback pass directly attributes a matching outlier to generation-2 GC: **307.86 ms inside a 313.62 ms native command**, at Blue command 333 and native history 6,195 → 6,199. It collects 4,620 objects and occurs outside both censuses. The value registry stays at exactly 2,000 through all 1,000 commands. The tracked graph grows from 495,487 to 658,206 objects (96.08 → 145.47 MB shallow bytes); 47.07 MB of startup dicts, 18.76 MB of startup sets, and 11.03 MB of FieldInfo are already present before the command workload. Growth includes 48,416 dicts, 40,338 sets, 34,936 lists and 22,775 UUIDs; the native event cursor grows 49 → 9,299. There are also 2,000 retained TurnContext and 1,000 AdvanceResult values, whose default BaseObject registration is a separate owner-audit lead, not automatically intentional event history. Receipt: `http-long-profile-after-20261007/attribution-summary.json`. The startup/end censuses add 276 / 373 ms and are excluded from latency claims. Those allocation-only cohorts did not disable, freeze or retune GC. The final production process policy below is a separate, explicitly measured change.


The final passive-record repair defaults TurnContext and AdvanceResult to unregistered values after auditing UUID ownership. Through 1,000 real commands, BaseValue stays **2,000 → 2,000** and BaseObject stays **535 → 535**, with no registered TurnContext or AdvanceResult retained. Native event history intentionally grows **49 → 9,299**; this is kept distinct from transient-registry retention.

Both the real worker CLI and the instrumentation wrapper call the same `player_server.worker.run_process()`. It refuses a previously installed runtime or nonempty native history, warms the static protocol identity, performs a full collection, freezes only that pre-Start graph, and enters the normal worker loop. The probe confirms event cursor and both native registries are zero at freeze time. It observes approximately **459,472 frozen objects** and **85.09 MB of shallow tracked bytes** immediately before freezing, with process RSS **304.51 MB**. The shallow byte count describes the existing graph and is not an additional allocation or a complete deep-memory estimate.

Measured entry components are protocol warming **120.63 ms**, full collection **209.37 ms**, and freeze **0.001 ms**. The complete instrumented prelude spans **538.63 ms**, including a **177.86 ms** pre-freeze census and other measurement overhead; it is not offered as an uninstrumented startup time. The normal path performs the same policy without these probes. The policy's cost belongs to process startup, not to an excluded gameplay command or scheduled between-command collection.

Runtime GC remains enabled throughout the observed start/end states, with thresholds unchanged at **(2,000, 10, 10)**. An instrumentation-only generation-0 proof reclaims a newly created cycle after Start. During commands/advances, **185 collections** still occur, including a **43.57 ms generation-2 collection inside a 49.01 ms native command**. Frozen count is **459,464** both after Start and at the end; no live game graph is subsequently frozen. Normal tracked objects grow **31,996 → 179,113**, normal shallow bytes **10.55 → 53.63 MB**, and process RSS **316.57 → 375.55 MB** as retained event history grows. Startup/end runtime censuses add 45.83 / 116.19 ms and remain outside the ordinary timing evidence.

The tradeoff is explicit: imported cycles orphaned after freezing can remain until this single-game process exits. No `unfreeze`, GC-disable window, changed threshold, or benchmark-only freeze is used. Process exit bounds that retention; this is not an in-process multi-session policy. The proof receipt is `http-long-process-policy-profile-20261007/policy-summary.json`. The earlier long callback receipt remains available so the improvement is not inferred from the short 200-command run alone.
