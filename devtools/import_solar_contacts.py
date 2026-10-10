"""Register accepted radiant contact and a literal forward-hand crop."""

import argparse
import json
from pathlib import Path

from PIL import Image

from devtools.import_registered_media import DIRECTIONS
from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage

ROOT = Path(__file__).resolve().parents[1]


def import_contacts(source: Path, *, preserved: Path, production: Path, repo: Path = ROOT) -> None:
    contacts = 'holy-guardians-study/assets/contact-radiant.png'
    hands = 'cantrips-review/actors/sacred_flame/hand-glow.png'
    sockets_path = 'electric-live-study/cast-assets/hand-sockets.json'
    sockets = json.loads(contained_media_path(source, sockets_path).read_text())
    digests = {contacts: 'eb99bbf86c78fb197241fb9de3b65245f9b041ef5cd1b616359cdc27688c3461',
        hands: sockets['sourceSha256']}
    for path, dimensions in ((contacts, (1280, 1344)), (hands, (1920, 1024))):
        with Image.open(contained_media_path(source, path)) as im:
            if im.mode != 'RGBA' or im.size != dimensions:
                raise ValueError('Accepted solar contact dimensions changed')
    bundle = repo/'game/data/weather_solar_media'
    bindings = json.loads((bundle/'bindings.json').read_text())
    assets = {row['assetId']: row for row in json.loads((bundle/'projectile-assets.json').read_text())}
    root = 'game/assets/weather_solar_media/contacts'
    selections = {}
    for identity, size, count, pivot in (
            ('holy.contact.radiant', (160, 224), 48, (80, 150)),
            ('solar.sunbeam.hand', (23, 23), 1, (11, 11))):
        views, anchors = {}, {}
        for row, facing in enumerate(DIRECTIONS):
            if count == 48:
                views[facing] = [[{'file': root+'/contact-radiant.png',
                    'rect': [frame%8*160, frame//8*224, 160, 224], 'offset': [0, 0]}] for frame in range(48)]
            else:
                sx, sy = sockets['sockets'][row][7]
                x, y = round(sx)-11, round(sy)-11
                views[facing] = [[{'file': root+'/hand-glow.png', 'rect': [7*128+x, row*128+y, 23, 23], 'offset': [0, 0]}]]
                anchors[facing] = {'x': (sx-x)/23, 'y': (sy-y)/23}
                with Image.open(source/hands) as im:
                    crop = im.crop((7*128+x, row*128+y, 7*128+x+23, row*128+y+23)).getchannel('A')
                    if any(crop.getpixel(p) for i in range(23) for p in ((i, 0), (i, 22), (0, i), (22, i))):
                        raise ValueError('The literal forward-hand crop clips source pixels')
            selections[identity] = {'phases': {'impact': {'layers': [{'partsByFacing': views, 'blendMode': 'normal'}]}}}
        asset = {'assetId': identity, 'displayName': identity, 'sheet': '/'+identity+'.png',
            'frame': {'width': size[0], 'height': size[1], 'rows': 8, 'cols': count}, 'fps': 32,
            'rowOrder': list(DIRECTIONS), 'phases': {'impact': {'start': 0, 'frames': count, 'fps': 32, 'loop': count == 1}},
            'anchor': {'x': pivot[0]/size[0], 'y': pivot[1]/size[1]}, 'defaultScale': 1,
            'palettePreview': {'colors': [0xf7d366]}}
        if anchors:
            asset['anchorsByFacing'] = anchors
        AuthoredProjectileAsset.model_validate_json(json.dumps(asset))
        ProjectileStorage.model_validate_json(json.dumps(selections[identity]))
        assets[identity] = asset
    metadata = []
    for relative in (sockets_path, 'holy-guardians-study/manifest.json'):
        value = contained_media_path(source, relative).read_bytes()
        target = contained_media_path(preserved, relative)
        if target.exists() and target.read_bytes() != value:
            raise ValueError('Preserved solar metadata differs')
        metadata.append((target, value))
    files = install_verified_payloads(source, tuple((path, root+'/'+Path(path).name, digest)
        for path, digest in digests.items()), preserved=preserved, production=production, repo=repo)
    for target, value in metadata:
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(value)
    bindings['projectileStorage'].update(selections)
    bindings['resources']['/weather-solar/Attack5-hand-glow.png'] = root+'/hand-glow.png'
    (bundle/'bindings.json').write_text(json.dumps(bindings, separators=(',', ':'))+'\n')
    (bundle/'projectile-assets.json').write_text(json.dumps(list(assets.values()), separators=(',', ':'))+'\n')
    (bundle/'contacts-source.json').write_text(json.dumps({'source': str(source), 'preserved': str(preserved),
        'files': files, 'identities': list(selections), 'hand_adaptation':
        'Unchanged 23x23 forward cluster from original Attack5 frame 7, anchored by delivered hand sockets to the current actor hand; other-hand cluster omitted.',
        'contact_adaptation': 'Unchanged holy contact, 48 frames at 32 FPS, pivot (80,150), source worldPixels=160/3.1.'}, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'preserved', 'production'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    import_contacts(args.source, preserved=args.preserved, production=args.production)
