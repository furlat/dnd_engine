"""Install validated source-coordinate companions into existing surface storage."""

import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from math import sqrt
from pathlib import Path
import struct
import zipfile

from devtools.import_registered_media import DIRECTIONS
from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage

ROOT = Path(__file__).resolve().parents[1]


def import_surfaces(source: Path, program: str, *, preserved: Path,
                    production: Path, repo: Path = ROOT) -> dict:
    receipt_path = contained_media_path(source, program+'-ownership.json')
    receipt = json.loads(receipt_path.read_text())
    expected = ({f'beam-{i}' for i in range(8)} if program == 'beam' else
                {'burst-back', 'burst-front'} if program == 'burst' else
                {'sleet-ground', 'sleet-back', 'sleet-front'} if program == 'sleet' else set())
    banks = {row['bank']: row for row in receipt['banks']}
    if not expected or set(banks) != expected or len(banks) != len(receipt['banks']):
        raise ValueError('Surface export has incomplete or duplicate source banks')
    if receipt['bounds'] != [-64, 64] or receipt['coordinateBasis'] != 'camera_local_xyz':
        raise ValueError('Unexpected source coordinate contract')
    if receipt['production_rgba_recaptured'] != (program == 'beam') or receipt['accepted_rgba_byte_exact'] != (program != 'beam'):
        raise ValueError('Source colour provenance is inconsistent')
    count = {'beam': 48, 'burst': 64, 'sleet': 128}[program]
    payloads = []
    for bank in banks.values():
        path = contained_media_path(source, bank['file'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != bank['sha256']:
            raise ValueError('Surface payload checksum mismatch')
        if bank['frames'] != count or len(bank['checks']) != count or bank['worldPixels'] <= 0:
            raise ValueError('Unexpected source frame count or camera scale')
        if any(check['frame'] != frame or check['missingOwnership'] or check['maxCameraErrorPixels'] > .8
               for frame, check in enumerate(bank['checks'])):
            raise ValueError('Surface export has unresolved ownership or camera error')
        with zipfile.ZipFile(path) as archive:
            if set(archive.namelist()) != {f'{frame:03d}.bin.gz' for frame in range(count)} or len(archive.namelist()) != count:
                raise ValueError('Surface packet sequence mismatch')
            for frame in range(count):
                payload = gzip.decompress(archive.read(f'{frame:03d}.bin.gz'))
                width, height, _, _ = struct.unpack('<HHhh', payload[:8])
                pixels = width*height
                if not width or not height or len(payload) != 8+pixels*11:
                    raise ValueError('Malformed packed source surface')
                rgba, owned = payload[8:8+pixels*4], payload[8+pixels*10:]
                if any(alpha and not owner for alpha, owner in zip(rgba[3::4], owned)):
                    raise ValueError('A visible source pixel has no owner')
        runtime = f"game/assets/weather_solar_media/surfaces/{bank['file']}"
        payloads.append((bank['file'], runtime, bank['sha256']))
    bundle = repo / 'game/data/weather_solar_media'
    bindings = json.loads((bundle/'bindings.json').read_text())
    assets = {row['assetId']: row for row in json.loads((bundle/'projectile-assets.json').read_text())}
    selected = {}
    phases = [('full', 0, count)] if program != 'sleet' else [('apply', 0, 32), ('hold', 32, 64), ('remove', 96, 32)]
    for phase, first, frames in phases:
        for side in ([None] if program == 'beam' else ['back', 'front'] if program == 'burst' else ['ground', 'back', 'front']):
            base = ('solar.sunbeam' if program == 'beam' else f'solar.sunburst.{side}'
                    if program == 'burst' else f'weather.sleet.storm.{phase}.{side}')
            identity = base+'.surface'
            asset = deepcopy(assets[base]); asset['assetId'] = identity
            asset['displayName'] = identity
            components = {}
            for index, facing in enumerate(DIRECTIONS):
                bank = banks[f'beam-{(index-1)%8}' if program == 'beam' else f'{program}-{side}']
                components[facing] = [{'archive': {'file': f"game/assets/weather_solar_media/surfaces/{bank['file']}",
                    'memberPattern': '{frame:03d}.bin.gz'}, 'pivot': bank['pivot'], 'blendMode': 'normal'}]
            packet = {'componentsByFacing': components, 'frameIndices': list(range(first, first+frames)),
                'bounds': receipt['bounds'], 'verticalScale': receipt['verticalScale'],
                'referencePixelScale': 64*sqrt(2)/bank['worldPixels']}
            storage = {'phases': {'impact': {'surfaceFrames': packet}}}
            AuthoredProjectileAsset.model_validate_json(json.dumps(asset))
            ProjectileStorage.model_validate_json(json.dumps(storage))
            assets[identity] = asset
            selected[identity] = storage
    # Preflight provenance before any payload mutation, like the original intake.
    metadata = [(receipt_path, contained_media_path(preserved, receipt_path.name))]
    project_path = contained_media_path(source, program+'-source-project.json')
    project = json.loads(project_path.read_text()) if project_path.exists() else None
    if project is not None:
        metadata.append((project_path, contained_media_path(preserved, project_path.name)))
    for folder in ([program+'-opaque'] if program != 'sleet' else ['ground', 'back', 'front']):
        for file in sorted(file for file in (source/folder).iterdir() if file.suffix in ('.gd', '.gdshader')):
            relative = folder+'/'+file.name
            metadata.append((contained_media_path(source, relative), contained_media_path(preserved, relative)))
        complete = contained_media_path(source, folder+'/complete.json')
        metadata.append((complete, contained_media_path(preserved, folder+'/complete.json')))
    contents = [(origin.read_bytes(), target) for origin, target in metadata]
    if any(target.exists() and target.read_bytes() != value for value, target in contents):
        raise ValueError('Preserved surface provenance differs')
    files = install_verified_payloads(source, tuple(payloads), preserved=preserved, production=production, repo=repo)
    for value, target in contents:
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(value)
    bindings.setdefault('projectileStorage', {}).update(selected)
    (bundle/'bindings.json').write_text(json.dumps(bindings, separators=(',', ':'))+'\n')
    (bundle/'projectile-assets.json').write_text(json.dumps(list(assets.values()), separators=(',', ':'))+'\n')
    public = {**receipt, 'preserved': str(preserved), 'identities': list(selected), 'files': files}
    public['capture_adapters'] = {str(target.relative_to(preserved)): hashlib.sha256(value).hexdigest()
        for value, target in contents if target.suffix in ('.gd', '.gdshader')}
    if project is not None:
        public['source_project'] = project['source_project']
        public['source_project_sha256'] = hashlib.sha256(project_path.read_bytes()).hexdigest()
        public['source_project_files'] = len(project['files'])
    for bank in public['banks']:
        bank['validation'] = {'frames': len(bank['checks']), 'missingOwnership': 0,
            'maxCameraErrorPixels': max(check['maxCameraErrorPixels'] for check in bank['checks'])}
        del bank['checks']
    (bundle/(program+'-surfaces-source.json')).write_text(json.dumps(public, indent=2)+'\n')
    return public


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'preserved', 'production'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--program', choices=('beam', 'burst', 'sleet'), required=True)
    args = parser.parse_args()
    result = import_surfaces(args.source, args.program, preserved=args.preserved, production=args.production)
    print('Installed', len(result['files']), 'validated source surface archives')
