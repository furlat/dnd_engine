"""Bind ordinary and opportunity attacks to the existing authored profiles.

This is a body/contact executor. The caller retains the complete lineage and
owns its position among other actions; damage comes only from retained facts.
"""

from dataclasses import dataclass, replace
from math import hypot, isfinite
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from dnd.core.dice import AttackOutcome
from dnd.core.equipment_types import WeaponSlot
from dnd.core.life_types import LifeState
from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallPolyline, WallSegment
from game.animation import (
    ActorContact, ObjectContact, BodySample, DamageTiming, GeometryProjectileSample, NumberSample, VitalsSample,
    feedback_identity,
    actor_point_offset, view_facing,
    body_clip, body_duration, body_elevation_steps, body_frame, compile_damage, facing_for_delta,
    projectile_curve_point, projectile_curve_tangent, projectile_endpoints, reference_point_contact,
    resolve_damage, sample_damage_body, sample_damage_number, rest_pose_offset,
)
from game.animation_data import resolve_player_layers
from game.animation_rates import action_playback_rate
from game.animation_types import (
    ActionFeedback, ActionProjectile, AnimationData, AttackRecipe, AttackVariant, ChildAttackPresentation, ElementColors, Facing8,
    LayerColors, RigLayer, StudioActorLayer, StudioDamage, WeaponTrailPose, WeaponTrailPresentation,
)
from game.combat import actor_contact, object_contact
from game.player_facts import AttackFact, DamageResultFact, ObjectDamageFact, LifeFact, PlayerLineage, PlayerNode, PlayerState
from game.player_reduction import PlayerCausalIndex, index_player_lineage, reduce_lineage
from game.projection import HEIGHT_STEP_PIXELS, TILE_WIDTH, project_world


_OUTCOMES = {
    AttackOutcome.HIT: "hit", AttackOutcome.MISS: "miss",
    AttackOutcome.CRIT: "critical", AttackOutcome.CRIT_MISS: "critical_miss",
}
_PHYSICAL_DAMAGE = frozenset(("Bludgeoning", "Piercing", "Slashing"))


@dataclass(frozen=True, slots=True)
class ProjectileInterception:
    position: tuple[float, float]
    fraction: float
    tangent: tuple[float, float]
    components: str


def _received_interception(fact: AttackFact, before: PlayerState, data: AnimationData,
        start: tuple[float, float], end: tuple[float, float]) -> ProjectileInterception | None:
    point = fact.projectile_deflection_position
    if point is None or before.senses is None or fact.intercepted_by_condition_uuid is None:
        return None
    owner = before.senses.spatial_effects.get(fact.intercepted_by_condition_uuid)
    if owner is None or not isinstance(owner.area_geometry, WallAssemblyPresentationGeometry):
        return None
    binding = data.spatial_media.get(owner.content_ref.content_id)
    if binding is None or binding.interceptionComponents is None:
        return None
    path = owner.area_geometry.path
    points = (path.start,path.end) if isinstance(path,WallSegment) else path.points if isinstance(path,WallPolyline) else ()
    candidates = []
    for a,b in zip(points,points[1:]):
        dx,dy = b[0]-a[0],b[1]-a[1]
        length2 = dx*dx+dy*dy
        t = min(1.,max(0.,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length2))
        candidates.append((hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy),(dx,dy)))
    if not candidates:
        return None
    dx,dy = end[0]-start[0],end[1]-start[1]
    length2 = dx*dx+dy*dy
    if not length2:
        return None
    fraction = min(1.,max(0.,((point[0]-start[0])*dx+(point[1]-start[1])*dy)/length2))
    return ProjectileInterception(point,fraction,min(candidates)[1],binding.interceptionComponents)


@dataclass(frozen=True, slots=True)
class AttackProjectileTimeline:
    recipe: ActionProjectile
    start_ms: float
    end_ms: float
    from_point: tuple[float, float]
    to_point: tuple[float, float]
    element_colors: ElementColors
    interception: ProjectileInterception | None = None


@dataclass(frozen=True, slots=True)
class AttackTimeline:
    root_event_uuid: str
    source: ActorContact
    target: ActorContact | ObjectContact
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
    results: tuple[PlayerNode, ...] = ()
    weapon_trail: WeaponTrailPresentation | None = None
    weapon_pose: WeaponTrailPose | None = None
    contact_scale: float = 1
    show_contact: bool = False


@dataclass(frozen=True, slots=True)
class AttackSample:
    bodies: tuple[BodySample, ...]
    numbers: tuple[NumberSample, ...]
    vitals: tuple[VitalsSample, ...]
    complete: bool
    projectiles: tuple[GeometryProjectileSample, ...] = ()
    elapsed_ms: float = 0


@dataclass(frozen=True, slots=True)
class BoundAttack:
    timeline: AttackTimeline
    after: PlayerState
    appearances: Mapping[str, tuple[RigLayer, ...]]
    owned_life_events: frozenset[UUID] = frozenset()


def attack_actor_contacts(timeline: AttackTimeline) -> tuple[ActorContact, ...]:
    return ((timeline.source, timeline.target) if isinstance(timeline.target, ActorContact)
            else (timeline.source,))


def select_attack_profile(recipe: AttackRecipe, event: AttackFact, rig_id: str | None = None) -> AttackVariant | None:
    """Original highest-precedence selector using declaration-time facts.

    Current engine facts use direct authored species/behavior IDs. Existing
    recipe refs bind those identities; labels and live equipment never select
    the profile. Source JSON remains responsible for the variant conditions.
    """
    delivery = "projectile" if event.weapon_slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF) else "melee"
    damage_types = tuple(row.value for row in event.damage_types)
    primary = damage_types[0] if damage_types else None
    elemental = any(row not in _PHYSICAL_DAMAGE for row in damage_types)
    item_id = event.source_item_id
    candidates: list[AttackVariant] = []
    for candidate in recipe.variants:
        match = candidate.match
        if ((match.rigIds is None or rig_id in match.rigIds)
                and (match.sourceKinds is None or event.attack_source_kind in match.sourceKinds)
                and (match.delivery is None or match.delivery == delivery)
                and (match.weaponSlots is None or event.weapon_slot.value in match.weaponSlots)
                and (match.outcomes is None or event.attack_outcome is not None
                     and _OUTCOMES[event.attack_outcome] in match.outcomes)
                and (match.primaryDamageTypes is None or primary in match.primaryDamageTypes)
                and (match.elemental is None or match.elemental == elemental)
                and (match.sourceItemRefs is None or any(ref.content_id == item_id for ref in match.sourceItemRefs))
                and (match.sourceItemIds is None or item_id in match.sourceItemIds)):
            candidates.append(candidate)
    if not candidates:
        return None
    highest = max(row.precedence for row in candidates)
    winners = [row for row in candidates if row.precedence == highest]
    if len(winners) != 1:
        raise ValueError(f"authored attack profiles tie for {recipe.definitionRef.content_id}")
    return winners[0]


def _attack_colors(data: AnimationData, event: AttackFact) -> ElementColors:
    types = tuple(row.value for row in event.damage_types)
    elemental = next((row for row in types if row not in _PHYSICAL_DAMAGE), types[0] if types else None)
    palette = data.damage_context.palette
    return (palette.untyped if elemental is None else palette.byDamageType[elemental]).elementColors


def _attack_layers(data: AnimationData, source: ActorContact, profile: AttackVariant,
                   event: AttackFact) -> tuple[tuple[StudioActorLayer, ...], tuple[str, ...]]:
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


def _projectile_source_offset(data: AnimationData, source: ActorContact,
                              recipe: ActionProjectile, quadrant: int) -> tuple[float, float]:
    sockets = recipe.sourceSocketsByRig.get(source.rig_id)
    if sockets is not None:
        point = sockets.release[view_facing(source.facing, quadrant, data)]
        return actor_point_offset(data, source, (point.x, point.y))
    return recipe.originX * source.visual_scale, recipe.originY * source.visual_scale


def _semantic_projectile_endpoints(data: AnimationData, source: ActorContact, target: ActorContact | ObjectContact,
                                   recipe: ActionProjectile, quadrant: int, *, include_height: bool,
                                   ) -> tuple[tuple[float, float], tuple[float, float]]:
    """Measured release sockets or the profile's semantic body anchors."""
    factor = data.rig.TILE_W / TILE_WIDTH
    start = project_world(source.grid, quadrant=quadrant,
                          elevation_steps=body_elevation_steps(source, data) if include_height else 0)
    target_height = body_elevation_steps(target, data) if isinstance(target, ActorContact) else target.elevation_steps
    end = project_world(target.grid, quadrant=quadrant, elevation_steps=target_height if include_height else 0)
    dx, dy = _projectile_source_offset(data, source, recipe, quadrant)
    first = start[0] * factor + dx, start[1] * factor + dy
    lift = recipe.targetY * target.visual_scale if isinstance(target, ActorContact) else 0
    last = end[0] * factor, end[1] * factor + lift
    first, last = projectile_endpoints(first, last, recipe.sourceForwardPx, recipe.targetForwardPx)
    dx, dy = rest_pose_offset(data, target, quadrant) if isinstance(target, ActorContact) else (0, 0)
    return first, (last[0] + dx, last[1] + dy)


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
    if projectile.interception is not None:
        fraction = projectile.interception.fraction
        sampled = _bolt_sample(timeline.data,first,last,effect.progress*fraction,projectile.recipe)
        height = attack_projectile_height(timeline, 1., quadrant)
        end = project_world(projectile.interception.position, quadrant=quadrant, elevation_steps=height)
        factor = timeline.data.rig.TILE_W / TILE_WIDTH
        curvature = projectile.recipe.trajectory.curvature if projectile.recipe.trajectory.type == 'bezier' else 0
        original_end = projectile_curve_point(first,last,fraction,curvature)
        correction = end[0]*factor-original_end[0],end[1]*factor-original_end[1]
        # Preserve the original curve's elapsed parameter and bolt length.
        # Only the socket inset is blended out at the native wall contact.
        point = sampled.point[0]+effect.progress*correction[0],sampled.point[1]+effect.progress*correction[1]
        dx,dy = projectile_curve_tangent(first,last,effect.progress*fraction,curvature)
        dx,dy = dx*fraction+correction[0],dy*fraction+correction[1]
        length = hypot(sampled.point[0]-sampled.trail[0][0],sampled.point[1]-sampled.trail[0][1])
        norm = max(hypot(dx,dy),1e-9)
        return replace(sampled,point=point,trail=((point[0]-dx*length/norm,point[1]-dy*length/norm),point),progress=effect.progress)
    return _bolt_sample(timeline.data, first, last, effect.progress, projectile.recipe)


def attack_projectile_height(timeline: AttackTimeline, progress: float, quadrant: int) -> float:
    """Interception cuts the existing source-to-target height interpolation."""
    projectile = timeline.projectile
    assert projectile is not None
    source, target = timeline.source, timeline.target
    if projectile.interception is not None:
        progress *= projectile.interception.fraction
    target_lift = (projectile.recipe.targetY * target.visual_scale
                   + rest_pose_offset(timeline.data, target, quadrant)[1]) if isinstance(target, ActorContact) else 0
    target_height = body_elevation_steps(target, timeline.data) if isinstance(target, ActorContact) else target.elevation_steps
    source_lift = _projectile_source_offset(timeline.data, source, projectile.recipe, quadrant)[1]
    lift = source_lift * (1 - progress) + target_lift * progress
    height = (body_elevation_steps(source, timeline.data) * (1 - progress)
              + target_height * progress
              - lift * TILE_WIDTH / timeline.data.rig.TILE_W / HEIGHT_STEP_PIXELS)
    return height


def attack_projectile_contact(timeline: AttackTimeline, effect: GeometryProjectileSample,
                              quadrant: int) -> tuple[tuple[float, float], float]:
    """The rendered point's body lift remains height rather than ground drift."""
    height = attack_projectile_height(timeline, effect.progress, quadrant)
    return reference_point_contact(timeline.data, effect.point, height, quadrant), height


def bind_attack(before: PlayerState, lineage: PlayerLineage, data: AnimationData,
                *, facings: Mapping[str, Facing8] | None = None,
                contacts: Mapping[str, ActorContact] | None = None,
                child_presentation: ChildAttackPresentation | None = None,
                causal_index: PlayerCausalIndex | None = None,
                emitting_handlers: tuple[str, ...] = ()) -> BoundAttack | None:
    """Bind one retained attack root; geometry remains authored profile data."""
    root_node = lineage.root
    root = root_node.fact
    if not isinstance(root, AttackFact):
        raise ValueError("attack binding requires a retained AttackFact root")
    if root.behavior_id is None or root.behavior_id not in data.attack_recipes:
        return None
    recipe = data.attack_recipes[root.behavior_id]
    source_actor = before.actors.get(root.source_entity_uuid)
    target_actor = before.actors.get(root.target_entity_uuid) if root.target_kind == "creature" else None
    if source_actor is None or root.target_kind == "creature" and target_actor is None:
        return None
    facings = facings or {}
    contacts = contacts or {}
    source = contacts.get(str(source_actor.uuid)) or actor_contact(before, source_actor, data, facings.get(str(source_actor.uuid), "S"))
    profile = select_attack_profile(recipe, root, source.rig_id)
    if (profile is None or not profile.actor.enabled
            or profile.actor.hiddenSlots or profile.actor.media):
        return None
    if profile.projectile is not None and (not profile.projectile.geometry.enabled
                                          or profile.projectile.geometry.primitive != "bolt"):
        return None
    rate = action_playback_rate(data, source_actor)
    if rate != 1:
        profile = profile.model_copy(update={"actor": profile.actor.model_copy(
            update={"playbackSpeed": profile.actor.playbackSpeed*rate})})
    if target_actor is not None:
        target = contacts.get(str(target_actor.uuid)) or actor_contact(before, target_actor, data,
            facings.get(str(target_actor.uuid), "S"))
        # Placed contacts can predate earlier children in the same action.
        # Keep that placement, but each attack owns its retained recipient state.
        target = replace(target, hp=target_actor.normal_hp, life_state=target_actor.life_state)
    else:
        target = object_contact(before, root.target_entity_uuid,
            position=root.target_position, base_height_steps=root.target_base_height_steps)
    if target is None:
        return None
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
        target_height = body_elevation_steps(target, data) if isinstance(target, ActorContact) else target.elevation_steps
        height = (target_height - body_elevation_steps(source, data)) * HEIGHT_STEP_PIXELS * data.rig.TILE_W / TILE_WIDTH
        duration = (max(profile.projectile.minimumTravelDurationMs,
                        hypot(planar, height) * 1000 / profile.projectile.speedPxPerSecond)
                    if hypot(planar, height) >= 1 else 0)
        interception = _received_interception(root, before, data, source.grid, target.grid)
        contact += duration * (interception.fraction if interception is not None else 1)
        projectile = AttackProjectileTimeline(profile.projectile, release, contact, first, last, _attack_colors(data, root), interception)
    index = causal_index if causal_index is not None else index_player_lineage(lineage)
    reference = root_node.resolution_ref
    owned = index.owned.get(reference, ()) if reference is not None else ()
    results = index.results.get(reference, ()) if reference is not None else ()
    applied = [node.fact for node in results if isinstance(node.fact, DamageResultFact)]
    if any(event.target_entity_uuid != root.target_entity_uuid for event in applied):
        raise ValueError("Attack result belongs to a different recipient")
    changes = [(event.uuid, event.fact) for event in owned if isinstance(event.fact, LifeFact)
               and event.fact.entity_uuid == root.target_entity_uuid and not event.canceled]
    life = changes[-1][1].new_state if changes else None
    fact = applied[-1] if applied else None
    object_packets = [node.fact for node in results if isinstance(node.fact, ObjectDamageFact)
                      and node.fact.object_uuid == root.target_entity_uuid]
    object_damage = object_packets[-1] if object_packets else None
    damage_type = fact.damage_type if fact is not None else object_damage.damage_type if object_damage is not None else None
    damage = (resolve_damage(data, damage_type.value if damage_type is not None else None,
                             critical=root.attack_outcome is AttackOutcome.CRIT)
              if fact is not None or object_damage is not None else None)
    timing = compile_damage(data, target, damage, contact, life) if damage is not None and isinstance(target, ActorContact) else None
    layers, missing = _attack_layers(data, source, profile, root)
    appearances = {source.actor_uuid: resolve_player_layers(data, source_actor, rig_id=source.rig_id,
                                                            active_weapon_set=root.weapon_set)}
    if target_actor is not None and isinstance(target, ActorContact):
        appearances[target.actor_uuid] = resolve_player_layers(data, target_actor, rig_id=target.rig_id)
    weapon_trail = (recipe.weaponTrail if projectile is None
        and root.attack_source_kind == 'equipped' and not root_node.canceled else None)
    if weapon_trail is not None and not (root.behavior_id in weapon_trail.behaviorIds
            or any(identity in weapon_trail.handlerIds for identity in emitting_handlers)
            or root.attack_outcome is not None and _OUTCOMES[root.attack_outcome] in weapon_trail.outcomes):
        weapon_trail=None
    weapon_pose = None
    if weapon_trail is not None:
        slot = 'offhand' if root.weapon_slot == WeaponSlot.MELEE_OFF else 'weapon'
        category = next((layer.category for layer in appearances[source.actor_uuid] if layer.slot == slot), None)
        weapon_pose = next((pose for pose in weapon_trail.poses
            if (pose.rigId, pose.category, pose.clip) == (source.rig_id, category, display_clip)), None)
        if weapon_pose is not None and all(row.value in _PHYSICAL_DAMAGE for row in root.damage_types):
            layers = tuple(layer for layer in layers if layer.slot != 'slash')
    show_contact = weapon_trail is not None and root.attack_outcome in (AttackOutcome.HIT, AttackOutcome.CRIT)
    contact_end = contact
    if show_contact and weapon_trail is not None:
        impact = data.projectile_assets[weapon_trail.impactAssetId].phases.impact
        if impact is None:
            raise ValueError('Weapon contact media requires an impact phase')
        contact_end += impact.frames * 1000 / (impact.fps or data.projectile_assets[weapon_trail.impactAssetId].fps)
    if child_presentation is not None:
        weapon = next((layer.category for layer in appearances[source.actor_uuid] if layer.slot == "weapon"), None)
        poses = [pose for pose in child_presentation.poses
                 if (pose.rigId, pose.weaponCategory, pose.clip) == (source.rig_id, weapon, display_clip)]
        if not poses:
            poses = [pose for pose in child_presentation.poses if pose.weaponCategory is None
                     and (pose.rigId, pose.clip) == (source.rig_id, display_clip)]
        if len(poses) > 1:
            raise ValueError("child attack has ambiguous authored weapon-pose layers")
        if poses:
            layers = (*layers, *(layer for layer in poses[0].layers if layer.enabled and not layer.hidden))
            slots = [layer.slot for layer in layers]
            if len(slots) != len(set(slots)):
                raise ValueError("child attack layers must have distinct destination slots")
        else:
            missing = (*missing, f"child_attack/{source.rig_id}/{weapon}/{display_clip}")
    if projectile is not None and projectile.interception is not None:
        contact_end = max(contact_end, contact + 1000)
    timeline = AttackTimeline(
        root_event_uuid=str(root_node.uuid), source=source, target=target, data=data,
        profile_id=profile.id, clip=display_clip, playback_speed=profile.actor.playbackSpeed,
        facing=facing, contact_ms=contact, body_end_ms=body_end,
        # FloatingText.run returns immediately: a badge fade does not hold the
        # causal join. The enclosing historical head owns overlay retirement.
        complete_ms=max(body_end, timing.end_ms if timing is not None else contact, contact_end), layers=layers,
        damage=damage, damage_timing=timing, results=results,
        damage_total=(sum(row.applied_damage for row in applied) if applied
            else sum(row.applied_damage for row in object_packets) if object_packets else None),
        # The owned life commit may normalize the packet's intermediate HP
        # (for example, entering DYING at zero). Present its HP/life together.
        resulting_hp=changes[-1][1].normal_hit_points if changes else fact.resulting_normal_hp if fact is not None else None,
        resulting_life_state=life,
        feedback=(recipe.attackFeedback[_OUTCOMES[root.attack_outcome]]
                  if root.attack_outcome is not None else None), missing_media=(*body_missing, *missing),
        projectile=projectile, authored_clip=profile.actor.clip,
        release_ms=release if projectile is not None else None,
        weapon_trail=weapon_trail, weapon_pose=weapon_pose, show_contact=show_contact,
        contact_scale=1.2 if root.attack_outcome is AttackOutcome.CRIT else 1,
    )
    return BoundAttack(timeline, reduce_lineage(before, lineage), MappingProxyType(appearances),
                       frozenset(identity for identity, _ in changes) if timing is not None else frozenset())


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
    hp, life, flash = (target.hp, target.life_state, None) if isinstance(target, ActorContact) else (None, None, None)
    if timing is not None and t >= timing.hp_ms:
        hp = timeline.resulting_hp if timeline.resulting_hp is not None else hp
        life = timeline.resulting_life_state or life
    recipient = sample_damage_body(data, target, t,
        start_ms=timing.start_ms if started and timing is not None else None,
        end_ms=timing.end_ms if started and timing is not None else None,
        death_start_ms=timing.start_ms if started and timing is not None and life == LifeState.DEAD else None,
        resulting_life_state=life, life_start_ms=timing.hp_ms if timing is not None else None,
        life_body=timing.life_body if timing is not None else None) if isinstance(target, ActorContact) else None
    numbers: list[NumberSample] = []
    if timing is not None and damage is not None:
        if (damage.hitFlash.enabled and timing.flash_ms <= t < timing.flash_ms + damage.hitFlash.durationMs
                and t < timeline.complete_ms):
            flash = damage.hitFlash.color
        number = sample_damage_number(data, feedback_identity(target), damage, timeline.damage_total,
                                      timing.number_ms, t, timeline.complete_ms)
        if number is not None:
            numbers.append(number)
    if isinstance(target, ObjectContact) and damage is not None:
        number = sample_damage_number(data, target.object_uuid, damage, timeline.damage_total,
                                      timeline.contact_ms, t, timeline.complete_ms)
        if number is not None:
            numbers.append(number)
    feedback, style = timeline.feedback, data.badge_style
    if feedback is not None and timeline.contact_ms <= t < min(timeline.complete_ms, timeline.contact_ms + style.durationMs):
        progress = (t - timeline.contact_ms) / style.durationMs
        alpha = 1.0 if progress < style.fadeStartFraction else (1 - progress) / (1 - style.fadeStartFraction)
        numbers.append(NumberSample(feedback_identity(target), None, feedback.text, feedback.color,
                                    progress, alpha, kind="badge"))
    projectiles: tuple[GeometryProjectileSample, ...] = ()
    projectile = timeline.projectile
    if projectile is not None and projectile.start_ms <= t < projectile.end_ms:
        progress = (t - projectile.start_ms) / (projectile.end_ms - projectile.start_ms)
        effect = _bolt_sample(data, projectile.from_point, projectile.to_point, progress, projectile.recipe)
        projectiles = (project_attack_projectile(timeline,effect,0) if projectile.interception is not None else effect,)
    vitals = ((VitalsSample(target.actor_uuid, hp, life, flash),)
              if isinstance(target, ActorContact) and life is not None else ())
    return AttackSample((body, recipient) if recipient is not None else (body,), tuple(numbers),
                        vitals, t >= timeline.complete_ms, projectiles, t)
