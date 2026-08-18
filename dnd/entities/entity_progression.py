"""Entity-owned ordered class-level transactions."""

from dataclasses import dataclass
from typing import Optional

from dnd.blocks.action_economy import RechargeType
from dnd.types.damage import DamageType, ResistanceStatus
from dnd.types.equipment import (
    ArmorType,
    BodyPart,
    EquipmentSlot,
    RingSlot,
    WeaponProperty,
    WeaponSlot,
)
from dnd.entities.creature_transforms import (
    EntityTransform,
    EntityTransformReceipt,
    apply_entity_transforms,
    rollback_entity_transforms,
)
from dnd.entities.entity import Entity
from dnd.core.events.entity_events import (
    EntityLevelAddedEvent,
    EntityLevelRemovedEvent,
)
from dnd.core.events.events_registry import EventPhase, EventQueue
from dnd.types.progression import AppliedClassLevel, AppliedOriginState


_CONCRETE_EQUIPMENT_SLOTS: tuple[EquipmentSlot, ...] = (
    *tuple(WeaponSlot),
    BodyPart.HEAD,
    BodyPart.BODY,
    BodyPart.HANDS,
    BodyPart.LEGS,
    BodyPart.FEET,
    BodyPart.AMULET,
    RingSlot.LEFT,
    RingSlot.RIGHT,
    BodyPart.CLOAK,
)


_SUBCLASS_OWNER = {
    "berserker": "barbarian",
    "champion": "fighter",
    "draconic_bloodline": "sorcerer",
}


@dataclass(frozen=True, slots=True)
class ResolvedLevelStep:
    """Content-resolved semantic level row plus concrete operations."""

    level: AppliedClassLevel
    transforms: tuple[EntityTransform, ...] = ()


@dataclass(frozen=True, slots=True)
class AppliedLevelReceipt:
    """Live inverse handles for one applied semantic level row."""

    step: ResolvedLevelStep
    transforms: tuple[EntityTransformReceipt, ...]


def entity_terminal_state_fields(entity: Entity) -> dict[str, object]:
    """Serialize reducer-complete direct state after birth or progression."""
    inventory_items = tuple(entity.inventory.items.values())
    equipped_by_slot = tuple(
        (slot, item)
        for slot in _CONCRETE_EQUIPMENT_SLOTS
        if (item := entity.equipment.get_item_by_slot(slot)) is not None
    )
    items_by_uuid = {
        item.uuid: item
        for item in (
            *inventory_items,
            *(item for _, item in equipped_by_slot),
        )
    }
    proficiencies = entity.creature_proficiencies
    weapon_proficiencies = []
    for category in (WeaponProperty.SIMPLE, WeaponProperty.MARTIAL):
        if proficiencies.is_weapon_proficient((category,)):
            weapon_proficiencies.append(f"weapon.{category.value.lower()}")
    weapon_proficiencies.extend(sorted(
        set(proficiencies.base_weapon_ids)
        | {
            key
            for key, sources in proficiencies.specific_weapon_sources.items()
            if sources.sources
        },
    ))
    resources = tuple(
        (
            name,
            resource.current,
            resource.maximum,
            resource.recharge_type.value,
        )
        for name, resource in sorted(entity.action_economy.resources.items())
    )
    resource_recoveries = tuple(
        (name, trigger.value, amount)
        for name, resource in sorted(entity.action_economy.resources.items())
        for trigger in RechargeType
        if (
            amount := sum(
                contribution.amount
                for contribution in resource.recovery_contributions.values()
                if contribution.trigger is trigger
            )
        )
    )
    return {
        "ability_scores": tuple(
            (ability.name, ability.ability_score.score)
            for ability in entity.ability_scores.abilities_list
        ),
        "skill_proficiencies": tuple(
            skill.name for skill in entity.skill_set.proficiencies
        ),
        "skill_expertise": tuple(
            skill.name for skill in entity.skill_set.expertise
        ),
        "saving_throw_proficiencies": tuple(
            saving_throw.name
            for saving_throw in entity.saving_throws.proficiencies
        ),
        "proficiency_bonus": entity.proficiency_bonus.normalized_score,
        "armor_class": entity.ac_bonus().normalized_score,
        "current_hit_points": max(0, entity.get_hp()),
        "maximum_hit_points": max(0, entity.get_max_hp()),
        "hit_dice": tuple(
            (
                hit_die.hit_dice_value.normalized_score,
                hit_die.hit_dice_count.normalized_score,
                hit_die.spent_hit_dice,
                hit_die.mode,
                hit_die.ignore_first_level,
            )
            for hit_die in entity.health.hit_dices
        ),
        "damage_affinities": tuple(
            (damage_type, status)
            for damage_type in DamageType
            if (
                status := entity.health.get_resistance(damage_type)
            ) is not ResistanceStatus.NONE
        ),
        "walking_speed_feet": entity.action_economy.current_speed(),
        "swimming_speed_feet": entity.swimming_speed,
        "sense_modes": tuple(entity.senses.get_sense_modes()),
        "origin_capabilities": tuple(sorted(
            (
                capability
                for capability, sources in entity.origin_capability_sources.items()
                if sources
            ),
            key=lambda capability: capability.value,
        )),
        "body_semantics": tuple(sorted(
            entity.appearance.semantic_properties.items(),
        )),
        "feature_ids": tuple(sorted(entity.feature_sources)),
        "weapon_proficiencies": tuple(weapon_proficiencies),
        "armor_proficiencies": tuple(
            armor_type.value
            for armor_type in (ArmorType.LIGHT, ArmorType.MEDIUM, ArmorType.HEAVY)
            if proficiencies.is_armor_proficient(armor_type)
        ),
        "shield_proficient": proficiencies.is_shield_proficient(),
        "languages": tuple(sorted(
            set(proficiencies.base_languages)
            | {
                key
                for key, sources in proficiencies.language_sources.items()
                if sources.sources
            },
        )),
        "tools": tuple(sorted(
            set(proficiencies.base_tools)
            | {
                key
                for key, sources in proficiencies.tool_sources.items()
                if sources.sources
            },
        )),
        "action_ids": tuple(sorted(
            action.get_semantic_key() for action in entity.registered_actions
        )),
        "handler_ids": tuple(sorted(
            handler.get_semantic_key()
            for handler in entity.event_handlers.values()
        )),
        "condition_ids": tuple(sorted(
            condition.get_semantic_key()
            for condition in entity.active_conditions.values()
        )),
        "condition_immunities": tuple(sorted({
            condition_name
            for condition_name, _source_name in entity.condition_immunities
        })),
        "attacks_per_action": (
            entity.action_economy.resolve_attacks_per_attack_action()
        ),
        "attack_multiplicity": tuple(
            (
                grant.provider_id,
                grant.attacks_per_attack_action,
                grant.acquisition_ordinal,
            )
            for grant in entity.action_economy.get_attack_multiplicity_grants()
        ),
        "resources": resources,
        "resource_recoveries": resource_recoveries,
        "spell_sources": tuple(
            (
                source.source_kind,
                source.provider_id,
                source.ability,
                source.provider_level,
                source.maximum_spell_rank,
                (
                    source.caster_progression.value
                    if source.caster_progression is not None
                    else None
                ),
                (
                    source.ritual_policy.value
                    if source.ritual_policy is not None
                    else None
                ),
            )
            for source in sorted(
                entity.spellcasting.sources.values(),
                key=lambda row: (row.provider_id, str(row.source_id)),
            )
        ),
        "known_spell_ids": tuple(sorted({
            action.behavior_id
            for action in entity.registered_actions
            if action.behavior_id.startswith("spell.")
        })),
        "reaction_spell_ids": tuple(sorted(
            entity.spellcasting.learned_reaction_spell_handlers,
        )),
        "prepared_spell_ids": tuple(sorted(entity.prepared_spell_ids)),
        "feature_toggle_ids": tuple(sorted(entity.feature_toggle_ids)),
        "spell_slots": tuple(
            (
                rank,
                entity.action_economy.spell_slot_value(rank).normalized_score,
            )
            for rank in range(1, 10)
        ),
        "armor_class_formulas": tuple(
            (
                formula.base_ac,
                formula.ability_names,
                formula.requires_unarmored,
                formula.allows_shield,
            )
            for formula in sorted(
                entity.equipment.armor_class_formula_candidates.values(),
                key=lambda row: str(row.source_id),
            )
        ),
        "items": tuple(
            items_by_uuid[item_uuid].to_item_state()
            for item_uuid in sorted(items_by_uuid, key=str)
        ),
        "inventory_item_uuids": tuple(sorted(
            entity.inventory.items,
            key=str,
        )),
        "equipment": tuple(
            (slot.value, item.uuid)
            for slot, item in equipped_by_slot
        ),
    }


def _validate_next_level(entity: Entity, level: AppliedClassLevel) -> None:
    """Validate append-only total, class, subclass, and source-step order."""
    if level.step_id in entity._progression_receipts:
        raise ValueError(f"level step {level.step_id!r} is already applied")
    expected_character_level = len(entity.applied_class_levels) + 1
    if level.character_level != expected_character_level:
        raise ValueError(
            "character level must append exactly one step: "
            f"expected {expected_character_level}, got {level.character_level}",
        )
    same_class = tuple(
        row for row in entity.applied_class_levels if row.class_id is level.class_id
    )
    expected_class_level = len(same_class) + 1
    if level.resulting_class_level != expected_class_level:
        raise ValueError(
            f"{level.class_id.value} level must be {expected_class_level}, "
            f"got {level.resulting_class_level}",
        )
    if (
        level.subclass_id is not None
        and _SUBCLASS_OWNER[level.subclass_id.value] != level.class_id.value
    ):
        raise ValueError("subclass does not belong to the applied class")
    selected_subclasses = {
        row.subclass_id for row in same_class if row.subclass_id is not None
    }
    if selected_subclasses and level.subclass_id not in selected_subclasses:
        raise ValueError("an applied class cannot change its subclass")


def _install_level(entity: Entity, step: ResolvedLevelStep) -> AppliedLevelReceipt:
    """Install one resolved step without publishing a progression fact."""
    _validate_next_level(entity, step.level)
    transform_receipts = apply_entity_transforms(entity, step.transforms)
    receipt = AppliedLevelReceipt(
        step=step,
        transforms=transform_receipts,
    )
    try:
        entity.applied_class_levels.append(step.level)
        entity._progression_receipts[step.level.step_id] = receipt
    except Exception:
        rollback_entity_transforms(transform_receipts)
        raise
    return receipt


def apply_level(entity: Entity, step: ResolvedLevelStep) -> AppliedClassLevel:
    """Apply one already-resolved level through the universal entity path."""
    if not entity.creation_committed:
        raise RuntimeError("cannot level an entity before creation commits")
    previous_total = len(entity.applied_class_levels)
    receipt = _install_level(entity, step)
    try:
        EventQueue.publish_completed_fact(EntityLevelAddedEvent(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            use_register=False,
            phase=EventPhase.COMPLETION,
            entity_uuid=entity.uuid,
            previous_total_level=previous_total,
            new_total_level=len(entity.applied_class_levels),
            level=step.level,
            resulting_class_levels=_resulting_class_levels(entity),
            **entity_terminal_state_fields(entity),
        ))
    except Exception:
        rollback_entity_transforms(receipt.transforms)
        entity.applied_class_levels.pop()
        del entity._progression_receipts[step.level.step_id]
        raise
    return step.level


def remove_last_level(
    entity: Entity,
    expected_step_id: Optional[str] = None,
) -> AppliedClassLevel:
    """Undo only the final applied level and remove its semantic ledger row."""
    previous_total = len(entity.applied_class_levels)
    level, receipt = _uninstall_last_level(entity, expected_step_id)
    try:
        EventQueue.publish_completed_fact(EntityLevelRemovedEvent(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            use_register=False,
            phase=EventPhase.COMPLETION,
            entity_uuid=entity.uuid,
            previous_total_level=previous_total,
            new_total_level=len(entity.applied_class_levels),
            level=level,
            resulting_class_levels=_resulting_class_levels(entity),
            **entity_terminal_state_fields(entity),
        ))
    except Exception:
        _install_level(entity, receipt.step)
        raise
    return level


def _uninstall_last_level(
    entity: Entity,
    expected_step_id: Optional[str] = None,
) -> tuple[AppliedClassLevel, AppliedLevelReceipt]:
    """Undo the final live receipt without publishing a progression fact."""
    if not entity.applied_class_levels:
        raise ValueError("entity has no applied class level")
    level = entity.applied_class_levels[-1]
    if expected_step_id is not None and level.step_id != expected_step_id:
        raise ValueError(
            f"last level step is {level.step_id!r}, not {expected_step_id!r}",
        )
    receipt = entity._progression_receipts.get(level.step_id)
    if not isinstance(receipt, AppliedLevelReceipt):
        raise RuntimeError(f"live receipt for level step {level.step_id!r} is missing")
    rollback_entity_transforms(receipt.transforms)
    entity.applied_class_levels.pop()
    del entity._progression_receipts[level.step_id]
    return level, receipt


def _resulting_class_levels(entity: Entity) -> tuple[tuple[str, int], ...]:
    """Return stable per-class totals directly from the semantic ledger."""
    totals: dict[str, int] = {}
    for row in entity.applied_class_levels:
        totals[row.class_id.value] = row.resulting_class_level
    return tuple(sorted(totals.items()))


def hydrate_progression(
    entity: Entity,
    applied_origin: Optional[AppliedOriginState],
    resolved_steps: tuple[ResolvedLevelStep, ...],
    *,
    origin_transforms: tuple[EntityTransform, ...] = (),
) -> tuple[AppliedLevelReceipt, ...]:
    """Rebuild live receipts from persisted state without content lookup."""
    if entity.creation_committed or entity.is_deployed:
        raise ValueError("progression hydration requires an unpublished entity")
    if entity.applied_class_levels or entity._progression_receipts:
        raise ValueError("progression hydration requires an empty entity ledger")
    if entity.applied_origin_state is not None:
        raise ValueError("progression hydration requires empty origin state")

    origin_receipts = apply_entity_transforms(entity, origin_transforms)
    installed: list[AppliedLevelReceipt] = []
    entity.applied_origin_state = applied_origin
    try:
        for step in resolved_steps:
            installed.append(_install_level(entity, step))
    except Exception:
        while entity.applied_class_levels:
            _uninstall_last_level(entity)
        rollback_entity_transforms(origin_receipts)
        entity.applied_origin_state = None
        raise
    return tuple(installed)


__all__ = [
    "AppliedLevelReceipt",
    "ResolvedLevelStep",
    "apply_level",
    "hydrate_progression",
    "remove_last_level",
]
