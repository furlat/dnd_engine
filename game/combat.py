"""Bind retained spell and equipment lineages to their authored executors."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping
from math import atan2, floor, pi
from uuid import UUID

from dnd.core.equipment_types import WeaponSet
from dnd.core.life_types import LifeState
from dnd.core.dice import AttackOutcome
from dnd.core.presentation_geometry import ConePresentationGeometry, LinePresentationGeometry, CubePresentationGeometry, SpherePresentationGeometry
from dnd.types.world import WorldEdgeChannel
from dnd.types.world_placement import WorldObjectPlacement
from game.animation import (
    ActorContact, CastApplication, CastInput, CastTimeline, EquipmentTimeline, GroundContact, compile_cast, compile_equipment,
)
from game.animation_data import resolve_player_layers
from game.animation_types import AnimationData, Facing8, RigLayer
from game.player_facts import (
    ActionFact, AttackFact, ConditionChangeFact, DamageFact, EquipmentFact, LifeFact, PlayerActor, PlayerLineage, PlayerNode, PlayerState, SpellFact,
)
from game.player_reduction import reduce_lineage
from game.device_art import DeviceEmission, device_bank
from game.condition_animation import resolve_condition_appearance
from game.animation_rates import action_playback_rate
from game.area_media import AreaSolid
from dnd.core.events import EventType, WorldTileState


@dataclass(frozen=True, slots=True)
class BoundCast:
    """One active historical input and its mechanically reduced successor."""

    timeline: CastTimeline
    after: PlayerState
    appearances: Mapping[str, tuple[RigLayer, ...]]
    owned_life_events: frozenset[UUID] = frozenset()
    area_boundaries: tuple[WorldObjectPlacement, ...] = ()
    area_solids: tuple[AreaSolid, ...] = ()
    area_supports: tuple[WorldTileState, ...] = ()


@dataclass(frozen=True, slots=True)
class BoundEquipment:
    """One visible loadout change; its other known actors stay in the scene."""

    timeline: EquipmentTimeline
    after: PlayerState
    contacts: Mapping[str, ActorContact]
    appearances: Mapping[str, tuple[RigLayer, ...]]
    replacement: tuple[RigLayer, ...]


def actor_is_visible(target: PlayerState, actor: PlayerActor) -> bool:
    """Whether retained observation currently supplies this actor's visual pose."""
    if target.senses is None:
        return False
    perceived = target.senses.entities.get(actor.uuid)
    return (actor.uuid == target.observer_uuid or perceived is not None and perceived.visual
            or actor.life_state is LifeState.DEAD and actor.last_visual_position is not None)


def actor_contact(target: PlayerState, actor: PlayerActor, data: AnimationData, facing: Facing8 = "S") -> ActorContact:
    if target.senses is None:
        raise ValueError("actor binding requires retained observer contacts")
    if actor.uuid == target.observer_uuid:
        position = target.senses.position
    else:
        perceived = target.senses.entities.get(actor.uuid)
        if perceived is not None and perceived.visual:
            position = perceived.position
        elif actor.life_state == LifeState.DEAD and actor.last_visual_position is not None:
            position = actor.last_visual_position
        else:
            raise ValueError("selected actor binding requires a retained visual contact")
    support = target.tiles.get(position)
    if support is None:
        raise ValueError("actor contact requires its retained world support")
    if actor.creature_content_ref is None:
        rig_id = data.root_rig
    elif actor.creature_content_ref in data.creature_rigs:
        rig_id = data.creature_rigs[actor.creature_content_ref]
    else:
        raise NotImplementedError(f"no selected rig binding for {actor.creature_content_ref}")
    condition = resolve_condition_appearance(actor.conditions, data.condition_recipes)
    return ActorContact(
        actor_uuid=str(actor.uuid),
        grid=position,
        facing=facing,
        visual_scale=actor.appearance.visual_scale * condition.scale,
        condition_scale=condition.scale,
        visual_scale_x=actor.appearance.visual_scale_x,
        hp=actor.normal_hp,
        life_state=actor.life_state,
        elevation_steps=support.elevation_steps,
        rig_id=rig_id,
        rest_pose=condition.body_pose,
    )


def bind_cast(
    target: PlayerState,
    lineage: PlayerLineage,
    data: AnimationData,
    *, travel_apex_steps: float = 0.0,
    contacts: Mapping[str, ActorContact] | None = None,
    facings: Mapping[str, Facing8] | None = None,
) -> BoundCast:
    """Use the historical pre-head state and actual child results, without IO."""
    root_node = lineage.root
    root = root_node.fact
    if not isinstance(root, (SpellFact, ActionFact)):
        raise NotImplementedError("authored delivery requires a spell or registered action root")
    spell = root if isinstance(root, SpellFact) else None
    caster = target.actors.get(root.source_entity_uuid)
    if caster is None:
        raise ValueError("cast binding requires the retained source actor")
    source_contact = actor_contact(target, caster, data, (facings or {}).get(str(caster.uuid), "S"))
    if spell is not None and spell.source_position is not None and spell.source_position != source_contact.grid:
        raise ValueError("spell declaration and retained caster contact disagree")
    overrides = contacts or {}
    source_contact = overrides.get(str(caster.uuid), source_contact)
    # Authored semantic identity is captured by the action before admission.
    # Names and log text do not choose recipes or infer damage.
    if root.behavior_id is None:
        raise ValueError("cast lacks its authored semantic identity")
    area = spell is not None and spell.area_geometry is not None
    ground_target = None
    area_direction = None
    if area:
        assert spell is not None
        if spell.aoe_position is None or spell.aoe_position not in target.tiles:
            raise ValueError("area delivery requires an observed destination and support")
        ground_target = GroundContact(spell.aoe_position, target.tiles[spell.aoe_position].elevation_steps)
        geometry = spell.area_geometry
        if isinstance(geometry, (ConePresentationGeometry, LinePresentationGeometry, CubePresentationGeometry)):
            area_direction = geometry.direction
            if isinstance(geometry, CubePresentationGeometry) and not geometry.centered and area_direction is not None:
                dx, dy = area_direction
                area_direction = ((1 if dx >= 0 else -1, 0) if abs(dx) >= abs(dy)
                                  else (0, 1 if dy >= 0 else -1))
            ground_target = GroundContact(geometry.origin, target.tiles[geometry.origin].elevation_steps)
    spell_applications = sorted(
        ((event, event.fact) for event in lineage.events if isinstance(event.fact, SpellFact)
         and event.parent_lineage == root_node.lineage_uuid and event.fact.application_index is not None),
        key=lambda row: row[1].application_index or 0,
    )
    if spell_applications and not area:
        assert spell is not None
        if ([fact.application_index for _, fact in spell_applications] != list(range(len(spell_applications)))
                or [fact.target_entity_uuid for _, fact in spell_applications] != list(spell.declared_target_entity_uuids)):
            raise ValueError("cast application identities disagree with its declared allocation")
    application_roots: list[tuple[PlayerNode, SpellFact | ActionFact]] = list(spell_applications)
    if not application_roots and not area and root.target_entity_uuid is not None and not root_node.canceled:
        application_roots = [(root_node, root)]
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    actor_contacts = {caster.uuid: source_contact}
    applications: list[CastApplication] = []
    owned_life_events: set[UUID] = set()
    for application_node, application in application_roots:
        recipient = target.actors.get(application.target_entity_uuid) if application.target_entity_uuid else None
        if area and (recipient is None or not actor_is_visible(target, recipient)):
            continue
        if recipient is None:
            raise ValueError("cast binding requires each retained target actor")
        actor_contacts.setdefault(recipient.uuid, overrides.get(str(recipient.uuid), actor_contact(
            target, recipient, data, (facings or {}).get(str(recipient.uuid), "S"))))
        descendants: list[PlayerNode] = []
        pending = list(application_node.children_lineages)
        while pending:
            child = by_lineage[pending.pop()]
            if (isinstance(child.fact, (AttackFact, SpellFact))
                    or isinstance(child.fact, ActionFact) and child.fact.behavior_id in data.drafts):
                # A nested action owns its own delivery/effect subtree. The
                # shared compositor binds it at this application's anchor.
                continue
            descendants.append(child)
            pending.extend(child.children_lineages)
        applied = [event.fact for event in descendants
                   if isinstance(event.fact, DamageFact) and event.fact.stage == "applied"]
        if not applied:
            damage = None
        elif len(applied) == 1 and applied[0].target_entity_uuid == recipient.uuid:
            damage = applied[0]
        else:
            raise NotImplementedError("selected cast binding requires one positive packet per application or an actual miss")
        descendants_ids = {event.uuid for event in descendants}
        changes = [(event.uuid, event.fact) for event in lineage.events
                   if event.uuid in descendants_ids and not event.canceled
                   and isinstance(event.fact, LifeFact) and event.fact.entity_uuid == recipient.uuid]
        if damage is not None:
            owned_life_events.update(identity for identity, _ in changes)
        applications.append(CastApplication(
            application_id=(str(application.application_id)
                if isinstance(application, SpellFact) and application.application_id is not None else None),
            target=actor_contacts[recipient.uuid],
            damage_applied=damage is not None,
            damage_total=damage.applied_damage if damage is not None else None,
            resulting_hp=(changes[-1][1].normal_hit_points if changes else
                          damage.resulting_normal_hp if damage is not None else None),
            resulting_life_state=changes[-1][1].new_state if changes else None,
            damage_type=damage.damage_type.value if damage is not None and damage.damage_type is not None else None,
            travel_apex_steps=travel_apex_steps,
            hit=(application.attack_outcome in (AttackOutcome.HIT, AttackOutcome.CRIT)
                 if isinstance(application, SpellFact) and application.attack_outcome is not None else None),
            removed_condition_tags=frozenset(tag for event in descendants if not event.canceled
                and isinstance(event.fact, ConditionChangeFact)
                and event.fact.target_entity_uuid == recipient.uuid
                and event.fact.event_type is EventType.CONDITION_REMOVAL
                and event.fact.condition.state is not None for tag in event.fact.condition.state.tags),
        ))
    if root_node.canceled and not application_roots and not area:
        # The declaration is real attempted allocation, even when no application
        # executed. These IDs name presentation tracks, never fabricated events.
        declared = (spell.declared_target_entity_uuids if spell is not None else ())
        if not declared and root.target_entity_uuid is not None:
            declared = (root.target_entity_uuid,)
        for index, identity in enumerate(declared):
            recipient = target.actors.get(identity)
            if recipient is None:
                raise ValueError("attempt binding requires each disclosed selected target")
            actor_contacts.setdefault(identity, overrides.get(str(identity), actor_contact(
                target, recipient, data, (facings or {}).get(str(identity), "S"))))
            applications.append(CastApplication(application_id=f"{root_node.uuid}:attempt:{index}",
                target=actor_contacts[identity], damage_applied=False, damage_total=None,
                resulting_hp=None, travel_apex_steps=travel_apex_steps))
    emitter = None
    if spell is not None and spell.cast_origin == "source_item":
        device = target.objects.get(root.source_item_uuid) if root.source_item_uuid is not None else None
        if device is None:
            raise ValueError("device cast requires its disclosed historical placement")
        art = data.devices.get(device.item.item_id)
        if art is None:
            raise NotImplementedError("device cast has no authored body binding")
        dx = device.placement.position[0] - source_contact.grid[0]
        dy = device.placement.position[1] - source_contact.grid[1]
        facing = art.rows[floor(atan2(dy, dx) / (pi / 4) + .5) % 8]
        emitter = DeviceEmission(str(root.source_item_uuid), device.placement.position,
            device.placement.base_height_steps, facing, art, device_bank(art))
    source = CastInput(root_event_uuid=str(root_node.uuid), caster=source_contact,
                       applications=tuple(applications), ground_target=ground_target, emitter=emitter,
                       area_direction=area_direction,
                       area_propagation=spell.area_propagation if spell is not None else "line_of_effect",
                       area_radius_feet=(spell.area_geometry.radius_feet
                           if spell is not None and isinstance(spell.area_geometry, SpherePresentationGeometry) else 0),
                       protections=tuple((identity, target.senses.spatial_effects[identity])
                           for identity in dict.fromkeys(suppression.provider_uuid
                               for fact in (spell, *(fact for _, fact in spell_applications)) if fact is not None
                               for suppression in fact.suppressions)
                           if target.senses is not None and identity in target.senses.spatial_effects))
    timeline = compile_cast(data, (spell.effect_id if spell is not None else None) or root.behavior_id,
                            source, body_rate=action_playback_rate(data, caster))
    appearances = {
        contact.actor_uuid: resolve_player_layers(data, target.actors[actor_uuid], rig_id=contact.rig_id)
        for actor_uuid, contact in actor_contacts.items()
    }
    boundaries = tuple(obj.placement for obj in target.objects.values()
        if area and obj.item.boundary_structure is not None
        and WorldEdgeChannel.PROPAGATION in obj.item.boundary_structure.blocked_channels)
    solids = tuple(AreaSolid(position, obj.placement.base_height_steps, obj.placement.top_height_steps)
        for obj in target.objects.values() if area and obj.item.boundary_structure is None
        and obj.item.blocks_propagation for position in obj.placement.positions) + tuple(
        AreaSolid(tile.position, tile.elevation_steps) for tile in target.tiles.values()
        if area and tile.blocks_propagation)
    return BoundCast(timeline, reduce_lineage(target, lineage), MappingProxyType(appearances),
                     frozenset(owned_life_events), boundaries, solids, tuple(target.tiles.values()) if area else ())


def bind_equipment(
    target: PlayerState,
    lineage: PlayerLineage,
    data: AnimationData,
    facings: Mapping[str, Facing8],
    *, contacts: Mapping[str, ActorContact] | None = None,
) -> BoundEquipment | None:
    """Bind visible stance or item changes to the original equipment gesture.

    Equipment completions supply the accepted stance; item-location facts
    supply membership. A fact that leaves visible layers unchanged adds no
    gesture. Sampling commits stance at the authored frame and items at the end.
    """
    root_node = lineage.root
    root = root_node.fact
    if not isinstance(root, EquipmentFact):
        raise ValueError("equipment binding requires a disclosed equipment fact")
    # The existing mapper emits no stance gesture for NONE.
    if root.visual_loadout.active_weapon_set is WeaponSet.NONE:
        return None
    owner = root.source_entity_uuid
    after = reduce_lineage(target, lineage)
    actor = target.actors[owner]
    contact = actor_contact(target, actor, data, facings.get(str(actor.uuid), "S"))
    placed = (contacts or {}).get(contact.actor_uuid)
    if placed is not None:
        contact = replace(contact, grid=placed.grid, elevation_steps=placed.elevation_steps,
                          body_lift_px=placed.body_lift_px, facing=placed.facing)
    previous = resolve_player_layers(data, actor, rig_id=contact.rig_id)
    successor = after.actors[actor.uuid]
    replacement = resolve_player_layers(data, successor, rig_id=contact.rig_id)
    if replacement == previous:
        return None
    actor_contacts = dict(contacts) if contacts is not None else {
        str(row.uuid): actor_contact(target, row, data, facings.get(str(row.uuid), "S"))
        for row in target.actors.values() if actor_is_visible(target, row)
    }
    actor_contacts[contact.actor_uuid] = contact
    appearances = {
        str(row.uuid): resolve_player_layers(data, row, rig_id=actor_contacts[str(row.uuid)].rig_id)
        for row in target.actors.values() if str(row.uuid) in actor_contacts
    }
    return BoundEquipment(
        compile_equipment(data, str(root_node.uuid), contact), after,
        MappingProxyType(actor_contacts), MappingProxyType(appearances), replacement,
    )
