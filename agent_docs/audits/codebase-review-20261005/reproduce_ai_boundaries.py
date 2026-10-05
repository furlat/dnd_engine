"""Run with PYTHONPATH=. uv run --no-sync python <this-file>."""
from uuid import uuid4
from dnd.ai.contracts.observation import ObservationEntityFact, KnowledgeState, SubjectiveWorldState
from dnd.ai.runtime.knowledge_reduction import AIKnowledge
from dnd.ai.contracts.control import AffordanceSet

identity = uuid4()
knowledge = AIKnowledge((identity,))
knowledge.known_entities[str(identity)] = ObservationEntityFact(
    uuid=str(identity), name='actor', knowledge_state=KnowledgeState.VISIBLE, hp=10,
)
# Same shallow publication operation as state_projection.py:111-117.
world = SubjectiveWorldState.model_construct(known_entities=dict(knowledge.known_entities))
world.known_entities[str(identity)].hp = 999
world.known_entities[str(identity)].conditions.append('fake')
print('retained knowledge after public mutation:',
      knowledge.known_entities[str(identity)].hp,
      knowledge.known_entities[str(identity)].conditions)

payload = {
    'actor_uuid': 'actor', 'computed_at_observation_cursor': 0,
    'target_catalog': [{'index': 0, 'target_name': 'first'}, {'index': 1, 'target_name': 'last'}],
    'action_sources': [{
        'source_action_id': 's', 'bucket': 'entity_actions', 'template_name': 'x',
        'display_name': 'x', 'action_category': 'x', 'target_type': 'x',
        'can_afford': True, 'target_option_indices': [-1],
    }],
    'entity_actions': [{'row_id': 'r', 'source_action_id': 's'}],
}
affordances = AffordanceSet.model_validate(payload)
print('negative target option resolved to:', affordances.entity_actions[0].target_options[0].target_name)
