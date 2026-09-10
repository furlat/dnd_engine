"""Offline presentation artifacts preserve authored values and selected media.

These checks require neither NeuroClient nor Bun. Playback timing belongs to
the next cut; copying a recipe does not prove its execution.
"""

from hashlib import sha256
import json
from pathlib import Path

import pygame

from dnd.content_system.spell_catalog_composition import SPELL_CATALOG_COMPOSITION_BY_ID


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "game/data/neuroclient"
SOURCE = DATA / "source"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_local_outputs_match_provenance_and_copied_sources() -> None:
    provenance = read_json(DATA / "provenance.json")
    source_hashes = provenance["neuroclient"]["source_sha256"]
    for relative_path, expected in provenance["outputs"].items():
        assert sha256((ROOT / relative_path).read_bytes()).hexdigest() == expected
    for path in SOURCE.rglob("*.json"):
        assert sha256(path.read_bytes()).hexdigest() == source_hashes[path.relative_to(SOURCE).as_posix()]
    for url, local_path in read_json(DATA / "bindings.json")["resources"].items():
        assert sha256((ROOT / local_path).read_bytes()).hexdigest() == source_hashes["public" + url]


def test_saved_recipes_survive_materialization_including_disabled_tracks() -> None:
    saved = read_json(SOURCE / "public/studio/spell-studio-drafts.json")
    exported = read_json(DATA / "spell-studio-drafts.materialized.json")
    assert (exported["schema"], exported["version"]) == (saved["schema"], saved["version"])
    by_id = {row["definitionRef"]["content_id"]: row for row in exported["spells"]}

    for original in saved["spells"]:
        materialized = by_id[original["definitionRef"]["content_id"]]
        for field, value in original.items():
            if field == "cast":
                # The source merge fills omitted cast defaults. Every authored
                # cast field, including disabled effects/recovery, stays exact.
                for cast_field, cast_value in value.items():
                    assert materialized["cast"][cast_field] == cast_value
            else:
                assert materialized[field] == value

    fire = by_id["spell.fire_bolt"]
    assert fire["cast"]["actionClip"] == "Attack5"
    assert fire["cast"]["releaseFrame"] == 7
    assert fire["projectile"]["sprite"]["mediaFailurePolicy"] == "fail_transaction"
    assert fire["cast"]["effects"][0]["enabled"] is False
    assert fire["cast"]["recovery"]["enabled"] is False


def test_catalog_snapshot_and_bindings_match_the_current_content_owner() -> None:
    catalog = read_json(DATA / "catalog-input.json")
    bindings = read_json(DATA / "bindings.json")
    assert bindings["root_rig"] == "neuroclient.modular"
    assert set(bindings["spells"]) == {
        "spell.fire_bolt", "spell.acid_splash", "spell.magic_missile",
    }
    for captured in catalog:
        row = SPELL_CATALOG_COMPOSITION_BY_ID[captured["metadata"]["catalog_id"]]
        ref = row.declaration.ref.model_dump(mode="json")
        assert captured == {
            "name": row.display_name,
            "school": row.school,
            "level": row.level,
            "source": row.declaration.provenance.primary_source_id,
            "contentRef": ref,
            "metadata": row.metadata.model_dump(mode="json"),
        }
        assert bindings["spells"][ref["content_id"]] == ref


def test_missing_authored_values_use_the_original_generated_profile() -> None:
    profile = read_json(SOURCE / "src/render/data/animation/generatedSpellPresentationProfile.json")
    drafts = read_json(DATA / "spell-studio-drafts.materialized.json")["spells"]
    by_id = {row["definitionRef"]["content_id"]: row for row in drafts}
    assert by_id["spell.fire_bolt"]["cast"]["bodyPlaybackSpeed"] == profile["cast"]["bodyPlaybackSpeed"]

    # Magic Missile has no saved Studio override: it exercises actual generated
    # input alongside the two exact authored spells, using the same data format.
    missile = by_id["spell.magic_missile"]
    assert missile["cast"]["actionClip"] == profile["cast"]["bodyClip"]
    assert missile["cast"]["releaseFrame"] == profile["cast"]["releaseFrame"]
    assert missile["cast"]["recovery"] == profile["cast"]["recovery"]
    assert missile["condition"] == profile["condition"]
    assert missile["projectile"]["geometry"] == {
        "renderer": "geometry_projectile", "enabled": True, "primitive": "dart",
    }


def test_selected_root_and_fire_bolt_media_can_be_decoded_locally() -> None:
    bindings = read_json(DATA / "bindings.json")
    rig = read_json(DATA / "rig-tables.json")
    assets = read_json(SOURCE / "public/studio/spell-projectile-assets.json")
    drafts = read_json(DATA / "spell-studio-drafts.materialized.json")["spells"]
    fire = next(row for row in drafts if row["definitionRef"]["content_id"] == "spell.fire_bolt")
    by_id = {asset["assetId"]: asset for asset in assets}
    sizes = {
        url: pygame.image.load(ROOT / local_path).get_size()
        for url, local_path in bindings["resources"].items()
    }
    assert rig["AUTHORED_PROJECTILE_ROW_ORDER"] == sorted(rig["FACING_ROW"], key=rig["FACING_ROW"].get)
    assert "Magic2" in rig["SLOT_CATEGORIES"]["weaponGlow"]
    assert rig["CELL_H"] - rig["RIG_ORIGIN_Y_FROM_GROUND"] == 87

    for category in ("NakedBody", "Head22", "Head15", "Chest14", "Legs1", "Belt2", "Shoes1", "Shadow", "Melee1", "Melee3",
                     "Legs7", "Shoes2", "Chest7", "Belt1", "Shield5", "Melee2", "Head2", "Head10", "Head13", "Ranged1"):
        for clip in ("Idle", "Attack1", "Attack2", "Attack3", "Attack4", "Attack5", "Attack6", "TakeDamage", "Die", "Taunt", "Special1", "Run", "Rolling"):
            assert sizes[f"/spritesheets/{category}/{clip}.png"] == (
                rig["SHEET_COLS"] * rig["CELL_W"], len(rig["FACING_ROW"]) * rig["CELL_H"],
            )
    assert sizes["/spritesheets/Magic2/Attack5.png"] == sizes["/spritesheets/NakedBody/Attack5.png"]

    projectile = fire["projectile"]
    for track in (projectile["sprite"], projectile["prepare"], projectile["travel"], projectile["impact"]):
        asset = by_id[track["assetId"]]
        frame = asset["frame"]
        assert sizes[asset["sheet"]] == (frame["cols"] * frame["width"], frame["rows"] * frame["height"])
        assert asset["rowOrder"] == rig["AUTHORED_PROJECTILE_ROW_ORDER"]
        for phase in asset["phases"].values():
            assert 0 <= phase["start"] < phase["start"] + phase["frames"] <= frame["cols"]
