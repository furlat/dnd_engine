"""Atomic received operations preserve the same event-time view as saved lineages."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.core.events import EventPhase
from dnd.player.bodies import loadout_id
from dnd.player.audience import PlayerAudience
from dnd.player.capture import capture_interval
from dnd.core.events import EventQueue
from dnd.player.facts import (
    BodyRecord, BodyState, PlayerLineage, PlayerNode, PlayerUpdate, SensoryFact,
    SpatialFact, VersionRows,
)
from dnd.player.projection import SessionProjection, begin_projection
from dnd.player.reduction import reduce_initialization, reduce_lineage, reduce_operation
from dnd.types.event_facts import SpatialChangeType
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
    _, initial = begin_projection(SessionProjection(), envelope)
    before = reduce_initialization(initial)
    frozen = deepcopy(before)
    # A settlement of the seat that changed nothing it is shown but its paths.
    sensory = SensoryFact(paths_dirty=True)
    lineages = []
    for index, step in enumerate(steps, start=before.reducer_cursor):
        # Each step is its own one-version lineage: its occurrence is its lineage's index.
        fact = None
        bodies = ()
        if step in ('sensory', 'canceled'):
            fact = sensory
        elif step == 'entry':
            fact = SpatialFact(change_type=SpatialChangeType.ENTITY_ENTERED,
                entity_uuid=owner.uuid, position=(7, 5), commit_occurrence=index)
        elif step == 'departure':
            fact = SpatialFact(change_type=SpatialChangeType.ENTITY_LEFT,
                entity_uuid=witness.uuid, position=(6, 5), commit_occurrence=index,
                terminal_departure=True)
        else:
            # The witness's body entering view again, hurt: every changeable field, its birth held.
            held = before.actors[witness.uuid]
            bodies = (BodyRecord(occurrence=index, actor_uuid=witness.uuid, body=BodyState(
                visual_loadout_id=loadout_id(held.visual_loadout), normal_hp=1, maximum_hp=held.maximum_hp,
                temporary_hp=held.temporary_hp, life_state=held.life_state, armor_class=held.armor_class,
                conditions=held.conditions, occupancy_layer=held.occupancy_layer, faction=held.faction,
                resolved_size=held.resolved_size), loadout=held.visual_loadout),)
        node = PlayerNode(occurrence=index, parent_event=None,
            parent_lineage=None, children_lineages=(), phase=EventPhase.COMPLETION,
            canceled=step == 'canceled', fact=fact)
        lineages.append(PlayerLineage(lineage=index, root=0, events=(node,),
            version_rows=VersionRows(occurrences=(index,), lineages=(index,)),
            start_cursor=index, end_cursor=index + 1, bodies=bodies,
            sensory_rows=initial.sensory_rows))
    if together:
        lineages = [replace(lineages[0], events=tuple(node for row in lineages for node in row.events),
            version_rows=VersionRows(occurrences=tuple(value for row in lineages for value in row.version_rows.occurrences),
                lineages=tuple(value for row in lineages for value in row.version_rows.lineages)),
            bodies=tuple(value for row in lineages for value in row.bodies),
            end_cursor=lineages[-1].end_cursor)]
    update = PlayerUpdate(generation=before.generation, observer_uuid=owner.uuid, lineages=tuple(lineages), hud=None,
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
        assert actual.actors[witness.uuid].normal_hp == 1
    elif steps[-1] == 'departure':
        assert witness.uuid not in actual.senses.entities
        assert not actual.actors[witness.uuid].present
    # A late cursor failure must leave the caller's retained state intact after
    # all preceding sensory facts and observations have already been processed.
    invalid = received.model_copy(update={'lineages': (*received.lineages, received.lineages[0])})
    with pytest.raises(ValueError, match='Operation occurrence sequence has a gap'):
        reduce_operation(before, invalid)
    assert before == frozen
