"""The selected normal attack owns object targeting, costs and weapon identity."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import Attack, AttackEvent
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, TakeDamageEvent, Trigger
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture
def arena() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 9))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


@pytest.mark.parametrize("slot,armed", [
    (WeaponSlot.MELEE_MAIN, True),
    (WeaponSlot.RANGED_MAIN, True),
    (WeaponSlot.MELEE_MAIN, False),
])
def test_discovered_attack_hits_object_with_selected_source(arena: Game, slot: WeaponSlot, armed: bool) -> None:
    source = Entity.create(uuid4(), "Attacker", config=EntityConfig(position=(2, 3)))
    items = [(build_authored_item("weapon.longbow", source.uuid), WeaponSlot.RANGED_MAIN)]
    if armed:
        items.append((build_authored_item("weapon.longsword", source.uuid), WeaponSlot.MELEE_MAIN))
    source.install_initial_items(tuple(items))
    source.compose_entity()
    setup_standard_actions(source)
    arena.deploy_entity(source, (2, 3))
    source.equipment.activate_weapon_slot(WeaponSlot.RANGED_MAIN)
    stove = build_authored_item("environment.furniture.clay_stove", source.uuid)
    stove.place_on_grid((3, 3))
    Entity.update_all_entities_senses()

    available = get_available_actions(source, legal_only=True)
    assert not any(row.behavior_id == "action.attack_object" for row in available.all_actions)
    row = next(row for row in available.all_actions if row.template_name == f"Attack_{slot.value}")
    target = next(target for target in row.valid_targets if target.target_uuid == stove.uuid)
    hp = stove.get_hp()
    with fixed_dice_faces(18, 1):
        result = execute_by_index(source, row.template_name, target.index, available=available)
    assert isinstance(result, AttackEvent) and not result.canceled
    assert result.weapon_slot is slot
    assert result.weapon_name == ("Unarmed" if not armed else "Longbow" if slot is WeaponSlot.RANGED_MAIN else "Longsword")
    assert stove.get_hp() < hp
    assert source.action_economy.actions.normalized_score == 0


@pytest.mark.parametrize("target_kind", ["object", "creature"])
def test_canceling_damage_roll_application_keeps_hp_but_spends_attack(arena: Game, target_kind: str):
    source = Entity.create(uuid4(), "Attacker", config=EntityConfig(position=(2, 3)))
    sword = build_authored_item("weapon.longsword", source.uuid)
    source.install_initial_items(((sword, WeaponSlot.MELEE_MAIN),))
    source.compose_entity()
    arena.deploy_entity(source, (2, 3))
    if target_kind == "object":
        target = build_authored_item("environment.furniture.clay_stove", source.uuid)
        target.place_on_grid((3, 3))
    else:
        target = Entity.create(uuid4(), "Target", config=EntityConfig(position=(3, 3)))
        target.compose_entity()
        arena.deploy_entity(target, (3, 3))
    Entity.update_all_entities_senses()

    def stop_damage(event, _source):
        return event.cancel(status_message="Damage roll application canceled")

    EventQueue.add_event_handler(EventHandler(name="Stop damage application",
        source_entity_uuid=source.uuid,
        trigger_conditions=[Trigger(event_type=EventType.DAMAGE_ROLL_RESULT, event_phase=EventPhase.EFFECT)],
        event_processor=stop_damage))
    before = target.get_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(18, 2):
        result = Attack(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert result is not None and result.canceled
    assert target.get_hp() == before
    assert source.action_economy.actions.normalized_score == 0
    assert not any(isinstance(event, TakeDamageEvent) for _, event in EventQueue.iter_events_since(cursor))
