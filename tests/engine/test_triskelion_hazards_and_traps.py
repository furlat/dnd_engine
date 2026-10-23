"""Triskelion hazards and container traps, through movement, actions and the map."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import Move
from dnd.actions_functional import execute_available_action, setup_standard_actions
from dnd.blocks.base_item import BaseItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_actions import AvailableActionInfo
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.modifiers import AdvantageStatus
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.core.creature_types import DamageType
from dnd.items.container_traps import build_trap_disarm_toolkit, install_container_trap
from dnd.items.environment_interactables import StorageChest
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import (
    materialize_electric_floor, materialize_gray_mold, materialize_spike_trap_condition,
)
from dnd.spells.abjuration import LesserRestoration
from dnd.spells.conjuration import Daylight, materialize_authored_darkness
from dnd.types.senses import OBSCUREMENT_SETS, OpticalObscurement
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


@pytest.fixture
def arena() -> Iterator[None]:
    reset_spell_regression_arena(16, 8)
    yield
    reset_engine_runtime()


def creature(name: str, position: tuple[int, int], *, strength: int = 10, dexterity: int = 10,
             constitution: int = 10, wisdom: int = 10) -> Entity:
    entity = create_spell_regression_actor(name, position, "heroes", strength=strength, dexterity=dexterity,
                                           constitution=constitution, wisdom=wisdom)
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()
    return entity


def walk(entity: Entity, *cells: tuple[int, int], faces: tuple[int, ...] = ()) -> None:
    entity.action_economy.reset_all_costs()
    entity.update_entity_senses()
    path = [entity.position, *cells]
    with fixed_dice_faces(*faces):
        move = Move(source_entity_uuid=entity.uuid, path=path, end_position=path[-1]).apply()
    assert move is not None and not move.canceled and entity.position == path[-1]


def row(entity: Entity, name: str) -> AvailableActionInfo | None:
    entity.action_economy.reset_all_costs()
    entity.update_entity_senses()
    return next((info for info in entity.get_available_actions().all_actions
                 if info.template_name == name or info.template_name.startswith(f"{name}__item_")), None)


def act(entity: Entity, name: str, *, target: BaseItem | None = None, faces: tuple[int, ...] = ()) -> None:
    info = row(entity, name)
    assert info is not None, name
    choice = next(option for option in info.valid_targets
                  if target is None or option.target_uuid == target.uuid)
    with fixed_dice_faces(*faces):
        result = execute_available_action(entity, info, choice)
    assert result is not None and not result.canceled, result


def wear(entity: Entity, item_id: str, slot: BodyPart) -> None:
    item = build_authored_item(item_id, entity.uuid)
    assert entity.loot_item(item) and entity.equip_item(item.uuid, slot)


@pytest.mark.parametrize(("gear", "shocked"), (
    ((), False),
    ((("armor.chain_mail", BodyPart.BODY),), True),
    ((("armor.chain_mail", BodyPart.BODY), ("apparel.leather_boots", BodyPart.FEET)), False),
))
def test_an_electric_plate_shocks_on_a_failed_save_with_metal_armor_and_boots_counted(arena, gear, shocked):
    walker = creature("Walker", (2, 2), strength=18)
    for item_id, slot in gear:
        wear(walker, item_id, slot)
    materialize_electric_floor({(3, 2)})
    before = walker.get_hp()
    walk(walker, (3, 2), faces=(15, 3))  # Dex save 15: beats DC 13, not 17; the damage die shows 3
    assert before - walker.get_hp() == (3 if shocked else 0)
    hp = walker.get_hp()
    walk(walker, (4, 2))  # a carpet cell is left out of the plates: no save, no die
    assert walker.get_hp() == hp


def test_gray_mold_spores_ask_one_save_per_stay_and_leave_the_failed_coughing(arena):
    materialize_gray_mold({(3, 2), (4, 2), (5, 2)})
    bystander = creature("Bystander", (5, 2), constitution=1)
    frail = creature("Frail", (2, 2), constitution=1)
    walk(frail, (3, 2), faces=(4,) * 4)  # everyone present saves: 4 - 5 fails twice; each d6 shows 4
    assert "Coughing" in frail.active_conditions and "Coughing" in bystander.active_conditions
    assert frail.active_conditions["Coughing"].duration.duration == 4
    walk(frail, (4, 2))  # moving inside the same exposure asks no save
    walk(frail, (3, 2), (2, 2))
    frail.remove_condition("Coughing")
    walk(frail, (3, 2), faces=(4, 2))  # a fresh stay: only Frail saves again
    assert frail.active_conditions["Coughing"].duration.duration == 2


def test_coughing_runs_out_after_its_rolled_rounds(arena):
    materialize_gray_mold({(3, 2)})
    frail = creature("Frail", (2, 2), constitution=1)
    walk(frail, (3, 2), faces=(4, 2))
    for _ in range(3):
        frail.on_turn_start()
        frail.on_turn_end()
    assert "Coughing" not in frail.active_conditions


def test_coughing_makes_stealth_checks_noisy(arena):
    materialize_gray_mold({(3, 2)})
    frail = creature("Frail", (2, 2), constitution=1)
    walk(frail, (3, 2), faces=(4, 4))
    stealth = frail.skill_set.get_skill("stealth").skill_bonus
    assert stealth.advantage is AdvantageStatus.DISADVANTAGE


def test_authored_darkness_is_magical_and_daylight_lifts_it(arena):
    cells = {(x, y) for x in range(4, 8) for y in range(2, 5)}
    materialize_authored_darkness(cells)
    assert OpticalObscurement.MAGICAL_DARKNESS in OBSCUREMENT_SETS[get_map().optical_obscurement_bits_at((5, 3))]
    cleric = create_spell_regression_actor("Cleric", (12, 3), "heroes", spell_slots={3: 1})
    cleric.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=120)
    result = Daylight(source_entity_uuid=cleric.uuid, end_position=(9, 3), cast_at_level=3).apply()
    assert result is not None and not result.canceled
    assert OpticalObscurement.MAGICAL_DARKNESS not in OBSCUREMENT_SETS[get_map().optical_obscurement_bits_at((5, 3))]


def trapped_footlocker(position: tuple[int, int]) -> StorageChest:
    footlocker = build_authored_item("environment.container.footlocker", uuid4())
    assert isinstance(footlocker, StorageChest)
    footlocker.place_on_grid(position)
    install_container_trap(footlocker)
    return footlocker


def test_a_needle_pricks_its_first_opener_once_and_then_stays_spent(arena):
    footlocker = trapped_footlocker((3, 2))
    opener = creature("Opener", (2, 2), constitution=10)
    act(opener, "Open Chest", faces=(5,))  # Con save 5 fails DC 13
    assert "Needle paralysis" in opener.active_conditions and "Paralyzed" in opener.active_conditions
    assert opener.active_conditions["Needle paralysis"].duration.duration == 10
    opener.remove_condition("Needle paralysis")
    assert "Paralyzed" not in opener.active_conditions
    act(opener, "Close Chest")
    act(opener, "Open Chest")  # no die is left to roll: the needle is spent
    assert "Needle paralysis" not in opener.active_conditions
    assert footlocker.is_open


def test_a_repeat_save_at_the_victims_turn_end_ends_the_needle_paralysis(arena):
    trapped_footlocker((3, 2))
    opener = creature("Opener", (2, 2), constitution=10)
    act(opener, "Open Chest", faces=(5,))
    opener.on_turn_start()
    with fixed_dice_faces(15):  # Con save 15 beats DC 13
        opener.on_turn_end()
    assert "Needle paralysis" not in opener.active_conditions and "Paralyzed" not in opener.active_conditions


def test_lesser_restoration_cures_the_whole_needle_paralysis(arena):
    trapped_footlocker((3, 2))
    opener = creature("Opener", (2, 2), constitution=10)
    act(opener, "Open Chest", faces=(5,))
    cleric = create_spell_regression_actor("Cleric", (2, 3), "heroes", spell_slots={2: 1})
    cleric.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = LesserRestoration(source_entity_uuid=cleric.uuid, target_entity_uuid=opener.uuid).apply()
    assert result is not None and not result.canceled
    assert "Needle paralysis" not in opener.active_conditions and "Paralyzed" not in opener.active_conditions
    opener.on_turn_start()
    opener.on_turn_end()  # no repeat save is left to roll


def test_search_finds_a_hidden_needle_and_only_then_offers_disarm(arena):
    footlocker = trapped_footlocker((3, 2))
    rogue = creature("Rogue", (2, 2), wisdom=8, dexterity=18)  # passive Perception 9 cannot see DC 13
    assert rogue.loot_item(build_authored_item("tool.trap_disarm_toolkit", rogue.uuid))
    assert row(rogue, "Disarm Trap") is None
    act(rogue, "Search for Traps", faces=(5,))  # 5 - 1 misses DC 13
    assert row(rogue, "Disarm Trap") is None
    act(rogue, "Search for Traps", faces=(16,))  # 16 - 1 finds it
    assert row(rogue, "Disarm Trap") is not None
    act(rogue, "Disarm Trap", target=footlocker, faces=(12,))  # Sleight of Hand 12 + 4 beats DC 13
    toolkit = next(item for item in rogue.inventory.items.values() if item.item_id == "tool.trap_disarm_toolkit")
    assert toolkit.stack_count == 1
    act(rogue, "Open Chest")
    assert "Needle paralysis" not in rogue.active_conditions


def test_a_failed_disarm_uses_up_one_kit_and_springs_the_needle_on_the_disarmer(arena):
    footlocker = trapped_footlocker((3, 2))
    clumsy = creature("Clumsy", (2, 2), wisdom=20, dexterity=8)  # passive Perception 15 already sees it
    assert clumsy.loot_item(build_trap_disarm_toolkit(clumsy.uuid, 2))
    act(clumsy, "Disarm Trap", target=footlocker, faces=(3, 2))  # Sleight 3 - 1 fails; Con save 2 fails
    toolkit = next(item for item in clumsy.inventory.items.values() if item.item_id == "tool.trap_disarm_toolkit")
    assert toolkit.stack_count == 1
    assert "Needle paralysis" in clumsy.active_conditions
    clumsy.remove_condition("Needle paralysis")
    act(clumsy, "Open Chest")  # no die is left to roll: the needle is spent


def test_breaking_a_trapped_container_disarms_it(arena):
    footlocker = trapped_footlocker((3, 2))
    footlocker.receive_damage(footlocker.get_hp(), DamageType.BLUDGEONING, footlocker.uuid)
    assert not any(condition.name == "Poison needle" for condition in footlocker.active_conditions.values())


def test_search_reveals_a_hidden_floor_trap_to_the_searcher_alone(arena):
    trap = materialize_spike_trap_condition({(4, 2)}, stealth_dc=13)
    searcher = creature("Searcher", (2, 2), wisdom=8)
    bystander = creature("Bystander", (2, 3), wisdom=8)
    assert trap.uuid not in searcher.senses.spatial_effects
    act(searcher, "Search for Traps", faces=(16,))
    bystander.update_entity_senses()
    assert trap.uuid in searcher.senses.spatial_effects
    assert trap.uuid not in bystander.senses.spatial_effects
