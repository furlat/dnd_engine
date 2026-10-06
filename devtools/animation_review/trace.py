"""Export retained evidence and sampled pixels' coordinates, without live rules."""

from typing import Any, Mapping
from uuid import UUID

from pydantic import TypeAdapter

from game.presentation_timing import (PresentationMilestone, presentation_milestones,
    PresentationDependencies, presentation_dependencies)
from game.animation import BodyTransition, CastTimeline, EquipmentTimeline
from game.attack import AttackTimeline, BoundAttack
from game.animation_types import RigLayer, ItemAttachmentStart
from game.action_media import ActionStripCue
from game.body_action import BodyActionCue
from game.body_hop import BodyHopCue
from game.portal_animation import PortalTransferCue
from game.choreography import BoundChoreography, StateCommitEvidence, MotionStateProvenance
from game.condition_animation import ConditionTimeline, ConditionResponseCue
from game.damage import DamageCue
from game.forced_movement import ForcedMovementCue, ShoveCue
from game.motion import MotionLeg, MotionTimeline
from game.player_facts import PlayerLineage, PlayerState
from game.world_animation import WorldTransition
from game.stationary_media import StationaryMediaCue
from game.finite_material import BodyMaterialCue
from game.residue_media import ResidueReveal
from game.condition_media_lifetime import ConditionMediaLifetime
from game.spatial_media_lifetime import SpatialMediaLifetime
from game.construction_transitions import ConstructionMediaLifetime
from game.concentration_media import ConcentrationMediaLifetime
from game.deposit_media import DepositStart


MILESTONES = TypeAdapter(tuple[PresentationMilestone, ...])
DEPENDENCIES = TypeAdapter(tuple[PresentationDependencies, ...])
STATE = TypeAdapter(PlayerState)
LINEAGE = TypeAdapter(PlayerLineage)
TIMELINE = TypeAdapter(AttackTimeline | CastTimeline)
CONDITIONS = TypeAdapter(tuple[ConditionTimeline, ...])
LEGS = TypeAdapter(tuple[MotionLeg, ...])
EQUIPMENT = TypeAdapter(EquipmentTimeline)
BODY_TRANSITION = TypeAdapter(BodyTransition)
LAYERS = TypeAdapter(tuple[RigLayer, ...])
SHOVE = TypeAdapter(ShoveCue)
FORCED = TypeAdapter(ForcedMovementCue)
DAMAGE = TypeAdapter(DamageCue)
BODY_ACTION = TypeAdapter(BodyActionCue)
BODY_HOP = TypeAdapter(BodyHopCue)
PORTAL = TypeAdapter(PortalTransferCue)
ACTION_STRIP = TypeAdapter(ActionStripCue)
WORLD_CHANGES = TypeAdapter(tuple[WorldTransition, ...])
STATE_COMMITS = TypeAdapter(tuple[StateCommitEvidence, ...])
MOTION_PROVENANCE = TypeAdapter(tuple[MotionStateProvenance, ...])
STATIONARY = TypeAdapter(StationaryMediaCue)
FINITE_MATERIAL = TypeAdapter(BodyMaterialCue)
CONDITION_RESPONSE = TypeAdapter(ConditionResponseCue)
RESIDUE_REVEALS = TypeAdapter(tuple[ResidueReveal, ...])
CONDITION_LIFETIMES = TypeAdapter(dict[UUID, ConditionMediaLifetime])
SPATIAL_LIFETIMES = TypeAdapter(dict[UUID, SpatialMediaLifetime])
CONSTRUCTION_LIFETIMES = TypeAdapter(dict[UUID, ConstructionMediaLifetime])
CONCENTRATION_LIFETIMES = TypeAdapter(dict[UUID, ConcentrationMediaLifetime])
ITEM_STARTS = TypeAdapter(dict[UUID, ItemAttachmentStart])


def state_summary(state: PlayerState) -> dict[str, Any]:
    """Compact actual reducer facts; full initial state is stored once per clip."""
    return {
        "cursor": state.reducer_cursor,
        "observer_uuid": str(state.observer_uuid),
        "current_actor_uuid": str(state.current_actor_uuid) if state.current_actor_uuid else None,
        "round": state.round_number,
        "actors": {str(identity): {
            "name": actor.name, "hp": actor.normal_hp, "max_hp": actor.maximum_hp,
            "temporary_hp": actor.temporary_hp, "life": actor.life_state.value,
            "active_weapon_set": actor.visual_loadout.active_weapon_set.value,
            "equipment": [(item.slot, str(item.item_uuid)) for item in actor.visual_loadout.layers],
            "conditions": [{"uuid": str(row.condition_uuid), "event_uuid": str(row.event_uuid),
                            "behavior_id": row.behavior_id, "name": row.name} for row in actor.conditions],
            "last_visual_position": actor.last_visual_position,
            "controlled_items": (None if actor.controlled_items is None
                                 else [str(item.item_uuid) for item in actor.controlled_items]),
        } for identity, actor in state.actors.items()},
        "objects": {str(identity): {
            "item_id": obj.item.item_id, "position": obj.placement.position,
            "is_open": obj.item.is_open, "is_lit": obj.item.is_lit, "is_engaged": obj.item.is_engaged,
        } for identity, obj in state.objects.items()},
        "residues": [{"position": tile.position,
                      "members": [row.model_dump(mode="json") for row in tile.residues]}
                     for tile in state.tiles.values() if tile.residues],
        "spatial_effects": {} if state.senses is None else {str(identity): {
            "content_id": effect.content_ref.content_id,
            "state": effect.trap_state.value if effect.trap_state is not None else None,
            "positions": effect.positions, "description": effect.description,
        } for identity, effect in state.senses.spatial_effects.items()},
    }


def stationary_trace(cue: StationaryMediaCue) -> dict[str, Any]:
    return {**STATIONARY.dump_python(cue, mode="json", exclude={"data"}, warnings="error"),
            "end_ms": cue.end_ms}


def group_trace(group: BoundChoreography) -> dict[str, Any]:
    return {
        "trace_version": 2,
        "milestones": MILESTONES.dump_python(presentation_milestones(group), mode="json", warnings="error"),
        "dependencies": DEPENDENCIES.dump_python(presentation_dependencies(group), mode="json", warnings="error"),
        "root_uuid": str(group.root_uuid), "complete_ms": group.complete_ms,
        "state_commits": STATE_COMMITS.dump_python(group.state_commits, mode="json", warnings="error"),
        "world_changes": WORLD_CHANGES.dump_python(group.world_transitions, mode="json", warnings="error"),
        "residue_reveals": residue_trace(group.residue_reveals),
        "stationary_media": [stationary_trace(cue) for cue in group.stationary_media],
        "contact_media": [stationary_trace(cue) for cue in group.contact_media],
        "condition_responses": [{**CONDITION_RESPONSE.dump_python(cue, mode="json", warnings="error"),
                                 "end_ms": cue.end_ms} for cue in group.condition_responses],
        "turn_starts": [{"at_ms": at, "actor_uuid": str(actor), "event_uuid": str(event)}
                        for at, actor, event in group.turn_starts],
        "reaction_media": [{"event_uuid": str(cue.event_uuid),
            "incoming_event_uuid": str(cue.incoming_event_uuid), "succeeded": cue.succeeded,
            "start_ms": cue.start_ms, "complete_ms": cue.complete_ms,
            "source_point": cue.source_point, "recipe": cue.recipe.model_dump(mode="json")}
            for cue in group.reaction_media],
        "entity_lifecycle": [{"event_uuid": str(cue.event_uuid), "phase": cue.phase,
            "actor_uuid": cue.actor.contact.actor_uuid, "start_ms": cue.start_ms,
            "body_end_ms": cue.body_end_ms, "recipe": cue.recipe.model_dump(mode="json")}
            for cue in group.entity_lifecycle],
        "finite_materials": [FINITE_MATERIAL.dump_python(cue, mode="json", warnings="error")
            for cue in group.finite_materials],
        "spatial_responses": [{"owner_uuid": str(cue.owner_uuid),
            "recipient_uuid": cue.recipient.actor_uuid, "contact_ms": cue.contact_ms,
            "media": stationary_trace(cue.media), "recipe": cue.recipe.model_dump(mode="json")}
            for cue in group.spatial_responses],
        "state_times_ms": [at for at, _ in group.states],
        "observations": [{"at_ms": at, "event_uuid": str(observation.event_uuid),
                          "actor_uuid": str(observation.actor.uuid)} for at, observation in group.observations],
        "shoves": [SHOVE.dump_python(cue, mode="json", exclude={"data"}, warnings="error") for cue in group.shoves],
        "forced_movement": [{**FORCED.dump_python(cue, mode="json", exclude={"data"}, warnings="error"),
                             "context": cue.data.forced_movement_context.model_dump(mode="json"),
                             "profile": cue.data.forced_movement_profile.model_dump(mode="json")}
                            for cue in group.forced_movement],
        "damage": [DAMAGE.dump_python(cue, mode="json", exclude={
            "data": True, "timing": {"life_body": {"data": True}},
        }, warnings="error") for cue in group.damage],
        "body_actions": [BODY_ACTION.dump_python(cue, mode="json", exclude={"data"}, warnings="error")
                         for cue in group.body_actions],
        "body_hops": [BODY_HOP.dump_python(cue, mode="json", exclude={"data"}, warnings="error")
                      for cue in group.body_hops],
        "portals": [PORTAL.dump_python(cue, mode="json", exclude={"art", "data"}, warnings="error")
                    for cue in group.portals],
        "nodes": [{"event_uuid": str(node.event_uuid), "start_ms": node.start_ms,
                   "primitive": "attack" if isinstance(node.bound, BoundAttack) else "cast",
                   "timeline": timeline_trace(node.bound.timeline)} for node in group.nodes],
        "conditions": CONDITIONS.dump_python(group.conditions, mode="json", warnings="error", exclude={
            "__all__": {"body": {"data": True},
                        **{name: {"layers": {"__all__": {"media": True}}}
                           for name in ("before_appearance", "after_appearance")}}}),
        "healing": [{"event_uuid": str(cue.event.uuid), "start_ms": cue.start_ms,
                     "end_ms": cue.end_ms} for cue in group.healing],
        "lifecycle": [{"event_uuid": str(cue.event.uuid), "start_ms": cue.start_ms,
                       "death_end_ms": cue.death_end_ms, "state_owned": cue.state_owned,
                       "body_end_ms": cue.body_end_ms,
                       "body": BODY_TRANSITION.dump_python(cue.body, mode="json", exclude={"data"}, warnings="error")
                       if cue.body is not None else None,
                       "feedback": cue.feedback.model_dump(mode="json") if cue.feedback is not None else None}
                      for cue in group.lifecycle],
        "equipment": [{"event_uuid": str(cue.event_uuid), "start_ms": cue.start_ms,
                       "timeline": EQUIPMENT.dump_python(cue.bound.timeline, mode="json", exclude={"data"}, warnings="error"),
                       "replacement": LAYERS.dump_python(cue.bound.replacement, mode="json", warnings="error")}
                      for cue in group.equipment],
        "movements": [{"event_uuid": str(cue.event_uuid), "start_ms": cue.start_ms,
                       "motion": motion_trace(cue.timeline)} for cue in group.movements],
        "strips": [ACTION_STRIP.dump_python(cue, mode="json", exclude={"data"}, warnings="error")
                   for cue in group.strips],
        "gaps": [(str(identity), detail) for identity, detail in group.gaps],
    }


def timeline_trace(timeline: AttackTimeline | CastTimeline) -> dict[str, Any]:
    """Keep the measured emitter contact without copying its whole art catalog."""
    result = TIMELINE.dump_python(timeline, mode="json", exclude={
        "data": True, "source": {"emitter": {"art": True, "bank": True}},
        "applications": {"__all__": {"life_body": {"data": True}}},
        "damage_timing": {"life_body": {"data": True}},
    }, warnings="error")
    if isinstance(timeline, CastTimeline) and timeline.source.emitter is not None:
        emitter = timeline.source.emitter
        result["source"]["emitter"].update(body_asset=emitter.art.identity, pitch_degrees=emitter.bank.degrees)
    return result


def motion_trace(motion: MotionTimeline) -> dict[str, Any]:
    return {
        "trace_version": 2,
        "milestones": MILESTONES.dump_python(presentation_milestones(motion=motion), mode="json", warnings="error"),
        "dependencies": DEPENDENCIES.dump_python(presentation_dependencies(motion=motion), mode="json", warnings="error"),
        "actor_uuid": motion.actor.actor_uuid, "clip": motion.clip,
        "state_provenance": MOTION_PROVENANCE.dump_python(motion.state_provenance, mode="json", warnings="error"),
        "playback_speed": motion.playback_speed, "body_loops": motion.body_loops,
        "complete_ms": motion.complete_ms,
        "legs": LEGS.dump_python(motion.legs, mode="json", warnings="error"),
        "arc_height_px": motion.arc_height_px, "settled_lift_px": motion.settled_lift_px,
        "animation_id": motion.animation_id, "body_frame_keys": motion.body_frame_keys,
        "body_context": motion.body_context.model_dump(mode="json") if motion.body_context is not None else None,
        "recovery_body": motion.recovery_body.model_dump(mode="json") if motion.recovery_body is not None else None,
        "recovery_start_ms": motion.recovery_start_ms,
        "world_changes": WORLD_CHANGES.dump_python(motion.world_transitions, mode="json", warnings="error"),
        "residue_reveals": residue_trace(motion.residue_reveals),
        "contact_media": [stationary_trace(cue) for cue in motion.contact_media],
        "states": [{"at_ms": at, "cursor": state.reducer_cursor,
                    "actors": [str(identity) for identity in state.actors]}
                   for at, state in motion.states],
        "reactions": [{"start_ms": row.start_ms, "end_ms": row.end_ms,
                       "held_grid": row.contact.grid if row.contact is not None else None, "lift_px": row.lift_px,
                       "group": group_trace(row.choreography)} for row in motion.reactions],
    }


def residue_trace(reveals: tuple[ResidueReveal, ...]) -> list[dict[str, Any]]:
    rows = RESIDUE_REVEALS.dump_python(reveals, mode="json", warnings="error",
        exclude={"__all__": {"asset"}})
    return [{**row, "asset_id": reveal.asset.assetId} for row, reveal in zip(rows, reveals)]


def retained_trace(*, conditions: Mapping[UUID, ConditionMediaLifetime],
                   spatial: Mapping[UUID, SpatialMediaLifetime],
                   construction: Mapping[UUID, ConstructionMediaLifetime],
                   concentration: Mapping[UUID, ConcentrationMediaLifetime],
                   items: Mapping[UUID, ItemAttachmentStart],
                   deposits: Mapping[UUID, DepositStart]) -> dict[str, Any]:
    """Snapshot existing owner clocks; never re-register or infer membership."""
    appearance = {"layers": {"__all__": {"media"}},
                  "live_copies": {"layers": {"__all__": {1: {"__all__": {"media"}}}}}}
    pose = {"actor": {"condition": appearance}, "appearance_override": appearance}
    return {
        "conditions": CONDITION_LIFETIMES.dump_python(dict(conditions), mode="json", warnings="error",
            exclude={"__all__": {"absence_pose": pose, "returned_pose": pose}}),
        "spatial": SPATIAL_LIFETIMES.dump_python(dict(spatial), mode="json", warnings="error"),
        "construction": CONSTRUCTION_LIFETIMES.dump_python(dict(construction), mode="json", warnings="error"),
        "concentration": CONCENTRATION_LIFETIMES.dump_python(dict(concentration), mode="json", warnings="error"),
        "items": ITEM_STARTS.dump_python(dict(items), mode="json", warnings="error"),
        "deposits": {str(identity): TypeAdapter(DepositStart).dump_python(start, mode="json", warnings="error")
            for identity, start in deposits.items()},
    }
