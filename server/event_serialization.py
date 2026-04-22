"""Compatibility helper for JSON-compatible domain event serialization."""

from typing import Any, Dict

from dnd.core.events import Event


def serialize_event(event: Event) -> Dict[str, Any]:
    """Serialize an event without adding transport-only presentation fields."""
    return event.model_dump(mode="json")
