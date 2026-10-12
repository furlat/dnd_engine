"""Explicit game contexts in an agent workspace; archives have no connection."""
from collections.abc import Sequence
from dataclasses import dataclass
import json

from monty_sandbox import player


@dataclass
class GameEntry:
    game_ref: str
    seat: str
    identity: dict
    records: Sequence[dict]
    live: player.Player | None
    archived: dict | None = None


def describe(entry: GameEntry) -> dict:
    return {'game_ref': entry.game_ref, 'seat': entry.seat, 'identity': entry.identity,
        'mode': 'live' if entry.live is not None else 'archived', 'record_count': len(entry.records)}


def lookup(games: dict[str, GameEntry], game_ref: str) -> GameEntry:
    if game_ref not in games:
        raise ValueError('Unknown game_ref in this agent session')
    return games[game_ref]


def require_live(games: dict[str, GameEntry], game_ref: str) -> player.Player:
    entry = lookup(games, game_ref)
    if entry.live is None:
        raise ValueError('Archived game is read-only; no live authority remains')
    return entry.live


async def read(entry: GameEntry) -> dict:
    observation = entry.archived if entry.live is None else await player.read_game(entry.live)
    return {**observation, **describe(entry)}


async def archive(entry: GameEntry) -> dict:
    if entry.live is not None:
        if entry.live.unresolved is not None:
            raise ValueError('Resolve the pending command before archiving')
        observation = await player.read_game(entry.live)
        if observation['status']['boundary']['lifecycle'] not in ('terminal', 'failed', 'closed'):
            raise ValueError('Only a finished game can be archived')
        await player.close_player(entry.live)
        entry.records = tuple(entry.records)
        entry.archived = json.loads(json.dumps(observation))
        entry.live = None
    return await read(entry)


def callbacks(games: dict[str, GameEntry]) -> dict:
    async def list_games():
        return {'games': [describe(entry) for entry in games.values()]}

    async def read_game(game_ref: str):
        return await read(lookup(games, game_ref))

    async def events(game_ref: str, after: int = -1, limit: int = 16):
        entry = lookup(games, game_ref)
        return {**player.events(entry.records, after, limit), 'game_ref': game_ref}

    async def choices(game_ref: str, force_attack: bool = False):
        return await player.discover(require_live(games, game_ref), force_attack)

    async def preview(game_ref: str, actor_uuid: str, state_revision: str,
                      discovery_generation: int, selection: dict):
        return await player.preview_action(require_live(games, game_ref), actor_uuid,
            state_revision, discovery_generation, selection)

    async def act(game_ref: str, actor_uuid: str, state_revision: str, intent: dict):
        result = await player.act(require_live(games, game_ref), actor_uuid, state_revision, intent)
        result['observation'].update(describe(lookup(games, game_ref)))
        return result

    async def receipt(game_ref: str):
        result = await player.resolve_receipt(require_live(games, game_ref))
        result['observation'].update(describe(lookup(games, game_ref)))
        return result

    async def wait(game_ref: str, timeout_seconds: float = 20):
        result = await player.wait_game(require_live(games, game_ref), timeout_seconds)
        return {**result, **describe(lookup(games, game_ref))}

    return {'game_list': list_games, 'game_read': read_game, 'game_events': events,
        'game_choices': choices, 'game_preview': preview, 'game_act': act,
        'game_receipt': receipt, 'game_wait': wait}
