"""Saved player input owns interaction timing and keeps remote/private state private."""

from typing import Literal
from uuid import UUID

import pytest

from dnd.core.events import EventQueue
from dnd.entity import Entity
from game.animation_data import load_animation_data
from game.animation_types import AnimationData
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import ActionFact, PlayerLineage, PlayerState
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import CapturedHistory
from tests.game.environment_control_scenarios import control_history


@pytest.fixture(scope="module")
def histories() -> dict[str, CapturedHistory]:
    return {
        "light": control_history(),
        "hidden": control_history(hidden_light=True),
        "door": control_history(program="door"),
        "chest": control_history(program="chest"),
    }


@pytest.fixture(scope="module")
def animation_data() -> AnimationData:
    return load_animation_data()


def saved_view(history: CapturedHistory, role: str) -> tuple[bytes, PlayerState, tuple[PlayerLineage, ...]]:
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    payload = encode_player_sequence(project_sequence(history.views[role]))
    state, roots = decode_player_sequence(payload)
    return payload, state, roots


def object_at(state: PlayerState, position: tuple[int, int]) -> UUID:
    return next(identity for identity, obj in state.objects.items() if obj.placement.position == position)


def first_action(state: PlayerState, roots: tuple[PlayerLineage, ...], behavior: str) -> tuple[PlayerState, PlayerLineage]:
    for root in roots:
        fact = root.root.fact
        if isinstance(fact, ActionFact) and fact.behavior_id == behavior and not root.root.canceled:
            return state, root
        state = reduce_lineage(state, root)
    pytest.fail(f"No disclosed {behavior} action")


def interaction_values(state: PlayerState, program: str, touched: UUID, affected: UUID) -> tuple[bool | None, ...]:
    if program == "light":
        return state.objects[touched].item.is_engaged, state.objects[affected].item.is_lit
    if program == "door":
        return state.objects[touched].item.is_engaged, state.objects[affected].item.is_open
    return (state.objects[touched].item.is_open,)


@pytest.mark.parametrize("role", ("operator", "witness"))
@pytest.mark.parametrize("program", ("light", "door", "chest"))
def test_saved_interaction_changes_objects_at_one_physical_reach(
    histories: dict[str, CapturedHistory], animation_data: AnimationData,
    role: str, program: Literal["light", "door", "chest"],
) -> None:
    _, state, roots = saved_view(histories[program], role)
    behavior = ("action.environment.storage_chest.open" if program == "chest"
                else "action.environment.control_lever.toggle")
    before, root = first_action(state, roots, behavior)
    fact = root.root.fact
    assert isinstance(fact, ActionFact) and fact.source_item_uuid is not None
    touched = fact.source_item_uuid
    affected = object_at(before, {"light": (6, 5), "door": (8, 4), "chest": (3, 2)}[program])
    previous = interaction_values(before, program, touched, affected)
    latest = reduce_lineage(before, root)
    expected = interaction_values(latest, program, touched, affected)
    assert expected != previous

    bound = bind_choreography(before, root, animation_data)
    assert not bound.gaps
    cue, = bound.body_actions  # Remote target changes share the one physical reach.
    assert cue.interaction_object_uuid == touched
    assert UUID(cue.contact.actor_uuid) == fact.source_entity_uuid
    assert cue.effect_ms > 0
    pending = sample_choreography(bound, cue.effect_ms - 1)
    reached = sample_choreography(bound, cue.effect_ms)
    assert interaction_values(pending.displayed, program, touched, affected) == previous
    assert interaction_values(reached.displayed, program, touched, affected) == expected
    assert not reached.complete
    assert sample_choreography(bound, cue.effect_ms - 1) == pending
    assert sample_choreography(bound, cue.effect_ms) == reached
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_hidden_linked_light_identity_stays_private_in_saved_operator_view(
    histories: dict[str, CapturedHistory], animation_data: AnimationData,
) -> None:
    history = histories["hidden"]
    _, witnessed, witness_roots = saved_view(history, "witness")
    hidden_target = object_at(witnessed, (10, 5))
    payload, state, roots = saved_view(history, "operator")
    assert str(hidden_target).encode() not in payload
    touched = object_at(state, (3, 7))
    assert hidden_target not in state.objects
    handles = [state.objects[touched].item.is_engaged]
    for root in roots:
        fact = root.root.fact
        if isinstance(fact, ActionFact) and fact.source_item_uuid == touched:
            bound = bind_choreography(state, root, animation_data)
            cue, = bound.body_actions
            assert cue.interaction_object_uuid == touched
        state = reduce_lineage(state, root)
        assert hidden_target not in state.objects
        engaged = state.objects[touched].item.is_engaged
        if engaged != handles[-1]:
            handles.append(engaged)
    assert handles == [True, False, True, False, True]
    light_values = [witnessed.objects[hidden_target].item.is_lit]
    for root in witness_roots:
        witnessed = reduce_lineage(witnessed, root)
        lit = witnessed.objects[hidden_target].item.is_lit
        if lit != light_values[-1]:
            light_values.append(lit)
    assert light_values == [True, False, True, False, True]
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_loot_arrives_at_contact_only_in_the_owners_saved_inventory(
    histories: dict[str, CapturedHistory], animation_data: AnimationData,
) -> None:
    history = histories["chest"]
    _, initial, roots = saved_view(history, "operator")
    before, root = first_action(initial, roots, "action.environment.storage_chest.loot_all")
    owner = before.observer_uuid
    original_items = before.actors[owner].controlled_items
    assert original_items is not None
    original = {item.item_uuid for item in original_items}
    latest = reduce_lineage(before, root)
    latest_items = latest.actors[owner].controlled_items
    assert latest_items is not None
    acquired = {item.item_uuid for item in latest_items} - original
    assert acquired
    bound = bind_choreography(before, root, animation_data)
    cue, = bound.body_actions
    pending_items = sample_choreography(bound, cue.effect_ms - 1).displayed.actors[owner].controlled_items
    reached_items = sample_choreography(bound, cue.effect_ms).displayed.actors[owner].controlled_items
    assert pending_items == original_items
    assert reached_items == latest_items

    witness_payload, witness_state, witness_roots = saved_view(history, "witness")
    assert all(str(identity).encode() not in witness_payload for identity in acquired)
    for witness_root in witness_roots:
        witness_state = reduce_lineage(witness_state, witness_root)
        assert witness_state.actors[owner].controlled_items is None
    chest = object_at(witness_state, (3, 2))
    assert witness_state.objects[chest].item.is_open is True
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
