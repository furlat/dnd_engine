"""Local presentation dates derived from received membership, never native time.

Callers register each admitted head once. Sampling is pure and four cameras read
exactly the same dates. Initial/reacquired unknown effects enter their quiet loop.
"""

from dataclasses import dataclass, replace
from typing import Mapping
from types import MappingProxyType
from uuid import UUID

from dnd.core.events import EventType, SpatialChangeType
from dnd.core.creature_types import DamageType
from dnd.types.actor import SpatialDisposition
from game.animation_types import AnimationData, Facing8
from game.animation import BodySample
from game.body_pose_types import ActorPose
from game.body_presentation import sample_body_presentation
from game.choreography import BoundChoreography, MotionTimeline, walk_bound_timelines
from game.condition_animation import (ConditionAppearance, LiveCopyAppearance,
    ConditionResponseCue, condition_body_pose, resolve_condition_appearance)
from game.condition_media import ConditionLayerMedia, ResolvedConditionLayer, supported_layer
from game.condition_types import ConditionLayer, ConditionRecipe, ConditionTransitionEffect, ConditionLiveCopies
from game.player_facts import ConditionChangeFact, PlayerActor, PlayerLineage, PlayerState, SpatialFact, TemporaryHitPointsFact


@dataclass(frozen=True, slots=True)
class ConditionMediaLifetime:
    actor_uuid: UUID
    owner_uuid: UUID
    behavior_id: str
    applied_ms: float | None = None
    removed_ms: float | None = None
    # Selected media losing their last effective owner: persistent or finite.
    removed_layers: tuple[str, ...] = ()
    activated_ms: float | None = None
    initial_copy_count: int = 0
    copy_updates: tuple[tuple[float, int], ...] = ()
    responses: tuple[ConditionResponseCue, ...] = ()
    consumed_ms: float | None = None
    frozen_body: BodySample | None = None
    absence_pose: ActorPose | None = None
    returned_ms: float | None = None
    returned_pose: ActorPose | None = None
    energy_type: DamageType | None = None


def extra_media_members(actor: PlayerActor) -> tuple[tuple[UUID, str], ...]:
    grant = actor.temporary_hp_grant
    return ((grant.instance_uuid, grant.source_id),) if grant is not None and grant.source_id is not None else ()


def _removal_duration(media: ConditionLayerMedia, data: AnimationData) -> float:
    if media.removal_asset_id is not None:
        asset = data.projectile_assets[media.removal_asset_id]
        phase = asset.phases.impact
        assert phase is not None
        if phase.loop:
            raise ValueError("color release requires a finite bank")
        return phase.frames * 1000 / (phase.fps or asset.fps)
    if media.removal_mask_asset_id is None:
        return media.removal_fade_ms
    asset = data.projectile_assets[media.removal_mask_asset_id]
    phase = asset.phases.impact
    assert phase is not None
    return phase.frames * 1000 / (phase.fps or asset.fps)


def _media_assets(recipe: ConditionRecipe, data: AnimationData) -> tuple[str, ...]:
    copies = recipe.persistent.liveCopies
    tracks = (*recipe.persistent.layers, *recipe.application.effects, *recipe.removal.effects,
              *(recipe.activation.effects if recipe.activation is not None else ()),
              *(effect for response in recipe.responses for effect in response.effects),
              *( (*copies.layers, *copies.applicationEffects, *copies.removalEffects) if copies else ()))
    return tuple(dict.fromkeys(track.assetId for track in tracks
        if (media := data.condition_media.get(track.assetId)) is not None and media.asset_id is not None))


def _members(actor: PlayerActor, data: AnimationData) -> dict[UUID, str]:
    members = {member.condition_uuid: member.behavior_id for member in actor.conditions
               if member.behavior_id is not None}
    members.update(extra_media_members(actor))
    return {owner: identity for owner, identity in members.items()
            if (recipe := data.condition_recipes.get(identity)) is not None
            and (_media_assets(recipe, data) or recipe.persistent.liveCopies is not None
                 or recipe.persistent.bodyDistortion is not None or recipe.persistent.bodyScale is not None
                 or recipe.persistent.bodyRamp is not None or recipe.persistent.bodyOutline is not None
                 or recipe.persistent.frozenPose is not None or recipe.persistent.absenceEcho is not None)}


def _effective_assets(recipe: ConditionRecipe, data: AnimationData,
                      appearance: ConditionAppearance, owner: UUID) -> tuple[str, ...]:
    selected = tuple(layer.layer.assetId for layer in appearance.layers if layer.owner_uuid == owner)
    persistent = {layer.assetId for layer in recipe.persistent.layers}
    return tuple(dict.fromkeys((*selected, *(asset for asset in _media_assets(recipe, data)
                                             if asset not in persistent))))


def _state_edges(before: PlayerState, states: tuple[tuple[float, PlayerState], ...],
                 data: AnimationData) -> list[tuple[float, UUID, UUID, str, bool, tuple[str, ...]]]:
    result = []
    prior = before
    for at, state in states:
        for actor_id, actor in state.actors.items():
            old = _members(prior.actors[actor_id], data) if actor_id in prior.actors else {}
            new = _members(actor, data)
            removed = old.keys() - new.keys()
            appearance = (resolve_condition_appearance(prior.actors[actor_id].conditions,
                data.condition_recipes, data.condition_media, extra_members=extra_media_members(prior.actors[actor_id]))
                if removed else ConditionAppearance())
            selected_owners: dict[str, UUID] = {}
            for owner, identity in old.items():
                if identity in appearance.matched_behavior_ids:
                    selected_owners.setdefault(identity, owner)
            result.extend((at, actor_id, owner, old[owner], False,
                _effective_assets(data.condition_recipes[old[owner]], data, appearance, owner)
                if old[owner] not in new.values() and selected_owners.get(old[owner]) == owner else ())
                for owner in removed)
            result.extend((at, actor_id, owner, new[owner], True, ()) for owner in new.keys() - old.keys())
        prior = state
    return result


def register_condition_lifetimes(
    retained: Mapping[UUID, ConditionMediaLifetime], before: PlayerState, data: AnimationData,
    *, absolute_start_ms: float, lineage: PlayerLineage | None = None,
    choreography: BoundChoreography | None = None, motion: MotionTimeline | None = None,
    facings: Mapping[str, Facing8] = MappingProxyType({}),
) -> dict[UUID, ConditionMediaLifetime]:
    current = {owner: (actor.uuid, identity) for actor in before.actors.values()
               for owner, identity in _members(actor, data).items()}
    energies = {member.condition_uuid: member.state.energy_type for actor in before.actors.values()
        for member in actor.conditions if member.state is not None}
    if lineage is not None:
        energies.update({node.fact.condition.condition_uuid: node.fact.condition.state.energy_type
            for node in lineage.events if isinstance(node.fact,ConditionChangeFact)
            and node.fact.condition.state is not None})
    # Retain only live memberships and unfinished tails at head admission.
    # Prior mappings remain untouched, so a retained older head is still seekable.
    result = {}
    for owner, lifetime in retained.items():
        recipe = data.condition_recipes[lifetime.behavior_id]
        fade_ms = max((*(_removal_duration(data.condition_media[asset], data)
                         for asset in lifetime.removed_layers),
                       max((effect.startOffsetMs + effect.durationMs for effect in recipe.removal.effects), default=0.),
                       recipe.removal.durationMs if recipe.persistent.bodyDistortion else 0.,
                       recipe.persistent.bodyRamp.removalMs if recipe.persistent.bodyRamp else 0.,
                       max(recipe.persistent.liveCopies.dissipateMs,
                           max((effect.startOffsetMs + effect.durationMs
                               for effect in recipe.persistent.liveCopies.removalEffects), default=0.))
                           if recipe.persistent.liveCopies else 0.))
        responses = tuple(cue for cue in lifetime.responses if cue.end_ms > absolute_start_ms)
        echo = recipe.persistent.absenceEcho
        if echo is not None:
            fade_ms = max(fade_ms, echo.returnPortalMs, echo.clearMs)
        pending_return = (echo is not None and lifetime.returned_ms is None
            and lifetime.actor_uuid in before.actors
            and before.actors[lifetime.actor_uuid].spatial_disposition in
                (SpatialDisposition.ABSENT, SpatialDisposition.RETURN_PENDING))
        if (owner in current or lifetime.removed_ms is None or responses
                or pending_return or lifetime.returned_ms is not None and echo is not None
                and absolute_start_ms < lifetime.returned_ms+echo.returnPortalMs
                or absolute_start_ms < lifetime.removed_ms + fade_ms):
            result[owner] = replace(lifetime, responses=responses)
    for owner, (actor_id, identity) in current.items():
        member = next((row for row in before.actors[actor_id].conditions if row.condition_uuid == owner), None)
        count = member.state.duplicate_count if member is not None and member.state is not None else None
        result.setdefault(owner, ConditionMediaLifetime(actor_id, owner, identity, initial_copy_count=count or 0,
            energy_type=energies.get(owner)))
    applications = set()
    consumed = set()
    witnessed_entries = set()
    if lineage is not None:
        for node in lineage.events:
            if node.canceled:
                continue
            fact = node.fact
            if isinstance(fact, SpatialFact) and fact.change_type is SpatialChangeType.ENTITY_ENTERED:
                witnessed_entries.add(fact.entity_uuid)
            if isinstance(fact, ConditionChangeFact) and fact.consumed:
                consumed.add(fact.condition.condition_uuid)
            if isinstance(fact, ConditionChangeFact) and fact.event_type is EventType.CONDITION_APPLICATION:
                applications.add(fact.condition.condition_uuid)
            elif isinstance(fact, TemporaryHitPointsFact) and fact.grant is not None:
                applications.add(fact.grant.instance_uuid)
    visits = tuple(walk_bound_timelines(choreography, motion))
    edges = [(at + visit.offset_ms, actor, owner, identity, added, layers)
             for visit in visits for at, actor, owner, identity, added, layers
             in _state_edges(visit.timeline.before, visit.timeline.states, data)]
    # Nested timelines can publish the same received membership. Stable owners
    # are initialized once; duplicate views of that transition never restart it.
    for at, actor, owner, identity, added, layers in sorted(set(edges), key=lambda row: (row[0], row[4])):
        absolute = absolute_start_ms + at
        previous = result.get(owner)
        if added:
            if previous is None:
                overlapping = next((row for row in result.values()
                    if row.actor_uuid == actor and row.behavior_id == identity
                    and (row.removed_ms is None or row.removed_ms >= absolute)), None)
                result[owner] = ConditionMediaLifetime(actor, owner, identity,
                    overlapping.applied_ms if overlapping is not None else
                    absolute if owner in applications else None,
                    activated_ms=overlapping.activated_ms if overlapping is not None else None,
                    energy_type=energies.get(owner))
        elif previous is not None and previous.removed_ms is None:
            result[owner] = replace(previous, removed_ms=absolute, removed_layers=layers,
                consumed_ms=absolute if owner in consumed else previous.consumed_ms)
    turns = ((at + visit.offset_ms, actor) for visit in visits
             if isinstance(visit.timeline, BoundChoreography) for at, actor in visit.timeline.turn_starts)
    for at, actor_id in turns:
        absolute = absolute_start_ms + at
        for owner, lifetime in tuple(result.items()):
            if (lifetime.actor_uuid == actor_id and lifetime.activated_ms is None
                    and (lifetime.applied_ms is None or lifetime.applied_ms <= absolute)
                    and (lifetime.removed_ms is None or lifetime.removed_ms > absolute)
                    and data.condition_recipes[lifetime.behavior_id].activation is not None):
                result[owner] = replace(lifetime, activated_ms=absolute)
    conditions = ((row.start_ms + visit.offset_ms, row) for visit in visits
                  if isinstance(visit.timeline, BoundChoreography) for row in visit.timeline.conditions)
    for at, timeline in sorted(conditions, key=lambda row: row[0]):
        for member in timeline.after_membership:
            if member.state is None or member.state.duplicate_count is None:
                continue
            lifetime = result.get(member.condition_uuid)
            if lifetime is None:
                continue
            count = member.state.duplicate_count
            if (absolute_start_ms + at, count) in lifetime.copy_updates:
                continue
            previous_count = lifetime.copy_updates[-1][1] if lifetime.copy_updates else lifetime.initial_copy_count
            if count != previous_count:
                result[member.condition_uuid] = replace(lifetime,
                    copy_updates=(*lifetime.copy_updates, (absolute_start_ms + at, count)))
    responses = (replace(cue, start_ms=visit.offset_ms + cue.start_ms) for visit in visits
                 if isinstance(visit.timeline, BoundChoreography) for cue in visit.timeline.condition_responses)
    for cue in responses:
        absolute = replace(cue, start_ms=absolute_start_ms + cue.start_ms)
        lifetime = result.get(cue.owner_uuid) or ConditionMediaLifetime(
            cue.actor_uuid, cue.owner_uuid, cue.behavior_id, removed_ms=absolute.start_ms)
        if any(previous.event_uuid == cue.event_uuid for previous in lifetime.responses):
            continue
        result[cue.owner_uuid] = replace(lifetime, responses=(*lifetime.responses, absolute),
            consumed_ms=absolute.start_ms if cue.trigger == "consumed" else lifetime.consumed_ms)
    for owner, lifetime in tuple(result.items()):
        echo = data.condition_recipes[lifetime.behavior_id].persistent.absenceEcho
        if echo is not None:
            if lifetime.absence_pose is None and owner not in retained and lifetime.applied_ms is not None:
                when = lifetime.applied_ms
                frame = sample_body_presentation(before,None,data,max(0.,when-absolute_start_ms-.001),
                    max(0.,when-.001),facings,choreography=choreography,motion=motion)
                pose = next((row for row in frame.poses if row.body.actor_uuid == str(lifetime.actor_uuid)),None)
                lifetime = replace(lifetime,absence_pose=pose)
            # Later sight can replace an old absent snapshot with a present one.
            # Only a received entry admits a return, never that reacquisition.
            if lifetime.returned_ms is None and lifetime.actor_uuid in witnessed_entries:
                for visit in visits:
                    prior = visit.timeline.before
                    for at,state in visit.timeline.states:
                        old,new = prior.actors.get(lifetime.actor_uuid),state.actors.get(lifetime.actor_uuid)
                        if (old is not None and new is not None and old.spatial_disposition in echo.dispositions
                                and new.spatial_disposition is SpatialDisposition.PRESENT):
                            when = absolute_start_ms+visit.offset_ms+at
                            frame = sample_body_presentation(state,None,data,0,when,facings)
                            pose = next((row for row in frame.poses if row.body.actor_uuid == str(lifetime.actor_uuid)),None)
                            if pose is not None:
                                lifetime = replace(lifetime,returned_ms=when,returned_pose=pose)
                                break
                        prior=state
                    if lifetime.returned_ms is not None:
                        break
            result[owner]=lifetime
        freeze = data.condition_recipes[lifetime.behavior_id].persistent.frozenPose
        if freeze is None or not freeze.captureCurrent or lifetime.frozen_body is not None or owner in retained:
            continue
        when = lifetime.applied_ms if lifetime.applied_ms is not None else absolute_start_ms
        # A hidden onset keeps its authored quiet fallback; unrelated later heads
        # cannot recapture it as a different pose.
        overlapping = next((row.frozen_body for row in result.values()
            if row.actor_uuid == lifetime.actor_uuid and row.frozen_body is not None
            and (row.applied_ms is None or row.applied_ms <= when)
            and (row.removed_ms is None or row.removed_ms > when)), None)
        local = max(0., when - absolute_start_ms - .001)
        pose = None
        if overlapping is None:
            frame = sample_body_presentation(before, None, data, local, max(0., when - .001), facings,
                choreography=choreography, motion=motion)
            sampled = next((row for row in frame.poses if row.body.actor_uuid == str(lifetime.actor_uuid)), None)
            if sampled is not None:
                actor = frame.displayed.actors.get(lifetime.actor_uuid)
                prior = (resolve_condition_appearance(tuple(member for member in actor.conditions
                    if member.condition_uuid != owner), data.condition_recipes, data.condition_media,
                    extra_members=extra_media_members(actor)) if actor is not None else sampled.actor.condition)
                prior = sample_condition_lifetimes({str(lifetime.actor_uuid): prior}, result, data,
                    max(0., when - .001))[str(lifetime.actor_uuid)]
                pose = condition_body_pose(data, sampled.body, sampled.actor.contact, prior)
        result[owner] = replace(lifetime, frozen_body=overlapping or pose)
    return result


def _transition_layers(effects: tuple[ConditionTransitionEffect, ...], lifetime: ConditionMediaLifetime,
                       age_ms: float, data: AnimationData) -> tuple[ResolvedConditionLayer, ...]:
    result = []
    for effect in effects:
        if effect.whenEnergyType is not None and effect.whenEnergyType is not lifetime.energy_type:
            continue
        if not effect.startOffsetMs <= age_ms < effect.startOffsetMs + effect.durationMs:
            continue
        media = data.condition_media.get(effect.assetId)
        if media is None or media.asset_id is None:
            continue
        asset = data.projectile_assets[media.asset_id]
        phase = asset.phases.impact
        assert phase is not None
        layer = ConditionLayer(id=effect.id, assetId=effect.assetId, category=effect.category,
            animation=effect.animation, fps=phase.fps or asset.fps, attachment=effect.attachment,
            offsetX=effect.offsetX, offsetY=effect.offsetY,
            opacity=effect.opacity,
            activeDuring=("idle", "move", "jump", "forced_move", "attack", "cast", "act", "hit"),
            priority=effect.priority, colors=effect.colors, drawOrder=effect.drawOrder, lifeStates=effect.lifeStates)
        result.append(ResolvedConditionLayer(layer, media, lifetime.owner_uuid,
            age_ms - effect.startOffsetMs, finite=True))
    return tuple(result)


def sample_condition_lifetimes(
    appearances: Mapping[str, ConditionAppearance], records: Mapping[UUID, ConditionMediaLifetime],
    data: AnimationData, absolute_ms: float,
) -> dict[str, ConditionAppearance]:
    """Phase only the displayed memberships, plus a finite removed-layer fade."""
    result = {}
    for actor_id, appearance in appearances.items():
        layers = []
        for layer in appearance.layers:
            lifetime = records.get(layer.owner_uuid) if layer.owner_uuid is not None else None
            start = lifetime.applied_ms if lifetime is not None else None
            if lifetime is not None and lifetime.consumed_ms is not None and absolute_ms >= lifetime.consumed_ms:
                continue
            if lifetime is not None and lifetime.activated_ms is not None and absolute_ms >= lifetime.activated_ms:
                continue
            layers.append(replace(layer, age_ms=max(0., absolute_ms - start) if start is not None else absolute_ms,
                                  application=start is not None))
        present = {layer.layer.assetId for layer in layers}
        displayed_recipes: set[str] = set()
        for lifetime in records.values():
            end = lifetime.removed_ms
            for cue in lifetime.responses:
                if cue.start_ms <= absolute_ms < cue.end_ms:
                    selected = tuple(effect for effect in cue.effects
                        if str(cue.recipient_uuid if effect.participant == "recipient" else cue.actor_uuid) == actor_id)
                    layers.extend(_transition_layers(selected, lifetime, absolute_ms - cue.start_ms, data))
            if str(lifetime.actor_uuid) != actor_id:
                continue
            if lifetime.consumed_ms is not None and absolute_ms >= lifetime.consumed_ms:
                continue
            recipe = data.condition_recipes[lifetime.behavior_id]
            active = end is None or absolute_ms < end
            activated = lifetime.activated_ms
            if activated is not None and absolute_ms >= activated and recipe.activation is not None:
                layers.extend(_transition_layers(recipe.activation.effects, lifetime, absolute_ms - activated, data))
                continue
            if active:
                if lifetime.behavior_id in appearance.matched_behavior_ids and lifetime.behavior_id not in displayed_recipes:
                    displayed_recipes.add(lifetime.behavior_id)
                    if lifetime.applied_ms is not None and absolute_ms >= lifetime.applied_ms:
                        layers.extend(_transition_layers(recipe.application.effects, lifetime,
                                                         absolute_ms - lifetime.applied_ms, data))
                continue
            if end is None or not lifetime.removed_layers or lifetime.behavior_id in appearance.matched_behavior_ids:
                continue
            layers.extend(_transition_layers(recipe.removal.effects, lifetime, absolute_ms - end, data))
            for layer in recipe.persistent.layers:
                if (layer.assetId not in lifetime.removed_layers or layer.assetId in present
                        or not supported_layer(layer, data.condition_media)):
                    continue
                media = data.condition_media[layer.assetId]
                duration = _removal_duration(media, data)
                if media.asset_id is None or not end <= absolute_ms < end + duration:
                    continue
                start = lifetime.applied_ms
                color_release = media.removal_asset_id is not None
                clock = end if color_release else absolute_ms
                layers.append(ResolvedConditionLayer(layer, media, lifetime.owner_uuid,
                    max(0., clock - start) if start is not None else clock,
                    start is not None, 1. if media.removal_mask_asset_id or color_release else 1 - (absolute_ms - end) / duration,
                    fade_in_age_ms=max(0., end - start - layer.startOffsetMs) if start is not None else None,
                    removal_age_ms=absolute_ms - end))
        copies = appearance.live_copies
        distortion = appearance.distortion
        distortion_strength = 1.
        ramp, ramp_strength = appearance.body_ramp, 1.
        ramp_age = absolute_ms
        frozen_lifetime = records.get(appearance.frozen_owner_uuid) if appearance.frozen_owner_uuid else None
        frozen_body = (frozen_lifetime.frozen_body if frozen_lifetime is not None
            and (frozen_lifetime.applied_ms is None or frozen_lifetime.applied_ms <= absolute_ms)
            and (frozen_lifetime.removed_ms is None or absolute_ms < frozen_lifetime.removed_ms) else None)
        for lifetime in records.values():
            authored = data.condition_recipes[lifetime.behavior_id]
            if str(lifetime.actor_uuid) != actor_id:
                continue
            material = authored.persistent.bodyRamp
            if material is not None:
                if (ramp == material and lifetime.applied_ms is not None and lifetime.applied_ms <= absolute_ms
                        and (lifetime.removed_ms is None or absolute_ms < lifetime.removed_ms)):
                    ramp_age = absolute_ms - lifetime.applied_ms
                    ramp_strength = (min(1., max(0., (absolute_ms - lifetime.applied_ms) / material.applicationMs))
                                     if material.applicationMs else 1.)
                if (ramp is None and lifetime.behavior_id not in appearance.matched_behavior_ids
                        and lifetime.removed_ms is not None
                        and lifetime.removed_ms <= absolute_ms < lifetime.removed_ms + material.removalMs):
                    ramp = material
                    ramp_age = absolute_ms - lifetime.applied_ms if lifetime.applied_ms is not None else absolute_ms
                    ramp_strength = 1 - (absolute_ms - lifetime.removed_ms) / material.removalMs
            if authored.persistent.bodyDistortion is not None:
                if (distortion is not None and lifetime.applied_ms is not None
                        and (lifetime.removed_ms is None or absolute_ms < lifetime.removed_ms)):
                    duration = authored.application.durationMs
                    distortion_strength = min(1., max(0., (absolute_ms - lifetime.applied_ms) / duration)) if duration else 1.
                if (lifetime.behavior_id not in appearance.matched_behavior_ids and lifetime.removed_ms is not None
                        and lifetime.removed_ms <= absolute_ms < lifetime.removed_ms + authored.removal.durationMs):
                    distortion = authored.persistent.bodyDistortion
                    distortion_strength = 1 - (absolute_ms - lifetime.removed_ms) / authored.removal.durationMs
            recipe = authored.persistent.liveCopies
            if recipe is None:
                continue
            if copies is not None and copies.owner_uuid != lifetime.owner_uuid:
                continue
            if copies is None and lifetime.removed_ms is None:
                continue
            sampled = _sample_copies(lifetime, recipe, absolute_ms, data)
            if sampled.slots:
                copies = sampled
        outline_lifetime = records.get(appearance.outline_owner_uuid) if appearance.outline_owner_uuid is not None else None
        outline_start = outline_lifetime.applied_ms if outline_lifetime is not None else None
        outline_age = max(0., absolute_ms - outline_start) if outline_start is not None else None
        result[actor_id] = replace(appearance, layers=tuple(layers), live_copies=copies, time_ms=absolute_ms,
                                  outline_age_ms=outline_age,
                                  distortion=distortion, distortion_strength=distortion_strength,
                                  body_ramp=ramp, ramp_strength=ramp_strength, ramp_age_ms=ramp_age,
                                  frozen_body=frozen_body)
    return result


def _sample_copies(lifetime: ConditionMediaLifetime, recipe: ConditionLiveCopies,
                   now: float, data: AnimationData) -> LiveCopyAppearance:
    """Stable slots emerge once and disappear at their actual native count changes."""
    slots = []
    slot_layers = []
    updates = lifetime.copy_updates
    if lifetime.removed_ms is not None:
        updates = (*updates, (lifetime.removed_ms, 0))
    final_count = lifetime.initial_copy_count
    tail_ms = max(recipe.dissipateMs,
                  max((effect.startOffsetMs + effect.durationMs for effect in recipe.removalEffects), default=0.))
    for at, count in updates:
        if at <= now:
            final_count = count
    for index in range(len(recipe.slots)):
        live = index < lifetime.initial_copy_count
        born = lifetime.applied_ms if live else None
        removed = None
        for at, count in updates:
            if at > now:
                break
            next_live = index < count
            if next_live and not live:
                born, removed = at, None
            elif live and not next_live:
                removed = at
            live = next_live
        if not live and (removed is None or now >= removed + tail_ms):
            continue
        if born is not None and now < born:
            continue
        emerge = min(1., (now - born) / recipe.emergeMs) if born is not None and recipe.emergeMs else 1.
        fraction = 1. - (1. - emerge) ** 3
        alpha = (max(0., 1. - (now - removed) / recipe.dissipateMs)
                 if removed is not None and recipe.dissipateMs else emerge)
        slots.append((index, fraction, alpha))
        layers = tuple(ResolvedConditionLayer(layer, data.condition_media[layer.assetId], lifetime.owner_uuid,
            max(0., now - born) if born is not None else now, born is not None)
            for layer in recipe.layers if supported_layer(layer, data.condition_media))
        if born is not None:
            layers = (*layers, *_transition_layers(recipe.applicationEffects, lifetime, now - born, data))
        if removed is not None:
            layers = (*layers, *_transition_layers(recipe.removalEffects, lifetime, now - removed, data))
        slot_layers.append((index, layers))
    return LiveCopyAppearance(recipe, lifetime.owner_uuid, final_count, tuple(slots), tuple(slot_layers))
