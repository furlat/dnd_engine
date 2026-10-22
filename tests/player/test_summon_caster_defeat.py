"""Caster downing retires summons through ordinary worker commands and replay.

Two real creator-backed Life Clerics share one seat. An opposing creator-backed
Evocation Wizard downs one with Fireball while both spectral weapons stand
outside its area. No HP, resource, control or audience mutation sets up defeat.
"""

import asyncio
import random
from uuid import uuid4

import httpx
import pytest

from devtools.player_server_acceptance.fixtures import configuration
from dnd.content.characters.premades import CLERIC_PREMADE_ID, WIZARD_PREMADE_ID
from dnd.core.content.encounters import (
    EncounterDeploymentSpec, EncounterDeploymentZone, EncounterRecipe,
    EncounterRosterRecipe, FixedRosterOpeningPolicy, PremadeCharacterRosterSource,
    RosterControllerKind,
)
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from dnd.player.audience import SeatAssignment
from dnd.player.commands import ActionSelection, CommandRejected
from dnd.player.facts import AudienceFact, SpatialFact
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import close_session
from dnd.types.world import MovementMode
from server import host as host_owner, service, worker
from server.app import create_app
from server.protocol import (
    ChoicesRequest, ChoicesResponse, CommandRequest, EndTurnIntent, ExecuteSelectionIntent,
    InitializationResponse, PlayerOperation, PreviewRequest,
)
from server.worker_protocol import Advance, Choices, Command, Preview, Start
from tests.player.test_compact_choices import rows
from tests.player.test_prepared_classes_http import completed_receipt, fold, receive_operations


def defeat_configuration(path, mode):
    config = configuration('two_sides', path)
    slots = []
    for slot in config.recipe.roster_slots:
        members = slot.roster.members if slot.roster_slot_id == 'amber' else slot.roster.members[:1]
        premade = CLERIC_PREMADE_ID if slot.roster_slot_id == 'amber' else WIZARD_PREMADE_ID
        slots.append(slot.model_copy(update={
            'controller_defaults': slot.controller_defaults.model_copy(update={'controller': mode}),
            'roster': EncounterRosterRecipe.create(roster_id=slot.roster.roster_id,
                title=slot.roster.title, members=tuple(member.model_copy(update={
                    'source': PremadeCharacterRosterSource(premade_id=premade),
                    'scenario_setup_effects': (),
                }) for member in members)),
        }))
    deployment = EncounterDeploymentSpec.create(deployment_id='deployment.caster_defeat',
        title='Caster defeat', battlefield_id=config.recipe.battlefield_id, zones=(
            EncounterDeploymentZone(zone_id='amber', ordered_slots=((3, 7), (10, 12))),
            EncounterDeploymentZone(zone_id='blue', ordered_slots=((9, 7),)),
        ))
    recipe = EncounterRecipe.create(encounter_id='encounter.caster_defeat', title='Caster defeat',
        battlefield_id=config.recipe.battlefield_id, deployment=deployment, roster_slots=tuple(slots),
        opening_policy=FixedRosterOpeningPolicy(roster_slot_id='amber'))
    return config.model_copy(update={'recipe': recipe, 'assignments': (
        SeatAssignment('amber', (('amber', 'unit_1'), ('amber', 'unit_2'))),
        SeatAssignment('blue', (('blue', 'unit_1'),)),
    )})


@pytest.mark.parametrize('mode', [RosterControllerKind.HUMAN, RosterControllerKind.CODEX])
def test_weapon_moves_resets_and_departs_with_only_its_caster(tmp_path, mode):
    config = defeat_configuration(tmp_path, mode)
    previous_random = random.getstate()
    audience_ids = {assignment.seat_id: uuid4() for assignment in config.assignments}
    seats = {identity: seat for seat, identity in audience_ids.items()}
    runtime, _, initial = worker.start(Start(game_id='caster-defeat', game_epoch=uuid4(),
        audience_ids=audience_ids, encounter_id=None, recipe=config.recipe,
        assignments=config.assignments, test_seed=2))
    encoded = {seat: [] for seat in audience_ids}
    states = {}

    def consume(records):
        for record in records:
            seat = seats[record.cursor.audience_id]
            raw = record.model_dump_json()
            encoded[seat].append(raw)
            if isinstance(record, InitializationResponse):
                decoded = InitializationResponse.model_validate_json(raw)
                states[seat] = reduce_initialization(decoded.initialization,
                    content_additions=decoded.content_additions)
            else:
                states[seat] = reduce_operation(states[seat], PlayerOperation.model_validate_json(raw))

    def dispatch(request):
        result = worker.dispatch(runtime, request)
        consume(result[1])
        return result

    def await_actor(actor):
        for _ in range(60):
            if worker.needs_advance(runtime.session):
                dispatch(Advance())
                continue
            seat, publication = next((seat, pub) for seat, pub in runtime.publications.items()
                if pub.boundary.input_actor_uuid is not None)
            if publication.boundary.input_actor_uuid == actor:
                return seat, publication
            reply, _, _ = dispatch(Command(seat_id=seat, request=CommandRequest(command_number=1,
                actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision,
                intent=EndTurnIntent())))
            assert reply.rejection is None
        pytest.fail('Expected actor never received its ordinary external turn')

    def cast_at(actor, spell, level, position):
        seat, publication = await_actor(actor)
        query = ChoicesRequest(actor_uuid=actor, state_revision=publication.state_revision,
            force_attack=False, correlation_id=uuid4())
        _, _, response = dispatch(Choices(seat_id=seat, request=query))
        offered = response.choices
        row = next(row for row in rows(offered) if row.behavior_id == spell
            and row.cast_at_level == level and row.can_afford)
        selection = ActionSelection(row.discovery_index, (), extra_target_positions=(position,))
        dispatch(Preview(seat_id=seat, request=PreviewRequest(actor_uuid=actor,
            state_revision=publication.state_revision, discovery_generation=offered.discovery_generation,
            selection=selection, correlation_id=uuid4())))
        with fixed_dice_faces(*([6] * 200)):
            reply, records, _ = dispatch(Command(seat_id=seat, request=CommandRequest(command_number=1,
                actor_uuid=actor, state_revision=publication.state_revision,
                intent=ExecuteSelectionIntent(discovery_generation=offered.discovery_generation,
                    selection=selection))))
        assert reply.rejection is None
        return records

    def move_weapon(actor, destination):
        seat, publication = await_actor(actor)
        _, _, response = dispatch(Choices(seat_id=seat, request=ChoicesRequest(actor_uuid=actor,
            state_revision=publication.state_revision, force_attack=False, correlation_id=uuid4())))
        offered = response.choices
        moves = [row for row in rows(offered) if row.behavior_id == 'action.move' and row.can_afford]
        assert moves, 'A freshly summoned Spiritual Weapon must offer affordable movement on its own turn'
        destinations = [(row, target) for row in moves for target in offered.target_sets[row.target_set]
            if target.position is not None and offered.positions[target.position] == destination]
        assert destinations, 'A fresh Spiritual Weapon must discover an unobstructed adjacent Move target'
        move, target = destinations[0]
        selection = ActionSelection(move.discovery_index, (target.index,))
        entity = runtime.session.game.entities[actor]
        assert entity.action_economy.movement_remaining(MovementMode.FLYING) == 20
        dispatch(Preview(seat_id=seat, request=PreviewRequest(actor_uuid=actor,
            state_revision=publication.state_revision, discovery_generation=offered.discovery_generation,
            selection=selection, correlation_id=uuid4())))
        assert entity.action_economy.movement_remaining(MovementMode.FLYING) == 20
        reply, _, _ = dispatch(Command(seat_id=seat, request=CommandRequest(command_number=1,
            actor_uuid=actor, state_revision=publication.state_revision,
            intent=ExecuteSelectionIntent(discovery_generation=offered.discovery_generation, selection=selection))))
        assert reply.rejection is None
        assert entity.position == destination
        assert entity.action_economy.movement_spent() == 5
        assert entity.action_economy.movement_remaining(MovementMode.FLYING) == 15

    try:
        consume(initial)
        initial_controlled = runtime.session.seats['amber'].controlled
        caster = next(identity for identity in initial_controlled
            if runtime.session.game.entities[identity].position == (3, 7))
        ally, = set(initial_controlled) - {caster}
        attacker, = runtime.session.seats['blue'].controlled
        before = set(runtime.session.seats['amber'].controlled)
        cast_at(caster, 'spell.spiritual_weapon', 2, (3, 12))
        summon, = set(runtime.session.seats['amber'].controlled) - before
        move_weapon(summon, (4, 12))
        before = set(runtime.session.seats['amber'].controlled)
        cast_at(ally, 'spell.spiritual_weapon', 2, (11, 12))
        other_summon, = set(runtime.session.seats['amber'].controlled) - before
        assert states['amber'].audience.controls(summon)
        assert states['amber'].audience.controls(other_summon)
        await_actor(summon)
        assert runtime.session.game.entities[summon].action_economy.movement_remaining(MovementMode.FLYING) == 20
        assert runtime.session.game.entities[summon].action_economy.movement_spent() == 0

        records = cast_at(attacker, 'spell.fireball', 3, (3, 7))
        assert runtime.session.game.entities[caster].health.life_state is LifeState.DYING
        assert runtime.session.game.entities[caster].get_normal_hp() == 0
        assert summon not in runtime.session.game.entities
        assert other_summon in runtime.session.game.entities
        assert runtime.session.game.entities[ally].health.life_state is LifeState.ALIVE
        assert states['amber'].audience.controlled == (*initial_controlled, other_summon)
        assert states['amber'].audience.observers == (*initial_controlled, other_summon)
        assert summon not in runtime.session.sheets.by_actor
        assert other_summon in runtime.session.sheets.by_actor
        assert not any(sheet.actor_uuid == summon for sheet in states['amber'].hud_snapshot.sheets)
        assert all(publication.boundary.input_actor_uuid != summon
            for publication in runtime.publications.values())

        for seat in audience_ids:
            seat_records = [record for record in records if record.cursor.audience_id == audience_ids[seat]]
            facts = [node.fact for record in seat_records for lineage in record.lineages for node in lineage.events]
            departures = [fact for fact in facts if isinstance(fact, SpatialFact)
                and fact.entity_uuid == summon and fact.terminal_departure]
            assert len(departures) == 1
            assert departures[0].terminal_cause.value == 'caster_defeated'
            audience_facts = [fact for fact in facts if isinstance(fact, AudienceFact)]
            assert bool(audience_facts) is (seat == 'amber')
            assert states[seat].audience == runtime.publications[seat].audience == runtime.session.seats[seat]
            initial_packet = InitializationResponse.model_validate_json(encoded[seat][0])
            replayed = reduce_initialization(initial_packet.initialization,
                content_additions=initial_packet.content_additions)
            for raw in encoded[seat][1:]:
                replayed = reduce_operation(replayed, PlayerOperation.model_validate_json(raw))
            assert replayed == states[seat]

        cursor = EventQueue.event_cursor()
        with pytest.raises(CommandRejected, match='not_your_turn'):
            worker.dispatch(runtime, Command(seat_id='amber', request=CommandRequest(command_number=2,
                actor_uuid=summon, state_revision=runtime.publications['amber'].state_revision,
                intent=EndTurnIntent())))
        assert EventQueue.event_cursor() == cursor
        assert runtime.session.seats['amber'].controls(other_summon)
    finally:
        close_session(runtime.session)
        random.setstate(previous_random)


def test_http_bootstrap_and_reattached_replay_exclude_defeated_casters_weapon(tmp_path):
    async def exercise():
        config = defeat_configuration(tmp_path, RosterControllerKind.CODEX).model_copy(update={'game_id': 'encounter'})
        app = create_app(config)
        host = app.state.player_host
        host.task = asyncio.create_task(host_owner.run(host))
        path = '/api/v1/games/encounter/'
        try:
            async with asyncio.timeout(60):
                async with host.changed:
                    await host.changed.wait_for(lambda: host.failure is not None or (
                        host.seats['amber'].publication is not None
                        and host.seats['amber'].publication.boundary.lifecycle == 'waiting_for_codex'))
            assert host.failure is None
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                headers, states, delivered = {}, {}, {}
                commands = {seat: 0 for seat in host.seats}
                for credential in config.credentials:
                    seat = host.seats[credential.seat_id]
                    base = {'Authorization': f'Bearer {credential.token}', 'X-Game-Epoch': str(host.epoch),
                        'X-Audience-Id': str(seat.audience_id)}
                    response = await client.post(path + 'attachment', headers=base,
                        json={'acquisition_id': str(uuid4()), 'expected_attachment_epoch': None})
                    assert response.status_code == 200, response.text
                    headers[credential.seat_id] = {**base, 'X-Attachment-Epoch': response.json()['attachment_epoch']}
                    response = await client.get(path + 'initialization', headers=headers[credential.seat_id])
                    assert response.status_code == 200, response.text
                    opening = InitializationResponse.model_validate_json(response.text)
                    states[credential.seat_id] = reduce_initialization(opening.initialization,
                        content_additions=opening.content_additions)
                    delivered[credential.seat_id] = opening.cursor.sequence

                async def consume():
                    for name, seat in host.seats.items():
                        cursor = seat.publication.cursor
                        if cursor.sequence > delivered[name]:
                            records = await receive_operations(app, headers[name], after=delivered[name], through=cursor.sequence)
                            states[name] = fold(states[name], records)
                            delivered[name] = cursor.sequence
                        response = await client.post(path + 'ack', headers=headers[name],
                            json={'cursor': cursor.model_dump(mode='json')})
                        assert response.status_code == 200, response.text

                async def submit(name, intent):
                    seat = host.seats[name]
                    commands[name] += 1
                    receipt = await completed_receipt(client, host, seat, headers[name], CommandRequest(
                        command_number=commands[name], actor_uuid=seat.publication.boundary.input_actor_uuid,
                        state_revision=seat.publication.state_revision, intent=intent).model_dump(mode='json'))
                    assert receipt.kind == 'committed'
                    await consume()

                async def await_actor(actor):
                    for _ in range(60):
                        async with asyncio.timeout(30):
                            async with host.changed:
                                await host.changed.wait_for(lambda: host.failure is not None or any(
                                    seat.publication.boundary.input_actor_uuid is not None for seat in host.seats.values()))
                        assert host.failure is None
                        await consume()
                        name, seat = next((name, seat) for name, seat in host.seats.items()
                            if seat.publication.boundary.input_actor_uuid is not None)
                        if seat.publication.boundary.input_actor_uuid == actor:
                            return name, seat
                        await submit(name, EndTurnIntent())
                    pytest.fail('Expected actor never reached an HTTP input boundary')

                async def cast_at(actor, spell, level, position):
                    name, seat = await await_actor(actor)
                    response = await client.post(path + 'choices', headers=headers[name], json=ChoicesRequest(
                        actor_uuid=actor, state_revision=seat.publication.state_revision,
                        force_attack=False, correlation_id=uuid4()).model_dump(mode='json'))
                    assert response.status_code == 200, response.text
                    offered = ChoicesResponse.model_validate_json(response.text).choices
                    row = next(row for row in rows(offered) if row.behavior_id == spell
                        and row.cast_at_level == level and row.can_afford)
                    await submit(name, ExecuteSelectionIntent(discovery_generation=offered.discovery_generation,
                        selection=ActionSelection(row.discovery_index, (), extra_target_positions=(position,))))

                await consume()
                initial_controlled = host.seats['amber'].publication.audience.controlled
                caster = next(identity for identity in initial_controlled
                    if states['amber'].actors[identity].name == 'Amber scout 1')
                ally, = set(initial_controlled) - {caster}
                attacker, = host.seats['blue'].publication.audience.controlled
                await cast_at(caster, 'spell.spiritual_weapon', 2, (3, 12))
                summon, = set(host.seats['amber'].publication.audience.controlled) - {caster, ally}
                before = await client.get('/api/v1/bootstrap', headers=headers['amber'])
                assert before.status_code == 200, before.text
                assert str(summon) in before.json()['audience']['controlled']
                for _ in range(2):
                    await cast_at(attacker, 'spell.fireball', 3, (3, 7))
                    if states['amber'].actors[caster].life_state is not LifeState.ALIVE:
                        break
                    await submit('blue', EndTurnIntent())
                assert states['amber'].actors[caster].life_state is LifeState.DYING
                after = await client.get('/api/v1/bootstrap', headers=headers['amber'])
                assert after.status_code == 200, after.text
                assert after.json()['audience']['controlled'] == list(map(str, initial_controlled))
                assert after.json()['audience']['observers'] == list(map(str, initial_controlled))
                assert not states['amber'].audience.controls(summon)
                response = await client.post(path + 'attachment', headers=headers['amber'], json={
                    'acquisition_id': str(uuid4()), 'expected_attachment_epoch': headers['amber']['X-Attachment-Epoch']})
                assert response.status_code == 200, response.text
                headers['amber']['X-Attachment-Epoch'] = response.json()['attachment_epoch']
                response = await client.get(path + 'initialization', headers=headers['amber'])
                assert response.status_code == 200, response.text
                opening = InitializationResponse.model_validate_json(response.text)
                replayed = reduce_initialization(opening.initialization, content_additions=opening.content_additions)
                records = await receive_operations(app, headers['amber'], after=opening.cursor.sequence,
                    through=host.seats['amber'].publication.cursor.sequence)
                replayed = fold(replayed, records)
                assert replayed.audience == host.seats['amber'].publication.audience == states['amber'].audience
                assert not replayed.audience.controls(summon)
                assert not any(sheet.actor_uuid == summon for sheet in replayed.hud_snapshot.sheets)
        finally:
            await service.shutdown(app.state.player_service)
    asyncio.run(exercise())
