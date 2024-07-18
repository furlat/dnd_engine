from datetime import datetime, timedelta
from dnd.dnd_enums import (AdvantageStatus, AttackType, DamageType, Ability)
from dnd.newlogs import SourceType, ConditionInfo, EffectSource, AdvantageSource, DisadvantageSource, Modifier, DiceRollLog, HitRollLog, DamageRollLog, AttackLog, HealthChangeLog, AttackResult, DamageLog, DamageTypeEffect
# Example 1: Basic successful attack
basic_attack = AttackLog(
    entity_id="ATK001",
    source_entity_id="Goblin",
    target_entity_id="Skeleton",
    weapon_name="Scimitar",
    attack_type=AttackType.MELEE_WEAPON,
    attacker_conditions=[],
    target_conditions=[],
    hit_roll_log=HitRollLog(
        entity_id="Goblin",
        dice_roll=DiceRollLog(
            entity_id="Goblin",
            dice_size=20,
            roll_results=[15],
            modifiers=[Modifier(value=3, effect_source=EffectSource(
                source_type=SourceType.ABILITY,
                responsible_entity_id="Goblin",
                ability_name="DEX",
                description="DEX modifier"
            ))],
            advantage_status=AdvantageStatus.NONE,
            advantage_sources=[],
            disadvantage_sources=[],
            total_roll=18,
            is_critical=False
        ),
        target_ac=13,
        is_hit=True
    ),
    damage_log=DamageLog(
        entity_id="Goblin",
        damage_rolls=[DamageRollLog(
            entity_id="Goblin",
            damage_type=DamageType.SLASHING,
            dice_roll=DiceRollLog(
                entity_id="Goblin",
                dice_size=6,
                roll_results=[3],
                modifiers=[Modifier(value=2, effect_source=EffectSource(
                    source_type=SourceType.ABILITY,
                    responsible_entity_id="Goblin",
                    ability_name="DEX",
                    description="DEX modifier"
                ))],
                advantage_status=AdvantageStatus.NONE,
                advantage_sources=[],
                disadvantage_sources=[],
                total_roll=5
            )
        )],
        total_damage_by_type={DamageType.SLASHING: 5},
        final_damage=5
    ),
    health_change_log=HealthChangeLog(
        entity_id="Skeleton",
        target_max_hp=13,
        target_previous_hp=13,
        target_previous_temp_hp=0,
        damage_taken=5,
        temp_hp_absorbed=0,
        resistances_applied=[],
        vulnerabilities_applied=[],
        immunities_applied=[],
        target_current_hp=8,
        target_current_temp_hp=0
    ),
    final_result=AttackResult.HIT
)

# Example 2: Attack with advantage and various modifiers
complex_attack = AttackLog(
    entity_id="ATK002",
    source_entity_id="Goblin",
    target_entity_id="Skeleton",
    weapon_name="Scimitar",
    attack_type=AttackType.MELEE_WEAPON,
    attacker_conditions=[ConditionInfo(
        condition_name="Recklessness",
        affected_entity_id="Goblin",
        source_entity_id="Goblin",
        source_ability="Reckless Attack",
        start_time=datetime.now()
    )],
    target_conditions=[ConditionInfo(
        condition_name="Blinded",
        affected_entity_id="Skeleton",
        source_entity_id="Wizard",
        source_ability="Blindness/Deafness",
        start_time=datetime.now()
    )],
    hit_roll_log=HitRollLog(
        entity_id="Goblin",
        dice_roll=DiceRollLog(
            entity_id="Goblin",
            dice_size=20,
            roll_results=[13, 4],
            modifiers=[
                Modifier(value=3, effect_source=EffectSource(
                    source_type=SourceType.ABILITY,
                    responsible_entity_id="Goblin",
                    ability_name="DEX",
                    description="DEX modifier"
                )),
                Modifier(value=2, effect_source=EffectSource(
                    source_type=SourceType.CONDITION,
                    responsible_entity_id="Goblin",
                    condition_info=ConditionInfo(
                        condition_name="Recklessness",
                        affected_entity_id="Goblin",
                        source_entity_id="Goblin",
                        source_ability="Reckless Attack",
                        start_time=datetime.now()
                    ),
                    description="Recklessness bonus"
                )),
                Modifier(value=-3, effect_source=EffectSource(
                    source_type=SourceType.CONDITION,
                    responsible_entity_id="Skeleton",
                    condition_info=ConditionInfo(
                        condition_name="Aura of Terror",
                        affected_entity_id="Skeleton",
                        start_time=datetime.now()
                    ),
                    description="Aura of Terror debuff"
                ))
            ],
            advantage_status=AdvantageStatus.ADVANTAGE,
            advantage_sources=[AdvantageSource(
                effect_source=EffectSource(
                    source_type=SourceType.CONDITION,
                    responsible_entity_id="Skeleton",
                    condition_info=ConditionInfo(
                        condition_name="Blinded",
                        affected_entity_id="Skeleton",
                        source_entity_id="Wizard",
                        source_ability="Blindness/Deafness",
                        start_time=datetime.now()
                    ),
                    description="Target is blinded"
                ),
                description="Advantage against blinded targets"
            )],
            disadvantage_sources=[],
            total_roll=15,
            is_critical=False
        ),
        target_ac=13,
        is_hit=True
    ),
    damage_log=DamageLog(
        entity_id="Goblin",
        damage_rolls=[DamageRollLog(
            entity_id="Goblin",
            damage_type=DamageType.SLASHING,
            dice_roll=DiceRollLog(
                entity_id="Goblin",
                dice_size=6,
                roll_results=[5],
                modifiers=[Modifier(value=2, effect_source=EffectSource(
                    source_type=SourceType.ABILITY,
                    responsible_entity_id="Goblin",
                    ability_name="DEX",
                    description="DEX modifier"
                ))],
                advantage_status=AdvantageStatus.NONE,
                advantage_sources=[],
                disadvantage_sources=[],
                total_roll=7
            )
        )],
        total_damage_by_type={DamageType.SLASHING: 7},
        final_damage=7
    ),
    health_change_log=HealthChangeLog(
        entity_id="Skeleton",
        target_max_hp=13,
        target_previous_hp=13,
        target_previous_temp_hp=0,
        damage_taken=7,
        temp_hp_absorbed=0,
        resistances_applied=[],
        vulnerabilities_applied=[],
        immunities_applied=[],
        target_current_hp=6,
        target_current_temp_hp=0
    ),
    final_result=AttackResult.HIT
)

# Example 3: Critical hit with multiple damage types
critical_hit = AttackLog(
    entity_id="ATK003",
    source_entity_id="Paladin",
    target_entity_id="Zombie",
    weapon_name="Flaming Longsword",
    attack_type=AttackType.MELEE_WEAPON,
    attacker_conditions=[],
    target_conditions=[],
    hit_roll_log=HitRollLog(
        entity_id="Paladin",
        dice_roll=DiceRollLog(
            entity_id="Paladin",
            dice_size=20,
            roll_results=[20],
            modifiers=[Modifier(value=5, effect_source=EffectSource(
                source_type=SourceType.ABILITY,
                responsible_entity_id="Paladin",
                ability_name="STR",
                description="STR modifier"
            ))],
            advantage_status=AdvantageStatus.NONE,
            advantage_sources=[],
            disadvantage_sources=[],
            total_roll=25,
            is_critical=True
        ),
        target_ac=12,
        is_hit=True
    ),
    damage_log=DamageLog(
        entity_id="Paladin",
        damage_rolls=[
            DamageRollLog(
                entity_id="Paladin",
                damage_type=DamageType.SLASHING,
                dice_roll=DiceRollLog(
                    entity_id="Paladin",
                    dice_size=8,
                    roll_results=[6, 5],
                    modifiers=[Modifier(value=3, effect_source=EffectSource(
                        source_type=SourceType.ABILITY,
                        responsible_entity_id="Paladin",
                        ability_name="STR",
                        description="STR modifier"
                    ))],
                    advantage_status=AdvantageStatus.NONE,
                    advantage_sources=[],
                    disadvantage_sources=[],
                    total_roll=14
                )
            ),
            DamageRollLog(
                entity_id="Paladin",
                damage_type=DamageType.FIRE,
                dice_roll=DiceRollLog(
                    entity_id="Paladin",
                    dice_size=6,
                    roll_results=[5, 3],
                    modifiers=[],
                    advantage_status=AdvantageStatus.NONE,
                    advantage_sources=[],
                    disadvantage_sources=[],
                    total_roll=8
                )
            )
        ],
        total_damage_by_type={DamageType.SLASHING: 14, DamageType.FIRE: 8},
        final_damage=22
    ),
    health_change_log=HealthChangeLog(
        entity_id="Zombie",
        target_max_hp=22,
        target_previous_hp=22,
        target_previous_temp_hp=0,
        damage_taken=15,
        temp_hp_absorbed=0,
        resistances_applied=[DamageTypeEffect(
            damage_type=DamageType.SLASHING,
            effect_source=EffectSource(
                source_type=SourceType.ABILITY,
                responsible_entity_id="Zombie",
                ability_name="Undead Fortitude",
                description="Resistance to slashing damage"
            )
        )],
        vulnerabilities_applied=[],
        immunities_applied=[],
        target_current_hp=7,
        target_current_temp_hp=0
    ),
    final_result=AttackResult.CRITICAL_HIT
)

# Example 4: Miss due to disadvantage
disadvantage_miss = AttackLog(
    entity_id="ATK004",
    source_entity_id="Fighter",
    target_entity_id="Gelatinous Cube",
    weapon_name="Longsword",
    attack_type=AttackType.MELEE_WEAPON,
    attacker_conditions=[ConditionInfo(
        condition_name="Underwater",
        affected_entity_id="Fighter",
        source_entity_id="Environment",
        start_time=datetime.now()
    )],
    target_conditions=[],
    hit_roll_log=HitRollLog(
        entity_id="Fighter",
        dice_roll=DiceRollLog(
            entity_id="Fighter",
            dice_size=20,
            roll_results=[12, 7],
            modifiers=[
                Modifier(value=4, effect_source=EffectSource(
                    source_type=SourceType.ABILITY,
                    responsible_entity_id="Fighter",
                    ability_name="STR",
                    description="STR modifier"
                )),
                Modifier(value=1, effect_source=EffectSource(
                    source_type=SourceType.ITEM,
                    responsible_entity_id="Fighter",
                    item_name="Weapon +1",
                    description="+1 magic weapon"
                )),
                Modifier(value=-2, effect_source=EffectSource(
                    source_type=SourceType.CONDITION,
                    responsible_entity_id="Gelatinous Cube",
                    condition_info=ConditionInfo(
                        condition_name="Obscuring Form",
                        affected_entity_id="Gelatinous Cube",
                        start_time=datetime.now()
                    ),
                    description="Obscuring form"
                ))
            ],
            advantage_status=AdvantageStatus.DISADVANTAGE,
            advantage_sources=[],
            disadvantage_sources=[DisadvantageSource(
                effect_source=EffectSource(
                    source_type=SourceType.CONDITION,
                    responsible_entity_id="Fighter",
                    condition_info=ConditionInfo(
                        condition_name="Underwater",
                        affected_entity_id="Fighter",
                        source_entity_id="Environment",
                        start_time=datetime.now()
                    ),
                    description="Underwater combat"
                ),
                description="Disadvantage on melee weapon attacks underwater"
            )],
            total_roll=10,
            is_critical=False
        ),
        target_ac=10,
        is_hit=False
    ),
    damage_log=None,
    health_change_log=None,
    final_result=AttackResult.MISS
)

print("PORCODIOO")
print("BAsic attack")
print(basic_attack.generate_log_string())
print("Complex attack")
print(complex_attack.generate_log_string())
print("Critical hit")
print(critical_hit.generate_log_string())
print("disadvantage miss")
print(disadvantage_miss.generate_log_string())