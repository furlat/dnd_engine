"""Objective illumination and replayed subjective-perception contracts."""

from uuid import UUID

from dnd.blocks.sensory import Senses, capture_senses_snapshot
from dnd.core.events.events_registry import EventPhase, EventQueue, EventType
from dnd.core.events.world_events import SensoryUpdateEvent
from dnd.core.gridmap import get_map
from dnd.types.senses import PerceivedContact, SensesType
from dnd.types.world import LightLevel
from tests.engine.support import create_test_monster, reset_combat_state


def reset_objective_scene(*, default_light: LightLevel) -> None:
    """Build one event-silent line before deploying observers."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 6, 1)
    for position in grid.get_all_tiles():
        grid.set_tile_base_light(position, default_light)
    grid.enable_events(flush_pending=False)


def observer_updates(observer_uuid: UUID) -> list[SensoryUpdateEvent]:
    """Return the recorded subjective projection for one observer."""
    return [
        event
        for event in EventQueue.get_events_by_type(EventType.SENSORY_UPDATE)
        if isinstance(event, SensoryUpdateEvent)
        and event.phase is EventPhase.COMPLETION
        and event.observer_uuid == observer_uuid
    ]


def perception_projection(senses: Senses) -> tuple[object, ...]:
    """Return the accepted replay projection without navigation caches."""
    snapshot = capture_senses_snapshot(senses)
    return (
        snapshot.position,
        snapshot.visible,
        snapshot.seen,
        snapshot.entities,
        snapshot.objects,
        snapshot.effective_light_levels,
        tuple(senses.get_sense_modes()),
        snapshot.passive_perception,
        snapshot.visual_access,
    )


def test_objective_darkness_and_subjective_darkvision_remain_distinct() -> None:
    """Darkvision changes observer projection without rewriting objective light."""
    reset_objective_scene(default_light=LightLevel.DARKNESS)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=True,
    )
    target = create_test_monster(
        "monster.skeleton", name="Target", position=(3, 0), darkvision=False,
    )

    tile = get_map().get_tile(3, 0)
    assert tile is not None
    assert tile.resolved_light_level is LightLevel.DARKNESS
    assert observer.senses.effective_light_levels[(3, 0)] is LightLevel.DIM_LIGHT
    assert observer.senses.entities[target.uuid] == PerceivedContact(
        position=(3, 0),
        visual=True,
        special_senses=(SensesType.DARKVISION,),
    )


def test_typed_sensory_events_replay_the_complete_subjective_projection() -> None:
    """Cold deltas rebuild Senses without querying live GridMap state."""
    reset_objective_scene(default_light=LightLevel.DARKNESS)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=True,
    )
    create_test_monster(
        "monster.skeleton", name="Target", position=(3, 0), darkvision=False,
    )

    replay = Senses.create(source_entity_uuid=observer.uuid)
    for event in observer_updates(observer.uuid):
        replay.apply_sensory_update(event)

    assert perception_projection(replay) == perception_projection(observer.senses)
    assert all(
        isinstance(contact, PerceivedContact)
        for contact in replay.entities.values()
    )
