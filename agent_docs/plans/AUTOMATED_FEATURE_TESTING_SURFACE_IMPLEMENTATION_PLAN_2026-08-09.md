# Automated Feature Testing Surface Implementation Plan

**Status:** DRAFT — INDEPENDENT PLAN REVIEW REQUIRED

**Date:** 2026-08-09

**Scope:** engine + server + generated TypeScript SDK + NeuroClient test architecture

**Implementation authorization:** not granted by this document

**Primary doctrine:** the attached *How to Test* document; feature boundaries,
data-driven checks, explicit observability, layered integrated tests, and owned
external processes

**Immediate motivation:** the canonical player journey could create a game but
could not bootstrap it, while the maintained green gates did not execute that
real journey

## 1. Objective

Create one durable automated testing surface that can prove the product works
without a model or person manually clicking it.

The completed surface must make this statement executable:

> Starting from a clean local profile, the product truthfully blocks a player
> who has no character; after the player creates a character, the canonical UI
> can create a game through the real server, join the resulting session,
> bootstrap the subjective SDK, activate the encounter, render the playable
> scene, execute the canonical state-changing Move through the mounted action
> bar and world target, survive recovery boundaries, and finish or replay the
> game.

That is a feature claim. It must not be inferred from build success, source
searches, mocked fetch handlers, directly constructed frontend stores, manual
browser operation, or independent green tests for the pieces.

The new surface also needs fast, data-driven integrated checks below the full
process boundary. A developer changing an engine rule, server contract, SDK
decoder, or frontend presenter must get a useful failure at the nearest public
layer without booting the whole product. The slow canonical browser journey is
the final product proof, not the only test.

## 2. Why the current surface is insufficient

The existing repository contains substantial semantic coverage. It is not an
absence-of-tests problem. It is an ownership and composition problem.

At the planning cutoff:

- the engine repository has hundreds of focused pytest files, including 204
  files under `tests/manual`, but no single maintained runner describes the
  canonical product journeys as reusable input/output data;
- NeuroClient has more than eighty scripts which launch Chromium, while the
  package scripts divide them across `check`, `check:browser`, `live:check`,
  `hosted:check`, and several one-off commands;
- many browser scripts import production modules directly or inject a store,
  journal, transport, clock, or fake response. Those are useful layer tests,
  but they cannot authenticate the real process topology;
- some scripts intercept application routes. A route-intercepted browser test
  may test the UI layer, but it cannot support a server/SDK/product claim;
- several browser scripts rely on `waitForTimeout` or short sleeps rather than
  an owned causal completion signal;
- real-process scripts commonly assume an externally started backend or Vite
  server. Passing therefore depends on invisible ambient state;
- the default build previously passed only when another task happened to own a
  Vite process, illustrating that the command graph itself was not the tested
  artifact;
- the canonical game-creation tests mocked or bypassed the boundary that later
  failed: prepared encounter source adoption and bootstrap HTTP decoding;
- an empty persistent profile silently selected an authored observer/AI roster,
  so the UI could report a ready game that did not satisfy the player-product
  invariant;
- acceptance relied on many green sub-seams without one automatic test proving
  their composition.

The correction must preserve valuable focused semantics while ending the
practice of treating a source scan, a fake fetch, or a manually supplied
service as product evidence.

## 3. Testing doctrine translated into repository rules

### 3.1 Test features, not implementation functions

A feature case describes:

- the starting world/profile;
- the input visible to a public consumer;
- user or protocol actions at that public boundary;
- observable product results;
- optional named diagnostic evidence explaining why the result occurred.

A case must remain useful if the implementation behind the same public
boundary is replaced. Direct tests of pure algorithms remain allowed where the
algorithm itself is a public engine rule, but they do not substitute for the
feature case that consumes the rule.

### 3.2 One `check` owner per boundary

Do not let every test assemble the application differently. Each layer gets
one maintained runner with an intentionally small adapter surface:

1. `check_engine_feature(case)`;
2. `check_server_feature(case)`;
3. `check_sdk_feature(case)`;
4. `check_replication_sequence(case)`;
5. `check_reconciliation_case(case)`;
6. `check_ui_feature(case)`;
7. `check_product_journey(case)`.

Cases are data. The runners own construction, invocation, normalization,
assertion messages, timing, cleanup, and artifacts. A refactor changes the
runner once rather than repairing dozens of tests that reached into the old
implementation.

### 3.3 Integrated does not mean slow

Each layer runner exercises all code below its public boundary, but avoids IO
unless IO is the behavior under test.

- engine features use in-memory state and deterministic inputs;
- server features use the real FastAPI application and real route contracts in
  an isolated process-neutral test context where network scheduling is not the
  subject;
- SDK features compile and call the public generated/handwritten SDK surface;
- UI features run the built application in a real browser but may use an
  explicit typed fixture transport when the feature is purely UI-local;
- product journeys own real OS backend and Vite processes and use no route
  interception for product APIs.

Duplicated lower-layer execution is expected. A high-layer test exercising
lower layers is not waste; the nearest-layer check supplies speed and failure
locality, while the higher-layer check proves composition.

### 3.4 IO is explicit and owned

If a test needs disk, HTTP, SSE, WebSocket, browser, subprocess, or SQLite, its
runner owns that resource from creation through teardown. It must not depend on
ports `8000`, `5173`, or any service started by a developer, model, reviewer,
or another test.

### 3.5 Concurrency remains awaitable

No test launches background work it cannot join. Every task, stream, timer,
worker, process, browser, and file watcher belongs to an owner with:

- a readiness signal;
- a completion or cancellation signal;
- an absolute deadline;
- idempotent teardown;
- leak detection after teardown.

Fixed stabilization sleeps are forbidden. Bounded polling is permitted only
for an external readiness surface that has no event interface, and the poll
must report the last observed state on timeout.

### 3.6 Observability is product evidence, not private mutation

When a property is not directly visible, expose a read-only diagnostic fact or
coverage mark. Do not reach into a private store to manufacture success.

Examples include:

- game, encounter, session, source-stream, generation, perspective, and actor
  identities returned by their public contracts;
- HTTP request/response transcript with sensitive values redacted;
- replication observation/presentation/log watermarks;
- presentation drain and command lease states through existing diagnostic
  outputs;
- normalized Pixi/scene manifest and accessibility tree facts;
- process lifecycle and cleanup evidence;
- named coverage marks such as `prepared_source_adopted`,
  `bootstrap_deferral_retried`, `head_committed`, `command_submitted`, and
  `terminal_installed`.

Coverage marks explain which lawful branch produced the result. They are not a
second control plane and cannot change application behavior.

### 3.7 Doctrine conformance is itself checked

The implementation must keep the *How to Test* principles executable rather
than merely citing them:

- **neural-network test:** feature cases use public inputs and user/protocol
  outputs; replacing internals behind the same boundaries does not require
  rewriting case data;
- **low test friction:** one `check_*` owner and one external case schema per
  layer make a new regression primarily a data addition, with contextual diffs
  maintained centrally;
- **fast integrated compute:** engine, server-contract, SDK, pipeline, and
  ledger checks exercise all code below their boundary without OS/browser IO
  unless IO is the feature;
- **owned external world:** product cases embrace real IO but own every process,
  port, profile, browser, deadline, and teardown;
- **expect tests:** normalized outputs have an explicit reviewable update mode
  which is disabled in ordinary and CI runs;
- **peeking without control:** coverage marks and reconciliation evidence make
  negative branches non-vacuous but cannot mutate or admit product state;
- **externalized without tooling loss:** every externalized runner retains one
  trivial in-source smoke/IDE-debug case, while `--case` runs any external case
  directly;
- **beyond examples:** exhaustive, property, structured-fuzz, and shrinking
  packs reuse the data-driven check surface only after its example cases are
  green;
- **awaitable concurrency:** no success depends on detached work or sleeps;
- **layered checks:** each public boundary has its own integrated runner, and a
  higher-layer pass never substitutes for the nearest lower-layer contract;
- **test everything:** command graphs, generated inventories, architecture
  policies, performance curves, cleanup, and release manifests are executable
  checks rather than undocumented CI ceremony;
- **speed and flakes:** every phase reports duration, outliers have explicit
  budgets, and a red first attempt remains red rather than being hidden by a
  retry.

Checkpoint reviews include a generated doctrine audit mapping every bullet to
the owning runner, command, and self-test. A runner which accumulates private
production calls, per-case orchestration code, ambient IO, or fixed waits fails
this audit even if its cases are green.

## 4. Scope and non-goals

### 4.1 In scope

- a shared external case format;
- reusable check runners for engine, server, SDK, replication pipeline,
  reconciliation evidence, UI, and full product;
- a process harness for real backend, Vite, and browser ownership;
- deterministic profile, character, content, encounter, and network fixtures;
- canonical release journeys and negative journeys;
- normalized expectations, diagnostic artifacts, and failure bundles;
- timing and flake budgets;
- migration of maintained tests into an explicit tier/feature inventory;
- CI/local command ownership;
- hard gates preventing route-mocked or ambient-service tests from claiming
  full-product coverage.

### 4.2 Out of scope

- redesigning mechanics to make a test easier;
- changing production contracts solely to expose mutable test hooks;
- replacing every useful focused semantic test with a browser test;
- golden screenshots for every pixel;
- model-driven exploratory clicking as acceptance evidence;
- accepting manual QA in place of an automated release journey;
- hiding slow tests behind conditional compilation or silently skipping them;
- quarantining a flaky critical journey and continuing to call the product
  releasable;
- compatibility routes, fake player rosters, or retry fallbacks added only for
  tests.

## 5. Canonical feature-case model

Create a versioned, language-neutral JSON case format. JSON is chosen because
Python, TypeScript, the SDK, external tools, and a future alternative client
can consume it without a new parser dependency.

The initial envelope is:

```json
{
  "schema_version": 1,
  "case_id": "player.create_character_and_enter_game",
  "title": "Owned character enters a prepared game",
  "layer": "product",
  "tags": ["release", "profile", "bootstrap", "playable"],
  "seed": 1729,
  "deadline_ms": 90000,
  "given": {},
  "steps": [],
  "expect": {},
  "coverage": []
}
```

The closed `layer` values are:

- `engine`;
- `server`;
- `sdk`;
- `pipeline`;
- `reconciliation`;
- `ui`;
- `product`.

Each layer owns a versioned schema for `given`, `steps`, and `expect`. Unknown
fields fail validation. A case never embeds an implementation function name,
source line, Python import path, Vite module URL, or private store key.

### 5.1 Stable inputs

Input data may include:

- a clean or seeded persistent profile;
- character creation choices expressed through public content identities;
- a game recipe/scenario/content identity;
- an explicit controller/seat assignment;
- a deterministic engine seed;
- a public action selection and target allocation;
- transport events such as disconnect, reconnect, bounded delay, duplicate,
  or exact typed fault;
- a replay artifact or durable directory state;
- a versioned browser-storage seed manifest limited to maintained product keys,
  used only by persistence/recovery cases before application startup.

Random UUIDs, ports, timestamps, and temporary paths are generated by the
runner and normalized in output. Tests must never depend on their literal
values.

### 5.2 Stable steps

Product steps use semantic operations implemented by one browser driver:

- `open_product`;
- `expect_profile`;
- `create_character`;
- `select_character`;
- `open_new_match`;
- `select_scenario`;
- `compose_game`;
- `start_game`;
- `wait_for_playable`;
- `select_action`;
- `select_target`;
- `finish_targets`;
- `end_turn`;
- `disconnect_transport`;
- `restore_transport`;
- `reload_client`;
- `open_replay`;
- `seek_replay`;
- `destroy_surface`.

The driver uses accessible roles, labels, and stable `data-testid` product
identities. Tests do not encode CSS layout or call frontend functions.

### 5.3 Stable expectations

Expected output is normalized semantic data, for example:

```json
{
  "ui": {
    "mode": "playable",
    "create_game_enabled": true,
    "action_bar_enabled": true
  },
  "server": {
    "game_status": "active",
    "controlled_actor_count": 1
  },
  "replication": {
    "bootstrap_status": 200,
    "observation_cursor_min": 1,
    "presentation_caught_up": true
  },
  "scene": {
    "controlled_actor_visible": true,
    "interactive_world": true
  },
  "network": {
    "unexpected_requests": [],
    "failed_requests": []
  }
}
```

Exact values are used for contract discriminators, statuses, counts, ordering,
and product text. Ranges or predicates are used for runtime-generated cursors
and timings. The expectation format cannot say “no error” without stating the
positive state reached.

### 5.4 Expectation updates

Provide an explicit `--update-expectations` developer command for deliberately
changed normalized outputs. Default and CI runs never update files. Updates
print the semantic diff and require review like production code.

Do not create large opaque whole-world snapshots. Snapshot only the smallest
public result that fully expresses the feature. Privacy, lifecycle, ordering,
and identity assertions remain explicit fields so a large unrelated diff
cannot hide them.

## 6. Shared runner architecture

### 6.1 Common case loader and result model

Add a dependency-neutral test package at the engine repository boundary, for
example:

```text
testing/
  feature_cases/
  feature_harness/
    schema/
    normalize/
    artifacts/
    cli/
```

The final location may change during implementation review, but ownership may
not be split across ad-hoc scripts. The common package owns:

- schema validation;
- tag and case selection;
- deterministic seed allocation;
- normalized result and expectation diff;
- deadline handling;
- duration reporting;
- artifact directory naming;
- secret redaction;
- result summary in JSON and human-readable form.

Every runner returns one `FeatureCaseResult`. It does not print success and
discard evidence.

### 6.2 Engine runner

`check_engine_feature` constructs the real engine from dependency-neutral
data, executes public actions/events, and returns a normalized causal ledger
and final projection.

It must cover whole engine features, not private helper calls:

- turn and action economy;
- movement, forced movement, jump, and connector traversal;
- attack, save, damage, heal, life-state, death, and revival;
- spells, reactions, conditions, concentration, zones, and perception;
- inventory, equip/unequip, use-item, drop, and destruction;
- AI/native controller decisions where deterministically seedable;
- encounter terminal and replayable event facts.

The runner uses no filesystem, HTTP, sleep, or live global service. Global
registries are installed and cleared by one explicit test world owner.

### 6.3 Server runner

`check_server_feature` exercises the real application contracts using an
isolated server application owner and a temporary durable directory. It must
not monkeypatch the route under test or call its internal function in place of
HTTP.

The application owner enters and exits the real FastAPI lifespan. A bare
`ASGITransport(app=app)` does not run lifespan by itself and cannot claim
startup, callback attachment, content loading, worker ownership, or teardown
coverage. A deliberately route-only case may use a lighter owner only when it
is labelled as such and makes none of those claims.

It covers:

- character directory creation and validation;
- game compose/start/activate and authoritative roster checks;
- sessions, join/control/observe, reconnect, and saved seats;
- prepared encounter source adoption and consecutive replacement;
- subjective bootstrap, frames, follow, reset, logs, and terminal facts;
- available actions and exact command validation;
- replay/archive/history and worker/hosted relay contracts;
- player-scoped presentation-expectation diagnostics and disjoint
  administrator-only objective diagnostics, including authorization,
  perspective binding, non-joinability, and no journal/cursor mutation;
- typed error envelopes and atomic no-mutation negatives.

An in-process ASGI transport is appropriate when socket behavior is irrelevant.
Anything involving streaming scheduling, proxy byte preservation, OS process
startup, or service replacement belongs to the product/transport runner.

### 6.4 SDK runner

`check_sdk_feature` compiles the real TypeScript SDK and invokes only its public
surface. It consumes exact server contract data or a small owned protocol
fixture server when testing transport classification.

It covers:

- generated contract decoding and hard version/hash cuts;
- raw deferral versus generic HTTP conflict discrimination;
- bounded retry policy for initial and replacement bootstrap;
- journal ingest, exact-head preview/reset tokens, combat-log barriers, and
  resync;
- REST catch-up through the sole journal;
- objective/subjective render projection and privacy;
- replay import, segment topology, terminal authority, and seek.
- generated player-safe reconciliation diagnostic decoding, hard version/hash
  parity, stale/cross-perspective rejection, and diagnostic-unavailable truth.

A protocol fixture is not product evidence. Every fixture case states which
wire contract it isolates, and the same successful path is exercised against
the real server in at least one higher-layer journey.

### 6.5 Replication sequence laboratory

`check_replication_sequence` is the fast, non-manual composition boundary that
is currently missing. It treats a subjective replication trace as feature
data and runs the real public pipeline below the browser:

```text
engine command/event sequence
        |
        v
server privacy projection + frame/log production
        |
        v
generated SDK wire decoder + semantic SSE/follower
        |
        v
exact production live composition root
        |
        v
existing journal/head drain -> renderer/runtime terminal

and, separately:

raw replay trace -> exact isolated replay composition root -> Studio scene
```

This runner exists specifically so a person does not have to play every spell,
condition, movement, reaction, reset, or terminal combination to discover that
one lawful server sequence crashes the reducer or cannot be animated.

The case data describes public engine commands and perspectives, not concrete
event constructors. The server adapter executes those commands through the
real engine/runtime owners and uses the replay capture/journal boundaries to
emit a language-neutral trace containing opening bootstrap B0, each projected
world W_i, the ordered raw sync/frame/combat-log deliveries, and closing
bootstrap B1 at the same captured frontier.

The laboratory does **not** assemble decode, journal ingest, preview, planning,
queueing, or commit/reset itself. That would create a second presentation
coordinator which could pass while production composition is broken. It owns
only trace production, injected transport bytes, deterministic clock/assets,
and read-only diagnostics. One disjoint live adapter invokes the exact
production `eventStream`/`eventIngestion` composition root and its sole live
head drain. A second adapter invokes the exact isolated replay session/head
drain/Studio scene root. Those production roots decide how to decode, follow,
ingest, preview/reset, plan, stage, enqueue, settle, and commit.

Direct `reduceSubjectiveWorld()` cases remain useful for focused patch
semantics, but they do not replace either production composition path.

For each accepted head the production roots expose diagnostics which let the
runner assert that the composition:

- validates the authoritative and presentation replicas;
- records the generated-decoder, follower, journal, planner, queue, and scene
  stage reached so a failure cannot be attributed to the wrong boundary;
- proves the candidate passed the SDK render projection;
- proves the real live or replay planner owned the disposition;
- records the closed disposition: state-only, visual transaction, reset, or
  privacy-valid omission;
- the production queue/runtime ran any visual transaction through the injected
  frame-driven clock to one exact terminal and recorded a normalized semantic
  scene delta;
- the production drain committed or reset only its exact issued journal token;
- NORMAL and RESET stage marks cover terminal preinstall, additive/rollback
  scene staging, enqueue and causal barrier, precommit owner/head recheck,
  exact token settlement, postcommit replica application/stateSync, staging
  release, terminal installation, and any recovery/teardown path;
- proves authoritative and presentation replicas converge after the drain is
  idle.

The fast non-browser mode does not assert pixels. Any case whose correctness
depends on Pixi, assets, entry anchors, clip cancellation, or scene teardown is
delegated to the one UI runner and its one browser owner; the sequence
laboratory may not launch another browser or reconstruct a browser consumer.
The UI runner supplies the same trace and deterministic clock to the production
composition root and asserts the normalized scene manifest. A small reviewed
screenshot set may supplement those semantic assertions but never replaces
them.

#### 6.5.1 Trace case format

The `pipeline` schema extends the common envelope with data such as:

```json
{
  "case_id": "pipeline.damage_death_then_terminal",
  "layer": "pipeline",
  "seed": 1729,
  "given": {
    "scenario": "fixture.small_encounter",
    "perspectives": ["controlled.hero", "spectator.enemy"],
    "live_attachment": "attachment-a"
  },
  "steps": [
    {"transport": {"op": "sse_open", "connection": "sse-a"}},
    {"transport": {"op": "sse_bytes", "connection": "sse-a", "delivery": "initial_sync"}},
    {"command": {"kind": "attack", "actor": "hero", "target": "enemy"}},
    {"transport": {"op": "sse_bytes", "connection": "sse-a", "delivery": "next_server_batch"}},
    {"drain": "through_idle"}
  ],
  "expect": {
    "health": "ready",
    "dispositions": ["visual_transaction", "visual_transaction"],
    "presentation_caught_up": true
  },
  "coverage": [
    "sse_a.initial_sync_consumed",
    "server_frame_emitted",
    "live_head.staged",
    "live_head.state_sync_completed",
    "live_head.committed"
  ]
}
```

The stored failure form additionally contains the minimized serialized
bootstrap/delivery trace so the exact failure is reproducible without rerunning
the stochastic producer. Random UUIDs and cursors are symbolically normalized
only in expectations; the bytes passed to generated decoding are never
rewritten.

Transport lifecycle is explicit data rather than one synthetic ordered stream.
The closed operation set distinguishes:

- opening an SSE connection epoch and receiving its one required initial sync;
- delivering raw SSE bytes on that epoch and closing/aborting it;
- fetching a REST catch-up page through the public client catch-up operation;
- opening a new SSE follower after reconnect, seeded from the existing journal;
- authenticated bootstrap plus journal/attachment replacement for changed
  source, generation, or perspective identity;
- receiving an authenticated perspective-safe reconciliation diagnostic through
  its read-only evidence owner, never through the journal/reducer;
- waiting for the production head drain or replacement owner to become idle.

Each SSE connection owns a new real follower and cannot cross identity. REST
pages go through the public client catch-up/onUpdate route into the existing
journal and never through an SSE follower. Generation/perspective replacement
goes only through the canonical authenticated bootstrap/replacement root. Old
connection bytes, catch-up continuations, preview/reset tokens, clip
completions, and callbacks are retained as explicit stale operations so the
case can prove their abort/identity fences. The runner supplies operations to
the production transport entry; it does not call the follower or journal
directly.

#### 6.5.2 Five sequence packs

1. **Lawful authored traces.** Generate real sequences for every classified
   event/action/presentation family and representative cross-family chains.
   Every trace must decode, reduce, project, plan, drain, and settle with the
   expected positive state.
2. **Transport/state-machine traces.** Exhaust the small meaningful relations
   among connection epochs, bootstrap, sync, normal frame, reset frame,
   nullable/visible combat log, duplicate, REST catch-up, reconnect, abort,
   terminal, and replay segment operations through their disjoint production
   owners.
3. **Lawful live-generation replacement traces.** Run live generation A,
   drain and retire only A's live attachment, transport, journal/head drain,
   scene transients, targeting, and lease, then install live generation B from
   exact authenticated bootstrap. Exercise normal and reset/fault handoffs and
   prove only live B can reacquire live presentation and command authority.
   An already-open isolated replay-A session is not retired by this case: it
   remains seekable, receives no B delivery, and cannot mutate B.
4. **Replay lifecycle/isolation traces.** Keep replay A open while live A is
   replaced by live B, inject reciprocal late operations, and prove late live-A
   work affects neither replay A nor live B while replay-A seek/teardown affects
   neither live B nor its authority. Retiring replay A and opening replay B is a
   separate replay-owned lifecycle case; it is never inferred from live
   replacement.
5. **Single-fault mutations.** Begin from a lawful trace and alter exactly one
   identity, cursor, ordering relation, patch invariant, cue graph, terminal
   fact, privacy fact, or token operation. The exact decoder error or journal
   resync reason and the absence of partial mutation are part of the expected
   result.

#### 6.5.3 Required oracles

“No exception” is necessary but is not a sufficient expectation. Lawful cases
assert all applicable positive oracles:

- a fresh server projection/bootstrap at the same captured frontier is
  semantically equal to the SDK authoritative replica produced by reduction;
- for every server checkpoint W_i, the server's world diff equals the emitted
  patches and TypeScript reduction of the prior state plus those patches
  equals W_i;
- after every fully drained prefix, the presentation replica equals the
  authoritative public world/log frontier it is allowed to have reached;
- duplicate delivery is idempotent and conflicting replay is not;
- legal delivery chunking and perspective partitioning do not change the
  per-perspective result;
- render projection contains exactly the authorized facts from the reduced
  replica and no objective/private facts;
- each presentation cue has one expected disposition, transaction lineage,
  semantic scene delta, and terminal outcome;
- live and replay consumers agree where their public semantics are shared and
  remain isolated where their ownership differs;
- reset, failure, cancellation, and stale completion leave no partial reducer,
  scene, clip, timer, or token state.

At every checkpoint/prefix W_i and for every perspective, the runner also asks
the independent censorship/parity diagnostic to derive the lawful subjective
result from the objective prefix. That diagnostic must not import or reuse the
canonical projector. Its result is compared with the emitted patch result, the
SDK authoritative frontier, and the presentation frontier which has lawfully
drained that prefix. Exact source interval, perspective, patch digest, and
hidden/visible/omitted branch coverage marks are required. Final B1 parity is
an additional closure, not a replacement for transient-prefix parity. This
prevents a producer and consumer that share or later converge away the same
transient defect from serving as their own oracle.

Invalid cases assert the exact typed failure/resync boundary and compare state
before and after the rejected operation. A validator failure which happens
before the intended mutation boundary is a non-vacuous failure, not a pass.
Validation results require a stable semantic rule ID/code plus structured path;
tests never bind to prose or stack text. Where current Python or TypeScript
errors expose only prose, adding that stable read-only error identity is part
of this testing-surface implementation.

#### 6.5.4 Generation and shrinking

The generator first creates a valid trace from a closed grammar of public
operations and protocol relations. Fault generators then apply one named
mutation. On failure, the runner records the seed and automatically minimizes
in this order:

1. shortest failing prefix;
2. removable independent commands/deliveries;
3. unrelated entities, patches, cues, and logs;
4. simpler values which preserve the same coverage marks and failure class.

The minimized trace becomes an ordinary checked-in case. Shrinking must retain
the causal parent/child graph and the exact failure boundary; it may not turn a
deep reducer/planner failure into an earlier schema rejection.
For replacement failures it must also retain the minimum A -> B lifecycle
boundary, the stale-live-A operation being tested, the live-B owner whose
authority must remain intact, and any independent replay-A session whose
continued seekability or teardown isolation is part of the failure. Replay
lifecycle shrinking separately preserves replay-A retirement/replay-B install
without manufacturing a live replacement dependency.

### 6.6 Reconciliation evidence runner

`check_reconciliation_case` is the fast public boundary for the versioned
ledger contract in §8.12. Its input is serialized production-issued evidence
data, not journal/queue/scene objects or callbacks. It returns the normalized
ledger JSON, view model, health, retention/tombstones, and structured rejection
for invalid input.

It covers:

- all three disjoint incident roots and their available-identity rules;
- legal node lifecycles, materialized blocked edges, and unmaterialized
  category markers;
- first-causal-node retention, sibling outcomes, recovery links, and
  observational side incidents;
- deterministic ordering, digest, privacy projection, redaction, and export;
- exact byte/node/incident/tombstone budgets and whole-incident compaction;
- current/prior/malformed schema input, quota/non-durable state, view
  degradation, core-capture health failure, and idempotent cleanup.

The runner is sans browser, network, storage IO, and production presentation
work. Persistence and mounted-view integration are separate higher-layer cases
which consume the same normalized contract. A ledger implementation could be
replaced wholesale without changing these cases if it preserves this public
evidence result.

### 6.7 UI runner

`check_ui_feature` launches a real built NeuroClient browser surface with a
typed fixture transport owned by the runner. It covers UI-only behavior that
does not need the server:

- accessibility and keyboard/pointer equivalence;
- action selection/targeting and lease invalidation;
- panel state, focus, modal, and teardown;
- render projection to Pixi manifests;
- clip/animation/replay behavior under injected deterministic clocks;
- visual state for loading, error, disabled, empty, and terminal conditions.

Route interception is allowed only in this layer and only through the shared
typed fixture transport. The result is labelled `ui`, never `product`. A test
which intercepts `/game-creation`, `/session`, `/replication`, `/actions`, or
another product API cannot claim a server, SDK, or full-product tag.

### 6.8 Product runner

`check_product_journey` owns the real product topology:

```text
temporary profile/runtime root
        |
        v
real backend OS process <-HTTP/SSE-> real Vite OS process <-browser-> Playwright
```

It must:

- allocate non-default ports;
- start a fresh backend with a unique temporary runtime root and known seed;
- start Vite configured to proxy only to that backend;
- launch an isolated browser context;
- prohibit application-route interception;
- capture requests, responses, console errors, page errors, server logs, and
  process exits;
- drive only the canonical UI;
- wait on positive product signals, not sleeps;
- terminate the browser, Vite, backend, and process groups in `finally`;
- prove the ports and child processes are gone;
- retain a bounded artifact bundle on failure.

The harness has two explicit frontend modes. Developer qualification may use
the owned Vite development server. Release qualification first performs a
clean production build and serves that exact artifact through the owned
preview/static-server boundary. At least the canonical create-character ->
playable -> first-command journey runs in both modes; a dev-server pass cannot
authenticate the shipped bundle.

The runner must fail if another process already owns a selected port, if the
browser contacts an unapproved origin, or if either service was not started by
the case owner.

## 7. Owned-process harness

### 7.1 Resource owner

Implement one `ProductTestWorld`/equivalent with explicit lifecycle:

```text
create -> start_backend -> await_backend_ready
       -> start_vite    -> await_vite_ready
       -> start_browser -> run_case
       -> collect_result
       -> close_browser -> stop_vite -> stop_backend -> assert_clean
```

All child process handles are retained. Fire-and-forget process creation is
forbidden. Teardown is idempotent and runs after setup failure as well as test
failure.

### 7.2 Port allocation

The harness owns port allocation. It must avoid check-then-bind races by
holding or atomically transferring reserved sockets where the platform permits.
If Vite/Uvicorn cannot inherit a socket, allocation retries are bounded and the
process must prove the expected instance via a run identity in its readiness
response/log, not merely observe that something responds on the port.

No canonical automated test uses ambient `:8000`, `:5173`, or `:5174`.

### 7.3 Temporary durable state

Every product case gets a new directory containing:

- profile/directory database;
- game history/archive database;
- generated run identity;
- logs and artifacts;
- any writable content cache;
- browser user data when needed.

Content packs and immutable assets may be shared read-only. No case reads or
mutates the developer's real `.runtime` state.

Browser state is fresh by default, but the recovery runner also owns an
explicit pre-start browser-storage seed manifest. It may seed only maintained,
versioned product storage boundaries through their real browser storage medium
before the first application script executes; it may not construct private
stores or invoke persistence internals. This permits production startup to
exercise its one pre-parse persistence owner against:

- a valid current payload which must survive unchanged;
- malformed JSON/structured payloads, prior schema versions, and
  source/generation/session identity mismatches which must be atomically
  cleaned or quarantined according to the maintained contract;
- mixed state where invalid volatile replication/presentation facts are
  removed while valid profile, replay, and user-preference data remain scoped
  and usable;
- reload and live generation replacement after cleanup;
- real browser quota pressure or denied writes, without replacing the
  production writer;
- repeated startup/cleanup and teardown, proving idempotence and no error loop.

The case captures the before/after maintained keys and production cleanup
diagnostics. It then performs authenticated bootstrap to the playable state
with zero page/console errors. An unknown ad-hoc key is not evidence that a
maintained persistence boundary was tested.

### 7.4 Readiness and deadlines

Backend readiness requires its real capability/health contract plus matching
run identity. Vite readiness requires loading the exact application build from
the owned origin. Browser readiness requires a visible product landmark.

Each phase has a separate deadline and failure message. A 90-second journey
does not hide whether backend startup, Vite startup, character creation,
bootstrap, rendering, or teardown consumed the time.

### 7.5 Failure artifacts

On failure, retain:

- case JSON and normalized expectation diff;
- backend stdout/stderr;
- Vite stdout/stderr;
- browser console and page errors;
- redacted network transcript;
- last accessibility snapshot;
- screenshot;
- scene/render diagnostic manifest when available;
- the versioned reconciliation chain identifying the first failing causal node
  and every later node blocked by it;
- server game/session/replication diagnostic facts through public read-only
  contracts;
- process/port leak report;
- timing breakdown.

Artifacts are diagnostics, not acceptance evidence by themselves. The case
passes only from its assertions.

## 8. Mandatory feature journey matrix

The initial implementation is incomplete until every P0/P1 row below has a
case ID, one layer owner, and at least one automated positive or negative.

### 8.1 Profile and character journeys

1. Clean profile shows zero characters and actionable character creation.
2. Standard New Match is disabled with exact “Create a character to start a
   match” guidance; no compose/start request is sent.
3. Direct empty/invalid owned roster request is rejected by the server before
   current game/source mutation.
4. Premade character creation through the canonical UI persists a real
   character and rehydrates the shelf.
5. Invalid character choices fail structurally and do not create a partial
   durable record.
6. Existing character selection survives reload.

### 8.2 Canonical game creation and replacement

1. Selected owned character + selected scenario composes successfully.
2. Start creates the exact game/encounter and owner roster slot.
3. Session creation and join grant the expected controlled actor.
4. Prepared subjective bootstrap succeeds before encounter activation.
5. Activation produces live frames and the playable scene/input state.
6. The deterministic first command is an ordinary state-changing Move selected
   through the mounted action bar and an exact world target. The case proves
   the exact leased action row/actor/target, one POST, authoritative from/to
   position and movement cost, advancing subjective frame and combat-log
   cursors, visible Pixi motion through the authored production drain, final
   presented occupancy equal to authoritative occupancy, continued lawful
   input/turn state, and zero page/console/network faults. This runs in both
   owned dev-server and production-build modes; End Turn, a canceled picker,
   or a no-visible-change receipt cannot satisfy it.
7. A second canonical game in the same backend process adopts a new source and
   bootstraps without stale identity from the first.
8. Foreign explicit encounter/source requests fail atomically.
9. Explicit observer/AI simulation remains a separately named operation and
   cannot be selected by absence of player characters.

### 8.3 Replication and recovery

1. Exact raw `source_batch_in_flight` bootstrap deferral retries within the
   bounded SDK policy.
2. Generic/non-deferral 409 preserves its typed envelope and terminates after
   one initial or replacement bootstrap request.
3. SSE duplicate and legal reconnect do not duplicate state.
4. REST catch-up ingests through the sole journal and fixed presentation fence.
5. Resync-required catch-up delegates once to authenticated replacement.
6. RESET_REQUIRED disables commands synchronously, retains visible rows, and
   applies exactly once.
7. Disconnect/reconnect, reload, and saved-seat resume restore the same lawful
   perspective or fail with a truthful terminal identity error.
8. Combat logs remain ordered across normal/reset/reconnect boundaries.
9. A lawful production generation A -> B transition drains and retires live A,
   installs B only from exact authenticated bootstrap, rejects late live-A
   frames/logs/reset tokens/clip completions, clears A's live targeting, lease,
   scene, attachment, and drain transients, and permits only live B to
   reacquire and execute. Reset or recovery during the handoff is covered.
   An open isolated replay-A session remains seekable and receives no B; live-A
   late work affects neither replay A nor live B, and replay-A seek/teardown
   cannot affect live B.

### 8.4 Turn, command, and action journeys

1. Available-action rows become enabled only with an exact presented lease.
2. Single-target action submits the exact leased row.
3. Multi-target action accepts a lawful submaximum and maximum allocation and
   rejects invented, duplicate, reordered, or stale rows.
4. Keyboard and pointer paths produce the same typed command.
5. Accepted frame, reset, turn loss, actor/generation change, and reconnect
   cancel stale targeting immediately.
6. Turn end, reaction, cancellation, and timeout each reach one exact terminal
   outcome without queued causal work.

### 8.5 Presentation, privacy, and locomotion

1. Objective and subjective projection agree on authorized public facts while
   hidden/private fields never appear.
2. Walk, Swim, Fly, Burrow, Jump, and Connector produce the correct entry
   anchor/profile and one aggregate commit.
3. Live and replay sessions with identical source/entity remain isolated.
4. Connector rendering preserves SDK order, is noninteractive, and commands
   use safe connector identity only.
5. Hidden-visible transitions do not destination-snap or backtrack.
6. Clip failure, deadline, reset, and stale completion cannot authorize
   command/presentation terminal truth.
7. Consecutive disclosed one-edge Step heads commit independently while a
   typed body-cycle lease preserves Walking phase across compatible fragments;
   only an explicit presentation/turn/action/terminal/reset/cancel/entity-loss
   boundary ends the cycle, and no client infers an undisclosed route.

### 8.6 Inventory, equipment, conditions, and combat

1. Inventory pickup/drop/use and equip/unequip round-trip authoritative state
   and visible presentation.
2. Damage, healing, life-state changes, death, revival, and capability denial
   agree across engine, subjective state, UI, and combat log.
3. Attack, save, spell, multi-target, reaction, concentration, zone, and forced
   movement features each have engine data cases and at least one composed UI
   or product representative.
4. Perception/light/hidden hazard facts respect subjective privacy.
5. Invalid action/equipment/target operations fail without partial mutation.

### 8.7 Terminal, archive, and replay

1. Ordinary cue and reset-terminal fact each install one exact encounter result
   after their barrier.
2. Terminal authority survives postinstall recovery but not forged branch,
   event, encounter, or authority mode.
3. Game archive persists and cold-decodes after real completion.
4. Replay seek across NORMAL -> RESET -> NORMAL reconstructs pixels, state,
   combat-log cursor, and terminal result in an isolated Studio surface.
5. Replay teardown during pending mount/animation leaves no process, ticker,
   observer, or live-store mutation.
6. Replay A can remain open and seekable across live A -> live B replacement;
   it receives no live-B data and cannot mutate live B. Its later teardown is
   replay-owned and leaves live B intact.
7. Replay-A retirement followed by replay-B installation is exercised as its
   own replay lifecycle, including late replay-A completion/token/seek attempts
   and replay-B-only scene/session authority.

### 8.8 Catalog, route, and error coverage inventories

Generate feature inventories from the authoritative registries rather than
maintaining hand-written counts:

- every public engine action/event family;
- every shipped spell, item-use, condition, controller, scenario, and
  traversal behavior category;
- every canonical character/build loadout, semantic terrain material, authored
  presentation recipe, and referenced media atlas with its compiled dimensions
  and renderer/device-limit policy;
- every player-facing HTTP/SSE route and generated SDK operation;
- every closed presentation disposition and locomotion family;
- every presentation-owned requestFrame, timeout, deferred callback, decorative
  child, and resource-lease/transfer terminal;
- every typed public error discriminator;
- every reconciliation stage, cue/transaction/clip terminal outcome, and
  blocked-by relation exposed by the maintained evidence contract;
- every canonical top-level UI surface and command entry point;
- every maintained browser-persistence key, schema/version discriminator,
  migration/cleanup rule, and production startup owner.

Each row maps to:

- at least one fast positive case;
- required structural/semantic negative cases;
- zero or more product representatives;
- one owning runner and expectation;
- a reason when full-product coverage is deliberately unnecessary.

The inventory gate fails on an unclassified new row. This is feature coverage,
not line coverage: a new spell which shares an already-proven semantic recipe
may use a generated engine/catalog case plus one representative product path,
while a new behavior family requires its own integrated cases. Conversely, a
high code-coverage percentage cannot satisfy a missing public route, error, or
journey row.

### 8.9 Reducer, journal, and presentation sequence matrix

The initial sequence corpus must include, at minimum:

1. each patch kind alone and in lawful same-frame combinations, including
   remove/upsert, visibility, equipment/loadout, door, connector, and encounter
   replacement ordering;
2. each presentation cue family alone and in lawful parent/child graphs;
3. real engine chains for movement/reaction, attack/damage/life-state,
   spell/save/multi-target, condition apply/remove, equipment/use-item,
   perception reveal/hide, turn transition, and encounter terminal;
4. multiple lawful actions across one turn and multiple turns, including
   nullable and visible combat-log deliveries interleaved with presentation;
5. normal -> reset -> normal, reset-terminal, ordinary terminal, reconnect,
   catch-up, saved-seat, replay import, and replay seek sequences;
6. two simultaneous perspectives over the same source sequence, proving both
   legal subjective divergence and shared public cursor/terminal truth;
7. duplicate delivery at every retained frontier, plus one conflicting replay
   of the same identity;
8. missing/reordered/advanced/regressed frame and log cursors, reused
   presentation IDs, changed source/generation/perspective identities, stale
   preview/reset tokens, and queue overflow;
9. one-field malformed patches, invalid resulting-world invariants, invalid
   cue graphs/dispositions, and invalid terminal authority, each with exact
   no-partial-mutation expectations;
10. animation settlement for every closed presentation disposition and
    locomotion family with success, cancellation, failure, timeout, reset, and
    late-completion ordering;
11. a cross-root action-trigger dependency cycle which is structurally
    decodable but cannot be scheduled; it must fail at the owned semantic
    contract boundary, never first appear as a runtime animation crash;
12. a COMMITTED movement cue whose endpoint disagrees with the resulting
    entity patch; it must fail before animation can move the actor somewhere
    the reduced world did not commit;
13. lawful live generation A -> B in the production live owner, including
    reset/fault during handoff and late live-A
    delivery/token/clip/callback attempts after live B is active, with exact
    live-A retirement and live-B-only authority marks while an independent
    replay-A session remains open and seekable;
14. reciprocal live/replay isolation: late live-A work affects neither replay A
    nor live B; replay-A seek/teardown affects neither live B nor its command
    authority; separate replay-A retirement -> replay-B installation rejects
    late replay-A operations and grants only replay-B scene/session authority;
15. NORMAL and RESET failures injected at staging, causal enqueue/settlement,
    precommit ownership recheck, and postcommit stateSync, proving exact token
    consumption, rollback versus retained installed authority, one recovery
    incident, and no test-owned retry in both live and isolated replay roots.
16. Decorative/async child resource leases across live, replay, and Studio,
    proving terminal cannot precede the last owned callback, stateSync/reset/
    seek/destroy/generation replacement cancels or transfers every child, and a
    deliberately released late callback is classified before it can touch a
    destroyed scene object.

An authoritative feature inventory generates the coverage table for this
matrix. A new event, patch, cue, error discriminator, or presentation
disposition fails inventory validation until it is assigned to a lawful trace,
the required mutations, and an expected reducer/planner outcome.

### 8.10 Browser persistence startup and recovery

The owned browser runner executes this pack before application startup using
only the maintained storage boundaries enumerated by §8.8:

1. valid current persisted state survives startup and reload unchanged;
2. malformed structured data and a prior schema version are cleaned or
   quarantined once by the production pre-parse startup owner, without a page
   crash or repeated cleanup loop;
3. source, generation, session, or perspective-mismatched volatile state is
   rejected before it can populate the live journal, presentation, targeting,
   lease, terminal, or scene owners;
4. mixed storage preserves still-valid profile, replay, and preference data
   while removing only invalid scoped replication/presentation state;
5. after cleanup, authenticated bootstrap reaches a playable scene with zero
   page/console/network errors, and reload plus live generation replacement
   remain lawful;
6. quota exhaustion or denied write reports one truthful recoverable result,
   leaves the last valid persisted value readable, and does not spin or prevent
   teardown;
7. repeating startup, cleanup, reload, and teardown is idempotent and leaves no
   browser context, storage listener, timer, worker, or process leak.

Every case proves the exact maintained key/schema and startup owner reached.
Seeding an unused key, clearing the whole browser profile, or catching a page
exception without reaching playable is non-vacuous failure, not a pass.

### 8.11 Permanent live-regression cluster

The user-observed combat/render cluster from 2026-08-09 is permanent required
coverage. It is not retired after the immediate defects are fixed and cannot
be represented by one final-state assertion.

1. `pipeline.multi_target_death_corpse_memory_prefix_parity` executes real
   multi-target damage/death/visibility-loss prefixes. The independent
   objective-to-subjective diagnostic, emitted patches, SDK authoritative
   world, and drained presentation world must retain the same perspective-
   authorized remembered-corpse rows at every W_i. A bounded mounted UI/product
   representative asserts the actual scene manifest at the key visible,
   death, and remembered-corpse prefixes rather than making the non-browser
   pipeline manufacture pixels. The
   diagnostic cannot drop lawful corpse memory merely because the objective
   creature is now dead or no longer visible. The canonical subjective memory
   contract and reducer are not weakened merely to make the diagnostic pass.
2. `pipeline.enemy_fireball_haste_fireball_death_head_liveness` stores a
   deterministic real server trace equivalent to enemy Fireball -> damage ->
   Drink Haste Potion -> Haste gain -> second Fireball -> Invisibility removal
   -> damage/death -> Turn End. The exact production live root and isolated
   replay root must process every journal head in order. At every prefix the
   case asserts head identity, presentation cursor, ClipQueue transaction
   terminal, postcommit stateSync, scene fact, and semantic visual. Continued
   mechanics or combat-log progress cannot mask a stuck earlier presentation
   head. The captured pre-fix evidence is imported into the checked-in corpus
   with a content digest: objective events 1058..1100 disclosed the complete
   second Fireball root and effects, while the fatal subjective frame contained
   damage/dead/light/turn-end/encounter-end cues but no Fireball spell cue. A
   producer-side branch therefore proves privacy-safe root-scoped disclosure:
   when cast start/source was lawfully disclosed, the same root spell cue is
   not suppressed merely because the controlled observer dies or loses
   visibility before root completion. The frontend may not infer the missing
   cast from damage or combat-log text. A separate consumer branch starts from
   a lawful trace containing the cue and localizes the first Fireball's missing
   popup/FX through the real ledger and drains.
3. `ui.haste_potion_semantic_visual` proves more than cue transport. The
   authored presentation must communicate Drink Haste Potion plus Haste
   condition gain through an explicit semantic prop/effect/feedback contract;
   a generic Taunt body action or cue-count-only assertion cannot satisfy it.
4. `pipeline.multi_tile_walk_continuous_cycle` uses a real multi-tile movement
   trace and the production runtime host. Adjacent authorized Step fragments
   preserve a presentation-owned body-cycle lease/phase while each frame-local
   spatial clip and journal head still settles/commits independently. The
   obs4/5/6/7 and obs63/64/65 one-edge sequences are retained representatives:
   Walking does not restart or pass through Idle between compatible disclosed
   fragments, and playback phase is monotonic. The cycle ends only at a safely
   observed boundary: incompatible next presented cue/state, action/turn/
   terminal/reset/cancel, entity loss, or an explicit presentation terminal.
   The client may not infer a hidden route or use coordinates/timing to guess
   continuity. If the current cue contract cannot state the necessary terminal
   boundary, the case remains red until the backend presentation contract adds
   one; MoveClip may not secretly stitch paths.
5. `ui.fire_bolt_atlas_policy_and_authored_visual` has two mandatory,
   non-substitutable branches. The shipped/repacked Fire Bolt atlas must satisfy
   the supported renderer policy and its real authored transaction must load,
   display recognizable Fire Bolt spell FX, settle successfully, leave the
   scene visible, and permit the exact head to commit. Separately, a preserved
   legacy 9216 x 2048 fixture is exercised against a WebGL
   `MAX_TEXTURE_SIZE = 8192`; asset compilation/preflight must reject it before
   GPU upload, keep the base scene visible, reach one deterministic nonblocking
   clip/transaction terminal, and report exact asset ID, atlas dimensions,
   device limit, and WebGL facts. A black canvas, uncaught `texImage2D`, stalled
   head, or silently dropped optional media fails. The legacy fail-safe cannot
   substitute for successful presentation of the corrected shipped asset.
   Presentation recovery preserves the last completely committed scene until
   an authenticated replacement scene is ready; it cannot destroy actors,
   floor, and VFX first and leave a black surface if rebootstrap/catch-up fails.
   The mounted case advances through the real restart/reset recovery microtask
   and a failed replacement catch-up, not merely the synchronous clip-failure
   latch, while continuously sampling the committed scene manifest/canvas.
6. `product.acid_splash_single_target_finish_and_enter` proves Acid Splash's
   canonical one-to-two target law in the mounted product. The primary
   submaximum cases expose at least two lawful targets, select exactly one, and
   then complete separately by Finish-ring click and Enter; each submits
   exactly one request with the exact leased primary and zero extras, applies
   engine mechanics, presents the spell/damage, and returns to continuing
   lawful input. A second world with only one discoverable lawful target proves
   the same one-target allocation remains completable. Adjacent cases select
   both targets and cover duplicate rejection, stale lease, enemy turn, and
   cancellation. `num_projectiles = 2` remains a maximum, never a required
   cardinality.
7. `product.water_material_render` checks the authoritative content/wire fact
   and mounted semantic material for Water. The shipped arena recipe which
   previously constructed `name = "Water"` without a sprite must use the
   canonical `water_factory` contract (or an exact reviewed equivalent) so the
   authoritative tile carries `water.png` plus the canonical swim/movement
   semantics through world projection. A projection fallback to `floor.png`
   fails even if the display name still says Water; the frontend may not infer
   water from that name. The product representative asserts the exact wire
   material/movement facts, a water scene-manifest material, and a bounded
   captured screenshot artifact. Automated semantic material and scene facts
   decide the case; human/model screenshot review is supplemental only.
8. `server.default_sorcerer_invisibility_inventory` freezes the required
   `hero.sorcerer_l5_standard_torch` default/persisted build spell set at
   character creation and materialization, then proves the authored
   Invisibility grant and resulting lawful action are present. The frontend
   cannot add or infer a missing spell. If the canonical content decision
   intentionally removes it, the versioned build contract, expected inventory,
   and regression-scenario fixture must change together through explicit
   content review rather than drift silently.

The following independent-audit findings are separate mandatory cases unless a
stored trace proves a causal relationship. They cannot be marked covered by a
fix to one of the eight cases above:

9. `pipeline.position_only_spatial_effect_contract` aligns the Python
   position-only `SpatialEffectPresentationCue`, generated/handwritten SDK
   semantic validation, and Neuro mapper disposition. Lawful zone-creating
   spell frames must decode and present; malformed entity/position/effect
   combinations fail at one stable contract rule.
10. `pipeline.diagnostics_best_effort_non_authoritative` injects throwing and
    inconsistent presentation/coverage/parity subscribers. Immutable
    diagnostic delivery records the incident but cannot reject a lawful head,
    fail enqueue/clip execution, or request authenticated recovery. It
    explicitly exercises synchronous subscriber notification at queued and
    started lifecycle boundaries, where an uncaught observer previously could
    escape outside ClipQueue's defensive execution boundary.
11. `pipeline.cancelled_generation_mutation_fenced` stalls every host mutation
    sink, cancels/replaces its generation, then releases the old completion.
    No old weapon, entity, condition, terminal, or store mutation may cross
    into the replacement scene.
12. `ui.nonzero_negative_grid_origin` renders positive-offset, non-zero, and
    negative-inclusive board bounds. Grid geometry, light lookup, overlays,
    highlighting, entities, and startup camera share the exact absolute-to-
    render transform.
13. `product.pretry_storage_failure_ui` denies or throws from maintained
    session/local storage before ordinary startup initialization. The root
    startup owner must catch the typed failure, render truthful recovery UI,
    preserve scoped valid state, and tear down cleanly; an unobserved `init()`
    rejection fails.
14. `ui.decorative_callback_resource_lease_lifecycle` inventories BannerClip,
    FloatingText, and every requestFrame/timeout/deferred child created by a
    visual transaction. Each callback owns a typed resource lease bound to the
    clip/transaction/runtime host. Live, replay, and Studio traces exercise
    terminal, stateSync, reset, seek, surface destroy, and generation
    replacement. A node cannot report `COMPLETED` until all owned callbacks are
    terminal or have transferred to an explicitly identified longer-lived
    owner. No callback may run after its lease terminal or touch a destroyed
    container; zero page errors are required. The exact recovered replay case
    where BannerClip returned as decorative, stateSync destroyed HUD children,
    and a later requestFrame callback threw is permanent. The fix and test own
    the central clock/resource-lease boundary, never a Banner-specific null
    guard.

Evidence is applicability-scoped by the case owner; no lower layer emits empty
or synthetic browser facts. All cases record case/seed identity, the exact
production boundary reached, required coverage marks, and before/after state.
Pipeline cases record raw trace, game/session/source/generation/perspective
identity where present, all cursors, every production-issued head/cue/
transaction/clip identity and outcome, semantic projection/reconciliation
facts, and minimized failure prefix. UI cases additionally record authored
recipe/asset IDs, applicable WebGL limits/errors, mounted scene manifest,
console/page faults, and screenshot. Server/content cases record canonical
content/wire identities and route facts. Product cases record the complete
network transcript, lease/action/target rows, browser faults, scene manifest,
and screenshot in addition to applicable lower-layer evidence. A log-only
pass, final-state-only parity pass, cue-count-only pass, absent inapplicable
field disguised as evidence, or manual/model visual judgment is vacuous.

Cases 1, 2, 4, and 9-11 belong to `test:feature:pipeline`; cases 3, 5, 12, and 14
belong to the owned `test:feature:ui` browser boundary; cases 6, 7, 8, and 13
have server/content checks plus owned product representatives. The complete
stored combat sequence and its mounted visual representative run under
`test:product:recovery`, and `test:product:release` includes every case in this
cluster. A lower-layer pass never substitutes for its named product
representative. Case 4 additionally has a mounted motion representative which
proves visible animation-phase continuity rather than only session metadata.
Required product representatives are explicit: the stored combat journey
covers cases 1-3; separate mounted journeys cover cases 4-9 and 12-14. Cases
10 and 11 are deterministic fault-injection checks through the exact production
composition/UI roots and do not require an artificial user journey merely to
inject a diagnostic subscriber or late canceled completion.

### 8.12 Reconciliation observability vertical

Reconciliation/presentation evidence is a core product feature, not optional
debug logging. It must explain the first causal presentation failure without a
person reconstructing it from console stacks and combat logs.

The evidence schema has three mutually exclusive incident roots:

1. `DELIVERY_ADMISSION_INCIDENT` is used when raw delivery, generated decode,
   semantic envelope/follower, journal admission, or head preview fails before
   the production owner issues an exact accepted head/token. It carries only
   identities actually available at that boundary: connection/attachment,
   delivery digest/kind, authenticated/validated
   source/generation/perspective/cursors when present, stable rule/path, and
   error outcome. Rejected but parseable wire fields are stored only as a
   quarantined field-name set plus redacted payload digest; attacker-asserted
   values never become identity. It never claims an accepted head, token, cue
   graph, transaction, or clip which was not produced.
2. `ACCEPTED_HEAD_PRESENTATION_INCIDENT` exists only after the production owner
   issues an exact head/token. It anchors causal presentation failure to that
   real head and may reference only cue, transaction, clip, recipe, profile,
   asset, staging, scene, commit, and stateSync identities subsequently issued
   by the same production root.
3. `EVIDENCE_OWNER_INCIDENT` is observational-only and exists for evidence
   startup/migration, first persistence write, schema, compaction, export, or
   mounted-view failures which occur before any connection, delivery, or head.
   Its real identity is the product run/browser context, evidence-owner
   incarnation, schema version, storage boundary, and ledger sequence. Product
   delivery/head/cue identities are explicitly null. It never owns `BLOCKS`,
   queue, commit, reset, or recovery edges.

These roots are not interchangeable and cannot be upgraded by inference. A
delivery-admission incident remains a delivery-admission incident even when a
later retry accepts the same logical server batch. An accepted-head incident
must cite the exact production-issued token; matching cursors or cue payloads
are not a substitute. An evidence-owner incident cannot later acquire delivery
identity. Retry/replacement creates a new root linked by a typed `RECOVERY_OF`
edge, preserving both attempts. Root event IDs are unique within the evidence-
owner incarnation; exact duplicate events are idempotent, while a conflicting
reuse is a typed schema incident and qualification failure.

For every accepted presentation head, the maintained evidence model records an
immutable identity containing only facts actually issued by the production
root:

- live or replay consumer identity, source stream, generation, perspective
  epoch, and source/observation/presentation/combat-log cursors;
- delivery kind and exact journal head/token identity;
- every cue presentation ID, root/parent relation, disposition, authored
  recipe/profile identity, and referenced asset identity;
- every `VisualTransaction` and clip identity which production actually
  materialized, with queued, started, and one terminal timestamp/outcome.

The maintained ledger is an append-only, versioned event stream projected into
the reconciliation JSON. Its closed node lifecycle is:

```text
materialized node:
  ISSUED -> QUEUED -> STARTED -> COMPLETED | FAILED | CANCELLED | TIMED_OUT
         -> NOT_STARTED_BLOCKED_BY

nearest real node:
  -> NOT_MATERIALIZED_DUE_TO(category)   (marker, never a concrete node)
```

Only transitions applicable to the node kind are legal. For example, a head
can be issued and fail during staging without claiming a clip was started; a
materialized clip may be blocked before start; and an unmaterialized clip
category never receives a fabricated clip identity. Each append has a
monotonic ledger sequence and the identity of the production boundary which
emitted it. Wall-clock timestamps cannot establish causal order.

A visual node may reach `COMPLETED` only after its typed resource lease proves
that every owned requestFrame callback, timer, deferred continuation, HUD/VFX
child, and render container is terminal or has atomically transferred to a
named longer-lived owner. Transfer preserves the causal parent and creates a
new owner/lease identity; “decorative” is not an ownership exemption. A
callback observed after the cited lease/node terminal creates a separate
causal `LATE_CALLBACK_AFTER_TERMINAL` incident referencing the immutable prior
terminal; the ledger does not rewrite history to pretend the node never
completed. Any such contradiction fails qualification and the callback is
fenced before it can touch destroyed scene state.

The schema also has two disjoint outcome tracks. The closed causal production-
stage vocabulary distinguishes mapping/disposition, scene staging, production
asset resolution/load/GPU upload, clip execution, watchdog, scene/world
barrier, token commit uncertainty, postcommit stateSync, and reset for an
accepted head. Delivery/decode/follower/journal/preview stages belong only to
`DELIVERY_ADMISSION_INCIDENT`. The nonblocking observational-incident
vocabulary contains independent parity mismatches, coverage/reconciliation
subscriber faults, evidence persistence failures, and reconciliation/debug-UI
rendering failures. A new stage or incident cannot appear as free-form prose;
it must enter the versioned inventory and its renderer/schema tests.

The normalized summary exposes two independent optional fields:

- `first_causal_production_failure`, which may own `BLOCKS` edges and comes
  only from an authoritative delivery-admission rejection or accepted-head
  production outcome;
- `first_observed_divergence`, which may identify an earlier independent
  parity/coverage/evidence discrepancy but never owns `BLOCKS` edges or changes
  admission, settlement, commit, reset, or recovery.

An ordinary subjective client cannot infer an omitted cue from damage, combat
log, or objective state. Product-visible `EXPECTED_CUE_NOT_EMITTED` therefore
requires a generated `SubjectivePresentationExpectationDiagnostic`, fetched
from a separately authenticated read-only player-diagnostics operation owned
by the server presentation authority and bound to the requesting session's
exact perspective. It never rides the subjective journal, cannot advance a
replication cursor, and cannot be submitted by the browser. The fact carries
only:

- the already-authenticated source/generation/perspective and delivery/frame
  identity;
- a per-perspective, non-joinable expectation identity;
- a public presentation family/content reference only when that action/root
  was already lawfully disclosed to the same perspective;
- the frozen root-disclosure proof kind and stable omission rule ID.

It carries no raw objective event lineage, hidden target, undisclosed content,
private actor fact, or cross-perspective-stable correlation key. A separate
privileged pipeline artifact may retain objective lineage for the independent
W_i oracle, but that artifact never enters player JSON/UI. Administrator-only
objective diagnostics use a different generated response and authorization
scope and are never merged into a player ledger. The production runner does
not inject either fact: the player fact arrives through its public authenticated
diagnostic client/decoder and evidence owner, outside the journal/reducer, and
can only create an observational incident. Schema generation, SDK decoding,
server authorization, client delivery, and mounted rendering all share the
same version/hash cut. If that diagnostic is disabled, unauthorized, missing,
stale, or unavailable, the ledger records
`PRESENTATION_DIAGNOSTIC_UNAVAILABLE` and does not claim to know whether a cue
was omitted. The mounted view may report “upstream authorized cue omission; no
client transaction issued” only from the authenticated safe fact, never by
inference.

Cross-perspective cases prove that a player cannot correlate another
perspective's expectation IDs or learn an undisclosed spell/target. Forged but
well-formed identity fields remain quarantined; a lawful omission whose
objective lineage was never disclosed produces no player-visible content or
lineage. The independent oracle still fails the pipeline case in its privileged
artifact, so diagnostic unavailability cannot turn a producer defect green.
They also prove a player cannot call the administrator diagnostic operation,
cannot replay a safe fact across session/perspective/generation, and cannot
join player-safe expectation IDs to administrator/objective lineage.

Each causal chain has one stable `incident_id`. Within a retained incident, the
first failing causal node is immutable evidence. A later reset, death, terminal
head, recovery, or teardown cannot rewrite or replace it. Every downstream
identity which production already issued but
which never began is recorded as `NOT_STARTED_BLOCKED_BY` with the exact
existing head/cue/transaction identity rather than silently missing. A later
head which was never previewed/planned records its nearest existing delivery,
head, or cue identity plus typed `NOT_MATERIALIZED_DUE_TO` entries for the
`VISUAL_TRANSACTION` and `CLIP` categories; the evidence owner must not invoke
mapping/planning to invent concrete IDs. Clip-level blocked edges are required
only for clips already materialized by an issued transaction.
Siblings which lawfully completed remain completed.

The production owner publishes its immutable stage fact to the in-memory
ledger before invoking any fallible external evidence subscriber or mounted
view. Ledger append never calls back into the journal, queue, renderer, store,
or recovery owner. Snapshots are copy-isolated, carry ledger sequence range and
content digest, and expose no mutable production objects. Reentrant or throwing
subscribers therefore cannot reorder, duplicate, erase, or manufacture causal
facts.

One versioned reconciliation JSON document and the mounted diagnostic UI render
the same structured chain whenever the view is healthy. A deliberate view-
failure case instead asserts the truthful observational code
`EVIDENCE_VIEW_DEGRADED`, `view = DEGRADED`, and the still-readable JSON/health
channel. When frame/cue identity exists, no healthy surface may display root
cue `unknown`, a generic
`control_plane_failure`, or an unscoped stack as the primary cause. Console
stacks may be attached as secondary artifacts only.

Evidence publication is immutable, best-effort, and non-authoritative. A
throwing subscriber, failed evidence persistence write, reconciliation/debug-
UI renderer fault, or evidence schema migration is recorded only on the
observational track and cannot reject a lawful head, alter queue settlement,
request authenticated recovery, or mutate presentation truth. A production
asset/GPU/clip/scene fault remains a causal presentation outcome and does
determine its normal settlement/recovery path. Independent W_i parity remains
a mandatory test oracle, but its mismatch never becomes the causal node that
blocks live presentation. Persistence is bounded, versioned, quota-safe, and
uses the production startup cleanup owner from §8.10; malformed or old evidence
cleans/quarantines without crashing startup or deleting scoped valid
profile/replay/preferences. A denied/quota-failed write emits the typed
`EVIDENCE_NOT_DURABLY_PERSISTED` observational incident. The current in-memory
chain remains inspectable until owner teardown, but the system and tests make
no claim that it survives that teardown.

Every observational incident cites the ledger sequence range and strongest
authenticated real identity present when it occurred, but it has no `BLOCKS`
edge. Before any delivery/head, that identity is only the evidence-owner root;
product identities remain explicitly null. If publishing the mounted view
fails, the JSON snapshot and health channel still identify view degradation;
if persistence fails, the mounted in-memory view says
`EVIDENCE_NOT_DURABLY_PERSISTED`. Neither may masquerade as a product renderer,
asset, GPU, clip, or scene failure.

Failure of the core in-memory evidence append itself is not silently converted
to success. A dependency-minimal bounded health channel records
`EVIDENCE_CAPTURE_FAILED` with the evidence-owner identity plus any strongest
authenticated incident/head/delivery identity already known, ledger sequence
range, and stable rule ID without invoking the normal subscriber or
persistence path. Gameplay still follows the real production outcome, but
every qualification/release case fails immediately.
The plan makes no impossible guarantee for process termination or exhausted
memory; it guarantees that every tested recoverable evidence failure is typed,
visible, and non-authoritative rather than lost or misclassified.

Ledger acceptance invariants are closed and data-driven:

- in a healthy ledger, every production-issued node appears exactly once and
  has one legal monotonic transition sequence ending in exactly one terminal
  status; an injected ledger-core failure must instead trip the independent
  `EVIDENCE_CAPTURE_FAILED` qualification failure;
- causal order derives from issued identities and sequence numbers, not wall-
  clock ordering; timestamps are monotonic diagnostic facts only;
- every edge references an existing node, except typed category-level
  `NOT_MATERIALIZED_DUE_TO` anchored to the nearest real identity;
- there are no orphan nodes, duplicate roots, overwritten first failures, or
  silent descendants;
- serialization is deterministic and privacy-safe for the exact perspective;
  objective/private facts never enter subjective evidence;
- bounded compaction operates on whole completed incidents, never by deleting
  or replacing the first node inside a retained in-budget incident. A completed
  older incident may be evicted only by the declared retention policy or
  explicit export/acknowledgement. Its bounded tombstone contains incident ID,
  first-node identity, terminal/blocked/materialization counts, detail digest,
  eviction reason, and durable-export identity when one exists;
- when capacity needs an eligible completed victim, selection is deterministic:
  lowest terminal ledger sequence first, then stable incident ID. Active or
  unresolved incidents are never silently selected, wall time is never a
  tie-breaker, and export/acknowledgement changes eligibility only through its
  own recorded ledger event;
- overflow is explicit and total rather than an exception to the invariants.
  Each root/incident has a declared node and byte budget with capacity reserved
  for `INCIDENT_DETAIL_OVERFLOW`, `FIRST_FAILURE_AFTER_OVERFLOW`, and a final
  incident summary. Before the next detail would consume that reserve, the owner
  appends the overflow marker, freezes the retained prefix including the first
  node, and switches to a fixed-size monotonic overflow accumulator containing
  omitted counts by node kind, first/last omitted sequence, and rolling digest.
  No later concrete detail node is claimed as captured. If the incident's first
  causal production failure occurs only after detail overflow, the owner uses
  the dedicated reserved node exactly once to retain its strongest real issued
  identity, stage, outcome, sequence, and causal anchor; it never reconstructs
  descendants or overwrites that first failure. If no such failure occurs the
  node remains unused. Final settlement occupies the reserved summary slot.
  The capture dimension becomes `INCOMPLETE_OVERFLOW`, and qualification fails;
- the global incident budget also reserves one
  `GLOBAL_CAPTURE_SATURATED` accumulator. If all retained incidents are active
  or unresolved and no completed victim exists, a new root is not partially
  constructed: the accumulator records root kind, first/last rejected ledger
  sequence, count, and rolling digest. It also has one fixed optional slot for
  the first real causal production failure observed among rejected roots,
  retaining only its strongest authenticated issued identity, stage, outcome,
  and sequence. It never creates the rejected incident or descendants. Capture
  health becomes incomplete. Gameplay proceeds, but the evidence run cannot
  qualify;
- the tombstone budget reserves one deterministic `TOMBSTONE_ROLLUP`. When the
  individual tombstone ring is full, the oldest eligible tombstone is folded
  into that rollup with count, sequence bounds, eviction-reason counts, and
  rolling digest before the new tombstone is added. The rollup truthfully says
  individual identity is no longer retained. It never masquerades as a full
  tombstone and cannot remove an active/unresolved incident;
- health is orthogonal, not one lossy enum. The snapshot reports
  `capture = COMPLETE | INCOMPLETE_OVERFLOW | FAILED`,
  `durability = PENDING | DURABLE | NOT_DURABLY_PERSISTED`, and
  `view = UNMOUNTED | AVAILABLE | DEGRADED`, plus current and sticky
  `ever_degraded` incident IDs for each dimension. Capture failure or overflow
  is sticky for that evidence-owner incarnation; later persistence/view
  recovery may change current state but cannot erase the recorded failure.
  The derived qualification state is `PASS` only when all required dimensions
  are healthy and no degradation occurred during the case.

The versioned schema declares explicit per-root/per-incident byte and node
budgets, global active/unresolved/completed incident counts, individual
tombstone count, reserved overflow/first-failure/terminal/rollup capacity, and fixed
accumulator widths. Tests fill every boundary exactly and one over. They cover
a single oversized active incident, multiple unresolved incidents with no
victim, an observational storm, persistence failure during overflow, a full
tombstone ring/rollup, dual durability+view degradation, triple
capture+durability+view degradation, and recovery/stickiness. No implementation
may hide growth behind browser quota, silently truncate a chain, vary the victim
by timing, or collapse simultaneous faults. Snapshot and mounted-view ordering
is ledger sequence first, then stable identity as a deterministic tie-breaker.
Schema validation rejects a configuration whose minimum root plus all reserved
markers/summaries cannot fit its per-incident cap, or whose global/tombstone
accumulators are not reserved inside their own caps; overflow behavior must
remain executable without attempting another unbudgeted allocation.

`product.reconciliation_fireball_blocked_chain` runs the stored
Fireball -> Haste Potion -> Fireball -> Invisibility removal -> death -> Turn
End trace. The ledger and mounted UI must agree exactly on which heads, cues,
transactions, clips, assets, and stateSync operations completed, which first
failed, which were blocked, and whether an earlier upstream cue omission was an
observed divergence rather than a client node failure. The preserved pre-fix
trace's privileged pipeline artifact must prove the objective/subjection
omission directly. Its mounted product view may render
`EXPECTED_CUE_NOT_EMITTED` with no invented transaction/clip only when the real
server supplies the authenticated perspective-safe diagnostic; otherwise it
truthfully renders `PRESENTATION_DIAGNOSTIC_UNAVAILABLE`. The corrected lawful
trace must not report an omission. It has one successful canonical branch in
which all expected visuals complete and one naturally triggerable failure
branch using a versioned product content/media fixture through normal backend,
catalog, UI, and renderer paths. It does not call private stage-fault hooks.

Stage injection is split by real test boundary. SDK/pipeline cases inject
delivery/decode/follower/journal/preview and pre-render production-composition
failures through public injectable transport and deterministic clock adapters.
UI cases inject
staging, asset resolution/load/GPU, clip, watchdog, scene barrier, reset, commit
uncertainty, and stateSync outcomes through the exact mounted composition root.
These layer cases exercise every discriminator and materialized
`NOT_STARTED_BLOCKED_BY`/`NOT_MATERIALIZED_DUE_TO` relation. The owned product
case proves natural composition and mounted evidence; it is not a universal
private fault injector.

The reconciliation runner also checks the ledger as a feature boundary in its
own right. Given a serialized sequence of production-issued evidence events,
one data-driven `check_reconciliation_case` asserts the normalized JSON,
mounted-view model, health, retention/tombstone result, and privacy projection.
This check does not execute gameplay or plan presentation work. It makes adding
a new stage, transition, compaction rule, or malformed-input case data-only and
keeps ledger schema testing fast enough for the default check.

The mounted view is a read-only rendering of the normalized snapshot. It shows
incident root kind, the independent current/sticky capture, durability, and
view dimensions, first causal node, completed and failed siblings, blocked
materialized nodes, unmaterialized categories, first observed divergence,
recovery links, and observational incidents. It provides
copy/export of the same redacted JSON and never reads the journal, queue,
scene, or asset services to reconstruct missing facts. The test compares
normalized view-model data and export bytes; screenshots are supplemental
layout evidence only.

Non-vacuity is strict: a console stack alone, combat log alone, final cursor
equality, generic `control_plane_failure`, cue-count equality, or final scene
snapshot cannot satisfy this vertical.

### 8.13 Escaped-regression postmortem and first-red replacements

This table is a required migration artifact, not historical commentary. At
Checkpoint 0 the inventory owner records the exact pre-surface test file hash,
command, input, and oracle for every row. If later source inspection disproves
one description, the row is corrected before implementation; it is never
dropped merely because the old test was renamed. “Nearest” means the old green
test which most plausibly appeared to cover the feature, not a claim that the
test caused the defect.

| Escaped feature | Nearest maintained pre-surface test/command | Exact old input and oracle | Why the green result was vacuous; severity | First red replacement |
| --- | --- | --- | --- | --- |
| Remembered corpse prefix parity | `uv run pytest tests/manual/test_120_subjective_world_projection.py` and `npm run render-parity-live:smoke` | The Python case projected one already-known corpse through visibility loss; the live parity gate compared its selected/final diagnostic snapshot. | Neither drove real multi-target damage/death through every W_i nor compared the independent oracle, emitted patches, SDK authoritative frontier, and drained presentation frontier at the same prefixes. The faulty independent manifest could omit the corpse while canonical memory remained lawful. **P0 diagnostic false alarm.** | `pipeline.multi_target_death_corpse_memory_prefix_parity` |
| Fireball -> Haste -> Fireball -> death head liveness | `npm run presentation-head-drain-live:smoke`, `npm run replay-presentation-head-drain:smoke`, and per-family mapper tests | Synthetic isolated heads exercised selected NORMAL/RESET/terminal and recovery outcomes; each fixture ended at its own expected token/cursor, while mapper cases classified already-present spell cues. | No real server-produced cross-family chain tested both production and consumption. Exact captured objective events 1058..1100 disclosed the second Fireball, but the fatal subjective frame omitted its root cue after the observer died; separately, the first Fireball cue existed while its FX/popup did not settle. Per-family green cases caught neither producer omission nor the first blocked consumer node. **P0 playable presentation stall and projection omission.** | producer-disclosure and consumer-ledger branches of `pipeline.enemy_fireball_haste_fireball_death_head_liveness` plus `product.reconciliation_fireball_blocked_chain` |
| Haste-potion semantic visual | `npm run potion-animation:smoke` | A constructed Drink Haste cue plus Haste child cue was mapped; the old fixture explicitly accepted `actor_clip = Taunt` and observed generic transaction/body/effect callbacks. | Cue mapping and callback presence did not require a recognizable potion prop/feedback and condition-gain visual in the mounted scene. **P1 semantic feedback loss.** | `ui.haste_potion_semantic_visual` |
| Continuous multi-tile walking | `npm run movement-animation:smoke` and `npm run locomotion-presentation:smoke` | One authored path intent and a family table asserted Walking start/end, anchors, profile, and terminal behavior. | Production emits adjacent two-anchor per-Step cues with distinct presentation IDs, and the old owner deleted its session in each intent's `finally`; MoveClip therefore forced Walking -> Idle per tile. A single path fixture never proved a presentation-owned body-cycle lease across obs4/5/6/7 or obs63/64/65 without hidden-route inference. **P1 visible animation regression.** | `pipeline.multi_tile_walk_continuous_cycle` plus its mounted motion representative |
| Fire Bolt atlas/device limit | `npm run presentation-asset-service:smoke`, `npm run animation-readiness:smoke`, and `npm run icons:validate` | Small fixture assets/catalog references were resolved and declared media was checked for catalog/readiness properties. | No gate compiled the shipped Fire Bolt atlas dimensions against a real browser's `MAX_TEXTURE_SIZE`, uploaded the actual media, or required recognizable FX and a committed head. The 9216-wide atlas reached an 8192 device; the later recovery microtask could reset/destroy the committed scene before replacement catch-up, producing black output. **P0 renderer loss.** | Both branches and real recovery-microtask assertion of `ui.fire_bolt_atlas_policy_and_authored_visual` |
| Acid Splash one-of-two completion | `npm run presented-affordance-lease:smoke` and `npm run action-ui-authority:smoke` | Constructed leased rows checked `num_projectiles = 2` maximum semantics, helper-driven Finish/max submission, and static Enter ownership. | The old checks did not mount the real action bar with at least two lawful targets, select exactly one, activate Finish and Enter separately, observe one network request, and continue through mechanics/presentation. **P0 command path unavailable.** | `product.acid_splash_single_target_finish_and_enter` |
| Water material authoring | `uv run pytest tests/engine/test_spell_families.py` and `npm run static-board-sync:smoke` | Engine tests used canonical `water_factory`; the UI fixture manually installed generic tile/material data and asserted board synchronization. | The shipped arena constructed a Water-named tile without the factory sprite contract, and world projection truthfully fell back to `floor.png`. Neither test inventoried scenario tile recipes through wire to mounted semantic material/swim facts; name-based appearance was deliberately not an oracle. **P1 content/render drift.** | `product.water_material_render` |
| Default sorcerer Invisibility inventory | `uv run pytest tests/progression/test_schema2_character_materialization.py`, `npm run character-content-summary:smoke`, and `npm run condition-presentation:smoke` | Focused tests proved materialization generally and that an Invisibility presentation recipe/key existed. | Existence of the spell and its visual recipe did not freeze `hero.sorcerer_l5_standard_torch` from creation through materialization and available actions; the authored default list could omit Invisibility while every generic check stayed green. **P1 canonical content drift.** | `server.default_sorcerer_invisibility_inventory` plus product representative |
| Position-only SpatialEffect contract | `uv run pytest tests/manual/test_121_canonical_presentation_mapper.py`, SDK replication tests, and `npm run presentation-disposition-matrix:smoke` | Python emitted a selected spatial cue; SDK tests rejected malformed geometry; UI used a hand-constructed structurally complete spatial cue. | The three layers did not consume the same lawful serialized position-only cue, so incompatible Python/SDK/Neuro assumptions could all pass separately. **P0 cross-contract failure.** | `pipeline.position_only_spatial_effect_contract` |
| Diagnostic subscribers are non-authoritative | `npm run render-lifecycle-isolation:smoke`, `npm run presented-affordance-lease:smoke`, and replay drain diagnostic callbacks | Selected debug/lease/replay callbacks threw while a narrow owner was asserted to continue. | No shared real live-head case injected inconsistent parity plus throwing coverage/reconciliation subscribers at queued/started notifications. The production diagnostics notifier called subscribers synchronously outside ClipQueue's defensive catch, so an observer could change admission/settlement. **P0 diagnostic control-plane inversion.** | `pipeline.diagnostics_best_effort_non_authoritative` and §8.12 observational-incident cases |
| Canceled-generation mutation sinks | `npm run replay-presentation-head-drain:smoke`, `npm run clip-queue-liveness:smoke`, and `npm run render-lifecycle-isolation:smoke` | Selected late visual completions/tokens were released after replay seek or queue generation cancellation. | The fixtures did not stall and release every entity, weapon, condition, terminal, and store mutation sink across a real live replacement. Untested sinks could still mutate B. **P0 stale-authority corruption.** | `pipeline.cancelled_generation_mutation_fenced` plus §8.9 live A -> B cases |
| Nonzero/negative grid origin | `npm run static-board-sync:smoke` and `npm run render-anchors:smoke` | Static board used `gridBounds` starting at `(0,0)`; anchor tests varied actor-rig pixel offsets, not board-world minima. | Neither case mounted a board whose canonical cells cross negative/nonzero world coordinates and checked the same transform for material, light, overlays, hit testing, camera, and actors. **P1 scene misregistration.** | `ui.nonzero_negative_grid_origin` |
| Pre-try storage failure | `npm run presentation-persistence-cut:smoke`, `npm run studio-document-history:smoke`, and `npm run startup-transport-failure:smoke` | Valid/malformed selected values were read or written after their fixture owner had initialized; transport failures occurred after ordinary startup code entered its guarded path. | A synchronous `localStorage`/`sessionStorage` getter or write throwing before the old `try` boundary could reject startup with no mounted recovery surface. **P0 startup crash.** | `product.pretry_storage_failure_ui` and §8.10 quota/denied-write cases |
| Decorative callback after claimed terminal | `npm run clip-queue-liveness:smoke`, `npm run replay-presentation-head-drain:smoke`, and Studio presentation smokes | Fixtures awaited the clip/transaction's returned terminal and checked queue/head completion; selected late queue completions were fenced. | A decorative BannerClip could return immediately, leave requestFrame alive, be reported complete, then fault after Studio stateSync destroyed its HUD container. No inventory tied every callback/timer child to a resource lease whose terminal gates node completion across live/replay/Studio. **P0 post-terminal page fault and false ledger success.** | `ui.decorative_callback_resource_lease_lifecycle` plus §8.9 resource-lease matrix |

The reconciliation vertical has its own escaped-evidence rows because a green
ledger which cannot identify the first fault is itself a product failure:

| Escaped evidence feature | Nearest maintained pre-surface test/command | Exact old input and oracle | Why the green result was vacuous; severity | First red replacement |
| --- | --- | --- | --- | --- |
| Delivery-admission identity | `npm --prefix sdk/typescript test` and `npm run player-replication-boundary:smoke` | Individual malformed payloads or source checks asserted a typed throw/resync and selected source-level diagnostic fields. | There was no versioned delivery incident root, normalized wire/request identity, or JSON/UI projection; failures before head acceptance were later reported as generic presentation faults or forced into nonexistent head fields. **P0 diagnosis loss.** | `DELIVERY_ADMISSION_INCIDENT` data cases in `check_reconciliation_case` |
| Pre-delivery evidence-owner failure | `npm run presentation-persistence-cut:smoke`, `npm run studio-document-history:smoke`, and diagnostics view smokes | Selected persisted/view data was exercised only after a product or Studio owner had already initialized. | Malformed migration, denied first write, or view failure can precede every connection/delivery/head, so forcing it into delivery/head evidence would fabricate product identity or drop the fault. **P0 startup/diagnosis loss.** | `EVIDENCE_OWNER_INCIDENT` startup/view/persistence cases |
| Accepted-head causal chain | `npm run presentation-head-drain-live:smoke`, `npm run clip-queue-liveness:smoke`, and replay drain smoke | Individual fixtures asserted drain/queue terminal, token behavior, or a diagnostic callback. | The tests did not require one immutable production-issued chain spanning head/cue/recipe/asset/transaction/clip/stage/stateSync identities or preserve the first failure across reset/terminal. **P0 diagnosis loss.** | `ACCEPTED_HEAD_PRESENTATION_INCIDENT` stage matrix |
| Materialized versus never-created descendants | `npm run presentation-head-drain-live:smoke` and `npm run replay-presentation-head-drain:smoke` | The fixtures stopped at a selected failed head and asserted that later presentation did not complete or that the drain stopped. | Absence did not say whether a real node was queued then blocked or never planned at all. A proposed diagnostic could have invented transaction/clip IDs by running a second planner. **P0 misleading evidence.** | `NOT_STARTED_BLOCKED_BY` and `NOT_MATERIALIZED_DUE_TO` reconciliation cases |
| Causal product fault versus evidence fault | Throwing diagnostic-callback cases in lease/replay/render isolation smokes | A selected subscriber threw and the narrow operation still returned its expected result. | There was no closed two-track vocabulary proving a real asset/GPU/clip/scene fault controls normal settlement while parity/subscriber/persistence/debug-view faults never do. **P0 authority inversion risk.** | causal-stage matrix plus observational-incident matrix |
| Omitted-cue privacy and wire identity trust | SDK malformed-envelope tests, render parity diagnostics, and mapper disposition smokes | A malformed delivery was rejected, or a privileged parity mismatch was printed, while independently constructed cues were classified. | No player-safe generated diagnostic contract distinguished authenticated perspective identity from attacker-asserted wire fields or privileged objective lineage. A client could only infer an omitted cue or leak/join private facts. **P0 privacy/diagnosis conflict.** | player-safe diagnostic authorization/non-joinability/unavailable cases plus rejected-wire quarantine cases |
| Core evidence append failure | Throwing diagnostics-subscriber smokes | A downstream observer threw and the selected production operation continued. | Nothing proved that failure of the dependency-minimal in-memory ledger itself reached a separate bounded health channel; a dead evidence core could silently report no incident. **P0 false diagnostic success.** | `EVIDENCE_CAPTURE_FAILED` fallback/qualification cases |
| Ledger durability, bounded overflow, and orthogonal health | `npm run presentation-persistence-cut:smoke` and `npm run studio-document-history:smoke` | Selected current/malformed records were retained or cleared. | No total active-incident/global/tombstone overflow policy, reserved post-overflow first-failure fact, deterministic victim order, truthful non-durability, or simultaneous capture/durability/view state existed. “Survives” could be claimed after a denied write, and an evidence storm had no bounded truthful result. **P1 postmortem loss/startup risk.** | `check_reconciliation_case` exact-limit/one-over/storm/retention/quota/migration/compound-health pack |
| Mounted JSON/debug-UI equality | `npm run live-subjective-actions:smoke`, `npm run studio-evidence-import:smoke`, and `npm run studio-coverage-workspace:smoke` | Tests inspected either a programmatic diagnostics snapshot or a Studio UI fragment for selected fields. | They did not render the same versioned chain from the same copy-isolated snapshot or forbid `unknown` when typed identities existed. **P1 misleading UI.** | mounted reconciliation view cases plus `product.reconciliation_fireball_blocked_chain` |
| Exhaustive fault injection versus product truth | No single lawful owner; prior smokes injected private fixtures independently. | Layer-specific fake frames/callbacks produced the intended local error. | Combining every failpoint into one no-mock product journey is impossible, while treating isolated injections as product proof is false. **P0 test-ownership error.** | split SDK/pipeline/UI stage matrices plus one naturally triggerable owned product representative |

The table itself is checked by the inventory runner: every row needs one
active first-red case ID, every cited old test has a keep/convert/retire
disposition, and no replacement may be marked green from a weaker layer than
the row declares.

## 9. Coverage marks and non-vacuity

Every critical negative must prove it reached the intended boundary.

For example, “empty roster did not start a game” is insufficient because the
button might be detached. The case also asserts:

- profile request completed with zero characters;
- the standard New Match control was mounted;
- the control was disabled for reason `owned_character_required`;
- compose/start request counts remained zero;
- the existing server game/source identity was unchanged.

Similarly, “forged target rejected” must prove the exact lease/action/primary
row were current so rejection occurred at the full allocation check rather
than an earlier `no lease` branch.

Critical cases list required named coverage marks. Missing or duplicate marks
fail the case. Marks are emitted by the layer runner or a read-only diagnostic
owner, never inferred by source search.

Replication sequence cases use closed mark families rather than a generic
`pipeline_reached` flag. At minimum they distinguish:

- transport connection/attachment epoch open, exact initial sync, REST
  catch-up application, reconnect, authenticated replacement, and stale
  operation rejection;
- generated decode, semantic envelope decode, follower delivery, journal
  accept/duplicate/resync, authoritative preview, and exact token ownership;
- live versus replay terminal preinstall, scene staging or rollback, planner
  disposition, causal enqueue/barrier, precommit owner/head recheck, token
  settlement, postcommit stateSync, staging release, terminal install,
  recovery, and teardown;
- prefix parity for every perspective, including emitted patch digest, SDK
  authoritative frontier, presentation frontier, and hidden/visible/omitted
  censorship branch.

The required mark set is declared by the case's operations and expectations.
For example, a REST case cannot pass with only SSE marks. A live A -> B case
cannot pass without `A_live_retired`, authenticated `B_live_installed`,
stale-live-A rejection, and live-B-only authority marks; it must not emit a
replay-destroyed mark. A concurrent replay-A case additionally requires
`replay_A_retained`, reciprocal isolation, and replay-A teardown isolation.
Only the separate replay lifecycle may emit replay-A retirement and replay-B
installation marks.

## 10. Timing, determinism, and flake policy

### 10.1 Generative and exhaustive cases

Once a boundary is expressed as data, add generated cases where they improve
confidence without duplicating hand-written examples:

- exhaustive small-domain checks for turn/action economy, target allocation,
  equipment-slot occupancy, life-state transitions, cursor relations, and
  replay segment topology;
- property-based generation of valid action/target/roster combinations, with a
  simple reference predicate where one exists;
- structured generation of valid event/frame/replay inputs followed by one
  deliberately invalid field or ordering relation;
- coverage-guided fuzzing of untrusted JSON/SSE/replay/content decoders, which
  must produce a typed error rather than crash, hang, or partially mutate;
- state-machine traces for bootstrap/follow/catch-up/reset/reconnect and
  targeting/lease/submit, checked against explicit invariants after every step;
- production-owner generation transitions with late-operation injection and a
  shrinker constrained to preserve the live A -> live B retirement boundary
  and any independent retained replay-A session.

Every randomized failure records a reproducible seed and the minimized case as
ordinary feature data. Unseeded fuzz results are not release evidence. The
critical product journey remains example-based and deterministic; fuzzing does
not replace it.

### 10.2 Non-functional feature cases

Treat user-visible quality and architectural limits as features with data
inputs and measurable outputs:

- accessibility: keyboard-only canonical journey, focus order, roles, names,
  disabled semantics, and no hidden enabled duplicate control;
- performance: startup and first-playable phase timings, pointer/render update
  scaling, journal/catch-up bounds, and synthetic 1x/2x/4x input curves where
  linear behavior is required;
- privacy: two simultaneous perspectives compared for forbidden entity,
  connector, action, combat-log, and replay facts;
- durability: process restart, saved seat, archive, replay, and consecutive
  game replacement from the same temporary durable directory;
- browser persistence: maintained current-state survival; malformed,
  prior-version, and identity-mismatched cleanup/quarantine; scoped retention
  of valid profile/replay/preferences; reload and generation replacement;
  quota/write failure; and repeated idempotent startup/teardown;
- visual integrity: semantic scene manifests and a small reviewed set of
  stable screenshots for layout/occlusion regressions, never screenshots as
  the sole gameplay assertion;
- media/device compatibility: compiled atlas dimensions, texture limits,
  shader/material identities, GPU upload failures, and deterministic optional-
  media degradation tested against representative renderer capabilities;
- security/robustness: malformed/foreign IDs, stale generations, invalid
  target allocations, unauthorized roster members, and unexpected origins;
- resource behavior: bounded queues, timers, processes, observers, render
  nodes, storage growth, and typed ownership/terminality for every RAF, timer,
  deferred continuation, decorative child, and transferred presentation
  resource lease.

These cases use the same runner/result model and timing output. They do not
create a separate unowned performance or visual test universe.

### 10.3 Deterministic inputs

- every case records its seed;
- stochastic engine choices use injected/owned seed sources;
- case order cannot affect persistent or global state;
- clocks are injected below the OS-process boundary where wall time is not the
  feature;
- OS journeys assert event/state transitions with deadlines, not exact
  millisecond animation timing;
- UUIDs/timestamps/ports are normalized only in expectations, never rewritten
  in the product.

### 10.4 No sleep-based success

Replace `waitForTimeout` success paths with waits on:

- a specific response;
- DOM/accessibility state;
- replication cursor/fence;
- scene manifest generation;
- command terminal;
- process exit/readiness;
- explicit animation/test clock completion.

A tiny event-loop yield may exist inside a deterministic runner, but cannot be
the fact that makes the assertion eventually pass.

### 10.5 Duration budgets

Record every case duration and phase duration. Initial budgets:

- engine case: target <= 100 ms, hard per-case deadline 2 s;
- server in-process case: target <= 500 ms, hard deadline 5 s;
- SDK case: target <= 1 s after build, hard deadline 5 s;
- pipeline sequence case: target <= 2 s after build, hard deadline 10 s;
- reconciliation case: target <= 100 ms, hard per-case deadline 2 s;
- UI fixture case: target <= 5 s, hard deadline 20 s;
- product journey: target <= 60 s, hard deadline 90 s unless explicitly
  reviewed as a longer release case.

Budgets are measured at the implementation baseline before enforcement. A
small number of justified outliers may receive explicit case-local budgets;
the suite cannot silently raise a global timeout.

### 10.6 Flakes are failures

The critical product journey runs repeatedly during harness qualification.
Any intermittent result is a blocker. There is no automatic retry that turns a
red first attempt green. A diagnostic rerun may be recorded separately, but
the original failure remains the run result.

An open flaky case follows `KNOWN_ISSUES.md` policy with an exact reproducer.
A P0 release journey cannot remain xfailed or quarantined while the product is
called accepted.

## 11. Command and CI topology

Define a small command surface rather than another hundred top-level scripts:

```text
test:feature:engine
test:feature:server
test:feature:sdk
test:feature:pipeline
test:feature:reconciliation
test:feature:ui
test:product:canonical
test:product:recovery
test:product:release
```

Each command accepts `--case`, `--tag`, `--list`, `--timings`, and
`--artifacts`. The same case ID runs locally and in CI.

### 11.1 Local default

The default fast check includes:

- schema validation;
- engine/server/SDK data cases that need no OS services;
- the bounded reducer/journal/presentation sequence pack after its TypeScript
  adapters are built;
- the sans-IO reconciliation schema/lifecycle/privacy/compaction pack;
- TypeScript/Python type checks;
- generated contract checks;
- static architecture policies that genuinely require source inspection.

It starts no browser or ambient server and remains self-contained.

### 11.2 Browser check

The browser check owns its Vite lifecycle and runs UI-layer cases. No external
Vite instance is required. A recursive command-graph audit proves the default
fast check contains no browser/live edge.

### 11.3 Canonical product check

The canonical product check starts fresh services and always includes:

- empty-profile block;
- real character creation;
- create/join/bootstrap/activate/playable;
- the exact mounted ordinary Move described in §8.2, including mechanics,
  replication, authored motion, final occupancy, and continued input;
- consecutive game replacement;
- one reconnect/resync journey;
- teardown/leak proof.

This is mandatory before any implementation cutoff is called accepted. It is
not replaced by all lower layers passing.

### 11.4 Recovery product check

`test:product:recovery` owns fresh processes and includes reconnect, REST
catch-up, resync, RESET, lawful live generation replacement, replay isolation,
the complete browser-persistence startup pack from §8.10, and the stored
Fireball -> Haste Potion -> Fireball -> death/Turn End cluster from §8.11,
including the reconciliation JSON/debug-UI chain from §8.12. At least one
browser-persistence case continues from cleanup through authenticated
bootstrap and a playable scene in the production-build mode. It accepts no
ambient browser profile, route interception, or startup exception suppression.

### 11.5 Release check

The release command runs the immutable generated/type/build gates, all critical
feature packs, and the canonical/recovery product checks from a clean process
environment. It writes one machine-readable manifest containing:

- source file hashes or repository revision plus dirty-tree manifest;
- exact commands;
- feature-case, trace, and reconciliation schema versions plus declared
  reconciliation retention budgets;
- case IDs and results;
- timings;
- process/environment identities;
- artifact links;
- no-skips/no-retries statement.

Reviewers rerun this command rather than reconstructing an undocumented order
of scripts.

## 12. Migration of existing tests

### 12.1 Inventory before deletion

Generate a checked-in inventory of every pytest, SDK test, and NeuroClient
script with:

- current command/owner;
- feature claims;
- public boundary used;
- route/process mocks;
- ambient service dependency;
- fixed sleeps;
- unique semantic assertions;
- replacement case IDs;
- disposition: keep, convert, merge, or retire.

No test is deleted because it is old or inconvenient. Unique semantic,
privacy, lifecycle, protocol, performance, and failure assertions are first
mapped to a maintained case or retained focused gate.

### 12.2 Keep focused layer tests

Keep tests which efficiently prove a real lower-layer contract, including
strict model validators, event mechanics, reducer invariants, privacy,
topology, and deterministic concurrency. Migrate repetitive construction into
the layer check runner where practical.

### 12.3 Convert browser scripts

Browser scripts fall into three groups:

1. UI fixture tests: convert to `ui` cases and shared browser ownership;
2. genuine live/product tests: convert to `product` cases and owned backend +
   Vite topology;
3. static source/ownership checks: keep only when the claimed property is
   architectural and cannot be observed as behavior.

Remove per-script Chromium launch, Vite assumptions, duplicated waits, and
duplicated artifact handling after equivalent cases are green.

### 12.4 Retire vacuous evidence

Retire or relabel tests which pass for the wrong reason, including:

- a forged command rejected because the test bound a different module
  incarnation and therefore had no lease;
- a product browser test whose server routes are fulfilled by the test itself;
- a live gate which never starts or proves ownership of its services;
- a negative which never proves the target control/branch was reachable;
- a source scan presented as runtime evidence.

## 13. Implementation checkpoints

### Checkpoint 0 — inventory and baseline

Deliver:

- complete test inventory;
- current command dependency graph;
- duration baseline;
- mocked/ambient/sleep classification;
- P0 journey gap report;
- exact migration map for unique assertions.

Gate: reviewers can trace every current feature claim to a future case or an
explicit retained test.

### Checkpoint 1 — schemas, check runners, and expectations

Deliver:

- version-1 case/result schemas;
- version-1 reconciliation event/snapshot/view schemas and explicit retention
  budgets;
- common loader/normalizer/diff/artifact package;
- one smoke case for every layer;
- the version-1 replication trace schema, deterministic sequence runner, and
  one server-produced trace consumed through the exact production live
  composition root plus the separate isolated replay root, with explicit
  transport epochs and no test-owned head sequencing;
- rich contextual failure output;
- explicit expectation update command;
- schema/golden self-tests.

Gate: adding a new table-driven case requires data only unless it introduces a
new public operation.

### Checkpoint 2 — owned-process product harness

Deliver:

- temp runtime/profile owner;
- dynamic port/process owner;
- backend/Vite/browser readiness and teardown;
- network/log/accessibility/screenshot artifacts;
- no-route-mock enforcement;
- process/port leak detection;
- pre-start maintained browser-storage seeding and before/after capture;
- harness self-tests for startup failure, mid-run process death, timeout, and
  teardown during partial startup, malformed/prior-version storage cleanup,
  and quota/write failure.

Gate: two product worlds can run sequentially and, where supported, in parallel
without sharing state or ports.

### Checkpoint 3 — canonical P0 journeys

Deliver the automated cases for:

- empty profile blocked before mutation;
- authoritative forged empty/invalid roster rejection;
- real character creation;
- canonical game create/join/bootstrap/activate/playable;
- the mounted ordinary Move acceptance case from §8.2 in owned dev and
  production-build modes;
- consecutive game replacement;
- raw deferral vs generic conflict and bounded retry;
- clean teardown.

Gate: this reproduces the exact journey that escaped the former suite and fails
against the pre-fix product for the correct reasons.

### Checkpoint 4 — recovery and high-risk product packs

Deliver the declared fast layer cases and the specifically named product
representatives for:

- disconnect/reconnect/REST catch-up/resync/reset;
- saved seat and multiple controlled actors;
- action targeting and turn authority;
- movement/connector/hidden transition;
- inventory/equipment;
- combat/life-state/terminal;
- archive/replay/Studio teardown;
- the complete §8.11 live-regression cluster, including the stored ordered
  combat trace, first-blocked-head localization, corpse-memory prefix parity,
  continuous multi-tile motion, successful repaired Fire Bolt authored media
  plus legacy device-limit handling, Acid Splash one-of-two input/cast with two
  lawful choices and with one discoverable choice, water material, default
  sorcerer content, and every adjacent audit case;
- the decorative-resource lifecycle matrix across live, replay, and Studio,
  including BannerClip, FloatingText, and every inventoried RAF/timer/deferred
  child through stateSync, terminal, reset, seek, destroy, and generation
  replacement, with no post-terminal callback or false early completion;
- the §8.12 reconciliation observability vertical: exhaustive delivery and
  pre-render injections at the SDK/pipeline owners, mounted
  staging/asset/GPU/clip/scene/commit/stateSync and evidence-view injections at
  the UI owner, and one naturally triggerable no-interception product
  representative; all prove first-causal-node retention, typed blocked versus
  unmaterialized descendants, JSON/debug-UI equality, reset/death/terminal
  retention, and bounded quota-safe persistence with truthful non-durability;
- lawful live generation A -> B with reset/fault, stale-live-A injection, and
  an independently retained replay-A session;
- separate replay-A retirement/replay-B installation and reciprocal
  live/replay late-operation isolation;
- the owned browser-persistence startup pack covering valid, malformed,
  prior-version, identity-mismatched, mixed-scope, quota/write-failure, reload,
  generation-replacement, and repeated-cleanup cases;
- the complete lawful, transport/state-machine, live-generation-replacement,
  replay-lifecycle-isolation, and single-fault reducer sequence packs,
  with minimized checked-in failures and browser presentation representatives.

Gate: each high-risk seam has its nearest fast layer coverage and every product
representative explicitly required by §§8.11-8.13 is green. A private
layer-injected fault does not acquire a fabricated product representative.

### Checkpoint 5 — existing-suite migration

Deliver:

- converted UI/product cases;
- retained focused tests with declared claims;
- removal of ambient service assumptions and duplicated browser launch code;
- removal of fixed success sleeps;
- simplified package/CI command graph;
- zero unmapped active test claims.

Gate: no deleted test owned a unique assertion; the migration manifest proves
the replacement.

### Checkpoint 6 — release gate and independent qualification

Deliver:

- one self-contained release command;
- immutable run manifest;
- repeated clean canonical runs;
- timing budget enforcement;
- no retry/skip/leak proof;
- documentation for local reproduction and failure artifact reading.

Gate: internal, engine-external, and NeuroClient-external reviewers each rerun
the same frozen cases from clean owned services. Manual/model clicking is not
accepted as evidence.

## 14. Harness self-tests

The testing system itself must prove that it fails when it should.

Required self-tests include:

- schema rejects unknown/ill-typed fields;
- a server case which omits application lifespan cannot emit startup/teardown
  coverage marks or satisfy a lifespan-owned feature claim;
- expectation mismatch produces a semantic diff;
- update mode changes only the selected expectation;
- unexpected request fails a product case;
- product route interception is rejected;
- an ambient listener on a requested port cannot be mistaken for the owned
  process;
- backend or Vite early exit fails with captured logs;
- browser page/console error fails unless explicitly expected;
- browser persistence seeding rejects unmaintained keys and cannot satisfy a
  case unless the production pre-parse startup owner emits the exact maintained
  key/schema coverage mark;
- malformed/prior-version/identity-mismatched startup self-tests prove scoped
  cleanup or quarantine without deleting valid profile/replay/preferences;
- quota/denied-write self-tests prove one recoverable diagnostic, preservation
  of the last valid value, and idempotent reload/teardown rather than exception
  suppression;
- an over-device-limit atlas self-test proves rejection occurs before GPU
  upload and leaves a visible scene plus one deterministic transaction terminal;
- the Fire Bolt recovery self-test advances beyond the synchronous asset-fault
  latch through the real restart/reset microtask and a failed replacement
  catch-up, continuously proving the last committed scene remains visible;
- decorative-resource self-tests release a retained RAF, timer, and deferred
  callback after apparent clip settlement and then run stateSync, terminal,
  reset, seek, destroy, and generation replacement. The central resource-lease
  owner must either keep the node nonterminal or fence the callback; a claimed
  completion followed by `LATE_CALLBACK_AFTER_TERMINAL`, page error, or scene
  mutation fails in live, replay, and Studio;
- multi-step locomotion self-tests use the stored one-edge sequences and prove
  per-head position/token settlement plus continuous body-cycle phase, followed
  by every explicit safe terminal boundary and stale-generation rejection;
- the stored Fireball/Haste/Fireball/death trace self-test deliberately wedges
  one selected head and proves the harness reports that first blocked head,
  while later server/log progress cannot produce a false pass;
- reconciliation self-tests use the declared owner for each stage: SDK/pipeline
  admission and pre-render failures, mounted UI presentation failures, and
  non-authoritative evidence subscriber/view/persistence failures. They add
  later reset/death/terminal and malformed/quota evidence cases; the original
  first causal node, materialized blocked edges, unmaterialized category marks,
  and ledger health remain exact. Evidence-only faults leave live admission and
  settlement unchanged, while real production presentation faults retain their
  normal queue/recovery semantics;
- evidence-root self-tests cover malformed startup migration, denied first
  write, and mounted-view failure before any delivery/head, proving exact null
  product identities, idempotent duplicates, and conflicting event-ID
  rejection without synthesizing a delivery root;
- identity/privacy self-tests feed forged but well-formed source/generation/
  perspective fields and prove they remain quarantined, then compare two
  perspectives for non-joinable expectation IDs and no undisclosed objective
  lineage/content. Diagnostic-unavailable cases never infer an omitted cue;
- reconciliation capacity self-tests cover exact-limit and one-over writes,
  one oversized active incident, multiple unresolved incidents with no victim,
  observational storms, reserved final summaries, persistence failure during
  overflow, and full tombstone rollup. They assert retained first node,
  incomplete-detail marker/counters/digest, the dedicated first-failure slot
  when the first failure occurs only after detail overflow, the global
  saturation first-failure slot when no root can be admitted, no fabricated
  nodes, deterministic completed-victim order, invalid reserve-configuration
  rejection, and no effect on gameplay;
- reconciliation health self-tests inject durability and view degradation
  together, then capture overflow/failure as a third dimension. Current and
  sticky states, recovery, JSON, health channel, and mounted fallback preserve
  all simultaneous facts rather than applying precedence;
- deadline cancels and joins all work;
- teardown during partial backend, Vite, browser, or stream startup is clean;
- a leaked child/process/port fails the case;
- redaction removes tokens/secrets but retains discriminators and identities
  required for diagnosis;
- a missing coverage mark fails a non-vacuity assertion;
- a lawful server trace which cannot decode, reduce, project, plan, or settle
  fails at the exact stage with the full minimized prefix;
- a one-fault trace rejected at an earlier unintended boundary fails its
  non-vacuity mark;
- the shrinker preserves the original failure class and causal graph;
- duplicate case IDs and unmapped release tags fail discovery;
- default fast command graph cannot reach browser/live commands;
- product release manifest reports any skip or retry as failure.

## 15. Review and immutable-cutoff protocol

At every checkpoint, submit:

- exact source and fixture hashes;
- feature-case, trace, and reconciliation schema versions plus declared
  reconciliation retention budgets;
- added/changed case IDs;
- red-first evidence where correcting a known gap;
- green commands and counts;
- timing table;
- skipped/retried cases (expected to be zero for acceptance);
- known environmental limitations;
- artifact location for at least one deliberately induced self-test failure.

Reviewers inspect the case meaning, not only runner code. A green case is
rejected if it mocks the authority it claims to test, reaches the wrong branch,
depends on ambient services, or asserts absence without positive reachability.

Implementation acceptance requires three fresh verdicts on one immutable
cutoff:

1. internal architecture/behavior review;
2. engine/server external review;
3. NeuroClient external review.

No acceptance transfers across source drift. A real canonical failure revokes
the release claim even if lower-layer tests remain green; the failing journey
becomes or strengthens a permanent automated case before refreeze.

## 16. Completion criteria

This plan is complete only when all of the following are true:

- a developer or CI worker can run the canonical player journey with one
  command and no prestarted services;
- the run begins from a fresh temporary profile and uses the real UI, Vite
  proxy, FastAPI server, SDK, journal, renderer, and command path;
- empty profile, invalid direct roster, valid character/game, and consecutive
  replacement cases are green;
- generic bootstrap conflicts cannot be mistaken for deferrals or retried
  forever;
- the mounted ordinary Move in §8.2 is proven from lease/target through engine
  cost/state, replication/log delivery, authored animation, final presented
  occupancy, and continued input in both dev and production-build modes;
- recovery, terminal, and replay representatives are automated;
- lawful live generation A -> B retirement/isolation and stale-live-A
  rejection are proven without destroying an open replay-A session; reciprocal
  late-operation isolation and the separate replay-A -> replay-B lifecycle are
  proven through their own production owners;
- maintained browser persistence is exercised from pre-start seeded current,
  malformed, prior-version, identity-mismatched, mixed-scope, and quota/write
  states through production cleanup/quarantine, authenticated playable
  bootstrap, reload/generation replacement, and idempotent teardown with valid
  profile/replay/preferences preserved;
- every named §8.11 regression is automated at its exact owner, the stored
  Fireball/Haste/Fireball/death sequence drains every head through both
  production live and replay roots, and its product representative proves the
  corresponding semantic visuals without manual judgment;
- every presentation-owned RAF/timer/deferred/decorative resource has a typed
  lease and terminal across live, replay, and Studio; stateSync, reset, seek,
  destroy, terminal, and generation replacement leave no late callback able to
  touch destroyed state, and a node cannot qualify as complete while owned work
  remains live;
- multi-step disclosed movement commits each head independently while one
  explicitly authorized body-cycle lease preserves phase across compatible
  fragments and ends only at a contract-owned observable boundary, never from
  inferred hidden path geometry or timing;
- the maintained §8.12 reconciliation JSON and mounted debug UI agree on the
  exact first failed causal node and, while capture is complete, all
  completed/failed/blocked descendants. They retain that truth in memory across
  later reset/death/terminal; report bounded persistence failure without
  promising post-teardown survival; expose capture, durability, and view health
  as simultaneous dimensions; preserve whole-incident/tombstone/rollup
  invariants when durable storage succeeds; and report explicit incomplete
  overflow rather than silent truncation. They never use generic/unknown
  evidence when authenticated typed delivery/head/cue identity exists and never
  promote quarantined wire/objective-private fields into subjective identity;
- every classified engine/server presentation family has a real lawful trace
  that reaches generated decoding, the journal/reducer, render projection, and
  its expected presentation disposition without manual play;
- generated invalid traces prove exact typed failure/resync behavior and no
  partial state, while stored seeds/minimized traces reproduce every failure;
- every background resource is awaitable and leak-checked;
- critical success does not depend on `waitForTimeout`, manual/model clicking,
  route mocks, or ambient ports;
- every active test has an explicit feature claim and layer;
- every retired test's unique assertions have a recorded replacement;
- fast lower-layer checks remain practical during development;
- slow product checks are explicit, self-contained, and mandatory for release;
- failure artifacts make the next defect diagnosable without reproducing it by
  hand;
- the same immutable cutoff receives all required independent reviews.

Until those criteria are met, build success and isolated smoke success are
valuable diagnostics but are not evidence that the application is playable.
