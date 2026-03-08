"""
Integration tests for the AI framework.

Tests:
1. TacticalState construction from engine entities
2. BehaviorTree agent plays a turn (skeleton vs hero)
3. MoveAndAttack composite
4. Interrupt detection
5. Utility scorer picks highest-value option
6. AIAgentController integration with Encounter
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4

from dnd.utils import reset_combat_state, get_hp, get_max_hp
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.encounter import Encounter
from dnd.controller import PassController, AIAgentController

from ai.interface import LocalGameInterface
from ai.models import TacticalState, hit_chance, crit_chance, attack_ev, AttackData, DiceSpec
from ai.composites import MoveAndAttack, detect_interrupts, InterruptType
from ai.agents.examples import create_melee_fighter_bt
from ai.primitives.utility import UtilityAI, DamageScorer, FocusFireScorer


def test_tactical_state_construction():
    """Test that LocalGameInterface.get_tactical_state() builds correctly."""
    print("\n=== Test: TacticalState Construction ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    skeleton = create_skeleton(name="Skeleton", position=(5, 5))
    hero = create_skeleton(name="Hero", position=(8, 5), faction="heroes")
    Entity.update_all_entities_senses()

    iface = LocalGameInterface()
    state = iface.get_tactical_state(str(skeleton.uuid))

    # Self
    assert state.me.name == "Skeleton", f"Expected 'Skeleton', got '{state.me.name}'"
    assert state.me.position == (5, 5)
    assert state.me.hp > 0
    assert state.me.hp == get_hp(skeleton)

    # Enemies
    assert len(state.enemies) == 1, f"Expected 1 enemy, got {len(state.enemies)}"
    assert state.enemies[0].name == "Hero"
    assert state.enemies[0].uuid == str(hero.uuid)

    # Distance
    assert state.enemies[0].distance_feet is not None
    expected_dist = abs(5 - 8) * 5 + abs(5 - 5) * 5  # Manhattan * 5ft
    assert state.enemies[0].distance_feet == expected_dist, \
        f"Expected {expected_dist}ft, got {state.enemies[0].distance_feet}ft"

    # Actions
    assert len(state.attacks) > 0 or len(state.movements) > 0, "Should have attacks or movements"
    assert len(state.self_actions) > 0, "Should have self actions (Dash, Dodge)"

    # Query helpers
    nearest = state.nearest_enemy()
    assert nearest is not None
    assert nearest.name == "Hero"

    weakest = state.weakest_enemy()
    assert weakest is not None

    print(f"  Me: {state.me.name} at {state.me.position}, HP={state.me.hp}")
    print(f"  Enemies: {[(e.name, e.distance_feet) for e in state.enemies]}")
    print(f"  Attacks: {[a.display_name for a in state.attacks]}")
    print(f"  Self actions: {[a.display_name for a in state.self_actions]}")
    print(f"  Movements: {len(state.movements)} positions")
    print("  PASSED")


def test_tactical_state_action_economy():
    """Test action economy is correctly reported."""
    print("\n=== Test: Action Economy ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    skeleton = create_skeleton(name="Skeleton", position=(5, 5))
    Entity.update_all_entities_senses()

    # Set up encounter to initialize action economy
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(skeleton, PassController(source_entity_uuid=skeleton.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    iface = LocalGameInterface()
    state = iface.get_tactical_state(str(skeleton.uuid))

    assert state.action_economy.has_action, "Should have action"
    assert state.action_economy.has_movement, "Should have movement"
    assert not state.action_economy.is_empty, "Economy should not be empty"

    print(f"  Actions: {state.action_economy.actions}")
    print(f"  Bonus: {state.action_economy.bonus_actions}")
    print(f"  Movement: {state.action_economy.movement}")
    print("  PASSED")


def test_ev_computation():
    """Test expected value computation helpers."""
    print("\n=== Test: EV Computation ===")

    # Hit chance
    assert abs(hit_chance(5, 15) - 0.55) < 0.01, "5 vs AC 15 should be ~55%"
    assert hit_chance(5, 15, "advantage") > hit_chance(5, 15), "Advantage > normal"
    assert hit_chance(5, 15, "disadvantage") < hit_chance(5, 15), "Disadvantage < normal"
    assert hit_chance(0, 0, auto_hit="autohit") == 1.0
    assert hit_chance(0, 0, auto_hit="automiss") == 0.0

    # Crit chance
    assert abs(crit_chance(20) - 0.05) < 0.001
    assert abs(crit_chance(19) - 0.10) < 0.001

    # Attack EV
    data = AttackData(
        attack_bonus=5,
        damage_dice=[DiceSpec(count=1, sides=8, bonus=3)],
        crit_threshold=20,
    )
    ev = attack_ev(data, target_ac=15)
    assert ev > 0, f"EV should be > 0, got {ev}"
    # Rough check: ~55% * 7.5 = ~4.1 (plus crit component)
    assert 3.0 < ev < 6.0, f"EV {ev} outside reasonable range"

    print(f"  Hit chance (5 vs AC15): {hit_chance(5, 15):.2%}")
    print(f"  Crit chance (threshold 20): {crit_chance(20):.2%}")
    print(f"  Attack EV (1d8+3 vs AC15): {ev:.2f}")
    print("  PASSED")


def test_execute_action():
    """Test LocalGameInterface.execute()."""
    print("\n=== Test: Execute Action ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    skeleton = create_skeleton(name="Skeleton", position=(5, 5))
    hero = create_skeleton(name="Hero", position=(6, 5))  # Adjacent
    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(skeleton, PassController(source_entity_uuid=skeleton.uuid))
    encounter.add_combatant(hero, PassController(source_entity_uuid=hero.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    # Start first turn, skip to skeleton's turn if needed
    encounter.start_turn()
    current = encounter.get_current_entity()
    if current and current.uuid != skeleton.uuid:
        encounter.end_turn()
        encounter.next_turn()  # auto-calls start_turn()

    iface = LocalGameInterface()
    state = iface.get_tactical_state(str(skeleton.uuid))

    # Should have an attack available against adjacent hero
    attack = state.find_attack_targeting(str(hero.uuid))
    assert attack is not None, "Should find attack targeting Hero"

    result = iface.execute(str(skeleton.uuid), attack[0].template_name, attack[1].index)
    assert result.success, "Attack should succeed"
    assert result.entity_hp is not None, "Should report entity HP"

    print(f"  Attack result: success={result.success}")
    print(f"  Skeleton HP after: {result.entity_hp}")
    print(f"  Hero HP after: {result.target_hp}")
    print("  PASSED")


def test_behavior_tree_agent():
    """Test BT agent plays a full turn: move toward enemy and attack."""
    print("\n=== Test: BehaviorTree Agent ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    skeleton = create_skeleton(name="BT Skeleton", position=(2, 5))
    hero = create_skeleton(name="Target Hero", position=(8, 5), faction="heroes")
    Entity.update_all_entities_senses()

    iface = LocalGameInterface()
    agent = create_melee_fighter_bt(iface, str(skeleton.uuid))

    # Set up encounter and start skeleton's turn
    controller = AIAgentController(source_entity_uuid=skeleton.uuid)
    controller.set_agent(agent)

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(skeleton, controller)
    encounter.add_combatant(hero, PassController(source_entity_uuid=hero.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    initial_skeleton_pos = skeleton.position
    initial_hero_hp = get_hp(hero)

    # Start first turn manually, then use next_turn() which auto-calls start_turn()
    encounter.start_turn()

    for _ in range(6):  # 6 turns max
        current = encounter.get_current_entity()
        if current is None:
            break

        if current.uuid == skeleton.uuid:
            agent.run_turn()

        encounter.end_turn()
        encounter.check_deaths()
        if encounter.state.value != "active":
            break
        encounter.next_turn()  # auto-calls start_turn()

    # Skeleton should have moved from initial position
    final_skeleton_pos = skeleton.position
    moved = final_skeleton_pos != initial_skeleton_pos

    print(f"  Skeleton moved: {initial_skeleton_pos} -> {final_skeleton_pos} (moved={moved})")
    print(f"  Hero HP: {initial_hero_hp} -> {get_hp(hero)}")
    print(f"  Encounter state: {encounter.state.value}")
    assert moved, "Skeleton should have moved toward hero"
    print("  PASSED")


def test_move_and_attack_composite():
    """Test MoveAndAttack composite action."""
    print("\n=== Test: MoveAndAttack Composite ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    skeleton = create_skeleton(name="Attacker", position=(3, 5))
    hero = create_skeleton(name="Target", position=(5, 5), faction="heroes")
    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(skeleton, PassController(source_entity_uuid=skeleton.uuid))
    encounter.add_combatant(hero, PassController(source_entity_uuid=hero.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    # Start first turn, skip to skeleton's turn if needed
    encounter.start_turn()
    current = encounter.get_current_entity()
    if current and current.uuid != skeleton.uuid:
        encounter.end_turn()
        encounter.next_turn()  # auto-calls start_turn()

    iface = LocalGameInterface()
    state = iface.get_tactical_state(str(skeleton.uuid))

    composite = MoveAndAttack(str(hero.uuid))
    result = composite.execute(iface, state, str(skeleton.uuid))

    print(f"  Result: success={result.success}, actions_taken={result.actions_taken}")
    print(f"  Description: {result.description}")
    print(f"  Skeleton position: {skeleton.position}")
    # Skeleton should have moved closer or attacked
    assert result.actions_taken > 0, "Should have taken at least one action"
    print("  PASSED")


def test_interrupt_detection():
    """Test interrupt detection between tactical states."""
    print("\n=== Test: Interrupt Detection ===")

    from ai.models import TacticalEntity, ActionEconomy, ActionResult

    before_me = TacticalEntity(
        uuid="me", name="Me", position=(0, 0),
        hp=50, max_hp=50, ac=15,
    )
    after_me = TacticalEntity(
        uuid="me", name="Me", position=(0, 0),
        hp=43, max_hp=50, ac=15,
        conditions=["Poisoned"],
    )
    enemy = TacticalEntity(
        uuid="enemy1", name="Goblin", position=(5, 5),
        hp=10, max_hp=10, ac=12,
    )
    new_enemy = TacticalEntity(
        uuid="enemy2", name="Hobgoblin", position=(10, 10),
        hp=20, max_hp=20, ac=16,
    )

    before = TacticalState(
        me=before_me,
        action_economy=ActionEconomy(actions=1, bonus_actions=1, reactions=1, movement=30),
        enemies=[enemy],
    )
    after = TacticalState(
        me=after_me,
        action_economy=ActionEconomy(actions=0, bonus_actions=1, reactions=1, movement=30),
        enemies=[enemy, new_enemy],
    )
    result = ActionResult(success=True, entity_hp=43, deaths=["Goblin"])

    interrupts = detect_interrupts(before, result, after)

    assert InterruptType.DAMAGE_TAKEN in interrupts, "Should detect damage taken (50->43)"
    assert InterruptType.TARGET_DIED in interrupts, "Should detect target death"
    assert InterruptType.NEW_ENEMY in interrupts, "Should detect new enemy (Hobgoblin)"
    assert InterruptType.CONDITION_GAINED in interrupts, "Should detect Poisoned condition"

    print(f"  Detected interrupts: {[i.value for i in interrupts]}")
    print("  PASSED")


def test_utility_scorer():
    """Test utility scoring picks the best action."""
    print("\n=== Test: Utility Scorer ===")

    from ai.models import TacticalEntity, ActionEconomy, ActionOption, TargetOption

    me = TacticalEntity(
        uuid="me", name="Fighter", position=(5, 5),
        hp=50, max_hp=50, ac=18,
    )

    weak_enemy = TacticalEntity(
        uuid="weak", name="Weak Goblin", position=(6, 5),
        hp=3, max_hp=10, ac=12, distance_feet=5,
    )
    strong_enemy = TacticalEntity(
        uuid="strong", name="Strong Orc", position=(7, 5),
        hp=50, max_hp=50, ac=16, distance_feet=10,
    )

    # Create two attack options
    from ai.models import AttackData, DiceSpec
    attack_weak = ActionOption(
        template_name="Attack_MELEE_MAIN",
        display_name="Longsword",
        category="attack",
        target_type="entity",
        cost_type="actions",
        can_afford=True,
        attack_data=AttackData(
            attack_bonus=7,
            damage_dice=[DiceSpec(count=1, sides=8, bonus=4)],
        ),
        targets=[TargetOption(
            index=0, target_uuid="weak", target_name="Weak Goblin",
            target_ac=12,
        )],
    )
    attack_strong = ActionOption(
        template_name="Attack_MELEE_MAIN",
        display_name="Longsword",
        category="attack",
        target_type="entity",
        cost_type="actions",
        can_afford=True,
        attack_data=AttackData(
            attack_bonus=7,
            damage_dice=[DiceSpec(count=1, sides=8, bonus=4)],
        ),
        targets=[TargetOption(
            index=1, target_uuid="strong", target_name="Strong Orc",
            target_ac=16,
        )],
    )

    state = TacticalState(
        me=me,
        action_economy=ActionEconomy(actions=1, bonus_actions=1, reactions=1, movement=30),
        enemies=[weak_enemy, strong_enemy],
        attacks=[attack_weak, attack_strong],
    )

    utility = UtilityAI([
        DamageScorer(weight=1.0),
        FocusFireScorer(weight=0.5),
    ])

    ranked = utility.evaluate_all(state)
    assert len(ranked) > 0, "Should have scored options"

    best = ranked[0]
    print(f"  Best action: {best.action.display_name}")
    print(f"  Best target: {best.target.target_name if best.target else 'none'}")
    print(f"  Score: {best.score:.2f}")
    print(f"  Breakdown: {best.breakdown}")

    # The weak enemy should score higher: same damage EV (lower AC = higher hit chance)
    # plus focus fire bonus for being weakest
    assert best.target is not None
    assert best.target.target_uuid == "weak", \
        f"Should target weak enemy (focus fire), got {best.target.target_uuid}"
    print("  PASSED")


def test_ai_controller_integration():
    """Test AIAgentController with a full encounter."""
    print("\n=== Test: AIAgentController Integration ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    skeleton = create_skeleton(name="AI Skeleton", position=(3, 5))
    hero = create_skeleton(name="Passive Hero", position=(5, 5), faction="heroes")
    Entity.update_all_entities_senses()

    iface = LocalGameInterface()

    # Create controller and bind agent
    ai_controller = AIAgentController(source_entity_uuid=skeleton.uuid)
    agent = create_melee_fighter_bt(iface, str(skeleton.uuid))
    ai_controller.set_agent(agent)

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(skeleton, ai_controller)
    encounter.add_combatant(hero, PassController(source_entity_uuid=hero.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    # Run 3 full rounds
    for _ in range(6):  # 6 turns = 3 rounds for 2 entities
        current = encounter.get_current_entity()
        if current is None:
            break
        encounter.run_turn()
        if encounter.state.value != "active":
            break

    print(f"  Skeleton position: {skeleton.position}")
    print(f"  Hero HP: {get_hp(hero)}")
    print(f"  Encounter state: {encounter.state.value}")
    # The skeleton should have moved and potentially dealt damage
    assert skeleton.position != (3, 5) or get_hp(hero) < get_max_hp(hero), \
        "Skeleton should have either moved or dealt damage"
    print("  PASSED")


def test_find_move_helpers():
    """Test TacticalState movement helpers."""
    print("\n=== Test: Movement Helpers ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    skeleton = create_skeleton(name="Mover", position=(5, 5))
    hero = create_skeleton(name="Target", position=(10, 5), faction="heroes")
    Entity.update_all_entities_senses()

    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(skeleton, PassController(source_entity_uuid=skeleton.uuid))
    encounter.add_combatant(hero, PassController(source_entity_uuid=hero.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    encounter.start_turn()
    current = encounter.get_current_entity()
    if current and current.uuid != skeleton.uuid:
        encounter.end_turn()
        encounter.next_turn()  # auto-calls start_turn()

    iface = LocalGameInterface()
    state = iface.get_tactical_state(str(skeleton.uuid))

    # Test find_move_toward
    move_toward = state.find_move_toward(str(hero.uuid))
    assert move_toward is not None, "Should find a move toward hero"
    assert move_toward[1].position is not None
    # Move toward should get us closer
    my_dist = abs(5 - 10) + abs(5 - 5)
    new_dist = abs(move_toward[1].position[0] - 10) + abs(move_toward[1].position[1] - 5)
    assert new_dist < my_dist, f"Should get closer: {my_dist} -> {new_dist}"

    # Test find_move_away_from
    move_away = state.find_move_away_from(hero.position)
    assert move_away is not None, "Should find a move away from hero"
    assert move_away[1].position is not None
    away_dist = abs(move_away[1].position[0] - 10) + abs(move_away[1].position[1] - 5)
    assert away_dist > my_dist, f"Should get farther: {my_dist} -> {away_dist}"

    # Test find_self_action
    dodge = state.find_self_action("Dodge")
    assert dodge is not None, "Should find Dodge action"
    dash = state.find_self_action("Dash")
    assert dash is not None, "Should find Dash action"

    print(f"  Move toward: {move_toward[1].position} (dist {my_dist} -> {new_dist})")
    print(f"  Move away: {move_away[1].position} (dist {my_dist} -> {away_dist})")
    print(f"  Found Dodge: {dodge.template_name}")
    print(f"  Found Dash: {dash.template_name}")
    print("  PASSED")


if __name__ == "__main__":
    test_tactical_state_construction()
    test_tactical_state_action_economy()
    test_ev_computation()
    test_execute_action()
    test_behavior_tree_agent()
    test_move_and_attack_composite()
    test_interrupt_detection()
    test_utility_scorer()
    test_ai_controller_integration()
    test_find_move_helpers()
    print("\n=== ALL TESTS PASSED ===")
