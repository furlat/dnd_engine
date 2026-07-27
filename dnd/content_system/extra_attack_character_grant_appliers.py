"""Shared structural Extra Attack rank and runtime-family installation."""

from uuid import uuid5

from dnd.blocks.action_economy import (
    RechargeType,
    ResourceCapacityPolicy,
)
from dnd.classes.fighter import (
    ExtraAttack,
    ExtraAttackFeature,
    create_extra_attack_resource_handler,
)
from dnd.content_system.character_build_validation import (
    CharacterGrantScheduleEntry,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import CharacterGrantReceipt
from dnd.core.content.registration import get_content_declaration
from dnd.core.feature_grants import AttackMultiplicityGrant


EXTRA_ATTACK_FEATURE_REF = get_content_declaration(
    ExtraAttackFeature,
).ref

_ATTACKS_PER_ACTION_BY_FEATURE_LEVEL = {
    5: 2,
    11: 3,
    20: 4,
}


def apply_extra_attack_grant(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> CharacterGrantReceipt:
    """Install one source rank; the family action/handler is installed once."""
    if entry.content_ref != EXTRA_ATTACK_FEATURE_REF:
        raise ValueError("Extra Attack applier received a different content ref")
    class_level = entry.provenance.class_level
    if class_level is None:
        raise ValueError("Extra Attack grant requires an exact class level")
    try:
        attacks_per_action = _ATTACKS_PER_ACTION_BY_FEATURE_LEVEL[
            class_level
        ]
    except KeyError as error:
        raise ValueError(
            f"unsupported Extra Attack threshold {class_level}",
        ) from error
    character_level = entry.provenance.character_level
    if character_level is None:
        raise ValueError(
            "Extra Attack grant requires an acquisition character level",
        )

    grant_id = uuid5(context.character_id, entry.grant_token)
    entity = context.entity
    entity.action_economy.add_attack_multiplicity_grant(
        AttackMultiplicityGrant(
            grant_id=grant_id,
            provider_ref=EXTRA_ATTACK_FEATURE_REF,
            attacks_per_attack_action=attacks_per_action,
            acquisition_ordinal=character_level,
        ),
    )
    try:
        entity.action_economy.add_resource_contribution(
            "extra_attacks",
            grant_id,
            maximum=attacks_per_action - 1,
            recharge_type=RechargeType.TURN_START,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
    except Exception:
        entity.action_economy.remove_attack_multiplicity_grant(grant_id)
        raise
    return CharacterGrantReceipt(
        grant_id=grant_id,
        grant_token=entry.grant_token,
        definition_ref=EXTRA_ATTACK_FEATURE_REF,
        resource_contribution_ids=(("extra_attacks", grant_id),),
        attack_multiplicity_grant_ids=(grant_id,),
    )


def install_extra_attack_family(
    context: BuiltinCharacterGrantContext,
) -> CharacterGrantReceipt | None:
    """Install one equipment-independent action/handler for resolved ranks."""
    entity = context.entity
    if not entity.action_economy.get_attack_multiplicity_grants():
        return None
    grant_id = uuid5(
        context.character_id,
        "character-structural-family:v1:extra_attack",
    )
    action = ExtraAttack(
        source_entity_uuid=entity.uuid,
        name="Extra Attack",
        template=True,
        discover_equipped_weapon_slots=True,
    )
    context.runtime.bind_granted_behavior(
        action,
        provider_ref=EXTRA_ATTACK_FEATURE_REF,
        runtime_owner_uuid=entity.uuid,
    )
    entity.register_action(action)
    handler = create_extra_attack_resource_handler(entity.uuid)
    try:
        context.runtime.bind_granted_behavior(
            handler,
            provider_ref=EXTRA_ATTACK_FEATURE_REF,
            runtime_owner_uuid=entity.uuid,
        )
        entity.add_event_handler(handler)
    except Exception:
        entity.unregister_action_by_uuid(action.uuid)
        raise
    return CharacterGrantReceipt(
        grant_id=grant_id,
        definition_ref=EXTRA_ATTACK_FEATURE_REF,
        action_uuids=(action.uuid,),
        handler_uuids=(handler.uuid,),
    )


EXTRA_ATTACK_CHARACTER_GRANT_APPLIERS = {
    EXTRA_ATTACK_FEATURE_REF.identity_key: apply_extra_attack_grant,
}


__all__ = [
    "EXTRA_ATTACK_CHARACTER_GRANT_APPLIERS",
    "EXTRA_ATTACK_FEATURE_REF",
    "apply_extra_attack_grant",
    "install_extra_attack_family",
]
