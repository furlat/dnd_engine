from dnd.contextual import ModifiableValue, ContextualEffects
from dnd.logger import Logger
from dnd.dnd_enums import AdvantageStatus
from dnd.tests.example_bm import create_battlemap_with_entities
from datetime import timedelta

def test_modifiable_value_and_logging():
    # Create a battle map with entities
    battle_map, goblin, skeleton = create_battlemap_with_entities()

    # Create a ModifiableValue instance (let's say it's the goblin's attack bonus)
    attack_bonus = ModifiableValue(base_value=2)

    # Add some effects
    attack_bonus.add_bonus("Weapon Proficiency", lambda s, t, c: 2)
    attack_bonus.add_bonus("Strength Modifier", lambda s, t, c: 1)
    attack_bonus.add_advantage_condition("Reckless Attack", lambda s, t, c: s.name == "Goblin")
    attack_bonus.add_disadvantage_condition("Frightened", lambda s, t, c: "Frightened" in s.active_conditions)

    # Test the ModifiableValue
    value, log = attack_bonus.get_value(goblin, skeleton, return_log=True)
    print(f"Attack Bonus: {value}")
    print("ModifiableValue Log:")
    print(log.model_dump_json(indent=2))

    # Add some more complex effects
    def range_check(source, target, context):
        if not (source and target):
            return False
        distance = source.get_distance(target.sensory.origin)
        return distance is not None and distance <= 5

    attack_bonus.add_auto_critical_self_condition("Paralyzed", lambda s, t, c: "Paralyzed" in t.active_conditions and range_check(s, t, c))

    value, log = attack_bonus.get_value(goblin, skeleton, return_log=True)
    print(f"Attack Bonus: {value}")
    print("ModifiableValue Log:")
    print(log.model_dump_json(indent=2))

    # Test advantage status
    adv_status, adv_log = attack_bonus.get_advantage_status(goblin, skeleton, return_log=True)
    print(f"\nAdvantage Status: {adv_status}")
    print("Advantage Status Log:")
    print(adv_log)

    # Test auto-critical
    is_crit, crit_log = attack_bonus.is_auto_critical(goblin, skeleton, return_log=True)
    print(f"\nIs Auto-Critical: {is_crit}")
    print("Auto-Critical Log:")
    print(crit_log)

    # Retrieve logs from the Logger
    recent_logs = Logger.get_logs_in_last(timedelta(minutes=5), log_type="ModifiableValue", limit=10)
    print("\nRecent Logs from Logger:")
    for log in recent_logs:
        print(log.model_dump_json(indent=2))

if __name__ == "__main__":
    
    test_modifiable_value_and_logging()