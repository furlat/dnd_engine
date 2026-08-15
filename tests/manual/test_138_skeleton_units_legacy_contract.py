"""Deterministic contracts for the displaced specialized-skeleton matrix."""

from dataclasses import dataclass
from typing import Literal

from dnd.actions.operations import (
    execute_by_index,
    execute_use_action,
    get_available_actions,
)
from dnd.blocks.base_item import (
    UsableItem,
)
from dnd.conditions import Hidden
from dnd.core.base_actions import (
    AvailableTarget,
)
from dnd.core.base_block import BaseBlock
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.dice import fixed_dice_faces
from dnd.types.equipment import WeaponSlot
from dnd.core.events.events_registry import (
    Event,
    EventQueue,
)
from dnd.types.damage import DamageType
from dnd.entity import Entity
from dnd.monsters.bestiary import (
    create_skeleton,
    create_skeleton_archer,
    create_skeleton_warlock,
    create_skeleton_warrior,
)
from dnd.monsters.skeleton_abilities import MarkTargetAction
from dnd.spells.evocation import BurningHands, EldritchBlast
from tests.engine.support import (
    deal_damage_to,
    force_attack_hit,
    force_spell_attack_hit,
    get_hp,
    get_max_hp,
    remove_attack_modifier,
    remove_spell_attack_modifier,
    set_hp,
)
from tests.engine.test_monster_presets import (
    get_inventory_item,
    reset_monster_state,
)


CoverageStatus = Literal["active", "strengthened"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived specialized-skeleton case's reviewed replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_138_skeleton_units_legacy_contract.py"
PRESET_INTEGRATION_SELECTOR = (
    f"{THIS_FILE}::"
    "test_specialized_skeleton_presets_preserve_identity_and_arena_interop"
)
ELDRITCH_SELECTOR = f"{THIS_FILE}::test_eldritch_blast_hit_miss_and_range"
ACID_SELECTOR = f"{THIS_FILE}::test_acid_flask_affects_every_creature_in_its_area"
MARK_BASE_SELECTOR = (
    "tests/engine/test_monster_presets.py::"
    "test_eb_17_003_mark_target_creates_concentration_link_and_cleans_target_state"
)
MARK_STEALTH_SELECTOR = (
    "tests/engine/test_monster_presets.py::"
    "test_eb_17_004_mark_target_strips_and_blocks_hidden_or_invisible_state"
)
MARK_CLEANUP_SELECTOR = (
    f"{THIS_FILE}::test_mark_target_damage_death_and_range_boundaries"
)
MARK_STATE_SELECTOR = (
    f"{THIS_FILE}::"
    "test_mark_target_strips_existing_hidden_and_rejects_second_use"
)
STAFF_SELECTOR = f"{THIS_FILE}::test_arcane_staff_modifier_and_melee_attack_lifecycle"
SCROLL_SELECTOR = (
    f"{THIS_FILE}::"
    "test_warlock_invisibility_scroll_applies_effect_without_spell_slots"
)
WARLOCK_SPELL_SELECTOR = (
    f"{THIS_FILE}::test_warlock_burning_hands_spends_only_its_selected_slot"
)


SKELETON_UNITS_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_skeleton_warrior_creation": LegacyCoverage(
        "strengthened",
        PRESET_INTEGRATION_SELECTOR,
        "The maintained integration asserts the warrior's full preset identity inside the shared arena.",
    ),
    "test_skeleton_archer_creation": LegacyCoverage(
        "strengthened",
        PRESET_INTEGRATION_SELECTOR,
        "The maintained integration asserts the archer's equipment, action, stats, and shared-arena visibility.",
    ),
    "test_skeleton_warlock_creation": LegacyCoverage(
        "strengthened",
        PRESET_INTEGRATION_SELECTOR,
        "The maintained integration includes the previously omitted Crown assertion and all warlock preset facts.",
    ),
    "test_eldritch_blast_hit": LegacyCoverage(
        "active",
        ELDRITCH_SELECTOR,
        "The maintained cantrip test forces a hit and asserts damage without spending a slot.",
    ),
    "test_eldritch_blast_miss": LegacyCoverage(
        "active",
        ELDRITCH_SELECTOR,
        "The maintained cantrip test forces a miss and asserts unchanged target HP.",
    ),
    "test_eldritch_blast_range": LegacyCoverage(
        "active",
        ELDRITCH_SELECTOR,
        "The maintained cantrip test rejects a target beyond 120 feet.",
    ),
    "test_acid_flask_single_target": LegacyCoverage(
        "strengthened",
        ACID_SELECTOR,
        "The maintained area test asserts damage to every occupied target cell in one cast.",
    ),
    "test_acid_flask_aoe_multiple_targets": LegacyCoverage(
        "strengthened",
        ACID_SELECTOR,
        "The maintained area test proves both creatures in the flask footprint are damaged.",
    ),
    "test_acid_flask_consumable": LegacyCoverage(
        "strengthened",
        (
            "tests/engine/test_monster_presets.py::"
            "test_eb_17_006_warrior_acid_flask_is_a_consumable_spell_item"
        ),
        "The engine-book contract asserts inventory ownership, one charge, one item action, and damage.",
    ),
    "test_mark_applies_condition": LegacyCoverage(
        "strengthened",
        MARK_BASE_SELECTOR,
        "The maintained contract asserts Marked, Concentrating, cooldown, linkage, and cost.",
    ),
    "test_mark_grants_advantage": LegacyCoverage(
        "strengthened",
        MARK_BASE_SELECTOR,
        "The maintained contract inspects the exact incoming-attack advantage modifier.",
    ),
    "test_mark_strips_existing_invisibility": LegacyCoverage(
        "strengthened",
        MARK_STEALTH_SELECTOR,
        "The maintained contract strips an existing Invisible state and blocks reapplication.",
    ),
    "test_mark_strips_existing_hidden": LegacyCoverage(
        "strengthened",
        MARK_STATE_SELECTOR,
        "The maintained regression starts with Hidden active, then asserts condition and stealth-DC cleanup.",
    ),
    "test_mark_prevents_future_invisibility": LegacyCoverage(
        "strengthened",
        MARK_STEALTH_SELECTOR,
        "The maintained contract asserts Marked's explicit Invisible immunity.",
    ),
    "test_mark_prevents_future_hidden": LegacyCoverage(
        "strengthened",
        MARK_STEALTH_SELECTOR,
        "The maintained contract asserts Marked's explicit Hidden immunity and no stealth residue.",
    ),
    "test_mark_concentration_break": LegacyCoverage(
        "strengthened",
        MARK_BASE_SELECTOR,
        "The maintained contract asserts linked cleanup, immunities, and owned modifier removal.",
    ),
    "test_mark_concentration_break_from_damage": LegacyCoverage(
        "strengthened",
        MARK_CLEANUP_SELECTOR,
        "The maintained regression asserts damage cleanup plus nested save and removal combat logs.",
    ),
    "test_mark_concentration_break_on_death": LegacyCoverage(
        "strengthened",
        MARK_CLEANUP_SELECTOR,
        "The maintained regression asserts lethal cleanup plus nested death and removal combat logs.",
    ),
    "test_mark_bonus_action_cost": LegacyCoverage(
        "strengthened",
        MARK_BASE_SELECTOR,
        "The maintained contract asserts the bonus-action pool reaches zero.",
    ),
    "test_mark_one_use_per_rest": LegacyCoverage(
        "strengthened",
        MARK_STATE_SELECTOR,
        "The maintained regression rejects a second target through discovery and authoritative apply validation.",
    ),
    "test_mark_range": LegacyCoverage(
        "active",
        MARK_CLEANUP_SELECTOR,
        "The maintained contract rejects Mark Target beyond its 60-foot boundary.",
    ),
    "test_arcane_staff_spell_attack_bonus": LegacyCoverage(
        "strengthened",
        STAFF_SELECTOR,
        "The maintained lifecycle asserts exact -1 removal and +1 restoration.",
    ),
    "test_arcane_staff_melee": LegacyCoverage(
        "strengthened",
        STAFF_SELECTOR,
        "The same equipped staff executes a forced-hit melee attack and deals damage.",
    ),
    "test_scroll_of_invisibility_use": LegacyCoverage(
        "strengthened",
        SCROLL_SELECTOR,
        "The preset's actual scroll is executed and asserts Invisible plus the entity capability.",
    ),
    "test_scroll_no_spell_slot": LegacyCoverage(
        "strengthened",
        SCROLL_SELECTOR,
        "The actual scroll leaves both preset spell-slot levels unchanged and destroys only the item.",
    ),
    "test_warlock_burning_hands": LegacyCoverage(
        "strengthened",
        WARLOCK_SPELL_SELECTOR,
        "The maintained test casts twice, damages the target, and exhausts exactly level-one slots.",
    ),
    "test_warlock_slot_exhaustion": LegacyCoverage(
        "strengthened",
        WARLOCK_SPELL_SELECTOR,
        "The maintained test covers Eldritch Blast plus Burning Hands and Thunderwave affordability at both slot levels.",
    ),
    "test_arena_specialized_skeletons": LegacyCoverage(
        "strengthened",
        PRESET_INTEGRATION_SELECTOR,
        "The maintained arena asserts factions, positions, HP ordering, and simultaneous hero visibility.",
    ),
}


def test_skeleton_units_manifest_accounts_for_all_28_cases() -> None:
    """Every displaced specialized-skeleton case has an active selector."""
    assert len(SKELETON_UNITS_LEGACY_CASES) == 28
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for case, row in SKELETON_UNITS_LEGACY_CASES.items()
    )


def _combat_log_types(entry: CombatLogEntry) -> list[CombatLogEntryType]:
    """Flatten one causal combat-log tree in deterministic preorder."""
    result = [entry.entry_type]
    for child in entry.sub_entries:
        result.extend(_combat_log_types(child))
    return result


def _equipped_weapon_name(entity: Entity, slot: WeaponSlot) -> str:
    """Return a required equipped weapon-family item's display name."""
    item = entity.equipment.get_item_by_slot(slot)
    assert item is not None
    assert item.name is not None
    return item.name


def test_specialized_skeleton_presets_preserve_identity_and_arena_interop() -> None:
    """All three presets retain their exact identities in one visible arena."""
    reset_monster_state(width=20, height=15)
    warrior = create_skeleton_warrior(
        name="Skeleton Warrior",
        position=(12, 5),
        faction="monsters",
        darkvision=True,
    )
    archer = create_skeleton_archer(
        name="Skeleton Archer",
        position=(12, 7),
        faction="monsters",
        darkvision=True,
    )
    warlock = create_skeleton_warlock(
        name="Skeleton Warlock",
        position=(12, 9),
        faction="monsters",
        darkvision=True,
    )
    hero = create_skeleton(
        name="Hero",
        position=(3, 7),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=100)

    assert (warrior.faction, archer.faction, warlock.faction, hero.faction) == (
        "monsters",
        "monsters",
        "monsters",
        "heroes",
    )
    assert (warrior.position, archer.position, warlock.position) == (
        (12, 5),
        (12, 7),
        (12, 9),
    )
    assert get_max_hp(warrior) > get_max_hp(archer) > get_max_hp(warlock)
    assert all(
        hero.uuid in monster.senses.entities
        for monster in (warrior, archer, warlock)
    )

    assert warrior.ac_bonus().normalized_score == 15
    assert _equipped_weapon_name(warrior, WeaponSlot.MELEE_MAIN) == "Longsword"
    assert _equipped_weapon_name(warrior, WeaponSlot.MELEE_OFF) == "Wooden Shield"
    assert "Acid Flask" in {
        item.name for item in warrior.inventory.items.values()
    }
    assert "Attack_MELEE_MAIN" in {
        action.name for action in warrior.registered_actions
    }

    assert archer.ac_bonus().normalized_score == 13
    assert archer.ability_scores.dexterity.modifier == 3
    assert _equipped_weapon_name(archer, WeaponSlot.RANGED_MAIN) == "Shortbow"
    assert _equipped_weapon_name(archer, WeaponSlot.MELEE_MAIN) == "Dagger"
    assert _equipped_weapon_name(archer, WeaponSlot.MELEE_OFF) == "Dagger"
    assert {"Mark Target", "Attack_RANGED_MAIN"} <= {
        action.name for action in archer.registered_actions
    }

    assert warlock.is_spellcaster
    assert warlock.ac_bonus().normalized_score == 13
    assert warlock.ability_scores.charisma.modifier == 2
    assert warlock.action_economy.spell_slot_value(1).normalized_score == 2
    assert warlock.action_economy.spell_slot_value(2).normalized_score == 1
    assert _equipped_weapon_name(warlock, WeaponSlot.MELEE_MAIN) == "Arcane Staff"
    assert warlock.equipment.helmet is not None
    assert warlock.equipment.helmet.name == "Crown"
    assert "Scroll of Invisibility" in {
        item.name for item in warlock.inventory.items.values()
    }
    assert {"Eldritch Blast", "Burning Hands", "Thunderwave"} <= {
        action.name for action in warlock.registered_actions
    }


def test_eldritch_blast_hit_miss_and_range() -> None:
    """The preset cantrip hits, misses, and enforces its 120-foot range."""
    reset_monster_state(width=30, height=30)
    warlock = create_skeleton_warlock(
        name="Warlock",
        position=(0, 0),
        faction="monsters",
    )
    target = create_skeleton(
        name="Target",
        position=(10, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=150)
    initial_slots = (
        warlock.action_economy.spell_slot_value(1).normalized_score
    )

    hit_modifier = force_spell_attack_hit(warlock)
    try:
        with fixed_dice_faces(10, 5):
            hit_event = EldritchBlast(
                source_entity_uuid=warlock.uuid,
                target_entity_uuid=target.uuid,
                caster_level=1,
            ).apply()
    finally:
        remove_spell_attack_modifier(warlock, hit_modifier)

    assert hit_event is not None and not hit_event.canceled
    assert get_hp(target) < target.get_max_hp()
    assert (
        warlock.action_economy.spell_slot_value(1).normalized_score
        == initial_slots
    )

    warlock.action_economy.reset_all_costs()
    set_hp(target, target.get_max_hp())
    with fixed_dice_faces(1):
        miss_event = EldritchBlast(
            source_entity_uuid=warlock.uuid,
            target_entity_uuid=target.uuid,
            caster_level=1,
        ).apply()

    assert miss_event is not None and not miss_event.canceled
    assert get_hp(target) == target.get_max_hp()

    reset_monster_state(width=30, height=30)
    warlock = create_skeleton_warlock(
        name="Warlock",
        position=(0, 0),
        faction="monsters",
    )
    target = create_skeleton(
        name="Distant Target",
        position=(25, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=150)
    range_event = EldritchBlast(
        source_entity_uuid=warlock.uuid,
        target_entity_uuid=target.uuid,
        caster_level=1,
    ).apply()

    assert range_event is not None and range_event.canceled


def test_acid_flask_affects_every_creature_in_its_area() -> None:
    """The preset flask's area damages both occupied cells in its footprint."""
    reset_monster_state(width=15, height=15)
    warrior = create_skeleton_warrior(
        name="Warrior",
        position=(0, 0),
        faction="monsters",
    )
    first = create_skeleton(
        name="First Target",
        position=(5, 5),
        faction="heroes",
    )
    second = create_skeleton(
        name="Second Target",
        position=(5, 4),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=100)
    before = (get_hp(first), get_hp(second))
    flask = get_inventory_item(warrior, "Acid Flask")
    action = flask.get_use_actions(warrior.uuid)[0].instantiate(end_position=(5, 5))

    with fixed_dice_faces(*([1] * 20)):
        event = action.apply()

    assert event is not None and not event.canceled
    assert get_hp(first) < before[0]
    assert get_hp(second) < before[1]


def test_mark_target_strips_existing_hidden_and_rejects_second_use() -> None:
    """Mark removes an active Hidden state and cannot bypass its cooldown."""
    reset_monster_state(width=30, height=15)
    archer = create_skeleton_archer(
        name="Archer",
        position=(0, 0),
        faction="monsters",
    )
    first = create_skeleton(
        name="First Target",
        position=(5, 0),
        faction="heroes",
    )
    second = create_skeleton(
        name="Second Target",
        position=(3, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=150)
    first.add_condition(
        Hidden(
            source_entity_uuid=first.uuid,
            target_entity_uuid=first.uuid,
            stealth_result=8,
        )
    )
    Entity.update_all_entities_senses(max_distance=150)

    assert "Hidden" in first.active_conditions
    assert first.stealth_dc == 8
    assert first.uuid in archer.senses.entities

    first_mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=first.uuid,
    ).apply()

    assert first_mark is not None and not first_mark.canceled
    assert "Hidden" not in first.active_conditions
    assert first.stealth_dc is None
    assert "Marked" in first.active_conditions
    assert "Mark Cooldown" in archer.active_conditions

    archer.remove_condition("Concentrating")
    archer.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=150)
    second_mark = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=second.uuid,
    )

    assert not second_mark.pre_validate()
    rejected = second_mark.apply()
    assert rejected is not None and rejected.canceled
    assert "Marked" not in second.active_conditions
    assert "Concentrating" not in archer.active_conditions
    assert "Mark Cooldown" in archer.active_conditions


def test_mark_target_damage_death_and_range_boundaries() -> None:
    """Damage, death, and range all honor Mark Target ownership."""
    reset_monster_state(width=30, height=15)
    archer = create_skeleton_archer(
        name="Archer",
        position=(0, 0),
        faction="monsters",
    )
    target = create_skeleton(
        name="Target",
        position=(5, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=150)
    mark_event = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    ).apply()

    assert mark_event is not None and not mark_event.canceled
    assert "Marked" in target.active_conditions
    set_hp(archer, 500)
    damage_events: list[Event] = []
    EventQueue.set_combat_log_callback(damage_events.append)
    with fixed_dice_faces(1):
        deal_damage_to(
            archer,
            20,
            DamageType.SLASHING,
            target.uuid,
        )
    assert archer.has_hp
    assert "Concentrating" not in archer.active_conditions
    assert "Marked" not in target.active_conditions
    assert len(damage_events) == 1
    damage_log = damage_events[0].combat_log
    assert damage_log is not None
    damage_log_types = _combat_log_types(damage_log)
    assert damage_log_types[0] is CombatLogEntryType.DAMAGE_TAKEN
    assert CombatLogEntryType.SAVING_THROW in damage_log_types
    assert damage_log_types.count(CombatLogEntryType.CONDITION_REMOVED) >= 2

    reset_monster_state(width=30, height=15)
    archer = create_skeleton_archer(
        name="Archer",
        position=(0, 0),
        faction="monsters",
    )
    target = create_skeleton(
        name="Target",
        position=(5, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=150)
    MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=target.uuid,
    ).apply()
    death_events: list[Event] = []
    EventQueue.set_combat_log_callback(death_events.append)
    deal_damage_to(
        archer,
        9999,
        DamageType.SLASHING,
        target.uuid,
    )
    assert not archer.has_hp
    assert "Concentrating" not in archer.active_conditions
    assert "Marked" not in target.active_conditions
    assert len(death_events) == 1
    death_log = death_events[0].combat_log
    assert death_log is not None
    death_log_types = _combat_log_types(death_log)
    assert death_log_types[0] is CombatLogEntryType.DAMAGE_TAKEN
    assert CombatLogEntryType.DEATH in death_log_types
    assert death_log_types.count(CombatLogEntryType.CONDITION_REMOVED) >= 2

    reset_monster_state(width=30, height=15)
    archer = create_skeleton_archer(
        name="Archer",
        position=(0, 0),
        faction="monsters",
    )
    distant = create_skeleton(
        name="Distant Target",
        position=(13, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=150)
    range_event = MarkTargetAction(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=distant.uuid,
    ).apply()
    assert range_event is not None and range_event.canceled


def test_arcane_staff_modifier_and_melee_attack_lifecycle() -> None:
    """The staff owns one spell bonus and remains a functional melee weapon."""
    reset_monster_state(width=15, height=15)
    warlock = create_skeleton_warlock(
        name="Warlock",
        position=(0, 0),
        faction="monsters",
    )
    target = create_skeleton(
        name="Target",
        position=(1, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=75)
    bonus_with_staff = warlock.spellcasting.spell_attack_bonus.normalized_score

    staff = warlock.unequip_item(WeaponSlot.MELEE_MAIN)
    assert staff is not None and staff.name == "Arcane Staff"
    assert (
        warlock.spellcasting.spell_attack_bonus.normalized_score
        == bonus_with_staff - 1
    )
    assert warlock.equip_item(staff.uuid, WeaponSlot.MELEE_MAIN)
    assert (
        warlock.spellcasting.spell_attack_bonus.normalized_score
        == bonus_with_staff
    )

    hit_modifier = force_attack_hit(warlock)
    try:
        before = get_hp(target)
        with fixed_dice_faces(10, 5):
            attack_event = execute_by_index(
                warlock,
                "Attack_MELEE_MAIN",
                0,
            )
    finally:
        remove_attack_modifier(warlock, hit_modifier)

    assert attack_event is not None and not attack_event.canceled
    assert get_hp(target) < before


def test_warlock_invisibility_scroll_applies_effect_without_spell_slots() -> None:
    """The preset scroll applies Invisibility and consumes only itself."""
    reset_monster_state(width=15, height=15)
    warlock = create_skeleton_warlock(
        name="Warlock",
        position=(0, 0),
        faction="monsters",
    )
    Entity.update_all_entities_senses(max_distance=75)
    scroll = next(
        item
        for item in warlock.inventory.items.values()
        if item.name == "Scroll of Invisibility"
    )
    assert isinstance(scroll, UsableItem)
    scroll_uuid = scroll.uuid
    use_actions = scroll.get_use_actions(warlock.uuid)
    assert len(use_actions) == 1
    slots_before = (
        warlock.action_economy.spell_slot_value(1).normalized_score,
        warlock.action_economy.spell_slot_value(2).normalized_score,
    )

    completion = execute_use_action(
        warlock,
        scroll.uuid,
        use_actions[0].get_discovery_template_name(),
        AvailableTarget(
            index=0,
            target_uuid=warlock.uuid,
            target_name=warlock.name,
        ),
    )

    assert completion is not None and not completion.canceled
    assert "Invisible" in warlock.active_conditions
    assert warlock.is_invisible
    assert (
        warlock.action_economy.spell_slot_value(1).normalized_score,
        warlock.action_economy.spell_slot_value(2).normalized_score,
    ) == slots_before
    assert not warlock.inventory.has_item(scroll_uuid)
    assert BaseBlock.get(scroll_uuid) is None


def test_warlock_burning_hands_spends_only_its_selected_slot() -> None:
    """Preset spell variants spend level-one slots and retain level two."""
    reset_monster_state(width=15, height=15)
    warlock = create_skeleton_warlock(
        name="Warlock",
        position=(5, 5),
        faction="monsters",
    )
    target = create_skeleton(
        name="Target",
        position=(6, 5),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=75)

    for _ in range(2):
        before = get_hp(target)
        with fixed_dice_faces(*([1] * 20)):
            event = BurningHands(
                source_entity_uuid=warlock.uuid,
                caster_level=1,
                end_position=target.position,
                cast_at_level=1,
            ).apply()
        assert event is not None and not event.canceled
        assert get_hp(target) < before
        set_hp(target, target.get_max_hp())
        warlock.action_economy.reset_all_costs()

    assert (
        warlock.action_economy.spell_slot_value(1).normalized_score == 0
    )
    assert (
        warlock.action_economy.spell_slot_value(2).normalized_score == 1
    )

    rows = {
        row.template_name: row
        for row in get_available_actions(warlock).all_actions
    }
    assert "Eldritch Blast" in rows
    assert (
        "Burning Hands__slot_1" not in rows
        or not rows["Burning Hands__slot_1"].can_afford
    )
    assert (
        "Thunderwave__slot_1" not in rows
        or not rows["Thunderwave__slot_1"].can_afford
    )
    assert rows["Burning Hands__slot_2"].can_afford
    assert rows["Thunderwave__slot_2"].can_afford
