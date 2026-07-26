"""Stable identities for authored content definitions."""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


_NAMESPACED_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ContentDefinitionKind(str, Enum):
    """Kinds of independently identifiable content definitions."""

    ITEM = "item"
    CREATURE = "creature"
    ACTION = "action"
    SPELL = "spell"
    CONDITION = "condition"
    TRAIT = "trait"
    REACTION = "reaction"
    FEAT = "feat"
    CLASS_FEATURE = "class_feature"
    ENVIRONMENT_OBJECT = "environment_object"
    RULE_PRIMITIVE = "rule_primitive"


def validate_namespaced_id(value: str, field_name: str) -> str:
    """Validate and return one lowercase dotted authored identifier."""
    if not _NAMESPACED_ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a lowercase dotted identifier; got {value!r}",
        )
    return value


def validate_sha256(value: str, field_name: str) -> str:
    """Validate and return one lowercase SHA-256 digest."""
    if not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return value


class ContentRef(BaseModel):
    """Immutable identity and authenticated contract for one definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: str = Field(description="Namespaced identity of the owning pack.")
    definition_kind: ContentDefinitionKind
    content_id: str = Field(description="Namespaced identity within the pack.")
    content_version: int = Field(ge=1)
    definition_contract_hash: str = Field(
        description=(
            "SHA-256 of the definition mode, kind, and typed contract."
        ),
    )

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "pack_id")

    @field_validator("content_id")
    @classmethod
    def _validate_content_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "content_id")

    @field_validator("definition_contract_hash")
    @classmethod
    def _validate_contract_hash(cls, value: str) -> str:
        return validate_sha256(value, "definition_contract_hash")

    @property
    def identity_key(self) -> str:
        """Return the contract-independent registry identity."""
        return (
            f"{self.pack_id}:{self.definition_kind.value}:"
            f"{self.content_id}@{self.content_version}"
        )
