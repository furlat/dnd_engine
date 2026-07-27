"""Durable lifecycle coordinator for one standalone local-profile game.

The coordinator contains no engine policy.  It serializes the existing
directory primitives around a standalone runtime so local and hosted games
share the same durable game, membership, lease, and pinned-deployment facts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from server.character_settlement import (
    build_terminal_settlement_bundle,
    project_terminal_character_holdings,
)
from server.character_deployment import build_character_deployment_snapshot
from server.character_directory_service import CharacterDirectoryService
from server.game_artifact_store import GameArtifactStore
from server.game_directory.contracts import (
    ArtifactCreate,
    CharacterDeploymentLeaseCreate,
    CharacterDeploymentLeaseRecord,
    CharacterRevisionBundleCommit,
    ExecutionKind,
    GameCreate,
    GameLifecycleState,
    GameRecord,
    JsonObject,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRecord,
    MembershipRole,
    ObserverPolicy,
    PinnedCharacterDeploymentCreate,
    PinnedCharacterDeploymentRecord,
    ProducerKind,
    VisibilityPolicy,
)
from server.game_directory.repository import GameDirectoryRepository
from server.game_runtime_identity import ENGINE_VERSION, RULESET_VERSION
from server.game_summary_store import WorkerSummaryEvidence
from server.objective_replay import ObjectiveReplayBundle
from server.player_replay import SubjectivePlayerReplayArchive
from server.terminal_evidence import (
    store_terminal_artifacts,
    validate_stored_terminal_artifacts,
)


class LocalTerminalCommitEnvelope(BaseModel):
    """Compact typed inputs needed to resume local terminal publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    game_id: UUID
    evidence: WorkerSummaryEvidence
    objective_replay_artifact: ArtifactCreate
    subjective_replay_artifact: ArtifactCreate
    settlement_bundle: CharacterRevisionBundleCommit | None = None
    lease_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class PreparedLocalGame:
    """Durable facts reserved before standalone engine materialization."""

    game: GameRecord
    membership: MembershipRecord
    character_snapshot: CharacterDeploymentSnapshot | None
    lease_id: UUID | None
    deployment_id: UUID | None
    runtime_entity_uuid: UUID | None = None


class StandaloneLocalGameCoordinator:
    """Own one process's pointer to durable local-game lifecycle facts."""

    def __init__(
        self,
        *,
        repository: GameDirectoryRepository,
        character_directory: CharacterDirectoryService,
        artifact_root: str | Path,
        owner_principal_id: UUID,
        content_digest: str,
        ruleset_version: str = RULESET_VERSION,
        engine_version: str = ENGINE_VERSION,
        on_mutation: Callable[[], None] | None = None,
    ) -> None:
        if not content_digest:
            raise ValueError("content_digest cannot be empty")
        self.repository = repository
        self.character_directory = character_directory
        self.artifact_store = GameArtifactStore(artifact_root)
        self.owner_principal_id = owner_principal_id
        self.content_digest = content_digest
        self.ruleset_version = ruleset_version
        self.engine_version = engine_version
        self._on_mutation = on_mutation
        self._current: PreparedLocalGame | None = None
        self._pending_terminal: tuple[
            LocalTerminalCommitEnvelope,
            str,
        ] | None = None

    @property
    def current(self) -> PreparedLocalGame | None:
        """Return the currently prepared durable local game, if any."""

        return self._current

    @property
    def membership_id(self) -> UUID | None:
        """Return the exact durable owner membership used by player replay."""

        current = self._current
        return None if current is None else current.membership.membership_id

    def prepare(
        self,
        *,
        creation_manifest: JsonObject,
        scenario_kind: str,
        scenario_id: str,
        display_name: str,
        character_id: UUID | None,
        seed: int | None = None,
    ) -> PreparedLocalGame:
        """Reserve STARTING game authority and lease the selected character."""

        if self._current is not None:
            raise RuntimeError(
                "current local game must be ended, failed, or interrupted "
                "before another game is prepared",
            )
        game = self.repository.create_game(
            GameCreate(
                engine_game_id=None,
                created_by_principal_id=self.owner_principal_id,
                lifecycle_state=GameLifecycleState.STARTING,
                visibility_policy=VisibilityPolicy.PRIVATE,
                observer_policy=ObserverPolicy.MEMBERS,
                execution_kind=ExecutionKind.LOCAL,
                scenario_kind=scenario_kind,
                scenario_id=scenario_id,
                display_name=display_name,
                creation_manifest=creation_manifest,
                seed=seed,
                ruleset_version=self.ruleset_version,
                engine_version=self.engine_version,
                content_digest=self.content_digest,
            ),
        )
        membership: MembershipRecord | None = None
        lease: CharacterDeploymentLeaseRecord | None = None
        try:
            membership = self.repository.create_membership(
                MembershipCreate(
                    game_id=game.game_id,
                    principal_id=self.owner_principal_id,
                    role=MembershipRole.OWNER,
                    side_id="side_a",
                    controller_kind="local_profile",
                    capabilities=MembershipCapabilities(
                        may_connect=True,
                        may_observe_public_state=True,
                        may_observe_subjective_state=True,
                        may_control_entities=True,
                        may_manage_members=True,
                        may_manage_game=True,
                        may_view_objective_replay=True,
                    ),
                ),
            )
            character_snapshot: CharacterDeploymentSnapshot | None = None
            deployment_id: UUID | None = None
            if character_id is not None:
                lease = self.repository.acquire_character_deployment_lease(
                    CharacterDeploymentLeaseCreate(
                        character_id=character_id,
                        game_id=game.game_id,
                        membership_id=membership.membership_id,
                    ),
                )
                character_snapshot = build_character_deployment_snapshot(
                    self.character_directory,
                    self.owner_principal_id,
                    character_id,
                )
                deployment_id = uuid4()
            prepared = PreparedLocalGame(
                game=game,
                membership=membership,
                character_snapshot=character_snapshot,
                lease_id=None if lease is None else lease.lease_id,
                deployment_id=deployment_id,
            )
            self._current = prepared
            self._publish_mutation()
            return prepared
        except BaseException:
            failed = self.repository.get_game(game.game_id)
            if failed.lifecycle_state is GameLifecycleState.STARTING:
                self.repository.terminate_game_and_release_leases(
                    game.game_id,
                    expected_row_version=failed.row_version,
                    lifecycle_state=GameLifecycleState.FAILED,
                    terminal_reason="local_game_prepare_failed",
                )
                self._publish_mutation()
            raise

    def pin_character(
        self,
        entity_uuid: UUID,
    ) -> PinnedCharacterDeploymentRecord | None:
        """Bind the leased character heads to its concrete runtime entity."""

        current = self._require_current()
        snapshot = current.character_snapshot
        if snapshot is None:
            return None
        if current.lease_id is None or current.deployment_id is None:
            raise RuntimeError("character-bearing local game has incomplete pins")
        deployment = self.repository.deploy_character_pinned(
            PinnedCharacterDeploymentCreate(
                deployment_id=current.deployment_id,
                game_id=current.game.game_id,
                membership_id=current.membership.membership_id,
                character_id=snapshot.character_id,
                entity_uuid=entity_uuid,
                lease_id=current.lease_id,
            ),
        )
        self._current = PreparedLocalGame(
            game=current.game,
            membership=current.membership,
            character_snapshot=current.character_snapshot,
            lease_id=current.lease_id,
            deployment_id=current.deployment_id,
            runtime_entity_uuid=entity_uuid,
        )
        return deployment

    def activate(self) -> GameRecord:
        """Cross the durable STARTING-to-ACTIVE boundary exactly once."""

        current = self._require_current()
        game = self.repository.get_game(current.game.game_id)
        if game.lifecycle_state is GameLifecycleState.ACTIVE:
            return game
        if game.lifecycle_state is not GameLifecycleState.STARTING:
            raise RuntimeError(
                f"local game cannot activate from {game.lifecycle_state.value}",
            )
        active = self.repository.transition_game(
            game.game_id,
            expected_row_version=game.row_version,
            lifecycle_state=GameLifecycleState.ACTIVE,
            engine_game_id=game.game_id,
        )
        self._replace_current_game(active)
        self._publish_mutation()
        return active

    def complete_terminal(
        self,
        *,
        evidence: WorkerSummaryEvidence,
        objective_replay: ObjectiveReplayBundle,
        subjective_replay: SubjectivePlayerReplayArchive,
    ) -> GameRecord:
        """Publish terminal evidence, settle holdings, and release the lease."""

        current = self._require_current()
        pending = self._pending_terminal
        if pending is not None:
            envelope, payload_digest = pending
            if envelope.game_id != current.game.game_id:
                raise RuntimeError(
                    "pending local terminal commit belongs to another game",
                )
            self._finalize_terminal_envelope(envelope, payload_digest)
            ended = self.repository.get_game(current.game.game_id)
            self._pending_terminal = None
            self._current = None
            self._publish_mutation()
            return ended
        settlement_bundle = (
            self._build_character_settlement(current, evidence)
            if current.character_snapshot is not None
            else None
        )
        known_memberships = frozenset(
            membership.membership_id
            for membership in self.repository.list_memberships(
                current.game.game_id,
            )
        )
        replay_artifact, subjective_artifact = store_terminal_artifacts(
            artifact_store=self.artifact_store,
            game_id=current.game.game_id,
            evidence=evidence,
            objective_replay=objective_replay,
            subjective_replay=subjective_replay,
            known_membership_ids=known_memberships,
            producer_kind=ProducerKind.WORKER,
            producer_version=self.engine_version,
        )
        envelope = LocalTerminalCommitEnvelope(
            game_id=current.game.game_id,
            evidence=evidence,
            objective_replay_artifact=replay_artifact,
            subjective_replay_artifact=subjective_artifact,
            settlement_bundle=settlement_bundle,
            lease_id=current.lease_id,
        )
        payload = envelope.model_dump(mode="json")
        payload_digest = self.repository.stage_local_terminal_commit(
            current.game.game_id,
            lease_id=current.lease_id,
            payload=payload,
        )
        self._pending_terminal = (envelope, payload_digest)
        self._finalize_terminal_envelope(envelope, payload_digest)
        ended = self.repository.get_game(current.game.game_id)
        self._pending_terminal = None
        self._current = None
        self._publish_mutation()
        return ended

    def fail(self, reason: str) -> GameRecord | None:
        """Fail the prepared game and release its character lease."""

        return self._finish_nonreplay_terminal(
            GameLifecycleState.FAILED,
            reason,
        )

    def interrupt(self, reason: str) -> GameRecord | None:
        """Interrupt a live/prepared game and release its character lease."""

        return self._finish_nonreplay_terminal(
            GameLifecycleState.INTERRUPTED,
            reason,
        )

    def recover_abandoned_games(self) -> tuple[UUID, ...]:
        """Interrupt prior-process STARTING/ACTIVE games and release leases."""

        recovered: list[UUID] = []
        for (
            game_id,
            lease_id,
            payload,
            payload_digest,
        ) in self.repository.list_pending_local_terminal_commits():
            envelope = LocalTerminalCommitEnvelope.model_validate(payload)
            if envelope.game_id != game_id or envelope.lease_id != lease_id:
                raise RuntimeError(
                    "staged local terminal identity does not match its row",
                )
            self._finalize_terminal_envelope(envelope, payload_digest)
            recovered.append(game_id)
        for state in (
            GameLifecycleState.STARTING,
            GameLifecycleState.ACTIVE,
        ):
            for game in self.repository.list_games(
                lifecycle_state=state,
                limit=1_000,
            ):
                if game.execution_kind is not ExecutionKind.LOCAL:
                    continue
                latest = self.repository.get_game(game.game_id)
                self.repository.terminate_game_and_release_leases(
                    game.game_id,
                    expected_row_version=latest.row_version,
                    lifecycle_state=GameLifecycleState.INTERRUPTED,
                    terminal_reason="local_game_process_recovered",
                )
                recovered.append(game.game_id)
        if recovered:
            self._publish_mutation()
        return tuple(sorted(recovered, key=lambda game_id: game_id.hex))

    def _finish_nonreplay_terminal(
        self,
        lifecycle_state: GameLifecycleState,
        reason: str,
    ) -> GameRecord | None:
        if not reason:
            raise ValueError("terminal reason cannot be empty")
        current = self._current
        if current is None:
            return None
        pending = self.repository.get_pending_local_terminal_commit(
            current.game.game_id,
        )
        if pending is not None:
            lease_id, payload, payload_digest = pending
            envelope = LocalTerminalCommitEnvelope.model_validate(payload)
            if (
                envelope.game_id != current.game.game_id
                or envelope.lease_id != lease_id
            ):
                raise RuntimeError(
                    "staged local terminal identity does not match its game",
                )
            self._finalize_terminal_envelope(envelope, payload_digest)
            ended = self.repository.get_game(current.game.game_id)
            self._pending_terminal = None
            self._current = None
            self._publish_mutation()
            return ended
        game = self.repository.get_game(current.game.game_id)
        if game.lifecycle_state in {
            GameLifecycleState.STARTING,
            GameLifecycleState.ACTIVE,
        }:
            game = self.repository.terminate_game_and_release_leases(
                game.game_id,
                expected_row_version=game.row_version,
                lifecycle_state=lifecycle_state,
                terminal_reason=reason,
            )
        self._current = None
        self._pending_terminal = None
        self._publish_mutation()
        return game

    def _publish_mutation(self) -> None:
        """Notify the deployment after a durable lifecycle transaction commits."""

        if self._on_mutation is not None:
            self._on_mutation()

    def _finalize_terminal_envelope(
        self,
        envelope: LocalTerminalCommitEnvelope,
        payload_digest: str,
    ) -> None:
        known_memberships = frozenset(
            membership.membership_id
            for membership in self.repository.list_memberships(
                envelope.game_id,
            )
        )
        validate_stored_terminal_artifacts(
            artifact_store=self.artifact_store,
            game_id=envelope.game_id,
            evidence=envelope.evidence,
            objective_artifact=envelope.objective_replay_artifact,
            subjective_artifact=envelope.subjective_replay_artifact,
            known_membership_ids=known_memberships,
        )
        self.repository.finalize_staged_local_terminal_commit(
            envelope.objective_replay_artifact,
            envelope.evidence.summary,
            additional_artifacts=(envelope.subjective_replay_artifact,),
            summary_revision=1,
            source_event_digest=envelope.evidence.source_event_digest,
            source_combat_log_digest=(
                envelope.evidence.source_combat_log_digest
            ),
            payload_digest=payload_digest,
            settlement_bundle=envelope.settlement_bundle,
            lease_id=envelope.lease_id,
        )

    def _build_character_settlement(
        self,
        current: PreparedLocalGame,
        evidence: WorkerSummaryEvidence,
    ) -> CharacterRevisionBundleCommit:
        snapshot = current.character_snapshot
        if (
            snapshot is None
            or current.deployment_id is None
            or current.runtime_entity_uuid is None
        ):
            raise RuntimeError(
                "terminal character settlement requires a pinned runtime",
            )
        holdings_evidence = project_terminal_character_holdings(
            snapshot,
            game_id=current.game.game_id,
            generation_id=evidence.generation_id,
            terminal_event_cursor=(
                evidence.summary.terminal_cursor.event_cursor
            ),
            terminal_combat_log_cursor=(
                evidence.summary.terminal_cursor.combat_log_cursor
            ),
            runtime_entity_uuid=current.runtime_entity_uuid,
        )
        deployment = next(
            row
            for row in self.repository.list_character_deployments(
                snapshot.character_id,
            )
            if row.deployment_id == current.deployment_id
        )
        return build_terminal_settlement_bundle(
            holdings_evidence,
            deployment,
            settlement_namespace="dnd-engine:local-character-settlement:v1",
        )

    def _replace_current_game(self, game: GameRecord) -> None:
        current = self._require_current()
        self._current = PreparedLocalGame(
            game=game,
            membership=current.membership,
            character_snapshot=current.character_snapshot,
            lease_id=current.lease_id,
            deployment_id=current.deployment_id,
            runtime_entity_uuid=current.runtime_entity_uuid,
        )

    def _require_current(self) -> PreparedLocalGame:
        current = self._current
        if current is None:
            raise RuntimeError("no local game is prepared")
        return current


__all__ = [
    "PreparedLocalGame",
    "StandaloneLocalGameCoordinator",
]
