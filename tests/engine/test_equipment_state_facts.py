"""Accepted equipment operations publish the native stance needed by replay."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem
from dnd.blocks.equipment import EquipmentEvent
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import EquipmentSlot, WeaponSet, WeaponSlot
from dnd.core.events import EntityCreatedEvent, Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def reset_runtime() -> Iterator[None]:
    reset_engine_runtime(grid_size=(3, 3))
    yield
    reset_engine_runtime()


def _compose(
    loadout: tuple[tuple[str, EquipmentSlot | None], ...],
) -> tuple[Entity, EntityCreatedEvent, dict[str, BaseItem]]:
    actor = Entity.create(uuid4(), "Equipment history", config=EntityConfig(position=(1, 1)))
    items = {item_id: build_authored_item(item_id, actor.uuid) for item_id, _ in loadout}
    actor.install_initial_items(tuple((items[item_id], slot) for item_id, slot in loadout))
    birth = actor.compose_entity()
    Game().deploy_entity(actor, (1, 1))
    return actor, birth, items


def _completion_facts(cursor: int) -> tuple[EquipmentEvent, ...]:
    return tuple(event for _, event in EventQueue.iter_events_since(cursor)
                 if isinstance(event, EquipmentEvent) and event.phase is EventPhase.COMPLETION)


@pytest.mark.parametrize(("loadout", "expected"), (
    ((), WeaponSet.NONE),
    ((("weapon.shortsword", WeaponSlot.MELEE_MAIN),), WeaponSet.MELEE),
    ((("weapon.longbow", WeaponSlot.RANGED_MAIN),), WeaponSet.RANGED),
))
def test_birth_records_composed_weapon_stance(
    loadout: tuple[tuple[str, EquipmentSlot | None], ...], expected: WeaponSet,
) -> None:
    actor, birth, _ = _compose(loadout)
    assert birth.active_weapon_set is actor.equipment.active_weapon_set is expected
    assert birth.model_dump(mode="json")["active_weapon_set"] == expected.value


def test_equipment_history_records_each_accepted_stance_without_recomputing_it() -> None:
    actor, birth, items = _compose((
        ("weapon.shortsword", None), ("weapon.longbow", None), ("weapon.dagger", None),
    ))
    recorded: list[tuple[EquipmentEvent, WeaponSet]] = []
    operations = (
        ("weapon.shortsword", WeaponSlot.MELEE_MAIN, WeaponSet.MELEE),
        ("weapon.longbow", WeaponSlot.RANGED_MAIN, WeaponSet.MELEE),
        (None, WeaponSlot.MELEE_MAIN, WeaponSet.RANGED),
        ("weapon.dagger", WeaponSlot.MELEE_MAIN, WeaponSet.RANGED),
        ("weapon.shortsword", WeaponSlot.MELEE_MAIN, WeaponSet.RANGED),
        (None, WeaponSlot.RANGED_MAIN, WeaponSet.MELEE),
        (None, WeaponSlot.MELEE_MAIN, WeaponSet.NONE),
    )
    for item_id, slot, expected in operations:
        cursor = EventQueue.event_cursor()
        if item_id is None:
            assert actor.unequip_item(slot) is not None
        else:
            assert actor.equip_item(items[item_id].uuid, slot)
        facts = _completion_facts(cursor)
        assert facts
        assert actor.equipment.active_weapon_set is expected
        for fact in facts:
            assert fact.active_weapon_set_after is expected
            assert fact.model_dump(mode="json")["active_weapon_set_after"] == expected.value
            recorded.append((fact, expected))
        for _, event in EventQueue.iter_events_since(cursor):
            if isinstance(event, EquipmentEvent) and event.phase is not EventPhase.COMPLETION:
                assert event.active_weapon_set_after is None
    assert birth.active_weapon_set is WeaponSet.NONE
    assert all(fact.active_weapon_set_after is expected for fact, expected in recorded)


def test_destroying_active_equipment_records_surviving_stance() -> None:
    actor, _, items = _compose((
        ("weapon.shortsword", WeaponSlot.MELEE_MAIN),
        ("weapon.longbow", WeaponSlot.RANGED_MAIN),
    ))
    cursor = EventQueue.event_cursor()
    items["weapon.shortsword"].destroy()
    fact, = _completion_facts(cursor)
    assert fact.item_uuid == items["weapon.shortsword"].uuid
    assert fact.active_weapon_set_after is actor.equipment.active_weapon_set is WeaponSet.RANGED
    assert actor.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is None


@pytest.mark.parametrize("equipping", (True, False))
def test_canceled_equipment_operation_emits_no_accepted_stance(equipping: bool) -> None:
    actor, _, items = _compose((
        ("weapon.shortsword", WeaponSlot.MELEE_MAIN),
        ("weapon.longbow", WeaponSlot.RANGED_MAIN),
        ("weapon.dagger", None),
    ))

    def cancel(event: Event, _source_entity_uuid: object) -> Event:
        return event.cancel(status_message="Equipment remains unchanged")

    actor.add_event_handler(EventHandler(
        name="Reject equipment transition", source_entity_uuid=actor.uuid,
        validation_only=True, event_processor=cancel,
        trigger_conditions=[Trigger(
            event_type=EventType.WEAPON_EQUIP if equipping else EventType.WEAPON_UNEQUIP,
            event_phase=EventPhase.EXECUTION, event_source_entity_uuid=actor.uuid,
        )],
    ))
    cursor = EventQueue.event_cursor()
    if equipping:
        assert not actor.equip_item(items["weapon.dagger"].uuid, WeaponSlot.MELEE_MAIN)
    else:
        assert actor.unequip_item(WeaponSlot.MELEE_MAIN) is None
    assert not _completion_facts(cursor)
    assert actor.equipment.active_weapon_set is WeaponSet.MELEE
    assert actor.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is items["weapon.shortsword"]
