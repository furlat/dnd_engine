"""Support media packaging preserves exports and complete conditional attachments."""

import json
from pathlib import Path
from uuid import uuid4

import pygame
import pytest

from devtools.import_support_media import WEAPON_CHARGE_SHEETS, import_bundle
from dnd.core.condition_types import ConditionCategory
from game.actor_facts import ConditionFact
from game.animation_data import load_animation_data
from game.condition_animation import resolve_condition_appearance
from game.condition_types import load_condition_recipes


def test_selected_support_reimport_preserves_media_registration_and_authored_owners(tmp_path: Path):
    source, repo = tmp_path / "source", tmp_path / "repo"
    folder = repo / "game/data/support_spells"
    folder.mkdir(parents=True)
    recipe = b'{"independently authored behavior":true}\n'
    for path in (folder / "spell-studio-drafts.json", folder / "true-strike-draft.json",
                 repo / "game/data/condition-recipes.json"):
        path.write_bytes(recipe)
    bindings = {"resources": {"other": "unchanged.png"}, "spells": {"spell.guidance": "authored"},
                "projectileStorage": {"other": {"keep": True}}}
    (folder / "bindings.json").write_text(json.dumps(bindings))
    (folder / "projectile-assets.json").write_text('[{"assetId":"other","keep":true}]')
    (repo / "game/data/assets.json").write_text('{"schema_version":1,"resources":{"other":{"keep":true}}}')
    (repo / "game/data/condition-media.json").write_text(
        json.dumps({"schema": "dnd.conditionLayerMedia", "version": 1, "layers": {
            "other": {"keep": True}, "support.guidance.front": {
                "category": "guidance", "animation": "static", "scale": .37,
                "world_basis": "SE", "removal_fade_ms": 765, "sustain_start_ms": 123}}}))
    directions = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
    copied: dict[str, bytes] = {}

    def png(name: str, columns: int = 1) -> str:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        surface = pygame.Surface((8 * columns, 8), pygame.SRCALPHA)
        for frame in range(columns):
            surface.fill((19 + frame, 51, 9, 73 + frame), (frame * 8 + 1, 2, 3, 4))
        pygame.image.save(surface, path)
        copied[name] = path.read_bytes()
        return name

    phases = {}
    poses = {}
    for depth in ("back", "front"):
        pages = [{"file": png(f"guidance/{depth}/0.png", 2), "firstFrame": 0, "frameCount": 2, "columns": 2},
                 {"file": png(f"guidance/{depth}/1.png"), "firstFrame": 2, "frameCount": 1, "columns": 1}]
        phases[depth] = {"cell": 8, "pivot": [3, 5], "frames": 3, "fps": 144,
                         "pages": {facing: pages for facing in directions}}
        poses[depth] = {facing: png(f"conditions/guidance/{depth}/{facing}.png") for facing in directions}
    glow = png("actors/guidance/Attack5-glow.png")
    for sheet in WEAPON_CHARGE_SHEETS:
        png(f"weapon-charge/{sheet}")
    spell = {"id": "guidance", "directions": directions, "phases": phases,
             "palette": {"colors": [[19, 51, 9], [20, 51, 9]]}, "cast": {"sourceLayer": glow},
             "conditionPose": {"cell": 8, "pivot": [3, 5], "layers": poses}}
    (source / "manifest.json").write_text(json.dumps({"spells": [spell,
        {"id": "true_strike", "cast": {"sourceLayer": "forbidden-donor.png"}},
        {"id": "not_selected", "phases": {"missing": "not imported"}}]}))

    import_bundle(source, repo=repo)
    import_bundle(source, repo=repo)

    for path in (folder / "spell-studio-drafts.json", folder / "true-strike-draft.json",
                 repo / "game/data/condition-recipes.json"):
        assert path.read_bytes() == recipe
    for name, original in copied.items():
        assert (repo / "game/assets/support_spells" / name).read_bytes() == original
    imported = json.loads((folder / "bindings.json").read_text())
    assert imported["spells"] == bindings["spells"]
    assert imported["resources"]["other"] == "unchanged.png"
    assert imported["projectileStorage"]["other"] == {"keep": True}
    assert set(imported["resources"]) == {"other", "/support-spells/guidance/cast.png",
        *(f"/support-spells/true_strike/{sheet}" for sheet in WEAPON_CHARGE_SHEETS)}
    assets = {row["assetId"]: row for row in json.loads((folder / "projectile-assets.json").read_text())}
    assert assets["other"] == {"assetId": "other", "keep": True}
    for depth in ("back", "front"):
        identity = f"support.guidance.{depth}"
        asset = assets[identity]
        assert asset["frame"] == {"width": 8, "height": 8, "rows": 8, "cols": 3}
        assert asset["rowOrder"] == directions and asset["fps"] == 144
        assert asset["phases"]["impact"] == {"start": 0, "frames": 3, "fps": 144, "loop": False}
        assert asset["anchorsByFacing"] == {facing: {"x": 3 / 8, "y": 5 / 8} for facing in directions}
        assert asset["palettePreview"]["colors"] == [0x133309, 0x143309]
        layer, = imported["projectileStorage"][identity]["phases"]["impact"]["layers"]
        assert layer["blendMode"] == "normal"
        for facing in directions:
            assert [page["firstFrame"] for page in layer["pages"][facing]] == [0, 2]
            assert [page["frameCount"] for page in layer["pages"][facing]] == [2, 1]
    resources = json.loads((repo / "game/data/assets.json").read_text())["resources"]
    assert resources["other"] == {"keep": True}
    assert resources["support.guidance.back.E"] == {
        "path": "support_spells/conditions/guidance/back/E.png", "native_size": [8, 8], "pivot": [3, 5], "scale": 1}
    layers = json.loads((repo / "game/data/condition-media.json").read_text())["layers"]
    assert layers["other"] == {"keep": True}
    assert layers["support.guidance.front"]["images_by_facing"] == {
        facing: f"support.guidance.front.{facing}" for facing in directions}
    assert {key: layers['support.guidance.front'][key] for key in
            ('scale', 'world_basis', 'removal_fade_ms', 'sustain_start_ms')} == {
                'scale': .37, 'world_basis': 'SE', 'removal_fade_ms': 765, 'sustain_start_ms': 123}


def test_support_recipes_retain_duration_ground_registration_and_no_damage():
    data = load_animation_data()
    expected = {"cure_wounds": (3000, 256, 500), "healing_word": (3000, 256, 500),
                "prayer_of_healing": (3000, 384, 500), "guidance": (2000, 256, 1000 / 6),
                "resistance": (2000, 256, 1000 / 6), "shield_of_faith": (4000, 384, 2000 / 3),
                "light": (2000, 256, 0), "thaumaturgy": (1000, 256, 0)}
    for name, (duration_ms, cell, contact_ms) in expected.items():
        recipe = data.drafts[f"spell.{name}"]
        assert recipe.damage is None and recipe.projectile is None and recipe.area is None
        assert recipe.contact is not None and recipe.contact.delayMs == 0
        assert recipe.cast.weaponGlow is not None
        assert recipe.cast.weaponGlow.sourceSheet == f"/support-spells/{name}/cast.png"
        assert recipe.cast.weaponGlow.sourceSheet in data.resources
        assert len(recipe.media) == 2
        for track, depth in zip(recipe.media, ("behind_body", "front_body"), strict=True):
            assert track.depth == depth and track.scale == .5 and track.fps == 32
            assert track.attachment == ("source_ground" if name == "thaumaturgy" else "target_ground")
            assert track.startOffsetMs + contact_ms == pytest.approx(0)
            assert track.durationMs == duration_ms
            asset = data.projectile_assets[track.assetId]
            assert asset.phases.impact is not None
            assert asset.phases.impact.frames * 1000 / track.fps == duration_ms
            assert (asset.frame.width, asset.frame.height) == (cell, cell)
            assert asset.anchor.x * cell == cell / 2
            assert asset.anchor.y * cell == pytest.approx(cell / 2 + 36.95041723)


def test_four_condition_visuals_keep_both_halves_with_concentration_and_independent_removal():
    data = load_animation_data()
    names = ("guidance", "resistance", "shield_of_faith", "light")
    members = tuple(ConditionFact(uuid4(), uuid4(), name, ConditionCategory.STATUS,
        f"condition.spell.{name}", None, None) for name in names)
    concentrating = ConditionFact(uuid4(), uuid4(), "Concentrating", ConditionCategory.STATUS,
        "condition.concentrating", None, None)
    for removed in (None, *members):
        retained = tuple(member for member in members if member is not removed)
        appearance = resolve_condition_appearance((*retained, concentrating), data.condition_recipes, data.condition_media)
        expected = {f"support.{member.name}.{depth}" for member in retained for depth in ("back", "front")}
        assert {resolved.layer.assetId for resolved in appearance.layers} == expected
        assert not appearance.unsupported and appearance.alpha == 1 and appearance.body_color is None
        assert all(resolved.layer.drawOrder == ("behind_body" if resolved.layer.id.endswith("back") else "in_front_of_body")
                   for resolved in appearance.layers)
    duplicate = ConditionFact(uuid4(), uuid4(), "guidance", ConditionCategory.STATUS,
        "condition.spell.guidance", None, None)
    appearance = resolve_condition_appearance((*members, duplicate), data.condition_recipes, data.condition_media)
    assert len(appearance.layers) == 8


def test_local_condition_replacement_is_complete_and_requires_same_native_definition(tmp_path: Path):
    original = Path("game/data/neuroclient/source/src/render/data/animation/conditionPresentation.json")
    local = json.loads(Path("game/data/condition-recipes.json").read_text())
    guidance = next(row for row in local["recipes"] if row["definitionRef"]["content_id"] == "condition.spell.guidance")
    replacement = tmp_path / "conditions.json"
    replacement.write_text(json.dumps({**local, "recipes": [guidance]}))
    recipes = load_condition_recipes(original, local=replacement)
    assert recipes["condition.spell.guidance"].model_dump(mode="json", exclude_unset=True) == guidance
    unchanged = load_condition_recipes(original)
    assert recipes["condition.invisible"] == unchanged["condition.invisible"]
    guidance["definitionRef"]["content_version"] += 1
    replacement.write_text(json.dumps({**local, "recipes": [guidance]}))
    with pytest.raises(ValueError, match="definitionRef disagrees"):
        load_condition_recipes(original, local=replacement)
