"""SRD 5.1 Half-Orc active origin mechanics."""

from typing import Optional
from uuid import UUID

from dnd.core.events import Event, TakeDamageEvent
from dnd.core.life_types import LifeState
from dnd.entity import Entity


HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE = (
    "half_orc_relentless_endurance"
)


def half_orc_relentless_endurance_processor(
    event: Event,
    source_entity_uuid: UUID,
) -> Optional[Event]:
    """Cap one qualifying lethal damage packet at 1 normal hit point."""
    if (
        not isinstance(event, TakeDamageEvent)
        or event.target_entity_uuid != source_entity_uuid
    ):
        return None
    entity = Entity.get(source_entity_uuid)
    if (
        not isinstance(entity, Entity)
        or entity.health.life_state is LifeState.DEAD
        or entity.get_normal_hp() <= 0
    ):
        return None
    preview = entity.preview_take_damage(event)
    current_hp = entity.get_normal_hp()
    if current_hp - preview.normal_hit_point_damage > 0:
        return None
    if preview.overkill_damage >= entity.get_max_hp():
        return None
    if entity.action_economy.get_resource_current(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    ) <= 0:
        return None
    if not entity.action_economy.consume_resource(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
        1,
    ):
        return None
    damage_cap = max(0, current_hp - 1)
    if event.normal_hit_point_damage_cap is not None:
        damage_cap = min(
            damage_cap,
            event.normal_hit_point_damage_cap,
        )
    return event.with_updates(
        normal_hit_point_damage_cap=damage_cap,
        status_message=(
            "Relentless Endurance keeps the target at 1 hit point"
        ),
    )


__all__ = [
    "HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE",
    "half_orc_relentless_endurance_processor",
]
