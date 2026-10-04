"""Passive item dates admitted once with the existing choreography head."""

from dataclasses import replace
from typing import Mapping
from uuid import UUID

from dnd.core.events import EventType
from dnd.core.item_types import ItemEffectPresentationState
from game.animation_types import AnimationData, ItemAttachmentStart
from game.choreography import BoundChoreography, MotionTimeline, walk_bound_timelines
from game.player_facts import ItemEffectChangeFact, PlayerLineage, PlayerState


def item_attachment_members(state: PlayerState, data: AnimationData,
                            ) -> dict[UUID, tuple[UUID, ItemEffectPresentationState]]:
    """Covered items retain dates; only disclosed floor/gear pixels render."""
    items = (*(obj.item for obj in state.objects.values()),
        *(item for actor in state.actors.values() for item in actor.visual_loadout.layers),
        *(item for actor in state.actors.values() for item in actor.controlled_items or ()))
    return {effect.effect_uuid: (item.item_uuid, effect) for item in items
            for effect in item.item_effects if effect.behavior_id in data.item_attachments}


def register_item_attachment_starts(
    retained: Mapping[UUID, ItemAttachmentStart], before: PlayerState, data: AnimationData,
    *, absolute_start_ms: float, lineage: PlayerLineage | None = None,
    choreography: BoundChoreography | None = None, motion: MotionTimeline | None = None,
) -> dict[UUID, ItemAttachmentStart]:
    """Visibility and suppression never reset an already received source clock."""
    result = dict(retained)
    for owner, (item, effect) in item_attachment_members(before, data).items():
        result.setdefault(owner, ItemAttachmentStart(item, source_cursor=effect.applied_source_event_cursor))
    versions = {row.event_uuid: row.source_index for row in lineage.version_rows} if lineage else {}
    applications = {node.fact.effect_uuid: versions.get(node.uuid)
        for node in lineage.events if not node.canceled and isinstance(node.fact, ItemEffectChangeFact)
        and node.fact.event_type is EventType.CONDITION_APPLICATION} if lineage else {}
    visits = tuple(walk_bound_timelines(choreography, motion))
    states = [(at + visit.offset_ms, state) for visit in visits
              for at, state in visit.timeline.states]
    states.extend((visit.offset_ms + visit.timeline.complete_ms, visit.timeline.after)
                  for visit in visits if isinstance(visit.timeline, BoundChoreography))
    for at, state in sorted(states, key=lambda row: row[0]):
        for owner, (item, effect) in item_attachment_members(state, data).items():
            previous = result.get(owner)
            if previous is None:
                result[owner] = ItemAttachmentStart(item,
                    absolute_start_ms + at if owner in applications else None,
                    effect.applied_source_event_cursor or applications.get(owner))
            elif previous.source_cursor is None and effect.applied_source_event_cursor is not None:
                result[owner] = replace(previous, source_cursor=effect.applied_source_event_cursor)
    return result
