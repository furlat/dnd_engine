"""Test-only view over the canonical authored encounter assembler."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dnd.encounters.encounter import Encounter
from dnd.content.scenarios.scenario_catalog import encounter_definition
from dnd.content.scenarios.scenario_deployment import (
    AssembledScenario,
    assemble_scenario,
)
from dnd.entities.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@dataclass(frozen=True, slots=True)
class AuthoredEncounterView:
    """Convenience projection for mechanics tests, never a runtime path."""

    assembled: AssembledScenario

    @property
    def hero(self) -> Entity:
        return self.assembled.entities_by_roster_slot["roster_1"][0]

    @property
    def monsters(self) -> tuple[Entity, ...]:
        return self.assembled.entities_by_roster_slot["roster_2"]

    @property
    def encounter(self) -> Encounter:
        return self.assembled.encounter

    @property
    def controllers(self) -> dict[UUID, object]:
        return dict(self.assembled.controllers)

    @property
    def notable_positions(self) -> dict[str, tuple[int, int]]:
        return dict(self.assembled.notable_positions)

    @property
    def environment(self):
        return self.assembled.battlefield.environment


def assemble_authored_encounter(arena_id: str) -> AuthoredEncounterView:
    """Assemble one retained authored encounter through the product path."""
    reset_engine_runtime()
    return AuthoredEncounterView(
        assemble_scenario(
            Game(),
            encounter_definition(f"encounter.{arena_id}"),
        ),
    )


def reset_authored_encounter_state() -> None:
    """Reset the ordinary engine runtime used by authored encounter tests."""
    reset_engine_runtime()
