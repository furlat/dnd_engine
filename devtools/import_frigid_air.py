"""Preserve accepted quiet air and register its original component geometry."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from devtools.import_assembly_media import SOURCE_CAMERAS
from devtools.import_registered_media import import_registered_bank
from devtools.media_delivery import contained_media_path,install_verified_payloads
from game.construction_surface import WallMesh

ROOT=Path(__file__).resolve().parents[1]


def install(source: Path, mesh_export: Path, preserved: Path, production: Path, repo: Path=ROOT) -> dict:
    manifest=json.loads((source/'media.json').read_text());cameras={};payloads={}
    for camera,original in enumerate(SOURCE_CAMERAS):
        layers={}
        for side in ('back','front'):
            bank=manifest['banks'][f'ice-v0-hazard/d0/q{original}/{side}']
            if bank['times']!=[5.5+(i+1)/32 for i in range(256)]:
                raise ValueError('Original quiet air clock differs')
            if bank['registration']['worldHeadingRadians']!=0 or bank['registration']['pivot']!=[256,311.425626]:
                raise ValueError('Original quiet air placement differs')
            for page in bank['pages']:
                path=contained_media_path(source,page['path']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
                if digest!=page['sha256']:raise ValueError('Original quiet air page changed')
                payloads[page['path']]=digest
            layers[side]={'frames':bank['frames'],'pages':[p['path'] for p in bank['pages']]}
        cameras[str(camera)]={'layers':layers}
    row={'fps':32,'frames':256,'cell':512,'pivot':manifest['pivot'],'palette':('183a55','326585','609dbc','a6d5e4','e2f0ed'),'cameras':cameras}
    original_mesh=(mesh_export/'mesh.json').read_bytes();mesh=WallMesh.model_validate_json(original_mesh)
    if len(mesh.vertices)!=len(mesh.normals) or len(mesh.vertices)!=len(mesh.uv) or len(mesh.indices)%3:
        raise ValueError('Unpaired original air SphereMesh')
    if min(mesh.indices)<0 or max(mesh.indices)>=len(mesh.vertices):raise ValueError('Invalid source SphereMesh indices')
    # Read source contracts, generated adapter and selected source bytes first.
    metadata={name:(source/name).read_bytes() for name in ('HANDOFF.md','media.json','ice-v0-hazard/d0/q0/back/adapter.gd')}
    metadata['air-sphere-export.gd']=(mesh_export/'adapter.gd').read_bytes()
    for name,content in metadata.items():
        target=contained_media_path(preserved,name)
        if target.exists() and target.read_bytes()!=content:raise ValueError('Preserved air source differs')
    bindings_path=repo/'game/data/wall_media/bindings.json';assets_path=repo/'game/data/wall_media/projectile-assets.json'
    bindings=json.loads(bindings_path.read_text());assets={a['assetId']:a for a in json.loads(assets_path.read_text())}
    with TemporaryDirectory(prefix='frigid-air-') as temporary:
        staging=Path(temporary)
        normalized=staging/'original';normalized.mkdir()
        for name in payloads:
            target=contained_media_path(normalized,name);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(contained_media_path(source,name).read_bytes())
        (normalized/'SHA256SUMS').write_text(''.join(digest+'  '+name+'\n' for name,digest in sorted(payloads.items())))
        import_registered_bank(normalized,row,'frigid_air_d0',(('hold',0,256),),staging,bundle='wall_media')
        imported=json.loads((staging/'game/data/wall_media/bindings.json').read_text())
        added=json.loads((staging/'game/data/wall_media/projectile-assets.json').read_text())
        copied=staging/'game/assets/wall_media'
        (copied/'air-sphere.json').write_bytes(original_mesh)
        rows=(*tuple((name,'game/assets/wall_media/'+name,digest) for name,digest in payloads.items()),
            ('air-sphere.json','game/assets/construction_operators/air-sphere.json',hashlib.sha256(original_mesh).hexdigest()))
        install_verified_payloads(copied,rows,preserved=preserved,production=production,repo=repo)
    for name,content in metadata.items():
        target=contained_media_path(preserved,name);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    bindings['projectileStorage'].update(imported['projectileStorage']);assets.update({a['assetId']:a for a in added})
    bindings.setdefault('resources',{})['/construction/air-sphere.json']='game/assets/construction_operators/air-sphere.json'
    bindings_path.write_text(json.dumps(bindings,separators=(',',':'))+'\n');assets_path.write_text(json.dumps(list(assets.values()),indent=2)+'\n')
    receipt={'source':str(source),'sphereExport':str(mesh_export),'preserved':str(preserved),
        'sourceHashes':{name:hashlib.sha256(content).hexdigest() for name,content in metadata.items()},
        'rgba':'Original d0 quiet bank preserved byte-exact; four native views, no fabricated heading banks.',
        'operator':'Original flat16-step stationary density +14flakes, original dome SphereMesh+24flakes; native owner transform through existing triangle compositor.',
        'payloads':payloads,'sphereSha256':hashlib.sha256(original_mesh).hexdigest()}
    (repo/'game/data/wall_media/frigid-air-source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (preserved/'source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return {'pages':len(payloads),'assets':len(added),'sphereVertices':len(mesh.vertices)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--mesh-export',type=Path,required=True);parser.add_argument('--preserved',type=Path,required=True)
    parser.add_argument('--production',type=Path,required=True);args=parser.parse_args()
    print(install(args.source,args.mesh_export,args.preserved,args.production))
