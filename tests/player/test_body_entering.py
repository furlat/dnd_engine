"""A body enters a seat's view whole, once per seat-level entry, unless the seat holds it unchanged (player
schema 16; digest stamps).

Live play on the party seat (the fighter and the sorcerer), each update folded the way the client folds it. A
member regaining a body the other member still sees sends nothing; a body both members lost goes out whole again
when one of them regains it, without its birth, and replaces what the client remembered; a condition ending on a
body the seat no longer perceives reaches the seat not at all (leaving view sends nothing).
"""

import random
from uuid import uuid5

import pytest

from dnd.conditions import Invisible, Prone
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.player.application import capture_application_operation, initialize_audiences, seat_content
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import ActorChangeFact, BodyRecord, PlayerState, PlayerUpdate
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import Session, close_session, create_session, publish_sheets
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import Darkness
from dnd.spells.enchantment import HoldPerson
from tests.player.test_emitted_update_replica import (INITIALIZATION, Step, cast, darkness_ends, enemies, entity,
    move, operation_since)


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


def play(session: Session, steps: tuple[Step, ...]) -> tuple[tuple[BodyRecord, ...], dict[str, PlayerUpdate],
                                                            dict[str, PlayerState]]:
    """The party seat's initialization bodies, its update at each step and its client after each step."""
    sorcerer = session.player_uuids[1]
    session.game.entities[sorcerer].action_economy.set_normal_spell_slot_capacity(
        uuid5(sorcerer, 'entering'), {level: 4 for level in range(1, 10)})
    publish_sheets(session)
    catalog = ui_content_manifest()
    runtimes, initializations = initialize_audiences(session, catalog)
    initial = INITIALIZATION.validate_json(INITIALIZATION.dump_json(initializations['party']))
    client = reduce_initialization(initial, content_additions=seat_content(runtimes['party']))
    updates, clients = {}, {}
    for step in steps:
        start = EventQueue.event_cursor()
        step.act(session)
        update = PlayerUpdate.model_validate_json(capture_application_operation(
            runtimes, operation_since(session, start), catalog)['party'].model_dump_json())
        client = reduce_operation(client, update)
        updates[step.name], clients[step.name] = update, client
    return initial.bodies, updates, clients


def records(update: PlayerUpdate) -> list[tuple[str, bool]]:
    return [(str(row.actor_uuid), row.birth is not None) for lineage in update.lineages for row in lineage.bodies]


def condition_names(client: PlayerState, identity) -> set[str]:
    return {member.name for member in client.actors[identity].conditions}


def test_a_member_regaining_a_body_the_seat_still_sees_sends_nothing(session):
    # The fighter steps into a darkness and loses both goblins, which the sorcerer keeps seeing, then steps out.
    _, updates, _ = play(session, (
        Step('darkness west of the party', cast(Darkness, (6, 11), 2)),
        Step('fighter steps into the darkness', move(0, (7, 11))),
        Step('fighter steps out', move(0, (10, 10))),
    ))
    assert {name: records(update) for name, update in updates.items()} == {name: [] for name in updates}


def test_a_body_the_seat_lost_reenters_whole_once_without_its_birth_unless_unchanged(session):
    goblins = [str(actor.uuid) for actor in enemies(session)]
    unseen, still = enemies(session)[1], enemies(session)[0]

    def unseen_goblin_falls_prone(session: Session) -> None:
        unseen.add_condition(Prone(source_entity_uuid=unseen.uuid, target_entity_uuid=unseen.uuid))

    initial, updates, clients = play(session, (
        Step('darkness over the goblins', cast(Darkness, (14, 11), 2)),
        Step('a goblin falls prone unseen', unseen_goblin_falls_prone),
        Step('the darkness ends', darkness_ends),
    ))
    # Each goblin's birth went out once, at initialization.
    assert sorted((str(row.actor_uuid), row.birth is not None) for row in initial
                  if str(row.actor_uuid) in goblins) == sorted((identity, True) for identity in goblins)
    assert records(updates['darkness over the goblins']) == []
    assert records(updates['a goblin falls prone unseen']) == []
    assert 'Prone' not in condition_names(clients['a goblin falls prone unseen'], unseen.uuid)
    # Both members lost them. When the darkness ends the goblin that changed unseen re-enters whole, without its
    # birth, replacing the memory; the other, unchanged, is confirmed by its digest stamp: no record.
    assert records(updates['the darkness ends']) == [(str(unseen.uuid), False)]
    assert 'Prone' in condition_names(clients['the darkness ends'], unseen.uuid)
    held, kept = clients['darkness over the goblins'].actors[still.uuid], clients['the darkness ends'].actors[still.uuid]
    assert (kept.normal_hp, kept.conditions, kept.visual_loadout) == (held.normal_hp, held.conditions, held.visual_loadout)


def test_a_condition_ending_on_a_body_the_seat_no_longer_perceives_reaches_nothing(session):
    held = enemies(session)[0]

    def hold_the_goblin(session: Session) -> None:
        caster = entity(session, 1)
        caster.action_economy.reset_all_costs()
        with fixed_dice_faces(*([2] * 120)):
            outcome = HoldPerson(source_entity_uuid=caster.uuid, target_entity_uuid=held.uuid, use_register=False,
                caster_level=20, cast_at_level=2).apply()
        assert outcome is not None and not outcome.canceled, outcome and outcome.status_message

    def the_goblin_turns_invisible(session: Session) -> None:
        held.add_condition(Invisible(source_entity_uuid=held.uuid, target_entity_uuid=held.uuid))

    _, updates, clients = play(session, (
        Step('the sorcerer holds a goblin', hold_the_goblin),
        Step('the goblin turns invisible', the_goblin_turns_invisible),
        Step('the sorcerer drops concentration', darkness_ends),
    ))
    assert 'Hold Person' in condition_names(clients['the goblin turns invisible'], held.uuid)
    changed = {row.actor_uuid for lineage in updates['the sorcerer drops concentration'].lineages
               for event in lineage.events if isinstance(event.fact, ActorChangeFact) for row in event.fact.actors}
    # The caster's own concentration ends on its body; the unseen goblin's hold reaches the seat not at all.
    assert held.uuid not in changed and session.player_uuids[1] in changed
    assert 'Hold Person' in condition_names(clients['the sorcerer drops concentration'], held.uuid)
