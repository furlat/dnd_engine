"""Finite terrain contacts from disclosed entries and applied damage facts."""

from typing import Literal, Mapping
from math import atan2, pi, sqrt
from uuid import UUID

from dnd.core.events import SpatialChangeType
from dnd.core.presentation_geometry import SpherePresentationGeometry
from dnd.types.world import OccupancyLayer
from game.animation import ActorContact
from game.animation_types import AnimationData, StudioMediaTrack, Facing8
from game.combat import BoundCast, actor_contact, actor_is_visible
from game.player_facts import DamageFact, PlayerNode, PlayerState, SpatialFact
from game.stationary_media import StationaryMediaCue


def bind_suppression_media(bound: BoundCast, event_uuid: UUID, at_ms: float,
                           contact_ms: float) -> tuple[StationaryMediaCue, ...]:
    """One authored shell response per disclosed native provider and cast."""
    timeline, cues = bound.timeline, []
    source, data = timeline.source, timeline.data
    incoming = (source.ground_target.grid if source.ground_target is not None else
                source.emitter.grid if source.emitter is not None else source.caster.grid)
    for identity, effect in source.protections:
        geometry = effect.area_geometry
        binding = data.spatial_media.get(effect.content_ref.content_id)
        if binding is None or not isinstance(geometry, SpherePresentationGeometry):
            continue
        facing: Facing8 = "E"
        if binding.suppressionDirection is not None:
            authored = binding.suppressionDirection
            dx, dy = incoming[0] - geometry.center[0], incoming[1] - geometry.center[1]
            rotation = round((atan2(dy, dx) - atan2(authored.y, authored.x)) / (pi / 2)) if dx or dy else 0
            banks: tuple[Facing8, ...] = ("E", "S", "W", "N")
            facing = banks[(-rotation) % 4]
        for layer in binding.layers:
            if layer.suppressionAssetId is None:
                continue
            track = StudioMediaTrack(id=f"suppression:{identity}:{layer.side}",
                assetId=layer.suppressionAssetId, assetPhase=binding.assetPhase,
                attachment="area_ground", scale=binding.scale)
            cues.append(StationaryMediaCue(event_uuid, track, geometry.center,
                effect.anchor_elevation_steps or 0, facing, at_ms + contact_ms, data,
                {"rear": -1, "center": 0, "front": 1}[layer.side] * geometry.radius_feet / 5 / sqrt(2)))
    return tuple(cues)


def ground_contact_is_authored(state: PlayerState, fact: SpatialFact, data: AnimationData) -> bool:
    """Cheap admission before compiling an otherwise consequence-free entry."""
    return (fact.change_type is SpatialChangeType.ENTITY_ENTERED
        and fact.occupancy_layer is OccupancyLayer.GROUND and state.senses is not None
        and any(fact.position in effect.positions
                and (binding := data.spatial_media.get(effect.content_ref.content_id)) is not None
                and "ground_entry" in binding.contactMedia
                for effect in state.senses.spatial_effects.values()))


def bind_spatial_contacts(state: PlayerState, event: PlayerNode, data: AnimationData,
                          at_ms: float, contacts: Mapping[str, ActorContact]) -> tuple[StationaryMediaCue, ...]:
    """Known area identity never makes an unseen floor contact visible."""
    senses, fact = state.senses, event.fact
    if senses is None:
        return ()
    trigger: Literal["ground_entry", "damage"]
    if isinstance(fact, SpatialFact) and ground_contact_is_authored(state, fact, data):
        identity, position, effect_id, trigger = fact.entity_uuid, fact.position, None, "ground_entry"
    elif (isinstance(fact, DamageFact) and fact.stage == "applied"
          and fact.applied_damage is not None and fact.applied_damage > 0 and fact.effect_id is not None):
        identity, position, effect_id, trigger = fact.target_entity_uuid, None, fact.effect_id, "damage"
    else:
        return ()
    actor = state.actors.get(identity) if identity is not None else None
    if actor is None or not actor_is_visible(state, actor):
        return ()
    contact = contacts.get(str(identity)) or actor_contact(state, actor, data)
    position = position or contact.grid
    cell = round(position[0]), round(position[1])
    if cell not in senses.visible or cell not in state.tiles:
        return ()
    cues = {}
    for effect in senses.spatial_effects.values():
        if cell not in effect.positions or effect_id is not None and effect.content_ref.identity_key != effect_id:
            continue
        binding = data.spatial_media.get(effect.content_ref.content_id)
        track = binding.contactMedia.get(trigger) if binding is not None else None
        if track is None:
            continue
        # Several observed owners of the same content do not duplicate one
        # actual damage packet. The victim's disclosed contact owns this media.
        cues[track.id] = StationaryMediaCue(event.uuid, track, position, state.tiles[cell].elevation_steps,
            contact.facing, at_ms+track.startOffsetMs, data)
    return tuple(cues.values())
