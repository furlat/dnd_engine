"""Shared event serialization for polling and streaming transports."""

from typing import Any, Dict

from dnd.blocks.equipment import EquipmentEvent
from dnd.core.events import Event
from dnd.entity import Entity

from server.api_models import APIEquipmentOverview


def serialize_event(event: Event) -> Dict[str, Any]:
    """Serialize an event with presentation-only transport enrichments."""
    event_data = event.model_dump(mode='json')

    if isinstance(event, EquipmentEvent) and event.source_entity_uuid:
        entity = Entity.get(event.source_entity_uuid)
        if entity is not None:
            event_data['resulting_equipment'] = (
                APIEquipmentOverview.create(entity).model_dump(mode='json')
            )

    return event_data
