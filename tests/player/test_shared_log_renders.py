"""A native combat-log entry is rendered once per distinct disclosure and shared by the seats that decide alike
(each seat still decides what of it it may see); every seat's entry equals its own unshared projection."""

import random
from uuid import UUID, uuid5

import pytest

from dnd.core.events import EventPhase, EventQueue
from dnd.player.audience import PlayerAudience
from dnd.player.capture import SharedLogEntries, capture_lineages, seat_log_entry
from dnd.player.session import close_session, create_session
from dnd.runtime_reset import reset_engine_runtime
from tests.player.test_emitted_update_replica import SCENARIO, Step, move


@pytest.fixture
def session():
    state = random.getstate()
    random.seed(0)
    value = create_session()
    try:
        yield value
    finally:
        close_session(value)
        reset_engine_runtime()
        random.setstate(state)


def test_seats_deciding_alike_share_one_rendering_of_each_entry(session):
    # The replica scenario: moves, a logged step, dimmed light, a Fireball, a darkness the fighter walks into.
    sorcerer = session.player_uuids[1]
    session.game.entities[sorcerer].action_economy.set_normal_spell_slot_capacity(
        uuid5(sorcerer, 'shared-logs'), {level: 4 for level in range(1, 10)})
    actors = tuple(session.game.entities)
    native = {}
    for step in SCENARIO[:-1] + (Step('fighter walks into the darkness', move(0, (10, 10))),):
        start = EventQueue.event_cursor()
        step.act(session)
        roots = tuple(event for _, event in EventQueue.iter_events_since(start) if event.parent_lineage is None
                      and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
        native.update((identity, log) for lineage in capture_lineages(roots, observer_uuid=sorcerer)
                      for identity, log in lineage.native_logs.items())
    # Every actor as its own seat, the party seat, and a spectator through each actor.
    audiences = (*(PlayerAudience((identity,), (identity,)) for identity in actors), session.seats['party'],
                 *(PlayerAudience((), (identity,)) for identity in actors))
    names = {str(identity): entity.name for identity, entity in session.game.entities.items()}
    shared = SharedLogEntries()
    seen: dict[UUID, set[str]] = {}
    projections = 0
    for audience in audiences:
        alone, together = {}, {}
        for identity, log in native.items():
            expected = seat_log_entry(log, audience, known_entity_names=names, retained_entries=alone)
            assert seat_log_entry(log, audience, known_entity_names=names, retained_entries=together,
                                  shared=shared) == expected
            seen.setdefault(identity, set()).add(repr(expected))
            projections += expected is not None
    # The seats do not all see the same entries, and seats deciding alike share renderings.
    assert any(len(entries) > 1 for entries in seen.values())
    assert len(shared.entries) < projections
