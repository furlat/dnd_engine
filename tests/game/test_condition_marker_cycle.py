"""Overhead symbols share one slot without changing other condition visuals."""

from dataclasses import replace
from uuid import UUID

import pytest

from game.animation_data import load_animation_data
from game.condition_animation import resolve_condition_appearance
from game.condition_media import ResolvedConditionLayer
from game.condition_sampling import select_condition_markers
from game.actor_facts import ConditionFact
from dnd.core.condition_types import ConditionCategory


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


def layers(data, identity, owner):
    recipe = data.condition_recipes[identity]
    return tuple(ResolvedConditionLayer(row, data.condition_media[row.assetId], owner)
                 for row in recipe.persistent.layers)


def groups(rows):
    return {row.layer.markerGroup for row in rows if row.layer.markerGroup is not None}


def test_multiple_symbols_cycle_while_body_effects_continue(data):
    a = layers(data, "condition.blinded", UUID(int=1))
    b = layers(data, "condition.deafened", UUID(int=2))
    body = tuple(row for row in layers(data, "condition.frightened", UUID(int=3))
                 if row.layer.markerGroup is None)
    seen = set()
    for time in (0, 1800, 3600, 5400):
        selected = select_condition_markers(a + b + body, time, activity="idle", life_state="alive")
        assert len(groups(selected)) == 1
        assert all(row in selected for row in body)
        assert sum(row.layer.markerGroup is not None for row in selected) == 2  # front/back together
        seen.update(groups(selected))
        assert selected == select_condition_markers(b + a + body, time, activity="idle", life_state="alive")
    assert seen == {"blinded", "deafened"}


def test_alias_owners_share_one_symbol_and_removal_reveals_survivor(data):
    a = layers(data, "condition.incapacitated", UUID(int=1))
    b = layers(data, "condition.spell.hypnotic_pattern", UUID(int=2))
    selected = select_condition_markers(b + a, 2300, activity="idle", life_state="alive")
    assert len(selected) == 1
    assert selected[0].owner_uuid == UUID(int=1)
    assert select_condition_markers(b, 2300, activity="idle", life_state="alive") == b
    assert not select_condition_markers((), 2300, activity="idle", life_state="alive")


def test_invisible_candidates_do_not_create_empty_slots(data):
    a = layers(data, "condition.blinded", UUID(int=1))
    b = layers(data, "condition.no_reactions", UUID(int=2))
    delayed = tuple(replace(row, application=True, age_ms=100,
        layer=row.layer.model_copy(update={"startOffsetMs": 500})) for row in b)
    for time in (0, 1800, 3600):
        assert select_condition_markers(a + delayed, time, activity="idle", life_state="alive") == a
    assert not select_condition_markers(b, 0, activity="idle", life_state="dead")


def test_duplicate_membership_input_order_selects_same_owner(data):
    identity = "condition.blinded"
    def fact(owner):
        return ConditionFact(condition_uuid=owner, category=ConditionCategory.CONDITION,
            behavior_id=identity, event_uuid=UUID(int=3), name="Blinded", resulting_max_hp=None, resulting_ac=None)
    a, b = fact(UUID(int=1)), fact(UUID(int=2))
    first = resolve_condition_appearance((a,b),data.condition_recipes,data.condition_media)
    second = resolve_condition_appearance((b,a),data.condition_recipes,data.condition_media)
    assert first.layers == second.layers
    assert {row.owner_uuid for row in first.layers} == {UUID(int=1)}


def test_three_groups_cycle_and_retired_cue_never_competes(data):
    a = layers(data, "condition.blinded", UUID(int=1))
    b = layers(data, "condition.deafened", UUID(int=2))
    c = layers(data, "condition.no_reactions", UUID(int=3))
    seen = [groups(select_condition_markers(a+b+c, time, activity="idle", life_state="alive"))
            for time in (0,1800,3600)]
    assert len(set.union(*seen)) == 3
    retired = tuple(replace(row, removal_age_ms=50, alpha=.75) for row in a)
    for time in (0,1800,3600):
        chosen = select_condition_markers(retired+b, time, activity="idle", life_state="alive")
        assert groups(chosen) == {"deafened"}
    assert select_condition_markers(retired, 0, activity="idle", life_state="alive") == retired


def test_full_slow_and_movement_penalties_have_distinct_symbols(data):
    slow = layers(data, 'condition.spell.slow', UUID(int=1))
    movement = layers(data, 'condition.spell.spirit_guardians.slowed', UUID(int=2))
    duplicate = layers(data, 'condition.spell.spirit_guardians.slowed', UUID(int=3))
    assert groups(slow) == {'slow'}
    assert groups(movement) == {'movement_slowed'}
    assert {row.media.asset_id for row in movement} == {'condition.marker.movement_slowed.overhead'}
    body = tuple(row for row in slow if row.layer.markerGroup is None)
    seen = set()
    for time in (0, 1800):
        chosen = select_condition_markers(slow + movement + duplicate, time,
            activity='idle', life_state='alive')
        assert all(row in chosen for row in body)
        assert sum(row.layer.markerGroup is not None for row in chosen) == 1
        seen.update(groups(chosen))
    assert seen == {'slow', 'movement_slowed'}
    assert groups(select_condition_markers(duplicate, 0,
        activity='idle', life_state='alive')) == {'movement_slowed'}
