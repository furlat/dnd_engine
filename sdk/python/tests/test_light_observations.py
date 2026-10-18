"""Public optical DTO admission; source privacy and gameplay are tested at projection."""
import json

import pytest

from dnd_player.transport import ProtocolError, decode


# A light source entering perception, as a row of its group: identities are rows of the group's uuids. It carries
# no native revision and no footprint (the cells' light is their own value).
SOURCE = {
    'source': 0, 'position': [-2, 6], 'base_height_steps': 2, 'very_bright_radius_feet': 10,
    'bright_radius_feet': 20, 'dim_radius_feet': 20, 'appearance': 'torch', 'actor_anchored': True,
    'anchor_entity': None, 'anchor_item': 1,
}


def test_light_row_preserves_anchors_and_sparse_defaults():
    assert decode('LightRow', json.dumps(SOURCE).encode()) == SOURCE
    sparse = {key: value for key, value in SOURCE.items() if key not in
        ('base_height_steps', 'appearance', 'actor_anchored', 'anchor_entity', 'anchor_item')}
    assert decode('LightRow', json.dumps(sparse).encode()) == sparse


@pytest.mark.parametrize('field,value', [
    ('revision', 3), ('source', -1), ('position', [1]), ('position', [1.5, 2]),
    ('appearance', 'private_inventory'), ('actor_anchored', 1),
    ('affected_tiles', {'1,2': 4}), ('anchor_item', 'not-an-index'),
])
def test_invalid_light_row_is_rejected(field, value):
    with pytest.raises(ProtocolError):
        decode('LightRow', json.dumps({**SOURCE, field: value}).encode())
