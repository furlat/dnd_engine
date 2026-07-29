"""Checked-in official-source coverage ledger contracts."""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
    validate_namespaced_id,
)


class SourceCoverageSection(str, Enum):
    """Reviewed sections in the SRD 5.1 source coverage ledger."""

    CREATURE_STAT_BLOCKS = "creature_stat_blocks"
    WEAPONS = "weapons"
    ARMOR_AND_SHIELDS = "armor_and_shields"
    MAGIC_ITEMS = "magic_items"
    SPELLS = "spells"
    OTHER_EQUIPMENT = "other_equipment"


class SourceImplementationStatus(str, Enum):
    """Mechanical implementation state of one official-source row."""

    CATALOGUED = "catalogued"
    MISSING = "missing"
    PARTIAL = "partial"
    PLAYABLE = "playable"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    FIXTURE_ONLY = "fixture_only"


class SourceCoverageRow(BaseModel):
    """One source definition and its measured implementation state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_entry_id: str
    section: SourceCoverageSection
    definition_kind: ContentDefinitionKind
    source_name: str = Field(min_length=1)
    source_anchor: str = Field(min_length=1)
    implementation_status: SourceImplementationStatus
    legacy_locators: tuple[str, ...] = ()
    content_ref: ContentRef | None = None
    dependency_refs: tuple[ContentRef, ...] = ()
    mechanical_notes: str = ""
    measuring_test_nodeids: tuple[str, ...] = Field(min_length=1)

    @field_validator("source_entry_id")
    @classmethod
    def _validate_entry_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "source_entry_id")

    @field_validator("measuring_test_nodeids")
    @classmethod
    def _validate_test_nodeids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(not nodeid.strip() for nodeid in value):
            raise ValueError("measuring_test_nodeids cannot contain empty rows")
        if len(set(value)) != len(value):
            raise ValueError("measuring_test_nodeids cannot contain duplicates")
        return value

    @field_validator("legacy_locators")
    @classmethod
    def _validate_legacy_locators(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(not locator.strip() for locator in value):
            raise ValueError("legacy_locators cannot contain empty rows")
        if len(set(value)) != len(value):
            raise ValueError("legacy_locators cannot contain duplicates")
        return value

    @model_validator(mode="after")
    def _validate_implementation_state(self) -> Self:
        if (
            self.implementation_status == SourceImplementationStatus.COMPLETE
            and self.content_ref is None
        ):
            raise ValueError(
                "complete rows require content_ref",
            )
        if (
            self.implementation_status
            in {
                SourceImplementationStatus.PARTIAL,
                SourceImplementationStatus.PLAYABLE,
            }
            and self.content_ref is None
            and not self.legacy_locators
        ):
            raise ValueError(
                f"{self.implementation_status.value} rows require content_ref "
                "or legacy_locators",
            )
        if (
            self.content_ref is not None
            and self.content_ref.definition_kind != self.definition_kind
        ):
            raise ValueError(
                "content_ref definition kind must match definition_kind",
            )
        if self.implementation_status == SourceImplementationStatus.NOT_APPLICABLE:
            if self.content_ref is not None:
                raise ValueError("not_applicable rows cannot have content_ref")
            if not self.mechanical_notes.strip():
                raise ValueError(
                    "not_applicable rows require a reviewed mechanical reason",
                )
        return self


class SourceCoverageLedger(BaseModel):
    """Complete reviewed row set for one exact official source document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1, ge=1)
    source_id: str
    expected_section_counts: dict[SourceCoverageSection, int]
    rows: tuple[SourceCoverageRow, ...]

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "source_id")

    @field_validator("expected_section_counts")
    @classmethod
    def _validate_expected_counts(
        cls,
        value: dict[SourceCoverageSection, int],
    ) -> dict[SourceCoverageSection, int]:
        if not value:
            raise ValueError("expected_section_counts cannot be empty")
        if any(count < 0 for count in value.values()):
            raise ValueError("expected_section_counts cannot be negative")
        return value

    @model_validator(mode="after")
    def _validate_complete_row_set(self) -> Self:
        seen: set[str] = set()
        duplicates: set[str] = set()
        actual_counts = {
            section: 0
            for section in self.expected_section_counts
        }
        unexpected_sections: set[SourceCoverageSection] = set()
        for row in self.rows:
            if row.source_entry_id in seen:
                duplicates.add(row.source_entry_id)
            seen.add(row.source_entry_id)
            if row.section not in actual_counts:
                unexpected_sections.add(row.section)
            else:
                actual_counts[row.section] += 1
        if duplicates:
            raise ValueError(
                "Duplicate source_entry_id rows: "
                + ", ".join(sorted(duplicates)),
            )
        if unexpected_sections:
            raise ValueError(
                "Rows use sections absent from expected_section_counts: "
                + ", ".join(
                    section.value for section in sorted(
                        unexpected_sections,
                        key=lambda item: item.value,
                    )
                ),
            )
        mismatches = [
            f"{section.value}: expected {expected}, found {actual_counts[section]}"
            for section, expected in sorted(
                self.expected_section_counts.items(),
                key=lambda item: item[0].value,
            )
            if actual_counts[section] != expected
        ]
        if mismatches:
            raise ValueError(
                "expected_section_counts do not match ledger rows: "
                + "; ".join(mismatches),
            )
        return self

    @property
    def blocking_entry_ids(self) -> tuple[str, ...]:
        """Return rows that prevent full agreed-source completion."""
        terminal = {
            SourceImplementationStatus.COMPLETE,
            SourceImplementationStatus.NOT_APPLICABLE,
            SourceImplementationStatus.FIXTURE_ONLY,
        }
        return tuple(
            sorted(
                row.source_entry_id
                for row in self.rows
                if row.implementation_status not in terminal
            ),
        )

    @property
    def is_complete(self) -> bool:
        """Whether every row is complete or deliberately non-runtime."""
        return not self.blocking_entry_ids
