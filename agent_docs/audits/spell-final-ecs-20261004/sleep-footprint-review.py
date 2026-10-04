from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.events import EventPhase,EventType
from game.player_facts import ConditionChangeFact,SpellFact
from game.player_reduction import reduce_lineage
from tests.game.device_scenarios import device_history
from tests.game.test_sleep_area_projection import saved_player
SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
for program in ('normal-sleep','sleep-area'):
 history=device_history(program=program);before,roots=saved_player(history.views['target'])
 for root in roots:
  if isinstance(root.root.fact,SpellFact) and root.root.fact.behavior_id=='spell.sleep':
   native=next(r for r in history.views['target'].lineages if r.root.lineage_uuid==root.root.lineage_uuid)
   assert before.senses is not None
   native_cells=set(native.root.resolved_area_positions);visible=set(before.senses.visible);public=set(root.root.fact.resolved_area_positions)
   assert public==native_cells&visible
   effect=next(r.source_index for r in native.objective_rows if r.lineage_uuid==native.root.lineage_uuid and r.phase==EventPhase.EFFECT.value)
   applications=[e for e in native.events if e.event_type is EventType.CONDITION_APPLICATION]
   assert effect<min(r.source_index for r in native.objective_rows if any(e.lineage_uuid==r.lineage_uuid for e in applications))
   denied={e.lineage_uuid for e in applications if e.target_entity_uuid!=before.observer_uuid and str(before.observer_uuid) not in e.identified_entity_observer_uuids.get(str(e.target_entity_uuid),set())}
   assert not any(isinstance(n.fact,ConditionChangeFact) and n.lineage_uuid in denied for n in root.events)
   print(program,'native cells',len(native_cells),'entry visible',len(public),'genuinely unseen omitted',len(native_cells-visible),'later denied condition lineages',len(denied),'footprint effect index',effect)
   break
  before=reduce_lineage(before,root)
