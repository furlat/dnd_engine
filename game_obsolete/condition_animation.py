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
from dnd.core.content.identities import ContentRef
from dnd.types.event_facts import EventType
from dnd.core.life_types import LifeState
from game.animation import (ActorContact, BodySample, BodyTransition, NumberSample, body_clip,
                            compile_body_transition, sample_body_transition, body_context, resolve_body_context)
from game.animation_types import BodyMaterialSample, AnimationData, FloatingFeedbackStyle, StudioCondition, ContentBodyQualifier
from game.condition_types import (Activity, ConditionBodyColor, ConditionLabel, ConditionRecipe, ConditionTransition,
                                  ConditionBodyDistortion, ConditionLiveCopies, ConditionBodyRamp, ConditionTransitionEffect,
                                  ConditionFrozenPose, ConditionBodyOutline, ConditionAppearanceLayer,
                                  ConditionEquipmentModifier, ConditionAbsenceEcho)
from game.condition_media import ConditionLayerMedia, ResolvedConditionLayer, supported_layer
from dnd.types.actor_facts import ConditionFact
from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference, record_timing
from dnd.player.facts import ConditionChangeFact, DamageFact, HealFact, PlayerActor, PlayerNode


@dataclass(frozen=True, slots=True)
class LiveCopyAppearance:
    recipe: ConditionLiveCopies
    owner_uuid: UUID
    count: int
    # (slot, world offset fraction, opacity fraction), sampled on the shared clock.
    slots: tuple[tuple[int, float, float], ...] = ()
    layers: tuple[tuple[int, tuple[ResolvedConditionLayer, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class ConditionRigLayer:
    layer: ConditionAppearanceLayer
    owner_uuid: UUID
    alpha: float = 1.


@dataclass(frozen=True, slots=True)
class ConditionItemModifier:
    item_uuid: UUID
    modifier: ConditionEquipmentModifier


@dataclass(frozen=True, slots=True)
class AbsenceBodySample:
    recipe: ConditionAbsenceEcho
    progress: float
    opacity: float = 1.


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
    ramp_age_ms: float = 0.
    frozen_pose: ConditionFrozenPose | None = None
    body_outline: ConditionBodyOutline | None = None
    outline_owner_uuid: UUID | None = None
    outline_age_ms: float | None = None
    body_pose_ref: ContentRef | None = None
    frozen_pose_ref: ContentRef | None = None
    frozen_body: BodySample | None = None
    frozen_owner_uuid: UUID | None = None
    rig_layers: tuple[ConditionRigLayer, ...] = ()
    item_modifiers: tuple[ConditionItemModifier, ...] = ()
    finite_materials: tuple[BodyMaterialSample, ...] = ()
    absence: AbsenceBodySample | None = None


@dataclass(frozen=True, slots=True)
class ConditionResponseCue:
    """One finite response to one received condition-owned fact."""

    event_uuid: UUID
    owner_uuid: UUID
    actor_uuid: UUID
    behavior_id: str
    trigger: Literal["consumed", "healed", "damage_requested", "damage_applied", "damage_received"]
    start_ms: float
    effects: tuple[ConditionTransitionEffect, ...]
    recipient_uuid: UUID | None = None

    @property
    def end_ms(self) -> float:
        return self.start_ms + max((effect.startOffsetMs + effect.durationMs for effect in self.effects), default=0.)


def bind_condition_response(event_uuid: UUID, actor_uuid: UUID, member: ConditionFact,
                            trigger: Literal["consumed", "healed", "damage_requested", "damage_applied", "damage_received"], start_ms: float,
                            recipes: Mapping[str, ConditionRecipe], *,
                            recipient_uuid: UUID | None = None) -> ConditionResponseCue | None:
    recipe = recipes.get(member.behavior_id or "")
    if recipe is None:
        return None
    effects = tuple(effect for response in recipe.responses if response.trigger == trigger for effect in response.effects
        if (effect.participant == "owner" or recipient_uuid is not None)
        and (effect.whenEnergyType is None or member.state is not None and member.state.energy_type is effect.whenEnergyType))
    return (ConditionResponseCue(event_uuid, member.condition_uuid, actor_uuid,
        recipe.definitionRef.content_id, trigger, start_ms, effects, recipient_uuid) if effects else None)


def bind_event_condition_response(event: PlayerNode,
        actors: Mapping[UUID, PlayerActor], start_ms: float,
        recipes: Mapping[str, ConditionRecipe]) -> ConditionResponseCue | None:
    """Bind only recorded consumption, healing or source-owned damage outcomes."""
    fact = event.fact
    if (isinstance(fact, ConditionChangeFact) and fact.consumed
            and fact.event_type is EventType.CONDITION_REMOVAL
            and fact.condition.category is not ConditionCategory.INTERNAL):
        return bind_condition_response(event.uuid, fact.target_entity_uuid,
            fact.condition, "consumed", start_ms, recipes)
    if isinstance(fact, HealFact):
        if fact.was_blocked or fact.actual_healing <= 0 or fact.source_condition_uuid is None:
            return None
        owner = actors.get(fact.target_entity_uuid)
        member = next((row for row in owner.conditions
            if row.condition_uuid == fact.source_condition_uuid), None) if owner else None
        return bind_condition_response(event.uuid, fact.target_entity_uuid,
            member, "healed", start_ms, recipes) if member is not None else None
    if isinstance(fact, DamageFact) and fact.source_condition_uuid is not None:
        source = actors.get(fact.source_entity_uuid) if fact.source_entity_uuid is not None else None
        member = next((row for row in source.conditions
            if row.condition_uuid == fact.source_condition_uuid), None) if source else None
        if member is not None and source is not None:
            return bind_condition_response(event.uuid, source.uuid, member,
                "damage_requested" if fact.stage == "taken" else "damage_applied",
                start_ms, recipes, recipient_uuid=fact.target_entity_uuid)
    return None


def bind_received_damage_responses(event: PlayerNode, actors: Mapping[UUID,PlayerActor], start_ms: float,
        recipes: Mapping[str,ConditionRecipe]) -> tuple[ConditionResponseCue,...]:
    fact = event.fact
    if event.canceled or not isinstance(fact,DamageFact) or fact.stage != 'applied':
        return ()
    actor = actors.get(fact.target_entity_uuid)
    if actor is None:
        return ()
    return tuple(cue for member in actor.conditions if member.state is not None
        and not member.state.suppression_provider_uuids and member.state.energy_type is fact.damage_type
        if (cue := bind_condition_response(event.uuid,actor.uuid,member,'damage_received',start_ms,recipes)) is not None)


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
    timing_evidence: tuple[TimingEvidence, ...] = ()


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
          for modifier in persistent.equipmentModifiers
          if recipe.classification.runtimeRole != "equipment_or_weapon_state" and not modifier.affectedItemOnly),
        *(f"Condition rig layer colors unsupported: {identity}/{layer.id}" for layer in persistent.appearanceLayers
          if layer.tint2 is not None or layer.tint3 is not None),
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
        if (member.category is ConditionCategory.INTERNAL
                or member.state is not None and member.state.suppression_provider_uuids):
            continue
        recipe = recipes.get(member.behavior_id) if member.behavior_id is not None else None
        if recipe is None:
            unsupported.append(f"Missing condition recipe: {member.behavior_id}")
        else:
            exact[recipe.definitionRef.identity_key] = recipe
            previous = owners.setdefault(recipe.definitionRef.identity_key, member.condition_uuid)
            if any(layer.markerGroup for layer in recipe.persistent.layers):
                owners[recipe.definitionRef.identity_key] = min(previous, member.condition_uuid, key=str)
    for owner, identity in extra_members:
        recipe = recipes.get(identity)
        if recipe is not None:
            exact[recipe.definitionRef.identity_key] = recipe
            previous = owners.setdefault(recipe.definitionRef.identity_key, owner)
            if any(layer.markerGroup for layer in recipe.persistent.layers):
                owners[recipe.definitionRef.identity_key] = min(previous, owner, key=str)
    ordered = sorted(exact.values(), key=lambda recipe: (
        -recipe.composition.priority, recipe.definitionRef.identity_key,
    ))
    claimed: set[str] = set()
    counts: dict[str, int] = {}
    selected: list[str] = []
    alpha, body, pose, label = 1.0, None, None, None
    scale = 1.
    copies, distortion, ramp = None, None, None
    frozen, outline = None, None
    pose_ref = frozen_ref = None
    outline_owner = frozen_owner = None
    layers: list[ResolvedConditionLayer] = []
    rig_layers: dict[tuple[str, str], ConditionRigLayer] = {}
    item_modifiers: list[ConditionItemModifier] = []
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
        for layer in sorted(persistent.appearanceLayers, key=lambda row: -row.priority):
            if layer.tint2 is None and layer.tint3 is None:
                rig_layers.setdefault((layer.slot, layer.category), ConditionRigLayer(layer, owner))
        member = facts.get(owner)
        if member is not None and member.state is not None:
            if member.state.affected_item_uuid is not None:
                item_modifiers.extend(ConditionItemModifier(member.state.affected_item_uuid, modifier)
                    for modifier in persistent.equipmentModifiers if modifier.affectedItemOnly)
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
        if frozen is None and persistent.frozenPose is not None:
            frozen = persistent.frozenPose
            frozen_ref = recipe.definitionRef
            frozen_owner = owner
        if outline is None and persistent.bodyOutline is not None:
            outline = persistent.bodyOutline
            outline_owner = owner
        alpha *= persistent.alphaMultiplier
        if body is None and persistent.bodyColor is not None:
            body = persistent.bodyColor
        if pose is None and persistent.bodyPose is not None:
            pose = persistent.bodyPose
            pose_ref = recipe.definitionRef
        if label is None and persistent.label is not None:
            label = persistent.label
        layers.extend(ResolvedConditionLayer(layer, media[layer.assetId], owners[recipe.definitionRef.identity_key])
                      for layer in persistent.layers if supported_layer(layer, media)
                      and (layer.whenEnergyType is None or member is not None and member.state is not None
                           and layer.whenEnergyType is member.state.energy_type)
                      and (layer.whenAbility is None or member is not None and member.state is not None
                           and layer.whenAbility == member.state.enhanced_ability)
                      and (layer.whenMetamagicMode is None or member is not None and member.state is not None
                           and layer.whenMetamagicMode == member.state.metamagic_mode)
                      and (layer.whenSizeChange is None or member is not None and member.state is not None
                           and layer.whenSizeChange == member.state.size_change))
        unsupported.extend(persistent_limitations(recipe, media))
    selected_layers = tuple(sorted(layers, key=lambda value: (-value.layer.priority, value.layer.id)))
    return ConditionAppearance(alpha, body, tuple(selected), tuple(dict.fromkeys(unsupported)), pose, label,
                               selected_layers, scale=scale, live_copies=copies, distortion=distortion, body_ramp=ramp,
                               frozen_pose=frozen, body_outline=outline, outline_owner_uuid=outline_owner,
                               body_pose_ref=pose_ref, frozen_pose_ref=frozen_ref, frozen_owner_uuid=frozen_owner,
                               rig_layers=tuple(rig_layers.values()), item_modifiers=tuple(item_modifiers))


def condition_contact(contact: ActorContact, appearance: ConditionAppearance | None) -> ActorContact:
    """Resolve one scale before drawing sockets/body; already resolved contacts are idempotent."""
    if appearance is None or contact.condition_scale == appearance.scale:
        return contact
    return replace(contact, visual_scale=contact.visual_scale / contact.condition_scale * appearance.scale,
                   condition_scale=appearance.scale)


def condition_body_pose(data: AnimationData, body: BodySample, contact: ActorContact,
                        appearance: ConditionAppearance | None) -> BodySample:
    """A retained condition replaces idle only; actions and death keep ownership."""
    if appearance is not None and appearance.frozen_pose is not None and contact.life_state is not LifeState.DEAD:
        pose = appearance.frozen_pose
        if pose.captureCurrent and appearance.frozen_body is not None:
            return appearance.frozen_body
        frame = pose.framesByRig.get(contact.rig_id, pose.frame)
        selected = (resolve_body_context(data, contact, "condition_hold",
            ContentBodyQualifier(contentRef=appearance.frozen_pose_ref)) if appearance.frozen_pose_ref is not None else None)
        clip = selected.actor.clip if selected is not None else pose.clip
        if selected is not None:
            assert selected.restFrame is not None
            frame = selected.restFrame
        if frame >= body_clip(data, contact, clip).frames:
            raise ValueError("frozen pose frame exceeds the registered clip")
        return replace(body, clip=clip, frame=frame)
    if (body.clip not in ("Idle", data.damage_context.bodyClip) or contact.life_state is LifeState.DEAD
            or appearance is None or appearance.body_pose is None):
        return body
    clip = appearance.body_pose
    # Resolve before reading the shared pose's metadata: an alternate body may
    # legitimately lack that source clip entirely.
    selected = None
    if appearance.body_pose_ref is not None:
        selected = resolve_body_context(data, contact, "condition_hold",
            ContentBodyQualifier(contentRef=appearance.body_pose_ref))
    if selected is not None and selected.restFrame is not None:
        return replace(body, clip=selected.actor.clip, frame=selected.restFrame)
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
    selected = resolve_body_context(data, contact, "condition_entry" if new is not None else "condition_exit",
        ContentBodyQualifier(contentRef=recipe.definitionRef), body_context(
            animation.bodyClip, animation.bodyPlaybackSpeed, reversed=animation.reversed))
    cue = compile_body_transition(data, contact, animation, body=selected)
    evidence = list(timeline.timing_evidence)
    previous = next((row for row in reversed(evidence) if row.target.anchor == 'complete'), None)
    complete = max(timeline.complete_ms, timeline.start_ms + cue.frames * 1000 / cue.fps)
    record_timing(evidence, TimingReference('event', timeline.event_uuid, 'complete'), 'condition_transition',
        (TimingOperand(TimingReference('event', timeline.event_uuid, 'complete'), timeline.complete_ms,
            producer_index=previous.index if previous is not None else None),
         TimingOperand(TimingReference('event', timeline.event_uuid, 'start'), timeline.start_ms,
            offset_ms=cue.frames * 1000 / cue.fps, authored_field='condition.selected_body.duration')), complete, 'maximum')
    return replace(timeline, body=cue, alpha_end_ms=timeline.complete_ms,
                   complete_ms=complete, timing_evidence=tuple(evidence))


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
    evidence: list[TimingEvidence] = []
    start_source = record_timing(evidence, TimingReference('event', event.uuid, 'start'), 'condition_transition',
        (TimingOperand(TimingReference('event', event.uuid, 'admission'), start_ms,
            offset_ms=override.delayMs if override is not None else 0,
            authored_field='spell.condition.delayMs' if override is not None else None),), start)
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
    appearance_duration = (transition.durationMs if
        {(row.layer.slot, row.layer.category) for row in old_appearance.rig_layers}
        != {(row.layer.slot, row.layer.category) for row in new_appearance.rig_layers} else 0.)
    if changed and recipe.persistent.absenceEcho is not None:
        appearance_duration = max(appearance_duration, transition.durationMs)
    unsupported = tuple(dict.fromkeys((
        *old_appearance.unsupported, *new_appearance.unsupported,
        *transition_limitations(recipe.definitionRef.content_id, transition, media),
    )))
    operands = [start_source,
        replace(start_source, offset_ms=alpha_duration, authored_field='condition.transition.durationMs'),
        replace(start_source, offset_ms=ramp_duration, authored_field='condition.persistent.bodyRamp'),
        replace(start_source, offset_ms=appearance_duration, authored_field='condition.appearance.transition.durationMs')]
    if changed and (applied or not media_activated and not change.consumed):
        operands.extend(replace(start_source, offset_ms=effect.startOffsetMs + effect.durationMs,
            authored_field=f'condition.transition.effects.{effect.id}') for effect in transition.effects)
    complete = start + max(alpha_duration, media_duration, ramp_duration, appearance_duration)
    record_timing(evidence, TimingReference('event', event.uuid, 'complete'), 'condition_transition',
        tuple(operands), complete, 'maximum')
    return ConditionTimeline(
        event.uuid, change.target_entity_uuid, start, complete,
        before, after, old_appearance, new_appearance,
        ("+" if applied else "−") + fact.name if feedback else None,
        transition.feedbackColor, badge_style, unsupported,
        alpha_end_ms=(start + alpha_duration
                      if abs(old_appearance.scale - new_appearance.scale) >= .001 else None),
        timing_evidence=tuple(evidence),
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
    old = {(row.layer.slot, row.layer.category): row for row in timeline.before_appearance.rig_layers}
    new = {(row.layer.slot, row.layer.category): row for row in timeline.after_appearance.rig_layers}
    appearance = replace(appearance, rig_layers=(
        *(replace(row, alpha=1. if key in old else eased) for key, row in new.items()),
        *(replace(row, alpha=1. - eased) for key, row in old.items() if key not in new and eased < 1.)))
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
            before = {(row.layer.slot, row.layer.category): row for row in timeline.before_appearance.rig_layers}
            after = {(row.layer.slot, row.layer.category): row for row in timeline.after_appearance.rig_layers}
            changed = before.keys() ^ after.keys()
            current = {(row.layer.slot, row.layer.category): row for row in result[actor].rig_layers}
            for row in sample.rig_layers:
                key = row.layer.slot, row.layer.category
                if key in changed and (key not in current or current[key].owner_uuid == row.owner_uuid):
                    current[key] = row
            result[actor] = replace(result[actor], alpha=sample.alpha, scale=sample.scale,
                                    rig_layers=tuple(current.values()))
    return result
