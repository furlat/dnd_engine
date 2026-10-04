"""Export the original procedural Dread noise, without recreating its algorithm."""
import argparse
import json
from pathlib import Path
import subprocess


SCRIPT = '''extends SceneTree
func _initialize()->void:
 call_deferred("export_original")
func export_original()->void:
 var donor=load("res://codexfx_exporter/Dread_rot.tscn").instantiate()
 var texture:Texture2D=donor.get_node("Aura").material_override.get_shader_parameter("noise_texture")
 if texture.get_image()==null:await texture.changed
 var result=texture.get_image().save_png(OUTPUT)
 print("DREAD_NOISE_EXPORTED ",result," ",texture.get_width(),"x",texture.get_height())
 donor.free()
 quit(result)
'''


def export_dread_noise(project: Path, output: Path, godot: Path) -> Path:
    """Resolve the donor's existing NoiseTexture2D through its original engine."""
    output.mkdir(parents=True, exist_ok=True)
    def windows(path: Path) -> str:
        return subprocess.check_output(['wslpath','-w',str(path)], text=True).strip()
    source = SCRIPT.replace('OUTPUT',json.dumps(windows(output/'dread-noise.png')))
    script = project/'codexfx_exporter/ExportDreadNoise.gd'
    script.write_text(source)
    (output/'ExportDreadNoise.gd').write_text(source)
    command = [str(godot),'--headless','--path',windows(project),'--script',
               'res://codexfx_exporter/ExportDreadNoise.gd']
    (output/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    with (output/'capture.log').open('w') as stream:
        subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=60)
    path = output/'dread-noise.png'
    if not path.is_file():
        raise ValueError('Original donor texture was not exported')
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('project','output','godot'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(export_dread_noise(args.project,args.output,args.godot))


def export_plasma_particles(project: Path, output: Path, godot: Path) -> Path:
    """Export original Godot RNG samples, preserving source seeds and draw order."""
    output.mkdir(parents=True,exist_ok=True)
    destination = subprocess.check_output(['wslpath','-w',str(output/'plasma-particles.json')],text=True).strip()
    script = '''extends SceneTree
func _initialize()->void:
 var rng=RandomNumberGenerator.new();rng.seed=319482
 var flight=[]
 for i in range(48):
  flight.append([rng.randf_range(0,TAU),rng.randf_range(2.0,4.5),rng.randf_range(1.5,3.0)])
 rng.seed=61461
 var impact=[]
 for i in range(120):
  var origin=Vector3.ZERO if i<48 else Vector3(rng.randf_range(-.4,.4),rng.randf_range(-1,1),0)
  var velocity=Vector3(rng.randf_range(-.9,.9),rng.randf_range(.1,1.0),rng.randf_range(-.9,.9))
  impact.append({"origin":[origin.x,origin.y,origin.z],"velocity":[velocity.x,velocity.y,velocity.z]})
 var f=FileAccess.open(OUTPUT,FileAccess.WRITE)
 f.store_string(JSON.stringify({"flight":flight,"impact":impact}))
 print("ORIGINAL_PLASMA_PARTICLES_EXPORTED ",flight.size()," ",impact.size())
 quit()
'''.replace('OUTPUT',json.dumps(destination))
    path=output/'ExportPlasmaParticles.gd';path.write_text(script)
    win_script=subprocess.check_output(['wslpath','-w',str(path)],text=True).strip()
    win_project=subprocess.check_output(['wslpath','-w',str(project)],text=True).strip()
    command=[str(godot),'--headless','--path',win_project,'--script',win_script]
    (output/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    with (output/'capture.log').open('w') as stream:
        subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=60)
    return output/'plasma-particles.json'
