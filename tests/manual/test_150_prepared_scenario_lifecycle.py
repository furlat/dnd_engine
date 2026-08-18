"""Regression coverage for installing final controllers before encounter start."""

from __future__ import annotations

from typing import ClassVar

from dnd.content.scenarios.scenario_catalog import encounter_definition
from dnd.content.scenarios.scenario_deployment import prepare_scenario
from dnd.encounters.controllers import PassController
from dnd.types.encounter_state import EncounterState
from dnd.entities.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


class _RecordingController(PassController):
    """Record the encounter-start hook seen by a final controller."""

    started_entities: ClassVar[list[tuple[str, ...]]] = []

    def on_encounter_start(self, entities: list[Entity]) -> None:
        self.started_entities.append(tuple(sorted(str(entity.uuid) for entity in entities)))


def test_prepared_scenario_does_not_start_before_final_controllers_are_installed() -> None:
    _RecordingController.started_entities.clear()
    reset_engine_runtime()
    assembled = prepare_scenario(
        Game(),
        encounter_definition("encounter.standard_skeleton_doors"),
    )
    encounter = assembled.encounter

    assert encounter.state is EncounterState.NOT_STARTED
    assert encounter.get_current_entity() is None

    for actor in assembled.entities:
        encounter.set_controller_for(
            actor.uuid,
            _RecordingController(source_entity_uuid=actor.uuid),
        )

    encounter.start_encounter()

    assert encounter.state is EncounterState.ACTIVE
    assert encounter.get_current_entity() is not None
    assert len(_RecordingController.started_entities) == len(
        assembled.entities,
    )
    assert all(len(entity_uuids) == 1 for entity_uuids in _RecordingController.started_entities)
