"""Pure condition transitions and persistent appearance from Studio recipes.

Membership comes from retained condition UUIDs. Visual composition follows the
original priority/exclusive-group rules without acquiring mechanical ownership.
"""

from dataclasses import dataclass, replace
from math import isfinite
from types import MappingProxyType
from typing import Literal, Mapping
from uuid import UUID

from dnd.core.condition_types import ConditionCategory
from dnd.core.events import EventType
from dnd.core.life_types import LifeState
from game.animation import (ActorContact, BodySample, BodyTransition, NumberSample, body_clip,
                            compile_body_transition, sample_body_transition)
from game.animation_types import AnimationData, FloatingFeedbackStyle, StudioCondition
from game.condition_types import (Activity, ConditionBodyColor, ConditionLabel, ConditionRecipe, ConditionTransition,
                                  ConditionBodyDistortion, ConditionLiveCopies, ConditionBodyRamp, ConditionTransitionEffect)
from game.condition_media import ConditionLayerMedia, ResolvedConditionLayer, supported_layer
from game.actor_facts import ConditionFact
from game.player_facts import ConditionChangeFact, PlayerNode


@dataclass(frozen=True, slots=True)
class LiveCopyAppearance:
    recipe: ConditionLiveCopies
    owner_uuid: UUID
    count: int
    # (slot, world offset fraction, opacity fraction), sampled on the shared clock.
    slots: tuple[tuple[int, float, float], ...] = ()
    layers: tuple[tuple[int, tuple[ResolvedConditionLayer, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class ConditionAppearance:
    alpha: float = 1.0
    body_color: ConditionBodyColor | None = None
    matched_behavior_ids: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()
    body_pose: str | None = None
    label: ConditionLabel | None = None
    layers: tuple[ResolvedConditionLayer, ...] = ()
    activity: Activity = "idle"
    scale: float = 1.
    live_copies: LiveCopyAppearance | None = None
    distortion: ConditionBodyDistortion | None = None
    distortion_strength: float = 1.
    time_ms: float = 0.
    body_ramp: ConditionBodyRamp | None = None
    ramp_strength: float = 1.


@dataclass(frozen=True, slots=True)
class ConditionResponseCue:
    """One finite response to one received condition-owned fact."""

    event_uuid: UUID
    owner_uuid: UUID
    actor_uuid: UUID
    behavior_id: str
    trigger: Literal["consumed", "healed"]
    start_ms: float
    effects: tuple[ConditionTransitionEffect, ...]

    @property
    def end_ms(self) -> float:
        return self.start_ms + max((effect.startOffsetMs + effect.durationMs for effect in self.effects), default=0.)


def bind_condition_response(event_uuid: UUID, actor_uuid: UUID, member: ConditionFact,
                            trigger: Literal["consumed", "healed"], start_ms: float,
                            recipes: Mapping[str, ConditionRecipe]) -> ConditionResponseCue | None:
    recipe = recipes.get(member.behavior_id or "")
    if recipe is None:
        return None
    effects = tuple(effect for response in recipe.responses if response.trigger == trigger for effect in response.effects)
    return (ConditionResponseCue(event_uuid, member.condition_uuid, actor_uuid,
        recipe.definitionRef.content_id, trigger, start_ms, effects) if effects else None)


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
    body: BodyTransition | None = None
    alpha_end_ms: float | None = None


@dataclass(frozen=True, slots=True)
class ConditionSample:
    membership: tuple[ConditionFact, ...]
    appearance: ConditionAppearance
    feedback: NumberSample | None
    complete: bool


def persistent_limitations(recipe: ConditionRecipe,
                          media: Mapping[str, ConditionLayerMedia] = MappingProxyType({})) -> tuple[str, ...]:
    """Selected unsupported tracks, shared by binding and developer inventory."""
    identity, persistent = recipe.definitionRef.content_id, recipe.persistent
    return (
        *(f"Condition strip unsupported: {identity}/{layer.id}" for layer in persistent.layers
          if not supported_layer(layer, media)),
        *(f"Condition equipment modifier unsupported: {identity}/{modifier.id}"
          for modifier in persistent.equipmentModifiers),
        *(f"Condition rig layer unsupported: {identity}/{layer.id}" for layer in persistent.appearanceLayers),
        *(f"Condition response strip unsupported: {identity}/{effect.id}"
          for response in recipe.responses for effect in response.effects
          if effect.assetId not in media or media[effect.assetId].asset_id is None),
    )


def transition_limitations(identity: str, transition: ConditionTransition,
                           media: Mapping[str, ConditionLayerMedia] = MappingProxyType({})) -> tuple[str, ...]:
    return tuple(f"Condition transition strip unsupported: {identity}/{effect.id}"
                 for effect in transition.effects
                 if effect.assetId not in media or media[effect.assetId].asset_id is None)


def resolve_condition_appearance(
    members: tuple[ConditionFact, ...], recipes: Mapping[str, ConditionRecipe],
    media: Mapping[str, ConditionLayerMedia] = MappingProxyType({}),
    *, extra_members: tuple[tuple[UUID, str], ...] = (),
) -> ConditionAppearance:
    """Deduplicate visual recipes while retaining source-owned membership."""
    exact: dict[str, ConditionRecipe] = {}
    owners: dict[str, UUID] = {}
    facts = {member.condition_uuid: member for member in members}
    unsupported: list[str] = []
    for member in members:
        if member.category is ConditionCategory.INTERNAL:
            continue
        recipe = recipes.get(member.behavior_id) if member.behavior_id is not None else None
        if recipe is None:
            unsupported.append(f"Missing condition recipe: {member.behavior_id}")
        else:
            exact[recipe.definitionRef.identity_key] = recipe
            owners.setdefault(recipe.definitionRef.identity_key, member.condition_uuid)
    for owner, identity in extra_members:
        recipe = recipes.get(identity)
        if recipe is not None:
            exact[recipe.definitionRef.identity_key] = recipe
            owners.setdefault(recipe.definitionRef.identity_key, owner)
    ordered = sorted(exact.values(), key=lambda recipe: (
        -recipe.composition.priority, recipe.definitionRef.identity_key,
    ))
    claimed: set[str] = set()
    counts: dict[str, int] = {}
    selected: list[str] = []
    alpha, body, pose, label = 1.0, None, None, None
    scale = 1.
    copies, distortion, ramp = None, None, None
    layers: list[ResolvedConditionLayer] = []
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
        owner = owners[recipe.definitionRef.identity_key]
        member = facts.get(owner)
        if member is not None and member.state is not None:
            if persistent.bodyScale is not None:
                if member.state.size_change == "enlarge":
                    scale *= persistent.bodyScale.enlarge
                elif member.state.size_change == "reduce":
                    scale *= persistent.bodyScale.reduce
            if copies is None and persistent.liveCopies is not None and member.state.duplicate_count is not None:
                count = min(member.state.duplicate_count, len(persistent.liveCopies.slots))
                copies = LiveCopyAppearance(persistent.liveCopies, owner, count,
                    tuple((index, 1., 1.) for index in range(count)))
        if distortion is None and persistent.bodyDistortion is not None:
            distortion = persistent.bodyDistortion
        if ramp is None and persistent.bodyRamp is not None:
            ramp = persistent.bodyRamp
        alpha *= persistent.alphaMultiplier
        if body is None and persistent.bodyColor is not None:
            body = persistent.bodyColor
        if pose is None and persistent.bodyPose is not None:
            pose = persistent.bodyPose
        if label is None and persistent.label is not None:
            label = persistent.label
        layers.extend(ResolvedConditionLayer(layer, media[layer.assetId], owners[recipe.definitionRef.identity_key])
                      for layer in persistent.layers if supported_layer(layer, media)
                      and (layer.whenEnergyType is None or member is not None and member.state is not None
                           and layer.whenEnergyType is member.state.energy_type)
                      and (layer.whenAbility is None or member is not None and member.state is not None
                           and layer.whenAbility == member.state.enhanced_ability))
        unsupported.extend(persistent_limitations(recipe, media))
    selected_layers = tuple(sorted(layers, key=lambda value: (-value.layer.priority, value.layer.id)))
    return ConditionAppearance(alpha, body, tuple(selected), tuple(dict.fromkeys(unsupported)), pose, label,
                               selected_layers, scale=scale, live_copies=copies, distortion=distortion, body_ramp=ramp)


def condition_contact(contact: ActorContact, appearance: ConditionAppearance | None) -> ActorContact:
    """Resolve one scale before drawing sockets/body; already resolved contacts are idempotent."""
    if appearance is None or contact.condition_scale == appearance.scale:
        return contact
    return replace(contact, visual_scale=contact.visual_scale / contact.condition_scale * appearance.scale,
                   condition_scale=appearance.scale)


def condition_body_pose(data: AnimationData, body: BodySample, contact: ActorContact,
                        appearance: ConditionAppearance | None) -> BodySample:
    """A retained condition replaces idle only; actions and death keep ownership."""
    if (body.clip not in ("Idle", data.damage_context.bodyClip) or contact.life_state is LifeState.DEAD
            or appearance is None or appearance.body_pose is None):
        return body
    clip = appearance.body_pose
    return replace(body, clip=clip, frame=body_clip(data, contact, clip).frames - 1)


def bind_condition_body(timeline: ConditionTimeline, recipe: ConditionRecipe | None,
                        data: AnimationData, contact: ActorContact) -> ConditionTimeline:
    """A finite gesture follows an actual aggregate rest-pose entry or exit."""
    old, new = timeline.before_appearance.body_pose, timeline.after_appearance.body_pose
    if recipe is None or old == new:
        return timeline
    animation = (recipe.application if new is not None else recipe.removal).bodyAnimation
    if animation is None:
        return timeline
    cue = compile_body_transition(data, contact, animation)
    return replace(timeline, body=cue, alpha_end_ms=timeline.complete_ms,
                   complete_ms=max(timeline.complete_ms, timeline.start_ms + cue.frames * 1000 / cue.fps))


def sample_condition_body(timeline: ConditionTimeline, elapsed_ms: float,
                          life_state: LifeState) -> BodySample | None:
    cue = timeline.body
    if cue is None or life_state is not LifeState.ALIVE or elapsed_ms < timeline.start_ms:
        return None
    return sample_body_transition(cue, elapsed_ms - timeline.start_ms)


def compile_condition(
    recipes: Mapping[str, ConditionRecipe], event: PlayerNode, fact: ConditionFact,
    before: tuple[ConditionFact, ...], *, start_ms: float,
    badge_style: FloatingFeedbackStyle, override: StudioCondition | None = None,
    media: Mapping[str, ConditionLayerMedia] = MappingProxyType({}),
    media_activated: bool = False,
) -> ConditionTimeline:
    """Attach one actual condition transition at its parent's authored anchor."""
    if not isfinite(start_ms) or start_ms < 0:
        raise ValueError("condition start requires finite nonnegative time")
    change = event.fact
    if (event.uuid != fact.event_uuid or not isinstance(change, ConditionChangeFact)
            or change.event_type not in (EventType.CONDITION_APPLICATION, EventType.CONDITION_REMOVAL,
                                         EventType.CONDITION_STATE_CHANGED)):
        raise ValueError("condition timeline requires its exact retained header and target")
    recipe = recipes.get(fact.behavior_id) if fact.behavior_id is not None else None
    applied = change.event_type is EventType.CONDITION_APPLICATION
    updated = change.event_type is EventType.CONDITION_STATE_CHANGED
    members = {member.condition_uuid: member for member in before}
    if (applied or updated) and fact.category is not ConditionCategory.INTERNAL:
        members[fact.condition_uuid] = fact
    elif not applied:
        members.pop(fact.condition_uuid, None)
    after = tuple(members.values())
    old_appearance = resolve_condition_appearance(before, recipes, media)
    new_appearance = resolve_condition_appearance(after, recipes, media)
    if updated:
        return ConditionTimeline(event.uuid, change.target_entity_uuid, start_ms, start_ms,
            before, after, old_appearance, new_appearance, None, 0xFFFFFF, badge_style,
            tuple(dict.fromkeys((*old_appearance.unsupported, *new_appearance.unsupported))))
    if recipe is None:
        # Membership is still an actual retained fact. An absent authoring row
        # supplies no invented duration, feedback, tint or strip animation.
        unsupported = tuple(dict.fromkeys((*old_appearance.unsupported, *new_appearance.unsupported,
                                            f"Missing condition recipe: {fact.behavior_id}")))
        return ConditionTimeline(
            event.uuid, change.target_entity_uuid, start_ms, start_ms,
            before, after, old_appearance, new_appearance, None, 0xFFFFFF, badge_style, unsupported,
        )
    transition = recipe.application if applied else recipe.removal
    start = start_ms + (override.delayMs if override is not None else 0)
    # Body filtering changes at entry. Authored alpha and size share this
    # transition; its duration does not delay unrelated steady-state filters.
    alpha_duration = (transition.durationMs
                      if (abs(old_appearance.alpha - new_appearance.alpha) >= 0.001
                          or abs(old_appearance.scale - new_appearance.scale) >= 0.001) else 0)
    feedback = override.feedbackEnabled if override is not None else transition.feedbackEnabled
    identity = recipe.definitionRef.content_id
    changed = ((identity not in old_appearance.matched_behavior_ids and identity in new_appearance.matched_behavior_ids)
               if applied else (identity in old_appearance.matched_behavior_ids and identity not in new_appearance.matched_behavior_ids))
    # An executed activation already owns its finite tail. Removal effects are
    # cancellation media only in that case, as in the shared lifetime sampler.
    media_duration = max((effect.startOffsetMs + effect.durationMs for effect in transition.effects), default=0) if (
        changed and (applied or not media_activated and not change.consumed)) else 0
    ramp_duration = (recipe.persistent.bodyRamp.applicationMs if applied else recipe.persistent.bodyRamp.removalMs
                     ) if changed and recipe.persistent.bodyRamp is not None else 0.
    unsupported = tuple(dict.fromkeys((
        *old_appearance.unsupported, *new_appearance.unsupported,
        *transition_limitations(recipe.definitionRef.content_id, transition, media),
    )))
    return ConditionTimeline(
        event.uuid, change.target_entity_uuid, start, start + max(alpha_duration, media_duration, ramp_duration),
        before, after, old_appearance, new_appearance,
        ("+" if applied else "−") + fact.name if feedback else None,
        transition.feedbackColor, badge_style, unsupported,
        alpha_end_ms=(start + alpha_duration
                      if abs(old_appearance.scale - new_appearance.scale) >= .001 else None),
    )


def sample_condition(timeline: ConditionTimeline, elapsed_ms: float) -> ConditionSample:
    """Absolute sampling preserves replay; a floating badge does not hold a join."""
    if not isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("condition sampling requires finite nonnegative time")
    if elapsed_ms < timeline.start_ms:
        return ConditionSample(timeline.before_membership, timeline.before_appearance, None, False)
    duration = (timeline.alpha_end_ms if timeline.alpha_end_ms is not None else timeline.complete_ms) - timeline.start_ms
    progress = min(1.0, (elapsed_ms - timeline.start_ms) / duration) if duration > 0 else 1.0
    eased = progress * progress * (3 - 2 * progress)
    appearance = replace(timeline.after_appearance, alpha=(
        timeline.before_appearance.alpha
        + (timeline.after_appearance.alpha - timeline.before_appearance.alpha) * eased
    ), scale=timeline.before_appearance.scale
        + (timeline.after_appearance.scale - timeline.before_appearance.scale) * eased)
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
            sample = sample_condition(timeline, elapsed_ms).appearance
            result[actor] = replace(result[actor], alpha=sample.alpha, scale=sample.scale)
    return result
