"""Local presentation dates derived from received membership, never native time.

Callers register each admitted head once. Sampling is pure and four cameras read
exactly the same dates. Initial/reacquired unknown effects enter their quiet loop.
"""

from dataclasses import dataclass, replace
from typing import Mapping
from uuid import UUID

from dnd.core.events import EventType
from game.animation_types import AnimationData
from game.choreography import BoundChoreography, MotionTimeline
from game.condition_animation import ConditionAppearance, ConditionTimeline, LiveCopyAppearance, resolve_condition_appearance
from game.condition_media import ConditionLayerMedia, ResolvedConditionLayer, supported_layer
from game.condition_types import ConditionLayer, ConditionRecipe, ConditionTransitionEffect, ConditionLiveCopies
from game.player_facts import ConditionChangeFact, PlayerActor, PlayerLineage, PlayerState, TemporaryHitPointsFact


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


def extra_media_members(actor: PlayerActor) -> tuple[tuple[UUID, str], ...]:
    grant = actor.temporary_hp_grant
    return ((grant.instance_uuid, grant.source_id),) if grant is not None and grant.source_id is not None else ()


def _removal_duration(media: ConditionLayerMedia, data: AnimationData) -> float:
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
                 or recipe.persistent.bodyDistortion is not None or recipe.persistent.bodyScale is not None)}


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


def _group_edges(group: BoundChoreography, data: AnimationData,
                 offset: float = 0) -> list[tuple[float, UUID, UUID, str, bool, tuple[str, ...]]]:
    result = [(at + offset, actor, owner, identity, added, layers)
              for at, actor, owner, identity, added, layers in _state_edges(group.before, group.states, data)]
    for movement in group.movements:
        result.extend(_motion_edges(movement.timeline, data, offset + movement.start_ms))
    return result


def _motion_edges(motion: MotionTimeline, data: AnimationData,
                  offset: float = 0) -> list[tuple[float, UUID, UUID, str, bool, tuple[str, ...]]]:
    result = [(at + offset, actor, owner, identity, added, layers)
              for at, actor, owner, identity, added, layers in _state_edges(motion.before, motion.states, data)]
    for reaction in motion.reactions:
        result.extend(_group_edges(reaction.choreography, data, offset + reaction.start_ms))
    return result


def register_condition_lifetimes(
    retained: Mapping[UUID, ConditionMediaLifetime], before: PlayerState, data: AnimationData,
    *, absolute_start_ms: float, lineage: PlayerLineage | None = None,
    choreography: BoundChoreography | None = None, motion: MotionTimeline | None = None,
) -> dict[UUID, ConditionMediaLifetime]:
    current = {owner: (actor.uuid, identity) for actor in before.actors.values()
               for owner, identity in _members(actor, data).items()}
    # Retain only live memberships and unfinished tails at head admission.
    # Prior mappings remain untouched, so a retained older head is still seekable.
    result = {}
    for owner, lifetime in retained.items():
        recipe = data.condition_recipes[lifetime.behavior_id]
        fade_ms = max((*(_removal_duration(data.condition_media[asset], data)
                         for asset in lifetime.removed_layers),
                       max((effect.startOffsetMs + effect.durationMs for effect in recipe.removal.effects), default=0.),
                       recipe.removal.durationMs if recipe.persistent.bodyDistortion else 0.,
                       max(recipe.persistent.liveCopies.dissipateMs,
                           max((effect.startOffsetMs + effect.durationMs
                               for effect in recipe.persistent.liveCopies.removalEffects), default=0.))
                           if recipe.persistent.liveCopies else 0.))
        if (owner in current or lifetime.removed_ms is None
                or absolute_start_ms < lifetime.removed_ms + fade_ms):
            result[owner] = lifetime
    for owner, (actor_id, identity) in current.items():
        member = next((row for row in before.actors[actor_id].conditions if row.condition_uuid == owner), None)
        count = member.state.duplicate_count if member is not None and member.state is not None else None
        result.setdefault(owner, ConditionMediaLifetime(actor_id, owner, identity, initial_copy_count=count or 0))
    applications = set()
    if lineage is not None:
        for node in lineage.events:
            fact = node.fact
            if isinstance(fact, ConditionChangeFact) and fact.event_type is EventType.CONDITION_APPLICATION:
                applications.add(fact.condition.condition_uuid)
            elif isinstance(fact, TemporaryHitPointsFact) and fact.grant is not None:
                applications.add(fact.grant.instance_uuid)
    edges = (_motion_edges(motion, data) if motion is not None else
             _group_edges(choreography, data) if choreography is not None else [])
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
                    activated_ms=overlapping.activated_ms if overlapping is not None else None)
        elif previous is not None and previous.removed_ms is None:
            result[owner] = replace(previous, removed_ms=absolute, removed_layers=layers)
    turns = (_motion_turns(motion) if motion is not None else
             _group_turns(choreography) if choreography is not None else ())
    for at, actor_id in turns:
        absolute = absolute_start_ms + at
        for owner, lifetime in tuple(result.items()):
            if (lifetime.actor_uuid == actor_id and lifetime.activated_ms is None
                    and (lifetime.applied_ms is None or lifetime.applied_ms <= absolute)
                    and (lifetime.removed_ms is None or lifetime.removed_ms > absolute)
                    and data.condition_recipes[lifetime.behavior_id].activation is not None):
                result[owner] = replace(lifetime, activated_ms=absolute)
    conditions = (_motion_conditions(motion) if motion is not None else
                  _group_conditions(choreography) if choreography is not None else ())
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
    return result


def _group_conditions(group: BoundChoreography, offset: float = 0) -> tuple[tuple[float, ConditionTimeline], ...]:
    return (*( (offset + row.start_ms, row) for row in group.conditions),
            *(row for cue in group.movements for row in _motion_conditions(cue.timeline, offset + cue.start_ms)))


def _motion_conditions(motion: MotionTimeline, offset: float = 0) -> tuple[tuple[float, ConditionTimeline], ...]:
    return tuple(row for reaction in motion.reactions
                 for row in _group_conditions(reaction.choreography, offset + reaction.start_ms))


def _group_turns(group: BoundChoreography, offset: float = 0) -> tuple[tuple[float, UUID], ...]:
    return (*( (at + offset, actor) for at, actor in group.turn_starts),
            *(row for cue in group.movements for row in _motion_turns(cue.timeline, offset + cue.start_ms)))


def _motion_turns(motion: MotionTimeline, offset: float = 0) -> tuple[tuple[float, UUID], ...]:
    return tuple(row for reaction in motion.reactions
                 for row in _group_turns(reaction.choreography, offset + reaction.start_ms))


def _transition_layers(effects: tuple[ConditionTransitionEffect, ...], lifetime: ConditionMediaLifetime,
                       age_ms: float, data: AnimationData) -> tuple[ResolvedConditionLayer, ...]:
    result = []
    for effect in effects:
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
            if lifetime is not None and lifetime.activated_ms is not None and absolute_ms >= lifetime.activated_ms:
                continue
            layers.append(replace(layer, age_ms=max(0., absolute_ms - start) if start is not None else absolute_ms,
                                  application=start is not None))
        present = {layer.layer.assetId for layer in layers}
        displayed_recipes: set[str] = set()
        for lifetime in records.values():
            end = lifetime.removed_ms
            if str(lifetime.actor_uuid) != actor_id:
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
                layers.append(ResolvedConditionLayer(layer, media, lifetime.owner_uuid,
                    max(0., absolute_ms - start) if start is not None else absolute_ms,
                    start is not None, 1. if media.removal_mask_asset_id else 1 - (absolute_ms - end) / duration,
                    fade_in_age_ms=max(0., end - start - layer.startOffsetMs) if start is not None else None,
                    removal_age_ms=absolute_ms - end if media.removal_mask_asset_id else None))
        copies = appearance.live_copies
        distortion = appearance.distortion
        distortion_strength = 1.
        for lifetime in records.values():
            authored = data.condition_recipes[lifetime.behavior_id]
            if str(lifetime.actor_uuid) != actor_id:
                continue
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
        result[actor_id] = replace(appearance, layers=tuple(layers), live_copies=copies, time_ms=absolute_ms,
                                  distortion=distortion, distortion_strength=distortion_strength)
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
