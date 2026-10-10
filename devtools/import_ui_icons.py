"""Install the explicit CIE28 handoff through the existing private-art manifest."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from PIL import Image

from devtools.art import ROOT, MANIFEST, copy_file, digest, read_manifest, write_json
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from game.ui_composition import compose_ui_media
from game.ui.media_types import ChoiceRecord


ARCHIVE_SHA256 = 'da85d0f936d05e9e4630cc3c0060dcbd142ed9c778233dfbddb5e80691b84f11'
PREFIX = 'ui-icons-cie28-delivery-2026-10-05/'


def import_smooth_icons(archive: Path, sources: Path, production: Path) -> None:
    """Install the complete smooth handoff at its existing exact icon keys."""
    checksum = digest(archive)
    original = sources / 'original-delivery.zip'
    if original.exists() and digest(original) != checksum:
        raise ValueError('Preserved smooth icon delivery differs')
    if not original.exists():
        copy_file(archive, original)
    media = json.loads((ROOT / 'game/data/ui_media.json').read_text())
    current_choices = [ChoiceRecord.model_validate(row) for row in
                       json.loads((ROOT / 'game/data/ui_choices.json').read_text())]
    selected = {}
    with ZipFile(original) as package:
        manifest = json.loads(package.read('manifest.json'))
        bindings = json.loads(package.read('replacement-bindings.json'))
        choices = json.loads(package.read('choice-bindings.json'))
        if len(bindings) != 620 or len(manifest['rows']) != 594 or len(choices) != 103:
            raise ValueError('Incomplete smooth icon handoff')
        expected = {row['unpixelated']['file']: row['unpixelated'] for row in manifest['rows']}
        if {row['smooth144'] for row in bindings.values()} != set(expected):
            raise ValueError('Smooth icon files and bindings disagree')
        if not {key[5:] for key in media if key.startswith('icon:')} <= bindings.keys():
            raise ValueError('An existing icon is missing from the replacement')
        delivered_choices = [ChoiceRecord(owner=row['owner'], facet=row['facetKey'],
            value=str(row['value']), icon_key=row['iconKey'], label=row['label'],
            requirements={('form' if key == 'wall_form' else key): value
                          for key, value in row.get('requires', {}).items()}) for row in choices
                             if row.get('exposure') == 'discovery' and row.get('facetKey')]
        if delivered_choices != current_choices:
            raise ValueError('Smooth handoff changes native choice bindings')
        for relative, row in expected.items():
            path = PurePosixPath(relative)
            if path.is_absolute() or '..' in path.parts or path.parts[0] != 'smooth144':
                raise ValueError(f'Invalid smooth icon path: {relative}')
            payload = package.read(relative)
            if len(payload) != row['bytes'] or sha256(payload).hexdigest() != row['sha256']:
                raise ValueError(f'Smooth icon differs from manifest: {relative}')
            with Image.open(BytesIO(payload)) as png:
                if png.size != (144, 144) or png.mode != 'RGBA':
                    raise ValueError(f'Smooth icon dimensions or channels differ: {relative}')
            preserved = sources / relative
            if preserved.exists() and preserved.read_bytes() != payload:
                raise ValueError(f'Preserved smooth icon differs: {relative}')
            preserved.parent.mkdir(parents=True, exist_ok=True)
            preserved.write_bytes(payload)
            installed = 'game/assets/ui_smooth/' + path.name
            for destination in (ROOT / installed, production / installed):
                if not destination.exists() or digest(destination) != row['sha256']:
                    copy_file(preserved, destination)
            selected[installed] = {'path': installed, 'bytes': len(payload), 'sha256': row['sha256']}
        for key, row in bindings.items():
            media['icon:' + key] = {'path': 'ui_smooth/' + PurePosixPath(row['smooth144']).name,
                                    'native_size': [144, 144], 'pivot': [0, 0], 'scale': 1}
    for root in (production, ROOT / '.runtime'):
        installation = read_manifest(root)
        files = {row['path']: row for row in installation['files']}
        files.update(selected)
        write_json(root / MANIFEST, {'version': 1, 'files': sorted(files.values(), key=lambda row: row['path'])})
    write_json(ROOT / 'game/data/ui_media.json', media)
    write_json(sources / 'admission.json', {'archive_sha256': checksum,
        'format': 'smooth144', 'binding_count': len(bindings), 'choice_count': len(choices),
        'files': list(selected.values())})
    print(f'Installed {len(selected)} smooth icons for {len(bindings)} exact keys; portraits and choices preserved')


def import_icons(archive: Path, sources: Path, production: Path) -> None:
    if digest(archive) != ARCHIVE_SHA256:
        raise ValueError('CIE28 archive differs from the delivered handoff')
    sources.mkdir(parents=True, exist_ok=True)
    original = sources / 'original-delivery.zip'
    if original.exists() and digest(original) != ARCHIVE_SHA256:
        raise ValueError('Preserved UI source archive has changed')
    if not original.exists():
        copy_file(archive, original)
    with ZipFile(original) as package:
        with ZipFile(BytesIO(package.read(PREFIX+'cie28-runtime-art.zip'))) as runtime:
            for name in runtime.namelist():
                path = PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts or '\\' in name:
                    raise ValueError(f'Invalid UI source path: {name}')
                if name.endswith('/'):
                    continue
                target = sources / 'runtime' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = runtime.read(name)
                if target.exists() and target.read_bytes() != payload:
                    raise ValueError(f'Preserved UI source differs: {name}')
                target.write_bytes(payload)
    source_root = sources / 'runtime'
    runtime_data = json.loads((source_root / 'runtime-manifest.json').read_text())
    required = json.loads((source_root / 'player-ui-manifest.json').read_text())
    variants = json.loads((source_root / 'variant-manifest.json').read_text())
    overlay = json.loads((source_root / 'overlays/manifest.json').read_text())
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    catalog = compose_ui_media()
    media = json.loads((ROOT / 'game/data/ui_media.json').read_text())
    presentation = json.loads((ROOT / 'game/data/ui_presentation.json').read_text())
    selected: dict[str, dict] = {}
    bindings: dict[str, tuple[str, tuple[int, int]]] = {}

    def select(key: str, file: str, checksum: str, size: tuple[int, int]) -> None:
        source = source_root / file
        if digest(source) != checksum:
            raise ValueError(f'UI image failed its source hash: {file}')
        with Image.open(source) as image:
            if image.size != size or image.mode != 'RGBA':
                raise ValueError(f'UI image dimensions/alpha disagree: {file}')
        selected[file] = {'path': f'game/assets/ui_cie28/{file}', 'bytes': source.stat().st_size, 'sha256': checksum}
        bindings[key] = file, size

    for row in runtime_data['rows']:
        select('icon:'+row['key'], row['file'], row['sha256'], tuple(row['size']))
    refreshed = []
    for row in required['rows']:
        owner = row['owner']
        ref = catalog.content_refs.get(owner['content_id'])
        if ref is None or (ref.pack_id, ref.definition_kind.value, ref.content_version) != (owner['pack_id'], owner['definition_kind'], owner['content_version']):
            raise ValueError(f'Delivered UI owner is not current content: {row["key"]}')
        icon_key = catalog.content[ref].presentation.icon_key
        # Internal/generic conditions intentionally have no native icon. The
        # explicitly supplied fallback is retained under its requested key;
        # this does not make a new public mechanical condition.
        icon_key = icon_key or row['key']
        select('icon:'+icon_key, row['file'], row['sha256'], tuple(row['nativeSize']))
        source_key = row['sourceIconKey']
        # A shared condition image also retains its manifest-named spell
        # address when that address was absent from the ordinary icon bank.
        if 'icon:'+source_key not in media and 'icon:'+source_key not in bindings:
            select('icon:'+source_key, row['file'], row['sha256'], tuple(row['nativeSize']))
        refreshed.append({'subject':row['key'], 'owner':ref.model_dump(mode='json'), 'icon_key':icon_key, 'file':row['file']})
    select('skin:slot.pixel28', overlay['file'], overlay['sha256'], tuple(overlay['sourceSize']))
    # Choice artwork is staged with its explicit ownership. Its widgets consume
    # only facets actually returned by current discovery, never configuration-
    # supported branches merely mentioned in an artist's manifest.
    choices = []
    for row in variants['choices']:
        ref = catalog.content_refs.get(row['owner']['content_id'])
        if ref is None:
            raise ValueError(f'Unknown choice owner: {row["owner"]["content_id"]}')
        if row.get('exposure') != 'discovery' or not row.get('facetKey'):
            continue
        image = next(value for value in (*variants['rows'], *runtime_data['rows']) if value['key'] == row['iconKey'])
        select('icon:'+image['key'], image['file'], image['sha256'], tuple(image['size']))
        choices.append({'owner':ref.model_dump(mode='json'), 'facet':row['facetKey'], 'value':str(row['value']),
            'icon_key':row['iconKey'], 'label':row['label'],
            'requirements':{('form' if key=='wall_form' else key):value for key,value in row.get('requires', {}).items()}})
    for file, row in selected.items():
        for destination in (production / row['path'], ROOT / row['path']):
            copy_file(source_root / file, destination)
            if digest(destination) != row['sha256']:
                raise ValueError(f'UI installation verification failed: {destination}')
    for key, (file, size) in bindings.items():
        media[key] = {'path':'ui_cie28/'+file, 'native_size':list(size), 'pivot':[0,0], 'scale':1}
    common = {'end_turn':'ui.end-turn-medallion', 'waiting':'ui.waiting-medallion',
        'page_next':'ui.page-next', 'page_previous':'ui.page-previous', 'slot_border':None}
    for name, icon in common.items():
        if icon is not None:
            presentation['common'][name] = {'label':name.replace('_',' ').title(), 'presentation':{'icon_key':icon}, 'approximation':None}
    for root in (production, ROOT / '.runtime'):
        manifest = read_manifest(root)
        old = {row['path']:row for row in manifest['files']}
        old.update((row['path'],row) for row in selected.values())
        write_json(root / MANIFEST, {'version':1, 'files':sorted(old.values(),key=lambda row:row['path'])})
    write_json(ROOT / 'game/data/ui_media.json',media)
    write_json(ROOT / 'game/data/ui_presentation.json',presentation)
    write_json(ROOT / 'game/data/ui_choices.json',choices)
    write_json(sources / 'admission.json', {'archive_sha256':ARCHIVE_SHA256,'files':list(selected.values()),'refreshed_owners':refreshed})
    print(f'Installed {len(selected)} unchanged CIE28 files, {sum(row["bytes"] for row in selected.values()):,} bytes; {len(refreshed)} native subject bindings')


def import_portraits(archive: Path, sources: Path, production: Path) -> None:
    """Bind role-specific pixels to exact existing original source identities."""
    sources.mkdir(parents=True, exist_ok=True)
    original = sources / 'original-delivery.zip'
    checksum = digest(archive)
    if original.exists() and digest(original) != checksum:
        raise ValueError('Preserved portrait source archive has changed')
    if not original.exists():
        copy_file(archive, original)
    media = json.loads((ROOT / 'game/data/ui_media.json').read_text())
    selected = []
    with ZipFile(original) as package:
        manifest = json.loads(package.read('portraits/manifest.json'))
        for row in manifest['entries']:
            for role, image in row['files'].items():
                name = PurePosixPath(image['file'])
                if name.is_absolute() or '..' in name.parts or '\\' in image['file']:
                    raise ValueError('Invalid portrait source path')
                target = sources / image['file']
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = package.read(image['file'])
                if target.exists() and target.read_bytes() != payload:
                    raise ValueError('Preserved portrait pixels differ')
                target.write_bytes(payload)
                if digest(target) != image['sha256']:
                    raise ValueError(f'Portrait failed its source hash: {image["file"]}')
                with Image.open(target) as png:
                    if png.size != tuple(manifest['nativeSizes'][role]) or png.mode != 'RGBA':
                        raise ValueError(f'Portrait dimensions/alpha disagree: {image["file"]}')
                if row['collection'] != 'existing-cie':
                    continue
                # Match the original file address, not names, aliases or subjects.
                source = Path(row['source']).relative_to('/home/tommaso/Dev/NeuroClient/app/public')
                bindings = [key for key, value in media.items()
                            if key.startswith('portrait:') and value['path'] == 'ui_recovered/' + source.as_posix()]
                if len(bindings) != 1 or digest(Path(row['source'])) != row['sourceSha256']:
                    raise ValueError(f'Portrait original identity/source differs: {row["key"]}')
                registration = bindings[0] + ':' + role
                relative = 'game/assets/ui_pixelated/' + image['file']
                selected.append({'path': relative, 'bytes': target.stat().st_size,
                                 'sha256': image['sha256'], 'registration': registration})
                for destination in (production / relative, ROOT / relative):
                    copy_file(target, destination)
                    if digest(destination) != image['sha256']:
                        raise ValueError(f'Portrait installation differs: {relative}')
                media[registration] = {'path': 'ui_pixelated/' + image['file'],
                                      'native_size': image['size'], 'pivot': [0,0], 'scale': 1}
        if len(selected) != manifest['existingPortraitCount'] * len(manifest['nativeSizes']):
            raise ValueError('Incomplete pixelated portrait bank')
        (sources / 'manifest.json').write_bytes(package.read('portraits/manifest.json'))
    for root in (production, ROOT / '.runtime'):
        installation = read_manifest(root)
        old = {row['path']: row for row in installation['files']}
        old.update((row['path'], {key:value for key,value in row.items() if key != 'registration'}) for row in selected)
        write_json(root / MANIFEST, {'version':1, 'files':sorted(old.values(), key=lambda row:row['path'])})
    write_json(ROOT / 'game/data/ui_media.json', media)
    write_json(sources / 'admission.json', {'archive_sha256':checksum, 'files':selected})
    print(f'Installed {len(selected)} unchanged role portraits; original portraits and identities retained')



def import_creature_portraits(archive: Path, sources: Path, production: Path) -> None:
    """Validate the exact content/rig pair and install unchanged native role PNGs."""
    checksum='b2ecf653234a75f4ed4cd81b63814825d71ef1fd010be058b01178db8546073a'
    if digest(archive)!=checksum:
        raise ValueError('Creature portrait archive differs from the delivered handoff')
    sources.mkdir(parents=True,exist_ok=True)
    original=sources/'original-delivery.zip'
    if original.exists() and digest(original)!=checksum:
        raise ValueError('Preserved creature portrait archive differs')
    if not original.exists():
        copy_file(archive,original)
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    catalog=compose_ui_media()
    media=json.loads((ROOT/'game/data/ui_media.json').read_text())
    portraits={}
    selected=[]
    with ZipFile(original) as package:
        manifest=json.loads(package.read('manifest.json'))
        if len(manifest['entries'])!=41 or manifest['completedPortraits']!=41:
            raise ValueError('Incomplete creature portrait bank')
        for row in manifest['entries']:
            ref=next((ref for ref in catalog.content if ref.identity_key==row['contentRef'] or ref.model_dump(mode='json')==row['contentRef']),None)
            rig=ROOT/'game/data/rigs'/Path(row['rig']).name
            binding=json.loads(rig.read_text())
            if (ref is None or ref.content_id!=row['contentId']
                or binding['rig_id']!=row['rigId'] or ref.identity_key not in binding['creature_content_refs']
                or digest(rig)!=row['rigSha256']):
                raise ValueError(f'Creature content/rig identity changed: {row["key"]}')
            body=ROOT/'game/assets'/Path(row['bodySource']).relative_to('/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/game/assets')
            if digest(body)!=row['bodySourceSha256']:
                raise ValueError(f'Creature source body changed: {row["key"]}')
            portrait_key=catalog.content[ref].presentation.portrait_key
            if portrait_key is None:
                raise ValueError('Native creature descriptor has no portrait key')
            portraits[ref.identity_key]={'ref':ref.model_dump(mode='json'),'rig_id':row['rigId'],
                'label':row['label'],'presentation':{'portrait_key':portrait_key}}
            for role,image in row['files'].items():
                name=PurePosixPath(image['file'])
                if name.is_absolute() or '..' in name.parts or '\\' in image['file']:
                    raise ValueError('Invalid creature portrait path')
                target=sources/image['file']
                payload=package.read(image['file'])
                if target.exists() and target.read_bytes()!=payload:
                    raise ValueError('Preserved creature portrait pixels differ')
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(payload)
                if digest(target)!=image['sha256']:
                    raise ValueError(f'Creature portrait hash differs: {image["file"]}')
                with Image.open(target) as png:
                    if png.size!=tuple(manifest['nativeSizes'][role]) or png.mode!='RGBA':
                        raise ValueError('Creature portrait dimensions/alpha differ')
                relative='game/assets/ui_pixelated/creatures/'+image['file']
                selected.append({'path':relative,'bytes':len(payload),'sha256':image['sha256']})
                for destination in (ROOT/relative,production/relative):
                    copy_file(target,destination)
                    if digest(destination)!=image['sha256']:
                        raise ValueError('Creature portrait installation differs')
                resource={'path':'ui_pixelated/creatures/'+image['file'],'native_size':image['size'],'pivot':[0,0],'scale':1}
                media['portrait:'+portrait_key+':'+role]=resource
                if role=='hud':
                    media['portrait:'+portrait_key]=resource
        (sources/'manifest.json').write_bytes(package.read('manifest.json'))
    if len(selected)!=123 or len(portraits)!=41:
        raise ValueError('Creature portrait coverage differs')
    for root in (production,ROOT/'.runtime'):
        installation=read_manifest(root)
        old={row['path']:row for row in installation['files']}
        old.update((row['path'],row) for row in selected)
        write_json(root/MANIFEST,{'version':1,'files':sorted(old.values(),key=lambda row:row['path'])})
    write_json(ROOT/'game/data/ui_media.json',media)
    write_json(sources/'admission.json',{'archive_sha256':checksum,'files':selected,'bindings':portraits})
    print(f'Installed {len(selected)} unchanged creature portraits for {len(portraits)} exact content/rig pairs')

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--sources',type=Path,required=True)
    parser.add_argument('--production',type=Path,required=True)
    parser.add_argument('--portraits',action='store_true',help='Import the portrait-only handoff instead of CIE28 icons')
    parser.add_argument('--creatures',action='store_true',help='Import exact creature portrait roles')
    parser.add_argument('--smooth',action='store_true',help='Import the complete smooth144 replacement')
    args = parser.parse_args()
    importer=(import_smooth_icons if args.smooth else import_creature_portraits if args.creatures
              else import_portraits if args.portraits else import_icons)
    importer(args.archive,args.sources,args.production)


if __name__ == '__main__':
    main()
