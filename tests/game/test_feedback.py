"""Source FloatingText fades survive short joins without delaying gameplay."""

from dataclasses import replace
from pathlib import Path
import random
from uuid import uuid4

import pytest

from dnd.core.condition_types import ConditionCategory
from dnd.core.events import Event, EventPhase, EventType
from dnd.runtime_reset import reset_engine_runtime
from game.animation import ActorContact
from game.animation_data import load_animation_data
from game.animation_types import AnimationData
from game.choreography import BoundChoreography, bind_choreography
from game.combat_demo import iter_combat_demo
from game.condition_animation import compile_condition
from game.feedback import choreography_feedback, motion_feedback, sample_feedback
from game.motion import bind_motion, sample_motion
from game.presentation import CompletedLineage, ConditionFact, PresentationTarget
from tests.game.scenarios import attack_history, movement_with_paralysis


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))


def test_dodge_badge_survives_immediate_join_and_seeks_on_the_presentation_clock(data: AnimationData) -> None:
    target = uuid4()
    fact = ConditionFact(uuid4(), uuid4(), "Dodging", ConditionCategory.STATUS,
                         "condition.dodging", None, None)
    event = Event(uuid=fact.event_uuid, source_entity_uuid=target, target_entity_uuid=target,
        event_type=EventType.CONDITION_APPLICATION, phase=EventPhase.COMPLETION, use_register=False)
    condition = compile_condition(data.condition_recipes, event, fact, (), start_ms=0,
                                  badge_style=data.badge_style)
    state = PresentationTarget(uuid4(), target)
    group = BoundChoreography(event.uuid, state, state, (), (condition,), condition.complete_ms, ())
    launch = ActorContact(str(target), (3.25, 4.5), "E", .5, elevation_steps=1.25)
    contacts = {str(target): launch}
    tracks = choreography_feedback(group, data, 250, contacts=contacts)
    assert group.complete_ms == 0 and len(tracks) == 1
    track = tracks[0]
    assert track.start_ms == 250 and track.duration_ms == data.badge_style.durationMs
    initial = sample_feedback(track, 250)
    assert initial is not None and (initial.label, initial.value, initial.kind) == ("+Dodging", None, "badge")
    assert sample_feedback(track, 249) is None
    middle = sample_feedback(track, 250 + track.duration_ms * .75)
    assert middle is not None and middle.progress == .75
    expected_alpha = (1 - .75) / (1 - data.badge_style.fadeStartFraction)
    assert middle.alpha == pytest.approx(expected_alpha)
    # A paused clock and backward seek do not replay or consume the decoration.
    assert sample_feedback(track, 250 + track.duration_ms) is None
    assert sample_feedback(track, 250 + track.duration_ms * .75) == middle
    assert sample_feedback(track, 250) == initial
    # FloatingText captures its anchor once, even if a later action moves actor.
    contacts[str(target)] = replace(launch, grid=(9, 9), elevation_steps=3)
    assert track.contact == launch and track.contact.grid == (3.25, 4.5)
    assert group.complete_ms == 0


@pytest.mark.parametrize("seed", [17, 1])
def test_real_attack_uses_number_recipe_duration_or_independent_miss_badge(data: AnimationData, seed: int) -> None:
    random_state = random.getstate()
    try:
        before, lineage = attack_history("weapon.longsword", seed)
        group = bind_choreography(before, lineage, data)
        complete = group.complete_ms
        tracks = choreography_feedback(group, data, 100)
        assert len(tracks) == 1
        track = tracks[0]
        if seed == 17:
            assert track.kind == "number" and track.value is not None and track.value > 0
            assert track.duration_ms == data.damage_context.numberDurationMs
            assert track.duration_ms != track.style.durationMs
        else:
            assert (track.kind, track.label, track.value) == ("badge", "Miss", None)
            assert sample_feedback(track, 100 + complete + 1) is not None
        assert sample_feedback(track, track.start_ms) is not None
        assert sample_feedback(track, track.start_ms + track.duration_ms) is None
        assert group.complete_ms == complete
    finally:
        reset_engine_runtime()
        random.setstate(random_state)


def test_repeated_cast_feedback_keeps_original_application_identity_and_anchors(data: AnimationData) -> None:
    script = iter_combat_demo(magic_missile=True)
    try:
        before, lineage = next(script), next(script)
        assert isinstance(before, PresentationTarget) and isinstance(lineage, CompletedLineage)
        group = bind_choreography(before, lineage, data)
        tracks = choreography_feedback(group, data, 400)
        assert len(tracks) == 3
        assert [track.value for track in tracks] == [5, 5, 2]
        assert len({track.application_id for track in tracks}) == 3
        assert tracks[0].contact == tracks[2].contact and tracks[0].contact != tracks[1].contact
        assert tracks[0].start_ms < tracks[1].start_ms < tracks[2].start_ms
        for track in tracks:
            sample = sample_feedback(track, track.start_ms)
            assert sample is not None and sample.application_id == track.application_id
            assert (sample.value, sample.label, sample.progress) == (track.value, "Force", 0)
            assert track.duration_ms == data.damage_context.numberDurationMs
    finally:
        script.close()


def test_reaction_badge_uses_authored_context_without_changing_movement(data: AnimationData) -> None:
    before, lineage = movement_with_paralysis(17)
    motion = bind_motion(before, lineage, data)
    assert motion is not None
    tracks = motion_feedback(motion, data, 400)
    badge, = (track for track in tracks if track.kind == "badge")
    reactor = next(actor for actor in before.actors.values() if actor.name == "Sword wielder")
    assert badge.contact.actor_uuid == str(reactor.uuid)
    assert badge.label.startswith(data.movement_reaction_context.label)
    assert "Opportunity" in badge.label
    assert sample_feedback(badge, badge.start_ms - 1) is None
    assert sample_feedback(badge, badge.start_ms) is not None
    assert badge.duration_ms == data.badge_style.durationMs

    hidden = replace(data, movement_reaction_context=data.movement_reaction_context.model_copy(
        update={"feedbackEnabled": False},
    ))
    quiet_motion = bind_motion(before, lineage, hidden)
    assert quiet_motion is not None
    assert motion_feedback(quiet_motion, hidden, 400) == tuple(track for track in tracks if track is not badge)
    assert quiet_motion.complete_ms == motion.complete_ms
    assert sample_motion(quiet_motion, hidden, quiet_motion.complete_ms) == sample_motion(motion, data, motion.complete_ms)
