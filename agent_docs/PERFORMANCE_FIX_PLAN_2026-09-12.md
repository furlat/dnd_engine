# Performance and design repair plan — September 12, 2026

Status: **implementation authorized** after the reviewed plan and current timing
baseline. The September 12 user instruction to proceed supersedes the earlier
implementation stop. First unit: ordinary startup/import and media ownership,
with bounded native query duplication work prepared alongside it. Measure serially
after focused behavior checks; record results below as units are validated.

**Implementation checkpoint:** [measured results](PERFORMANCE_REPAIR_RESULTS_2026-09-12.md).
Ordinary-play audit removal, passive public import ownership, session/requested
media loading, native query/AI value duplication, the world-diff guard and batch
source indexing are implemented and checked. Whole saved playback is 3.493s
versus 8.404s. The fourth checkpoint reduces 4,096-cell construction from 1.412s
to 0.164s and encounter setup from 0.424s to 0.215s. Its initial native activity
measurement is 3.565s versus the prior 3.308s; the results preserve that difference
and an alternating comparison. Native imports, private actor-history refolding
and the remaining content-identity work are still open as bounded below. This is
not completion of every numbered phase.

### Current authorized unit: ordinary terrain and remaining catalog obligations

The first pass is checkpointed as `13f412d` (native) and `18a2163` (public
playback/media and its audit/results). The user authorized continuing recovery.

The 4,096-cell construction profile after imports records 114,688 Pydantic
constructions, including 16,384 ModifiableValue graphs. Its instrumented time is
2.533s; the uninstrumented comparator remains 1.412s. The nested profile costs
are attribution, not promised savings.

The reviewed Tile implementation keeps its four current movement-cost fields,
each holding either its authored integer or its existing ModifiableValue.
Reading a cost never creates a graph. An explicit mutation entry promotes only
the requested movement mode, records it in the existing Tile.values collection,
and preserves current source/context/target ownership. The three existing
zero-cost caps (walking, swimming, burrowing) remain; flying keeps its distinct
behavior. Once created, a graph remains until tile disposal so conditions can
remove their retained modifier UUIDs. There is no parallel scalar/graph state,
implicit promotion property, lazy proxy or new modifier implementation.

Inputs/outputs are the current authored floor/water/wall costs, spatial terrain
effects, removals, replacement and path queries. Expected results are unchanged
evaluated costs and world events, independent neighboring tiles/modes, valid
condition removal and no dangling owned graphs after legitimate replacement.
Tests that require every untouched tile to allocate graphs must request an
actual mutation or express the relevant path/lifetime result instead.

The separate catalog review found that native binding uses explicit providers
and actual effects, while `condition_effect_population` predicts effects for
admission/catalog metadata and replaces authored dependency edges. The mandatory
catalog is removed. Authored dependencies, condition lifecycle and existing
checks for explicitly supplied optional profiles remain. Removing the secondary
prediction obligation is not a claim that it accounts for the native import
time; most executable classes are loaded independently. No replacement metadata
generator is planned.

**Anti-OOP reviewer:** `animation_contract` has traced Tile query/mutation,
condition UUID removal, world after-values and replacement ownership.
**Anti-slop reviewer:** `recorded_gallery` independently reviews the Tile proposal
and approves the actual Tile/catalog diffs. `lifecycle_source_review` independently
approved the catalog removal and studies the source-ordered
admission fold separately; that study does not authorize adding a persistent
capture owner before its concrete input/output design is reviewed.

Root keeps timings serial, compares construction and the same native turns,
and checks real spatial/terrain behavior before committing this unit. Renderer
or spell changes are outside it.

**Validation result:** 186 distinct terrain cases and six native AI cases pass;
eight current metadata/provider/True Seeing cases pass. Independent reviewers
approved the actual representation and catalog diffs. The results record keeps
the initial fixture failures, minimal fixture corrections, inherited typecheck
limitations and exact timing conditions. No persistent admission fold has been
implemented as part of this unit.

The objective is a fast game with understandable ownership. The failure was
allowing code and tests to justify more machinery without asking what gameplay
needed. This plan therefore removes unnecessary obligations and repeated work
before considering different representations. It does not turn all audit hits
into an automatic backlog, restore the old server, or propose a new rules engine.

Read the [audit](audits/CODEBASE_MACHINERY_AUDIT_2026-09-12.md) for source/caller
proof and [current baseline](PERFORMANCE_BASELINE_2026-09-12.md) for measurements.
The starting point includes the uncommitted source-audit, asset-loader, native
query/value and immutable-item-copy edits. They remain subject to review.

## First implementation unit and order

The first unit is **ordinary startup and media ownership**: phases 1 and 2, covering
import separation and repeated asset loading. Current timings place
4.65s native imports, 3.99s saved-render imports and 2.36s actor loading ahead of
small frame checks. Review and measure that concrete change before expanding it.

Then phase 3's native query/allocation and AI projection work:
controller advancement costs about 3.07s in the current turn workload. Capture
and root-compilation work (phases 4/5) follows; measure history scaling before
implementing a persistent fold. The separate 4,096-tile case establishes a real
construction issue for phase 6, while the actual encounter setup is 0.47s.
Phase 7's identity/ownership decisions are separately bounded design work, not a
mandatory broad redesign before each earlier fix can land.

The numbered sections group owners and acceptance criteria; the execution order
above follows the current measurements. They are not seven compulsory projects
that all have to finish before any gameplay work can resume.

## 0. Establish the actual starting point — this session

Measure the current working tree, serially, in fresh processes. Keep native work
separate from public capture/reduction and rendering saved events. Use ordinary
elapsed timers and small counts/outcomes, with no diagnostic hashes, source
fingerprints, frame digests, source verification, asset audit or mandatory video
export. Leave current game behavior intact so measurements include its remaining
costs instead of silently bypassing them.

Use three repetitions of each fixed workload. Keep raw timings and runnable
local scripts, report median/range, and preserve failed diagnostic attempts as
failed attempts rather than performance results. Existing intrinsic game checks
remain part of the measured implementation; the harness adds no attestation.
Do not run agent tests, profiles or other benchmarks concurrently.

This is a baseline, not a benchmark framework or acceptance score. A small scene
cannot establish performance of every condition, map or long encounter. Report
that limit plainly. After each repair, rerun the relevant unchanged workload and
compare stage cost as well as actual workload counts. Do not add the stage
medians together and label that a measured process total.

## 1. Finish removal of ordinary-play audit machinery

**Result:** starting the built-in game reads and constructs the content/assets it
uses. It does not authenticate locally shipped source, replay a historical
catalog audit, or enter external-import rollback when importing no external code.

**Import boundary:** split the common painter/sampler from old diagnostic
producers and reference runners in `app.py`, `__main__.py` and gallery case
composition. A saved-input renderer should import its schemas, data and drawing
owners, not the full native fixture catalog. Keep an ordinary import DAG; no
late imports, TYPE_CHECKING concealment, dynamic registry or import-time schema
cache. The remaining import profile attributes substantial cost to eager
Pydantic class construction; distinguish genuinely needed native value models
from cold catalog/server metadata dragged through composition before choosing a
change. Do not mass-convert every Pydantic class or defer all model building.

Concrete work:

- Finish the pending built-in source walk/hash removal and its dead field
  consumers. Do not replace it with cached hashes, generated source manifests,
  memoized schema digests or deferred imports.
- In `dnd/content_system/pack_loader.py`, give the built-in-only path direct
  registry construction. Preserve `builder.freeze`'s actual construction role;
  omit external-pack module snapshots, global runtime snapshots, mutation-token
  comparisons, rollback and import-cache invalidation when there are no packs.
- In `dnd/items/authored_variant_inventory.py`, retain the category/layer facts
  used by `game/animation_data.py`; remove the import-time self-digest,
  historical collision-evidence recomputation and fixed source census. Preserve
  actual lookup identity. No replacement evidence ledger.
- Remove exact-size import gates in `builtin_inventory.py` and `srd_roster.py`.
  Content IDs and unambiguous builders remain meaningful; 312/28 are not rules.
- Review the pending `assets.py`/`animation_data.py` edits with the remaining
  `animation_draw.py` path. Decode/load shipped data during play. Existing
  importers already own authored source conversion; discard duplicated checks
  in the new offline validator rather than assuming every removed runtime check
  deserves a new permanent tool. Keep an explicit authoring check only when it
  has a concrete uncovered use.

**Validation:** actual direct premades and a monster compose; discovered actions
and a provider-owned condition emit their normal events; equipped layer mappings
load; saved public input decodes/reduces without native production. Reuse those
behavior tests. Do not make historical counts/digests an acceptance gate.
Measure native/presentation imports, installation and asset preparation again.

**Bound:** repairing old external-pack lifecycle internals or restoring missing
server modules is not part of this unit. Existing generated SDK field edits are
a compatibility cleanup to review, not a reason to resurrect its old backend.

## 2. Give media and diagnostic work the right lifetime

**Result:** each required sprite row is decoded once per loaded presentation
session, and ordinary play does not accumulate test evidence per frame.

- `animation_draw.py`, `scene.py`, `choreography_draw.py`: reuse the existing
  loaded body-row mapping across scene admission, equipment changes and action
  media. Load only missing rows using the existing rig/clip/category/facing-row
  identity, scoped to one AnimationData/resource set and one Pygame session.
  Per-head appearances remain historical; tint/condition compositing uses working
  pixel copies. No process-global media cache or content fingerprint.
  New gear and action media can require additional rows; actor ID
  alone is not a valid media identity. No new asset manager or parallel cache.
- Request scene standing/dead poses and the actual clips/loadouts of each next
  complete bound head; do not preload every clip the rig can support. Motion and
  choreography's existing typed cues own the requests. The existing world
  SurfaceCache likewise decodes canonical rasters when requested. Report first
  view and whole-process cost so moving decoding into first use cannot disguise
  it as a performance gain.
- `app.py` and `encounter_play.py`: explicit diagnostic callers own expected/
  actual evidence collection and optional frame history. Normal play keeps
  command depth/identity/bounds needed for drawing and labels, but does not build
  duplicate proof sets or retain a GameFrame for every interactive frame.
- `motion.py` and `playback_frame.py`: use one sample of the active reaction at
  its local time. Preserve completed reactions' retained vitals; they represent
  previous consequences, not duplicates of the active sample.
- Resolve the same displayed actor list once per frame where possible. Build
  immutable catalog lookup tables once alongside existing animation data;
  changing equipment/conditions still takes effect at its authored event time.

**Validation:** equip change followed by melee/ranged attacks; entry into sight
with previously unseen gear; nonlethal/lethal/paralyzing opportunity attacks;
paused playback and corpse position; representative fixed and modular rigs.
Use existing saved packets and sampler/pixel expectations. The timing command
never exports or hashes a video. A targeted visual review can remain a separate
optional diagnostic when the affected behavior is genuinely visual.

**Timing:** first media preparation, a repeated request for already loaded rows,
head preparation, first view, steady sampling/drawing and normal frame-retention
behavior. Repeated-load timing must request the same rows; do not disguise new
asset work as a failed reuse result. The current doorway render is a small-scene
baseline, not a VFX benchmark.

## 3. Remove native query duplication and unnecessary AI projection

**Result:** unchanged native decisions and perception facts are produced with
less construction and copying at the existing owners.

- `dnd/ai/runtime/subjective_projection.py`: only construct a remembered fallback
  when the freshly projected entity/object/tile is absent. The current eager
  `setdefault` argument constructs and discards copies for present keys.
- `dnd/core/gridmap.py` and `base_tiles.py`: boundary route/membership queries
  should read the directed bands actually needed, without constructing whole
  edge views, sorting bands and then discarding that order, or building a
  dictionary from an immediately temporary tuple. Keep directional and height
  semantics. Review the pending validation-only key allocation at the public
  boundary instead of preserving it automatically.
- `base_block.py`: reuse the same field discovery through one construction pass
  instead of scanning it again after propagating source ownership.
- `values.py`: retain the narrow removal of irrelevant outgoing-bucket work on
  incoming values only if its actual contribution/removal semantics hold.
- `blocks/sensory.py` and current capture adapters: share immutable contact/item
  leaves where proven immutable. Keep mutable snapshot maps/sets detached;
  mutable `SenseMode` is a different case.

**Validation:** directed door/contact reach across both channels and height
bands; actual doorway crossing and reacquisition from both participants;
modifier contribution and removal; independent before/latest values. Existing
`test_world_geometry_contract`, `test_visible_movement`,
`test_modifiable_value_semantics` and public projection cases cover these owners.
Add a missing observable case only where existing coverage is insufficient.
No arbitrary allocation-failure/corruption scenario becomes a new game contract.

**Timing:** same native turns, discovery, capture and projection. Record each
removal's scale honestly. Small field checks cannot be presented as solving the
larger world representation or full-world AI projection cost.

### Larger AI adaptation at the same existing owners

For native AI, follow the current movement continuation predicate to the exact
new-hostile, new-hazard and actor-state facts it reads. Reuse/narrow the existing
projection for that check at each committed step. Keep the native per-step
interruption decision and required observation state advancement. The existing `NativeAIStateProjector._world`
actually retains known/remembered facts and advances the observation cursor;
keep that advancement on CONTINUE as well as INTERRUPT, including briefly seen
ordinary tiles/objects that do not trigger a stop. Reuse existing entity/object/
tile projection owners while separating unrelated DTO construction. Do not create another
sensory ledger or change who can perceive what.

For engine→AI DTO adapters, enumerate actual primitive differences (UUID/string,
mutable/immutable collections, exposure records) and construct the owned values
directly where JSON dump/revalidation is merely an internal bridge. A shared
leaf type is appropriate only when both boundaries already mean the same thing.
No reflective converter, unchecked arbitrary model copying or replacement policy
schema system. Existing GC suspension/caches are reassessed only if their cost
or necessity is implicated by the changed allocation path.

**Validation:** real AI chooses available actions and stops a movement at the
same material newly perceived change. Both observers retain the same public
consequences. Saved lineage reaction ordering, pause/seek and terminal state
remain unchanged. **Timing:** native controller/discovery, head binding and
saved-frame sampling, separately.

## 4. Make capture and projection proportional to incoming facts

**Result:** existing causal state is processed once at its proper point; a new
root does not refold all prior history for every observer.

Start with owner-local work:

- In `_project_nodes`/`apply_world_fact`, derive world differences only after
  actual world changes or this observer's sensory changes. Keep the existing
  rule that a sensory child can reflect its spatial parent's already-committed
  after-value before the parent completion record. Do not wait until root end,
  skip brief visibility, or add a new dirty-event bus.
- In `capture_history`, share source traversal/index work across requested roots
  and perspectives from the same native experiment. A root remains its complete
  native lineage; an operation's cursor range or callback batch is not a new
  animation unit.
- In `capture_lineage`, use the EventQueue's existing lineage/version ownership
  instead of rebuilding an all-history latest-version dictionary each call.
  `get_event_index` currently scans history; calling it once per child is not a
  solution. Determine source indexes once in the existing capture operation.

Then address the necessary retained fold explicitly, after measuring scaling.
Before implementing persistence, establish one source-ordered fold of private
births/after-values and separate per-observer contact/admission progress. At each
actual admission event, retain its detached actor/contact value with that event's
existing identity/index. Completed roots select these recorded admission facts;
root completion order never controls fold order, and a later actor value or
known-ID set cannot reconstruct an earlier admission. Fold all relevant native
source events, including roots that produce no public packet. A late observer's
contact state begins at its native initializer while actor values include prior
recorded private updates. Live and recorded-batch paths reuse this fold with
EventQueue generation/reset ownership. Retain admission facts, not a full state
snapshot per event. No additional journal, event queue, callbacks, reconnect
protocol or rules-state authority. Public `ProjectionState.actors` is not the
private source history.

Before changing that fold, write a short input/output example showing an unseen
gear/HP change followed by brief doorway acquisition and later reacquisition,
from both observers, plus the existing overlapping equipment roots. This establishes exactly which state must exist at each
admission; it is the design decision, not a speculative failure checklist.
If the existing owner can retain the needed accumulator directly, do that
instead of introducing a generalized incremental-reduction framework.

**Source review retained for the next fold implementation (September 12):**

- In the existing visibility history, the subject starts observed at `(8, 7)`
  with 40 HP and a shortsword, leaves sight, equips a dagger and takes seven
  damage while unseen, then is reacquired with 33 HP and the dagger. That
  admission belongs to its actual sensory child. The subject's own view receives
  its intervening facts. In the doorway route `(8, 4)` → `(8, 10)`, acquisition
  occurs at `(8, 6)` and is lost after `(8, 8)` within one complete Move.
- The capture-growth equipment operation produces four independent roots with
  overlapping source intervals. Current known-actor filtering progresses in
  returned-root order; private actor/contact values must still fold in raw
  source order. A source-order known-ID set cannot replace both responsibilities.
- Existing per-row order is birth, own sensory/contact update, eligible
  admission snapshot, then actor after-value. Selected nonterminal versions can
  carry an admission; completion-only folding would silently drop those.
- A prospective caller-owned fold retains the current private actor aggregate,
  current contacts/position per tracked observer and source cursor. Sparse
  candidate facts distinguish first eligibility within a root from genuine
  contact reacquisition: reacquisitions survive even for remembered actors.
  Complete roots select candidates in native version order using their current
  known set. This must not become full actor snapshots at every event.
- Ownership is the native session's EventQueue generation. Advance all relevant
  source rows, even for roots that yield no public packet, and discard with the
  session. No reset callback, engine import of game code or extra event ledger.
  A newly introduced observer can require one initialization replay; the current
  private aggregate is not a public initializer. Isolated historical captures
  still need a defined path and cannot borrow today's hidden state.

This is a reviewed direction, not an implemented accumulator or a proven final
API. The next edit must make its sparse selection and initialization concrete
against these existing histories before replacing the current pure capture.

**Validation:** paired player packets preserve permitted facts, event identities,
source ordering, complete ancestry and acquisition-time state; hidden inventory
and unseen updates remain private. Include late observer initialization, one/two
visible stretches during a walk, a door state remembered while unseen, condition
reveal and lethal movement interruption. Existing visibility/concealment/public
replay cases are the references. Compare values/bytes directly where relevant;
no source hashes or fingerprints. Run no native game while replaying saved input.

**Timing:** capture/project/reduce the same native work; also measure fixed
prefixes of a longer recorded source history to expose repeated full-history
folding. Add this scaling case when touching the fold, not a new all-purpose
benchmark collection. Track source rows visited alongside received roots, rather
than asserting private function call order.

## 5. Reuse root-local compilation results

For choreography, reuse an already-computed successor and repeated prefix/subtree
results within one root compilation. Distinct child entry states remain distinct;
using final state everywhere would break movement reactions. Root-local data
suffices; no global snapshot store, replay cache or alternate scheduler.

**Validation:** actual reaction and equipment entry states, pause/seek and final
state from saved complete roots. **Timing:** compile the same roots and sample
the same frames; do not substitute the final state for intermediate child states.

## 6. Address terrain construction as bounded representation work

**Implemented and checked in checkpoint four:** compact authored costs with
explicit, existing modifier ownership on actual edits. The current rectangle
costs 0.164s; four-actor setup costs 0.215s. The rationale and boundaries below
retain the original decision context.

At the starting baseline, the 4,096-cell rectangle cost 1.64s to construct and
the actual four-actor encounter setup cost 0.47s. Address this representation if it remains material
after direct query/allocation cleanup. Multi-second imports are handled at their
own owners and do not automatically justify a Tile redesign. Construction work
cannot be declared solved merely because a few cheap validators disappeared.

**Terrain representation:** untouched cells should not need four full registered
modifier graphs just to hold normal traversal costs. Preserve the current Tile
and modifier owners while evaluating compact base costs plus independently owned
mutable contributions where the actual terrain uses them. Enumerate the current
terrain consumers before selecting a representation: walking/swimming/burrowing,
constraints, condition contribution/removal, destination-priced paths and tile
replacement. Do not implement shared mutable defaults or hide the same cost
behind a new general lazy proxy framework. The final representation needs a
bounded design review because it changes ownership, not because every micro-fix
needs permission.

**Validation:** unaffected sibling tiles, distinct modes, water/passability,
actual area-condition add/update/remove, destination costs, replacement with
live references and complete world events. Adapt tests that merely count eager
graph objects; preserve actual lifetime and path semantics. Reuse
`test_spatial_conditions` and `test_world_modification` where they cover these
behaviors. **Timing:** same 4,096-cell rectangle and actual four-actor setup,
plus native turn queries, so cheap construction cannot hide more expensive play.

## 7. Consolidate content identity and internal admission

Treat changes to installed identity and mutable recipe ownership as explicit,
bounded design decisions; do not bundle them into local duplicate-call removals.
Separate the useful content contract from authentication layers inherited with
it. Stable behavior/provider IDs, authored construction values and public
appearance/active equipment facts remain. Renderer descriptors should not force
replacement of a mechanical content set merely because their cosmetics changed.

- Reduce repeated recipe verification/reconstruction across resolution,
  materialization and binding. Choose the owned representation and actual input
  boundary first; do not retain a mutable parameter graph solely because
  repeated hashes can later detect mutation.
- Bind already-authored descriptor values without repeated dump/construct/
  revalidate passes. Exact icon mappings remain simple data.
- Decide the current consumer of the parallel condition-effect profile catalog.
  It currently supplies cold dependency/catalog metadata and does not execute
  gameplay. Remove it from mandatory game admission if only tooling needs it;
  do not replace event outcomes with its predictions or maintain a second rule
  executor. Do not create a new metadata generator simply to keep every old row.
  **Completed in checkpoint four:** mandatory population/census removed;
  authored dependencies/lifecycle and optional explicit-profile checks remain.
- Remove the orphaned installed-creature adapter and classify retained durable
  server models as outside current game composition. This does not authorize
  broad server-file deletion or a transport migration.

**Validation:** actual factory/behavior/provider resolution, direct character
composition, a condition granted by a spell/item, expected public appearance
and saved event replay. Keep malformed external-input checks at a real boundary;
do not preserve every internal self-authentication exception as a requirement.
Measure imports/materialization; report structural reductions even when their
runtime savings are small, without billing them as the main bottleneck.

## Testing and review are part of each unit

Read `HOW_TO_TEST.md`. Move the session-autouse content bootstrap out of tests
that only exercise passive data, decoding or rendering. Make native-content
setup explicit for tests that actually need it, using the existing fixture
owner rather than a second test runtime. This is test coupling cleanup alongside
its affected cases, not a rewrite of hundreds of tests for uniformity.

Historical plan/source hashes and fixed inventory counts belong to their stated
one-time evidence purpose; do not let them block a legitimate replacement. Keep
architecture tests for explicit import policies, and behavior tests for actual
rules, visibility, events and playback. Byte equality can check saved output;
it does not require hashing source or every frame. No complete gallery
regeneration is required for an unrelated native query or boot change.

Each implementation unit has two named reviews:

- **Anti-slop reviewer:** checks why the work exists, whether the before/after
  workload and behavior remain comparable, and whether the change removes an
  unnecessary obligation instead of making it more elaborate. Challenges tests
  that merely freeze the old mechanism and unsupported claimed savings.
- **Anti-OOP reviewer:** checks existing owner boundaries, passive ECS data and
  import direction; looks for duplicate queues, generic managers, global caches,
  parallel sensory state and new lifecycle protocols. Preserves the user's
  complete-lineage and independent-clock design.

Reviewers first examine the concrete problem independently, then review the
change. Agreement is evidence about their checked claims, not proof of global
correctness. Root owns serial timing and reports purpose removed, behavior kept,
stage improvement and remaining cost. Reconcile accepted pending edits and
commit small coherent units after their checks. Do not combine the whole audit
into one enormous patch.

## Deliberately outside this repair sequence

The audit found old source hashing, layered journals and repeated serialization
in retained remote AI/server/SDK code. They must not be imported as ready-made
infrastructure for the current game. Repairing all fifteen stale server module
targets, rebuilding durable character services, changing connector wire contracts,
a global constructor-registration redesign, or rewriting preview caches is not
required to remove the demonstrated active costs. Track those findings in the
audit until their actual product path is selected; do not make them prerequisites
for resuming gameplay development.

Nor is this a spell/VFX authoring unit. Preserve Studio JSON and rig mappings.
Use shared gameplay cases to validate changes; do not expand into individual
spell implementations to keep a performance session busy.

## Checkpoints and return to gameplay work

At the first checkpoint, ordinary startup should no longer perform the selected
source/asset self-audits, render imports should avoid unrelated native fixture
owners, and already-loaded body rows should be reused. Existing behavior checks
and the same serial baseline establish what changed. Report the remaining
native/AI/world cost explicitly and select the next bounded unit from the
measured owners above.

Broader capture persistence, terrain representation and content-identity work
are not automatic prerequisites for all gameplay development. Their readiness
must be decided from the actual workload and current contracts. Do not quietly
wave away a large active bottleneck, but do not replace the previous slop with
an endless perfection project either. A remaining design decision is named and
reviewable; it is not a license to implement speculative infrastructure.

The original request produced this plan and its baseline; subsequent user
instructions authorized implementation and the next measured recovery units.
No new VFX work, retired-server restoration or repository skill is part of them.

## Independent plan review

The anti-slop and anti-OOP reviewers both accepted the direction with concrete
amendments, incorporated here: move import/media repairs earlier, prioritize
measured native controller work over capture persistence, keep admission fold
order separate from root completion order, preserve AI memory advancement on
continued movement, scope media reuse to one resource/session owner, distinguish
large-map construction from encounter setup, and bound the exit criteria so all
seven sections do not become an obligatory rewrite. Native timing repetitions'
HP variation is documented in the baseline; equal counts are not a proof of
semantic equivalence. Reviewers performed source/document work only while root
ran all timing serially.
