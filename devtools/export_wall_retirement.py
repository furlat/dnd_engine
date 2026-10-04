"""Capture the delivered intact wall retirement law with its original Godot adapter.

This offline production export changes only the explicit event law and batches
camera/headings. Original donor construction, shaders, resources, palette,
postprocess, registration and the retained 1.5-second intact pose are preserved.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image

from devtools.export_solar_ownership import GODOT, record_source_project, windows
from devtools.import_assembly_media import SOURCE_CAMERAS
from devtools.import_solid_wall_media import PALETTES


FRAMES = 29  # Last sample proves the source is empty; native lifetime is exactly .85 s.
PROCESS = '''func _process(_delta:float)->void:
 if not is_instance_valid(subject):return
 tick+=1
 # Three actual render ticks let both original color and ownership postpasses settle.
 var sample_index=int((tick-1)/3);var phase=sample_index%29;var bank=int(sample_index/29)
 var heading=int(bank/8)%4;var quadrant=int(bank/2)%4;var front=(bank%2)==1
 var signs=[Vector2(1,1),Vector2(-1,1),Vector2(-1,-1),Vector2(1,-1)][quadrant]
 camera_ground=signs.normalized();subject.rotation.y=float(heading)*PI/2.
 camera.position=Vector3(12*signs.x,11.297958971,12*signs.y);camera.look_at(Vector3(0,1.5,0))
 var mask_camera=ownership_view.get_child(0) as Camera3D;mask_camera.transform=camera.transform
 var ground3=subject.to_global(Vector3(0,0,2*CELL));var ground=Vector2(ground3.x,ground3.z)
 var u=clampf(float(phase)/32./.85,0.,1.);var fade=1.-u*u*(3.-2.*u)
 for panel in panels:panel.position.y=-HEIGHT*(1.-fade);panel.visible=true
 for m in mats:
  m.set_shader_parameter("actor_ground",ground);m.set_shader_parameter("camera_ground",camera_ground)
  m.set_shader_parameter("foreground",front);m.set_shader_parameter("wall_clock",1.5)
  m.set_shader_parameter("fracture",0.);m.set_shader_parameter("opacity",fade)
 for mesh in air+frost_flakes:mesh.visible=false
 if ownership_sources.is_empty():register_ownership(subject)
 for m in ownership_mats:m.set_shader_parameter("camera_ground",camera_ground)
 (pixel_view.get_child(0) as ColorRect).material.set_shader_parameter("foreground",front)
 update_ownership(ground)
'''


def prepare(source: Path, original_project: Path, output: Path, kind: str, variant: int) -> tuple[Path, list[str]]:
    """Prepare a separate captured project without editing the accepted delivery."""
    contract = json.loads((source/'INTACT_RETIREMENT_SOURCE_CONTRACT.json').read_text())
    if (contract['revision'], contract['durationSeconds'], contract['fracture'], contract['air']) != (
            'intact-source-retirement-20261002', .85, False, False):
        raise ValueError('Intact retirement source contract differs')
    output.mkdir(parents=True, exist_ok=True)
    record_source_project(original_project, output/(kind+'-source-project.json'))
    project = output/(kind+'-project')
    if not project.exists():
        shutil.copytree(original_project, project)
    donor = source/f'{kind}-v{variant}-lifecycle/d0/q0/back'
    script = (donor/'adapter.gd').read_text()
    first, last = script.index('func _process('), script.index('var ownership_view:')
    script = script[:first]+PROCESS+script[last:]
    name = f'IntactRetirement_{kind}_{variant}'
    job = output/name
    job.mkdir(exist_ok=True)
    (job/'adapter.gd').write_text(script)
    (project/'codexfx_exporter'/f'{name}.gd').write_text(script)
    template = (original_project/'codexfx_exporter/ExactProjectileCameraRecorder.tscn').read_text()
    (project/'codexfx_exporter'/f'{name}.tscn').write_text(template.replace('ExactProjectileCameraRecorder.gd',name+'.gd'))
    command = json.loads((donor/'command.json').read_text())
    command[0] = str(GODOT)
    command[command.index('--')-1] = 'res://codexfx_exporter/'+name+'.tscn'
    for key, value in {'--path': windows(project), '--frames':str(FRAMES*32),
            '--sample-times-seconds':','.join(str((i+1)*3/144) for i in range(FRAMES*32)),
            '--output':windows(job/'strip.png'),'--frames-dir':windows(job/'frames'),
            '--manifest':windows(job/'capture.json')}.items():
        command[command.index(key)+1] = value
    (job/'command.json').write_text(json.dumps(command))
    (job/'source.json').write_text(json.dumps({'original_adapter':str(donor/'adapter.gd'),
        'sha256':hashlib.sha256((donor/'adapter.gd').read_bytes()).hexdigest(),
        'source_contract':contract,'adaptation':'Original frozen intact donor; only declared retirement law and batched view selection.'},indent=2))
    return job, command


def capture(job: Path, command: list[str]) -> None:
    fingerprint = hashlib.sha256((job/'adapter.gd').read_bytes()).hexdigest()
    completed = job/'complete.json'
    if completed.exists() and json.loads(completed.read_text())['adapter_sha256'] == fingerprint:
        return
    with (job/'capture.log').open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    log = (job/'capture.log').read_text()
    if result.returncode or 'SCRIPT ERROR' in log or 'SHADER ERROR' in log:
        raise ValueError(log[-8000:])
    if len(tuple((job/'frames').glob('*.png'))) != FRAMES*32:
        raise ValueError('Incomplete retirement export')
    completed.write_text(json.dumps({'adapter_sha256':fingerprint,'frames':FRAMES*32}))


def pack(source: Path, output: Path) -> dict:
    """Lossless packing of original-operator samples, with intact/floor/empty proof."""
    original = json.loads((source/'media.json').read_text())
    rows, hashes, validation = {}, {}, []
    for kind in ('stone','ice'):
        for variant in range(3):
            job=output/f'IntactRetirement_{kind}_{variant}'
            if not (job/'complete.json').exists():
                raise ValueError('All original wall variants must be captured before packing')
            for direction in range(4):
                cameras={}
                for camera, native in enumerate(SOURCE_CAMERAS):
                    layers={}
                    for side_index, side in enumerate(('back','front')):
                        start=(direction*8+native*2+side_index)*FRAMES
                        pictures=[Image.open(job/'frames'/f'frame_{start+i:03d}.png').convert('RGBA') for i in range(FRAMES)]
                        # A new camera export is accepted only if its starting wall matches the delivered intact shape.
                        bank=original['banks'][f'{kind}-v{variant}-lifecycle/d{direction}/q{native}/{side}']
                        original_frame=bank['frames'][47]
                        reference=Image.new('RGBA',(512,512))
                        if original_frame is not None:
                            page=Image.open(source/bank['pages'][original_frame['page']]['path']).convert('RGBA')
                            x,y,w,h=original_frame['source']
                            reference.paste(page.crop((x,y,x+w,y+h)),original_frame['offset'])
                        if pictures[-1].getbbox() is not None:
                            raise ValueError('Retirement source does not finish empty')
                        # Preserve measured agreement, never tune or pick another donor to improve it.
                        same=pictures[0].tobytes()==reference.tobytes()
                        if not same:
                            raise ValueError(f'{kind}/{variant}/{direction}/{native}/{side}: intact source pixels differ')
                        validation.append({'kind':kind,'variant':variant,'direction':direction,'camera':native,
                            'side':side,'intact_byte_exact':same,'intact_bbox':pictures[0].getbbox(),
                            'original_bbox':reference.getbbox(),'final_empty':True})
                        atlas=Image.new('RGBA',(2048,2048));frames=[];x=y=height=0;pages=[]
                        def save():
                            relative=f'packed/{kind}_v{variant}_d{direction}/q{camera}/{side}-{len(pages)}.png'
                            target=output/relative;target.parent.mkdir(parents=True,exist_ok=True);atlas.save(target)
                            hashes[relative]=hashlib.sha256(target.read_bytes()).hexdigest();pages.append(relative)
                        for picture in pictures:
                            box=picture.getbbox()
                            if box is None:frames.append(None);continue
                            crop=picture.crop(box);w,h=crop.size
                            if x+w>2048:x=0;y+=height;height=0
                            if y+h>2048:save();atlas=Image.new('RGBA',(2048,2048));x=y=height=0
                            atlas.paste(crop,(x,y));frames.append({'page':len(pages),'source':[x,y,w,h],'offset':list(box[:2])})
                            x+=w;height=max(height,h)
                        save();layers[side]={'pages':pages,'frames':frames}
                    cameras[str(camera)]={'layers':layers}
                rows[f'{kind}_v{variant}_d{direction}']={'fps':32,'frames':FRAMES,'cell':512,
                    'pivot':original['pivot'],'palette':PALETTES[kind],'cameras':cameras}
    (output/'media.json').write_text(json.dumps(rows,separators=(',',':'))+'\n')
    (output/'SHA256SUMS').write_text(''.join(digest+'  '+name+'\n' for name,digest in sorted(hashes.items())))
    (output/'validation.json').write_text(json.dumps({'samples':validation,'durationMs':850,
        'originals_preserved':str(source),'production':'Recaptured from original operator; no new art.'},indent=2)+'\n')
    return {'banks':len(rows),'pages':len(hashes),'exact_intact':sum(v['intact_byte_exact'] for v in validation),'views':len(validation)}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--kind',choices=('stone','ice'))
    parser.add_argument('--variant',type=int,choices=range(3))
    parser.add_argument('--project',type=Path)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--pack',action='store_true')
    args=parser.parse_args()
    if args.pack:print(pack(args.source,args.output))
    else:
        if args.project is None or args.kind is None or args.variant is None:parser.error('Capture requires project, kind, variant')
        job,command=prepare(args.source,args.project,args.output,args.kind,args.variant)
        if not args.prepare_only:capture(job,command)
        print(job)
