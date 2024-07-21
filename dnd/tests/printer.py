
def print_log_details(log):
    print(f"Log Type: {log.log_type}")
    print(f"Timestamp: {log.timestamp}")
    print(f"Source ID: {log.source_entity_id}")
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


