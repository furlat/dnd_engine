"""Loopback MCP service with persistent Monty sessions and existing player SDK calls."""
import argparse
import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

from mcp.server import MCPServer
from pydantic_monty import AsyncMonty, AsyncMontySession, MontyCrashedError, MontyError, MontyRuntimeError

from monty_sandbox import player as game
from monty_sandbox import workspace
from monty_sandbox.observe import Observer, ignore, journal, summary
from monty_sandbox.toolkit import Toolkit, selected_sources, validate_bundle, validate_source


GUIDE = """Persistent agent workspace; no filesystem, network, or third-party imports.
Join games with join_game(session_id, seat); keep the returned game_ref explicitly.
All game functions require game_ref. There is no implicit current game.
  await game_list() -> {games: [{game_ref, seat, identity, mode, record_count}, ...]}
  await game_read(game_ref) -> status, cursor, audience, recording counts, recent commands, mode
  await game_events(game_ref, after=-1, limit=16) -> records, next_after, has_more
  await game_choices(game_ref, force_attack=False) -> schema-8 ChoicesResponse
  await game_preview(game_ref, actor_uuid, state_revision, discovery_generation, selection) -> schema-8 PreviewResponse
  await game_act(game_ref, actor_uuid, state_revision, intent) -> receipt, observation
  await game_receipt(game_ref) -> resolves that game's saved unresolved command
  await game_wait(game_ref, timeout_seconds=20) -> observation at our input/terminal boundary or timeout
Finished games can be archived with archive_game(session_id, game_ref). Their read/events
remain available offline; choices/preview/act/receipt/wait reject archived references.
Refs are local to this workspace, with native game_id + game_epoch + audience_id identity.
Choices contain entity_actions, position_actions, self_actions, object_actions.
Each action references choices['target_sets'][action['target_set']]. Each binding has kind
'subject', 'position' or 'self'. Subject bindings reference choices['subjects'][binding['subject']]
(uuid, kind, optional name). A binding's optional position references choices['positions'].
Read optional distance with binding.get('distance'); false path hazard and empty exposure
lists can also be omitted. Keep these shared values read-only; store selection state separately.
Use native discovery_index, target index, state_revision and discovery_generation unchanged.
Table offsets are lookups, never replacement target indexes. A primary's secondary_set
overrides its secondary pool; absent inherits the action pool, an explicit empty set has none.
Selection = {action_index: int, target_indices: [int, ...], extra_target_positions: []}.
Execute intent = {kind: 'execute_selection', discovery_generation: int, selection: selection}.
End-turn intent = {kind: 'end_turn'}. Other native intents remain supported.
Targets are ordered and may repeat. Preview reports can_confirm and next_target_set;
resolve preview['target_sets'][preview['next_target_set']] against Preview's own subjects
and positions. next_positions and affected_positions also index that Preview's positions,
including coordinates not present in Choices. Never resolve Preview offsets against Choices.
Optional AoE effects are deferred in Choices; Preview computes the selected subjective area.
A valid direct command needs no prior Preview; use Preview for compound selections or exact effects.
Raw world_updates contain full tiles and tile_changes. Apply each change to its known tile
in event order; omitted fields stay unchanged and explicit null clears a value.
Rediscover after state changes; do not reuse stale action indexes. Data is only this seat's view.
Only print output and the final expression enter model context. Filter large values in Python.
Variables/functions persist. Each execute needs a unique request_id; retry the SAME id and code
after transport failures, or use wait_execution. This never reruns an already accepted snippet.
Return JSON-compatible values. Monty is a Python subset: this version evaluates generator
expressions as lists, so use [item for item in items if condition][0] instead of next(...).
A failed snippet can already have acted. Inspect recent receipts before deciding what to do next.
Use execute(..., save_as='name') for source you explicitly want to reuse. Only a successful
execution saves its exact code. export_tools(session_id, names=[...]) exports selected sources
in that order. open_session(toolkit=bundle) loads them into a NEW empty workspace, without game
callbacks during import. No globals, records, receipts or connections are copied. Source may
itself contain data literals: inspect the bundle, and select dependencies explicitly.
Sessions outlive MCP reconnections, not service restarts. Closing a session or archiving a game
does not release that server seat for another client. A new match has a different epoch.
"""


@dataclass
class Execution:
    code: str
    save_as: str | None = None
    task: asyncio.Task | None = None
    started: float = field(default_factory=time.monotonic)
    stdout: str = ''
    stdout_truncated: bool = False
    host_calls: int = 0
    answer: dict | None = None


@dataclass
class Sandbox:
    monty: AsyncMontySession
    stack: AsyncExitStack
    label: str
    games: dict[str, workspace.GameEntry] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    runs: dict[str, Execution] = field(default_factory=dict)
    lifecycle: asyncio.Lock = field(default_factory=asyncio.Lock)
    broken: bool = False
    closed: bool = False


def require_idle(sandbox: Sandbox) -> None:
    if sandbox.closed or sandbox.broken:
        raise ValueError('Session is closed or unusable')
    if any(not run.task.done() for run in sandbox.runs.values()):
        raise ValueError('Session busy; wait for its existing execution')


async def execute_code(sandbox: Sandbox, run: Execution, observe: Observer = ignore) -> None:
    def printed(stream: str, text: str):
        remaining = 4000 - len(run.stdout)
        run.stdout += text[:remaining]
        run.stdout_truncated |= len(text) > remaining
        if remaining > 0:
            observe({'kind': 'stdout', 'text': text[:remaining]})

    def counted(name, fn):
        async def call(*args, **kwargs):
            run.host_calls += 1
            if run.host_calls > 128:
                raise ValueError('Host call budget reached for this execution')
            game_ref = kwargs.get('game_ref', args[0] if args else None)
            entry = sandbox.games.get(game_ref)
            context = {} if entry is None else {'game_ref': game_ref, 'seat': entry.seat}
            observe({**context, 'kind': 'host_call', 'name': name, 'args': args, 'kwargs': kwargs})
            try:
                result = await fn(*args, **kwargs)
            except Exception as error:
                observe({**context, 'kind': 'host_error', 'name': name, 'error': str(error)[:2000]})
                raise
            observe({**context, 'kind': 'host_result', 'name': name, 'result': summary(name, result)})
            return result
        return call

    callbacks = {name: counted(name, fn) for name, fn in workspace.callbacks(sandbox.games).items()}
    try:
        async with asyncio.timeout(45):
            value = await sandbox.monty.feed_run(run.code, external_lookup=callbacks, print_callback=printed)
        try:
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            run.answer = {'state': 'failed', 'error':
                'Final value is not JSON-compatible. Store it in the REPL and return a JSON-compatible selection.'}
            return
        run.answer = ({'state': 'completed', 'result': value, 'result_truncated': False}
            if len(encoded) <= 12000 else {'state': 'completed', 'result_preview': encoded[:12000],
                'result_truncated': True, 'hint': 'Value remains in REPL if assigned; return a smaller selection'})
        if run.save_as is not None:
            sandbox.sources[run.save_as] = run.code
            run.answer['saved_as'] = run.save_as
    except MontyRuntimeError as error:
        try:
            raise error.exception()
        except (MemoryError, TimeoutError):
            sandbox.broken = True  # Monty says discard after terminal resource failures.
        except Exception:
            pass
        run.answer = {'state': 'failed', 'error': str(error)[:4000]}
    except MontyCrashedError as error:
        sandbox.broken = True
        run.answer = {'state': 'failed', 'error': str(error)[:4000]}
    except MontyError as error:
        run.answer = {'state': 'failed', 'error': str(error)[:4000]}
    except Exception as error:
        sandbox.broken = True
        run.answer = {'state': 'failed', 'error': f'{type(error).__name__}: {str(error)[:4000]}'}
    finally:
        if run.answer is not None:
            run.answer.update(session_usable=not sandbox.broken, elapsed_seconds=round(time.monotonic()-run.started, 3))
            run.answer['recent_receipts'] = {ref: [row['receipt'] for row in entry.live.commands[-4:]]
                for ref, entry in sandbox.games.items() if entry.live is not None}
            observe({'kind': 'execution_done', 'answer': run.answer, 'host_calls': run.host_calls})


async def execution_result(run: Execution, request_id: str, wait_ms: int) -> dict:
    if not 0 <= wait_ms <= 10000:
        raise ValueError('wait_ms must be between 0 and 10000')
    if wait_ms:
        await asyncio.wait({run.task}, timeout=wait_ms / 1000)
    return {'request_id': request_id, **(run.answer or {'state': 'pending'}),
        'stdout': run.stdout, 'stdout_truncated': run.stdout_truncated, 'host_calls': run.host_calls}


def create_mcp(seats: dict[str, dict[str, str]], observe: Observer = ignore) -> MCPServer:
    sessions: dict[str, Sandbox] = {}
    opening = asyncio.Lock()
    pool: AsyncMonty | None = None

    async def close(sandbox: Sandbox):
        for run in sandbox.runs.values():
            if not run.task.done():
                run.task.cancel()
        await asyncio.gather(*(run.task for run in sandbox.runs.values()), return_exceptions=True)
        for entry in sandbox.games.values():
            if entry.live is not None:
                await game.close_player(entry.live)
        await sandbox.stack.aclose()

    @asynccontextmanager
    async def lifespan(server):
        nonlocal pool
        async with AsyncMonty(max_processes=4, request_timeout=10) as active_pool:
            pool = active_pool
            try:
                yield {}
            finally:
                for sandbox in sessions.values():
                    await close(sandbox)

    mcp = MCPServer('D&D Monty Sandbox', instructions=GUIDE, lifespan=lifespan)

    async def attach_game(sandbox: Sandbox, session_id: str, seat: str) -> dict:
        if seat not in seats or len(sandbox.games) >= 8:
            raise ValueError('Unknown seat or eight-game workspace capacity reached')
        game_ref = str(uuid4())
        def emit(event):
            observe({'agent': sandbox.label, 'seat': seat, 'session_id': session_id, 'game_ref': game_ref, **event})
        player = None
        try:
            player = await game.open_player(seats[seat]['url'], seats[seat]['credential'], emit)
            observation = await game.read_game(player)
            identity = {key: observation['status'][key] for key in ('game_id', 'game_epoch', 'audience_id')}
            entry = workspace.GameEntry(game_ref, seat, identity, player.packets, player)
            sandbox.games[game_ref] = entry
            observation.update(workspace.describe(entry))
            emit({'kind': 'game_joined', 'observation': observation})
            return {'game_ref': game_ref, 'observation': observation}
        except BaseException:
            if player is not None:
                await game.close_player(player)
            raise

    @mcp.tool()
    async def open_session(seat: str | None = None, toolkit: Toolkit | None = None) -> dict[str, Any]:
        """Create an empty agent REPL, optionally load explicit source tools, then optionally join a seat."""
        sources = validate_bundle(toolkit)
        session_id = str(uuid4())
        label = seat or 'agent-' + session_id[:8]

        def emit(event):
            observe({'agent': label, 'seat': seat, 'session_id': session_id, **event})

        emit({'kind': 'mcp_call', 'name': 'open_session'})
        async with opening:
            if len(sessions) >= 4:
                raise ValueError('Four-session trial capacity reached; close a session first')
            if seat is not None and seat not in seats:
                raise ValueError('Unknown configured seat')
            stack = AsyncExitStack()
            sandbox = None
            try:
                monty = await stack.enter_async_context(pool.checkout(limits={
                    'max_memory': 128 * 1024 * 1024, 'max_feed_duration_secs': 5,
                    'max_turn_duration_secs': 2, 'max_recursion_depth': 100,
                    'max_suspensions': 10000, 'max_total_sleep_secs': 5}))
                sandbox = Sandbox(monty, stack, label)
                async with asyncio.timeout(45):
                    for source in sources:
                        await monty.feed_run(source['code'], external_lookup={}, print_callback=lambda stream, text: None)
                        sandbox.sources[source['name']] = source['code']
                joined = {'game_ref': None, 'observation': None} if seat is None else await attach_game(sandbox, session_id, seat)
                observation = joined['observation']
                sessions[session_id] = sandbox
                emit({'kind': 'session_open', 'observation': observation})
                return {'session_id': session_id, 'seat': seat, 'guide': GUIDE,
                    'available_seats': list(seats), 'loaded_tools': list(sandbox.sources),
                    'games': [workspace.describe(entry) for entry in sandbox.games.values()], **joined}
            except BaseException:
                if sandbox is not None:
                    await close(sandbox)
                else:
                    await stack.aclose()
                raise

    @mcp.tool()
    async def join_game(session_id: str, seat: str) -> dict[str, Any]:
        """Attach another configured game/seat to the same agent REPL. Returns an explicit game_ref."""
        sandbox = sessions[session_id]
        async with sandbox.lifecycle:
            require_idle(sandbox)
            async with opening:
                observe({'kind': 'mcp_call', 'name': 'join_game', 'agent': sandbox.label,
                    'seat': seat, 'session_id': session_id})
                return await attach_game(sandbox, session_id, seat)

    @mcp.tool()
    async def archive_game(session_id: str, game_ref: str) -> dict[str, Any]:
        """Close a finished game's connection; retain its frozen observation and records for analysis."""
        sandbox = sessions[session_id]
        async with sandbox.lifecycle:
            require_idle(sandbox)
            entry = workspace.lookup(sandbox.games, game_ref)
            result = await workspace.archive(entry)
            observe({'kind': 'game_archived', 'agent': sandbox.label, 'seat': entry.seat,
                'session_id': session_id, 'game_ref': game_ref, 'observation': result})
            return result

    @mcp.tool()
    async def export_tools(session_id: str, names: list[str]) -> dict[str, Any]:
        """Export named, explicitly saved source blocks in the requested order. No heap or history."""
        sandbox = sessions[session_id]
        if sandbox.closed or sandbox.lifecycle.locked() or any(not run.task.done() for run in sandbox.runs.values()):
            raise ValueError('Session busy or closed; wait before exporting saved sources')
        result = selected_sources(sandbox.sources, names)
        observe({'kind': 'mcp_call', 'name': 'export_tools', 'agent': sandbox.label,
            'session_id': session_id, 'sources': names})
        return result

    @mcp.tool()
    async def execute(session_id: str, request_id: str, code: str, wait_ms: int = 1000,
                      save_as: str | None = None) -> dict[str, Any]:
        """Run Python in a persistent sandbox. Retry identical request_id/code safely; poll pending runs with wait_execution."""
        sandbox = sessions[session_id]
        def emit(event):
            observe({'agent': sandbox.label, 'session_id': session_id, 'request_id': request_id, **event})

        emit({'kind': 'mcp_call', 'name': 'execute', 'retry': request_id in sandbox.runs, 'code': code[:32768]})
        if request_id in sandbox.runs:
            run = sandbox.runs[request_id]
            if run.code != code or run.save_as != save_as:
                raise ValueError('request_id already used with different code or save_as')
            return await execution_result(run, request_id, wait_ms)
        if not request_id or len(request_id) > 128 or len(code) > 32768 or not 0 <= wait_ms <= 10000:
            raise ValueError('Invalid request id, code length, or wait_ms')
        require_idle(sandbox)
        if sandbox.lifecycle.locked():
            raise ValueError('Session is changing its game attachments')
        if save_as is not None:
            validate_source(save_as, code)
            if save_as not in sandbox.sources and len(sandbox.sources) >= 16:
                raise ValueError('Sixteen saved-source capacity reached')
        if len(sandbox.runs) >= 128:
            raise ValueError('Trial session execution budget reached')
        run = Execution(code, save_as=save_as)
        sandbox.runs[request_id] = run
        run.task = asyncio.create_task(execute_code(sandbox, run, emit), name=f'monty:{session_id}:{request_id}')
        return await execution_result(run, request_id, wait_ms)

    @mcp.tool()
    async def wait_execution(session_id: str, request_id: str, wait_ms: int = 1000) -> dict[str, Any]:
        """Read a submitted execution without rerunning it. Results survive MCP reconnects."""
        sandbox = sessions[session_id]
        observe({'kind': 'mcp_call', 'name': 'wait_execution', 'agent': sandbox.label,
            'session_id': session_id, 'request_id': request_id})
        return await execution_result(sandbox.runs[request_id], request_id, wait_ms)

    @mcp.tool()
    async def close_session(session_id: str) -> dict[str, Any]:
        """Close only this sandbox and its player connection. Already committed actions remain committed."""
        sandbox = sessions[session_id]
        async with sandbox.lifecycle:
            sandbox.closed = True
            sessions.pop(session_id)
            observe({'kind': 'mcp_call', 'name': 'close_session', 'agent': sandbox.label, 'session_id': session_id})
            await close(sandbox)
            observe({'kind': 'session_closed', 'agent': sandbox.label, 'session_id': session_id})
        return {'closed': session_id}

    return mcp


def main():
    parser = argparse.ArgumentParser(description='Loopback-only MCP/Monty player trial')
    parser.add_argument('--seats', type=Path, required=True, help='Private JSON mapping aliases to url and credential')
    parser.add_argument('--port', type=int, default=18892)
    parser.add_argument('--events', type=Path, help='New operator-only JSONL trace file')
    args = parser.parse_args()
    create_mcp(json.loads(args.seats.read_text()), ignore if args.events is None else journal(args.events)).run(transport='streamable-http',
        host='127.0.0.1', port=args.port, stateless_http=True, json_response=True)


if __name__ == '__main__':
    main()
