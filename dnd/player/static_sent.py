"""The static content each seat was sent: one record, the ids of each kind (plan §3.5).

It is written only from an emitted group (an initialization or a lineage), never in the middle of a walk. Each
kind is one field, typed by its id; the lanes that send a new kind add its field here.
"""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(slots=True)
class StaticSent:
    # Actors whose birth fields (their first whole body) the seat was sent: the actors it knows.
    actor_births: set[UUID] = field(default_factory=set)
    # Content descriptors the seat holds, by identity key.
    content: set[str] = field(default_factory=set)
    # Tiles whose static row the seat was sent, by tile uuid; tile looks (surface, name), by content id.
    tiles: set[UUID] = field(default_factory=set)
    tile_looks: set[str] = field(default_factory=set)
    # Residue materials whose static row the seat was sent, by residue id.
    residues: set[str] = field(default_factory=set)
    # Objects whose look the seat was sent (floor objects and contained items), by item uuid.
    object_looks: set[UUID] = field(default_factory=set)
    # Boundary structures the seat was sent, by content id.
    boundary_structures: set[str] = field(default_factory=set)


def merge_static_sent(sent: StaticSent, emitted: StaticSent) -> None:
    """An emitted group's static rows join what the seat was sent."""
    sent.actor_births.update(emitted.actor_births)
    sent.content.update(emitted.content)
    sent.tiles.update(emitted.tiles)
    sent.tile_looks.update(emitted.tile_looks)
    sent.residues.update(emitted.residues)
    sent.object_looks.update(emitted.object_looks)
    sent.boundary_structures.update(emitted.boundary_structures)
