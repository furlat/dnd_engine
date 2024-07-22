from dnd.actions import PrerequisiteDetails, ActionLog, ActionResultDetails

def print_log_details(log):
    # Handle PrerequisiteDetails specifically
    if isinstance(log, PrerequisiteDetails):
        print("Prerequisite Details:")
        for field, value in log.model_dump().items():
            if value is not None:
                print(f"  {field.capitalize().replace('_', ' ')}: {value}")
        print()
        return

    # Handle ActionLog specifically
    if isinstance(log, ActionLog):
        print(f"Log Type: {log.log_type}")
        print(f"Action Name: {log.action_name}")
        print(f"Timestamp: {log.timestamp}")
        print(f"Source ID: {log.source_entity_id}")
        print(f"Target ID: {log.target_entity_id}")
        print(f"Success: {log.success}")
        
        if log.result_details:
            print("Result Details:")
            print(f"  Success: {log.result_details.success}")
            print(f"  Reason: {log.result_details.reason}")
            print(f"  Effects: {log.result_details.effects}")
        
        if log.prerequisite_logs:
            print("Prerequisite Logs:")
            for prereq_name, prereq_log in log.prerequisite_logs.items():
                print(f"  {prereq_name}:")
                print(f"    Passed: {prereq_log.passed}")
                print(f"    Details: {prereq_log.details.model_dump()}")
        
        if log.dice_rolls:
            print("Dice Rolls:")
            for roll in log.dice_rolls:
                print_log_details(roll)
        
        if log.damage_rolls:
            print("Damage Rolls:")
            for roll in log.damage_rolls:
                print_log_details(roll)
        
        print()
        return

    # Original logic for other log types
    if hasattr(log, 'log_type'):
        print(f"Log Type: {log.log_type}")
    if hasattr(log, 'timestamp'):
        print(f"Timestamp: {log.timestamp}")
    if hasattr(log, 'source_entity_id'):
        print(f"Source ID: {log.source_entity_id}")
    if hasattr(log, 'target_entity_id'):
        print(f"Target ID: {log.target_entity_id}")
    
    if hasattr(log, 'condition'):
        print(f"Condition: {log.condition}")
    if hasattr(log, 'condition_name'):
        print(f"Condition: {log.condition_name}")
    if hasattr(log, 'details'):
        print(f"Details: {log.details}")
    if hasattr(log, 'duration'):
        print(f"Duration: {log.duration}")
    if hasattr(log, 'removed_reason'):
        print(f"Removed Reason: {log.removed_reason}")
    
    if hasattr(log, 'skill'):
        print(f"Skill: {log.skill}")
    if hasattr(log, 'ability'):
        print(f"Ability: {log.ability}")
    if hasattr(log, 'dc'):
        print(f"DC: {log.dc}")
    if hasattr(log, 'roll'):
        print(f"Roll: {log.roll.total_roll}")
        print(f"Base Roll: {log.roll.base_roll.result}")
        print(f"Advantage Status: {log.roll.bonus.advantage_tracker.status}")
        print(f"AutoHit Status: {log.roll.bonus.auto_hit_tracker.status}")
        print(f"Critical Status: {log.roll.bonus.critical_tracker.status}")
        print(f"Hit: {log.roll.hit}")
        print(f"Hit Reason: {log.roll.hit_reason}")
        if log.roll.critical_reason:
            print(f"Critical Reason: {log.roll.critical_reason}")
        print(f"Success: {log.roll.success}")
    
    if hasattr(log, 'hand'):
        print(f"Attack Hand: {log.hand}")
    if hasattr(log, 'attack_type'):
        print(f"Attack Type: {log.attack_type}")
    if hasattr(log, 'total_target_ac'):
        print(f"Target AC: {log.total_target_ac}")
    
    if hasattr(log, 'damage_type'):
        print(f"Damage Type: {log.damage_type}")
    if hasattr(log, 'total_damage'):
        print(f"Total Damage: {log.total_damage}")
    
    print()