# Gameplay Regression Work Packet 003

## BUG-016 Stage 2: direct position-owned client presentation

Date: 2026-08-10  
Status: Gate A Revision 4 draft; no production edit, test edit, build, browser,
service start, or execution is authorized until independent R1-R4 approval and
Coordinator governance verification.

Revision 1 was rejected 0/4 on its exact 495-line identity. Revision 2 changes
only the proof protocol inside the same five-production/two-smoke boundary:

- resolve the observed Fog spatial ref through the public spell's unique
  production dependency rather than treating it as a public catalog row;
- validate the complete wire fixture and obtain its receipt through the
  production live planner;
- make position facing, release dispatch, child traversal, and dispatcher
  admission independently observable after the natural facing red; and
- add one focused local TypeScript compiler gate before each governed smoke
  phase.

No Revision 1 approval carries to this identity.

Revision 2 was rejected 0/4 on its exact 573-line identity. Revision 3 changes
only three proof expectations: the public spell dependency is the sole owner of
the spatial target ref; the preserved direct/public runtime paths perform two
and three caster lookups respectively; and the focused compiler command gates
`app/src`, while the JavaScript smokes retain their separate review/execution
proof. No Revision 2 verdict carries to this identity.

Revision 3 was rejected 3/4 on its exact 593-line identity. Revision 4 changes
only one generated receipt name and two matching authority descriptions:
`SubjectiveReplicationFrame` is the planner input, public/authoring owners agree
on the Fog root ref, and the public dependency alone owns the spatial ref. No
Revision 3 verdict carries to this identity.

## 1. Authority and packet boundary

This packet is the next bounded seam in the already authorized BUG-001 through
BUG-034 gameplay-regression program. It follows the automatically closed
WP-002 / BUG-016 Stage 1 packet.

WP-002 established only that the TypeScript SDK accepts the same position-owned
spatial-effect graph as the Python player contract when the application
coordinate belongs to disclosed current or previous geometry. It did not claim
NeuroClient mapping, planning, queue admission, clip execution, reducer state,
scene state, or pixels.

The governing regression ledger requires a lawful position-only spatial-effect
spell to traverse the client without inventing either an entity target or AoE.
The preserved stabilization manifest records the already-established design:
NeuroClient uses a distinct position delivery. This packet restores only the
smallest coherent direct-delivery slice of that design.

This is not a new public protocol, backend contract, SDK contract, persistence
shape, or general spell-routing redesign. `CastIntent` is an internal
NeuroClient render receipt. Adding its position variant is necessary to retain
the already-decoded authoritative application coordinate without lying about
entity or area ownership.

Frozen authorities:

- regression ledger: SHA-256
  `9ac0633322a2203222076a54bd2a8edb23c10e17b49b84562a77d971b922a805`;
- stabilization manifest: SHA-256
  `0048c7192773c2a0086a540fabda89023830408ad7ecaf9894c6e34e7529fe5b`;
- accepted WP-002 plan: 380 lines, SHA-256
  `1d719bfcbbd00a63c7287ae64b8aac47f4d2fa81b81ddfd40275457d8c586bb0`;
- accepted WP-002 SDK validator: 1303 lines, SHA-256
  `1c711f181decac37a033d498929acacda8524735321767ab712c8f84661b958f`;
- accepted WP-002 SDK test: 2666 lines, SHA-256
  `e6fe855ecca8946490435082d5923cb71fcbbb36e1630eccb74291fbacb8758f`.

WP-002 authorities remain byte-identical throughout this packet.

## 2. Frozen NeuroClient baseline

The packet is based on the current accepted NeuroClient working surface,
including the completed WP-001 mapper correction. Existing dirty files belong
to prior accepted work and must not be reverted or normalized.

Production baselines:

1. `app/src/render/types.ts`
   - 915 lines
   - SHA-256
     `5dc9070fac04be8f31df0c08083417d63dd343568475377240f368ca24998149`
2. `app/src/render/subjectivePresentationMapper.ts`
   - 3220 lines
   - SHA-256
     `024889137a0884c5e8d0e86b25ed900dce9015fad44222dfd2c3e89a93cecbbd`
3. `app/src/render/castIntentChildren.ts`
   - 15 lines
   - SHA-256
     `4db4ef71577f88efc88f586ac77d3f1e814ed59681b02f9905b927083d730b03`
4. `app/src/render/dispatcher.ts`
   - 198 lines
   - SHA-256
     `3ef0be0cf3ec181a47b91f1636b1b8959b792cc32a0abfe57bd84ec94838ba04`
5. `app/src/render/clips/CastClip.ts`
   - 545 lines
   - SHA-256
     `171955c3409449c4d8519608679ca67e43748514a53a0d2d653eb9011be2f3eb`

Tester baselines:

1. `app/scripts/subjective-presentation-semantic-smoke.mjs`
   - 1539 lines
   - SHA-256
     `daf40f2e0f02df395de958446c9c2958fa0f75b0c732e3daafe63a3e53680916`
2. `app/scripts/target-facing-smoke.mjs`
   - 407 lines
   - SHA-256
     `84264ccf9532551357801409e606fd36cfa2fa3a2420762a19be125cb8997ccd`

Command authority:

- `app/package.json`
  - 165 lines
  - SHA-256
    `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3`
  - remains byte-identical.

## 3. Static causal study

### 3.1 The decoded application is lawful

The Python and corrected SDK graph owners now agree:

- one spell application may have `target_uuid: null` and a non-null position;
- a spatial-effect child owned by that application must have no entity target;
- the application position must occur in the child's affected or previous
  disclosed geometry;
- non-spatial spell children still require an explicit entity application.

For a non-area, non-projectile ranged zone spell, the Python mapper emits
`delivery: "direct"`. It does not rewrite the spell to AoE merely because its
application owns a grid coordinate.

### 3.2 The current NeuroClient mapper rejects that lawful direct graph

`mapSpell` in `subjectivePresentationMapper.ts` preserves both application
fields in its local normalized row. The `touch` / `direct` branch then reads
only `applications[0].targetUuid` and throws when it is null. The exact decoded
position is present but discarded as a routing authority.

The mapper already treats `spatial_effect` as reducer-owned state and produces
no child clip for it. That is correct and remains unchanged. The missing visual
receipt is the spell root: the caster must still perform a position-directed
cast while the spatial child receives one exact state-only disposition.

### 3.3 Existing CastIntent variants cannot express the truth

The internal union currently has only:

- AoE, which owns typed area geometry, radius, shape, center, and affected
  entity entries;
- projectile and missile-volley entity routes;
- touch/self entity routes.

Mapping the direct position application to AoE would invent area semantics.
Mapping it to touch/self would invent an entity target. Dropping the cast root
would lose the spell presentation and its exact cue disposition. A distinct
position receipt is therefore the smallest non-fabricating representation.

### 3.4 The new union member has four necessary consumers

Adding only a mapper branch would leave stale ownership:

1. `directIntentChildren` would not traverse its disclosed children when
   constructing exact mapper evidence;
2. `castIntentChildren` would not expose them to diagnostics and Studio
   inspection;
3. `dispatcher.requiredEntityUuids` would not return a valid actor-only entity
   set for queue admission;
4. `CastClip` would neither face the authoritative coordinate nor dispatch its
   release children.

Those consumers make the five-file production packet one coherent internal
receipt migration rather than adjacent feature work.

## 4. Objective and proof boundary

The packet succeeds only if all of the following are proven:

1. a lawful `direct` spell cue with exactly one position-owned spatial-effect
   application maps to one frozen visual transaction;
2. its root maps to exactly one `CastIntent` with
   `delivery: "position"`, the exact cloned grid position, and no fabricated
   entity UUID, radius, shape, or AoE target list;
3. the spatial child remains reducer-owned and receives exactly the existing
   `spatial_effect_reducer_state` evidence rather than a fabricated clip;
4. exact mapper evidence associates the spell root with the cast and records
   the spatial child as state-only;
5. queue entity admission requires the caster only for this route;
6. both production child-traversal owners return the exact `onHit` list without
   duplicating or reconstructing it;
7. CastClip faces the position from the caster's current grid coordinate,
   performs the ordinary authored cast body/release/recovery sequence, and
   dispatches `onHit` at the existing release anchor;
8. CastClip performs no target-entity lookup for the position route;
9. current entity-owned direct/touch/self, projectile, missile-volley, and AoE
   behavior remains unchanged;
10. the output remains frozen and no consumer may mutate the application
    position or accepted plan.

The packet closes only BUG-016 Stage 2 direct client presentation. It does not
close the full BUG-016 product chain.

## 5. Exact production assignment — Implementation

Implementation may edit exactly the following five files and may execute
nothing.

### 5.1 `app/src/render/types.ts`

Add exactly one `CastIntent` union member:

- `delivery: "position"`;
- `position: Pos`;
- `onHit: ClipIntent[]`.

It carries no `targetUuid`, `radius`, `aoeShapeType`, `actorPosition`,
`targets`, or `missiles` field. Do not alter `CastIntentBase`, the phase graph,
or any public wire/SDK model.

### 5.2 `app/src/render/subjectivePresentationMapper.ts`

In `directIntentChildren`, treat `position` with projectile/touch/self and
return `intent.onHit`.

In `mapSpell`:

1. keep `touch` entity-only and preserve its present failure when no entity
   target exists;
2. separate the `direct` branch;
3. require its first normalized application to exist;
4. if that application has an entity UUID, preserve the current immediate
   `touch` CastIntent mapping byte-for-behavior;
5. otherwise require its non-null position and create the distinct `position`
   CastIntent using a cloned position and the existing flattened application
   effects;
6. compile and validate the same no-projectile/no-area presentation phase graph
   and recovery already used by direct/touch;
7. do not infer AoE, radius, shape, entity, projectile, or area data.

Do not change `mapCueUnchecked` for `spatial_effect`, state-only reasons,
disposition planning, authored spell resolution, evidence ownership, or any
other spell delivery.

### 5.3 `app/src/render/castIntentChildren.ts`

Return `intent.onHit` for the position route exactly as for the immediate
entity routes. Add no recursive traversal or new collection.

### 5.4 `app/src/render/dispatcher.ts`

For a position cast, `requiredEntityUuids` returns only `intent.actorUuid`.
No coordinate-to-entity lookup, board lookup, or target synthesis is allowed.
All other dispatch and lifecycle behavior remains unchanged.

### 5.5 `app/src/render/clips/CastClip.ts`

1. update the route comment to name position delivery;
2. keep concrete entity facing authoritative for entity routes;
3. when no facing override/entity target exists, face `intent.position` for
   both AoE and position routes;
4. make `castFacingTargetUuid` return no UUID for position;
5. execute position delivery by calling the existing
   `dispatchDisclosedEffects(intent, intent.onHit, ctx, "release")` path;
6. preserve cast body, release frame, authored VFX, recovery, cancellation,
   equipment restoration, and phase-graph validation unchanged.

Do not add a new clip, FX owner, board query, target search, fallback, timer,
or area/projectile branch.

## 6. Exact test assignment — Tester

Tester may edit exactly the following two existing registered smoke files and
may execute nothing until a separately reviewed one-shot release.

### 6.1 `app/scripts/subjective-presentation-semantic-smoke.mjs`

Extend the existing production-bundle semantic case with one exact Fog Cloud
fixture:

1. locate the exact public `spell.fog_cloud` catalog entry, require it to be
   unique and of spell kind, obtain the real spell ContentRef through the
   existing `spellDefinitionRef("fog_cloud")` authoring owner, and require
   exact `sameContentRef` (or canonical `contentRefKey`) equality between those
   two owners of the Fog root ref;
2. from that exact public spell entry, require exactly one
   `creates_spatial_effect` production dependency and take its target
   ContentRef; require that ref to have kind `spatial_effect` and ID
   `spatial_effect.spell.fog_cloud`. Fail on a missing, duplicate, wrong-kind,
   or wrong-ID dependency. The public Fog entry's dependency is the sole owner
   of this observed spatial ref: the spell-authoring model has no spatial
   dependency field. The observed spatial declaration is not required to be,
   and must not be synthesized as, a top-level public catalog row;
3. construct one complete reciprocal two-cue `SubjectiveReplicationFrame`
   using the existing frame/cue fixture vocabulary and every field required by
   the generated SDK/wire contract, including all ordinary cue identity/cursor
   fields, application `outcome`, and spatial `effect_uuid`:
   - root spell: actor `hero`, Fog Cloud behavior attribution, school
     `conjuration`, level 1, `delivery: "direct"`, no projectile, no area;
   - exactly one application with index 0, a unique application ID,
     `target_uuid: null`, a non-null coordinate, and exactly the spatial child
     ID;
   - child spatial effect: matching parent, `operation: "created"`, layer
     `cloud`, non-null anchor, affected geometry containing the application
     coordinate, empty previous geometry, and the exact spatial ContentRef;
4. feed the complete frame through production `planLivePresentationFrame`, not
   directly through the mapper. This must exercise generated SDK frame
   validation, the production mapper, `directIntentChildren`, exact
   disposition closure, transaction freezing, and the existing exact
   transaction-mapping-evidence accessor. Do not hand-author a transaction,
   intent, disposition, plan, or evidence map;
5. require one frozen `visual_transaction` plan and its exact frozen
   transaction, with dispositions covering both cue IDs exactly once; require
   one cast whose delivery is exactly
   `position`, whose position is exactly the application coordinate, whose
   `onHit` is empty because the only child is reducer-owned, and which has none
   of the AoE/entity ownership fields;
6. require the root disposition/evidence to identify the one cast and the
   child disposition to be state-only with reason exactly
   `spatial_effect_reducer_state`; require the transaction evidence accessor to
   agree with those same cue identities;
7. retain all current semantic assertions unchanged.

This fixture is a bounded client mapping proof using real production catalog,
authoring compilation, mapper, and evidence owners. It is not claimed as a
real engine event capture or mounted gameplay proof.

### 6.2 `app/scripts/target-facing-smoke.mjs`

Add one position-route case beside the existing entity and AoE cases:

1. use the existing real `CastClip.run`, compiled no-projectile/no-area phase
   graph, and deterministic animation clock, but create a case-specific caster
   at grid coordinate `[2, 2]` with explicit initial facing `S`;
2. create one frozen position intent with `delivery: "position"`, position
   `[2, -2]`, no `actorFacingOverride`, and one separately named frozen empty
   `onHit` array. The required relative facing is `NE`; the incorrect
   origin/absolute-coordinate facing is `E`; both differ from initial `S`;
3. for this case only, use a release-capable variant of the fake animated
   entity. Its `beginBodyTravel` must receive the normal presentation options,
   invoke `options.onFrame[castBase.releaseFrame]` exactly once, and then
   resolve ordinary body completion. Do not change the existing missile/AoE
   facing fakes, which intentionally do not own delivery-capable phase graphs;
4. make the dispatch context contain only this caster, record every
   `getEntity`, and throw for any UUID other than the caster. Spy
   `dispatchChildren` and record the child-array identity and call count;
5. run the position intent directly through real `CastClip.run` and assert the
   exact final facing `NE` first. This is deliberately the first new assertion
   so unchanged production fails at the natural facing boundary before any
   green-only branch proof;
6. after the facing assertion, require the authored release callback to have
   fired exactly once and `dispatchChildren` to have been called exactly once
   with the identical frozen `onHit` array. Empty children are intentional;
   call identity plus count proves the release route without inventing a child.
   Require exactly two recorded `getEntity` calls on this direct
   `CastClip.run` path—entry and release—and require both UUIDs to equal the
   caster;
7. require production `castIntentChildren(positionIntent)` to return that exact
   same `onHit` array;
8. reset all counters and use a fresh case-specific caster/context, then invoke
   the same frozen position intent once through production `runIntent`.
   Require its lifecycle to report `started` then `completed`, exactly three
   recorded `getEntity` calls—dispatcher admission, CastClip entry, and
   CastClip release—with every UUID equal to the caster and none undefined or
   non-caster, exactly one release callback, and exactly one dispatch of the
   identical `onHit` array;
9. retain the existing entity-target precedence, missile, AoE fallback,
   movement, and jump assertions unchanged.

The test may extend the returned summary only with exact position-route facts.
It may not add a fixture framework, alternate clip, or product API.

## 7. Natural first-red and execution protocol

### 7.1 Edit-only freeze

Tester first returns only the two-file diff, line counts, and SHA-256 values.
No build, browser, service, formatter, debug command, or test is allowed.

Fresh isolated R1-R4 review must prove:

- the Fog graph is reciprocal and otherwise lawful;
- every required wire field is present and the generated SDK/live planner owns
  validation, transaction freezing, dispositions, and mapping evidence;
- the public and authoring owners agree on the exact Fog root ContentRef, then
  the public Fog entry's unique `creates_spatial_effect` dependency exclusively
  owns the exact observed spatial ref;
- the semantic test fails only at the current direct/no-entity mapper guard;
- the facing test first fails only because current CastClip has no position
  route, with initial, relative, and absolute-coordinate facings all distinct;
- green-only assertions cover one authored release, exact child-array identity,
  `castIntentChildren`, exactly two caster lookups for direct `CastClip.run`,
  exactly three caster lookups for public `runIntent`, no non-caster lookup,
  actor-only admission, and completed lifecycle;
- all inherited assertions remain active;
- no manual plan/intent/evidence authority was introduced.

### 7.2 Isolated browser stack

After 4/4 approval and Coordinator verification, Tester may start one isolated
temporary stack only for the governed proof:

- preflight ports 8000 and 5173; stop if either is occupied;
- backend from NeuroClient root through the existing tracked script invoked as
  `bash ./server.sh`, with `DND_LOCAL_PROFILE_RUNTIME_ROOT` set to one fresh
  `/tmp` directory;
- frontend from `app` through the existing `npm run dev` command;
- bounded readiness probes only;
- no repository runtime/profile mutation;
- stop both owned processes after evidence collection and prove both ports and
  owned child processes are closed.

The script's missing executable bit is advisory backlog evidence and is not
changed in this packet.

### 7.3 One-shot first red

Before starting the isolated stack, Tester invokes exactly once from the
NeuroClient root:

1. `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`

This is the focused local compiler gate for the frozen `app/src` production
surface and the internal `CastIntent` union migration. `app/tsconfig.json`
includes `src`; it does not typecheck the two `.mjs` Tester files. Those files
are covered by fresh static review and their separately governed smoke
executions. This is not the broad app check suite and does not authorize another
package command. Any nonzero result freezes the packet before services start.

After the compiler gate passes, Tester invokes each existing registered smoke
command exactly once against that same isolated stack:

2. `npm --prefix app run subjective-presentation:smoke`
3. `npm --prefix app run target-facing:smoke`

Required unchanged-source red:

- semantic smoke passes SDK/live-planner prerequisite validation, public
  catalog dependency validation, and public/authoring Fog root-ref equality,
  then fails at the exact
  `direct delivery has no entity target` mapper boundary for the Fog root;
- target-facing smoke reaches its new position case and fails its exact facing
  assertion (`S` received versus required `NE`) before the release/helper/
  dispatcher assertions, without a missing-entity, phase-graph, body, or timing
  failure;
- prior assertions in both commands pass before their new terminal assertion.

Any compiler failure, service/bootstrap failure, dependency lookup failure,
authored recipe failure, SDK/planner prerequisite failure, different mapper
error, entity lookup, phase failure, unexpected success, or unrelated smoke
failure freezes the result. No rerun, workaround, fixture edit, debug command,
or alternate service is authorized.

### 7.4 Implementation and green

Only after fresh R1-R4 review of the natural red plus Coordinator verification
may Implementation receive Section 5. Implementation edits only, runs nothing,
and returns the five-file diff/identity.

The combined seven-file surface then receives fresh isolated R1-R4 static
review. After 4/4 plus Coordinator verification, Tester first repeats the exact
focused local compiler command once. Only after it exits zero may Tester repeat
the same two registered smoke commands exactly once each on one fresh isolated
stack.

Green requires the compiler and both smoke commands to exit zero, all inherited
assertions to remain green, exact SDK/planner-owned position mapping/evidence
to pass, exact position facing to pass first, one exact release dispatch,
exact child-helper identity, the exact two/three caster-only lookup counts,
actor-only public dispatcher admission/lifecycle, and clean owned-process
teardown. Any nonzero or unexpected result freezes as a blocker without rerun.

## 8. Performance, duplication, and serialization constraints

The production correction must remain O(1) beyond existing work:

- one application branch and one two-coordinate clone already required for
  immutable intent ownership;
- one existing `onHit` traversal path;
- one facing delta calculation at clip start;
- no new cue, graph, intent, entity, or geometry scan.

Rejected implementation patterns:

- converting a position application into AoE or an entity target;
- looking up an entity by coordinate;
- rescanning the frame, cue graph, journal, reducer patches, board, or scene;
- adding a second spell mapper, decoder, validator, planner, or classifier;
- hand-authoring or persisting a disposition/evidence receipt;
- adding a cache, index, registry, adapter, DTO, schema, serializer,
  deserializer, protocol version, persistence field, telemetry stream,
  dependency, framework, or public API;
- adding a compatibility fallback for malformed data;
- changing authored spell or spatial-effect catalog data;
- adjacent cleanup or formatting churn.

The position remains an internal immutable two-number value already decoded by
the SDK. It is not serialized again and does not enter storage.

## 9. Explicit non-goals

This packet does not prove or change:

- backend projection or privacy evidence;
- SDK validation (already WP-002);
- SDK journal bootstrap/ingest/preview;
- reducer installation/removal of spatial-effect geometry;
- scene/Pixi spatial-effect creation, update, or removal;
- live Grease or Fog Cloud command execution;
- mounted UI, GPU, screenshot, or pixel output;
- projectile or missile-volley position applications;
- AoE application filtering;
- mixed/multiple direct application policy;
- spell authoring content or media;
- Studio editing/preview semantics;
- any BUG family other than BUG-016 direct Stage 2.

Those require later packets and fresh Gate A review. A need to support a
position-owned projectile/missile in this packet is scope pressure, not license
to broaden.

## 10. Ownership and isolation

- Planner owns this packet, gates, evidence routing, and public ledger.
- Tester continuation `019fec24-ec85-7eb1-9676-5bab2853a627` owns only the two
  Section 6 smoke files, authorized service lifecycle, and one-shot commands.
- Implementation `019feaea-52c1-7053-a709-4d4c739e0530` owns only the five
  Section 5 production files and performs no execution.
- R1, R2 Backend, R3 Frontend, and R4 Scope/Duplication/Serialization review
  identical frozen surfaces independently and return only to Planner.
- Coordinator independently verifies every unanimous transition.
- Live Stack and Full Suite monitors remain advisory/non-gating and are not
  execution owners for this packet.

No owner contacts another owner or reviewer. No reviewer receives a peer
verdict before blind review closes.

## 11. Stop conditions

Stop and return to Planner without further edit or execution if any of the
following occurs:

1. a sixth production file or third test file appears necessary;
2. `app/package.json`, backend, SDK, generated, reducer, scene, public content,
   persistence, or Studio source appears necessary;
3. the public and authoring Fog root refs cannot be obtained or do not compare
   equal, or the exact spatial ref cannot be obtained from the public Fog
   entry's unique `creates_spatial_effect` dependency;
4. the first red occurs outside the two specified boundaries;
5. a position route requires invented AoE/entity semantics;
6. TypeScript exhaustiveness exposes another maintained CastIntent consumer;
7. a port is occupied or the isolated stack cannot start cleanly;
8. a run leaks a process, modifies a worktree/runtime profile, or produces an
   unrelated failure;
9. any dependency, framework, schema, protocol, persistence, public-contract,
   or materially different architecture is proposed.

Items 1, 2, 6, and 9 require a revised packet and may require human scope
review depending on materiality. They are not implementation discretion.

## 12. Gate A reviewer questions

Each reviewer must inspect the complete frozen sources and answer:

1. Is `delivery: "position"` the smallest truthful internal receipt, with AoE
   and entity routes demonstrably false substitutes?
2. Does the five-file production algorithm cover every necessary maintained
   consumer without a hidden sixth file, runtime cycle, or stale exhaustive
   switch?
3. Does the direct mapper branch preserve current entity-direct behavior and
   change only the position-owned case?
4. Does the semantic Fog fixture use real production refs/authoring and prove
   root cast plus child state-only evidence without becoming a second mapper or
   claiming real engine output?
5. Does the facing fixture isolate exact coordinate facing, actor-only entity
   ownership, one exact authored release/child dispatch, production child
   traversal, the exact two direct/three public caster-only lookup counts,
   public dispatcher lifecycle, and absence of target lookup?
6. Are both first-red boundaries natural, independently reachable, and
   discriminating under one fresh isolated stack, and does the focused
   compiler gate close the internal union migration without broadening scope?
7. Are the performance, duplication, serialization, non-goal, service, and
   stop boundaries sufficient?
8. Is any added file, public/internal contract migration, projectile case, or
   material scope decision actually required before edit-only release?

Allowed verdicts:

- `APPROVE_WORK_PACKET_003_GATE_A`
- `CHANGES_REQUIRED`
- `HUMAN_SCOPE_REQUIRED`

Approval authorizes no edit or execution by itself. Progression requires fresh
unanimous R1-R4 approval on one exact packet identity plus Coordinator
governance verification.
