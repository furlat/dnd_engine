"""Pre-contact body cues from actual condition-owned interceptions."""

from dataclasses import dataclass, replace
from typing import Mapping, cast
from uuid import UUID

from dnd.core.events import EventType
from game.animation import ActorContact, body_elevation_steps, facing_for_delta
from game.animation_types import AnimationData, Facing8, StudioMediaTrack
from game.attack import BoundAttack
from game.body_action import BodyActionCue, bind_body_action
from game.combat import BoundCast, actor_contact, actor_is_visible
from game.player_facts import AttackFact, ConditionChangeFact, DamageFact, PlayerLineage, PlayerState, SpellFact
from game.stationary_media import StationaryMediaCue


@dataclass(frozen=True, slots=True)
class _Interception:
    event_uuid: UUID
    owner_uuid: UUID
    target_uuid: UUID
    contact_ms: float


def _interceptions(lineage: PlayerLineage, bound: BoundAttack | BoundCast) -> tuple[_Interception, ...]:
    root = lineage.root.fact
    if isinstance(root, AttackFact) and isinstance(bound, BoundAttack):
        return ((_Interception(lineage.root.uuid, root.intercepted_by_condition_uuid,
                               root.target_entity_uuid, bound.timeline.contact_ms),)
                if root.intercepted_by_condition_uuid is not None else ())
    result = []
    if isinstance(root, SpellFact) and isinstance(bound, BoundCast):
        nodes = {node.lineage_uuid: node for node in lineage.events}
        for node in lineage.events:
            fact = node.fact
            if not isinstance(fact, DamageFact) or fact.intercepted_by_condition_uuid is None:
                continue
            parent = node
            application_id = None
            while parent.parent_lineage is not None and parent.parent_lineage in nodes:
                parent = nodes[parent.parent_lineage]
                if isinstance(parent.fact, SpellFact) and parent.fact.application_id is not None:
                    application_id = str(parent.fact.application_id)
                    break
            delivery = next((row for row in bound.timeline.applications
                if row.source.target.actor_uuid == str(fact.target_entity_uuid)
                and (application_id is None or row.source.application_id == application_id)), None)
            if delivery is not None:
                result.append(_Interception(node.uuid, fact.intercepted_by_condition_uuid,
                                             fact.target_entity_uuid, delivery.travel_end_ms))
    return tuple(result)


def bind_condition_reaction_bodies(
    before: PlayerState, lineage: PlayerLineage, bound: BoundAttack | BoundCast,
    data: AnimationData, *, start_ms: float, facings: Mapping[str, Facing8],
    contacts: Mapping[str, ActorContact],
) -> tuple[float, tuple[BodyActionCue, ...]]:
    """Fit a real intercepted condition's authored release before incoming contact.

    The parent's existing timeline stays intact. Only an otherwise negative
    reaction start delays its entry; both body tracks then run at authored speed.
    Maintained shield contacts have no new application and replay no gesture.
    """
    root = lineage.root.fact
    if not isinstance(root, (AttackFact, SpellFact)):
        return 0., ()
    contacts_by_owner: dict[UUID, float] = {}
    for contact in _interceptions(lineage, bound):
        contacts_by_owner.setdefault(contact.owner_uuid, contact.contact_ms)
    entries = []
    delay = 0.
    for node in lineage.events:
        fact = node.fact
        if (node.canceled or not isinstance(fact, ConditionChangeFact)
                or fact.event_type is not EventType.CONDITION_APPLICATION):
            continue
        contact_ms = contacts_by_owner.get(fact.condition.condition_uuid)
        if contact_ms is None:
            continue
        cue = bind_body_action(before, node, data, start_ms=0., facings=facings,
                               contacts=contacts, reaction_source_uuid=root.source_entity_uuid)
        if cue is None:
            continue
        draft = data.drafts[cue.recipe_id]
        reveal_lead = draft.contact.delayMs if draft.contact is not None else 0.
        lead = cue.effect_ms + reveal_lead
        delay = max(delay, lead - contact_ms)
        entries.append((cue, contact_ms, lead))
    result = []
    for cue, contact_ms, lead in entries:
        offset = start_ms + delay + contact_ms - lead
        result.append(replace(cue, start_ms=offset, effect_ms=cue.effect_ms + offset,
            body_end_ms=cue.body_end_ms + offset, join_ms=cue.join_ms + offset,
            complete_ms=cue.complete_ms + offset))
    return delay, tuple(result)


def bind_condition_interception_media(
    before: PlayerState, lineage: PlayerLineage, bound: BoundAttack | BoundCast,
    data: AnimationData, *, start_ms: float, contacts: Mapping[str, ActorContact],
) -> tuple[StationaryMediaCue, ...]:
    """Separate actual incoming bearing from the authored camera atlas basis."""
    root = lineage.root.fact
    if not isinstance(root, (AttackFact, SpellFact)):
        return ()
    source = before.actors.get(root.source_entity_uuid)
    if source is None or not (str(source.uuid) in contacts or actor_is_visible(before, source)):
        return ()
    origin = contacts.get(str(source.uuid)) or actor_contact(before, source, data)
    members = {member.condition_uuid: member for actor in before.actors.values() for member in actor.conditions}
    members.update({node.fact.condition.condition_uuid: node.fact.condition for node in lineage.events
                    if isinstance(node.fact, ConditionChangeFact)
                    and node.fact.event_type is EventType.CONDITION_APPLICATION and not node.canceled})
    result = []
    for interception in _interceptions(lineage, bound):
        member = members.get(interception.owner_uuid)
        recipe = data.condition_recipes.get(member.behavior_id or "") if member is not None else None
        target = before.actors.get(interception.target_uuid)
        if (recipe is None or target is None
                or not (str(target.uuid) in contacts or actor_is_visible(before, target))):
            continue
        target_contact = contacts.get(str(target.uuid)) or actor_contact(before, target, data)
        delta = target_contact.grid[0] - origin.grid[0], target_contact.grid[1] - origin.grid[1]
        if delta == (0,0):
            continue
        direction = facing_for_delta(delta, data)
        for effect in recipe.interceptionEffectsByDirection.get(direction, ()):
            media = data.condition_media[effect.assetId]
            if media.asset_id is None:
                raise ValueError("condition interception requires registered media")
            if effect.attachment != "body" or effect.offsetX or effect.offsetY:
                raise ValueError("condition interception uses registered body-ground origin")
            track = StudioMediaTrack(id=effect.id,assetId=media.asset_id,attachment="target_body",
                durationMs=effect.durationMs,scale=media.scale * target_contact.visual_scale,
                alpha=effect.opacity,depth="behind_body" if effect.drawOrder=="behind_body" else "front_body",
                viewFacing=cast(Facing8,media.world_basis) if media.world_basis is not None else None)
            result.append(StationaryMediaCue(interception.event_uuid,track,target_contact.grid,
                body_elevation_steps(target_contact,data),direction,
                start_ms+interception.contact_ms+effect.startOffsetMs,data))
    return tuple(result)
