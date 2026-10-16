"""Named retired metadata is handled only by the passive native recording reader."""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventType, EventPhase, EventQueue, ItemDestructionEvent, SpatialChangeEvent
from dnd.core.item_types import ItemLocation
from dnd.player.event_record import decode_event, encode_event
from dnd.spells.evocation import ContinualFlame
from dnd.types.world import CardinalDirection
from tests.engine.test_continual_flame_items import game as game, actor, cast


def old_ordinary_item_event(game):
    caster = actor(game)
    item = build_authored_item("weapon.club", caster.uuid)
    item.place_on_grid((3, 2))
    cast(ContinualFlame, caster, item)
    current = item.publish_location_state(ItemLocation.FLOOR)
    payload = encode_event(current)
    effect, = payload["item_state"]["item_effects"]
    effect["suppression_provider_uuids"] = []
    payload["item_state"]["suppression_provider_uuids"] = []
    return current, payload


def test_previous_ordinary_item_effect_record_decodes_without_live_retired_fields(game):
    current, payload = old_ordinary_item_event(game)
    restored = decode_event(payload)
    observed = encode_event(restored)
    expected = encode_event(current)
    assert observed == expected


@pytest.mark.parametrize("retired", [[str(uuid4())], {}, 0, None, ""])
def test_old_active_or_malformed_suppression_is_explicitly_rejected(game, retired):
    _, payload = old_ordinary_item_event(game)
    payload["item_state"]["item_effects"][0]["suppression_provider_uuids"] = retired
    with pytest.raises(ValueError, match="retired Antimagic"):
        decode_event(payload)


def test_live_item_contract_still_rejects_retired_field(game):
    current, payload = old_ordinary_item_event(game)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        type(current.item_state).model_validate(payload["item_state"])


@pytest.mark.parametrize("context", [
    {"antimagic": "an ordinary annotation"},
    {"suppression_provider_uuids": {"custom": "metadata"}},
    {"item_state": {"item_effects": [{"suppression_provider_uuids": "opaque user data"}]}},
])
def test_current_opaque_context_roundtrips_unchanged(context):
    event = Event(event_type=EventType.BASE_ACTION, source_entity_uuid=uuid4(),
        phase=EventPhase.COMPLETION, context=context, use_register=False)
    payload = encode_event(event)
    restored = encode_event(decode_event(payload))
    assert restored == payload


@pytest.mark.parametrize("snapshot_field", ["previous_state", "resulting_state", "object_state"])
@pytest.mark.parametrize("active", [False, True])
def test_archived_destruction_and_spatial_item_snapshots_obey_retired_field_contract(game, snapshot_field, active):
    caster = actor(game)
    wall = build_directional_wall()
    wall.place_on_grid((7, 2), boundary_direction=CardinalDirection.EAST)
    wall.receive_damage(10000, DamageType.FORCE, caster.uuid)
    family = SpatialChangeEvent if snapshot_field == "object_state" else ItemDestructionEvent
    event = next(event for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, family) and event.phase is EventPhase.COMPLETION
        and encode_event(event).get(snapshot_field) is not None)
    payload = encode_event(event)
    payload[snapshot_field]["suppression_provider_uuids"] = [str(uuid4())] if active else []
    if active:
        with pytest.raises(ValueError, match="retired Antimagic"):
            decode_event(payload)
    else:
        assert encode_event(decode_event(payload)) == encode_event(event)
