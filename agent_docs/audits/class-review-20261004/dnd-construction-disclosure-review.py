from dataclasses import replace
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.events import SensoryUpdateEvent
from dnd.blocks.base_item import ItemLocationStateEvent
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence,encode_player_sequence,reduce_lineage
from tests.game.construction_scenarios import construction_history

SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
sequence=construction_history(material='force',break_section=False,antimagic=True).views['caster']
providers={s.provider_uuid for line in sequence.lineages for e in line.events if isinstance(e,ItemLocationStateEvent) for s in e.item_state.construction_suppressions}
assert providers
raw_sections={e.item_state.item_uuid for line in sequence.lineages for e in line.events if isinstance(e,ItemLocationStateEvent) and e.item_state.construction_suppressions}
assert len(raw_sections)==3

def hide(event):
    if not isinstance(event,SensoryUpdateEvent):return event
    return event.model_copy(update={'spatial_effects_changed':{k:v.model_copy(update={'suppressions':tuple(s for s in v.suppressions if s.provider_uuid not in providers)}) for k,v in event.spatial_effects_changed.items() if k not in providers},'spatial_effects_removed':event.spatial_effects_removed-providers})
initial=replace(sequence.initialization,admitted=tuple((i,hide(e)) for i,e in sequence.initialization.admitted))
lines=tuple(replace(line,root=hide(line.root),events=tuple(map(hide,line.events)),observed_sources=tuple(map(hide,line.observed_sources))) for line in sequence.lineages)
redacted=sequence.model_copy(update={'initialization':initial,'lineages':lines})
# Exact native item after-values still carry suppression. The projected provider
# permission is deliberately absent, exercising that public disclosure boundary.
state,roots=decode_player_sequence(encode_player_sequence(project_sequence(redacted)))
seen=set()
for line in roots:
    state=reduce_lineage(state,line)
    for key,obj in state.objects.items():
        if key in raw_sections:
            seen.add(key);assert not obj.item.construction_suppressions
assert seen==raw_sections
print('3 real retained Force sections; raw native provider geometry withheld when no provider observation was received; passive codec roundtrip passed')
