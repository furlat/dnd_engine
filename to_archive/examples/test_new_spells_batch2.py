"""Tests for the 9-spell batch: Counterspell, Enhance Ability, Enlarge/Reduce,
Stinking Cloud, Sleet Storm, Chain Lightning, Eyebite, Prismatic Spray, Dimension Door.
"""
import random

from dnd.utils import (
    reset_combat_state, get_hp, set_hp, deal_damage_to,
    get_position, has_condition,
)
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import Size, DamageType, AdvantageStatus, NumericalModifier
from dnd.core.events import EventQueue, AbilityName
from dnd.entity import Entity, get_natural_roll
from dnd.monsters.bestiary import create_caster, create_skeleton
from dnd.actions_functional import setup_standard_actions, register_spell
from dnd.items.weapons import create_longsword
from dnd.blocks.equipment import WeaponSlot
from dnd.spells import (
    EnhanceAbility, EnlargeReduce, StinkingCloud, SleetStorm,
    ChainLightning, Eyebite, PrismaticSpray, DimensionDoor,
    register_counterspell_reaction, Fireball,
)

passed = 0
failed = 0


def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")


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


def setup_arena(size: int = 30):
    """Set up a floor arena."""
    reset_map()
    grid = get_map()
    for x in range(size):
        for y in range(size):
            grid.set_tile(x, y, walkable=True, name="Floor")
    return grid


def force_fail_save(entity: Entity, ability: AbilityName):
    """Force an entity to fail a saving throw by adding -100 penalty."""
    save = entity.saving_throws.get_saving_throw(ability)
    return save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(source_entity_uuid=entity.uuid, name="Force Fail", value=-100)
    )


def force_pass_save(entity: Entity, ability: AbilityName):
    """Force an entity to pass a saving throw by adding +100 bonus."""
    save = entity.saving_throws.get_saving_throw(ability)
    return save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(source_entity_uuid=entity.uuid, name="Force Pass", value=100)
    )


# =============================================================================
# TEST 1: Counterspell — actually counter a spell
# =============================================================================
print("\n=== TEST 1: Counterspell ===")

for attempt in range(10):
    reset_combat_state()
    grid = setup_arena()

    caster = create_caster(name="Enemy Mage", position=(5, 5), level=7)
    counter = create_caster(name="Counter-Mage", position=(7, 5), level=7)
    target = create_skeleton(name="Target", position=(5, 8))

    counter.faction = "team_blue"
    target.faction = "team_blue"
    caster.faction = "team_red"

    register_counterspell_reaction(counter)
    register_spell(caster, Fireball, caster_level=7)

    Entity.update_all_entities_senses()

    # Verify setup
    test("Counter can see caster", caster.uuid in counter.senses.entities)
    test("Counter within 60ft", counter.senses.get_feet_distance(caster.position) <= 60)

    handler = counter.get_event_handler_by_name("Counterspell")
    test("Counterspell handler registered", handler is not None)

    # Cast Fireball (L3 spell) — counter-mage has L3 slots, should auto-counter
    target_hp_before = get_hp(target)
    set_hp(target, 200)  # High HP so we can check damage
    target_hp_before = get_hp(target)

    fireball = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(5, 8),
        cast_at_level=3,
        template=False,
        costs=[]
    )
    result = fireball.apply()

    if had_critical_d20():
        print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
        continue

    # If counterspell worked, target should take no damage
    target_hp_after = get_hp(target)
    spell_was_countered = result is not None and result.canceled
    test("Fireball was countered", spell_was_countered)
    test("Target took no damage (spell countered)", target_hp_after == target_hp_before)

    # Counter-mage should have consumed reaction + spell slot
    test("Reaction consumed", not counter.action_economy.can_afford("reactions", 1))

    # Now test that counter can't counter again (no reaction left)
    set_hp(target, 200)
    target_hp_before2 = get_hp(target)
    fireball2 = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(5, 8),
        cast_at_level=3,
        template=False,
        costs=[]
    )
    result2 = fireball2.apply()
    target_hp_after2 = get_hp(target)
    test("Second Fireball NOT countered (no reaction)", target_hp_after2 < target_hp_before2)
    break
else:
    print("  SKIP: Could not avoid nat 1/20 in 10 attempts")


# =============================================================================
# TEST 2: Enhance Ability — advantage + Bear's Endurance temp HP
# =============================================================================
print("\n=== TEST 2: Enhance Ability ===")

reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Buff Caster", position=(5, 5), level=5)
caster.faction = "team_blue"
setup_standard_actions(caster)
Entity.update_all_entities_senses()

# Cast Enhance Ability (Bull's Strength = STR advantage)
spell = EnhanceAbility(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    enhance_ability_type="strength",
    cast_at_level=2,
    template=False,
    costs=[]
)
result = spell.apply()
test("Enhance Ability cast succeeds", result is not None and not result.canceled)
test("Condition applied", has_condition(caster, "Enhance Ability"))
test("Concentrating", has_condition(caster, "Concentrating"))

# Check advantage on STR checks
str_ability = caster.ability_scores.get_ability("strength")
test("STR checks have advantage", str_ability.ability_score.advantage == AdvantageStatus.ADVANTAGE)

# Other abilities should NOT have advantage
dex_ability = caster.ability_scores.get_ability("dexterity")
test("DEX checks unchanged", dex_ability.ability_score.advantage == AdvantageStatus.NONE)

# Concentration break removes
caster.remove_condition("Concentrating")
test("Concentration break removes Enhance Ability", not has_condition(caster, "Enhance Ability"))
test("STR advantage removed", str_ability.ability_score.advantage == AdvantageStatus.NONE)

# Bear's Endurance: CON variant grants temp HP
reset_combat_state()
grid = setup_arena()
caster = create_caster(name="Bear Caster", position=(5, 5), level=5)
setup_standard_actions(caster)
Entity.update_all_entities_senses()

spell_bear = EnhanceAbility(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    enhance_ability_type="constitution",
    cast_at_level=2,
    template=False,
    costs=[]
)
temp_hp_before = caster.health.temporary_hit_points.score
result = spell_bear.apply()
temp_hp_after = caster.health.temporary_hit_points.score
test("Bear's Endurance grants temp HP", temp_hp_after > temp_hp_before)
test("Temp HP is 2-12 range (2d6)", 2 <= temp_hp_after <= 12)


# =============================================================================
# TEST 3: Enlarge/Reduce — full mechanics
# =============================================================================
print("\n=== TEST 3: Enlarge/Reduce ===")

reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Size Mage", position=(5, 5), level=5)
target = create_caster(name="Warrior", position=(6, 5), level=5)
caster.faction = "team_blue"
target.faction = "team_blue"
setup_standard_actions(caster)
setup_standard_actions(target)

# Give target a weapon to check damage dice
longsword = create_longsword(target.uuid)
target.equipment.equip(longsword, WeaponSlot.MELEE_MAIN)

Entity.update_all_entities_senses()

# Test enlarge
test("Target starts Medium", target.size == Size.MEDIUM)

spell_enlarge = EnlargeReduce(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    enlarge_mode="enlarge",
    cast_at_level=2,
    template=False,
    costs=[]
)
result = spell_enlarge.apply()
test("Enlarge succeeds", result is not None and not result.canceled)
test("Target is now Large", target.size == Size.LARGE)
test("Condition applied", has_condition(target, "Enlarge/Reduce"))
test("Caster concentrating", has_condition(caster, "Concentrating"))

# STR advantage
str_ability = target.ability_scores.get_ability("strength")
test("STR checks have advantage", str_ability.ability_score.advantage == AdvantageStatus.ADVANTAGE)

# STR saves have advantage
str_save = target.saving_throws.get_saving_throw("strength")
test("STR saves have advantage", str_save.bonus.advantage == AdvantageStatus.ADVANTAGE)

# Size-based damage dice
test("Large: 1 extra d4", target.get_size_damage_dice() == 1)
damages = target.get_damages(WeaponSlot.MELEE_MAIN)
has_size_damage = any(d.damage_dice == 4 and d.dice_numbers == 1 for d in damages)
test("Damages include 1d4 from size", has_size_damage)

# Concentration break restores
caster.remove_condition("Concentrating")
test("Size restored after concentration break", target.size == Size.MEDIUM)
test("Condition removed", not has_condition(target, "Enlarge/Reduce"))
test("STR advantage removed", str_ability.ability_score.advantage == AdvantageStatus.NONE)
test("Size dice back to 0", target.get_size_damage_dice() == 0)

# Test reduce on ally
reset_combat_state()
grid = setup_arena()
caster = create_caster(name="Reduce Mage", position=(5, 5), level=5)
target = create_caster(name="Small Friend", position=(6, 5), level=5)
caster.faction = "team_blue"
target.faction = "team_blue"
setup_standard_actions(caster)
setup_standard_actions(target)
Entity.update_all_entities_senses()

spell_reduce = EnlargeReduce(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    enlarge_mode="reduce",
    cast_at_level=2,
    template=False,
    costs=[]
)
result = spell_reduce.apply()
test("Reduce succeeds", result is not None and not result.canceled)
test("Target is now Small", target.size == Size.SMALL)
str_ability_r = target.ability_scores.get_ability("strength")
test("STR checks have disadvantage", str_ability_r.ability_score.advantage == AdvantageStatus.DISADVANTAGE)

# Test enlarge on unwilling enemy — CON save to resist
for attempt in range(10):
    reset_combat_state()
    grid = setup_arena()
    caster = create_caster(name="Enemy Mage", position=(5, 5), level=5)
    enemy = create_caster(name="Enemy", position=(6, 5), level=5)
    caster.faction = "team_blue"
    enemy.faction = "team_red"
    setup_standard_actions(caster)
    setup_standard_actions(enemy)

    # Force enemy to pass CON save
    force_pass_save(enemy, "constitution")
    Entity.update_all_entities_senses()

    spell_enemy = EnlargeReduce(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemy.uuid,
        enlarge_mode="enlarge",
        cast_at_level=2,
        template=False,
        costs=[]
    )
    result = spell_enemy.apply()

    if had_critical_d20():
        print(f"  Attempt {attempt + 1}: nat 1/20, retrying...")
        continue

    # Enemy saved — should still be Medium
    test("Enemy resists with CON save (stays Medium)", enemy.size == Size.MEDIUM)
    test("No condition on enemy", not has_condition(enemy, "Enlarge/Reduce"))
    break
else:
    print("  SKIP: Could not avoid nat 1/20 in 10 attempts")


# =============================================================================
# TEST 4: Stinking Cloud — turn start nauseation
# =============================================================================
print("\n=== TEST 4: Stinking Cloud ===")

for attempt in range(10):
    reset_combat_state()
    grid = setup_arena()

    caster = create_caster(name="Cloud Caster", position=(5, 5), level=5)
    enemy = create_caster(name="Cloud Victim", position=(10, 10), level=5)
    caster.faction = "team_blue"
    enemy.faction = "team_red"
    setup_standard_actions(caster)
    setup_standard_actions(enemy)

    # Force enemy to fail CON save
    force_fail_save(enemy, "constitution")

    Entity.update_all_entities_senses()

    spell = StinkingCloud(
        source_entity_uuid=caster.uuid,
        end_position=(10, 10),
        cast_at_level=3,
        template=False,
        costs=[]
    )
    result = spell.apply()
    test("Stinking Cloud cast succeeds", result is not None and not result.canceled)
    test("Zone condition on caster", has_condition(caster, "Stinking Cloud Zone"))
    test("Concentrating", has_condition(caster, "Concentrating"))

    # Enemy starts turn in cloud → CON save or nauseated
    test("Enemy NOT nauseated yet (hasn't started turn)", not has_condition(enemy, "Nauseated"))

    # Fire turn start
    enemy.on_turn_start()

    if had_critical_d20():
        print(f"  Attempt {attempt + 1}: nat 1/20, retrying...")
        continue

    test("Enemy nauseated after turn start", has_condition(enemy, "Nauseated"))

    actions_available = enemy.action_economy.actions.normalized_score
    bonus_available = enemy.action_economy.bonus_actions.normalized_score
    test("Actions locked to 0", actions_available == 0)
    test("Bonus actions still available", bonus_available == 1)

    # But movement still works
    movement = enemy.action_economy.movement.normalized_score
    test("Movement still available", movement > 0)

    # Concentration break removes zone
    caster.remove_condition("Concentrating")
    test("Zone removed on concentration break", not has_condition(caster, "Stinking Cloud Zone"))
    break
else:
    print("  SKIP: Could not avoid nat 1/20 in 10 attempts")


# =============================================================================
# TEST 5: Sleet Storm — entry prone + turn start prone + concentration disruption
# =============================================================================
print("\n=== TEST 5: Sleet Storm ===")

# Test entry effect: DEX save or prone
for attempt in range(10):
    reset_combat_state()
    grid = setup_arena()

    caster = create_caster(name="Storm Caster", position=(5, 5), level=5)
    # Place enemy FAR from zone center so they're outside 40ft radius at cast time
    enemy = create_skeleton(name="Storm Target", position=(25, 5))
    caster.faction = "team_blue"
    enemy.faction = "team_red"
    setup_standard_actions(caster)
    setup_standard_actions(enemy)

    # Force DEX save fail
    force_fail_save(enemy, "dexterity")
    Entity.update_all_entities_senses()

    # Cast sleet storm at (8, 8) — within caster's 50ft vision
    spell = SleetStorm(
        source_entity_uuid=caster.uuid,
        end_position=(8, 8),
        cast_at_level=3,
        template=False,
        costs=[]
    )
    result = spell.apply()
    test("Sleet Storm cast succeeds", result is not None and not result.canceled)
    test("Zone condition on caster", has_condition(caster, "Sleet Storm Zone"))

    # Enemy is outside zone — should NOT be prone
    test("Enemy not prone before entering zone", not has_condition(enemy, "Prone"))
    # Move enemy into zone center
    Entity.update_entity_position(enemy, (8, 8))

    if had_critical_d20():
        print(f"  Attempt {attempt + 1}: nat 1/20, retrying...")
        continue

    test("Enemy prone after entering zone (failed DEX save)", has_condition(enemy, "Prone"))
    break
else:
    print("  SKIP: Could not avoid nat 1/20 in 10 attempts")

# Test turn start: prone + concentration disruption
for attempt in range(10):
    reset_combat_state()
    grid = setup_arena()

    # Keep caster close enough to see zone center
    caster = create_caster(name="Storm Caster", position=(5, 5), level=5)
    # Enemy is a caster concentrating on something, positioned where zone will be
    enemy_caster = create_caster(name="Concentrating Enemy", position=(8, 8), level=5)
    caster.faction = "team_blue"
    enemy_caster.faction = "team_red"
    setup_standard_actions(caster)
    setup_standard_actions(enemy_caster)

    # Force all saves to fail
    force_fail_save(enemy_caster, "dexterity")
    force_fail_save(enemy_caster, "constitution")

    Entity.update_all_entities_senses()

    # Enemy caster concentrates on Enhance Ability (simple concentration spell)
    conc_spell = EnhanceAbility(
        source_entity_uuid=enemy_caster.uuid,
        target_entity_uuid=enemy_caster.uuid,
        enhance_ability_type="wisdom",
        cast_at_level=2,
        template=False,
        costs=[]
    )
    conc_spell.apply()
    test("Enemy concentrating before sleet storm", has_condition(enemy_caster, "Concentrating"))

    # Cast sleet storm centered on enemy (within caster's 50ft vision)
    spell = SleetStorm(
        source_entity_uuid=caster.uuid,
        end_position=(8, 8),
        cast_at_level=3,
        template=False,
        costs=[]
    )
    result_ss = spell.apply()
    test("Sleet Storm cast for concentration test", result_ss is not None and not result_ss.canceled)

    # Remove any prone from initial cast entry
    if has_condition(enemy_caster, "Prone"):
        enemy_caster.remove_condition("Prone")
    # Concentration may have already been disrupted by initial zone creation entry
    # If so, re-apply it for the turn start test
    if not has_condition(enemy_caster, "Concentrating"):
        conc_spell2 = EnhanceAbility(
            source_entity_uuid=enemy_caster.uuid,
            target_entity_uuid=enemy_caster.uuid,
            enhance_ability_type="wisdom",
            cast_at_level=2,
            template=False,
            costs=[]
        )
        conc_spell2.apply()

    # Fire turn start for enemy
    enemy_caster.on_turn_start()

    if had_critical_d20():
        print(f"  Attempt {attempt + 1}: nat 1/20, retrying...")
        continue

    # Turn start should cause: DEX save → Prone, CON save → lose concentration
    test("Enemy concentration disrupted by sleet storm",
         not has_condition(enemy_caster, "Concentrating"))
    break
else:
    print("  SKIP: Could not avoid nat 1/20 in 10 attempts")

# Cleanup test
reset_combat_state()
grid = setup_arena()
caster = create_caster(name="Storm Caster", position=(5, 5), level=5)
setup_standard_actions(caster)
Entity.update_all_entities_senses()

spell = SleetStorm(
    source_entity_uuid=caster.uuid,
    end_position=(8, 8),
    cast_at_level=3,
    template=False,
    costs=[]
)
spell.apply()
test("Sleet Storm zone exists", has_condition(caster, "Sleet Storm Zone"))
caster.remove_condition("Concentrating")
test("Zone removed on concentration break", not has_condition(caster, "Sleet Storm Zone"))


# =============================================================================
# TEST 6: Chain Lightning — targeting, chaining, damage, ally safety
# =============================================================================
print("\n=== TEST 6: Chain Lightning ===")

# Test basic chaining to nearby enemies
reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Lightning Mage", position=(5, 5), level=11)
target1 = create_skeleton(name="Primary", position=(10, 5))
target2 = create_skeleton(name="Secondary 1", position=(12, 5))  # 10ft from primary
target3 = create_skeleton(name="Secondary 2", position=(14, 5))  # 20ft from primary
ally = create_skeleton(name="Ally", position=(11, 5))             # 5ft from primary

caster.faction = "team_blue"
ally.faction = "team_blue"
target1.faction = "team_red"
target2.faction = "team_red"
target3.faction = "team_red"

setup_standard_actions(caster)
Entity.update_all_entities_senses()

set_hp(target1, 200)
set_hp(target2, 200)
set_hp(target3, 200)
set_hp(ally, 200)

hp_before = {e.name: get_hp(e) for e in [target1, target2, target3, ally]}

spell = ChainLightning(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target1.uuid,
    cast_at_level=6,
    template=False,
    costs=[]
)
result = spell.apply()
test("Chain Lightning succeeds", result is not None and not result.canceled)

test("Primary took damage", get_hp(target1) < hp_before["Primary"])
test("Secondary 1 took damage", get_hp(target2) < hp_before["Secondary 1"])
test("Secondary 2 took damage", get_hp(target3) < hp_before["Secondary 2"])
test("Ally NOT damaged", get_hp(ally) == hp_before["Ally"])

# Test chaining with far targets — out of 30ft range
reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Lightning Mage", position=(0, 0), level=11)
target_close = create_skeleton(name="Close", position=(8, 0))       # 40ft from caster
target_far = create_skeleton(name="Far Away", position=(16, 0))     # 40ft from Close (>30ft)

caster.faction = "team_blue"
target_close.faction = "team_red"
target_far.faction = "team_red"
setup_standard_actions(caster)
Entity.update_all_entities_senses()

set_hp(target_close, 200)
set_hp(target_far, 200)
far_hp_before = get_hp(target_far)

spell = ChainLightning(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target_close.uuid,
    cast_at_level=6,
    template=False,
    costs=[]
)
spell.apply()

test("Close target took damage", get_hp(target_close) < 200)
test("Far target NOT hit (>30ft from chain)", get_hp(target_far) == far_hp_before)

# Test 3 max secondaries at L6 (no upcast bonus)
reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Lightning Mage", position=(0, 0), level=11)
targets = []
for i in range(5):
    t = create_skeleton(name=f"T{i}", position=(6+i*2, 0))  # All within 30ft of each other
    t.faction = "team_red"
    set_hp(t, 200)
    targets.append(t)
caster.faction = "team_blue"
setup_standard_actions(caster)
Entity.update_all_entities_senses()

spell = ChainLightning(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=targets[0].uuid,
    cast_at_level=6,
    template=False,
    costs=[]
)
spell.apply()

hit_count = sum(1 for t in targets if get_hp(t) < 200)
test("Primary + up to 3 secondaries = max 4 hit", hit_count <= 4)
test("At least primary hit", hit_count >= 1)

# Test upcast at L7: should get 4 secondaries (3 + 1)
reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Lightning Mage", position=(0, 0), level=13)
targets7 = []
for i in range(6):
    t = create_skeleton(name=f"T{i}", position=(6+i*2, 0))
    t.faction = "team_red"
    set_hp(t, 200)
    targets7.append(t)
caster.faction = "team_blue"
setup_standard_actions(caster)
Entity.update_all_entities_senses()

spell = ChainLightning(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=targets7[0].uuid,
    cast_at_level=7,  # +1 secondary
    template=False,
    costs=[]
)
spell.apply()

hit_count7 = sum(1 for t in targets7 if get_hp(t) < 200)
test(f"L7 upcast: up to 5 hit (got {hit_count7})", hit_count7 <= 5)


# =============================================================================
# TEST 7: Eyebite — Sickened effect with WIS save and repeat CON save
# =============================================================================
print("\n=== TEST 7: Eyebite ===")

# Test Sickened effect
for attempt in range(10):
    reset_combat_state()
    grid = setup_arena()

    caster = create_caster(name="Eye Mage", position=(5, 5), level=11)
    target = create_skeleton(name="Eye Victim", position=(8, 5))
    caster.faction = "team_blue"
    target.faction = "team_red"
    setup_standard_actions(caster)
    setup_standard_actions(target)

    # Force target to fail WIS save
    force_fail_save(target, "wisdom")
    Entity.update_all_entities_senses()

    spell = Eyebite(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        effect_choice="sickened",
        cast_at_level=6,
        template=False,
        costs=[]
    )
    result = spell.apply()

    if had_critical_d20():
        print(f"  Attempt {attempt + 1}: nat 1/20, retrying...")
        continue

    test("Eyebite cast succeeds", result is not None and not result.canceled)
    test("Concentrating", has_condition(caster, "Concentrating"))
    test("Target is Sickened", has_condition(target, "Sickened"))

    # Sickened: disadvantage on attacks
    test("Attack disadvantage",
         target.equipment.attack_bonus.self_static.advantage_sum < 0)

    # Sickened: disadvantage on ability checks (check STR as sample)
    str_ability = target.ability_scores.get_ability("strength")
    test("STR check disadvantage",
         str_ability.ability_score.advantage == AdvantageStatus.DISADVANTAGE)

    # Granted action
    has_strike = any(a.name == "Eyebite Strike" for a in caster.registered_actions)
    test("Eyebite Strike action registered", has_strike)
    break
else:
    print("  SKIP: Could not avoid nat 1/20 in 10 attempts")

# Test Asleep effect: Unconscious + wake on damage
for attempt in range(10):
    reset_combat_state()
    grid = setup_arena()

    caster = create_caster(name="Eye Mage", position=(5, 5), level=11)
    target = create_skeleton(name="Sleeper", position=(8, 5))
    caster.faction = "team_blue"
    target.faction = "team_red"
    setup_standard_actions(caster)
    setup_standard_actions(target)
    force_fail_save(target, "wisdom")
    Entity.update_all_entities_senses()
    set_hp(target, 200)

    spell = Eyebite(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        effect_choice="asleep",
        cast_at_level=6,
        template=False,
        costs=[]
    )
    spell.apply()

    if had_critical_d20():
        print(f"  Attempt {attempt + 1}: nat 1/20, retrying...")
        continue

    test("Target is Unconscious (Asleep)", has_condition(target, "Unconscious"))
    test("Eyebite Asleep condition", has_condition(target, "Eyebite Asleep"))

    # Wake on damage
    deal_damage_to(target, 5, DamageType.BLUDGEONING, caster.uuid)
    test("Woke up after damage (no Unconscious)", not has_condition(target, "Unconscious"))
    test("Eyebite Asleep removed", not has_condition(target, "Eyebite Asleep"))
    break
else:
    print("  SKIP: Could not avoid nat 1/20 in 10 attempts")

# Test Panicked effect: Frightened
for attempt in range(10):
    reset_combat_state()
    grid = setup_arena()

    caster = create_caster(name="Eye Mage", position=(5, 5), level=11)
    target = create_skeleton(name="Panicker", position=(8, 5))
    caster.faction = "team_blue"
    target.faction = "team_red"
    setup_standard_actions(caster)
    setup_standard_actions(target)
    force_fail_save(target, "wisdom")
    Entity.update_all_entities_senses()

    spell = Eyebite(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        effect_choice="panicked",
        cast_at_level=6,
        template=False,
        costs=[]
    )
    spell.apply()

    if had_critical_d20():
        print(f"  Attempt {attempt + 1}: nat 1/20, retrying...")
        continue

    test("Target is Frightened (Panicked)", has_condition(target, "Frightened"))
    test("Eyebite Panicked condition", has_condition(target, "Eyebite Panicked"))
    break
else:
    print("  SKIP: Could not avoid nat 1/20 in 10 attempts")

# Test concentration break removes everything
reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Eye Mage", position=(5, 5), level=11)
target = create_skeleton(name="Victim", position=(8, 5))
caster.faction = "team_blue"
target.faction = "team_red"
setup_standard_actions(caster)
setup_standard_actions(target)
force_fail_save(target, "wisdom")
Entity.update_all_entities_senses()

spell = Eyebite(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    effect_choice="sickened",
    cast_at_level=6,
    template=False,
    costs=[]
)
spell.apply()

caster.remove_condition("Concentrating")
test("Sickened removed on concentration break", not has_condition(target, "Sickened"))
test("Eyebite Strike removed",
     not any(a.name == "Eyebite Strike" for a in caster.registered_actions))


# =============================================================================
# TEST 8: Prismatic Spray — damage, conditions, cone
# =============================================================================
print("\n=== TEST 8: Prismatic Spray ===")

# Force specific colors by patching random to test each branch
reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Prism Mage", position=(5, 5), level=13)
caster.faction = "team_blue"
setup_standard_actions(caster)
Entity.update_all_entities_senses()

# Create targets in the cone direction (east)
targets_p = []
for i in range(3):
    t = create_skeleton(name=f"Prism T{i}", position=(7+i, 5))
    t.faction = "team_red"
    set_hp(t, 200)
    targets_p.append(t)

Entity.update_all_entities_senses()

# Test damage color (force color 1 = Red/Fire)
original_randint = random.randint
color_sequence = iter([1, 1, 1])  # All get red (fire damage)

def mock_randint_damage(a, b):
    if a == 1 and b == 8:
        return next(color_sequence, 1)
    return original_randint(a, b)

# Force targets to fail saves
for t in targets_p:
    force_fail_save(t, "dexterity")

random.randint = mock_randint_damage  # type: ignore
spell = PrismaticSpray(
    source_entity_uuid=caster.uuid,
    end_position=(10, 5),
    cast_at_level=7,
    template=False,
    costs=[]
)
result = spell.apply()
random.randint = original_randint  # type: ignore

test("Prismatic Spray succeeds", result is not None and not result.canceled)
for t in targets_p:
    test(f"{t.name} took fire damage (color 1)", get_hp(t) < 200)

# Test condition color (Indigo = 6 → Restrained)
reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Prism Mage", position=(5, 5), level=13)
target_indigo = create_skeleton(name="Indigo Target", position=(7, 5))
caster.faction = "team_blue"
target_indigo.faction = "team_red"
setup_standard_actions(caster)
set_hp(target_indigo, 200)
force_fail_save(target_indigo, "constitution")  # Indigo uses CON save
Entity.update_all_entities_senses()

color_sequence_6 = iter([6])

def mock_randint_indigo(a, b):
    if a == 1 and b == 8:
        return next(color_sequence_6, 6)
    return original_randint(a, b)

random.randint = mock_randint_indigo  # type: ignore
spell = PrismaticSpray(
    source_entity_uuid=caster.uuid,
    end_position=(10, 5),
    cast_at_level=7,
    template=False,
    costs=[]
)
spell.apply()
random.randint = original_randint  # type: ignore

test("Indigo: Prismatic Restrained applied", has_condition(target_indigo, "Prismatic Restrained"))
test("Indigo: Restrained sub-condition", has_condition(target_indigo, "Restrained"))

# Test Violet = 7 → Blinded
reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Prism Mage", position=(5, 5), level=13)
target_violet = create_skeleton(name="Violet Target", position=(7, 5))
caster.faction = "team_blue"
target_violet.faction = "team_red"
setup_standard_actions(caster)
set_hp(target_violet, 200)
force_fail_save(target_violet, "wisdom")  # Violet uses WIS save
Entity.update_all_entities_senses()

color_sequence_7 = iter([7])

def mock_randint_violet(a, b):
    if a == 1 and b == 8:
        return next(color_sequence_7, 7)
    return original_randint(a, b)

random.randint = mock_randint_violet  # type: ignore
spell = PrismaticSpray(
    source_entity_uuid=caster.uuid,
    end_position=(10, 5),
    cast_at_level=7,
    template=False,
    costs=[]
)
spell.apply()
random.randint = original_randint  # type: ignore

test("Violet: Blinded applied", has_condition(target_violet, "Blinded"))


# =============================================================================
# TEST 9: Dimension Door — teleport, validation
# =============================================================================
print("\n=== TEST 9: Dimension Door ===")

reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Door Mage", position=(5, 5), level=7)
setup_standard_actions(caster)
Entity.update_all_entities_senses()

test("Caster starts at (5,5)", get_position(caster) == (5, 5))

spell = DimensionDoor(
    source_entity_uuid=caster.uuid,
    end_position=(12, 12),
    cast_at_level=4,
    template=False,
    costs=[]
)
result = spell.apply()
test("Dimension Door succeeds", result is not None and not result.canceled)
test("Caster teleported to (12,12)", get_position(caster) == (12, 12))

# Test: occupied position → fail
reset_combat_state()
grid = setup_arena()

caster = create_caster(name="Door Mage", position=(5, 5), level=7)
blocker = create_skeleton(name="Blocker", position=(10, 10))
setup_standard_actions(caster)
Entity.update_all_entities_senses()

spell_blocked = DimensionDoor(
    source_entity_uuid=caster.uuid,
    end_position=(10, 10),
    cast_at_level=4,
    template=False,
    costs=[]
)
result_blocked = spell_blocked.apply()
test("Can't teleport to occupied position", result_blocked is None or result_blocked.canceled)
test("Caster didn't move", get_position(caster) == (5, 5))

# Test: non-visible position → fail
spell_novis = DimensionDoor(
    source_entity_uuid=caster.uuid,
    end_position=(50, 50),
    cast_at_level=4,
    template=False,
    costs=[]
)
result_novis = spell_novis.apply()
test("Can't teleport to non-visible position", result_novis is None or result_novis.canceled)

# Test: no tile (off grid) → fail
spell_offgrid = DimensionDoor(
    source_entity_uuid=caster.uuid,
    end_position=(100, 100),
    cast_at_level=4,
    template=False,
    costs=[]
)
result_offgrid = spell_offgrid.apply()
test("Can't teleport off grid", result_offgrid is None or result_offgrid.canceled)


# =============================================================================
# TEST 10: Size-based damage dice (base rule)
# =============================================================================
print("\n=== TEST 10: Size-based damage dice ===")

reset_combat_state()
grid = setup_arena()

giant = create_caster(name="Giant", position=(5, 5), level=5)
setup_standard_actions(giant)
longsword = create_longsword(giant.uuid)
giant.equipment.equip(longsword, WeaponSlot.MELEE_MAIN)
Entity.update_all_entities_senses()

# Medium: no extra dice
test("Medium: 0 extra d4", giant.get_size_damage_dice() == 0)
damages_med = giant.get_damages(WeaponSlot.MELEE_MAIN)
no_size_damage = not any(d.damage_dice == 4 for d in damages_med)
test("Medium: no d4 in damages", no_size_damage)

# Large: 1 extra d4
giant.size = Size.LARGE
test("Large: 1 extra d4", giant.get_size_damage_dice() == 1)
damages_lg = giant.get_damages(WeaponSlot.MELEE_MAIN)
test("Large: 1d4 in damages", any(d.damage_dice == 4 and d.dice_numbers == 1 for d in damages_lg))

# Huge: 2 extra d4
giant.size = Size.HUGE
test("Huge: 2 extra d4", giant.get_size_damage_dice() == 2)
damages_hg = giant.get_damages(WeaponSlot.MELEE_MAIN)
test("Huge: 2d4 in damages", any(d.damage_dice == 4 and d.dice_numbers == 2 for d in damages_hg))

# Gargantuan: 3 extra d4
giant.size = Size.GARGANTUAN
test("Gargantuan: 3 extra d4", giant.get_size_damage_dice() == 3)
damages_gg = giant.get_damages(WeaponSlot.MELEE_MAIN)
test("Gargantuan: 3d4 in damages", any(d.damage_dice == 4 and d.dice_numbers == 3 for d in damages_gg))

# Small/Tiny: 0 extra dice
giant.size = Size.SMALL
test("Small: 0 extra d4", giant.get_size_damage_dice() == 0)
giant.size = Size.TINY
test("Tiny: 0 extra d4", giant.get_size_damage_dice() == 0)


# =============================================================================
# SUMMARY
# =============================================================================
print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
print(f"{'='*60}")

if failed > 0:
    exit(1)
