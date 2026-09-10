"""Original condition records drive passive appearance, timing and UUID lifetime."""

from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.core.condition_types import ConditionCategory
from dnd.core.events import Event, EventPhase, EventType
from game.animation_types import FloatingFeedbackStyle, StudioCondition
from game.condition_animation import (
    compile_condition, condition_transition_appearances, resolve_condition_appearance, sample_condition,
)
from game.condition_types import load_condition_recipes
from game.presentation import ConditionFact


SOURCE = Path("game/data/neuroclient/source/src/render/data/animation")


@pytest.fixture(scope="module")
def recipes():
    return load_condition_recipes(SOURCE / "conditionPresentation.json")


@pytest.fixture(scope="module")
def badge_style() -> FloatingFeedbackStyle:
    contexts = json.loads((SOURCE / "actionContextPresentation.json").read_text())
    return FloatingFeedbackStyle.model_validate_json(json.dumps(contexts["contexts"]["floating_feedback"]["badge"]))


def condition_fact(identity: str, name: str) -> ConditionFact:
    return ConditionFact(uuid4(), uuid4(), name, ConditionCategory.STATUS, identity, None, None)


def header(fact: ConditionFact, *, applied: bool = True) -> Event:
    actor = uuid4()
    return Event(
        uuid=fact.event_uuid, source_entity_uuid=actor, target_entity_uuid=actor,
        event_type=EventType.CONDITION_APPLICATION if applied else EventType.CONDITION_REMOVAL,
        phase=EventPhase.COMPLETION, use_register=False,
    )


def test_entire_original_condition_document_remains_available_and_immutable(recipes) -> None:
    original = json.loads((SOURCE / "conditionPresentation.json").read_text())
    assert len(recipes) == len(original["recipes"]) == 141
    for source in original["recipes"]:
        retained = recipes[source["definitionRef"]["content_id"]]
        assert retained.model_dump(mode="json", exclude_unset=True) == source
    with pytest.raises(TypeError):
        recipes["condition.invisible"] = recipes["condition.poisoned"]


def test_authored_visibility_alpha_body_color_delay_and_replay(recipes, badge_style) -> None:
    fact = condition_fact("condition.invisible", "Invisible")
    override = StudioCondition(anchor="effect", delayMs=50, feedbackEnabled=True)
    timeline = compile_condition(recipes, header(fact), fact, (), start_ms=100,
                                 badge_style=badge_style, override=override)
    assert (timeline.start_ms, timeline.complete_ms) == (150, 390)
    before = sample_condition(timeline, 149)
    entry = sample_condition(timeline, 150)
    middle = sample_condition(timeline, 270)
    after = sample_condition(timeline, 390)
    assert before.membership == () and before.appearance.alpha == 1
    assert entry.membership == (fact,) and entry.appearance.alpha == 1
    assert middle.appearance.alpha == pytest.approx(0.75)
    assert after.appearance.alpha == 0.5 and after.complete
    assert entry.appearance.body_color == recipes[fact.behavior_id].persistent.bodyColor
    assert entry.appearance.body_color is not None
    assert (entry.appearance.body_color.tintRgb, entry.appearance.body_color.saturation,
            entry.appearance.body_color.brightness) == (12044287, 0.62, 0.96)
    assert entry.feedback is not None and entry.feedback.label == "+Invisible"
    assert entry.feedback.color == recipes[fact.behavior_id].application.feedbackColor
    assert not timeline.unsupported
    assert sample_condition(timeline, 149) == before
    assert sample_condition(timeline, 270) == middle


def test_removal_preserves_other_condition_instances_and_recipe_exclusivity(recipes, badge_style) -> None:
    one = condition_fact("condition.invisible", "Invisible")
    two = condition_fact("condition.invisible", "Invisible")
    poison = condition_fact("condition.poisoned", "Poisoned")
    spell = condition_fact("condition.spell.invisibility", "Invisibility")
    appearance = resolve_condition_appearance((one, two, poison, spell), recipes)
    assert appearance.alpha == 0.5
    assert len(appearance.matched_behavior_ids) == 2  # one exclusive visibility recipe plus poison
    assert appearance.body_color == recipes[one.behavior_id].persistent.bodyColor
    removed = replace(one, event_uuid=uuid4())
    first = compile_condition(recipes, header(removed, applied=False), removed, (one, two, poison),
                              start_ms=0, badge_style=badge_style)
    assert first.after_membership == (two, poison)
    assert first.complete_ms == 0 and sample_condition(first, 0).appearance.alpha == 0.5
    removed_again = replace(two, event_uuid=uuid4())
    last = compile_condition(recipes, header(removed_again, applied=False), removed_again, first.after_membership,
                             start_ms=100, badge_style=badge_style)
    assert last.after_membership == (poison,) and last.complete_ms == 300
    assert sample_condition(last, 200).appearance.alpha == pytest.approx(0.75)
    assert sample_condition(last, 300).appearance.body_color == recipes[poison.behavior_id].persistent.bodyColor


def test_feedback_and_body_filter_changes_do_not_invent_a_blocking_transition(recipes, badge_style) -> None:
    for identity, name in (("condition.dodging", "Dodging"), ("condition.poisoned", "Poisoned")):
        fact = condition_fact(identity, name)
        timeline = compile_condition(recipes, header(fact), fact, (), start_ms=20, badge_style=badge_style)
        assert timeline.complete_ms == 20  # source alpha is unchanged; badge returns immediately
        sample = sample_condition(timeline, 20)
        assert sample.complete and sample.membership == (fact,)
        assert sample.feedback is not None and sample.feedback.label == "+" + name
        assert sample_condition(timeline, 20 + badge_style.durationMs).feedback is None
        assert sample.appearance.body_color == recipes[identity].persistent.bodyColor


def test_source_state_only_and_unimplemented_appearance_domains_are_distinct(recipes, badge_style) -> None:
    state_recipe = next(recipe for recipe in recipes.values() if recipe.disposition == "state_only")
    fact = condition_fact(state_recipe.definitionRef.content_id, state_recipe.label)
    timeline = compile_condition(recipes, header(fact), fact, (), start_ms=0, badge_style=badge_style)
    sample = sample_condition(timeline, 0)
    assert sample.membership == (fact,) and sample.feedback is None
    assert sample.appearance.alpha == 1 and sample.appearance.body_color is None
    assert timeline.complete_ms == 0 and not timeline.unsupported
    equipment_recipe = next(recipe for recipe in recipes.values() if recipe.persistent.equipmentModifiers)
    equipment = condition_fact(equipment_recipe.definitionRef.content_id, equipment_recipe.label)
    timeline = compile_condition(recipes, header(equipment), equipment, (), start_ms=0, badge_style=badge_style)
    assert timeline.unsupported
    assert any("equipment modifier unsupported" in issue for issue in timeline.unsupported)
    assert sample_condition(timeline, 0).membership == (equipment,)


def test_missing_recipe_keeps_actual_membership_without_inventing_a_transition(recipes, badge_style) -> None:
    unknown = condition_fact("condition.test_missing", "A retained condition")
    timeline = compile_condition(recipes, header(unknown), unknown, (), start_ms=30, badge_style=badge_style)
    assert timeline.start_ms == timeline.complete_ms == 30
    assert sample_condition(timeline, 29).membership == ()
    after = sample_condition(timeline, 30)
    assert after.membership == (unknown,) and after.appearance.alpha == 1
    assert after.appearance.body_color is None and after.feedback is None
    assert timeline.unsupported == ("Missing condition recipe: condition.test_missing",)


def test_late_neutral_wrapper_keeps_active_alpha_and_current_aggregate_color(recipes, badge_style) -> None:
    invisible = condition_fact("condition.invisible", "Invisible")
    fade = compile_condition(recipes, header(invisible), invisible, (), start_ms=0, badge_style=badge_style)
    wrapper = condition_fact("trait.ghoul_paralysis", "Ghoul Paralysis")
    event = Event(uuid=wrapper.event_uuid, source_entity_uuid=fade.target_uuid,
                  target_entity_uuid=fade.target_uuid, event_type=EventType.CONDITION_APPLICATION,
                  phase=EventPhase.COMPLETION, use_register=False)
    leaf = compile_condition(recipes, event, wrapper, (invisible,), start_ms=60, badge_style=badge_style)
    assert leaf.start_ms == leaf.complete_ms
    actor = str(fade.target_uuid)
    baseline = {actor: resolve_condition_appearance(leaf.after_membership, recipes)}
    current = condition_transition_appearances((fade, leaf), 120, baseline)
    assert current[actor].alpha == pytest.approx(.75)
    assert current[actor].body_color == baseline[actor].body_color
    assert current[actor].matched_behavior_ids == baseline[actor].matched_behavior_ids
    assert baseline[actor].alpha == .5
    assert condition_transition_appearances((fade, leaf), fade.complete_ms, baseline) == baseline
