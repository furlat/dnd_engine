"""The selected normal attack owns object targeting, costs and weapon identity."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import Attack, AttackEvent
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.base_item import BaseItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_authored_door
from dnd.content.items.world_prop_builders import build_world_prop
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, TakeDamageEvent, Trigger
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection


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


def _place(kind: str, position: tuple[int, int], owner) -> BaseItem:
    if kind == "stove":
        item = build_authored_item("environment.furniture.clay_stove", owner)
        item.place_on_grid(position)
    elif kind == "bed":  # two floor spaces; rotated north, the second is one cell north (+y) of `position`
        item = build_world_prop("environment.furniture.bed", source_entity_uuid=owner)
        item.place_on_grid(position, orientation=CardinalDirection.NORTH)
    elif kind == "door":  # on the east edge of `position`: contacted from either side of that edge
        item = build_authored_door("environment.door.desert_c7")
        item.place_on_grid(position, boundary_direction=CardinalDirection.EAST)
    else:
        raise ValueError(f"Unknown object kind {kind}")
    return item


@pytest.mark.parametrize("slot,attacker,kind,position,listed", [
    (WeaponSlot.MELEE_MAIN, (2, 3), "stove", (3, 3), True),
    (WeaponSlot.MELEE_MAIN, (1, 3), "bed", (3, 2), False),
    # The anchor is 10 ft off; the near support or the edge's far side is 5 ft off.
    (WeaponSlot.MELEE_MAIN, (3, 5), "bed", (3, 3), True),
    (WeaponSlot.MELEE_MAIN, (5, 2), "door", (3, 2), True),
    (WeaponSlot.RANGED_MAIN, (1, 3), "bed", (3, 2), True),
], ids=["adjacent", "beyond reach", "near support", "door far side", "ranged"])
def test_attack_lists_the_objects_its_weapon_reaches(arena: Game, slot, attacker, kind, position, listed):
    source = Entity.create(uuid4(), "Attacker", config=EntityConfig(position=attacker))
    source.install_initial_items(((build_authored_item("weapon.longbow", source.uuid), WeaponSlot.RANGED_MAIN),
        (build_authored_item("weapon.longsword", source.uuid), WeaponSlot.MELEE_MAIN)))
    source.compose_entity()
    setup_standard_actions(source)
    arena.deploy_entity(source, attacker)
    item = _place(kind, position, source.uuid)
    Entity.update_all_entities_senses()
    assert item.uuid in source.senses.objects

    row = next(row for row in get_available_actions(source).all_actions if row.template_name == f"Attack_{slot.value}")
    assert (item.uuid in {target.target_uuid for target in row.valid_targets}) is listed
