"""Dependency-neutral identities for persistent spatial conditions."""

from enum import Enum


class SpatialEffectLayer(str, Enum):
    """Independently occupiable world-condition layers."""

    GROUND_SURFACE = "ground_surface"
    CLOUD = "cloud"
    FIELD = "field"


class SpatialEffectAnchorKind(str, Enum):
    """How one spatial condition is anchored in the world."""

    FIXED_POSITION = "fixed_position"
    ENTITY = "entity"
    WORLD_OBJECT = "world_object"
    INDEPENDENT_MOVABLE = "independent_movable"


class SpatialEffectOccupancyPolicy(str, Enum):
    """How conditions sharing a layer may occupy one cell."""

    EXCLUSIVE_TRANSFORMING = "exclusive_transforming"
    OVERLAPPING = "overlapping"


class SpatialEffectBlockingPolicy(str, Enum):
    """Which portion of a condition footprint blocks traversal."""

    NONE = "none"
    ANCHOR = "anchor"
    FOOTPRINT = "footprint"


class SpatialEffectTriggerKind(str, Enum):
    """Mechanical moments at which a spatial condition may act."""

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
    """Observable lifecycle operations for a spatial condition."""

    CREATED = "created"
    FOOTPRINT_CHANGED = "footprint_changed"
    REVEALED = "revealed"
    REMOVED = "removed"
    TRANSFORMED = "transformed"


class SpatialEffectInteractionOperation(str, Enum):
    """Environmental operations which may affect spatial conditions."""

    IGNITE = "ignite"
    DOUSE = "douse"
    FREEZE = "freeze"
    ELECTRIFY = "electrify"
    VAPORIZE = "vaporize"
    DISPERSE = "disperse"


class SpatialEffectInteractionIntensity(str, Enum):
    """Rules-facing strength of an environmental interaction."""

    MINOR = "minor"
    MODERATE = "moderate"
    STRONG = "strong"


class SpatialEffectTransitionAction(str, Enum):
    """Transition applied to the intersecting cells of one condition."""

    REMOVE_AFFECTED = "remove_affected"
    REPLACE_AFFECTED = "replace_affected"
    REMOVE_AFFECTED_AND_CREATE_SECONDARY = (
        "remove_affected_and_create_secondary"
    )


__all__ = [
    "SpatialEffectAnchorKind",
    "SpatialEffectBlockingPolicy",
    "SpatialEffectChangeOperation",
    "SpatialEffectInteractionIntensity",
    "SpatialEffectInteractionOperation",
    "SpatialEffectLayer",
    "SpatialEffectOccupancyPolicy",
    "SpatialEffectTransitionAction",
    "SpatialEffectTriggerKind",
]
