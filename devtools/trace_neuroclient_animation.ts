/** Offline source oracle; no Python runtime dependency on Bun/Pixi/NeuroClient.
 * Run from this repository with NeuroClient's installed native Bun executable:
 *   /path/to/NeuroClient/app/node_modules/@oven/bun-linux-x64-baseline/bin/bun \
 *     devtools/trace_neuroclient_animation.ts --source-app /path/to/NeuroClient/app \
 *     --data-root game/data/neuroclient --output tests/game/fixtures/neuroclient_animation_timing.json
 * Add --magic-missile and select neuroclient_magic_missile_timing.json for the
 * separate original-runtime A/B/A volley trace.
 * Original source owners run unchanged. Only diagnostics, texture/font/GPU IO,
 * frame delivery and watchdog IO are substituted. This is not a gameplay mapper.
 * Imports follow mock registration because Bun must install those IO boundaries
 * before loading the external source; nothing is vendored or rewritten.
 */
import { mock } from 'bun:test';
import { existsSync, lstatSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { basename, dirname, resolve } from 'node:path';
import { parseArgs } from 'node:util';
const {values}=parseArgs({options:{
  'source-app':{type:'string'},'data-root':{type:'string'},output:{type:'string'},
  'magic-missile':{type:'boolean',default:false},
},strict:true});
if(!values['source-app']||!values['data-root']||!values.output)
  throw Error('Required: --source-app PATH --data-root PATH --output PATH');
const app=realpathSync(values['source-app']),dataRoot=realpathSync(values['data-root']);
const outputPath=resolve(realpathSync(dirname(resolve(values.output))),basename(values.output));
const sourceRoot=dirname(app);
if(outputPath===sourceRoot||outputPath.startsWith(sourceRoot+'/'))throw Error('Output must be outside NeuroClient');
if(existsSync(outputPath)&&(!lstatSync(outputPath).isFile()||lstatSync(outputPath).isSymbolicLink()))throw Error('Output must be a regular file');
const sourceRevision=execFileSync('git',['rev-parse','HEAD'],{cwd:app,encoding:'utf8'}).trim();
if(sourceRevision!=='d274f2d62ca9c1c5ed62a77841cacf6cc0347491')throw Error('source revision changed');
if(execFileSync('git',['status','--porcelain'],{cwd:app,encoding:'utf8'}).trim())throw Error('source checkout is dirty');
let now=0;
let events:any[]=[];
const record=(kind:string, value:any={})=>events.push({timeMs:now,kind,...value});
// Diagnostics are the only import path to the absent old SDK; never executed
// for timing. Drawing below uses real Pixi objects but no GPU or font rasterizer.
mock.module(app+'/src/render/runtimeBoundaryTelemetry.ts',()=>({recordClipReadiness:()=>{}}));
mock.module(app+'/src/render/presentationDiagnostics.ts',()=>({recordPresentationControlPlaneFailure:()=>{}}));
mock.module(app+'/src/render/animationCoverage.ts',()=>({recordSubjectiveIntentLifecycle:()=>{},recordSubjectiveTransactionLifecycle:()=>{}}));
mock.module(app+'/src/render/log.ts',()=>({LOG:{
  fsm:(uuid:string,from:string,to:string,trigger:string,clip:string)=>record('body-state',{uuid,from,to,trigger,clip}),
  onFrame:(uuid:string,frame:number,mode:string)=>record('body-anchor',{uuid,frame,mode}),
  queue:()=>{},dispatch:()=>{},events:()=>{},
}}));
const {Container,Graphics,Sprite,Texture,TextureSource,DOMAdapter}=await import(app+'/node_modules/pixi.js/lib/index.mjs');
DOMAdapter.set({...DOMAdapter.get(),createCanvas:()=>({getContext:()=>null})} as any);
const textureMeta=new Map<any,any>();
function texture(meta:any){
  const value=new Texture({source:new TextureSource({width:128,height:128})});
  textureMeta.set(value,meta);return value;
}
mock.module(app+'/src/render/pixiRendering.ts',()=>({createPixiText:(options:any)=>{
  const text=new Sprite(texture({kind:'text',value:options.text}));
  record('number-visible',{value:options.text});
  text.on('destroyed',()=>record('number-removed',{value:options.text}));
  return text;
}}));
const {AnimatedEntity}=await import(app+'/src/render/AnimatedEntity.ts');
const CastClip=await import(app+'/src/render/clips/CastClip.ts');
const TakeDamageClip=await import(app+'/src/render/clips/TakeDamageClip.ts');
const DeathClip=await import(app+'/src/render/clips/DeathClip.ts');
const HitFlash=await import(app+'/src/render/clips/HitFlashFx.ts');
const FloatingText=await import(app+'/src/render/clips/FloatingText.ts');
const {resolveAuthoredSpellPresentation}=await import(app+'/src/render/spellAuthoring/runtimeResolver.ts');
const {compileCastPresentationPhaseGraph}=await import(app+'/src/render/spellAuthoring/phaseGraph.ts');
const {contentRefKey}=await import(app+'/src/render/contentPresentationCatalog.ts');
const {buildTimelineModel}=await import(app+'/src/ui/spellStudio/timelineBuild.ts');
const {ClipQueue}=await import(app+'/src/render/clipQueue.ts');
const {createFrameDrivenPresentationClock}=await import(app+'/src/render/presentationRuntimeHost.ts');
const rig=JSON.parse(readFileSync(dataRoot+'/rig-tables.json','utf8'));
const sourceDrafts=JSON.parse(readFileSync(dataRoot+'/spell-studio-drafts.materialized.json','utf8'));
const catalogInput=JSON.parse(readFileSync(dataRoot+'/catalog-input.json','utf8'));
const projectileAssets=JSON.parse(readFileSync(app+'/public/studio/spell-projectile-assets.json','utf8'));
const contexts=JSON.parse(readFileSync(app+'/src/render/data/animation/actionContextPresentation.json','utf8')).contexts;
const sheetCache=new Map<string,any>();
const projectileCache=new Map<string,any>();
function rigFrames(category:string,clip:string){
  const key=category+'/'+clip;
  if(!sheetCache.has(key)){
    const png=readFileSync(app+'/public/spritesheets/'+key+'.png');
    if(png.readUInt32BE(16)!==rig.CELL_W*rig.SHEET_COLS || png.readUInt32BE(20)!==rig.CELL_H*8)throw Error('wrong rig dimensions '+key);
    sheetCache.set(key,Object.fromEntries(Object.keys(rig.FACING_ROW).map(facing=>[facing,
      Array.from({length:rig.SHEET_COLS},(_,index)=>texture({kind:'rig',category,clip,facing,index}))])));
  }
  return sheetCache.get(key);
}
const assets={
  preloadRigSheets:async(entries:any[])=>{for(const [category,clip] of entries)rigFrames(category,clip);},
  getRigSheet:(category:string,clip:string)=>sheetCache.get(category+'/'+clip),
  loadAuthoredProjectile:async(asset:any,owner:string)=>{
    record('projectile-resource',{owner});
    if(!projectileCache.has(asset.assetId)){
      const png=readFileSync(app+'/public'+asset.sheet);
      if(png.readUInt32BE(16)!==asset.frame.width*asset.frame.cols||png.readUInt32BE(20)!==asset.frame.height*asset.frame.rows)throw Error('wrong projectile dimensions');
      projectileCache.set(asset.assetId,{phases:Object.fromEntries(Object.entries(asset.phases).map(([phase,spec]:any)=>[
        phase,Object.fromEntries(asset.rowOrder.map((facing:string)=>[facing,
          Array.from({length:spec.frames},(_,index)=>texture({kind:'projectile',phase,facing,index}))]))]))});
    }
    return projectileCache.get(asset.assetId);
  },
};
const appearance=Object.fromEntries(rig.SLOT_RENDER_ORDER.map((slot:string)=>[slot,null]));
Object.assign(appearance,{
  body:{category:'NakedBody',tint:0xffffff},head:{category:'Head22',tint:0xffffff},
  helmet:{category:'Head15',tint:0xffffff},chest:{category:'Chest14',tint:0xffffff},
  legs:{category:'Legs1',tint:0xffffff},belt:{category:'Belt2',tint:0xffffff},
  shoes:{category:'Shoes1',tint:0xffffff},weapon:{category:'Melee1',tint:0xffffff},
  shadow:{category:'Shadow',tint:0xffffff,alpha:0.5},
});
for(const category of ['NakedBody','Head22','Head15','Chest14','Legs1','Belt2','Shoes1','Melee1','Shadow','Magic2']){
  for(const clip of ['Idle','Attack5','TakeDamage','Die','Taunt'])rigFrames(category,clip);
}
// Drain actual asynchronous source continuations without advancing time. One
// immediate turn is an event-loop boundary, not a guessed real-time sleep.
const flush=()=>new Promise<void>(resolve=>setImmediate(resolve));
function freeze(value:any){if(value&&typeof value==='object'){for(const child of Object.values(value))freeze(child);Object.freeze(value);}return value;}
async function runCase(config:any){
  now=0;events=[];let frameCallbacks:(()=>void)[]=[];
  const clock=createFrameDrivenPresentationClock({nowMs:()=>now,requestFrame:(callback:()=>void)=>frameCallbacks.push(callback)});
  const worldLayer=new Container(),floorLayer=new Container(),vfxLayer=new Container();
  const caster=new AnimatedEntity({uuid:'caster',gx:0,gy:0,appearance,visualScale:0.5,visualScaleX:0.5,
    facing:'E',initialState:'Idle',preloadAllClips:false,worldLayer,floorLayer,presentationAssets:assets});
  const target=new AnimatedEntity({uuid:'target',gx:config.target[0],gy:config.target[1],appearance,
    visualScale:0.5,visualScaleX:0.5,facing:'W',initialState:config.terminal?'Dead':'Idle',
    preloadAllClips:false,worldLayer,floorLayer,presentationAssets:assets});
  await Promise.all([caster.waitForPresentationReady(),target.waitForPresentationReady()]);
  let hp=config.terminal?0:20;
  const entities=new Map([['caster',caster],['target',target]]);
  const ctx:any={worldLayer,floorLayer,vfxLayer,presentationAssets:assets,animationClock:clock,
    getEntity:(uuid:string)=>entities.get(uuid),isCancelled:()=>false,
    onIntentLifecycle:(intent:any,phase:string)=>record('intent-'+phase,{type:intent.type}),
    patchEntityVitals:(uuid:string,patch:any)=>{hp=patch.hp??hp;record('vitals',{uuid,...patch});},
    dispatchChildren:async(children:any[])=>{await Promise.all(children.map(async child=>{
      record('child-start',{type:child.type});
      if(child.type==='takeDamage')await TakeDamageClip.run(child,ctx);
      else if(child.type==='die')await DeathClip.run(child,ctx);
      else if(child.type==='hitFlash')await HitFlash.run(child,ctx);
      else if(child.type==='floatingNumber')await FloatingText.run(child,ctx);
      else throw Error('unsupported fixture child '+child.type);
      record('child-settled',{type:child.type});
    }));},
  };
  const draft=structuredClone(sourceDrafts.spells.find((r:any)=>r.definitionRef.content_id==='spell.fire_bolt'));
  draft.cast.bodyPlaybackSpeed=config.castSpeed;
  if(config.recovery)draft.cast.recovery.enabled=true;
  if(config.number===false)draft.damage.floatingNumber.enabled=false;
  const key=contentRefKey(draft.definitionRef);
  const authored=resolveAuthoredSpellPresentation({
    studioDraftByContentRefKey:new Map([[key,draft]]),
    // This selected resolver only checks exact catalog membership. Preserve the
    // actual P1 owner capture for that check; do not fabricate a catalog row.
    catalogByContentRefKey:new Map(catalogInput.map((row:any)=>[contentRefKey(row.contentRef),row])),
    projectileAssetById:new Map(projectileAssets.map((asset:any)=>[asset.assetId,asset])),
  } as any,{entitiesById:new Map(),entitiesEquipmentById:new Map(),visualLoadoutByEntity:new Map()},
  {contentRef:draft.definitionRef,actorUuid:'caster'});
  const delivery=authored.projectile!;
  const projectile={...delivery,speedPxPerSecond:delivery.speed,sourceAnchorsByFacing:delivery.sourceAnchorsByFacing??{},
    spriteTrack:authored.spriteProjectile,debugAnchor:false};
  const recovery={...authored.recovery,vfx:{}};
  const damage=authored.damage!;
  const damageContext=contexts.vital_effect.damage;
  const death={type:'die',entityUuid:'target',...contexts.vital_effect.death,vfx:{}};
  const onHit=[{type:'takeDamage',targetUuid:'target',bodyClip:damageContext.bodyClip,
    bodyPlaybackSpeed:config.damageSpeed,impactDelayMs:damage.impactDelayMs,resultingHp:config.lethal||config.terminal?0:13,
    frameEvents:{flashEnabled:damage.hitFlash.enabled,flashFrame:damage.hitFlash.frame,
      flashColor:damage.hitFlash.color,flashDurationMs:damage.hitFlash.durationMs,
      numEnabled:damage.floatingNumber.enabled,numFrame:damage.floatingNumber.frame,total:7,
      numColor:damage.floatingNumber.color,numLabel:damage.floatingNumber.label,
      numDurationMs:damage.floatingNumber.durationMs,numStyle:contexts.floating_feedback.number,
      deathEnabled:damage.death!.enabled,deathFrame:damage.death!.frame,
      ...(config.lethal?{deathAtFrame:[death]}:{}),
    }}];
  if(config.repeat)onHit.push({...structuredClone(onHit[0]),impactDelayMs:damage.impactDelayMs+100,resultingHp:6});
  // Named detached fixture at the original CastIntent boundary. No legacy fact
  // mapper is claimed: original resolver/graph own authored values and all
  // original clip/body/projectile implementations below own temporal behavior.
  const intent={type:'cast',delivery:'projectile',actorUuid:'caster',targetUuid:'target',
    clip:authored.actionClip,playbackSpeed:authored.bodyPlaybackSpeed,hiddenSlots:[],releaseFrame:authored.releaseFrame,
    elementColors:authored.elementColors,vfx:Object.fromEntries(Object.entries(authored.actorVfxSlots??{}).filter(([k,v])=>v!==null||k==='weaponOverride')),
    presentation:compileCastPresentationPhaseGraph({projectile,area:null,recovery}),onHit};
  const editor=buildTimelineModel([{intents:[intent]}] as any,
    new Map([['caster',{uuid:'caster',position:[0,0]}],['target',{uuid:'target',position:config.target}]] as any),
    new Map([['caster','NakedBody'],['target','NakedBody']]),new Map(),'hidden',{} as any);
  let done=false;
  const queue=new ClipQueue(ctx,{nowMs:()=>now,setTimeout:()=>null,clearTimeout:()=>{}});
  const queued=config.queue?queue.enqueueTransaction(freeze({rootLineage:config.id,kind:'action',causal:true,
    groups:[{intents:[intent]}]})):null;
  if(queued?.status==='rejected')throw Error('fixture queue rejected');
  const promise=queued?queued.outcome.then((outcome:any)=>{if(outcome.status!=='completed')throw Error(JSON.stringify(outcome));done=true;record('queue-settled');}):
    CastClip.run(intent as any,ctx).then(()=>{done=true;record('cast-settled');});
  await flush();
  const samples:any[]=[];let previous='';
  function sample(){
    const sprites=worldLayer.children.filter(child=>child!==caster&&child!==target).flatMap(child=>{
      if(child instanceof Sprite)return[{...textureMeta.get(child.texture),x:child.x,y:child.y,alpha:child.alpha}];
      return child.children.filter(sprite=>sprite instanceof Sprite).map(sprite=>({
        ...textureMeta.get(sprite.texture),x:child.x,y:child.y,rotation:sprite.rotation}));
    });
    const value={caster:{state:caster.fsm.currentState,clip:caster.appliedClip,frame:Math.floor(caster.currentFrame),
      weapon:caster.getSlot('weapon')?.category??null,glow:caster.getSlot('weaponGlow')?.category??null},
      target:{state:target.fsm.currentState,clip:target.appliedClip,frame:Math.floor(target.currentFrame)},
      hp,done,sprites};
    const eventKey=JSON.stringify({...value,sprites:sprites.map(({x,y,rotation,alpha,...rest}:any)=>rest)});
    if(eventKey!==previous){samples.push({timeMs:now,...value});previous=eventKey;}
  }
  sample();
  for(let iteration=0;now<5000;iteration++){
    const dt=iteration===0?(config.initialStepMs??1):1;
    now+=dt;
    caster.update(dt);target.update(dt);
    const callbacks=frameCallbacks;frameCallbacks=[];for(const callback of callbacks)callback();
    await flush();sample();
    if(done&&frameCallbacks.length===0)break;
  }
  if(!done)throw Error('unsettled fixture '+config.id);
  await promise;
  const output=compactCase(config,editor,events,samples);
  caster.destroy();target.destroy();worldLayer.destroy({children:true});floorLayer.destroy({children:true});vfxLayer.destroy({children:true});
  return output;
}

/** Select observations already emitted by the source, never expected formulas. */
function compactCase(config:any,editor:any,observed:any[],samples:any[]){
  const times=(kind:string)=>observed.filter(e=>e.kind===kind).map(e=>e.timeMs);
  const transitions=observed.filter(e=>e.kind==='body-state');
  const phaseStart=(phase:string)=>samples.find(s=>s.sprites.some((p:any)=>p.phase===phase))?.timeMs??null;
  const phaseEnd=(phase:string)=>{
    const start=phaseStart(phase);
    return start===null?null:samples.find(s=>s.timeMs>start&&!s.sprites.some((p:any)=>p.phase===phase))?.timeMs??null;
  };
  const bodyEnd=transitions.find(e=>e.uuid==='caster'&&e.from==='Casting')?.timeMs??null;
  const anchors=observed.filter(e=>e.kind==='body-anchor');
  const vitals=observed.filter(e=>e.kind==='vitals').map(({kind,uuid,...value})=>value);
  const settled=times(config.queue?'queue-settled':'cast-settled')[0];
  const editorTrack=(id:string)=>{
    const track=editor.tracks.find((track:any)=>track.id===id);
    if(!track)throw Error('Original editor omitted expected track '+id);
    return track;
  };
  const selected=new Set([0,phaseStart('cast'),phaseStart('travel'),phaseStart('impact'),phaseEnd('impact'),bodyEnd,settled,
    ...vitals.map(e=>e.timeMs),...transitions.filter(e=>e.uuid==='target'&&e.to!=='Idle').map(e=>e.timeMs)]);
  const midTravel=samples.find(s=>s.sprites.some((p:any)=>p.phase==='travel'&&p.index===7));
  if(midTravel)selected.add(midTravel.timeMs);
  const priorBodyEnd=samples.findLast(s=>bodyEnd!==null&&s.timeMs<bodyEnd);
  if(priorBodyEnd)selected.add(priorBodyEnd.timeMs);
  return {
    id:config.id,boundary:config.queue?'queue':'direct_clip',
    input:{draftContentId:'spell.fire_bolt',sourceGrid:[0,0],targetGrid:config.target,visualScale:0.5,
      castSpeed:config.castSpeed,damageSpeed:config.damageSpeed,initialHp:config.terminal?0:20,
      resultingHp:config.lethal||config.terminal?0:13,damageAmount:7,lethal:config.lethal??false,terminal:config.terminal??false,
      numberEnabled:config.number!==false,recoveryEnabled:config.recovery??false,
      repeatDamageAfterMs:config.repeat?100:null,repeatResultingHp:config.repeat?6:null},
    pump:{stepMs:1,initialStepMs:config.initialStepMs??1},
    timing:{prepareStartMs:phaseStart('cast'),releaseAnchorMs:anchors.find(e=>e.uuid==='caster'&&e.frame===7)?.timeMs??null,
      travelStartMs:phaseStart('travel'),impactMs:phaseStart('impact'),impactEndMs:phaseEnd('impact'),bodyEndMs:bodyEnd,
      damageStartMs:config.terminal?vitals.map(e=>e.timeMs):transitions.filter(e=>e.uuid==='target'&&(e.to==='TakingHit'||e.to==='Dying')).map(e=>e.timeMs),
      vitals,recoveryStartMs:transitions.find(e=>e.uuid==='caster'&&e.to==='Acting')?.timeMs??null,
      settledMs:settled,numberVisibleMs:times('number-visible'),numberRemovedMs:times('number-removed')},
    bodyTransitions:transitions.map(({kind,...value})=>value),
    frameAnchors:anchors.map(({kind,...value})=>value),
    selectedFrames:samples.filter(s=>selected.has(s.timeMs)).map(s=>({timeMs:s.timeMs,caster:s.caster,target:s.target,hp:s.hp,
      projectiles:s.sprites.filter((p:any)=>p.kind==='projectile').map(({kind,index,x,y,...p}:any)=>({...p,frame:index,root:[x,y]})),
      numberVisible:s.sprites.some((p:any)=>p.kind==='text')})),
    editor:{bodyEndMs:editorTrack('actor-action').endMs,releaseMs:editor.releaseMs,impactMs:editor.impactMs,
      recoveryStartMs:editorTrack('cast-recovery').startMs},
  };
}
async function runMissileCase(){
  now=0;events=[];let frameCallbacks:(()=>void)[]=[];
  const clock=createFrameDrivenPresentationClock({nowMs:()=>now,requestFrame:(callback:()=>void)=>frameCallbacks.push(callback)});
  const worldLayer=new Container(),floorLayer=new Container(),vfxLayer=new Container();
  const input={draftContentId:'spell.magic_missile',sourceGrid:[0,0],visualScale:0.5,
    targets:[{uuid:'A',grid:[3,-3],initialHp:80},{uuid:'B',grid:[4,-2],initialHp:80}],
    applications:[{applicationId:'missile-0',targetUuid:'A',damage:5,resultingHp:75},
      {applicationId:'missile-1',targetUuid:'B',damage:5,resultingHp:75},
      {applicationId:'missile-2',targetUuid:'A',damage:2,resultingHp:73}]};
  const entities=new Map<string,any>();
  for(const row of [{uuid:'caster',grid:input.sourceGrid},...input.targets]){
    entities.set(row.uuid,new AnimatedEntity({uuid:row.uuid,gx:row.grid[0],gy:row.grid[1],appearance,
      visualScale:input.visualScale,visualScaleX:input.visualScale,facing:row.uuid==='caster'?'E':'W',
      initialState:'Idle',preloadAllClips:false,worldLayer,floorLayer,presentationAssets:assets}));
  }
  await Promise.all([...entities.values()].map(entity=>entity.waitForPresentationReady()));
  const hp:Record<string,number>=Object.fromEntries(input.targets.map(row=>[row.uuid,row.initialHp]));
  const graphics=new Map<any,number>();let launchCount=0;
  // Observe real Pixi object lifetime. No ProjectileFx function or clock is replaced.
  for(const layer of [worldLayer,floorLayer,vfxLayer])layer.on('childAdded',(child:any)=>{
    if(!(child instanceof Graphics))return;
    const index=launchCount++;
    graphics.set(child,index);record('projectile-launch',{applicationIndex:index});
    child.on('destroyed',()=>{record('projectile-arrival',{applicationIndex:index});graphics.delete(child);});
  });
  const applicationByIntent=new Map<any,number>();
  const ctx:any={worldLayer,floorLayer,vfxLayer,presentationAssets:assets,animationClock:clock,
    getEntity:(uuid:string)=>entities.get(uuid),isCancelled:()=>false,
    patchEntityVitals:(uuid:string,patch:any)=>{hp[uuid]=patch.hp??hp[uuid];record('vitals',{uuid,...patch});},
    onIntentLifecycle:(intent:any,phase:string)=>record('intent-'+phase,{type:intent.type,
      targetUuid:intent.targetUuid,applicationIndex:applicationByIntent.get(intent)??null,
      ...(intent.type==='floatingNumber'?{value:intent.value,label:intent.label}:{} )}),
  };
  const draft=sourceDrafts.spells.find((row:any)=>row.definitionRef.content_id===input.draftContentId);
  const authored=resolveAuthoredSpellPresentation({
    studioDraftByContentRefKey:new Map([[contentRefKey(draft.definitionRef),draft]]),
    catalogByContentRefKey:new Map(catalogInput.map((row:any)=>[contentRefKey(row.contentRef),row])),
    projectileAssetById:new Map(projectileAssets.map((asset:any)=>[asset.assetId,asset])),
  } as any,{entitiesById:new Map(),entitiesEquipmentById:new Map(),visualLoadoutByEntity:new Map()},
  {contentRef:draft.definitionRef,actorUuid:'caster'});
  if(authored.damage!==undefined&&authored.damage!==null)throw Error('missile fixture requires the unchanged absent damage override');
  const damage=contexts.vital_effect.damage,palette=damage.palette.byDamageType.Force;
  const missiles=input.applications.map((application,index)=>{
    const hit={type:'takeDamage',targetUuid:application.targetUuid,bodyClip:damage.bodyClip,
      bodyPlaybackSpeed:damage.bodyPlaybackSpeed,impactDelayMs:damage.impactDelayMs,resultingHp:application.resultingHp,
      frameEvents:{flashEnabled:damage.flashEnabled,flashFrame:damage.flashFrame,
        flashColor:damage.flashColorMode==='damage_type'?palette.impactColor:damage.flashColor,
        flashDurationMs:damage.flashDurationMs,numEnabled:damage.numberEnabled,numFrame:damage.numberFrame,
        total:application.damage,numColor:palette.impactColor,numLabel:'Force',
        numDurationMs:damage.numberDurationMs,numStyle:contexts.floating_feedback.number,
        conditionFrame:damage.conditionFrame,deathEnabled:false,deathFrame:damage.deathFrame}};
    applicationByIntent.set(hit,index);
    return {targetUuid:application.targetUuid,onHit:[hit]};
  });
  const delivery=authored.projectile!;
  const projectile={...delivery,speedPxPerSecond:delivery.speed,sourceAnchorsByFacing:delivery.sourceAnchorsByFacing??{},
    spriteTrack:authored.spriteProjectile,debugAnchor:false};
  const intent={type:'cast',delivery:'missile_volley',actorUuid:'caster',missiles,
    clip:authored.actionClip,playbackSpeed:authored.bodyPlaybackSpeed,hiddenSlots:[],releaseFrame:authored.releaseFrame,
    elementColors:authored.elementColors,
    vfx:Object.fromEntries(Object.entries(authored.actorVfxSlots??{}).filter(([key,value])=>value!==null||key==='weaponOverride')),
    presentation:compileCastPresentationPhaseGraph({projectile,area:null,recovery:{...authored.recovery,vfx:{}}})};
  const queue=new ClipQueue(ctx,{nowMs:()=>now,setTimeout:()=>null,clearTimeout:()=>{}});
  const queued=queue.enqueueTransaction(freeze({rootLineage:'magic-missile-aba',kind:'action',causal:true,groups:[{intents:[intent]}]}));
  if(queued.status==='rejected')throw Error('missile fixture queue rejected');
  let done=false;
  const promise=queued.outcome.then((outcome:any)=>{
    if(outcome.status!=='completed')throw Error(JSON.stringify(outcome));
    done=true;record('queue-settled');
  });
  await flush();
  const samples:any[]=[];let previous='';
  function sample(){
    const value={bodies:[...entities].map(([uuid,entity])=>({uuid,state:entity.fsm.currentState,
      clip:entity.appliedClip,frame:Math.floor(entity.currentFrame)})),hp:{...hp},done,
      projectiles:[...graphics.values()],numbers:worldLayer.children.filter(child=>child instanceof Sprite)
        .map((child:any)=>textureMeta.get(child.texture)).filter(meta=>meta?.kind==='text').map(meta=>meta.value)};
    const key=JSON.stringify(value);
    if(key!==previous){samples.push({timeMs:now,...value});previous=key;}
  }
  sample();
  while(now<5000){
    now+=1;for(const entity of entities.values())entity.update(1);
    const callbacks=frameCallbacks;frameCallbacks=[];for(const callback of callbacks)callback();
    await flush();sample();
    if(done&&frameCallbacks.length===0)break;
  }
  if(!done||launchCount!==3)throw Error('incomplete actual three-missile volley');
  await promise;
  const observed=events.map(({kind,...event})=>({kind,...event}));
  for(const entity of entities.values())entity.destroy();
  worldLayer.destroy({children:true});floorLayer.destroy({children:true});vfxLayer.destroy({children:true});
  return {id:'queue-magic-missile-aba',input,pump:{stepMs:1},events:observed,frames:samples};
}

const cases=[];
for(const config of values['magic-missile']?[]:[
  {id:'saved-speed1',castSpeed:1,damageSpeed:1,target:[3,-3]},
  {id:'cast-speed2',castSpeed:2,damageSpeed:1,target:[3,-3]},
  {id:'damage-speed2',castSpeed:1,damageSpeed:2,target:[3,-3]},
  {id:'lethal',castSpeed:1,damageSpeed:1,target:[3,-3],lethal:true},
  {id:'terminal',castSpeed:1,damageSpeed:1,target:[3,-3],terminal:true},
  {id:'number-disabled',castSpeed:1,damageSpeed:1,target:[3,-3],number:false},
  {id:'recovery-enabled',castSpeed:1,damageSpeed:1,target:[3,-3],recovery:true},
  {id:'queue-saved-speed1',castSpeed:1,damageSpeed:1,target:[3,-3],queue:true},
  {id:'queue-cast-speed2',castSpeed:2,damageSpeed:1,target:[3,-3],queue:true},
  {id:'queue-damage-speed2',castSpeed:1,damageSpeed:2,target:[3,-3],queue:true},
  {id:'queue-lethal',castSpeed:1,damageSpeed:1,target:[3,-3],queue:true,lethal:true},
  {id:'queue-recovery-enabled',castSpeed:1,damageSpeed:1,target:[3,-3],queue:true,recovery:true},
  {id:'queue-near',castSpeed:1,damageSpeed:1,target:[1,-1],queue:true},
  {id:'queue-repeat-hit',castSpeed:1,damageSpeed:1,target:[3,-3],queue:true,repeat:true},
  {id:'queue-large-initial-delta',castSpeed:1,damageSpeed:1,target:[3,-3],queue:true,initialStepMs:1500},
])cases.push(await runCase(config));
if(values['magic-missile'])cases.push(await runMissileCase());
const owners=['render/AnimatedEntity.ts','render/AnimationFSM.ts','render/clips/CastClip.ts','render/clips/TakeDamageClip.ts',
 'render/clips/DeathClip.ts','render/clips/HitFlashFx.ts','render/clips/FloatingText.ts','render/spellAuthoring/runtimeResolver.ts',
 'render/spellAuthoring/phaseGraph.ts','render/spellAuthoring/SpriteProjectileFx.ts','ui/spellStudio/timelineBuild.ts',
 'render/clipQueue.ts','render/dispatcher.ts','render/presentationRuntimeHost.ts',
 'render/clips/ProjectileFx.ts','render/clips/MovementRecovery.ts','render/controllers/ActionVfxController.ts',
 'render/projectileEndpoints.ts','render/visualAnchors.ts','render/types.ts','render/SpriteAssetRegistry.ts'];
if(values['magic-missile'])owners.push('render/data/animation/actionContextPresentation.json');
const result={schema:values['magic-missile']?'dnd.neuroclient-magic-missile-timing-oracle':'dnd.neuroclient-animation-timing-oracle',version:1,
  source:{revision:sourceRevision,owners:Object.fromEntries(owners.map(path=>['src/'+path,
    createHash('sha256').update(readFileSync(app+'/src/'+path)).digest('hex')]))},
  dataInputs:Object.fromEntries(['rig-tables.json','spell-studio-drafts.materialized.json','catalog-input.json'].map(path=>[
    path,createHash('sha256').update(readFileSync(dataRoot+'/'+path)).digest('hex')])),
  pumpOwner:'createFrameDrivenPresentationClock',pumpOrdering:'actor updates, queued frame callbacks, drain microtasks',
  substitutions:['Diagnostic sinks replace SDK/ledger imports.','PNG-checked frame metadata supplies inert Pixi textures; no GPU rasterization.',
    'Font rasterization supplies a Pixi sprite with the original label.','No WebGL context.','Frame callbacks are delivered by the controlled pump.',
    'Queue watchdog timeout is inert.'],
  limitations:['Detached original CastIntent fixture; no event mapper/SDK proof.','Real Pixi objects with inert texture resources and no font/GPU rasterizer.',
    'Original frame-driven clock has a deterministic supplied pump; 1ms quantization is retained except the named initial-hitch case.',
    'Queue watchdog timer is inert; no deadline/reset/network proof.','No source formula is reimplemented to generate expected runtime times.',
    'Repeated-hit flush and initial-hitch cases record source behavior; they do not define the accepted Python correction.',
    'Enabled recovery is source evidence; it does not assert Taunt media is imported into the game.'],cases};
if(values['magic-missile'])result.limitations=[
  'Detached original CastIntent fixture; no event mapper/SDK proof.',
  'Real Pixi objects with inert texture resources and no font/GPU rasterizer.',
  'Original frame-driven clock has a deterministic 1ms pump; frame-zero damage callbacks run on the next actor update.',
  'Queue watchdog timer is inert; no deadline/reset/network proof.',
  'No source formula is reimplemented to generate expected runtime times.',
  'TakeDamage inputs use the original global damage context and Force palette because the spell has no authored damage override.',
  'Application indices label actual launch Graphics and original onHit intent objects; source missile entries have no application ID.',
  'Graphics lifetime is observed; geometry coordinates and frame-count-dependent trail rasterization are outside this timing fixture.',
];
if(execFileSync('git',['status','--porcelain'],{cwd:app,encoding:'utf8'}).trim())throw Error('source checkout changed during probe');
if(execFileSync('git',['rev-parse','HEAD'],{cwd:app,encoding:'utf8'}).trim()!==sourceRevision)throw Error('source revision changed during probe');
writeFileSync(outputPath,JSON.stringify(result,null,2)+'\n');
console.log(`Recorded ${cases.length} source cases to ${outputPath}`);
