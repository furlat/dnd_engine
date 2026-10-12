"""Operator-only observations; never added to either player's sandbox inputs."""
from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


Observer = Callable[[dict], None]


def ignore(event: dict) -> None:
    pass


def journal(path: Path) -> Observer:
    path.touch(mode=0o600, exist_ok=False)
    output = path.open('a', buffering=1)
    sequence = 0
    size = 0
    disabled = False

    def emit(event: dict) -> None:
        nonlocal sequence, size, disabled
        if disabled:
            return
        try:
            sequence += 1
            line = json.dumps({'sequence': sequence, 'time': datetime.now(timezone.utc).isoformat(),
                **event}, ensure_ascii=False) + '\n'
            size += len(line.encode())
            if size > 64 * 1024 * 1024:
                raise OSError('Operator trace reached its 64 MiB limit')
            output.write(line)
        except (OSError, TypeError, ValueError) as error:
            disabled = True
            output.close()
            print(f'Operator trace stopped: {error}', file=sys.stderr, flush=True)

    return emit


def summary(name: str, result: dict) -> dict:
    if name == 'game_events':
        return {'records': len(result['records']), 'next_after': result['next_after'],
            'has_more': result['has_more']}
    if name == 'game_choices':
        choices = result['choices']
        return {'actor': choices['entity_uuid'], 'actions': [row['display_name']
            for group in ('entity_actions', 'position_actions', 'self_actions', 'object_actions')
            for row in choices.get(group, [])]}
    if name == 'game_preview':
        return {'can_confirm': result['preview']['can_confirm']}
    observation = result.get('observation', result)
    if 'status' in observation:
        return {'boundary': observation['status']['boundary'], 'cursor': observation['cursor'],
            'receipt': result.get('receipt'), 'wait_timed_out': result.get('wait_timed_out', False),
            'game_ref': observation.get('game_ref'), 'mode': observation.get('mode')}
    return result
