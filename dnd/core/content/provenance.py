"""Rules-source, license, and review provenance for content definitions."""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.identities import (
    validate_namespaced_id,
    validate_sha256,
)


class ContentSourceFamily(str, Enum):
    """Authored source families kept separate from runtime effect origin."""

    SRD_5_1_CC = "srd_5_1_cc"
    SRD_5_2_1_CC = "srd_5_2_1_cc"
    NEURODRAGON_ORIGINAL = "neurodragon_original"
    THIRD_PARTY_OPEN = "third_party_open"
    FIXTURE_INTERNAL = "fixture_internal"
    PROVENANCE_UNVERIFIED = "provenance_unverified"


class RulesBaseline(str, Enum):
    """Rules language and mechanics baseline used by a source."""

    RULES_2014 = "2014"
    RULES_2024 = "2024"
    ENGINE_NEUTRAL = "engine_neutral"


class ContentProvenanceRelation(str, Enum):
    """How an implementation relates to its cited source."""

    FAITHFUL_IMPLEMENTATION = "faithful_implementation"
    COMPATIBLE_ADAPTATION = "compatible_adaptation"
    DERIVED_CONTENT = "derived_content"
    ORIGINAL_CONTENT = "original_content"


class ContentFidelity(str, Enum):
    """Current mechanical fidelity of one implementation."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class ContentReviewStatus(str, Enum):
    """Whether source and mechanical classification were reviewed."""

    REVIEWED = "reviewed"
    UNREVIEWED = "unreviewed"


class ContentSource(BaseModel):
    """One exact rules/licensing source available to a content pack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    source_family: ContentSourceFamily
    title: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    rules_baseline: RulesBaseline
    license_id: str = Field(min_length=1)
    canonical_uri: str = Field(min_length=1)
    document_digest: str
    attribution_text: str = Field(min_length=1)
    notices: tuple[str, ...] = ()

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "source_id")

    @field_validator("document_digest")
    @classmethod
    def _validate_document_digest(cls, value: str) -> str:
        return validate_sha256(value, "document_digest")

    @model_validator(mode="after")
    def _validate_srd_baseline(self) -> Self:
        if (
            self.source_family == ContentSourceFamily.SRD_5_1_CC
            and self.rules_baseline != RulesBaseline.RULES_2014
        ):
            raise ValueError("SRD 5.1 content must use the 2014 rules baseline")
        if (
            self.source_family == ContentSourceFamily.SRD_5_2_1_CC
            and self.rules_baseline != RulesBaseline.RULES_2024
        ):
            raise ValueError("SRD 5.2.1 content must use the 2024 rules baseline")
        return self


class ContentProvenance(BaseModel):
    """Source relationship and review state for one content definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_source_id: str
    source_anchor: str = Field(min_length=1)
    relation: ContentProvenanceRelation
    fidelity: ContentFidelity
    review_status: ContentReviewStatus
    adapted_from_source_id: str | None = None
    notes: str = ""

    @field_validator("primary_source_id", "adapted_from_source_id")
    @classmethod
    def _validate_source_ref(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, info.field_name)

    @model_validator(mode="after")
    def _validate_adaptation_source(self) -> Self:
        if (
            self.relation == ContentProvenanceRelation.COMPATIBLE_ADAPTATION
            and self.adapted_from_source_id is None
        ):
            raise ValueError(
                "compatible adaptations must declare adapted_from_source_id",
            )
        return self
