"""Recorded area actions carry saves, complete pushes and persistent cleanup."""

import pytest

from dnd.actions import SpellEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY, BaseObject
from dnd.core.events import EventQueue, ForcedMovementEvent, SavingThrowEvent
from dnd.entity import Entity
from game.player_facts import SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.area_spell_scenarios import area_spell_history


CASES = (
    ("burning_hands", False, False), ("burning_hands", True, False),
    ("thunderwave", False, False), ("thunderwave", True, False), ("thunderwave", False, True),
    ("gust_of_wind", False, False), ("gust_of_wind", True, False), ("gust_of_wind", False, True),
)


@pytest.fixture(scope="module", params=CASES, ids=lambda row: f"{row[0]}-{'diagonal' if row[1] else 'axial'}{'-blocked' if row[2] else ''}")
def captured(request):
    program, diagonal, blocked = request.param
    return request.param, area_spell_history(program=program, diagonal=diagonal, blocked=blocked)


def test_selected_area_actions_have_real_saves_and_admitted_displacements(captured):
    (program, diagonal, blocked), history = captured
    cast, = (root for root in history.views["caster"].lineages if isinstance(root.root, SpellEvent))
    assert cast.root.behavior_id == "spell." + program
    assert cast.root.area_geometry is not None and cast.root.resolved_area_positions
    saves = {event.target_entity_name: event.result for event in cast.events if isinstance(event, SavingThrowEvent)}
    assert saves == {"Target": False, "Saved": True}
    moves = [event for event in cast.events if isinstance(event, ForcedMovementEvent)]
    if program == "burning_hands":
        assert not moves
    else:
        move, = moves
        dx = abs(move.end_position[0] - move.start_position[0])
        dy = abs(move.end_position[1] - move.start_position[1])
        expected_steps = 1 if blocked else 2 if program == "thunderwave" else 3
        assert max(dx, dy) == expected_steps
        assert move.actual_distance == expected_steps * 5
        assert move.blocked_by_obstacle is blocked
        assert move.target_entity_name == "Target"
        assert (dx > 0 and dy > 0) is diagonal


@pytest.mark.parametrize("role", ("caster", "target"))
def test_saved_subjective_area_events_replay_without_live_engine(captured, role):
    (program, _, _), history = captured
    detached = RecordedSequence.model_validate_json(history.views[role].model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(detached)))
    initial = {actor.name: (actor.uuid, actor.normal_hp, actor.last_visual_position) for actor in state.actors.values()}
    cast_seen = False
    for root in roots:
        lineages = {node.lineage_uuid for node in root.events}
        assert all(child in lineages for node in root.events for child in node.children_lineages)
        state = reduce_lineage(state, root)
        if isinstance(root.root.fact, SpellFact):
            cast_seen = True
            assert root.root.fact.behavior_id == "spell." + program
            assert root.root.fact.area_geometry is not None
            if program == "gust_of_wind":
                assert state.senses is not None
                assert any(effect.content_ref.content_id == "spatial_effect.spell.gust_of_wind"
                           for effect in state.senses.spatial_effects.values())
    assert cast_seen
    final = {actor.name: actor for actor in state.actors.values()}
    assert final["Outside"].normal_hp == initial["Outside"][1]
    assert final["Saved"].last_visual_position == initial["Saved"][2]
    if program == "gust_of_wind":
        assert all(actor.normal_hp == initial[actor.name][1] for actor in final.values())
        assert state.senses is not None and not state.senses.spatial_effects
        assert final["Caster"].last_visual_position == initial["Caster"][2]
    else:
        failed_damage = initial["Target"][1] - final["Target"].normal_hp
        saved_damage = initial["Saved"][1] - final["Saved"].normal_hp
        assert failed_damage > 0 and failed_damage == saved_damage * 2
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities() and not BaseObject._registry
