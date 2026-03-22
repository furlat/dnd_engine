"""
Combat Conditions Test Suite

Tests all D&D 5e conditions and verifies their effects match the expected behavior
from CLAUDE.md. Since dice rolls are random, we test the MODIFIERS that conditions
apply, which are deterministic.

Expected Condition Effects (from CLAUDE.md):
| Condition     | Self Effects                                    | Effects on Attackers                    | Sub-conditions |
|---------------|------------------------------------------------|----------------------------------------|----------------|
| Blinded       | Disadvantage on attacks, auto-fail sight skills | Advantage on attacks                   | -              |
| Charmed       | Auto-miss attacks vs charmer                    | Charmer advantage on social skills     | -              |
| Dashing       | +movement equal to base speed                   | -                                      | -              |
| Deafened      | Auto-fail hearing skills                        | -                                      | -              |
| Dodging       | Advantage on DEX saves                          | Disadvantage on attacks                | -              |
| Frightened    | Disadvantage on attacks & checks (contextual)   | -                                      | -              |
| Grappled      | Speed max = 0                                   | -                                      | -              |
| Incapacitated | Actions, bonus, reactions, movement = 0         | -                                      | -              |
| Invisible     | Advantage on attacks (contextual)               | Disadvantage on attacks (contextual)   | -              |
| Paralyzed     | Auto-fail STR/DEX saves                         | Advantage, auto-crit within 5ft        | Incapacitated  |
| Poisoned      | Disadvantage on attacks & ability checks        | -                                      | -              |
| Prone         | Disadvantage on attacks                         | Advantage ≤5ft, disadvantage >5ft      | -              |
| Restrained    | Speed=0, disadvantage attacks, disadv DEX saves | Advantage on attacks                   | -              |
| Stunned       | Auto-fail STR/DEX saves                         | Advantage on attacks                   | Incapacitated  |
| Unconscious   | Auto-fail STR/DEX saves                         | Advantage, auto-crit ≤5ft, prone-like  | Incapacitated  |
"""

from typing import List, Tuple, cast

from dnd.core.events import SkillName
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.utils import reset_combat_state
from dnd.conditions import (
    Blinded, Charmed, Dashing, Deafened, Dodging, Frightened,
    Grappled, Incapacitated, Paralyzed, Poisoned,
    Prone, Restrained, Stunned, Unconscious
)
from dnd.blocks.equipment import WeaponSlot
from dnd.blocks.skills import skills_requiring_sight, skills_requiring_hearing, skills_social
from dnd.entity import Entity
from dnd.core.values import AdvantageStatus, CriticalStatus, AutoHitStatus


class TestResult:
    """Tracks test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: List[str] = []

    def check(self, condition: bool, message: str) -> bool:
        if condition:
            self.passed += 1
            print(f"    ✓ {message}")
            return True
        else:
            self.failed += 1
            self.failures.append(message)
            print(f"    ✗ FAILED: {message}")
            return False

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n  Results: {self.passed}/{total} passed")
        if self.failures:
            print("  Failures:")
            for f in self.failures:
                print(f"    - {f}")
        return self.failed == 0


def setup_combat_pair(distance_ft: int = 5) -> Tuple[Entity, Entity]:
    """Create two entities at specified distance (in feet, 1 grid = 5ft)."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)
    grid_distance = distance_ft // 5
    attacker = create_goblin(name="Attacker", position=(0, 0))
    target = create_skeleton(name="Target", position=(grid_distance, 0))
    Entity.update_all_entities_senses()
    return attacker, target


def get_attack_modifiers(attacker: Entity, target: Entity):
    """Get attack bonus with proper target setup."""
    attacker.set_target_entity(target.uuid)
    target.set_target_entity(attacker.uuid)
    attack_bonus = attacker.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
    attacker.clear_target_entity()
    target.clear_target_entity()
    return attack_bonus


def get_defense_modifiers(defender: Entity, attacker: Entity):
    """
    Get the combined attack modifiers that an attacker would have against a defender.
    This properly propagates to_target_static and to_target_contextual modifiers
    from the defender's AC to the attacker's attack bonus via set_from_target().

    Returns the attacker's attack_bonus with defender's modifiers applied.
    """
    defender.set_target_entity(attacker.uuid)
    attacker.set_target_entity(defender.uuid)

    attack_bonus = attacker.attack_bonus(WeaponSlot.MELEE_MAIN, defender.uuid)
    ac_bonus = defender.ac_bonus(attacker.uuid)

    # This is the key: propagate to_target modifiers from defender to attacker
    attack_bonus.set_from_target(ac_bonus)

    defender.clear_target_entity()
    attacker.clear_target_entity()
    return attack_bonus


def print_separator(title: str) -> None:
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")


# =============================================================================
# INDIVIDUAL CONDITION TESTS
# =============================================================================

def test_blinded() -> bool:
    """
    Blinded: Disadvantage on attacks, auto-fail sight skills, attackers have advantage.
    """
    print_separator("TEST: BLINDED")
    result = TestResult()
    attacker, target = setup_combat_pair()

    # Apply Blinded to attacker
    blinded = Blinded(source_entity_uuid=target.uuid, target_entity_uuid=attacker.uuid)
    attacker.add_condition(blinded)

    # Check 1: Disadvantage on own attacks
    attack_bonus = get_attack_modifiers(attacker, target)
    result.check(
        attack_bonus.advantage == AdvantageStatus.DISADVANTAGE,
        f"Blinded creature has disadvantage on attacks (got {attack_bonus.advantage})"
    )

    # Check 2: Attackers against blinded have advantage
    ac_bonus = get_defense_modifiers(attacker, target)
    result.check(
        ac_bonus.advantage == AdvantageStatus.ADVANTAGE,
        f"Attackers have advantage vs blinded (got {ac_bonus.advantage})"
    )

    # Check 3: Auto-fail sight-based skills
    for skill_name in skills_requiring_sight:
        skill = attacker.skill_set.get_skill(skill_name)
        result.check(
            skill.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS,
            f"Blinded auto-fails {skill_name} (got {skill.skill_bonus.auto_hit})"
        )

    # Check 4: Removal cleans up
    attacker.remove_condition("Blinded")
    attack_bonus = get_attack_modifiers(attacker, target)
    result.check(
        attack_bonus.advantage == AdvantageStatus.NONE,
        f"After removal: no disadvantage (got {attack_bonus.advantage})"
    )

    return result.summary()


def test_charmed() -> bool:
    """
    Charmed: Auto-miss attacks vs charmer, charmer has advantage on social skills.
    """
    print_separator("TEST: CHARMED")
    result = TestResult()
    attacker, target = setup_combat_pair()

    # Attacker charms target (target cannot attack attacker, attacker has social advantage)
    charmed = Charmed(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(charmed)

    # Check 1: Charmed creature auto-misses vs charmer (contextual)
    target.set_target_entity(attacker.uuid)
    attack_bonus = target.attack_bonus(WeaponSlot.MELEE_MAIN, attacker.uuid)
    result.check(
        attack_bonus.auto_hit == AutoHitStatus.AUTOMISS,
        f"Charmed creature auto-misses vs charmer (got {attack_bonus.auto_hit})"
    )
    target.clear_target_entity()

    # Check 2: Charmer has advantage on social skills vs charmed (via to_target_contextual)
    for skill_name in skills_social:
        # The advantage is given to the charmer via to_target_contextual
        attacker.set_target_entity(target.uuid)
        target.set_target_entity(attacker.uuid)
        # Get the skill with proper targeting to evaluate contextual modifiers
        skill_bonus = attacker.skill_bonus(target.uuid, skill_name)
        result.check(
            skill_bonus.advantage == AdvantageStatus.ADVANTAGE,
            f"Charmer has advantage on {skill_name} vs charmed (got {skill_bonus.advantage})"
        )
        attacker.clear_target_entity()
        target.clear_target_entity()

    # Check 3: Removal cleans up
    target.remove_condition("Charmed")
    target.set_target_entity(attacker.uuid)
    attack_bonus = target.attack_bonus(WeaponSlot.MELEE_MAIN, attacker.uuid)
    result.check(
        attack_bonus.auto_hit == AutoHitStatus.NONE,
        f"After removal: no auto-miss (got {attack_bonus.auto_hit})"
    )
    target.clear_target_entity()

    return result.summary()


def test_dashing() -> bool:
    """
    Dashing: +movement equal to base speed.
    """
    print_separator("TEST: DASHING")
    result = TestResult()
    attacker, _ = setup_combat_pair()

    base_modifier = attacker.action_economy.movement.get_base_modifier()
    if base_modifier is None:
        print("    ✗ FAILED: Could not get base movement modifier")
        return False
    base_speed = base_modifier.value

    # Apply Dashing
    dashing = Dashing(source_entity_uuid=attacker.uuid, target_entity_uuid=attacker.uuid)
    attacker.add_condition(dashing)

    # Check: Movement doubled
    new_speed = attacker.action_economy.movement.normalized_score
    result.check(
        new_speed == base_speed * 2,
        f"Dashing doubles movement: {base_speed} -> {new_speed} (expected {base_speed * 2})"
    )

    # Removal
    attacker.remove_condition("Dashing")
    final_speed = attacker.action_economy.movement.normalized_score
    result.check(
        final_speed == base_speed,
        f"After removal: movement restored to {final_speed} (expected {base_speed})"
    )

    return result.summary()


def test_deafened() -> bool:
    """
    Deafened: Auto-fail hearing skills.
    """
    print_separator("TEST: DEAFENED")
    result = TestResult()
    attacker, target = setup_combat_pair()

    deafened = Deafened(source_entity_uuid=target.uuid, target_entity_uuid=attacker.uuid)
    attacker.add_condition(deafened)

    # Check: Auto-fail hearing skills
    for skill_name in skills_requiring_hearing:
        skill = attacker.skill_set.get_skill(skill_name)
        result.check(
            skill.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS,
            f"Deafened auto-fails {skill_name} (got {skill.skill_bonus.auto_hit})"
        )

    # Removal
    attacker.remove_condition("Deafened")
    for skill_name in skills_requiring_hearing:
        skill = attacker.skill_set.get_skill(skill_name)
        result.check(
            skill.skill_bonus.auto_hit == AutoHitStatus.NONE,
            f"After removal: {skill_name} normal (got {skill.skill_bonus.auto_hit})"
        )

    return result.summary()


def test_dodging() -> bool:
    """
    Dodging: Advantage on DEX saves, attackers have disadvantage.
    """
    print_separator("TEST: DODGING")
    result = TestResult()
    attacker, target = setup_combat_pair()

    dodging = Dodging(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    target.add_condition(dodging)

    # Check 1: Advantage on DEX saves
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    result.check(
        dex_save.bonus.advantage == AdvantageStatus.ADVANTAGE,
        f"Dodging gives advantage on DEX saves (got {dex_save.bonus.advantage})"
    )

    # Check 2: Attackers have disadvantage
    ac_bonus = get_defense_modifiers(target, attacker)
    result.check(
        ac_bonus.advantage == AdvantageStatus.DISADVANTAGE,
        f"Attackers have disadvantage vs dodging (got {ac_bonus.advantage})"
    )

    # Removal
    target.remove_condition("Dodging")
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    result.check(
        dex_save.bonus.advantage == AdvantageStatus.NONE,
        f"After removal: DEX save normal (got {dex_save.bonus.advantage})"
    )

    return result.summary()


def test_frightened() -> bool:
    """
    Frightened: Disadvantage on attacks & checks when frightener visible, can't move toward.
    """
    print_separator("TEST: FRIGHTENED")
    result = TestResult()
    attacker, target = setup_combat_pair()

    # Attacker frightens target
    frightened = Frightened(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(frightened)

    # Check 1: Disadvantage on attacks when frightener visible (contextual)
    target.set_target_entity(attacker.uuid)
    attack_bonus = target.attack_bonus(WeaponSlot.MELEE_MAIN, attacker.uuid)
    result.check(
        attack_bonus.advantage == AdvantageStatus.DISADVANTAGE,
        f"Frightened has disadvantage on attacks when frightener visible (got {attack_bonus.advantage})"
    )
    target.clear_target_entity()

    # Check 2: Disadvantage on ability checks (contextual - frightener must be visible)
    # The contextual check requires the frightener to be in senses
    for skill_str in ["perception", "investigation"]:  # Sample skills
        skill_name = cast(SkillName, skill_str)
        target.set_target_entity(attacker.uuid)
        skill_bonus = target.skill_bonus(attacker.uuid, skill_name)
        result.check(
            skill_bonus.advantage == AdvantageStatus.DISADVANTAGE,
            f"Frightened has disadvantage on {skill_name} (got {skill_bonus.advantage})"
        )
        target.clear_target_entity()

    # Check 3: Movement constrained toward frightener (max 0 contextual)
    movement = target.action_economy.movement.normalized_score
    result.check(
        movement == 0,
        f"Frightened movement toward frightener = 0 (got {movement})"
    )

    # Removal
    target.remove_condition("Frightened")
    movement = target.action_economy.movement.normalized_score
    result.check(
        movement > 0,
        f"After removal: movement restored (got {movement})"
    )

    return result.summary()


def test_grappled() -> bool:
    """
    Grappled: Speed max = 0.
    """
    print_separator("TEST: GRAPPLED")
    result = TestResult()
    attacker, target = setup_combat_pair()

    grappled = Grappled(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(grappled)

    # Check: Speed = 0
    speed = target.action_economy.movement.normalized_score
    result.check(speed == 0, f"Grappled speed = 0 (got {speed})")

    # Removal
    target.remove_condition("Grappled")
    speed = target.action_economy.movement.normalized_score
    result.check(speed > 0, f"After removal: speed restored (got {speed})")

    return result.summary()


def test_incapacitated() -> bool:
    """
    Incapacitated: Actions, bonus actions, reactions, movement all = 0.
    """
    print_separator("TEST: INCAPACITATED")
    result = TestResult()
    attacker, target = setup_combat_pair()

    incap = Incapacitated(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(incap)

    # Check all action economy
    result.check(
        target.action_economy.actions.normalized_score == 0,
        f"Incapacitated actions = 0 (got {target.action_economy.actions.normalized_score})"
    )
    result.check(
        target.action_economy.bonus_actions.normalized_score == 0,
        f"Incapacitated bonus_actions = 0 (got {target.action_economy.bonus_actions.normalized_score})"
    )
    result.check(
        target.action_economy.reactions.normalized_score == 0,
        f"Incapacitated reactions = 0 (got {target.action_economy.reactions.normalized_score})"
    )
    result.check(
        target.action_economy.movement.normalized_score == 0,
        f"Incapacitated movement = 0 (got {target.action_economy.movement.normalized_score})"
    )

    # Removal
    target.remove_condition("Incapacitated")
    result.check(
        target.action_economy.actions.normalized_score > 0,
        f"After removal: actions restored (got {target.action_economy.actions.normalized_score})"
    )

    return result.summary()


def test_paralyzed() -> bool:
    """
    Paralyzed: Auto-fail STR/DEX saves, attackers have advantage, auto-crit within 5ft.
    Includes Incapacitated as sub-condition.
    """
    print_separator("TEST: PARALYZED")
    result = TestResult()
    attacker, target = setup_combat_pair(distance_ft=5)  # Within 5ft

    paralyzed = Paralyzed(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(paralyzed)

    # Check 1: Has Incapacitated sub-condition
    result.check(
        "Incapacitated" in target.active_conditions,
        f"Paralyzed includes Incapacitated sub-condition"
    )

    # Check 2: Auto-fail STR saves
    str_save = target.saving_throws.get_saving_throw("strength")
    result.check(
        str_save.bonus.auto_hit == AutoHitStatus.AUTOMISS,
        f"Paralyzed auto-fails STR saves (got {str_save.bonus.auto_hit})"
    )

    # Check 3: Auto-fail DEX saves
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    result.check(
        dex_save.bonus.auto_hit == AutoHitStatus.AUTOMISS,
        f"Paralyzed auto-fails DEX saves (got {dex_save.bonus.auto_hit})"
    )

    # Check 4: Attackers have auto-crit within 5ft (via to_target_contextual)
    ac_bonus = get_defense_modifiers(target, attacker)
    result.check(
        ac_bonus.critical == CriticalStatus.AUTOCRIT,
        f"Attackers get auto-crit within 5ft (got {ac_bonus.critical})"
    )

    # Check 5: Incapacitated effects (movement = 0)
    result.check(
        target.action_economy.movement.normalized_score == 0,
        f"Paralyzed movement = 0 (got {target.action_economy.movement.normalized_score})"
    )

    # Removal
    target.remove_condition("Paralyzed")
    result.check(
        "Incapacitated" not in target.active_conditions,
        f"After removal: Incapacitated also removed"
    )
    result.check(
        target.action_economy.movement.normalized_score > 0,
        f"After removal: movement restored (got {target.action_economy.movement.normalized_score})"
    )

    return result.summary()


def test_poisoned() -> bool:
    """
    Poisoned: Disadvantage on all attacks and ability checks.
    """
    print_separator("TEST: POISONED")
    result = TestResult()
    attacker, target = setup_combat_pair()

    poisoned = Poisoned(source_entity_uuid=target.uuid, target_entity_uuid=attacker.uuid)
    attacker.add_condition(poisoned)

    # Check 1: Disadvantage on attacks
    attack_bonus = get_attack_modifiers(attacker, target)
    result.check(
        attack_bonus.advantage == AdvantageStatus.DISADVANTAGE,
        f"Poisoned has disadvantage on attacks (got {attack_bonus.advantage})"
    )

    # Check 2: Disadvantage on ALL ability checks (sample a few)
    for skill_str in ["athletics", "perception", "stealth", "persuasion"]:
        skill_name = cast(SkillName, skill_str)
        skill = attacker.skill_set.get_skill(skill_name)
        result.check(
            skill.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE,
            f"Poisoned has disadvantage on {skill_name} (got {skill.skill_bonus.advantage})"
        )

    # Removal
    attacker.remove_condition("Poisoned")
    attack_bonus = get_attack_modifiers(attacker, target)
    result.check(
        attack_bonus.advantage == AdvantageStatus.NONE,
        f"After removal: no disadvantage (got {attack_bonus.advantage})"
    )

    return result.summary()


def test_prone() -> bool:
    """
    Prone: Disadvantage on own attacks, advantage to melee (≤5ft), disadvantage to ranged (>5ft).
    """
    print_separator("TEST: PRONE")
    result = TestResult()

    # Test at melee range (5ft)
    attacker, target = setup_combat_pair(distance_ft=5)
    prone = Prone(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(prone)

    # Check 1: Prone has disadvantage on own attacks
    attack_bonus = get_attack_modifiers(target, attacker)
    result.check(
        attack_bonus.advantage == AdvantageStatus.DISADVANTAGE,
        f"Prone has disadvantage on own attacks (got {attack_bonus.advantage})"
    )

    # Check 2: Melee attackers (≤5ft) have advantage
    ac_bonus = get_defense_modifiers(target, attacker)
    result.check(
        ac_bonus.advantage == AdvantageStatus.ADVANTAGE,
        f"Melee attacker (5ft) has advantage vs prone (got {ac_bonus.advantage})"
    )

    # Test at ranged distance (>5ft)
    attacker2, target2 = setup_combat_pair(distance_ft=30)
    prone2 = Prone(source_entity_uuid=attacker2.uuid, target_entity_uuid=target2.uuid)
    target2.add_condition(prone2)

    # Check 3: Ranged attackers (>5ft) have disadvantage
    ac_bonus2 = get_defense_modifiers(target2, attacker2)
    result.check(
        ac_bonus2.advantage == AdvantageStatus.DISADVANTAGE,
        f"Ranged attacker (30ft) has disadvantage vs prone (got {ac_bonus2.advantage})"
    )

    # Removal
    target2.remove_condition("Prone")
    ac_bonus2 = get_defense_modifiers(target2, attacker2)
    result.check(
        ac_bonus2.advantage == AdvantageStatus.NONE,
        f"After removal: no advantage modifier (got {ac_bonus2.advantage})"
    )

    return result.summary()


def test_restrained() -> bool:
    """
    Restrained: Speed=0, disadvantage on attacks, disadvantage on DEX saves, attackers have advantage.
    """
    print_separator("TEST: RESTRAINED")
    result = TestResult()
    attacker, target = setup_combat_pair()

    restrained = Restrained(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(restrained)

    # Check 1: Speed = 0
    result.check(
        target.action_economy.movement.normalized_score == 0,
        f"Restrained speed = 0 (got {target.action_economy.movement.normalized_score})"
    )

    # Check 2: Disadvantage on attacks
    attack_bonus = get_attack_modifiers(target, attacker)
    result.check(
        attack_bonus.advantage == AdvantageStatus.DISADVANTAGE,
        f"Restrained has disadvantage on attacks (got {attack_bonus.advantage})"
    )

    # Check 3: Disadvantage on DEX saves (SRD: "disadvantage on Dexterity saving throws")
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    result.check(
        dex_save.bonus.advantage == AdvantageStatus.DISADVANTAGE,
        f"Restrained has disadvantage on DEX saves (got {dex_save.bonus.advantage})"
    )

    # Check 4: Attackers have advantage
    ac_bonus = get_defense_modifiers(target, attacker)
    result.check(
        ac_bonus.advantage == AdvantageStatus.ADVANTAGE,
        f"Attackers have advantage vs restrained (got {ac_bonus.advantage})"
    )

    # Removal
    target.remove_condition("Restrained")
    result.check(
        target.action_economy.movement.normalized_score > 0,
        f"After removal: speed restored (got {target.action_economy.movement.normalized_score})"
    )

    return result.summary()


def test_stunned() -> bool:
    """
    Stunned: Auto-fail STR/DEX saves, attackers have advantage. Includes Incapacitated.
    """
    print_separator("TEST: STUNNED")
    result = TestResult()
    attacker, target = setup_combat_pair()

    stunned = Stunned(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(stunned)

    # Check 1: Has Incapacitated sub-condition
    result.check(
        "Incapacitated" in target.active_conditions,
        f"Stunned includes Incapacitated sub-condition"
    )

    # Check 2: Auto-fail STR saves
    str_save = target.saving_throws.get_saving_throw("strength")
    result.check(
        str_save.bonus.auto_hit == AutoHitStatus.AUTOMISS,
        f"Stunned auto-fails STR saves (got {str_save.bonus.auto_hit})"
    )

    # Check 3: Auto-fail DEX saves
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    result.check(
        dex_save.bonus.auto_hit == AutoHitStatus.AUTOMISS,
        f"Stunned auto-fails DEX saves (got {dex_save.bonus.auto_hit})"
    )

    # Check 4: Attackers have advantage
    ac_bonus = get_defense_modifiers(target, attacker)
    result.check(
        ac_bonus.advantage == AdvantageStatus.ADVANTAGE,
        f"Attackers have advantage vs stunned (got {ac_bonus.advantage})"
    )

    # Removal
    target.remove_condition("Stunned")
    result.check(
        "Incapacitated" not in target.active_conditions,
        f"After removal: Incapacitated also removed"
    )

    return result.summary()


def test_unconscious() -> bool:
    """
    Unconscious: Auto-fail STR/DEX saves, advantage + auto-crit ≤5ft, prone-like ranged.
    Includes Incapacitated.
    """
    print_separator("TEST: UNCONSCIOUS")
    result = TestResult()

    # Test at melee range
    attacker, target = setup_combat_pair(distance_ft=5)
    unconscious = Unconscious(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(unconscious)

    # Check 1: Has Incapacitated sub-condition
    result.check(
        "Incapacitated" in target.active_conditions,
        f"Unconscious includes Incapacitated sub-condition"
    )

    # Check 2: Auto-fail STR saves
    str_save = target.saving_throws.get_saving_throw("strength")
    result.check(
        str_save.bonus.auto_hit == AutoHitStatus.AUTOMISS,
        f"Unconscious auto-fails STR saves (got {str_save.bonus.auto_hit})"
    )

    # Check 3: Auto-fail DEX saves
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    result.check(
        dex_save.bonus.auto_hit == AutoHitStatus.AUTOMISS,
        f"Unconscious auto-fails DEX saves (got {dex_save.bonus.auto_hit})"
    )

    # Check 4: Attackers have advantage
    ac_bonus = get_defense_modifiers(target, attacker)
    result.check(
        ac_bonus.advantage == AdvantageStatus.ADVANTAGE,
        f"Attackers have advantage vs unconscious (got {ac_bonus.advantage})"
    )

    # Check 5: Auto-crit within 5ft
    result.check(
        ac_bonus.critical == CriticalStatus.AUTOCRIT,
        f"Attackers get auto-crit within 5ft (got {ac_bonus.critical})"
    )

    # Test ranged (prone-like disadvantage cancels advantage)
    attacker2, target2 = setup_combat_pair(distance_ft=30)
    unconscious2 = Unconscious(source_entity_uuid=attacker2.uuid, target_entity_uuid=target2.uuid)
    target2.add_condition(unconscious2)

    ac_bonus2 = get_defense_modifiers(target2, attacker2)
    # Advantage (unconscious) + Disadvantage (prone-like at range) = NONE
    result.check(
        ac_bonus2.advantage == AdvantageStatus.NONE,
        f"Ranged attacker: advantage + disadvantage cancel (got {ac_bonus2.advantage})"
    )

    # Removal
    target2.remove_condition("Unconscious")
    result.check(
        "Incapacitated" not in target2.active_conditions,
        f"After removal: Incapacitated also removed"
    )

    return result.summary()


# =============================================================================
# COMBINATION TESTS
# =============================================================================

def test_multiple_disadvantages() -> bool:
    """
    Test that multiple disadvantage sources still result in disadvantage (no stacking).
    Poisoned + Blinded = still just disadvantage on attacks.
    """
    print_separator("TEST: MULTIPLE DISADVANTAGES (Poisoned + Blinded)")
    result = TestResult()
    attacker, target = setup_combat_pair()

    # Apply both conditions
    poisoned = Poisoned(source_entity_uuid=target.uuid, target_entity_uuid=attacker.uuid)
    blinded = Blinded(source_entity_uuid=target.uuid, target_entity_uuid=attacker.uuid)
    attacker.add_condition(poisoned)
    attacker.add_condition(blinded)

    # Check: Still disadvantage (not double disadvantage)
    attack_bonus = get_attack_modifiers(attacker, target)
    result.check(
        attack_bonus.advantage == AdvantageStatus.DISADVANTAGE,
        f"Multiple disadvantages = DISADVANTAGE (got {attack_bonus.advantage})"
    )

    # Remove one, still have disadvantage from other
    attacker.remove_condition("Poisoned")
    attack_bonus = get_attack_modifiers(attacker, target)
    result.check(
        attack_bonus.advantage == AdvantageStatus.DISADVANTAGE,
        f"After removing Poisoned, Blinded still gives disadvantage (got {attack_bonus.advantage})"
    )

    # Remove all
    attacker.remove_condition("Blinded")
    attack_bonus = get_attack_modifiers(attacker, target)
    result.check(
        attack_bonus.advantage == AdvantageStatus.NONE,
        f"After removing all: no disadvantage (got {attack_bonus.advantage})"
    )

    return result.summary()


def test_advantage_disadvantage_cancel() -> bool:
    """
    Test that advantage and disadvantage cancel each other.
    Target is Prone (attacker has advantage), but attacker is Poisoned (has disadvantage).
    """
    print_separator("TEST: ADVANTAGE + DISADVANTAGE CANCEL")
    result = TestResult()
    attacker, target = setup_combat_pair(distance_ft=5)

    # Attacker has Poisoned (disadvantage on attacks)
    poisoned = Poisoned(source_entity_uuid=target.uuid, target_entity_uuid=attacker.uuid)
    attacker.add_condition(poisoned)

    # Target is Prone (attacker gets advantage at melee via to_target_contextual)
    prone = Prone(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(prone)

    # Get combined attack roll modifiers with proper cross-entity propagation
    attacker.set_target_entity(target.uuid)
    target.set_target_entity(attacker.uuid)

    attack_bonus = attacker.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
    ac_bonus = target.ac_bonus(attacker.uuid)

    # KEY: Propagate to_target modifiers from prone target to attacker
    attack_bonus.set_from_target(ac_bonus)

    # Advantage (from prone target via to_target_contextual) + Disadvantage (from poisoned via self_static) = NONE
    result.check(
        attack_bonus.advantage == AdvantageStatus.NONE,
        f"Advantage + Disadvantage = NONE (got {attack_bonus.advantage})"
    )

    attacker.clear_target_entity()
    target.clear_target_entity()

    return result.summary()


def test_incapacitated_chain() -> bool:
    """
    Test conditions with Incapacitated sub-condition.
    Paralyzed and Stunned both add Incapacitated.
    """
    print_separator("TEST: INCAPACITATED SUB-CONDITIONS")
    result = TestResult()
    attacker, target = setup_combat_pair()

    # Apply Paralyzed (includes Incapacitated)
    paralyzed = Paralyzed(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(paralyzed)

    result.check(
        "Paralyzed" in target.active_conditions,
        "Paralyzed condition active"
    )
    result.check(
        "Incapacitated" in target.active_conditions,
        "Incapacitated sub-condition active"
    )
    result.check(
        target.action_economy.movement.normalized_score == 0,
        f"Movement = 0 (got {target.action_economy.movement.normalized_score})"
    )

    # Remove Paralyzed - should also remove Incapacitated
    target.remove_condition("Paralyzed")

    result.check(
        "Paralyzed" not in target.active_conditions,
        "Paralyzed removed"
    )
    result.check(
        "Incapacitated" not in target.active_conditions,
        "Incapacitated sub-condition also removed"
    )
    result.check(
        target.action_economy.movement.normalized_score > 0,
        f"Movement restored (got {target.action_economy.movement.normalized_score})"
    )

    return result.summary()


def test_stacking_movement_restrictions() -> bool:
    """
    Test multiple movement restrictions (Grappled + Restrained).
    Both set speed to 0.
    """
    print_separator("TEST: STACKING MOVEMENT RESTRICTIONS")
    result = TestResult()
    attacker, target = setup_combat_pair()

    # Apply both
    grappled = Grappled(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    restrained = Restrained(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid)
    target.add_condition(grappled)
    target.add_condition(restrained)

    result.check(
        target.action_economy.movement.normalized_score == 0,
        f"Both conditions: movement = 0 (got {target.action_economy.movement.normalized_score})"
    )

    # Remove one, still restricted
    target.remove_condition("Grappled")
    result.check(
        target.action_economy.movement.normalized_score == 0,
        f"After removing Grappled: still 0 from Restrained (got {target.action_economy.movement.normalized_score})"
    )

    # Remove other, restored
    target.remove_condition("Restrained")
    result.check(
        target.action_economy.movement.normalized_score > 0,
        f"After removing both: movement restored (got {target.action_economy.movement.normalized_score})"
    )

    return result.summary()


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print(" D&D 5e CONDITION EFFECTS TEST SUITE")
    print("=" * 70)
    print("\nTesting all conditions against expected effects from CLAUDE.md")
    print("These tests verify MODIFIERS (deterministic), not dice rolls (random).\n")

    all_tests = [
        ("Blinded", test_blinded),
        ("Charmed", test_charmed),
        ("Dashing", test_dashing),
        ("Deafened", test_deafened),
        ("Dodging", test_dodging),
        ("Frightened", test_frightened),
        ("Grappled", test_grappled),
        ("Incapacitated", test_incapacitated),
        ("Paralyzed", test_paralyzed),
        ("Poisoned", test_poisoned),
        ("Prone", test_prone),
        ("Restrained", test_restrained),
        ("Stunned", test_stunned),
        ("Unconscious", test_unconscious),
        # Combination tests
        ("Multiple Disadvantages", test_multiple_disadvantages),
        ("Advantage/Disadvantage Cancel", test_advantage_disadvantage_cancel),
        ("Incapacitated Chain", test_incapacitated_chain),
        ("Stacking Movement", test_stacking_movement_restrictions),
    ]

    passed = 0
    failed = 0
    failed_tests = []

    for name, test_fn in all_tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
                failed_tests.append(name)
        except Exception as e:
            failed += 1
            failed_tests.append(f"{name} (EXCEPTION: {e})")
            print(f"    ✗ EXCEPTION: {e}")

    print("\n" + "=" * 70)
    print(" FINAL RESULTS")
    print("=" * 70)
    print(f"\n  Tests passed: {passed}/{passed + failed}")

    if failed_tests:
        print(f"\n  FAILED TESTS:")
        for t in failed_tests:
            print(f"    - {t}")
        print("\n  SOME TESTS FAILED!")
        return False
    else:
        print("\n  ALL TESTS PASSED!")
        return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
