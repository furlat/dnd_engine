# Multi-Game Gateway

The engine has two supported server shapes. They share the same game runtime,
but they solve different deployment problems.

Clients detect the shape through the generated `ServerCapabilitiesResponse` at
`GET /server/capabilities`. Both deployments return HTTP 200: standalone
declares one DB-free runtime, while the gateway declares directory, persistent
history, and isolated-worker support. Clients do not probe optional routes and
interpret a 404.

## Standalone Game Server

`server.event_server` hosts one hot game in one process and has no database
dependency. The bundled native policy is part of the canonical server
composition:

```bash
uv run uvicorn server.event_server:app --host 127.0.0.1 --port 8000
```

All state, event execution, sessions, subjective observations, and native
policy assignments remain in memory. Each AI side owns an independent policy,
memory, projector, bounded decision loop, and core instrumentation. Game
creation prepares those assignments without executing decisions; the explicit
activation request starts the encounter.

## Multi-Game Gateway

`server.game_gateway` is an additive control plane for hosting multiple games:

```bash
export DND_DIRECTORY_CAPABILITY_PEPPER="replace-with-a-private-random-secret"
export DND_HOSTED_WARM_WORKERS=1
uv run uvicorn server.game_gateway:app --host 127.0.0.1 --port 8000 --workers 1
```

By default it stores cold directory data at
`.runtime/game-directory.sqlite3` and worker files under
`.runtime/hosted-games/`. Each active game runs in an isolated
`server.event_server:app` worker reached over a Unix-domain socket. The worker
imports the bundled native policy during prewarm and creates lightweight
per-side assignments after a game claims it. This retains process isolation
between games without nesting another Python interpreter for every AI side.

Registered-provider catalogs are process-local deployment state and are not
yet propagated by the gateway. Hosted creation therefore advertises the
native policies built into its worker composition and must not infer external
provider availability from configuration hints.

SQLite is used for identities, memberships, grants, attachments, game
lifecycle, immutable summaries, and rating evidence. It is not consulted while
proxying runtime HTTP or SSE traffic. Runtime authorization is installed in an
in-memory, game-scoped capability cache during attachment.

## Registered Policy Providers

The legacy player-session/self-HTTP AI workflow has been removed. An external
policy process now implements the closed registered-provider protocol and is
registered by deployment administration, never by impersonating a player or
redeeming a gameplay attachment.

The reference provider runs independently:

```bash
uv run python -m services.ai_policy_server
```

A standalone game server configured with
`DND_AI_PROVIDER_ADMIN_TOKEN` registers that provider through
`POST /admin/ai/providers` using deployment bearer authentication and the
exact `{provider_id, base_url}` request. Only handshake-authenticated policies
then appear in `/game-creation/catalog`; each game side owns one explicit
provider assignment and the server remains the authority for projection,
intent validation, execution, feedback, timing, and teardown.

Provider registration is currently a standalone-server capability. The
multi-game gateway must not advertise registered-provider policies until its
worker manifest and lifecycle propagation are implemented and tested.

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
