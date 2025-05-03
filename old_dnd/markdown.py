from typing import List, Dict, Optional, Tuple, Any, Union
from pydantic import BaseModel, Field
from old_dnd.dnd_enums import (
    Ability, Alignment, Language, Size, MonsterType, Skills, AttackHand, 
    SensesType, DamageType, UnarmoredAc, ArmorType, WeaponProperty, AttackType, RangeType
)
from old_dnd.statsblock import StatsBlock
from old_dnd.monsters.goblin import create_goblin
class MarkdownCharacterSheetGenerator:
    def __init__(self, stats_block: StatsBlock):
        self.stats_block = stats_block

    def generate(self) -> str:
        parts = [
            self._generate_general_info(),
            self._generate_proficiency(),
            self._generate_speed(),
            self._generate_ability_scores(),
            self._generate_skills(),
            self._generate_saving_throws(),
            self._generate_armor_class(),
            self._generate_action_economy(),
            self._generate_sensory(),
            self._generate_health(),
            self._generate_spellcasting(),
            self._generate_condition_manager(),
            self._generate_attacks(),
            self._generate_other_info()
        ]
        return "\n\n".join(parts)
    
    def _generate_general_info(self) -> str:
        meta = self.stats_block.meta
        return (
            "# Character Sheet: {}\n\n"
            "## General Information\n"
            "- **Name:** {}\n"
            "- **ID:** {}\n"
            "- **Size:** {}\n"
            "- **Type:** {}\n"
            "- **Alignment:** {}\n"
            "- **Languages:** {}\n"
            "- **Challenge Rating:** {}\n"
            "- **Experience Points:** {}"
        ).format(
            meta.name,
            meta.name,
            meta.id,
            meta.size.value,
            meta.type.value,
            meta.alignment.value,
            ", ".join([lang.value for lang in meta.languages]),
            meta.challenge,
            meta.experience_points
        )

    def _generate_proficiency(self) -> str:
        proficiency = self.stats_block.proficiency_bonus.base_value.base_value
        return (
            "## Proficiency\n"
            "- **Proficiency Bonus:** {}"
        ).format(proficiency)

    def _generate_speed(self) -> str:
        speed = self.stats_block.speed
        return (
            "## Speed\n"
            "- **Walk:** {} feet/turn\n"
            "- **Fly:** {} feet/turn\n"
            "- **Swim:** {} feet/turn\n"
            "- **Burrow:** {} feet/turn\n"
            "- **Climb:** {} feet/turn"
        ).format(
            speed.walk.base_value.base_value,
            speed.fly.base_value.base_value,
            speed.swim.base_value.base_value,
            speed.burrow.base_value.base_value,
            speed.climb.base_value.base_value
        )

    def _generate_ability_scores(self) -> str:
        abilities = self.stats_block.ability_scores
        ability_template = "| **{}** | {} | +{} |\n"
        return (
            "## Ability Scores\n"
            "| Ability      | Score | Modifier |\n"
            "|--------------|-------|-----------|\n" +
            ability_template.format(
                Ability.STR.value, abilities.strength.score.base_value.base_value,
                abilities.strength.get_modifier()
            ) +
            ability_template.format(
                Ability.DEX.value, abilities.dexterity.score.base_value.base_value,
                abilities.dexterity.get_modifier()
            ) +
            ability_template.format(
                Ability.CON.value, abilities.constitution.score.base_value.base_value,
                abilities.constitution.get_modifier()
            ) +
            ability_template.format(
                Ability.INT.value, abilities.intelligence.score.base_value.base_value,
                abilities.intelligence.get_modifier()
            ) +
            ability_template.format(
                Ability.WIS.value, abilities.wisdom.score.base_value.base_value,
                abilities.wisdom.get_modifier()
            ) +
            ability_template.format(
                Ability.CHA.value, abilities.charisma.score.base_value.base_value,
                abilities.charisma.get_modifier()
            )
        )

    def _generate_skills(self) -> str:
        skills = self.stats_block.skillset
        skill_template = "| **{}** | {} | {} | +{} |\n"
        return (
            "## Skills\n"
            "| Skill            | Proficient | Expertise | Modifier |\n"
            "|------------------|------------|-----------|-----------|\n" +
            "\n".join([
                skill_template.format(
                    skill.value,
                    "Yes" if getattr(skills, skill.name.lower()).proficient else "No",
                    "Yes" if getattr(skills, skill.name.lower()).expertise else "No",
                    getattr(skills, skill.name.lower()).bonus.apply(self.stats_block).total_bonus
                ) for skill in Skills
            ])
        )

    def _generate_saving_throws(self) -> str:
        saves = self.stats_block.saving_throws
        save_template = "| **{}** | {} | +{} |\n"
        return (
            "## Saving Throws\n"
            "| Ability      | Proficient | Modifier |\n"
            "|--------------|------------|-----------|\n" +
            save_template.format(
                Ability.STR.value, "Yes" if saves.strength.proficient else "No",
                saves.strength.bonus.apply(self.stats_block).total_bonus
            ) +
            save_template.format(
                Ability.DEX.value, "Yes" if saves.dexterity.proficient else "No",
                saves.dexterity.bonus.apply(self.stats_block).total_bonus
            ) +
            save_template.format(
                Ability.CON.value, "Yes" if saves.constitution.proficient else "No",
                saves.constitution.bonus.apply(self.stats_block).total_bonus
            ) +
            save_template.format(
                Ability.INT.value, "Yes" if saves.intelligence.proficient else "No",
                saves.intelligence.bonus.apply(self.stats_block).total_bonus
            ) +
            save_template.format(
                Ability.WIS.value, "Yes" if saves.wisdom.proficient else "No",
                saves.wisdom.bonus.apply(self.stats_block).total_bonus
            ) +
            save_template.format(
                Ability.CHA.value, "Yes" if saves.charisma.proficient else "No",
                saves.charisma.bonus.apply(self.stats_block).total_bonus
            )
        )

    def _generate_armor_class(self) -> str:
        ac = self.stats_block.armor_class
        return (
            "## Armor Class\n"
            "- **Base AC:** {}\n"
            "- **Equipped Armor:** {}\n"
            "- **Equipped Shield:** {}\n"
            "- **Unarmored AC:** {}"
        ).format(
            ac.base_ac,
            f"{ac.equipped_armor.name} (base AC {ac.equipped_armor.base_ac} + DEX bonus)" if ac.equipped_armor else "None",
            f"{ac.equipped_shield.name} (AC bonus {ac.equipped_shield.ac_bonus})" if ac.equipped_shield else "None",
            ac.unarmored_ac.value if ac.unarmored_ac != UnarmoredAc.NONE else "None"
        )

    def _generate_action_economy(self) -> str:
        ae = self.stats_block.action_economy
        return (
            "## Action Economy\n"
            "| Action Type      | Base Value |\n"
            "|------------------|------------|\n"
            "| **Actions**      | {}         |\n"
            "| **Bonus Actions**| {}         |\n"
            "| **Reactions**    | {}         |\n"
            "| **Movement**     | {} feet/turn |"
        ).format(
            ae.actions.base_value.base_value,
            ae.bonus_actions.base_value.base_value,
            ae.reactions.base_value.base_value,
            ae.movement.base_value.base_value
        )

    def _generate_sensory(self) -> str:
        sensory = self.stats_block.sensory
        senses = ", ".join([f"{sense.type.value} ({sense.range} feet)" for sense in sensory.senses])
        return f"## Sensory\n- **Senses:** {senses}"

    def _generate_health(self) -> str:
        health = self.stats_block.health
        return (
            "## Health\n"
            "- **Hit Dice:** {}d{}\n"
            "- **Max Hit Points:** {}\n"
            "- **Current Hit Points:** {}\n"
            "- **Temporary Hit Points:** {}\n"
            "- **Damage Taken:** {}\n"
        ).format(
            health.hit_dice_count, health.hit_dice_value,
            health.max_hit_points, health.current_hit_points,
            health.current_temporary_hit_points, health.damage_taken
        )

    def _generate_spellcasting(self) -> str:
        return (
            "## Spellcasting\n"
            "- **Spellcasting Ability:** {}"
        ).format(self.stats_block.spellcasting_ability.value)

    def _generate_condition_manager(self) -> str:
        cm = self.stats_block.condition_manager
        return (
            "## Condition Manager\n"
            "- **Active Conditions:** {}\n"
            "- **Condition Immunities:** {}\n"
            "- **Contextual Condition Immunities:** {}"
        ).format(
            cm.active_conditions,
            cm.condition_immunities,
            cm.contextual_condition_immunities
        )

    def _generate_attacks(self) -> str:
        am = self.stats_block.attacks_manager
        attacks = []
        if am.melee_right_hand:
            attacks.append(self._generate_weapon_block("Melee Weapon (Right Hand)", am.melee_right_hand))
        if am.melee_left_hand:
            attacks.append(self._generate_weapon_block("Melee Weapon (Left Hand)", am.melee_left_hand))
        if am.ranged_right_hand:
            attacks.append(self._generate_weapon_block("Ranged Weapon (Right Hand)", am.ranged_right_hand))
        if am.ranged_left_hand:
            attacks.append(self._generate_weapon_block("Ranged Weapon (Left Hand)", am.ranged_left_hand))
        return "## Attacks\n" + "\n".join(attacks)

    def _generate_weapon_block(self, name: str, weapon: Any) -> str:
        return (
            f"### {name}\n"
            "- **Name:** {}\n"
            "- **Damage:** 1d{} ({})\n"
            "- **Properties:** {}\n"
            "- **Range:** {}"
        ).format(
            weapon.name,
            weapon.damage_dice, weapon.damage_type.value,
            ", ".join([prop.value for prop in weapon.properties]),
            self._format_range(weapon.range)
        )

    def _format_range(self, range) -> str:
        if range.type == RangeType.REACH:
            return f"Reach ({range.normal} feet)"
        return f"Normal {range.normal} feet, Long {range.long} feet" if range.long else f"Normal {range.normal} feet"

    def _generate_other_info(self) -> str:
        health = self.stats_block.health
        return (
            "## Other Information\n"
            "- **Proficiencies:** {}\n"
            "- **Expertise:** {}\n"
            "- **Vulnerabilities:** {}\n"
            "- **Resistances:** {}\n"
            "- **Immunities:** {}\n"
            "- **Is Dead:** {}\n"
            "- **Total Hit Points:** {}\n"
            "- **Current Temporary Hit Points:** {}"
        ).format(
            self.stats_block.skillset.proficiencies,
            self.stats_block.skillset.expertise,
            health.vulnerabilities,
            health.resistances,
            health.immunities,
            health.is_dead,
            health.total_hit_points,
            health.current_temporary_hit_points
        )
# Example usage:
stats_block_instance = create_goblin()
generator = MarkdownCharacterSheetGenerator(stats_block_instance)
markdown_output = generator.generate()
print(markdown_output)
