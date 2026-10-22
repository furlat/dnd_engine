"""Transport preserves ordered audience changes and the Codex input boundary."""
import json

import pytest

from dnd_player.transport import ProtocolError, decode

CASTER = '00000000-0000-4000-8000-000000000001'
SUMMON = '00000000-0000-4000-8000-000000000002'


def test_audience_transition_round_trip_preserves_member_order_and_revision():
    grant = {'kind': 'audience', 'audience': {'controlled': [CASTER, SUMMON],
        'observers': [CASTER, SUMMON], 'revision': 1}, 'sensory': None}
    revoke = {'kind': 'audience', 'audience': {'controlled': [CASTER],
        'observers': [CASTER], 'revision': 2}, 'sensory': None}
    assert [decode('AudienceFact', json.dumps(row).encode()) for row in (grant, revoke)] == [grant, revoke]
    boundary = {'lifecycle': 'waiting_for_codex', 'input_actor_uuid': SUMMON, 'state_revision': 'summon-turn'}
    assert decode('BoundaryState', json.dumps(boundary).encode()) == boundary


@pytest.mark.parametrize('changes', [{'revision': -1}, {'revision': 1.5}, {'controlled': ['not-a-uuid']}])
def test_malformed_audience_transition_is_rejected(changes):
    fact = {'kind': 'audience', 'audience': {'controlled': [CASTER], 'observers': [CASTER], 'revision': 1, **changes}}
    with pytest.raises(ProtocolError):
        decode('AudienceFact', json.dumps(fact).encode())
