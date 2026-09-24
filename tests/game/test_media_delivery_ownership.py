"""Explicit delivery intake preserves selected media and independent authoring."""

import json
from pathlib import Path
import shutil

from devtools.import_aoe_surfaces import BUNDLES, FACINGS, import_bundle as import_surfaces
from devtools.import_area_spells import import_bundle as import_areas
from devtools.import_globe_media import import_bundle as import_globe
from devtools.import_pending_spells import import_bundle as import_pending
from devtools.import_sleep_spell import import_bundle as import_sleep


ROOT = Path(__file__).resolve().parents[2]


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def current_bundle(repo: Path, name: str) -> Path:
    folder = repo / 'game/data' / name
    folder.mkdir(parents=True)
    for filename in ('bindings.json', 'projectile-assets.json', 'spell-studio-drafts.json'):
        shutil.copyfile(ROOT / 'game/data' / name / filename, folder / filename)
    return folder


def test_aoe_intake_updates_storage_without_reauthoring_tuned_tracks(tmp_path):
    repo, source = tmp_path / 'repo', tmp_path / 'source'
    recipes, assets = {}, {}
    for bundle in sorted({bundle for _, bundle, _, _ in BUNDLES}):
        folder = current_bundle(repo, bundle)
        path = folder / 'spell-studio-drafts.json'
        document = json.loads(path.read_text())
        for spell in [*document['spells'], *document.get('effectDrafts', {}).values()]:
            for track in spell.get('media', ()):
                track.update(scale=.371, startOffsetMs=53)
            if spell.get('projectile') is not None:
                spell['projectile']['impact']['viewFacing'] = 'N'
        write(path, document)
        recipes[path] = path.read_bytes()
        asset_path = folder / 'projectile-assets.json'
        assets[asset_path] = asset_path.read_bytes()
    for name in {name for name, _, _, _ in BUNDLES}:
        write(source / f'{name}-manifest.json', {'spell': name, 'frames': 1,
            'directions': {facing: [10.25, 12.5] for facing in FACINGS}, 'displayScale': .83})
        directory = source / 'delivery' / name
        directory.mkdir(parents=True)
        (directory / 'packet.bin.gz').write_bytes(b'delivered unchanged packet')

    import_surfaces(source, repo)
    first = {path: path.read_bytes() for path in repo.glob('game/data/*/bindings.json')}
    import_surfaces(source, repo)

    assert all(path.read_bytes() == value for path, value in recipes.items())
    assert all(path.read_bytes() == value for path, value in assets.items())
    assert all(path.read_bytes() == value for path, value in first.items())
    for name, bundle, identity, component in BUNDLES:
        storage = json.loads((repo / 'game/data' / bundle / 'bindings.json').read_text())['projectileStorage']
        packet = storage[identity]['phases']['impact']['surfaceFrames']
        assert packet['frameIndices'] == [0] and packet['positionScale'] == .83
        assert packet['componentsByFacing']['N'][0]['pivot'] == [10.25, 12.5]
        assert (repo / 'game/assets/aoe_surface' / name / 'packet.bin.gz').read_bytes() == b'delivered unchanged packet'


def test_old_area_bundle_preserves_xyz_selection_and_does_not_revive_cell_tracks(tmp_path):
    repo, source = tmp_path / 'repo', tmp_path / 'source'
    folder = current_bundle(repo, 'area_spells')
    original = {name: json.loads((folder / name).read_text())
                for name in ('bindings.json', 'projectile-assets.json')}
    for relative in ('aoe-crest-review/actors/burning_hands/hand-glow.png',
                     'aoe-crest-review/actors/thunderwave/Special1-glow.png',
                     'gust-wave-review/actors/gust_of_wind/hand-glow.png'):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'selected caster sheet')
    import_areas(source, repo=repo)
    assert json.loads((folder / 'projectile-assets.json').read_text()) == original['projectile-assets.json']
    assert json.loads((folder / 'bindings.json').read_text()) == original['bindings.json']


def test_old_shatter_delivery_preserves_selected_xyz_and_other_pending_spells(tmp_path):
    repo, source = tmp_path / 'repo', tmp_path / 'source'
    folder = current_bundle(repo, 'pending_spells')
    selected = {name: json.loads((folder / name).read_text()) for name in ('bindings.json', 'projectile-assets.json')}
    write(source / 'delivery-next-spells-directions-v1/manifest.json', {'spells': [{
        'id': 'shatter', 'frames': 1, 'fps': 144, 'frameSize': [8, 8], 'pivot': [4, 4],
        'palette': ['ffffff'], 'columns': 1, 'framesPerPage': 1,
        'directions': {'E': {'layers': {'back': ['not-selected.png'], 'front': ['not-selected.png']}}}}]})
    import_pending(source, repo=repo)
    assert all(json.loads((folder / name).read_text()) == before for name, before in selected.items())


def test_old_sleep_arrival_preserves_selected_surface_media(tmp_path):
    repo, source = tmp_path / 'repo', tmp_path / 'source'
    folder = current_bundle(repo, 'spell_recovery')
    selected = {name: json.loads((folder / name).read_text()) for name in ('bindings.json', 'projectile-assets.json')}
    write(repo / 'game/data/assets.json', {'resources': {}})
    write(source / 'manifest.json', {'id': 'sleep', 'palette': 'palette.json',
                                   'projectile': {}, 'assets': {'sleep': {}}})
    write(source / 'palette.json', {'colors': [[1, 2, 3]]})
    import_sleep(source, repo=repo)
    assert all(json.loads((folder / name).read_text()) == before for name, before in selected.items())


def test_globe_delivery_preserves_other_selected_media(tmp_path):
    source, repo = tmp_path / 'source', tmp_path / 'repo'
    catalog = {}
    for prefix in ('globe', 'physics'):
        for quadrant in range(4):
            for side in ('back', 'front'):
                catalog[f'{prefix}-q{quadrant}-{side}'] = {'pages': ['page.png'],
                    'frames': [{'page': 0, 'source': [0, 0, 1, 1], 'offset': [0, 0]}] * 672}
    write(source / 'media.json', catalog)
    (source / 'page.png').write_bytes(b'one unchanged atlas')
    folder = repo / 'game/data/globe_media'
    write(folder / 'projectile-assets.json', [{'assetId': 'other', 'authored': True}])
    write(folder / 'bindings.json', {'resources': {}, 'projectileStorage': {'other': {'keep': True}}})
    import_globe(source, repo)
    assert {'assetId': 'other', 'authored': True} in json.loads((folder / 'projectile-assets.json').read_text())
    assert json.loads((folder / 'bindings.json').read_text())['projectileStorage']['other'] == {'keep': True}
