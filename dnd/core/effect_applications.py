"""Native recipient admission, carrying provenance without feature decisions."""

from uuid import UUID
from dnd.core.effect_types import EffectOrigin
from dnd.core.events import Event, EventPhase, EventQueue, EffectApplicationEvent


def admit_effect_application(
    source_uuid: UUID,
    target_uuid: UUID,
    *,
    origin: EffectOrigin,
    parent: Event,
    source_position: tuple[int, int] | None,
    target_position: tuple[int, int] | None,
) -> bool:
    event = EventQueue.publish_declaration(
        EffectApplicationEvent(
            use_register=False,
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            parent_event=parent.uuid,
            effect_origin=origin,
            source_position=source_position,
            target_position=target_position,
        )
    )
    if event.canceled:
        return False
    event = event.phase_to(EventPhase.EXECUTION)
    if event.canceled:
        return False
    event.phase_to(EventPhase.COMPLETION)
    return True
