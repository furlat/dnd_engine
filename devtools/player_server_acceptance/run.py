"""Live lane: independently installed Python/TS clients against one native server."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from time import perf_counter
import urllib.error
import urllib.request

from devtools.player_server_acceptance.fixtures import configuration


async def run_case(mode: str, output: Path, python: str, node_client: Path, port: int, swap: bool, server_python: str | None = None):
    directory = output / (mode + ('-swapped' if swap else ''))
    directory.mkdir(parents=True, exist_ok=False)
    config = configuration(mode, directory)
    path = directory / 'server.json'; path.write_text(config.model_dump_json(indent=2))
    source = Path(__file__).resolve().parent
    (node_client / 'player.mjs').write_bytes((source / 'typescript_player.mjs').read_bytes())
    started = perf_counter()
    server_log = (directory / 'server.log').open('wb')
    server = await asyncio.create_subprocess_exec(server_python or sys.executable, '-m', 'player_server', '--config', str(path), '--port', str(port),
        stdout=server_log, stderr=server_log)
    jobs=[];logs=[]
    def live():
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=1) as response:return response.status==200
        except (urllib.error.URLError,TimeoutError):return False
    try:
        async with asyncio.timeout(30):
            while not await asyncio.to_thread(live):
                if server.returncode is not None:raise RuntimeError('Server exited during launch')
                await asyncio.sleep(.05)
        for index, row in enumerate(config.credentials):
            destination=directory / row.seat_id;destination.mkdir()
            env=dict(os.environ,PLAYER_URL=f'http://127.0.0.1:{port}',PLAYER_TOKEN=row.token,PLAYER_OUTPUT=str(destination.absolute()))
            use_python=(index % 2 == 0) != swap
            cmd=[python,str(source/'python_player.py')] if use_python else ['node',str(node_client/'player.mjs')]
            if mode == 'crypt':
                # Headless oracle uses the identical production player reducer.
                env['PYTHONPATH']=str(Path('sdk/python/src').absolute())+os.pathsep+str(Path.cwd())
                cmd=[sys.executable,str(source/'crypt_player.py')]
            log=(destination/'client.log').open('wb');logs.append(log)
            jobs.append(await asyncio.create_subprocess_exec(*cmd,env=env,stdout=log,stderr=log))
        async with asyncio.timeout(260 if mode == 'crypt' else 150):
            outcomes=await asyncio.gather(*(job.wait() for job in jobs))
        if any(outcomes):raise RuntimeError(f'{mode} client failures: {outcomes}; see {directory}')
        results=[json.loads((directory/row.seat_id/'result.json').read_text()) for row in config.credentials]
        assert all(row['terminal'] for row in results)
        report={'mode':mode,'swap':swap,'elapsed_seconds':perf_counter()-started,'seats':len(results),'clients':results}
        (directory/'acceptance.json').write_text(json.dumps(report,indent=2))
        print(json.dumps({key:value for key,value in report.items() if key!='clients'}),flush=True)
        return report
    finally:
        for job in jobs:
            if job.returncode is None:job.terminate()
        await asyncio.gather(*(job.wait() for job in jobs))
        if server.returncode is None:server.terminate()
        await server.wait();server_log.close()
        for log in logs:log.close()


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--python',required=True);parser.add_argument('--node-client',type=Path,required=True)
    parser.add_argument('--modes',nargs='+',default=['two_sides','per_entity','human_vs_ai','ai_vs_human','mixed'])
    parser.add_argument('--swap',action='store_true');parser.add_argument('--server-python');args=parser.parse_args()
    for mode in args.modes:await run_case(mode,args.output,args.python,args.node_client,8792,args.swap,args.server_python)


if __name__=='__main__':asyncio.run(main())
