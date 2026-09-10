"""Bind retained spell and equipment lineages to their authored executors."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from dnd.actions import AttackEvent, SpellEvent
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.core.events import DamageAppliedEvent, Event, LifeStateChangeEvent
from dnd.core.life_types import LifeState
from game.animation import (
    ActorContact, CastApplication, CastInput, CastTimeline, EquipmentTimeline, compile_cast, compile_equipment,
)
from game.animation_data import resolve_actor_layers
from game.animation_types import AnimationData, Facing8, RigLayer
from game.presentation import ActorState, CompletedLineage, PresentationTarget, reduce_lineage


@dataclass(frozen=True, slots=True)
class BoundCast:
    """One active historical input and its mechanically reduced successor."""

    timeline: CastTimeline
    after: PresentationTarget
    appearances: Mapping[str, tuple[RigLayer, ...]]


@dataclass(frozen=True, slots=True)
class BoundEquipment:
    """One visible loadout change; its other known actors stay in the scene."""

    timeline: EquipmentTimeline
    after: PresentationTarget
    contacts: Mapping[str, ActorContact]
    appearances: Mapping[str, tuple[RigLayer, ...]]
    replacement: tuple[RigLayer, ...]


def actor_contact(target: PresentationTarget, actor: ActorState, data: AnimationData, facing: Facing8 = "S") -> ActorContact:
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
    target: PresentationTarget,
    lineage: CompletedLineage,
    data: AnimationData,
    *, travel_apex_steps: float = 0.0,
    contacts: Mapping[str, ActorContact] | None = None,
) -> BoundCast:
    """Use the historical pre-head state and actual child results, without IO."""
    root = lineage.root
    if not isinstance(root, SpellEvent):
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
        (event for event in lineage.events if isinstance(event, SpellEvent)
         and event.parent_lineage == root.lineage_uuid and event.application_index is not None),
        key=lambda event: event.application_index or 0,
    )
    if application_roots:
        if ([event.application_index for event in application_roots] != list(range(len(application_roots)))
                or [event.target_entity_uuid for event in application_roots] != root.declared_target_entity_uuids):
            raise ValueError("cast application identities disagree with its declared allocation")
    else:
        application_roots = [root]
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    actor_contacts = {caster.uuid: source_contact}
    applications: list[CastApplication] = []
    for application in application_roots:
        recipient = target.actors.get(application.target_entity_uuid) if application.target_entity_uuid else None
        if recipient is None:
            raise ValueError("cast binding requires each retained target actor")
        actor_contacts.setdefault(recipient.uuid, overrides.get(str(recipient.uuid), actor_contact(target, recipient, data)))
        descendants: list[Event] = []
        pending = list(application.children_lineages)
        while pending:
            child = by_lineage[pending.pop()]
            if isinstance(child, (AttackEvent, SpellEvent)):
                # A nested action owns its own delivery/effect subtree. The
                # shared compositor binds it at this application's anchor.
                continue
            descendants.append(child)
            pending.extend(child.children_lineages)
        applied = [event for event in descendants if isinstance(event, DamageAppliedEvent)]
        if not applied:
            damage = None
        elif len(applied) == 1 and applied[0].target_entity_uuid == recipient.uuid:
            damage = applied[0]
        else:
            raise NotImplementedError("selected cast binding requires one positive packet per application or an actual miss")
        changes = [event for event in descendants
                   if isinstance(event, LifeStateChangeEvent) and event.entity_uuid == recipient.uuid]
        if len(changes) > 1:
            raise NotImplementedError("selected cast binding requires one final life transition per application")
        applications.append(CastApplication(
            application_id=str(application.application_id) if application.application_id is not None else None,
            target=actor_contacts[recipient.uuid],
            damage_applied=damage is not None,
            damage_total=damage.applied_damage if damage is not None else None,
            resulting_hp=damage.resulting_normal_hp if damage is not None else None,
            resulting_life_state=changes[0].new_state if changes else None,
            damage_type=damage.damage_type.value if damage is not None else None,
            travel_apex_steps=travel_apex_steps,
        ))
    source = CastInput(root_event_uuid=str(root.uuid), caster=source_contact, applications=tuple(applications))
    timeline = compile_cast(data, root.behavior_id, source)
    appearances = {
        contact.actor_uuid: resolve_actor_layers(
            data, target.actors[actor_uuid].appearance, target.actors[actor_uuid].items,
            target.actors[actor_uuid].equipment, target.actors[actor_uuid].active_weapon_set,
            rig_id=contact.rig_id,
        )
        for actor_uuid, contact in actor_contacts.items()
    }
    return BoundCast(timeline, reduce_lineage(target, lineage), MappingProxyType(appearances))


def bind_equipment(
    target: PresentationTarget,
    lineage: CompletedLineage,
    data: AnimationData,
    facings: Mapping[str, Facing8],
) -> BoundEquipment | None:
    """Animate an actual visible item replacement, retaining its old layers.

    The original frame machinery staged a loadout patch alongside one gesture.
    Here the committed fact that changes visible layers owns that gesture;
    the other independent equipment roots still reduce without animation.
    """
    root = lineage.root
    if not isinstance(root, ItemLocationStateEvent) or root.owner_uuid is None:
        raise ValueError("equipment binding requires an owned item-location root")
    after = reduce_lineage(target, lineage)
    actor = target.actors[root.owner_uuid]
    contact = actor_contact(target, actor, data, facings.get(str(actor.uuid), "S"))
    previous = resolve_actor_layers(
        data, actor.appearance, actor.items, actor.equipment,
        actor.active_weapon_set, rig_id=contact.rig_id,
    )
    successor = after.actors[actor.uuid]
    replacement = resolve_actor_layers(
        data, successor.appearance, successor.items, successor.equipment,
        successor.active_weapon_set, rig_id=contact.rig_id,
    )
    if replacement == previous:
        return None
    if successor.active_weapon_set != actor.active_weapon_set:
        raise NotImplementedError("this binding consumes item replacement within the same active set")
    contacts = {
        str(row.uuid): actor_contact(target, row, data, facings.get(str(row.uuid), "S"))
        for row in target.actors.values()
    }
    appearances = {
        str(row.uuid): resolve_actor_layers(
            data, row.appearance, row.items, row.equipment,
            row.active_weapon_set, rig_id=contacts[str(row.uuid)].rig_id,
        )
        for row in target.actors.values()
    }
    return BoundEquipment(
        compile_equipment(data, str(root.uuid), contact), after,
        MappingProxyType(contacts), MappingProxyType(appearances), replacement,
    )
