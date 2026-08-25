"""Completion facts required to replay inventory and equipment state."""
from dnd.types.materials import Material, TileSurface

from uuid import uuid4

from dnd.actions.operations import execute_use_action
from dnd.blocks.base_item import (
    BaseItem,
)
from dnd.core.events.item_events import (
    ItemChargeConsumptionEvent,
    ItemLocationStateEvent,
)
from dnd.core.events.item_events import (
    EquipmentEvent,
    ShieldUnequipEvent,
    WeaponEquipEvent,
)
from dnd.blocks.equipment import (
    Shield,
    Weapon,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_block import BaseBlock
from dnd.types.equipment import WeaponSlot
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.types.items import ItemLocation
from dnd.presentation import ItemPresentationKind
from dnd.types.damage import DamageType
from dnd.entities.entity import Entity
from dnd.items.armors import SHIELD_RECIPE
from dnd.items.consumables import (
    HEALING_POTION_RECIPE,
    healing_potion_recipe,
)
from dnd.items.weapons import GREATSWORD_RECIPE
from tests.engine.support import reset_combat_state, set_hp


def _fresh_entity(name: str = "Fact Keeper") -> Entity:
    """Create one minimal entity on a fresh engine runtime."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 4, 3, surface=TileSurface(base_material=Material.STONE))
    return Entity.create(source_entity_uuid=uuid4(), name=name)


def _completion_facts_since(cursor: int) -> list[Event]:
    """Return stored completion versions appended after ``cursor``."""
    return [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if event.phase is EventPhase.COMPLETION
    ]


def test_equipment_displacement_publishes_slot_then_inventory_and_ac_facts() -> None:
    """A two-handed equip is replayable without fetching a new equipment snapshot."""
    entity = _fresh_entity()
    shield = materialize_item(
        SHIELD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    greatsword = materialize_item(
        GREATSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert entity.loot_item(shield)
    assert entity.loot_item(greatsword)
    base_ac = entity.ac_bonus().normalized_score

    assert entity.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
    assert entity.ac_bonus().normalized_score == base_ac + 2
    cursor = EventQueue.event_cursor()

    assert entity.equip_item(greatsword.uuid, WeaponSlot.MELEE_MAIN)

    facts = [
        event
        for event in _completion_facts_since(cursor)
        if isinstance(event, (EquipmentEvent, ItemLocationStateEvent))
    ]
    assert [type(event) for event in facts] == [
        ShieldUnequipEvent,
        WeaponEquipEvent,
        ItemLocationStateEvent,
        ItemLocationStateEvent,
    ]

    equipped_fact = facts[2]
    displaced_fact = facts[3]
    assert isinstance(equipped_fact, ItemLocationStateEvent)
    assert isinstance(displaced_fact, ItemLocationStateEvent)
    assert equipped_fact.item_state.item_uuid == greatsword.uuid
    assert equipped_fact.location is ItemLocation.EQUIPMENT
    assert equipped_fact.equipment_slot is WeaponSlot.MELEE_MAIN
    assert equipped_fact.entity_armor_class_after == base_ac
    assert displaced_fact.item_state.item_uuid == shield.uuid
    assert displaced_fact.location is ItemLocation.INVENTORY
    assert displaced_fact.entity_armor_class_after == base_ac
    assert entity.inventory.has_item(shield.uuid)
    assert not entity.inventory.has_item(greatsword.uuid)


def test_pickup_drop_and_stack_merge_publish_exact_inventory_state() -> None:
    """Pickup/drop facts include membership and both sides of a stack merge."""
    entity = _fresh_entity()
    item = BaseItem(source_entity_uuid=uuid4(), name="Silver Key")
    item.place_on_grid((1, 0))

    cursor = EventQueue.event_cursor()
    assert entity.loot_item(item)
    pickup_facts = [
        event
        for event in _completion_facts_since(cursor)
        if isinstance(event, ItemLocationStateEvent)
    ]
    assert len(pickup_facts) == 1
    assert pickup_facts[0].item_state.item_uuid == item.uuid
    assert pickup_facts[0].location is ItemLocation.INVENTORY
    assert pickup_facts[0].item_state.stack_count == 1
    assert pickup_facts[0].item_state.name == "Silver Key"
    assert pickup_facts[0].item_state.visual_item_name == "Silver Key"
    assert pickup_facts[0].item_state.item_kind is ItemPresentationKind.ITEM

    cursor = EventQueue.event_cursor()
    assert entity.drop_item(item.uuid, (0, 1)) is item
    drop_facts = [
        event
        for event in _completion_facts_since(cursor)
        if isinstance(event, ItemLocationStateEvent)
    ]
    assert len(drop_facts) == 1
    assert drop_facts[0].item_state.item_uuid == item.uuid
    assert drop_facts[0].location is ItemLocation.FLOOR
    assert drop_facts[0].world_placement is not None
    assert drop_facts[0].world_placement.position == (0, 1)
    assert drop_facts[0].world_placement == get_map().get_object_placement(item.uuid)

    existing = materialize_item(
        HEALING_POTION_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    incoming = materialize_item(
        HEALING_POTION_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    existing.stack_count = 8
    incoming.stack_count = 2
    assert entity.loot_item(existing)
    incoming.place_on_grid((1, 0))
    cursor = EventQueue.event_cursor()

    assert entity.loot_item(incoming)

    merge_facts = [
        event
        for event in _completion_facts_since(cursor)
        if isinstance(event, ItemLocationStateEvent)
    ]
    assert len(merge_facts) == 2
    assert merge_facts[0].item_state.item_uuid == existing.uuid
    assert merge_facts[0].location is ItemLocation.INVENTORY
    assert merge_facts[0].item_state.stack_count == 10
    assert merge_facts[0].item_state.item_kind is ItemPresentationKind.USABLE
    assert merge_facts[1].item_state.item_uuid == incoming.uuid
    assert merge_facts[1].location is ItemLocation.MERGED
    assert merge_facts[1].item_state.stack_count == 0
    assert merge_facts[1].merged_into_item_uuid == existing.uuid
    assert BaseBlock.get(incoming.uuid) is None


def test_destroyed_equipment_and_consumables_publish_ordered_removal_facts() -> None:
    """Destruction removes slot/membership before exposing the final aggregate AC."""
    entity = _fresh_entity()
    shield = materialize_item(
        SHIELD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    shield.is_targetable = True
    shield.health = BaseItem.create_item_health(entity.uuid, hp=4)
    base_ac = entity.ac_bonus().normalized_score
    assert entity.loot_item(shield)
    assert entity.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
    assert entity.ac_bonus().normalized_score == base_ac + 2
    cursor = EventQueue.event_cursor()

    assert shield.receive_damage(99, DamageType.BLUDGEONING, entity.uuid) > 0

    destruction_facts = [
        event
        for event in _completion_facts_since(cursor)
        if isinstance(event, (EquipmentEvent, ItemLocationStateEvent))
    ]
    assert [type(event) for event in destruction_facts] == [
        ShieldUnequipEvent,
        ItemLocationStateEvent,
    ]
    destroyed_fact = destruction_facts[1]
    assert isinstance(destroyed_fact, ItemLocationStateEvent)
    assert destroyed_fact.item_state.item_uuid == shield.uuid
    assert destroyed_fact.location is ItemLocation.DESTROYED
    assert destroyed_fact.item_state.stack_count == 0
    assert destroyed_fact.item_state.item_kind is ItemPresentationKind.SHIELD
    assert destroyed_fact.item_state.shield_ac_bonus == 2
    assert destroyed_fact.entity_armor_class_after == base_ac

    potion = materialize_item(
        healing_potion_recipe(heal_amount=4),
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert entity.loot_item(potion)
    set_hp(entity, 1)
    cursor = EventQueue.event_cursor()

    result = execute_use_action(entity, potion.uuid, "Drink Potion")

    assert result is not None and not result.canceled
    consumption_facts = [
        event
        for event in _completion_facts_since(cursor)
        if isinstance(event, (ItemLocationStateEvent, ItemChargeConsumptionEvent))
    ]
    assert [type(event) for event in consumption_facts] == [
        ItemLocationStateEvent,
        ItemChargeConsumptionEvent,
    ]
    removal_fact = consumption_facts[0]
    charge_fact = consumption_facts[1]
    assert isinstance(removal_fact, ItemLocationStateEvent)
    assert isinstance(charge_fact, ItemChargeConsumptionEvent)
    assert removal_fact.item_state.item_uuid == potion.uuid
    assert removal_fact.location is ItemLocation.DESTROYED
    assert removal_fact.item_state.stack_count == 0
    assert charge_fact.item_uuid == potion.uuid
    assert charge_fact.item_destroyed is True
    assert removal_fact.parent_lineage == charge_fact.lineage_uuid


def test_canceled_equip_publishes_no_item_location_fact() -> None:
    """A rejected equipment proposal cannot produce a false completion fact."""
    entity = _fresh_entity()
    shield = materialize_item(
        SHIELD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    assert entity.loot_item(shield)

    def cancel_equip(event: Event, _source_entity_uuid) -> Event:
        return event.cancel(status_message="Rejected by test")

    entity.add_event_handler(
        EventHandler(
            name="Reject shield equip",
            source_entity_uuid=entity.uuid,
            validation_only=True,
            event_processor=cancel_equip,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SHIELD_EQUIP,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=entity.uuid,
                )
            ],
        )
    )
    cursor = EventQueue.event_cursor()

    assert entity.equip_item(shield.uuid, WeaponSlot.MELEE_OFF) is False

    assert not any(
        isinstance(event, ItemLocationStateEvent)
        for event in _completion_facts_since(cursor)
    )
    assert entity.inventory.has_item(shield.uuid)
    assert entity.equipment.weapon_melee_off is None
