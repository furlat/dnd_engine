# D&D Engine TypeScript SDK

This package is the browser and TypeScript replication boundary owned by
`dnd_engine`. A game client consumes this package; it does not redefine engine
events, action rows, state snapshots, combat logs, or stream cursors.

## Contract Source

`devtools/generate_typescript_sdk.py` walks the existing Pydantic models used by
the engine and server. It generates:

- every concrete engine event with its Python class path as `wire_type`;
- public state, visibility, entity, equipment, action, session, and game setup models;
- SSE sync, event, combat-log, heartbeat, and eviction envelopes;
- runtime model and enum descriptors used to validate JSON at the network boundary.

Arbitrary values become `JsonValue` only where the Python annotation is already
`Any` or `JsonValue`. The generator emits no TypeScript `any` or `unknown` wire
fields. `unknown` appears only as the input type of runtime validators before a
payload has proved its contract.

Regenerate and verify with:

```bash
uv run python devtools/generate_typescript_sdk.py
uv run python devtools/generate_typescript_sdk.py --check
npm test --prefix sdk/typescript
```

## Replication Model

The server exposes one atomic base at `/replication/bootstrap`. It includes the
state, visibility, combat-log history, session context, event cursor, log
cursor, event-contract identity, and EventQueue generation UUID.

`DndEngineClient.events()` resumes from those cursors. Every payload is runtime
validated before it enters `ReplicationJournal`.

```text
server EventQueue                   local SDK
-----------------                  ---------
atomic bootstrap  ---------------> authoritative world
event burst       ---------------> validate -> reduce immediately
                                      |
                                      +----> ordered presentation backlog
                                                |
renderer finishes clip <---------------- acknowledge one cursor
                                                |
                                      presentation world advances
```

The authoritative world answers what the server currently knows. The
presentation world answers what the player has actually seen rendered. They
use the same pure reducer but advance at different speeds. A slow animation can
therefore never cause a later server position, death, or condition update to
overwrite the actor currently on screen.

Numeric cursors are scoped by `generation_id`. A server reset changes the
generation even though cursors restart at zero. Duplicate events are ignored;
cursor gaps, generation changes, eviction, contract mismatch, and presentation
overflow explicitly require a fresh bootstrap.

## Client Responsibilities

The SDK owns transport parsing, validation, cursor semantics, replay,
authoritative reduction, and presentation coordination. A game client owns
rendering decisions: which terminal event maps to which animation, how clips
are coalesced, camera behavior, VFX, controls, and UI composition.

The SDK is intentionally independent from `ai.observation` and the subjective
agent runtime. Human-client replication and AI belief construction solve
different problems even though both consume engine events.

## Starting A Human Client

World creation resets the engine generation and therefore invalidates every
session from the previous world. The canonical startup order is:

```text
create world -> create session -> join entities -> atomic replication bootstrap
```

All request and response values below are generated from the Python models. A
consumer should not redeclare any of their shapes.

```ts
import {
  DndEngineClient,
  ReplicationJournal,
} from "@neurodragon/dnd-engine-sdk";

const client = new DndEngineClient("/api");
const simulation = await client.startHuman("fighter");
if (simulation.hero_uuid === null) throw new Error("world has no hero");

const session = await client.createSession({
  player_type: "human",
  name: "My Client",
});
await client.joinGame({
  session_id: session.session_id,
  entity_uuids: [simulation.hero_uuid],
  entity_uuid: null,
  faction: null,
});

const journal = new ReplicationJournal();
journal.bootstrap(await client.bootstrap(session.session_id));
```

## Hosted Games And Reconnection

Use `DndEngineClient.getServerCapabilities()` before choosing a startup flow.
The typed response distinguishes the DB-free standalone server from the hosted
gateway without relying on an expected 404 from `/games`.

`GameDirectoryClient` owns the cold multi-game control plane. Applications use
it to discover games, create or observe a hosted game, reopen a reconnect grant,
and retrieve the immutable terminal summary. Once attached, `runtimeClient()`
returns the ordinary `DndEngineClient` bound to that game and its short-lived
runtime authority token.

Directory principal capabilities and runtime tokens are sent in headers. They
are never placed in query strings or SSE URLs.

```ts
import {
  GameDirectoryClient,
  ReplicationJournal,
} from "@neurodragon/dnd-engine-sdk";

const directory = new GameDirectoryClient("/gateway-api");
const guest = await directory.createGuest({ display_name: "Tommaso" });
const credential = {
  principalId: guest.principal.principal_id,
  principalCapability: guest.principal_capability,
};

const visible = await directory.listGames(credential);
const attachment = await directory.attach(visible.games[0]!.game_id, {
  grant_id: savedReconnectGrantId,
  capability: savedReconnectCapability,
  client_instance_id: browserInstanceId,
  client_kind: "neuroclient",
});

const client = directory.runtimeClient(attachment.connection);
const journal = new ReplicationJournal();
journal.bootstrap(await client.bootstrap(attachment.connection.runtime_session_id));
```

`followGames()` consumes the durable directory lifecycle stream. It validates
every envelope, resumes from the last delivered global cursor, filters private
games through the supplied principal credential, and reconnects after transient
transport failures.

```ts
const controller = new AbortController();

void directory.followGames({
  credential,
  signal: controller.signal,
  onEnvelope: ({ event, data }) => {
    if (event === "directory_event") {
      // Refresh or patch the game browser from data.event_type and data.game_id.
    }
  },
});
```

The SDK deliberately does not persist capabilities. The application chooses
its platform-appropriate secret storage and supplies a saved reconnect grant
when opening a new attachment.

## Following Replication

`followReplication()` is the normal connection surface. It resumes at the
journal cursors, validates every SSE envelope, applies events in order,
reconnects after transient transport failures, and performs an atomic bootstrap
when a generation change, cursor gap, eviction, contract mismatch, or local
presentation overflow requires resynchronization.

```ts
const controller = new AbortController();

void client.followReplication(journal, {
  sessionId: session.session_id,
  signal: controller.signal,
  onUpdate: async ({ envelope, result }) => {
    // Read journal.state().authoritative for current game truth.
    // Queue visual work only for applied game_event envelopes.
  },
  onReplicaReset: async ({ state }) => {
    // Snap the renderer to state.presentation after the atomic replacement.
  },
});
```

The consumer must acknowledge presentation only after the corresponding visual
transaction has finished:

```ts
journal.commitPresentationThrough(completedRootEventCursor);
```

This is the only renderer-owned cursor operation. SSE parsing, retries, replay,
deduplication, authoritative reduction, and resync belong to the SDK.

## Contract Discipline

- Python engine/Pydantic models are the sole wire-contract source.
- Generated files are never edited manually.
- SDK runtime types describe local behavior such as connection health; they do
  not redeclare backend payloads.
- The reducer explicitly classifies every generated event wire class. A new
  event class fails TypeScript compilation until its public-state behavior is
  handled or deliberately identified as observational.
- A fresh bootstrap is the parity oracle for the locally reduced replica.
