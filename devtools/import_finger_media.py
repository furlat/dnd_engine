"""Lossless registration of original Finger source and native heading captures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

from devtools.import_registered_media import DIRECTIONS
from devtools.media_delivery import contained_media_path, install_verified_payloads
from devtools.repack_support_media import _repack_layer
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=Path('/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review')


def pack(native:Path,stage:Path)->dict:
    stage.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ORIGINAL/'finger-of-death-approved-media.json').read_text())
    storage={};assets=[];source_hashes={}

    def register(identity:str,row:dict,views:dict)->None:
        count,cell=row['frames'],row['cell']
        asset={'assetId':identity,'displayName':identity,'sheet':'/'+identity+'.png',
            'frame':{'width':cell,'height':cell,'rows':8,'cols':count},'fps':32,'rowOrder':list(DIRECTIONS),
            'phases':{'impact':{'start':0,'frames':count,'fps':32,'loop':False}},
            'anchor':{'x':row['pivot'][0]/cell,'y':row['pivot'][1]/cell},'defaultScale':1,
            'palettePreview':{'colors':[int(v,16) for v in row.get('palette',['ffffff'])]}}
        selected={'phases':{'impact':{'layers':[{'partsByFacing':views,'blendMode':'normal'}]}}}
        AuthoredProjectileAsset.model_validate_json(json.dumps(asset));ProjectileStorage.model_validate_json(json.dumps(selected))
        assets.append(asset);storage[identity]=selected

    for branch,key in (('normal','finger_ground_magic_v8'),('cameo','finger_counterspell_v5')):
        row=manifest[key]
        for quadrant in range(4):
            # Native batch slots ascend CCW; the game's camera quarters descend.
            camera_slot=(-quadrant)%4
            for side in ('back','front'):
                def facing_parts(index: int, facing: str) -> tuple[str,list,str,str]:
                    world_row=(index-2*quadrant)%8
                    heading=(3-world_row)%8
                    folder=native/branch/f'd{heading}'/f'q{camera_slot}'/side
                    paths=sorted((folder/'frames').glob('frame_*.png'))
                    if len(paths)!=104 or not (folder/'capture.json').is_file():
                        raise ValueError(f'Incomplete original pose capture: {folder}')
                    frames=[];pages=[]
                    for path in paths:
                        pages.append(path.relative_to(native).as_posix())
                        with Image.open(path) as image:
                            if image.mode!='RGBA' or image.size!=(768,768):raise ValueError(str(path))
                            box=image.getchannel('A').getbbox()
                        frames.append(None if box is None else {'page':len(pages)-1,
                            'source':[box[0],box[1],box[2]-box[0],box[3]-box[1]],'offset':[box[0],box[1]]})
                    packed=_repack_layer(native.resolve(),stage.resolve(),{'pages':pages,'frames':frames},list(range(104)),
                        f'hand/{branch}/q{quadrant}/{side}/{facing}',2048)
                    parts=[[] if frame is None else [{'file':'game/assets/finger_media/'+packed['pages'][frame['page']],
                        'rect':frame['source'],'offset':frame['offset']}] for frame in packed['frames']]
                    return facing, parts, folder.relative_to(native).as_posix(), hashlib.sha256((folder/'adapter.gd').read_bytes()).hexdigest()
                with ThreadPoolExecutor(max_workers=8) as pool:
                    results=tuple(pool.map(facing_parts,range(8),DIRECTIONS))
                views={facing:parts for facing,parts,_,_ in results}
                source_hashes.update({key:digest for _,_,key,digest in results})
                print(f'Packed {branch} q{quadrant} {side}',flush=True)
                register(f'finger.hand.{branch}.{side}.q{quadrant}',row,views)
    for key,prefix in (('finger_death_impact_v2','finger.contact'),('counterspell_stop_v1','finger.counterspell')):
        row=manifest[key]
        for side in ('back','front'):
            if not any(row['cameras'][str(q)]['layers'][side]['frames'] for q in range(4)):
                continue
            # Empty source back layers remain explicit empty parts; no pixels invented.
            for quadrant in range(4):
                layer=row['cameras'][str(quadrant)]['layers'][side]
                for relative in layer['pages']:
                    target=stage/'original'/relative;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(ORIGINAL/relative,target)
                parts=[[] if frame is None else [{'file':'game/assets/finger_media/original/'+layer['pages'][frame['page']],
                    'rect':frame['source'],'offset':frame['offset']}] for frame in layer['frames']]
                register(f'{prefix}.{side}.q{quadrant}',row,{facing:parts for facing in DIRECTIONS})
    shutil.copytree(native/'components',stage/'components',dirs_exist_ok=True)
    result={'assets':assets,'storage':storage,'source_adapter_sha256':source_hashes,
        'approved_manifest_sha256':hashlib.sha256((ORIGINAL/'finger-of-death-approved-media.json').read_bytes()).hexdigest()}
    (stage/'selection.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    return result


def install(native:Path,stage:Path,preserved:Path,production:Path)->dict:
    selection=json.loads((stage/'selection.json').read_text())
    # Preserve every complete source cell and its invocation separately from crops.
    shutil.copytree(native,preserved/'native',dirs_exist_ok=True)
    original=preserved/'approved'
    original.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ORIGINAL/'finger-of-death-approved-media.json').read_text())
    originals={'finger-of-death-approved-media.json','skeletal-finger-2b3413c31d2b.js'}
    originals.update(path.relative_to(ORIGINAL).as_posix() for path in (ORIGINAL/'production-handoff').rglob('*') if path.is_file())
    originals.update(relative for row in manifest.values() for camera in row['cameras'].values()
        for layer in camera['layers'].values() for relative in layer['pages'])
    for relative in originals:
        target=contained_media_path(original,relative);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ORIGINAL/relative,target)
    payloads=tuple((path.relative_to(stage).as_posix(),'game/assets/finger_media/'+path.relative_to(stage).as_posix(),
        hashlib.sha256(path.read_bytes()).hexdigest()) for path in stage.rglob('*')
        if path.is_file() and (path.suffix in ('.png','.rgba32f') or path.name in ('darkness-mesh.json','splinter.json')))
    files=install_verified_payloads(stage,payloads,preserved=preserved/'selected',production=production,repo=ROOT)
    folder=ROOT/'game/data/finger_media';folder.mkdir(parents=True,exist_ok=True)
    bindings={'spells':{'spell.finger_of_death':{'content_id':'spell.finger_of_death','content_version':1,'definition_contract_hash':'e4d439f0a9828e38cd3ff0522ba3e140b0d419f4c24de2900d8c3a8e7349cb00','definition_kind':'spell','pack_id':'content.srd_5_1_cc'}},'resources':{'/finger/darkness-mesh.json':'game/assets/finger_media/components/darkness-mesh.json'},
        'projectileStorage':selection['storage']}
    (folder/'bindings.json').write_text(json.dumps(bindings,separators=(',',':'))+'\n')
    (folder/'projectile-assets.json').write_text(json.dumps(selection['assets'],separators=(',',':'))+'\n')
    receipt={'native_source':str(native),'preserved':str(preserved),'files':files,
        'approved_manifest_sha256':selection['approved_manifest_sha256'],
        'source_adapter_sha256':selection['source_adapter_sha256'],
        'camera_slot_map':[0,3,2,1],'native_heading_from_world_row':'(3-row)%8',
        'normal_model':'SkeletalArm.glb','cameo_model':'SkeletalCounterspellV5.glb',
        'mesh_source':'ProjectileVFX/Scenes/VFX_Darkness_projectile.tscn'}
    (folder/'source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('pack','install'))
    for name in ('native','stage','preserved','production'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.operation=='pack':
        print('Packed',len(pack(args.native,args.stage)['assets']),'registered sources')
    else:
        print('Installed',len(install(args.native,args.stage,args.preserved,args.production)['files']),'payloads')
