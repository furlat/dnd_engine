"""Paralysis outline clocks follow admitted owners, not the scene's age."""

from uuid import uuid4

import pygame
import pytest

from dnd.core.condition_types import ConditionCategory
from game.actor_facts import ConditionFact
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.condition_animation import resolve_condition_appearance
from game.condition_draw import condition_body_outline
from game.condition_media_lifetime import ConditionMediaLifetime, register_condition_lifetimes, sample_condition_lifetimes
from game.player_projection import project_sequence
from game.player_reduction import reduce_lineage, decode_player_sequence, encode_player_sequence
from tests.game.hold_scenarios import hold_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


def test_delayed_native_application_and_surviving_replacement_keep_owner_clock(data):
    history = hold_history(program='hold_person', retain_paralysis=True)
    projected = project_sequence(history.views['caster'])
    # Match the public history decoder boundary used by the other native tests.
    state, roots = decode_player_sequence(encode_player_sequence(projected))
    clock = 10000.
    records = {}
    selected_owners = set()
    starts = set()
    saw_after_hold_clear = False
    for root in roots:
        group = bind_choreography(state, root, data)
        records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
            lineage=root, choreography=group)
        state = reduce_lineage(state, root)
        now = clock + group.complete_ms
        appearances = {str(actor.uuid): resolve_condition_appearance(actor.conditions,
            data.condition_recipes, data.condition_media) for actor in state.actors.values()}
        sampled = sample_condition_lifetimes(appearances, records, data, now)
        for appearance in sampled.values():
            if appearance.body_outline is None:
                continue
            owner = appearance.outline_owner_uuid
            assert owner is not None
            start = records[owner].applied_ms
            assert start is not None
            selected_owners.add(owner)
            starts.add(start)
            assert appearance.outline_age_ms == pytest.approx(now - start)
            assert appearance.time_ms == now
            onset = sample_condition_lifetimes(appearances, records, data, start)[str(records[owner].actor_uuid)]
            assert onset.outline_age_ms == 0
            body = pygame.Surface((48, 64), pygame.SRCALPHA)
            body.fill((20, 40, 60, 255), (8, 8, 32, 48))
            initial = condition_body_outline(body, appearance.body_outline, onset.outline_age_ms)
            quiet = condition_body_outline(body, appearance.body_outline, None)
            assert (pygame.surfarray.array_alpha(initial) > pygame.surfarray.array_alpha(quiet)).any()
            saw_after_hold_clear |= 'condition.spell.hold_person' not in appearance.matched_behavior_ids
        clock = now + 25
    assert len(selected_owners) == 2 and len(starts) == 1
    assert saw_after_hold_clear


def test_unknown_reacquired_owner_does_not_fabricate_outline_onset(data):
    actor, owner = uuid4(), uuid4()
    fact = ConditionFact(condition_uuid=owner, category=ConditionCategory.CONDITION,
        behavior_id='condition.paralyzed', event_uuid=uuid4(), name='Paralyzed',
        resulting_max_hp=None, resulting_ac=None)
    appearance = resolve_condition_appearance((fact,), data.condition_recipes, data.condition_media)
    records = {owner: ConditionMediaLifetime(actor, owner, 'condition.paralyzed')}
    sampled = sample_condition_lifetimes({str(actor): appearance}, records, data, 15000)[str(actor)]
    assert sampled.body_outline is not None and sampled.outline_owner_uuid == owner
    assert sampled.outline_age_ms is None and sampled.time_ms == 15000
