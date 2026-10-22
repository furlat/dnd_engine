"""Summon commands follow the caster through real worker and HTTP boundaries.

Real creator Wizard5 + an authored Conjure Animals grant exercises human/Codex
roster control, two seats, movement, an attack and retirement. No summon is
manually assigned a controller or inserted into the player audience.
"""
import asyncio
import random
from uuid import uuid4

import httpx
import pytest

from devtools.player_server_acceptance.fixtures import combat_configuration
from dnd.actions_functional import register_spell
from dnd.content.characters.premades import WIZARD_PREMADE_ID
from dnd.core.content.encounters import (EncounterRecipe, EncounterRosterRecipe,
    PremadeCharacterRosterSource, RosterControllerKind, RosterMemberControllerOverride)
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.player.commands import ActionSelection, CommandRejected
from dnd.player.facts import AudienceFact, AttackFact
from dnd.player.reduction import reduce_initialization
from dnd.player.session import close_session
from dnd.spells.summoning import ConjureFey
from dnd.types.character_progression import CharacterClass
from server import host as host_owner, protocol as wire, service, worker
from server.app import create_app
from server.protocol import (AttachmentRequest, ChoicesRequest, CommandRequest,
    EndTurnIntent, ExecuteSelectionIntent, PreviewRequest)
from server.worker_protocol import Advance, Choices, Command, Preview, Start
from tests.player.test_compact_choices import rows
from tests.player.test_prepared_classes_http import completed_receipt, fold, receive_operations
from tests.progression.prepared_class_support import prepared_build


def configuration(path, controller, *, member_override=False):
    config = combat_configuration('conjure_animals', path)
    amber, blue = config.recipe.roster_slots
    member, = amber.roster.members
    member = member.model_copy(update={'source': PremadeCharacterRosterSource(premade_id=WIZARD_PREMADE_ID)})
    roster = EncounterRosterRecipe.create(roster_id=amber.roster.roster_id, title=amber.roster.title, members=(member,))
    defaults = amber.controller_defaults.model_copy(update={
        'controller': RosterControllerKind.HUMAN if member_override else controller,
        'member_overrides': (RosterMemberControllerOverride(member_id=member.member_id, controller=controller),)
            if member_override else (),
    })
    amber = amber.model_copy(update={'roster': roster, 'controller_defaults': defaults})
    recipe = EncounterRecipe.create(encounter_id=config.recipe.encounter_id, title=config.recipe.title,
        battlefield_id=config.recipe.battlefield_id, deployment=config.recipe.deployment,
        roster_slots=(amber, blue), opening_policy=config.recipe.opening_policy)
    return config.model_copy(update={'recipe': recipe})


def owner(runtime):
    return next((seat, row) for seat, row in runtime.publications.items() if row.boundary.input_actor_uuid is not None)


def advance_to_input(runtime):
    for _ in range(80):
        if not worker.needs_advance(runtime.session):
            return owner(runtime)
        worker.dispatch(runtime, Advance())
    pytest.fail('Native advance did not expose an external turn')


def choices(runtime):
    seat, publication = owner(runtime)
    _, _, response = worker.dispatch(runtime, Choices(seat_id=seat, request=ChoicesRequest(
        actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision,
        force_attack=False, correlation_id=uuid4())))
    return response.choices


def action(runtime, offered, selection):
    seat, publication = owner(runtime)
    common = dict(actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision)
    worker.dispatch(runtime, Preview(seat_id=seat, request=PreviewRequest(**common,
        discovery_generation=offered.discovery_generation, selection=selection, correlation_id=uuid4())))
    with fixed_dice_faces(*([12] * 200)):
        reply, records, _ = worker.dispatch(runtime, Command(seat_id=seat, request=CommandRequest(**common,
            command_number=1, intent=ExecuteSelectionIntent(discovery_generation=offered.discovery_generation,
                selection=selection))))
    assert reply.rejection is None
    return records


def cast(runtime, spell='spell.conjure_animals', level=3, position=(7, 7)):
    offered = choices(runtime)
    row = next(row for row in rows(offered) if row.behavior_id == spell and row.can_afford
        and row.cast_at_level == level and any(f.key == 'form' and f.value == 'wolf' for f in row.variant_facets))
    before = set(runtime.session.game.entities)
    records = action(runtime, offered, ActionSelection(row.discovery_index, (), extra_target_positions=(position,)))
    summon, = set(runtime.session.game.entities) - before
    return summon, records


def end_turn(runtime):
    seat, publication = owner(runtime)
    return worker.dispatch(runtime, Command(seat_id=seat, request=CommandRequest(command_number=1,
        actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision, intent=EndTurnIntent())))


def facts(records):
    return [node.fact for record in records for lineage in record.lineages for node in lineage.events]


@pytest.fixture
def workers():
    active = []
    previous = random.getstate()
    def open_worker(config=None, builds=None):
        runtime, _, _ = worker.start(Start(game_id='summon-control-test', game_epoch=uuid4(), encounter_id=None,
            recipe=config.recipe if config else None, assignments=config.assignments if config else None,
            audience_ids={seat.seat_id: uuid4() for seat in config.assignments} if config else {'party': uuid4()},
            test_seed=2, player_builds=builds))
        active.append(runtime)
        advance_to_input(runtime)
        return runtime
    yield open_worker
    for runtime in active:
        close_session(runtime.session)
    random.setstate(previous)


def check_summon_journey(runtime, mode):
    """One public play sequence, also used to produce the client handoff recording."""
    caster = owner(runtime)[1].boundary.input_actor_uuid
    caster_controller = runtime.session.encounter.get_controller_for(caster)
    assert caster_controller.controller_type == mode.value
    summon, records = cast(runtime)
    assert runtime.session.encounter.get_controller_for(summon) is caster_controller
    assert runtime.session.seats['amber'].controls(summon)
    assert runtime.session.seats['amber'].observes(summon)
    assert not runtime.session.seats['blue'].controls(summon)
    assert runtime.publications['amber'].audience == runtime.session.seats['amber']
    assert any(isinstance(fact, AudienceFact) and fact.audience.controls(summon) for fact in facts(records))
    assert summon in runtime.session.sheets.by_actor
    assert not runtime.session.game.entities[summon].is_player_companion
    end_turn(runtime)
    seat, publication = advance_to_input(runtime)
    assert seat == 'amber' and publication.boundary.input_actor_uuid == summon
    assert publication.boundary.lifecycle == ('waiting_for_codex' if mode is RosterControllerKind.CODEX else 'waiting_for_human')
    assert not worker.needs_advance(runtime.session)
    before = EventQueue.event_cursor()
    with pytest.raises(CommandRejected):
        worker.dispatch(runtime, Choices(seat_id='blue', request=ChoicesRequest(actor_uuid=summon,
            state_revision=runtime.publications['blue'].state_revision, force_attack=False, correlation_id=uuid4())))
    assert EventQueue.event_cursor() == before
    offered = choices(runtime)
    move = next(row for row in rows(offered) if row.behavior_id == 'action.move' and row.can_afford
        and any(target.position is not None and offered.positions[target.position] == (8, 7)
            for target in offered.target_sets[row.target_set]))
    destination = next(target for target in offered.target_sets[move.target_set]
        if target.position is not None and offered.positions[target.position] == (8, 7))
    action(runtime, offered, ActionSelection(move.discovery_index, (destination.index,)))
    assert runtime.session.game.entities[summon].position == (8, 7)
    offered = choices(runtime)
    attack = next(row for row in offered.entity_actions if row.behavior_id == 'action.attack' and row.can_afford)
    target = offered.target_sets[attack.target_set][0]
    records = action(runtime, offered, ActionSelection(attack.discovery_index, (target.index,)))
    assert any(isinstance(fact, AttackFact) for fact in facts(records))
    end_turn(runtime)
    for _ in range(10):
        _, publication = advance_to_input(runtime)
        if publication.boundary.input_actor_uuid == caster:
            break
        end_turn(runtime)
    assert publication.boundary.input_actor_uuid == caster
    offered = choices(runtime)
    drop = next(row for row in offered.self_actions if row.behavior_id == 'action.drop_concentration')
    records = action(runtime, offered, ActionSelection(drop.discovery_index, (offered.target_sets[drop.target_set][0].index,)))
    assert summon not in runtime.session.game.entities
    assert not runtime.session.seats['amber'].controls(summon)
    assert summon not in runtime.session.sheets.by_actor
    assert runtime.publications['amber'].audience == runtime.session.seats['amber']
    assert any(isinstance(fact, AudienceFact) and not fact.audience.controls(summon) for fact in facts(records))
    with pytest.raises(CommandRejected):
        worker.dispatch(runtime, Choices(seat_id='amber', request=ChoicesRequest(actor_uuid=summon,
            state_revision=runtime.publications['amber'].state_revision, force_attack=False, correlation_id=uuid4())))


@pytest.mark.parametrize('mode,override', [(RosterControllerKind.HUMAN, False),
    (RosterControllerKind.CODEX, False), (RosterControllerKind.CODEX, True)])
def test_caster_seat_commands_summon_moves_attacks_and_loses_retired_authority(tmp_path, workers, mode, override):
    check_summon_journey(workers(configuration(tmp_path, mode, member_override=override)), mode)


def test_fey_release_revokes_commands_while_body_remains(workers):
    runtime = workers(builds=(prepared_build(CharacterClass.WIZARD, 11),))
    caster = runtime.session.game.entities[runtime.session.player_uuids[0]]
    register_spell(caster, ConjureFey, caster_level=11)
    summon, _ = cast(runtime, 'spell.conjure_fey', 6, (12, 10))
    offered = choices(runtime)
    drop = next(row for row in offered.self_actions if row.behavior_id == 'action.drop_concentration')
    action(runtime, offered, ActionSelection(drop.discovery_index, (offered.target_sets[drop.target_set][0].index,)))
    assert summon in runtime.session.game.entities
    assert not runtime.session.seats['party'].controls(summon)
    assert not runtime.session.seats['party'].observes(summon)
    assert runtime.session.game.entities[summon].is_enemy(caster)
    assert summon not in runtime.session.sheets.by_actor
    before = EventQueue.event_cursor()
    with pytest.raises(CommandRejected):
        worker.dispatch(runtime, Choices(seat_id='party', request=ChoicesRequest(actor_uuid=summon,
            state_revision=runtime.publications['party'].state_revision, force_attack=False, correlation_id=uuid4())))
    assert EventQueue.event_cursor() == before


@pytest.mark.parametrize('mode', [RosterControllerKind.HUMAN, RosterControllerKind.CODEX])
def test_http_summon_input_catchup_and_reconnect_keep_current_authority(tmp_path, mode):
    async def exercise():
        config = configuration(tmp_path, mode).model_copy(update={'game_id': 'encounter'})
        app = create_app(config)
        host = app.state.player_host
        host.task = asyncio.create_task(host_owner.run(host))
        expected = 'waiting_for_codex' if mode is RosterControllerKind.CODEX else 'waiting_for_human'
        path = '/api/v1/games/encounter/'
        try:
            async with asyncio.timeout(60):
                async with host.changed:
                    await host.changed.wait_for(lambda: host.failure is not None or (
                        host.seats['amber'].publication is not None
                        and host.seats['amber'].publication.boundary.lifecycle == expected))
            assert host.failure is None
            headers, delivered, states = {}, {}, {}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                for credential in config.credentials:
                    seat = host.seats[credential.seat_id]
                    base = {'Authorization': f'Bearer {credential.token}', 'X-Game-Epoch': str(host.epoch),
                        'X-Audience-Id': str(seat.audience_id)}
                    attachment = await client.post(path + 'attachment', headers=base,
                        json={'acquisition_id': str(uuid4()), 'expected_attachment_epoch': None})
                    assert attachment.status_code == 200, attachment.text
                    headers[credential.seat_id] = {**base, 'X-Attachment-Epoch': attachment.json()['attachment_epoch']}
                    initial = await client.get(path + 'initialization', headers=headers[credential.seat_id])
                    assert initial.status_code == 200, initial.text
                    opening = wire.InitializationResponse.model_validate_json(initial.text)
                    states[credential.seat_id] = reduce_initialization(opening.initialization, content_additions=opening.content_additions)
                    delivered[credential.seat_id] = opening.cursor.sequence

                async def consume(name):
                    seat = host.seats[name]
                    cursor = seat.publication.cursor
                    if cursor.sequence > delivered[name]:
                        records = await receive_operations(app, headers[name], after=delivered[name], through=cursor.sequence)
                        states[name] = fold(states[name], records)
                        delivered[name] = cursor.sequence
                    ack = await client.post(path + 'ack', headers=headers[name], json={'cursor': cursor.model_dump(mode='json')})
                    assert ack.status_code == 200, ack.text

                for name in headers:
                    await consume(name)
                seat = host.seats['amber']
                caster = seat.publication.boundary.input_actor_uuid
                query = {'actor_uuid': str(caster), 'state_revision': seat.publication.state_revision,
                    'force_attack': False, 'correlation_id': str(uuid4())}
                response = await client.post(path + 'choices', headers=headers['amber'], json=query)
                assert response.status_code == 200, response.text
                offered = wire.ChoicesResponse.model_validate_json(response.text).choices
                row = next(row for row in rows(offered) if row.behavior_id == 'spell.conjure_animals'
                    and row.cast_at_level == 3 and any(f.key == 'form' and f.value == 'wolf' for f in row.variant_facets))
                selection = ActionSelection(row.discovery_index, (), extra_target_positions=((7, 7),))
                preview = await client.post(path + 'preview', headers=headers['amber'], json=PreviewRequest(
                    actor_uuid=caster, state_revision=seat.publication.state_revision,
                    discovery_generation=offered.discovery_generation, correlation_id=uuid4(),
                    selection=selection).model_dump(mode='json'))
                assert preview.status_code == 200, preview.text
                before = set(seat.publication.audience.controlled)
                command = CommandRequest(command_number=1, actor_uuid=caster, state_revision=seat.publication.state_revision,
                    intent=ExecuteSelectionIntent(discovery_generation=offered.discovery_generation, selection=selection))
                receipt = await completed_receipt(client, host, seat, headers['amber'], command.model_dump(mode='json'))
                assert receipt.kind == 'committed'
                summon, = set(seat.publication.audience.controlled) - before
                for name in headers:
                    await consume(name)
                assert states['amber'].audience.controls(summon)
                assert not states['blue'].audience.controls(summon)
                assert any(sheet.actor_uuid == summon for sheet in states['amber'].hud_snapshot.sheets)
                unauthorized = await client.post(path + 'choices', headers=headers['blue'], json={
                    'actor_uuid': str(summon), 'state_revision': host.seats['blue'].publication.state_revision,
                    'force_attack': False, 'correlation_id': str(uuid4())})
                assert unauthorized.status_code == 409, unauthorized.text
                assert unauthorized.json()['code'] == 'not_your_turn'
                receipt = await completed_receipt(client, host, seat, headers['amber'], CommandRequest(
                    command_number=2, actor_uuid=caster, state_revision=seat.publication.state_revision,
                    intent=EndTurnIntent()).model_dump(mode='json'))
                assert receipt.kind == 'committed'
                async with asyncio.timeout(15):
                    async with host.changed:
                        await host.changed.wait_for(lambda: host.failure is not None
                            or seat.publication.boundary.input_actor_uuid == summon)
                assert host.failure is None and not host.needs_advance
                assert seat.publication.boundary.lifecycle == expected
                await consume('amber')
                response = await client.post(path + 'choices', headers=headers['amber'], json={
                    'actor_uuid': str(summon), 'state_revision': seat.publication.state_revision,
                    'force_attack': False, 'correlation_id': str(uuid4())})
                assert response.status_code == 200, response.text
                offered = wire.ChoicesResponse.model_validate_json(response.text).choices
                move = next(row for row in offered.position_actions if row.behavior_id == 'action.move'
                    and any(target.position is not None and offered.positions[target.position] == (8, 7)
                        for target in offered.target_sets[row.target_set]))
                target = next(target for target in offered.target_sets[move.target_set]
                    if target.position is not None and offered.positions[target.position] == (8, 7))
                receipt = await completed_receipt(client, host, seat, headers['amber'], CommandRequest(
                    command_number=3, actor_uuid=summon, state_revision=seat.publication.state_revision,
                    intent=ExecuteSelectionIntent(discovery_generation=offered.discovery_generation,
                        selection=ActionSelection(move.discovery_index, (target.index,)))).model_dump(mode='json'))
                assert receipt.kind == 'committed'
                await consume('amber')
                bootstrap = await client.get('/api/v1/bootstrap', headers=headers['amber'])
                assert bootstrap.status_code == 200
                assert str(summon) in bootstrap.json()['audience']['controlled']
                attachment = await client.post(path + 'attachment', headers=headers['amber'], json={
                    'acquisition_id': str(uuid4()), 'expected_attachment_epoch': headers['amber']['X-Attachment-Epoch']})
                assert attachment.status_code == 200, attachment.text
                headers['amber']['X-Attachment-Epoch'] = attachment.json()['attachment_epoch']
                initial = await client.get(path + 'initialization', headers=headers['amber'])
                opening = wire.InitializationResponse.model_validate_json(initial.text)
                replayed = reduce_initialization(opening.initialization, content_additions=opening.content_additions)
                records = await receive_operations(app, headers['amber'], after=opening.cursor.sequence,
                    through=seat.publication.cursor.sequence)
                replayed = fold(replayed, records)
                assert replayed.audience == seat.publication.audience
                assert replayed.audience.controls(summon)
        finally:
            await service.shutdown(app.state.player_service)
    asyncio.run(exercise())
