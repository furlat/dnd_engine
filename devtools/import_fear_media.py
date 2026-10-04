"""Register accepted native eight-heading Fear and source-owned Frightened banks."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from devtools.import_registered_media import DIRECTIONS, import_registered_bank
from devtools.media_delivery import install_verified_payloads

ROOT = Path(__file__).resolve().parents[1]


def import_fear(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    rows = json.loads((source / 'media.json').read_text())
    for name, frames, cell in (('fear_path_v7', 144, 896),
                              ('fear_path_v7_diagonal', 144, 896),
                              ('frightened_v5', 96, 384)):
        row = rows[name]
        if (row['fps'], row['frames'], row['cell']) != (32, frames, cell):
            raise ValueError('Fear requires the pinned native finite and selected condition windows')
    cardinal, diagonal = rows['fear_path_v7'], rows['fear_path_v7_diagonal']
    if cardinal['palette'] != diagonal['palette'] or any(abs(a-b) > 1e-6
            for a,b in zip(cardinal['pivot'], diagonal['pivot'], strict=True)):
        raise ValueError('Fear native headings require matching palette and ground pivot')
    # Validate every packet before changing installed media or registration.
    with TemporaryDirectory(prefix='fear-registration-') as temporary:
        staging = Path(temporary)
        for name, program, windows in (
                ('fear_path_v7', 'fear_cardinal', (('finite', 0, 144),)),
                ('fear_path_v7_diagonal', 'fear_diagonal', (('finite', 0, 144),)),
                ('frightened_v5', 'frightened', (('apply', 0, 48), ('hold', 32, 64)))):
            import_registered_bank(source, rows[name], program, windows, staging,
                bundle='control_media', default_scale=.5)
        folder = staging / 'game/data/control_media'
        bindings = json.loads((folder / 'bindings.json').read_text())
        storage = bindings['projectileStorage']
        assets = {r['assetId']: r for r in json.loads((folder / 'projectile-assets.json').read_text())}
        for side in ('back', 'front'):
            identity = f'control.fear.finite.{side}'
            card_id, diag_id = (f'control.fear_{kind}.finite.{side}' for kind in ('cardinal', 'diagonal'))
            asset = assets.pop(card_id)
            assets.pop(diag_id)
            asset.update(assetId=identity, displayName=identity,
                sheet=f'/control_media/fear/finite/{side}.png')
            assets[identity] = asset
            card_views = storage.pop(card_id)['phases']['impact']['layers'][0]['partsByFacing']
            diag_views = storage.pop(diag_id)['phases']['impact']['layers'][0]['partsByFacing']
            # Source+Z is grid+Y (world SW), not grid+X. Native quarter samples
            # match engine camera turns; positive source yaw reduces the quarter.
            views = {facing: (diag_views if i % 2 == 0 else card_views)[DIRECTIONS[2*((i+6)//2 % 4)]]
                for i,facing in enumerate(DIRECTIONS)}
            storage[identity] = {'phases': {'impact': {'layers': [
                {'partsByFacing': views, 'blendMode': 'normal'}]}}}
        destination = repo / 'game/data/control_media'
        old_bindings = json.loads((destination / 'bindings.json').read_text()) if (destination / 'bindings.json').exists() else {'resources': {}, 'spells': {}}
        old_assets = {r['assetId']: r for r in json.loads((destination / 'projectile-assets.json').read_text())} if (destination / 'projectile-assets.json').exists() else {}
        old_bindings.setdefault('projectileStorage', {}).update(storage)
        old_assets.update(assets)
        for origin in (staging / 'game/assets/control_media').rglob('*.png'):
            target = repo / origin.relative_to(staging)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'bindings.json').write_text(json.dumps(old_bindings, indent=2)+'\n')
        (destination / 'projectile-assets.json').write_text(json.dumps(list(old_assets.values()), indent=2)+'\n')
    return tuple(assets)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=ROOT)
    args = parser.parse_args()
    print(f'Registered {len(import_fear(args.source, repo=args.repo))} Fear / Frightened layers')


def import_sickened(source: Path, *, production: Path, repo: Path = ROOT) -> tuple[str, ...]:
    """Reuse the archived Eyebite handoff's common condition; no spell binding."""
    row = json.loads((source / 'production-handoff/fear-eyebite-approved-media.json').read_text())['sickened_v5']
    row = {**row, 'fps': 32}  # Explicit export clock in FEAR_EYEBITE.md.
    with TemporaryDirectory(prefix='sickened-registration-') as temporary:
        staging = Path(temporary)
        identities = import_registered_bank(source, row, 'sickened',
            (('apply', 0, 48), ('hold', 32, 64)), staging, bundle='control_media', default_scale=.5)
        payloads = tuple((str(path.relative_to(source)),
            'game/assets/control_media/' + str(path.relative_to(source)),
            hashlib.sha256(path.read_bytes()).hexdigest())
            for path in dict.fromkeys(source / page for camera in row['cameras'].values()
                for layer in camera['layers'].values() for page in layer['pages']))
        install_verified_payloads(source, payloads, preserved=source, production=production, repo=repo)
        folder = repo / 'game/data/control_media'
        bindings = json.loads((folder / 'bindings.json').read_text())
        staged = staging / 'game/data/control_media'
        bindings['projectileStorage'].update(json.loads((staged / 'bindings.json').read_text())['projectileStorage'])
        assets = {r['assetId']: r for r in json.loads((folder / 'projectile-assets.json').read_text())}
        assets.update({r['assetId']: r for r in json.loads((staged / 'projectile-assets.json').read_text())})
        (folder / 'bindings.json').write_text(json.dumps(bindings, indent=2)+'\n')
        (folder / 'projectile-assets.json').write_text(json.dumps(list(assets.values()), indent=2)+'\n')
        (folder / 'sickened-source.json').write_text(json.dumps({'source': str(source),
            'manifest': 'production-handoff/fear-eyebite-approved-media.json',
            'manifest_sha256': hashlib.sha256((source / 'production-handoff/fear-eyebite-approved-media.json').read_bytes()).hexdigest(),
            'identities': identities, 'selected_windows': {'apply': [0, 48], 'hold': [32, 64]}}, indent=2)+'\n')
    return identities


def import_eyebite(source: Path, *, production: Path, repo: Path = ROOT) -> tuple[str, ...]:
    """Register accepted eye/contact windows; recipes remain independently authored."""
    manifest_path = source/'production-handoff/fear-eyebite-approved-media.json'
    rows = json.loads(manifest_path.read_text())
    selections = (('eyebite_eye_v1','eyebite_eye',(('apply',0,48),('hold',32,80))),
                  ('eyebite_hit_v2','eyebite_hit',(('finite',0,48),)))
    result = []
    payloads = {}
    with TemporaryDirectory(prefix='eyebite-registration-') as temporary:
        staging = Path(temporary)
        for identity,program,windows in selections:
            row = {**rows[identity],'fps':32}
            result.extend(import_registered_bank(source,row,program,windows,staging,
                bundle='control_media',default_scale=.5))
            for camera in row['cameras'].values():
                for layer in camera['layers'].values():
                    for relative in layer['pages']:
                        path=source/relative
                        payloads[relative]=(relative,'game/assets/control_media/'+relative,
                            hashlib.sha256(path.read_bytes()).hexdigest())
        install_verified_payloads(source,tuple(payloads.values()),preserved=source,production=production,repo=repo)
        folder=repo/'game/data/control_media'
        bindings=json.loads((folder/'bindings.json').read_text())
        staged=staging/'game/data/control_media'
        bindings['projectileStorage'].update(json.loads((staged/'bindings.json').read_text())['projectileStorage'])
        assets={row['assetId']:row for row in json.loads((folder/'projectile-assets.json').read_text())}
        assets.update({row['assetId']:row for row in json.loads((staged/'projectile-assets.json').read_text())})
        (folder/'bindings.json').write_text(json.dumps(bindings,indent=2)+'\n')
        (folder/'projectile-assets.json').write_text(json.dumps(list(assets.values()),indent=2)+'\n')
        (folder/'eyebite-source.json').write_text(json.dumps({'source':str(source),
            'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'identities':result,'selected_windows':selections},indent=2)+'\n')
    return tuple(result)
