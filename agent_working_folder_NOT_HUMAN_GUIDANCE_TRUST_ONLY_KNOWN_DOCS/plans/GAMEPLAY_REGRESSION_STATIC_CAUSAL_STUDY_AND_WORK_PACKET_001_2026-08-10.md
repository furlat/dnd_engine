# Gameplay Regression Static Causal Study and Work Packet 001

**Status:** DRAFT REVISION 4 — GATE A TECHNICAL REVIEW NOT YET COMPLETE

**Date:** 2026-08-10

**Project scope:** Neurodragon (`dnd_engine` and `NeuroClient`)

**Authority:** Explicit human instruction to preserve the static BUG-001 through
BUG-034 study and prepare the first bounded work packet. This document does not
authorize production implementation, test implementation, or test execution.

**Planner:** Planner / External Reviewer 1,
`019feabb-5319-7f22-9993-88a65be261ea`

## 1. Human direction and non-negotiable outcome

The work is not merely to patch the currently visible regressions. Neurodragon
needs clean, inspectable information-transition boundaries so a lawful engine
sequence can be passed through the real downstream owners and every missing,
rejected, transformed, state-only, visual, or terminal fact can be identified
before a person has to discover the gap by playing the game.

This must not create a parallel runtime, a second mapper, a second reducer, a
generic event bus, broad serialization infrastructure, permanent hot-path
telemetry, or a large test framework which slows the product and development.
The first packet therefore proves the approach at one current broken seam by
reusing existing production types and functions.

## 2. Governance and acceptance

All findings, questions, assignments, revisions, and verdicts route through the
Planner. Implementation and Tester work must not begin before Gate A reaches
global acceptance.

| Gate A participant | Role | Current state |
| --- | --- | --- |
| External Reviewer 1 | Planner and whole-plan reviewer | Revision 3 CHANGES REQUIRED; Revision 4 re-review pending |
| External Reviewer 2 | Backend and server-contract reviewer | Revision 3 APPROVED; Revision 4 re-review pending |
| External Reviewer 3 | Frontend and presentation-lifecycle reviewer | Revision 3 APPROVED; Revision 4 re-review pending |
| External Reviewer 4 | Scope, duplication, serialization, and slop reviewer | Revision 3 APPROVED; Revision 4 re-review pending |
| Coordinator | Verifies roles, routing, boundaries, and completed review gate; not a technical vote | Revision 1–3 blind dispatches verified; Revision 4 dispatch pending |
| Human | Final authority | PENDING |

Technical approval requires unanimous approval from External Reviewers 1–4.
Global acceptance additionally requires human acceptance. A sub-agent
self-review is mandatory before Reviewer 1 records a formal verdict. The word
`DONE` must not be used while any required verdict is missing or conditional.

Every review round is dispatched by the Coordinator simultaneously and blindly.
All four verdicts for a frozen revision are recorded before findings are
consolidated into the next revision. Re-review must again use the same revision
for every reviewer; no implementation or testing packet may be dispatched
between reviewer verdicts.

## 3. Sources and method

This study is based on static source tracing only. No application, service,
test, build, generator, browser, or gameplay session was run while producing
the causal findings.

Primary sources:

- `agent_working_folder_NOT_HUMAN_GUIDANCE/USER_REPORTED_GAMEPLAY_AND_PRODUCT_REGRESSION_LEDGER_2026-08-10.md`;
- current `dnd_engine` mechanics, player-replication contracts, projector,
  runtime, and TypeScript SDK source;
- current `NeuroClient/app/src` ingestion, mapper, queue, renderer, state-sync,
  startup, diagnostics, Studio, and product source;
- `HOW_TO_TEST.MD`;
- the preserved broad testing-surface plan, used as historical design input
  only and not adopted wholesale.

Classification:

- **LIVE:** the defective mechanism is directly present in current source;
- **MIXED:** a correction exists, but an adjacent or incomplete path remains;
- **GUARDED:** the exact reported mechanism appears corrected in current
  source. This is a static source conclusion, not product acceptance.

Static result: 23 LIVE, 7 MIXED, and 4 GUARDED rows.

## 4. Architectural conclusion

Neurodragon is strict inside individual layers but not compositionally strict
across the complete information path. Independent validators, projections,
mappers, authoring resolvers, diagnostics, and lifecycle owners can each be
locally consistent while disagreeing about the same lawful fact.

The recurring causes are:

1. **No end-to-end conservation rule.** A semantic fact can be emitted,
   censored, patched, folded, cloned, or omitted without one stable receipt
   proving its final disposition.
2. **Parallel authorities.** Python contracts, hand-written SDK validation,
   frontend mapping, diagnostics, and product policy sometimes decide the same
   question independently.
3. **Unstable identity across transformations.** Authoritative cue accounting
   depends on JavaScript object identity even when authoring rewrites clone the
   intent.
4. **Mismatched lifecycle scopes.** Causal batch, journal head, queue
   generation, transaction, timer, renderer host, partition, and product
   session do not share one explicit ownership/retirement relation.
5. **Fail-closed amplification.** One correct local rejection blocks a journal
   head; recovery can then destroy otherwise valid presentation state, making
   one mapping defect appear as multiple gameplay failures.
6. **Tests entering halfway through the path.** Hand-built frames, stores,
   intents, routes, or browser state can prove a downstream fixture is
   accepted without proving the upstream owner can lawfully produce it.
7. **Harness false confidence.** Stale fixtures, asynchronous polling,
   label-coupled navigation, and ambient processes can become green or fail
   before reaching the claimed behavior.

The corrective pattern is one bounded vertical slice at a time:

```text
real upstream value
    -> real serialization/contract boundary
    -> real downstream consumer
    -> one immutable ID-based transition receipt
    -> explicit accepted / state-only / visual / rejected / terminal result
```

Receipts are values returned by the existing owner. They are not an event bus,
not persistent telemetry, and not a second control plane.

For Work Packet 001 the receipt is immutable but ephemeral within one journal
head. Cue `presentationId` and disposition semantics are authoritative at this
boundary. Transaction-local `intentEvidenceIds` are traversal evidence only:
they must not become durable/public identity, be serialized or persisted, or
be asserted by exact string/order in tests.

## 5. Static causal ledger

### BUG-001 through BUG-015

| ID | State | Static cause in current source |
| --- | --- | --- |
| BUG-001 | LIVE | The presentation coordinator drains one head and blocks on any candidate, mapping, staging, asset, enqueue, or execution failure. BUG-013 supplies a concrete mapping failure which leaves every later Fireball/death/terminal head undrained. |
| BUG-002 | MIXED | Root groups currently execute sequentially, so death does not independently reorder valid prior work. The symptom follows when an earlier head fails or is omitted, ordinary recovery destroys the scene, and a later death/result is the first visible successor. |
| BUG-003 | MIXED | Spell-source grants are frozen and unioned only inside one `_BatchIndex`. If lifecycle phases cross causal-batch boundaries, completion cannot recover an earlier lawful source grant and the spell root can be suppressed. |
| BUG-004 | GUARDED | Corpse memory lawfully survives lost visibility while objective parity describes current visibility. Current parity normalization filters retained subjective entities/loadouts/encounter rows to currently identified actors. |
| BUG-005 | MIXED | The Studio asset catalog retains 256-by-256, 36-column projectile atlases (9216 pixels wide). Fire Bolt currently selects a smaller asset and renderer texture limits are checked before upload, but oversized entries remain selectable. |
| BUG-006 | LIVE | Presentation failure requests stream restart. Ordinary replica reset uses `preserveScene=false`; scene preservation is reserved for an already committed encounter result, so a presentation failure can erase the last committed ordinary scene. |
| BUG-007 | LIVE | `turn_end` deliberately maps to no visual intent. Other missing feedback can be a downstream consequence of one fail-closed recipe, asset, or exact-disposition failure blocking the whole head. |
| BUG-008 | LIVE | Haste Potion is authored with the generic actor clip `Taunt`, without a semantic drinking body action or held bottle/prop contract. |
| BUG-009 | LIVE | Server movement coalesces only contiguous steps in one causal batch. The client starts and stops Walking per resulting cue; no presentation-owned locomotion session spans adjacent journal heads. |
| BUG-010 | LIVE | A visible entity position patch can be lawful when only the destination is visible, while `_step_geometry_allowed` suppresses the movement cue unless one observer saw both endpoints. There is no required explicit state-only movement disposition. |
| BUG-011 | LIVE | Movement cues prove their anchors and local endpoint outcome but are not contractually related to the frame-final entity position after forced movement, relocation, death, or later state-only supersession. |
| BUG-012 | MIXED | Mechanics permit one or two Acid Splash targets, but the live action DTO exposes `num_projectiles=2` without a minimum cardinality. Current UI treats it as a maximum and permits explicit one-target completion; the cross-stack cardinality contract remains overloaded. |
| BUG-013 | LIVE | `mapCue` records cue evidence against original `ClipIntent` objects. Authored damage/condition transformations clone those objects without transferring the evidence, so exact disposition validation reports that a lawful cue has no disposition after mechanics already succeeded. |
| BUG-014 | GUARDED | Rendering uses `sprite_name`, not the display name Water. The current arena uses `water_factory`, which supplies `water.png` and the water traversal facts. |
| BUG-015 | LIVE | `hero.sorcerer_l5_standard_torch` omits Invisibility from its authored `spell_names` despite the spell existing in the catalog/progression system. |

### BUG-016 through BUG-026

| ID | State | Static cause in current source |
| --- | --- | --- |
| BUG-016 | LIVE | Python permits a position-only spell application with spatial-effect children. The TypeScript SDK rejects effects when `target_uuid` is null, so two strict contract owners reject each other's lawful domain. |
| BUG-017 | LIVE | Generic parity failure is recorded as a new latest control-plane fault. Earlier causes remain in bounded history but are not one immutable causal graph, allowing a later symptom to become the UI headline. |
| BUG-018 | LIVE | `recordSubjectiveFrameMapped` is a diagnostics function whose returned count directly controls live head admission. Diagnostic computation therefore remains part of gameplay authority even though subscriber exceptions have been partially quarantined. |
| BUG-019 | LIVE | Objective parity polling can remain in flight while a terminal partition is retired. Server `diagnostic_snapshot` requires the live partition and returns `subjective_parity_partition_unavailable` rather than a retained or typed terminal result. |
| BUG-020 | LIVE | Queue cancellation wraps entity lookup and child dispatch but passes raw mutation sinks. `SwitchWeaponClip` commits from `finally` without a cancellation check, so an old generation can mutate replacement visual state. |
| BUG-021 | LIVE | Grid, light, and camera geometry use zero-based dimensions while tiles/entities retain authoritative non-zero coordinates. Positive-offset and negative-origin maps therefore disagree across consumers. |
| BUG-022 | LIVE | Presentation persistence reads/removes browser storage before the main startup `try`. A storage `SecurityError` can reject `init()` before the recoverable startup UI owns the failure. |
| BUG-023 | MIXED | Stale-principal HTTP 404 now clears identity and selection. Invalid stored identity still throws deliberately, and unavailable storage remains an uncaught startup path. |
| BUG-024 | GUARDED | Current Python deferral supplies `code=source_batch_in_flight`, the endpoint serializes it, and the SDK checks and decodes it. The exact missing-code route is currently aligned. |
| BUG-025 | LIVE | UI and server explicitly permit a zero-Human AI/Codex recipe through the player-facing creation flow. Administrative simulation and player-product authority are not separated. |
| BUG-026 | LIVE | Base action convolution invokes Fireball `_apply` once per target, and `_apply` creates and rolls damage inside that target-local call. There is no execution-scoped shared roll identity/value. |

### BUG-027 through BUG-034

| ID | State | Static cause in current source |
| --- | --- | --- |
| BUG-027 | MIXED | Connector data now reaches SDK reduction and the client board, but rendering is one inert generic line and every connector kind uses the planar walking profile. Typed kind is transported but not meaningfully consumed. |
| BUG-028 | LIVE | Action Studio accepts context-authored variants `move` and `jump` only. `action.traverse_connector` has no scenario and Studio movement frames force `connector:null`. |
| BUG-029 | LIVE | The cold Rolling fixture creates the retired Jump intent shape without current anchors/presentation identity. `JumpClip` rejects it before Rolling media is requested, so the claimed readiness branch is never reached. |
| BUG-030 | LIVE | Studio browser scripts locate tabs by labels and assume the correct overlay/workspace is already open. They can fail on navigation before reaching the presentation behavior they claim to check. |
| BUG-031 | LIVE | Promise-valued `waitForFunction(async ...)` predicates remain in maintained scripts with no static policy gate, allowing the installed harness behavior to admit readiness before the resolved condition is true. |
| BUG-032 | LIVE | Many browser scripts default to ambient `127.0.0.1:5173` and do not own or identity-check frontend/backend processes. A pass need not correspond to the invoking source tree. |
| BUG-033 | MIXED | Transaction-owned RAF callbacks for Banner/FloatingText now have a closing lease. `delay` remains a raw pass-through, so general timer/deferred continuations are not uniformly canceled and joined. |
| BUG-034 | GUARDED | Current gameplay creates the Events/Combat Log sidebar, feeds it only from isolated objective diagnostics, exposes cursor/status, and gates it through developer visibility. It does not feed player command/reducer authority. |

## 6. Cross-bug causal clusters

The first implementation order must follow causes, not the number of visible
symptoms.

### Cluster A — presentation disposition and head liveness

BUG-013 can block the head, which produces or amplifies BUG-001, BUG-002,
BUG-006, BUG-007, BUG-017, and BUG-018. This is the selected first seam.

### Cluster B — cross-language contract disagreement

BUG-010, BUG-011, BUG-012, BUG-016, BUG-027, and BUG-028 show that lawful data
domains and dispositions are not closed across producer, SDK, mapper, and
authoring tools.

### Cluster C — retirement and asynchronous ownership

BUG-019, BUG-020, and BUG-033 cross partition, generation, transaction, and
callback lifetimes without one retirement receipt.

### Cluster D — product/static-state boundaries

BUG-021, BUG-022, BUG-023, and BUG-025 lose coordinate origin, storage
authority, identity recovery, or player-product authority before the normal
consumer can own the result.

### Cluster E — unreliable evidence surface

BUG-029 through BUG-032 demonstrate why additional browser scripts are not the
first corrective action. The first proof must be value-in/value-out, cold,
service-, browser-, network-, and ambient-process-neutral, and below the UI.

## 7. Work Packet 001 — canonical presentation-plan receipt

### 7.1 Objective

Close one exact transition while supplying the real static presentation
authority required by its consumer:

```text
Python production authorities
    -> ContentCatalogResponse + SpellCatalogResponse
    -> initial SubjectiveSyncDelivery == predecessor bootstrap boundary
    -> production-bound Acid Splash lifecycle/events -> CausalEventBatch
    -> contiguous successor SubjectiveFrameDelivery
    -> four separately framed Python model JSON payloads

TypeScript production owners
    -> JSON.parse once per payload -> generated SDK decodeModel
    -> real content-catalog index + pure compiled presentation bundle
    -> real SDK journal bootstrap / existing SSE envelope ingest / head preview
    -> real transition presentation world and presentation map context
    -> planLivePresentationFrame
    -> immutable NormalSubjectiveFramePresentationPlan
    -> exactly one CuePresentationDisposition per cue
```

The content and spell catalogs are authority inputs, not test-authored fixtures.
They allow the real client compiler and mapper to consume the real server
sequence without HTTP or a fabricated presentation profile.

The production result is that
`NormalSubjectiveFramePresentationPlan.dispositions` becomes the sole
authoritative frame-to-plan accounting receipt. Diagnostics consume that
receipt observationally and cannot independently accept or reject the head.

This packet fixes the direct BUG-013 evidence-loss path and the BUG-018
diagnostic admission inversion at this seam. It does not claim to close the
queue, renderer, commit lifecycle, scene recovery, or entire BUG-001 cluster.

### 7.2 Why this is first

- It is a demonstrated current defect, not speculative architecture work.
- Existing stable types already describe the required closed disposition;
  the work consolidates authority instead of introducing another framework.
- It creates a repeatable service-, browser-, network-, and ambient-process-
  neutral producer-to-consumer proof without HTTP, Vite, DOM, Pixi, or manual
  gameplay. One owned short-lived Python child is permitted solely on the
  first-red capture run to cross the Python-to-TypeScript language boundary.
- It proves that real typed values can cross each owner in sequence while one
  raw bounded transcript makes the failure replayable across the production
  edit.
- Later packets can extend the same receipt pattern upstream or downstream
  only after this narrow version is reviewed for usefulness and cost.

### 7.3 Required production behavior

1. Every cue in one normal subjective frame receives exactly one frozen
   `CuePresentationDisposition`: `direct_intent`, `folded_into_parent`, or
   `state_only`.
2. Cue accounting survives every authored damage-intent rewrite actually
   reached by the frozen Acid Splash regression sequence, including any nested
   `parallel` shape actually present in that sequence. When an in-scope rewrite
   replaces an intent object, mapper-local cue association is transferred from
   the original to the replacement. Condition and all other rewrite families
   are deferred.
3. Object-keyed association may exist while the mapper synchronously constructs
   the plan and may remain in the existing transaction-bounded weak evidence
   used by lifecycle diagnostics. It cannot be a downstream admission owner.
   The frozen plan dispositions are the sole downstream disposition authority.
4. `recordSubjectiveFrameMapped` in `animationCoverage.ts` consumes the already
   accepted plan/dispositions observationally, does not recompute disposition,
   and returns `void`. `eventIngestion.ts` neither consumes a diagnostic value
   nor lets a diagnostic exception change the already constructed plan or its
   frame-to-plan admission decision. Queue and commit-lifecycle behavior remain
   deferred.
5. Transaction-local `intentEvidenceIds` are traversal evidence only. They are
   not serialized, persisted, snapshotted, or compared by exact value/order
   across runs.
6. Missing, duplicate, conflicting, or orphaned cue accounting fails while
   constructing the plan, before staging/enqueue/commit, with the exact
   presentation ID and boundary named.
7. State-only frames continue to commit without fabricating a visual
   transaction.
8. The public `VisualTransaction` contract does not acquire replication-only
   fields.

### 7.4 Production files permitted for Implementation Thread

The approved production diff may touch only these three NeuroClient files:

- `app/src/render/subjectivePresentationMapper.ts`;
- `app/src/engine/eventIngestion.ts`;
- `app/src/render/animationCoverage.ts`.

`app/src/render/presentationDiagnostics.ts` is deliberately not in the
production edit set because it does not own this notification. The existing
public `subscribeAnimationCoverage` seam in `animationCoverage.ts` is the
observer boundary exercised by the Tester case below; no new subscriber seam
is authorized.

No `dnd_engine` Python production file, generated SDK contract, queue, clip,
renderer, scene, state-sync, presentation-bundle/bootstrap, Studio, asset,
startup, product UI, package dependency, or build configuration change is in
scope.

If implementation discovers that a file outside the three-file list is
required, work stops and the Planner returns the scope question to the human.
It must not be added as a convenient refactor.

### 7.5 Tester-owned proof surface

The Tester Thread must read `HOW_TO_TEST.MD` before proposing or changing the
surface. It owns all test code, test execution, raw capture retention, and raw
capture cleanup.

The proof is one service-, browser-, network-, and ambient-process-neutral
transition check, not another browser smoke. The first-red capture mode owns
exactly one short-lived Python child and must join it and its streams
deterministically. Replay mode spawns no Python process.

The only test files permitted by this packet are:

- new `dnd_engine/tests/transition_sequences/emit_acid_splash_presentation_sequence.py`;
- new `NeuroClient/app/scripts/presentation-transition-sequence-check.ts`;
- existing `NeuroClient/app/package.json`, limited to one command registration:
  `presentation-transition-sequence:check`.

The package command must run the existing `sdk:build` command before invoking
the already-declared Bun runtime. This focused SDK build is authorized so the
check consumes the current local package export rather than an ambient stale
`dist`; no dependency, generator, SDK source, or other package script change is
permitted.

The two exact Gate B invocations, from the NeuroClient repository, are:

```text
npm --prefix app run presentation-transition-sequence:check -- --capture <absolute-os-temp-capture-path>
npm --prefix app run presentation-transition-sequence:check -- --replay <the-same-absolute-os-temp-capture-path>
```

The capture path must be a new absolute file outside both worktrees. Capture
mode must fail rather than overwrite an existing file. The single file is a
bounded Gate B evidence artifact, not a checked-in fixture, fixture directory,
snapshot system, or reusable store. It is retained unchanged through combined
review and human decision, then the Tester deletes it when the Planner releases
it and reports cleanup.

The TypeScript adapter resolves the checked-out `dnd_engine` root by taking the
real path of the installed local `@neurodragon/dnd-engine-sdk` package and
walking from `sdk/typescript` to its repository root. It fails if that package
does not resolve to a local checkout. It must not scan directories, guess a
path, use an ambient environment variable, or attach to another process.

Capture mode launches exactly `<dnd_engine>/.venv/bin/python`. It fails clearly
if that interpreter is missing or is not Python 3.12 or newer. It must not use
`python` from `PATH`, invoke `uv`, synchronize dependencies, access the network,
or spawn a service. The child is terminated on adapter failure and awaited on
every exit path; stdout and stderr are both drained.

#### Python producer boundary

The Python adapter must use production owners rather than define a parallel
model or hand-author a frame:

1. bootstrap the built-in production content system with
   `bootstrap_content_system(pack_roots=())`, install that same loaded set
   through `SERVER_CONTENT_SYSTEM_RUNTIME`, then build the exact
   `ContentCatalogResponse` with `build_public_content_catalog`;
2. build the exact `SpellCatalogResponse` with `build_spell_catalog`;
3. create a lawful encounter, bind a
   `CanonicalSubjectiveReplicationContext`, establish its subscription, and
   dequeue exactly one initial `SubjectiveSyncDelivery` before any Acid event;
   immediately capture `context.bootstrap()` and assert the sync protocol,
   perspective, and watermarks exactly equal that bootstrap boundary;
4. resolve the built-in `AcidSplash` declaration through the installed
   `LoadedContentSystem.registry`, construct the action, and bind it only
   through `SERVER_CONTENT_SYSTEM_RUNTIME.bind_granted_behavior` using that
   exact declaration ref as provider and the caster as runtime owner. Direct
   assignment of `behavior_binding` or construction of a `BehaviorBinding` is
   forbidden;
5. execute that bound Acid Splash through the real mechanics/action/event queue
   inside the existing public `dnd.core.dice.fixed_dice_faces` context manager,
   with explicit faces which lawfully fail the target save and produce nonzero
   damage. This named production dice authority is the only permitted roll
   control; monkey-patching RNG or mechanics is forbidden;
6. require the very next subscription delivery to be the Acid
   `SubjectiveFrameDelivery`; do not scan past another sync, control, combat-log,
   or unrelated frame delivery. Assert the root `SpellEvent.behavior_binding`
   and emitted spell cue behavior attribution resolve to the same built-in Acid
   Splash definition ref, and assert that exact ref occurs in both emitted
   content and spell catalogs;
7. assert that bootstrap and delivery share source-stream, generation,
   perspective-epoch, partition, and observer identity; assert
   `delivery.frame.watermarks.observation_cursor ==`
   `bootstrap.watermarks.observation_cursor + 1` and
   `delivery.frame.presentation_from_cursor ==`
   `bootstrap.watermarks.presentation_cursor`;
8. call `model_dump_json()` on the four production models and write exactly
   four single-line JSON documents to stdout in this fixed order:
   `ContentCatalogResponse`, `SpellCatalogResponse`,
   `SubjectiveReplicationBootstrap`, `SubjectiveFrameDelivery`;
9. write no label, log, diagnostic, or wrapper object to stdout. Producer
   diagnostics use stderr only.

The initial sync is a barrier assertion, not a fifth captured payload. The
fixed dice faces are producer control inputs; the resulting authoritative save
and damage values live only in the captured production delivery and are replayed
unchanged downstream.

This fixed four-line protocol is the complete adapter framing. No envelope DTO,
delimiter schema, mirrored contract, or generic process protocol is allowed.

#### TypeScript consumer boundary

Capture mode writes the four raw stdout lines unchanged to the new evidence
file before consumer assertions. Capture and replay both:

1. require exactly four nonempty lines and reject all other stdout shapes;
2. apply `JSON.parse` exactly once to each line and pass the resulting
   unmodified value to generated SDK `decodeModel` for
   `ContentCatalogResponse`, `SpellCatalogResponse`,
   `SubjectiveReplicationBootstrap`, and `SubjectiveFrameDelivery`;
3. build the exact catalog with `createContentPresentationCatalogIndex`;
4. read the checked-in production documents
   `app/public/studio/spell-projectile-assets.json` and
   `app/public/studio/spell-studio-drafts.json`, map the decoded spell catalog
   through production `backendSpellToCatalogEntry`, and call production
   `buildLoadedSpellAuthoringData`;
5. form the existing `PresentationSourceSet` only from that loaded spell data
   and the production getters `getContentActionPresentationRecipeFile`,
   `getActionPresentationDispositionFile`,
   `getActionContextPresentationFile`, `getConditionPresentationFile`, and
   `getActionMediaAssetFile`; compile it through the pure production
   `compilePresentationBundle` with generation `1`;
6. install the decoded bootstrap in the real SDK journal, wrap the decoded
   delivery in the SDK's existing `SubjectiveSseEnvelope` with `event: "frame"`,
   `data: decodedDelivery`, and the canonical cursor ID derived from that
   delivery's watermarks:
   `s=<source_event_cursor>;o=<observation_cursor>;p=<presentation_cursor>;l=<combat_log_cursor>`.
   Pass that typed envelope to public `journal.ingest` and preview the resulting
   real head. The ID must equal the existing SDK SSE invariant; an arbitrary
   nonempty ID is forbidden. The envelope is not a fifth producer payload, new
   DTO, or mirrored contract;
7. project the journal base/candidate through the real projection functions,
   construct the transition world with `createTransitionPresentationWorld`,
   and call `createPresentationMapContext` with the exact compiled bundle and
   catalog overrides;
8. call the real `planLivePresentationFrame`, assert a closed disposition for
   the spell root and every nested damage cue after the authored damage
   rewrite, and assert the transaction contains the intended authored damage
   values;
9. after the green plan is frozen, subscribe a deliberately throwing observer
   through existing public `subscribeAnimationCoverage`, invoke the
   observational mapping recorder with the accepted plan, prove the exception
   is quarantined and the same frozen plan remains unchanged, and unsubscribe
   in `finally`;
10. print a compact structured TypeScript-owned report naming content/spell
    authority, bound Acid action/event/cue identity, initial sync, predecessor
    bootstrap, successor delivery, framing, SDK decode, presentation
    compilation, typed SSE envelope, journal bootstrap/ingest/preview, plan
    construction, disposition closure, coverage-observer isolation, and process
    teardown.

The first-red report must show that every preceding stage succeeded and the
unchanged current source failed specifically in `planLivePresentationFrame`.
Replay mode must read the same capture file, spawn no producer, and report the
same full-file content digest before processing. Values used for SDK decode,
journal ingest, compilation, and planning are never rewritten. Normalization
is permitted only on copies used for human-readable report fields.

No other test file or command change is authorized. There is no approval for a
general case schema, generic runner framework, fixture warehouse, snapshot
system, reusable process harness, private module mutation, or test-only
production hook.

### 7.6 Mandatory cases

The packet has two cases only:

1. **Acid authored rewrite:** the raw captured production authorities contain
   one sync-matched predecessor bootstrap and its immediately contiguous Acid
   Splash successor delivery. The action/event/cue and both catalogs share one
   production-bound built-in Acid Splash ref. The capture run is the natural
   pre-implementation red at plan construction; replaying those exact four
   payloads after implementation is the green, with one disposition per cue
   and no private-state mutation.
2. **Diagnostic isolation:** only after the replay produces a lawful frozen
   plan, the existing public animation-coverage subscription seam is given a
   throwing observer. The observer is quarantined and cannot mutate, replace,
   or reject the plan. Implementation source/type evidence separately proves
   that the recorder returns `void` and `eventIngestion` consumes no diagnostic
   result.

Adding Fireball, position-only spatial effects, movement, connector, terminal,
queue, recovery, renderer, or product cases is a later human-approved packet.

### 7.7 Anti-slop and performance constraints

The production diff is rejected if it introduces any of the following:

- a second cue-disposition union or plan type;
- a new generic transition framework or event bus;
- new production JSON serialization/deserialization;
- new persistent evidence, browser storage, network traffic, worker, timer, or
  background task;
- a second mapper/reducer/planner pass for diagnostics;
- a global registry of cues, intents, or transactions beyond current bounded
  ownership;
- reflection over arbitrary object shapes;
- a compatibility fallback which silently fabricates a disposition;
- test-only flags or control flow in production;
- new package dependency;
- a broad rename, file move, formatter sweep, generated-file rewrite, or
  neighboring bug fix.

The intended hot-path change replaces duplicated/parallel classification with
one already-required plan receipt. It must not add another traversal beyond
the traversal needed to construct and validate that receipt. The implementation
submission must report the before/after number of cue/intent graph traversals
by source inspection and explain any increase; an unexplained increase is a
review blocker. Timing microbenchmarks are not required for this packet unless
reviewers find a plausible regression in the submitted design.

The test diff is rejected if it adds an adapter contract, duplicate catalog,
hand-authored presentation profile, generalized capture format, runner class,
new dependency, direct `BehaviorBinding` construction/assignment, custom SSE
envelope type, RNG monkey-patch, or a second case hidden behind configuration.

### 7.8 Explicit non-goals

- No claim that BUG-001 through BUG-034 are fixed.
- No ClipQueue, renderer, asset, GPU, scene-preservation, terminal, or
  queue/commit-lifecycle change.
- No backend contract, backend production, SDK source, or generated-contract
  change.
- No condition-rewrite claim or condition-producing test sequence.
- No full replication laboratory or canonical feature-case framework.
- No migration or deletion of existing tests.
- No browser/product acceptance claim.
- No new diagnostic UI, persistence, or subscriber hook.
- No cleanup of unrelated weak maps, maps, logs, comments, or types.
- No changes to the broad historical testing-surface plan.

### 7.9 Implementation submission required from Implementation Thread

After Gate A global acceptance, the production owner must return to the
Planner:

1. exact changed-file list, limited to the three files in Section 7.4;
2. concise causal explanation tied to BUG-013 and BUG-018;
3. explanation of the single authoritative disposition owner before and after;
4. proof that every in-scope damage-intent rewrite reached by the frozen Acid
   Splash sequence transfers or reconstructs mapper-local cue association,
   including any real nested `parallel` shape, while condition and other
   rewrite families remain deferred;
5. source/type proof that `recordSubjectiveFrameMapped` returns `void`, consumes
   the accepted plan/dispositions without reclassification, and that
   `eventIngestion` consumes no diagnostic result and quarantines diagnostic
   failure after plan construction;
6. source-level traversal and allocation comparison;
7. explicit statement of any scope pressure or deferred adjacent issue;
8. no test edits and no test execution presented as its own acceptance.

### 7.10 Testing submission required from Tester Thread

After Gate A global acceptance, the test owner must return to the Planner:

1. confirmation that `HOW_TO_TEST.MD` was read;
2. exact changed-file list and the two exact capture/replay invocations;
3. confirmation that the focused SDK package build preceded both runs and that
   no pre-existing `dist` was trusted;
4. first-red structured stage evidence showing the intended current plan
   failure after production content binding, initial-sync/bootstrap equality,
   contiguous delivery, framing, decode, compilation, typed SSE-envelope, and
   journal stages, including equality between the envelope ID and the decoded
   delivery's canonical `s/o/p/l` cursor ID;
5. the absolute non-worktree capture path, its four-line shape, and its content
   digest, without checking the payload into either repository;
6. post-implementation focused result using `--replay`, the matching content
   digest, and proof that replay spawned no Python producer;
7. proof of one disposition per Acid spell/damage cue and the intended authored
   damage values;
8. proof that the public animation-coverage subscriber was quarantined, the
   frozen plan was unchanged, and the subscription was removed;
9. duration and confirmation of zero HTTP/UI/service/Vite/browser/ambient-port,
   real-timer, `uv`, dependency-sync, or network use;
10. capture-run child exit/join/stdout/stderr teardown evidence and a zero-leak
    result;
11. no production edits and no unapproved test files;
12. after Planner release, deletion of the single raw capture artifact and
    confirmation that it was never placed in a worktree.

### 7.11 Gate B review

Gate B begins with the Tester-owned transition surface and `--capture` natural
first-red while production source is unchanged. Reviewers confirm that the red
reaches the intended plan boundary and is not a content authority, framing,
decode, compilation, bootstrap, journal, or setup failure. The raw four-line
capture is retained outside the worktrees.

Only then may the Implementation Thread edit the three permitted production
files. The Tester subsequently uses `--replay` against the same retained bytes;
it must not regenerate the sequence for the green. This sequencing prevents
the implementation from erasing the real red and prevents a fabricated
regression fixture from replacing it.

Production and testing submissions are reviewed independently and together by
External Reviewers 1–4. Every reviewer examines both surfaces; specialization
does not waive whole-submission review. Findings route through the Planner to
the sole owner of the affected surface. Review repeats until all four reviewers
approve. The Coordinator verifies governance and review completion but is not
a technical approval vote. Global acceptance additionally requires human
acceptance. The Planner then releases the temporary transcript for Tester-owned
deletion.

## 8. Future sequence, not authorized by this packet

If Work Packet 001 proves useful without runtime or development cost, future
human-approved packets can extend the same value-receipt pattern one seam at a
time:

1. server projection to generated SDK acceptance, beginning with BUG-016;
2. visible position patch to movement/state-only settlement, BUG-010/011;
3. planned transaction to queue terminal and scene commit, BUG-001/006/020/033;
4. terminal partition to retained diagnostic result, BUG-019;
5. product authority and startup boundaries, BUG-021/022/023/025;
6. authored connector and Studio consumption, BUG-027/028;
7. only then, a small owned product representative where pixels or interaction
   are the actual requirement.

This ordering is advisory context only. Each later packet requires new human
guidance and a fresh Gate A.

## 9. Review record

### Revision 2 consolidation

No initial finding was waived. Revision 2:

1. defines a real predecessor bootstrap and contiguous successor delivery;
2. distinguishes raw model JSON, one `JSON.parse`, and generated SDK decode;
3. authorizes one raw non-worktree capture with explicit capture/replay modes;
4. fixes stdout framing to four production-model lines without an envelope;
5. requires a fresh focused SDK build and an exact repository-local Python
   interpreter without `uv`, network, or dependency synchronization;
6. supplies the mapper through real content/spell catalog payloads, checked-in
   production authoring documents, and pure production compiler/index owners;
7. bounds object-keyed association to construction/weak diagnostic evidence,
   limits rewrites to Acid damage paths, and leaves condition rewrites deferred;
8. assigns source/type proof to Implementation and narrows the runtime claim to
   frame-to-plan admission rather than queue/commit lifecycle;
9. reduces the permitted production edit set from four files to three.

### Revision 3 consolidation

Revision 3 preserves every Revision 2 boundary and additionally:

1. corrects the observer seam to existing public
   `subscribeAnimationCoverage`, the listener actually notified by the mapping
   recorder;
2. passes the decoded delivery to `journal.ingest` through the SDK's existing
   typed `SubjectiveSseEnvelope`, including its required nonempty transport ID,
   without adding a producer payload or contract;
3. names public production `fixed_dice_faces` as the only deterministic roll
   authority and forbids RNG/mechanics monkey-patching;
4. binds Acid Splash through `SERVER_CONTENT_SYSTEM_RUNTIME` using the exact
   installed built-in declaration and requires action, event, cue, content
   catalog, and spell catalog identity agreement;
5. consumes exactly one initial `SubjectiveSyncDelivery`, proves it equals the
   predecessor bootstrap boundary, and requires Acid to be the immediate next
   delivery rather than scanning past unexpected state.

### Revision 4 consolidation

Revision 4 makes one transport-boundary correction only: the existing
`SubjectiveSseEnvelope.id` must be the canonical `s/o/p/l` cursor ID derived
from the decoded delivery watermarks. An arbitrary nonempty test-local ID is no
longer permitted. The producer protocol remains exactly four model payloads;
no fifth payload, envelope type, decoder, or journal adapter is introduced.

### Mandatory sub-agent self-review

- Reviewer identity: `/root/wp001_self_review`
- Draft initial verdict: CHANGES_REQUIRED
- Draft Revision 1 verdict: CHANGES_REQUIRED
- Remaining Revision 1 findings: construction-time object association was
  contradicted by the written boundary; no real presentation-catalog/context
  authority was named; exact replay was infeasible; implementation proof
  silently re-expanded to every rewrite family; Tester was assigned a
  source/type assertion; process-neutral wording still conflicted with the
  owned child.
- Revision 2 verdict: CHANGES_REQUIRED
- Revision 2 findings: wrong observer seam; decoded delivery was not wrapped in
  the journal's existing SSE envelope; deterministic rolls named no public
  authority.
- Revision 3 verdict: CHANGES_REQUIRED
- Revision 3 finding: the SSE envelope used an arbitrary ID rather than the
  SDK's canonical delivery-watermark cursor ID.
- Revision 4 state: finding addressed; follow-up verdict pending.

### External Reviewer 1

- Revision 1 verdict: CHANGES_REQUIRED
- Basis: mandatory independent self-review plus Planner verification of the
  same contradictions and feasibility gaps.
- Revision 2 verdict: CHANGES_REQUIRED
- Revision 3 verdict: CHANGES_REQUIRED
- Revision 4 verdict: PENDING

### External Reviewer 2 — Backend

- Revision 1 verdict: CHANGES_REQUIRED
- Findings: bootstrap/delivery lacked a contiguous predecessor/successor
  contract; SDK decoding was inaccurately described as accepting bytes;
  literal replay had no artifact; the command could trust stale SDK `dist`;
  the Python launcher/dependency ownership was ambient.
- Revision 2 verdict: CHANGES_REQUIRED
- Revision 2 findings: Acid behavior identity was not bound through the
  installed production content owner; initial sync was not consumed and proven
  equal to the predecessor bootstrap.
- Revision 3 verdict: APPROVE
- Revision 4 verdict: PENDING

### External Reviewer 3 — Frontend

- Revision 1 verdict: CHANGES_REQUIRED
- Findings: diagnostic file optionality conflicted with the stated behavior;
  bootstrap/delivery cursor preconditions were unspecified; exact replay had
  no retention mechanism; implementation proof expanded beyond Acid damage;
  diagnostics claimed enqueue/commit behavior outside the proof boundary.
- Revision 2 verdict: APPROVE
- Revision 3 verdict: APPROVE
- Revision 4 verdict: PENDING

### External Reviewer 4 — Scope, Duplication & Serialization

- Revision 1 verdict: CHANGES_REQUIRED
- Findings: exact replay required an unapproved persistence mechanism;
  implementation proof expanded to all rewrites; child stdout had no framing
  rule; the throwing-observer case named no existing public seam.
- Revision 2 verdict: APPROVE
- Revision 3 verdict: APPROVE
- Revision 4 verdict: PENDING

### Coordinator governance verification

- State: Revision 1 through Revision 3 dispatches were simultaneous and blind;
  all four frozen-revision verdicts were recorded before each consolidation.
  Revision 4 re-review dispatch is pending.

### Human acceptance

- State: PENDING
