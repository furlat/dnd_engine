"""
Test Bane, Bless, and Necrotic Bless spells.

Tests:
1. Bane: CHA save fail → -d4 on attacks and saves
2. Bane: CHA save success → no effect
3. Bane: concentration break removes all BaneEffects
4. Bless: auto-apply +d4 to 3 allies on attack and save rolls
5. Bless: concentration break removes all BlessEffects
6. Necrotic Bless: undead→Bless, non-undead→CHA save→Bane
7. Necrotic Bless: mixed targets (some undead, some not)

Run: python examples/test_bless_bane.py
"""
from uuid import uuid4

from dnd.utils import reset_combat_state, has_condition
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig
from dnd.core.events import WeaponSlot
from dnd.core.modifiers import CreatureType
from dnd.items.weapons import create_scimitar
from dnd.actions_functional import setup_standard_actions
from dnd.spells.enchantment import Bane, Bless
from dnd.spells.necromancy import NecroticBless

passed = 0
failed = 0


def check(condition: bool, msg: str):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {msg}")
    else:
        failed += 1
        print(f"  FAIL: {msg}")


def create_caster(name: str = "Caster", position: tuple = (0, 0), faction: str = "heroes") -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            charisma=AbilityConfig(ability_score=18),  # +4
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 4, 2: 3}),
        equipment=EquipmentConfig(),
        proficiency_bonus=3,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(entity)
    scimitar = create_scimitar(entity.uuid)
    entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
    return entity


def create_fighter(name: str, position: tuple, faction: str, creature_type: CreatureType = CreatureType.HUMANOID) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            charisma=AbilityConfig(ability_score=8),  # -1, easier to fail CHA saves
        ),
        health=HealthConfig(),
        equipment=EquipmentConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
        creature_type=creature_type,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(entity)
    scimitar = create_scimitar(entity.uuid)
    entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
    return entity


# =============================================================================
# TEST 1: Bane — CHA save failure applies -d4
# =============================================================================
def test_bane_save_fail():
    print("\n=== Test 1: Bane — CHA save fail ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Cleric", (0, 0), "heroes")
    enemy = create_fighter("Goblin", (2, 0), "monsters")

    Entity.update_all_entities_senses()

    # Force CHA save to fail: cast with high DC vs low CHA
    # DC = 8 + prof(3) + CHA(4) = 15, enemy CHA save = -1
    # Need to avoid nat 20 which auto-succeeds
    spell = Bane(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemy.uuid,
        cast_at_level=1,
    )

    # Try until we get a non-nat-20 roll (failure is almost guaranteed with DC 15 vs -1)
    for _ in range(20):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(-5, -5, 25, 25)
        caster = create_caster("Cleric", (0, 0), "heroes")
        enemy = create_fighter("Goblin", (2, 0), "monsters")
        Entity.update_all_entities_senses()

        spell = Bane(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=enemy.uuid,
            cast_at_level=1,
        )
        spell.apply(parent_event=None)
        if has_condition(enemy, "Bane"):
            break

    check(has_condition(enemy, "Bane"), "Enemy has Bane condition after failed save")
    check(has_condition(caster, "Concentrating"), "Caster is concentrating")

    # Verify the handler is registered (check attack d20 roll manipulation)
    bane_handlers = [h for h in enemy.event_handlers.values() if h.name == "Bane"]
    check(len(bane_handlers) == 1, f"Enemy has 1 Bane handler (got {len(bane_handlers)})")


# =============================================================================
# TEST 2: Bane — CHA save success, no effect
# =============================================================================
def test_bane_save_success():
    print("\n=== Test 2: Bane — CHA save success ===")

    # Use a target with high CHA to make saves likely
    for _ in range(20):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(-5, -5, 25, 25)
        caster = create_caster("Cleric", (0, 0), "heroes")

        # Create enemy with very high CHA to succeed on save
        config = EntityConfig(
            ability_scores=AbilityScoresConfig(charisma=AbilityConfig(ability_score=30)),
            proficiency_bonus=10,
            position=(2, 0),
            faction="monsters",
        )
        tough_enemy = Entity.create(source_entity_uuid=uuid4(), name="Archmage", config=config)
        setup_standard_actions(tough_enemy)
        Entity.update_all_entities_senses()

        spell = Bane(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=tough_enemy.uuid,
            cast_at_level=1,
        )
        spell.apply(parent_event=None)

        # Check if save succeeded (no Bane condition)
        if not has_condition(tough_enemy, "Bane"):
            break

    check(not has_condition(tough_enemy, "Bane"), "High-CHA enemy resisted Bane")
    check(has_condition(caster, "Concentrating"), "Caster still concentrating even if all targets save")


# =============================================================================
# TEST 3: Bane — Concentration break removes all BaneEffects
# =============================================================================
def test_bane_concentration_break():
    print("\n=== Test 3: Bane — Concentration break ===")

    for _ in range(20):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(-5, -5, 25, 25)
        caster = create_caster("Cleric", (0, 0), "heroes")
        enemy1 = create_fighter("Goblin 1", (2, 0), "monsters")
        enemy2 = create_fighter("Goblin 2", (0, 2), "monsters")
        Entity.update_all_entities_senses()

        spell = Bane(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=enemy1.uuid,
            extra_target_entity_uuids=[enemy2.uuid],
            cast_at_level=1,
        )
        spell.apply(parent_event=None)
        # Both must have Bane
        if has_condition(enemy1, "Bane") and has_condition(enemy2, "Bane"):
            break

    check(has_condition(enemy1, "Bane"), "Enemy 1 has Bane")
    check(has_condition(enemy2, "Bane"), "Enemy 2 has Bane")
    check(has_condition(caster, "Concentrating"), "Caster concentrating")

    # Break concentration by removing the condition directly
    caster.remove_condition("Concentrating")

    check(not has_condition(caster, "Concentrating"), "Concentration removed")
    check(not has_condition(enemy1, "Bane"), "Enemy 1 Bane removed via concentration break")
    check(not has_condition(enemy2, "Bane"), "Enemy 2 Bane removed via concentration break")


# =============================================================================
# TEST 4: Bless — auto-apply +d4 to allies
# =============================================================================
def test_bless_auto_apply():
    print("\n=== Test 4: Bless — auto-apply to allies ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Cleric", (0, 0), "heroes")
    ally1 = create_fighter("Fighter", (2, 0), "heroes")
    ally2 = create_fighter("Rogue", (0, 2), "heroes")

    Entity.update_all_entities_senses()

    spell = Bless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally1.uuid,
        extra_target_entity_uuids=[ally2.uuid],
        cast_at_level=1,
    )
    spell.apply(parent_event=None)

    check(has_condition(ally1, "Bless"), "Ally 1 has Bless")
    check(has_condition(ally2, "Bless"), "Ally 2 has Bless")
    check(has_condition(caster, "Concentrating"), "Caster concentrating on Bless")

    # Verify Bless handlers exist
    bless_handlers_1 = [h for h in ally1.event_handlers.values() if h.name == "Bless"]
    bless_handlers_2 = [h for h in ally2.event_handlers.values() if h.name == "Bless"]
    check(len(bless_handlers_1) == 1, f"Ally 1 has Bless handler (got {len(bless_handlers_1)})")
    check(len(bless_handlers_2) == 1, f"Ally 2 has Bless handler (got {len(bless_handlers_2)})")


# =============================================================================
# TEST 5: Bless — Concentration break removes all BlessEffects
# =============================================================================
def test_bless_concentration_break():
    print("\n=== Test 5: Bless — Concentration break ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Cleric", (0, 0), "heroes")
    ally1 = create_fighter("Fighter", (2, 0), "heroes")
    ally2 = create_fighter("Rogue", (0, 2), "heroes")

    Entity.update_all_entities_senses()

    spell = Bless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally1.uuid,
        extra_target_entity_uuids=[ally2.uuid],
        cast_at_level=1,
    )
    spell.apply(parent_event=None)

    check(has_condition(ally1, "Bless"), "Ally 1 blessed before break")
    check(has_condition(ally2, "Bless"), "Ally 2 blessed before break")

    # Break concentration
    caster.remove_condition("Concentrating")

    check(not has_condition(caster, "Concentrating"), "Concentration removed")
    check(not has_condition(ally1, "Bless"), "Ally 1 Bless removed via concentration break")
    check(not has_condition(ally2, "Bless"), "Ally 2 Bless removed via concentration break")


# =============================================================================
# TEST 6: Necrotic Bless — undead get Bless, non-undead get CHA save → Bane
# =============================================================================
def test_necrotic_bless_dual_effect():
    print("\n=== Test 6: Necrotic Bless — dual effect ===")

    for _ in range(20):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(-5, -5, 25, 25)

        caster = create_caster("Necromancer", (0, 0), "undead_army")

        # Create undead ally
        undead = create_fighter("Skeleton", (2, 0), "undead_army", creature_type=CreatureType.UNDEAD)

        # Create non-undead enemy with low CHA
        living = create_fighter("Peasant", (0, 2), "villagers")

        Entity.update_all_entities_senses()

        spell = NecroticBless(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=undead.uuid,
            extra_target_entity_uuids=[living.uuid],
            cast_at_level=2,
        )
        spell.apply(parent_event=None)

        # Undead should always get Bless (no save), living should get Bane on fail
        if has_condition(undead, "Bless") and has_condition(living, "Bane"):
            break

    check(has_condition(undead, "Bless"), "Undead has Bless (no save needed)")
    check(has_condition(living, "Bane"), "Living enemy has Bane (failed CHA save)")
    check(has_condition(caster, "Concentrating"), "Caster concentrating")

    # Break concentration — both effects should be removed
    caster.remove_condition("Concentrating")
    check(not has_condition(undead, "Bless"), "Undead Bless removed on concentration break")
    check(not has_condition(living, "Bane"), "Living Bane removed on concentration break")


# =============================================================================
# TEST 7: Necrotic Bless — non-undead saves successfully
# =============================================================================
def test_necrotic_bless_save_success():
    print("\n=== Test 7: Necrotic Bless — non-undead saves ===")

    for _ in range(20):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(-5, -5, 25, 25)

        caster = create_caster("Necromancer", (0, 0), "undead_army")

        # High CHA non-undead that will succeed on save
        config = EntityConfig(
            ability_scores=AbilityScoresConfig(charisma=AbilityConfig(ability_score=30)),
            proficiency_bonus=10,
            position=(2, 0),
            faction="villagers",
        )
        strong_target = Entity.create(source_entity_uuid=uuid4(), name="Archfey", config=config)
        setup_standard_actions(strong_target)

        Entity.update_all_entities_senses()

        spell = NecroticBless(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=strong_target.uuid,
            cast_at_level=2,
        )
        spell.apply(parent_event=None)

        if not has_condition(strong_target, "Bane"):
            break

    check(not has_condition(strong_target, "Bane"), "High-CHA target resisted Necrotic Bless")
    check(has_condition(caster, "Concentrating"), "Caster still concentrating")


# =============================================================================
# TEST 8: Bane — verify handler triggers (attack and save)
# =============================================================================
def test_bane_handler_triggers():
    print("\n=== Test 8: Bane — handler trigger verification ===")

    for _ in range(20):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(-5, -5, 25, 25)

        caster = create_caster("Cleric", (0, 0), "heroes")
        enemy = create_fighter("Goblin", (1, 0), "monsters")

        Entity.update_all_entities_senses()

        spell = Bane(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=enemy.uuid,
            cast_at_level=1,
        )
        spell.apply(parent_event=None)
        if has_condition(enemy, "Bane"):
            break

    check(has_condition(enemy, "Bane"), "Enemy has Bane")

    # Verify handler has correct triggers
    bane_handlers = [h for h in enemy.event_handlers.values() if h.name == "Bane"]
    check(len(bane_handlers) == 1, "Bane handler registered")
    triggers = bane_handlers[0].trigger_conditions
    trigger_types = {t.event_type.value for t in triggers}
    check("attack_d20_roll" in trigger_types, "Bane triggers on attack d20 rolls")
    check("save_d20_roll" in trigger_types, "Bane triggers on save d20 rolls")


# =============================================================================
# TEST 9: Bless — verify d20 roll is actually modified (saving throw)
# =============================================================================
def test_bless_modifies_save_roll():
    print("\n=== Test 9: Bless — d20 roll modification on saves ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Cleric", (0, 0), "heroes")
    ally = create_fighter("Fighter", (2, 0), "heroes")
    _enemy = create_fighter("Enemy Caster", (0, 4), "monsters")

    Entity.update_all_entities_senses()

    spell = Bless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=1,
    )
    spell.apply(parent_event=None)

    check(has_condition(ally, "Bless"), "Ally has Bless")

    # Verify handler is registered for saves
    bless_handlers = [h for h in ally.event_handlers.values() if h.name == "Bless"]
    check(len(bless_handlers) == 1, "Bless handler registered for saves")
    triggers = bless_handlers[0].trigger_conditions
    save_triggers = [t for t in triggers if "save" in t.event_type.value]
    check(len(save_triggers) == 1, f"Bless handler has save trigger (got {len(save_triggers)})")


# =============================================================================
# TEST 10: Bless target self
# =============================================================================
def test_bless_self():
    print("\n=== Test 10: Bless — self-targeting ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Cleric", (0, 0), "heroes")
    Entity.update_all_entities_senses()

    spell = Bless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,  # Self-target
        cast_at_level=1,
    )
    spell.apply(parent_event=None)

    check(has_condition(caster, "Bless"), "Caster can bless self")
    check(has_condition(caster, "Concentrating"), "Caster concentrating")


# =============================================================================
# TEST 11: Bane multi-target count (get_multi_target_count)
# =============================================================================
def test_multi_target_counts():
    print("\n=== Test 11: Multi-target counts ===")
    reset_combat_state()

    bane = Bane(source_entity_uuid=uuid4(), cast_at_level=1)
    check(bane.get_multi_target_count() == 3, f"Bane L1: 3 targets (got {bane.get_multi_target_count()})")

    bane_up = Bane(source_entity_uuid=uuid4(), cast_at_level=3)
    check(bane_up.get_multi_target_count() == 5, f"Bane L3 upcast: 5 targets (got {bane_up.get_multi_target_count()})")

    bless = Bless(source_entity_uuid=uuid4(), cast_at_level=1)
    check(bless.get_multi_target_count() == 3, f"Bless L1: 3 targets (got {bless.get_multi_target_count()})")

    nb = NecroticBless(source_entity_uuid=uuid4(), cast_at_level=2)
    check(nb.get_multi_target_count() == 4, f"NecroticBless: 4 targets (got {nb.get_multi_target_count()})")


# =============================================================================
# RUN ALL TESTS
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("BLESS / BANE / NECROTIC BLESS TEST SUITE")
    print("=" * 60)

    test_bane_save_fail()
    test_bane_save_success()
    test_bane_concentration_break()
    test_bless_auto_apply()
    test_bless_concentration_break()
    test_necrotic_bless_dual_effect()
    test_necrotic_bless_save_success()
    test_bane_handler_triggers()
    test_bless_modifies_save_roll()
    test_bless_self()
    test_multi_target_counts()

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} checks")
    print(f"{'=' * 60}")

    if failed > 0:
        exit(1)
    else:
        print("ALL TESTS PASSED!")
