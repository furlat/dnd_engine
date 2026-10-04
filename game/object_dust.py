"""Finite source-alpha object retirement on received world transition dates."""
from typing import Sequence

import numpy as np

from game.animation_types import SilhouetteDust
from game.body_effects import silhouette_dust
from game.draw_commands import DrawCommand
from game.world_animation import WorldTransitionSample


def object_dust_commands(commands: Sequence[DrawCommand], transitions: Sequence[WorldTransitionSample],
                         recipe: SilhouetteDust | None) -> list[DrawCommand]:
    samples = {str(sample.transition.identity):sample for sample in transitions
        if sample.transition.object_dust is not None
        and sample.transition.object_dust.object.item.construction_geometry is None
        and not sample.transition.object_dust.partial}
    if not samples:
        return list(commands)
    if recipe is None:
        raise ValueError('Witnessed object dust has no authored silhouette recipe')
    result = []
    for command in commands:
        owner = command.owner or (str(command.evidence[0]) if command.evidence else '')
        sample = samples.get(owner)
        if sample is None:
            result.append(command)
            continue
        cue = sample.transition.object_dust
        assert cue is not None
        image,offset = silhouette_dust(command.surface,recipe,sample.elapsed_ms,cue.seed)
        depth = command.world_depth
        if depth is not None:
            depth = np.pad(np.broadcast_to(depth,command.surface.size),
                ((-offset[0],image.width-command.surface.width+offset[0]),
                 (-offset[1],image.height-command.surface.height+offset[1])),
                mode='edge')
        result.append(command._replace(surface=image,
            destination=(command.destination[0]+offset[0],command.destination[1]+offset[1]),
            world_depth=depth,owner=owner))
    return result
