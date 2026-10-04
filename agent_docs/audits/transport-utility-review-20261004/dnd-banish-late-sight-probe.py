import pygame
from uuid import uuid4
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.conditions import Blinded,Deafened
from dnd.actions_functional import register_spell
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import Banishment
from game.presentation import capture_interval,reduce_interval
from game.replay import capture_history,ObserverCapture
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.condition_media_lifetime import register_condition_lifetimes
from game.player_reduction import reduce_lineage
from tests.game.player_helpers import player_history
from tests.manual.spell_regression_support import create_spell_regression_actor,force_save_result
SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
reset_engine_runtime();build_battlefield('battlefield.open_floor_bright');game=Game()
caster=create_spell_regression_actor('Caster',(3,5),'heroes',spell_slots={4:1})
target=create_spell_regression_actor('Recipient',(7,5),'enemies')
register_spell(caster,Banishment);force_save_result(target,'charisma',succeeds=False)
Entity.update_all_entities_senses()
encounter=Encounter(name='Hidden return',source_entity_uuid=caster.uuid)
for actor in (caster,target):encounter.add_combatant(actor,HumanController(source_entity_uuid=actor.uuid))
encounter.start_encounter();encounter.start_turn()
while encounter.get_current_entity() is not caster:encounter.next_turn()
cursor=EventQueue.event_cursor()
initial=capture_interval(name='Banish hidden return',start_cursor=0,end_cursor=cursor,observer_uuid=caster.uuid,battlefield_id='battlefield.open_floor_bright')
before,_=reduce_interval(None,initial)
template=caster.get_action_template('Banishment');assert template
with fixed_dice_faces(*([3]*50)):result=template.instantiate(target_entity_uuid=target.uuid).apply()
assert result and not result.canceled
caster.add_condition(Blinded(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
caster.add_condition(Deafened(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid))
assert not caster.senses.entities.get(target.uuid)
caster.remove_condition('Concentrating')
assert target.is_deployed
print('hidden at native return',caster.senses.entities.get(target.uuid))
caster.remove_condition('Blinded');caster.remove_condition('Deafened')
history=capture_history(before,(),observers=(ObserverCapture('caster',caster.uuid,cursor),))
game.close();reset_engine_runtime();pygame.init();pygame.display.set_mode((1,1));data=load_animation_data()
state,roots=player_history(history,role='caster');records={};clock=1000.
for root in roots:
 group=bind_choreography(state,root,data)
 old={k:v.returned_ms for k,v in records.items()}
 records=register_condition_lifetimes(records,state,data,absolute_start_ms=clock,lineage=root,choreography=group)
 after=reduce_lineage(state,root)
 if any(v.returned_ms is not None and old.get(k) is None for k,v in records.items()):
  print('RETURN CUE on',type(root.root.fact).__name__,str(root.root.fact)[:350])
 print(type(root.root.fact).__name__,len(group.portals),[(str(k),v.returned_ms) for k,v in records.items() if v.behavior_id=='condition.spell.banishment'])
 state=after;clock+=group.complete_ms+500
pygame.quit()
