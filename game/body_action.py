"""Authored actor tracks whose children take effect without a projectile.

Studio self/touch casts and content actions share a body/frame/join shape.
Their original records still own equipment scope, feedback and recovery. The
causal compositor supplies the child join; this module owns no event queue.
"""

from dataclasses import dataclass, replace
from typing import Mapping
from uuid import UUID

from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference, TimingMeasurement, record_timing
from dnd.types.event_facts import EventType
from game.animation import (ActorContact, BodySample, body_context, context_duration, context_anchor_ms,
                            resolve_body_context, resolve_cast_recipe,
                            sample_context_body, sample_idle_body, facing_for_delta)
from game.animation_types import (ActionFeedback, AnimationData, BodyActionRecipe, Facing8,
                                  StudioActorLayer, StudioCondition, StudioRecovery, StudioSpellDraft)
from game.animation_types import BodyContext, ContentBodyQualifier, ActionFrameAnchor
from game.combat import actor_contact, actor_is_visible, received_cast_palette
from game.player_facts import (ActionFact, AttackFact, ConditionChangeFact, DamageRequestFact,
    SavingThrowFact, PlayerNode, PlayerState, SpellFact, PlayerLineage)
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
    body_context: BodyContext | None = None
    recovery_body: BodyContext | None = None
    save_success: bool | None = None
    timing_evidence: tuple[TimingEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class BodyActionSubject:
    """An already disclosed intervention can select the same authored actor track."""

    behavior_id: str
    source_uuid: UUID
    target_uuid: UUID | None = None
    save_success: bool | None = None


def intervention_subjects(event: PlayerNode, data: AnimationData) -> tuple[BodyActionSubject, ...]:
    """Actual disclosed handler evidence selects existing content action data."""
    fact = event.fact
    success = (fact.indomitable_reroll.succeeded if isinstance(fact,SavingThrowFact)
        and fact.indomitable_reroll is not None else
        fact.relentless_rage.succeeded if isinstance(fact,DamageRequestFact)
        and fact.relentless_rage is not None else None)
    target = (fact.target_entity_uuid if isinstance(fact,(AttackFact,SavingThrowFact,DamageRequestFact)) else None)
    return tuple(BodyActionSubject(row.behavior_id,row.source_entity_uuid,target,success)
        for row in event.content_attributions if row.role == 'effective_handler'
        and row.source_entity_uuid is not None
        and (recipe := data.body_action_recipes.get(row.behavior_id)) is not None
        and recipe.handlerResponse)


def body_cast_limitations(draft: StudioSpellDraft) -> tuple[str, ...]:
    return ()


def body_action_limitations(action: BodyActionRecipe) -> tuple[str, ...]:
    return (("Authored body-action strip media is not bound",) if action.actor.media else ())


def bind_body_action(before: PlayerState, event: PlayerNode, data: AnimationData,
                     *, start_ms: float, facings: Mapping[str, Facing8],
                     contacts: Mapping[str, ActorContact],
                     reaction_source_uuid: UUID | None = None,
                     subject: BodyActionSubject | None = None,
                     lineage: PlayerLineage | None = None) -> BodyActionCue | None:
    fact = event.fact
    if subject is not None:
        behavior_id, source_uuid, target_uuid = subject.behavior_id, subject.source_uuid, subject.target_uuid
    elif isinstance(fact, ConditionChangeFact):
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
    action = data.body_action_recipes.get(recipe_id) if isinstance(fact, ActionFact) or subject is not None else None
    if draft is None and action is None:
        return None
    if draft is not None and (draft.projectile is not None or draft.area is not None):
        return None
    actor = before.actors.get(source_uuid)
    if actor is None or not (str(actor.uuid) in contacts or actor_is_visible(before, actor)):
        return None
    contact = contacts.get(str(actor.uuid))
    if contact is None:
        contact = actor_contact(before, actor, data, facings.get(str(actor.uuid), "S"))
    if target_uuid is not None and target_uuid != actor.uuid:
        target = contacts.get(str(target_uuid))
        other = before.actors.get(target_uuid)
        if target is None and other is not None and actor_is_visible(before, other):
            target = actor_contact(before, other, data)
        if target is not None and target.grid != contact.grid:
            contact = replace(contact, facing=facing_for_delta(
                (target.grid[0] - contact.grid[0], target.grid[1] - contact.grid[1]), data))
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
    cast_body = None
    if draft is not None:
        if lineage is not None:
            draft = received_cast_palette(draft, lineage)
        cast_body = resolve_body_context(data, contact, "cast", ContentBodyQualifier(contentRef=draft.definitionRef))
        draft = resolve_cast_recipe(data, contact, draft)
        if ((draft.media and behavior_id not in data.relocation_actions)
                or draft.bodyMaterials or draft.displacementLayers or draft.arcs is not None or draft.directed is not None):
            return None
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
            cast_body = resolve_body_context(data, contact, "cast", ContentBodyQualifier(contentRef=action.definitionRef))
            if cast_body is not None:
                cast_layers = ()  # Original accents follow the selected body's clip.
            other = before.actors.get(target_uuid) if target_uuid is not None else None
            target = contacts.get(str(target_uuid))
            if target is None and other is not None and actor_is_visible(before, other):
                target = actor_contact(before, other, data)
            if target is not None and target.grid != contact.grid:
                contact = replace(contact, facing=facing_for_delta(
                    (target.grid[0] - contact.grid[0], target.grid[1] - contact.grid[1]), data))
        gaps.extend(body_action_limitations(action))
    if draft is not None:
        qualifier = ContentBodyQualifier(contentRef=draft.definitionRef)
    else:
        assert action is not None
        qualifier = ContentBodyQualifier(contentRef=action.definitionRef)
    selected = (cast_body.model_copy(update={"anchors": (ActionFrameAnchor(name="effect",
        frame=next(anchor.frame for anchor in cast_body.anchors if anchor.name == "release")),)})
        if cast_body is not None else resolve_body_context(data, contact, "body_action", qualifier, body_context(
            clip, speed, enabled=enabled, anchors=(ActionFrameAnchor(name="effect", frame=effect_frame),))))
    selected = selected.model_copy(update={"actor": selected.actor.model_copy(update={
        "playbackSpeed": selected.actor.playbackSpeed * action_playback_rate(data, actor)})})
    recovery_body = resolve_body_context(data, contact, "body_action_recovery", qualifier, body_context(
        recovery.bodyClip if recovery else "Idle", recovery.bodyPlaybackSpeed if recovery else 1,
        enabled=recovery.enabled if recovery else False))
    clip, speed, enabled = selected.actor.clip, selected.actor.playbackSpeed, selected.actor.enabled
    body_duration_ms = context_duration(data, contact, selected)
    effect_offset_ms = context_anchor_ms(data, contact, selected, "effect")
    body_end = start_ms + body_duration_ms
    effect_ms = start_ms + effect_offset_ms
    evidence: list[TimingEvidence] = []
    start = TimingOperand(TimingReference('event', event.uuid, 'start'), start_ms)
    record_timing(evidence, TimingReference('event', event.uuid, 'body_end'), 'body_end',
        (replace(start, offset_ms=body_duration_ms, authored_field='body_context.duration'),), body_end)
    record_timing(evidence, TimingReference('event', event.uuid, 'effect'), 'body_effect',
        (replace(start, offset_ms=effect_offset_ms, authored_field='body_context.anchors.effect', measurements=(
            TimingMeasurement('body.playbackSpeed', speed),)),), effect_ms)
    cue = BodyActionCue(event.uuid, contact, data, recipe_id, clip, speed, start_ms, effect_ms,
        body_end, body_end, body_end, enabled, hidden_slots, hide_weapon,
        recovery, condition, feedback, tuple(gaps), interaction_object_uuid,
        behavior_id in data.relocation_actions, cast_layers, selected, recovery_body,
        subject.save_success if subject is not None else None, timing_evidence=tuple(evidence))
    return join_body_action(cue, data, body_end)


def join_body_action(cue: BodyActionCue, data: AnimationData, child_end_ms: float, *,
                     child_evidence: tuple[TimingOperand, ...] = ()) -> BodyActionCue:
    """Both original leaves await the body and its children before restoring slots."""
    join = max(cue.body_end_ms, child_end_ms)
    recovery_duration = context_duration(data, cue.contact, cue.recovery_body) if cue.recovery_body is not None else 0
    evidence = list(cue.timing_evidence)
    body = next((TimingOperand(row.target, row.at_ms, row.index) for row in reversed(evidence)
        if row.target.anchor == 'body_end'), TimingOperand(TimingReference('event', cue.event_uuid, 'body_end'), cue.body_end_ms))
    joined = record_timing(evidence, TimingReference('event', cue.event_uuid, 'join'), 'body_join',
        (body, *(child_evidence or (TimingOperand(TimingReference('event', cue.event_uuid, 'join'), child_end_ms),))),
        join, 'maximum')
    record_timing(evidence, TimingReference('event', cue.event_uuid, 'complete'), 'body_complete',
        (replace(joined, offset_ms=recovery_duration, authored_field='recovery_body.duration'),), join + recovery_duration)
    return replace(cue, join_ms=join, complete_ms=join + recovery_duration, timing_evidence=tuple(evidence))


def sample_body_action(cue: BodyActionCue, data: AnimationData, elapsed_ms: float) -> BodySample | None:
    if elapsed_ms < cue.start_ms or elapsed_ms >= cue.complete_ms:
        return None
    during_body = elapsed_ms < cue.body_end_ms
    if cue.recovery_body is not None and cue.recovery_body.actor.enabled and elapsed_ms >= cue.join_ms:
        body = sample_context_body(data, cue.contact, cue.recovery_body, elapsed_ms - cue.join_ms)
    elif not cue.enabled:
        return None
    elif during_body:
        selected = cue.body_context or body_context(cue.clip, cue.playback_speed)
        body = sample_context_body(data, cue.contact, selected, elapsed_ms - cue.start_ms)
    else:
        body = sample_idle_body(data, cue.contact, elapsed_ms - cue.body_end_ms)
    return replace(body,
        hide_weapon=during_body and cue.hide_weapon_during_body,
        cast_layers=cue.cast_layers if during_body else (),
        hidden_slots=cue.hidden_slots if elapsed_ms < cue.join_ms else ())
