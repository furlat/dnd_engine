"""Export original seeded Force owner motes and native-dimension source lattices."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from devtools.export_solar_ownership import GODOT, windows


def export(source: Path, project: Path, folder: Path) -> None:
    folder.mkdir(parents=True,exist_ok=True)
    original=source.read_text()
    scripts=[]
    for form,size in [('dome',5),('dome',10),* [('panels',i*10) for i in range(1,11)]]:
     name=f'ForceMotes{form}{size}'
     text=original.replace('const SHAPE="ice-dome"',f'const SHAPE="{form}"').replace('const RADIUS=CELL*2.0',f'const RADIUS=CELL*{size/5 if form=="dome" else 2:.1f}')
     if form=='panels':text=text.replace('const LENGTH=CELL*6.0',f'const LENGTH=CELL*{size/5:.1f}').replace('const NX=96;const NY=32',f'const NX={int(size/10*32)};const NY=32')
     text=text.replace('func _process(', 'func _original_process(').replace('func _physics_process(', 'func _original_physics_process(')
     text+='\nfunc _ready()->void:pass\nfunc _process(_delta:float)->void:pass\nfunc _physics_process(_delta:float)->void:pass\n'
     (project/'codexfx_exporter'/f'{name}.gd').write_text(text);(folder/f'{name}.gd').write_text(text);scripts.append((name,form,size))
    win=windows(folder)
    code='extends Node3D\nfunc _ready()->void:\n var records=[]\n'
    for name,form,size in scripts:
     code+=f' var o_{name}=load("res://codexfx_exporter/{name}.gd").new()\n add_child(o_{name})\n o_{name}._options={{"manifest":"{win}/{name}"}}\n var subject_{name}=Node3D.new();o_{name}.add_child(subject_{name})\n o_{name}._apply_visibility_filters(subject_{name})\n var rows_{name}=[]\n for i in range(30,90):\n  var p=o_{name}.mote_origins[i];var v=o_{name}.mote_velocities[i];var q=o_{name}.motes[i].mesh.size\n  rows_{name}.append({{"origin":[p.x,p.y,p.z],"velocity":[v.x,v.y,v.z],"size":[q.x,q.y]}})\n records.append({{"form":"{form}","sizeFeet":{size},"motes":rows_{name}}})\n'
    code+=f' var img=load("res://VFX/textures/T_VFX_Noise_10.PNG").get_image()\n var format=img.get_format()\n if img.is_compressed():img.decompress()\n img.convert(Image.FORMAT_RGBAF)\n var file=FileAccess.open("{win}/noise.rgba32f",FileAccess.WRITE);file.store_buffer(img.get_data());file.close()\n file=FileAccess.open("{win}/motes.json",FileAccess.WRITE);file.store_string(JSON.stringify({{"groups":records,"noise":{{"file":"noise.rgba32f","size":[img.get_width(),img.get_height()],"original_format":format}}}}));file.close()\n print("FORCE_MOTES_EXPORTED")\n get_tree().quit()\n'
    (project/'codexfx_exporter/ForceMotesExport.gd').write_text(code);(folder/'adapter.gd').write_text(code)
    (project/'codexfx_exporter/ForceMotesExport.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://codexfx_exporter/ForceMotesExport.gd" id="1"]\n[node name="Export" type="Node3D"]\nscript = ExtResource("1")\n')
    command=[str(GODOT),'--headless','--path',windows(project),'res://codexfx_exporter/ForceMotesExport.tscn']
    (folder/'command.json').write_text(json.dumps(command));result=subprocess.run(command,stdout=(folder/'export.log').open('w'),stderr=subprocess.STDOUT,text=True,timeout=60);result.stdout=(folder/'export.log').read_text()
    if result.returncode or 'ERROR:' in result.stdout or 'FORCE_MOTES_EXPORTED' not in result.stdout:
     raise ValueError(result.stdout[-8000:])
    (folder/'source.json').write_text(json.dumps({'source':str(source),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'adaptation':'Original seeded make_disintegrate blue owner motes; native supported panel lengths retain 32 columns per ten feet. Original supplied quad sizes, origins, velocities and noise texture. Green plasma remains owned by spell delivery.','hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file() and p.name!='source.json'}},indent=2)+'\n')
    print('Force mote metadata export complete')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--project',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();export(args.source,args.project,args.output)
