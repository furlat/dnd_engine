"""Pure condition transitions and persistent appearance from Studio recipes.

Membership comes from retained condition UUIDs. Visual composition follows the
original priority/exclusive-group rules without acquiring mechanical ownership.
"""

from dataclasses import dataclass, replace
from math import isfinite
from typing import Mapping
from uuid import UUID

from dnd.core.condition_types import ConditionCategory
from dnd.core.events import Event, EventType
from game.animation import NumberSample
from game.animation_types import FloatingFeedbackStyle, StudioCondition
from game.condition_types import ConditionBodyColor, ConditionRecipe
from game.presentation import ConditionFact


@dataclass(frozen=True, slots=True)
class ConditionAppearance:
    alpha: float = 1.0
    body_color: ConditionBodyColor | None = None
    matched_behavior_ids: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConditionTimeline:
    event_uuid: UUID
    target_uuid: UUID
    start_ms: float
    complete_ms: float
    before_membership: tuple[ConditionFact, ...]
    after_membership: tuple[ConditionFact, ...]
    before_appearance: ConditionAppearance
    after_appearance: ConditionAppearance
    feedback_text: str | None
    feedback_color: int
    badge_style: FloatingFeedbackStyle
    unsupported: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConditionSample:
    membership: tuple[ConditionFact, ...]
    appearance: ConditionAppearance
    feedback: NumberSample | None
    complete: bool


def resolve_condition_appearance(
    members: tuple[ConditionFact, ...], recipes: Mapping[str, ConditionRecipe],
) -> ConditionAppearance:
    """Deduplicate visual recipes while retaining source-owned membership."""
    exact: dict[str, ConditionRecipe] = {}
    unsupported: list[str] = []
    for member in members:
        if member.category is ConditionCategory.INTERNAL:
            continue
        recipe = recipes.get(member.behavior_id) if member.behavior_id is not None else None
        if recipe is None:
            unsupported.append(f"Missing condition recipe: {member.behavior_id}")
        else:
            exact[recipe.definitionRef.identity_key] = recipe
    ordered = sorted(exact.values(), key=lambda recipe: (
        -recipe.composition.priority, recipe.definitionRef.identity_key,
    ))
    claimed: set[str] = set()
    counts: dict[str, int] = {}
    selected: list[str] = []
    alpha, body = 1.0, None
    for recipe in ordered:
        composition = recipe.composition
        if (composition.exclusiveGroup and composition.exclusiveGroup in claimed
                or counts.get(composition.group, 0) >= composition.maxLayers):
            continue
        if composition.exclusiveGroup:
            claimed.add(composition.exclusiveGroup)
        counts[composition.group] = counts.get(composition.group, 0) + 1
        identity = recipe.definitionRef.content_id
        selected.append(identity)
        persistent = recipe.persistent
        alpha *= persistent.alphaMultiplier
        if body is None and persistent.bodyColor is not None:
            body = persistent.bodyColor
        unsupported.extend(f"Condition strip unsupported: {identity}/{layer.id}" for layer in persistent.layers)
        unsupported.extend(f"Condition equipment modifier unsupported: {identity}/{modifier.id}"
                           for modifier in persistent.equipmentModifiers)
        unsupported.extend(f"Condition rig layer unsupported: {identity}/{layer.id}"
                           for layer in persistent.appearanceLayers)
    return ConditionAppearance(alpha, body, tuple(selected), tuple(dict.fromkeys(unsupported)))


def compile_condition(
    recipes: Mapping[str, ConditionRecipe], event: Event, fact: ConditionFact,
    before: tuple[ConditionFact, ...], *, start_ms: float,
    badge_style: FloatingFeedbackStyle, override: StudioCondition | None = None,
) -> ConditionTimeline:
    """Attach one actual condition transition at its parent's authored anchor."""
    if not isfinite(start_ms) or start_ms < 0:
        raise ValueError("condition start requires finite nonnegative time")
    if (event.uuid != fact.event_uuid or event.target_entity_uuid is None
            or event.event_type not in (EventType.CONDITION_APPLICATION, EventType.CONDITION_REMOVAL)):
        raise ValueError("condition timeline requires its exact retained header and target")
    recipe = recipes.get(fact.behavior_id) if fact.behavior_id is not None else None
    applied = event.event_type is EventType.CONDITION_APPLICATION
    members = {member.condition_uuid: member for member in before}
    if applied and fact.category is not ConditionCategory.INTERNAL:
        members[fact.condition_uuid] = fact
    elif not applied:
        members.pop(fact.condition_uuid, None)
    after = tuple(members.values())
    old_appearance = resolve_condition_appearance(before, recipes)
    new_appearance = resolve_condition_appearance(after, recipes)
    if recipe is None:
        # Membership is still an actual retained fact. An absent authoring row
        # supplies no invented duration, feedback, tint or strip animation.
        unsupported = tuple(dict.fromkeys((*old_appearance.unsupported, *new_appearance.unsupported,
                                            f"Missing condition recipe: {fact.behavior_id}")))
        return ConditionTimeline(
            event.uuid, event.target_entity_uuid, start_ms, start_ms,
            before, after, old_appearance, new_appearance, None, 0xFFFFFF, badge_style, unsupported,
        )
    transition = recipe.application if applied else recipe.removal
    start = start_ms + (override.delayMs if override is not None else 0)
    # ConditionClip changes persistent body filtering at entry; only alpha
    # interpolates. Equal alpha returns immediately, irrespective of durationMs.
    alpha_duration = (transition.durationMs
                      if abs(old_appearance.alpha - new_appearance.alpha) >= 0.001 else 0)
    feedback = override.feedbackEnabled if override is not None else transition.feedbackEnabled
    unsupported = tuple(dict.fromkeys((
        *old_appearance.unsupported, *new_appearance.unsupported,
        *(f"Condition transition strip unsupported: {recipe.definitionRef.content_id}/{effect.id}"
          for effect in transition.effects),
    )))
    return ConditionTimeline(
        event.uuid, event.target_entity_uuid, start, start + alpha_duration,
        before, after, old_appearance, new_appearance,
        ("+" if applied else "−") + fact.name if feedback else None,
        transition.feedbackColor, badge_style, unsupported,
    )


def sample_condition(timeline: ConditionTimeline, elapsed_ms: float) -> ConditionSample:
    """Absolute sampling preserves replay; a floating badge does not hold a join."""
    if not isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("condition sampling requires finite nonnegative time")
    if elapsed_ms < timeline.start_ms:
        return ConditionSample(timeline.before_membership, timeline.before_appearance, None, False)
    duration = timeline.complete_ms - timeline.start_ms
    progress = min(1.0, (elapsed_ms - timeline.start_ms) / duration) if duration > 0 else 1.0
    eased = progress * progress * (3 - 2 * progress)
    appearance = replace(timeline.after_appearance, alpha=(
        timeline.before_appearance.alpha
        + (timeline.after_appearance.alpha - timeline.before_appearance.alpha) * eased
    ))
    feedback = None
    style = timeline.badge_style
    if timeline.feedback_text is not None and elapsed_ms < timeline.start_ms + style.durationMs:
        badge_progress = (elapsed_ms - timeline.start_ms) / style.durationMs
        alpha = (1.0 if badge_progress < style.fadeStartFraction or style.fadeStartFraction == 1
                 else (1 - badge_progress) / (1 - style.fadeStartFraction))
        feedback = NumberSample(str(timeline.target_uuid), None, timeline.feedback_text,
                                timeline.feedback_color, badge_progress, alpha, kind="badge")
    return ConditionSample(timeline.after_membership, appearance, feedback, elapsed_ms >= timeline.complete_ms)


def condition_transition_appearances(
    timelines: tuple[ConditionTimeline, ...], elapsed_ms: float,
    appearances: Mapping[str, ConditionAppearance],
) -> dict[str, ConditionAppearance]:
    """Overlay active alpha clocks on appearance from all current memberships.

    ConditionClip's persistent sync selects the current aggregate body filter;
    an alpha transition ticks independently. Immediate or finished sibling
    leaves cannot overwrite that active tick with an old membership snapshot.
    """
    if not isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("condition sampling requires finite nonnegative time")
    result = dict(appearances)
    for timeline in sorted(timelines, key=lambda item: item.start_ms):
        actor = str(timeline.target_uuid)
        if actor in result and timeline.start_ms <= elapsed_ms < timeline.complete_ms:
            result[actor] = replace(result[actor], alpha=sample_condition(timeline, elapsed_ms).appearance.alpha)
    return result
