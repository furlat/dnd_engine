"""Environment state a client reads from existing rows: a locked container and a found trap."""
import json

import pytest

from dnd_player.transport import ProtocolError, decode

LOCK_EFFECT = {
    'effect_uuid': '00000000-0000-0000-0000-0000000000a1',
    'behavior_id': 'condition.environment.lock', 'display_name': 'Locked', 'description': 'Locked.',
}
LOCKED_CHEST = {'name': 'Iron-bound chest', 'map_char': 'Ω', 'item_effects': [LOCK_EFFECT]}
FOUND_NEEDLE = {
    'positions': {'x0': 3, 'y0': 2, 'width': 1, 'height': 1, 'bits': 'AQ=='}, 'trap_state': 'ready',
    'anchor_item_uuid': '00000000-0000-0000-0000-0000000000c1',
}


def test_a_locked_container_reads_as_one_locked_effect_row():
    assert decode('ObjectState', json.dumps(LOCKED_CHEST).encode()) == LOCKED_CHEST


def test_a_lock_row_cannot_carry_its_dc_or_key():
    with pytest.raises(ProtocolError):
        decode('ItemEffectPresentationState', json.dumps({**LOCK_EFFECT, 'lock_dc': 15}).encode())


def test_a_found_container_trap_reads_as_a_sighting_on_its_container():
    assert decode('SpatialEffectSighting', json.dumps(FOUND_NEEDLE).encode()) == FOUND_NEEDLE
