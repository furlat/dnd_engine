# Canonical Player Presentation: Connectors, Locomotion, and Structural-Edge Identity

**Status:** FROZEN REVISION 14 — INTERNAL, IMPLEMENTATION-TASK, AND NEUROCLIENT REVIEWS REQUIRED
**Date:** 2026-08-09
**Scope:** one bounded backend/SDK/NeuroClient presentation-seam unit
**Implementation authority:** not granted until all three independent reviewers accept this exact revision and hash

## 1. Outcome

This unit closes three player-presentation seams without changing game mechanics:

1. traversal connectors retained by the canonical SDK replica become first-class render facts instead of disappearing in `renderProjection.ts`;
2. player movement cues preserve the real locomotion family, trajectory family, authorized support elevations, and safe connector presentation identity already authored by the engine;
3. the SDK exposes the stable canonical identity it already computes for structural edges, so clients stop rebuilding that key.

The completed ownership chain is:

```text
engine events / subjective world
        |
        v
server privacy projection + player cue mapper
        |
        v
generated SDK decoder + canonical subjective replica
        |
        v
SDK render projection / typed presentation cue
        |
        v
NeuroClient presentation-frame coordinator
        |
        v
presentation replica -> stateSync / VisualTransaction
        |
        v
existing planar renderer / one locomotion-session executor
```

No frontend code may query objective engine state, reconstruct hidden connector facts, read the canonical replica ahead of the presentation replica, or maintain a second world reducer.

## 2. Current defects, stated narrowly

### 2.1 Connector render loss

The backend and canonical SDK replica already retain the player-safe connector facts:

- `server/world_contracts.py::APIGrid.connectors` carries typed connectors;
- `server/world_projection.py::project_grid()` includes a subjective connector only when both endpoints are currently authorized to the requester;
- `server/player_replication_contract.py` carries connector-set replacement patches;
- `sdk/typescript/src/reducer.ts` retains connectors and validates identity, bounds, endpoint visibility, and elevation consistency.

The loss occurs later: `sdk/typescript/src/renderProjection.ts::RenderGrid` projects tiles and structural edges but omits connectors. A client consuming `ReplicatedRenderWorld` cannot render them without bypassing the SDK render owner.

### 2.2 Locomotion cue collapse

`MovementPresentationCue` currently has only `walk | jump` and an ordered list of two-dimensional positions. `server/player_replication/mapper.py::_add_movement_nodes()` maps direct arcs to Jump and effectively every other accepted movement to Walk. `TraverseConnectorEvent` is not a movement root there and may instead fall through the generic action-cue path.

The engine already owns the exact facts needed by presentation:

- `MovementEvent.movement_mode`: walking, swimming, flying, or burrowing;
- `MovementEvent.trajectory`: path;
- `JumpEvent.trajectory`: direct arc;
- `TraverseConnectorEvent`: exact connector UUID, authored ID, kind, presentation key, and revision;
- `StepMovementEvent`: exact trajectory plus authorized source/destination support elevation.

The cue currently discards those facts and can mislabel Swim, Fly, Burrow, and connector traversal as Walk.

### 2.3 Structural-edge identity is real but private

`sdk/typescript/src/renderProjection.ts` already normalizes north/east/south/west tile-local halves into one canonical north/east owner. Existing tests cover reciprocal deduplication, conflicts, and persistent open-door identity.

The problem is ergonomic: `RenderStructuralEdge` exposes only the identity components, so NeuroClient reconstructs its own string key in `app/src/tiles.ts`. This unit exposes the existing SDK identity; it does not redesign edges or add provider identity.

## 3. Non-negotiable ownership rules

### 3.1 Canonical state versus presentation

- `APIGrid.connectors` remains canonical replica state.
- `RenderGrid.connectors` is a pure, deterministic, read-only projection of that state.
- `MovementPresentationCue` is delivery-time presentation evidence derived from accepted subjective event facts.
- A movement cue never mutates replica state and never authorizes commands.
- NeuroClient state synchronization consumes only `ReplicatedRenderWorld`, never raw `APIGrid` or an objective service.
- NeuroClient cue ingestion consumes only generated, SDK-validated presentation cues.
- The canonical replica may disable/clear interaction immediately, but visible motion advances only through the accepted-frame presentation transaction.

### 3.2 Privacy

- The render layer may copy only fields already present in the privacy-filtered `APIGrid.connectors` row.
- The cue mapper validates each current unfiltered Step against its exact accepted root EFFECT before applying subjective grants.
- For path movement, it may copy only the maximal contiguous run of current-frame Steps whose geometry/elevation passes the existing subjective grant. It never joins runs across an unauthorized edge.
- For Jump and connector transfer, the one engine-authored Step is also the whole presentation leg, so both authorized endpoints are required.
- It may copy root classification facts only when the exact root event passes the event-local subjective identity grant.
- A Step grant never lends authorization to root movement mode, connector identity, content attribution, labels, or root endpoints.
- Missing root authorization omits every cue for that root as privacy-valid absence. A missing PATH Step grant omits only that edge; an independently authorized later edge may produce a later frame-local cue without revealing or joining the hidden gap. A missing Jump/connector endpoint omits its one leg. None of these privacy-valid omissions is a projection fault.
- Once a frozen context resolves, a causally malformed root/Step set produces `SubjectiveEventProjectionError` before subjective filtering and uses the existing journal resync/fault path. Failure to capture/resolve the bounded context itself uses the explicit reset-required boundary in §§4.6/5.1 instead; neither case is privacy-valid omission.
- No private connector support UUID, objective digest, movement/action cost, provocation policy, bidirectionality, or hidden endpoint is added to the render record or cue.
- This unit adds no movement content attribution. Existing independently authorized attribution remains independent; root behavior-binding evidence is not inferred or copied merely because the Step is visible.

### 3.3 No new mechanics authority

- `Move`, `Swim`, `Fly`, `Jump`, and `TraverseConnector` remain separate engine actions and transaction owners.
- This unit does not merge their executors, costs, settlement, OA, collision, or position logic.
- `MovementMode`, `MovementTrajectory`, `TraversalConnectorKind`, and connector root evidence remain engine-owned.
- Frontend switches on the generated closed presentation enums, never action names, connector names, authored IDs, or `presentation_key` strings.
- There is no new `Burrow` action. The Burrow presentation proof uses a real `Move` configured with `MovementMode.BURROWING`.

### 3.4 One frontend locomotion owner

- All locomotion families enter one `VisualTransaction`-owned locomotion-session executor.
- `eventIngestion.ts` remains the sole family-neutral `PresentationFrameCoordinator`, driven by one serialized `PresentationHeadDrain`. The drain owns at most one in-flight journal head: it does not map, stage, enqueue, execute, commit, or reset frame N+1 until frame N has reached its one terminal path and left or replaced the journal. It stages an accepted normal head, resolves its one presentation barrier (immediate for mapper-confirmed state-only work, aggregate `ClipQueue` terminal otherwise), verifies the frame/generation/cursor, and performs the one whole-frame normal presentation-journal commit. A server-authored reset-required head takes the separate reset branch defined in §§4.6 and 7.6 only when every earlier head is gone; it is never reclassified as normal/state-only success.
- `eventIngestion.ts` does not branch by locomotion family, buffer Jump, call clips directly, or perform a family-specific commit.
- Jump, connector transfer, and path movement may use different stateless visual primitives, but they do not own separate queues, sequence journals, deferred-frame protocols, or commit paths.
- The presentation journal commits the same accepted normal frame only after the one frame barrier succeeds: immediately for a mapper-confirmed state-only frame, or after `ClipQueue` returns the aggregate transaction success. Reset-required frames use one SDK-owned atomic presentation reset method and no normal commit.
- Accepted later frames remain inert journal entries until they become the exact head. They consume no `ClipQueue` slot, own no staging token or watchdog, and cannot cancel or observe the active head.

## 4. Public contracts

### 4.1 SDK render connector

Add SDK-owned, non-generated render types in `sdk/typescript/src/renderProjection.ts`:

```ts
export interface RenderTraversalConnectorEndpoint {
  readonly position: readonly [number, number];
  readonly elevation_feet: number;
}

export interface RenderTraversalConnector {
  readonly uuid: string;
  readonly authored_id: string;
  readonly kind: APITraversalConnector["kind"];
  readonly presentation_key: string;
  readonly endpoints: readonly [
    RenderTraversalConnectorEndpoint,
    RenderTraversalConnectorEndpoint,
  ];
  readonly enabled: boolean;
}
```

`RenderGrid` gains:

```ts
readonly connectors: ReadonlyArray<RenderTraversalConnector>;
```

This is deliberately narrower than `APITraversalConnector`.

Included because rendering needs them:

- runtime UUID: retained render-node identity;
- authored ID: stable authored identity and diagnostics;
- kind and presentation key: safe semantic presentation identity;
- authorized endpoint positions/elevations: geometry;
- enabled: deterministic live/inert style.

Excluded because they are execution-only or private:

- support tile UUIDs;
- objective digest;
- movement cost;
- action cost type/amount;
- provocation policy;
- bidirectionality.
- revision.

Executable direction and affordability remain action-discovery facts. If a later product design needs a one-way visual, that is a separately reviewed contract addition.

### 4.2 Projection-neutral connector validation

Extract one SDK structural validator used by both objective and subjective render paths:

```ts
export function assertGridConnectorStructure(grid: APIGrid): void;
```

It validates only facts available in either projection:

- connector runtime UUID and authored ID uniqueness;
- two distinct endpoints;
- endpoint positions in grid bounds;
- each endpoint resolves to a projected tile;
- each endpoint elevation equals the projected support tile elevation.

Subjective replica validation remains stricter and additionally requires current authorization/visibility for both endpoints. Objective rendering does not invent that privacy rule, but it must run the common structural validator before projecting connectors. This closes objective-versus-subjective parity without turning render projection into a game-state authority.

### 4.3 Deterministic connector projection

Add:

```ts
export function projectTraversalConnectors(
  connectors: ReadonlyArray<APITraversalConnector>,
): Array<RenderTraversalConnector>;
```

Rules:

1. copy only the fields listed in §4.1;
2. deep-copy endpoint tuples;
3. preserve authored endpoint order;
4. sort deterministically by `(authored_id, uuid)`;
5. do not query services, caches, or objective state;
6. run only after `assertGridConnectorStructure()` and any subjective-only replica validation;
7. use the same pure function inside objective and subjective `projectGrid()` paths.

Direct SDK unit tests may call it with a structurally valid decoded connector. Product paths must reach it through `projectObjectiveRenderWorld()` or `projectSubjectiveRenderWorld()`.

### 4.4 Strict typed locomotion cue language

Replace the two-value `MovementKind` discriminator with closed player-replication models:

```python
class LocomotionFamily(str, Enum):
    WALK = "walk"
    SWIM = "swim"
    FLY = "fly"
    BURROW = "burrow"
    JUMP = "jump"
    CONNECTOR = "connector"


class LocomotionTrajectory(str, Enum):
    PATH = "path"
    DIRECT_ARC = "direct_arc"
    CONNECTOR_TRANSFER = "connector_transfer"


class LocomotionAnchor(PlayerReplicationModel):
    position: Tuple[StrictInt, StrictInt]
    elevation_feet: StrictInt


class ConnectorPresentationIdentity(PlayerReplicationModel):
    uuid: UUID
    authored_id: str = Field(
        min_length=1,
        pattern=CONNECTOR_AUTHORED_ID_PATTERN,
    )
    kind: TraversalConnectorKind
    presentation_key: str = Field(
        min_length=1,
        pattern=CONNECTOR_PRESENTATION_KEY_PATTERN,
    )
    revision: StrictInt = Field(ge=1)
```

Promote the existing canonical regex strings in `dnd/core/traversal_connectors.py` to dependency-neutral public constants and use those same constants in `TraversalConnectorDefinition` and this player contract. Do not copy or widen the patterns. In particular, the first character after `connector.` and the first character of a presentation key remain a letter.

Every nested cue record inherits `PlayerReplicationModel`, so it is frozen and `extra="forbid"`. Positions and elevations reject bool/string coercion. UUID, authored identity, presentation key, and revision use explicit types/constraints. Because engine elevation is step-authored, cue validation also requires each `elevation_feet` to be divisible by five.

`MovementPresentationCue` retains its graph/cursor fields, endpoint outcome, and perception-commit semantics, but replaces:

```text
movement_kind -> locomotion_family
trajectory     -> anchors
```

and adds:

```text
trajectory_family
connector: ConnectorPresentationIdentity | None
```

Remove `path_start_index` and `path_total_steps`. Per-Step subjective frames already have authoritative source/presentation cursor order; exposing objective path indices/totals creates a second sequencing protocol and leaks hidden path length. A client never waits for a missing movement fragment. There is no compatibility alias and no duplicate legacy field.

Remove `movement_sequence_id` from the player cue as well. The normal cue `presentation_id` identifies the one independently terminal delivered run/leg. Root-lineage correlation remains server-side diagnostic evidence only; no player-visible token may link two authorized runs across a hidden PATH edge.

### 4.5 Cue-level invariants

| Family | Trajectory | Anchors | Delivery unit | Connector identity |
|---|---|---|---|---|
| Walk/Swim/Fly/Burrow | Path | two or more | maximal contiguous authorized run in the current frame | forbidden |
| Jump | Direct arc | exactly takeoff + landing | one independently terminal leg | forbidden |
| Connector | Connector transfer | exactly source + destination | one independently terminal leg | required |

Additional rules:

- a not-committed cue represents exactly one attempted edge and requires a delivered pre-edge reaction child;
- non-connector families reject connector identity;
- a committed cue states that each represented Step committed when it was authored; it does **not** assert that the entity still occupies the final anchor after synchronous forced displacement or another accepted child effect;
- frame validation preserves only the negative rule: a `NOT_COMMITTED` cue must not be used as proof that the attempted destination became occupied;
- no validator requires final frame occupancy to equal the final cue anchor;
- neither objective Step index nor root/Step total path length is serialized in the cue;
- one cue is independently terminal and its ordinary `presentation_id` is local to that delivered run/leg; no public root-stable movement identifier or predecessor/successor wait exists.

These are presentation invariants, not transition-legality, cost, collision, or current-occupancy validation.

### 4.6 Requester-safe presentation reset directive

Add one generated frame-level discriminator; it is not a cue and carries no root/path identity:

```python
class PresentationDeliveryMode(str, Enum):
    NORMAL = "normal"
    RESET_REQUIRED = "presentation_reset_required"


class PresentationResetReason(str, Enum):
    SOURCE_PRESENTATION_DISCONTINUITY = "source_presentation_discontinuity"


class EncounterTerminalPresentationFact(PlayerReplicationModel):
    encounter_uuid: str
    source_event_uuid: UUID
    source_event_cursor: int = Field(ge=1)
    terminal_authority_id: str
    reason: str | None = None
    projected_combatant_uuids: tuple[str, ...] = ()
    terminal_barrier: Literal[True] = True
```

`SubjectiveReplicationFrame` adds:

```python
presentation_delivery: PresentationDeliveryMode = PresentationDeliveryMode.NORMAL
presentation_reset_reason: PresentationResetReason | None = None
encounter_terminal: EncounterTerminalPresentationFact | None = None
```

Exact invariants:

- `NORMAL` requires a null reset reason and null frame-level terminal fact and retains the ordinary patches/cue window rules, including the existing `EncounterPresentationCue` terminal authority;
- `RESET_REQUIRED` requires one closed reason, an empty `presentation` tuple, and no presentation-cursor advance; it still carries the exact subjective world patches and source/observation watermarks for that reducer boundary and may carry the one frame-level terminal fact below;
- if the closure callback has no unconsumed source slot because the last committed Step frame already consumed the source prefix, it may append exactly one observation-only reset control frame: source and presentation cursors remain unchanged, observation advances by one, patches are empty, and the frame records the already-verified closed-through source cursor. This does not invent an engine event or gameplay fact;
- the sole public reason exposes no event family, root UUID/lineage, alias count, hidden endpoint/path/elevation, observer set, internal exception text, or cross-perspective correlation; exact context-versus-lifecycle cause remains host-internal diagnostics only;
- a reset frame says only that visible presentation must atomically rebase to the canonical subjective state carried through that frame. It does not claim animation success, command settlement, source-generation rotation, or journal corruption;
- `encounter_terminal` is present only on the **final observation delivery** produced by the depth-zero containing-batch callback, if and only if that exact final source suffix contains the one subjectively authorized accepted `EncounterEndEvent` and the resulting encounter patch/bootstrap state is ended. It reuses the existing encounter-cue projector's requester-safe encounter UUID, event UUID/cursor, reason, and projected combatant set; it carries no movement/root/reset-cause fact and is mutually exclusive with an `EncounterPresentationCue` because reset frames contain no cues;
- `terminal_authority_id` is authored only by `project_reset_encounter_terminal()` as `"{perspective_epoch_id}:{observation_cursor}:reset-terminal:{source_event_uuid}"`. The domain tag cannot collide with the existing numeric-ordinal cue IDs, it advances no presentation cursor, and Python/generated SDK frame validation recomputes it from the exact frame perspective/observation/event fields. NeuroClient and replay consumers copy the validated field; they never synthesize it from labels, the event UUID alone, coordinates, encounter state, or a fake cue;
- an intermediate poisoned-Step reset may never carry terminal authority or an ended encounter patch. If its candidate boundary has already observed the accepted `EncounterEndEvent`/ended state, that candidate is not appended to the journal; the runtime retains only a constant-size `terminal_reset_pending` marker bound to that terminal event/cursor, not a frame, patch list, world snapshot, or cue. The containing depth-zero callback reprojects once from the partition's last accepted replica to the exact final subjective state and emits one final terminal reset. A terminal reset is necessarily the last **observation frame/source slot** for that encounter: the closure callback audits and clears poison and applies deferred detach without appending an observation-only reset, and any real later source slot or observation frame after the accepted terminal event is an invariant failure. Independently finalized combat-log deliveries may still advance only the combat-log watermark through the existing terminal archive barrier; they are not observation frames or renderer work;
- a final reset source suffix that ends the encounter must carry exactly one matching terminal fact; a nonterminal suffix or an already-ended bootstrap must not invent one. Multiple/mismatched terminal events, event cursor outside the containing batch's consumed source interval, nonunique combatants, a real later source slot, or ended patch without the required fact fail frame construction before journal/replay publication;
- in this unit only `CanonicalSubjectiveReplicationRuntime` at (a) an exact poisoned-Step boundary, (b) its containing explicit-batch/immediate-singleton poison closure, or (c) the proven explicit-action missing-terminal lifecycle audit may author `RESET_REQUIRED`. Path (c) uses the same final-suffix/terminal rules: if its exact closed action batch also ends the encounter, that audit emits the one final terminal reset and no observation-only successor. The generic cue mapper, SDK, client, renderer, diagnostics, and transport never promote a normal frame into reset;
- these frames use the same retained paging, SSE, replay capture, decoder, duplicate detection, and observation ordering as every other `SubjectiveReplicationFrame`. There is no recovery endpoint, incident token, raw error parser, or hosted proxy mutation route.

The SDK journal, not NeuroClient, owns normal-head candidate reduction. Add one bounded private preview slot per journal plus these exported operations:

```ts
interface SubjectivePresentationFramePreview {
  readonly token: PresentationHeadPreviewToken;
  readonly frame: SubjectiveReplicationFrame;
  readonly candidatePresentation: SubjectiveReplicaView;
}

interface ExactResetPresentationHead {
  readonly token: PresentationResetHeadToken;
  readonly frame: SubjectiveReplicationFrame;
}

previewPresentationFrame(observationCursor: number): SubjectivePresentationFramePreview;
commitPresentationFrame(token: PresentationHeadPreviewToken): SubjectiveReplicaView;
inspectResetPresentationHead(observationCursor: number): ExactResetPresentationHead;
resetPresentationFrame(token: PresentationResetHeadToken): SubjectiveReplicaView;
```

`previewPresentationFrame()` is legal only for the exact `NORMAL` queue head. It reduces that head's patches against the current **presentation** replica—not the canonical/authoritative-ahead replica—runs the ordinary SDK world/identity validation, deep-freezes an immutable head-frame view plus candidate, and returns them with an opaque nonserializable token bound to the journal instance/incarnation, base presentation identity/digest, exact head frame identity/digest, and observation cursor. It mutates no replica, cursor, queue, presentation ID set, or external store. Repeated preview of the unchanged head is idempotent and returns the same private slot; each journal retains at most one. Head change, reset, invalidation, bootstrap replacement, seek-generation replacement, or commit clears it.

`commitPresentationFrame(token)` accepts only that journal's current unconsumed preview token and rechecks every bound identity before atomically installing the SDK-owned private candidate and removing exactly that normal head. A forged, cross-journal, replay/live-crossed, stale, or already-consumed token fails without mutation. NeuroClient receives the immutable candidate for SDK render projection/mapping/staging but never applies patches itself and never reads `journal.authoritative` to approximate the candidate. Canonical-ahead frame N+1 therefore cannot enter frame N's preview, mapper, staging, or pixels.

The generated SDK journal separately adds `inspectResetPresentationHead(observationCursor)`. It is legal only for the exact `RESET_REQUIRED` queue head and returns one deep-frozen frame plus an opaque, nonserializable `PresentationResetHeadToken` bound to the journal instance/incarnation, exact head identity/digest, and observation cursor. It performs no patch reduction, candidate construction, cue mapping, replica/cursor mutation, or external write. At most one normal-preview or reset-head private slot exists for the one journal head; head change, invalidation, bootstrap replacement, seek-generation replacement, or consumption clears it.

`resetPresentationFrame(token)` accepts only that exact current reset-head token. It applies only that frame's validated patches to a staged copy of the presentation replica, validates the result and any frame-level encounter terminal fact, atomically installs it, advances the presentation observation/world watermarks through that frame, and removes that one queue head. It never advances the cue cursor because the reset frame contains no cues. A forged, normal-head, cross-journal, replay/live-crossed, stale, or already-consumed token fails without mutation. It cannot skip an earlier queue head, consume a later authoritative snapshot, or be called by renderer/clips/stateSync.

The journal method is deliberately a one-head primitive, not a range reset. Liveness belongs to the caller's serialized `PresentationHeadDrain`: a later reset directive may disable interaction as soon as it is observed in the accepted backlog, but it remains inert until every earlier normal/reset head terminates. The drain never cancels the active normal transaction merely to reach a later reset. If an earlier normal head succeeds, it commits and leaves the journal before the drain advances. If it fails, that head's single local-recovery latch replaces the old journal/presentation generation; every later old-journal entry, including a pending reset directive, is retired with that identity and cannot request a second recovery. Thus a reset head is reached with no earlier causal transaction still owning a commit, staging token, or required clip.

`SubjectiveReplicationJournalState` exposes `pendingResetFrames: number`, maintained in O(1) on accepted ingest/reset/compaction/replacement and bounded by `presentationBacklog`. It is diagnostic/safety state only: it authorizes the unconditional frontend disable token, never frame skipping or reset execution. NeuroClient does not rescan a 16,384-frame backlog to discover reset relevance.

The same primitive is reused against an isolated replay journal. That does not grant the replay owner access to live credentials, command authority, transport, or recovery callbacks; §8.2 defines its exact consumer.

A **new** partition cannot bootstrap while a poisoned explicit-batch or immediate-singleton delivery remains unclosed. Define one generated requester-safe error body for the existing GET bootstrap route:

```python
class SubjectiveBootstrapDeferred(PlayerReplicationModel):
    code: Literal["source_batch_in_flight"] = "source_batch_in_flight"
    retryable: Literal[True] = True
    source_stream_id: str
    generation_id: str
```

The worker returns HTTP 409 with this body only when `bind()` would open an absent partition while capture is poisoned; already-open partitions and SSE/page readers continue normally and receive reset frames. The existing hosted replication GET proxy preserves the typed status/body unchanged. Change the generated SDK client boundary explicitly:

```ts
type SubjectiveBootstrapAttempt =
  | { readonly status: "ready"; readonly bootstrap: SubjectiveReplicationBootstrap }
  | { readonly status: "deferred"; readonly deferral: SubjectiveBootstrapDeferred };

bootstrapAttempt(sessionId, signal?): Promise<SubjectiveBootstrapAttempt>;
```

The existing `bootstrap()` method becomes the SDK follower's bounded wrapper around `bootstrapAttempt` and retains its successful `Promise<SubjectiveReplicationBootstrap>` contract: browser-monotonic total window 10 seconds, delay capped at 250 ms, abort-signal aware, and only the exact `deferred` branch is retryable. Success returns the ordinary bootstrap; expiry throws one exported typed `SubjectiveBootstrapUnavailableError` to the connection lifecycle. UI components do not implement another retry. No raw error text, mutation request, hidden background task, or unbounded loop is allowed. The body carries no perspective incident, root, path, or hidden facts. Direct-worker, hosted-proxy, SDK decode, abort/expiry, and successful post-closure bootstrap tests are mandatory.

## 5. Backend mapper changes

### 5.1 Per-Step runtime boundary and root context

The canonical runtime deliberately publishes each committed Step immediately, before later Steps and before root COMPLETION, so player LOS/light/world patches remain live. This unit preserves that boundary; it does not buffer movement or delay frames.

Add one bounded generation-scoped `MovementRootProjectionContextStore` owned by `CanonicalSubjectiveReplicationRuntime`. It stores a closed union of deeply immutable `@dataclass(frozen=True, slots=True)` projection facts, never an Event, `ProjectedEventSlot`, subjective world state, patch, reaction, or presentation output:

```text
key: (EventQueue generation ID, root lineage UUID)
value:
  context: PathMovementRootContext | JumpRootContext | ConnectorRootContext
  effect_uuid_aliases: bounded UUID -> source-cursor map for mechanically identical EFFECT versions, including the first EFFECT
  delivery_scope: EXPLICIT_ACTION_BATCH | IMMEDIATE_SINGLETON_SEQUENCE
  terminal_cursor: optional root COMPLETION/CANCEL cursor, set only by passive storage evidence
```

Every variant contains only:

| Variant | Immutable facts captured once |
|---|---|
| common | generation ID, first root EFFECT source cursor/UUID, exact root kind/type, `EFFECT`, source UUID, lineage UUID, and the frozenset of observer UUIDs that identified that source at the root |
| Path | `MovementMode`, `PATH`, and the admitted path as an immutable position tuple |
| Jump | `DIRECT_ARC`, takeoff/landing positions and elevations, and the immutable disclosed arc tuple |
| Connector | source/destination positions and elevations, plus safe connector UUID/authored ID/kind/presentation key/revision; `CONNECTOR_TRANSFER` is derived only from the exact `TraverseConnectorEvent` root type and is not read from a nonexistent root trajectory field |

The pure `capture_movement_root_context()` accepts only the exact closed root runtime type, uncanceled `EFFECT` phase, and exact runtime shapes. The first EFFECT version in one lineage copies list/map inputs once into tuples/frozensets, seeds its own UUID/cursor as alias 1, and freezes whether `EventQueue.is_event_batch_active()` was true at that storage boundary as `EXPLICIT_ACTION_BATCH` or false as `IMMEDIATE_SINGLETON_SEQUENCE`. It retains no root costs, digest, child lists, queue evidence, callbacks, mutable observer map, or Event reference. A root with no modifying handler therefore resolves its Step parent through that first alias without any later EFFECT version.

EventQueue may store more than one legitimate EFFECT UUID for the same root lineage when a guarded handler returns an allowed status-only edit. Every later EFFECT version is compared against the first frozen context using an explicit whitelist:

- exact root runtime/event type, `EFFECT`, source UUID, lineage UUID;
- Path mode/trajectory/admitted path;
- Jump trajectory/anchors/elevations/disclosed arc;
- connector anchors/elevations/safe connector identity; connector-transfer classification remains derived from the exact root type;
- exact source identity-grant observer set.

UUID, timestamp, `modified`, status/outcome text, child/lineage lists, and other queue-owned linkage are deliberately not context equality fields. A matching later version adds only its UUID/cursor to `effect_uuid_aliases`; it never recopies the path/context or consumes another root-capacity slot. Re-delivery of the same UUID at the same source cursor is idempotent; the same UUID at another cursor or another UUID claiming an occupied cursor is a conflict. `MAX_ROOT_EFFECT_ALIASES_PER_LINEAGE = 16` is the total bound including the seeded first alias: alias 16 is accepted and alias 17 poisons the active capture boundary. A mechanical/grant mismatch has the same result. Later child publication or mutation of a queue-owned version cannot affect the frozen context.

Lifecycle:

1. extend the runtime's source-start attachment with one passive root lifecycle callback installed before commands alongside the existing Step/batch callbacks; on root EFFECT it creates/validates the lineage owner even when zero subjective partitions are open, while exact root COMPLETION/CANCEL only records that lineage's terminal cursor for later containing-delivery projection/eviction;
2. every Step resolves `step.parent_event` through the alias map to exactly one lineage context; a current `_BatchIndex` root slot may be compared for consistency but is never classification/privacy authority;
3. pass the same safely shared frozen context plus an immutable bounded alias view to each eligible partition as `CausalEventBatch.movement_root_contexts`; contexts/aliases never advance watermarks, create nodes, or re-enter source delivery;
4. on root COMPLETION/CANCEL, evict only after the containing delivery with that terminal cursor has been processed by every healthy partition; an individual journal projection failure follows that journal's existing resync/fault contract and cannot retain shared root state indefinitely;
5. clear all contexts on generation reset, runtime detach/failure, or source-history reset;
6. reject conflicting lineage/alias ownership and fail closed if a Step references a missing, ambiguous, or wrong-generation EFFECT alias;
7. retain at most `MAX_MOVEMENT_ROOT_CONTEXTS = 64`; alias/type/capacity failure enters the bounded reset-required path below rather than dropping/reusing context or inventing a root. If capacity poison closes, it clears the bounded context/alias store only after publishing the reset boundary; later Steps from abandoned incomplete singleton lineages fail closed rather than borrowing authority.

`CausalEventBatch.movement_root_contexts` defaults to empty. Its validation requires unique lineage owners and aliases, the current generation, `EFFECT`, and alias source cursors no later than the batch watermark; `_BatchIndex` creates only an alias-to-context lookup and never adds contexts to `slots`, completions, lineage traversal, ordering, node creation, or cursor accounting.

Hosted and standalone source startup must call the existing runtime `ensure_attached()` before any command can execute. The root-capture callback does not depend on an open player partition, so a partition bound between Steps resolves the already-captured context rather than re-querying EventQueue or joining with partial authority. In the healthy state, stop/generation rotation removes the callback and clears the store with the existing runtime attachments. The poisoned in-flight exception is the narrow deferred-detach rule below.

Because passive callback exceptions are isolated by EventQueue, the runtime owns one partition-independent capture latch:

```text
MovementRootCaptureHealth = HEALTHY | POISONED_AWAITING_CONTAINING_DELIVERY
```

`POISONED_AWAITING_CONTAINING_DELIVERY` is keyed only to facts the immediate passive callbacks can observe: the exact EventQueue generation and the first offending stored event cursor. For root capture/alias failure that cursor is the stored root EFFECT; for missing/wrong Step context it is the stored Step boundary that detected the failure. Installation is legal for either delivery topology already owned by EventQueue: if `is_event_batch_active()` is true, the containing delivery is the later depth-zero outer batch; otherwise `_store_event()` must synchronously follow its immediate event callback with the existing one-event batch callback, and that exact singleton containing the offending cursor is the containing delivery. No relevant root/Step storage route may suppress both batch deliveries. Internal diagnostics retain the first typed failure reason; requester/player contracts receive only the closed reset reason from §4.6. The root/Step callback that first detects a capture/alias/type/capacity/context conflict atomically:

1. installs that poison once without rethrowing into gameplay;
2. marks every root context/alias ineligible for lookup while poisoned, but does not guess an outer-batch identity or clear unrelated retained lineages before the containing delivery is known;
3. for an explicit outer batch, makes the detecting Step boundary (when applicable) plus every later nonterminal Step projection emit `RESET_REQUIRED/SOURCE_PRESENTATION_DISCONTINUITY`, exact subjective patches/watermarks, and zero cues; an immediate singleton has no later in-flight Step before its synchronous containing callback;
4. makes `bind()` return one requester-safe transient `source_batch_in_flight` only when it would open an absent partition while that poison remains open; already-open contexts remain readable and receive reset frames.

The reset-frame builder is a narrow sibling of normal frame projection: it consumes the same exact source slots and calls the same subjective world projector/diff owner, but never invokes the generic cue mapper and cannot copy an Event into presentation. One narrow `project_reset_encounter_terminal()` function reuses the existing authorized `EncounterEndEvent` encounter-cue projection fields to produce `EncounterTerminalPresentationFact` when required; it emits no other cue/fact and faults on zero/multiple/mismatched terminal authority. Each open partition appends the resulting reset frame to its ordinary journal/replay in source order. A journal that cannot validate/store that exact frame uses its pre-existing journal failure contract; the capture latch does not attempt to repair it.

Only `CanonicalSubjectiveReplicationRuntime._on_event_batch()` may close the capture poison. EventQueue invokes it either synchronously with the one-event singleton immediately after outside-batch storage, or after an outermost explicit batch scope has restored depth zero. This **delivery-scoped poison closure is not movement-lifecycle completeness evidence**. It runs even with zero partitions, computes the delivered sequence's exact stored cursor interval, requires the same generation and membership of the poisoned cursor in that interval, emits the one reset-required suffix still required by that containing delivery to each open healthy partition, and records the exact closed-through source cursor. It then evicts the offending lineage when exact, or clears the bounded store only for an ambiguous/capacity conflict; unrelated healthy contexts become eligible again. When that emitted final reset carries terminal authority, it is the callback's sole observation output; poison clearing and deferred detach occur afterward without appending an observation-only reset. Only after those operations does it return capture to `HEALTHY`. A noncontaining delivery cannot clear it, and no in-flight Step from the containing explicit batch can follow its depth-zero callback.

`stop()` or same-generation detach requested while poisoned sets one `detach_after_poison_closure` latch and returns without removing the root/Step/batch callbacks, clearing contexts, retiring open journals, or changing the capture health. `ensure_attached()` during that interval is idempotent and likewise must not remove/reorder those callbacks; it records the requested final attached state. After the exact containing `_on_event_batch()` has emitted/closed the required frames and returned health to `HEALTHY`, it applies the deferred final state once: detach removes callbacks/clears contexts, while attached leaves the normal callbacks installed. An EventQueue generation change or process loss is the separate terminal lifecycle boundary and may retire the entire old-generation runtime; it cannot preserve a same-generation 409 latch. There is no state in which the sole closure callback is absent while a live same-generation poison remains.

If zero partitions were open, no journal/reset frame exists: bind is transiently rejected until the explicit-batch or immediate-singleton containing callback closes poison, then succeeds from a current atomic bootstrap. Existing partitions remain ordinary healthy journals whose reset frames deterministically rebase presentation; no epoch rotation, journal retirement, replay abort, source reset, incident-token exchange, or new HTTP/proxy route occurs. `stop()`, `ensure_attached()`, and same-generation clearing obey the deferred-detach rule and cannot orphan or prematurely clear a poison awaiting either delivery topology. An actual EventQueue generation change retires all old contexts/latch state before any bootstrap in the new source generation.

The store is not a second reducer or movement accumulator. It retains no per-Step snapshot and does not delay a Step for completion. The normal per-Step frame continues to own its exact world/light patches and same-frame reactions.

The same `_on_event_batch()` callback performs a **separate lifecycle audit only when the delivered evidence proves a lifecycle boundary**:

- production Move/Swim/Fly/Jump/connector execution reaches the queue through the existing `BaseAction.apply()` owner, whose `EventQueue.batch_on_event_callbacks()` scope encloses `_apply_action()` and whose depth-zero exit is the actual action lifecycle closure; the encounter controller's broader batch only nests around it. For such an explicit outer delivery, each context whose first root alias belongs to that delivered interval and whose `delivery_scope` is `EXPLICIT_ACTION_BATCH` must have its exact root COMPLETION/CANCEL in that same delivered sequence;
- for an immediate singleton sequence, root EFFECT and Step-only singleton deliveries are never completeness boundaries. Their healthy context survives across the legal `root EFFECT -> Step(s) -> root COMPLETION/CANCEL` singleton sequence. A singleton containing the exact stored root COMPLETION/CANCEL is the terminal boundary for that lineage: project its suffix, then evict after every healthy partition has consumed it;
- poison closure for either topology remains governed only by membership of the offending cursor and never runs the healthy incomplete-root audit merely because a singleton callback fired.

At a proven explicit action closure, if any one of its distinct root lineages lacks matching COMPLETION/CANCEL—including precommit failures and supported postcommit `PositionPublicationError` branches—the runtime:

1. evicts that root context immediately, if present;
2. does not publish the incomplete final suffix as a normal subjective frame;
3. emits one `RESET_REQUIRED/SOURCE_PRESENTATION_DISCONTINUITY` final-suffix frame with exact subjective patches and zero cues to every open healthy partition;
4. relies on that frame's SDK presentation-reset branch to install current state, including any position/cost already committed before a publication failure; a zero-partition source merely resumes clean root capture after closure.

It does not keep an explicitly closed incomplete context until capacity pressure, invent a terminal root, or claim that the unprojected suffix settled. A healthy immediate-singleton lineage without terminal evidence is not falsely declared incomplete: it remains within the 64-context bound until its terminal singleton, generation/detach, or a later bounded capacity poison/rebase. Normal terminal deliveries project first and evict after their terminal suffix succeeds.

The resolved referenced context must have been captured from an accepted `EFFECT` of exactly one root type:

```python
MovementEvent | JumpEvent | TraverseConnectorEvent
```

Root COMPLETION is later settlement evidence and is not required to present an already committed Step. `parent_lineage`, nearest-ancestor, action name, combat-log text, endpoint geometry, and label heuristics are never family authority.

Validation and delivery occur in this order:

1. resolve the exact frozen root context by `Step.parent_event`;
2. validate every current-frame Step against that context before subjective filtering;
3. require controlled ownership or intersection with the context's frozen identified-observer set for root classification;
4. apply `_step_geometry_allowed()` independently to each current-frame Step;
5. for PATH, emit maximal contiguous authorized runs from that frame only;
6. for DIRECT_ARC/CONNECTOR_TRANSFER, require both endpoints for the single leg or omit it;
7. construct cues only from the authorized Step facts.

An unauthorized PATH edge is omitted without fault. It never prevents an earlier/later independently authorized edge from receiving its own frame-local cue, and runs are never stitched across the hidden edge. Cues contain no root-stable identifier, indices, totals, hidden endpoint, or hidden elevation. Ordinary observation/source watermark advancement may still reveal that some authorized source activity occurred between presented frames; this unit neither claims to hide that transport fact nor turns it into movement/path correlation. Jump/connector endpoint denial omits their one leg. Independently authorized same-frame reaction/action cues retain normal graph reparenting and never authorize omitted movement. Malformed unfiltered root/Step evidence raises `SubjectiveEventProjectionError`. Never default to Walk.

### 5.2 Exact family invariants

#### Path movement

- Root context is an accepted `MovementEvent` EFFECT with trajectory `PATH`.
- Every current Step is `PATH`, references the exact root-effect UUID as `parent_event`, and has the same source/lineage owner.
- The once-copied immutable admitted path is the authority for order; direct tuple indexing validates each later Step in `O(1)`.
- For root path `p`, Step `i` is exactly `from=p[i-1]`, `to=p[i]`, `path_index=i`, `total_path_length=len(p)`, and `disclosed_path=(from,to)`.
- Current-frame coalescing accepts only consecutive indices with exact position/elevation chaining; duplicates, index rewrites, or broken chains fault.
- An interrupted uncommitted Step, when delivered with its same-frame reaction child, remains one not-committed cue.
- Across frames, source and presentation cursors provide order; the player cue exposes no objective index/total and never waits for continuity.

#### Jump

- Root context is an accepted `JumpEvent` EFFECT with trajectory `DIRECT_ARC` and immutable takeoff/landing/elevation facts.
- The current Step is the one Jump leg; endpoint denial omits it without corruption.
- That Step has `trajectory=DIRECT_ARC`, `path_index=1`, the exact root-effect event as parent, and the same source.
- Step `disclosed_path`, source/destination, and endpoint elevations exactly match the accepted root Jump arc evidence.
- The one Jump Step may compare its disclosed arc once in `O(n)` to the once-captured arc; there is no per-cell or per-partition recopy.
- `Step.total_path_length` remains engine evidence describing the disclosed arc shape; it does not become presentation progress.
- The cue carries only takeoff and landing anchors and always has one presentation step.

#### Connector traversal

- Root context is an accepted `TraverseConnectorEvent` EFFECT with exact safe connector UUID/authored ID/kind/presentation key/revision.
- The current Step is the one connector leg with `trajectory=CONNECTOR_TRANSFER`, `path_index=1`, `total_path_length=2`, a two-position `disclosed_path`, and the exact root-effect event as parent. Endpoint denial omits it without fault.
- Step endpoints/elevations exactly match the accepted root source/requested endpoint facts.
- Root connector facts are copied from the accepted events; the mapper never re-queries `GridMap` or a connector registry.
- `TraverseConnectorEvent` is explicitly excluded from generic `ActionPresentationCue` creation, so one traversal creates one connector locomotion owner, not an Action cue plus a movement cue.

### 5.3 Closed mapping table

| Root | Engine fact | Cue family | Cue trajectory |
|---|---|---|---|
| `MovementEvent` | `MovementMode.WALKING` | Walk | Path |
| `MovementEvent` | `MovementMode.SWIMMING` | Swim | Path |
| `MovementEvent` | `MovementMode.FLYING` | Fly | Path |
| `MovementEvent` | `MovementMode.BURROWING` | Burrow | Path |
| `JumpEvent` | exact root type | Jump | Direct arc |
| `TraverseConnectorEvent` | exact root type | Connector | Connector transfer |

An unhandled enum member raises. It never defaults to Walk.

### 5.4 Authorized anchor construction

Anchors are built only after the current root/Step evidence passes validation and the local run passes delivery authorization:

```text
first.from_position + first.from_elevation_feet
each step.to_position + step.to_elevation_feet
```

Root requested/objective endpoints and combat-log text are never geometry authority. PATH runs are frame-local and never cross an unauthorized edge. A committed-arrival-plus-forced-displacement test proves that a truthful Step cue survives even when the final frame position differs.

## 6. SDK render and structural-edge identity

### 6.1 Canonical structural-edge key

Add:

```ts
declare const renderStructuralEdgeKeyBrand: unique symbol;
export type RenderStructuralEdgeKey = string & {
  readonly [renderStructuralEdgeKeyBrand]: true;
};

export function canonicalRenderStructuralEdgeKey(
  position: readonly [number, number],
  direction: FloorObjectDirection,
): RenderStructuralEdgeKey;
```

The function applies the existing `canonicalEdgeOwner()` normalization and serializes exactly:

```text
edge:<owned-x>,<owned-y>:<north|east>
```

`RenderStructuralEdge` gains:

```ts
readonly edge_key: RenderStructuralEdgeKey;
```

### 6.2 No key parsing

`projectStructuralEdges()` groups candidates as:

```ts
Map<RenderStructuralEdgeKey, {
  readonly owner: CanonicalEdgeOwner;
  readonly rows: Array<APIStructuralEdge>;
}>
```

It emits geometry from the retained canonical owner object. It never parses `edge_key` back into coordinates/direction. Keys are computed once per candidate and are identity only; spatial ordering remains `(y, x, owned direction)`.

Tests cover north/east/south/west reciprocal input, negative coordinates, conflict behavior, and door open/close persistence. No provider UUID is exposed.

### 6.3 SDK exports

Export render connectors, the structural validator/projector, structural-edge key type/function, and the new generated locomotion cue through the normal SDK public root. No broad compatibility root or Runtime V2 artifact is restored.

## 7. NeuroClient integration

### 7.1 Sole connector state path

In `/home/tommaso/Dev/NeuroClient/app`:

- alias SDK `RenderTraversalConnector` in `src/engine/types.ts`;
- add a read-only connector collection to `StoreState`;
- in `stateSync.applySubjectiveReplicaView()`, populate it only from `renderWorld.state.grid.connectors`;
- clear it with the same generation/reset teardown as tiles and structural edges;
- add it to render parity and static-board signatures;
- prohibit imports of raw `APITraversalConnector` in renderer/state code.

The sole accepted source path is:

```text
replicationJournal presentation replica
  -> projectSubjectiveRenderWorld
  -> ReplicatedRenderWorld.state.grid.connectors
  -> stateSync
  -> StoreState
  -> connector reconciler / renderer
```

### 7.2 Connector-only lifecycle owner

Add one UUID-keyed connector reconciler and `connectorPresentationSignature()` separate from tile, wall, object, light, and entity signatures.

- register/reveal creates one retained connector node;
- replacement or safe-field/style change updates only that connector;
- disable updates only inert styling;
- remove/hide/reset destroys the connector node and its cache row;
- connector-only change must not rebuild tiles, walls, objects, lights, or entities;
- hidden connectors have no node, cache row, picking region, shadow, ordering entry, or camera behavior.

The feature manifest must name this connector reconciler/signature and prove no overlap with other static-board owners.

Add one `connectorsLayer` to the existing viewport stack immediately after `objectsLayer` and before `worldLayer`. It is non-sortable and receives connectors in SDK-deterministic `(authored_id, uuid)` order. This fixed planar rule places connectors above floor/static objects and below entities/VFX without a second depth formula. Hidden/remove/reset paths remove the node from this exact layer.

### 7.3 Explicit planar presentation boundary

This unit does **not** partially implement terrain elevation in NeuroClient. The recovered renderer remains planar:

- connector endpoints use the existing `toIso(position)` projection;
- locomotion clips use the existing planar entity/clip transform from each anchor's `position`;
- connector/cue elevation remains exact typed presentation evidence in StoreState, intents, diagnostics, replay, and Studio evidence;
- no clip converts elevation into pixels, writes a second vertical transform, or claims that the board visually represents Z;
- static placement and animated terminal placement therefore continue to share the same existing planar coordinate owner and cannot snap between two coordinate systems.

Actual elevated rendering is a separate coherent frontend feature. Its later plan must move tiles, settled/transient entities, attached objects/structures/effects, overlays, picking, camera bounds, and animation terminals to one renderer-owned surface-geometry authority together. This unit does not create a partial `presentedAnchor()`, entity support-elevation field, vertical-face renderer, camera-fit registry, or second transform channel.

The neutral connector primitive is non-pickable (`eventMode="none"`), casts no shadow, and contributes no new camera-fit behavior. Hidden connectors remain absent from current-state nodes, caches, picking, ordering, shadows, inspector state, and current-state diagnostics. Historical replay/ledger/fault/Studio evidence that was authorized when captured remains immutable event-time evidence; hiding a connector later does not erase or reconstruct that history.

### 7.4 Neutral connector renderer

Render one kind-independent neutral planar primitive between the existing `toIso()` projections of its endpoint positions. Dimensions are bounded to one `TILE_H` stroke envelope around the segment. Disabled connectors remain visible in a deterministic inert style. Endpoint elevations remain present in the retained record and diagnostics but do not alter pixels in this unit.

The primitive must not branch on connector kind, authored ID, action name, or presentation key. Connector-specific sprites and safe-presentation catalog bindings are a follow-up.

### 7.5 Structural-edge consumers

Delete NeuroClient's local `structuralEdgeKey()` serializer. Use `edge.edge_key` for retained maps, parity records, depth tie-breakers, and lifecycle updates. Position/direction remain geometry. No local branded-key clone or reciprocal normalizer remains.

### 7.6 One locomotion presentation transaction

`subjectivePresentationMapper.ts` maps the generated cue into a closed `LocomotionPresentationIntent` union:

```text
PathLocomotionIntent      -> Walk / Swim / Fly / Burrow
JumpLocomotionIntent      -> Jump
ConnectorLocomotionIntent -> Connector
```

Every variant retains its exact family, trajectory, anchors, cue presentation ID, outcome, and source frame/generation identity. Connector intent additionally retains the generated safe connector identity. There is no public root-stable movement sequence, objective root progress/total field, or fragment-wait protocol.

One `LocomotionSessionExecutor`, owned by the existing `VisualTransaction`/presentation runtime host, executes all variants. It may dispatch to stateless planar path, arc, or transfer interpolation primitives. It owns only:

- one active locomotion session per `(source stream, perspective generation, entity UUID)`;
- per-entity/source/generation locomotion-session acceptance;
- cancellation and teardown;
- its typed locomotion terminal result;
- stale terminal isolation.

This unit adds no new authored locomotion media schema. The closed family-to-existing-profile table is deliberate:

| Cue family | Planar executor/profile in this unit |
|---|---|
| Walk | existing Walk path clip and Walk-authored body/timing/media fields |
| Swim | same existing Walk planar translation/body profile, while retaining `SWIM` in intent/diagnostics |
| Fly | same existing Walk planar translation/body profile, while retaining `FLY` in intent/diagnostics |
| Burrow | same existing Walk planar translation/body profile, while retaining `BURROW` in intent/diagnostics |
| Jump | existing Jump arc clip and Jump-authored body/timing/media fields, invoked once for the two authorized anchors |
| Connector | existing Walk planar translation/body profile over exactly two anchors, while retaining `CONNECTOR` and its safe identity in intent/diagnostics |

The switch is exhaustive on the generated enum, never on labels, connector kinds, authored IDs, or presentation keys. Distinct Swim/Fly/Burrow/connector media is a later safe-presentation catalog addition; the absence of such media cannot collapse their typed cue/intent identity back to Walk.

`ClipQueue` remains the sole whole-`VisualTransaction` executor/terminal owner and aggregates locomotion, reactions, damage, conditions, and every other intent. The frame coordinator awaits only that aggregate result; it never treats a locomotion terminal as whole-frame success.

Jump is one presentation leg, so the old `deferredJumpSequence`, `resetBufferedJumpPresentation()`, and JumpClip-owned frame buffer are deleted. `JumpClip` becomes a stateless planar primitive invoked by the central session. Connector transfer adds no second queue or coordinator. Every intent retains elevation unchanged even though clips intentionally use only its planar position in this unit.

The mapper no longer uses raw `null` as state-only authority. Live and replay consumers share the pure cue-to-intent logic but use disjoint dependency-neutral consumer identities:

```ts
type PresentationConsumerIdentity =
  | {
      readonly kind: "live";
      readonly attachmentIdentity: string;
      readonly attachmentGeneration: string;
    }
  | {
      readonly kind: "replay";
      readonly replaySessionId: string;
      readonly replayGeneration: number;
    };

interface PresentationFrameIdentity {
  readonly consumer: PresentationConsumerIdentity;
  readonly sourceStreamId: string;
  readonly perspectiveGeneration: string;
  readonly perspectiveEpochId: string;
  readonly observationCursor: number;
  readonly frameDigest: string;
}
```

The source/perspective fields identify the accepted live or archived frame; they do not turn a replay into a current attachment. Normal and reset planning have deliberately disjoint constructors:

- `planLivePresentationFrame(preview, liveIdentity)` and `planReplayPresentationFrame(preview, replayIdentity)` accept only `SubjectivePresentationFramePreview`, therefore only a `NORMAL` exact head. They return only `state_only | visual_transaction` and perform the exhaustive cue disposition mapping below.
- `planLiveResetPresentationHead(resetHead, liveIdentity)` and `planReplayResetPresentationHead(resetHead, replayIdentity)` accept only `ExactResetPresentationHead`, therefore only a `RESET_REQUIRED` exact head. They validate the closed reset reason, empty cue tuple, optional terminal fact, consumer identity, and exact token/head binding and return only `reset_required`. They never invoke candidate preview reduction, cue mapping, state-only classification, entry-anchor derivation, or `VisualTransaction` compilation.
- live entrypoints require `consumer.kind === "live"` and the exact current attachment. Replay entrypoints require `consumer.kind === "replay"`, never accept an attachment capability, and bind every plan/intent/session terminal to the isolated replay session/generation.

Their outputs remain one closed consumer result after those disjoint entry boundaries:

```ts
type ResetSubjectiveFramePresentationPlan = {
      readonly kind: "reset_required";
      readonly frameIdentity: PresentationFrameIdentity;
      readonly reason: PresentationResetReason;
      readonly dispositions: readonly [];
      readonly entryAnchorByEntity: ReadonlyMap<string, never>;
    };

type NormalSubjectiveFramePresentationPlan =
  | {
      readonly kind: "state_only";
      readonly frameIdentity: PresentationFrameIdentity;
      readonly dispositions: ReadonlyArray<CuePresentationDisposition>;
      readonly entryAnchorByEntity: ReadonlyMap<string, LocomotionAnchor>;
    }
  | {
      readonly kind: "visual_transaction";
      readonly frameIdentity: PresentationFrameIdentity;
      readonly dispositions: ReadonlyArray<CuePresentationDisposition>;
      readonly entryAnchorByEntity: ReadonlyMap<string, LocomotionAnchor>;
      readonly transaction: VisualTransaction;
    };

type SubjectiveFramePresentationPlan =
  | ResetSubjectiveFramePresentationPlan
  | NormalSubjectiveFramePresentationPlan;

type CuePresentationDisposition =
  | {
      readonly kind: "direct_intent";
      readonly presentationId: string;
      readonly intentEvidenceIds: readonly string[];
    }
  | {
      readonly kind: "folded_into_parent";
      readonly presentationId: string;
      readonly ownerPresentationId: string;
      readonly intentEvidenceIds: readonly string[];
    }
  | {
      readonly kind: "state_only";
      readonly presentationId: string;
      readonly reason: ClosedStateOnlyReason;
    };

type ClosedStateOnlyReason =
  | "door_reducer_state"
  | "light_reducer_state"
  | "spatial_effect_reducer_state"
  | "internal_condition"
  | "unequipped_loadout_replacement"
  | "unchanged_alive_state"
  | "encounter_reducer_transition"
  | "effectless_lifecycle_cause"
  | "authored_action_empty_envelope"
  | "authored_action_state_only_children";
```

The top-level frame planner returns `reset_required` directly from the SDK-validated frame discriminator and verifies its empty cue window; it does not invoke `mapCue()`, infer reset from missing intents, or accept a local incident as server evidence. Normal frames are created from the existing exact mapping-coverage evidence, not inferred from `transaction === null`. Human-readable reason text remains diagnostic only and cannot authorize commit. `ClosedStateOnlyReason` has this exhaustive eligibility table:

| Reason | Exact eligible cue/predicate |
|---|---|
| `door_reducer_state` | `door`, always; the installed door patch owns display |
| `light_reducer_state` | `light`, always; the installed effective-light row owns display |
| `spatial_effect_reducer_state` | `spatial_effect`, always; installed tile/effect replacement owns display |
| `internal_condition` | `condition` with `condition_category === "internal"` |
| `unequipped_loadout_replacement` | `equipment` with `visual_loadout.active_weapon_set === "none"` |
| `unchanged_alive_state` | `life_state` with `previous === "alive" && current === "alive"` |
| `encounter_reducer_transition` | `encounter` with transition exactly `start | round_start | turn_end | round_end` |
| `effectless_lifecycle_cause` | `lifecycle_cause` with null death-save outcome and an empty child-ID list |
| `authored_action_empty_envelope` | `action` whose resolved authenticated recipe has actor disabled, null action feedback, and zero declared effect IDs |
| `authored_action_state_only_children` | the same disabled/no-feedback `action`; its nonempty declared effect-ID set equals its direct graph-child ID set exactly, and every such child already has one independently valid closed state-only disposition |

Movement, forced movement, Shove, Counterspell, item action, attack, spell, damage, heal, any player-facing condition/life/encounter transition, and any action failing the exact recipe predicates have no state-only reason. Adding a new cue kind or reason is a compile-time exhaustive-table change, never a string fallback.

Each compiled `ClipIntent` receives one mapper-local immutable evidence ID during the single compile pass. A `direct_intent` disposition has a nonempty unique set of IDs owned by that cue. A `folded_into_parent` disposition is valid only when:

1. `ownerPresentationId` is the nearest declared ancestor in the already-validated acyclic `parent_presentation_id` graph that owns a direct intent;
2. its nonempty `intentEvidenceIds` exactly equal the IDs attributed to the child by `mapCue()` and are a subset of the recursively flattened intent IDs owned by that ancestor's direct transaction group;
3. the same intent object/evidence IDs—not merely equal intent type strings—prove the fold.

A sibling, unrelated root, wrong ancestor, empty child mapping, or owner lacking the child's exact intent evidence is a coverage failure. A parent-owned visual may deliberately attribute its exact intent evidence to a child during compilation, but a missing child mapping cannot be inferred afterward.

Before either normal plan branch is returned, the mapper proves that the disposition IDs equal the frame's presentation IDs exactly: no duplicate, missing, unknown, or multiply-owned cue; each folded child satisfies the exact graph/evidence predicate; each state-only cue satisfies the closed table; every visually relevant cue owns or folds into an intent. A state-only result requires an empty entry-anchor map. A normal frame with zero cues may return `state_only` with empty dispositions/anchors. Any coverage failure throws a typed mapping failure before enqueue/commit.

The plan also carries a family-neutral `entryAnchorByEntity` map derived only from locomotion intents. During staging, if an entity is absent from the currently presented scene but appears in the candidate render world with an authorized locomotion cue, the staging owner creates it at that cue's first anchor before the display object can render. An already-present entity keeps its current presented pose. The map may neither synthesize a hidden edge nor use the candidate final position as an entry pose; duplicate/conflicting entry anchors fail mapping. Transaction success lets the committed replica settle the final pose, while any precommit failure destroys the transient node. This is planar staging ownership, not a second reducer or elevation transform.

`eventIngestion.ts` is the sole `PresentationFrameCoordinator` for every accepted live frame. One `PresentationHeadDrain` serializes access to it. The drain owns exactly one head coordinator at a time and starts another only after the prior head was committed/reset and state-synced, or after that prior head's local recovery replaced the journal identity. Merely accepting, paging, or receiving a later frame does not start another coordinator transaction.

As soon as the accepted current-journal backlog contains any `RESET_REQUIRED` frame, the drain acquires one unconditional `PendingResetSafetyToken` for that journal identity, disables gameplay mutation, and marks the presentation backlog resolving. The generic reset has no offer/basis relevance metadata, so no selector may waive or narrow this token. It remains held while **any** reset frame is pending and is released only after the last such frame is consumed and state-synced or the whole journal identity is retired/replaced. It does **not** cancel the earlier head, reveal/reset pixels early, or call the SDK reset method out of order. Canonical/current-state arrival may disable immediately, but cannot enable a command or advance display.

For a `NORMAL` head, including state-only and non-locomotion frames, the coordinator:

1. accept one SDK-validated frame in cursor order;
2. call the SDK journal's `previewPresentationFrame(head.watermarks.observation_cursor)`, project the immutable candidate presentation through the SDK render projector, map it with `planLivePresentationFrame(preview, liveIdentity)`, and verify its exact preview/head/consumer identity plus exhaustive dispositions; neither event ingestion nor stateSync reduces patches or reads the authoritative-ahead replica;
3. stage the candidate world with the plan's entry anchors without advancing the journal, retaining one teardown token for every transient node/cache/pose;
4. treat a verified `state_only` plan as the immediate successful no-animation barrier, or enqueue/await the visual plan's aggregate `ClipQueue` result;
5. recheck source stream, perspective generation, attachment identity, observation cursor, and that the staged frame is still the queue head;
6. call `replicationJournal.commitPresentationFrame(preview.token)` at most once;
7. verify whether that exact cursor/frame committed;
8. invoke stateSync from the committed presentation replica;
9. release the staging token only after stateSync succeeds.

For a `RESET_REQUIRED` head it instead:

1. calls `inspectResetPresentationHead(head.watermarks.observation_cursor)`, passes that exact evidence to `planLiveResetPresentationHead(resetHead, liveIdentity)`, and verifies its token/frame/source/generation/attachment/cursor and closed reset plan; it never calls the normal preview or normal mapper;
2. keeps presentation command safety disabled and proves there is no earlier/current normal coordinator, staging token, causal `ClipQueue` transaction, or commit owner;
3. cancels only decorative/transient work and stale timers that are not required to retire another journal head; because the drain is exclusive, no earlier causal owner can be torn down here;
4. rechecks that this reset frame remains the exact queue head;
5. calls `replicationJournal.resetPresentationFrame(resetHead.token)` at most once—never `commitPresentationFrame()` and never the cue mapper/ClipQueue;
6. reconciles a thrown call from the exact journal cursor/head just like the normal commit boundary, without a blind second call;
7. if `encounter_terminal` is present, stages its exact terminal record before reset installation; state-syncs the atomically reset presentation replica, clears stale scene/cache state through normal reset ownership, records typed `ServerPresentationResetEvidence`, crosses the reset itself as that terminal fact's visual barrier, and commits the terminal lock/result only after successful reset stateSync;
8. retains the unconditional reset safety token if another reset remains and otherwise permits the current-owner affordance lease process below to start. Reset success itself never enables interaction.

A reset head never enters `ClipQueue`, consumes causal high-water capacity, or owns a clip watchdog. A high-water rejection can affect only the current normal head; that head's one local recovery replaces the old journal and retires a reset waiting behind it. A pending reset can never cancel the active owner needed to remove an earlier head, and it can never invoke a second local-recovery path after that earlier head failed. Every accepted head therefore has exactly one terminal owner: normal commit plus stateSync, reset plus stateSync, or old-journal retirement by the failing head's one recovery transaction.

Do not introduce the conceptual `ActorOffer`, `CommandBasis`, or `InteractionSafetyWatermark` contracts in this unit: they are not executable owners in the current repositories. Use the current journal, controller, and `APIAvailableActions` boundaries to create one local `PresentedAffordanceLease` only after catch-up:

```ts
interface PresentedAffordanceLease {
  readonly journalIdentity: string;
  readonly sourceStreamId: string;
  readonly generationId: string;
  readonly perspectiveEpochId: string;
  readonly sourceEventCursor: number;
  readonly observationCursor: number;
  readonly presentationCursor: number;
  readonly controlledEntityUuid: string;
  readonly actions: APIAvailableActions;
}

type CapturedPresentationFence = Pick<
  PlayerReplicationWatermarks,
  "source_event_cursor" | "observation_cursor" | "presentation_cursor"
>;
```

The lease is a frontend presentation-safety cache over one authenticated fetch. `journalIdentity` is the drain-owned local journal-incarnation token, replaced whenever bootstrap/recovery installs another journal even if server cursors happen to repeat; it is not serialized or sent to the backend. The lease neither changes `APIAvailableActions` nor adds a backend offer/basis protocol.

One `PresentedAffordanceLeaseOwner`, mounted by the authenticated live `eventStream.ts` owner with injected SDK client and read-only drain state, owns this closed state machine:

```text
DISABLED
  -> WAITING_FOR_IDLE
  -> ACQUIRING_ROWS(attempt_id, idle_epoch, frozen_snapshot, AbortController)
  -> LEASED
  -> DISABLED

ACQUIRING_ROWS + advanced capture
  -> CATCHING_UP_FIXED_FENCE(target, rearm_after_idle=true)
  -> ARMED_FOR_POST_CATCHUP_IDLE
  -> ACQUIRING_ROWS(new_attempt_id, new_idle_epoch, ...)

ACQUIRING_ROWS + unrelated accepted frame/head start
  -> ARMED_FOR_POST_INVALIDATION_IDLE
  -> ACQUIRING_ROWS(new_attempt_id, new_idle_epoch, ...)

ACQUIRING_ROWS fetch failure -> WAITING_FOR_NEXT_TRIGGER
ACQUIRING_ROWS regressive/incomparable capture -> FENCE_FAULTED_WAITING_STREAM_RECOVERY
```

There is at most one row acquisition/abort controller and one fixed catch-up target per live attachment. `idle_epoch` increments only on a real transition from non-idle to idle/backlog-empty, and an automatic row acquisition may start at most once per idle epoch. The other exact triggers are initial authenticated mount, controlled-entity change, transport reconnect, and an explicit user refresh/open-actions request; concurrent triggers coalesce, and explicit requests while one acquisition is active do not start another. There is no timer, polling loop, background retry, or same-idle hot loop. A transport/fetch failure with no later idle edge remains safely disabled in `WAITING_FOR_NEXT_TRIGGER` until reconnect or explicit user demand. `FENCE_FAULTED_WAITING_STREAM_RECOVERY` admits no user/acquisition retry on the same journal; it records the generated page-watermark validation failure once and delegates to the existing authenticated stream/journal recovery owner. Only replacement journal identity/reconnect can leave it.

While `ACQUIRING_ROWS`, an unrelated accepted observation frame/head start discards rows and transitions once to `ARMED_FOR_POST_INVALIDATION_IDLE`; after the ordinary drain returns idle, that state consumes its one trigger. It does not leave a half-live lease or compete with the page-owned catch-up path. Once the first page proves an advanced fixed fence, the row acquisition ends before those frames are fed to the follower and the owner enters `CATCHING_UP_FIXED_FENCE`. Frames at or below that fixed target are expected catch-up input and therefore do not self-cancel the pager. Frames beyond it never extend the target or revive stale rows; they remain ordinary follower input and keep the eventual idle condition false. Reaching the fixed target moves to `ARMED_FOR_POST_CATCHUP_IDLE`; when the sole drain is idle/backlog-empty, that state consumes its queued trigger against the current real `idle_epoch` and begins exactly one fresh acquisition even if the ordinary idle notification occurred before the target-reached callback. Catch-up necessarily made the drain non-idle before that current epoch, so this does not manufacture an idle transition or reuse the attempt's prior epoch. Attachment/controller/generation/journal change, reset/recovery replacement, terminal lock, or unmount aborts either phase and fences every late result by identity/`attempt_id`; the replacement journal's own mount/idle edge is the only automatic retrigger.

An attempt executes exactly:

1. require the live head drain idle, SDK presentation backlog empty, and no preview, reset-head token, staging token, causal transaction, reset reconciliation, local recovery, terminal lock, or `PendingResetSafetyToken`;
2. snapshot exact journal incarnation, source stream, generation, perspective epoch, observation/source/presentation cursors, controlled entity UUID, and `idle_epoch`;
3. fetch authenticated `APIAvailableActions` for that entity, then issue the first ordinary subjective observation-page request from the snapshotted observation cursor. Project that response's generated `captured_watermarks` to the exact `CapturedPresentationFence`; this is the fixed post-fetch server observation fence for the attempt—not an inferred SSE time or local wall clock. Combat-log-only advancement is deliberately outside this presentation/command lease and cannot force a redundant actions fetch;
4. compare the captured presentation fence componentwise with the frozen `(source, observation, presentation)` cursor triple. Exact equality is the only lease candidate. Componentwise dominance with at least one strict advance is the only catch-up case. If any captured component is lower—including mixed higher/lower incomparability—discard rows, abort the attempt, enter `FENCE_FAULTED_WAITING_STREAM_RECOVERY`, keep actions disabled/visible, and pass the typed page invariant failure to the existing stream recovery owner once; it cannot retry or choose a “largest” cursor;
5. for the strictly dominating case, discard the fetched rows, end `ACQUIRING_ROWS`, and atomically install `CATCHING_UP_FIXED_FENCE(target, rearm_after_idle=true)` **before** feeding the first returned frame to the follower. The existing bounded pager may continue from `through_watermarks` only until the SDK follower reaches that fixed source/observation/presentation target; later response capture values do not extend it. Every returned frame enters the sole SDK follower and ordinary serialized head drain. Once target and full drain idle are both true, the one armed trigger starts a new acquisition; stale rows are never reused;
6. only for exact equality, and only when the owner rechecks the same attachment, controller, journal identity, cursors, idle epoch, idle drain, empty backlog, and no safety token, may it install `PresentedAffordanceLease`. A stale/aborted response is dropped without UI or journal mutation;
7. accepting any later frame, changing controller/entity/attachment/generation, acquiring a pending-reset token, starting local recovery, or beginning a new drain head synchronously invalidates the lease and disables mutation before mapping/staging that frame;
8. command preparation/submission requires the still-current lease, exact displayed row/target, unchanged journal identity/cursors, idle drain, empty backlog, and no safety token. Picking uses only presented geometry. The backend's current command endpoint remains the final mechanics/authority validator.

`PresentedAffordanceLease` authorizes only row enablement, target preparation, and command submission. It is **not** an action-bar visibility owner. The last presentation-clocked rows may remain mounted, visible, focusable for inspection, and explicitly disabled while no lease exists—during an active normal transaction, enemy activity, pending reset, catch-up, or transient fetch failure. They clear or rebase only through the existing presented SELF/current-turn/terminal workflow after its frame commits or resets, never merely because canonical-ahead state or lease invalidation arrived. A successful fresh lease may replace those visible rows with its exact fetched rows; losing the lease disables but does not hide them. Consecutive reset heads hold the unconditional token across the gap between them, so no visible stale row becomes actionable between drain heads.

`ServerPresentationResetEvidence` is not a `PresentationIncident`: it records only the requester-safe reset reason and frame identity. A failure while applying/staging/state-syncing this reset is a new local `PresentationIncident` and enters the existing authenticated local-journal bootstrap/resync path. No client-local incident can be sent back as a server recovery token because no such endpoint or token exists.

The existing `EncounterTerminalRecord.lineageUuid` is not a lineage UUID: current code fills it from `EncounterPresentationCue.presentation_id`. Remove that overloaded field rather than feeding it an event UUID or fabricated cue. The one encounter-result owner uses this internal closed identity:

```ts
type EncounterTerminalAuthorityIdentity =
  | {
      readonly kind: "presentation_cue";
      readonly presentationId: string;
    }
  | {
      readonly kind: "reset_terminal_fact";
      readonly terminalAuthorityId: string;
    };

interface EncounterTerminalRecord {
  readonly encounterUuid: string;
  readonly eventUuid: string;
  readonly authorityIdentity: EncounterTerminalAuthorityIdentity;
  readonly eventCursor: number;
  readonly reason: string | null;
  readonly combatantUuids: readonly string[];
}
```

`acceptSubjectiveEncounterEnd()` and `commitSubjectiveEncounterEnd()` accept the ordinary terminal cue or generated frame-level fact through typed overloads and stage/commit the same record owner. The cue branch copies only `cue.presentation_id`; the reset branch copies only validated `fact.terminal_authority_id`. The normal branch requires its aggregate visual barrier; the reset branch requires the exact reset token installation plus stateSync barrier. No client path converts source event UUID, labels, coordinates, graph position, or terminal state into either identity.

Duplicate/conflict rules are exact: byte-equivalent re-delivery of the same branch, source event, authority ID, cursor, reason, and combatant set is idempotent; the same source event under the other authority branch, a changed authority ID/payload, or any different terminal event after one accepted terminal is a conflict. A normal cue and reset fact for the same terminal event are therefore conflicting duplicate authorities, never two ways to “repair” one another. A preinstall reset failure clears only the staged terminal record for that exact reset authority; a proven installed reset with later stateSync failure retains terminal journal truth but leaves input/result finalization disabled until local scene recovery. An ended reducer patch cannot open the result shell without the matching branch/barrier identity.

The coordinator has one explicit failure matrix for both state-only and visual plans:

| Failure point | Required result |
|---|---|
| candidate derivation, mapping/coverage, staging, enqueue rejection/error, barrier failure/cancel/deadline, or precommit identity recheck | idempotently tear down staged/transient state, make zero commit attempts after the failure, record one incident, disable presentation command safety, and request authenticated recovery once |
| `commitPresentationFrame()` throws | never retry blindly; read the SDK journal's exact presentation cursor/frame identity. If the previewed head and token remain current at the prior cursor, use the precommit branch. If the exact previewed frame is installed, retain that committed fact and use the postcommit branch. Any other/unknown state is unsafe and requests recovery without a second commit |
| stateSync or critical scene reconciliation after a proven commit | retain the committed journal fact, tear down/mark the scene unsafe, record one postcommit incident, disable safety, request recovery once, and never commit the frame again |
| diagnostics/evidence recording after successful stateSync | failure-isolated best-effort evidence only; it cannot roll back, duplicate, or invalidate an otherwise presented frame |

Each accepted head has one idempotent local-incident/recovery latch, so compound frontend failures cannot request multiple resets. Local recovery bootstrap replaces the scene/presentation replica from the committed or uncommitted journal truth; it never guesses based on pixels. A successfully applied server reset directive is already the presentation rebase transaction and does not request another bootstrap. A reset pending behind a failed normal head is retired by that normal head's journal replacement and never gets its own recovery latch.

`VisualTransaction`, `ClipQueue`, `LocomotionSessionExecutor`, clips, renderer, and stateSync never import or write the journal. They return typed terminal results only. `eventStream.ts` injects one dependency-neutral `requestPresentationRecovery(incident)` callback into the frame coordinator for **local** presentation failures; event ingestion never reverse-imports event stream. A failed, canceled, or stale local terminal causes no normal commit: the coordinator records one local incident, cancels remaining work for that generation, invalidates every `PresentedAffordanceLease`, marks presentation command safety false, and invokes that callback once. The stream owner performs the existing authenticated local-journal resync/bootstrap; interaction can become enabled afterward only by creating a fresh post-idle lease through the exact current-owner sequence above, never from bootstrap or authoritative arrival alone. A server `RESET_REQUIRED` frame follows the separate SDK reset branch above and never calls that callback merely because the directive exists. No locomotion family has a different backlog or commit rule.

### 7.7 Bounded queue liveness

Do not claim to predict clip duration from intent data. Actual wall time also depends on runtime-loaded animation frame counts, live rendered projectile endpoints, asset preparation, and clip-owned children scheduled at frame offsets. This unit adds no duplicate timing model and no backend timing contract.

`ClipQueue` instead owns one conservative monotonic wall-clock bound for the one active live causal transaction:

- `MAX_CAUSAL_ACTIVE_EXECUTION_MS = 60_000`, starting when execution becomes active and covering asset preparation/loading, all sequential/parallel root intents, live-distance interpolation, frame-offset children, recursively dispatched children, and terminal resolution;
- it uses the browser monotonic clock plus an owned watchdog timer; background throttling may delay detection but can never turn an expired/retired generation into success;
- `MAX_PENDING_CAUSAL_TRANSACTIONS = 0`: the serialized head drain does not enqueue the next journal frame while one is active. An enqueue attempted while a causal transaction is already active is a synchronous high-water rejection and evidence of an ownership/failure path, not a supported backlog;
- accepted later frames remain bounded by the SDK journal's existing `DEFAULT_PRESENTATION_QUEUE_LIMIT = 16_384` fail-closed retention/backpressure and never allocate clip promises, timers, staging tokens, or causal queue entries before becoming head; this unit does not add a second backlog or raise that limit;
- decorative work does not consume the causal transaction slot and is canceled by the same generation teardown; this unit does not claim channel preemption or isolation, so any shared body/VFX contention remains bounded by the active transaction's wall watchdog.

These are intentionally conservative failure bounds, not authored duration estimates. A normal real product transaction must finish inside the active bound; otherwise recovery is safer than an indefinitely blocked command/frame boundary.

`enqueueTransaction()` returns a closed accepted/rejected result. Busy/high-water rejection is synchronous, creates no lineage waiter, and enters the same coordinator failure branch. An accepted causal transaction resolves its lineage exactly once as completed/failed/canceled; its deadline is owned and cleared by `ClipQueue`.

Deadline or high-water failure produces one typed failed queue outcome. `ClipQueue` aborts/releases the matching generation/session and returns that outcome; the frame coordinator alone records exactly one `PresentationIncident`, sets the disable-only presentation command-safety flag, commits no frame, and requests authenticated recovery through the injected callback. It never invents a terminal pose, snaps state, drops a frame as successful, or advances a cursor. Once a reset has lawfully reached the exclusive head, there is no earlier causal transaction left; it clears stale watchdog/decorative state without canceling an owner needed for head retirement. A late promise completion is observed but generation-fenced and cannot commit or mutate the new scene.

### 7.8 Interaction and accessibility

The connector scene primitive is deliberately noninteractive. Gameplay interaction remains in the existing action bar:

- connector traversal is discovered through generated `connector_traversal` action facts;
- mouse and keyboard activation submit that exact typed option through the existing command boundary;
- no board click, label parsing, connector kind, or presentation key constructs a command;
- the action button retains normal focus order and an accessible name from the generated action label;
- disabled/non-actionable connector render state never enables an action.

The existing tile/selection inspector gains a read-only connector status row when an authorized connector endpoint is selected. Its accessible text derives mechanically from generated `kind` plus enabled/disabled state; it is not a command surface and does not branch on content names.

### 7.9 Local presentation persistence cut

The complete durable inventory containing cue/transaction/frame shapes is exactly:

| Storage | Key | Owner |
|---|---|---|
| `sessionStorage` | `neuroclient.clientPresentationLedger.v1` | presentation ledger |
| `sessionStorage` | `neuroclient.clientPresentationFrameArchive.v2` | raw presentation-frame archive |
| `localStorage` | `neuroclient.presentationFaults.v2` | presentation fault/intent/transaction evidence |

Do not invent a persistent render-cache namespace. Connector and renderer caches remain in memory and clear through ordinary reset/teardown. The run-ID key contains no cue-shaped data and is not reclassified as one.

Add one `PresentationPersistenceCutCoordinator` in the engine/startup layer. Remove eager module-evaluation parsing from `presentationLedger.ts` and `presentationDiagnostics.ts`; those modules expose explicit initialization functions and read nothing until the coordinator calls them.

Each of the three durable values becomes a small envelope whose top level contains its local schema plus the generated player-replication contract version/hash before any nested entries. At application startup, before scene/presentation initialization and before stream attachment:

1. parse only that top-level envelope identity;
2. compare it to the current generated identity;
3. on mismatch or legacy array shape, delete that exact incompatible key without parsing nested frames, cues, intents, transactions, or faults;
4. aggregate results across all three keys into one cutover decision;
5. initialize the ledger/archive/fault modules only after all envelope checks complete;
6. cancel presentation work and clear in-memory presentation/connector caches when the aggregate decision requires recovery;
7. return one `requiresAuthenticatedBootstrap` flag to the stream-attachment owner; no startup module performs a network call before authentication;
8. after authenticated attachment, invoke exactly one normal bootstrap/reset for that flag;
9. do not delete preferences, credentials, unrelated Studio documents, or immutable server history.

A seeded regression populates all three exact V1-shaped keys plus unrelated durable keys and proves scoped deletion, no V1 diagnostic interpretation, clean authenticated rebootstrap, and no stale animation/connector or unauthenticated fetch.

## 8. Version and replay cut

The cue schema is incompatible. Perform one hard cut:

- `PLAYER_REPLICATION_CONTRACT_VERSION`: 1 -> 2;
- `PLAYER_REPLAY_CONTRACT_VERSION`: 1 -> 2;
- regenerate player replication hashes, subjective replay hashes, TypeScript declarations/descriptors, contract manifest, build identity, and fixtures;
- do not bump objective replay or timeline solely for SDK-only render types or the subjective cue;
- do not add a V1 cue decoder, compatibility field, or dual mapper.

### 8.1 Decode ordering

SDK replay import first reads only the minimal top-level envelope identity needed to inspect replay version/hash. Unknown or V1 identity is rejected with the established typed contract-mismatch result **before** attempting to decode the nested V2 player-replication schema. This is an identity preflight, not a V1 decoder.

Backend game-history reads preserve immutable V1 bytes and return the existing `subjective_replay_metadata_invalid` product code rather than crashing or misclassifying the archive. Audit worker spool, terminal archive, retained-frame metadata, and fixture schema IDs so no V1 ID is emitted under V2 hashes.

Current V2 capture, authenticated import, seek, and SDK replay validation must use the new cue contract.

### 8.2 Isolated replay/Studio reset consumption

Retention and decoding are not presentation. Add one `ReplayPresentationHeadDrain` beside the live drain, parameterized by an isolated SDK replay journal, `consumer.kind === "replay"` identity, and isolated presentation scene/store. It shares the closed `presentation_delivery` discriminator and the SDK journal's exact-head operations, but it has no live attachment identity and no import or injected edge to live `eventStream.ts`, credentials, command submission, membership/attachment control, live recovery callbacks, or the live StoreState. A live consumer identity is rejected before replay mapping/staging, and a replay identity is rejected by the live drain.

The replay drain processes retained frames strictly in observation order:

- a `NORMAL` head calls the isolated SDK journal's exact `previewPresentationFrame()`, uses `planReplayPresentationFrame(preview, replayIdentity)`, stages only the immutable preview candidate, and commits only its token after the replay-owned visual/state-only barrier;
- a `RESET_REQUIRED` head disables replay playback/seek mutation for that isolated drain, cancels only replay-owned decorative/clip/staging/timer/transient work, calls `inspectResetPresentationHead()` and `planReplayResetPresentationHead()` for the exact replay consumer, invokes `resetPresentationFrame(resetHead.token)` on the isolated SDK journal exactly once, and state-syncs the isolated replay presentation replica; it never calls normal preview/cue mapping;
- when reset carries `encounter_terminal`, the replay drain stages that fact, treats successful reset plus replay stateSync as its exact terminal presentation barrier, installs the isolated terminal result/lock, and marks the replay segment ended; it never needs an empty cue to impersonate terminal evidence;
- it never invokes live authenticated recovery, fetches a bootstrap, rotates a credential/attachment, changes live interaction safety, or translates the reset into a client/server incident;
- it records only generic requester-safe `ServerPresentationResetEvidence` in replay diagnostics. A local replay application failure produces an isolated `ReplayPresentationIncident`, stops that replay drain, and leaves live gameplay untouched;
- a duplicate retained reset frame is removed by the SDK journal's existing frame-identity/observation duplicate handling and cannot execute reset twice;
- stale clip completions are fenced by the replay session/generation and cannot mutate a seek result.

Seek retires the old replay consumer generation, cancels only that isolated drain, creates a fresh replay consumer identity/journal/scene from the authenticated archive bootstrap or validated checkpoint, and reconstructs both the replay canonical replica and replay presentation replica by processing retained ordered heads through this discriminator. Seeking before a reset stops before it; seeking at the reset includes its atomic patch install/stateSync; seeking after it includes it exactly once before later normal heads. It may use a validated replay checkpoint only when that checkpoint records both replicas, terminal state, and the exact next journal head/observation identity; it may not jump the presentation replica across a reset using canonical state alone. A terminal checkpoint/segment admits no later observation frame.

Reset-call reconciliation is identical to the live journal boundary but stays local: if the method throws before installation, the exact reset remains the head and the replay stops unsafe without a blind retry; if inspection proves that exact cursor/frame installed, stateSync/terminal completion may complete once; any other result is an isolated replay fault. A stateSync throw after install retains the installed journal/terminal fact, stops playback, and cannot apply the frame again. Studio evidence/history views consume this isolated drain or its fully state-synced checkpoints; they never feed a reset frame through the normal cue mapper or silently ignore it.

`SubjectiveReplayCaptureStore`, Python replay validation, and SDK replay validation treat exactly one of these as encounter-end authority: an ended bootstrap, an ordinary terminal `EncounterPresentationCue`, or a reset frame's `EncounterTerminalPresentationFact`. They preserve and validate the applicable cue `presentation_id` or fact `terminal_authority_id` exactly through encode/import/seek; they never translate between branches. They reject same-event cross-branch delivery, changed IDs/payload, multiple terminal events, and every later **observation** delivery/source slot, while preserving the existing right to append exact already-finalized combat-log deliveries whose event barriers do not exceed the terminal source cursor and whose combat-log cursors advance contiguously to the bundle's `terminal_combat_log_cursor`. Those log-only deliveries create no presentation head and cannot change encounter-end authority. The validators require the replay segment's `end_reason="encounter_ended"` to match and preserve the same event UUID/cursor/reason/combatant facts through encode/import/seek. A reset frame that installs ended encounter state without the fact is invalid and cannot close an archive.

## 9. Implementation checkpoints

### Checkpoint A — SDK render projection and edge key

1. Add projection-neutral connector validation, render connector records/projector, and `RenderGrid.connectors`.
2. Add branded structural-edge key without parsing it back into geometry.
3. Update SDK render tests and exports.
4. Update NeuroClient stateSync/store/parity/static-board connector path and edge-key consumption.
5. Add the connector reconciler and neutral planar node through the existing `toIso()` geometry.

The checkpoint is not complete if a recovered client reads `APIGrid.connectors` directly or connector changes rebuild unrelated board domains.

### Checkpoint B — typed locomotion cue and replay hard cut

1. Replace the cue enum/geometry contract with strict closed models.
2. Add the bounded root-EFFECT context store and bind each Step `parent_event` to that exact current/context root EFFECT without waiting for root COMPLETION.
3. Add exact cursor-keyed poison closure/deferred-detach for both explicit outer-batch and immediate-singleton delivery, requester-safe reset frames, final-delivery terminal authority, SDK normal-preview/reset-head token methods, and typed transient GET-bootstrap deferral; add no recovery mutation endpoint.
4. Enforce the exact family table and omit connector roots from generic action cues.
5. Bump player replication/replay versions and regenerate contracts.
6. Add real Move, Swim, Fly, Burrow-mode Move, Jump, and connector mapper tests.
7. Add V1 replay preflight/history, reset-terminal closure, and local presentation-persistence cutover tests.

The checkpoint is not complete if any family defaults to Walk, any player cue exposes objective path progress/total, or any consumer waits for an unknown movement fragment.

### Checkpoint C — one NeuroClient locomotion owner and product vertical

1. Cut active cue consumers to the new generated fields.
2. Replace Jump buffering and any connector-specific queue with the one locomotion session.
3. Route all families through the existing planar clip geometry and the single transaction terminal while retaining typed elevation evidence losslessly.
4. Make one serialized live `PresentationHeadDrain` the exclusive normal/reset journal consumer; consume only SDK exact-head previews and enforce unconditional pending-reset tokens plus post-idle `PresentedAffordanceLease` invalidation/catch-up using current owners.
5. Add disjoint live/replay consumer identities and the isolated `ReplayPresentationHeadDrain` with exact preview/normal/reset/terminal/seek semantics and no live transport, attachment, credential, command, recovery, or store edge.
6. Preserve action-bar discovery/submission and accessibility.
7. Run one recovered-client vertical proving connector render, traversal cue, ordered reset, safety catch-up, replay reset/seek, and teardown without reducer bypass.
8. Delete retired two-family cue code, deferred Jump owner, and local structural-edge key.

Each checkpoint is reviewable, but this is one atomic product cut. Main may not consume mixed cue generations.

## 10. Required tests

### 10.1 Backend/player projection

Extend focused owner tests, primarily:

- `tests/manual/test_117_player_replication_contract.py`;
- `tests/manual/test_121_canonical_presentation_mapper.py`;
- `tests/manual/test_122_canonical_replication_runtime.py`;
- `tests/manual/test_120_subjective_world_projection.py`;
- `tests/engine/test_move_settlement.py`;
- `tests/engine/test_elevated_jump_transaction.py`;
- `tests/engine/test_traversal_connectors.py`.

Required exact cases:

1. real walking root -> Walk/Path with per-Step elevations;
2. real Swim root -> Swim/Path;
3. real Fly root -> Fly/Path;
4. real `Move(movement_mode=BURROWING)` -> Burrow/Path;
5. real multi-cell elevated Jump -> one Jump/DirectArc cue with exactly two elevation-bearing anchors and no progress/total protocol;
6. real connector root -> one Connector/ConnectorTransfer cue, no generic Action cue;
7. first and later Step frames resolve only the minimal frozen root context by `Step.parent_event`; a matching current-batch Event is consistency evidence only and root COMPLETION is not awaited;
8. a visible-hidden-visible PATH emits the authorized visible run before the gap and a later independently terminal visible run after it, never stitches the runs, and exposes no public identifier linking those runs or hidden endpoint/elevation/path total;
9. a hidden Jump endpoint, hidden connector endpoint, or missing root identity grant omits the applicable one-leg/root cues without fault or partial geometry;
10. mismatched current root/Step type, source, lineage, admitted path, index, total, trajectory, elevation, or connector identity fails closed before privacy filtering;
11. current-frame gaps, duplicate Steps, broken position/elevation chains, and invalid admitted-path membership fail closed;
12. connector cue contains no digest, costs, provocation, support UUID, bidirectionality, or hidden endpoint;
13. nested/child Step belongs to exactly one root and creates exactly one cue;
14. a committed arrival followed by synchronous forced displacement retains its truthful cue although final frame occupancy differs;
15. `NOT_COMMITTED` attempted endpoint is never treated as committed occupancy;
16. extra fields, bool/string numeric coercions, invalid UUID/exact canonical pattern/revision/elevation, and invalid family combinations reject at model construction;
17. no movement behavior-binding attribution appears solely from Step/root grouping.

Runtime-level context-store cases additionally prove:

1. a multi-Step Move publishes each committed Step frame immediately with that frame's exact FOV/light/world patches;
2. the passive root-EFFECT callback captures/seeds the lineage context and first UUID/cursor alias before any Step; first and later Steps only resolve aliases and never capture, copy, query, or repair root authority;
3. later child publication plus direct mutation of the original queue-owned root cannot alter the minimal frozen context or a later perspective authorization decision;
4. same-frame pre-edge reactions remain graph-local to the Step frame that contains them;
5. multiple active subjective partitions share the same immutable context safely, and root COMPLETION/CANCEL evicts it only after every healthy partition projects its final source suffix;
6. a closed **explicit action batch** with an accepted root EFFECT captured under `EXPLICIT_ACTION_BATCH` but no terminal immediately evicts once and emits one generic `SOURCE_PRESENTATION_DISCONTINUITY` reset-required final suffix; separate precommit and postcommit publication-failure cases rebase to truthful current state without inventing completion. When that otherwise healthy missing-terminal audit also owns the accepted encounter end/ended patch, it is the enumerated §4.6 author of the one final terminal reset with no later observation-only frame;
7. reset, detach, generation change, conflicting lineage/alias ownership, missing/wrong-generation context, and capacity overflow follow the exact poisoned-batch/reset-frame state machine and never misuse `clear_generation()` as a source reset;
8. duplicate delivery of the same UUID/cursor is idempotent, conflicting UUID/cursor ownership fails, and neither path creates a second presentation node;
9. the store never retains Events, slots, world snapshots, patches, Steps, reactions, or presentation output and never delays a source watermark;
10. real Movement, Jump, and connector EFFECT handlers each make one allowed status edit; the final returned EFFECT UUID resolves through the lineage alias, PATH/context copies once, root capacity counts one lineage, connector classification derives from exact root type rather than a root trajectory field, and terminal/incomplete cleanup runs once;
11. an instrumented long PATH with multiple subjective partitions constructs/copies the path context exactly once and performs one direct indexed validation per Step per partition, with no path copy/scan during later PATH Step validation;
12. a no-handler root resolves through seeded alias 1; exactly 16 total aliases for one lineage remain valid and alias 17 fails closed;
13. with zero open partitions, injected alias/type/capacity failure blocks only an absent-partition bind with typed `source_batch_in_flight`; both an explicit outer batch and an outside-batch immediate singleton deliver the offending cursor to the exact batch callback, close poison once without conflating singleton delivery with lifecycle completeness, and permit a later GET bootstrap from current truth; no relevant root/Step store route can omit that containing callback;
14. with existing partitions, every later Step and final suffix in the poisoned batch carries exact patches/watermarks, zero cues, and the closed generic `SOURCE_PRESENTATION_DISCONTINUITY` reset directive; the journals/replay remain healthy and ordered and other perspectives learn no event family;
15. already-open page/SSE readers continue through poison, while direct-worker and hosted-proxy absent-partition bootstrap return/decode the typed 409 and boundedly succeed only after closure; no raw string or POST recovery path exists;
16. a poison is keyed by the observable offending root/Step cursor; only the delivered explicit batch or immediate singleton whose exact cursor interval contains it closes the latch, while an unrelated batch cannot;
17. `stop()` after poison but before containing delivery defers callback removal; explicit outer-batch and immediate-singleton zero/existing-partition closure paths run once, then detach/clear occurs; same-generation reattach before/after closure cannot orphan a 409 latch, duplicate a reset, or lose a terminal suffix;
18. a real generation change retires the old latch/runtime, and a later independent movement after normal closure captures/projects normally;
19. a real movement-poison outer batch that also contains accepted `EncounterEndEvent` produces one **final** reset frame with exact deterministic `terminal_authority_id`, ended encounter patch, zero cues, live discriminated terminal record/lock/result after reset stateSync, and one durable replay segment that closes/validates/seeks as `encounter_ended`; an earlier detecting Step candidate cannot publish the terminal fact/ended patch, the closure emits no observation-only reset after that terminal frame, and any real later source slot plus missing/duplicate/mismatched fact fails closed. An exact terminal-at-Step-boundary/empty-closure case proves poison clearing without a second observation delivery;
20. real healthy immediate singleton delivery in the order root EFFECT -> multiple committed Steps -> root COMPLETION/CANCEL retains one context across the nonterminal singleton callbacks, projects every Step, projects the terminal suffix once, then evicts. Root EFFECT and Step-only singletons never run the explicit-action incomplete audit. Separate poisoned singleton sequences with zero/existing partitions and stop/deferred-detach close only the offending delivery and cannot false-reset or evict an unrelated healthy singleton lineage.

### 10.2 SDK

Extend:

- `sdk/typescript/src/tests/renderProjection.test.ts`;
- `sdk/typescript/src/tests/replication.test.ts`;
- `sdk/typescript/src/tests/replay.test.ts`.

Required exact cases:

1. objective and subjective render projection produce equal connector records for the same structurally valid authorized `APIGrid`;
2. common connector validator rejects duplicate identity, equal endpoints, bounds, missing tile, and elevation mismatch in both render paths;
3. subjective validation additionally rejects hidden/unprojected connector endpoints;
4. projection exposes only the §4.1 field set;
5. deterministic connector ordering is input-order independent;
6. connector set replacement covers register, replace, enable, disable, hide/reveal, and remove through reducer then render projection;
7. reciprocal structural-edge halves in all four directions and at negative coordinates produce one equal key;
8. door open/close retains the same key and conflict handling remains unchanged;
9. projection never parses the key back into geometry;
10. V2 cue decoding and replay seek/import preserve families, trajectories, anchors, and connector identity;
11. V1/unknown replay is rejected at envelope identity preflight before V2 nested decode;
12. worker/archive/fixture schema IDs and hashes are V2-coherent;
13. exact normal head N preview reduces only presentation+N while authoritative already contains N+1; the immutable preview/token is idempotent, one-slot bounded, and cross-journal/stale/reset/live-replay-crossed tokens cannot commit;
14. `inspectResetPresentationHead()` accepts only the exact reset head, returns no candidate, and its opaque token alone may reset that head. Normal planners reject reset evidence; reset planners reject normal preview evidence and execute zero cue-mapper/candidate-reduction calls for both live and replay consumers;
15. reset terminal fact construction/decoding requires the exact domain-separated authority ID, ended patch, and final source interval, is mutually exclusive with cues, and Python/SDK replay capture/validation recognizes ended bootstrap, ordinary terminal cue, or final reset terminal fact as the closed disjoint terminal authority. Same-branch exact duplicate is idempotent; ordinary-cue versus reset-fact authority for the same event, changed authority ID/payload, and multiple terminal events conflict. Encode/import/seek preserves the discriminated ID byte-for-byte and no client derives one;
16. replay seek before/at/after a terminal reset preserves exact terminal state and rejects any later observation delivery.

### 10.3 NeuroClient

Add the exact maintained script:

```text
connector-presentation:smoke
```

and include it in the maintained browser/release aggregate. Required gates are:

- default `npm run check`;
- production `npm run build`;
- maintained SDK full test/check, not only focused files;
- `player-replication-boundary:smoke`;
- `render-projection-parity:smoke`;
- `render-parity-live:smoke`;
- `subjective-production-adapter:smoke`;
- `static-board-sync:smoke`;
- `world-depth-structural-edge:smoke`;
- `movement-presentation:smoke`;
- `subjective-presentation:smoke`;
- `subjective-animation-coverage:smoke`;
- `presentation-head-drain:smoke`;
- `presented-affordance-lease:smoke`;
- `subjective-replay-reset:smoke`;
- `studio-evidence-import:smoke`;
- `render-lifecycle-isolation:smoke`;
- `connector-presentation:smoke`;
- recovered-client browser smoke.

If stale Runtime-V2 rollback tests prevent the maintained default suite from running, remove them only after mapping every unique active behavior to a maintained test. Do not restore abandoned artifacts or hide the tests from the default command.

The recovered-client vertical proves:

1. bootstrap contains an authorized connector;
2. the SDK journal accepts it;
3. `projectSubjectiveRenderWorld()` emits it;
4. stateSync stores that exact render record;
5. the connector reconciler creates one retained node;
6. replacement/disable updates only that node;
7. removal/reset destroys it;
8. action bar discovers and submits a typed connector action by mouse and keyboard;
9. traversal produces Connector/ConnectorTransfer intent with exact authorized position/elevation facts;
10. one central transaction commits the frame after animation;
11. stale, canceled, failed, reset, and generation-mismatched terminals cannot commit or resurrect state;
12. no renderer path imports raw connector replica state.

Frame-coordinator tests additionally prove exactly one normal commit attempt using the SDK-owned exact-head preview token for a verified state-only plan, a non-locomotion visual plan, and a successful locomotion plan. Canonical/authoritative state already containing N+1 cannot enter N's immutable preview, render projection, mapper, staging, or pixels. They prove the live drain never has two head coordinators, never stages/enqueues N+1 while N is active, and leaves accepted later frames inert in the SDK journal. Live plans reject replay consumer identity; replay plans reject live attachment identity; a retired seek generation cannot settle a new replay plan. Every row in the closed state-only table has one positive exact-predicate case plus wrong-kind/wrong-field negatives; every visually relevant cue family is rejected if labeled state-only. Exact identity/disposition negatives cover unknown, duplicate, missing, multiply-owned, wrong-parent/sibling/unrelated folded owner, empty folded evidence, and an owner lacking the child's exact shared intent evidence. A valid visually relevant cue for which the mapper returns neither an intent nor an allowed state-only reason produces one mapping incident, zero journal commits, and authenticated local recovery; it cannot take the immediate barrier.

Reset-directive gates prove: generated NORMAL/reason-null and RESET_REQUIRED/reason-present construction; reset frames reject cues/cue-cursor advance; a nonterminal closure with no unconsumed source slot emits exactly one observation-only reset with unchanged source/presentation cursors, while a terminal-bearing final reset suppresses that extra closure frame; SDK paging/SSE/duplicate/replay preserve them; `pendingResetFrames` remains exact under duplicates, compaction, consecutive reset, reset consumption, invalidation, and bootstrap replacement. `inspectResetPresentationHead()` accepts only the exact reset queue head and produces no candidate/cue mapping; `resetPresentationFrame(token)` accepts only its exact opaque token, applies only that frame's patches, advances no cue cursor, and is atomic on validation failure. Exact live-drain cases cover active NORMAL -> accepted RESET, pending NORMAL -> RESET, a reset accepted while the current NORMAL enqueue is at causal high-water, consecutive resets, and canonical-ahead RESET -> NORMAL. They prove the reset-pending mask disables immediately but does not cancel the earlier head; every head terminates exactly once; later frames consume no causal queue capacity before becoming head; a failed earlier normal owns the only recovery and retires the later reset with the old journal; a successful earlier normal leaves before reset; and no server directive plus local-recovery double path exists. At a reset head, event ingestion uses only the live reset planner, performs zero normal preview/commit/map/enqueue calls, invokes the token-bound reset method at most once, state-syncs the reset replica, and records server-reset evidence rather than a local incident. Reset-method throw-before/after-install reconciliation, stateSync failure, stale generation, and late clip completion cannot duplicate, skip, or resurrect presentation. A successfully applied server directive invokes no local recovery callback.

Presented-affordance gates use only executable current owners. Every accepted reset in the current journal holds the unconditional `PendingResetSafetyToken` until all resets are consumed/state-synced or that journal is retired; consecutive resets cannot transiently enable between heads, even when an old row appears unrelated. The sole lease owner permits at most one abortable row acquisition, one fixed catch-up target, and one automatic acquisition per idle epoch; concurrent mount/controller/reconnect/user triggers coalesce, stale responses cannot install, and fetch failure creates no timer/polling loop. `APIAvailableActions` is fetched only after an idle/empty drain, followed by a first ordinary page whose exact source/observation/presentation projection of `captured_watermarks` is the fixed attempt fence. Exact equality may install only after before/after revalidation; componentwise dominance with a strict advance is the only catch-up relation. Axis-specific source/observation/presentation regressions and every mixed higher/lower pair enter `FENCE_FAULTED_WAITING_STREAM_RECOVERY`, produce no lease/retry, and recover only with a replacement journal. Advanced capture proves the exact phase sequence `ACQUIRING_ROWS -> CATCHING_UP_FIXED_FENCE -> ARMED_FOR_POST_CATCHUP_IDLE -> fresh ACQUIRING_ROWS`: rows are discarded before follower ingest, expected through-target frames—including reset directives—do not self-abort, later capture values do not extend the target, and exactly one queued fresh acquisition starts when target and full drain idle are both true even if the ordinary idle notification happened earlier. Exact gates cover unrelated frame arrival during actions fetch, advanced first page, fixed-fence continuation, beyond-target traffic, reset consumption, reset/recovery journal replacement and other identity abort, combat-log-only advancement without redundant lease invalidation, unmount/controller/generation races, transient fetch/page failure, sustained frame traffic, reconnect, explicit user retry, and a late response from an old `attempt_id`. Any later accepted observation frame, head start, controller/attachment/generation change, recovery, terminal lock, or reset token invalidates an installed lease synchronously. Submission requires the current lease plus exact displayed row/target and presented geometry; server command validation remains final authority. Canonical-ahead RESET -> NORMAL and fetch-race cases cannot enable against stale pixels, and no case hot-loops or remains silently enabled.

Mounted browser/visual gates prove that lease absence affects only interactivity. During active normal animation, enemy activity, pending reset, fixed-fence catch-up, and transient affordance-fetch/page failure, the last presentation-clocked action rows remain mounted, visible, inspectable, and keyboard-focusable but disabled with no target/submit edge. They clear or rebase only when the presented SELF/current-turn/terminal workflow commits or resets; canonical-ahead state and lease invalidation alone cannot hide/flicker the bar. A fresh lease enables/replaces exact rows without remount churn or focus loss beyond the existing presented workflow.

Encounter-result gates run ordinary terminal cue and cue-less terminal reset through the same mounted result owner. They prove the record's authority union is exact, the old misleading `lineageUuid` field is absent, each branch crosses only its own barrier, same-branch replay is idempotent, cross-branch same-event and changed-ID delivery fault, and reset fact authority survives local persistence/replay/seek without client synthesis.

Replay/Studio gates run an isolated V2 archive through `NORMAL -> RESET_REQUIRED -> NORMAL`, including an observation-only reset, and a separate movement-poison `NORMAL -> terminal RESET_REQUIRED -> finalized log-only deliveries` archive. They prove disjoint replay-session identity, seek before/at/after reset, duplicate reset delivery, stale completion fencing, and throw-before-install/throw-after-install/stateSync reconciliation. Each reset is applied exactly once to the replay presentation replica; later normal frames see the nonterminal reset state; a terminal reset closes presentation/result authority exactly once and admits no later observation frame, while exact contiguous combat-log-only deliveries may reach the terminal log cursor without creating a presentation head. Playback/Studio pixels, transient nodes, logs, diagnostics, terminal reason/combatants, and replay end reason agree at each seek point; and no replay path imports or calls live transport, attachment, credentials, command submission, presented-affordance lease, authenticated recovery, or live StoreState. A reset can never be routed through the normal cue mapper or ignored as state-only.

Injected failures cover candidate derivation, mapping/coverage, partial staging, enqueue rejection/throw, barrier failure/cancel, precommit recheck, commit-before-mutation throw, commit-after-mutation throw, stateSync, and best-effort diagnostics for both state-only and visual plans. They prove the exact precommit/postcommit matrix, at-most-one commit call, cursor-based commit reconciliation, one incident/recovery latch, transient teardown, and successful replacement bootstrap. Transaction reset and stale generation each produce zero new commit attempts and cannot resurrect state. Static dependency checks prove live journal writes are imported only by the live frame coordinator/head drain and isolated replay journal writes only by the replay head drain, never by VisualTransaction, clips, renderer, stateSync, or the locomotion executor; prove `eventIngestion.ts` does not reverse-import `eventStream.ts`; and prove the replay drain has none of the forbidden live edges in §8.2.

A maintained browser/runtime visible-hidden-visible case commits the hidden state-only removal, then presents the later authorized PATH edge from its first authorized anchor with no destination-first pixel, backward snap, hidden-gap interpolation, or root-stable correlation. Maintained real-family tests execute Walk, Swim, Fly, Burrow, Jump, and Connector through the one session and assert the exact §7.6 profile, typed family retention, terminal pose, reset, and teardown.

ClipQueue liveness tests use a deterministic monotonic clock to cover a concurrent/busy enqueue rejection, a never-resolving clip, stalled asset preparation, stalled live-distance projectile, lost frame-offset child completion, active timeout/reset recovery, and a stale completion after timeout. Real Attack, Cast, Shove, TakeDamage, Walk, Jump, and Connector transactions complete inside the conservative active wall bound. The gates prove the head drain creates no supported causal backlog, decorative work consumes no causal slot, watchdogs are canceled on lawful head reset/recovery, no failed transaction invents a pose or success, and only the aggregate ClipQueue result can release the frame barrier.

The local-cutover test seeds all three exact durable keys from §7.9, verifies their envelope identities before nested parsing, and proves unrelated storage plus the run-ID key remain untouched. A static startup gate proves those owner modules perform no storage parse at module evaluation and that only `PresentationPersistenceCutCoordinator` may authorize their initialization.

### 10.4 Visual and accessibility evidence

Capture stable browser screenshots for:

- the existing zero-elevation/no-connector baseline;
- the maintained connector proving scene, including elevation-bearing connector data rendered intentionally through the planar product boundary.

Pixel/product assertions must prove:

- tiles, walls, objects, entities, HUD scale, and Pixi framing remain unchanged from the recovered planar renderer;
- neutral connector dimensions stay within the §7.4 bound;
- hidden connector has no node, picking, ordering, shadow, or camera effect;
- connector rendering does not change the fixed recovered camera/zoom behavior;
- positive/negative endpoint elevation remains exact in state, intent, replay, diagnostics, and Studio evidence while producing no independent pixel offset;
- no console error, presentation incident, or leaked display object occurs;
- action-bar connector control is focusable, keyboard-operable, and accessibly named;
- read-only connector status is accessible but cannot issue a command.

## 11. Static/deletion gates

Acceptance scans prove:

- no `MovementKind` or `movement_kind` remains in active presentation contracts/consumers;
- no 2-D `trajectory` field remains on `MovementPresentationCue`;
- no `movement_sequence_id`, `path_start_index`, `path_total_steps`, objective movement progress/total, or fragment-wait protocol remains in active player cues/consumers;
- no mapper branch defaults non-direct-arc movement to Walk;
- no `TraverseConnectorEvent` also creates a generic Action cue;
- no root facts are consumed without root-local authorization;
- no current-batch/queue-owned Event is root classification or privacy authority; Step parent UUIDs resolve only through the bounded lineage alias map to the minimal frozen context;
- passive root-capture failure cannot be dropped when zero partitions are open; absent-partition bind is transiently deferred through the exact containing explicit-batch or immediate-singleton callback, while existing partitions receive requester-safe reset frames and no mutation recovery protocol exists;
- no renderer/state module reads canonical `APIGrid.connectors` directly;
- no frontend switch branches on connector authored ID, name, kind-specific content, or `presentation_key`;
- no local NeuroClient structural-edge key/reciprocal normalizer remains;
- no edge-key string parser reconstructs geometry;
- no render connector exposes digest, costs, provocation, bidirectionality, or support UUID;
- no `deferredJumpSequence`, `resetBufferedJumpPresentation`, JumpClip buffer, connector-specific queue, or family-specific commit path remains;
- `eventIngestion.ts` contains no locomotion-family branch or direct clip/session commit;
- no raw `VisualTransaction | null`, `transaction === null`, free-form reason string, or missing-intent inference authorizes a state-only commit; only the closed frame-bound presentation plan, literal reason table, and exact graph/intent dispositions can do so;
- no reset frame is passed through generic presentation-cue mapping, normal preview, `commitPresentationFrame()`, ClipQueue, or a client/server incident-token exchange; only the narrow terminal projector may add the closed frame-level terminal fact, and only an SDK `ExactResetPresentationHead` token reaches `resetPresentationFrame()`;
- no frontend/replay module applies subjective patches or derives a head candidate from the authoritative-ahead replica; only SDK `previewPresentationFrame()` creates a normal candidate/token, and only that token can commit the normal head;
- no terminal reset relies on an empty cue: the frame-level terminal fact is the sole alternate terminal authority and is consumed consistently by live result, replay capture, Python/SDK validation, seek, and Studio;
- no public reset reason names movement, connector, root identity, internal failure, or hidden geometry, and no `POST /replication/recover`/epoch-swap protocol is introduced;
- no accepted later live frame is mapped, staged, enqueued, executed, committed, or reset before it becomes the exact serialized journal head; the live ClipQueue has no pending-frame capacity;
- every pending reset in the current journal holds one unconditional disable token; it cannot be waived as basis-unrelated, cancel an earlier head, call reset out of order, or enable from authoritative state ahead of presentation catch-up;
- no `ActorOffer`, `CommandBasis`, or `InteractionSafetyWatermark` placeholder is introduced; interaction uses the exact current journal/controller/`APIAvailableActions` lease sequence and invalidation rules in §7.6;
- no poisoned same-generation runtime removes its sole closure callback before the containing explicit depth-zero batch or immediate singleton callback; deferred detach/reattach cannot leave an orphan 409 latch;
- live journal commits/resets are reachable only from `PresentationFrameCoordinator` through `PresentationHeadDrain`, and `eventIngestion.ts` has no reverse import of `eventStream.ts`;
- replay journal commits/resets are reachable only from `ReplayPresentationHeadDrain`; that module has no dependency on live event stream, transport, credentials, command submission, authenticated recovery, interaction safety, or live StoreState;
- neither live nor replay reset can be routed through the normal cue mapper or state-only classification;
- `LocomotionSessionExecutor` cannot settle a whole `VisualTransaction`; only `ClipQueue` can produce the aggregate frame-barrier terminal;
- no locomotion clip or connector renderer converts elevation into a private pixel transform;
- no V1/V2 dual cue reducer or compatibility alias exists;
- local V1 presentation state is fenced and discarded before parsing.
- presentation persistence owners perform no eager storage read/parse before `PresentationPersistenceCutCoordinator` initializes them.

Source scans are necessary but not sufficient; §10 behavior and screenshot gates must also pass.

## 12. Performance and resource fences

- Connector render projection is `O(c log c)` for `c` authorized connectors due only to deterministic sorting; it performs no grid search or service call.
- Structural-edge projection keeps its existing complexity and computes each key once without parsing it.
- NeuroClient retains at most one connector display object per connector UUID.
- Connector-only updates do not rebuild unrelated scene domains.
- remove/hide/reset destroys node, graphics resources, cache row, and listeners immediately.
- A PATH lineage copies its admitted path once in `O(n)`; each later Step lookup/validation is `O(1)`. At most 16 allowed EFFECT aliases may each compare—but never copy—the path once, so across `p` partitions and `n` Steps work is `O(16*n + p*n)`, never `O(p*n^2)`. Jump performs one arc capture plus bounded alias comparisons for its single leg; connector context is constant-size.
- The root-context store retains at most 64 minimal frozen root classification/authorization records and 16 total UUID/cursor aliases per lineage per generation, including the first EFFECT alias. It contains no Event/slot alias, cost, digest, child list, world snapshot, patch, Step, reaction, or presentation output.
- A poisoned explicit outer batch emits at most one nonterminal reset frame for each already-existing Step reducer boundary plus one final closure frame; an immediate singleton emits at most its one closure frame. If encounter end is observed, intermediate terminal output is replaced by one constant-size event/cursor marker and exactly one final terminal reset; no frame, patch list, world snapshot, replacement bootstrap, incident queue, replay copy, or retry task is retained.
- The locomotion session owns at most one active transaction per entity/source/generation and releases timers/tweens/listeners on every terminal.
- the live ClipQueue retains zero pending causal transactions and at most one active head transaction; accepted later frames remain only in the bounded SDK journal, and active wall time—including preparation and nested execution—is bounded by 60 seconds.
- No worker, thread, or background scheduler is added. The bootstrap-deferred path retains its foreground, abortable, 10-second bound. Presented-affordance acquisition adds one authenticated actions fetch plus one first observation-page request per admitted row attempt and only the existing bounded pager calls needed to reach that first response's fixed captured presentation fence. At most one row attempt or one nonextending fixed-fence catch-up phase exists, one armed post-catch-up trigger is retained, at most one automatic row attempt occurs per idle epoch, and there is no polling/timer/same-idle retry. Ordinary frame processing itself adds no network call.

## 13. Exact implementation gates

Backend/SDK implementation must include:

```text
uv run pytest <each focused owner file> -q
uv run pyright <changed Python production and focused tests>
uv run python devtools/generate_event_contract.py --check
uv run python devtools/generate_typescript_sdk.py --check
npm --prefix sdk/typescript run build
npm --prefix sdk/typescript test
```

NeuroClient implementation must include its default `npm run check`, production build, the named smoke gates, and screenshots in §10.4. A generator command that only rewrites artifacts without a final `--check` is not acceptance.

## 14. Explicit non-goals

This unit does not:

- change movement, Jump, connector, OA, collision, cost, or settlement mechanics;
- merge engine action executors;
- expose connector provider/support identity;
- restore abandoned Runtime V2 architecture or tests;
- add connector-name, authored-ID, kind-specific content, or presentation-key switches;
- author final ladder/rope/lift/vertical-stairs/passage sprites;
- build a connector asset catalog;
- implement partial or board-wide elevation rendering, vertical faces, elevated picking, or elevated camera bounds;
- migrate immutable server-side V1 replay bytes;
- broaden forced-movement cue semantics;
- redesign structural edges.

Elevation is preserved as typed presentation evidence but intentionally remains planar in this unit. A later elevation-rendering feature must introduce one renderer-owned surface geometry for all consumers together; no partial bridge is left here.

## 15. Acceptance definition

The unit is complete only when all of the following are simultaneously true:

1. `ReplicatedRenderWorld.state.grid.connectors` contains deterministic privacy-safe render records.
2. A recovered NeuroClient reaches and renders those records through the SDK presentation replica only.
3. Connector lifecycle replacement/disable/remove/reset has one retained identity and complete isolated teardown.
4. Structural edges expose/use one SDK-owned key without reparsing it.
5. Real Walk, Swim, Fly, Burrow-mode Move, Jump, and connector actions emit distinct truthful cues.
6. Exact minimal frozen root EFFECT authority, bounded generation-scoped context, and Step parent binding prevent family/identity borrowing without delaying per-Step frames for root COMPLETION.
7. Cue anchors preserve only authorized position/elevation facts and do not claim current occupancy.
8. Jump is one presentation leg with no objective progress protocol; all families use one central locomotion session while `ClipQueue` alone owns whole-transaction settlement.
9. Connector cues carry only safe presentation identity and do not also become generic Action cues.
10. Connector and locomotion rendering stay on the one recovered planar geometry while preserving exact elevation facts for the later coherent renderer feature.
11. Current SDK replay/cue decoding, local presentation persistence, and active NeuroClient consumers are V2-only and green.
12. SDK exact-head preview is the sole normal candidate owner, and its disjoint exact-reset-head token is the sole reset owner; neither live nor replay frontend reduces patches or reads authoritative-ahead state to stage a frame.
13. One serialized live head drain makes every accepted normal/reset frame terminal exactly once; later frames stay inert in the SDK journal and cannot cancel or bypass the active head.
14. Every pending reset holds an unconditional disable token; mutation becomes enabled only through the sole bounded, abortable, coalesced post-idle `PresentedAffordanceLeaseOwner` bound to the exact page capture fence, presentation identity/cursors, and current controlled entity. Fixed-fence catch-up cannot cancel or lose its one post-idle reacquisition, every later accepted frame invalidates a lease synchronously, and lease absence disables without hiding presentation-clocked rows.
15. Isolated replay/Studio presentation uses disjoint replay-session identity, applies every retained reset/terminal fact exactly once in order, seeks deterministically across it, and has no live attachment, transport, credential, command, recovery, or store authority.
16. A terminal reset is the final observation frame, preserves one requester-safe encounter terminal fact through live result ownership, replay capture/validation, archive closure, and seek despite its empty cue window, and still permits only exact finalized log-only deliveries through the terminal combat-log barrier.
17. Interaction remains generated action-bar authority and stays keyboard/accessibility complete.
18. No objective re-query, second reducer, compatibility layer, connector-name switch, or broad scene rewrite was introduced.
19. Default maintained SDK and NeuroClient checks, production build, focused backend gates, browser vertical, and visual evidence all pass.
20. Per-Step source frames preserve intermediate world/FOV/light truth; hidden PATH gaps are neither stitched, linked by a public root token, nor converted into whole-root suppression.
21. The one active ClipQueue deadline, zero pending causal backlog, reset/head ordering, and stale completion fencing make the frame barrier bounded without inventing presentation success.
22. Root-capture poison is keyed by the offending observable cursor and closes only at its containing explicit depth-zero batch or immediate singleton delivery, independently of lifecycle completeness. Healthy singleton root/Step contexts survive until their exact terminal singleton; explicit action batches alone prove missing terminal evidence. Neither path can be orphaned by same-generation stop/detach/reattach; existing partitions consume reset frames and zero-partition bootstrap is deferred only until exact poison closure.
23. This exact plan revision receives independent internal, implementation-task, and NeuroClient acceptance before implementation; the final implementation cutoff receives independent backend and frontend review.

Compile-green without the recovered-client vertical, privacy negatives, lifecycle isolation, one transaction owner, replay/local-cache cutover, accessibility, and visual parity is not acceptance.
