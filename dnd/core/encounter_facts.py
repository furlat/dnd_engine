"""Narrow reads of encounter-owned opening-turn facts without an import cycle."""

from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from dnd.core.base_object import BaseObject


@dataclass(frozen=True, slots=True)
class OpeningTurnFacts:
    has_started_turn: bool
    is_surprised: bool


class EncounterFactsReader(Protocol):
    def opening_turn_facts(self, entity_uuid: UUID) -> OpeningTurnFacts | None: ...


def opening_turn_facts(encounter_uuid: UUID, entity_uuid: UUID) -> OpeningTurnFacts | None:
    """Read the exact active encounter identity already held by the actor."""
    owner = BaseObject.get_contribution_owner(encounter_uuid)
    if owner is None:
        return None
    return cast(EncounterFactsReader, owner).opening_turn_facts(entity_uuid)
