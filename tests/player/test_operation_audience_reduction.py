"""Atomic received operations preserve the same event-time view as saved lineages."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.core.events import EventPhase
from dnd.player.audience import PlayerAudience
from dnd.player.capture import capture_interval
from dnd.core.events import EventQueue
from dnd.player.facts import (
    PlayerLineage, PlayerNode, PlayerObservation, PlayerUpdate, SensoryFact,
    SpatialFact, VersionRow,
)
from dnd.player.projection import begin_projection
from dnd.player.reduction import reduce_initialization, reduce_lineage, reduce_operation
from dnd.types.event_facts import SpatialChangeType
from dnd.types.senses import PerceivedContact
from tests.player.test_recorded_boundary import world


@pytest.mark.parametrize('together', [False, True])
@pytest.mark.parametrize('steps', [
    ('observation', 'entry'),
    ('observation', 'canceled', 'entry'),
    ('sensory', 'entry', 'observation'),
    ('entry', 'observation', 'sensory'),
    ('sensory', 'observation', 'sensory', 'departure'),
    ('sensory', 'departure', 'sensory'),
])
def test_operation_view_matches_ordered_lineage_replay_without_mutating_history(world, together, steps):
    # Recorded-value boundary: supply event-order permutations to the public
    # reducer, using native actor/sensory initialization. This does not invent
    # a gameplay action that emits each permutation.
    _, built, (owner, witness) = world
    for actor in (owner, witness):
        actor.update_entity_senses(max_distance=8)
    audience = PlayerAudience((owner.uuid, witness.uuid), (owner.uuid, witness.uuid))
    envelope = capture_interval(name='operation audience fold', start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=owner.uuid, audience=audience,
        battlefield_id=built.definition.battlefield_id)
    _, initial = begin_projection(envelope)
    before = reduce_initialization(initial)
    frozen = deepcopy(before)
    template = next(node.fact for node in initial.nodes
        if isinstance(node.fact, SensoryFact) and node.fact.observer_uuid == owner.uuid)
    sensory = replace(template, initial=False, observer_position_changed=False,
        effective_light_levels_changed={}, cause_event_uuid=None,
        visible_cells_added=(), visible_cells_removed=(), seen_cells_added=(),
        entity_contacts_changed={}, entity_contacts_removed=frozenset(),
        object_contacts_changed={}, object_contacts_removed=frozenset(),
        sense_modes_changed=False, sense_modes=None, passive_perception_changed=False,
        passive_perception=None, visual_access_changed=False, visual_access=None,
        hazardous_cells_changed={}, spatial_effect_sightings={}, spatial_effect_content={},
            spatial_effects_removed=frozenset())
    lineages = []
    for index, step in enumerate(steps, start=before.reducer_cursor):
        identity, lineage_id = uuid4(), uuid4()
        fact = None
        observations = ()
        if step in ('sensory', 'canceled'):
            fact = sensory
        elif step == 'entry':
            fact = SpatialFact(change_type=SpatialChangeType.ENTITY_ENTERED,
                entity_uuid=owner.uuid, position=(7, 5), commit_event_uuid=identity)
        elif step == 'departure':
            fact = SpatialFact(change_type=SpatialChangeType.ENTITY_LEFT,
                entity_uuid=witness.uuid, position=(6, 5), commit_event_uuid=identity,
                terminal_departure=True)
        else:
            # A re-observation of an unchanged body: an empty patch with its contact.
            observations = (PlayerObservation(event_uuid=identity, actor_uuid=witness.uuid, changes={},
                contact=PerceivedContact(position=(8, 5), visual=True)),)
        node = PlayerNode(uuid=identity, lineage_uuid=lineage_id, parent_event=None,
            parent_lineage=None, children_lineages=(), phase=EventPhase.COMPLETION,
            canceled=step == 'canceled', fact=fact)
        lineages.append(PlayerLineage(generation=before.generation, observer_uuid=owner.uuid,
            audience=audience, lineage_uuid=lineage_id, root=0, events=(node,),
            version_rows=(VersionRow(source_index=index, event_uuid=identity, lineage_uuid=lineage_id),),
            start_cursor=index, end_cursor=index + 1, observations=observations))
    if together:
        lineages = [replace(lineages[0], events=tuple(node for row in lineages for node in row.events),
            version_rows=tuple(version for row in lineages for version in row.version_rows),
            observations=tuple(value for row in lineages for value in row.observations),
            end_cursor=lineages[-1].end_cursor)]
    update = PlayerUpdate(audience=audience, lineages=tuple(lineages), hud=None,
        combat_log_appends=(), content_additions=())
    received = PlayerUpdate.model_validate_json(update.model_dump_json())
    expected = before
    for lineage in received.lineages:
        expected = reduce_lineage(expected, lineage)
    actual = reduce_operation(before, received)
    assert actual == expected
    assert before == frozen
    assert actual.senses is not None
    if steps[-1] == 'entry':
        assert actual.senses.position == (7, 5)
    elif steps[-1] == 'observation':
        assert actual.senses.entities[witness.uuid].position == (8, 5)
    elif steps[-1] == 'departure':
        assert witness.uuid not in actual.senses.entities
        assert not actual.actors[witness.uuid].present
    # A late cursor failure must leave the caller's retained state intact after
    # all preceding sensory facts and observations have already been processed.
    invalid = received.model_copy(update={'lineages': (*received.lineages, received.lineages[0])})
    with pytest.raises(ValueError, match='Operation occurrence sequence has a gap'):
        reduce_operation(before, invalid)
    assert before == frozen
