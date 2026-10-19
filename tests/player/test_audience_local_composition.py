"""A seat composes its members' observations once per settlement, as a function of their snapshots alone
(plan §3.1, §3.2): the incremental composition always equals the cold one."""

from copy import deepcopy
from uuid import UUID

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import EventPhase, SensoryUpdateEvent
from dnd.core.sensory_fold import reduce_senses_snapshot
from dnd.player.audience import (
    AudienceComposition, AudiencePerception, ComposedEffect, PlayerAudience, apply_settlement, composed_view,
)
from dnd.types.cells import value_at
from dnd.types.senses import PerceivedContact, PerceivedSpatialEffect
from dnd.types.world import LightLevel
from tests.sensory_cells import cells, packed_cells


FIRST, SECOND, SUBJECT, EFFECT = (UUID(int=value) for value in (1, 2, 3, 4))
AUDIENCE = PlayerAudience((FIRST, SECOND), (FIRST, SECOND))


def delta(observer, *, initial=False, **values):
    values = packed_cells(values)
    if initial:
        values = dict(observer_position=(0, 0), observer_position_changed=True,
            sense_modes_changed=True, sense_modes=[], passive_perception_changed=True,
            passive_perception=10, visual_access_changed=True, visual_access=1, **values)
    return SensoryUpdateEvent.model_validate(dict(observer_uuid=observer,
        source_entity_uuid=observer, initial=initial, use_register=False,
        phase=EventPhase.COMPLETION, **values), context=PASSIVE_EVENT_REPLAY)


def effect(positions, *, apparent=True, revision=1, **values):
    return PerceivedSpatialEffect(content_ref=ContentRef(pack_id='test.pack',
        definition_kind=ContentDefinitionKind.CONDITION, content_id='test.shared',
        content_version=1, definition_contract_hash='0'*64), name='Shared', description='',
        positions=positions, owner_revision=revision, apparent_presence=apparent, **values)


def check(rows):
    """Fold saved observations, a settlement per row (one observation or several), and compare the owned
    composition with the cold one: each member's snapshot folded on its own, then composed."""
    members = {}
    current = AudienceComposition()
    history = []
    changes = []
    for value in rows:
        settlement = value if isinstance(value, list) else [value]
        events = [SensoryUpdateEvent.model_validate_json(row.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
                  for row in settlement]
        for event in events:
            members[event.observer_uuid] = reduce_senses_snapshot(event.observer_uuid, members.get(event.observer_uuid),
                                                                   event)
        public = AudiencePerception(dict(members))
        changes.append(apply_settlement(current, AUDIENCE, FIRST, events))
        assert current.perception == public
        assert current.view == composed_view(public, FIRST)
        history.append((public, deepcopy(public)))
    for retained, expected in history:
        assert retained == expected
    return current, changes


def test_shared_light_contact_ties_and_member_reset_keep_other_evidence():
    visual = PerceivedContact(position=(0, 0), visual=True)
    distant = PerceivedContact(position=(4, 0), visual=False)
    current, _ = check([
        delta(FIRST, initial=True, visible_cells_added=[(0, 0)], seen_cells_added=[(0, 0), (9, 0)],
            effective_light_levels_changed={(0, 0): LightLevel.DIM_LIGHT.value},
            hazardous_cells_changed={(0, 0): False}, entity_contacts_changed={SUBJECT: visual}),
        delta(SECOND, initial=True, visible_cells_added=[(0, 0)], seen_cells_added=[(0, 0)],
            effective_light_levels_changed={(0, 0): LightLevel.BRIGHT_LIGHT.value},
            hazardous_cells_changed={(0, 0): True}, entity_contacts_changed={SUBJECT: distant}),
    ])
    # A visual holder's contact is shown before a member's later, non-visual one (no sighting order).
    assert current.view.entities[SUBJECT] == visual
    current, _ = check([
        delta(FIRST, initial=True, visible_cells_added=[(0, 0)], seen_cells_added=[(0, 0), (9, 0)],
            effective_light_levels_changed={(0, 0): LightLevel.DIM_LIGHT.value},
            hazardous_cells_changed={(0, 0): False}, entity_contacts_changed={SUBJECT: visual}),
        delta(SECOND, initial=True, visible_cells_added=[(0, 0)], seen_cells_added=[(0, 0)],
            effective_light_levels_changed={(0, 0): LightLevel.BRIGHT_LIGHT.value},
            hazardous_cells_changed={(0, 0): True}, entity_contacts_changed={SUBJECT: distant}),
        delta(FIRST, effective_light_levels_changed={(0, 0): LightLevel.BRIGHT_LIGHT.value}),
        delta(FIRST, initial=True, visible_cells_added=[(2, 0)], seen_cells_added=[(2, 0)]),
    ])
    assert value_at(current.view.hazardous_cells, (0, 0)) == 1
    assert current.view.entities[SUBJECT] == distant
    assert cells(current.view.visible) == {(0, 0), (2, 0)}


def test_owner_handover_matches_the_cold_composition():
    """A cell's composed light follows its brightest member as members change and leave."""
    dim, bright = LightLevel.DIM_LIGHT.value, LightLevel.BRIGHT_LIGHT.value
    current, _ = check([
        delta(FIRST, initial=True, visible_cells_added=[(0, 0), (1, 0)],
            effective_light_levels_changed={(0, 0): dim, (1, 0): dim}),
        delta(SECOND, initial=True, visible_cells_added=[(0, 0), (1, 0)],
            effective_light_levels_changed={(0, 0): bright, (1, 0): bright}),
        delta(FIRST, effective_light_levels_changed={(0, 0): LightLevel.DARKNESS.value}),
        delta(SECOND, visible_cells_removed=[(0, 0)]),
        delta(FIRST, visible_cells_removed=[(1, 0)]),
        delta(SECOND, initial=True, visible_cells_added=[(0, 0)], effective_light_levels_changed={(0, 0): dim}),
    ])
    assert cells(current.view.visible) == {(0, 0)}


def test_hazards_follow_owners_and_a_moving_member_match_the_cold_composition():
    """A hazard changes no cell's owner; a member's view can move past every cell the seat held."""
    dim, bright = LightLevel.DIM_LIGHT.value, LightLevel.BRIGHT_LIGHT.value
    current, _ = check([
        delta(FIRST, initial=True, visible_cells_added=[(0, 0), (1, 0)],
            effective_light_levels_changed={(0, 0): dim, (1, 0): dim},
            hazardous_cells_changed={(0, 0): False, (1, 0): False}),
        delta(SECOND, initial=True, visible_cells_added=[(1, 0)],
            effective_light_levels_changed={(1, 0): bright}, hazardous_cells_changed={(1, 0): False}),
        delta(FIRST, hazardous_cells_changed={(0, 0): True, (1, 0): True}),
        delta(SECOND, hazardous_cells_changed={(1, 0): True}),
        delta(FIRST, visible_cells_removed=[(0, 0), (1, 0)], visible_cells_added=[(8, 3), (9, 3)],
            effective_light_levels_changed={(8, 3): dim, (9, 3): bright},
            hazardous_cells_changed={(8, 3): True, (9, 3): False}),
        delta(FIRST, hazardous_cells_changed={(9, 3): True}),
    ])
    assert cells(current.view.visible) == {(1, 0), (8, 3), (9, 3)}
    assert {position: value_at(current.view.hazardous_cells, position) for position in ((1, 0), (8, 3), (9, 3))} == {
        (1, 0): 1, (8, 3): 1, (9, 3): 1}


def test_an_effect_is_composed_from_what_its_members_see_now():
    """Only the visible part of each member's row is composed: a cell the member remembers but no longer sees is
    not shown, wherever another member looks; a found concealed effect leaves with its finder's removal."""
    current, changes = check([
        delta(FIRST, initial=True, visible_cells_added=[(0, 0)],
            spatial_effects_changed={EFFECT: effect(((0, 0), (1, 0)))}),
        delta(SECOND, initial=True, visible_cells_added=[(1, 0)]),
    ])
    assert current.view.spatial_effects[EFFECT].positions == ((0, 0),)
    assert changes[0].effects[EFFECT][1] == ComposedEffect(effect(((0, 0),)), frozenset({FIRST}))
    current, changes = check([
        delta(FIRST, initial=True, visible_cells_added=[(0, 0)],
            spatial_effects_changed={EFFECT: effect(((0, 0),), apparent=False)}),
        delta(SECOND, initial=True, visible_cells_added=[(0, 0)]),
        delta(FIRST, spatial_effects_removed={EFFECT}),
    ])
    assert EFFECT not in current.view.spatial_effects
    assert changes[2].effects[EFFECT][1] is None and changes[2].retired == {EFFECT: frozenset({(0, 0)})}


def test_effect_union_reset_and_reappearance_keep_compatible_values():
    current, _ = check([
        delta(FIRST, initial=True, visible_cells_added=[(0, 0)],
            spatial_effects_changed={EFFECT: effect(((0, 0),), anchor_position=(0, 0))}),
        delta(SECOND, initial=True, visible_cells_added=[(1, 0)],
            spatial_effects_changed={EFFECT: effect(((1, 0),), anchor_position=(0, 0))}),
        delta(SECOND, initial=True, visible_cells_added=[(1, 0)]),
        delta(FIRST, spatial_effects_changed={EFFECT: effect(((0, 0), (2, 0)), revision=2)}),
        delta(SECOND, visible_cells_added=[(2, 0)],
            spatial_effects_changed={EFFECT: effect(((1, 0), (2, 0)), revision=2)}),
    ])
    assert current.view.spatial_effects[EFFECT].positions == ((0, 0), (1, 0), (2, 0))
    assert current.view.spatial_effects[EFFECT].owner_revision == 2


def test_a_settlement_composes_once_and_equals_its_members_folded_one_by_one():
    """One composition per settlement: the members' observations folded together give the view they give one
    by one, and the change names each record once, its member bits after the whole settlement."""
    visual = PerceivedContact(position=(0, 0), visual=True)
    rows = [delta(FIRST, initial=True, visible_cells_added=[(0, 0)], entity_contacts_changed={SUBJECT: visual}),
            delta(SECOND, initial=True, visible_cells_added=[(0, 0)], entity_contacts_changed={SUBJECT: visual})]
    together, changes = check([rows])
    one_by_one, _ = check(rows)
    assert together.view == one_by_one.view
    (before, after), = changes[0].entities.values()
    assert before is None and after is not None and after.members == {FIRST, SECOND}
    assert changes[0].initial and cells(changes[0].visible_added) == {(0, 0)}


def test_rejected_delta_does_not_mutate():
    current = AudienceComposition()
    apply_settlement(current, AUDIENCE, FIRST, [delta(FIRST, initial=True, visible_cells_added=[(0, 0)],
        seen_cells_added=[(0, 0)])])
    before = deepcopy(current)
    with pytest.raises(ValueError):
        # A delta for a member without its initial state is rejected by the shared reducer.
        apply_settlement(current, AUDIENCE, FIRST, [delta(SECOND, visible_cells_added=[(2, 0)])])
    assert current == before
    apply_settlement(current, AUDIENCE, FIRST, [delta(FIRST, seen_cells_added=[(2, 0)])])
    # The server keeps no seen cells: the client folds them (plan §3.2).
    assert cells(current.view.seen) == set()
