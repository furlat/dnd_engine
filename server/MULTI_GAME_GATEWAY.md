# Multi-Game Gateway

The engine has two supported server shapes. They share the same game runtime,
but they solve different deployment problems.

Clients detect the shape through the generated `ServerCapabilitiesResponse` at
`GET /server/capabilities`. Both deployments return HTTP 200: standalone
declares one DB-free runtime, while the gateway declares directory, persistent
history, and isolated-worker support. Clients do not probe optional routes and
interpret a 404.

## Standalone Game Server

`server.event_server` hosts one hot game in one process. It has no database
dependency and remains the shortest path for local development:

```bash
uv run uvicorn server.event_server:app --host 127.0.0.1 --port 8000
```

All state, event execution, sessions, subjective observations, and controller
commands remain in memory. Importing or running this module does not open the
game-directory SQLite database.

## Multi-Game Gateway

`server.game_gateway` is an additive control plane for hosting multiple games:

```bash
export DND_DIRECTORY_CAPABILITY_PEPPER="replace-with-a-private-random-secret"
uv run uvicorn server.game_gateway:app --host 127.0.0.1 --port 8000
```

By default it stores cold directory data at
`.runtime/game-directory.sqlite3` and worker files under
`.runtime/hosted-games/`. Each active game runs in an isolated, unchanged
`server.event_server` worker reached over a Unix-domain socket.

SQLite is used for identities, memberships, grants, attachments, game
lifecycle, immutable summaries, and rating evidence. It is not consulted while
proxying runtime HTTP or SSE traffic. Runtime authorization is installed in an
in-memory, game-scoped capability cache during attachment.

## Remote Agent Workflow

A remotely executing traditional AI follows the same authority flow as a human
or Codex client:

1. Create the game with the remotely controlled side configured as `codex`.
   The worker creates a subjective session and waits at that side's turns.
2. Create a principal for the remote process.
3. The game owner issues `POST /games/{game_id}/agent-grants` for that principal
   and side.
4. The remote process redeems the returned grant through
   `POST /games/{game_id}/attachments` with `client_kind="external_ai"`.
5. Start the policy process from any host that can reach the gateway. It
   redeems the grant itself and receives `engine_base_url`,
   `runtime_session_id`, `runtime_token`, and its controller lease:

```bash
export DND_AGENT_GRANT_ID='<grant_id>'
export DND_AGENT_GRANT_CAPABILITY='<grant_capability>'
uv run python -m ai.external_agent \
  --gateway-url 'https://games.example.test' \
  --game-id '<game_id>'
```

For local worker management and low-level diagnostics, the same executable can
still be started directly with `--base-url`, `--session-id`,
`--runtime-token`, and optional `--takeover-claim-id`.

The process bootstraps one subjective snapshot, consumes its ordered
observation and decision-epoch SSE stream, reduces that stream locally, and
submits typed epoch/row commands. It does not poll available actions and does
not import or inspect live server state.

Remote-agent authority is intentionally narrower than observer authority. An
agent token can access only its own `/ai/sessions/{session_id}/...` surface.
The gateway rejects objective `/state`, `/visibility`, `/events`, setup/reset,
evidence, session enumeration, another session, and uncontrolled entities.
Agent telemetry is written back through the same scoped session surface. The
agent also heartbeats only the takeover lease named by its connection; another
claim identifier is rejected by the in-memory authority layer.

For a process on another machine, bind the gateway to a reachable interface and
place it behind authenticated TLS. The returned `engine_base_url` must use the
public gateway origin rather than a worker socket or private worker address.

## Reconnection And Observation

Directory grants are cold, durable capabilities. Redeeming a reconnect or
agent grant creates a fresh hot runtime token while preserving the worker
session and entity assignment. Public observers receive a read-only worker
session and cannot submit commands. Private games and their directory events or
summaries are visible only to authenticated members.

## TypeScript Game Clients

`@neurodragon/dnd-engine-sdk` owns the browser-facing gateway boundary. Its
`GameDirectoryClient` uses generated backend contracts for guest identity,
discovery, creation, attachment, observation, grants, stopping, and terminal
summaries. `followGames()` consumes the authorized durable lifecycle stream
with cursor replay and retry; `runtimeClient()` binds the returned game URL and
runtime token to the existing event-replication client.

The TypeScript package does not implement an AI agent. Subjective agent
observation and policy execution remain in the independent Python agent
workflow described above.

NeuroClient uses this boundary directly. It keeps the directory principal and
durable reconnect grants in browser storage, keeps runtime bearer tokens only
in memory, and gives each browser tab its own client-instance identity. Create,
reconnect, and public-observer handshakes all converge on the same replication
bootstrap and event journal. Before a hot token expires, NeuroClient redeems
the durable grant, atomically rebinds the SDK client, and resumes from the
existing journal cursor. Standalone startup continues through the same renderer
after the capability probe reports that no game directory is present.

## Terminal Evidence

The gateway watches each worker's objective event stream for the real
`EncounterEndEvent`. Only after that event does it fetch the worker's typed
evidence envelope and persist the canonical `GameSummaryV1`. The worker remains
hot so clients can drain their presentation queues and inspect the final board.
SQLite never participates in the encounter's mutation or rendering timeline.
