"""
Test Healing Spells Batch: Core fixes (RollType.HEAL, spell_level) + 10 spells.

Spells tested:
- Core: RollType.HEAL, spell_level on HealEvent
- Cure Wounds, Healing Word, Prayer of Healing, Mass Healing Word
- Mass Cure Wounds, Heal, Mass Heal
- Regenerate
- Lesser Restoration, Greater Restoration

Run: python examples/test_healing_spells.py
"""
from uuid import uuid4

from dnd.utils import reset_combat_state, get_hp, get_max_hp, deal_damage_to, has_condition
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.events import WeaponSlot, EventPhase, HealEvent
from dnd.core.modifiers import DamageType
from dnd.core.dice import RollType, Dice
from dnd.core.values import ModifiableValue
from dnd.items.weapons import create_scimitar
from dnd.actions_functional import setup_standard_actions, register_spells_by_name
from dnd.conditions import Blinded, Deafened, Poisoned, Paralyzed, Charmed, Frightened, Stunned
from dnd.encounter import Encounter
from dnd.controller import HumanController

from dnd.spells.evocation import (
    CureWounds, HealingWord, PrayerOfHealing, MassHealingWord,
    MassCureWounds, HealSpell, MassHeal
)
from dnd.spells.transmutation import Regenerate
from dnd.spells.abjuration import LesserRestoration, GreaterRestoration

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
    """Create a level 10 Cleric with WIS 18 (+4 mod), proficiency +3, spell DC 15."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=18),  # +4 mod
            strength=AbilityConfig(ability_score=14),
            dexterity=AbilityConfig(ability_score=12),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]),
        action_economy=ActionEconomyConfig(spell_slots={1: 4, 2: 3, 3: 3, 4: 2, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1}),
        equipment=EquipmentConfig(),
        proficiency_bonus=3,
        position=position,
        faction=faction,
        spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(entity)
    scimitar = create_scimitar(entity.uuid)
    entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
    register_spells_by_name(entity, [
        "Cure Wounds", "Healing Word", "Prayer of Healing", "Mass Healing Word",
        "Mass Cure Wounds", "Heal", "Mass Heal", "Regenerate",
        "Lesser Restoration", "Greater Restoration",
    ])
    return entity


def create_ally(name: str = "Ally", position: tuple = (1, 0), faction: str = "heroes") -> Entity:
    """Create an ally with 50 max HP."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            constitution=AbilityConfig(ability_score=14),
            wisdom=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="maximums")]),
        equipment=EquipmentConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(entity)
    return entity


def create_enemy(name: str = "Enemy", position: tuple = (3, 0), faction: str = "enemies") -> Entity:
    """Create an enemy for negative tests."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]),
        equipment=EquipmentConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(entity)
    return entity


def setup_arena():
    """Standard arena reset with tile grid and senses update."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)


def setup_encounter(*entities: Entity) -> Encounter:
    """Create an encounter and start it."""
    encounter = Encounter(name="Test Healing", source_entity_uuid=uuid4())
    for e in entities:
        encounter.add_combatant(e, HumanController(source_entity_uuid=e.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    return encounter


def advance_to_combatant(encounter: Encounter, entity: Entity) -> None:
    """Advance encounter turns until it's entity's turn (turn already started)."""
    encounter.start_turn()
    combatant = encounter.get_current_combatant()
    while combatant and combatant.entity_uuid != entity.uuid:
        encounter.end_turn()
        encounter.next_turn()
        combatant = encounter.get_current_combatant()


# =============================================================================
# CORE FIXES
# =============================================================================

def test_rolltype_heal_multi_dice():
    """RollType.HEAL allows multi-dice (like DAMAGE)."""
    section("RollType.HEAL multi-dice")

    dice = Dice(
        count=3,
        value=8,
        bonus=ModifiableValue.create(source_entity_uuid=uuid4(), base_value=4, value_name="Test"),
        roll_type=RollType.HEAL
    )
    roll = dice.roll
    check(roll.roll_type == RollType.HEAL, "Roll type is HEAL")
    # 3d8+4: min=7, max=28
    check(7 <= roll.total <= 28, f"Total in range: {roll.total}")
    results = roll.results
    check(isinstance(results, list) and len(results) == 3, f"3 dice results: {results}")


def test_spell_level_default_zero():
    """HealEvent spell_level defaults to 0."""
    section("spell_level default")

    heal_event = HealEvent(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        total_healing=10,
        phase=EventPhase.DECLARATION
    )
    check(heal_event.spell_level == 0, "Default spell_level is 0")


def test_spell_level_passed_through():
    """receive_healing passes spell_level to HealEvent."""
    section("spell_level passthrough")
    setup_arena()

    ally = create_ally()
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 10, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    actual = ally.receive_healing(
        5, uuid4(),
        source_description="Test",
        spell_level=3
    )
    check(actual > 0, f"Healing applied: {actual}")
    check(get_hp(ally) == hp_before + actual, "HP increased correctly")


# =============================================================================
# CURE WOUNDS
# =============================================================================

def test_cure_wounds_basic():
    """Cure Wounds heals an injured ally."""
    section("Cure Wounds basic")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 20, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    spell = CureWounds(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=1,
        caster_level=10,
    )
    spell.apply()

    hp_after = get_hp(ally)
    healed = hp_after - hp_before
    # 1d8+4: min 5, max 12
    check(healed >= 5, f"Healed at least 5: {healed}")
    check(healed <= 12, f"Healed at most 12: {healed}")


def test_cure_wounds_upcast():
    """Cure Wounds at level 3 heals 3d8+4."""
    section("Cure Wounds upcast L3")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 40, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    spell = CureWounds(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=3,
        caster_level=10,
    )
    spell.apply()

    healed = get_hp(ally) - hp_before
    # 3d8+4: min 7, max 28
    check(healed >= 7, f"L3 healed at least 7: {healed}")
    check(healed <= 28, f"L3 healed at most 28: {healed}")


def test_cure_wounds_hp_cap():
    """Cure Wounds doesn't heal above max HP."""
    section("Cure Wounds HP cap")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    max_hp = get_max_hp(ally)
    deal_damage_to(ally, 2, DamageType.SLASHING, uuid4())

    spell = CureWounds(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=3,
        caster_level=10,
    )
    spell.apply()

    check(get_hp(ally) == max_hp, f"HP at max: {get_hp(ally)} == {max_hp}")


def test_cure_wounds_self_target():
    """Cure Wounds can target self."""
    section("Cure Wounds self-target")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    Entity.update_all_entities_senses()

    max_hp = get_max_hp(cleric)
    deal_damage_to(cleric, 15, DamageType.SLASHING, cleric.uuid)
    hp_before = get_hp(cleric)
    check(hp_before < max_hp, f"Damage applied: {hp_before} < {max_hp}")

    spell = CureWounds(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=cleric.uuid,
        cast_at_level=1,
        caster_level=10,
    )
    spell.apply()

    check(get_hp(cleric) > hp_before, f"Cleric healed self: {get_hp(cleric)} > {hp_before}")


# =============================================================================
# HEALING WORD
# =============================================================================

def test_healing_word_basic():
    """Healing Word heals an ally at 60ft range."""
    section("Healing Word basic")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(10, 0))  # 50ft
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 15, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    spell = HealingWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=1,
        caster_level=10,
    )
    spell.apply()

    healed = get_hp(ally) - hp_before
    # 1d4+4: min 5, max 8
    check(healed >= 5, f"Healed at least 5: {healed}")
    check(healed <= 8, f"Healed at most 8: {healed}")


def test_healing_word_bonus_action_cost():
    """Healing Word costs a bonus action (not an action)."""
    section("Healing Word bonus action cost")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    encounter = setup_encounter(cleric, ally)
    advance_to_combatant(encounter, cleric)

    deal_damage_to(ally, 10, DamageType.SLASHING, uuid4())

    ba_before = cleric.action_economy.bonus_actions.normalized_score
    actions_before = cleric.action_economy.actions.normalized_score

    spell = HealingWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=1,
        caster_level=10,
    )
    spell.apply()

    ba_after = cleric.action_economy.bonus_actions.normalized_score
    actions_after = cleric.action_economy.actions.normalized_score
    check(ba_after == ba_before - 1, f"Bonus action consumed: {ba_before} -> {ba_after}")
    check(actions_after == actions_before, f"Action NOT consumed: {actions_before} -> {actions_after}")


def test_healing_word_upcast():
    """Healing Word at L2 heals 2d4+4."""
    section("Healing Word upcast L2")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 20, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    spell = HealingWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
        caster_level=10,
    )
    spell.apply()

    healed = get_hp(ally) - hp_before
    # 2d4+4: min 6, max 12
    check(healed >= 6, f"L2 healed at least 6: {healed}")
    check(healed <= 12, f"L2 healed at most 12: {healed}")


# =============================================================================
# PRAYER OF HEALING
# =============================================================================

def test_prayer_of_healing_multi():
    """Prayer of Healing heals multiple allies."""
    section("Prayer of Healing multi-target")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    a1 = create_ally(name="Ally1", position=(1, 0))
    a2 = create_ally(name="Ally2", position=(2, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(a1, 20, DamageType.SLASHING, uuid4())
    deal_damage_to(a2, 20, DamageType.SLASHING, uuid4())
    hp1_before = get_hp(a1)
    hp2_before = get_hp(a2)

    spell = PrayerOfHealing(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=a1.uuid,
        extra_target_entity_uuids=[a2.uuid],
        cast_at_level=2,
        caster_level=10,
    )
    spell.apply()

    check(get_hp(a1) > hp1_before, f"Ally1 healed: {get_hp(a1)} > {hp1_before}")
    check(get_hp(a2) > hp2_before, f"Ally2 healed: {get_hp(a2)} > {hp2_before}")


def test_prayer_of_healing_enemies_excluded():
    """Prayer of Healing doesn't heal enemies."""
    section("Prayer of Healing enemy filter")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    enemy = create_enemy(position=(2, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(enemy, 10, DamageType.SLASHING, uuid4())
    hp_before = get_hp(enemy)

    spell = PrayerOfHealing(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=enemy.uuid,
        cast_at_level=2,
        caster_level=10,
    )
    spell.apply()

    check(get_hp(enemy) == hp_before, f"Enemy NOT healed: {get_hp(enemy)} == {hp_before}")


# =============================================================================
# MASS HEALING WORD
# =============================================================================

def test_mass_healing_word_multi():
    """Mass Healing Word heals multiple allies as bonus action."""
    section("Mass Healing Word multi")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    a1 = create_ally(name="Ally1", position=(1, 0))
    a2 = create_ally(name="Ally2", position=(2, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(a1, 15, DamageType.SLASHING, uuid4())
    deal_damage_to(a2, 15, DamageType.SLASHING, uuid4())
    hp1_before = get_hp(a1)
    hp2_before = get_hp(a2)

    spell = MassHealingWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=a1.uuid,
        extra_target_entity_uuids=[a2.uuid],
        cast_at_level=3,
        caster_level=10,
    )
    spell.apply()

    check(get_hp(a1) > hp1_before, f"Ally1 healed: {get_hp(a1)} > {hp1_before}")
    check(get_hp(a2) > hp2_before, f"Ally2 healed: {get_hp(a2)} > {hp2_before}")


def test_mass_healing_word_upcast():
    """Mass Healing Word at L5 heals 3d4+4."""
    section("Mass Healing Word upcast L5")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 30, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    spell = MassHealingWord(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=5,
        caster_level=10,
    )
    spell.apply()

    healed = get_hp(ally) - hp_before
    # 3d4+4 (L5 = 1 + 5-3 = 3 dice): min 7, max 16
    check(healed >= 7, f"L5 healed at least 7: {healed}")
    check(healed <= 16, f"L5 healed at most 16: {healed}")


# =============================================================================
# MASS CURE WOUNDS
# =============================================================================

def test_mass_cure_wounds_aoe():
    """Mass Cure Wounds heals allies in 30ft sphere."""
    section("Mass Cure Wounds AoE")
    setup_arena()

    cleric = create_cleric(position=(5, 5))
    a1 = create_ally(name="Ally1", position=(6, 5))
    a2 = create_ally(name="Ally2", position=(5, 6))
    enemy = create_enemy(position=(7, 5))
    Entity.update_all_entities_senses()

    deal_damage_to(a1, 25, DamageType.SLASHING, uuid4())
    deal_damage_to(a2, 25, DamageType.SLASHING, uuid4())
    deal_damage_to(enemy, 25, DamageType.SLASHING, uuid4())

    hp1_before = get_hp(a1)
    hp2_before = get_hp(a2)
    enemy_hp_before = get_hp(enemy)

    spell = MassCureWounds(
        source_entity_uuid=cleric.uuid,
        end_position=(6, 6),
        cast_at_level=5,
        caster_level=10,
    )
    spell.apply()

    check(get_hp(a1) > hp1_before, f"Ally1 healed: {get_hp(a1)} > {hp1_before}")
    check(get_hp(a2) > hp2_before, f"Ally2 healed: {get_hp(a2)} > {hp2_before}")
    check(get_hp(enemy) == enemy_hp_before, f"Enemy NOT healed: {get_hp(enemy)} == {enemy_hp_before}")


def test_mass_cure_wounds_upcast():
    """Mass Cure Wounds at L7 heals 5d8+4."""
    section("Mass Cure Wounds upcast L7")
    setup_arena()

    cleric = create_cleric(position=(5, 5))
    ally = create_ally(position=(6, 5))
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 50, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    spell = MassCureWounds(
        source_entity_uuid=cleric.uuid,
        end_position=(6, 5),
        cast_at_level=7,
        caster_level=10,
    )
    spell.apply()

    healed = get_hp(ally) - hp_before
    # 5d8+4: min 9, max 44
    check(healed >= 9, f"L7 healed at least 9: {healed}")
    check(healed <= 44, f"L7 healed at most 44: {healed}")


# =============================================================================
# HEAL
# =============================================================================

def test_heal_flat_70():
    """Heal restores 70 HP."""
    section("Heal flat 70 HP")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    max_hp = get_max_hp(ally)
    # Set ally to low HP
    deal_damage_to(ally, max_hp - 1, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    spell = HealSpell(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=6,
        caster_level=10,
    )
    spell.apply()

    healed = get_hp(ally) - hp_before
    # 70 HP healed, but capped at max HP
    expected = min(70, max_hp - hp_before)
    check(healed == expected, f"Healed {expected}: {healed}")


def test_heal_removes_blinded():
    """Heal removes Blinded condition."""
    section("Heal removes Blinded")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    blinded = Blinded(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(blinded)
    check(has_condition(ally, "Blinded"), "Ally is blinded")

    deal_damage_to(ally, 10, DamageType.SLASHING, uuid4())

    spell = HealSpell(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=6,
        caster_level=10,
    )
    spell.apply()

    check(not has_condition(ally, "Blinded"), "Blinded removed by Heal")


def test_heal_removes_deafened():
    """Heal removes Deafened condition."""
    section("Heal removes Deafened")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    deafened = Deafened(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(deafened)
    check(has_condition(ally, "Deafened"), "Ally is deafened")

    deal_damage_to(ally, 10, DamageType.SLASHING, uuid4())

    spell = HealSpell(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=6,
        caster_level=10,
    )
    spell.apply()

    check(not has_condition(ally, "Deafened"), "Deafened removed by Heal")


def test_heal_upcast():
    """Heal at L8 heals 90 HP (70 + 20)."""
    section("Heal upcast L8")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    max_hp = get_max_hp(ally)
    deal_damage_to(ally, max_hp - 1, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    spell = HealSpell(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=8,
        caster_level=10,
    )
    spell.apply()

    healed = get_hp(ally) - hp_before
    expected = min(90, max_hp - hp_before)
    check(healed == expected, f"L8 healed {expected}: {healed}")


# =============================================================================
# MASS HEAL
# =============================================================================

def test_mass_heal_pool():
    """Mass Heal distributes 700 HP pool among targets."""
    section("Mass Heal pool distribution")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    a1 = create_ally(name="Ally1", position=(1, 0))
    a2 = create_ally(name="Ally2", position=(2, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(a1, 20, DamageType.SLASHING, uuid4())
    deal_damage_to(a2, 30, DamageType.SLASHING, uuid4())

    spell = MassHeal(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=a1.uuid,
        extra_target_entity_uuids=[a2.uuid],
        cast_at_level=9,
        caster_level=10,
    )
    spell.apply()

    # Both should be fully healed (20+30=50 << 700)
    check(get_hp(a1) == get_max_hp(a1), f"Ally1 fully healed: {get_hp(a1)}")
    check(get_hp(a2) == get_max_hp(a2), f"Ally2 fully healed: {get_hp(a2)}")
    check(spell.healing_pool_remaining == 700 - 20 - 30,
          f"Pool remaining: {spell.healing_pool_remaining}")


def test_mass_heal_removes_conditions():
    """Mass Heal removes Blinded/Deafened from healed targets."""
    section("Mass Heal condition removal")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    blinded = Blinded(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(blinded)
    deal_damage_to(ally, 10, DamageType.SLASHING, uuid4())

    spell = MassHeal(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=9,
        caster_level=10,
    )
    spell.apply()

    check(not has_condition(ally, "Blinded"), "Blinded removed by Mass Heal")


# =============================================================================
# REGENERATE
# =============================================================================

def test_regenerate_instant_heal():
    """Regenerate heals 4d8+15 instantly."""
    section("Regenerate instant heal")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 50, DamageType.SLASHING, uuid4())
    hp_before = get_hp(ally)

    spell = Regenerate(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=7,
        caster_level=10,
    )
    spell.apply()

    healed = get_hp(ally) - hp_before
    # 4d8+15: min 19, max 47
    check(healed >= 19, f"Instant heal at least 19: {healed}")
    check(healed <= 47, f"Instant heal at most 47: {healed}")
    check(has_condition(ally, "Regenerating"), "Regenerating condition applied")


def test_regenerate_per_turn():
    """Regenerate heals 1 HP per turn via condition."""
    section("Regenerate per-turn heal")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 50, DamageType.SLASHING, uuid4())

    spell = Regenerate(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=7,
        caster_level=10,
    )
    spell.apply()

    hp_after_cast = get_hp(ally)

    # Set up encounter to cycle turns
    encounter = setup_encounter(ally, cleric)
    advance_to_combatant(encounter, ally)

    hp_after_turn_start = get_hp(ally)
    healed_on_turn = hp_after_turn_start - hp_after_cast
    check(healed_on_turn == 1, f"Healed 1 HP on turn start: {healed_on_turn}")


def test_regenerate_expires():
    """Regenerate condition expires after 10 rounds."""
    section("Regenerate expiry")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    deal_damage_to(ally, 50, DamageType.SLASHING, uuid4())

    spell = Regenerate(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=7,
        caster_level=10,
    )
    spell.apply()

    encounter = setup_encounter(ally, cleric)

    # Cycle through 10 rounds (each has ally + cleric turns)
    for i in range(10):
        if i == 0:
            advance_to_combatant(encounter, ally)
        else:
            # next_turn auto-calls start_turn, cycle until ally's turn
            combatant = encounter.get_current_combatant()
            while combatant and combatant.entity_uuid != ally.uuid:
                encounter.end_turn()
                encounter.next_turn()
                combatant = encounter.get_current_combatant()
        encounter.end_turn()
        encounter.next_turn()

    check(not has_condition(ally, "Regenerating"), "Regenerating removed after 10 rounds")


def test_regenerate_not_concentration():
    """Regenerate is NOT a concentration spell."""
    section("Regenerate not concentration")

    spell = Regenerate(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        cast_at_level=7,
        caster_level=10,
    )
    check(spell.concentration is False, "Regenerate is NOT concentration")


# =============================================================================
# LESSER RESTORATION
# =============================================================================

def test_lesser_restoration_blinded():
    """Lesser Restoration removes Blinded."""
    section("Lesser Restoration removes Blinded")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    blinded = Blinded(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(blinded)
    check(has_condition(ally, "Blinded"), "Blinded applied")

    spell = LesserRestoration(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
        caster_level=10,
    )
    spell.apply()

    check(not has_condition(ally, "Blinded"), "Blinded removed")


def test_lesser_restoration_poisoned():
    """Lesser Restoration removes Poisoned."""
    section("Lesser Restoration removes Poisoned")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    poisoned = Poisoned(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(poisoned)
    check(has_condition(ally, "Poisoned"), "Poisoned applied")

    spell = LesserRestoration(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
        caster_level=10,
    )
    spell.apply()

    check(not has_condition(ally, "Poisoned"), "Poisoned removed")


def test_lesser_restoration_paralyzed():
    """Lesser Restoration removes Paralyzed."""
    section("Lesser Restoration removes Paralyzed")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    paralyzed = Paralyzed(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(paralyzed)
    check(has_condition(ally, "Paralyzed"), "Paralyzed applied")

    spell = LesserRestoration(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
        caster_level=10,
    )
    spell.apply()

    check(not has_condition(ally, "Paralyzed"), "Paralyzed removed")


def test_lesser_restoration_no_stunned():
    """Lesser Restoration does NOT remove Stunned (not in its list)."""
    section("Lesser Restoration doesn't remove Stunned")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    stunned = Stunned(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(stunned)
    check(has_condition(ally, "Stunned"), "Stunned applied")

    spell = LesserRestoration(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
        caster_level=10,
    )
    spell.apply()

    check(has_condition(ally, "Stunned"), "Stunned NOT removed (not in Lesser Restoration list)")


# =============================================================================
# GREATER RESTORATION
# =============================================================================

def test_greater_restoration_charmed():
    """Greater Restoration removes Charmed."""
    section("Greater Restoration removes Charmed")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    charmed = Charmed(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(charmed)
    check(has_condition(ally, "Charmed"), "Charmed applied")

    spell = GreaterRestoration(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=5,
        caster_level=10,
    )
    spell.apply()

    check(not has_condition(ally, "Charmed"), "Charmed removed")


def test_greater_restoration_frightened():
    """Greater Restoration removes Frightened."""
    section("Greater Restoration removes Frightened")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    frightened = Frightened(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(frightened)
    check(has_condition(ally, "Frightened"), "Frightened applied")

    spell = GreaterRestoration(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=5,
        caster_level=10,
    )
    spell.apply()

    check(not has_condition(ally, "Frightened"), "Frightened removed")


def test_greater_restoration_stunned():
    """Greater Restoration removes Stunned."""
    section("Greater Restoration removes Stunned")
    setup_arena()

    cleric = create_cleric(position=(0, 0))
    ally = create_ally(position=(1, 0))
    Entity.update_all_entities_senses()

    stunned = Stunned(source_entity_uuid=uuid4(), target_entity_uuid=ally.uuid)
    ally.add_condition(stunned)
    check(has_condition(ally, "Stunned"), "Stunned applied")

    spell = GreaterRestoration(
        source_entity_uuid=cleric.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=5,
        caster_level=10,
    )
    spell.apply()

    check(not has_condition(ally, "Stunned"), "Stunned removed")


# =============================================================================
# RUN ALL
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("HEALING SPELLS TEST SUITE")
    print("=" * 60)

    # Core fixes
    test_rolltype_heal_multi_dice()
    test_spell_level_default_zero()
    test_spell_level_passed_through()

    # Cure Wounds
    test_cure_wounds_basic()
    test_cure_wounds_upcast()
    test_cure_wounds_hp_cap()
    test_cure_wounds_self_target()

    # Healing Word
    test_healing_word_basic()
    test_healing_word_bonus_action_cost()
    test_healing_word_upcast()

    # Prayer of Healing
    test_prayer_of_healing_multi()
    test_prayer_of_healing_enemies_excluded()

    # Mass Healing Word
    test_mass_healing_word_multi()
    test_mass_healing_word_upcast()

    # Mass Cure Wounds
    test_mass_cure_wounds_aoe()
    test_mass_cure_wounds_upcast()

    # Heal
    test_heal_flat_70()
    test_heal_removes_blinded()
    test_heal_removes_deafened()
    test_heal_upcast()

    # Mass Heal
    test_mass_heal_pool()
    test_mass_heal_removes_conditions()

    # Regenerate
    test_regenerate_instant_heal()
    test_regenerate_per_turn()
    test_regenerate_expires()
    test_regenerate_not_concentration()

    # Lesser Restoration
    test_lesser_restoration_blinded()
    test_lesser_restoration_poisoned()
    test_lesser_restoration_paralyzed()
    test_lesser_restoration_no_stunned()

    # Greater Restoration
    test_greater_restoration_charmed()
    test_greater_restoration_frightened()
    test_greater_restoration_stunned()

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
    print(f"{'=' * 60}")

    if failed > 0:
        exit(1)
