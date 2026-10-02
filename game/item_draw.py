"""Ground equipment from reviewed isolated frames; no physical geometry inference."""

from functools import lru_cache
from pathlib import Path

import pygame

from dnd.core.item_types import ItemEffectPresentationState, ItemIntegrity
from game.draw_commands import DrawCommand
from game.item_appearance import ground_appearance
from dnd.core.events import WorldObjectState
from game.item_effects import item_condition_recipes, item_material
from game.player_facts import PlayerObject
from game.projection import TILE_WIDTH, Camera, painter_key, project_screen


@lru_cache(maxsize=64)
def _sheet(key: str, clip: str) -> pygame.Surface:
    return pygame.image.load(Path(__file__).parent / "assets/neuroclient/spritesheets" / key / f"{clip}.png").convert_alpha()


@lru_cache(maxsize=512)
def _ground_frame(category: str, variant: str | None, quadrant: int, zoom: float,
                  effects: tuple[ItemEffectPresentationState, ...]) -> pygame.Surface:
    binding = ground_appearance(category, variant)
    if binding is None:
        raise ValueError("missing authored ground appearance")
    width, height = binding.cell
    row = binding.rows_by_camera[quadrant]
    frame = pygame.Surface((width, height), pygame.SRCALPHA)
    sources = tuple((layer.sprite_key, layer.tint_rgb) for layer in binding.layers) or ((binding.sprite_key, binding.tint),)
    for key, tint in sources:
        part = _sheet(key, binding.clip).subsurface(
            (binding.frame * width, row * height, width, height)).copy()
        part = item_material(part, effects,
                             "offhand" if category.startswith("Off-hand ") else "weapon",
                             item_condition_recipes(), category=key, base_tint=tint)
        frame.blit(part, (0, 0))
    factor = binding.scale * TILE_WIDTH / binding.reference_tile_width * zoom
    return pygame.transform.scale(frame, (max(1, round(width * factor)), max(1, round(height * factor))))


def item_ground_commands(obj: PlayerObject | WorldObjectState, camera: Camera) -> tuple[DrawCommand, ...]:
    item = obj.item
    binding = ground_appearance(item.visual_item_name, item.visual_variant_id)
    if binding is None or item.integrity is ItemIntegrity.DESTROYED:
        return ()
    image = _ground_frame(item.visual_item_name, item.visual_variant_id, camera.quadrant, camera.zoom,
                          item.item_effects)
    factor = binding.scale * TILE_WIDTH / binding.reference_tile_width * camera.zoom
    pivot = binding.pivots_by_camera[camera.quadrant]
    ground = project_screen(obj.placement.position, camera, elevation_steps=obj.placement.base_height_steps)
    # Crop after registration; rotation is around the explicitly authored contact.
    box = image.get_bounding_rect(min_alpha=1)
    crop = image.subsurface(box)
    center = pygame.Vector2(box.center) - pygame.Vector2(pivot) * factor
    if binding.rotation:
        crop = pygame.transform.rotate(crop, binding.rotation)
        center.rotate_ip(-binding.rotation)
    point = (round(ground[0] + center.x - crop.width / 2), round(ground[1] + center.y - crop.height / 2))
    key = painter_key(obj.placement.position, elevation_steps=obj.placement.base_height_steps,
                      quadrant=camera.quadrant, role="object", identity=item.item_uuid)
    commands = []
    if binding.shadow_sprite_key is not None:
        shadow = _sheet(binding.shadow_sprite_key, "Idle").subsurface((0, 2 * 128, 128, 128))
        shadow = shadow.subsurface(shadow.get_bounding_rect(min_alpha=1)).copy()
        shadow = pygame.transform.scale_by(shadow, binding.shadow_scale * TILE_WIDTH
                                           / binding.reference_tile_width * camera.zoom)
        shadow.set_alpha(100)
        commands.append(DrawCommand(key, shadow, (round(ground[0]-shadow.width/2), round(ground[1]-shadow.height/2)),
            0, (), owner=str(item.item_uuid), cell=obj.placement.position))
    commands.append(DrawCommand(key, crop, point, 0,
        (str(item.item_uuid), item.stack_count, binding.sprite_key, binding.frame),
        owner=str(item.item_uuid), cell=obj.placement.position))
    return tuple(commands)


def item_selection_command(obj: PlayerObject, camera: Camera) -> DrawCommand | None:
    commands = item_ground_commands(obj, camera)
    return commands[-1] if commands else None
