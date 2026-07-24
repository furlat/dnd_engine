"""Focused timeline and authority foundations for subjective replication."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from server.replication_perspective import PerspectiveEpochRegistry, PerspectiveScope
from server.runtime_authority import RuntimeProjectionAuthority, RuntimeScope
from server.session import PlayerSession, PlayerType
from server.subjective_authority import SubjectiveAuthorityError, resolve_subjective_authority
from server.timeline_contracts import (
    CombatLogFrame,
    CombatLogFramesResponse,
    CombatLogProjection,
)


def _entry(name: str) -> CombatLogEntry:
    return CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=name,
        source_uuid=str(uuid4()),
        compact=name,
        verbose=name,
        detailed=name,
    )


def _frame(
    cursor: int,
    *,
    entry: CombatLogEntry | None,
    generation_id: str = "generation-a",
    perspective_epoch_id: str = "perspective-a",
    source_stream_id: str = "stream-a",
) -> CombatLogFrame:
    return CombatLogFrame(
        source_stream_id=source_stream_id,
        generation_id=generation_id,
        perspective_epoch_id=perspective_epoch_id,
        projection=CombatLogProjection.SUBJECTIVE,
        combat_log_cursor=cursor,
        event_cursor=cursor * 10,
        entry=entry,
    )


def test_subjective_log_window_preserves_null_source_slots() -> None:
    response = CombatLogFramesResponse(
        source_stream_id="stream-a",
        generation_id="generation-a",
        perspective_epoch_id="perspective-a",
        projection=CombatLogProjection.SUBJECTIVE,
        retained_from_cursor=0,
        from_cursor=0,
        through_cursor=3,
        frames=(
            _frame(1, entry=_entry("A")),
            _frame(2, entry=None),
            _frame(3, entry=_entry("C")),
        ),
        total=3,
    )

    assert [frame.combat_log_cursor for frame in response.frames] == [1, 2, 3]
    assert [frame.entry is None for frame in response.frames] == [False, True, False]


@pytest.mark.parametrize(
    "frames",
    [
        (_frame(1, entry=_entry("A")), _frame(3, entry=_entry("C"))),
        (
            _frame(1, entry=_entry("A")),
            _frame(2, entry=None, perspective_epoch_id="perspective-b"),
        ),
        (
            _frame(1, entry=_entry("A")),
            _frame(2, entry=None, generation_id="generation-b"),
        ),
        (
            _frame(1, entry=_entry("A")),
            _frame(2, entry=None, source_stream_id="stream-b"),
        ),
    ],
)
def test_subjective_log_window_rejects_gaps_and_cross_epoch_frames(
    frames: tuple[CombatLogFrame, ...],
) -> None:
    with pytest.raises(ValidationError):
        CombatLogFramesResponse(
            source_stream_id="stream-a",
            generation_id="generation-a",
            perspective_epoch_id="perspective-a",
            projection=CombatLogProjection.SUBJECTIVE,
            retained_from_cursor=0,
            from_cursor=0,
            through_cursor=2,
            frames=frames,
            total=2,
        )


def test_perspective_epoch_rotates_only_when_projection_scope_changes() -> None:
    registry = PerspectiveEpochRegistry()
    session_id = str(uuid4())
    first_entity = str(uuid4())
    second_entity = str(uuid4())
    base = PerspectiveScope(
        session_id=session_id,
        membership_id=str(uuid4()),
        authority_epoch=1,
        projection=CombatLogProjection.SUBJECTIVE,
        controlled_entity_uuids=(first_entity,),
        observer_entity_uuids=(first_entity,),
        active_observer_uuid=first_entity,
    )

    first = registry.resolve(base)
    assert registry.resolve(base) == first
    changed = base.model_copy(update={
        "controlled_entity_uuids": (first_entity, second_entity),
        "observer_entity_uuids": (second_entity, first_entity),
    })
    second = registry.resolve(changed)
    assert second != first
    active_changed = changed.model_copy(update={"active_observer_uuid": second_entity})
    third = registry.resolve(active_changed)
    assert third not in {first, second}
    registry.clear_session(session_id)
    assert registry.resolve(active_changed) not in {first, second, third}


def test_subjective_authority_requires_trusted_scope_and_exact_ownership() -> None:
    session_id = uuid4()
    entity_id = uuid4()
    session = PlayerSession(
        session_id=session_id,
        player_type=PlayerType.HUMAN,
        name="Player",
        controlled_entities={entity_id},
    )
    session.synchronize_controlled_observers()
    authority = RuntimeProjectionAuthority(
        hosted_game_id=uuid4(),
        runtime_session_id=session_id,
        membership_id=uuid4(),
        scopes=frozenset({RuntimeScope.SUBJECTIVE_OBSERVE}),
        controlled_entity_uuids=frozenset({entity_id}),
        observer_entity_uuids=frozenset({entity_id}),
        active_observer_uuid=entity_id,
        authority_epoch=3,
    )
    registry = PerspectiveEpochRegistry()

    resolved = resolve_subjective_authority(session, authority, registry=registry)
    assert resolved.scope.authority_epoch == 3
    with pytest.raises(SubjectiveAuthorityError, match="trusted runtime authority"):
        resolve_subjective_authority(session, None, registry=registry)
    with pytest.raises(SubjectiveAuthorityError, match="another runtime session"):
        resolve_subjective_authority(
            session,
            authority.model_copy(update={"runtime_session_id": uuid4()}),
            registry=registry,
        )
    with pytest.raises(SubjectiveAuthorityError, match="ownership does not match"):
        resolve_subjective_authority(
            session,
            authority.model_copy(update={"controlled_entity_uuids": frozenset()}),
            registry=registry,
        )


def test_subjective_authority_accepts_explicit_zero_control_spectator_union() -> None:
    observer_ids = frozenset({uuid4(), uuid4()})
    session = PlayerSession(
        session_id=uuid4(),
        player_type=PlayerType.OBSERVER,
        name="Spectator",
    )
    authority = RuntimeProjectionAuthority(
        hosted_game_id=uuid4(),
        runtime_session_id=session.session_id,
        membership_id=uuid4(),
        scopes=frozenset({RuntimeScope.SUBJECTIVE_OBSERVE}),
        controlled_entity_uuids=frozenset(),
        observer_entity_uuids=observer_ids,
        active_observer_uuid=min(observer_ids, key=str),
        authority_epoch=2,
    )

    resolved = resolve_subjective_authority(session, authority)

    assert set(resolved.scope.observer_entity_uuids) == {
        str(entity_uuid) for entity_uuid in observer_ids
    }
    assert resolved.scope.active_observer_uuid == str(min(observer_ids, key=str))


def test_standalone_spectator_uses_only_join_time_observer_configuration() -> None:
    observer_ids = {uuid4(), uuid4()}
    active_observer = max(observer_ids, key=str)
    session = PlayerSession(
        session_id=uuid4(),
        player_type=PlayerType.OBSERVER,
        name="Standalone spectator",
    )
    session.configure_subjective_observers(
        observer_ids,
        active_observer_uuid=active_observer,
    )

    resolved = resolve_subjective_authority(
        session,
        None,
        allow_standalone=True,
        registry=PerspectiveEpochRegistry(),
    )

    assert resolved.scope.membership_id == f"standalone:{session.session_id}"
    assert set(resolved.scope.observer_entity_uuids) == {
        str(entity_uuid) for entity_uuid in observer_ids
    }
    assert resolved.scope.active_observer_uuid == str(active_observer)
