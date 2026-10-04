"""Install the accepted electric components without generating layout-specific art."""
import argparse
import hashlib
import json
from pathlib import Path

from devtools.media_delivery import contained_media_path, install_verified_payloads

ROOT = Path(__file__).resolve().parents[1]


def import_electric_media(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> dict:
    manifest = json.loads((source / 'components.json').read_text())
    payloads = [('assets/' + name, 'game/assets/electric_media/' + name, entry['sha256'])
                for name, entry in manifest['files'].items()]
    hand = 'cast-assets/lightning-hands.png'
    payloads.append((hand, 'game/assets/electric_media/lightning-hands.png',
                     hashlib.sha256((source / hand).read_bytes()).hexdigest()))
    metadata = []
    source_hashes = {}
    for name in ('components.json', 'CAST_HANDOFF.md', 'LIGHTNING_BOLT.md', 'lifecycle.js',
                 'spell.js', 'bolt.js', 'cast-assets/hand-sockets.json'):
        origin = contained_media_path(source, name)
        destination = contained_media_path(preserved, name)
        content = origin.read_bytes()
        if destination.exists() and (not destination.is_file() or destination.read_bytes() != content):
            raise ValueError(f'Preserved electric source differs: {name}')
        metadata.append((destination, content))
        source_hashes[name] = hashlib.sha256(content).hexdigest()
    bundle = repo / 'game/data/electric_media'
    bindings_path = bundle / 'bindings.json'
    bindings = json.loads(bindings_path.read_text()) if bindings_path.exists() else {'spells': {}, 'resources': {}}
    files = install_verified_payloads(source, tuple(payloads), preserved=preserved,
        production=production, repo=repo)
    for destination, content in metadata:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    bundle.mkdir(parents=True, exist_ok=True)
    for _, runtime, _ in payloads:
        bindings['resources']['/electric/' + Path(runtime).name] = runtime
    bindings_path.write_text(json.dumps(bindings, indent=2) + '\n')
    asset_path = bundle / 'projectile-assets.json'
    if not asset_path.exists():
        asset_path.write_text('[]\n')
    receipt = {'source': str(source), 'preserved': str(preserved), 'files': files, 'source_sha256': source_hashes}
    (bundle / 'electric-source.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('source', 'preserved', 'production'):
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    receipt = import_electric_media(args.source, preserved=args.preserved, production=args.production)
    print(f"Installed {len(receipt['files'])} original electric components")
