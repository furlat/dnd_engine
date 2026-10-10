"""Finite real-service reuse cohort; existing standalone SDK clients and replay files."""
import argparse
import asyncio
import ctypes
from ctypes import wintypes
import json
from hashlib import sha256
import os
from pathlib import Path
import statistics
import sys
from time import perf_counter

import uvicorn

from devtools.player_server_acceptance.fixtures import combat_configuration, configuration
from server.app import create_app
from server import service


def resident_bytes(pid):
    if os.name != 'nt':
        return int(Path(f'/proc/{pid}/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
            ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
            ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
            ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
            ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    handle = kernel.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        value = Counters()
        value.cb = ctypes.sizeof(value)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(value), value.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.WorkingSetSize
    finally:
        kernel.CloseHandle(handle)


async def wait_ready(host):
    async with asyncio.timeout(60):
        async with host.changed:
            await host.changed.wait_for(lambda: host.failure is not None or any(
                seat.publication is not None and seat.publication.boundary.input_actor_uuid is not None
                for seat in host.seats.values()))
    if host.failure is not None:
        raise RuntimeError(f'Game failed at startup: {host.failure}')


async def clients(root, config, url, combat_case):
    config_path = root / 'server.json'
    config_path.write_text(config.model_dump_json(indent=2))
    jobs, logs = [], []
    try:
        for mode in ('monitor', 'client'):
            log = (root / f'{mode}.log').open('wb')
            logs.append(log)
            jobs.append(await asyncio.create_subprocess_exec(sys.executable, '-m',
                'devtools.player_server_acceptance.http_performance', mode, '--url', url,
                '--config', str(config_path), '--output', str(root), '--commands', '200' if combat_case else '2',
                *(['--combat-case', combat_case] if combat_case else []), stdout=log, stderr=log))
        async with asyncio.timeout(240):
            codes = await asyncio.gather(*(job.wait() for job in jobs))
        if any(codes):
            raise RuntimeError(f'SDK cohort failed: {codes}; {root}')
        return json.loads((root / 'result.json').read_text())
    finally:
        (root / 'monitor.stop').touch()
        (root / 'monitor.start').touch()
        for job in jobs:
            if job.returncode is None:
                job.terminate()
        await asyncio.gather(*(job.wait() for job in jobs))
        for log in logs:
            log.close()


async def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    source_root = Path(__file__).resolve().parents[2]
    source_paths = sorted((source_root / 'server').glob('*.py')) + [source_root / path for path in (
        'dnd/runtime_reset.py', 'dnd/player/session.py', 'dnd/ai/runtime/action_semantics.py',
        'dnd/ai/runtime/decision_epoch.py', 'dnd/core/base_actions.py', 'dnd/core/base_conditions.py')]
    (args.output / 'source.json').write_text(json.dumps({str(path.relative_to(source_root)): 
        sha256(path.read_bytes()).hexdigest() for path in source_paths}, indent=2))
    cases = [(f'ordinary-{i:02}', 'two_sides', None) for i in range(args.games)]
    if args.combat:
        cases.extend((case, 'two_sides', case) for case in ('fireball_six_goblins', 'wall_of_fire', 'conjure_animals'))
        cases.extend((mode, mode, None) for mode in ('mixed', 'crypt'))
    configs = []
    for name, mode, case in cases:
        root = args.output / name
        root.mkdir()
        config = combat_configuration(case, root) if case else configuration(mode, root)
        # Last ordinary game uses normal entropy after seeded previous games.
        config = config.model_copy(update={'game_id': name,
            'test_seed': None if name == f'ordinary-{args.games - 1:02}' else config.test_seed})
        configs.append(config)
    app = create_app(configs[0])
    hosting = app.state.player_service
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port,
        log_level='warning', timeout_graceful_shutdown=5))
    began = perf_counter()
    task = asyncio.create_task(server.serve())
    rows, processes = [], []
    try:
        async with asyncio.timeout(30):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError('HTTP host exited')
                await asyncio.sleep(.01)
        listener_ms = (perf_counter() - began) * 1000
        for index, ((name, mode, case), config) in enumerate(zip(cases, configs, strict=True)):
            started = began if index == 0 else perf_counter()
            host = app.state.player_host if index == 0 else service.start_game(hosting, config)
            await wait_ready(host)
            ready_ms = (perf_counter() - started) * 1000
            process = host.process.process
            processes.append(process)
            result = await clients(args.output / name, config, f'http://127.0.0.1:{args.port}', case)
            before_end = perf_counter()
            await service.end_game(hosting, name)
            retired_ms = (perf_counter() - before_end) * 1000
            assert host.process is None and process.returncode is None
            rows.append({'game': name, 'worker_pid': process.pid, 'ready_ms': ready_ms,
                'end_wait_ms': retired_ms, 'native_reset_ms': [ms for kind, ms in host.timings if kind == 'end_game'],
                'commands': result['commands'], 'records': result['records'], 'terminal': result['terminal'],
                'latencies': result['latencies'], 'worker_timings': host.timings,
                'owned_process_rss_bytes': resident_bytes(process.pid),
                'rss_scope': 'Windows venv launcher only; not interpreter RSS' if os.name == 'nt'
                    else 'Native worker interpreter RSS from /proc',
                'retained_spool_bytes': sum(spool.committed_bytes for game in hosting.games.values()
                    for spool in game.recording.audiences.values())})
            print(json.dumps({key: rows[-1][key] for key in ('game', 'worker_pid', 'ready_ms', 'native_reset_ms')}), flush=True)
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 20)
        (args.output / 'result.json').write_text(json.dumps({'scope':
            'One long-lived production HTTP service; native worker subprocess with ordinary import/GC policy; '
            'SDK clients and health monitors are independent processes. Ready includes worker acquisition, '
            'native startup, encoding/pipe/spool and first own input boundary. Host import/config preparation '
            'excluded. First game cold worker; later games warm worker. No startup percentiles from this cohort.',
            'python': sys.version, 'listener_ms': listener_ms, 'rows': rows,
            'worker_returncodes': [p.returncode for p in processes], 'owned_workers_after_shutdown': hosting.workers.count,
            'warm_ordinary_mean_ms': statistics.fmean(row['ready_ms'] for row in rows[1:args.games]) if len(rows) > 1 else None}, indent=2))
    assert len({p.pid for p in processes}) == 1
    assert all(p.returncode == 0 for p in processes)
    assert hosting.workers.count == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--games', type=int, default=11)
    parser.add_argument('--port', type=int, default=8797)
    parser.add_argument('--combat', action='store_true')
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
