"""Bind retained spell and equipment lineages to their authored executors."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from dnd.core.equipment_types import WeaponSet
from dnd.core.life_types import LifeState
from game.animation import (
    ActorContact, CastApplication, CastInput, CastTimeline, EquipmentTimeline, compile_cast, compile_equipment,
)
from game.animation_data import resolve_player_layers
from game.animation_types import AnimationData, Facing8, RigLayer
from game.player_facts import (
    AttackFact, DamageFact, EquipmentFact, LifeFact, PlayerActor, PlayerLineage, PlayerNode, PlayerState, SpellFact,
)
from game.player_projection import reduce_lineage


@dataclass(frozen=True, slots=True)
class BoundCast:
    """One active historical input and its mechanically reduced successor."""

    timeline: CastTimeline
    after: PlayerState
    appearances: Mapping[str, tuple[RigLayer, ...]]
    owned_life_events: frozenset[UUID] = frozenset()


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
    return ActorContact(
        actor_uuid=str(actor.uuid),
        grid=position,
        facing=facing,
        visual_scale=actor.appearance.visual_scale,
        visual_scale_x=actor.appearance.visual_scale_x,
        hp=actor.normal_hp,
        life_state=actor.life_state,
        elevation_steps=support.elevation_steps,
        rig_id=rig_id,
    )


def bind_cast(
    target: PlayerState,
    lineage: PlayerLineage,
    data: AnimationData,
    *, travel_apex_steps: float = 0.0,
    contacts: Mapping[str, ActorContact] | None = None,
) -> BoundCast:
    """Use the historical pre-head state and actual child results, without IO."""
    root_node = lineage.root
    root = root_node.fact
    if not isinstance(root, SpellFact):
        raise NotImplementedError("selected authored binding requires a spell root")
    caster = target.actors.get(root.source_entity_uuid)
    if caster is None:
        raise ValueError("cast binding requires the retained source actor")
    source_contact = actor_contact(target, caster, data)
    if root.source_position != source_contact.grid:
        raise ValueError("spell declaration and retained caster contact disagree")
    overrides = contacts or {}
    source_contact = overrides.get(str(caster.uuid), source_contact)
    # Authored semantic identity is captured by the action before admission.
    # Names and log text do not choose recipes or infer damage.
    if root.behavior_id is None:
        raise ValueError("cast lacks its authored semantic identity")
    application_roots = sorted(
        ((event, event.fact) for event in lineage.events if isinstance(event.fact, SpellFact)
         and event.parent_lineage == root_node.lineage_uuid and event.fact.application_index is not None),
        key=lambda row: row[1].application_index or 0,
    )
    if application_roots:
        if ([fact.application_index for _, fact in application_roots] != list(range(len(application_roots)))
                or [fact.target_entity_uuid for _, fact in application_roots] != list(root.declared_target_entity_uuids)):
            raise ValueError("cast application identities disagree with its declared allocation")
    else:
        application_roots = [(root_node, root)]
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    actor_contacts = {caster.uuid: source_contact}
    applications: list[CastApplication] = []
    owned_life_events: set[UUID] = set()
    for application_node, application in application_roots:
        recipient = target.actors.get(application.target_entity_uuid) if application.target_entity_uuid else None
        if recipient is None:
            raise ValueError("cast binding requires each retained target actor")
        actor_contacts.setdefault(recipient.uuid, overrides.get(str(recipient.uuid), actor_contact(target, recipient, data)))
        descendants: list[PlayerNode] = []
        pending = list(application_node.children_lineages)
        while pending:
            child = by_lineage[pending.pop()]
            if isinstance(child.fact, (AttackFact, SpellFact)):
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
        changes = [(event.uuid, event.fact) for event in descendants
                   if isinstance(event.fact, LifeFact) and event.fact.entity_uuid == recipient.uuid]
        if len(changes) > 1:
            raise NotImplementedError("selected cast binding requires one final life transition per application")
        if damage is not None:
            owned_life_events.update(identity for identity, fact in changes if fact.new_state is LifeState.DEAD)
        applications.append(CastApplication(
            application_id=str(application.application_id) if application.application_id is not None else None,
            target=actor_contacts[recipient.uuid],
            damage_applied=damage is not None,
            damage_total=damage.applied_damage if damage is not None else None,
            resulting_hp=damage.resulting_normal_hp if damage is not None else None,
            resulting_life_state=changes[0][1].new_state if changes else None,
            damage_type=damage.damage_type.value if damage is not None and damage.damage_type is not None else None,
            travel_apex_steps=travel_apex_steps,
        ))
    source = CastInput(root_event_uuid=str(root_node.uuid), caster=source_contact, applications=tuple(applications))
    timeline = compile_cast(data, root.behavior_id, source)
    appearances = {
        contact.actor_uuid: resolve_player_layers(data, target.actors[actor_uuid], rig_id=contact.rig_id)
        for actor_uuid, contact in actor_contacts.items()
    }
    return BoundCast(timeline, reduce_lineage(target, lineage), MappingProxyType(appearances), frozenset(owned_life_events))


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
