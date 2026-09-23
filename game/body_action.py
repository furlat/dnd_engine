"""Authored actor tracks whose children take effect without a projectile.

Studio self/touch casts and content actions share a body/frame/join shape.
Their original records still own equipment scope, feedback and recovery. The
causal compositor supplies the child join; this module owns no event queue.
"""

from dataclasses import dataclass, replace
from typing import Mapping
from uuid import UUID

from dnd.core.events import EventType
from game.animation import ActorContact, BodySample, body_clip, body_duration, body_frame, facing_for_delta
from game.animation_types import (ActionFeedback, AnimationData, BodyActionRecipe, Facing8,
                                  StudioActorLayer, StudioCondition, StudioRecovery, StudioSpellDraft)
from game.combat import actor_contact, actor_is_visible
from game.player_facts import ActionFact, ConditionChangeFact, PlayerNode, PlayerState, SpellFact
from game.animation_rates import action_playback_rate


# The user accepted these existing potion source-strip omissions. This is a
# review decision, not permission to silently omit media from future actions.
ACCEPTED_SOURCE_STRIP_RECIPES = frozenset({
    "action.item.potion_greater_invisibility.drink",
    "action.item.potion_haste.drink",
    "action.item.potion_healing.drink",
})


@dataclass(frozen=True, slots=True)
class BodyActionCue:
    event_uuid: UUID
    contact: ActorContact
    data: AnimationData
    recipe_id: str
    clip: str
    playback_speed: float
    start_ms: float
    effect_ms: float
    body_end_ms: float
    join_ms: float
    complete_ms: float
    enabled: bool
    hidden_slots: tuple[str, ...]
    hide_weapon_during_body: bool
    recovery: StudioRecovery | None
    condition: StudioCondition | None
    feedback: ActionFeedback | None
    gaps: tuple[str, ...] = ()
    interaction_object_uuid: UUID | None = None
    relocates: bool = False
    cast_layers: tuple[StudioActorLayer, ...] = ()


def body_cast_limitations(draft: StudioSpellDraft) -> tuple[str, ...]:
    return ()


def body_action_limitations(action: BodyActionRecipe) -> tuple[str, ...]:
    return (("Authored body-action strip media is not bound",) if action.actor.media else ())


def bind_body_action(before: PlayerState, event: PlayerNode, data: AnimationData,
                     *, start_ms: float, facings: Mapping[str, Facing8],
                     contacts: Mapping[str, ActorContact],
                     reaction_source_uuid: UUID | None = None) -> BodyActionCue | None:
    fact = event.fact
    if isinstance(fact, ConditionChangeFact):
        recipe = data.condition_recipes.get(fact.condition.behavior_id or "")
        if (fact.event_type is not EventType.CONDITION_APPLICATION or recipe is None
                or recipe.reactionCastBinding is None or reaction_source_uuid is None):
            return None
        behavior_id = recipe.reactionCastBinding
        source_uuid, target_uuid = fact.target_entity_uuid, reaction_source_uuid
    elif isinstance(fact, (SpellFact, ActionFact)) and fact.behavior_id is not None:
        behavior_id = (fact.effect_id or fact.behavior_id) if isinstance(fact, SpellFact) else fact.behavior_id
        source_uuid, target_uuid = fact.source_entity_uuid, fact.target_entity_uuid
    else:
        return None
    draft = data.drafts.get(behavior_id)
    binding = data.body_action_bindings.get(behavior_id)
    recipe_id = binding.source_recipe if binding is not None else behavior_id
    action = data.body_action_recipes.get(recipe_id) if isinstance(fact, ActionFact) else None
    if draft is None and action is None:
        return None
    if draft is not None and (draft.projectile is not None or draft.area is not None
            or draft.media and behavior_id not in data.relocation_actions):
        return None
    actor = before.actors.get(source_uuid)
    if actor is None or not (str(actor.uuid) in contacts or actor_is_visible(before, actor)):
        return None
    contact = contacts.get(str(actor.uuid))
    if contact is None:
        contact = actor_contact(before, actor, data, facings.get(str(actor.uuid), "S"))
    interaction_object_uuid = None
    if isinstance(fact, ActionFact) and binding is not None and binding.interaction_target is not None:
        interaction_object_uuid = (fact.source_item_uuid if binding.interaction_target == "source_item"
                                   else fact.target_entity_uuid)
        target_object = before.objects.get(interaction_object_uuid) if interaction_object_uuid is not None else None
        if target_object is not None and target_object.placement.position != contact.grid:
            position = target_object.placement.position
            contact = replace(contact, facing=facing_for_delta(
                (position[0] - contact.grid[0], position[1] - contact.grid[1]), data))
    gaps: list[str] = []
    recovery = condition = None
    feedback = None
    hidden_slots: tuple[str, ...] = ()
    hide_weapon = False
    enabled = True
    cast_layers = ()
    if draft is not None:
        cast = draft.cast
        if cast.bodyPlaybackSpeed is None or cast.equipment is None:
            raise ValueError("body cast requires materialized Studio defaults")
        clip, speed, effect_frame = cast.actionClip, cast.bodyPlaybackSpeed, cast.releaseFrame
        if cast.equipment.kind not in ("hidden", "unchanged"):
            raise ValueError("body cast equipment selection requires its authored loadout binding")
        hide_weapon = cast.equipment.kind == "hidden"
        recovery, condition = cast.recovery, draft.condition
        cast_layers = tuple(layer for layer in (cast.weaponGlow, cast.aura, *(cast.effects or ()), cast.slash)
                            if layer is not None and layer.enabled and not layer.hidden)
        gaps.extend(body_cast_limitations(draft))
        if target_uuid is not None and target_uuid != actor.uuid:
            target = contacts.get(str(target_uuid))
            other = before.actors.get(target_uuid)
            if target is None and other is not None and actor_is_visible(before, other):
                target = actor_contact(before, other, data)
            if target is not None and target.grid != contact.grid:
                contact = replace(contact, facing=facing_for_delta(
                    (target.grid[0] - contact.grid[0], target.grid[1] - contact.grid[1]), data))
    else:
        assert action is not None
        if action.variants or action.projectile is not None:
            raise ValueError("body action requires a resolved actor-only content recipe")
        clip, speed = action.actor.clip, action.actor.playbackSpeed
        enabled, hidden_slots = action.actor.enabled, action.actor.hiddenSlots
        effect = next((anchor for name in ("effect", "release", "contact")
                       for anchor in action.anchors if anchor.name == name), None)
        if effect is None:
            raise ValueError("body action lacks an authored effect anchor")
        effect_frame = effect.frame
        feedback = binding.action_feedback if binding is not None else action.actionFeedback
        if isinstance(fact, ActionFact) and fact.reaction is not None and action.counterspellFeedback is not None:
            outcomes = action.counterspellFeedback
            feedback = (outcomes.automatic_success if fact.reaction.automatic else outcomes.check_success
                        ) if fact.reaction.succeeded else outcomes.check_failure
            media = data.interruptions.reactions.get(behavior_id)
            if media is not None:
                cast_layers = media.castLayers
            other = before.actors.get(target_uuid) if target_uuid is not None else None
            target = contacts.get(str(target_uuid))
            if target is None and other is not None and actor_is_visible(before, other):
                target = actor_contact(before, other, data)
            if target is not None and target.grid != contact.grid:
                contact = replace(contact, facing=facing_for_delta(
                    (target.grid[0] - contact.grid[0], target.grid[1] - contact.grid[1]), data))
        gaps.extend(body_action_limitations(action))
    speed *= action_playback_rate(data, actor)
    metadata = body_clip(data, contact, clip)
    if enabled and effect_frame >= metadata.frames:
        raise ValueError(f"unreachable body action effect frame {effect_frame} in {clip}")
    body_end = start_ms + (body_duration(metadata, speed) if enabled else 0)
    effect_ms = start_ms + (effect_frame * 1000 / (metadata.fps * speed) if enabled else 0)
    cue = BodyActionCue(event.uuid, contact, data, recipe_id, clip, speed, start_ms, effect_ms,
        body_end, body_end, body_end, enabled, hidden_slots, hide_weapon,
        recovery, condition, feedback, tuple(gaps), interaction_object_uuid,
        behavior_id in data.relocation_actions, cast_layers)
    return join_body_action(cue, data, body_end)


def join_body_action(cue: BodyActionCue, data: AnimationData, child_end_ms: float) -> BodyActionCue:
    """Both original leaves await the body and its children before restoring slots."""
    join = max(cue.body_end_ms, child_end_ms)
    recovery_duration = (body_duration(body_clip(data, cue.contact, cue.recovery.bodyClip),
                                      cue.recovery.bodyPlaybackSpeed)
                         if cue.recovery is not None and cue.recovery.enabled else 0)
    return replace(cue, join_ms=join, complete_ms=join + recovery_duration)


def sample_body_action(cue: BodyActionCue, data: AnimationData, elapsed_ms: float) -> BodySample | None:
    if not cue.enabled or elapsed_ms < cue.start_ms or elapsed_ms >= cue.complete_ms:
        return None
    during_body = elapsed_ms < cue.body_end_ms
    clip, start, speed = (cue.clip, cue.start_ms, cue.playback_speed) if during_body else ("Idle", cue.body_end_ms, 1)
    if cue.recovery is not None and cue.recovery.enabled and elapsed_ms >= cue.join_ms:
        clip, start, speed = cue.recovery.bodyClip, cue.join_ms, cue.recovery.bodyPlaybackSpeed
    metadata = body_clip(data, cue.contact, clip)
    return BodySample(cue.contact.actor_uuid, clip,
        body_frame(elapsed_ms - start, metadata.fps * speed, metadata.frames, loop=clip == "Idle"),
        cue.contact.facing, during_body and cue.hide_weapon_during_body,
        cast_layers=cue.cast_layers if during_body else (),
        hidden_slots=cue.hidden_slots if elapsed_ms < cue.join_ms else ())
