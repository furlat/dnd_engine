"""Canonical ability, skill, and saving-throw identities."""

from typing import Literal, TypeAlias


AbilityName: TypeAlias = Literal[
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
]

SkillName: TypeAlias = Literal[
    "acrobatics",
    "animal_handling",
    "arcana",
    "athletics",
    "deception",
    "history",
    "insight",
    "intimidation",
    "investigation",
    "medicine",
    "nature",
    "perception",
    "performance",
    "persuasion",
    "religion",
    "sleight_of_hand",
    "stealth",
    "survival",
]

SavingThrowName: TypeAlias = Literal[
    "strength_saving_throw",
    "dexterity_saving_throw",
    "constitution_saving_throw",
    "intelligence_saving_throw",
    "wisdom_saving_throw",
    "charisma_saving_throw",
]


__all__ = ["AbilityName", "SavingThrowName", "SkillName"]
