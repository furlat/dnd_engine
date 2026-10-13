"""Shared recorded observations preserve arbitration while advancing owned views."""

from copy import deepcopy
from uuid import UUID

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import EventPhase, SensoryUpdateEvent
from dnd.player.audience import (
    AudienceComposition, AudiencePerception, PlayerAudience, apply_current_audience,
    audience_view, begin_audience_composition, observe_audience,
)
from dnd.types.senses import PerceivedContact, PerceivedSpatialEffect
from dnd.types.world import LightLevel


FIRST, SECOND, SUBJECT, EFFECT = (UUID(int=value) for value in (1, 2, 3, 4))
AUDIENCE = PlayerAudience((FIRST, SECOND), (FIRST, SECOND))


def delta(observer, *, initial=False, **values):
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
    """Read saved inputs, compare each owned result to the detached public fold."""
    public = AudiencePerception()
    current = AudienceComposition()
    history = []
    for cursor, value in rows:
        event = SensoryUpdateEvent.model_validate_json(value.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        public = observe_audience(public, AUDIENCE, event, cursor)
        apply_current_audience(current, AUDIENCE, FIRST, event, cursor)
        assert current.perception == public
        assert current.view == audience_view(public, FIRST)
        history.append((public, deepcopy(public)))
    for retained, expected in history:
        assert retained == expected
    return current


def test_shared_light_contact_ties_and_member_reset_keep_other_evidence():
    visual = PerceivedContact(position=(0, 0), visual=True)
    distant = PerceivedContact(position=(4, 0), visual=False)
    current = check([
        (0, delta(FIRST, initial=True, visible_cells_added=[(0, 0)], seen_cells_added=[(0, 0), (9, 0)],
            effective_light_levels_changed={'0,0': LightLevel.DIM_LIGHT.value},
            hazardous_cells_changed={'0,0': False}, entity_contacts_changed={SUBJECT: visual})),
        (1, delta(SECOND, initial=True, visible_cells_added=[(0, 0)], seen_cells_added=[(0, 0)],
            effective_light_levels_changed={'0,0': LightLevel.BRIGHT_LIGHT.value},
            hazardous_cells_changed={'0,0': True}, entity_contacts_changed={SUBJECT: distant})),
        (2, delta(FIRST, effective_light_levels_changed={'0,0': LightLevel.BRIGHT_LIGHT.value})),
        (3, delta(FIRST, initial=True, visible_cells_added=[(2, 0)], seen_cells_added=[(2, 0)])),
    ])
    assert current.view.seen == {(0, 0), (2, 0)}
    assert current.view.hazardous_cells[(0, 0)]
    assert current.view.entities[SUBJECT] == distant
    assert current.view.visible == {(0, 0), (2, 0)}


def test_empty_delta_renews_absence_against_older_positive_evidence():
    current = check([
        (0, delta(FIRST, initial=True, visible_cells_added=[(0, 0)],
            spatial_effects_changed={EFFECT: effect(((0, 0), (1, 0)))})),
        (1, delta(SECOND, initial=True, visible_cells_added=[(1, 0)])),
        (9, delta(SECOND)),
        (4, delta(FIRST, visible_cells_added=[(1, 0)],
            spatial_effects_changed={EFFECT: effect(((0, 0), (1, 0)))})),
    ])
    assert current.view.spatial_effects[EFFECT].positions == ((0, 0),)
    current = check([
        (0, delta(FIRST, initial=True, visible_cells_added=[(0, 0)],
            spatial_effects_changed={EFFECT: effect(((0, 0),), apparent=False)})),
        (1, delta(SECOND, initial=True, visible_cells_added=[(0, 0)])),
        (2, delta(FIRST, spatial_effects_removed={EFFECT})),
    ])
    assert EFFECT not in current.view.spatial_effects


def test_effect_union_reset_and_reappearance_keep_compatible_values():
    current = check([
        (0, delta(FIRST, initial=True, visible_cells_added=[(0, 0)],
            spatial_effects_changed={EFFECT: effect(((0, 0),), anchor_position=(0, 0))})),
        (1, delta(SECOND, initial=True, visible_cells_added=[(1, 0)],
            spatial_effects_changed={EFFECT: effect(((1, 0),), anchor_position=(0, 0))})),
        (2, delta(SECOND, initial=True, visible_cells_added=[(1, 0)])),
        (3, delta(FIRST, spatial_effects_changed={EFFECT: effect(((0, 0), (2, 0)), revision=2)})),
        (4, delta(SECOND, visible_cells_added=[(2, 0)],
            spatial_effects_changed={EFFECT: effect(((1, 0), (2, 0)), revision=2)})),
    ])
    assert current.view.spatial_effects[EFFECT].positions == ((0, 0), (1, 0), (2, 0))
    assert current.view.spatial_effects[EFFECT].owner_revision == 2


def test_owned_acquisition_detaches_history_and_rejected_delta_does_not_mutate():
    public = observe_audience(AudiencePerception(), AUDIENCE,
        delta(FIRST, initial=True, visible_cells_added=[(0, 0)], seen_cells_added=[(0, 0)]), 0)
    retained = deepcopy(public)
    current = begin_audience_composition(public, FIRST)
    before = deepcopy(current)
    with pytest.raises(ValueError):
        apply_current_audience(current, AUDIENCE, FIRST,
            delta(FIRST, visible_cells_added=[(2, 0)], effective_light_levels_changed={'bad': 0}), 1)
    assert current == before
    apply_current_audience(current, AUDIENCE, FIRST, delta(FIRST, seen_cells_added=[(2, 0)]), 2)
    assert public == retained
    assert current.view.seen == {(0, 0), (2, 0)}
