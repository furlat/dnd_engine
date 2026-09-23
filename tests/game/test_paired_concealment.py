"""Native concealment outcomes survive both saved subjective player packets."""

from pathlib import Path
from uuid import UUID

import pytest

from devtools.animation_review.cases import ConcealmentCase, load_cases
from devtools.animation_review.produce import produce
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue, SensoryUpdateEvent, SkillCheckEvent
from dnd.entity import Entity
from dnd.types.senses import SensesType
from game.player_facts import ItemChargeFact, SensoryFact, StepFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import reduce_interval
from game.replay import RecordedSequence


def contact_pattern(
    initially_visible: bool, other_uuid: UUID, events: tuple[SensoryUpdateEvent | SensoryFact, ...],
) -> tuple[bool, ...]:
    pattern = [initially_visible]
    for event in events:
        visible = pattern[-1]
        if other_uuid in event.entity_contacts_removed:
            visible = False
        if other_uuid in event.entity_contacts_changed:
            visible = event.entity_contacts_changed[other_uuid].visual
        if visible != pattern[-1]:
            pattern.append(visible)
    return tuple(pattern)


@pytest.mark.parametrize("case_id, expected_contact, expected_steps", [
    ("conceal-invisible-enemy", (True, False, True), 0),
    ("conceal-invisible-ally", (True, False, True), 0),
    ("conceal-greater-invisibility", (True, False, True), 0),
    ("conceal-see-invisibility", (True,), 2),
    ("conceal-true-spell-enemy", (True,), 2),
    ("conceal-true-spell-ally", (True,), 2),
    ("conceal-true-expiry", (True, False, True, False), 2),
    ("conceal-true-doorway", (True, False, True, False), 3),
    ("conceal-hide-enemy-blocked", (True,), 0),
    ("conceal-hide-ally", (True, False), 0),
    ("conceal-hide-dim-high", (True, False, True), 0),
    ("conceal-hide-dim-low", (True,), 2),
    ("conceal-stacked-true", (True, False, True), 0),
    ("conceal-hide-low-true", (True,), 2),
    ("conceal-true-potion-enemy", (True,), 2),
    ("conceal-true-potion-ally", (True,), 2),
])
def test_concealment_matrix_records_real_contact_and_replays_both_views(
    tmp_path: Path, case_id: str, expected_contact: tuple[bool, ...], expected_steps: int,
) -> None:
    case = next(row for row in load_cases() if row.id == case_id)
    assert isinstance(case.scenario, ConcealmentCase)
    scenario = case.scenario
    captured = produce(case)
    assert set(captured.views) == {"perceiver", "subject"}
    perceiver, subject = (captured.views[role] for role in ("perceiver", "subject"))
    assert perceiver.initialization.generation == subject.initialization.generation
    assert perceiver.initialization.end_cursor == subject.initialization.end_cursor
    assert [lineage.root.uuid for lineage in perceiver.lineages] == [lineage.root.uuid for lineage in subject.lineages]
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()

    for role, original in captured.views.items():
        native = RecordedSequence.model_validate_json(original.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        other_uuid = next(view.initialization.observer_uuid for name, view in captured.views.items() if name != role)
        before, _ = reduce_interval(None, native.initialization)
        assert before.senses is not None
        actual_contact = contact_pattern(other_uuid in before.senses.entities, other_uuid, tuple(
            event for lineage in native.lineages for event in lineage.events
            if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == before.observer_uuid))
        expected = expected_contact if role == "perceiver" or scenario.program == "doorway" else (True,)
        assert actual_contact == expected, (case_id, role, actual_contact)

        rolls = [event.dice_roll.total for lineage in native.lineages for event in lineage.events
                 if isinstance(event, SkillCheckEvent) and event.skill_name == "stealth" and event.dice_roll]
        hide_allowed = scenario.program in ("hide-dim", "stacked") or case_id == "conceal-hide-ally"
        assert rolls == ([scenario.stealth_face] if hide_allowed else [])
        if case_id == "conceal-hide-enemy-blocked":
            assert not native.lineages  # Discovery withheld Hide; there was no rejected action to animate.

        public_path = tmp_path / f"{role}.json"
        public_path.write_bytes(encode_player_sequence(project_sequence(native)))
        state, lineages = decode_player_sequence(public_path.read_bytes())
        own = state.actors[state.observer_uuid]
        assert own.controlled_items is not None
        potion_ids = {item.item_uuid for item in own.controlled_items
                      if item.item_id == "consumable.potion_true_seeing"}
        public_senses = tuple(node.fact for lineage in lineages for node in lineage.events
                              if isinstance(node.fact, SensoryFact))
        assert state.senses is not None
        assert contact_pattern(other_uuid in state.senses.entities, other_uuid, public_senses) == expected
        steps = [node.fact for lineage in lineages for node in lineage.events if isinstance(node.fact, StepFact)]
        if role == "perceiver":
            assert len(steps) == expected_steps
        for lineage in lineages:
            state = reduce_lineage(state, lineage)
            assert state.observer_uuid in state.actors
            assert all(actor.controlled_items is None for uuid, actor in state.actors.items() if uuid != state.observer_uuid)
        assert state.senses is not None and (other_uuid in state.senses.entities) == expected[-1]
        own = state.actors[state.observer_uuid]
        conditions = {condition.name for condition in own.conditions}
        if role == "subject":
            expected_conditions = ({"Invisible", "Concentrating"} if scenario.program in ("doorway", "sight-expiry")
                                   else {"Hidden"} if case_id == "conceal-hide-ally" else set())
            assert conditions == expected_conditions
            expected_position = ((8, 10) if scenario.program == "doorway" else (7, 3)
                                 if scenario.program == "hide-bright" else (9, 3))
            assert state.senses.position == expected_position
        else:
            true_remains = scenario.sight_grant != "none" and scenario.program != "sight-expiry"
            see_remains = scenario.program == "see-invisibility"
            assert conditions == ({"True Seeing"} if true_remains else {"See Invisibility"} if see_remains else set())
            assert any(mode.sense_type == SensesType.TRUESIGHT and mode.range_feet == 120
                       for mode in state.senses.sense_modes) == true_remains
            assert any(mode.sense_type == SensesType.SEE_INVISIBLE
                       for mode in state.senses.sense_modes) == see_remains

        charges = [node.fact for lineage in lineages for node in lineage.events if isinstance(node.fact, ItemChargeFact)]
        if scenario.sight_grant == "potion" and role == "perceiver":
            assert len(potion_ids) == 1 and len(charges) == 1
            assert charges[0].item_uuid in potion_ids and charges[0].item_destroyed
            assert charges[0].charges_after == 0
            assert own.controlled_items is not None
            assert not potion_ids.intersection(item.item_uuid for item in own.controlled_items)
        else:
            assert not charges
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
