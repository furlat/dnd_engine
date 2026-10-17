"""Exact player choices survive compact transport without eager area effects.

Boundary: native session -> serialized server Choices/Preview -> native command.
Input: small authored caster encounters and ordered player selections.
Expected: unchanged options/costs, local preview domains, isolated public values.
"""

import json
import random
from uuid import uuid4

import pytest

from devtools.player_server_acceptance.fixtures import combat_configuration
from dnd.actions import SpellEvent
from dnd.core.base_actions import AvailableTarget
from dnd.core.events import EventQueue
from dnd.player.commands import ActionSelection, CommandRejected
from dnd.player.session import close_session, discover_player_actions
from server.protocol import ChoicesRequest, CommandRequest, ExecuteSelectionIntent, PreviewRequest
from server.worker import dispatch, needs_advance, response_bytes, start
from server.worker_protocol import Advance, Choices, Command, Preview, Start


@pytest.fixture
def world(tmp_path):
    rng = random.getstate()
    config = combat_configuration('fireball_six_goblins', tmp_path)
    runtime, _, _ = start(Start(game_id=config.game_id, game_epoch=uuid4(),
        audience_ids={row.seat_id: uuid4() for row in config.credentials},
        encounter_id=config.encounter_id, recipe=config.recipe, assignments=config.assignments,
        test_seed=config.test_seed))
    while needs_advance(runtime.session):
        dispatch(runtime, Advance())
    seat, publication = next((key, value) for key, value in runtime.publications.items()
        if value.boundary.input_actor_uuid is not None)
    try:
        yield runtime, seat, publication
    finally:
        close_session(runtime.session)
        random.setstate(rng)


def request_choices(world):
    runtime, seat, publication = world
    query = ChoicesRequest(actor_uuid=publication.boundary.input_actor_uuid,
        state_revision=publication.state_revision, force_attack=False, correlation_id=uuid4())
    _, _, response = dispatch(runtime, Choices(seat_id=seat, request=query))
    assert response.correlation_id == query.correlation_id
    return response


def rows(choices):
    return choices.entity_actions + choices.position_actions + choices.self_actions + choices.object_actions


def native_value(domains, binding):
    data = binding.model_dump(exclude={'kind', 'subject', 'position', 'secondary_set'})
    if binding.kind == 'subject':
        subject = domains.subjects[binding.subject]
        data.update(target_uuid=subject.uuid, target_kind=subject.kind, target_name=subject.name)
    if binding.kind != 'self' and binding.position is not None:
        data['position'] = domains.positions[binding.position]
    if binding.secondary_set is not None:
        data['secondary_targets'] = [native_value(domains, row) for row in domains.target_sets[binding.secondary_set]]
    for key in ('path', 'safe_path'):
        if key in data:
            data[key] = [domains.positions[reference] for reference in data[key]]
    for key in ('opportunity_attack_exposures', 'safe_path_opportunity_attack_exposures'):
        for exposure in data.get(key, ()):
            exposure['from_position'] = domains.positions[exposure['from_position']]
            exposure['to_position'] = domains.positions[exposure['to_position']]
    return AvailableTarget.model_validate(data).model_dump()


def test_choices_wire_bytes_are_the_canonical_encoding_on_miss_and_hit(world):
    runtime, seat, publication = world
    for _ in range(2):  # the discovery, then its retained answer
        request = Choices(seat_id=seat, request=ChoicesRequest(actor_uuid=publication.boundary.input_actor_uuid,
            state_revision=publication.state_revision, force_attack=False, correlation_id=uuid4()))
        _, _, response = dispatch(runtime, request)
        assert response_bytes(runtime, request, response) == response.model_dump_json().encode()


@pytest.mark.parametrize('rich_first', [False, True])
def test_compact_and_rich_queries_share_exact_admission_and_isolate_caller_mutation(world, rich_first):
    runtime, seat, publication = world
    actor = publication.boundary.input_actor_uuid
    cursor = EventQueue.event_cursor()
    if rich_first:
        rich = discover_player_actions(runtime.session, actor, seat_id=seat)
    first = request_choices(world)
    if not rich_first:
        rich = discover_player_actions(runtime.session, actor, seat_id=seat)
    again = request_choices(world)
    assert first.choices.model_dump() == again.choices.model_dump()
    assert first.choices.discovery_generation == rich.discovery_generation
    preview_fields = {'affected_positions', 'affected_entity_uuids', 'affected_entity_names', 'affected_count'}
    for compact, native in zip(rows(first.choices), rich.all_actions, strict=True):
        assert compact.model_dump(exclude={'target_set', 'area_preview', 'aiming', 'range_origin',
            'area_include_self', 'area_target_filter', 'area_include_dead'}) == native.model_dump(exclude={'valid_targets'})
        actual = [native_value(first.choices, binding) for binding in first.choices.target_sets[compact.target_set]]
        expected = [AvailableTarget.model_validate(target.model_dump(exclude=preview_fields)).model_dump()
            for target in native.valid_targets]
        assert actual == expected, compact.template_name
    assert EventQueue.event_cursor() == cursor
    preserved = rich.model_dump()
    for row in rich.all_actions:
        row.valid_targets.clear()
        row.costs.clear()
        row.display_name = 'Caller edit'
    fresh = discover_player_actions(runtime.session, actor, seat_id=seat)
    assert fresh.model_dump() == preserved
    assert request_choices(world).choices.model_dump() == first.choices.model_dump()
    packet = json.loads(first.model_dump_json())
    assert 'valid_targets' not in packet['choices']['position_actions'][0]
    assert all('affected_positions' not in binding for pool in packet['choices']['target_sets'] for binding in pool)


def test_selected_area_preview_matches_rich_effects_and_command_needs_no_preview(world):
    runtime, seat, publication = world
    actor = publication.boundary.input_actor_uuid
    discovered = request_choices(world).choices
    action = next(row for row in rows(discovered) if row.behavior_id == 'spell.fireball' and row.can_afford)
    target = next(row for row in discovered.target_sets[action.target_set]
        if discovered.positions[row.position] == (10, 7))
    assert action.area_preview == 'deferred' and action.aiming.geometry.shape == 'sphere'
    assert action.range_origin == (3, 7)
    selection = ActionSelection(action_index=action.discovery_index, target_indices=(target.index,), extra_target_positions=())
    # The execution contract never requires a Preview request.
    _, records, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
        command_number=1, actor_uuid=actor, state_revision=publication.state_revision,
        intent=ExecuteSelectionIntent(discovery_generation=discovered.discovery_generation, selection=selection))))
    assert records
    assert any(isinstance(event, SpellEvent) and not event.canceled for _, event in EventQueue.iter_events_since(0))
    with pytest.raises(CommandRejected):
        dispatch(runtime, Preview(seat_id=seat, request=PreviewRequest(actor_uuid=actor,
            state_revision=publication.state_revision, discovery_generation=discovered.discovery_generation,
            correlation_id=uuid4(), selection=selection)))


@pytest.mark.parametrize("rich_before", [False, True])
def test_preview_has_own_domains_and_exact_subjective_area_effects(world, rich_before):
    runtime, seat, publication = world
    actor = publication.boundary.input_actor_uuid
    discovered = request_choices(world).choices
    rich = discover_player_actions(runtime.session, actor, seat_id=seat) if rich_before else None
    action = next(row for row in rows(discovered) if row.behavior_id == 'spell.fireball' and row.can_afford)
    target = next(row for row in discovered.target_sets[action.target_set]
        if discovered.positions[row.position] == (10, 7))
    query = PreviewRequest(actor_uuid=actor, state_revision=publication.state_revision,
        discovery_generation=discovered.discovery_generation, correlation_id=uuid4(),
        selection=ActionSelection(action_index=action.discovery_index, target_indices=(target.index,), extra_target_positions=()))
    before = EventQueue.event_cursor()
    _, _, response = dispatch(runtime, Preview(seat_id=seat, request=query))
    value = response.preview
    if rich is None:
        rich = discover_player_actions(runtime.session, actor, seat_id=seat)
    expected = next(row for row in rich.all_actions[action.discovery_index].valid_targets if row.index == target.index)
    assert response.request == query
    assert value.can_confirm and value.area_preview == 'computed'
    assert tuple(value.positions[index] for index in value.affected_positions) == tuple(expected.affected_positions)
    assert value.affected_entity_uuids == tuple(expected.affected_entity_uuids)
    assert value.affected_entity_names == tuple(expected.affected_entity_names)
    assert EventQueue.event_cursor() == before
    _, _, repeated = dispatch(runtime, Preview(seat_id=seat, request=query))
    assert repeated.preview == value
