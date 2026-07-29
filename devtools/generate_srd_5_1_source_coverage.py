"""Generate the reviewed SRD 5.1 source-coverage ledger.

The generator reads the official Wizards of the Coast CC-BY-4.0 PDF and pins
its exact SHA-256 before extracting source headings.  It does not copy rules
prose.  Run it with an ephemeral pdfplumber dependency:

    uv run --with pdfplumber python \
      devtools/generate_srd_5_1_source_coverage.py \
      --pdf /path/to/SRD_CC_v5.1.pdf

Official source:
https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import pdfplumber  # type: ignore[import-not-found]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.identities import ContentRef
from dnd.core.content.inventory import (
    SourceCoverageLedger,
    SourceCoverageSection,
    SourceImplementationStatus,
)
from dnd.core.content.provenance import ContentSource
from dnd.items.armors import SRD_ARMOR_DECLARATIONS
from dnd.items.consumables import (
    HASTE_POTION_DECLARATION,
    HASTE_POTION_REF,
    HEALING_POTION_DECLARATION,
    HEALING_POTION_REF,
)
from dnd.items.spell_items import (
    SpellGrantingItem,
    WAND_OF_MAGIC_MISSILES_REF,
)
from dnd.items.weapons import SRD_WEAPON_DECLARATIONS
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
)
from dnd.monsters.circus_fighter_items import (
    LONGSWORD_PLUS_ONE_DECLARATION,
    LONGSWORD_PLUS_ONE_REF,
)
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS,
)
from dnd.spells.catalog_content import (
    SPELL_CONTENT_DECLARATIONS_BY_NAME,
    SPELL_CONTENT_IDENTITY_SPECS,
)
from dnd.spells.reaction_spell_content import (
    LEARNED_REACTION_SPELL_SPECS,
)

ALL_SPELLS = {
    spec.display_name: spec.spell_type
    for spec in SPELL_CONTENT_IDENTITY_SPECS
}
_SRD_WEAPON_REFS_BY_CONTENT_ID = {
    declaration.ref.content_id.removeprefix("weapon."): declaration.ref
    for declaration in SRD_WEAPON_DECLARATIONS
}
_SRD_ARMOR_REFS_BY_CONTENT_ID = {
    declaration.ref.content_id.removeprefix("armor."): declaration.ref
    for declaration in SRD_ARMOR_DECLARATIONS
}

_DEFAULT_OUTPUT = (
    _REPOSITORY_ROOT
    / "content_data"
    / "ledgers"
    / "srd_5_1_source_coverage.json"
)
_SOURCE_CONTRACT_PATH = (
    _REPOSITORY_ROOT
    / "content_data"
    / "sources"
    / "srd_5_1_cc.json"
)
_SOURCE_CONTRACT = ContentSource.model_validate_json(
    _SOURCE_CONTRACT_PATH.read_text(encoding="utf-8"),
)
_MEASURING_NODEID = (
    "tests/manual/test_158_srd_5_1_source_coverage_ledger.py"
    "::test_srd_5_1_ledger_is_exhaustive_and_measured"
)
_SIZE_PREFIXES = (
    "Tiny",
    "Small",
    "Medium",
    "Large",
    "Huge",
    "Gargantuan",
)
_SPELL_SCHOOLS = (
    "abjuration",
    "conjuration",
    "divination",
    "enchantment",
    "evocation",
    "illusion",
    "necromancy",
    "transmutation",
)
_SPELL_LEVELS = (
    "1st",
    "2nd",
    "3rd",
    "4th",
    "5th",
    "6th",
    "7th",
    "8th",
    "9th",
)
_MAGIC_ITEM_CATEGORY = re.compile(
    r"^(?:"
    r"Armor(?:\s+\(|,)|"
    r"Potion,|"
    r"Ring,|"
    r"Rod,|"
    r"Scroll,|"
    r"Staff,|"
    r"Wand,|"
    r"Weapon(?:\s+\(|,)|"
    r"Wondrous item,"
    r")",
)

_WEAPON_NAMES = (
    "Club",
    "Dagger",
    "Greatclub",
    "Handaxe",
    "Javelin",
    "Light hammer",
    "Mace",
    "Quarterstaff",
    "Sickle",
    "Spear",
    "Crossbow, light",
    "Dart",
    "Shortbow",
    "Sling",
    "Battleaxe",
    "Flail",
    "Glaive",
    "Greataxe",
    "Greatsword",
    "Halberd",
    "Lance",
    "Longsword",
    "Maul",
    "Morningstar",
    "Pike",
    "Rapier",
    "Scimitar",
    "Shortsword",
    "Trident",
    "War pick",
    "Warhammer",
    "Whip",
    "Blowgun",
    "Crossbow, hand",
    "Crossbow, heavy",
    "Longbow",
    "Net",
)
_WEAPON_RECIPE_KEYS = {
    "Club": "club",
    "Dagger": "dagger",
    "Handaxe": "handaxe",
    "Javelin": "javelin",
    "Light hammer": "light_hammer",
    "Mace": "mace",
    "Quarterstaff": "quarterstaff",
    "Sickle": "sickle",
    "Spear": "spear",
    "Crossbow, light": "light_crossbow",
    "Dart": "dart",
    "Shortbow": "shortbow",
    "Sling": "sling",
    "Battleaxe": "battleaxe",
    "Greataxe": "greataxe",
    "Greatsword": "greatsword",
    "Longsword": "longsword",
    "Morningstar": "morningstar",
    "Rapier": "rapier",
    "Scimitar": "scimitar",
    "Shortsword": "shortsword",
    "Trident": "trident",
    "Warhammer": "warhammer",
    "Crossbow, heavy": "heavy_crossbow",
    "Longbow": "longbow",
}
_WEAPON_FACTORY_NAMES = {
    source_name: f"_build_{recipe_key}"
    for source_name, recipe_key in _WEAPON_RECIPE_KEYS.items()
}
_ARMOR_NAMES = (
    "Padded",
    "Leather",
    "Studded leather",
    "Hide",
    "Chain shirt",
    "Scale mail",
    "Breastplate",
    "Half plate",
    "Ring mail",
    "Chain mail",
    "Splint",
    "Plate",
    "Shield",
)
_ARMOR_REGISTRY_KEYS = {
    "Padded": "padded",
    "Leather": "leather",
    "Studded leather": "studded_leather",
    "Hide": "hide",
    "Chain shirt": "chain_shirt",
    "Scale mail": "scale_mail",
    "Breastplate": "breastplate",
    "Half plate": "half_plate",
    "Ring mail": "ring_mail",
    "Chain mail": "chain_mail",
    "Splint": "splint",
    "Plate": "plate",
    "Shield": "shield",
}
_ARMOR_LEGACY_FACTORY_NAMES = {
    "Padded": "create_padded_armor",
    "Leather": "create_leather_armor",
    "Studded leather": "create_studded_leather",
    "Hide": "create_hide_armor",
    "Chain shirt": "create_chain_shirt",
    "Scale mail": "create_scale_mail",
    "Breastplate": "create_breastplate",
    "Half plate": "create_half_plate",
    "Ring mail": "create_ring_mail",
    "Chain mail": "create_chain_mail",
    "Splint": "create_splint_armor",
    "Plate": "create_plate_armor",
    "Shield": "create_shield",
}
_LEARNED_REACTION_SPELLS_BY_NAME = {
    spec.display_name: spec
    for spec in LEARNED_REACTION_SPELL_SPECS
}


@dataclass(frozen=True)
class _PdfLine:
    """One reconstructed line in one PDF column."""

    text: str
    height: float


@dataclass(frozen=True)
class _SourceHeading:
    """One source heading extracted from the official PDF."""

    name: str
    page_number: int
    detail: str
    source_group: str


def _clean_source_text(value: str) -> str:
    """Normalize PDF typography without changing source wording."""
    text = value.replace("\N{SOFT HYPHEN}", "")
    text = text.replace("\N{LEFT SINGLE QUOTATION MARK}", "'")
    text = text.replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
    text = text.replace("\N{LEFT DOUBLE QUOTATION MARK}", '"')
    text = text.replace("\N{RIGHT DOUBLE QUOTATION MARK}", '"')
    text = re.sub(r"[-‐‑–—]+", "-", text)
    return " ".join(text.split())


def _slug(value: str) -> str:
    """Return a deterministic lowercase identifier component."""
    normalized = unicodedata.normalize("NFKD", value).casefold()
    parts: list[str] = []
    separator_pending = False
    for character in normalized:
        if character.isascii() and character.isalnum():
            if separator_pending and parts:
                parts.append("_")
            parts.append(character)
            separator_pending = False
        else:
            separator_pending = True
    slug = "".join(parts).strip("_")
    if not slug or not slug[0].isalpha():
        slug = f"entry_{slug}"
    return slug


def _locator(definition: Any) -> str:
    """Return a repository-relative implementation locator."""
    source_file = inspect.getsourcefile(definition)
    if source_file is None:
        raise RuntimeError(f"Cannot locate source for {definition!r}")
    relative_path = Path(source_file).resolve().relative_to(_REPOSITORY_ROOT)
    return f"{relative_path.as_posix()}:{definition.__name__}"


def _column_lines(page: Any) -> tuple[tuple[_PdfLine, ...], ...]:
    """Reconstruct the two source columns from positioned PDF words."""
    columns: dict[int, list[dict[str, Any]]] = {0: [], 1: []}
    for word in page.extract_words():
        columns[0 if word["x0"] < page.width / 2 else 1].append(word)

    result: list[tuple[_PdfLine, ...]] = []
    for column in (0, 1):
        groups: list[tuple[float, list[dict[str, Any]]]] = []
        for word in sorted(
            columns[column],
            key=lambda row: (row["top"], row["x0"]),
        ):
            if groups and abs(groups[-1][0] - word["top"]) < 0.8:
                groups[-1][1].append(word)
            else:
                groups.append((word["top"], [word]))
        lines = []
        for _top, words in groups:
            ordered_words = sorted(words, key=lambda row: row["x0"])
            lines.append(
                _PdfLine(
                    text=_clean_source_text(
                        " ".join(word["text"] for word in ordered_words),
                    ),
                    height=max(float(word["height"]) for word in ordered_words),
                ),
            )
        result.append(tuple(lines))
    return tuple(result)


def _extract_creatures(pdf: Any) -> tuple[_SourceHeading, ...]:
    """Extract the 201 main, 95 miscellaneous, and 21 NPC stat blocks."""
    headings: list[_SourceHeading] = []
    page_indexes = (*range(260, 357), *range(365, 403))
    for page_index in page_indexes:
        page_number = page_index + 1
        for lines in _column_lines(pdf.pages[page_index]):
            for index, line in enumerate(lines[:-1]):
                detail = lines[index + 1].text
                if (
                    line.height >= 11.5
                    and detail.startswith(_SIZE_PREFIXES)
                ):
                    if 366 <= page_number <= 393:
                        source_group = "Appendix MM-A"
                    elif page_number >= 395:
                        source_group = "Appendix MM-B"
                    else:
                        source_group = "Monsters A-Z"
                    headings.append(
                        _SourceHeading(
                            name=line.text,
                            page_number=page_number,
                            detail=detail,
                            source_group=source_group,
                        ),
                    )
    if len(headings) != 317:
        raise RuntimeError(
            f"Expected 317 SRD creature stat blocks, found {len(headings)}",
        )
    return tuple(headings)


def _is_spell_declaration(value: str) -> bool:
    """Whether a PDF line is a spell level/school declaration."""
    normalized = "".join(
        character
        for character in value.casefold()
        if character.isalnum() or character == " "
    )
    if any(
        normalized.startswith(f"{school} cantrip")
        for school in _SPELL_SCHOOLS
    ):
        return True
    return (
        any(
            normalized.startswith(f"{level}level ")
            for level in _SPELL_LEVELS
        )
        and any(f" {school}" in normalized for school in _SPELL_SCHOOLS)
    )


def _extract_spells(pdf: Any) -> tuple[_SourceHeading, ...]:
    """Extract all 319 spell definitions from Spell Descriptions."""
    headings: list[_SourceHeading] = []
    for page_index in range(113, 193):
        page_number = page_index + 1
        for lines in _column_lines(pdf.pages[page_index]):
            for index, line in enumerate(lines[:-1]):
                detail = lines[index + 1].text
                if line.height >= 11.5 and _is_spell_declaration(detail):
                    headings.append(
                        _SourceHeading(
                            name=line.text,
                            page_number=page_number,
                            detail=detail,
                            source_group="Spell Descriptions",
                        ),
                    )
    if len(headings) != 319:
        raise RuntimeError(
            f"Expected 319 SRD spells, found {len(headings)}",
        )
    return tuple(headings)


def _extract_magic_items(pdf: Any) -> tuple[_SourceHeading, ...]:
    """Extract the 239 named entries in Magic Items A-Z."""
    headings: list[_SourceHeading] = []
    for page_index in range(206, 251):
        page_number = page_index + 1
        for lines in _column_lines(pdf.pages[page_index]):
            for index, line in enumerate(lines[:-1]):
                if line.height < 11.5:
                    continue
                if index > 0 and lines[index - 1].height >= 11.5:
                    continue
                name_parts = [line.text]
                detail_index = index + 1
                while (
                    detail_index < len(lines)
                    and lines[detail_index].height >= 11.5
                ):
                    name_parts.append(lines[detail_index].text)
                    detail_index += 1
                if detail_index >= len(lines):
                    continue
                detail = lines[detail_index].text
                if _MAGIC_ITEM_CATEGORY.match(detail):
                    headings.append(
                        _SourceHeading(
                            name=_clean_source_text(" ".join(name_parts)),
                            page_number=page_number,
                            detail=detail,
                            source_group="Magic Items A-Z",
                        ),
                    )
    if len(headings) != 239:
        raise RuntimeError(
            f"Expected 239 named SRD magic items, found {len(headings)}",
        )
    return tuple(headings)


def _row(
    *,
    source_entry_id: str,
    section: SourceCoverageSection,
    definition_kind: ContentDefinitionKind,
    source_name: str,
    source_anchor: str,
    implementation_status: SourceImplementationStatus,
    legacy_locators: Sequence[str] = (),
    content_ref: ContentRef | None = None,
    dependency_refs: Sequence[ContentRef] = (),
    mechanical_notes: str = "",
) -> dict[str, Any]:
    """Build one JSON-ready source row with an authenticated ref when migrated."""
    return {
        "source_entry_id": source_entry_id,
        "section": section.value,
        "definition_kind": definition_kind.value,
        "source_name": source_name,
        "source_anchor": source_anchor,
        "implementation_status": implementation_status.value,
        "legacy_locators": list(legacy_locators),
        "content_ref": (
            content_ref.model_dump(mode="json")
            if content_ref is not None
            else None
        ),
        "dependency_refs": [
            ref.model_dump(mode="json")
            for ref in dependency_refs
        ],
        "mechanical_notes": mechanical_notes,
        "measuring_test_nodeids": [_MEASURING_NODEID],
    }


def _creature_rows(
    headings: Iterable[_SourceHeading],
) -> list[dict[str, Any]]:
    """Build creature rows and conservatively identify current factories."""
    current_factories: dict[str, tuple[Any, ContentRef | None]] = {
        declaration.descriptor.display_name: (
            declaration.construction.factory,
            declaration.ref,
        )
        for declaration in SRD_CREATURE_DECLARATIONS
        if declaration.construction is not None
    }
    current_factories["Goblin"] = (
        create_goblin,
        BESTIARY_CREATURE_DECLARATIONS_BY_ID["goblin"].ref,
    )
    current_factories["Skeleton"] = (
        create_skeleton,
        BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref,
    )

    rows = []
    for heading in headings:
        implementation = current_factories.get(heading.name)
        if implementation is None:
            status = SourceImplementationStatus.MISSING
            locators: tuple[str, ...] = ()
            content_ref = None
            notes = ""
        else:
            factory, content_ref = implementation
            status = SourceImplementationStatus.PLAYABLE
            locators = (_locator(factory),)
            notes = (
                "The current factory builds a live actor with legal actions. "
                "Playable does not claim exhaustive SRD stat-block parity."
            )
        rows.append(
            _row(
                source_entry_id=(
                    f"srd_5_1.creature.{_slug(heading.name)}"
                ),
                section=SourceCoverageSection.CREATURE_STAT_BLOCKS,
                definition_kind=ContentDefinitionKind.CREATURE,
                source_name=heading.name,
                source_anchor=(
                    "SRD 5.1 (CC-BY-4.0), "
                    f"p. {heading.page_number}, {heading.source_group}: "
                    f"{heading.name}"
                ),
                implementation_status=status,
                legacy_locators=locators,
                content_ref=content_ref,
                mechanical_notes=notes,
            ),
        )
    return rows


def _weapon_rows() -> list[dict[str, Any]]:
    """Build the 37-row mundane weapon table ledger."""
    rows = []
    for source_name in _WEAPON_NAMES:
        recipe_key = _WEAPON_RECIPE_KEYS.get(source_name)
        content_ref = (
            _SRD_WEAPON_REFS_BY_CONTENT_ID.get(recipe_key)
            if recipe_key is not None
            else None
        )
        status = (
            SourceImplementationStatus.PLAYABLE
            if content_ref is not None
            else SourceImplementationStatus.MISSING
        )
        legacy_locators = (
            (
                "dnd/items/weapons.py:"
                f"{_WEAPON_FACTORY_NAMES[source_name]}",
            )
            if content_ref is not None
            else ()
        )
        rows.append(
            _row(
                source_entry_id=f"srd_5_1.weapon.{_slug(source_name)}",
                section=SourceCoverageSection.WEAPONS,
                definition_kind=ContentDefinitionKind.ITEM,
                source_name=source_name,
                source_anchor=(
                    "SRD 5.1 (CC-BY-4.0), pp. 65-66, Weapons table: "
                    f"{source_name}"
                ),
                implementation_status=status,
                legacy_locators=legacy_locators,
                content_ref=content_ref,
                mechanical_notes=(
                    "The migrated content definition is usable for attacks; "
                    "playable does not claim complete cost, weight, or "
                    "property parity."
                    if content_ref is not None
                    else ""
                ),
            ),
        )
    return rows


def _armor_rows() -> list[dict[str, Any]]:
    """Build the 12 armor-suit rows and shield row."""
    rows = []
    for source_name in _ARMOR_NAMES:
        content_ref = _SRD_ARMOR_REFS_BY_CONTENT_ID[
            _ARMOR_REGISTRY_KEYS[source_name]
        ]
        rows.append(
            _row(
                source_entry_id=f"srd_5_1.armor.{_slug(source_name)}",
                section=SourceCoverageSection.ARMOR_AND_SHIELDS,
                definition_kind=ContentDefinitionKind.ITEM,
                source_name=source_name,
                source_anchor=(
                    "SRD 5.1 (CC-BY-4.0), pp. 63-64, Armor table: "
                    f"{source_name}"
                ),
                implementation_status=SourceImplementationStatus.PLAYABLE,
                legacy_locators=(
                    "dnd/items/armors.py:"
                    f"{_ARMOR_LEGACY_FACTORY_NAMES[source_name]}",
                ),
                content_ref=content_ref,
                mechanical_notes=(
                    "The migrated definition supports equip and Armor Class "
                    "behavior; playable does not claim complete "
                    "equipment-table parity."
                ),
            ),
        )
    return rows


def _magic_item_rows(
    headings: Iterable[_SourceHeading],
) -> list[dict[str, Any]]:
    """Build magic-item rows with only reviewed legacy correspondences."""
    healing_factory = HEALING_POTION_DECLARATION.construction
    haste_factory = HASTE_POTION_DECLARATION.construction
    if healing_factory is None or haste_factory is None:
        raise RuntimeError("Potion declarations must remain constructible")
    longsword_plus_one_factory = LONGSWORD_PLUS_ONE_DECLARATION.construction
    if longsword_plus_one_factory is None:
        raise RuntimeError("Longsword +1 declaration must remain constructible")
    partial_implementations: dict[
        str,
        tuple[ContentRef | None, Any | None, str],
    ] = {
        "Potion of Healing": (
            HEALING_POTION_REF,
            healing_factory.factory,
            "A consumable healing-potion implementation exists, but its "
            "fixed-healing/default-state contract is not full SRD parity.",
        ),
        "Potion of Speed": (
            HASTE_POTION_REF,
            haste_factory.factory,
            "Potion of Haste implements the main non-concentration Haste "
            "effect under a non-SRD identity; source parity is incomplete.",
        ),
        "Spell Scroll": (
            None,
            SpellGrantingItem,
            "Several exact spell-scroll content definitions reuse the "
            "SpellGrantingItem mechanism; arbitrary SRD scroll coverage is "
            "absent.",
        ),
        "Wand of Magic Missiles": (
            WAND_OF_MAGIC_MISSILES_REF,
            SpellGrantingItem,
            "The wand is usable, but charge count, recharge, multi-charge "
            "casting, and destruction behavior are incomplete.",
        ),
        "Weapon, +1, +2, or +3": (
            LONGSWORD_PLUS_ONE_REF,
            longsword_plus_one_factory.factory,
            "One legacy +1 longsword fixture exists; the generic weapon "
            "family and +2/+3 variants are absent.",
        ),
    }

    rows = []
    for heading in headings:
        partial = partial_implementations.get(heading.name)
        if partial is None:
            status = SourceImplementationStatus.MISSING
            locators: tuple[str, ...] = ()
            content_ref = None
            notes = f"Source category: {heading.detail}."
        else:
            content_ref, definition, parity_note = partial
            status = SourceImplementationStatus.PARTIAL
            locators = (
                (_locator(definition),)
                if definition is not None
                else ()
            )
            notes = f"Source category: {heading.detail}. {parity_note}"
        rows.append(
            _row(
                source_entry_id=(
                    f"srd_5_1.magic_item.{_slug(heading.name)}"
                ),
                section=SourceCoverageSection.MAGIC_ITEMS,
                definition_kind=ContentDefinitionKind.ITEM,
                source_name=heading.name,
                source_anchor=(
                    "SRD 5.1 (CC-BY-4.0), "
                    f"p. {heading.page_number}, Magic Items A-Z: "
                    f"{heading.name}"
                ),
                implementation_status=status,
                legacy_locators=locators,
                content_ref=content_ref,
                mechanical_notes=notes,
            ),
        )
    return rows


def _spell_rows(
    headings: Iterable[_SourceHeading],
) -> list[dict[str, Any]]:
    """Build spell rows and identify exact current catalog names."""
    rows = []
    for heading in headings:
        spell_class = ALL_SPELLS.get(heading.name)
        reaction_spell = _LEARNED_REACTION_SPELLS_BY_NAME.get(heading.name)
        if spell_class is None and reaction_spell is None:
            status = SourceImplementationStatus.MISSING
            locators: tuple[str, ...] = ()
            content_ref = None
            dependency_refs: tuple[ContentRef, ...] = ()
            notes = f"Source declaration: {heading.detail}."
        elif reaction_spell is not None:
            status = SourceImplementationStatus.PLAYABLE
            locators = (_locator(reaction_spell.handler_type),)
            content_ref = reaction_spell.declaration.ref
            dependency_refs = tuple(
                dependency.target_ref
                for dependency in reaction_spell.declaration.dependencies
            )
            notes = (
                f"Source declaration: {heading.detail}. The exact learned "
                "spell root installs its exact playable reaction behavior."
            )
        else:
            assert spell_class is not None
            status = SourceImplementationStatus.PLAYABLE
            locators = (_locator(spell_class),)
            content_ref = SPELL_CONTENT_DECLARATIONS_BY_NAME[
                heading.name
            ].ref
            dependency_refs = ()
            notes = (
                f"Source declaration: {heading.detail}. The spell is in the "
                "live legacy spell catalog; playable does not claim every "
                "edge-case interpretation is complete."
            )
        rows.append(
            _row(
                source_entry_id=f"srd_5_1.spell.{_slug(heading.name)}",
                section=SourceCoverageSection.SPELLS,
                definition_kind=ContentDefinitionKind.SPELL,
                source_name=heading.name,
                source_anchor=(
                    "SRD 5.1 (CC-BY-4.0), "
                    f"p. {heading.page_number}, Spell Descriptions: "
                    f"{heading.name}"
                ),
                implementation_status=status,
                legacy_locators=locators,
                content_ref=content_ref,
                dependency_refs=dependency_refs,
                mechanical_notes=notes,
            ),
        )
    return rows


def _current_migrated_content_refs(
) -> dict[tuple[SourceCoverageSection, str], ContentRef]:
    """Return exact current refs for source rows already migrated to content."""
    refs = {
        (
            SourceCoverageSection.CREATURE_STAT_BLOCKS,
            declaration.descriptor.display_name,
        ): declaration.ref
        for declaration in SRD_CREATURE_DECLARATIONS
    }
    refs.update({
        (
            SourceCoverageSection.CREATURE_STAT_BLOCKS,
            source_name,
        ): BESTIARY_CREATURE_DECLARATIONS_BY_ID[creature_id].ref
        for source_name, creature_id in (
            ("Goblin", "goblin"),
            ("Skeleton", "skeleton"),
        )
    })
    refs.update({
        (
            SourceCoverageSection.WEAPONS,
            source_name,
        ): _SRD_WEAPON_REFS_BY_CONTENT_ID[recipe_key]
        for source_name, recipe_key in _WEAPON_RECIPE_KEYS.items()
    })
    refs.update({
        (
            SourceCoverageSection.ARMOR_AND_SHIELDS,
            source_name,
        ): _SRD_ARMOR_REFS_BY_CONTENT_ID[registry_key]
        for source_name, registry_key in _ARMOR_REGISTRY_KEYS.items()
    })
    refs.update({
        (SourceCoverageSection.MAGIC_ITEMS, source_name): ref
        for source_name, ref in (
            ("Potion of Healing", HEALING_POTION_REF),
            ("Potion of Speed", HASTE_POTION_REF),
            ("Wand of Magic Missiles", WAND_OF_MAGIC_MISSILES_REF),
            ("Weapon, +1, +2, or +3", LONGSWORD_PLUS_ONE_REF),
        )
    })
    refs.update({
        (
            SourceCoverageSection.SPELLS,
            display_name,
        ): declaration.ref
        for display_name, declaration
        in SPELL_CONTENT_DECLARATIONS_BY_NAME.items()
        if declaration.ref.pack_id == "content.srd_5_1_cc"
    })
    refs.update({
        (
            SourceCoverageSection.SPELLS,
            spec.display_name,
        ): spec.declaration.ref
        for spec in LEARNED_REACTION_SPELL_SPECS
    })
    return refs


def _refresh_content_refs(
    ledger: SourceCoverageLedger,
) -> SourceCoverageLedger:
    """Refresh authenticated refs without re-extracting the pinned source PDF."""
    refs = _current_migrated_content_refs()
    payload = ledger.model_dump(mode="json")
    for row in payload["rows"]:
        key = (
            SourceCoverageSection(row["section"]),
            row["source_name"],
        )
        ref = refs.get(key)
        row["content_ref"] = (
            ref.model_dump(mode="json")
            if ref is not None
            else None
        )
        weapon_recipe_key = (
            _WEAPON_RECIPE_KEYS.get(row["source_name"])
            if row["section"] == SourceCoverageSection.WEAPONS.value
            else None
        )
        if weapon_recipe_key is not None:
            row["implementation_status"] = (
                SourceImplementationStatus.PLAYABLE.value
            )
            row["legacy_locators"] = [
                f"dnd/items/weapons.py:_build_{weapon_recipe_key}",
            ]
            row["mechanical_notes"] = (
                "The migrated content definition is usable for attacks; "
                "playable does not claim complete cost, weight, or property "
                "parity."
            )
        reaction_spell = (
            _LEARNED_REACTION_SPELLS_BY_NAME.get(row["source_name"])
            if row["section"] == SourceCoverageSection.SPELLS.value
            else None
        )
        if reaction_spell is not None:
            source_declaration = row["mechanical_notes"].partition(".")[0]
            row["implementation_status"] = (
                SourceImplementationStatus.PLAYABLE.value
            )
            row["legacy_locators"] = [
                _locator(reaction_spell.handler_type),
            ]
            row["content_ref"] = (
                reaction_spell.declaration.ref.model_dump(mode="json")
            )
            row["dependency_refs"] = [
                dependency.target_ref.model_dump(mode="json")
                for dependency in reaction_spell.declaration.dependencies
            ]
            row["mechanical_notes"] = (
                f"{source_declaration}. The exact learned spell root installs "
                "its exact playable reaction behavior."
            )
    return SourceCoverageLedger.model_validate(payload)


def _build_ledger(pdf_path: Path) -> SourceCoverageLedger:
    """Extract, classify, and validate the complete ledger."""
    actual_digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if actual_digest != _SOURCE_CONTRACT.document_digest:
        raise RuntimeError(
            "SRD PDF SHA-256 mismatch: expected "
            f"{_SOURCE_CONTRACT.document_digest}, found {actual_digest}",
        )

    with pdfplumber.open(pdf_path) as pdf:
        creature_headings = _extract_creatures(pdf)
        magic_item_headings = _extract_magic_items(pdf)
        spell_headings = _extract_spells(pdf)

    rows = [
        *_creature_rows(creature_headings),
        *_weapon_rows(),
        *_armor_rows(),
        *_magic_item_rows(magic_item_headings),
        *_spell_rows(spell_headings),
    ]
    payload = {
        "schema_version": 1,
        "source_id": "wotc.srd_5_1_cc",
        "expected_section_counts": {
            SourceCoverageSection.CREATURE_STAT_BLOCKS.value: 317,
            SourceCoverageSection.WEAPONS.value: 37,
            SourceCoverageSection.ARMOR_AND_SHIELDS.value: 13,
            SourceCoverageSection.MAGIC_ITEMS.value: 239,
            SourceCoverageSection.SPELLS.value: 319,
        },
        "rows": rows,
    }
    return SourceCoverageLedger.model_validate(payload)


def _render(ledger: SourceCoverageLedger) -> str:
    """Render deterministic checked-in JSON."""
    return json.dumps(
        ledger.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def main() -> None:
    """Generate or verify the checked-in SRD source ledger."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pdf",
        type=Path,
        required=False,
        help="Path to the official SRD_CC_v5.1.pdf.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Ledger destination.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the checked-in ledger differs from generated output.",
    )
    parser.add_argument(
        "--refresh-content-refs",
        action="store_true",
        help=(
            "Refresh authenticated refs in the checked-in extracted ledger "
            "without re-reading the unchanged pinned PDF."
        ),
    )
    arguments = parser.parse_args()

    output_path = arguments.output.resolve()
    if arguments.refresh_content_refs:
        if not output_path.exists():
            raise SystemExit(
                f"{output_path} does not exist; a PDF extraction is required",
            )
        ledger = _refresh_content_refs(
            SourceCoverageLedger.model_validate_json(
                output_path.read_text(encoding="utf-8"),
            ),
        )
    else:
        if arguments.pdf is None:
            parser.error(
                "--pdf is required unless --refresh-content-refs is used",
            )
        ledger = _build_ledger(arguments.pdf.resolve())
    rendered = _render(ledger)
    if arguments.check:
        if not output_path.exists() or output_path.read_text(
            encoding="utf-8",
        ) != rendered:
            raise SystemExit(
                f"{output_path} is stale; regenerate the SRD 5.1 ledger",
            )
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
