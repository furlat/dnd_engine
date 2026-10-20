"""Solid-wall choices, formation and cancellation survive public worker capture.

Input: the reported four-actor layout, selected panel side, and native vetoes.
Boundary: Choices -> Preview -> Command -> detached operations and client fold.
Expected: blocked choices spend nothing; valid walls form/retire; vetoes cancel.
"""
from contextlib import contextmanager
from pathlib import Path
import random
from uuid import uuid4

import pytest

from devtools.player_server_acceptance.fixtures import configuration
from dnd.conditions import Invisible
from dnd.core.base_block import BaseBlock
from dnd.core.content.encounters import (AuthoredCreatureRosterSource, EncounterDeploymentSpec,
    EncounterDeploymentZone, EncounterRecipe, EncounterRosterRecipe, RosterSpellGrant)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import get_content_declaration
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.player.application import initialize_audiences, seat_content
from dnd.player.commands import ActionSelection, CommandRejected
from dnd.player.facts import ForcedMovementFact, SpellFact
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import close_session
from dnd.spells.wall_constructions import SolidWallZone, WallOfForce, WallOfIce, WallOfStone
from server.protocol import CommandRequest, EndTurnIntent, ExecuteSelectionIntent, PlayerOperation, PreviewRequest
from server.worker import dispatch, needs_advance, start
from server.worker_protocol import Advance, Command, Preview, Start
from tests.player.test_compact_choices import request_choices, rows
from tests.player.test_handoff_discovery_regressions import submit

WALLS = [(WallOfForce, 'spell.wall_of_force'), (WallOfIce, 'spell.wall_of_ice'),
         (WallOfStone, 'spell.wall_of_stone')]


@contextmanager
def wall_world(spell, *, blocked=True, displaced=True):
    """The original level-20 authored builds and four-actor formation, seed 2."""
    rng = random.getstate()
    config = configuration('human', Path('/unused-memory-only-wall-configuration'))
    source = AuthoredCreatureRosterSource(recipe=ContentRecipe.create(
        ref=BESTIARY_CREATURE_RECIPES_BY_ID['generic_caster'].ref, parameters={'level': 20}))
    slots = []
    for slot in config.recipe.roster_slots:
        members = tuple(member.model_copy(update={'source': source,
            'scenario_setup_effects': (RosterSpellGrant(spell_refs=(get_content_declaration(spell).ref,),
                caster_level=20),) if slot.faction_id == 'amber' and index == 0 else ()})
            for index, member in enumerate(slot.roster.members))
        roster = EncounterRosterRecipe.create(roster_id=slot.roster.roster_id,
            title=slot.roster.title, members=members)
        slots.append(slot.model_copy(update={'roster': roster}))
    blue = ((4, 7), (4, 8) if blocked else (7, 8)) if displaced else ((8, 7), (8, 8))
    deployment = EncounterDeploymentSpec.create(deployment_id='deployment.wall_capture',
        title='Wall capture', battlefield_id=config.recipe.battlefield_id,
        zones=(EncounterDeploymentZone(zone_id='amber', ordered_slots=((3, 7), (3, 8))),
               EncounterDeploymentZone(zone_id='blue', ordered_slots=blue)))
    recipe = EncounterRecipe.create(encounter_id='encounter.wall_capture', title='Wall capture',
        battlefield_id=config.recipe.battlefield_id, deployment=deployment,
        roster_slots=tuple(slots), opening_policy=config.recipe.opening_policy)
    runtime, _, _ = start(Start(game_id='wall-capture', game_epoch=uuid4(),
        audience_ids={row.seat_id: uuid4() for row in config.credentials},
        encounter_id=None, recipe=recipe, assignments=config.assignments, test_seed=2))
    try:
        caster = next(entity for entity in runtime.session.game.entities.values() if entity.position == (3, 7))
        for number in range(1, 12):
            while needs_advance(runtime.session):
                dispatch(runtime, Advance())
            seat, publication = next((seat, row) for seat, row in runtime.publications.items()
                if row.boundary.input_actor_uuid is not None)
            if publication.boundary.input_actor_uuid == caster.uuid:
                break
            dispatch(runtime, Command(seat_id=seat, request=CommandRequest(command_number=number,
                actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision,
                intent=EndTurnIntent())))
        assert publication.boundary.input_actor_uuid == caster.uuid
        yield runtime, seat, publication
    finally:
        close_session(runtime.session)
        random.setstate(rng)


def selection_preview(world, behavior, side, *, positions=((6, 7),)):
    runtime, seat, publication = world
    discovered = request_choices(world).choices
    row = next(row for row in rows(discovered) if row.behavior_id == behavior
        and row.can_afford and all(any(facet.key == key and facet.value == value
            for facet in row.variant_facets) for key, value in (('form', 'panels'), ('side', side))))
    selection = ActionSelection(action_index=row.discovery_index, target_indices=(),
        extra_target_positions=positions, prefer_safe=False)
    before = EventQueue.event_cursor()
    _, _, response = dispatch(runtime, Preview(seat_id=seat, request=PreviewRequest(
        actor_uuid=publication.boundary.input_actor_uuid, state_revision=publication.state_revision,
        discovery_generation=discovered.discovery_generation, correlation_id=uuid4(), selection=selection)))
    assert EventQueue.event_cursor() == before
    return discovered, selection, response.preview


def clients_at_boundary(runtime):
    runtimes, initial = initialize_audiences(runtime.session, runtime.catalog)
    runtime.audiences = runtimes
    return {seat: reduce_initialization(value, content_additions=seat_content(runtimes[seat]))
        for seat, value in initial.items()}


def fold_records(runtime, clients, records):
    for record in records:
        seat = next(seat for seat, publication in runtime.publications.items()
            if publication.cursor.audience_id == record.cursor.audience_id)
        detached = PlayerOperation.model_validate_json(record.model_dump_json())
        clients[seat] = reduce_operation(clients[seat], detached)


@pytest.mark.parametrize('spell,behavior', WALLS)
def test_blocked_wall_side_is_rejected_before_commit(spell, behavior):
    with wall_world(spell) as world:
        runtime, seat, publication = world
        actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        positions = {key: entity.position for key, entity in runtime.session.game.entities.items()}
        before = EventQueue.event_cursor()
        discovered, selection, preview = selection_preview(world, behavior, 'left')
        assert not preview.can_confirm
        with pytest.raises(CommandRejected):
            submit(runtime, seat, actor, discovered, selection, 20)
        assert EventQueue.event_cursor() == before
        assert positions == {key: entity.position for key, entity in runtime.session.game.entities.items()}
        assert actor.action_economy.actions.normalized_score == 1
        assert not get_map().get_spatial_conditions()


@pytest.mark.parametrize('spell,behavior', WALLS)
def test_solid_wall_formation_and_retirement_fold_from_public_operations(spell, behavior):
    with wall_world(spell) as world:
        runtime, seat, publication = world
        actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        target = next(entity for entity in runtime.session.game.entities.values() if entity.position == (4, 7))
        clients = clients_at_boundary(runtime)
        discovered, selection, preview = selection_preview(world, behavior, 'right')
        assert preview.can_confirm
        with fixed_dice_faces(*([2] * 100)):
            records = submit(runtime, seat, actor, discovered, selection, 20)
        assert target.position == (4, 6)
        zone, = (condition for condition in get_map().get_spatial_conditions() if isinstance(condition, SolidWallZone))
        section_ids = set(zone.sections)
        assert section_ids
        fold_records(runtime, clients, records)
        assert len(records) == 2
        for record in records:
            facts = [node.fact for group in record.lineages for node in group.events]
            assert any(isinstance(fact, SpellFact) and fact.behavior_id == behavior for fact in facts)
            assert any(isinstance(fact, ForcedMovementFact) and fact.target_entity_uuid == target.uuid
                and fact.end_position == (4, 6) for fact in facts)
        if spell is not WallOfForce:
            assert all(section_ids <= state.objects.keys() for state in clients.values())
        discovered = request_choices((runtime, seat, runtime.publications[seat])).choices
        drop, = (row for row in rows(discovered) if row.behavior_id == 'action.drop_concentration')
        binding, = discovered.target_sets[drop.target_set]
        retired = submit(runtime, seat, actor, discovered,
            ActionSelection(drop.discovery_index, (binding.index,)), 21)
        fold_records(runtime, clients, retired)
        assert not any(BaseBlock.get(identity) is not None for identity in section_ids)
        assert not get_map().get_spatial_conditions()
        assert all(not section_ids.intersection(state.objects) for state in clients.values())


@pytest.mark.parametrize('spell,behavior', WALLS)
def test_formation_veto_publishes_cancellation_and_no_partial_wall(spell, behavior):
    with wall_world(spell, displaced=False) as world:
        runtime, seat, publication = world
        actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        clients = clients_at_boundary(runtime)
        discovered, selection, preview = selection_preview(world, behavior, 'left', positions=((6, 5), (10, 5)))
        assert preview.can_confirm
        seen = []
        def refuse_second(event, _):
            if event.object_uuid not in seen:
                seen.append(event.object_uuid)
            return event.cancel(status_message='Second placement refused') if len(seen) == 2 else None
        handler = EventHandler(name='Refuse second wall section', source_entity_uuid=actor.uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_PLACED, event_phase=EventPhase.EFFECT)],
            event_processor=refuse_second)
        EventQueue.add_event_handler(handler)
        before = EventQueue.event_cursor()
        records = submit(runtime, seat, actor, discovered, selection, 20)
        fold_records(runtime, clients, records)
        latest = {event.lineage_uuid: event for _, event in EventQueue.iter_events_since(before)}
        assert all(event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL) for event in latest.values())
        assert len(seen) == 2 and all(BaseBlock.get(identity) is None for identity in seen)
        assert not get_map().get_spatial_conditions()
        assert all(not set(seen).intersection(state.objects) for state in clients.values())
        assert any(node.phase is EventPhase.CANCEL and isinstance(node.fact, SpellFact)
            and node.fact.behavior_id == behavior for record in records for group in record.lineages for node in group.events)


def test_subjective_wall_displacement_does_not_reveal_an_invisible_blocker():
    with wall_world(WallOfForce) as world:
        runtime, seat, publication = world
        caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        target = next(entity for entity in runtime.session.game.entities.values() if entity.position == (4, 7))
        blocker = next(entity for entity in runtime.session.game.entities.values() if entity.position == (4, 8))
        assert blocker.add_condition(Invisible(source_entity_uuid=blocker.uuid, target_entity_uuid=blocker.uuid))
        assert blocker.uuid not in caster.senses.entities
        assert target.uuid in caster.senses.entities
        assert not target.can_end_movement_at(caster.position, subjective=True, observer=caster)
        assert target.can_end_movement_at(blocker.position, subjective=True, observer=caster)
        assert not target.can_end_movement_at(blocker.position)
        _, _, preview = selection_preview(world, 'spell.wall_of_force', 'left')
        assert preview.can_confirm
