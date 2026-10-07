"""Private hosting composition: many games, one bounded reusable worker set."""
import asyncio
from dataclasses import dataclass, field
import secrets

from player_server import host as owner, protocol as wire, workers
from player_server.config import ServerConfig, ServiceLimits


@dataclass(slots=True)
class Service:
    workers: workers.Workers
    allowed_origins: tuple[str, ...]
    games: dict[str, owner.Host] = field(default_factory=dict)
    closing: bool = False


def create_service(config: ServerConfig, limits: ServiceLimits) -> Service:
    service = Service(workers.Workers(limits), config.allowed_origins)
    prepare_game(service, config)
    return service


def prepare_game(service: Service, config: ServerConfig) -> owner.Host:
    """Atomically reserve identities and recording budget before starting work."""
    if service.closing:
        raise RuntimeError('Player service is closing')
    # Expired recordings have already been removed by their owning Host.
    service.games = {key: value for key, value in service.games.items() if not value.history_expired}
    if config.game_id in service.games:
        raise ValueError('Game ID is already active or retained')
    if config.allowed_origins != service.allowed_origins:
        raise ValueError('All games share the service CORS policy')
    credentials = {row.token for host in service.games.values() for row in host.config.credentials}
    if any(row.token in credentials for row in config.credentials):
        raise ValueError('Credentials must be distinct across active and retained games')
    limits = service.workers.limits
    reserved = sum(host.config.spool_limit_bytes * len(host.seats) for host in service.games.values())
    if (len(service.games) >= limits.max_games or
            reserved + config.spool_limit_bytes * len(config.credentials) > limits.recording_budget_bytes):
        raise ValueError('Player service game/recording budget exhausted')
    host = owner.create_host(config, service.workers)
    service.games[config.game_id] = host
    return host


def start_game(service: Service, config: ServerConfig) -> owner.Host:
    """Deployment entry point; this is not an untrusted player/admin endpoint."""
    asyncio.get_running_loop()  # Reject before allocation when called outside the service loop.
    host = prepare_game(service, config)
    host.task = asyncio.create_task(owner.run(host), name=f'native-game:{config.game_id}')
    return host


def authorize(service: Service, token: str, game_id: str | None = None) -> tuple[owner.Host, owner.Seat]:
    for host in service.games.values():
        for row in host.config.credentials:
            if secrets.compare_digest(token.encode(), row.token.encode()):
                if game_id is not None and game_id != host.config.game_id:
                    raise owner.ApiFailure(wire.ErrorGameNotFound())
                return host, host.seats[row.seat_id]
    raise owner.ApiFailure(wire.ErrorUnauthenticated())


async def end_game(service: Service, game_id: str) -> None:
    await owner.end_game(service.games[game_id])


async def shutdown(service: Service) -> None:
    service.closing = True
    cleanup = asyncio.create_task(_shutdown(service), name='player-service-shutdown')
    try:
        await asyncio.shield(cleanup)
    except asyncio.CancelledError:
        await cleanup
        raise


async def _shutdown(service: Service) -> None:
    # Wake pending acquisitions before awaiting Hosts; their workers cannot be reused.
    try:
        await workers.shutdown(service.workers)
    finally:
        try:
            results = await asyncio.gather(*(owner.shutdown(host) for host in service.games.values()),
                return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException):
                    raise result
        finally:
            await workers.shutdown(service.workers)
