"""Regression coverage for installing final controllers before encounter start."""

from __future__ import annotations

from typing import ClassVar

from dnd.controller import PassController
from dnd.encounter import EncounterState
from dnd.entity import Entity
from dnd.scenarios.evaluation.assembler import prepare_legacy_scenario


class _RecordingController(PassController):
    """Record the encounter-start hook seen by a final controller."""

    started_entities: ClassVar[list[tuple[str, ...]]] = []

    def on_encounter_start(self, entities: list[Entity]) -> None:
        self.started_entities.append(tuple(sorted(str(entity.uuid) for entity in entities)))


def test_prepared_scenario_does_not_start_before_final_controllers_are_installed() -> None:
    _RecordingController.started_entities.clear()
    arena = prepare_legacy_scenario("standard_skeleton_doors", opening_faction="heroes")

    assert arena.encounter.state is EncounterState.NOT_STARTED
    assert arena.encounter.get_current_entity() is None

    for actor in (*arena.side_a, *arena.side_b):
        arena.encounter.set_controller_for(
            actor.uuid,
            _RecordingController(source_entity_uuid=actor.uuid),
        )

    arena.encounter.start_encounter()

    assert arena.encounter.state is EncounterState.ACTIVE
    assert arena.encounter.get_current_entity() is not None
    assert len(_RecordingController.started_entities) == len((*arena.side_a, *arena.side_b))
    assert all(len(entity_uuids) == 1 for entity_uuids in _RecordingController.started_entities)
