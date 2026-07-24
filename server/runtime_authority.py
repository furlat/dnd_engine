"""In-memory authority for game-worker runtime requests."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from enum import Enum
from typing import Iterable, Mapping
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class RuntimeAuthorityError(RuntimeError):
    """Raised when a runtime capability is absent, invalid, or insufficient."""


class RuntimeScope(str, Enum):
    """Permissions understood by the hot gateway path."""

    OBSERVE = "observe"
    SUBJECTIVE_OBSERVE = "subjective_observe"
    CONTROL = "control"
    AGENT = "agent"
    ADMINISTER = "administer"


class RuntimeAuthority(BaseModel):
    """Validated hot authority installed after a cold attachment handshake."""

    model_config = ConfigDict(frozen=True)

    authority_id: UUID = Field(default_factory=uuid4, description="Runtime authority identity.")
    hosted_game_id: UUID = Field(description="Only game this authority may access.")
    runtime_session_id: UUID = Field(description="Worker session bound to this authority.")
    membership_id: UUID = Field(description="Durable membership that issued this authority.")
    scopes: frozenset[RuntimeScope] = Field(description="Hot-path permissions.")
    controlled_entity_uuids: frozenset[UUID] = Field(
        default_factory=frozenset,
        description="Entities this authority may command.",
    )
    observer_entity_uuids: frozenset[UUID] = Field(
        default_factory=frozenset,
        description="Explicit entity senses this authority may combine into a subjective perspective.",
    )
    active_observer_uuid: UUID | None = Field(
        default=None,
        description="Authorized observer selected for observer-relative presentation choices.",
    )
    takeover_claim_uuids: frozenset[UUID] = Field(
        default_factory=frozenset,
        description="Takeover leases this authority may keep alive.",
    )
    authority_epoch: int = Field(ge=1, description="Revocation/version epoch installed in memory.")
    issued_at: float = Field(description="Unix timestamp when the runtime token was issued.")
    expires_at: float = Field(description="Unix timestamp when the runtime token expires.")


class IssuedRuntimeAuthority(BaseModel):
    """One-time runtime capability response returned by attachment."""

    model_config = ConfigDict(frozen=True)

    token: str = Field(min_length=32, description="Secret bearer capability returned only to its holder.")
    authority: RuntimeAuthority = Field(description="Non-secret authority metadata.")


class RuntimeProjectionAuthority(BaseModel):
    """Non-secret authority claims forwarded over the private worker hop."""

    model_config = ConfigDict(frozen=True)

    hosted_game_id: UUID = Field(description="Hosted game selected by the gateway.")
    runtime_session_id: UUID = Field(description="Worker session bound to the capability.")
    membership_id: UUID = Field(description="Durable membership owning the capability.")
    scopes: frozenset[RuntimeScope] = Field(description="Validated hot-path permissions.")
    controlled_entity_uuids: frozenset[UUID] = Field(
        default_factory=frozenset,
        description="Entities this authority may command.",
    )
    observer_entity_uuids: frozenset[UUID] = Field(
        default_factory=frozenset,
        description="Explicit entity senses authorized for the subjective perspective.",
    )
    active_observer_uuid: UUID | None = Field(
        default=None,
        description="Observer selected for focus within the authorized subjective union.",
    )
    authority_epoch: int = Field(ge=1, description="Installed membership authority version.")


RUNTIME_PROJECTION_HEADER_PREFIX = "x-dnd-runtime-"
RUNTIME_GAME_HEADER = f"{RUNTIME_PROJECTION_HEADER_PREFIX}game-id"
RUNTIME_SESSION_HEADER = f"{RUNTIME_PROJECTION_HEADER_PREFIX}session-id"
RUNTIME_MEMBERSHIP_HEADER = f"{RUNTIME_PROJECTION_HEADER_PREFIX}membership-id"
RUNTIME_AUTHORITY_EPOCH_HEADER = f"{RUNTIME_PROJECTION_HEADER_PREFIX}authority-epoch"
RUNTIME_SCOPES_HEADER = f"{RUNTIME_PROJECTION_HEADER_PREFIX}scopes"
RUNTIME_CONTROLLED_ENTITIES_HEADER = f"{RUNTIME_PROJECTION_HEADER_PREFIX}controlled-entities"
RUNTIME_OBSERVER_ENTITIES_HEADER = f"{RUNTIME_PROJECTION_HEADER_PREFIX}observer-entities"
RUNTIME_ACTIVE_OBSERVER_HEADER = f"{RUNTIME_PROJECTION_HEADER_PREFIX}active-observer"


class RuntimeAuthorityCache:
    """Validate runtime access without consulting SQLite or engine state."""

    def __init__(self) -> None:
        """Create an empty hot authority cache."""
        self._by_digest: dict[str, RuntimeAuthority] = {}
        self._digests_by_game: dict[UUID, set[str]] = {}

    def issue(
        self,
        *,
        hosted_game_id: UUID,
        runtime_session_id: UUID,
        membership_id: UUID,
        scopes: Iterable[RuntimeScope],
        controlled_entity_uuids: Iterable[UUID] = (),
        observer_entity_uuids: Iterable[UUID] | None = None,
        active_observer_uuid: UUID | None = None,
        takeover_claim_uuids: Iterable[UUID] = (),
        authority_epoch: int = 1,
        ttl_seconds: float = 3600.0,
        now: float | None = None,
    ) -> IssuedRuntimeAuthority:
        """Issue and install a new game-scoped bearer capability."""
        issued_at = time.time() if now is None else now
        token = secrets.token_urlsafe(36)
        return self.install(
            token,
            hosted_game_id=hosted_game_id,
            runtime_session_id=runtime_session_id,
            membership_id=membership_id,
            scopes=scopes,
            controlled_entity_uuids=controlled_entity_uuids,
            observer_entity_uuids=observer_entity_uuids,
            active_observer_uuid=active_observer_uuid,
            takeover_claim_uuids=takeover_claim_uuids,
            authority_epoch=authority_epoch,
            expires_at=issued_at + ttl_seconds,
            issued_at=issued_at,
        )

    def install(
        self,
        token: str,
        *,
        hosted_game_id: UUID,
        runtime_session_id: UUID,
        membership_id: UUID,
        scopes: Iterable[RuntimeScope],
        controlled_entity_uuids: Iterable[UUID] = (),
        observer_entity_uuids: Iterable[UUID] | None = None,
        active_observer_uuid: UUID | None = None,
        takeover_claim_uuids: Iterable[UUID] = (),
        authority_epoch: int = 1,
        expires_at: float,
        issued_at: float | None = None,
    ) -> IssuedRuntimeAuthority:
        """Install a cold-handshake token into the hot authority cache."""
        installed_at = time.time() if issued_at is None else issued_at
        if expires_at <= installed_at:
            raise ValueError("Runtime authority must expire after it is issued")
        digest = _token_digest(token)
        controlled = frozenset(controlled_entity_uuids)
        observers = controlled if observer_entity_uuids is None else frozenset(observer_entity_uuids)
        active_observer = active_observer_uuid
        if active_observer is None and observers:
            active_observer = min(observers, key=str)
        if active_observer is not None and active_observer not in observers:
            raise ValueError("Active observer must belong to the authorized observer set")
        installed_scopes = frozenset(scopes)
        if RuntimeScope.SUBJECTIVE_OBSERVE in installed_scopes and active_observer is None:
            raise ValueError("Subjective observation authority requires an active observer")
        authority = RuntimeAuthority(
            hosted_game_id=hosted_game_id,
            runtime_session_id=runtime_session_id,
            membership_id=membership_id,
            scopes=installed_scopes,
            controlled_entity_uuids=controlled,
            observer_entity_uuids=observers,
            active_observer_uuid=active_observer,
            takeover_claim_uuids=frozenset(takeover_claim_uuids),
            authority_epoch=authority_epoch,
            issued_at=installed_at,
            expires_at=expires_at,
        )
        self._by_digest[digest] = authority
        self._digests_by_game.setdefault(hosted_game_id, set()).add(digest)
        return IssuedRuntimeAuthority(token=token, authority=authority)

    def validate(
        self,
        token: str,
        *,
        hosted_game_id: UUID,
        required_scope: RuntimeScope,
        now: float | None = None,
    ) -> RuntimeAuthority:
        """Validate a bearer token entirely from memory."""
        digest = _token_digest(token)
        authority = self._by_digest.get(digest)
        if authority is None:
            raise RuntimeAuthorityError("Unknown runtime capability")
        current_time = time.time() if now is None else now
        if current_time >= authority.expires_at:
            self.revoke(token)
            raise RuntimeAuthorityError("Runtime capability expired")
        if authority.hosted_game_id != hosted_game_id:
            raise RuntimeAuthorityError("Runtime capability belongs to another game")
        if required_scope not in authority.scopes and RuntimeScope.ADMINISTER not in authority.scopes:
            raise RuntimeAuthorityError(f"Runtime capability lacks {required_scope.value} scope")
        return authority

    def revoke(self, token: str) -> None:
        """Remove one runtime token from the in-memory cache."""
        digest = _token_digest(token)
        authority = self._by_digest.pop(digest, None)
        if authority is None:
            return
        game_digests = self._digests_by_game.get(authority.hosted_game_id)
        if game_digests is not None:
            game_digests.discard(digest)
            if not game_digests:
                self._digests_by_game.pop(authority.hosted_game_id, None)

    def revoke_game(self, hosted_game_id: UUID) -> None:
        """Remove all runtime tokens for one hosted game."""
        for digest in self._digests_by_game.pop(hosted_game_id, set()):
            self._by_digest.pop(digest, None)

    def revoke_membership(self, hosted_game_id: UUID, membership_id: UUID) -> None:
        """Remove every hot token issued for one game membership."""

        digests = self._digests_by_game.get(hosted_game_id, set()).copy()
        for digest in digests:
            authority = self._by_digest.get(digest)
            if authority is None or authority.membership_id != membership_id:
                continue
            self._by_digest.pop(digest, None)
            self._digests_by_game[hosted_game_id].discard(digest)
        if not self._digests_by_game.get(hosted_game_id):
            self._digests_by_game.pop(hosted_game_id, None)

    def replace_epoch(
        self,
        hosted_game_id: UUID,
        minimum_epoch: int,
    ) -> None:
        """Revoke cached authorities older than a control-plane epoch."""
        digests = self._digests_by_game.get(hosted_game_id, set()).copy()
        for digest in digests:
            authority = self._by_digest.get(digest)
            if authority is not None and authority.authority_epoch < minimum_epoch:
                self._by_digest.pop(digest, None)
                self._digests_by_game[hosted_game_id].discard(digest)


def extract_bearer_token(authorization: str | None) -> str:
    """Extract a bearer token from one HTTP Authorization header."""
    if authorization is None:
        raise RuntimeAuthorityError("Runtime bearer capability is required")
    scheme, separator, token = authorization.partition(" ")
    if separator == "" or scheme.lower() != "bearer" or not token.strip():
        raise RuntimeAuthorityError("Malformed runtime Authorization header")
    return token.strip()


def validate_session_binding(
    authority: RuntimeAuthority,
    *,
    path: str,
    query: Mapping[str, str],
    json_body: object | None,
) -> None:
    """Reject cross-session or uncontrolled-entity runtime requests."""
    expected_session = str(authority.runtime_session_id)
    session_values: list[str] = []
    query_session = query.get("session_id")
    if query_session is not None:
        session_values.append(query_session)

    path_parts = [part for part in path.strip("/").split("/") if part]
    for marker in ("session", "sessions"):
        if marker in path_parts:
            index = path_parts.index(marker)
            if index + 1 < len(path_parts):
                session_values.append(path_parts[index + 1])

    body_mapping = json_body if isinstance(json_body, dict) else None
    if body_mapping is not None:
        body_session = body_mapping.get("session_id")
        if isinstance(body_session, str):
            session_values.append(body_session)

    if any(not hmac.compare_digest(value, expected_session) for value in session_values):
        raise RuntimeAuthorityError("Request references another runtime session")

    entity_values: list[str] = []
    if "entity" in path_parts:
        index = path_parts.index("entity")
        if index + 1 < len(path_parts):
            entity_values.append(path_parts[index + 1])
    if body_mapping is not None:
        body_entity = body_mapping.get("entity_uuid")
        if isinstance(body_entity, str):
            entity_values.append(body_entity)

    if RuntimeScope.CONTROL in authority.scopes and entity_values:
        controlled = {str(entity_uuid) for entity_uuid in authority.controlled_entity_uuids}
        if any(value not in controlled for value in entity_values):
            raise RuntimeAuthorityError("Request references an uncontrolled entity")

    if path_parts[:2] == ["ai", "takeover"] and len(path_parts) >= 4:
        claim_value = path_parts[2]
        allowed_claims = {str(claim_uuid) for claim_uuid in authority.takeover_claim_uuids}
        if claim_value not in allowed_claims:
            raise RuntimeAuthorityError("Request references an unauthorized takeover claim")


def runtime_projection_headers(authority: RuntimeAuthority) -> dict[str, str]:
    """Serialize validated non-secret claims for the private gateway-worker hop."""
    return {
        RUNTIME_GAME_HEADER: str(authority.hosted_game_id),
        RUNTIME_SESSION_HEADER: str(authority.runtime_session_id),
        RUNTIME_MEMBERSHIP_HEADER: str(authority.membership_id),
        RUNTIME_AUTHORITY_EPOCH_HEADER: str(authority.authority_epoch),
        RUNTIME_SCOPES_HEADER: ",".join(sorted(scope.value for scope in authority.scopes)),
        RUNTIME_CONTROLLED_ENTITIES_HEADER: ",".join(
            sorted(str(entity_uuid) for entity_uuid in authority.controlled_entity_uuids)
        ),
        RUNTIME_OBSERVER_ENTITIES_HEADER: ",".join(
            sorted(str(entity_uuid) for entity_uuid in authority.observer_entity_uuids)
        ),
        RUNTIME_ACTIVE_OBSERVER_HEADER: (
            "" if authority.active_observer_uuid is None else str(authority.active_observer_uuid)
        ),
    }


def parse_runtime_projection_authority(
    headers: Mapping[str, str],
) -> RuntimeProjectionAuthority | None:
    """Parse trusted projection claims installed by the private gateway proxy.

    Direct standalone requests carry none of these headers and return ``None``.
    A partial or malformed claim set is rejected instead of being interpreted
    as weaker authority.
    """
    normalized = {key.lower(): value for key, value in headers.items()}
    names = (
        RUNTIME_GAME_HEADER,
        RUNTIME_SESSION_HEADER,
        RUNTIME_MEMBERSHIP_HEADER,
        RUNTIME_AUTHORITY_EPOCH_HEADER,
        RUNTIME_SCOPES_HEADER,
        RUNTIME_CONTROLLED_ENTITIES_HEADER,
        RUNTIME_OBSERVER_ENTITIES_HEADER,
        RUNTIME_ACTIVE_OBSERVER_HEADER,
    )
    present = [name in normalized for name in names]
    if not any(present):
        return None
    if not all(present):
        raise RuntimeAuthorityError("Incomplete runtime projection authority headers")

    try:
        scopes = frozenset(
            RuntimeScope(value)
            for value in normalized[RUNTIME_SCOPES_HEADER].split(",")
            if value
        )
        controlled = frozenset(
            UUID(value)
            for value in normalized[RUNTIME_CONTROLLED_ENTITIES_HEADER].split(",")
            if value
        )
        observers = frozenset(
            UUID(value)
            for value in normalized[RUNTIME_OBSERVER_ENTITIES_HEADER].split(",")
            if value
        )
        active_observer_value = normalized[RUNTIME_ACTIVE_OBSERVER_HEADER]
        active_observer = UUID(active_observer_value) if active_observer_value else None
        if active_observer is not None and active_observer not in observers:
            raise ValueError("active observer is outside the observer set")
        if RuntimeScope.SUBJECTIVE_OBSERVE in scopes and active_observer is None:
            raise ValueError("subjective authority has no active observer")
        return RuntimeProjectionAuthority(
            hosted_game_id=UUID(normalized[RUNTIME_GAME_HEADER]),
            runtime_session_id=UUID(normalized[RUNTIME_SESSION_HEADER]),
            membership_id=UUID(normalized[RUNTIME_MEMBERSHIP_HEADER]),
            scopes=scopes,
            controlled_entity_uuids=controlled,
            observer_entity_uuids=observers,
            active_observer_uuid=active_observer,
            authority_epoch=int(normalized[RUNTIME_AUTHORITY_EPOCH_HEADER]),
        )
    except (ValueError, TypeError) as exc:
        raise RuntimeAuthorityError("Malformed runtime projection authority headers") from exc


def _token_digest(token: str) -> str:
    """Return a stable digest without retaining bearer-token plaintext."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
