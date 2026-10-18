"""A seat receives one composed perception change per settlement (plan §3.1, Q1 (a)), whatever number of its
members observed it.

Over the replica scenario (a two-observer party seat beside a one-observer seat): each settlement marker lies in
one walk group; a settlement of the seat's members publishes at most one sensory fact, at its first member's
version, and no later member's version or lineage ever reaches the seat; the client's member bitsets name the
members holding each contact and effect in the seat's composition; an effect's content travels once; the anchor's
position travels only when it changed.
"""

from copy import deepcopy
from uuid import UUID, uuid5

from dnd.core.events import EventQueue, SensoryUpdateEvent
from dnd.player.application import capture_application_operation, initialize_audiences, seat_content
from dnd.player.audience import PlayerAudience
from dnd.player.capture import capture_context
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import PlayerState, PlayerUpdate, SensoryFact
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import publish_sheets
from tests.player.test_emitted_update_replica import INITIALIZATION, SCENARIO, operation_since
from tests.player.test_emitted_update_replica import session as session  # the fixture


def bits(members: set[UUID], audience: PlayerAudience) -> int:
    return sum(1 << index for index, member in enumerate(audience.observers) if member in members)


def test_one_composed_fact_per_settlement_with_the_members_perceiving_each_row(session):
    fighter, sorcerer = session.player_uuids
    session.seats['fighter'] = PlayerAudience((fighter,), (fighter,))
    session.game.entities[sorcerer].action_economy.set_normal_spell_slot_capacity(
        uuid5(sorcerer, 'wire'), {level: 4 for level in range(1, 10)})
    publish_sheets(session)
    catalog = ui_content_manifest()
    runtimes, initializations = initialize_audiences(session, catalog)
    clients: dict[str, PlayerState] = {seat: reduce_initialization(INITIALIZATION.validate_json(
        INITIALIZATION.dump_json(initial)), content_additions=seat_content(runtimes[seat]))
        for seat, initial in initializations.items()}
    contents: dict[str, list[UUID]] = {seat: [identity for node in initial.nodes if isinstance(node.fact, SensoryFact)
        for identity in node.fact.spatial_effect_content] for seat, initial in initializations.items()}
    grouped = composed = 0
    for step in SCENARIO:
        start = EventQueue.event_cursor()
        step.act(session)
        operation = operation_since(session, start)
        # Each settlement closes inside one walk group (the walk composes a settlement where it meets it).
        # (The groups of a copy of the shared capture fold: capturing advances it.)
        context = capture_context(deepcopy(next(iter(runtimes.values())).capture), operation.roots)
        markers: dict[int, int] = {}
        for group, graph in enumerate(context.graphs.values()):
            for _, event in graph.indexed:
                if isinstance(event, SensoryUpdateEvent) and event.settlement is not None:
                    assert markers.setdefault(event.settlement, group) == group, step.name
        grouped += len(context.graphs) > 1
        native = [event for _, event in EventQueue.iter_events_since(start) if isinstance(event, SensoryUpdateEvent)]
        updates = capture_application_operation(runtimes, operation, catalog)
        for seat, update in updates.items():
            runtime, audience = runtimes[seat], session.seats[seat]
            projection = runtime.projection
            # The seat's settlements: its members' events by marker, in native order.
            settlements: dict[int, list[SensoryUpdateEvent]] = {}
            for event in native:
                if audience.observes(event.observer_uuid) and event.settlement is not None:
                    settlements.setdefault(event.settlement, []).append(event)
            firsts = {projection.public_versions[members[0].uuid] for members in settlements.values()
                      if members[0].uuid in projection.public_versions}
            later = [event for members in settlements.values() for event in members[1:]]
            composed += bool(later)
            facts = [(node.occurrence, node.fact) for lineage in update.lineages for node in lineage.events
                     if isinstance(node.fact, SensoryFact)]
            occurrences = [occurrence for occurrence, _ in facts]
            assert set(occurrences) <= firsts and len(occurrences) == len(set(occurrences)), (step.name, seat)
            assert not any(event.uuid in projection.public_versions for event in later), (step.name, seat)
            lineage_keys = runtime.session.lineages
            assert not any(lineage_keys[event.lineage_uuid] in projection.public_lineages
                           for members in settlements.values() for event in members[1:]
                           if event.lineage_uuid != members[0].lineage_uuid), (step.name, seat)
            # The anchor's position travels only when it changed.
            before = clients[seat].senses
            assert before is not None
            clients[seat] = reduce_operation(clients[seat], PlayerUpdate.model_validate_json(update.model_dump_json()))
            after = clients[seat].senses
            assert after is not None
            if after.position == before.position:
                assert all(fact.observer_position is None for _, fact in facts), (step.name, seat)
            contents[seat] += [identity for _, fact in facts for identity in fact.spatial_effect_content]
            # Each contact and effect the client perceives names the members holding it in the composition.
            composition = projection.audience_composition
            client = clients[seat]
            assert client.entity_members == {identity: bits(composition.entity_members[identity], audience)
                                             for identity in after.entities}, (step.name, seat)
            assert client.object_contact_members == {identity: bits(composition.object_members[identity], audience)
                                                     for identity in after.objects}, (step.name, seat)
            assert set(client.effect_members) == set(after.spatial_effects), (step.name, seat)
    # An effect's content is sent to a seat once.
    for seat, sent in contents.items():
        assert len(sent) == len(set(sent)), seat
    assert grouped, "the scenario walks an operation of several groups"
    assert composed, "the party's members observe a settlement together"
