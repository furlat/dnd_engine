"""Session-based player authority and active-game ownership."""

from enum import Enum
from typing import Any, Dict, Iterable, Set, Optional, List
from uuid import UUID, uuid4
from dataclasses import dataclass, field
import time
from fastapi import HTTPException

from dnd.encounter import Encounter, TurnState


class PlayerType(str, Enum):
    """Type of player controlling entities."""

    HUMAN = "human"
    CODEX = "codex"
    AI = "ai"
    OBSERVER = "observer"


class ConnectionStatus(str, Enum):
    """Connection state of a player session."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    WAITING = "waiting"


@dataclass
class PlayerSession:
    """Represent a connected player that can control entities.

    Attributes:
        session_id: Unique identifier for this connected player session.
        player_type: Controller source for this session.
        name: Display name for this player.
        connection_status: Current connection state.
        last_activity: Timestamp of last activity for timeout detection.
        controlled_entities: Entity UUIDs this player can control.
        observer_entities: Entity UUIDs authorized for subjective observation.
        active_observer_uuid: Observer selected for observer-relative presentation.
    """

    session_id: UUID = field(metadata={"description": "Unique identifier for this connected player session."})
    player_type: PlayerType = field(metadata={"description": "Controller source for this session."})
    name: str = field(metadata={"description": "Display name for this player."})
    connection_status: ConnectionStatus = field(
        default=ConnectionStatus.CONNECTED,
        metadata={"description": "Current connection state."},
    )
    last_activity: float = field(
        default_factory=time.time,
        metadata={"description": "Timestamp of last activity for timeout detection."},
    )
    controlled_entities: Set[UUID] = field(
        default_factory=set,
        metadata={"description": "Entity UUIDs this player can control."},
    )
    observer_entities: Set[UUID] = field(
        default_factory=set,
        metadata={"description": "Explicit entity senses authorized for subjective replication."},
    )
    active_observer_uuid: Optional[UUID] = field(
        default=None,
        metadata={"description": "Observer selected for observer-relative presentation."},
    )

    def configure_subjective_observers(
        self,
        observer_entity_uuids: Iterable[UUID],
        *,
        active_observer_uuid: Optional[UUID] = None,
    ) -> None:
        """Install one explicit observer union without any objective fallback."""
        observers = set(observer_entity_uuids)
        active = active_observer_uuid
        if active is None and observers:
            active = min(observers, key=str)
        if active is not None and active not in observers:
            raise ValueError("Active observer must belong to the observer union")
        self.observer_entities = observers
        self.active_observer_uuid = active

    def synchronize_controlled_observers(self) -> None:
        """Keep participant knowledge exactly equal to its owned entities."""
        if self.player_type is PlayerType.OBSERVER:
            return
        active = self.active_observer_uuid
        if active not in self.controlled_entities:
            active = min(self.controlled_entities, key=str) if self.controlled_entities else None
        self.configure_subjective_observers(
            self.controlled_entities,
            active_observer_uuid=active,
        )

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
            "controlled_entities": [str(e) for e in self.controlled_entities],
            "observer_entities": [str(e) for e in sorted(self.observer_entities, key=str)],
            "active_observer_uuid": (
                str(self.active_observer_uuid) if self.active_observer_uuid is not None else None
            ),
        }


@dataclass
class GameSession:
    """Represent an active game with players and entity ownership.

    This is the single source of truth for:
    - Which players are in the game
    - Which entities each player controls
    - Whose turn it is (derived from encounter, not duplicated)

    Attributes:
        game_id: Unique identifier for this game session.
        encounter: Active turn-based encounter, if one is attached.
        players: Player sessions keyed by session UUID.
        entity_to_player: Owning session UUID keyed by controlled entity UUID.
    """

    game_id: UUID = field(metadata={"description": "Unique identifier for this game session."})
    encounter: Optional[Encounter] = field(
        default=None,
        metadata={"description": "Active turn-based encounter, if one is attached."},
    )
    players: Dict[UUID, PlayerSession] = field(
        default_factory=dict,
        metadata={"description": "Player sessions keyed by session UUID."},
    )
    entity_to_player: Dict[UUID, UUID] = field(
        default_factory=dict,
        metadata={"description": "Owning session UUID keyed by controlled entity UUID."},
    )

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

        old_owner = self.entity_to_player.get(entity_uuid)
        if old_owner and old_owner in self.players:
            self.players[old_owner].controlled_entities.discard(entity_uuid)
            self.players[old_owner].synchronize_controlled_observers()

        self.entity_to_player[entity_uuid] = session_id
        self.players[session_id].controlled_entities.add(entity_uuid)
        self.players[session_id].synchronize_controlled_observers()
        return True

    def unassign_entity(self, entity_uuid: UUID) -> None:
        """Remove any player ownership for one entity."""
        old_owner = self.entity_to_player.pop(entity_uuid, None)
        if old_owner and old_owner in self.players:
            self.players[old_owner].controlled_entities.discard(entity_uuid)
            self.players[old_owner].synchronize_controlled_observers()

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
        self.active_game: Optional[GameSession] = None

    @classmethod
    def get(cls) -> 'SessionManager':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton without invalidating existing owner references."""
        if cls._instance is None:
            return
        cls._instance.sessions.clear()
        cls._instance.games.clear()
        cls._instance.active_game = None

    def create_session(
        self,
        player_type: PlayerType,
        name: Optional[str] = None
    ) -> PlayerSession:
        """
        Create a new player session.

        Args:
            player_type: HUMAN, CODEX, or AI
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
            for game in self.games.values():
                game.remove_player(session_id)
            del self.sessions[session_id]

    def create_game(
        self,
        encounter: Optional[Encounter] = None,
        *,
        game_id: UUID | None = None,
    ) -> GameSession:
        """
        Create a new game session.

        Args:
            encounter: Optional encounter to associate with the game.
            game_id: Optional durable directory identity selected by the
                composition root. Direct engine callers receive a fresh UUID.

        Returns:
            The created GameSession
        """
        game = GameSession(
            game_id=uuid4() if game_id is None else game_id,
            encounter=encounter
        )
        if game.game_id in self.games:
            raise ValueError(f"Game session {game.game_id} already exists")
        self.games[game.game_id] = game
        self.active_game = game
        return game

    def get_game(self, game_id: UUID) -> Optional[GameSession]:
        """Get a game by ID."""
        return self.games.get(game_id)

    def get_active_game(self) -> Optional[GameSession]:
        """Get the active game (single-game mode)."""
        return self.active_game

    def _action_error_detail(
        self,
        code: str,
        message: str,
        session_id: UUID,
        entity_uuid: UUID,
        session: Optional[PlayerSession] = None,
        game: Optional[GameSession] = None,
    ) -> dict[str, Any]:
        """Build structured correction context for action-authority failures."""
        active_game = game or self.active_game
        active_entity_uuid = active_game.active_entity_uuid if active_game else None
        owner_session_id = active_game.entity_to_player.get(entity_uuid) if active_game else None
        return {
            "code": code,
            "message": message,
            "session_id": str(session_id),
            "entity_uuid": str(entity_uuid),
            "known_session_ids": [str(known_session_id) for known_session_id in self.sessions],
            "known_sessions": [known_session.to_dict() for known_session in self.sessions.values()],
            "active_game_id": str(active_game.game_id) if active_game else None,
            "active_entity_uuid": str(active_entity_uuid) if active_entity_uuid else None,
            "encounter_state": active_game.encounter.state.value if active_game and active_game.encounter else None,
            "turn_state": active_game.encounter.turn_state.value if active_game and active_game.encounter else None,
            "controlled_entities": [str(controlled) for controlled in session.controlled_entities] if session else [],
            "connection_status": session.connection_status.value if session else None,
            "entity_owner_session_id": str(owner_session_id) if owner_session_id else None,
        }

    def _action_http_exception(
        self,
        status_code: int,
        code: str,
        message: str,
        session_id: UUID,
        entity_uuid: UUID,
        session: Optional[PlayerSession] = None,
        game: Optional[GameSession] = None,
    ) -> HTTPException:
        """Create a structured action-authority HTTP exception."""
        return HTTPException(
            status_code=status_code,
            detail=self._action_error_detail(
                code=code,
                message=message,
                session_id=session_id,
                entity_uuid=entity_uuid,
                session=session,
                game=game,
            ),
        )

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
        session = self.get_session(session_id)
        if not session:
            raise self._action_http_exception(
                status_code=401,
                code="invalid_session",
                message="Invalid session",
                session_id=session_id,
                entity_uuid=entity_uuid,
                game=game,
            )

        if session.connection_status == ConnectionStatus.DISCONNECTED:
            raise self._action_http_exception(
                status_code=401,
                code="session_disconnected",
                message="Session disconnected",
                session_id=session_id,
                entity_uuid=entity_uuid,
                session=session,
                game=game,
            )

        session.ping()

        game = game or self.active_game
        if not game:
            raise self._action_http_exception(
                status_code=400,
                code="no_active_game",
                message="No active game",
                session_id=session_id,
                entity_uuid=entity_uuid,
                session=session,
                game=game,
            )

        if not session.owns_entity(entity_uuid):
            raise self._action_http_exception(
                status_code=403,
                code="entity_not_controlled",
                message="You don't control this entity",
                session_id=session_id,
                entity_uuid=entity_uuid,
                session=session,
                game=game,
            )

        if not game.is_entity_turn(entity_uuid):
            raise self._action_http_exception(
                status_code=403,
                code="not_entity_turn",
                message="Not this entity's turn",
                session_id=session_id,
                entity_uuid=entity_uuid,
                session=session,
                game=game,
            )

        if game.encounter and game.encounter.turn_state != TurnState.IN_PROGRESS:
            raise self._action_http_exception(
                status_code=400,
                code="turn_not_in_progress",
                message="Turn not in progress",
                session_id=session_id,
                entity_uuid=entity_uuid,
                session=session,
                game=game,
            )

        return session, game

    def cleanup_timed_out_sessions(self, timeout_seconds: float = 30.0) -> List[UUID]:
        """
        Clean up sessions that have timed out.

        Returns list of removed session IDs.
        """
        removed = []
        for session_id, session in list(self.sessions.items()):
            if session.player_type == PlayerType.AI:
                continue
            if session.is_timed_out(timeout_seconds):
                self.remove_session(session_id)
                removed.append(session_id)
        return removed


def get_session_manager() -> SessionManager:
    """Get the SessionManager singleton."""
    return SessionManager.get()
