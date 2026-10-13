"""Temporary full-path host diagnostics for the owned gallery acceptance run.

The production host, worker protocol, recording and HTTP application still run.
All timing here includes diagnostic overhead; gallery's plain lane never imports
this module. No request bodies, credentials or public payloads are logged.
"""
import argparse
import asyncio
from collections import deque
from contextlib import ExitStack
from contextvars import ContextVar
import cProfile
import json
from pathlib import Path
import sys
from time import perf_counter_ns
from unittest.mock import patch

from pydantic import BaseModel, TypeAdapter

from devtools.player_server_acceptance import test_host
from server import app, connection, host, recording


async def run(args):
    directory = args.result.parent
    rows = []
    dropped = 0
    limit = 120_000
    request_context = ContextVar('movement_diagnostic_request', default=None)
    profile = None if args.coarse_timing else cProfile.Profile()

    def emit(label, started, **facts):
        nonlocal dropped
        if len(rows) < limit:
            rows.append({'name': label, 'start_ns': started, 'end_ns': perf_counter_ns(),
                'request': request_context.get(), **facts})
        else:
            dropped += 1

    original_exchange = connection.exchange
    async def exchange(process, request, spool):
        identity = {'kind': request.kind}
        if request.kind == 'command':
            identity['command_number'] = request.request.command_number
        token = request_context.set(identity)
        started = perf_counter_ns()
        try:
            result = await original_exchange(process, request, spool)
            emit('connection.exchange', started, worker_reported_ms=result[0].elapsed_ms,
                cursors=[row.cursor.model_dump(mode='json') for row in result[0].publications])
            return result
        finally:
            request_context.reset(token)

    async def launch():
        process = await asyncio.create_subprocess_exec(sys.executable, '-m',
            'devtools.player_server_acceptance.movement_profile_worker',
            '--output', str(directory), '--diagnostic-commands', args.diagnostic_commands,
            *(['--coarse-timing'] if args.coarse_timing else []),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        diagnostics = deque(maxlen=64)
        return connection.Connection(process, diagnostics,
            asyncio.create_task(connection._drain(process.stderr, diagnostics)))

    original_read = connection._read
    async def read(stream):
        started = perf_counter_ns()
        result = await original_read(stream)
        emit('connection.read_frame', started, bytes=len(result))
        return result

    original_host_exchange = host._exchange
    async def published_exchange(owner, request):
        identity = {'kind': request.kind}
        if request.kind == 'command':
            identity['command_number'] = request.request.command_number
        token = request_context.set(identity)
        started = perf_counter_ns()
        try:
            result = await original_host_exchange(owner, request)
            emit('host.exchange_through_publication', started,
                cursors=[row.cursor.model_dump(mode='json') for row in result[0].publications])
            return result
        finally:
            request_context.reset(token)

    original_submit = host.submit
    def submit(owner, seat, request):
        started = perf_counter_ns()
        result = original_submit(owner, seat, request)
        emit('host.submit_admission', started, command_number=request.command_number,
            receipt_kind=result.receipt.kind)
        return result

    original_receipt = host.store_receipt
    def store_receipt(seat, number, digest, value):
        started = perf_counter_ns()
        result = original_receipt(seat, number, digest, value)
        emit('host.store_receipt', started, command_number=number, kind=value.kind)
        return result

    original_stage = recording.stage_record
    def stage(spool, seat, sequence, payload):
        started = perf_counter_ns()
        result = original_stage(spool, seat, sequence, payload)
        emit('recording.stage_flush', started, seat=seat, sequence=sequence, bytes=len(payload))
        return result

    original_commit = recording.commit_records
    def commit(spool, staged):
        started = perf_counter_ns()
        result = original_commit(spool, staged)
        emit('recording.commit', started, audiences=len(staged),
            bytes=sum(value[1] for value in staged.values()))
        return result

    original_chunk = app.read_chunk
    def chunk(spool, seat, sequence, offset, size):
        started = perf_counter_ns()
        result = original_chunk(spool, seat, sequence, offset, size)
        emit('recording.read_stream_chunk', started, seat=seat, sequence=sequence,
            offset=offset, bytes=len(result))
        return result

    original_body = app.BoundedBody.__call__
    async def body(owner, scope, receive, send):
        if scope['type'] != 'http':
            return await original_body(owner, scope, receive, send)
        started = perf_counter_ns()
        # Existing URL structure is a safe route identity; omit query strings,
        # bodies and authorization headers entirely.
        path = scope['path']
        first_byte = None
        sent = 0
        received = 0
        async def measured_receive():
            nonlocal received
            message = await receive()
            if message['type'] == 'http.request':
                received += len(message.get('body', b''))
            return message
        async def measured_send(message):
            nonlocal first_byte, sent
            send_started = perf_counter_ns()
            await send(message)
            if message['type'] == 'http.response.body':
                sent += len(message.get('body', b''))
                if first_byte is None:
                    first_byte = perf_counter_ns()
                emit('http.send_body', send_started, path=path, bytes=len(message.get('body', b'')))
        try:
            return await original_body(owner, scope, measured_receive, measured_send)
        finally:
            emit('http.request', started, path=path, method=scope['method'],
                first_body_ns=first_byte, request_bytes=received, response_bytes=sent)

    original_json = BaseModel.model_dump_json
    def dump_json(model, *arguments, **keywords):
        started = perf_counter_ns()
        result = original_json(model, *arguments, **keywords)
        emit('model.dump_json', started, characters=len(result))
        return result

    original_adapter_dump = TypeAdapter.dump_json
    def adapter_dump(adapter, *arguments, **keywords):
        started = perf_counter_ns()
        result = original_adapter_dump(adapter, *arguments, **keywords)
        emit('type_adapter.dump_json', started, bytes=len(result))
        return result

    original_validate_json = BaseModel.model_validate_json.__func__
    def validate_json(cls, value, *arguments, **keywords):
        started = perf_counter_ns()
        result = original_validate_json(cls, value, *arguments, **keywords)
        emit('model.validate_json', started, input_size=len(value))
        return result

    args.worker_profile = None
    args.profile_census_after = 0
    with ExitStack() as patches:
        patches.enter_context(patch.object(connection, 'launch', launch))
        patches.enter_context(patch.object(connection, 'exchange', exchange))
        patches.enter_context(patch.object(connection, '_read', read))
        patches.enter_context(patch.object(connection, 'stage_record', stage))
        patches.enter_context(patch.object(host, '_exchange', published_exchange))
        patches.enter_context(patch.object(host, 'commit_records', commit))
        patches.enter_context(patch.object(host, 'submit', submit))
        patches.enter_context(patch.object(host, 'store_receipt', store_receipt))
        patches.enter_context(patch.object(app, 'read_chunk', chunk))
        patches.enter_context(patch.object(app.BoundedBody, '__call__', body))
        if not args.coarse_timing:
            patches.enter_context(patch.object(BaseModel, 'model_dump_json', dump_json))
            patches.enter_context(patch.object(BaseModel, 'model_validate_json', classmethod(validate_json)))
            patches.enter_context(patch.object(TypeAdapter, 'dump_json', adapter_dump))
        if profile is not None:
            profile.enable()
        try:
            await test_host.run(args)
        finally:
            if profile is not None:
                profile.disable()
    if profile is not None:
        profile.dump_stats(str(directory / 'host-route.pstats'))
    (directory / 'host-spans.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    (directory / 'host-diagnostics.json').write_text(json.dumps({
        'diagnostic': True, 'mode': 'coarse' if args.coarse_timing else 'full',
        'cprofile': profile is not None, 'rows': len(rows), 'dropped': dropped,
        'scope': ('Host explicit wall spans only; no cProfile or schema wrappers. Still instrumented. '
            if args.coarse_timing else 'Host whole-route CPU profile plus wall spans; includes schema wrappers. ')
            + 'Includes HTTP polling/streaming. Worker runs in another process. Inclusive async spans overlap; never sum them or use this run as speed evidence.',
        'not_instrumented': ['OS socket/pipe scheduling below Python',
            'thread-local cProfile in asyncio.to_thread (explicit recording spans cover wall time)'],
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--stop', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--diagnostic-commands', required=True)
    parser.add_argument('--coarse-timing', action='store_true')
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
