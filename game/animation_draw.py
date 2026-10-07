"""Pygame composition of sampled actor rigs on the map or reference stage.

Actor and legacy atlas rows load before playback; finite projectile frames use
bounded shared storage. Authored clocks and facts remain in game.animation.
"""

from __future__ import annotations

from colorsys import rgb_to_hsv
from dataclasses import dataclass, replace
from math import ceil, cos, floor, hypot, pi, sin, sqrt
from types import MappingProxyType
from typing import Literal, Mapping, NamedTuple, Sequence
from uuid import UUID
from weakref import WeakKeyDictionary

import numpy as np
import pygame

from dnd.core.life_types import LifeState
from dnd.types.event_facts import WorldTileState
from game.animation import (
    effective_layer_palette,
    pose_attachment_anchors, ActorContact, ObjectContact, BodySample, CastSample, CastTimeline, GeometryProjectileSample, NumberSample, feedback_identity, cast_actor_contacts,
    ProjectileSample, body_clip, body_elevation_steps, body_rig, project_geometry_projectile, project_projectile,
    projectile_registration, projectile_phase_scale, projectile_contact, view_facing, cast_deliveries, actor_rest_pose, death_body_context,
)
from game.animation_types import AnimationData, BodyRig, DepthMode, ElementColors, Facing8, ItemAttachmentStart, PaletteTreatment, ParticleMediaAsset, StudioActorLayer, RigLayer as RigLayer
from game.action_media import ActionStripCue, ActionStripSample
from game.attack import AttackSample, AttackTimeline, attack_actor_contacts, attack_projectile_contact, project_attack_projectile
from game.weapon_trail_media import weapon_trail_draw_commands
from game.condition_animation import ConditionAppearance, ConditionRigLayer, condition_body_pose, condition_contact
from game.condition_types import ConditionAppearanceLayer, ConditionLiveCopies
from game.item_effects import item_material
from game.item_draw import compose_item_attachments
from game.body_effects import distort_body, ghost_body, reveal_body, silhouette_dust, absence_silhouette
from game.body_pose_types import BodyTrailPose
from game.condition_draw import (CONDITION_BODY_SLOTS, body_ramp_cacheable, compose_condition_layers, condition_body_color,
    condition_body_ramp, blend_body_ramp, condition_body_outline)
from game.projectile_media import projectile_frame_layers
from game.media_coverage import covered_media
from game.cast_media import cast_media_draw_commands, preload_cast_media, cast_surface_volume
from game.spell_palette import cached_palette, palette_noise, recolor_palette, retain_palette
from game.particle_media import sample_particles, sample_vapor
from game.blood_draw import blood_particle_image
from game.area_media import AreaLayer, AreaMedia, mask_ground_area
from game.animation_types import AreaSolid
from game.draw_commands import DrawCommand as AnimationDrawCommand
from game.interaction_types import SelectionCoverage, WorldHit
from game.interaction_frame import align_coverage
from game.media_blend import SCREEN_BLEND, blit_media
from game.directed_media import directed_draw_commands, preload_directed_media
from game.registered_media import registered_media_samples, transform_registered_part
from game.device_draw import device_draw_command
from dnd.types.world_placement import WorldObjectPlacement
from game.projection import Camera, HEIGHT_STEP_PIXELS, TILE_WIDTH, painter_key, project_screen, rotate_position


BodyRows = Mapping[tuple[str, str, str, int], pygame.Surface]
LoadedBodyRows = dict[tuple[str, str, str, int], pygame.Surface]
ActorMediaRequest = tuple[ActorContact, tuple[RigLayer, ...], tuple[str, ...]]

# Immutable loaded rows own this geometry; weak keys do not retain old media.
_MARKER_ROW_TOPS: WeakKeyDictionary[pygame.Surface, int | None] = WeakKeyDictionary()


def _marker_row_top(row: pygame.Surface) -> int | None:
    if row not in _MARKER_ROW_TOPS:
        bounds = row.get_bounding_rect()
        _MARKER_ROW_TOPS[row] = bounds.top if bounds else None
    return _MARKER_ROW_TOPS[row]


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
    colors = cue.particle_colors or asset.colors
    for particle in sample_particles(sample, asset):
        if cue.response is not None:
            image, destination = blood_particle_image(particle, cue.response, asset,
                cue.particle_colors or cue.response.colors, camera, cue.track.scale)
            result.append(AnimationDrawCommand(painter_key(particle.grid, elevation_steps=particle.elevation,
                quadrant=camera.quadrant, role="action_strip", identity=(str(cue.event_uuid), str(particle.identity))),
                image, destination, 0, (str(cue.event_uuid), particle.grid, asset.assetId, "current", None, "authored",
                    "particle", particle.elevation, cue.track.id, particle.identity)))
            continue
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
        for shape, color in ((body, colors[0]), (highlight, colors[1])):
            pygame.draw.polygon(image, _rgb(color), tuple((x - left, y - top) for x, y in shape))
        result.append(AnimationDrawCommand(painter_key(particle.grid, elevation_steps=particle.elevation,
            quadrant=camera.quadrant, role="action_strip", identity=(str(cue.event_uuid), str(particle.identity))),
            image, (left, top), 0, (str(cue.event_uuid), particle.grid, asset.assetId, "current", None, "authored",
                                 "particle", particle.elevation, cue.track.id, particle.identity)))
    for vapor in sample_vapor(sample, asset):
        point = project_screen(vapor.grid, camera, elevation_steps=vapor.elevation)
        size = max(1, round(vapor.size * camera.zoom))
        image = pygame.Surface((size*2,size*2), pygame.SRCALPHA)
        image.fill((*_rgb(vapor.color), round(vapor.alpha * 255)))
        result.append(AnimationDrawCommand(painter_key(vapor.grid, elevation_steps=vapor.elevation,
            quadrant=camera.quadrant, role="action_strip", identity=(str(cue.event_uuid), "vapor", str(vapor.identity))),
            image, (round(point[0]-size), round(point[1]-size)), 0,
            (str(cue.event_uuid), vapor.grid, asset.assetId, "current", None, "authored",
                "blood_vapor", vapor.elevation, cue.track.id, vapor.identity)))
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
    palette = effective_layer_palette(layer)
    treatment = "source" if palette is None else palette.model_dump_json()
    return f"cast:{layer.sourceSheet or layer.category}:{treatment}"


def load_cast_rows(data: AnimationData, contact: ActorContact, clip_name: str,
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
            palette = effective_layer_palette(layer)
            if palette is not None:
                image = recolor_palette(image, palette,
                    noise=(palette_noise(data.resources[palette.noiseSheet])
                           if palette.noiseSheet is not None else None),
                    cell_size=(rig.cell_width, rig.cell_height))
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
        for clip in clips:
            for layer in body_clip(data, contact, clip).layers:
                body_requests.setdefault((contact.rig_id, clip, layer.category), set()).update(rows)
            # A membership can enter/leave inside this head. Preload compatible
            # authored extras with its requested body clips, never during drawing.
            for recipe in data.condition_recipes.values():
                for extra in recipe.persistent.appearanceLayers:
                    if (extra.category in rig.slot_categories.get(extra.slot, ())
                            and not (extra.anatomy == "wings" and rig.native_wings)):
                        if extra.category not in rig.clips[clip].sheets:
                            raise ValueError(f"missing condition appearance bank: {contact.rig_id}/{clip}/{extra.category}")
                        body_requests.setdefault((contact.rig_id, clip, extra.category), set()).update(rows)
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
        for recipe in data.condition_recipes.values():
            for extra in recipe.persistent.appearanceLayers:
                if extra.category == category and extra.tint2 is None and extra.tint3 is None:
                    for row in rows:
                        _appearance_material(body_rows[rig_id, clip, category, row], extra,
                                             (data.media_root, rig_id, clip, row))
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
                     *(RigLayer(layer.slot, layer.category) for layer in timeline.layers if layer.sourceSheet is None))
    for layer in timeline.layers:
        if layer.sourceSheet is not None:
            if layer.slot not in body_rig(data, timeline.source).slot_order:
                raise ValueError(f"literal attack layer has no rig slot: {layer.slot}")
            if layer.sourceSheet not in data.resources:
                raise ValueError(f"missing literal attack layer resource: {layer.sourceSheet}")
    target_clips = {"Idle"}
    if isinstance(timeline.target, ActorContact):
        target_clips.add(actor_rest_pose(data, timeline.target) or "Idle")
    if timeline.damage_timing is not None:
        target_clips.add(death_body_context(data, timeline.target).actor.clip
                         if timeline.resulting_life_state is LifeState.DEAD and isinstance(timeline.target, ActorContact)
                         else data.damage_context.bodyClip)
        # Attack HP and life commit at hp_ms, so a lethal hit can begin with
        # TakeDamage before entering the authored death clip.
        if timeline.damage_timing.hp_ms > timeline.damage_timing.start_ms:
            target_clips.add(data.damage_context.bodyClip)
        if timeline.damage_timing.life_body is not None:
            target_clips.add(timeline.damage_timing.life_body.clip)
    cache = {} if body_rows is None else body_rows
    loaded = load_actor_media(data, (
        (timeline.source, appearances[timeline.source.actor_uuid], ("Idle", timeline.clip)),
        (timeline.source, source_layers, (timeline.clip,)),
        *(((timeline.target, appearances[timeline.target.actor_uuid], tuple(target_clips)),)
            if isinstance(timeline.target, ActorContact) else ()),
    ), body_rows=cache)
    load_cast_rows(data, timeline.source, timeline.clip, timeline.facing, timeline.layers, cache)
    return loaded


def load_animation_media(timeline: CastTimeline,
                         appearances: Mapping[str, tuple[RigLayer, ...]], *,
                         body_rows: LoadedBodyRows | None = None,
                         area_boundaries: tuple[WorldObjectPlacement, ...] = (),
                         area_solids: tuple[AreaSolid, ...] = (),
                         area_supports: tuple[WorldTileState, ...] = ()) -> AnimationMedia:
    """Load selected media, reusing the session's existing body rows."""
    data, source, cast = timeline.data, timeline.source, timeline.recipe.cast
    preload_directed_media(timeline)
    projectile = timeline.recipe.projectile
    if projectile is not None and projectile.sprite is not None and projectile.sprite.blendMode == "screen":
        raise ValueError("screen blend requires a separate pixel parity proof")
    targets = {application.target.actor_uuid: application.target for application in source.applications
               if isinstance(application.target, ActorContact)}
    if set(appearances) != {source.caster.actor_uuid, *targets}:
        raise ValueError("reference media requires one complete appearance per disclosed actor")
    caster_clips = {"Idle", cast.actionClip} | ({cast.recovery.bodyClip} if cast.recovery.enabled else set())
    target_clips = {identity: {actor_rest_pose(data, target) or "Idle", "Idle"}
                    for identity, target in targets.items()}
    for application in timeline.applications:
        if isinstance(application.source.target, ActorContact) and application.damage_start_ms is not None:
            target_clips[application.source.target.actor_uuid].add(
                death_body_context(data, application.source.target).actor.clip if application.source.resulting_life_state is LifeState.DEAD
                else data.damage_context.bodyClip)
        if isinstance(application.source.target, ActorContact) and application.life_body is not None:
            target_clips[application.source.target.actor_uuid].add(application.life_body.clip)
    body_requests = _actor_media_requests(data, (
        (replace(source.caster, facing=timeline.facing), appearances[source.caster.actor_uuid], tuple(caster_clips)),
        *((target, appearances[target.actor_uuid],
           tuple(target_clips[target.actor_uuid])) for target in targets.values()),
    ))
    caster_rig = body_rig(data, source.caster)
    for layer in (cast.weaponGlow, cast.aura, *(cast.effects or ()), cast.slash):
        if layer is None or not layer.enabled or layer.hidden:
            continue
        effective_layer_palette(layer)  # Validate the same treatment used by loading and its cache.
        if layer.category not in caster_rig.slot_categories.get(layer.slot, ()):
            raise ValueError(f"cast layer is unavailable on rig: {source.caster.rig_id}/{layer.slot}/{layer.category}")
        if layer.category not in body_clip(data, source.caster, cast.actionClip).sheets:
            raise ValueError(f"missing cast layer binding: {source.caster.rig_id}/{cast.actionClip}/{layer.category}")
    cache = {} if body_rows is None else body_rows
    loaded_rows = _load_body_rows(data, body_requests, cache)
    load_cast_rows(data, source.caster, cast.actionClip, timeline.facing,
                    (cast.weaponGlow, cast.aura, *(cast.effects or ()), cast.slash), cache)
    for application in timeline.applications:
        damage = application.damage
        if (damage is None or not damage.hitFlash.enabled or damage.hitFlash.palette is None
                or not isinstance(application.source.target, ActorContact)):
            continue
        target = application.source.target
        clip = (death_body_context(data, target).actor.clip if target.life_state is LifeState.DEAD
                or application.source.resulting_life_state is LifeState.DEAD else data.damage_context.bodyClip)
        for quadrant in range(4):
            pose = BodySample(target.actor_uuid, clip, 0, view_facing(target.facing, quadrant, data))
            _body_image(pose, target, appearances[target.actor_uuid], loaded_rows, data,
                        damage.hitFlash.palette, only_shadow=False)
    projectile_rows: dict[tuple[str, int], pygame.Surface] = {}
    for application, interval in ((application, interval) for application in cast_deliveries(timeline)
                                  for interval in application.projectile_intervals):
        asset = interval.asset
        if asset.assetId in data.projectile_storage:
            continue
        rows = (set(range(len(asset.rowOrder))) if projectile is not None and projectile.orientation.directionSource == "tangent"
                else {asset.rowOrder.index(view_facing(application.facing, quadrant, data)) for quadrant in range(4)})
        if all((asset.assetId, row) in projectile_rows for row in rows):
            continue
        sheet = pygame.image.load(data.resources[asset.sheet]).convert_alpha()
        expected = asset.frame.width * asset.frame.cols, asset.frame.height * asset.frame.rows
        for row in rows:
            projectile_rows[asset.assetId, row] = sheet.subsurface((0, row * asset.frame.height, expected[0], asset.frame.height)).copy()
    preload_cast_media(timeline)
    font = pygame.font.SysFont(data.number_style.fontFamily, round(data.number_style.fontSizePx),
                               bold=data.number_style.fontWeight == "bold")
    return AnimationMedia(MappingProxyType(dict(appearances)), loaded_rows,
                          MappingProxyType(projectile_rows), font,
                          AreaMedia(area_boundaries, area_solids, area_supports,
                                    admitted=timeline.source.resolved_area_positions)
                          if timeline.source.ground_target is not None else None)


def _appearance_material(image: pygame.Surface, layer: ConditionAppearanceLayer,
                         source_key: tuple[object, ...]) -> pygame.Surface:
    """Existing palette-zone replacement; bounded emission preserves source alpha."""
    key = ("condition-appearance", *source_key, layer)
    cached = cached_palette(key)
    if cached is not None:
        return cached
    colored = item_material(image, (), layer.slot, {}, category=layer.category, base_tint=layer.tint)
    if layer.glowStrength:
        colored = colored.copy()
        pixels = pygame.surfarray.pixels3d(colored)
        pixels[:] = np.clip(np.rint(pixels.astype(float)
            + np.array(_rgb(layer.tint)) * layer.glowStrength), 0, 255).astype(np.uint8)
        del pixels
    return retain_palette(key, colored)


def condition_rig_layers(rig: BodyRig, appearance: tuple[RigLayer, ...],
                         condition: ConditionAppearance | None) -> tuple[ConditionRigLayer, ...]:
    """Compatible transient anatomy adds to equipment without occupying its slot."""
    if condition is None:
        return ()
    equipped = {layer.category for layer in appearance}
    return tuple(row for row in condition.rig_layers
        if row.layer.category not in equipped
        and row.layer.category in rig.slot_categories.get(row.layer.slot, ())
        and not (row.layer.anatomy == "wings" and rig.native_wings))


def _body_image(body: BodySample, contact: ActorContact, appearance: tuple[RigLayer, ...],
                body_rows: BodyRows, data: AnimationData,
                flash: int | PaletteTreatment | None, *, only_shadow: bool | None = None,
                physical_only: bool = False,
                condition: ConditionAppearance | None = None) -> pygame.Surface:
    rig = body_rig(data, contact)
    extra_layers = condition_rig_layers(rig, appearance, condition)
    treatment = flash if isinstance(flash, PaletteTreatment) and only_shadow is not True and not physical_only else None
    key = (data.media_root, contact.rig_id, body.clip, body.facing, appearance,
           body.hide_weapon, body.hidden_slots, body.cast_layers, treatment, extra_layers)
    physical_key = ("selection-pose", *key, body.frame)
    if physical_only:
        cached = cached_palette(physical_key)
        if cached is not None:
            return cached
    colored_row = cached_palette(key) if treatment is not None else None
    if colored_row is not None:
        colored = colored_row.subsurface((body.frame * rig.cell_width, 0, rig.cell_width, rig.cell_height))
        if only_shadow is False:
            return colored
        result = _body_image(body, contact, appearance, body_rows, data, None, only_shadow=True)
        result.blit(colored, (0, 0))
        return result
    # Palette mapping is cached per complete pose row, never repeated per frame.
    width = rig.cell_width * body_clip(data, contact, body.clip).frames if treatment else rig.cell_width
    result = pygame.Surface((width, rig.cell_height), pygame.SRCALPHA)
    layers = {layer.slot: layer for layer in (*appearance, *rig.clips[body.clip].layers)}
    # AnimatedEntity._updateHeadVisibility: ordinary helmets cover hair;
    # crowns Head5/Head8 preserve it. The identity layer remains in appearance.
    if "helmet" in layers and layers["helmet"].category not in {"Head5", "Head8"}:
        layers.pop("head", None)
    if body.hide_weapon:
        layers.pop("weapon", None)
    overlays = {layer.slot: layer for layer in body.cast_layers}
    row = rig.facing_rows[body.facing]
    ramped = (_ramp_image(body, contact, appearance, body_rows, data, condition)
              if not physical_only and flash is None and only_shadow is not True and condition is not None
              and condition.body_ramp is not None and condition.ramp_strength > 0 else None)
    material_drawn = False
    for slot in rig.slot_order:
        if physical_only and slot in rig.selection_excluded_slots:
            continue
        if slot in body.hidden_slots:
            continue
        if only_shadow is not None and (slot == "shadow") != only_shadow:
            continue
        if treatment is not None and slot == "shadow":
            continue
        if ramped is not None and slot in CONDITION_BODY_SLOTS:
            if not material_drawn:
                result.blit(ramped, (0, 0))
                material_drawn = True
            continue
        overlay = overlays.get(slot)
        layer = layers.get(slot)
        if physical_only and (overlay is not None or
                layer is not None and layer.category in rig.selection_excluded_categories):
            continue
        for extra in extra_layers:
            if extra.layer.slot != slot or extra.alpha <= 0:
                continue
            atlas = body_rows[contact.rig_id, body.clip, extra.layer.category, row]
            colored = (_colored(atlas, flash) if isinstance(flash, int) else
                atlas if treatment is not None else _appearance_material(atlas, extra.layer,
                    (data.media_root, contact.rig_id, body.clip, row)))
            if treatment is None:
                colored = colored.subsurface((body.frame * rig.cell_width, 0, rig.cell_width, rig.cell_height))
            if extra.alpha != 1:
                colored = colored.copy()
                colored.set_alpha(round(extra.alpha * 255))
            if flash is None and condition is not None and condition.body_color is not None:
                colored = condition_body_color(colored, condition.body_color)
            result.blit(colored, (0, 0))
        if overlay is None and layer is None:
            continue
        if overlay is not None:
            category, tint = overlay.category, overlay.colors.primary
        else:
            assert layer is not None
            category, tint = layer.category, layer.tint
        atlas = body_rows[contact.rig_id, body.clip, _cast_row_key(overlay) if overlay else category, row]
        frame = atlas if treatment is not None else atlas.subsurface((body.frame * rig.cell_width, 0, rig.cell_width, rig.cell_height))
        # Source hit flash clears filters and replaces tint. Never tint already
        # filtered pixels and then try to reconstruct the previous equipment.
        if physical_only:
            colored = frame
        elif slot == "shadow":
            assert layer is not None
            colored = frame.copy()
            colored.set_alpha(round(layer.alpha * 255))
        else:
            if treatment is not None:
                colored = frame if treatment.untinted or overlay is not None else _colored(frame, tint)
            else:
                color = flash if isinstance(flash, int) else tint
                colored = frame if overlay is not None and flash is None else _colored(frame, color)
            if (layer is not None and overlay is None and flash is None
                    and layer.item_uuid is not None):
                colored = item_material(frame, layer.item_effects, slot, data.condition_recipes,
                    category=category, base_tint=tint,
                    owned_modifiers=tuple(row.modifier for row in condition.item_modifiers
                        if row.item_uuid == layer.item_uuid) if condition is not None else (),
                    time_ms=condition.time_ms if condition is not None else 0.,
                    source_key=(data.media_root, contact.rig_id, body.clip, category, row,
                                None if treatment is not None else body.frame))
            if (flash is None and condition is not None and condition.body_color is not None
                    and slot in CONDITION_BODY_SLOTS):
                colored = condition_body_color(colored, condition.body_color)
        blend = (SCREEN_BLEND if overlay is not None and overlay.blendMode == "screen" else
                 pygame.BLEND_RGB_ADD if overlay is not None and overlay.blendMode == "add" else 0)
        blit_media(result, colored, (0, 0), blend)
    if treatment is not None:
        noise = palette_noise(data.resources[treatment.noiseSheet]) if treatment.noiseSheet else None
        colored_row = retain_palette(key, recolor_palette(result, treatment, noise=noise,
            cell_size=(rig.cell_width, rig.cell_height)))
        colored = colored_row.subsurface((body.frame * rig.cell_width, 0, rig.cell_width, rig.cell_height))
        if only_shadow is False:
            return colored
        result = _body_image(body, contact, appearance, body_rows, data, None, only_shadow=True)
        result.blit(colored, (0, 0))
    return retain_palette(physical_key, result) if physical_only else result


def _ramp_image(body: BodySample, contact: ActorContact, appearance: tuple[RigLayer, ...],
                body_rows: BodyRows, data: AnimationData, condition: ConditionAppearance) -> pygame.Surface:
    """Cache one composed material row, not a row for every equipment layer."""
    ramp = condition.body_ramp
    assert ramp is not None
    rig = body_rig(data, contact)
    material_layers = tuple(layer for layer in appearance if layer.slot in CONDITION_BODY_SLOTS)
    material_body = replace(body, cast_layers=tuple(layer for layer in body.cast_layers if layer.slot in CONDITION_BODY_SLOTS))
    plain_condition = replace(condition, body_ramp=None)
    # Cache selection cannot change item ownership or material composition order.
    # Conservatively evaluate the current frame when owned modifiers are present.
    static_ramp = body_ramp_cacheable(ramp)
    if not static_ramp or condition.item_modifiers:
        original = _body_image(material_body, contact, material_layers, body_rows, data, None,
            only_shadow=False, condition=plain_condition)
        mapped = condition_body_ramp(original, ramp,
            texture=palette_noise(data.resources[ramp.texture]) if ramp.texture else None,
            normal_texture=palette_noise(data.resources[ramp.normalTexture]) if ramp.normalTexture else None,
            cell_size=(rig.cell_width, rig.cell_height),
            strength=1. if static_ramp else condition.ramp_strength,
            age_ms=condition.ramp_age_ms)
        return blend_body_ramp(original, mapped, condition.ramp_strength) if static_ramp else mapped
    key = ("condition-ramp", data.media_root, contact.rig_id, body.clip, body.facing, material_layers,
           body.hide_weapon, body.hidden_slots, material_body.cast_layers, condition.body_color,
           ramp, condition.rig_layers)
    row = cached_palette(key)
    if row is None:
        frames = body_clip(data, contact, body.clip).frames
        source = pygame.Surface((rig.cell_width * frames, rig.cell_height), pygame.SRCALPHA)
        for frame in range(frames):
            source.blit(_body_image(replace(material_body, frame=frame), contact, material_layers,
                body_rows, data, None, only_shadow=False, condition=plain_condition), (frame * rig.cell_width, 0))
        row = retain_palette(key, condition_body_ramp(source, ramp,
            texture=palette_noise(data.resources[ramp.texture]) if ramp.texture is not None else None,
            cell_size=(rig.cell_width, rig.cell_height)))
    mapped = row.subsurface((body.frame * rig.cell_width, 0, rig.cell_width, rig.cell_height))
    if condition.ramp_strength >= 1.:
        return mapped
    original = _body_image(material_body, contact, material_layers, body_rows, data, None,
        only_shadow=False, condition=plain_condition)
    return blend_body_ramp(original, mapped, condition.ramp_strength)


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
                data: AnimationData, camera: Camera, flash: int | PaletteTreatment | None,
                *, only_shadow: bool | None = None,
                physical_only: bool = False,
                condition: ConditionAppearance | None = None,
                ghost: tuple[tuple[int, int, int, int], float] | None = None,
                copy_recipe: ConditionLiveCopies | None = None, copy_slot: int = 0,
                body_opacity: float = 1.,
                coverage: float = 1.,
                dust_elapsed_ms: float | None = None, dust_seed: int = 1,
                item_starts: Mapping[UUID, ItemAttachmentStart] = MappingProxyType({}),
                presentation_ms: float = 0.,
                ) -> tuple[pygame.Surface, tuple[int, int]]:
    material = data.body_materials.get(contact.manifestation) if contact.manifestation is not None else None
    if material is not None and only_shadow is not True:
        treatment = condition or ConditionAppearance()
        condition = replace(treatment, alpha=treatment.alpha * material.alpha,
            body_ramp=treatment.body_ramp or material.palette,
            ramp_strength=treatment.ramp_strength if treatment.body_ramp is not None else 1.)
    factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
    rig = body_rig(data, contact)
    height = contact.elevation_steps if only_shadow else body_elevation_steps(contact, data)
    ground = project_screen(contact.grid, camera, elevation_steps=height)
    scale = contact.visual_scale * factor
    viewed_body = replace(body, facing=view_facing(body.facing, camera.quadrant, data))
    image = _body_image(viewed_body, contact, appearance, body_rows, data, flash,
                        only_shadow=only_shadow, condition=condition, physical_only=physical_only)
    if not physical_only and condition is not None and only_shadow is not True:
        for sample in condition.finite_materials:
            ramp = sample.material
            image = condition_body_ramp(image, ramp,
                texture=palette_noise(data.resources[ramp.texture]) if ramp.texture is not None else None,
                normal_texture=palette_noise(data.resources[ramp.normalTexture]) if ramp.normalTexture is not None else None,
                cell_size=(rig.cell_width, rig.cell_height), strength=sample.strength, pulse=sample.pulse, age_ms=sample.age_ms)
    if condition is not None and condition.absence is not None:
        if only_shadow:
            image = reveal_body(image,0.)
        else:
            sample=condition.absence
            image=absence_silhouette(image,sample.recipe,sample.progress,sample.opacity)
    if ghost is not None:
        image = ghost_body(image, *ghost, copies=copy_recipe,
                           time_ms=condition.time_ms if condition else 0., slot=copy_slot)
    if condition is not None and condition.distortion is not None and not only_shadow:
        image, _ = distort_body(image, condition.distortion, condition.time_ms, condition.distortion_strength)
    if coverage != 1.:
        image = reveal_body(image, coverage)
    dust_padding = 0
    if dust_elapsed_ms is not None:
        recipe = data.death_context.silhouetteDust
        if recipe is None:
            raise ValueError("Disintegrated remains require authored silhouette dust")
        if only_shadow:
            image = reveal_body(image, max(0., 1-dust_elapsed_ms/recipe.erosionMs))
        else:
            image, offset = silhouette_dust(image, recipe, dust_elapsed_ms, dust_seed)
            dust_padding = -offset[1]
    if body_opacity != 1.:
        image = image.copy()
        alpha = pygame.surfarray.pixels_alpha(image)
        alpha[:] = np.rint(alpha * body_opacity)
        del alpha
    body_scale = (1, 1) if only_shadow else body.scale
    image = pygame.transform.scale(image, (max(1, round(image.width * scale * contact.visual_scale_x * body_scale[0])),
                                           max(1, round(image.height * scale * body_scale[1]))))
    # Tuck around the authored passage point, keeping it on the trajectory.
    # The support shadow is drawn separately and never receives this squash.
    root_y = ground[1] + (rig.origin_y_from_ground * body_scale[1]
                         - body.scale_anchor_height_px * (1 - body_scale[1])) * scale
    destination = (round(ground[0] - image.width / 2),
                   round(root_y - image.height + dust_padding * scale * body_scale[1]))
    registration = (0.0, 0.0)
    if not only_shadow and body.registration_socket is not None:
        poses = rig.pose_sockets.get(body.registration_socket, {}).get(body.clip)
        if poses is not None:
            point = poses[viewed_body.facing][body.frame]
            if point is None:
                raise ValueError(f"Unmeasured pose registration: {body.registration_socket}/{body.clip}/{body.frame}")
            registration = (
                (rig.cell_width / 2 - point.x)
                      * scale * contact.visual_scale_x * body_scale[0] * body.registration_weight,
                (rig.cell_height - rig.origin_y_from_ground
                      - body.scale_anchor_height_px - point.y)
                      * scale * body_scale[1] * body.registration_weight,
            )
            destination = (round(destination[0] + registration[0]), round(destination[1] + registration[1]))
    attachments = []
    if not physical_only and not only_shadow and ghost is None:
        item_bounds: dict[UUID, pygame.Rect] = {}
        item_effects = {}
        hidden = set(body.hidden_slots) | {layer.slot for layer in body.cast_layers}
        if body.hide_weapon:
            hidden.add("weapon")
        for layer in appearance:
            if (layer.item_uuid is None or layer.slot in hidden or layer.suppression_provider_uuids
                    or not any(effect.behavior_id in data.item_attachments for effect in layer.item_effects)):
                continue
            row = body_rows[contact.rig_id, body.clip, layer.category, rig.facing_rows[viewed_body.facing]]
            frame = row.subsurface((body.frame * rig.cell_width, 0, rig.cell_width, rig.cell_height))
            box = frame.get_bounding_rect(min_alpha=1)
            if not box:
                continue
            if layer.item_uuid in item_bounds:
                item_bounds[layer.item_uuid].union_ip(box)
            else:
                item_bounds[layer.item_uuid] = box
                item_effects[layer.item_uuid] = layer.item_effects
        for identity, box in item_bounds.items():
            anchor = (destination[0] + box.centerx * scale * contact.visual_scale_x * body_scale[0],
                      destination[1] + box.centery * scale * body_scale[1])
            attachments.append((item_effects[identity], anchor))
    if condition is not None and not physical_only:
        if condition.body_outline is not None and not only_shadow:
            image.blit(condition_body_outline(image, condition.body_outline, condition.outline_age_ms,
                quiet_age_ms=condition.time_ms), (0, 0))
        if condition.layers and not only_shadow:
            marker_anchor = None
            if any(row.layer.markerGroup is not None for row in condition.layers):
                held = condition.frozen_body is not None or condition.body_pose is not None
                head_rows = rig.pose_sockets.get("head", {}).get(viewed_body.clip)
                if head_rows is not None:
                    points = tuple(point for point in (head_rows[viewed_body.facing][body.frame:body.frame+1]
                        if held else head_rows[viewed_body.facing]) if point is not None)
                    if points:
                        head_x = sum(point.x for point in points) / len(points)
                        top = min(point.y for point in points)
                        hidden_slots = set(body.hidden_slots) | {layer.slot for layer in body.cast_layers}
                        if body.hide_weapon:
                            hidden_slots.add("weapon")
                        for layer in appearance:
                            if layer.slot in hidden_slots or layer.suppression_provider_uuids:
                                continue
                            row = body_rows.get((contact.rig_id, body.clip, layer.category,
                                rig.facing_rows[viewed_body.facing]))
                            if row is None:
                                continue
                            if held:
                                box = row.subsurface((body.frame * rig.cell_width, 0,
                                    rig.cell_width, rig.cell_height)).get_bounding_rect()
                                row_top = box.top if box else None
                            else:
                                row_top = _marker_row_top(row)
                            if row_top is not None:
                                top = min(top, row_top)
                        marker_anchor = (ground[0] + registration[0] + (head_x-rig.cell_width/2)*scale*contact.visual_scale_x*body_scale[0],
                            root_y + registration[1] + (top-rig.cell_height)*scale*body_scale[1])
            image, destination = compose_condition_layers(image, destination, ground, viewed_body.facing,
                contact.visual_scale * camera.zoom, contact.visual_scale_x,
                condition.layers, body_rows, data=data, quadrant=camera.quadrant,
                floor_ground=project_screen(contact.grid, camera, elevation_steps=contact.elevation_steps),
                activity=condition.activity, absolute_ms=condition.time_ms, marker_anchor=marker_anchor, marker_scale=camera.zoom,
                attachment_anchors=pose_attachment_anchors(rig, viewed_body,
                    (ground[0] + registration[0], ground[1] + registration[1]
                     - body.scale_anchor_height_px * (1 - body_scale[1]) * scale),
                    scale * body_scale[1], contact.visual_scale_x * body_scale[0] / body_scale[1]),
                life_state=contact.life_state)
    if attachments:
        image, destination = compose_item_attachments(image, destination, data, tuple(attachments),
            facing=view_facing("E", camera.quadrant, data), scale=scale,
            time_ms=presentation_ms, starts=item_starts)
    if condition is not None:
        image.set_alpha(round(condition.alpha * 255))
    return image, destination


class ProjectileLayerBlit(NamedTuple):
    image: pygame.Surface
    destination: tuple[int, int]
    blend: int
    depth: Literal["world", "behind_body", "front_body"] = "world"


def projectile_layer_blits(timeline: CastTimeline, effect: ProjectileSample,
                           media: AnimationMedia, camera: Camera,
                           *, coverage: pygame.Surface | None = None,
                           ) -> tuple[tuple[pygame.Surface, tuple[int, int], int], ...]:
    """Keep the existing pixel API; ordering metadata is compositor-owned."""
    return tuple((layer.image, layer.destination, layer.blend) for layer in
        _projectile_layer_blits(timeline, effect, media, camera, coverage=coverage))


def _projectile_layer_blits(timeline: CastTimeline, effect: ProjectileSample,
                           media: AnimationMedia, camera: Camera,
                           *, coverage: pygame.Surface | None = None,
                           ) -> tuple[ProjectileLayerBlit, ...]:
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
    offset = projectile_registration(timeline.recipe, asset, effect.phase,
                                        asset.rowOrder[effect.row], effect.rotation_radians)
    center = (point[0] + offset[0] * factor, point[1] + offset[1] * factor)
    result = []
    for layer in layers:
        frame = (covered_media(layer.image, coverage, layer.blend,
                    canvas=(asset.frame.width, asset.frame.height),
                    offset=(round(layer.offset[0]), round(layer.offset[1])))
                 if coverage is not None else layer.image)
        transformed = transform_registered_part(frame, offset=layer.offset,
            asset_pivot=(asset.frame.width / 2, asset.frame.height / 2), scale=scale,
            anchor=center, rotation=effect.rotation_radians)
        if transformed is None:
            continue
        frame, destination, _ = transformed
        if effect.opacity < 1:
            frame = frame.copy()
            if layer.blend == pygame.BLEND_RGB_ADD:
                fade = round(effect.opacity * 255)
                frame.fill((fade, fade, fade, 255), special_flags=pygame.BLEND_RGBA_MULT)
            else:
                frame.set_alpha(round((frame.get_alpha() or 255) * effect.opacity))
        result.append(ProjectileLayerBlit(frame, destination, layer.blend, layer.depth))
    return tuple(result)


def _projectile_body_contact(timeline: CastTimeline, effect: ProjectileSample) -> ActorContact | ObjectContact | None:
    """Only declared source preparation and recipient impact can bracket bodies."""
    if effect.phase == "prepare":
        return timeline.source.caster
    if effect.phase == "impact":
        return next((row.target for row in timeline.source.applications
            if row.application_id == effect.application_id), None)
    return None


def _number_blit(number: NumberSample, contact: ActorContact | ObjectContact, font: pygame.font.Font,
                 data: AnimationData, camera: Camera) -> tuple[pygame.Surface, tuple[int, int]]:
    factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
    style = data.badge_style if number.kind == "badge" else data.number_style
    height = body_elevation_steps(contact, data) if isinstance(contact, ActorContact) else contact.elevation_steps
    ground = project_screen(contact.grid, camera, elevation_steps=height)
    label = number.label if number.kind == "badge" else f"{number.value} {number.label}".rstrip()
    fill = font.render(label, True, _rgb(number.color))
    stroke = font.render(label, True, _rgb(style.strokeColor))
    radius = round(style.strokeWidthPx)
    text = pygame.Surface((fill.width + radius * 2, fill.height + radius * 2), pygame.SRCALPHA)
    for x, y in ((-radius, 0), (radius, 0), (0, -radius), (0, radius)):
        text.blit(stroke, (radius + x, radius + y))
    text.blit(fill, (radius, radius))
    text.set_alpha(round(number.alpha * 255))
    anchor = ((body_rig(data, contact).origin_y_from_ground - style.anchorLiftPx) * contact.visual_scale
              if isinstance(contact, ActorContact) else -style.anchorLiftPx)
    bottom = ground[1] + (anchor - style.risePx * number.progress) * factor
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


def actor_painter_key(data: AnimationData, body: BodySample, contact: ActorContact,
                      camera: Camera, *, role: str, height: float,
                      identity: str | tuple[str, ...]) -> tuple[int, float, float, int, tuple[str, ...]]:
    """Sort a baked ground displacement without moving its pixels or native contact."""
    key = painter_key(contact.grid, elevation_steps=height,
                      quadrant=camera.quadrant, role=role, identity=identity)
    points = body_rig(data, contact).pose_sockets.get("ground_depth")
    if points is None or body.clip not in points:
        return key
    facing = view_facing(body.facing, camera.quadrant, data)
    point, origin = points[body.clip][facing][body.frame], points["Idle"][facing][0]
    assert point is not None and origin is not None
    scale = contact.visual_scale * TILE_WIDTH / data.rig.TILE_W
    return (key[0], key[1] + (point.y - origin.y) * scale,
            key[2] + (point.x - origin.x) * scale * contact.visual_scale_x, key[3], key[4])


def actor_draw_commands(data: AnimationData, body: BodySample, contact: ActorContact,
                        layers: tuple[RigLayer, ...], body_rows: BodyRows, camera: Camera,
                        *, flash: int | PaletteTreatment | None = None,
                        condition: ConditionAppearance | None = None,
                        coverage: float = 1.,
                        dust_elapsed_ms: float | None = None, dust_seed: int = 1,
                        item_starts: Mapping[UUID, ItemAttachmentStart] = MappingProxyType({}),
                        presentation_ms: float = 0.) -> tuple[AnimationDrawCommand, ...]:
    """Compose one explicitly sampled actor using the map's shared painter."""
    contact = condition_contact(contact, condition)
    body = condition_body_pose(data, body, contact, condition)
    if dust_elapsed_ms is not None and condition is not None:
        condition = replace(condition, layers=(), body_outline=None, live_copies=None)
    commands: list[AnimationDrawCommand] = []
    for shadow in (True, False):
        if shadow and not any(layer.slot == "shadow" for layer in layers):
            continue
        role = "actor_shadow" if shadow else "actor"
        height = contact.elevation_steps if shadow else body_elevation_steps(contact, data)
        image, destination = _actor_blit(
            body, contact, layers, body_rows, data, camera, flash, only_shadow=shadow,
            coverage=coverage, dust_elapsed_ms=dust_elapsed_ms, dust_seed=dust_seed,
            item_starts=item_starts, presentation_ms=presentation_ms,
            condition=(replace(condition, alpha=condition.alpha * (
                1 - condition.distortion_strength * (1 - condition.distortion.bodyOpacity)))
                       if condition is not None and condition.distortion is not None and not shadow else condition),
        )
        selection = ()
        blocker = None
        if not shadow and dust_elapsed_ms is None:
            physical, physical_destination = _actor_blit(body, contact, layers, body_rows,
                data, camera, None, only_shadow=False, physical_only=True,
                coverage=coverage, condition=condition)
            aligned = align_coverage(pygame.surfarray.array_alpha(physical) > 0,
                physical_destination, AnimationDrawCommand(
                    (0, 0., 0., 0, ()), image, destination, 0, ()))
            if physical.get_alpha() == 0:
                aligned = np.zeros(image.get_size(), dtype=bool)
                aligned.setflags(write=False)
            selection = (SelectionCoverage(WorldHit("actor", contact.actor_uuid,
                contact.grid, contact.elevation_steps), aligned),)
            blocker = aligned
        commands.append(AnimationDrawCommand(
            actor_painter_key(data, body, contact, camera, role=role, height=height,
                              identity=contact.actor_uuid),
            image, destination, 0,
            (contact.actor_uuid, contact.grid, contact.rig_id, "current", None, "authored",
             role, height, body.clip, body.frame),
            role=role, owner=contact.actor_uuid, support_height_steps=contact.elevation_steps,
            selection=selection, selection_occluder=bool(selection), selection_block_mask=blocker,
        ))
    if condition is not None and condition.live_copies is not None:
        copies = condition.live_copies
        for slot, distance, opacity in copies.slots:
            offset = copies.recipe.slots[slot]
            location = (contact.grid[0] + offset[0] * distance, contact.grid[1] + offset[1] * distance)
            copy_contact = replace(contact, grid=location)
            copy_appearance = replace(condition, live_copies=None, distortion=None,
                layers=dict(copies.layers).get(slot, ()))
            image, destination = _actor_blit(body, copy_contact, layers, body_rows, data, camera, None,
                only_shadow=False, condition=copy_appearance,
                ghost=(copies.recipe.palette, copies.recipe.paletteMaximum), copy_recipe=copies.recipe, copy_slot=slot,
                body_opacity=copies.recipe.opacity * opacity, coverage=coverage)
            height = body_elevation_steps(copy_contact, data)
            commands.append(AnimationDrawCommand(actor_painter_key(data, body, copy_contact, camera,
                role="actor", height=height, identity=(contact.actor_uuid, "copy", str(slot))),
                image, destination, 0, (contact.actor_uuid, location, contact.rig_id, "current", None, "authored",
                                       "body_copy", height, body.clip, body.frame, slot),
                role="body_copy", owner=contact.actor_uuid))
    if condition is not None and condition.distortion is not None:
        recipe = condition.distortion
        for index, contour in enumerate(recipe.contours):
            t = condition.time_ms / 1000 * contour.frequency
            offset = (contour.offset[0] + contour.oscillation[0] * sin(t),
                      contour.offset[1] + contour.oscillation[1] * cos(t))
            location = (contact.grid[0] + offset[0], contact.grid[1] + offset[1])
            contour_contact = replace(contact, grid=location)
            image, destination = _actor_blit(body, contour_contact, layers, body_rows, data, camera, None,
                only_shadow=False, condition=replace(condition, layers=(), live_copies=None,
                    alpha=condition.alpha * contour.opacity * condition.distortion_strength),
                    ghost=(recipe.palette, recipe.paletteMaximum), coverage=coverage)
            height = body_elevation_steps(contour_contact, data)
            commands.append(AnimationDrawCommand(actor_painter_key(data, body, contour_contact, camera,
                role="actor", height=height, identity=(contact.actor_uuid, "contour", str(index))),
                image, destination, 0, (contact.actor_uuid, location, contact.rig_id, "current", None, "authored",
                                       "body_contour", height, body.clip, body.frame, index),
                role="body_contour", owner=contact.actor_uuid))
    return tuple(commands)


def body_trail_draw_command(trail: BodyTrailPose, data: AnimationData, body_rows: BodyRows,
                            camera: Camera) -> AnimationDrawCommand:
    actor, body = trail.pose.actor, trail.pose.body
    condition = actor.condition
    distortion = condition.distortion
    assert distortion is not None
    body = condition_body_pose(data, body, actor.contact, condition)
    image, destination = _actor_blit(body, actor.contact, actor.layers, body_rows, data, camera, None,
        only_shadow=False, condition=replace(condition, layers=(), live_copies=None, distortion=None,
                                              alpha=condition.alpha * trail.opacity),
        ghost=(distortion.palette, distortion.paletteMaximum))
    height = body_elevation_steps(actor.contact, data)
    return AnimationDrawCommand(actor_painter_key(data, body, actor.contact, camera,
        role="actor", height=height, identity=(body.actor_uuid, "trail", str(trail.age_ms))),
        image, destination, 0, (body.actor_uuid, actor.contact.grid, actor.contact.rig_id, "current", None,
                               "authored", "body_trail", height, body.clip, body.frame, trail.age_ms),
        role="body_trail", owner=body.actor_uuid)


def animation_draw_commands(timeline: CastTimeline, sample: CastSample,
                            media: AnimationMedia, camera: Camera, *,
                            condition_appearances: Mapping[str, ConditionAppearance] | None = None,
                            include_bodies: bool = True,
                            actor_bounds: Mapping[str, pygame.Rect] | None = None,
                            projectile_coverage: pygame.Surface | None = None,
                            body_samples: Mapping[str, BodySample] | None = None,
                            actor_contacts: Mapping[str, ActorContact] | None = None,
                            ) -> tuple[AnimationDrawCommand, ...]:
    """Join sampled actors and effects to the map's existing painter ordering."""
    data, source = timeline.data, timeline.source
    contacts = {contact.actor_uuid: contact for contact in cast_actor_contacts(source)}
    feedback_contacts = {source.caster.actor_uuid: source.caster,
                         **{feedback_identity(application.target): application.target for application in source.applications}}
    flashes = {vital.actor_uuid: vital.flash for vital in sample.vitals}
    commands: list[AnimationDrawCommand] = []
    if source.emitter is not None and sample.device_frame is not None:
        commands.append(device_draw_command(source.emitter, sample.device_frame, camera))
    for body in sample.bodies if include_bodies else ():
        contact = contacts[body.actor_uuid]
        commands.extend(actor_draw_commands(
            data, body, contact, media.appearances[body.actor_uuid], media.body_rows, camera,
            flash=flashes.get(body.actor_uuid),
            condition=condition_appearances.get(body.actor_uuid) if condition_appearances is not None else None,
        ))
    projectile = timeline.recipe.projectile
    for reference_effect in sample.projectiles:
        assert projectile is not None
        match reference_effect:
            case ProjectileSample():
                effect = project_projectile(timeline, reference_effect, camera.quadrant)
                phase_name = "cast" if effect.phase == "prepare" else effect.phase
                authored_phase = {"prepare": projectile.prepare, "travel": projectile.travel,
                                  "impact": projectile.impact}[effect.phase]
                if authored_phase.composition == "xyz_volume":
                    assert source.ground_target is not None
                    asset = data.projectile_assets[effect.asset_id]
                    position, height = source.ground_target.grid, source.ground_target.elevation_steps
                    anchor = project_screen(position, camera, elevation_steps=height)
                    for layer_index, layer in enumerate(registered_media_samples(data, effect.asset_id,
                            phase_name, effect.column, asset.rowOrder[effect.row],
                            scale=projectile_phase_scale(projectile, effect.phase) * TILE_WIDTH / data.rig.TILE_W * camera.zoom,
                            anchor=anchor, rows=media.projectile_rows, alpha=effect.opacity, zoom=camera.zoom)):
                        assert layer.positions is not None and layer.ownership is not None
                        commands.append(AnimationDrawCommand(painter_key(position, elevation_steps=height,
                            quadrant=camera.quadrant, role="projectile",
                            identity=(source.root_event_uuid, effect.phase, str(layer_index))),
                            layer.image, layer.destination, layer.blend,
                            (source.root_event_uuid, position, effect.asset_id, "current", None, "authored",
                             "projectile", height, effect.phase, effect.column, effect.application_id),
                            volume=cast_surface_volume(timeline, layer, media.area, position, height,
                                                      support_clipping=authored_phase.supportClipping),
                            world_depth_group=(source.root_event_uuid, effect.phase, effect.application_id or "")))
                    continue
                layers = _projectile_layer_blits(timeline, effect, media, camera, coverage=projectile_coverage)
                visual, frame = effect.asset_id, effect.column
            case GeometryProjectileSample():
                effect = project_geometry_projectile(timeline, reference_effect, camera.quadrant)
                command = geometry_draw_command(
                    data, effect, timeline.recipe.elementColors,
                    projectile_contact(timeline, effect, quadrant=camera.quadrant),
                    projectile.depthMode, source.root_event_uuid, camera,
                )
                if projectile_coverage is not None:
                    command = command._replace(surface=covered_media(
                        command.surface, projectile_coverage, command.blend))
                commands.append(command)
                continue
        position, height = projectile_contact(timeline, effect, quadrant=camera.quadrant)
        role = "ground_effect" if projectile.depthMode == "ground" else "projectile"
        key = painter_key(position, elevation_steps=height, quadrant=camera.quadrant,
                          role=role, identity=(source.root_event_uuid, effect.application_id or "", effect.phase))
        if projectile.depthMode == "overlay":
            key = (200, *key[1:])
        for layer in layers:
            layer_key = key
            contact = _projectile_body_contact(timeline, effect)
            if layer.depth != "world" and contact is not None:
                contact_height = (body_elevation_steps(contact, data)
                    if isinstance(contact, ActorContact) else contact.elevation_steps)
                actor_key = painter_key(contact.grid, elevation_steps=contact_height,
                    quadrant=camera.quadrant, role="actor",
                    identity=(source.root_event_uuid, effect.application_id or "", effect.phase))
                layer_key = (*actor_key[:3], actor_key[3] + (-1 if layer.depth == "behind_body" else 1), actor_key[4])
            commands.append(AnimationDrawCommand(
                layer_key, layer.image, layer.destination, layer.blend,
                (source.root_event_uuid, position, visual, "current", None, "authored",
                 "projectile", height, effect.phase, frame, effect.application_id),
                AreaLayer(source.ground_target.grid, source.ground_target.elevation_steps, media.area)
                if source.ground_target is not None and effect.phase == "impact" else None,
            ))
    if sample.delivery_enabled:
        commands.extend(cast_media_draw_commands(timeline, sample, camera, media.area, media.projectile_rows,
            actor_bounds=actor_screen_bounds(commands) if actor_bounds is None else actor_bounds,
            body_samples=body_samples, actor_contacts=actor_contacts))
        commands.extend(directed_draw_commands(timeline, sample, camera, media.area))
    commands.extend(number_draw_commands(data, sample.numbers, feedback_contacts, media.font, camera))
    return tuple(commands)


def number_draw_commands(data: AnimationData, numbers: tuple[NumberSample, ...],
                         contacts: Mapping[str, ActorContact | ObjectContact], font: pygame.font.Font,
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
        height = body_elevation_steps(contact, data) if isinstance(contact, ActorContact) else contact.elevation_steps
        identity = feedback_identity(contact)
        key = painter_key(contact.grid, elevation_steps=height,
                          quadrant=camera.quadrant, role="actor",
                          identity=(identity, number.application_id or ""))
        commands.append(AnimationDrawCommand(
            (210, *key[1:]), image, destination, 0,
            (identity, contact.grid, number.label, "current", None, "authored",
             "floating_number", height, number.value, number.progress, number.application_id),
            role="floating_number", owner=identity,
        ))
    return tuple(commands)


def actor_screen_bounds(commands: Sequence[AnimationDrawCommand]) -> dict[str, pygame.Rect]:
    """Visible body pixels, excluding shadows and the atlas's empty padding."""
    bounds: dict[str, pygame.Rect] = {}
    for command in commands:
        image, position = command.surface, command.destination
        if command.role != "actor" or image.get_alpha() == 0:
            continue
        rect = image.get_bounding_rect(min_alpha=1).move(position)
        if rect.width == 0 or rect.height == 0:
            continue
        identity = command.owner
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
        image, position = command.surface, command.destination
        if command.role != "floating_number":
            arranged.append(command)
            continue
        rect = place_feedback_rect(image.get_rect(topleft=position),
                                   actor_bounds.get(command.owner), occupied, viewport)
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
                         include_bodies: bool = True,
                         ) -> tuple[AnimationDrawCommand, ...]:
    contacts = {contact.actor_uuid: contact for contact in attack_actor_contacts(timeline)}
    flashes = {vital.actor_uuid: vital.flash for vital in sample.vitals}
    commands = tuple(command for body in sample.bodies for command in actor_draw_commands(
        timeline.data, body, contacts[body.actor_uuid], appearances[body.actor_uuid], media, camera,
        flash=flashes.get(body.actor_uuid),
        condition=condition_appearances.get(body.actor_uuid) if condition_appearances is not None else None,
    )) if include_bodies else ()
    projectile_commands = ()
    if timeline.projectile is not None:
        projectile_commands = tuple(geometry_draw_command(
            timeline.data, effect, timeline.projectile.element_colors,
            attack_projectile_contact(timeline, effect, camera.quadrant),
            timeline.projectile.recipe.depthMode, timeline.root_event_uuid, camera,
        ) for reference in sample.projectiles
          for effect in (project_attack_projectile(timeline, reference, camera.quadrant),))
    return (*commands, *projectile_commands, *weapon_trail_draw_commands(timeline, sample.elapsed_ms, camera),
        *number_draw_commands(timeline.data, sample.numbers,
            {**contacts, feedback_identity(timeline.target): timeline.target}, font, camera, badge_font=badge_font))


def draw_animation(surface: pygame.Surface, timeline: CastTimeline, sample: CastSample,
                   media: AnimationMedia, camera: Camera) -> None:
    """Keep the detached source-stage ordering using the shared image builders."""
    if timeline.recipe.media:
        for command in sorted(animation_draw_commands(timeline, sample, media, camera), key=lambda row: row.key):
            blit_media(surface, command.surface, command.destination, command.blend)
        return
    data, source = timeline.data, timeline.source
    contacts = {contact.actor_uuid: contact for contact in cast_actor_contacts(source)}
    feedback_contacts = {source.caster.actor_uuid: source.caster,
                         **{feedback_identity(application.target): application.target for application in source.applications}}
    flashes = {vital.actor_uuid: vital.flash for vital in sample.vitals}
    draws: list[tuple[float, pygame.Surface, tuple[int, int], int]] = []
    for body in sample.bodies:
        contact = contacts[body.actor_uuid]
        # A lifted detached-stage body still leaves its shadow on support.
        for shadow in (True, False) if contact.body_lift_px or contact.manifestation in data.body_materials else (None,):
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
                layers = _projectile_layer_blits(timeline, effect, media, camera)
            case GeometryProjectileSample():
                effect = project_geometry_projectile(timeline, reference_effect, camera.quadrant)
                layers = (ProjectileLayerBlit(*_geometry_blit(data, effect, timeline.recipe.elementColors, camera)),)
        _, support_height = projectile_contact(timeline, effect, quadrant=camera.quadrant)
        unlifted_y = effect.point[1] + support_height * HEIGHT_STEP_PIXELS * data.rig.TILE_W / TILE_WIDTH
        depth = {"overlay": float("inf"), "ground": -float("inf"),
                 "world": unlifted_y / (data.rig.TILE_H / 2) * 1024 + 240}[projectile.depthMode]
        for layer in layers:
            image, destination, blend = layer.image, layer.destination, layer.blend
            layer_depth = depth
            if isinstance(effect, ProjectileSample) and layer.depth != "world":
                contact = _projectile_body_contact(timeline, effect)
                if contact is not None:
                    layer_depth = _reference_actor_depth(rotate_position(contact.grid, camera.quadrant),
                        feedback_identity(contact)) + (-1 if layer.depth == "behind_body" else 1)
            ground = source.ground_target
            if ground is not None and effect.phase == "impact" and media.area is not None:
                image = mask_ground_area(image, destination, ground.grid, ground.elevation_steps, camera, media.area)
            draws.append((layer_depth, image, destination, blend))
    for _, image, destination, blend in sorted(draws, key=lambda item: item[0]):
        surface.blit(image, destination, special_flags=blend)
    for number in sample.numbers:
        image, destination = _number_blit(number, feedback_contacts[number.actor_uuid], media.font, data, camera)
        surface.blit(image, destination)
