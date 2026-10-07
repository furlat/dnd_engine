"""Retirement releases real world objects, including summon and AI ownership."""
import gc
import random
import weakref
from uuid import uuid4

from devtools.player_server_acceptance.fixtures import combat_configuration, configuration
from dnd.core.dice import Dice, DiceRoll
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.player.commands import ActionSelection
from dnd.player.session import close_session
from dnd.runtime_reset import reset_engine_runtime
from player_server.protocol import ChoicesRequest, CommandRequest, EndTurnIntent, ExecuteSelectionIntent, PreviewRequest
from player_server.worker import dispatch, needs_advance, start
from player_server.worker_protocol import Advance, Choices, Command, Preview, Start


def used_world(config, *, summon=False):
    runtime, reply, records = start(Start(game_id=config.game_id, game_epoch=uuid4(),
        audience_ids={row.seat_id: uuid4() for row in config.credentials},
        encounter_id=config.encounter_id, recipe=config.recipe, assignments=config.assignments,
        test_seed=config.test_seed))
    initial_count = len(runtime.session.game.entities)
    while needs_advance(runtime.session):
        reply, records, response = dispatch(runtime, Advance())
    if summon:
        seat, publication = next((key, value) for key, value in runtime.publications.items()
            if value.boundary.input_actor_uuid is not None)
        actor = publication.boundary.input_actor_uuid
        reply, records, discovered = dispatch(runtime, Choices(seat_id=seat, request=ChoicesRequest(
            actor_uuid=actor, state_revision=publication.state_revision,
            force_attack=False, correlation_id=uuid4())))
        row = next(row for row in discovered.choices.all_actions
            if row.behavior_id == 'spell.conjure_animals' and row.can_afford and row.valid_targets)
        selection = ActionSelection(action_index=row.discovery_index, target_indices=(row.valid_targets[0].index,),
            extra_target_positions=())
        for _ in range(12):
            reply, records, response = dispatch(runtime, Preview(seat_id=seat, request=PreviewRequest(
                actor_uuid=actor, state_revision=publication.state_revision, correlation_id=uuid4(),
                discovery_generation=discovered.choices.discovery_generation, selection=selection)))
            if response.preview.can_confirm:
                break
            selection = selection.model_copy(update={'extra_target_positions':
                (*selection.extra_target_positions, response.preview.next_positions[0])})
        assert response.preview.can_confirm
        reply, records, response = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
            command_number=1, actor_uuid=actor, state_revision=publication.state_revision,
            intent=ExecuteSelectionIntent(discovery_generation=discovered.choices.discovery_generation, selection=selection))))
        assert len(runtime.session.game.entities) > initial_count
    else:
        # Let the real mixed-controller game use AI discovery/decisions/attacks.
        for number in range(1, 20):
            if needs_advance(runtime.session):
                reply, records, response = dispatch(runtime, Advance())
            else:
                inputs = [(key, value) for key, value in runtime.publications.items()
                    if value.boundary.input_actor_uuid is not None]
                if not inputs:
                    break
                seat, publication = inputs[0]
                reply, records, response = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
                    command_number=number, actor_uuid=publication.boundary.input_actor_uuid,
                    state_revision=publication.state_revision, intent=EndTurnIntent())))
    references = [weakref.ref(entity) for entity in runtime.session.game.entities.values()]
    references.extend((weakref.ref(get_map()), weakref.ref(runtime.session.game)))
    rolls = tuple(DiceRoll._registry)
    assert rolls
    # Exactly the application/native cleanup used before EndGame acknowledgement.
    close_session(runtime.session)
    reset_engine_runtime()
    return references, rolls


def test_summoned_and_ai_worlds_are_collectible_before_next_world(tmp_path):
    original_rng = random.getstate()
    try:
        for config, summon in ((combat_configuration('conjure_animals', tmp_path), True),
                (configuration('mixed', tmp_path), False)):
            references, rolls = used_world(config, summon=summon)
            gc.collect()
            assert all(reference() is None for reference in references)
            assert all(DiceRoll.get(identity) is None for identity in rolls)
            assert EventQueue.event_cursor() == 0
            assert not Dice._registry
    finally:
        random.setstate(original_rng)
