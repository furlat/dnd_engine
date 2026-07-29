"""Measured official-source coverage ledger contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.inventory import (
    SourceCoverageLedger,
    SourceCoverageRow,
    SourceCoverageSection,
    SourceImplementationStatus,
)


_ITEM_REF = ContentRef(
    pack_id="content.srd_5_1_cc",
    definition_kind=ContentDefinitionKind.ITEM,
    content_id="weapon.club",
    content_version=1,
    definition_contract_hash="a" * 64,
)


def test_source_coverage_rows_keep_missing_work_visible_and_measured() -> None:
    """A missing SRD row is a typed work item rather than an omitted definition."""
    missing = SourceCoverageRow(
        source_entry_id="srd_5_1.creature.archmage",
        section=SourceCoverageSection.CREATURE_STAT_BLOCKS,
        definition_kind=ContentDefinitionKind.CREATURE,
        source_name="Archmage",
        source_anchor="Appendix MM-B / Archmage",
        implementation_status=SourceImplementationStatus.MISSING,
        mechanical_notes="Factory and spell dependency closure are absent.",
        measuring_test_nodeids=(
            "tests/manual/test_155_content_inventory_contracts.py"
            "::test_source_coverage_rows_keep_missing_work_visible_and_measured",
        ),
    )
    ledger = SourceCoverageLedger(
        source_id="wotc.srd_5_1_cc",
        expected_section_counts={
            SourceCoverageSection.CREATURE_STAT_BLOCKS: 1,
        },
        rows=(missing,),
    )

    assert ledger.blocking_entry_ids == (missing.source_entry_id,)
    assert ledger.is_complete is False


def test_complete_source_row_requires_content_ref_and_semantic_test() -> None:
    """Source completion means implemented, attributed, and behavior-tested."""
    complete = SourceCoverageRow(
        source_entry_id="srd_5_1.weapon.club",
        section=SourceCoverageSection.WEAPONS,
        definition_kind=ContentDefinitionKind.ITEM,
        source_name="Club",
        source_anchor="Equipment / Weapons / Club",
        implementation_status=SourceImplementationStatus.COMPLETE,
        content_ref=_ITEM_REF,
        measuring_test_nodeids=(
            "tests/manual/test_155_content_inventory_contracts.py"
            "::test_complete_source_row_requires_content_ref_and_semantic_test",
        ),
    )
    ledger = SourceCoverageLedger(
        source_id="wotc.srd_5_1_cc",
        expected_section_counts={SourceCoverageSection.WEAPONS: 1},
        rows=(complete,),
    )
    assert ledger.is_complete

    invalid = complete.model_dump(mode="json")
    invalid["content_ref"] = None
    with pytest.raises(ValidationError, match="content_ref"):
        SourceCoverageRow.model_validate(invalid)


def test_source_ledger_rejects_count_drift_and_duplicate_entries() -> None:
    """The official-source extraction count is owned by one deterministic ledger."""
    row = SourceCoverageRow(
        source_entry_id="srd_5_1.spell.aid",
        section=SourceCoverageSection.SPELLS,
        definition_kind=ContentDefinitionKind.SPELL,
        source_name="Aid",
        source_anchor="Spells / Aid",
        implementation_status=SourceImplementationStatus.MISSING,
        mechanical_notes="Not yet classified against the current spell map.",
        measuring_test_nodeids=(
            "tests/manual/test_155_content_inventory_contracts.py"
            "::test_source_ledger_rejects_count_drift_and_duplicate_entries",
        ),
    )
    with pytest.raises(ValidationError, match="expected_section_counts"):
        SourceCoverageLedger(
            source_id="wotc.srd_5_1_cc",
            expected_section_counts={SourceCoverageSection.SPELLS: 2},
            rows=(row,),
        )
    with pytest.raises(ValidationError, match="Duplicate source_entry_id"):
        SourceCoverageLedger(
            source_id="wotc.srd_5_1_cc",
            expected_section_counts={SourceCoverageSection.SPELLS: 2},
            rows=(row, row),
        )
