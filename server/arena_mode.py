"""Standard arena mode helpers for manual examples and local clients."""

import asyncio
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import httpx

from dnd.core.equipment_types import WeaponSlot
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
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
            path: Route path, such as `/diagnostics/objective/bootstrap`.
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
    reset_engine_runtime()
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
    response = client.get("/diagnostics/objective/bootstrap")
    response.raise_for_status()
    state = response.json()["world"]["state"]
    return [obj["name"] for obj in state["floor_objects"]]


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
    """Prepare, join, bootstrap, and activate one canonical local arena.

    Args:
        character_class: Canonical hero configuration family to select.

    Returns:
        Started arena bundle with the API client, session ID, and hero UUID.
    """
    reset_standard_arena_runtime()
    client = ArenaApiClient()
    hero_configurations = {
        "fighter": "hero.fighter_l5_archer_torch",
        "sorcerer": "hero.sorcerer_l5_standard_torch",
        "barbarian": "hero.barbarian_l5_berserker_torch",
    }
    try:
        hero_configuration_id = hero_configurations[character_class]
    except KeyError as error:
        raise ValueError(
            f"Unsupported arena character class: {character_class}"
        ) from error
    start_response = client.post(
        "/game-creation/start",
        json={
            "scenario": {
                "kind": "composed",
                "hero_configuration_id": hero_configuration_id,
                "monster_configuration_id": "monsters.skeleton_trio",
                "battlefield_id": "battlefield.standard_hazards_closed",
                "deployment_id": "neutral.battlefield.standard_hazards_closed",
            },
            "side_a": {
                "controller": "human",
                "name": "Arena Player",
            },
            "side_b": {
                "controller": "ai",
                "name": "Basic AI",
                "policy_id": "builtin.basic",
            },
            "opening_side": "side_a",
        },
    )
    start_response.raise_for_status()
    assignments = start_response.json()["side_a"]["entity_assignments"]
    if not assignments:
        raise RuntimeError("Prepared arena has no hero assignment")
    hero_uuid = assignments[0]["entity_uuid"]

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
    bootstrap_response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    bootstrap_response.raise_for_status()
    bootstrap = bootstrap_response.json()
    activation_response = client.post(
        "/game-creation/activate",
        json={
            "session_id": session_id,
            "expected_source_stream_id": bootstrap["protocol"][
                "source_stream_id"
            ],
            "expected_generation_id": bootstrap["protocol"]["generation_id"],
            "expected_perspective_epoch_id": bootstrap["perspective"][
                "perspective_epoch_id"
            ],
        },
    )
    activation_response.raise_for_status()

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
