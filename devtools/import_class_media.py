"""Preserve roar-cast-v5 and select its original atlases and literal RGB palettes."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from io import BytesIO

import numpy as np
from PIL import Image

from devtools.import_registered_media import DIRECTIONS
from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage
from game.animation_data import load_animation_data

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SHA256 = "d046dd3171ae1d85fe213490995ddaf140f9e1ce90be3d90db55ed159a96e2de"


def palette_pixels(pixels: np.ndarray, colors: tuple[str, ...]) -> np.ndarray:
    """Exact accepted preview.js colorAt: source red/239, three RGB endpoints."""
    palette = np.array([[int(color[index:index+2], 16) for index in (1, 3, 5)]
        for color in colors[:3]], dtype=np.float64)
    scaled = np.clip(pixels[..., 0].astype(np.float64) / 239, 0, 1) * 2
    first = np.minimum(1, np.floor(scaled).astype(int))
    amount = (scaled - first)[..., None]
    result = pixels.copy()
    colored = np.floor(palette[first]*(1-amount)+palette[first+1]*amount+.5).astype(np.uint8)
    visible = pixels[..., 3] > 0
    result[..., :3][visible] = colored[visible]
    return result


def import_class_media(source: Path, *, preserved: Path, production: Path,
    stage: Path, rig_source: Path, repo: Path = ROOT) -> dict:
    manifest_bytes = (source / "manifest.json").read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Expected the accepted roar-cast-v5 manifest")
    manifest = json.loads(manifest_bytes)
    proposals = {row['id']: row for row in json.loads((source.parent/'proposals.json').read_text())['proposals']}
    for original in source.rglob('*'):
        if not original.is_file():
            continue
        target = contained_media_path(preserved, original.relative_to(source).as_posix())
        if target.exists() and target.read_bytes() != original.read_bytes():
            raise ValueError(f"Preserved class source differs: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(original, target)
    proposal_copy = preserved / 'approved-proposals.json'
    original_proposals = (source.parent/'proposals.json').read_bytes()
    if proposal_copy.exists() and proposal_copy.read_bytes() != original_proposals:
        raise ValueError('Preserved class proposals differ')
    proposal_copy.write_bytes(original_proposals)
    stage.mkdir(parents=True, exist_ok=True)
    assets, storage, payloads, conversions = [], {}, {}, []
    resources = {}
    data = load_animation_data()
    original_archive = Path('/home/tommaso/Dev/neurodragon_art/sources/item-equipment-20261002/Stand-alone Character creator - 2D Fantasy V1.3.zip')
    archive = zipfile.ZipFile(original_archive)
    archive_root = 'Fantasy Character Creator_Data/StreamingAssets/Spritesheets/'
    pose_sources = {}
    idle_sheets = data.rigs[data.root_rig].clips['Idle'].sheets
    for category, identity in idle_sheets.items():
        source_idle = contained_media_path(rig_source, category+'/Idle.png')
        use_archive = archive.read(archive_root+category+'/Idle.png') == data.resources[identity].read_bytes()
        if not use_archive and source_idle.read_bytes() != data.resources[identity].read_bytes():
            raise ValueError(f'Original class pose family differs from the installed Idle: {category}')
        pose_sources[category] = str(original_archive) if use_archive else str(rig_source)
        for clip in ('Idle2','Idle4'):
            relative = f'rig/{category}/{clip}.png'
            origin = contained_media_path(rig_source, f'{category}/{clip}.png')
            original_bytes = (archive.read(archive_root+category+'/'+clip+'.png') if use_archive
                else origin.read_bytes())
            image = Image.open(BytesIO(original_bytes))
            if image.mode != 'RGBA' or image.size != (1920,1024):
                raise ValueError(f'Unexpected original class pose layout: {origin}')
            target = contained_media_path(stage, relative)
            target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(original_bytes)
            runtime = 'game/assets/class_media/'+relative
            payloads[relative] = (relative,runtime,hashlib.sha256(original_bytes).hexdigest())
            resources[f'/spritesheets/{category}/{clip}.png'] = runtime
    archive.close()

    def prepare(key: str, palette: tuple[str, ...], treatment: str) -> tuple[dict, str]:
        bank = manifest['banks'][key]
        path = contained_media_path(source, bank['file'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != bank['sha256']:
            raise ValueError(f'Class source hash differs: {path}')
        image = Image.open(path)
        if image.mode != 'RGBA':
            raise ValueError('Class sources must retain straight RGBA')
        relative = f'{treatment}/{key}.png'
        target = contained_media_path(stage, relative)
        if relative not in payloads:
            target.parent.mkdir(parents=True, exist_ok=True)
            original = np.array(image)
            transformed = palette_pixels(original, palette)
            if not np.array_equal(original[..., 3], transformed[..., 3]):
                raise AssertionError('Palette conversion changed source alpha')
            Image.fromarray(transformed).save(target, optimize=True)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            payloads[relative] = (relative, 'game/assets/class_media/'+relative, digest)
            conversions.append(dict(source=bank['file'], source_sha256=bank['sha256'],
                selected=relative, palette=palette, sha256=digest,
                operator='preview.js colorAt; original alpha and crop registration'))
        return bank, 'game/assets/class_media/'+relative

    def register(identity: str, keys: tuple[str, ...], treatment: str, palette: tuple[str, ...],
        *, row_offset: int = 0) -> None:
        selected = [prepare(key, palette, treatment) for key in keys]
        bank = selected[0][0]
        width, height = bank['canvas']
        count = bank['count']
        views = {}
        for row, facing in enumerate(DIRECTIONS):
            current, path = selected[(row+row_offset)%8 if len(keys) == 8 else 0]
            if (current['canvas'], current['count'], current['pivot']) != (bank['canvas'], count, bank['pivot']):
                raise ValueError('Class direction banks disagree on registration')
            views[facing] = [[dict(file=path, rect=frame['source'], offset=frame['offset'])]
                if current['alphaPixelsByFrame'][index] else []
                for index, frame in enumerate(current['frames'])]
        asset = dict(assetId=identity, displayName=identity, sheet='/'+identity+'.png',
            frame=dict(width=width, height=height, rows=8, cols=count), fps=32,
            rowOrder=list(DIRECTIONS), phases=dict(impact=dict(start=0,frames=count,fps=32,loop=bank['loop'])),
            anchor=dict(x=bank['pivot'][0]/width,y=bank['pivot'][1]/height), defaultScale=1,
            palettePreview=dict(colors=[int(color[1:],16) for color in palette[:3]]))
        selected_storage = dict(phases=dict(impact=dict(layers=[dict(partsByFacing=views,blendMode='normal')])))
        AuthoredProjectileAsset.model_validate_json(json.dumps(asset))
        ProjectileStorage.model_validate_json(json.dumps(selected_storage))
        assets.append(asset); storage[identity] = selected_storage

    pairs = dict(rage=('mantle','ground'), frenzy=('mantle','ground'),
        relentless=('burst',), action_surge=('burst',), indomitable=('burst',),
        second_wind=('heal',), wings=('mantle',), awe=('presence','charge'),
        draconic_fear=('presence','charge'), font_gather=('charge',),
        quickened=('quickened',),twinned=('twinned',),distant=('distant',))
    for treatment, kinds in pairs.items():
        palette = tuple(proposals[treatment]['palette'][:3])
        if treatment == 'wings': palette = ('#254e69','#64aec7','#c5d8d8')
        for kind in kinds:
            keys = [key for key in manifest['banks'] if key.startswith(kind+'-q')]
            for key in keys:
                register('class.'+treatment+'.'+key, (key,), treatment, palette)
    for energy, palette in dict(fire=('#572932','#c8513c','#ed9973'),
        cold=('#1d4661','#559ac5','#b9dce6'),lightning=('#17486c','#51aabd','#e8c275'),
        acid=('#55552a','#9caa48','#c8ce83'),poison=('#304e38','#6f9756','#b3c589')).items():
        for side in ('back','front'):
            key = 'affinity-q0-'+side
            register('class.affinity.'+energy+'.'+side, (key,), 'affinity-'+energy, palette)
    register('class.intimidate.threat', tuple('threat-h'+str(index)+'-all' for index in range(8)),
        'intimidate', tuple(proposals['intimidate']['palette'][:3]), row_offset=-1)
    crimson = ('#642b2b','#bf5745','#e4ccb1')
    register('class.martial.melee1.attack1', tuple('slash-h'+str(index)+'-all' for index in range(8)),
        'martial', crimson)
    register('class.martial.impact', ('impact-q0-all',), 'martial', crimson)
    # Reassemble the original scalar movie; no actor alpha or new material is baked.
    film = manifest['banks']['film-q0-all']
    film_path = contained_media_path(source, film['file'])
    if hashlib.sha256(film_path.read_bytes()).hexdigest() != film['sha256']:
        raise ValueError('Original film source hash differs')
    original = Image.open(film_path)
    field = Image.new('RGBA', (128,128*film['count']))
    for index, frame in enumerate(film['frames']):
        x,y,w,h = frame['source']; ox,oy = frame['offset']
        field.paste(original.crop((x,y,x+w,y+h)), (ox,index*128+oy))
    field_path = stage/'film-field.png'; field.save(field_path,optimize=True)
    payloads['film-field.png'] = ('film-field.png','game/assets/class_media/film-field.png',
        hashlib.sha256(field_path.read_bytes()).hexdigest())
    installed = install_verified_payloads(stage, tuple(payloads.values()), preserved=preserved/'selected',
        production=production, repo=repo)
    folder = repo/'game/data/class_media'; folder.mkdir(parents=True,exist_ok=True)
    bindings_path = folder/'bindings.json'
    bindings = json.loads(bindings_path.read_text()) if bindings_path.exists() else dict(resources={},projectileStorage={})
    bindings['projectileStorage'].update(storage)
    bindings['resources'].update(resources)
    bindings['resources']['class.material.film'] = 'game/assets/class_media/film-field.png'
    bindings_path.write_text(json.dumps(bindings,separators=(',',':'))+'\n')
    asset_path=folder/'projectile-assets.json'
    existing=json.loads(asset_path.read_text()) if asset_path.exists() else []
    selected={row['assetId'] for row in assets}
    combined=[row for row in existing if row['assetId'] not in selected]+assets
    asset_path.write_text(json.dumps(combined,separators=(',',':'))+'\n')
    receipt = dict(source=str(source),rig_source=str(rig_source),original_archive=str(original_archive),
        original_archive_sha256=hashlib.sha256(original_archive.read_bytes()).hexdigest(),
        pose_sources=pose_sources,preserved=str(preserved),revision='roar-cast-v5',
        manifest_sha256=MANIFEST_SHA256,film_source_sha256=film['sha256'],files=installed,conversions=conversions,
        identities=[asset['assetId'] for asset in assets])
    (folder/'source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source','preserved','production','stage','rig-source'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    receipt = import_class_media(args.source,preserved=args.preserved,production=args.production,
        stage=args.stage,rig_source=args.rig_source)
    print(f"Installed {len(receipt['identities'])} class records / {len(receipt['files'])} payloads")
