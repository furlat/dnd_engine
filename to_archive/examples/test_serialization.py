"""
Test serializable contextual modifiers with indexed cache.

Tests that entity.model_dump(mode='json') works without crashes,
that contextual modifier results are cached and indexed correctly,
and that breakdowns include contextual data from cached results.
"""

import json
import sys
from uuid import uuid4, UUID
from typing import Optional, Dict, Any

from dnd.utils import reset_combat_state, setup_combat_arena, force_attack_hit, remove_attack_modifier
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary import create_goblin
from dnd.entity import Entity
from dnd.actions_functional import register_spells_by_name
from dnd.conditions import Frightened, Prone, Paralyzed
from dnd.core.modifiers import (
    AdvantageModifier, AdvantageStatus, NumericalModifier,
    ContextualAdvantageModifier, ContextualNumericalModifier,
)
from dnd.core.events import WeaponSlot

passed = 0
failed = 0

def test(name, condition, details=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} {details}")


# =========================================================================
# GROUP 1: Crash-Free Serialization
# =========================================================================
print("\n=== GROUP 1: Crash-Free Serialization ===\n")

# Test 1.1 — Vanilla entity at rest
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
goblin = create_goblin(name="Goblin", position=(5, 5))
Entity.update_all_entities_senses()

dump = goblin.model_dump(mode='json')
json_str = json.dumps(dump)
test("1.1 Vanilla entity serializes to JSON", len(json_str) > 0)

# Test 1.2 — Entity with conditions
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
hero = create_goblin(name="Hero", position=(3, 3))
goblin = create_goblin(name="Goblin", position=(5, 5))
Entity.update_all_entities_senses()

goblin.add_condition(Frightened(source_entity_uuid=hero.uuid, target_entity_uuid=goblin.uuid))
goblin.add_condition(Prone(source_entity_uuid=hero.uuid, target_entity_uuid=goblin.uuid))

dump = goblin.model_dump(mode='json')
json_str = json.dumps(dump)
test("1.2 Entity with conditions serializes", len(json_str) > 0)
test("1.2 Frightened condition present", "Frightened" in dump.get("active_conditions", {}))
test("1.2 Prone condition present", "Prone" in dump.get("active_conditions", {}))

# Test 1.3 — Entity with spells and concentration
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
mage = create_goblin(name="Mage", position=(0, 0))
target = create_goblin(name="Target", position=(3, 3))
Entity.update_all_entities_senses()

register_spells_by_name(mage, ["Hold Person", "Fire Bolt"], caster_level=5)

dump = mage.model_dump(mode='json')
json_str = json.dumps(dump)
test("1.3 Spellcaster entity serializes", len(json_str) > 0)

# Test 1.4 — Handler serialization (event_processor excluded)
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
goblin = create_goblin(name="Goblin", position=(5, 5))
Entity.update_all_entities_senses()

dump = goblin.model_dump(mode='json')
handlers = dump.get('event_handlers', {})
if handlers:
    handler_values = list(handlers.values())
    first_handler = handler_values[0]
    test("1.4 Handler has 'enabled' field", 'enabled' in first_handler)
    test("1.4 Handler excludes 'event_processor'", 'event_processor' not in first_handler)
else:
    test("1.4 Handler serialization", False, "(no handlers found)")

# Test 1.5 — Action serialization
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
goblin = create_goblin(name="Goblin", position=(5, 5))
Entity.update_all_entities_senses()

for action in goblin.registered_actions:
    d = action.model_dump(mode='json')
    json_str = json.dumps(d)
    test(f"1.5 Action '{action.name}' serializes", len(json_str) > 0)
    # Check StructuredAction fields
    if hasattr(action, 'prerequisites'):
        test(f"1.5 '{action.name}' has prerequisite_names", 'prerequisite_names' in d)
        test(f"1.5 '{action.name}' excludes prerequisites callable", 'prerequisites' not in d)
    break  # Just test first action to keep output manageable

# Test 1.6 — Equipment and inventory
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
goblin = create_goblin(name="Goblin", position=(5, 5))
Entity.update_all_entities_senses()

equip_dump = goblin.equipment.model_dump(mode='json')
json_str = json.dumps(equip_dump)
test("1.6 Equipment serializes", len(json_str) > 0)

inv_dump = goblin.inventory.model_dump(mode='json')
json_str = json.dumps(inv_dump)
test("1.6 Inventory serializes", len(json_str) > 0)


# =========================================================================
# GROUP 2: Contextual Cache Correctness
# =========================================================================
print("\n=== GROUP 2: Contextual Cache Correctness ===\n")

# Test 2.1 — Cache populated after evaluation
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
attacker = create_goblin(name="Attacker", position=(3, 3))
target = create_goblin(name="Target", position=(4, 3))
Entity.update_all_entities_senses()

# Create a contextual modifier
def position_advantage(source_uuid: UUID, target_uuid: Optional[UUID] = None, context: Optional[Dict[str, Any]] = None):
    entity = Entity.get(source_uuid)
    if entity and entity.position[0] < 5:
        return AdvantageModifier(name="Near", value=AdvantageStatus.ADVANTAGE,
                                  source_entity_uuid=source_uuid, target_entity_uuid=target_uuid)
    return AdvantageModifier(name="Far", value=AdvantageStatus.DISADVANTAGE,
                              source_entity_uuid=source_uuid, target_entity_uuid=target_uuid)

ctx_mod = ContextualAdvantageModifier(
    name="PositionDependent",
    callable=position_advantage,
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=attacker.uuid,
)
attacker.equipment.attack_bonus.self_contextual.add_advantage_modifier(ctx_mod)

test("2.1 cached_results empty before evaluation", len(ctx_mod.cached_results) == 0)

# Now evaluate it manually
result = ctx_mod.evaluate(attacker.uuid, target.uuid, None, event_lineage_uuid=uuid4())
test("2.1 cached_results has 1 entry after evaluate", len(ctx_mod.cached_results) == 1)
test("2.1 cached result is AdvantageModifier", isinstance(result, AdvantageModifier))
test("2.1 cached result has ADVANTAGE (pos < 5)", result is not None and result.value == AdvantageStatus.ADVANTAGE)

# Test 2.2 — Cache indexed by different targets
lineage1 = uuid4()
lineage2 = uuid4()
target2 = create_goblin(name="Target2", position=(6, 3))
Entity.update_all_entities_senses()

ctx_mod2 = ContextualAdvantageModifier(
    name="PosDep2",
    callable=position_advantage,
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=attacker.uuid,
)
ctx_mod2.evaluate(attacker.uuid, target.uuid, None, event_lineage_uuid=lineage1)
ctx_mod2.evaluate(attacker.uuid, target2.uuid, None, event_lineage_uuid=lineage2)
test("2.2 Two entries for different targets+lineages", len(ctx_mod2.cached_results) == 2)

# Test 2.3 — Same target, different lineages → separate cache entries
ctx_mod3 = ContextualAdvantageModifier(
    name="PosDep3",
    callable=position_advantage,
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=attacker.uuid,
)
l1 = uuid4()
l2 = uuid4()
ctx_mod3.evaluate(attacker.uuid, target.uuid, None, event_lineage_uuid=l1)
ctx_mod3.evaluate(attacker.uuid, target.uuid, None, event_lineage_uuid=l2)
test("2.3 Same target, different lineages = 2 entries", len(ctx_mod3.cached_results) == 2)

# Test 2.4 — Cache preserves Pydantic model type in serialization
dump = ctx_mod.model_dump(mode='json')
cached = dump.get('cached_results', {})
test("2.4 cached_results present in dump", len(cached) > 0)
first_entry = list(cached.values())[0]
test("2.4 cached entry has 'value' field", 'value' in first_entry)
test("2.4 cached entry has 'name' field", 'name' in first_entry)


# =========================================================================
# GROUP 3: Game Mechanic Scenarios
# =========================================================================
print("\n=== GROUP 3: Game Mechanic Scenarios ===\n")

# Test 3.1 — Frightened: contextual disadvantage on attacks
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
hero = create_goblin(name="Hero", position=(3, 3))
goblin = create_goblin(name="Goblin", position=(4, 3))
Entity.update_all_entities_senses()

encounter = setup_combat_arena(goblin, hero)
encounter.start_encounter()

# Apply Frightened
goblin.add_condition(Frightened(source_entity_uuid=hero.uuid, target_entity_uuid=goblin.uuid))

# Goblin's turn: attack hero (frightener is visible, so disadvantage should apply)
encounter.start_turn()
force_mod = force_attack_hit(goblin)

# Get attack_bonus with target set
attack_bonus = goblin.attack_bonus(weapon_slot=WeaponSlot.MELEE_MAIN, target_entity_uuid=hero.uuid)
# The contextual modifiers on attack_bonus should give DISADVANTAGE since hero (frightener) is visible
advantage = attack_bonus.advantage
test("3.1 Frightened gives DISADVANTAGE on attack vs frightener", advantage == AdvantageStatus.DISADVANTAGE)

remove_attack_modifier(goblin, force_mod)

# Test 3.2 — Prone: contextual advantage based on distance
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
melee_attacker = create_goblin(name="Melee", position=(3, 3))
ranged_attacker = create_goblin(name="Ranged", position=(3, 10))
target = create_goblin(name="Prone Target", position=(4, 3))
Entity.update_all_entities_senses()

target.add_condition(Prone(source_entity_uuid=melee_attacker.uuid, target_entity_uuid=target.uuid))

# Melee attack (5ft) → ADVANTAGE
melee_ac = target.ac_bonus(melee_attacker.uuid)
test("3.2 Prone target: melee attacker sees ADVANTAGE",
     melee_ac.to_target_contextual.advantage == AdvantageStatus.ADVANTAGE)

# Test 3.3 — Paralyzed: auto-crit within 5ft
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
attacker = create_goblin(name="Attacker", position=(3, 3))
target = create_goblin(name="Paralyzed Target", position=(4, 3))
Entity.update_all_entities_senses()

target.add_condition(Paralyzed(source_entity_uuid=attacker.uuid, target_entity_uuid=target.uuid))

ac = target.ac_bonus(attacker.uuid)
from dnd.core.modifiers import CriticalStatus
test("3.3 Paralyzed grants AUTOCRIT to melee attackers",
     ac.to_target_contextual.critical == CriticalStatus.AUTOCRIT)

# Test 3.4 — Multiple conditions stacking
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
hero = create_goblin(name="Hero", position=(3, 3))
goblin = create_goblin(name="Goblin", position=(4, 3))
target = create_goblin(name="Prone Target", position=(5, 3))
Entity.update_all_entities_senses()

# Goblin is Frightened by hero AND attacking a Prone target
goblin.add_condition(Frightened(source_entity_uuid=hero.uuid, target_entity_uuid=goblin.uuid))
target.add_condition(Prone(source_entity_uuid=goblin.uuid, target_entity_uuid=target.uuid))

# Frightened gives disadvantage when attacking and frightener is visible
# Prone at melee range gives advantage to attacker via to_target
# When goblin attacks prone target, Frightened disadvantage applies (hero/frightener visible)
# AND Prone advantage applies — they cancel out
attack_bonus = goblin.attack_bonus(weapon_slot=WeaponSlot.MELEE_MAIN, target_entity_uuid=target.uuid)
ac = target.ac_bonus(goblin.uuid)
attack_bonus.set_from_target(ac)
# Both modifiers should be present — Frightened DIS + Prone ADV = NONE
advantage = attack_bonus.advantage
test("3.4 Frightened DIS + Prone ADV cancel to NONE",
     advantage == AdvantageStatus.NONE)
attack_bonus.reset_from_target()


# =========================================================================
# GROUP 5: Breakdown Correctness
# =========================================================================
print("\n=== GROUP 5: Breakdown Correctness ===\n")

# Test 5.1 — get_full_breakdown() includes contextual numericals
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
entity = create_goblin(name="TestGoblin", position=(3, 3))
Entity.update_all_entities_senses()

def hp_bonus(source_uuid, target_uuid=None, context=None):
    return NumericalModifier.create(name="HP Bonus", value=2, source_entity_uuid=source_uuid)

ctx_num = ContextualNumericalModifier(
    name="HP Bonus",
    callable=hp_bonus,
    source_entity_uuid=entity.uuid,
    target_entity_uuid=entity.uuid,
)
entity.equipment.attack_bonus.self_contextual.add_value_modifier(ctx_num)

# Evaluate with a lineage
lineage = uuid4()
entity.equipment.attack_bonus.self_contextual.event_lineage_uuid = lineage
ctx_num.evaluate(entity.uuid, None, None, event_lineage_uuid=lineage)

breakdown = entity.equipment.attack_bonus.get_full_breakdown()
contextual_entries = [e for e in breakdown if e.get('contextual')]
test("5.1 get_full_breakdown includes contextual numericals", len(contextual_entries) >= 1)
test("5.1 contextual entry has HP Bonus name", any(e['name'] == 'HP Bonus' for e in contextual_entries))

entity.equipment.attack_bonus.self_contextual.event_lineage_uuid = None

# Test 5.2 — get_full_advantage_breakdown() includes contextual advantages
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
hero = create_goblin(name="Hero", position=(3, 3))
goblin = create_goblin(name="Goblin", position=(4, 3))
Entity.update_all_entities_senses()

goblin.add_condition(Frightened(source_entity_uuid=hero.uuid, target_entity_uuid=goblin.uuid))

# Set up context and evaluate
attack_bonus = goblin.equipment.attack_bonus
lineage = uuid4()
attack_bonus.set_event_lineage(lineage)
attack_bonus.set_target_entity(hero.uuid)

# Force evaluation of contextual modifiers by accessing advantage
_ = attack_bonus.advantage

full_breakdown = attack_bonus.get_full_advantage_breakdown()
attack_bonus.clear_event_lineage()
attack_bonus.clear_target_entity()

test("5.2 get_full_advantage_breakdown has entries", len(full_breakdown) >= 1)

# Test 5.4 — Breakdown for never-evaluated modifier shows inactive
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
entity = create_goblin(name="TestGoblin", position=(3, 3))
Entity.update_all_entities_senses()

def never_called(source_uuid, target_uuid=None, context=None):
    return AdvantageModifier(name="Never", value=AdvantageStatus.ADVANTAGE,
                              source_entity_uuid=source_uuid)

ctx_never = ContextualAdvantageModifier(
    name="NeverEvaluated",
    callable=never_called,
    source_entity_uuid=entity.uuid,
    target_entity_uuid=entity.uuid,
)
entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(ctx_never)

breakdown = entity.equipment.attack_bonus.get_full_advantage_breakdown()
inactive_entries = [e for e in breakdown if not e.get('active', True)]
test("5.4 Never-evaluated modifier shows inactive", len(inactive_entries) >= 1)
test("5.4 Inactive entry has NeverEvaluated name",
     any(e.get('name') == 'NeverEvaluated' for e in inactive_entries))


# =========================================================================
# GROUP 7: Serialization Fidelity
# =========================================================================
print("\n=== GROUP 7: Serialization Fidelity ===\n")

# Test 7.1 — Duration field_serializer
from dnd.core.base_conditions import Duration, DurationType

d_rounds = Duration(duration=3, duration_type=DurationType.ROUNDS, source_entity_uuid=uuid4(), target_entity_uuid=uuid4())
dump_rounds = d_rounds.model_dump(mode='json')
test("7.1 Int duration serializes as int", dump_rounds['duration'] == 3)

d_perm = Duration(duration=None, duration_type=DurationType.PERMANENT, source_entity_uuid=uuid4(), target_entity_uuid=uuid4())
dump_perm = d_perm.model_dump(mode='json')
test("7.1 None duration serializes as null", dump_perm['duration'] is None)

d_cond = Duration(
    duration=lambda s, t, c: False,
    duration_type=DurationType.ON_CONDITION,
    source_entity_uuid=uuid4(),
    target_entity_uuid=uuid4()
)
dump_cond = d_cond.model_dump(mode='json')
test("7.1 Callable duration serializes as 'conditional'", dump_cond['duration'] == "conditional")

# Test 7.2 — BaseBlock excluded fields
reset_combat_state()
get_map().create_rectangle(0, 0, 20, 20)
entity = create_goblin(name="TestGoblin", position=(5, 5))
Entity.update_all_entities_senses()

dump = entity.model_dump(mode='json')
test("7.2 active_conditions_by_uuid excluded", 'active_conditions_by_uuid' not in dump)
test("7.2 contextual_condition_immunities excluded", 'contextual_condition_immunities' not in dump)
test("7.2 event_handlers_by_trigger excluded", 'event_handlers_by_trigger' not in dump)
test("7.2 event_handlers_by_simple_trigger excluded", 'event_handlers_by_simple_trigger' not in dump)
test("7.2 active_conditions_by_source excluded", 'active_conditions_by_source' not in dump)
# contextual_immunity_names computed_field should appear
test("7.2 contextual_immunity_names IS present", 'contextual_immunity_names' in dump)

# Test 7.3 — StructuredAction computed_fields
from dnd.core.base_actions import StructuredAction
# Create a StructuredAction directly to test its serialization
test_structured = StructuredAction(
    name="TestStructured",
    source_entity_uuid=entity.uuid,
)
test_structured.prerequisites["check_range"] = lambda e, u: e
test_structured.consequences["apply_damage"] = lambda e, u: e

d = test_structured.model_dump(mode='json')
test("7.3 prerequisite_names present", 'prerequisite_names' in d)
test("7.3 consequence_names present", 'consequence_names' in d)
test("7.3 prerequisites excluded", 'prerequisites' not in d)
test("7.3 consequences excluded", 'consequences' not in d)
test("7.3 prerequisite_names has correct values", d['prerequisite_names'] == ['check_range'])
test("7.3 consequence_names has correct values", d['consequence_names'] == ['apply_damage'])


# =========================================================================
# Summary
# =========================================================================
print(f"\n{'='*60}")
print(f"SERIALIZATION TESTS: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
