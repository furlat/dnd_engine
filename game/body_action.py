"""Authored actor tracks whose children take effect without a projectile.

Studio self/touch casts and content actions share a body/frame/join shape.
Their original records still own equipment scope, feedback and recovery. The
causal compositor supplies the child join; this module owns no event queue.
"""

from dataclasses import dataclass, replace
from typing import Mapping
from uuid import UUID

from game.animation import ActorContact, BodySample, body_clip, body_duration, body_frame, facing_for_delta
from game.animation_types import ActionFeedback, AnimationData, Facing8, StudioCondition, StudioRecovery
from game.combat import actor_contact, actor_is_visible
from game.player_facts import ActionFact, PlayerNode, PlayerState, SpellFact


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


def bind_body_action(before: PlayerState, event: PlayerNode, data: AnimationData,
                     *, start_ms: float, facings: Mapping[str, Facing8],
                     contacts: Mapping[str, ActorContact]) -> BodyActionCue | None:
    fact = event.fact
    if not isinstance(fact, (SpellFact, ActionFact)) or fact.behavior_id is None:
        return None
    draft = data.drafts.get(fact.behavior_id) if isinstance(fact, SpellFact) else None
    binding = data.body_action_bindings.get(fact.behavior_id)
    recipe_id = binding.source_recipe if binding is not None else fact.behavior_id
    action = data.body_action_recipes.get(recipe_id) if isinstance(fact, ActionFact) else None
    if draft is None and action is None:
        return None
    if draft is not None and (draft.projectile is not None or draft.area is not None):
        return None
    actor = before.actors.get(fact.source_entity_uuid)
    if actor is None or not (str(actor.uuid) in contacts or actor_is_visible(before, actor)):
        return None
    contact = contacts.get(str(actor.uuid))
    if contact is None:
        contact = actor_contact(before, actor, data, facings.get(str(actor.uuid), "S"))
    gaps: list[str] = []
    recovery = condition = None
    feedback = None
    hidden_slots: tuple[str, ...] = ()
    hide_weapon = False
    enabled = True
    if draft is not None:
        cast = draft.cast
        if cast.bodyPlaybackSpeed is None or cast.equipment is None:
            raise ValueError("body cast requires materialized Studio defaults")
        clip, speed, effect_frame = cast.actionClip, cast.bodyPlaybackSpeed, cast.releaseFrame
        if cast.equipment.kind not in ("hidden", "unchanged"):
            raise ValueError("body cast equipment selection requires its authored loadout binding")
        hide_weapon = cast.equipment.kind == "hidden"
        recovery, condition = cast.recovery, draft.condition
        if any(layer is not None and layer.enabled and not layer.hidden
               for layer in (cast.weaponGlow, cast.aura, cast.slash, *(cast.effects or ()))):
            gaps.append("Body cast actor VFX layers are not bound")
        if fact.target_entity_uuid is not None and fact.target_entity_uuid != actor.uuid:
            target = contacts.get(str(fact.target_entity_uuid))
            other = before.actors.get(fact.target_entity_uuid)
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
        if action.actor.media:
            gaps.append("Authored body-action strip media is not bound")
    metadata = body_clip(data, contact, clip)
    if enabled and effect_frame >= metadata.frames:
        raise ValueError(f"unreachable body action effect frame {effect_frame} in {clip}")
    body_end = start_ms + (body_duration(metadata, speed) if enabled else 0)
    effect_ms = start_ms + (effect_frame * 1000 / (metadata.fps * speed) if enabled else 0)
    cue = BodyActionCue(event.uuid, contact, data, recipe_id, clip, speed, start_ms, effect_ms,
        body_end, body_end, body_end, enabled, hidden_slots, hide_weapon,
        recovery, condition, feedback, tuple(gaps))
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
        hidden_slots=cue.hidden_slots if elapsed_ms < cue.join_ms else ())
