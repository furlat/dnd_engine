"""Typed dependency edges between authored content definitions."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from dnd.core.content.identities import ContentRef


class ContentDependencyRelation(str, Enum):
    """Supported semantic relationships in a content behavior closure."""

    GRANTS_ACTION = "grants_action"
    GRANTS_SPELL = "grants_spell"
    APPLIES_CONDITION = "applies_condition"
    INSTALLS_HANDLER = "installs_handler"
    CREATES_ZONE = "creates_zone"
    CREATES_OBJECT = "creates_object"
    CREATES_ITEM = "creates_item"
    EQUIPS_ITEM = "equips_item"
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
