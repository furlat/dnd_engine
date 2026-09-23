"""Detached body/gear samples shared by pose sampling and pixel composition."""

from dataclasses import dataclass

from game.animation import ActorContact, BodySample
from game.animation_types import RigLayer
from game.condition_animation import ConditionAppearance


@dataclass(frozen=True, slots=True)
class SceneActor:
    contact: ActorContact
    layers: tuple[RigLayer, ...]
    condition: ConditionAppearance = ConditionAppearance()


@dataclass(frozen=True, slots=True)
class ActorPose:
    actor: SceneActor
    body: BodySample


@dataclass(frozen=True, slots=True)
class BodyTrailPose:
    pose: ActorPose
    opacity: float
    age_ms: float
