# Failed engine speedups and remaining slowdowns handoff

Date: 2026-10-16. For the engineer or agent continuing the engine performance work.

The execution migration has not delivered the required action latency. Several local improvements are real, but large costs remain in repeated input discovery, source and dependency checks, sensory preparation, terrain lifecycles, discovery enumeration, copying and publication. Correctness requirements explain which results must be preserved; they do not justify the observed hundreds of milliseconds or seconds. The continuation must remove specific repeated work and demonstrate the complete resulting cost.

This handoff covers the failed or incomplete spell-execution, sensory/terrain, discovery, copying/publication and causal-execution speedups, with the worktree and saved evidence for each approach. It does not authorize a new engine rewrite. The accompanying [first-principles analysis and diagrams](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/agent_docs/ENGINE_COMPUTATION_THEORY_2026-10-16.md) is a theoretical alternative, not an implemented or benchmarked solution. Only documentation was changed in this review/handoff work; no fresh engine tests or benchmarks were run.

**1. Human direction and constraints to retain**

- The objective is materially faster actual gameplay, including Ice Storm, Fireball, Sleet installation/removal and discovery. Inventory completion, more framework plumbing and passing correctness checks are not performance outcomes.
- The previous approval/review process failed to insist on an early demonstrated reduction in dominant work. Do not defend the latency by reciting reactions, ordering or possible callbacks.
- Keep ECS data and existing system owners. Avoid a new universal World, opcode/rule interpreter, manager hierarchy, reflective proxy or framework that classifies every other framework.
- Independent substantial calculations and independent output channels may run in parallel. Do not serialize everything behind a full observer/publication barrier. Do not create a task per scalar or cell assignment.
- Preserve actual rules and observable dependencies, including per-step movement. A serial loop alone does not prove that all of its mathematical work must stay serial.
- The causal worktree records the human's one-execution-path requirement. Do not silently introduce competing old/new mutation pipelines or merge the held experiment wholesale.
- Antimagic was explicitly removed. Its old optimization package is superseded; generic Globe/world-presence behavior remains relevant.
- Read the applicable AGENTS.md, RECOVERY_PLAN.md and HOW_TO_TEST.md before later implementation/testing. No other chat may be read or messaged. Code, saved artifacts and the human are the evidence.
- The minimum 20-minute theoretical study was completed. The later request is to hand off the findings, not to start implementing the alternative without direction.

**2. Actual worktrees and what belongs to each**

The following locations were checked against `git worktree list`. A shared HEAD does not imply shared working files: substantial changes are uncommitted. The Windows checkout sometimes appears with lower-case path components in Git metadata; the mixed-case path below is the current workspace path.

| Worktree and branch | Approach tried or role | Evidence and disposition |
| --- | --- | --- |
| `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine` — `feature/speedupsensory`, HEAD `229ce025f3ff` | Production/reference checkout and current theory/handoff documents. | The benchmark baseline is an archive of this commit, not an assertion that today's dirty primary equals the archive. Existing [discovery rework](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/agent_docs/PLAYER_ACTION_DISCOVERY_REWORK_PLAN_2026-10-13.md) supplies background, not proof the later full Choices cost is solved. |
| `/home/tommaso/.codex/worktrees/aoe-sensory-batching/dnd_engine` — `codex/aoe-sensory-batching`, HEAD `229ce025f3ff` | Earlier targeted speedup: admitted terrain unions, separate freshness channels, emitting-destruction settlement, staged area observation, aggregate blood/ash records and optical allocation changes. | [Batching plan](/home/tommaso/.codex/worktrees/aoe-sensory-batching/dnd_engine/agent_docs/plans/AOE_NONMOVEMENT_SENSORY_BATCHING_PLAN_2026-10-15.md), [study](/home/tommaso/.codex/worktrees/aoe-sensory-batching/dnd_engine/agent_docs/AOE_SENSORY_PERFORMANCE_STUDY_2026-10-15.md). Initial worker Fireball median about 685.89→534.67 ms with 431 versions; later staged sample 146.41 ms with 161 versions. Expanded qualification remained pending. This approach predates the general service and used no thread pool or general scheduler. |
| `/home/tommaso/.codex/worktrees/aoe-general-execution/dnd_engine` — `codex/aoe-general-execution`, HEAD `229ce025f3ff` | Held general-effect experiment: authored execution/query changes, observation settlement, shared physical preparation, field installation/retirement, crossing domains, capture/copy/history experiments and discovery/wall algorithms. | Main investigation: [GENERAL_EFFECT_EXECUTION_PLAN](/home/tommaso/.codex/worktrees/aoe-general-execution/dnd_engine/agent_docs/plans/GENERAL_EFFECT_EXECUTION_PLAN_2026-10-15.md). Mixed retained improvements, rejected experiments and unfinished work. Faster held casts do not qualify the later causal implementation. This tree is source evidence for selective reuse, not a wholesale merge source. |
| `/home/tommaso/.codex/worktrees/causal-execution/dnd_engine` — `codex/causal-execution`, HEAD `229ce025f3ff` | Fresh production-based typed causal service: query/dispatch routing, dependency/conflict graph, source grouping, current observation ownership, coupled mutations, optical calculations, native query migration and capture/public-state work. | [Architecture/progress plan](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/agent_docs/plans/ENGINE_ARCHITECTURE_PLAN_2026-10-16.md), [migration inventory](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/agent_docs/plans/ENGINE_QUERY_DISPATCH_MIGRATION_INVENTORY_2026-10-16.md). This is the active implementation being criticized. Saved ordinary runs still miss the latency targets. Protect its ongoing dirty changes. |
| `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine` — `codex/spells-rank-one-two`, HEAD `059ad0af4c9` | Local owner/result simplifications: finite-item resource revision, Guardian strike result, fall applied result, Harm completed incoming result. Also analyzes turn witnesses, Fireball readbacks and movement provenance. | [Owned-state report](/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine/agent_docs/OWNED_STATE_READBACK_FIXES_AND_REWORK_REPORT_2026-10-16.md). Four fixes are delivered in that working tree; the three additional findings are analysis there. Do not count its tests as causal-worktree qualification or independently recreate already-delivered fixes. |
| `/home/tommaso/.codex/worktrees/light-observation-performance/dnd_engine` — detached HEAD `792ec024ee56`, dirty source | Earlier light-observation optimization: compact emitter descriptors and removal of duplicate live footprint/objective/ambient maps. Related sensory evidence, not an implementation of the causal service. | [Exact result](/home/tommaso/.codex/worktrees/light-observation-performance/dnd_engine/.runtime/light-performance/result.json). Gallery dispatch/encoding medians: committed baseline 85.19 ms, dirty light implementation 187.42 ms, compact candidate 88.94 ms. This largely repairs that light regression; it does not qualify AoE cast targets. |

The targeted batching and general-execution experiments are different approaches. Their lower event counts partly reflect staged/aggregated event contracts; they cannot be compared to the causal service as though all three merely changed an internal scheduler.

Exact targeted-batching artifacts are [first checkpoint](/home/tommaso/.codex/worktrees/aoe-sensory-batching/dnd_engine/.runtime/performance-investigation-20261015/final/headline-comparison.json) and [later staged worker sample](/home/tommaso/.codex/worktrees/aoe-sensory-batching/dnd_engine/.runtime/performance-investigation-20261015/staged/stage-worker-batched.json). The directory named `final` is an earlier checkpoint, not the latest state. The later 146.41 ms result is one sample in a full replay; its roughly 148.95 ms Choices cost is separately recorded. Some headline study values differ from later overwritten `fields/*-plain.json` artifacts: cite the named checkpoint, not a blended “final result.”

**3. Frozen source arms inside the causal worktree are not separate worktrees**

All directories in this table are under `/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/.runtime/causal-execution/`. They preserve historical benchmark source arms. They are different from the live dirty implementation above.

| Directory | What was measured | Result files in the same runtime directory |
| --- | --- | --- |
| `production-229ce/` | Archived production baseline at `229ce025f3ff`. | `production-fireball-ordinary-v1.json`, `production-sleet-ordinary-v1.json`, `production-ice-storm-ordinary-v1.json`. Separate validation files exist. |
| `service-routing-cost-only-v1/` | Initial connected service/action/event/sensory slice plus traversal-cost hint; excludes later coupled/capture/optical changes. | `service-cost-sleet-ordinary-v1.json` and `service-cost-sleet-validation-v1.json`. Large Sleet improvement from the pathological baseline, still too slow. |
| `connected-service-v1/` | Adds connected coupled item, capture and owned-optics source. | `connected-service-{fireball,sleet,icestorm}-ordinary-v1.json`; Sleet cast regressed versus the narrower previous arm. |
| `connected-world-query-v2/` | Optical masks/passive eligibility reuse, indexed UUID relationships, bounded capture membership, deferred map publication and authored crossing domains. | `connected-world-query-{fireball,sleet,icestorm}-ordinary-v2.json`, plus separate Sleet validation. |
| `native-value-boundaries-v3/` | Further native evaluator/current-query boundaries, before the connected sensory source-group consumer was complete. | `native-value-boundaries-{fireball,sleet,icestorm}-ordinary-v3.json`; ordinary totals regressed against v2. |

`connected-current-fields-v9-fireball.json`, `connected-acquired-cohorts-v10-fireball-profile.json` and `connected-light-domains-v11-sleet.json` identify the live causal worktree as their source. They describe the source at those recorded runs, not an assertion about every subsequent edit. No newer ordinary Ice Storm run was found among the top-level causal artifacts inspected for this handoff; v3 must not be called today's measured Ice Storm performance.

**4. Verified saved ordinary timings**

Milliseconds, rounded. These are individual loaded samples, not medians. Native includes construction/apply/death work. Total includes post-operation, both-audience publication and encoding. Setup/replay, discovery, player-command binding, network, client work and session close are excluded. Session close is separately reported and must not be added to every action. Different source arms and changed event counts require semantic qualification; similar final damage alone does not establish full equivalence.

| Source arm / spell | Native | Both-audience publication | Total with encoding | Native versions |
| --- | ---: | ---: | ---: | ---: |
| Production Fireball | 718.412 | 46.872 | 770.231 | 431 |
| Production Sleet cast | 53,258.035 | 122.821 | 53,387.237 | 853 |
| Production Sleet drop | 6,140.664 | 349.938 | 6,499.514 | 810 |
| Production Ice Storm | 2,453.201 | 166.041 | 2,628.514 | 626 |
| Cost-only/service v1 Sleet cast | 1,487.080 | 112.732 | 1,605.185 | 853 |
| World-query v2 Fireball | 694.411 | 41.226 | 740.377 | 431 |
| World-query v2 Sleet cast | 1,362.245 | 103.314 | 1,470.442 | 853 |
| World-query v2 Sleet drop | 257.336 | 114.034 | 379.699 | 810 |
| World-query v2 Ice Storm | 395.637 | 167.593 | 566.889 | 350 |
| Native-value v3 Ice Storm | 436.867 | 178.685 | 619.705 | 350 |
| Current-fields v9 Fireball | 1,302.880 | 55.786 | 1,364.699 | 455 |
| Light-domains v11 Sleet cast | 1,496.582 | 88.241 | 1,591.081 | 853 |
| Light-domains v11 Sleet drop | 364.729 | 285.669 | 662.844 | 810 |

Direct evidence: [production Fireball](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/.runtime/causal-execution/production-fireball-ordinary-v1.json), [production Sleet](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/.runtime/causal-execution/production-sleet-ordinary-v1.json), [production Ice Storm](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/.runtime/causal-execution/production-ice-storm-ordinary-v1.json), [v9 Fireball](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/.runtime/causal-execution/connected-current-fields-v9-fireball.json), [v11 Sleet](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/.runtime/causal-execution/connected-light-domains-v11-sleet.json), [v3 Ice Storm](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/.runtime/causal-execution/native-value-boundaries-icestorm-ordinary-v3.json).

The large early Sleet reduction is real evidence of improvement in that source arm; “nothing ever improved” is inaccurate. The later samples still miss the targets, and some regress against earlier connected checkpoints. Neither the under-100 ms nor the subsequent 40 ms goal is qualified. The faster held general-execution command samples have different implementation/history contracts, so no direct speedup factor against causal v9 is established.

**5. The measured amplification behind the Fireball complaint**

The [acquired-cohorts v10 diagnostic](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/.runtime/causal-execution/connected-acquired-cohorts-v10-fireball-profile.json) is instrumented. Use its invocation counts; do not mix its elapsed times with ordinary timings or add nested inclusive times.

| Observed operation | Count |
| --- | ---: |
| Dictionary `get` calls | 1,400,805 |
| Execution queries | 8,953 |
| Predecessor checks | 43,503 |
| Tile query-support requirements | 136,683 |
| Native-value support checks | 52,410 |
| Native block-hazard support checks | 68,250 |
| Observer recomputation entries / boundary snapshots | 72 / 72 |
| Physical directional FOV calculations | 24 |
| Contact passes | 102 |
| Passive-perception scalar calls | 566 |
| Boundary providers resolved / reused | 11,304 / 0 |
| Contacts reported reused | 22,066 |
| Sensory-update terminal constructions | 12 |

The million dictionary operations are not all proven unnecessary checks. The concrete diagnosis is amplification around preparation, validation and control, even when results are reused. Seventy-two recomputation entries are not 72 complete FOV solves; 12 terminal records do not imply only 12 preparation passes.

The source path is event metadata → participant identification → current observations → pending settlement/query control → physical/contact/provider preparation → observation evidence. Entry points include [events.py](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/dnd/core/events.py), [encounter.py](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/dnd/encounter.py), [execution.py](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/dnd/core/execution.py), [sensory.py](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/dnd/blocks/sensory.py) and [gridmap.py](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/dnd/core/gridmap.py). Function names and saved source labels are more durable than old plan line numbers.

**6. Identified problems and the work each correction must remove**

| Problem | Evidence / affected path | Required computational difference and status |
| --- | --- | --- |
| Per-read execution bookkeeping | `execution.query` derives access, settles pending work and collects/orders predecessors across active prefixes. | Ordinary ready reads must not reconstruct sequencing already provided by completed synchronous child calls. Necessary local reentrancy/dependencies remain. The theoretical alternative is not implemented. |
| Expensive proof of a cache hit | Tile/value/block-hazard/source admission recursively inspects owners and providers. | Own the inputs being reused and invalidate them at actual writes. A clean read checks bounded metadata; moving the same complete scan to every write is not a win. |
| Repeated physical input extraction | Boundary snapshots repeatedly acquire the same layout/provider data; 11,304 providers resolved, zero reused in v10. | Existing owners maintain physical contribution rows/indexes; share unchanged rows across relevant consumers. No universal capability registry or arbitrary callback-result cache. |
| Event/source changes coupled to physical work | Participant identity and new source/terminal processing enter observation settlement. | Separate physical-input changes, contextual procedure calls and historical evidence. A new event cursor alone does not change a wall; a genuinely source-sensitive procedure still runs. |
| Too much work per observer | Shared boundary/light inputs are prepared repeatedly while contacts and observer verdicts also run. | Share objective physical data; retain distinct senses, concealment, contacts, knowledge and disclosure. Whole `recompute_observer` is not automatically a passive worker job. |
| Terrain cell multiplication | Field installation/removal performs actual per-cell modifiers, source acquisition, after-value capture, invalidation and publication. | Keep the C actual component updates and required after-values; event count follows the admitted aggregation contract, not cell count. Factor common source/input preparation out of the loop, union changed addresses between real reads, avoid C complete observer jobs. Current buffering/hints already exist and must not be presented as new fixes. |
| Destruction and attached contributions | Blocker removal, support, walking, location, emitter retirement and debris creation cross owners. | Preserve each actual admitted transition coherently before its dependent callback; use direct contribution handles and union/reuse affected-data work within that transition. Genuine reads and separately admitted debris fields can split it. Later breach reach uses committed geometry. No whole-cast rollback or fabricated simultaneous admission. |
| Installation and removal tails | Common field refresh is followed by maintained handlers, DISPERSE/DOUSE, cleanup, terminals or concentration callbacks. | Carry pending derived dirt across compatible owner boundaries; facts must not redirty committed inputs. Cover drop, expiry, suppression, resumption and replacement, not only cast. |
| Broad crossing fallback | An irrelevant unknown crossing owner can disable the sparse algorithm globally. | Maintain actual authored channel/coverage domains at registration/change/removal. Preserve genuine unknown/remote constraints. Domain selection has been attempted in held and causal sources. |
| Unrelated handler scans | Each event searches broadly across subscriptions before actual matching. | Indexed family/phase/source/spatial candidate selection; preserve the real matching calls and their original candidate-capture/order semantics. |
| Artificial sensory barriers and repeated root-cast handlers | The earlier batching study found global summoning cleanup forcing sensory reads for nonmember props, and root-only cast handlers treating recipient applications as additional casts. | Correct actual handler membership/root occurrence, rather than inserting another full refresh. Counterspell/Greater Invisibility occurrence semantics are correctness issues as well as work amplification. Source evidence belongs to the batching study; do not assume these defects remain in every later tree. |
| Passive material event explosion | Earlier Fireball attribution counted 196 ash, 68 blood-birth and four blood-growth versions out of 431. | The targeted batching plan explicitly records human-authorized aggregate material events and staged observations. Preserve required addressed values/causes without reinstating one four-phase lifecycle per inert material cell. Reconcile the actual event contract before porting. |
| Avoidable optical allocation | Prepared optical rays generated large temporary coordinate graphs and copied cached absolute routes. | The batching experiment translated existing immutable supercover offsets transiently instead of populating/copying absolute rays. Keep endpoints, exclusions and actual optical math; smaller allocations require an enclosing timing result before being called a speedup. |
| Discovery graph copies | Per-position/per-variant copying allocates rich action graphs. | Stable shared template/configuration plus isolated candidate state where the concrete interface permits it. Preserve mutable binding, hooks and retained continuation identity where required. Not the only discovery bottleneck. |
| Preview cache copies and discovery lifetime | The held player session serializes a cold Preview to budget it, copies it into the cache, copies it back to the consumer, and synchronously releases retained discovery graphs inside the operation. | Avoid redundant serialization/copy preparation where the actual contract permits; preserve independent mutable outputs and charge release at its real boundary. This is separate from candidate copying and wall enumeration. Source: `aoe-general-execution/dnd/player/session.py`, Preview/cache and `_operation` owners. |
| Chain Lightning secondary discovery repetition | The batching plan attributes repeated activity/HP/contact checks before distance rejection and across equivalent slot variants. | It proposed an exact conservative contact-distance broad phase and request-local raw secondary-option reuse, retaining real support/boundary/subjective checks and per-row index rebasing. This is a named earlier attempt, not a proven fix for all discovery or authority to cache arbitrary candidate verdicts. |
| Wall raster and continuation repetition | Repeated full bounding-box shell scans and repeated search for the first legal continuation witness. | Exact output-cell interval rasterization and original-order lazy witness enumeration; share a shell only across identical actual inputs. Held interval lowering has measured benefit; whole-request shell memo was rejected for retention cost. |
| Wall placement/propagation repetition | Repeated Tile membership, height, reach, targeting snapshots and provider calls across candidates. | Factor genuinely shared owned data access; retain actual traversal/callback semantics. Existing 107-call domain preparation was already reused in the held profile and is not the missing solution. |
| Per-audience topology preparation | Capture reconstructs source/lineage closure and normalized topology for multiple audiences. | Share unchanged operation-owned topology; keep audience admission, payload copies and knowledge separate. Held implementation exists; causal source has related ownership changes, not a blanket completed performance qualification. |
| Rich payload copying | Detached Events and nested payloads are copied at several boundaries. | Reuse genuinely stable producer-owned values while preserving independent mutable outputs and original hook points. Frozen outer objects do not prove nested immutability. Small-record tactics alone showed small gains. |
| Duplicate public-state calculation | Historically projection remembered state and application latest state both compose overlapping results. | One correctly normalized public transition per audience, adopted by application. Duration/correlated owner revisions precede ranking/joining, and empty sensory deltas retain negative evidence. Causal plan §17.9 records implementation and focused checks; do not report this as untouched. Complete cost benefit remains unqualified. |
| Retained history/control coupling | Required history can retain invocation graphs; alternative representations can add decode/reconstruction work. | Release invocation-only scheduling/preparation data at close; keep exact history identity and late children. Count real retaining roots, not every index reference as a duplicate payload. |
| Event-history readback for owned results | Resource, damage, turn witness, Fireball stage and movement provenance owners rediscover their own results. | Return/accumulate the specific accepted result at its owner. Some fixes exist in the spell worktree and Fireball source has advanced in causal; details below. |
| Full-path and failure-state gaps | Kernel-only numbers omit discovery/binding/publication/encoding/cleanup. A partial capture/projection failure can leave counters/checkpoints advanced. | Measure the actual requested boundary and preserve a consistent failure checkpoint without rerunning gameplay or hooks. Public validation alone does not prove earlier capture state was transactional. |

**7. Spell and lifecycle mapping**

| Family | Dominant identified seams and behavior that remains |
| --- | --- |
| Fireball / destructive AoE | Source identity reads, boundary/light/contact preparation, blocker/emitter/debris coupling, exact destruction results and successive breach stages. v9 reports six recipients, 187 damage and four destruction records. Later casts into a depleted two-target scene are not equivalent workloads. |
| Ice Storm | Ordered saves and damage, then `_finalize_aoe` installs the resolved terrain footprint. Required target work + actual cell contributions + demanded movement/field knowledge + output. Movement-cost changes alone do not require optical reconstruction. Hundreds of milliseconds are not justified by this ordering. |
| Sleet and clouds | Terrain, obscuration/hazards, exposed floor/carried/equipped flame dousing, concentration and removal. Saved Sleet cast/drop has 197 tile changes and 853/810 versions; six actual lights are doused. `target_count=0` does not mean no mechanics occurred, and does not qualify occupied entry/turn cases. Fog, Darkness, Cloudkill, Stinking Cloud and Incendiary Cloud retain their distinct rules. |
| Grease / Web / Spike Growth / Insect Plague | Shared field setup/teardown plus actual occupied appearance, entry, exit and turn rules. Web ignition/escape/collapse, Spike Growth every-entered-tile damage and real turn fences cannot be replaced by generic once-per-turn behavior. |
| Gust / Wind Wall | Handler construction and interaction tails cause extra refreshes. Actual forced movement keeps every step/collision/entry boundary. Historical Gust three-cast recomputations 42→6 retained the real pushes. |
| Ice/Stone/Force and other solid walls | Formation movement, coherent section placement, same section identities, later area membership, fractures and retirement. Historical Ice Wall 25→7 rebuilds is one workload's count improvement, not a universal seven-call contract. |
| Wall of Fire / Thorns | Irrelevant crossing-domain fallback plus optical/heat/terrain/contact rules. Held Wall of Fire ordinary triplets improved roughly 45–51 ms; no equivalent Thorns timing forecast is established. |
| Circle of Death / Sunburst / Chain Lightning / darts / rays | Subscription selection and repeated shared preparation around actual saves, attacks and conditions. Earlier reactions can affect later recipients. Parallelize genuinely independent accepted calculations; do not freeze every target at cast start. |
| Full Choices / wall Preview | Candidate representation, rasterization, continuation witnesses, placement/reach/Tile access and retained outputs. Discovery is a separate major slowdown; a fast cast does not close it. |

Concrete Ice Storm owners: [evocation finalization](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/dnd/spells/evocation.py:3559), [terrain cell owner](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/dnd/spatial/area_conditions.py:1382), [source and after-value capture](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/dnd/core/gridmap.py:2281). New debris areas are authored by [DestructionDebris](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/dnd/content/items/world_prop_builders.py:721). Separately admitted field activation must retain its own cancellation/observation boundary.

**8. Precise experiment map inside the held general-execution worktree**

All paths in this table are inside `/home/tommaso/.codex/worktrees/aoe-general-execution/dnd_engine`. These results belong to that experiment. The investigation document distinguishes kept source, proposals, ignored pilots and rejected paths.

| Attempt | Exact evidence location | Outcome / limit |
| --- | --- | --- |
| Shared owners, crossing domains and multi-spell sweep | `.runtime/performance-investigation-20261016/shared-owners/matrix-crossing-domain-v1-summary.json`; plan §14 in the architecture document. | 47 fresh-process spell samples; useful mechanism evidence, not full lifecycle/Choices/client qualification. |
| Gust installation-owner change | `.runtime/performance-investigation-20261016/shared-owners/gust-owner-baseline-ordinary-v1-owner.json` and `gust-owner-selected-ordinary-v1-owner.json`; investigation around line 3898. | Removed setup recomputation while preserving actual pushes. Does not predict all Wind Wall costs. |
| Crossing-domain correction | `.runtime/performance-investigation-20261016/shared-owners/crossing-domain-wall-fire-ordinary-v1.json` and corresponding cycles file. | Restored sparse solving where the crossing producer imposes no relevant constraint; preserve real global constraints. |
| Full discovery attribution | `.runtime/performance-investigation-20261016/shared-owners/finite-hazard-full-choices-ordinary.json`; investigation around line 4482 and `current-native-choices-profile-v1-33-choices.pstats`. | Ordinary Choices 33,033.85 ms. 73,243 represented wall candidates across 107 variants are not 73,243 legal actions. Dominant whole-action copy fallback was already removed. |
| Tile storage access lowering | `.runtime/performance-investigation-20261016/shared-owners/tile-storage-owner-ab-v1-summary.json`; investigation around line 4542. | Separate ordinary A/B about 32,075→26,639 ms, 16.95%. Shows storage access overhead, not permission to skip provider semantics. |
| Whole-request wall-shell memo | Investigation around lines 4618–4895; `native-wall-shell-input-census-v1-census.json` under `shared-owners/`. | Rejected: the sampled complete-key/order table retained about 1.02 million cell rows, 2.70 million nodes and 155 MB shallow bytes. More caching was not automatically an improvement. |
| Exact wall column-interval rasterization | `.runtime/performance-investigation-20261016/shared-owners/wall-interval-owner-ab-v2-summary.json`. | Kept after the recorded source/math checks. Ordinary Choices medians 26,556.41→24,304.97 ms, 8.48%. No Fireball cast speedup demonstrated. Separate from the Tile A/B; do not add percentages. |
| Grouped sensory scalar representation with ordinary copying and old-wire lowering | `.runtime/performance-investigation-20261016/shared-owners/compact-sensory-cells-v2.json`; investigation around line 4947. | Rejected for production migration in that form. Faster folds were outweighed by grouping, copying and wire reconstruction. |
| Operation-owned capture sources | Investigation around line 5000; source `dnd/player/capture.py` and `dnd/player/application.py`. | Shared closure/versions/objective rows across an actual operation while keeping independent audience copies. Not interchangeable with causal-worktree source or a universal cursor-based cache. |
| Closed mechanics / requirements programs and native query migration | Investigation sections “Requirements are independent from consequence/geometry authority” and “Reduced query admission and call order”. | Experimental architecture. The production causal plan explicitly says not to import the closed interpreter; shared math/data may be considered individually. |

The discovery profile's overlapping inclusive counts include 244,084 placement checks, 280,575 reach checks, 2.67 million propagation queries, 316,640 wall-shell calls and 46,660 continuation-witness calls. Domain preparation already ran only 107 times/about 97.87 ms. Roughly 12.24 million Pydantic private-attribute reads were attributed mainly to Tile storage access. These are diagnostic attribution, not independent time budgets that can be added.

The rejected grouped-copy experiment reported folds 87.22→75.38 ms but per-arm partial totals 137.45→143.53 ms over two cast/drop pairs plus restore. Constructor validation was untimed and individual rows were separate medians. Memory-only experiments retained the original roots, so their byte/node reductions were representation ceilings, not realized runtime savings. Do not revive either result as a completed performance win.

**9. Owner readbacks and separate correctness findings**

The [spell worktree report](/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine/agent_docs/OWNED_STATE_READBACK_FIXES_AND_REWORK_REPORT_2026-10-16.md) provides four local examples worth reusing selectively: item-owned spend/recharge revision, Guardian's exact completed applied-damage result, fall's exact applied result, and Harm's exact completed incoming result. The item revision is captured before declaration and advances on accepted commitment, detecting spend→recharge even if the final quantity is equal. Existing exact-lineage idempotence remains.

Three broader findings were recorded separately: encounter-owned turn identity witnesses, Fireball latest-version access plus stage-owned destruction results, and movement/landing operation provenance instead of ancestry reconstruction. The causal source inspected during this review already uses `get_latest_event_version` and `collect_destruction_results` in Fireball. Do not tell a successor those two calls are still absent. Their complete semantic/performance qualification, turn-publication integration and movement-provenance status remain separate questions.

Turn witnesses use the exact `turn_execution_id` and already recorded eligible identity grants. Death/departure must not restore location or grant party-wide knowledge. Movement provenance belongs to the exact nested admitted/committed movement operation; a global last-step field or present-day FOV cannot substitute.

Requested/raw damage, final incoming damage, optional applied damage and normal-HP loss are different results. A fully absorbed fall may have no applied fact. A reported Harm counterexample grants 10 temporary HP during admission of a 28-point packet and produces completed facts of 18 while raw resolution says 28. The admission-time temporary-HP bookkeeping is a separate correctness defect; do not silently change it while claiming a pure speed/readback fix.

The external report has its own schema lineage and four failing Globe propagation fixtures. Neither its passing counts nor its failures establish this causal worktree's status. Reconcile actual schema/SDK/cold inputs when integration is authorized; copying a version number or digest does not establish compatibility.

**10. Why the previous plan failed as a performance strategy**

The plan correctly identified many problems and explicitly warned against per-lookup tasks, repeated preparation and overhead exceeding saved work. Nevertheless, the implementation sequence centered on service/routing infrastructure, universal migration coverage and concurrency before demonstrating removal of dominant read-time products. Wrapping existing bodies preserved substantial old work and added control cost. Missing native selections then blocked loaded runs, turning the effort into a wide migration-repair exercise.

The review process accepted coverage tables, framework milestones and correctness gates as substitutes for a cost argument. Small owner fixes were sometimes discussed as though they explained the large observer costs. Faster held experiments and current production-based runs were too easy to conflate. The repair is to require an explicit eliminated term and a matching complete-operation result, not another inventory of future mechanisms.

Some progress must be retained honestly: early Sleet cost-only routing removed a severe pathological cost; indexing, optical/crossing work, coupled state installation and direct Fireball results exist; causal §17.9 records normalized public-transition and startup capture work. Startup errors from older attempts are historical, not proof the latest checkout cannot load. Focused tests are evidence of behavior on their own source, not latency qualification, and overlapping test totals must not be added.

**11. The theoretical correction and how to falsify it**

The proposed direction uses existing component owners to maintain physical contribution data, small pending sets of changed addresses/channels, direct prerequisites for demanded values, and ordinary ordered mechanics. Substantial independent calculations can use coarse fork/join. Movement/terrain calculation does not wait for unrelated lighting or HUD work, while every actual step still joins observations its callbacks/history require. Perception joins the geometry/light it actually needs. Coupled accepted contributions are coherent before required callouts. Actual mechanical child writes finish before their dependent caller continues.

This is an alternative under review, not authorization to bypass the sole execution path or replace all runtime storage. Its central claim is narrow: unchanged owned inputs permit a cheap read. Its proof fails for untracked input writes, mutable result aliases, effectful input acquisition or reordered callbacks. Keep such procedures at their real execution points; do not build a universal purity-certification framework to avoid that limitation.

Current perception can be reused while occurrence-local memory/evidence still advances. A flash followed by darkness must retain what was learned. Automatic engine observation, direct API return/raw-senses freshness and every required movement boundary are consumers even without an explicit rule getter.

Charge cold builds, maintenance, conservative false-positive invalidations, fanout, memory, copying and output. With R reads, S old discovery cost/read, h cheap metadata cost/read, U writes, m maintenance/write, I added initialization and F false-positive rebuild cost, the proposed saving requires `R * (S - h) > U * m + I + F`, holding necessary calculations equal. Parallelism separately shortens independent remaining work; it does not excuse multiplying it first.

Reject a purported implementation of this theory if unchanged reads still traverse the complete provider graph, each write scans every potential observer/candidate, a movement-only update causes unrelated optical work, callback order or candidate isolation changes, evidence is reconstructed from the final world, or reducing one component worsens the enclosing operation.

**12. What the successor should establish next**

Use the worktree/evidence map before choosing source to change. Preserve ongoing dirty work; do not reset, merge experiments or recreate the four foreign fixes on the strength of this handoff. The next implementation direction must reconcile the existing causal plan with the human's later first-principles critique.

For each chosen correction, state the repeated work it removes, its owning data/function, the operations still required and the cost introduced. Ice Storm's cell/source loop, Fireball's physical-input/control amplification and Sleet's lifecycle/publication are concrete execution priorities; discovery has its own much larger enumeration/input-access problem. A new abstraction without an eliminated term is not progress.

Use existing loaded fixtures and meaningful behavioral checks after an actual change, then compare ordinary complete-operation timings on matched source/input semantics. Keep instrumented attribution separate. Include first destructive casts, real drop/expiry, occupied fields, intermediate observations, independent audiences and required cold replay. Expand checks when a new failure or concern warrants it; do not spend hours repeating unchanged matrices or checksum ceremonies. Report the remaining dominant cost and whether the latency target is actually met.

The handoff's complete supporting theory is [ENGINE_COMPUTATION_THEORY_2026-10-16.md](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/agent_docs/ENGINE_COMPUTATION_THEORY_2026-10-16.md). The active implementation's original inventory remains [ENGINE_QUERY_DISPATCH_MIGRATION_INVENTORY_2026-10-16.md](/home/tommaso/.codex/worktrees/causal-execution/dnd_engine/agent_docs/plans/ENGINE_QUERY_DISPATCH_MIGRATION_INVENTORY_2026-10-16.md); it is a coverage aid, not evidence of speed.
