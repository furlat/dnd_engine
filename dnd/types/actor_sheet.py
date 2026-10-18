"""A player character's evaluated sheet groups as native values: what the sheet publisher compares and publishes.

These are the sheet fields that are computed when read and change with no event of their own. The
rest of a character's sheet travels with its own events: HP, name and portrait with the body facts;
species, background, origin, class levels, spellbook, feature uses and preparations with the birth
and their change events.
"""

from dataclasses import dataclass
from uuid import UUID

from dnd.core.action_types import AvailableHandlerInfo
from dnd.types.abilities import AbilityName


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerResource:
    """One spendable channel or resource row of a sheet; its label is fixed by its key."""

    key: str
    label: str
    current: int
    maximum: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerResourceValue:
    """A resource row's new values, by its key."""

    key: str
    current: int
    maximum: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ActorSheetState:
    """The sheet groups evaluated at a publication boundary."""

    abilities: tuple[tuple[AbilityName, int], ...]
    skills: tuple[str, ...]
    expertise: tuple[str, ...]
    saves: tuple[str, ...]
    proficiency_bonus: int
    resources: tuple[PlayerResource, ...]
    compatible_item_slots: tuple[tuple[UUID, tuple[str, ...]], ...]
    handler_details: tuple[AvailableHandlerInfo, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ActorSheetChange:
    """One publication's keyed change of an actor's sheet groups.

    An actor's first publication carries every group. Later ones carry the groups that changed
    (None: unchanged). `resources` is whole when its key sequence changed; otherwise
    `resource_values` names the rows whose values changed.
    """

    abilities: tuple[tuple[AbilityName, int], ...] | None = None
    skills: tuple[str, ...] | None = None
    expertise: tuple[str, ...] | None = None
    saves: tuple[str, ...] | None = None
    proficiency_bonus: int | None = None
    resources: tuple[PlayerResource, ...] | None = None
    resource_values: tuple[PlayerResourceValue, ...] = ()
    compatible_item_slots: tuple[tuple[UUID, tuple[str, ...]], ...] | None = None
    handler_details: tuple[AvailableHandlerInfo, ...] | None = None
