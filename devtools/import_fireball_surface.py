"""Install the accepted paired Fireball color/XYZ delivery without authoring behavior."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import shutil

from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


ROOT = Path(__file__).resolve().parents[1]


def convert_single_view(source: Path, output: Path, asset: AuthoredProjectileAsset,
                        *, prefix: str = 'game/assets/fireball_single_view_v4') -> tuple[AuthoredProjectileAsset, ProjectileStorage, dict[str, dict]]:
    """Translate the accepted native MRT export into the existing media schema.

    This is an offline derived release; legacy installed art and the source
    manifest are preserved. No Godot-specific manifest reaches the client.
    """
    encoded = (source / 'manifest.json').read_bytes()
    if sha256(encoded).hexdigest() != '192fa78c65c8cc1f574a317d64f78663898dbe49e0078b8ce756e8b3cc703061':
        raise ValueError('Fireball source differs from the selected v4 handoff')
    manifest = json.loads(encoded)
    transform = manifest['sourceToHost'][:3]
    geometry = {'kind': 'ray_depth', 'basis': 'camera_local', 'sourceToLocal': transform,
        'depthRange': [manifest['depthMin'], manifest['depthMax']],
        'pixelToRayOrigin': manifest['sourcePixelToRayOrigin'], 'rayDirection': manifest['rayDirection']}
    layers, resources = [], {}
    for band in manifest['depthLayers']:
        parts = []
        for frame in manifest['frames']:
            layer = frame['layers'][band]
            paths = {}
            for name in ('appearance', 'geometry'):
                record = layer[name]
                path = (source / record['file']).resolve()
                if not path.is_relative_to(source.resolve()):
                    raise ValueError('Fireball plane leaves the source delivery')
                compressed = path.read_bytes()
                if len(compressed) != record['compressedBytes'] or sha256(compressed).hexdigest() != record['sha256']:
                    raise ValueError(f'Fireball plane differs: {record["file"]}')
                payload = gzip.decompress(compressed)
                if len(payload) != record['decodedBytes'] or sha256(payload).hexdigest() != record['decodedSha256']:
                    raise ValueError(f'Fireball decoded plane differs: {record["file"]}')
                relative = f'{prefix}/{record["file"]}'
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                paths[name] = relative
                resources[relative] = {'width': layer['width'], 'height': layer['height'],
                    'channels': 4, 'encoding': 'raw_gzip'}
            parts.append([{'file': paths['appearance'], 'geometryFile': paths['geometry'],
                'rect': [0, 0, layer['width'], layer['height']],
                'offset': layer['absoluteCropPixels'][:2]}])
        layers.append({'parts': parts, 'blendMode': 'normal',
            'appearanceEncoding': 'linear_premultiplied_rgba8', 'radianceScale': manifest['radianceScale'],
            'geometry': geometry, 'receiving': {'enabled': True, 'preserveEmission': True}})
    keys = []
    for key in manifest['lightCurve']['keys']:
        p = [*key['sourceLocalPosition'], 1]
        keys.append({'elapsedMs': key['timeSeconds'] * 1000,
            'position': [sum(a * b for a, b in zip(row, p)) for row in transform],
            'colorLinear': key['linearRGB'], 'intensity': key['relativeIntensity'], 'range': key['radiusGridUnits']})
    storage = ProjectileStorage.model_validate_json(json.dumps({'phases': {'impact': {'layers': layers,
        'emitter': {'keys': keys, 'interpolation': 'linear'}}}}))
    selected = asset.model_dump(mode='json')
    width, height = manifest['untrimmedSize']
    selected.update(sheet=None, fps=manifest['fps'], rowOrder=[manifest['view']], defaultScale=1,
        frame={'width': width, 'height': height, 'rows': 1, 'cols': len(manifest['frames'])},
        anchor={'x': manifest['pivotPixels'][0] / width, 'y': manifest['pivotPixels'][1] / height},
        anchorsByFacing=None, phases={'impact': {'start': 0, 'frames': len(manifest['frames']),
            'fps': manifest['fps'], 'loop': False}}, source=None, preview=None)
    return AuthoredProjectileAsset.model_validate_json(json.dumps(selected)), storage, resources


def import_bundle(source: Path, repo: Path = ROOT) -> None:
    destination = repo / "game/assets/fireball_surface"
    # Keep every native sample available. Playback selects the approved 48-frame
    # schedule; copying packets changes neither pixels nor their geometry.
    for direction in ("E", "SE", "S", "SW", "W", "NW", "N", "NE"):
        folder = destination / direction
        folder.mkdir(parents=True, exist_ok=True)
        for frame in range(288):
            shutil.copyfile(source / "delivery" / direction / f"{frame:03d}.bin.gz",
                            folder / f"{frame:03d}.bin.gz")
    path = repo / "game/data/spell_recovery/bindings.json"
    bindings = json.loads(path.read_text())
    bindings["projectileStorage"]["shared.fireball.20ft-ground.smoke.v3"] = {
        "phases": {"impact": {"surfaceFrames": {
            "pattern": "game/assets/fireball_surface/{direction}/{frame:03d}.bin.gz",
            "frameIndices": [*range(0, 277, 6), 287],
            "bounds": [-16, 16], "verticalScale": 1.224744871391589,
            "blendModes": ["normal", "add"],
        }}}
    }
    path.write_text(json.dumps(bindings, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    import_bundle(args.source)
    print("Installed all eight paired Fireball banks; existing recipe and timing retained.")
