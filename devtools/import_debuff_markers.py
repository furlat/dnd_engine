"""Install the delivered steady marker pixels into existing registered media."""

import argparse
import json
from pathlib import Path
import shutil

from devtools.media_delivery import install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage
from game.condition_media import ConditionMediaDocument

ROOT = Path(__file__).resolve().parents[1]


def import_markers(source: Path) -> None:
    packet = source / 'production'
    receipt = json.loads((packet / 'asset-receipt.json').read_text())
    if receipt['revision'] not in ('steady-markers-v2', 'distinct-slow-v3'):
        raise ValueError('Expected steady marker delivery')
    assets = json.loads((packet / 'projectile-assets.json').read_text())
    bindings = json.loads((packet / 'bindings.json').read_text())
    media = ConditionMediaDocument.model_validate_json((packet / 'condition-media-additions.json').read_text())
    for row in assets:
        asset = AuthoredProjectileAsset.model_validate_json(json.dumps(row))
        if asset.phases.impact is None or asset.phases.impact.frames != 1:
            raise ValueError('Overhead markers must be single frames')
    for row in bindings['projectileStorage'].values():
        ProjectileStorage.model_validate_json(json.dumps(row))
    preserved = Path('/home/tommaso/Dev/neurodragon_art/sources/debuff-markers-steady-20261005')
    files = install_verified_payloads(packet, tuple((row['sourceFile'], row['installFile'], row['sha256'])
        for row in receipt['banks'].values()), preserved=preserved,
        production=Path('/home/tommaso/Dev/neurodragon_art-production'), repo=ROOT)
    for name in ('HANDOFF.md', 'markers.json', 'validation.json'):
        shutil.copyfile(source / name, preserved / name)
    for path in packet.glob('*.json'):
        shutil.copyfile(path, preserved / path.name)
    bundle = ROOT / 'game/data/necrotic_media'
    path = bundle / 'bindings.json'
    current = json.loads(path.read_text())
    for key in ('resources', 'projectileStorage'):
        current.setdefault(key, {}).update(bindings[key])
    path.write_text(json.dumps(current, indent=2) + '\n')
    path = bundle / 'projectile-assets.json'
    current_assets = {row['assetId']: row for row in json.loads(path.read_text())}
    current_assets.update({row['assetId']: row for row in assets})
    path.write_text(json.dumps(list(current_assets.values()), separators=(',', ':')) + '\n')
    path = ROOT / 'game/data/condition-media.json'
    current = json.loads(path.read_text())
    for identity, layer in json.loads(media.model_dump_json(by_alias=True))['layers'].items():
        if identity in current['layers']:
            layer['scale'] = current['layers'][identity]['scale']
        current['layers'][identity] = layer
    path.write_text(json.dumps(current, indent=2) + '\n')
    (preserved / 'installed.json').write_text(json.dumps(files, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    import_markers(parser.parse_args().source)
