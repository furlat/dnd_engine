"""Link historical evidence to current selected identities, without treating it as acceptance."""
import csv,json
from collections import defaultdict,Counter
from pathlib import Path
out=Path(__file__).parent
roots=[Path('.runtime/spell-casting-20261004/persistent/acceptance/runs/20261004-all-spell-casts'),Path('.runtime/spell-repair-20261005/persistent/runs/20261005-issue-review')]
byidentity=defaultdict(list)
case_rows=[]
for root in roots:
 d=json.loads((root/'manifest.json').read_text())
 for c in d['cases']:
  identities=sorted({(r.get('family'),r.get('identity')) for r in c.get('coverage',[]) if r.get('identity')})
  rec={'case':c['id'],'manifest':str(root/'manifest.json'),'source_commit':d['run'].get('commit'),'video':str(root/c['video']),'input':str(root/c['input']) if c.get('input') else None,'poster':str(root/c['poster']) if c.get('poster') else None,'recorded_status':c.get('status'),'identities':identities,'current_visual_review':'pending'}
  case_rows.append(rec)
  for family,identity in identities:byidentity[(family,identity)].append({'case':c['id'],'manifest':str(root/'manifest.json'),'video':rec['video']})
spells=json.loads((out/'spell-matrix.json').read_text())
for row in spells:
 row['historical_evidence']=byidentity[('spell',row['identity'])]
 row['requirements']=['fact_identity','source_and_recipient_disclosure','rig_gesture_and_layers','palette','cancel_or_partial_evidence','shared_narrative_meaning']
 if row['delivery']!='none':row['requirements']+=['release_contact_registration',row['delivery']+'_sampler']
 if row['area']:row['requirements']+=['admitted_area_geometry','area_envelope_and_depth']
 if row['media_tracks']:row['requirements']+=['media_attachment_and_outcome_selection']
 if row['body_material_tracks']:row['requirements']+=['finite_body_material_composition']
 if row['child_attack']:row['requirements']+=['child_attack_native_outcome_ownership']
(out/'spell-matrix.json').write_text(json.dumps(spells,indent=2)+'\n')
(out/'historical-case-links.json').write_text(json.dumps(case_rows,indent=2)+'\n')
with (out/'spell-matrix.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['identity','motion','delivery','area','media_tracks','body_materials','child_attack','historical_cases','required_contract_checks','current_visual_review'])
 for r in spells:w.writerow([r['identity'],r['motion'],r['delivery'],r['area'],r['media_tracks'],r['body_material_tracks'],r['child_attack'],len(r['historical_evidence']),'; '.join(r['requirements']),'pending'])
print(json.dumps({'historical_cases':len(case_rows),'selected_drafts':len(spells),'with_historical_case_identity_links':sum(bool(r['historical_evidence']) for r in spells),'without_links':[r['identity'] for r in spells if not r['historical_evidence']],'warning':'historical source identity links only; no current pixel or schema sufficiency proof'},indent=2))
