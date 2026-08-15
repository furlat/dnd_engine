"""Canonical ability, skill, and saving-throw identities."""

from enum import StrEnum


class AbilityName(StrEnum):
    """The six rules-level ability score identities."""

    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"


class SkillName(StrEnum):
    """The eighteen rules-level skill identities."""

    ACROBATICS = "acrobatics"
    ANIMAL_HANDLING = "animal_handling"
    ARCANA = "arcana"
    ATHLETICS = "athletics"
    DECEPTION = "deception"
    HISTORY = "history"
    INSIGHT = "insight"
    INTIMIDATION = "intimidation"
    INVESTIGATION = "investigation"
    MEDICINE = "medicine"
    NATURE = "nature"
    PERCEPTION = "perception"
    PERFORMANCE = "performance"
    PERSUASION = "persuasion"
    RELIGION = "religion"
    SLEIGHT_OF_HAND = "sleight_of_hand"
    STEALTH = "stealth"
    SURVIVAL = "survival"


class SavingThrowName(StrEnum):
    """The six ability-keyed saving-throw block identities."""

    STRENGTH = "strength_saving_throw"
    DEXTERITY = "dexterity_saving_throw"
    CONSTITUTION = "constitution_saving_throw"
    INTELLIGENCE = "intelligence_saving_throw"
    WISDOM = "wisdom_saving_throw"
    CHARISMA = "charisma_saving_throw"


__all__ = ["AbilityName", "SavingThrowName", "SkillName"]
