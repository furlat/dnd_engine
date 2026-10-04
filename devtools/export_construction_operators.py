"""Export original wall meshes and native rigid poses, never inferred raster depth."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from devtools.export_solar_ownership import GODOT, windows


EXPORT = '''
var export_poses=[]
func _ready()->void:
 _options={"manifest":EXPORT_FOLDER+"/construction"}
 var owner_node=Node3D.new();add_child(owner_node)
 _apply_visibility_filters(owner_node)
 var pieces=[]
 for b in ice_bodies:
  var visual=b.get_child(1) as MeshInstance3D
  pieces.append({"mesh":export_mesh(visual.mesh),"origin":[b.position.x,b.position.y,b.position.z]})
 var file=FileAccess.open(EXPORT_FOLDER+"/geometry.json",FileAccess.WRITE)
 file.store_string(JSON.stringify({"radiusFeet":EXPORT_RADIUS,"whole":export_mesh(ice_whole.mesh),"pieces":pieces,
  "force":{"vertices":export_vectors(points),"uv":export_vectors(uvs),"indices":Array(indices)}}));file.close()
func export_vectors(values):
 var result=[]
 for value in values:
  if value is Vector3:result.append([value.x,value.y,value.z])
  else:result.append([value.x,value.y])
 return result
func export_mesh(mesh:Mesh)->Dictionary:
 var arrays=mesh.surface_get_arrays(0)
 var ids=Array(arrays[Mesh.ARRAY_INDEX]) if arrays[Mesh.ARRAY_INDEX]!=null else range(arrays[Mesh.ARRAY_VERTEX].size())
 return {"vertices":export_vectors(arrays[Mesh.ARRAY_VERTEX]),"normals":export_vectors(arrays[Mesh.ARRAY_NORMAL]),
  "uv":export_vectors(arrays[Mesh.ARRAY_TEX_UV]),"indices":ids}
func _process(delta:float)->void:
 if not is_instance_valid(subject):return
 super._process(delta)
 if tick>=590:
  var poses=[]
  for b in ice_bodies:
   var t=b.transform
   poses.append([t.origin.x,t.origin.y,t.origin.z,t.basis.x.x,t.basis.x.y,t.basis.x.z,
    t.basis.y.x,t.basis.y.y,t.basis.y.z,t.basis.z.x,t.basis.z.y,t.basis.z.z])
  export_poses.append({"tick":tick,"poses":poses})
 if tick>=930:
  var file=FileAccess.open(EXPORT_FOLDER+"/poses.json",FileAccess.WRITE)
  file.store_string(JSON.stringify({"fps":144,"breakTick":591,"frames":export_poses}));file.close()
  print("CONSTRUCTION_GEOMETRY_COMPLETE")
  get_tree().quit()
'''


def export(source: Path, project: Path, output: Path, radius: int) -> None:
    if radius not in (5,10):
        raise ValueError('Only native supported radii are exported')
    output.mkdir(parents=True,exist_ok=True)
    original=source.read_bytes();text=original.decode()
    if 'const RADIUS=CELL*2.0' not in text:
        raise ValueError('Original wall constructor differs')
    name=f'ProductionIceGeometry{radius}'
    donor=name+'Source'
    (project/'codexfx_exporter'/f'{donor}.gd').write_text(text.replace('const RADIUS=CELL*2.0',f'const RADIUS=CELL*{radius/5:.1f}'))
    script=f'extends "res://codexfx_exporter/{donor}.gd"\nconst EXPORT_FOLDER={json.dumps(windows(output))}\nconst EXPORT_RADIUS={radius}\n'+EXPORT
    (output/'adapter.gd').write_text(script)
    (project/'codexfx_exporter'/f'{name}.gd').write_text(script)
    scene='[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://codexfx_exporter/'+name+'.gd" id="1"]\n[node name="Export" type="Node3D"]\nscript = ExtResource("1")\n'
    scene+='\n'.join(f'[node name="{node}" type="{kind}" parent="."]\n' for node,kind in (('SubjectRoot','Node3D'),('Camera3D','Camera3D'),('WorldEnvironment','WorldEnvironment')))
    (project/'codexfx_exporter'/f'{name}.tscn').write_text(scene)
    command=[str(GODOT),'--path',windows(project),'--fixed-fps','144','--disable-vsync','--resolution','64x64','res://codexfx_exporter/'+name+'.tscn']
    (output/'command.json').write_text(json.dumps(command))
    with (output/'capture.log').open('w') as log:
        completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=240)
    log=(output/'capture.log').read_text()
    if completed.returncode or 'SCRIPT ERROR' in log or 'CONSTRUCTION_GEOMETRY_COMPLETE' not in log:
        raise ValueError(log[-6000:])
    geometry=json.loads((output/'geometry.json').read_text());poses=json.loads((output/'poses.json').read_text())
    if len(geometry['pieces'])!=72 or len(poses['frames'])!=341 or any(len(f['poses'])!=72 for f in poses['frames']):
        raise ValueError('Original ice pieces/clock are incomplete')
    receipt={'source':str(source),'sourceSha256':hashlib.sha256(original).hexdigest(),'radiusFeet':radius,
        'adaptation':'Original constructor at native selected radius; original Godot rigid-body physics at 144 Hz. No raster-derived coordinates.',
        'hashes':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in ('adapter.gd','geometry.json','poses.json','command.json')}}
    (output/'source.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--project',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    for radius in (5,10):
        export(args.source,args.project,args.output/str(radius),radius)
