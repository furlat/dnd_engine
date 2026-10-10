"""Both real observers replay retained cloud occupancy through door transitions."""

import pytest

from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.types.senses import PerceivedSpatialEffect
from dnd.player.reduction import reduce_lineage
from tests.game.persistent_spell_scenarios import persistent_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module')
def door_history():
    return persistent_spell_history(program='insect_plague', environment='door-cycle')


def test_cloud_and_door_lineages_replay_for_both_observers_without_engine(door_history):
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    observations = []
    for role in ('caster', 'target'):
        state, lineages = player_history(door_history, role=role)
        states = []
        for lineage in lineages:
            state = reduce_lineage(state, lineage)
            assert state.senses is not None
            states.extend(effect for effect in state.senses.spatial_effects.values()
                if effect.content_ref.content_id == 'spatial_effect.spell.insect_plague')
        assert states
        assert all(effect.area_propagation == 'connected' for effect in states)
        assert all(effect.area_geometry == states[0].area_geometry for effect in states)
        assert not any(effect.content_ref.content_id == 'spatial_effect.spell.insect_plague'
                       for effect in state.senses.spatial_effects.values())
        observations.append(tuple(states))
    assert observations[0] != observations[1], 'Each observer retains its own permitted cells'
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


def test_old_spatial_record_retains_cells_without_guessing_a_new_policy(door_history):
    state, lineages = player_history(door_history)
    state = reduce_lineage(state, lineages[0])
    assert state.senses is not None
    effect, = state.senses.spatial_effects.values()
    legacy = PerceivedSpatialEffect.model_validate_json(effect.model_dump_json(exclude={'area_propagation'}))
    assert legacy.area_propagation is None
    assert legacy.positions == effect.positions and legacy.area_geometry == effect.area_geometry
    assert legacy.suppressions == effect.suppressions


def test_inset_wall_upper_surface_survives_both_player_event_streams():
    history = persistent_spell_history(program='cloudkill', environment='wall')
    assert not Entity.get_all_entities()
    for role in ('caster', 'target'):
        state, lineages = player_history(history, role=role)
        grants = []
        for lineage in lineages:
            state = reduce_lineage(state, lineage)
            assert state.senses is not None
            for effect in state.senses.spatial_effects.values():
                grants.extend(effect.upper_volume_surfaces)
                for row in effect.upper_volume_surfaces:
                    assert row.position not in effect.visible_volume_positions
                    assert row.position not in state.senses.visible
                    assert row.lower_height_planes
        assert grants, role
        assert not state.senses.spatial_effects, 'Ending the real cloud removes current volume permission'
