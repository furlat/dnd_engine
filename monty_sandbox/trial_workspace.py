"""Live acceptance: two native matches, one agent REPL, then a history-free toolkit import."""
import argparse
import asyncio
from contextlib import ExitStack
import json
from pathlib import Path
import signal
import socket
import sys

from mcp import Client

from monty_sandbox.cli import ROOT, ready


async def stop_child(child):
    if child.returncode is None:
        child.send_signal(signal.SIGINT)
        try:
            await asyncio.wait_for(child.wait(), timeout=10)
        except TimeoutError:
            child.kill()
            await child.wait()


async def trial(directory: Path, base_port: int) -> None:
    directory = directory.resolve()
    for port in range(base_port, base_port + 3):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', port))
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    children = []
    seats = {}
    endpoint = f'http://127.0.0.1:{base_port + 2}/mcp'
    stop = asyncio.Event()
    with ExitStack() as files:
        transcript = files.enter_context((directory / 'mcp-transcript.jsonl').open('w'))
        try:
            for index, seed in enumerate((2, 7)):
                folder = directory / f'game-{index + 1}'
                prepare = await asyncio.create_subprocess_exec(str(ROOT / '.venv/bin/python'), '-m',
                    'monty_sandbox.prepare_trial', '--output', str(folder),
                    '--game-port', str(base_port + index), '--seed', str(seed), cwd=ROOT)
                if await prepare.wait():
                    raise RuntimeError('Fixture preparation failed')
                seats[f'game-{index + 1}'] = json.loads((folder / 'seats.json').read_text())['amber']
                log = files.enter_context((folder / 'game.log').open('w'))
                child = await asyncio.create_subprocess_exec(str(ROOT / '.venv/bin/python'), '-m',
                    'server', '--config', str(folder / 'game.json'), '--port', str(base_port + index),
                    cwd=ROOT, stdout=log, stderr=log)
                children.append(child)
                await ready(child, f'http://127.0.0.1:{base_port + index}/health', folder / 'game.log', stop)
            config = directory / 'seats.json'
            config.touch(mode=0o600)
            config.write_text(json.dumps(seats))
            log = files.enter_context((directory / 'mcp.log').open('w'))
            mcp = await asyncio.create_subprocess_exec(sys.executable, '-m', 'monty_sandbox.app',
                '--seats', str(config), '--port', str(base_port + 2), '--events', str(directory / 'events.jsonl'),
                cwd=ROOT, stdout=log, stderr=log)
            children.append(mcp)
            (directory / 'arena.json').write_text(json.dumps({'mcp_url':endpoint, 'seats':list(seats),
                'game_ports':[base_port, base_port + 1], 'mcp_port':base_port + 2, 'pids':[child.pid for child in children]}, indent=2))
            await ready(mcp, endpoint, directory / 'mcp.log', stop, 'OPTIONS')

            async with Client(endpoint, read_timeout_seconds=70) as client:
                async def call(name, **arguments):
                    response = await client.call_tool(name, arguments)
                    transcript.write(json.dumps({'tool':name, 'arguments':arguments,
                        'is_error':response.is_error, 'result':response.structured_content}) + '\n')
                    transcript.flush()
                    assert not response.is_error, response
                    return response.structured_content

                async def execute(session, request_id, code, *, failed=False, save_as=None):
                    answer = await call('execute', session_id=session, request_id=request_id,
                        code=code, save_as=save_as, wait_ms=10000)
                    while answer['state'] == 'pending':
                        answer = await call('wait_execution', session_id=session, request_id=request_id, wait_ms=10000)
                    assert answer['state'] == ('failed' if failed else 'completed'), answer
                    return answer

                session = (await call('open_session'))['session_id']
                source = (ROOT / 'monty_sandbox/examples/scouts.py').read_text()
                await execute(session, 'install-tools', source, save_as='scouts')
                await execute(session, 'private-memory',
                    "workspace_token = 'PRIVATE_MATCH_MEMORY_ONLY'\nagent_notes = []\ngame_refs = {}")
                reports = []
                archived_rejections = []
                for index in range(2):
                    alias = f'game-{index + 1}'
                    joined = await call('join_game', session_id=session, seat=alias)
                    ref = joined['game_ref']
                    await execute(session, f'remember-{index}',
                        f"game_refs[{alias!r}] = {ref!r}\nassert workspace_token == 'PRIVATE_MATCH_MEMORY_ONLY'\nassert len(agent_notes) == {index}")
                    if index:
                        first = reports[0]['game_ref']
                        old = await execute(session, 'read-old-during-new', f'await game_summary({first!r})')
                        assert old['result']['identity'] == reports[0]['identity']
                        assert old['result']['mode'] == 'archived'
                        denied = await execute(session, 'old-cannot-act',
                            f"await game_act({first!r}, 'old-actor', 'old-revision', {{'kind':'end_turn'}})", failed=True)
                        assert 'Archived game' in denied['error']
                        archived_rejections.append(denied['error'])
                    commands = 0
                    for batch in range(8):
                        answer = await execute(session, f'play-{index}-{batch}', f'await play_steps({ref!r}, 12)')
                        result = answer['result']
                        commands += sum(step['receipt'] == 'committed' for step in result['steps'])
                        if result['game']['boundary']['lifecycle'] == 'terminal':
                            break
                    assert result['game']['boundary']['lifecycle'] == 'terminal', result
                    await execute(session, f'note-{index}', f"agent_notes.append({{'game':{ref!r}, 'commands':{commands}}})")
                    archived = await call('archive_game', session_id=session, game_ref=ref)
                    assert archived['mode'] == 'archived'
                    await stop_child(children[index])
                    # Archive remains usable after the native server is gone.
                    report = (await execute(session, f'offline-{index}', f'await game_summary({ref!r})'))['result']
                    report['committed_commands'] = commands
                    reports.append(report)
                    print(json.dumps({'finished':alias, 'session_id':session, 'game_ref':ref,
                        'cursor':report['cursor']['sequence'], 'commands':commands, 'offline_history_read':True}), flush=True)
                assert reports[0]['identity']['game_id'] == reports[1]['identity']['game_id']
                assert reports[0]['identity']['game_epoch'] != reports[1]['identity']['game_epoch']
                memory = (await execute(session, 'compare-games',
                    "{'token':workspace_token, 'notes':agent_notes, 'games':await game_list(), "
                    "'reports':[await game_summary(ref) for ref in game_refs.values()]}"))['result']
                assert len(memory['games']['games']) == len(memory['notes']) == 2
                assert all(row['mode'] == 'archived' for row in memory['games']['games'])
                bundle = await call('export_tools', session_id=session, names=['scouts'])
                serialized = json.dumps(bundle, indent=2)
                assert 'PRIVATE_MATCH_MEMORY_ONLY' not in serialized
                assert all(row['game_ref'] not in serialized for row in reports)
                (directory / 'toolkit.json').write_text(serialized + '\n')
                await call('close_session', session_id=session)

                fresh = await call('open_session', toolkit=bundle)
                assert fresh['games'] == [] and fresh['session_id'] != session
                clean = (await execute(fresh['session_id'], 'use-tools',
                    "{'feature_result':combat_summary([]), 'games':await game_list()}"))['result']
                assert clean == {'feature_result':{'attacks':[], 'deaths':[]}, 'games':{'games':[]}}
                for variable in ('workspace_token', 'agent_notes', 'game_refs'):
                    missing = await execute(fresh['session_id'], 'no-' + variable, variable, failed=True)
                    assert 'NameError' in missing['error']
                for index, report in enumerate(reports):
                    denied = await execute(fresh['session_id'], f'foreign-{index}',
                        f"await game_summary({report['game_ref']!r})", failed=True)
                    assert 'Unknown game_ref' in denied['error']
                denied = await execute(fresh['session_id'], 'no-old-actions',
                    f"await game_act({reports[0]['game_ref']!r}, 'actor', 'revision', {{'kind':'end_turn'}})", failed=True)
                assert 'Unknown game_ref' in denied['error']
                # The restored helper also processes new caller-supplied data, without a game.
                synthetic = [{'lineages':[], 'combat_log_appends':[{'entry':{'entry_type':'attack', 'compact':'Fresh sample attack'}}]}]
                fresh_feature = (await execute(fresh['session_id'], 'new-data',
                    f'combat_summary({synthetic!r})'))['result']
                assert fresh_feature == {'attacks':['Fresh sample attack'], 'deaths':[]}
                final = (await execute(fresh['session_id'], 'still-clean', 'await game_list()'))['result']
                assert final == {'games':[]}
                await call('close_session', session_id=fresh['session_id'])
                proof = {'source_session':session, 'fresh_session':fresh['session_id'], 'games':reports,
                    'same_sandbox_across_games':True, 'same_native_game_id_different_epochs':True,
                    'archives_read_after_servers_stopped':True, 'archived_actions_rejected':bool(archived_rejections),
                    'source_session_closed_before_import':True, 'exported_sources':fresh['loaded_tools'],
                    'fresh_games':[], 'unsaved_globals_absent':True, 'real_old_refs_rejected':True,
                    'restored_feature_result':fresh_feature, 'game_server_changes':False}
                (directory / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
                print(json.dumps(proof, indent=2), flush=True)
        finally:
            for child in reversed(children):
                await stop_child(child)
            print('All owned trial services stopped.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/monty-workspace-trial')
    parser.add_argument('--base-port', type=int, default=18911)
    args = parser.parse_args()
    asyncio.run(trial(args.output, args.base_port))


if __name__ == '__main__':
    main()
