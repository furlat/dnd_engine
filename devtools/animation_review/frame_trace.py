"""Pixel/frame diagnostics for the graphical review recorder."""

from typing import Any

from pydantic import TypeAdapter

from game.playback_frame import PlaybackFrame
from game.world_animation import WorldTransitionSample
from devtools.animation_review.trace import state_summary


WORLD_TRANSITIONS = TypeAdapter(tuple[WorldTransitionSample, ...])


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
