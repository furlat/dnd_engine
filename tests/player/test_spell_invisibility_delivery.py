"""An admitted cast reveals ordinary invisibility before its recipients lose sight.

Real creator characters and native casts feed the serialized player boundary.
The spell's completed result may follow damage; its causal identity must survive.
"""

from contextlib import contextmanager
import random

from pydantic import TypeAdapter
import pytest

from dnd.conditions import GreaterInvisibilityEffect, Invisible
from dnd.content.characters.premades import SORCERER_PREMADE_ID, create_premade_character
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, SensoryUpdateEvent, Trigger
from dnd.core.modifiers import AdvantageStatus
from dnd.entity import Entity
from dnd.game import Game
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.facts import DamageResultFact, LifeFact, PlayerLineage, SensoryFact, SpellFact
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import FireBolt, LightningBolt
from dnd.spells.illusion import Invisibility
from tests.engine.support import setup_combat_arena


@contextmanager
def cast_world(visibility, *, death_saves=True):
    rng = random.getstate()
    reset_engine_runtime()
    built = build_battlefield('battlefield.open_floor_bright')
    game = Game()
    try:
        caster = create_premade_character(SORCERER_PREMADE_ID, position=(5, 5), faction='red')
        target = create_premade_character(SORCERER_PREMADE_ID, position=(8, 5), faction='blue')
        target.uses_death_saves = death_saves
        for actor in (caster, target):
            game.deploy_entity(actor, actor.position)
        encounter = setup_combat_arena(caster, target)
        encounter.start_encounter()
        if visibility == 'spell':
            cast = Invisibility(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid).apply()
            assert cast is not None and not cast.canceled
            caster.on_turn_start(round_number=2)
        elif visibility == 'persistent':
            caster.add_condition(Invisible(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
        elif visibility == 'greater':
            caster.add_condition(GreaterInvisibilityEffect(
                source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
        Entity.update_all_entities_senses()
        session = SessionProjection()
        state, _ = begin_projection(session, capture_interval(name='invisibility delivery', start_cursor=0,
            end_cursor=EventQueue.event_cursor(), observer_uuid=target.uuid,
            battlefield_id=built.definition.battlefield_id))
        yield caster, target, session, state
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(rng)


def public_cast(world, spell, faces):
    caster, target, session, state = world
    before = EventQueue.event_cursor()
    with fixed_dice_faces(*faces):
        result = spell.apply()
    assert result is not None and not result.canceled
    native = tuple(EventQueue.iter_events_since(before))
    codec = TypeAdapter(PlayerLineage)
    packets = tuple(codec.validate_json(codec.dump_json(packet))
        for line in capture_lineages((result,), observer_uuid=target.uuid)
        if (packet := project_lineage(session, state, line)) is not None)
    return result, native, packets


def revealed_occurrences(packets, identity):
    return [node.occurrence for packet in packets for node in packet.events
        if isinstance(node.fact, SensoryFact) and any(
            packet.sensory_rows.uuids[packet.sensory_rows.contact_uuid_index[row]] == identity
            for row in node.fact.entity_contacts_changed)]


@pytest.mark.parametrize('visibility', ['visible', 'spell'])
@pytest.mark.parametrize('face, death_saves, outcome', [(2, True, 'alive'), (6, True, 'dying'), (6, False, 'dead')])
def test_lightning_delivery_keeps_caster_and_reveal_before_surviving_or_terminal_damage(
        visibility, face, death_saves, outcome):
    with cast_world(visibility, death_saves=death_saves) as world:
        caster, target, _, _ = world
        _, native, packets = public_cast(world,
            LightningBolt(source_entity_uuid=caster.uuid, end_position=target.position), [face] * 200)
        assert target.health.life_state.value == outcome
        nodes = [node for packet in packets for node in packet.events]
        damage = [node for node in nodes if isinstance(node.fact, DamageResultFact)]
        assert damage and all(node.fact.source_entity_uuid == caster.uuid for node in damage)
        assert all(node.resolution is not None for node in damage)
        spell, = (node.fact for node in nodes if isinstance(node.fact, SpellFact)
            and node.fact.source_entity_uuid == caster.uuid and node.fact.name == 'Lightning Bolt')
        assert spell.area_geometry is not None and spell.area_geometry.origin == caster.position
        assert spell.aoe_position == caster.position
        if visibility == 'spell':
            reveals = [index for index, event in native if isinstance(event, SensoryUpdateEvent)
                and event.observer_uuid == target.uuid and caster.uuid in event.entity_contacts_changed]
            first_damage = min(index for index, event in native if event.event_type is EventType.TAKE_DAMAGE)
            assert reveals and min(reveals) < first_damage
            assert min(revealed_occurrences(packets, caster.uuid)) < min(node.occurrence for node in damage)
            life = [node.occurrence for node in nodes if isinstance(node.fact, LifeFact)]
            assert not life or min(revealed_occurrences(packets, caster.uuid)) < min(life)


def test_spell_attack_keeps_unseen_advantage_and_reveals_before_its_damage():
    with cast_world('spell') as world:
        caster, target, _, _ = world
        result, _, packets = public_cast(world,
            FireBolt(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid), [2, 17] + [4] * 200)
        assert result.dice_roll.advantage_status is AdvantageStatus.ADVANTAGE
        assert result.dice_roll.total - result.dice_roll.bonus == 17
        damage = [node for packet in packets for node in packet.events if isinstance(node.fact, DamageResultFact)]
        assert damage and all(node.fact.source_entity_uuid == caster.uuid for node in damage)
        assert min(revealed_occurrences(packets, caster.uuid)) < min(node.occurrence for node in damage)


@pytest.mark.parametrize('visibility', ['persistent', 'greater'])
def test_nonrevealing_invisibility_keeps_spell_source_private(visibility):
    with cast_world(visibility) as world:
        caster, target, _, _ = world
        _, _, packets = public_cast(world,
            LightningBolt(source_entity_uuid=caster.uuid, end_position=target.position),
            ([20] if visibility == 'greater' else []) + [6] * 200)
        assert caster.is_invisible
        if visibility == 'greater':
            assert caster.active_conditions['Invisible'].check_count == 1
        nodes = [node for packet in packets for node in packet.events]
        assert not any(isinstance(node.fact, SpellFact) for node in nodes)
        assert all(node.fact.source_entity_uuid is None for node in nodes
            if isinstance(node.fact, DamageResultFact))
        assert not revealed_occurrences(packets, caster.uuid)


def cancel_cast(event, source_entity_uuid):
    return event.cancel(status_message='Cast interrupted')


@pytest.mark.parametrize('phase', [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT])
def test_canceled_cast_does_not_reveal_or_damage(phase):
    with cast_world('spell') as world:
        caster, target, _, _ = world
        before = target.get_hp()
        caster.add_event_handler(EventHandler(name='Interrupt cast', source_entity_uuid=caster.uuid,
            trigger_conditions=[Trigger(event_type=EventType.CAST_SPELL, event_phase=phase)],
            event_processor=cancel_cast))
        result = LightningBolt(source_entity_uuid=caster.uuid, end_position=target.position).apply()
        assert result is not None and result.canceled
        assert caster.is_invisible and caster.uuid not in target.senses.entities
        assert target.get_hp() == before
