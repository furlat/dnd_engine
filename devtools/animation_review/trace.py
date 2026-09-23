"""Export retained evidence and sampled pixels' coordinates, without live rules."""

from typing import Any

from pydantic import TypeAdapter

from game.animation import BodyTransition, CastTimeline, EquipmentTimeline
from game.attack import AttackTimeline, BoundAttack
from game.animation_types import RigLayer
from game.action_media import ActionStripCue
from game.body_action import BodyActionCue
from game.body_hop import BodyHopCue
from game.portal_animation import PortalTransferCue
from game.choreography import BoundChoreography
from game.condition_animation import ConditionTimeline
from game.damage import DamageCue
from game.forced_movement import ForcedMovementCue, ShoveCue
from game.motion import MotionLeg, MotionTimeline
from game.playback_frame import PlaybackFrame
from game.player_facts import PlayerLineage, PlayerState
from game.world_animation import WorldTransitionSample


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
WORLD_TRANSITIONS = TypeAdapter(tuple[WorldTransitionSample, ...])


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


def group_trace(group: BoundChoreography) -> dict[str, Any]:
    return {
        "root_uuid": str(group.root_uuid), "complete_ms": group.complete_ms,
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
        "healing": [{"event_uuid": str(cue.event.uuid), "start_ms": cue.start_ms} for cue in group.healing],
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
        "actor_uuid": motion.actor.actor_uuid, "clip": motion.clip,
        "playback_speed": motion.playback_speed, "body_loops": motion.body_loops,
        "complete_ms": motion.complete_ms,
        "legs": LEGS.dump_python(motion.legs, mode="json", warnings="error"),
        "states": [{"at_ms": at, "cursor": state.reducer_cursor,
                    "actors": [str(identity) for identity in state.actors]}
                   for at, state in motion.states],
        "reactions": [{"start_ms": row.start_ms, "end_ms": row.end_ms,
                       "held_grid": row.contact.grid if row.contact is not None else None, "lift_px": row.lift_px,
                       "group": group_trace(row.choreography)} for row in motion.reactions],
    }


def frame_trace(frame: PlaybackFrame) -> dict[str, Any]:
    return {
        "world_transitions": WORLD_TRANSITIONS.dump_python(frame.world_transitions, mode="json"),
        "residue_reveals": [{"position": row.reveal.position,
            "condition_uuid": str(row.reveal.after.condition_uuid), "elapsed_ms": row.elapsed_ms,
            "start_ms": row.reveal.start_ms, "end_ms": row.reveal.end_ms,
            "before_amount": row.reveal.before.amount if row.reveal.before else 0,
            "after_amount": row.reveal.after.amount, "pattern": row.reveal.pattern,
            "asset_id": row.reveal.asset.assetId} for row in frame.residue_reveals],
        "state": state_summary(frame.displayed), "complete": frame.complete,
        "contacts": [{"actor_uuid": row.contact.actor_uuid, "grid": row.contact.grid,
                      "elevation_steps": row.contact.elevation_steps,
                      "body_lift_px": row.contact.body_lift_px,
                      "rig": row.contact.rig_id, "facing": frame.facings.get(row.contact.actor_uuid),
                      "shown_hp": frame.shown_hp.get(row.contact.actor_uuid, row.contact.hp)}
                     for row in frame.actors],
    }


def draw_trace(frame: PlaybackFrame) -> list[dict[str, Any]]:
    return [{"depth": command.key, "screen_xy": command.destination, "size": command.surface.get_size(),
             "blend": command.blend, "evidence": command.evidence}
            for command in frame.commands]
