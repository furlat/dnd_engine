"""Render the operator journal. Watching/replaying never sends game commands."""
from collections import deque
from dataclasses import dataclass, field
from io import StringIO
import json
from pathlib import Path
import re

from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


@dataclass
class View:
    seats: dict = field(default_factory=dict)
    recent: deque = field(default_factory=lambda: deque(maxlen=8))
    count: int = 0


def clean(value: str) -> str:
    # Source code and game strings are data, never terminal escape sequences.
    return ''.join(char for char in value if char in '\n\t' or char.isprintable())


def update(view: View, event: dict) -> None:
    view.count += 1
    name = event.get('agent') or event.get('seat') or 'scratch'
    seat = view.seats.setdefault(name, {'status': 'connecting', 'cursor': '-', 'calls': 0,
        'commands': 0, 'host_calls': 0, 'code': '', 'stdout': '', 'result': '', 'controlled': [],
        'game_ref': None, 'game_label': '', 'controlled_by_game': {},
        'logs': deque(maxlen=5), 'activity': deque(maxlen=5)})
    kind = event['kind']
    label = event.get('name', kind)
    if event.get('game_ref') and event['game_ref'] != seat['game_ref']:
        seat['game_ref'] = event['game_ref']
        seat['game_label'] = f'{event.get("seat", "game")} · {event["game_ref"][:8]}'
        seat['controlled'] = seat['controlled_by_game'].get(event['game_ref'], [])
        seat['logs'].clear()
    if kind == 'mcp_call':
        seat['calls'] += 1
        if label == 'execute' and not event.get('retry'):
            seat['code'] = clean(event['code'])
            seat['stdout'] = ''
            seat['result'] = ''
        detail = f'{name}  {label}  {event.get("request_id", "")}'
        if event.get('retry'):
            detail += ' (saved execution)'
        view.recent.append(clean(detail))
    if kind == 'host_call':
        seat['host_calls'] += 1
        seat['activity'].append(f'→ {label}')
    if kind == 'host_error':
        seat['activity'].append(clean(f'! {label}: {event["error"]}')[:180])
    if kind in ('session_open', 'game_joined', 'game_archived') and event['observation'] is not None:
        seat['controlled'] = event['observation']['audience']['controlled']
        if seat['game_ref'] is not None:
            seat['controlled_by_game'][seat['game_ref']] = seat['controlled']
    observation = (event.get('observation') or {}) if kind in ('session_open', 'game_joined', 'game_archived') else event if kind == 'record' else event.get('result', {})
    if kind in ('host_result', 'session_open', 'game_joined', 'game_archived', 'record'):
        boundary = observation.get('boundary', observation.get('status', {}).get('boundary'))
        if boundary:
            seat['status'] = boundary['lifecycle']
            if seat['status'] == 'waiting_for_human':
                seat['status'] = 'YOUR TURN' if boundary['input_actor_uuid'] in seat['controlled'] else 'waiting for opponent'
        receipt = observation.get('receipt')
        if receipt:
            seat['commands'] += receipt['kind'] == 'committed'
            seat['activity'].append(f'✓ command {receipt["command_number"]}: {receipt["kind"]}')
        cursor = observation.get('cursor')
        if cursor:
            seat['cursor'] = cursor['sequence']
        if observation.get('mode') == 'archived':
            seat['status'] = 'archived · read-only'
    if kind == 'record':
        seat['cursor'] = event['cursor']['sequence']
        seat['logs'].extend(clean(re.sub(r'\{[a-zA-Z_ #0-9]+:([^{}]*)\}', r'\1', line)) for line in event['logs'])
    if kind == 'stdout':
        seat['stdout'] = (seat['stdout'] + clean(event['text']))[-1000:]
    if kind == 'execution_done':
        answer = event['answer']
        seat['activity'].append(f'{answer["state"]} · {event["host_calls"]} host calls · {answer["elapsed_seconds"]}s')
        value = answer.get('error', answer.get('result', answer.get('result_preview')))
        seat['result'] = clean(json.dumps(value, ensure_ascii=False))[:1000]
    if kind == 'session_closed':
        seat['status'] = 'closed'


def consume(handle, view: View) -> list[dict]:
    events = []
    while True:
        position = handle.tell()
        line = handle.readline()
        if not line.endswith('\n'):
            handle.seek(position)
            return events
        event = json.loads(line)
        update(view, event)
        events.append(event)


def render(view: View, title: str, endpoint: str, height: int = 45) -> Group:
    short = height < 42
    columns = Table.grid(expand=True, padding=(0, 1))
    names = list(view.seats) if any(name not in ('amber', 'blue') for name in view.seats) else ['amber', 'blue']
    panels = []
    for name in names:
        seat = view.seats.get(name)
        color = 'yellow' if name == 'amber' else 'bright_cyan'
        if seat is None:
            body = Text('Waiting for an agent to open this seat.', style='dim')
        else:
            lines = seat['code'].splitlines()
            code = '\n'.join(lines[-(3 if short else 6):]) or '# No code submitted yet'
            body = Group(
                Text(f'{seat["status"]}  |  cursor {seat["cursor"]}', style='bold'),
                Text(seat['game_label'] or 'No game attached', style='dim'),
                Text(f'{seat["calls"]} MCP · {seat["host_calls"]} game · {seat["commands"]} commands'),
                Text(f'Latest code ({len(lines)} lines; tail shown)', style='dim'),
                Syntax(code, 'python', theme='monokai', word_wrap=False),
                Text('\n'.join(list(seat['activity'])[-(2 if short else 3):]) or 'No activity yet', no_wrap=True, overflow='ellipsis'),
                Text('Agent output', style='bold'),
                Text('\n'.join(seat['stdout'].splitlines()[-(2 if short else 3):]) or '—', no_wrap=True, overflow='ellipsis'),
                Text('Result', style='bold'), Text(seat['result'] or '—', no_wrap=True, overflow='ellipsis'),
                Text('Combat', style='bold'),
                Text('\n'.join(list(seat['logs'])[-(3 if short else 4):]) or '—', no_wrap=True, overflow='ellipsis'))
        panels.append(Panel(body, title=Text(name.upper()), border_style=color))
    for _ in panels:
        columns.add_column(ratio=1)
    columns.add_row(*panels)
    return Group(Panel(Text(f'{title} · {view.count} events\n{endpoint} · Ctrl-C closes this command')),
        columns, Panel(Text('\n'.join(list(view.recent)[-(2 if short else 4):]) or 'Waiting for MCP clients',
            no_wrap=True, overflow='ellipsis'), title='MCP activity'))


def line_summary(event: dict) -> str:
    seat = event.get('agent') or event.get('seat') or 'scratch'
    value = event.get('name', event['kind'])
    if event['kind'] == 'record':
        value = ' | '.join(event['logs']) or f'record {event["cursor"]["sequence"]}'
    elif event['kind'] == 'stdout':
        value = event['text']
    elif event['kind'] == 'execution_done':
        value = json.dumps(event['answer'], ensure_ascii=False)
    elif event['kind'] == 'host_result':
        value += ' ' + json.dumps(event['result'], ensure_ascii=False)
    return clean(f'{event.get("time", "")[11:19]} {seat:7} {event["kind"]:16} {value}')[:1000]


def snapshot(view: View, directory: Path, endpoint: str) -> None:
    console = Console(record=True, width=140, file=StringIO())
    console.print(render(view, 'Recorded match — operator view', endpoint))
    console.save_html(str(directory / 'dashboard.html'), clear=False)
    console.save_text(str(directory / 'dashboard.txt'), clear=False)
    console.save_svg(str(directory / 'dashboard.svg'), title='D&D · agent duel', clear=False)
