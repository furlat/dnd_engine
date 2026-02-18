"""
Test Second Wind resource system - verifies integration with available actions.

This example demonstrates:
1. Resource system in ActionEconomy (add_resource, consume_resource, on_short_rest)
2. BaseCost extension with resource_name/resource_cost
3. SecondWind action that uses bonus action + second_wind resource
4. Integration with get_available_actions() and execute_by_index()
"""
from typing import Optional, List
from pydantic import Field

from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.core.base_actions import (
    BaseAction, ActionEvent, Cost, TargetType, BaseCost
)
from dnd.core.events import EventPhase
from dnd.core.dice import Dice, RollType
from dnd.core.values import ModifiableValue
from dnd.core.gridmap import get_map
from dnd.blocks.action_economy import RechargeType
from dnd.blocks.health import DamageType
from dnd.actions import entity_action_economy_cost_evaluator, entity_action_economy_cost_applier
from dnd.actions_functional import setup_standard_actions, execute_by_index
from dnd.utils import reset_combat_state


# =============================================================================
# SecondWind Action (defined locally for this proof-of-concept)
# =============================================================================

class SecondWind(BaseAction):
    """
    Fighter's Second Wind - heal 1d10 + fighter level as a bonus action.
    Uses the 'second_wind' resource (must be registered on entity).
    """
    name: str = Field(default="Second Wind")
    description: str = Field(default="Heal 1d10 + level as a bonus action")
    target_type: TargetType = Field(default=TargetType.SELF)
    fighter_level: int = Field(default=1)

    # Cost: 1 bonus action + 1 second_wind resource
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(
            name="Second Wind Cost",
            cost_type="bonus_actions",
            cost=1,
            evaluator=entity_action_economy_cost_evaluator,
            resource_name="second_wind",
            resource_cost=1
        )
    ])

    def _create_declaration_event(self, parent_event=None, use_register: bool = True) -> Optional[ActionEvent]:
        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register
        )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return declaration_event.cancel(status_message="Entity not found")

        # Check entity is damaged (has damage_taken > 0)
        if entity.health.damage_taken == 0:
            return declaration_event.cancel(status_message="Already at full health")

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Second Wind ready"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")

        # Roll healing: 1d10 + fighter level
        # Use CHECK roll type since DAMAGE requires attack_outcome
        healing_dice = Dice(
            count=1,
            value=10,
            bonus=ModifiableValue.create(source_entity_uuid=self.source_entity_uuid, base_value=self.fighter_level, value_name="Fighter Level"),
            roll_type=RollType.CHECK  # Using CHECK type for healing dice (no attack outcome needed)
        )
        healing_roll = healing_dice.roll
        total_healing = healing_roll.total

        # Apply healing
        hp_before = entity.get_hp()
        entity.health.heal(total_healing)
        hp_after = entity.get_hp()
        actual_healing = hp_after - hp_before

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Second Wind heals {actual_healing} HP (d10+{self.fighter_level}={total_healing})"
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Second Wind complete - healed {actual_healing} HP"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# Test Script
# =============================================================================

def test_second_wind():
    print("=" * 60)
    print("TEST: Second Wind Resource System")
    print("=" * 60)

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    # Create entity (skeleton as base)
    fighter = create_skeleton(name="Fighter", position=(0, 0))
    setup_standard_actions(fighter)

    # =========================================================================
    # SETUP: Register Second Wind resource and action
    # =========================================================================
    print("\n--- SETUP ---")

    # Register the resource (simulating Fighter level 1 feature)
    fighter.action_economy.add_resource("second_wind", maximum=1, recharge_type=RechargeType.SHORT_REST)
    print(f"Registered 'second_wind' resource: {fighter.action_economy.resources['second_wind']}")

    # Register Second Wind action template
    second_wind_template = SecondWind(
        source_entity_uuid=fighter.uuid,
        template=True,
        fighter_level=1
    )
    fighter.register_action(second_wind_template)
    print(f"Registered 'Second Wind' action template")

    # Damage the fighter
    initial_hp = fighter.get_hp()
    print(f"\nInitial HP: {initial_hp}")
    fighter.health.take_damage(10, DamageType.SLASHING, fighter.uuid)
    print(f"After damage: {fighter.get_hp()} (took 10 slashing)")

    # =========================================================================
    # TEST 1: Second Wind appears in get_available_actions()
    # =========================================================================
    print("\n--- TEST 1: Available Actions ---")

    # Debug: Check if Second Wind is registered
    print(f"Registered actions: {[a.name for a in fighter.registered_actions]}")
    print(f"Self actions (from property): {[a.name for a in fighter.self_actions]}")

    actions = fighter.get_available_actions()
    self_action_names = [a.template_name for a in actions.self_actions]
    print(f"Available self actions: {self_action_names}")

    assert "Second Wind" in self_action_names, "Second Wind should appear in self_actions!"
    print("PASS: Second Wind appears in available actions")

    # Find Second Wind in the list
    second_wind_action = next((a for a in actions.self_actions if a.template_name == "Second Wind"), None)
    assert second_wind_action is not None
    print(f"  can_afford: {second_wind_action.can_afford}")
    print(f"  valid_targets: {len(second_wind_action.valid_targets)} (self)")
    assert second_wind_action.can_afford, "Should be able to afford Second Wind"
    print("PASS: Second Wind is affordable")

    # =========================================================================
    # TEST 2: Execute via available actions interface (execute_by_index)
    # =========================================================================
    print("\n--- TEST 2: Execute via Available Actions Interface ---")
    hp_before = fighter.get_hp()
    event = execute_by_index(fighter, "Second Wind", target_index=0)
    print(f"Result: {event.status_message if event else 'Failed'}")
    hp_after = fighter.get_hp()
    print(f"HP: {hp_before} -> {hp_after} (healed {hp_after - hp_before})")
    assert hp_after > hp_before, "Should have healed"
    print("PASS: Second Wind healed the fighter")

    # =========================================================================
    # TEST 3: Resource consumed - action no longer affordable
    # =========================================================================
    print("\n--- TEST 3: Resource Consumed ---")
    print(f"Second Wind uses remaining: {fighter.action_economy.resources['second_wind'].current}")
    assert fighter.action_economy.resources['second_wind'].current == 0, "Resource should be consumed"
    print("PASS: Resource was consumed")

    # Check available actions again - Second Wind should show can_afford=False
    actions2 = fighter.get_available_actions()
    second_wind_action2 = next((a for a in actions2.self_actions if a.template_name == "Second Wind"), None)
    print(f"Second Wind can_afford after use: {second_wind_action2.can_afford if second_wind_action2 else 'NOT FOUND'}")
    assert second_wind_action2 is not None, "Second Wind should still appear"
    assert not second_wind_action2.can_afford, "Should NOT be able to afford (resource consumed)"
    print("PASS: Second Wind shows as not affordable after use")

    # =========================================================================
    # TEST 4: Manual execution also fails (no resource)
    # =========================================================================
    print("\n--- TEST 4: Manual Execution Fails ---")
    # Damage again so health check passes (if they were fully healed)
    if fighter.health.damage_taken == 0:
        fighter.health.take_damage(5, DamageType.SLASHING, fighter.uuid)
    second_wind_manual = SecondWind(source_entity_uuid=fighter.uuid, fighter_level=1)
    event2 = second_wind_manual.apply()
    result_msg = event2.status_message if event2 else "Failed - returned None (cost check failed)"
    print(f"Manual attempt: {result_msg}")
    assert event2 is None, "Should fail due to no resource"
    print("PASS: Manual execution fails when no resource")

    # =========================================================================
    # TEST 5: Short rest recharges resource
    # =========================================================================
    print("\n--- TEST 5: Short Rest Recharges ---")
    fighter.action_economy.on_short_rest()
    print(f"After short rest: {fighter.action_economy.resources['second_wind'].current} uses")
    assert fighter.action_economy.resources['second_wind'].current == 1, "Should recharge"
    print("PASS: Resource recharged on short rest")

    # Also reset action economy (simulate start of a new turn after rest)
    # Short rest only restores resources, not action economy
    fighter.action_economy.reset_all_costs()
    print(f"After reset_all_costs: bonus_actions = {fighter.action_economy.bonus_actions.self_static.normalized_score}")

    # Check available actions - should be affordable again
    actions3 = fighter.get_available_actions()
    second_wind_action3 = next((a for a in actions3.self_actions if a.template_name == "Second Wind"), None)
    assert second_wind_action3 is not None, "Second Wind should still be registered"
    print(f"Second Wind can_afford after rest: {second_wind_action3.can_afford}")
    assert second_wind_action3.can_afford, "Should be affordable after rest"
    print("PASS: Second Wind is affordable again after rest")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print("\nDemonstrated:")
    print("  1. Resource registration (add_resource with RechargeType)")
    print("  2. Action template with resource cost (resource_name + resource_cost)")
    print("  3. Resource checking in check_costs()")
    print("  4. Resource consumption in entity_action_economy_cost_applier()")
    print("  5. Integration with get_available_actions() and execute_by_index()")
    print("  6. Short rest resource recharge")


if __name__ == "__main__":
    test_second_wind()
