"""Reversible active runtime grants owned by character origins."""

from __future__ import annotations

from collections.abc import Callable

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
from dnd.content_system.character_grant_applier_runtime import (
    CharacterGrantInstallation,
    character_grant_id,
    grant_receipt,
    require_grant_ref,
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
    require_grant_ref(entry, HALFLING_LUCKY_REF)
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
    with CharacterGrantInstallation(context, entry) as installation:
        installation.add_bound_handler(handler)
    return grant_receipt(
        context,
        entry,
        handler_uuids=installation.handler_uuids,
    )


def _apply_half_orc_relentless_endurance(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    require_grant_ref(entry, HALF_ORC_RELENTLESS_ENDURANCE_REF)
    entity = context.entity
    grant_id = character_grant_id(context, entry)
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
    with CharacterGrantInstallation(context, entry) as installation:
        installation.add_resource(
            HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
            grant_id,
            maximum=1,
            recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        installation.add_bound_handler(handler)
    return grant_receipt(
        context,
        entry,
        handler_uuids=installation.handler_uuids,
        resource_contribution_ids=installation.resource_contribution_ids,
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
