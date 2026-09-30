"""Window family content scaffold; not registered as playable items yet.

These identities describe the ten confirmed Fantasy families. Physical profiles,
parent destruction and traversal must be completed before adding live builders.
Artwork bindings belong to presentation data, not these definitions.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from dnd.content.items.authored_item_definitions import AuthoredItemDefinition


@dataclass(frozen=True, slots=True)
class WindowDefinition:
    """One family with a parent wall and an optional, separate insert target."""

    wall: AuthoredItemDefinition
    insert: AuthoredItemDefinition | None


def _grilled_window(code: str) -> WindowDefinition:
    return WindowDefinition(
        wall=AuthoredItemDefinition(
            item_id=f"environment.window.fantasy_{code}.wall",
            name=f"Window wall {code.upper()}",
            description="A wall surrounding a window opening, with its frame and sill.",
            tags=("environment", "window_frame"),
        ),
        insert=AuthoredItemDefinition(
            item_id=f"environment.window.fantasy_{code}.insert",
            name=f"Window grille {code.upper()}",
            description="A fixed grille in the opening, separate from the surrounding wall.",
            tags=("environment", "window_insert", "fixed_grille"),
        ),
    )


WINDOW_DEFINITIONS: Mapping[str, WindowDefinition] = MappingProxyType({
    "environment.window.fantasy_a4": _grilled_window("a4"),
    "environment.window.fantasy_a5": _grilled_window("a5"),
    "environment.window.fantasy_c4": _grilled_window("c4"),
    "environment.window.fantasy_d16": _grilled_window("d16"),
    "environment.window.fantasy_d7": _grilled_window("d7"),
    "environment.window.fantasy_f16": _grilled_window("f16"),
    "environment.window.fantasy_f7": _grilled_window("f7"),
    "environment.window.fantasy_g7": WindowDefinition(
        wall=AuthoredItemDefinition(
            item_id="environment.window.fantasy_g7.wall",
            name="Empty window wall G7",
            description="A wall with an empty window opening; no insert fills the aperture.",
            tags=("environment", "window_frame", "empty_aperture"),
        ),
        insert=None,
    ),
    "environment.window.fantasy_g8": _grilled_window("g8"),
    "environment.window.fantasy_g9": WindowDefinition(
        wall=AuthoredItemDefinition(
            item_id="environment.window.fantasy_g9.wall",
            name="Shuttered window wall G9",
            description="A wall surrounding a shuttered window, with its frame and sill.",
            tags=("environment", "window_frame"),
        ),
        insert=AuthoredItemDefinition(
            item_id="environment.window.fantasy_g9.insert",
            name="Window shutter G9",
            description="A fixed wooden shutter filling the opening, separate from the wall.",
            tags=("environment", "window_insert", "shutter"),
        ),
    ),
})
