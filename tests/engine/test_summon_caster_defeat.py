"""Real caster defeat retires linked bodies without inventing a summon death."""

import pytest
from uuid import uuid4

from dnd.controller import Controller, CodexController, HumanController
from dnd.ai.runtime.controller import NativeAIController
from dnd.ai.runtime.assignment_lifecycle import AIAssignmentState
from dnd.conditions import Unconscious, Stunned, Paralyzed
from dnd.core.creature_types import DamageType
from dnd.core.events import ControllerAssignmentChangedEvent, EventPhase, EventQueue, SpatialChangeEvent, EventHandler, EventType, Trigger
from dnd.core.life_types import LifeState
from dnd.entity import Entity, EntityConfig
from dnd.blocks.health import HealthConfig
from dnd.spells.abjuration import DeathWardEffect
from dnd.spells.summoning import ConjureFey, SpiritualWeapon, ConjureElemental
from dnd.types.event_facts import GroupEntryKind
from tests.engine.test_summon_controller_ownership import FAMILIES
from tests.engine.test_summoning_lifecycle import battle, cast_one


@pytest.mark.parametrize('spell,form,level', FAMILIES)
def test_caster_downing_dismisses_every_family(battle, spell, form, level):
    game, encounter, system, caster, enemy = battle
    caster.uses_death_saves = True
    member = cast_one(battle, spell, form, max(3, level))
    borrowed = member.controller
    cursor = EventQueue.event_cursor()
    caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
    assert caster.health.life_state is LifeState.DYING
    assert member.entity.uuid not in game.entities
    assert member.entity.uuid not in system.memberships
    assert member.entity.uuid not in encounter.combatants
    assert Entity.get(member.entity.uuid) is None
    assert Controller.get(borrowed.uuid) is borrowed
    events = [event for _, event in EventQueue.iter_events_since(cursor)
        if event.phase is EventPhase.COMPLETION]
    changes = [event for event in events if isinstance(event, ControllerAssignmentChangedEvent)
        and event.entity_uuid == member.entity.uuid]
    assert len(changes) == 1 and changes[0].controller_uuid is None
    departures = [event for event in events if isinstance(event, SpatialChangeEvent)
        and event.entity_uuid == member.entity.uuid and event.terminal_release is not None]
    assert len(departures) == 1
    assert departures[0].terminal_release.cause.value in {'caster_defeated', 'sustain_lost'}
    assert member.owned_ai is None


@pytest.mark.parametrize('mode', ['human', 'codex', 'ai'])
def test_defeat_releases_only_owned_controller_resources(battle, mode):
    game, encounter, system, caster, enemy = battle
    controller = (NativeAIController.create(source_entity_uuid=caster.uuid, game_id=str(system.uuid),
        assignment_id='caster', controlled_entity_uuids=(caster.uuid,), knowledge=system.ai_knowledge)
        if mode == 'ai' else (CodexController if mode == 'codex' else HumanController)(source_entity_uuid=caster.uuid))
    encounter.set_controller_for(caster.uuid, controller)
    if mode == 'ai':
        controller.start([caster])
        ally = Entity.create(source_entity_uuid=uuid4(), name='Standing ally', config=EntityConfig(
            faction=caster.faction, position=(5, 3), health=HealthConfig(max_hit_points_bonus=20)))
        ally.compose_entity()
        game.deploy_entity(ally, ally.position)
        encounter.add_combatant(ally, HumanController(source_entity_uuid=ally.uuid))
        encounter.initiative_order.append(ally.uuid)
    try:
        member = cast_one(battle, SpiritualWeapon, 'spiritual_weapon', 3)
        caster.uses_death_saves = True
        caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
        assert member.entity.uuid not in system.memberships
        assert Controller.get(controller.uuid) is controller
        if mode == 'ai':
            assert member.owned_ai.assignment.state is AIAssignmentState.CLOSED
            assert Controller.get(member.owned_ai.uuid) is None
            assert controller.assignment.state is AIAssignmentState.STARTED
    finally:
        if mode == 'ai':
            controller.close()
            controller.remove_from_register()


@pytest.mark.parametrize('transition', ['dying', 'stable', 'instant_death'])
def test_direct_committed_life_changes_cleanup_without_damage(battle, transition):
    game, _, _, caster, enemy = battle
    member = cast_one(battle, SpiritualWeapon, 'spiritual_weapon', 3)
    caster.uses_death_saves = True
    if transition == 'dying':
        caster.enter_dying_state()
    elif transition == 'stable':
        caster.health.damage_taken = caster.get_max_hp()
        assert caster.stabilize()
    else:
        assert not caster.receive_instant_death(enemy.uuid).canceled
    assert member.entity.uuid not in game.entities


def test_released_fey_still_departs_with_original_caster(battle):
    game, _, _, caster, enemy = battle
    member = cast_one(battle, ConjureFey, 'wolf', 6)
    assert caster.remove_condition('Concentrating')
    assert member.entity.faction != caster.faction
    owned = member.owned_ai
    caster.uses_death_saves = True
    caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
    assert member.entity.uuid not in game.entities
    assert owned.assignment.state is AIAssignmentState.CLOSED


def test_grouped_instant_death_retires_fey_without_hostile_handover(battle):
    game, _, _, caster, enemy = battle
    member = cast_one(battle, ConjureFey, 'wolf', 6)
    cursor = EventQueue.event_cursor()
    with EventQueue.group(GroupEntryKind.AREA_APPLICATION):
        assert not caster.receive_instant_death(enemy.uuid).canceled
        assert member.entity.uuid in game.entities
    assert member.entity.uuid not in game.entities
    changes = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ControllerAssignmentChangedEvent) and event.phase is EventPhase.COMPLETION
        and event.entity_uuid == member.entity.uuid]
    assert len(changes) == 1 and changes[0].controller_uuid is None
    assert member.owned_ai is None


@pytest.mark.parametrize('grouped', [False, True])
def test_prevented_death_completes_deferred_fey_handover(battle, grouped):
    game, encounter, _, caster, enemy = battle
    member = cast_one(battle, ConjureFey, 'wolf', 6)
    handler = EventHandler(source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.DEATH, event_phase=EventPhase.EXECUTION)],
        event_processor=lambda event, _: event.cancel(status_message='Death prevented'))
    EventQueue.add_event_handler(handler)
    try:
        if grouped:
            with EventQueue.group(GroupEntryKind.AREA_APPLICATION):
                caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
        else:
            caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
        assert caster.health.life_state is LifeState.ALIVE and caster.get_normal_hp() == 1
        assert member.entity.uuid in game.entities and not member.control.applied
        assert member.owned_ai is not None
        assert encounter.get_controller_for(member.entity.uuid) is member.owned_ai
        assert member.owned_ai.assignment.state is AIAssignmentState.STARTED
        assert member.entity.faction != caster.faction
    finally:
        handler.remove()
        handler.remove_from_register()


@pytest.mark.parametrize('prevention', ['death_ward', 'temporary_hp', 'canceled_damage'])
def test_no_caster_defeat_means_no_independent_summon_cleanup(battle, prevention):
    game, _, _, caster, enemy = battle
    member = cast_one(battle, SpiritualWeapon, 'spiritual_weapon', 3)
    amount = caster.get_normal_hp()
    handler = None
    if prevention == 'death_ward':
        assert not caster.add_condition(DeathWardEffect(source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid)).canceled
    elif prevention == 'temporary_hp':
        caster.health.add_temporary_hit_points(amount, caster.uuid)
    else:
        handler = EventHandler(source_entity_uuid=caster.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TAKE_DAMAGE, event_phase=EventPhase.EXECUTION)],
            event_processor=lambda event, _: event.cancel(status_message='Damage prevented'))
        EventQueue.add_event_handler(handler)
    try:
        caster.receive_damage(amount, DamageType.FORCE, enemy.uuid)
        assert caster.health.life_state is LifeState.ALIVE and caster.get_normal_hp() > 0
        assert member.entity.uuid in game.entities and member.existence.applied
    finally:
        if handler is not None:
            handler.remove()
            handler.remove_from_register()


@pytest.mark.parametrize('condition', [Unconscious, Stunned, Paralyzed])
def test_positive_hp_impairment_adds_no_independent_summon_dismissal(battle, condition):
    game, _, _, caster, enemy = battle
    member = cast_one(battle, SpiritualWeapon, 'spiritual_weapon', 3)
    assert not caster.add_condition(condition(source_entity_uuid=enemy.uuid, target_entity_uuid=caster.uuid)).canceled
    assert caster.get_normal_hp() > 0 and member.entity.uuid in game.entities


def test_sibling_cleanup_settles_once_and_healing_does_not_restore_summons(battle):
    game, encounter, system, caster, enemy = battle
    first = cast_one(battle, ConjureElemental, 'air_elemental', 5)
    caster.action_economy.reset_all_costs()
    result = SpiritualWeapon(source_entity_uuid=caster.uuid, cast_at_level=3, end_position=(4, 3)).apply()
    assert not result.canceled
    identities = set(system.memberships)
    assert len(identities) == 2
    caster.uses_death_saves = True
    cursor = EventQueue.event_cursor()
    caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
    assert caster.stabilize()
    caster.receive_healing(5, caster.uuid)
    assert not identities.intersection(game.entities)
    assert not system.memberships
    assert not first.entity.has_runtime_agency()
    completed = [event for _, event in EventQueue.iter_events_since(cursor) if event.phase is EventPhase.COMPLETION]
    leaves = [event for event in completed if isinstance(event, SpatialChangeEvent)
        and event.entity_uuid in identities and event.terminal_release is not None]
    assert len(leaves) == 2
    end, = (index for index, event in enumerate(completed) if event.event_type is EventType.ENCOUNTER_END)
    assert all(completed.index(event) < end for event in leaves)


def test_simultaneous_caster_and_summon_hits_keep_group_entry_targets(battle):
    game, _, system, caster, enemy = battle
    member = cast_one(battle, SpiritualWeapon, 'spiritual_weapon', 3)
    caster.uses_death_saves = True
    cursor = EventQueue.event_cursor()
    with EventQueue.group(GroupEntryKind.AREA_APPLICATION):
        caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
        assert member.entity.uuid in game.entities
        member.entity.receive_damage(1, DamageType.FORCE, enemy.uuid)
    assert member.entity.uuid not in system.memberships
    leaves = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent) and event.phase is EventPhase.COMPLETION
        and event.entity_uuid == member.entity.uuid and event.terminal_release is not None]
    assert len(leaves) == 1


def test_simultaneous_caster_defeats_retire_both_sides_before_encounter_end(battle):
    game, _, system, caster, enemy = battle
    cast_one(battle, SpiritualWeapon, 'spiritual_weapon', 3)
    result = SpiritualWeapon(source_entity_uuid=enemy.uuid, cast_at_level=3, end_position=(14, 2)).apply()
    assert not result.canceled
    identities = set(system.memberships)
    assert len(identities) == 2
    caster.uses_death_saves = enemy.uses_death_saves = True
    cursor = EventQueue.event_cursor()
    with EventQueue.group(GroupEntryKind.AREA_APPLICATION):
        caster.receive_damage(caster.get_normal_hp(), DamageType.FORCE, enemy.uuid)
        enemy.receive_damage(enemy.get_normal_hp(), DamageType.FORCE, caster.uuid)
        assert identities.issubset(game.entities)
    assert not identities.intersection(game.entities)
    completed = [event for _, event in EventQueue.iter_events_since(cursor)
        if event.phase is EventPhase.COMPLETION]
    departures = [index for index, event in enumerate(completed)
        if isinstance(event, SpatialChangeEvent) and event.entity_uuid in identities
        and event.terminal_release is not None]
    end, = (index for index, event in enumerate(completed) if event.event_type is EventType.ENCOUNTER_END)
    assert len(departures) == 2 and max(departures) < end
