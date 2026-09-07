"""Closed capture, finite admission, and shared sensory reduction proofs."""

from uuid import uuid4

import pytest

from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.sensory import (
    Senses,
    SensesSnapshot,
    capture_senses_snapshot,
    reduce_senses_snapshot,
)
from dnd.core.events import (
    EventQueue,
    SensoryUpdateEvent,
    SpatialChangeEvent,
    WorldInitializedEvent,
)
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.senses import PerceivedContact, SenseMode, SensesType
from dnd.types.world import LightLevel
from game.app import build_demo_intervals
from game.presentation import Disposition, reduce_interval


def test_three_intervals_are_complete_passive_and_replay_after_reset() -> None:
    intervals = build_demo_intervals()
    startup, opened, closed = intervals
    assert [interval.name for interval in intervals] == ["startup", "open", "close"]
    assert startup.start_cursor == 0
    assert startup.end_cursor == opened.start_cursor
    assert opened.end_cursor == closed.start_cursor
    assert all(
        tuple(row.source_index for row in interval.objective_rows)
        == tuple(range(interval.start_cursor, interval.end_cursor))
        for interval in intervals
    )
    assert all(
        type(event) in {
            WorldInitializedEvent,
            ItemLocationStateEvent,
            SpatialChangeEvent,
            SensoryUpdateEvent,
        }
        for interval in intervals
        for _, event in interval.admitted
    )
    assert all(
        event.context is None and event.combat_log is None and not event.effective_handler_presentations
        for interval in intervals
        for _, event in interval.admitted
    )
    live_index = dict(EventQueue.iter_events_since(0))
    for interval in intervals:
        for index, copied in interval.admitted:
            source = live_index[index]
            assert copied is not source
            assert type(copied) is type(source)
            assert copied == source
            assert (
                copied.uuid,
                copied.lineage_uuid,
                copied.parent_event,
                copied.parent_lineage,
                copied.phase,
            ) == (
                source.uuid,
                source.lineage_uuid,
                source.parent_event,
                source.parent_lineage,
                source.phase,
            )
    for interval in (opened, closed):
        completion_types = {
            row.event_type
            for row in interval.objective_rows
            if row.phase == "completion"
        }
        assert {
            "base_action",
            "spatial_object_changed",
            "spatial_light_changed",
            "sensory_update",
        }.issubset(completion_types)

    live_observer = Entity.get(startup.observer_uuid)
    assert live_observer is not None
    assert live_observer.inventory.items == {}

    live_final = capture_senses_snapshot(live_observer.senses)
    reset_engine_runtime()

    target = None
    target, reduced_startup = reduce_interval(target, startup)
    assert target.world is not None and len(target.tiles) == 4096
    assert target.door_is_open is False
    assert (30, 31) in target.senses.visible
    assert (32, 31) not in target.senses.visible
    assert startup.door_uuid in target.senses.objects
    assert startup.standing_torch_uuid in target.senses.objects
    assert target.standing_torch_state is not None and target.standing_torch_state.is_lit is True

    target, reduced_open = reduce_interval(target, opened)
    assert target.door_is_open is True
    assert (32, 31) in target.senses.visible
    assert target.senses.effective_light_levels[(32, 31)] is LightLevel.DIM_LIGHT

    target, reduced_closed = reduce_interval(target, closed)
    assert target.door_is_open is False
    assert (32, 31) not in target.senses.visible
    assert (32, 31) in target.senses.seen
    assert target.senses == live_final
    assert all(
        len(reduced.dispositions) == len(reduced.envelope.objective_rows)
        for reduced in (reduced_startup, reduced_open, reduced_closed)
    )
    assert any(
        disposition is Disposition.UNSUPPORTED
        for reduced in (reduced_startup, reduced_open, reduced_closed)
        for disposition in reduced.dispositions.values()
    )


def test_wrong_observer_reduction_rejects_without_mutating_seed() -> None:
    startup = build_demo_intervals()[0]
    sensory = next(event for _, event in startup.admitted if type(event) is SensoryUpdateEvent)
    seed = startup.seed_snapshot
    assert seed is not None
    before = (set(seed.visible), set(seed.seen), dict(seed.objects))
    with pytest.raises(ValueError, match="different observer"):
        reduce_senses_snapshot(uuid4(), seed, sensory)
    assert (seed.visible, seed.seen, seed.objects) == before


def test_pure_reduction_removes_before_after_values_and_copies_payloads() -> None:
    observer_uuid = uuid4()
    contact_uuid = uuid4()
    old_contact = PerceivedContact(position=(1, 1), visual=True)
    changed_contact = PerceivedContact(position=(2, 2), visual=True)
    previous = SensesSnapshot(
        position=(0, 0),
        visible={(1, 1)},
        seen={(1, 1)},
        entities={contact_uuid: old_contact},
        objects={contact_uuid: old_contact},
        effective_light_levels={(1, 1): LightLevel.DARKNESS},
        paths_dirty=False,
        passive_perception=10,
        sense_modes_hash=0,
        sense_modes=(),
        visual_access=1,
    )
    event = SensoryUpdateEvent(
        source_entity_uuid=observer_uuid,
        observer_uuid=observer_uuid,
        observer_position=(2, 2),
        observer_position_changed=True,
        cause_event_uuid=uuid4(),
        visible_cells_removed=[(1, 1)],
        visible_cells_added=[(1, 1), (2, 2)],
        seen_cells_added=[(2, 2)],
        effective_light_levels_changed={
            "1,1": LightLevel.BRIGHT_LIGHT.value,
            "2,2": LightLevel.DIM_LIGHT.value,
        },
        entity_contacts_removed={contact_uuid},
        entity_contacts_changed={contact_uuid: changed_contact},
        object_contacts_removed={contact_uuid},
        object_contacts_changed={contact_uuid: changed_contact},
        passive_perception_changed=True,
        passive_perception=14,
        visual_access_changed=True,
        visual_access=0,
        paths_dirty=True,
        use_register=False,
    )

    reduced = reduce_senses_snapshot(observer_uuid, previous, event)

    assert reduced.position == (2, 2)
    assert reduced.visible == {(1, 1), (2, 2)}
    assert reduced.seen == {(1, 1), (2, 2)}
    assert reduced.effective_light_levels == {
        (1, 1): LightLevel.BRIGHT_LIGHT,
        (2, 2): LightLevel.DIM_LIGHT,
    }
    assert reduced.entities == reduced.objects == {contact_uuid: changed_contact}
    assert reduced.entities[contact_uuid] is not changed_contact
    assert reduced.passive_perception == 14
    assert reduced.visual_access == 0
    assert reduced.paths_dirty is True
    assert previous.entities == previous.objects == {contact_uuid: old_contact}


def test_live_replay_preserves_component_owners_until_modes_actually_change() -> None:
    observer_uuid = uuid4()
    source_uuid = uuid4()
    senses = Senses.create(source_entity_uuid=observer_uuid)
    darkvision = SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
    senses.add_sense_mode_source(source_uuid, darkvision)
    visual_access_owner = senses.visual_access

    same = SensoryUpdateEvent(
        source_entity_uuid=observer_uuid,
        observer_uuid=observer_uuid,
        cause_event_uuid=uuid4(),
        sense_modes_changed=True,
        sense_modes=[darkvision],
        visual_access_changed=True,
        visual_access=0,
        use_register=False,
    )
    senses.apply_sensory_update(same)
    assert senses.sense_mode_sources == {source_uuid: darkvision}
    assert senses.visual_access is visual_access_owner
    assert senses._last_visual_access == 0

    blindsight = SenseMode(sense_type=SensesType.BLINDSIGHT, range_feet=30)
    changed = same.model_copy(update={
        "cause_event_uuid": uuid4(),
        "sense_modes": [blindsight],
        "visual_access_changed": False,
        "visual_access": None,
    })
    senses.apply_sensory_update(changed)
    assert senses.sense_mode_sources == {}
    assert senses.get_sense_modes() == [blindsight]
    assert senses.visual_access is visual_access_owner
