"""Runtime control leasing for Codex takeover of autonomous combatants."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, Optional
from uuid import UUID, uuid4

from dnd.controller import CodexController, Controller, ExternalAIController
from dnd.encounter import Encounter
from dnd.entity import Entity
from server.session import GameSession, PlayerSession, PlayerType, SessionManager


class TakeoverError(RuntimeError):
    """Base error for takeover failures."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        """Create a structured takeover error."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass
class ClaimedEntityState:
    """Restoration state for one claimed combatant."""

    entity_uuid: UUID
    previous_controller_uuid: UUID
    previous_owner_session_id: Optional[UUID]


@dataclass
class TakeoverClaim:
    """Live Codex control claim over one group of combatants."""

    claim_id: UUID
    session_id: UUID
    entity_states: dict[UUID, ClaimedEntityState]
    created_at: float
    last_heartbeat_at: float
    lease_seconds: float
    name: str
    faction: Optional[str] = None

    @property
    def entity_uuids(self) -> list[UUID]:
        """Return claimed entity UUIDs in stable order."""
        return sorted(self.entity_states, key=str)

    @property
    def expires_at(self) -> float:
        """Return the absolute expiry timestamp."""
        return self.last_heartbeat_at + self.lease_seconds

    def is_expired(self, now: Optional[float] = None) -> bool:
        """Return whether this claim has exceeded its lease."""
        return (now if now is not None else time.time()) >= self.expires_at

    def heartbeat(self, now: Optional[float] = None) -> None:
        """Refresh the claim lease."""
        self.last_heartbeat_at = now if now is not None else time.time()


class AITakeoverManager:
    """Manage runtime Codex controller claims and restoration."""

    def __init__(self) -> None:
        """Create an empty takeover manager."""
        self._claims: dict[UUID, TakeoverClaim] = {}

    def active_claims(self, now: Optional[float] = None) -> list[TakeoverClaim]:
        """Return non-expired claims."""
        check_time = now if now is not None else time.time()
        return [claim for claim in self._claims.values() if not claim.is_expired(check_time)]

    def get_claim(self, claim_id: UUID) -> Optional[TakeoverClaim]:
        """Return a claim by UUID."""
        return self._claims.get(claim_id)

    def claim(
        self,
        *,
        encounter: Encounter,
        game: GameSession,
        session_manager: SessionManager,
        faction: Optional[str] = "monsters",
        entity_uuids: Optional[Iterable[UUID]] = None,
        session_id: Optional[UUID] = None,
        name: str = "Codex Monsters",
        force: bool = False,
        lease_seconds: float = 120.0,
    ) -> TakeoverClaim:
        """Claim combatants for Codex control."""
        self.restore_expired(encounter, game)
        targets = self._resolve_targets(encounter, faction, entity_uuids)
        if not targets:
            raise TakeoverError("no_claim_targets", "No matching combatants can be claimed", 404)

        conflicts = self._conflicting_claims(targets)
        if conflicts and not force:
            raise TakeoverError("takeover_conflict", "Requested combatants are already claimed", 409)
        for conflict in conflicts:
            self.release(conflict.claim_id, encounter, game)

        session = self._resolve_or_create_session(session_manager, session_id, name)
        game.add_player(session)

        now = time.time()
        entity_states: dict[UUID, ClaimedEntityState] = {}
        for entity_uuid in targets:
            previous_controller = encounter.get_controller_for(entity_uuid)
            if previous_controller is None:
                raise TakeoverError(
                    "controller_not_found",
                    f"Combatant {entity_uuid} has no controller",
                    500,
                )
            previous_owner_session_id = game.entity_to_player.get(entity_uuid)
            codex_controller = CodexController(source_entity_uuid=entity_uuid)
            previous_controller_uuid = encounter.set_controller_for(entity_uuid, codex_controller)
            game.assign_entity(entity_uuid, session.session_id)
            entity_states[entity_uuid] = ClaimedEntityState(
                entity_uuid=entity_uuid,
                previous_controller_uuid=previous_controller_uuid,
                previous_owner_session_id=previous_owner_session_id,
            )

        claim = TakeoverClaim(
            claim_id=uuid4(),
            session_id=session.session_id,
            entity_states=entity_states,
            created_at=now,
            last_heartbeat_at=now,
            lease_seconds=lease_seconds,
            name=name,
            faction=faction,
        )
        self._claims[claim.claim_id] = claim
        return claim

    def release(
        self,
        claim_id: UUID,
        encounter: Optional[Encounter],
        game: Optional[GameSession],
    ) -> Optional[TakeoverClaim]:
        """Release one claim and restore previous ownership."""
        claim = self._claims.pop(claim_id, None)
        if claim is None:
            return None
        if encounter is None or game is None:
            return claim

        for state in claim.entity_states.values():
            entity = Entity.get(state.entity_uuid)
            if entity is None or state.entity_uuid not in encounter.combatants:
                continue
            previous_controller = Controller.get(state.previous_controller_uuid)
            if previous_controller is None:
                previous_controller = ExternalAIController(source_entity_uuid=state.entity_uuid)
            encounter.set_controller_for(state.entity_uuid, previous_controller)
            if state.previous_owner_session_id is None:
                game.unassign_entity(state.entity_uuid)
            elif state.previous_owner_session_id in game.players:
                game.assign_entity(state.entity_uuid, state.previous_owner_session_id)
            else:
                game.unassign_entity(state.entity_uuid)
        return claim

    def heartbeat(self, claim_id: UUID) -> Optional[TakeoverClaim]:
        """Refresh a claim lease."""
        claim = self._claims.get(claim_id)
        if claim is None:
            return None
        claim.heartbeat()
        return claim

    def restore_expired(
        self,
        encounter: Optional[Encounter],
        game: Optional[GameSession],
        now: Optional[float] = None,
    ) -> list[TakeoverClaim]:
        """Release and return all expired claims."""
        check_time = now if now is not None else time.time()
        expired = [
            claim for claim in self._claims.values()
            if claim.is_expired(check_time)
        ]
        for claim in expired:
            self.release(claim.claim_id, encounter, game)
        return expired

    def clear(self, encounter: Optional[Encounter] = None, game: Optional[GameSession] = None) -> None:
        """Release all claims and clear manager state."""
        for claim_id in list(self._claims):
            self.release(claim_id, encounter, game)
        self._claims.clear()

    def _resolve_or_create_session(
        self,
        session_manager: SessionManager,
        session_id: Optional[UUID],
        name: str,
    ) -> PlayerSession:
        """Return a valid Codex session for a claim."""
        if session_id is None:
            return session_manager.create_session(PlayerType.CODEX, name)
        session = session_manager.get_session(session_id)
        if session is None:
            raise TakeoverError("session_not_found", "Requested Codex session was not found", 404)
        if session.player_type != PlayerType.CODEX:
            raise TakeoverError("invalid_session_type", "Takeover session must be a Codex session", 400)
        return session

    def _resolve_targets(
        self,
        encounter: Encounter,
        faction: Optional[str],
        entity_uuids: Optional[Iterable[UUID]],
    ) -> list[UUID]:
        """Resolve requested target combatants."""
        if entity_uuids is not None:
            requested = list(entity_uuids)
            return [
                entity_uuid for entity_uuid in requested
                if entity_uuid in encounter.combatants
            ]
        return [
            entity.uuid for entity in Entity.get_all_entities()
            if entity.uuid in encounter.combatants and (faction is None or entity.faction == faction)
        ]

    def _conflicting_claims(self, entity_uuids: list[UUID]) -> list[TakeoverClaim]:
        """Return live claims that overlap the requested entity UUIDs."""
        requested = set(entity_uuids)
        return [
            claim for claim in self.active_claims()
            if requested.intersection(claim.entity_states)
        ]
