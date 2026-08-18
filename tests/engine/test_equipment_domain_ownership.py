"""Ownership contracts for equipment slot policy and aggregate delegation."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.blocks.equipment import (
    BodyArmor,
    Ring,
    Shield,
    Weapon,
)
from dnd.blocks.base_item import (
    BaseItem,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.classes.rage import Raging
from dnd.types.equipment import (
    ArmorType,
    BodyPart,
    RingSlot,
    WeaponSlot,
)
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.items.armors import CHAIN_MAIL_RECIPE, SHIELD_RECIPE
from dnd.items.weapons import (
    GREATSWORD_RECIPE,
    SHORTBOW_RECIPE,
    SHORTSWORD_RECIPE,
)
from tests.engine.support import create_test_monster
from dnd.spells.abjuration import (
    MageArmorCondition,
)
from tests.engine.support import reset_combat_state


def test_equippable_items_declare_compatible_and_default_slots() -> None:
    """Concrete gear owns its slot policy; rings intentionally have no default."""
    owner_uuid = uuid4()
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    bow = materialize_item(
        SHORTBOW_RECIPE,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    greatsword = materialize_item(
        GREATSWORD_RECIPE,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    shield = materialize_item(
        SHIELD_RECIPE,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    armor = materialize_item(
        CHAIN_MAIL_RECIPE,
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    ring = Ring(source_entity_uuid=owner_uuid, type=ArmorType.CLOTH)

    assert sword.compatible_equipment_slots() == (
        WeaponSlot.MELEE_MAIN,
        WeaponSlot.MELEE_OFF,
    )
    assert sword.default_equipment_slot() == WeaponSlot.MELEE_MAIN
    assert sword.equipment_event_type(equipping=True) == EventType.WEAPON_EQUIP
    assert sword.equipment_event_type(equipping=False) == EventType.WEAPON_UNEQUIP
    assert bow.compatible_equipment_slots() == (WeaponSlot.RANGED_MAIN,)
    assert bow.default_equipment_slot() == WeaponSlot.RANGED_MAIN
    assert greatsword.occupied_equipment_slots(WeaponSlot.MELEE_MAIN) == frozenset({
        WeaponSlot.MELEE_MAIN,
        WeaponSlot.MELEE_OFF,
    })
    assert bow.occupied_equipment_slots(WeaponSlot.RANGED_MAIN) == frozenset({
        WeaponSlot.RANGED_MAIN,
    })
    assert shield.compatible_equipment_slots() == (WeaponSlot.MELEE_OFF,)
    assert shield.default_equipment_slot() == WeaponSlot.MELEE_OFF
    assert shield.equipment_event_type(equipping=True) == EventType.SHIELD_EQUIP
    assert armor.compatible_equipment_slots() == (BodyPart.BODY,)
    assert armor.default_equipment_slot() == BodyPart.BODY
    assert armor.equipment_event_type(equipping=False) == EventType.ARMOR_UNEQUIP
    assert ring.compatible_equipment_slots() == (RingSlot.LEFT, RingSlot.RIGHT)
    assert ring.default_equipment_slot() is None


def test_equipment_resolves_defaults_but_requires_an_explicit_ring_slot() -> None:
    """Equipment, rather than Entity or transport code, resolves optional slots."""
    reset_combat_state()
    entity = create_test_monster("monster.skeleton", name="Equipment Owner", position=(0, 0), darkvision=False)
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    ring = Ring(source_entity_uuid=entity.uuid, type=ArmorType.CLOTH)
    ordinary_item = BaseItem(source_entity_uuid=entity.uuid, name="Keepsake")
    assert entity.inventory.add_item(sword)
    assert entity.inventory.add_item(ring)
    assert entity.inventory.add_item(ordinary_item)

    assert entity.is_inventory_item_equippable(sword.uuid)
    assert not entity.is_inventory_item_equippable(ordinary_item.uuid)
    assert not entity.is_inventory_item_equippable(uuid4())

    assert entity.equip_item(sword.uuid)
    assert entity.equipment.weapon_melee_main is sword

    with pytest.raises(ValueError, match="explicit equipment slot"):
        entity.equip_item(ring.uuid)

    assert entity.inventory.has_item(ring.uuid)
    assert entity.equip_item(ring.uuid, RingSlot.LEFT)
    assert entity.equipment.ring_left is ring


def test_conflict_cancellation_keeps_the_equipment_transaction_atomic() -> None:
    """A canceled displacement cannot leave a partially changed loadout."""
    reset_combat_state()
    entity = create_test_monster("monster.skeleton", name="Atomic Loadout", position=(0, 0), darkvision=False)
    original_weapon = entity.equipment.weapon_melee_main
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
    assert original_weapon is not None
    assert entity.inventory.add_item(shield)
    assert entity.inventory.add_item(greatsword)
    assert entity.equip_item(shield.uuid)

    def cancel_shield_removal(event: Event, _source_entity_uuid) -> Event:
        return event.cancel(status_message="Shield remains equipped")

    entity.add_event_handler(EventHandler(
        name="Keep Shield Equipped",
        source_entity_uuid=entity.uuid,
        validation_only=True,
        event_processor=cancel_shield_removal,
        trigger_conditions=[Trigger(
            event_type=EventType.SHIELD_UNEQUIP,
            event_phase=EventPhase.EXECUTION,
            event_source_entity_uuid=entity.uuid,
        )],
    ))

    assert not entity.equip_item(greatsword.uuid)
    assert entity.equipment.weapon_melee_main is original_weapon
    assert entity.equipment.weapon_melee_off is shield
    assert original_weapon.is_equipped
    assert shield.is_equipped
    assert entity.inventory.has_item(greatsword.uuid)
    assert not greatsword.is_equipped


def test_canceled_multislot_equip_has_no_public_events_or_location_mutation() -> None:
    """Rejected conflict preflight is invisible and leaves every owner field intact."""
    reset_combat_state()
    entity = create_test_monster("monster.skeleton", name="Atomic Observer", position=(0, 0), darkvision=False)
    original_weapon = entity.equipment.weapon_melee_main
    shield = materialize_item(
        SHIELD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    foreign_owner_uuid = uuid4()
    greatsword = materialize_item(
        GREATSWORD_RECIPE,
        foreign_owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert original_weapon is not None
    assert entity.inventory.add_item(shield)
    assert entity.equip_item(shield.uuid)

    source_snapshot = (
        greatsword.source_entity_uuid,
        greatsword.attack_bonus.source_entity_uuid,
        greatsword.attack_bonus.self_static.source_entity_uuid,
        greatsword.owner_uuid,
        greatsword.stored_in_uuid,
    )
    observed_events: list[Event] = []
    validation_counts = {"main": 0, "shield": 0}

    def accept_main_removal(event: Event, _source_entity_uuid) -> Event:
        validation_counts["main"] += 1
        return event

    def reject_shield_removal(event: Event, _source_entity_uuid) -> Event:
        validation_counts["shield"] += 1
        return event.cancel(status_message="Shield remains equipped")

    entity.add_event_handler(EventHandler(
        name="Observe Main-Hand Validation",
        source_entity_uuid=entity.uuid,
        validation_only=True,
        event_processor=accept_main_removal,
        trigger_conditions=[Trigger(
            event_type=EventType.WEAPON_UNEQUIP,
            event_phase=EventPhase.EXECUTION,
            event_source_entity_uuid=entity.uuid,
        )],
    ))
    entity.add_event_handler(EventHandler(
        name="Reject Shield Validation",
        source_entity_uuid=entity.uuid,
        validation_only=True,
        event_processor=reject_shield_removal,
        trigger_conditions=[Trigger(
            event_type=EventType.SHIELD_UNEQUIP,
            event_phase=EventPhase.EXECUTION,
            event_source_entity_uuid=entity.uuid,
        )],
    ))

    equipment_event_types = {
        EventType.WEAPON_EQUIP,
        EventType.WEAPON_UNEQUIP,
        EventType.SHIELD_EQUIP,
        EventType.SHIELD_UNEQUIP,
        EventType.ARMOR_EQUIP,
        EventType.ARMOR_UNEQUIP,
    }

    def observe_equipment_event(event: Event) -> None:
        if event.event_type in equipment_event_types:
            observed_events.append(event)

    EventQueue.add_on_event_callback(observe_equipment_event)
    cursor = EventQueue.event_cursor()
    try:
        assert not entity.equipment.equip(greatsword, WeaponSlot.MELEE_MAIN)
    finally:
        EventQueue.remove_on_event_callback(observe_equipment_event)

    assert validation_counts == {"main": 1, "shield": 1}
    assert observed_events == []
    assert [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type in equipment_event_types
    ] == []
    assert entity.equipment.weapon_melee_main is original_weapon
    assert entity.equipment.weapon_melee_off is shield
    assert original_weapon.is_equipped
    assert shield.is_equipped
    assert not greatsword.is_equipped
    assert (
        greatsword.source_entity_uuid,
        greatsword.attack_bonus.source_entity_uuid,
        greatsword.attack_bonus.self_static.source_entity_uuid,
        greatsword.owner_uuid,
        greatsword.stored_in_uuid,
    ) == source_snapshot


def test_successful_multislot_equip_publishes_one_complete_lifecycle_per_step() -> None:
    """Accepted gear transactions publish each committed transition exactly once."""
    reset_combat_state()
    entity = create_test_monster("monster.skeleton", name="Atomic Commit", position=(0, 0), darkvision=False)
    original_weapon = entity.equipment.weapon_melee_main
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
    assert original_weapon is not None
    assert entity.inventory.add_item(shield)
    assert entity.equip_item(shield.uuid)

    equip_validation_calls = 0

    def accept_equip(event: Event, _source_entity_uuid) -> Event:
        nonlocal equip_validation_calls
        equip_validation_calls += 1
        return event

    entity.add_event_handler(EventHandler(
        name="Accept Atomic Equip",
        source_entity_uuid=entity.uuid,
        validation_only=True,
        event_processor=accept_equip,
        trigger_conditions=[Trigger(
            event_type=EventType.WEAPON_EQUIP,
            event_phase=EventPhase.EXECUTION,
            event_source_entity_uuid=entity.uuid,
        )],
    ))

    cursor = EventQueue.event_cursor()
    assert entity.equipment.equip(greatsword, WeaponSlot.MELEE_MAIN)
    assert equip_validation_calls == 1

    relevant_item_uuids = {original_weapon.uuid, shield.uuid, greatsword.uuid}
    histories: dict[tuple[EventType, object], list[EventPhase]] = {}
    published_events: list[Event] = []
    for _, event in EventQueue.iter_events_since(cursor):
        item_uuid = getattr(event, "item_uuid", None)
        if item_uuid not in relevant_item_uuids:
            continue
        published_events.append(event)
        histories.setdefault((event.event_type, item_uuid), []).append(event.phase)

    assert [event.timestamp for event in published_events] == sorted(
        event.timestamp for event in published_events
    )
    assert histories == {
        (EventType.WEAPON_UNEQUIP, original_weapon.uuid): [
            EventPhase.DECLARATION,
            EventPhase.EXECUTION,
            EventPhase.EFFECT,
            EventPhase.COMPLETION,
        ],
        (EventType.SHIELD_UNEQUIP, shield.uuid): [
            EventPhase.DECLARATION,
            EventPhase.EXECUTION,
            EventPhase.EFFECT,
            EventPhase.COMPLETION,
        ],
        (EventType.WEAPON_EQUIP, greatsword.uuid): [
            EventPhase.DECLARATION,
            EventPhase.EXECUTION,
            EventPhase.EFFECT,
            EventPhase.COMPLETION,
        ],
    }


def test_transaction_rejects_impure_execution_handlers_before_publication() -> None:
    """Transactional execution hooks must explicitly obey the pure guard contract."""
    reset_combat_state()
    entity = create_test_monster("monster.skeleton", name="Guard Contract", position=(0, 0), darkvision=False)
    original_weapon = entity.equipment.weapon_melee_main
    replacement = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert original_weapon is not None

    def undeclared_execution_handler(event: Event, _source_entity_uuid) -> Event:
        return event

    entity.add_event_handler(EventHandler(
        name="Impure Equipment Execution Hook",
        source_entity_uuid=entity.uuid,
        event_processor=undeclared_execution_handler,
        trigger_conditions=[Trigger(
            event_type=EventType.WEAPON_EQUIP,
            event_phase=EventPhase.EXECUTION,
            event_source_entity_uuid=entity.uuid,
        )],
    ))
    cursor = EventQueue.event_cursor()

    with pytest.raises(RuntimeError, match="validation_only"):
        entity.equipment.equip(replacement, WeaponSlot.MELEE_MAIN)

    assert EventQueue.event_cursor() == cursor
    assert entity.equipment.weapon_melee_main is original_weapon
    assert original_weapon.is_equipped
    assert not replacement.is_equipped


def test_validation_only_handler_cannot_emit_a_child_event() -> None:
    """Preflight blocks attempted event publication before it reaches the registry."""
    reset_combat_state()
    entity = create_test_monster("monster.skeleton", name="Guard Isolation", position=(0, 0), darkvision=False)
    original_weapon = entity.equipment.weapon_melee_main
    replacement = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert original_weapon is not None

    def emitting_validator(event: Event, _source_entity_uuid) -> Event:
        Event(
            name="Forbidden Preflight Child",
            event_type=EventType.BASE_ACTION,
            source_entity_uuid=entity.uuid,
        )
        return event

    entity.add_event_handler(EventHandler(
        name="Emitting Equipment Validator",
        source_entity_uuid=entity.uuid,
        validation_only=True,
        event_processor=emitting_validator,
        trigger_conditions=[Trigger(
            event_type=EventType.WEAPON_EQUIP,
            event_phase=EventPhase.EXECUTION,
            event_source_entity_uuid=entity.uuid,
        )],
    ))
    cursor = EventQueue.event_cursor()

    with pytest.raises(RuntimeError, match="cannot publish events during preflight"):
        entity.equipment.equip(replacement, WeaponSlot.MELEE_MAIN)

    assert EventQueue.event_cursor() == cursor
    assert entity.equipment.weapon_melee_main is original_weapon
    assert original_weapon.is_equipped
    assert not replacement.is_equipped


def test_committed_armor_effect_handlers_observe_the_final_loadout() -> None:
    """Reactive gear rules run at EFFECT after the whole loadout is committed."""
    reset_combat_state()
    entity = create_test_monster("monster.skeleton", name="Armor Effect Owner", position=(0, 0), darkvision=False)
    chain_mail = materialize_item(
        CHAIN_MAIL_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    entity.equipment.unequip(BodyPart.BODY)
    assert entity.equipment.body_armor is None

    assert entity.add_condition(MageArmorCondition(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )) is not None
    assert entity.add_condition(Raging(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )) is not None
    assert "Mage Armor" in entity.active_conditions
    assert "Raging" in entity.active_conditions

    committed_state_seen: list[bool] = []

    def observe_committed_armor(event: Event, _source_entity_uuid) -> Event:
        committed_state_seen.append(entity.equipment.body_armor is chain_mail)
        return event

    entity.add_event_handler(EventHandler(
        name="Observe Committed Armor",
        source_entity_uuid=entity.uuid,
        event_processor=observe_committed_armor,
        trigger_conditions=[Trigger(
            event_type=EventType.ARMOR_EQUIP,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=entity.uuid,
        )],
    ))

    assert entity.equipment.equip(chain_mail, BodyPart.BODY)

    assert committed_state_seen == [True]
    assert entity.equipment.body_armor is chain_mail
    assert "Mage Armor" not in entity.active_conditions
    assert "Raging" not in entity.active_conditions


def test_equipment_groups_inventory_projection_from_declared_slot_policy() -> None:
    """Grouped discovery uses the same authoritative policy as equip validation."""
    reset_combat_state()
    entity = create_test_monster("monster.skeleton", name="Loadout Owner", position=(0, 0), darkvision=False)
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    shield = materialize_item(
        SHIELD_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Shield,
    )
    armor = materialize_item(
        CHAIN_MAIL_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=BodyArmor,
    )
    ring = Ring(source_entity_uuid=entity.uuid, type=ArmorType.CLOTH, name="Copper Ring")
    for item in (sword, shield, armor, ring):
        assert entity.inventory.add_item(item)

    grouped = entity.get_equippable_items()

    assert {entry["item_name"] for entry in grouped["weapon_melee_main"]} == {
        sword.name,
    }
    assert {entry["item_name"] for entry in grouped["weapon_melee_off"]} == {
        sword.name,
        shield.name,
    }
    assert [entry["item_name"] for entry in grouped["body_armor"]] == [armor.name]
    assert [entry["item_name"] for entry in grouped["ring_left"]] == [ring.name]
    assert [entry["item_name"] for entry in grouped["ring_right"]] == [ring.name]


def test_equipment_projection_reports_every_authoritative_footprint_conflict() -> None:
    """Discovery and commit use one conflict calculation, including two-hand reach."""
    reset_combat_state()
    entity = create_test_monster("monster.skeleton", name="Footprint Projection", position=(0, 0), darkvision=False)
    original_weapon = entity.equipment.weapon_melee_main
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
    assert original_weapon is not None
    assert entity.inventory.add_item(shield)
    assert entity.inventory.add_item(greatsword)
    assert entity.equip_item(shield.uuid)

    grouped = entity.get_equippable_items()
    greatsword_entry = next(
        entry
        for entry in grouped["weapon_melee_main"]
        if entry["item_uuid"] == str(greatsword.uuid)
    )
    assert greatsword_entry["displaced_items"] == [
        {
            "item_uuid": str(original_weapon.uuid),
            "item_name": original_weapon.name,
            "slot": WeaponSlot.MELEE_MAIN.value,
        },
        {
            "item_uuid": str(shield.uuid),
            "item_name": shield.name,
            "slot": WeaponSlot.MELEE_OFF.value,
        },
    ]

    assert entity.equip_item(greatsword.uuid, WeaponSlot.MELEE_MAIN)
    grouped = entity.get_equippable_items()
    shield_entry = next(
        entry
        for entry in grouped["weapon_melee_off"]
        if entry["item_uuid"] == str(shield.uuid)
    )
    assert shield_entry["displaced_items"] == [
        {
            "item_uuid": str(greatsword.uuid),
            "item_name": greatsword.name,
            "slot": WeaponSlot.MELEE_MAIN.value,
        }
    ]


def test_entity_has_no_concrete_gear_policy_or_local_import_workaround() -> None:
    """Entity knows the Equipment component and neutral slots, not gear classes."""
    entity_path = Path(__file__).resolve().parents[2] / "dnd" / "entity.py"
    tree = ast.parse(entity_path.read_text(encoding="utf-8"), filename=str(entity_path))
    forbidden_names = {"Armor", "Ring", "Shield", "Weapon", "slot_mapping"}

    referenced_forbidden_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in forbidden_names
    }
    assert referenced_forbidden_names == set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            local_imports = [
                descendant
                for descendant in ast.walk(node)
                if isinstance(descendant, (ast.Import, ast.ImportFrom))
            ]
            assert local_imports == [], f"local import in Entity.{node.name}"
