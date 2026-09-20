"""Pygame composition of sampled actor rigs on the map or reference stage.

Actor and legacy atlas rows load before playback; finite projectile frames use
bounded shared storage. Authored clocks and facts remain in game.animation.
"""

from __future__ import annotations

from colorsys import rgb_to_hsv
from dataclasses import dataclass, replace
from math import ceil, cos, degrees, floor, hypot, pi, sin, sqrt
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np
import pygame

from dnd.core.life_types import LifeState
from game.animation import (
    ActorContact, BodySample, CastSample, CastTimeline, GeometryProjectileSample, NumberSample,
    ProjectileSample, body_clip, body_elevation_steps, body_rig, project_geometry_projectile, project_projectile,
    projectile_center_offset, projectile_phase_scale, projectile_contact, view_facing, cast_deliveries,
)
from game.animation_types import AnimationData, DepthMode, ElementColors, Facing8, ParticleMediaAsset, StudioActorLayer, RigLayer as RigLayer
from game.action_media import ActionStripCue, ActionStripSample
from game.attack import AttackSample, AttackTimeline, attack_projectile_contact, project_attack_projectile
from game.condition_animation import ConditionAppearance
from game.condition_draw import CONDITION_BODY_SLOTS, condition_body_color
from game.projectile_media import projectile_frame_layers
from game.particle_media import sample_particles
from game.area_media import AreaLayer, AreaMedia, mask_ground_area
from game.draw_commands import DrawCommand as AnimationDrawCommand
from dnd.types.world_placement import WorldObjectPlacement
from game.projection import Camera, HEIGHT_STEP_PIXELS, TILE_WIDTH, painter_key, project_screen, rotate_position


BodyRows = Mapping[tuple[str, str, str, int], pygame.Surface]
LoadedBodyRows = dict[tuple[str, str, str, int], pygame.Surface]
ActorMediaRequest = tuple[ActorContact, tuple[RigLayer, ...], tuple[str, ...]]


def load_action_strip_media(cues: Sequence[ActionStripCue]) -> dict[str, pygame.Surface]:
    """Preload only strips selected by this historical head."""
    rows = {}
    for cue in cues:
        if isinstance(cue.asset, ParticleMediaAsset):
            continue
        if cue.asset.assetId not in rows:
            path = cue.data.resources[f"/spritesheets/{cue.asset.source}.png"]
            rows[cue.asset.assetId] = pygame.image.load(path).convert_alpha()
    return rows


def action_strip_draw_command(sample: ActionStripSample, rows: Mapping[str, pygame.Surface],
                              camera: Camera) -> AnimationDrawCommand:
    """NeuroStudio body overlay: bottom-center local anchor, inherited rig scale."""
    cue, frame = sample.cue, sample.frame
    track, asset, contact, data = cue.track, cue.asset, cue.contact, cue.data
    assert not isinstance(asset, ParticleMediaAsset)
    sheet = rows[asset.assetId]
    width = sheet.width // asset.frames
    height = sheet.height // (8 if asset.directional else 1)
    row = data.rig.FACING_ROW[view_facing(contact.facing, camera.quadrant, data)] if asset.directional else 0
    image = sheet.subsurface((frame * width, row * height, width, height))
    if track.tint != 0xFFFFFF:
        image = _colored(image, track.tint, data.vfx_source_hues.get(asset.source))
    factor = contact.visual_scale * TILE_WIDTH / data.rig.TILE_W * camera.zoom
    image = pygame.transform.scale(image, (
        max(1, round(width * track.scale * factor * contact.visual_scale_x)),
        max(1, round(height * track.scale * factor))))
    elevation = body_elevation_steps(contact, data)
    ground = project_screen(contact.grid, camera, elevation_steps=elevation)
    bottom = (ground[0] + track.offsetX * factor * contact.visual_scale_x,
              ground[1] + (body_rig(data, contact).origin_y_from_ground + track.offsetY) * factor)
    return AnimationDrawCommand(
        painter_key(contact.grid, elevation_steps=elevation, quadrant=camera.quadrant,
                    role="action_strip", identity=(str(cue.event_uuid), track.id)),
        image, (round(bottom[0] - image.width / 2), round(bottom[1] - image.height)), 0,
        (str(cue.event_uuid), contact.grid, asset.assetId, "current", None, "authored",
         "action_strip", elevation, track.id, frame),
    )


def action_media_draw_commands(sample: ActionStripSample, rows: Mapping[str, pygame.Surface],
                               camera: Camera) -> tuple[AnimationDrawCommand, ...]:
    """Both authored media representations share the existing track/clock."""
    cue, asset = sample.cue, sample.cue.asset
    if not isinstance(asset, ParticleMediaAsset):
        return (action_strip_draw_command(sample, rows, camera),)
    result = []
    for particle in sample_particles(sample, asset):
        head = project_screen(particle.grid, camera, elevation_steps=particle.elevation)
        previous = project_screen(particle.previous_grid, camera, elevation_steps=particle.previous_elevation)
        dx, dy = head[0] - previous[0], head[1] - previous[1]
        distance = hypot(dx, dy)
        ux, uy = (dx / distance, dy / distance) if distance else (1.0, 0.0)
        factor = camera.zoom * cue.track.scale
        length = min(asset.tailMaxPx * factor, max(asset.tailMinPx * factor, distance))
        size = particle.size * camera.zoom
        snap = asset.snapPx * camera.zoom
        head = (round(head[0] / snap) * snap, round(head[1] / snap) * snap)

        def polygon(left: float, top: float, right: float, bottom: float):
            return tuple((head[0] + x * ux - y * uy, head[1] + x * uy + y * ux)
                         for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)))

        body = (tuple(project_screen((particle.grid[0] + x, particle.grid[1] + y), camera,
                      elevation_steps=particle.elevation) for x, y in particle.fragment)
                if particle.fragment else polygon(-length, -size, 2 * factor, size))
        highlight = polygon(-factor, -size, factor, -size + max(factor, size * .6))
        left, top = floor(min(p[0] for p in body)), floor(min(p[1] for p in body))
        right, bottom = ceil(max(p[0] for p in body)), ceil(max(p[1] for p in body))
        image = pygame.Surface((max(1, right - left + 1), max(1, bottom - top + 1)), pygame.SRCALPHA)
        for shape, color in ((body, asset.colors[0]), (highlight, asset.colors[1])):
            pygame.draw.polygon(image, _rgb(color), tuple((x - left, y - top) for x, y in shape))
        result.append(AnimationDrawCommand(painter_key(particle.grid, elevation_steps=particle.elevation,
            quadrant=camera.quadrant, role="action_strip", identity=(str(cue.event_uuid), str(particle.identity))),
            image, (left, top), 0, (str(cue.event_uuid), particle.grid, asset.assetId, "current", None, "authored",
                                 "particle", particle.elevation, cue.track.id, particle.identity)))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class AnimationMedia:
    appearances: Mapping[str, tuple[RigLayer, ...]]
    # Cropped rows own their pixels; no full atlas remains live after preload.
    body_rows: Mapping[tuple[str, str, str, int], pygame.Surface]
    projectile_rows: Mapping[tuple[str, int], pygame.Surface]
    font: pygame.font.Font
    area: AreaMedia | None = None


def _rgb(color: int) -> tuple[int, int, int]:
    return color >> 16 & 255, color >> 8 & 255, color & 255


def _colored(frame: pygame.Surface, tint: int, source_hue: float | None = None) -> pygame.Surface:
    result = frame.copy()
    if source_hue is None:
        if tint != 0xFFFFFF:
            result.fill((*_rgb(tint), 255), special_flags=pygame.BLEND_RGBA_MULT)
        return result
    # Pixi HslAdjustmentFilter uses rotation about the RGB grey axis, not HLS
    # conversion. Match that shader with saturation/lightness adjustments zero.
    angle = (rgb_to_hsv(*[value / 255 for value in _rgb(tint)])[0] * 360 - source_hue) * pi / 180
    rgb = pygame.surfarray.pixels3d(result)
    values = rgb.astype(np.float32)
    axis = np.full(3, 1 / sqrt(3))
    rotated = (values * cos(angle) + np.cross(axis, values) * sin(angle)
               + axis * np.sum(values * axis, axis=2, keepdims=True) * (1 - cos(angle)))
    rgb[:] = np.clip(np.rint(rotated), 0, 255).astype(np.uint8)
    del rgb
    return result


def _cast_row_key(layer: StudioActorLayer) -> str:
    return layer.sourceSheet or f"cast:{layer.category}:{layer.colors.primary}:{layer.colors.secondary}"


def _load_cast_rows(data: AnimationData, contact: ActorContact, clip_name: str,
                    facing: Facing8, layers: Sequence[StudioActorLayer | None], rows: LoadedBodyRows) -> None:
    """Resolve isolated overlays once; sampling only selects authored frames."""
    rig = body_rig(data, contact)
    clip = body_clip(data, contact, clip_name)
    facings = {rig.facing_rows[view_facing(facing, quadrant, data)] for quadrant in range(4)}
    for layer in layers:
        if layer is None or not layer.enabled or layer.hidden:
            continue
        key = _cast_row_key(layer)
        missing = [row for row in facings if (contact.rig_id, clip_name, key, row) not in rows]
        if not missing:
            continue
        sheet = pygame.image.load(data.resources[layer.sourceSheet or clip.sheets[layer.category]]).convert_alpha()
        for row in missing:
            image = sheet.subsurface((0, row * rig.cell_height, clip.frames * rig.cell_width, rig.cell_height)).copy()
            if layer.sourceSheet is None:
                image = _colored(image, layer.colors.primary, data.vfx_source_hues.get(layer.category))
                if layer.category == "Magic3" and layer.colors.secondary is not None:
                    rgb = pygame.surfarray.pixels3d(image)
                    white = np.linalg.norm(rgb.astype(np.float32) / 255 - 1, axis=2) < .5
                    rgb[white] = _rgb(layer.colors.secondary)
                    del rgb
            rows[contact.rig_id, clip_name, key, row] = image


def _actor_media_requests(data: AnimationData, actors: tuple[ActorMediaRequest, ...], *,
                          all_facings: bool = False,
                          ) -> dict[tuple[str, str, str], set[int]]:
    body_requests: dict[tuple[str, str, str], set[int]] = {}
    for contact, layers, clips in actors:
        rig = body_rig(data, contact)
        slots = [layer.slot for layer in layers]
        if len(slots) != len(set(slots)) or "body" not in slots:
            raise ValueError("rig appearance requires a body and unique slots")
        rows = (set(rig.facing_rows.values()) if all_facings else
                {rig.facing_rows[view_facing(contact.facing, quadrant, data)] for quadrant in range(4)})
        for layer in layers:
            if layer.category not in rig.slot_categories.get(layer.slot, ()):
                raise ValueError(f"invalid rig slot/category: {contact.rig_id}/{layer.slot}/{layer.category}")
            if not 0 <= layer.alpha <= 1 or not 0 <= layer.tint <= 0xFFFFFF:
                raise ValueError("rig layer alpha/tint must be bounded")
            if layer.slot != "shadow" and layer.alpha != 1:
                raise ValueError("source equipment opacity is fixed; only shadow authors alpha")
            for clip in clips:
                binding = body_clip(data, contact, clip)
                if layer.category not in binding.sheets:
                    raise ValueError(f"missing required rig layer: {contact.rig_id}/{clip}/{layer.category}")
                body_requests.setdefault((contact.rig_id, clip, layer.category), set()).update(rows)
    return body_requests


def _load_body_rows(data: AnimationData, requests: Mapping[tuple[str, str, str], set[int]],
                    body_rows: LoadedBodyRows) -> BodyRows:
    for (rig_id, clip, category), rows in requests.items():
        missing = rows - {row for row in rows if (rig_id, clip, category, row) in body_rows}
        if not missing:
            continue
        rig = data.rigs[rig_id]
        binding = rig.clips[clip]
        url = binding.sheets[category]
        if url not in data.resources:
            raise ValueError(f"missing required rig media: {url}")
        sheet = pygame.image.load(data.resources[url]).convert_alpha()
        expected = rig.cell_width * binding.frames, rig.cell_height * len(rig.facing_rows)
        for row in missing:
            body_rows[rig_id, clip, category, row] = sheet.subsurface(
                (0, row * rig.cell_height, expected[0], rig.cell_height)
            ).copy()
    return MappingProxyType(body_rows)


def load_actor_media(data: AnimationData, requests: tuple[ActorMediaRequest, ...], *,
                     body_rows: LoadedBodyRows | None = None,
                     all_facings: bool = False) -> BodyRows:
    """Add missing rows to the caller's session media; appearances stay historical.

    The supplied map belongs to one AnimationData and Pygame display session.
    Loaded surfaces are read-only sources for per-frame compositing.
    """
    return _load_body_rows(data, _actor_media_requests(data, requests, all_facings=all_facings),
                           {} if body_rows is None else body_rows)


def load_attack_media(timeline: AttackTimeline, appearances: Mapping[str, tuple[RigLayer, ...]], *,
                      body_rows: LoadedBodyRows | None = None) -> BodyRows:
    data = timeline.data
    source_layers = (*appearances[timeline.source.actor_uuid],
                     *(RigLayer(layer.slot, layer.category) for layer in timeline.layers))
    target_clips = {data.death_context.bodyClip if timeline.target.life_state is LifeState.DEAD else "Idle"}
    if timeline.damage_timing is not None:
        target_clips.add(data.death_context.bodyClip if timeline.resulting_life_state is LifeState.DEAD
                         else data.damage_context.bodyClip)
        # Attack HP and life commit at hp_ms, so a lethal hit can begin with
        # TakeDamage before entering the authored death clip.
        if timeline.damage_timing.hp_ms > timeline.damage_timing.start_ms:
            target_clips.add(data.damage_context.bodyClip)
    cache = {} if body_rows is None else body_rows
    loaded = load_actor_media(data, (
        (timeline.source, appearances[timeline.source.actor_uuid], ("Idle", timeline.clip)),
        (timeline.source, source_layers, (timeline.clip,)),
        (timeline.target, appearances[timeline.target.actor_uuid],
         tuple(target_clips)),
    ), body_rows=cache)
    _load_cast_rows(data, timeline.source, timeline.clip, timeline.facing, timeline.layers, cache)
    return loaded


def load_animation_media(timeline: CastTimeline,
                         appearances: Mapping[str, tuple[RigLayer, ...]], *,
                         body_rows: LoadedBodyRows | None = None,
                         area_boundaries: tuple[WorldObjectPlacement, ...] = ()) -> AnimationMedia:
    """Load selected media, reusing the session's existing body rows."""
    data, source, cast = timeline.data, timeline.source, timeline.recipe.cast
    projectile = timeline.recipe.projectile
    assert projectile is not None
    if projectile.sprite is not None and projectile.sprite.blendMode == "screen":
        raise ValueError("screen blend requires a separate pixel parity proof")
    targets = {application.target.actor_uuid: application.target for application in source.applications}
    if set(appearances) != {source.caster.actor_uuid, *targets}:
        raise ValueError("reference media requires one complete appearance per disclosed actor")
    caster_clips = {"Idle", cast.actionClip} | ({cast.recovery.bodyClip} if cast.recovery.enabled else set())
    target_clips = {identity: {data.death_context.bodyClip if target.life_state is LifeState.DEAD else "Idle"}
                    for identity, target in targets.items()}
    for application in timeline.applications:
        if application.damage_start_ms is not None:
            target_clips[application.source.target.actor_uuid].add(
                data.death_context.bodyClip if application.source.resulting_life_state is LifeState.DEAD
                else data.damage_context.bodyClip)
    body_requests = _actor_media_requests(data, (
        (replace(source.caster, facing=timeline.facing), appearances[source.caster.actor_uuid], tuple(caster_clips)),
        *((target, appearances[target.actor_uuid],
           tuple(target_clips[target.actor_uuid])) for target in targets.values()),
    ))
    caster_rig = body_rig(data, source.caster)
    for layer in (cast.weaponGlow, cast.aura, *(cast.effects or ()), cast.slash):
        if layer is None or not layer.enabled or layer.hidden:
            continue
        # This selected media cut uses the source colored-VFX path (Magic2).
        # Other palette policies need their own pixel proof before admission.
        if layer.sourceSheet is None and (layer.category not in data.vfx_source_hues or layer.category in {"Effect2", "Effect4", "Buff9"}):
            raise ValueError(f"cast-layer color policy has no selected pixel proof: {layer.category}")
        if layer.category not in caster_rig.slot_categories.get(layer.slot, ()):
            raise ValueError(f"cast layer is unavailable on rig: {source.caster.rig_id}/{layer.slot}/{layer.category}")
        if layer.category not in body_clip(data, source.caster, cast.actionClip).sheets:
            raise ValueError(f"missing cast layer binding: {source.caster.rig_id}/{cast.actionClip}/{layer.category}")
    cache = {} if body_rows is None else body_rows
    loaded_rows = _load_body_rows(data, body_requests, cache)
    _load_cast_rows(data, source.caster, cast.actionClip, timeline.facing,
                    (cast.weaponGlow, cast.aura, *(cast.effects or ()), cast.slash), cache)
    projectile_rows: dict[tuple[str, int], pygame.Surface] = {}
    for application, interval in ((application, interval) for application in cast_deliveries(timeline)
                                  for interval in application.projectile_intervals):
        asset = interval.asset
        if asset.assetId in data.projectile_storage:
            continue
        rows = {asset.rowOrder.index(view_facing(application.facing, quadrant, data)) for quadrant in range(4)}
        if all((asset.assetId, row) in projectile_rows for row in rows):
            continue
        sheet = pygame.image.load(data.resources[asset.sheet]).convert_alpha()
        expected = asset.frame.width * asset.frame.cols, asset.frame.height * asset.frame.rows
        for row in rows:
            projectile_rows[asset.assetId, row] = sheet.subsurface((0, row * asset.frame.height, expected[0], asset.frame.height)).copy()
    font = pygame.font.SysFont(data.number_style.fontFamily, round(data.number_style.fontSizePx),
                               bold=data.number_style.fontWeight == "bold")
    return AnimationMedia(MappingProxyType(dict(appearances)), loaded_rows,
                          MappingProxyType(projectile_rows), font,
                          AreaMedia(area_boundaries) if timeline.source.ground_target is not None else None)


def _body_image(body: BodySample, contact: ActorContact, appearance: tuple[RigLayer, ...],
                body_rows: BodyRows, data: AnimationData,
                flash: int | None, *, only_shadow: bool | None = None,
                condition: ConditionAppearance | None = None) -> pygame.Surface:
    rig = body_rig(data, contact)
    result = pygame.Surface((rig.cell_width, rig.cell_height), pygame.SRCALPHA)
    layers = {layer.slot: layer for layer in appearance}
    # AnimatedEntity._updateHeadVisibility: ordinary helmets cover hair;
    # crowns Head5/Head8 preserve it. The identity layer remains in appearance.
    if "helmet" in layers and layers["helmet"].category not in {"Head5", "Head8"}:
        layers.pop("head", None)
    if body.hide_weapon:
        layers.pop("weapon", None)
    overlays = {layer.slot: layer for layer in body.cast_layers}
    row = rig.facing_rows[body.facing]
    for slot in rig.slot_order:
        if slot in body.hidden_slots:
            continue
        if only_shadow is not None and (slot == "shadow") != only_shadow:
            continue
        overlay = overlays.get(slot)
        layer = layers.get(slot)
        if overlay is None and layer is None:
            continue
        if overlay is not None:
            category, tint = overlay.category, overlay.colors.primary
        else:
            assert layer is not None
            category, tint = layer.category, layer.tint
        atlas = body_rows[contact.rig_id, body.clip, _cast_row_key(overlay) if overlay else category, row]
        frame = atlas.subsurface((body.frame * rig.cell_width, 0, rig.cell_width, rig.cell_height))
        # Source hit flash clears filters and replaces tint. Never tint already
        # filtered pixels and then try to reconstruct the previous equipment.
        if slot == "shadow":
            assert layer is not None
            colored = frame.copy()
            colored.set_alpha(round(layer.alpha * 255))
        else:
            colored = frame if overlay is not None and flash is None else _colored(frame, flash if flash is not None else tint)
            if (flash is None and condition is not None and condition.body_color is not None
                    and slot in CONDITION_BODY_SLOTS):
                colored = condition_body_color(colored, condition.body_color)
        result.blit(colored, (0, 0))
    return result


def _reference_screen(point: tuple[float, float], camera: Camera, data: AnimationData) -> tuple[float, float]:
    factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
    return point[0] * factor + camera.pan[0], point[1] * factor + camera.pan[1]


def _reference_actor_depth(grid: tuple[float, float], actor_uuid: str) -> float:
    # Preserve source worldDepth.ts bands/ties only for the detached stage.
    encoded = actor_uuid.encode("utf-16-le")
    hashed = 2166136261
    for index in range(0, len(encoded), 2):
        hashed = ((hashed ^ int.from_bytes(encoded[index:index + 2], "little")) * 16777619) & 0xFFFFFFFF
    return sum(grid) * 1024 + 120 + hashed % 1000 / 1000


def _actor_blit(body: BodySample, contact: ActorContact, appearance: tuple[RigLayer, ...], body_rows: BodyRows,
                data: AnimationData, camera: Camera, flash: int | None,
                *, only_shadow: bool | None = None,
                condition: ConditionAppearance | None = None) -> tuple[pygame.Surface, tuple[int, int]]:
    factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
    rig = body_rig(data, contact)
    height = contact.elevation_steps if only_shadow else body_elevation_steps(contact, data)
    ground = project_screen(contact.grid, camera, elevation_steps=height)
    scale = contact.visual_scale * factor
    viewed_body = replace(body, facing=view_facing(body.facing, camera.quadrant, data))
    image = _body_image(viewed_body, contact, appearance, body_rows, data, flash,
                        only_shadow=only_shadow, condition=condition)
    image = pygame.transform.scale(image, (max(1, round(image.width * scale * contact.visual_scale_x)),
                                           max(1, round(image.height * scale))))
    if condition is not None:
        image.set_alpha(round(condition.alpha * 255))
    root_y = ground[1] + rig.origin_y_from_ground * scale
    return image, (round(ground[0] - image.width / 2), round(root_y - image.height))


def projectile_layer_blits(timeline: CastTimeline, effect: ProjectileSample,
                           media: AnimationMedia, camera: Camera,
                           ) -> tuple[tuple[pygame.Surface, tuple[int, int], int], ...]:
    """Ordered shared layer pixels; masks must leave source surfaces untouched."""
    data = timeline.data
    factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
    projectile = timeline.recipe.projectile
    assert projectile is not None and projectile.sprite is not None
    visual = projectile.sprite
    asset = data.projectile_assets[effect.asset_id]
    phase_name = "cast" if effect.phase == "prepare" else effect.phase
    phase = {"cast": asset.phases.cast, "travel": asset.phases.travel,
             "impact": asset.phases.impact}[phase_name]
    assert phase is not None
    layers = projectile_frame_layers(data, asset, phase_name, effect.column - phase.start,
                                     asset.rowOrder[effect.row], visual, media.projectile_rows)
    scale = projectile_phase_scale(projectile, effect.phase) * factor
    # Authored offsets and pivots position art; they do not move world contacts.
    point = _reference_screen(effect.point, camera, data)
    offset = projectile_center_offset(timeline.recipe, asset, effect.phase)
    center = (point[0] + offset[0] * factor, point[1] + offset[1] * factor)
    result = []
    for layer in layers:
        frame = layer.image
        size = (max(1, round(frame.width * scale)), max(1, round(frame.height * scale)))
        if size != frame.get_size():
            frame = pygame.transform.scale(frame, size)
        if effect.rotation_radians != 0:
            frame = pygame.transform.rotate(frame, -degrees(effect.rotation_radians))
        destination = (round(center[0] - frame.width / 2), round(center[1] - frame.height / 2))
        result.append((frame, destination, layer.blend))
    return tuple(result)


def _number_blit(number: NumberSample, contact: ActorContact, font: pygame.font.Font,
                 data: AnimationData, camera: Camera) -> tuple[pygame.Surface, tuple[int, int]]:
    factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
    style = data.badge_style if number.kind == "badge" else data.number_style
    rig = body_rig(data, contact)
    ground = project_screen(contact.grid, camera, elevation_steps=body_elevation_steps(contact, data))
    label = number.label if number.kind == "badge" else f"{number.value} {number.label}".rstrip()
    fill = font.render(label, False, _rgb(number.color))
    stroke = font.render(label, False, _rgb(style.strokeColor))
    radius = round(style.strokeWidthPx)
    text = pygame.Surface((fill.width + radius * 2, fill.height + radius * 2), pygame.SRCALPHA)
    for x, y in ((-radius, 0), (radius, 0), (0, -radius), (0, radius)):
        text.blit(stroke, (radius + x, radius + y))
    text.blit(fill, (radius, radius))
    text = pygame.transform.scale(text, (max(1, round(text.width * factor)), max(1, round(text.height * factor))))
    text.set_alpha(round(number.alpha * 255))
    bottom = ground[1] + ((rig.origin_y_from_ground - style.anchorLiftPx) * contact.visual_scale
                          - style.risePx * number.progress) * factor
    return text, (round(ground[0] - text.width / 2), round(bottom - text.height))


def _geometry_blit(data: AnimationData, effect: GeometryProjectileSample, colors: ElementColors,
                   camera: Camera) -> tuple[pygame.Surface, tuple[int, int], int]:
    """Draw original point geometry; the sampler supplies its visible path."""
    if effect.primitive == "bolt":
        width, alpha = data.bolt_style.strokeWidthPx, data.bolt_style.strokeAlpha
        radius, head_alpha = data.bolt_style.headRadiusPx, data.bolt_style.headAlpha
    else:
        width, alpha = data.dart_style.trailWidthPx, data.dart_style.trailAlpha
        radius, head_alpha = data.dart_style.headRadiusPx, data.dart_style.headAlpha
    factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
    points = tuple(_reference_screen(point, camera, data) for point in effect.trail)
    head = _reference_screen(effect.point, camera, data)
    padding = max(radius, width) * factor + 1
    left = floor(min(point[0] for point in (*points, head)) - padding)
    top = floor(min(point[1] for point in (*points, head)) - padding)
    right = ceil(max(point[0] for point in (*points, head)) + padding)
    bottom = ceil(max(point[1] for point in (*points, head)) + padding)
    image = pygame.Surface((right - left, bottom - top), pygame.SRCALPHA)
    layer = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    local = tuple((round(x - left), round(y - top)) for x, y in points)
    for index, (start, end) in enumerate(zip(local, local[1:])):
        layer.fill((0, 0, 0, 0))
        segment_alpha = alpha if effect.primitive == "bolt" else (index + 1) / len(local) * alpha
        pygame.draw.line(layer, (*_rgb(colors.secondary), round(segment_alpha * 255)),
                         start, end, max(1, round(width * factor)))
        image.blit(layer, (0, 0))
    layer.fill((0, 0, 0, 0))
    pygame.draw.circle(layer, (*_rgb(colors.primary), round(head_alpha * 255)),
                       (round(head[0] - left), round(head[1] - top)),
                       max(1, round(radius * factor)))
    image.blit(layer, (0, 0))
    return image, (left, top), 0


def geometry_draw_command(data: AnimationData, effect: GeometryProjectileSample,
                          colors: ElementColors, contact: tuple[tuple[float, float], float],
                          depth_mode: DepthMode, root_event_uuid: str,
                          camera: Camera) -> AnimationDrawCommand:
    """The same geometry pixels and world-depth command for casts and attacks."""
    image, destination, blend = _geometry_blit(data, effect, colors, camera)
    position, height = contact
    role = "ground_effect" if depth_mode == "ground" else "projectile"
    key = painter_key(position, elevation_steps=height, quadrant=camera.quadrant, role=role,
                      identity=(root_event_uuid, effect.application_id or "", effect.phase))
    if depth_mode == "overlay":
        key = (200, *key[1:])
    return AnimationDrawCommand(key, image, destination, blend,
            (root_event_uuid, position, effect.primitive, "current", None, "authored",
             "projectile", height, effect.phase, None, effect.application_id))


def actor_draw_commands(data: AnimationData, body: BodySample, contact: ActorContact,
                        layers: tuple[RigLayer, ...], body_rows: BodyRows, camera: Camera,
                        *, flash: int | None = None,
                        condition: ConditionAppearance | None = None) -> tuple[AnimationDrawCommand, ...]:
    """Compose one explicitly sampled actor using the map's shared painter."""
    commands: list[AnimationDrawCommand] = []
    for shadow in (True, False):
        if shadow and not any(layer.slot == "shadow" for layer in layers):
            continue
        role = "actor_shadow" if shadow else "actor"
        height = contact.elevation_steps if shadow else body_elevation_steps(contact, data)
        image, destination = _actor_blit(
            body, contact, layers, body_rows, data, camera, flash, only_shadow=shadow, condition=condition,
        )
        commands.append(AnimationDrawCommand(
            painter_key(contact.grid, elevation_steps=height,
                        quadrant=camera.quadrant, role=role, identity=contact.actor_uuid),
            image, destination, 0,
            (contact.actor_uuid, contact.grid, contact.rig_id, "current", None, "authored",
             role, height, body.clip, body.frame),
        ))
    return tuple(commands)


def animation_draw_commands(timeline: CastTimeline, sample: CastSample,
                            media: AnimationMedia, camera: Camera, *,
                            condition_appearances: Mapping[str, ConditionAppearance] | None = None,
                            ) -> tuple[AnimationDrawCommand, ...]:
    """Join sampled actors and effects to the map's existing painter ordering."""
    data, source = timeline.data, timeline.source
    contacts = {source.caster.actor_uuid: source.caster,
                **{application.target.actor_uuid: application.target for application in source.applications}}
    flashes = {vital.actor_uuid: vital.flash for vital in sample.vitals}
    commands: list[AnimationDrawCommand] = []
    for body in sample.bodies:
        contact = contacts[body.actor_uuid]
        commands.extend(actor_draw_commands(
            data, body, contact, media.appearances[body.actor_uuid], media.body_rows, camera,
            flash=flashes.get(body.actor_uuid),
            condition=condition_appearances.get(body.actor_uuid) if condition_appearances is not None else None,
        ))
    projectile = timeline.recipe.projectile
    assert projectile is not None
    for reference_effect in sample.projectiles:
        match reference_effect:
            case ProjectileSample():
                effect = project_projectile(timeline, reference_effect, camera.quadrant)
                layers = projectile_layer_blits(timeline, effect, media, camera)
                visual, frame = effect.asset_id, effect.column
            case GeometryProjectileSample():
                effect = project_geometry_projectile(timeline, reference_effect, camera.quadrant)
                commands.append(geometry_draw_command(
                    data, effect, timeline.recipe.elementColors,
                    projectile_contact(timeline, effect, quadrant=camera.quadrant),
                    projectile.depthMode, source.root_event_uuid, camera,
                ))
                continue
        position, height = projectile_contact(timeline, effect, quadrant=camera.quadrant)
        role = "ground_effect" if projectile.depthMode == "ground" else "projectile"
        key = painter_key(position, elevation_steps=height, quadrant=camera.quadrant,
                          role=role, identity=(source.root_event_uuid, effect.application_id or "", effect.phase))
        if projectile.depthMode == "overlay":
            key = (200, *key[1:])
        commands.extend(AnimationDrawCommand(
            key, image, destination, blend,
            (source.root_event_uuid, position, visual, "current", None, "authored",
             "projectile", height, effect.phase, frame, effect.application_id),
            AreaLayer(source.ground_target.grid, source.ground_target.elevation_steps, media.area)
            if source.ground_target is not None and effect.phase == "impact" else None,
        ) for image, destination, blend in layers)
    commands.extend(number_draw_commands(data, sample.numbers, contacts, media.font, camera))
    return tuple(commands)


def number_draw_commands(data: AnimationData, numbers: tuple[NumberSample, ...],
                         contacts: Mapping[str, ActorContact], font: pygame.font.Font,
                         camera: Camera, *, badge_font: pygame.font.Font | None = None,
                         ) -> tuple[AnimationDrawCommand, ...]:
    """The same authored feedback drawer for spell and weapon consequences."""
    commands: list[AnimationDrawCommand] = []
    for number in numbers:
        contact = contacts[number.actor_uuid]
        if number.kind == "badge" and badge_font is None:
            raise ValueError("badge feedback requires its authored font")
        selected_font = badge_font if number.kind == "badge" else font
        assert selected_font is not None
        image, destination = _number_blit(number, contact, selected_font, data, camera)
        height = body_elevation_steps(contact, data)
        key = painter_key(contact.grid, elevation_steps=height,
                          quadrant=camera.quadrant, role="actor",
                          identity=(contact.actor_uuid, number.application_id or ""))
        commands.append(AnimationDrawCommand(
            (210, *key[1:]), image, destination, 0,
            (contact.actor_uuid, contact.grid, number.label, "current", None, "authored",
             "floating_number", height, number.value, number.progress, number.application_id),
        ))
    return tuple(commands)


def actor_screen_bounds(commands: Sequence[AnimationDrawCommand]) -> dict[str, pygame.Rect]:
    """Visible body pixels, excluding shadows and the atlas's empty padding."""
    bounds: dict[str, pygame.Rect] = {}
    for _, image, position, _, evidence, _ in commands:
        if evidence[6] != "actor" or image.get_alpha() == 0:
            continue
        rect = image.get_bounding_rect(min_alpha=1).move(position)
        if rect.width == 0 or rect.height == 0:
            continue
        identity = str(evidence[0])
        bounds[identity] = bounds[identity].union(rect) if identity in bounds else rect
    return bounds


def place_feedback_rect(preferred: pygame.Rect, anchor: pygame.Rect | None,
                        obstacles: Sequence[pygame.Rect], viewport: pygame.Rect, *,
                        gap: int = 6) -> pygame.Rect:
    """Keep a label clear of bodies: above first, below when the top is full."""
    left = max(viewport.left, min(preferred.left, viewport.right - preferred.width))
    above = preferred.copy()
    above.left = left
    if anchor is not None:
        above.bottom = min(above.bottom, anchor.top - gap)
    while collisions := [rect for rect in obstacles if above.colliderect(rect.inflate(gap * 2, gap * 2))]:
        above.bottom = min(rect.top for rect in collisions) - gap
    if viewport.contains(above):
        return above
    below = preferred.copy()
    below.left = left
    below.top = max(viewport.top, anchor.bottom + gap if anchor is not None else preferred.top)
    while collisions := [rect for rect in obstacles if below.colliderect(rect.inflate(gap * 2, gap * 2))]:
        below.top = max(rect.bottom for rect in collisions) + gap
    if viewport.contains(below):
        return below
    # When the viewport has no clear vertical slot, retain as much visible
    # text as possible without changing its authored font or rasterization.
    candidates = (above.clamp(viewport), below.clamp(viewport))
    return min(candidates, key=lambda candidate: sum(
        candidate.clip(rect).width * candidate.clip(rect).height for rect in obstacles))


def arrange_feedback_commands(commands: Sequence[AnimationDrawCommand],
                               actor_bounds: Mapping[str, pygame.Rect], viewport: pygame.Rect,
                               ) -> tuple[AnimationDrawCommand, ...]:
    """Arrange simultaneous feedback together; surfaces and authored time stay exact."""
    occupied = list(actor_bounds.values())
    arranged: list[AnimationDrawCommand] = []
    for command in commands:
        _, image, position, _, evidence, _ = command
        if evidence[6] != "floating_number":
            arranged.append(command)
            continue
        rect = place_feedback_rect(image.get_rect(topleft=position),
                                   actor_bounds.get(str(evidence[0])), occupied, viewport)
        occupied.append(rect)
        # The trace's screen_xy comes from this actual draw position. Retained
        # world contact, application identity and progress remain unchanged.
        arranged.append(command._replace(destination=rect.topleft))
    return tuple(arranged)


def attack_draw_commands(timeline: AttackTimeline, sample: AttackSample,
                         appearances: Mapping[str, tuple[RigLayer, ...]], media: BodyRows,
                         font: pygame.font.Font, badge_font: pygame.font.Font,
                         camera: Camera, *,
                         condition_appearances: Mapping[str, ConditionAppearance] | None = None,
                         ) -> tuple[AnimationDrawCommand, ...]:
    contacts = {contact.actor_uuid: contact for contact in (timeline.source, timeline.target)}
    flashes = {vital.actor_uuid: vital.flash for vital in sample.vitals}
    commands = tuple(command for body in sample.bodies for command in actor_draw_commands(
        timeline.data, body, contacts[body.actor_uuid], appearances[body.actor_uuid], media, camera,
        flash=flashes.get(body.actor_uuid),
        condition=condition_appearances.get(body.actor_uuid) if condition_appearances is not None else None,
    ))
    projectile_commands = ()
    if timeline.projectile is not None:
        projectile_commands = tuple(geometry_draw_command(
            timeline.data, effect, timeline.projectile.element_colors,
            attack_projectile_contact(timeline, effect, camera.quadrant),
            timeline.projectile.recipe.depthMode, timeline.root_event_uuid, camera,
        ) for reference in sample.projectiles
          for effect in (project_attack_projectile(timeline, reference, camera.quadrant),))
    return (*commands, *projectile_commands, *number_draw_commands(timeline.data, sample.numbers, contacts, font, camera,
                                             badge_font=badge_font))


def draw_animation(surface: pygame.Surface, timeline: CastTimeline, sample: CastSample,
                   media: AnimationMedia, camera: Camera) -> None:
    """Keep the detached source-stage ordering using the shared image builders."""
    data, source = timeline.data, timeline.source
    contacts = {source.caster.actor_uuid: source.caster,
                **{application.target.actor_uuid: application.target for application in source.applications}}
    flashes = {vital.actor_uuid: vital.flash for vital in sample.vitals}
    draws: list[tuple[float, pygame.Surface, tuple[int, int], int]] = []
    for body in sample.bodies:
        contact = contacts[body.actor_uuid]
        # A lifted detached-stage body still leaves its shadow on support.
        for shadow in (True, False) if contact.body_lift_px else (None,):
            image, destination = _actor_blit(
                body, contact, media.appearances[body.actor_uuid], media.body_rows, data, camera,
                flashes.get(body.actor_uuid), only_shadow=shadow,
            )
            draws.append((_reference_actor_depth(rotate_position(contact.grid, camera.quadrant), contact.actor_uuid),
                          image, destination, 0))
    projectile = timeline.recipe.projectile
    assert projectile is not None
    for reference_effect in sample.projectiles:
        match reference_effect:
            case ProjectileSample():
                effect = project_projectile(timeline, reference_effect, camera.quadrant)
                layers = projectile_layer_blits(timeline, effect, media, camera)
            case GeometryProjectileSample():
                effect = project_geometry_projectile(timeline, reference_effect, camera.quadrant)
                layers = (_geometry_blit(data, effect, timeline.recipe.elementColors, camera),)
        _, support_height = projectile_contact(timeline, effect, quadrant=camera.quadrant)
        unlifted_y = effect.point[1] + support_height * HEIGHT_STEP_PIXELS * data.rig.TILE_W / TILE_WIDTH
        depth = {"overlay": float("inf"), "ground": -float("inf"),
                 "world": unlifted_y / (data.rig.TILE_H / 2) * 1024 + 240}[projectile.depthMode]
        for image, destination, blend in layers:
            ground = source.ground_target
            if ground is not None and effect.phase == "impact" and media.area is not None:
                image = mask_ground_area(image, destination, ground.grid, ground.elevation_steps, camera, media.area)
            draws.append((depth, image, destination, blend))
    for _, image, destination, blend in sorted(draws, key=lambda item: item[0]):
        surface.blit(image, destination, special_flags=blend)
    for number in sample.numbers:
        image, destination = _number_blit(number, contacts[number.actor_uuid], media.font, data, camera)
        surface.blit(image, destination)
