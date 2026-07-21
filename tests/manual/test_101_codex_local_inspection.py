"""Safe immutable local inspection over Codex subjective state."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import cast

import pytest
from pydantic import JsonValue

from ai.codex_tools.representation.inspection import (
    ArchiveLookupStatus,
    InspectionArchive,
    InspectionDiffOperation,
    InspectionDiffRequest,
    InspectionDocumentTooLarge,
    InspectionGetRequest,
    InspectionGetStatus,
    InspectionSearchMatchKind,
    InspectionSearchMode,
    InspectionSearchRequest,
    InspectionSerializationError,
    JsonValueType,
    capture_inspection_document,
)
from ai.observation.models import (
    KnowledgeState,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationSessionState,
    ObservationTileFact,
    SubjectiveWorldState,
)
from ai.subjective.models import AgentState


def test_capture_is_immutable_canonical_and_digest_stable() -> None:
    """Captured bytes do not follow mutable inputs and ignore mapping insertion order."""
    world = _world()
    agent_state = AgentState(variables={"focus": {"door": "closed"}})
    predicates = {
        "door.reachable": {"truth": "unknown", "evidence": ["door"]},
        "nullable": None,
    }
    representation = {
        "profile_id": "codex.balanced-v2",
        "components": ["core.turn", "contacts.partition"],
    }
    document = capture_inspection_document(
        world=world,
        agent_state=agent_state,
        predicates=predicates,
        representation=representation,
    )
    same_document = capture_inspection_document(
        world=_world(),
        agent_state=AgentState(variables={"focus": {"door": "closed"}}),
        predicates=dict(reversed(tuple(predicates.items()))),
        representation=dict(reversed(tuple(representation.items()))),
    )
    original_bytes = document.canonical_bytes

    world.known_entities["enemy/one~x"].hp = 1
    agent_state.variables["focus"]["door"] = "open"
    predicates["nullable"] = "changed"
    representation["profile_id"] = "changed"

    assert document.canonical_bytes == original_bytes
    assert document.revision.document_digest == same_document.revision.document_digest
    captured = cast(dict[str, JsonValue], document.value())
    captured_world = cast(dict[str, JsonValue], captured["world"])
    captured_entities = cast(dict[str, JsonValue], captured_world["known_entities"])
    captured_enemy = cast(dict[str, JsonValue], captured_entities["enemy/one~x"])
    assert captured_enemy["hp"] == 12
    assert sha256(document.canonical_bytes).hexdigest() == document.revision.document_digest


def test_exact_get_uses_json_pointers_and_preserves_missing_versus_null() -> None:
    """Exact reads support escaping while never traversing Python attributes."""
    document = _document()
    result = document.get(InspectionGetRequest(
        pointers=(
            "/world/known_entities/enemy~1one~0x/name",
            "/world/known_objects/door/state/is_open",
            "/world/known_entities/missing",
            "/__class__",
            "/world/~2invalid",
            "",
        ),
    ))

    assert result.items[0].status is InspectionGetStatus.FOUND
    assert result.items[0].value == "Goblin Scout"
    assert result.items[1].status is InspectionGetStatus.FOUND
    assert result.items[1].value_type is JsonValueType.NULL
    assert result.items[1].value is None
    assert result.items[2].status is InspectionGetStatus.MISSING
    assert result.items[3].status is InspectionGetStatus.MISSING
    assert result.items[4].status is InspectionGetStatus.INVALID_POINTER
    assert result.items[5].status is InspectionGetStatus.INVALID_POINTER

    limited = document.get(InspectionGetRequest(
        pointers=("/world",),
        max_response_bytes=64,
    ))
    assert limited.items[0].status is InspectionGetStatus.RESPONSE_LIMIT
    assert limited.items[0].value is None


def test_search_is_literal_deterministic_bounded_and_subjective() -> None:
    """Search discovers canonical local facts without inventing hidden entities."""
    document = _document()
    request = InspectionSearchRequest(
        pattern="door",
        mode=InspectionSearchMode.CONTAINS,
        roots=("world", "agent_state", "missing-root"),
        limit=2,
    )

    first = document.search(request)
    second = document.search(request)

    assert first == second
    assert first.total_matches >= 3
    assert len(first.hits) == 2
    assert first.truncated is True
    assert first.unknown_roots == ("missing-root",)
    assert all(hit.pointer.startswith(("/world", "/agent_state")) for hit in first.hits)
    assert document.search(InspectionSearchRequest(pattern="objective-secret")).total_matches == 0

    exact = document.search(InspectionSearchRequest(
        pattern="Ancient Door",
        mode=InspectionSearchMode.EXACT,
        roots=("/world/known_objects",),
        match_paths=False,
    ))
    assert len(exact.hits) == 1
    assert exact.hits[0].match_kind is InspectionSearchMatchKind.VALUE
    assert exact.hits[0].pointer == "/world/known_objects/door/name"

    prefix = document.search(InspectionSearchRequest(
        pattern="/world/known_entities/enemy",
        mode=InspectionSearchMode.PREFIX,
        roots=("world",),
        match_values=False,
        limit=200,
    ))
    assert prefix.total_matches > 1
    assert all(hit.match_kind is InspectionSearchMatchKind.PATH for hit in prefix.hits)


def test_export_catalog_and_schema_describe_only_allowlisted_roots() -> None:
    """Export and discovery metadata identify exact bytes and open JSON fields."""
    document = _document()
    exported = document.export()
    catalog = document.catalog()
    schema = document.schema_bundle()
    parsed = json.loads(exported.canonical_json)

    assert exported.byte_count == len(exported.canonical_json.encode("utf-8"))
    assert sha256(exported.canonical_json.encode("utf-8")).hexdigest() == exported.document_digest
    assert set(parsed) == {
        "revision",
        "world",
        "observation_frames",
        "agent_state",
        "predicates",
        "representation",
    }
    assert schema.schema_digest == document.revision.schema_digest
    assert set(schema.schemas) >= {
        "world",
        "observation_frames",
        "agent_state",
        "predicates",
        "representation",
    }
    assert "/world/known_objects/*/state" in schema.open_json_paths
    summaries = {row.name: row for row in catalog.roots}
    assert summaries["world.known_entities"].item_count == 2
    assert summaries["world.known_objects"].item_count == 1
    assert "diff" in catalog.supported_operations


def test_archive_produces_structural_diff_and_distinguishes_eviction() -> None:
    """Historical comparison uses retained bytes and reports eviction explicitly."""
    before = _document(cursor=3, enemy_hp=12)
    after = _document(cursor=4, enemy_hp=8)
    newest = _document(cursor=5, enemy_hp=7)
    archive = InspectionArchive(max_documents=2, max_bytes=4_000_000)
    archive.add(before)
    archive.add(after)

    diff = archive.diff(InspectionDiffRequest(
        before_digest=before.revision.document_digest,
        after_digest=after.revision.document_digest,
        root="/world/known_entities/enemy~1one~0x",
    ))
    changes = {row.pointer: row for row in diff.changes}

    assert diff.available is True
    assert diff.before_status is ArchiveLookupStatus.RETAINED
    assert changes["/world/known_entities/enemy~1one~0x/hp"].operation is InspectionDiffOperation.REPLACE
    assert changes["/world/known_entities/enemy~1one~0x/hp"].before == 12
    assert changes["/world/known_entities/enemy~1one~0x/hp"].after == 8

    assert archive.add(newest) == (before.revision.document_digest,)
    evicted = archive.diff(InspectionDiffRequest(
        before_digest=before.revision.document_digest,
        after_digest=newest.revision.document_digest,
    ))
    assert evicted.available is False
    assert evicted.before_status is ArchiveLookupStatus.EVICTED
    assert evicted.after_status is ArchiveLookupStatus.RETAINED

    unknown = archive.diff(InspectionDiffRequest(
        before_digest="f" * 64,
        after_digest=newest.revision.document_digest,
    ))
    assert unknown.before_status is ArchiveLookupStatus.UNKNOWN


def test_capture_rejects_non_finite_and_non_json_values_and_archive_oversize() -> None:
    """Open mappings cannot smuggle runtime objects or invalid numbers into inspection."""
    with pytest.raises(InspectionSerializationError, match="non-finite"):
        capture_inspection_document(
            world=_world(),
            agent_state=AgentState(),
            predicates={"bad": float("nan")},
            representation={"profile_id": "test"},
        )
    with pytest.raises(InspectionSerializationError, match="Unsupported"):
        capture_inspection_document(
            world=_world(),
            agent_state=AgentState(),
            predicates={"bad": object()},
            representation={"profile_id": "test"},
        )

    document = _document()
    with pytest.raises(InspectionDocumentTooLarge):
        InspectionArchive(max_bytes=1).add(document)


def _document(*, cursor: int = 3, enemy_hp: int = 12):
    return capture_inspection_document(
        world=_world(cursor=cursor, enemy_hp=enemy_hp),
        agent_state=AgentState(variables={
            "object_focus": {"kind": "door", "state": "closed"},
            "nullable": None,
        }),
        predicates={
            "door.reachable": {"truth": "unknown"},
            "enemy.visible": {"truth": "true"},
        },
        representation={
            "profile_id": "codex.balanced-v2",
            "manifest_digest": "manifest-test",
            "components": ["core.turn", "objects.ledger"],
        },
        materialization_generation=1,
        processor_generation=2,
    )


def _world(*, cursor: int = 3, enemy_hp: int = 12) -> SubjectiveWorldState:
    session = ObservationSessionState(
        session_id="session",
        player_type="codex",
        name="Codex",
        connection_status="connected",
        controlled_entity_uuids=["actor"],
        active_entity_uuid="actor",
        active_entity_name="Hero",
        is_my_turn=False,
    )
    encounter = ObservationEncounterState(
        uuid="encounter",
        name="Inspection Arena",
        state="in_progress",
        round_number=2,
        current_turn_index=0,
        current_entity_uuid="actor",
        current_entity_name="Hero",
    )
    return SubjectiveWorldState(
        observation_cursor=cursor,
        session=session,
        encounter=encounter,
        observers={
            "actor": ObservationObserverState(
                observer_uuid="actor",
                entity_name="Hero",
                position=(2, 3),
                passive_perception=12,
                visible_cells=[(2, 3), (3, 3)],
                seen_cells=[(1, 3), (2, 3), (3, 3)],
                visible_entity_uuids=["enemy/one~x"],
                visible_object_uuids=["door"],
            ),
        },
        known_entities={
            "actor": ObservationEntityFact(
                uuid="actor",
                name="Hero",
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                controlled=True,
                position=(2, 3),
                hp=20,
                max_hp=20,
                faction="heroes",
                is_dead=False,
            ),
            "enemy/one~x": ObservationEntityFact(
                uuid="enemy/one~x",
                name="Goblin Scout",
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                position=(4, 3),
                hp=enemy_hp,
                max_hp=12,
                faction="monsters",
                is_dead=False,
            ),
        },
        known_objects={
            "door": ObservationObjectFact(
                uuid="door",
                name="Ancient Door",
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                position=(3, 3),
                state={"is_open": None, "material": "oak"},
            ),
        },
        known_tiles={
            "2,3": ObservationTileFact(
                key="2,3",
                position=(2, 3),
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                name="Stone Floor",
                walkable=True,
                walking_cost=5,
                is_hazardous=False,
            ),
        },
        combat_logs=[{"compact": "Hero spots the Ancient Door", "data": {"door": "door"}}],
    )
