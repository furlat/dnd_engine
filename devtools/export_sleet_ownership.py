"""Capture surface coordinates from the accepted Sleet Storm operator and clock.

The delivered RGBA remains byte-exact; this companion pass changes only shader
outputs and storage format in a private copy of its original Godot project.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile

import numpy as np
from PIL import Image

from devtools.export_solar_ownership import COORDINATES, record_source_project, windows


def capture(source: Path, project_source: Path, output: Path) -> None:
    project = output / 'project'
    record_source_project(project_source, output/'sleet-source-project.json')
    if not project.exists():
        shutil.copytree(project_source, project)
    exporter = project / 'codexfx_exporter'
    original = (exporter / 'ExactProjectileCameraRecorder.gd').read_text()
    recorder = original.replace('_configure_viewport()', '_configure_viewport()\n\tget_viewport().use_hdr_2d=true')
    recorder = recorder.replace('image.convert(Image.FORMAT_RGBA8)\n\t\t_zero_postprocess_dark_alpha_pixels(image)',
                                'image.convert(Image.FORMAT_RGBAF)')
    recorder = recorder.replace('var frame_err := image.save_png(frame_path)',
        'FileAccess.open(frame_path.replace(".png",".bin"),FileAccess.WRITE).store_buffer(image.get_data())\n\t\tvar frame_err := OK')
    start, end = recorder.index('\tvar sheet := _build_sheet'), recorder.index('\n\t_write_manifest')
    recorder = recorder[:start]+recorder[end:]
    (exporter / 'ExactSleetOwnership.gd').write_text(recorder)
    helper = '''
func ownership(code:String)->String:
 code=code.replace("ALPHA","ownership_alpha")
 var start=code.find("void fragment()")
 var at=code.find("{",start)+1
 var depth=1
 while at<code.length() and depth>0:
  if code[at]=="{":depth+=1
  elif code[at]=="}":depth-=1
  at+=1
 code=code.insert(at-1,COORDINATES)
 code=code.insert(code.find("{",start)+1,"float ownership_alpha=1.;")
 return code.replace("depth_draw_never","depth_draw_always")
'''.replace('COORDINATES', json.dumps(COORDINATES))
    for side in ('ground', 'back', 'front'):
        target = output / side
        target.mkdir(parents=True, exist_ok=True)
        script = (source / 'authoring/SleetCapture.gd').read_text().replace('SIDE_NAME', side)
        script = script.replace('ExactProjectileCameraRecorder.gd', 'ExactSleetOwnership.gd')
        script = script.replace('s.code=code;m.shader=s;', 's.code=ownership(code);m.shader=s;')+helper
        digest = hashlib.sha256((script+recorder).encode()).hexdigest()
        complete = target / 'complete.json'
        if complete.exists() and json.loads(complete.read_text())['adapter_sha256'] == digest:
            continue
        name = 'SleetOwnership_'+side
        (exporter / (name+'.gd')).write_text(script)
        (target / (name+'.gd')).write_text(script)
        (target / 'ExactSleetOwnership.gd').write_text(recorder)
        scene = (exporter / 'ExactProjectileCameraRecorder.tscn').read_text().replace('ExactProjectileCameraRecorder.gd', name+'.gd')
        (exporter / (name+'.tscn')).write_text(scene)
        native = source / ('native-v4' if side == 'ground' else 'native-v5') / side
        command = json.loads((native / 'command.json').read_text())
        command[command.index('--')-1] = 'res://codexfx_exporter/'+name+'.tscn'
        for option, value in {'--path': windows(project), '--output': windows(target/'strip.png'),
                '--frames-dir': windows(target/'frames'), '--manifest': windows(target/'capture.json')}.items():
            command[command.index(option)+1] = value
        (target / 'command.json').write_text(json.dumps(command, indent=2))
        with (target / 'capture.log').open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=240)
        log = (target / 'capture.log').read_text()
        if result.returncode or 'SCRIPT ERROR' in log or 'SHADER ERROR' in log:
            raise ValueError(log[-6000:])
        captured = json.loads((target / 'capture.json').read_text())['captured']
        if len(captured) != 128 or any(row['actual_tick'] != row['target_tick'] for row in captured):
            raise ValueError('Sleet source clock mismatch')
        complete.write_text(json.dumps(dict(adapter_sha256=digest, frames=128)))
        print('Captured', side, flush=True)


def pack(source: Path, output: Path) -> None:
    manifest = json.loads((source / 'media.json').read_text())
    receipts = []
    for side, bank in manifest['layers'].items():
        archive = output / ('sleet-'+side+'-surface.zip')
        temporary = archive.with_suffix('.zip.tmp')
        checks = []
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as target:
            for frame, address in enumerate(bank['frames']):
                raw = np.frombuffer((output / side / 'frames' / f'frame_{frame:03d}.bin').read_bytes(), dtype='<f4').reshape(640, 640, 4)
                points = raw[:, :, :3] / np.maximum(raw[:, :, 3, None], .00001)*32-16
                if address is None:
                    ox, oy, w, h = 0, 0, 1, 1
                    color = np.zeros((1, 1, 4), dtype=np.uint8)
                else:
                    px, py, w, h = address['source']; ox, oy = address['offset']
                    page = np.asarray(Image.open(source / bank['pages'][address['page']]).convert('RGBA'))
                    color = page[py:py+h, px:px+w].copy()
                need = color[:, :, 3] > 0
                points = points[oy:oy+h, ox:ox+w]
                missing = int(np.sum(need & (raw[oy:oy+h, ox:ox+w, 3] == 0)))
                if missing or np.any(~np.isfinite(points[need])) or np.any(np.abs(points[need]) >= 64):
                    raise ValueError(f'{side}/{frame}: missing={missing} invalid coordinates')
                quantized = np.rint((points+64)*65535/128).astype('>u2'); quantized[~need] = 0
                decoded = quantized.astype(float)*128/65535-64
                pivot = manifest['pivot']; pixels = 640/manifest['ortho']
                projected_x = (decoded[:, :, 0]-decoded[:, :, 2])/2**.5*pixels+pivot[0]
                projected_y = ((decoded[:, :, 0]+decoded[:, :, 2])*.3535533906-decoded[:, :, 1]*.86602540378)*pixels+pivot[1]
                gy, gx = np.indices((h, w))
                error = np.hypot(projected_x-gx-ox-.5, projected_y-gy-oy-.5)[need]
                maximum = float(error.max()) if len(error) else 0.
                if maximum > .8:
                    raise ValueError(f'{side}/{frame}: camera mismatch {maximum}')
                payload = struct.pack('<HHhh', w, h, ox-round(pivot[0]), oy-round(pivot[1]))+color.tobytes()+quantized.tobytes()+need.astype(np.uint8).tobytes()
                target.writestr(f'{frame:03d}.bin.gz', gzip.compress(payload, compresslevel=6, mtime=0))
                checks.append(dict(frame=frame, rgbaExact=True, ownedPixels=int(need.sum()), missingOwnership=missing, maxCameraErrorPixels=maximum))
        temporary.replace(archive)
        receipts.append(dict(bank='sleet-'+side, file=archive.name, sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            pivot=manifest['pivot'], frames=128, worldPixels=640/manifest['ortho'], checks=checks,
            adapter=json.loads((output / side / 'complete.json').read_text())))
    (output / 'sleet-ownership.json').write_text(json.dumps(dict(source=str(source),
        production_rgba_recaptured=False, accepted_rgba_byte_exact=True,
        source_metadata_sha256=hashlib.sha256((source/'media.json').read_bytes()).hexdigest(),
        bounds=[-64, 64], verticalScale=1.224744871391589, coordinateBasis='camera_local_xyz', banks=receipts), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'project', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    capture(args.source, args.project, args.output)
    pack(args.source, args.output)
