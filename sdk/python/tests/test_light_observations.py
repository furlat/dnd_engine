"""Public optical DTO admission; source privacy and gameplay are tested at projection."""
import json

import pytest

from dnd_player.transport import ProtocolError, decode


SOURCE = {
    'source_uuid': '00000000-0000-4000-8000-000000000001', 'revision': 3,
    'position': [-2, 6], 'base_height_steps': 2, 'very_bright_radius_feet': 10,
    'bright_radius_feet': 20, 'dim_radius_feet': 20, 'appearance': 'torch',
    'actor_anchored': True, 'anchor_entity_uuid': None, 'anchor_item_uuid': None,
    'affected_tiles': {'-2,6': 4, '1,6': 3, '4,6': 2},
}


def test_optical_source_preserves_anonymous_anchor_and_exact_footprint():
    assert decode('PerceivedLightSource', json.dumps(SOURCE).encode()) == SOURCE
    sparse = {key: value for key, value in SOURCE.items() if key not in
        ('appearance', 'actor_anchored', 'anchor_entity_uuid', 'anchor_item_uuid', 'affected_tiles')}
    assert decode('PerceivedLightSource', json.dumps(sparse).encode()) == sparse


@pytest.mark.parametrize('field,value', [
    ('revision', -1), ('position', [1]), ('position', [1.5, 2]),
    ('appearance', 'private_inventory'), ('actor_anchored', 1),
    ('affected_tiles', {'1,2': 99}), ('anchor_item_uuid', 'not-a-uuid'),
])
def test_invalid_optical_source_is_rejected(field, value):
    with pytest.raises(ProtocolError):
        decode('PerceivedLightSource', json.dumps({**SOURCE, field: value}).encode())
