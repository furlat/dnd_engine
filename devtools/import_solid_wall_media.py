"""Extract independent section phases from the released Stone/Ice fixture.

The fixture's later break is not an idle animation. Its selection omits intact
retirement; the separately verified original-law export supplies that phase.
"""

import hashlib
import json
from math import isclose
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from devtools.import_assembly_media import SOURCE_CAMERAS
from devtools.import_registered_media import import_registered_bank
from devtools.media_delivery import contained_media_path, install_verified_payloads


# Source samples are at (index + 1)/32 seconds. Pose47 equals pose78 in
# the artist's validation; fracture starts after2.63s. Its finite tail includes
# the source's fragment cleanup. It is never selected by concentration loss.
SECTION_SELECTION = (*range(32), 47, *range(83, 224))
SECTION_WINDOWS = (('application', 0, 32), ('hold', 32, 1), ('destruction', 33, 141))
PALETTES = {
    'ice': ('183a55', '326585', '609dbc', 'a6d5e4', 'e2f0ed'),
    'stone': ('383b34', '62665a', '939682', 'c5c4aa', 'ece4c6'),
}


def normalize_solid_sections(source: Path, output: Path) -> tuple[str, ...]:
    """Validate pinned paired crops before writing a separate staging tree."""
    manifest = json.loads((source / 'media.json').read_text())
    if (manifest['fps'], manifest['canvas'], manifest['ortho']) != (32, [512, 512], 12):
        raise ValueError('Solid sections require the released native registration')
    if not isclose(manifest['nativeCell'], 2.121320344, abs_tol=1e-9):
        raise ValueError('Solid section native cell differs')
    if manifest['pivot'] != [256, 311.425626]:
        raise ValueError('Solid section ground pivot differs')
    rows, payloads = {}, {}
    for material in ('stone', 'ice'):
        for variant in range(3):
            for direction in range(4):
                name = f'{material}_v{variant}_d{direction}'
                cameras = {}
                for camera, original in enumerate(SOURCE_CAMERAS):
                    layers = {}
                    for side in ('back', 'front'):
                        bank = manifest['banks'][f'{material}-v{variant}-lifecycle/d{direction}/q{original}/{side}']
                        if len(bank['frames']) != 224 or bank['times'] != [(i+1)/32 for i in range(224)]:
                            raise ValueError('Solid section clock or samples differ')
                        registration = bank['registration']
                        if (registration['variant'], registration['viewport'], registration['ortho']) != (variant, [512, 512], 12):
                            raise ValueError('Solid section owner registration differs')
                        if not isclose(registration['worldHeadingRadians'], direction*3.141592653589793/2):
                            raise ValueError('Solid section native heading differs')
                        pages = []
                        for page in bank['pages']:
                            relative = page['path']
                            origin = (source / relative).resolve()
                            if not origin.is_relative_to(source.resolve()) or not origin.is_file():
                                raise ValueError('Solid section payload leaves delivery or is missing')
                            if relative not in payloads:
                                if hashlib.sha256(origin.read_bytes()).hexdigest() != page['sha256']:
                                    raise ValueError('Solid section page checksum differs')
                                payloads[relative] = origin
                            pages.append(relative)
                        frames = [bank['frames'][i] for i in SECTION_SELECTION]
                        if any(frame is not None and not 0 <= frame['page'] < len(pages) for frame in frames):
                            raise ValueError('Solid section crop references an absent page')
                        layers[side] = {'frames': frames, 'pages': pages}
                    cameras[str(camera)] = {'layers': layers}
                rows[name] = {'fps': 32, 'frames': len(SECTION_SELECTION), 'cell': 512,
                    'pivot': manifest['pivot'], 'ortho': 12, 'palette': PALETTES[material], 'cameras': cameras}
    if output.exists() or output.resolve().is_relative_to(source.resolve()):
        raise ValueError('Solid section normalization requires separate new staging')
    output.mkdir(parents=True)
    for relative, origin in payloads.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
    (output / 'media.json').write_text(json.dumps(rows, indent=2)+'\n')
    (output / 'SHA256SUMS').write_text(''.join(hashlib.sha256((output / p).read_bytes()).hexdigest()+'  '+p+'\n'
        for p in sorted(payloads)))
    return tuple(rows)


def import_solid_sections(source: Path, repo: Path) -> tuple[str, ...]:
    """Register prepared phases using the established paired storage contract."""
    identities = []
    for name, row in json.loads((source / 'media.json').read_text()).items():
        identities.extend(import_registered_bank(source, row, name, SECTION_WINDOWS, repo, bundle='wall_media'))
    return tuple(identities)


def import_solid_retirement(source: Path, *, preserved: Path, production: Path, repo: Path) -> tuple[str, ...]:
    """Install the source-law export; selected construction recipes stay separate."""
    rows = json.loads((source / 'media.json').read_text())
    validation = json.loads((source / 'validation.json').read_text())
    if (validation['durationMs'] != 850 or len(validation['samples']) != 192
            or not all(row['intact_byte_exact'] and row['final_empty'] for row in validation['samples'])
            or set(rows) != {f'{kind}_v{v}_d{d}' for kind in ('stone','ice') for v in range(3) for d in range(4)}):
        raise ValueError('Retirement export does not preserve every intact donor and finite ending')
    metadata = []
    for origin in sorted(source.rglob('*')):
        if not origin.is_file() or any(part.endswith('-project') for part in origin.relative_to(source).parts):
            continue
        relative = origin.relative_to(source).as_posix()
        checked, target = contained_media_path(source, relative), contained_media_path(preserved, relative)
        content = checked.read_bytes()
        if target.exists() and (not target.is_file() or target.read_bytes() != content):
            raise ValueError(f'Preserved retirement export differs: {relative}')
        metadata.append((checked, target))
    bundle = repo / 'game/data/wall_media'
    bindings = json.loads((bundle/'bindings.json').read_text())
    assets = {row['assetId']: row for row in json.loads((bundle/'projectile-assets.json').read_text())}
    with TemporaryDirectory(prefix='solid-retirement-') as temporary:
        staging = Path(temporary)
        identities = tuple(identity for name, row in rows.items()
            for identity in import_registered_bank(source,row,name,(('removal',0,29),),staging,bundle='wall_media'))
        additions = staging/'game/data/wall_media'
        payloads = tuple((path.relative_to(source).as_posix(),
            (Path('game/assets/wall_media/retirement')/path.relative_to(source)).as_posix(),
            hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted((source/'packed').rglob('*.png')))
        staged = json.loads((additions/'bindings.json').read_text())['projectileStorage']
        # Address this new export separately from unchanged original lifecycle pages.
        for storage in staged.values():
            for layer in storage['phases']['impact']['layers']:
                for frames in layer['partsByFacing'].values():
                    for parts in frames:
                        for part in parts:
                            part['file'] = part['file'].replace('game/assets/wall_media/','game/assets/wall_media/retirement/',1)
        files = install_verified_payloads(source,payloads,preserved=preserved,production=production,repo=repo)
        for origin,target in metadata:
            target.parent.mkdir(parents=True,exist_ok=True)
            if origin != target:shutil.copyfile(origin,target)
        bindings['projectileStorage'].update(staged)
        assets.update({row['assetId']:row for row in json.loads((additions/'projectile-assets.json').read_text())})
    (bundle/'bindings.json').write_text(json.dumps(bindings,indent=2)+'\n')
    (bundle/'projectile-assets.json').write_text(json.dumps(list(assets.values()),indent=2)+'\n')
    (bundle/'intact-retirement-source.json').write_text(json.dumps({'source':str(source),'preserved':str(preserved),
        'durationMs':850,'rgba':'Original-operator production recapture; intact first samples byte-identical.',
        'validation_sha256':hashlib.sha256((source/'validation.json').read_bytes()).hexdigest(),
        'identities':identities,'files':files},indent=2)+'\n')
    return identities
