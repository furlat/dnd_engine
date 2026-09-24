"""Replacing delivered media preserves authored behavior and selected colors."""

import json
from dataclasses import replace
from pathlib import Path
import shutil

import pygame
import pytest

from devtools.bake_spell_palettes import bake_palettes, DEFAULT_DRAFTS
from devtools.import_ice_spells import import_bundle as import_ice
from devtools.import_spell_recovery import import_bundle as import_recovery
from devtools.media_delivery import owns_selected_media
from game.animation_data import load_animation_data
from game.animation_types import StudioDraftFile


REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("components", (False, True))
@pytest.mark.parametrize("root,expected", (("game/assets/packed", False), ("game/assets/source", True)))
def test_reimport_selection_reads_archive_addresses_without_opening_payloads(components, root, expected):
    address = {"archive": {"file": root + "/impact.zip", "memberPattern": "{direction}/{frame}.gz"}}
    packet = {"componentsByFacing": {"E": [address]}} if components else address
    storage = {"spell": {"phases": {"impact": {"surfaceFrames": packet}}}}
    assert owns_selected_media(storage, "spell", "game/assets/source") is expected


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def copy_bundle(repo, name):
    destination = repo / 'game/data' / name
    destination.mkdir(parents=True)
    for filename in ('bindings.json', 'projectile-assets.json', 'spell-studio-drafts.json'):
        shutil.copyfile(REPO / 'game/data' / name / filename, destination / filename)
    return destination


def test_reimport_keeps_tuned_recipes_resources_and_selected_color_revision(tmp_path):
    repo, source = tmp_path / 'repo', tmp_path / 'source'
    data = copy_bundle(repo, 'spell_recovery')
    recipe_path = data / 'spell-studio-drafts.json'
    recipes = json.loads(recipe_path.read_text())
    recipes['spells'][0]['projectile']['speedPxPerSecond'] = 777
    write_json(recipe_path, recipes)
    authored = recipe_path.read_bytes()
    bindings_before = json.loads((data / 'bindings.json').read_text())
    assets = json.loads((data / 'projectile-assets.json').read_text())
    extra_asset = {**assets[0], 'assetId': 'another.authored.media.selection'}
    write_json(data / 'projectile-assets.json', [*assets, extra_asset])
    phase = {'start': 0, 'frames': 1, 'fps': 24, 'loop': True}
    rows = []
    for name in ('acid_splash', 'guiding_bolt', 'eldritch_blast'):
        rows.append({'id': name, 'cell': 256, 'rows': ['E'], 'phases': {'travel': phase}})
        path = source / 'spell-recovery/release' / name / 'travel/E/00.png'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'original delivered frame')
    write_json(source / 'spell-recovery/release/manifest.json', rows)
    fire_id = next(a['assetId'] for a in assets if 'fireball' in a['assetId'] and not a['assetId'].endswith('.travel'))
    fire_phase = {'frames': 1, 'fps': 24, 'loop': False, 'cell': 256}
    write_json(source / 'library-selection/release/shared-fireball-20ft.json',
               {'assetId': fire_id, 'rowOrder': ['E'], 'travel': fire_phase, 'impact': fire_phase})
    for name in ('fireball_b', 'fireball_smoke', 'fireball_explosion'):
        path = source / 'library-selection/release' / name / 'E/00.png'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'original delivered frame')
    magic = source / 'public/spritesheets/Magic3/Special1.png'
    magic.parent.mkdir(parents=True)
    magic.write_bytes(b'original isolated sheet')
    revision = source / 'color-revision'
    revised_path = Path('game/assets/spell_recovery/fireball_b/E/00.png')
    frame = revision / 'media' / revised_path
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b'approved revised frame')
    write_json(revision / 'delivery.json', {'assetRoot': 'media', 'media': [{'path': revised_path.as_posix()}]})
    write_json(revision / 'palettes.json', {s: {'revised': [[100, 40, 20]]} for s in ('eldritch_blast', 'fireball')})

    import_recovery(source, source, revision, repo=repo)

    assert recipe_path.read_bytes() == authored
    bindings_after = json.loads((data / 'bindings.json').read_text())
    assert bindings_after['resources'] == bindings_before['resources']
    assert bindings_after['spells'] == bindings_before['spells']
    assert (repo / revised_path).read_bytes() == b'approved revised frame'
    assert extra_asset in json.loads((data / 'projectile-assets.json').read_text())
    assert bindings_after['projectileStorage'][fire_id] == bindings_before['projectileStorage'][fire_id]
    before_fire = next(row for row in assets if row['assetId'] == fire_id)
    after_fire = next(row for row in json.loads((data / 'projectile-assets.json').read_text())
                      if row['assetId'] == fire_id)
    assert after_fire == before_fire, 'The older color delivery cannot replace selected XYZ registration'
    assert bindings_after['projectileStorage'][fire_id + '.travel']['phases']['travel']['layers'][0]['blendMode'] == 'add'
    import_recovery(source, source, revision, repo=repo)
    assert json.loads((data / 'bindings.json').read_text()) == bindings_after


def test_ice_page_reimport_keeps_authored_body_contact_and_child_burst(tmp_path):
    repo, source = tmp_path / 'repo', tmp_path / 'source'
    data = copy_bundle(repo, 'ice_spells')
    copy_bundle(repo, 'spell_recovery')
    authored = (data / 'spell-studio-drafts.json').read_bytes()
    source.mkdir()
    (source / 'page.png').write_bytes(b'delivered page')
    (source / 'source-hand-noise.png').write_bytes(b'delivered noise')
    phase = {'frames': 1, 'blend': 'normal', 'directions': {
        'E': [{'file': 'page.png', 'firstFrame': 0, 'frameCount': 1, 'columns': 1}]}}
    write_json(source / 'manifest.json', {'spells': [{
        'id': 'ice_knife', 'cell': 512, 'directions': ['E'], 'palette': {'colors': [[50, 100, 200]]},
        'registration': {'travel': {'E': [250, 200]}},
        'phases': {'travel': phase, 'impact': {'cell': 999, 'frames': 999}}}]})
    selected = json.loads((data / 'bindings.json').read_text())['projectileStorage']['ice.v8.ice_knife.impact']
    selected_asset = next(row for row in json.loads((data / 'projectile-assets.json').read_text())
                          if row['assetId'] == 'ice.v8.ice_knife.impact')

    import_ice(source, repo=repo)

    assert (data / 'spell-studio-drafts.json').read_bytes() == authored
    assert 'spell.ice_knife.burst' in json.loads(authored)['effectDrafts']
    assert (repo / 'game/assets/ice_spells/page.png').read_bytes() == b'delivered page'
    asset = next(row for row in json.loads((data / 'projectile-assets.json').read_text())
                 if row['assetId'] == 'ice.v8.ice_knife.travel')
    assert asset['anchorsByFacing']['E'] == {'x': 250 / 512, 'y': 200 / 512}
    assert json.loads((data / 'bindings.json').read_text())['projectileStorage']['ice.v8.ice_knife.impact'] == selected
    assert next(row for row in json.loads((data / 'projectile-assets.json').read_text())
                if row['assetId'] == 'ice.v8.ice_knife.impact') == selected_asset


@pytest.mark.parametrize('draft_path', DEFAULT_DRAFTS, ids=lambda path: path.parent.name)
def test_rebake_uses_explicit_originals_and_preserves_palette_alpha_geometry_and_authoring(tmp_path, monkeypatch, draft_path):
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        original = draft_path.read_bytes()
        data = load_animation_data()
        draft = StudioDraftFile.model_validate_json(original)
        archive, installed, output_root = (tmp_path / name for name in ('archive', 'installed', 'rebaked'))
        data = replace(data, media_root=installed, resources={
            key: installed / path.relative_to(data.media_root) for key, path in data.resources.items()})
        source = pygame.Surface((4, 2), pygame.SRCALPHA)
        alphas = ((255, 255, 64, 0), (255, 255, 128, 192))
        for y, row in enumerate(alphas):
            for x, alpha in enumerate(row):
                gray = 255 if x % 2 else 0
                source.set_at((x, y), (gray, gray, gray, alpha))
        expected, selected_before, sources_before = {}, {}, {}
        for recipe in (*draft.spells, *draft.effectDrafts.values()):
            cast = recipe.cast
            if not cast.enabled:
                continue
            for layer in (cast.weaponGlow, cast.aura, cast.slash, *(cast.effects or ())):
                if layer is None or not layer.enabled or layer.hidden or layer.palette is None:
                    continue
                assert layer.sourceSheet is not None
                assert layer.palette.noiseSheet is None, 'Noise treatment has a separate palette test.'
                source_path = archive / data.resources[f'/spritesheets/{layer.category}/{cast.actionClip}.png'].relative_to(installed)
                source_path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(source, source_path)
                sources_before[source_path] = source_path.read_bytes()
                selected = data.resources[layer.sourceSheet]
                selected.parent.mkdir(parents=True, exist_ok=True)
                selected.write_bytes(b'previous selected output must remain untouched')
                selected_before[selected] = selected.read_bytes()
                expected[output_root / selected.relative_to(installed)] = layer.palette
        outputs = bake_palettes(data, draft, source_root=archive, output_root=output_root)
        assert set(outputs) == set(expected)
        for output, palette in expected.items():
            actual = pygame.image.load(output)
            assert actual.get_size() == source.get_size()
            for y, row in enumerate(alphas):
                for x, alpha in enumerate(row):
                    color = palette.colors[-1 if x % 2 else 0]
                    assert tuple(actual.get_at((x, y))) == (
                        (color >> 16) & 255, (color >> 8) & 255, color & 255, alpha)
        assert all(path.read_bytes() == content for path, content in selected_before.items())
        assert all(path.read_bytes() == content for path, content in sources_before.items())
        assert draft_path.read_bytes() == original
    finally:
        pygame.quit()
