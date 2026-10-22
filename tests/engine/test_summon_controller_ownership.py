"""Summon authority follows the caster without owning an external controller.

Native casts, live encounter turns and settled condition removal preserve real
body, budget and controller lifetimes. Assignment publications precede birth and
retirement sensory evidence; initial-party companion rules stay independent.
"""

from uuid import uuid4

import pytest

from dnd.controller import CodexController, HumanController, Controller, ControllerExecutionMode
from dnd.ai.runtime.controller import NativeAIController
from dnd.ai.runtime.assignment_lifecycle import AIAssignmentState
from dnd.core.events import ControllerAssignmentChangedEvent, EntityCreatedEvent, SensoryUpdateEvent, EventPhase, EventQueue, EventType, EventHandler, Trigger
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.encounter import Encounter
from dnd.actions import Move
from dnd.conditions import Invisible
from dnd.ai.runtime.knowledge_system import AIKnowledgeSystem
from dnd.entity import Entity
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.spells.summoning import (
    ConjureAnimals, ConjureFey, ConjureFiend, ConjureElemental, PlanarAlly,
    SummonDragon, SpiritualWeapon, FlamingSphere,
)
from tests.engine.test_summoning_lifecycle import battle, cast_one


FAMILIES = (
    (ConjureAnimals, 'wolf', 3), (ConjureFey, 'jaguar', 6),
    (ConjureFiend, 'dretch', 3), (ConjureElemental, 'air_elemental', 5),
    (PlanarAlly, 'deva', 6), (SummonDragon, 'red', 5),
    (SpiritualWeapon, 'spiritual_weapon', 2), (FlamingSphere, 'flaming_sphere', 2),
)


@pytest.mark.parametrize('controller_kind', [HumanController, CodexController])
@pytest.mark.parametrize('spell,form,level', FAMILIES)
def test_external_summon_borrows_caster_controller_and_waits(battle, controller_kind, spell, form, level):
    _, encounter, _, caster, _ = battle
    controller = controller_kind(source_entity_uuid=caster.uuid)
    encounter.set_controller_for(caster.uuid, controller)
    caster.action_economy.set_normal_spell_slot_capacity(uuid4(), {rank: 3 for rank in range(2, 10)})
    cursor = EventQueue.event_cursor()
    member = cast_one(battle, spell, form, level)
    assert member.controller is controller
    assert member.owned_ai is None
    combatant = encounter.combatants[member.entity.uuid]
    assert combatant.external_owner_uuid == caster.uuid
    changes = [(index, event) for index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ControllerAssignmentChangedEvent) and event.entity_uuid == member.entity.uuid]
    assert len(changes) == 1
    index, changed = changes[0]
    birth, = (index for index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, EntityCreatedEvent) and event.entity_uuid == member.entity.uuid)
    assert index < birth
    assert changed.previous_controller_uuid is None and changed.controller_uuid == controller.uuid
    assert changed.previous_external_owner_uuid is None and changed.new_external_owner_uuid == caster.uuid
    assert changed.execution_mode is ControllerExecutionMode.EXTERNAL
    assert changed.parent_event is not None
    assert not member.entity.is_player_companion
    encounter.next_turn()
    assert encounter.get_current_entity() is member.entity
    before = member.entity.get_normal_hp(), member.entity.action_economy.actions.normalized_score
    boundary = encounter.advance_one_controller_action_boundary()
    assert boundary.status == ('waiting_for_codex' if controller_kind is CodexController else 'waiting_for_human')
    assert before == (member.entity.get_normal_hp(), member.entity.action_economy.actions.normalized_score)


@pytest.mark.parametrize('spell,form,level', FAMILIES)
def test_native_ai_caster_keeps_independent_started_summon_assignment(battle, spell, form, level):
    _, encounter, system, caster, _ = battle
    controller = NativeAIController.create(source_entity_uuid=caster.uuid,
        game_id=str(system.uuid), assignment_id='native-caster',
        controlled_entity_uuids=(caster.uuid,), knowledge=system.ai_knowledge)
    try:
        encounter.set_controller_for(caster.uuid, controller)
        controller.start([caster])
        caster.action_economy.set_normal_spell_slot_capacity(uuid4(), {rank: 3 for rank in range(2, 10)})
        member = cast_one(battle, spell, form, level)
        assert member.controller is member.owned_ai and member.owned_ai is not None
        assert member.controller is not controller
        assert member.owned_ai.assignment.state is AIAssignmentState.STARTED
        assert member.owned_ai.controlled_entity_uuids == (member.entity.uuid,)
        assert controller.controlled_entity_uuids == (caster.uuid,)
        assert encounter.combatants[member.entity.uuid].external_owner_uuid is None
        assert not member.entity.is_player_companion
        assert member.entity.remove_condition_by_uuid(member.existence.uuid)
        assert member.owned_ai.assignment.state is AIAssignmentState.CLOSED
        assert Controller.get(member.owned_ai.uuid) is None
        assert controller.assignment.state is AIAssignmentState.STARTED
    finally:
        controller.close()
        controller.remove_from_register()


def test_fey_handover_preserves_turn_budget_and_leaves_borrowed_controller_alive(battle):
    _, encounter, system, caster, _ = battle
    borrowed = encounter.get_controller_for(caster.uuid)
    member = cast_one(battle, ConjureFey, 'wolf', 6)
    actor = member.entity
    encounter.next_turn()
    actor.action_economy.consume('movement', 5, 'Already moved')
    actor.action_economy.consume('actions', 1, 'Already acted')
    before = (actor.uuid, actor.get_normal_hp(), actor.action_economy.movement_remaining(),
        actor.action_economy.actions.normalized_score, member.existence.duration.duration,
        encounter.current_turn_execution_id)
    cursor = EventQueue.event_cursor()
    assert caster.remove_condition('Concentrating')
    assert member.owned_ai is not None and member.controller is member.owned_ai
    assert member.owned_ai.assignment.state is AIAssignmentState.STARTED
    assert before == (actor.uuid, actor.get_normal_hp(), actor.action_economy.movement_remaining(),
        actor.action_economy.actions.normalized_score, member.existence.duration.duration,
        encounter.current_turn_execution_id)
    assert encounter.get_controller_for(caster.uuid) is borrowed
    assert Controller.get(borrowed.uuid) is borrowed
    assert actor.faction != caster.faction
    changes = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ControllerAssignmentChangedEvent) and event.entity_uuid == actor.uuid]
    change, = changes
    assert change.previous_controller_uuid == borrowed.uuid and change.previous_external_owner_uuid == caster.uuid
    assert change.controller_uuid == member.owned_ai.uuid and change.new_external_owner_uuid is None
    assert change.execution_mode is ControllerExecutionMode.AUTONOMOUS
    assert change.parent_event is not None


@pytest.mark.parametrize('retire', ['dismiss', 'defeat', 'close'])
def test_retirement_revokes_only_one_borrowed_body_before_detach(battle, retire):
    _, encounter, system, caster, _ = battle
    borrowed = encounter.get_controller_for(caster.uuid)
    first = cast_one(battle, ConjureElemental, 'air_elemental', 5)
    caster.action_economy.reset_all_costs()
    result = SpiritualWeapon(source_entity_uuid=caster.uuid, cast_at_level=3,
        end_position=(4, 3)).apply()
    assert result is not None and not result.canceled
    sibling = next(member for member in system.memberships.values() if member is not first)
    cursor = EventQueue.event_cursor()
    if retire == 'defeat':
        first.entity.receive_damage(1000, DamageType.FORCE, caster.uuid)
    elif retire == 'close':
        system.close()
    else:
        assert first.entity.remove_condition_by_uuid(first.existence.uuid)
    changes = [(index, event) for index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ControllerAssignmentChangedEvent) and event.entity_uuid == first.entity.uuid]
    index, change = changes[0]
    assert len(changes) == 1 and change.controller_uuid is None
    assert change.previous_controller_uuid == borrowed.uuid
    assert change.previous_external_owner_uuid == caster.uuid and change.new_external_owner_uuid is None
    departed = [i for i, event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.SPATIAL_ENTITY_LEFT and event.entity_uuid == first.entity.uuid]
    assert departed and index < min(departed)
    assert encounter.get_controller_for(caster.uuid) is borrowed
    assert Controller.get(borrowed.uuid) is borrowed
    if retire != 'close':
        assert encounter.get_controller_for(sibling.entity.uuid) is borrowed
        assert sibling.entity.uuid in system.memberships


def test_whole_fey_departure_never_transiently_assigns_hostile_ai(battle):
    _, encounter, _, caster, _ = battle
    member = cast_one(battle, ConjureFey, 'wolf', 6)
    cursor = EventQueue.event_cursor()
    assert member.entity.remove_condition_by_uuid(member.existence.uuid)
    changes = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ControllerAssignmentChangedEvent) and event.entity_uuid == member.entity.uuid]
    change, = changes
    assert change.controller_uuid is None and change.new_external_owner_uuid is None
    assert member.owned_ai is None
    assert encounter.get_controller_for(caster.uuid) is member.controller


def test_external_rebind_resolves_new_caster_assignment_without_closing_old_controller(battle):
    _, previous, system, caster, enemy = battle
    member = cast_one(battle, ConjureFey, 'wolf', 6)
    borrowed = member.controller
    previous.end_encounter()
    later = Encounter(source_entity_uuid=uuid4(), name='Later external encounter')
    incoming = CodexController(source_entity_uuid=caster.uuid)
    later.add_combatant(caster, incoming)
    later.add_combatant(enemy, HumanController(source_entity_uuid=enemy.uuid))
    later.initiative_order = [caster.uuid, enemy.uuid]
    later.start_encounter()
    before = member.entity.uuid, member.entity.get_normal_hp(), member.existence.duration.duration
    cursor = EventQueue.event_cursor()
    system.rebind_encounter(later)
    assert member.controller is incoming and member.owned_ai is None
    assert before == (member.entity.uuid, member.entity.get_normal_hp(), member.existence.duration.duration)
    assert Controller.get(borrowed.uuid) is borrowed
    assert not member.entity.is_player_companion
    changes = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ControllerAssignmentChangedEvent) and event.entity_uuid == member.entity.uuid]
    assert [(event.previous_external_owner_uuid, event.new_external_owner_uuid) for event in changes] == [
        (caster.uuid, None), (None, caster.uuid)]
    assert previous.get_controller_for(member.entity.uuid) is None
    initials = [(index, event) for index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == member.entity.uuid and event.initial]
    initial_index, initial = initials[0]
    assert len(initials) == 1
    grant_index, grant = next((index, event) for index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ControllerAssignmentChangedEvent) and event.new_external_owner_uuid == caster.uuid)
    assert grant_index < initial_index and initial.parent_lineage == grant.lineage_uuid
    assert initial.observer_position == member.entity.position


def test_vetoed_replacement_keeps_original_borrowed_authority_and_has_no_grant(battle):
    _, encounter, system, caster, _ = battle
    first = cast_one(battle)
    borrowed = first.controller
    controllers = {controller.uuid for controller in Controller.get_all()}
    caster.action_economy.reset_all_costs()
    cursor = EventQueue.event_cursor()

    def reject_new_existence(event, _):
        if isinstance(event, ConditionApplicationEvent) and event.condition.name == 'Summoned':
            return event.cancel(status_message='Reject new summon existence')
        return None

    handler = EventHandler(source_entity_uuid=caster.uuid, event_processor=reject_new_existence,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION, event_phase=EventPhase.EXECUTION)])
    EventQueue.add_event_handler(handler)
    try:
        result = ConjureAnimals(source_entity_uuid=caster.uuid, form_id='boar',
            cast_at_level=3, end_position=(4, 3)).apply()
        assert result is not None and result.canceled
        assert system.memberships == {first.entity.uuid: first}
        assert encounter.get_controller_for(first.entity.uuid) is borrowed
        assert encounter.get_controller_for(caster.uuid) is borrowed
        assert {controller.uuid for controller in Controller.get_all()} == controllers
        assert not [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ControllerAssignmentChangedEvent)]
    finally:
        handler.remove()
        handler.remove_from_register()


def test_assignment_observer_failure_does_not_undo_tracked_native_membership(battle, caplog):
    game, encounter, system, caster, _ = battle
    borrowed = encounter.get_controller_for(caster.uuid)
    emitted = []

    def publication_fails(event):
        if isinstance(event, ControllerAssignmentChangedEvent) and event.new_external_owner_uuid == caster.uuid:
            emitted.append(event.entity_uuid)
            assert event.entity_uuid in system.memberships
            raise RuntimeError('Assignment transport receiver failed after native commitment')

    EventQueue.add_on_event_callback(publication_fails)
    try:
        result = ConjureAnimals(source_entity_uuid=caster.uuid, form_id='wolf', cast_at_level=3,
            end_position=(4, 2)).apply()
        assert result is not None and not result.canceled
        assert 'Assignment transport receiver failed after native commitment' in caplog.text
    finally:
        EventQueue.remove_on_event_callback(publication_fails)
    identity, = emitted
    member = system.memberships[identity]
    assert game.get_entity(identity) is member.entity
    assert member.entity.creation_committed and member.entity.is_deployed
    assert encounter.get_controller_for(identity) is borrowed
    assert member.owned_ai is None
    assert member.entity.remove_condition_by_uuid(member.existence.uuid)
    assert Controller.get(borrowed.uuid) is borrowed


def test_fey_voluntary_veto_disposes_prepared_ai_without_revoking_control(battle):
    _, encounter, system, caster, _ = battle
    member = cast_one(battle, ConjureFey, 'wolf', 6)
    controllers = {controller.uuid for controller in Controller.get_all()}
    borrowed = member.controller

    # A later genuine linked child rejects after SummonControl already admitted
    # its independent AI assignment. Cancellation must release that resource.
    invisible = Invisible(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid)
    assert not caster.add_condition(invisible).canceled
    caster.active_conditions['Concentrating'].add_linked_condition(caster.uuid, invisible.uuid)
    prepared_ai = []

    def reject_concentration(event, _):
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == invisible.uuid:
            prepared_ai.extend(controller for controller in Controller.get_all()
                if controller.uuid not in controllers)
            return event.cancel(status_message='Keep later linked child')
        return None

    handler = EventHandler(source_entity_uuid=caster.uuid, event_processor=reject_concentration,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.EFFECT)])
    EventQueue.add_event_handler(handler)
    try:
        assert not caster.remove_condition('Concentrating')
        assert member.control.applied and member.owned_ai is None
        assert encounter.get_controller_for(member.entity.uuid) is borrowed
        assert {controller.uuid for controller in Controller.get_all()} == controllers
        assert not system.ai_knowledge.knowledge
        assert len(prepared_ai) == 1
        assert prepared_ai[0].assignment.state is AIAssignmentState.CLOSED
    finally:
        handler.remove()
        handler.remove_from_register()


@pytest.mark.parametrize('mandatory', [False, True])
def test_unavailable_fey_ai_admission_vetoes_voluntary_loss_but_mandatory_loss_revokes(battle, mandatory):
    _, encounter, system, caster, enemy = battle
    member = cast_one(battle, ConjureFey, 'wolf', 6)
    borrowed = member.controller
    # A real stale knowledge owner cannot start an assignment in this generation.
    system.ai_knowledge = AIKnowledgeSystem(uuid4())
    if mandatory:
        with fixed_dice_faces(1), pytest.raises(BaseExceptionGroup):
            caster.receive_damage(1, DamageType.FORCE, enemy.uuid)
        assert not member.control.applied and member.existence.applied
        assert member.controller is None and member.owned_ai is None
        assert encounter.get_controller_for(member.entity.uuid) is None
        assert encounter.combatants[member.entity.uuid].external_owner_uuid is None
        assert member.entity.faction != caster.faction
        assert Controller.get(borrowed.uuid) is borrowed
    else:
        assert not caster.remove_condition('Concentrating')
        assert member.control.applied and member.existence.applied
        assert member.controller is borrowed and member.owned_ai is None
        assert encounter.get_controller_for(member.entity.uuid) is borrowed


def test_existing_summon_observer_regrant_records_fresh_initial_after_assignment(battle):
    _, encounter, _, caster, _ = battle
    member = cast_one(battle)
    borrowed = member.controller
    cursor = EventQueue.event_cursor()
    encounter.set_controller_for(member.entity.uuid, None, promote_companion=False)
    encounter.set_controller_for(member.entity.uuid, borrowed,
        external_owner_uuid=caster.uuid, promote_companion=False)
    changes = [(index, event) for index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ControllerAssignmentChangedEvent)]
    assert len(changes) == 2
    grant_index, grant = changes[-1]
    initial_index, initial = next((index, event) for index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == member.entity.uuid and event.initial)
    assert grant_index < initial_index and initial.parent_lineage == grant.lineage_uuid
    assert initial.observer_position == member.entity.position
