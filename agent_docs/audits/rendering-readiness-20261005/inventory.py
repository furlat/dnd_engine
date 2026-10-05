"""Read-only audit of effective presentation metadata. Does not certify visuals."""
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import ast
from collections import Counter, defaultdict
from dataclasses import fields, is_dataclass
from collections.abc import Mapping
from enum import Enum
from pydantic import BaseModel
import hashlib
import json
from pathlib import Path
import subprocess
from pydantic import TypeAdapter
from game.animation_data import load_animation_data
from game.assets import load_catalog
from game.environment_art import load_environment_art
from game.presentation_coverage import presentation_inventory
from game.player_facts import PlayerFact
from dnd.content_system.spell_catalog_composition import SPELL_CATALOG_COMPOSITION_ROWS

def plain(v):
    if isinstance(v,BaseModel):return {name:plain(object.__getattribute__(v,name)) for name in type(v).model_fields}
    if isinstance(v,Enum):return v.value
    if isinstance(v,Path):return str(v)
    if isinstance(v,Mapping):return {str(k):plain(w) for k,w in v.items()}
    if isinstance(v,(tuple,list,set,frozenset)):return [plain(w) for w in v]
    if is_dataclass(v):return {f.name:plain(object.__getattribute__(v,f.name)) for f in fields(v)}
    return v
out=Path(__file__).parent
rigs=tuple(sorted(Path('game/data/rigs').glob('*.json')))
world=load_catalog()
data=load_animation_data(rig_files=rigs,world_source=world.world_source)
rows=presentation_inventory(data,spell_ids=(r.declaration.ref.content_id for r in SPELL_CATALOG_COMPOSITION_ROWS),environment=load_environment_art())
(out/'existing-coverage.json').write_text(json.dumps(rows,indent=2)+'\n')
selected={}
for field in fields(data):
    selected[field.name]=plain(object.__getattribute__(data,field.name))
(out/'effective-catalog.json').write_text(json.dumps(selected,indent=2)+'\n')
features=defaultdict(list)
def walk(value,path=''):
    if isinstance(value,dict):
        for k,v in value.items():
            p=f'{path}.{k}' if path else k
            if k in ('renderer','composition','mapping','attachment','type','depthMode','source','mode') and isinstance(v,(str,bool)):
                yield p,str(v)
            yield from walk(v,p)
    elif isinstance(value,list):
        for v in value:yield from walk(v,path+'[]')
for family in ('drafts','attack_recipes','body_action_recipes','condition_recipes','spatial_media','construction_media','deposit_media','item_attachments'):
    for identity,value in selected[family].items():
        for path,v in sorted(set(walk(value))):features[f'{family}:{path}={v}'].append(identity)
(out/'feature-owners.json').write_text(json.dumps(dict(sorted(features.items())),indent=2)+'\n')
spells=[]
for identity,d in selected['drafts'].items():
    p=d['projectile'];a=d['area']
    spells.append({'identity':identity,'owner':d['definitionRef'],'motion':d['cast']['actionClip'],
      'delivery':('projectile' if p else 'directed' if d['directed'] else 'arcs' if d['arcs'] else 'none'),
      'area':a is not None,'media_tracks':len(d['media']),'body_material_tracks':len(d['bodyMaterials']),
      'child_attack':d['childAttack'] is not None,'contact':d['contact'] is not None,
      'cancellation':d['cancellationMedia'] is not None,
      'trajectory':p['trajectory']['type'] if p else None,
      'source_sockets':bool(d['cast'].get('sourceSockets')),
      'visual_status':'not_revalidated','schema_status':'requires_source_and_case_review'})
(out/'spell-matrix.json').write_text(json.dumps(spells,indent=2)+'\n')
branches=[]
for file in sorted(Path('game').glob('*.py')):
    source=file.read_text();tree=ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node,ast.If):
            expr=ast.get_source_segment(source,node.test) or ''
            if any(key in expr for key in ('.composition','.mapping','.renderer','.attachment','.kind','.phase','.trajectory','.movement_mode','.life_state','isinstance(')):
                branches.append({'file':str(file),'line':node.lineno,'condition':expr})
(out/'dispatch-branches.json').write_text(json.dumps(branches,indent=2)+'\n')
files=sorted(set(Path('game').glob('*.py'))|set(Path('game/data').rglob('*.json')))
provenance={'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'rig_files':[str(p) for p in rigs], 'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
summary={'scope':'Effective metadata and source dispatch inventory; no pixel or runtime case validation.',
 'counts':{name:len(value) for name,value in selected.items() if name in ('drafts','attack_recipes','body_action_recipes','condition_recipes','rigs','creature_rigs','spatial_media','construction_media')},
 'coverage_statuses':dict(Counter(r['status'] for r in rows)),
 'coverage_families':dict(Counter(r['family'] for r in rows)),
 'nonselected_rows':[r for r in rows if r['status'] in ('missing_binding','partial','unassessed')],
 'spell_delivery':dict(Counter(r['delivery'] for r in spells)),
 'spell_motions':dict(Counter(r['motion'] for r in spells)),
 'source_branches':len(branches),'feature_values':len(features)}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
