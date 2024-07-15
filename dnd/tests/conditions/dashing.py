from dnd.statsblock import StatsBlock
from dnd.monsters.goblin import create_goblin
from dnd.conditions import Dashing, Duration, DurationType

def print_creature_details(creature: StatsBlock):
    print(f"{creature.name} Details:")
    print(f"HP: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Speed: Walk {creature.speed.get_speed('walk', creature)} ft, "
          f"Fly {creature.speed.get_speed('fly', creature)} ft, "
          f"Swim {creature.speed.get_speed('swim', creature)} ft")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")

def test_dashing_condition():
    goblin = create_goblin()
    
    print("\n=== Testing Dashing Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    
    print("\n2. Applying Dashing condition to Goblin")
    dashing_condition = Dashing(name="Dashing", duration=Duration(time=1, type=DurationType.ROUNDS))
    goblin.apply_condition(dashing_condition)
    print_creature_details(goblin)
    
    print("\n3. Adding a speed bonus while Dashing")
    goblin.speed.add_static_modifier('walk', "Magic Boost", 10)
    print_creature_details(goblin)
    
    print("\n4. Advancing time to expire the Dashing condition")
    goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n5. Removing the speed bonus")
    goblin.speed.remove_static_modifier('walk', "Magic Boost")
    print_creature_details(goblin)

if __name__ == "__main__":
    test_dashing_condition()