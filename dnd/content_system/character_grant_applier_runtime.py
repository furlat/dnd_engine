"""Shared reversible-install primitives for structural character grants."""

from __future__ import annotations

from uuid import UUID, uuid5

from dnd.content_system.character_build_validation import (
    CharacterGrantScheduleEntry,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ConditionImmunityHandle,
    LearnedReactionSpellHandle,
    ModifierHandle,
    ProficiencyHandle,
)
from dnd.core.base_actions import BaseAction
from dnd.core.content.identities import ContentRef
from dnd.core.content.origin_features import OriginCapability
from dnd.core.events import EventHandler


def character_grant_id(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> UUID:
    """Return the deterministic runtime owner id for one sealed grant row."""
    return uuid5(context.character_id, entry.grant_token)


def require_grant_ref(
    entry: CharacterGrantScheduleEntry,
    expected_ref: ContentRef,
) -> None:
    """Reject dispatch drift before a grant mutates engine state."""
    if entry.content_ref != expected_ref:
        raise ValueError("grant applier received a different content ref")


def grant_receipt(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    *,
    modifier_handles: tuple[ModifierHandle, ...] = (),
    proficiency_handles: tuple[ProficiencyHandle, ...] = (),
    hit_die_uuids: tuple[UUID, ...] = (),
    spellcasting_source_ids: tuple[UUID, ...] = (),
    normal_spell_slot_capacity_source_ids: tuple[UUID, ...] = (),
    spell_damage_affinity_contribution_ids: tuple[UUID, ...] = (),
    action_uuids: tuple[UUID, ...] = (),
    handler_uuids: tuple[UUID, ...] = (),
    learned_reaction_spell_handles: tuple[
        LearnedReactionSpellHandle,
        ...,
    ] = (),
    resource_contribution_ids: tuple[tuple[str, UUID], ...] = (),
    resource_recovery_contribution_ids: tuple[tuple[str, UUID], ...] = (),
    armor_class_formula_ids: tuple[UUID, ...] = (),
    attack_multiplicity_grant_ids: tuple[UUID, ...] = (),
    condition_immunity_handles: tuple[ConditionImmunityHandle, ...] = (),
    sense_mode_source_ids: tuple[UUID, ...] = (),
    structural_size_source_ids: tuple[UUID, ...] = (),
    origin_capability_source_ids: tuple[
        tuple[OriginCapability, UUID],
        ...,
    ] = (),
    transient_condition_refs_to_remove: tuple[ContentRef, ...] = (),
) -> CharacterGrantReceipt:
    """Build the one canonical receipt shape from a validated grant row."""
    return CharacterGrantReceipt(
        grant_id=character_grant_id(context, entry),
        grant_token=entry.grant_token,
        definition_ref=entry.content_ref,
        modifier_handles=modifier_handles,
        proficiency_handles=proficiency_handles,
        hit_die_uuids=hit_die_uuids,
        spellcasting_source_ids=spellcasting_source_ids,
        normal_spell_slot_capacity_source_ids=(
            normal_spell_slot_capacity_source_ids
        ),
        spell_damage_affinity_contribution_ids=(
            spell_damage_affinity_contribution_ids
        ),
        action_uuids=action_uuids,
        handler_uuids=handler_uuids,
        learned_reaction_spell_handles=learned_reaction_spell_handles,
        resource_contribution_ids=resource_contribution_ids,
        resource_recovery_contribution_ids=(
            resource_recovery_contribution_ids
        ),
        armor_class_formula_ids=armor_class_formula_ids,
        attack_multiplicity_grant_ids=attack_multiplicity_grant_ids,
        condition_immunity_handles=condition_immunity_handles,
        sense_mode_source_ids=sense_mode_source_ids,
        structural_size_source_ids=structural_size_source_ids,
        origin_capability_source_ids=origin_capability_source_ids,
        transient_condition_refs_to_remove=(
            transient_condition_refs_to_remove
        ),
    )


def is_first_grant_for_ref(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
) -> bool:
    """Return whether a repeated row owns its feature's shared runtime family."""
    if entry.content_ref is None:
        return False
    for scheduled in context.preview.grant_schedule:
        if scheduled.content_ref == entry.content_ref:
            return scheduled.grant_token == entry.grant_token
    raise ValueError("grant entry is absent from its validated preview")


def validated_class_level(
    context: BuiltinCharacterGrantContext,
    class_ref: ContentRef,
) -> int:
    """Resolve an exact class level from the sealed validation preview."""
    for scheduled_ref, level in context.preview.class_level_counts:
        if scheduled_ref == class_ref:
            return level
    raise ValueError(
        f"feature grant requires class levels in {class_ref.identity_key}",
    )


def register_bound_action(
    context: BuiltinCharacterGrantContext,
    *,
    provider_ref: ContentRef,
    action: BaseAction,
) -> None:
    """Bind and register one action under its exact authored provider."""
    context.runtime.bind_granted_behavior(
        action,
        provider_id=provider_ref.content_id,
        runtime_owner_uuid=context.entity.uuid,
    )
    context.entity.register_action(action)


def install_bound_handler(
    context: BuiltinCharacterGrantContext,
    entry: CharacterGrantScheduleEntry,
    handler: EventHandler,
) -> CharacterGrantReceipt:
    """Bind/register one handler and return its reversible receipt."""
    content_ref = entry.content_ref
    if content_ref is None:
        raise ValueError("handler grant requires exact content identity")
    context.runtime.bind_granted_behavior(
        handler,
        provider_id=content_ref.content_id,
        runtime_owner_uuid=context.entity.uuid,
    )
    context.entity.add_event_handler(handler)
    return grant_receipt(
        context,
        entry,
        handler_uuids=(handler.uuid,),
    )


__all__ = [
    "character_grant_id",
    "grant_receipt",
    "install_bound_handler",
    "is_first_grant_for_ref",
    "register_bound_action",
    "require_grant_ref",
    "validated_class_level",
]
