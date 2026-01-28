"""Re-export base spell classes from actions.py.

SpellAction and SpellEvent live in actions.py alongside other action infrastructure.
This module just re-exports them for convenience.
"""
from dnd.actions import SpellAction, SpellEvent

__all__ = ["SpellAction", "SpellEvent"]
