"""Bind ordinary and opportunity attacks to the existing authored profiles.

This is a body/contact executor. The caller retains the complete lineage and
owns its position among other actions; damage comes only from retained facts.
"""

from dataclasses import dataclass, replace
from math import hypot, isfinite
from types import MappingProxyType
from typing import Mapping

from dnd.actions import AttackEvent, SpellEvent
from dnd.core.dice import AttackOutcome
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.events import DamageAppliedEvent, Event, LifeStateChangeEvent
from dnd.core.life_types import LifeState
from game.animation import (
    ActorContact, BodySample, DamageTiming, GeometryProjectileSample, NumberSample, VitalsSample,
    body_clip, body_duration, body_elevation_steps, body_frame, compile_damage, facing_for_delta,
    projectile_curve_point, projectile_curve_tangent, projectile_endpoints, reference_point_contact,
    resolve_damage, sample_damage_body, sample_damage_number,
)
from game.animation_data import resolve_actor_layers
from game.animation_types import (
    ActionFeedback, ActionProjectile, AnimationData, AttackRecipe, AttackVariant, ElementColors, Facing8,
    LayerColors, RigLayer, StudioActorLayer, StudioDamage,
)
from game.combat import actor_contact
from game.presentation import CompletedLineage, PresentationTarget, reduce_lineage
from game.projection import HEIGHT_STEP_PIXELS, TILE_WIDTH, project_world


_OUTCOMES = {
    AttackOutcome.HIT: "hit", AttackOutcome.MISS: "miss",
    AttackOutcome.CRIT: "critical", AttackOutcome.CRIT_MISS: "critical_miss",
}
_PHYSICAL_DAMAGE = frozenset(("Bludgeoning", "Piercing", "Slashing"))


@dataclass(frozen=True, slots=True)
class AttackProjectileTimeline:
    recipe: ActionProjectile
    start_ms: float
    end_ms: float
    from_point: tuple[float, float]
    to_point: tuple[float, float]
    element_colors: ElementColors


@dataclass(frozen=True, slots=True)
class AttackTimeline:
    root_event_uuid: str
    source: ActorContact
    target: ActorContact
    data: AnimationData
    profile_id: str
    clip: str
    playback_speed: float
    facing: Facing8
    contact_ms: float
    body_end_ms: float
    complete_ms: float
    layers: tuple[StudioActorLayer, ...]
    damage: StudioDamage | None
    damage_timing: DamageTiming | None
    damage_total: int | None
    resulting_hp: int | None
    resulting_life_state: LifeState | None
    feedback: ActionFeedback | None
    missing_media: tuple[str, ...]
    projectile: AttackProjectileTimeline | None = None
    authored_clip: str | None = None
    release_ms: float | None = None


@dataclass(frozen=True, slots=True)
class AttackSample:
    bodies: tuple[BodySample, ...]
    numbers: tuple[NumberSample, ...]
    vitals: tuple[VitalsSample, ...]
    complete: bool
    projectiles: tuple[GeometryProjectileSample, ...] = ()


@dataclass(frozen=True, slots=True)
class BoundAttack:
    timeline: AttackTimeline
    after: PresentationTarget
    appearances: Mapping[str, tuple[RigLayer, ...]]


def select_attack_profile(recipe: AttackRecipe, event: AttackEvent) -> AttackVariant | None:
    """Original highest-precedence selector using declaration-time facts.

    Current engine facts use direct authored species/behavior IDs. Existing
    recipe refs bind those identities; labels and live equipment never select
    the profile. Source JSON remains responsible for the variant conditions.
    """
    if event.attack_outcome is None:
        return None
    delivery = "projectile" if event.weapon_slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF) else "melee"
    damage_types = tuple(row.value for row in event.damage_types)
    primary = damage_types[0] if damage_types else None
    elemental = any(row not in _PHYSICAL_DAMAGE for row in damage_types)
    item_id = event.source_item_presentation.item_id if event.source_item_presentation is not None else None
    candidates: list[AttackVariant] = []
    for candidate in recipe.variants:
        match = candidate.match
        if ((match.delivery is None or match.delivery == delivery)
                and (match.weaponSlots is None or event.weapon_slot.value in match.weaponSlots)
                and (match.outcomes is None or _OUTCOMES[event.attack_outcome] in match.outcomes)
                and (match.primaryDamageTypes is None or primary in match.primaryDamageTypes)
                and (match.elemental is None or match.elemental == elemental)
                and (match.sourceItemRefs is None or any(ref.content_id == item_id for ref in match.sourceItemRefs))):
            candidates.append(candidate)
    if not candidates:
        return None
    highest = max(row.precedence for row in candidates)
    winners = [row for row in candidates if row.precedence == highest]
    if len(winners) != 1:
        raise ValueError(f"authored attack profiles tie for {recipe.definitionRef.content_id}")
    return winners[0]


def _attack_colors(data: AnimationData, event: AttackEvent) -> ElementColors:
    types = tuple(row.value for row in event.damage_types)
    elemental = next((row for row in types if row not in _PHYSICAL_DAMAGE), types[0] if types else None)
    palette = data.damage_context.palette
    return (palette.untyped if elemental is None else palette.byDamageType[elemental]).elementColors


def _attack_layers(data: AnimationData, source: ActorContact, profile: AttackVariant,
                   event: AttackEvent) -> tuple[tuple[StudioActorLayer, ...], tuple[str, ...]]:
    hit = event.attack_outcome in (AttackOutcome.HIT, AttackOutcome.CRIT)
    rules = profile.attackVfx
    selected = (rules.onMiss if not hit else rules.onCrit
                if event.attack_outcome is AttackOutcome.CRIT and rules.onCrit is not None else rules.onHit)
    colors = _attack_colors(data, event)
    tokens = {"white": 0xFFFFFF, "$element": colors.primary,
              "$element.primary": colors.primary, "$element.secondary": colors.secondary,
              "$element.tertiary": colors.tertiary}
    rig = data.rigs[source.rig_id]
    clip = rig.clips.get(profile.actor.clip)
    layers: list[StudioActorLayer] = []
    missing: list[str] = []
    for slot, layer in selected.items():
        # The selected source attack profiles author a slash track. A fixed
        # creature body has no separable slash slot; this is media coverage,
        # not a reason to discard its attack or damage presentation.
        if (clip is None or slot != "slash" or layer.category not in rig.slot_categories.get(slot, ())
                or clip.sheets.get(layer.category) not in data.resources):
            missing.append(f"{source.rig_id}/{profile.actor.clip}/{slot}/{layer.category}")
            continue
        tint = layer.tint if isinstance(layer.tint, int) else tokens[layer.tint]
        layers.append(StudioActorLayer(
            id=f"attack.{slot}", slot="slash", enabled=True, hidden=False,
            category=layer.category,
            colors=LayerColors(source="override", primary=tint, mode="tint"),
        ))
    return tuple(layers), tuple(missing)


def _semantic_projectile_endpoints(data: AnimationData, source: ActorContact, target: ActorContact,
                                   recipe: ActionProjectile, quadrant: int, *, include_height: bool,
                                   ) -> tuple[tuple[float, float], tuple[float, float]]:
    """AttackClip's semantic body anchors, which already use the tile center."""
    factor = data.rig.TILE_W / TILE_WIDTH
    start = project_world(source.grid, quadrant=quadrant,
                          elevation_steps=body_elevation_steps(source, data) if include_height else 0)
    end = project_world(target.grid, quadrant=quadrant,
                        elevation_steps=body_elevation_steps(target, data) if include_height else 0)
    first = start[0] * factor + recipe.originX * source.visual_scale, start[1] * factor + recipe.originY * source.visual_scale
    last = end[0] * factor, end[1] * factor + recipe.targetY * target.visual_scale
    return projectile_endpoints(first, last, recipe.sourceForwardPx, recipe.targetForwardPx)


def _bolt_sample(data: AnimationData, first: tuple[float, float], last: tuple[float, float],
                 progress: float, recipe: ActionProjectile) -> GeometryProjectileSample:
    curvature = recipe.trajectory.curvature if recipe.trajectory.type == "bezier" else 0
    point = projectile_curve_point(first, last, progress, curvature)
    dx, dy = projectile_curve_tangent(first, last, progress, curvature)
    length = min(data.bolt_style.maximumLengthPx,
                 hypot(last[0] - first[0], last[1] - first[1]) * data.bolt_style.distanceLengthRatio)
    tangent_length = hypot(dx, dy)
    tail = (point[0] - dx * length / tangent_length,
            point[1] - dy * length / tangent_length) if tangent_length else point
    return GeometryProjectileSample(None, "travel", point, (tail, point), progress, "bolt")


def project_attack_projectile(timeline: AttackTimeline, effect: GeometryProjectileSample,
                              quadrant: int) -> GeometryProjectileSample:
    projectile = timeline.projectile
    assert projectile is not None
    first, last = _semantic_projectile_endpoints(timeline.data, timeline.source, timeline.target,
                                                projectile.recipe, quadrant, include_height=True)
    return _bolt_sample(timeline.data, first, last, effect.progress, projectile.recipe)


def attack_projectile_contact(timeline: AttackTimeline, effect: GeometryProjectileSample,
                              quadrant: int) -> tuple[tuple[float, float], float]:
    """The rendered point's body lift remains height rather than ground drift."""
    projectile = timeline.projectile
    assert projectile is not None
    source, target, progress = timeline.source, timeline.target, effect.progress
    lift = (projectile.recipe.originY * source.visual_scale * (1 - progress)
            + projectile.recipe.targetY * target.visual_scale * progress)
    height = (body_elevation_steps(source, timeline.data) * (1 - progress)
              + body_elevation_steps(target, timeline.data) * progress
              - lift * TILE_WIDTH / timeline.data.rig.TILE_W / HEIGHT_STEP_PIXELS)
    return reference_point_contact(timeline.data, effect.point, height, quadrant), height


def bind_attack(before: PresentationTarget, lineage: CompletedLineage, data: AnimationData,
                *, facings: Mapping[str, Facing8] | None = None,
                contacts: Mapping[str, ActorContact] | None = None) -> BoundAttack | None:
    """Bind one retained attack root; geometry remains authored profile data."""
    root = lineage.root
    if not isinstance(root, AttackEvent):
        raise ValueError("attack binding requires a retained AttackEvent root")
    if root.behavior_id is None or root.behavior_id not in data.attack_recipes:
        return None
    recipe = data.attack_recipes[root.behavior_id]
    profile = select_attack_profile(recipe, root)
    if (profile is None or not profile.actor.enabled
            or profile.actor.hiddenSlots or profile.actor.media):
        return None
    if profile.projectile is not None and (not profile.projectile.geometry.enabled
                                          or profile.projectile.geometry.primitive != "bolt"):
        return None
    if (root.source_entity_uuid not in before.actors or root.target_entity_uuid is None
            or root.target_entity_uuid not in before.actors):
        return None
    source_actor, target_actor = before.actors[root.source_entity_uuid], before.actors[root.target_entity_uuid]
    facings = facings or {}
    contacts = contacts or {}
    source = contacts.get(str(source_actor.uuid)) or actor_contact(before, source_actor, data, facings.get(str(source_actor.uuid), "S"))
    target = contacts.get(str(target_actor.uuid)) or actor_contact(before, target_actor, data, facings.get(str(target_actor.uuid), "S"))
    facing = facing_for_delta((target.grid[0] - source.grid[0], target.grid[1] - source.grid[1]), data)
    source = replace(source, facing=facing)
    display_clip = profile.actor.clip
    body_missing: tuple[str, ...] = ()
    if profile.actor.clip not in data.rigs[source.rig_id].clips:
        # Fixed Goblin01 has only melee sheets. Preserve the authored clock
        # with an explicit Idle body, rather than relabel an axe swing as bow art.
        if profile.projectile is None:
            return None
        clip = data.rigs[data.root_rig].clips[profile.actor.clip]
        display_clip = "Idle"
        body_missing = (f"{source.rig_id}/{profile.actor.clip}/body",)
    else:
        clip = body_clip(data, source, profile.actor.clip)
    names = ("release",) if profile.projectile is not None else ("impact", "contact", "effect")
    frame = next((row.frame for name in names
                  for row in profile.anchors if row.name == name), None)
    if frame is None or frame >= clip.frames:
        return None
    release = contact = frame * 1000 / (clip.fps * profile.actor.playbackSpeed)
    body_end = body_duration(clip, profile.actor.playbackSpeed)
    projectile = None
    if profile.projectile is not None:
        first, last = _semantic_projectile_endpoints(data, source, target, profile.projectile, 0, include_height=False)
        planar = hypot(last[0] - first[0], last[1] - first[1])
        height = (body_elevation_steps(target, data) - body_elevation_steps(source, data)) * HEIGHT_STEP_PIXELS * data.rig.TILE_W / TILE_WIDTH
        duration = (max(profile.projectile.minimumTravelDurationMs,
                        hypot(planar, height) * 1000 / profile.projectile.speedPxPerSecond)
                    if hypot(planar, height) >= 1 else 0)
        contact += duration
        projectile = AttackProjectileTimeline(profile.projectile, release, contact, first, last, _attack_colors(data, root))
    by_lineage = {event.lineage_uuid: event for event in lineage.events}

    def primary_effect(event: Event) -> bool:
        """Nested actions own their own effects in the shared causal composition."""
        parent = event.parent_lineage
        while parent is not None and parent != root.lineage_uuid:
            ancestor = by_lineage[parent]
            if isinstance(ancestor, (AttackEvent, SpellEvent)):
                return False
            parent = ancestor.parent_lineage
        return parent == root.lineage_uuid

    applied = [event for event in lineage.events if isinstance(event, DamageAppliedEvent) and primary_effect(event)]
    if len(applied) > 1 or any(event.target_entity_uuid != target_actor.uuid for event in applied):
        return None
    changes = [event for event in lineage.events if isinstance(event, LifeStateChangeEvent)
               and event.entity_uuid == target_actor.uuid and primary_effect(event)]
    if len(changes) > 1:
        return None
    life = changes[0].new_state if changes else None
    fact = applied[0] if applied else None
    damage = resolve_damage(data, fact.damage_type.value, critical=root.attack_outcome is AttackOutcome.CRIT) if fact is not None else None
    timing = compile_damage(data, target, damage, contact, life) if damage is not None else None
    layers, missing = _attack_layers(data, source, profile, root)
    assert root.attack_outcome is not None
    timeline = AttackTimeline(
        root_event_uuid=str(root.uuid), source=source, target=target, data=data,
        profile_id=profile.id, clip=display_clip, playback_speed=profile.actor.playbackSpeed,
        facing=facing, contact_ms=contact, body_end_ms=body_end,
        # FloatingText.run returns immediately: a badge fade does not hold the
        # causal join. The enclosing historical head owns overlay retirement.
        complete_ms=max(body_end, timing.end_ms if timing is not None else contact), layers=layers,
        damage=damage, damage_timing=timing, damage_total=fact.applied_damage if fact is not None else None,
        resulting_hp=fact.resulting_normal_hp if fact is not None else None, resulting_life_state=life,
        feedback=recipe.attackFeedback[_OUTCOMES[root.attack_outcome]], missing_media=(*body_missing, *missing),
        projectile=projectile, authored_clip=profile.actor.clip,
        release_ms=release if projectile is not None else None,
    )
    appearances = {
        contact.actor_uuid: resolve_actor_layers(
            data, actor.appearance, actor.items, actor.equipment,
            (WeaponSet.RANGED if profile.projectile is not None else WeaponSet.MELEE)
            if actor.uuid == source_actor.uuid else actor.active_weapon_set, rig_id=contact.rig_id,
        ) for actor, contact in ((source_actor, source), (target_actor, target))
    }
    return BoundAttack(timeline, reduce_lineage(before, lineage), MappingProxyType(appearances))


def sample_attack(timeline: AttackTimeline, elapsed_ms: float) -> AttackSample:
    """Sample the original attack body and its contact-started damage join."""
    if not isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("elapsed time must be finite and nonnegative")
    data, source, target, t = timeline.data, timeline.source, timeline.target, elapsed_ms
    attacking = t < timeline.body_end_ms
    clip_name = timeline.clip if attacking else "Idle"
    clip = body_clip(data, source, clip_name)
    body = BodySample(source.actor_uuid, clip_name, body_frame(
        t if attacking else t - timeline.body_end_ms,
        clip.fps * timeline.playback_speed if attacking else clip.fps, clip.frames,
        loop=not attacking or clip_name == "Idle"), timeline.facing, cast_layers=timeline.layers if attacking else ())
    timing, damage = timeline.damage_timing, timeline.damage
    started = timing is not None and t >= timing.start_ms
    hp, life, flash = target.hp, target.life_state, None
    if timing is not None and t >= timing.hp_ms:
        hp = timeline.resulting_hp if timeline.resulting_hp is not None else hp
        life = timeline.resulting_life_state or life
    recipient = sample_damage_body(data, target, t,
        start_ms=timing.start_ms if started and timing is not None else None,
        end_ms=timing.end_ms if started and timing is not None else None,
        death_start_ms=timing.start_ms if started and timing is not None and life == LifeState.DEAD else None)
    numbers: list[NumberSample] = []
    if timing is not None and damage is not None:
        if (damage.hitFlash.enabled and timing.flash_ms <= t < timing.flash_ms + damage.hitFlash.durationMs
                and t < timeline.complete_ms):
            flash = damage.hitFlash.color
        number = sample_damage_number(data, target.actor_uuid, damage, timeline.damage_total,
                                      timing.number_ms, t, timeline.complete_ms)
        if number is not None:
            numbers.append(number)
    feedback, style = timeline.feedback, data.badge_style
    if feedback is not None and timeline.contact_ms <= t < min(timeline.complete_ms, timeline.contact_ms + style.durationMs):
        progress = (t - timeline.contact_ms) / style.durationMs
        alpha = 1.0 if progress < style.fadeStartFraction else (1 - progress) / (1 - style.fadeStartFraction)
        numbers.append(NumberSample(target.actor_uuid, None, feedback.text, feedback.color,
                                    progress, alpha, kind="badge"))
    projectiles: tuple[GeometryProjectileSample, ...] = ()
    projectile = timeline.projectile
    if projectile is not None and projectile.start_ms <= t < projectile.end_ms:
        progress = (t - projectile.start_ms) / (projectile.end_ms - projectile.start_ms)
        projectiles = (_bolt_sample(data, projectile.from_point, projectile.to_point, progress, projectile.recipe),)
    return AttackSample((body, recipient), tuple(numbers),
                        (VitalsSample(target.actor_uuid, hp, life, flash),), t >= timeline.complete_ms,
                        projectiles)
