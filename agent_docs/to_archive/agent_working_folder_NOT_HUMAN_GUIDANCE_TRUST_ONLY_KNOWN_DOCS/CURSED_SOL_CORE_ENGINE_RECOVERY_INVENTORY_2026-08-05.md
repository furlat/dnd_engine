# Core-engine recovery inventory from `cursed-sol`

Date: 2026-08-05

Current baseline: `feat-zaxis` / `e745f389f7a34321d16146a6d241c363597ed37a`

Abandoned comparison ref: `cursed-sol` / `d2fb3931527f8c1cad4bdda163876baaaedb0555`

Relationship: `cursed-sol` has exactly one parent, the current baseline commit.

Review mode: Git-object comparison only; the abandoned branch was not checked out, merged, or executed.

## Executive decision

Do **not** cherry-pick or merge `cursed-sol`.

The abandoned commit changes 457 paths, adds about 273,669 lines, and deletes
about 53,871. Its new `dnd/runtime` tree alone adds 36,419 lines; the Runtime V2
developer tooling adds another 66,034, and the TypeScript SDK change is over
63,000 added lines. That is not a recoverable unit.

There is, however, genuinely valuable lower-engine work in the commit. The
right recovery strategy is a small sequence of mechanics-first ports and
rewrites, each landing behind route-free engine tests. The best material is:

1. encounter-local deterministic randomness;
2. an idempotent spatial-effect reveal fix;
3. typed authored condition/Counterspell/combat-log facts;
4. movement lifecycle corrections and richer movement target facts;
5. canonical reciprocal wall/door identity;
6. authored traversal connectors;
7. same-Human multi-actor initiative blocks with reversible End Turn;
8. a small route-free source/assignment/fairness boundary, rewritten without
   the Runtime V2 transaction machinery.

The first four can be recovered in small contained patches. The next four are
valuable designs but must be rewritten or heavily pared down. The rest of the
Runtime V2/server/SDK branch should stay abandoned unless a later product need
justifies a fresh implementation.

## Mapping to the accepted plan

This inventory preserves the useful requirements of the accepted architecture
without treating its failed implementation as authoritative code.

| Accepted-plan requirement | Recovery treatment |
|---|---|
| Production plan §13.1–13.3: grouped control assignment, plural offers, controlled-actor inspection | Recover shared initiative and an explicit control identity; implement inspection lazily rather than porting the full snapshot/digest product |
| Production plan §13.4: fair READY/PENDING/UNAVAILABLE source scheduling | Retain the behavior and adversarial tests; rewrite a small route-free scheduler after mechanics are stable |
| Production plan §13.5: runtime-local randomness and clean teardown | Recover context-local RNG now; reject per-runtime daemon threads and global contamination |
| Production plan §14.5: one locomotion/checkpoint owner | Recover movement settlement truth, but replace the duplicated Move/Jump/connector loops with one executor |
| Canonical architecture §17.1: `WorldTopology` extension seam | Recover reciprocal boundary identity and connectors after fixing clear/reset ownership |
| Canonical architecture §17.2: movement query/plan authority | Keep engine-owned path/OA facts; reject eager full-world deep hashing on every inspection/revalidation |
| Canonical architecture §19.2/§19.7: standalone and feature-extension gates | Build route-free scripted/AI terminal gates and connector/movement proving grounds before any hosted/SDK cut |
| Production plan §21: deletion only after explicit parity approval | Recover no deletions from `cursed-sol`; current rich behavior remains evidence until independently replaced |

The accepted plan's ownership boundaries remain useful. Its transaction,
durability, SDK, and frontend cuts are not prerequisites for the engine recovery
listed here.

## Comparison integrity

- `git merge-base feat-zaxis cursed-sol` is exactly `e745f389...`.
- `cursed-sol^` is exactly `e745f389...`.
- At the review cutoff, `git diff -w --exit-code` and
  `git diff --ignore-cr-at-eol --exit-code` both reported no semantic working
  tree difference from `feat-zaxis`. The large dirty list was CRLF churn, not a
  second implementation baseline.
- All abandoned code references below can be inspected without switching
  branches, for example:

  ```bash
  git show cursed-sol:dnd/core/randomness.py
  git diff feat-zaxis..cursed-sol -- dnd/actions.py
  ```

## Recovery ranking

| Rank | Capability | Product/mechanics value | Coupling in abandoned code | Decision |
|---:|---|---|---|---|
| 1 | Encounter-local deterministic RNG | Very high | Low | Recover now, with a small adaptation |
| 2 | Idempotent spatial-effect reveal | High correctness value | Tiny | Recover now |
| 3 | Authored condition and Counterspell log identity | High replay/UI/debug value | Low-to-medium | Recover selected hunks now |
| 4 | Movement target path/OA facts and movement termination truth | High gameplay/AI value | Medium | Recover in focused mechanics patches |
| 5 | Character portrait propagation | Real product value, not core mechanics | Tiny | Recover opportunistically |
| 6 | Canonical reciprocal wall/door identity | High world-model value | Medium | Rewrite/port after fixing lifecycle bugs |
| 7 | Traversal connectors | High 2.5-D and map value | Medium-high | Rewrite around one movement executor |
| 8 | Shared Human initiative block | High multi-character UX value | High encounter-flow risk | Port after dedicated characterization |
| 9 | Minimal route-free source scheduler | High architectural value | Very high in abandoned implementation | Recover behavior/tests, rewrite implementation |
| 10 | Full actor-affordance snapshot/digest system | Useful goal, expensive implementation | Very high | Do not recover wholesale |
| 11 | Runtime V2 durability/player-product/SDK/server cut | Not a core-engine feature | Extreme | Do not recover |

## Recover now: small, high-confidence code

### 1. Encounter-local deterministic randomness

The current engine routes ordinary dice through `dnd/core/dice.py`, but many
rules still call process-global `random.randint` directly. That means a seeded
encounter does not actually control Counterspell checks, Bless/Bane/Guidance,
Sleep/Color Spray pools, Great Weapon Fighting rerolls, Prismatic Spray,
Heroes' Feast healing, and several other mechanics.

The useful abandoned implementation is:

- all of `cursed-sol:dnd/core/randomness.py`;
- the direct `randint` import substitutions in:
  - `dnd/blocks/health.py`;
  - `dnd/classes/fighter.py`;
  - `dnd/core/dice.py`;
  - `dnd/items/environment_interactables.py`;
  - `dnd/spells/abjuration.py`;
  - `dnd/spells/conjuration.py`;
  - `dnd/spells/divination.py`;
  - `dnd/spells/enchantment.py`;
  - `dnd/spells/evocation.py`;
  - `dnd/spells/illusion.py`.

Why it is good:

- `ContextVar` scopes the generator to the active serialized encounter call;
- it never calls process-global `random.seed`;
- unscoped legacy behavior still uses Python's ordinary generator;
- it is independent of FastAPI, SDKs, persistence, and player projection.

Required adaptation:

- do not make `dnd/runtime` the only owner capable of installing the scope;
- expose the scope at the existing encounter/controller execution boundary;
- reconcile it with `fixed_dice_faces()` so tests have one explicit override
  hierarchy rather than two competing randomness systems.

Required gates:

- same seed plus same commands produces the same objective event/log trace;
- different seeds diverge where stochastic rules execute;
- nested/failing scopes restore the prior generator;
- concurrent context-local scopes do not contaminate each other;
- a static scan finds no gameplay `random.randint` bypasses.

### 2. Spatial-effect reveal must be one-way and idempotent

The current `SpatialEffect.publish_revealed()` emits a reveal event without
clearing `stealth_dc`, and repeated calls can publish repeated reveal events.
The abandoned implementation contains the correct four-line semantic fix in
`cursed-sol:dnd/spatial_effects.py`:

```python
if self.stealth_dc is None:
    return None
self.stealth_dc = None
```

This is a real engine bug fix, independent of Runtime V2. Recover it nearly
verbatim and add a focused regression proving:

- the first reveal clears hidden state and publishes once;
- the second reveal is a no-op;
- projection/replay cannot observe the effect becoming hidden again.

Do not couple this patch to the abandoned located-observer projection changes.

### 3. Typed authored condition and Counterspell truth

Several selected hunks improve objective facts without requiring the new
runtime:

- `ConditionLogData` in `dnd/core/combat_log.py`;
- `condition_content_identity` captured by condition apply/remove declarations
  in `dnd/core/base_conditions.py`;
- typed immune-condition result data in `dnd/entity.py`;
- bounded and internally consistent Counterspell event/log evidence in
  `dnd/spells/abjuration.py` and `dnd/core/combat_log.py`;
- exact authored identities for the Counterspell reaction and incoming spell.

These eliminate name-as-identity behavior and make replay/debugging materially
safer.

Recover selectively. Do **not** take the abandoned enum/schema rename from
`SPATIAL_EFFECT` to `SPATIAL_EFFECT_CHANGE` in the same patch; that is a wire
compatibility migration, not a mechanics fix. Likewise, add a new typed
spatial-effect-interaction log without renaming an existing entry type unless
all current consumers are migrated deliberately.

Required gates:

- automatic Counterspell cannot fail or carry check evidence;
- checked Counterspell requires the exact DC and result relation;
- legacy unbound conditions remain explicitly `None`, never names masquerading
  as identities;
- current player/objective log privacy tests remain green.

### 4. Canonical equipment slot conversion helpers

`cursed-sol:dnd/core/equipment_types.py` adds one closed mapping between
`VisualLoadoutSlot` names and engine `WeaponSlot`/`BodyPart`/`RingSlot` values.
The current branch has duplicate server conversions in at least
`server/character_equipment_mutation_worker.py` and
`server/character_settlement.py`.

Recover the lower helper, then migrate callers in a separate mechanical patch.
This removes server-owned interpretation of an engine enum without introducing
any new runtime authority.

### 5. Preserve a selected character portrait during encounter materialization

The one-field addition to `CharacterDeploymentSnapshot` and the small
assignment to `materialized.appearance.portrait_key` in
`dnd/scenarios/encounter_assembler.py` preserve a real product choice through
the character-to-encounter boundary.

This is not combat mechanics, but it is useful, cheap, and independent of the
failed architecture. Recover it if the restored frontend expects profile or
creator portraits in play.

## Recover as focused mechanics patches

### 6. Movement facts and settlement corrections

The abandoned movement changes contain genuine improvements:

- movement boundaries retain mode, trajectory, path index, total length, and
  optional connector identity;
- Jump retains requested versus actual destination and a typed termination
  reason;
- Jump consumes movement for each committed step before a post-commit
  incapacity can end the loop;
- voluntary Move gives checkpoint observation/revalidation a chance to see the
  committed step before terminating for post-step incapacity;
- forced movement can publish a distinct committed checkpoint without
  consuming voluntary movement or triggering voluntary step rules;
- action discovery discloses the selected path and ordered opportunity-attack
  exposures instead of forcing consumers to reconstruct them.

Relevant abandoned locations:

- `dnd/core/action_execution.py`;
- Move, Jump, Shove, and `MovementEvent` hunks in `dnd/actions.py`;
- `dnd/action_dispatch.py`;
- `BaseAction.get_traversal_connector_uuid()` in
  `dnd/core/base_actions.py`;
- the path/OA additions in `Entity.get_available_actions()`.

Do not port the `CausalCheckpointSink` as a durability/player-product owner.
The current engine already has `MovementContinuationGuard`; retain a small
engine callback or result boundary and let transports observe it later.

Most importantly, use this recovery to create **one** voluntary movement
executor for Walk/Swim/Jump/Fly/connector legs. The abandoned branch did not
achieve the plan's unification: it added another roughly 300-line
`TraverseConnector` action and continued to maintain separate loops.

Required gates:

- Walk, Swim, Jump, Fly, and connector travel use the same committed-step
  accounting contract;
- forced movement remains mechanically distinct;
- movement is never free when a committed arrival causes incapacity;
- requested/actual destination, path, spent/remaining movement, trajectory,
  interruption, and settlement are internally consistent;
- OA exposure comes from engine discovery, not a server or client recompute;
- no callback, queue, or thread remains open while awaiting a player decision.

### 7. Canonical reciprocal wall and door identity

`cursed-sol:dnd/core/world_topology.py` solves a real model problem: the east
side of one cell and west side of its neighbor become views of one stable
physical boundary. Doors retain one object-backed identity while open/closed
state and blocked channels change. That is valuable for rules, projection,
editor round trips, and later height-aware structures.

The useful pieces are:

- `PhysicalBoundary` and its canonical adjacent-cell identity;
- deterministic side indexes;
- object-to-boundary ownership;
- immutable topology snapshots and named revisions;
- `ItemDirectionalStructureProvider` as a dependency-neutral structural seam.

Do not copy the integration unchanged. The abandoned `GridMap.clear()` clears
connector registries but never resets `_world_topology`, so stale wall/door
facts can survive a map clear. The integration also updates indexes eagerly
inside general grid mutation paths; it needs a measured lifecycle and no-op
revision policy.

Recover first with the route-free portions of
`tests/engine/test_world_topology_identity.py`:

- reciprocal queries share one boundary ID;
- door open/close changes state without changing identity;
- intrinsic borders receive one reciprocal identity;
- snapshot round-trip preserves IDs.

Add missing clear/reset/removal/replacement tests before using it in live maps.

### 8. Authored traversal connectors

`cursed-sol:dnd/core/traversal_connectors.py` is a useful prototype for stairs,
ladders, ramps, lifts, and passages. It correctly separates:

- stable objective connector identity;
- exact support-tile identities;
- endpoint elevations;
- world-space presentation geometry;
- directed/bidirectional traversal;
- movement cost and a deterministic dependency digest.

The corresponding grid indexes and `TraverseConnector` action demonstrate a
working direction, but should be rewritten around the unified movement
executor. Do not copy the action verbatim: it defines `_apply_costs` twice in
`cursed-sol:dnd/actions.py`, and no dedicated route-free connector mechanics
test catches that duplication.

Also be honest about scope: the abandoned commit does **not** contain the full
2.5-D architecture claimed by its plan/ledger. There are no engine symbols for
`surface_elevation_ft`, `ceiling_elevation_ft`, `LocomotionProfile`, roof facts,
or finite vertical structural spans. What exists is a flat grid plus an
elevation-bearing connector prototype and the pre-existing `Fly` subclass.

Required connector gates:

- support-tile replacement/removal invalidates the connector;
- `GridMap.clear()` removes every connector and topology fact;
- disabled and one-way connectors fail correctly from each endpoint;
- stale connector digest cannot execute;
- travel spends the exact cost once and emits one lifecycle;
- both endpoints and geometry remain objective facts, with privacy filtering
  left to the existing player projection boundary.

### 9. Same-Human multi-actor initiative block

The most substantial good gameplay feature is the Encounter-owned shared
initiative block in:

- `dnd/core/decision_types.py`;
- the `dnd/encounter.py` initiative-block changes;
- `Controller.human_control_identity()`;
- the initiative-block events in `dnd/core/events.py`;
- `tests/engine/test_encounter_shared_initiative.py`.

It supports:

- one Human control identity acting through consecutive initiative slots;
- both actors being open without executing simultaneously;
- reversible End Turn/Cancel End Turn readiness;
- one ordered causal execution identity;
- dead/dying/surprised auto-resolution;
- forward extension across dead intervening slots;
- revived skipped actors enrolled once at the round tail;
- stale revision and wrong-controller rejection;
- clean terminal closure.

This directly addresses the real multi-character Human requirement that the
old scalar turn UI cannot represent well. The seven route-free engine tests are
valuable and should be recovered as characterization even if the code is
rewritten.

Port cautiously. The abandoned patch changes about 944 lines in
`dnd/encounter.py` and replaces the basic turn lifecycle. Before landing it:

- give the control identity an explicit meaning rather than relying only on
  reusing the same `HumanController` object;
- prove legacy single-actor, AI, Codex, surprise, death-save, resurrection, and
  encounter-terminal behavior unchanged;
- keep grants, sessions, perspectives, and HTTP outside `Encounter`;
- do not require Runtime V2 command receipts to mark readiness.

## Recover the behavior, not the abandoned implementation

### 10. A small route-free encounter/source boundary

The accepted architecture's valuable central idea remains valid: scripted and
AI-vs-AI encounters should be runnable without importing `server`. The
abandoned branch proved portions of that direction, but its implementation
combined the small need with player-product projection, durability artifacts,
lookup evidence, host fencing, replay obligations, and generated contracts.

Potentially reusable concepts:

- the one-to-many entity mapping in `dnd/runtime/assignments.py`;
- a tiny `CommandSource` protocol from `dnd/runtime/sources.py`;
- READY/PENDING/UNAVAILABLE and round-robin fairness behavior from
  `dnd/runtime/cooperative_scheduler.py`;
- the fairness and stale-basis cases in
  `tests/runtime/test_cooperative_source_scheduler.py`;
- native AI emitting an intent/command instead of owning a special server path.

Do not reuse:

- `dnd/runtime/runtime.py` (5,004 lines);
- `dnd/runtime/command_service.py` (2,258 lines);
- `dnd/runtime/player_product/runtime.py` (5,556 lines);
- the 24-file, roughly 11,500-line V2 contract family;
- the per-runtime finalizer thread and durability state machine.

A replacement should initially do only this:

```text
prepare encounter -> expose current control boundary -> accept one engine
intent -> execute through existing action dispatch -> return objective result ->
advance or stop
```

Then add plural assignments and fair local sources. Persistence, reconnect,
SDKs, player presentation, and hosted control must remain separate layers and
must not be prerequisites for creating a game.

## Code that should remain abandoned

### Full Runtime V2 player-product and durability stack

Do not recover the generated contract forest, player-product reducer/projector,
durability artifacts, host fencing, command lookup proof hierarchy, replay
capture obligations, or hosted control journal as core-engine code. They are
transport/product concerns and were the main source of coupling and volume.

The branch created:

- 54 new `dnd/runtime` files and 36,419 lines;
- 12,907 lines under `dnd/runtime/player_product`;
- 66,034 lines of Runtime V2 developer tooling;
- over 63,000 TypeScript SDK additions;
- a 5,004-line runtime aggregate and a 5,556-line player-product owner.

That scale made a simple game creation path construct identities, projections,
digests, caches, artifacts, and transport products before the user could play.

### Full `inspect_actor_affordances()` and `MovementQueryService`

The goal—side-effect-free inspection—is valid. The implementation is not worth
recovering wholesale.

At `cursed-sol:dnd/actor_affordances.py:374-475`, one inspection:

1. snapshots resources and equipment;
2. calls full action discovery;
3. serializes every action and handler to JSON;
4. deserializes them into new Pydantic objects;
5. snapshots resources/equipment again;
6. hashes action, handler, resource, inventory, and equipment payloads;
7. builds movement plan sets for every movement action.

`MovementQueryService.query_action()` then constructs every target plan and
hashes knowledge, resources, stance, conditions, capabilities, connectors, and
every relevant tile/object/effect hazard. The player-product runtime invokes
this during authority projection and can invoke it again for command
revalidation.

This is a plausible direct contributor to slow compose/bootstrap. Replace it
with lazy, revision-keyed queries:

- inspect only the selected/visible actor;
- compute targets only when the relevant UI/policy asks for them;
- retain engine object identity privately instead of JSON round-tripping it;
- use existing named revision counters before considering deep digests;
- measure cold/warm calls before adding caches.

### Per-runtime command-finalizer thread

`cursed-sol:dnd/runtime/player_command_work.py:125-145` starts one daemon
`Thread` as soon as the work owner is constructed. `EncounterRuntime`
constructs that owner during runtime creation.

The thread is not the only cause of multi-second creation, but it is unnecessary
for a local synchronous encounter and makes lifetime/failure behavior harder to
reason about. Do not restore it as a core requirement. If hosted request
cancellation later needs a request-independent owner, keep that owner in the
host adapter or use an explicitly managed shared executor after measurement.

### Retirement of the existing direct AI executor

The abandoned `dnd/ai/runtime/execution.py` replaces actual policy validation
and dispatch with an unconditional `RuntimeError` telling callers to use
`EncounterRuntime`. Do not recover that deletion. It removes a working gameplay
vertical before the replacement is proven.

A future route-free command source may adapt the existing AI policy, but the
old execution path should be removed only after an equally direct tested game
works.

### Durability-gated passive publication

`dnd/core/passive_publication.py` is tidy code, but it exists solely to delay
event/log observer delivery until Runtime V2 artifact durability. It is not a
core gameplay feature. Keep current synchronous engine events; let a future
persistence/host layer stage its own outgoing publication.

### Authored action-menu taxonomy as a core dependency

The abandoned content metadata adds a large action/menu/icon taxonomy and
touches many spells/items/actions. Content-driven UI grouping can be useful,
but it is not required to execute mechanics and should not block game creation.
Recover it later as optional presentation metadata only after the restored
frontend's actual requirements are characterized.

Do not recover the hard-coded `floor.png`/`water.png` additions as engine
authority. They are presentation fallbacks, not world mechanics.

### Old-code deletions and compatibility removals

Do not copy any deletion from `cursed-sol`. In particular, do not remove the
old rich player projection, direct AI behavior, replay routes, SDK exports, or
their tests merely because a replacement contract compiles. The failed cut
demonstrated that compile-green is not product parity.

## Specific defects proving the commit is not cherry-pickable

1. `TraverseConnector` defines `_apply_costs` twice in
   `cursed-sol:dnd/actions.py`.
2. `GridMap.clear()` clears connector maps but not `_world_topology`, permitting
   stale physical boundaries after clear/reuse.
3. `inspect_actor_affordances()` performs a full JSON detach/reattach and deep
   movement dependency scan instead of a cheap read view.
4. player command finalization starts a dedicated daemon thread per runtime.
5. direct AI execution is replaced by an unconditional error.
6. the hosted join path can install controller/entity authority and then fail
   constructing attachment evidence after its rollback scope has ended.
7. concurrent exact retries map the same runtime work to different host future
   identities, so host finalization/persistence can run twice.
8. the claimed complete 2.5-D model is absent; only a connector prototype was
   added.

The last two are server/runtime defects rather than core mechanics, but they
confirm that no larger branch slice should be trusted as an atomic recovery.

## Proposed recovery sequence

### Patch A — deterministic mechanics and tiny correctness fixes

- encounter-local RNG seam and all direct gameplay random call sites;
- spatial-effect reveal idempotency;
- equipment slot mapping;
- optional portrait propagation.

Budget: small. No server/SDK/frontend changes required.

### Patch B — typed objective event/log facts

- condition identity and typed condition logs;
- strict Counterspell resolution evidence;
- additive spatial-effect-interaction log type without renaming old wire
  values.

Budget: small-to-medium. Preserve current player privacy projection.

### Patch C — movement correctness

- enrich current movement boundary/result types;
- fix Jump step accounting and termination truth;
- expose path/OA facts from engine discovery;
- add forced-movement checkpoint facts without Runtime V2 coupling.

Budget: medium. Do not add connectors yet.

### Patch D — canonical topology

- reciprocal wall/door identity;
- structural provider seam;
- snapshot and revisions;
- complete clear/reset/replacement tests.

Budget: medium. Measure map build and door-toggle cost.

### Patch E — unified locomotion and connectors

- one movement executor;
- connector registry and action as one leg type;
- Walk/Swim/Jump/Fly/connector parity tests;
- no player-product or generated-contract dependency.

Budget: medium-to-large. Must remain playable after each step.

### Patch F — multi-character initiative

- explicit control identity;
- Encounter-owned plural block;
- End/Cancel End semantics;
- all seven abandoned route-free tests plus existing encounter tests.

Budget: large and high risk; land independently.

### Patch G — minimal standalone orchestration

- small assignment/source protocol;
- plural boundary and fair source polling;
- scripted and native-AI terminal games without `server` imports;
- no durability, SDK, player projection, or hosted lifecycle in the first cut.

Budget: deliberately bounded. Stop if it starts recreating the abandoned
contract/durability forest.

## Acceptance and performance guardrails

Every recovery patch should satisfy all of the following:

- current frontend/backend game creation remains playable;
- no new worker thread, process, network request, persistence write, full player
  projection, or SDK generation occurs during pure encounter construction;
- cold and warm compose/create timings are recorded by named subphase;
- no single new engine query exceeds the agreed local budget without a profile;
- action inspection is lazy and revision-keyed;
- route-free engine tests are primary; HTTP/browser tests are integration
  confirmation, not the only proof;
- no compatibility owner is deleted in the same patch that introduces its
  replacement;
- each patch can be reverted independently without corrupting saved state;
- plan/ledger completion claims require executable evidence, not symbol
  presence or generated-schema freshness.

## Bottom line

The abandoned branch contains roughly **eight** good engine capabilities, not
one good architecture package. Recover the tiny correctness work directly,
rewrite the topology/movement/initiative pieces behind lower tests, and salvage
only the behavioral requirements of the standalone scheduler.

The Runtime V2 player-product/durability/SDK/host stack is not necessary to
recover those features and should not be allowed back onto game creation's hot
path.
