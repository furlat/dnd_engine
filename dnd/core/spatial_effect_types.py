"""Dependency-neutral identities for persistent spatial effects."""

from enum import Enum


class SpatialEffectLayer(str, Enum):
    """Independently occupiable world-effect layers."""

    GROUND_SURFACE = "ground_surface"
    CLOUD = "cloud"
    FIELD = "field"


class SpatialEffectAnchorKind(str, Enum):
    """How one effect footprint is positioned in the world."""

    FIXED_POSITION = "fixed_position"
    ENTITY = "entity"
    WORLD_OBJECT = "world_object"
    INDEPENDENT_MOVABLE = "independent_movable"


class SpatialEffectOccupancyPolicy(str, Enum):
    """How effects sharing a layer may occupy the same grid cell."""

    EXCLUSIVE_TRANSFORMING = "exclusive_transforming"
    OVERLAPPING = "overlapping"


class SpatialEffectBlockingPolicy(str, Enum):
    """Which part of an effect's footprint physically blocks traversal."""

    NONE = "none"
    ANCHOR = "anchor"
    FOOTPRINT = "footprint"


class SpatialEffectTriggerKind(str, Enum):
    """Closed mechanical moments at which an effect may affect occupants."""

    APPEAR = "appear"
    ENTER = "enter"
    EFFECT_ENTERS_OCCUPANT = "effect_enters_occupant"
    EFFECT_LEAVES_OCCUPANT = "effect_leaves_occupant"
    LEAVE = "leave"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    MOVEMENT_INTERVAL = "movement_interval"
    ROUND_TICK = "round_tick"
    INTERACTION = "interaction"
    REMOVAL = "removal"


class SpatialEffectChangeOperation(str, Enum):
    """Observable lifecycle operation for one independent effect instance."""

    CREATED = "created"
    FOOTPRINT_CHANGED = "footprint_changed"
    REVEALED = "revealed"
    REMOVED = "removed"
    TRANSFORMED = "transformed"


class SpatialEffectInteractionOperation(str, Enum):
    """Closed environmental operations that can affect spatial phenomena."""

    IGNITE = "ignite"
    DOUSE = "douse"
    FREEZE = "freeze"
    ELECTRIFY = "electrify"
    VAPORIZE = "vaporize"
    DISPERSE = "disperse"


class SpatialEffectInteractionIntensity(str, Enum):
    """Rules-facing strength band for an environmental operation."""

    MINOR = "minor"
    MODERATE = "moderate"
    STRONG = "strong"


class SpatialEffectTransitionAction(str, Enum):
    """State transition applied to the intersecting cells of one effect."""

    REMOVE_AFFECTED = "remove_affected"
    REPLACE_AFFECTED = "replace_affected"
    REMOVE_AFFECTED_AND_CREATE_SECONDARY = (
        "remove_affected_and_create_secondary"
    )


__all__ = [
    "SpatialEffectAnchorKind",
    "SpatialEffectChangeOperation",
    "SpatialEffectInteractionIntensity",
    "SpatialEffectInteractionOperation",
    "SpatialEffectLayer",
    "SpatialEffectBlockingPolicy",
    "SpatialEffectOccupancyPolicy",
    "SpatialEffectTriggerKind",
    "SpatialEffectTransitionAction",
]
