"""A real Shield interruption owns its gesture and each directional contact."""

import pytest

from dnd.core.events import EventQueue, EventType
from dnd.entity import Entity
from game.animation import facing_for_delta
from game.animation_data import load_animation_data
from game.attack import BoundAttack
from game.choreography import bind_choreography, sample_choreography
from game.combat import BoundCast, actor_contact
from game.motion_media import choreography_motion_media
from game.player_facts import AttackFact, ConditionChangeFact, DamageFact, SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from tests.game.persistent_spell_scenarios import persistent_spell_history


@pytest.fixture(scope="module")
def animations():
    return load_animation_data()


@pytest.mark.parametrize("delivery", ("melee", "ranged", "missile"))
def test_saved_shield_gesture_precedes_actual_intercept_and_maintained_contacts_only(animations, delivery):
    data = animations
    history = persistent_spell_history(program="shield", shield_delivery=delivery)
    payloads = tuple(encode_player_sequence(project_sequence(view)) for view in history.views.values())
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    for payload in payloads:
        before, roots = decode_player_sequence(payload)
        gesture_count, interceptions, untreated_attacks = 0, 0, 0
        for root in roots:
            group = bind_choreography(before, root, data)
            tagged = [(node, node.fact) for node in root.events if isinstance(node.fact, (AttackFact, DamageFact))
                      and node.fact.intercepted_by_condition_uuid is not None]
            if tagged:
                assert not group.gaps
                owner = tagged[0][1].intercepted_by_condition_uuid
                assert len(group.contact_media) == len(tagged) * 2
                interception_times = []
                assert isinstance(root.root.fact, (AttackFact, SpellFact))
                for cue in group.contact_media:
                    assert cue.event_uuid in {node.uuid for node, _ in tagged}
                    assert cue.track.viewFacing == "E"
                    source = before.actors[root.root.fact.source_entity_uuid]
                    target = before.actors[tagged[0][1].target_entity_uuid]
                    source_contact, target_contact = actor_contact(before, source, data), actor_contact(before, target, data)
                    direction = facing_for_delta((target_contact.grid[0] - source_contact.grid[0],
                                                  target_contact.grid[1] - source_contact.grid[1]), data)
                    assert cue.facing == direction
                    assert f"shield.hit.{direction}." in cue.track.assetId
                    assert cue.position == target_contact.grid
                    interception_times.append(cue.start_ms)
                node = group.nodes[0]
                if isinstance(node.bound, BoundAttack):
                    assert all(at == pytest.approx(node.start_ms + node.bound.timeline.contact_ms)
                               for at in interception_times)
                elif isinstance(node.bound, BoundCast):
                    actual_times = [node.start_ms + row.travel_end_ms for row in node.bound.timeline.applications]
                    assert all(any(at == pytest.approx(actual) for actual in actual_times)
                               for at in interception_times)
                applications = [(node, node.fact) for node in root.events if isinstance(node.fact, ConditionChangeFact)
                                and node.fact.event_type is EventType.CONDITION_APPLICATION
                                and node.fact.condition.condition_uuid == owner]
                if applications:
                    assert len(applications) == len(group.body_actions) == 1
                    gesture = group.body_actions[0]
                    assert gesture.event_uuid == applications[0][0].uuid
                    assert gesture.clip == "Attack5" and gesture.cast_layers
                    assert 0 <= gesture.start_ms < gesture.effect_ms <= min(interception_times)
                    transition = next(row for row in group.conditions if row.event_uuid == gesture.event_uuid)
                    assert transition.start_ms == gesture.effect_ms
                    actor_id = applications[0][1].target_entity_uuid
                    early = sample_choreography(group, gesture.effect_ms - .001).displayed
                    revealed = sample_choreography(group, gesture.effect_ms).displayed
                    assert not any(row.condition_uuid == owner for row in early.actors[actor_id].conditions)
                    assert any(row.condition_uuid == owner for row in revealed.actors[actor_id].conditions)
                    assert sample_choreography(group, gesture.effect_ms).displayed == revealed
                    gesture_count += 1
                else:
                    assert not group.body_actions
                # Impact media are retained separately across heads, not a new
                # pause that changes the native movement/action playback speed.
                retained = choreography_motion_media(group, data, 100)
                assert [cue.media.start_ms for cue in retained] == [100 + cue.start_ms for cue in group.contact_media]
                interceptions += len(tagged)
            elif any(isinstance(node.fact, AttackFact) for node in root.events):
                assert not group.contact_media and not group.body_actions
                untreated_attacks += 1
            before = reduce_lineage(before, root)
        assert gesture_count == 1
        assert interceptions == (6 if delivery == "missile" else 2)
        assert untreated_attacks == (0 if delivery == "missile" else 2)
