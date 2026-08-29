"""Committed entity birth and progression facts."""

from typing import ClassVar, Optional
from uuid import UUID

from pydantic import Field

from dnd.core.events.item_events import ItemState
from dnd.core.events.events_registry import Event, EventType
from dnd.types.abilities import AbilityName, SavingThrowName, SkillName
from dnd.types.creatures import (
    Background,
    CreatureType,
    OriginCapability,
    Size,
    Species,
    SpeciesVariant,
)
from dnd.types.damage import DamageType, ResistanceStatus
from dnd.types.life import LifeState
from dnd.types.progression import AppliedClassLevel, AppliedOriginState
from dnd.types.senses import SenseMode


_SpellSourceFact = tuple[
    str,
    str,
    AbilityName,
    int,
    int,
    Optional[str],
    Optional[str],
]
_ArmorFormulaFact = tuple[int, tuple[AbilityName, ...], bool, bool]


class EntityCreatedEvent(Event):
    """Terminal renderer-agnostic fact for one composed entity."""

    inert_terminal_fact: ClassVar[bool] = True

    name: str = Field(default="Entity Created")
    event_type: EventType = Field(default=EventType.ENTITY_CREATED, frozen=True)
    entity_uuid: UUID
    entity_kind_id: str
    entity_name: str
    entity_description: Optional[str] = None
    creature_type: CreatureType
    size: Size
    structural_base_size: Size
    weight: int
    faction: Optional[str] = None
    species: Optional[Species] = None
    species_variant: Optional[SpeciesVariant] = None
    background: Optional[Background] = None
    applied_origin_state: Optional[AppliedOriginState] = None
    applied_class_levels: tuple[AppliedClassLevel, ...] = ()
    ability_scores: tuple[tuple[AbilityName, int], ...] = ()
    skill_proficiencies: tuple[SkillName, ...] = ()
    skill_expertise: tuple[SkillName, ...] = ()
    saving_throw_proficiencies: tuple[SavingThrowName, ...] = ()
    proficiency_bonus: int = 0
    initiative: int = 0
    armor_class: int = Field(default=10, ge=0)
    life_state: LifeState = LifeState.ALIVE
    current_hit_points: int = 0
    maximum_hit_points: int = 0
    temporary_hit_points: int = 0
    damage_taken: int = Field(default=0, ge=0)
    hit_dice: tuple[tuple[int, int, int, str, bool], ...] = ()
    damage_affinities: tuple[tuple[DamageType, ResistanceStatus], ...] = ()
    walking_speed_feet: int = Field(default=0, ge=0)
    swimming_speed_feet: int = Field(default=0, ge=0)
    has_ordinary_sight: bool = True
    sense_modes: tuple[SenseMode, ...] = ()
    requires_breathing: bool = True
    uses_death_saves: bool = False
    death_save_successes: int = Field(default=0, ge=0, le=3)
    death_save_failures: int = Field(default=0, ge=0, le=3)
    origin_capabilities: tuple[OriginCapability, ...] = ()
    body_semantics: tuple[tuple[str, str], ...] = ()
    feature_ids: tuple[str, ...] = ()
    weapon_proficiencies: tuple[str, ...] = ()
    armor_proficiencies: tuple[str, ...] = ()
    shield_proficient: bool = False
    languages: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    action_ids: tuple[str, ...] = ()
    handler_ids: tuple[str, ...] = ()
    condition_ids: tuple[str, ...] = ()
    condition_immunities: tuple[str, ...] = ()
    attacks_per_action: int = Field(default=1, ge=1)
    resources: tuple[tuple[str, int, int, str], ...] = ()
    resource_recoveries: tuple[tuple[str, str, int], ...] = ()
    attack_multiplicity: tuple[tuple[str, int, int], ...] = ()
    spell_sources: tuple[_SpellSourceFact, ...] = ()
    known_spell_ids: tuple[str, ...] = ()
    reaction_spell_ids: tuple[str, ...] = ()
    prepared_spell_ids: tuple[str, ...] = ()
    feature_toggle_ids: tuple[str, ...] = ()
    spell_slots: tuple[tuple[int, int], ...] = ()
    armor_class_formulas: tuple[_ArmorFormulaFact, ...] = ()
    items: tuple[ItemState, ...] = ()
    inventory_item_uuids: tuple[UUID, ...] = ()
    equipment: tuple[tuple[str, UUID], ...] = ()


class EntityLevelAddedEvent(Event):
    """Terminal fact for one successfully applied class-level step."""

    inert_terminal_fact: ClassVar[bool] = True

    name: str = Field(default="Entity Level Added")
    event_type: EventType = Field(default=EventType.ENTITY_LEVEL_ADDED, frozen=True)
    entity_uuid: UUID
    previous_total_level: int
    new_total_level: int
    level: AppliedClassLevel
    resulting_class_levels: tuple[tuple[str, int], ...]
    ability_scores: tuple[tuple[AbilityName, int], ...] = ()
    skill_proficiencies: tuple[SkillName, ...] = ()
    skill_expertise: tuple[SkillName, ...] = ()
    saving_throw_proficiencies: tuple[SavingThrowName, ...] = ()
    proficiency_bonus: int = 0
    armor_class: int = Field(default=10, ge=0)
    current_hit_points: int = 0
    maximum_hit_points: int = 0
    hit_dice: tuple[tuple[int, int, int, str, bool], ...] = ()
    damage_affinities: tuple[tuple[DamageType, ResistanceStatus], ...] = ()
    walking_speed_feet: int = Field(default=0, ge=0)
    swimming_speed_feet: int = Field(default=0, ge=0)
    sense_modes: tuple[SenseMode, ...] = ()
    origin_capabilities: tuple[OriginCapability, ...] = ()
    body_semantics: tuple[tuple[str, str], ...] = ()
    feature_ids: tuple[str, ...] = ()
    weapon_proficiencies: tuple[str, ...] = ()
    armor_proficiencies: tuple[str, ...] = ()
    shield_proficient: bool = False
    languages: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    action_ids: tuple[str, ...] = ()
    handler_ids: tuple[str, ...] = ()
    condition_ids: tuple[str, ...] = ()
    condition_immunities: tuple[str, ...] = ()
    attacks_per_action: int = Field(default=1, ge=1)
    attack_multiplicity: tuple[tuple[str, int, int], ...] = ()
    resources: tuple[tuple[str, int, int, str], ...] = ()
    resource_recoveries: tuple[tuple[str, str, int], ...] = ()
    spell_sources: tuple[_SpellSourceFact, ...] = ()
    known_spell_ids: tuple[str, ...] = ()
    reaction_spell_ids: tuple[str, ...] = ()
    prepared_spell_ids: tuple[str, ...] = ()
    feature_toggle_ids: tuple[str, ...] = ()
    spell_slots: tuple[tuple[int, int], ...] = ()
    armor_class_formulas: tuple[_ArmorFormulaFact, ...] = ()
    items: tuple[ItemState, ...] = ()
    inventory_item_uuids: tuple[UUID, ...] = ()
    equipment: tuple[tuple[str, UUID], ...] = ()


class EntityLevelRemovedEvent(Event):
    """Terminal fact for one successfully removed class-level step."""

    inert_terminal_fact: ClassVar[bool] = True

    name: str = Field(default="Entity Level Removed")
    event_type: EventType = Field(default=EventType.ENTITY_LEVEL_REMOVED, frozen=True)
    entity_uuid: UUID
    previous_total_level: int
    new_total_level: int
    level: AppliedClassLevel
    resulting_class_levels: tuple[tuple[str, int], ...]
    ability_scores: tuple[tuple[AbilityName, int], ...] = ()
    skill_proficiencies: tuple[SkillName, ...] = ()
    skill_expertise: tuple[SkillName, ...] = ()
    saving_throw_proficiencies: tuple[SavingThrowName, ...] = ()
    proficiency_bonus: int = 0
    armor_class: int = Field(default=10, ge=0)
    current_hit_points: int = 0
    maximum_hit_points: int = 0
    hit_dice: tuple[tuple[int, int, int, str, bool], ...] = ()
    damage_affinities: tuple[tuple[DamageType, ResistanceStatus], ...] = ()
    walking_speed_feet: int = Field(default=0, ge=0)
    swimming_speed_feet: int = Field(default=0, ge=0)
    sense_modes: tuple[SenseMode, ...] = ()
    origin_capabilities: tuple[OriginCapability, ...] = ()
    body_semantics: tuple[tuple[str, str], ...] = ()
    feature_ids: tuple[str, ...] = ()
    weapon_proficiencies: tuple[str, ...] = ()
    armor_proficiencies: tuple[str, ...] = ()
    shield_proficient: bool = False
    languages: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    action_ids: tuple[str, ...] = ()
    handler_ids: tuple[str, ...] = ()
    condition_ids: tuple[str, ...] = ()
    condition_immunities: tuple[str, ...] = ()
    attacks_per_action: int = Field(default=1, ge=1)
    attack_multiplicity: tuple[tuple[str, int, int], ...] = ()
    resources: tuple[tuple[str, int, int, str], ...] = ()
    resource_recoveries: tuple[tuple[str, str, int], ...] = ()
    spell_sources: tuple[_SpellSourceFact, ...] = ()
    known_spell_ids: tuple[str, ...] = ()
    reaction_spell_ids: tuple[str, ...] = ()
    prepared_spell_ids: tuple[str, ...] = ()
    feature_toggle_ids: tuple[str, ...] = ()
    spell_slots: tuple[tuple[int, int], ...] = ()
    armor_class_formulas: tuple[_ArmorFormulaFact, ...] = ()
    items: tuple[ItemState, ...] = ()
    inventory_item_uuids: tuple[UUID, ...] = ()
    equipment: tuple[tuple[str, UUID], ...] = ()


__all__ = [
    "EntityCreatedEvent",
    "EntityLevelAddedEvent",
    "EntityLevelRemovedEvent",
]
