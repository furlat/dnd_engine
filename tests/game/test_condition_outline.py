"""Approved alpha-mask contours preserve source pixels and frozen pose contracts."""

from dataclasses import replace

import numpy as np
import pygame
import pytest
from pydantic import ValidationError

from dnd.core.life_types import LifeState
from game.animation import ActorContact, BodySample
from game.animation_data import load_animation_data
from game.condition_animation import ConditionAppearance, condition_body_pose
from game.condition_draw import condition_body_outline
from game.condition_types import ConditionBodyOutline, ConditionFrozenPose


def test_outline_uses_alpha_without_recoloring_source_or_spilling_outside_body():
    body = pygame.Surface((48, 64), pygame.SRCALPHA)
    body.fill((11, 80, 121, 255), (12, 10, 24, 45))
    original = pygame.image.tobytes(body, 'RGBA')
    recipe = ConditionBodyOutline(color=0xffc249, pulseColor=0xffd47c)
    quiet = condition_body_outline(body, recipe, 1050)
    active = condition_body_outline(body, recipe, 350)
    alpha = pygame.surfarray.array_alpha(body)
    quiet_alpha = pygame.surfarray.array_alpha(quiet)
    active_alpha = pygame.surfarray.array_alpha(active)
    assert not active_alpha[alpha == 0].any()
    assert quiet_alpha[12, 12] > 0 and quiet_alpha[20, 20] == 0
    assert np.any(active_alpha > quiet_alpha)
    assert pygame.image.tobytes(body, 'RGBA') == original


def test_outline_does_not_wrap_opposite_canvas_edges():
    body = pygame.Surface((8, 8), pygame.SRCALPHA)
    body.fill((100, 80, 30, 255))
    overlay = condition_body_outline(body, ConditionBodyOutline(color=0xffc249, pulseColor=0xffd47c), 1050)
    alpha = pygame.surfarray.array_alpha(overlay)
    assert alpha[0, 0] and alpha[7, 7]
    assert not alpha[4, 4]


def test_frozen_pose_rejects_invalid_frames():
    assert ConditionFrozenPose(clip='Idle', frame=0).frame == 0
    with pytest.raises(ValidationError):
        ConditionFrozenPose(clip='Idle', frame=-1)


def test_frozen_pose_keeps_spatial_scale_and_dead_action_ownership():
    data = load_animation_data()
    body = BodySample('actor', 'Walk', 3, 'E', scale=(.8, .7))
    contact = ActorContact('actor', (4., 6.), 'E', 1.)
    frozen = ConditionAppearance(frozen_pose=ConditionFrozenPose(clip='Idle', frame=0))
    observed = condition_body_pose(data, body, contact, frozen)
    assert (observed.clip, observed.frame, observed.scale, observed.facing) == ('Idle', 0, body.scale, 'E')
    assert condition_body_pose(data, body, contact, ConditionAppearance()) == body
    assert condition_body_pose(data, body, replace(contact, life_state=LifeState.DEAD), frozen) == body


def test_frozen_pose_uses_registered_rig_override_and_safe_default():
    data = load_animation_data()
    body = BodySample('actor', 'Idle', 5, 'E')
    contact = ActorContact('actor', (4., 6.), 'E', 1.)
    frozen = ConditionAppearance(frozen_pose=ConditionFrozenPose(clip='Idle', frame=0,
        framesByRig={'neuroclient.modular': 3}))
    assert condition_body_pose(data, body, contact, frozen).frame == 3
    assert frozen.frozen_pose is not None
    default = ConditionAppearance(frozen_pose=frozen.frozen_pose.model_copy(update={'framesByRig': {}}))
    assert condition_body_pose(data, body, contact, default).frame == 0
