"""Export retained evidence and sampled pixels' coordinates, without live rules."""

from typing import Any

from pydantic import TypeAdapter

from game.animation import CastTimeline
from game.attack import AttackTimeline, BoundAttack
from game.choreography import BoundChoreography
from game.condition_animation import ConditionTimeline
from game.motion import MotionLeg, MotionTimeline
from game.playback_frame import PlaybackFrame
from game.presentation import CompletedLineage, PresentationTarget


STATE = TypeAdapter(PresentationTarget)
LINEAGE = TypeAdapter(CompletedLineage)
TIMELINE = TypeAdapter(AttackTimeline | CastTimeline)
CONDITIONS = TypeAdapter(tuple[ConditionTimeline, ...])
LEGS = TypeAdapter(tuple[MotionLeg, ...])


def state_summary(state: PresentationTarget) -> dict[str, Any]:
    """Compact actual reducer facts; full initial state is stored once per clip."""
    return {
        "cursor": state.reducer_cursor,
        "observer_uuid": str(state.observer_uuid),
        "current_actor_uuid": str(state.current_actor_uuid) if state.current_actor_uuid else None,
        "round": state.round_number,
        "actors": {str(identity): {
            "name": actor.name, "hp": actor.normal_hp, "max_hp": actor.maximum_hp,
            "temporary_hp": actor.temporary_hp, "life": actor.life_state.value,
            "active_weapon_set": actor.active_weapon_set.value,
            "equipment": [(slot, str(item)) for slot, item in actor.equipment],
            "conditions": [{"uuid": str(row.condition_uuid), "event_uuid": str(row.event_uuid),
                            "behavior_id": row.behavior_id, "name": row.name} for row in actor.conditions],
            "last_visual_position": actor.last_visual_position,
        } for identity, actor in state.actors.items()},
    }


def group_trace(group: BoundChoreography) -> dict[str, Any]:
    return {
        "root_uuid": str(group.root_uuid), "complete_ms": group.complete_ms,
        "nodes": [{"event_uuid": str(node.event_uuid), "start_ms": node.start_ms,
                   "primitive": "attack" if isinstance(node.bound, BoundAttack) else "cast",
                   "timeline": TIMELINE.dump_python(
                       node.bound.timeline, mode="json", exclude={"data"},
                       warnings="error",
                   )} for node in group.nodes],
        "conditions": CONDITIONS.dump_python(group.conditions, mode="json", warnings="error"),
        "gaps": [(str(identity), detail) for identity, detail in group.gaps],
    }


def motion_trace(motion: MotionTimeline) -> dict[str, Any]:
    return {
        "actor_uuid": motion.actor.actor_uuid, "clip": motion.clip,
        "playback_speed": motion.playback_speed, "complete_ms": motion.complete_ms,
        "legs": LEGS.dump_python(motion.legs, mode="json", warnings="error"),
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
