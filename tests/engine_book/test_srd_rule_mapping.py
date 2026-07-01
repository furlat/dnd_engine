"""Checks for the internal SRD-to-manual rule mapping."""

from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / "engine_book" / "srd_rule_mapping.md"
MANUAL_ROOT = Path("/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual")
ALLOWED_RELATIONSHIPS = {
    "source-vocabulary",
    "srd-aligned",
    "engine-adaptation",
    "product-extension",
}
REQUIRED_POLICY_PHRASES = {
    "Forced movement is modeled as `FORCED_MOVEMENT`",
    "Standard Shove is the videogame/BG3-style bonus-action implementation",
    "Equipment uses one melee loadout and one ranged loadout",
    "Advantage/disadvantage is currently accumulated by modifier score",
    "Great Weapon Fighting follows the local class markdown behavior",
    "Encounter ending is a videogame policy based on faction survival",
}


def _frontmatter_rules(chapter_path: Path) -> list[str]:
    text = chapter_path.read_text(encoding="utf-8")
    match = re.search(r"^---\n(?P<frontmatter>.*?)\n---", text, re.DOTALL)
    assert match is not None, f"{chapter_path.name} has no frontmatter."

    rules_match = re.search(
        r'^rules:\s*(?P<rules>\[.*\])$',
        match.group("frontmatter"),
        re.MULTILINE,
    )
    assert rules_match is not None, f"{chapter_path.name} has no rules list."
    rules = ast.literal_eval(rules_match.group("rules"))
    assert isinstance(rules, list)
    return rules


def _mapping_rows() -> list[dict[str, str]]:
    text = MAPPING_PATH.read_text(encoding="utf-8")
    rows: list[dict[str, str]] = []

    for line in text.splitlines():
        if not re.match(r"^\|\s*\d{2}\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 6, f"Malformed mapping row: {line}"
        rows.append(
            {
                "chapter": cells[0],
                "public_chapter": cells[1].strip("`"),
                "touchpoints": cells[2],
                "relationship": cells[3],
                "sources": cells[4],
                "policy": cells[5],
            }
        )

    return rows


def test_srd_rule_mapping_covers_every_public_chapter() -> None:
    """The internal mapping has one row for every public manual chapter."""
    rows = _mapping_rows()
    mapped_chapters = {row["public_chapter"] for row in rows}
    public_chapters = {path.name for path in MANUAL_ROOT.glob("*.mdx")}

    assert mapped_chapters == public_chapters
    assert {row["chapter"] for row in rows} == {
        f"{index:02d}" for index in range(28)
    }


def test_srd_rule_mapping_matches_chapter_rule_touchpoints() -> None:
    """Each mapping row repeats the public chapter's declared rule touchpoints."""
    for row in _mapping_rows():
        chapter_path = MANUAL_ROOT / row["public_chapter"]
        for rule in _frontmatter_rules(chapter_path):
            assert rule in row["touchpoints"], (
                f"{row['public_chapter']} maps rule {rule!r} in frontmatter, "
                f"but not in engine_book/srd_rule_mapping.md."
            )


def test_srd_rule_mapping_sources_exist_and_have_relationship_labels() -> None:
    """Referenced local SRD markdown files must exist and rows use known labels."""
    for row in _mapping_rows():
        assert row["relationship"] in ALLOWED_RELATIONSHIPS
        sources = re.findall(r"`(interactive_ruleset/[^`]+)`", row["sources"])
        assert sources, f"{row['public_chapter']} has no local SRD source paths."

        for source in sources:
            assert (ROOT / source).is_file(), (
                f"{row['public_chapter']} references missing SRD source {source!r}."
            )


def test_srd_rule_mapping_records_current_videogame_policy_points() -> None:
    """Ruleset policy choices that caused confusion stay explicit in the map."""
    text = MAPPING_PATH.read_text(encoding="utf-8")

    for phrase in REQUIRED_POLICY_PHRASES:
        assert phrase in text

    assert "RulesProfile" not in text
    assert "parallel SRD/BG3 profiles" in text
