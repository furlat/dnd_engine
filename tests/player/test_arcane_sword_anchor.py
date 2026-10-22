"""Real sword actions publish a separately observed blade through detached updates.

Input: registered cast, move, strike, caster movement and concentration removal.
Boundary: native action -> application capture -> detached client/reconnect state.
Expected: one stable independent spatial UUID, correct anchors and spell outcomes.
"""

from time import perf_counter
from uuid import uuid4

import pytest

from dnd.actions_functional import register_spell
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.audience import PlayerAudience
from dnd.player.facts import ActionFact, PlayerUpdate, SpellFact
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.spells.conjuration import FogCloud
from dnd.spells.evocation import ArcaneSword, ArcaneSwordStrike, MoveArcaneSword
from tests.player.test_emitted_update_replica import operation_since
from tests.player.test_solid_wall_transport import clients_at_boundary, wall_world


def capture(runtime, clients, cursor):
    updates = capture_application_operation(runtime.audiences,
        operation_since(runtime.session, cursor), runtime.catalog)
    detached = {seat: PlayerUpdate.model_validate_json(update.model_dump_json())
        for seat, update in updates.items()}
    for seat, update in detached.items():
        clients[seat] = reduce_operation(clients[seat], update)
    return detached


def use(runtime, clients, actor, action_type, **selection):
    actor.action_economy.reset_all_costs()
    template, = (action for action in actor.registered_actions if isinstance(action, action_type))
    cursor = EventQueue.event_cursor()
    start = perf_counter()
    with fixed_dice_faces(15, *([2] * 100)):
        result = template.instantiate(**selection).apply()
    native_ms = (perf_counter() - start) * 1000
    assert result is not None and not result.canceled, result
    native_events = EventQueue.event_cursor() - cursor
    start = perf_counter()
    updates = capture(runtime, clients, cursor)
    return updates, dict(native_ms=native_ms, capture_decode_fold_ms=(perf_counter() - start) * 1000,
        event_versions=native_events)


def facts(update, kind):
    return [node.fact for group in update.lineages for node in group.events
        if isinstance(node.fact, kind)]


def blades(client):
    return {identity: effect for identity, effect in client.senses.spatial_effects.items()
        if effect.content_ref.content_id == 'spatial_effect.spell.arcane_sword'}


@pytest.mark.parametrize('ending', ['drop', 'expiry'])
def test_sword_anchor_survives_move_repeat_caster_movement_and_reconnect(ending):
    with wall_world(ArcaneSword, displaced=False) as (runtime, seat, publication):
        caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        victim = next(actor for actor in runtime.session.game.entities.values() if actor.position == (8, 7))
        clients = clients_at_boundary(runtime)
        updates, _ = use(runtime, clients, caster, ArcaneSword,
            target_entity_uuid=victim.uuid, end_position=(9, 7))
        identity, = blades(clients[seat])
        for client in clients.values():
            assert blades(client)[identity].anchor_position == (9, 7)
            assert blades(client)[identity].anchor_entity_uuid is None
        for update in updates.values():
            spell, = (fact for fact in facts(update, SpellFact) if fact.behavior_id == 'spell.arcane_sword')
            assert spell.source_position == caster.position and spell.attack_outcome is not None

        updates, _ = use(runtime, clients, caster, MoveArcaneSword, end_position=(9, 6))
        for update in updates.values():
            move, = (fact for fact in facts(update, ActionFact)
                if fact.behavior_id == 'action.spell.arcane_sword.move')
            assert move.target_position == (9, 6)
        for anchor in ((9, 6), (8, 6)):
            updates, _ = use(runtime, clients, caster, ArcaneSwordStrike,
                target_entity_uuid=victim.uuid, end_position=anchor)
            for client in clients.values():
                assert set(blades(client)) == {identity}
                assert blades(client)[identity].anchor_position == anchor
            for update in updates.values():
                strike, = (fact for fact in facts(update, SpellFact)
                    if fact.behavior_id == 'action.spell.arcane_sword.strike')
                assert strike.source_position == caster.position and strike.attack_outcome is not None

        caster.action_economy.reset_all_costs()
        cursor = EventQueue.event_cursor()
        caster.move((3, 6))
        capture(runtime, clients, cursor)
        assert caster.position == (3, 6)
        assert all(blades(client)[identity].anchor_position == (8, 6) for client in clients.values())
        _, initial = initialize_audiences(runtime.session, runtime.catalog)
        for value in initial.values():
            resumed = reduce_initialization(value)
            assert blades(resumed)[identity].anchor_position == (8, 6)

        if ending == 'drop':
            cursor = EventQueue.event_cursor()
            caster.remove_condition('Concentrating')
            capture(runtime, clients, cursor)
        else:
            encounter_uuid = uuid4()
            for round_number in range(1, 11):
                cursor = EventQueue.event_cursor()
                caster.on_turn_start(encounter_uuid, round_number=round_number)
                capture(runtime, clients, cursor)
                if round_number < 10:
                    assert all(identity in blades(client) for client in clients.values())
        assert all(not blades(client) for client in clients.values())
        assert not any(isinstance(action, (MoveArcaneSword, ArcaneSwordStrike)) for action in caster.registered_actions)


def test_visible_caster_does_not_reveal_hidden_blade_and_sight_reacquires_same_anchor():
    with wall_world(ArcaneSword, displaced=False) as (runtime, seat, publication):
        caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        observer = next(actor for actor in runtime.session.game.entities.values() if actor.position == (3, 8))
        victim = next(actor for actor in runtime.session.game.entities.values() if actor.position == (8, 7))
        fog_caster = next(actor for actor in runtime.session.game.entities.values() if actor.position == (8, 8))
        runtime.session.seats['watcher'] = PlayerAudience((), (observer.uuid,))
        clients = clients_at_boundary(runtime)
        use(runtime, clients, caster, ArcaneSword, target_entity_uuid=victim.uuid, end_position=(9, 7))
        identity, = blades(clients['watcher'])

        register_spell(fog_caster, FogCloud, caster_level=20)
        use(runtime, clients, fog_caster, FogCloud, end_position=(9, 7))
        assert caster.uuid in clients['watcher'].senses.entities
        assert not blades(clients['watcher'])
        _, initial = initialize_audiences(runtime.session, runtime.catalog)
        resumed = reduce_initialization(initial['watcher'])
        assert caster.uuid in resumed.senses.entities
        assert not blades(resumed)
        # A previously observed blade may retain its last-seen memory; it must
        # not be presented as currently visible merely because its caster is.
        assert resumed.remembered_effects[identity].anchor_position == (9, 7)

        cursor = EventQueue.event_cursor()
        fog_caster.remove_condition('Concentrating')
        capture(runtime, clients, cursor)
        assert set(blades(clients['watcher'])) == {identity}
        assert blades(clients['watcher'])[identity].anchor_position == (9, 7)
