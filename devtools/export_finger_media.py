"""Capture accepted skeletal models at native owner headings; preserve source pixels."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from math import cos, pi, sin
from pathlib import Path
import subprocess

BASE=Path('/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review')
PROJECT=BASE.parent/'godot-library/projects/lelu-portal'
GODOT=Path('/mnt/c/Users/tommaso/Documents/Dev/CodexFX/tools/godot/windows/Godot_v4.6.2-stable_win64_console.exe')


def windows(path: Path) -> str:
    return subprocess.check_output(['wslpath','-w',str(path.resolve())],text=True).strip()


def capture(output: Path, *, branch: str, heading: int, quadrant: int, side: str) -> None:
    identity='finger_ground_magic_v8' if branch=='normal' else 'finger_counterspell_v5'
    folder=output/branch/f'd{heading}'/f'q{quadrant}'/side
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'capture.json').is_file() and len(tuple((folder/'frames').glob('*.png')))==104:
        print('Retained',folder,flush=True)
        return
    original=BASE/'native'/identity/'q0'/side
    script=(original/'adapter.gd').read_text()
    # Heading rotates the complete authored visual owner; the light remains in
    # original world orientation, and the split remains camera-world-relative.
    script=script.replace('super._apply_visibility_filters(node)',
        'super._apply_visibility_filters(node)\n var visual_owner=Node3D.new();node.add_child(visual_owner);visual_owner.rotation.y='+str(heading*pi/4))
    for name in ('hand','portal','flare','rim','particles'):
        script=script.replace(f'node.add_child({name})',f'visual_owner.add_child({name})')
    camera_angle=pi/4+quadrant*pi/2
    script=script.replace('vec3(0.70710678,0.0,0.70710678)',
        f'vec3({cos(camera_angle):.12f},0.0,{sin(camera_angle):.12f})')
    name=f'ProductionFinger_{branch}_{heading}_{quadrant}_{side}'
    exporter=PROJECT/'codexfx_exporter'
    (exporter/(name+'.gd')).write_text(script)
    scene=(exporter/f'Fire_{identity}_0_{side}.tscn').read_text().replace(f'Fire_{identity}_0_{side}.gd',name+'.gd')
    (exporter/(name+'.tscn')).write_text(scene)
    (folder/'adapter.gd').write_text(script)
    command=json.loads((original/'command.json').read_text())
    command[command.index('--path')+1]=windows(PROJECT)
    command[command.index('--path')+2]='res://codexfx_exporter/'+name+'.tscn'
    for key,value in (('--output',windows(folder/'strip.png')),('--frames-dir',windows(folder/'frames')),
                      ('--manifest',windows(folder/'capture.json')),
                      ('--camera-position',f'{12*2**.5*cos(camera_angle)},10.797958971,{12*2**.5*sin(camera_angle)}')):
        command[command.index(key)+1]=value
    (folder/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    (folder/'source.json').write_text(json.dumps({'source_adapter':str(original/'adapter.gd'),
        'source_sha256':hashlib.sha256((original/'adapter.gd').read_bytes()).hexdigest(),
        'owner_yaw':heading*pi/4,'camera_quadrant':quadrant,'world_light_retained':True},indent=2)+'\n')
    with (folder/'capture.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    frames=tuple((folder/'frames').glob('*.png'))
    if len(frames)!=104:
        raise ValueError(f'Incomplete native capture: {folder}: {len(frames)}')
    print('Captured',folder,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--branch',choices=('normal','cameo','all'),default='all')
    parser.add_argument('--heading',type=int,choices=range(8))
    parser.add_argument('--quadrant',type=int,choices=range(4))
    parser.add_argument('--side',choices=('front','back'))
    parser.add_argument('--workers',type=int,choices=range(1,5),default=1)
    args=parser.parse_args()
    jobs=[(branch,heading,quadrant,side)
        for branch in (('normal','cameo') if args.branch=='all' else (args.branch,))
        for heading in (range(8) if args.heading is None else (args.heading,))
        for quadrant in (range(4) if args.quadrant is None else (args.quadrant,))
        for side in (('back','front') if args.side is None else (args.side,))]
    def run(job:tuple[str,int,int,str])->None:
        branch,heading,quadrant,side=job
        capture(args.output,branch=branch,heading=heading,quadrant=quadrant,side=side)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        tuple(executor.map(run,jobs))
