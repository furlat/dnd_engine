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
