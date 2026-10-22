"""Real casts publish defeat separately from a surviving party's recovery state."""

import asyncio
import random
from uuid import uuid4

import httpx
import pytest

from devtools.player_server_acceptance.fixtures import configuration
from dnd.content.characters.premades import SORCERER_PREMADE_ID
from dnd.core.content.encounters import (
    EncounterDeploymentSpec, EncounterDeploymentZone, EncounterRecipe,
    EncounterRosterRecipe, FixedRosterOpeningPolicy, PremadeCharacterRosterSource,
    RosterStartingDamage,
)
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.life_types import LifeState
from dnd.player.audience import SeatAssignment
from dnd.player.commands import ActionSelection, CommandRejected
from dnd.player.session import close_session
from server import host as owner, service, worker
from server.app import create_app
from server.config import SeatCredential
from server.protocol import (
    AttachmentRequest, ChoicesRequest, ChoicesResponse, CommandRequest, EndTurnIntent,
    ExecuteSelectionIntent, PlayerOperation,
)
from server.worker_protocol import Advance, Choices, Command, Start
from tests.player.test_compact_choices import rows
from tests.player.test_prepared_classes_http import completed_receipt, receive_operations


def defeat_config(path, *, ally=False, death_saves=True, wounded=False):
    base = configuration('two_sides', path)
    slots = []
    for slot in base.recipe.roster_slots:
        members = slot.roster.members[:2 if ally and slot.roster_slot_id == 'amber' else 1]
        roster = EncounterRosterRecipe.create(roster_id=slot.roster.roster_id,
            title=slot.roster.title, members=tuple(member.model_copy(update={
                'source': PremadeCharacterRosterSource(premade_id=SORCERER_PREMADE_ID),
                'uses_death_saves': death_saves,
                'scenario_setup_effects': (RosterStartingDamage(amount=36,
                    damage_type=DamageType.FORCE),) if wounded and slot.roster_slot_id == 'amber' else (),
            }) for member in members))
        slots.append(slot.model_copy(update={'roster': roster}))
    deployment = EncounterDeploymentSpec.create(deployment_id='deployment.defeat_boundary',
        title='Defeat boundary', battlefield_id=base.recipe.battlefield_id, zones=(
            EncounterDeploymentZone(zone_id='amber', ordered_slots=((3, 7), (3, 12))),
            EncounterDeploymentZone(zone_id='blue', ordered_slots=((9, 7),)),
        ))
    recipe = EncounterRecipe.create(encounter_id='encounter.defeat_boundary', title='Defeat boundary',
        battlefield_id=deployment.battlefield_id, deployment=deployment,
        roster_slots=tuple(slots), opening_policy=FixedRosterOpeningPolicy(roster_slot_id='blue'))
    assignments = (SeatAssignment('amber', (('amber', 'unit_1'),)),
        SeatAssignment('blue', (('blue', 'unit_1'),)))
    if ally:
        assignments += (SeatAssignment('ally', (('amber', 'unit_2'),)),)
    return base.model_copy(update={'game_id': 'encounter', 'recipe': recipe, 'assignments': assignments,
        'credentials': tuple(SeatCredential(seat_id=row.seat_id, token='defeat-boundary-test-token-' + row.seat_id)
            for row in assignments)})


def await_turn(runtime, seat):
    for _ in range(20):
        if worker.needs_advance(runtime.session):
            worker.dispatch(runtime, Advance())
        elif runtime.publications[seat].boundary.input_actor_uuid is not None:
            return runtime.publications[seat]
        else:
            other, publication = next((key, value) for key, value in runtime.publications.items()
                if value.boundary.input_actor_uuid is not None)
            worker.dispatch(runtime, Command(seat_id=other, request=CommandRequest(command_number=1,
                actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision,
                intent=EndTurnIntent())))
    pytest.fail('Expected external turn did not arrive')


def fireball(runtime, seat, position):
    publication = await_turn(runtime, seat)
    actor = publication.boundary.input_actor_uuid
    _, _, response = worker.dispatch(runtime, Choices(seat_id=seat, request=ChoicesRequest(
        actor_uuid=actor, state_revision=publication.state_revision, force_attack=False, correlation_id=uuid4())))
    row = next(row for row in rows(response.choices)
        if row.behavior_id == 'spell.fireball' and row.cast_at_level == 3 and row.can_afford)
    with fixed_dice_faces(*([6] * 200)):
        reply, records, _ = worker.dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
            command_number=1, actor_uuid=actor, state_revision=publication.state_revision,
            intent=ExecuteSelectionIntent(discovery_generation=response.choices.discovery_generation,
                selection=ActionSelection(row.discovery_index, (), extra_target_positions=(position,))))))
    assert reply.rejection is None
    return [PlayerOperation.model_validate_json(record.model_dump_json()) for record in records]


@pytest.mark.parametrize('death_saves', [True, False], ids=['dying', 'dead'])
def test_losing_seat_is_terminal_and_winner_can_act_after_combat(tmp_path, death_saves):
    config = defeat_config(tmp_path, death_saves=death_saves)
    before_random = random.getstate()
    runtime, _, _ = worker.start(Start(game_id='encounter', game_epoch=uuid4(), encounter_id=None,
        audience_ids={row.seat_id: uuid4() for row in config.assignments},
        recipe=config.recipe, assignments=config.assignments, test_seed=2))
    try:
        records = fireball(runtime, 'blue', (3, 7))
        victim = runtime.session.game.entities[runtime.session.seats['amber'].controlled[0]]
        assert victim.health.life_state is (LifeState.DYING if death_saves else LifeState.DEAD)
        for seat, lifecycle in [('amber', 'terminal'), ('blue', 'outside_encounter')]:
            publication = runtime.publications[seat]
            record = next(row for row in records if row.cursor.audience_id == publication.cursor.audience_id)
            assert record.boundary.lifecycle == lifecycle
            assert (record.boundary.state_revision is None) is (lifecycle == 'terminal')
            actor = runtime.session.seats[seat].controlled[0]
            request = Choices(seat_id=seat, request=ChoicesRequest(actor_uuid=actor,
                state_revision=publication.state_revision, force_attack=False, correlation_id=uuid4()))
            if lifecycle == 'terminal':
                with pytest.raises(CommandRejected, match='actor_unavailable'):
                    worker.dispatch(runtime, request)
            else:
                assert worker.dispatch(runtime, request)[2].choices.entity_uuid == actor
    finally:
        close_session(runtime.session)
        random.setstate(before_random)


def test_downed_seat_remains_recoverable_when_an_allied_seat_wins(tmp_path):
    config = defeat_config(tmp_path, ally=True)
    before_random = random.getstate()
    runtime, _, _ = worker.start(Start(game_id='encounter', game_epoch=uuid4(), encounter_id=None,
        audience_ids={row.seat_id: uuid4() for row in config.assignments},
        recipe=config.recipe, assignments=config.assignments, test_seed=2))
    try:
        fireball(runtime, 'blue', (3, 7))
        assert runtime.publications['amber'].boundary.lifecycle != 'terminal'
        with fixed_dice_faces(*([6] * 200)):
            records = fireball(runtime, 'ally', (9, 7))
        victim = runtime.session.game.entities[runtime.session.seats['amber'].controlled[0]]
        assert victim.health.life_state is LifeState.DYING
        assert {seat: publication.boundary.lifecycle for seat, publication in runtime.publications.items()} == {
            'amber': 'outside_encounter', 'ally': 'outside_encounter', 'blue': 'terminal'}
        assert any(row.boundary.lifecycle == 'terminal' for row in records)
    finally:
        close_session(runtime.session)
        random.setstate(before_random)


def test_http_defeat_publishes_final_cursor_and_rejects_further_input(tmp_path):
    async def check():
        config = defeat_config(tmp_path, wounded=True)
        app = create_app(config)
        host = app.state.player_host
        host.task = asyncio.create_task(owner.run(host))
        try:
            async with asyncio.timeout(60):
                async with host.changed:
                    await host.changed.wait_for(lambda: host.failure is not None or (
                        host.seats['blue'].publication is not None and
                        host.seats['blue'].publication.boundary.input_actor_uuid is not None))
            assert host.failure is None
            headers = {}
            for seat_id, seat in host.seats.items():
                attachment = owner.attach(host, seat, AttachmentRequest(acquisition_id=uuid4(),
                    expected_attachment_epoch=None))
                headers[seat_id] = {'Authorization': 'Bearer defeat-boundary-test-token-' + seat_id,
                    'X-Game-Epoch': str(host.epoch), 'X-Audience-Id': str(seat.audience_id),
                    'X-Attachment-Epoch': str(attachment.attachment_epoch)}
                seat.attachment.highest_sent = seat.publication.cursor.sequence
                owner.acknowledge(host, seat, seat.attachment, seat.publication.cursor)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                path = '/api/v1/games/encounter/'
                blue = host.seats['blue']
                actor = blue.publication.boundary.input_actor_uuid
                answer = await client.post(path + 'choices', headers=headers['blue'], json={
                    'actor_uuid': str(actor), 'state_revision': blue.publication.state_revision, 'force_attack': False,
                    'correlation_id': str(uuid4())})
                assert answer.status_code == 200, answer.text
                choices = ChoicesResponse.model_validate_json(answer.text).choices
                row = next(row for row in rows(choices)
                    if row.behavior_id == 'spell.fireball' and row.cast_at_level == 3 and row.can_afford)
                previous = host.seats['amber'].publication.cursor.sequence
                receipt = await completed_receipt(client, host, blue, headers['blue'], {
                    'command_number': 1, 'actor_uuid': str(actor),
                    'state_revision': blue.publication.state_revision,
                    'intent': {'kind': 'execute_selection', 'discovery_generation': choices.discovery_generation,
                        'selection': {'action_index': row.discovery_index, 'target_indices': [],
                            'extra_target_positions': [[3, 7]]}}})
                assert receipt.kind == 'committed'
                amber = host.seats['amber']
                operations = await receive_operations(app, headers['amber'], after=previous,
                    through=amber.publication.cursor.sequence)
                assert operations[-1].boundary.lifecycle == 'terminal'
                state = (await client.get(path + 'status', headers=headers['amber'])).json()['status']
                assert state['final_cursor'] == amber.publication.cursor.model_dump(mode='json')
                assert state['boundary']['state_revision'] is None
                response = await client.post(path + 'ack', headers=headers['amber'], json={
                    'cursor': amber.publication.cursor.model_dump(mode='json')})
                assert response.status_code == 200, response.text
                actor = amber.publication.audience.controlled[0]
                response = await client.post(path + 'choices', headers=headers['amber'], json={
                    'actor_uuid': str(actor), 'state_revision': amber.publication.state_revision, 'force_attack': False,
                    'correlation_id': str(uuid4())})
                assert response.status_code == 409 and response.json()['code'] == 'game_terminal'
                assert host.seats['blue'].publication.boundary.lifecycle == 'outside_encounter'
        finally:
            await service.shutdown(app.state.player_service)
    asyncio.run(check())
