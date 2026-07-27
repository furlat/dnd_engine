"""Transport-neutral game-history queries and their shared HTTP routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response

from server.game_artifact_store import GameArtifactStore, ArtifactStoreError
from server.game_directory.contracts import (
    ArtifactKind,
    ArtifactRecord,
    DirectoryEventRecord,
    FinalSummaryRecord,
    GameLifecycleState,
    GameRecord,
    MembershipState,
    VisibilityPolicy,
)
from server.game_directory.errors import NotFoundError
from server.game_directory.repository import GameDirectoryRepository
from server.game_history_contracts import GameHistoryListResponse
from server.objective_replay import ObjectiveReplayBundle
from server.player_replay import (
    SubjectivePlayerReplayArchive,
    SubjectivePlayerReplayBundle,
)
from server.terminal_evidence import (
    OBJECTIVE_REPLAY_SCHEMA_VERSION,
    SUBJECTIVE_REPLAY_SCHEMA_VERSION,
)


@dataclass(frozen=True, slots=True)
class GameHistoryQueryError(RuntimeError):
    """Stable cold-history failure shared by both deployment shapes."""

    status_code: int
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class GameHistoryQueryService:
    """Read directory history and immutable replay files without runtime state."""

    def __init__(
        self,
        repository: GameDirectoryRepository,
        artifact_store: GameArtifactStore,
    ) -> None:
        self.repository = repository
        self.artifact_store = artifact_store

    def list_visible_games(
        self,
        principal_id: UUID | None,
    ) -> GameHistoryListResponse:
        """List public games plus private games seated by the principal."""

        games = self.repository.list_games(limit=500)
        visible: list[GameRecord] = []
        for game in games:
            if game.visibility_policy is VisibilityPolicy.PUBLIC:
                visible.append(game)
                continue
            if principal_id is None:
                continue
            if self._principal_has_membership(game.game_id, principal_id):
                visible.append(game)
        return GameHistoryListResponse(games=visible, count=len(visible))

    def directory_event_filter(
        self,
        principal_id: UUID | None,
    ) -> Callable[[DirectoryEventRecord], bool]:
        """Build the canonical public-or-member directory visibility rule."""

        def event_is_visible(event: DirectoryEventRecord) -> bool:
            if event.game_id is None:
                return False
            try:
                game = self.repository.get_game(event.game_id)
            except NotFoundError:
                return False
            if game.visibility_policy is VisibilityPolicy.PUBLIC:
                return True
            return (
                principal_id is not None
                and self._principal_has_membership(
                    event.game_id,
                    principal_id,
                )
            )

        return event_is_visible

    def require_visible_game(
        self,
        game_id: UUID,
        principal_id: UUID | None,
    ) -> GameRecord:
        """Resolve one public or principal-owned game without leaking private IDs."""

        try:
            game = self.repository.get_game(game_id)
        except NotFoundError as exc:
            raise GameHistoryQueryError(
                404,
                "game_not_found",
                "Game was not found",
            ) from exc
        if game.visibility_policy is VisibilityPolicy.PUBLIC:
            return game
        if (
            principal_id is None
            or not self._principal_has_membership(game_id, principal_id)
        ):
            raise GameHistoryQueryError(
                404,
                "game_not_found",
                "Game was not found",
            )
        return game

    def get_summary(
        self,
        game_id: UUID,
        principal_id: UUID | None,
    ) -> FinalSummaryRecord:
        """Read one visible game's current immutable terminal summary."""

        self.require_visible_game(game_id, principal_id)
        try:
            return self.repository.get_current_summary(game_id)
        except NotFoundError as exc:
            raise GameHistoryQueryError(
                404,
                "game_summary_not_found",
                "Game summary was not found",
            ) from exc

    def get_objective_replay(
        self,
        game_id: UUID,
        principal_id: UUID,
    ) -> ObjectiveReplayBundle:
        """Read objective evidence only for an explicitly capable seat."""

        game = self._require_terminal_game(game_id, "objective")
        authorized = any(
            membership.principal_id == principal_id
            and membership.membership_state
            in {MembershipState.ACTIVE, MembershipState.DISCONNECTED}
            and membership.capabilities.may_view_objective_replay
            for membership in self.repository.list_memberships(game_id)
        )
        if not authorized:
            raise GameHistoryQueryError(
                403,
                "objective_replay_denied",
                "Principal may not read objective replay evidence",
            )
        artifact = self._require_artifact(
            game_id,
            ArtifactKind.REPLAY_BUNDLE,
            schema_version=OBJECTIVE_REPLAY_SCHEMA_VERSION,
            label="objective_replay",
        )
        payload = self._read_artifact_bytes(artifact, label="objective_replay")
        try:
            replay = ObjectiveReplayBundle.model_validate_json(payload)
        except ValueError as exc:
            raise GameHistoryQueryError(
                500,
                "objective_replay_contract_invalid",
                "Objective replay bytes do not match the canonical contract",
            ) from exc
        if replay.game_id != str(game_id):
            raise GameHistoryQueryError(
                500,
                "objective_replay_game_mismatch",
                "Objective replay belongs to another game",
            )
        summary = self.repository.get_current_summary(game_id).summary
        if replay.encounter_uuid != str(summary.encounter_uuid):
            raise GameHistoryQueryError(
                500,
                "objective_replay_encounter_mismatch",
                "Objective replay describes another encounter",
            )
        if (
            replay.terminal_event_cursor != game.final_event_cursor
            or replay.terminal_combat_log_cursor
            != game.final_combat_log_cursor
        ):
            raise GameHistoryQueryError(
                500,
                "objective_replay_cursor_mismatch",
                "Objective replay disagrees with terminal game cursors",
            )
        return replay

    def get_subjective_replay(
        self,
        game_id: UUID,
        membership_id: UUID,
        principal_id: UUID,
    ) -> SubjectivePlayerReplayBundle:
        """Read exactly one principal-owned membership replay."""

        self._require_terminal_game(game_id, "subjective")
        try:
            membership = self.repository.get_membership(membership_id)
        except NotFoundError as exc:
            raise GameHistoryQueryError(
                404,
                "subjective_replay_membership_not_found",
                "Game membership was not found",
            ) from exc
        if (
            membership.game_id != game_id
            or membership.principal_id != principal_id
            or membership.membership_state
            not in {MembershipState.ACTIVE, MembershipState.DISCONNECTED}
            or not membership.capabilities.may_observe_subjective_state
        ):
            raise GameHistoryQueryError(
                403,
                "subjective_replay_denied",
                "Principal may not read this membership's player replay",
            )
        archive = self.read_subjective_archive(game_id)
        replay = next(
            (
                candidate
                for candidate in archive.membership_replays
                if candidate.membership_id == str(membership_id)
            ),
            None,
        )
        if replay is None:
            raise GameHistoryQueryError(
                404,
                "subjective_replay_missing",
                "No canonical player replay was recorded for this membership",
            )
        return replay

    def read_subjective_archive(
        self,
        game_id: UUID,
    ) -> SubjectivePlayerReplayArchive:
        game = self.repository.get_game(game_id)
        artifact = self._require_artifact(
            game_id,
            ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
            schema_version=SUBJECTIVE_REPLAY_SCHEMA_VERSION,
            label="subjective_replay",
        )
        payload = self._read_artifact_bytes(
            artifact,
            label="subjective_replay",
        )
        try:
            archive = SubjectivePlayerReplayArchive.model_validate_json(
                payload,
            )
        except ValueError as exc:
            raise GameHistoryQueryError(
                500,
                "subjective_replay_contract_invalid",
                "Player replay bytes do not match the canonical contract",
            ) from exc
        if archive.game_id != str(game_id):
            raise GameHistoryQueryError(
                500,
                "subjective_replay_game_mismatch",
                "Player replay archive belongs to another game",
            )
        summary = self.repository.get_current_summary(game_id).summary
        if archive.encounter_uuid != str(summary.encounter_uuid):
            raise GameHistoryQueryError(
                500,
                "subjective_replay_encounter_mismatch",
                "Player replay archive describes another encounter",
            )
        if (
            archive.terminal_source_event_cursor != game.final_event_cursor
            or archive.terminal_combat_log_cursor
            != game.final_combat_log_cursor
        ):
            raise GameHistoryQueryError(
                500,
                "subjective_replay_cursor_mismatch",
                "Player replay archive disagrees with terminal game cursors",
            )
        return archive

    def _require_terminal_game(
        self,
        game_id: UUID,
        label: str,
    ) -> GameRecord:
        try:
            game = self.repository.get_game(game_id)
        except NotFoundError as exc:
            raise GameHistoryQueryError(
                404,
                "game_not_found",
                "Game was not found",
            ) from exc
        if game.lifecycle_state not in {
            GameLifecycleState.ENDED,
            GameLifecycleState.ARCHIVED,
        }:
            raise GameHistoryQueryError(
                409,
                f"{label}_replay_not_terminal",
                "Replay is available only for ended or archived games",
            )
        return game

    def _principal_has_membership(
        self,
        game_id: UUID,
        principal_id: UUID,
    ) -> bool:
        return any(
            membership.principal_id == principal_id
            and membership.membership_state
            in {MembershipState.ACTIVE, MembershipState.DISCONNECTED}
            for membership in self.repository.list_memberships(game_id)
        )

    def _require_artifact(
        self,
        game_id: UUID,
        artifact_kind: ArtifactKind,
        *,
        schema_version: str,
        label: str,
    ) -> ArtifactRecord:
        artifacts = self.repository.list_artifacts(
            game_id,
            artifact_kind=artifact_kind,
        )
        if not artifacts:
            raise GameHistoryQueryError(
                404,
                f"{label}_missing",
                "Replay artifact was not found",
            )
        if len(artifacts) != 1:
            raise GameHistoryQueryError(
                409,
                f"{label}_ambiguous",
                "Multiple replay artifacts are registered",
            )
        artifact = artifacts[0]
        if (
            artifact.schema_version != schema_version
            or artifact.media_type != "application/json"
        ):
            raise GameHistoryQueryError(
                500,
                f"{label}_metadata_invalid",
                "Replay metadata contract is invalid",
            )
        return artifact

    def _read_artifact_bytes(
        self,
        artifact: ArtifactRecord,
        *,
        label: str,
    ) -> bytes:
        try:
            payload = self.artifact_store.read_bytes(
                artifact.content_digest,
            )
        except ArtifactStoreError as exc:
            raise GameHistoryQueryError(
                500,
                f"{label}_integrity_failed",
                str(exc),
            ) from exc
        if len(payload) != artifact.byte_size:
            raise GameHistoryQueryError(
                500,
                f"{label}_size_mismatch",
                "Replay byte size does not match directory metadata",
            )
        return payload


ResolveHistoryService = Callable[[Request], GameHistoryQueryService]
AuthorizeOptionalPrincipal = Callable[
    [Request, UUID | None, str | None],
    UUID | None,
]
AuthorizeRequiredPrincipal = Callable[[Request, UUID, str], UUID]


def create_game_history_router(
    *,
    resolve_service: ResolveHistoryService,
    authorize_optional_principal: AuthorizeOptionalPrincipal,
    authorize_required_principal: AuthorizeRequiredPrincipal,
) -> APIRouter:
    """Build the one canonical cold-history route family."""

    router = APIRouter()

    def raise_query_error(exc: GameHistoryQueryError) -> NoReturn:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    @router.get("/games", response_model=GameHistoryListResponse)
    async def list_games(
        request: Request,
        principal_id: UUID | None = Header(
            default=None,
            alias="X-Dnd-Principal-Id",
        ),
        principal_capability: str | None = Header(
            default=None,
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> GameHistoryListResponse:
        principal = authorize_optional_principal(
            request,
            principal_id,
            principal_capability,
        )
        return resolve_service(request).list_visible_games(principal)

    @router.get("/games/{game_id}", response_model=GameRecord)
    async def get_game(
        game_id: UUID,
        request: Request,
        principal_id: UUID | None = Header(
            default=None,
            alias="X-Dnd-Principal-Id",
        ),
        principal_capability: str | None = Header(
            default=None,
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> GameRecord:
        principal = authorize_optional_principal(
            request,
            principal_id,
            principal_capability,
        )
        try:
            return resolve_service(request).require_visible_game(
                game_id,
                principal,
            )
        except GameHistoryQueryError as exc:
            raise_query_error(exc)

    @router.get(
        "/games/{game_id}/summary",
        response_model=FinalSummaryRecord,
    )
    async def get_summary(
        game_id: UUID,
        request: Request,
        principal_id: UUID | None = Header(
            default=None,
            alias="X-Dnd-Principal-Id",
        ),
        principal_capability: str | None = Header(
            default=None,
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> FinalSummaryRecord:
        principal = authorize_optional_principal(
            request,
            principal_id,
            principal_capability,
        )
        try:
            return resolve_service(request).get_summary(game_id, principal)
        except GameHistoryQueryError as exc:
            raise_query_error(exc)

    @router.get(
        "/games/{game_id}/diagnostics/objective-replay",
        response_model=ObjectiveReplayBundle,
    )
    async def get_objective_replay(
        game_id: UUID,
        request: Request,
        response: Response,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> ObjectiveReplayBundle:
        principal = authorize_required_principal(
            request,
            principal_id,
            principal_capability,
        )
        try:
            replay = resolve_service(request).get_objective_replay(
                game_id,
                principal,
            )
        except GameHistoryQueryError as exc:
            raise_query_error(exc)
        response.headers["Cache-Control"] = "private, no-store"
        return replay

    @router.get(
        "/games/{game_id}/memberships/{membership_id}/replay",
        response_model=SubjectivePlayerReplayBundle,
    )
    async def get_subjective_replay(
        game_id: UUID,
        membership_id: UUID,
        request: Request,
        response: Response,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> SubjectivePlayerReplayBundle:
        principal = authorize_required_principal(
            request,
            principal_id,
            principal_capability,
        )
        try:
            replay = resolve_service(request).get_subjective_replay(
                game_id,
                membership_id,
                principal,
            )
        except GameHistoryQueryError as exc:
            raise_query_error(exc)
        response.headers["Cache-Control"] = "private, no-store"
        return replay

    return router


__all__ = [
    "GameHistoryQueryError",
    "GameHistoryQueryService",
    "create_game_history_router",
]
