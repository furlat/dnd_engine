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

from pydantic import BaseModel, ConfigDict, model_validator
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from server.canonical_json import canonical_json_sha256
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
    CharacterRevisionHeads,
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
from server.game_directory.errors import ConflictError
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
    settlement_bundles: tuple[CharacterRevisionBundleCommit, ...] = ()
    lease_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def _validate_settlement_leases(self) -> "LocalTerminalCommitEnvelope":
        if len(self.settlement_bundles) != len(self.lease_ids):
            raise ValueError(
                "terminal settlement bundles and leases must be one-to-one",
            )
        return self


@dataclass(frozen=True, slots=True)
class PreparedLocalCharacter:
    """One leased durable character awaiting or owning a runtime entity."""

    snapshot: CharacterDeploymentSnapshot
    lease_id: UUID
    deployment_id: UUID
    runtime_entity_uuid: UUID | None = None


@dataclass(frozen=True, slots=True)
class PreparedLocalGame:
    """Durable facts reserved before standalone engine materialization."""

    game: GameRecord
    membership: MembershipRecord
    characters: tuple[PreparedLocalCharacter, ...] = ()


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
        character_ids: tuple[UUID, ...],
        membership_roster_slot_id: str,
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
        try:
            membership = self.repository.create_membership(
                MembershipCreate(
                    game_id=game.game_id,
                    principal_id=self.owner_principal_id,
                    role=MembershipRole.OWNER,
                    side_id=membership_roster_slot_id,
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
            snapshots = tuple(
                build_character_deployment_snapshot(
                    self.character_directory,
                    self.owner_principal_id,
                    character_id,
                )
                for character_id in character_ids
            )
            lease_requests = tuple(
                CharacterDeploymentLeaseCreate(
                    character_id=snapshot.character_id,
                    game_id=game.game_id,
                    membership_id=membership.membership_id,
                )
                for snapshot in snapshots
            )
            leases = self.repository.acquire_character_deployment_leases(
                lease_requests,
            )
            characters = tuple(
                PreparedLocalCharacter(
                    snapshot=snapshot,
                    lease_id=lease.lease_id,
                    deployment_id=uuid4(),
                )
                for snapshot, lease in zip(
                    snapshots,
                    leases,
                    strict=True,
                )
            )
            prepared = PreparedLocalGame(
                game=game,
                membership=membership,
                characters=characters,
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

    def pin_characters(
        self,
        entity_uuids: dict[UUID, UUID],
    ) -> tuple[PinnedCharacterDeploymentRecord, ...]:
        """Bind every leased character head-set to its runtime entity."""

        current = self._require_current()
        expected_ids = {
            row.snapshot.character_id for row in current.characters
        }
        if set(entity_uuids) != expected_ids:
            raise RuntimeError(
                "runtime character entities do not match prepared leases",
            )
        deployments = self.repository.deploy_characters_pinned(
            tuple(
                PinnedCharacterDeploymentCreate(
                    deployment_id=row.deployment_id,
                    game_id=current.game.game_id,
                    membership_id=current.membership.membership_id,
                    character_id=row.snapshot.character_id,
                    entity_uuid=entity_uuids[row.snapshot.character_id],
                    lease_id=row.lease_id,
                )
                for row in current.characters
            ),
            expected_character_heads={
                row.snapshot.character_id: (
                    row.snapshot.character_row_version,
                    CharacterRevisionHeads(
                        definition_revision=(
                            row.snapshot.definition.definition_revision
                        ),
                        definition_digest=(
                            row.snapshot.definition.definition_digest
                        ),
                        holdings_revision=(
                            row.snapshot.holdings.holdings_revision
                        ),
                        holdings_digest=(
                            row.snapshot.holdings.holdings_digest
                        ),
                        loadout_revision=(
                            row.snapshot.loadout.loadout_revision
                        ),
                        loadout_digest=(
                            row.snapshot.loadout.loadout_digest
                        ),
                    ),
                )
                for row in current.characters
            },
        )
        self._current = PreparedLocalGame(
            game=current.game,
            membership=current.membership,
            characters=tuple(
                PreparedLocalCharacter(
                    snapshot=row.snapshot,
                    lease_id=row.lease_id,
                    deployment_id=row.deployment_id,
                    runtime_entity_uuid=entity_uuids[
                        row.snapshot.character_id
                    ],
                )
                for row in current.characters
            ),
        )
        return deployments

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
            if (
                canonical_json_sha256(evidence)
                != canonical_json_sha256(envelope.evidence)
                or canonical_json_sha256(objective_replay)
                != envelope.objective_replay_artifact.content_digest
                or canonical_json_sha256(subjective_replay)
                != envelope.subjective_replay_artifact.content_digest
            ):
                raise ConflictError(
                    "Local terminal retry evidence differs from the staged "
                    "terminal commit",
                )
            self._finalize_terminal_envelope(envelope, payload_digest)
            ended = self.repository.get_game(current.game.game_id)
            self._pending_terminal = None
            self._current = None
            self._publish_mutation()
            return ended
        settlement_bundles = self._build_character_settlements(
            current,
            evidence,
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
            settlement_bundles=settlement_bundles,
            lease_ids=tuple(
                row.lease_id for row in current.characters
            ),
        )
        payload = envelope.model_dump(mode="json")
        payload_digest = self.repository.stage_local_terminal_commit(
            current.game.game_id,
            lease_ids=envelope.lease_ids,
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
            lease_ids,
            payload,
            payload_digest,
        ) in self.repository.list_pending_local_terminal_commits():
            envelope = LocalTerminalCommitEnvelope.model_validate(payload)
            if (
                envelope.game_id != game_id
                or envelope.lease_ids != lease_ids
            ):
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
            lease_ids, payload, payload_digest = pending
            envelope = LocalTerminalCommitEnvelope.model_validate(payload)
            if (
                envelope.game_id != current.game.game_id
                or envelope.lease_ids != lease_ids
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
            settlement_bundles=envelope.settlement_bundles,
            lease_ids=envelope.lease_ids,
        )

    def _build_character_settlements(
        self,
        current: PreparedLocalGame,
        evidence: WorkerSummaryEvidence,
    ) -> tuple[CharacterRevisionBundleCommit, ...]:
        settlements: list[CharacterRevisionBundleCommit] = []
        for prepared in current.characters:
            runtime_entity_uuid = prepared.runtime_entity_uuid
            if runtime_entity_uuid is None:
                raise RuntimeError(
                    "terminal character settlement requires a pinned runtime",
                )
            holdings_evidence = project_terminal_character_holdings(
                prepared.snapshot,
                game_id=current.game.game_id,
                generation_id=evidence.generation_id,
                terminal_event_cursor=(
                    evidence.summary.terminal_cursor.event_cursor
                ),
                terminal_combat_log_cursor=(
                    evidence.summary.terminal_cursor.combat_log_cursor
                ),
                runtime_entity_uuid=runtime_entity_uuid,
            )
            deployments = self.repository.list_character_deployments(
                prepared.snapshot.character_id,
                game_id=current.game.game_id,
                lease_id=prepared.lease_id,
            )
            matching_deployments = tuple(
                row
                for row in deployments
                if row.deployment_id == prepared.deployment_id
            )
            if len(matching_deployments) != 1:
                raise ConflictError(
                    "Local terminal holdings evidence requires exactly one "
                    "matching pinned deployment",
                )
            settlements.append(build_terminal_settlement_bundle(
                holdings_evidence,
                matching_deployments[0],
                settlement_namespace=(
                    "dnd-engine:local-character-settlement:v1"
                ),
            ))
        return tuple(settlements)

    def _replace_current_game(self, game: GameRecord) -> None:
        current = self._require_current()
        self._current = PreparedLocalGame(
            game=game,
            membership=current.membership,
            characters=current.characters,
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
