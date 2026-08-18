"""Canonical reversal of source-owned structural character-grant receipts."""

from typing import cast

from dnd.content_system.character_grant_applier_runtime import (
    remove_modifier_handle,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ProficiencyHandle,
)
from dnd.core.base_block import BaseBlock
from dnd.core.content.durable_characters import ProficiencySubjectKind
from dnd.core.events import AbilityName, SkillName
from dnd.entities.entity import Entity


def _remove_transient_conditions(
    entity: Entity,
    identity_keys: set[str],
) -> None:
    """Remove source-owned runtime conditions in one world traversal."""

    if not identity_keys:
        return
    for condition_owner in Entity.get_all_entities():
        for condition in tuple(
            condition_owner.active_conditions_by_uuid.values(),
        ):
            binding = condition.behavior_binding
            if (
                binding is not None
                and binding.definition_ref.identity_key in identity_keys
                and condition.source_entity_uuid == entity.uuid
            ):
                condition_owner.remove_condition_by_uuid(condition.uuid)


def _remove_proficiency_handle(
    entity: Entity,
    handle: ProficiencyHandle,
) -> None:
    subject = handle.subject
    subject_id = subject.subject_id
    if subject.subject_kind is ProficiencySubjectKind.ABILITY_CHECK:
        if subject_id is None or not subject_id.startswith("ability_check."):
            raise RuntimeError(
                "ability-check receipt has an invalid subject identity",
            )
        entity.ability_scores.get_ability(
            cast(AbilityName, subject_id.removeprefix("ability_check.")),
        ).remove_check_proficiency_source(handle.source_id)
        return
    if subject.subject_kind is ProficiencySubjectKind.SKILL:
        if subject_id is None or not subject_id.startswith("skill."):
            raise RuntimeError("skill receipt has an invalid subject identity")
        entity.skill_set.get_skill(
            cast(SkillName, subject_id.removeprefix("skill.")),
        ).remove_proficiency_source(handle.source_id)
        return
    if subject.subject_kind is ProficiencySubjectKind.SAVING_THROW:
        if subject_id is None or not subject_id.startswith("saving_throw."):
            raise RuntimeError(
                "saving-throw receipt has an invalid subject identity",
            )
        entity.saving_throws.get_saving_throw(
            cast(AbilityName, subject_id.removeprefix("saving_throw.")),
        ).remove_proficiency_source(handle.source_id)
        return
    entity.creature_proficiencies.remove_source(handle.source_id)


def remove_character_grant_receipt(
    entity: Entity,
    grant: CharacterGrantReceipt,
) -> None:
    """Reverse every declared handle in one grant receipt exactly once."""
    _remove_transient_conditions(
        entity,
        {
            ref.identity_key
            for ref in grant.transient_condition_refs_to_remove
        },
    )
    _remove_character_grant_handles(entity, grant)


def _remove_character_grant_handles(
    entity: Entity,
    grant: CharacterGrantReceipt,
) -> None:
    """Reverse non-condition handles after shared transient cleanup."""

    for action_uuid in reversed(grant.action_uuids):
        entity.unregister_action_by_uuid(action_uuid)
    for handler_uuid in reversed(grant.handler_uuids):
        handler = entity.event_handlers.get(handler_uuid)
        if handler is not None:
            entity.remove_event_handler(handler)
    for handle in reversed(grant.learned_reaction_spell_handles):
        remove_handler = (
            entity.spellcasting.remove_learned_reaction_spell_source(
                spell_ref=handle.spell_ref,
                source_id=handle.spellcasting_source_id,
                handler_uuid=handle.handler_uuid,
            )
        )
        if remove_handler:
            handler = entity.event_handlers.get(handle.handler_uuid)
            if handler is None:
                raise RuntimeError(
                    "learned reaction spell handler "
                    f"{handle.handler_uuid} is missing",
                )
            entity.remove_event_handler(handler)
    for handle in reversed(grant.condition_immunity_handles):
        block = BaseBlock.get(handle.block_uuid)
        if block is None:
            raise RuntimeError(
                f"composition immunity block {handle.block_uuid} is missing",
            )
        block.remove_condition_immunity_source(
            handle.condition_name,
            handle.source_id,
        )
    for source_id in reversed(grant.sense_mode_source_ids):
        entity.senses.remove_sense_mode_source(source_id)
    for source_id in reversed(grant.structural_size_source_ids):
        entity.remove_structural_size_source(source_id)
    for capability, source_id in reversed(
        grant.origin_capability_source_ids,
    ):
        entity.remove_origin_capability_source(capability, source_id)
    for resource_name, source_id in reversed(
        grant.resource_recovery_contribution_ids,
    ):
        entity.action_economy.remove_resource_recovery_contribution(
            resource_name,
            source_id,
        )
    for resource_name, source_id in reversed(
        grant.resource_contribution_ids,
    ):
        entity.action_economy.remove_resource_contribution(
            resource_name,
            source_id,
        )
    for formula_id in reversed(grant.armor_class_formula_ids):
        entity.equipment.remove_armor_class_formula_candidate(formula_id)
    for source_id in reversed(grant.attack_multiplicity_grant_ids):
        entity.action_economy.remove_attack_multiplicity_grant(source_id)
    for source_id in reversed(grant.normal_spell_slot_capacity_source_ids):
        entity.action_economy.remove_normal_spell_slot_capacity(source_id)
    for source_id in reversed(
        grant.spell_damage_affinity_contribution_ids,
    ):
        entity.spellcasting.remove_spell_damage_affinity_contribution(
            source_id,
        )
    for source_id in reversed(grant.spellcasting_source_ids):
        entity.spellcasting.remove_source(source_id)
    for hit_die_uuid in reversed(grant.hit_die_uuids):
        entity.health.remove_hit_dice_by_uuid(hit_die_uuid)
    for handle in reversed(grant.proficiency_handles):
        _remove_proficiency_handle(entity, handle)
    for handle in reversed(grant.modifier_handles):
        remove_modifier_handle(handle)


def remove_character_grant_receipts(
    entity: Entity,
    receipts: tuple[CharacterGrantReceipt, ...]
    | list[CharacterGrantReceipt],
) -> None:
    """Reverse an ordered receipt ledger in dependency-safe order."""

    _remove_transient_conditions(
        entity,
        {
            ref.identity_key
            for receipt in receipts
            for ref in receipt.transient_condition_refs_to_remove
        },
    )
    for receipt in reversed(receipts):
        _remove_character_grant_handles(entity, receipt)


__all__ = [
    "remove_character_grant_receipt",
    "remove_character_grant_receipts",
]
