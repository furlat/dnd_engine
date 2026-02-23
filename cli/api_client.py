"""
HTTP client for communicating with the D&D Engine server.

Updated to use session-based authentication for all actions.
"""

from typing import Optional, Dict, Any, List, Tuple
import httpx


class APIClient:
    """Client for the D&D Engine REST API with session support."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 10.0):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=timeout)
        self._current_entity_uuid: Optional[str] = None
        self._controlled_entity_uuids: List[str] = []  # All entities this session controls
        self._session_id: Optional[str] = None

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    # =========================================================================
    # Session Management
    # =========================================================================

    def create_session(self, player_type: str = "human", name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new player session.

        Args:
            player_type: "human" or "claude"
            name: Optional display name

        Returns:
            Session info including session_id
        """
        payload = {"player_type": player_type}
        if name:
            payload["name"] = name

        resp = self.client.post("/session/create", json=payload)
        resp.raise_for_status()
        data = resp.json()
        self._session_id = data.get("session_id")
        return data

    def ping_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Ping a session to update activity and get status.

        Returns info about whether it's this session's turn.
        """
        sid = session_id or self._session_id
        if not sid:
            raise ValueError("No session ID - call create_session first")

        resp = self.client.post(f"/session/{sid}/ping")
        resp.raise_for_status()
        return resp.json()

    def join_game(self, session_id: Optional[str] = None, entity_uuids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Join the active game with a session.

        If entity_uuids is provided, controls those entities.
        Otherwise auto-assigns based on player type.
        """
        sid = session_id or self._session_id
        if not sid:
            raise ValueError("No session ID - call create_session first")

        payload: Dict[str, Any] = {"session_id": sid}
        if entity_uuids:
            payload["entity_uuids"] = entity_uuids

        resp = self.client.post("/game/join", json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Store all controlled entities
        controlled = data.get("controlled_entities", [])
        self._controlled_entity_uuids = controlled
        if controlled:
            self._current_entity_uuid = controlled[0]

        return data

    def get_game_status(self) -> Dict[str, Any]:
        """Get current game status including all sessions."""
        resp = self.client.get("/game/status")
        resp.raise_for_status()
        return resp.json()

    @property
    def session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._session_id

    # =========================================================================
    # Simulation Control
    # =========================================================================

    def start_human_game(self, character_class: str = "fighter") -> Dict[str, Any]:
        """Start a new game with human control (vs AI).

        Args:
            character_class: "fighter" or "barbarian" - the hero's class
        """
        resp = self.client.post("/simulation/start-human", params={"character_class": character_class})
        resp.raise_for_status()
        data = resp.json()
        # Store hero UUID for joining
        if data.get("hero_uuid"):
            self._current_entity_uuid = data["hero_uuid"]
        return data

    def start_pvp_game(self, character_class: str = "fighter") -> Dict[str, Any]:
        """Start a new PvP game (human vs claude).

        Args:
            character_class: "fighter" or "barbarian" - the hero's class
        """
        resp = self.client.post("/simulation/start-pvp", params={"character_class": character_class})
        resp.raise_for_status()
        return resp.json()

    def get_simulation_status(self) -> Dict[str, Any]:
        """Get simulation status."""
        resp = self.client.get("/simulation/status")
        resp.raise_for_status()
        return resp.json()

    def get_pvp_status(self) -> Dict[str, Any]:
        """Get PvP game status including session connections."""
        resp = self.client.get("/pvp/status")
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
        # NOTE: Don't update _current_entity_uuid here!
        # That tracks the entity THIS client controls, not whose turn it is.
        # The active turn entity is in data["current_entity_uuid"].
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

    def get_tile_info(self, x: int, y: int) -> Dict[str, Any]:
        """Get detailed information about a specific tile.

        Returns:
            Tile info including name, walkable, walking_cost, conditions, handlers, entities
        """
        resp = self.client.get(f"/tile/{x}/{y}")
        resp.raise_for_status()
        return resp.json()

    def get_events(self, limit: int = 50, event_type: Optional[str] = None, phase: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent events from the server.

        Args:
            limit: Max number of events to return
            event_type: Filter by event type (e.g., "attack", "movement")
            phase: Filter by phase (e.g., "completion")

        Returns:
            List of event dictionaries
        """
        params: Dict[str, Any] = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        if phase:
            params["phase"] = phase

        resp = self.client.get("/events", params=params)
        resp.raise_for_status()
        return resp.json().get("events", [])

    def get_combat_log(self, since: int = 0) -> Dict[str, Any]:
        """
        Get combat log entries from the server.

        Args:
            since: Only return entries with index >= since (for polling)

        Returns:
            Dict with 'entries', 'count', and 'total' keys
        """
        resp = self.client.get("/combat-log", params={"since": since})
        resp.raise_for_status()
        return resp.json()

    # =========================================================================
    # Actions (require session_id)
    # =========================================================================

    def _require_session(self) -> str:
        """Ensure we have a session ID."""
        if not self._session_id:
            raise ValueError("No session ID - call create_session and join_game first")
        return self._session_id

    def execute_action(self, template_name: str, target_index: int = 0,
                        entity_uuid: Optional[str] = None,
                        extra_target_uuids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Execute any action by template name and target index.

        This is the unified action execution method that works with all action types:
        - Move: template_name="Move", target_index=position index from valid_targets
        - Attack: template_name="Attack_MELEE_MAIN", target_index=target index
        - Self actions: template_name="Dash"/"Dodge"/"Disengage", target_index=0
        - Multi-target spells: template_name="Magic Missile", extra_target_uuids for additional targets

        Args:
            template_name: Action template name (from available_actions)
            target_index: Index in valid_targets list (default 0 for self actions)
            entity_uuid: Entity performing action (defaults to current entity)
            extra_target_uuids: Additional target UUIDs for multi-target spells (e.g., Magic Missile darts)
        """
        session_id = self._require_session()
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        payload: Dict[str, Any] = {
            "session_id": session_id,
            "entity_uuid": uuid,
            "template_name": template_name,
            "target_index": target_index
        }
        if extra_target_uuids:
            payload["extra_target_uuids"] = extra_target_uuids
        resp = self.client.post("/action/execute", json=payload)
        resp.raise_for_status()
        return resp.json()

    def move(self, position: Tuple[int, int], entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute a move action to a position.

        NOTE: This requires finding the target_index for the position from available_actions.
        For simpler usage, call execute_action() directly with the index.
        """
        # Get available actions to find the position index
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")

        actions = self.get_available_actions(uuid)
        position_actions = actions.get("position_actions", [])

        for action in position_actions:
            for target in action.get("valid_targets", []):
                pos = target.get("position")
                if pos and tuple(pos) == tuple(position):
                    return self.execute_action(action["template_name"], target["index"], uuid)

        raise ValueError(f"Position {position} not in valid move targets")

    def attack(self, target_uuid: str, weapon_slot: str = "melee_main",
               entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute an attack action against a target.

        Args:
            target_uuid: UUID of the target entity
            weapon_slot: Weapon slot (melee_main, melee_off, ranged_main, ranged_off)
        """
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")

        actions = self.get_available_actions(uuid)
        entity_actions = actions.get("entity_actions", [])

        # Find matching attack action
        for action in entity_actions:
            # Match by weapon slot if specified
            action_slot = action.get("weapon_slot", "").lower()
            if weapon_slot and action_slot and weapon_slot.lower() != action_slot:
                continue

            for target in action.get("valid_targets", []):
                if target.get("target_uuid") == target_uuid:
                    return self.execute_action(action["template_name"], target["index"], uuid)

        raise ValueError(f"Target {target_uuid} not in valid attack targets")

    def dash(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute a dash action."""
        return self.execute_action("Dash", 0, entity_uuid)

    def dodge(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute a dodge action."""
        return self.execute_action("Dodge", 0, entity_uuid)

    def disengage(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute a disengage action."""
        return self.execute_action("Disengage", 0, entity_uuid)

    def end_turn(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """End the current turn."""
        session_id = self._require_session()
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.post("/action/end-turn", json={
            "session_id": session_id,
            "entity_uuid": uuid
        })
        resp.raise_for_status()
        data = resp.json()
        # NOTE: Don't update _current_entity_uuid here!
        # The returned entity_uuid is whoever's turn is NEXT, not who we control.
        # Our controlled entity was set in join_game and doesn't change.
        return data

    def execute_position_action(self, action_name: str, position: Tuple[int, int],
                                entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Execute a position-targeting action by name and position.

        Calls /action/position directly, bypassing the prefiltered valid_targets list.
        Used for AoE spells targeting positions not in the preview (e.g., empty ground).

        Args:
            action_name: Template name (e.g., "Fireball")
            position: Target (x, y) position
            entity_uuid: Entity performing the action
        """
        session_id = self._require_session()
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.post("/action/position", json={
            "session_id": session_id,
            "entity_uuid": uuid,
            "action_name": action_name,
            "position": list(position),
        })
        resp.raise_for_status()
        return resp.json()

    def get_handlers(self, entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Get all event handlers for an entity."""
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.get(f"/entity/{uuid}/handlers")
        resp.raise_for_status()
        return resp.json()

    def toggle_handler(self, handler_name: str, enabled: bool,
                       entity_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Toggle a handler's enabled state."""
        session_id = self._require_session()
        uuid = entity_uuid or self._current_entity_uuid
        if not uuid:
            raise ValueError("No entity UUID")
        resp = self.client.post(f"/entity/{uuid}/handlers/{handler_name}/toggle", json={
            "session_id": session_id,
            "entity_uuid": uuid,
            "enabled": enabled,
        })
        resp.raise_for_status()
        return resp.json()

    @property
    def current_entity_uuid(self) -> Optional[str]:
        """Get the current entity UUID."""
        return self._current_entity_uuid
