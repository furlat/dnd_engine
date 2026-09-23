"""Authored actor cadence selected from retained condition membership."""

from game.animation_types import AnimationData
from game.player_facts import PlayerActor


def action_playback_rate(data: AnimationData, actor: PlayerActor) -> float:
    return max((data.action_playback_rates.get(member.behavior_id or "", 1.0)
                for member in actor.conditions), default=1.0)
