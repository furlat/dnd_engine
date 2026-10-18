"""Public optical DTO admission; source privacy and gameplay are tested at projection."""
import json

import pytest

from dnd_player.transport import ProtocolError, decode


# A light source row of its group: identities are rows of the group's uuids; the footprint is a level per cell.
SOURCE = {
    'source': 0, 'revision': 3, 'position': [-2, 6], 'base_height_steps': 2, 'very_bright_radius_feet': 10,
    'bright_radius_feet': 20, 'dim_radius_feet': 20, 'appearance': 'torch', 'actor_anchored': True,
    'anchor_entity': None, 'anchor_item': 1,
    'affected_tiles': {'cells': {'x0': -2, 'y0': 6, 'width': 7, 'height': 1, 'bits': 'SQ=='}, 'values': 'BAMC'},
}


def test_light_row_preserves_anchors_footprint_and_sparse_defaults():
    assert decode('LightRow', json.dumps(SOURCE).encode()) == SOURCE
    sparse = {key: value for key, value in SOURCE.items() if key not in
        ('base_height_steps', 'appearance', 'actor_anchored', 'anchor_entity', 'anchor_item', 'affected_tiles')}
    assert decode('LightRow', json.dumps(sparse).encode()) == sparse


@pytest.mark.parametrize('field,value', [
    ('revision', -1), ('source', -1), ('position', [1]), ('position', [1.5, 2]),
    ('appearance', 'private_inventory'), ('actor_anchored', 1),
    ('affected_tiles', {'1,2': 4}), ('anchor_item', 'not-an-index'),
])
def test_invalid_light_row_is_rejected(field, value):
    with pytest.raises(ProtocolError):
        decode('LightRow', json.dumps({**SOURCE, field: value}).encode())
