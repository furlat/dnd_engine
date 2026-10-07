# Headless player server

The service hosts independent encounters in exclusively leased Python workers. It exposes
authorized player values over HTTP and one SSE stream per attached seat. It does
not import the old `server/`, render assets, make rules decisions, or wait for
animations. `dnd/player` is the shared application, capture, projection and reducer
used by the desktop and headless clients.

## Start

From the repository, with its locked uv environment installed:

```sh
uv run --no-sync python -m player_server --port 8790
```

This starts the Lantern Crypt, controlling Fighter and Sorcerer through one
`Expedition` seat. A new local bearer credential is printed at launch. The server
binds to `127.0.0.1` unless `--host` is explicitly supplied. Ctrl+C closes its
owned workers. `/health` checks host liveness; authenticated `/api/v1/bootstrap` reports
whether the encounter is ready. `/docs` and `/openapi.json` describe the actual
routes and exported value types. Credentials never belong in URLs or source files.

When the server runs on Windows and the client runs in WSL's NAT network, bind
the server to Windows' WSL adapter address with `--host ADDRESS`; point the
client at that same address. Windows-only `127.0.0.1` does not expose the listener
on that adapter. Find the current address with PowerShell
`Get-NetIPAddress -AddressFamily IPv4` and use the entry for the WSL adapter.
The measured local setup uses `172.19.208.1`; it is machine-specific, not a server
default. No firewall change or public-interface binding is needed in this setup.

For configured encounters use `--config path/to/private-server.json`.
`player_server/config.py:ServerConfig` is the private launch schema. It accepts an
existing `encounter_id` or an authored `EncounterRecipe`, seat assignments and
distinct credentials. `test_seed` is optional private test configuration; normal
launch does not force test dice. `allowed_origins` is an explicit CORS allowlist.
TLS, credential issuance and a public lobby belong to deployment work; there is no public native-world or administrative endpoint.

The dedicated worker prepares its protocol identity, collects import-time garbage,
then freezes the pre-game object graph once before reading `Start`. This keeps
process-lifetime schemas out of repeated cyclic-GC scans. Normal garbage collection
stays enabled for subsequently created game objects; thresholds are unchanged.
Frozen cycles orphaned later can remain until that worker exits. Completed game
worlds are closed/reset/collected before the worker accepts another Start. Content
and completed schemas stay loaded; no game graph is frozen. The
policy belongs only to `run_process()`, never to the shared engine or in-process
session APIs. Startup measurements must include this preparation, and memory
measurements must include the frozen graph. See the
[performance receipt](../agent_docs/audits/server-implementation-20261007/PERFORMANCE.md).

## Successive and simultaneous games

`create_app(initial_config, limits=ServiceLimits(...))` owns a long-lived service.
Deployment code running on that application's event loop can use its **private
Python composition functions**:

```python
from player_server.app import create_app
from player_server.config import ServiceLimits
from player_server.service import end_game, start_game

app = create_app(initial_config, limits=ServiceLimits(max_workers=4, idle_workers=2))

# Later, inside the running service's event loop:
await end_game(app.state.player_service, initial_config.game_id)
next_host = start_game(app.state.player_service, next_config)
```

Natural terminal games retire automatically. Explicit `end_game` closes native
play without fabricating victory; it awaits retirement and keeps the exact old
public prefix available. An admitted command finishes when possible; uncertain
failure produces an indeterminate receipt. New games get new epochs, audiences,
actors, attachments and command counters. Old credentials remain scoped to their
original game, including while its replay is retained. Game IDs and credentials
must be distinct among active/retained games; issue fresh credentials for new games.
CORS is service-wide. This adds no public game-creation/admin endpoint.

A worker owns only one world at a time. Successful retirement acknowledges the
old epoch after cleanup before another Host may lease it. Concurrent games need
separate workers; additional capacity and failed-worker replacements pay cold
startup once. Idle retention avoids repeating imports, schema compilation and
content installation on subsequent games. Code/content deployment changes require
service replacement; hot reload is not supported.

`ServiceLimits` defaults to four workers, two idle workers, 64 active/retained
games and 64 GiB of reserved public recording capacity. All are configurable
operator budgets, not entity/seat limits. Reservation counts each game's configured
per-audience quota, even after native retirement, until history deletion succeeds.
Admission refuses unavailable capacity rather than deleting unexpired history.
Expired Hosts are reaped on the next admission. A game waiting for worker capacity
stays `starting`; ending it cancels that wait without constructing a world.

## Control, knowledge and AI

An assignment addresses existing `(roster_slot_id, member_id)` pairs:

```json
{
  "seat_id": "blue",
  "controlled": [["blue_party", "fighter"], ["blue_party", "sorcerer"]],
  "observers": null
}
```

Null `observers` means the controlled members. Explicit observer grants may include
other members of the same faction. Grants are validated before encounter creation.
Every human-controlled member has exactly one owner. AI is chosen through the
existing recipe controller defaults/overrides and remains native AI.

The same model supports one controller per side, one per unit, either side human
against AI, and mixed human/AI control on both sides. There is no numeric seat cap.
Faction is not ownership, and ownership is not automatic faction-wide sight.
One seat combines its authorized observers in one stream. Changing the selected
body cannot change that stream or grant the body another actor's range/senses.
Concrete working configurations are in
`devtools/player_server_acceptance/fixtures.py`.

## Protocol

The authoritative export is [sdk/protocol](../sdk/protocol/README.md): protocol 1,
player schema 4. Both SDKs validate the same digest and types. Transport operations,
disclosed event occurrence indices and native private history indices are distinct.
Native history indices never become public sequence counters.

1. Bootstrap with `Authorization: Bearer …`; retain game epoch and audience identity.
2. Acquire an attachment with a new acquisition UUID and the expected previous
   attachment epoch. Repeating that acquisition is safe; replacement invalidates
   the earlier attachment.
3. Consume initialization at sequence zero, then follow `/events?after=0`.
   `operation` events carry exact retained bytes and numbered cursors.
   `ready`, `status` and `error` events are unnumbered transport information.
4. ACK only after the consumer has accepted the complete record. SDK followers
   do this after the awaited callback. Catch up before submitting a new command.
5. Query native choices and previews using the current state revision. Keep the
   returned discovery generation, ordered target indices and position choices.
   The server never reconstructs a second path or spell targeting algorithm.
6. Submit the next command number. A pending receipt is not gameplay success.
   A committed receipt points to its public operation; `wait_for_cursor` /
   `waitForCursor` waits for consumer acceptance of that result.

If a command reply is lost, read its receipt or repeat **the identical numbered
request**. Never assume failure and submit it with a new number. Reusing a number
with different data is a conflict. An accepted but stale/illegal native command
gets a stable rejection receipt; malformed/unauthorized/busy admission does not
reserve a number. The SDK does not automatically retry gameplay commands.

Enemy sheets, private gear and unknown causal identities are withheld at native
projection. Known event-time names survive loss of sight and death. Logs carry
original typed rolls, modifiers and ordered child references; neither host nor SDK
rerolls or synthesizes mechanics. New permitted content descriptors arrive before
the shared reducer consumes facts referring to them.

## Bounds and failure behavior

- Requests: 256 KiB. One framed/public record: 64 MiB.
- Native command: one in flight. Queries, previews, receipts and delivery buffers
  have explicit entry/byte limits in their existing owners.
- Preview cache: 128 entries / 8 MiB. Host delivery credit: 128 MiB shared across
  catalog, queries and streamed chunks. Slow readers wait without holding the game
  mutation lock; exact public history remains on disk.
- Default spool quota: 1 GiB per audience. Capacity is checked before committing
  new work. Missing/truncated history returns `resume_unavailable`.
- Terminal history is retained for 24 hours while the host remains alive.
  Reconnecting rebuilds from initialization and exact records. **This is not
  whole-game save/load across server restarts.**

Native/capture faults fail the game with an opaque incident ID and private
diagnostics. The retained public prefix remains readable. Shutdown completes
accepted work when possible; forced shutdown reports indeterminate outcome instead
of pretending a command was rejected or saved.

## Independent clients and checks

See [Python SDK](../sdk/python/README.md),
[TypeScript SDK](../sdk/player-typescript/README.md), and the installed-package
drivers under `devtools/player_server_acceptance/`. The Python crypt driver uses
the same `dnd/player/reduction.py` as production; the SDK itself has no reducer.

```sh
uv run --no-sync python -m pytest -q tests/player
uv run --no-sync python -m devtools.player_server_acceptance.corpus --output .runtime/server-facts
```

The multi-process acceptance runner takes `--python` for an independently installed
Python SDK and `--node-client` for a directory containing the independently
installed npm package. It supports `two_sides`, `per_entity`, `human_vs_ai`,
`ai_vs_human`, `mixed`, `crypt`, and `--swap` for the opposing language assignment.
Its private credentials and large public recordings stay under ignored `.runtime`.
