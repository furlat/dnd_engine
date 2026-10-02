"""Normalize released single-RGBA wall modules into existing registered storage."""

import argparse
import hashlib
import json
from math import isclose
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from devtools.import_registered_media import import_registered_bank

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CAMERAS = (0, 3, 2, 1)
WINDOWS = (('application', 0, 63), ('hold', 63, 64), ('removal', 128, 32))
PALETTE = ('22271c', '473823', '716044', 'a18b61', '44502b', '69713d', '9b995c', 'd0c096')


def normalize_assembly(source: Path, output: Path, program: str) -> tuple[str, ...]:
    """Keep single-layer pixels single; an empty adapter side is never published."""
    manifest = json.loads((source / 'media.json').read_text())
    if program not in ('thorns', 'wind'):
        raise ValueError('No released module contract for this selection')
    if (manifest['fps'], manifest['canvas']) != (32, [512, 512]):
        raise ValueError('Wall modules require their native 512-pixel 32-FPS source')
    if manifest['loop'] != {'first': 63, 'lastExclusive': 127, 'periodSeconds': 2, 'verificationEndpoint': 127}:
        raise ValueError('Wall loop contract differs from the released two-second selection')
    if manifest['removal'] != {'first': 128, 'lastExclusive': 160}:
        raise ValueError('Wall retirement must be a distinct finite phase')
    if not isclose(manifest['nativeCell'], 2.121320344, abs_tol=1e-9):
        raise ValueError('Wall source cell registration differs')
    names = [(f'{program}_d{d}', 'module', d) for d in range(8)]
    if program == 'thorns':
        names.append(('thorns_ring', 'circle', 0))
    rows, payloads = {}, {}
    # Validate every selected bank before creating output.
    for name, shape, d in names:
        cameras = {}
        for q, original_q in enumerate(SOURCE_CAMERAS):
            bank = manifest['banks'][f'{shape}/d{d}/q{original_q}']
            if len(bank['frames']) != 160 or bank['ortho'] != (16 if shape == 'circle' else 12):
                raise ValueError('Incomplete native wall registration')
            expected_pivot = (256, 297.56921938165306 if shape == 'circle' else 311.42562584220406)
            if any(not isclose(a, b, abs_tol=1e-8) for a, b in zip(bank['pivot'], expected_pivot, strict=True)):
                raise ValueError('Wall source ground pivot differs')
            for frame in bank['frames']:
                if frame is not None and not 0 <= frame['page'] < len(bank['pages']):
                    raise ValueError('Absent source page')
            for relative in bank['pages']:
                origin = (source / relative).resolve()
                if not origin.is_relative_to(source.resolve()) or not origin.is_file():
                    raise ValueError('Wall source path leaves delivery or is absent')
                payloads[relative] = origin
            frames = list(bank['frames'])
            frames[127] = None  # Diagnostic duplicate: neither addressed nor packed for playback.
            cameras[str(q)] = {'layers': {'back': {'frames': frames, 'pages': bank['pages']},
                'front': {'frames': [None]*160, 'pages': []}}}
        rows[name] = {'fps': 32, 'frames': 160, 'cell': 512, 'pivot': list(expected_pivot),
            'ortho': bank['ortho'], 'palette': list(PALETTE), 'cameras': cameras}
    if output.exists() or output.resolve().is_relative_to(source.resolve()):
        raise ValueError('Normalization requires separate new staging')
    output.mkdir(parents=True)
    for relative, origin in payloads.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
    (output / 'media.json').write_text(json.dumps(rows, indent=2)+'\n')
    (output / 'SHA256SUMS').write_text(''.join(hashlib.sha256((output / p).read_bytes()).hexdigest()+'  '+p+'\n' for p in sorted(payloads)))
    return tuple(rows)


def import_assembly(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    rows = json.loads((source / 'media.json').read_text())
    with TemporaryDirectory(prefix='wall-assembly-registration-') as temporary:
        staging = Path(temporary)
        for name, row in rows.items():
            import_registered_bank(source, row, name, WINDOWS, staging, bundle='wall_media')
        folder = staging / 'game/data/wall_media'
        bindings = json.loads((folder / 'bindings.json').read_text())
        assets = [a for a in json.loads((folder / 'projectile-assets.json').read_text()) if a['assetId'].endswith('.back')]
        storage = {k: v for k, v in bindings['projectileStorage'].items() if k.endswith('.back')}
        destination = repo / 'game/data/wall_media'
        old_bindings = json.loads((destination / 'bindings.json').read_text()) if destination.exists() else {'resources': {}, 'spells': {}}
        old_assets = {a['assetId']: a for a in json.loads((destination / 'projectile-assets.json').read_text())} if destination.exists() else {}
        old_bindings.setdefault('projectileStorage', {}).update(storage)
        old_assets.update({a['assetId']: a for a in assets})
        for origin in (staging / 'game/assets/wall_media').rglob('*.png'):
            target = repo / origin.relative_to(staging)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'bindings.json').write_text(json.dumps(old_bindings, indent=2)+'\n')
        (destination / 'projectile-assets.json').write_text(json.dumps(list(old_assets.values()), indent=2)+'\n')
    return tuple(a['assetId'] for a in assets)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=ROOT)
    args = parser.parse_args()
    print(f'Registered {len(import_assembly(args.source, repo=args.repo))} original wall lifecycle banks')
