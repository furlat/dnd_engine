"""Ground equipment from reviewed isolated frames; no physical geometry inference."""

from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

import pygame

from dnd.core.item_types import ItemEffectPresentationState, ItemIntegrity, ItemPresentationState
from game.draw_commands import DrawCommand
from game.item_appearance import ground_appearance
from dnd.core.events import WorldObjectState
from game.item_effects import item_condition_recipes, item_material
from game.animation_types import AnimationData, Facing8, ItemAttachmentStart
from game.maintained_media import maintained_media_frame
from game.registered_media import registered_media_blits
from game.player_facts import FloorItem, PlayerObject
from game.projection import TILE_WIDTH, Camera, painter_key, project_screen


def _item_attachment_blits(
    data: AnimationData, effects: tuple[ItemEffectPresentationState, ...],
    anchor: tuple[float, float], *, facing: Facing8, scale: float, time_ms: float,
    starts: Mapping[UUID, ItemAttachmentStart],
) -> tuple[list[tuple[pygame.Surface, tuple[int, int], int]],
           list[tuple[pygame.Surface, tuple[int, int], int]]]:
    rear, front = [], []
    for effect in effects:
        if effect.suppression_provider_uuids:
            continue
        binding = data.item_attachments.get(effect.behavior_id)
        if binding is None:
            continue
        start = starts.get(effect.effect_uuid)
        for layer in binding.layers:
            sampled = maintained_media_frame(data, binding, layer, time_ms,
                start.applied_ms if start is not None else None)
            if sampled is None:
                continue
            asset, frame = sampled
            (rear if layer.side == "rear" else front).extend(registered_media_blits(
                data, asset, binding.assetPhase, frame, facing,
                scale=scale * binding.scale, anchor=anchor, rows={}))
    return rear, front


def compose_item_attachments(
    image: pygame.Surface, destination: tuple[int, int], data: AnimationData,
    attachments: tuple[tuple[tuple[ItemEffectPresentationState, ...], tuple[float, float]], ...],
    *, facing: Facing8, scale: float, time_ms: float,
    starts: Mapping[UUID, ItemAttachmentStart],
) -> tuple[pygame.Surface, tuple[int, int]]:
    """Bracket visible item pixels with the existing registered rear/front parts."""
    rear, front = [], []
    bounds = pygame.Rect(destination, image.size)
    for effects, anchor in attachments:
        back, fore = _item_attachment_blits(data, effects, anchor, facing=facing,
            scale=scale, time_ms=time_ms, starts=starts)
        rear.extend(back)
        front.extend(fore)
        for part, point, _ in (*back, *fore):
            bounds.union_ip(pygame.Rect(point, part.size))
    if not rear and not front:
        return image, destination
    result = pygame.Surface(bounds.size, pygame.SRCALPHA)
    for part, point, blend in (*rear, (image, destination, 0), *front):
        result.blit(part, (point[0] - bounds.x, point[1] - bounds.y), special_flags=blend)
    return result, bounds.topleft


def item_attachment_commands(
    command: DrawCommand, item: ItemPresentationState | FloorItem, data: AnimationData | None,
    camera: Camera, *, time_ms: float, starts: Mapping[UUID, ItemAttachmentStart],
) -> tuple[tuple[DrawCommand, ...], tuple[DrawCommand, ...]]:
    """Decorate a real object frame without replacing its depth/occlusion pixels."""
    if (data is None or item.integrity is ItemIntegrity.DESTROYED
            or item.suppression_provider_uuids
            or not any(effect.behavior_id in data.item_attachments for effect in item.item_effects)):
        return (), ()
    box = command.surface.get_bounding_rect(min_alpha=1)
    if not box:
        return (), ()
    anchor = command.destination[0] + box.centerx, command.destination[1] + box.centery
    layers = _item_attachment_blits(data, item.item_effects, anchor,
        facing=data.rig.AUTHORED_PROJECTILE_ROW_ORDER[2 * camera.quadrant],
        scale=TILE_WIDTH / data.rig.TILE_W * camera.zoom, time_ms=time_ms, starts=starts)
    rear, front = (tuple(DrawCommand(command.key, image, point, blend,
        (item.item_uuid, "item_attachment", side), owner=str(item.item_uuid),
        cell=command.cell, support_height_steps=command.support_height_steps)
        for image, point, blend in parts) for side, parts in zip(("rear", "front"), layers))
    return rear, front


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


def item_ground_commands(obj: PlayerObject | WorldObjectState, camera: Camera, *,
                         data: AnimationData | None = None, time_ms: float = 0.,
                         starts: Mapping[UUID, ItemAttachmentStart] = MappingProxyType({}),
                         ) -> tuple[DrawCommand, ...]:
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
    if data is not None and not item.suppression_provider_uuids:
        anchor = (point[0] + crop.get_bounding_rect().centerx, point[1] + crop.get_bounding_rect().centery)
        crop, point = compose_item_attachments(crop, point, data, ((item.item_effects, anchor),),
            facing=data.rig.AUTHORED_PROJECTILE_ROW_ORDER[2 * camera.quadrant],
            scale=TILE_WIDTH / data.rig.TILE_W * camera.zoom, time_ms=time_ms, starts=starts)
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
