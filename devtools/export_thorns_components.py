"""Export accepted Thorns donor data without applying its per-module variation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from devtools.media_delivery import install_verified_payloads

ROOT = Path(__file__).resolve().parents[1]
SCENE = 'VFX/Scenes/VFX_Nature_Vines_Wall.tscn'
ORIGINALS = (SCENE, 'VFX/objects/sm_vine_plants11.obj', 'VFX/shaders/ss_vines.gdshader',
    'VFX/textures/T_VFX_Noise_5.PNG', 'VFX/textures/T_Noise_6Yu1.png', 'VFX/textures/misc/T_BarkA1_col.png',
    'codexfx_exporter/postprocess/pixel_lab_palette_preserve_alpha.gdshader')
SOURCE_DOCS=('ThornsModules.gd','authoring/capture.py','multi/d0/q0/capture.json')
SCRIPT = r'''extends SceneTree
const OUTPUT=OUTPUT_PATH
func value(data):
 if data is Vector2:return [data.x,data.y]
 if data is Vector3:return [data.x,data.y,data.z]
 if data is Color:return [data.r,data.g,data.b,data.a]
 return data
func mesh_arrays(mesh:Mesh)->Dictionary:
 assert(mesh.get_surface_count()==1)
 var a=mesh.surface_get_arrays(0)
 var vertices=[];var normals=[];var uv=[];var indices=[]
 for p in a[Mesh.ARRAY_VERTEX]:vertices.append(value(p))
 for p in a[Mesh.ARRAY_NORMAL]:normals.append(value(p))
 for p in a[Mesh.ARRAY_TEX_UV]:uv.append(value(p))
 for p in a[Mesh.ARRAY_INDEX]:indices.append(p)
 return {"vertices":vertices,"normals":normals,"uv":uv,"indices":indices}
func _initialize()->void:
 call_deferred("export_original")
func export_original()->void:
 var scene=load("res://VFX/Scenes/VFX_Nature_Vines_Wall.tscn").instantiate()
 root.add_child(scene)
 var body=scene.get_node("SmVinePlants11") as MeshInstance3D
 var transform=body.transform
 (scene.get_node("AnimationPlayer") as AnimationPlayer).stop()
 var mesh=mesh_arrays(body.mesh)
 var original=body.material_override as ShaderMaterial
 var adapter=load("res://codexfx_exporter/ProductionThornsModules.gd").new()
 root.add_child(adapter)
 # adapt() supplies the accepted shader/parameters only. build() would call
 # vary_interior; its raw mesh must remain untouched for runtime variants.
 var material=adapter.adapt(original)
 await process_frame
 await process_frame
 var textures={}
 for key in ["VinesTexture","EnergyColor2DGradient","DetailsNoiseTexture","DisolverDetailsTexture"]:
  var texture=material.get_shader_parameter(key)
  if texture.get_image()==null:await texture.changed
  var image=texture.get_image()
  var original_format=image.get_format()
  if image.is_compressed():image.decompress()
  image.convert(Image.FORMAT_RGBAF)
  var file=key+".rgba32f"
  FileAccess.open(OUTPUT.path_join(file),FileAccess.WRITE).store_buffer(image.get_data())
  textures[key]={"file":file,"size":[image.get_width(),image.get_height()],"original_format":original_format}
 var params={}
 for row in material.shader.get_shader_uniform_list():
  var parameter=material.get_shader_parameter(row.name)
  if parameter!=null and not parameter is Texture:params[str(row.name)]=value(parameter)
 params["DisolverDetails"]=RenderingServer.instance_geometry_get_shader_parameter_default_value(body.get_instance(),"DisolverDetails")
 var animation=(scene.get_node("AnimationPlayer") as AnimationPlayer).get_animation("Start")
 var tracks=[];var scale_track=-1;var step_track=-1
 for track in animation.get_track_count():
  var path=str(animation.track_get_path(track))
  if not path.begins_with("SmVinePlants11:"):continue
  var times=[];var values=[];var transitions=[]
  for key in animation.track_get_key_count(track):
   times.append(animation.track_get_key_time(track,key))
   values.append(value(animation.track_get_key_value(track,key)))
   transitions.append(animation.track_get_key_transition(track,key))
  tracks.append({"path":path,"times":times,"values":values,"transitions":transitions,
   "interpolation":animation.track_get_interpolation_type(track)})
  if path.ends_with(":scale"):scale_track=track
  if path.ends_with("/DisolverSTEP"):step_track=track
 assert(scale_track>=0 and step_track>=0)
 var times=[];var scales=[];var steps=[]
 for frame in range(int(ceil(animation.length*144))+1):
  var at=minf(float(frame)/144,animation.length)
  times.append(at);scales.append(value(animation.value_track_interpolate(scale_track,at)))
  steps.append(animation.value_track_interpolate(step_track,at))
 var components={"mesh":mesh,"textures":textures,"params":params,
  "child_transform":{"basis":[value(transform.basis.x),value(transform.basis.y),value(transform.basis.z)],"origin":value(transform.origin)},
  "start":{"times":times,"scales":scales,"steps":steps,"tracks":tracks,"duration":animation.length}}
 FileAccess.open(OUTPUT.path_join("thorns-components.json"),FileAccess.WRITE).store_string(JSON.stringify(components))
 FileAccess.open(OUTPUT.path_join("accepted.gdshader"),FileAccess.WRITE).store_string(material.shader.code)
 FileAccess.open(OUTPUT.path_join("donor.gdshader"),FileAccess.WRITE).store_string(original.shader.code)
 print("ORIGINAL_THORNS_COMPONENTS_EXPORTED")
 quit()
'''


def export(project: Path, source: Path, output: Path, godot: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    def windows(path: Path) -> str:
        return subprocess.check_output(['wslpath', '-w', str(path.resolve())], text=True).strip()
    shutil.copyfile(source/'ThornsModules.gd', project/'codexfx_exporter/ProductionThornsModules.gd')
    script=SCRIPT.replace('OUTPUT_PATH',json.dumps(windows(output)))
    (output/'ExportThornsComponents.gd').write_text(script)
    command=[str(godot),'--rendering-method','forward_plus','--rendering-driver','vulkan',
        '--audio-driver','Dummy','--path',windows(project),'--script',windows(output/'ExportThornsComponents.gd')]
    (output/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    with (output/'export.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    if not (output/'thorns-components.json').is_file():
        raise ValueError('Original Thorns export incomplete')


def install(project: Path, source: Path, output: Path, preserved: Path, production: Path) -> None:
    originals=preserved/'original'
    for name in ORIGINALS:
        target=originals/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(project/name,target)
    for name in SOURCE_DOCS:
        target=originals/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,target)
    shutil.copytree(output,preserved/'export',dirs_exist_ok=True)
    selected=preserved/'production-staging';selected.mkdir(parents=True,exist_ok=True)
    components=json.loads((output/'thorns-components.json').read_text())
    components['start'].pop('tracks')
    components['start'].pop('duration')
    wanted=('VineTextureScale','NoiseScale','Intensity','IsInvertFresnel','FresnelPower',
        'AlphaScissorThreshold','DisolverDetailsScale','DisolverDetailsSpeed','DisolverDetails')
    components['params']={key:components['params'][key] for key in wanted}
    (selected/'thorns-components.json').write_text(json.dumps(components,separators=(',',':'))+'\n')
    for path in output.glob('*.rgba32f'):shutil.copyfile(path,selected/path.name)
    payloads=tuple((path.name,'game/assets/thorns_flow/'+path.name,hashlib.sha256(path.read_bytes()).hexdigest())
        for path in selected.iterdir())
    files=install_verified_payloads(selected,payloads,preserved=preserved/'selected-runtime',production=production,repo=ROOT)
    folder=ROOT/'game/data/wall_media';path=folder/'bindings.json';bindings=json.loads(path.read_text())
    bindings['resources']['/thorns/components.json']='game/assets/thorns_flow/thorns-components.json'
    path.write_text(json.dumps(bindings,separators=(',',':'))+'\n')
    (folder/'thorns-flow-source.json').write_text(json.dumps({'source':str(source),'preserved':str(preserved),
        'files':files,'originals':{name:hashlib.sha256((originals/name).read_bytes()).hexdigest()
            for name in (*ORIGINALS,*SOURCE_DOCS)}},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('export','install'))
    for name in ('project','source','output','godot','preserved','production'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.operation=='export':export(args.project,args.source,args.output,args.godot)
    else:install(args.project,args.source,args.output,args.preserved,args.production)
