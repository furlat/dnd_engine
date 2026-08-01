"""Typed dependency edges between authored content definitions."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from dnd.core.content.identities import ContentRef


class ContentDependencyRelation(str, Enum):
    """Supported semantic relationships in a content behavior closure."""

    GRANTS_ACTION = "grants_action"
    GRANTS_SPELL = "grants_spell"
    GRANTS_FEATURE = "grants_feature"
    OFFERS_SUBCLASS = "offers_subclass"
    OFFERS_STARTING_EQUIPMENT = "offers_starting_equipment"
    HAS_SPECIES_VARIANT = "has_species_variant"
    APPLIES_CONDITION = "applies_condition"
    INSTALLS_HANDLER = "installs_handler"
    CREATES_ZONE = "creates_zone"
    CREATES_SPATIAL_EFFECT = "creates_spatial_effect"
    TRANSFORMS_TO_SPATIAL_EFFECT = "transforms_to_spatial_effect"
    CREATES_OBJECT = "creates_object"
    CREATES_ITEM = "creates_item"
    EQUIPS_ITEM = "equips_item"
    CONFIGURES_CREATURE = "configures_creature"
    SUMMONS_CREATURE = "summons_creature"
    REQUIRES_PRIMITIVE = "requires_primitive"


class ContentDependencyPhase(str, Enum):
    """Whether an edge participates in materialization-cycle validation."""

    CONSTRUCTION = "construction"
    RUNTIME_REFERENCE = "runtime_reference"


class ContentDependency(BaseModel):
    """One validated edge in a definition's transitive behavior closure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation: ContentDependencyRelation
    target_ref: ContentRef
    required: bool = True
    phase: ContentDependencyPhase = ContentDependencyPhase.RUNTIME_REFERENCE
    notes: str = ""
