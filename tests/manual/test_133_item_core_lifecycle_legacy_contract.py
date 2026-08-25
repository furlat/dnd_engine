"""Coverage ledger for the displaced core item and lifecycle-hook suites.

The archived files remain useful historical specifications, but they are not
normal pytest suites: their isolation lived in a custom ``__main__`` runner.
This module maps every old logical case to a maintained selector and restores
the current public contracts that had no active equivalent.
"""
from dnd.types.materials import Material, TileSurface

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import (
    BaseItem,
    EquippableItem,
    UsableItem,
)
from dnd.blocks.equipment import (
    EquipmentConfig,
)
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.events.events_registry import (
    Event,
)
from dnd.core.gridmap import get_map
from dnd.types.items import ItemRarity
from dnd.types.world_placement import WorldObjectPlacement
from dnd.types.damage import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.entities.entity import Entity, EntityConfig
from tests.engine.support import (
    create_test_entity,
    get_hp,
    get_max_hp,
    reset_combat_state,
    set_hp,
)


THIS_FILE = "tests/manual/test_133_item_core_lifecycle_legacy_contract.py"
BOOK_ACTIONS_FILE = "tests/engine/test_action_discovery.py"
BOOK_GRID_FILE = "tests/engine/test_grid_pathfinding.py"
BOOK_ITEMS_FILE = "tests/engine/test_items_inventory_equipment.py"
BOOK_CONDITIONS_FILE = "tests/engine/test_condition_lifecycle.py"
ADVANCED_ITEMS_FILE = "tests/manual/test_131_advanced_item_world_legacy_contract.py"
DEPENDENCY_FILE = "tests/architecture/test_dependency_boundaries.py"


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


BASE_ITEM_SELECTOR = (
    f"{THIS_FILE}::test_base_item_value_damage_affinity_and_destroy_contract"
)
GRID_CLEAR_SELECTOR = (
    f"{THIS_FILE}::test_grid_clear_synchronizes_each_floor_item_exactly_once"
)
HOOK_CONTEXT_SELECTOR = (
    f"{THIS_FILE}::test_lifecycle_hooks_receive_authoritative_context_in_order"
)
DESTROY_EFFECT_SELECTOR = (
    "tests/engine/test_spatial_effects.py::"
    "test_oil_barrel_destruction_uses_material_transition_table"
)
LOOT_EFFECT_SELECTOR = (
    f"{THIS_FILE}::test_loot_hook_can_apply_condition_and_bounded_healing"
)
MODIFIER_EFFECT_SELECTOR = (
    f"{THIS_FILE}::test_loot_drop_hooks_move_an_owned_modifier_between_actors"
)
LOCATION_SELECTOR = (
    f"{BOOK_ITEMS_FILE}::test_eb_13_001_floor_loot_and_drop_update_authoritative_location"
)
TRANSFER_SELECTOR = (
    f"{BOOK_ITEMS_FILE}::test_eb_13_003_inventory_capacity_and_transfer_update_container_fields"
)
PICKUP_SELECTOR = (
    f"{BOOK_ACTIONS_FILE}::test_eb_09_004_floor_objects_create_object_actions_and_can_be_picked_up"
)
ATTACK_OBJECT_SELECTOR = (
    f"{BOOK_ACTIONS_FILE}::test_eb_09_012_attack_object_discovers_and_destroys_breakables"
)
BLOCKING_SELECTOR = (
    f"{BOOK_GRID_FILE}::test_eb_11_005_occupants_and_objects_block_walkable_tiles_polymorphically"
)
RAW_REMOVAL_SELECTOR = (
    f"{BOOK_GRID_FILE}::test_eb_11_016_raw_object_removal_clears_item_floor_location_state"
)
VISION_SELECTOR = (
    f"{ADVANCED_ITEMS_FILE}::test_vision_blocker_hides_then_destroy_reveals_floor_item_and_entity"
)
SENSES_SELECTOR = (
    f"{ADVANCED_ITEMS_FILE}::test_dropped_and_colocated_items_preserve_grid_and_visibility"
)
INVENTORY_VALUE_SELECTOR = (
    f"{ADVANCED_ITEMS_FILE}::test_inventory_weight_equippable_flags_and_tag_filters"
)
PICKUP_BOUNDARY_SELECTOR = (
    f"{ADVANCED_ITEMS_FILE}::test_pickup_targets_respect_capacity_and_five_foot_range"
)
NON_TARGET_SELECTOR = (
    f"{ADVANCED_ITEMS_FILE}::test_nonbreakable_or_unseen_items_are_not_object_targets"
)
ITEM_CONDITION_SELECTOR = (
    f"{BOOK_CONDITIONS_FILE}::test_eb_07_013_item_conditions_index_expire_and_destroy_cleanly"
)
DEPENDENCY_SELECTOR = (
    f"{DEPENDENCY_FILE}::test_internal_import_graph_has_no_cycles"
)


PHASE1_CASES: dict[str, CoverageRecord] = {
    "test_base_item_fields": CoverageRecord(
        BASE_ITEM_SELECTOR,
        reason="The exact name and canonical nonblocking defaults remain asserted.",
    ),
    "test_equippable_usable_stubs": CoverageRecord(BASE_ITEM_SELECTOR),
    "test_item_health_damage": CoverageRecord(BASE_ITEM_SELECTOR),
    "test_item_health_resistances": CoverageRecord(BASE_ITEM_SELECTOR),
    "test_item_destruction": CoverageRecord(BASE_ITEM_SELECTOR),
    "test_gridmap_place_remove": CoverageRecord(LOCATION_SELECTOR),
    "test_gridmap_clear": CoverageRecord(
        GRID_CLEAR_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The replacement also clears each live item's floor-location facts.",
    ),
    "test_blocking_object_walkability": CoverageRecord(BLOCKING_SELECTOR),
    "test_blocking_object_vision": CoverageRecord(VISION_SELECTOR),
    "test_senses_objects": CoverageRecord(SENSES_SELECTOR),
    "test_senses_objects_removed": CoverageRecord(RAW_REMOVAL_SELECTOR),
    "test_inventory_add_remove": CoverageRecord(TRANSFER_SELECTOR),
    "test_inventory_capacity": CoverageRecord(TRANSFER_SELECTOR),
    "test_inventory_transfer": CoverageRecord(TRANSFER_SELECTOR),
    "test_inventory_find": CoverageRecord(INVENTORY_VALUE_SELECTOR),
    "test_entity_loot_item": CoverageRecord(LOCATION_SELECTOR),
    "test_entity_drop_item": CoverageRecord(LOCATION_SELECTOR),
    "test_lifecycle_hooks": CoverageRecord(HOOK_CONTEXT_SELECTOR),
    "test_pickup_available_actions": CoverageRecord(PICKUP_SELECTOR),
    "test_pickup_execute": CoverageRecord(PICKUP_SELECTOR),
    "test_attack_object_available_actions": CoverageRecord(ATTACK_OBJECT_SELECTOR),
    "test_attack_object_execute": CoverageRecord(ATTACK_OBJECT_SELECTOR),
    "test_attack_object_destruction": CoverageRecord(ATTACK_OBJECT_SELECTOR),
    "test_non_pickable_not_in_pickup": CoverageRecord(NON_TARGET_SELECTOR),
    "test_item_out_of_reach": CoverageRecord(PICKUP_BOUNDARY_SELECTOR),
    "test_objects_with_conditions": CoverageRecord(ITEM_CONDITION_SELECTOR),
    "test_no_circular_imports": CoverageRecord(
        DEPENDENCY_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "A whole-project static graph assertion replaces an import-order smoke test.",
    ),
}


LIFECYCLE_CASES: dict[str, CoverageRecord] = {
    "test_get_position_on_floor": CoverageRecord(LOCATION_SELECTOR),
    "test_get_position_in_inventory": CoverageRecord(LOCATION_SELECTOR),
    "test_get_position_nowhere": CoverageRecord(BASE_ITEM_SELECTOR),
    "test_stored_in_uuid_set_on_loot": CoverageRecord(LOCATION_SELECTOR),
    "test_tile_uuid_cleared_on_loot": CoverageRecord(LOCATION_SELECTOR),
    "test_location_fields_set_on_drop": CoverageRecord(LOCATION_SELECTOR),
    "test_transfer_updates_stored_in_uuid": CoverageRecord(TRANSFER_SELECTOR),
    "test_drop_at_adjacent_position": CoverageRecord(LOCATION_SELECTOR),
    "test_get_position_floor_returns_own_position": CoverageRecord(LOCATION_SELECTOR),
    "test_destroy_clears_location_fields": CoverageRecord(
        BASE_ITEM_SELECTOR,
        CoverageStatus.STRENGTHENED,
        "The archived test contained no post-destruction assertion.",
    ),
    "test_oil_barrel_destroy_applies_tile_conditions": CoverageRecord(
        DESTROY_EFFECT_SELECTOR,
    ),
    "test_oil_barrel_oily_duration": CoverageRecord(DESTROY_EFFECT_SELECTOR),
    "test_cursed_gem_applies_poisoned": CoverageRecord(LOOT_EFFECT_SELECTOR),
    "test_cursed_gem_condition_persists_after_drop": CoverageRecord(
        LOOT_EFFECT_SELECTOR,
    ),
    "test_aura_stone_adds_ac_on_loot": CoverageRecord(MODIFIER_EFFECT_SELECTOR),
    "test_aura_stone_removes_ac_on_drop": CoverageRecord(MODIFIER_EFFECT_SELECTOR),
    "test_aura_stone_transfer_moves_modifier": CoverageRecord(
        MODIFIER_EFFECT_SELECTOR,
    ),
    "test_healing_herb_heals_on_loot": CoverageRecord(LOOT_EFFECT_SELECTOR),
    "test_healing_herb_no_overheal": CoverageRecord(LOOT_EFFECT_SELECTOR),
    "test_loot_hook_receives_correct_params": CoverageRecord(HOOK_CONTEXT_SELECTOR),
    "test_drop_hook_receives_correct_params": CoverageRecord(HOOK_CONTEXT_SELECTOR),
    "test_drop_hook_receives_adjacent_position": CoverageRecord(
        HOOK_CONTEXT_SELECTOR,
    ),
}


class GridRemovalProbeItem(BaseItem):
    """Floor item that records authoritative grid-removal callbacks."""

    removal_calls: list[tuple[int, int]] = Field(default_factory=list)

    def on_grid_object_removed(
        self,
        position: tuple[int, int],
        parent_event: Optional[UUID] = None,
    ) -> None:
        self.removal_calls.append(position)
        super().on_grid_object_removed(position, parent_event=parent_event)


class LifecycleProbeItem(BaseItem):
    """Item that records the location facts visible to each lifecycle hook."""

    hook_calls: list[
        tuple[
            str,
            UUID | None,
            UUID | None,
            WorldObjectPlacement | None,
            tuple[int, int] | None,
        ]
    ] = Field(default_factory=list)

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        self.hook_calls.append(
            ("loot", entity_uuid, inventory_uuid, get_map().get_object_placement(self.uuid), self.get_position())
        )

    def _on_drop(self, entity_uuid: UUID, position: tuple[int, int]) -> None:
        self.hook_calls.append(
            ("drop", entity_uuid, self.stored_in_uuid, get_map().get_object_placement(self.uuid), self.get_position())
        )

    def _on_destroy(self, parent_event: Event | None) -> None:
        del parent_event
        self.hook_calls.append(
            ("destroy", self.owner_uuid, self.stored_in_uuid, get_map().get_object_placement(self.uuid), self.get_position())
        )


class LootEffectProbeItem(BaseItem):
    """Pickup extension that heals and applies a persistent marker condition."""

    heal_amount: int = 10

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is None:
            return
        entity.health.heal(self.heal_amount)
        entity.add_condition(
            BaseCondition(
                name="Lifecycle Curse",
                source_entity_uuid=self.uuid,
                target_entity_uuid=entity.uuid,
            )
        )


class AuraProbeItem(BaseItem):
    """Pickup/drop extension that owns exactly one AC modifier."""

    modifier_uuid: UUID | None = None
    modifier_owner_uuid: UUID | None = None

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        entity = Entity.get(entity_uuid)
        if entity is None:
            return
        self.modifier_uuid = (
            entity.equipment.ac_bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Lifecycle Aura",
                    value=2,
                    source_entity_uuid=self.uuid,
                    target_entity_uuid=entity.uuid,
                )
            )
        )
        self.modifier_owner_uuid = entity.uuid

    def _on_drop(self, entity_uuid: UUID, position: tuple[int, int]) -> None:
        owner = (
            Entity.get(self.modifier_owner_uuid)
            if self.modifier_owner_uuid is not None
            else None
        )
        if owner is not None and self.modifier_uuid is not None:
            owner.equipment.ac_bonus.self_static.remove_modifier(self.modifier_uuid)
        self.modifier_uuid = None
        self.modifier_owner_uuid = None


def reset_item_world(width: int = 12, height: int = 12) -> None:
    """Reset global engine state and create one bright floor."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, width, height, surface=TileSurface(base_material=Material.STONE))


def create_actor(
    position: tuple[int, int],
    *,
    name: str = "Collector",
    faction: str = "heroes",
) -> Entity:
    """Create a current-architecture actor for item lifecycle tests."""
    actor_uuid = uuid4()
    return create_test_entity(
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=14),
                dexterity=AbilityConfig(ability_score=14),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=5,
                        mode="maximums",
                    )
                ]
            ),
            equipment=EquipmentConfig(),
            action_economy=ActionEconomyConfig(),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
        entity_kind_id="test.item_actor",
        source_id=actor_uuid,
    )


def test_legacy_core_item_manifests_account_for_all_49_cases() -> None:
    """Every displaced core/lifecycle case has an explicit disposition."""
    assert len(PHASE1_CASES) == 27
    assert len(LIFECYCLE_CASES) == 22
    records = tuple(PHASE1_CASES.values()) + tuple(LIFECYCLE_CASES.values())
    assert len(records) == 49
    assert all(
        record.selector.startswith("tests/") and "::test_" in record.selector
        for record in records
    )
    assert all(
        record.reason
        for record in records
        if record.status is not CoverageStatus.ACTIVE
    )
    assert all(record.status is not CoverageStatus.RETIRED for record in records)


def test_base_item_value_damage_affinity_and_destroy_contract() -> None:
    """Item values, capabilities, damage affinities, and cleanup remain coherent."""
    reset_item_world()
    inert = BaseItem(
        source_entity_uuid=uuid4(),
        name="Unplaced Relic",
        weight=5,
        value=100,
        rarity=ItemRarity.RARE,
    )
    equippable = EquippableItem(source_entity_uuid=uuid4(), name="Ring")
    usable = UsableItem(source_entity_uuid=uuid4(), name="Scroll")
    blocker = BaseItem(
        source_entity_uuid=uuid4(),
        name="Barricade",
        blocks_movement=True,
        blocks_optics_field=True,
    )

    assert (
        inert.name,
        inert.weight,
        inert.value,
        inert.rarity,
        inert.is_pickable,
        inert.is_equippable,
        inert.is_usable,
        inert.blocks_movement,
        inert.blocks_optics_field,
        inert.blocks_walking(),
        inert.blocks_optics_at_center(),
        inert.get_position(),
    ) == (
        "Unplaced Relic",
        5,
        100,
        ItemRarity.RARE,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        None,
    )
    assert equippable.is_equippable and equippable.is_pickable
    assert usable.is_usable
    assert blocker.blocks_walking() and blocker.blocks_optics_at_center()

    source_uuid = uuid4()
    breakable = BaseItem(
        source_entity_uuid=source_uuid,
        name="Wooden Crate",
        is_targetable=True,
        health=BaseItem.create_item_health(
            source_uuid,
            hp=16,
            hit_dice_value=8,
            immunities=[DamageType.POISON],
            vulnerabilities=[DamageType.FIRE],
        ),
    )
    breakable.place_on_grid((5, 5))

    assert breakable.is_breakable()
    assert breakable.get_max_hp() == 16
    assert breakable.receive_damage(10, DamageType.POISON, uuid4()) == 0
    assert breakable.get_hp() == 16
    assert breakable.receive_damage(4, DamageType.FIRE, uuid4()) == 8
    assert breakable.get_hp() == 8

    breakable.receive_damage(100, DamageType.BLUDGEONING, uuid4())

    assert BaseBlock.get(breakable.uuid) is None
    assert get_map().get_object_position(breakable.uuid) is None
    assert breakable.owner_uuid is None
    assert breakable.stored_in_uuid is None
    assert get_map().get_object_placement(breakable.uuid) is None
    assert breakable.get_position() is None


def test_grid_clear_synchronizes_each_floor_item_exactly_once() -> None:
    """Destructive map clear cannot leave live items claiming stale floor slots."""
    reset_item_world()
    grid = get_map()
    first = GridRemovalProbeItem(source_entity_uuid=uuid4(), name="First")
    second = GridRemovalProbeItem(source_entity_uuid=uuid4(), name="Second")
    first.place_on_grid((2, 2))
    second.place_on_grid((3, 2))

    grid.clear()

    assert first.removal_calls == [(2, 2)]
    assert second.removal_calls == [(3, 2)]
    for item in (first, second):
        assert grid.get_object_position(item.uuid) is None
        assert grid.get_object_placement(item.uuid) is None
        assert item.get_position() is None


def test_lifecycle_hooks_receive_authoritative_context_in_order() -> None:
    """Loot, drop, and destroy hooks observe the committed location for that phase."""
    reset_item_world()
    actor = create_actor((4, 4))
    item = LifecycleProbeItem(source_entity_uuid=uuid4(), name="Tracked")
    item.place_on_grid((5, 4))
    original_placement = get_map().get_object_placement(item.uuid)

    assert actor.loot_item(item)
    assert actor.drop_item(item.uuid, position=(4, 5)) is item
    dropped_placement = get_map().get_object_placement(item.uuid)
    item.destroy()

    assert item.hook_calls == [
        (
            "loot",
            actor.uuid,
            actor.inventory.uuid,
            None,
            actor.position,
        ),
        (
            "drop",
            actor.uuid,
            None,
            dropped_placement,
            (4, 5),
        ),
        (
            "destroy",
            None,
            None,
            dropped_placement,
            (4, 5),
        ),
    ]
    assert original_placement is not None
    assert dropped_placement is not None
    assert get_map().get_object_placement(item.uuid) is None
    assert item.get_position() is None


def test_loot_hook_can_apply_condition_and_bounded_healing() -> None:
    """Pickup extensions can mutate the looter while core healing still caps at max."""
    for missing_hp, expected_healing in ((20, 10), (3, 3)):
        reset_item_world()
        actor = create_actor((3, 3))
        set_hp(actor, get_max_hp(actor) - missing_hp)
        before = get_hp(actor)
        item = LootEffectProbeItem(source_entity_uuid=uuid4(), name="Cursed Herb")
        item.place_on_grid((4, 3))

        assert actor.loot_item(item)

        assert get_hp(actor) == before + expected_healing
        assert "Lifecycle Curse" in actor.active_conditions
        assert actor.drop_item(item.uuid) is item
        assert "Lifecycle Curse" in actor.active_conditions


def test_loot_drop_hooks_move_an_owned_modifier_between_actors() -> None:
    """An item extension removes its modifier from the old holder before reuse."""
    reset_item_world()
    first = create_actor((3, 3), name="First")
    second = create_actor((4, 3), name="Second", faction="others")
    item = AuraProbeItem(source_entity_uuid=uuid4(), name="Aura")
    item.place_on_grid((3, 4))
    first_base = first.ac_bonus().normalized_score
    second_base = second.ac_bonus().normalized_score

    assert first.loot_item(item)
    assert first.ac_bonus().normalized_score == first_base + 2

    assert first.drop_item(item.uuid) is item
    assert first.ac_bonus().normalized_score == first_base

    assert second.loot_item(item)
    assert first.ac_bonus().normalized_score == first_base
    assert second.ac_bonus().normalized_score == second_base + 2
