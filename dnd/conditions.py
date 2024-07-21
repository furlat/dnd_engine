from typing import Dict, Any, Optional
from pydantic import Field
from dnd.core import Condition, ConditionAppliedDetails, ConditionRemovedDetails
from dnd.contextual import ContextAwareAutoHit, ModifiableValue
from dnd.dnd_enums import AdvantageStatus, AutoHitStatus, Skills,Ability
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

# class Incapacitated(Condition):
#     name: str = "Incapacitated"

#     def apply(self, stats_block: 'StatsBlock') -> None:
#         print(f"Applying Incapacitated condition to {stats_block.name}")
#         stats_block.action_economy.set_max_actions("Incapacitated", 0)
#         stats_block.action_economy.set_max_bonus_actions("Incapacitated", 0)
#         stats_block.action_economy.set_max_reactions("Incapacitated", 0)

#     def remove(self, stats_block: 'StatsBlock') -> None:
#         print(f"Removing Incapacitated condition from {stats_block.name}")
#         stats_block.action_economy.reset_max_actions("Incapacitated")
#         stats_block.action_economy.reset_max_bonus_actions("Incapacitated")
#         stats_block.action_economy.reset_max_reactions("Incapacitated")

# class Invisible(Condition):
#     name: str = "Invisible"

#     def apply(self, stats_block: 'StatsBlock') -> None:
#         print(f"Applying Invisible condition to {stats_block.name}")
        
#         # Add advantage to all attacks
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.add_contextual_advantage("Invisible", self.invisible_offensive_check)
        
#         # Give disadvantage to all attacks against this creature
#         stats_block.armor_class.add_opponent_disadvantage_condition("Invisible", self.invisible_defensive_check)

#     def remove(self, stats_block: 'StatsBlock') -> None:
#         print(f"Removing Invisible condition from {stats_block.name}")
        
#         # Remove advantage from all attacks
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.remove_effect("Invisible")
        
#         # Remove disadvantage from all attacks against this creature
#         stats_block.armor_class.remove_opponent_disadvantage_condition("Invisible")

#     @staticmethod
#     def can_see_invisible(observer: 'StatsBlock', target: 'StatsBlock') -> bool:
#         observer_senses = {sense.type for sense in observer.sensory.senses}
#         return SensesType.TRUESIGHT in observer_senses or SensesType.TREMORSENSE in observer_senses

#     @staticmethod
#     def invisible_offensive_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         if target is None:
#             print("No target provided for invisible check")
#             return True  # If no target, assume advantage applies
#         if Invisible.can_see_invisible(target, source) and target.is_visible(source.sensory.origin):
#             print(f"{target.name} can see invisible {source.name}")
#             return False
#         print(f"{target.name} cannot see invisible {source.name}")
#         return True
    
#     @staticmethod
#     def invisible_defensive_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         if target is None:
#             print("No target provided for invisible check")
#             return True  # If no target, assume advantage applies
#         if Invisible.can_see_invisible(source, target) and source.is_visible(target.sensory.origin):
#             print(f"{source.name} can see invisible {target.name}")
#             return False
#         print(f"{source.name} cannot see invisible {target.name}")
#         return True
    
# class Paralyzed(Condition):
#     name: str = "Paralyzed"

#     def apply(self, stats_block: 'StatsBlock') -> None:
#         print(f"Applying Paralyzed condition to {stats_block.name}")
        
#         # Incapacitated effects (can't take actions or reactions)
#         stats_block.action_economy.set_max_actions("Paralyzed", 0)
#         stats_block.action_economy.set_max_bonus_actions("Paralyzed", 0)
#         stats_block.action_economy.set_max_reactions("Paralyzed", 0)
        
#         # Can't move
#         stats_block.speed.set_max_speed_to_zero("Paralyzed")
        
#         # Auto-fail STR and DEX saves
#         stats_block.saving_throws.get_ability(Ability.STR).add_auto_fail_condition("Paralyzed", self.paralyzed_check)
#         stats_block.saving_throws.get_ability(Ability.DEX).add_auto_fail_condition("Paralyzed", self.paralyzed_check)
        
#         # Any attack that hits the creature is a critical hit if the attacker is within 5 feet of the creature
#         stats_block.armor_class.add_opponent_auto_critical_condition("Paralyzed", self.paralyzed_attack_check)

#     def remove(self, stats_block: 'StatsBlock') -> None:
#         print(f"Removing Paralyzed condition from {stats_block.name}")
        
#         # Remove Incapacitated effects
#         stats_block.action_economy.reset_max_actions("Paralyzed")
#         stats_block.action_economy.reset_max_bonus_actions("Paralyzed")
#         stats_block.action_economy.reset_max_reactions("Paralyzed")
        
#         # Remove movement restriction
#         stats_block.speed.reset_max_speed("Paralyzed")
        
#         # Remove auto-fail on STR and DEX saves
#         stats_block.saving_throws.get_ability(Ability.STR).remove_effect("Paralyzed")
#         stats_block.saving_throws.get_ability(Ability.DEX).remove_effect("Paralyzed")
        
#         # Remove auto-critical condition
#         stats_block.armor_class.remove_opponent_auto_critical_condition("Paralyzed")

#     @staticmethod
#     def paralyzed_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         return True  # Always apply the effect when paralyzed
    
#     @staticmethod
#     def paralyzed_attack_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         if target is None or source is None:
#             return False
#         distance = source.get_distance(target.sensory.origin)
#         return distance is not None and distance <= 5  # 5 feet for melee range
    
# class Poisoned(Condition):
#     name: str = "Poisoned"

#     def apply(self, stats_block: 'StatsBlock') -> None:
#         print(f"Applying Poisoned condition to {stats_block.name}")
        
#         # Add disadvantage to all attacks
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.hit_bonus.self_effects.add_disadvantage_condition("Poisoned", self.poisoned_check)
        
#         # Add disadvantage to all ability checks (which includes skill checks)
#         for skill in Skills:
#             skill_obj = stats_block.skills.get_skill(skill)
#             skill_obj.bonus.self_effects.add_disadvantage_condition("Poisoned", self.poisoned_check)

#     def remove(self, stats_block: 'StatsBlock') -> None:
#         print(f"Removing Poisoned condition from {stats_block.name}")
        
#         # Remove disadvantage from all attacks
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.hit_bonus.self_effects.remove_effect("Poisoned")
        
#         # Remove disadvantage from all ability checks
#         for skill in Skills:
#             skill_obj = stats_block.skills.get_skill(skill)
#             skill_obj.bonus.self_effects.remove_effect("Poisoned")

#     @staticmethod
#     def poisoned_check(source: 'StatsBlock', target: Optional['StatsBlock'] = None,  context: Optional[Dict[str, Any]] = None) -> bool:
#         return True  # Always apply disadvantage when poisoned
    

# class Prone(Condition):
#     name: str = "Prone"

#     def apply(self, stats_block: 'StatsBlock') -> None:
#         print(f"Applying Prone condition to {stats_block.name}")
        
#         # Disadvantage on attack rolls
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.add_contextual_disadvantage("Prone", self.prone_attack_check)
        
#         # Advantage on melee attacks within 5 feet, disadvantage on attacks from more than 10 feet
#         stats_block.armor_class.add_opponent_advantage_condition("Prone", self.prone_melee_advantage_check)
#         stats_block.armor_class.add_opponent_disadvantage_condition("Prone", self.prone_ranged_disadvantage_check)

#     def remove(self, stats_block: 'StatsBlock') -> None:
#         print(f"Removing Prone condition from {stats_block.name}")
        
#         # Remove disadvantage on attack rolls
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.remove_effect("Prone")
        
#         # Remove advantage and disadvantage conditions from armor class
#         stats_block.armor_class.remove_opponent_advantage_condition("Prone")
#         stats_block.armor_class.remove_opponent_disadvantage_condition("Prone")

#     @staticmethod
#     def prone_attack_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         return True  # Always apply disadvantage to own attacks when prone

#     @staticmethod
#     def prone_melee_advantage_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         if target is None or source is None:
#             return False
#         distance = source.get_distance(target.sensory.origin)
#         return distance is not None and distance <= 5  # 5 feet for melee range

#     @staticmethod
#     def prone_ranged_disadvantage_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         if target is None or source is None:
#             return False
#         distance = source.get_distance(target.sensory.origin)
#         return distance is None or distance > 10  # More than 10 feet for ranged attacks
    

# class Stunned(Condition):
#     name: str = "Stunned"

#     def apply(self, stats_block: 'StatsBlock') -> None:
#         print(f"Applying Stunned condition to {stats_block.name}")
        
#         # Incapacitated effects (can't take actions or reactions)
#         stats_block.action_economy.set_max_actions("Stunned", 0)
#         stats_block.action_economy.set_max_bonus_actions("Stunned", 0)
#         stats_block.action_economy.set_max_reactions("Stunned", 0)
        
#         # Can't move
#         stats_block.speed.set_max_speed_to_zero("Stunned")
        
#         # Auto-fail STR and DEX saves
#         stats_block.saving_throws.get_ability(Ability.STR).add_auto_fail_condition("Stunned", self.stunned_check)
#         stats_block.saving_throws.get_ability(Ability.DEX).add_auto_fail_condition("Stunned", self.stunned_check)
        
#         # Advantage on attacks against this creature
#         stats_block.armor_class.add_opponent_advantage_condition("Stunned", self.stunned_check)

#     def remove(self, stats_block: 'StatsBlock') -> None:
#         print(f"Removing Stunned condition from {stats_block.name}")
        
#         # Remove Incapacitated effects
#         stats_block.action_economy.reset_max_actions("Stunned")
#         stats_block.action_economy.reset_max_bonus_actions("Stunned")
#         stats_block.action_economy.reset_max_reactions("Stunned")
        
#         # Remove movement restriction
#         stats_block.speed.reset_max_speed("Stunned")
        
#         # Remove auto-fail on STR and DEX saves
#         stats_block.saving_throws.get_ability(Ability.STR).remove_effect("Stunned")
#         stats_block.saving_throws.get_ability(Ability.DEX).remove_effect("Stunned")
        
#         # Remove advantage on attacks against this creature
#         stats_block.armor_class.remove_opponent_advantage_condition("Stunned")

#     @staticmethod
#     def stunned_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         return True  # Always apply the effect when stunned

# class Restrained(Condition):
#     name: str = "Restrained"

#     def apply(self, stats_block: 'StatsBlock') -> None:
#         print(f"Applying Restrained condition to {stats_block.name}")
        
#         # Set speed to 0
#         stats_block.speed.set_max_speed_to_zero("Restrained")
        
#         # Add disadvantage to all attacks
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.hit_bonus.self_effects.add_disadvantage_condition("Restrained", self.restrained_check)
        
#         # Add disadvantage to Dexterity saving throws
#         dex_save = stats_block.saving_throws.get_ability(Ability.DEX)
#         dex_save.bonus.self_effects.add_disadvantage_condition("Restrained", self.restrained_check)

#     def remove(self, stats_block: 'StatsBlock') -> None:
#         print(f"Removing Restrained condition from {stats_block.name}")
        
#         # Reset speed
#         stats_block.speed.reset_max_speed("Restrained")
        
#         # Remove disadvantage from all attacks
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.hit_bonus.self_effects.remove_effect("Restrained")
        
#         # Remove disadvantage from Dexterity saving throws
#         dex_save = stats_block.saving_throws.get_ability(Ability.DEX)
#         dex_save.bonus.self_effects.remove_effect("Restrained")

#     @staticmethod
#     def restrained_check(source: 'StatsBlock', target: Optional['StatsBlock'] = None,  context: Optional[Dict[str, Any]] = None) -> bool:
#         return True  # Always apply disadvantage when restrained

# class Unconscious(Condition):
#     name: str = "Unconscious"

#     def apply(self, stats_block: 'StatsBlock') -> None:
#         print(f"Applying Unconscious condition to {stats_block.name}")
        
#         # Incapacitated effects (can't take actions or reactions)
#         stats_block.action_economy.set_max_actions("Unconscious", 0)
#         stats_block.action_economy.set_max_bonus_actions("Unconscious", 0)
#         stats_block.action_economy.set_max_reactions("Unconscious", 0)
        
#         # Can't move
#         stats_block.speed.set_max_speed_to_zero("Unconscious")
        
#         # Auto-fail STR and DEX saves
#         stats_block.saving_throws.get_ability(Ability.STR).add_auto_fail_condition("Unconscious", self.unconscious_check)
#         stats_block.saving_throws.get_ability(Ability.DEX).add_auto_fail_condition("Unconscious", self.unconscious_check)
        
#         # Advantage on attacks against
#         stats_block.armor_class.add_opponent_advantage_condition("Unconscious", self.unconscious_check)
        
#         # Critical hit on attacks within 5 feet
#         stats_block.armor_class.add_opponent_auto_critical_condition("Unconscious", self.unconscious_melee_check)
        
#         # Apply Prone condition
#         # Disadvantage on attack rolls
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.add_contextual_disadvantage("Unconscious", Prone.prone_attack_check)
        
#         # Advantage on melee attacks within 5 feet, disadvantage on attacks from more than 10 feet
#         stats_block.armor_class.add_opponent_advantage_condition("Unconscious", Prone.prone_melee_advantage_check)
#         stats_block.armor_class.add_opponent_disadvantage_condition("Unconscious", Prone.prone_ranged_disadvantage_check)

#     def remove(self, stats_block: 'StatsBlock') -> None:
#         print(f"Removing Unconscious condition from {stats_block.name}")
        
#         # Remove Incapacitated effects
#         stats_block.action_economy.reset_max_actions("Unconscious")
#         stats_block.action_economy.reset_max_bonus_actions("Unconscious")
#         stats_block.action_economy.reset_max_reactions("Unconscious")
        
#         # Remove movement restriction
#         stats_block.speed.reset_max_speed("Unconscious")
        
#         # Remove auto-fail on STR and DEX saves
#         stats_block.saving_throws.get_ability(Ability.STR).remove_effect("Unconscious")
#         stats_block.saving_throws.get_ability(Ability.DEX).remove_effect("Unconscious")
        
#         # Remove advantage on attacks against
#         stats_block.armor_class.remove_opponent_advantage_condition("Unconscious")
        
#         # Remove auto-critical condition
#         stats_block.armor_class.remove_opponent_auto_critical_condition("Unconscious")
        
#         # Remove disadvantage on attack rolls
#         for action in stats_block.actions:
#             if isinstance(action, Attack):
#                 action.remove_effect("Unconscious")
        
#         # Remove advantage and disadvantage conditions from armor class
#         stats_block.armor_class.remove_opponent_advantage_condition("Unconscious")
#         stats_block.armor_class.remove_opponent_disadvantage_condition("Unconscious")

#     @staticmethod
#     def unconscious_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         return True  # Always apply the effect when unconscious

#     @staticmethod
#     def unconscious_melee_check(source: 'StatsBlock', target: Optional['StatsBlock'], context: Optional[Dict[str, Any]] = None) -> bool:
#         if target is None or source is None:
#             return False
#         distance = source.get_distance(target.sensory.origin)
#         return distance is not None and distance <= 5  # 5 feet for melee range


## missing condition effects
## condition effects
# | **Status Effect**       | **Description**                                                                                             | **Required Components in Submodels**                                                                                        |
# |-------------------------|-------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
# | **Petrified**           | Transformed into solid inanimate substance, incapacitated, and unaware of surroundings.                     | `ActionEconomy`: Add logic to block actions and reactions; `Speed`: Add logic to set speed to 0; `SavingThrow`: Add failure condition. |
# | **Hiding**              | Makes Dexterity (Stealth) checks to hide.                                                                   | `AbilityCheck`: Add logic for hiding mechanic.                                                                              |
# | **Helping**             | Lends aid to another creature, giving advantage on next ability check or attack roll.                       | `Attack`: Add ability to apply advantage; `AbilityCheck`: Add ability to apply advantage.                                   |
