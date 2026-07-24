"""Dependency-neutral creature life-state contracts."""

from enum import Enum


class LifeState(str, Enum):
    """Authoritative lifecycle state stored by an entity's health block."""

    ALIVE = "alive"
    DYING = "dying"
    STABLE = "stable"
    DEAD = "dead"


class LifeStateChangeReason(str, Enum):
    """Rules-facing cause of a requested life-state transition."""

    DAMAGE = "damage"
    MASSIVE_DAMAGE = "massive_damage"
    INSTANT_DEATH = "instant_death"
    DEATH_SAVE_FAILURES = "death_save_failures"
    STABILIZATION = "stabilization"
    HEALING = "healing"
    REVIVAL = "revival"
    DIRECT_STATE_CHECK = "direct_state_check"
