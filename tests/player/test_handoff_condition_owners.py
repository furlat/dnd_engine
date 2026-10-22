"""Actual condition owners publish selected values and lifecycle transitions.

Worker casts and external summon commands produce the conditions. Both serialized
seat operations must retain their exact identities and committed after-values.
"""

from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from dnd.actions_functional import register_spell
from dnd.classes.paladin import PaladinAuraBenefit
from dnd.classes.rage import Frenzied, Raging
from dnd.content.characters.premades import BARBARIAN_PREMADE_ID
from dnd.core.base_conditions import ConditionStateChangedEvent
from dnd.core.content.encounters import EncounterRecipe, EncounterRosterRecipe, PremadeCharacterRosterSource
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.monsters.spell_summon_actions import (
    DraconicBreathCadence, DragonSharedResistance, ElementalMultiattackBonus, MyrmidonStrikeDice,
)
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.audience import PlayerAudience
from dnd.player.content_composition import ui_content_manifest
from dnd.player.commands import ActionSelection
from dnd.player.facts import ActorChangeFact, PlayerInitialization, PlayerUpdate
from dnd.player.reduction import reduce_initialization
from dnd.player.session import close_session, create_session
from dnd.spells.summoning import ConjureElemental, SummonDragon
from dnd.types.actor_facts import ConditionRow
from dnd.types.character_progression import CharacterClass
from server.protocol import CommandRequest, EndTurnIntent, PlayerOperation
from server.worker import dispatch, needs_advance
from server.worker_protocol import Advance, Command
from tests.player.test_compact_choices import request_choices, rows, world
from tests.player.test_handoff_discovery_regressions import submit
from tests.player.test_handoff_passive_attribution import turning_recipe, workers
from tests.player.test_emitted_update_replica import operation_since
from tests.progression.prepared_class_support import prepared_build


def members(record):
    return [(body.actor_uuid, member) for group in record.lineages for body in group.bodies
            for member in body.body.conditions] + [
        (actor.actor_uuid, row.member) for group in record.lineages for node in group.events
        if isinstance(node.fact, ActorChangeFact) for actor in node.fact.actors for row in actor.rows
        if isinstance(row, ConditionRow) and row.member is not None]


def state_changes(records, condition_uuid):
    return [member.state for record in records for _, member in members(record)
        if member.condition_uuid == condition_uuid and member.state is not None]


def test_frenzy_worker_publishes_exact_same_actor_raging_parent_in_both_streams(workers):
    recipe = turning_recipe()
    slot = recipe.roster_slots[0]
    member = slot.roster.members[0].model_copy(update={
        'source': PremadeCharacterRosterSource(premade_id=BARBARIAN_PREMADE_ID)})
    roster = EncounterRosterRecipe.create(roster_id='roster.frenzy_owner', title='Berserker', members=(member,))
    recipe = EncounterRecipe.create(encounter_id='encounter.frenzy_owner', title='Frenzy owner',
        battlefield_id=recipe.battlefield_id, deployment=recipe.deployment,
        roster_slots=(slot.model_copy(update={'roster': roster}), recipe.roster_slots[1]),
        opening_policy=recipe.opening_policy)
    runtime = workers(audience_ids={'cleric': uuid4(), 'undead': uuid4()}, recipe=recipe)
    while needs_advance(runtime.session):
        dispatch(runtime, Advance())
    seat, publication = next((key, value) for key, value in runtime.publications.items()
        if value.boundary.input_actor_uuid is not None)
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    discovered = request_choices((runtime, seat, publication)).choices
    action, = (row for row in rows(discovered) if row.behavior_id == 'action.class.barbarian.frenzy')
    binding, = discovered.target_sets[action.target_set]
    records = submit(runtime, seat, actor, discovered,
        ActionSelection(action.discovery_index, (binding.index,)), 1)
    raging, = (condition for condition in actor.active_conditions_by_uuid.values()
        if isinstance(condition, Raging))
    frenzied, = (condition for condition in actor.active_conditions_by_uuid.values()
        if isinstance(condition, Frenzied))
    assert frenzied.parent_condition == raging.uuid
    assert len(records) == 2
    for record in records:
        states = state_changes((record,), frenzied.uuid)
        assert states and all(state.parent_condition_uuid == raging.uuid for state in states)
        assert all(owner == actor.uuid for owner, member in members(record)
            if member.condition_uuid in (raging.uuid, frenzied.uuid))
        assert all(member.state.parent_condition_uuid is None for _, member in members(record)
            if member.state is not None and member.condition_uuid != frenzied.uuid)


def summoned_dragon(world, color="white"):
    runtime, seat, publication = world
    caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    caster.action_economy.set_normal_spell_slot_capacity(uuid4(), {5: 1})
    caster.action_economy.reset_spell_slot_costs()
    register_spell(caster, SummonDragon, caster_level=9)
    discovered = request_choices(world).choices
    dragon_rows = [row for row in rows(discovered) if row.behavior_id == 'spell.summon_dragon']
    assert len(dragon_rows) == 5
    assert {tuple((facet.key, facet.value) for facet in row.variant_facets) for row in dragon_rows} == {
        (("form", value),) for value in ("black", "blue", "green", "red", "white")}
    action, = (row for row in dragon_rows if row.variant_facets[0].value == color)
    with fixed_dice_faces(*([2] * 400)):
        records = submit(runtime, seat, caster, discovered,
            ActionSelection(action.discovery_index, (), extra_target_positions=((7, 7),)), 1)
    dragon = next(actor for actor in runtime.session.game.entities.values()
        if any(isinstance(condition, DraconicBreathCadence)
            for condition in actor.active_conditions_by_uuid.values()))
    cadence, = (condition for condition in dragon.active_conditions_by_uuid.values()
        if isinstance(condition, DraconicBreathCadence))
    return caster, dragon, cadence, records


def dragon_input(runtime, seat, dragon):
    while needs_advance(runtime.session):
        dispatch(runtime, Advance())
    assert runtime.publications[seat].boundary.input_actor_uuid == dragon.uuid


def dragon_action(runtime, seat, dragon, behavior, number):
    discovered = request_choices((runtime, seat, runtime.publications[seat])).choices
    action = next(row for row in rows(discovered) if row.behavior_id == behavior and row.can_afford)
    targets = discovered.target_sets[action.target_set]
    selection = (ActionSelection(action.discovery_index, (targets[0].index,)) if targets else
        ActionSelection(action.discovery_index, (), extra_target_positions=((9, 7),)))
    with fixed_dice_faces(*([2] * 400)):
        return submit(runtime, seat, dragon, discovered, selection, number)


@pytest.mark.parametrize('color,element', [
    ("black", DamageType.ACID), ("white", DamageType.COLD),
    ("red", DamageType.FIRE), ("blue", DamageType.LIGHTNING),
    ("green", DamageType.POISON),
])
def test_dragon_worker_publishes_one_color_matching_elements_and_free_breath_readiness(world, color, element):
    runtime, seat, _ = world
    caster, dragon, cadence, births = summoned_dragon(world, color)
    resistance, = (condition for condition in caster.active_conditions_by_uuid.values()
        if isinstance(condition, DragonSharedResistance))
    assert len(births) == 2
    for record in births:
        cadence_states = state_changes((record,), cadence.uuid)
        assert cadence_states and all(state.breath_type is element and state.ready is False
            for state in cadence_states)
        resistance_states = state_changes((record,), resistance.uuid)
        assert resistance_states and all(state.damage_type is element for state in resistance_states)
        assert any(body.actor_uuid == dragon.uuid and body.birth is not None
            and body.birth.name == f"{color.title()} Draconic Spirit"
            for group in record.lineages for body in group.bodies)
    reply, _, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
        command_number=2, actor_uuid=caster.uuid,
        state_revision=runtime.publications[seat].state_revision, intent=EndTurnIntent())))
    assert reply.rejection is None and needs_advance(runtime.session)
    dragon_input(runtime, seat, dragon)
    for expected, behavior, number in ((True, 'action.monster.multiattack', 3),
            (False, 'action.draconic_spirit.breath', 4)):
        cursor = EventQueue.event_cursor()
        records = dragon_action(runtime, seat, dragon, behavior, number)
        assert (cadence.free_action_uuid is not None) is expected
        assert len(records) == 2
        for record in records:
            states = state_changes((record,), cadence.uuid)
            assert states and all(state.ready is expected for state in states)
        events = [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ConditionStateChangedEvent)
            and event.condition_state.condition_uuid == cadence.uuid]
        assert len(events) == 1 and events[0].condition_state.ready is expected
        assert events[0].parent_event is not None
        parent = EventQueue.get_event_by_uuid(events[0].parent_event)
        assert parent is not None and parent.source_entity_uuid == dragon.uuid


@pytest.mark.parametrize('ending', ['turn_end', 'cancel', 'remove'])
def test_dragon_unused_allowance_closes_without_resurrecting_membership(world, ending):
    runtime, seat, _ = world
    caster, dragon, cadence, _ = summoned_dragon(world)
    if ending == 'cancel':
        def interrupt(boundary, _):
            if boundary.behavior_id == 'action.monster.multiattack' and cadence.free_action_uuid is not None:
                return boundary.cancel(status_message='Interrupt the paid multiattack after its allowance grant')
            return None
        dragon.add_event_handler(EventHandler(source_entity_uuid=dragon.uuid,
            name='Paid multiattack interruption', trigger_conditions=[Trigger(
                event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=dragon.uuid)], event_processor=interrupt))
    reply, _, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
        command_number=2, actor_uuid=caster.uuid,
        state_revision=runtime.publications[seat].state_revision, intent=EndTurnIntent())))
    assert reply.rejection is None
    dragon_input(runtime, seat, dragon)
    records = dragon_action(runtime, seat, dragon, 'action.monster.multiattack', 3)
    if ending == 'cancel':
        assert cadence.free_action_uuid is None and not cadence.issued
        for record in records:
            assert [state.ready for state in state_changes((record,), cadence.uuid)] == [True, False]
        return
    assert cadence.free_action_uuid is not None
    cursor = EventQueue.event_cursor()
    if ending == 'turn_end':
        reply, delivered, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
            command_number=4, actor_uuid=dragon.uuid,
            state_revision=runtime.publications[seat].state_revision, intent=EndTurnIntent())))
        assert reply.rejection is None
        records = tuple(PlayerOperation.model_validate_json(record.model_dump_json()) for record in delivered)
    else:
        assert dragon.remove_condition_by_uuid(cadence.uuid)
        updates = capture_application_operation(runtime.audiences,
            operation_since(runtime.session, cursor), runtime.catalog)
        records = tuple(PlayerUpdate.model_validate_json(update.model_dump_json()) for update in updates.values())
    assert cadence.free_action_uuid is None and len(records) == 2
    events = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ConditionStateChangedEvent)
        and event.condition_state.condition_uuid == cadence.uuid]
    if ending == 'turn_end':
        assert len(events) == 1 and events[0].condition_state.ready is False
        assert not cadence.issued and cadence.granted_lineage is None
        for record in records:
            assert [state.ready for state in state_changes((record,), cadence.uuid)] == [False]
    else:
        assert not events and cadence.uuid not in dragon.active_conditions_by_uuid
        for record in records:
            assert not state_changes((record,), cadence.uuid)
            assert any(isinstance(node.fact, ActorChangeFact)
                and any(isinstance(row, ConditionRow) and row.condition_uuid == cadence.uuid
                    and row.member is None for actor in node.fact.actors for row in actor.rows)
                for group in record.lineages for node in group.events)


def test_real_paladin_aura_kinds_survive_both_initial_public_perspectives():
    session = create_session(player_builds=(prepared_build(CharacterClass.PALADIN, 10),))
    try:
        owner = session.game.entities[session.player_uuids[0]]
        witness = next(actor for actor in session.game.entities.values() if owner.is_enemy(actor))
        session.seats['witness'] = PlayerAudience((), (witness.uuid,))
        _, initials = initialize_audiences(session, ui_content_manifest())
        expected = {condition.uuid: condition.aura_kind
            for condition in owner.active_conditions_by_uuid.values()
            if isinstance(condition, PaladinAuraBenefit)}
        assert set(expected.values()) == {'protection', 'devotion', 'courage'}
        codec = TypeAdapter(PlayerInitialization)
        assert len(initials) == 2
        for initial in initials.values():
            public = codec.validate_json(codec.dump_json(initial))
            client = reduce_initialization(public)
            observed = {member.condition_uuid: member.state.aura_kind
                for member in client.actors[owner.uuid].conditions
                if member.condition_uuid in expected and member.state is not None}
            assert observed == expected
    finally:
        close_session(session)


@pytest.mark.parametrize('form,selector,element,action_id', [
    ('air_elemental', 'Shocked', None, None), ('earth_elemental', 'Prone', None, None),
    ('fire_elemental', 'Burning', None, None), ('water_elemental', 'Chilled', None, None),
    ('air_myrmidon', None, DamageType.LIGHTNING, 'action.air_myrmidon.electrified_flail'),
    ('fire_myrmidon', None, DamageType.FIRE, 'action.fire_myrmidon.scorching_strike'),
    ('water_myrmidon', None, DamageType.COLD, 'action.water_myrmidon.hiemal_strike'),
])
def test_native_elemental_birth_selector_values_reach_both_serialized_streams(world,
        form, selector, element, action_id):
    # The existing strict worker xfail for slot-six Myrmidon discovery remains.
    # This independently proves the actual native summon producer/public capture.
    runtime, _, publication = world
    caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    rank = 6 if selector is None else 5
    caster.action_economy.set_normal_spell_slot_capacity(uuid4(), {rank: 1})
    caster.action_economy.reset_spell_slot_costs()
    cursor = EventQueue.event_cursor()
    result = ConjureElemental(source_entity_uuid=caster.uuid, form_id=form,
        cast_at_level=rank, end_position=(7, 7)).apply()
    assert result is not None and not result.canceled
    updates = capture_application_operation(runtime.audiences,
        operation_since(runtime.session, cursor), runtime.catalog)
    records = tuple(PlayerUpdate.model_validate_json(update.model_dump_json()) for update in updates.values())
    summoned = next(actor for actor in runtime.session.game.entities.values()
        if actor.uuid != caster.uuid and actor.faction == caster.faction)
    kind = ElementalMultiattackBonus if selector is not None else MyrmidonStrikeDice
    condition, = (condition for condition in summoned.active_conditions_by_uuid.values()
        if isinstance(condition, kind))
    assert len(records) == 2
    for record in records:
        states = state_changes((record,), condition.uuid)
        assert states
        if selector is not None:
            assert all(state.prerequisite == selector for state in states)
        else:
            assert all(state.damage_type is element and state.action_id == action_id for state in states)
