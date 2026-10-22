"""Launch a private game + MCP and show both agents in one terminal."""
import argparse
import asyncio
from contextlib import ExitStack, nullcontext
from datetime import datetime
import json
from pathlib import Path
import signal
import socket
import sys

import httpx
from rich.console import Console
from rich.live import Live

from monty_sandbox.watch import View, consume, line_summary, render, snapshot


ROOT = Path(__file__).resolve().parents[1]


async def ready(process, url: str, log: Path, stop: asyncio.Event, method: str = 'GET') -> None:
    async with httpx.AsyncClient() as client, asyncio.timeout(60):
        while process.returncode is None and not stop.is_set():
            try:
                response = await client.request(method, url, timeout=1)
                if response.status_code < 500:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(.1)
    if stop.is_set():
        return
    raise RuntimeError(f'Service failed to start; inspect {log}')


async def display(directory: Path, endpoint: str, plain: bool, stop: asyncio.Event,
                  children=(), once: bool = False) -> None:
    console = Console()
    view = View()
    path = directory / 'events.jsonl'
    with path.open() as handle, (nullcontext() if plain else Live(console=console, auto_refresh=False)) as live:
        while True:
            for event in consume(handle, view):
                if plain:
                    console.print(line_summary(event), markup=False, highlight=False)
            if not plain:
                title = 'D&D · Monty agent arena' if children else 'D&D · operator trace'
                live.update(render(view, title, endpoint, console.height), refresh=True)
            if once or stop.is_set() or any(child.returncode is not None for child in children):
                snapshot(view, directory, endpoint)
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=.15)
            except TimeoutError:
                pass


async def run(args) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    if args.command == 'watch':
        info = json.loads((args.directory / 'arena.json').read_text())
        await display(args.directory, info['mcp_url'], args.plain, stop, once=args.once)
        return
    if args.game_port == args.mcp_port:
        raise ValueError('Game and MCP need different ports')
    for port in (args.game_port, args.mcp_port):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', port))
    directory = args.output.resolve()
    endpoint = f'http://127.0.0.1:{args.mcp_port}/mcp'
    console = Console()
    console.print(f'Preparing private 1v1 match in {directory}', markup=False)
    prepare = await asyncio.create_subprocess_exec(str(args.server_python), '-m',
        'monty_sandbox.prepare_trial', '--summoner-duel' if args.summoner_duel else '--duel', '--output', str(directory),
        '--game-port', str(args.game_port), '--seed', str(args.seed), cwd=ROOT)
    if await prepare.wait():
        raise RuntimeError('Could not prepare the private match')
    if stop.is_set():
        return
    children = []
    try:
        with ExitStack() as files:
            for name, command in (
                ('game', [str(args.server_python), '-m', 'server', '--config', str(directory / 'game.json'),
                    '--port', str(args.game_port)]),
                ('mcp', [sys.executable, '-m', 'monty_sandbox.app', '--seats', str(directory / 'seats.json'),
                    '--port', str(args.mcp_port), '--events', str(directory / 'events.jsonl')])):
                log = files.enter_context((directory / f'{name}.log').open('w'))
                children.append(await asyncio.create_subprocess_exec(*command, cwd=ROOT, stdout=log, stderr=log))
            info = {'mcp_url': endpoint, 'game_port': args.game_port, 'mcp_port': args.mcp_port,
                'seats': ['amber', 'blue'], 'seed': args.seed,
                'fixture': 'summoner_duel' if args.summoner_duel else 'skeleton_duel',
                'pids': [child.pid for child in children]}
            (directory / 'arena.json').write_text(json.dumps(info, indent=2))
            await asyncio.gather(ready(children[0], f'http://127.0.0.1:{args.game_port}/health', directory / 'game.log', stop),
                ready(children[1], endpoint, directory / 'mcp.log', stop, 'OPTIONS'))
            if stop.is_set():
                return
            console.print(f'Ready: {endpoint} | seats amber / blue | Ctrl-C stops only these services', markup=False)
            await display(directory, endpoint, args.plain, stop, children)
    finally:
        for child in reversed(children):
            if child.returncode is None:
                child.send_signal(signal.SIGINT)
                try:
                    await asyncio.wait_for(child.wait(), timeout=10)
                except TimeoutError:
                    child.kill()
                    await child.wait()
        console.print(f'Owned services stopped. Replay: python -m monty_sandbox.cli watch {directory} --once', markup=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('run', help='Start a fresh native 1v1 match, MCP and operator display')
    start.add_argument('--output', type=Path, default=ROOT / '.runtime' / ('monty-arena-' + datetime.now().strftime('%Y%m%d-%H%M%S')))
    start.add_argument('--game-port', type=int, default=18893)
    start.add_argument('--mcp-port', type=int, default=18894)
    start.add_argument('--server-python', type=Path, default=ROOT / '.venv/bin/python')
    start.add_argument('--seed', type=int, default=7)
    start.add_argument('--summoner-duel', action='store_true', help='Use identical Codex clerics with animal summons')
    start.add_argument('--plain', action='store_true', help='Append readable event lines instead of a live dashboard')
    watch = commands.add_parser('watch', help='Watch or replay an existing trace; never submits actions')
    watch.add_argument('directory', type=Path)
    watch.add_argument('--once', action='store_true', help='Render the current recorded result and exit')
    watch.add_argument('--plain', action='store_true')
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
