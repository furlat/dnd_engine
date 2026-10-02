"""Bake the approved pause-bar reference into the existing condition media schema."""

import argparse
import hashlib
import json
from math import floor, pi, sin
from pathlib import Path

from PIL import Image, ImageDraw

from devtools.import_registered_media import import_registered_bank

REFERENCE_SHA = '1e374d54c4edc318b2499690cf5165e40cdf1615ddf5fcf9cc62857affcebee1'


def bake_pause_bars(reference: Path, output: Path, repo: Path) -> None:
    if hashlib.sha256(reference.read_bytes()).hexdigest() != REFERENCE_SHA:
        raise ValueError('Pause bars require the pinned approved reference')
    output.mkdir(parents=True, exist_ok=True)
    rows = {}
    checksums = []
    for phase, count in (('apply', 10), ('hold', 64)):
        sheet = Image.new('RGBA', (32 * count, 32))
        draw = ImageDraw.Draw(sheet)
        frames = []
        for frame in range(count):
            age = frame / 32 if phase == 'apply' else frame / 32 + 2
            inward = max(0., 1-age/.3)*7
            pulse = .5 + .5 * sin(age*pi)
            for side in (-1, 1):
                x = 32*frame + floor(16 + side*(4+inward)-2 + .5)
                draw.rectangle((x, 7, x+3, 19), fill='#996b30')
                x = 32*frame + floor(16 + side*(4+inward)-1 + .5)
                draw.rectangle((x, 6, x+1, 16), fill='#fff0bf' if pulse > .45 else '#e5b454')
            frames.append({'page': 0, 'source': [32*frame,0,32,32], 'offset': [0,0]})
        name = 'incapacitated_'+phase
        relative = name+'.png'
        sheet.save(output/relative)
        checksums.append(hashlib.sha256((output/relative).read_bytes()).hexdigest()+'  '+relative)
        rows[name]={'fps':32,'frames':count,'cell':32,'ortho':16,'pivot':[16,20],
            'palette':['996b30','fff0bf','e5b454'], 'cameras': {str(q): {'layers': {
                'back': {'pages': [], 'frames': [None]*count},
                'front': {'pages': [relative], 'frames': frames}}} for q in range(4)}}
    (output/'SHA256SUMS').write_text('\n'.join(checksums)+'\n')
    (output/'media.json').write_text(json.dumps(rows,indent=2)+'\n')
    for phase in ('apply', 'hold'):
        row=rows['incapacitated_'+phase]
        import_registered_bank(output,row,'incapacitated',((phase,0,row['frames']),),
            repo,bundle='control_media',default_scale=.5)
    (output/'reference-receipt.json').write_text(json.dumps({'reference':str(reference),
        'sha256':REFERENCE_SHA, 'native_fps':32, 'source_function':'incapacitated',
        'registration':'Actual actor head, original bars translated from fixture y-80..y-66'},indent=2)+'\n')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repo',type=Path,required=True)
    args=parser.parse_args()
    bake_pause_bars(args.reference,args.output,args.repo)
