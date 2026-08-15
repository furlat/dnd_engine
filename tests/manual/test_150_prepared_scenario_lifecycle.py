"""Regression coverage for installing final controllers before encounter start."""

from __future__ import annotations

from typing import ClassVar

from dnd.controller import PassController
from dnd.types.encounter import EncounterState
from dnd.entity import Entity
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import (
    encounter_recipe,
)


class _RecordingController(PassController):
    """Record the encounter-start hook seen by a final controller."""

    started_entities: ClassVar[list[tuple[str, ...]]] = []

    def on_encounter_start(self, entities: list[Entity]) -> None:
        self.started_entities.append(tuple(sorted(str(entity.uuid) for entity in entities)))


def test_prepared_scenario_does_not_start_before_final_controllers_are_installed() -> None:
    _RecordingController.started_entities.clear()
    assembled = prepare_encounter_recipe(
        encounter_recipe("encounter.standard_skeleton_doors"),
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
