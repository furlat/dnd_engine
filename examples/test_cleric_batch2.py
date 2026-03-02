"""
Test Cleric Batch 2: Protection from Poison, Death Ward, Freedom of Movement.

Plus infrastructure: ignore_difficult_terrain flag, parent_event chain fix.

Run: python examples/test_cleric_batch2.py
"""
from uuid import uuid4

from dnd.utils import reset_combat_state, has_condition, get_hp, set_hp, deal_damage_to
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType, NumericalModifier
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.actions_functional import setup_standard_actions
from dnd.conditions import Poisoned, Grappled, Restrained
from dnd.actions import Move
from dnd.core.events import EventQueue, SavingThrowEvent

from dnd.spells.abjuration import (
    ProtectionFromPoison,
    DeathWard,
    FreedomOfMovement,
)

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


def section(title: str):
    print(f"\n--- {title} ---")


def create_cleric(name: str = "Cleric", position: tuple = (0, 0), faction: str = "heroes") -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=18),
            strength=AbilityConfig(ability_score=14),
            dexterity=AbilityConfig(ability_score=12),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]),
        action_economy=ActionEconomyConfig(spell_slots={1: 4, 2: 3, 3: 2, 4: 2, 5: 1}),
        proficiency_bonus=3,
        position=position,
        faction=faction,
        spellcasting=SpellcastingConfig(
            spellcasting_ability="wisdom",
        ),
    )
    entity = Entity.create(name=name, source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    return entity


def create_target(name: str = "Target", position: tuple = (1, 0), faction: str = "heroes") -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="maximums")]),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(name=name, source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    return entity


def create_enemy(name: str = "Enemy", position: tuple = (2, 0), faction: str = "villains") -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="maximums")]),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(name=name, source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    return entity


def make_tile_difficult(x: int, y: int):
    """Add +1 walking cost to a tile (total cost = 2 = difficult terrain)."""
    grid = get_map()
    tile = grid.get_tile(x, y)
    assert tile is not None, f"No tile at ({x}, {y})"
    tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=tile.uuid,
            name="Difficult Terrain",
            value=1
        )
    )


# ============================================================================
# Protection from Poison Tests
# ============================================================================

def test_protection_from_poison_resistance():
    """Poison damage is halved."""
    section("Protection from Poison: Resistance")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    Entity.update_all_entities_senses()

    # Cast Protection from Poison on target
    spell = ProtectionFromPoison(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    result = spell.apply()
    check(result is not None and not result.canceled, "Protection from Poison cast successfully")
    check(has_condition(target, "Protection from Poison"), "Condition applied")

    # Deal poison damage — should be halved
    hp_before = get_hp(target)
    deal_damage_to(target, 20, DamageType.POISON, source_uuid=cleric.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after
    check(damage_taken == 10, f"Poison damage halved: {damage_taken} (expected 10)")

    # Deal slashing damage — should NOT be halved
    hp_before = get_hp(target)
    deal_damage_to(target, 20, DamageType.SLASHING, source_uuid=cleric.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after
    check(damage_taken == 20, f"Slashing damage not halved: {damage_taken} (expected 20)")


def test_protection_from_poison_immunity():
    """Poisoned condition blocked."""
    section("Protection from Poison: Condition Immunity")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    Entity.update_all_entities_senses()

    # Cast Protection from Poison
    spell = ProtectionFromPoison(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()

    # Try to apply Poisoned — should be blocked
    poisoned = Poisoned(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(poisoned)
    check(not has_condition(target, "Poisoned"), "Poisoned condition blocked by immunity")


def test_protection_from_poison_cleanup():
    """Removal restores vulnerability to poison."""
    section("Protection from Poison: Cleanup")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    Entity.update_all_entities_senses()

    # Cast then remove
    spell = ProtectionFromPoison(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()
    target.remove_condition("Protection from Poison")
    check(not has_condition(target, "Protection from Poison"), "Condition removed")

    # Poison damage should be full now
    hp_before = get_hp(target)
    deal_damage_to(target, 20, DamageType.POISON, source_uuid=cleric.uuid)
    hp_after = get_hp(target)
    damage_taken = hp_before - hp_after
    check(damage_taken == 20, f"Poison damage full after removal: {damage_taken} (expected 20)")

    # Poisoned condition should apply now
    poisoned = Poisoned(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(poisoned)
    check(has_condition(target, "Poisoned"), "Poisoned condition applies after removal")


def test_protection_from_poison_not_concentration():
    """Protection from Poison is NOT concentration."""
    section("Protection from Poison: Not Concentration")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    Entity.update_all_entities_senses()

    spell = ProtectionFromPoison(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()

    check(not has_condition(cleric, "Concentrating"), "Caster is NOT concentrating")
    check(has_condition(target, "Protection from Poison"), "Effect persists without concentration")


# ============================================================================
# Death Ward Tests
# ============================================================================

def test_death_ward_lethal():
    """Lethal damage -> survive at 1 HP, Death Ward consumed."""
    section("Death Ward: Lethal Damage")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    Entity.update_all_entities_senses()

    # Cast Death Ward
    spell = DeathWard(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    result = spell.apply()
    check(result is not None and not result.canceled, "Death Ward cast successfully")
    check(has_condition(target, "Death Ward"), "Death Ward condition applied")

    # Set HP to 10, deal 50 damage (lethal)
    set_hp(target, 10)
    deal_damage_to(target, 50, DamageType.SLASHING, source_uuid=cleric.uuid)
    check(get_hp(target) == 1, f"Survived at 1 HP (got {get_hp(target)})")
    check(not has_condition(target, "Death Ward"), "Death Ward consumed (removed)")


def test_death_ward_nonlethal():
    """Non-lethal damage -> Death Ward NOT consumed."""
    section("Death Ward: Non-Lethal Damage")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    Entity.update_all_entities_senses()

    # Cast Death Ward
    spell = DeathWard(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()

    # Set HP to 30, deal 10 damage (non-lethal)
    set_hp(target, 30)
    deal_damage_to(target, 10, DamageType.SLASHING, source_uuid=cleric.uuid)
    check(get_hp(target) == 20, f"HP reduced normally: {get_hp(target)} (expected 20)")
    check(has_condition(target, "Death Ward"), "Death Ward still active")


def test_death_ward_one_use():
    """Second lethal hit kills -- ward already spent."""
    section("Death Ward: One Use Only")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    Entity.update_all_entities_senses()

    # Cast Death Ward
    spell = DeathWard(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()

    # First lethal hit — survive
    set_hp(target, 10)
    deal_damage_to(target, 50, DamageType.SLASHING, source_uuid=cleric.uuid)
    check(get_hp(target) == 1, "First lethal: survived at 1 HP")
    check(not has_condition(target, "Death Ward"), "Death Ward consumed")

    # Second lethal hit — no protection
    deal_damage_to(target, 50, DamageType.SLASHING, source_uuid=cleric.uuid)
    check(get_hp(target) <= 0, f"Second lethal: died (HP={get_hp(target)})")


def test_death_ward_not_concentration():
    """Death Ward is NOT concentration."""
    section("Death Ward: Not Concentration")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    Entity.update_all_entities_senses()

    spell = DeathWard(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()

    check(not has_condition(cleric, "Concentrating"), "Caster is NOT concentrating")
    check(has_condition(target, "Death Ward"), "Effect persists without concentration")


# ============================================================================
# Freedom of Movement Tests
# ============================================================================

def test_freedom_of_movement_difficult_terrain_pathfinding():
    """Pathfinding path cost through difficult terrain is lower with FoM."""
    section("Freedom of Movement: Difficult Terrain Pathfinding")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(name="Runner", position=(1, 0))
    Entity.update_all_entities_senses()

    # Make a wide band of difficult terrain (x=2..4, all y) so no diagonal bypass
    for x in range(2, 5):
        for y in range(0, 20):
            make_tile_difficult(x, y)

    # Without FoM: any path (1,0)->(5,0) must cross 3 difficult tiles at cost 2 each
    # Shortest: (1,0)->(2,_)->(3,_)->(4,_)->(5,0) = 3 difficult + 1 normal = 7 cost units
    distances_before, _ = grid.compute_paths((1, 0), max_distance=20,
                                              requesting_entity_uuid=target.uuid,
                                              subjective=True)
    cost_before = distances_before.get((5, 0), -1)

    # Cast Freedom of Movement (cleric adjacent to target)
    spell = FreedomOfMovement(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    result = spell.apply()
    check(result is not None and not result.canceled, "Freedom of Movement cast successfully")
    check(has_condition(target, "Freedom of Movement"), "Condition applied")
    check(target.ignore_difficult_terrain, "ignore_difficult_terrain flag set")

    # With FoM: difficult tiles cost 1 each, so 3+1 = 4 cost units
    distances_after, _ = grid.compute_paths((1, 0), max_distance=20,
                                             requesting_entity_uuid=target.uuid,
                                             subjective=True,
                                             ignore_difficult_terrain=True)
    cost_after = distances_after.get((5, 0), -1)

    check(cost_before > cost_after, f"Path cost without FoM ({cost_before}) > with FoM ({cost_after})")
    check(cost_after == 4, f"Path cost with FoM: {cost_after} (expected 4)")


def test_freedom_of_movement_step_cost():
    """Actual movement through difficult terrain uses base cost."""
    section("Freedom of Movement: Step Cost")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(name="Runner", position=(1, 0))  # Adjacent to cleric
    Entity.update_all_entities_senses()

    # Make tile at (2,0) difficult terrain
    make_tile_difficult(2, 0)

    # Cast Freedom of Movement (cleric adjacent to target)
    spell = FreedomOfMovement(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()
    target.update_entity_senses(max_distance=20)

    # Move through difficult terrain — should cost 5ft not 10ft
    movement_before = target.action_economy.movement.normalized_score
    move = Move(
        source_entity_uuid=target.uuid,
        end_position=(2, 0),
    )
    move.apply()
    movement_after = target.action_economy.movement.normalized_score
    cost = movement_before - movement_after
    check(cost == 5, f"Step cost through difficult terrain: {cost}ft (expected 5ft)")


def test_freedom_of_movement_grappled_immunity():
    """Grappled condition blocked."""
    section("Freedom of Movement: Grappled Immunity")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    enemy = create_enemy(position=(2, 0))
    Entity.update_all_entities_senses()

    # Cast Freedom of Movement
    spell = FreedomOfMovement(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()

    # Try to grapple — should be blocked
    grapple = Grappled(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(grapple)
    check(not has_condition(target, "Grappled"), "Grappled condition blocked by immunity")


def test_freedom_of_movement_restrained_immunity():
    """Restrained condition blocked."""
    section("Freedom of Movement: Restrained Immunity")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    enemy = create_enemy(position=(2, 0))
    Entity.update_all_entities_senses()

    # Cast Freedom of Movement
    spell = FreedomOfMovement(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()

    # Try to restrain — should be blocked
    restrained = Restrained(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(restrained)
    check(not has_condition(target, "Restrained"), "Restrained condition blocked by immunity")


def test_freedom_of_movement_cleanup():
    """Removal restores terrain costs and condition vulnerability."""
    section("Freedom of Movement: Cleanup")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))  # Adjacent to cleric
    enemy = create_enemy(position=(2, 0))
    Entity.update_all_entities_senses()

    # Cast then remove
    spell = FreedomOfMovement(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=target.uuid,
    )
    spell.apply()
    check(target.ignore_difficult_terrain, "Flag set after cast")

    target.remove_condition("Freedom of Movement")
    check(not has_condition(target, "Freedom of Movement"), "Condition removed")
    check(not target.ignore_difficult_terrain, "Flag cleared after removal")

    # Grappled should apply now
    grapple = Grappled(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(grapple)
    check(has_condition(target, "Grappled"), "Grappled applies after removal")


# ============================================================================
# Infrastructure: parent_event chain on D20 roll events
# ============================================================================

def test_parent_event_chain():
    """SavingThrowD20RollResultEvent.parent_event points to SavingThrowEvent.uuid."""
    section("Infrastructure: parent_event chain on saving throws")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    cleric = create_cleric(position=(0, 0))
    target = create_target(position=(1, 0))
    Entity.update_all_entities_senses()

    # Capture D20 roll events via handler
    captured_d20_events = []
    from dnd.core.events import EventHandler, Trigger, EventType, EventPhase

    def capture_d20(event, source_entity_uuid):
        _ = source_entity_uuid
        captured_d20_events.append(event)
        return None

    handler = EventHandler(
        name="D20 Capture",
        source_entity_uuid=target.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.SAVE_D20_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target.uuid,
            )
        ],
        event_processor=capture_d20
    )
    target.add_event_handler(handler)

    # Create and execute a saving throw
    request = cleric.create_saving_throw_request(
        target_entity_uuid=target.uuid,
        ability_name="wisdom",
        dc=15,
    )
    target.saving_throw(request)

    # Check the captured D20 event has parent_event pointing to the SavingThrowEvent
    check(len(captured_d20_events) > 0, f"Captured {len(captured_d20_events)} D20 roll event(s)")

    if captured_d20_events:
        d20_event = captured_d20_events[0]
        check(d20_event.parent_event is not None, "D20 roll event has parent_event set")
        if d20_event.parent_event:
            parent = EventQueue.get_event_by_uuid(d20_event.parent_event)
            check(parent is not None, "Parent event found in EventQueue")
            if parent:
                check(isinstance(parent, SavingThrowEvent), f"Parent is SavingThrowEvent (got {type(parent).__name__})")


# ============================================================================
# Run all tests
# ============================================================================

if __name__ == "__main__":
    # Protection from Poison
    test_protection_from_poison_resistance()
    test_protection_from_poison_immunity()
    test_protection_from_poison_cleanup()
    test_protection_from_poison_not_concentration()

    # Death Ward
    test_death_ward_lethal()
    test_death_ward_nonlethal()
    test_death_ward_one_use()
    test_death_ward_not_concentration()

    # Freedom of Movement
    test_freedom_of_movement_difficult_terrain_pathfinding()
    test_freedom_of_movement_step_cost()
    test_freedom_of_movement_grappled_immunity()
    test_freedom_of_movement_restrained_immunity()
    test_freedom_of_movement_cleanup()

    # Infrastructure
    test_parent_event_chain()

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if failed:
        print("SOME TESTS FAILED!")
        exit(1)
    else:
        print("ALL TESTS PASSED!")
