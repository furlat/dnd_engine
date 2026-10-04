"""Install preserved original transport artwork and faithful native camera views."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from devtools.import_registered_media import import_registered_bank, validate_billboard_bank
from devtools.media_delivery import contained_media_path, install_verified_payloads

ROOT = Path(__file__).resolve().parents[1]


def import_transport_media(source: Path, *, preserved: Path, production: Path,
                           program: str, repo: Path = ROOT) -> dict:
    manifest = source / 'manifest.json'
    row = json.loads(manifest.read_text())
    metadata = tuple((name, (source/name).read_bytes()) for name in ('manifest.json','SHA256SUMS'))
    for name, content in metadata:
        destination = contained_media_path(preserved,name)
        if destination.exists() and destination.read_bytes() != content:
            raise ValueError(f'Preserved transport registration changed: {name}')
    hashes = dict((parts[1],parts[0]) for line in (source/'SHA256SUMS').read_text().splitlines()
                  if (parts := line.split(maxsplit=1)))
    selected = tuple(dict.fromkeys(page for camera in row['cameras'].values()
        for layer in camera['layers'].values() for page in layer['pages']))
    for relative in selected:
        if hashlib.sha256(contained_media_path(source,relative).read_bytes()).hexdigest() != hashes.get(relative):
            raise ValueError(f'Transport source checksum mismatch: {relative}')
    # Validate every camera and crop before publishing artwork or selected bindings.
    if row['fps'] != 32 or set(row['cameras']) != {'0','1','2','3'}:
        raise ValueError('Transport delivery needs its actual four camera banks at 32FPS')
    for camera in row['cameras'].values():
        validate_billboard_bank({**row, 'layers': camera['layers']})
        for layer in camera['layers'].values():
            dimensions = []
            for relative in layer['pages']:
                with Image.open(contained_media_path(source, relative)) as page:
                    page.verify()
                    dimensions.append(page.size)
            for frame in layer['frames']:
                if frame is None:
                    continue
                x, y, width, height = frame['source']
                page_width, page_height = dimensions[frame['page']]
                if x + width > page_width or y + height > page_height:
                    raise ValueError('Transport frame crop leaves its atlas page')
    bundle = 'transport_media'
    files = install_verified_payloads(source,tuple((name,f'game/assets/{bundle}/{name}',hashes[name])
        for name in selected),preserved=preserved,production=production,repo=repo)
    preserved.mkdir(parents=True,exist_ok=True)
    for name,content in metadata:
        (preserved/name).write_bytes(content)
    identities = import_registered_bank(source,row,program,(('finite',0,row['frames']),),repo,
        bundle=bundle,default_scale=1)
    receipt={'source':str(source),'preserved':str(preserved),'files':files,'identities':identities,
        'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}
    (repo/'game/data'/bundle/f'{program}-source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','preserved','production'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--program',choices=('dimension_door','banishment'),required=True)
    args=parser.parse_args()
    result=import_transport_media(args.source,preserved=args.preserved,production=args.production,program=args.program)
    print(f"Installed {len(result['files'])} original transport pages")
