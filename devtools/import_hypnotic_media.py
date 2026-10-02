"""Register approved floor samples; gameplay ownership is authored separately."""

import argparse
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from devtools.import_registered_media import import_registered_bank

ROOT = Path(__file__).resolve().parents[1]


def import_hypnotic(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    rows = json.loads((source / 'media.json').read_text())
    programs = (('hypnotic_circle_ground', 'hypnotic_rosette', 'finite', 96),
                ('hypnotic_spiral_loop', 'hypnotic_spiral', 'hold', 128))
    for name, _, _, count in programs:
        row = rows[name]
        if (row['fps'], row['cell'], row['ortho']) != (32, 768, 16):
            raise ValueError('Hypnotic requires its original 32-FPS floor registration')
        if row['frames'] not in ((128, 129) if count == 128 else (96,)):
            raise ValueError('Hypnotic source window differs from the accepted contract')
        if count == 128 and row.get('loopFrames') != 128:
            raise ValueError('Hypnotic sustain must exclude the verification endpoint')
        if any(any(frame is not None for frame in camera['layers']['front']['frames'])
               for camera in row['cameras'].values()):
            raise ValueError('Hypnotic source is an intentionally rear-only floor bank')
    if rows[programs[0][0]]['pivot'] != rows[programs[1][0]]['pivot']:
        raise ValueError('Hypnotic formation and sustain require a common ground pivot')
    with TemporaryDirectory(prefix='hypnotic-registration-') as temporary:
        staging = Path(temporary)
        for name, program, phase, count in programs:
            import_registered_bank(source, rows[name], program, ((phase, 0, count),),
                staging, bundle='control_media', default_scale=.5)
        folder = staging / 'game/data/control_media'
        bindings = json.loads((folder / 'bindings.json').read_text())
        assets = json.loads((folder / 'projectile-assets.json').read_text())
        # Do not publish empty counterpart identities as usable visual layers.
        assets = [row for row in assets if row['assetId'].endswith('.back')]
        storage = {identity: row for identity, row in bindings['projectileStorage'].items()
                   if identity.endswith('.back')}
        destination = repo / 'game/data/control_media'
        old_bindings = json.loads((destination / 'bindings.json').read_text()) if (
            destination / 'bindings.json').exists() else {'resources': {}, 'spells': {}}
        old_assets = {row['assetId']: row for row in json.loads(
            (destination / 'projectile-assets.json').read_text())} if (
            destination / 'projectile-assets.json').exists() else {}
        old_bindings.setdefault('projectileStorage', {}).update(storage)
        old_assets.update({row['assetId']: row for row in assets})
        for origin in (staging / 'game/assets/control_media').rglob('*.png'):
            target = repo / origin.relative_to(staging)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'bindings.json').write_text(json.dumps(old_bindings, indent=2)+'\n')
        (destination / 'projectile-assets.json').write_text(json.dumps(list(old_assets.values()), indent=2)+'\n')
    return tuple(row['assetId'] for row in assets)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=ROOT)
    args = parser.parse_args()
    print(f'Registered {len(import_hypnotic(args.source, repo=args.repo))} Hypnotic floor banks')
