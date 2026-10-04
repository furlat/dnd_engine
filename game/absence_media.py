"""Sample witnessed absence echoes from the existing retained condition clock."""

from dataclasses import replace
from typing import Mapping
from uuid import UUID

from game.animation import view_facing
from game.animation_types import AnimationData
from game.body_pose_types import ActorPose
from game.condition_animation import AbsenceBodySample
from game.condition_media_lifetime import ConditionMediaLifetime
from game.draw_commands import DrawCommand
from game.player_facts import PlayerState
from game.projection import Camera, painter_key, project_screen
from game.registered_media import registered_media_blits


def _ease(start: float, end: float, time: float) -> float:
    value=min(1.,max(0.,(time-start)/(end-start)))
    return value*value*(3-2*value)


def absence_poses(poses: tuple[ActorPose,...], state: PlayerState,
                  records: Mapping[UUID,ConditionMediaLifetime], data: AnimationData,
                  time_ms: float) -> tuple[ActorPose,...]:
    selected={pose.body.actor_uuid:pose for pose in poses}
    for lifetime in records.values():
        recipe=data.condition_recipes[lifetime.behavior_id].persistent.absenceEcho
        if recipe is None or lifetime.applied_ms is None or lifetime.absence_pose is None:
            continue
        if time_ms < lifetime.applied_ms:
            continue
        returning=lifetime.returned_ms is not None and time_ms >= lifetime.returned_ms
        pose=lifetime.returned_pose if returning else lifetime.absence_pose
        if pose is None:
            continue
        if returning:
            assert lifetime.returned_ms is not None
            age=time_ms-lifetime.returned_ms
            if age>=recipe.returnMs[1]:
                continue
            progress=1-_ease(*recipe.returnMs,age)
            opacity=1.
        else:
            age=time_ms-lifetime.applied_ms
            progress=_ease(*recipe.departureMs,age)
            opacity=(1-_ease(0,recipe.clearMs,time_ms-lifetime.removed_ms)
                if lifetime.removed_ms is not None and time_ms>=lifetime.removed_ms else 1.)
        contact=pose.actor.contact
        # A remembered echo never reveals a currently unseen location.
        if opacity<=0 or state.senses is None or contact.grid not in state.senses.visible:
            continue
        appearance=replace(pose.actor.condition,absence=AbsenceBodySample(recipe,progress,opacity))
        selected[pose.body.actor_uuid]=replace(pose,appearance_override=appearance)
    return tuple(selected.values())


def absence_draw_commands(state: PlayerState, records: Mapping[UUID,ConditionMediaLifetime],
                           data: AnimationData, time_ms: float, camera: Camera) -> tuple[DrawCommand,...]:
    commands=[]
    for lifetime in records.values():
        recipe=data.condition_recipes[lifetime.behavior_id].persistent.absenceEcho
        if recipe is None or lifetime.applied_ms is None or lifetime.absence_pose is None:
            continue
        returning=lifetime.returned_ms is not None and time_ms>=lifetime.returned_ms
        if returning:
            assert lifetime.returned_ms is not None
            elapsed=time_ms-lifetime.returned_ms
            age=1020-elapsed if elapsed<720 else 300+elapsed-720
            pose=lifetime.returned_pose
        else:
            age=time_ms-lifetime.applied_ms
            pose=lifetime.absence_pose
        if pose is None or not 0<=age<recipe.portalDurationMs:
            continue
        contact=pose.actor.contact
        if state.senses is None or contact.grid not in state.senses.visible:
            continue
        anchor=project_screen(contact.grid,camera,elevation_steps=contact.elevation_steps)
        scale=recipe.scale*contact.visual_scale*camera.zoom
        for side,identity in (('back',recipe.back),('front',recipe.front)):
            key=painter_key(contact.grid,elevation_steps=contact.elevation_steps,quadrant=camera.quadrant,
                role='actor',identity=(str(lifetime.owner_uuid),side))
            key=(*key[:3],key[3]+(-1 if side=='back' else 1),key[4])
            frame=int(age*data.projectile_assets[identity].fps/1000)
            for image,destination,blend in registered_media_blits(data,identity,'impact',frame,
                    view_facing('E',camera.quadrant,data),scale=scale,anchor=anchor,rows={}):
                commands.append(DrawCommand(key,image,destination,blend,
                    (str(lifetime.owner_uuid),identity,side,frame)))
    return tuple(commands)
