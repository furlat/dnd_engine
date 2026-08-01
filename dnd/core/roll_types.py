"""Dependency-neutral enums describing resolved and pending roll states."""

from enum import Enum


class AdvantageStatus(str, Enum):
    """Net d20 advantage state after advantage and disadvantage cancel."""

    NONE = "None"
    ADVANTAGE = "Advantage"
    DISADVANTAGE = "Disadvantage"
