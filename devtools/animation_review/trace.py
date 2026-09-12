"""Export retained evidence and sampled pixels' coordinates, without live rules."""

from typing import Any

from pydantic import TypeAdapter

from game.animation import CastTimeline, EquipmentTimeline
from game.attack import AttackTimeline, BoundAttack
from game.animation_types import RigLayer
from game.body_action import BodyActionCue
from game.choreography import BoundChoreography
from game.condition_animation import ConditionTimeline
from game.damage import DamageCue
from game.forced_movement import ForcedMovementCue, ShoveCue
from game.motion import MotionLeg, MotionTimeline
from game.playback_frame import PlaybackFrame
from game.player_facts import PlayerLineage, PlayerState


STATE = TypeAdapter(PlayerState)
LINEAGE = TypeAdapter(PlayerLineage)
TIMELINE = TypeAdapter(AttackTimeline | CastTimeline)
CONDITIONS = TypeAdapter(tuple[ConditionTimeline, ...])
LEGS = TypeAdapter(tuple[MotionLeg, ...])
EQUIPMENT = TypeAdapter(EquipmentTimeline)
LAYERS = TypeAdapter(tuple[RigLayer, ...])
SHOVE = TypeAdapter(ShoveCue)
FORCED = TypeAdapter(ForcedMovementCue)
DAMAGE = TypeAdapter(DamageCue)
BODY_ACTION = TypeAdapter(BodyActionCue)


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
        } for identity, actor in state.actors.items()},
    }


def group_trace(group: BoundChoreography) -> dict[str, Any]:
    return {
        "root_uuid": str(group.root_uuid), "complete_ms": group.complete_ms,
        "observations": [{"at_ms": at, "event_uuid": str(observation.event_uuid),
                          "actor_uuid": str(observation.actor.uuid)} for at, observation in group.observations],
        "shoves": [SHOVE.dump_python(cue, mode="json", exclude={"data"}, warnings="error") for cue in group.shoves],
        "forced_movement": [{**FORCED.dump_python(cue, mode="json", exclude={"data"}, warnings="error"),
                             "context": cue.data.forced_movement_context.model_dump(mode="json"),
                             "profile": cue.data.forced_movement_profile.model_dump(mode="json")}
                            for cue in group.forced_movement],
        "damage": [DAMAGE.dump_python(cue, mode="json", exclude={"data"}, warnings="error") for cue in group.damage],
        "body_actions": [BODY_ACTION.dump_python(cue, mode="json", exclude={"data"}, warnings="error")
                         for cue in group.body_actions],
        "nodes": [{"event_uuid": str(node.event_uuid), "start_ms": node.start_ms,
                   "primitive": "attack" if isinstance(node.bound, BoundAttack) else "cast",
                   "timeline": TIMELINE.dump_python(
                       node.bound.timeline, mode="json", exclude={"data"},
                       warnings="error",
                   )} for node in group.nodes],
        "conditions": CONDITIONS.dump_python(group.conditions, mode="json", warnings="error"),
        "healing": [{"event_uuid": str(cue.event.uuid), "start_ms": cue.start_ms} for cue in group.healing],
        "lifecycle": [{"event_uuid": str(cue.event.uuid), "start_ms": cue.start_ms,
                       "death_end_ms": cue.death_end_ms, "state_owned": cue.state_owned,
                       "feedback": cue.feedback.model_dump(mode="json") if cue.feedback is not None else None}
                      for cue in group.lifecycle],
        "equipment": [{"event_uuid": str(cue.event_uuid), "start_ms": cue.start_ms,
                       "timeline": EQUIPMENT.dump_python(cue.bound.timeline, mode="json", exclude={"data"}, warnings="error"),
                       "replacement": LAYERS.dump_python(cue.bound.replacement, mode="json", warnings="error")}
                      for cue in group.equipment],
        "gaps": [(str(identity), detail) for identity, detail in group.gaps],
    }


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
                       "held_grid": row.contact.grid, "lift_px": row.lift_px,
                       "group": group_trace(row.choreography)} for row in motion.reactions],
    }


def frame_trace(frame: PlaybackFrame) -> dict[str, Any]:
    return {
        "state": state_summary(frame.displayed), "complete": frame.complete,
        "contacts": [{"actor_uuid": row.contact.actor_uuid, "grid": row.contact.grid,
                      "elevation_steps": row.contact.elevation_steps,
                      "body_lift_px": row.contact.body_lift_px,
                      "rig": row.contact.rig_id, "facing": frame.facings.get(row.contact.actor_uuid),
                      "shown_hp": frame.shown_hp.get(row.contact.actor_uuid, row.contact.hp)}
                     for row in frame.actors],
    }


def draw_trace(frame: PlaybackFrame) -> list[dict[str, Any]]:
    return [{"depth": key, "screen_xy": position, "size": surface.get_size(),
             "blend": flags, "evidence": evidence}
            for key, surface, position, flags, evidence in frame.commands]
