"""
Session-based player authority system.

This module provides clean abstractions for managing players and game sessions,
replacing the scattered sim.* state variables with a unified system.

Key concepts:
- PlayerSession: A connected client (human, claude, or AI) that controls entities
- GameSession: The active game with all players and entity ownership mappings
- SessionManager: Singleton managing all active sessions and games
"""

from enum import Enum
from typing import Dict, Set, Optional, List
from uuid import UUID, uuid4
from dataclasses import dataclass, field
import time
from fastapi import HTTPException

from dnd.encounter import Encounter, TurnState


class PlayerType(str, Enum):
    """Type of player controlling entities."""
    HUMAN = "human"      # User via CLI
    CLAUDE = "claude"    # Claude via agent CLI
    AI = "ai"            # Built-in AI (MeleeAIController etc)


class ConnectionStatus(str, Enum):
    """Connection state of a player session."""
    CONNECTED = "connected"       # Active, responding to pings
    DISCONNECTED = "disconnected" # Timed out or explicitly disconnected
    WAITING = "waiting"           # Turn started, waiting for action


@dataclass
class PlayerSession:
    """
    A connected player that can control entities.

    Attributes:
        session_id: Unique identifier for this session
        player_type: HUMAN, CLAUDE, or AI
        name: Display name for this player
        connection_status: Current connection state
        last_activity: Timestamp of last activity (for timeout detection)
        controlled_entities: Set of entity UUIDs this player can control
    """
    session_id: UUID
    player_type: PlayerType
    name: str
    connection_status: ConnectionStatus = ConnectionStatus.CONNECTED
    last_activity: float = field(default_factory=time.time)
    controlled_entities: Set[UUID] = field(default_factory=set)

    def ping(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()
        if self.connection_status == ConnectionStatus.DISCONNECTED:
            self.connection_status = ConnectionStatus.CONNECTED

    def disconnect(self) -> None:
        """Mark session as disconnected."""
        self.connection_status = ConnectionStatus.DISCONNECTED

    def is_timed_out(self, timeout_seconds: float = 30.0) -> bool:
        """Check if session has timed out."""
        return time.time() - self.last_activity > timeout_seconds

    def owns_entity(self, entity_uuid: UUID) -> bool:
        """Check if this session controls the given entity."""
        return entity_uuid in self.controlled_entities

    def to_dict(self) -> dict:
        """Serialize to dictionary for API responses."""
        return {
            "session_id": str(self.session_id),
            "player_type": self.player_type.value,
            "name": self.name,
            "connection_status": self.connection_status.value,
            "last_activity": self.last_activity,
            "controlled_entities": [str(e) for e in self.controlled_entities]
        }


@dataclass
class GameSession:
    """
    An active game with players and entity ownership.

    This is the single source of truth for:
    - Which players are in the game
    - Which entities each player controls
    - Whose turn it is (derived from encounter, not duplicated)

    Attributes:
        game_id: Unique identifier for this game
        encounter: The active encounter (turn-based combat)
        players: Dict mapping session_id -> PlayerSession
        entity_to_player: Dict mapping entity_uuid -> session_id (owner)
    """
    game_id: UUID
    encounter: Optional[Encounter] = None
    players: Dict[UUID, PlayerSession] = field(default_factory=dict)
    entity_to_player: Dict[UUID, UUID] = field(default_factory=dict)

    @property
    def active_entity_uuid(self) -> Optional[UUID]:
        """Get the UUID of the entity whose turn it is."""
        if not self.encounter:
            return None
        current = self.encounter.get_current_entity()
        return current.uuid if current else None

    @property
    def active_player(self) -> Optional[PlayerSession]:
        """Get the player whose turn it is."""
        entity_uuid = self.active_entity_uuid
        if not entity_uuid:
            return None
        player_id = self.entity_to_player.get(entity_uuid)
        if not player_id:
            return None
        return self.players.get(player_id)

    def add_player(self, session: PlayerSession) -> None:
        """Add a player to the game."""
        self.players[session.session_id] = session

    def remove_player(self, session_id: UUID) -> None:
        """Remove a player from the game."""
        if session_id in self.players:
            session = self.players[session_id]
            # Remove entity ownership mappings
            for entity_uuid in session.controlled_entities:
                if entity_uuid in self.entity_to_player:
                    del self.entity_to_player[entity_uuid]
            del self.players[session_id]

    def assign_entity(self, entity_uuid: UUID, session_id: UUID) -> bool:
        """
        Assign an entity to a player session.

        Returns True if successful, False if session doesn't exist.
        """
        if session_id not in self.players:
            return False

        # Remove from previous owner if any
        old_owner = self.entity_to_player.get(entity_uuid)
        if old_owner and old_owner in self.players:
            self.players[old_owner].controlled_entities.discard(entity_uuid)

        # Assign to new owner
        self.entity_to_player[entity_uuid] = session_id
        self.players[session_id].controlled_entities.add(entity_uuid)
        return True

    def get_entity_owner(self, entity_uuid: UUID) -> Optional[PlayerSession]:
        """Get the player who owns an entity."""
        session_id = self.entity_to_player.get(entity_uuid)
        if not session_id:
            return None
        return self.players.get(session_id)

    def is_entity_turn(self, entity_uuid: UUID) -> bool:
        """Check if it's the given entity's turn."""
        return self.active_entity_uuid == entity_uuid

    def is_player_turn(self, session_id: UUID) -> bool:
        """Check if it's the given player's turn.

        Returns True if the active entity is any of the session's controlled entities.
        """
        session = self.players.get(session_id)
        if not session:
            return False
        active_uuid = self.active_entity_uuid
        return active_uuid in session.controlled_entities if active_uuid else False

    def get_players_by_type(self, player_type: PlayerType) -> List[PlayerSession]:
        """Get all players of a given type."""
        return [p for p in self.players.values() if p.player_type == player_type]

    def to_dict(self) -> dict:
        """Serialize to dictionary for API responses."""
        return {
            "game_id": str(self.game_id),
            "encounter_active": self.encounter is not None and self.encounter.state.value == "active",
            "active_entity_uuid": str(self.active_entity_uuid) if self.active_entity_uuid else None,
            "players": {str(k): v.to_dict() for k, v in self.players.items()},
            "entity_to_player": {str(k): str(v) for k, v in self.entity_to_player.items()}
        }


class SessionManager:
    """
    Singleton managing all active sessions and games.

    Provides:
    - Session creation and lookup
    - Game creation and management
    - Action validation
    """

    _instance: Optional['SessionManager'] = None

    def __init__(self):
        self.sessions: Dict[UUID, PlayerSession] = {}
        self.games: Dict[UUID, GameSession] = {}
        self.active_game: Optional[GameSession] = None  # For single-game mode

    @classmethod
    def get(cls) -> 'SessionManager':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    def create_session(
        self,
        player_type: PlayerType,
        name: Optional[str] = None
    ) -> PlayerSession:
        """
        Create a new player session.

        Args:
            player_type: HUMAN, CLAUDE, or AI
            name: Display name (defaults to player_type if not provided)

        Returns:
            The created PlayerSession
        """
        session = PlayerSession(
            session_id=uuid4(),
            player_type=player_type,
            name=name or player_type.value.capitalize()
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: UUID) -> Optional[PlayerSession]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def remove_session(self, session_id: UUID) -> None:
        """Remove a session and clean up game associations."""
        if session_id in self.sessions:
            # Remove from any games
            for game in self.games.values():
                game.remove_player(session_id)
            del self.sessions[session_id]

    def create_game(self, encounter: Optional[Encounter] = None) -> GameSession:
        """
        Create a new game session.

        Args:
            encounter: Optional encounter to associate with the game

        Returns:
            The created GameSession
        """
        game = GameSession(
            game_id=uuid4(),
            encounter=encounter
        )
        self.games[game.game_id] = game
        self.active_game = game
        return game

    def get_game(self, game_id: UUID) -> Optional[GameSession]:
        """Get a game by ID."""
        return self.games.get(game_id)

    def get_active_game(self) -> Optional[GameSession]:
        """Get the active game (single-game mode)."""
        return self.active_game

    def validate_action(
        self,
        session_id: UUID,
        entity_uuid: UUID,
        game: Optional[GameSession] = None
    ) -> tuple:
        """
        Validate that a session can take an action with an entity.

        Checks:
        1. Session exists and is connected
        2. Session owns the entity
        3. Entity is the active entity (it's their turn)
        4. Turn is in progress

        Args:
            session_id: The session attempting the action
            entity_uuid: The entity performing the action
            game: Optional game session (uses active_game if not provided)

        Returns:
            Tuple of (PlayerSession, GameSession) if valid

        Raises:
            HTTPException with appropriate status code if invalid
        """
        # Get session
        session = self.get_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")

        # Check connection status
        if session.connection_status == ConnectionStatus.DISCONNECTED:
            raise HTTPException(status_code=401, detail="Session disconnected")

        # Update activity timestamp
        session.ping()

        # Get game
        game = game or self.active_game
        if not game:
            raise HTTPException(status_code=400, detail="No active game")

        # Check entity ownership
        if not session.owns_entity(entity_uuid):
            raise HTTPException(status_code=403, detail="You don't control this entity")

        # Check it's their turn
        if not game.is_entity_turn(entity_uuid):
            raise HTTPException(status_code=403, detail="Not this entity's turn")

        # Check turn state
        if game.encounter and game.encounter.turn_state != TurnState.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Turn not in progress")

        return session, game

    def cleanup_timed_out_sessions(self, timeout_seconds: float = 30.0) -> List[UUID]:
        """
        Clean up sessions that have timed out.

        Returns list of removed session IDs.
        """
        removed = []
        for session_id, session in list(self.sessions.items()):
            # Don't timeout AI sessions
            if session.player_type == PlayerType.AI:
                continue
            if session.is_timed_out(timeout_seconds):
                self.remove_session(session_id)
                removed.append(session_id)
        return removed


# Convenience function for getting the singleton
def get_session_manager() -> SessionManager:
    """Get the SessionManager singleton."""
    return SessionManager.get()
