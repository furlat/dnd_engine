"""Two swords retain exact caster joins through fresh public initialization.

Input: two real casters, their blades, reconnect and stationary repeat attacks.
Boundary: native actions -> serialized updates/initialization -> detached clients.
Expected: existing concentration slot UUIDs identify each blade without proximity.
"""

from pydantic import TypeAdapter
import pytest

from dnd.actions_functional import register_spell
from dnd.conditions import Blinded
from dnd.core.events import EventQueue
from dnd.player.application import initialize_audiences
from dnd.player.audience import PlayerAudience
from dnd.player.facts import PlayerInitialization, SpatialEffectStateFact, SpellFact
from dnd.player.reduction import reduce_initialization
from dnd.spells.conjuration import FogCloud
from dnd.spells.evocation import ArcaneSword, ArcaneSwordStrike
from tests.player.test_arcane_sword_anchor import blades, capture, facts, use
from tests.player.test_solid_wall_transport import clients_at_boundary, wall_world


def caster_blade(client, caster_uuid):
    slots = {slot.slot_uuid for member in client.actors[caster_uuid].conditions
        if member.state is not None for slot in member.state.concentration_slots
        if slot.spell_id == 'spell.arcane_sword'}
    assert len(slots) == 1
    matches = [(identity, effect) for identity, effect in blades(client).items()
        if effect.concentration_slot_uuid in slots]
    assert len(matches) == 1
    return matches[0]


def test_two_casters_keep_exact_blades_after_reconnect_and_stationary_repeats():
    with wall_world(ArcaneSword, displaced=False) as (runtime, seat, publication):
        first = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        second = next(actor for actor in runtime.session.game.entities.values() if actor.position == (8, 8))
        first_victim = next(actor for actor in runtime.session.game.entities.values() if actor.position == (8, 7))
        second_victim = next(actor for actor in runtime.session.game.entities.values() if actor.position == (3, 8))
        register_spell(second, ArcaneSword, caster_level=20)
        clients = clients_at_boundary(runtime)
        casts = ((first, first_victim, (9, 7)), (second, second_victim, (4, 8)))
        identities = {}
        for caster, victim, position in casts:
            use(runtime, clients, caster, ArcaneSword, target_entity_uuid=victim.uuid, end_position=position)
            identity, effect = caster_blade(clients[seat], caster.uuid)
            assert effect.anchor_position == position
            identities[caster.uuid] = identity
        assert len(set(identities.values())) == 2
        for client in clients.values():
            for caster, _, position in casts:
                identity, effect = caster_blade(client, caster.uuid)
                assert identity == identities[caster.uuid] and effect.anchor_position == position

        runtime.audiences, initializations = initialize_audiences(runtime.session, runtime.catalog)
        adapter = TypeAdapter(PlayerInitialization)
        clients = {key: reduce_initialization(adapter.validate_json(adapter.dump_json(initial)))
            for key, initial in initializations.items()}
        for caster, victim, position in casts:
            for client in clients.values():
                identity, effect = caster_blade(client, caster.uuid)
                assert identity == identities[caster.uuid] and effect.anchor_position == position
            updates, _ = use(runtime, clients, caster, ArcaneSwordStrike,
                target_entity_uuid=victim.uuid, end_position=position)
            for key, update in updates.items():
                spell, = (fact for fact in facts(update, SpellFact)
                    if fact.behavior_id == 'action.spell.arcane_sword.strike')
                assert spell.source_entity_uuid == caster.uuid and spell.attack_outcome is not None
                assert not facts(update, SpatialEffectStateFact)
                identity, effect = caster_blade(clients[key], spell.source_entity_uuid)
                assert identity == identities[caster.uuid] and effect.anchor_position == position


@pytest.mark.parametrize('first_observed_hidden', [False, True])
def test_visible_blade_opaque_slot_does_not_reveal_hidden_caster(first_observed_hidden):
    with wall_world(ArcaneSword, displaced=False) as (runtime, seat, publication):
        caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        watcher = next(actor for actor in runtime.session.game.entities.values() if actor.position == (8, 7))
        fog_caster = next(actor for actor in runtime.session.game.entities.values() if actor.position == (8, 8))
        if first_observed_hidden:
            watcher.add_condition(Blinded(source_entity_uuid=watcher.uuid, target_entity_uuid=watcher.uuid))
        runtime.session.seats['watcher'] = PlayerAudience((), (watcher.uuid,))
        clients = clients_at_boundary(runtime)
        use(runtime, clients, caster, ArcaneSword, target_entity_uuid=watcher.uuid, end_position=(9, 7))
        identity, effect = caster_blade(clients[seat], caster.uuid)
        slot = effect.concentration_slot_uuid
        assert slot is not None
        if first_observed_hidden:
            assert not blades(clients['watcher'])
        else:
            assert caster_blade(clients['watcher'], caster.uuid)[0] == identity

        register_spell(fog_caster, FogCloud, caster_level=20)
        use(runtime, clients, fog_caster, FogCloud, end_position=(3, 7))
        if first_observed_hidden:
            cursor = EventQueue.event_cursor()
            watcher.remove_condition('Blinded')
            capture(runtime, clients, cursor)
        contact = clients['watcher'].senses.entities.get(caster.uuid)
        assert contact is None or not contact.visual
        blade = blades(clients['watcher'])[identity]
        assert blade.anchor_position == (9, 7) and blade.concentration_slot_uuid == slot
        assert blade.anchor_entity_uuid is None and blade.sustainer_item_uuid is None
        if first_observed_hidden:
            assert slot not in {entry.slot_uuid for actor in clients['watcher'].actors.values()
                for member in actor.conditions if member.state is not None
                for entry in member.state.concentration_slots}

        _, initializations = initialize_audiences(runtime.session, runtime.catalog)
        adapter = TypeAdapter(PlayerInitialization)
        resumed = reduce_initialization(adapter.validate_json(adapter.dump_json(initializations['watcher'])))
        blade = blades(resumed)[identity]
        assert blade.anchor_position == (9, 7) and blade.concentration_slot_uuid == slot
        if first_observed_hidden:
            assert slot not in {entry.slot_uuid for actor in resumed.actors.values()
                for member in actor.conditions if member.state is not None
                for entry in member.state.concentration_slots}

        cursor = EventQueue.event_cursor()
        fog_caster.remove_condition('Concentrating')
        capture(runtime, clients, cursor)
        restored_identity, effect = caster_blade(clients['watcher'], caster.uuid)
        assert restored_identity == identity and effect.concentration_slot_uuid == slot
