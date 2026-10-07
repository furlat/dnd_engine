"""Resumed capture publishes the same event-time facts as original-history capture."""

from uuid import uuid4

import pytest

from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import Blinded
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.core.life_types import LifeState
from dnd.entity import Entity, EntityConfig
from dnd.encounter import Encounter
from dnd.game import Game
from dnd.player.audience import PlayerAudience
from dnd.player.capture import CaptureCheckpoint, capture_interval, capture_lineages
from dnd.player.facts import PlayerSequence
from dnd.player.projection import begin_projection, project_lineage
from dnd.player.reduction import encode_player_sequence, reduce_initialization, reduce_lineage
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.summoning import SummonDepartureCause, TerminalOwnerRelease


@pytest.fixture
def world():
    reset_engine_runtime()
    build_battlefield('battlefield.open_floor_bright')
    game = Game()
    try:
        yield game
    finally:
        game.close()
        reset_engine_runtime()


def member(game, name, position, *, deploy=True):
    actor = Entity.create(uuid4(), name, config=EntityConfig(position=position,
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode='maximums')])))
    actor.compose_entity()
    if deploy:
        game.deploy_entity(actor, position)
    return actor


def test_hot_and_cold_capture_preserve_discovery_reacquisition_and_terminal_facts(world):
    first = member(world, 'First observer', (0, 3))
    second = member(world, 'Second observer', (0, 4))
    encounter = Encounter(name='Checkpoint observations', source_entity_uuid=first.uuid)
    for observer in (first, second):
        encounter.add_combatant(observer, HumanController(source_entity_uuid=observer.uuid))
    encounter.start_encounter()
    audience = PlayerAudience((first.uuid, second.uuid), (first.uuid, second.uuid))
    checkpoint = CaptureCheckpoint(EventQueue.generation_id(), audience)
    arguments = dict(name='checkpoint parity', start_cursor=0, end_cursor=EventQueue.event_cursor(),
        observer_uuid=first.uuid, audience=audience, battlefield_id='battlefield.open_floor_bright')
    original = capture_interval(**arguments)
    assert capture_interval(**arguments, checkpoint=checkpoint) == original
    hot_projection, initial = begin_projection(original)
    cold_projection, _ = begin_projection(original)
    hot = cold = reduce_initialization(initial)
    cursor = EventQueue.event_cursor()

    def consume():
        nonlocal hot, cold, cursor
        roots = tuple(event for _, event in EventQueue.iter_events_since(cursor)
            if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
        arguments = dict(observer_uuid=first.uuid, audience=audience,
            known_actor_uuids=frozenset(hot.actors),
            known_entity_names={str(identity): actor.name for identity, actor in hot.actors.items()})
        resumed = capture_lineages(roots, **arguments, checkpoint=checkpoint)
        original = capture_lineages(roots, **arguments)
        assert resumed == original
        for left, right in zip(resumed, original, strict=True):
            hot_public = project_lineage(hot_projection, left)
            cold_public = project_lineage(cold_projection, right)
            assert hot_public == cold_public
            if hot_public is not None:
                assert encode_player_sequence(PlayerSequence(initialization=initial, lineages=(hot_public,))) == (
                    encode_player_sequence(PlayerSequence(initialization=initial, lineages=(cold_public,))))
                hot = reduce_lineage(hot, hot_public)
                cold = reduce_lineage(cold, cold_public)
        assert hot == cold
        cursor = EventQueue.event_cursor()
        return roots, arguments, resumed

    unseen = member(world, 'Previously unseen', (4, 3), deploy=False)
    dagger = build_authored_item('weapon.dagger', unseen.uuid)
    assert unseen.loot_item(dagger) and unseen.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
    unseen.add_condition(Blinded(source_entity_uuid=unseen.uuid, target_entity_uuid=unseen.uuid))
    unseen.receive_damage(7, DamageType.FORCE, source_entity_uuid=unseen.uuid)
    consume()
    assert unseen.uuid not in hot.actors

    world.deploy_entity(unseen, unseen.position)
    unseen.receive_damage(2, DamageType.FORCE, source_entity_uuid=unseen.uuid)
    earlier_roots, earlier_arguments, earlier_capture = consume()
    discovered = next(row for root in earlier_capture for row in root.admissions if row.actor.uuid == unseen.uuid)
    assert discovered.actor.normal_hp == 33, 'Discovery must precede the later damage in the same operation'
    assert dict(discovered.actor.equipment)[WeaponSlot.MELEE_MAIN.value] == dagger.uuid
    assert any(condition.name == 'Blinded' for condition in discovered.actor.conditions)
    assert unseen.get_normal_hp() == 31
    assert hot.actors[unseen.uuid].normal_hp == 31

    unseen.remove_condition('Blinded')
    assert unseen.unequip_item(WeaponSlot.MELEE_MAIN)
    consume()
    assert 'Blinded' not in unseen.active_conditions
    assert not any(condition.name == 'Blinded' for condition in hot.actors[unseen.uuid].conditions)
    world.remove_entity(unseen.uuid)
    consume()
    remembered_hp = hot.actors[unseen.uuid].normal_hp
    unseen.receive_damage(3, DamageType.FORCE, source_entity_uuid=unseen.uuid)
    consume()
    assert hot.actors[unseen.uuid].normal_hp == remembered_hp, 'Unseen damage must remain private'
    world.deploy_entity(unseen, unseen.position)
    _, _, reacquired = consume()
    assert any(row.actor.uuid == unseen.uuid and row.actor.normal_hp == 28
        for root in reacquired for row in root.admissions)
    assert hot.actors[unseen.uuid].normal_hp == 28

    unseen.receive_damage(1000, DamageType.FORCE, source_entity_uuid=first.uuid)
    consume()
    assert hot.actors[unseen.uuid].life_state is LifeState.DEAD
    prepared = world.prepare_entity_retirement(unseen.uuid, cause=TerminalOwnerRelease(
        entity_uuid=unseen.uuid, existence_condition_uuid=uuid4(), cause=SummonDepartureCause.EXPIRED))
    assert prepared is not None
    world.commit_entity_retirement(prepared)
    consume()
    assert unseen.uuid in hot.actors, 'Retiring private reconstruction must preserve admitted public identity'
    assert unseen.uuid not in checkpoint.actors
    assert all(unseen.uuid not in contacts for contacts in checkpoint.contacts.values())
    assert discovered.actor.normal_hp == 33

    # A historical request after the hot cursor must reconstruct the original
    # event-time state instead of using the newest actor/contact snapshot.
    assert capture_lineages(earlier_roots, **earlier_arguments, checkpoint=checkpoint) == earlier_capture


def test_capture_checkpoint_resets_with_event_queue_generation(world):
    first = member(world, 'Old generation', (2, 2))
    audience = PlayerAudience((first.uuid,), (first.uuid,))
    checkpoint = CaptureCheckpoint(EventQueue.generation_id(), audience)
    capture_interval(name='old', start_cursor=0, end_cursor=EventQueue.event_cursor(),
        observer_uuid=first.uuid, audience=audience, battlefield_id='battlefield.open_floor_bright',
        checkpoint=checkpoint)
    old_event = next(EventQueue.iter_events_since(0))[1]
    assert EventQueue.get_event_index(old_event.uuid) == 0
    world.close()
    reset_engine_runtime()
    build_battlefield('battlefield.open_floor_bright')
    second = member(world, 'New generation', (2, 2))
    assert EventQueue.get_event_index(old_event.uuid) is None
    audience = PlayerAudience((second.uuid,), (second.uuid,))
    arguments = dict(name='new', start_cursor=0, end_cursor=EventQueue.event_cursor(),
        observer_uuid=second.uuid, audience=audience, battlefield_id='battlefield.open_floor_bright')
    assert capture_interval(**arguments, checkpoint=checkpoint) == capture_interval(**arguments)
    assert first.uuid not in checkpoint.actors and second.uuid in checkpoint.actors
