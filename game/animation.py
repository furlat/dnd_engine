"""Execute imported Studio casts with an explicit, renderer-independent clock.

The records below are detached presentation inputs and transient samples, not
mechanical Events. Source recipes remain the authoring format. Compilation
resolves their finite cast/delivery/reaction phases; it does not schedule tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import atan2, cos, floor, hypot, isfinite, pi, sin
from typing import Literal

from dnd.core.life_types import LifeState
from game.animation_types import (
    AnimationData, AuthoredProjectileAsset, AuthoredProjectilePhase, BodyClip, BodyRig,
    DamageDeath, EquipmentTransitionContext, Facing8, FloatingNumber, HitFlash,
    StudioActorLayer, StudioDamage, StudioProjectilePhase, StudioSpellDraft,
)
from game.projection import HEIGHT_STEP_PIXELS, TILE_HEIGHT, TILE_WIDTH, inverse_rotate_position, project_world


@dataclass(frozen=True, slots=True)
class ActorContact:
    """Frozen grid/support contact; one elevation step is five engine feet."""

    actor_uuid: str
    grid: tuple[float, float]
    facing: Facing8
    visual_scale: float
    hp: int | None = None
    life_state: LifeState = LifeState.ALIVE
    elevation_steps: float = 0
    rig_id: str = "neuroclient.modular"
    visual_scale_x: float = 1.0
    body_lift_px: float = 0.0


def body_elevation_steps(contact: ActorContact, data: AnimationData) -> float:
    """Body attachment height; lift is unscaled rig pixels above support."""
    return contact.elevation_steps + contact.body_lift_px * TILE_WIDTH / data.rig.TILE_W / HEIGHT_STEP_PIXELS


@dataclass(frozen=True, slots=True)
class CastApplication:
    """One retained application; repeated recipients keep distinct identities."""

    application_id: str | None
    target: ActorContact
    damage_applied: bool
    damage_total: int | None
    resulting_hp: int | None
    resulting_life_state: LifeState | None = None
    damage_type: str | None = None
    # Explicit world-height adaptation above the authored endpoint segment.
    travel_apex_steps: float = 0.0


@dataclass(frozen=True, slots=True)
class CastInput:
    root_event_uuid: str
    caster: ActorContact
    applications: tuple[CastApplication, ...]


@dataclass(frozen=True, slots=True)
class Anchor:
    name: str
    at_ms: float
    application_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectileInterval:
    name: Literal["prepare", "travel", "impact"]
    asset: AuthoredProjectileAsset
    phase: AuthoredProjectilePhase
    fps: float
    start_ms: float
    end_ms: float


@dataclass(frozen=True, slots=True)
class ApplicationTimeline:
    source: CastApplication
    facing: Facing8
    from_point: tuple[float, float]
    to_point: tuple[float, float]
    travel_start_ms: float
    travel_end_ms: float
    curvature: float
    projectile_intervals: tuple[ProjectileInterval, ...]
    damage: StudioDamage | None
    damage_start_ms: float | None
    damage_end_ms: float | None
    hp_ms: float | None
    flash_ms: float | None
    number_ms: float | None


@dataclass(frozen=True, slots=True)
class CastTimeline:
    source: CastInput
    recipe: StudioSpellDraft
    data: AnimationData
    facing: Facing8
    body_end_ms: float
    release_ms: float
    applications: tuple[ApplicationTimeline, ...]
    recovery_start_ms: float
    complete_ms: float
    anchors: tuple[Anchor, ...]


@dataclass(frozen=True, slots=True)
class BodySample:
    actor_uuid: str
    clip: str
    frame: int
    facing: Facing8
    hide_weapon: bool = False
    cast_layers: tuple[StudioActorLayer, ...] = ()


@dataclass(frozen=True, slots=True)
class EquipmentTimeline:
    """The authored body gesture for one retained loadout replacement."""

    root_event_uuid: str
    actor: ActorContact
    recipe: EquipmentTransitionContext
    data: AnimationData
    complete_ms: float


@dataclass(frozen=True, slots=True)
class EquipmentSample:
    """Same-stance replacements retain their old layers until completion."""

    body: BodySample
    complete: bool


@dataclass(frozen=True, slots=True)
class ProjectileSample:
    """A phase-local sample in unzoomed rig reference pixels.

    sample_cast uses canonical flat coordinates. project_projectile returns
    current-view coordinates without changing phase time or progress.
    """

    application_id: str | None
    phase: Literal["prepare", "travel", "impact"]
    asset_id: str
    column: int
    row: int
    point: tuple[float, float]
    rotation_radians: float
    progress: float


@dataclass(frozen=True, slots=True)
class GeometryProjectileSample:
    application_id: str | None
    phase: Literal["travel"]
    point: tuple[float, float]
    trail: tuple[tuple[float, float], ...]
    progress: float
    primitive: Literal["dart", "bolt"] = "dart"


@dataclass(frozen=True, slots=True)
class NumberSample:
    actor_uuid: str
    value: int | None
    label: str
    color: int
    progress: float
    alpha: float
    application_id: str | None = None
    kind: Literal["number", "badge"] = "number"


@dataclass(frozen=True, slots=True)
class VitalsSample:
    actor_uuid: str
    hp: int | None
    life_state: LifeState
    flash: int | None


@dataclass(frozen=True, slots=True)
class CastSample:
    bodies: tuple[BodySample, ...]
    projectiles: tuple[ProjectileSample | GeometryProjectileSample, ...]
    numbers: tuple[NumberSample, ...]
    vitals: tuple[VitalsSample, ...]
    complete: bool


def body_frame(elapsed_ms: float, fps: float, count: int, *, loop: bool) -> int:
    raw = floor(elapsed_ms * fps / 1000 + 1e-10)
    return raw % count if loop else min(count - 1, raw)


def body_rig(data: AnimationData, contact: ActorContact) -> BodyRig:
    """Resolve one frozen actor's presentation rig without a runtime lookup."""
    if contact.rig_id not in data.rigs:
        raise ValueError(f"unknown actor rig: {contact.rig_id}")
    return data.rigs[contact.rig_id]


def body_clip(data: AnimationData, contact: ActorContact, clip: str) -> BodyClip:
    """Resolve a root-vocabulary clip and require its mapped body resource."""
    rig = body_rig(data, contact)
    if clip not in rig.clips:
        raise ValueError(f"missing body clip mapping: {contact.rig_id}/{clip}")
    mapped = rig.clips[clip]
    if not any(mapped.sheets.get(category) in data.resources
               for category in rig.slot_categories.get("body", ())):
        raise ValueError(f"missing body clip resource: {contact.rig_id}/{clip}")
    return mapped


def body_duration(clip: BodyClip, speed: float) -> float:
    # AnimatedEntity/FSM settles when the last index is reached, not one frame
    # later. Actual selected sheets are validated at the resource boundary.
    return (clip.frames - 1) * 1000 / (clip.fps * speed)


def _require_frame(clip: BodyClip, frame: int, anchor: str) -> None:
    if not 0 <= frame < clip.frames:
        raise ValueError(f"unreachable {anchor} frame {frame} in {clip.source_clip} ({clip.frames} frames)")


def compile_equipment(data: AnimationData, root_event_uuid: str, actor: ActorContact) -> EquipmentTimeline:
    """Bind the existing body context; item facts remain in the history reducer."""
    recipe = data.equipment_context
    body_clip(data, actor, "Idle")
    if recipe.media:
        raise NotImplementedError("equipment transition media is outside the selected body-only context")
    duration = 0.0
    if recipe.bodyEnabled:
        duration = body_duration(body_clip(data, actor, recipe.bodyClip), recipe.bodyPlaybackSpeed)
    return EquipmentTimeline(root_event_uuid, actor, recipe, data, duration)


def sample_idle_body(data: AnimationData, actor: ActorContact, elapsed_ms: float) -> BodySample:
    """Sample a retained actor between actions, preserving its final death pose."""
    if not isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("elapsed time must be finite and nonnegative")
    clip = data.death_context.bodyClip if actor.life_state == LifeState.DEAD else "Idle"
    metadata = body_clip(data, actor, clip)
    frame = (metadata.frames - 1 if actor.life_state == LifeState.DEAD
             else body_frame(elapsed_ms, metadata.fps, metadata.frames, loop=True))
    return BodySample(actor.actor_uuid, clip, frame, actor.facing)


def sample_equipment(timeline: EquipmentTimeline, elapsed_ms: float) -> EquipmentSample:
    """Seek the same-MELEE gesture without modifying identity or equipped items."""
    if not isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("elapsed time must be finite and nonnegative")
    actor, recipe, data = timeline.actor, timeline.recipe, timeline.data
    if elapsed_ms >= timeline.complete_ms:
        return EquipmentSample(sample_idle_body(data, actor, elapsed_ms - timeline.complete_ms), True)
    metadata = body_clip(data, actor, recipe.bodyClip)
    body = BodySample(
        actor.actor_uuid, recipe.bodyClip,
        body_frame(elapsed_ms, metadata.fps * recipe.bodyPlaybackSpeed, metadata.frames, loop=False),
        actor.facing,
    )
    # commitFrame changes the source's selected weapon set. This selected
    # replacement keeps MELEE throughout; item identity changes at settlement.
    return EquipmentSample(body, False)


def _iso(grid: tuple[float, float], data: AnimationData) -> tuple[float, float]:
    x, y = grid
    return (x - y) * data.rig.TILE_W / 2, (x + y) * data.rig.TILE_H / 2


def facing_for_delta(grid_delta: tuple[float, float], data: AnimationData) -> Facing8:
    """Resolve a world-grid direction with the original authored facing rows."""
    x, y = grid_delta
    if x == 0 and y == 0:
        return "S"
    # JS Math.round's half convention differs from Python round.
    sector = floor((atan2(y, x) + pi / 4) / (pi / 4) + 0.5) % 8
    return data.rig.AUTHORED_PROJECTILE_ROW_ORDER[sector]


def _facing_vector(facing: Facing8, data: AnimationData) -> tuple[float, float]:
    index = data.rig.AUTHORED_PROJECTILE_ROW_ORDER.index(facing)
    angle = index * pi / 4 - pi / 4
    return _iso((cos(angle), sin(angle)), data)


def view_facing(facing: Facing8, quadrant: int, data: AnimationData) -> Facing8:
    """Rotate world facing with the projection owner's camera quarter turns."""
    if quadrant not in range(4):
        raise ValueError("camera quadrant must be 0 through 3")
    order = data.rig.AUTHORED_PROJECTILE_ROW_ORDER
    return order[(order.index(facing) + 2 * quadrant) % len(order)]


def _anchored_points(caster: ActorContact, target_contact: ActorContact, recipe: StudioSpellDraft,
                     data: AnimationData, facing: Facing8,
                     origin: tuple[float, float], target: tuple[float, float],
                     *, local_scales: tuple[float, float] = (1, 1),
                     anchor_basis: Literal["rig_root", "tile_center"] = "rig_root",
                     ) -> tuple[tuple[float, float], tuple[float, float]]:
    """Bind screen-local authored offsets after projecting support contacts."""
    projectile = recipe.projectile
    assert projectile is not None
    anchor = (projectile.sourceAnchorsByFacing or {}).get(facing, projectile.sourceAnchor)
    vx, vy = _facing_vector(facing, data)
    length = hypot(vx, vy)
    ux, uy = vx / length, vy / length
    x, y = origin
    tx, ty = target
    # Original execution/timing uses the rig root. Point-geometry projection
    # honors its tileCenter data instead; sprites retain canvas registration.
    if anchor_basis == "rig_root":
        y += body_rig(data, caster).origin_y_from_ground * caster.visual_scale
        ty += body_rig(data, target_contact).origin_y_from_ground * target_contact.visual_scale
    x += (ux * anchor.forwardPx - uy * anchor.sidePx) * local_scales[0]
    y += (uy * anchor.forwardPx + ux * anchor.sidePx + anchor.liftY) * local_scales[0]
    ty += projectile.targetAnchor.liftY * local_scales[1]
    return (x, y), (tx, ty)


def projectile_endpoints(first: tuple[float, float], last: tuple[float, float],
               source_axis_px: float, target_axis_px: float,
               ) -> tuple[tuple[float, float], tuple[float, float]]:
    """Apply the source axis-inset rule, retaining coincident view contacts."""
    x, y = first
    tx, ty = last
    dx, dy = tx - x, ty - y
    distance = hypot(dx, dy)
    if distance == 0:
        return first, last
    ux, uy = dx / distance, dy / distance
    start, end = source_axis_px, distance + target_axis_px
    separation = min(8, distance)
    if end - start < separation:
        available = max(0, distance - separation)
        source_inset = max(0, source_axis_px)
        target_inset = max(0, -target_axis_px)
        total = source_inset + target_inset
        if total > 0:
            start, end = available * source_inset / total, distance - available * target_inset / total
        else:
            center = max(separation / 2, min(distance - separation / 2, (start + end) / 2))
            start, end = center - separation / 2, center + separation / 2
    return (x + ux * start, y + uy * start), (x + ux * end, y + uy * end)


def _projectile_point(phase: Literal["prepare", "travel", "impact"], progress: float,
                      first: tuple[float, float], last: tuple[float, float],
                      curvature: float = 0) -> tuple[float, float]:
    if phase == "travel":
        return projectile_curve_point(first, last, progress, curvature)
    return first if phase == "prepare" else last


def _projectile_rotation(timeline: CastTimeline, phase: Literal["prepare", "travel", "impact"],
                         facing: Facing8, first: tuple[float, float], last: tuple[float, float],
                         *, vertical_tangent_px: float = 0.0, curvature: float = 0.0) -> float:
    projectile = timeline.recipe.projectile
    assert projectile is not None
    orientation = projectile.orientation
    if orientation.fineRotation == "none":
        return 0.0
    offset = orientation.rotationOffsetDeg * pi / 180
    if phase == "prepare":
        return offset
    vx, vy = _facing_vector(facing, timeline.data)
    # A camera may collapse distinct raised world contacts. Keep the frozen
    # world-facing row and its orientation rather than derive a new direction.
    dx, dy = last[0] - first[0], last[1] - first[1]
    # SpriteProjectileFx.target_vector keeps the initial trajectory tangent,
    # including a Bézier's first control leg; its authored row stays fixed.
    dx, dy = dx - 2 * dy * curvature, dy + 2 * dx * curvature - vertical_tangent_px
    angle = atan2(vy, vx) if dx == 0 and dy == 0 else atan2(dy, dx)
    return (angle - atan2(vy, vx) + pi) % (2 * pi) - pi + offset


def _application(timeline: CastTimeline, identity: str | None) -> ApplicationTimeline:
    for application in timeline.applications:
        if application.source.application_id == identity:
            return application
    raise ValueError("projectile sample belongs to a different cast application")


def _projectile_arc(application: CastApplication, phase: str, progress: float) -> tuple[float, float]:
    """World-height lift and its progress derivative, including arrival tangent."""
    progress = progress if phase == "travel" else (0 if phase == "prepare" else 1)
    apex = application.travel_apex_steps
    return 4 * progress * (1 - progress) * apex, 4 * (1 - 2 * progress) * apex


def projectile_contact(timeline: CastTimeline, effect: ProjectileSample | GeometryProjectileSample,
                       *, quadrant: int = 0) -> tuple[tuple[float, float], float]:
    """Frozen support with the authored curve represented in ground depth."""
    application = _application(timeline, effect.application_id)
    source, target = timeline.source.caster, application.source.target
    progress = effect.progress if effect.phase == "travel" else (0 if effect.phase == "prepare" else 1)
    lift, _ = _projectile_arc(application.source, effect.phase, effect.progress)
    source_height = body_elevation_steps(source, timeline.data)
    target_height = body_elevation_steps(target, timeline.data)
    height = source_height + (target_height - source_height) * progress + lift
    if isinstance(effect, GeometryProjectileSample):
        projected = project_geometry_projectile(timeline, effect, quadrant)
        factor = TILE_WIDTH / timeline.data.rig.TILE_W
        projectile = timeline.recipe.projectile
        assert projectile is not None
        facing = view_facing(application.facing, quadrant, timeline.data)
        anchor = (projectile.sourceAnchorsByFacing or {}).get(facing, projectile.sourceAnchor)
        attachment_lift = (anchor.liftY * source.visual_scale * (1 - progress)
                           + projectile.targetAnchor.liftY * target.visual_scale * progress)
        # Vertical attachment offsets are height, like support and the arc.
        # Leaving them in the ground inversion sorted a dart behind its floor.
        height -= attachment_lift * factor / HEIGHT_STEP_PIXELS
        return reference_point_contact(timeline.data, projected.point, height, quadrant), height
    ground = (source.grid[0] + (target.grid[0] - source.grid[0]) * progress,
              source.grid[1] + (target.grid[1] - source.grid[1]) * progress)
    if application.curvature:
        asset = timeline.data.projectile_assets[effect.asset_id]
        center = projectile_center_offset(timeline.recipe, asset)
        _, first, last = _projected_endpoints(timeline, application, quadrant, center)
        point = projectile_curve_point(first, last, progress, application.curvature)
        straight = projectile_curve_point(first, last, progress, 0)
        factor = TILE_WIDTH / timeline.data.rig.TILE_W
        dx, dy = (point[0] - straight[0]) * factor, (point[1] - straight[1]) * factor
        offset = inverse_rotate_position((dx / TILE_WIDTH + dy / TILE_HEIGHT,
                                          dy / TILE_HEIGHT - dx / TILE_WIDTH), quadrant)
        ground = ground[0] + offset[0], ground[1] + offset[1]
    return ground, height


def reference_point_contact(data: AnimationData, point: tuple[float, float],
                            visual_height: float, quadrant: int) -> tuple[float, float]:
    """Separate a projected effect's vertical attachment from its ground depth."""
    factor = TILE_WIDTH / data.rig.TILE_W
    x, y = point[0] * factor, point[1] * factor + visual_height * HEIGHT_STEP_PIXELS
    return inverse_rotate_position((x / TILE_WIDTH + y / TILE_HEIGHT,
                                    y / TILE_HEIGHT - x / TILE_WIDTH), quadrant)


def projectile_center_offset(recipe: StudioSpellDraft, asset: AuthoredProjectileAsset) -> tuple[float, float]:
    """Original SpriteProjectileFx canvas-center registration, before camera zoom."""
    projectile = recipe.projectile
    assert projectile is not None and projectile.sprite is not None
    visual = projectile.sprite
    anchor = visual.anchor or asset.anchor
    return (visual.offsetX + (0.5 - anchor.x) * asset.frame.width * projectile.scale,
            visual.offsetY + (0.5 - anchor.y) * asset.frame.height * projectile.scale)


def _projected_endpoints(timeline: CastTimeline, application: ApplicationTimeline, quadrant: int,
                         center: tuple[float, float] = (0, 0),
                         ) -> tuple[Facing8, tuple[float, float], tuple[float, float]]:
    caster, target, data = timeline.source.caster, application.source.target, timeline.data
    facing = view_facing(application.facing, quadrant, data)
    scale = data.rig.TILE_W / TILE_WIDTH
    x, y = project_world(caster.grid, elevation_steps=body_elevation_steps(caster, data), quadrant=quadrant)
    tx, ty = project_world(target.grid, elevation_steps=body_elevation_steps(target, data), quadrant=quadrant)
    projectile = timeline.recipe.projectile
    assert projectile is not None
    first, last = _anchored_points(
        caster, target, timeline.recipe, data, facing, (x * scale, y * scale), (tx * scale, ty * scale),
        local_scales=(caster.visual_scale, target.visual_scale),
        # Generated geometry has no sprite canvas whose registration cancels
        # root padding. Applying the source's forced root put darts at feet.
        anchor_basis="tile_center" if projectile.geometry.enabled else "rig_root",
    )
    cx, cy = center
    first, last = projectile_endpoints(
        (first[0] + cx * caster.visual_scale, first[1] + cy * caster.visual_scale),
        (last[0] + cx * target.visual_scale, last[1] + cy * target.visual_scale),
        projectile.sourceAnchor.axisPx * caster.visual_scale,
        projectile.targetAnchor.forwardPx * target.visual_scale,
    )
    return facing, first, last


def project_projectile(timeline: CastTimeline, effect: ProjectileSample, quadrant: int) -> ProjectileSample:
    """Reproject sprite canvas attachments without changing the compiled clock."""
    application = _application(timeline, effect.application_id)
    if not isfinite(effect.progress) or not 0 <= effect.progress <= 1:
        raise ValueError("projectile phase progress must be finite and between zero and one")
    data = timeline.data
    asset = data.projectile_assets[effect.asset_id]
    cx, cy = projectile_center_offset(timeline.recipe, asset)
    facing, first, last = _projected_endpoints(timeline, application, quadrant, (cx, cy))
    point = _projectile_point(effect.phase, effect.progress, first, last, application.curvature)
    lift, tangent = _projectile_arc(application.source, effect.phase, effect.progress)
    height_pixels = HEIGHT_STEP_PIXELS * data.rig.TILE_W / TILE_WIDTH
    return replace(effect, point=(point[0] - cx, point[1] - cy - lift * height_pixels),
                   row=asset.rowOrder.index(facing),
                   rotation_radians=_projectile_rotation(
                       timeline, effect.phase, facing, first, last,
                       vertical_tangent_px=tangent * height_pixels, curvature=application.curvature,
                   ))


def projectile_curve_point(first: tuple[float, float], last: tuple[float, float],
                 progress: float, curvature: float) -> tuple[float, float]:
    # Source quadratic control = midpoint + perpendicular(chord) * curvature.
    dx, dy = last[0] - first[0], last[1] - first[1]
    bend = 2 * (1 - progress) * progress * curvature
    return (first[0] + dx * progress - dy * bend,
            first[1] + dy * progress + dx * bend)


def projectile_curve_tangent(first: tuple[float, float], last: tuple[float, float],
                             progress: float, curvature: float) -> tuple[float, float]:
    """Derivative of the same source quadratic used by sprite/dart travel."""
    dx, dy = last[0] - first[0], last[1] - first[1]
    bend = 2 * (1 - 2 * progress) * curvature
    return dx - dy * bend, dy + dx * bend


# Source trails keep eight actual rendered frames. A fixed 60 Hz reference
# makes that visual history seekable without changing launch/arrival timing.
_GEOMETRY_TRAIL_STEP_MS = 1000 / 60


def _trail_progresses(application: ApplicationTimeline, progress: float, limit: int) -> tuple[float, ...]:
    duration = application.travel_end_ms - application.travel_start_ms
    elapsed = progress * duration
    last_frame = floor(elapsed / _GEOMETRY_TRAIL_STEP_MS + 1e-10)
    times = [frame * _GEOMETRY_TRAIL_STEP_MS
             for frame in range(max(1, last_frame - limit + 1), last_frame + 1)]
    if not times or abs(times[-1] - elapsed) > 1e-7:
        times.append(elapsed)
    return tuple(at / duration for at in times[-limit:])


def project_geometry_projectile(timeline: CastTimeline, effect: GeometryProjectileSample,
                                quadrant: int) -> GeometryProjectileSample:
    """Project the original screen curve plus independent world-height lift."""
    application = _application(timeline, effect.application_id)
    if not isfinite(effect.progress) or not 0 <= effect.progress <= 1:
        raise ValueError("projectile phase progress must be finite and between zero and one")
    _, first, last = _projected_endpoints(timeline, application, quadrant)
    height_pixels = HEIGHT_STEP_PIXELS * timeline.data.rig.TILE_W / TILE_WIDTH

    def point_at(progress: float) -> tuple[float, float]:
        x, y = projectile_curve_point(first, last, progress, application.curvature)
        lift, _ = _projectile_arc(application.source, "travel", progress)
        return x, y - lift * height_pixels

    trail = tuple(point_at(progress) for progress in _trail_progresses(
        application, effect.progress, timeline.data.dart_style.trailPointLimit,
    ))
    return replace(effect, point=point_at(effect.progress), trail=trail)


def _phase(data: AnimationData, recipe: StudioSpellDraft, binding: StudioProjectilePhase,
           name: Literal["prepare", "travel", "impact"], start: float,
           duration: float | None = None) -> ProjectileInterval:
    projectile = recipe.projectile
    assert projectile is not None and projectile.sprite is not None
    asset_id = binding.assetId or projectile.sprite.assetId
    if asset_id not in data.projectile_assets:
        raise ValueError(f"{name}: unknown projectile assetId {asset_id}")
    asset = data.projectile_assets[asset_id]
    if asset.sheet not in data.resources:
        raise ValueError(f"{name}: missing local projectile media {asset.sheet}")
    phases = {"prepare": asset.phases.cast, "travel": asset.phases.travel, "impact": asset.phases.impact}
    phase = phases[name]
    if phase is None:
        raise ValueError(f"{name}: asset {asset_id} has no {binding.assetPhase} phase")
    # The original travel runner uses the main asset/presentation FPS. Prepare
    # and impact allow the explicit phase override before presentation FPS.
    fps = projectile.fps if name == "travel" else (binding.fps or projectile.fps)
    duration = duration if duration is not None else (
        binding.durationMs if binding.durationMs is not None else phase.frames * 1000 / fps
    )
    return ProjectileInterval(name, asset, phase, fps, start, start + duration)


@dataclass(frozen=True, slots=True)
class DamageTiming:
    start_ms: float
    end_ms: float
    hp_ms: float
    flash_ms: float
    number_ms: float


def resolve_damage(data: AnimationData, damage_type: str | None,
                   override: StudioDamage | None = None, *, critical: bool = False) -> StudioDamage:
    """The original global vital context, optionally overridden by spell data."""
    if override is not None:
        return override
    context = data.damage_context
    palette = context.palette.untyped if damage_type is None else context.palette.byDamageType[damage_type]
    return StudioDamage(
        impactDelayMs=context.impactDelayMs,
        hitFlash=HitFlash(enabled=context.flashEnabled, frame=int(context.flashFrame),
                         durationMs=context.flashDurationMs,
                         color=context.criticalFlashColor if critical else
                         palette.impactColor if context.flashColorMode == "damage_type" else context.flashColor),
        floatingNumber=FloatingNumber(enabled=context.numberEnabled, frame=int(context.numberFrame),
                                      durationMs=context.numberDurationMs,
                                      label=damage_type or context.palette.untyped.label or "Damage",
                                      color=palette.impactColor),
        death=DamageDeath(enabled=True, frame=int(context.deathFrame)),
    )


def compile_damage(data: AnimationData, target: ActorContact, damage: StudioDamage,
                   contact_ms: float, resulting_life_state: LifeState | None) -> DamageTiming:
    """Compile TakeDamage/Die's original callback frames after actual contact."""
    start = contact_ms + damage.impactDelayMs
    terminal = target.life_state == LifeState.DEAD
    lethal = resulting_life_state == LifeState.DEAD
    if lethal and (damage.death is None or not damage.death.enabled):
        raise ValueError("disclosed death requires enabled authored death presentation")
    if terminal or lethal:
        end = start
        if lethal and not terminal:
            end += body_duration(body_clip(data, target, data.death_context.bodyClip), data.death_context.bodyPlaybackSpeed)
        return DamageTiming(start, end, start, start, start)
    metadata = body_clip(data, target, data.damage_context.bodyClip)
    _require_frame(metadata, damage.floatingNumber.frame, "vitals")
    if damage.hitFlash.enabled:
        _require_frame(metadata, damage.hitFlash.frame, "hit flash")
    fps = metadata.fps * data.damage_context.bodyPlaybackSpeed
    return DamageTiming(start, start + body_duration(metadata, data.damage_context.bodyPlaybackSpeed),
                        start + damage.floatingNumber.frame * 1000 / fps,
                        start + damage.hitFlash.frame * 1000 / fps,
                        start + damage.floatingNumber.frame * 1000 / fps)


def sample_damage_body(data: AnimationData, target: ActorContact, elapsed_ms: float, *,
                       start_ms: float | None = None, end_ms: float | None = None,
                       death_start_ms: float | None = None) -> BodySample:
    """One recipient body; callers select the latest actual hit/death interval."""
    clip, start, speed = "Idle", 0.0, 1.0
    if target.life_state == LifeState.DEAD:
        clip = data.death_context.bodyClip
    elif death_start_ms is not None:
        clip, start, speed = data.death_context.bodyClip, death_start_ms, data.death_context.bodyPlaybackSpeed
    elif start_ms is not None and end_ms is not None:
        if elapsed_ms < end_ms:
            clip, start, speed = data.damage_context.bodyClip, start_ms, data.damage_context.bodyPlaybackSpeed
        else:
            start = end_ms
    metadata = body_clip(data, target, clip)
    frame = metadata.frames - 1 if target.life_state == LifeState.DEAD else body_frame(
        elapsed_ms - start, metadata.fps * speed, metadata.frames, loop=clip == "Idle")
    return BodySample(target.actor_uuid, clip, frame, target.facing)


def sample_damage_number(data: AnimationData, actor_uuid: str, damage: StudioDamage,
                         total: int | None, number_ms: float | None, elapsed_ms: float,
                         complete_ms: float, application_id: str | None = None) -> NumberSample | None:
    row = damage.floatingNumber
    if (not row.enabled or total is None or number_ms is None or elapsed_ms >= complete_ms
            or not number_ms <= elapsed_ms < number_ms + row.durationMs):
        return None
    progress = (elapsed_ms - number_ms) / row.durationMs
    fade = data.number_style.fadeStartFraction
    alpha = 1.0 if progress < fade or fade == 1 else (1 - progress) / (1 - fade)
    return NumberSample(actor_uuid, total, row.label, row.color, progress, alpha, application_id)


def compile_cast(data: AnimationData, spell_id: str, source: CastInput) -> CastTimeline:
    """Compile one cast body and its ordered sprite/dart applications."""
    if spell_id not in data.drafts:
        raise ValueError(f"unknown authored spell binding: {spell_id}")
    recipe = data.drafts[spell_id]
    cast, projectile = recipe.cast, recipe.projectile
    if not source.applications:
        raise ValueError("projectile cast requires an application")
    identities = [application.application_id for application in source.applications]
    if len(set(identities)) != len(identities):
        raise ValueError("cast applications require distinct retained identities")
    if source.caster.life_state != LifeState.ALIVE:
        raise ValueError("a terminal caster requires a different admitted action")
    for contact in (source.caster, *(application.target for application in source.applications)):
        if (not all(isfinite(value) for value in (*contact.grid, contact.visual_scale, contact.visual_scale_x,
                                                 contact.elevation_steps, contact.body_lift_px))
                or contact.visual_scale <= 0 or contact.visual_scale_x <= 0):
            raise ValueError("actor contact requires finite coordinates and positive visual scale")
    if cast.bodyPlaybackSpeed is None or cast.equipment is None or cast.effects is None:
        raise ValueError("cast requires the complete original TS-materialized defaults")
    if len({layer.slot for layer in cast.effects}) != len(cast.effects):
        raise ValueError("duplicate cast effect slots require original last-write clearing semantics")
    if recipe.area is not None or projectile is None:
        raise ValueError("selected executor requires projectile delivery without an area")
    if projectile.geometry.enabled:
        if projectile.geometry.primitive != "dart" or projectile.sprite is not None:
            raise ValueError("geometry projectile support is the authored standalone dart")
        if projectile.colors is not None:
            raise ValueError("geometry projectile consumes the selected spell element colors")
    else:
        if projectile.sprite is None:
            raise ValueError("selected sprite projectile requires media")
        if projectile.sprite.mediaFailurePolicy != "fail_transaction":
            raise ValueError("optional-track media omission is outside this selected family")
        if projectile.orientation.directionSource != "target_vector":
            raise ValueError("tangent-facing projectile rows await source parity proof")
        if projectile.travel.assetId not in (None, projectile.sprite.assetId):
            raise ValueError("alternate travel assets require source resolver parity")
        if projectile.sprite.paletteSwap is not None:
            raise ValueError("projectile palette-swap drawing is not implemented yet")
    if not projectile.travel.enabled:
        raise ValueError("disabled travel requires the original resolved phase behavior")
    if cast.equipment.kind not in ("hidden", "unchanged"):
        raise ValueError("weapon selection requires a permitted resolved equipment loadout")
    if data.death_context.media:
        raise ValueError("death media execution is not implemented yet")
    if data.death_context.hiddenSlots:
        raise ValueError("death equipment hiding requires the selected slot presentation adapter")
    caster_rig = body_rig(data, source.caster)
    casting_clip = body_clip(data, source.caster, cast.actionClip)
    body_clip(data, source.caster, "Idle")
    _require_frame(casting_clip, cast.releaseFrame, "release")
    if cast.equipment.kind == "hidden" and "weapon" not in caster_rig.slot_categories:
        raise ValueError(f"actor rig cannot hide a separate weapon layer: {source.caster.rig_id}")
    for layer in (cast.weaponGlow, cast.aura, *cast.effects, cast.slash):
        if layer is None or not layer.enabled or layer.hidden:
            continue
        if layer.category not in caster_rig.slot_categories.get(layer.slot, ()):
            raise ValueError(f"actor rig lacks cast layer capability: {layer.slot}/{layer.category}")
        if casting_clip.sheets.get(layer.category) not in data.resources:
            raise ValueError(f"missing enabled cast layer resource: {layer.category}/{cast.actionClip}")
    body_end = body_duration(casting_clip, cast.bodyPlaybackSpeed)
    release = cast.releaseFrame * 1000 / (casting_clip.fps * cast.bodyPlaybackSpeed)
    anchors = [Anchor("action_start", 0), Anchor("release", release)]
    launch = release
    prepare: ProjectileInterval | None = None
    if projectile.sprite is not None and projectile.prepare.enabled:
        prepare_frame = projectile.prepare.startFrame
        if prepare_frame is None or prepare_frame >= cast.releaseFrame:
            raise ValueError("selected prepare requires an explicit frame before release")
        _require_frame(casting_clip, prepare_frame, "prepare")
        start = prepare_frame * 1000 / (casting_clip.fps * cast.bodyPlaybackSpeed)
        cap = max(1, (cast.releaseFrame - prepare_frame) * 1000 / casting_clip.fps)
        duration = min(projectile.prepare.durationMs or cap, cap)
        prepare = _phase(data, recipe, projectile.prepare, "prepare", start, duration)
        anchors.append(Anchor("prepare", start))
        launch = max(release, prepare.end_ms)
    counts: dict[str, int] = {}
    for application in source.applications:
        counts[application.target.actor_uuid] = counts.get(application.target.actor_uuid, 0) + 1
    indices: dict[str, int] = {}
    applications: list[ApplicationTimeline] = []
    for index, application in enumerate(source.applications):
        target = application.target
        if source.caster.actor_uuid == target.actor_uuid:
            raise ValueError("self delivery is outside the selected projectile family")
        if not isfinite(application.travel_apex_steps) or application.travel_apex_steps < 0:
            raise ValueError("travel apex requires a finite nonnegative world height")
        if (target.life_state in (LifeState.DYING, LifeState.STABLE)
                or application.resulting_life_state in (LifeState.DYING, LifeState.STABLE)):
            raise ValueError("D&D dying/stable are distinct from death; their body presentation is outside this slice")
        if application.resulting_life_state == LifeState.ALIVE:
            raise ValueError("revival is outside the selected damage application")
        if not application.damage_applied and any(value is not None for value in (
            application.damage_total, application.resulting_hp, application.resulting_life_state,
        )):
            raise ValueError("damage values require a disclosed damage application")
        if application.damage_total is not None and application.damage_total <= 0:
            raise ValueError("DamageApplied requires a positive disclosed total, or None when undisclosed")
        body_clip(data, target, "Idle")
        facing = facing_for_delta((target.grid[0] - source.caster.grid[0], target.grid[1] - source.caster.grid[1]), data)
        first, last = _anchored_points(source.caster, target, recipe, data, facing,
                                      _iso(source.caster.grid, data), _iso(target.grid, data))
        if hypot(last[0] - first[0], last[1] - first[1]) < 1:
            raise ValueError("coincident projectile endpoints require the separate source zero-travel case")
        first, last = projectile_endpoints(first, last, projectile.sourceAnchor.axisPx, projectile.targetAnchor.forwardPx)
        height = (body_elevation_steps(target, data) - body_elevation_steps(source.caster, data)) * HEIGHT_STEP_PIXELS / TILE_WIDTH * data.rig.TILE_W
        duration = max(projectile.minimumTravelDurationMs,
                       hypot(last[0] - first[0], last[1] - first[1], height) * 1000 / projectile.speedPxPerSecond)
        start = launch + index * projectile.missileStaggerMs
        arrival = start + duration
        intervals: list[ProjectileInterval] = [prepare] if prepare is not None and index == 0 else []
        if projectile.sprite is not None:
            intervals.append(_phase(data, recipe, projectile.travel, "travel", start, duration))
            if projectile.impact.enabled:
                intervals.append(_phase(data, recipe, projectile.impact, "impact", arrival))
        count, occurrence = counts[target.actor_uuid], indices.get(target.actor_uuid, 0)
        indices[target.actor_uuid] = occurrence + 1
        curvature = 0.0
        if projectile.trajectory.type == "bezier":
            spread = (occurrence / (count - 1) * 2 - 1
                      if projectile.trajectory.sameTargetSpread and count > 1 else 1)
            curvature = projectile.trajectory.curvature * spread
        damage = resolve_damage(data, application.damage_type, recipe.damage) if application.damage_applied else None
        damage_start = damage_end = hp_ms = flash_ms = number_ms = None
        if target.life_state == LifeState.DEAD:
            body_clip(data, target, data.death_context.bodyClip)
        if damage is not None:
            timing = compile_damage(data, target, damage, arrival, application.resulting_life_state)
            damage_start, damage_end = timing.start_ms, timing.end_ms
            hp_ms, flash_ms, number_ms = timing.hp_ms, timing.flash_ms, timing.number_ms
        applications.append(ApplicationTimeline(application, facing, first, last, start, arrival, curvature,
                                                 tuple(intervals), damage, damage_start, damage_end, hp_ms, flash_ms, number_ms))
    # TakingHit reentry flushes pending callbacks, then restarts the one body.
    # Current Magic Missile uses frame 0; this also retains the source's exit
    # meaning for an already authored delayed callback on an earlier hit.
    for index, application in enumerate(applications):
        if application.damage_start_ms is None or application.damage_end_ms is None:
            continue
        following = [other.damage_start_ms for other in applications
                     if other.source.target.actor_uuid == application.source.target.actor_uuid
                     and other.damage_start_ms is not None
                     and application.damage_start_ms < other.damage_start_ms < application.damage_end_ms]
        if following:
            exit_ms = min(following)
            applications[index] = replace(application,
                hp_ms=min(application.hp_ms, exit_ms) if application.hp_ms is not None else None,
                flash_ms=min(application.flash_ms, exit_ms) if application.flash_ms is not None else None,
                number_ms=min(application.number_ms, exit_ms) if application.number_ms is not None else None)
    delivery_end = max(application.travel_end_ms for application in applications)
    for application in applications:
        identity = application.source.application_id
        anchors.extend((Anchor("travel", application.travel_start_ms, identity),
                        Anchor("impact", application.travel_end_ms, identity)))
        if application.damage_start_ms is not None:
            assert application.damage_end_ms is not None and application.hp_ms is not None
            anchors.extend((Anchor("effect", application.damage_start_ms, identity), Anchor("vitals", application.hp_ms, identity)))
            delivery_end = max(delivery_end, application.damage_end_ms)
        if application.projectile_intervals:
            delivery_end = max(delivery_end, *(phase.end_ms for phase in application.projectile_intervals))
    recovery_start = max(body_end, delivery_end)
    complete = recovery_start
    if cast.recovery.enabled:
        complete += body_duration(body_clip(data, source.caster, cast.recovery.bodyClip), cast.recovery.bodyPlaybackSpeed)
        anchors.append(Anchor("recover", recovery_start))
    anchors.append(Anchor("complete", complete))
    return CastTimeline(source, recipe, data, applications[0].facing, body_end, release, tuple(applications),
                        recovery_start, complete, tuple(sorted(anchors, key=lambda anchor: anchor.at_ms)))


def crossed_anchors(timeline: CastTimeline, previous_ms: float, current_ms: float) -> tuple[Anchor, ...]:
    """Account for every crossed source anchor once, including a large step."""
    if not isfinite(previous_ms) or not isfinite(current_ms) or previous_ms > current_ms:
        raise ValueError("anchor accounting requires finite monotonic elapsed times")
    return tuple(anchor for anchor in timeline.anchors if previous_ms < anchor.at_ms <= current_ms)


def sample_cast(timeline: CastTimeline, elapsed_ms: float) -> CastSample:
    """Seek and ordinary playback share this exact value-in/value-out boundary."""
    if not isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("elapsed time must be finite and nonnegative")
    source, recipe, data = timeline.source, timeline.recipe, timeline.data
    cast = recipe.cast
    assert cast.bodyPlaybackSpeed is not None and cast.equipment is not None and cast.effects is not None
    t = elapsed_ms
    caster_clip, caster_start, caster_speed = "Idle", timeline.body_end_ms, 1.0
    cast_layers: tuple[StudioActorLayer, ...] = ()
    casting = t < timeline.body_end_ms
    if casting:
        caster_clip, caster_start, caster_speed = cast.actionClip, 0, cast.bodyPlaybackSpeed
        cast_layers = tuple(layer for layer in (cast.weaponGlow, cast.aura, *cast.effects, cast.slash)
                            if layer is not None and layer.enabled and not layer.hidden)
    elif cast.recovery.enabled and timeline.recovery_start_ms <= t < timeline.complete_ms:
        caster_clip, caster_start, caster_speed = cast.recovery.bodyClip, timeline.recovery_start_ms, cast.recovery.bodyPlaybackSpeed
    elif cast.recovery.enabled and t >= timeline.complete_ms:
        caster_start = timeline.complete_ms
    caster_metadata = body_clip(data, source.caster, caster_clip)
    caster = BodySample(source.caster.actor_uuid, caster_clip,
                        body_frame(t - caster_start, caster_metadata.fps * caster_speed,
                               caster_metadata.frames, loop=caster_clip == "Idle"),
                        timeline.facing, casting and cast.equipment.kind == "hidden", cast_layers)
    bodies = [caster]
    vitals: list[VitalsSample] = []
    targets = {application.source.target.actor_uuid: application.source.target for application in timeline.applications}
    for actor_id, target_contact in targets.items():
        applications = [application for application in timeline.applications if application.source.target.actor_uuid == actor_id]
        hp, life = target_contact.hp, target_contact.life_state
        for application in sorted(applications, key=lambda row: row.hp_ms if row.hp_ms is not None else float("inf")):
            if application.hp_ms is not None and t >= application.hp_ms and application.source.resulting_hp is not None:
                hp = application.source.resulting_hp
        started = sorted((application for application in applications
                          if application.damage_start_ms is not None and application.damage_start_ms <= t),
                         key=lambda row: row.damage_start_ms if row.damage_start_ms is not None else 0)
        death = next((application for application in started if application.source.resulting_life_state == LifeState.DEAD), None)
        if death is not None:
            life = LifeState.DEAD
        reaction = started[-1] if started else None
        bodies.append(sample_damage_body(
            data, target_contact, t,
            start_ms=reaction.damage_start_ms if reaction is not None else None,
            end_ms=reaction.damage_end_ms if reaction is not None else None,
            death_start_ms=death.damage_start_ms if death is not None else None,
        ))
        flashes = [application for application in applications
                   if application.damage is not None and application.damage.hitFlash.enabled
                   and application.flash_ms is not None and application.flash_ms <= t]
        flash = None
        if flashes and t < timeline.complete_ms:
            latest = max(flashes, key=lambda row: row.flash_ms if row.flash_ms is not None else 0)
            assert latest.damage is not None and latest.flash_ms is not None
            if t < latest.flash_ms + latest.damage.hitFlash.durationMs:
                flash = latest.damage.hitFlash.color
        vitals.append(VitalsSample(actor_id, hp, life, flash))
    projectile = recipe.projectile
    assert projectile is not None
    samples: list[ProjectileSample | GeometryProjectileSample] = []
    numbers: list[NumberSample] = []
    for application in timeline.applications:
        identity = application.source.application_id
        if projectile.geometry.enabled and application.travel_start_ms <= t < application.travel_end_ms:
            progress = (t - application.travel_start_ms) / (application.travel_end_ms - application.travel_start_ms)
            trail = tuple(projectile_curve_point(application.from_point, application.to_point, at, application.curvature)
                          for at in _trail_progresses(application, progress, data.dart_style.trailPointLimit))
            samples.append(GeometryProjectileSample(identity, "travel",
                projectile_curve_point(application.from_point, application.to_point, progress, application.curvature), trail, progress))
        for interval in application.projectile_intervals:
            if not interval.start_ms <= t < interval.end_ms:
                continue
            progress = (t - interval.start_ms) / (interval.end_ms - interval.start_ms)
            point = _projectile_point(interval.name, progress, application.from_point, application.to_point,
                                      application.curvature)
            column = interval.phase.start + body_frame(t - interval.start_ms, interval.fps, interval.phase.frames, loop=interval.phase.loop)
            samples.append(ProjectileSample(identity, interval.name, interval.asset.assetId,
                                           column, interval.asset.rowOrder.index(application.facing), point,
                                           _projectile_rotation(timeline, interval.name, application.facing,
                                                                application.from_point, application.to_point,
                                                                curvature=application.curvature), progress))
        damage = application.damage
        if damage is not None:
            number = sample_damage_number(data, application.source.target.actor_uuid, damage,
                application.source.damage_total, application.number_ms, t, timeline.complete_ms, identity)
            if number is not None:
                numbers.append(number)
    return CastSample(tuple(bodies), tuple(samples), tuple(numbers), tuple(vitals), t >= timeline.complete_ms)
