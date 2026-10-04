"""Install original construction donor textures and exported mesh/pose records."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.construction_surface import ConstructionComponents, ForceMotes

ROOT=Path(__file__).resolve().parents[1]


def pack(donors: Path, geometry: Path, output: Path) -> dict:
    force=json.loads((donors/'force.json').read_text());ice=json.loads((donors/'ice.json').read_text())
    output.mkdir(parents=True,exist_ok=True)
    textures={};payloads=[]
    for key,record in (('force_overlay',force['textures']['Overlay_Texture']),
            ('ice_add',ice['textures']['AddTexture']),('ice_details',ice['textures']['DetailsTexture']),
            ('ice_gradient',ice['textures']['Color1DGradient'])):
        path=contained_media_path(donors,record['file']);content=path.read_bytes()
        width,height=record['size']
        if min(width,height)<=0 or len(content)<width*height*16:
            raise ValueError('Original donor texture dimensions differ')
        samples=np.frombuffer(content,dtype='<f4',count=width*height*4)
        if not np.isfinite(samples).all():
            raise ValueError('Nonfinite donor texture')
        shutil.copyfile(path,output/path.name);textures[key]=record
        payloads.append(path.name)
    domes=[];sources=[]
    for radius in (5,10):
        folder=geometry/str(radius);receipt=json.loads((folder/'source.json').read_text())
        source=Path(receipt['source'])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=receipt['sourceSha256']:
            raise ValueError('Original construction adapter changed')
        for relative,digest in receipt['hashes'].items():
            if hashlib.sha256(contained_media_path(folder,relative).read_bytes()).hexdigest()!=digest:
                raise ValueError('Original geometry export changed')
        mesh=json.loads((folder/'geometry.json').read_text());poses=json.loads((folder/'poses.json').read_text())
        if mesh['radiusFeet']!=radius or poses['fps']!=144 or poses['breakTick']!=591:
            raise ValueError('Construction radius/clock changed')
        mesh['poses']=poses['frames'];domes.append(mesh);sources.append(receipt)
    components={'textures':textures,'domes':domes}
    admitted=ConstructionComponents.model_validate_json(json.dumps(components))
    for dome in admitted.domes:
        if len(dome.pieces)!=72 or len(dome.poses)!=341 or tuple(p.tick for p in dome.poses)!=tuple(range(590,931)):
            raise ValueError('Incomplete native ice shell')
        for mesh in (dome.whole,*(piece.mesh for piece in dome.pieces)):
            if len(mesh.vertices)!=len(mesh.normals) or len(mesh.vertices)!=len(mesh.uv) or len(mesh.indices)%3:
                raise ValueError('Unpaired original mesh channels')
            if min(mesh.indices)<0 or max(mesh.indices)>=len(mesh.vertices):
                raise ValueError('Invalid original triangle index')
        if any(len(p.poses)!=72 or any(len(t)!=12 or not np.isfinite(t).all() for t in p.poses) for p in dome.poses):
            raise ValueError('Invalid original rigid transform')
    (output/'components.json').write_text(json.dumps(components,separators=(',',':'))+'\n');payloads.append('components.json')
    result={'sources':sources,'geometrySource':str(geometry),'donorSource':str(donors),'donorHashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in donors.iterdir() if p.is_file()},'payloads':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in payloads},
        'adaptation':'Original textures, triangle geometry and recorded Godot transforms; production source-material evaluation on native admitted dimensions.'}
    (output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def install(packed: Path, preserved: Path, production: Path, repo: Path=ROOT) -> dict:
    receipt=json.loads((packed/'receipt.json').read_text())
    ConstructionComponents.model_validate_json((packed/'components.json').read_bytes())
    donors=Path(receipt['donorSource'])
    for name,digest in receipt['donorHashes'].items():
        if hashlib.sha256(contained_media_path(donors,name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Original donor export changed')
    bindings_path=repo/'game/data/wall_media/bindings.json'
    bindings=json.loads(bindings_path.read_text())
    rows=tuple((name,'game/assets/construction_operators/'+name,digest) for name,digest in receipt['payloads'].items())
    # Every metadata source is loaded before the first payload write.
    originals=[('donors/'+name,(donors/name).read_bytes()) for name in receipt['donorHashes']]
    for source in receipt['sources']:
        original=Path(source['source']);content=original.read_bytes()
        if hashlib.sha256(content).hexdigest()!=source['sourceSha256']:
            raise ValueError('Original construction source changed')
        originals.append(('source/'+original.name,content))
        folder=Path(receipt['geometrySource'])/str(source['radiusFeet'])
        for name,digest in source['hashes'].items():
            content=contained_media_path(folder,name).read_bytes()
            if hashlib.sha256(content).hexdigest()!=digest:
                raise ValueError('Geometry export changed before install')
            originals.append((str(source['radiusFeet'])+'/'+name,content))
    for name,content in originals:
        target=contained_media_path(preserved/'originals',name)
        if target.exists() and target.read_bytes()!=content:
            raise ValueError('Conflicting preserved source')
    install_verified_payloads(packed,rows,preserved=preserved/'production',production=production,repo=repo)
    for name,content in originals:
        target=contained_media_path(preserved/'originals',name);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(content)
    bindings.setdefault('resources',{})['/construction/operators.json']='game/assets/construction_operators/components.json'
    bindings_path.write_text(json.dumps(bindings,separators=(',',':'))+'\n')
    for destination in (preserved/'source.json',repo/'game/data/wall_media/construction-operator-source.json'):
        destination.write_text(json.dumps(receipt,indent=2)+'\n')
    return {'payloads':len(rows),'bytes':sum((packed/name).stat().st_size for name in receipt['payloads'])}


def install_force_motes(source: Path, accepted: Path, preserved: Path, production: Path, repo: Path=ROOT) -> dict:
    """Preserve accepted RGBA dependencies and install only exact source metadata."""
    receipt=json.loads((source/'source.json').read_text())
    original=Path(receipt['source'])
    if hashlib.sha256(original.read_bytes()).hexdigest()!=receipt['sourceSha256']:
        raise ValueError('Force adapter changed')
    originals=[('adapter-original.gd',original.read_bytes())]
    for name,digest in receipt['hashes'].items():
        content=contained_media_path(source,name).read_bytes()
        if hashlib.sha256(content).hexdigest()!=digest:raise ValueError('Force export changed')
        originals.append(('export/'+name,content))
    record=ForceMotes.model_validate_json((source/'motes.json').read_bytes())
    if {(r.form,r.sizeFeet) for r in record.groups}!={('dome',5),('dome',10),*(('panels',i*10) for i in range(1,11))}:
        raise ValueError('Native Force dimensions incomplete')
    if any(len(r.motes)!=60 or any(not np.isfinite((*m.origin,*m.velocity,*m.size)).all() or min(m.size)<=0 for m in r.motes) for r in record.groups):
        raise ValueError('Invalid original owner motes')
    pixels=contained_media_path(source,record.noise.file).read_bytes();width,height=record.noise.size
    if min(width,height)<=0 or len(pixels)<width*height*16 or not np.isfinite(np.frombuffer(pixels,dtype='<f4')).all():
        raise ValueError('Invalid original Force noise')
    dependencies=json.loads((accepted/'delivery-dependencies.json').read_bytes())
    media=(accepted/dependencies['manifest']).read_bytes()
    if hashlib.sha256(media).hexdigest()!=dependencies['manifestSHA256']:
        raise ValueError('Accepted Force manifest changed')
    # Keep the complete delivered package and all pinned V1 dependencies. Paths
    # are required to resolve beneath the source study, including V2 symlinks.
    base=accepted.parent.resolve()
    for path in accepted.rglob('*'):
        if path.is_file():
            resolved=path.resolve()
            if not resolved.is_relative_to(base):raise ValueError('Force source escapes study')
            originals.append(('accepted/'+str(path.relative_to(accepted)),resolved.read_bytes()))
    for row in dependencies['pages']:
        path=(accepted/row['manifestPath']).resolve()
        if not path.is_relative_to(base):raise ValueError('Force dependency escapes study')
        content=path.read_bytes()
        if len(content)!=row['bytes'] or hashlib.sha256(content).hexdigest()!=row['sha256']:
            raise ValueError('Accepted Force page changed')
        originals.append(('dependencies/'+str(path.relative_to(base)),content))
    for name,content in originals:
        target=contained_media_path(preserved,name)
        if target.exists() and target.read_bytes()!=content:raise ValueError('Conflicting preserved Force source')
    rows=tuple((name,'game/assets/construction_operators/force/'+name,hashlib.sha256((source/name).read_bytes()).hexdigest()) for name in ('motes.json',record.noise.file))
    bindings_path=repo/'game/data/wall_media/bindings.json';bindings=json.loads(bindings_path.read_bytes())
    install_verified_payloads(source,rows,preserved=preserved/'production',production=production,repo=repo)
    for name,content in originals:
        target=contained_media_path(preserved,name);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    bindings.setdefault('resources',{})['/construction/force-motes.json']='game/assets/construction_operators/force/motes.json'
    original_bytes=bindings_path.read_bytes();text=json.dumps(bindings,separators=(',',':'))+'\n'
    bindings_path.write_bytes(text.replace('\n','\r\n' if b'\r\n' in original_bytes else '\n').encode())
    result={'export':receipt,'acceptedSource':str(accepted),'acceptedPages':len(dependencies['pages']),
        'acceptedManifestSha256':dependencies['manifestSHA256'],
        'preservedHashes':{name:hashlib.sha256(content).hexdigest() for name,content in originals},
        'payloads':{destination:digest for _,destination,digest in rows}}
    for target in (preserved/'source.json',repo/'game/data/wall_media/force-motes-source.json'):
        target.write_text(json.dumps(result,indent=2)+'\n')
    return {'payloads':len(rows),'acceptedPages':len(dependencies['pages'])}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--donors',type=Path)
    parser.add_argument('--geometry',type=Path);parser.add_argument('--packed',type=Path)
    parser.add_argument('--force-motes',type=Path);parser.add_argument('--accepted',type=Path)
    parser.add_argument('--preserved',type=Path,required=True);parser.add_argument('--production',type=Path,required=True)
    args=parser.parse_args()
    if args.force_motes is not None:
        if args.accepted is None:parser.error('--accepted is required for Force motes')
        print(install_force_motes(args.force_motes,args.accepted,args.preserved,args.production))
    else:
        if args.donors is None or args.geometry is None or args.packed is None:parser.error('Original donor/geometry/packed paths are required')
        pack(args.donors,args.geometry,args.packed)
        print(install(args.packed,args.preserved,args.production))
