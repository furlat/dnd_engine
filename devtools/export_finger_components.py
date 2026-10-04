"""Export original Darkness donor arrays/textures through Godot's resource loader."""
import argparse
import json
from pathlib import Path
import subprocess

SCRIPT=r'''extends SceneTree
const OUTPUT=OUTPUT_PATH
const SPHERE=SPHERE_PATH
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
 var scene=load("res://ProjectileVFX/Scenes/VFX_Darkness_projectile.tscn").instantiate()
 var rows=[]
 for name in ["FBHead","FBHead2inner","FBHead3outside"]:
  var node=scene.get_node(name)
  var row=mesh_arrays(node.mesh)
  row["name"]=name
  var t=node.transform
  row["transform"]=[[t.basis.x.x,t.basis.x.y,t.basis.x.z],[t.basis.y.x,t.basis.y.y,t.basis.y.z],[t.basis.z.x,t.basis.z.y,t.basis.z.z],[t.origin.x,t.origin.y,t.origin.z]]
  var material=node.material_override
  var parameters={}
  for key in ["Fire_Scale","Fire_Speed","Color_Dissipation","Dissapear_Step","Proximity_Fade"]:
   var value=material.get_shader_parameter(key)
   parameters[key]=[value.x,value.y] if value is Vector2 else value
  var textures={}
  for key in ["Fire_Texture","Gradient_Substract","Color_1D_Gradient"]:
   var texture=material.get_shader_parameter(key)
   if texture is GradientTexture1D:
    texture=texture.duplicate(true)
    texture.gradient=texture.gradient.duplicate(true)
    var colors=texture.gradient.colors
    for i in colors.size():colors[i]=Color(colors[i].v,colors[i].v,colors[i].v,colors[i].a)
    texture.gradient.colors=colors
   await process_frame
   await process_frame
   if texture.get_image()==null:await texture.changed
   var image=texture.get_image()
   var original_format=image.get_format()
   if image.is_compressed():image.decompress()
   image.convert(Image.FORMAT_RGBAF)
   var file=name+"-"+key+".rgba32f"
   FileAccess.open(OUTPUT.path_join(file),FileAccess.WRITE).store_buffer(image.get_data())
   textures[key]={"file":file,"size":[image.get_width(),image.get_height()],"original_format":original_format}
  row["parameters"]=parameters;row["textures"]=textures
  rows.append(row)
 FileAccess.open(OUTPUT.path_join("darkness-mesh.json"),FileAccess.WRITE).store_string(JSON.stringify({"scale":[.40,.40,.68],"meshes":rows}))
 var sphere=SphereMesh.new();sphere.radius=1.;sphere.height=2.;sphere.radial_segments=24;sphere.rings=12
 FileAccess.open(SPHERE,FileAccess.WRITE).store_string(JSON.stringify(mesh_arrays(sphere)))
 var splinter=CylinderMesh.new();splinter.top_radius=0.;splinter.bottom_radius=.028;splinter.height=.22;splinter.radial_segments=3
 FileAccess.open(OUTPUT.path_join("splinter.json"),FileAccess.WRITE).store_string(JSON.stringify(mesh_arrays(splinter)))
 scene.free()
 print("FINGER_COMPONENTS_EXPORTED ",rows.size())
 quit()
'''


def export(project:Path,output:Path,godot:Path,sphere:Path)->None:
    output.mkdir(parents=True,exist_ok=True);sphere.parent.mkdir(parents=True,exist_ok=True)
    def windows(path:Path)->str:
        return subprocess.check_output(['wslpath','-w',str(path.resolve())],text=True).strip()
    script=SCRIPT.replace('OUTPUT_PATH',json.dumps(windows(output))).replace('SPHERE_PATH',json.dumps(windows(sphere)))
    name='ExportFingerOriginalComponents.gd'
    (project/'codexfx_exporter'/name).write_text(script)
    (output/name).write_text(script)
    command=[str(godot),'--rendering-method','forward_plus','--rendering-driver','vulkan','--audio-driver','Dummy','--path',windows(project),'--script','res://codexfx_exporter/'+name]
    (output/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    with (output/'export.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    if not (output/'darkness-mesh.json').is_file() or not sphere.is_file():
        raise ValueError('Original component export did not complete')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('project','output','godot','sphere'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();export(args.project,args.output,args.godot,args.sphere)
