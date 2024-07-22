from typing import Dict, Any, Optional
from pydantic import Field
from dnd.core import Condition, ConditionAppliedDetails, ConditionRemovedDetails
from dnd.contextual import ContextAwareAutoHit, ModifiableValue
from dnd.dnd_enums import AdvantageStatus, AutoHitStatus, Skills,Ability,SensesType,CriticalStatus
from dnd.statsblock import StatsBlock

class Blinded(Condition):
    name: str = "Blinded"
    description: str = "A blinded creature can't see and automatically fails any ability check that requires sight. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage."

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Add disadvantage to all attacks (static)
        stats_block.attacks_manager.hit_bonus.self_static.add_advantage_condition("Blinded", AdvantageStatus.DISADVANTAGE)
        
        # Give advantage to all attacks against this creature (static)
        stats_block.armor_class.ac.target_static.add_advantage_condition("Blinded", AdvantageStatus.ADVANTAGE)

        # Add auto-fail condition for sight-based ability checks (contextual)
        for skill in Skills:
            skill_obj = stats_block.skillset.get_skill(skill)
            skill_obj.bonus.self_contextual.add_auto_hit_condition("Blinded", self.blinded_sight_check)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        # Remove effects
        stats_block.attacks_manager.hit_bonus.remove_effect("Blinded")
        stats_block.armor_class.ac.remove_effect("Blinded")
        for skill in Skills:
            skill_obj = stats_block.skillset.get_skill(skill)
            skill_obj.bonus.remove_effect("Blinded")

        return ConditionRemovedDetails(details="Removed Blinded condition")

    @staticmethod
    def blinded_sight_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> AutoHitStatus:
        if context and context.get('requires_sight', False):
            return AutoHitStatus.AUTOMISS
        return AutoHitStatus.NONE

# Type hint for the static method

class Charmed(Condition):
    name: str = "Charmed"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Prevent attacking the charmer
        stats_block.attacks_manager.hit_bonus.self_contextual.add_auto_hit_condition("Charmed", self.charmed_attack_check)

        # Add advantage on social checks for the charmer
        social_skills = [Skills.DECEPTION, Skills.INTIMIDATION, Skills.PERFORMANCE, Skills.PERSUASION]
        for skill in social_skills:
            skill_obj = stats_block.skillset.get_skill(skill)
            skill_obj.bonus.target_contextual.add_advantage_condition("Charmed", self.charmed_social_check)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        stats_block.attacks_manager.hit_bonus.remove_effect("Charmed")
        
        social_skills = [Skills.DECEPTION, Skills.INTIMIDATION, Skills.PERFORMANCE, Skills.PERSUASION]
        for skill in social_skills:
            skill_obj = stats_block.skillset.get_skill(skill)
            skill_obj.bonus.remove_effect("Charmed")

        return ConditionRemovedDetails(details="Removed Charmed condition")

    @staticmethod
    def charmed_social_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        if target and "Charmed" in stats_block.condition_manager.active_conditions:
            charmed_condition = stats_block.condition_manager.active_conditions["Charmed"]
            if charmed_condition.source_entity_id == target.id:
                return AdvantageStatus.ADVANTAGE
        return AdvantageStatus.NONE

    @staticmethod
    def charmed_attack_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> AutoHitStatus:
        if target and "Charmed" in stats_block.condition_manager.active_conditions:
            charmed_condition = stats_block.condition_manager.active_conditions["Charmed"]
            if charmed_condition.source_entity_id == target.id:
                return AutoHitStatus.AUTOMISS
        return AutoHitStatus.NONE

    
class Dashing(Condition):
    name: str = "Dashing"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            base_speed = speed_obj.base_value.base_value
            if base_speed > 0:
                speed_obj.self_static.add_bonus("Dashing", base_speed)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            speed_obj.remove_effect("Dashing")

        return ConditionRemovedDetails(details="Removed Dashing condition")
    

class Deafened(Condition):
    name: str = "Deafened"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Add auto-fail condition for hearing-based ability checks
        for skill in Skills:
            skill_obj = stats_block.skillset.get_skill(skill)
            skill_obj.bonus.self_contextual.add_auto_hit_condition("Deafened", self.deafened_hearing_check)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        for skill in Skills:
            skill_obj = stats_block.skillset.get_skill(skill)
            skill_obj.bonus.remove_effect("Deafened")

        return ConditionRemovedDetails(details="Removed Deafened condition")

    @staticmethod
    def deafened_hearing_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> AutoHitStatus:
        if context and context.get('requires_hearing', False):
            return AutoHitStatus.AUTOMISS
        return AutoHitStatus.NONE

    
    
class Dodging(Condition):
    name: str = "Dodging"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Add disadvantage to attacks against this creature
        stats_block.armor_class.ac.target_static.add_advantage_condition("Dodging", AdvantageStatus.DISADVANTAGE)
        
        # Add advantage to Dexterity saving throws
        dex_save = stats_block.saving_throws.get_ability(Ability.DEX)
        dex_save.bonus.self_static.add_advantage_condition("Dodging", AdvantageStatus.ADVANTAGE)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        stats_block.armor_class.ac.remove_effect("Dodging")
        dex_save = stats_block.saving_throws.get_ability(Ability.DEX)
        dex_save.bonus.remove_effect("Dodging")

        return ConditionRemovedDetails(details="Removed Dodging condition")

class Frightened(Condition):
    name: str = "Frightened"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Add disadvantage to all attacks
        stats_block.attacks_manager.hit_bonus.self_contextual.add_advantage_condition("Frightened", self.frightened_check)
        
        # Add disadvantage to all ability checks
        for ability in Ability:
            ability_score = stats_block.ability_scores.get_ability(ability)
            ability_score.score.self_contextual.add_advantage_condition("Frightened", self.frightened_check)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        stats_block.attacks_manager.hit_bonus.remove_effect("Frightened")
        for ability in Ability:
            ability_score = stats_block.ability_scores.get_ability(ability)
            ability_score.score.remove_effect("Frightened")

        return ConditionRemovedDetails(details="Removed Frightened condition")

    @staticmethod
    def frightened_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        if "Frightened" in stats_block.condition_manager.active_conditions:
            frightened_condition = stats_block.condition_manager.active_conditions["Frightened"]
            frightening_entity = frightened_condition.source_entity_id
            frightening_block : StatsBlock = StatsBlock.get_instance(frightening_entity)
            if frightening_entity and stats_block.sensory.is_visible(frightening_block.sensory.origin):
                return AdvantageStatus.DISADVANTAGE
        return AdvantageStatus.NONE

class Grappled(Condition):
    name: str = "Grappled"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            speed_obj.self_static.add_max_constraint("Grappled", 0)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            speed_obj.remove_effect("Grappled")

        return ConditionRemovedDetails(details="Removed Grappled condition")

class Incapacitated(Condition):
    name: str = "Incapacitated"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Set max actions, bonus actions, and reactions to 0
        stats_block.action_economy.actions.self_static.add_max_constraint("Incapacitated", 0)
        stats_block.action_economy.bonus_actions.self_static.add_max_constraint("Incapacitated", 0)
        stats_block.action_economy.reactions.self_static.add_max_constraint("Incapacitated", 0)

        # Set max speed to 0 for all movement types
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj = getattr(stats_block.speed, speed_type)
            speed_obj.self_static.add_max_constraint("Incapacitated", 0)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        # Remove constraints from action economy
        stats_block.action_economy.actions.remove_effect("Incapacitated")
        stats_block.action_economy.bonus_actions.remove_effect("Incapacitated")
        stats_block.action_economy.reactions.remove_effect("Incapacitated")

        # Remove constraints from speed
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj = getattr(stats_block.speed, speed_type)
            speed_obj.remove_effect("Incapacitated")

        return ConditionRemovedDetails(details="Removed Incapacitated condition")

class Invisible(Condition):
    name: str = "Invisible"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Add advantage to all attacks
        stats_block.attacks_manager.hit_bonus.self_contextual.add_advantage_condition("Invisible", self.invisible_offensive_check)
        
        # Give disadvantage to all attacks against this creature
        stats_block.armor_class.ac.target_contextual.add_advantage_condition("Invisible", self.invisible_defensive_check)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        stats_block.attacks_manager.hit_bonus.remove_effect("Invisible")
        stats_block.armor_class.ac.remove_effect("Invisible")

        return ConditionRemovedDetails(details="Removed Invisible condition")

    @staticmethod
    def can_see_invisible(observer: StatsBlock) -> bool:
        observer_senses = {sense.type for sense in observer.sensory.senses}
        return SensesType.TRUESIGHT in observer_senses or SensesType.TREMORSENSE in observer_senses

    @staticmethod
    def invisible_offensive_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        if target is None or "Invisible" not in stats_block.condition_manager.active_conditions:
            return AdvantageStatus.NONE
        if Invisible.can_see_invisible(target) and target.sensory.is_visible(stats_block.sensory.origin):
            return AdvantageStatus.NONE
        return AdvantageStatus.ADVANTAGE

    @staticmethod
    def invisible_defensive_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        if target is None or "Invisible" not in stats_block.condition_manager.active_conditions:
            return AdvantageStatus.NONE
        if Invisible.can_see_invisible(target) and target.sensory.is_visible(stats_block.sensory.origin):
            return AdvantageStatus.NONE
        return AdvantageStatus.DISADVANTAGE
    
class Paralyzed(Condition):
    name: str = "Paralyzed"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Set max actions, bonus actions, and reactions to 0
        stats_block.action_economy.actions.self_static.add_max_constraint("Paralyzed", 0)
        stats_block.action_economy.bonus_actions.self_static.add_max_constraint("Paralyzed", 0)
        stats_block.action_economy.reactions.self_static.add_max_constraint("Paralyzed", 0)

        # Set max speed to 0 for all movement types
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            speed_obj.self_static.add_max_constraint("Paralyzed", 0)

        # Auto-fail STR and DEX saves
        stats_block.saving_throws.get_ability(Ability.STR).bonus.self_static.add_auto_hit_condition("Paralyzed", AutoHitStatus.AUTOMISS)
        stats_block.saving_throws.get_ability(Ability.DEX).bonus.self_static.add_auto_hit_condition("Paralyzed", AutoHitStatus.AUTOMISS)

        # Auto-critical for attacks within 5 feet
        stats_block.armor_class.ac.target_contextual.add_critical_condition("Paralyzed", self.paralyzed_attack_check)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        # Remove all effects
        stats_block.action_economy.actions.remove_effect("Paralyzed")
        stats_block.action_economy.bonus_actions.remove_effect("Paralyzed")
        stats_block.action_economy.reactions.remove_effect("Paralyzed")
        
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            speed_obj.remove_effect("Paralyzed")
        
        stats_block.saving_throws.get_ability(Ability.STR).bonus.remove_effect("Paralyzed")
        stats_block.saving_throws.get_ability(Ability.DEX).bonus.remove_effect("Paralyzed")
        
        stats_block.armor_class.ac.remove_effect("Paralyzed")

        return ConditionRemovedDetails(details="Removed Paralyzed condition")

    @staticmethod
    def paralyzed_attack_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> CriticalStatus:
        if target is None or "Paralyzed" not in stats_block.condition_manager.active_conditions:
            return CriticalStatus.NONE
        distance = stats_block.sensory.get_distance(target.sensory.origin)
        if distance is not None and distance <= 5:  # 5 feet for melee range
            return CriticalStatus.AUTOCRIT
        return CriticalStatus.NONE
    
class Poisoned(Condition):
    name: str = "Poisoned"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Add disadvantage to all attacks
        stats_block.attacks_manager.hit_bonus.self_static.add_advantage_condition("Poisoned", AdvantageStatus.DISADVANTAGE)
        
        # Add disadvantage to all ability checks (which includes skill checks)
        for skill in Skills:
            skill_obj = stats_block.skillset.get_skill(skill)
            skill_obj.bonus.self_static.add_advantage_condition("Poisoned", AdvantageStatus.DISADVANTAGE)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        # Remove disadvantage from all attacks
        stats_block.attacks_manager.hit_bonus.remove_effect("Poisoned")
        
        # Remove disadvantage from all ability checks
        for skill in Skills:
            skill_obj = stats_block.skillset.get_skill(skill)
            skill_obj.bonus.remove_effect("Poisoned")

        return ConditionRemovedDetails(details="Removed Poisoned condition")
    

class Prone(Condition):
    name: str = "Prone"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Disadvantage on attack rolls for the prone creature
        stats_block.attacks_manager.hit_bonus.self_static.add_advantage_condition("Prone", AdvantageStatus.DISADVANTAGE)
        
        # Advantage on melee attacks within 5 feet, disadvantage from ranged attacks
        stats_block.armor_class.ac.target_contextual.add_advantage_condition("Prone", self.prone_attack_check)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        # Remove disadvantage on attack rolls
        stats_block.attacks_manager.hit_bonus.remove_effect("Prone")
        
        # Remove advantage/disadvantage conditions from armor class
        stats_block.armor_class.ac.remove_effect("Prone")

        return ConditionRemovedDetails(details="Removed Prone condition")

    @staticmethod
    def prone_attack_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        if target is None or "Prone" not in stats_block.condition_manager.active_conditions:
            return AdvantageStatus.NONE
        distance = stats_block.sensory.get_distance(target.sensory.origin)
        if distance is not None and distance <= 5:  # 5 feet for melee range
            return AdvantageStatus.ADVANTAGE
        elif distance is None or distance > 5:  # More than 5 feet for ranged attacks
            return AdvantageStatus.DISADVANTAGE
        return AdvantageStatus.NONE
    

class Stunned(Condition):
    name: str = "Stunned"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Incapacitated effects (can't take actions or reactions)
        stats_block.action_economy.actions.self_static.add_max_constraint("Stunned", 0)
        stats_block.action_economy.bonus_actions.self_static.add_max_constraint("Stunned", 0)
        stats_block.action_economy.reactions.self_static.add_max_constraint("Stunned", 0)
        
        # Can't move
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            speed_obj.self_static.add_max_constraint("Stunned", 0)
        
        # Auto-fail STR and DEX saves
        stats_block.saving_throws.get_ability(Ability.STR).bonus.self_static.add_auto_hit_condition("Stunned", AutoHitStatus.AUTOMISS)
        stats_block.saving_throws.get_ability(Ability.DEX).bonus.self_static.add_auto_hit_condition("Stunned", AutoHitStatus.AUTOMISS)
        
        # Advantage on attacks against this creature
        stats_block.armor_class.ac.target_static.add_advantage_condition("Stunned", AdvantageStatus.ADVANTAGE)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        # Remove all effects
        stats_block.action_economy.actions.remove_effect("Stunned")
        stats_block.action_economy.bonus_actions.remove_effect("Stunned")
        stats_block.action_economy.reactions.remove_effect("Stunned")
        
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            speed_obj.remove_effect("Stunned")
        
        stats_block.saving_throws.get_ability(Ability.STR).bonus.remove_effect("Stunned")
        stats_block.saving_throws.get_ability(Ability.DEX).bonus.remove_effect("Stunned")
        
        stats_block.armor_class.ac.remove_effect("Stunned")

        return ConditionRemovedDetails(details="Removed Stunned condition")


class Restrained(Condition):
    name: str = "Restrained"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Set speed to 0 for all movement types
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            speed_obj.self_static.add_max_constraint("Restrained", 0)
        
        # Add disadvantage to all attacks
        stats_block.attacks_manager.hit_bonus.self_static.add_advantage_condition("Restrained", AdvantageStatus.DISADVANTAGE)
        
        # Add disadvantage to Dexterity saving throws
        dex_save = stats_block.saving_throws.get_ability(Ability.DEX)
        dex_save.bonus.self_static.add_advantage_condition("Restrained", AdvantageStatus.DISADVANTAGE)

        # Add advantage to attacks against this creature
        stats_block.armor_class.ac.target_static.add_advantage_condition("Restrained", AdvantageStatus.ADVANTAGE)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        # Remove all effects
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj : ModifiableValue = getattr(stats_block.speed, speed_type)
            speed_obj.remove_effect("Restrained")
        
        stats_block.attacks_manager.hit_bonus.remove_effect("Restrained")
        
        dex_save = stats_block.saving_throws.get_ability(Ability.DEX)
        dex_save.bonus.remove_effect("Restrained")

        stats_block.armor_class.ac.remove_effect("Restrained")

        return ConditionRemovedDetails(details="Removed Restrained condition")

class Unconscious(Condition):
    name: str = "Unconscious"

    def _apply(self, stats_block: StatsBlock) -> ConditionAppliedDetails:
        # Incapacitated effects (can't take actions or reactions)
        stats_block.action_economy.actions.self_static.add_max_constraint("Unconscious", 0)
        stats_block.action_economy.bonus_actions.self_static.add_max_constraint("Unconscious", 0)
        stats_block.action_economy.reactions.self_static.add_max_constraint("Unconscious", 0)
        
        # Can't move
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj = getattr(stats_block.speed, speed_type)
            speed_obj.self_static.add_max_constraint("Unconscious", 0)
        
        # Auto-fail STR and DEX saves
        stats_block.saving_throws.get_ability(Ability.STR).bonus.self_static.add_auto_hit_condition("Unconscious", AutoHitStatus.AUTOMISS)
        stats_block.saving_throws.get_ability(Ability.DEX).bonus.self_static.add_auto_hit_condition("Unconscious", AutoHitStatus.AUTOMISS)
        
        # Advantage on attacks against
        stats_block.armor_class.ac.target_static.add_advantage_condition("Unconscious", AdvantageStatus.ADVANTAGE)
        
        # Critical hit on attacks within 5 feet
        stats_block.armor_class.ac.target_contextual.add_critical_condition("Unconscious", self.unconscious_melee_check)

        # Apply Prone-like effects
        stats_block.attacks_manager.hit_bonus.self_static.add_advantage_condition("Unconscious", AdvantageStatus.DISADVANTAGE)
        stats_block.armor_class.ac.target_contextual.add_advantage_condition("Unconscious", self.unconscious_prone_check)

        return ConditionAppliedDetails(
            condition_name=self.name,
            source_entity_id=self.source_entity_id,
            source_ability=self.source_ability
        )

    def _remove(self) -> ConditionRemovedDetails:
        stats_block = self.get_target(self.targeted_entity_id)
        
        # Remove all effects
        stats_block.action_economy.actions.remove_effect("Unconscious")
        stats_block.action_economy.bonus_actions.remove_effect("Unconscious")
        stats_block.action_economy.reactions.remove_effect("Unconscious")
        
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj = getattr(stats_block.speed, speed_type)
            speed_obj.remove_effect("Unconscious")
        
        stats_block.saving_throws.get_ability(Ability.STR).bonus.remove_effect("Unconscious")
        stats_block.saving_throws.get_ability(Ability.DEX).bonus.remove_effect("Unconscious")
        
        stats_block.armor_class.ac.remove_effect("Unconscious")
        stats_block.attacks_manager.hit_bonus.remove_effect("Unconscious")

        return ConditionRemovedDetails(details="Removed Unconscious condition")

    @staticmethod
    def unconscious_melee_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> CriticalStatus:
        if target is None or "Unconscious" not in stats_block.condition_manager.active_conditions:
            return CriticalStatus.NONE
        distance = stats_block.sensory.get_distance(target.sensory.origin)
        if distance is not None and distance <= 5:  # 5 feet for melee range
            return CriticalStatus.AUTOCRIT
        return CriticalStatus.NONE

    @staticmethod
    def unconscious_prone_check(stats_block: StatsBlock, target: Optional[StatsBlock], context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        if target is None or "Unconscious" not in stats_block.condition_manager.active_conditions:
            return AdvantageStatus.NONE
        distance = stats_block.sensory.get_distance(target.sensory.origin)
        if distance is not None and distance <= 5:  # 5 feet for melee range
            return AdvantageStatus.ADVANTAGE
        elif distance is None or distance > 5:  # More than 5 feet for ranged attacks
            return AdvantageStatus.DISADVANTAGE
        return AdvantageStatus.NONE

