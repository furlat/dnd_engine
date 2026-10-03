"""Cosmetic cast areas owned by exact, observed native concentration slots."""

from dataclasses import dataclass, replace
from typing import Mapping
from uuid import UUID

from dnd.core.item_types import ItemConcentrationSlot
from dnd.core.presentation_geometry import AoEPresentationGeometry
from game.animation_types import AnimationData
from game.choreography import BoundChoreography, MotionTimeline, walk_bound_timelines
from game.combat import BoundCast
from game.draw_commands import DrawCommand
from game.maintained_media import maintained_media_alpha, maintained_media_frame, maintained_removal_duration
from game.player_facts import PlayerLineage, PlayerState, SpellFact
from game.player_reduction import reduce_lineage
from game.projection import Camera
from game.spatial_field_media import field_media_commands


@dataclass(frozen=True, slots=True)
class ConcentrationMediaLifetime:
    slot_uuid: UUID
    spell_id: str
    actor_uuid: UUID
    item_uuid: UUID | None
    geometry: AoEPresentationGeometry
    positions: tuple[tuple[int, int], ...]
    elevation_steps: float
    applied_ms: float
    removed_ms: float | None = None


def _slots(state: PlayerState, actor: UUID, item: UUID | None) -> tuple[ItemConcentrationSlot, ...] | None:
    """Missing observation is unknown; an observed empty slot list is authoritative."""
    if item is not None:
        if state.senses is None or item not in state.senses.objects:
            return None
        obj = state.objects.get(item)
        return obj.item.concentration_slots if obj is not None else None
    if actor != state.observer_uuid and (state.senses is None
            or (contact := state.senses.entities.get(actor)) is None or not contact.visual):
        return None
    owner = state.actors.get(actor)
    if owner is None:
        return None
    return tuple(slot for condition in owner.conditions if condition.state is not None
                 for slot in condition.state.concentration_slots)


def register_concentration_lifetimes(
    retained: Mapping[UUID, ConcentrationMediaLifetime], before: PlayerState, data: AnimationData,
    *, absolute_start_ms: float, lineage: PlayerLineage | None = None,
    choreography: BoundChoreography | None = None, motion: MotionTimeline | None = None,
) -> dict[UUID, ConcentrationMediaLifetime]:
    """Reconcile committed slots, never a transient Concentrating root replacement."""
    result = {owner: row for owner, row in retained.items() if row.removed_ms is None
              or absolute_start_ms < row.removed_ms + maintained_removal_duration(data, data.concentration_media[row.spell_id])}
    if lineage is None:
        return result  # Cold snapshots alone supply no cast-area permission.
    after = reduce_lineage(before, lineage)
    visits = tuple(walk_bound_timelines(choreography, motion))
    groups = tuple((visit.offset_ms, visit.timeline) for visit in visits
                   if isinstance(visit.timeline, BoundChoreography))
    # A slot carries its actual creating cast, independently of spell identity.
    nodes = {node.uuid: node for node in lineage.events}
    for offset, group in groups:
        for cast in group.nodes:
            node = nodes.get(cast.event_uuid)
            if node is None or node.canceled or not isinstance(node.fact, SpellFact) or not isinstance(cast.bound, BoundCast):
                continue
            fact = node.fact
            if (fact.behavior_id not in data.concentration_media or fact.area_geometry is None
                    or fact.resolved_area_positions is None
                    or fact.cast_origin == "source_item" and fact.source_item_uuid is None):
                continue
            slots = _slots(cast.bound.after, fact.source_entity_uuid, fact.source_item_uuid)
            slot = next((slot for slot in slots or () if slot.cast_lineage_uuid == node.lineage_uuid), None)
            if slot is None or slot.slot_uuid in result:
                continue
            origin = fact.aoe_position
            support = group.before.tiles.get(origin) if origin is not None else None
            if support is None:
                continue
            assert fact.behavior_id is not None
            result[slot.slot_uuid] = ConcentrationMediaLifetime(slot.slot_uuid, fact.behavior_id,
                fact.source_entity_uuid, fact.source_item_uuid, fact.area_geometry, fact.resolved_area_positions,
                support.elevation_steps, absolute_start_ms + offset + cast.start_ms + cast.bound.timeline.release_ms)
    # Use the final committed observation, so retained slots survive native root
    # replacement. Retirement starts at its observed owner-state change.
    for owner, record in tuple(result.items()):
        slots = _slots(after, record.actor_uuid, record.item_uuid)
        if record.removed_ms is not None or slots is None or any(slot.slot_uuid == owner for slot in slots):
            continue
        states = sorted(((offset + at, state) for visit in visits for offset in (visit.offset_ms,) for at, state in visit.timeline.states), key=lambda row: row[0])
        known_states = [(at, known) for at, state in states
                        if (known := _slots(state, record.actor_uuid, record.item_uuid)) is not None]
        last_present = max((index for index, (_, known) in enumerate(known_states)
                            if any(slot.slot_uuid == owner for slot in known)), default=-1)
        at = next((at for index, (at, known) in enumerate(known_states) if index > last_present
                   and not any(slot.slot_uuid == owner for slot in known)), 0.)
        result[owner] = replace(record, removed_ms=absolute_start_ms + at)
    return result


def concentration_media_draw_commands(state: PlayerState, data: AnimationData, now_ms: float,
                                      camera: Camera, retained: Mapping[UUID, ConcentrationMediaLifetime],
                                      ) -> tuple[DrawCommand, ...]:
    commands = []
    for owner, record in retained.items():
        binding = data.concentration_media[record.spell_id]
        if now_ms < record.applied_ms:
            continue
        for index, layer in enumerate(binding.layers):
            alpha = maintained_media_alpha(binding, layer, now_ms, record.removed_ms)
            if binding.formationFadeMs:
                alpha *= min(1., (now_ms - record.applied_ms) / binding.formationFadeMs)
            frame = maintained_media_frame(data, binding, layer, now_ms, record.applied_ms, record.removed_ms)
            if alpha <= 0 or frame is None:
                continue
            commands.extend(field_media_commands(state, data, owner, record.geometry, record.positions,
                binding, layer, index, *frame, camera, alpha, anchor_elevation_steps=record.elevation_steps))
    return tuple(commands)
