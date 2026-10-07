"""A fresh audience receives the recorded duration of its existing spell field."""

from uuid import uuid4

from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.events import Event, EventQueue, EventType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.player.capture import capture_interval
from dnd.player.projection import begin_projection
from dnd.player.reduction import reduce_initialization
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import GreaseZone


def test_initialization_retains_owned_spatial_duration() -> None:
    reset_engine_runtime()
    battlefield = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        owner = Entity.create(uuid4(), "Owner", config=EntityConfig(position=(5, 5)))
        owner.compose_entity()
        game.deploy_entity(owner, (5, 5))
        field = GreaseZone(source_entity_uuid=owner.uuid, position=(6, 5),
            affected_positions={(6, 5)},
            duration=Duration(duration=3, duration_type=DurationType.ROUNDS))
        assert field.activate(parent_event=Event(event_type=EventType.BASE_ACTION,
            source_entity_uuid=owner.uuid)) is not None
        expected = owner.senses.spatial_effects[field.uuid].duration
        assert expected is not None and expected.remaining_rounds == 3

        _, initialization = begin_projection(capture_interval(name="existing field", start_cursor=0,
            end_cursor=EventQueue.event_cursor(), observer_uuid=owner.uuid,
            battlefield_id=battlefield.definition.battlefield_id))
        restored = reduce_initialization(initialization)
        assert restored.senses is not None
        assert restored.senses.spatial_effects[field.uuid].duration == expected
    finally:
        game.close()
        reset_engine_runtime()
