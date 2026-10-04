"""Capture the accepted small flame/trail at eight native projectile headings.

The camera follows the original moving emitter, leaving owner-local pixels for
the existing projectile sampler. The review fixture's launch/recipient positions
are never baked into a production trajectory.
"""

import argparse
import hashlib
import json
from math import pi, sqrt
from pathlib import Path
import subprocess

SOURCE = Path('/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/nature-utility-batch')
PROJECT = SOURCE.parent / 'godot-library/projects/lelu-godot-fire-premium'


def windows(path: Path) -> str:
    return subprocess.check_output(['wslpath', '-w', str(path.resolve())], text=True).strip()


def capture(output: Path, heading: int, side: str) -> None:
    folder = output / f'd{heading}' / side
    folder.mkdir(parents=True, exist_ok=True)
    source = (SOURCE / 'authoring/ProduceCapture.gd').read_text()
    script = source.replace('KIND_VALUE', 'produce-throw').replace('FRONT_VALUE', str(side == 'front').lower())
    script = script.replace('asset.rotation.y=-PI/2.', f'asset.rotation.y=-PI/2.+{heading*pi/4}')
    start, end = script.index('func _process('), script.index('func _zero_postprocess_dark_alpha_pixels(')
    # Retain the original travel velocity, trail width/lifetime, nine sparks,
    # particle seed, geometry, shaders and palette. Only remove the fixture's
    # destination cutoff and follow its emitter with the orthographic camera.
    script = script[:start] + f'''func _process(_delta:float)->void:
 if asset==null:return
 tick+=1;var age=float(tick)/144.
 var direction=Vector3.RIGHT.rotated(Vector3.UP,{heading*pi/4})
 asset.position=direction*(3.65/.45)*age
 camera.position=Vector3(24.,19.595917942,24.)+asset.position
 for mat in mats:
  mat.set_shader_parameter("fx_clock",fposmod(age-.25,2.))
  mat.set_shader_parameter("opacity",1.)
  mat.set_shader_parameter("split_center",asset.position.x+asset.position.z)
''' + script[end:]
    fingerprint = hashlib.sha256(script.encode()).hexdigest()
    receipt_path = folder / 'source.json'
    if receipt_path.is_file() and (folder / 'capture.json').is_file():
        receipt = json.loads(receipt_path.read_text())
        if receipt['adapter_sha256'] != fingerprint:
            raise ValueError(f'Existing capture uses another source: {folder}')
        if len(tuple((folder / 'frames').glob('*.png'))) == 64:
            print(f'Retained {folder}', flush=True)
            return
    name = f'ProductionProduceTravel_{heading}_{side}'
    exporter = PROJECT / 'codexfx_exporter'
    (exporter / (name + '.gd')).write_text(script)
    (exporter / (name + '.tscn')).write_text((exporter / 'ExactProjectileCameraRecorder.tscn')
        .read_text().replace('ExactProjectileCameraRecorder.gd', name + '.gd'))
    (folder / 'adapter.gd').write_text(script)
    command = json.loads((SOURCE / 'native-v1/produce-throw-front/command.json').read_text())
    command[command.index('--') - 1] = 'res://codexfx_exporter/' + name + '.tscn'
    updates = {'--path': windows(PROJECT), '--output': windows(folder / 'strip.png'),
        '--frames-dir': windows(folder / 'frames'), '--manifest': windows(folder / 'capture.json'),
        '--frames': '64', '--sample-times-seconds': ','.join(str(.25+(i+1)/32) for i in range(64)),
        '--viewport-size': '192,192', '--resolution': '192x192',
        '--ortho-size': str(192/(64*sqrt(2)*.9)),
        '--camera-position': '24,19.595917942,24', '--camera-target': '0,0,0'}
    for key, value in updates.items():
        command[command.index(key) + 1] = value
    (folder / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    with (folder / 'capture.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    log = (folder / 'capture.log').read_text()
    if 'SCRIPT ERROR' in log or 'SHADER ERROR' in log or len(tuple((folder / 'frames').glob('*.png'))) != 64:
        raise ValueError(f'Incomplete source capture: {folder}; inspect capture.log')
    receipt_path.write_text(json.dumps({'source': str(SOURCE / 'authoring/ProduceCapture.gd'),
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'adapter_sha256': fingerprint,
        'heading_radians': heading*pi/4, 'side': side, 'frames': 64, 'fps': 32,
        'cell': [192, 192], 'pivot': [96, 96], 'original_travel_speed': 3.65/.45,
        'trail_seconds': .035, 'spark_count': 9, 'spark_lifetime': .1,
        'adaptation': 'Original emitter moving at source velocity; camera tracks its center; accepted hold material clock loops at two seconds; no fixture endpoints.'}, indent=2) + '\n')
    print(f'Captured {folder}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--heading', type=int, choices=range(8))
    parser.add_argument('--side', choices=('back', 'front'))
    args = parser.parse_args()
    for heading in range(8) if args.heading is None else (args.heading,):
        for side in ('back', 'front') if args.side is None else (args.side,):
            capture(args.output, heading, side)
