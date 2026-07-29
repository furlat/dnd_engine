"""Official SRD 5.1 source-ledger and current-implementation coverage gate."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.inventory import (
    SourceCoverageLedger,
    SourceCoverageSection,
    SourceImplementationStatus,
)
from dnd.core.content.provenance import ContentSource
from dnd.items.armors import SRD_ARMOR_RECIPES_BY_LEGACY_ID
from dnd.items.consumables import HASTE_POTION_REF, HEALING_POTION_REF
from dnd.items.spell_items import WAND_OF_MAGIC_MISSILES_REF
from dnd.items.weapons import SRD_WEAPON_RECIPES_BY_CONTENT_ID
from dnd.monsters.srd_roster import SRD_CREATURE_DECLARATIONS
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
)
from dnd.monsters.circus_fighter_items import LONGSWORD_PLUS_ONE_REF
from tests.spell_test_exports import ALL_SPELLS, SPELL_CONTENT_DECLARATIONS_BY_NAME
from dnd.spells.reaction_spell_content import (
    LEARNED_REACTION_SPELL_SPECS,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_LEDGER_PATH = (
    _REPOSITORY_ROOT
    / "content_data"
    / "ledgers"
    / "srd_5_1_source_coverage.json"
)
_SOURCE_PATH = (
    _REPOSITORY_ROOT
    / "content_data"
    / "sources"
    / "srd_5_1_cc.json"
)
_MEASURING_NODEID = (
    "tests/manual/test_158_srd_5_1_source_coverage_ledger.py"
    "::test_srd_5_1_ledger_is_exhaustive_and_measured"
)
_EXPECTED_COUNTS = {
    SourceCoverageSection.CREATURE_STAT_BLOCKS: 317,
    SourceCoverageSection.WEAPONS: 37,
    SourceCoverageSection.ARMOR_AND_SHIELDS: 13,
    SourceCoverageSection.MAGIC_ITEMS: 239,
    SourceCoverageSection.SPELLS: 319,
}
_EXPECTED_KINDS = {
    SourceCoverageSection.CREATURE_STAT_BLOCKS:
        ContentDefinitionKind.CREATURE,
    SourceCoverageSection.WEAPONS: ContentDefinitionKind.ITEM,
    SourceCoverageSection.ARMOR_AND_SHIELDS: ContentDefinitionKind.ITEM,
    SourceCoverageSection.MAGIC_ITEMS: ContentDefinitionKind.ITEM,
    SourceCoverageSection.SPELLS: ContentDefinitionKind.SPELL,
}
_LEARNED_REACTION_SPELLS_BY_NAME = {
    spec.display_name: spec
    for spec in LEARNED_REACTION_SPELL_SPECS
}
_WEAPON_SOURCE_NAMES = {
    "club": "Club",
    "dagger": "Dagger",
    "handaxe": "Handaxe",
    "javelin": "Javelin",
    "light_hammer": "Light hammer",
    "mace": "Mace",
    "quarterstaff": "Quarterstaff",
    "sickle": "Sickle",
    "spear": "Spear",
    "light_crossbow": "Crossbow, light",
    "dart": "Dart",
    "shortbow": "Shortbow",
    "sling": "Sling",
    "battleaxe": "Battleaxe",
    "greataxe": "Greataxe",
    "greatsword": "Greatsword",
    "longsword": "Longsword",
    "morningstar": "Morningstar",
    "rapier": "Rapier",
    "scimitar": "Scimitar",
    "shortsword": "Shortsword",
    "trident": "Trident",
    "warhammer": "Warhammer",
    "longbow": "Longbow",
    "heavy_crossbow": "Crossbow, heavy",
}
_ARMOR_SOURCE_NAMES = {
    "padded": "Padded",
    "leather": "Leather",
    "studded_leather": "Studded leather",
    "hide": "Hide",
    "chain_shirt": "Chain shirt",
    "scale_mail": "Scale mail",
    "breastplate": "Breastplate",
    "half_plate": "Half plate",
    "ring_mail": "Ring mail",
    "chain_mail": "Chain mail",
    "splint": "Splint",
    "plate": "Plate",
    "shield": "Shield",
}
_MIGRATED_SOURCE_REFS = {
    **{
        (SourceCoverageSection.WEAPONS, _WEAPON_SOURCE_NAMES[legacy_id]):
            recipe.ref
        for legacy_id, recipe in SRD_WEAPON_RECIPES_BY_CONTENT_ID.items()
    },
    **{
        (
            SourceCoverageSection.ARMOR_AND_SHIELDS,
            _ARMOR_SOURCE_NAMES[legacy_id],
        ): recipe.ref
        for legacy_id, recipe in SRD_ARMOR_RECIPES_BY_LEGACY_ID.items()
    },
    **{
        (
            SourceCoverageSection.CREATURE_STAT_BLOCKS,
            declaration.descriptor.display_name,
        ): declaration.ref
        for declaration in SRD_CREATURE_DECLARATIONS
    },
    **{
        (
            SourceCoverageSection.CREATURE_STAT_BLOCKS,
            source_name,
        ): BESTIARY_CREATURE_DECLARATIONS_BY_ID[creature_id].ref
        for source_name, creature_id in (
            ("Goblin", "goblin"),
            ("Skeleton", "skeleton"),
        )
    },
    (
        SourceCoverageSection.MAGIC_ITEMS,
        "Potion of Healing",
    ): HEALING_POTION_REF,
    (
        SourceCoverageSection.MAGIC_ITEMS,
        "Potion of Speed",
    ): HASTE_POTION_REF,
    (
        SourceCoverageSection.MAGIC_ITEMS,
        "Wand of Magic Missiles",
    ): WAND_OF_MAGIC_MISSILES_REF,
    (
        SourceCoverageSection.MAGIC_ITEMS,
        "Weapon, +1, +2, or +3",
    ): LONGSWORD_PLUS_ONE_REF,
    **{
        (
            SourceCoverageSection.SPELLS,
            spell_name,
        ): declaration.ref
        for spell_name, declaration
        in SPELL_CONTENT_DECLARATIONS_BY_NAME.items()
        if declaration.ref.pack_id == "content.srd_5_1_cc"
    },
    **{
        (
            SourceCoverageSection.SPELLS,
            spec.display_name,
        ): spec.declaration.ref
        for spec in LEARNED_REACTION_SPELL_SPECS
    },
}


def _load_ledger() -> SourceCoverageLedger:
    """Load the checked-in ledger through its strict Pydantic contract."""
    return SourceCoverageLedger.model_validate(
        json.loads(_LEDGER_PATH.read_text(encoding="utf-8")),
    )


def _load_source() -> ContentSource:
    """Load the exact official source and licensing contract."""
    return ContentSource.model_validate(
        json.loads(_SOURCE_PATH.read_text(encoding="utf-8")),
    )


def test_srd_5_1_ledger_is_exhaustive_and_measured() -> None:
    """Every reviewed source row must have an anchor and deterministic gate."""
    ledger = _load_ledger()
    source = _load_source()

    assert ledger.source_id == "wotc.srd_5_1_cc"
    assert source.source_id == ledger.source_id
    assert source.document_digest == (
        "2504d2a0abb0a4d491a939be4f17910a2dde0312570ab8d208080225ccf0a1f0"
    )
    assert source.license_id == "CC-BY-4.0"
    assert source.canonical_uri == (
        "https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf"
    )
    assert ledger.expected_section_counts == _EXPECTED_COUNTS
    assert len(ledger.rows) == sum(_EXPECTED_COUNTS.values()) == 925
    assert Counter(row.section for row in ledger.rows) == _EXPECTED_COUNTS

    for row in ledger.rows:
        assert row.definition_kind == _EXPECTED_KINDS[row.section]
        assert row.source_anchor.startswith("SRD 5.1 (CC-BY-4.0), ")
        assert row.measuring_test_nodeids == (_MEASURING_NODEID,)
        assert row.content_ref == _MIGRATED_SOURCE_REFS.get(
            (row.section, row.source_name),
        )
        if row.implementation_status == SourceImplementationStatus.MISSING:
            assert row.legacy_locators == ()
        else:
            assert row.implementation_status in {
                SourceImplementationStatus.PARTIAL,
                SourceImplementationStatus.PLAYABLE,
            }
            assert row.legacy_locators
            assert row.mechanical_notes


def test_srd_5_1_ledger_tracks_every_current_legacy_root_honestly() -> None:
    """The ledger must follow additions to current SRD-facing registries."""
    ledger = _load_ledger()
    rows_by_section_and_name = {
        (row.section, row.source_name): row
        for row in ledger.rows
    }

    tracked_monsters = {
        row.source_name
        for row in ledger.rows
        if row.section == SourceCoverageSection.CREATURE_STAT_BLOCKS
        and row.implementation_status == SourceImplementationStatus.PLAYABLE
    }
    assert tracked_monsters == {
        *(
            declaration.descriptor.display_name
            for declaration in SRD_CREATURE_DECLARATIONS
        ),
        "Goblin",
        "Skeleton",
    }
    for declaration in SRD_CREATURE_DECLARATIONS:
        row = rows_by_section_and_name[
            (
                SourceCoverageSection.CREATURE_STAT_BLOCKS,
                declaration.descriptor.display_name,
            )
        ]
        assert row.content_ref == declaration.ref
    for source_name, creature_id in (
        ("Goblin", "goblin"),
        ("Skeleton", "skeleton"),
    ):
        row = rows_by_section_and_name[
            (SourceCoverageSection.CREATURE_STAT_BLOCKS, source_name)
        ]
        assert (
            row.content_ref
            == BESTIARY_CREATURE_DECLARATIONS_BY_ID[creature_id].ref
        )

    official_spell_names = {
        row.source_name
        for row in ledger.rows
        if row.section == SourceCoverageSection.SPELLS
    }
    assert set(ALL_SPELLS) - official_spell_names == {"Necrotic Bless"}
    for spell_name in set(ALL_SPELLS) & official_spell_names:
        row = rows_by_section_and_name[
            (SourceCoverageSection.SPELLS, spell_name)
        ]
        assert row.implementation_status == SourceImplementationStatus.PLAYABLE
        assert row.legacy_locators
        assert (
            row.content_ref
            == SPELL_CONTENT_DECLARATIONS_BY_NAME[spell_name].ref
        )
    for source_name, spec in _LEARNED_REACTION_SPELLS_BY_NAME.items():
        row = rows_by_section_and_name[
            (SourceCoverageSection.SPELLS, source_name)
        ]
        assert row.implementation_status is SourceImplementationStatus.PLAYABLE
        assert row.content_ref == spec.declaration.ref
        assert row.dependency_refs == tuple(
            dependency.target_ref
            for dependency in spec.declaration.dependencies
        )

    tracked_weapon_rows = {
        row.source_name: row
        for row in ledger.rows
        if row.section == SourceCoverageSection.WEAPONS
        and row.implementation_status == SourceImplementationStatus.PLAYABLE
    }
    assert set(tracked_weapon_rows) == set(_WEAPON_SOURCE_NAMES.values())
    for legacy_id, source_name in _WEAPON_SOURCE_NAMES.items():
        row = tracked_weapon_rows[source_name]
        assert row.content_ref == (
            SRD_WEAPON_RECIPES_BY_CONTENT_ID[legacy_id].ref
        )
        assert row.legacy_locators == (
            f"dnd/items/weapons.py:_build_{legacy_id}",
        )

    tracked_armor_rows = {
        row.source_name: row
        for row in ledger.rows
        if row.section == SourceCoverageSection.ARMOR_AND_SHIELDS
    }
    assert set(tracked_armor_rows) == set(_ARMOR_SOURCE_NAMES.values())
    for legacy_id, source_name in _ARMOR_SOURCE_NAMES.items():
        assert tracked_armor_rows[source_name].content_ref == (
            SRD_ARMOR_RECIPES_BY_LEGACY_ID[legacy_id].ref
        )

    assert Counter(
        row.implementation_status
        for row in ledger.rows
        if row.section == SourceCoverageSection.CREATURE_STAT_BLOCKS
    ) == {
        SourceImplementationStatus.PLAYABLE: 29,
        SourceImplementationStatus.MISSING: 288,
    }
    assert Counter(
        row.implementation_status
        for row in ledger.rows
        if row.section == SourceCoverageSection.WEAPONS
    ) == {
        SourceImplementationStatus.PLAYABLE: 25,
        SourceImplementationStatus.MISSING: 12,
    }
    assert Counter(
        row.implementation_status
        for row in ledger.rows
        if row.section == SourceCoverageSection.ARMOR_AND_SHIELDS
    ) == {
        SourceImplementationStatus.PLAYABLE: 13,
    }
    assert Counter(
        row.implementation_status
        for row in ledger.rows
        if row.section == SourceCoverageSection.MAGIC_ITEMS
    ) == {
        SourceImplementationStatus.PARTIAL: 5,
        SourceImplementationStatus.MISSING: 234,
    }
    assert Counter(
        row.implementation_status
        for row in ledger.rows
        if row.section == SourceCoverageSection.SPELLS
    ) == {
        SourceImplementationStatus.PLAYABLE: 110,
        SourceImplementationStatus.MISSING: 209,
    }

    learned_reaction_rows = {
        row.source_name: row
        for row in ledger.rows
        if (
            row.section == SourceCoverageSection.SPELLS
            and row.source_name in _LEARNED_REACTION_SPELLS_BY_NAME
        )
    }
    assert set(learned_reaction_rows) == set(
        _LEARNED_REACTION_SPELLS_BY_NAME,
    )
    for source_name, spec in _LEARNED_REACTION_SPELLS_BY_NAME.items():
        row = learned_reaction_rows[source_name]
        assert row.content_ref == spec.declaration.ref
        assert row.dependency_refs == tuple(
            dependency.target_ref
            for dependency in spec.declaration.dependencies
        )
        assert row.legacy_locators
        assert "exact playable reaction behavior" in row.mechanical_notes
