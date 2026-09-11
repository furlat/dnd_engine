"""Sample one retained damage packet at its caller-owned contact and time."""

from dataclasses import dataclass, replace
from math import isfinite
from uuid import UUID

from dnd.actions import AttackEvent, SpellEvent
from dnd.core.events import DamageAppliedEvent, Event, LifeStateChangeEvent, TakeDamageEvent
from dnd.core.life_types import LifeState
from game.animation import (
    ActorContact, BodySample, DamageTiming, VitalsSample, compile_damage,
    resolve_damage, sample_damage_body,
)
from game.animation_types import AnimationData, StudioDamage
from game.combat import actor_contact
from game.presentation import CompletedLineage, PresentationTarget


@dataclass(frozen=True, slots=True)
class DamageCue:
    event_uuid: UUID
    contact: ActorContact
    timing: DamageTiming
    damage: StudioDamage
    applied_damage: int
    resulting_hp: int
    resulting_life_state: LifeState
    owned_life_events: frozenset[UUID]
    data: AnimationData


@dataclass(frozen=True, slots=True)
class DamageSample:
    body: BodySample | None
    vitals: VitalsSample | None
    complete: bool


def bind_damage(before: PresentationTarget, lineage: CompletedLineage, data: AnimationData,
                *, start_ms: float, contact: ActorContact | None = None) -> DamageCue | None:
    """Own one direct applied packet and its life commit, excluding nested hits."""
    root = lineage.root
    if not isinstance(root, TakeDamageEvent):
        raise ValueError("damage binding requires a retained TakeDamageEvent root")
    if not isfinite(start_ms) or start_ms < 0:
        raise ValueError("damage start requires finite nonnegative time")
    if root.canceled or root.target_entity_uuid is None or root.target_entity_uuid not in before.actors:
        return None
    actor = before.actors[root.target_entity_uuid]
    packets = [event for event in lineage.events if isinstance(event, DamageAppliedEvent)
               and not event.canceled and event.parent_lineage == root.lineage_uuid]
    if len(packets) != 1 or packets[0].target_entity_uuid != actor.uuid:
        return None
    by_lineage = {event.lineage_uuid: event for event in lineage.events}

    def owned_effect(event: Event) -> bool:
        parent = event.parent_lineage
        while parent is not None and parent != root.lineage_uuid:
            ancestor = by_lineage[parent]
            if isinstance(ancestor, (AttackEvent, SpellEvent, TakeDamageEvent)):
                return False
            parent = ancestor.parent_lineage
        return parent == root.lineage_uuid

    changes = [event for event in lineage.events if isinstance(event, LifeStateChangeEvent)
               and not event.canceled and event.entity_uuid == actor.uuid and owned_effect(event)]
    if len(changes) > 1:
        return None
    target = actor_contact(before, actor, data) if contact is None else contact
    if target.actor_uuid != str(actor.uuid):
        raise ValueError("damage contact belongs to a different recipient")
    target = replace(target, hp=actor.normal_hp, life_state=actor.life_state)
    packet = packets[0]
    life = changes[0].new_state if changes else actor.life_state
    # Entering DYING can normalize the packet's intermediate negative HP.
    hp = changes[0].normal_hit_points if changes else packet.resulting_normal_hp
    damage = resolve_damage(data, packet.damage_type.value)
    timing = compile_damage(data, target, damage, start_ms, life)
    return DamageCue(root.uuid, target, timing, damage, packet.applied_damage, hp, life,
                     frozenset(event.uuid for event in changes), data)


def sample_damage(cue: DamageCue, elapsed_ms: float) -> DamageSample:
    """Seek absolute authored hit/death time without applying another packet."""
    if not isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("damage sampling requires finite nonnegative time")
    timing = cue.timing
    if elapsed_ms < timing.start_ms:
        return DamageSample(None, None, False)
    committed = elapsed_ms >= timing.hp_ms
    hp = cue.resulting_hp if committed else cue.contact.hp
    life = cue.resulting_life_state if committed else cue.contact.life_state
    complete = elapsed_ms >= timing.end_ms
    body = None
    if not complete or life is LifeState.DEAD:
        body = sample_damage_body(cue.data, cue.contact, elapsed_ms,
            start_ms=timing.start_ms, end_ms=timing.end_ms,
            death_start_ms=timing.start_ms if life is LifeState.DEAD else None)
    flash = cue.damage.hitFlash
    color = (flash.color if flash.enabled and not complete
             and timing.flash_ms <= elapsed_ms < timing.flash_ms + flash.durationMs else None)
    return DamageSample(body, VitalsSample(cue.contact.actor_uuid, hp, life, color), complete)
