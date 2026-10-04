"""Select literal roar-cast-v5 components on existing class action and status owners."""
import copy
import hashlib
import json
from math import cos,sin,sqrt
from pathlib import Path

from PIL import Image,ImageDraw,ImageFilter
from pydantic import JsonValue

from devtools.import_registered_media import DIRECTIONS
from devtools.media_delivery import install_verified_payloads
from dnd.content_system.condition_definitions import CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.classes.fighter import Indomitable,Survivor
from dnd.classes.barbarian import RelentlessRage
from game.animation_data import load_animation_data
from game.animation_types import BodyActionRecipe, SpatialMediaBinding
from game.condition_types import ConditionRecipe

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'game/data/class_media'
PALETTES={'reckless':0xe55747,'quickened':0x80c9e2,'twinned':0x80c9e2,'distant':0x80c9e2,
 'affinity.fire':0xc8513c,'affinity.cold':0x559ac5,'affinity.lightning':0x51aabd,
 'affinity.acid':0x9caa48,'affinity.poison':0x6f9756}
ACTIVITIES=['idle','move','jump','forced_move','attack','cast','act','hit']
COLORS=dict(primary=0xffffff,secondary=0xffffff,tertiary=0xffffff)


def markers():
    """Original preview.js icon paths, stroke1.5/shadow4; no invented pictograms."""
    stage=ROOT/'.runtime/class-media-20261004/markers';stage.mkdir(parents=True,exist_ok=True)
    bindings=json.loads((FOLDER/'bindings.json').read_text());assets=json.loads((FOLDER/'projectile-assets.json').read_text())
    assets=[row for row in assets if not row['assetId'].startswith('class.marker.')]
    payloads=[]
    for kind,color in PALETTES.items():
        shape=kind.split('.')[0];n=8;mask=Image.new('L',(32*n,32*n));draw=ImageDraw.Draw(mask)
        def line(points):draw.line([((x+16)*n,(y+16)*n) for x,y in points],fill=255,width=12,joint='curve')
        if shape=='reckless':
            line([(-6,-7),(6,7)]);line([(6,-7),(-6,7)]);line([(-8,3),(-8,7),(-4,7)])
        elif shape=='quickened':
            line([(-5,-7),(2,0),(-5,7)]);line([(1,-7),(8,0),(1,7)])
        elif shape=='twinned':
            for x in (-4,4):draw.ellipse(((x-4+16)*n,12*n,(x+4+16)*n,20*n),outline=255,width=12)
        elif shape=='distant':
            line([(-7,0),(7,0)]);line([(3,-4),(7,0),(3,4)])
        else:line([(0,-7),(6,0),(0,7),(-6,0),(0,-7)])
        rgb=((color>>16)&255,(color>>8)&255,color&255)
        glow=Image.new('RGBA',mask.size,(*rgb,0));glow.putalpha(mask.filter(ImageFilter.GaussianBlur(2*n)))
        stroke=Image.new('RGBA',mask.size,(*rgb,0));stroke.putalpha(mask)
        image=Image.alpha_composite(glow,stroke).resize((32,32),Image.Resampling.LANCZOS)
        filename=kind+'.png';image.save(stage/filename)
        runtime='game/assets/class_media/markers/'+filename;identity='class.marker.'+kind
        payloads.append((filename,runtime,hashlib.sha256((stage/filename).read_bytes()).hexdigest()))
        assets.append(dict(assetId=identity,displayName=identity,kind='projectile',sheet='/'+identity+'.png',
            frame=dict(width=32,height=32,rows=8,cols=1),fps=32,rowOrder=list(DIRECTIONS),
            phases=dict(impact=dict(start=0,frames=1,fps=32,loop=True)),anchor=dict(x=.5,y=.75),
            defaultScale=1,palettePreview=dict(colors=[color])))
        bindings['projectileStorage'][identity]=dict(phases=dict(impact=dict(layers=[dict(
            parts=[[dict(file=runtime,rect=[0,0,32,32],offset=[0,0])]],blendMode='normal')])))
    receipt=install_verified_payloads(stage,tuple(payloads),
        preserved=Path('/home/tommaso/Dev/neurodragon_art/sources/class-actions-roar-cast-v5-20261004/markers'),
        production=Path('/home/tommaso/Dev/neurodragon_art-production'),repo=ROOT)
    (FOLDER/'markers-source.json').write_text(json.dumps(dict(source='preview.js icon()',
        geometry='literal authored paths; stroke1.5 and shadowBlur4; 8x raster coverage',files=receipt),indent=2)+'\n')
    (FOLDER/'bindings.json').write_text(json.dumps(bindings,separators=(',',':'))+'\n')
    (FOLDER/'projectile-assets.json').write_text(json.dumps(assets,separators=(',',':'))+'\n')


def author():
    data=load_animation_data();actions=[]
    def track(asset,**kw):
        return dict(id=asset,assetId=asset,attachment='source_ground',scale=.5,**kw)
    def pair(treatment,kind,**kw):
        return [track(f'class.{treatment}.{kind}-q0-{side}',depth='behind_body' if side=='back' else 'front_body',**kw)
            for side in ('back','front')]
    def action(identity,clip='Idle4',media=(),enabled=True,feature=None,handler_response=False):
        row=(data.body_action_recipes[identity] if identity in data.body_action_recipes else
            data.body_action_recipes['action.class.fighter.second_wind']).model_dump(mode='json')
        if feature is not None:row['definitionRef']=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[feature].ref.model_dump(mode='json')
        row['actor'].update(enabled=enabled,clip=clip,playbackSpeed=1,media=[])
        row['anchors']=[dict(name='action_start',frame=0),dict(name='effect',frame=0),dict(name='recover',frame=14)]
        row['media']=list(media);row['actionFeedback']=None;row['handlerResponse']=handler_response
        BodyActionRecipe.model_validate_json(json.dumps(row));actions.append(row)
    action('action.class.fighter.second_wind','Idle2',pair('second_wind','heal',startOffsetMs=450,requireHealingApplied=True))
    action('action.class.fighter.action_surge',media=pair('action_surge','burst',startOffsetMs=200,alpha=.9))
    action('class_feature.fighter.indomitable',feature=Indomitable,handler_response=True,
        media=[dict(t,scale=.425) for t in pair('indomitable','burst',startOffsetMs=600,alpha=.8,requiredSaveSuccess=True)])
    action('class_feature.barbarian.relentless_rage',enabled=False,feature=RelentlessRage,handler_response=True,
        media=[dict(t,scale=.425) for t in pair('relentless','burst',startOffsetMs=600,alpha=.8,requiredSaveSuccess=True)])
    action('class_feature.fighter.survivor','Idle',enabled=False,feature=Survivor,handler_response=True,
        media=pair('second_wind','heal',startOffsetMs=450,alpha=.55,requireHealingApplied=True))
    action('reaction.class_feature.fighter.protection',handler_response=True)
    for kind in ('rage','frenzy'):
        action('action.class.barbarian.'+kind,media=[track(f'class.{kind}.ground-q0-ground',
            depth='ground',durationMs=950,loop=True,alpha=.6 if kind=='frenzy' else .4,
            fadeInMs=180,fadeOutMs=350,fadeCurve='smoothstep',startOffsetMs=100)])
    action('action.class.barbarian.end_rage',enabled=False)
    action('action.class.barbarian.reckless_attack')
    for identity in ('intimidating_presence','extend_intimidating_presence'):
        action('action.class.barbarian.'+identity,media=[dict(track('class.intimidate.threat',startOffsetMs=220),
            poseSocket='face',depth='front_body')])
    for identity,reverse,sockets in [('convert_slot_to_sorcery_points',True,('hand','other_hand')),
            ('convert_sorcery_points_to_slot',False,('hand',))]:
        tracks=[]
        for socket in sockets:
            charge:dict[str,JsonValue]=dict(track('class.font_gather.charge-q0-all',alpha=.95),
                id='charge-'+socket,scale=.3,poseSocket=socket,
                assetIdsByCamera=[f'class.font_gather.charge-q{q}-all' for q in range(4)])
            if reverse:charge['timeMap']=[dict(elapsedMs=0,sourceFrame=39),dict(elapsedMs=1250,sourceFrame=0)]
            tracks.append(charge)
        action('action.class.sorcerer.'+identity,'Special1',tracks)
    for kind in ('quickened','twinned','distant'):
        action('action.class.sorcerer.'+kind+'_spell','Special1',[
            dict(track(f'class.{kind}.{kind}-q0-all',alpha=.95),poseSocket='hand')])
    action('action.class.sorcerer.elemental_affinity.resistance','Special1')
    action('action.class.sorcerer.dragon_wings.toggle','Idle',media=[dict(t,scale=.4,durationMs=1250,loop=True,
        fadeInMs=180,fadeOutMs=350,requireAppliedConditionId='class_feature.sorcerer.dragon_wings.active')
        for t in pair('wings','mantle',alpha=.4)])
    action('action.class.sorcerer.draconic_presence','Special1',[
        dict(track(f'class.{kind}.charge-q0-all',alpha=.95),id='charge-'+mode,scale=.3,poseSocket='hand',
            whenPresenceMode=mode,assetIdsByCamera=[f'class.{kind}.charge-q{q}-all' for q in range(4)])
        for mode,kind in (('awe','awe'),('fear','draconic_fear'))])
    (FOLDER/'action-recipes.json').write_text(json.dumps(actions,indent=2)+'\n')
    condition_path=ROOT/'game/data/condition-recipes.json';document=json.loads(condition_path.read_text())
    recipes={row['definitionRef']['content_id']:row for row in document['recipes']}
    media_path=ROOT/'game/data/condition-media.json';media=json.loads(media_path.read_text())
    concentration=data.condition_recipes['condition.concentrating'].model_dump(mode='json')
    concentration['definitionRef']=dict(data.condition_recipes['class_feature.sorcerer.metamagic_active'].definitionRef.model_dump(mode='json'),
        content_id='class_feature.sorcerer.draconic_presence')
    recipes['class_feature.sorcerer.draconic_presence']=concentration
    def register(asset,scale=.5,**kw):
        media['layers'][asset]=dict(category='ClassOriginal',animation='original',asset_id=asset,scale=scale,**kw)
        return asset
    def layer(asset,attachment='body',opacity:float=1.,**kw):
        register(asset)
        return dict(id=asset,assetId=asset,category='ClassOriginal',animation='original',attachment=attachment,
            fps=32,opacity=opacity,activeDuring=ACTIVITIES,priority=50,colors=COLORS,**kw)
    def effect(asset,alpha=1,**kw):
        register(asset)
        return dict(id=asset,assetId=asset,category='ClassOriginal',animation='original',attachment='body',
            opacity=alpha,priority=50,colors=COLORS,durationMs=1250,**kw)
    def condition(identity):
        row=copy.deepcopy(recipes.get(identity) or data.condition_recipes[identity].model_dump(mode='json'))
        row['disposition']='authored';row['classification'].update(runtimeRole='active_combat_state',
            visualIntensity='ambient_passive',presentationDomains=['body_overlay'])
        row['composition'].update(group='class-'+identity,exclusiveGroup=None,priority=50,maxLayers=3)
        return row
    for kind,identity,colors in [('rage','raging',[0x7b2629,0xc74439,0xec8763,0xff9a78]),
            ('frenzy','frenzied',[0x78262b,0xda393f,0xf07b68,0xff826e])]:
        row=condition('class_feature.barbarian.'+identity)
        row['composition'].update(group='class-rage',exclusiveGroup='class-rage',priority=61 if kind=='frenzy' else 60,maxLayers=1)
        row['persistent']['bodyRamp']=dict(colors=colors,mapping='flowing_film',texture='class.material.film',
            textureFrames=64,textureFps=32,textureWeight=.4,gain=.48 if kind=='frenzy' else .34,applicationMs=180,removalMs=350)
        row['persistent']['layers']=[layer(f'class.{kind}.mantle-q0-{side}',opacity=.70 if kind=='frenzy' else .52,
            fadeInMs=180,drawOrder='behind_body' if side=='back' else 'in_front_of_body') for side in ('back','front')]
        for side in ('back','front'):media['layers'][f'class.{kind}.mantle-q0-{side}']['removal_fade_ms']=350
        recipes[row['definitionRef']['content_id']]=row
    row=condition('class_feature.barbarian.reckless_attacking')
    row['persistent']['layers']=[layer('class.marker.reckless','head',.85)]
    recipes[row['definitionRef']['content_id']]=row
    row=condition('class_feature.sorcerer.metamagic_active')
    row['persistent']['layers']=[layer('class.marker.'+kind,'head',.55,whenMetamagicMode=kind)
        for kind in ('quickened','twinned','distant')]
    recipes[row['definitionRef']['content_id']]=row
    row=condition('class_feature.sorcerer.elemental_affinity.resistance')
    row['persistent']['layers']=[layer('class.marker.affinity.'+kind,'head',.55,whenEnergyType=kind.title())
        for kind in ('fire','cold','lightning','acid','poison')]
    effects=[effect('class.affinity.'+kind+'.'+side,whenEnergyType=kind.title(),
        drawOrder='behind_body' if side=='back' else 'in_front_of_body')
        for kind in ('fire','cold','lightning','acid','poison') for side in ('back','front')]
    row['application'].update(durationMs=1250,effects=[dict(e,opacity=.78) for e in effects])
    row['responses']=[dict(trigger='damage_received',effects=[dict(e,opacity=.95) for e in effects])]
    recipes[row['definitionRef']['content_id']]=row
    for identity,spec in media['layers'].items():
        if identity.startswith('class.marker.'):spec['actor_top_clearance_px']=3
    for row in recipes.values():ConditionRecipe.model_validate_json(json.dumps(row))
    document['recipes']=list(recipes.values());condition_path.write_text(json.dumps(document,indent=2)+'\n')
    media_path.write_text(json.dumps(media,indent=2)+'\n')
    world_path=ROOT/'game/data/world_bindings.json'
    bindings=json.loads(world_path.read_text())
    layers=[]
    for mode,kind in (('awe','awe'),('fear','draconic_fear')):
        for i in range(49):
            radius=sqrt((i+.5)/49)*9.3;angle=i*2.399963
            layers.append(dict(assetId=f'class.{kind}.presence-q0-ground',composition='clump',whenPresenceMode=mode,
                offsetCells=[cos(angle)*radius,sin(angle)*radius],phaseOffsetMs=i*137,
                scale=1.85+(i%3)*.1,alpha=.6))
    field=dict(layers=layers,holdStartFrame=0,holdFrames=64,fps=32,scale=.5,formationFadeMs=180,removalFadeMs=350)
    SpatialMediaBinding.model_validate_json(json.dumps(field))
    bindings['spatial_media'].pop('class_feature.sorcerer.draconic_presence.aura',None)
    bindings['spatial_media']['spatial_effect.class_feature.draconic_presence']=field
    world_path.write_text(json.dumps(bindings,indent=2)+'\n')


if __name__=='__main__':
    markers();author()
