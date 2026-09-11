"""Original forced-motion authoring and local cue adaptation remain portable data."""

import json

import pygame

from game.animation_data import DATA_ROOT, load_animation_data


def test_original_forced_context_shove_recipe_and_feedback_survive_loading() -> None:
    data = load_animation_data()
    source = DATA_ROOT / "source/src/render/data/animation"
    contexts = json.loads((source / "actionContextPresentation.json").read_text())["contexts"]
    recipes = json.loads((source / "contentActionPresentationRecipes.json").read_text())["recipes"]
    shove = next(row for row in recipes if row["definitionRef"]["content_id"] == "action.shove")
    assert data.forced_movement_context.model_dump(mode="json") == contexts["forced_movement"]
    assert data.shove_recipes["action.shove"].model_dump(mode="json") == shove
    assert {key: value.model_dump(mode="json") for key, value in data.shove_feedback.items()} == contexts["outcome_feedback"]["shove"]
    assert data.shove_recipes["action.shove"].actor.clip == "Kick"
    assert next(row.frame for row in data.shove_recipes["action.shove"].anchors if row.name == "contact") == 7


def test_studio_cue_literals_are_explicit_local_data_with_source_provenance() -> None:
    data = load_animation_data()
    profile = data.forced_movement_profile
    assert profile.model_dump(mode="json", exclude={"provenance"}) == {
        "duration_ms": 420, "target_clip": "TakeDamage", "brace_frame": 3, "playback_speed": 1,
    }
    provenance = json.loads((DATA_ROOT / "provenance.json").read_text())["neuroclient"]
    assert profile.provenance["source"] == "src/ui/actionStudio/studioSubjectiveActionFrame.ts"
    assert profile.provenance["revision"] == provenance["revision"]
    assert profile.provenance["source_sha256"] == provenance["source_sha256"][profile.provenance["source"]]
    # The original context has scales; these base cue values were never fields
    # in that source JSON and must not be mistaken for native mechanics facts.
    assert "brace_frame" not in data.forced_movement_context.model_dump()


def test_kick_covers_existing_modular_layers_and_fixed_rigs_keep_their_own_clips() -> None:
    rig_files = tuple(sorted((DATA_ROOT.parent / "rigs").glob("*.json")))
    data = load_animation_data(rig_files=rig_files)
    root = data.rigs[data.root_rig]
    kick = root.clips[data.shove_recipes["action.shove"].actor.clip]
    assert set(kick.sheets) == set(root.clips["Run"].sheets)
    for url in kick.sheets.values():
        sheet = pygame.image.load(data.resources[url])
        assert sheet.get_size() == (root.cell_width * kick.frames, root.cell_height * 8)
    body = pygame.image.load(data.resources[kick.sheets["NakedBody"]])
    assert body.get_bounding_rect().width > 0
    for path in rig_files:
        original = json.loads(path.read_text())
        rig = data.rigs[original["rig_id"]]
        assert set(rig.clips) == set(original["rig"]["clips"])
        brace = rig.clips[data.forced_movement_profile.target_clip]
        assert all(data.resources[url].is_file() for url in brace.sheets.values())
