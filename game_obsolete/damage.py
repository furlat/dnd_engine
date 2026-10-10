"""Sample one retained damage packet at its caller-owned contact and time."""

from dataclasses import dataclass, replace
from math import isfinite
from uuid import UUID

from dnd.core.life_types import LifeState
from game.animation import (
    ActorContact, BodySample, DamageTiming, VitalsSample, compile_damage,
    resolve_damage, sample_damage_body,
)
from game.animation_types import AnimationData, StudioDamage
from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference
from game.combat import actor_contact
from dnd.player.reduction import PlayerCausalIndex, index_player_lineage
from dnd.player.facts import DamageRequestFact, DamageResultFact, LifeFact, PlayerLineage, PlayerNode, PlayerState


@dataclass(frozen=True, slots=True)
class DamageCue:
    event_uuid: UUID
    contact: ActorContact
    timing: DamageTiming
    damage: StudioDamage
    results: tuple[PlayerNode, ...]
    applied_damage: int
    resulting_hp: int
    resulting_life_state: LifeState
    owned_life_events: frozenset[UUID]
    data: AnimationData
    timing_evidence: tuple[TimingEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class DamageSample:
    body: BodySample | None
    vitals: VitalsSample | None
    complete: bool


def bind_damage(before: PlayerState, lineage: PlayerLineage, data: AnimationData,
                *, start_ms: float, contact: ActorContact | None = None,
                causal_index: PlayerCausalIndex | None = None) -> DamageCue | None:
    """Own one direct applied packet and its life commit, excluding nested hits."""
    root_node = lineage.root
    root = root_node.fact
    if not isinstance(root, DamageRequestFact):
        raise ValueError("damage binding requires a retained TakeDamageEvent root")
    if not isfinite(start_ms) or start_ms < 0:
        raise ValueError("damage start requires finite nonnegative time")
    if root_node.canceled or root.target_entity_uuid is None or root.target_entity_uuid not in before.actors:
        return None
    actor = before.actors[root.target_entity_uuid]
    index = causal_index or index_player_lineage(lineage)
    # A hidden cause remains absent. The request's explicit child relationship
    # can still identify its own committed after-value without inventing an owner.
    candidates = (index.results.get(root_node.resolution_ref, ())
                  if root_node.resolution_ref is not None else lineage.events)
    results = tuple(node for node in candidates
                    if node.parent_lineage == root_node.lineage_uuid and not node.canceled
                    and isinstance(node.fact, DamageResultFact)
                    and node.fact.target_entity_uuid == actor.uuid)
    if not results:
        return None
    packets = tuple(node.fact for node in results if isinstance(node.fact, DamageResultFact))
    owned = (index.owned.get(root_node.resolution_ref, ())
             if root_node.resolution_ref is not None else lineage.events)
    changes = [(event.uuid, event.fact) for event in owned if isinstance(event.fact, LifeFact)
               and not event.canceled and event.fact.entity_uuid == actor.uuid
               and index.damage_requests.get(event.lineage_uuid) == root_node.lineage_uuid]
    target = actor_contact(before, actor, data) if contact is None else contact
    if target.actor_uuid != str(actor.uuid):
        raise ValueError("damage contact belongs to a different recipient")
    target = replace(target, hp=actor.normal_hp, life_state=actor.life_state)
    packet = packets[-1]
    if packet.damage_type is None or packet.applied_damage is None or packet.resulting_normal_hp is None:
        raise ValueError("applied damage requires its native after-values")
    life = changes[-1][1].new_state if changes else actor.life_state
    # Entering DYING can normalize the packet's intermediate negative HP.
    hp = changes[-1][1].normal_hit_points if changes else packet.resulting_normal_hp
    damage = resolve_damage(data, packet.damage_type.value)
    evidence: list[TimingEvidence] = []
    timing = compile_damage(data, target, damage, start_ms, life, timing_evidence=evidence,
        contact_evidence=TimingOperand(TimingReference('event', root_node.uuid, 'contact'), start_ms))
    return DamageCue(root_node.uuid, target, timing, damage, results,
                     sum(packet.applied_damage for packet in packets), hp, life,
                     frozenset(identity for identity, _ in changes), data, tuple(evidence))


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
    if not complete or life is not LifeState.ALIVE:
        body = sample_damage_body(cue.data, cue.contact, elapsed_ms,
            start_ms=timing.start_ms, end_ms=timing.end_ms,
            death_start_ms=timing.start_ms if life is LifeState.DEAD else None,
            resulting_life_state=life, life_start_ms=timing.hp_ms, life_body=timing.life_body)
    flash = cue.damage.hitFlash
    color = ((flash.palette or flash.color) if flash.enabled and not complete
             and timing.flash_ms <= elapsed_ms < timing.flash_ms + flash.durationMs else None)
    return DamageSample(body, VitalsSample(cue.contact.actor_uuid, hp, life, color), complete)
