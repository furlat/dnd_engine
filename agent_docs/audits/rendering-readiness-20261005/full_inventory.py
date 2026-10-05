"""Study-only full metadata/source denominator; no execution/visual proof implied."""
import ast
import csv
import json
from collections import Counter
from pathlib import Path

out=Path(__file__).parent

def write(name,value):
    (out/name).write_text(json.dumps(value,indent=2)+'\n')

catalog=json.loads((out/'effective-catalog.json').read_text())
coverage=json.loads((out/'existing-coverage.json').read_text())
evidence=json.loads((out/'historical-case-links.json').read_text())
linked={}
for case in evidence:
    for family,identity in case['identities']:
        linked.setdefault((family,identity),[]).append(case['case'])
rows=[]
for r in coverage:
    rows.append({**r,'historical_case_ids':linked.get((r['family'],r['identity']),[]),
        'source_binding_status':r['status'],'timing_compared':False,'disclosure_asserted':False,
        'visual_reviewed':False,'schema_mapping':'family design required; metadata selection is not acceptance'})
write('all-content-coverage.json',rows)
with (out/'all-content-coverage.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['family','identity','owner','selected_binding','declared_status','historical_cases','timing_compared','disclosure_asserted','visual_reviewed'])
    for r in rows:w.writerow([r['family'],r['identity'],r['owner'],r['binding'],r['status'],len(r['historical_case_ids']),False,False,False])
# Enumerate every AnimationData field, including those omitted by the initial inventory.
tree=ast.parse(Path('game/animation_types.py').read_text())
record=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AnimationData')
fields=[]
for n in record.body:
    if isinstance(n,ast.AnnAssign):
        name=n.target.id
        fields.append({'field':name,'type':ast.unparse(n.annotation),'line':n.lineno,
            'metadata_materialized_in_initial_inventory':name in catalog,
            'role':'authored/runtime catalog field; source references enumerated',
            'references':[]})
modules=[]
for p in sorted(Path('game').glob('*.py')):
    source=p.read_text();t=ast.parse(source)
    imports=[]
    for n in ast.walk(t):
        if isinstance(n,ast.ImportFrom) and n.module:imports.append(n.module)
        elif isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
    for row in fields:
        refs=[n.lineno for n in ast.walk(t) if isinstance(n,ast.Attribute) and n.attr==row['field']]
        if refs:row['references'].append({'file':str(p),'lines':sorted(set(refs))})
    modules.append({'file':str(p),'description':ast.get_docstring(t),'imports':sorted(set(imports)),
        'functions':[{'name':n.name,'line':n.lineno} for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))],
        'records':[{'name':n.name,'line':n.lineno,'fields':[{'name':a.target.id,'type':ast.unparse(a.annotation)} for a in n.body if isinstance(a,ast.AnnAssign) and isinstance(a.target,ast.Name)]} for n in t.body if isinstance(n,ast.ClassDef)],
        'status':'source index; detailed family disposition in full pipeline coverage report'})
write('catalog-field-coverage.json',fields)
write('module-source-index.json',modules)
public=[]
for filename in ('game/player_facts.py','game/world_animation.py','game/choreography.py','game/playback_frame.py','dnd/types/event_facts.py','dnd/types/senses.py'):
    t=ast.parse(Path(filename).read_text())
    for n in t.body:
        if isinstance(n,ast.ClassDef):
            public.append({'file':filename,'record':n.name,'line':n.lineno,
                'fields':[{'name':a.target.id,'type':ast.unparse(a.annotation)} for a in n.body if isinstance(a,ast.AnnAssign) and isinstance(a.target,ast.Name)]})
write('record-field-index.json',public)
cases=json.loads(Path('devtools/animation_review/catalog.json').read_text())
write('declared-case-index.json',[{'id':c['id'],'title':c.get('title'),'tags':c.get('tags',[]),'scenario':c.get('scenario'),'status':'declared; not executed for this study'} for c in cases])
summary={'content_rows':len(rows),'families':dict(Counter(r['family'] for r in rows)),
 'animation_data_fields':len(fields),'initial_inventory_omitted_fields':[r['field'] for r in fields if not r['metadata_materialized_in_initial_inventory']],
 'game_modules':len(modules),'declared_cases':len(cases),'public_and_bound_records':len(public),
 'qualification':'Full enumerated metadata/source denominator; not exhaustive runtime or visual validation.'}
write('full-summary.json',summary)
print(json.dumps(summary,indent=2))
