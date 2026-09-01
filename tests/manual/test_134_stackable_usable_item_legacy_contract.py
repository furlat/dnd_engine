"""Coverage ledger for the displaced stackable and environment-item suites.

The archived scripts encoded valuable behavior, but their reset hooks only ran
through custom ``__main__`` runners and several assertions selected action
index zero instead of the intended UUID.  This module records every old case's
disposition and restores item-specific behavior against current discovered
action identities.
"""

from dataclasses import dataclass
from enum import StrEnum
from unittest.mock import patch
from uuid import UUID, uuid4

from dnd.actions_functional import (
    execute_by_index,
    execute_use_action,
    get_available_actions,
    setup_standard_actions,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.inventory import Inventory
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import (
    build_campfire,
    build_directional_door,
    build_storage_chest,
    build_trap_lever,
)
from dnd.core.base_actions import AvailableActionInfo
from dnd.core.base_block import BaseBlock
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase
from dnd.core.gridmap import get_map
from dnd.core.creature_types import DamageType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.consumables import (
    build_fire_weapon_coat,
    build_healing_potion,
    build_lightning_weapon_coat,
)
from dnd.items.spell_items import (
    build_fireball_scroll,
    build_magic_missile_scroll,
    build_wand_of_magic_missiles,
)
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.types.world import CardinalDirection
from tests.engine.support import get_hp, reset_combat_state, set_hp


THIS_FILE = "tests/manual/test_134_stackable_usable_item_legacy_contract.py"
BOOK_ITEMS_FILE = "tests/engine/test_items_inventory_equipment.py"
INVENTORY_USE_FILE = (
    "tests/manual/test_131_inventory_use_actions_legacy_contract.py"
)


class CoverageStatus(StrEnum):
    """Disposition of one displaced logical case."""

    ACTIVE = "active"
    STRENGTHENED = "strengthened"
    RETIRED = "retired"


@dataclass(frozen=True)
class CoverageRecord:
    """Maintained selector and disposition for one archived case."""

    selector: str
    status: CoverageStatus = CoverageStatus.ACTIVE
    reason: str = ""


STACK_IDENTITY_SELECTOR = (
    f"{THIS_FILE}::test_stack_identity_limits_weight_and_full_slot_merge"
)
STACK_ACTION_SELECTOR = (
    f"{THIS_FILE}::test_stacked_scroll_has_one_discovered_row_and_consumes_one_copy"
)
LIGHTNING_COAT_SELECTOR = (
    f"{THIS_FILE}::test_elemental_coat_stacks_stay_distinct_and_lightning_applies"
)
DOOR_SELECTOR = (
    f"{THIS_FILE}::test_override_and_default_door_actions_toggle_spatial_state"
)
LEVER_SELECTOR = (
    f"{THIS_FILE}::test_lever_depletion_removes_only_its_linked_trap"
)
CHEST_SELECTOR = (
    f"{THIS_FILE}::test_chest_discovery_loot_and_empty_state_are_one_contract"
)
CHEST_DESTROY_SELECTOR = (
    f"{BOOK_ITEMS_FILE}::test_eb_13_010_breakable_items_destroy_and_spill_nested_inventory"
)
CAMPFIRE_SELECTOR = (
    f"{THIS_FILE}::test_multi_action_environment_item_executes_and_depletes"
)
ENVIRONMENT_BOUNDARY_SELECTOR = (
    f"{THIS_FILE}::test_nonusable_and_out_of_range_objects_do_not_surface_use_rows"
)
POTION_STACK_SELECTOR = (
    f"{BOOK_ITEMS_FILE}::test_eb_13_002_inventory_stack_merge_can_consume_or_split_items"
)
CONSUME_FINAL_SELECTOR = (
    f"{INVENTORY_USE_FILE}::test_scroll_execute_by_index_consumes_item_not_spell_slots"
)


STACKABLE_CASES: dict[str, CoverageRecord] = {
    "test_stack_merge_on_loot": CoverageRecord(STACK_IDENTITY_SELECTOR),
    "test_no_merge_different_levels": CoverageRecord(STACK_IDENTITY_SELECTOR),
    "test_no_merge_different_types": CoverageRecord(STACK_IDENTITY_SELECTOR),
    "test_consume_from_stack": CoverageRecord(
        STACK_ACTION_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement executes the exact discovered leveled-spell identity.",
    ),
    "test_consume_last_in_stack": CoverageRecord(
        CONSUME_FINAL_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement executes the exact discovered leveled-spell identity.",
    ),
    "test_action_appears_once": CoverageRecord(STACK_ACTION_SELECTOR),
    "test_display_name_includes_count": CoverageRecord(STACK_ACTION_SELECTOR),
    "test_stack_limit_respected": CoverageRecord(STACK_IDENTITY_SELECTOR),
    "test_potion_stacking": CoverageRecord(POTION_STACK_SELECTOR),
    "test_non_stackable_unchanged": CoverageRecord(STACK_IDENTITY_SELECTOR),
    "test_weight_with_stacks": CoverageRecord(STACK_IDENTITY_SELECTOR),
    "test_can_add_with_full_slots": CoverageRecord(STACK_IDENTITY_SELECTOR),
    "test_fire_coat_stacking": CoverageRecord(LIGHTNING_COAT_SELECTOR),
    "test_fire_vs_lightning_no_merge": CoverageRecord(LIGHTNING_COAT_SELECTOR),
    "test_lightning_coat_applies_damage": CoverageRecord(
        LIGHTNING_COAT_SELECTOR,
    ),
}


USABLE_CASES: dict[str, CoverageRecord] = {
    "test_door_a_discovery": CoverageRecord(DOOR_SELECTOR),
    "test_door_a_open_close_cycle": CoverageRecord(DOOR_SELECTOR),
    "test_door_a_blocks_movement": CoverageRecord(DOOR_SELECTOR),
    "test_door_b_discovery": CoverageRecord(
        DOOR_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The fixture-only parallel door now uses a second exact canonical door root.",
    ),
    "test_door_b_toggle": CoverageRecord(
        DOOR_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The fixture-only parallel door now uses a second exact canonical door root.",
    ),
    "test_door_b_uses_default_field": CoverageRecord(
        DOOR_SELECTOR,
        CoverageStatus.RETIRED,
        "Class-method identity was implementation coupling; inherited behavior is asserted.",
    ),
    "test_door_vision_blocking": CoverageRecord(DOOR_SELECTOR),
    "test_lever_discovery": CoverageRecord(LEVER_SELECTOR),
    "test_lever_deactivates_trap": CoverageRecord(LEVER_SELECTOR),
    "test_lever_one_use": CoverageRecord(LEVER_SELECTOR),
    "test_chest_discovery": CoverageRecord(CHEST_SELECTOR),
    "test_chest_loot_transfers": CoverageRecord(CHEST_SELECTOR),
    "test_empty_chest_no_action": CoverageRecord(CHEST_SELECTOR),
    "test_chest_destroy_drops_loot": CoverageRecord(CHEST_DESTROY_SELECTOR),
    "test_campfire_multiple_actions": CoverageRecord(CAMPFIRE_SELECTOR),
    "test_campfire_execute_each": CoverageRecord(CAMPFIRE_SELECTOR),
    "test_out_of_range": CoverageRecord(ENVIRONMENT_BOUNDARY_SELECTOR),
    "test_non_usable_ignored": CoverageRecord(ENVIRONMENT_BOUNDARY_SELECTOR),
    "test_charges_system": CoverageRecord(CAMPFIRE_SELECTOR),
}


def reset_item_world(width: int = 20, height: int = 20) -> None:
    """Reset global engine state and create one bright floor."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, width, height)


def create_actor(
    position: tuple[int, int],
    *,
    name: str = "Hero",
    faction: str = "heroes",
    hit_dice_count: int = 10,
) -> Entity:
    """Create a durable current-architecture actor for item action tests."""
    actor_uuid = uuid4()
    actor = Entity.create(
        source_entity_uuid=actor_uuid,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=16),
                dexterity=AbilityConfig(ability_score=14),
                intelligence=AbilityConfig(ability_score=16),
                constitution=AbilityConfig(ability_score=14),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=hit_dice_count,
                        mode="maximums",
                    )
                ]
            ),
            equipment=EquipmentConfig(),
            action_economy=ActionEconomyConfig(
                spell_slots={1: 4, 2: 3, 3: 2},
            ),
            spellcasting=SpellcastingConfig(
                spellcasting_ability="intelligence",
            ),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
    )
    setup_standard_actions(actor)
    actor.compose_entity()
    Game().deploy_entity(actor, position)
    return actor


def item_rows(entity: Entity, item_uuid: UUID) -> list[AvailableActionInfo]:
    """Return discovered rows belonging to one item UUID."""
    return [
        row
        for row in get_available_actions(entity).all_actions
        if row.source_item_uuid == item_uuid
    ]


def test_legacy_stackable_and_usable_manifests_account_for_all_34_cases() -> None:
    """Every displaced stackable/usable case has an explicit disposition."""
    assert len(STACKABLE_CASES) == 15
    assert len(USABLE_CASES) == 19
    records = tuple(STACKABLE_CASES.values()) + tuple(USABLE_CASES.values())
    assert len(records) == 34
    assert all(
        record.selector.startswith("tests/") and "::test_" in record.selector
        for record in records
    )
    assert all(
        record.reason
        for record in records
        if record.status is not CoverageStatus.ACTIVE
    )
    retired = [
        case
        for case, record in USABLE_CASES.items()
        if record.status is CoverageStatus.RETIRED
    ]
    assert retired == ["test_door_b_uses_default_field"]


def test_stack_identity_limits_weight_and_full_slot_merge() -> None:
    """Stack IDs own compatibility, limits, weight, and full-slot merging."""
    reset_item_world()
    owner_uuid = uuid4()
    inventory = Inventory(source_entity_uuid=owner_uuid)
    for _ in range(22):
        scroll = build_fireball_scroll(owner_uuid, cast_level=3)
        scroll.weight = 0.5
        assert inventory.add_item(scroll)

    fireball_level_three = list(inventory.items.values())
    assert sorted(item.stack_count for item in fireball_level_three) == [2, 20]
    assert inventory.item_count == 2
    assert inventory.total_weight == 11

    level_five = build_fireball_scroll(owner_uuid, cast_level=5)
    missile = build_magic_missile_scroll(owner_uuid)
    first_wand = build_wand_of_magic_missiles(owner_uuid)
    second_wand = build_wand_of_magic_missiles(owner_uuid)
    for item in (level_five, missile, first_wand, second_wand):
        assert inventory.add_item(item)

    assert inventory.item_count == 6
    assert level_five.stack_id != fireball_level_three[0].stack_id
    assert missile.stack_id != fireball_level_three[0].stack_id
    assert first_wand.stack_id is None
    assert second_wand.stack_id is None
    assert first_wand.uuid in inventory.items
    assert second_wand.uuid in inventory.items

    tight = Inventory(source_entity_uuid=uuid4(), max_slots=1)
    existing = build_fireball_scroll(tight.source_entity_uuid)
    compatible = build_fireball_scroll(tight.source_entity_uuid)
    incompatible = build_magic_missile_scroll(tight.source_entity_uuid)
    assert tight.add_item(existing)
    assert tight.can_add(compatible)
    assert tight.add_item(compatible)
    assert tight.item_count == 1
    assert existing.stack_count == 2
    assert not tight.can_add(incompatible)
    assert not tight.add_item(incompatible)

    potion_inventory = Inventory(source_entity_uuid=uuid4())
    for _ in range(3):
        assert potion_inventory.add_item(
            build_healing_potion(potion_inventory.source_entity_uuid)
        )
    potion_stack = next(iter(potion_inventory.items.values()))
    assert potion_stack.stack_count == 3


def test_stacked_scroll_has_one_discovered_row_and_consumes_one_copy() -> None:
    """A stack publishes one item-bound action row and spends one represented copy."""
    reset_item_world()
    caster = create_actor((1, 5), name="Caster")
    target = create_actor(
        (8, 5),
        name="Target",
        faction="monsters",
        hit_dice_count=50,
    )
    for _ in range(3):
        assert caster.loot_item(build_fireball_scroll(caster.uuid))
    stacked = next(iter(caster.inventory.items.values()))
    assert isinstance(stacked, UsableItem)
    Entity.update_all_entities_senses()

    available = get_available_actions(caster)
    rows = [
        row
        for row in available.all_actions
        if row.source_item_uuid == stacked.uuid
    ]

    assert len(rows) == 1
    row = rows[0]
    assert row.item_stack_count == 3
    assert row.display_name == "Fireball (Scroll of Fireball x3)"
    target_row = next(
        candidate
        for candidate in row.valid_targets
        if candidate.position == target.position
    )

    with fixed_dice_faces(*([1] * 12)):
        result = execute_by_index(
            caster,
            row.template_name,
            target_row.index,
            available=available,
        )

    assert result is not None and not result.canceled
    assert result.phase is EventPhase.COMPLETION
    assert stacked.stack_count == 2
    assert stacked.charges == stacked.max_charges == 1
    assert caster.inventory.has_item(stacked.uuid)
    refreshed = item_rows(caster, stacked.uuid)
    assert len(refreshed) == 1
    assert refreshed[0].can_afford is False
    assert refreshed[0].item_stack_count == 2
    caster.action_economy.reset_all_costs()
    refreshed = item_rows(caster, stacked.uuid)
    assert len(refreshed) == 1
    assert refreshed[0].item_stack_count == 2
    assert refreshed[0].display_name == "Fireball (Scroll of Fireball x2)"


def test_elemental_coat_stacks_stay_distinct_and_lightning_applies() -> None:
    """Element identity controls coat stacking and the applied damage packet."""
    reset_item_world()
    actor = create_actor((3, 3))
    sword = build_authored_item("weapon.longsword", actor.uuid)
    assert actor.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    first_fire = build_fire_weapon_coat(actor.uuid)
    second_fire = build_fire_weapon_coat(actor.uuid)
    lightning = build_lightning_weapon_coat(actor.uuid)
    assert actor.loot_item(first_fire)
    assert actor.loot_item(second_fire)
    assert actor.loot_item(lightning)

    fire_stack = next(
        item
        for item in actor.inventory.items.values()
        if item.item_id == "consumable.weapon_coat.fire"
    )
    lightning_stack = next(
        item
        for item in actor.inventory.items.values()
        if item.item_id == "consumable.weapon_coat.lightning"
    )
    assert fire_stack.stack_count == 2
    assert lightning_stack.stack_count == 1
    assert fire_stack.uuid != lightning_stack.uuid

    lightning_row = next(
        row
        for row in item_rows(actor, lightning_stack.uuid)
        if row.template_name.startswith("Coat Main Hand")
    )
    result = execute_use_action(
        actor,
        lightning_stack.uuid,
        lightning_row.template_name,
    )

    assert result is not None and not result.canceled
    assert "Lightning Coat" in actor.active_conditions
    assert sword.extra_damage_dices == [6]
    assert sword.extra_damage_type == [DamageType.LIGHTNING]
    assert BaseBlock.get(lightning_stack.uuid) is None
    assert actor.inventory.has_item(fire_stack.uuid)
    assert fire_stack.stack_count == 2


def test_override_and_default_door_actions_toggle_spatial_state() -> None:
    """Two exact canonical door roots discover and commit independent state."""
    reset_item_world()
    actor = create_actor((3, 3))
    override_door = build_directional_door(display_name="Override Door")
    default_door = build_directional_door()
    override_door.place_on_grid(
        (4, 3),
        boundary_direction=CardinalDirection.WEST,
    )
    default_door.place_on_grid(
        (3, 4),
        boundary_direction=CardinalDirection.SOUTH,
    )
    Entity.update_all_entities_senses()

    override_rows = item_rows(actor, override_door.uuid)
    default_rows = item_rows(actor, default_door.uuid)
    assert [row.template_name.split("__item_")[0] for row in override_rows] == [
        "Open Door"
    ]
    assert [row.template_name.split("__item_")[0] for row in default_rows] == [
        "Open Door"
    ]
    grid = get_map()
    transitions = (((3, 3), (4, 3)), ((3, 3), (3, 4)))
    for origin, destination in transitions:
        assert not grid.can_transition(origin, destination)
        assert not grid.can_optical_transition(origin, destination)

    opened_override = execute_use_action(actor, override_door.uuid, "Open Door")
    opened_default = execute_use_action(actor, default_door.uuid, "Open Door")

    assert opened_override is not None and not opened_override.canceled
    assert opened_default is not None and not opened_default.canceled
    for door in (override_door, default_door):
        assert door.is_open
    for origin, destination in transitions:
        assert grid.can_transition(origin, destination)
        assert grid.can_optical_transition(origin, destination)

    closed_override = execute_use_action(actor, override_door.uuid, "Close Door")
    closed_default = execute_use_action(actor, default_door.uuid, "Close Door")

    assert closed_override is not None and not closed_override.canceled
    assert closed_default is not None and not closed_default.canceled
    for door in (override_door, default_door):
        assert not door.is_open
    for origin, destination in transitions:
        assert not grid.can_transition(origin, destination)
        assert not grid.can_optical_transition(origin, destination)


def test_lever_depletion_removes_only_its_linked_trap() -> None:
    """A lever removes its linked trap and disappears after its finite use."""
    reset_item_world()
    actor = create_actor((5, 5))
    linked_condition = materialize_spike_trap_condition({(3, 3)})
    other_condition = materialize_spike_trap_condition({(7, 7)})
    lever = build_trap_lever(
        linked_condition.uuid,
        charges=1,
    )
    lever.max_charges = 1
    lever.place_on_grid((5, 6))
    Entity.update_all_entities_senses()

    rows = item_rows(actor, lever.uuid)
    assert len(rows) == 1
    assert rows[0].template_name.startswith("Pull Lever")

    result = execute_use_action(actor, lever.uuid, rows[0].template_name)

    assert result is not None and not result.canceled
    assert lever.charges == 0
    assert item_rows(actor, lever.uuid) == []
    grid = get_map()
    assert not linked_condition.applied
    assert not grid.has_spatial_condition(linked_condition.uuid)
    assert grid.get_spatial_conditions_at((3, 3)) == []
    assert other_condition.applied
    assert grid.has_spatial_condition(other_condition.uuid)
    assert grid.get_spatial_conditions_at((7, 7)) == [other_condition]


def test_chest_discovery_loot_and_empty_state_are_one_contract() -> None:
    """Loot All transfers every nested item and then vanishes from discovery."""
    reset_item_world()
    actor = create_actor((5, 5))
    chest = build_storage_chest("Loot Chest", include_loot_all_action=True)
    chest.chest_inventory.source_entity_uuid = chest.uuid
    sword = build_authored_item("weapon.shortsword", chest.uuid)
    potion = build_healing_potion(chest.uuid)
    assert chest.chest_inventory.add_item(sword)
    assert chest.chest_inventory.add_item(potion)
    chest.place_on_grid((6, 5))
    Entity.update_all_entities_senses()

    rows = item_rows(actor, chest.uuid)
    assert len(rows) == 1
    assert rows[0].template_name.startswith("Loot All")

    result = execute_use_action(actor, chest.uuid, rows[0].template_name)

    assert result is not None and not result.canceled
    assert chest.chest_inventory.item_count == 0
    assert actor.inventory.has_item(sword.uuid)
    assert actor.inventory.has_item(potion.uuid)
    for item in (sword, potion):
        assert item.owner_uuid == actor.uuid
        assert item.stored_in_uuid == actor.inventory.uuid
        assert item.tile_uuid is None
    assert item_rows(actor, chest.uuid) == []


def test_multi_action_environment_item_executes_and_depletes() -> None:
    """One finite environment item owns two independent effects and one charge pool."""
    reset_item_world()
    actor = create_actor((5, 5))
    set_hp(actor, get_hp(actor) - 10)
    before = get_hp(actor)
    campfire = build_campfire(uuid4())
    campfire.charges = 2
    campfire.max_charges = 2
    campfire.place_on_grid((5, 6))
    Entity.update_all_entities_senses()

    rows = item_rows(actor, campfire.uuid)
    assert {
        row.template_name.split("__item_")[0]
        for row in rows
    } == {"Rest", "Cook"}

    with patch("dnd.items.environment_interactables.random.randint", return_value=4):
        rest = execute_use_action(actor, campfire.uuid, "Rest")
    assert rest is not None and not rest.canceled
    assert get_hp(actor) == before + 4

    cook = execute_use_action(actor, campfire.uuid, "Cook")

    assert cook is not None and not cook.canceled
    assert get_hp(actor) == before + 7
    assert actor.health.temporary_hit_points.score == 3
    assert campfire.charges == 0
    assert item_rows(actor, campfire.uuid) == []


def test_nonusable_and_out_of_range_objects_do_not_surface_use_rows() -> None:
    """Floor discovery excludes plain objects and usable objects beyond five feet."""
    reset_item_world()
    actor = create_actor((1, 1))
    rock = BaseItem(
        source_entity_uuid=uuid4(),
        item_id="test.item.rock",
        name="Rock",
        is_pickable=False,
    )
    far_door = build_directional_door()
    rock.place_on_grid((2, 1))
    far_door.place_on_grid(
        (8, 8),
        boundary_direction=CardinalDirection.WEST,
    )
    Entity.update_all_entities_senses()

    all_rows = get_available_actions(actor).all_actions

    assert all(row.source_item_uuid != rock.uuid for row in all_rows)
    assert all(row.source_item_uuid != far_door.uuid for row in all_rows)
