"""Export paired source-rendered solar colour and surface ownership.

Offline adapter for the delivered Godot operators. Their original clocks,
geometry, shaders, particles, camera and MSAA coverage remain authoritative.
A floating-point coordinate pass avoids byte-channel blending at MSAA edges.
Burst retains accepted RGBA. Beam recaptures RGBA and coordinates from the same
frozen source particle state; the accepted delivery remains archived separately.
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


GODOT = Path('/mnt/c/Users/tommaso/Documents/Dev/CodexFX/tools/godot/windows/Godot_v4.6.2-stable_win64_console.exe')
COORDINATES = '''
 if(ownership_alpha <= .000001) discard;
 vec3 ownership_world=(INV_VIEW_MATRIX*vec4(VERTEX,1.)).xyz;
 ALBEDO=(ownership_world+vec3(16.))/32.;EMISSION=vec3(0.);
'''


def windows(path: Path) -> str:
    return subprocess.check_output(['wslpath', '-w', str(path.resolve())], text=True).strip()


def record_source_project(project: Path, destination: Path) -> None:
    """Pin the unmodified source project inputs, excluding generated caches."""
    files = {path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(project.rglob('*')) if path.is_file()
        and not {'.godot', '.git'}.intersection(path.relative_to(project).parts)}
    encoded = json.dumps({'source_project': str(project.resolve()), 'files': files}, indent=2)+'\n'
    if destination.exists() and destination.read_text() != encoded:
        raise ValueError('The source project changed after this capture; use a fresh export directory')
    destination.write_text(encoded)


def capture(source: Path, project_source: Path, output: Path, program: str) -> None:
    """Capture one bounded job from a private copy of the original project."""
    project = output / 'project'
    record_source_project(project_source, output/(program+'-source-project.json'))
    if not project.exists():
        shutil.copytree(project_source, project)
    exporter, target = project / 'codexfx_exporter', output / (program+'-opaque')
    target.mkdir(parents=True, exist_ok=True)
    if program == 'burst':
        script = (source / 'authoring/SunburstCapture.gd').read_text()
        shader = (source / 'authoring/solar-burst.gdshader').read_text().replace('depth_draw_never', 'depth_draw_always')
        shader = shader.replace('ALPHA', 'ownership_alpha').replace('void fragment(){', 'void fragment(){float ownership_alpha=1.;')
        at = shader.rfind('}')
        (exporter / 'OwnershipBurst.gdshader').write_text(shader[:at]+COORDINATES+shader[at:])
        (target / 'OwnershipBurst.gdshader').write_text(shader[:at]+COORDINATES+shader[at:])
        script = script.replace('solar-burst.gdshader', 'OwnershipBurst.gdshader')
        script = script.replace('var sheet=Image.create(512*8,384*8,false,Image.FORMAT_RGBA8)', 'pass')
        script = script.replace('sheet.blit_rect(im,Rect2i(0,0,512,384),Vector2i(f%8*512,f/8*384))',
            'FileAccess.open(folder+"/"+side+"-"+str(f)+".bin",FileAccess.WRITE).store_buffer(im.get_data())')
        script = script.replace('sheet.save_png(folder+"/burst-"+side+".png");print("BURST ",side)', 'print("BURST ",side)')
    else:
        script = (source / 'authoring/SolarBeamCapture.gd').read_text()
        helper = '''
func ownership_shader(code:String)->String:
 code=code.replace("ALPHA","ownership_alpha")
 var start=code.find("void fragment()")
 assert(start>=0)
 var at=code.find("{",start)+1
 var depth=1
 while at<code.length() and depth>0:
  if code[at]=="{":depth+=1
  elif code[at]=="}":depth-=1
  at+=1
 code=code.insert(at-1,COORDINATES)
 code=code.insert(code.find("{",start)+1,"float ownership_alpha=1.;")
 return code.replace("depth_draw_never","depth_draw_always").replace("blend_add","blend_mix")
'''.replace('COORDINATES', json.dumps(COORDINATES))
        script += helper
        script = script.replace('var sheet=Image.create(512*4,384*12,false,Image.FORMAT_RGBA8)', 'pass')
        script = script.replace('sheet.blit_rect(im,Rect2i(0,0,512,384),Vector2i(frame%4*512,frame/4*384))', '''im.save_png(folder+"/beam-"+str(dir)+"-"+str(frame)+".png")
   # Freeze this exact particle/animation state for its coordinate companion.
   var old_process=n.process_mode;n.process_mode=Node.PROCESS_MODE_DISABLED
   var particles=[]
   for child in n.find_children("*","GPUParticles3D",true,false):
    particles.append([child,child.speed_scale]);child.speed_scale=0.
   var originals=[]
   for m in mats:
    originals.append(m.shader);var coordinates=Shader.new();coordinates.code=ownership_shader(m.shader.code);m.shader=coordinates
   vp.use_hdr_2d=true
   await process_frame;await RenderingServer.frame_post_draw
   var points=vp.get_texture().get_image();points.convert(Image.FORMAT_RGBAF)
   FileAccess.open(folder+"/beam-"+str(dir)+"-"+str(frame)+".bin",FileAccess.WRITE).store_buffer(points.get_data())
   vp.use_hdr_2d=false
   for index in range(mats.size()):mats[index].shader=originals[index]
   for pair in particles:pair[0].speed_scale=pair[1]
   n.process_mode=old_process''')
        script = script.replace('sheet.save_png(folder+"/beam-"+str(dir)+".png");print("BEAM ",dir)', 'print("BEAM ",dir)')
    if program == 'burst':
        script = script.replace('vp.transparent_bg=true;', 'vp.transparent_bg=true;vp.use_hdr_2d=true;')
        script = script.replace('im.convert(Image.FORMAT_RGBA8)', 'im.convert(Image.FORMAT_RGBAF)')
    digest = hashlib.sha256(script.encode()).hexdigest()
    completed_path = target / 'complete.json'
    if completed_path.exists() and json.loads(completed_path.read_text())['adapter_sha256'] == digest:
        return
    name = 'OwnershipSolar.gd'
    (exporter / name).write_text(script)
    (target / name).write_text(script)
    args = [str(GODOT), '--path', windows(project), '--rendering-method', 'forward_plus',
        '--rendering-driver', 'vulkan', '--audio-driver', 'Dummy', '--resolution', '64x64',
        '--fixed-fps', '32', '--script', 'res://codexfx_exporter/'+name, '--', windows(target), '--full']
    with (target / 'capture.log').open('w') as log:
        completed = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, timeout=480)
    log = (target / 'capture.log').read_text()
    if completed.returncode or 'SCRIPT ERROR' in log or 'SHADER ERROR' in log:
        raise ValueError(log[-6000:])
    expected = 128 if program == 'burst' else 384
    if len(tuple(target.glob('*.bin'))) != expected:
        raise ValueError('Incomplete native coordinate export')
    completed_path.write_text(json.dumps(dict(program=program, frames=expected, adapter_sha256=digest)))


def source_colour(path: Path, palette: Image.Image) -> Image.Image:
    """The delivered pack.py's straight-alpha and fixed-palette operation."""
    color = np.asarray(Image.open(path).convert('RGBA'), dtype=np.float32).copy()
    alpha = color[:, :, 3]
    rgb = color[:, :, :3] / 255
    linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
    linear = np.minimum(1, linear * 255 / np.maximum(alpha[:, :, None], 1))
    color[:, :, :3] = np.where(linear <= .0031308, linear * 12.92,
                                1.055 * linear ** (1 / 2.4) - .055) * 255
    color[alpha < 3] = 0
    original = Image.fromarray(color.astype('uint8'))
    quantized = original.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE).convert('RGBA')
    quantized.putalpha(original.getchannel('A'))
    return quantized


def pack(source: Path, output: Path, program: str, palette_path: Path | None) -> None:
    manifest = json.loads((source / 'manifest.json').read_text())
    palette = Image.new('P', (1, 1))
    if program == 'beam':
        if palette_path is None:
            raise ValueError('Paired beam export requires the delivered Sacred Flame palette')
        colors = json.loads(palette_path.read_text())['colors']
        palette.putpalette(sum(colors, []) + colors[-1] * (256-len(colors)))
    receipts = []
    for name, bank in manifest['banks'].items():
        if not name.startswith(program):
            continue
        rgba_page = np.asarray(Image.open(source / bank['file']).convert('RGBA'))
        archive = output / (name + '-surface.zip')
        temporary = archive.with_suffix('.zip.tmp')
        checks = []
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as target:
            for frame, address in enumerate(bank['frames']):
                key = name.removeprefix('burst-') if program == 'burst' else name
                raw = np.frombuffer((output / (program+'-opaque') / f'{key}-{frame}.bin').read_bytes(), dtype='<f4').reshape(384, 512, 4)
                points = raw[:, :, :3] / np.maximum(raw[:, :, 3, None], .00001) * 32 - 16
                if program == 'beam':
                    picture = source_colour(output / (program+'-opaque') / f'{key}-{frame}.png', palette)
                    ox, oy, right, bottom = picture.getbbox() or (0, 0, 1, 1)
                    w, h = right-ox, bottom-oy
                    color = np.asarray(picture.crop((ox, oy, right, bottom)))
                else:
                    px, py, w, h = address['source']; ox, oy = address['offset']
                    color = rgba_page[py:py+h, px:px+w].copy()
                need = color[:, :, 3] > 0
                points = points[oy:oy+h, ox:ox+w]
                missing = int(np.sum(need & (raw[oy:oy+h, ox:ox+w, 3] == 0)))
                if missing or np.any(~np.isfinite(points[need])) or np.any(np.abs(points[need]) >= 64):
                    raise ValueError(f'{name}/{frame}: source ownership is incomplete or out of bounds ({missing})')
                owner = need.astype(np.uint8)
                # MSAA may shade a silhouette at a pixel center outside the
                # triangle. Retain that source position (never clamp it into
                # the effect); native volume admission owns the eventual cut.
                quantized = np.rint((points+64)*65535/128).astype('>u2'); quantized[~need] = 0
                decoded = quantized.astype(float)*128/65535-64
                pivot = bank['pivot']; pixels = bank['worldPixels']
                projected_x = (decoded[:, :, 0]-decoded[:, :, 2])/2**.5*pixels+pivot[0]
                projected_y = ((decoded[:, :, 0]+decoded[:, :, 2])*.3535533906-decoded[:, :, 1]*.86602540378)*pixels+pivot[1]
                gy, gx = np.indices((h, w))
                error = np.hypot(projected_x-gx-ox-.5, projected_y-gy-oy-.5)[need]
                maximum = float(error.max()) if len(error) else 0.
                if maximum > .8:
                    raise ValueError(f'{name}/{frame}: source camera reprojection mismatch ({maximum}px)')
                payload = struct.pack('<HHhh', w, h, ox-round(pivot[0]), oy-round(pivot[1])) + color.tobytes() + quantized.tobytes() + owner.tobytes()
                encoded = gzip.compress(payload, compresslevel=6, mtime=0)
                target.writestr(f'{frame:03d}.bin.gz', encoded)
                assert gzip.decompress(encoded)[8:8+w*h*4] == color.tobytes()
                checks.append(dict(frame=frame, rgbaExact=program == 'burst', pairedSourceColour=program == 'beam',
                    ownedPixels=int(need.sum()), missingOwnership=missing, maxCameraErrorPixels=maximum))
        temporary.replace(archive)
        receipts.append(dict(bank=name, file=archive.name, sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            pivot=bank['pivot'], frames=bank['count'], worldPixels=bank['worldPixels'], source_sha256=bank['sha256'], checks=checks))
    (output / (program+'-ownership.json')).write_text(json.dumps(dict(source=str(source),
        production_rgba_recaptured=program == 'beam', accepted_rgba_byte_exact=program == 'burst',
        adapter=json.loads((output / (program+'-opaque') / 'complete.json').read_text()),
        palette_sha256=hashlib.sha256(palette_path.read_bytes()).hexdigest() if palette_path else None,
        bounds=[-64, 64], verticalScale=1.224744871391589, coordinateBasis='camera_local_xyz',
        ownership='source-rendered surface coordinates with original MSAA coverage; no particle identity or hidden depth', banks=receipts), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--program', choices=('beam', 'burst'), required=True)
    parser.add_argument('--palette', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    capture(args.source, args.project, args.output, args.program)
    pack(args.source, args.output, args.program, args.palette)
