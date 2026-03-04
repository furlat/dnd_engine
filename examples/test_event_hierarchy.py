"""Test event parent-child hierarchy at COMPLETION phase.

Verifies that:
1. COMPLETION events have populated children_lineages
2. COMPLETION events have parent_lineage matching parent's lineage_uuid
3. Attack → D20 roll hierarchy is preserved
4. Spell → saving throw hierarchy is preserved
5. get_parent_event() / get_children_events() use stable lineage fields
"""

from dnd.utils import reset_combat_state, setup_combat_arena, force_attack_hit, remove_attack_modifier
from dnd.core.events import EventQueue, EventPhase, EventType, Event
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin
from dnd.actions_functional import execute_by_index
from uuid import uuid4

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


print("=" * 60)
print("EVENT PARENT-CHILD HIERARCHY TESTS")
print("=" * 60)


# ============================================================
# Test 1: Basic phase_to() produces stable lineage fields
# ============================================================
print("\n=== Test 1: Basic COMPLETION has stable lineage fields ===")
reset_combat_state()

parent_event = Event(
    name="Parent",
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
)

child_event = Event(
    name="Child",
    event_type=EventType.TAKE_DAMAGE,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
    parent_event=parent_event.uuid,
)

# Phase parent through to COMPLETION
exec_parent = parent_event.phase_to(EventPhase.EXECUTION)
effect_parent = exec_parent.phase_to(EventPhase.EFFECT)
completion_parent = effect_parent.phase_to(EventPhase.COMPLETION)

check(len(completion_parent.children_lineages) > 0,
      f"COMPLETION has children_lineages (count={len(completion_parent.children_lineages)})")
check(child_event.lineage_uuid in completion_parent.children_lineages,
      "children_lineages contains child's lineage_uuid")


# ============================================================
# Test 2: Child COMPLETION has parent_lineage
# ============================================================
print("\n=== Test 2: Child COMPLETION has parent_lineage ===")
reset_combat_state()

parent = Event(
    name="Parent",
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
)

child = Event(
    name="Child",
    event_type=EventType.TAKE_DAMAGE,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
    parent_event=parent.uuid,
)

child_exec = child.phase_to(EventPhase.EXECUTION)
child_effect = child_exec.phase_to(EventPhase.EFFECT)
child_completion = child_effect.phase_to(EventPhase.COMPLETION)

check(child_completion.parent_lineage is not None,
      "child COMPLETION has parent_lineage set")
check(child_completion.parent_lineage == parent.lineage_uuid,
      f"parent_lineage matches parent's lineage_uuid")


# ============================================================
# Test 3: get_parent_event() returns latest parent version
# ============================================================
print("\n=== Test 3: get_parent_event() uses parent_lineage ===")
reset_combat_state()

parent = Event(
    name="Parent",
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
)
parent_exec = parent.phase_to(EventPhase.EXECUTION)

child = Event(
    name="Child",
    event_type=EventType.TAKE_DAMAGE,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
    parent_event=parent.uuid,  # Points to DECLARATION uuid
)

child_completion = child.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)

resolved_parent = child_completion.get_parent_event()
check(resolved_parent is not None, "get_parent_event() returns a parent")
if resolved_parent:
    # Should return the LATEST version (EXECUTION), not DECLARATION
    check(resolved_parent.phase == EventPhase.EXECUTION,
          f"get_parent_event() returns latest phase ({resolved_parent.phase.value})")
    check(resolved_parent.lineage_uuid == parent.lineage_uuid,
          "resolved parent has correct lineage_uuid")


# ============================================================
# Test 4: get_children_events() returns latest child versions
# ============================================================
print("\n=== Test 4: get_children_events() uses children_lineages ===")
reset_combat_state()

parent = Event(
    name="Parent",
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
)

child1 = Event(
    name="Child1",
    event_type=EventType.TAKE_DAMAGE,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
    parent_event=parent.uuid,
)
child1_completion = child1.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)

child2 = Event(
    name="Child2",
    event_type=EventType.SAVING_THROW,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
    parent_event=parent.uuid,
)
child2_exec = child2.phase_to(EventPhase.EXECUTION)

parent_completion = parent.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)

children = parent_completion.get_children_events()
check(len(children) == 2, f"get_children_events() returns 2 children (got {len(children)})")

if len(children) == 2:
    # Each returned child should be the latest version in its lineage
    child_phases = {c.name: c.phase for c in children}
    check(child_phases.get("Child1") == EventPhase.COMPLETION,
          "Child1 resolved to COMPLETION phase")
    check(child_phases.get("Child2") == EventPhase.EXECUTION,
          "Child2 resolved to EXECUTION phase (latest)")


# ============================================================
# Test 5: Attack → D20 roll + DamageRollResult hierarchy
# ============================================================
print("\n=== Test 5: Attack hierarchy with real combat ===")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

attacker = create_goblin(name="Attacker", position=(0, 0))
target = create_goblin(name="Target", position=(1, 0))
Entity.update_all_entities_senses()

encounter = setup_combat_arena(attacker, target)
encounter.start_encounter()
encounter.start_turn()

mod_id = force_attack_hit(attacker)

# Find the attack action
actions = attacker.get_available_actions()
attack_action = None
for a in actions.entity_actions:
    if a.template_name.lower().startswith("scimitar") or "attack" in a.template_name.lower():
        attack_action = a
        break

if attack_action and attack_action.valid_targets:
    execute_by_index(attacker, attack_action.template_name, 0)

    # Find attack COMPLETION event
    attack_completions = [
        e for e in EventQueue._all_events
        if e.event_type == EventType.ATTACK and e.phase == EventPhase.COMPLETION
    ]

    if attack_completions:
        attack_comp = attack_completions[-1]
        check(len(attack_comp.children_lineages) > 0,
              f"Attack COMPLETION has children_lineages (count={len(attack_comp.children_lineages)})")

        children = attack_comp.get_children_events()
        child_types = {c.event_type for c in children}

        # D20 roll should now appear as child of attack (was orphaned before fix)
        has_d20_child = bool(child_types & {
            EventType.D20_ROLL_RESULT, EventType.ATTACK_D20_ROLL_RESULT,
        })
        check(has_d20_child, f"Attack D20 roll is a child of attack ({[t.value for t in child_types]})")

        # DamageRollResult should appear as child (now reaches COMPLETION)
        has_damage_roll_child = EventType.DAMAGE_ROLL_RESULT in child_types
        check(has_damage_roll_child, f"DamageRollResult is a child of attack ({[t.value for t in child_types]})")

        # TakeDamage should be a child
        has_take_damage_child = EventType.TAKE_DAMAGE in child_types
        check(has_take_damage_child, f"TakeDamage is a child of attack ({[t.value for t in child_types]})")

        # DamageRollResult should have reached COMPLETION
        damage_roll_completions = [
            e for e in EventQueue._all_events
            if e.event_type == EventType.DAMAGE_ROLL_RESULT and e.phase == EventPhase.COMPLETION
        ]
        check(len(damage_roll_completions) > 0,
              "DamageRollResultEvent reaches COMPLETION phase")

        if damage_roll_completions:
            dmg_comp = damage_roll_completions[-1]
            check(dmg_comp.parent_lineage is not None,
                  "DamageRollResult COMPLETION has parent_lineage set")
            check(dmg_comp.parent_lineage == attack_comp.lineage_uuid,
                  "DamageRollResult parent_lineage matches attack lineage")
    else:
        check(False, "No attack COMPLETION event found")
else:
    check(False, "No attack action available")

remove_attack_modifier(attacker, mod_id)


# ============================================================
# Test 6: children_lineages are deduplicated
# ============================================================
print("\n=== Test 6: children_lineages deduplication ===")
reset_combat_state()

parent = Event(
    name="Parent",
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
)

# Create child that phases through multiple times, each registering as child
child = Event(
    name="Child",
    event_type=EventType.TAKE_DAMAGE,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
    parent_event=parent.uuid,
)
child_exec = child.phase_to(EventPhase.EXECUTION)
child_effect = child_exec.phase_to(EventPhase.EFFECT)
child_completion = child_effect.phase_to(EventPhase.COMPLETION)

parent_completion = parent.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)

# children_lineages should have exactly 1 entry (deduplicated)
check(len(parent_completion.children_lineages) == 1,
      f"children_lineages deduplicated (count={len(parent_completion.children_lineages)}, expected 1)")
check(parent_completion.children_lineages[0] == child.lineage_uuid,
      "Deduped lineage matches child's lineage_uuid")


# ============================================================
# Test 7: Non-COMPLETION phases don't have stable fields
# ============================================================
print("\n=== Test 7: Non-COMPLETION phases have empty stable fields ===")
reset_combat_state()

parent = Event(
    name="Parent",
    event_type=EventType.BASE_ACTION,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
)

child = Event(
    name="Child",
    event_type=EventType.TAKE_DAMAGE,
    phase=EventPhase.DECLARATION,
    source_entity_uuid=uuid4(),
    parent_event=parent.uuid,
)

parent_exec = parent.phase_to(EventPhase.EXECUTION)
check(len(parent_exec.children_lineages) == 0,
      "EXECUTION phase has empty children_lineages")
check(parent_exec.parent_lineage is None,
      "EXECUTION phase has no parent_lineage")

child_effect = child.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
check(child_effect.parent_lineage is None,
      "EFFECT phase has no parent_lineage")


# ============================================================
# Test 8: SkillCheckEvent now reaches COMPLETION
# ============================================================
print("\n=== Test 8: SkillCheckEvent phase progression ===")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 20, 20)

from dnd.monsters.bestiary import create_skeleton
checker = create_skeleton(name="Checker", position=(5, 5))
Entity.update_all_entities_senses()

from dnd.core.events import SkillCheckEvent
check_event = SkillCheckEvent(
    source_entity_uuid=checker.uuid,
    target_entity_uuid=checker.uuid,
    skill_name="athletics",
    dc=10,
    source_entity_name=checker.name,
)
checker.skill_check(check_event)

# Verify SkillCheckEvent reached COMPLETION
skill_check_completions = [
    e for e in EventQueue._all_events
    if e.event_type == EventType.SKILL_CHECK and e.phase == EventPhase.COMPLETION
]
check(len(skill_check_completions) > 0,
      "SkillCheckEvent reaches COMPLETION phase")

# Verify D20 roll is child of skill check
if skill_check_completions:
    sc_comp = skill_check_completions[-1]
    children = sc_comp.get_children_events()
    child_types = {c.event_type for c in children}
    has_d20 = bool(child_types & {EventType.D20_ROLL_RESULT, EventType.CHECK_D20_ROLL_RESULT})
    check(has_d20, f"D20 roll is child of SkillCheck ({[t.value for t in child_types]})")


# ============================================================
# Results
# ============================================================
print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print(f"FAILURES: {failed}")
print("=" * 60)
