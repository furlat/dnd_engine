"""Offline page packing preserves every addressed pixel and spatial registration."""

import hashlib
import json

from PIL import Image
import pytest

from devtools.repack_registered_media import repack_bank


def test_repacked_animation_keeps_exact_alpha_offsets_and_empty_samples(tmp_path):
    source = tmp_path / 'original'
    source.mkdir()
    image = Image.new('RGBA', (9, 7))
    image.putpixel((2, 3), (25, 87, 196, 31))
    image.putpixel((4, 4), (252, 3, 49, 254))
    image.save(source / 'atlas.png')
    row = {'fps': 32, 'frames': 3, 'cell': 128, 'pivot': [64, 92.25],
        'cameras': {str(q): {'layers': {side: {'pages': ['atlas.png'], 'frames': [
            {'page': 0, 'source': [2, 3, 3, 2], 'offset': [17, 29]}, None,
            {'page': 0, 'source': [4, 4, 1, 1], 'offset': [21, 30]}]}
            for side in ('back', 'front')}} for q in range(4)}}
    (source / 'media.json').write_text(json.dumps({'bank': row}))
    payload = (source / 'atlas.png').read_bytes()
    (source / 'SHA256SUMS').write_text(hashlib.sha256(payload).hexdigest() + '  atlas.png\n')
    output = tmp_path / 'packed'
    receipt = repack_bank(source, 'bank', output, page_size=16)
    packed = json.loads((output / 'media.json').read_text())['bank']
    assert receipt['exact_rgba_crops_verified'] == 16
    assert (packed['fps'], packed['frames'], packed['pivot']) == (32, 3, [64, 92.25])
    for q, camera in packed['cameras'].items():
        for side, layer in camera['layers'].items():
            original = row['cameras'][q]['layers'][side]
            for before, after in zip(original['frames'], layer['frames'], strict=True):
                if before is None:
                    assert after is None
                    continue
                assert after['offset'] == before['offset']
                x, y, w, h = before['source']
                px, py, pw, ph = after['source']
                with Image.open(output / layer['pages'][after['page']]) as atlas:
                    assert atlas.crop((px, py, px+pw, py+ph)).tobytes() == image.crop((x, y, x+w, y+h)).tobytes()
    assert (source / 'atlas.png').read_bytes() == payload
    with pytest.raises(ValueError, match='new'):
        repack_bank(source, 'bank', output)
    (source / 'atlas.png').write_bytes(b'corrupt')
    rejected = tmp_path / 'rejected'
    with pytest.raises(ValueError, match='Unverified'):
        repack_bank(source, 'bank', rejected)
    assert not rejected.exists()
