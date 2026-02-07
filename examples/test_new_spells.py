"""
Tests for newly implemented spells (Phase 1-3).

Tests the following spells:
- Ray of Frost (cantrip - attack + speed reduction)
- Acid Splash (cantrip - 2-target DEX save)
- Scorching Ray (L2 - multi-attack)
- Blur (L2 - disadvantage buff)
- Misty Step (L2 - bonus action teleport)
- Blindness/Deafness (L2 - condition application)
- Fear (L3 - cone AoE + Frightened)
- Hypnotic Pattern (L3 - cube AoE + Charmed + Incapacitated)

Run with: python examples/test_new_spells.py
"""

from uuid import uuid4

from dnd.utils import reset_combat_state, get_hp, has_condition, get_position
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.actions_functional import setup_standard_actions
from dnd.monsters.bestiary import create_sorcerer
from dnd.core.events import EventPhase
from dnd.core.modifiers import NumericalModifier, AdvantageStatus, AutoHitModifier, AutoHitStatus
from dnd.blocks.equipment import WeaponSlot
from dnd.spells.evocation import RayOfFrost, ScorchingRay
from dnd.spells.conjuration import AcidSplash, MistyStep
from dnd.spells.necromancy import BlindnessDeafness
from dnd.spells.illusion import Blur, Fear, HypnoticPattern
from dnd.core.events import EventQueue
from dnd.entity import get_natural_roll


def had_critical_d20() -> bool:
    """Check if any d20 roll in the current EventQueue had a nat 1 or nat 20."""
    for event in EventQueue._all_events:
        for attr in ('dice_roll', 'save_roll'):
            roll = getattr(event, attr, None)
            if roll is not None:
                try:
                    nat = get_natural_roll(roll)
                    if nat in (1, 20):
                        return True
                except Exception:
                    pass
    return False


def create_test_target(name: str, position: tuple, dex: int = 10, con: int = 10, wis: int = 10, faction: str = "monsters"):
    """Helper to create test targets with specified ability scores."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=dex),
            constitution=AbilityConfig(ability_score=con),
            wisdom=AbilityConfig(ability_score=wis)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]),
        position=position,
        faction=faction,
        proficiency_bonus=2,
    )
    entity = Entity.create(name=name, source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(entity)
    return entity


# =============================================================================
# Ray of Frost Tests
# =============================================================================

def test_ray_of_frost_hit_damage():
    """Ray of Frost deals cold damage on hit."""
    print("\n=== Test: Ray of Frost Hit Damage ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    # Low DEX = low AC, easier to hit
    target = create_test_target("Target", (2, 0), dex=1)

    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)

    # Force hit via AUTOHIT modifier (prevents natural 1 auto-miss)
    hit_mod = AutoHitModifier(name="Force Hit", value=AutoHitStatus.AUTOHIT, source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    mod_uuid = caster.spellcasting.spell_attack_bonus.self_static.add_auto_hit_modifier(hit_mod)

    ray = RayOfFrost(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, caster_level=1)
    _result = ray.apply()

    caster.spellcasting.spell_attack_bonus.self_static.remove_modifier(mod_uuid)

    final_hp = get_hp(target)
    damage = initial_hp - final_hp

    assert damage > 0, f"Should deal damage on hit, dealt {damage}"
    print(f"  Damage dealt: {damage}")
    print("PASS: Ray of Frost deals damage on hit")


def test_ray_of_frost_speed_reduction():
    """Ray of Frost reduces target speed by 10ft on hit."""
    print("\n=== Test: Ray of Frost Speed Reduction ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target = create_test_target("Target", (2, 0), dex=1)

    Entity.update_all_entities_senses()

    initial_speed = target.action_economy.movement.normalized_score

    # Force hit
    hit_mod = NumericalModifier(name="Force Hit", value=100, source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    mod_uuid = caster.spellcasting.spell_attack_bonus.self_static.add_value_modifier(hit_mod)

    ray = RayOfFrost(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, caster_level=1)
    ray.apply()

    caster.spellcasting.spell_attack_bonus.self_static.remove_modifier(mod_uuid)

    final_speed = target.action_economy.movement.normalized_score
    speed_reduction = initial_speed - final_speed

    # Effect condition lives on CASTER (tracks duration until caster's turn)
    assert has_condition(caster, "Ray of Frost Effect"), "Caster should have Ray of Frost Effect condition"
    assert speed_reduction == 10, f"Speed should be reduced by 10, got {speed_reduction}"
    print(f"  Initial speed: {initial_speed}")
    print(f"  Final speed: {final_speed}")
    print("PASS: Ray of Frost reduces speed by 10ft")


def test_ray_of_frost_duration():
    """Ray of Frost slow expires at START of CASTER's next turn, not target's.

    This test verifies the fix for the duration bug. The SRD says the speed
    reduction lasts "until the start of your next turn" (caster's turn).
    Before the fix, it expired at the start of the target's turn (wrong).
    """
    print("\n=== Test: Ray of Frost Duration (Caster's Turn) ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target = create_test_target("Target", (2, 0), dex=1)

    Entity.update_all_entities_senses()

    # Force hit
    hit_mod = NumericalModifier(name="Force Hit", value=100, source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    mod_uuid = caster.spellcasting.spell_attack_bonus.self_static.add_value_modifier(hit_mod)

    ray = RayOfFrost(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, caster_level=1)
    ray.apply()

    caster.spellcasting.spell_attack_bonus.self_static.remove_modifier(mod_uuid)

    # Verify setup: caster has effect condition (which tracks the speed modifier on target)
    base_speed = 30  # Default speed
    assert has_condition(caster, "Ray of Frost Effect"), "Caster should have RayOfFrostEffect"
    assert target.action_economy.movement.normalized_score == base_speed - 10, "Target should be slowed"
    print("  Setup verified: caster has effect, target speed reduced")

    # Simulate TARGET's turn start - target should STILL be slowed!
    # The effect is on caster, so target's turn doesn't affect it
    target.on_turn_start()
    assert target.action_economy.movement.normalized_score == base_speed - 10, \
        "Target should STILL be slowed after their turn start"
    print("  After target's turn start: still slowed (correct!)")

    # Simulate TARGET's turn end
    target.on_turn_end()
    assert target.action_economy.movement.normalized_score == base_speed - 10, \
        "Target should still be slowed after their turn end"
    print("  After target's turn end: still slowed")

    # Simulate CASTER's turn start - NOW the effect should expire
    caster.on_turn_start()
    assert not has_condition(caster, "Ray of Frost Effect"), "Caster's effect should expire at their turn start"
    assert target.action_economy.movement.normalized_score == base_speed, \
        "Target speed should be restored when effect expires"
    print("  After caster's turn start: effect expired, target speed restored")

    # Verify speed is restored
    expected_speed = 30  # Default speed
    actual_speed = target.action_economy.movement.normalized_score
    assert actual_speed == expected_speed, f"Speed should be restored to {expected_speed}, got {actual_speed}"
    print(f"  Target speed: {actual_speed} (restored)")

    print("PASS: Ray of Frost expires at caster's turn start (correct per SRD)")


# =============================================================================
# Acid Splash Tests
# =============================================================================

def test_acid_splash_single_target():
    """Acid Splash works on single target."""
    print("\n=== Test: Acid Splash Single Target ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    # Low DEX = guaranteed fail
    target = create_test_target("Target", (2, 0), dex=1)

    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)

    acid = AcidSplash(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, caster_level=1)
    _result = acid.apply()

    final_hp = get_hp(target)
    damage = initial_hp - final_hp

    assert damage > 0, f"Should deal damage on failed save, dealt {damage}"
    print(f"  Damage dealt: {damage}")
    print("PASS: Acid Splash damages single target")


def test_acid_splash_two_targets():
    """Acid Splash can hit two targets within 5ft of each other."""
    print("\n=== Test: Acid Splash Two Targets ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target1 = create_test_target("Target1", (2, 0), dex=1)  # Adjacent
    target2 = create_test_target("Target2", (2, 1), dex=1)  # Within 5ft of target1

    Entity.update_all_entities_senses()

    initial_hp1 = get_hp(target1)
    initial_hp2 = get_hp(target2)

    acid = AcidSplash(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target1.uuid,
        extra_target_entity_uuids=[target2.uuid],
        caster_level=1
    )
    _result = acid.apply()

    damage1 = initial_hp1 - get_hp(target1)
    damage2 = initial_hp2 - get_hp(target2)

    assert damage1 > 0, f"Target1 should take damage, got {damage1}"
    assert damage2 > 0, f"Target2 should take damage, got {damage2}"
    print(f"  Target1 damage: {damage1}")
    print(f"  Target2 damage: {damage2}")
    print("PASS: Acid Splash hits two targets")


def test_acid_splash_rejects_distant_targets():
    """Acid Splash rejects targets not within 5ft of each other."""
    print("\n=== Test: Acid Splash Rejects Distant Targets ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target1 = create_test_target("Target1", (2, 0), dex=1)
    target2 = create_test_target("Target2", (5, 0), dex=1)  # Too far from target1

    Entity.update_all_entities_senses()

    acid = AcidSplash(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target1.uuid,
        extra_target_entity_uuids=[target2.uuid],
        caster_level=1
    )
    result = acid.apply()
    assert result is not None
    assert result.status_message is not None

    assert result.phase == EventPhase.CANCEL, f"Should be canceled, got {result.phase}"
    assert "5ft" in result.status_message.lower(), f"Message should mention 5ft: {result.status_message}"
    print(f"  Cancel message: {result.status_message}")
    print("PASS: Acid Splash rejects distant targets")


# =============================================================================
# Scorching Ray Tests
# =============================================================================

def test_scorching_ray_three_rays():
    """Scorching Ray fires 3 rays at base level."""
    print("\n=== Test: Scorching Ray Three Rays ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target = create_test_target("Target", (2, 0), dex=1)

    Entity.update_all_entities_senses()

    initial_hp = get_hp(target)

    # Force all hits
    hit_mod = NumericalModifier(name="Force Hit", value=100, source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    mod_uuid = caster.spellcasting.spell_attack_bonus.self_static.add_value_modifier(hit_mod)

    scorching = ScorchingRay(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, cast_at_level=2, caster_level=5)

    # Check projectile count
    num_rays = scorching.get_num_projectiles()
    assert num_rays == 3, f"Should have 3 rays at level 2, got {num_rays}"

    _result = scorching.apply()
    caster.spellcasting.spell_attack_bonus.self_static.remove_modifier(mod_uuid)

    final_hp = get_hp(target)
    damage = initial_hp - final_hp

    # 3 rays x 2d6 = minimum 6 damage (3x2)
    assert damage >= 6, f"Should deal at least 6 damage from 3 rays, dealt {damage}"
    print(f"  Rays: {num_rays}")
    print(f"  Total damage: {damage}")
    print("PASS: Scorching Ray fires 3 rays")


def test_scorching_ray_upcast():
    """Scorching Ray gains rays when upcast."""
    print("\n=== Test: Scorching Ray Upcast ===")
    reset_combat_state()


    # Check ray scaling
    for level, expected_rays in [(2, 3), (3, 4), (4, 5), (5, 6)]:
        spell = ScorchingRay(source_entity_uuid=uuid4(), cast_at_level=level, caster_level=10)
        rays = spell.get_num_projectiles()
        assert rays == expected_rays, f"Level {level} should have {expected_rays} rays, got {rays}"
        print(f"  Level {level}: {rays} rays")

    print("PASS: Scorching Ray upcast scaling correct")


# =============================================================================
# Blur Tests
# =============================================================================

def test_blur_applies_disadvantage():
    """Blur gives attackers disadvantage."""
    print("\n=== Test: Blur Applies Disadvantage ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    attacker = create_test_target("Attacker", (1, 0), faction="monsters")

    Entity.update_all_entities_senses()

    # Cast Blur on self
    blur = Blur(source_entity_uuid=caster.uuid, caster_level=5)
    blur.apply()

    assert has_condition(caster, "Blur"), "Caster should have Blur condition"
    assert has_condition(caster, "Concentrating"), "Caster should be Concentrating"

    # Check that attacker gets disadvantage via to_target propagation
    attacker_bonus = attacker.attack_bonus(WeaponSlot.MELEE_MAIN, caster.uuid)
    caster_ac = caster.ac_bonus(attacker.uuid)
    attacker_bonus.set_from_target(caster_ac)

    adv_status = attacker_bonus.advantage
    assert adv_status == AdvantageStatus.DISADVANTAGE, f"Attacker should have disadvantage, got {adv_status}"

    attacker_bonus.reset_from_target()

    print("PASS: Blur gives attackers disadvantage")


def test_blur_concentration():
    """Blur ends when concentration breaks."""
    print("\n=== Test: Blur Concentration ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses()

    blur = Blur(source_entity_uuid=caster.uuid, caster_level=5)
    blur.apply()

    assert has_condition(caster, "Blur"), "Should have Blur"
    assert has_condition(caster, "Concentrating"), "Should be Concentrating"

    # Break concentration
    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Blur"), "Blur should end when concentration breaks"
    print("PASS: Blur ends with concentration")


# =============================================================================
# Misty Step Tests
# =============================================================================

def test_misty_step_teleport():
    """Misty Step teleports caster to visible location."""
    print("\n=== Test: Misty Step Teleport ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses()

    start_pos = get_position(caster)
    target_pos = (5, 0)  # 25ft away

    misty = MistyStep(source_entity_uuid=caster.uuid, end_position=target_pos, caster_level=5)
    result = misty.apply()
    assert result is not None

    end_pos = get_position(caster)

    assert result.phase == EventPhase.COMPLETION, f"Should complete, got {result.phase}"
    assert end_pos == target_pos, f"Should be at {target_pos}, got {end_pos}"
    print(f"  Start: {start_pos}")
    print(f"  End: {end_pos}")
    print("PASS: Misty Step teleports correctly")


def test_misty_step_range_limit():
    """Misty Step fails beyond 30ft."""
    print("\n=== Test: Misty Step Range Limit ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses()

    target_pos = (8, 0)  # 40ft away (8 tiles * 5ft)

    misty = MistyStep(source_entity_uuid=caster.uuid, end_position=target_pos, caster_level=5)
    result = misty.apply()
    assert result is not None
    assert result.status_message is not None

    assert result.phase == EventPhase.CANCEL, f"Should cancel, got {result.phase}"
    assert "range" in result.status_message.lower(), f"Message should mention range: {result.status_message}"
    print(f"  Cancel message: {result.status_message}")
    print("PASS: Misty Step respects 30ft range")


def test_misty_step_bonus_action():
    """Misty Step uses bonus action, not action."""
    print("\n=== Test: Misty Step Bonus Action ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses()

    initial_actions = caster.action_economy.actions.normalized_score
    initial_bonus = caster.action_economy.bonus_actions.normalized_score

    target_pos = (3, 0)
    misty = MistyStep(source_entity_uuid=caster.uuid, end_position=target_pos, caster_level=5)
    misty.apply()

    final_actions = caster.action_economy.actions.normalized_score
    final_bonus = caster.action_economy.bonus_actions.normalized_score

    assert final_actions == initial_actions, f"Actions should be unchanged, was {initial_actions}, now {final_actions}"
    assert final_bonus == initial_bonus - 1, f"Bonus action should be spent, was {initial_bonus}, now {final_bonus}"
    print(f"  Actions: {initial_actions} -> {final_actions}")
    print(f"  Bonus: {initial_bonus} -> {final_bonus}")
    print("PASS: Misty Step uses bonus action")


# =============================================================================
# Blindness/Deafness Tests
# =============================================================================

def test_blindness_deafness_applies_blinded():
    """Blindness/Deafness can apply Blinded condition."""
    print("\n=== Test: Blindness/Deafness Applies Blinded ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (2, 0), con=1)

        Entity.update_all_entities_senses()

        spell = BlindnessDeafness(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            effect_type="blinded",
            caster_level=5
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        assert has_condition(target, "Blindness/Deafness"), "Should have Blindness/Deafness"
        assert has_condition(target, "Blinded"), "Should have Blinded sub-condition"
        print("PASS: Blindness/Deafness applies Blinded")
        break
    else:
        raise AssertionError("Got nat 1/20 on all 10 attempts")


def test_blindness_deafness_applies_deafened():
    """Blindness/Deafness can apply Deafened condition."""
    print("\n=== Test: Blindness/Deafness Applies Deafened ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (2, 0), con=1)

        Entity.update_all_entities_senses()

        spell = BlindnessDeafness(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            effect_type="deafened",
            caster_level=5
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        assert has_condition(target, "Blindness/Deafness"), "Should have Blindness/Deafness"
        assert has_condition(target, "Deafened"), "Should have Deafened sub-condition"
        print("PASS: Blindness/Deafness applies Deafened")
        break
    else:
        raise AssertionError("Got nat 1/20 on all 10 attempts")


def test_blindness_deafness_not_concentration():
    """Blindness/Deafness is NOT concentration."""
    print("\n=== Test: Blindness/Deafness Not Concentration ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target = create_test_target("Target", (2, 0), con=1)

    Entity.update_all_entities_senses()

    spell = BlindnessDeafness(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        effect_type="blinded",
        caster_level=5
    )
    spell.apply()

    # Caster should NOT be concentrating
    assert not has_condition(caster, "Concentrating"), "Caster should NOT be concentrating"
    print("PASS: Blindness/Deafness is not concentration")


# =============================================================================
# Fear Tests
# =============================================================================

def test_fear_applies_frightened():
    """Fear applies Frightened condition on failed save."""
    print("\n=== Test: Fear Applies Frightened ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (2, 0), wis=1)

        Entity.update_all_entities_senses()

        fear = Fear(source_entity_uuid=caster.uuid, end_position=(5, 0), caster_level=5)
        fear.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        assert has_condition(target, "Fear"), "Target should have Fear effect"
        assert has_condition(target, "Frightened"), "Target should have Frightened sub-condition"
        assert has_condition(caster, "Concentrating"), "Caster should be concentrating"
        print("PASS: Fear applies Frightened")
        break
    else:
        raise AssertionError("Got nat 1/20 on all 10 attempts")


def test_fear_cone_shape():
    """Fear affects targets in 30ft cone."""
    print("\n=== Test: Fear Cone Shape ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(5, 5), faction="heroes")
    # Targets in cone direction (east)
    target_in_cone = create_test_target("InCone", (8, 5), wis=1)
    # Target outside cone (behind caster)
    target_outside = create_test_target("Outside", (2, 5), wis=1)

    Entity.update_all_entities_senses()

    fear = Fear(source_entity_uuid=caster.uuid, end_position=(10, 5), caster_level=5)
    fear.apply()

    assert has_condition(target_in_cone, "Fear"), "Target in cone should be affected"
    assert not has_condition(target_outside, "Fear"), "Target outside cone should not be affected"
    print("PASS: Fear cone targets correctly")


# =============================================================================
# Hypnotic Pattern Tests
# =============================================================================

def test_hypnotic_pattern_applies_conditions():
    """Hypnotic Pattern applies Charmed + Incapacitated."""
    print("\n=== Test: Hypnotic Pattern Applies Conditions ===")

    for attempt in range(10):
        reset_combat_state()
        grid = get_map()
        grid.create_rectangle(0, 0, 20, 20)

        caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
        target = create_test_target("Target", (5, 0), wis=1)

        Entity.update_all_entities_senses()

        hp = HypnoticPattern(source_entity_uuid=caster.uuid, end_position=(5, 0), caster_level=5)
        hp.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        assert has_condition(target, "Hypnotic Pattern"), "Target should have Hypnotic Pattern effect"
        assert has_condition(target, "Charmed"), "Target should have Charmed sub-condition"
        assert has_condition(target, "Incapacitated"), "Target should have Incapacitated sub-condition"
        print("PASS: Hypnotic Pattern applies conditions")
        break
    else:
        raise AssertionError("Got nat 1/20 on all 10 attempts")


def test_hypnotic_pattern_concentration_cleanup():
    """Hypnotic Pattern ends when concentration breaks."""
    print("\n=== Test: Hypnotic Pattern Concentration Cleanup ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


    caster = create_sorcerer(name="Caster", position=(0, 0), faction="heroes")
    target = create_test_target("Target", (5, 0), wis=1)

    Entity.update_all_entities_senses()

    hp = HypnoticPattern(source_entity_uuid=caster.uuid, end_position=(5, 0), caster_level=5)
    hp.apply()

    assert has_condition(target, "Hypnotic Pattern"), "Should have Hypnotic Pattern"
    assert has_condition(caster, "Concentrating"), "Caster should be concentrating"

    # Break concentration
    caster.remove_condition("Concentrating")

    # Effect should be removed via linked_conditions cleanup
    assert not has_condition(target, "Hypnotic Pattern"), "Hypnotic Pattern should end"
    assert not has_condition(target, "Charmed"), "Charmed should be removed"
    assert not has_condition(target, "Incapacitated"), "Incapacitated should be removed"
    print("PASS: Hypnotic Pattern ends with concentration")


# =============================================================================
# Run All Tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("NEW SPELLS TEST SUITE (Phases 1-3)")
    print("=" * 60)

    tests = [
        # Ray of Frost
        test_ray_of_frost_hit_damage,
        test_ray_of_frost_speed_reduction,
        test_ray_of_frost_duration,
        # Acid Splash
        test_acid_splash_single_target,
        test_acid_splash_two_targets,
        test_acid_splash_rejects_distant_targets,
        # Scorching Ray
        test_scorching_ray_three_rays,
        test_scorching_ray_upcast,
        # Blur
        test_blur_applies_disadvantage,
        test_blur_concentration,
        # Misty Step
        test_misty_step_teleport,
        test_misty_step_range_limit,
        test_misty_step_bonus_action,
        # Blindness/Deafness
        test_blindness_deafness_applies_blinded,
        test_blindness_deafness_applies_deafened,
        test_blindness_deafness_not_concentration,
        # Fear
        test_fear_applies_frightened,
        test_fear_cone_shape,
        # Hypnotic Pattern
        test_hypnotic_pattern_applies_conditions,
        test_hypnotic_pattern_concentration_cleanup,
    ]

    passed = 0
    failed = 0
    MAX_RETRIES = 3

    for test in tests:
        success = False
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                test()
                success = True
                if attempt > 0:
                    print(f"  (passed on retry {attempt + 1} - previous had nat 1/20)")
                break
            except (AssertionError, Exception) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1 and had_critical_d20():
                    continue
                break
        if success:
            passed += 1
        else:
            if isinstance(last_error, AssertionError):
                print(f"\n*** FAILED: {test.__name__} ***")
                print(f"    {last_error}")
            else:
                print(f"\n*** ERROR: {test.__name__} ***")
                print(f"    {type(last_error).__name__}: {last_error}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)

    if failed > 0:
        exit(1)
