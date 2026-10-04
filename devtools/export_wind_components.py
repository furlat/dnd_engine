"""Export the unchanged joined Wind source's material textures and contact mesh."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from devtools.media_delivery import install_verified_payloads

ROOT=Path(__file__).resolve().parents[1]
DONORS=('VFX/materials/m_windstreaks13.tres','VFX/shaders/s_windpanner_1_p_ds.tres',
    'VFX/textures/T_PerlinNoise_Tiled11_inv.png','VFX/textures/T_VFX_Noise_531.png',
    'VFX/Scenes/VFX_WindHit_K2.tscn','VFX/shaders/s_animated_ds_toon.gdshader','VFX/textures/T_WindWaveAnim.png')
SCRIPT=r'''extends SceneTree
const OUTPUT=OUTPUT_PATH
func mesh_arrays(mesh:Mesh)->Dictionary:
 var a=mesh.surface_get_arrays(0)
 var vertices=[];var uv=[];var indices=[]
 for p in a[Mesh.ARRAY_VERTEX]:vertices.append([p.x,p.y,p.z])
 for p in a[Mesh.ARRAY_TEX_UV]:uv.append([p.x,p.y])
 for p in a[Mesh.ARRAY_INDEX]:indices.append(p)
 return {"vertices":vertices,"uv":uv,"indices":indices}
func _initialize()->void:
 call_deferred("export_original")
func export_original()->void:
 var owner=Node3D.new();root.add_child(owner)
 var wall=load("res://codexfx_exporter/ProductionWindModules.gd").new();root.add_child(wall)
 wall.build(owner)
 await process_frame
 await process_frame
 var textures={}
 var material=wall.mats[0]
 for key in ["Wind_1_texture","Wind_2_texture_subs","Color1DGradient","sprite_sheet"]:
  var texture=wall.hit_mats[0].get_shader_parameter(key) if key=="sprite_sheet" else material.get_shader_parameter(key)
  if texture.get_image()==null:await texture.changed
  var image=texture.get_image()
  var original_format=image.get_format()
  if image.is_compressed():image.decompress()
  image.convert(Image.FORMAT_RGBAF)
  var file=key+".rgba32f"
  FileAccess.open(OUTPUT.path_join(file),FileAccess.WRITE).store_buffer(image.get_data())
  textures[key]={"file":file,"size":[image.get_width(),image.get_height()],"original_format":original_format}
 FileAccess.open(OUTPUT.path_join("wind-components.json"),FileAccess.WRITE).store_string(JSON.stringify({"textures":textures,"contact":mesh_arrays(wall.hit_meshes[0].mesh)}))
 FileAccess.open(OUTPUT.path_join("flow.gdshader"),FileAccess.WRITE).store_string(material.shader.code)
 FileAccess.open(OUTPUT.path_join("contact.gdshader"),FileAccess.WRITE).store_string(wall.hit_mats[0].shader.code)
 print("ORIGINAL_WIND_COMPONENTS_EXPORTED")
 quit()
'''


def export(project:Path,source:Path,output:Path,godot:Path)->None:
    output.mkdir(parents=True,exist_ok=True)
    def windows(path:Path)->str:
        return subprocess.check_output(['wslpath','-w',str(path.resolve())],text=True).strip()
    shutil.copyfile(source/'WindModules.gd',project/'codexfx_exporter/ProductionWindModules.gd')
    script=SCRIPT.replace('OUTPUT_PATH',json.dumps(windows(output)))
    (output/'ExportWindComponents.gd').write_text(script)
    command=[str(godot),'--rendering-method','forward_plus','--rendering-driver','vulkan',
        '--audio-driver','Dummy','--path',windows(project),'--script',windows(output/'ExportWindComponents.gd')]
    (output/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    with (output/'export.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    if not (output/'wind-components.json').is_file():raise ValueError('Original Wind export incomplete')


def install(project:Path,source:Path,output:Path,preserved:Path,production:Path)->None:
    originals=preserved/'original';originals.mkdir(parents=True,exist_ok=True)
    for name in ('WindModules.gd','authoring/Postprocess.gd.txt','authoring/capture.py'):
        target=originals/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,target)
    for name in DONORS:
        target=originals/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(project/name,target)
    shutil.copytree(output,preserved/'export',dirs_exist_ok=True)
    payloads=tuple((p.name,'game/assets/wind_flow/'+p.name,hashlib.sha256(p.read_bytes()).hexdigest())
        for p in output.iterdir() if p.suffix=='.rgba32f' or p.name=='wind-components.json')
    files=install_verified_payloads(output,payloads,preserved=preserved/'selected',production=production,repo=ROOT)
    folder=ROOT/'game/data/wall_media';path=folder/'bindings.json';bindings=json.loads(path.read_text())
    bindings['resources']['/wind/flow-components.json']='game/assets/wind_flow/wind-components.json'
    path.write_text(json.dumps(bindings,separators=(',',':'))+'\n')
    (folder/'wind-flow-source.json').write_text(json.dumps({'source':str(source),'preserved':str(preserved),
        'files':files,'originals':{name:hashlib.sha256((originals/name).read_bytes()).hexdigest()
            for name in ('WindModules.gd','authoring/Postprocess.gd.txt','authoring/capture.py',*DONORS)}},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('export','install'))
    for name in ('project','source','output','godot','preserved','production'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.operation=='export':export(args.project,args.source,args.output,args.godot)
    else:install(args.project,args.source,args.output,args.preserved,args.production)
