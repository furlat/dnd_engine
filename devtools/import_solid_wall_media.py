"""Extract independent section phases from the released Stone/Ice fixture.

The fixture's later break is not an idle animation. Retirement of an intact
section needs a separate donor and is deliberately absent from this selection.
"""

import hashlib
import json
from math import isclose
from pathlib import Path
import shutil

from devtools.import_assembly_media import SOURCE_CAMERAS
from devtools.import_registered_media import import_registered_bank


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
