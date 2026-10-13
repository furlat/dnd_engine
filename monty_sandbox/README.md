# Monty sandbox

A local MCP client for the existing player server. Each agent session owns a persistent
Monty REPL and can attach to several configured games using the normal SDK and HTTP/SSE
stream. Every game operation takes an explicit workspace-local `game_ref`. Python can
inspect records, keep helpers and state, and perform several actions in one MCP call.
The server remains authoritative for choices, previews, revisions, commands and receipts.
There are no game-server changes.

The first live trial controlled both Amber scouts against the native Blue AI and
won: three commands committed, stream terminal at sequence 11. This small seeded
fight demonstrates the connection and execution path, not general playing strength.
See [recorded evidence](evidence/trial.json) and the
[agent-authored REPL policy](examples/scouts.py).

The workspace trial reused **one sandbox across two complete games**, archived both,
and queried their records after their servers stopped. It then exported the selected
helper source, closed the original sandbox, and loaded the source into a fresh sandbox
with no games or unsaved globals. See [proof](evidence/workspace/proof.json) and the
actual portable [toolkit](evidence/workspace/toolkit.json).

## One agent, several games, portable tools

`open_session()` creates an empty agent workspace. `join_game(session_id, seat)` attaches
a configured seat and returns its `game_ref`. Store references under names you choose
in the REPL. Each entry also exposes native `game_id`, `game_epoch` and `audience_id`,
so even matches with the same game ID stay distinct. There is no implicit current game.

An agent can write and revise arbitrary helpers during play. To make a source block
portable, submit it through `execute` with `save_as="scouts"`. For example, submit
[examples/scouts.py](examples/scouts.py) as `code`, then use separate executions for:

```python
# Supply the exact reference returned by join_game; this variable is your own state.
first_game = "<returned game_ref>"
await play_steps(first_game, 12)
```

After a game finishes, call `archive_game(session_id, game_ref)` while its server is
still reachable. This closes that connection and retains its observation and authorized
records in the workspace. `game_read` and `game_events` continue working offline;
action/discovery/wait callbacks reject archived references. Join another game in the
same session, retain its reference separately, and reuse your functions. For example:

```python
old_report = await game_summary(first_game)
new_report = await game_summary(second_game)
{'previous': old_report, 'ongoing': new_report}
```

Export with `export_tools(session_id, names=["scouts"])`. The returned JSON bundle is:

```json
{"format":"monty-tools-v1","sources":[{"name":"scouts","code":"<exact saved Python source>"}]}
```

Save that JSON outside Monty and pass it to `open_session(toolkit=bundle)` to load a
fresh workspace. Sources run in the requested order, without game callbacks during
import and before any optional seat attachment. The fresh workspace has no game
history, receipts, live connections, or globals from the old workspace. Functions and
configuration defined by the selected source are recreated. The same toolkit can be
loaded again after restarting the MCP service.

This exports the last successfully saved source for each selected name; it does not
extract the current heap or discover dependencies. Select required blocks in dependency
order. Include reusable configuration in the source, and keep match notes in separate
executions. Source literals are copied verbatim, including any history an agent explicitly
wrote into that source. Failed executions do not replace saved source; already saved
blocks remain exportable after a Monty resource failure. The sample policy is optional
agent code, not a rule imposed by the host.

## Watch two agents play

From the repository root, after the dependency setup below:

```sh
./monty_sandbox/arena run
```

This starts a fresh game on **18893**, MCP on **18894**, and an Amber/Blue terminal
display. The duel uses one native skeleton per side, both externally controlled.
Each agent connects to `http://127.0.0.1:18894/mcp` and opens its own seat (`amber`
or `blue`). The CLI runs the services and observes the match; the agents are MCP
clients supplied separately. It does not launch model subscriptions or API jobs.

The display shows each side's turn status, MCP/host-call counts, committed commands,
latest submitted Python, printed output, results and combat narration. Full submitted
code and bounded results are retained in the operator journal. Maximize the terminal
to see both columns comfortably. `--plain` gives an append-only text feed instead.

Useful options:

```sh
./monty_sandbox/arena run --game-port 18903 --mcp-port 18904 --seed 7
./monty_sandbox/arena watch .runtime/monty-arena-RUN --once
./monty_sandbox/arena watch .runtime/monty-arena-RUN
```

`run` prints its private run directory; `--output PATH` chooses a new one explicitly.
Ctrl-C stops only the two services that command created. Occupied ports and existing
run directories are refused. `watch` reads an existing journal and never sends game
commands; Ctrl-C only closes that viewer. `--once` renders the saved view and exits.
On exit the viewer also writes `dashboard.html`, `dashboard.svg` and `dashboard.txt`. The underlying
`events.jsonl` replays the operator display, not a complete native game state.

The combined view is operator-only. Each Monty session still receives only its
own authorized game stream. There is no extra spectator attachment. This remains
a trusted local service: the seat aliases are not separate authentication accounts.

The recorded agent-vs-agent rematch reached terminal cursor **21**: Amber won,
and each agent committed **seven commands**. Blue fired, moved into melee and
used its sword; Amber switched from bow to sword. Both sides chose actions through
independent MCP/Monty sessions. Replay that operator trace with:

```sh
./monty_sandbox/arena watch monty_sandbox/evidence/duel --once
```

See [duel evidence](evidence/duel/summary.json). An earlier goblin duel ended on
Amber's first hit before Blue could act, so the visible rematch uses the sturdier
native skeleton recipe. These are demonstrations, not a performance benchmark.

## Run locally

Run these commands from the repository root in WSL/Linux. Dependencies stay in two
separate virtual environments. The preparation command refuses an existing output
directory and creates private credentials for a new match.

```sh
uv sync --locked --compile-bytecode
uv sync --project monty_sandbox --locked --compile-bytecode
.venv/bin/python -m monty_sandbox.prepare_trial
```

After updating the engine/player protocol, refresh the sandbox's installed SDK
explicitly; it is a local package installation, not an editable source import:

```sh
uv sync --project monty_sandbox --locked --reinstall-package dnd-player-sdk
```

Restart the game and MCP processes together after updating. Current code uses
player schema 8; an older SDK is rejected by the protocol handshake. Load the
updated `examples/scouts.py` into a fresh workspace. Previously exported source
that reads `valid_targets` or `next_targets` must be migrated before reuse; loading
old source does not rewrite it. Historical evidence folders remain old recordings.

Start the game in one terminal and MCP in another:

```sh
.venv/bin/python -m server --config .runtime/monty-player-demo/game.json --port 18891
```

```sh
monty_sandbox/.venv/bin/python -m monty_sandbox.app \
  --seats .runtime/monty-player-demo/seats.json --port 18892
```

The MCP endpoint is `http://127.0.0.1:18892/mcp` (Streamable HTTP). It uses the
existing game socket at `http://127.0.0.1:18891`; Monty itself has no network access.
Choose other unused ports if needed; pass the game port to `prepare_trial` too.
Use Ctrl-C in those terminals to stop only these processes.

List tools or open a player REPL from a third terminal:

```sh
monty_sandbox/.venv/bin/python -m monty_sandbox.call list
monty_sandbox/.venv/bin/python -m monty_sandbox.call open_session <<'JSON'
{"seat":"amber"}
JSON
```

Use the returned `session_id` with `execute`, and keep its `game_ref`. Submit
`examples/scouts.py` as `code` with `save_as="scouts"`, then call
`await play_steps("<returned game_ref>", 12)` in another execution. Later calls can
inspect `await game_summary("<returned game_ref>")` or run another batch. Always give
a new snippet a new `request_id`.
If a response is pending, call `wait_execution` with the same session and request.
The `call` helper reads JSON arguments from stdin and makes a real network MCP call;
sessions survive its connection closing.

## MCP tools

| Tool | Arguments | Result |
| --- | --- | --- |
| `open_session` | `seat: string \| null = null`, `toolkit: Toolkit \| null = null` | `session_id`, `seat`, `guide`, configured `available_seats`, `loaded_tools`, `games`, `game_ref` and initial `observation` (last two null without a seat) |
| `join_game` | `session_id`, `seat` | `game_ref`, initial `observation` including native identity and workspace metadata |
| `archive_game` | `session_id`, `game_ref` | Frozen observation with `mode: "archived"`; repeated archive returns the same retained state |
| `export_tools` | `session_id`, `names: list[string]` | `Toolkit`: `{format: "monty-tools-v1", sources: [{name, code}, ...]}` in requested order |
| `execute` | `session_id`, `request_id`, `code`, `wait_ms: int = 1000`, `save_as: string \| null = null` | `request_id`, `state`, bounded `stdout`, `stdout_truncated`, `host_calls`; completed: `result` or `result_preview`, `result_truncated`, optional `saved_as`; failed: `error`; finished: `session_usable`, `elapsed_seconds`, and `recent_receipts` keyed by live `game_ref` |
| `wait_execution` | `session_id`, `request_id`, `wait_ms: int = 1000` | Same execution envelope, without running code again |
| `close_session` | `session_id` | `{closed: session_id}` |

`state` is `pending`, `completed` or `failed`. Invalid tool arguments or session
operations are MCP errors. Snippet errors are execution results. Reusing a request
ID with identical code and `save_as` returns the saved execution; changing either is rejected.
One snippet runs at a time per session; different sessions can run concurrently.
Join/archive operations require an idle usable session. Export requires an idle session
but does not require Monty to remain usable. Closing a session drops all of its retained
games and unsaved state. An exported bundle remains usable independently.

## Functions inside the agent REPL

| Function | Returns |
| --- | --- |
| `await game_list()` | `{games: [{game_ref, seat, identity, mode, record_count}, ...]}` |
| `await game_read(game_ref)` | Native status, consumed cursor, audience, record count/bytes, recent commands and any unresolved command; plus workspace metadata |
| `await game_events(game_ref, after=-1, limit=16)` | Native records, `game_ref`, `next_after`, `has_more`; maximum 64 records per call |
| `await game_choices(game_ref, force_attack=False)` | Schema-8 choices response for that game's current controlled actor |
| `await game_preview(game_ref, actor_uuid, state_revision, discovery_generation, selection)` | Schema-8 preview response with its own lookup domains |
| `await game_act(game_ref, actor_uuid, state_revision, intent)` | Settled command receipt and observation |
| `await game_receipt(game_ref)` | Resolves that game's saved unresolved command using its original number and payload |
| `await game_wait(game_ref, timeout_seconds=20)` | Observation at this seat's input/terminal boundary, plus `wait_timed_out` |

Use native discovery indexes and target indexes unchanged. Use Preview for
compound selection or exact effects; direct commands do not require a prior
Preview. Rediscover after state changes. A snippet can fail after
committing an action: inspect receipts before deciding what to do next. Ambiguous
commands remain saved outside Monty and block new actions until resolved.

Large stream values stay in the host/REPL until the snippet explicitly returns or
prints them. This prototype offers raw records and native choices, with no state
reducer. The sample filters combat logs and chooses actions inside Monty. It does
not invoke nested language models.

Choices share lookup tables; Monty can index the admitted dictionaries directly:

```python
options = choices['target_sets'][action['target_set']]
target = options[0]
if target['kind'] == 'subject':
    subject = choices['subjects'][target['subject']]  # uuid, kind, optional name
if target.get('position') is not None:
    position = choices['positions'][target['position']]
selection = {'action_index': action['discovery_index'],
    'target_indices': [target['index']], 'extra_target_positions': []}
```

Binding kinds are `subject`, `position` and `self`. Table offsets are not native
selection indexes. Pair fields such as distance may be omitted; use
`target.get('distance')`. Keep shared values read-only and retain local UI/policy
state separately. A primary binding's `secondary_set` overrides its secondary
pool; absence inherits the action's set, while an explicit empty set has no
secondary options. Individual membership does not prove that a compound prefix
is legal.

Every Preview has its own `subjects`, `positions` and `target_sets`. Resolve
`next_target_set`, `next_positions` and `affected_positions` against that Preview,
including newly offered landing/path coordinates. Retain target order and
repeats when submitting a selection. Optional AoE effects are `deferred` in
Choices; a selected Preview returns `computed` subjective effects, which may be
empty. See the [complete protocol handoff](../sdk/protocol/README.md) for geometry
prediction, recipient limits, movement and stale-response rules.

Raw event records also include ordered `world_updates[].tile_changes`: update
only the supplied fields on each already-known tile. Omitted fields retain
their values; explicit null clears one. Apply these alongside full `tiles` in
event order. The sandbox forwards those records unchanged and adds no reducer.

## Bounds and current limitations

This endpoint is for trusted local clients, binds loopback, and has no MCP auth.
Separate clients have isolated REPL globals but share the endpoint's configured
seat aliases; this is not a tenant authorization boundary. Server credentials stay
in the host and never enter Monty. A claimed seat cannot be opened twice, and the
client refuses to replace an existing server attachment. Closing a session does
not detach the seat on the current server; use a fresh match for another trial.

At most four sessions, eight game entries per session (including archives), 16 saved
source blocks per session (up to 32,768 characters each), 128 executions per session,
one active execution per session, 128 host calls per execution, 128 MiB Monty memory,
64 MiB buffered stream per game attachment.
Monty has a 2-second turn/5-second feed execution budget; the complete host operation
has a 45-second timeout. Returned text is bounded (4,000 printed characters and
12,000 characters of serialized result). Resource failures can require closing a
session. Live workspace/history state does not persist across service restarts; exported
source is portable. Archive while the finished server remains reachable. Recovery of
a failed stream into an archive is not implemented.

Monty supports a Python subset. In the version used here, generator expressions
evaluated as lists: `next(x for x in values if ...)` failed. Use a list comprehension
and indexing instead. Return JSON-compatible values; retain other values in globals
and return a smaller projection. No file access or arbitrary imports are exposed.

## Validation

Schema-8 refresh (2026-10-13): all nine sandbox tests pass. The existing real
two-game workspace trial also passes using the installed SDK and updated scout
source: 16 committed commands, 48 records, both matches terminal, offline archive
reads and history-free helper export/import preserved. Its local evidence is in
`.runtime/monty-schema8-workspace/proof.json`; the checked-in older demonstration
captures below remain historical.

```sh
uv run --project monty_sandbox --no-sync python -m pytest monty_sandbox/tests -q
```

Tests use real Monty workers through MCP to exercise persistence, isolation,
idempotent execution, pending-result polling, recoverable errors, denied file/game
access in scratch sessions, bounded runaway execution, source export after failure,
fresh import without implicit history or callbacks, failed-import cleanup, and operator
display correctness when games interleave. Native SDK HTTP tests cover ambiguous
command retries followed by definite rejection, and waiting when stream status lags
the authoritative turn. The original separate live match
also checked transport reconnects, two simultaneous clients, duplicate-seat refusal
and replaying the exact attack request without another game command.

Reproduce the two-game workspace/export trial (two native servers plus MCP, automatically
stopped afterward; occupied ports and existing output directories are refused):

```sh
uv run --project monty_sandbox --no-sync python -m monty_sandbox.trial_workspace \
  --output .runtime/my-workspace-trial --base-port 18911
./monty_sandbox/arena watch .runtime/my-workspace-trial --once
```

The saved [workspace proof](evidence/workspace/proof.json) records terminal cursors 11
and 35, with 3 and 13 committed commands. Both games used the same native game ID but
different epochs. The trial read game one's archived history while game two was live,
queried both after stopping their servers, rejected archived actions, then closed the
source session before importing its tools into an empty sandbox. Both real old game
references and unsaved globals were rejected there, while the restored combat helper
processed new caller-supplied data. Replay the operator journal with:

```sh
./monty_sandbox/arena watch monty_sandbox/evidence/workspace --once
```

Earlier trial/duel journals preserve their original one-game callback signatures as
historical evidence. The tables and example source above describe the current API.
