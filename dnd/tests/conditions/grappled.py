from dnd.statsblock import StatsBlock
from dnd.monsters.goblin import create_goblin
from dnd.monsters.skeleton import create_skeleton
from dnd.conditions import Grappled, Duration, DurationType
from dnd.core import Speed

def print_creature_details(creature: StatsBlock):
    print(f"{creature.name} Details:")
    print(f"HP: {creature.current_hit_points}/{creature.max_hit_points}")
    print(f"Speed: Walk {creature.speed.get_speed('walk', creature)} ft, "
          f"Fly {creature.speed.get_speed('fly', creature)} ft, "
          f"Swim {creature.speed.get_speed('swim', creature)} ft")
    print(f"Active Conditions: {', '.join([cond for cond in creature.active_conditions.keys()])}")
def test_grappled_condition():
    goblin = create_goblin()
    skeleton = create_skeleton()
    
    print("\n=== Testing Grappled Condition ===")
    
    print("\n1. Initial State")
    print_creature_details(goblin)
    
    print("\n2. Applying Grappled condition to Goblin")
    grappled_condition = Grappled(name="Grappled", duration=Duration(time=3, type=DurationType.ROUNDS), source_entity_id=skeleton.id)
    goblin.apply_condition(grappled_condition)
    print_creature_details(goblin)
    
    print("\n3. Attempting to move while Grappled")
    print(f"Goblin tries to move: {'Can move' if goblin.speed.get_speed('walk', goblin) > 0 else 'Cannot move'}")
    
    print("\n4. Adding a speed bonus while Grappled")
    goblin.speed.add_bonus('walk', "Magic Boost", lambda src, tgt,ctx: 10)
    print_creature_details(goblin)
    
    print("\n5. Advancing time to expire the Grappled condition")
    for _ in range(3):
        goblin.update_conditions()
    print_creature_details(goblin)
    
    print("\n6. Removing the speed bonus")
    goblin.speed.remove_effect('walk', "Magic Boost")
    print_creature_details(goblin)

# ... rest of the script remains the same

if __name__ == "__main__":
    test_grappled_condition()