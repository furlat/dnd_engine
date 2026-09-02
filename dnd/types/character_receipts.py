"""Closed data-only receipts for direct character grant families.

Each field names a concrete Entity/component owner operation.  These rows are
not interpreted generically: the matching origin or class cleanup function
reads only its own receipt type and calls those owners directly.
"""

from dataclasses import dataclass
from uuid import UUID

from dnd.types.abilities import AbilityName, SavingThrowName, SkillName
from dnd.types.character_progression import OriginCapability


def _require_step_id(step_id: str) -> None:
    if not step_id or "." not in step_id:
        raise ValueError("receipt step_id must be a namespaced semantic ID")


@dataclass(frozen=True, slots=True)
class OriginGrantReceipt:
    """Exact owner contributions installed by one applied origin."""

    step_id: str
    source_id: UUID
    ability_score_modifier_ids: tuple[tuple[AbilityName, UUID], ...] = ()
    skill_proficiency_sources: tuple[tuple[SkillName, UUID], ...] = ()
    creature_proficiency_source_ids: tuple[UUID, ...] = ()
    saving_throw_advantage_modifier_ids: tuple[
        tuple[AbilityName, UUID], ...
    ] = ()
    damage_resistance_modifier_ids: tuple[tuple[str, UUID], ...] = ()
    melee_critical_extra_dice_modifier_ids: tuple[UUID, ...] = ()
    maximum_hit_point_modifier_ids: tuple[UUID, ...] = ()
    walking_speed_modifier_ids: tuple[UUID, ...] = ()
    action_uuids: tuple[UUID, ...] = ()
    darkness_root_owner_action_uuids: tuple[UUID, ...] = ()
    handler_uuids: tuple[UUID, ...] = ()
    resource_contributions: tuple[tuple[str, UUID], ...] = ()
    sense_source_ids: tuple[UUID, ...] = ()
    size_source_ids: tuple[UUID, ...] = ()
    capability_sources: tuple[tuple[OriginCapability, UUID], ...] = ()
    feature_sources: tuple[tuple[str, UUID], ...] = ()
    spell_source_ids: tuple[UUID, ...] = ()
    learned_reaction_spell_sources: tuple[
        tuple[str, UUID, UUID], ...
    ] = ()

    def __post_init__(self) -> None:
        _require_step_id(self.step_id)


@dataclass(frozen=True, slots=True)
class FighterGrantReceipt:
    """Exact owner contributions installed by one Fighter/Champion level."""

    step_id: str
    source_id: UUID
    hit_die_uuids: tuple[UUID, ...] = ()
    skill_proficiency_sources: tuple[tuple[SkillName, UUID], ...] = ()
    saving_throw_proficiency_sources: tuple[
        tuple[SavingThrowName, UUID], ...
    ] = ()
    creature_proficiency_source_ids: tuple[UUID, ...] = ()
    ability_score_modifier_ids: tuple[tuple[AbilityName, UUID], ...] = ()
    ability_check_proficiency_sources: tuple[tuple[AbilityName, UUID], ...] = ()
    ranged_attack_bonus_modifier_ids: tuple[UUID, ...] = ()
    armor_class_bonus_modifier_ids: tuple[UUID, ...] = ()
    melee_damage_bonus_modifier_ids: tuple[UUID, ...] = ()
    off_hand_melee_ability_bonus_modifier_ids: tuple[UUID, ...] = ()
    off_hand_ranged_ability_bonus_modifier_ids: tuple[UUID, ...] = ()
    melee_critical_threshold_modifier_ids: tuple[UUID, ...] = ()
    ranged_critical_threshold_modifier_ids: tuple[UUID, ...] = ()
    jump_distance_additive_modifier_ids: tuple[UUID, ...] = ()
    action_uuids: tuple[UUID, ...] = ()
    handler_uuids: tuple[UUID, ...] = ()
    resource_contributions: tuple[tuple[str, UUID], ...] = ()
    attack_multiplicity_grant_ids: tuple[UUID, ...] = ()
    feature_sources: tuple[tuple[str, UUID], ...] = ()

    def __post_init__(self) -> None:
        _require_step_id(self.step_id)


@dataclass(frozen=True, slots=True)
class BarbarianGrantReceipt:
    """Exact owner contributions installed by one Barbarian/Berserker level."""

    step_id: str
    source_id: UUID
    hit_die_uuids: tuple[UUID, ...] = ()
    skill_proficiency_sources: tuple[tuple[SkillName, UUID], ...] = ()
    saving_throw_proficiency_sources: tuple[
        tuple[SavingThrowName, UUID], ...
    ] = ()
    creature_proficiency_source_ids: tuple[UUID, ...] = ()
    ability_score_modifier_ids: tuple[tuple[AbilityName, UUID], ...] = ()
    dexterity_save_advantage_modifier_ids: tuple[UUID, ...] = ()
    walking_speed_modifier_ids: tuple[UUID, ...] = ()
    initiative_advantage_modifier_ids: tuple[UUID, ...] = ()
    melee_critical_extra_dice_modifier_ids: tuple[UUID, ...] = ()
    action_uuids: tuple[UUID, ...] = ()
    raging_root_owner_action_uuids: tuple[UUID, ...] = ()
    reckless_root_owner_action_uuids: tuple[UUID, ...] = ()
    handler_uuids: tuple[UUID, ...] = ()
    resource_contributions: tuple[tuple[str, UUID], ...] = ()
    armor_class_formula_ids: tuple[UUID, ...] = ()
    attack_multiplicity_grant_ids: tuple[UUID, ...] = ()
    condition_immunity_sources: tuple[tuple[str, UUID], ...] = ()
    feature_sources: tuple[tuple[str, UUID], ...] = ()
    replaced_rage_action_uuid: UUID | None = None
    replaced_rage_action_index: int | None = None
    replaced_rage_damage: int | None = None
    replaced_rage_mindless: bool | None = None
    replaced_rage_persistent: bool | None = None

    def __post_init__(self) -> None:
        _require_step_id(self.step_id)
        replacement = (
            self.replaced_rage_action_uuid,
            self.replaced_rage_action_index,
            self.replaced_rage_damage,
            self.replaced_rage_mindless,
            self.replaced_rage_persistent,
        )
        if any(value is not None for value in replacement) and not all(
            value is not None for value in replacement
        ):
            raise ValueError("Frenzy replacement requires the complete Rage template row")
        if (
            self.replaced_rage_action_index is not None
            and self.replaced_rage_action_index < 0
        ):
            raise ValueError("Frenzy replacement action index cannot be negative")


@dataclass(frozen=True, slots=True)
class SorcererGrantReceipt:
    """Exact owner contributions installed by one Sorcerer/Draconic level."""

    step_id: str
    source_id: UUID
    hit_die_uuids: tuple[UUID, ...] = ()
    skill_proficiency_sources: tuple[tuple[SkillName, UUID], ...] = ()
    saving_throw_proficiency_sources: tuple[
        tuple[SavingThrowName, UUID], ...
    ] = ()
    creature_proficiency_source_ids: tuple[UUID, ...] = ()
    ability_score_modifier_ids: tuple[tuple[AbilityName, UUID], ...] = ()
    maximum_hit_point_modifier_ids: tuple[UUID, ...] = ()
    action_uuids: tuple[UUID, ...] = ()
    metamagic_root_owner_action_uuids: tuple[UUID, ...] = ()
    elemental_affinity_root_owner_action_uuids: tuple[UUID, ...] = ()
    dragon_wings_root_owner_action_uuids: tuple[UUID, ...] = ()
    draconic_presence_root_owner_action_uuids: tuple[UUID, ...] = ()
    handler_uuids: tuple[UUID, ...] = ()
    resource_contributions: tuple[tuple[str, UUID], ...] = ()
    resource_recovery_contributions: tuple[tuple[str, UUID], ...] = ()
    spell_source_ids: tuple[UUID, ...] = ()
    normal_spell_slot_capacity_ids: tuple[UUID, ...] = ()
    learned_reaction_spell_sources: tuple[
        tuple[str, UUID, UUID], ...
    ] = ()
    spell_affinity_contribution_ids: tuple[UUID, ...] = ()
    armor_class_formula_ids: tuple[UUID, ...] = ()
    feature_sources: tuple[tuple[str, UUID], ...] = ()
    replaced_spell_id: str | None = None
    replaced_spell_action_uuid: UUID | None = None
    replaced_spell_action_index: int | None = None
    replaced_reaction_spell_source: tuple[str, UUID, UUID] | None = None
    replaced_reaction_spell_handler_was_enabled: bool | None = None

    def __post_init__(self) -> None:
        _require_step_id(self.step_id)
        action_replacement = (
            self.replaced_spell_id,
            self.replaced_spell_action_uuid,
            self.replaced_spell_action_index,
        )
        if any(value is not None for value in action_replacement) and not all(
            value is not None for value in action_replacement
        ) and self.replaced_reaction_spell_source is None:
            raise ValueError("replaced spell action requires its complete identity row")
        if (
            self.replaced_reaction_spell_source is not None
            and self.replaced_spell_id is None
        ):
            raise ValueError("replaced reaction spell requires its semantic spell ID")
        if (
            self.replaced_spell_action_uuid is not None
            and self.replaced_reaction_spell_source is not None
        ):
            raise ValueError("a replaced spell has one concrete ownership form")
        if (self.replaced_reaction_spell_source is None) != (
            self.replaced_reaction_spell_handler_was_enabled is None
        ):
            raise ValueError(
                "replaced reaction spell requires its exact handler state"
            )
        if (
            self.replaced_spell_action_index is not None
            and self.replaced_spell_action_index < 0
        ):
            raise ValueError("replaced spell action index cannot be negative")


CharacterGrantReceipt = (
    OriginGrantReceipt
    | FighterGrantReceipt
    | BarbarianGrantReceipt
    | SorcererGrantReceipt
)


__all__ = [
    "BarbarianGrantReceipt",
    "CharacterGrantReceipt",
    "FighterGrantReceipt",
    "OriginGrantReceipt",
    "SorcererGrantReceipt",
]
