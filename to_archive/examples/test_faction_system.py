"""
Test the faction system implementation.

This script verifies:
1. Faction assignment to entities
2. is_ally() and is_enemy() methods
3. get_visible_enemies() and get_visible_allies()
4. Encounter end condition based on factions
5. Backward compatibility with faction=None
"""

from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.encounter import Encounter
from dnd.controller import Controller
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType
from dnd.reactions import add_opportunity_attack_handler
from dnd.actions_functional import setup_standard_actions, execute_by_index
from dnd.utils import get_hp, setup_combat_arena, force_attack_hit


def reset_state():
    """Reset all registries for fresh test."""
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    get_map().clear()
    # Create a 20x20 grid so visibility works
    get_map().create_rectangle(0, 0, 20, 20)


def test_faction_assignment():
    """Test that faction can be assigned via factory."""
    reset_state()

    # Create entities with factions
    hero = create_skeleton(name="Hero", position=(0, 0), faction="heroes")
    ally = create_skeleton(name="Ally", position=(1, 0), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(3, 0), faction="monsters")

    assert hero.faction == "heroes", f"Hero faction should be 'heroes', got {hero.faction}"
    assert ally.faction == "heroes", f"Ally faction should be 'heroes', got {ally.faction}"
    assert enemy.faction == "monsters", f"Enemy faction should be 'monsters', got {enemy.faction}"

    print("✓ test_faction_assignment passed")


def test_is_ally_is_enemy():
    """Test is_ally() and is_enemy() methods."""
    reset_state()

    hero = create_skeleton(name="Hero", position=(0, 0), faction="heroes")
    ally = create_skeleton(name="Ally", position=(1, 0), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(3, 0), faction="monsters")
    neutral = create_skeleton(name="Neutral", position=(5, 0), faction=None)

    # Same faction = ally
    assert hero.is_ally(ally), "Hero should be ally of Ally (same faction)"
    assert ally.is_ally(hero), "Ally should be ally of Hero (same faction)"

    # Different faction = enemy
    assert hero.is_enemy(enemy), "Hero should be enemy of Enemy (different faction)"
    assert enemy.is_enemy(hero), "Enemy should be enemy of Hero (different faction)"

    # Same faction = not enemy
    assert not hero.is_enemy(ally), "Hero should not be enemy of Ally (same faction)"

    # No faction = enemy to all
    assert hero.is_enemy(neutral), "Hero should be enemy of Neutral (None faction = enemy to all)"
    assert neutral.is_enemy(hero), "Neutral should be enemy of Hero (None faction = enemy to all)"
    assert neutral.is_enemy(enemy), "Neutral should be enemy of Enemy (None faction = enemy to all)"

    # No faction = no allies
    assert not neutral.is_ally(hero), "Neutral should not be ally of anyone (None faction = no allies)"

    # Self relationship - entity is its own ally (for self-targeting spells)
    assert hero.is_ally(hero), "Entity should be its own ally (for self-buff spells)"
    assert not hero.is_enemy(hero), "Entity should not be its own enemy"

    print("✓ test_is_ally_is_enemy passed")


def test_get_visible_enemies_allies():
    """Test get_visible_enemies() and get_visible_allies() methods."""
    reset_state()

    # Position entities close together so they're visible
    hero = create_skeleton(name="Hero", position=(5, 5), faction="heroes")
    ally = create_skeleton(name="Ally", position=(6, 5), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(7, 5), faction="monsters")

    # Update senses for all entities
    Entity.update_all_entities_senses()

    # Hero should see ally as ally, enemy as enemy
    visible_enemies = hero.get_visible_enemies()
    visible_allies = hero.get_visible_allies()

    assert enemy.uuid in visible_enemies, "Hero should see Enemy as visible enemy"
    assert ally.uuid in visible_allies, "Hero should see Ally as visible ally"
    assert hero.uuid not in visible_enemies, "Hero should not see self as enemy"
    # Self is in visible_allies because is_ally(self) returns True (for self-targeting spells)
    # This is expected behavior - get_visible_allies() includes visible allies + self

    print("✓ test_get_visible_enemies_allies passed")


def test_get_entities_by_faction():
    """Test get_entities_by_faction() and get_alive_by_faction()."""
    reset_state()

    hero1 = create_skeleton(name="Hero1", position=(0, 0), faction="heroes")
    _hero2 = create_skeleton(name="Hero2", position=(1, 0), faction="heroes")
    _monster1 = create_skeleton(name="Monster1", position=(5, 0), faction="monsters")

    heroes = Entity.get_entities_by_faction("heroes")
    monsters = Entity.get_entities_by_faction("monsters")

    assert len(heroes) == 2, f"Should have 2 heroes, got {len(heroes)}"
    assert len(monsters) == 1, f"Should have 1 monster, got {len(monsters)}"

    # Kill one hero
    hero1.health.take_damage(1000, DamageType.SLASHING, hero1.uuid)

    alive_heroes = Entity.get_alive_by_faction("heroes")
    assert len(alive_heroes) == 1, f"Should have 1 alive hero, got {len(alive_heroes)}"
    assert alive_heroes[0].name == "Hero2", f"Alive hero should be Hero2"

    print("✓ test_get_entities_by_faction passed")


def test_encounter_end_faction():
    """Test that encounter ends when only one faction remains."""
    reset_state()

    # Create entities with factions
    hero = create_skeleton(name="Hero", position=(0, 0), faction="heroes")
    ally = create_skeleton(name="Ally", position=(1, 0), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(5, 0), faction="monsters")

    Entity.update_all_entities_senses()

    # Create encounter
    encounter = Encounter(name="Test Encounter", source_entity_uuid=hero.uuid)
    controller = Controller(name="Test", source_entity_uuid=hero.uuid)

    encounter.add_combatant(hero, controller)
    encounter.add_combatant(ally, controller)
    encounter.add_combatant(enemy, controller)

    encounter.start_encounter()

    # Kill enemy - should end encounter (only heroes faction left)
    enemy.health.take_damage(1000, DamageType.SLASHING, hero.uuid)
    deaths = encounter.check_deaths()

    assert len(deaths) == 1, f"Should have 1 death, got {len(deaths)}"
    assert encounter.state.value == "ended", f"Encounter should be ended, got {encounter.state.value}"

    print("✓ test_encounter_end_faction passed")


def test_backward_compatibility():
    """Test that faction=None preserves old behavior (enemy to everyone)."""
    reset_state()

    # Create entities without factions (old behavior)
    entity1 = create_skeleton(name="Entity1", position=(0, 0), faction=None)
    entity2 = create_skeleton(name="Entity2", position=(1, 0), faction=None)

    # Without factions, they should be enemies to each other
    assert entity1.is_enemy(entity2), "Factionless entities should be enemies"
    assert entity2.is_enemy(entity1), "Factionless entities should be enemies"

    # And not allies
    assert not entity1.is_ally(entity2), "Factionless entities should not be allies"

    print("✓ test_backward_compatibility passed")


def test_is_threatened_faction():
    """Test that is_threatened() only considers enemies."""
    reset_state()

    # Position hero with ally adjacent and enemy far away
    hero = create_skeleton(name="Hero", position=(5, 5), faction="heroes")
    _ally = create_skeleton(name="Ally", position=(6, 5), faction="heroes")  # Adjacent
    enemy = create_skeleton(name="Enemy", position=(10, 5), faction="monsters")  # Far

    Entity.update_all_entities_senses()

    # Hero should not be threatened (ally is adjacent but not an enemy)
    assert not hero.is_threatened(), "Hero should not be threatened by adjacent ally"

    # Move enemy adjacent to hero
    enemy.move((4, 5))
    Entity.update_all_entities_senses()

    # Now hero should be threatened
    assert hero.is_threatened(), "Hero should be threatened by adjacent enemy"

    print("✓ test_is_threatened_faction passed")


def test_get_available_actions_target_filter():
    """Test that get_available_actions() uses target_filter."""
    reset_state()

    # Position entities adjacent (within melee range)
    hero = create_skeleton(name="Hero", position=(5, 5), faction="heroes")
    ally = create_skeleton(name="Ally", position=(5, 6), faction="heroes")  # North
    enemy = create_skeleton(name="Enemy", position=(6, 5), faction="monsters")  # East

    Entity.update_all_entities_senses()

    # Default (enemies) - should only show enemy as target
    actions_enemies = hero.get_available_actions(target_filter="enemies")
    entity_actions_enemies = actions_enemies.entity_actions
    if entity_actions_enemies:
        targets = [t.target_uuid for t in entity_actions_enemies[0].valid_targets]
        assert enemy.uuid in targets, "Enemy should be valid target with 'enemies' filter"
        assert ally.uuid not in targets, "Ally should not be valid target with 'enemies' filter"

    # Allies - should only show ally as target
    actions_allies = hero.get_available_actions(target_filter="allies")
    entity_actions_allies = actions_allies.entity_actions
    if entity_actions_allies:
        targets = [t.target_uuid for t in entity_actions_allies[0].valid_targets]
        assert ally.uuid in targets, "Ally should be valid target with 'allies' filter"
        assert enemy.uuid not in targets, "Enemy should not be valid target with 'allies' filter"

    # All - should show both
    actions_all = hero.get_available_actions(target_filter="all")
    entity_actions_all = actions_all.entity_actions
    if entity_actions_all:
        targets = [t.target_uuid for t in entity_actions_all[0].valid_targets]
        assert enemy.uuid in targets, "Enemy should be valid target with 'all' filter"
        assert ally.uuid in targets, "Ally should be valid target with 'all' filter"

    print("✓ test_get_available_actions_target_filter passed")


def test_opportunity_attack_respects_faction():
    """Test that opportunity attacks do NOT trigger against allies, only enemies."""
    reset_state()

    # --- Test 1: Ally moving away from ally should NOT trigger OA ---
    # Keep enemy far away so only ally OA could fire
    ally1 = create_skeleton(name="Ally1", position=(5, 5), faction="heroes")
    ally2 = create_skeleton(name="Ally2", position=(6, 5), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(15, 15), faction="monsters")

    setup_standard_actions(ally1)
    setup_standard_actions(ally2)
    setup_standard_actions(enemy)

    add_opportunity_attack_handler(ally1)
    add_opportunity_attack_handler(enemy)

    Entity.update_all_entities_senses()

    encounter = setup_combat_arena(ally2, ally1)
    encounter.add_combatant(enemy, Controller(name="Enemy", source_entity_uuid=enemy.uuid))
    encounter.start_encounter()

    force_attack_hit(ally1)

    encounter.start_turn()  # ally2's turn
    ally2_hp_before = get_hp(ally2)

    # Move ally2 away from ally1's threat range
    actions = ally2.get_available_actions()
    move_actions = [a for a in actions.position_actions if a.template_name == "Move"]
    assert move_actions, "Ally2 should have move action"

    target_pos = None
    for t in move_actions[0].valid_targets:
        if t.position == (10, 5):
            target_pos = t
            break
    assert target_pos is not None, "Should be able to move to (10,5)"

    execute_by_index(ally2, "Move", target_pos.index)

    ally2_hp_after = get_hp(ally2)
    assert ally2_hp_after == ally2_hp_before, \
        f"Ally should NOT take OA from ally! Lost {ally2_hp_before - ally2_hp_after} HP"

    print("  Part 1: Ally does NOT OA ally ✓")

    # --- Test 2: Ally moving away from enemy SHOULD trigger OA ---
    reset_state()

    enemy2 = create_skeleton(name="Enemy2", position=(5, 5), faction="monsters")
    mover = create_skeleton(name="Mover", position=(6, 5), faction="heroes")

    setup_standard_actions(enemy2)
    setup_standard_actions(mover)

    add_opportunity_attack_handler(enemy2)

    Entity.update_all_entities_senses()

    encounter2 = setup_combat_arena(mover, enemy2)
    encounter2.start_encounter()

    force_attack_hit(enemy2)

    encounter2.start_turn()  # mover's turn
    mover_hp_before = get_hp(mover)

    actions = mover.get_available_actions()
    move_actions = [a for a in actions.position_actions if a.template_name == "Move"]
    target_pos = None
    for t in move_actions[0].valid_targets:
        if t.position == (10, 5):
            target_pos = t
            break
    assert target_pos is not None, "Should be able to move to (10,5)"

    execute_by_index(mover, "Move", target_pos.index)

    mover_hp_after = get_hp(mover)
    assert mover_hp_after < mover_hp_before, \
        f"Enemy SHOULD OA when leaving threat! HP unchanged at {mover_hp_after}"

    print("  Part 2: Enemy DOES OA enemy ✓")
    print("✓ test_opportunity_attack_respects_faction passed")


if __name__ == "__main__":
    print("Testing Faction System...")
    print()

    test_faction_assignment()
    test_is_ally_is_enemy()
    test_get_visible_enemies_allies()
    test_get_entities_by_faction()
    test_encounter_end_faction()
    test_backward_compatibility()
    test_is_threatened_faction()
    test_get_available_actions_target_filter()
    test_opportunity_attack_respects_faction()

    print()
    print("=" * 50)
    print("All faction system tests passed!")
    print("=" * 50)
