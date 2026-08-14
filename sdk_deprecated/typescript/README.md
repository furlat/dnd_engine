# D&D Engine TypeScript SDK

This package is the generated and handwritten browser boundary owned by
`dnd_engine`. Player replication, objective diagnostics, and the game-directory
control plane are deliberately separate transports.

## Contract generation

`devtools/generate_typescript_sdk.py` walks the backend Pydantic graph. The
player contract is authenticated by `PLAYER_REPLICATION_CONTRACT_HASH`, which
covers the complete transitive subjective wire schema.

```bash
uv run python devtools/generate_typescript_sdk.py
uv run python devtools/generate_typescript_sdk.py --check
npm test --prefix sdk/typescript
```

Generated files are never edited manually. Runtime validators accept
`unknown`, prove a generated descriptor, and return the corresponding generated
type. `decodeAlias()` validates the discriminated `SubjectiveWorldPatch`,
`SubjectivePresentationCue`, `SubjectiveStreamDelivery`, and
`SubjectiveReplayDelivery` unions.

## Canonical player replication

There is one player route family:

- `/replication/bootstrap`
- `/replication/frames`
- `/replication/combat-log`
- `/replication/subscribe`

`SubjectiveReplicationClient` is its only SDK client. The three non-bootstrap
routes require the source-stream, generation, and perspective-epoch identities.
The SSE union is exactly `sync | frame | combat_log`; it never carries engine
events, objective state, heartbeats, command receipts, or compatibility frames.

`SubjectiveReplicationJournal` maintains two views. Its authoritative view
applies typed world patches as soon as an observation frame arrives. Its
presentation view applies the same patch transaction only when the renderer
commits that whole frame. Combat-log source slots—including hidden nullable
slots—advance independently and are released to presentation only after their
source-event barrier has been presented.

```text
subjective bootstrap
       |
       +----> authoritative world
       +----> presentation world

frame --typed patches--> authoritative world
  |
  +--safe cue graph--> renderer transaction
                           |
                    commitPresentationFrame()
                           |
                    presentation world
```

### Standalone startup

```ts
import {
  DndEngineClient,
  SubjectiveReplicationClient,
  SubjectiveReplicationJournal,
} from "@neurodragon/dnd-engine-sdk";

const engine = new DndEngineClient("/api");
const prepared = await engine.startGameCreation({
  scenario: {
    kind: "preset",
    arena_id: "standard_skeleton_doors",
  },
  side_a: { controller: "human", name: "My Client", policy_id: null },
  side_b: { controller: "ai", name: "Basic AI", policy_id: "builtin.basic" },
  opening_side: "side_a",
  codex_lease_seconds: 600,
});
const heroUuid = prepared.side_a.entity_assignments[0]?.entity_uuid;
if (heroUuid === undefined) throw new Error("prepared side has no hero");

const session = await engine.createSession({
  player_type: "human",
  name: "My Client",
});
await engine.joinGame({
  session_id: session.session_id,
  entity_uuids: [heroUuid],
  entity_uuid: null,
  faction: null,
  observer_entity_uuids: [],
  active_observer_uuid: null,
});

const replication = new SubjectiveReplicationClient("/api");
const journal = new SubjectiveReplicationJournal();
const bootstrap = await replication.bootstrap(session.session_id);
journal.bootstrap(bootstrap);
await engine.activateGameCreation({
  session_id: session.session_id,
  expected_source_stream_id: bootstrap.protocol.source_stream_id,
  expected_generation_id: bootstrap.protocol.generation_id,
  expected_perspective_epoch_id:
    bootstrap.perspective.perspective_epoch_id,
});
```

### Following the stream

```ts
const controller = new AbortController();

void replication.follow(journal, {
  sessionId: session.session_id,
  signal: controller.signal,
  onUpdate: ({ envelope }) => {
    if (envelope.event === "frame") {
      // Build one animation transaction from envelope.data.frame.presentation.
    }
  },
  onReplicaReset: ({ bootstrap, state }) => {
    // Atomically seed the app from the exact validated bootstrap fetched for
    // this reset; its sparse combat-log window is not reconstructed from state.
  },
});

const next = journal.peekPresentationFrame();
if (next !== null) {
  await renderFrame(next.presentation);
  journal.commitPresentationFrame(next.watermarks.observation_cursor);
}
```

Movement perception commits atomically with its observation frame. A trajectory
describes animation order; it does not expose intermediate visibility states.

## One render projection

`projectSubjectiveRenderWorld()` and `projectObjectiveRenderWorld()` feed the
same render DTO and the same `projectGrid()` implementation. Physical tile
boundaries are emitted only as `RenderGrid.structural_edges`. Every edge has
canonical north/east ownership, a `wall | door | generic` kind, an explicit
door state, and its blocked channels. Clients must not reconstruct a second
edge set from tile halves or draw directional floor-object rows as duplicate
geometry.

## Hosted games

`GameDirectoryClient` owns discovery and attachment. Its `runtimeClient()` is
the general action/state client. Construct `SubjectiveReplicationClient` with
the same runtime base URL and authorization headers for the player stream.
Credentials remain in headers and are never placed in SSE URLs.

## Durable ended-game replays

`GameDirectoryClient.getObjectiveReplay()` reads
`/games/{gameId}/diagnostics/objective-replay`; `getSubjectiveReplay()` reads
only one exact membership from `/games/{gameId}/memberships/{membershipId}/replay`.
Both require principal credentials in headers.

`decodeObjectiveReplay()` accepts the completion-only objective reducer seed,
event frames, and objective logs. `decodeSubjectivePlayerReplay()` accepts only
the same canonical subjective bootstrap, typed patch/presentation frames, and
nullable subjective log deliveries used during first play. Raw engine events
and objective state cannot inhabit the player replay type. The persistence-only
aggregate archive containing every membership is deliberately not exported by
the SDK.

## Objective diagnostics

`ObjectiveDiagnosticsClient`, `ObjectiveDiagnosticsSseDecoder`, and
`ObjectiveDiagnosticsFollower` own the separate privileged objective surface.
Its cold `GameEventFrame` and broad `TimelineCombatLogFrame` types are not
accepted by the subjective client or journal.

An ADMINISTER client can continuously audit an already-open player partition:

```ts
const report = await objectiveDiagnostics.subjectiveParity(sessionId);
if (!report.matches) console.error(report.mismatches);
```

The check compares the retained subjective reducer with an independently
censored objective checkpoint at the same source/generation/perspective
boundary. It never bootstraps, binds, advances, or repairs player state.

## Stable live exports

- `SubjectiveReplicationClient`, `SUBJECTIVE_REPLICATION_ROUTES`
- `SubjectiveSseDecoder`, `SubjectiveStreamFollower`, `SubjectiveSseEnvelope`
- `SubjectiveReplicationJournal`, `SubjectiveReplicationJournalState`
- `reduceSubjectiveWorld`, `assertSubjectiveWorld`
- `projectSubjectiveRenderWorld`, `projectObjectiveRenderWorld`,
  `projectStructuralEdges`
- `ObjectiveDiagnosticsClient.subjectiveParity`
- `decodeObjectiveReplay`, `decodeSubjectivePlayerReplay`
- generated `ObjectiveReplayBundle`, `SubjectivePlayerReplayBundle`,
  `SubjectiveReplaySegment`, and `SubjectiveReplayDelivery`
- generated `SubjectiveReplicationBootstrap`, `SubjectiveFramesResponse`,
  `SubjectiveCombatLogFramesResponse`, `SubjectiveWorldPatch`,
  `SubjectivePresentationCue`, and `SubjectiveStreamDelivery`

The general `DndEngineClient` intentionally has no replication methods. That
keeps one correct player transport instead of parallel legacy entry points.
