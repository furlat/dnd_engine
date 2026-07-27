"""Focused durability and integrity gates for hosted terminal-ready evidence."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from dnd.core.content.durable_characters import CharacterHoldingsRevision
from dnd.runtime_reset import reset_engine_runtime
from server import worker_terminal_spool as spool_module
from server.canonical_json import canonical_json_bytes
from server.character_settlement import WorkerCharacterHoldingsEvidence
from server.event_stream import event_stream
from server.game_directory.contracts import CharacterRevisionHeads
from server.game_summary_store import WorkerGameSummaryStore, WorkerSummaryEvidence
from server.live_replication import create_stream_scene, execute_stream_attack
from server.objective_replay import ObjectiveReplayBundle
from server.player_replay import SubjectivePlayerReplayArchive
from server.worker_replay import build_worker_objective_replay
from server.worker_terminal_spool import (
    WorkerTerminalComponentKind,
    WorkerTerminalSpool,
    WorkerTerminalSpoolIntegrityError,
    WorkerTerminalSpoolNotReady,
)


@pytest.fixture(autouse=True)
def clean_runtime() -> Iterator[None]:
    """Keep retained engine/event identities isolated between spool fixtures."""

    event_stream.stop()
    reset_engine_runtime()
    event_stream.ensure_attached()
    yield
    event_stream.stop()
    reset_engine_runtime()


def _terminal_components(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    UUID,
    WorkerSummaryEvidence,
    ObjectiveReplayBundle,
    SubjectivePlayerReplayArchive,
    WorkerCharacterHoldingsEvidence,
]:
    """Build one small, internally consistent terminal component set."""

    game_id = uuid4()
    monkeypatch.setenv("DND_HOSTED_GAME_ID", str(game_id))
    scene = create_stream_scene()
    summary_store = WorkerGameSummaryStore()
    summary_store.capture_active_encounter(scene.encounter)
    execute_stream_attack(scene.hero, scene.monster, scene.encounter)
    scene.encounter.end_encounter("worker terminal spool fixture")
    summary = summary_store.get_evidence(game_id)
    capture = summary_store.get_replay_capture(game_id)
    assert summary is not None
    assert capture is not None
    objective = build_worker_objective_replay(
        capture,
        encounter=scene.encounter,
        stream=event_stream,
    )
    subjective = SubjectivePlayerReplayArchive(
        game_id=str(game_id),
        encounter_uuid=str(scene.encounter.uuid),
        terminal_source_event_cursor=capture.terminal_event_cursor,
        terminal_combat_log_cursor=capture.terminal_combat_log_cursor,
        opened_partition_count=0,
        membership_replays=(),
    )
    character_id = uuid4()
    opening_heads = CharacterRevisionHeads(
        definition_revision=1,
        definition_digest="a" * 64,
        holdings_revision=1,
        holdings_digest="b" * 64,
        loadout_revision=1,
        loadout_digest="c" * 64,
    )
    holdings = WorkerCharacterHoldingsEvidence(
        game_id=game_id,
        generation_id=summary.generation_id,
        terminal_event_cursor=capture.terminal_event_cursor,
        terminal_combat_log_cursor=capture.terminal_combat_log_cursor,
        runtime_entity_uuid=scene.hero.uuid,
        character_id=character_id,
        expected_row_version=1,
        expected_heads=opening_heads,
        resulting_holdings=CharacterHoldingsRevision.create(
            character_id=character_id,
            holdings_revision=2,
            items=(),
        ),
    )
    return game_id, summary, objective, subjective, holdings


def test_publish_writes_components_before_atomic_ready_manifest_and_roundtrips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready becomes visible last and authenticates every typed component."""

    game_id, summary, objective, subjective, holdings = _terminal_components(
        monkeypatch,
    )
    worker_instance_id = uuid4()
    spool = WorkerTerminalSpool(tmp_path / "game-runtime")
    published_paths: list[Path] = []
    original_publish = spool_module._publish_immutable_file

    def track_publish(
        path: Path,
        payload: bytes,
        *,
        directory: Path,
        label: str,
    ) -> None:
        if path == spool.ready_manifest_path:
            component_paths = (
                spool.ready_manifest_path.parent / "components"
            ).glob("*.json")
            assert len(tuple(component_paths)) == 4
        original_publish(
            path,
            payload,
            directory=directory,
            label=label,
        )
        published_paths.append(path)

    monkeypatch.setattr(
        spool_module,
        "_publish_immutable_file",
        track_publish,
    )
    manifest = spool.publish(
        game_id=game_id,
        worker_instance_id=worker_instance_id,
        worker_generation=7,
        summary=summary,
        objective_replay=objective,
        subjective_replay=subjective,
        holdings=holdings,
    )

    assert published_paths[-1] == spool.ready_manifest_path
    assert manifest.holdings is not None
    assert {
        descriptor.component_kind
        for descriptor in (
            manifest.summary,
            manifest.objective_replay,
            manifest.subjective_replay,
            manifest.holdings,
        )
    } == set(WorkerTerminalComponentKind)
    decoded = spool.read_ready(
        expected_game_id=game_id,
        expected_worker_instance_id=worker_instance_id,
        expected_worker_generation=7,
    )
    assert decoded.manifest == manifest
    assert decoded.summary == summary
    assert canonical_json_bytes(decoded.objective_replay) == canonical_json_bytes(
        objective,
    )
    assert canonical_json_bytes(decoded.subjective_replay) == canonical_json_bytes(
        subjective,
    )
    assert decoded.holdings == holdings

    ready_stat = spool.ready_manifest_path.stat()
    repeated = spool.publish(
        game_id=game_id,
        worker_instance_id=worker_instance_id,
        worker_generation=7,
        summary=summary,
        objective_replay=objective,
        subjective_replay=subjective,
        holdings=holdings,
    )
    assert repeated == manifest
    assert spool.ready_manifest_path.stat().st_ino == ready_stat.st_ino
    assert spool.ready_manifest_path.stat().st_mtime_ns == ready_stat.st_mtime_ns


def test_incomplete_spool_has_no_terminal_ready_boundary(tmp_path: Path) -> None:
    """Component-directory creation alone cannot be mistaken for readiness."""

    spool = WorkerTerminalSpool(tmp_path / "game-runtime")
    with pytest.raises(WorkerTerminalSpoolNotReady, match="does not exist"):
        spool.read_ready(
            expected_game_id=uuid4(),
            expected_worker_instance_id=uuid4(),
            expected_worker_generation=1,
        )


def test_read_rejects_wrong_worker_generation_and_component_corruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale generation or changed component can never be adopted."""

    game_id, summary, objective, subjective, holdings = _terminal_components(
        monkeypatch,
    )
    worker_instance_id = uuid4()
    spool = WorkerTerminalSpool(tmp_path / "game-runtime")
    manifest = spool.publish(
        game_id=game_id,
        worker_instance_id=worker_instance_id,
        worker_generation=3,
        summary=summary,
        objective_replay=objective,
        subjective_replay=subjective,
        holdings=holdings,
    )

    with pytest.raises(
        WorkerTerminalSpoolIntegrityError,
        match="identity or generation mismatch",
    ):
        spool.read_ready(
            expected_game_id=game_id,
            expected_worker_instance_id=worker_instance_id,
            expected_worker_generation=4,
        )

    objective_path = (
        spool.ready_manifest_path.parent
        / Path(manifest.objective_replay.relative_path)
    )
    payload = objective_path.read_bytes()
    objective_path.write_bytes(
        bytes((payload[0] ^ 1,)) + payload[1:],
    )
    with pytest.raises(
        WorkerTerminalSpoolIntegrityError,
        match="objective_replay digest mismatch",
    ):
        spool.read_ready(
            expected_game_id=game_id,
            expected_worker_instance_id=worker_instance_id,
            expected_worker_generation=3,
        )


def test_read_rejects_manifest_tampering_and_holdings_presence_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manifest self-digest binds its generation and optional holdings field."""

    game_id, summary, objective, subjective, holdings = _terminal_components(
        monkeypatch,
    )
    worker_instance_id = uuid4()
    spool = WorkerTerminalSpool(tmp_path / "game-runtime")
    spool.publish(
        game_id=game_id,
        worker_instance_id=worker_instance_id,
        worker_generation=2,
        summary=summary,
        objective_replay=objective,
        subjective_replay=subjective,
        holdings=holdings,
    )
    raw_manifest = json.loads(spool.ready_manifest_path.read_bytes())
    raw_manifest["holdings"] = None
    spool.ready_manifest_path.write_bytes(canonical_json_bytes(raw_manifest))

    with pytest.raises(
        WorkerTerminalSpoolIntegrityError,
        match="ready manifest is invalid",
    ):
        spool.read_ready(
            expected_game_id=game_id,
            expected_worker_instance_id=worker_instance_id,
            expected_worker_generation=2,
        )


def test_publish_rejects_holdings_from_another_terminal_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Holdings evidence cannot cross a game, generation, or cursor boundary."""

    game_id, summary, objective, subjective, holdings = _terminal_components(
        monkeypatch,
    )
    spool = WorkerTerminalSpool(tmp_path / "game-runtime")
    wrong_generation = holdings.model_copy(update={"generation_id": uuid4()})

    with pytest.raises(
        WorkerTerminalSpoolIntegrityError,
        match="holdings boundary mismatch",
    ):
        spool.publish(
            game_id=game_id,
            worker_instance_id=uuid4(),
            worker_generation=1,
            summary=summary,
            objective_replay=objective,
            subjective_replay=subjective,
            holdings=wrong_generation,
        )
