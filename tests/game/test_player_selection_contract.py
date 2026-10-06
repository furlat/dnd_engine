"""Native discovery and selection behavior used by the player interface."""

import random

import pytest

from dnd.entity import Entity
from dnd.content.items.window_builders import place_window
from dnd.types.world import CardinalDirection
from dnd.spells.conjuration import AcidSplash, DimensionDoor
from dnd.actions_functional import get_available_actions, register_spell, preview_available_selection
from dnd.core.events import EventQueue
from uuid import uuid4
from dnd.spells.abjuration import BeaconOfHope
from dnd.spells.evocation import MagicMissile, DivineWord, FireShield, FireShieldEffect
from dnd.content.items.environment_item_builders import build_spell_device
from dnd.actions import SpellEvent
from dnd.core.dice import fixed_dice_faces
from dnd.spells.transmutation import EnhanceAbility, EnlargeReduce
from game.session import (advance_controller, close_session, create_session,
                          discover_player_actions, execute_player_action, end_player_turn,
                          preview_player_selection)


@pytest.fixture
def human_session():
    random_state = random.getstate()
    random.seed(0)
    session = create_session()
    try:
        for _ in range(40):
            operation = advance_controller(session)
            if operation.boundary.status == "waiting_for_human":
                actor = session.encounter.get_current_entity()
                if actor.name == "Draconic Sorcerer":
                    break
                end_player_turn(session, actor.uuid)
        yield session
    finally:
        close_session(session)
        random.setstate(random_state)


def test_view_has_no_executors_and_stale_selection_cannot_spend(human_session):
    session = human_session
    actor = session.encounter.get_current_entity()
    choices = discover_player_actions(session, actor.uuid)
    row = next(row for row in choices.self_actions if row.behavior_id == "action.dodge")
    assert row.execution_template is None
    assert choices.registered_action_variants == ()
    assert choices.inventory_use_action_sources == ()
    discover_player_actions(session, actor.uuid)
    before = EventQueue.event_cursor(), actor.action_economy.actions.normalized_score
    with pytest.raises(ValueError, match="stale"):
        execute_player_action(session, actor.uuid, row, row.valid_targets[0])
    assert before == (EventQueue.event_cursor(), actor.action_economy.actions.normalized_score)


def test_partial_and_repeated_projectile_previews_are_pure(human_session):
    session = human_session
    sorcerer = next(actor for actor in session.game.entities.values()
                    if actor.name == "Draconic Sorcerer")
    # Query the real native row independent of the current human's class.
    register_spell(sorcerer, MagicMissile)
    choices = get_available_actions(sorcerer)
    row = next(row for row in choices.entity_actions
               if row.behavior_id == "spell.magic_missile" and row.cast_at_level == 1)
    first, second = row.valid_targets[:2]
    rng = random.getstate()
    cursor = EventQueue.event_cursor()
    original = row.execution_template.model_dump()
    pools = sorcerer.action_economy.get_normal_spell_slot_capacities()
    for _ in range(3):
        partial = preview_available_selection(sorcerer, row, (first, second))
        assert partial.can_confirm
        assert partial.effective_target_uuids == (first.target_uuid, second.target_uuid, first.target_uuid)
        repeated = preview_available_selection(sorcerer, row, (first, second, first))
        assert repeated.can_confirm and repeated.next_targets == ()
        assert repeated.effective_target_uuids == partial.effective_target_uuids
    assert random.getstate() == rng and EventQueue.event_cursor() == cursor
    assert row.execution_template.model_dump() == original
    assert sorcerer.action_economy.get_normal_spell_slot_capacities() == pools


def test_mode_facets_and_depleted_known_ranks_remain_discoverable(human_session):
    actor = next(actor for actor in human_session.game.entities.values() if actor.name == "Draconic Sorcerer")
    register_spell(actor, EnhanceAbility)
    register_spell(actor, EnlargeReduce)
    actor.action_economy.consume("spell_slot_2", 3)
    choices = get_available_actions(actor)
    depleted = [row for row in choices.all_actions if row.cast_at_level == 2]
    assert depleted and all(not row.can_afford and not row.valid_targets for row in depleted)
    modes = {facet.value for row in choices.all_actions if row.behavior_id == "spell.enhance_ability"
             for facet in row.variant_facets if facet.key == "ability"}
    assert modes == {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
    forms = {facet.value for row in choices.all_actions if row.behavior_id == "spell.enlarge_reduce"
             for facet in row.variant_facets if facet.key == "form"}
    assert forms == {"enlarge", "reduce"}


def test_up_to_recipient_cap_uses_the_native_count_hook():
    # Count is part of authored rule metadata and independent of resources.
    action = BeaconOfHope(source_entity_uuid=uuid4(), template=True)
    assert action.get_multi_target_count() == 6


def test_preview_and_command_resolve_authoritative_target_handles(human_session):
    actor = human_session.encounter.get_current_entity()
    choices = discover_player_actions(human_session, actor.uuid)
    move = next(row for row in choices.position_actions if row.behavior_id == "action.move"
                and not row.variant_facets[0].value == "flying")
    target = next(target for target in move.valid_targets if target.position != actor.position)
    admitted = target.position
    preview = preview_player_selection(human_session, actor.uuid, move)
    assert preview.next_targets
    preview.next_targets[0].position = (99, 99)
    assert preview_player_selection(human_session, actor.uuid, move).next_targets[0].position != (99, 99)
    target.position = (99, 99)
    target.path = [(99, 99)]
    execute_player_action(human_session, actor.uuid, move, target)
    assert actor.position == admitted


def test_invalid_complete_prefix_does_not_spend_or_publish(human_session):
    actor = human_session.encounter.get_current_entity()
    register_spell(actor, MagicMissile)
    choices = discover_player_actions(human_session, actor.uuid)
    row = next(row for row in choices.entity_actions if row.behavior_id == "spell.magic_missile"
               and row.cast_at_level == 1)
    target = row.valid_targets[0]
    before = (EventQueue.event_cursor(), actor.action_economy.actions.normalized_score,
              actor.action_economy.spell_slot_value(1).normalized_score, random.getstate())
    preview = preview_player_selection(human_session, actor.uuid, row, (target,) * 4)
    assert not preview.can_confirm and preview.reason
    assert before == (EventQueue.event_cursor(), actor.action_economy.actions.normalized_score,
                      actor.action_economy.spell_slot_value(1).normalized_score, random.getstate())


def test_observed_window_approach_then_fresh_native_traversal(human_session):
    actor = human_session.encounter.get_current_entity()
    endpoint = (actor.position[0] + 2, actor.position[1])
    window = place_window("environment.window.fantasy_g8", endpoint, CardinalDirection.EAST,
                          insert_destroyed=True)
    Entity.update_all_entities_senses()
    choices = discover_player_actions(human_session, actor.uuid)
    passage = next(row for row in choices.world_interactions
        if row.subject_uuid == window.wall.uuid and row.behavior_id == "action.traverse_connector")
    assert endpoint in passage.contact_positions
    assert not any(row.connector_traversal is not None for row in choices.self_actions)
    move = next(row for row in choices.position_actions if row.behavior_id == "action.move"
                and any(target.position == endpoint for target in row.valid_targets))
    target = next(target for target in move.valid_targets if target.position == endpoint)
    execute_player_action(human_session, actor.uuid, move, target)
    choices = discover_player_actions(human_session, actor.uuid)
    traverse = next(row for row in choices.self_actions if row.connector_traversal is not None
                    and row.connector_traversal.command.connector_uuid == passage.connector_uuid)
    before = actor.action_economy.movement_remaining()
    operation = execute_player_action(human_session, actor.uuid, traverse, traverse.valid_targets[0])
    assert actor.position == traverse.connector_traversal.command.destination_position
    assert actor.action_economy.movement_remaining() == before - traverse.connector_traversal.movement_cost_feet
    assert operation.roots


def test_entity_destination_and_pair_preview_reject_invalid_prefix_without_events(human_session):
    actor = human_session.encounter.get_current_entity()
    register_spell(actor, DimensionDoor)
    register_spell(actor, AcidSplash)
    native = get_available_actions(actor)
    acid = next(row for row in native.entity_actions if row.behavior_id == "spell.acid_splash")
    first, second = acid.valid_targets[:2]
    before = EventQueue.event_cursor(), random.getstate(), actor.action_economy.actions.normalized_score
    preview = preview_available_selection(actor, acid, (first, second))
    assert not preview.can_confirm and preview.reason
    # A higher-rank direct grant makes Dimension Door discoverable without changing execution rules.
    actor.action_economy.set_normal_spell_slot_capacity(uuid4(), {1: 4, 2: 3, 3: 2, 4: 1})
    native = get_available_actions(actor)
    door = next(row for row in native.entity_actions if row.behavior_id == "spell.dimension_door"
                and row.valid_targets)
    invalid = preview_available_selection(actor, door, (door.valid_targets[0],), ((999, 999),))
    assert not invalid.can_confirm
    assert before == (EventQueue.event_cursor(), random.getstate(), actor.action_economy.actions.normalized_score)


@pytest.mark.parametrize("spell, identity, rank, channel", [
    (BeaconOfHope, "spell.beacon_of_hope", 3, "actions"),
    (DivineWord, "spell.divine_word", 7, "bonus_actions"),
])
def test_native_two_recipient_execution_spends_one_cast(human_session, spell, identity, rank, channel):
    actor = human_session.encounter.get_current_entity()
    if rank == 7:
        actor.action_economy.set_normal_spell_slot_capacity(uuid4(), {1: 4, 2: 3, 3: 2, 7: 1})
    register_spell(actor, spell)
    choices = discover_player_actions(human_session, actor.uuid)
    row = next(row for row in choices.entity_actions if row.behavior_id == identity
               and row.cast_at_level == rank)
    first, second = row.valid_targets[:2]
    before = actor.action_economy._get_value_for_cost_type(channel).normalized_score
    slots = actor.action_economy.spell_slot_value(rank).normalized_score
    with fixed_dice_faces(*([1] * 32)):
        operation = execute_player_action(human_session, actor.uuid, row, first,
            extra_target_uuids=(second.target_uuid,))
    cast = next(root for root in operation.roots if isinstance(root, SpellEvent))
    assert not cast.canceled
    recipients = {event.target_entity_uuid for index, event in EventQueue.iter_events_since(operation.start_cursor)
                  if isinstance(event, SpellEvent)}
    assert {first.target_uuid, second.target_uuid} <= recipients
    assert actor.action_economy._get_value_for_cost_type(channel).normalized_score == before - 1
    assert actor.action_economy.spell_slot_value(rank).normalized_score == slots - 1


def test_source_item_executes_exact_retained_variant(human_session):
    actor = human_session.encounter.get_current_entity()
    item = build_spell_device(item_id="environment.fireball_cannon", name="Shield device",
        spell_templates=[FireShield(source_entity_uuid=actor.uuid, template=True, cast_origin="source_item", shield_kind="chill")],
        charges=2)
    item.place_on_grid((actor.position[0] + 1, actor.position[1]))
    Entity.update_all_entities_senses()
    choices = discover_player_actions(human_session, actor.uuid)
    row = next(row for row in choices.self_actions if row.source_item_uuid == item.uuid
               and any(facet.value == "chill" for facet in row.variant_facets))
    operation = execute_player_action(human_session, actor.uuid, row, row.valid_targets[0])
    assert operation.roots and not operation.roots[0].canceled
    assert any(isinstance(condition, FireShieldEffect) and condition.shield_kind == "chill"
               for condition in actor.active_conditions_by_uuid.values())
    assert item.charges == 1


def test_previous_session_handle_cannot_resolve_after_restart():
    first = create_session()
    try:
        for _ in range(32):
            if advance_controller(first).boundary.status == "waiting_for_human":
                break
        actor = first.encounter.get_current_entity()
        choices = discover_player_actions(first, actor.uuid)
        old = next(row for row in choices.self_actions if row.behavior_id == "action.dodge")
    finally:
        close_session(first)
    second = create_session()
    try:
        for _ in range(32):
            if advance_controller(second).boundary.status == "waiting_for_human":
                break
        actor = second.encounter.get_current_entity()
        discover_player_actions(second, actor.uuid)
        before = EventQueue.event_cursor(), actor.action_economy.actions.normalized_score
        with pytest.raises(ValueError, match="stale"):
            preview_player_selection(second, actor.uuid, old)
        with pytest.raises(ValueError, match="stale"):
            execute_player_action(second, actor.uuid, old, old.valid_targets[0])
        assert before == (EventQueue.event_cursor(), actor.action_economy.actions.normalized_score)
    finally:
        close_session(second)
