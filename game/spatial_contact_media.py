"""Finite terrain contacts from disclosed entries and applied damage facts."""

from typing import Literal, Mapping
from math import atan2, pi, sqrt
from uuid import UUID
from types import MappingProxyType

from dnd.core.events import SpatialChangeType
from dnd.core.presentation_geometry import SpherePresentationGeometry
from dnd.types.world import OccupancyLayer
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from dnd.types.senses import PerceivedSpatialEffect
from game.animation import ActorContact, media_track_duration
from game.animation_types import AnimationData, StudioMediaTrack, Facing8, ContactSweep
from game.combat import BoundCast, actor_contact, actor_is_visible
from game.player_facts import DamageResultFact, PlayerNode, PlayerState, SpatialFact, SpatialEffectStateFact
from game.stationary_media import StationaryMediaCue
from game.spatial_response import damage_spatial_owner


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
                          at_ms: float, contacts: Mapping[str, ActorContact],
                          created_effects: Mapping[UUID, tuple[PerceivedSpatialEffect, ...]] = MappingProxyType({})) -> tuple[StationaryMediaCue, ...]:
    """Known area identity never makes an unseen floor contact visible."""
    senses, fact = state.senses, event.fact
    if senses is None:
        return ()
    if isinstance(fact,SpatialEffectStateFact):
        effect = senses.spatial_effects.get(fact.spatial_effect_uuid)
        binding = data.spatial_media.get(effect.content_ref.content_id) if effect is not None else None
        if (event.canceled or fact.interaction_operation is not SpatialEffectInteractionOperation.DOUSE
                or binding is None or not binding.quenchVariants):
            return ()
        cues = []
        for cell in fact.removed_positions:
            if cell not in senses.visible or cell not in state.tiles:
                continue
            variant = binding.quenchVariants[(fact.spatial_effect_uuid.int+cell[0]*73856093+cell[1]*19349663)%len(binding.quenchVariants)]
            for side,asset_id in ((-1,variant.rearAssetId),(1,variant.frontAssetId)):
                track = StudioMediaTrack(id=f'quench:{fact.spatial_effect_uuid}:{cell}:{side}',assetId=asset_id,
                    attachment='area_ground',scale=binding.scale)
                cues.append(StationaryMediaCue(event.uuid,track,cell,state.tiles[cell].elevation_steps,
                    'E',at_ms,data,side*.01,native_pixels=True))
        return tuple(cues)
    sweep = bind_damage_sweep(state, event, data, at_ms, created_effects)
    trigger: Literal["ground_entry", "damage"]
    if isinstance(fact, SpatialFact) and ground_contact_is_authored(state, fact, data):
        identity, position, effect_id, trigger = fact.entity_uuid, fact.position, None, "ground_entry"
    elif (isinstance(fact, DamageResultFact) and fact.stage == "applied"
          and fact.applied_damage is not None and fact.applied_damage > 0
          and (fact.effect_id is not None or fact.source_condition_uuid is not None)):
        identity, position, effect_id, trigger = fact.target_entity_uuid, None, fact.effect_id, "damage"
    else:
        return sweep
    actor = state.actors.get(identity) if identity is not None else None
    if actor is None or not actor_is_visible(state, actor):
        return ()
    contact = contacts.get(str(identity)) or actor_contact(state, actor, data)
    position = position or contact.grid
    cell = round(position[0]), round(position[1])
    if cell not in senses.visible or cell not in state.tiles:
        return ()
    cues = {}
    exact = damage_spatial_owner(state, fact, created_effects) if isinstance(fact, DamageResultFact) else None
    effects = (exact,) if exact is not None else senses.spatial_effects.values()
    for effect in effects:
        if cell not in effect.positions or exact is None and effect_id is not None and effect.content_ref.identity_key != effect_id:
            continue
        binding = data.spatial_media.get(effect.content_ref.content_id)
        tracks = (binding.contactMediaByEnergy.get(fact.damage_type.value, ()) if binding is not None
            and isinstance(fact, DamageResultFact) else ())
        if not tracks and binding is not None and (fallback := binding.contactMedia.get(trigger)) is not None:
            tracks = (fallback,)
        # Several observed owners of the same content do not duplicate one
        # actual packet. Authored back/front layers share its contact and clock.
        for track in tracks:
            duration = media_track_duration(data,track)
            cues[track.id] = StationaryMediaCue(event.uuid, track, position, state.tiles[cell].elevation_steps,
                contact.facing, at_ms+track.startOffsetMs, data,
                fade_out_ms=(duration-track.fadeOutMs,duration) if track.fadeOutMs else None)
    return (*sweep, *cues.values())


def damage_sweep_recipe(state: PlayerState, fact: DamageResultFact,
                        data: AnimationData,
                        created_effects: Mapping[UUID, tuple[PerceivedSpatialEffect, ...]] = MappingProxyType({})) -> ContactSweep | None:
    """Resolve only a witnessed positive packet's authored contact presentation."""
    senses = state.senses
    if (fact.stage != "applied"
            or not fact.applied_damage or fact.applied_damage <= 0
            or fact.spatial_source is None or senses is None):
        return None
    source = fact.spatial_source
    effect = next((row for row in (senses.spatial_effects.get(source.spatial_effect_uuid),
        *created_effects.get(source.spatial_effect_uuid, ()))
        if row is not None and source.position in row.positions), None)
    if effect is None:
        return None
    binding = data.spatial_media.get(effect.content_ref.content_id)
    sweep = binding.damageSweeps.get(source.exposure) if binding is not None else None
    if sweep is None:
        return None
    same_contact = source.position == source.target_position
    if same_contact != (source.exposure == "contact"):
        return None
    dx, dy = (source.target_position[i]-source.position[i] for i in (0, 1))
    if dx and dy:
        return None  # Delivered cardinal banks cannot represent an oblique sweep.
    return sweep


def bind_damage_sweep(state: PlayerState, event: PlayerNode, data: AnimationData,
                      at_ms: float,
                      created_effects: Mapping[UUID, tuple[PerceivedSpatialEffect, ...]] = MappingProxyType({})) -> tuple[StationaryMediaCue, ...]:
    """Compile a witnessed applied contact; never infer a source from nearby fields."""
    fact = event.fact
    if not isinstance(fact, DamageResultFact) or (sweep := damage_sweep_recipe(state, fact, data, created_effects)) is None:
        return ()
    source = fact.spatial_source
    assert source is not None
    dx, dy = (source.target_position[i]-source.position[i] for i in (0, 1))
    directions = {"E": (1, 0), "S": (0, 1), "W": (-1, 0), "N": (0, -1)}
    bank = max(sweep.directions, key=lambda bank: dx*directions[bank.direction][0]+dy*directions[bank.direction][1])
    cues = []
    for index, node in enumerate(sweep.nodes):
        position = (source.position[0]+node.fraction*dx, source.position[1]+node.fraction*dy)
        variant = bank.variants[node.variant]
        layers: tuple[tuple[Literal["behind_body", "front_body"], str], ...] = (
            ("behind_body", variant.rearAssetId), ("front_body", variant.frontAssetId))
        for side, asset_id in layers:
            track = StudioMediaTrack(id=f"contact-sweep:{index}:{side}", assetId=asset_id,
                attachment="area_ground", scale=sweep.scale, depth=side, viewFacing="E")
            cues.append(StationaryMediaCue(event.uuid, track, position, source.base_height_steps,
                "E", at_ms+node.delayMs, data, native_pixels=True,
                fade_out_ms=(sweep.fadeStartMs, sweep.fadeEndMs)))
    return tuple(cues)
