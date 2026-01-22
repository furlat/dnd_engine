"""
HTTP client for communicating with the D&D Engine server.
"""

from typing import Optional, Dict, Any, List, Tuple
import httpx


class APIClient:
    """Client for the D&D Engine REST API."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 10.0):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=timeout)
        self._current_entity_uuid: Optional[str] = None

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    # =========================================================================
    # Simulation Control
    # =========================================================================

    def start_human_game(self) -> Dict[str, Any]:
        """Start a new game with human control."""
        resp = self.client.post("/simulation/start-human")
        resp.raise_for_status()
        data = resp.json()
        self._current_entity_uuid = data.get("entity_uuid")
        return data

    def get_simulation_status(self) -> Dict[str, Any]:
        """Get simulation status."""
        resp = self.client.get("/simulation/status")
        resp.raise_for_status()
        return resp.json()

    # =========================================================================
    # State Queries
    # =========================================================================

    def get_state(self) -> Dict[str, Any]:
        """Get full game state (grid, entities, encounter)."""
        resp = self.client.get("/state")
        resp.raise_for_status()
        return resp.json()

    def get_current_turn(self) -> Dict[str, Any]:
        """Get current turn information."""
        resp = self.client.get("/encounter/current-turn")
        resp.raise_for_status()
        data = resp.json()
        if data.get("current_entity_uuid"):
            self._current_entity_uuid = data["current_entity_uuid"]
        return data

    def get_available_actions(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Get available actions for an entity."""
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID - call get_current_turn first")
        resp = self.client.get(f"/entity/{uuid}/available-actions")
        resp.raise_for_status()
        return resp.json()

    def get_entity(self, entity_uuid: str) -> Dict[str, Any]:
        """Get full entity details."""
        resp = self.client.get(f"/entity/{entity_uuid}")
        resp.raise_for_status()
        return resp.json()

    def get_entities(self) -> List[Dict[str, Any]]:
        """Get all entities (lightweight)."""
        resp = self.client.get("/entities")
        resp.raise_for_status()
        return resp.json().get("entities", [])

    def get_visibility(self) -> Dict[str, Any]:
        """Get visibility data for all entities."""
        resp = self.client.get("/visibility")
        resp.raise_for_status()
        return resp.json()

    # =========================================================================
    # Actions
    # =========================================================================

    def move(self, position: Tuple[int, int], entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute a move action."""
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.post("/action/move", json={
            "entity_uuid": uuid,
            "position": list(position)
        })
        resp.raise_for_status()
        return resp.json()

    def attack(self, target_uuid: str, weapon_slot: str = "main_hand",
               entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute an attack action."""
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.post("/action/attack", json={
            "entity_uuid": uuid,
            "target_uuid": target_uuid,
            "weapon_slot": weapon_slot
        })
        resp.raise_for_status()
        return resp.json()

    def dash(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute a dash action."""
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.post("/action/dash", json={"entity_uuid": uuid})
        resp.raise_for_status()
        return resp.json()

    def dodge(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute a dodge action."""
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.post("/action/dodge", json={"entity_uuid": uuid})
        resp.raise_for_status()
        return resp.json()

    def disengage(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute a disengage action."""
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.post("/action/disengage", json={"entity_uuid": uuid})
        resp.raise_for_status()
        return resp.json()

    def end_turn(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """End the current turn."""
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.post("/action/end-turn", json={"entity_uuid": uuid})
        resp.raise_for_status()
        data = resp.json()
        # Update current entity if returned
        if data.get("entity_uuid"):
            self._current_entity_uuid = data["entity_uuid"]
        return data

    @property
    def current_entity_uuid(self) -> Optional[str]:
        """Get the current entity UUID."""
        return self._current_entity_uuid
