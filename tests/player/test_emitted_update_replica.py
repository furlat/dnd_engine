"""Emitted updates, folded the way the client folds them, reproduce what the seat's projection knows.

The server keeps no replica of a seat's client state. Its projection fold
(`ProjectionState.remembered`) is what capture and the worker read, and the
bodies it patches against, so the client fold of the detached updates must
agree with it on every body and on everything else read there, and the
client's composed view must equal a cold composition of its folded member
senses. The HUD each seat shows equals the live engine (the op-end oracle).
"""

from dataclasses import dataclass
import random
from typing import Callable
from uuid import uuid4, uuid5

import pytest
from pydantic import TypeAdapter

from dnd.actions import DropConcentration, Move
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EmptyLogData
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.player.application import AudienceRuntime, capture_application_operation, initialize_audiences
from dnd.player.audience import PlayerAudience, begin_audience_composition
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import PlayerInitialization, PlayerState, PlayerUpdate
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import Operation, Session, close_session, create_session, publish_sheets
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import Darkness
from dnd.spells.evocation import Fireball
from dnd.types.world import LightLevel
from tests.player.test_hud_operation_oracle import live, shown


INITIALIZATION = TypeAdapter(PlayerInitialization)


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


@dataclass(frozen=True)
class Step:
    name: str
    act: Callable[[Session], None]


def operation_since(session: Session, start: int) -> Operation:
    # As an operation ends: the sheet publication, then the interval.
    publish_sheets(session)
    originals = tuple(session.logs.log_appends)
    session.logs.log_appends.clear()
    return Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(),
        roots=tuple(event for _, event in EventQueue.iter_events_since(start)
            if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)),
        original_logs=originals)


def what_capture_reads(state: PlayerState) -> tuple:
    return (state.actors, state.items, state.spatial_content, state.connectors, state.content,
        state.tiles, state.objects)


def check_replica(session: Session, steps: tuple[Step, ...]) -> dict[str, PlayerState]:
    catalog = ui_content_manifest()
    runtimes, initializations = initialize_audiences(session, catalog)
    clients = {seat: reduce_initialization(INITIALIZATION.validate_json(INITIALIZATION.dump_json(initial)),
            content_additions=runtimes[seat].projection.remembered.content)
        for seat, initial in initializations.items()}

    def check(name: str, seat: str, client: PlayerState, runtime: AudienceRuntime) -> None:
        case = f'{name} / {seat}'
        assert what_capture_reads(client) == what_capture_reads(runtime.projection.remembered), case
        assert (client.reducer_cursor, len(client.combat_log_appends)) == (
            runtime.projection.next_occurrence, runtime.projection.next_log_append), case
        assert client.senses == begin_audience_composition(client.perception, client.observer_uuid).view, case
        assert shown(client) == live(session, seat), case

    for seat, client in clients.items():
        check('initialization', seat, client, runtimes[seat])
    for step in steps:
        start = EventQueue.event_cursor()
        step.act(session)
        updates = capture_application_operation(runtimes, operation_since(session, start), catalog)
        for seat, update in updates.items():
            clients[seat] = reduce_operation(clients[seat], PlayerUpdate.model_validate_json(update.model_dump_json()))
            check(step.name, seat, clients[seat], runtimes[seat])
    return clients


def entity(session: Session, index: int):
    return session.game.entities[session.player_uuids[index]]


def enemies(session: Session):
    return [actor for identity, actor in session.game.entities.items() if identity not in session.player_uuids]


def move(index: int, destination: tuple[int, int]) -> Callable[[Session], None]:
    def act(session: Session) -> None:
        actor = entity(session, index)
        actor.action_economy.reset_all_costs()
        outcome = Move(source_entity_uuid=actor.uuid, end_position=destination, use_register=False).apply()
        assert outcome is not None and not outcome.canceled and actor.position == destination, (
            outcome and outcome.status_message)
    return act


def cast(spell, aim: tuple[int, int], level: int) -> Callable[[Session], None]:
    def act(session: Session) -> None:
        caster = entity(session, 1)
        caster.action_economy.reset_all_costs()
        with fixed_dice_faces(*([6] * 120)):
            outcome = spell(source_entity_uuid=caster.uuid, end_position=aim, use_register=False,
                caster_level=20, cast_at_level=level).apply()
        assert outcome is not None and not outcome.canceled, outcome and outcome.status_message
        session.encounter.check_deaths()
    return act


def dim_light(session: Session) -> None:
    cells = {(x, y) for x in range(5, 10) for y in range(9, 14)}
    assert get_map().apply_light_modifier(uuid4(), cells, LightLevel.DIM_LIGHT, cap=True)


def enemies_die(session: Session) -> None:
    cast(Fireball, (13, 11), 3)(session)
    assert enemies(session) and all(actor.health.life_state is LifeState.DEAD for actor in enemies(session))


def darkness_ends(session: Session) -> None:
    caster = entity(session, 1)
    outcome = DropConcentration(source_entity_uuid=caster.uuid, use_register=False).apply()
    assert outcome is not None and not outcome.canceled


def logged_step(session: Session) -> None:
    move(0, (6, 11))(session)
    actor = entity(session, 0)
    text = f'{actor.name} checks the passage.'
    EventQueue.push_combat_log(CombatLogEntry(entry_type=CombatLogEntryType.ACTION,
        source_uuid=str(actor.uuid), source_name=actor.name,
        compact=text, verbose=text, detailed=text, data=EmptyLogData()), actor.uuid)
    assert session.logs.log_appends


# The 15x15 arena: the party at (10, 10) and (10, 12), the enemies at (14, 10) and (14, 12).
# The log step precedes the deaths: the encounter (and its combat log) ends with the last enemy.
SCENARIO = (
    Step('fighter falls back', move(0, (6, 10))),
    Step('fighter steps aside with a log entry', logged_step),
    Step('sorcerer falls back', move(1, (7, 12))),
    Step('light dims around the party', dim_light),
    Step('fireball kills both enemies', enemies_die),
    Step('darkness zone installs', cast(Darkness, (12, 11), 2)),
    Step('fighter walks up to the darkness', move(0, (8, 10))),
    Step('darkness zone ends', darkness_ends),
)


def test_client_fold_of_emitted_updates_matches_projection_and_cold_composition(session):
    fighter, sorcerer = session.player_uuids
    # A second, single-observer seat beside the two-observer party seat.
    session.seats['fighter'] = PlayerAudience((fighter,), (fighter,))
    session.game.entities[sorcerer].action_economy.set_normal_spell_slot_capacity(
        uuid5(sorcerer, 'replica'), {level: 4 for level in range(1, 10)})
    # The composed session already published its sheets; this change reaches them as any operation's end does.
    publish_sheets(session)
    clients = check_replica(session, SCENARIO)
    for client in clients.values():
        assert tuple(row.encounter_log_index for row in client.combat_log_appends) == tuple(
            range(len(client.combat_log_appends)))
    assert clients['party'].combat_log_appends
