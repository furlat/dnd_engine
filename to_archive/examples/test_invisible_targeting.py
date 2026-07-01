"""
Test that spells cannot target invisible/non-visible entities.

Tests:
1. Magic Missile cannot target invisible entity (senses.entities check)
2. Magic Missile extra_target_uuids cannot target invisible entity
3. Bane cannot target invisible entity
4. Bless cannot target invisible ally that is out of senses
5. NecroticBless cannot target non-visible entity

Run: python examples/test_invisible_targeting.py
"""
from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.core.modifiers import CreatureType
from dnd.actions_functional import setup_standard_actions
from dnd.spells.evocation import MagicMissile
from dnd.spells.enchantment import Bane, Bless
from dnd.spells.necromancy import NecroticBless
from dnd.conditions import Invisible

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
        ability_scores=AbilityScoresConfig(charisma=AbilityConfig(ability_score=18)),
        action_economy=ActionEconomyConfig(spell_slots={1: 4, 2: 3}),
        equipment=EquipmentConfig(),
        proficiency_bonus=3,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(entity)
    return entity


def create_target(name: str, position: tuple, faction: str, creature_type: CreatureType = CreatureType.HUMANOID) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(),
        equipment=EquipmentConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
        creature_type=creature_type,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(entity)
    return entity


# =============================================================================
# TEST 1: Magic Missile — cannot target invisible entity (primary target)
# =============================================================================
def test_mm_invisible_primary():
    print("\n=== Test 1: Magic Missile — invisible primary target ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Wizard", (0, 0), "heroes")
    enemy = create_target("Rogue", (3, 0), "monsters")

    # Make enemy invisible
    invis = Invisible(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=enemy.uuid,
    )
    enemy.add_condition(invis)

    Entity.update_all_entities_senses()

    # Verify caster can't see enemy
    can_see = enemy.uuid in caster.senses.entities
    check(not can_see, f"Caster cannot see invisible enemy (can_see={can_see})")

    # Try to cast Magic Missile at the invisible enemy
    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemy.uuid,
        cast_at_level=1,
    )
    result = spell.apply(parent_event=None)

    # Should be canceled
    check(result is not None and result.canceled, "Magic Missile canceled on invisible primary target")
    if result and result.status_message:
        print(f"    Reason: {result.status_message}")


# =============================================================================
# TEST 2: Magic Missile — invisible extra target via extra_target_uuids
# =============================================================================
def test_mm_invisible_extra():
    print("\n=== Test 2: Magic Missile — invisible extra target ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Wizard", (0, 0), "heroes")
    visible_enemy = create_target("Goblin", (3, 0), "monsters")
    invisible_enemy = create_target("Rogue", (0, 3), "monsters")

    # Make second enemy invisible
    invis = Invisible(
        source_entity_uuid=invisible_enemy.uuid,
        target_entity_uuid=invisible_enemy.uuid,
    )
    invisible_enemy.add_condition(invis)

    Entity.update_all_entities_senses()

    # Verify setup: can see visible, can't see invisible
    check(visible_enemy.uuid in caster.senses.entities, "Caster can see visible enemy")
    check(invisible_enemy.uuid not in caster.senses.entities, "Caster cannot see invisible enemy")

    # Cast Magic Missile: 2 darts at visible, 1 dart at invisible (via extra_target_uuids)
    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=visible_enemy.uuid,
        extra_target_entity_uuids=[visible_enemy.uuid, invisible_enemy.uuid],
        cast_at_level=1,
    )
    result = spell.apply(parent_event=None)

    # Should be canceled because one of the targets is invisible
    check(result is not None and result.canceled, "Magic Missile canceled with invisible extra target")
    if result and result.status_message:
        print(f"    Reason: {result.status_message}")


# =============================================================================
# TEST 3: Bane — cannot target invisible entity
# =============================================================================
def test_bane_invisible():
    print("\n=== Test 3: Bane — invisible target ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Cleric", (0, 0), "heroes")
    visible_enemy = create_target("Orc", (2, 0), "monsters")
    invisible_enemy = create_target("Rogue", (0, 2), "monsters")

    invis = Invisible(
        source_entity_uuid=invisible_enemy.uuid,
        target_entity_uuid=invisible_enemy.uuid,
    )
    invisible_enemy.add_condition(invis)

    Entity.update_all_entities_senses()

    check(invisible_enemy.uuid not in caster.senses.entities, "Caster cannot see invisible enemy")

    # Try Bane on visible + invisible
    spell = Bane(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=visible_enemy.uuid,
        extra_target_entity_uuids=[invisible_enemy.uuid],
        cast_at_level=1,
    )
    result = spell.apply(parent_event=None)

    check(result is not None and result.canceled, "Bane canceled with invisible extra target")
    if result and result.status_message:
        print(f"    Reason: {result.status_message}")


# =============================================================================
# TEST 4: Bless — cannot target non-visible ally
# =============================================================================
def test_bless_nonvisible_ally():
    print("\n=== Test 4: Bless — non-visible ally ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Cleric", (0, 0), "heroes")
    nearby_ally = create_target("Fighter", (2, 0), "heroes")

    # Create ally behind a wall (not visible)
    grid.set_tile(5, 0, walkable=False, visible=False, name="Wall")
    far_ally = create_target("Ranger", (6, 0), "heroes")

    Entity.update_all_entities_senses()

    can_see_far = far_ally.uuid in caster.senses.entities
    print(f"    Can see far ally: {can_see_far}")

    # Try Bless on nearby + far ally
    spell = Bless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=nearby_ally.uuid,
        extra_target_entity_uuids=[far_ally.uuid],
        cast_at_level=1,
    )
    result = spell.apply(parent_event=None)

    if not can_see_far:
        check(result is not None and result.canceled, "Bless canceled with non-visible extra target")
        if result and result.status_message:
            print(f"    Reason: {result.status_message}")
    else:
        print("    (far ally was visible — wall didn't block. Skipping.)")


# =============================================================================
# TEST 5: NecroticBless — cannot target non-visible entity
# =============================================================================
def test_necrotic_bless_invisible():
    print("\n=== Test 5: NecroticBless — invisible target ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Necromancer", (0, 0), "undead_army")
    visible_undead = create_target("Skeleton", (2, 0), "undead_army", creature_type=CreatureType.UNDEAD)
    invisible_target = create_target("Hidden Foe", (0, 2), "villagers")

    invis = Invisible(
        source_entity_uuid=invisible_target.uuid,
        target_entity_uuid=invisible_target.uuid,
    )
    invisible_target.add_condition(invis)

    Entity.update_all_entities_senses()

    check(invisible_target.uuid not in caster.senses.entities, "Caster cannot see invisible target")

    spell = NecroticBless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=visible_undead.uuid,
        extra_target_entity_uuids=[invisible_target.uuid],
        cast_at_level=2,
    )
    result = spell.apply(parent_event=None)

    check(result is not None and result.canceled, "NecroticBless canceled with invisible extra target")
    if result and result.status_message:
        print(f"    Reason: {result.status_message}")


# =============================================================================
# TEST 6: Magic Missile — visible targets work fine
# =============================================================================
def test_mm_visible_targets():
    print("\n=== Test 6: Magic Missile — all visible targets (control) ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(-5, -5, 25, 25)

    caster = create_caster("Wizard", (0, 0), "heroes")
    enemy1 = create_target("Goblin 1", (3, 0), "monsters")
    enemy2 = create_target("Goblin 2", (0, 3), "monsters")

    Entity.update_all_entities_senses()

    check(enemy1.uuid in caster.senses.entities, "Can see enemy 1")
    check(enemy2.uuid in caster.senses.entities, "Can see enemy 2")

    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemy1.uuid,
        extra_target_entity_uuids=[enemy1.uuid, enemy2.uuid],
        cast_at_level=1,
    )
    result = spell.apply(parent_event=None)

    check(result is not None and not result.canceled, "Magic Missile succeeds with all visible targets")


# =============================================================================
# RUN ALL TESTS
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("INVISIBLE TARGETING TEST SUITE")
    print("=" * 60)

    test_mm_invisible_primary()
    test_mm_invisible_extra()
    test_bane_invisible()
    test_bless_nonvisible_ally()
    test_necrotic_bless_invisible()
    test_mm_visible_targets()

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} checks")
    print(f"{'=' * 60}")

    if failed > 0:
        print("\nFAILURES DETECTED — indicates missing visibility validation!")
        exit(1)
    else:
        print("ALL TESTS PASSED!")
