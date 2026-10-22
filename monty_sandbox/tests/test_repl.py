"""MCP-visible REPL behavior with real Monty workers; no game/network fixture."""
import asyncio
import json

from mcp import Client

from monty_sandbox.app import create_mcp
from monty_sandbox.observe import journal
from monty_sandbox.watch import View, consume, line_summary, render, snapshot, update
from rich.console import Console


async def call(client, name, **arguments):
    result = await client.call_tool(name, arguments)
    assert not result.is_error, result
    return result.structured_content


def test_persistence_isolation_and_retry_do_not_reexecute():
    async def check():
        async with Client(create_mcp({})) as client:
            one = (await call(client, 'open_session'))['session_id']
            two = (await call(client, 'open_session'))['session_id']
            await call(client, 'execute', session_id=one, request_id='init', code='counter = 40')
            first = await call(client, 'execute', session_id=one, request_id='increment', code='counter += 1\ncounter')
            retry = await call(client, 'execute', session_id=one, request_id='increment', code='counter += 1\ncounter')
            assert first['result'] == retry['result'] == 41
            changed = await client.call_tool('execute', {'session_id':one, 'request_id':'increment', 'code':'counter += 5'})
            assert changed.is_error
            isolated = await call(client, 'execute', session_id=two, request_id='read', code='counter')
            assert isolated['state'] == 'failed' and isolated['session_usable']
            assert 'NameError' in isolated['error']
            ordinary = await call(client, 'execute', session_id=one, request_id='raise', code="raise RuntimeError('try again')")
            assert ordinary['state'] == 'failed' and ordinary['session_usable']
            unsupported = await call(client, 'execute', session_id=one, request_id='set', code='{1, 2}')
            assert unsupported['state'] == 'failed' and unsupported['session_usable']
            value = await call(client, 'execute', session_id=one, request_id='later', code='counter')
            assert value['result'] == 41
    asyncio.run(check())


def test_pending_execution_can_be_polled_without_repeating():
    async def check():
        async with Client(create_mcp({})) as client:
            session = (await call(client, 'open_session'))['session_id']
            args = {'session_id':session, 'request_id':'sleep', 'code':"import asyncio\nawait asyncio.sleep(0.1)\n42", 'wait_ms':0}
            pending = await call(client, 'execute', **args)
            assert pending['state'] == 'pending'
            done = await call(client, 'wait_execution', session_id=session, request_id='sleep', wait_ms=1000)
            assert done['state'] == 'completed' and done['result'] == 42
    asyncio.run(check())


def test_scratch_has_no_file_or_game_access_and_loop_is_bounded():
    async def check():
        async with Client(create_mcp({})) as client:
            session = (await call(client, 'open_session'))['session_id']
            denied = await call(client, 'execute', session_id=session, request_id='game', code="await game_read('not-attached')")
            assert denied['state'] == 'failed' and 'Unknown game_ref' in denied['error']
            denied = await call(client, 'execute', session_id=session, request_id='file', code="open('/etc/passwd').read()")
            assert denied['state'] == 'failed'
            # A fresh session tests resource termination independently of unsupported I/O errors.
            other = (await call(client, 'open_session'))['session_id']
            source = 'def answer():\n    return 42'
            await call(client, 'execute', session_id=other, request_id='save', code=source, save_as='answer')
            loop = await call(client, 'execute', session_id=other, request_id='loop', code='while True:\n    pass', wait_ms=10000)
            assert loop['state'] == 'failed' and not loop['session_usable']
            rejected = await client.call_tool('execute', {'session_id':other,'request_id':'again','code':'42'})
            assert rejected.is_error
            bundle = await call(client, 'export_tools', session_id=other, names=['answer'])
            assert bundle['sources'] == [{'name':'answer', 'code':source}]
    asyncio.run(check())


def test_operator_can_replay_code_output_and_retries_without_reexecution(tmp_path):
    path = tmp_path / 'events.jsonl'
    async def check():
        async with Client(create_mcp({}, journal(path))) as client:
            session = (await call(client, 'open_session'))['session_id']
            arguments = dict(session_id=session, request_id='visible', code="print('hello' + ' operator')\n6 * 7")
            await call(client, 'execute', **arguments)
            await call(client, 'execute', **arguments)
    asyncio.run(check())
    events = [json.loads(line) for line in path.read_text().splitlines()]
    submitted = [row for row in events if row['kind'] == 'mcp_call' and row['name'] == 'execute']
    assert [row['retry'] for row in submitted] == [False, True]
    assert submitted[0]['code'] == "print('hello' + ' operator')\n6 * 7"
    assert len([row for row in events if row['kind'] == 'execution_done']) == 1
    view = View()
    with path.open() as source:
        consume(source, view)
    console = Console(width=140)
    with console.capture() as display:
        console.print(render(view, 'Replay', 'local'))
    assert 'hello operator' in display.get()
    assert '42' in display.get()
    assert 'saved execution' in display.get()
    snapshot(view, tmp_path, 'local')
    assert 'hello operator' in (tmp_path / 'dashboard.txt').read_text()
    assert 'hello operator' in (tmp_path / 'dashboard.html').read_text()


def test_operator_uses_each_games_controlled_actors_when_streams_interleave():
    view = View()
    for ref, actor in [('first', 'alice'), ('second', 'bob')]:
        update(view, {'kind':'game_joined', 'agent':'one-agent', 'seat':ref, 'game_ref':ref,
            'observation':{'audience':{'controlled':[actor]}}})
    update(view, {'kind':'record', 'agent':'one-agent', 'seat':'first', 'game_ref':'first',
        'boundary':{'lifecycle':'waiting_for_human', 'input_actor_uuid':'alice'},
        'cursor':{'sequence':3}, 'logs':[]})
    assert view.seats['one-agent']['status'] == 'YOUR TURN'
    assert view.seats['one-agent']['game_ref'] == 'first'
    assert 'one-agent' in line_summary({'kind':'stdout', 'agent':'one-agent', 'text':'hello'})


def test_operator_shows_current_codex_summon_control_without_changing_another_game():
    view = View()
    for ref, actor in [('first', 'alice'), ('second', 'bob')]:
        update(view, {'kind': 'game_joined', 'agent': 'one-agent', 'seat': ref, 'game_ref': ref,
            'observation': {'audience': {'controlled': [actor]}}})
    record = {'kind': 'record', 'agent': 'one-agent', 'seat': 'first', 'game_ref': 'first',
        'boundary': {'lifecycle': 'waiting_for_codex', 'input_actor_uuid': 'wolf'},
        'cursor': {'sequence': 3}, 'logs': []}
    update(view, {**record, 'audience': {'controlled': ['alice', 'wolf']}})
    assert view.seats['one-agent']['status'] == 'YOUR TURN'
    update(view, {**record, 'audience': {'controlled': ['alice']}})
    assert view.seats['one-agent']['status'] == 'waiting for opponent'
    update(view, {**record, 'game_ref': 'second', 'seat': 'second',
        'boundary': {'lifecycle': 'waiting_for_codex', 'input_actor_uuid': 'bob'}})
    assert view.seats['one-agent']['status'] == 'YOUR TURN'
    assert view.seats['one-agent']['controlled'] == ['bob']


def test_exported_sources_work_in_fresh_workspace_without_implicit_history():
    async def check():
        async with Client(create_mcp({})) as client:
            first = (await call(client, 'open_session'))['session_id']
            await call(client, 'execute', session_id=first, request_id='private',
                code="match_history = ['not-for-export']\nold_game_ref = 'old-match'")
            code = "FACTOR = 3\ndef project(values):\n    return [value * FACTOR for value in values]"
            saved = await call(client, 'execute', session_id=first, request_id='tools', code=code, save_as='projection')
            assert saved['saved_as'] == 'projection'
            failed = await call(client, 'execute', session_id=first, request_id='bad-source',
                code="raise ValueError('not saved')", save_as='broken')
            assert failed['state'] == 'failed'
            assert (await client.call_tool('export_tools', {'session_id':first, 'names':['broken']})).is_error
            bundle = await call(client, 'export_tools', session_id=first, names=['projection'])
            assert bundle['sources'] == [{'name':'projection', 'code':code}]
            assert 'not-for-export' not in json.dumps(bundle)
            fresh = await call(client, 'open_session', toolkit=bundle)
            assert fresh['games'] == [] and fresh['loaded_tools'] == ['projection']
            result = await call(client, 'execute', session_id=fresh['session_id'], request_id='use',
                code="{'result':project([2,4]), 'games':await game_list()}")
            assert result['result'] == {'result':[6,12], 'games':{'games':[]}}
            for name in ('match_history', 'old_game_ref'):
                missing = await call(client, 'execute', session_id=fresh['session_id'], request_id=name, code=name)
                assert missing['state'] == 'failed' and 'NameError' in missing['error']
            denied = await call(client, 'execute', session_id=fresh['session_id'], request_id='old-ref',
                code="await game_act('old-match', 'actor', 'revision', {'kind':'end_turn'})")
            assert denied['state'] == 'failed' and 'Unknown game_ref' in denied['error']
            # Import has no callbacks, even if source tries to inspect games at top level.
            for _ in range(3):
                invalid = await client.call_tool('open_session', {'toolkit':{'format':'monty-tools-v1',
                    'sources':[{'name':'action-at-import', 'code':'await game_list()'}]}})
                assert invalid.is_error
            # Failed imports released their workers/session capacity.
            another = await call(client, 'open_session', toolkit=bundle)
            assert another['games'] == []
    asyncio.run(check())
