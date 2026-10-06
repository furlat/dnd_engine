"""Shared nine-slice drawing of authored Blender chrome, at native pixel cells."""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import pygame
from pydantic import BaseModel, ConfigDict, NonNegativeInt, TypeAdapter

from game.asset_types import AssetSpec
from game.assets import DATA_ROOT


class SkinSource(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    resource_id: str
    inset: tuple[NonNegativeInt, NonNegativeInt, NonNegativeInt, NonNegativeInt]


@dataclass(frozen=True, slots=True)
class SkinPatch:
    image: pygame.Surface
    inset: tuple[int, int, int, int]


UISkin = Mapping[str, Mapping[str, SkinPatch]]
_SOURCES = TypeAdapter(dict[str, dict[str, SkinSource]])


def load_skin(resources: Mapping[str, AssetSpec], *, data_root: Path = DATA_ROOT) -> UISkin:
    sources = _SOURCES.validate_json((data_root / 'ui_skin.json').read_text())
    groups = {}
    for kind, states in sources.items():
        patches = {}
        for state, source in states.items():
            resource = resources[source.resource_id]
            image = pygame.image.load(resource.path).convert_alpha()
            if resource.rect is not None:
                image = image.subsurface(resource.rect).copy()
            if image.get_size() != resource.native_size:
                raise ValueError(f'UI skin size disagrees with registration: {source.resource_id}')
            left, top, right, bottom = source.inset
            if left+right >= image.width or top+bottom >= image.height:
                raise ValueError(f'UI skin inset consumes its centre: {source.resource_id}')
            patches[state] = SkinPatch(image, source.inset)
        groups[kind] = MappingProxyType(patches)
    return MappingProxyType(groups)


def draw_skin(screen: pygame.Surface, rect: pygame.Rect, patch: SkinPatch, *, scale: float = 1.) -> None:
    left, top, right, bottom = patch.inset
    source_x = (0, left, patch.image.width-right, patch.image.width)
    source_y = (0, top, patch.image.height-bottom, patch.image.height)
    # Tight widgets retain proportional edges rather than negative centre sizes.
    horizontal = min(scale, rect.width / max(1, left+right))
    vertical = min(scale, rect.height / max(1, top+bottom))
    target_x = (rect.left, rect.left+round(left*horizontal), rect.right-round(right*horizontal), rect.right)
    target_y = (rect.top, rect.top+round(top*vertical), rect.bottom-round(bottom*vertical), rect.bottom)
    for y in range(3):
        for x in range(3):
            size = (target_x[x+1]-target_x[x], target_y[y+1]-target_y[y])
            if min(size) <= 0:
                continue
            source = pygame.Rect(source_x[x], source_y[y], source_x[x+1]-source_x[x], source_y[y+1]-source_y[y])
            cell = patch.image.subsurface(source)
            screen.blit(pygame.transform.scale(cell, size), (target_x[x], target_y[y]))
