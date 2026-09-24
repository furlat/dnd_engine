"""Offline presentation artifacts preserve authored values and selected media.

These checks require neither NeuroClient nor Bun. Playback timing belongs to
the next cut; copying a recipe does not prove its execution.
"""

import json
from pathlib import Path

import pygame

from dnd.content_system.spell_catalog_composition import SPELL_CATALOG_COMPOSITION_BY_ID
from game.animation_data import load_animation_data


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "game/data/neuroclient"
SOURCE = DATA / "source"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
    drafts = read_json(DATA / "spell-studio-drafts.materialized.json")["spells"]
    assert bindings["root_rig"] == "neuroclient.modular"
    authored_refs = {row["definitionRef"]["content_id"]: row["definitionRef"] for row in drafts}
    catalog_refs = {row["contentRef"]["content_id"]: row["contentRef"] for row in catalog}
    assert bindings["spells"] == authored_refs == catalog_refs
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
    selected = load_animation_data()
    rig = read_json(DATA / "rig-tables.json")
    fire = selected.drafts["spell.fire_bolt"]
    assert rig["AUTHORED_PROJECTILE_ROW_ORDER"] == sorted(rig["FACING_ROW"], key=rig["FACING_ROW"].get)
    assert "Magic2" in rig["SLOT_CATEGORIES"]["weaponGlow"]
    assert rig["CELL_H"] - rig["RIG_ORIGIN_Y_FROM_GROUND"] == 87

    for category in ("NakedBody", "Head22", "Head15", "Chest14", "Legs1", "Belt2", "Shoes1", "Shadow", "Melee1", "Melee3",
                     "Legs7", "Shoes2", "Chest7", "Belt1", "Shield5", "Melee2", "Head2", "Head10", "Head13", "Ranged1"):
        for clip in ("Idle", "Attack1", "Attack2", "Attack3", "Attack4", "Attack5", "Attack6", "TakeDamage", "Die", "Taunt", "Special1", "Run", "Rolling"):
            path = selected.resources[f"/spritesheets/{category}/{clip}.png"]
            assert pygame.image.load(path).get_size() == (
                rig["SHEET_COLS"] * rig["CELL_W"], len(rig["FACING_ROW"]) * rig["CELL_H"],
            )
    # The original uncolored Magic2 overlay is source-only; current Fire Bolt
    # selects its authored palette sheet. Historical bindings need no media IO.
    glow = fire.cast.weaponGlow
    assert glow is not None and glow.enabled and not glow.hidden
    assert glow.sourceSheet is not None
    assert pygame.image.load(selected.resources[glow.sourceSheet]).get_size() == (
        rig["SHEET_COLS"] * rig["CELL_W"], len(rig["FACING_ROW"]) * rig["CELL_H"],
    )

    projectile = fire.projectile
    assert projectile.sprite is not None
    for track in (projectile.sprite, projectile.prepare, projectile.travel, projectile.impact):
        asset = selected.projectile_assets[track.assetId]
        frame = asset.frame
        assert pygame.image.load(selected.resources[asset.sheet]).get_size() == (
            frame.cols * frame.width, frame.rows * frame.height,
        )
        assert list(asset.rowOrder) == rig["AUTHORED_PROJECTILE_ROW_ORDER"]
        for phase in (asset.phases.cast, asset.phases.travel, asset.phases.impact):
            assert phase is not None
            assert 0 <= phase.start < phase.start + phase.frames <= frame.cols
