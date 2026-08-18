"""Active coverage for the archived inventory use-action behavior matrix.

``to_archive/examples/test_inventory_use_actions.py`` still runs as a custom
script, but its 47 cases are invisible to normal pytest collection.  This file
records the exact replacement selector for every old case and restores the
item-specific combinations that generic spell tests cannot cover: discovery
binding, charge budgets, consumption, environment ownership, and effect
lifecycle cleanup.
"""

from uuid import UUID, uuid4

from dnd.actions.standard import (
    SpellAction,
)
from dnd.actions.operations import (
    execute_action,
    execute_by_index,
    execute_use_action,
    get_available_actions,
    setup_standard_actions,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import (
    BaseItem,
)
from dnd.blocks.equipment import (
    EquipmentConfig,
    Weapon,
)
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.skills import SkillConfig, SkillSetConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_actions import (
    AvailableActionInfo,
    AvailableTarget,
    TargetType,
)
from dnd.core.base_block import BaseBlock
from dnd.core.dice import fixed_dice_faces
from dnd.types.equipment import WeaponSlot
from dnd.types.abilities import AbilityName
from dnd.core.gridmap import get_map
from dnd.core.base_conditions import BaseCondition
from dnd.types.damage import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.entities.entity import Entity, EntityConfig
from dnd.items.consumables import (
    CONCENTRATION_FIRE_WEAPON_COAT_RECIPE,
    FIRE_WEAPON_COAT_RECIPE,
    timed_fire_weapon_coat_recipe,
)
from dnd.items.environment_content import (
    ARCANE_MACHINE_GUN_RECIPE,
    arcane_device_recipe,
    fireball_cannon_recipe,
)
from dnd.items.spell_items import (
    FIREBALL_SCROLL_RECIPE,
    FIRE_BOLT_SCROLL_RECIPE,
    HOLD_PERSON_SCROLL_RECIPE,
    MAGE_ARMOR_SCROLL_RECIPE,
    MAGIC_MISSILE_SCROLL_RECIPE,
    SpellGrantingItem,
    SPIKE_GROWTH_SCROLL_RECIPE,
    fire_bolt_scroll_recipe,
    magic_missile_scroll_recipe,
    wand_of_fire_recipe,
    wand_of_magic_missiles_recipe,
)
from dnd.items.environment_interactables import ArcaneDevice
from dnd.items.weapons import SHORTSWORD_RECIPE
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spells.evocation import Fireball
from tests.engine.support import (
    force_attack_hit,
    force_spell_attack_hit,
    get_hp,
    remove_attack_modifier,
    remove_spell_attack_modifier,
    reset_combat_state,
    set_hp,
)


THIS_FILE = "tests/manual/test_131_inventory_use_actions_legacy_contract.py"
BOOK_ITEMS_FILE = "tests/engine/test_items_inventory_equipment.py"

SCROLL_DISCOVERY_SELECTOR = (
    f"{THIS_FILE}::test_scroll_targeting_matrix_is_item_bound"
)
SCROLL_EXECUTION_SELECTOR = (
    f"{THIS_FILE}::test_scroll_execute_by_index_consumes_item_not_spell_slots"
)
MISSILE_SCALING_SELECTOR = (
    f"{THIS_FILE}::test_magic_missile_scroll_level_controls_dart_count"
)
POTION_SELECTOR = (
    f"{BOOK_ITEMS_FILE}::test_eb_13_008_consumable_use_actions_consume_charges_and_stacks"
)
COAT_SELECTOR = (
    f"{THIS_FILE}::test_permanent_weapon_coat_discovery_damage_and_cleanup"
)
WAND_DEPLETION_SELECTOR = (
    f"{THIS_FILE}::test_magic_missile_wand_depletes_without_destroying_item"
)
WAND_FIRE_SELECTOR = (
    f"{THIS_FILE}::test_wand_of_fire_enforces_per_spell_charge_costs"
)
WAND_FIRE_LEVEL_SELECTOR = (
    f"{THIS_FILE}::test_wand_fireballs_preserve_explicit_level_and_variant_isolation"
)
MACHINE_GUN_SELECTOR = (
    f"{THIS_FILE}::test_arcane_machine_gun_is_repeatable_environment_spell_source"
)
CANNON_SELECTOR = (
    f"{THIS_FILE}::test_fireball_cannon_depletes_and_disappears_from_discovery"
)
DEVICE_SELECTOR = (
    f"{THIS_FILE}::test_environment_actions_require_range_and_arcana_proficiency"
)
FIREBALL_SELECTOR = (
    f"{THIS_FILE}::test_fireball_scroll_resolves_both_save_branches_and_consumes"
)
BURNING_HANDS_SELECTOR = (
    f"{THIS_FILE}::test_wand_burning_hands_preserves_direction_and_damage"
)
HOLD_PERSON_SELECTOR = (
    f"{THIS_FILE}::test_hold_person_scroll_owns_concentration_cleanup"
)
SPIKE_GROWTH_SELECTOR = (
    f"{THIS_FILE}::test_spike_growth_scroll_owns_entry_damage_and_terrain_cleanup"
)
MAGE_BOLT_SELECTOR = (
    f"{THIS_FILE}::test_mage_armor_and_fire_bolt_scroll_effects"
)
COAT_LIFETIME_SELECTOR = (
    f"{THIS_FILE}::test_weapon_coat_concentration_and_timed_lifetimes"
)


LEGACY_CASE_TO_ACTIVE_SELECTOR: dict[str, str] = {
    "test_scroll_fireball_aoe_discovery": SCROLL_DISCOVERY_SELECTOR,
    "test_scroll_fireball_execute": FIREBALL_SELECTOR,
    "test_scroll_magic_missile_multi_discovery": SCROLL_DISCOVERY_SELECTOR,
    "test_scroll_magic_missile_execute": SCROLL_EXECUTION_SELECTOR,
    "test_scroll_hold_person_entity": SCROLL_DISCOVERY_SELECTOR,
    "test_scroll_mage_armor_self": SCROLL_DISCOVERY_SELECTOR,
    "test_scroll_spike_growth_zone": SPIKE_GROWTH_SELECTOR,
    "test_scroll_fire_bolt_cantrip": SCROLL_DISCOVERY_SELECTOR,
    "test_scroll_magic_missile_level_scaling": MISSILE_SCALING_SELECTOR,
    "test_scroll_no_spell_slot_consumed": SCROLL_EXECUTION_SELECTOR,
    "test_potion_heals_and_consumed": POTION_SELECTOR,
    "test_weapon_coat_applies_condition": COAT_SELECTOR,
    "test_weapon_coat_consumed_after_use": COAT_SELECTOR,
    "test_scroll_consumed_removed_from_inventory": SCROLL_EXECUTION_SELECTOR,
    "test_wand_multi_charge_depletion": WAND_DEPLETION_SELECTOR,
    "test_wand_not_destroyed_when_depleted": WAND_DEPLETION_SELECTOR,
    "test_wand_of_fire_multiple_spells": WAND_FIRE_SELECTOR,
    "test_wand_of_fire_charge_cost_consumption": WAND_FIRE_SELECTOR,
    "test_wand_of_fire_insufficient_charges": WAND_FIRE_SELECTOR,
    "test_arcane_machine_gun_discovery": MACHINE_GUN_SELECTOR,
    "test_arcane_machine_gun_execute": MACHINE_GUN_SELECTOR,
    "test_fireball_cannon_discovery": CANNON_SELECTOR,
    "test_fireball_cannon_execute_and_charges": CANNON_SELECTOR,
    "test_arcane_device_proficiency_required": DEVICE_SELECTOR,
    "test_arcane_device_proficiency_met": DEVICE_SELECTOR,
    "test_environment_out_of_range": DEVICE_SELECTOR,
    "test_execute_by_index_item_routing": SCROLL_EXECUTION_SELECTOR,
    "test_scroll_fireball_actual_damage": FIREBALL_SELECTOR,
    "test_scroll_fireball_save_halves_damage": FIREBALL_SELECTOR,
    "test_wand_burning_hands_actual_damage": BURNING_HANDS_SELECTOR,
    "test_wand_burning_hands_cone_direction": BURNING_HANDS_SELECTOR,
    "test_scroll_hold_person_applies_paralyzed": HOLD_PERSON_SELECTOR,
    "test_scroll_hold_person_concentration_cleanup": HOLD_PERSON_SELECTOR,
    "test_scroll_spike_growth_zone_movement_damage": SPIKE_GROWTH_SELECTOR,
    "test_scroll_spike_growth_concentration_cleanup": SPIKE_GROWTH_SELECTOR,
    "test_scroll_magic_missile_actual_damage_range": MISSILE_SCALING_SELECTOR,
    "test_scroll_magic_missile_upcast_more_darts": MISSILE_SCALING_SELECTOR,
    "test_scroll_mage_armor_ac_formula": MAGE_BOLT_SELECTOR,
    "test_scroll_fire_bolt_damage_on_hit": MAGE_BOLT_SELECTOR,
    "test_weapon_coat_adds_fire_dice_to_weapon": COAT_SELECTOR,
    "test_weapon_coat_no_weapon_not_discovered": COAT_SELECTOR,
    "test_weapon_coat_cleanup_removes_dice": COAT_SELECTOR,
    "test_weapon_coat_two_actions_available": COAT_SELECTOR,
    "test_flaming_weapon_spell_concentration": COAT_LIFETIME_SELECTOR,
    "test_timed_coat_expires_after_rounds": COAT_LIFETIME_SELECTOR,
    "test_timed_coat_active_during_duration": COAT_LIFETIME_SELECTOR,
    "test_wand_of_fire_fireball_deals_damage": WAND_FIRE_LEVEL_SELECTOR,
}


def reset_item_arena(width: int = 20, height: int = 20) -> None:
    """Reset engine-global state and create one rectangular floor."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, width, height)


def create_caster(
    position: tuple[int, int],
    *,
    name: str = "Wizard",
    faction: str = "heroes",
    intelligence: int = 18,
    arcana_proficient: bool = False,
) -> Entity:
    """Create a durable legal caster with explicit slots and item actions."""
    actor_uuid = uuid4()
    actor = Entity.create(
        source_entity_uuid=actor_uuid,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=14),
                intelligence=AbilityConfig(ability_score=intelligence),
                wisdom=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=12,
                        hit_dice_count=20,
                        mode="maximums",
                    )
                ],
            ),
            action_economy=ActionEconomyConfig(
                spell_slots={1: 4, 2: 3, 3: 2, 4: 1},
            ),
            spellcasting=SpellcastingConfig(
                spellcasting_ability="intelligence",
            ),
            skill_set=SkillSetConfig(
                arcana=SkillConfig(proficiency=arcana_proficient),
            ),
            equipment=EquipmentConfig(),
            proficiency_bonus=4,
            position=position,
            faction=faction,
        ),
    )
    setup_standard_actions(actor)
    return actor


def create_target(
    position: tuple[int, int],
    *,
    name: str = "Target",
    faction: str = "monsters",
) -> Entity:
    """Create a durable target with explicit save blocks."""
    target_uuid = uuid4()
    target = Entity.create(
        source_entity_uuid=target_uuid,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=10),
                constitution=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=12,
                        hit_dice_count=20,
                        mode="maximums",
                    )
                ],
            ),
            action_economy=ActionEconomyConfig(),
            equipment=EquipmentConfig(),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
    )
    setup_standard_actions(target)
    return target


def force_save(
    target: Entity,
    ability_name: AbilityName,
    *,
    succeeds: bool,
) -> None:
    """Force a noncritical pass/fail margin while retaining a real d20 event."""
    modifier = NumericalModifier.create(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        name=f"Inventory regression {ability_name} save",
        value=100 if succeeds else -100,
    )
    target.saving_throws.get_saving_throw(ability_name).bonus.self_static.add_value_modifier(
        modifier
    )


def put_in_inventory(entity: Entity, item: BaseItem) -> None:
    """Use the entity lifecycle so item location and ownership stay canonical."""
    assert entity.loot_item(item)


def item_action(
    entity: Entity,
    item_uuid: UUID,
    name: str,
    *,
    target_type: TargetType | None = None,
) -> AvailableActionInfo:
    """Find one current discovery row bound to the exact source item."""
    for info in get_available_actions(entity).all_actions:
        if (
            info.is_item_use
            and info.source_item_uuid == item_uuid
            and name in info.template_name
            and (target_type is None or info.target_type is target_type)
        ):
            return info
    raise AssertionError(f"No {name!r} action was bound to item {item_uuid}")


def target_hitting(
    info: AvailableActionInfo,
    *entity_uuids: UUID,
    excluding: UUID | None = None,
) -> AvailableTarget:
    """Pick a preview row that includes every requested actor."""
    for target in info.valid_targets:
        affected = set(target.affected_entity_uuids or [])
        if set(entity_uuids) <= affected and (
            excluding is None or excluding not in affected
        ):
            return target
    raise AssertionError(
        f"No {info.template_name!r} preview affected {entity_uuids}"
    )


def test_legacy_inventory_use_manifest_accounts_for_all_47_cases() -> None:
    """Every displaced named case has one explicit maintained selector."""
    assert len(LEGACY_CASE_TO_ACTIVE_SELECTOR) == 47
    assert all(case.startswith("test_") for case in LEGACY_CASE_TO_ACTIVE_SELECTOR)
    assert all(
        selector.startswith("tests/") and "::test_" in selector
        for selector in LEGACY_CASE_TO_ACTIVE_SELECTOR.values()
    )


def test_scroll_targeting_matrix_is_item_bound() -> None:
    """Every scroll family retains its target shape, owner, and valid targets."""
    reset_item_arena()
    caster = create_caster((1, 5))
    target = create_target((5, 5))
    scrolls = {
        "Fireball": materialize_item(
            FIREBALL_SCROLL_RECIPE,
            caster.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=SpellGrantingItem,
        ),
        "Magic Missile": materialize_item(
            MAGIC_MISSILE_SCROLL_RECIPE,
            caster.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=SpellGrantingItem,
        ),
        "Hold Person": materialize_item(
            HOLD_PERSON_SCROLL_RECIPE,
            caster.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=SpellGrantingItem,
        ),
        "Mage Armor": materialize_item(
            MAGE_ARMOR_SCROLL_RECIPE,
            caster.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=SpellGrantingItem,
        ),
        "Spike Growth": materialize_item(
            SPIKE_GROWTH_SCROLL_RECIPE,
            caster.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=SpellGrantingItem,
        ),
        "Fire Bolt": materialize_item(
            FIRE_BOLT_SCROLL_RECIPE,
            caster.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=SpellGrantingItem,
        ),
    }
    for scroll in scrolls.values():
        put_in_inventory(caster, scroll)
    Entity.update_all_entities_senses()

    expected = {
        "Fireball": TargetType.POSITION_AOE,
        "Magic Missile": TargetType.MULTI_ENTITY,
        "Hold Person": TargetType.ENTITY,
        "Mage Armor": TargetType.ENTITY,
        "Spike Growth": TargetType.POSITION,
        "Fire Bolt": TargetType.ENTITY,
    }
    for name, target_type in expected.items():
        info = item_action(
            caster,
            scrolls[name].uuid,
            name,
            target_type=target_type,
        )
        assert info.source_item_uuid == scrolls[name].uuid
        assert info.valid_targets

    mage_armor = item_action(caster, scrolls["Mage Armor"].uuid, "Mage Armor")
    assert any(row.target_uuid == caster.uuid for row in mage_armor.valid_targets)
    magic_missile = item_action(
        caster,
        scrolls["Magic Missile"].uuid,
        "Magic Missile",
    )
    assert any(row.target_uuid == target.uuid for row in magic_missile.valid_targets)


def test_scroll_execute_by_index_consumes_item_not_spell_slots() -> None:
    """Controller routing consumes the scroll while leaving caster slots intact."""
    reset_item_arena()
    caster = create_caster((1, 5))
    target = create_target((4, 5))
    scroll = materialize_item(
        MAGIC_MISSILE_SCROLL_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=SpellGrantingItem,
    )
    put_in_inventory(caster, scroll)
    Entity.update_all_entities_senses()
    slots_before = {
        level: caster.action_economy.spell_slot_value(level).normalized_score
        for level in range(1, 5)
    }
    info = item_action(caster, scroll.uuid, "Magic Missile")
    target_row = next(
        row for row in info.valid_targets if row.target_uuid == target.uuid
    )
    hp_before = get_hp(target)

    with fixed_dice_faces(2, 2, 2):
        result = execute_by_index(
            caster,
            info.template_name,
            target_row.index,
            available=get_available_actions(caster),
        )

    assert result is not None and not result.canceled
    assert get_hp(target) == hp_before - 9
    assert scroll.uuid not in caster.inventory.items
    assert BaseBlock.get(scroll.uuid) is None
    assert {
        level: caster.action_economy.spell_slot_value(level).normalized_score
        for level in range(1, 5)
    } == slots_before


def test_magic_missile_scroll_level_controls_dart_count() -> None:
    """Fixed-level scroll variants own three versus five projectile rolls."""
    damages: dict[int, int] = {}
    for cast_level, dart_count in ((1, 3), (3, 5)):
        reset_item_arena()
        caster = create_caster((1, 5))
        target = create_target((4, 5))
        scroll = materialize_item(
            magic_missile_scroll_recipe(cast_level=cast_level),
            caster.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=SpellGrantingItem,
        )
        put_in_inventory(caster, scroll)
        Entity.update_all_entities_senses()
        info = item_action(caster, scroll.uuid, "Magic Missile")
        target_row = next(
            row for row in info.valid_targets if row.target_uuid == target.uuid
        )
        hp_before = get_hp(target)

        with fixed_dice_faces(*([2] * dart_count)):
            result = execute_use_action(
                caster,
                scroll.uuid,
                info.template_name,
                target_row,
            )

        assert result is not None and not result.canceled
        damages[cast_level] = hp_before - get_hp(target)

    assert damages == {1: 9, 3: 15}


def test_permanent_weapon_coat_discovery_damage_and_cleanup() -> None:
    """Coat actions follow equipped slots and own one removable fire packet."""
    reset_item_arena()
    caster = create_caster((3, 3))
    target = create_target((4, 3))
    coat = materialize_item(
        FIRE_WEAPON_COAT_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    put_in_inventory(caster, coat)
    Entity.update_all_entities_senses()
    unavailable_coat_actions = [
        info
        for info in get_available_actions(caster).self_actions
        if info.source_item_uuid == coat.uuid
    ]
    assert {
        info.template_name.split("__item_")[0]
        for info in unavailable_coat_actions
    } == {
        "Coat Main Hand",
        "Coat Off Hand",
    }
    assert all(
        info.availability_status == "requirements_unmet"
        and info.can_afford
        and info.valid_targets == []
        for info in unavailable_coat_actions
    )

    main = materialize_item(
        SHORTSWORD_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    off = materialize_item(
        SHORTSWORD_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert caster.equipment.equip(main, WeaponSlot.MELEE_MAIN)
    assert caster.equipment.equip(off, WeaponSlot.MELEE_OFF)
    actions = [
        info
        for info in get_available_actions(caster).self_actions
        if info.source_item_uuid == coat.uuid
    ]
    assert {info.template_name.split("__item_")[0] for info in actions} == {
        "Coat Main Hand",
        "Coat Off Hand",
    }
    main_action = next(
        info for info in actions if info.template_name.startswith("Coat Main Hand")
    )

    result = execute_use_action(caster, coat.uuid, main_action.template_name)

    assert result is not None and not result.canceled
    assert coat.uuid not in caster.inventory.items
    assert BaseBlock.get(coat.uuid) is None
    assert "Flaming Coat" in caster.active_conditions
    assert main.extra_damage_dices == [6]
    assert main.extra_damage_type == [DamageType.FIRE]
    assert off.extra_damage_dices == []

    caster.action_economy.reset_all_costs()
    modifier_uuid = force_attack_hit(caster)
    attack = next(
        info
        for info in get_available_actions(caster).entity_actions
        if info.template_name == "Attack_MELEE_MAIN"
        and any(row.target_uuid == target.uuid for row in info.valid_targets)
    )
    target_row = next(
        row for row in attack.valid_targets if row.target_uuid == target.uuid
    )
    hp_before = get_hp(target)
    with fixed_dice_faces(10, 4, 3):
        attack_result = execute_action(
            caster,
            attack.template_name,
            target_row,
        )
    remove_attack_modifier(caster, modifier_uuid)

    assert attack_result is not None and not attack_result.canceled
    assert get_hp(target) < hp_before

    caster.remove_condition("Flaming Coat")

    assert main.extra_damage_dices == []
    assert main.extra_damage_type == []


def test_magic_missile_wand_depletes_without_destroying_item() -> None:
    """A finite nonconsumable wand remains registered after its last charge."""
    reset_item_arena()
    caster = create_caster((1, 5))
    target = create_target((4, 5))
    wand = materialize_item(
        wand_of_magic_missiles_recipe(charges=3),
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=SpellGrantingItem,
    )
    put_in_inventory(caster, wand)
    Entity.update_all_entities_senses()

    for _ in range(3):
        info = item_action(caster, wand.uuid, "Magic Missile")
        target_row = next(
            row for row in info.valid_targets if row.target_uuid == target.uuid
        )
        with fixed_dice_faces(2, 2, 2):
            result = execute_use_action(
                caster,
                wand.uuid,
                info.template_name,
                target_row,
            )
        assert result is not None and not result.canceled
        caster.action_economy.reset_all_costs()

    assert wand.charges == 0
    assert caster.inventory.has_item(wand.uuid)
    assert BaseBlock.get(wand.uuid) is wand
    assert all(
        info.source_item_uuid != wand.uuid
        for info in get_available_actions(caster).all_actions
    )


def test_wand_of_fire_enforces_per_spell_charge_costs() -> None:
    """The wand publishes and spends one-, three-, and four-charge variants."""
    reset_item_arena()
    caster = create_caster((5, 5))
    target = create_target((7, 5))
    force_save(target, "dexterity", succeeds=False)
    wand = materialize_item(
        wand_of_fire_recipe(charges=7),
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=SpellGrantingItem,
    )
    put_in_inventory(caster, wand)
    Entity.update_all_entities_senses()
    rows = [
        info
        for info in get_available_actions(caster).position_actions
        if info.source_item_uuid == wand.uuid
    ]

    assert {
        (
            info.base_template_name,
            info.item_charge_cost,
            info.cast_at_level,
        )
        for info in rows
    } == {
        ("Burning Hands", 1, 1),
        ("Fireball", 3, 3),
        ("Fireball", 4, 4),
    }

    burning = next(info for info in rows if info.item_charge_cost == 1)
    with fixed_dice_faces(10, 4, 4, 4):
        result = execute_use_action(
            caster,
            wand.uuid,
            burning.template_name,
            target_hitting(burning, target.uuid),
        )
    assert result is not None and not result.canceled
    assert wand.charges == 6

    caster.action_economy.reset_all_costs()
    fireball = next(
        info
        for info in get_available_actions(caster).position_actions
        if info.source_item_uuid == wand.uuid and info.item_charge_cost == 3
    )
    hp_before = get_hp(target)
    with fixed_dice_faces(10, *([4] * 8)):
        result = execute_use_action(
            caster,
            wand.uuid,
            fireball.template_name,
            target_hitting(
                fireball,
                target.uuid,
                excluding=caster.uuid,
            ),
        )
    assert result is not None and not result.canceled
    assert get_hp(target) == hp_before - 32
    assert wand.charges == 3

    wand.charges = 2
    caster.action_economy.reset_all_costs()
    remaining = [
        info
        for info in get_available_actions(caster).all_actions
        if info.source_item_uuid == wand.uuid
    ]
    assert {info.item_charge_cost for info in remaining} == {1}


def test_wand_fireballs_preserve_explicit_level_and_variant_isolation() -> None:
    """Three/four charges cast L3/L4 without slots or cross-variant mutation."""
    for charge_cost, cast_level, dice_count in ((3, 3, 8), (4, 4, 9)):
        reset_item_arena()
        caster = create_caster((5, 5))
        target = create_target((8, 5))
        force_save(target, "dexterity", succeeds=False)
        wand = materialize_item(
            wand_of_fire_recipe(charges=7),
            caster.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=SpellGrantingItem,
        )
        put_in_inventory(caster, wand)
        Entity.update_all_entities_senses()
        slots_before = {
            level: caster.action_economy.spell_slot_value(
                level
            ).normalized_score
            for level in range(1, 5)
        }
        available = get_available_actions(caster)
        rows = {
            info.item_charge_cost: info
            for info in available.position_actions
            if (
                info.source_item_uuid == wand.uuid
                and isinstance(info.execution_template, Fireball)
            )
        }
        assert set(rows) == {3, 4}
        assert rows[3].cast_at_level == 3
        assert rows[4].cast_at_level == 4
        assert rows[3].template_name != rows[4].template_name
        assert rows[3].execution_template is not rows[4].execution_template
        selected = rows[charge_cost]
        template = selected.execution_template
        assert isinstance(template, SpellAction)
        assert isinstance(template, Fireball)
        assert template.cast_at_level == cast_level
        assert template.get_damage_dice_count() == dice_count
        preview = target_hitting(
            selected,
            target.uuid,
            excluding=caster.uuid,
        )
        hp_before = get_hp(target)

        with fixed_dice_faces(10, *([4] * dice_count)):
            result = execute_by_index(
                caster,
                selected.template_name,
                preview.index,
                available=available,
            )

        assert result is not None and not result.canceled
        assert hp_before - get_hp(target) == dice_count * 4
        assert wand.charges == 7 - charge_cost
        assert {
            level: caster.action_economy.spell_slot_value(
                level
            ).normalized_score
            for level in range(1, 5)
        } == slots_before

        source_fireballs = {
            action.charge_cost: action
            for action in wand.use_action_templates
            if isinstance(action, Fireball)
        }
        assert set(source_fireballs) == {3, 4}
        assert source_fireballs[3].cast_at_level == 3
        assert source_fireballs[4].cast_at_level == 4
        assert source_fireballs[3].get_damage_dice_count() == 8
        assert source_fireballs[4].get_damage_dice_count() == 9

        remaining_rows = {
            info.item_charge_cost: info
            for info in get_available_actions(caster).position_actions
            if (
                info.source_item_uuid == wand.uuid
                and isinstance(info.execution_template, Fireball)
            )
        }
        if charge_cost == 3:
            assert set(remaining_rows) == {3, 4}
        else:
            assert set(remaining_rows) == {3}
        assert all(
            info.cast_at_level == remaining_charge_cost
            for remaining_charge_cost, info in remaining_rows.items()
        )
        assert all(
            info.availability_status == "source_unaffordable"
            and not info.can_afford
            and info.valid_targets == []
            for info in remaining_rows.values()
        )


def test_arcane_machine_gun_is_repeatable_environment_spell_source() -> None:
    """An adjacent unlimited source executes without entering inventory."""
    reset_item_arena()
    caster = create_caster((1, 5))
    target = create_target((4, 5))
    gun = materialize_item(
        ARCANE_MACHINE_GUN_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=SpellGrantingItem,
    )
    gun.place_on_grid((2, 5))
    Entity.update_all_entities_senses()
    info = item_action(caster, gun.uuid, "Magic Missile")

    assert info.target_type is TargetType.MULTI_ENTITY
    assert not caster.inventory.has_item(gun.uuid)
    hp_before = get_hp(target)
    target_row = next(
        row for row in info.valid_targets if row.target_uuid == target.uuid
    )
    with fixed_dice_faces(2, 2, 2):
        result = execute_use_action(
            caster,
            gun.uuid,
            info.template_name,
            target_row,
        )

    assert result is not None and not result.canceled
    assert get_hp(target) == hp_before - 9
    assert gun.charges == -1
    caster.action_economy.reset_all_costs()
    assert item_action(caster, gun.uuid, "Magic Missile") is not None


def test_fireball_cannon_depletes_and_disappears_from_discovery() -> None:
    """Each cannon shot consumes one charge; the third closes discovery."""
    reset_item_arena()
    caster = create_caster((1, 5))
    create_target((8, 5))
    cannon = materialize_item(
        fireball_cannon_recipe(charges=3),
        caster.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=SpellGrantingItem,
    )
    cannon.place_on_grid((2, 5))
    Entity.update_all_entities_senses()

    for expected_charges in (2, 1, 0):
        info = item_action(caster, cannon.uuid, "Fireball")
        assert info.target_type is TargetType.POSITION_AOE
        result = execute_use_action(
            caster,
            cannon.uuid,
            info.template_name,
            info.valid_targets[0],
        )
        assert result is not None and not result.canceled
        assert cannon.charges == expected_charges
        caster.action_economy.reset_all_costs()

    assert BaseBlock.get(cannon.uuid) is cannon
    assert all(
        info.source_item_uuid != cannon.uuid
        for info in get_available_actions(caster).all_actions
    )


def test_environment_actions_require_range_and_arcana_proficiency() -> None:
    """Environment item discovery enforces both actor and spatial predicates."""
    reset_item_arena()
    novice = create_caster((1, 5), name="Novice")
    adjacent_device = materialize_item(
        arcane_device_recipe(),
        novice.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=ArcaneDevice,
    )
    adjacent_device.place_on_grid((2, 5))
    far_gun = materialize_item(
        ARCANE_MACHINE_GUN_RECIPE,
        novice.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=SpellGrantingItem,
    )
    far_gun.place_on_grid((4, 5))
    Entity.update_all_entities_senses()
    novice_sources = {
        info.source_item_uuid
        for info in get_available_actions(novice).all_actions
        if info.is_item_use
    }

    assert adjacent_device.uuid not in novice_sources
    assert far_gun.uuid not in novice_sources

    reset_item_arena()
    scholar = create_caster(
        (1, 5),
        name="Scholar",
        arcana_proficient=True,
    )
    device = materialize_item(
        arcane_device_recipe(),
        scholar.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=ArcaneDevice,
    )
    device.place_on_grid((2, 5))
    set_hp(scholar, 50)
    Entity.update_all_entities_senses()
    info = item_action(scholar, device.uuid, "Activate Device")

    result = execute_use_action(
        scholar,
        device.uuid,
        info.template_name,
    )

    assert result is not None and not result.canceled
    assert get_hp(scholar) > 50


def test_fireball_scroll_resolves_both_save_branches_and_consumes() -> None:
    """One item-backed AoE applies full and half damage under one action."""
    reset_item_arena()
    caster = create_caster((1, 5))
    failing = create_target((5, 5), name="Failing")
    passing = create_target((6, 5), name="Passing")
    force_save(failing, "dexterity", succeeds=False)
    force_save(passing, "dexterity", succeeds=True)
    scroll = materialize_item(
        FIREBALL_SCROLL_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=SpellGrantingItem,
    )
    put_in_inventory(caster, scroll)
    Entity.update_all_entities_senses()
    info = item_action(caster, scroll.uuid, "Fireball")
    preview = target_hitting(
        info,
        failing.uuid,
        passing.uuid,
        excluding=caster.uuid,
    )
    hp_before = {
        failing.uuid: get_hp(failing),
        passing.uuid: get_hp(passing),
    }

    with fixed_dice_faces(
        10,
        *([4] * 8),
        10,
        *([4] * 8),
    ):
        result = execute_use_action(
            caster,
            scroll.uuid,
            info.template_name,
            preview,
        )

    assert result is not None and not result.canceled
    assert hp_before[failing.uuid] - get_hp(failing) == 32
    assert hp_before[passing.uuid] - get_hp(passing) == 16
    assert scroll.uuid not in caster.inventory.items
    assert BaseBlock.get(scroll.uuid) is None


def test_wand_burning_hands_preserves_direction_and_damage() -> None:
    """The chosen cone damages its included target but not the opposite side."""
    reset_item_arena()
    caster = create_caster((5, 5))
    east = create_target((7, 5), name="East")
    west = create_target((3, 5), name="West")
    force_save(east, "dexterity", succeeds=False)
    wand = materialize_item(
        wand_of_fire_recipe(),
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=SpellGrantingItem,
    )
    put_in_inventory(caster, wand)
    Entity.update_all_entities_senses()
    info = item_action(caster, wand.uuid, "Burning Hands")
    preview = target_hitting(info, east.uuid, excluding=west.uuid)
    east_hp = get_hp(east)
    west_hp = get_hp(west)

    with fixed_dice_faces(10, 4, 4, 4):
        result = execute_use_action(
            caster,
            wand.uuid,
            info.template_name,
            preview,
        )

    assert result is not None and not result.canceled
    assert east_hp - get_hp(east) == 12
    assert get_hp(west) == west_hp
    assert wand.charges == 6


def test_hold_person_scroll_owns_concentration_cleanup() -> None:
    """A failed item-backed save links Paralyzed to caster concentration."""
    reset_item_arena()
    caster = create_caster((1, 5))
    target = create_target((4, 5), name="Held")
    force_save(target, "wisdom", succeeds=False)
    scroll = materialize_item(
        HOLD_PERSON_SCROLL_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=SpellGrantingItem,
    )
    put_in_inventory(caster, scroll)
    Entity.update_all_entities_senses()
    info = item_action(caster, scroll.uuid, "Hold Person")
    target_row = next(
        row for row in info.valid_targets if row.target_uuid == target.uuid
    )

    with fixed_dice_faces(10):
        result = execute_use_action(
            caster,
            scroll.uuid,
            info.template_name,
            target_row,
        )

    assert result is not None and not result.canceled
    assert "Hold Person" in target.active_conditions
    assert "Paralyzed" in target.active_conditions
    assert "Concentrating" in caster.active_conditions
    assert BaseBlock.get(scroll.uuid) is None

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Hold Person" not in target.active_conditions
    assert "Paralyzed" not in target.active_conditions


def test_spike_growth_scroll_owns_entry_damage_and_terrain_cleanup() -> None:
    """The scroll creates one linked zone whose terrain and damage both clean."""
    reset_item_arena()
    grid = get_map()
    caster = create_caster((1, 5))
    target = create_target((15, 5), name="Zone Victim")
    scroll = materialize_item(
        SPIKE_GROWTH_SCROLL_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=SpellGrantingItem,
    )
    put_in_inventory(caster, scroll)
    Entity.update_all_entities_senses()
    info = item_action(caster, scroll.uuid, "Spike Growth")
    preview = next(
        (
            row
            for row in info.valid_targets
            if row.position == (10, 5)
        ),
        info.valid_targets[0],
    )
    assert preview.position is not None

    result = execute_use_action(
        caster,
        scroll.uuid,
        info.template_name,
        preview,
    )

    assert result is not None and not result.canceled
    assert "Concentrating" in caster.active_conditions
    matches = [
        condition
        for condition in get_map().get_spatial_conditions()
        if condition.name == "Spike Growth Zone"
    ]
    assert len(matches) == 1
    condition = matches[0]
    assert isinstance(condition, AreaCondition)
    assert (condition.uuid, condition.uuid) in caster.active_conditions[
        "Concentrating"
    ].linked_conditions
    tile = grid.get_tile(*preview.position)
    assert tile is not None
    assert tile.walking_cost.normalized_score >= 2
    hp_before = get_hp(target)

    with fixed_dice_faces(4, 4):
        Entity.update_entity_position(target, preview.position)

    assert hp_before - get_hp(target) == 8

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert BaseCondition.get(effect.uuid) is None
    assert tile.walking_cost.normalized_score == 1


def test_mage_armor_and_fire_bolt_scroll_effects() -> None:
    """Self-buff and attack-roll scrolls retain their concrete spell effects."""
    reset_item_arena()
    caster = create_caster((1, 5))
    mage_armor = materialize_item(
        MAGE_ARMOR_SCROLL_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=SpellGrantingItem,
    )
    put_in_inventory(caster, mage_armor)
    Entity.update_all_entities_senses()
    armor_info = item_action(caster, mage_armor.uuid, "Mage Armor")
    self_row = next(
        row for row in armor_info.valid_targets if row.target_uuid == caster.uuid
    )
    ac_before = caster.ac_bonus().normalized_score

    result = execute_use_action(
        caster,
        mage_armor.uuid,
        armor_info.template_name,
        self_row,
    )

    assert result is not None and not result.canceled
    assert caster.ac_bonus().normalized_score == ac_before + 3
    assert "Mage Armor" in caster.active_conditions
    assert BaseBlock.get(mage_armor.uuid) is None

    reset_item_arena()
    caster = create_caster((1, 5))
    target = create_target((4, 5))
    fire_bolt = materialize_item(
        fire_bolt_scroll_recipe(caster_level=5),
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=SpellGrantingItem,
    )
    put_in_inventory(caster, fire_bolt)
    Entity.update_all_entities_senses()
    modifier_uuid = force_spell_attack_hit(caster)
    bolt_info = item_action(caster, fire_bolt.uuid, "Fire Bolt")
    target_row = next(
        row for row in bolt_info.valid_targets if row.target_uuid == target.uuid
    )
    hp_before = get_hp(target)

    with fixed_dice_faces(10, 4, 4):
        result = execute_use_action(
            caster,
            fire_bolt.uuid,
            bolt_info.template_name,
            target_row,
        )
    remove_spell_attack_modifier(caster, modifier_uuid)

    assert result is not None and not result.canceled
    assert hp_before - get_hp(target) == 8
    assert BaseBlock.get(fire_bolt.uuid) is None


def test_weapon_coat_concentration_and_timed_lifetimes() -> None:
    """Concentration and round duration each remove only their coat packet."""
    reset_item_arena()
    caster = create_caster((3, 3))
    sword = materialize_item(
        SHORTSWORD_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert caster.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    concentrating_coat = materialize_item(
        CONCENTRATION_FIRE_WEAPON_COAT_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    put_in_inventory(caster, concentrating_coat)
    Entity.update_all_entities_senses()
    info = item_action(caster, concentrating_coat.uuid, "Coat Main Hand")

    result = execute_use_action(
        caster,
        concentrating_coat.uuid,
        info.template_name,
    )

    assert result is not None and not result.canceled
    assert "Concentrating" in caster.active_conditions
    assert "Flaming Coat" in caster.active_conditions
    assert sword.extra_damage_dices == [6]

    caster.remove_condition("Concentrating")

    assert "Flaming Coat" not in caster.active_conditions
    assert sword.extra_damage_dices == []

    caster.action_economy.reset_all_costs()
    timed_coat = materialize_item(
        timed_fire_weapon_coat_recipe(rounds=3),
        caster.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    put_in_inventory(caster, timed_coat)
    info = item_action(caster, timed_coat.uuid, "Coat Main Hand")
    result = execute_use_action(
        caster,
        timed_coat.uuid,
        info.template_name,
    )
    assert result is not None and not result.canceled

    caster.advance_duration_condition("Flaming Coat")
    assert "Flaming Coat" in caster.active_conditions
    assert sword.extra_damage_dices == [6]

    caster.advance_duration_condition("Flaming Coat")
    assert "Flaming Coat" in caster.active_conditions
    caster.advance_duration_condition("Flaming Coat")

    assert "Flaming Coat" not in caster.active_conditions
    assert sword.extra_damage_dices == []
