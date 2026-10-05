"""Pygame pixels for the original per-slot Pixi condition body filter."""

from math import sin, pi
from pathlib import Path
from typing import Mapping, Sequence, cast

import numpy as np
import pygame

from game.condition_types import Activity, ConditionBodyColor, ConditionBodyRamp, ConditionBodyOutline
from dnd.core.life_types import LifeState
from game.condition_media import ResolvedConditionLayer
from game.condition_sampling import sample_condition_media, select_condition_markers
from game.animation_types import AnimationData, Facing8
from game.animation import view_facing
from game.registered_media import registered_media_blits
from game.projection import TILE_WIDTH
from game.directed_surface import repeated_texture


# ConditionOverlayController's body visual slots: equipment participates;
# independent actor effect/slash layers and the shadow do not receive color.
CONDITION_BODY_SLOTS = frozenset((
    "body", "shoes", "legs", "mount", "chest", "belt", "hands", "offhand",
    "weapon", "weaponGlow", "backpack", "head", "beard", "helmet",
))


def load_condition_layers(layers: Sequence[ResolvedConditionLayer],
                          rows: dict[tuple[str, str, str, int], pygame.Surface]) -> None:
    """Preload selected attachments into the existing session's immutable rows."""
    pages: dict[Path, pygame.Surface] = {}
    for resolved in layers:
        layer = resolved.layer
        for facing, spec in resolved.media.images_by_facing.items():
            key = ("condition", layer.assetId, facing, 0)
            if key not in rows:
                page = pages.get(spec.path)
                if page is None:
                    page = pages[spec.path] = pygame.image.load(spec.path).convert_alpha()
                rows[key] = page if spec.rect is None else page.subsurface(spec.rect)


def compose_condition_layers(body: pygame.Surface, destination: tuple[int, int],
                             ground: tuple[float, float], facing: str, scale: float, scale_x: float,
                             layers: tuple[ResolvedConditionLayer, ...],
                             rows: Mapping[tuple[str, str, str, int], pygame.Surface],
                             *, data: AnimationData | None = None, quadrant: int = 0,
                             floor_ground: tuple[float, float] | None = None, activity: Activity = "idle",
                             attachment_anchors: Mapping[str, tuple[float, float]] | None = None,
                             life_state: LifeState = LifeState.ALIVE,
                             absolute_ms: float = 0,
                             marker_anchor: tuple[float, float] | None = None,
                             marker_scale: float | None = None,
                             ) -> tuple[pygame.Surface, tuple[int, int]]:
    """Keep feet registration while joining back/body/front at one actor depth."""
    behind, front = [], []
    bounds = pygame.Rect(destination, body.size)
    for resolved in select_condition_markers(layers, absolute_ms, activity=activity, life_state=life_state.value):
        layer = resolved.layer
        if activity not in layer.activeDuring or life_state.value not in layer.lifeStates:
            continue
        head_marker = layer.markerGroup is not None and layer.attachment == "head"
        layer_scale = marker_scale if head_marker and marker_scale is not None else scale
        anchor = ground if layer.attachment == "body" or floor_ground is None else floor_ground
        if layer.attachment in ("head", "face", "hand"):
            if head_marker and marker_anchor is not None:
                anchor = marker_anchor
                if resolved.media.actor_top_clearance_px is not None:
                    anchor = (anchor[0], anchor[1] - resolved.media.actor_top_clearance_px * layer_scale)
            else:
                if attachment_anchors is None or layer.attachment not in attachment_anchors:
                    continue
                anchor = attachment_anchors[layer.attachment]
                if resolved.media.actor_top_clearance_px is not None:
                    # Ordinary attachments retain their actual per-frame pose.
                    top = destination[1] + body.get_bounding_rect().top
                    anchor = (anchor[0], min(anchor[1], top)
                        - resolved.media.actor_top_clearance_px * scale)
        factor = layer_scale * TILE_WIDTH / data.rig.TILE_W if data is not None else layer_scale
        anchor = (anchor[0] + layer.offsetX * factor * scale_x, anchor[1] + layer.offsetY * factor)
        media = resolved.media
        if media.asset_id is not None:
            assert data is not None
            viewed = (view_facing(cast(Facing8, media.world_basis), quadrant, data)
                      if media.world_basis is not None else cast(Facing8, facing))
            for sample in sample_condition_media(data, resolved):
                masks = (registered_media_blits(data, sample.removal_mask[0], "impact", sample.removal_mask[1],
                    viewed, scale=media.scale * layer_scale * TILE_WIDTH / data.rig.TILE_W, anchor=anchor, rows={})
                    if sample.removal_mask is not None else ())
                for image, point, _ in registered_media_blits(data, sample.asset_id, "impact", sample.frame,
                        viewed, scale=media.scale * layer_scale * TILE_WIDTH / data.rig.TILE_W,
                        anchor=anchor, rows={}, alpha=sample.alpha * layer.opacity):
                    if sample.removal_mask is not None:
                        mask = pygame.Surface(image.size, pygame.SRCALPHA)
                        for part, origin, _ in masks:
                            mask.blit(part, (origin[0] - point[0], origin[1] - point[1]))
                        image = image.copy()
                        alpha = pygame.surfarray.pixels_alpha(image)
                        alpha[:] = np.rint(alpha.astype(np.float32) * pygame.surfarray.array_alpha(mask) / 255)
                        del alpha
                    bounds.union_ip(pygame.Rect(point, image.size))
                    (behind if layer.drawOrder == "behind_body" else front).append((image, point))
            continue
        spec = resolved.media.images_by_facing[facing]
        image = rows[("condition", layer.assetId, facing, 0)]
        sy, sx = spec.scale * layer_scale, spec.scale * layer_scale * scale_x
        image = pygame.transform.scale(image, (max(1, round(image.width * sx)), max(1, round(image.height * sy))))
        if layer.opacity != 1.:
            image.set_alpha(round((image.get_alpha() or 255) * layer.opacity))
        point = (round(anchor[0] - spec.pivot[0] * sx), round(anchor[1] - spec.pivot[1] * sy))
        bounds.union_ip(pygame.Rect(point, image.size))
        (behind if layer.drawOrder == "behind_body" else front).append((image, point))
    result = pygame.Surface(bounds.size, pygame.SRCALPHA)
    for image, point in (*behind, (body, destination), *front):
        result.blit(image, (point[0] - bounds.x, point[1] - bounds.y))
    return result, bounds.topleft


def condition_body_ramp(surface: pygame.Surface, ramp: ConditionBodyRamp, *,
                        texture: pygame.Surface | None = None, cell_size: tuple[int, int] | None = None,
                        strength: float = 1., pulse: float = 0., age_ms: float = 0.,
                        normal_texture: pygame.Surface | None = None) -> pygame.Surface:
    """Map current row RGB; flowing film uses the source alpha-over silhouette operator."""
    result = surface.copy()
    rgb = pygame.surfarray.array3d(surface)
    colors = np.array([((color >> 16) & 255, (color >> 8) & 255, color & 255)
                       for color in ramp.colors], dtype=np.float32)
    if ramp.mapping == "frost_texture":
        if texture is None or normal_texture is None or cell_size is None:
            raise ValueError("frost material requires original noise, normal and actor frame dimensions")
        x = (np.arange(surface.width)%cell_size[0]+.5)/cell_size[0]
        y = (np.arange(surface.height)%cell_size[1]+.5)/cell_size[1]
        def source_sample(source: pygame.Surface, frequency: float) -> np.ndarray:
            # Source uses fract(UV) followed by LINEAR + CLAMP_TO_EDGE.
            u = np.clip(x*frequency % 1, .5/source.width, 1-.5/source.width)
            v = np.clip(y*frequency % 1, .5/source.height, 1-.5/source.height)
            return repeated_texture(pygame.surfarray.array3d(source)/255, u[:,None], v[None,:])
        noise = source_sample(texture, 1.7)[...,0]
        normal = source_sample(normal_texture, 1.3)*2-1
        normal /= np.maximum(np.linalg.norm(normal,axis=2)[...,None],1e-8)
        light = np.array((-.4,.7,.55));light /= np.linalg.norm(light)
        facet = .65+.35*np.maximum(normal@light,0)
        factor = np.clip(noise*.85+facet*.40,0,1)[...,None]
        ice = (np.array((.4307,.54221,.59))*(1-factor)+np.array((.753754,.934002,1))*factor)*facet[...,None]
        deposit = _smoothstep((noise-.18)/.04)*.96
        reveal = _smoothstep((strength*1.18-y+.12)/.24)[None,:]
        coverage = (strength*deposit*reveal)[...,None]
        pixels = pygame.surfarray.pixels3d(result)
        pixels[:] = np.clip(np.rint(rgb*(1-coverage)+ice*255*coverage),0,255).astype(np.uint8)
        del pixels
        return result
    if ramp.mapping == "flowing_film":
        if texture is None or cell_size is None or texture.height % ramp.textureFrames:
            raise ValueError("flowing film requires its original registered scalar frames")
        frame_height = texture.height // ramp.textureFrames
        frame = int(max(0.,age_ms)*ramp.textureFps/1000) % ramp.textureFrames
        x = np.floor((np.arange(surface.width) % cell_size[0])*texture.width/cell_size[0]).astype(int)
        y = np.floor((np.arange(surface.height) % cell_size[1])*frame_height/cell_size[1]).astype(int)
        scalar = pygame.surfarray.array3d(texture)[x[:,None],frame*frame_height+y[None,:],0]/239.
        value = np.clip(scalar,0,1)*2
        index = np.minimum(1,np.floor(value).astype(int))
        fraction = (value-index)[...,None]
        painted = np.floor(colors[index]*(1-fraction)+colors[index+1]*fraction+.5)
        source_y = (np.arange(surface.height) % cell_size[1])*128/cell_size[1]
        chest = _smoothstep((source_y-35)/13)*(1-_smoothstep((source_y-84)/10))
        amount = np.clip(strength*ramp.gain*chest[None,:]*(.2+.8*scalar*scalar),0,1)
        base = rgb*(1-strength*ramp.textureWeight+strength*ramp.textureWeight*colors[3]/255)
        source_alpha = pygame.surfarray.array_alpha(surface).astype(np.float32)/255
        added_alpha = source_alpha*amount
        alpha = added_alpha+source_alpha*(1-added_alpha)
        numerator = painted*added_alpha[...,None]+base*source_alpha[...,None]*(1-added_alpha[...,None])
        pixels = pygame.surfarray.pixels3d(result)
        pixels[:] = np.clip(np.rint(np.divide(numerator,alpha[...,None],
            out=np.zeros_like(numerator),where=alpha[...,None]>0)),0,255).astype(np.uint8)
        del pixels
        out_alpha = pygame.surfarray.pixels_alpha(result)
        out_alpha[:] = np.rint(alpha*255).astype(np.uint8)
        del out_alpha
        return result
    if ramp.mapping == "fracture_wave":
        x = np.arange(surface.width)[:, None]
        y = np.arange(surface.height)[None, :]
        noise = (np.sin(x * .79 + y * .45) + np.sin(x * .25 - y * .71) + 2) / 4
        crack = _smoothstep((noise - .73) / .17)
        amount = strength * (.20 + .62 * crack)
        mapped = np.where((crack > .5)[..., None], colors[1], colors[0])
        pixels = pygame.surfarray.pixels3d(result)
        pixels[:] = np.rint(rgb * (1 - amount[..., None]) + mapped * amount[..., None]).astype(np.uint8)
        del pixels
        return result
    if ramp.mapping == "etched_burn":
        field = pygame.Surface(surface.size)
        field.fill(ramp.colors[0])
        sx, sy = (surface.width/128,surface.height/128) if cell_size is None else (cell_size[0]/128,cell_size[1]/128)
        for index in range(7):
            points = [(sx*(35+index*8),sy*28),*((sx*(35+index*8+np.sin(step*2+index+age_ms*.007)*4),
                sy*(28+step*12)) for step in range(6))]
            pygame.draw.lines(field,ramp.colors[1 if index % 2 else 2],False,points,max(1,round(2.4*sx)))
        mapped = pygame.surfarray.array3d(field).astype(np.float32)
        pixels = pygame.surfarray.pixels3d(result)
        pixels[:] = np.clip(np.rint(255-(255-rgb)*(1-mapped*strength/255)),0,255).astype(np.uint8)
        del pixels
        return result
    if ramp.mapping in {"energy_burn", "rising_bands"}:
        age = age_ms / 1000
        x, y = np.indices(surface.size, dtype=np.float32)
        if cell_size is not None:
            x, y = x * 128 / cell_size[0], y * 128 / cell_size[1]
        alpha = pygame.surfarray.array_alpha(surface)
        if ramp.mapping == "energy_burn":
            edge = np.zeros(surface.size, dtype=bool)
            padded = np.pad(alpha, 1)
            for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
                edge |= padded[dx:dx+surface.width, dy:dy+surface.height] < 64
            noise = (np.sin(x*.31+y*.16-age*7) + np.sin(x*.63-y*.43+age*9)
                + np.sin(y*.39+x*.21-age*11)) / 3
            value = np.clip((noise+.1)*1.3 + edge*.55, 0, 1)
            amount = np.where(alpha >= 32, strength*(.2+value*.8), 0.)
        else:
            value = np.zeros(surface.size)
            for index in range(5):
                line = 105 - ((age*43+index*21) % 92)
                value = np.maximum(value, ((y >= line) & (y < line+2)).astype(float))
            amount = strength * (alpha > 0)
        mapped = colors[0] + value[..., None]*(colors[1]-colors[0])
        # Canvas screen compositing over the current body, preserving source alpha.
        pixels = pygame.surfarray.pixels3d(result)
        pixels[:] = np.clip(np.rint(255-(255-rgb)*(1-mapped*amount[..., None]/255)), 0, 255).astype(np.uint8)
        del pixels
        return result
    if ramp.mapping == "wither_texture":
        if texture is None:
            raise ValueError("wither material requires its registered donor texture")
        occupied = pygame.surfarray.array_alpha(surface) > 180
        xs, ys = np.nonzero(occupied)
        if not len(xs):
            return result
        # Accepted donor-noise operator, evaluated on the current silhouette.
        x = (np.arange(surface.width) - xs.min()) / max(1, xs.max() - xs.min() + 1)
        y = (np.arange(surface.height) - ys.min()) / max(1, ys.max() - ys.min() + 1)
        tx = np.floor(x * 1.4 * texture.width).astype(int) % texture.width
        ty = np.floor(y * 1.6 * texture.height).astype(int) % texture.height
        noise = pygame.surfarray.array3d(texture)[..., 0] / 255.
        n = noise[tx[:, None], ty[None, :]]
        n2 = noise[(tx[:, None] + 27) % texture.width, (ty[None, :] + 39) % texture.height]
        luminance = rgb @ np.array([.2126, .7152, .0722]) / 255.
        patch = _smoothstep((n + .5 * strength - .15) / .75) * strength * .85
        crack = np.where((np.abs(n2 - .47) < .024) & (n > .36), strength, 0.)
        base = colors[0] + luminance[..., None] * (colors[1] - colors[0])
        scar = colors[3] if pulse > .1 else colors[2]
        mapped = np.where((crack > .12)[..., None], scar, base)
        amount = np.where(occupied, np.maximum(patch, crack * .82), 0.)
        pixels = pygame.surfarray.pixels3d(result)
        pixels[:] = np.clip(np.rint(rgb * (1 - amount[..., None]) + mapped * amount[..., None]), 0, 255).astype(np.uint8)
        del pixels
        return result
    if ramp.mapping == "bark_texture":
        if texture is None or cell_size is None:
            raise ValueError("bark material requires its registered texture and frame dimensions")
        # Literal accepted material math; no multiplied tint or alpha erosion.
        x = (np.arange(surface.width) % cell_size[0] + .5) / cell_size[0]
        y = (np.arange(surface.height) % cell_size[1] + .5) / cell_size[1]
        tx = np.floor(x * 2.4 * texture.width).astype(int) % texture.width
        ty = np.floor(y * 1.8 * texture.height).astype(int) % texture.height
        wood = pygame.surfarray.array3d(texture)[tx[:, None], ty[None, :]] / 255.
        light = (rgb / 255.) @ np.array([.3, .59, .11])
        grain = wood @ np.array([.3, .59, .11])
        groove = np.sin(x[:, None] * 48 + np.sin(y[None, :] * 14) * 1.6)
        fissure = np.maximum(0, groove) ** 15 * _smoothstep((grain - .13) / (.34 - .13))
        colors = colors / 255.
        mixing = np.clip(grain * 1.9, 0, 1)[..., None]
        mapped = (colors[0] * (1 - mixing) + colors[1] * mixing) * (.72 + light[..., None] * .75)
        grow = _smoothstep((strength * 1.15 - y + .12) / .24)[None, :]
        deposit = strength * grow * .89
        magic = (1 - _smoothstep((np.abs(y - strength) - .02) / .04)) * strength * (1 - strength) * 3
        final = rgb / 255. * (1 - deposit[..., None]) + mapped * deposit[..., None]
        final += np.array([.52, .56, .18]) * magic[None, :, None]
        final += np.array([.12, .13, .025]) * (fissure * deposit)[..., None]
        pixels = pygame.surfarray.pixels3d(result)
        pixels[:] = np.clip(np.rint(final * 255), 0, 255).astype(np.uint8)
        del pixels
        return result
    value = np.minimum(1., rgb.max(axis=2).astype(np.float32) * (ramp.gain / 255.))
    if ramp.mapping == "luminance_texture":
        if texture is None or cell_size is None:
            raise ValueError("textured body palette requires its source texture and frame dimensions")
        x = np.arange(surface.width) % cell_size[0] / cell_size[0]
        y = np.arange(surface.height) % cell_size[1] / cell_size[1]
        tx = np.floor(x * ramp.textureRepeats * texture.width).astype(int) % texture.width
        ty = np.floor(y * ramp.textureRepeats * texture.height).astype(int) % texture.height
        grain = pygame.surfarray.array3d(texture)[tx[:, None], ty[None, :]].mean(axis=2) / 255
        luminance = (rgb.astype(np.float32) @ np.array([.2126, .7152, .0722])) / 255
        value = np.clip(luminance * (1 - ramp.textureWeight) + grain * ramp.textureWeight, 0, 1)
    indices = np.minimum(len(colors) - 1, (value * len(colors)).astype(int))
    pixels = pygame.surfarray.pixels3d(result)
    pixels[:] = colors[indices]
    del pixels
    return result


def _smoothstep(value: np.ndarray) -> np.ndarray:
    bounded = np.clip(value, 0, 1)
    return bounded * bounded * (3 - 2 * bounded)


def blend_body_ramp(original: pygame.Surface, mapped: pygame.Surface, strength: float) -> pygame.Surface:
    if strength >= 1.:
        return mapped
    if strength <= 0.:
        return original
    result = original.copy()
    rgb = pygame.surfarray.array3d(original).astype(np.float32)
    pixels = pygame.surfarray.pixels3d(result)
    pixels[:] = np.rint(rgb + (pygame.surfarray.array3d(mapped).astype(np.float32) - rgb) * strength).astype(np.uint8)
    del pixels
    return result


def condition_body_color(surface: pygame.Surface, color: ConditionBodyColor) -> pygame.Surface:
    """Match Pixi tint @ saturate(s - 1) @ brightness, preserving alpha.

    Pixi's saturation matrix uses the equal-channel mean, not luminance.
    AnimatedEntity adds this filter after the slot's normal tint/color policy.
    """
    image = surface.copy()
    pixels = pygame.surfarray.pixels3d(image)
    rgb = pixels.astype(np.float32)
    if abs(color.saturation - 1) > .001:
        rgb = rgb * color.saturation + rgb.mean(axis=2, keepdims=True) * (1 - color.saturation)
    if color.tintRgb is not None:
        tint = np.array((color.tintRgb >> 16 & 255, color.tintRgb >> 8 & 255,
                         color.tintRgb & 255), dtype=np.float32) / 255
        rgb *= tint
    if abs(color.brightness - 1) > .001:
        rgb *= color.brightness
    pixels[:] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    del pixels
    return image


def condition_body_outline(body: pygame.Surface, recipe: ConditionBodyOutline, age_ms: float | None,
                           *, quiet_age_ms: float = 0.) -> pygame.Surface:
    """An alpha-only inner contour and short clipped angular pulses; RGB stays authored."""
    alpha = pygame.surfarray.array_alpha(body)
    occupied = alpha >= recipe.alphaThreshold
    padded = np.pad(occupied, 1)
    interior = (padded[:-2, 1:-1] & padded[2:, 1:-1]
        & padded[1:-1, :-2] & padded[1:-1, 2:])
    edge = occupied & ~interior
    pulse_age = quiet_age_ms if age_ms is None else age_ms
    beat = max(0., sin(max(0., pulse_age) * 2 * pi / recipe.periodMs)) ** 6
    onset = 0. if age_ms is None else max(0., 1 - max(0., age_ms) / recipe.onsetMs)
    overlay = pygame.Surface(body.get_size(), pygame.SRCALPHA)
    overlay.fill(((recipe.color >> 16) & 255, (recipe.color >> 8) & 255, recipe.color & 255, 0))
    output_alpha = pygame.surfarray.pixels_alpha(overlay)
    output_alpha[:] = np.where(edge, round(255 * min(1., recipe.opacity + .4 * beat)), 0)
    del output_alpha
    pulse = pygame.Surface(body.get_size(), pygame.SRCALPHA)
    width, height = body.get_size()
    color = ((recipe.pulseColor >> 16) & 255, (recipe.pulseColor >> 8) & 255,
        recipe.pulseColor & 255, round(255 * recipe.pulseOpacity * max(beat, onset)))
    for k in range(5):
        y = height * (.29 + k * .085)
        pygame.draw.lines(pulse, color, False, [(width*.30,y), (width*.44,y-3),
            (width*.49,y+2), (width*.56,y-3), (width*.70,y)])
    pulse_alpha = pygame.surfarray.pixels_alpha(pulse)
    pulse_alpha[:] = np.minimum(pulse_alpha, alpha)
    del pulse_alpha
    overlay.blit(pulse, (0, 0))
    return overlay
