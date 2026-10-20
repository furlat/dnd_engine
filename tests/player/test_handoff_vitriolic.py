"""Vitriolic Sphere's real cast and recipient turn ends retain public causes.

Input: initialized, visible encounter actors with enough HP to survive the acid.
Boundary: worker Choices/Command and actual EndTurn commands in both seat streams.
Output: exact resolved footprint and each recipient's own residue UUID on damage.
"""

from dnd.actions import SpellEvent
from dnd.actions_functional import register_spell
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import Channel, Kind, add_modifier
from dnd.player.commands import ActionSelection
from dnd.player.facts import DamageResultFact, SpellFact
from dnd.spells.evocation import VitriolicResidue, VitriolicSphere
from server.protocol import CommandRequest, EndTurnIntent, ExecuteSelectionIntent, PlayerOperation
from server.worker import dispatch, needs_advance
from server.worker_protocol import Advance, Command
from tests.manual.spell_regression_support import force_save_result
from tests.player.test_compact_choices import request_choices, rows, world


def serialized(records):
    return tuple(PlayerOperation.model_validate_json(record.model_dump_json()) for record in records)


def test_vitriolic_cast_footprint_and_each_residue_deadline_survive_both_seat_streams(world):
    runtime, seat, publication = world
    caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    recipients = [actor for actor in runtime.session.game.entities.values() if caster.is_enemy(actor)]
    assert len(recipients) == 6
    for recipient in recipients:
        add_modifier(recipient.health.max_hit_points_bonus, Channel.SELF_STATIC, Kind.VALUE,
            NumericalModifier(name='Survive initial and delayed acid', value=200,
                source_entity_uuid=recipient.uuid))
        assert recipient.get_normal_hp() >= 200
        force_save_result(recipient, 'dexterity', succeeds=False)
    register_spell(caster, VitriolicSphere, caster_level=7)
    choices = request_choices(world).choices
    action, = (row for row in rows(choices) if row.behavior_id == 'spell.vitriolic_sphere')
    aim = (10, 7)
    selection = ActionSelection(action_index=action.discovery_index, target_indices=(),
        extra_target_positions=(aim,))
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 200)):
        reply, delivered, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
            command_number=1, actor_uuid=caster.uuid, state_revision=publication.state_revision,
            intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation,
                selection=selection))))
    assert reply.rejection is None
    initial_records = serialized(delivered)
    expected = {(x, y) for x in range(6, 15) for y in range(3, 12)
        if (x - aim[0]) ** 2 + (y - aim[1]) ** 2 <= 16}
    native_casts = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpellEvent) and event.phase is EventPhase.COMPLETION
        and event.source_entity_uuid == caster.uuid and event.resolved_area_positions is not None]
    assert native_casts and all(set(event.resolved_area_positions) == expected for event in native_casts)
    assert len(initial_records) == 2
    observers = {record.observer_uuid for record in initial_records}
    for record in initial_records:
        casts = [node.fact for group in record.lineages for node in group.events
            if isinstance(node.fact, SpellFact) and node.fact.behavior_id == 'spell.vitriolic_sphere']
        assert any(fact.resolved_area_positions is not None
            and set(fact.resolved_area_positions) == expected for fact in casts)

    residues = {}
    for recipient in recipients:
        residue, = (condition for condition in recipient.active_conditions_by_uuid.values()
            if isinstance(condition, VitriolicResidue))
        residues[recipient.uuid] = residue.uuid
    assert len(set(residues.values())) == len(recipients)
    before_deadline_hp = {recipient.uuid: recipient.get_normal_hp() for recipient in recipients}
    deadline_cursor = EventQueue.event_cursor()
    deadline_records = []
    number = 1
    for _ in range(30):
        if all(residue not in runtime.session.game.entities[identity].active_conditions_by_uuid
               for identity, residue in residues.items()):
            break
        with fixed_dice_faces(*([2] * 200)):
            if needs_advance(runtime.session):
                _, delivered, _ = dispatch(runtime, Advance())
            else:
                turn_seat, turn = next((key, value) for key, value in runtime.publications.items()
                    if value.boundary.input_actor_uuid is not None)
                number += 1
                reply, delivered, _ = dispatch(runtime, Command(seat_id=turn_seat,
                    request=CommandRequest(command_number=number,
                        actor_uuid=turn.boundary.input_actor_uuid, state_revision=turn.state_revision,
                        intent=EndTurnIntent())))
                assert reply.rejection is None
        deadline_records.extend(serialized(delivered))
    else:
        raise AssertionError('Recipients did not finish their next actual turns')

    native_damage = [event for _, event in EventQueue.iter_events_since(deadline_cursor)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION
        and event.source_condition_uuid in residues.values()]
    assert len(native_damage) == len(recipients)
    assert {event.target_entity_uuid: event.source_condition_uuid for event in native_damage} == residues
    for recipient in recipients:
        assert recipient.get_normal_hp() == before_deadline_hp[recipient.uuid] - 10
        assert residues[recipient.uuid] not in recipient.active_conditions_by_uuid
    observed_damage = [(record.observer_uuid, node.fact)
        for record in deadline_records for group in record.lineages for node in group.events
        if isinstance(node.fact, DamageResultFact) and node.fact.target_entity_uuid in residues]
    assert len(observed_damage) == len(observers) * len(recipients)
    assert {(observer, fact.target_entity_uuid): fact.source_condition_uuid
            for observer, fact in observed_damage} == {
        (observer, recipient): residue for observer in observers for recipient, residue in residues.items()}
    assert all(fact.damage_type is DamageType.ACID and fact.applied_damage == 10
        for _, fact in observed_damage)
