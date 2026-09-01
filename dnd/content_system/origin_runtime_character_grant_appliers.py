"""Reversible active runtime grants owned by character origins."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid5

from dnd.blocks.action_economy import (
    RechargeType,
    ResourceCapacityPolicy,
)
from dnd.content_system.character_build_validation import (
    CharacterGrantScheduleEntry,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import CharacterGrantReceipt
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.origins.halfling import (
    HALFLING_LUCKY_REF,
    halfling_lucky_processor,
)
from dnd.origins.half_orc import (
    HALF_ORC_RELENTLESS_ENDURANCE_REF,
    HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    half_orc_relentless_endurance_processor,
)


OriginRuntimeCharacterGrantApplier = Callable[
    [BuiltinCharacterGrantContext, CharacterGrantScheduleEntry],
    CharacterGrantReceipt,
]


def _apply_halfling_lucky(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    if entry.content_ref != HALFLING_LUCKY_REF:
        raise ValueError("Halfling Lucky applier received a different ref")
    entity = context.entity
    handler = EventHandler(
        name="Halfling Lucky",
        source_entity_uuid=entity.uuid,
        trigger_conditions=[
            Trigger(
                event_type=event_type,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=entity.uuid,
            )
            for event_type in (
                EventType.ATTACK_D20_ROLL_RESULT,
                EventType.SAVE_D20_ROLL_RESULT,
                EventType.CHECK_D20_ROLL_RESULT,
            )
        ],
        event_processor=halfling_lucky_processor,
    )
    try:
        context.runtime.bind_granted_behavior(
            handler,
            provider_id=HALFLING_LUCKY_REF.content_id,
            runtime_owner_uuid=entity.uuid,
        )
        entity.add_event_handler(handler)
    except Exception:
        handler.remove_from_register()
        raise
    return CharacterGrantReceipt(
        grant_id=handler.uuid,
        grant_token=entry.grant_token,
        definition_ref=HALFLING_LUCKY_REF,
        handler_uuids=(handler.uuid,),
    )


def _apply_half_orc_relentless_endurance(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    if entry.content_ref != HALF_ORC_RELENTLESS_ENDURANCE_REF:
        raise ValueError(
            "Relentless Endurance applier received a different ref",
        )
    entity = context.entity
    grant_id = uuid5(
        context.character_id,
        f"dnd-engine:character-structural-grant:v1:{entry.grant_token}",
    )
    handler = EventHandler(
        name="Relentless Endurance",
        source_entity_uuid=entity.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=entity.uuid,
            ),
        ],
        event_processor=half_orc_relentless_endurance_processor,
    )
    resource_installed = False
    handler_installed = False
    try:
        entity.action_economy.add_resource_contribution(
            HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
            grant_id,
            maximum=1,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        resource_installed = True
        context.runtime.bind_granted_behavior(
            handler,
            provider_id=HALF_ORC_RELENTLESS_ENDURANCE_REF.content_id,
            runtime_owner_uuid=entity.uuid,
        )
        entity.add_event_handler(handler)
        handler_installed = True
    except Exception:
        if handler_installed:
            entity.remove_event_handler(handler)
        else:
            handler.remove_from_register()
        if resource_installed:
            entity.action_economy.remove_resource_contribution(
                HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
                grant_id,
            )
        raise
    return CharacterGrantReceipt(
        grant_id=grant_id,
        grant_token=entry.grant_token,
        definition_ref=HALF_ORC_RELENTLESS_ENDURANCE_REF,
        handler_uuids=(handler.uuid,),
        resource_contribution_ids=(
            (HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE, grant_id),
        ),
    )


ORIGIN_RUNTIME_CHARACTER_GRANT_APPLIERS: dict[
    str,
    OriginRuntimeCharacterGrantApplier,
] = {
    HALF_ORC_RELENTLESS_ENDURANCE_REF.identity_key: (
        _apply_half_orc_relentless_endurance
    ),
    HALFLING_LUCKY_REF.identity_key: _apply_halfling_lucky,
}


__all__ = [
    "ORIGIN_RUNTIME_CHARACTER_GRANT_APPLIERS",
    "OriginRuntimeCharacterGrantApplier",
]
