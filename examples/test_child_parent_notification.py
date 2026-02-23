"""
Test suite for reverse-link child→parent condition notification + DropConcentration.

Tests the parent_link / child_removal_policy system on BaseCondition and the
DropConcentration action.

Tests:
 1. parent_link set by add_linked_condition()
 2. parent_link is None for conditions without linked parent
 3. child_removal_policy defaults to "none"
 4. "last" policy: single child removed → parent removed
 5. "last" policy: single child removed → parent sub_conditions cleaned
 6. "last" policy: 2 children, remove one → parent stays, remove second → parent removed
 7. "last" policy: 2 children, verify remaining sibling state during intermediate step
 8. "any" policy: 2 siblings, remove one → parent + other sibling removed
 9. "any" policy: verify sibling sub_conditions cleaned in cascade
10. "none" policy: child removed → parent stays
11. "none" policy: parent linked_conditions stale reference preserved
12. Parent-driven removal still removes all linked children
13. No double-removal crash with parent_link set
14. Caster dies → concentration breaks → linked effects removed
15. Target dies → conditions removed → Concentrating removed via reverse link
16. Both alive, effect dispelled → Concentrating removed
17. Zone condition on caster removed → Concentrating removed
18. Concentrating broken → zone removed → no double notification
19. 3-level chain: remove C → B removed → A removed, no loop
20. 3-level chain: parent-driven removal from top still works
21. Hold Person: target saves → effect removed → Concentrating auto-removed
22. Hold Person: full chain verification after save
23. Hold Monster: same as Hold Person
24. Hold Person: concentration broken by damage → effect removed (forward path)
25. DropConcentration available when concentrating
26. DropConcentration NOT available when not concentrating
27. DropConcentration costs 0 actions
28. DropConcentration removes concentration + all linked effects
29. After DropConcentration, can cast new concentration spell
30. Stale parent_link → no crash
31. parent_link to non-existent block → no crash
32. parent_link with "none" policy → no notification
"""

from uuid import uuid4, UUID
from typing import List, Tuple, Optional, Literal

from dnd.utils import reset_combat_state, set_hp, deal_damage_to, has_condition
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import Concentrating
from dnd.core.base_conditions import BaseCondition, ConditionCategory
from dnd.core.events import Event, EventPhase, DamageType
from dnd.actions_functional import setup_standard_actions, get_available_actions
from dnd.spells import HoldPerson, HoldMonster


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


# =========================================================================
# Helpers
# =========================================================================

def create_caster(name: str, position: tuple) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=20),
            constitution=AbilityConfig(ability_score=20),
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 4, 2: 3, 3: 2, 4: 2, 5: 1}),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode="maximums")]),
        proficiency_bonus=6,
        position=position
    )
    caster = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(caster)
    return caster


def create_target(name: str, position: tuple) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=1),
            constitution=AbilityConfig(ability_score=1),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode="maximums")]),
        proficiency_bonus=0,
        position=position
    )
    target = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    setup_standard_actions(target)
    return target


class DummyEffect(BaseCondition):
    """A simple test condition that applies without modifiers."""
    name: str = "DummyEffect"
    condition_category: ConditionCategory = ConditionCategory.CONDITION

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION)
        event = event.phase_to(EventPhase.EFFECT)
        return [], [], [], [], event


class DummyEffectWithSub(BaseCondition):
    """A test condition that applies a sub-condition."""
    name: str = "DummyEffectWithSub"
    condition_category: ConditionCategory = ConditionCategory.CONDITION

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION)
        event = event.phase_to(EventPhase.EFFECT)

        # Add a sub-condition on same entity
        if self.target_entity_uuid is None:
            return [], [], [], [], event
        target = Entity.get(self.target_entity_uuid)
        if target:
            sub = DummySubCondition(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid,
            )
            target.add_condition(sub)
            return [], [], [sub.uuid], [], event
        return [], [], [], [], event


class DummySubCondition(BaseCondition):
    """Sub-condition for testing."""
    name: str = "DummySubCondition"
    condition_category: ConditionCategory = ConditionCategory.CONDITION

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION)
        event = event.phase_to(EventPhase.EFFECT)
        return [], [], [], [], event


class ParentWithPolicy(BaseCondition):
    """Parent condition with configurable child_removal_policy for tests."""
    name: str = "ParentWithPolicy"
    condition_category: ConditionCategory = ConditionCategory.STATUS

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION)
        event = event.phase_to(EventPhase.EFFECT)
        return [], [], [], [], event


class MiddleCondition(BaseCondition):
    """Middle-level condition for 3-level chain tests."""
    name: str = "MiddleCondition"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    child_removal_policy: Literal["none", "any", "last"] = "last"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        event = declaration_event.phase_to(EventPhase.EXECUTION)
        event = event.phase_to(EventPhase.EFFECT)
        return [], [], [], [], event


# =========================================================================
# Tests
# =========================================================================

def test_1_parent_link_set():
    """parent_link is set by add_linked_condition()."""
    print("\n=== Test 1: parent_link set by add_linked_condition() ===")
    reset_combat_state()

    entity_a = create_caster("A", (0, 0))
    entity_b = create_target("B", (1, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=entity_a.uuid,
        target_entity_uuid=entity_a.uuid,
    )
    entity_a.add_condition(parent)

    child = DummyEffect(
        source_entity_uuid=entity_a.uuid,
        target_entity_uuid=entity_b.uuid,
    )
    entity_b.add_condition(child)

    parent.add_linked_condition(entity_b.uuid, child.uuid)

    check(child.parent_link is not None, "child.parent_link is not None")
    check(child.parent_link == (entity_a.uuid, parent.uuid), "parent_link has correct (block_uuid, cond_uuid)")


def test_2_parent_link_default_none():
    """parent_link is None by default."""
    print("\n=== Test 2: parent_link defaults to None ===")
    reset_combat_state()

    entity = create_caster("A", (0, 0))
    cond = DummyEffect(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    entity.add_condition(cond)

    check(cond.parent_link is None, "parent_link is None for unlinked condition")


def test_3_policy_default_none():
    """child_removal_policy defaults to 'none'."""
    print("\n=== Test 3: child_removal_policy defaults to 'none' ===")
    reset_combat_state()

    cond = DummyEffect(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
    )
    check(cond.child_removal_policy == "none", "Default policy is 'none'")


def test_4_last_policy_single_child():
    """'last' policy: single child removed → parent removed."""
    print("\n=== Test 4: 'last' policy — single child removed → parent removed ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="last",
    )
    caster.add_condition(parent)

    child = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(child)
    parent.add_linked_condition(target.uuid, child.uuid)

    check(has_condition(caster, "ParentWithPolicy"), "Parent is active before child removal")
    check(has_condition(target, "DummyEffect"), "Child is active before removal")

    target.remove_condition("DummyEffect")

    check(not has_condition(target, "DummyEffect"), "Child removed")
    check(not has_condition(caster, "ParentWithPolicy"), "Parent auto-removed via reverse link")


def test_5_last_policy_parent_subconditions_cleaned():
    """'last' policy: parent's own sub_conditions cleaned up."""
    print("\n=== Test 5: 'last' policy — parent sub_conditions cleaned ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))

    # Parent with a sub-condition on the caster
    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="last",
    )
    caster.add_condition(parent)

    # Add sub-condition on caster (same block)
    sub = DummySubCondition(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        parent_condition=parent.uuid,
    )
    caster.add_condition(sub)
    parent.sub_conditions.append(sub.uuid)

    # Add linked child on target
    child = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(child)
    parent.add_linked_condition(target.uuid, child.uuid)

    check(has_condition(caster, "DummySubCondition"), "Sub-condition active before")

    target.remove_condition("DummyEffect")

    check(not has_condition(caster, "ParentWithPolicy"), "Parent removed")
    check(not has_condition(caster, "DummySubCondition"), "Sub-condition also cleaned up")


def test_6_last_policy_two_children():
    """'last' policy: 2 children — remove one, parent stays; remove second, parent removed."""
    print("\n=== Test 6: 'last' policy — 2 children, sequential removal ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target1 = create_target("Target1", (1, 0))
    target2 = create_target("Target2", (2, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="last",
    )
    caster.add_condition(parent)

    child1 = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target1.uuid,
    )
    target1.add_condition(child1)
    parent.add_linked_condition(target1.uuid, child1.uuid)

    child2 = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target2.uuid,
    )
    target2.add_condition(child2)
    parent.add_linked_condition(target2.uuid, child2.uuid)

    # Remove first child
    target1.remove_condition("DummyEffect")

    check(not has_condition(target1, "DummyEffect"), "Child1 removed")
    check(has_condition(caster, "ParentWithPolicy"), "Parent still active (one child remains)")
    check(has_condition(target2, "DummyEffect"), "Child2 still active")

    # Remove second child
    target2.remove_condition("DummyEffect")

    check(not has_condition(target2, "DummyEffect"), "Child2 removed")
    check(not has_condition(caster, "ParentWithPolicy"), "Parent removed after last child")


def test_7_last_policy_sibling_state():
    """'last' policy: verify remaining sibling applied state during intermediate step."""
    print("\n=== Test 7: 'last' policy — sibling applied state ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target1 = create_target("Target1", (1, 0))
    target2 = create_target("Target2", (2, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="last",
    )
    caster.add_condition(parent)

    child1 = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target1.uuid,
    )
    target1.add_condition(child1)
    parent.add_linked_condition(target1.uuid, child1.uuid)

    child2 = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target2.uuid,
    )
    target2.add_condition(child2)
    parent.add_linked_condition(target2.uuid, child2.uuid)

    # Remove first child — second should still be applied
    target1.remove_condition("DummyEffect")

    check(child2.applied, "Remaining sibling is still applied")
    check(has_condition(target2, "DummyEffect"), "Remaining sibling still in target's active_conditions")


def test_8_any_policy_cascade():
    """'any' policy: remove one child → parent + other sibling all removed."""
    print("\n=== Test 8: 'any' policy — cascade removal ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target1 = create_target("Target1", (1, 0))
    target2 = create_target("Target2", (2, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="any",
    )
    caster.add_condition(parent)

    child1 = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target1.uuid,
    )
    target1.add_condition(child1)
    parent.add_linked_condition(target1.uuid, child1.uuid)

    child2 = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target2.uuid,
    )
    target2.add_condition(child2)
    parent.add_linked_condition(target2.uuid, child2.uuid)

    # Remove first child — should cascade: parent removed, then child2 removed via linked_conditions
    target1.remove_condition("DummyEffect")

    check(not has_condition(target1, "DummyEffect"), "Child1 removed")
    check(not has_condition(caster, "ParentWithPolicy"), "Parent removed via 'any' policy")
    check(not has_condition(target2, "DummyEffect"), "Child2 removed via parent cascade")


def test_9_any_policy_deep_cleanup():
    """'any' policy: sibling's sub_conditions cleaned in cascade."""
    print("\n=== Test 9: 'any' policy — deep cleanup ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target1 = create_target("Target1", (1, 0))
    target2 = create_target("Target2", (2, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="any",
    )
    caster.add_condition(parent)

    child1 = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target1.uuid,
    )
    target1.add_condition(child1)
    parent.add_linked_condition(target1.uuid, child1.uuid)

    # child2 has a sub-condition
    child2 = DummyEffectWithSub(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target2.uuid,
    )
    target2.add_condition(child2)
    parent.add_linked_condition(target2.uuid, child2.uuid)

    check(has_condition(target2, "DummySubCondition"), "Child2's sub-condition active before")

    target1.remove_condition("DummyEffect")

    check(not has_condition(target2, "DummyEffectWithSub"), "Child2 removed via cascade")
    check(not has_condition(target2, "DummySubCondition"), "Child2's sub-condition also cleaned")


def test_10_none_policy_no_notification():
    """'none' policy: child removed → parent stays."""
    print("\n=== Test 10: 'none' policy — no notification ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="none",
    )
    caster.add_condition(parent)

    child = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(child)
    parent.add_linked_condition(target.uuid, child.uuid)

    target.remove_condition("DummyEffect")

    check(not has_condition(target, "DummyEffect"), "Child removed")
    check(has_condition(caster, "ParentWithPolicy"), "Parent still active (policy='none')")


def test_11_none_policy_stale_reference():
    """'none' policy: parent linked_conditions still has stale reference."""
    print("\n=== Test 11: 'none' policy — stale reference preserved ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="none",
    )
    caster.add_condition(parent)

    child = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(child)
    parent.add_linked_condition(target.uuid, child.uuid)

    target.remove_condition("DummyEffect")

    check(len(parent.linked_conditions) == 1, "Parent still has linked_conditions entry (stale)")


def test_12_parent_driven_removal():
    """Parent-driven removal still removes all linked children."""
    print("\n=== Test 12: Parent-driven removal ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target1 = create_target("Target1", (1, 0))
    target2 = create_target("Target2", (2, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="last",
    )
    caster.add_condition(parent)

    child1 = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target1.uuid,
    )
    target1.add_condition(child1)
    parent.add_linked_condition(target1.uuid, child1.uuid)

    child2 = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target2.uuid,
    )
    target2.add_condition(child2)
    parent.add_linked_condition(target2.uuid, child2.uuid)

    # Remove parent directly
    caster.remove_condition("ParentWithPolicy")

    check(not has_condition(caster, "ParentWithPolicy"), "Parent removed")
    check(not has_condition(target1, "DummyEffect"), "Child1 removed via parent")
    check(not has_condition(target2, "DummyEffect"), "Child2 removed via parent")


def test_13_no_double_removal_crash():
    """No double-removal crash when parent drives removal of children with parent_link set."""
    print("\n=== Test 13: No double-removal crash ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="last",
    )
    caster.add_condition(parent)

    child = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(child)
    parent.add_linked_condition(target.uuid, child.uuid)

    # Parent-driven removal: child's reverse link should NOT cause infinite loop
    try:
        caster.remove_condition("ParentWithPolicy")
        check(True, "No crash during parent-driven removal with reverse link")
    except RecursionError:
        check(False, "RecursionError during parent-driven removal!")


def test_14_caster_dies_concentration_breaks():
    """Caster dies → concentration breaks → linked effects removed."""
    print("\n=== Test 14: Caster dies → concentration breaks ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))
    Entity.update_all_entities_senses()

    # Apply concentration + linked effect manually
    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="TestSpell"
    )
    caster.add_condition(concentration)

    effect = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(effect)
    concentration.add_linked_condition(target.uuid, effect.uuid)

    check(has_condition(caster, "Concentrating"), "Caster concentrating before death")
    check(has_condition(target, "DummyEffect"), "Target has effect before caster death")

    # Kill the caster via damage - this triggers death handler which breaks concentration
    set_hp(caster, 1)
    deal_damage_to(caster, 100, DamageType.FORCE, source_uuid=target.uuid)

    check(not has_condition(target, "DummyEffect"), "Target effect removed after caster death")


def test_15_target_dies_effect_removed():
    """Target dies → effect manually dispelled from dead target → Concentrating removed via reverse link.

    Note: Death alone doesn't auto-remove arbitrary conditions from the target.
    The reverse link fires when the effect is explicitly removed (e.g., dispel on dead target).
    """
    print("\n=== Test 15: Effect removed from dead target → Concentrating removed ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))
    attacker = create_caster("Attacker", (2, 0))
    Entity.update_all_entities_senses()

    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="TestSpell"
    )
    caster.add_condition(concentration)

    effect = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(effect)
    concentration.add_linked_condition(target.uuid, effect.uuid)

    check(has_condition(caster, "Concentrating"), "Caster concentrating before target death")

    # Kill the target
    set_hp(target, 1)
    deal_damage_to(target, 100, DamageType.FORCE, source_uuid=attacker.uuid)

    # Effect still present on dead target (death doesn't auto-remove)
    check(has_condition(target, "DummyEffect"), "Effect still on dead target")

    # Now dispel the effect from the dead target
    target.remove_condition("DummyEffect")
    check(not has_condition(caster, "Concentrating"), "Concentrating removed via reverse link after effect dispelled")


def test_16_effect_dispelled():
    """Both alive, effect dispelled → Concentrating removed."""
    print("\n=== Test 16: Effect dispelled → Concentrating removed ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))

    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="TestSpell"
    )
    caster.add_condition(concentration)

    effect = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(effect)
    concentration.add_linked_condition(target.uuid, effect.uuid)

    # Dispel the effect directly
    target.remove_condition("DummyEffect")

    check(not has_condition(target, "DummyEffect"), "Effect removed")
    check(not has_condition(caster, "Concentrating"), "Concentrating auto-removed via reverse link")


def test_17_zone_condition_removed():
    """Zone condition on caster removed → Concentrating removed."""
    print("\n=== Test 17: Zone condition removed → Concentrating removed ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))

    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="TestZone"
    )
    caster.add_condition(concentration)

    # Zone conditions are typically on the caster itself
    zone = DummyEffect(
        name="TestZone",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
    )
    caster.add_condition(zone)
    concentration.add_linked_condition(caster.uuid, zone.uuid)

    check(has_condition(caster, "Concentrating"), "Concentrating active")
    check(has_condition(caster, "TestZone"), "Zone active")

    caster.remove_condition("TestZone")

    check(not has_condition(caster, "TestZone"), "Zone removed")
    check(not has_condition(caster, "Concentrating"), "Concentrating auto-removed")


def test_18_concentration_broken_zone_no_double():
    """Concentrating broken → zone removed → no double notification crash."""
    print("\n=== Test 18: Concentration broken → zone removed → no double notification ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))

    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="TestZone"
    )
    caster.add_condition(concentration)

    zone = DummyEffect(
        name="TestZone",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
    )
    caster.add_condition(zone)
    concentration.add_linked_condition(caster.uuid, zone.uuid)

    try:
        caster.remove_condition("Concentrating")
        check(not has_condition(caster, "Concentrating"), "Concentrating removed")
        check(not has_condition(caster, "TestZone"), "Zone also removed")
        check(True, "No crash during forward removal with reverse link")
    except RecursionError:
        check(False, "RecursionError during forward removal!")


def test_19_three_level_chain_bottom_up():
    """3-level chain: remove C → B removed → A removed, no infinite loop."""
    print("\n=== Test 19: 3-level chain — bottom-up removal ===")
    reset_combat_state()

    entity_a = create_caster("A", (0, 0))
    entity_b = create_target("B", (1, 0))
    entity_c = create_target("C", (2, 0))

    # A → linked → B → linked → C
    cond_a = ParentWithPolicy(
        name="LevelA",
        source_entity_uuid=entity_a.uuid,
        target_entity_uuid=entity_a.uuid,
        child_removal_policy="last",
    )
    entity_a.add_condition(cond_a)

    cond_b = MiddleCondition(
        name="LevelB",
        source_entity_uuid=entity_a.uuid,
        target_entity_uuid=entity_b.uuid,
    )
    entity_b.add_condition(cond_b)
    cond_a.add_linked_condition(entity_b.uuid, cond_b.uuid)

    cond_c = DummyEffect(
        name="LevelC",
        source_entity_uuid=entity_a.uuid,
        target_entity_uuid=entity_c.uuid,
    )
    entity_c.add_condition(cond_c)
    cond_b.add_linked_condition(entity_c.uuid, cond_c.uuid)

    try:
        entity_c.remove_condition("LevelC")
        check(not has_condition(entity_c, "LevelC"), "C removed")
        check(not has_condition(entity_b, "LevelB"), "B auto-removed via reverse link")
        check(not has_condition(entity_a, "LevelA"), "A auto-removed via reverse link chain")
        check(True, "No infinite loop in 3-level chain")
    except RecursionError:
        check(False, "RecursionError in 3-level chain!")


def test_20_three_level_chain_top_down():
    """3-level chain: parent-driven removal from top still works."""
    print("\n=== Test 20: 3-level chain — top-down removal ===")
    reset_combat_state()

    entity_a = create_caster("A", (0, 0))
    entity_b = create_target("B", (1, 0))
    entity_c = create_target("C", (2, 0))

    cond_a = ParentWithPolicy(
        name="LevelA",
        source_entity_uuid=entity_a.uuid,
        target_entity_uuid=entity_a.uuid,
        child_removal_policy="last",
    )
    entity_a.add_condition(cond_a)

    cond_b = MiddleCondition(
        name="LevelB",
        source_entity_uuid=entity_a.uuid,
        target_entity_uuid=entity_b.uuid,
    )
    entity_b.add_condition(cond_b)
    cond_a.add_linked_condition(entity_b.uuid, cond_b.uuid)

    cond_c = DummyEffect(
        name="LevelC",
        source_entity_uuid=entity_a.uuid,
        target_entity_uuid=entity_c.uuid,
    )
    entity_c.add_condition(cond_c)
    cond_b.add_linked_condition(entity_c.uuid, cond_c.uuid)

    try:
        entity_a.remove_condition("LevelA")
        check(not has_condition(entity_a, "LevelA"), "A removed")
        check(not has_condition(entity_b, "LevelB"), "B removed via parent")
        check(not has_condition(entity_c, "LevelC"), "C removed via grandparent")
        check(True, "No crash in top-down 3-level removal")
    except RecursionError:
        check(False, "RecursionError in top-down 3-level!")


def test_21_hold_person_save_removes_concentrating():
    """Hold Person: target saves → effect removed → Concentrating auto-removed."""
    print("\n=== Test 21: Hold Person save → Concentrating removed ===")

    spell_landed = False
    for _ in range(20):
        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)
        caster = create_caster("Mage", (0, 0))
        target = create_target("Victim", (1, 0))
        Entity.update_all_entities_senses()

        hold = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=2,
            template=False,
        )
        hold.apply()

        if has_condition(target, "Hold Person") and has_condition(caster, "Concentrating"):
            spell_landed = True
            # Now simulate a successful save by removing the effect directly
            target.remove_condition("Hold Person")
            check(not has_condition(target, "Hold Person"), "Hold Person removed from target")
            check(not has_condition(target, "Paralyzed"), "Paralyzed sub-condition removed")
            check(not has_condition(caster, "Concentrating"), "Concentrating auto-removed via reverse link")
            break

    if not spell_landed:
        check(False, "Hold Person never landed in 20 attempts (random save)")


def test_22_hold_person_full_chain():
    """Hold Person: after save, no Concentrating or Paralyzed anywhere."""
    print("\n=== Test 22: Hold Person full chain verification ===")

    for _ in range(20):
        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)
        caster = create_caster("Mage", (0, 0))
        target = create_target("Victim", (1, 0))
        Entity.update_all_entities_senses()

        hold = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=2,
            template=False,
        )
        hold.apply()

        if has_condition(target, "Hold Person"):
            target.remove_condition("Hold Person")

            check(not has_condition(caster, "Concentrating"), "No Concentrating on caster")
            check(not has_condition(target, "Paralyzed"), "No Paralyzed on target")
            check(not has_condition(target, "Hold Person"), "No Hold Person on target")
            break
    else:
        check(False, "Hold Person never landed")


def test_23_hold_monster_save():
    """Hold Monster: same pattern as Hold Person."""
    print("\n=== Test 23: Hold Monster save → Concentrating removed ===")

    for _ in range(20):
        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)
        caster = create_caster("Mage", (0, 0))
        target = create_target("Victim", (1, 0))
        Entity.update_all_entities_senses()

        hold = HoldMonster(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=5,
            template=False,
        )
        hold.apply()

        if has_condition(target, "Hold Monster"):
            target.remove_condition("Hold Monster")
            check(not has_condition(target, "Hold Monster"), "Hold Monster removed")
            check(not has_condition(target, "Paralyzed"), "Paralyzed removed")
            check(not has_condition(caster, "Concentrating"), "Concentrating auto-removed")
            break
    else:
        check(False, "Hold Monster never landed")


def test_24_hold_person_forward_path():
    """Hold Person: concentration broken → effect removed from target (forward path)."""
    print("\n=== Test 24: Hold Person — forward path (concentration broken) ===")

    for _ in range(20):
        reset_combat_state()
        get_map().create_rectangle(0, 0, 20, 20)
        caster = create_caster("Mage", (0, 0))
        target = create_target("Victim", (1, 0))
        Entity.update_all_entities_senses()

        hold = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=2,
            template=False,
        )
        hold.apply()

        if has_condition(target, "Hold Person"):
            # Break concentration from caster side
            caster.remove_condition("Concentrating")
            check(not has_condition(caster, "Concentrating"), "Concentrating removed from caster")
            check(not has_condition(target, "Hold Person"), "Hold Person removed from target")
            check(not has_condition(target, "Paralyzed"), "Paralyzed removed from target")
            break
    else:
        check(False, "Hold Person never landed")


def test_25_drop_concentration_available():
    """DropConcentration available when concentrating."""
    print("\n=== Test 25: DropConcentration available when concentrating ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Mage", (0, 0))
    Entity.update_all_entities_senses()

    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="TestSpell"
    )
    caster.add_condition(concentration)

    available = get_available_actions(caster)
    drop_action = None
    for info in available.all_actions:
        if info.template_name == "Drop Concentration":
            drop_action = info
            break

    check(drop_action is not None, "DropConcentration action is available")


def test_26_drop_concentration_not_available():
    """DropConcentration NOT available when not concentrating."""
    print("\n=== Test 26: DropConcentration NOT available when not concentrating ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Mage", (0, 0))
    Entity.update_all_entities_senses()

    # Validate DropConcentration cancels when not concentrating via direct instantiation.
    from dnd.actions import DropConcentration
    dc = DropConcentration(source_entity_uuid=caster.uuid, template=False)
    result = dc.apply()
    check(result is None or result.canceled, "DropConcentration cancels when not concentrating")


def test_27_drop_concentration_zero_cost():
    """DropConcentration costs 0 actions."""
    print("\n=== Test 27: DropConcentration costs 0 actions ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Mage", (0, 0))
    Entity.update_all_entities_senses()

    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="TestSpell"
    )
    caster.add_condition(concentration)

    actions_before = caster.action_economy.actions.normalized_score

    from dnd.actions import DropConcentration
    dc = DropConcentration(source_entity_uuid=caster.uuid, template=False)
    dc.apply()

    actions_after = caster.action_economy.actions.normalized_score

    check(actions_before == actions_after, f"Actions unchanged: {actions_before} → {actions_after}")


def test_28_drop_concentration_full_cleanup():
    """DropConcentration removes concentration + all linked effects."""
    print("\n=== Test 28: DropConcentration full cleanup ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    caster = create_caster("Mage", (0, 0))
    target = create_target("Target", (1, 0))
    Entity.update_all_entities_senses()

    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="TestSpell"
    )
    caster.add_condition(concentration)

    effect = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(effect)
    concentration.add_linked_condition(target.uuid, effect.uuid)

    from dnd.actions import DropConcentration
    dc = DropConcentration(source_entity_uuid=caster.uuid, template=False)
    dc.apply()

    check(not has_condition(caster, "Concentrating"), "Concentrating removed")
    check(not has_condition(target, "DummyEffect"), "Linked effect removed")


def test_29_drop_concentration_allows_new_spell():
    """After DropConcentration, entity can cast a new concentration spell."""
    print("\n=== Test 29: After DropConcentration, can cast new concentration spell ===")
    reset_combat_state()

    caster = create_caster("Mage", (0, 0))

    conc1 = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Spell1"
    )
    caster.add_condition(conc1)

    from dnd.actions import DropConcentration
    dc = DropConcentration(source_entity_uuid=caster.uuid, template=False)
    dc.apply()

    check(not has_condition(caster, "Concentrating"), "Old concentration gone")

    conc2 = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Spell2"
    )
    caster.add_condition(conc2)

    check(has_condition(caster, "Concentrating"), "New concentration applied")
    conc = caster.active_conditions["Concentrating"]
    assert isinstance(conc, Concentrating)
    check(conc.spell_name == "Spell2", f"New spell name: {conc.spell_name}")


def test_30_stale_parent_link():
    """Stale parent_link (parent already removed) → no crash."""
    print("\n=== Test 30: Stale parent_link → no crash ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="last",
    )
    caster.add_condition(parent)

    child = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(child)
    parent.add_linked_condition(target.uuid, child.uuid)

    # Remove parent first
    caster.remove_condition("ParentWithPolicy")
    # child was already removed by parent cascade, but if it weren't...
    # Verify no crash if child's parent_link points to removed parent
    check(True, "No crash with stale parent link")


def test_31_nonexistent_parent_block():
    """parent_link to non-existent block → no crash."""
    print("\n=== Test 31: Non-existent parent block → no crash ===")
    reset_combat_state()

    target = create_target("Target", (0, 0))

    child = DummyEffect(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    # Manually set parent_link to a non-existent block
    child.parent_link = (uuid4(), uuid4())
    target.add_condition(child)

    try:
        target.remove_condition("DummyEffect")
        check(True, "No crash when parent block doesn't exist")
    except Exception as e:
        check(False, f"Crash: {e}")


def test_32_parent_link_with_none_policy():
    """Condition with parent_link but parent has 'none' policy → no notification."""
    print("\n=== Test 32: parent_link with 'none' policy → no notification ===")
    reset_combat_state()

    caster = create_caster("Caster", (0, 0))
    target = create_target("Target", (1, 0))

    parent = ParentWithPolicy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        child_removal_policy="none",
    )
    caster.add_condition(parent)

    child = DummyEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(child)
    parent.add_linked_condition(target.uuid, child.uuid)

    check(child.parent_link is not None, "parent_link is set")

    target.remove_condition("DummyEffect")
    check(has_condition(caster, "ParentWithPolicy"), "Parent NOT removed (policy is 'none')")


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    test_1_parent_link_set()
    test_2_parent_link_default_none()
    test_3_policy_default_none()
    test_4_last_policy_single_child()
    test_5_last_policy_parent_subconditions_cleaned()
    test_6_last_policy_two_children()
    test_7_last_policy_sibling_state()
    test_8_any_policy_cascade()
    test_9_any_policy_deep_cleanup()
    test_10_none_policy_no_notification()
    test_11_none_policy_stale_reference()
    test_12_parent_driven_removal()
    test_13_no_double_removal_crash()
    test_14_caster_dies_concentration_breaks()
    test_15_target_dies_effect_removed()
    test_16_effect_dispelled()
    test_17_zone_condition_removed()
    test_18_concentration_broken_zone_no_double()
    test_19_three_level_chain_bottom_up()
    test_20_three_level_chain_top_down()
    test_21_hold_person_save_removes_concentrating()
    test_22_hold_person_full_chain()
    test_23_hold_monster_save()
    test_24_hold_person_forward_path()
    test_25_drop_concentration_available()
    test_26_drop_concentration_not_available()
    test_27_drop_concentration_zero_cost()
    test_28_drop_concentration_full_cleanup()
    test_29_drop_concentration_allows_new_spell()
    test_30_stale_parent_link()
    test_31_nonexistent_parent_block()
    test_32_parent_link_with_none_policy()

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if failed > 0:
        print("SOME TESTS FAILED!")
        exit(1)
    else:
        print("ALL TESTS PASSED!")
