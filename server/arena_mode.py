"""Standard arena mode helpers for manual examples and local clients."""

import asyncio
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import httpx

from dnd.controller import Controller
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue, WeaponSlot
from dnd.core.gridmap import GridMap
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from server.event_server import app, sim


class ArenaApiClient:
    """Synchronous in-process client for the standard arena API."""

    def __init__(self) -> None:
        """Create a reusable in-process ASGI client.

        The self-play and validation harnesses issue many small API calls. A
        persistent runner and HTTPX client keep that path from measuring client
        setup cost as gameplay latency.
        """
        self._runner: Optional[asyncio.Runner] = None
        self._client: Optional[httpx.AsyncClient] = None

    def get(self, path: str, **kwargs) -> httpx.Response:
        """Issue a GET request to the arena API.

        Args:
            path: Route path, such as `/state`.
            **kwargs: Request options forwarded to HTTPX.

        Returns:
            HTTP response produced by the FastAPI app.
        """
        return self._run(self._request("GET", path, **kwargs))

    def post(self, path: str, **kwargs) -> httpx.Response:
        """Issue a POST request to the arena API.

        Args:
            path: Route path, such as `/session/create`.
            **kwargs: Request options forwarded to HTTPX.

        Returns:
            HTTP response produced by the FastAPI app.
        """
        return self._run(self._request("POST", path, **kwargs))

    def close(self) -> None:
        """Close the reusable ASGI client and event loop."""
        if self._runner is None:
            return
        if self._client is not None:
            self._runner.run(self._client.aclose())
            self._client = None
        self._runner.close()
        self._runner = None

    def __enter__(self) -> "ArenaApiClient":
        """Return this client for context-manager use."""
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        """Close the reusable client and allow exceptions to propagate."""
        self.close()
        return False

    def _run(self, awaitable):
        """Run one coroutine on the client's persistent event loop."""
        if self._runner is None:
            self._runner = asyncio.Runner()
        return self._runner.run(awaitable)

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Run one request through HTTPX's ASGI transport.

        Args:
            method: HTTP method name.
            path: Route path.
            **kwargs: Request options forwarded to HTTPX.

        Returns:
            HTTP response produced by the FastAPI app.
        """
        if self._client is None:
            transport = httpx.ASGITransport(app=app)
            self._client = httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            )
        return await self._client.request(method, path, **kwargs)


@dataclass(frozen=True)
class JoinedHumanArena:
    """Started arena session owned by one human player."""

    client: ArenaApiClient
    session_id: str
    hero_uuid: str


def reset_standard_arena_runtime() -> None:
    """Clear engine and server state for a fresh standard arena scene."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    GridMap.reset()
    sim.reset()


def entity_by_name(name: str) -> Entity:
    """Return the currently registered entity with a display name.

    Args:
        name: Entity display name to find.

    Returns:
        Matching registered entity.

    Raises:
        LookupError: If no entity with that display name exists.
    """
    entity = next(
        (candidate for candidate in Entity.get_all_entities() if candidate.name == name),
        None,
    )
    if entity is None:
        raise LookupError(f"No registered entity named {name!r}")
    return entity


def floor_object_names(client: ArenaApiClient) -> list[str]:
    """Return floor-object names from the public game-state payload.

    Args:
        client: Arena API client.

    Returns:
        Object display names currently present on the map floor.
    """
    response = client.get("/state")
    response.raise_for_status()
    return [obj["name"] for obj in response.json()["floor_objects"]]


def action_template_names(entity: Entity) -> set[str]:
    """Return registered action-template names for an entity.

    Args:
        entity: Actor whose available action templates are inspected.

    Returns:
        Names of registered action templates.
    """
    return {action.name for action in entity.registered_actions if action.name is not None}


def inventory_item_names(entity: Entity) -> list[str]:
    """Return inventory item names for an entity.

    Args:
        entity: Actor whose inventory is inspected.

    Returns:
        Sorted item display names.
    """
    return sorted(item.name for item in entity.inventory.items.values() if item.name is not None)


def equipped_item_name(entity: Entity, slot: WeaponSlot) -> str:
    """Return the name of an item equipped in a weapon slot.

    Args:
        entity: Actor whose equipment is inspected.
        slot: Weapon slot to read.

    Returns:
        Equipped item display name.

    Raises:
        LookupError: If the slot is empty or the item has no display name.
    """
    item = entity.equipment.get_item_by_slot(slot)
    if item is None or item.name is None:
        raise LookupError(f"{entity.name} has no named item in {slot.value}")
    return item.name


def start_joined_human_arena(character_class: str = "fighter") -> JoinedHumanArena:
    """Start human arena mode and join a human session to the hero.

    Args:
        character_class: Hero class selected by the arena start route.

    Returns:
        Started arena bundle with the API client, session ID, and hero UUID.
    """
    reset_standard_arena_runtime()
    client = ArenaApiClient()
    start_response = client.post(
        "/simulation/start-human",
        params={"character_class": character_class},
    )
    start_response.raise_for_status()
    hero_uuid = start_response.json()["hero_uuid"]

    session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Arena Player"},
    )
    session_response.raise_for_status()
    session_id = session_response.json()["session_id"]

    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [hero_uuid]},
    )
    join_response.raise_for_status()

    return JoinedHumanArena(
        client=client,
        session_id=session_id,
        hero_uuid=hero_uuid,
    )


def normalize_uuid(value: str | UUID) -> str:
    """Return a UUID value as the API string representation.

    Args:
        value: UUID instance or string UUID.

    Returns:
        String UUID used by API payloads.
    """
    return str(value)
