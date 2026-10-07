"""Run a bounded real HTTP cohort and shut down its owned host and worker."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from time import perf_counter, time_ns

from devtools.player_server_acceptance.fixtures import COMBAT_CASES, combat_configuration, configuration


def join_worker_timings(root):
    result = json.loads((root / 'result.json').read_text())
    measured = json.loads((root / 'host-result.json').read_text())['timings']
    queries, command_index = [], -1
    for kind, milliseconds in measured:
        if kind in ('choices', 'preview'):
            queries.append({'kind': kind, 'ms': milliseconds})
        elif kind == 'command':
            command_index += 1
            result['rows'][command_index].update(worker_ms=milliseconds, worker_queries=queries, following_advances_ms=[])
            queries = []
        elif kind == 'advance' and command_index >= 0:
            result['rows'][command_index]['following_advances_ms'].append(milliseconds)
    assert command_index + 1 == len(result['rows']), 'Worker and client command counts differ'
    (root / 'result.json').write_text(json.dumps(result, indent=2))


async def run(args):
    root = args.output
    root.mkdir(parents=True, exist_ok=False)
    config = root / 'server.json'
    settings = combat_configuration(args.combat_case, root, args.seed) if args.combat_case else configuration('two_sides', root)
    config.write_text(settings.model_dump_json(indent=2))
    log = (root / 'server.log').open('wb')
    extra = ['--worker-profile', str(root / 'worker-profile.json'),
        '--profile-census-after', str(args.commands)] if args.profile else []
    started = perf_counter()
    spawned_unix_ns = time_ns()
    server = await asyncio.create_subprocess_exec(args.python, '-m', 'devtools.player_server_acceptance.test_host',
        '--config', str(config), '--stop', str(root / 'server.stop'), '--result', str(root / 'host-result.json'),
        '--port', str(args.port), *extra, stdout=log, stderr=log)
    jobs, logs = [], []
    try:
        async with asyncio.timeout(30):
            while not (root / 'host.ready').exists():
                if server.returncode is not None:
                    raise RuntimeError('Owned test host exited during startup')
                await asyncio.sleep(.05)
        host_ready_ms = (perf_counter() - started) * 1000
        for mode in ('monitor', 'client'):
            stream = (root / f'{mode}.log').open('wb')
            logs.append(stream)
            jobs.append(await asyncio.create_subprocess_exec(args.python, '-m',
                'devtools.player_server_acceptance.http_performance', mode,
                '--url', f'http://127.0.0.1:{args.port}', '--config', str(config), '--output', str(root),
                '--commands', str(args.commands), *(['--combat-case', args.combat_case] if args.combat_case else []),
                stdout=stream, stderr=stream))
        async with asyncio.timeout(240):
            codes = await asyncio.gather(*(job.wait() for job in jobs))
        if any(codes):
            raise RuntimeError(f'Probe subprocess failures: {codes}; see {root}')
        host_boundary = json.loads((root / 'host-first-human-boundary.json').read_text())
        sdk_boundary = json.loads((root / 'first-human-boundary.json').read_text())
        (root / 'runner-timings.json').write_text(json.dumps({'host_ready_wall_ms': host_ready_ms,
            'host_spawn_unix_ns': spawned_unix_ns,
            'host_first_human_boundary_ms': (host_boundary['observed_unix_ns'] - spawned_unix_ns) / 1000000,
            'host_first_human_boundary_scope': host_boundary['scope'],
            'sdk_first_human_boundary_ms': (sdk_boundary['observed_unix_ns'] - spawned_unix_ns) / 1000000,
            'sdk_first_human_boundary_scope': sdk_boundary['scope'],
            'published_to_sdk_consumed_ms': (sdk_boundary['observed_unix_ns'] - host_boundary['observed_unix_ns']) / 1000000,
            'complete_cohort_wall_ms': (perf_counter() - started) * 1000,
            'scope': 'Fresh host process spawn through HTTP listener started. Native worker launch is included, but native initialization may still be running; this is not game readiness. Fixture configuration preparation excluded. One observation, not a startup percentile.'}, indent=2))
        actual_commands = sum(json.loads((root / 'result.json').read_text())['commands'].values())
        print(f'Completed {actual_commands} commands: {root}', flush=True)
    finally:
        (root / 'monitor.stop').touch()
        (root / 'monitor.start').touch()
        for job in jobs:
            if job.returncode is None:
                job.terminate()
        await asyncio.gather(*(job.wait() for job in jobs))
        (root / 'server.stop').touch()
        # A stop file reaches the actual Windows host too; never kill WSL's
        # interoperability parent and leave its native worker orphaned.
        await asyncio.wait_for(server.wait(), 20)
        if (root / 'result.json').exists() and (root / 'host-result.json').exists():
            join_worker_timings(root)
        log.close()
        for stream in logs:
            stream.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--commands', type=int, default=200)
    parser.add_argument('--port', type=int, default=8796)
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--combat-case', choices=COMBAT_CASES)
    parser.add_argument('--seed', type=int, default=2)
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
