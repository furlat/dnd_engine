"""Test HP-pool targeting for Sleep and Color Spray spells."""
from uuid import uuid4
from typing import Tuple, List, Union

# Reset state FIRST - critical!
from dnd.utils import reset_combat_state
reset_combat_state()

# Core imports
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.gridmap import get_map
from dnd.core.modifiers import CreatureType

# Spell imports
from dnd.spells import Sleep, ColorSpray

# Test utilities
from dnd.utils import set_hp, deal_damage_to
from dnd.actions_functional import setup_standard_actions


def create_caster(
    name: str = "Caster",
    position: Tuple[int, int] = (0, 0),
    faction: str = "heroes",
    hp: int = 100,
    intelligence: int = 16,
    proficiency: int = 2
) -> Entity:
    """Create a spellcaster entity with proper config."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=intelligence),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2, 4: 1}
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        proficiency_bonus=proficiency,
        position=position,
        faction=faction,
    )
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config,
    )
    set_hp(entity, hp)
    setup_standard_actions(entity)
    return entity


def create_target(
    name: str = "Target",
    position: Tuple[int, int] = (5, 0),
    faction: str = "monsters",
    hp: int = 50,
    creature_type: CreatureType = CreatureType.HUMANOID
) -> Entity:
    """Create a target entity."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=10),
            strength=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=12),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]
        ),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config,
    )
    entity.creature_type = creature_type
    set_hp(entity, hp)
    return entity


def setup_arena(width: int = 30, height: int = 30):
    """Create a basic walkable arena."""
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    return grid


def test_sleep_hp_pool_ordering():
    """Test that Sleep affects creatures in HP order (lowest first)."""
    print("\n=== Test: Sleep HP Pool Ordering ===")
    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_caster(name="Wizard", position=(0, 0))

    # Create 3 targets with different HP values within sphere radius (20ft = 4 tiles)
    # Position them near (5,5) which will be the sphere center
    target1 = create_target(name="Goblin Low HP", position=(5, 5), hp=5)
    target2 = create_target(name="Goblin Mid HP", position=(6, 5), hp=10)
    target3 = create_target(name="Goblin High HP", position=(7, 5), hp=20)

    Entity.update_all_entities_senses(max_distance=20)

    # Create Sleep spell with fixed HP pool (for deterministic testing)
    sleep = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(5, 5),  # Center of sphere
        cast_at_level=1
    )

    # Force HP pool to exactly 18 (5 + 10 = 15, leaves 3 remaining)
    sleep.hp_pool_rolled = 18
    sleep.hp_pool_remaining = 18

    # Get targets - should select based on HP order
    targets = sleep.get_all_targets()

    print(f"HP Pool: {sleep.hp_pool_rolled}")
    print(f"Targets selected: {len(targets)}")

    for uid in targets:
        t = Entity.get(uid)
        if t:
            print(f"  - {t.name}: {t.get_hp()} HP")

    # With pool=18:
    # - Low HP (5): yes, remaining = 13
    # - Mid HP (10): yes, remaining = 3
    # - High HP (20): no, 20 > 3
    assert len(targets) == 2, f"Expected 2 targets, got {len(targets)}"
    assert target1.uuid in targets, "Low HP target should be affected"
    assert target2.uuid in targets, "Mid HP target should be affected"
    assert target3.uuid not in targets, "High HP target should NOT be affected"

    print(f"Remaining HP pool: {sleep.hp_pool_remaining}")
    assert sleep.hp_pool_remaining == 3, f"Expected 3 remaining, got {sleep.hp_pool_remaining}"

    print("PASSED!")


def test_sleep_undead_immunity():
    """Test that undead are immune to Sleep."""
    print("\n=== Test: Sleep Undead Immunity ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(0, 0))

    # Create undead target
    skeleton = create_target(name="Skeleton", position=(5, 5), hp=5, creature_type=CreatureType.UNDEAD)

    # Create humanoid target
    goblin = create_target(name="Goblin", position=(6, 5), hp=5, creature_type=CreatureType.HUMANOID)

    Entity.update_all_entities_senses(max_distance=20)

    sleep = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(5, 5),
        cast_at_level=1
    )
    sleep.hp_pool_rolled = 20
    sleep.hp_pool_remaining = 20

    targets = sleep.get_all_targets()
    target_entities_with_none: List[Union[Entity, None]] = [Entity.get(uid) for uid in targets]
    target_entities: List[Entity] = [e for e in target_entities_with_none if e is not None]
    target_names = [e.name for e in target_entities]
    print(f"Targets: {target_names}")
    assert skeleton.uuid not in targets, "Skeleton (undead) should be immune"
    assert goblin.uuid in targets, "Goblin (humanoid) should be affected"

    print("PASSED!")


def test_sleep_wake_on_damage():
    """Test that sleeping creatures wake when damaged."""
    print("\n=== Test: Sleep Wake on Damage ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(0, 0))
    target = create_target(name="Sleepy Goblin", position=(5, 5), hp=5)

    Entity.update_all_entities_senses(max_distance=20)

    # Cast Sleep
    sleep = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(5, 5),
        cast_at_level=1
    )
    sleep.hp_pool_rolled = 20
    sleep.hp_pool_remaining = 20

    event = sleep.apply()
    print(f"Sleep cast: {event.status_message if event else 'None'}")

    # Verify target is asleep
    assert "Sleep" in target.active_conditions, "Target should have Sleep condition"
    assert "Unconscious" in target.active_conditions, "Target should have Unconscious sub-condition"
    print(f"Target conditions: {list(target.active_conditions.keys())}")

    # Deal damage to wake - uses receive_damage which fires TakeDamageEvent
    deal_damage_to(target, 1, source_uuid=caster.uuid)
    print(f"Dealt 1 damage to {target.name}")

    # Verify target woke up
    assert "Sleep" not in target.active_conditions, "Sleep condition should be removed"
    assert "Unconscious" not in target.active_conditions, "Unconscious should be removed"
    print(f"Target conditions after damage: {list(target.active_conditions.keys())}")

    print("PASSED!")


def test_sleep_upcast():
    """Test that upcasting adds dice to HP pool."""
    print("\n=== Test: Sleep Upcast ===")
    reset_combat_state()

    caster_id = uuid4()

    # Base level 1: 5d8
    sleep_l1 = Sleep(source_entity_uuid=caster_id, end_position=(2, 0), cast_at_level=1)
    dice_l1 = sleep_l1.get_hp_pool_dice()
    print(f"Level 1: {dice_l1[0]}d{dice_l1[1]}")
    assert dice_l1 == (5, 8), f"Expected (5, 8), got {dice_l1}"

    # Level 3: 5d8 + 4d8 = 9d8
    sleep_l3 = Sleep(source_entity_uuid=caster_id, end_position=(2, 0), cast_at_level=3)
    dice_l3 = sleep_l3.get_hp_pool_dice()
    print(f"Level 3: {dice_l3[0]}d{dice_l3[1]}")
    assert dice_l3 == (9, 8), f"Expected (9, 8), got {dice_l3}"

    # Level 5: 5d8 + 8d8 = 13d8
    sleep_l5 = Sleep(source_entity_uuid=caster_id, end_position=(2, 0), cast_at_level=5)
    dice_l5 = sleep_l5.get_hp_pool_dice()
    print(f"Level 5: {dice_l5[0]}d{dice_l5[1]}")
    assert dice_l5 == (13, 8), f"Expected (13, 8), got {dice_l5}"

    print("PASSED!")


def test_color_spray_hp_pool_ordering():
    """Test that Color Spray affects creatures in HP order (lowest first)."""
    print("\n=== Test: Color Spray HP Pool Ordering ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(5, 5))

    # Create targets in cone direction (to the east from caster)
    # Cone is 15ft = 3 tiles
    target1 = create_target(name="Goblin Low HP", position=(6, 5), hp=8)
    target2 = create_target(name="Goblin Mid HP", position=(7, 5), hp=15)
    target3 = create_target(name="Goblin High HP", position=(8, 5), hp=30)

    Entity.update_all_entities_senses(max_distance=20)

    color_spray = ColorSpray(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # Direction: east
        cast_at_level=1
    )
    # Force HP pool to 25 (8 + 15 = 23, leaves 2)
    color_spray.hp_pool_rolled = 25
    color_spray.hp_pool_remaining = 25

    targets = color_spray.get_all_targets()

    print(f"HP Pool: {color_spray.hp_pool_rolled}")
    print(f"Targets selected: {len(targets)}")

    for uid in targets:
        t = Entity.get(uid)
        if t:
            print(f"  - {t.name}: {t.get_hp()} HP")

    # With pool=25:
    # - Low HP (8): yes, remaining = 17
    # - Mid HP (15): yes, remaining = 2
    # - High HP (30): no, 30 > 2
    assert len(targets) == 2, f"Expected 2 targets, got {len(targets)}"
    assert target1.uuid in targets, "Low HP target should be affected"
    assert target2.uuid in targets, "Mid HP target should be affected"
    assert target3.uuid not in targets, "High HP target should NOT be affected"

    print(f"Remaining HP pool: {color_spray.hp_pool_remaining}")
    assert color_spray.hp_pool_remaining == 2, f"Expected 2 remaining, got {color_spray.hp_pool_remaining}"

    print("PASSED!")


def test_color_spray_skips_unconscious():
    """Test that Color Spray skips unconscious creatures."""
    print("\n=== Test: Color Spray Skips Unconscious ===")
    reset_combat_state()
    setup_arena()

    from dnd.conditions import Unconscious

    caster = create_caster(name="Wizard", position=(5, 5))

    # Create conscious target
    conscious = create_target(name="Conscious Goblin", position=(6, 5), hp=5)

    # Create unconscious target
    unconscious_target = create_target(name="Unconscious Goblin", position=(7, 5), hp=3)
    unconscious_target.add_condition(Unconscious(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=unconscious_target.uuid
    ))

    Entity.update_all_entities_senses(max_distance=20)

    color_spray = ColorSpray(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=1
    )
    color_spray.hp_pool_rolled = 50
    color_spray.hp_pool_remaining = 50

    targets = color_spray.get_all_targets()
    target_entities_with_none: List[Union[Entity, None]] = [Entity.get(uid) for uid in targets]
    target_entities: List[Entity] = [e for e in target_entities_with_none if e is not None]
    target_names = [e.name for e in target_entities]

    print(f"Targets: {target_names}")
    assert unconscious_target.uuid not in targets, "Unconscious target should be skipped"
    assert conscious.uuid in targets, "Conscious target should be affected"

    print("PASSED!")


def test_color_spray_skips_already_blinded():
    """Test that Color Spray skips already-blinded creatures."""
    print("\n=== Test: Color Spray Skips Already Blinded ===")
    reset_combat_state()
    setup_arena()

    from dnd.conditions import Blinded

    caster = create_caster(name="Wizard", position=(5, 5))

    # Create normal target
    normal = create_target(name="Normal Goblin", position=(6, 5), hp=5)

    # Create blinded target
    blinded_target = create_target(name="Blinded Goblin", position=(7, 5), hp=3)
    blinded_target.add_condition(Blinded(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=blinded_target.uuid
    ))

    Entity.update_all_entities_senses(max_distance=20)

    color_spray = ColorSpray(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=1
    )
    color_spray.hp_pool_rolled = 50
    color_spray.hp_pool_remaining = 50

    targets = color_spray.get_all_targets()

    target_entities_with_none: List[Union[Entity, None]] = [Entity.get(uid) for uid in targets]
    target_entities: List[Entity] = [e for e in target_entities_with_none if e is not None]
    target_names = [e.name for e in target_entities]
    print(f"Targets: {target_names}")
    assert blinded_target.uuid not in targets, "Already-blinded target should be skipped"
    assert normal.uuid in targets, "Normal target should be affected"

    print("PASSED!")


def test_color_spray_applies_blinded():
    """Test that Color Spray applies Blinded condition."""
    print("\n=== Test: Color Spray Applies Blinded ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(5, 5))
    target = create_target(name="Target Goblin", position=(6, 5), hp=5)

    Entity.update_all_entities_senses(max_distance=20)

    color_spray = ColorSpray(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=1
    )
    color_spray.hp_pool_rolled = 50
    color_spray.hp_pool_remaining = 50

    event = color_spray.apply()
    print(f"Color Spray cast: {event.status_message if event else 'None'}")

    # Verify target is blinded
    assert "Color Spray" in target.active_conditions, "Target should have Color Spray condition"
    assert "Blinded" in target.active_conditions, "Target should have Blinded sub-condition"
    print(f"Target conditions: {list(target.active_conditions.keys())}")

    print("PASSED!")


def test_color_spray_upcast():
    """Test that upcasting adds dice to HP pool."""
    print("\n=== Test: Color Spray Upcast ===")
    reset_combat_state()

    caster_id = uuid4()

    # Base level 1: 6d10
    cs_l1 = ColorSpray(source_entity_uuid=caster_id, end_position=(1, 0), cast_at_level=1)
    dice_l1 = cs_l1.get_hp_pool_dice()
    print(f"Level 1: {dice_l1[0]}d{dice_l1[1]}")
    assert dice_l1 == (6, 10), f"Expected (6, 10), got {dice_l1}"

    # Level 3: 6d10 + 4d10 = 10d10
    cs_l3 = ColorSpray(source_entity_uuid=caster_id, end_position=(1, 0), cast_at_level=3)
    dice_l3 = cs_l3.get_hp_pool_dice()
    print(f"Level 3: {dice_l3[0]}d{dice_l3[1]}")
    assert dice_l3 == (10, 10), f"Expected (10, 10), got {dice_l3}"

    print("PASSED!")


def test_sleep_skip_high_hp():
    """Test that a target with HP > remaining pool is skipped (not partially affected)."""
    print("\n=== Test: Sleep Skip High HP ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(0, 0))

    # Single target with HP > pool

    Entity.update_all_entities_senses(max_distance=20)

    sleep = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(5, 5),
        cast_at_level=1
    )
    sleep.hp_pool_rolled = 10  # Less than target HP
    sleep.hp_pool_remaining = 10

    targets = sleep.get_all_targets()

    print(f"HP Pool: 10, Target HP: 15")
    print(f"Targets selected: {len(targets)}")

    assert len(targets) == 0, "No targets should be affected when HP > pool"
    assert sleep.hp_pool_remaining == 10, "Pool should remain unchanged"

    print("PASSED!")


def test_sleep_empty_aoe():
    """Test Sleep with no valid targets in AoE."""
    print("\n=== Test: Sleep Empty AoE ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(0, 0))

    Entity.update_all_entities_senses(max_distance=20)

    sleep = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(20, 20),  # No entities here
        cast_at_level=1
    )
    sleep.hp_pool_rolled = 50
    sleep.hp_pool_remaining = 50

    targets = sleep.get_all_targets()

    print(f"Targets in empty AoE: {len(targets)}")
    assert len(targets) == 0, "No targets in empty AoE"

    print("PASSED!")


if __name__ == "__main__":
    # Run all tests
    test_sleep_hp_pool_ordering()
    test_sleep_undead_immunity()
    test_sleep_wake_on_damage()
    test_sleep_upcast()
    test_color_spray_hp_pool_ordering()
    test_color_spray_skips_unconscious()
    test_color_spray_skips_already_blinded()
    test_color_spray_applies_blinded()
    test_color_spray_upcast()
    test_sleep_skip_high_hp()
    test_sleep_empty_aoe()

    print("\n" + "=" * 50)
    print("ALL TESTS PASSED!")
    print("=" * 50)
