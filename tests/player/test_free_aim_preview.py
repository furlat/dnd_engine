"""Ground aiming updates the public preview within one discovery.

Boundary: real worker Choices -> serialized Preview, without committing a cast.
Input: two empty ground aims in either order, revisits, and an out-of-range aim.
Expected: each aim's own geometry/recipients/admission; no emitted events.
"""

from uuid import uuid4

import pytest

from dnd.core.events import EventQueue
from dnd.player.commands import ActionSelection
from dnd.spells.evocation import Fireball
from server.protocol import PreviewRequest, PreviewResponse
from server.worker import dispatch
from server.worker_protocol import Preview
from tests.player.test_compact_choices import request_choices, rows
from tests.player.test_solid_wall_transport import wall_world


@pytest.mark.parametrize('aims', [((7, 7), (10, 7)), ((10, 7), (7, 7))])
def test_ground_preview_tracks_each_aim_and_rejects_illegal_aim_after_valid(aims):
    with wall_world(Fireball, displaced=False) as world:
        runtime, seat, publication = world
        discovered = request_choices(world).choices
        row = next(row for row in rows(discovered)
            if row.behavior_id == 'spell.fireball' and row.can_afford)
        assert row.position_region is not None
        entities = {entity.position: entity.uuid for entity in runtime.session.game.entities.values()}
        assert all(aim not in entities for aim in aims)
        expected = {
            (7, 7): {entities[(3, 7)], entities[(8, 7)], entities[(8, 8)]},
            (10, 7): {entities[(8, 7)], entities[(8, 8)]},
        }
        before = EventQueue.event_cursor()
        for aim in (*aims, *aims, (500, 500), aims[0]):
            query = PreviewRequest(actor_uuid=publication.boundary.input_actor_uuid,
                state_revision=publication.state_revision,
                discovery_generation=discovered.discovery_generation, correlation_id=uuid4(),
                selection=ActionSelection(row.discovery_index, (), extra_target_positions=(aim,)))
            _, _, response = dispatch(runtime, Preview(seat_id=seat, request=query))
            detached = PreviewResponse.model_validate_json(response.model_dump_json())
            assert detached.request == query
            value = detached.preview
            assert EventQueue.event_cursor() == before
            if aim == (500, 500):
                assert not value.can_confirm
                assert value.reason
                continue
            assert value.can_confirm
            assert value.geometry.shape == 'sphere'
            assert value.geometry.center == aim
            assert value.area_preview == 'computed'
            assert set(value.affected_entity_uuids) == expected[aim]
            assert aim in {value.positions[index] for index in value.affected_positions}
